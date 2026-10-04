# SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** 02-Programming-Languages
* **Track:** Swift & SwiftUI Native Development
* **Bab 08:** Data Architecture, Persistence, and Synchronization
* **Modul 01:** Persistensi & Offline-First Data Pipeline
* **Tingkat Kesulitan:** Advanced / Enterprise Grade
* **Prasyarat Pengetahuan:** 
  * Pemahaman mendalam tentang Swift Concurrency (`async/await`, `Task`, `Actor`, `Sendable`).
  * Dasar-dasar SwiftUI State Management (`@State`, `@Observable`, `@Environment`).
  * Familiaritas dengan REST API dan protokol jaringan dasar (HTTP status, JSON decoding).
* **Target Output Pengembang:** Mampu merancang, membangun, dan mengoptimalkan sistem persistensi data lokal terisolasi aktor menggunakan SwiftData/Core Data, yang terhubung dengan pipeline sinkronisasi dua arah (bidirectional synchronization), mitigasi konflik deterministik, optimasi antrean mutasi (mutation queue), serta transisi UI optimistik tanpa *blocking* di *Main Thread*.

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Mengonstruksi Local Persistence Engine Berbasis SwiftData & Core Data:** Menetapkan konfigurasi `ModelContainer`, `ModelConfiguration`, isolasi *in-memory* vs *disk-backed storage*, serta skema migrasi bertahap.
2. **Mengisolasi Konkurensi Data Layer Menggunakan `@ModelActor`:** Mengimplementasikan pola akses thread-safe pada background worker thread guna mencegah *data race* dan pelanggaran *Swift 6 strict concurrency checks*.
3. **Membangun Arsitektur Offline-First & Optimistic UI Pipeline:** Mengimplementasikan pola *Single Source of Truth* (SSOT) lokal di mana UI selalu membaca dari persistensi lokal, sementara mutasi lokal langsung diterapkan dan dieksekusi asinkron ke remote server.
4. **Merancang Mutation Queue & Retry Engine Berbasis `NWPathMonitor`:** Mengelola antrean operasi (Create, Update, Delete) yang persisten di disk, tahan terhadap terminasi aplikasi (*app termination*), dan memiliki kemampuan *exponential backoff retry*.
5. **Menerapkan Algoritma Resolusi Konflik (Conflict Resolution Strategy):** Mengembangkan sistem rekonsiliasi data menggunakan strategi *Last-Write-Wins* (LWW) berbasis timestamp atomik, *Field-Level Merging*, serta *Three-Way Merge*.
6. **Mengintegrasikan Background Synchronization:** Memanfaatkan `BGTaskScheduler` (`BGAppRefreshTask`) untuk menjaga konsistensi state ketika aplikasi dalam kondisi suspended atau terminated.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam paradigma rekayasa aplikasi enterprise modern, jaringan internet bukanlah dependensi deterministik; **jaringan adalah efek samping (side-effect) yang asinkron, fluktuatif, dan tidak dapat diandalkan**. Pola pikir tradisional yang menempatkan Network Request di depan Persistence Layer (Request $\to$ Response $\to$ Save to DB $\to$ Show UI) adalah anti-pattern yang menyebabkan:
1. UI terblokir atau memunculkan blocking spinner (*loading fatigue*).
2. Data hilang saat aplikasi ditutup mendadak di area tanpa sinyal (*data loss*).
3. Inkonsistensi status (*split-brain*) antara antarmuka pengguna dan database lokal.

```
MENTAL MODEL TRADISIONAL (RAPUH):
[UI Action] ---> [Network Call] ---> [Success?] 
                                       |-- Yes --> [Save DB] ---> [Render UI]
                                       +-- No  ---> [Show Error Alert (Drop State)]

MENTAL MODEL OFFLINE-FIRST (ROBUST / ENTERPRISE):
[UI Action] ---> [Write to Local DB (SSOT)] ---> [Instant Optimistic UI Update]
                           |
                           +---> [Enqueue Mutation Task to Disk]
                                          |
                                          v
                           [Sync Engine (Actor-Driven)]
                                          |
                        +-----------------+-----------------+
                        | (When Online via NWPathMonitor)  |
                        v                                   v
             [Dispatch to Remote API]            [Persist Retry / Exponential Backoff]
                        |
            [Conflict Reconciliation]
                        |
            [Update Local DB State] ---> [Auto-reflected to UI via Observation]
```

### Prinsip Utama Offline-First:
* **The Local Store is the Single Source of Truth (SSOT):** UI **tidak pernah** merender data langsung dari network response payload. UI hanya mengamati (observe) database lokal. Jaringan hanyalah pipa transportasi untuk merekonsiliasi state lokal dengan state global di server.
* **Optimistic Local Execution:** Setiap mutasi pengguna dicatat ke database lokal seketika dengan status transisi (misal: `.pendingSync`). Pengguna merasakan latensi 0ms.
* **Deterministic Idempotency:** Setiap mutasi memiliki Unique Operation ID (UUID/ULID) idempotensi agar jika terjadi transmisi ulang akibat timeout TCP, server tidak mengeksekusi duplikasi entri (mencegah *double charging*, *double creation*).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur pipeline data offline-first dengan isolasi konkuren penuh, antrean mutasi lokal, dan resolusi konflik:

