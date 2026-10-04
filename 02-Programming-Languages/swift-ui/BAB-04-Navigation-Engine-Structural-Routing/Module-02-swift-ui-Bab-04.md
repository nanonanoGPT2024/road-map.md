# BAB 04: Navigation Engine & Structural Routing
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menguasai arsitektur internal mesin navigasi SwiftUI modern (`NavigationStack`, `NavigationPath`, dan `NavigationSplitView`) serta interaksinya dengan `UINavigationController` di lapisan bawah (*underlying UIKit layer*).
- Merancang dan mengimplementasikan pola arsitektur navigasi decoupled tingkat *enterprise* (*Router/Coordinator Pattern*) berbasis Swift Concurrency dan Observation framework (`@Observable`).
- Mengelola state navigasi terprogram (*programmatic routing*), *deep linking*, *universal linking*, dan *state restoration* berbasis `Codable`.
- Menangani koordinasi modal kompleks (*sheet*, *fullScreenCover*, *inspector*) secara deterministik bersamaan dengan *push-pop stack*.
- Mendiagnosis dan mengeliminasi *memory leak*, *retain cycle*, *view-identity thrashing*, dan pemecahan *render tree* akibat mutasi path navigasi yang tidak sinkron.

---

### 2. Prerequisite
Untuk menyerap materi ini secara maksimal, Anda harus memahami:
- Swift 5.9+ / Swift 6: Semantik *Value Type* vs *Reference Type*, Protokol `Hashable`, `Codable`, `Sendable`, dan *Actor isolation* (`@MainActor`).
- SwiftUI Fundamentals: Siklus hidup View, *Identity* (Explicit vs Structural Identity), `@State`, `@Binding`, dan framework `Observation` (`@Observable`).
- Dasar Pemrograman iOS: Konsep *Responder Chain*, *Call Stack*, dan arsitektur `UINavigationController`/`UISplitViewController`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Evolusi Navigation Engine: Dari View Graph Coupling ke Data-Driven Stacks
Pada iterasi awal SwiftUI (iOS 13–15), navigasi diikat langsung ke pohon tampilan (*View Graph*) menggunakan `NavigationLink(destination:isActive:)`. Pendekatan ini memiliki kelemahan fatal:
1. **Eager Evaluation:** Tampilan tujuan (*destination view*) diinisialisasi secara instan saat tampilan induk dirender, meskipun tautan belum ditekan pengguna.
2. **Brittle State Binding:** Pengikatan status boolean individual untuk setiap rute memicu *bug* desinkronisasi status UIKit internal, menyebabkan *popping unprompted* atau animasi macet saat menangani hierarki bersarang (*nested hierarchies*).

Mulai iOS 16+, Apple merombak total paradigma ini dengan memperkenalkan `NavigationStack` dan `NavigationPath`. Model baru ini memisahkan **tampilan struktural** dari **tumpukan data (*data-driven path*)**.

```
                +---------------------------------------+
                |         NavigationStack Root          |
                +---------------------------------------+
                                   |
                   Bound via $path (NavigationPath)
                                   v
+---------------------------------------------------------------------+
| Backing Storage: Dynamic Array / Type-Erased Heterogeneous Buffer   |
| [ Route.dashboard, Route.transaction(id: 102), Route.receipt(id: 9) ]|
+---------------------------------------------------------------------+
                                   |
         Matched via .navigationDestination(for: Destination.self)
                                   v
+---------------------------------------------------------------------+
|                      SwiftUI View Graph Resolution                  |
| DestinationViewFactory evaluates data element -> Emits Lazy View   |
+---------------------------------------------------------------------+
                                   |
                          Underlying Bridge
                                   v
+---------------------------------------------------------------------+
|                        UINavigationController                       |
|   setViewControllers(_:animated:) managed automatically via diffs   |
+---------------------------------------------------------------------+
```

#### 3.2. Representasi Internal: Type-Safe vs Type-Erased Path
- **Typed Collections (`[Destination]`):** Ketika tumpukan navigasi bersifat homogen (hanya terdiri dari satu tipe enum), array standar Swift dapat langsung diikat. Ini memberikan performa kompilasi tercepat dan konsistensi tipe yang mutlak.
- **Type-Erased Path (`NavigationPath`):** Jika tumpukan navigasi harus mendukung tipe data heterogen, `NavigationPath` menggunakan representasi *type-erased box* berbasis `_NavigationPathRepresentable`. Di balik layar, tipe ini menyimpan array elemen `AnyHashable` serta mampu diserialisasi menjadi JSON/Property List jika setiap komponen mengimplementasikan protokol `Codable`.

