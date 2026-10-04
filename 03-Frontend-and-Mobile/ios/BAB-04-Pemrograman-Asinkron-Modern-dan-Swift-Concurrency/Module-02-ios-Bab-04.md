# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Pemrograman Asinkron Modern dan Swift Concurrency**  
**Kategori: 03-Frontend-and-Mobile (iOS)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis dan Mengoptimalkan Runtime Swift Concurrency:** Membedah cara kerja *Cooperative Thread Pool*, alokasi *Async Task Frames* pada heap, serta mitigasi risiko *thread starvation*.
2. **Mengatasi Masalah Actor Reentrancy:** Mengidentifikasi celah kerentanan *state corruption* akibat suspensi lintas-*await* boundary pada Actor dan menerapkan pola desain atomik.
3. **Mengimplementasikan Custom Serial Executor:** Membangun *custom executor* (berdasarkan Swift 5.9+ SE-0392) untuk mengintegrasikan isolasi Actor ke *dedicated dispatch queue* atau thread tertentu secara deterministik.
4. **Mendesain Stream Reaktif Enterprise dengan `AsyncStream`:** Merekayasa pipeline data *backpressure-aware*, menangani terminasi siklus hidup, dan mencegah *memory leak* pada *continuation closures*.
5. **Menjembatani Legacy Asynchronous Codebase:** Mengintegrasikan GCD (`DispatchQueue`), `OperationQueue`, dan API berbasis C-callback ke Swift Concurrency menggunakan `CheckedContinuation` dan `withTaskCancellationHandler` tanpa memicu *continuation leak* atau *double resumption*.
6. **Menerapkan Strict Concurrency (Swift 6 Ready):** Mengeliminasi data race statis menggunakan *Sendable enforcement*, *Region-based Isolation Analysis*, dan `@preconcurrency`.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
*   Sintaks dasar Swift Concurrency: `async/await`, `Task`, `TaskGroup`, `actor`, dan atribut `@MainActor`.
*   Konsep dasar *Grand Central Dispatch* (GCD): antrean serial/konkuren, QoS (*Quality of Service*), *Deadlock*, dan *Thread Explosion*.
*   Penggunaan pointer dasar, ARC (*Automatic Reference Counting*), siklus hidup memori (*strong, weak, unowned*), dan struktur penanganan *Error* di Swift.
*   Tooling: Xcode 15+ (Swift 5.9+) atau Xcode 16 (Swift 6) dengan flag kompilasi `-strict-concurrency=complete`.

---

## 3. Concept & Internal Architecture

### 3.1 Cooperative Thread Pool vs. GCD Thread Explosion

Pada arsitektur konkurensi legacy (GCD), setiap kali sebuah antrean konkuren terblokir (misalnya menunggu I/O atau penguncian sinkron), libdispatch dapat membuat thread baru untuk mempertahankan throughput. Dalam sistem kompleks dengan ratusan dependensi asinkron, hal ini memicu **Thread Explosion**:

```
GCD: 
[Task 1 (Blocked)] -> Spawns Thread 1
[Task 2 (Blocked)] -> Spawns Thread 2
...
[Task N (Blocked)] -> Spawns Thread 100+ -> High Context Switch Overhead + 1MB Stack Memory per Thread Exhaustion
```

Swift Concurrency menyelesaikan masalah ini secara arsitektural melalui **Cooperative Thread Pool**:
*   **Batas Thread Konkuren:** Runtime membatasi jumlah thread pekerja aktif secara deterministik sesuai dengan jumlah *logical CPU cores* (misalnya: 6 core = 6 thread pekerja).
*   **Non-blocking Suspension:** Ketika sebuah `Task` mencapai titik suspensi (`await`), thread underlying **tidak pernah diblokir**. Sebaliknya, fungsi saat ini ditangguhkan (*suspended*), status eksekusi dikemas ke dalam *Continuation*, dan thread pekerja tersebut langsung dilepaskan untuk mengeksekusi *Task* lain yang siap berjalan (*runnable*).

```
Swift Concurrency:
Core 0: [ Worker Thread 1 ] <--- Task A yields ---> [ Executes Task B ]
Core 1: [ Worker Thread 2 ] <--- Task C yields ---> [ Executes Task D ]
(Jumlah thread stabil = Kapasitas Core CPU)
```

### 3.2 Task Frames & Heap Allocation (Continuation Passing Style)

Fungsi sinkron konvensional mengalokasikan memori variabel lokal pada thread stack frame. Ketika fungsi memanggil fungsi lain, frame baru ditumpuk ke atas stack.

Fungsi `async` tidak dapat menggunakan stack murni karena fungsi tersebut dapat ditangguhkan dan dilanjutkan kemudian pada thread yang berbeda. Oleh karena itu, runtime Swift menggunakan mekanisme **Async Frame Allocation**:
1. Saat fungsi `async` dipanggil, runtime mengalokasikan **Task Frame** di memori heap (dikelola oleh runtime allocator `swift_task_alloc`).
2. Task Frame menyimpan variabel lokal yang harus bertahan melintasi suspensi point (`await`).
3. Ketika suspensi terjadi, stack frame saat ini di-*unwind* ke thread pool, namun *Task Frame* tetap aman di heap.
4. Saat suspensi selesai (misalnya respons jaringan diterima), scheduler mengambil *Task Frame* dari heap dan menjadwalkannya pada thread pekerja yang tersedia di pool.

```
       Stack (Transient Execution)                 Heap (Async Task Execution Context)
+---------------------------------------+       +---------------------------------------+
| Thread Worker 1:                      |       | Task Frame Root:                      |
| [ Current executing non-async frame ] |       | - Task ID, Priority, Local Variables  |
| [ swift_task_switch context ]         | ----> | - Continuation State Machine          |
+---------------------------------------+       | - Frame Data (Preserved across await) |
                                                +---------------------------------------+
```