```
+---------------------------------------------------------------------------------------+
|                                    SWIFTUI LAYER                                      |
|  Views observe @Query / @Observable Local Model. Zero direct network invocation.      |
+-------------------------------------------+-------------------------------------------+
                                            |
                         User Writes / Edit | Reads (@Query)
                                            v
+---------------------------------------------------------------------------------------+
|                                LOCAL STORAGE (SSOT)                                   |
|  SwiftData / Core Data SQLite Persistent Store (`ModelContainer` / `NSPersistentContainer`)|
|  - Entity Records: [EntityA (status: synced), EntityB (status: pendingSync)]          |
|  - Sync Queue Table: [MutationQueue (opId, entity, payload, retryCount, timestamp)]   |
+-------------------------------------------+-------------------------------------------+
                                            |
                      Transaction Committed | Event Trigger
                                            v
+---------------------------------------------------------------------------------------+
|                            BACKGROUND SYNC ENGINE (@ModelActor)                       |
|  Actor-isolated context. Decoupled from MainActor. Safe from UI stutters.            |
|                                                                                       |
|  +-----------------------+     +------------------------+     +--------------------+  |
|  |   Queue Processor     | --> |   Network Monitor      | --> |  Conflict Resolver |  |
|  |  (Pulls pending tasks)|     |  (NWPathMonitor Path)  |     |  (LWW / Merge)     |  |
|  +-----------------------+     +------------------------+     +--------------------+  |
+-------------------------------------------+-------------------------------------------+
                                            |
                             HTTPS REST / gRPC Payloads
                                            v
+---------------------------------------------------------------------------------------+
|                                    REMOTE SERVER                                      |
|  API Gateway -> Distributed Database (PostgreSQL / CockroachDB / Redis Event Bus)     |
+---------------------------------------------------------------------------------------+
```

### Siklus Hidup Sinkronisasi & Alur Penanganan Konflik:

```
[UI Mutation]
      |
      v
[Save Local: State=Pending] ---> [Save to PendingMutationQueue]
                                               |
                                               v
                                    [Check Network via Actor]
                                               |
                     +-------------------------+-------------------------+
                     | (Path is Unsatisfied)                             | (Path is Satisfied)
                     v                                                   v
         [Suspend Sync Engine]                               [Execute HTTP Request]
         [Register BGAppRefreshTask]                                     |
                                                  +----------------------+----------------------+
                                                  | Status == 200/201 OK                        | Status == 409 Conflict
                                                  v                                             v
                                      [Dequeue Mutation Record]                     [Fetch Remote Head Revision]
                                      [Set Entity Status=Synced]                                |
                                                  |                                             v
                                                  |                                [Compute Conflict Algorithm]
                                                  |                                (Field-Level Merge / Server-Wins)
                                                  |                                             |
                                                  +----------------------<----------------------+
                                                  |
                                                  v
                                      [Write Reconciliation to DB]
                                                  |
                                      [SwiftData Context Save]
                                                  |
                                                  v
                                      [UI Observes Updated Values]
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. ModelContainer & SQLite Primitives
Di bawah abstraksi SwiftData atau Core Data, mesin penyimpanan utamanya adalah SQLite yang berjalan dalam mode **WAL (Write-Ahead Logging)**. 
* Pada mode WAL, pembacaan (*reading*) dan penulisan (*writing*) dapat terjadi secara simultan tanpa saling memblokir: proses pembacaan membaca snapshot basis data pada titik waktu tertentu (*snapshot isolation*), sementara proses penulisan diarahkan ke berkas terpisah bertipe `-wal`.
* Checkpointing terjadi di latar belakang untuk mentransfer frame dari berkas WAL kembali ke berkas basis data utama `.sqlite`.

### 2. Concurrency Isolation dengan `@ModelActor`
Di SwiftData, setiap modifikasi data harus dilakukan dalam konteks `ModelContext`. Objek `ModelContext` **tidak thread-safe**. Memanipulasinya di sembarang background thread atau melintasi batas await (`suspension points`) tanpa isolasi eksplisit akan memicu *data corruption* atau ekskusi fatal `EXC_BAD_ACCESS`.

Makro `@ModelActor` memecahkan masalah ini dengan:
1. Mengonversi tipe data menjadi sebuah `actor` Swift murni.
2. Membentuk `modelExecutor` privat berbasis `DefaultSerialModelExecutor`.
3. Menginstansiasi `ModelContext` independen yang terikat langsung ke *executor* aktor tersebut.
4. Memastikan semua operasi basis data yang terjadi di dalam aktor dijalankan secara serial pada serial dispatch queue milik aktor tersebut.

```swift
// Ekspansi Sintaks Konseptual dari Makro @ModelActor
public actor DataSyncHandler: ModelActor {
    public nonisolated let modelContainer: ModelContainer
    public nonisolated let modelExecutor: any ModelExecutor

    public init(modelContainer: ModelContainer) {
        let modelContext = ModelContext(modelContainer)
        self.modelContainer = modelContainer
        self.modelExecutor = DefaultSerialModelExecutor(modelContext: modelContext)
    }
    
    // Akses context aman diisolasi secara internal ke actor
    private var context: ModelContext {
        modelExecutor.modelContext
    }
}
```

### 3. Change Tracking & Row Metadata
Untuk mewujudkan offline synchronization, tabel data lokal memerlukan kolom metadata esensial:
* `id: UUID`: Identifier universal entitas.
* `updatedAt: Date`: Stempel waktu modifikasi lokal terakhir.
* `serverUpdatedAt: Date?`: Stempel waktu modifikasi server terakhir yang diketahui klien.
* `syncStateRaw: String`: State siklus hidup sinkronisasi: `.synced`, `.createdOffline`, `.updatedOffline`, `.deletedOffline`.
* `version: Int`: Versi monotonic counter untuk *optimistic locking*.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Vector Clocks vs Last-Write-Wins (LWW)
Masalah fundamental dari arsitektur offline-first terdistribusi adalah: **Waktu di jam perangkat klien (Client Wall-Clock) tidak pernah dapat dipercaya**. Adanya *clock drift*, manipulasi waktu oleh pengguna, atau variasi latensi jaringan membuat algoritma pembanding berbasis waktu lokal rentan terhadap kehilangan data (*silent data overwrite*).

#### Last-Write-Wins (LWW)
Pendekatan paling umum di mana entitas dengan `updatedAt` terbaru menimpa nilai yang lama.
* *Kelemahan:* Bila Jam Device A lebih cepat 5 menit dari Device B, mutasi Device A akan selalu menimpa mutasi Device B terlepas dari urutan kejadian kausalitas yang sesungguhnya.
* *Mitigasi:* Server wajib menyematkan *Monotonic Server-Generated Timestamp* saat transaksi diterima, atau menggunakan protokol rekonsiliasi berbasis *Version Vector*.

#### Field-Level Merging (3-Way Merge)
Alih-alih menimpa seluruh baris/dokumen (*Record-Level Replacement*), rekonsiliasi dilakukan pada level individual atribut.

$$State_{Final} = Merge(State_{Base}, State_{Local}, State_{Remote})$$

Jika State Base memiliki atribut $\{A: 1, B: 2\}$, lalu klien offline mengubah $\{A: 5, B: 2\}$ dan remote mengubah $\{A: 1, B: 9\}$, sistem dapat secara otomatis mendamaikan menjadi $\{A: 5, B: 9\}$ tanpa konflik karena domain mutasinya saling lepas (disjoint). Konflik sejati hanya dideklarasikan jika $\Delta Local.key \cap \Delta Remote.key \neq \emptyset$ dan nilainya berbeda.

### 2. Idempotency Keys pada Arsitektur Jaringan
Dalam jaringan TCP/IP nir-kabel, *packet drop* kerap terjadi pada fase *Response*, bukan *Request*. Artinya, server sukses memproses mutasi, tetapi *acknowledgement (ACK)* tidak pernah sampai ke perangkat klien. 
Klien yang mengulang mutasi tersebut dapat membuat baris ganda di database server jika sistem tidak dirancang secara idempoten.

```
Client                             Server
  |                                  |
  |--- POST /tasks (Task A, Key:X) ->| (Server saves Task A to DB)
  |                                  | (Server generates Response 201)
  |          x (Drop Packet) --------|
  |                                  |
