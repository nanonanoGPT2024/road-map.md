# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI
**BAB 10: Enterprise Architecture, SPM Modularization, Multiplatform Target & The Composable Architecture (TCA)**
**Kategori: 02-Programming-Languages / swift-ui**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, Principal/Lead iOS Engineer diharapkan mampu:
1. **Mendesain dan Mengimplementasikan** arsitektur modular berskala enterprise menggunakan Swift Package Manager (SPM) dengan *compilation firewall* yang memisahkan layer antarmuka (*API/Interface*) dan implementasi (*Live/Mocks*).
2. **Menguasai Pola State Management Deterministik** berbasis The Composable Architecture (TCA) modern (v1.8+ dengan Observation framework `@ObservableState` dan `@Reducer`) untuk menghilangkan konkurensi tak terprediksi (*data race*) dan inkonsistensi state global.
3. **Mengoptimalkan Pipeline Kompilasi dan Linker** pada monorepo multi-target (iOS, macOS, visionOS) dengan memitigasi overhead *dynamic dispatch*, *static linking code bloat*, dan dependency cycle.
4. **Menerapkan Advanced Concurrency & Cancellation Trees** menggunakan Swift structured concurrency yang terintegrasi penuh ke dalam siklus hidup *Effects* TCA.
5. **Menulis Unit & Integration Test Berskala Enterprise** menggunakan `TestStore` dengan cakupan 100% jalur deterministik (non-exhaustive testing, dependency overriding, dan clock control).

---

## 2. Prerequisite
Untuk menyerap materi ini secara optimal, Anda wajib menguasai:
* **Swift Concurrency Mendalam**: `async`/`await`, `Actors`, `Sendable` checking, `TaskGroup`, dan `AsyncSequence`.
* **SwiftUI Core Internals**: Dependency graph SwiftUI, *AttributeGraph engine*, structural identity vs explicit identity, dan dynamic property wrappers.
* **SPM Dependency Manifest**: Pemahaman mendalam terkait `Package.swift`, target types (`.target`, `.executableTarget`, `.testTarget`), dependencies condition, dan build settings.
* **Git Workflows & Monorepo Strategy**: Branching scale, submodule/subtree, dan caching build artifacts (misal: Tuist, Bazel, atau SPM artifact caching).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 TCA Engine Internals: Modern Observation & Reducer Protocol
TCA modern meninggalkan abstraksi lama (`ViewStore` berbasis Combine) dan beralih langsung ke runtime engine Swift modern via makro `@ObservableState` dan framework `Observation`.

```
          +-------------------------------------------------+
          |                      VIEW                       |
          |  (Mengamati @ObservableState via Property Read) |
          +-------------------------------------------------+
                    |                              ^
             Mengirim Action                  State Berubah
                    v                        (Fine-grained)
          +-------------------------------------------------+
          |                     STORE                       |
          |          (Pusat Orkestrasi & State Box)         |
          +-------------------------------------------------+
                    |                              ^
             Meneruskan Action               Mutasi State &
                    v                        Eksekusi Effect
          +-------------------------------------------------+
          |                    REDUCER                      |
          |   mutating func reduce(into:action:) -> Effect  |
          +-------------------------------------------------+
                    |                              ^
              Pemicu Async/IO                Umpan Balik
                    v                         (Action)
          +-------------------------------------------------+
          |               DEPENDENCY SYSTEM                 |
          |   (@Dependency Client & Swift Concurrency Task) |
          +-------------------------------------------------+
```

#### Alur Eksekusi Internal:
1. **Property Access Registration**: Saat View mengevaluasi `body`, macro `@ObservableState` memanfaatkan `withObservationTracking` milik Swift runtime. Hanya field state spesifik yang di-*read* oleh View tersebut yang didaftarkan ke *AttributeGraph*. Jika field state lain pada node yang sama bermutasi, View **tidak akan me-render ulang** (menghilangkan *over-invalidation*).
2. **Action Dispatching**: Action dikirim ke `Store`. `Store` memastikan eksekusi berlangsung pada thread yang benar (secara default `@MainActor` terisolasi untuk UI Store).
3. **Synchronous Mutation**: Fungsi `reduce(into:inout State, action: Action) -> Effect<Action>` dieksekusi. State bermutasi secara deterministik (*inout*).
4. **Effect Resolution**: Reducer mengembalikan tipe `Effect`. Efek samping (*I/O, Network, Persistence*) dieksekusi secara asinkron dalam task terisolasi melalui `.run { send in ... }`. Task ini dapat membatalkan dirinya sendiri (*cancellation key*) atau mengirimkan Action lanjutan kembali ke Store.

### 3.2 Modularization via SPM Compilation Firewalls
Skala enterprise menuntut *Clean Architecture* berbasis package independen. Menggabungkan semua fitur dalam satu target aplikasi menyebabkan:
* *Exponential compile-time regression*.
* *Implicit tight coupling*.
* Kurangnya kepemilikan kode antar tim (*code ownership*).

Pola **Interface-Live-Mock (ILM)** membagi setiap modul menjadi tiga target berbeda:

```
[ Feature Implementation Target ] 
       |             |
       v             | (Hanya depend ke Interface)
[ Interface Target ] |
       ^             v
       |      [ Mock Target ] (Untuk TestStore & Preview)
[ Live Implementation Target ] (Mengimplementasikan network/DB riil)
```

