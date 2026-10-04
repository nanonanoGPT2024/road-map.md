# BAB 05 / MODUL 01: Modern Concurrency & Async UI Orchestration

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori:** 02-Programming-Languages
* **Kurikulum:** swift-ui
* **Jalur Pembelajaran:** Advanced iOS/macOS Systems & UI Engineering
* **Level Kognitif:** Level 4 (Advanced) to Level 5 (Expert)
* **Prasyarat:**
  * Penguasaan Swift 5.9+ / Swift 6 Syntax dasar.
  * Pemahaman mendalam tentang SwiftUI State Management (`@State`, `@Observable`, `@Binding`).
  * Pengetahuan dasar tentang thread, queue, dan runtime model Apple (POSIX Threads, Grand Central Dispatch).
* **Target Versi Runtime & Tools:**
  * Swift 6.0 (Complete Concurrency Checking / Strict Mode).
  * iOS 17.0+ / macOS 14.0+ SDK.
  * Xcode 16.0+.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda akan mampu:

1. **Menganalisis dan Membedakan** model eksekusi *Grand Central Dispatch* (GCD) berbasis OS-thread pool dengan *Swift Cooperative Thread Pool* dan kontrak penjadwalannya.
2. **Menguasai Mekanisme Structured Concurrency** menggunakan `async`/`await`, `withTaskGroup`, dan `withThrowingTaskGroup` guna menjamin determinisme siklus hidup proses background.
3. **Mengorkestrasi State SwiftUI** dengan tepat melalui isolasi domain `@MainActor`, eliminasi *data race* secara compile-time, serta memanfaatkan modifier siklus hidup `.task` dan `.task(id:)`.
4. **Menerapkan Pola Pembatalan Kooperatif (*Cooperative Task Cancellation*)** secara presisi pada alur I/O jaringan dan komputasi intensif.
5. **Mengabstraksi Sumber Data Asinkron Streaming** menggunakan `AsyncSequence` dan `AsyncStream` untuk konsumsi data reaktif real-time di UI layer.
6. **Mendiagnosis dan Memitigasi Masalah Konkurensi Kompleks** seperti *Actor Reentrancy*, *Thread Starvation*, dan kebocoran memori akibat *Unstructured Tasks*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: GCD vs. Swift Concurrency

Dalam model lama Grand Central Dispatch (GCD), developer berpikir dalam kerangka **antrean (*queues*) dan eksekusi blok closures**. Pola ini mengasumsikan bahwa setiap kali Anda membutuhkan pekerjaan di luar thread utama, Anda membuat atau memanggil antrean (`DispatchQueue.global().async { ... }`), yang dapat memicu pembuatan thread baru oleh kernel OS.

Ketika ratusan blok dikirim secara simultan, GCD dapat memicu fenomena **Thread Explosion**: sistem membuat ratusan thread, menyebabkan memori overhead yang besar untuk alokasi thread stack (minimal ~512KB per thread pada iOS), serta degradasi performa drastis akibat lonjakan *context-switching overhead* di level CPU.

```
Model Tradisional (GCD):
Tiap task baru berpotensi menuntut thread baru ➔ Risiko Thread Explosion & Lock Contention
[Queue] ---> Thread 1 (Block)
        ---> Thread 2 (Block)
        ---> ...
        ---> Thread 128 (Thread Explosion!)
```

Swift Concurrency didesain dengan mental model **Cooperative Thread Pool**:
* **Batasan Thread Intransigen:** Swift Concurrency membatasi jumlah thread worker maksimum sejumlah *core CPU fisik/logis* mesin.
* **Suspension vs. Blocking:** Jika suatu asynchronous unit (`Task`) terhenti menunggu I/O atau penguncian data, ia **tidak memblokir thread sistem**. Task tersebut melakukan *suspend* (menangguhkan eksekusi), melepaskan stack frame-nya, dan mengembalikan thread worker ke pool agar dapat mengeksekusi Task lain.
* **Continuations:** Task yang di-suspend direpresentasikan sebagai *Continuation* pada heap runtime Swift. Ketika operasi I/O selesai, runtime mengantrekan kembali continuation tersebut ke pool worker yang sedang idle.

```
Model Swift Concurrency:
N Core CPU = N Worker Threads. Eksekusi asynchronous ditangguhkan (Suspended), bukan diblokir.
Task A (Suspended) ──> Simpan State (Continuation) ──> Thread 1 kosong ──> Eksekusi Task B
```

### Mengaitkan Concurrency dengan Deklaratif UI (SwiftUI)

Dalam arsitektur SwiftUI, View bersifat *ephemeral* (sementara), dibuat dan dibuang berkali-kali oleh *rendering engine*. Menjalankan konkurensi di luar siklus hidup deklaratif SwiftUI (misal: memicu `Task.detached` di dalam `body` atau `onAppear`) merusak jaminan stabilitas state.

