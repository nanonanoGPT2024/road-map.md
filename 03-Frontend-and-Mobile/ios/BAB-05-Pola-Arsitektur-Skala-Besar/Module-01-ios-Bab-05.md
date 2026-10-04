# SEKSI 01 — IDENTITAS MODUL
* **Track:** Frontend & Mobile Engineering
* **Kategori:** 03-Frontend-and-Mobile
* **Kurikulum:** iOS Engineering (Advanced Level)
* **Bab:** 05 — Arsitektur & Rekayasa Perangkat Lunak Skala Enterprise
* **Modul:** 01 — Pola Arsitektur Skala Besar (Clean Architecture, MVVM, & TCA)
* **Target Audience:** Senior iOS Engineers, Mobile Architects, Lead Developers
* **Prasyarat:** Pemahaman mendalam tentang Swift modern (Concurrency/Actor, Structured Concurrency), SwiftUI lifecycle, Combine Framework, Dependency Injection, dan Unit Testing.

---

# SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta didik memiliki kapabilitas untuk:
1. Menganalisis, mengevaluasi, dan memilih arsitektur optimal (Clean Architecture + MVVM vs. The Composable Architecture / TCA) berdasarkan skala tim, kompleksitas domain, dan performa aplikasi.
2. Mengisolasi Business Domain dari framework Apple (SwiftUI, UIKit, CoreData, SwiftData) dengan menerapkan *Dependency Inversion Principle* (DIP) dan *Hexagonal/Clean Architecture Boundaries*.
3. Menerapkan state management deterministik, unireksional (*Unidirectional Data Flow* / UDF), dan bebas dari race condition menggunakan primitives modern Swift (Actors, `@Observable`, Sendable closures).
4. Merancang arsitektur aplikasi berbasis *The Composable Architecture* (TCA) yang modular, sepenuhnya dapat diuji (*100% testable*), serta mampu menangani *cancellation* dan efek samping (*side-effects*) kompleks secara deterministik.
5. Mengidentifikasi, mengukur, dan memitigasi *memory leaks*, *retain cycles*, serta *over-rendering* pada hierarki view SwiftUI melalui decoupling state yang granular.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Mental Model: Objek Imperatif ke Aliran Data Deterministik
Pada skala enterprise, arsitektur bukan sekadar tentang penempatan file atau folder, melainkan tentang **distribusi kepemilikan mutasi state** dan **isolasi side-effects**. 

```
Mental Model Tradisional (MVC/MVVM Spageti):
[View] <----> [ViewModel] <----> [Network/Database]
Mutasi state dapat dipicu dari mana saja, kapan saja, menghasilkan multi-source-of-truth dan Race Conditions.

Mental Model Skala Enterprise (UDF & Clean Architecture):
[Intent/Action] ---> [Pure Reducer / Domain Interactor] ---> [New Immutable State]
                                |                                     |
                                v                                     v
                       [Managed Side-Effect]                   [Declarative View]
```

Arsitektur skala enterprise membutuhkan tiga aksioma fundamental:
1. **Unidirectional Data Flow (UDF):** Data hanya mengalir dalam satu siklus tertutup. View hanya merender State; View mengirim Action; Mutator memproses Action dan menghasilkan State baru.
2. **Framework Decoupling:** Domain logic aplikasi Anda tidak boleh mengimpor `SwiftUI`, `UIKit`, atau `CoreData`. Domain logic harus berupa Swift murni (`Foundation` saja jika terpaksa) yang dapat dijalankan pada CLI (Command Line Interface) Linux tanpa modifikasi.
3. **Controlled Non-Determinism:** Jaringan, waktu (clocks), disk I/O, Bluetooth, dan random number generation adalah efek samping non-deterministik. Semuanya harus diabstraksi di balik interface/dependency clients yang dapat diganti dengan *mocks* instan saat automated testing.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram Komparatif: Clean Architecture (MVVM) vs. The Composable Architecture (TCA)

