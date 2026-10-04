# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 03-Frontend-and-Mobile | **Topik:** iOS | **Bab 01:** Fondasi dan Arsitektur

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, *Senior Mobile Software Engineer* diharapkan mampu:

1. **Menganalisis Internal Runtime & Memori iOS**: Membedah mekanisme *Dynamic vs Static Dispatch*, manipulasi *Witness Table*, *Side Table* pada *Automatic Reference Counting* (ARC), serta siklus hidup memori objek Swift hingga ke tingkat representasi biner.
2. **Mengimplementasikan Swift Concurrency Tingkat Lanjut**: Menguasai semantik *Structured Concurrency*, mitigasi *Actor Reentrancy*, *Custom Executors*, dan kepatuhan penuh terhadap *Swift 6 Data-Race Safety* (`Complete Concurrency Checking`).
3. **Merancang Arsitektur Modular Skala Enterprise**: Menerapkan arsitektur *Clean Swift / VIPER* berbasis modularisasi *Swift Package Manager* (SPM) atau *Tuist* dengan pemisahan dependensi ketat melalui *Inversion of Control* (IoC) dan *Composition Root Pattern*.
4. **Mendeteksi dan Memitigasi Masalah Kinerja Produksi**: Mengidentifikasi *retain cycles*, *memory footprint spikes*, *concurrency deadlocks*, dan *main thread hitching* menggunakan *Xcode Instruments* (*Time Profiler*, *Allocations*, *Leaks*).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Swift Foundations**: Pemahaman kuat terhadap *Value Type* (`struct`, `enum`) vs *Reference Type* (`class`), serta *Generics* tingkat lanjut.
- **Fundamental Concurrency**: Pengalaman praktis menggunakan `DispatchQueue` (GCD), `OperationQueue`, serta pengenalan dasar sintaks `async/await`.
- **Dasar Arsitektur UI**: Pemahaman mendalam terkait siklus hidup *UIKit* (`UIViewController`) dan *SwiftUI* (`View`), serta pola arsitektur MVVM dasar.
- **Sistem *Build* iOS**: Pemahaman dasar mengenai cara kerja *Xcode project scheme*, *frameworks*, dan *dynamic vs static linking*.

---

## 3. Concept & Internal Architecture

### 3.1 Swift Runtime: Method Dispatch & Memory Layout

Swift tidak menggunakan satu mekanisme pemanggilan fungsi tunggal. Runtime mengombinasikan tiga strategi *method dispatch* berdasarkan konteks deklarasi dan optimasi kompiler:

```
+-------------------+---------------------------+---------------------------------+
| Dispatch Type     | Kapan Digunakan           | Cost / Overhead                 |
+-------------------+---------------------------+---------------------------------+
| Static / Direct   | struct, enum, final class,| O(1) inline, nol overhead       |
|                   | extension (tanpa @objc)   | runtime. Memungkinkan inline.   |
+-------------------+---------------------------+---------------------------------+
| Table (V-Table /  | class methods, protocol   | O(1) pointer dereference        |
| Witness Table)    | conformance methods       | (Offset lookups via table).     |
+-------------------+---------------------------+---------------------------------+
| Message Dispatch  | @objc dynamic, NSObject   | O(log N) cache search ->        |
| (Objective-C Run) | subclasses, KVO/swizzling | slow path lookup. Sangat dinamis|
+-------------------+---------------------------+---------------------------------+
```

#### Memory Side Tables & ARC Mechanics
Setiap *heap object* di Swift memiliki alokasi *header* 16-byte (pada arsitektur 64-bit: 8 byte untuk *isa/metadata pointer*, 8 byte untuk *inline reference counts*). 

Struktur 64-bit *inline reference count* membagi *bits* untuk *Pure Strong Reference Count*, *Unowned Reference Count*, dan flag `USE_SIDE_TABLE`.

```
Representasi 64-bit Heap Object Header:
[ Metadata Pointer (64-bit) ]
[ Inline Ref Counts (64-bit) ] 
       |
       +---> [ Strong Bits | Unowned Bits | Side Table Flag | Pin/Dealloc Flags ]
```

Ketika kondisi berikut terpenuhi:
1. Strong reference count melampaui batas representasi *inline bit field*.
2. Objek memiliki *Weak Reference* pertama yang mereferensikannya.

Runtime mengekstrak ref count ke struktur terpisah bernama **HeapObjectSideTableEntry**.

```
[ Heap Object ] 
   Metadata Pointer 
   Side Table Pointer -------> [ HeapObjectSideTableEntry ]
                                  Strong Ref Count (64-bit)
                                  Unowned Ref Count (32-bit)
                                  Weak Ref Count (32-bit)
                                  Pointer back to Object
```

*Weak reference* di Swift tidak menunjuk langsung ke objek, melainkan menunjuk ke **Side Table**. Ketika strong ref count mencapai 0, objek langsung masuk fase *Deallocated*, tetapi memori *Side Table* tetap hidup sampai seluruh *weak references* hancur. Ini mencegah *dangling pointer* secara deterministik tanpa memerlukan penguncian global pada saat dereference.

### 3.2 Swift Concurrency Runtime Engine

Model konkurensi modern Swift tidak memetakan satu *Task* ke satu *OS Thread* secara 1:1. Swift Concurrency didesain di atas **Cooperative Thread Pool**:
- Pool thread dibatasi maksimal sebanyak jumlah inti CPU logical (`sysctl hw.logicalcpu`).
- **Cooperative Scheduling**: Saat thread mencapai titik penangguhan (`await`), eksekusi fungsi di-*suspend*, context state dikemas dalam heap-allocated *Continuation*, dan thread OS tersebut dibebaskan secara kooperatif untuk mengeksekusi task lain yang siap (*continuation stealing*).
- **Actor Isolation**: Actor melindungi mutasi state internal melalui antrean eksekusi pesan secara serial (*actor mailbox*). Setiap akses properti mutable actor dari luar konteks isolasinya dipaksa menggunakan `await`.

