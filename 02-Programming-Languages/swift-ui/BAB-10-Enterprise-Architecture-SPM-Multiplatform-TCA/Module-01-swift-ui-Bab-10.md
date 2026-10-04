# Bab 10 Module 01: Enterprise Architecture: SPM, Multiplatform, & TCA

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `SWIFTUI-ENT-1001`
* **Kategori**: `02-Programming-Languages`
* **Kurikulum**: `swift-ui`
* **Tingkat Kemahiran**: Advanced / Enterprise Staff Engineer
* **Prasyarat**:
  * Penguasaan mendalam Swift 6 (Strict Concurrency, Structured Concurrency, Actors, Protocols).
  * Pemahaman arsitektur reaktif SwiftUI (`@Observable`, `@Binding`, View Lifecycle).
  * Pengalaman menggunakan Swift Package Manager (SPM) untuk manajemen pustaka pihak ketiga.
  * Konsep dasar Unidirectional Data Flow (UDF) dan Functional Programming.
* **Target Audiens**: Lead iOS/macOS Engineers, Mobile Architects, Senior Software Engineers yang merancang aplikasi skala multi-tim (monorepo/modularized) dan multiplatform.
* **Estimasi Waktu Belajar**: 12–16 Jam (Teori, Analisis Kode, Arsitektur Monorepo, Hands-on Lab).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Mendesain Arsitektur Modular Skala Enterprise**: Menerapkan pola *Micro-Features Architecture* menggunakan SPM lokal murni untuk memotong waktu kompilasi (*build-time*) hingga 60% dan mencegah *cyclic dependencies*.
2. **Menguasai The Composable Architecture (TCA v1.x+)**: Mengimplementasikan Reducer Protocol, `@ObservableState`, Scoping, Action Tree, Effects, dan Structured Concurrency secara deterministik dan *thread-safe*.
3. **Mengisolasi Dependencies & Side Effects**: Memanfaatkan `@Dependency` client pattern TCA untuk mendukung pengujian unit murni (*pure unit tests*) berkecepatan tinggi tanpa *mocking runtime overhead*.
4. **Membangun Aplikasi Multiplatform Native**: Mengabstraksikan domain logic antar-platform (iOS, iPadOS, macOS) menggunakan satu codebase bersama, sambil mempertahankan ergonomi native tiap sistem operasi.
5. **Mengintegrasikan Swift 6 Concurrency & Strict Concurrency Checking**: Mengeliminasi seluruh peringatan *data race* pada batas modularisasi dengan kepatuhan penuh terhadap protokol `Sendable`.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam proyek skala enterprise dengan puluhan kontributor, pendekatan arsitektur tradisional seperti *Massive-View-Controller* (MVC) atau *Model-View-ViewModel* (MVVM) yang tidak terstandardisasi sering kali runtuh akibat tiga faktor:
1. **Shared Mutable State**: State yang dapat dimutasi dari sembarang titik (View, Callback, async task) menyebabkan *race condition* visual dan *inconsistent business state*.
2. **Monolithic Build Targets**: Menaruh seluruh kode dalam satu target aplikasi Xcode menghasilkan waktu kompilasi eksponensial dan membatasi kerja paralel tim.
3. **Tight Coupling dengan Platform API**: Mengikat business rules langsung ke UIKit/AppKit membuat porting antar-platform menjadi proses penulisan ulang (*rewriting*) yang mahal.

### Mental Model 1: Micro-Features via Swift Package Manager
Alih-alih memperlakukan project Xcode sebagai satu kontainer besar, bayangkan arsitektur modular SPM sebagai **Directed Acyclic Graph (DAG)**. Setiap fitur bisnis dipecah secara horizontal dan vertikal:
* **Horizontal**: Fitur `Payment`, `Authentication`, `AccountOverview`.
* **Vertikal**: Pemisahan tegas antara `Interface` (kontrak/protokol/model data), `Implementation` (reducer, UI, private helpers), dan `Testing/Mocks`.

### Mental Model 2: Unidirectional State Machine (TCA)
TCA memperlakukan aplikasi sebagai mesin status (*state machine*) deterministik. Status aplikasi bersifat *read-only* bagi View. View hanya dapat memancarkan aksi (*Action*). Sebuah fungsi murni bernama *Reducer* menerima status saat ini beserta aksi yang terjadi, lalu menghasilkan status baru dan rangkaian efek samping (*Effect*) asinkron.

```
+-------------+         Action          +-------------+
|             | ----------------------> |             |
|    View     |                         |   Reducer   | (Fungsi Murni)
|  (SwiftUI)  | <---------------------- |             |
+-------------+      ObservableState    +-------------+
                                               |
                                               | Emits Effect
                                               v
                                        +-------------+
                                        | Environment |
                                        |/Dependency  | (Async Tasks, API, DB)
                                        +-------------+
```

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Struktur Modul Enterprise (SPM Directed Acyclic Graph)

Pemisahan antarmuka publik dan implementasi internal (*Interface-Implementation pattern*) mengisolasi perubahan internal dari *re-indexing* dan *re-compilation* modul konsumen:

```
[ App Executable (iOS / macOS) ]
               |
               v
      [ RootFeatureImpl ]
        /            \
       v              v
[ AuthFeatureImpl ]  [ DashboardFeatureImpl ]
       |                      |
       v                      v
[ AuthFeatureInterface ] [ DashboardFeatureInterface ]
       \                      /
        v                    v
         [ CoreNetworkClient ]
                   |
                   v
         [ SharedModels / DTO ]
```

### 2. Siklus Hidup Aliran Data TCA