Dengan memisahkan `FeatureInterface` dari `FeatureLive`, compiler tidak perlu melakukan recompilation pada target `FeatureConsumer` saat implementasi internal di `FeatureLive` mengalami perubahan kode.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Massive MVVM / Clean-VIPER) | Enterprise Modular TCA (SPM + Reducer Protocol) |
| :--- | :--- | :--- |
| **State Consistency** | Mutasi state tersebar di berbagai `ObservableObject`, rawan *race condition* dan *dual source of truth*. | *Single Source of Truth* per domain context; mutasi state hanya diizinkan secara deterministik melalui *Action*. |
| **Concurrency Bugs** | Mengandalkan `DispatchQueue.main.async` manual atau Task bebas; memicu *purple runtime warnings* dan *thread starvation*. | Dikelola via structured concurrency (`Effect.run`); pembatalan otomatis (*cancellation tokens*) dan *mockable clocks*. |
| **Compile Time** | Monolithic build graph; perubahan 1 baris kode memicu re-compile seluruh module dependan. | *Interface-driven compilation firewalls*; eksploitasi penuh SPM dynamic/static target graph caching. |
| **Testability** | Bergantung pada mock object manual yang rentan mengalami *drift*; testing interaksi async sering membutuhkan `wait(for:timeout:)`. | Menggunakan `TestStore` bawaan; verifikasi mutasi state exhaustif / non-exhaustif dan assertion dependency tanpa mock boilerplates. |

---

## 5. How (Workflow Detail)

1. **Definisikan Domain Interface**:
   Buat target SPM `[Feature]DomainInterface`. Buat data transfer object (DTO) bertipe `Sendable`, `Equatable`, serta client struct yang membungkus endpoint fungsional melalui property bertipe closure.
2. **Registrasikan Dependency**:
   Gunakan macro `@DependencyClient` dari Point-Free untuk membuat implementasi *unimplemented/test-friendly*. Daftarkan client ke `DependencyValues` via `DependencyKey`.
3. **Konstruksi State & Reducer**:
   Implementasikan modul UI `[Feature]Feature`. Definisikan `State` (dianotasi `@ObservableState`), `Action`, dan implementasikan body reducer menggunakan macro `@Reducer`.
4. **Tangani Side-Effects & Concurrency**:
   Gunakan environment `@Dependency` yang disuntikkan secara deklaratif. Hindari pemanggilan asinkronus tak terkontrol; bungkus dalam `Effect.run` dengan penanganan pembatalan (*cancellation token*) eksplisit.
5. **Isolasi Implementasi Real**:
   Implementasikan target `[Feature]DomainLive`. Target ini mengimpor `[Feature]DomainInterface` dan menyuntikkan adapter jaringan/database riil.
6. **Integrasi Komposisi Root**:
   Pada root application target, gabungkan reducer fitur individual ke root reducer via *Tree-based navigation* (`Presents()` dan `ifLet()`) atau *Stack-based navigation* (`StackState` dan `StackAction`).

---

## 6. Analogy & Diagram ASCII

### Analogi: Sistem Avionik Fly-by-Wire Pesawat Komersial
Bayangkan arsitektur enterprise seperti kokpit pesawat modern:
* **View (Instrumen Kokpit & Tuas)**: Pilot melihat tampilan instrumen dan menggerakkan tuas navigasi (*UI Interactions*). Pilot tidak menggerakkan hidrolik sayap secara mekanis langsung.
* **Action (Sinyal Digital dari Tuas)**: Tuas menghasilkan sinyal elektrik standar (*Action*) yang dikirim ke bus data sentral.
* **Store & Reducer (Flight Control Computer)**: Komputer pusat memproses sinyal, memvalidasi dengan kondisi fisik saat ini (*State*), lalu menghasilkan perubahan status flap (*State Mutation*) dan mengirim perintah ke motor mekanik (*Effects*).
* **Dependencies (Sensor Radar, GPS, dan Pompa Hidrolik)**: Komputer tidak tahu merek pompa hidrolik apa yang terpasang; ia hanya berbicara pada protokol standar (*Domain Interface*). Saat pengujian di hangar, mekanik mencabut sensor asli dan memasang unit simulator penerbangan (*Test/Mock Implementation*) tanpa menyentuh komputer kokpit.

### Diagram Arsitektur SPM Enterprise
```
+--------------------------------------------------------------------------+
|                               App Target                                 |
|         (Composition Root, AppReducer, Dynamic Environment Injection)   |
+--------------------------------------------------------------------------+
       |                                                    |
       v                                                    v
+-------------------------------+         +--------------------------------+
|    OnboardingFeature (SPM)    |         |       CheckoutFeature (SPM)    |
| (UI, State Machine, Reducer)  |         |  (UI, State Machine, Reducer)  |
+-------------------------------+         +--------------------------------+
       |                                                    |
       v                                                    v
+-------------------------------+         +--------------------------------+
| OnboardingInterface & Models  |         |   PaymentDomainInterface (SPM) |
|         (Lightweight)         |         |     (@DependencyClient DTO)    |
+-------------------------------+         +--------------------------------+
                                                            ^
                                                            |
                                          +--------------------------------+
                                          |    PaymentDomainLive (SPM)     |
                                          | (URLSession, Stripe/APM SDK)   |
                                          +--------------------------------+
                                                            |
                                                            v
                                          +--------------------------------+
                                          |   NetworkingCoreEngine (SPM)   |
                                          |   (HTTPClient, AuthInterceptor)|
                                          +--------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Reducer Modern Menggunakan Observation (TCA v1.8+)
Berikut adalah implementasi dasar isolasi state dan action dengan penanganan asinkron modern.

```swift
import ComposableArchitecture
import Foundation

// MARK: - Reducer Definition
@Reducer
public struct CounterFeature {
    @ObservableState
    public struct State: Equatable {
        public var count: Int = 0
        public var isTimerRunning: Bool = false
        public init() {}
    }