#### Actor Reentrancy (Bahaya Tersembunyi)
Actor menjamin eksklusivitas eksekusi: hanya satu thread yang dapat mengakses state mutable-nya pada satu waktu. **Namun, Actor TIDAK menjamin atomisitas lintas titik `await`.** Ketika sebuah task di dalam actor menemui `await`, task tersebut disuspend, dan thread actor bebas mengeksekusi pesan lain dari mailbox. State actor dapat berubah sebelum kelanjutan task pertama dieksekusi.

---

## 4. Why & What

### Mengapa Membutuhkan Arsitektur Produksi Khusus?

Pola arsitektur standar seperti MVC atau Vanilla MVVM sering gagal pada aplikasi mobile enterprise skala besar karena:
1. **Massive View Controller / God ViewModel**: ViewModel menangani routing, state presentation, validasi data, *caching*, dan network request sekaligus.
2. **Coupling Module**: Fitur A mengimpor modul Fitur B secara langsung. Mengubah Fitur B memicu kompilasi ulang seluruh aplikasi (*broken incremental build*).
3. **Data-Race Bugs**: Mutasi data lintas thread di latar belakang mengakibatkan *crash* acak (`EXC_BAD_ACCESS`) yang sulit direproduksi di lingkungan testing lokal.

### Apa Solusinya?

Penerapan **Modular Clean Swift / VIPER** terisolasi yang dipadukan dengan **Strict Concurrency (Swift 6)**:
- **Clean Separation of Concerns**: View hanya merender tampilan; Presenter memformat data untuk presentasi; Interactor memproses *business logic*; Worker menangani infrastruktur data (*Network/Persistence*).
- **Loose Coupling via Dependency Inversion**: Modul hanya bergantung pada antarmuka domain (*Protocols*), bukan implementasi konkret.
- **Composition Root**: Instansiasi dependensi dilakukan di tepi aplikasi (*Application Boundary*), bukan di dalam modul fitur itu sendiri.

---

## 5. How (Workflow Detail)

Alur transmisi data dan kontrol dalam satu siklus interaksi pengguna:

```
[ User Interaction ] 
        |
        v
    [ View ] (SwiftUI / UIViewController)
        |
        | Memanggil Event Intent (e.g., `didTapPayButton()`)
        v
 [ Interactor ] (Domain Logic Boundary)
        |
        | Melakukan kalkulasi, validasi state
        +---> [ Worker / Repository (Data Layer) ]
        |            | (Network / CoreData / SwiftData via Actor)
        |            v
        |<--- [ Return Decoupled Domain Entity ]
        |
        | Mengirim Domain Entity (Bukan DTO / DB Model)
        v
  [ Presenter ] (Presentation Logic Boundary)
        |
        | Melakukan pemformatan (Currency formatting, localization, UI mapping)
        v
    [ View ] (Menerima ViewModel/ViewState primitives: String, Color, Bool)
        |
        | (Jika navigasi diperlukan)
        v
    [ Router / Coordinator ] (Navigation Boundary)
```

---

## 6. Analogy & Diagram ASCII

### Analogi Restoran Bintang Lima untuk VIPER
- **View**: *Waiter/Pramusaji*. Menerima pesanan dari pelanggan, menyajikan makanan di piring. Tidak boleh memasak, tidak boleh menghitung harga diskon.
- **Presenter**: *Food Stylist / Maitre d'*. Mengambil hasil masakan dari dapur, menghiasnya agar siap dinikmati pelanggan, dan memberikannya ke Waiter.
- **Interactor**: *Executive Chef*. Mengolah resep, memeriksa ketersediaan bahan, memproses logika masakan. Tidak peduli makanan disajikan dengan piring porselen atau mangkuk kertas.
- **Worker/Repository**: *Supplier Bahan Baku*. Memasok bahan segar dari gudang pendingin (Cache/Database) atau pasar luar (API Network).
- **Router/Coordinator**: *Hostess/Floor Manager*. Memandu tamu dari pintu depan, ke meja makan, atau ke ruang VIP.

### Diagram Arsitektur Modular Skala Enterprise

```
                               +-----------------------------+
                               |     App Target (Assembly)   |
                               +--------------+--------------+
                                              |
                   +--------------------------+--------------------------+
                   | Linkage                                             | Linkage
                   v                                                     v
       +-----------------------+                             +-----------------------+
       |   Feature: Payment    |                             |    Feature: Account   |
       +-----------+-----------+                             +-----------+-----------+
                   |                                                     |
                   | Implements protocols                                | Implements protocols
                   v                                                     v
       +-----------------------+                             +-----------------------+
       | PaymentDomainProtocol |                             | AccountDomainProtocol |
       +-----------+-----------+                             +-----------+-----------+
                   ^                                                     ^
                   | Depends on Core Interfaces                          | Depends on Core Interfaces
                   +--------------------------+--------------------------+
                                              |
                                              |
                               +--------------+--------------+
                               |      CoreNetworkKit         |
                               |  (Actors, HttpClient, Auth) |
                               +--------------+--------------+
                                              |
                               +--------------+--------------+
                               |       CoreStorageKit        |
                               | (Keychain, Database Engine) |
                               +-----------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Mitigasi Actor Reentrancy

Berikut adalah contoh masalah *Actor Reentrancy* dan solusinya menggunakan *Generation ID Token Pattern*.

```swift
import Foundation

