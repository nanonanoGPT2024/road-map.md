# Bab 04 Module 01: Pemrograman Asinkron Modern & Swift Concurrency

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran:** Frontend and Mobile Engineering (`03-Frontend-and-Mobile`)
*   **Track:** iOS Native Development Enterprise Track
*   **Modul:** Bab 04 Module 01
*   **Topik Utama:** Pemrograman Asinkron Modern & Swift Concurrency
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** Pemahaman mendalam tentang ARC (Automatic Reference Counting), Swift Closures, Threading dasar, Grand Central Dispatch (GCD), serta siklus hidup aplikasi iOS.

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik diharapkan mampu:
1.  Menganalisis dan membongkar arsitektur kooperatif Swift Concurrency Runtime serta perbedaannya secara mekanis dibanding *thread-per-task model* (GCD).
2.  Mengimplementasikan pola `async/await`, structured concurrency (`TaskGroup`, `async let`), dan unstructured tasks (`Task`, `Task.detached`) secara presisi tanpa memicu *concurrency leaks*.
3.  Menerapkan isolasi data dan konkurensi aman bebas data race menggunakan `Actor`, `GlobalActor` (`@MainActor`), serta protokol penanda `Sendable` dalam sistem bertaraf *Complete Concurrency Checking* (Swift 6).
4.  Mengembangkan pipeline aliran data asinkron reaktif berbasis `AsyncSequence`, `AsyncStream`, dan kustom backpressure controller.
5.  Melakukan instrumentasi, deteksi deadlock/starvation, dan profiling alokasi context switching menggunakan Instruments (Time Profiler & Swift Concurrency Trace).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam paradigma komputasi konkuren terdahulu (Grand Central Dispatch / `pthread`), programmer memandang konkurensi dari perspektif *Thread Execution Management*: mengeksekusi closure pada antrean tertentu (`DispatchQueue.global().async`) dan berharap sistem operasi menjadwalkannya tanpa terjadi *thread explosion*. Konsekuensinya adalah pemborosan memori akibat alokasi tumpukan (stack) per thread (masing-masing ~512 KB hingga 1 MB di iOS) dan *kernel context-switching overhead* yang masif.

```
PARADIGMA GCD (THREAD EXPLOSION RISK)
Request 1 ──► [Thread 1 (Stack 512KB)] ──► Blocking I/O ──► Kernel Context Switch
Request 2 ──► [Thread 2 (Stack 512KB)] ──► Blocking I/O ──► Kernel Context Switch
Request N ──► [Thread N (Stack 512KB)] ──► OOM / CPU Thrashing

PARADIGMA SWIFT CONCURRENCY (COOPERATIVE THREAD POOL)
Tasks (Job) ──► [ Fixed Cooperative Thread Pool (= CPU Cores ) ]
Continuation ──► Suspends to Heap, Thread remains 100% active for next Job
```

Mental model Swift Concurrency bergeser dari **Thread Allocation** ke **Continuation Suspension over a Cooperative Pool**:
1.  **Cooperative Thread Pool:** Runtime Swift hanya mengalokasikan thread sejumlah core CPU logis perangkat (misal: 6 core pada A16/A17 Bionic). Jumlah thread eksekusi tidak pernah membengkak secara eksponensial.
2.  **Suspension Point (`await`):** Ketika sebuah fungsi asinkron ditangguhkan via `await`, kontrol eksekusi melepaskan thread saat itu juga. Alih-alih memblokir thread (seperti `semaphore.wait()` atau I/O sinkron), frame fungsi dikemas menjadi objek *Continuation* di memori heap, dan thread yang sama langsung digunakan oleh runtime untuk mengeksekusi pekerjaan lain (*Job*).
3.  **Forward Progress Invariant:** Sistem mengasumsikan bahwa setiap task yang dialokasikan akan selalu memberikan jalan (yield/suspend) atau menyelesaikan eksekusinya, melarang pemblokiran primitif yang menahan thread eksekusi.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur Swift Concurrency dibangun di atas Swift Runtime Layer yang berinteraksi langsung dengan Darwin Kernel Libdispatch. Di bawah ini adalah pemetaan arsitektural eksekusi tugas dari level abstraksi tinggi hingga context switching thread kooperatif:

```
+-------------------------------------------------------------------------+
|                              APLIKASI iOS                               |
|   +-----------------------------------------------------------------+   |
|   |                  @MainActor (UI Interaction)                    |   |
|   +-----------------------------------------------------------------+   |
|         │ Task { await download() }                │ TaskGroup.addTask  |
|         ▼                                          ▼                    |
|   +-----------------------+              +--------------------------+   |
|   | Structured Task Tree  |              | Unstructured Background  |   |
|   | (async let / Groups)  |              | Task.detached            |   |
|   +-----------------------+              +--------------------------+   |
+-------------------------------------------------------------------------+
                                    │
                                    ▼
+-------------------------------------------------------------------------+
|                         SWIFT RUNTIME CONCURRENCY                       |
|   +─────────────────────────────────────────────────────────────────+   |
|   |      Continuation Allocator & Task Dependency DAG Engine        |   |
|   +─────────────────────────────────────────────────────────────────+   |
|   | Cooperative Executor (Work-Stealing Queue Engine)               |   |
|   |                                                                 |   |
|   |  Global Run-Queue: [Job 4] [Job 5] [Job 6]                      |   |
|   |                                                                 |   |
|   |  Worker 1 (Core 0): [Job 1] ──suspension──> Yield to [Job 4]    |   |
|   |  Worker 2 (Core 1): [Job 2]                                     |   |
|   |  Worker 3 (Core 2): [Job 3] ──suspension──> Steal [Job 5]       |   |
|   |  Worker 4 (Core 3): [Idle]  ──work-steal──> Steal [Job 6]       |   |
|   +─────────────────────────────────────────────────────────────────+   |
+-------------------------------------------------------------------------+
                                    │
                                    ▼
+-------------------------------------------------------------------------+
|                          DARWIN KERNEL LAYER                            |
|     pthread_workqueue  ───► Fixed Size Native Threads (CPU Bound)       |
+-------------------------------------------------------------------------+
```

### Diagram Alur: Lifecycle Eksekusi & Suspension

```
[Pemanggilan Task]
       │
       ▼
[Task Dialokasikan di Heap] ─── (Inherits Priority & Actor Context)
       │
       ▼
[Jadwalkan ke Cooperative Executor]
       │
       ▼
[Thread Kooperatif Menjalankan Frame]
       │
       ├───► [Ketemu Titik "await"] ───► Simpan Frame ke Continuation (Heap)
       │                                 Lepaskan Thread ke Job Lain
       │                                 I/O Berjalan Asinkron di OS Kernel
       │                                              │
       │                                 I/O Selesai / Sinyal Kernel Aktif
       │                                              │
       │                                 Enqueue Ulang Continuation
       │                                              ▼
       └───◄─── Resume Eksekusi ◄─────── [Thread Bebas Mengambil Job]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Task di Memori Heap
Sebuah `Task` dalam Swift bukan representasi thread kernel. Secara fisik, `Task` adalah instance dari struktur internal C++ `swift::AsyncTask` di runtime Swift:
*   **Header Ref Count:** Status referensi siklus hidup task.
*   **Status Flags:** Membawa flag pembatalan (`isCancelled`), prioritas task (`TaskPriority`), dan status penangguhan (`suspended`, `running`, `enqueued`).
*   **Continuation Context Pointer:** Pointer ke stack frame yang tersimpan di heap saat fungsi mencapai titik suspensi `await`.

### 2. Async Frame Allocation (Asynchronous Stacks)
Pada fungsi sinkron biasa, pemanggilan fungsi mendorong *call frame* baru ke thread stack memori native. Pada Swift Concurrency:
*   Fungsi yang ditandai `async` mengalokasikan frame komputasinya pada *Task-Local Heap-allocated Storage* yang dikenal sebagai **Async Frame**.
*   Saat suspensi (`await`), stack pointer native tidak tertahan. Pointer async frame tetap valid di heap. Begitu pemanggilan I/O selesai, thread yang sedang menganggur dapat membaca heap frame ini dan melanjutkan instruksi assembly selanjutnya (melalui instruction pointer/IP resume offset).

### 3. Actor Reentrancy & Mailbox Mechanism
Actor diisolasi menggunakan abstraksi antrean pesan internal (*Actor Mailbox*):
*   Sebuah `actor` menjamin *Mutual Exclusion* (hanya satu thread yang dapat mengakses state internalnya pada satu satuan waktu).
*   **Actor Reentrancy:** Jika Task A sedang mengeksekusi metode di dalam Actor X dan mencapai `await`, eksekusi Task A di dalam Actor X **ditangguhkan**. Actor X membuka kuncinya dan bebas memproses Task B yang ada di mailbox-nya sebelum Task A melanjutkan sisa eksekusinya. 
*   **Risiko State Inconsistency:** State lokal actor dapat berubah secara signifikan antara sebelum `await` dan sesudah `await`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Structured Concurrency vs Unstructured Concurrency
Prinsip fundamental dari Structured Concurrency adalah: **Masa hidup (lifetime) sebuah konkurensi dibatasi secara statis oleh scope blok sintaks tempat ia dibuat.**

```
Structured Concurrency Tree:
Parent Task Scope
  │
  ├── async let a = fetchA()  ───┐ Anakan Task terikat secara deterministik.
  ├── async let b = fetchB()  ───┤ Jika Parent di-cancel atau melempar error,
  │                              │ semua anakan di-cancel otomatis secara cascading.
  └── await (a, b) ──────────────┘