Mental model yang benar: **Siklus hidup Task konkurensi harus terikat secara deterministik ke siklus hidup Node pada Dependency Graph SwiftUI.** Modifier `.task` mengikat eksekusi asynchronous ke durasi eksistensi view di layar: saat view muncul, task dibuat; saat view hilang dari hierarki, task secara otomatis menerima sinyal pembatalan (*cancellation*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur orkestrasi konkurensi modern dalam sistem SwiftUI mengintegrasikan UI Tree, Isolasi `@MainActor`, Data Synchronization Actor, dan Cooperative Thread Pool:

```
+-------------------------------------------------------------------------------+
|                                SWIFTUI VIEW LAYER                             |
|                                                                               |
|   +-----------------------------------------------------------------------+   |
|   | struct MarketDashboardView: View                                      |   |
|   |                                                                       |   |
|   |   @State private var model: MarketDashboardModel                      |   |
|   |                                                                       |   |
|   |   var body: some View {                                               |   |
|   |       List(model.feed) { ... }                                        |   |
|   |           .task(id: model.selectedSymbol) {                           |   |
|   |               await model.subscribeToLiveTicks()                      |   |
|   |           }                                                           |   |
|   |   }                                                                   |   |
|   +-----------------------------------------------------------------------+   |
+-------------------------------------------------------------------------------+
         | Bind State Update                        ^ Yield Dispatched State
         | (Implicitly isolated to @MainActor)       | (Main RunLoop)
         v                                          |
+---------------------------------------------------+---------------------------+
|                        APPLICATION & PRESENTATION DOMAIN                      |
|                                                                               |
|   @Observable @MainActor                                                      |
|   final class MarketDashboardModel {                                          |
|       var feed: [Tick] = []                                                   |
|       private let repository: MarketDataRepository // Actor                  |
|                                                                               |
|       func subscribeToLiveTicks() async {                                     |
|           // Suspension Point 1: Hop dari MainActor ke Cooperative Pool       |
|           let stream = await repository.tickStream(for: selectedSymbol)       |
|           for await tick in stream {                                          |
|               // Suspension Point 2: Tiap event dievaluasi di @MainActor      |
|               self.feed.append(tick)                                          |
|           }                                                                   |
|       }                                                                       |
|   }                                                                           |
+-------------------------------------------------------------------------------+
         | Call Actor API (Thread-Safe Isolation Boundary Crossing)
         v
+-------------------------------------------------------------------------------+
|                            ISOLATED DATA REPOSITORY                           |
|                                                                               |
|   actor MarketDataRepository {                                                |
|       private var activeSession: URLSessionWebSocketTask?                     |
|                                                                               |
|       func tickStream(for symbol: String) -> AsyncStream<Tick> {              |
|           // Mailbox-based synchronization                                    |
|           // Membaca socket, decode di background thread                      |
|       }                                                                       |
|   }                                                                           |
+-------------------------------------------------------------------------------+
         |
         | Execution Dispatched to:
         v
+-------------------------------------------------------------------------------+
|                      SWIFT COOPERATIVE THREAD POOL                            |
|                                                                               |
|  [ Thread 1 (Core 0) ] <---> [ Thread 2 (Core 1) ] <---> [ Thread N (Core N) ]|
|  +-------------------+       +-------------------+       +-------------------+|
|  | Task: WS Reader   |       | Task: JSON Decode |       | Idle / Next Queue ||
|  +-------------------+       +-------------------+       +-------------------+|
+-------------------------------------------------------------------------------+
```

### Diagram Alur Penanganan Task Cancellation

```
[View Ditampilkan] ──> [.task Dimulai] ──> [Task Diinisialisasi (TaskPriority.userInitiated)]
                                                        │
                                                        ▼
                                           [Operasi Network I/O Dimulai]
                                                        │
         ┌──────────────────────────────────────────────┴──────────────────────────────┐
         ▼                                                                             ▼
[View Dihancurkan / ID Berubah]                                             [I/O Berhasil Diunduh]
         │                                                                             │
         ▼                                                                             ▼
[.task Mengirimkan .cancel()]                                               [Lakukan JSON Parsing]
         │                                                                             │
         ▼                                                                             ▼
[Task.isCancelled == true]                                                  [Update State ke @MainActor]
         │                                                                             │
         ├──────────────────────────────────┐                                          ▼
         ▼                                  ▼                                    [Render Frame]
[URLSession Menghentikan Socket]    [Task Melempar CancellationError]
         │                                  │
         └──────────────────────────────────┴──> [Task Dihentikan & Heap Diclear]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Model Kompilasi: Async/Await Transformasi CPS (*Continuation-Passing Style*)

Ketika fungsi ditandai dengan keyword `async`, compiler Swift (`swiftc`) tidak lagi mengompilasinya menjadi fungsi standar berbasis stack frame C-convention. Fungsi tersebut dipecah secara mendasar pada setiap titik **suspension point** (yang ditandai oleh keyword `await`):

```swift
func loadData() async throws -> Data {
    let raw = try await networkFetch() // Suspension Point 1
    let parsed = await process(raw)    // Suspension Point 2
    return parsed
}
```

Di balik layar, compiler membagi fungsi ini menjadi *continuation-passing state machine*:
* **Asynchronous Frame Stack:** Alih-alih mengalokasikan stack di register memori thread OS yang fixed, Swift mengalokasikan *async task frame* di heap. Frame ini menyimpan nilai variabel lokal (`raw`, `parsed`) di seluruh suspension point.
* **Splitting:** `loadData()` dipecah menjadi tiga bagian:
  1. Entry point hingga `networkFetch()`.
  2. Kelanjutan (resume pointer) dari `networkFetch()` hingga `process()`.
  3. Kelanjutan dari `process()` hingga pengembalian `Data`.
* Ketika titik `await` tercapai, runtime mengecek ketersediaan data. Jika tertunda, runtime mengembalikan pointer kendali ke thread pool worker saat ini, melepaskan CPU thread untuk mengeksekusi closure/task lain.

### 2. Actor Mailbox & Isolation Boundary

`actor` diimplementasikan sebagai objek referensi (`AnyObject`) yang mengamankan mutasi internal state-nya melalui abstraksi sinkronisasi internal bernama **Serial Mailbox Executor**:
* Setiap actor memiliki satu antrean pesan (*mailbox*).
* Ketika fungsi actor dipanggil secara asinkron dari luar (`await myActor.execute()`), runtime membungkus pemanggilan ini sebagai pesan dan memasukkannya ke mailbox actor tersebut.
* Actor mengeksekusi pesan dalam mailbox satu per satu, menjamin tidak ada dua thread yang mengakses memori stored properties actor secara paralel. Ini melenyapkan *Data Race* pada level bahasa.

### 3. Cooperative Task Scheduling Engine

Scheduler Swift Concurrency dibangun tepat di atas primitif runtime yang terintegrasi dengan OS:
* Jumlah thread maksimum worker ditentukan saat proses dimulai: $N_{threads} = N_{logical\_cores}$.
* **Work-Stealing Queue:** Setiap worker thread memiliki *local run queue*. Jika suatu worker kehabisan task untuk dijalankan, ia akan "mencuri" (*steal*) continuation task dari worker thread lain. Hal ini menjaga throughput komputasi tetap seimbang tanpa perlu intervensi sistem operasi (bebas biaya system call context switches).

### 4. SwiftUI Lifecycle Bridge (`.task` Modifier)

Modifier `.task(priority:_:)` bertindak sebagai representasi level tinggi dari integrasi deklaratif:
1. Ketika node SwiftUI view masuk ke dalam hierarki render tree (`onAppear`), runtime SwiftUI membuat instance `Task(priority:)` baru.
2. Closure yang diberikan dieksekusi secara terisolasi di domain `@MainActor` (secara default, karena modifier ini berada di body View).
3. Jika view tereliminasi dari view hierarchy (`onDisappear`), SwiftUI secara eksplisit memanggil `task.cancel()`.
4. Jika parameter identitas diubah (`.task(id: value)`), SwiftUI membatalkan task yang sedang berjalan saat ini, menunggu status pembatalannya didaftarkan, lalu memicu Task baru dengan payload nilai yang baru.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Structured Concurrency vs. Unstructured Concurrency

Structured Concurrency mematuhi paradigma kontrol alur terstruktur: masa hidup konkurensi terikat secara strictly hierarkis ke lexical scope tempat konkurensi diinisialisasi.

```
       [Parent Task]
       ├── withTaskGroup
       │      ├── Child Task 1 (Concurrent)
       │      └── Child Task 2 (Concurrent)
       └── Await All Children Resolves
```

* **Child Tasks:** Semua child task yang dibuat di dalam scope `withTaskGroup` atau `async let` secara intrinsik mewarisi Task Priority, Task-Local Values, dan Actor Isolation dari parent task.
* **Deterministic Lifetime:** Parent task tidak dapat menyelesaikan operasinya sampai seluruh child task-nya selesai atau dibatalkan. Hal ini mencegah fenomena **Orphaned Tasks** yang sering menjadi akar kebocoran memori di GCD.
* **Unstructured Concurrency (`Task { ... }` / `Task.detached { ... }`):**
  * `Task { }`: Mewarisi isolasi konteks saat ini (misal: tetap berada di `@MainActor` jika dipanggil di view), mewarisi Task-Local Values, namun **memutus hubungan hierarki struktural**. Parent scope tidak menunggu task ini selesai.
  * `Task.detached { }`: Memutus hierarki sepenuhnya, tidak mewarisi isolation domain (dieksekusi langsung di cooperative pool), dan tidak mewarisi priority/Task-Local values. Penggunaannya harus dibatasi secara ketat, hanya untuk background processing yang benar-benar independen dari UI/Enclosing context.

### 2. Task Cancellation Propagation

Pembatalan dalam Swift Concurrency bersifat **kooperatif (*cooperative*)**, bukan preemptive:
* Memanggil `task.cancel()` tidak secara paksa menghentikan eksekusi thread. Sistem operasi tidak membunuh thread yang bersangkutan.
* Memanggil `cancel()` hanya menyetel flag boolean `Task.isCancelled` menjadi `true`.
* Pengembang wajib memeriksa status ini di titik-titik krusial menggunakan:
  1. `try Task.checkCancellation()`: Langsung melempar `CancellationError` jika task telah dibatalkan, menghentikan eksekusi frame saat ini dan membersihkan resources.
  2. `Task.isCancelled`: Pengecekan non-throwing untuk eksekusi logika pembersihan custom (misal: menutup file descriptor atau koneksi socket).

### 3. Swift 6 Data-Race Safety & `Sendable` Contract

Swift 6 menerapkan pembatasan *Compile-Time Data-Race Safety* secara mutlak. Kunci pertahanannya adalah protokol marker `Sendable`:
* **Tipe Data `Sendable`:** Tipe data yang aman dipindahkan melintasi batasan isolasi konkurensi (misal: dari background actor ke `@MainActor`).
  * Nilai *Value Type* (struct, enum) yang propertinya juga `Sendable`.
  * Class yang immutable (hanya memiliki properti `let` bertipe `Sendable` dan berstatus `final`).
  * Actor types (karena akses state di dalamnya diatur secara serial).
* Tipe data referensi yang mutable (class standar) **bukan** `Sendable`. Mengirim instance kelas semacam ini melintasi suspension point menuju context lain akan memicu error kompilasi di Swift 6 (`Sending 'myObject' risks causing data races`).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental: Mengambil data pengguna secara asinkron, menangani loading state, error boundaries, dan cooperative cancellation di SwiftUI menggunakan modern async lifecycle.

```swift
import SwiftUI

// MARK: - Models & DTOs (Sendable Guaranteed)
struct UserProfile: Identifiable, Codable, Sendable {
    let id: UUID
    let username: String
    let email: String
    let bio: String
}

enum ViewState: Sendable {
    case idle
    case loading
    case success(UserProfile)
    case failure(String)
}

// MARK: - Service Layer
actor UserProfileService {
    func fetchProfile(for userId: UUID) async throws -> UserProfile {
        // Simulasi network request delay
        try await Task.sleep(nanoseconds: 1_500_000_000)
        
        // Verifikasi apakah Task sudah dibatalkan sebelum memproses payload
        try Task.checkCancellation()
        
        return UserProfile(
            id: userId,
            username: "alex_dev",
            email: "alex@engineering.internal",
            bio: "Systems architect & compiler enthusiast."
        )
    }
}

// MARK: - UI Layer
struct UserProfileView: View {
    let userId: UUID
    private let service = UserProfileService()
    
    @State private var state: ViewState = .idle

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                switch state {
                case .idle:
                    Text("Menunggu inisialisasi...")
                        .foregroundStyle(.secondary)
                case .loading:
                    ProgressView("Mengambil profil pengguna...")
                        .controlSize(.regular)
                case .success(let profile):
                    ProfileDetailCard(profile: profile)
                case .failure(let errorMessage):
                    ContentUnavailableView {
                        Label("Gagal Memuat Data", systemImage: "exclamationmark.triangle")
                    } description: {
                        Text(errorMessage)
                    } actions: {
                        Button("Coba Lagi") {
                            // Memicu re-run dengan memperbarui id atau state
                            state = .loading
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }
            }
            .navigationTitle("User Profile")
            // Memanfaatkan .task modifier yang otomatis bind ke View lifecycle
            .task(id: userId) {
                await loadData()
            }
        }
    }

    @MainActor
    private func loadData() async {
        state = .loading
        do {
            let profile = try await service.fetchProfile(for: userId)
            // State mutation aman karena fungsi ini berjalan di @MainActor
            state = .success(profile)
        } catch is CancellationError {
            // Task dibatalkan karena view unmount. Hindari mutasi state berlebih.
            #if DEBUG
            print("Task cancelled gracefully: User navigated away.")
            #endif
        } catch {
            state = .failure(error.localizedDescription)
        }
    }
}

