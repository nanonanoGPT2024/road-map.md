# Kurikulum Rekayasa Perangkat Lunak Enterprise: SwiftUI
## BAB 08: Persistensi & Offline-First Data Pipeline
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis & Mengisolasi Concurrency Context**: Menguasai arsitektur isolasi memori SwiftData/Core Data menggunakan `@ModelActor` dan `ModelExecutor` kustom untuk mencegah data race dan crash `EXC_BAD_ACCESS` pada Swift 6 Strict Concurrency mode.
- **Merancang Transactional Outbox Pattern**: Mengimplementasikan pipeline mutasi data lokal yang deterministik dan tangguh terhadap kegagalan jaringan (*zero data loss*) dengan antrean asinkronus berbasis prioritas.
- **Mengembangkan Resolusi Konflik Berskala Enterprise**: Membangun mekanisme rekonsiliasi data *bidirectional sync* (kombinasi *Last-Write-Wins* berbasis hybrid logical clocks dan skema *field-level merging*).
- **Mengoptimalkan Throughput & Footprint Memori**: Mengelola batching pemrosesan data skala masif (>50.000 entitas), pemanfaatan faulting context, serta eliminasi latensi sinkronisasi pada *Main Thread* agar rendering UI tetap berada di target 120 FPS (ProMotion).

---

### 2. Prerequisite
Untuk menyerap modul ini secara optimal, engineer wajib memiliki pemahaman mendalam tentang:
- **Swift Concurrency**: Actor isolation model, global actors (`@MainActor`), Structured Concurrency (`TaskGroup`, `AsyncStream`), serta kepatuhan protokol `Sendable`.
- **Dasar Persistensi Apple Core Engine**: SQLite backend architecture (WAL mode, page cache, schema migration dasar), lifecycle `NSManagedObjectContext` atau dasar `ModelContainer` / `ModelContext` pada SwiftData.
- **SwiftUI Rendering Mechanics**: Pemicu re-evaluasi *View Body*, mekanisme dependensi *DynamicProperty* via `@Query`, serta bridging observabilitas melalui macro `@Observable`.

---

### 3. Concept & Internal Architecture (Mendalam)

Membangun arsitektur *Offline-First* enterprise pada ekosistem Apple membutuhkan pemahaman komprehensif mengenai interaksi antara *User Interface Layer*, *Isolated Database Engine*, dan *Remote Networking Pipeline*.

```
   +-----------------------------------------------------------------------+
   |                       SWIFTUI VIEW LAYER                              |
   |   (Observes via @Query, renders at 120 FPS on @MainActor Context)     |
   +-----------------------------------------------------------------------+
                                      |
                      Dispatches Mutation Intent (DTO/Values)
                                      v
   +-----------------------------------------------------------------------+
   |                       DOMAIN PIPELINE / ACTOR                         |
   |              (AppCoordinator / Domain UseCases / BoundedContext)      |
   +-----------------------------------------------------------------------+
                                      |
         Writes Mutation Payload      | Spawns Controlled Task
                    v                 v
   +-----------------------------------------------------------------------+
   |                      TRANSACTIONAL OUTBOX PIPELINE                    |
   |                                                                       |
   |   +--------------------------+     +------------------------------+   |
   |   |   @ModelActor (Sync)     |     |   Outbox Engine Actor        |   |
   |   |   - Isolated ModelContext|     |   - Background Task Queue    |   |
   |   |   - Write-Ahead Records  |<===>|   - Exponential Backoff      |   |
   |   |   - Idempotency Ledger   |     |   - Network Path Monitor     |   |
   |   +--------------------------+     +------------------------------+   |
   +-----------------------------------------------------------------------+
                     |                                       |
    Executes Batched | Commits                               | Streams Sync
    Disk Operations  | (WAL)                                 | Payload (JSON/gRPC)
                     v                                       v
   +------------------------------------+   +------------------------------+
   |      SQLITE ENGINE LAYER (WAL)     |   |     REMOTE GATEWAY / CDN     |
   | - Shm / Wal Cache                  |   | - Idempotent Endpoints       |
   | - Cross-thread Notification Bus    |   | - Hybrid Logical Clock Sync  |
   +------------------------------------+   +------------------------------+
```

#### A. Isolasi Memori: `@ModelActor` vs Main Context
Pada aplikasi modular enterprise, menulis langsung ke `modelContext` milik view (`@Environment(\.modelContext)`) dari thread latar belakang adalah anti-pattern kritis. SwiftData mengikat context view ke `@MainActor`. Jika operasi *batch import* atau mutasi sinkronisasi dieksekusi di context ini, instruksi grafis UI akan terblokir (*hitch/hang*).