```
User Interaksi (Tap Tombol Login)
       |
       v
View mengirimkan Store.send(.loginButtonTapped)
       |
       v
+-------------------------------------------------------------------+
| AuthFeature.body (Reducer)                                        |
| 1. Memodifikasi State: state.isLoading = true                     |
| 2. Mengembalikan Effect: .run { send in                           |
|      let response = try await authClient.login(creds)            |
|      await send(.loginResponse(response))                        |
|    }                                                              |
+-------------------------------------------------------------------+
       |                                              |
       | Update State langsung                        | Eksekusi Task Asinkron
       v                                              v
View mendeteksi `@ObservableState`             Background Thread (Sendable)
ProgressView dirender                          Eksekusi HTTP Client
                                                      |
                                                      v
                                        Store.send(.loginResponse(result))
                                                      |
                                                      v
                                        Reducer menangani `.loginResponse`
                                        state.isLoading = false
                                        state.currentUser = result.user
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. `@ObservableState` Macro & Observation Framework
Mulai dari TCA 1.7+, TCA mengintegrasikan kerangka kerja `Observation` bawaan Swift 5.9+. Tidak seperti `ViewStore` terdahulu yang bergantung pada `Combine` dan memicu evaluasi view secara agresif, `@ObservableState` menggunakan pelacakan akses properti granular pada level register compiler:

* Saat View mengakses `store.user.name`, SwiftUI hanya mendaftarkan ketergantungan pada *field* `name`.
* Jika `store.user.email` berubah, View tersebut **tidak akan** menjalankan ulang `body`.

### 2. Reducer Engine & Concurrency Safety
TCA Reducer didefinisikan melalui protokol:

```swift
public protocol Reducer<State, Action> {
    associatedtype State
    associatedtype Action
    
    @ReducerBuilder<State, Action>
    var body: Self.Body { get }
}
```

Mekanisme internal `Reduce` mengisolasi mutasi state ke dalam parameter `inout State`. Hal ini menjamin bahwa mutasi hanya terjadi secara sekuensial di dalam antrean store, menghindari kebutuhan penguncian manual (*locks/mutexes*).

### 3. Swift Package Manifest: Granular Target Design
Penggunaan *multi-library target* dalam satu `Package.swift` memungkinkan kompilasi paralel maksimum pada core CPU yang tersedia di mesin pengembangan CI/CD.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Dynamic vs Static Framework Linking di SPM
Secara bawaan, target SPM dikompilasi sebagai pustaka statis (*static libraries*). Dalam enterprise scale dengan puluhan modul fitur:
* **Static Linking**: Mempercepat startup aplikasi (*pre-main time*), namun jika modul `SharedModels` ditautkan secara statis ke dalam modul dinamik ganda (misalnya Target Utama + Notification Service Extension), duplikasi biner dan runtime symbol collision dapat terjadi.
* **Solusi**: Biarkan SPM menentukan tipe linking secara otomatis (`nil`), kecuali pada modul dasar utilitas tinggi yang dibungkus sebagai `type: .dynamic` jika dibagikan lintas target bundel aplikasi independen.

### 2. Abstraksi Multiplatform: Shared Core, Adaptive Shell
Arsitektur multiplatform modern tidak memaksakan UI seragam antara iOS dan macOS. Pendekatan yang benar adalah:
* **100% Shared**: Domain Model, Network DTO, Persistence, TCA Reducers, Dependency Clients.
* **Shared Adaptive UI**: Komponen dasar (*Design System Tokens*, Tombol, Form).
* **Platform Dedicated Shell**: 
  * iOS: `NavigationStack`, `sheet`, `TabBar`.
  * macOS: `NavigationSplitView`, `WindowGroup`, `MenuBarExtra`, Command Menu shortcuts.

### 3. Swift 6 Concurrency & Boundaries Isolation
Seluruh `Action` dan `State` dalam TCA harus mengadopsi protokol `Sendable`. Ini menjamin payload aksi dapat berpindah secara aman antar-utas eksekusi (*structured concurrency boundaries*) tanpa menyisakan referensi data race ke memori heap.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL (Step-by-step)

Di bawah ini adalah implementasi target SPM mandiri yang memuat fitur autentikasi dengan client dependency independen.

### Langkah 1: Client Dependency Definition (Contract & Live Implementation)

```swift
// Packages/AuthFeature/Sources/AuthFeature/AuthClient.swift
import Foundation
import Dependencies

public struct User: Equatable, Sendable, Codable, Identifiable {
    public let id: UUID
    public let username: String
    public let token: String
    
    public init(id: UUID, username: String, token: String) {
        self.id = id
        self.username = username
        self.token = token
    }
}

public struct AuthClient: Sendable {
    public var login: @Sendable (_ username: String) async throws -> User
}

extension AuthClient: DependencyKey {
    public static let liveValue = AuthClient(
        login: { username in
            // Simulasi latensi jaringan
            try await Task.sleep(for: .seconds(1))
            guard !username.isEmpty else {
                throw AuthError.invalidCredentials
            }
            return User(id: UUID(), username: username, token: "jwt_token_\(UUID().uuidString)")
        }
    )
    
    public static let testValue = AuthClient(
        login: { username in
            User(id: UUID(uuidString: "00000000-0000-0000-0000-000000000000")!, username: username, token: "mock_token")
        }
    )
}

public enum AuthError: Error, Equatable, Sendable {
    case invalidCredentials
}

public extension DependencyValues {
    var authClient: AuthClient {
        get { self[AuthClient.self] }
        set { self[AuthClient.self] = newValue }
    }
}
```

### Langkah 2: Reducer Implementation

```swift
// Packages/AuthFeature/Sources/AuthFeature/AuthFeature.swift
import Foundation
import ComposableArchitecture

@Reducer
public struct AuthFeature: Sendable {
    @ObservableState
    public struct State: Equatable, Sendable {
        public var usernameText: String = ""
        public var isLoading: Bool = false
        public var authenticatedUser: User?
        public var errorMessage: String?
        
        public init() {}
    }
    
    public enum Action: Sendable, Equatable {
        case usernameChanged(String)
        case loginButtonTapped
        case loginResponse(Result<User, AuthError>)
        case logoutButtonTapped
    }
    
    @Dependency(\.authClient) var authClient
    
    public init() {}
    
    public var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case let .usernameChanged(newUsername):
                state.usernameText = newUsername
                state.errorMessage = nil
                return .none
                