### 3.3 Actor Mailbox & Reentrancy Mechanics

Secara internal, `actor` di Swift memproteksi state miliknya menggunakan mekanisme antrean pesan serial (*Actor Mailbox*) dan bukan menggunakan lock konvensional (seperti `os_unfair_lock` atau `pthread_mutex`) untuk pemanggilan asinkron.

#### Cara Kerja Mailbox:
1. Pemanggilan metode isolasi actor dari luar batas actor dikemas menjadi sebuah `Job`.
2. `Job` dimasukkan ke dalam antrean mailbox actor (`DefaultActor`).
3. Executor milik actor memproses `Job` satu per satu.

#### Kerentanan: Actor Reentrancy
Actor di Swift bersifat **reentrant**. Jika sebuah metode actor mencapai titik suspensi (`await`), actor **melepaskan eksekusi thread** sehingga mailbox dapat memproses `Job` berikutnya yang antre. 

Konsekuensi arsitektural: **State dari actor dapat berubah di antara sebelum titik `await` dan sesudah titik `await`.**

```
Timeline Actor:
Time t0: Task A memanggil actor.updateData() -> Memeriksa cache (State: Valid)
Time t1: Task A mengeksekusi `await networkService.fetch()` -> Task A SUSPENDED.
Time t2: Task B masuk mailbox -> Memanggil actor.clearCache() -> (State diubah menjadi: Empty).
Time t3: Task A RESUMED dari fetch().
Time t4: Task A melanjutkan eksekusi dengan asumsi State masih "Valid" -> CRASH / DATA CORRUPTION!
```

### 3.4 Custom Serial Executors (SE-0392)

Mulai Swift 5.9, developer dapat menggantikan antrean runtime default milik actor dengan *Custom Serial Executor*. Fitur ini memungkinkan Anda memetakan isolasi actor ke:
*   Sebuah `DispatchQueue` serial spesifik yang telah ada (berguna untuk sinkronisasi dengan library legacy berbasis C/Objective-C).
*   Sebuah thread khusus real-time (misalnya: pemrosesan audio tingkat rendah).

Protokol internal yang terlibat:
*   `SerialExecutor`: Menerima job eksekusi (`Job`) dan menjalankannya secara serial.
*   Metode `unownedSerialExecutor`: Aksesor kustom pada actor untuk memberitahukan runtime executor mana yang harus mengontrol mailbox.

---

## 4. Why & What

| Fitur / Masalah | Grand Central Dispatch (GCD) | Swift Concurrency Modern |
| :--- | :--- | :--- |
| **Pencegahan Data Race** | Manual (Developer wajib disiplin menggunakan serial queue/locks). Rentan *human error*. | Statis via Compiler (*Sendable checking*, *Actor Isolation*, *Region-based Isolation*). |
| **Alokasi Thread** | Dinamis tidak terbatas (Rentan *Thread Explosion* dan memori OOM). | Terbatas (*Cooperative Thread Pool* terikat pada jumlah Core CPU). |
| **Penanganan Pembatalan (*Cancellation*)** | Manual via flag boolean atau `DispatchWorkItem.cancel()` (Sulit dipropagasi ke child thread). | Terintegrasi secara kooperatif melalui pohon hierarki (*Task Cancellation Tree*). |
| **Kontekstual Eksekusi** | Stack frame terikat pada Thread OS fisik. | *Task Frame* dialokasikan di heap, berpindah thread secara transparan saat suspensi. |
| **Sinkronisasi State Mutabel** | Mutex, NSLock, GCD Serial Queue (Dapat memicu *priority inversion* dan *deadlock*). | `actor` primitives dengan *mailbox execution* dan penghindaran *deadlock* struktural. |

---

## 5. How (Workflow Detail)

### 5.1 Siklus Hidup Eksekusi Task dan State Machine

```
[ Task Lifecycle ]
  1. Creation (Task { ... }) 
        |
        v
  2. Enqueued to Cooperative Pool (Job Scheduled)
        |
        v
  3. Execution on Worker Thread (Running)
        |
        +-----> Suspended on `await`? 
        |           |
        |           v (Save Task Frame to Heap, Yield Worker Thread)
        |       [ Waiting for Continuation / I/O ]
        |           |
        |           v (Continuation Resumed)
        +-----< Re-enqueued to Cooperative Pool
        |
        v
  4. Task Completion (Success / Throws Failure)
        |
        v
  5. Deallocation of Task Frame (swift_task_dealloc)
```

### 5.2 Alur Propagasi Pembatalan Hierarkis (*Cancellation Cascade*)

1. `Task` induk dibatalkan via `.cancel()`.
2. Status `isCancelled` dari Task induk menjadi `true`.
3. Sinyal pembatalan dipropagasikan ke seluruh `TaskGroup` atau *Child Tasks* secara rekursif ke bawah pohon hierarki.
4. Operasi asinkron yang sedang menunggu suspensi point menangkap status ini melalui:
   *   Pemeriksaan periodik `Task.isCancelled`.
   *   Pemanggilan metode `try Task.checkCancellation()`, yang langsung melempar `CancellationError`.
   *   Penanganan interupsi I/O via `withTaskCancellationHandler(operation:onCancel:)`.

---

## 6. Analogy & Diagram ASCII

### 6.1 Analogi Operator Dapur Restoran