Protokol `ModelActor` mengatasi masalah ini dengan menggabungkan kapabilitas Swift Actor dengan context independen:
1. `ModelExecutor`: Mengelola serialisasi instruksi kerja database pada thread terisolasi.
2. `ModelContext`: Berjalan secara eksklusif di dalam boundaries aktor tersebut. Context ini dibuat detached dari Main Context tetapi membaca database file SQLite fisik yang sama via *shared WAL (Write-Ahead Logging)*.
3. Notifikasi Antar Context: Ketika `@ModelActor` melakukan commit (`save()`), engine SQLite memicu sistem koordinasi internal yang secara asinkron memperbarui snapshot memori pada `@MainActor`, merender ulang UI via `@Query` secara aman.

#### B. The Transactional Outbox Pattern
Untuk menjamin determinisme dalam konektivitas nirkabel yang fluktuatif (*spotty connectivity*), seluruh mutasi sistem tidak boleh berasumsi bahwa jaringan tersedia:
- Operasi bisnis lokal dan pembuatan catatan *Outbox Record* dieksekusi dalam **satu transaksi database lokal tunggal** yang atomik (*All-or-Nothing*).
- Jika app dihentikan paksa (*crash/terminated*) sebelum transmisi payload berhasil, antrean outbox tetap tersimpan secara persisten pada disk.
- Sinkronisasi engine membaca antrean ini, mengunggah mutasi secara serial/idempoten, dan menghapus atau menandai mutasi sebagai *synced* hanya setelah menerima respons HTTP 2xx/gRPC status `OK`.

---

### 4. Why & What

| Dimensi | Pendekatan Naive (Online-First + Cache) | Pendekatan Enterprise (Offline-First Outbox) |
| :--- | :--- | :--- |
| **Pusat Kebenaran (Source of Truth)** | Server API; database lokal hanya cache pasif sementara. | Database lokal (SQLite/SwiftData); API bertindak sebagai sync hub. |
| **Resiliensi Transaksi** | Rentan hilang jika aplikasi ditutup paksa saat request *in-flight*. | Zero-loss; dijamin atomisitas lokal via Outbox Pattern. |
| **Performa Rendering UI** | Sering menunggu *network roundtrip* (menampilkan loader/shimmer). | Instan (Optimistic UI Update); data dimutasi lokal langsung di frame 0ms. |
| **Kebutuhan Identitas Data** | Mengandalkan *auto-increment* database ID dari backend. | Menggunakan UUID v4/v7 terdistribusi yang dibuat di sisi klien. |
| **Skalabilitas Data Sync** | Polling masif atau refetch seluruh list (`GET /api/v1/items`). | Delta sync menggunakan *Watermark / Version Clocks / Sequence Numbers*. |

---

### 5. How: Workflow Detail Rekonsiliasi Data

Alur siklus hidup penuh operasi mutasi dari aksi pengguna hingga resolusi backend:

```
[User Action] 
       │
       ▼
1. Emit Optimistic Mutation Command (ViewModel / Coordinator)
       │
       ▼
2. Write Transaction to Local SQLite via Dedicated `@ModelActor`
   ├── A. Update Domain Model (State: PENDING_SYNC)
   └── B. Append Operation into OutboxEntity (Action, Payload, UUID, Monotonic Timestamp)
       │
       ▼
3. UI Observes Change immediately via `@Query` (0ms feedback)
       │
       ▼
4. Outbox Worker detects network availability (NWPathMonitor)
       │
       ▼
5. Worker reads Outbox FIFO -> Dispatches HTTP/gRPC Request with Idempotency-Key
       │
       ├───► [Network Failure / 5xx] ──► Apply Exponential Backoff + Jitter -> Stop Queue
       │
       ├───► [Conflict 409 / Version Mismatch]
       │         │
       │         ▼
       │     Trigger Conflict Resolution Engine
       │     ├── Branch A: Client-Wins -> Force Remote Overwrite
       │     ├── Branch B: Server-Wins -> Revert Domain Model & Flush Outbox Entry
       │     └── Branch C: Field-Level Merge -> Recompute state, Commit Local, Resync
       │
       └───► [Success 200/201 OK]
                 │
                 ▼
6. Mark OutboxEntity as EXECUTED or Purge from Store
       │
       ▼
7. Broadcast Sync Success -> Trigger Merged Checkpoint
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Buku Kas Ekspedisi Lapangan & Kurir Sentral
Bayangkan tim logistik lapangan yang mengantarkan logistik ke daerah pedalaman tanpa sinyal seluler.
- **Naive approach**: Kurir berhenti di setiap rumah pelanggan, menunggu sinyal internet muncul untuk mencatat paket telah terkirim ke server pusat. Jika tidak ada sinyal, paket tidak diserahkan.
- **Enterprise approach (Outbox Pipeline)**: Kurir membawa **Buku Kas Fisik (SQLite via ModelActor)**. Ketika paket tiba di pelanggan, kurir menandatangani buku kas dan menulis nota tugas pengiriman di halaman **Outbox Pending**. Pelanggan menerima paket seketika (*Optimistic Local Commit*). Ketika armada kurir kembali ke pangkalan yang memiliki Wi-Fi satelit (*NWPathMonitor online*), petugas sentral memindai buku nota dan mengirimkan log transmisi batch ke server pusat. Jika server mendeteksi anomali pada salah satu paket, resolusi diterapkan di pangkalan sesuai aturan rekonsiliasi yang disepakati (*Conflict Resolution*).

---

### 7. Implementasi Kode Terstruktur & Produksi

Di bawah ini adalah implementasi sistem persistensi offline-first modern yang sepenuhnya mematuhi arsitektur isolasi konkurensi Swift 6.

#### A. Definisi Entitas & Skema (Domain & Outbox Models)

```swift
import Foundation
import SwiftData