(Client Timeout / Network Resumed)   |
  |                                  |
  |--- POST /tasks (Task A, Key:X) ->| (Server detects Key:X already processed!)
  |                                  | (Server returns cached 201 without duplication)
  |<-- 201 Created (Key:X) ----------|
```

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah pondasi data layer: Skema model SwiftData yang memuat metadata sinkronisasi, skema antrean mutasi (`MutationRecord`), dan inisialisasi `ModelContainer` terisolasi.

### Langkah 1: Model Entitas Bisnis & Antrean Mutasi

```swift
import Foundation
import SwiftData

public enum SyncState: String, Codable, CaseIterable {
    case synced
    case pendingCreation
    case pendingUpdate
    case pendingDeletion
}

public enum MutationOperation: String, Codable {
    case create
    case update
    case delete
}

@Model
public final class ProjectTaskItem {
    @Attribute(.unique) public var id: UUID
    public var title: String
    public var notes: String
    public var isCompleted: Bool
    public var updatedAt: Date
    public var serverVersion: Int
    public var syncStateRaw: String
    
    public var syncState: SyncState {
        get { SyncState(rawValue: syncStateRaw) ?? .pendingCreation }
        set { syncStateRaw = newValue.rawValue }
    }
    
    public init(
        id: UUID = UUID(),
        title: String,
        notes: String = "",
        isCompleted: Bool = false,
        updatedAt: Date = Date(),
        serverVersion: Int = 1,
        syncState: SyncState = .pendingCreation
    ) {
        self.id = id
        self.title = title
        self.notes = notes
        self.isCompleted = isCompleted
        self.updatedAt = updatedAt
        self.serverVersion = serverVersion
        self.syncStateRaw = syncState.rawValue
    }
}

@Model
public final class PersistentMutationRecord {
    @Attribute(.unique) public var mutationId: UUID
    public var entityId: UUID
    public var entityName: String
    public var operationRaw: String
    public var payloadData: Data
    public var createdAt: Date
    public var retryCount: Int
    public var lastError: String?
    
    public var operation: MutationOperation {
        get { MutationOperation(rawValue: operationRaw) ?? .create }
        set { operationRaw = newValue.rawValue }
    }
    
    public init(
        mutationId: UUID = UUID(),
        entityId: UUID,
        entityName: String,
        operation: MutationOperation,
        payloadData: Data,
        createdAt: Date = Date(),
        retryCount: Int = 0,
        lastError: String? = nil
    ) {
        self.mutationId = mutationId
        self.entityId = entityId
        self.entityName = entityName
        self.operationRaw = operation.rawValue
        self.payloadData = payloadData
        self.createdAt = createdAt
        self.retryCount = retryCount
        self.lastError = lastError
    }
}
```

### Langkah 2: Setup Dynamic App ModelContainer Factory

```swift
import Foundation
import SwiftData

public final class AppPersistenceContainer {
    public static let shared = AppPersistenceContainer()
    
    public let container: ModelContainer
    