*   **GCD (Model Lama):** Setiap kali ada pesanan steak yang butuh dipanggang 20 menit, restoran menyewa satu koki baru khusus untuk berdiri diam di depan panggangan menunggu daging matang. Ketika ada 100 pesanan steak, ada 100 koki di dapur kecil saling bertabrakan (*Thread Explosion*), menghabiskan gaji dan ruang dapur (*OOM / Latency Overhead*).
*   **Swift Concurrency (Cooperative):** Restoran hanya mempekerjakan 4 koki tetap sesuai jumlah kompor yang ada (*Cooperative Pool = CPU Cores*). Ketika seorang koki menaruh steak di atas panggangan (`await`), koki tersebut mencatat timer di kertas pesanan (*Continuation Heap Frame*), lalu langsung memproses racikan salad untuk pesanan lain. Begitu timer steak berbunyi, salah satu koki yang sedang luang akan mengangkat steak tersebut.

### 6.2 Arsitektur Custom Serial Executor

```
+-----------------------------------------------------------------------+
|                            ACTOR CONTEXT                              |
|                                                                       |
|  actor EnterpriseOrderEngine {                                        |
|      nonisolated var unownedSerialExecutor: UnownedSerialExecutor {   |
|          myCustomQueue.asUnownedSerialExecutor()                       |
|      }                                                                |
|  }                                                                    |
+-----------------------------------------------------------------------+
                                  |
                                  | Enqueue Jobs
                                  v
+-----------------------------------------------------------------------+
|                    CUSTOM SERIAL EXECUTOR LAYER                       |
|                                                                       |
|  DispatchQueue(label: "com.enterprise.order-engine.queue")             |
|                                                                       |
|  [ Job 1: execute() ] -> [ Job 2: execute() ] -> [ Job 3: execute() ] |
+-----------------------------------------------------------------------+
                                  |
                                  | Executes deterministically on
                                  v
+-----------------------------------------------------------------------+
|                        OS DISPATCH WORKER                             |
|                   (Dedicated Serial Execution)                        |
+-----------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Bahaya Actor Reentrancy & Mitigasi Atomik

Contoh ini menunjukkan celah keamanan reentrancy pada transfer saldo, serta implementasi solusinya menggunakan *Transaction Lock State Machine*.

```swift
import Foundation

// MARK: - KODE RENTAN (Vulnerable Actor Reentrancy)
actor VulnerableBankVault {
    private var balance: Double = 1000.0

    func withdraw(amount: Double) async -> Bool {
        // Titik A: Validasi
        guard balance >= amount else {
            return false
        }

        // Titik Suspensi: Simulasi otentikasi jaringan ke server fraud check
        // Selama suspensi ini, eksekusi lain BISA masuk ke withdraw()!
        try? await Task.sleep(nanoseconds: 500_000_000) // 500ms

        // Titik B: Eksekusi state mutation tanpa re-validasi
        balance -= amount
        return true
    }

    func getBalance() -> Double { balance }
}

// MARK: - KODE AMAN (Atomicity via Transaction Locking Pattern)
actor SecureBankVault {
    private var balance: Double = 1000.0
    private var isTransactionPending: Bool = false

    enum VaultError: Error {
        case transactionInProgress
        case insufficientFunds
    }

    func withdraw(amount: Double) async throws -> Double {
        // Cegah eksekusi paralel masuk ke dalam critical section
        while isTransactionPending {
            // Suspensi kooperatif hingga transaksi sebelumnya rampung
            await Task.yield()
        }

        guard balance >= amount else {
            throw VaultError.insufficientFunds
        }

        // Kunci critical section
        isTransactionPending = true

        defer {
            // Pastikan lock selalu dilepas saat keluar dari fungsi
            isTransactionPending = false
        }

        // Titik Suspensi Eksternal
        try await Task.sleep(nanoseconds: 500_000_000)

        // Mutasi aman dari tumpang-tindih transaksi lain
        balance -= amount
        return balance
    }

    func getBalance() -> Double { balance }
}
```

### 7.2 Practical Example: Enterprise-Grade Socket Stream Router dengan Custom Executor

Implementasi ini menggabungkan:
1. Custom Serial Executor (`SerialExecutor`) terikat pada antrean background berprioritas tinggi.
2. Jembatan *low-level C-style socket/event-driven* ke `AsyncStream` modern.
3. Propagasi pembatalan dan pembersihan memori deterministik.

```swift
import Foundation

// MARK: - 1. Custom Serial Executor Implementation
final class DedicatedDispatchExecutor: SerialExecutor {
    private let queue: DispatchQueue

    init(queue: DispatchQueue) {
        self.queue = queue
    }

    public func enqueue(_ job: UnownedJob) {
        queue.async {
            job.runSynchronously(on: self.asUnownedSerialExecutor())
        }
    }

    public func asUnownedSerialExecutor() -> UnownedSerialExecutor {
        UnownedSerialExecutor(complexEquality: self)
    }
}