@Model
public final class InventoryItem {
    @Attribute(.unique) public var id: UUID
    public var sku: String
    public var name: String
    public var quantity: Int
    public var updatedAt: Date
    public var syncStateRaw: String
    
    public var syncState: SyncState {
        get { SyncState(rawValue: syncStateRaw) ?? .pendingCreation }
        set { syncStateRaw = newValue.rawValue }
    }
    
    public init(id: UUID = UUID(), sku: String, name: String, quantity: Int, updatedAt: Date = Date(), syncState: SyncState = .pendingCreation) {
        self.id = id
        self.sku = sku
        self.name = name
        self.quantity = quantity
        self.updatedAt = updatedAt
        self.syncStateRaw = syncState.rawValue
    }
}

public enum SyncState: String, Codable, Sendable {
    case synced = "SYNCED"
    case pendingCreation = "PENDING_CREATION"
    case pendingUpdate = "PENDING_UPDATE"
    case pendingDeletion = "PENDING_DELETION"
}

@Model
public final class OutboxRecord {
    @Attribute(.unique) public var id: UUID
    public var entityId: UUID
    public var entityType: String
    public var operationType: String
    public var serializedPayload: Data
    public var createdAt: Date
    public var retryCount: Int
    public var lastError: String?

    public init(
        id: UUID = UUID(),
        entityId: UUID,
        entityType: String,
        operationType: String,
        serializedPayload: Data,
        createdAt: Date = Date(),
        retryCount: Int = 0,
        lastError: String? = nil
    ) {
        self.id = id
        self.entityId = entityId
        self.entityType = entityType
        self.operationType = operationType
        self.serializedPayload = serializedPayload
        self.createdAt = createdAt
        self.retryCount = retryCount
        self.lastError = lastError
    }
}
```

#### B. Thread-Safe Background Mutation via `@ModelActor`

```swift
import Foundation
import SwiftData

@ModelActor
public actor InventoryPersistenceActor {
    
    public func createItem(sku: String, name: String, initialQuantity: Int) throws -> UUID {
        let itemId = UUID()
        let item = InventoryItem(
            id: itemId,
            sku: sku,
            name: name,
            quantity: initialQuantity,
            updatedAt: Date(),
            syncState: .pendingCreation
        )
        modelContext.insert(item)
        
        // Simpan Outbox secara atomik dalam context yang sama
        let payloadDict: [String: Any] = [
            "id": itemId.uuidString,
            "sku": sku,
            "name": name,
            "quantity": initialQuantity
        ]
        let payloadData = try JSONSerialization.data(withJSONObject: payloadDict)
        
        let outbox = OutboxRecord(
            entityId: itemId,
            entityType: "InventoryItem",
            operationType: "CREATE",
            serializedPayload: payloadData
        )
        modelContext.insert(outbox)
        
        try modelContext.save()
        return itemId
    }
    
    public func fetchPendingOutboxBatches(limit: Int) throws -> [OutboxTransferDTO] {
        var descriptor = FetchDescriptor<OutboxRecord>(
            predicate: #Predicate { $0.retryCount < 5 },
            sortBy: [SortDescriptor(\.createdAt, order: .forward)]
        )
        descriptor.fetchLimit = limit
        
        let records = try modelContext.fetch(descriptor)
        return records.map {
            OutboxTransferDTO(
                id: $0.id,
                entityId: $0.entityId,
                entityType: $0.entityType,
                operationType: $0.operationType,
                payload: $0.serializedPayload,
                retryCount: $0.retryCount
            )
        }
    }
    
    public func acknowledgeOutboxSuccess(outboxId: UUID, entityId: UUID) throws {
        // Hapus Outbox Entry
        let outboxPredicate = #Predicate<OutboxRecord> { $0.id == outboxId }
        try modelContext.delete(model: OutboxRecord.self, where: outboxPredicate)
        
        // Mutasikan status sinkronisasi item
        let itemPredicate = #Predicate<InventoryItem> { $0.id == entityId }
        var descriptor = FetchDescriptor<InventoryItem>(predicate: itemPredicate)
        descriptor.fetchLimit = 1
        
        if let item = try modelContext.fetch(descriptor).first {
            item.syncState = .synced
        }
        
        try modelContext.save()
    }
    
    public func recordSyncFailure(outboxId: UUID, errorDescription: String) throws {
        let outboxPredicate = #Predicate<OutboxRecord> { $0.id == outboxId }
        var descriptor = FetchDescriptor<OutboxRecord>(predicate: outboxPredicate)
        descriptor.fetchLimit = 1
        
        if let outbox = try modelContext.fetch(descriptor).first {
            outbox.retryCount += 1
            outbox.lastError = errorDescription
            try modelContext.save()
        }
    }
}