struct ProfileDetailCard: View {
    let profile: UserProfile

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(profile.username)
                .font(.title2)
                .bold()
            Text(profile.email)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Divider()
            Text(profile.bio)
                .font(.body)
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal)
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis baris-baris kritis pada implementasi Seksi 07:

1. **`struct UserProfile: Identifiable, Codable, Sendable`**
   * Menandai model data secara eksplisit sebagai `Sendable`. Karena `UserProfile` adalah struct murni dengan value types (`UUID`, `String`), compiler Swift memverifikasi bahwa state ini kebal dari race condition ketika dialirkan dari actor `UserProfileService` ke thread utama (`@MainActor`).
2. **`actor UserProfileService`**
   * Mengisolasi service state ke dalam domain aktor independen. Semua fungsi di dalamnya diakses menggunakan eksekutor serial actor, menjamin isolation boundary yang kedap.
3. **`try await Task.sleep(nanoseconds: 1_500_000_000)`**
   * Penangguhan non-blocking selama 1.5 detik. Thread pool worker tidak diblokir; thread tersebut kembali ke pool untuk mengerjakan task lain. Fungsi ini sensitif terhadap pembatalan: jika task dibatalkan selama sleep, method ini seketika melempar `CancellationError`.
4. **`try Task.checkCancellation()`**
   * Titik koordinasi pembatalan (*cancellation checkpoint*). Jika pengguna berpindah layar sebelum proses parsing atau komputasi lanjutan selesai, baris ini melempar error dan menghentikan alokasi CPU yang sia-sia.
