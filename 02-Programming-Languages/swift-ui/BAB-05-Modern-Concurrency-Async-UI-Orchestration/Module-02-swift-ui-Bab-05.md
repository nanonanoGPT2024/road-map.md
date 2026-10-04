# BAB 05: Modern Concurrency & Async UI Orchestration
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Principal Software Engineer / Senior iOS Architect diharapkan mampu:
*   Menganalisis dan menanggulangi anomali *Actor Re-entrancy* serta mengeliminasi potensi *data races* pada *compile-time* menggunakan Swift 6 *Strict Concurrency Checking* (`-strict-concurrency=complete`).
*   Merancang arsitektur reaktif berbasis *Structured Concurrency* (`TaskGroup`, `AsyncStream`, `AsyncAlgorithms`) yang terintegrasi secara deterministik dengan siklus hidup SwiftUI *View Graph* (`AttributeGraph`).
*   Mengimplementasikan mekanisme *backpressure*, *buffering strategies*, dan *cooperative task cancellation* tingkat lanjut pada *high-throughput data pipelines* (WebSocket, Server-Sent Events, sensor telemetry).
*   Menghindari fenomena *thread pool starvation* dan *priority inversion* dengan mengisolasi beban komputasi berat dari *Cooperative Thread Pool* tanpa mengorbankan *MainActor UI frame-budget* (16.6ms / 8.3ms).
*   Mengonversi API asinkron *legacy* berbasis *closure/delegate* secara *thread-safe* menggunakan *Checked Continuations* dengan proteksi *lifecycle leaks*.

---

### 2. Prerequisite
*   Penguasaan mendalam terhadap Swift Memory Management (ARC, retain cycles, copy-on-write semantics).
*   Pemahaman ekstensif tentang eksekusi GCD (*Grand Central Dispatch*), serial/concurrent queues, dan runloops.
*   Pemahaman operasional Swift Modern Concurrency dasar (`async`/`await`, `Task`, `@MainActor`, `actor`).
*   Familiaritas dengan *SwiftUI Render Loop* (State changes $\rightarrow$ Transaction $\rightarrow$ AttributeGraph update $\rightarrow$ Layout $\rightarrow$ Render commit).

---

### 3. Concept & Internal Architecture

#### A. Cooperative Thread Pool vs. GCD Thread Explosion
Dalam model konkurensi klasik (GCD/`DispatchQueue`), pembuatan *concurrent queues* yang berlebihan dan pemblokiran thread (misalnya melalui semafor atau sinkronisasi I/O) dapat memicu *Thread Explosion*. Setiap *thread* mengalokasikan setidaknya 512KB hingga 1MB memori untuk *stack space*, menyebabkan pemborosan virtual memory, fragmentasi, dan *context switching overhead* yang mendegradasi performa CPU cache.

```
Model Tradisional (GCD Thread Explosion):
Task 1 (Blocked)  ---> Thread 1 [Stack: 512KB] \
Task 2 (Blocked)  ---> Thread 2 [Stack: 512KB]  |-- OS Kernel: Context Switching Thrashing
Task 3 (Runnable) ---> Thread 3 [Stack: 512KB]  |   High Latency, Cache Invalidation
Task N (...)      ---> Thread N [Stack: 512KB] /

Model Modern (Cooperative Thread Pool):
Cooperative Pool: Fixed Worker Threads (Jumlah Thread == Kapasitas Core CPU Fisik)
[ Thread 1 (Core 0) ] <--- [ Continuation Job A ] <--- [ Continuation Job B ] (Stealing)
[ Thread 2 (Core 1) ] <--- [ Suspended: Job C   ] <--- [ Continuation Job D ]
*Saat Job C suspended (await), Thread 2 TIDAK diblokir; langsung mengeksekusi Job D.*
```

Swift Concurrency mengimplementasikan **Cooperative Thread Pool**. Karakteristik internalnya:
1.  **Fixed-size Concurrency Limit:** Runtime membatasi jumlah *active worker threads* hanya sebanyak *logical CPU cores* yang tersedia pada *hardware*.
2.  **Continuations Execution:** Ketika sebuah fungsi `async` mencapai titik suspensi (`await`), frame eksekusinya dipindahkan dari *call stack* ke *heap allocation* yang disebut **Continuation Job**.
3.  **Work-Stealing Scheduler:** Thread yang sedang menganggur dapat mengambil (*steal*) *job* dari antrean thread lain, menjamin utilisasi CPU mendekati 100% tanpa overhead pergantian *kernel context*.

#### B. Actor Isolation & Re-entrancy Traps
Sebuah `actor` menjamin *mutual exclusion* terhadap *mutable state* miliknya. Namun, **Swift Actors bersifat Re-entrant**. Artinya:

> Ketika sebuah fungsi pada *actor* dihentikan sementara (*suspended*) melalui `await`, *actor* tersebut dibebaskan untuk menerima dan mengeksekusi pesan/tugas lain dari antreannya. 

Ketika suspensi selesai dan eksekusi dilanjutkan (*resumed*), asumsi *state* lokal yang divalidasi sebelum titik `await` berpotensi telah dimutasi oleh operasi lain.