public struct OutboxTransferDTO: Sendable {
    public let id: UUID
    public let entityId: UUID
    public let entityType: String
    public let operationType: String
    public let payload: Data
    public let retryCount: Int
}
```

#### C. Outbox Synchronization Engine & Retry Orchestrator

```swift
import Foundation
import Network

public actor SynchronizationEngine {
    private let persistenceActor: InventoryPersistenceActor
    private let networkClient: RemoteNetworkGateway
    private var isSyncing: Bool = false
    
    public init(persistenceActor: InventoryPersistenceActor, networkClient: RemoteNetworkGateway) {
        self.persistenceActor = persistenceActor
        self.networkClient = networkClient
    }
    
    public func triggerSync() async {
        guard !isSyncing else { return }
        isSyncing = true
        defer { isSyncing = false }
        
        do {
            let pendingItems = try await persistenceActor.fetchPendingOutboxBatches(limit: 20)
            guard !pendingItems.isEmpty else { return }
            
            for task in pendingItems {
                do {
                    // Gunakan idempotency key pada header transmisi data remote
                    try await networkClient.dispatchSyncPayload(
                        idempotencyKey: task.id,
                        entityType: task.entityType,
                        operation: task.operationType,
                        data: task.payload
                    )
                    
                    // Transaksi lokal menandai sukses
                    try await persistenceActor.acknowledgeOutboxSuccess(
                        outboxId: task.id,
                        entityId: task.entityId
                    )
                } catch {
                    let backoffSeconds = pow(2.0, Double(task.retryCount))
                    try? await Task.sleep(nanoseconds: UInt64(backoffSeconds * 1_000_000_000))
                    
                    try await persistenceActor.recordSyncFailure(
                        outboxId: task.id,
                        errorDescription: error.localizedDescription
                    )
                }
            }
        } catch {
            // Log telemetry error secara terpusat
        }
    }
}

public protocol RemoteNetworkGateway: Sendable {
    func dispatchSyncPayload(idempotencyKey: UUID, entityType: String, operation: String, data: Data) async throws
}
```

#### D. Konsumsi UI Berbasis SwiftUI Menggunakan Optimistic Rendering

```swift
import SwiftUI
import SwiftData

public struct InventoryDashboardView: View {
    @Environment(\.modelContext) private var modelContext
    
    // UI secara instan terupdate saat SQLite lokal dimodifikasi oleh Actor
    @Query(sort: \InventoryItem.updatedAt, order: .reverse) 
    private var items: [InventoryItem]
    
    private let persistenceActor: InventoryPersistenceActor
    private let syncEngine: SynchronizationEngine
    
    public init(persistenceActor: InventoryPersistenceActor, syncEngine: SynchronizationEngine) {
        self.persistenceActor = persistenceActor
        self.syncEngine = syncEngine
    }
    
    public var body: some View {
        NavigationStack {
            List(items) { item in
                HStack {
                    VStack(alignment: .leading) {
                        Text(item.name)
                            .font(.headline)
                        Text("SKU: \(item.sku)")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    VStack(alignment: .trailing) {
                        Text("\(item.quantity) unit")
                            .font(.body.monospacedDigit())
                        
                        SyncStatusBadge(status: item.syncState)
                    }
                }
            }
            .navigationTitle("Warehouse Stock")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button(action: triggerCreateItem) {
                        Label("Tambah Stok", systemImage: "plus")
                    }
                }
                ToolbarItem(placement: .status) {
                    Button("Sync Manual") {
                        Task { await syncEngine.triggerSync() }
                    }
                }
            }
        }
    }
    
    private func triggerCreateItem() {
        Task {
            _ = try await persistenceActor.createItem(
                sku: "WH-\(Int.random(in: 1000...9999))",
                name: "Barang Logistik Baru",
                initialQuantity: Int.random(in: 10...50)
            )
            // Trigger sync pipeline di background
            await syncEngine.triggerSync()
        }
    }
}

