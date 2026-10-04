# BAB 04 MODULE 01: Navigation Engine & Structural Routing

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 02-Programming-Languages
*   **Teknologi:** SwiftUI (iOS 16.0+, macOS 13.0+, Swift 5.9+)
*   **Topik:** Navigation Engine & Structural Routing
*   **Tingkat Kesulitan:** Advanced / Enterprise Architecture
*   **Prasyarat:** Pemahaman mendalam tentang SwiftUI View Lifecycle, Swift Type System (`Hashable`, `Codable`, `Identifiable`), Dynamic Property wrappers (`@State`, `@Binding`, `@EnvironmentObject`, `@Observable`), serta pemisahan concern berbasis Clean Architecture / MVVM.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda ditargetkan untuk mampu:

1.  **Membongkar Mekanisme Stack SwiftUI:** Memahami cara kerja internal `NavigationStack`, `NavigationPath`, dan `UINavigationController` bridge di bawah runtime Apple.
2.  **Mengimplementasikan Type-Safe Decoupled Routing:** Membangun arsitektur Coordinator/Router yang memisahkan View dari deklarasi tujuan navigasi secara konkret menggunakan enumerasi `Hashable`.
3.  **Mengelola Navigasi Terprogram (Programmatic Navigation):** Melakukan operasi *push*, *pop*, *pop-to-root*, dan manipulasi tumpukan hierarki navigasi berbasis modifikasi data array murni.
4.  **Menangani Multi-Column Structural Layouts:** Menguasai implementasi `NavigationSplitView` untuk adaptasi form-factor iPadOS dan macOS, lengkap dengan mekanisme fallback otomatis pada Compact Size Classes (iOS iPhone).
5.  **Membangun Serialisasi & Deep Linking Engine:** Mengonversi URL Skema/Universal Link menjadi representasi `NavigationPath` state yang dapat diserialisasi (JSON Encoding) untuk State Restoration.
6.  **Mengeliminasi Memory Leaks & Retain Cycles:** Mencegah kebocoran memori akibat retensi closure atau state retain cycle di dalam navigation stack tree.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Deklaratif vs Imperatif

Pada era imperatif (`UIKit`), navigasi dikelola melalui mutasi langsung terhadap hierarki tampilan:
```swift
// Mental Model UIKit: Manipulasi Langsung Tampilan
navigationController?.pushViewController(detailVC, animated: true)
```

Pada era SwiftUI modern (dimulai dari iOS 16), navigasi diperlakukan sebagai **Fungsi dari State Tumpukan Data**:

$$\text{Navigation Hierarchy} = f(\text{Navigation Stack State})$$

```swift
// Mental Model SwiftUI Modern: Manipulasi Data Sederhana
navigationPath.append(Route.detail(id: 42))
```

```
+-------------------------------------------------------------------------+
|                              MENTAL MODEL                               |
|                                                                         |
|      [ DATA STACK ]                        [ RENDERED UI STACK ]        |
|  +--------------------+                     +--------------------+      |
|  | Route.profile(12)  |   === Resolver ==>  |    ProfileView     |      |
|  +--------------------+                     +--------------------+      |
|  | Route.order(992)   |   === Resolver ==>  |    OrderDetailView |      |
|  +--------------------+                     +--------------------+      |
|  | Route.dashboard    |   === Resolver ==>  |    DashboardView   |      |
|  +--------------------+                     +--------------------+      |
|                                                                         |
|   Mutasi Array Data (Append/Drop)  ----->  Transisi Animasi Otomatis    |
+-------------------------------------------------------------------------+
```

Jangan pernah berpikir "Saya ingin membuka halaman X". Berpikirlah: "Saya menambahkan item $X$ ke dalam tumpukan array data, dan SwiftUI akan mengevaluasi transformator tipe data tersebut menjadi UI View yang sesuai."

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur decoupled router enterprise yang memisahkan trigger UI, state management router, dan resolusi UI view:

```
+-----------------------------------------------------------------------------------+
|                            ENTERPRISE ROUTING ARCHITECTURE                        |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
                              +-----------------------+
                              |   Incoming Triggers   |
                              |  (Tap, DeepLink, Push)|
                              +-----------------------+
                                          |
                                          | (Pass Route Enum)
                                          v
                              +-----------------------+
                              |    AppRouter / State  |
                              |   (ObservableObject / |
                              |      @Observable)     |
                              +-----------------------+
                                          |
                 +------------------------+------------------------+
                 | Holds: path: [Route] / NavigationPath           |
                 v                                                 v
  +-----------------------------+                   +-----------------------------+
  |    NavigationStack(path:)   |                   |    NavigationSplitView      |
  +-----------------------------+                   +-----------------------------+
                 |                                                 |
                 v                                                 v
  +-------------------------------------------------------------------------------+
  |                     .navigationDestination(for: Route.self)                   |
  +-------------------------------------------------------------------------------+
                                          |
                                          | (Resolves Route)
                                          v
                              +-----------------------+
                              |    View Factory /     |
                              |      Destination      |
                              +-----------------------+
                                          |
             +----------------------------+----------------------------+
             |                            |                            |
             v                            v                            v
    +------------------+         +------------------+         +------------------+
    |   HomeView()     |         |  DetailView(id)  |         | SettingsView()   |
    +------------------+         +------------------+         +------------------+
```