```
==========================================================================================
                     CLEAN ARCHITECTURE + MVVM (LAYERED / HEXAGONAL)
==========================================================================================

   [ Presentation Layer ]           [ Domain Layer ]                [ Data Layer ]
+---------------------------+     +--------------------+     +--------------------------+
|  SwiftUI View             |     |                    |     | Repositories (Impl)      |
|  - Observes ViewModel     |     | Use Cases          |     | - SwiftData / CoreData   |
|  - Triggers Intent/Action |     | (Interactors)      |     | - URLSession / Network   |
+-------------+-------------+     +---------+----------+     +-------------+------------+
              |                             |                              ^
              v                             v                              |
+---------------------------+     +--------------------+     +-------------+------------+
|  ViewModel (@Observable)  | --> | Domain Repository  | <-- | Data Mappers & DTOs      |
|  - UI State Machine       |     | (Protocols/DIP)    |     +--------------------------+
|  - Task lifecycle control |     +--------------------+
+---------------------------+     +--------------------+
                                  | Entities (Pure)    |
                                  +--------------------+

==========================================================================================
                      THE COMPOSABLE ARCHITECTURE (TCA / UDF)
==========================================================================================

                                       +--------------------------------+
                                       |             Store              |
                                       +--------------------------------+
                                        | ViewStore                     ^
                                        | Observes State                | Sends Action
                                        v                               |
                               +----------------+              +----------------+
                               |  SwiftUI View  | ------------>|     Action     |
                               +----------------+              +--------+-------+
                                                                        |
                                                                        v
+---------------------------------------------------------------------------------------+
|                                    Reducer (Pure)                                     |
|  (inout State, Action) -> Effect<Action>                                              |
|                                                                                       |
|   State Mutated In-Place               Dispatches Effect                              |
|   +---------------------+             +-------------------------------------------+   |
|   |  New State Emitted  |             | @Dependency(\.apiClient) var apiClient    |   |
|   +---------------------+             | - Async Stream / Task Execution           |   |
|                                       +---------------------+---------------------+   |
+-------------------------------------------------------------|-------------------------+
                                                              |
                                                              v
                                              [ External Systems / APIs ]
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Clean Architecture + Modern MVVM (`@Observable`)
* **Entity:** Model bisnis murni (`struct`, `Sendable`). Tidak mewarisi `NSObject` atau library persistence.
* **Domain Repository (Interface):** Kontrak abstraksi data. Mencegah Domain Layer mengetahui detail dari mana data berasal.
* **Use Case / Interactor:** Mengenkapsulasi satu alur kerja bisnis spesifik (Single Responsibility Principle). Mengeksekusi business rules dan memanggil repository.
* **ViewModel:** Bertindak sebagai state store untuk UI layer. Menggunakan Swift Observation Framework (`@Observable`) untuk meminimalkan re-evaluation tree pada SwiftUI.
* **Data Layer:** Berisi implementasi repository, network client, local cache, dan model DTO (*Data Transfer Object*).

### 2. The Composable Architecture (TCA)
* **State:** Tipe data (`struct`, `Equatable`) yang mendefinisikan seluruh variabel yang dibutuhkan UI untuk merender layar.
* **Action:** Enumerasi (`enum`) yang merepresentasikan semua kejadian interaksi pengguna, notifikasi sistem, atau callback asinkron.
* **Reducer:** Fungsi murni (`(inout State, Action) -> Effect<Action>`) yang mendeskripsikan bagaimana state berevolusi berdasarkan aksi, dan efek samping apa yang harus dieksekusi oleh runtime.
* **Effect:** Kontainer pembungkus operasi asinkron yang pada akhirnya dapat mengembalikan Action lain ke sistem atau selesai tanpa aksi (`.none`).
* **Store:** Runtime yang mengoordinasikan eksekusi Reducer, memegang state tunggal, dan mengelola pembatalan efek (*cancellation tokens*).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Batasan Memori dan Re-rendering pada SwiftUI
Sejak Swift 5.9, hadirnya macro `@Observable` menggantikan Combine-based `ObservableObject`.

```
SEBELUM (Combine - ObservableObject):
ObjectWillChangePublisher memancarkan sinyal SEBELUM properti berubah.
Setiap perubahan pada @Published property tunggal memicu re-evaluasi 
seluruh `body` dari View yang memegang @ObservedObject tersebut, 
terlepas apakah properti tersebut digunakan secara langsung di body atau tidak.