private struct SyncStatusBadge: View {
    let status: SyncState
    
    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(statusColor)
                .frame(width: 8, height: 8)
            Text(status.rawValue)
                .font(.caption2.bold())
                .foregroundStyle(statusColor)
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 2)
        .background(statusColor.opacity(0.12))
        .clipShape(Capsule())
    }
    
    private var statusColor: Color {
        switch status {
        case .synced: return .green
        case .pendingCreation, .pendingUpdate: return .orange
        case .pendingDeletion: return .red
        }
    }
}
```

---

### 8. Real World Case Study: Edge Logistics System (100k SKU Catalog)

#### Konteks & Skala Masalah
Sebuah platform manajemen logistik melayani gudang pelabuhan (*maritime port*) dengan konektivitas satelit intermittent. Aplikasi iPadOS menangani katalog lebih dari 100.000 SKU. Masalah yang dihadapi:
- Main-thread freeze hingga 8 detik saat mengimpor delta-manifest harian.
- Konflik pembaruan kuantitas stok barang saat dua petugas meng-update SKU yang sama secara paralel di dua kontainer berbeda.

#### Arsitektur Solusi
1. **Model Context Partitioning**: Data read katalog memanfaatkan paging menggunakan `#Predicate` dengan fetch limit kaku (`limit = 50`) dan indexed fields pada level SQLite.
2. **Delta Import Processor via Detached Task**: Import batch 10.000 items dieksekusi di dalam `@ModelActor` menggunakan `modelContext.transaction {}` dengan commit batch interval setiap 1.000 records untuk membatasi lonjakan alokasi memori (*heap footprint spikes*).
3. **Resolusi Konflik Tiga Arah (Three-Way Merge)**:
   - Metadata entitas menyimpan `version: UInt64` dan `lastModifiedDeviceUUID: UUID`.
   - Ketika engine menerima status respons remote `409 Conflict`, pipeline mengambil versi snapshot remote terbaru, mengeksekusi fungsi domain deterministik berikut:

```swift
public struct ConflictResolver {
    public static func resolve<T: LogisticalEntity>(local: T, remote: T) -> T {
        // Aturan Bisnis: Kuantitas stok inventaris menggunakan delta merging
        var resolved = remote
        let localDelta = local.quantityDeltaModifier
        resolved.quantity = max(0, remote.quantity + localDelta)
        resolved.version = remote.version + 1
        return resolved
    }
}
```

---

### 9. Trade-offs Architecture Analysis

| Parameter | Pendekatan Direct-Sync (Sync Langsung) | Pendekatan Transactional Outbox |
| :--- | :--- | :--- |
| **Throughput Mutasi** | Rendah; bergantung langsung pada latency jaringan (RTT). | **Sangat Tinggi**; dibatasi hanya oleh kecepatan penulisan disk lokal (I/O). |
| **Konsumsi Baterai** | Rendah-Sedang (transmisi sporadis). | **Lebih Tinggi** jika antrean loop retry tidak dibatasi (mitigasi: exponential backoff + NWPathMonitor). |
| **Kompleksitas Schema & Storage** | Minimal (hanya tabel bisnis). | **Meningkat 2x-3x** (memerlukan tabel ledger outbox, tracking state, dan snapshot version). |
| **Konsistensi Data (Consistency)** | Konsistensi instan sederhana (gagal langsung tampilkan alert). | **Eventual Consistency**; UI wajib mendesain state asinkronus (pending, retrying, conflicted). |

---

### 10. Common Mistakes & Troubleshooting

#### Pitfall 1: Retaining `ModelContext` Across Threads
- **Gejala**: Crash seketika dengan pesan `Illegal attempt to establish a relationship between distinct contexts` atau memory access corruption `EXC_BAD_ACCESS`.
- **Root Cause**: Mengoper instans class `@Model` langsung melewati boundary async antar-aktor atau memasukkan model yang dibuat di Thread A ke dalam context milik Thread B.
- **Solusi**: Jangan pernah mengoper *live model object* melewati boundaries. Oper hanya tipe data primitif atau `Sendable DTO`, lalu fetch kembali entitas tersebut di dalam actor lokal melalui ID (`PersistentIdentifier` atau `UUID`).