```

Sebaliknya:
*   `Task { }`: Unstructured Task. Mewarisi aktor konteks pemanggil, mewarisi prioritas, tetapi memiliki siklus hidup independen (outlives the enclosing scope).
*   `Task.detached { }`: Completely Unstructured. Tidak mewarisi isolasi aktor pemanggil, tidak mewarisi prioritas, berjalan murni di global pool.

### Protokol `Sendable` dan Definisi Type Isolation
Swift 6 mengaktifkan aturan *Data Race Safety by Default*. Inti penjaminnya adalah protokol semantik compiler: `Sendable`.
*   Tipe nilai (`struct`, `enum`) secara intrinsik memenuhi syarat `Sendable` jika semua stored property-nya bertipe `Sendable`.
*   Tipe referensi (`class`) hanya bisa menjadi `Sendable` jika:
    1. Ditandai `final` dan semua property bernilai `immutable` (`let`) dan bertipe `Sendable`.
    2. Menggunakan proteksi penguncian manual internal yang divalidasi dengan atribut `@unchecked Sendable`.

```swift
// Valid: Safe value semantics
public struct UserPayload: Sendable {
    public let id: UUID
    public let username: String
}

// Invalid: Mengakibatkan Compiler Error di Swift 6 (Shared Mutable State)
public class UnsafeSessionState {
    public var token: String = "" // Thread safety hazard!
}
```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi fundamental yang menggabungkan pembacaan paralel menggunakan `async let`, structured error handling, serta eksekusi aktor yang aman.

```swift
import Foundation

// MARK: - Model Sendable
public struct MarketInstrument: Sendable, Codable {
    public let ticker: String
    public let basePrice: Double
}

// MARK: - Isolated Actor State
public actor PriceCacheStore {
    private var cache: [String: Double] = [:]

    public func update(ticker: String, price: Double) {
        cache[ticker] = price
    }

    public func getPrice(for ticker: String) -> Double? {
        return cache[ticker]
    }
}

// MARK: - Business Logic Layer
public final class MarketDataEngine {
    private let cacheStore = PriceCacheStore()

    public func fetchLivePrice(for ticker: String) async throws -> Double {
        // Simulasi latensi jaringan I/O
        try await Task.sleep(nanoseconds: 100_000_000) // 100ms
        switch ticker {
        case "AAPL": return 185.50
        case "GOOGL": return 142.20
        default: return 100.00
        }
    }