    public enum Action: Sendable {
        case incrementButtonTapped
        case decrementButtonTapped
        case toggleTimerTapped
        case timerTicked
    }

    @Dependency(\.continuousClock) var clock
    private enum CancelID { case timer }

    public init() {}

    public var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case .incrementButtonTapped:
                state.count += 1
                return .none

            case .decrementButtonTapped:
                state.count -= 1
                return .none

            case .toggleTimerTapped:
                state.isTimerRunning.toggle()
                if state.isTimerRunning {
                    return .run { send in
                        for await _ in self.clock.timer(interval: .seconds(1)) {
                            await send(.timerTicked)
                        }
                    }
                    .cancellable(id: CancelID.timer)
                } else {
                    return .cancel(id: CancelID.timer)
                }

            case .timerTicked:
                state.count += 1
                return .none
            }
        }
    }
}
```

---

### 7.2 Practical Example: Enterprise Checkout Transaction Engine
Implementasi produksi untuk transaksi finansial yang modular, mencakup dependency decoupling, handling cancellation, idempotent API calls, dan error-recovery.

#### Layer 1: Interface Package (`PaymentDomainInterface`)
```swift
import ComposableArchitecture
import DependenciesMacros
import Foundation

public struct PaymentReceipt: Equatable, Sendable, Codable {
    public let transactionID: UUID
    public let amount: Decimal
    public let timestamp: Date

    public init(transactionID: UUID, amount: Decimal, timestamp: Date) {
        self.transactionID = transactionID
        self.amount = amount
        self.timestamp = timestamp
    }
}

public enum PaymentError: Error, Equatable, Sendable {
    case networkFailure(String)
    case insufficientFunds
    case fraudRejected
    case unknown
}

@DependencyClient
public struct PaymentClient: Sendable {
    public var processTransaction: @Sendable (_ amount: Decimal, _ idempotencyKey: UUID) async throws -> PaymentReceipt
}

extension DependencyValues {
    public var paymentClient: PaymentClient {
        get { self[PaymentClient.self] }
        set { self[PaymentClient.self] = newValue }
    }
}

extension PaymentClient: TestDependencyKey {
    public static let testValue = Self()
    public static let previewValue = Self(
        processTransaction: { amount, _ in
            PaymentReceipt(transactionID: UUID(), amount: amount, timestamp: Date())
        }
    )
}
```

#### Layer 2: Live Implementation Package (`PaymentDomainLive`)
```swift
import Dependencies
import Foundation
import PaymentDomainInterface

extension PaymentClient: DependencyKey {
    public static let liveValue = Self(
        processTransaction: { amount, idempotencyKey in
            var request = URLRequest(url: URL(string: "https://api.fintech.enterprise/v1/checkout")!)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue(idempotencyKey.uuidString, forHTTPHeaderField: "Idempotency-Key")

            let payload = ["amount": amount]
            request.httpBody = try JSONEncoder().encode(payload)

            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw PaymentError.unknown
            }

            switch httpResponse.statusCode {
            case 200...299:
                return try JSONDecoder().decode(PaymentReceipt.self, from: data)
            case 402:
                throw PaymentError.insufficientFunds
            case 403:
                throw PaymentError.fraudRejected
            default:
                throw PaymentError.networkFailure("HTTP Error: \(httpResponse.statusCode)")
            }
        }
    )
}
```

#### Layer 3: Feature Package (`PaymentFeature`)
```swift
import ComposableArchitecture
import Foundation
import PaymentDomainInterface
import SwiftUI

@Reducer
public struct CheckoutFeature {
    @ObservableState
    public struct State: Equatable {
        public var totalAmount: Decimal
        public var isProcessing: Bool = false
        public var transactionReceipt: PaymentReceipt?
        public var errorMessage: String?
        public var idempotencyToken: UUID

        public init(totalAmount: Decimal) {
            self.totalAmount = totalAmount
            self.idempotencyToken = UUID()
        }
    }

    public enum Action: Sendable {
        case payButtonTapped
        case transactionResponse(Result<PaymentReceipt, PaymentError>)
        case dismissReceipt
        case cancelOngoingPayment
    }

    @Dependency(\.paymentClient) var paymentClient
    private enum CancelID { case executionToken }

    public init() {}

    public var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case .payButtonTapped:
                state.isProcessing = true
                state.errorMessage = nil
                let amount = state.totalAmount
                let token = state.idempotencyToken

                return .run { send in
                    do {
                        let receipt = try await self.paymentClient.processTransaction(amount, token)
                        await send(.transactionResponse(.success(receipt)))
                    } catch let error as PaymentError {
                        await send(.transactionResponse(.failure(error)))
                    } catch {
                        await send(.transactionResponse(.failure(.unknown)))
                    }
                }
                .cancellable(id: CancelID.executionToken, cancelInFlight: true)

            case let .transactionResponse(.success(receipt)):
                state.isProcessing = false
                state.transactionReceipt = receipt
                return .none

            case let .transactionResponse(.failure(error)):
                state.isProcessing = false
                switch error {
                case .insufficientFunds:
                    state.errorMessage = "Saldo akun Anda tidak mencukupi untuk transaksi ini."
                case .fraudRejected:
                    state.errorMessage = "Transaksi ditolak oleh sistem keamanan perbankan."
                case let .networkFailure(msg):
                    state.errorMessage = "Koneksi terputus: \(msg). Silakan coba lagi."
                case .unknown:
                    state.errorMessage = "Terjadi kegagalan transaksi sistematis."
                }
                return .none

