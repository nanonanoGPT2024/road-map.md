# Bab 06 Module 01: Jaringan, Serialisasi Data, & Offline-First Persistence

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 03-Frontend-and-Mobile
* **Teknologi Utama:** iOS (Swift 6, URLSession, Swift Concurrency, SwiftData, CoreData engine)
* **Topik Modul:** Jaringan, Serialisasi Data, & Offline-First Persistence
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat:** Pemahaman mendalam mengenai Swift Concurrency (`async`/`await`, `Actor`, Structured Concurrency), Protocol-Oriented Programming, Memory Management (ARC, Retain Cycles), dan dasar-dasar arsitektur clean/modular pada iOS.

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, Anda diharapkan mampu:

1. **Membangun Abstraksi Jaringan Resilien:** Merancang networking layer modular berbasis Swift Concurrency (`URLSession`, `AsyncSequence`, Protocol-Oriented API Client) yang mendukung dekode asinkron, interceptor, retry otomatis dengan exponential backoff, serta pembatalan tugas (*task cancellation*).
2. **Menguasai Serialisasi Data Mutakhir:** Mengimplementasikan pipeline serialisasi JSON berperforma tinggi menggunakan protokol `Codable` kustom, strategi deserialisasi dinamis, isolasi aktor, penanganan polymorphic payload, serta strategi decoding tanpa parsing berulang (*zero-copy parsing paradigm*).
3. **Mendesain Arsitektur Offline-First:** Mengonstruksi pola *Single Source of Truth* (SSOT) yang memisahkan boundary antara cache lokal (`SwiftData` / `Core Data`) dan sinkronisasi remote API melalui layer *Repository Pattern*.
4. **Menerapkan Sinkronisasi Data & Rekonsiliasi Konflik:** Menyusun mesin sinkronisasi dua arah (*bi-directional sync engine*) yang menangani operasi offline queuing (Write-Ahead Logging / Outbox Pattern), rekonsiliasi idempotensi, mitigasi konflik versi berbasis *vector clock* / *last-write-wins*, dan background fetch task.
5. **Mengaudit Keamanan & Observabilitas Persistence:** Mengimplementasikan *Certificate Pinning*, enkripsi rest data menggunakan *SQLCipher* / *Data Protection Keychain*, serta melacak jejak telemetri menggunakan `os_signpost` dan metrik performa Instruments.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: "Network as an Eventual Source, Disk as Absolute Truth"

Dalam pengembangan aplikasi mobile berskala enterprise, koneksi jaringan harus selalu diasumsikan **tidak stabil (*unreliable*)**, **lambat (*latent*)**, atau **hilang sama sekali (*offline*)**. Paradigma naif memperlakukan REST API sebagai sumber data langsung UI:

```
[UI Component] ---> (Meminta Data) ---> [Network API] ---> (Decode) ---> [Render ke Layar]
```

Pola ini rapuh. Setiap kegagalan HTTP, timeout, atau fluktuasi sinyal langsung merusak antarmuka pengguna (*layout jitter*, *infinite loading spinner*, atau *blank screen*). 

Model mental yang benar pada arsitektur modern adalah **Offline-First Reactive Persistence**:

```
[UI Component] <--- (Observasi Aliran Reaktif) <--- [Local Persistence (SSOT)]
                                                              ^
                                                              | (Tulis/Update)
                                                    [Sync / Network Engine]
                                                              ^
                                                              | (Fetch / Push Delta)
                                                       [Remote Server]
```

UI **hanya boleh** mengamati (*observe*) disk lokal (misalnya `SwiftData` atau `CoreData`). Disk lokal bertindak sebagai *Single Source of Truth* (SSOT). Network Engine berjalan sebagai latar belakang asinkron: mengambil data dari server, memvalidasi dan membandingkan delta, memperbarui database lokal, dan membiarkan mekanisme reaktif lokal memperbarui UI secara deterministik. 