#### Pitfall 2: Large Transaction Memory Bloat
- **Gejala**: Aplikasi ditutup paksa oleh iOS Watchdog karena Out-Of-Memory (Jetsam Event) saat melakukan background import.
- **Root Cause**: Memasukkan 50.000 entitas ke dalam single `modelContext` tanpa melakukan save secara bertahap. Snapshot memori internal menyimpan pointer seluruh dirty-objects.
- **Solusi**: Terapkan chunked execution batching:
```swift
for batch in items.chunks(ofCount: 1_000) {
    for item in batch { modelContext.insert(item) }
    try modelContext.save()
}
```

#### Pitfall 3: Blocking Main Actor via Query Predicates
- **Gejala**: UI drop frame parah saat mengetik di search bar.
- **Root Cause**: Menggunakan Predicate yang tidak didukung index database SQLite fisik (seperti operasi string matching `contains` tanpa normalisasi lowercased).
- **Solusi**: Buat kolom terdenormalisasi yang telah diindeks secara khusus untuk pencarian teks (*search tokens*), hindari dynamic regular expressions kompleks di dalam `#Predicate`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan UUID Klien**: Buat identifier di sisi aplikasi klien menggunakan UUID format, jangan menunggu backend ID.
- [ ] **Hindari MainActor Persistence Operations**: Semua mutasi massal, sync background, dan cleanup wajib berada di dalam instance `@ModelActor`.
- [ ] **Indeks Atribut Predikat**: Pastikan field yang sering difilter atau diurutkan (`updatedAt`, `sku`, `syncState`) ditandai dengan opsi indexing yang sesuai.
- [ ] **Aktifkan WAL Mode**: Verifikasi SQLite backend bekerja dalam mode Write-Ahead Logging untuk mengizinkan operasi *concurrent read* dari MainActor saat background actor sedang melakukan *write*.
- [ ] **Pemberian Identitas Unik pada Request**: Selalu kirim UUID dari `OutboxRecord` sebagai header HTTP `X-Idempotency-Key` ke API Gateway remote.
- [ ] **Tangani Network Path Switch**: Gunakan framework `Network.framework` (`NWPathMonitor`) untuk menghentikan loop antrean sinkronisasi secara instan saat perangkat *offline*, mencegah *battery draining* akibat failed retries.

---

### 12. Hands-on Practice: Membangun Resilient Sync Queue Engine

Simpan seluruh file berikut pada struktur direktori: `hands-on/m02/`

#### Step 1: Inisialisasi Project Model Container
Buat file `hands-on/m02/StorageSchema.swift`:
```swift
import Foundation
import SwiftData

@Model
public final class AuditLogEntry {
    @Attribute(.unique) public var entryId: UUID
    public var timestamp: Date
    public var message: String
    
    public init(entryId: UUID = UUID(), timestamp: Date = Date(), message: String) {
        self.entryId = entryId
        self.timestamp = timestamp
        self.message = message
    }
}
```

#### Step 2: Implementasi Custom Model Actor
Buat file `hands-on/m02/AuditActor.swift`:
```swift
import Foundation
import SwiftData

@ModelActor
public actor AuditLoggingActor {
    public func recordBatch(messages: [String]) throws {
        for msg in messages {
            let log = AuditLogEntry(message: msg)
            modelContext.insert(log)
        }
        try modelContext.save()
    }
    
    public func countLogs() throws -> Int {
        let descriptor = FetchDescriptor<AuditLogEntry>()
        return try modelContext.fetchCount(descriptor)
    }
}
```

#### Step 3: Implementasi Test Run Harness
Buat file `hands-on/m02/ExecutionHarness.swift`:
Eksekusi pengujian stres konkurensi: Menulis 5.000 log dari 5 parallel task terpisah tanpa memblokir thread eksekusi utama.
```swift
import Foundation
import SwiftData

@main
struct AppHarness {
    static func main() async throws {
        let schema = Schema([AuditLogEntry.self])
        let config = ModelConfiguration(isStoredInMemoryOnly: true)
        let container = try ModelContainer(for: schema, configurations: config)
        
        let actorInstance = AuditLoggingActor(modelContainer: container)
        
        print("Starting Parallel Concurrency Stress Test...")
        let startTime = CFAbsoluteTimeGetCurrent()
        
        await withTaskGroup(of: Void.self) { group in
            for i in 0..<5 {
                group.addTask {
                    let batch = (0..<1_000).map { "Task \(i) - Log Message Index: \($0)" }
                    try? await actorInstance.recordBatch(messages: batch)
                }
            }
        }
        
        let totalTime = CFAbsoluteTimeGetCurrent() - startTime
        let count = try await actorInstance.countLogs()
        print("Completed. Total Rows: \(count) in \(String(format: "%.4f", totalTime)) seconds.")
    }
}
```