// MARK: - 2. Enterprise Real-Time Ingestion Engine
actor IngestionEngine {
    private let dedicatedQueue = DispatchQueue(label: "com.enterprise.ingestion.serial-queue", qos: .userInteractive)
    private let customExecutor: DedicatedDispatchExecutor

    // Kaitkan Actor dengan Custom Serial Executor (SE-0392)
    nonisolated var unownedSerialExecutor: UnownedSerialExecutor {
        customExecutor.asUnownedSerialExecutor()
    }

    private var packetBuffer: [Data] = []
    private var continuation: AsyncStream<Data>.Continuation?

    init() {
        self.customExecutor = DedicatedDispatchExecutor(queue: dedicatedQueue)
    }

    /// Menghasilkan stream konsumsi data real-time dengan proteksi backpressure
    func startPacketStream() -> AsyncStream<Data> {
        AsyncStream(Data.self, bufferingPolicy: .bufferingNewest(1000)) { [weak self] streamContinuation in
            Task { [weak self] in
                await self?.registerContinuation(streamContinuation)
            }

            streamContinuation.onTermination = { @Sendable [weak self] reason in
                Task { [weak self] in
                    await self?.handleTermination(reason)
                }
            }
        }
    }

    private func registerContinuation(_ continuation: AsyncStream<Data>.Continuation) {
        self.continuation = continuation
    }

    private func handleTermination(_ reason: AsyncStream<Data>.Continuation.Termination) {
        #if DEBUG
        print("Stream dihentikan dengan alasan: \(reason)")
        #endif
        self.continuation = nil
        self.packetBuffer.removeAll()
    }

    /// Metode yang menerima byte data dari driver C/Network POSIX socket
    func ingestRawPacket(_ data: Data) {
        packetBuffer.append(data)
        
        // Teruskan data ke subscriber aktif
        if let continuation = continuation {
            let yieldResult = continuation.yield(data)
            switch yieldResult {
            case .enqueued(let remaining):
                if remaining == 0 {
                    // Buffer hampir penuh, log tanda backpressure
                }
            case .dropped(let droppedData):
                #if DEBUG
                print("PERINGATAN: Buffer penuh! Ukuran data terbuang: \(droppedData.count) bytes")
                #endif
            case .terminated:
                self.continuation = nil
            @unknown default:
                break
            }
        }
    }

    func flush() -> [Data] {
        let current = packetBuffer
        packetBuffer.removeAll()
        return current
    }
}

// MARK: - 3. Legacy Socket Bridge Example
final class LegacyCStyleSocketConnector: @unchecked Sendable {
    private let engine: IngestionEngine
    private var isRunning: Bool = false

    init(engine: IngestionEngine) {
        self.engine = engine
    }

    func simulateIncomingTraffic() {
        isRunning = true
        // Mensimulasikan callback dari C-library / POSIX Socket
        DispatchQueue.global(qos: .default).async { [weak self] in
            guard let self = self else { return }
            while self.isRunning {
                let dummyPayload = "PACKET_HEADER_\(UUID().uuidString)".data(using: .utf8)!
                
                // Mengirim payload ke ingestion engine actor
                Task {
                    await self.engine.ingestRawPacket(dummyPayload)
                }
                
                Thread.sleep(forTimeInterval: 0.05) // Emulasi 20 packets/sec
            }
        }
    }