```
Timeline Actor Re-entrancy Bug:

Time  Actor Execution Pipeline                  Internal Actor State: balance = 100
 |
 0ms  Task A: transfer(amount: 80)
 1ms  Task A checks: balance >= 80 (OK)
 2ms  Task A: await network.authorize() -------+ Suspended. Actor lock RELEASED.
      =========================================|=> Actor is now free!
 3ms  Task B: transfer(amount: 50)             |
 4ms  Task B checks: balance >= 50 (OK)        |
 5ms  Task B: await network.authorize() -+     |
      ===================================|=====|
 6ms  Task A resumes <-------------------+     |
 7ms  Task A mutates: balance -= 80            | balance = 20
 8ms  Task B resumes <-------------------------+
 9ms  Task B mutates: balance -= 50            | balance = -30 (CRITICAL INVARIANT BREACH!)
 v
```

#### C. Integrasi SwiftUI AttributeGraph & View Updates
Sistem reaktivitas SwiftUI ditenagai oleh mesin internal berbasis graph: **AttributeGraph**. 
1.  Ketika nilai properti beranotasi `@State` atau properti dari kelas `@Observable` dimutasi, mutasi tersebut **wajib** terjadi pada `MainActor`.
2.  SwiftUI mendaftarkan ketergantungan dinamis (*dependency tracking*) selama fase evaluasi `body`.
3.  Jika mutasi dipicu di luar `MainActor` tanpa isolasi yang tepat, *data race* internal pada *AttributeGraph node pointer* akan terjadi, memicu crash tak terduga seperti `EXC_BAD_ACCESS` di dalam libsystem/AGX runtime.
4.  Modifier `.task(id:)` secara otomatis mengaitkan siklus hidup *Task* dengan keberadaan View di dalam graph. Ketika view dihapus (*destroyed*) atau nilai `id` berubah, SwiftUI secara implisit mengirimkan sinyal `Task.cancel()`.

---

### 4. Why & What

| Paradigma Concurrency | What (Mekanisme Kerja) | Why (Kapan Digunakan & Manfaat Produksi) |
| :--- | :--- | :--- |
| **Actor Isolation** | Perlindungan sinkronisasi *mutable state* berbasis *actor mailbox*. | Menghindari *data race* tanpa manual *locking/mutex*, menjamin validitas state secara *compile-time*. |
| **Structured Concurrency** (`TaskGroup`) | Relasi hierarkis anak-induk task: Task selesai bersamaan sebelum scope berakhir. | Memastikan propagasi *cancellation*, pembersihan *heap frames*, dan pencegahan *leaked background tasks*. |
| **AsyncStream (with Backpressure)** | Jembatan asinkron berorientasi aliran data diskrit dengan kapasitas buffer terbatas. | Mencegah lonjakan memori akibat *producer-consumer speed mismatch* (misal: WebSocket feed 5000 msg/sec). |
| **Global Actors (`@MainActor`)** | Eksekutor global yang terikat khusus pada Thread Utama (*Main Dispatch Queue*). | Menjamin pembaruan UI dan mutasi *SwiftUI Observable states* bebas dari race condition/flickering. |
| **TaskLocal** | State kontekstual yang diwariskan secara hierarkis melintasi rantai Task terstruktur. | Distributed tracing, request tracking ID, dan context propagation tanpa parameter injection. |

---

### 5. How (Workflow Detail)

Aliran siklus hidup data dari network ingestion level rendah hingga ke rendering antarmuka pengguna:

```
[ External Signal / Engine (I/O) ]
               │
               ▼
[ Legacy Callback / C-Library Event ]
               │
               ▼  (Wrapped via withCheckedCancellationHandler)
[ CheckedContinuation / AsyncStream Source ]
               │
               ▼  (Yielded into Buffered Pipeline)
[ Background Actor Pipeline (Processor) ] 
       - Structural Validation
       - Parallel Decryption/Transform via TaskGroup
       - Cooperative Cancellation Check (Task.checkCancellation)
               │
               ▼  (Normalized Immutable Value / DTO)
[ Ingestion Coordinator Actor ]
       - De-duplication & Local In-Memory Cache
               │
               ▼  (Context Switch to @MainActor)
[ @Observable ViewModel / State Store ]
       - In-place Array Mutation / Buffer swap
               │
               ▼
[ SwiftUI AttributeGraph Validation ]
       - Transaction Propagation
       - Diffing Engine (Attribute changes)
               │
               ▼
[ CATransaction Engine / Metal Render Loop ]
       - 60/120 FPS Target Met (Commit Frame)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Dapur Restoran Bintang Lima
*   **MainActor (Chef Utama / Exposer):** Bertanggung jawab hanya pada plating dan penyerahan makanan ke pelayan (UI Presentation). Jika Chef Utama memotong daging atau mencuci piring, seluruh restoran berhenti menyajikan makanan (Frame Drop/Jank).
*   **Worker Threads (Staf Persiapan Dapur):** Jumlah staf terbatas sesuai jumlah meja kerja (Cores). Mereka mengambil tugas dari papan pesanan terpusat.
*   **Actor Re-entrancy (Staf Mengambil Bahan):** Staf A mulai meracik saus, menyadari kecap habis, lalu pergi ke gudang (`await`). Meja kerja staf A tidak boleh kosong; staf B langsung mengambil alih meja untuk memotong wortel. Ketika staf A kembali dari gudang, ia harus memeriksa kembali apakah saus di mejanya tidak ditumpahkan atau dimodifikasi staf B.
*   **TaskGroup (Menu Paket Multi-Item):** Satu hidangan membutuhkan steak, saus, dan kentang. Tiga koki memasak bersamaan; paket tidak bisa disajikan jika salah satu gagal atau hangus (Cancellation).

#### Diagram Arsitektur Isolasi Eksekusi
```
+-------------------------------------------------------------------------+
|                              MAIN ACTOR                                 |
|  +------------------------------------+  +---------------------------+  |
|  |       SwiftUI View Hierarchy       |  |  @Observable State Model  |  |
|  |  (Body Evaluation / Metal Commit)  |  |   (UI State Store Data)   |  |
|  +------------------------------------+  +---------------------------+  |
+-----------------------------------▲-------------------------------------+
                                    │ (Actor Hop: MainActor boundary)