---

### 13. Exercise

#### Level Easy
Ubah entitas `InventoryItem` agar memiliki field status `isSoftDeleted: Bool`. Modifikasi operasi query di antarmuka SwiftUI agar menggunakan `#Predicate` yang memfilter item yang belum dihapus secara otomatis.

#### Level Medium
Tambahkan penanganan *Network Reachability* ke dalam `SynchronizationEngine`. Jika konektivitas berstatus `.unsatisfied`, engine harus secara otomatis membatalkan antrean sinkronisasi yang sedang berjalan dan masuk ke mode hibernasi hingga jaringan kembali online.

#### Level Hard
Rancang dan implementasikan skema *Hybrid Logical Clock (HLC)* di dalam SwiftData untuk mendeteksi persistensi kasual (*causality tracking*) antara dua node iPad tanpa bergantung pada sinkronisasi jam dinding (*wall-clock time*) NTP perangkat.

---

### 14. Challenge: Distributed Field-Level CRDT Engine

**Deskripsi Kasus:**
Bangun sebuah prototipe fungsional mesin *Conflict-Free Replicated Data Type (CRDT)* berbasis State-based LWW-Element-Set menggunakan SwiftData.

**Kebutuhan Teknis:**
1. Rancang model dokumen kolaboratif di mana setiap properti dari dokumen tersebut (`title`, `bodyPayload`, `tags`) memiliki stempel waktu terisolasi masing-masing (*per-field metadata*).
2. Implementasikan pipeline sinkronisasi peer-to-peer simulatif: Jika dua perangkat melakukan pembaruan di atribut yang berbeda secara offline (Node A mengubah `title`, Node B mengubah `bodyPayload`), saat proses sync terjadi, kedua pembaruan harus bergabung (*converge*) secara deterministik tanpa kehilangan data satu pun.
3. Kepatuhan mutlak terhadap isolasi *Swift 6 Strict Concurrency*. Tidak boleh ada *compiler warnings* terkait data race.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Mengapa modifikasi database pada antarmuka SwiftUI yang menggunakan `@Environment(\.modelContext)` tidak boleh digunakan untuk background batch importing?**
   - *Jawaban*: Karena context tersebut terikat pada `@MainActor`. Operasi pemrosesan data masif akan mengunci eksekusi thread utama (*UI hang*), merusak frame-rate render aplikasi.

2. **Apa peran utama dari protokol `@ModelActor` di SwiftData?**
   - *Jawaban*: Menyediakan wrapper *actor-isolated* yang mengelola lifecycle `ModelContext` dan `ModelExecutor` independen secara *thread-safe*, mengisolasi state persistensi dari thread lain.

3. **Mengapa penggunaan UUID lebih direkomendasikan dibanding Auto-Increment Integer ID pada arsitektur offline-first?**
   - *Jawaban*: UUID dapat di-generate secara independen dan unik di sisi klien tanpa perlu round-trip koordinasi ke backend database sentral.

4. **Apa fungsi mode Write-Ahead Logging (WAL) pada SQLite di balik implementasi SwiftData?**
   - *Jawaban*: WAL memungkinkan pembacaan (*concurrent reads*) dan penulisan (*concurrent writes*) terjadi secara simultan tanpa saling memblokir (*non-blocking reads*).

5. **Apa yang dimaksud dengan Optimistic UI Update?**
   - *Jawaban*: Pola di mana antarmuka pengguna langsung memperbarui tampilan datanya secara instan dengan asumsi transaksi lokal valid, sebelum menerima konfirmasi kesuksesan dari remote backend server.

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Bagaimana cara mencegah crash `EXC_BAD_ACCESS` saat mentransfer data hasil query dari `@ModelActor` ke `@MainActor`?**
   - *Jawaban*: Hindari mentransfer managed object class reference secara langsung. Transfer identifier unik (`PersistentIdentifier`), DTO bertipe *struct*, atau tipe data dasar yang mematuhi protokol `Sendable`.

7. **Kapan *Exponential Backoff with Full Jitter* wajib diterapkan pada Synchronization Pipeline?**
   - *Jawaban*: Saat terjadi kegagalan transmisi jaringan berseri, untuk mencegah masalah *thundering herd problem* (lonjakan beban server serentak ketika konektivitas internet baru saja pulih).

8. **Mengapa operasi `modelContext.save()` tidak boleh dipanggil setiap kali satu iterasi loop memasukkan data dalam batch 50.000 items?**
   - *Jawaban*: Karena setiap `save()` memicu disk I/O flush dan memancarkan notifikasi perubahan konteks secara masif, yang menyebabkan latensi tinggi; solusinya adalah melakukan commit per *chunk* (misalnya setiap 500-1.000 item).