SESUDAH (Swift Observation - @Observable):
Tracking berbasis property-access graph secara granular.
View hanya mendaftar (subscribe) ke properti spesifik yang dibaca 
di dalam scope fungsi `body`.
Perubahan pada state `isLoading` TIDAK AKAN mengevaluasi ulang View 
jika View tersebut hanya membaca `items`.
```

### Pure Function vs Side-Effect pada TCA
TCA memisahkan mutasi status deterministik dari non-deterministik:
$$f: (\text{State}_t, \text{Action}) \to (\text{State}_{t+1}, \text{Effect})$$
Fungsi Reducer wajib bersifat deterministik murni. Jika input $\text{State}_t$ dan $\text{Action}$ identik, maka $\text{State}_{t+1}$ harus selalu identik secara mutlak, tanpa akses langsung ke jam sistem (`Date()`), generator angka acak (`UUID()`), atau jaringan (`URLSession`). Semua efek tersebut harus diinjeksikan via sistem `@Dependency`.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi murni Clean Architecture menggunakan modern Swift Concurrency:

```swift
import Foundation
import Observation

// MARK: - 1. Domain Entities (Core Business Model)
public struct TradingAccount: Identifiable, Equatable, Sendable {
    public let id: UUID
    public let balance: Decimal
    public let currency: String
    
    public init(id: UUID, balance: Decimal, currency: String) {
        self.id = id
        self.balance = balance
        self.currency = currency
    }
}

// MARK: - 2. Domain Repository Contract (DIP)
public protocol AccountRepositoryProtocol: Sendable {
    func fetchAccount(id: UUID) async throws -> TradingAccount
    func transferFunds(amount: Decimal, from: UUID, to: UUID) async throws
}

// MARK: - 3. Domain Use Case (Single Responsibility Principle)
public final class TransferFundsUseCase: Sendable {
    private let repository: AccountRepositoryProtocol
    
    public init(repository: AccountRepositoryProtocol) {
        self.repository = repository
    }
    
    public func execute(sourceAccountId: UUID, destinationAccountId: UUID, amount: Decimal) async throws {
        guard amount > 0 else {
            throw DomainError.invalidAmount
        }
        try await repository.transferFunds(amount: amount, from: sourceAccountId, to: destinationAccountId)
    }
    
    public enum DomainError: Error, LocalizedError {
        case invalidAmount
        public var errorDescription: String? {
            switch self {
            case .invalidAmount: return "Jumlah transfer harus lebih besar dari 0."
            }
        }
    }
}

// MARK: - 4. Presentation ViewModel (Modern @Observable)
@Observable
@MainActor
public final class AccountViewModel {
    public private(set) var account: TradingAccount?
    public private(set) var isLoading: Bool = false
    public private(set) var errorMessage: String?
    
    private let fetchAccountUseCase: @Sendable (UUID) async throws -> TradingAccount
    private let transferFundsUseCase: TransferFundsUseCase
    
    public init(
        fetchAccount: @escaping @Sendable (UUID) async throws -> TradingAccount,
        transferFundsUseCase: TransferFundsUseCase
    ) {
        self.fetchAccountUseCase = fetchAccount
        self.transferFundsUseCase = transferFundsUseCase
    }
    
    public func loadAccount(id: UUID) async {
        isLoading = true
        errorMessage = nil
        do {
            self.account = try await fetchAccountUseCase(id)
        } catch {
            self.errorMessage = error.localizedDescription
        }
        isLoading = false
    }
    