+-----------------------------------┴-------------------------------------+
|                  COOPERATIVE THREAD POOL (N Cores)                      |
|                                                                         |
|  [ Actor: OrderBookEngine ]             [ Structured Task Group ]       |
|  +-----------------------------+        +----------------------------+  |
|  | - State: Local Orders Cache |        | Child Task 1: Decrypt      |  |
|  | - Reentrancy Barrier Zone   |        | Child Task 2: Parse JSON   |  |
|  | - Backpressure Dropping     |        | Child Task 3: Checksum     |  |
|  +-----------------------------+        +----------------------------+  |
|                 ▲                                      │                |
+-----------------│--------------------------------------│----------------+
                  │                                      │
+-----------------┴--------------------------------------▼----------------+
|                 SYSTEM I/O SUBSYSTEM (Kernel / Network)                 |
|  [ NWConnection / WebSocket ] ------------> [ High Frequency SSE ]      |
+-------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Safe Continuation Wrapper dengan Task Cancellation
Mengonversi closure-based asynchronous library ke async/await secara aman, mencegah continuation kebocoran memori (*leak*), dan mendukung pembatalan seketika (*early cancellation*).

```swift
import Foundation

enum NetworkError: Error {
    case taskCancelled
    case invalidPayload
    case connectionLost
}

// Simulasi legacy client
final class LegacySDKClient: @unchecked Sendable {
    func executeFetch(completion: @escaping (Result<Data, Error>) -> Void) -> UUID {
        let requestId = UUID()
        DispatchQueue.global().asyncAfter(deadline: .now() + 1.0) {
            completion(.success(Data("payload".utf8)))
        }
        return requestId
    }
    
    func abortRequest(_ id: UUID) {
        // Logika aborting legacy
    }
}

// Wrapper Modern
actor ModernAPIBridge {
    private let legacyClient = LegacySDKClient()

    func fetchPayloadSafely() async throws -> Data {
        // Melacak ID secara thread-safe di dalam context continuation
        var trackingId: UUID?

        return try await withTaskCancellationHandler {
            try Task.checkCancellation()
            
            return try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Data, Error>) in
                trackingId = self.legacyClient.executeFetch { result in
                    switch result {
                    case .success(let data):
                        continuation.resume(returning: data)
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                }
            }
        } onCancel: {
            if let id = trackingId {
                self.legacyClient.abortRequest(id)
            }
        }
    }
}
```

#### B. Practical Example: Resilient High-Throughput Ingestion Engine
Sistem streaming data finansial terstruktur: Menggabungkan `AsyncThrowingStream` dengan backpressure strategi, parsing paralel dengan `TaskGroup`, dan isolasi state aman dari Actor Reentrancy.