#### 3.3. Resolusi View dan Siklus Hidup Memori
Modifier `.navigationDestination(for: Value.self)` mendaftarkan *closure factory* ke dalam environment pohon tampilan. Saat elemen baru di-push ke dalam koleksi path:
1. `NavigationStack` membandingkan tipe elemen terhadap tabel pendaftaran factory yang ada pada *View Graph*.
2. SwiftUI membangun simpul baru pada *AttributeGraph* privat internal runtime.
3. Transisi visual didelegasikan ke `UINavigationController` bawaan sistem, memicu push controller yang membungkus *hosting controller* (`UIHostingController`).
4. Berbeda dengan mekanisme lama, *destination view* bersifat **lazy evaluated**; *body* dari tampilan hanya dievaluasi ketika view benar-benar akan tampil ke layar.
5. Saat path di-*pop*, node pada *AttributeGraph* dihancurkan secara deterministik, memicu pelepasan memori (*deallocation*) dari seluruh state lokal milik tampilan tersebut.

---

### 4. Why & What

| Dimensi | Legacy NavigationLink (iOS 13-15) | Data-Driven NavigationStack (iOS 16+) |
| :--- | :--- | :--- |
| **Paradigma** | Deklaratif berbasis View-Tree Coupling | Data-driven, terpisah antara Data State & View |
| **Inisialisasi Destination** | Eager (dibuat bersamaan dengan induk) | Lazy (hanya dibuat saat rute aktif/masuk stack) |
| **Pop-to-Root** | Sangat kompleks (memerlukan hack binding) | Trivial: mengosongkan path array (`path.removeAll()`) |
| **Deep Link Handling** | Rawan race-condition dan animasi glitch | Deterministik (tambahkan batch elemen ke path array) |
| **State Serialization** | Tidak didukung secara native | Didukung native via `NavigationPath.CodableRepresentation` |
| **Dukungan iPad/Mac** | Memaksa perilaku stack yang kaku | Menggunakan `NavigationSplitView` terintegrasi |

---

### 5. How (Workflow Detail)

Alur kerja arsitektur perutean perusahaan (*Enterprise Routing Workflow*):

```
[Incoming Intent: DeepLink / User Action / Push Notification]
                           │
                           ▼
            ┌─────────────────────────────┐
            │   AppCoordinator / Router   │
            │      (@Observable Class)    │
            └──────────────┬──────────────┘
                           │ Parse & Validate State
                           ▼
          ┌───────────────────────────────────┐
          │  Route Mutator & Auth Interceptor │
          │  (Redirect if unauthorized)       │
          └────────────────┬──────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
┌─────────────────────────┐ ┌─────────────────────────┐
│ Push to NavigationPath  │ │ Present Sheet / Overlay │
│ path.append(Route.order)│ │ activeSheet = .checkout │
└────────────┬────────────┘ └────────────┬────────────┘
             │                           │
             └─────────────┬─────────────┘
                           ▼
          ┌───────────────────────────────────┐
          │   NavigationStack View Bridge     │
          │   Re-evaluates registered         │
          │   .navigationDestination()        │
          └────────────────┬──────────────────┘
                           │
                           ▼
          ┌───────────────────────────────────┐
          │ Rendering Engine displays target  │
          │ and triggers transaction-safe anim│
          └───────────────────────────────────┘
```

1. **Intersepsi Input:** *Deep link* URL atau interaksi UI diterima oleh lapisan routing terpusat (*AppCoordinator* atau *Router*).
2. **Validasi & State Guarding:** Router memeriksa integritas payload serta status autentikasi/otorisasi pengguna saat ini (misal: redirect ke *Login* jika sesi habis).
3. **Mutasi Data State Navigasi:** Status path internal diubah secara atomik pada `@MainActor`.
4. **Graph Binding Dispatch:** Perubahan state terdeteksi oleh `NavigationStack`, merender ulang container dan mengeksekusi transisi native.
5. **State Persistensi (Opsional):** Jika aplikasi berpindah ke background, representasi path disimpan ke disk (`Codable`).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Call Stack Eksekusi Program
Bayangkan `NavigationStack` persis seperti *Call Stack* pada prosesor:
- **Stack Pointer:** Variabel `path` bertindak sebagai penunjuk instruksi saat ini.
- **Push Frame (`append`):** Menambahkan fungsi baru ke memori eksekusi.
- **Pop Frame (`removeLast`):** Menyelesaikan eksekusi fungsi dan kembali ke baris pemanggil.
- **Jump to Base (`removeAll`):** Mengembalikan program langsung ke fungsi `main()`.