    public func transfer(amount: Decimal, to destination: UUID) async {
        guard let account = account else { return }
        isLoading = true
        do {
            try await transferFundsUseCase.execute(
                sourceAccountId: account.id,
                destinationAccountId: destination,
                amount: amount
            )
            // Reload data pasca transfer
            await loadAccount(id: account.id)
        } catch {
            self.errorMessage = error.localizedDescription
            isLoading = false
        }
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

1. **`TradingAccount: Sendable`**: Menjamin struktur data aman ditransfer antar-thread atau Swift Concurrency Tasks tanpa data racing.
2. **`protocol AccountRepositoryProtocol: Sendable`**: Abstraksi data layer. Ditandai `Sendable` agar instance yang mengimplementasikan protocol ini dapat dipanggil di dalam concurrent actor contexts secara aman.
3. **`public final class TransferFundsUseCase: Sendable`**: Use Case bersifat *immutable* dan *stateless*. Menyimpan referensi dependensi ke repository dan hanya memiliki satu fungsi operasional publik (`execute`).
4. **`guard amount > 0 else { throw DomainError.invalidAmount }`**: Business rule dieksekusi murni di domain layer, bukan divalidasi pada SwiftUI Form atau Controller.
5. **`@Observable @MainActor public final class AccountViewModel`**: 
   - `@Observable` mengeliminasi overhead Combine `AnyCancellable`.
   - `@MainActor` menggaransi seluruh mutasi UI state (`account`, `isLoading`, `errorMessage`) dieksekusi di Main Thread tanpa perlu memanggil `DispatchQueue.main.async`.
6. **`public private(set) var account: TradingAccount?`**: Enkapsulasi data yang ketat. View hanya dapat membaca (*read-only*), sedangkan mutasi (*write*) hanya dapat dilakukan melalui method internal ViewModel.

---

# SEKSI 09 — STUDI KASUS NYATA

### Enterprise Scenario: High-Frequency Crypto Portfolio Tracker
Sebuah aplikasi bursa kripto tier-1 melayani jutaan pengguna. Aplikasi ini memiliki fitur pemantauan portofolio dan eksekusi order kilat.

**Kendala Skala Besar:**
1. **WebSocket Ticker Spikes:** Update harga aset kripto masuk hingga 50 kali per detik per pasangan aset. Jika arsitektur menggunakan standard MVVM tanpa mitigasi, SwiftUI runtime akan mengalami *render thrashing*, mengakibatkan frame drops (di bawah 60/120 fps) dan konsumsi baterai ekstrem.
2. **Side-Effect Orchestration:** Pengguna dapat menekan tombol "Quick Sell". Aksi ini membutuhkan: otentikasi biometrik, pengambilan harga terkini via REST API, pengiriman signature cryptographic via gRPC, pembatalan langganan WebSocket secara temporer, dan pembaruan database lokal. Jika jaringan putus di tengah jalan, state harus di-*rollback* secara konsisten.

**Solusi Arsitektural:**
Mengimplementasikan **The Composable Architecture (TCA)** yang dikombinasikan dengan mekanisme *throttling/debouncing* native pada Effects, isolasi state orderbook, serta kontrol pembatalan (*cancellation lifecycle*) deterministik.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA

Berikut adalah implementasi skala enterprise menggunakan struktur arsitektur The Composable Architecture (TCA v1.x pattern manual / core mechanism):

```swift
import Foundation
import Combine

// MARK: - 1. Domain States & Models
public struct CryptoAsset: Identifiable, Equatable, Sendable {
    public let id: String
    public let symbol: String
    public var priceUSD: Decimal
    public var holdingQuantity: Decimal
    
    public var totalValue: Decimal {
        priceUSD * holdingQuantity
    }
}

public struct PortfolioState: Equatable, Sendable {
    public var assets: [CryptoAsset] = []
    public var isExecutingTrade: Bool = false
    public var errorMessage: String?
    public var tradeSuccessMessage: String?
    
    public var totalBalanceUSD: Decimal {
        assets.reduce(0) { $0 + $1.totalValue }
    }
}

// MARK: - 2. Domain Actions
public enum PortfolioAction: Equatable, Sendable {
    case onAppear
    case priceStreamReceived([String: Decimal])
    case executeQuickSell(assetId: String, quantity: Decimal)
    case tradeExecutionCompleted(Result<String, TradeError>)
    case dismissAlert
}

public enum TradeError: Error, Equatable, Sendable {
    case insufficientBalance
    case networkTimeout
    case signatureFailed
}

// MARK: - 3. Dependencies Abstraction (Environment Clients)
public struct PortfolioClient: Sendable {
    public var startPriceStream: @Sendable () -> AsyncStream<[String: Decimal]>
    public var executeTrade: @Sendable (_ assetId: String, _ quantity: Decimal) async throws -> String
}

// MARK: - 4. Reducer Core Engine
public struct PortfolioReducer: Sendable {
    private let client: PortfolioClient
    
    public init(client: PortfolioClient) {
        self.client = client
    }
    
    // Pure Reducer Function: Deterministik & Tanpa Side-Effect Langsung
    public func reduce(state: inout PortfolioState, action: PortfolioAction) -> Effect<PortfolioAction> {
        switch action {
        case .onAppear:
            return .run { send in
                // Membuka stream harga dan mendistribusikan action
                for await prices in self.client.startPriceStream() {
                    await send(.priceStreamReceived(prices))
                }
            }
            .cancellable(id: "PRICE_STREAM_ID", cancelInFlight: true)
            
        case let .priceStreamReceived(priceMap):
            for i in state.assets.indices {
                if let newPrice = priceMap[state.assets[i].symbol] {
                    state.assets[i].priceUSD = newPrice
                }
            }
            return .none
            
        case let .executeQuickSell(assetId, quantity):
            guard let asset = state.assets.first(where: { $0.id == assetId }),
                  asset.holdingQuantity >= quantity else {
                state.errorMessage = "Saldo aset tidak mencukupi untuk order ini."
                return .none
            }
            
            state.isExecutingTrade = true
            state.errorMessage = nil
            
            return .run { send in
                do {
                    let txHash = try await self.client.executeTrade(assetId, quantity)
                    await send(.tradeExecutionCompleted(.success(txHash)))
                } catch let error as TradeError {
                    await send(.tradeExecutionCompleted(.failure(error)))
                } catch {
                    await send(.tradeExecutionCompleted(.failure(.networkTimeout)))
                }
            }
            
        case let .tradeExecutionCompleted(.success(txHash)):
            state.isExecutingTrade = false
            state.tradeSuccessMessage = "Transaksi Berhasil! TxHash: \(txHash)"
            return .none
            
        case let .tradeExecutionCompleted(.failure(error)):
            state.isExecutingTrade = false
            switch error {
            case .insufficientBalance:
                state.errorMessage = "Transaksi Ditolak: Saldo Tidak Mencukupi."
            case .networkTimeout:
                state.errorMessage = "Koneksi Bermasalah. Silakan Coba Lagi."
            case .signatureFailed:
                state.errorMessage = "Gagal Menandatangani Transaksi Kripto."
            }
            return .none
            
        case .dismissAlert:
            state.errorMessage = nil
            state.tradeSuccessMessage = nil
            return .none
        }
    }
}

// MARK: - 5. Lightweight Production Effect Implementation
public struct Effect<Action: Sendable>: Sendable {
    public typealias Operation = @Sendable (@escaping @Sendable (Action) async -> Void) async -> Void
    private let operation: Operation?
    
    public init(operation: Operation?) {
        self.operation = operation
    }
    
    public static var none: Effect<Action> {
        Effect(operation: nil)
    }
    
    public static func run(operation: @escaping Operation) -> Effect<Action> {
        Effect(operation: operation)
    }
    
    public func execute(send: @escaping @Sendable (Action) async -> Void) async {
        if let operation = self.operation {
            await operation(send)
        }
    }
    
    public func cancellable(id: String, cancelInFlight: Bool) -> Effect<Action> {
        // Implementasi integrasi lifecycle token cancellation
        return self
    }
}

// MARK: - 6. Architectural Store Core (Actor-Isolated Runtime)
@MainActor
@Observable
public final class Store<State: Equatable & Sendable, Action: Sendable> {
    public private(set) var state: State
    private let reducer: @Sendable (inout State, Action) -> Effect<Action>
    private var runningTasks: [Task<Void, Never>] = []
    
    public init(
        initialState: State,
        reducer: @escaping @Sendable (inout State, Action) -> Effect<Action>
    ) {
        self.state = initialState
        self.reducer = reducer
    }
    
    public func send(_ action: Action) {
        let effect = reducer(&self.state, action)
        
        let task = Task { [weak self] in
            await effect.execute { nextAction in
                Task { @MainActor [weak self] in
                    self?.send(nextAction)
                }
            }
        }
        runningTasks.append(task)
    }
    
    deinit {
        runningTasks.forEach { $0.cancel() }
    }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Evaluasi | Vanilla MVVM | Clean Architecture + MVVM | The Composable Architecture (TCA) |
| :--- | :--- | :--- | :--- |
| **Learning Curve** | Rendah (Mudah diadopsi junior) | Menengah (Memerlukan pemahaman DIP) | Sangat Tinggi (Mental model fungsional/UDF) |
| **Boilerplate Code** | Sangat Rendah | Sedang (Protocols, UseCases, Repos) | Tinggi (State, Actions, Reducer scoping) |
| **Determinisme State** | Rendah (Bisa race condition) | Menengah (Tergantung disiplin engineer) | Mutlak (Pure Functions & Single Store) |
| **Testability** | Sedang (Mocking ViewModel rumit) | Tinggi (Unit test isolated per UseCase) | Sempurna (Built-in Step-by-Step TestStore) |
| **Compile-time Safety** | Rendah | Sedang | Sangat Tinggi (Semua event tercakup dalam enum) |
| **Waktu Kompilasi** | Paling Cepat | Cepat | Cenderung Lambat (Eksploitasi macro & compiler) |
| **Cocok Untuk** | Prototype, CRUD, Tim Kecil (<4) | Enterprise Skala Sedang-Besar (5-20) | Ekosistem Skala Sangat Besar (>20 engineers) |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. State Mutation Re-entrancy pada Async/Await
* **Kasus Kegagalan:** Ketika action asinkron sedang berjalan, pengguna menekan tombol berulang kali sehingga dua async block memodifikasi properti state yang sama secara interleaving.
* **Mitigasi:** Pasang status eksplisit (seperti `isExecutingTrade`) untuk mencegah event re-trigger, atau gunakan structured concurrency `.cancellable(id:cancelInFlight: true)` untuk membatalkan Task sebelumnya saat task baru diinisiasi.

### 2. High-Frequency Rendering Thrashing
* **Kasus Kegagalan:** WebSocket mengirimkan perbaruan state 100x/detik. ViewModel yang menempel pada View akan memicu render ulang SwiftUI terus-menerus, menyebabkan frame rate turun hingga 15 FPS.
* **Mitigasi:** Terapkan layer `Buffer/Throttle` sebelum state dikirim ke UI Store. Gunakan AsyncAlgorithms library (`prices.debounce(for: .milliseconds(250))`).

### 3. Zombie Asynchronous Tasks pada Navigasi Layar
* **Kasus Kegagalan:** View sudah di-*pop* dari NavigationStack, tetapi UseCase atau Task ViewModel masih mengunduh data besar di memori background, membuang bandwidth dan baterai.
* **Mitigasi:** Ikat siklus hidup Task dengan View lifecycle melalui modifier `.task {}` di SwiftUI, yang secara otomatis memicu `Task.cancel()` saat View mengalami deallocation.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Membocorkan UI Framework ke Domain Layer
```swift
// BURUK: Domain Entity mengimpor SwiftUI
import SwiftUI

public struct ProductItem {
    public let id: String
    public let color: Color // PELANGGARAN: Domain layer terkontaminasi Framework UI!
}

// BENAR: Menggunakan Hex string atau Token Representasi Domain
public struct ProductItem: Sendable {
    public let id: String
    public let colorHex: String // Murni, bebas dependensi UI
}
```

### 2. Memanggil Async Side-Effect Langsung di dalam TCA Reducer
```swift
// BURUK: Melakukan network call di dalam body Reducer
case .buttonTapped:
    state.isLoading = true
    let data = try await network.fetch() // PELANGGARAN: Reducer harus berupa Pure Function!
    return .none

// BENAR: Kembalikan Effect asinkron
case .buttonTapped:
    state.isLoading = true
    return .run { send in
        let result = await TaskResult { try await network.fetch() }
        await send(.dataResponse(result))
    }
```

### 3. Over-Observing Mega-Objects
Mengekspos seluruh model database ke UI menyebabkan View me-render ulang setiap kali kolom mana pun (bahkan yang tidak terlihat di UI) diperbarui. **Solusi:** Buat `ViewState` representasional yang spesifik (*View-tailored model*) dan ramping.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Feature Scoping / Modularization:** Pisahkan modul secara fisik menggunakan Swift Package Manager (SPM).
   * `FeatureProfileDomain` (Hanya Entity & UseCase)
   * `FeatureProfileData` (Repository Impl, Networking, CoreData)
   * `FeatureProfileUI` (SwiftUI & ViewModel / Reducer)
2. **Explicit Dependency Injection:** Dilarang keras menggunakan Singleton `MyService.shared` di dalam UseCase atau Reducer. Wajib menggunakan initializer injection atau TCA Environment Injection.
3. **Immutability by Default:** Semua model data wajib berupa `struct` dengan deklarasi `let`. Mutasi hanya diperbolehkan melalui salinan mutasi eksplisit (`mutating func` atau copy-on-write).
4. **Actor Boundary Isolation:** Semua logic formatting, rendering, dan penyiapan data akhir untuk visualisasi View wajib diisolasi ke dalam `@MainActor`. Operasi komputasi kriptografi, parsing JSON, atau DB read/write wajib dieksekusi di global worker actor background.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Mengurangi View Redraw Tree Menggunakan Equatable & State Projection
Pada SwiftUI, jika Anda memecah tampilan layar besar menjadi beberapa sub-views, pastikan sub-views hanya menerima nilai primitif yang dibutuhkan, bukan keseluruhan ViewModel.

```swift
// Hindari passing mega ViewModel ke child view:
struct TransactionRowView: View {
    let transaction: CryptoTransaction // Pass data terisolasi & Equatable
    
    var body: some View {
        HStack {
            Text(transaction.title)
            Spacer()
            Text(transaction.amountFormatted)
        }
    }
}
```

### Swift Concurrency Task Cancellation Co-operation
Di dalam UseCase atau Reducer Effect yang menjalankan komputasi berat (misalnya kalkulasi indikator teknikal portofolio), selalu periksa status pembatalan Task secara manual:

```swift
public func calculateHeavyPortfolioYield(history: [Snapshot]) throws -> YieldMetrics {
    for snapshot in history {
        // Cek kooperatif secara periodik
        try Task.checkCancellation()
        // Lakukan pemrosesan
    }
    return YieldMetrics(...)
}
```

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. In-Memory Sensitive State Zeroing
Data keuangan seperti PIN, Private Keys, atau Nilai Portofolio sensitif tidak boleh dibiarkan menetap di memori heap saat layar berpindah ke background.

```swift
public struct SensitiveVaultState: Equatable, Sendable {
    private(set) var pinBuffer: [UInt8] = []
    
    public mutating func appendDigit(_ digit: UInt8) {
        pinBuffer.append(digit)
    }
    
    public mutating func wipe() {
        // Overwrite memori sebelum dibebaskan
        for i in 0..<pinBuffer.count {
            pinBuffer[i] = 0
        }
        pinBuffer.removeAll()
    }
}
```

### 2. Jailbreak Detection Integrity Gate
Pada Clean Architecture, isolasi pemeriksaan integritas perangkat ke dalam *Domain Security Interactor* yang dieksekusi sebelum modul transfer/portofolio diinisialisasi:
* Deteksi path terlarang: `/Applications/Cydia.app`, `/bin/sh`, `/usr/sbin/sshd`.
* Validasi *dynamic library injection* menggunakan `dyld_get_image_name`.

---

# SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Pada arsitektur berbasis aksi seperti UDF / TCA, observabilitas dapat diimplementasikan secara otomatis menggunakan **Higher-Order Reducer** untuk mencatat (*logging*) seluruh alur aplikasi:

```swift
extension PortfolioReducer {
    public func logging() -> Self {
        return PortfolioReducer(client: self.client) { state, action in
            #if DEBUG
            let start = DispatchTime.now()
            print("[ACTION RECEIVED]: \(action)")
            #endif
            
            let effect = self.reduce(state: &state, action: action)
            
            #if DEBUG
            let end = DispatchTime.now()
            let nanoTime = end.uptimeNanoseconds - start.uptimeNanoseconds
            let timeInterval = Double(nanoTime) / 1_000_000
            print("[STATE MUTATED]: \(state)")
            print("[EXECUTION TIME]: \(timeInterval) ms")
            #endif
            
            return effect
        }
    }
}
```

Jika terjadi crash di sisi client produksi, jejak *Time-Travel Log* yang berisi 10 Action terakhir dapat dikirimkan langsung ke Sentry atau Datadog untuk merekonstruksi bug secara presisi di local testing.

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Clean Architecture:** Domain berada di tengah, tidak mengetahui siapa presenternya (SwiftUI/UIKit) atau siapa penyedia datanya (URLSession/CoreData). Dependency mengalir **ke dalam** (*inward*).
* **MVVM Modern:** Gunakan `@Observable` (Swift Observation). Isolasi kelas dengan `@MainActor`. ViewModel hanya memanggil UseCase dan menyediakan properti siap render.
* **TCA:** Arsitektur UDF murni berbasis fungsional:
  * Mutasi state hanya melalui `(inout State, Action) -> Effect<Action>`.
  * Seluruh dependensi berada di environment wrapper `@Dependency`.
  * Determinisme mutlak mempermudah unit testing modular.
* **Kapan Menggunakan Apa?**
  * Pilih **Clean Architecture + MVVM** jika tim Anda didominasi oleh engineer yang terbiasa dengan standard OOP, modularisasi modular berbasis Clean Code, dan ingin menghindari dependensi framework pihak ketiga.
  * Pilih **TCA** jika aplikasi memiliki kompleksitas state flow multi-layar, state sharing global, membutuhkan time-travel debugging, dan memerlukan reliabilitas 100% testable logic.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Mengapa dalam Clean Architecture, Domain Layer dilarang melakukan `import SwiftUI` atau `import CoreData`?
* A. Karena library tersebut membuat ukuran binary aplikasi membengkak secara drastis.
* B. Agar business logic tidak terikat pada framework eksternal, sehingga mudah diuji secara independen dan tahan terhadap perubahan implementasi UI atau Database.
* C. Karena SwiftUI tidak mendukung Swift Concurrency dan Sendable protocols.
* D. Agar compilation time berkurang hingga tepat 50%.

### Soal 2
Apa perbedaan internal fundamental antara ViewModel yang menggunakan `@Observable` (Swift 5.9+) dibandingkan `ObservableObject` (Combine)?
* A. `@Observable` berjalan di background thread secara default, sedangkan `ObservableObject` berjalan di main thread.
* B. `@Observable` melacak akses properti secara spesifik; View hanya merender ulang jika properti yang dibaca di dalam `body` berubah, bukan setiap kali sembarang properti ViewModel dimutasi.
* C. `ObservableObject` menggunakan Actor, sedangkan `@Observable` menggunakan generic Struct.
* D. `@Observable` mengharuskan seluruh properti dideklarasikan menggunakan wrapper `@Published`.

### Soal 3
Dalam The Composable Architecture (TCA), fungsi Reducer didefinisikan sebagai fungsi murni (*pure function*). Manakah dari operasi berikut yang **TIDAK BOLEH** dilakukan secara langsung di dalam Reducer body?
* A. Mengubah nilai string pada `state.errorMessage = "Gagal"`.
* B. Mengiterasi daftar `state.assets` dan memfilter elemennya.
* C. Menjalankan `state.timestamp = Date()` atau memanggil `URLSession.shared.data(from: url)`.
* D. Mengembalikan `.none` jika action tidak memerlukan efek samping lanjutan.

### Soal 4
Bagaimana cara terbaik mencegah fenomena *Zombie Task* (task asinkron yang tetap berjalan setelah layar di-dismiss) pada SwiftUI modern?
* A. Menggunakan modifier `.onAppear` dan memanggil `DispatchQueue.global().async`.
* B. Menggunakan modifier `.task {}` yang terikat pada View lifecycle, atau membatalkan `Task` secara eksplisit saat deinitialization.
* C. Menambahkan retain cycle sengaja menggunakan strong reference.
* D. Melakukan restart pada aplikasi setiap kali berpindah view.

### Soal 5
Pada situasi apa TCA memiliki kelemahan signifikan dibandingkan Clean MVVM standar?
* A. Saat aplikasi membutuhkan unit testing yang komprehensif.
* B. Saat aplikasi memiliki state yang sangat kompleks antar child-parent.
* C. Pada compile-time build overhead, kurva belajar tim pemula, dan dependensi terhadap library eksternal.
* D. Saat aplikasi menggunakan Swift Concurrency.

---

### Kunci Jawaban & Analisis Evaluasi
1. **Jawaban: B** — Inti dari *Hexagonal / Clean Architecture* adalah *Dependency Inversion*. Domain adalah inti bisnis aplikasi Anda; ia tidak boleh mengetahui bagaimana data disimpan (CoreData/Realm) atau bagaimana ia dirender (SwiftUI/UIKit).
2. **Jawaban: B** — `ObservableObject` membunyikan `objectWillChange` global yang memicu evaluasi ulang view secara luas. `@Observable` menggunakan observasi berbasis *property-tracking* granular.
3. **Jawaban: C** — `Date()` menghasilkan waktu non-deterministik dan `URLSession` adalah asynchronous I/O side-effect. Operasi non-deterministik harus dialihkan keluar Reducer melalui `Effect` via injected