// MASALAH: Actor Reentrancy Bug
actor UnsafeImageCache {
    private var cache: [URL: Data] = [:]
    
    func loadImage(from url: URL) async throws -> Data {
        if let cached = cache[url] {
            return cached
        }
        
        // SUSPENSION POINT: Lock dilepas! Task lain bisa request URL yang sama secara paralel.
        let (data, _) = try await URLSession.shared.data(from: url)
        
        // State mutasi setelah resume: Redundant download dan overwriting
        cache[url] = data
        return data
    }
}

// SOLUSI: Atomic In-Flight Task Tracking
actor SafeImageCache {
    private enum CacheEntry {
        case inProgress(Task<Data, Error>)
        case ready(Data)
    }
    
    private var entries: [URL: CacheEntry] = [:]
    
    func loadImage(from url: URL) async throws -> Data {
        if let entry = entries[url] {
            switch entry {
            case .ready(let data):
                return data
            case .inProgress(let task):
                return try await task.value
            }
        }
        
        let downloadTask = Task<Data, Error> {
            let (data, _) = try await URLSession.shared.data(from: url)
            return data
        }
        
        entries[url] = .inProgress(downloadTask)
        
        do {
            let result = try await downloadTask.value
            entries[url] = .ready(result)
            return result
        } catch {
            entries.removeValue(forKey: url)
            throw error
        }
    }
}
```

### 7.2 Practical Example: Enterprise Modular Clean Swift Architecture

Implementasi transfer dana (*Fund Transfer*) dengan prinsip *Strict Concurrency* (`Swift 6 ready`), *Inversion of Control*, dan *Boundary Isolation*.

#### A. Domain Contracts (Pure Abstractions)
```swift
// File: PaymentDomainContracts.swift
import Foundation

public struct Money: Sendable, Equatable {
    public let amount: Decimal
    public let currency: String
    
    public init(amount: Decimal, currency: String) {
        self.amount = amount
        self.currency = currency
    }
}

public struct TransferRequest: Sendable {
    public let recipientAccountID: String
    public let funds: Money
    public let idempotencyKey: UUID
    
    public init(recipientAccountID: String, funds: Money, idempotencyKey: UUID = UUID()) {
        self.recipientAccountID = recipientAccountID
        self.funds = funds
        self.idempotencyKey = idempotencyKey
    }
}

public struct TransferReceipt: Sendable, Equatable {
    public let transactionID: String
    public let timestamp: Date
    public let status: String
}

public enum PaymentError: Error, Sendable, Equatable {
    case insufficientFunds
    case networkFailure(String)
    case invalidRecipient
}

public protocol TransferRepositoryProtocol: Sendable {
    func executeTransfer(_ request: TransferRequest) async throws -> TransferReceipt
}

public protocol TransferInteractorInputProtocol: Sendable {
    func initiateTransfer(recipientID: String, amount: Decimal, currency: String) async
}

public protocol TransferPresenterInputProtocol: Sendable {
    func presentTransferSuccess(_ receipt: TransferReceipt) async
    func presentTransferFailure(_ error: PaymentError) async
    func presentLoadingState(isLoading: Bool) async
}

@MainActor
public protocol TransferViewProtocol: AnyObject {
    func display(state: TransferViewState)
}

public enum TransferViewState: Equatable {
    case idle
    case loading
    case success(message: String)
    case error(message: String)
}
```

#### B. Repository Implementation (Infrastructure Worker Layer)
```swift
// File: TransferRepository.swift
import Foundation

public actor TransferRepository: TransferRepositoryProtocol {
    private let session: URLSession
    private let baseURL: URL
    
    public init(session: URLSession = .shared, baseURL: URL) {
        self.session = session
        self.baseURL = baseURL
    }
    
    public func executeTransfer(_ request: TransferRequest) async throws -> TransferReceipt {
        let endpoint = baseURL.appendingPathComponent("/api/v1/transfers")
        var urlRequest = URLRequest(url: endpoint)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.setValue(request.idempotencyKey.uuidString, forHTTPHeaderField: "X-Idempotency-Key")
        
        let payload: [String: Any] = [
            "recipient": request.recipientAccountID,
            "amount": NSDecimalNumber(decimal: request.funds.amount).doubleValue,
            "currency": request.funds.currency
        ]
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: payload)
        
        do {
            let (data, response) = try await session.data(for: urlRequest)
            guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
                throw PaymentError.networkFailure("Server returned invalid response")
            }
            
            // Parsing output
            guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let txnId = json["transaction_id"] as? String else {
                throw PaymentError.networkFailure("Malformed response body")
            }
            
            return TransferReceipt(transactionID: txnId, timestamp: Date(), status: "COMPLETED")
        } catch let err as PaymentError {
            throw err
        } catch {
            throw PaymentError.networkFailure(error.localizedDescription)
        }
    }
}
```

#### C. Interactor Layer (Domain Business Logic)
```swift
// File: TransferInteractor.swift
import Foundation

public final class TransferInteractor: TransferInteractorInputProtocol {
    private let repository: TransferRepositoryProtocol
    private let presenter: TransferPresenterInputProtocol
    
    public init(repository: TransferRepositoryProtocol, presenter: TransferPresenterInputProtocol) {
        self.repository = repository
        self.presenter = presenter
    }
    