Ketika pengguna melakukan mutasi data (misalnya: *Create*, *Update*, *Delete*):
1. Mutasi ditulis langsung ke database lokal secara optimistik (*Optimistic UI*).
2. Perubahan dicatat ke dalam antrean *Outbox Pattern* lokal dengan status `pending`.
3. Background Worker menguras antrean tersebut ke API remote saat jaringan tersedia.
4. Jika server menolak dengan galat bisnis, sistem membatalkan mutasi lokal (*compensating transaction*) atau memicu resolusi konflik.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Hidup Request, Persistence, dan Sync Engine

Diagram alur berikut mendemonstrasikan orkestrasi lengkap antara UI, Repository, Outbox Queue, Network Engine, dan Engine Persistence Database:

```
+---------------------------------------------------------------------------------------------------+
|                                       PRESENTATION LAYER (UI)                                     |
+---------------------------------------------------------------------------------------------------+
       |                                                 ^
  (1) Dispatch Action                              (8) Reactive Stream Updates
       v                                                 |
+---------------------------------------------------------------------------------------------------+
|                                          REPOSITORY LAYER                                         |
+---------------------------------------------------------------------------------------------------+
       |                                                 ^
       |                                                 |
  (2) Tulis Optimistik                             (7) SwiftData / Context Notification
       v                                                 |
+--------------------------------+              +---------------------------------------------------+
|     OUTBOX / MUTATION QUEUE    |              |              LOCAL STORAGE (SSOT)                 |
| (Pending Mutasi SQLite/Model)  |              |        (SwiftData / Core Data Engine)             |
+--------------------------------+              +---------------------------------------------------+
       |                                                 ^
  (3) Read Pending Sync                                  | (6) Persist Validated Data
       v                                                 |
+---------------------------------------------------------------------------------------------------+
|                                 SYNC ENGINE & RESILIENT NETWORK ACTOR                             |
|                                                                                                   |
|  +------------------------+   (4) Execute   +--------------------------------------------------+  |
|  | Request Interceptors   | --------------> | URLSession (HTTP/2 / HTTP/3 Pipeline)            |  |
|  | - Auth Token Injector  |                 | - Adaptive Timeout / Backoff Retry Engine        |  |
|  | - Idempotency Key Gen  |                 | - Certificate Pinning Validator                  |  |
|  +------------------------+                 +--------------------------------------------------+  |
|                                                                        |                          |
|                                                                  (5) Raw Response                 |
|                                                                        v                          |
|  +---------------------------------------------------------------------------------------------+  |
|  | Parsing & Deserialization Subsystem: Streaming JSONDecoder + Polymorphic Type Resolver       |  |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
                                                 |
                                           (Remote Wire)
                                                 v
                                    +--------------------------+
                                    |    REMOTE CLOUD API      |
                                    +--------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. URLSession Engine & Socket Abstraction
Di balik `URLSession`, Apple mengoperasikan daemon sistem tingkat rendah (`nsurlsessiond` untuk background tasks) dan *CFNetwork framework*. Saat memanggil `URLSession.data(for: request)` dalam Swift Concurrency:
- **Task Binding:** Pemanggilan memetakan Swift Task ke `CFURLRequest`. Thread pool libdispatch internal kernel mengelola I/O socket tanpa memblokir thread eksekusi Swift Concurrency.
- **Connection Pooling:** `URLSession` memelihara koneksi keep-alive melalui HTTP/1.1 pipelining atau multiplexing HTTP/2 dan HTTP/3 (QUIC) pada soket TCP/UDP yang sama jika remote endpoint mendukungnya.
- **Async Suspension Point:** Task disuspensi (*yielded*) pada boundary kernel I/O, melepaskan CPU thread pool cooperative (`Task.sleep` atau kernel read notification) hingga paket data pertama diterima.

### 2. Decoder Memory Allocation & Type Resolution
Dalam `JSONDecoder`:
- Parser default Apple membaca buffer biner `Data` ke representasi intermediate internal C/C++ (`_JSONDeserializer`).
- Jika payload besar (misal 50MB JSON), ini menghasilkan **dua hingga tiga kali alokasi memori**: buffer raw byte, pohon DOM internal parser C++, dan alokasi instans objek akhir di Swift Heap.
- Untuk efisiensi sistem, struktur model harus didesain `Sendable`, menggunakan value types (`struct`), menghindari properti intermediate yang tidak perlu, dan mendekode field tanggal/desimal menggunakan decoding strategy kustom yang dialokasikan di stack.

### 3. SwiftData / CoreData Engine Storage Layer
`SwiftData` dibangun di atas abstraksi `CoreData` (`NSManagedObjectModel`, `NSManagedObjectContext`, dan `NSPersistentStoreCoordinator`):
- Penyimpanan backing default adalah file database **SQLite** dengan mode **WAL (Write-Ahead Logging)** aktif.
- **Faulting Mechanism:** Instans model yang dibaca dari disk pada awalnya berstatus *fault*. Objek hanya mengalokasikan memori pointer; atributnya tidak dimuat dari SQLite ke heap Swift sampai properti individual tersebut diakses secara eksplisit oleh kode.
- **Context Boundaries:** `ModelContext` (atau `NSManagedObjectContext`) adalah scratchpad in-memory. Operasi baca/tulis di dalam sebuah `ModelActor` berjalan pada queue terisolasi, mencegah *race condition* multithreading terhadap baris SQLite.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### A. Idempotensi pada Jaringan Tidak Andal
Ketika perangkat seluler mengirim request mutasi (misalnya `POST /api/v1/orders`) melalui sinyal LTE yang terputus di tengah jalan, perangkat tidak pernah menerima respons:
- *Apakah request sampai ke server dan diproses?*
- *Ataukah request gagal sebelum mencapai server?*

Jika client langsung mencoba ulang tanpa kontrol, terjadi duplikasi (*double spend* atau *duplicate rows*). Solusinya adalah **Idempotency Key Injection**:
Setiap mutasi lokal di Outbox Queue menghasilkan UUIDv4 deterministik yang disematkan dalam header HTTP:
```http
X-Idempotency-Key: 9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d
```
Server wajib menyimpan kunci ini dalam cache atomic (misalnya Redis) selama window waktu tertentu (misal 24 jam). Jika server menerima kunci yang sama, server mengembalikan snapshot respons sebelumnya tanpa mengeksekusi logika mutasi backend kembali.

### B. Resolusi Konflik: Clock Asynchrony & Vector Clocks
Ketika dua node (Klien Offline dan Server) memutasi entity yang sama secara bersamaan, *system clock* fisik tidak dapat diandalkan karena adanya clock drift antar perangkat seluler (*NTP skew*).
- **LWW (Last-Write-Wins):** Pendekatan sederhana berbasis timestamp ISO-8601. Rentan terhadap kehilangan data jika clock ponsel diubah secara manual oleh pengguna.
- **State-based Reconciliation (Version Vectors):**
  Setiap model entity membawa field `version: Int`.
  1. Klien membaca item versi `1`.
  2. Klien melakukan modifikasi saat offline, menandai target versi `2` dari base `1`.
  3. Saat sinkronisasi, klien mengirim data beserta base version `1`.
  4. Jika database server telah berada pada versi `2` (diubah oleh web client lain), server mendeteksi `Conflict (HTTP 409)` dan mengembalikan payload server terbaru.
  5. Klien menjalankan strategi rekonsiliasi: *Client-Wins*, *Server-Wins*, atau *Three-Way Merge*.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi Network Client resilien modular menggunakan Swift Concurrency murni tanpa dependency pihak ketiga:

```swift
import Foundation