```swift
import Foundation
import Observation

// MARK: - Models
public struct OrderPacket: Identifiable, Sendable, Codable {
    public let id: UUID
    public let symbol: String
    public let price: Double
    public let timestamp: Date
}

// MARK: - Ingestion Stream with Backpressure
public final class MarketDataTransceiver: Sendable {
    public static let shared = MarketDataTransceiver()
    
    // Produksi stream dengan batas buffer tertentu (Backpressure mitigation)
    public func subscribe(to symbol: String) -> AsyncBackpressuredStream<OrderPacket> {
        let (stream, continuation) = AsyncThrowingStream.makeStream(
            of: OrderPacket.self,
            throwing: Error.self,
            bufferingPolicy: .bufferingNewest(500) // Jatuhkan pesan terlama jika UI/Processing lag
        )
        
        let sessionTask = Task.detached {
            do {
                while !Task.isCancelled {
                    // Simulasi I/O tick 200 Hz (5ms)
                    try await Task.sleep(for: .milliseconds(5))
                    let mockPacket = OrderPacket(
                        id: UUID(),
                        symbol: symbol,
                        price: Double.random(in: 100...200),
                        timestamp: .now
                    )
                    
                    let yieldResult = continuation.yield(mockPacket)
                    if case .dropped = yieldResult {
                        // Log metric telemetry: Frame dropped in pipeline
                    }
                }
                continuation.finish()
            } catch {
                continuation.finish(throwing: error)
            }
        }
        
        continuation.onTermination = { @Sendable _ in
            sessionTask.cancel()
        }
        
        return stream
    }
}

public typealias AsyncBackpressuredStream<T> = AsyncThrowingStream<T, Error>

// MARK: - Actor State Coordinator (Menangani Re-entrancy secara Deterministik)
public actor OrderBookActor {
    private var ledger: [UUID: OrderPacket] = [:]
    private var isSyncing = false
    
    // Menghindari Re-entrancy Bug dengan Mutex Flag State Locking
    public func batchIngest(_ packets: [OrderPacket]) async throws {
        // Pre-suspension barrier check
        while isSyncing {
            try Task.checkCancellation()
            await Task.yield() // Melepaskan cooperatively slot eksekusi
        }
        
        isSyncing = true
        defer { isSyncing = false } // Menjamin unlock state saat error/return
        
        // Parallel validation menggunakan TaskGroup
        let validPackets = try await withThrowingTaskGroup(of: OrderPacket?.self) { group in
            for packet in packets {
                group.addTask {
                    try Task.checkCancellation()
                    return packet.price > 0 ? packet : nil
                }
            }
            
            var collected: [OrderPacket] = []
            for try await result in group {
                if let valid = result {
                    collected.append(valid)
                }
            }
            return collected
        }
        
        // Mutasi sinkron pasca-suspensi (Atomic guarantee)
        for packet in validPackets {
            self.ledger[packet.id] = packet
        }
    }
    
    public func getLatestLedgerSlice(limit: Int) -> [OrderPacket] {
        return Array(ledger.values.prefix(limit))
    }
}

// MARK: - Observable UI Presentation Orchestrator
@Observable
@MainActor
public final class MarketDashboardViewModel {
    public private(set) var activeOrders: [OrderPacket] = []
    public private(set) var networkLatencyMs: Double = 0.0
    
    private let actorCore = OrderBookActor()
    private var ingestionTask: Task<Void, Never>?
    
    public func startLiveStream(for symbol: String) {
        stopLiveStream()
        
        ingestionTask = Task { [weak self] in
            guard let self else { return }
            
            let stream = MarketDataTransceiver.shared.subscribe(to: symbol)
            var batchBuffer: [OrderPacket] = []
            var lastFlushTime = ContinuousClock.now
            
            do {
                for try await packet in stream {
                    try Task.checkCancellation()
                    batchBuffer.append(packet)
                    
                    // Throttle UI update ke max 30Hz (~33ms) untuk mencegah starvation pada MainActor
                    if lastFlushTime.duration(to: .now) >= .milliseconds(33) || batchBuffer.count >= 50 {
                        let toProcess = batchBuffer
                        batchBuffer.removeAll(keepingCapacity: true)
                        lastFlushTime = .now
                        
                        // Eksekusi parsing di cooperative pool background actor
                        try await self.actorCore.batchIngest(toProcess)
                        
                        // Dapatkan snapshot immutable dan update properti Observable
                        let updatedSnapshot = await self.actorCore.getLatestLedgerSlice(limit: 30)
                        
                        // MainActor update context
                        self.activeOrders = updatedSnapshot
                    }
                }
            } catch is CancellationError {
                // Task dibatalkan secara elegan
            } catch {
                // Logging sentry telemetry
            }
        }
    }
    
    public func stopLiveStream() {
        ingestionTask?.cancel()
        ingestionTask = nil
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus Produksi: High-Frequency Limit Order Book (LOB) Pada Aplikasi Kripto Global
*   **Masalah:** Pada rilis v4.12, aplikasi mengalami penurunan FPS ke level 12 FPS (*severe micro-stutters*) dan crash sporadis `EXC_BAD_ACCESS` saat terjadi *volatility spike* di market BTC/USD (2.000–5.000 orderbook updates per detik).
*   **Akar Masalah (Root Cause Analysis):**
    1.  *Main Thread Saturation:* Data layer menggunakan Combine pipeline dengan `receive(on: DispatchQueue.main)`. Setiap frame incoming packet mengeksekusi closure terpisah pada main thread, membanjiri `CFRunLoop` sehingga *render phases* terlambat dieksekusi.
    2.  *Unbounded Queue Memory Spikes:* Buffer Combine yang tidak memiliki batasan eksplisit melonjak ke 850MB dalam 30 detik saat jaringan seluler berganti dari 5G ke 3G (Backpressure failure).
    3.  *Race Condition pada Model Rendering:* Properti array `@Published` dimutasi secara in-place secara concurrently saat SwiftUI `List` sedang membaca pointer internal array untuk rendering frame, menghasilkan pointer corruption (`EXC_BAD_ACCESS`).

#### Solusi Arsitektur
1.  **Conflation / Throttling Buffer:** Mengimplementasikan ring-buffer berbasis `AsyncStream(bufferingPolicy: .bufferingNewest(100))` untuk mengeliminasi lonjakan memori (Memory cap $\le 45\text{ MB}$).
2.  **Display Synchronization:** Memisahkan *data processing rate* (2.000 ops/detik di background actor) dengan *UI refresh rate* (tetap sinkron di 60 FPS menggunakan interval timer berbasis clock hardware).
3.  **Swift 6 Strict Concurrency Isolation:** Seluruh model DTO diubah menjadi *Immutable Structs* bertipe `Sendable`, sedangkan UI state diikat penuh ke `@MainActor`.

```swift
// Implementasi Conflation Actor yang Diimplementasikan
actor OrderConflator {
    private var pendingUpdates: [Double: Double] = [:] // Price : Quantity
    
    func ingest(price: Double, quantity: Double) {
        pendingUpdates[price] = quantity
    }
    
    func drainBatch() -> [Double: Double] {
        guard !pendingUpdates.isEmpty else { return [:] }
        let batch = pendingUpdates
        pendingUpdates.removeAll(keepingCapacity: true)
        return batch
    }
}
```

*   **Hasil:**
    *   Penggunaan memori stabil di 68MB (penurunan ~92%).
    *   FPS kembali terkunci di 60/120 FPS tanpa frame drops (*zero dropped frames* pada instrumen Core Animation).
    *   Crash rate turun dari 2.4% ke 0.001%.

---

### 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Actor Isolation vs. Traditional NSLock/OSAllocatedUnfairLock** | Bebas data races pada *compile-time*. Integrasi mulus dengan `async/await`. Bebas dari deadlocks akibat *inverted locking hierarchies*. | Biaya alokasi Continuation pada heap saat suspensi. Rentan terhadap *Actor Re-entrancy bugs* jika state diubah setelah titik suspensi (`await`). |
| **`Task.detached` vs. `Task {}` (Inherited)** | Tidak mewarisi isolasi konteks eksekutor pemanggil (misal: MainActor) atau *TaskPriority*. Cocok untuk komputasi terisolasi murni. | Memutus struktur hierarki task. Kehilangan propagasi pembatalan otomatis (*cancellation leak*), penanganan error menjadi manual. |
| **AsyncStream `bufferingNewest` vs. `bufferingOldest`** | Mencegah aplikasi kehabisan memori (*OOM Crash*) saat consumer lambat; UI selalu mendapatkan state data terbaru. | Data di tengah (*intermediate events*) hilang (*dropped*). Berbahaya untuk event transaksional (seperti ledger settlement). |
| **Batching/Throttling vs. Direct State Emission** | Menghemat siklus komputasi UI, menjamin target *frame budget* (16ms) tercapai. | Memperkenalkan latensi artifisial kecil (misal: 16-33ms) pada propagasi data ke layar. |

---

### 10. Common Mistakes & Troubleshooting

#### Antipattern 1: Asumsi Invarian State Valid Melintasi Titik `await` (Actor Reentrancy)
```swift
// SALAH: State dapat dimutasi oleh task lain saat await executeLongOperation()
actor UserWallet {
    var balance: Double = 100
    
    func withdraw(amount: Double) async -> Bool {
        guard balance >= amount else { return false }
        // TITIK SUSPENSI: Actor lock dilepaskan!
        let success = await PaymentGateway.charge(amount)
        if success {
            balance -= amount // BUG: balance bisa jadi sudah dimutasi oleh panggilan paralel withdraw()!
            return true
        }
        return false
    }
}