            case .loginButtonTapped:
                guard !state.usernameText.trimmingCharacters(in: .whitespaces).isEmpty else {
                    state.errorMessage = "Username tidak boleh kosong"
                    return .none
                }
                state.isLoading = true
                state.errorMessage = nil
                let username = state.usernameText
                
                return .run { send in
                    do {
                        let user = try await self.authClient.login(username)
                        await send(.loginResponse(.success(user)))
                    } catch let error as AuthError {
                        await send(.loginResponse(.failure(error)))
                    } catch {
                        await send(.loginResponse(.failure(.invalidCredentials)))
                    }
                }
                
            case let .loginResponse(.success(user)):
                state.isLoading = false
                state.authenticatedUser = user
                return .none
                
            case let .loginResponse(.failure(error)):
                state.isLoading = false
                state.errorMessage = error == .invalidCredentials 
                    ? "Kredensial tidak valid" 
                    : "Terjadi kesalahan internal"
                return .none
                
            case .logoutButtonTapped:
                state.authenticatedUser = nil
                state.usernameText = ""
                return .none
            }
        }
    }
}
```

### Langkah 3: Multiplatform SwiftUI View

```swift
// Packages/AuthFeature/Sources/AuthFeature/AuthView.swift
import SwiftUI
import ComposableArchitecture

public struct AuthView: View {
    @Bindable var store: StoreOf<AuthFeature>
    
    public init(store: StoreOf<AuthFeature>) {
        self.store = store
    }
    