// MARK: - HTTP Definitions

public enum HTTPMethod: String, Sendable {
    case get = "GET"
    case post = "POST"
    case put = "PUT"
    case delete = "DELETE"
}

public protocol APIEndpoint: Sendable {
    var baseURL: URL { get }
    var path: String { get }
    var method: HTTPMethod { get }
    var headers: [String: String]? { get }
    var body: Data? { get }
}

public enum NetworkError: Error, Sendable, LocalizedError {
    case invalidURL
    case badServerResponse(statusCode: Int, data: Data)
    case decodingFailed(String)
    case maxRetryExceeded(Error)
    case cancelled

    public var errorDescription: String? {
        switch self {
        case .invalidURL: return "Target URL parsing failed."
        case .badServerResponse(let code, _): return "Server responded with status code: \(code)."
        case .decodingFailed(let desc): return "Serialization failure: \(desc)."
        case .maxRetryExceeded(let lastErr): return "Retry policy exhausted. Last error: \(lastErr.localizedDescription)."
        case .cancelled: return "Task cancelled explicitly."
        }
    }
}

// MARK: - Resilient Network Client Actor

public actor ResilientNetworkClient {
    private let session: URLSession
    private let jsonDecoder: JSONDecoder

    public init(session: URLSession = .shared) {
        self.session = session
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        self.jsonDecoder = decoder
    }

    public func execute<T: Decodable & Sendable>(
        endpoint: APIEndpoint,
        maxRetries: Int = 3,
        baseBackoffSeconds: Double = 1.0
    ) async throws -> T {
        var lastCapturedError: Error?
        var currentAttempt = 0

        while currentAttempt <= maxRetries {
            // Periksa pembatalan Swift Task kooperatif
            try Task.checkCancellation()

            do {
                let request = try self.buildURLRequest(from: endpoint)
                let (data, response) = try await session.data(for: request)

                guard let httpResponse = response as? HTTPURLResponse else {
                    throw NetworkError.badServerResponse(statusCode: -1, data: data)
                }

                // Tangani Server Errors (5xx) dengan Retry
                if (500...599).contains(httpResponse.statusCode) {
                    throw NetworkError.badServerResponse(statusCode: httpResponse.statusCode, data: data)
                }

                guard (200...299).contains(httpResponse.statusCode) else {
                    throw NetworkError.badServerResponse(statusCode: httpResponse.statusCode, data: data)
                }

                return try self.jsonDecoder.decode(T.self, from: data)

            } catch is CancellationError {
                throw NetworkError.cancelled
            } catch {
                lastCapturedError = error
                currentAttempt += 1

                if currentAttempt > maxRetries {
                    break
                }

                // Kalkulasi Exponential Backoff dengan Jitter
                let backoffInterval = (pow(2.0, Double(currentAttempt - 1)) * baseBackoffSeconds) + Double.random(in: 0...0.5)
                
                // Suspensi non-blocking kooperatif
                try await Task.sleep(nanoseconds: UInt64(backoffInterval * 1_000_000_000))
            }
        }

        throw NetworkError.maxRetryExceeded(lastCapturedError ?? NetworkError.badServerResponse(statusCode: 500, data: Data()))
    }

    private func buildURLRequest(from endpoint: APIEndpoint) throws -> URLRequest {
        guard let url = URL(string: endpoint.path, relativeTo: endpoint.baseURL) else {
            throw NetworkError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = endpoint.method.rawValue
        request.httpBody = endpoint.body

        // Set default application/json headers
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if endpoint.body != nil {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }

        endpoint.headers?.forEach { key, value in
            request.setValue(value, forHTTPHeaderField: key)
        }

        return request
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Telaah Arsitektural `ResilientNetworkClient`

* **Baris 29:** `public actor ResilientNetworkClient`
  Mendeklarasikan client sebagai Swift `actor`. Semua internal state (`session`, `jsonDecoder`) terisolasi dari *data race*. Meskipun banyak thread/task memanggil `execute`, status internal runtime terjamin aman secara konkuren tanpa primitive locking manual (`NSLock`/`os_unfair_lock`).
* **Baris 48:** `try Task.checkCancellation()`
  Mengecek status pembatalan Task sebelum mencoba request baru atau memulai iterasi retry. Ini mencegah eksekusi operasi HTTP berlebih jika pengguna sudah menavigasi keluar dari layar UI (View ditutup).
* **Baris 51:** `let (data, response) = try await session.data(for: request)`
  Suspension point native Swift Concurrency. Mengeksekusi transfer jaringan secara asinkron tanpa memblokir thread eksekusi caller context.
* **Baris 58:** `if (500...599).contains(httpResponse.statusCode)`
  Mengklasifikasikan respons 5xx (*internal server errors*, *bad gateways*) sebagai transient failure yang layak di-retry. Status 4xx (*client errors* seperti 400 Bad Request atau 401 Unauthorized) **tidak boleh** di-retry secara membabi buta tanpa intervensi.
* **Baris 72:** `let backoffInterval = (pow(2.0, Double(currentAttempt - 1)) * baseBackoffSeconds) + Double.random(in: 0...0.5)`
  Rumus Exponential Backoff standar industri: $2^{(\text{attempt}-1)} \times \text{base} + \text{jitter}$. Jitter acak mencegah fenomena *Thundering Herd Problem*, di mana ribuan instance klien seluler membombardir server pada milidetik yang identik setelah pulih dari outage.
* **Baris 75:** `try await Task.sleep(nanoseconds: UInt64(backoffInterval * 1_000_000_000))`
  Mekanisme suspensi non-blocking. Thread sistem dilepaskan untuk mengeksekusi beban kerja UI atau komputasi lain selama jeda backoff.

---

## SEKSI 09 — STUDI KASUS NYATA

### Enterprise Scenario: "Field Logistics & Inspection Engine"

Sebuah perusahaan logistik skala enterprise mengirim 5.000 surveyor ke area pelosok, bunker bawah tanah, dan pelabuhan kargo tanpa konektivitas sinyal (zona zero-connectivity). 

**Masalah Kritis:**
1. Surveyor harus mampu membuat form inspeksi aset kontainer bernilai tinggi, memodifikasi status kerusakan, dan mencatat waktu tanpa hambatan UI.
2. Saat berpindah dari area blank-spot ke jangkauan Wi-Fi armada truk, ratusan data inspeksi yang terpendam harus disinkronisasikan ke distributed backend (PostgreSQL Cluster via API Gateway).
3. Jika dua surveyor mengubah log inventaris barang yang sama dari tablet berbeda dalam kondisi offline, data **tidak boleh terhapus secara destruktif**. Sistem harus melakukan rekonsiliasi state berbasis *Version Vector* serta *Outbox Processing Pattern* yang persisten terhadap kemungkinan aplikasi di-kill paksa oleh OS (*crash-safe* & *reboot-proof*).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Implementasi berikut menggunakan engine **SwiftData** modern dengan pemisahan konkurensi berbasis **ModelActor** terisolasi, Outbox Queue, dan mekanisme idempotensi:

```swift
import Foundation
import SwiftData

// MARK: - 1. Database Entities (SwiftData Schema)

@Model
public final class InspectionRecord {
    @Attribute(.unique) public var id: UUID
    public var assetTag: String
    public var inspectorNotes: String
    public var statusRaw: String
    public var version: Int
    public var isDirtyLocally: Bool
    public var lastModifiedAt: Date

    public init(
        id: UUID = UUID(),
        assetTag: String,
        inspectorNotes: String,
        statusRaw: String,
        version: Int = 1,
        isDirtyLocally: Bool = false,
        lastModifiedAt: Date = Date()
    ) {
        self.id = id
        self.assetTag = assetTag
        self.inspectorNotes = inspectorNotes
        self.statusRaw = statusRaw
        self.version = version
        self.isDirtyLocally = isDirtyLocally
        self.lastModifiedAt = lastModifiedAt
    }
}

@Model
public final class OutboxMutationLog {
    @Attribute(.unique) public var mutationId: UUID
    public var entityId: UUID
    public var actionRaw: String // "CREATE", "UPDATE", "DELETE"
    public var payload: Data
    public var createdAt: Date
    public var retryCount: Int

    public init(
        mutationId: UUID = UUID(),
        entityId: UUID,
        action: String,
        payload: Data,
        createdAt: Date = Date(),
        retryCount: Int = 0
    ) {
        self.mutationId = mutationId
        self.entityId = entityId
        self.actionRaw = action
        self.payload = payload
        self.createdAt = createdAt
        self.retryCount = retryCount
    }
}

// MARK: - 2. Transfer Objects (DTO)

public struct InspectionDTO: Codable, Sendable {
    public let id: UUID
    public let assetTag: String
    public let inspectorNotes: String
    public let status: String
    public let version: Int
    public let lastModifiedAt: Date
}

// MARK: - 3. Isolated Background Storage Actor

@ModelActor
public actor InspectionStorageActor {
    public func fetchAllInspections() throws -> [InspectionDTO] {
        let descriptor = FetchDescriptor<InspectionRecord>(sortBy: [SortDescriptor(\.lastModifiedAt, order: .reverse)])
        let records = try modelContext.fetch(descriptor)
        return records.map {
            InspectionDTO(
                id: $0.id,
                assetTag: $0.assetTag,
                inspectorNotes: $0.inspectorNotes,
                status: $0.statusRaw,
                version: $0.version,
                lastModifiedAt: $0.lastModifiedAt
            )
        }
    }

    public func saveOptimisticMutation(dto: InspectionDTO, action: String) throws {
        let targetId = dto.id
        let descriptor = FetchDescriptor<InspectionRecord>(predicate: #Predicate { $0.id == targetId })
        let existing = try modelContext.fetch(descriptor).first

        if let existing = existing {
            existing.assetTag = dto.assetTag
            existing.inspectorNotes = dto.inspectorNotes
            existing.statusRaw = dto.status
            existing.version = dto.version + 1
            existing.isDirtyLocally = true
            existing.lastModifiedAt = Date()
        } else {
            let newRecord = InspectionRecord(
                id: dto.id,
                assetTag: dto.assetTag,
                inspectorNotes: dto.inspectorNotes,
                statusRaw: dto.status,
                version: 1,
                isDirtyLocally: true,
                lastModifiedAt: Date()
            )
            modelContext.insert(newRecord)
        }

        // Tulis ke Outbox Mutation Log secara atomic dalam transaksi context yang sama
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let payloadData = try encoder.encode(dto)

        let outboxEntry = OutboxMutationLog(
            entityId: dto.id,
            action: action,
            payload: payloadData
        )
        modelContext.insert(outboxEntry)

        try modelContext.save()
    }

    public func fetchPendingOutboxMutations() throws -> [OutboxMutationLog] {
        var descriptor = FetchDescriptor<OutboxMutationLog>(sortBy: [SortDescriptor(\.createdAt, order: .forward)])
        descriptor.fetchLimit = 50 // Batasi batch size
        return try modelContext.fetch(descriptor)
    }

    public func resolveOutboxSuccess(mutationId: UUID, acknowledgedVersion: Int) throws {
        // Hapus Outbox Entry
        let outboxPredicate = #Predicate<OutboxMutationLog> { $0.mutationId == mutationId }
        let outboxLogs = try modelContext.fetch(FetchDescriptor(predicate: outboxPredicate))
        guard let log = outboxLogs.first else { return }

        let entityId = log.entityId
        modelContext.delete(log)

        // Bersihkan status Dirty pada entitas
        let entityPredicate = #Predicate<InspectionRecord> { $0.id == entityId }
        if let entity = try modelContext.fetch(FetchDescriptor(predicate: entityPredicate)).first {
            entity.isDirtyLocally = false
            entity.version = acknowledgedVersion
        }

        try modelContext.save()
    }

    public func applyRemoteUpdates(remoteEntities: [InspectionDTO]) throws {
        for dto in remoteEntities {
            let entityId = dto.id
            let descriptor = FetchDescriptor<InspectionRecord>(predicate: #Predicate { $0.id == entityId })
            let localMatch = try modelContext.fetch(descriptor).first

            if let local = localMatch {
                // Logika Resolusi Konflik: Abaikan remote jika lokal memiliki mutasi kotor (Local Pending Outbox Prioritized)
                // Kecuali remote version melampaui local version sebesar > 1 (Three-Way Split)
                if !local.isDirtyLocally {
                    local.assetTag = dto.assetTag
                    local.inspectorNotes = dto.inspectorNotes
                    local.statusRaw = dto.status
                    local.version = dto.version
                    local.lastModifiedAt = dto.lastModifiedAt
                }
            } else {
                let fresh = InspectionRecord(
                    id: dto.id,
                    assetTag: dto.assetTag,
                    inspectorNotes: dto.inspectorNotes,
                    statusRaw: dto.status,
                    version: dto.version,
                    isDirtyLocally: false,
                    lastModifiedAt: dto.lastModifiedAt
                )
                modelContext.insert(fresh)
            }
        }
        try modelContext.save()
    }
}

// MARK: - 4. Endpoint Definitions

public struct PushInspectionEndpoint: APIEndpoint {
    public let baseURL: URL
    public var path: String { "/api/v1/inspections/sync" }
    public var method: HTTPMethod { .post }
    public var headers: [String: String]?
    public var body: Data?

    public init(baseURL: URL, idempotencyKey: UUID, payload: Data) {
        self.baseURL = baseURL
        self.headers = [
            "X-Idempotency-Key": idempotencyKey.uuidString
        ]
        self.body = payload
    }
}

public struct RemoteSyncResponse: Codable, Sendable {
    public let status: String
    public let acknowledgedVersion: Int
}

// MARK: - 5. Bi-Directional Offline Sync Engine

public final class OfflineSyncCoordinator: Sendable {
    private let storage: InspectionStorageActor
    private let network: ResilientNetworkClient
    private let remoteBaseURL: URL

    public init(
        storage: InspectionStorageActor,
        network: ResilientNetworkClient,
        remoteBaseURL: URL
    ) {
        self.storage = storage
        self.network = network
        self.remoteBaseURL = remoteBaseURL
    }

    public func processOutboxQueue() async throws {
        let pendingQueue = try await storage.fetchPendingOutboxMutations()

        for mutation in pendingQueue {
            let endpoint = PushInspectionEndpoint(
                baseURL: remoteBaseURL,
                idempotencyKey: mutation.mutationId,
                payload: mutation.payload
            )

            do {
                let response: RemoteSyncResponse = try await network.execute(endpoint: endpoint, maxRetries: 3)
                // Tandai sukses & rekonsiliasikan status version
                try await storage.resolveOutboxSuccess(
                    mutationId: mutation.mutationId,
                    acknowledgedVersion: response.acknowledgedVersion
                )
            } catch let NetworkError.badServerResponse(statusCode, _) where statusCode == 409 {
                // HTTP 409 Conflict: Logika pemulihan rekonsiliasi manual
                // Pada skenario enterprise: Tandai item sebagai 'conflict_requires_manual_merge'
                print("[SyncEngine] Terjadi konflik versi pada entitas: \(mutation.entityId). Diperlukan rekonsiliasi server.")
                break
            } catch {
                print("[SyncEngine] Gagal mengirim antrean mutasi: \(mutation.mutationId). Error: \(error.localizedDescription)")
                // Hentikan pemrosesan batch untuk menjaga kausalitas operasi sequential (FIFO ordering)
                break
            }
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

Di bawah ini adalah analisis mendalam mengenai opsi arsitektural persistence pada ekosistem platform Apple:

| Kriteria Dimensi | SwiftData (iOS 17+) | Raw Core Data (NSPersistentContainer) | SQLite Murni / GRDB.swift | Realm Mobile Database |
| :--- | :--- | :--- | :--- | :--- |
| **Paradigma Bahasa** | Native Swift Macro (`@Model`), Swift Concurrency safe. | Objective-C legacy bridge, KVC/KVO, verbose. | Raw SQL / Typed Swift Builders via Protocol. | Object-Oriented C++ Core Engine via Realm Wrapper. |
| **Isolasi Concurrency** | Terintegrasi dengan `@ModelActor` native. | Memerlukan disiplin manual `performBackgroundTask`. | Serial Dispatch Queues atau Read-Write Pool lock. | Thread-confined object pointer; fatal crash jika lintas thread. |
| **Overhead Memori** | Menengah (Auto-faulting, memory footprint model Swift). | Rendah hingga Menengah (Faulting sangat teroptimasi). | **Sangat Rendah** (Bebas dari runtime class metadata heavy tracking). | Menengah hingga Tinggi (C++ internal backing cache per thread). |
| **Kompleksitas Query** | Terbatas pada Predicate Macro (Compile-time checked, subset terbatas). | Kompleks via `NSPredicate` (String based, runtime evaluation). | **Tak Terbatas** (Window functions, CTE, Index hints, FTS5). | Custom Query Language (NSPredicate-like). |
| **Ukuran Binary App** | 0 MB (Bawaan iOS SDK). | 0 MB (Bawaan iOS SDK). | Sangat kecil (GRDB ~1-2 MB). | Besar (+15-30 MB Dynamic Framework overhead). |
| **Rekomendasi Enterprise**| Proyek baru yang menargetkan spesifik iOS 17+. | Legacy enterprise apps dengan performa batch mutasi masif. | Aplikasi data-intensive (Fintech, GIS, Analytics, Chat DB). | Aplikasi rapid-prototyping multiplatform (Android/iOS parity). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The ModelActor Crossing Boundary Crash
* **Kegagalan:** Mencoba mengoper instans `@Model` (misal `InspectionRecord`) langsung keluar dari context `InspectionStorageActor` ke UI Main Thread.
* **Mekanisme Failure:** `NSManagedObject` / `SwiftData` instances tidak bersifat thread-safe. Mengakses properti objek yang dialokasikan di context thread/actor berbeda akan memicu *data race runtime violation* atau `EXC_BAD_ACCESS`.
* **Mitigasi:** Selalu petakan (*map*) entity database internal ke struktur Transfer Object bebas (`Sendable struct`, misalnya `InspectionDTO`) sebelum menyeberangi batasan aktor (*actor boundaries*).

### 2. Zombie Outbox Mutations (Indefinite Retries)
* **Kegagalan:** Payload mutasi mengandung malformed logic yang selalu memicu respons `HTTP 400 Bad Request` atau `422 Unprocessable Entity` dari server backend.
* **Mekanisme Failure:** Outbox queue memblokir antrean secara permanen (*head-of-line blocking*), terus-menerus mencoba ulang request yang secara fungsional pasti ditolak, menguras baterai dan kuota seluler klien.
* **Mitigasi:** Klasifikasikan status HTTP. Bedakan antara *Transient Failure* (502, 503, 504, Socket Timeout -> **Boleh Retry**) dan *Terminal Business Failure* (400, 401, 403, 422 -> **Pindahkan ke Dead-Letter Table / Outbox Error Table** dan tampilkan notifikasi kepada pengguna).

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Double JSON Decoding Memory Spikes
```swift
// BURUK: Membaca string mentah, mengubah ke Data, lalu parse berulang
let jsonString = String(data: rawData, encoding: .utf8)!
let finalData = jsonString.data(using: .utf8)!
let result = try JSONDecoder().decode(Model.self, from: finalData)
```
*Mengapa Salah:* Ini menduplikasi alokasi memori berukuran besar tiga kali di heap. Pada data JSON respons 30MB, sistem mobile dapat mengalami OOM (*Out-Of-Memory termination*).
```swift
// BENAR: Parsing zero-copy stream langsung dari buffer URLSession
let (bytes, response) = try await session.bytes(for: request)
// Atau decode langsung dari `Data` tanpa konversi intermediate String
let result = try JSONDecoder().decode(Model.self, from: data)
```

### 2. Mengabaikan Cancellation pada Long-Running Requests
```swift
// BURUK: Mengabaikan status pembatalan Task
func loadHeavyData() async {
    let result = try? await networkClient.fetchData()
    self.renderUI(result)
}
```
*Mengapa Salah:* Jika pengguna meninggalkan ViewController sebelum data tiba, transfer jaringan dan decoding tetap berjalan di latar belakang, membuang resource komputasi dan memicu kebocoran dependensi.
```swift
// BENAR: Monitor pembatalan secara kooperatif
func loadHeavyData() async {
    do {
        try Task.checkCancellation()
        let result = try await networkClient.fetchData()
        try Task.checkCancellation()
        self.renderUI(result)
    } catch is CancellationError {
        // Logica cleanup resource
    } catch {
        self.handleError(error)
    }
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Transactional Outbox Consistency:** Operasi penulisan entity lokal dan registrasi mutasi Outbox **wajib** berada di dalam satu transaksi atomic database lokal yang sama (`modelContext.save()`). Jangan pernah memisahkan penyimpanan mutasi outbox ke thread pool terpisah dari entity aslinya.
2. **Defensive API Schema Mapping:** Jangan gunakan tipe data opsional secara membabi buta, tetapi hindari pula pemetaan `!` (*force unwrap*). Selalu tentukan default value yang aman atau gunakan decoding wrapper kustom (`SafeArrayDecodingContainer`) agar kegagalan deserialisasi pada satu item dari 10.000 list array tidak menggagalkan decoding 9.999 item lainnya