    public func initiateTransfer(recipientID: String, amount: Decimal, currency: String) async {
        await presenter.presentLoadingState(isLoading: true)
        
        // Validasi domain murni
        guard amount > 0 else {
            await presenter.presentLoadingState(isLoading: false)
            await presenter.presentTransferFailure(.insufficientFunds)
            return
        }
        
        guard !recipientID.trimmingCharacters(in: .whitespaces).isEmpty else {
            await presenter.presentLoadingState(isLoading: false)
            await presenter.presentTransferFailure(.invalidRecipient)
            return
        }
        
        let request = TransferRequest(
            recipientAccountID: recipientID,
            funds: Money(amount: amount, currency: currency)
        )
        
        do {
            let receipt = try await repository.executeTransfer(request)
            await presenter.presentLoadingState(isLoading: false)
            await presenter.presentTransferSuccess(receipt)
        } catch let error as PaymentError {
            await presenter.presentLoadingState(isLoading: false)
            await presenter.presentTransferFailure(error)
        } catch {
            await presenter.presentLoadingState(isLoading: false)
            await presenter.presentTransferFailure(.networkFailure(error.localizedDescription))
        }
    }
}
```

#### D. Presenter Layer (UI Formatting Logic)
```swift
// File: TransferPresenter.swift
import Foundation

public final class TransferPresenter: TransferPresenterInputProtocol {
    // Weak reference untuk mencegah retain cycle; MainActor diisolasi ke View
    public weak var view: TransferViewProtocol?
    
    public init() {}
    
    public func presentLoadingState(isLoading: Bool) async {
        await MainActor.run {
            if isLoading {
                self.view?.display(state: .loading)
            } else {
                self.view?.display(state: .idle)
            }
        }
    }
    
    public func presentTransferSuccess(_ receipt: TransferReceipt) async {
        let formattedMessage = "Berhasil mentransfer! No. Referensi: \(receipt.transactionID)"
        await MainActor.run {
            self.view?.display(state: .success(message: formattedMessage))
        }
    }
    
    public func presentTransferFailure(_ error: PaymentError) async {
        let localizedError: String
        switch error {
        case .insufficientFunds:
            localizedError = "Saldo Anda tidak mencukupi untuk melakukan transaksi."
        case .invalidRecipient:
            localizedError = "Nomor rekening tujuan tidak valid."
        case .networkFailure(let details):
            localizedError = "Gangguan koneksi: \(details)"
        }
        
        await MainActor.run {
            self.view?.display(state: .error(message: localizedError))
        }
    }
}
```

#### E. View & Composition Root (Assembly Layer)
```swift
// File: TransferModuleAssembly.swift
import UIKit

@MainActor
public final class TransferViewController: UIViewController, TransferViewProtocol {
    private var interactor: TransferInteractorInputProtocol?
    
    public func inject(interactor: TransferInteractorInputProtocol) {
        self.interactor = interactor
    }
    
    public override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
    }
    
    public func onPayButtonTapped(recipient: String, amount: Decimal) {
        Task {
            await interactor?.initiateTransfer(recipientID: recipient, amount: amount, currency: "IDR")
        }
    }
    
    public func display(state: TransferViewState) {
        switch state {
        case .idle:
            print("[UI State] Idle")
        case .loading:
            print("[UI State] Loading Spinner Visible")
        case .success(let message):
            print("[UI State] Show Alert Success: \(message)")
        case .error(let message):
            print("[UI State] Show Error Banner: \(message)")
        }
    }
}

// Composition Root
public enum TransferModuleAssembly {
    @MainActor
    public static func build(apiBaseURL: URL) -> UIViewController {
        let view = TransferViewController()
        let presenter = TransferPresenter()
        let repository = TransferRepository(baseURL: apiBaseURL)
        let interactor = TransferInteractor(repository: repository, presenter: presenter)
        
        view.inject(interactor: interactor)
        presenter.view = view
        
        return view
    }
}
```

---

## 8. Real World Case Study: Arsitektur SuperApp FinTech

### Masalah
Sebuah SuperApp FinTech dengan 60+ modul SPM, 70 engineer, dan basis kode 1.2 juta baris mengalami:
1. **Waktu Clean Build CI/CD Membengkak**: Mencapai 42 menit per build karena dependensi siklis antar modul.
2. **Main Thread Hangs**: Penurunan framerate drastis (< 30 fps) saat rendering histori transaksi berukuran ribuan entitas di layar *Home*.
3. **Ghost Memory Leaks**: Konsumsi RAM melonjak hingga 450MB setelah 15 menit navigasi terus menerus, memicu *Jetsam Event* (OS terminate app paksa di background).

### Solusi Arsitektur
1. **Micro-Features Architecture & Protocol Modules**:
   - Memecah monolith feature menjadi tiga package terpisah per kapabilitas:
     - `FeatureTransferInterface` (Protocols, Models - Ringan, Static Framework)
     - `FeatureTransfer` (Implementasi VIPER - Private, Static Library)
     - `FeatureTransferTesting` (Mocks untuk unit testing modul lain)
   - Dependency Rule: Modul `A` dilarang mengimpor implementasi Modul `B`. Hanya boleh mengimpor `Interface` milik `B`.
2. **Offloading Data Processing via Background Actor**:
   - Parsing JSON sebesar 10MB dari CoreData/Network dialihkan ke `BackgroundDataProcessor` Actor.
   - Paging dilakukan dengan mekanisme zero-copy payload.
3. **Automated Leak Sanitization via CI**:
   - Memasang test target khusus dengan integrasi `FBAllocationTracker` dan instrumen `leaks` CLI pada tahap pull-request pipeline.

### Hasil Metrik Produksi
- **Waktu Build**: Berkurang dari 42 menit menjadi **11 menit** (Penurunan ~73%).
- **Framerate UI**: Bebas hitch (*0.2% hitch rate*), stabil pada **60/120 fps** (ProMotion).
- **Memory Footprint**: Konsumsi stabil di rentang **85MB - 120MB** tanpa degradasi akumulatif pasca pemindahan ke *Side-Table-Safe ARC design*.

---

## 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Biaya / Trade-off | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Actor vs Dispatch Serial Queue** | Aman dari *data races* di level compiler (*compile-time safety*), sintaksis bersih dengan `async/await`. | Tidak mendukung operasi sinkronus instan; potensi *Actor Reentrancy* jika logika bergantung pada state pre-suspension. | State mutasi internal di Swift 6; I/O operations; Networking layer. |
| **Modular SPM via Dynamic vs Static Framework** | Static: Kompilasi cepat, inline optimizations lintas file.<br>Dynamic: Ukuran binary app kecil jika framework dibagi banyak target. | Static: Risiko duplikasi simbolik jika arsitektur graph salah.<br>Dynamic: *App launch time* (dyld load phase) meningkat signifikan. | Gunakan Static Framework untuk modul domain/fitur. Dynamic hanya untuk binary pihak ketiga yang tak dapat diubah. |
| **Clean VIPER vs Vanilla MVVM** | Pemisahan tanggung jawab mutlak, modular, mudah dilakukan *isolated unit testing*. | *Boilerplate code* sangat tinggi; kurva belajar tajam; *over-engineering* jika layar UI bersifat statis/sederhana. | Fitur inti perbankan, checkout payment, atau form multi-langkah dengan validasi rumit. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Capture Self Mengambang di Task Tanpa Isolasi
```swift
// SALAH: Task inherit self context secara implisit, menahan UIViewController tetap di heap
class DetailViewController: UIViewController {
    var repository: RepositoryProtocol!
    