    private init() {
        let schema = Schema([
            ProjectTaskItem.self,
            PersistentMutationRecord.self
        ])
        
        let configuration = ModelConfiguration(
            schema: schema,
            isStoredInMemoryOnly: false,
            allowsSave: true
        )
        
        do {
            self.container = try ModelContainer(for: schema, configurations: [configuration])
        } catch {
            fatalError("CRITICAL: Gagal menginisialisasi SwiftData ModelContainer: \(error.localizedDescription)")
        }
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Pada implementasi Seksi 07:

1. `@Model public final class ProjectTaskItem`:
   * `@Model` adalah Swift Macro yang mengimplementasikan protokol `PersistentModel` di balik layar. Macro ini mengubah properti yang dideklarasikan menjadi stored properties yang diobservasi oleh dynamic schema backing data store SwiftData.
   * `@Attribute(.unique) public var id: UUID`: Mengharuskan kolom basis data SQLite memiliki *UNIQUE constraint*. Hal ini esensial untuk mencegah duplikasi entri ketika sinkronisasi batch masuk dari server.
2. `public var syncStateRaw: String`:
   * Enum SwiftData dengan parameter primitif seringkali paling aman disimpan dalam bentuk `String` primitif (Raw Representable) untuk meminimalkan *schema breaking changes* di SQLite bila ada penambahan kasus baru. Properti terkomputasi `syncState` menyederhanakan akses level bahasa dengan tipe aman.
3. `@Model public final class PersistentMutationRecord`:
   * Ini adalah tabel sistem yang bertindak sebagai *write-ahead intent log*. Setiap kali operasi offline terjadi, sebuah rekaman dibuat di tabel ini.
   * `payloadData: Data`: Representasi JSON-encoded dari entity delta. Payload disimpan persisten agar bila aplikasi di-kill paksa oleh iOS saat berada di background, data perubahan tidak menguap dari volatile RAM.
4. `let configuration = ModelConfiguration(...)`:
   * `isStoredInMemoryOnly: false`: Memastikan engine menyimpan data secara persisten ke direktori *Application Support* di sandbox sistem berkas iOS.
   * `allowsSave: true`: Membuka kunci kapabilitas flush memori ke disk.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Bisnis
Sebuah aplikasi inspeksi infrastruktur lapangan (*AeroInspect Enterprise*). Para insinyur memeriksa turbin angin di remote off-shore tanpa koneksi seluler selama 8 jam. 

### Tantangan Arsitektur:
1. **Zero Latency Operation:** Pengguna harus bisa memperbarui checklist, mengubah metadata, mengambil foto, dan memvalidasi tugas tanpa jeda spinner.
2. **Volatile App Lifecycle:** iOS dapat mematikan aplikasi sewaktu-waktu saat memori tinggi (*jetsam termination*).
3. **Flaky Connection Recovery:** Saat helikopter penjemput tiba, sinyal 4G/5G menyala-mati secara berkala (*intermittent network flapping*).
4. **Data Race Prevention:** Background synchronization tidak boleh mengunci Main Thread yang sedang menjalankan antarmuka animasi SwiftUI pada 120 FPS (ProMotion).

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah implementasi sistem produksi lengkap yang mencakup Network Path Monitoring, Background `@ModelActor` Processing, Antrean Mutasi, dan Integrasi SwiftUI.

### 1. DTO & Network Engine Mock

```swift
import Foundation

public struct TaskSyncPayloadDTO: Codable, Sendable {
    public let id: UUID
    public let title: String
    public let notes: String
    public let isCompleted: Bool
    public let clientUpdatedAt: Date
    public let serverVersion: Int
}

public struct RemoteTaskResponseDTO: Codable, Sendable {
    public let id: UUID
    public let title: String
    public let notes: String
    public let isCompleted: Bool
    public let serverUpdatedAt: Date
    public let serverVersion: Int
}

public protocol NetworkClientProtocol: Sendable {
    func pushMutation(payload: TaskSyncPayloadDTO, operation: MutationOperation) async throws -> RemoteTaskResponseDTO
}

public final class ProductionNetworkClient: NetworkClientProtocol {
    public init() {}
    
    public func pushMutation(payload: TaskSyncPayloadDTO, operation: MutationOperation) async throws -> RemoteTaskResponseDTO {
        // Simulasi latensi transmisi jaringan
        try await Task.sleep(nanoseconds: 800_000_000)
        
        // Simulasi validasi respons remote
        return RemoteTaskResponseDTO(
            id: payload.id,
            title: payload.title,
            notes: payload.notes,
            isCompleted: payload.isCompleted,
            serverUpdatedAt: Date(),
            serverVersion: payload.serverVersion + 1
        )
    }
}
```

### 2. Network Reachability Observer

```swift
import Foundation
import Network

@Observable
public final class NetworkMonitor: Sendable {
    public static let shared = NetworkMonitor()
    
    private let monitor = NWPathMonitor()
    private let queue = DispatchQueue(label: "com.enterprise.networkmonitor")
    
    public private(set) var isConnected: Bool = false
    public private(set) var isExpensive: Bool = false
    
    private init() {
        monitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor in
                self?.isConnected = (path.status == .satisfied)
                self?.isExpensive = path.isExpensive
            }
        }
        monitor.start(queue: queue)
    }
}
```

### 3. Background Sync Engine dengan Isolasi `@ModelActor`

```swift
import Foundation
import SwiftData

@ModelActor
public actor BackgroundDataSynchronizer {
    private let networkClient: NetworkClientProtocol
    
    public init(modelContainer: ModelContainer, networkClient: NetworkClientProtocol) {
        let context = ModelContext(modelContainer)
        context.autosaveEnabled = false // Manual transaction save control
        self.modelContainer = modelContainer
        self.modelExecutor = DefaultSerialModelExecutor(modelContext: context)
        self.networkClient = networkClient
    }
    
    public func enqueueTaskCreation(id: UUID, title: String, notes: String) throws {
        let task = ProjectTaskItem(
            id: id,
            title: title,
            notes: notes,
            isCompleted: false,
            updatedAt: Date(),
            serverVersion: 0,
            syncState: .pendingCreation
        )
        modelContext.insert(task)
        
        let dto = TaskSyncPayloadDTO(
            id: id,
            title: title,
            notes: notes,
            isCompleted: false,
            clientUpdatedAt: task.updatedAt,
            serverVersion: 0
        )
        
        let data = try JSONEncoder().encode(dto)
        let mutation = PersistentMutationRecord(
            entityId: id,
            entityName: "ProjectTaskItem",
            operation: .create,
            payloadData: data
        )
        
        modelContext.insert(mutation)
        try modelContext.save()
    }
    
    public func processPendingMutations() async throws -> Int {
        var fetchDescriptor = FetchDescriptor<PersistentMutationRecord>(
            sortBy: [SortDescriptor(\.createdAt, order: .forward)]
        )
        fetchDescriptor.fetchLimit = 50
        
        let pendingRecords = try modelContext.fetch(fetchDescriptor)
        guard !pendingRecords.isEmpty else { return 0 }
        
        var processedCount = 0
        
        for record in pendingRecords {
            do {
                try await dispatchRecord(record)
                modelContext.delete(record)
                try modelContext.save()
                processedCount += 1
            } catch {
                record.retryCount += 1
                record.lastError = error.localizedDescription
                try modelContext.save()
                // Hentikan batch jika koneksi jaringan putus saat transmisi berlangsung
                break
            }
        }
        
        return processedCount
    }
    
    private func dispatchRecord(_ record: PersistentMutationRecord) async throws {
        let decoder = JSONDecoder()
        let payload = try decoder.decode(TaskSyncPayloadDTO.self, from: record.payloadData)
        
        let remoteResponse = try await networkClient.pushMutation(
            payload: payload,
            operation: record.operation
        )
        
        // Rekonsiliasi State Lokal dengan Respons Server
        let targetId = remoteResponse.id
        var taskDescriptor = FetchDescriptor<ProjectTaskItem>(
            predicate: #Predicate { $0.id == targetId }
        )
        taskDescriptor.fetchLimit = 1
        
        if let matchingTask = try modelContext.fetch(taskDescriptor).first {
            // Evaluasi Resolusi Konflik: Three-Way / Server-Version Monotonicity
            if remoteResponse.serverVersion >= matchingTask.serverVersion {
                matchingTask.serverVersion = remoteResponse.serverVersion
                matchingTask.syncState = .synced
                matchingTask.updatedAt = remoteResponse.serverUpdatedAt
            }
        }
    }
}
```

### 4. Background Task Scheduler Coordinator

```swift
import Foundation
import BackgroundTasks
import SwiftData

public final class AppBackgroundSyncCoordinator: Sendable {
    public static let shared = AppBackgroundSyncCoordinator()
    public static let backgroundTaskId = "com.enterprise.tasksync.refresh"
    
    public func registerBackgroundSync(container: ModelContainer) {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: Self.backgroundTaskId, using: nil) { task in
            guard let refreshTask = task as? BGAppRefreshTask else { return }
            self.handleBackgroundSync(task: refreshTask, container: container)
        }
    }
    
    public func scheduleBackgroundSync() {
        let request = BGAppRefreshTaskRequest(identifier: Self.backgroundTaskId)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60) // 15 menit ke depan
        
        do {
            try BGTaskScheduler.shared.submit(request)
        } catch {
            print("Background Task scheduling failed: \(error.localizedDescription)")
        }
    }
    
    private func handleBackgroundSync(task: BGAppRefreshTask, container: ModelContainer) {
        scheduleBackgroundSync() // Jadwalkan loop berikutnya
        
        let client = ProductionNetworkClient()
        let synchronizer = BackgroundDataSynchronizer(modelContainer: container, networkClient: client)
        
        let syncOperationTask = Task {
            do {
                _ = try await synchronizer.processPendingMutations()
                task.setTaskCompleted(success: true)
            } catch {
                task.setTaskCompleted(success: false)
            }
        }
        
        task.expirationHandler = {
            syncOperationTask.cancel()
        }
    }
}
```

### 5. SwiftUI Implementation (Main Thread Protected)

```swift
import SwiftUI
import SwiftData

public struct TaskListView: View {
    @Environment(\.modelContext) private var mainModelContext
    
    // UI selalu mengamati local DB, menghasilkan 0ms optimistic visual update
    @Query(sort: \ProjectTaskItem.updatedAt, order: .reverse)
    private var tasks: [ProjectTaskItem]
    
    @State private var networkMonitor = NetworkMonitor.shared
    @State private var synchronizer: BackgroundDataSynchronizer?
    @State private var isShowingCreateSheet = false
    @State private var newTitle = ""
    @State private var newNotes = ""
    
    public init() {}
    
    public var body: some View {
        NavigationStack {
            List {
                Section(header: NetworkStatusBar(isConnected: networkMonitor.isConnected)) {
                    ForEach(tasks) { item in
                        TaskRowView(item: item)
                    }
                    .onDelete(perform: deleteItems)
                }
            }
            .navigationTitle("AeroInspect Tasks")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        isShowingCreateSheet = true
                    } label: {
                        Image(systemName: "plus.circle.fill")
                            .font(.title3)
                    }
                }
                ToolbarItem(placement: .topBarLeading) {
                    Button("Sync Now") {
                        triggerManualSync()
                    }
                    .disabled(!networkMonitor.isConnected)
                }
            }
            .sheet(isPresented: $isShowingCreateSheet) {
                NavigationStack {
                    Form {
                        TextField("Judul Tugas", text: $newTitle)
                        TextField("Catatan", text: $newNotes)
                    }
                    .navigationTitle("Tugas Baru")
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Batal") { isShowingCreateSheet = false }
                        }
                        ToolbarItem(placement: .confirmationAction) {
                            Button("Simpan") {
                                saveTaskOptimistically()
                                isShowingCreateSheet = false
                            }
                            .disabled(newTitle.trimmingCharacters(in: .whitespaces).isEmpty)
                        }
                    }
                }
            }
            .task {
                let networkClient = ProductionNetworkClient()
                synchronizer = BackgroundDataSynchronizer(
                    modelContainer: mainModelContext.container,
                    networkClient: networkClient
                )
                if networkMonitor.isConnected {
                    triggerManualSync()
                }
            }
            .onChange(of: networkMonitor.isConnected) { _, isNowConnected in
                if isNowConnected {
                    triggerManualSync()
                }
            }
        }
    }
    
    private func saveTaskOptimistically() {
        let taskTitle = newTitle
        let taskNotes = newNotes
        newTitle = ""
        newNotes = ""
        
        Task {
            guard let synchronizer else { return }
            do {
                let newId = UUID()
                try await synchronizer.enqueueTaskCreation(
                    id: newId,
                    title: taskTitle,
                    notes: taskNotes
                )
                if networkMonitor.isConnected {
                    _ = try await synchronizer.processPendingMutations()
                }
            } catch {
                print("Error enqueueing task: \(error.localizedDescription)")
            }
        }
    }
    
    private func deleteItems(at offsets: IndexSet) {
        for index in offsets {
            let task = tasks[index]
            mainModelContext.delete(task)
        }
        try? mainModelContext.save()
    }
    
    private func triggerManualSync() {
        Task {
            guard let synchronizer else { return }
            do {
                _ = try await synchronizer.processPendingMutations()
            } catch {
                print("Sync failed: \(error.localizedDescription)")
            }
        }
    }
}

public struct NetworkStatusBar: View {
    public let isConnected: Bool
    
    public var body: some View {
        HStack {
            Circle()
                .fill(isConnected ? Color.green : Color.red)
                .frame(width: 8, height: 8)
            Text(isConnected ? "ONLINE — PIPELINE TERHUBUNG" : "OFFLINE — PERUBAHAN TERSIMPAN LOKAL")
                .font(.caption2)
                .fontWeight(.bold)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 4)
    }
}

public struct TaskRowView: View {
    let item: ProjectTaskItem
    
    public var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(item.title)
                    .font(.headline)
                if !item.notes.isEmpty {
                    Text(item.notes)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }
            Spacer()
            SyncIndicatorBadge(state: item.syncState)
        }
    }
}

public struct SyncIndicatorBadge: View {
    let state: SyncState
    
    public var body: some View {
        switch state {
        case .synced:
            Image(systemName: "checkmark.icloud.fill")
                .foregroundColor(.blue)
        case .pendingCreation, .pendingUpdate:
            Image(systemName: "arrow.triangle.2.circlepath.icloud.fill")
                .foregroundColor(.orange)
        case .pendingDeletion:
            Image(systemName: "trash.circle.fill")
                .foregroundColor(.red)
        }
    }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Parameter Arsitektur | Direct Online-Only Pattern | Optimistic Offline-First Pipeline |
| :--- | :--- | :--- |
| **Latensi Antarmuka Pengguna** | Tinggi (~200ms - 2000ms tergantung jaringan) | Seketika (*Instant* ~0ms via lokal disk SQLite) |
| **Kompleksitas Kode** | Sangat Rendah (Cukup `URLSession` + JSON Mapping) | Tinggi (Perlu Queue, Actor Model, Conflict Engine) |
| **Penyimpanan Lokal (Footprint)** | Minimal (Hanya cache sementara) | Signifikan (Perlu skema lokal, WAL file, antrean) |
| **Ketergantungan Server** | Mutlak (Aplikasi tidak bekerja tanpa koneksi) | Minimum (Operasi bisnis tetap berjalan normal) |
| **Konsistensi Data (ACID)** | Dikelola penuh oleh Database Server | *Eventual Consistency* (Memerlukan rekonsiliasi data) |
| **Dampak Baterai (Energy Impact)** | Rendah (Hanya memproses saat interaksi aktif) | Moderat hingga Tinggi (Memerlukan Background Task) |

---

# SEKSI 12 — EDGE CASES & PITFALLS

1. **Jetsam Termination Saat Penulisan Antrean:**
   * *Masalah:* Jika data mutasi dipertahankan di *in-memory array* sebelum disimpan ke basis data, terminasi sistem operasi iOS akibat tekanan memori (*jetsam*) akan memusnahkan antrean secara permanen.
   * *Solusi:* Mutasi **wajib** disimpan secara atomik ke tabel SQLite (`PersistentMutationRecord`) dalam transaksi yang sama dengan modifikasi entitas lokal sebelum network task dieksekusi.
2. **Network Flapping (Koneksi Hidup-Mati dalam Interval Milidetik):**
   * *Masalah:* Panggilan API dilakukan saat `NWPathMonitor` mendeteksi status `.satisfied`, namun sinyal terputus tepat di tengah transmisi paket TCP.
   * *Solusi:* Implementasikan batas waktu koneksi pendek (`URLSessionConfiguration.timeoutIntervalForRequest = 10`), tangani error `URLError.timedOut`, dan terapkan algoritma *Exponential Backoff with Jitter*:
     
     $$T_{wait} = \min(T_{max}, T_{base} \times 2^{retryCount}) + \text{UniformRandom}(0, \text{Jitter})$$

3. **Duplikasi Identitas (Split Identity Crisis):**
   * *Masalah:* Entitas dibuat secara lokal dengan `UUID_A`, tetapi server merespons dengan ID internal serial `BIGINT_10023`.
   * *Solusi:* Gunakan format UUIDv4 atau UUIDv7 secara seragam dari sisi klien dan server sebagai Primary Key resmi basis data distributed. Jangan gunakan ID *auto-increment* server sebagai satu-satunya *identifier*.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Membagikan Instans `ModelContext` Lintas Task / Thread
* *Kesalahan:* Mengakses `@Environment(\.modelContext)` di dalam Task latar belakang atau closure asinkron:
  ```swift
  // KESALAHAN FATAL: Membocorkan context ke thread lain
  Task.detached {
      let task = ProjectTaskItem(title: "Crash")
      mainContext.insert(task) // CRASH: EXC_BAD_ACCESS atau inkonsistensi memori
  }
  ```
* *Solusi:* Gunakan aktor terisolasi dengan `@ModelActor` atau bentuk instance `ModelContext` baru secara eksplisit di background thread menggunakan `ModelContainer`.

### 2. UI Terikat Langsung dengan Network State
* *Kesalahan:* Mengubah array lokal di View menggunakan respons JSON dari server secara langsung tanpa menyimpannya ke database lokal.
* *Solusi:* Terapkan pola reaktif satu arah (*Unidirectional Data Flow*): `View Action` $\to$ `Mutate Local DB` $\to$ `SwiftData Engine` $\to$ `@Query auto-updates View`.

### 3. Mengabaikan Expiration Handler pada Background Task
* *Kesalahan:* Tidak menyematkan `task.expirationHandler` pada `BGAppRefreshTask`. 
* *Solusi:* Sistem operasi iOS akan mematikan paksa (*hard-kill*) aplikasi jika background task melampaui alokasi waktu eksekusi tanpa menyelesaikan atau membatalkan operasi aktif. Selalu sediakan pembatalan `Task` di blok handler tersebut.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Set `autosaveEnabled = false` pada Worker Context:** Saat memproses mutasi masif di background synchronizer, matikan *autosave*. Lakukan *batch save* manual setiap $N$ operasi (misalnya per 50 item) untuk meredam frekuensi flush berkas WAL ke disk yang memicu *I/O throttling*.
2. **Pisahkan Skema Bersih (Domain Layer) dan DTO (Transport Layer):** Jangan pernah memakai `@Model` SwiftData sebagai model encoding/decoding langsung dari JSON API endpoint. API eksternal dapat berubah sewaktu-waktu; mapping decoupling via DTO melindungi stabilitas skema SQLite lokal Anda.
3. **Pemberian Nama Idempoten:** Gunakan nama identifier yang eksplisit untuk setiap operasi yang mengantre, seperti kombinasi `mutationId`, `timestamp`, dan `userId`.
4. **Isolasi Testing Storage:** Dalam pengujian otomatis (*Unit Testing*), selalu setel konfigurasi `isStoredInMemoryOnly: true` di `ModelConfiguration` agar test case terisolasi dan tidak mencemari disk fisik simulator.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Prefetching & Fetch Limit
Gunakan `fetchLimit` dan `fetchBatchSize` secara ketat pada antrean mutasi untuk menghindari lonjakan alokasi memori (*memory spike*) jika antrean menumpuk ribuan rekaman:

```swift
var descriptor = FetchDescriptor<PersistentMutationRecord>()
descriptor.fetchLimit = 50
descriptor.propertiesToFetch = [\.mutationId, \.operationRaw, \.createdAt]
```

### 2. Reduksi Payload Serialization
Simpan payload mutasi dalam bentuk binary encoded representation (`Data`) yang sudah dipadatkan. Hindari menyimpan objek besar seperti berkas citra beresolusi tinggi langsung di dalam tabel SQLite. 
* Aturan emas: Jika objek $> 100\text{ KB}$, simpan objek ke direktori sandbox berkas lokal (`FileManager`), dan simpan *string path* berkas tersebut di atribut entitas SwiftData menggunakan decorator `@Attribute(.externalStorage)`.

---

# SEKSI 16 — KEAMANAN & HARDENING

1. **Enkripsi Database At-Rest dengan Data Protection Class:**
   Konfigurasikan SQLite backing store agar terenkripsi otomatis di level file system perangkat menggunakan API proteksi berkas bawaan iOS:
   ```swift
   let url = NSPersistentContainer.defaultDirectoryURL().appendingPathComponent("secure.store")
   try? FileManager.default.setAttributes(
       [.protectionKey: FileProtectionType.completeUnlessOpen],
       ofItemAtPath: url.path
   )
   ```
2. **Sanitasi Data Sensitif di Antrean Mutasi:**
   Jika antrean mutasi menyimpan payload yang memuat token otentikasi, password, atau identitas privat (PII), payload tersebut **wajib** dienkripsi menggunakan symmetric key dari Apple Keychain via *CryptoKit* (`ChaChaPoly` atau `AES.GCM`) sebelum disimpan ke `payloadData`.
3. **Penyegaran Token Otentikasi Terpusat:**
   Pastikan synchronization actor menghentikan eksekusi antrean ketika menerima status kode `HTTP 401 Unauthorized`, memicu proses *re-authentication / token refresh* via Lock Actor, dan memperbarui header otentikasi sebelum melanjutkan transaksi yang tertunda.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Gunakan framework subsistem `os.Logger` terstruktur, bukan menggunakan `print()`. Logger terstruktur tidak membebani performa I/O aplikasi dan terintegrasi langsung dengan Console.app Mac.

```swift
import OSLog

public enum DataPipelineLog {
    private static let subsystem = Bundle.main.bundleIdentifier ?? "com.enterprise.datapipeline"
    
    public static let sync = Logger(subsystem: subsystem, category: "SyncEngine")
    public static let persistence = Logger(subsystem: subsystem, category: "Persistence")
    public static let network = Logger(subsystem: subsystem, category: "Network")
}

// Penggunaan di BackgroundDataSynchronizer:
DataPipelineLog.sync.info("Memulai sinkronisasi antrean. Record count: \(pendingRecords.count, privacy: .public)")
DataPipelineLog.sync.error("Sinkronisasi gagal pada ID: \(record.mutationId), Error: \(error.localizedDescription, privacy: .private)")
```

### Core Data & SwiftData SQLite Debug Argument:
Sematkan flag berikut pada *Product Scheme -> Arguments -> Arguments Passed On Launch* di Xcode untuk melihat operasi query SQL yang dihasilkan secara langsung di konsol debug:
```
-com.apple.CoreData.SQLDebug 3
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+-----------------------------------+-------------------------------------------------------------+
| OPERASI / KEBUTUHAN               | SINTAKS / PENDEKATAN UTAMA                                  |
+-----------------------------------+-------------------------------------------------------------+
| Background Concurrency Context    | @ModelActor actor CustomSyncActor { ... }                   |
| Main Thread Observability         | @Query private var items: [MyEntity]                        |
| Matikan Autosave Performa         | modelContext.autosaveEnabled = false                        |
| Deteksi Jaringan                  | NWPathMonitor().pathUpdateHandler = { path in ... }        |
| Daftarkan Background Refresh      | BGTaskScheduler.shared.register(forTaskWithIdentifier: ...) |
| Idempotency Mitigation            | Kirim 'X-Idempotency-Key: UUID' pada HTTP Request Header    |
| Conflict Reconciliation           | Resolusi Field-Level Merge atau Server-Version Monotonicity |
+-----------------------------------+-------------------------------------------------------------+
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1 - 5)
1. **Mengapa aplikasi tidak boleh menunggu respons HTTP sebelum memvalidasi dan menampilkan mutasi data pengguna pada antarmuka?**
2. **Apa yang terjadi bila Anda menggunakan `ModelContext` yang diinstansiasi di thread UI (MainActor) dari dalam closure `Task.detached`?**
3. **Mengapa SQLite WAL (Write-Ahead Logging) mode sangat krusial bagi arsitektur offline-first?**
4. **Apa fungsi mendasar dari penambahan kolom atribut `syncState` pada model lokal?**
5. **Bagaimana cara mencegah duplikasi eksekusi request pada backend jika jaringan terputus sebelum client menerima response status 200 OK?**

### Soal Intermediate (6 - 10)
6. **Secara mendalam, apa perbedaan esensial dari macro `@ModelActor` dibandingkan instansiasi aktor konvensional di Swift Concurrency?**
7. **Mengapa algoritma Last-Write-Wins (LWW) murni yang hanya bergantung pada stempel jam perangkat pengguna (Device Clock) dianggap berbahaya di sistem produksi terdistribusi?**
8. **Kapan kondisi di mana Three-Way Data Merge tidak dapat diselesaikan secara otomatis dan memerlukan campur tangan pengguna (*User Intervention*)?**
9. **Bagaimana Anda mendesain penanganan operasi penghapusan data (Deletion) secara offline agar server tahu entitas tersebut telah dihapus, dan tidak malah mengembalikannya saat proses sync berikutnya?**
10. **Bagaimana implementasi `expirationHandler` pada `BGAppRefreshTask` memengaruhi keselamatan status data di SQLite?**

---

### Kunci Jawaban & Pembahasan

1. Menunggu respons HTTP menciptakan dependensi pada latensi jaringan, menampilkan blocking spinner yang merusak user experience, serta menyebabkan kegagalan pencatatan data jika perangkat berada di luar jangkauan koneksi internet.
2. Membocorkan `ModelContext` lintas batas isolasi konkurensi melanggar thread safety, menyebabkan *race condition*, inkonsistensi memori lokal, dan crash tak terduga berupa `EXC_BAD_ACCESS`.
3. Mode WAL memisahkan proses pembacaan dan penulisan berkas basis data. Thread UI dapat membaca snapshot data secara real-time tanpa pernah terblokir oleh proses background worker yang sedang menulis ribuan baris data baru.
4. Memberikan penanda deterministik bagi UI untuk menampilkan status mutasi (misalnya ikon pending upload) dan memberi tahu Sync Engine data baris mana saja yang perlu dikirim ke server.
5. Dengan memanfaatkan *Idempotency Key* (UUID unik untuk setiap aksi mutasi) yang dikirimkan pada header HTTP. Server menyimpan cache kunci ini dan tidak mengeksekusi ulang logika mutasi jika kunci yang sama dikirim ulang.
6. Macro `@ModelActor` secara otomatis mengimplementasikan protokol `ModelActor`, menghasilkan *serial model executor* terdedikasi, membungkus `ModelContext` privat, dan menjamin seluruh interaksi Core Data/SwiftData terjadi strictly pada konteks thread serial aktor tersebut.
7. Jam perangkat klien rentan terhadap *clock skew*, manipulasi manual oleh user, atau perbedaan timezone yang membuat mutasi usang dapat secara salah menimpa data yang jauh lebih baru di database server.
8. Ketika dua sumber (lokal dan remote) memodifikasi atribut spesifik yang **sama persis** secara bersamaan dari basis baseline versi yang sama dengan nilai baru yang berbeda.
9. Menggunakan teknik *Soft Deletion* (Tombstone). Alih-alih langsung mengeksekusi perintah SQLite `DELETE`, entitas ditandai statusnya menjadi `syncState = .pendingDeletion`. Setelah server mengonfirmasi penghapusan di distributed database, baris lokal baru benar-benar dihapus (*Hard Delete*).
10. Jika iOS mencabut izin eksekusi background saat operasi berjalan, kegagalan memanggil `cancel()` pada Swift Task melalui `expirationHandler` dapat menyebabkan aplikasi dihentikan secara paksa (*jetsam kill*), yang berisiko meninggalkan file rollback journal SQLite dalam status tidak stabil.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "AeroSync: Engine Sinkronisasi Dokumen Inspeksi Offline-First"

### Sasaran & Spesifikasi Teknis:
Bangun sebuah modul mandiri menggunakan SwiftUI dan SwiftData dengan kriteria ketat berikut:
1. **Model Arsitektur:**
   * Bangun entitas `InspectionForm` dengan relasi 1-to-many ke `InspectionIssue`.
   * Terapkan *Soft Deletion pattern* (`isMarkedForDeletion: Bool`).
2. **Actor Engine:**
   * Buat `@ModelActor public actor OfflineSyncWorker` yang menangani sinkronisasi dua arah.
   * Eksekusi antrean mutasi menggunakan mekanisme *exponential backoff retry* jika terjadi simulasi kegagalan koneksi.
3. **Conflict Resolution Strategy:**
   * Terapkan skenario konflik buatan: Simulasi server memiliki nilai `updatedAt` yang lebih tinggi pada atribut tertentu.
   * Tulis fungsi `resolveConflict(local: InspectionForm, remote: InspectionFormDTO) -> FormReconciliationPlan` yang mempertahankan nilai lokal untuk field yang belum disinkronkan, namun mengadopsi field remote yang tidak memiliki perubahan lokal (*Field-Level Disjoint Merge*).
4. **Unit Test Verification (Wajib):**
   * Tulis minimal 3 Unit Test menggunakan `XCTest` atau `Swift Testing Framework`:
     * Verifikasi penulisan lokal berhasil saat `NetworkMonitor` offline.
     * Verifikasi antrean `PersistentMutationRecord` otomatis berkurang saat mock sync sukses.
     * Verifikasi isolasi konkurensi: Pastikan data store diuji menggunakan `ModelConfiguration(isStoredInMemoryOnly: true)`.