// BENAR: Re-verifikasi state pasca-suspensi atau gunakan state-machine transaksional
actor ProtectedWallet {
    var balance: Double = 100
    
    func withdraw(amount: Double) async -> Bool {
        guard balance >= amount else { return false }
        let success = await PaymentGateway.charge(amount)
        guard success else { return false }
        
        // Re-check state setelah suspensi
        guard balance >= amount else {
            await PaymentGateway.refund(amount) // Rollback
            return false
        }
        balance -= amount
        return true
    }
}
```

#### Antipattern 2: Leaking Continuation (Unresumed or Double Resumed)
Aturan absolut `CheckedContinuation`: **Harus di-resume tepat satu kali di setiap cabang jalur kode.**
```swift
// SALAH: Jika error terjadi, continuation bocor (heap memory leak + task hang selamanya)
func fetchUser() async throws -> User {
    try await withCheckedThrowingContinuation { continuation in
        legacyFetch { user, error in
            if let user {
                continuation.resume(returning: user)
            }
            // Error case TERLUPAKAN! Continuation tidak pernah di-resume jika user nil!
        }
    }
}

// BENAR: Menangani semua exit paths secara komprehensif
func fetchUserFixed() async throws -> User {
    try await withCheckedThrowingContinuation { continuation in
        legacyFetch { user, error in
            if let error {
                continuation.resume(throwing: error)
            } else if let user {
                continuation.resume(returning: user)
            } else {
                continuation.resume(throwing: NetworkError.invalidPayload)
            }
        }
    }
}
```

#### Antipattern 3: Memanggil Blocking API di Dalam Cooperative Pool
```swift
// SALAH: Menahan thread Cooperative Thread Pool secara fisik
func processAssets() async {
    Thread.sleep(forTimeInterval: 5.0) // POOL STARVATION! Thread terkunci secara fisik!
}