    func loadData() {
        Task {
            let data = try await repository.fetchDetails()
            self.render(data) // Retain cycle tersembunyi hingga fetchDetails selesai!
        }
    }
    func render(_ data: Data) {}
}

// BENAR: Gunakan [weak self] dan pastikan guard MainActor unwrapping
class DetailViewController: UIViewController {
    var repository: RepositoryProtocol!
    
    func loadData() {
        Task { [weak self] in
            guard let self else { return }
            let data = try await self.repository.fetchDetails()
            await MainActor.run {
                self.render(data)
            }
        }
    }
    func render(_ data: Data) {}
}
```

### Mistake 2: Unsafe Sendable Crossing
Mengirimkan class mutable (*Non-Sendable*) melintasi batasan concurrent actor:
```swift
// ERROR PADA SWIFT 6
class UserProfile {
    var name: String = ""
}

actor ProfileManager {
    func update(profile: UserProfile) { // Compiler Warning/Error: Passing argument of non-sendable type 'UserProfile'
        // ...
    }
}

// SOLUSI: Konversi ke Immutable Value Type (Struct)
struct UserProfile: Sendable {
    let name: String
}
```

### Panduan Troubleshooting Memory Leak Melalui Xcode Instruments
1. Buka Xcode -> **Product** -> **Profile** (`Cmd + I`).
2. Pilih Template **Leaks**.
3. Jalankan skenario fitur bolak-balik sebanyak 10 kali (misal: Buka Form Transfer -> Kembali ke Home).
4. Amati track bar:
   - Jika terdapat checklist merah (**Red Cross**), klik tab *Leaks* di inspection window.
   - Buka **Cycles & Roots Graph**.
   - Analisis *backtrace* pointer: Cari node closure context yang mempertahankan referensi ganda antara Presenter dan Interactor.

---

## 11. Best Practices (Production Checklist)

### Strict Concurrency Checklist
- [ ] Flag Build Setting `-strict-concurrency=complete` aktif di seluruh SPM package dan project targets.
- [ ] Seluruh mutable shared states dilindungi oleh `actor` atau `@MainActor`.
- [ ] Tidak ada penggunaan bypass `@unchecked Sendable` kecuali terbungkus sinkronisasi level OS tingkat rendah (`os_unfair_lock`) yang telah diuji stress test.

### Memory & Architecture Checklist
- [ ] Semua protocol closure delegate dideklarasikan dengan tipe `AnyObject` dan ditandai `weak`.
- [ ] Semua domain entities adalah `immutable struct` yang mengadopsi protocol `Sendable`.
- [ ] Presenter diisolasi dari referensi langsung framework UI (kecuali tipe data primitif atau view model state structures murni).
- [ ] Tidak ada dependensi horizontal antar modul fitur (Modul Fitur X tidak boleh `import FeatureY`). Komunikasi harus melalui Router / Deep-link Core Coordinator.

---

## 12. Hands-on Practice

Struktur direktori praktikum yang harus dibangun:

```
hands-on/m02/
├── Package.swift
├── Sources/
│   ├── CoreNetwork/
│   │   └── NetworkClient.swift
│   ├── FeatureAuthDomain/
│   │   └── AuthProtocols.swift
│   └── FeatureAuth/
│       ├── AuthInteractor.swift
│       ├── AuthPresenter.swift
│       └── AuthWorker.swift
└── Tests/
    └── FeatureAuthTests/
        └── AuthInteractorTests.swift
```

### Langkah Praktikum

#### Langkah 1: Inisialisasi Workspace SPM
Buat direktori dan berkas konfigurasi SPM di `hands-on/m02/Package.swift`:

```swift
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "EnterpriseModule",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "CoreNetwork", targets: ["CoreNetwork"]),
        .library(name: "FeatureAuthDomain", targets: ["FeatureAuthDomain"]),
        .library(name: "FeatureAuth", targets: ["FeatureAuth"])
    ],
    targets: [
        .target(name: "CoreNetwork"),
        .target(name: "FeatureAuthDomain"),
        .target(
            name: "FeatureAuth",
            dependencies: ["FeatureAuthDomain", "CoreNetwork"]
        ),
        .testTarget(
            name: "FeatureAuthTests",
            dependencies: ["FeatureAuth", "FeatureAuthDomain"]
        )
    ]
)
```

#### Langkah 2: Buat Protocol Domain
Tulis berkas `Sources/FeatureAuthDomain/AuthProtocols.swift`:

```swift
import Foundation