### Alur Mutasi State Menuju Presentasi UI

```
[User Interaksi]
       |
       v
Router.navigate(to: .detail(id: "A1"))
       |
       v
path.append(.detail(id: "A1"))   <--- State Berubah
       |
       v
SwiftUI Runtime mengevaluasi perbedaan diffing tumpukan
       |
       v
SwiftUI mencocokkan tipe `.detail` pada `.navigationDestination(for: Route.self)`
       |
       v
Instansiasi DetailView(id: "A1") dan push view dengan transisi native
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. `NavigationStack` vs Legacy `NavigationView`

`NavigationView` (diperkenalkan iOS 13, didepresiasi iOS 16) dibungkus langsung di atas `UINavigationController` dan `UISplitViewController` dengan abstraksi bocor (*leaky abstraction*). Masalah struktural utamanya mencakup:
*   Inisialisasi eager: `NavigationLink(destination: DetailView())` langsung menginstansiasi instance struct view target sekalipun link belum ditekan.
*   Kehilangan kontrol pop-to-root yang bersih tanpa wrapper UIKit invasif.
*   Perilaku tidak terduga pada iPad (`DoubleColumnStyle` default yang merusak ekspektasi layout ponsel).

`NavigationStack` merestrukturisasi model ini:
*   Menerapkan *lazy view creation*: Destinasi hanya diinstansiasi ketika item terdaftar di dalam path stack data.
*   Pemisahan link dan target: `NavigationLink(value: Hashable)` memancarkan nilai, bukan View instance.
*   Target terpusat: Resolver `.navigationDestination(for: Type.self)` menerima data dan memetakan ke View secara terisolasi.

### 2. Representasi Internal: Homogeneous vs Type-Erased Stacks

SwiftUI menyediakan dua model tumpukan:
1.  **Homogeneous Collection (`[Route]`):** Menampung data bertipe sama. Keunggulannya: *compile-time type safety* murni, performa lebih tinggi tanpa runtime wrapping, dan kemudahan serialisasi serial berbasis protokol `Codable`.
2.  **Type-Erased Collection (`NavigationPath`):** Menampung berbagai tipe data arbitrer yang konforman terhadap `Hashable`. Menggunakan representasi *type-erased box* secara internal. Mendukung serialisasi berbasis `NavigationPath.CodableRepresentation`.

```
        Homogeneous Array [AppRoute]                 NavigationPath (Type-Erased)
       +----------------------------+             +-------------------------------+
Top -> | .settings                  |             | AnyHashable(UserProfile(...))|
       +----------------------------+             +-------------------------------+
       | .detail(id: "X-01")        |             | AnyHashable("simple_string")  |
       +----------------------------+             +-------------------------------+
Base-> | .dashboard                 |             | AnyHashable(42)               |
       +----------------------------+             +-------------------------------+
         Memory: Contiguous Array                   Memory: Existential Container Box
```

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Tipe Safety Melalui Protokol `Hashable`

Agar sebuah instance dapat diteruskan ke `NavigationLink(value:)` atau dimasukkan ke dalam `NavigationPath`, instance tersebut **wajib** mengimplementasikan protokol `Hashable`.

SwiftUI menggunakan `hash(into:)` dan operator kesetaraan `==` (`Equatable`) untuk:
1.  Mendeteksi apakah destinasi view yang sama sedang dipresentasikan.
2.  Menentukan identitas tampilan dalam Navigation Graph untuk mengelola restrukturisasi render tree.
3.  Memastikan komputasi diffing state navigation path efisien ($O(1)$ untuk lookup dan $O(N)$ untuk stack-depth reconciliation).

### NavigationSplitView: Master-Detail Architecture

Pada form factor besar (iPadOS, macOS, visionOS), pola multi-kolom diwujudkan oleh `NavigationSplitView`. Komponen ini mengontrol layout dua atau tiga kolom:
*   `Sidebar`: Hirarki navigasi level tertinggi (contoh: Folders, Menu).
*   `Content`: Level daftar item (contoh: Email list).
*   `Detail`: Detail view dari item yang dipilih (contoh: Email body).

Pada layar iPhone (Compact width), `NavigationSplitView` secara adaptif mereduksi dirinya menjadi tumpukan linier tunggal (*collapsing mechanism*), memperlakukan seleksi kolom sebagai operasi push standar.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL (STEP-BY-STEP)

Contoh berikut menunjukkan implementasi perutean dasar bertipe aman tanpa mencemari View dengan instansiasi manual.

```swift
import SwiftUI