    public var body: some View {
        VStack(spacing: 20) {
            if let user = store.authenticatedUser {
                VStack(spacing: 12) {
                    Text("Selamat datang, \(user.username)!")
                        .font(.title2)
                        .bold()
                    
                    Button("Logout") {
                        store.send(.logoutButtonTapped)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.red)
                }
            } else {
                VStack(spacing: 16) {
                    TextField("Username", text: $store.usernameText.sending(\.usernameChanged))
                        .textFieldStyle(.roundedBorder)
                        .disabled(store.isLoading)
                        #if os(iOS)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        #endif
                    
                    if let error = store.errorMessage {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(.red)
                    }
                    
                    if store.isLoading {
                        ProgressView()
                    } else {
                        Button("Masuk") {
                            store.send(.loginButtonTapped)
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(store.usernameText.isEmpty)
                    }
                }
            }
        }
        .padding(32)
        #if os(macOS)
        .frame(minWidth: 400, minHeight: 300)
        #endif
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis AuthClient.swift
* **Baris 4–12**: Definisi struct `User` yang mematuhi `Sendable`. Ini adalah syarat mutlak Swift 6 agar data dapat dilempar melintasi batas thread asynchronous.
* **Baris 14–16**: Struct `AuthClient` menggunakan teknik *closure-based interface*. Pendekatan ini lebih unggul daripada protokol tradisional dalam arsitektur TCA karena memungkinkan *in-line mocking* instan tanpa deklarasi kelas tambahan.
* **Baris 18–35**: Implementasi `DependencyKey`. `liveValue` dipakai saat aplikasi berjalan di simulator/device. `testValue` dipakai otomatis saat pengujian berjalan via `TestStore`. Jika developer lupa menentukan mock saat test, TCA runtime akan melempar fatal assertion failure secara preventif.

### Analisis AuthFeature.swift
* **Baris 4**: Macro `@Reducer` menghasilkan boilerplate code secara otomatis: konformasi protocol, inisialisasi state, dan routing logic.
* **Baris 6**: Macro `@ObservableState` mengimplementasikan tracking observation native Swift 5.9+. Ini menggantikan pembungkusan `@BindingState` lama dan mengeliminasi ketergantungan pada runtime `Combine`.
* **Baris 24**: Property wrapper `@Dependency(\.authClient)` melakukan injeksi dependensi secara dinamis. Nilai dependensi terikat pada `TaskLocal` TCA, sehingga terisolasi secara aman di tingkat concurrent environment.
* **Baris 42**: `.run { send in ... }` adalah API concurrency TCA. Blok ini menangani *structured task cancellation* secara otomatis. Jika Action lain membatalkan reducer ini, task asynchronous di dalam `.run` akan dibatalkan (*cooperative cancellation*).

### Analisis AuthView.swift
* **Baris 5**: `@Bindable var store: StoreOf<AuthFeature>` memungkinkan integrasi binding dua arah langsung ke state reducer melalui ekstensi `.sending(...)`.
* **Baris 29**: `.sending(\.usernameChanged)` mengubah SwiftUI native binding projection langsung menjadi Action TCA tanpa boilerplate closure.
* **Baris 31–34 & 51–53**: Penggunaan macro kompilasi `#if os(iOS)` dan `#if os(macOS)`. Kode core domain tetap bersatu 100%, sementara modifikasi spesifik platform diterapkan secara deklaratif pada lapisan View.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Konteks Bisnis: FinTech Omnichannel Asset Management
Sebuah bank investasi meluncurkan aplikasi manajemen portofolio aset multiplatform untuk analis institusional (macOS) dan nasabah prioritas (iOS/iPadOS).

### Masalah Arsitektural Awal:
1. **Monolith Codebase**: Proyek awal memiliki target Xcode tunggal dengan 450.000 baris kode. Waktu kompilasi bersih (clean build) di CI server memakan waktu 28 menit.
2. **Duplikasi Logika Bisnis**: Tim macOS dan iOS membuat repositori terpisah, menyebabkan perhitungan kalkulasi profit/loss (PnL) sering kali mengalami desinkronisasi hasil matematis.
3. **Flaky UI Tests**: Pengujian E2E (End-to-End) menggunakan XCUITest membutuhkan waktu 2 jam dan sering gagal akibat latensi backend dan socket network yang tidak deterministik.

### Solusi Arsitektur yang Diterapkan:
1. Migrasi ke struktur **SPM Local Monorepo** dengan pemisahan library target berorientasi domain.
2. Standardisasi state flow menggunakan **The Composable Architecture (TCA)**.
3. Seluruh kalkulasi performa portofolio dan stream WebSocket diisolasi ke dalam modul Core Domain yang dibagikan murni ke macOS dan iOS.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah blueprint implementasi arsitektur SPM monorepo riil beserta implementasi modul streaming portofolio multiplatform.

### 1. Root `Package.swift` (Modular Workspace Setup)

```swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "EnterpriseBankingCore",
    platforms: [
        .iOS(.v17),
        .macOS(.v14)
    ],
    products: [
        // Features
        .library(name: "PortfolioFeature", targets: ["PortfolioFeature"]),
        
        // Clients & Domain
        .library(name: "PortfolioClient", targets: ["PortfolioClient"]),
        .library(name: "SharedModels", targets: ["SharedModels"]),
    ],
    dependencies: [
        .package(url: "https://github.com/pointfreeco/swift-composable-architecture", exact: "1.10.0"),
        .package(url: "https://github.com/pointfreeco/swift-dependencies", exact: "1.3.1")
    ],
    targets: [
        // MARK: - Core Domain Models
        .target(
            name: "SharedModels",
            dependencies: []
        ),
        
        // MARK: - Client Interfaces & Live Implementations
        .target(
            name: "PortfolioClient",
            dependencies: [
                "SharedModels",
                .product(name: "Dependencies", package: "swift-dependencies"),
                .product(name: "DependenciesMacros", package: "swift-dependencies")
            ]
        ),
        
        // MARK: - Feature Modules
        .target(
            name: "PortfolioFeature",
            dependencies: [
                "SharedModels",
                "PortfolioClient",
                .product(name: "ComposableArchitecture", package: "swift-composable-architecture")
            ]
        ),
        .testTarget(
            name: "PortfolioFeatureTests",
            dependencies: [
                "PortfolioFeature"
            ]
        )
    ]
)
```

### 2. Domain Model & Precision Calculations

```swift
// Sources/SharedModels/Asset.swift
import Foundation

public struct Asset: Equatable, Sendable, Codable, Identifiable {
    public let id: String
    public let ticker: String
    public let allocatedAmount: Decimal
    public let currentPrice: Decimal
    
    public init(id: String, ticker: String, allocatedAmount: Decimal, currentPrice: Decimal) {
        self.id = id
        self.ticker = ticker
        self.allocatedAmount = allocatedAmount
        self.currentPrice = currentPrice
    }
    
    public var marketValue: Decimal {
        allocatedAmount * currentPrice
    }
}
```

### 3. Asynchronous Streaming Client Dependency

```swift
// Sources/PortfolioClient/PortfolioClient.swift
import Foundation
import SharedModels
import Dependencies
import DependenciesMacros

@DependencyClient
public struct PortfolioClient: Sendable {
    public var subscribeToMarketData: @Sendable () async throws -> AsyncStream<[Asset]>
    public var executeOrder: @Sendable (_ assetId: String, _ amount: Decimal) async throws -> Bool
}

extension PortfolioClient: DependencyKey {
    public static let liveValue: PortfolioClient = {
        return PortfolioClient(
            subscribeToMarketData: {
                AsyncStream { continuation in
                    let task = Task {
                        var prices: [String: Decimal] = ["AAPL": 180.50, "TSLA": 240.20, "NVDA": 850.10]
                        while !Task.isCancelled {
                            try? await Task.sleep(for: .seconds(2))
                            // Fluktuasi harga acak simulatif
                            for key in prices.keys {
                                let delta = Decimal(Double.random(in: -2.0...2.0))
                                prices[key] = max(Decimal(1.0), prices[key]! + delta)
                            }
                            
                            let mockAssets = [
                                Asset(id: "1", ticker: "AAPL", allocatedAmount: 100, currentPrice: prices["AAPL"]!),
                                Asset(id: "2", ticker: "TSLA", allocatedAmount: 50, currentPrice: prices["TSLA"]!),
                                Asset(id: "3", ticker: "NVDA", allocatedAmount: 30, currentPrice: prices["NVDA"]!)
                            ]
                            continuation.yield(mockAssets)
                        }
                    }
                    continuation.onTermination = { _ in
                        task.cancel()
                    }
                }
            },
            executeOrder: { _, _ in
                try await Task.sleep(for: .milliseconds(500))
                return true
            }
        )
    }()
    
    public static let testValue = PortfolioClient()
}

public extension DependencyValues {
    var portfolioClient: PortfolioClient {
        get { self[PortfolioClient.self] }
        set { self[PortfolioClient.self] = newValue }
    }
}
```

### 4. Enterprise Feature Reducer with Streaming Cancellation

```swift
// Sources/PortfolioFeature/PortfolioFeature.swift
import Foundation
import ComposableArchitecture
import SharedModels
import PortfolioClient

@Reducer
public struct PortfolioFeature: Sendable {
    public init() {}
    
    @ObservableState
    public struct State: Equatable, Sendable {
        public var assets: [Asset] = []
        public var totalPortfolioValue: Decimal = 0.0
        public var isStreamingActive: Bool = false
        public var alertMessage: String?
        
        public init() {}
    }
    
    public enum Action: Sendable, Equatable {
        case onAppear
        case onDisappear
        case marketDataUpdated([Asset])
        case marketStreamFailed
        case dismissAlert
    }
    
    private enum CancelID { case stream }
    
    @Dependency(\.portfolioClient) var portfolioClient
    
    public var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case .onAppear:
                state.isStreamingActive = true
                return .run { send in
                    do {
                        let stream = try await self.portfolioClient.subscribeToMarketData()
                        for await updatedAssets in stream {
                            await send(.marketDataUpdated(updatedAssets))
                        }
                    } catch {
                        await send(.marketStreamFailed)
                    }
                }
                .cancellable(id: CancelID.stream)
                
            case .onDisappear:
                state.isStreamingActive = false
                return .cancel(id: CancelID.stream)
                
            case let .marketDataUpdated(assets):
                state.assets = assets
                state.totalPortfolioValue = assets.reduce(Decimal(0)) { $0 + $1.marketValue }
                return .none
                
            case .marketStreamFailed:
                state.isStreamingActive = false
                state.alertMessage = "Koneksi bursa terputus. Menghubungkan ulang..."
                return .none
                
            case .dismissAlert:
                state.alertMessage = nil
                return .none
            }
        }
    }
}
```

### 5. Multiplatform Master-Detail User Interface

```swift
// Sources/PortfolioFeature/PortfolioView.swift
import SwiftUI
import ComposableArchitecture
import SharedModels

public struct PortfolioView: View {
    @Bindable var store: StoreOf<PortfolioFeature>
    
    public init(store: StoreOf<PortfolioFeature>) {
        self.store = store
    }
    
    public var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Header Metrik Bersama
                VStack(alignment: .leading, spacing: 4) {
                    Text("Total Nilai Portofolio")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    
                    Text(store.totalPortfolioValue, format: .currency(code: "USD"))
                        .font(.system(size: 32, weight: .bold, design: .rounded))
                    
                    HStack {
                        Circle()
                            .fill(store.isStreamingActive ? Color.green : Color.red)
                            .frame(width: 8, height: 8)
                        Text(store.isStreamingActive ? "Live Ticker Connected" : "Disconnected")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(Color(.secondarySystemBackground))
                
                // Asset List / Table
                #if os(macOS)
                macOSTableLayout
                #else
                iOSListLayout
                #endif
            }
            .navigationTitle("Executive Wealth")
            .onAppear { store.send(.onAppear) }
            .onDisappear { store.send(.onDisappear) }
            .alert(
                "Pemberitahuan Sistem",
                isPresented: Binding(
                    get: { store.alertMessage != nil },
                    set: { if !$0 { store.send(.dismissAlert) } }
                )
            ) {
                Button("OK", role: .cancel) { store.send(.dismissAlert) }
            } message: {
                Text(store.alertMessage ?? "")
            }
        }
    }
    
    #if os(iOS)
    private var iOSListLayout: some View {
        List(store.assets) { asset in
            HStack {
                VStack(alignment: .leading) {
                    Text(asset.ticker)
                        .font(.headline)
                    Text("\(asset.allocatedAmount.formatted()) lembar")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                VStack(alignment: .trailing) {
                    Text(asset.marketValue, format: .currency(code: "USD"))
                        .font(.body.monospacedDigit())
                        .bold()
                    Text(asset.currentPrice, format: .currency(code: "USD"))
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.vertical, 4)
        }
        .listStyle(.insetGrouped)
    }
    #endif
    
    #if os(macOS)
    private var macOSTableLayout: some View {
        Table(store.assets) {
            TableColumn("Ticker", value: \.ticker)
                .width(min: 80, ideal: 100)
            
            TableColumn("Alokasi") { asset in
                Text(asset.allocatedAmount.formatted())
                    .monospacedDigit()
            }
            .width(min: 80, ideal: 100)
            
            TableColumn("Harga Pasar") { asset in
                Text(asset.currentPrice, format: .currency(code: "USD"))
                    .monospacedDigit()
            }
            .width(min: 100, ideal: 120)
            
            TableColumn("Total Valuasi") { asset in
                Text(asset.marketValue, format: .currency(code: "USD"))
                    .bold()
                    .monospacedDigit()
            }
            .width(min: 120, ideal: 150)
        }
        .frame(minWidth: 500, minHeight: 300)
    }
    #endif
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Arsitektur: TCA vs MVVM Standar vs VIPER

| Parameter Dimensi | The Composable Architecture (TCA) | Standard MVVM (SwiftUI Native) | VIPER |
| :--- | :--- | :--- | :--- |
| **State Predictability** | **Sangat Tinggi**: Single source of truth, mutasi state terpusat via reducer murni. | **Rendah - Sedang**: State tersebar di berbagai `@Published` / `@Observable` ViewModel. | **Tinggi**: Terstruktur, namun state dapat tercecer antara Presenter & Interactor. |
| **Testability** | **Superior**: Menggunakan `TestStore`, memverifikasi alur state, aksi, dan efek samping secara exhaustif tanpa mock class manual. | **Sedang**: Membutuhkan pembuatan manual mock protocols/classes untuk ViewModel dependencies. | **Tinggi**: Sangat modular, namun membutuhkan mocking interfaces dalam jumlah masif. |
| **Boilerplate Code** | **Tinggi**: Aksi harus didefinisikan secara eksplisit untuk setiap interaksi sistem. | **Sangat Rendah**: Cukup binding langsung nilai view model ke UI fields. | **Sangat Tinggi**: Membutuhkan 5 file representasi untuk satu antarmuka layar kecil. |
| **Learning Curve** | **Curam**: Memerlukan pemahaman fungsional programming, state machines, dan concurrency isolations. | **Rendah**: Pola standar industri Apple. Mudah dipahami oleh junior engineer. | **Tinggi**: Alur inter-modul routing kaku dan rumit diimplementasikan di SwiftUI. |
| **Build-Time Impact** | **Moderat**: Penggunaan macro canggih (`@Reducer`, `@ObservableState`) meningkatkan dependensi compiler waktu build awal. | **Minimal**: Tidak ada framework eksternal, linking langsung terhadap SDK Apple native. | **Rendah**: Lebih sedikit macro, namun banyak file parsing overhead. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. State Re-entrancy & Deadlocks pada Swift 6 Actors
Saat menggunakan TCA Effects dengan `@Dependency`, hindari mengeksekusi blocking calls (`DispatchQueue.sync` atau `semaphore.wait()`) di dalam `.run { send in }`. Hal ini dapat menyebabkan thread starvation di bawah Swift cooperative thread pool:

```swift
// PITFALL: Deadlock Risk!
return .run { send in
    let result = DispatchSemaphore(value: 0)
    // Jangan pernah memblokir thread cooperative executor!
}
```

### 2. Memory Leaks Melalui AsyncStream Tak Terbatas
Jika `AsyncStream` tidak mendefinisikan penanganan pemutusan terminasi (`continuation.onTermination`), stream tetap mengonsumsi buffer memori dan mempertahankan referensi closure sekalipun Reducer atau View telah di-deallocate:

```swift
// MITIGASI: Selalu tangani termination
continuation.onTermination = { @Sendable status in
    underlyingNetworkTask.cancel()
}
```

### 3. macOS Window Destruction vs iOS Background Suspension
Pada iOS, saat pengguna keluar dari aplikasi, proses dibekukan (*suspended*). Pada macOS, menutup jendela aplikasi (*close window*) secara default **tidak mematikan proses**. Efek TCA jangka panjang (seperti polling jaringan atau socket) akan terus berjalan di background macOS kecuali reducer mendengarkan event window lifecycle atau aksi eksplisit `onDisappear`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mutasi Langsung dari Async Effect Tanpa `send`
* **Salah**:
  ```swift
  case .buttonTapped:
      return .run { [state] send in
          // ERROR: State bersifat immutable di dalam Effect scope!
          // state.counter += 1 
      }
  ```
* **Benar**: Lakukan mutasi state hanya di dalam scope inti `Reduce`:
  ```swift
  case .buttonTapped:
      state.counter += 1
      return .none
  ```

### Kesalahan 2: Menggunakan Pustaka Dynamic Tanpa Kebutuhan Jelas
* **Penyebab**: Menentukan `type: .dynamic` di setiap produk target `Package.swift`.
* **Dampak**: Waktu *pre-main launch time* (dyld loading) meningkat drastis pada perangkat iOS nyata.
* **Solusi**: Kosongkan parameter `type:` pada konfigurasi library SPM agar compiler mengoptimalkan penautan secara statis (`static archive .a`), kecuali ada kebutuhan dynamic framework eksplisit.

### Kesalahan 3: Mengirim Objek Non-Sendable Melintasi Batas Action
* **Penyebab**: Memasukkan objek tipe referensi (`class`) yang tidak `Sendable` ke dalam `enum Action`.
* **Dampak**: Swift 6 Compiler akan melempar error keras: `Type 'Action' does not conform to the 'Sendable' protocol`.
* **Solusi**: Hanya kirimkan tipe data primitif, struct dengan conformance `Sendable`, atau Immutable DTO.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

### 1. Interface-Implementation Target Separation (Pola IOI)
Bagi sebuah domain menjadi 2 target terpisah dalam Package:
* `FeatureDomainInterface`: Berisi Model data, Enum Action, dan Client interface.
* `FeatureDomainImplementation`: Berisi Reducer logika dan SwiftUI Views.

*Keuntungan*: Target lain yang hanya membutuhkan navigasi ke target ini hanya perlu mengimpor `FeatureDomainInterface`. Modifikasi pada file UI internal tidak akan memaksa kompilasi ulang pada modul-modul tetangga.

### 2. Standar Penamaan Target SPM Berbasis Skala Industri
Gunakan format terstruktur yang jelas:
* `[Domain]Interface` (e.g., `PaymentInterface`)
* `[Domain]Implementation` (e.g., `PaymentImpl`)
* `[Domain]Testing` (e.g., `PaymentTestingMocks`)
* `[Domain]UI` (e.g., `PaymentDesignSystem`)

### 3. Exhaustive Testing via `TestStore`
TCA menyediakan instrumen pengujian unit mutakhir bernama `TestStore`. Aturannya: setiap mutasi state dan efek yang terjadi harus dideklarasikan secara eksplisit dalam assertion test. Jika state berubah tanpa diverifikasi oleh test assert, pengujian unit dipastikan **gagal**.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Fine-Grained Observation Tracking via `@ObservableState`
Dengan `@ObservableState`, jangan membungkus keseluruhan state besar ke dalam child view jika child view hanya memerlukan satu nilai string:

```swift
// KURANG OPTIMAL: ChildView akan me-render ulang jika APAPUN di Feature.State berubah
struct HeaderView: View {
    let store: StoreOf<Feature>
    var body: some View { Text(store.username) }
}

// OPTIMAL: Teruskan hanya nilai spesifik atau scope store secara granular
struct HeaderView: View {
    let username: String
    var body: some View { Text(username) }
}
```

### 2. Kompilasi Paralel SPM
Strukturkan dependency graph secara **lebar (wide)**, bukan **dalam/bertingkat (deep)**. SPM dapat mengompilasi modul yang berdiri sejajar secara bersamaan menggunakan seluruh core CPU yang tersedia.

```
Graph Buruk (Serial):
App -> FeatureA -> FeatureB -> FeatureC -> FeatureD -> Core

Graph Baik (Paralel):
App -> FeatureA \
App -> FeatureB  --> CoreInterface
App -> FeatureC /
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Sanitasi State Logging (Data Leak Prevention)
Secara bawaan, mencetak state saat logging atau crash dump dapat membocorkan kredensial atau informasi kartu kredit. Implementasikan protokol `CustomDebugStringConvertible` pada Struct State yang memuat data sensitif:

```swift
@ObservableState
public struct State: Equatable, Sendable, CustomDebugStringConvertible {
    public var pinCode: String = ""
    public var balance: Decimal = 0.0
    
    public var debugDescription: String {
        return "State(pinCode: \"***REDACTED***\", balance: \(balance))"
    }
}
```

### 2. Secure In-Memory Sensitive Fields
Untuk token autentikasi atau private cryptographic keys di dalam Client Dependency, hapus nilai byte-level array dari memori segera setelah tidak digunakan, atau enkapsulasi dalam Keychain Service wrapper daripada menyimpannya di plain static properties.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. TCA Native Reducer Logging
Gunakan modifier `._printChanges()` selama fase *debug build* untuk menginspeksi mutasi state dan aksi yang terpapar secara otomatis di Xcode Console tanpa perlu menyisipkan breakpoint manual:

```swift
#if DEBUG
portfolioReducer._printChanges()
#else
portfolioReducer
#endif
```

### 2. Telemetry Tracing dengan `OSLog`
Integrasikan `Logger` bawaan Apple ke dalam client dependencies untuk melacak durasi eksekusi network streaming:

```swift
import OSLog

private let logger = Logger(subsystem: "com.enterprise.banking", category: "PortfolioPerformance")

public func traceMarketEvent() {
    logger.notice("Inisiasi koneksi WebSocket market stream.")
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Modularity SPM Rule**: Desain modul horizontal berbasis fitur, bukan layer teknis. Hindari "God Module" seperti `Utilities` atau `Common`.
* **Reducer Invariant**: Reducer harus murni (*pure function*). Jangan pernah menaruh asynchronous I/O langsung di badan reducer; lakukan delegasi seluruhnya ke dalam `Effect.run`.
* **State Immutability**: Di dalam `Effect.run`, State tidak dapat dimutasi langsung. Kirim Action baru menggunakan `await send(.actionName)` untuk memperbarui State di antrean utama Reducer.
* **Observation**: Gunakan macro `@ObservableState` di tingkat State dan `@Bindable var store` di tingkat View untuk meminimalisir overhead rendering view.
* **Multiplatform Strategy**: Pisahkan business engine ke paket SPM platform-agnostic, terapkan `#if os(...)` hanya pada lapisan akhir presentasi (View).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Pilihan Ganda (Tingkat Dasar)

#### Q1. Apa tujuan mendasar dari penggunaan macro `@ObservableState` dibandingkan arsitektur ObservableObject/Combine tradisional di TCA?
* A. Menghapus kebutuhan protokol `Equatable` dari deklarasi State.
* B. Melacak pembacaan properti state secara spesifik di tingkat View, sehingga SwiftUI hanya me-render ulang view yang field-nya benar-benar berubah.
* C. Mengizinkan mutasi state secara paralel dari beberapa asynchronous task sekaligus.
* D. Mengotomatisasi penulisan unit test tanpa memanggil `TestStore`.

*Jawaban*: **B**
*Penjelasan*: `@ObservableState` mengintegrasikan Swift observation engine modern yang melacak dependensi data pada tingkat properti individu, mencegah re-evaluasi seluruh hierarchy view ketika properti tetangga di dalam struct yang sama mengalami mutasi.

---

#### Q2. Di dalam The Composable Architecture, di manakah tempat yang valid untuk menjalankan panggilan API berbasis jaringan (Network I/O)?
* A. Langsung di dalam closure `Reduce { state, action in ... }`.
* B. Di dalam inisialisasi `State`.
* C. Di dalam closure `Effect.run { send in ... }` yang dikembalikan oleh Reducer.
* D. Di dalam View SwiftUI pada modifier `.task`.

*Jawaban*: **C**
*Penjelasan*: Reducer harus menjadi fungsi murni (*pure function*) yang bebas dari side effect langsung. Seluruh side effect (seperti networking, I/O, persistence) wajib diisolasi di dalam `Effect`, yang dikembalikan oleh Reducer dan dieksekusi secara asinkron oleh runtime TCA.

---

#### Q3. Mengapa struktur dependensi horizontal (Micro-features) lebih disukai daripada struktur satu modul aplikasi raksasa (Monolith)?
* A. Karena library eksternal hanya bisa diimpor satu kali saja.
* B. Karena SPM tidak mendukung project dengan lebih dari 50 file sumber kode.
* C. Untuk memecah dependency graph, memungkinkan kompilasi paralel oleh CPU, dan membatasi invalidasi cache kompilasi.
* D. Agar seluruh state dapat dibaca secara global tanpa modifier `public`.

*Jawaban*: **C**
*Penjelasan*: Modularisasi horizontal mendistribusikan kode ke dalam node-node independen pada build DAG. Hal ini memaksimalkan penggunaan multi-core compilation SPM dan membatasi cakupan *recompilation* hanya pada modul yang mengalami perubahan.

---

#### Q4. Perintah TCA apa yang digunakan untuk menghentikan asynchronous Effect yang sedang berlangsung secara paksa saat sebuah Action baru diterima?
* A. `.cancel(id:)`
* B. `Task.exit()`
* C. `.abort()`
* D. `.stopEffect()`

*Jawaban*: **A**
*Penjelasan*: Efek yang diidentifikasi dengan identifier unik melalui `.cancellable(id:)` dapat dibatalkan secara deterministik kapan saja menggunakan `return .cancel(id:)`.

---

#### Q5. Apa keuntungan mendasar dari mendefinisikan dependency client menggunakan struct dengan properti closure alih-alih class inheritance?
* A. Class tidak diizinkan di dalam target Swift Package Manager.
* B. Memberikan fleksibilitas in-line mocking per kasus uji tanpa perlu membuat class turunan baru, serta aman terhadap isolasi concurrency (`Sendable`).
* C. Menghilangkan alokasi memori heap secara permanen dari aplikasi.
* D. Memaksa compiler menjalankan seluruh dependensi di MainActor.

*Jawaban*: **B**
*Penjelasan*: *Closure-based client interface* sangat modular, dapat di-*override* per-metode dalam pengujian spesifik, dan mematuhi aturan protokol `Sendable` modern tanpa membawa beban status referensi bersama (*shared mutable state*).

---

### Soal Pilihan Ganda (Tingkat Menengah)

#### Q6. Sebuah modul fitur `SettingsFeature` bergantung langsung pada implementasi konkret `DatabaseClientImpl`. Masalah arsitektural apa yang ditimbulkan dari desain ini?
* A. Swift compiler menolak impor target yang berakhiran `Impl`.
* B. Pelanggaran Dependency Inversion Principle; setiap perubahan kode internal database memaksa modul `SettingsFeature` untuk dikompilasi ulang secara penuh.
* C. Reducer `SettingsFeature` kehilangan kemampuan memanggil macro `@ObservableState`.
* D. Menghasilkan runtime crash saat aplikasi diunggah ke TestFlight.

*Jawaban*: **B**
*Penjelasan*: Dependensi langsung ke target implementasi konkret menciptakan *tight-coupling* dan merusak pemisahan dependensi. Modul fitur harus bergantung pada target antarmuka (`Client/Interface`), bukan target implementasi detail (`Impl`).

---

#### Q7. Pada Swift 6 dengan Strict Concurrency Checking diaktifkan, compiler melempar error: `Passing argument of non-sendable type 'Product' outside of actor-isolated context`. Bagaimana cara memperbaikinya secara benar dalam konteks TCA Action payload?
* A. Menandai struct `Product` dengan `@unchecked Sendable` tanpa memeriksa dependensi properti internalnya.
* B. Mengubah `Product` menjadi tipe data `Any`.
* C. Mengubah `Product` menjadi struct yang hanya memuat tipe data yang mematuhi protokol `Sendable`, lalu menandainya dengan `Sendable`.
* D. Membungkus objek `Product` di dalam `DispatchQueue.main.async`.

*Jawaban*: **C**
*Penjelasan*: Seluruh payload Action TCA melintasi batas thread async/await. Cara yang benar dan aman menurut standar Swift 6 adalah memastikan seluruh struktur pembentuk data mematuhi `Sendable` secara murni (*deep conformity*).

---

#### Q8. Apa yang terjadi jika sebuah pengujian menggunakan TCA `TestStore` mengubah status State, tetapi developer tidak menuliskan assertion mutasi state di closure `store.receive`?
* A. `TestStore` akan mengasumsikan mutasi tersebut benar dan lulus secara otomatis.
* B. Pengujian unit akan gagal (*assertion failure*); `TestStore` bersifat exhaustive dan menuntut verifikasi eksplisit atas setiap mutasi state.
* C. Xcode compiler menolak mengompilasi unit test.
* D. Aplikasi simulator crash di latar belakang.

*Jawaban*: **B**
*Penjelasan*: Prinsip *Exhaustive Testing* TCA mewajibkan developer memverifikasi secara tepat seluruh siklus hidup state dan efek. Mutasi yang tidak terkonfirmasi akan memicu kegagalan unit test secara eksplisit untuk mencegah *unintended side effects*.

---

#### Q9. Mengapa penggunaan `#if os(macOS)` lebih disarankan ditempatkan di lapisan akhir View daripada menaruhnya di dalam Reducer Feature Logic?
* A. Compiler Swift melarang sintaks `#if os(...)` di dalam file selain file View.
* B. Agar logic bisnis dan pemrosesan state mesin tetap 100% konsisten antar-platform, meminimalkan branching logika bisnis yang berisiko memunculkan bug platform-spesifik.
* C. Karena macOS tidak mendukung protokol Reducer TCA.
* D. Mengurangi konsumsi CPU sistem operasi target sebesar 50%.

*Jawaban*: **B**
*Penjelasan*: Prinsip inti arsitektur multiplatform TCA adalah *Shared Core Domain*. Bisnis logic harus independen dari platform runtime. Perbedaan UI visual dan kontrol input harus diadaptasi secara murni pada lapisan presentasi (SwiftUI Views).

---

#### Q10. Kapan Anda harus memisahkan sebuah modul besar menjadi dua modul SPM: `DomainInterface` dan `DomainImplementation`?
* A. Hanya jika modul tersebut memiliki lebih dari 10.000 file.
* B. Ketika target modul tersebut dikonsumsi oleh banyak fitur paralel lain, sehingga isolasi interface mencegah kompilasi ulang massal saat implementasi internal diubah.
* C. Ketika aplikasi harus di-deploy ke watchOS.
* D. SPM melarang pembuatan modul tunggal tanpa interface module terpisah.

*Jawaban*: **B**
*Penjelasan*: Pola Interface-Implementation (IOI) dirancang untuk memutus rantai invalidasi dependensi build. Modul konsumen hanya me-link ke Interface, sehingga perubahan kode pada body implementation tidak memicu kompilasi ulang pada modul-modul konsumen tersebut.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Praktikum: "Enterprise Multiplatform Vault Manager"

#### Tujuan:
Bangun arsitektur monorepo lokal menggunakan SPM yang memisahkan aplikasi menjadi minimal 3 target mandiri:
1. `VaultClient`: Interface dan implementasi penyimpanan aman dengan simulasi delay enkripsi.
2. `VaultFeature`: Reducer TCA yang mengatur state keamanan (Locked, Unlocking, Unlocked, FailedAttempts).
3. `VaultApp`: Multiplatform App Target (iOS & macOS).

#### Persyaratan Fungsional & Teknis:
1. **Target SPM Modular**:
   * Definisikan satu local Swift Package dengan target terpisah untuk `VaultClient` dan `VaultFeature`.
   * Target `VaultFeature` **tidak boleh** mengimpor kode konkret Apple Security framework langsung; seluruh I/O wajib melalui `VaultClient`.
2. **Spesifikasi Logic TCA**:
   * Jika pengguna salah memasukkan PIN sebanyak 3 kali berturut-turut, kunci sistem selama 10 detik menggunakan timer effect yang dapat dibatalkan (`cancellable`).
   * State harus mematuhi `@ObservableState` dan Action harus berstatus `Sendable`.
3. **Multiplatform Adaptive View**:
   * **iOS**: Tampilkan custom Secure PIN Numpad (tombol 0–9 bergaya grid).
   * **macOS**: Tampilkan form input keyboard native `SecureField` dengan shortcut keyboard `Return`.
4. **Unit Test Coverage**:
   * Tulis minimal 2 unit test menggunakan `TestStore`:
     1. Uji skenario sukses memasukkan PIN dan memvalidasi state `isUnlocked == true`.
     2. Uji skenario gagal 3 kali dan pastikan timer penguncian diaktifkan secara akurat.

Tantangan ini menuntut integrasi penuh dari prinsip pemisahan interface, determinisme state machine, isolasi konkurensi Swift 6, dan adaptasi native multiplatform SwiftUI.