5. **`.task(id: userId) { await loadData() }`**
   * Lifecycle attachment. SwiftUI mengaitkan task ini dengan identity token `userId`. Jika nilai `userId` berganti (misal navigasi dari user A ke user B), SwiftUI otomatis membatalkan task yang aktif sebelumnya dan mengeksekusi closure `.task` dengan instance `userId` terbaru.
6. **`@MainActor private func loadData() async`**
   * Menjamin bahwa pembaruan UI state (`self.state = ...`) selalu dieksekusi secara native pada Main Thread RunLoop. Tidak diperlukan lagi instruksi legacy seperti `DispatchQueue.main.async`.
7. **`catch is CancellationError`**
   * Secara khusus memisahkan error pembatalan kooperatif dari error domain (seperti network down atau malformed JSON). Pembatalan bukanlah kegagalan aplikasi, melainkan intensi eksplisit dari perubahan UI tree.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Skenario: High-Frequency Real-Time Cryptocurrency Ticker Engine

**Deskripsi Masalah:**
Sebuah aplikasi bursa kripto tier-1 harus menampilkan pergerakan harga ratusan instrumen finansial (*Tick Stream*) secara real-time via WebSocket. 
* Frekuensi data masuk: **50-200 tick per detik**.
* Jika setiap tick langsung memicu pembaruan state SwiftUI (`@Observable`), View rendering loop akan tersedak (*dropping frames* / UI freeze 15 FPS) karena pemanggilan layout engine yang berlebihan.
* Terjadi potensi bahaya *memory leak* dan *thread contention* jika koneksi stream WebSocket tidak dimatikan saat user berpindah tab.

**Solusi Arsitektural:**
1. Menggunakan **`AsyncStream`** untuk menjembatani callback API WebSocket sistem lama atau URLSessionWebSocketTask ke Async/Await abstraction.
2. Membangun **Actor Buffering Engine** untuk menampung tick data dengan throughput tinggi, lalu mendistribusikannya menggunakan teknik **Time-Window Batching (Debouncing)**.
3. Menghubungkan UI ke aggregate buffer terisolasi yang hanya memancarkan pembaruan ke `@MainActor` pada interval 60Hz (maksimal 1 update per 16ms), menjaga rendering tetap 120 FPS di layar ProMotion.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah arsitektur produksi lengkap dan modular untuk menangani skenario streaming finansial di atas:

```swift
import SwiftUI
import Observation

// MARK: - Domain Models
public struct CryptoTick: Identifiable, Hashable, Sendable {
    public let id: UUID
    public let symbol: String
    public let price: Double
    public let timestamp: Date

    public init(symbol: String, price: Double) {
        self.id = UUID()
        self.symbol = symbol
        self.price = price
        self.timestamp = Date()
    }
}

// MARK: - Actor Data Pipeline (Ingestion & Buffering)
public actor MarketDataIngestor {
    private var isStreaming = false
    
    /// Mengonversi callback socket kontinu ke AsyncStream
    public func subscribeToStream(for symbol: String) -> AsyncStream<CryptoTick> {
        AsyncStream { continuation in
            let task = Task {
                var currentPrice = 50_000.0
                while !Task.isCancelled {
                    // Simulasi I/O latency frekuensi tinggi: 10ms - 50ms per paket
                    let deltaMs = UInt64.random(in: 10...50)
                    try? await Task.sleep(nanoseconds: deltaMs * 1_000_000)
                    
                    if Task.isCancelled { break }

                    // Simulasi fluktuasi acak
                    let change = Double.random(in: -25.0...25.0)
                    currentPrice += change
                    
                    let tick = CryptoTick(symbol: symbol, price: currentPrice)
                    
                    // Emisi tick ke consumer pipeline
                    let yieldResult = continuation.yield(tick)
                    if case .terminated = yieldResult {
                        break
                    }
                }
            }
            
            // Clean-up handler saat downstream consumer membatalkan stream
            continuation.onTermination = { @Sendable _ in
                task.cancel()
            }
        }
    }
}

// MARK: - View Model (Throttling & UI Orchestration)
@Observable
@MainActor
public final class MarketTickerViewModel {
    public private(set) var latestTick: CryptoTick?
    public private(set) var priceHistory: [CryptoTick] = []
    public private(set) var isConnected: Bool = false
    
    private let ingestor = MarketDataIngestor()
    private let maxHistoryEntries = 50

    public func startStreaming(for symbol: String) async {
        isConnected = true
        let tickStream = await ingestor.subscribeToStream(for: symbol)
        
        // Target: Render throttled stream tanpa membebani Main Thread
        // Mengumpulkan emisi dan batch update per window
        var lastRenderTime = CFAbsoluteTimeGetCurrent()
        let renderInterval: CFTimeInterval = 0.05 // Batas 20Hz update UI (~50ms)

        do {
            for await tick in tickStream {
                // Cooperative Cancellation Checkpoint
                try Task.checkCancellation()

                let currentTime = CFAbsoluteTimeGetCurrent()
                if currentTime - lastRenderTime >= renderInterval {
                    self.updateUIState(with: tick)
                    lastRenderTime = currentTime
                }
            }
        } catch {
            #if DEBUG
            print("Stream gracefully halted via cancellation.")
            #endif
        }
        
        isConnected = false
    }

    private func updateUIState(with tick: CryptoTick) {
        self.latestTick = tick
        self.priceHistory.append(tick)
        if self.priceHistory.count > maxHistoryEntries {
            self.priceHistory.removeFirst(self.priceHistory.count - maxHistoryEntries)
        }
    }
}

// MARK: - SwiftUI View Layer
public struct MarketTickerView: View {
    @State private var viewModel = MarketTickerViewModel()
    @State private var selectedSymbol: String = "BTC-USDT"
    
    public init() {}

    public var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Status Header
                HStack {
                    Circle()
                        .fill(viewModel.isConnected ? Color.green : Color.red)
                        .frame(width: 10, height: 10)
                    Text(viewModel.isConnected ? "LIVE FEED" : "DISCONNECTED")
                        .font(.caption)
                        .bold()
                        .foregroundColor(.secondary)
                    Spacer()
                    Picker("Asset", selection: $selectedSymbol) {
                        Text("BTC-USDT").tag("BTC-USDT")
                        Text("ETH-USDT").tag("ETH-USDT")
                        Text("SOL-USDT").tag("SOL-USDT")
                    }
                    .pickerStyle(.segmented)
                    .frame(maxWidth: 200)
                }
                .padding(.horizontal)

                // Current Price Display
                VStack(spacing: 4) {
                    Text(selectedSymbol)
                        .font(.headline)
                        .foregroundStyle(.secondary)
                    
                    if let tick = viewModel.latestTick {
                        Text(tick.price, format: .currency(code: "USD"))
                            .font(.system(size: 40, weight: .heavy, design: .monospaced))
                            .contentTransition(.numericText())
                    } else {
                        Text("Menerima Data...")
                            .font(.title2)
                            .foregroundStyle(.secondary)
                    }
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 20)
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .padding(.horizontal)

                // Streamed Price List
                List {
                    Section("Histori Perubahan Terakhir") {
                        ForEach(viewModel.priceHistory.reversed()) { tick in
                            HStack {
                                Text(tick.timestamp, format: .dateTime.hour().minute().second().secondFraction(.fractional(3)))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                Spacer()
                                Text(tick.price, format: .currency(code: "USD"))
                                    .font(.body)
                                    .monospacedDigit()
                            }
                        }
                    }
                }
                .listStyle(.insetGrouped)
            }
            .navigationTitle("High-Freq Ticker")
            // Pengikatan konkurensi siklus hidup ke parameter selectedSymbol
            .task(id: selectedSymbol) {
                await viewModel.startStreaming(for: selectedSymbol)
            }
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih mekanisme konkurensi yang tepat menuntut pemahaman mendalam tentang konsekuensi arsitektural:

| Parameter Evaluasi | Grand Central Dispatch (GCD) | Combine Framework | Swift Modern Concurrency |
| :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Antrean blok closures FIFO | Deklaratif functional Reactive Streams | Cooperative Thread Pool & Structured Tasks |
| **Compile-Time Data Safety** | **Nol**. Membutuhkan serial queue manual; rawan race conditions | Rendah. Thread-hopping via `receive(on:)` tanpa jaminan isolasi | **Sempurna**. Validasi `Sendable` dan Actor isolation dicek saat compile |
| **Beban Overhead Memori** | Tinggi jika thread explosion terjadi (~512KB per thread) | Menengah (allocasi operator chain & subscription graph) | Rendah (Fixed pool size; Heap-based state machine frame) |
| **Propagasi Pembatalan** | Manual (`DispatchWorkItem.cancel()`), rawan kebocoran eksekusi | Terkelola via `AnyCancellable` set lifetime | Terintegrasi native via hierarki Structured Concurrency |
| **Integrasi SwiftUI** | Buruk. Wajib membungkus mutasi ke `DispatchQueue.main` | Menengah. Native via publisher `$state`, tapi syntax rumit | **Sangat Baik**. Modifier `.task`, `.refreshable` terikat langsung ke lifecycle View |
| **Kurva Pembelajaran** | Mudah di awal, berbahaya di tingkat skala besar | Sangat curam (Functional Reactive Programming paradigms) | Curam (Pergeseran mindset isolasi data dan cooperative model) |

### Kapan Memilih Swift Concurrency dibanding Combine?
* **Pilih Swift Concurrency:** Untuk semua alur asynchronous standar: Network API calls, Database queries (CoreData/SwiftData), file processing, serial synchronization (Actors), dan integrasi View Lifecycle dengan `.task`.
* **Tetap Gunakan Combine:** Jika aplikasi memerlukan operator manipulasi stream tingkat tinggi yang sangat kompleks (seperti `combineLatest`, `zip`, `buffer`, `debounce`) yang implementasi `AsyncSequence`-nya masih memerlukan *boilerplate* tambahan di ekosistem standar Foundation tanpa pustaka pihak ketiga.

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Actor Reentrancy

Actor tidak mengunci diri secara total selama proses `await`. Ketika eksekusi dalam method actor mencapai suspension point (`await`), actor membebaskan mailbox-nya sehingga panggilan method lain dari luar dapat disisipkan (*interleaved*).

```swift
actor BankAccount {
    private var balance: Double = 100.0

    func debit(amount: Double) async -> Bool {
        guard balance >= amount else { return false }
        
        // SUSPENSION POINT: Mengizinkan request lain masuk ke actor!
        await triggerAuditLog(amount: amount) 
        
        // BUG BAHAYA: Nilai balance bisa saja sudah berubah sejak baris guard di atas!
        balance -= amount 
        return true
    }
}
```

*Mitigasi:* Asumsikan state lokal actor dapat berubah setelah setiap titik `await`. Selalu validasi ulang state invariants setelah suspension point, atau pastikan mutasi dilakukan sebelum suspend:

```swift
func debit(amount: Double) async -> Bool {
    guard balance >= amount else { return false }
    balance -= amount // Kurangi langsung sebelum suspend
    await triggerAuditLog(amount: amount)
    return true
}
```

### 2. Thread Starvation Melalui Blocking APIs

Memanggil blocking system call synchronous di dalam cooperative pool akan "menculik" worker thread yang jumlahnya terbatas:

```swift
Task.detached {
    // FATAL MISTAKE: Memblokir Cooperative Thread Worker!
    // Pool thread tidak bisa dipakai oleh Task lain.
    Thread.sleep(forTimeInterval: 5.0) 
    
    // FATAL MISTAKE: Blocking I/O sinkron
    let data = try? Data(contentsOf: massiveRemoteURL) 
}
```

*Mitigasi:*
Gunakan API asynchronous bawaan (`Task.sleep`, `URLSession.data(from:)`). Jika Anda terpaksa berinteraksi dengan legacy C API blocking atau komputasi disk blocking, alokasikan operasi tersebut ke thread kustom GCD khusus (`DispatchQueue(label: "blocking-io")`), lalu jembatani menggunakan `withCheckedContinuation`.

### 3. Continuation Leaks & Multiple Resumptions

Ketika menggunakan `withCheckedContinuation` atau `withCheckedThrowingContinuation`, runtime menuntut invariant absolut: **Continuation harus di-resume tepat satu kali (*exactly once*)**.

* Jika Anda lupa memanggil `continuation.resume()`, Task akan tertahan selamanya di memori (Leak).
* Jika Anda memanggil `continuation.resume()` dua kali, aplikasi akan seketika mengalami fatal crash (*EXC_BAD_INSTRUCTION*).

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mengabaikan Task Cancellation di Komputasi Berat

```swift
// SALAH: Task looping berjalan terus meski View sudah didestroy
.task {
    for item in 0..<1_000_000 {
        processHeavyMath(item)
    }
}