// LANGKAH 1: Definisikan Route sebagai Hashable Enum
enum CatalogRoute: Hashable {
    case category(name: String)
    case productDetail(productId: UUID)
    case reviews(productId: UUID, ratingFilter: Int?)
}

// LANGKAH 2: Bangun View Utama dengan State NavigationPath
struct CatalogNavigationView: View {
    @State private var path = [CatalogRoute]()

    var body: some View {
        NavigationStack(path: $path) {
            VStack(spacing: 20) {
                Text("Katalog Utama")
                    .font(.title)

                // Push via value-based link
                NavigationLink(value: CatalogRoute.category(name: "Elektronik")) {
                    Text("Buka Kategori Elektronik")
                        .padding()
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }

                // Push via programmatic state modification
                Button("Buka Produk Spesial Langsung") {
                    let specialId = UUID()
                    path.append(.productDetail(productId: specialId))
                }
                .buttonStyle(.borderedProminent)
            }
            // LANGKAH 3: Tangani registrasi destinasi secara terisolasi
            .navigationDestination(for: CatalogRoute.self) { route in
                switch route {
                case .category(let name):
                    CategoryListView(categoryName: name, path: $path)
                case .productDetail(let productId):
                    ProductDetailView(productId: productId, path: $path)
                case .reviews(let productId, let filter):
                    ReviewListView(productId: productId, filter: filter)
                }
            }
            .navigationTitle("Store Front")
        }
    }
}

// Sub-view dengan kemampuan programmatic back
struct CategoryListView: View {
    let categoryName: String
    @Binding var path: [CatalogRoute]

    var body: some View {
        VStack(spacing: 16) {
            Text("Daftar Produk: \(categoryName)")
                .font(.headline)

            Button("Pilih Mac Studio") {
                path.append(.productDetail(productId: UUID()))
            }
            
            Button("Pop Kembali") {
                _ = path.popLast()
            }
        }
        .navigationTitle(categoryName)
    }
}

struct ProductDetailView: View {
    let productId: UUID
    @Binding var path: [CatalogRoute]

    var body: some View {
        VStack(spacing: 16) {
            Text("Detail Produk: \(productId.uuidString.prefix(8))")
            
            Button("Lihat Ulasan") {
                path.append(.reviews(productId: productId, ratingFilter: 5))
            }

            Button("Pop to Root") {
                path.removeAll() // Membersihkan stack secara instan
            }
            .foregroundColor(.red)
        }
        .navigationTitle("Detail")
    }
}

struct ReviewListView: View {
    let productId: UUID
    let filter: Int?