// BENAR: Gunakan non-blocking sleep yang kooperatif
func processAssetsCorrectly() async throws {
    try await Task.sleep(for: .seconds(5)) // Thread dilepaskan untuk mengeksekusi job lain
}
```

---

### 11. Best Practices (Production Checklist)

| Tahapan Evaluasi | Checklist Verifikasi Teknis | Kriteria Kelulusan |
| :--- | :--- | :--- |
| **Compiler Flags** | Aktifkan `SWIFT_STRICT_CONCURRENCY` pada Xcode Build Settings. | Bernilai `Complete` tanpa warning pada target modul. |
| **Model Thread Safety** | Pastikan seluruh Model/Payload yang melintasi isolasi actor mengadopsi `Sendable`. | Tipe `final class` dengan properti konstan, atau `struct/enum` bernilai murni. |
| **UI Boundaries** | Verifikasi seluruh mutasi properti `@Observable` / `@Published` terjadi pada eksekutor UI. | Menggunakan anotasi `@MainActor` pada Class/ViewModel secara eksplisit. |
| **Cancellation Handling** | Mengimplementasikan `try Task.checkCancellation()` atau `Task.isCancelled` pada iterasi panjang. | Loop berhenti segera saat user meninggalkan layar (View pop/dismiss). |
| **Buffer Overflow Safeguard** | Mengonfigurasi `AsyncStream.Continuation.BufferingPolicy` secara eksplisit pada streaming data tinggi. | Kebijakan `.bufferingNewest` atau `.bufferingOldest` ditetapkan; tidak menggunakan unbounded policy. |
| **Continuations Safety** | Menggunakan `withCheckedContinuation` selama tahap pengembangan/staging. | Runtime akan melakukan `assertionFailure` jika ada missing / duplicate continuation resume. |

---

### 12. Hands-on Practice

Buat dan simpan file-file berikut pada direktori: `hands-on/m02/`

#### File: `hands-on/m02/SensorPipeline.swift`
Langkah implementasi komponen pipeline data telemetri:
1.  Buka terminal, buat direktori target:
    ```bash
    mkdir -p hands-on/m02
    cd hands-on/m02
    ```
2.  Tuliskan implementasi pemrosesan telemetri berkecepatan tinggi dengan proteksi pembatalan dan buffer bounded:

```swift
// hands-on/m02/SensorPipeline.swift
import Foundation

public struct SensorMetric: Sendable, Identifiable {
    public let id: Int
    public let reading: Double
    public let timestamp: Date
}

public actor TelemetryProcessor {
    private var records: [SensorMetric] = []
    
    public init() {}

    public func processBatch(_ batch: [SensorMetric]) async throws -> Double {
        // Simulasi cooperative work
        try Task.checkCancellation()
        
        let validMetrics = batch.filter { $0.reading >= 0.0 }
        records.append(contentsOf: validMetrics)
        
        // Komputasi rata-rata
        let sum = validMetrics.reduce(0.0) { $0 + $1.reading }
        return validMetrics.isEmpty ? 0.0 : sum / Double(validMetrics.count)
    }

    public func getRecordCount() -> Int {
        return records.count
    }
}

public final class HardwareSensorHub: Sendable {
    public init() {}

    public func startStream(totalEvents: Int) -> AsyncThrowingStream<SensorMetric, Error> {
        return AsyncThrowingStream(bufferingPolicy: .bufferingNewest(50)) { continuation in
            let producer = Task {
                for index in 1...totalEvents {
                    if Task.isCancelled { break }
                    
                    let metric = SensorMetric(
                        id: index,
                        reading: Double.random(in: -5.0...100.0),
                        timestamp: .now
                    )
                    continuation.yield(metric)
                    
                    // Emisi tiap 10 milidetik
                    try? await Task.sleep(for: .milliseconds(10))
                }
                continuation.finish()
            }
            
            continuation.onTermination = { @Sendable _ in
                producer.cancel()
            }
        }
    }
}
```

#### File: `hands-on/m02/main.swift`
Entry-point pengujian lokal:
```swift
// hands-on/m02/main.swift
import Foundation