// BENAR: Menyisipkan cooperative checking secara berkala
.task {
    for item in 0..<1_000_000 {
        if item % 1000 == 0 {
            // Segera keluar dari perulangan jika View unmounted
            guard !Task.isCancelled else { break }
        }
        processHeavyMath(item)
    }
}
```

### Kesalahan 2: Membungkus Pemanggilan State SwiftUI di Luar `@MainActor`

```swift
// SALAH (Swift 6 Compile Error):
nonisolated func processNetworkData() async {
    let result = await api.fetch()
    // ERROR: Mutation of MainActor-isolated property from non-isolated context
    myViewModel.items = result 
}

// BENAR: Isolasi eksplisit pada target mutasi
@MainActor
func updateState(with result: [Item]) {
    myViewModel.items = result
}
```

### Kesalahan 3: Penggunaan `Task.detached` yang Berlebihan

Banyak developer mengira `Task.detached` adalah padanan langsung dari `DispatchQueue.global().async`. Faktanya, `Task.detached` mematikan semua context inheritance: menurunkan prioritas tak terkontrol, menghilangkan Task-Local values, dan berpotensi memicu *priority inversions*. Gunakan `Task(priority:_:)` standar kecuali Anda benar-benar memiliki alasan arsitektural yang fundamental.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Mode Swift 6 Strict Concurrency:** Aktifkan setting build Xcode `SWIFT_STRICT_CONCURRENCY` ke level `Complete`. Tangani seluruh peringatan Sendable dan data-race safety sebelum masuk ke production.
2. **Prioritaskan Structural Concurrency:** Gunakan `async let` untuk operasi konkuren fixed-size, dan `withTaskGroup` untuk operasi paralel dynamic-size. Hindari instansiasi `Task { }` liar jika parent scope dapat menunggu hasilnya.
3. **Optimalkan Granularitas Actor:** Jangan membungkus seluruh aplikasi ke dalam satu `GlobalActor` raksasa (ini hanya memindahkan bottleneck serialisasi queue lama ke model baru). Pisahkan actor berdasarkan *bounded data domain*.
4. **Deklarasikan Dependency sebagai Interface Sendable:** Seluruh repository atau abstraction service yang melintasi context layer wajib berupa `Actor` atau protokol yang inherit dari `Sendable`.
5. **Gunakan `.task(id:)` sebagai Declarative Trigger:** Manfaatkan parameter `id` pada modifier `.task(id: ...)` untuk merespons perubahan state selektif alih-alih menggunakan listener imperatif `onChange(of: ...) { Task { ... } }`.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Menghindari Context Switching Berlebihan (Actor Hops)

Setiap pemanggilan dari satu actor ke actor lain (termasuk `@MainActor`) memerlukan *Actor Context Hop*, yang melibatkan antrean mailbox dan pelepasan thread execution. 

```swift
// TIDAK EFISIEN: 1000 kali actor hopping bolak-balik antara Worker dan MainActor
@MainActor
func updateList(items: [RawData]) async {
    for raw in items {
        let transformed = await backgroundTransformer.process(raw) // Hop ke Background Actor
        self.processedItems.append(transformed)                    // Hop kembali ke MainActor
    }
}