#### Diagram Topologi Routing Enterprise
```
+---------------------------------------------------------------------------------+
|                                   AppRouter                                     |
|  - path: NavigationPath                                                         |
|  - presentedSheet: SheetDestination?                                            |
|  - presentedCover: FullScreenDestination?                                       |
+---------------------------------------------------------------------------------+
        │                                 │                              │
        │ drives                          │ drives                       │ drives
        ▼                                 ▼                              ▼
+-----------------------+     +-----------------------+     +-----------------------+
|   NavigationStack     |     |   .sheet() modifier   |     | .fullScreenCover()    |
|   Root: HomeView      |     |                       |     |                       |
+-----------------------+     +-----------------------+     +-----------------------+
        │                                 │                              │
        ├── Push DetailView               ├── Presents ModalFlow         └── Presents AuthFlow
        │                                 │                                  (Full Overlay)
        └── Push SettingsView             └── Presents WebBrowser
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Typed Programmatic Navigation
Implementasi dasar berbasis enum tunggal tanpa type-erasure.

```swift
import SwiftUI

enum SettingsRoute: Hashable {
    case profile
    case notifications
    case privacyPolicy(version: String)
}

struct SimpleSettingsView: View {
    @State private var path: [SettingsRoute] = []

    var body: some View {
        NavigationStack(path: $path) {
            List {
                Button("Profil Pengguna") {
                    path.append(.profile)
                }
                Button("Pengaturan Notifikasi") {
                    path.append(.notifications)
                }
                Button("Kebijakan Privasi") {
                    path.append(.privacyPolicy(version: "2.4.0"))
                }
            }
            .navigationTitle("Pengaturan")
            .navigationDestination(for: SettingsRoute.self) { route in
                switch route {
                case .profile:
                    Text("Layar Profil Pengguna")
                case .notifications:
                    Text("Preferensi Notifikasi")
                case .privacyPolicy(let version):
                    VStack(spacing: 16) {
                        Text("Kebijakan Privasi v\(version)")
                        Button("Kembali ke Awal (Pop-to-Root)") {
                            path.removeAll()
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }
            }
        }
    }
}
```

#### 7.2. Practical Example: Enterprise Multi-Flow Decoupled Router
Implementasi tingkat produksi menggunakan Swift Concurrency, Observation framework, deep link parser, penanganan modal/sheet terintegrasi, dan *state restoration* berbasis `Codable`.

```swift
import SwiftUI
import OSLog

// MARK: - 1. Routing Contracts & Models

private let logger = Logger(subsystem: "com.enterprise.app.routing", category: "Navigation")

public protocol AppRouteDefinition: Hashable, Codable, Sendable {}

public enum AppRoute: AppRouteDefinition {
    case productList(category: String)
    case productDetail(productID: UUID)
    case checkout(cartID: String)
    case orderStatus(orderID: String, isSuccess: Bool)
}

public enum ModalSheet: Identifiable, Hashable, Sendable {
    case userProfile
    case filters(activeCategory: String)

    public var id: String {
        switch self {
        case .userProfile: return "userProfile"
        case .filters(let cat): return "filters_\(cat)"
        }
    }
}

public enum FullScreenCover: Identifiable, Hashable, Sendable {
    case authentication
    case onboarding

    public var id: String {
        switch self {
        case .authentication: return "authentication"
        case .onboarding: return "onboarding"
        }
    }
}

// MARK: - 2. Enterprise Router Engine

@Observable
@MainActor
public final class AppRouter {
    public var path: NavigationPath
    public var presentedSheet: ModalSheet?
    public var presentedCover: FullScreenCover?

    private let restorationKey = "SavedNavigationPathState"

    public init() {
        self.path = NavigationPath()
    }

    // MARK: - Stack Operations
    
    public func push(_ route: AppRoute) {
        logger.debug("Pushing route: \(String(describing: route))")
        path.append(route)
    }

    public func pop() {
        guard !path.isEmpty else { return }
        logger.debug("Popping top route")
        path.removeLast()
    }

    public func popToRoot() {
        logger.debug("Popping to root view")
        path.removeLast(path.count)
    }

    // MARK: - Modal Operations

    public func present(sheet: ModalSheet) {
        logger.debug("Presenting sheet: \(sheet.id)")
        self.presentedSheet = sheet
    }

    public func dismissSheet() {
        self.presentedSheet = nil
    }

    public func present(cover: FullScreenCover) {
        logger.debug("Presenting fullScreenCover: \(cover.id)")
        self.presentedCover = cover
    }

    public func dismissCover() {
        self.presentedCover = nil
    }

    // MARK: - Deep Link Resolution

    public func handleDeepLink(url: URL) -> Bool {
        logger.info("Processing Deep Link: \(url.absoluteString)")
        guard url.scheme == "enterpriseapp" else { return false }

        // Example URL: enterpriseapp://product/detail?id=E621E1F8-C36C-495A-93FC-0C247A3E6E5F
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: true),
              let host = components.host else {
            return false
        }

        switch host {
        case "product":
            if components.path == "/detail",
               let queryItem = components.queryItems?.first(where: { $0.name == "id" }),
               let value = queryItem.value,
               let uuid = UUID(uuidString: value) {
                // Bersihkan stack terlebih dahulu jika diperlukan
                popToRoot()
                push(.productDetail(productID: uuid))
                return true
            }
        case "checkout":
            if let cartID = components.queryItems?.first(where: { $0.name == "cartId" })?.value {
                push(.checkout(cartID: cartID))
                return true
            }
        default:
            logger.warning("Unrecognized host for routing: \(host)")
            return false
        }
        return false
    }

    // MARK: - State Restoration

    public func savePathState() {
        guard let codablePath = path.codable else {
            logger.error("Path elements are not serializable.")
            return
        }
        do {
            let data = try JSONEncoder().encode(codablePath)
            UserDefaults.standard.set(data, forKey: restorationKey)
            logger.info("Navigation path state successfully persisted.")
        } catch {
            logger.error("Failed to serialize path: \(error.localizedDescription)")
        }
    }

    public func restorePathState() {
        guard let data = UserDefaults.standard.data(forKey: restorationKey) else { return }
        do {
            let representation = try JSONDecoder().decode(NavigationPath.CodableRepresentation.self, from: data)
            self.path = NavigationPath(representation)
            logger.info("Navigation path state successfully restored.")
        } catch {
            logger.error("Failed to restore navigation state: \(error.localizedDescription)")
        }
    }
}

// MARK: - 3. Destination Resolver Factory

public struct RouteDestinationViewFactory {
    @ViewBuilder
    public static func makeDestination(for route: AppRoute) -> some View {
        switch route {
        case .productList(let category):
            ProductListView(category: category)
        case .productDetail(let productID):
            ProductDetailView(productID: productID)
        case .checkout(let cartID):
            CheckoutView(cartID: cartID)
        case .orderStatus(let orderID, let isSuccess):
            OrderStatusView(orderID: orderID, isSuccess: isSuccess)
        }
    }
}

// MARK: - 4. Presentation Views

public struct EnterpriseRootContainerView: View {
    @State private var router = AppRouter()