public struct UserCredentials: Sendable {
    public let email: String
    public let token: String
    public init(email: String, token: String) {
        self.email = email
        self.token = token
    }
}

public protocol AuthRepositoryProtocol: Sendable {
    func authenticate(token: String) async throws -> UserCredentials
}

public protocol AuthPresenterOutputProtocol: AnyObject, Sendable {
    func didAuthenticateSuccessfully(user: UserCredentials) async
    func didFailAuthentication(reason: String) async
}
```

#### Langkah 3: Implementasi Interactor & Testing
Tulis berkas `Sources/FeatureAuth/AuthInteractor.swift`:

```swift
import Foundation
import FeatureAuthDomain

public final class AuthInteractor: @unchecked Sendable {
    private let repository: AuthRepositoryProtocol
    public weak var presenter: AuthPresenterOutputProtocol?
    
    public init(repository: AuthRepositoryProtocol) {
        self.repository = repository
    }
    
    public func login(with token: String) async {
        guard !token.isEmpty else {
            await presenter?.didFailAuthentication(reason: "Invalid Token")
            return
        }
        
        do {
            let credentials = try await repository.authenticate(token: token)
            await presenter?.didAuthenticateSuccessfully(user: credentials)
        } catch {
            await presenter?.didFailAuthentication(reason: error.localizedDescription)
        }
    }
}
```

Tulis file unit test di `Tests/FeatureAuthTests/AuthInteractorTests.swift`:

```swift
import XCTest
@testable import FeatureAuth
@testable import FeatureAuthDomain

private final class MockAuthRepository: AuthRepositoryProtocol {
    var shouldFail: Bool = false
    
    func authenticate(token: String) async throws -> UserCredentials {
        if shouldFail {
            throw NSError(domain: "AuthError", code: 401, userInfo: [NSLocalizedDescriptionKey: "Unauthorized"])
        }
        return UserCredentials(email: "engineer@enterprise.com", token: token)
    }
}

private final class MockAuthPresenter: AuthPresenterOutputProtocol, @unchecked Sendable {
    var capturedUser: UserCredentials?
    var capturedError: String?
    
    func didAuthenticateSuccessfully(user: UserCredentials) async {
        self.capturedUser = user
    }
    
    func didFailAuthentication(reason: String) async {
        self.capturedError = reason
    }
}

final class AuthInteractorTests: XCTestCase {
    func testLoginSuccess() async {
        let repo = MockAuthRepository()
        let presenter = MockAuthPresenter()
        let sut = AuthInteractor(repository: repo)
        sut.presenter = presenter
        
        await sut.login(with: "VALID_JWT_TOKEN")
        
        XCTAssertEqual(presenter.capturedUser?.email, "engineer@enterprise.com")
        XCTAssertNil(presenter.capturedError)
    }
    