// OPTIMAL: Lakukan batch transform di background actor, hop HANYA SATU KALI
@MainActor
func updateListOptimized(items: [RawData]) async {
    let transformedBatch = await backgroundTransformer.processBatch(items) // 1 Hop
    self.processedItems.append(contentsOf: transformedBatch)               // Tetap di MainActor
}
```

### Penjadwalan Prioritas Task (Priority Escalation)

Swift Concurrency mendukung *Cooperative Priority Escalation*. Jika sebuah low-priority task (misal: `background`) menghasilkan dependency yang ditunggu (`await`) oleh sebuah UI Task (`userInitiated` di MainActor), runtime Swift akan menaikkan prioritas task background tersebut secara dinamis untuk mencegah *Priority Inversion* pada CPU cores scheduler.

---

## SEKSI 16 — KEAMANAN & HARDENING

Model konkurensi Swift dirancang untuk mencegah eksploitasi keamanan tingkat rendah yang sering terjadi di C/C++:

* **Pencegahan Undefined Behavior & Memory Corruption:** Race conditions pada level memori adalah salah satu vektor serangan paling umum (Use-After-Free, partial-write reads). Di Swift 6, data race safety dijamin secara statis pada fase kompilasi. Jika sebuah class tidak `Sendable`, Anda secara fisik tidak dapat mengompilasi kode yang membagikan instance tersebut ke multi-thread.
* **Checked Throwing Continuations:** Jangan gunakan `withUnsafeContinuation` di layer aplikasi enterprise kecuali performa siklus CPU fraksional sangat genting dan kode telah diaudit formal. Selalu gunakan `withCheckedContinuation`, yang menyisipkan *runtime traps* jika terjadi pelanggaran fatal seperti resumption ganda (*double resumption*).
* **Sanitasi Data di Isolasi Actor:** Amankan layer kriptografi dan penanganan access token JWT dalam Actor terisolasi khusus. Pastikan token string tidak bocor ke log non-isolated melalui logging interpolation yang tak terkendali.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Menelusuri Konkurensi dengan Apple Instruments

Xcode menyediakan instrumen khusus: **Swift Concurrency Template**:
1. Buka Instruments (`Cmd + I` di Xcode) -> Pilih **Swift Concurrency**.
2. **Swift Tasks View:** Menganalisis jumlah Task yang aktif, Task Creation graph, durasi *Suspended*, durasi *Running*, dan Task yang mengalami *Leak*.
3. **Swift Actor View:** Memvisualisasikan *Mailbox Contention*. Jika visualisasi antrean actor berwarna merah tebal, ini menandakan actor tersebut mengalami saturasi beban dan menjadi bottleneck throughput.

### Logging Terstruktur Terintegrasi Concurrency

Gunakan `OSLog` (Apple Unified Logging System) yang bersifat thread-safe dan membedakan privasi data secara native:

```swift
import OSLog