    public init() {}

    public var body: some View {
        NavigationStack(path: $router.path) {
            MainDashboardView()
                .navigationDestination(for: AppRoute.self) { route in
                    RouteDestinationViewFactory.makeDestination(for: route)
                }
        }
        .environment(router)
        .sheet(item: $router.presentedSheet) { sheet in
            switch sheet {
            case .userProfile:
                NavigationStack {
                    UserProfileSheetView()
                }
            case .filters(let category):
                FilterView(activeCategory: category)
            }
        }
        .fullScreenCover(item: $router.presentedCover) { cover in
            switch cover {
            case .authentication:
                AuthenticationView()
            case .onboarding:
                Text("Enterprise Onboarding Flow")
            }
        }
        .onOpenURL { url in
            _ = router.handleDeepLink(url: url)
        }
    }
}

// MARK: - 5. Feature Views Implementation

public struct MainDashboardView: View {
    @Environment(AppRouter.self) private var router

    public var body: some View {
        List {
            Section(header: Text("Kategori Produk")) {
                Button("Lihat Elektronik") {
                    router.push(.productList(category: "Elektronik"))
                }
                Button("Lihat Fashion") {
                    router.push(.productList(category: "Fashion"))
                }
            }

            Section(header: Text("Quick Actions")) {
                Button("Buka Profil (Sheet)") {
                    router.present(sheet: .userProfile)
                }
                Button("Paksa Autentikasi (FullScreen)") {
                    router.present(cover: .authentication)
                }
                Button("Simpan Status Navigasi") {
                    router.savePathState()
                }
                Button("Pulihkan Status Navigasi") {
                    router.restorePathState()
                }
            }
        }
        .navigationTitle("Dashboard")
    }
}

public struct ProductListView: View {
    let category: String
    @Environment(AppRouter.self) private var router

    public var body: some View {
        VStack(spacing: 20) {
            Text("Daftar Item Kategori: \(category)")
                .font(.headline)

            Button("Pilih Produk Acak") {
                let randomUUID = UUID()
                router.push(.productDetail(productID: randomUUID))
            }
            .buttonStyle(.borderedProminent)
        }
        .navigationTitle(category)
    }
}

public struct ProductDetailView: View {
    let productID: UUID
    @Environment(AppRouter.self) private var router