@main
struct Harness {
    static func main() async {
        print("=== Memulai Engine Concurrency Sandbox ===")
        let sensor = HardwareSensorHub()
        let processor = TelemetryProcessor()
        let stream = sensor.startStream(totalEvents: 100)
        
        var buffer: [SensorMetric] = []
        
        do {
            for try await metric in stream {
                buffer.append(metric)
                
                if buffer.count >= 20 {
                    let toFlush = buffer
                    buffer.removeAll(keepingCapacity: true)
                    
                    let average = try await processor.processBatch(toFlush)
                    print("Batch diproses. Rata-rata: \(String(format: "%.2f", average))")
                }
            }
            print("Pemrosesan Selesai. Total tersimpan: \(await processor.getRecordCount()) data.")
        } catch {
            print("Terjadi kegagalan: \(error)")
        }
    }
}
```

Jalankan pengujian via command-line:
```bash
swiftc -parse-as-library SensorPipeline.swift main.swift -o SandboxRunner
./SandboxRunner
```

---

### 13. Exercise

#### Level: Easy
Refactor fungsi *completion-handler* berikut ke format `async/await` menggunakan `withCheckedThrowingContinuation`.
```swift
func fetchAppConfiguration(completion: @escaping (Result<[String: String], Error>) -> Void)
```
*Batasan:* Tangani error dengan aman, pastikan continuation terpanggil saat throwing maupun success.

#### Level: Medium
Buat sebuah Actor bernama `ImageMemoryCache`.
*   Menyimpan representasi bytes `[URL: Data]`.
*   Memiliki fungsi `data(for url: URL) async throws -> Data`.
*   Jika image belum ada di memori, unduh dari URL menggunakan `URLSession.shared.data(from: url)`.
*   **Wajib:** Hindari *Duplicate In-Flight Requests*. Jika ada 5 callers meminta URL yang sama secara bersamaan saat cache kosong, network request hanya boleh terjadi 1 kali; 4 callers lainnya menunggu (`await`) hasil dari request pertama tersebut.

#### Level: Hard
Rancang sebuah tipe generic struct: `BackpressuredBatchQueue<T: Sendable>`.
*   Menerima elemen stream dengan throughput tinggi.
*   Mengakumulasi elemen dan mengeluarkan emisi (*flush*) ke listener hanya jika salah satu dari kondisi terpenuhi:
    1. Jumlah elemen yang di-buffer mencapai `maxBatchSize` (misal: 100 items).
    2. Waktu sejak item pertama masuk buffer mencapai `maxLatency` (misal: 50 milidetik).
*   **Wajib:** Harus *thread-safe*, memanfaatkan Swift Concurrency primitif (`ContinuousClock`, `TaskGroup`, atau unstructured tasks terkontrol), dan tidak boleh menyebabkan frame-drop saat diintegrasikan dengan `@Observable` ViewModel.

---

### 14. Challenge

Rancang arsitektur **Offline-First Synchronization Engine** untuk aplikasi Audit Medis Lapangan (Enterprise Healthcare):

1.  **Skenario:** Tim medis melakukan input ratusan data parameter vital pasien di daerah pedalaman tanpa sinyal. Tablet memiliki buffer lokal. Ketika perangkat mendeteksi jaringan (Wi-Fi/Cellular) yang unstable (konektivitas intermittent, latensi fluktuatif 200ms - 8000ms), sinkronisasi batch harus berjalan di latar belakang.
2.  **Spesifikasi Persyaratan Teknis:**
    *   **Prioritas Queue Terstruktur:** Data critical (denyut jantung anomali, kode darurat) harus didahulukan dibanding data demografis standar.
    *   **Actor Re-entrancy Protection:** Antrean sinkronisasi tidak boleh mengunggah ulang data medis yang sedang *in-flight* ke server meskipun koneksi terputus dan tersambung kembali di tengah proses transmisi.
    *   **Frame-rate Integrity:** Seluruh proses enkripsi AES-256 dan serialisasi data wajib berjalan pada worker threads non-UI dengan *cooperative yielding*, menjaga SwiftUI scroll view tetap berjalan stabil pada 120Hz di layar iPad Pro ProMotion.
    *   **Graceful Cancellation:** Ketika sistem beralih ke *Low Power Mode* atau aplikasi berpindah ke background dengan `backgroundTimeRemaining` menipis, engine harus membatalkan child tasks secara deterministik dan menyimpan offset sinkronisasi terakhir secara atomic.
3.  **Output yang Diharapkan:** Susun arsitektur dokumen teknis berupa class/actor breakdown diagram, interface protokol, serta skema isolasi concurrency yang mengeliminasi potensi race condition secara matematis/statis di bawah aturan Swift 6.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic (5 Pertanyaan)
1.  Apa yang membedakan *Cooperative Thread Pool* pada Swift Concurrency dengan thread pool konvensional pada GCD?
2.  Mengapa sebuah closure di dalam `Task.detached` tidak otomatis terisolasi pada `@MainActor` meskipun diinstansiasi di dalam SwiftUI View `body`?
3.  Apa fungsi dari macro/protokol `Sendable` dan masalah apa yang dicegah oleh compiler melaluinya?
4.  Kapan runtime Swift melemparkan fatal error saat menggunakan `CheckedContinuation`?
5.  Apa perbedaan mendasar antara `Task.isCancelled` dan `try Task.checkCancellation()`?

#### B. Intermediate (5 Pertanyaan)
6.  Jelaskan skenario bagaimana fenomena *Actor Re-entrancy* dapat merusak state atomik sebuah actor meskipun tidak ada thread race condition tradisional!
7.  Bagaimana modifier view `.task(id: someValue)` di SwiftUI merespons perubahan nilai pada `someValue`?
8.  Sebutkan risiko penggunaan `AsyncStream` tanpa menyertakan `BufferingPolicy` tertentu pada aplikasi produksi!
9.  Mengapa pemanggilan fungsi sinkronisasi blocking seperti `objc_sync_enter` atau `dispatch_semaphore_wait` di dalam fungsi `async` dianggap pelanggaran berat (*severe antipattern*) pada Swift Concurrency?
10. Bagaimana cara kerja hierarki pembatalan (*cancellation propagation*) pada `withTaskGroup` ketika salah satu child task melempar error (*throws*)?

#### C. Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario 1:** Sebuah aplikasi pelacak navigasi saham sering mengalami crash bertipe `EXC_BAD_INSTRUCTION` pada method pembacaan cache pasca migrasi ke Swift 5.9 dengan flag `-strict-concurrency=complete`. Cache diimplementasikan sebagai `class MemoryStorage: @unchecked Sendable` yang membungkus `NSMutableDictionary` tanpa lock. Mengapa crash baru terdeteksi/terjadi secara masif setelah migrasi ke structured concurrency?
12. **Skenario 2:** Profiling instrumen *Time Profiler* menunjukkan adanya lag antarmuka (UI Freezes) hingga 150ms pada view order entry. Kode menunjukkan deklarasi `@MainActor class OrderEntryViewModel` yang mengeksekusi iterasi 100.000 loop decoding kriptografi secara langsung di dalam fungsi `func processOrder() async`. Mengapa eksekusi tersebut membekukan UI padahal fungsi bertanda `async`?
13. **Skenario 3:** Tim Anda mendeteksi bahwa memori aplikasi melonjak tinggi saat pengguna membuka layar live-chat customer service yang menggunakan `AsyncStream`. Setelah pengguna menutup layar tersebut (*dismiss*), stream publisher di network layer masih terus berjalan dan memori tidak turun. Bagian arsitektur mana yang mengalami kegagalan desain (*leakage*)?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Jawaban Basic
1.  Cooperative Thread Pool membatasi jumlah thread aktif hanya sebanyak core CPU fisik dan mengeksekusi Continuation Jobs secara non-blocking; GCD dapat membuat ratusan thread baru saat terjadi thread blocking (memicu thread explosion).
2.  `Task.detached` secara eksplisit melepaskan diri dari context eksekutor pemanggil (tidak mewarisi actor context, priority, maupun task-local values).
3.  `Sendable` menandai bahwa suatu tipe data aman untuk dipindahkan batas isolasi konkurensinya (*across concurrency boundaries*) secara thread-safe tanpa risiko data races.
4.  Saat continuation di-resume lebih dari satu kali (*double resume*), atau saat continuation dilepaskan dari memori (*deallocated*) tanpa pernah di-resume sama sekali (*leaked continuation*).
5.  `Task.isCancelled` mengembalikan nilai Boolean (non-throwing) sehingga flow kontrol dapat diarahkan secara manual; sedangkan `try Task.checkCancellation()` otomatis melempar `CancellationError` jika task telah dibatalkan.

#### Jawaban Intermediate
6.  Ketika actor mengeksekusi operasi asinkron dan mencapai titik suspensi `await`, actor melepas lock-nya. Pesan/tugas lain dapat masuk ke actor dan mengubah *internal state*. Saat tugas awal dilanjutkan (*resumes*), asumsi data lokal yang diperiksa sebelum suspensi bisa menjadi usang/tidak valid.
7.  SwiftUI akan membatalkan task yang sedang berjalan (mengirimkan sinyal cancellation) dan segera membuat task baru dengan context parameter `someValue` yang baru.
8.  Tanpa batas buffer, policy default adalah *unbounded buffer*. Jika data diproduksi lebih cepat daripada kemampuan consumer memprosesnya, buffer memori heap akan membesar tanpa batas hingga OS mematikan aplikasi karena Out-Of-Memory (Jetsam event).
9.  Cooperative thread pool memiliki thread yang terbatas (sesuai core CPU). Memblokir thread worker secara fisik akan mencuri kapasitas thread global, menyebabkan thread pool starvation dan membuat task async lain di seluruh sistem aplikasi mengalami kemacetan eksekusi (*freeze*).
10. Melempar error di dalam task group tidak otomatis membatalkan sibling tasks yang lain kecuali pengembang secara eksplisit memanggil `group.cancelAll()` atau menangani flow pembatalan di block catch task group tersebut.

#### Jawaban Skenario Kasus Produksi
11. `@unchecked Sendable` menonaktifkan diagnosa keamanan compiler untuk kelas tersebut. Ketika GCD digantikan oleh Cooperative Pool yang sangat agresif dalam melakukan *work-stealing* dan pemindahan job lintas thread fisik, akses konkuren yang simultan langsung menghancurkan pointer memory internal `NSMutableDictionary` yang tidak thread-safe. Solusinya: Ubah menjadi `actor` atau lindungi state dengan `OSAllocatedUnfairLock`.
12. Anotasi `@MainActor` pada kelas menyebabkan **seluruh method di dalamnya terikat untuk dieksekusi di Main Thread secara default**, meskipun method tersebut bertanda `async`. Operasi CPU-heavy tersebut dijalankan di atas thread utama. Solusinya: Pindahkan komputasi berat tersebut ke `nonisolated` function, worker `actor`, atau jalankan secara terpisah di background worker pool.
13. `AsyncStream.Continuation` tidak mengimplementasikan closure `onTermination`, atau subscription task tidak dibatalkan pada siklus hidup view (misal: tidak dikaitkan dengan lifecycle `.task` SwiftUI atau tidak membatalkan streaming producer saat `deinit`), menyebabkan cyclic retention atau infinite task loop pada background data transceiver.

---

### 16. Summary
*   **Swift Modern Concurrency** mentransformasikan paradigma pengikatan thread: Dari model pembuatan thread tak terbatas pada GCD menjadi **Cooperative Thread Pool** berbasis *Continuation Tasks* yang terikat pada jumlah core prosesor fisik.
*   **Actor Isolation** menyediakan garansi keamanan memori dari *data race* saat kompilasi, namun menuntut mitigasi arsitektural terhadap **Actor Re-entrancy** pada setiap jeda suspensi (`await`).
*   Integrasi deterministik dengan **SwiftUI AttributeGraph** mewajibkan penataan batas isolasi yang kaku: Semua mutasi state render harus berada di bawah kendali `@MainActor`, sementara komputasi data throughput tinggi diorkestrasi di luar main thread melalui **TaskGroup** dan **AsyncStream dengan Backpressure Limits**.
*   Kepatuhan terhadap standar **Swift 6 Complete Concurrency Checking** menuntut eliminasi total terhadap pointer sharing yang tidak aman melalui adopsi tipe nilai murni bertipe `Sendable`.