actor NetworkPipelineManager {
    private let logger = Logger(subsystem: "com.enterprise.app", category: "Concurrency")

    func executeRequest(id: String) async throws {
        // Menggunakan Logger thread-safe tanpa locking overhead
        logger.debug("Task initiated execution for ID: \(id, privacy: .public)")
        
        let taskID = Task.currentPriority
        logger.info("Executing at priority: \(taskID.rawValue)")
    }
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

| Syntax / Modifier | Konteks Penggunaan | Perilaku Pembatalan (Cancellation) |
| :--- | :--- | :--- |
| `await expression` | Suspension point | Memungkinkan interleaving; melepaskan worker thread |
| `.task { ... }` | SwiftUI View Lifecycle | Dibatalkan otomatis saat View dilepas dari hierarki |
| `.task(id: token) { ... }`| SwiftUI State Change | Membatalkan task aktif dan spawn ulang saat token berubah |
| `Task { ... }` | Unstructured Scope | Manual (`task.cancel()`); mewarisi isolation domain pemanggil |
| `Task.detached { ... }`| Unstructured Background| Manual (`task.cancel()`); **tidak** mewarisi isolation/priority |
| `withTaskGroup { ... }`| Structured Concurrency | Otomatis propagate ke semua child tasks jika parent dibatalkan |
| `Task.isCancelled` | Boolean Check | Polling pembatalan non-throwing untuk custom resource cleanup |
| `try Task.checkCancellation()`| Strict Checkpoint | Seketika melempar `CancellationError` jika task dibatalkan |
| `@MainActor` | Attribute Isolation | Memaksa eksekusi kode berjalan eksklusif di Main RunLoop |

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Pilihan Ganda (Tingkat Basic)

#### Q1. Apa perbedaan paling fundamental antara `Task.sleep` dan `Thread.sleep`?
A. `Task.sleep` membutuhkan alokasi memori GCD yang lebih besar.  
B. `Task.sleep` menangguhkan eksekusi tanpa memblokir thread worker, sedangkan `Thread.sleep` memblokir thread OS yang sedang berjalan.  
C. `Task.sleep` hanya dapat dieksekusi di dalam Main Actor.  
D. `Thread.sleep` secara otomatis memicu `CancellationError` saat View unmount.  
*Jawaban:* **B**. `Task.sleep` mendaftarkan timer kelanjutan (continuation) dan membebaskan thread worker kembali ke cooperative pool, sementara `Thread.sleep` membekukan thread sistem seutuhnya.

#### Q2. Kapan modifier `.task` pada SwiftUI View otomatis membatalkan eksekusi internal closure-nya?
A. Hanya ketika aplikasi masuk ke background.  
B. Saat terjadi error runtime yang tidak tertangkap.  
C. Ketika View tersebut dilepas (*unmounted*) dari hierarki render tree aktif.  
D. Modifier `.task` tidak pernah membatalkan proses secara otomatis.  
*Jawaban:* **C**. Modifier `.task` mengikat siklus hidup komputasi secara deklaratif ke masa keberadaan View di layar.

#### Q3. Manakah deklarasi tipe data yang secara otomatis memenuhi protokol `Sendable` tanpa deklarasi manual?
A. Class bertipe `final` dengan satu variabel mutable `var count: Int`.  
B. Struct yang seluruh propertinya bertipe data primitif (seperti `Int`, `String`, `Double`).  
C. Protocol inheritance standard.  
D. Objective-C class yang mewarisi `NSObject`.  
*Jawaban:* **B**. Value types (struct) yang propertinya seluruhnya merupakan tipe `Sendable` secara implisit dianggap conform ke `Sendable` oleh compiler.

#### Q4. Apa yang dimaksud dengan konsep Cooperative Cancellation pada Swift Concurrency?
A. Sistem Operasi akan langsung mematikan thread yang mengeksekusi Task.  
B. Task tidak dihentikan paksa; runtime hanya menyetel status pembatalan, dan kode bertugas memeriksanya secara sadar.  
C. Pembatalan otomatis me-restart proses dari baris pertama.  
D. Task menunggu seluruh parent actor menyelesaikan antrean mailbox sebelum berhenti.  
*Jawaban:* **B**. Pembatalan dalam Swift bersifat kooperatif, menuntut developer untuk mengecek `Task.isCancelled` atau `Task.checkCancellation()`.

#### Q5. Modifier `.task(id: value)` akan mengeksekusi ulang closure jika:
A. Terjadi rotasi layar perangkat.  
B. Nilai parameter `value` berubah secara ekuivalensi (berdasarkan `Equatable`).  
C. Memori internal device mencapai ambang batas kritis.  
D. Main RunLoop mengalami frame dropping.  
*Jawaban:* **B**. Parameter `id` memicu siklus: batalkan task lama -> tunggu -> buat task baru jika nilai identitasnya mengalami mutasi.

---

### Soal Pilihan Ganda (Tingkat Intermediate)

#### Q6. Apa konsekuensi arsitektural dari fenomena *Actor Reentrancy*?
A. Actor dapat mengalami deadlock jika dua method dipanggil bersamaan dari UI.  
B. State internal actor dapat termutasi di antara titik `await` oleh pemanggilan method lain yang menyisip di mailbox.  
C. Actor berhenti memproses pesan dan langsung mendestruksi memory pool.  
D. Kompiler Swift 6 akan menolak kompilasi seluruh method actor yang bersifat async.  
*Jawaban:* **B**. Karena actor melepaskan mailbox-nya saat `await` (suspend), panggilan luar lain dapat dieksekusi sebelum method pertama melanjutkan operasinya pasca-suspend.

#### Q7. Mengapa penggunaan `Task.detached` di dalam SwiftUI View body dianggap sebagai *code smell* (buruk)?
A. Karena `Task.detached` tidak dapat mengeksekusi kode bertipe async/await.  
B. Karena `Task.detached` memutus isolasi `@MainActor`, Task-Local values, dan siklus pembatalan hierarki View.  
C. Karena `Task.detached` memperlambat rendering ProMotion secara artifisial.  
D. Karena `Task.detached` memaksa operasi berjalan di Single Thread POSIX.  
*Jawaban:* **B**. `Task.detached` melepaskan semua inheritance konteks, meningkatkan risiko leak dan UI state synchronization errors.

#### Q8. Apa yang terjadi pada level sistem jika Anda memanggil `continuation.resume(returning:)` dua kali pada `withCheckedContinuation`?
A. Pemanggilan kedua akan diabaikan secara diam-diam oleh runtime.  
B. Nilai kembalian kedua akan menimpa nilai pertama di heap.  
C. Terjadi fatal runtime crash (*assertion failure*) untuk mencegah state corruption.  
D. Thread worker akan mengalami sleep permanen selama 60 detik.  
*Jawaban:* **C**. Checked Continuations memiliki pelindung internal yang meledakkan runtime trap jika invariant *resume-exactly-once* dilanggar.

#### Q9. Model alokasi memori stack frame untuk async function di Swift berbeda dari fungsi sinkron klasik karena:
A. Frame dialokasikan di register kernel secara langsung.  
B. Frame dialokasikan secara dinamis di Heap sebagai async task context untuk mempertahankan nilai variabel saat suspension.  
C. Frame async tidak memerlukan memori RAM sama sekali.  
D. Frame async disimpan langsung di storage flash SSD internal.  
*Jawaban:* **B**. Karena eksekusi dapat di-suspend dan dilanjutkan di thread worker lain, frame lokal disimpan di heap alih-alih thread call stack biasa.

#### Q10. Di bawah sistem Swift 6 Strict Concurrency, apa yang harus Anda lakukan jika compiler memunculkan error: *"Capture of 'self' in an isolated closure risks concurrent access"*?
A. Mengubah deklarasi objek menjadi `unsafeUnowned`.  
B. Menandai class dengan `@unchecked Sendable` tanpa memeriksa thread safety.  
C. Mengisolasi class tersebut ke `@MainActor`, mengonversinya menjadi `actor`, atau menjadikannya struct immutabel bertipe `Sendable`.  
D. Menghapus konfigurasi `SWIFT_STRICT_CONCURRENCY` dari build settings.  
*Jawaban:* **C**. Menjamin integritas tipe data melalui isolasi actor atau value semantics adalah pendekatan yang valid dan aman di Swift 6.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: Resilient Multi-Source Search & Aggregator Engine

**Tujuan Praktikum:**
Bangun sebuah antarmuka pencarian dokumen di SwiftUI yang mengeksekusi *concurrent scatter-gather pattern* menggunakan Swift Concurrency tingkat lanjut.

**Spesifikasi Persyaratan Sistem:**
1. **Antarmuka Pengguna (SwiftUI):**
   * Gunakan modifier `.searchable` untuk menerima input query teks dari pengguna.
   * Hubungkan input search query ke pemanggilan data menggunakan `.task(id: query)`.
   * Terapkan debouncing kooperatif: Jika pengguna mengetik huruf baru dalam tempo < 300 milidetik, batalkan query network yang sedang terbang sebelum diproses.
2. **Concurrent Scatter-Gather Engine:**
   * Buat service bernama `DataAggregatorActor`.
   * Saat query valid diterima, sistem harus mengeksekusi pencarian ke **3 mock engine independen secara paralel** menggunakan `withThrowingTaskGroup`:
     1. Local Cache Engine (simulasi delay 50ms)
     2. Cloud Document Service (simulasi delay 400ms)
     3. External Archive Endpoint (simulasi delay 800ms)
   * Setiap child task harus menghasilkan array `[SearchResultItem]`.
   * Jika satu remote provider melempar error koneksi, aggregator tidak boleh gagal total; ia harus menangani error tersebut secara elegan dan tetap menyajikan hasil dari provider yang berhasil.
3. **Cancellation Resilience:**
   * Jika user menghapus teks pencarian atau mengganti keyword saat proses scatter-gather tengah berjalan, seluruh child tasks di dalam `withThrowingTaskGroup` harus seketika menerima sinyal pembatalan kooperatif dan memotong konsumsi CPU.
4. **Swift 6 Strict Compliance:**
   * Proyek harus terbebas 100% dari warning/error dengan flags Xcode `SWIFT_STRICT_CONCURRENCY=complete`.
   * Semua struct data transfer (`SearchResultItem`) wajib conform ke `Sendable` dan `Identifiable`.

**Indikator Keberhasilan:**
* Log console menampilkan eksekusi 3 provider secara paralel di thread worker yang berbeda.
* Indikator `ProgressView` muncul mulus tanpa patah-patah pada frame rate 60/120 FPS.
* Saat user mengetik cepat (misal: "S", "SW", "SWI", "SWIFT"), terminal secara akurat mencatat pembatalan (*graceful cancellation*) dari 3 task group sebelumnya tanpa ada *race condition* atau data visual yang tumpang-tindih di UI List.