            case .cancelOngoingPayment:
                state.isProcessing = false
                return .cancel(id: CancelID.executionToken)

            case .dismissReceipt:
                state.transactionReceipt = nil
                state.idempotencyToken = UUID() // Refresh token idempotensi baru
                return .none
            }
        }
    }
}

// MARK: - View Layer
public struct CheckoutView: View {
    @Bindable var store: StoreOf<CheckoutFeature>

    public init(store: StoreOf<CheckoutFeature>) {
        self.store = store
    }

    public var body: some View {
        VStack(spacing: 24) {
            Text("Total Tagihan")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            
            Text(store.totalAmount, format: .currency(code: "IDR"))
                .font(.system(size: 36, weight: .bold))

            if let error = store.errorMessage {
                Text(error)
                    .font(.footnote)
                    .foregroundStyle(.red)
                    .multilineTextAlignment(.center)
                    .padding()
            }

            if store.isProcessing {
                ProgressView("Memproses Transaksi Terenkripsi...")
                Button("Batalkan Transaksi") {
                    store.send(.cancelOngoingPayment)
                }
                .tint(.red)
            } else {
                Button("Konfirmasi & Bayar Sekarang") {
                    store.send(.payButtonTapped)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
            }
        }
        .padding()
        .sheet(item: Binding(
            get: { store.transactionReceipt.map { IdentifiableReceipt(receipt: $0) } },
            set: { _ in store.send(.dismissReceipt) }
        )) { wrapper in
            VStack(spacing: 16) {
                Image(systemName: "checkmark.seal.fill")
                    .font(.system(size: 64))
                    .foregroundStyle(.green)
                Text("Transaksi Berhasil!")
                    .font(.headline)
                Text("ID: \(wrapper.receipt.transactionID.uuidString)")
                    .font(.caption)
                    .monospaced()
                Button("Selesai") {
                    store.send(.dismissReceipt)
                }
                .buttonStyle(.bordered)
            }
            .padding()
        }
    }
}

private struct IdentifiableReceipt: Identifiable {
    var id: UUID { receipt.transactionID }
    let receipt: PaymentReceipt
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Tier-1 Digital Banking Platform (SuperApp Migration)
* **Konteks**: Aplikasi monolitik dengan 60+ engineer, 4 squad vertikal (Core Banking, Wealth/Investment, Lending, Lifestyle).
* **Masalah**:
  1. *Clean build time* lokal di CI/CD memakan waktu 24 menit; *incremental build* memakan waktu 3 menit.
  2. Modul *Wealth* sering memicu state mutation crash secara asinkron di modul *Core Banking* akibat pattern `NotificationCenter` dan shared singletons (`AccountBalanceManager.shared`).
  3. UI test sangat flaky (tingkat kegagalan 38%) karena dependensi asynchronous network timing.

### Solusi Arsitektur SPM + TCA:
1. **Pemisahan Monorepo SPM**:
   Memecah modul ke dalam 45 SPM packages terpisah dengan arsitektur multi-repo/monorepo híbrida. Core infrastructure dipisahkan ke `CoreNetwork`, `CoreDesignSystem`, `CoreStorage`.
2. **Penerapan Interface vs Implementation Firewall**:
   Setiap squad mengekspos paket `[Squad]DomainInterface`. Target Live hanya di-*link* oleh target aplikasi utama. Modul UI Squad A dapat berkomunikasi dengan Squad B hanya melalui `[Squad]DomainInterface` tanpa menautkan kode konkrit modul implementasi.
3. **Migrasi State Management ke TCA**:
   Seluruh mutasi balance diwajibkan melewati satu reducer root tree via `Scope`. Reducer Core Banking mengekspos dependency client untuk mengambil snapshot data, dieksekusi secara terisolasi via Swift Actors.
4. **Deterministic Testing Suite**:
   Flaky UI testing digantikan oleh 450+ unit testing berbasis `TestStore`. Asynchronous task diuji deterministik menggunakan `TestClock`.

### Hasil (Metrik Terukur):
* **Compile Time**: Clean build terpangkas dari 24 menit menjadi **5 menit 12 detik** di CI (memanfaatkan remote caching SPM); incremental build berkurang menjadi **9 detik**.
* **Crash Rate**: Angka *fatal concurrent mutation crash* drop dari **0.42% ke 0.002%**.
* **Pipeline Success Rate**: Keberhasilan build CI/CD meningkat dari **62% menjadi 99.1%**.

---

## 9. Trade-offs

| Dimensi Arsitektural | Pendekatan Monolitik / MVVM Tradisional | SPM Modularization + The Composable Architecture |
| :--- | :--- | :--- |
| **Runtime Performance** | **Tinggi (Direct Pointer)**. Tidak ada abstraksi middleware reducer. Minim alokasi heap ekstra. | **Sedang-Tinggi**. TCA modern berbasis macro `@ObservableState` sangat cepat, namun struct copying untuk state kompleks bernilai besar dapat menimbulkan overhead jika tidak didesain dengan copy-on-write semantics. |
| **Latency Mutasi State** | Nol komparasi. View langsung bereaksi terhadap binding reference pointer. | Deterministik. Mengalir melalui pipe Reducer, pencatatan log trace, dan dynamic scoping. |
| **Scalability (Tim)** | **Rendah**. Merge conflict persisten pada storyboard/file ViewModel sentral; batasan dependency antar engineer ambigu. | **Sangat Tinggi**. Interface boundary SPM kaku mencegah circular dependency. Squad dapat bekerja secara independen di package masing-masing. |
| **Cognitive Load & Learning Curve** | **Rendah**. Sangat lazim bagi programmer junior-intermediate Swift. | **Tinggi**. Membutuhkan penguasaan fungsional programming, Swift macros, state machines, serta structured concurrency. |
| **Binary Size Overhead** | Minimal. Hanya overhead standar Swift Runtime metadata. | Tambahan metadata macro dan *inlined action enums*. Namun dapat diminimalkan dengan penataan Static Library linking yang benar. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Scoping Store di Ephemeral Views Memicu Memory Leaks
* **Kesalahan**: Membuat store baru secara berulang kali langsung di dalam method `body` SwiftUI menggunakan `.scope()`.
```swift
// SALAH (MEMICU RE-INITIALIZATION LOOP DI SETIAP TICK RENDER)
var body: some View {
    ChildView(store: self.store.scope(state: \.child, action: \.child))
}
```
* **Solusi**: Di TCA modern, gunakan scoped store langsung via bindable property wrapper atau simpan scoping di dalam child state hierarchy menggunakan pattern tree navigation `@Presents`.
```swift
// BENAR (Modern Navigation Scoping)
var body: some View {
    NavigationStack {
        ParentView(store: self.store)
            .navigationDestination(
                item: $store.scope(state: \.destination?.detail, action: \.destination.detail)
            ) { childStore in
                DetailView(store: childStore)
            }
    }
}
```

### 10.2 Melakukan Mutasi Berat (I/O, Parsing) Langsung di Reducer
* **Kesalahan**: Melakukan blocking synchronization di dalam `reduce(into:action:)`. Ingat bahwa reducer dieksekusi sinkron di `@MainActor`.
```swift
// SALAH: BLOCKING THREAD UTAMA
case .loadJSONData:
    let data = try! Data(contentsOf: localFileURL) // Freeze MainActor!
    state.items = try! JSONDecoder().decode([Item].self, from: data)
    return .none
```
* **Solusi**: Alihkan semua tugas komputasi dan disk I/O ke dalam layer dependency atau bungkus ke dalam `Effect.run` menggunakan worker actor:
```swift
// BENAR: BACKGROUND EXECUTION VIA EFFECT
case .loadJSONData:
    state.isLoading = true
    return .run { send in
        let items = try await self.storageClient.fetchAndParse(localFileURL)
        await send(.dataLoaded(items))
    }
```

### 10.3 SPM Circular Dependency & Duplicate Symbol Linker Errors
* **Gejala Linker**: `ld: duplicate symbol '_OBJC_METACLASS_$_XYZ'` atau error cycle SPM: `Package graph contains a cycle`.
* **Investigasi**: Terjadi saat Target A depend ke Target B secara `.dynamic`, dan Target B depend kembali ke Target A, atau dua dynamic library mengimpor static package yang sama.
* **Solusi**:
  1. Standarkan package internal SPM Anda secara implisit (default SPM linker: biarkan tanpa `.static` atau `.dynamic` eksplisit kecuali jika membuat target plugin atau framework luar).
  2. Gunakan diagram dependensi strict unidirectional: `Root -> Feature -> DomainInterface <- DomainLive`.

---

## 11. Best Practices (Production Checklist)

- [ ] **State Flatness**: Hindari nesting state struct lebih dari 3 tingkat. Gunakan ID references atau normalized state collections jika menangani list relasional.
- [ ] **Thread Confinement**: Pastikan semua interaksi View dan Reducer Store utama dianotasi dengan `@MainActor`.
- [ ] **Action Granularity**: Beri nama Action berdasarkan **apa yang dilakukan pengguna**, bukan berdasarkan **apa yang harus diubah state** (misal: `payButtonTapped`, BUKAN `setLoadingTrueAndStartTransfer`).
- [ ] **Exhaustive Cancellation Tags**: Berikan Cancellation ID eksplisit (`.cancellable(id: ..., cancelInFlight: true)`) pada setiap request pencarian real-time (*typeahead*) atau pagination asinkron.
- [ ] **Zero Unhandled Effect Errors**: Bungkus seluruh dependency error dalam tipe Result bervariasi secara ketat (*typed errors*) agar tidak ada crash akibat `try!`.
- [ ] **SPM API Boundaries**: Target `Interface` dilarang keras mengimpor framework platform UI tingkat tinggi (`SwiftUI`, `AppKit`, `UIKit`) jika hanya berupa domain model & client logic.
- [ ] **Previews Isolation**: Manfaatkan `withDependencies` pada SwiftUI Preview agar preview dapat me-render data seketika tanpa koneksi jaringan riil.

---

## 12. Hands-on Practice: Membangun Multi-Package SPM Monorepo
Simpan struktur dan berkas proyek ini di bawah folder: `hands-on/m02/`

### Struktur Direktori:
```text
hands-on/m02/
├── Package.swift
└── Sources/
    ├── TransactionInterface/
    │   └── TransactionInterface.swift
    ├── TransactionLive/
    │   └── TransactionLive.swift
    └── TransactionFeature/
        ├── TransactionFeature.swift
        └── TransactionView.swift
```

### Langkah 1: Inisialisasi Manifest `Package.swift`
```swift
// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "EnterpriseBankingModule",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "TransactionFeature", targets: ["TransactionFeature"]),
        .library(name: "TransactionInterface", targets: ["TransactionInterface"]),
        .library(name: "TransactionLive", targets: ["TransactionLive"]),
    ],
    dependencies: [
        .package(url: "https://github.com/pointfreeco/swift-composable-architecture", exact: "1.8.2"),
        .package(url: "https://github.com/pointfreeco/swift-dependencies", exact: "1.2.2"),
    ],
    targets: [
        // Interface Target (Zero heavy dependencies)
        .target(
            name: "TransactionInterface",
            dependencies: [
                .product(name: "Dependencies", package: "swift-dependencies"),
                .product(name: "DependenciesMacros", package: "swift-dependencies"),
            ]
        ),
        // Live Implementation Target
        .target(
            name: "TransactionLive",
            dependencies: [
                "TransactionInterface",
            ]
        ),
        // Feature Target (UI + Reducer)
        .target(
            name: "TransactionFeature",
            dependencies: [
                "TransactionInterface",
                .product(name: "ComposableArchitecture", package: "swift-composable-architecture"),
            ]
        ),
    ]
)
```

### Langkah 2: Buat Kontrak `TransactionInterface.swift`
```swift
import Foundation
import Dependencies
import DependenciesMacros

public struct AccountBalance: Sendable, Equatable {
    public let available: Decimal
    public let currency: String

    public init(available: Decimal, currency: String) {
        self.available = available
        self.currency = currency
    }
}

@DependencyClient
public struct TransactionClient: Sendable {
    public var fetchBalance: @Sendable () async throws -> AccountBalance
}

extension DependencyValues {
    public var transactionClient: TransactionClient {
        get { self[TransactionClient.self] }
        set { self[TransactionClient.self] = newValue }
    }
}

extension TransactionClient: TestDependencyKey {
    public static let testValue = Self()
    public static let previewValue = Self(
        fetchBalance: { AccountBalance(available: 50000000.0, currency: "IDR") }
    )
}
```

### Langkah 3: Implementasi Adapter `TransactionLive.swift`
```swift
import Foundation
import Dependencies
import TransactionInterface

extension TransactionClient: DependencyKey {
    public static let liveValue = Self(
        fetchBalance: {
            // Simulasi Network Call Real
            try await Task.sleep(for: .seconds(1))
            return AccountBalance(available: 125750000.00, currency: "IDR")
        }
    )
}
```

### Langkah 4: Bangun UI dan Mesin Reducer `TransactionFeature.swift`
```swift
import ComposableArchitecture
import Foundation
import SwiftUI
import TransactionInterface

@Reducer
public struct TransactionFeature {
    @ObservableState
    public struct State: Equatable {
        public var balance: AccountBalance?
        public var isLoading: Bool = false
        public var errorMessage: String?

        public init() {}
    }

    public enum Action: Sendable {
        case onAppear
        case balanceResponse(Result<AccountBalance, Error>)
        case refreshTapped
    }

    @Dependency(\.transactionClient) var transactionClient

    public init() {}

    public var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case .onAppear, .refreshTapped:
                state.isLoading = true
                state.errorMessage = nil
                return .run { send in
                    do {
                        let result = try await self.transactionClient.fetchBalance()
                        await send(.balanceResponse(.success(result)))
                    } catch {
                        await send(.balanceResponse(.failure(error)))
                    }
                }

            case let .balanceResponse(.success(balance)):
                state.isLoading = false
                state.balance = balance
                return .none

            case let .balanceResponse(.failure(error)):
                state.isLoading = false
                state.errorMessage = error.localizedDescription
                return .none
            }
        }
    }
}

public struct TransactionView: View {
    @Bindable var store: StoreOf<TransactionFeature>

    public init(store: StoreOf<TransactionFeature>) {
        self.store = store
    }

    public var body: some View {
        VStack(spacing: 16) {
            if store.isLoading {
                ProgressView("Memperbarui Saldo...")
            } else if let balance = store.balance {
                Text("Saldo Rekening")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text("\(balance.currency) \(balance.available as NSNumber, formatter: NumberFormatter.currencyFormatter)")
                    .font(.title)
                    .bold()
            } else if let err = store.errorMessage {
                Text(err).foregroundStyle(.red)
            }

            Button("Segarkan Saldo") {
                store.send(.refreshTapped)
            }
            .buttonStyle(.bordered)
        }
        .onAppear {
            store.send(.onAppear)
        }
    }
}

private extension NumberFormatter {
    static let currencyFormatter: NumberFormatter = {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = "."
        return formatter
    }()
}
```

---

## 13. Exercise

### Level Easy: Porting Pola Sinkronus
Ambil sebuah tampilan konvensional SwiftUI `@State` yang memiliki toggle visibility dan counter angka. Konversikan komponen tersebut ke dalam modular target TCA dengan `@ObservableState`, action enum, dan pastikan reducer memvalidasi batasan nilai: angka tidak boleh bernilai negatif.

### Level Medium: Debounced Asynchronous Search Bar Feature
Bangun target SPM `SearchFeature` yang mengonsumsi dependency client `SearchClient`.
* Input query teks harus di-*debounce* selama 300ms menggunakan Swift Concurrency `Clock`.
* Jika pengguna mengetik karakter baru saat request sebelumnya masih berjalan di background, request lama harus otomatis dibatalkan via `.cancellable(id: ..., cancelInFlight: true)`.

### Level Hard: Multi-Step Registration Wizard dengan Isolation Rollback
Bangun sistem registrasi perbankan 3 langkah (Data Personal -> Dokumen KTP -> Pengaturan PIN).
* Gunakan tree-based navigation (`@Presents` dan `Path`).
* State dari langkah ke-3 tidak boleh dapat diselesaikan jika verification token di langkah ke-2 invalid.
* Sediakan mekanisme action `abortWizard` yang membatalkan seluruh network call child step, me-reset seluruh state child target, dan mengembalikan stack navigasi ke root dalam satu transisi atomik. Tuliskan pengujian deterministiknya menggunakan `TestStore`.

---

## 14. Challenge: Multi-Platform Document Synchronization Engine (Offline-First)

### Deskripsi Masalah:
Perusahaan enterprise membutuhkan Document Synchronization Feature yang harus berjalan di **iOS, macOS, dan visionOS**. Mesin ini beroperasi dalam mode offline-first dengan database SQLite/GRDB lokal, dan harus melakukan rekonsiliasi state dua arah saat perangkat terhubung kembali ke jaringan internet.

### Kriteria Arsitektur & Spesifikasi:
1. **Pemisahan Modular SPM**:
   * `SyncEngineCore`: Pure Swift (No UIKit/SwiftUI/AppKit), menangani state machine merge conflict, CRDT (*Conflict-free Replicated Data Type*), atau algoritma vector clock.
   * `SyncEngineDatabase`: Implementasi SQLite Client lokal.
   * `SyncEngineNetwork`: Mengelola WebSocket dan long-polling connection lifecycle.
   * `SyncEngineUI`: SwiftUI Views adaptif untuk platform mobile (touch), desktop (keyboard shortcuts), dan spatial spatial computing (visionOS volumes/windows).
2. **Kebutuhan Concurrency**:
   * Eksekusi parsing metadata file biner besar (>100MB) tidak boleh menempati thread `@MainActor`.
   * Reducer harus dapat menerima sinyal perubahan jaringan secara reaktif (menggunakan `AsyncStream`) dan mengorkestrasi *batch syncing*.
3. **Deterministic Failure Injection**:
   * Buat custom `TestStore` suite yang mensimulasikan kegagalan jaringan acak (jitter) di tengah proses sinkronisasi 10 dokumen, dan buktikan bahwa tidak ada duplikasi data atau kebocoran state parsial (*zero data corruption*).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)
1. **Mengapa macro `@ObservableState` pada TCA modern jauh lebih optimal dibanding `ViewStore` berbasis Combine?**
   * *Jawaban*: `@ObservableState` mengintegrasikan Swift Observation framework secara native, melacak pembacaan property secara presisi pada level field (*fine-grained observation*). Hal ini mencegah re-rendering view secara massal saat ada mutasi field lain dalam state yang tidak digunakan oleh view tersebut, sekaligus mengeliminasi dependensi Combine publisher dan overhead alokasi `ViewStore`.

2. **Apa peran utama dari `Sendable` protocol dalam arsitektur Action TCA?**
   * *Jawaban*: `Action` harus berpindah melintasi batas thread/actor secara aman ketika diproses oleh `Store` atau dijalankan di dalam worker task via `Effect.run`. Menandai Action sebagai `Sendable` memastikan compiler Swift mengecek secara statis bahwa tidak ada data *mutable reference* yang dibagikan antar thread, mencegah terjadinya data race runtime.

3. **Apa perbedaan mendasar antara `.cancellable(id:)` dengan `.cancel(id:)`?**
   * *Jawaban*: `.cancellable(id:)` adalah modifier pada suatu `Effect` yang mendaftarkan task asinkron tersebut dengan identifier tertentu sehingga dapat diinterupsi kemudian. Sedangkan `.cancel(id:)` adalah instruksi `Effect` aktif yang memerintahkan TCA runtime untuk membatalkan dan menghentikan eksekusi task yang sedang berjalan di bawah identifier tersebut.

4. **Mengapa dependency interface harus dideklarasikan sebagai closure struct, bukan Swift protocol klasik?**
   * *Jawaban*: Struct berbasis closure mempermudah pembuatan mock inline parsial tanpa harus menulis *dummy implementation* untuk keseluruhan method protocol, mendukung pemanfaatan macro `@DependencyClient` secara otomatis, serta menghindari overhead kompilasi protocol dynamic dispatch (existentials `/ any Protocol`).

5. **Apa fungsi dari `TestStore.exhaustivity = .off`?**
   * *Jawaban*: Digunakan untuk melakukan *non-exhaustive testing*. Secara default, `TestStore` mewajibkan pengujian untuk mengonfirmasi setiap mutasi state dan menangani seluruh Action yang dikirimkan. Mematikannya (`.off`) memungkinkan engineer hanya menguji integrasi fungsional spesifik dari suatu use-case tanpa harus meng-assert lusinan perubahan state internal yang tidak relevan dengan fokus test.

---

### Bagian 2: Intermediate (5 Soal)
1. **Bagaimana cara mencegah memory leak / retain cycle saat menangani `Effect.run` yang mengakses method atau client lokal?**
   * *Jawaban*: Hindari meng-*capture* instance reducer atau `self` class di dalam closure. Selalu akses dependensi melalui property wrapper `@Dependency` yang di-resolve sebelum block closure dieksekusi atau panggil langsung via environment global capture (`self.dependencyClient`), serta pastikan hanya melewatkan primitive values atau DTO `Sendable` ke dalam closure `Effect.run`.

2. **Kapan sebuah library pada SPM wajib didefinisikan sebagai dynamic framework (`type: .dynamic`)?**
   * *Jawaban*: Saat library tersebut digunakan secara bersamaan oleh main application target dan satu atau lebih target extension (seperti Widget Extension, Notification Service Extension, Share Extension). Jika dibiarkan static, kode binary library tersebut akan disalin ganda ke dalam masing-masing executable target, menyebabkan *code bloat* signifikan dan inkonsistensi memori static variable.

3. **Jelaskan peran `cancelInFlight: true` pada modifier `.cancellable`!**
   * *Jawaban*: Menjamin bahwa jika Action pemicu dipanggil kembali saat efek samping sebelumnya dengan identifier yang sama masih berjalan, maka efek samping yang lama akan langsung dibatalkan sebelum efek yang baru mulai dijalankan. Ini sangat krusial untuk fitur autocomplete pencarian teks atau throttling klik tombol.

4. **Bagaimana TCA menangani stack-based navigation modern menggunakan `StackState` dan `Path`?**
   * *Jawaban*: `StackState` menampung kumpulan state linear dalam bentuk array heterogen yang merepresentasikan history navigasi. Reducer child dihubungkan melalui `forEach(\.path, action: \.path)`. Mutasi stack dapat dikontrol secara terpusat oleh parent reducer dengan memodifikasi isi koleksi data stack tersebut (push, pop, popToRoot) secara deterministik.

5. **Apa kelemahan utama menempatkan seluruh feature package dalam satu Package.swift monolithic dibanding multi-Package.swift terisolasi?**
   * *Jawaban*: Pada single `Package.swift`, setiap kali ada perubahan pada konfigurasi dependensi atau branch git dependency eksternal, seluruh target dalam package tersebut harus menjalani *package resolution* ulang. Multi-package memungkinkan granular caching per-repo, isolasi akses branch yang ketat, dan resolusi dependensi yang terdistribusi.

---

### Bagian 3: Production Case Scenarios (3 Soal)

#### Skenario 1: The Zombie Effect Bug
* **Kasus**: Setelah pengguna melakukan logout dari aplikasi, terkadang muncul event push alert yang mencoba menavigasi aplikasi ke halaman transaksi pengguna sebelumnya, menyebabkan crash runtime `Fatal error: Unexpectedly found nil while unwrapping an Optional value` pada scoped reducer.
* **Akar Masalah**: Task listener asinkronus (misal: WebSocket / Push Notification listener) yang berjalan pada background store tidak dibatalkan saat root state berganti dari `Authenticated` ke `Unauthenticated`.
* **Solusi Perbaikan**:
  Definisikan Root Action `.logout` yang memancarkan efek pembatalan global secara eksplisit:
  ```swift
  case .logout:
      state = .unauthenticated(UnauthenticatedState())
      return .merge(
          .cancel(id: CancelID.userSocketSession),
          .cancel(id: CancelID.transactionSyncTask),
          .run { _ in await self.authClient.clearTokens() }
      )
  ```

#### Skenario 2: Xcode Build Time Regression Pasca Adopsi Macro
* **Kasus**: Setelah mengadopsi `@ObservableState` dan `@Reducer` pada 150 feature modules, waktu kompilasi CI melonjak 40%.
* **Akar Masalah**: Pengevaluasian Swift Syntax Macro berjalan di setiap kompilasi modul individual secara terpisah. Jika pembagian modul terlalu kecil (*micro-packages* berlebihan dengan 1-2 file), overhead inisialisasi compiler macro executable melebihi keuntungan paralelisasi compilation.
* **Solusi Perbaikan**:
  1. Gabungkan target mikro-feature yang saling berkaitan erat (*cohesive domain*) ke dalam satu module medium-sized.
  2. Pastikan binary macro tools dijalankan menggunakan pre-compiled host plugin binaries di CI runner.
  3. Aktifkan Build Setting `SWIFT_COMPILER_STATIC_INITIALIZATION=YES` dan SPM dynamic module caching strategy.

#### Skenario 3: Race Condition Update Real-Time Crypto Ticker
* **Kasus**: Aplikasi trading crypto menerima 50 update harga per detik via streaming sequence. Tampilan SwiftUI mengalami freezing (*dropped frames* parah hingga 15 FPS) dan CPU usage mencapai 100%.
* **Akar Masalah**: Mengirim setiap packet update streaming langsung sebagai Action TCA individual (`await send(.priceUpdated(price))`) membanjiri main thread. Setiap Action mengeksekusi reducer, menjalankan verifikasi dependency graph, dan memicu re-evaluasi rendering UI sebanyak 50 kali per detik.
* **Solusi Perbaikan**:
  Gunakan operator throttling atau *buffering* pada Swift Concurrency `AsyncSequence` di dalam `Effect.run`. Tangkap fluktuasi data dan kirimkan update ke Reducer Store dalam interval teratur (misalnya maksimal tiap 100ms):
  ```swift
  case .startPriceStream:
      return .run { send in
          var buffer: [PriceUpdate] = []
          for await tick in self.cryptoClient.stream() {
              buffer.append(tick)
              // Flush buffer secara batch tiap interval atau ukuran batch
          }
      }
      .cancellable(id: CancelID.cryptoStream)
  ```
  Atau gunakan `.throttle(for: .milliseconds(100), clock: self.clock)` sebelum menembakkan Action ke Store.

---

## 16. Summary
* **Arsitektur Enterprise**: Menuntut batas isolasi mutlak antar fitur. Pemisahan layer interface, implementasi konkrit, dan UI via target SPM menghadirkan waktu kompilasi terprediksi dan skalabilitas tim tanpa batas gesekan dependensi (*zero cross-talk*).
* **The Composable Architecture (Modern TCA)**: Bukan sekadar framework UI, melainkan metodologi rekayasa perangkat lunak holistik yang memformalkan **State**, **Action**, **Reducer**, dan **Effect** menjadi satu siklus hidup terisolasi, deterministik, dan dapat diuji tanpa dependensi lingkungan eksternal.
* **Structured Effects Engine**: Penanganan asynchronous logic menggunakan Swift Concurrency di dalam TCA memberikan proteksi terhadap kebocoran memori, data race, dan task orphaned melalui pembatalan pohon dependensi (*hierarchical cancellation trees*) yang terstruktur.