    public func aggregatePortfolioBalance() async throws -> Double {
        // Structured Parallel Execution menggunakan async let
        async let fetchAAPL = fetchLivePrice(for: "AAPL")
        async let fetchGOOGL = fetchLivePrice(for: "GOOGL")

        // Penangguhan bersamaan hingga kedua child task selesai
        let (priceAAPL, priceGOOGL) = try await (fetchAAPL, fetchGOOGL)

        // Akses aman ke state actor dengan await
        await cacheStore.update(ticker: "AAPL", price: priceAAPL)
        await cacheStore.update(ticker: "GOOGL", price: priceGOOGL)

        return priceAAPL + priceGOOGL
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis dari baris kode kritis pada SEKSI 07:

1.  `public struct MarketInstrument: Sendable, Codable`: Mendeklarasikan bahwa struktur ini dapat ditransfer melintasi batas domain konkurensi (antar aktor atau thread pool) tanpa menyebabkan data race. Compiler memverifikasi semua field adalah *Sendable*.
2.  `public actor PriceCacheStore`: Menghasilkan tipe isolasi konkurensi. Compiler Swift mengimplementasikan *internal lockless sync mailbox* untuk properti `var cache`.
3.  `public func update(ticker: String, price: Double)`: Metode isolasi aktor sinkron dari perspektif internal aktor, tetapi membutuhkan `await` saat dipanggil dari luar domain `PriceCacheStore`.
4.  `async let fetchAAPL = fetchLivePrice(for: "AAPL")`: Membuat *child task* baru yang dieksekusi serentak (*concurrently*) pada cooperative thread pool. Frame alokasi child task ini terikat langsung ke stack context pemanggil.
5.  `let (priceAAPL, priceGOOGL) = try await (fetchAAPL, fetchGOOGL)`: Titik suspensi resmi (*suspension point*). Thread pemanggil melepaskan eksekusinya dan runtime menunggu kedua child task mengembalikan nilai atau salah satunya melempar `Error`. Jika salah satu melempar `Error`, child task lainnya secara otomatis menerima sinyal *cancellation*.
6.  `await cacheStore.update(...)`: Crossing isolation boundaries. Thread berpindah context/menunggu mailbox `PriceCacheStore` kosong sebelum memutasi `cache`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Engine Pemrosesan Transaksi Finansial (High-Frequency Trading Telemetry)
Pada aplikasi Mobile Banking & Trading Enterprise, sistem harus menerima aliran data harga secara kontinu via WebSocket, memfilter fluktuasi, melakukan verifikasi terhadap saldo akun lokal, serta menjalankan batching analitik data transaksi secara paralel tanpa pernah membuat antarmuka pengguna (*Main Thread*) kehilangan frame (60/120 FPS drops).

### Masalah Arsitektural:
1.  **Backpressure & Memory Leaks:** Emisi data WebSocket berkecepatan tinggi dapat menumpuk di memori jika subscriber lambat mengonsumsinya.
2.  **State Contention:** Sinkronisasi saldo akun dan riwayat order diakses serentak oleh sinkronisasi UI, worker transaksi offline, dan background sync network worker.
3.  **UI Hangs / Thread Saturation:** Penjadwalan pemrosesan kalkulasi kriptografis transaksi yang salah di GCD dapat memicu thread explosion hingga puluhan thread, menyebabkan kernel starvation.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Arsitektur produksi berikut mengintegrasikan: `AsyncStream` dengan kapasitas buffering terkontrol (Backpressure), `ThrowingTaskGroup` dengan pembatasan konkurensi maksimum (*Worker Pool Pattern*), serta isolasi `@MainActor` terarah.

```swift
import Foundation

// MARK: - Domain Models
public struct TransactionOrder: Identifiable, Sendable, Codable {
    public let id: UUID
    public let symbol: String
    public let amount: Double
    public let timestamp: Date
}

public enum OrderProcessingError: Error, Sendable {
    case networkTimeout
    case insufficientLiquidity
    case cancelledByUser
}

// MARK: - Actor State Manager: Ledger Store
public actor PortfolioLedgerActor {
    private var totalBalance: Double
    private var executedOrders: [UUID: TransactionOrder] = [:]

    public init(initialBalance: Double) {
        self.totalBalance = initialBalance
    }

    public func debit(amount: Double, for order: TransactionOrder) throws {
        guard totalBalance >= amount else {
            throw OrderProcessingError.insufficientLiquidity
        }
        totalBalance -= amount
        executedOrders[order.id] = order
    }

    public func currentBalance() -> Double {
        return totalBalance
    }
}

// MARK: - Production Engine with AsyncStream & Bounded TaskGroup
public final class ResilientOrderProcessingEngine: Sendable {
    private let ledger: PortfolioLedgerActor

    public init(ledger: PortfolioLedgerActor) {
        self.ledger = ledger
    }

    /// Menghasilkan stream transaksional yang aman dari buffer overflow (Backpressure Control)
    public func createLiveOrderStream() -> (AsyncStream<TransactionOrder>, AsyncStream<TransactionOrder>.Continuation) {
        var continuationRef: AsyncStream<TransactionOrder>.Continuation?
        let stream = AsyncStream<TransactionOrder>(bufferingPolicy: .bufferingNewest(100)) { continuation in
            continuationRef = continuation
        }
        // Force unwrap aman di sini karena closure AsyncStream dieksekusi secara sinkronis pada inisialisasi
        return (stream, continuationRef!)
    }

    /// Memproses batch order menggunakan Pola Concurrency Limiting (Mencegah Resource Exhaustion)
    public func processBatchOrdersConcurrently(
        orders: [TransactionOrder], 
        maxConcurrentTasks: Int
    ) async throws -> [UUID] {
        guard !orders.isEmpty else { return [] }

        return try await withThrowingTaskGroup(of: UUID.self) { group in
            var processedOrderIDs: [UUID] = []
            processedOrderIDs.reserveCapacity(orders.count)

            var currentIndex = 0
            let total = orders.count

            // Batch initial filling: Hanya alokasikan sejumlah slot konkurensi aman
            let initialBatchLimit = min(maxConcurrentTasks, total)
            for _ in 0..<initialBatchLimit {
                let order = orders[currentIndex]
                currentIndex += 1
                group.addTask {
                    return try await self.executeInternalOrderTransaction(order)
                }
            }

            // Pool Sliding Window: Saat satu task selesai, masukkan task berikutnya
            for try await completedOrderID in group {
                processedOrderIDs.append(completedOrderID)
                
                // Cek status pembatalan parent
                try Task.checkCancellation()

                if currentIndex < total {
                    let nextOrder = orders[currentIndex]
                    currentIndex += 1
                    group.addTask {
                        return try await self.executeInternalOrderTransaction(nextOrder)
                    }
                }
            }

            return processedOrderIDs
        }
    }

    private func executeInternalOrderTransaction(_ order: TransactionOrder) async throws -> UUID {
        // Periksa kooperatif pembatalan sebelum operasi intensif
        try Task.checkCancellation()

        // Simulasi latensi RPC / Enkripsi payload
        try await Task.sleep(nanoseconds: 50_000_000) // 50ms

        // Crossing boundary ke Actor: Melindungi data balance mutasi
        try await ledger.debit(amount: order.amount, for: order)

        return order.id
    }
}

// MARK: - UI Coordinator (MainActor Presentation Binding)
@MainActor
public final class OrderProcessingViewModel {
    private let engine: ResilientOrderProcessingEngine
    private let ledger: PortfolioLedgerActor
    
    public private(set) var displayBalance: Double = 0.0
    public private(set) var isProcessing: Bool = false
    private var streamProcessingTask: Task<Void, Never>?

    public init(engine: ResilientOrderProcessingEngine, ledger: PortfolioLedgerActor) {
        self.engine = engine
        self.ledger = ledger
    }

    public func startListeningToLiveOrders(stream: AsyncStream<TransactionOrder>) {
        streamProcessingTask?.cancel() // Batalkan task listener lama jika aktif
        
        streamProcessingTask = Task { [weak self] in
            for await order in stream {
                guard let self = self else { return }
                do {
                    _ = try await self.engine.processBatchOrdersConcurrently(orders: [order], maxConcurrentTasks: 1)
                    // Mutasi state MainActor dilakukan secara otomatis di thread utama
                    self.displayBalance = await self.ledger.currentBalance()
                } catch {
                    // Logging terpusat dan graceful degradation
                    print("Gagal mengeksekusi order: \(order.id), Error: \(error)")
                }
            }
        }
    }

    public func teardown() {
        streamProcessingTask?.cancel()
        streamProcessingTask = nil
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek / Primitif | Grand Central Dispatch (GCD) | Swift Concurrency (Structured) | Combine Framework |
| :--- | :--- | :--- | :--- |
| **Model Threading** | Mengalokasikan thread baru (Thread-per-Queue). Rentan *Explosion*. | Cooperative Pool (Jumlah thread tetap = Core CPU). | Menggunakan pool GCD bawaan atau RunLoop. |
| **Penyimpanan Context** | Thread Stack (512KB - 1MB per thread native). | Async Frames di Heap Memory (Alokasi dinamis ringan). | Pipeline Subscription Graph di Heap. |
| **Keamanan Tipe Compiler** | Manual (`@escaping closures`). Rentan data races. | Validasi Statis Compile-time (`Sendable`, Actor Isolation). | Terisolasi parsial; manual race-safety mitigations. |
| **Propagasi Pembatalan** | Manual (`DispatchWorkItem.cancel()`), tidak terintegrasi ke child. | Otomatis (*Cascading Cooperative Cancellation*). | Deklaratif melalui siklus hidup token `AnyCancellable`. |
| **Debuggability** | Call stack terfragmentasi antar block context. | Full Structured Stack Traces via LLDB Async Unwinder. | Stack traces sangat dalam dan sulit dibaca (operator trees). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Actor Reentrancy Hazard (Interleaved State Mutation)
Sebuah actor **bukan** sebuah *recursive lock*. Begitu Anda menuliskan `await` di dalam metode actor, Anda melepaskan hak monopoli eksekusi thread atas actor tersebut.

```swift
// CRITICAL HAZARD: Interleaved Mutation
actor InventoryManager {
    var stockCount: Int = 10

    func purchaseItem() async -> Bool {
        // Titik 1: Pengecekan kondisi
        if stockCount > 0 {
            // Suspensi I/O: Thread dilepas! Task lain masuk dan memanggil purchaseItem()
            let paymentSuccess = await PaymentGateway.charge()
            
            // Titik 2: Resume. State stockCount BISA JADI sudah 0 akibat diproses task lain!
            if paymentSuccess {
                stockCount -= 1 // POTENSI NEGATIVE STOCK
                return true
            }
        }
        return false
    }
}
```
**Mitigasi:** Validasi ulang (*re-check*) kondisi invariabel state Anda segera setelah titik balik suspensi `await`, atau desain mutasi state actor sebagai operasi atomik tanpa disisipi `await`.

### 2. Cooperative Thread Pool Starvation
Jika Anda menjalankan operasi blocking sinkron (seperti `FileManager`, komputasi hashing intensif, atau `pthread_mutex_lock`) langsung di dalam task kooperatif, thread di pool akan terkuras. Karena pool bersifat terikat core CPU (misal: 6 thread), menjalankan 6 blocking call akan **membekukan seluruh operasi Swift Concurrency di aplikasi**.
*Mitigasi:* Jalankan tugas blocking murni pada legacy queue `DispatchQueue.global().async` atau batasi eksekusi I/O sinkronik di luar cooperative pool.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mengabaikan Pemeriksaan Pembatalan di Operasi Loop/Intensif
*Anti-Pattern:* Task induk telah di-cancel, namun child loop tetap mengeksekusi operasi mahal hingga selesai.

```swift
// BURUK
func parseLargeDataset(items: [Data]) async -> [DecodedItem] {
    var results: [DecodedItem] = []
    for item in items {
        results.append(decode(item)) // Terus berjalan meski task dibatalkan
    }
    return results
}

// BENAR
func parseLargeDataset(items: [Data]) async throws -> [DecodedItem] {
    var results: [DecodedItem] = []
    for item in items {
        try Task.checkCancellation() // Langsung lempar CancellationError
        results.append(decode(item))
    }
    return results
}
```

### Kesalahan 2: Menyalahgunakan `Task.detached` untuk Lari dari `@MainActor`
*Anti-Pattern:* Menggunakan `Task.detached` di ViewModel untuk komputasi cepat.
*Dampak:* Kehilangan prioritas task pemanggil, kehilangan Task-local values context, dan alokasi cost context-switch overhead yang tidak perlu.
*Solusi:* Gunakan non-isolated method atau structured child task terpisah alih-alih `Task.detached`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Strict Concurrency Flag Enabled:** Selalu aktifkan build setting `SWIFT_STRICT_CONCURRENCY = Complete` pada file build target Xcode. Ini memastikan audit data-race dilakukan secara penuh sebelum migrasi ke Swift 6.
2.  **Explicit `@MainActor` di Layer ViewModel:** Seluruh ViewModel yang bertugas memasok data binding langsung ke SwiftUI View atau UIKit ViewController wajib dianotasi dengan `@MainActor` pada tingkat deklarasi kelas.
3.  **Terapkan Protocol Isolation Patterns:** Ketika mendefinisikan abstractions/interface service (Dependency Injection), tandai protokol dengan inheritance `@Sendable`:
    ```swift
    public protocol PaymentProcessingService: Sendable {
        func executePayment(amount: Decimal) async throws -> TransactionResult
    }
    ```
4.  **Tutup Aliran `AsyncStream`:** Pastikan `continuation.finish()` atau `continuation.yield(with:)` selalu dipanggil di dalam deinit atau siklus terminal lifecycle objek guna menghindari memory leak pada consumer loop.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Mengeliminasi Context Switches via Cooperative Locality
Saat memanggil fungsi asinkron beruntun, runtime berusaha mempertahankan eksekusi pada thread CPU yang sama jika isolasi aktornya konsisten. Hindari melompat antar aktor berulang kali di dalam loop mikro.

```swift
// SUB-OPTIMAL: Memaksa Context Switch bolak-balik sebanyak 10.000 kali
for item in largeArray {
    await databaseActor.insert(item) // Context Switch: Main -> DB Actor -> Main -> DB Actor ...
}

// OPTIMAL: Lakukan batching untuk meminimalisir isolasi context boundary crossing
await databaseActor.insertBatch(largeArray) // 1x Context Switch
```

### 2. Task Reservation Memory Layout
Saat mengumpulkan hasil dari `TaskGroup`, panggil `reserveCapacity(_:)` pada array penampung hasil jika jumlah total pekerjaan telah dipastikan sejak awal, memotong biaya realokasi array amortized di heap.

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Sanitisasi Task Invalidation pada Token Revocation:** Ketika status autentikasi pengguna kedaluwarsa (HTTP 401 Unauthorized), semua task asinkron yang sedang membawa payload data kredensial harus dihentikan seketika melalui propagasi `Task.cancel()`.
2.  **Enkapsulasi Aktor pada Data Sensitif:** Cegah eksfiltrasi data sensitif seperti Private Key atau Plaintext Token dengan melarang properti aktor terekspos via non-isolated getters.

```swift
public actor SecureEnclaveKeyStorage {
    private var privateKeyMaterial: Data

    public init(key: Data) {
        self.privateKeyMaterial = key
    }

    // AMAN: Operasi kriptografi dilakukan internal, raw material tidak pernah menyeberang
    public func signPayload(_ payload: Data) -> Data {
        return CryptoSigner.sign(payload, using: privateKeyMaterial)
    }
}
```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### 1. LLDB Thread & Task State Inspection
Untuk menganalisis task yang sedang aktif atau mengalami deadlock pada session debug:
*   Jalankan perintah LLDB: `thread backtrace all` untuk melihat frame native.
*   Jalankan inspeksi suspensi Swift Concurrency: `task list` atau `task info <Task Address>`.

### 2. Xcode Instruments (Swift Tasks Profiler)
Gunakan template **Swift Concurrency System Instrument** di Instruments:
*   **Active Tasks Graph:** Mengamati lonjakan task creation vs task destruction rate. Mengidentifikasi apakah ada task yang menggantung tanpa henti (*Task Leaks*).
*   **Task Ancestry Hierarchy:** Memetakan relasi hierarki antara parent task dan child task.
*   **Continuation Block Events:** Menemukan fungsi mana yang paling lama berada pada fase penangguhan (high latency I/O).

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   `async`: Menandai fungsi sebagai titik yang dapat ditangguhkan (*suspension candidate*).
*   `await`: Menyerahkan kepemilikan thread eksekusi kembali ke cooperative thread pool sembari menunggu hasil/penyelesaian I/O.
*   `actor`: Reference type yang merealisasikan mutual-exclusion thread-safety secara otomatis untuk data internalnya.
*   `@MainActor`: Global actor unik yang mengikat eksekusi secara deterministik ke Main Thread (eksklusif untuk operasi UI).
*   `Task { }`: Membuat unstructured context yang mewarisi aktor pemanggil dan task-local environment.
*   `Task.detached { }`: Mengalokasikan task tanpa relasi konteks aktor atau prioritas pemanggil.
*   `withTaskGroup`: Membangun konkurensi paralel terstruktur dengan batas masa hidup (lifecycle) yang deterministik.
*   `AsyncStream`: Jembatan penyuplai data dari event listener callback/delegate lama menuju paradigma modern `for-await-in`.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah satu jawaban yang paling tepat serta analisis implikasi teknisnya:

**1. Apa konsekuensi teknis jika kita memanggil `Thread.sleep(5)` di dalam sebuah fungsi `async` pada Swift Concurrency?**
A. Hanya memblokir Task tersebut, thread kooperatif langsung mengambil Task lain.  
B. Memblokir native thread kooperatif yang sedang mengeksekusinya selama 5 detik, berisiko menyebabkan starvation pada seluruh cooperative thread pool.  
C. Runtime Swift secara otomatis mengonversinya menjadi `Task.sleep`.  
D. Menghasilkan compile-time error pada mode Swift 6.  
*Jawaban & Pembahasan Singkat:* **B**. `Thread.sleep` adalah pemanggilan blocking kernel POSIX murni. Ia tidak berkooperasi dengan Swift Runtime, sehingga menahan native worker thread dan memangkas kuota throughput thread pool global.

**2. Apa yang dimaksud dengan fenomena "Actor Reentrancy"?**
A. Sebuah actor dapat dipanggil berulang kali dari thread yang sama tanpa overhead.  
B. Kemampuan method actor untuk berjalan secara rekursif tanpa batas stack.  
C. Di antara titik suspensi (`await`), eksekusi method dalam actor dapat disisipi oleh pemanggilan method lain pada actor yang sama, memungkinkan perubahan state internal.  
D. Actor membatalkan eksekusi sebelumnya jika ada pemanggilan method baru yang masuk ke antrean.  
*Jawaban & Pembahasan Singkat:* **C**. Actor melepaskan kunci isolasinya saat mencapai suspensi `await`, sehingga instruksi lain dapat mengubah state sebelum task semula kembali melanjutkan eksekusi.

**3. Manakah deklarasi tipe referensi yang SAH memenuhi protokol `Sendable` secara eksplisit tanpa menggunakan bypass atribut `@unchecked`?**
A. Class non-final dengan konstanta immutable `let`.  
B. Class `final` dengan semua stored property immutable (`let`) yang juga bertipe `Sendable`.  
C. Struct yang membungkus reference class mutable.  
D. Class `final` dengan private variable (`var`) yang dilindungi NSLock.  
*Jawaban & Pembahasan Singkat:* **B**. Di bawah aturan Swift Concurrency, tipe referensi murni hanya aman jika dideklarasikan `final` dan semua property bernilai konstanta `let` yang berstatus `Sendable`.

**4. Mengapa Structured Concurrency (`async let` / `withTaskGroup`) lebih disukai daripada Unstructured Concurrency (`Task { }`)?**
A. Karena Structured Concurrency mengonsumsi alokasi stack lebih sedikit daripada heap.  
B. Karena Structured Concurrency menjamin propagasi pembatalan dan error secara otomatis ke seluruh tree eksekusi sebelum scope berakhir.  
C. Karena Unstructured Task tidak dapat berjalan di background thread.  
D. Structured Concurrency dapat membypass pengecekan actor boundary.  
*Jawaban & Pembahasan Singkat:* **B**. Structured Concurrency menjamin bahwa parent task tidak dapat keluar dari scope sintaks sebelum semua child task selesai atau dibatalkan, mencegah detached task leakage.

**5. Kapan sebaiknya Anda menggunakan `Task.detached` alih-alih `Task` reguler?**
A. Saat ingin memperbarui properti antarmuka pengguna secara cepat.  
B. Ketika operasi background sama sekali tidak boleh mewarisi actor isolation context maupun prioritas pemanggil (misal: penulisan low-priority audit trail caching ke storage disk).  
C. Kapan pun kita ingin menjalankan dua fungsi paralel di dalam closure.  
D. Saat memanggil fungsi asinkron dari dalam konteks sinkron UIView.  
*Jawaban & Pembahasan Singkat:* **B**. `Task.detached` secara sengaja memutuskan koneksi dari context pemanggil, berguna untuk tugas otonom terisolasi independen yang tidak berhubungan dengan aktor pemanggil.

---

## SEKSI 20 — TANTANGAN MANDIRI & PROYEK PRAKTIKUM

### Instruksi Proyek Praktikum: Resilient Image Pre-Caching Engine
Bangun sebuah modul caching gambar terdistribusi berstandar produksi yang memenuhi kriteria berikut:
1.  **Arsitektur Actor Isolated:** Buat actor `DiskMemoryCacheRegistry` yang melacak metadata file dan menjamin integritas pembacaan/penulisan file gambar lokal tanpa data race.
2.  