    public var body: some View {
        VStack(spacing: 16) {
            Text("Detail Produk")
                .font(.title2)
            Text("ID: \(productID.uuidString)")
                .font(.caption)
                .foregroundStyle(.secondary)

            Button("Beli Sekarang") {
                router.push(.checkout(cartID: "CART-\(productID.uuidString.prefix(4))"))
            }
            .buttonStyle(.borderedProminent)
        }
        .navigationTitle("Detail")
    }
}

public struct CheckoutView: View {
    let cartID: String
    @Environment(AppRouter.self) private var router

    public var body: some View {
        VStack(spacing: 16) {
            Text("Proses Checkout")
            Text("Cart: \(cartID)")

            Button("Bayar Transaksi") {
                router.push(.orderStatus(orderID: "ORD-9912", isSuccess: true))
            }
            .buttonStyle(.borderedProminent)
            .tint(.green)
        }
        .navigationTitle("Checkout")
    }
}

public struct OrderStatusView: View {
    let orderID: String
    let isSuccess: Bool
    @Environment(AppRouter.self) private var router

    public var body: some View {
        VStack(spacing: 20) {
            Image(systemName: isSuccess ? "checkmark.circle.fill" : "xmark.circle.fill")
                .resizable()
                .frame(width: 80, height: 80)
                .foregroundStyle(isSuccess ? .green : .red)

            Text("Pesanan \(orderID) Selesai!")
                .font(.title3)

            Button("Kembali ke Beranda") {
                router.popToRoot()
            }
            .buttonStyle(.bordered)
        }
        .navigationTitle("Status")
        .navigationBarBackButtonHidden(true)
    }
}

public struct UserProfileSheetView: View {
    @Environment(AppRouter.self) private var router

    public var body: some View {
        List {
            Text("Nama: John Doe")
            Text("Email: enterprise@company.com")
            Button("Tutup") {
                router.dismissSheet()
            }
            .foregroundStyle(.red)
        }
        .navigationTitle("Profil")
    }
}

public struct FilterView: View {
    let activeCategory: String
    public var body: some View {
        Text("Filter untuk: \(activeCategory)")
    }
}

public struct AuthenticationView: View {
    @Environment(AppRouter.self) private var router