    func testLoginEmptyTokenFails() async {
        let repo = MockAuthRepository()
        let presenter = MockAuthPresenter()
        let sut = AuthInteractor(repository: repo)
        sut.presenter = presenter
        
        await sut.login(with: "")
        
        XCTAssertEqual(presenter.capturedError, "Invalid Token")
        XCTAssertNil(presenter.capturedUser)
    }
}
```

Jalankan pengujian via Terminal:
```bash
cd hands-on/m02/
swift test
```

---

## 13. Exercise

### Level Easy
Ubah *class* mutable presenter lama di bawah ini menjadi presenter thread-safe yang mematuhi `@MainActor` isolation:
```swift
// Kode Awal:
class LegacyPresenter {
    var title: String = ""
    func updateTitle(_ text: String) {
        self.title = text
    }
}
```
*Kriteria Penerimaan*:
- Mengadopsi anotasi `@MainActor`.
- Tambahkan antarmuka protokol `Sendable`.

### Level Medium
Buat sebuah Actor bernama `MetricsCollector` yang mencatat *latency* jaringan.
- Memiliki fungsi `func record(time: TimeInterval, for endpoint: String)`.
- Memiliki fungsi `func averageLatency(for endpoint: String) -> TimeInterval`.
- Harus mampu menangani *concurrent insertion* dari 1000 tasks secara simultan tanpa *data-race* (verifikasi via `swift test --sanitize=thread`).

### Level Hard
Implementasikan sebuah `DependencyInjectionContainer` berbasis *Service Locator Pattern* tingkat lanjut yang:
- Menggunakan Swift Type System (`ObjectIdentifier`) sebagai lookup keys.
- Membedakan *Singleton Lifecycle* (disimpan dalam actor state) vs *Transient Lifecycle* (dibuat instansiasi baru via factory closure setiap dipanggil).
- Menjamin *Thread Safety* saat read dan register service.

---

## 14. Challenge

### Studi Kasus: Offline-First Resilient Transaction Dispatcher
Rancang subsistem pembayaran offline-first yang memenuhi kriteria ekstrim berikut:

1. **Persistensi Antrean Idempoten**: Saat koneksi internet terputus, mutasi pembayaran harus dimasukkan ke antrean lokal (enkripsi on-disk).
2. **Swift Concurrency Rules**: Seluruh sinkronisasi background worker wajib menggunakan `AsyncSequence` atau `TaskGroup`. Dilarang menggunakan `DispatchQueue` atau `OperationQueue`.
3. **Actor Serialization**: Pembayaran ke server harus dieksekusi secara serial satu demi satu (tidak boleh paralel) untuk menghindari duplikasi saldo pengguna, namun pelaporan progress ke antarmuka pengguna (UI) harus instan dan tidak boleh terblokir (*zero hitch*).
4. **Leak-Free Guarantee**: Buat skenario stress-test testing suite yang membuktikan bahwa pemutusan koneksi di tengah pemrosesan 500 antrean transaksi tidak meninggalkan *memory leak* pada objek transaksi maupun *Side Table entry*.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Kapan runtime Swift memutuskan untuk membuat *Side Table* bagi suatu heap object?
   - A. Saat method inheritance mencapai kedalaman lebih dari 3 tingkat.
   - B. Saat strong reference count melampaui inline storage atau saat weak reference pertama dibuat ke objek tersebut.
   - C. Setiap kali sebuah class mengadopsi protocol `Sendable`.
   - D. Ketika class dideklarasikan sebagai `final`.

2. Apa perbedaan utama antara *Static Dispatch* dan *Table Dispatch*?
   - A. Static dispatch membutuhkan runtime lookup; Table dispatch di-inline saat kompilasi.
   - B. Static dispatch mengarah langsung ke alamat memori tanpa overhead runtime; Table dispatch mencari pointer fungsi pada offset V-Table/Witness Table.
   - C. Table dispatch hanya digunakan oleh struct; Static dispatch hanya oleh class.
   - D. Static dispatch selalu mengeksekusi method di Main Thread.

3. Mengapa keyword `unowned` dapat memicu crash (*fatal error*) sedangkan `weak` tidak?
   - A. `unowned` selalu menghasilkan nilai `nil`.
   - B. `unowned` mengasumsikan objek rujukan selalu hidup; jika objek terdeallokasi, runtime mendereference memory liar tanpa zeroing mechanism.
   - C. `unowned` menggunakan Side Table secara eksklusif.
   - D. `unowned` hanya bekerja pada antarmuka C++.

4. Komponen mana dalam arsitektur VIPER yang bertanggung jawab memformat data numerik (seperti `Decimal` currency) menjadi `String` sebelum ditampilkan di layar?
   - A. Interactor
   - B. Worker
   - C. Presenter
   - D. Router

5. Apa dampak dari menyalakan build flag `-strict-concurrency=complete` pada Xcode?
   - A. Mengubah semua class menjadi struct secara otomatis.
   - B. Menegakkan aturan Data-Race Safety compile-time Swift 6, memvalidasi isolasi Sendable dan Actor di seluruh codebase.
   - C. Menonaktifkan sistem ARC untuk meningkatkan kecepatan.
   - D. Membatasi alokasi thread GCD hanya pada QoS Background.

### 5 Pertanyaan Intermediate
6. Amati skenario: Sebuah `actor BankAccount` memiliki method `withdraw(amount:)` yang memiliki titik suspensi `await logTransaction()`. Masalah apa yang berpotensi terjadi akibat *Actor Reentrancy*?
   - A. Deadlock permanen pada OS Thread.
   - B. State saldo akun dapat berubah di antara pemeriksaan saldo dan pengurangan saldo aktual karena task lain dieksekusi saat suspensi.
   - C. Runtime secara instan melempar exception `EXC_BAD_ACCESS`.
   - D. Compiler menolak kompilasi method actor yang memiliki titik suspensi.

7. Mengapa decoupling dependensi menggunakan protokol lebih disukai daripada subclassing class konkret dalam arsitektur modular enterprise?
   - A. Protokol menjamin static dispatch secara default di semua implementasi.
   - B. Mengizinkan penggantian implementasi dengan Mock Object saat unit testing serta memotong rantai dependensi fisik antar framework biner.
   - C. Mempercepat dynamic loading (dyld) saat cold start aplikasi.
   - D. Menghilangkan kebutuhan alokasi heap memori sepenuhnya.

8. Jika sebuah struct mengadopsi protocol dengan method non-mutating, dan struct tersebut berukuran 5 *word* (40 byte), bagaimana memori model struct tersebut dilewatkan ke dalam *Existential Container*?
   - A. Disimpan secara inline di dalam 3 *word buffer* Existential Container.
   - B. Karena ukurannya > 3 *words* (24 byte), struct dialokasikan di Heap, dan heap address-nya disimpan di dalam value buffer Existential Container.
   - C. Struct dipotong (*truncated*) menjadi 24 byte pertama.
   - D. Runtime memprogram ulang method table menjadi Dynamic Message Dispatch.

9. Manakah pernyataan yang paling tepat mengenai hubungan antara `Task` dan GCD Thread Pool di modern Swift Concurrency?
   - A. `Task.detached` selalu meluncurkan Thread `pthread` baru dari Kernel.
   - B. Swift Concurrency membatasi OS Thread Pool secara kooperatif sesuai core logis CPU, menghindari overhead thread explosion yang sering terjadi pada GCD queues.
   - C. Setiap kali `await` dipanggil, thread terkunci (*blocked*) sampai operasi I/O selesai.
   - D. Prioritas `TaskPriority` tidak berpengaruh terhadap urutan eksekusi Cooperative Thread Pool.

10. Mengapa `weak reference` tidak boleh diarahkan ke struktur data bertipe `struct`?
    - A. Karena struct tidak memiliki *deinit*.
    - B. Karena struct adalah Value Type yang hidup di Stack atau ter-inline di container-nya, sehingga tidak dikelola melalui heap pointer lifecycle milik ARC.
    - C. Karena compiler bug pada LLVM.
    - D. Karena struct secara otomatis berstatus `Sendable`.

### 3 Skenario Kasus Produksi
11. **Skenario 1**: Aplikasi perbankan Anda crash di tangan puluhan ribu pengguna dengan log `EXC_BAD_ACCESS KERN_INVALID_ADDRESS` yang acak pada modul pelacakan analitik. Kode menunjukkan `AnalyticsTracker.shared.track(event:)` memutasi dictionary internal tanpa sinkronisasi dari berbagai background task GCD. Apa solusi perbaikan arsitektural yang paling permanen dan aman?
    - A. Membungkus mutasi dictionary menggunakan `objc_sync_enter(self)`.
    - B. Mengubah `AnalyticsTracker` menjadi sebuah `actor` atau memproteksi dictionary menggunakan isolated serialization queue / os_unfair_lock, serta memastikan event parameter bersifat `Sendable`.
    - C. Mengganti dictionary Swift dengan `NSMutableDictionary` bawaan Objective-C.
    - D. Menurunkan QoS panggilan analitik menjadi `.background`.

12. **Skenario 2**: Profiling Instruments menunjukkan lonjakan memory leak saat pengguna berpindah-pindah antar halaman katalog produk. Investigasi menemukan bahwa `ProductPresenter` memegang referensi ke `ProductInteractor`, dan `ProductInteractor` memegang closure callback `var onUpdate: (() -> Void)?` yang disuplai oleh `ProductPresenter`. Bagaimana cara memecahkan circular retain cycle ini sesuai kaidah Clean Architecture?
    - A. Mengubah closure callback tersebut dengan pola delegation terbalik di mana Presenter mengadopsi protocol antarmuka yang dipegang secara `weak` oleh Interactor.
    - B. Memanggil `exit(0)` ketika halaman ditutup.
    - C. Mengubah Presenter dari `class` menjadi `struct`.
    - D. Mengubah reference di Interactor menjadi `unowned(unsafe)`.

13. **Skenario 3**: Sebuah tim enterprise ingin mengurangi waktu *Clean Build* dari 30 menit menjadi di bawah 10 menit. Arsitektur aplikasi saat ini berupa 1 Target Xcode Monolitik besar berisi 800 file Swift. Langkah modularisasi mana yang menghasilkan reduksi waktu kompilasi paling efektif?
    - A. Mengubah seluruh extension method menjadi `@objc dynamic`.
    - B. Memecah aplikasi menjadi multi-package SPM atau multi-project via Tuist/Bazel, memisahkan modul antarmuka/kontrak (API) dari modul implementasi, sehingga perubahan kode pada satu modul implementasi tidak memicu re-kompilasi modul lain yang tidak terhubung langsung.
    - C. Menghapus seluruh Unit Test target dari project workspace.
    - D. Menggabungkan 800 file tersebut menjadi satu file monolithic raksasa 100.000 baris agar LLVM hanya bekerja satu kali.

---

### Kunci Jawaban Quiz

#### Basic
1. **B** - Side Table dibuat ketika ref count bit inline overflow atau ketika objek tersebut pertama kali direferensikan oleh *weak reference*.
2. **B** - Static dispatch melompat langsung ke alamat fungsi statis. Table dispatch menggunakan V-Table/Witness Table untuk mencari pointer method secara dinamis berdasarkan runtime type.
3. **B** - `unowned` tidak memverifikasi apakah objek masih hidup saat dereferencing (tidak ada zeroing pointer); jika objek musnah, mengaksesnya mengakibatkan dangling memory access (crash).
4. **C** - Presenter adalah batas presentation-formatting domain: bertugas mengubah domain model menjadi view primitives.
5. **B** - Build setting tersebut mengaktifkan verifikasi penuh seluruh batasan thread-safety Swift 6 pada waktu kompilasi.

#### Intermediate
6. **B** - Actor Reentrancy memungkinkan task lain menyela eksekusi actor pada setiap titik suspensi `await`, sehingga state lokal berpotensi berubah di tengah proses transaksi logis jika tidak divalidasi ulang.
7. **B** - Protokol memutus rantai ketergantungan konkrit antar biner (*Dependency Inversion Principle*), mempermudah mock testing dan mempercepat incremental build.
8. **B** - Existential Container memiliki *Inline Value Buffer* sebesar 3 words (24 byte). Payload data yang melampaui ukuran tersebut dialokasikan runtime ke Heap.
9. **B** - Swift Concurrency Cooperative Pool membatasi worker thread sesuai kapabilitas core CPU guna menghindari overhead *thread explosion* dan *context switching latency*.
10. **B** - Value types (struct) tidak memiliki heap identity allocation tersendiri dan tidak dimonitor oleh ARC reference counter.

#### Skenario Kasus Produksi
11. **B** - Mengubah modul pelacakan menjadi `actor` mengeliminasi concurrent write mutasi pada state dictionary, sekaligus menjamin compile-time data race safety.
12. **A** - Mengganti closure yang saling mengikat (*strong capture*) dengan antarmuka protocol bertipe `weak` memutus siklus retain cycle antara Presenter dan Interactor secara arsitektural.
13. **B** - Pemecahan biner melalui modularisasi dependency inversion adalah standar enterprise untuk mengisolasi cache kompilasi dan memaksimalkan *parallel/incremental compilation pipeline*.

---

## 16. Summary

1. **Efisiensi Runtime Swift**: Kinerja eksekusi aplikasi berakar pada pemahaman *method dispatch* (Static vs Table vs Message) serta pengelolaan memori *ARC inline bitfield vs Side Table*. Penggunaan Value Types dan deklarasi `final` memaksimalkan *direct dispatch* yang membuka potensi optimasi kompiler (*inlining*).
2. **Kestabilan Skala Besar**: Menulis kode iOS modern pada level enterprise menuntut kepatuhan mutlak terhadap aturan **Swift 6 Concurrency**. Pola tradisional berbasis lock atau bare GCD queues harus digantikan oleh *Actors*, mitigasi *Actor Reentrancy*, dan pembatasan isolasi memori via *Sendable Value Semantics*.
3. **Arsitektur Modular**: Pola *Clean Swift / VIPER* yang dikombinasikan dengan pemisahan antarmuka modul (Interface vs Implementation Targets) mencegah degenerasi kode menjadi *God Objects*, meminimalisir waktu kompilasi biner (*build time*), dan memastikan setiap lapisan dapat diuji secara terisolasi tanpa efek samping.