9. **Apa kegunaan HTTP Header `X-Idempotency-Key` yang diambil dari identitas `OutboxRecord`?**
   - *Jawaban*: Menjamin server backend tidak mengeksekusi operasi bisnis yang sama berulang kali (duplikasi mutasi) jika respons jaringan terputus saat request telah berhasil diproses oleh server.

10. **Bagaimana mekanisme macro `@Query` memperbarui View saat ada perubahan data dari `@ModelActor` latar belakang?**
    - *Jawaban*: Saat context background mengeksekusi `save()`, notifikasi database tingkat rendah dipancarkan. Main context membaca perubahan tersebut via shared WAL file, dan `@Query` mengevaluasi ulang *dependency tracking*-nya, memicu refresh render view body.

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario A**: Sebuah aplikasi retail farmasi offline-first mengalami kondisi di mana kasir A menjual obat sisa 1 strip, dan kasir B menjual obat yang sama secara bersamaan di iPad yang berbeda saat router Wi-Fi lokal mati. Saat router menyala, Outbox Engine kasir mana yang harus menang, dan bagaimana status inventaris harus direkonsiliasi?
    - *Analisis Solusi*: Kasus ini tidak dapat diselesaikan hanya dengan *Last-Write-Wins (LWW)* murni karena akan menyebabkan *overselling* (stok minus tanpa audit). Sistem harus mengimplementasikan resolusi berbasis *Compensation Transaction*: Transaksi pertama yang diakui oleh remote ledger divalidasi sukses, sementara transaksi kasir berikutnya ditandai berstatus `RECONCILIATION_REQUIRED`, memicu alur antarmuka khusus bagi supervisor untuk mengesahkan pembatalan atau subsitusi barang.

12. **Skenario B**: Selama pengujian performa, aplikasi mengalami lonjakan alokasi RAM dari 80 MB menjadi 1.2 GB yang berujung pada crash *OOM Termination* oleh sistem operasi saat melakukan sinkronisasi delta 20.000 record baru. Profiling Instruments menunjukkan retain cycle pada objek `ModelContext`. Di mana letak masalahnya?
    - *Analisis Solusi*: ModelContext menahan referensi objek yang baru dimasukkan dalam memori graf internalnya (*registered objects graph*). Jika seluruh 20.000 objek dibuat di satu context tanpa pembersihan berkala, memori tidak akan pernah dideallokasikan. Solusinya: Pisahkan pemrosesan ke dalam batch loop yang lebih kecil, panggil `save()`, lalu inisialisasi ulang context per batch atau gunakan scope *autoreleasepool* untuk membersihkan heap snapshot secara paksa.

13. **Skenario C**: Pada Swift 6 Strict Concurrency, kompilator mengeluarkan error: `Type 'InventoryItem' does not conform to the 'Sendable' protocol` saat developer mencoba mem-passing instance `InventoryItem` dari ViewModel aktor ke `@ModelActor`. Mengapa arsitektur SwiftData dirancang demikian oleh Apple, dan apa desain perbaikan arsitektural yang paling tepat?
    - *Analisis Solusi*: Model class SwiftData adalah *reference type* yang merepresentasikan state internal database yang *mutable* dan terikat erat pada context pembuatnya. Membuatnya `Sendable` secara manual melanggar hukum keamanan memori karena data race akan terjadi jika dua thread memutasi properti model yang sama secara simultan. Desain perbaikan yang tepat: Ekstrak data yang akan dimutasi ke dalam bentuk `Sendable struct` (DTO payload), transfer DTO tersebut ke `@ModelActor`, lalu lakukan mutasi entity secara privat di dalam context actor tersebut.

---

### 16. Summary
Membangun arsitektur *Offline-First* enterprise pada SwiftUI memerlukan transisi paradigma dari sekadar melakukan pemanggilan REST API langsung menjadi orkestrasi pipeline data terdistribusi:
1. **Detached Memory Boundaries**: Gunakan `@ModelActor` untuk mengisolasi mutasi disk berat dari UI MainActor.
2. **Determinisme Outbox**: Bungkus semua aksi lokal ke dalam transactional outbox pattern untuk menjamin *zero data loss* saat offline.
3. **Optimistic Rendering**: Gunakan kombinasi `@Query` lokal dan UUID independen agar responsivitas aplikasi tetap berada pada target 120 FPS tanpa menunggu latensi jaringan remote.
4. **Idempotensi & Resolusi**: Lindungi API gateway menggunakan idempotency key serta terapkan skema rekonsiliasi yang deterministik untuk menangani konflik konkurensi multi-node.