    public var body: some View {
        VStack(spacing: 24) {
            Text("Sesi Berakhir. Silakan Login.")
                .font(.headline)
            Button("Masuk") {
                router.dismissCover()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: SuperApp Finansial dengan Global Interceptor & Dynamic Deep Linking
**Deskripsi Masalah:**
Sebuah SuperApp perbankan digital memiliki puluhan modul dinamis (*Payments*, *Investments*, *Credit Card*, *Customer Support*). Aplikasi sering menerima *push notification* berisi deep link saat aplikasi berada di latar belakang atau ketika pengguna belum terautentikasi (keadaan locked/biometric challenge).

Jika deep link dieksekusi secara instan:
1. Layar rahasia (*Account Statement*) terbuka sebelum FaceID selesai divalidasi.
2. Jika pengguna belum memiliki izin transaksi finansial, aplikasi mengalami *crash* atau *blank screen* karena data dependensi belum dimuat.

**Solusi Arsitektural:**
Membangun `NavigationInterceptor` yang mengantrekan (*queue*) rute yang diminta pengguna, memblokir transisi UI hingga status autentikasi berhasil diselesaikan, kemudian meneruskan eksekusi navigasi secara deterministik (*deferred routing execution*).

```swift
import Foundation
import Observation

public enum NavIntent: Sendable {
    case route(AppRoute)
    case sheet(ModalSheet)
}

@Observable
@MainActor
public final class SecureEnterpriseCoordinator {
    public var path = NavigationPath()
    public var isBiometricAuthenticated: Bool = false
    
    // Antrean rute yang ditunda
    private var pendingIntent: NavIntent?
    
    public func handleIncomingIntent(_ intent: NavIntent) {
        guard isBiometricAuthenticated else {
            // Simpan intent ke memory buffer, tampilkan proteksi login
            self.pendingIntent = intent
            triggerBiometricAuth()
            return
        }
        executeIntent(intent)
    }

    private func triggerBiometricAuth() {
        // Simulasi validasi async LocalAuthentication
        Task {
            let success = await performBiometricEvaluation()
            if success {
                self.isBiometricAuthenticated = true
                if let deferred = self.pendingIntent {
                    self.executeIntent(deferred)
                    self.pendingIntent = nil
                }
            }
        }
    }

    private func executeIntent(_ intent: NavIntent) {
        switch intent {
        case .route(let route):
            path.append(route)
        case .sheet:
            // logic modal handling
            break
        }
    }

    private func performBiometricEvaluation() async -> Bool {
        // Asynchronous call simulating LocalAuthentication context evaluation
        try? await Task.sleep(nanoseconds: 500_000_000)
        return true
    }
}
```

---

### 9. Trade-offs

| Parameter | Strongly Typed Stack (`[Route]`) | Type-Erased Stack (`NavigationPath`) | Custom UIKit Coordinator Wrapper |
| :--- | :--- | :--- | :--- |
| **Type Safety** | Sangat Tinggi (Terjamin saat kompilasi) | Sedang (Dynamic runtime resolution) | Rendah (Membutuhkan runtime casting) |
| **Heterogeneous Routes** | Sulit (Membutuhkan umbrella enum raksasa) | Sempurna (Mendukung tipe apa pun yang Hashable) | Sangat Fleksibel (Setiap ViewController bebas) |
| **State Persistence** | Menggunakan standar Codable native | Menggunakan `NavigationPath.CodableRepresentation` | Manual UIViewController restoration |
| **Compile Time Impact** | Cepat, dependensi minim | Minimal | Lambat karena overhead integrasi UIKit |
| **Performance Overhead** | Terendah (Zero dynamic lookup cost) | Sangat rendah (Pencarian O(1) berbasis type-hash) | Overhead pembuatan wrapper instance UIViewController |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Fatal: Multiple Identical `navigationDestination`
**Gejala:** Animasi ganda saat transisi, tampilan berkedip (*flickering*), atau SwiftUI mengeluarkan log warning runtime:
`"A navigationDestination for type X is already declared at an upper level..."`
**Penyebab:** Mendeklarasikan `.navigationDestination(for: Route.self)` di dalam sub-view yang dirender secara berulang (misalnya di dalam `ForEach` atau di dalam sel list).
**Solusi:** Daftarkan modifier `.navigationDestination` **hanya sekali** pada tingkat paling atas di dalam `NavigationStack`.

```swift
// SALAH (Diletakkan di dalam perulangan / baris)
List(items) { item in
    NavigationLink(value: item) {
        Text(item.name)
    }
    .navigationDestination(for: Item.self) { item in // FATAL: Didaftarkan N-kali!
        DetailView(item: item)
    }
}

// BENAR (Diletakkan di level container list)
NavigationStack(path: $router.path) {
    List(items) { item in
        NavigationLink(value: item) {
            Text(item.name)
        }
    }
    .navigationDestination(for: Item.self) { item in // Optimal: Tervalidasi sekali
        DetailView(item: item)
    }
}
```

#### 10.2. Kesalahan: Retain Cycle & Leaking ViewModel pada Pop Operation
**Gejala:** Konsumsi memori terus meningkat ketika pengguna melakukan push dan pop view berkali-kali. `deinit` pada ViewModel tidak pernah terpanggil.
**Penyebab:** Closure pada `navigationDestination` menangkap referensi instance ViewModel atau Router secara kuat (*strong capture*) di dalam asynchronous task atau observer.
**Solusi:** Gunakan `@StateObject` (atau `@State` jika menggunakan framework `@Observable` modern) di dalam destination view itu sendiri, bukan mengoper instance yang sudah dibuat dari parent view.

#### 10.3. Desinkronisasi Mutasi Path Bersamaan (Concurrent Mutations)
**Gejala:** Crash `Fatal error: Index out of range` atau `Simultaneous accesses to 0x...`.
**Penyebab:** Memanggil `path.append()` dari background task atau thread yang berbeda secara bersamaan tanpa sinkronisasi aktor.
**Solusi:** Tandai semua Router class dengan `@MainActor`, memastikan seluruh mutasi `NavigationPath` dieksekusi di Serial Main RunLoop.

---

### 11. Best Practices (Production Checklist)

- [ ] **Satu Sumber Kebenaran (Single Source of Truth):** Jangan pernah mencampur navigasi berbasis binding bool individual (`isActive`) dengan `NavigationPath` modern.
- [ ] **Lazy Evaluation:** Pastikan inisialisasi state view tujuan navigasi berada di dalam siklus hidup view itu sendiri, bukan dievaluasi saat mendaftarkan routing graph.
- [ ] **Hashable Conformance yang Benar:** Jangan menggunakan properti acak atau non-deterministik untuk protokol `Hashable`. Jika dua struct memiliki data identitas yang sama, `hash(into:)` harus identik.
- [ ] **Isolation MainActor:** Berikan anotasi `@MainActor` pada kelas Router navigasi untuk menghindari *thread collision*.
- [ ] **Pemisahan Modul Navigasi:** Jangan meletakkan seluruh rute aplikasi dalam satu file enum raksasa jika bekerja dalam tim skala besar. Pisahkan rute per modul fitur dan gunakan `NavigationPath` untuk perutean lintas modul (*cross-module navigation*).
- [ ] **Pembersihan Modal Bersamaan:** Selalu pastikan modal (*sheet* / *fullScreenCover*) telah ditutup (*dismissed*) sebelum melakukan navigasi stack yang drastis (seperti `popToRoot`) untuk menghindari *animation race-condition*.

---

### 12. Hands-on Practice

Buatlah workspace modular di direktori `hands-on/m02/` dengan langkah-langkah berikut:

#### Langkah 1: Inisialisasi Struktur File
```bash
mkdir -p hands-on/m02/EnterpriseRouter
cd hands-on/m02/EnterpriseRouter
touch NavigationContracts.swift AppRouter.swift ContentView.swift
```

#### Langkah 2: Definisikan Kontrak Routing
Buka `NavigationContracts.swift` dan implementasikan domain routing:
```swift
// hands-on/m02/EnterpriseRouter/NavigationContracts.swift
import Foundation

public enum OrderDestination: Hashable, Codable, Sendable {
    case tracking(orderNumber: String)
    case invoice(invoiceID: String)
}

public enum ProfileDestination: Hashable, Codable, Sendable {
    case editAddress
    case securitySettings
}
```

#### Langkah 3: Implementasikan Multi-Segment Router
Buka `AppRouter.swift`:
```swift
// hands-on/m02/EnterpriseRouter/AppRouter.swift
import SwiftUI
import Observation

@Observable
@MainActor
public final class ProductionRouter {
    public var path = NavigationPath()

    public init() {}

    public func navigate(to destination: any Hashable & Codable & Sendable) {
        path.append(destination)
    }

    public func popBack() {
        guard !path.isEmpty else { return }
        path.removeLast()
    }

    public func reset() {
        path = NavigationPath()
    }
}
```

#### Langkah 4: Hubungkan ke View Layer
Buka `ContentView.swift` dan gunakan modifier `.navigationDestination` modular:
```swift
// hands-on/m02/EnterpriseRouter/ContentView.swift
import SwiftUI

public struct RootAppView: View {
    @State private var router = ProductionRouter()

    public var body: some View {
        NavigationStack(path: $router.path) {
            VStack(spacing: 20) {
                Button("Buka Pelacakan Order #554") {
                    router.navigate(to: OrderDestination.tracking(orderNumber: "ORD-554"))
                }
                Button("Buka Pengaturan Keamanan") {
                    router.navigate(to: ProfileDestination.securitySettings)
                }
            }
            .navigationTitle("Main Hub")
            // Resolver Modul Order
            .navigationDestination(for: OrderDestination.self) { destination in
                switch destination {
                case .tracking(let num):
                    VStack {
                        Text("Melacak Order: \(num)")
                        Button("Lihat Invoice") {
                            router.navigate(to: OrderDestination.invoice(invoiceID: "INV-\(num)"))
                        }
                    }
                case .invoice(let invId):
                    VStack {
                        Text("Invoice ID: \(invId)")
                        Button("Selesai (Kembali ke Beranda)") {
                            router.reset()
                        }
                    }
                }
            }
            // Resolver Modul Profile
            .navigationDestination(for: ProfileDestination.self) { destination in
                switch destination {
                case .editAddress:
                    Text("Form Edit Alamat")
                case .securitySettings:
                    VStack {
                        Text("Pengaturan Keamanan Akun")
                        Button("Edit Alamat") {
                            router.navigate(to: ProfileDestination.editAddress)
                        }
                    }
                }
            }
        }
        .environment(router)
    }
}
```

---

### 13. Exercise

#### Level Easy
Buat tombol "Pop 2 Pages" yang memeriksa apakah kedalaman tumpukan navigasi (`path.count`) saat ini minimal 2 langkah. Jika benar, lakukan pemotongan tepat 2 elemen secara aman tanpa memicu crash `index out of range`.

#### Level Medium
Tambahkan mekanisme *breadcrumb tracking*. Setiap kali elemen baru dimasukkan ke dalam `NavigationPath`, simpan nama representatif rute ke dalam sebuah array `[String]`. Tampilkan status breadcrumb ini secara real-time pada view bar status custom di bagian bawah layar induk.

#### Level Hard
Rancang arsitektur navigasi adaptif: Pada perangkat **iPhone**, gunakan `NavigationStack` tunggal. Namun pada **iPad** dalam orientasi landscape, secara otomatis petakan rute ke dalam model `NavigationSplitView` (Sidebar -> Content List -> Detail Area) tanpa mengubah struktur enum routing yang digunakan oleh *ViewModel*.

---

### 14. Challenge

**Studi Kasus: Multi-Module Dependency Inversion Routing Engine**
Dalam arsitektur modular berskala besar, Modul Fitur A (`FeatureA`) tidak boleh mengimpor Modul Fitur B (`FeatureB`) secara langsung untuk mencegah dependensi siklis (*circular dependency*). 

**Tantangan Anda:**
1. Rancang modul `CoreNavigation` yang mendefinisikan protokol perutean abstrak (*abstract routing protocols*).
2. Buat mekanisme *Dynamic Feature Registration*: Setiap modul fitur mendaftarkan *Destination Factory Provider* miliknya sendiri ke Router saat modul tersebut dimuat saat runtime (*module bootstrap phase*).
3. Bangun skenario di mana pengguna berada di `FeatureA.CartView`, lalu menekan tombol "Bayar", yang memerintahkan Core Router untuk mengarahkan pengguna ke `FeatureB.PaymentGatewayView` tanpa `FeatureA` perlu mengimpor file `PaymentGatewayView.swift`.
4. Seluruh aliran harus mendukung penanganan *back-navigation* dan pembatalan (*cancellation callback*) menggunakan Swift Concurrency async/await.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Apa perbedaan mendasar antara `NavigationStack` dan `NavigationView` yang telah usang?
2. Mengapa sebuah tipe data yang digunakan pada `.navigationDestination(for:)` wajib mengimplementasikan protokol `Hashable`?
3. Apa perbedaan fungsional antara koleksi homogen `[MyRoute]` dan `NavigationPath` dalam deklarasi path `NavigationStack`?
4. Bagaimana cara instan melakukan navigasi kembali ke tampilan awal (*root view*) saat menggunakan `NavigationPath`?
5. Mengapa anotasi `@MainActor` wajib dilekatkan pada kelas implementasi Router navigasi?

#### 5 Pertanyaan Intermediate
6. Mengapa meletakkan deklarasi modifier `.navigationDestination` di dalam perulangan `ForEach` dianggap sebagai *anti-pattern* dan memicu masalah performa?
7. Bagaimana mekanisme `NavigationPath.CodableRepresentation` bekerja dalam proses serialisasi dan deserialisasi tumpukan navigasi heterogen?
8. Apa yang terjadi pada siklus hidup memori (*deallocation*) sebuah View ketika view tersebut dihapus dari `NavigationPath` via `removeLast()`?
9. Bagaimana cara menangani navigasi Sheet bertingkat (*nested modal presentation*) agar tidak terjadi konflik animasi dengan `NavigationStack` utama?
10. Dalam skenario deep linking, apa bahaya langsung melakukan mutasi pada path navigasi sebelum antarmuka pengguna selesai diinisialisasi (*view hierarchy rendered*)?

#### 3 Skenario Kasus Produksi
11. **Skenario 1:** Sebuah aplikasi e-commerce menerima push notification saat sedang menampilkan sheet form pembayaran. Tim developer melaporkan bahwa saat deep link dieksekusi, sheet tidak tertutup dan tampilan tujuan push notification rusak (*glitched*). Apa akar masalahnya dan bagaimana arsitektur router seharusnya menangani konflik ini?
12. **Skenario 2:** Aplikasi analitik memiliki tumpukan navigasi hingga kedalaman 10 layar. Saat pengguna menekan "Pop to Root", aplikasi mengalami pembekuan UI (*hiccup/frame drop*) selama 300ms. Apa yang menyebabkan lag tersebut dan bagaimana cara mengoptimalkannya?
13. **Skenario 3:** Setelah melakukan refactor ke `NavigationStack`, tim QA menemukan bahwa ViewModel pada layar target tetap hidup di memori (*memory leak*) meskipun pengguna sudah menekan tombol *Back*. Tunjukkan bagaimana cara melakukan audit kode dan menemukan akar masalah retain cycle tersebut!

---

### 16. Summary

- **Pemisahan Data dan Antarmuka:** Mesin navigasi modern SwiftUI (`NavigationStack`) bekerja secara murni berbasis data (*data-driven*). Antarmuka pengguna adalah cerminan langsung dari array atau `NavigationPath` yang mendasarinya.
- **Lazy Instantiation:** Berbeda dengan `NavigationLink` warisan yang bersifat eager, `navigationDestination` mengevaluasi view secara dinamis hanya saat dibutuhkan, meningkatkan performa konsumsi memori dan kecepatan rendering awal secara drastis.
- **Enterprise Decoupling:** Penggunaan pola arsitektur *Coordinator/Router* yang dikombinasikan dengan framework `Observation` memisahkan secara bersih tanggung jawab bisnis, validasi autentikasi, penanganan deep link, dan deklarasi pohon tampilan.
- **Serialisasi Deterministik:** Pemanfaatan `CodableRepresentation` pada `NavigationPath` memungkinkan aplikasi menyimpan dan memulihkan kondisi navigasi pengguna secara sempurna (*state restoration*), menciptakan pengalaman multitasking yang mulus bagi pengguna platform Apple.