    var body: some View {
        VStack {
            Text("Ulasan untuk Produk \(productId.uuidString.prefix(8))")
            if let filter = filter {
                Text("Filter Rating: Bintang \(filter)")
            }
        }
        .navigationTitle("Ulasan")
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis dari potongan kode Langkah 1 hingga 3 di atas:

1.  `enum CatalogRoute: Hashable`:
    *   Penggunaan `enum` Swift dengan *associated values* memastikan *type exhaustion* (setiap skenario tujuan terdefinisi secara terbatas).
    *   Kompiler menghasilkan sintesis implementasi protokol `Hashable` otomatis selama semua associated value (`String`, `UUID`, `Int?`) juga bertipe `Hashable`.

2.  `@State private var path = [CatalogRoute]()`:
    *   Mengalokasikan tumpukan navigasi dalam memori lokal view hierarchy. Menggunakan tipe array konkrit `[CatalogRoute]` alih-alih `NavigationPath` memberikan optimasi alokasi contigous memory array dan kejelasan tipe statis.

3.  `NavigationStack(path: $path)`:
    *   Menerima `Binding` ke state collection. Operator binding `$` memungkinkan `NavigationStack` menulis kembali ke state lokal (misalnya memanggil `popLast()` ketika tombol default back button bawaan sistem di-tap).

4.  `NavigationLink(value: CatalogRoute.category(name: "Elektronik"))`:
    *   Berbeda dari inisialisasi legacy `NavigationLink(destination:label:)`, overload ini **tidak** memuat view target di muka. Ia hanya menyuntikkan value payload ke event engine SwiftUI saat interaksi sentuhan divalidasi.

5.  `.navigationDestination(for: CatalogRoute.self) { route in ... }`:
    *   Modifier ini mendaftarkan *Dynamic Lookup Interceptor*. Setiap kali elemen bertipe `CatalogRoute` didorong ke dalam stack, closure ini dievaluasi.
    *   Switch case memetakan payload murni ke view instance baru. Proses alokasi memori view terjadi strictly **on-demand**.

6.  `path.removeAll()`:
    *   Melakukan mutasi array murni. Menghapus semua elemen dari array secara langsung menginstruksikan `NavigationStack` untuk memicu transisi pop visual kembali ke root view dalam 1 frame runtime loop.

---

## SEKSI 09 — STUDI KASUS NYATA (REAL-WORLD PRODUCTION SCENARIO)

### Masalah: Aplikasi Super-App FinTech Multi-Module
Sebuah aplikasi perbankan modern memiliki tiga kebutuhan kritis:
1.  **Deep Link Handling yang Kompleks:** Pengguna membuka tautan dari notifikasi: `bankapp://transfers/confirmation?txId=98124&source=promo`. Aplikasi harus mengarahkan user dari Root -> Dashboard -> Transfer Flow -> Transaction Confirmation tanpa tabrakan view hierarchy.
2.  **State Preservation / Restoration:** Jika OS mematikan background process karena *memory pressure*, ketika pengguna kembali, tumpukan navigasi harus dipulihkan secara persis dari disk cache JSON.
3.  **Global Decoupling:** Modul transaksi tidak boleh mengimpor modul profil pengguna secara langsung; perutean antar domain harus diorkestrasikan oleh Core Router.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah implementasi sistem navigasi tingkat produksi yang dapat diserialisasi (State Restoration), mendukung Deep Linking, dan decoupled menggunakan arsitektur Router modern (`@Observable` dari framework Swift Observation).

```swift
import SwiftUI
import OSLog

// MARK: - 1. DOMAIN ROUTES (SERIALIZABLE)

enum AppRoute: Codable, Hashable {
    case dashboard
    case accountDetail(accountId: String)
    case transferInput(sourceAccountId: String)
    case transferConfirmation(transactionId: String, amount: Double)
    case systemSettings
}

// MARK: - 2. CENTRALIZED NAVIGATION ENGINE / ROUTER

@Observable
final class NavigationRouter {
    private let logger = Logger(subsystem: "com.fintech.app", category: "NavigationRouter")
    
    // Core data stack
    var path: [AppRoute] = [] {
        didSet {
            logger.debug("Stack Mutated. Depth: \(self.path.count), Head: \(String(describing: self.path.last))")
        }
    }
    
    // Sheet presentation router
    var presentedSheet: AppSheet?
    
    enum AppSheet: Identifiable, Hashable {
        case biometricAuth
        case errorAlert(message: String)
        
        var id: String {
            switch self {
            case .biometricAuth: return "biometricAuth"
            case .errorAlert(let msg): return "error_\(msg)"
            }
        }
    }

    // MARK: Actions
    func navigate(to route: AppRoute) {
        path.append(route)
    }
    
    func pop() {
        guard !path.isEmpty else { return }
        path.removeLast()
    }
    
    func popToRoot() {
        path.removeAll()
    }
    
    // MARK: Deep Link Parsing Engine
    func handleDeepLink(url: URL) -> Bool {
        logger.info("Parsing Deep Link: \(url.absoluteString)")
        guard url.scheme == "bankapp" else { return false }
        
        // Format: bankapp://transfer/confirm?txId=TX9901&amount=500000
        guard let host = url.host else { return false }
        
        switch host {
        case "account":
            if let accountId = url.queryParameters?["id"] {
                popToRoot()
                navigate(to: .accountDetail(accountId: accountId))
                return true
            }
        case "transfer":
            if url.path == "/confirm",
               let txId = url.queryParameters?["txId"],
               let amountStr = url.queryParameters?["amount"],
               let amount = Double(amountStr) {
                popToRoot()
                navigate(to: .transferConfirmation(transactionId: txId, amount: amount))
                return true
            }
        default:
            break
        }
        return false
    }
    
    // MARK: State Persistence Engine
    func exportStateRepresentation() -> Data? {
        do {
            let encoder = JSONEncoder()
            return try encoder.encode(path)
        } catch {
            logger.error("Gagal serialisasi navigation stack: \(error.localizedDescription)")
            return nil
        }
    }
    
    func restoreState(from data: Data) {
        do {
            let decoder = JSONDecoder()
            let decodedPath = try decoder.decode([AppRoute].self, from: data)
            self.path = decodedPath
            logger.info("Stack state berhasil dipulihkan. Total node: \(decodedPath.count)")
        } catch {
            logger.error("Gagal memulihkan state dari data: \(error.localizedDescription)")
        }
    }
}

// Helper parsing URL query parameters
extension URL {
    var queryParameters: [String: String]? {
        guard let components = URLComponents(url: self, resolvingAgainstBaseURL: true),
              let queryItems = components.queryItems else { return nil }
        return queryItems.reduce(into: [String: String]()) { result, item in
            result[item.name] = item.value
        }
    }
}

// MARK: - 3. ROOT CONTAINER VIEW

struct ProductionRootView: View {
    @State private var router = NavigationRouter()
    @SceneStorage("navigation_state_cache") private var savedNavigationData: Data?

    var body: some View {
        NavigationStack(path: $router.path) {
            DashboardScreen()
                .navigationDestination(for: AppRoute.self) { route in
                    DestinationFactory.view(for: route)
                }
        }
        .environment(router)
        .sheet(item: $router.presentedSheet) { sheet in
            switch sheet {
            case .biometricAuth:
                Text("Autentikasi Biometrik Diperlukan")
                    .presentationDetents([.medium])
            case .errorAlert(let msg):
                Text("Error: \(msg)")
                    .presentationDetents([.fraction(0.3)])
            }
        }
        .onAppear {
            // Restore state saat launch
            if let savedNavigationData {
                router.restoreState(from: savedNavigationData)
            }
        }
        .onChange(of: router.path) { _, _ in
            // Save state saat path termutasi
            savedNavigationData = router.exportStateRepresentation()
        }
        .onOpenURL { url in
            _ = router.handleDeepLink(url: url)
        }
    }
}

// MARK: - 4. VIEW FACTORY (DECOUPLING INVERSION)

enum DestinationFactory {
    @ViewBuilder
    static func view(for route: AppRoute) -> some View {
        switch route {
        case .dashboard:
            DashboardScreen()
        case .accountDetail(let accountId):
            AccountDetailScreen(accountId: accountId)
        case .transferInput(let sourceId):
            TransferInputScreen(sourceAccountId: sourceId)
        case .transferConfirmation(let txId, let amount):
            TransferConfirmationScreen(transactionId: txId, amount: amount)
        case .systemSettings:
            SettingsScreen()
        }
    }
}

// MARK: - 5. SCREENS (ISOLATED COMPONENTS)

struct DashboardScreen: View {
    @Environment(NavigationRouter.self) private var router

    var body: some View {
        List {
            Section("Rekening Anda") {
                Button("Rekening Tabungan Utama") {
                    router.navigate(to: .accountDetail(accountId: "ACC-001928"))
                }
            }
            
            Section("Aksi Cepat") {
                Button("Transfer Dana") {
                    router.navigate(to: .transferInput(sourceAccountId: "ACC-001928"))
                }
            }
        }
        .navigationTitle("Dashboard FinTech")
        .toolbar {
            Button("Settings") {
                router.navigate(to: .systemSettings)
            }
        }
    }
}

struct AccountDetailScreen: View {
    let accountId: String
    @Environment(NavigationRouter.self) private var router

    var body: some View {
        VStack(spacing: 20) {
            Text("Detail Rekening: \(accountId)")
                .font(.headline)
            
            Button("Mulai Transfer dari Akun Ini") {
                router.navigate(to: .transferInput(sourceAccountId: accountId))
            }
        }
        .navigationTitle("Detail Akun")
    }
}

struct TransferInputScreen: View {
    let sourceAccountId: String
    @Environment(NavigationRouter.self) private var router

    var body: some View {
        VStack(spacing: 20) {
            Text("Transfer dari: \(sourceAccountId)")
            
            Button("Kirim Rp 500.000") {
                let generatedTxId = "TX-" + UUID().uuidString.prefix(6)
                router.navigate(to: .transferConfirmation(transactionId: String(generatedTxId), amount: 500_000))
            }
        }
        .navigationTitle("Pilih Nominal")
    }
}

struct TransferConfirmationScreen: View {
    let transactionId: String
    let amount: Double
    @Environment(NavigationRouter.self) private var router

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "checkmark.circle.fill")
                .foregroundColor(.green)
                .font(.system(size: 64))
            
            Text("Transaksi Berhasil!")
                .font(.title2)
            
            Text("ID Transaksi: \(transactionId)")
            Text("Nominal: Rp \(Int(amount))")
            
            Button("Kembali ke Dashboard Utama") {
                router.popToRoot()
            }
            .buttonStyle(.borderedProminent)
        }
        .navigationTitle("Konfirmasi")
        .navigationBarBackButtonHidden(true) // Cegah kembali ke flow input
    }
}

struct SettingsScreen: View {
    @Environment(NavigationRouter.self) private var router

    var body: some View {
        VStack {
            Text("Pengaturan Aplikasi")
            Button("Trigger Sheet Error") {
                router.presentedSheet = .errorAlert(message: "Koneksi Terputus")
            }
        }
        .navigationTitle("Settings")
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Parameter Arsitektur | Homogeneous Collection `[Route]` | Type-Erased `NavigationPath` | Legacy `NavigationView` + Push Link |
| :--- | :--- | :--- | :--- |
| **Type Safety** | **Sangat Tinggi**: Compile-time check penuh | **Sedang**: Runtime check berbasis AnyHashable | **Rendah**: Bergantung closure destination view instan |
| **Memori & Overhead** | **Paling Ringan**: Contiguous Array struct storage | **Sedang**: Menggunakan dynamic existential containers | **Boros**: Inisialisasi View target terjadi secara eager |
| **Serialisasi (State Restoration)** | **Sederhana**: Otomatis dengan `JSONEncoder` via `Codable` | **Kompleks**: Harus pakai `CodableRepresentation` | **Tidak Didukung**: Tidak ada representasi serializable native |
| **Heterogenitas Data** | **Terbatas**: Memerlukan satu Enum/Unified Hierarchy | **Fleksibel**: Menerima berbagai tipe data `Hashable` berbeda | N/A |
| **Modularitas Antar Tim** | Membutuhkan Shared Route Framework | Bebas mendaftarkan tipe payload independen | Memerlukan import langsung View target |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1.  **Siklus Animasi saat Manipulasi Ekstrem:** Memanggil `path.removeAll()` diikuti pemanggilan `path.append(...)` dalam siklus RunLoop yang sama dapat memicu visual glitch atau animasi stack terpotong. 
    *Mitigasi:* Jalankan mutasi bertingkat di dalam blok manipulasi transaksi terpisah atau tunggu frame rendering selesai jika membutuhkan transisi berurutan.
2.  **Duplikasi Identitas Hashable:** Jika Anda memasukkan model data yang sama dua kali ke dalam `NavigationPath`:
    ```swift
    path.append(userA)
    path.append(userA) // Duplikasi identitas
    ```
    SwiftUI runtime dapat membingungkan state tracking dari layer tampilan yang dipetakan, mengakibatkan popping tidak sengaja ketika terjadi update tampilan anak.
3.  **Sheet & Stack Presentation Collisions:** Menampilkan `.sheet` secara simultan saat `NavigationStack` sedang melakukan transisi push dapat memicu warning runtime UIKit: *"Attempt to present UIViewController while another transition is in progress"*. Selalu gunakan sinkronisasi status transisi.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Inisialisasi Eager di Destinasi
*Salah:*
```swift
NavigationLink("Ke Profil", destination: UserProfileView(userId: currentId))
// Masalah: UserProfileView langsung dialokasikan di memori saat list dirender, 
// memicu pemanggilan network/init yang tidak diinginkan!
```
*Benar:*
```swift
NavigationLink("Ke Profil", value: AppRoute.profile(userId: currentId))
// Alokasi memori UserProfileView ditunda hingga user menyentuh baris tersebut.
```

### 2. Multi-Declaration Collision pada `.navigationDestination`
*Salah:*
Mendaftarkan modifier `.navigationDestination(for: Route.self)` berkali-kali di level anak-anak yang berbeda di dalam satu `NavigationStack`. Ini menghasilkan *undefined behavior* di mana cabang registrasi paling dalam membajak atau mengabaikan event routing stack.
*Benar:*
Definisikan `.navigationDestination` tepat di level root view terluar dari `NavigationStack`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Pisahkan State Router dari UI View:** Terapkan router berbasis Class Observable (`@Observable` atau `ObservableObject`) sebagai *Single Source of Truth* untuk mutasi path. Jangan sebarkan variabel `@State private var path` di banyak view independen.
2.  **Gunakan Backing Enum Bertingkat:** Untuk aplikasi enterprise multi-domain, pecah route menjadi modular namespaces:
    ```swift
    enum FeatureARoute: Hashable { ... }
    enum FeatureBRoute: Hashable { ... }
    
    enum AppGlobalRoute: Hashable {
        case featureA(FeatureARoute)
        case featureB(FeatureBRoute)
    }
    ```
3.  **Gunakan Dependency Injection untuk Deep Link Handler:** Jangan biarkan logic pembedahan string URL hidup di dalam SwiftUI View. Parser harus berupa *pure unit-testable service*.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

*   **Identitas Struct Ringkas:** Pastikan data associated value pada enum route seringan mungkin (gunakan Primitive types, IDs, atau lightweight tokens). Hindari meletakkan model domain besar berisi lusinan sub-array ke dalam associated value route:
    ```swift
    // BURUK: Menghabiskan memory stack & hash computation time lambat
    case details(heavyModel: ComplexDatabaseRecordWithImages)

    // BAIK: Hanya lekatkan identifier
    case details(id: UUID)
    ```
*   **Profil Alokasi Memori dengan Instruments:** Saat menavigasi tumpukan mundur (*popping*), gunakan Xcode Instruments (*Allocations* & *Leaks*) untuk memvalidasi bahwa Struct dan View Hosting Controller yang ditinggalkan benar-benar dilepas dari memori (`deinit` terpanggil).

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Validasi Deep Link Input Payload:** State restoration dan deep link adalah celah eksploitasi perutean. Selalu validasi parameter yang diekstrak:
    ```swift
    guard let rawAmount = url.queryParameters?["amount"],
          let amount = Double(rawAmount),
          amount > 0, amount <= MAX_TRANSACTION_LIMIT else {
        self.presentedSheet = .errorAlert(message: "Parameter Transaksi Ilegal")
        return false
    }
    ```
2.  **Guarded Navigation (Route Interceptors):** Periksa status otentikasi sebelum memetakan ke view privat:
    ```swift
    .navigationDestination(for: AppRoute.self) { route in
        if route.requiresAuthentication && !AuthSession.shared.isLoggedIn {
            LoginScreen()
        } else {
            DestinationFactory.view(for: route)
        }
    }
    ```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Manfaatkan framework `OSLog` native untuk mentransmisikan jejak navigasi real-time yang dapat dibaca di macOS Console:

```swift
import OSLog

extension NavigationRouter {
    func logBreadcrumbs(action: String, target: AppRoute? = nil) {
        let logger = Logger(subsystem: "com.app.navigation", category: "Audit")
        let currentHead = path.map { String(describing: $0) }.joined(separator: " -> ")
        
        logger.info("[NAV ENGINE] Action: \(action) | Target: \(String(describing: target)) | Stack Hierarchy: [Root] -> \(currentHead, privacy: .public)")
    }
}
```

Tambahkan visualisasi status router pada build Development/Testing dengan overlay floating monitor untuk memantau perubahan ukuran tumpukan secara grafis saat debugging manual.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   `NavigationStack`: Kontainer visual root untuk navigasi linier hirarkis.
*   `NavigationSplitView`: Kontainer struktural adaptif (Multi-column iPad/macOS -> Single-stack iPhone).
*   `NavigationLink(value:)`: Menembakkan event routing tanpa menginstansiasi view secara eager.
*   `.navigationDestination(for: DestinationType.self)`: Factory block lazy-mapping dari data ke View.
*   `NavigationPath`: Tumpukan type-erased dynamic collection untuk routing heterogen.
*   `[T: Hashable]`: Array data homogen untuk tipe aman absolut dan efisiensi serialisasi.
*   `path.removeAll()`: Satu perintah imperatif berbasis data untuk mengeksekusi operasi pop-to-root seketika.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Apa perbedaan mendasar antara `NavigationLink(destination:label:)` (legacy) dan `NavigationLink(value:label:)` (modern)?**
   * A. Tidak ada perbedaan fungsional selain nama parameter.
   * B. Sintaks legacy langsung menginisialisasi view tujuan saat link ditampilkan, sedangkan sintaks modern mengevaluasi view secara lazily saat value diproses.
   * C. Sintaks legacy hanya bekerja pada macOS.
   * D. Sintaks modern membatasi kita hanya bisa mengirim data bertipe String.

2. **Protokol apa yang WAJIB diimplementasikan oleh sebuah tipe data agar dapat dikirim melalui `NavigationLink(value:)` atau `NavigationPath`?**
   * A. `Identifiable`
   * B. `Observable`
   * C. `Hashable`
   * D. `Sendable`

3. **Bagaimana cara paling bersih untuk melakukan aksi "Pop-to-Root" pada `NavigationStack(path: $path)` di mana `path` adalah `[AppRoute]`?**
   * A. Memanggil `path.popLast()` di dalam perulangan `while`.
   * B. Menghapus referensi `NavigationStack` dari view tree.
   * C. Menjalankan `path.removeAll()`.
   * D. Mengirim deep link kosong ke aplikasi.

4. **Kapan sebaiknya kita memilih `NavigationSplitView` dibandingkan `NavigationStack`?**
   * A. Ketika kita hanya membangun aplikasi khusus Apple Watch.
   * B. Ketika aplikasi ditujukan untuk perangkat multi-kolom (iPadOS/macOS) dengan tata letak Sidebar/Content/Detail yang tetap adaptif di iPhone.
   * C. Ketika kita memerlukan performa kompilasi 10x lebih cepat.
   * D. Ketika kita tidak ingin menggunakan protokol `Hashable`.

5. **Di mana modifier `.navigationDestination(for:destination:)` seharusnya dideklarasikan?**
   * A. Di dalam body setiap `NavigationLink`.
   * B. Di root container tampilan dalam `NavigationStack`.
   * C. Di luar struct `App`.
   * D. Di dalam AppDelegate saja.

---

### Soal Tingkat Menengah (Intermediate)

6. **Mengapa penggunaan array homogen `[AppRoute]` (enum) lebih disukai daripada `NavigationPath` untuk arsitektur State Restoration?**
   * A. `NavigationPath` sama sekali tidak bisa diserialisasi menjadi format apapun.
   * B. `[AppRoute]` dapat langsung mengimplementasikan protokol `Codable` bawaan Swift secara strictly-typed tanpa type-erasure container overhead.
   * C. `NavigationPath` memerlukan memori RAM minimal 2GB.
   * D. Array homogen mencegah aplikasi di-shutdown oleh operating system.

7. **Apa yang terjadi jika Anda mendaftarkan dua blok `.navigationDestination(for: Product.self)` yang identik dalam hirarki `NavigationStack` yang sama?**
   * A. Aplikasi akan langsung crash pada saat waktu kompilasi (compile-time failure).
   * B. Modifier terdekat/terdalam atau hierarki yang menangani event tersebut dapat menimbulkan konflik lookup tak terduga (*undefined routing behavior*).
   * C. SwiftUI otomatis menggabungkan kedua view menjadi tampilan split 50:50.
   * D. Kompiler mengabaikan keduanya dan mematikan fungsi link.

8. **Bagaimana cara menyembunyikan tombol back default sistem pada layer terdalam untuk mencegah pengguna membatalkan transaksi yang sudah diverifikasi?**
   * A. `.navigationBarHidden(true)`
   * B. `.navigationBarBackButtonHidden(true)`
   * C. `.backButtonDisplayMode(.minimal)`
   * D. `.ignoresSafeArea()`

9. **Jika sebuah associated value pada enum route didefinisikan sebagai struct model besar yang sering berubah (misal: `case detail(UserLargeProfile)`), apa dampaknya terhadap performa aplikasi?**
   * A. Performa render meningkat karena data sudah di-cache.
   * B. Mengurangi lifecycle overhead dari memory leak.
   * C. Menghabiskan resource saat komputasi hash kesetaraan nilai pada setiap frame diffing cycle, memperlambat transisi navigasi.
   * D. Tidak ada dampak performa apapun di iOS 17+.

10. **Bagaimana arsitektur Coordinator/Router menangani navigasi Deep Link URL skema secara elegan tanpa race condition tampilan?**
    * A. Menjalankan UIViewController present langsung melalui bridge UIWindow.
    * B. Mengonversi path URL menjadi node array Route yang valid, mereset path lama (popToRoot), dan menyuntikkan node baru secara berurutan pada state Router.
    * C. Menggunakan `NotificationCenter` untuk memicu refresh paksa setiap screen.
    * D. Meminta pengguna menutup aplikasi dan membukanya kembali via terminal.

---

### Kunci Jawaban & Pembahasan Singkat

1. **B** — Sintaks baru memanfaatkan model data-driven di mana view target dievaluasi lazily (hanya saat dibutuhkan).
2. **C** — Protokol `Hashable` diwajibkan untuk identitas unik node navigasi dan diffing state tree.
3. **C** — Karena stack adalah representasi State Array murni, mengosongkan array (`removeAll()`) otomatis mereset UI ke root.
4. **B** — `NavigationSplitView` menyediakan struktur adaptif multi-kolom yang otomatis menjadi push stack saat berada di iPhone (compact).
5. **B** — Mendeklarasikan destinasi di root level stack memastikan sentralisasi interceptor tujuan dan menghindari deklarasi redundant.
6. **B** — Enum homogen `[AppRoute]` yang konforman terhadap `Codable` dapat di-encode/decode secara langsung menggunakan `JSONEncoder` standard tanpa membongkar boxing metadata.
7. **B** — Multi-registrasi tipe yang sama dalam satu stack scope memicu ambiguitas runtime routing.
8. **B** — `.navigationBarBackButtonHidden(true)` adalah modifier eksplisit untuk menonaktifkan tombol back bawaan.
9. **C** — Struktur yang besar memperlambat kalkulasi fungsi hash dan kesetaraan nilai diffing pada runtime stack. Selalu teruskan ID/Token ringan.
10. **B** — Router memvalidasi URL, memetakannya ke data array, me-reset state lama, lalu memperbarui stack collection secara terprediksi.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Instruksi Proyek Praktikum: "Adaptive Multi-Column Media Library"

Bangun modul navigasi aplikasi Media Library dengan spesifikasi struktural berikut:

1.  **Arsitektur Target:**
    *   Gunakan `NavigationSplitView` tiga kolom untuk iPadOS/macOS:
        *   **Sidebar:** Kategori media (`Music`, `Podcasts`, `Audiobooks`).
        *   **Content List:** Daftar album / show dalam kategori terpilih.
        *   **Detail View:** Daftar track lagu lengkap beserta pemutar audio mockup.
    *   Pastikan struktur otomatis beradaptasi dengan mulus pada perangkat iPhone (Single Stack Push Navigation).
2.  **Manajemen State:**
    *   Gunakan class `@Observable NavigationManager` yang independen dari view.
    *   Terapkan deep linking dengan skema: `medialib://play?category=music&albumId=101&trackId=5`.
    *   Pastikan aplikasi dapat dipulihkan ke state pemutaran terakhir jika proses aplikasi terhenti menggunakan `@SceneStorage` atau cache JSON disk.
3.  **Kriteria Penilaian Keberhasilan:**
    *   Zero console warnings terkait inisialisasi eager navigation link.
    *   Kemampuan untuk melakukan "Pop to Root" dari detail track terdalam kembali ke awal sidebar kategori dalam satu interaksi tombol.
    *   Tidak ada memory leak view controller saat berpindah-pindah album secara berulang kali (verifikasi via Instrument Debug Memory Graph).