    func disconnect() {
        isRunning = false
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: High-Frequency Crypto/Stock Trading Order Book Stream (Binance/Robinhood Tier)

#### Permasalahan Arsitektur
Aplikasi enterprise FinTech menerima 500–1.000 pembaruan *Order Book Depth* per detik melalui WebSocket kompresi binary. Kebutuhan sistem:
1. Parsing payload binary terisolasi dari main thread.
2. Perhitungan order book depth (bid/ask aggregate) harus *in-order* dan bebas *race-condition*.
3. Render visual UI harus stabil pada 60/120 FPS tanpa frame drop (*micro-stuttering*), yang berarti Main Thread tidak boleh dibanjiri 1.000 event/detik.

#### Solusi Arsitektur

```
[ WebSocket (Binary Stream) ] 
              |
              v (Non-blocking Ingestion)
[ NetworkIngestionActor (Background QoS) ]
              |
              v (Throttled/Batching AsyncSequence via Custom Algorithm)
[ OrderBookAggregatorActor (Custom Serial Executor) ]
              |
              | Yields aggregated snapshot every 16ms (Display Sync)
              v
[ @MainActor ViewModel ] ---> [ SwiftUI / Metal Rendering Engine ]
```

#### Implementasi Produksi

```swift
import Foundation

// Snapshot Model yang immutable dan Sendable
public struct OrderBookSnapshot: Sendable, Equatable {
    public let timestamp: UInt64
    public let topBids: [(price: Double, quantity: Double)]
    public let topAsks: [(price: Double, quantity: Double)]
}

// Aggregator Engine dengan Throttling Internal
public actor OrderBookAggregator {
    private var rawBids: [Double: Double] = [:]
    private var rawAsks: [Double: Double] = [:]
    private var isFlushing: Bool = false

    public init() {}

    public func updateBid(price: Double, quantity: Double) {
        if quantity == 0 {
            rawBids.removeValue(forKey: price)
        } else {
            rawBids[price] = quantity
        }
    }

    public func updateAsk(price: Double, quantity: Double) {
        if quantity == 0 {
            rawAsks.removeValue(forKey: price)
        } else {
            rawAsks[price] = quantity
        }
    }

    /// Menghasilkan stream ter-throttle untuk konsumsi UI (Maksimum 60 update per detik)
    public func createUIThrottledStream() -> AsyncStream<OrderBookSnapshot> {
        AsyncStream { continuation in
            let throttleTask = Task {
                while !Task.isCancelled {
                    try? await Task.sleep(nanoseconds: 16_666_667) // ~60 Hz (16.6ms)
                    
                    let snapshot = self.generateCurrentSnapshot()
                    continuation.yield(snapshot)
                }
            }

            continuation.onTermination = { @Sendable _ in
                throttleTask.cancel()
            }
        }
    }

    private func generateCurrentSnapshot() -> OrderBookSnapshot {
        let sortedBids = rawBids.sorted { $0.key > $1.key }.prefix(20).map { ($0.key, $0.value) }
        let sortedAsks = rawAsks.sorted { $0.key < $1.key }.prefix(20).map { ($0.key, $0.value) }
        
        return OrderBookSnapshot(
            timestamp: DispatchTime.now().uptimeNanoseconds,
            topBids: Array(sortedBids),
            topAsks: Array(sortedAsks)
        )
    }
}
```

---

## 9. Trade-offs: Analisis Konsekuensi Keputusan Arsitektur

| Pendekatan | Keuntungan | Biaya / Trade-off | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Pure Actor Isolation** | Tidak mungkin terjadi memory corruption; compiler menggaransi bebas data-race. | *Overhead context switching* dan potensi *Actor Reentrancy bug* jika ada pemanggilan `await` di tengah mutasi state. | Logika bisnis umum, autentikasi, layer caching data. |
| **Custom Serial Executor** | Memaksa determinisme eksekusi ke thread/queue tertentu; interoperabilitas sempurna dengan C API. | Bypass optimasi thread scheduling default Apple; jika queue blocking, thread starvation terjadi pada queue tersebut. | Bridge audio DSP, network driver, atau integrasi core database berbasis C (e.g. SQLite low-level). |
| **Unchecked Continuation (`withUnsafeContinuation`)** | Mengurangi runtime checking overhead (kinerja mikro lebih tinggi). | **Undefined Behavior & Crash** jika resume dipanggil dua kali atau lupa dipanggil (leak selamanya). | Library performa ultra-tinggi yang sudah melalui audit matematis formal. Hindari di level aplikasi enterprise. |
| **AsyncStream Buffering (Newest vs Oldest)** | Melindungi memori aplikasi dari OOM akibat lonjakan event tak terduga (*burst traffic*). | Data loss (pesan terbuang jika buffer meluap). Membutuhkan *recovery sequence* atau audit log. | UI feed stream, stock ticker, telemetri real-time. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Blocking the Cooperative Thread Pool
**Kesalahan Fatal:** Memanggil kode sinkron yang memblokir eksekusi (seperti `Thread.sleep`, `DispatchSemaphore.wait()`, atau kalkulasi kriptografi intensif tanpa offloading) di dalam Task konkurensi.
```swift
// ANTI-PATTERN: Menghancurkan throughput seluruh aplikasi
Task {
    Thread.sleep(forTimeInterval: 5.0) // MEMBLOKIR thread worker di pool!
}
```
**Solusi:**
Gunakan `Task.sleep` untuk penundaan asinkron. Untuk komputasi CPU berat, gunakan background DispatchQueue yang di-wrap dalam continuation atau delegasikan ke framework khusus.

### 10.2 Continuation Leaks dan Double Resumption
**Kesalahan Fatal:** Lupa memanggil continuation di salah satu branch error handling, atau memanggilnya lebih dari satu kali.
```swift
// ANTI-PATTERN: Leak atau Fatal Crash
func fetchLegacyData() async throws -> Data {
    try await withCheckedContinuation { continuation in
        legacyService.request { result, error in
            if let data = result {
                continuation.resume(returning: data)
            }
            // FATAL: Jika data == nil dan error terjadi, continuation tidak dipanggil!
            // Task akan hang selamanya (Resource leak).
        }
    }
}
```
**Solusi:**
Gunakan branch exhaustiveness check atau pola guard ketat:
```swift
func fetchLegacyDataSafe() async throws -> Data {
    try await withCheckedThrowingContinuation { continuation in
        legacyService.request { result, error in
            if let error = error {
                continuation.resume(throwing: error)
            } else if let data = result {
                continuation.resume(returning: data)
            } else {
                continuation.resume(throwing: URLError(.badServerResponse))
            }
        }
    }
}
```

### 10.3 Actor Reentrancy Blindness
**Masalah:** Mengasumsikan nilai properti actor tidak berubah setelah melewati kata kunci `await`.
**Deteksi Debugging:** Tambahkan assertion atau state validator sebelum dan setelah titik `await`. Gunakan instrument *Swift Tasks and Actors* di Xcode Instruments untuk melacak suspensi task dan mailbox interleaving.

---

## 11. Best Practices (Production Checklist)

- [ ] **Strict Concurrency Active:** Flag `-strict-concurrency=complete` atau Swift 6 Language Mode diaktifkan di Build Settings Xcode tanpa warning.
- [ ] **Sendable Purity:** Seluruh data yang melintasi Actor boundary dideklarasikan sebagai `Sendable` (menggunakan `struct`, `enum`, atau *immutable thread-safe class*).
- [ ] **Cooperative Suspension:** Tidak ada satupun pemanggilan `Thread.sleep`, `pthread_mutex`, atau `DispatchSemaphore.wait()` di dalam konteks `Task` atau `actor`.
- [ ] **Cancellation Handled Responsively:** Setiap loop pemrosesan panjang dalam `Task` secara eksplisit memeriksa `Task.isCancelled` atau mengeksekusi `try Task.checkCancellation()`.
- [ ] **Continuation Safety:** Setiap penggunaan `withCheckedContinuation` / `withCheckedThrowingContinuation` dipastikan memanggil resume **tepat satu kali** di semua cabang logika kode (*defensive code path*).
- [ ] **Controlled Buffering:** Semua pipeline `AsyncStream` mendefinisikan batas `bufferingPolicy` eksplisit (misal: `.bufferingNewest(N)`) untuk mencegah *heap exhaustion* akibat backpressure.
- [ ] **Actor Reentrancy Proofing:** State lokal yang diandalkan setelah `await` selalu di-refresh atau dilindungi menggunakan *state machine locking mechanism*.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum ini pada path: `hands-on/m02/`

### File: `hands-on/m02/Package.swift`
```swift
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "EnterpriseConcurrencyEngine",
    platforms: [.macOS(.v13), .iOS(.v16)],
    products: [
        .library(name: "EnterpriseConcurrencyEngine", targets: ["EnterpriseConcurrencyEngine"]),
        .executable(name: "ConcurrencyCLI", targets: ["ConcurrencyCLI"])
    ],
    targets: [
        .target(
            name: "EnterpriseConcurrencyEngine",
            swiftSettings: [
                .unsafeFlags(["-Xfrontend", "-strict-concurrency=complete"])
            ]
        ),
        .executableTarget(
            name: "ConcurrencyCLI",
            dependencies: ["EnterpriseConcurrencyEngine"]
        ),
        .testTarget(
            name: "EnterpriseConcurrencyEngineTests",
            dependencies: ["EnterpriseConcurrencyEngine"]
        )
    ]
)
```

### File: `hands-on/m02/Sources/EnterpriseConcurrencyEngine/ResilientPipeline.swift`
```swift
import Foundation

public struct PipelineEvent: Sendable, Equatable {
    public let id: UUID
    public let payload: String
    
    public init(id: UUID = UUID(), payload: String) {
        self.id = id
        self.payload = payload
    }
}

public actor ResilientPipeline {
    private var isProcessing: Bool = false
    private var buffer: [PipelineEvent] = []

    public init() {}

    public func processBatchAtomic(events: [PipelineEvent]) async -> Int {
        while isProcessing {
            await Task.yield()
        }
        
        isProcessing = true
        defer { isProcessing = false }

        // Simulasi suspensi parsing eksternal
        try? await Task.sleep(nanoseconds: 50_000_000)
        
        buffer.append(contentsOf: events)
        return buffer.count
    }

    public func getProcessedCount() -> Int {
        return buffer.count
    }
}
```

### File: `hands-on/m02/Sources/ConcurrencyCLI/main.swift`
```swift
import Foundation
import EnterpriseConcurrencyEngine

print("Starting Resilient Pipeline Verification...")

let pipeline = ResilientPipeline()

let group = DispatchGroup()

// Simulasikan 5 Task konkuren yang menembakkan event secara bersamaan
for index in 1...5 {
    Task {
        let events = [
            PipelineEvent(payload: "Message-\(index)-A"),
            PipelineEvent(payload: "Message-\(index)-B")
        ]
        let count = await pipeline.processBatchAtomic(events: events)
        print("Task \(index) selesai memproses. Total buffer sekarang: \(count)")
    }
}

// Berikan waktu proses eksekusi CLI sebelum terminasi
try await Task.sleep(nanoseconds: 1_000_000_000)
let finalCount = await pipeline.getProcessedCount()
print("Verifikasi selesai. Total final buffer: \(finalCount)")
assert(finalCount == 10, "Terjadi race condition pada batch processing!")
```

### Instruksi Eksekusi Terminal:
```bash
cd hands-on/m02/
swift build
swift run ConcurrencyCLI
```

---

## 13. Exercise

### Level Easy
Modifikasi kode pada `VulnerableBankVault` (Seksi 7.1) agar menggunakan `withCheckedContinuation` untuk membungkus library login lama berbasis closure:
```swift
func legacyLogin(user: String, completion: @escaping (Bool) -> Void)
```
Ubah menjadi:
```swift
func login(user: String) async -> Bool
```
*Kriteria Penerimaan:* Tidak boleh ada thread hang; continuation harus di-resume dengan benar.

### Level Medium
Bangun sebuah custom sequence `ChunkedAsyncSequence` yang mengonsumsi sembarang `AsyncSequence` dan menghasilkan array elemen bertipe chunk `[T]` berukuran `N` atau mengeluarkan elemen sisa saat stream induk selesai.  
*Kriteria Penerimaan:* Wajib menerapkan propagasi error dan merespons `Task.isCancelled`.

### Level Hard
Bangun sebuah generic actor pool `ActorWorkerPool<Worker: Actor>` yang membatasi konkurensi maksimal ke sejumlah `N` instances actor. Permintaan pekerjaan (`Job`) harus dimasukkan ke antrean prioritas (Priority Queue) internal dan didistribusikan secara dinamis ke Worker pertama yang memasuki kondisi *idle*.  
*Kriteria Penerimaan:*
*   Menggunakan Swift 5.9+ Strict Concurrency.
*   Zero data race condition.
*   Tidak ada *deadlock* saat semua worker sibuk.

---

## 14. Challenge: Offline-First Synchronizer Engine

### Konteks Kasus
Anda adalah Principal Architect pada aplikasi logistik pergudangan kelas industri. Kurir lapangan memindai paket di area *blind spot* (tanpa sinyal). Aplikasi harus:
1. Menyimpan antrean mutasi data ke SQLite lokal di background.
2. Membuka socket stream sinkronisasi real-time ketika jaringan kembali online.
3. Mengirimkan ribuan operasi yang tertunda secara *batched* dan *in-order*.

### Spesifikasi Teknis Tantangan:
1. Bangun komponen `OfflineSyncCoordinator` (Actor).
2. Terapkan custom serial executor untuk memastikan pembacaan dan penulisan disk lokal SQLite berjalan eksklusif pada background thread yang sama.
3. Rancang mekanisme pembatalan (*cancellation*): Jika koneksi terputus mendadak di tengah upload batch 10.000 item, sistem harus berhenti seketika, mengembalikan sisa item yang belum terkonfirmasi ke pending queue, tanpa menyebabkan duplikasi data di transaksi berikutnya.
4. Jangan gunakan framework reaktif pihak ketiga (Combine/RxSwift). Murni menggunakan `AsyncStream`, `AsyncSequence`, dan `TaskGroup`.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic
1. Mengapa Swift Concurrency tidak menambah jumlah thread baru tanpa batas saat terjadi penumpukan Task asinkron?
   - A. Karena thread dibatasi oleh ukuran RAM perangkat.
   - B. Karena menggunakan Cooperative Thread Pool yang dipatok sesuai jumlah physical/logical CPU core.
   - C. Karena Swift Concurrency hanya berjalan pada satu thread (Single-threaded).
   - D. Karena compiler mengubah fungsi async menjadi pemanggilan synchronous biasa.

2. Di mana alokasi state memory dari sebuah fungsi `async` disimpan saat fungsi tersebut sedang dalam kondisi tersuspensi (`await`)?
   - A. Di stack memory milik Thread Main.
   - B. Di CPU Registers fisik.
   - C. Di memory Heap sebagai Async Task Frame.
   - D. Di Swap Storage / Disk.

3. Apa konsekuensi utama jika method `resume()` pada `CheckedContinuation` dipanggil dua kali?
   - A. Permintaan kedua akan diabaikan secara diam-diam (*silent discard*).
   - B. Terjadi crash fatal saat runtime (*Fatal Error: Continuation was already resumed*).
   - C. Fungsi asinkron akan return nilai kedua.
   - D. Aplikasi otomatis me-restart background worker.

4. Kapan sebuah struct secara otomatis memenuhi protokol `Sendable`?
   - A. Jika struct tersebut bertipe `public`.
   - B. Jika seluruh properti tersimpan (*stored properties*) di dalamnya juga bertipe `Sendable`.
   - C. Struct tidak akan pernah bisa menjadi `Sendable`.
   - D. Jika struct memiliki metode yang ditandai `mutating`.

5. Apa fungsi dari atribut `@MainActor` pada sebuah kelas atau fungsi?
   - A. Menjadikan kelas tersebut berjalan paling cepat dibanding kelas lain.
   - B. Mengisolasi eksekusi method dan mutasi properti agar selalu terjadi di Main Thread.
   - C. Mengunci alokasi memori agar tidak pernah di-dealloc oleh ARC.
   - D. Mengubah semua pemanggilan fungsi sinkron menjadi asynchronous.

---

### Bagian 2: Intermediate
6. Manakah dari pernyataan berikut yang **BENAR** mengenai sifat *Actor Reentrancy* pada Swift?
   - A. Sebuah actor menjamin tidak ada kode lain yang dieksekusi di dalam actor tersebut sebelum fungsi yang sedang berjalan selesai seluruhnya, meskipun terdapat titik `await`.
   - B. Suspensi pada titik `await` di dalam actor membebaskan actor mailbox untuk memproses request lain, sehingga state actor dapat berubah sebelum fungsi pertama dilanjutkan.
   - C. Actor reentrancy menyebabkan *deadlock* otomatis jika dua task mengakses actor yang sama.
   - D. Reentrancy hanya terjadi jika actor dijalankan pada iOS Simulator.

7. Perhatikan kode berikut:
   ```swift
   actor ImageLoader {
       var cache: [URL: UIImage] = [:]
       func load(url: URL) async -> UIImage {
           if let img = cache[url] { return img }
           let img = await downloadImage(from: url)
           cache[url] = img
           return img
       }
   }
   ```
   Celah arsitektur apa yang terdapat pada kode di atas?
   - A. Memory leak pada dictionary `cache`.
   - B. Duplikasi pengunduhan gambar (redundant network calls) jika `load(url:)` dipanggil secara konkuren untuk URL yang sama saat download pertama belum selesai.
   - C. Deadlock pada pemanggilan `downloadImage`.
   - D. Compiler error karena actor tidak boleh memiliki properti Dictionary.

8. Fitur Swift 5.9 manakah yang memungkinkan developer mengarahkan eksekusi internal Actor ke DispatchQueue tertentu?
   - A. TaskLocal.
   - B. Custom Serial Executor (`SerialExecutor` / `unownedSerialExecutor`).
   - C. Distributed Actor Isolation.
   - D. Dynamic Actor Dispatch.

9. Apa yang terjadi jika Anda memanggil fungsi pemblokir seperti `DispatchSemaphore.wait()` di dalam sebuah `Task` Swift Concurrency?
   - A. Runtime akan otomatis membuat thread baru di Cooperative Pool untuk menghindari starvation.
   - B. Thread pekerja fisik di Cooperative Pool akan hang/terblokir, berpotensi memicu degradasi performa masif (*Thread Starvation*).
   - C. Compiler akan melempar pesan compile-time error.
   - D. Task secara otomatis dialihkan ke status `.cancelled`.

10. Apa kegunaan utama `withTaskCancellationHandler(operation:onCancel:)` dibanding hanya memeriksa `Task.isCancelled`?
    - A. Mempercepat eksekusi fungsi hingga 2x lipat.
    - B. Memungkinkan eksekusi aksi interupsi pembersihan secara langsung dan segera (*eagerly*) saat sinyal pembatalan masuk, tanpa menunggu suspensi point selesai.
    - C. Mencegah error dilempar keluar dari konteks Task.
    - D. Menghindari pemakaian closure di Task.

---

### Bagian 3: Skenario Kasus Produksi
11. **Skenario Kasus 1:**  
    Sebuah aplikasi perbankan mengalami freeze visual acak selama 2-3 detik pada Main Thread setelah pengguna berhasil login, meskipun seluruh pemrosesan data jaringan sudah menggunakan `async/await`. Berdasarkan penyelidikan, pemanggilan integrasi analitik pihak ketiga menggunakan closure SDK sinkron: `AnalyticsSDK.shared.trackSync(event: String)` yang melakukan disk I/O. Kode dipanggil langsung di dalam method `@MainActor ViewModel.onLoginSuccess()`.  
    *Tindakan perbaikan arsitektural manakah yang paling tepat?*
    - A. Membungkus pemanggilan tersebut dengan `Task { AnalyticsSDK.shared.trackSync(...) }` langsung di dalam ViewModel.
    - B. Memindahkan eksekusi analitik ke sebuah `actor` independen atau menjalankannya di background executor non-MainActor terpisah melalui `Task.detached(priority: .background)`.
    - C. Mengganti `AnalyticsSDK` dengan pemanggilan `DispatchQueue.main.async`.
    - D. Menambah alokasi memori heap pada iOS Main RunLoop.

12. **Skenario Kasus 2:**  
    Sistem ingestion telemetri IoT mobil listrik memproduksi 3.000 log payload sensor per detik melalui UDP. Konsumen data memprosesnya via `AsyncStream`. Di perangkat dengan spesifikasi rendah, konsumsi memori aplikasi melonjak drastis hingga sistem iOS mematikan aplikasi dengan crash log `EXC_RESOURCE -> OS-Signals: SIGKILL (Jetsam OOM)`.  
    *Apa akar penyebab dan mitigasi teknisnya?*
    - A. Cooperative thread pool kehabisan thread; gunakan GCD concurrent queue.
    - B. `AsyncStream` diinisialisasi tanpa `BufferingPolicy` sehingga buffer default tidak terbatas (*unbounded*) menampung paket lebih cepat daripada kemampuan pemrosesan; mitigasi dengan menetapkan `.bufferingNewest(limit)` atau `.bufferingOldest(limit)`.
    - C. Kurang deklarasi kata kunci `weak` pada setiap task continuation.
    - D. Memory leak akibat penggunaan tipe data `Data`; ganti tipe data menjadi `[UInt8]`.

13. **Skenario Kasus 3:**  
    Sebuah tim migrasi memodernisasi codebase dari Objective-C ke Swift 6. Mereka mendapati crash di unit test:  
    `Fatal error: SWIFT TASK CONTINUATION MISUSE: tried to resume continuation more than once!`.  
    Pemeriksaan kode menunjukkan bahwa closure completion handler warisan (*legacy API*) terkadang memanggil callback dua kali pada kondisi error timeout tertentu.  
    *Bagaimana cara mengamankan continuation bridge tersebut secara enterprise-grade?*
    - A. Mengganti `withCheckedContinuation` dengan `withUnsafeContinuation` agar crash diabaikan.
    - B. Menggunakan flag sinkronisasi atomik lokal (misal: state lock atau `OSAllocatedUnfairLock`) untuk memastikan method `continuation.resume` hanya dapat dieksekusi tepat satu kali, mengabaikan pemanggilan callback berikutnya.
    - C. Memanggil `continuation.yield()` sebelum `continuation.resume()`.
    - D. Membungkus continuation di dalam block `do-catch` konvensional.

---

### Kunci Jawaban Evaluasi

#### Bagian 1 & 2
1. **B** — Swift Concurrency membatasi thread pool secara deterministik sesuai core fisik/logis CPU guna mencegah *thread explosion*.
2. **C** — State yang melintasi titik suspensi disimpan di memori heap dalam struktur *Async Task Frame*.
3. **B** — `CheckedContinuation` menerapkan runtime sanity check; memanggil resume lebih dari sekali memicu *fatal crash*.
4. **B** — Struct dengan seluruh stored properties yang `Sendable` secara implisit/otomatis berstatus `Sendable`.
5. **B** — `@MainActor` adalah Global Actor yang memastikan akses terisolasi pada UI Thread (Main Thread).
6. **B** — Actor melepaskan thread saat `await`, sehingga pekerjaan lain di mailbox dapat menyisip dan memutasi state.
7. **B** — Jika Task A tersuspensi pada `downloadImage`, Task B dapat masuk dan mendapati `cache[url]` masih kosong, memicu *duplicate network download*.
8. **B** — `SerialExecutor` memungkinkan penentuan antrean eksekusi mailbox actor secara manual.
9. **B** — Mengunci thread worker di Cooperative Pool menyebabkan *thread starvation* karena pool tidak menambah thread baru secara sembarangan.
10. **B** — Handler pembatalan dijalankan segera saat pembatalan terjadi (*eager execution*), tanpa menunggu suspensi point resume.

#### Bagian 3 (Skenario Produksi)
11. **B** — Menggunakan `Task {}` di dalam ViewModel yang beranotasi `@MainActor` akan mewarisi konteks isolasi MainActor, sehingga eksekusi sinkron tetap memblokir UI. Solusinya adalah memutus isolasi konteks MainActor menggunakan `Task.detached` atau Actor latar belakang terpisah.
12. **B** — Tanpa pembatasan buffer, `AsyncStream` akan mengalokasikan memori terus-menerus saat produser data lebih cepat dari konsumen (*unbounded queue*), menyebabkan Jetsam mematikan proses (OOM).
13. **B** — Penggunaan lock thread-safe untuk memproteksi satu kali eksekusi (*single-execution guarantee*) adalah pola standar industri untuk menjinakkan closure legacy yang tidak stabil saat dijembatani ke Swift Concurrency.

---

## 16. Summary

1. **Cooperative Multitasking:** Swift Concurrency menggeser paradigma dari *thread-heavy GCD queues* menuju *thread-conserving cooperative pools*, membatasi alokasi thread maksimum sebanding dengan core CPU guna memangkas overhead context switching.
2. **Async Call Frames:** Variabel asinkron dialokasikan di heap melalui Task Frame, memungkinkan fungsi melepaskan stack thread OS fisik saat menemui titik suspensi (`await`).
3. **Actor Reentrancy:** Actor tidak menjamin status internalnya tidak berubah selama proses suspensi berlangsung. Selalu pastikan validasi ulang state setelah kata kunci `await` atau gunakan *transaction locking pattern*.
4. **Custom Executors (SE-0392):** Memberikan kendali deterministik atas jalur eksekusi Actor, menjembatani isolasi Actor dengan antrean hardware/legacy tanpa mengorbankan keamanan data-race.
5. **Robust Bridging:** Menjembatani closure lama ke `Continuation` mewajibkan garansi *exactly-once resumption*, penanganan *backpressure* pada `AsyncStream`, dan integrasi pembatalan interaktif via `withTaskCancellationHandler`.