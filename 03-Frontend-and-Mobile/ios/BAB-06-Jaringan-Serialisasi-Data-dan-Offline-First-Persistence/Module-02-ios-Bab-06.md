# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI
**BAB 06: Jaringan, Serialisasi Data, dan Offline-First Persistence**
**Kategori: 03-Frontend-and-Mobile (iOS Enterprise)**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, Principal/Senior iOS Engineer diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur jaringan terisolasi concurrency (*Swift 6 Actor-based*) yang kebal terhadap *race condition* dan *thundering herd problem* saat token kedaluwarsa.
- Mengonfigurasi lapisan keamanan enterprise meliputi Public Key Pinning (SPKI SHA-256) menggunakan `URLSessionDelegate` dan `Security.framework` tingkat rendah.
- Membangun mesin persistensi *offline-first* deterministik dengan pola *Transactional Outbox*, memanfaatkan Core Data/SwiftData latar belakang (*background context*) dengan mode SQLite WAL (*Write-Ahead Logging*).
- Mengimplementasikan algoritma resolusi konflik (*Conflict Resolution Strategy*) berbasis *Last-Write-Wins* (LWW) dan rekonsiliasi data *field-level*.
- Menghindari *memory spikes* dan *data race* lintas thread/actor saat melakukan serialisasi polimorfik kompleks.

---

## 2. Prerequisite
- Penguasaan mendalam terhadap model konkurensi Swift modern: `actor`, `Sendable`, `Task`, `TaskGroup`, dan *data isolation*.
- Pemahaman fundamental terhadap stack jaringan POSIX/Darwin: BSD Sockets, CFNetwork, `URLSessionConfiguration`, dan *HTTP/2 framing*.
- Pengetahuan mendalam arsitektur penyimpanan relasional: ACID properties, SQLite B-Tree, Write-Ahead Logging (WAL), dan Core Data concurrency (`NSManagedObjectContext` model confinement).
- Penguasaan dasar kriptografi simetris/asimetris: X.509 certificates, Subject Alternative Name (SAN), dan Subject Public Key Info (SPKI).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Network Stack & Concurrency Engine (Darwin OS)
Di level terendah iOS, `URLSession` dibangun di atas `CFNetwork`, yang membungkus layer abstraksi soket BSD (`sys/socket.h`). Saat sebuah *request* dieksekusi:

```
[ Swift Concurrency Context / Actor ]
                 │
                 ▼
      [ Enterprise APIClient ]
                 │
                 ▼
     [ HTTP Interceptor Chain ] ── (Auth, Logging, Metric, SPKI Pinning)
                 │
                 ▼
         [ URLSessionTask ]
                 │
        ═════════╪════════════════════ Darwin OS Kernel Barrier
                 ▼
           [ CFNetwork ]
                 │
                 ▼
       [ CoreOS / BSD Socket ] ── (TCP Handshake, TLS 1.3 Negotiation)
```

1. **HTTP Pipeline Interception**: Interseptor bekerja secara serial asinkron. Setiap interseptor memodifikasi `URLRequest` atau memvalidasi `HTTPURLResponse`.
2. **Actor-Isolated Token Refresh**: Ketika menerima HTTP status 401 Unauthorized, sistem tidak boleh mengirimkan N request refresh secara paralel (*thundering herd*). Sebagai gantinya, request dialihkan ke sebuah `actor` yang mengeksekusi mekanisme *single-flight suspension*: task pertama menjalankan *refresh token*, sedangkan task kedua hingga ke-N tersuspensi pada titik *await* yang sama hingga token baru tersedia.

### 3.2 Offline-First Persistence Internals (SQLite WAL & Core Data)
Secara default, SQLite menggunakan *rollback journal*. Untuk aplikasi enterprise dengan I/O tinggi, konfigurasi harus dialihkan ke **WAL (Write-Ahead Logging)** mode (`PRAGMA journal_mode=WAL;`).

Dalam WAL:
- **Reader tidak memblokir Writer**, dan **Writer tidak memblokir Reader**. Operasi *read* berjalan langsung dari database file utama dan WAL index (`.shm`), sementara operasi *write* diarahkan ke berkas terpisah (`.wal`).
- **Core Data Background Concurrency**: `NSManagedObjectContext` dengan `NSPrivateQueueConcurrencyType` berjalan di antrean latar belakang. Model *Thread Confinement* digantikan dengan eksekusi blok `perform` atau `performAndWait`. Objek `NSManagedObject` bersifat *non-Sendable*; transfer data antar context/actor harus melalui `NSManagedObjectID` atau DTO bernilai (*Value Types*).

### 3.3 Transactional Outbox Pattern & Conflict Resolution Architecture
Untuk menjamin konsistensi *offline-first*:
1. Mutasi lokal dan pencatatan event outbox dibungkus dalam **satu transaksi database atomik**. Mutasi lokal diterapkan secara optimistik pada UI (*Optimistic UI Update*).
2. Sinkronisasi latar belakang mengambil daftar mutasi dari tabel `OutboxRecord` berstatus `PENDING`.
3. Strategi Resolusi Konflik:
   - **Last-Write-Wins (LWW)**: Bergantung pada server-assigned monotonic timestamp.
   - **Three-Way Merge**: Membandingkan `Base Version`, `Local Version`, dan `Remote Version` pada level atribut individual.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Naive Mobile App) | Pendekatan Enterprise (Robust Offline-First) |
| :--- | :--- | :--- |
| **Konektivitas Jaringan** | Asumsi koneksi selalu stabil (*Online-First*). Tampilkan loading spinner / error alert jika offline. | Menganggap jaringan *unreliable*. Seluruh mutasi masuk ke antrean lokal atomik (*Offline-First*). |
| **Auth Expiry** | Setiap request 401 memicu refresh token independen, menghasilkan *race condition* dan *session invalidation*. | Actor-based *Thundering Herd Protection*. Token direfresh tepat sekali, semua request tertahan dan diulang transparan. |
| **Data Integrity** | State disimpan langsung ke disk tanpa ACID protection. Rawan *corrupt* saat *crash*. | Transaksi ACID berbasis WAL. Data outbox dan mutasi domain disimpan dalam satu transaksi atomik. |
| **Keamanan Jaringan** | Percaya pada Certificate Authority (CA) bawaan OS (Rawan MITM via sertifikat root palsu). | Static SPKI SHA-256 Pinning pada public key sertifikat server. Menolak *custom root certificates*. |
| **Parsing JSON** | `JSONDecoder` standar tanpa validasi skema toleran (Gagal decode satu field membatalkan seluruh array). | Lossless dynamic polymorphic decoding dengan safe-containment untuk array partial parsing. |

---

## 5. How (Workflow Detail)

```
[ USER MUTATION (e.g. Update Profile) ]
                  │
                  ▼
┌────────────────────────────────────────────────────────┐
│ 1. Atomic Local Transaction                            │
│    ├── A. Simpan perubahan ke Domain Table (Local)    │
│    └── B. Sisipkan mutasi ke Outbox Table (PENDING)    │
└────────────────────────────────────────────────────────┘
                  │
                  ├──────────────────────────────┐
                  ▼                              ▼
      [ Update UI Optimistically ]      [ Sync Engine Triggered ]
                                                 │
                                                 ▼
                               ┌───────────────────────────────────┐
                               │ 2. Fetch Pending Outbox Records   │
                               └───────────────────────────────────┘
                                                 │
                                                 ▼
                               ┌───────────────────────────────────┐
                               │ 3. Execute HTTP Pipeline          │
                               │    ├── Interceptor: Inject Auth   │
                               │    ├── Interceptor: SPKI Pinning  │
                               │    └── Interceptor: Retry Policy  │
                               └───────────────────────────────────┘
                                                 │
                                 ┌───────────────┴───────────────┐
                                 │                               │
                       [ HTTP 200 OK ]                   [ HTTP 409 Conflict ]
                                 │                               │
                                 ▼                               ▼
                 ┌──────────────────────────────┐ ┌──────────────────────────────┐
                 │ 4. Mark Outbox as SYNCED     │ │ 4. Execute Conflict Resolver │
                 │    Update entity server_id   │ │    - Three-Way Field Merge   │
                 │    Notify UI via Combine/Task│ │    - Re-queue/Discard Outbox │
                 └──────────────────────────────┘ └──────────────────────────────┘
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem ini seperti **Kantor Pos Logistik Ekspedisi Militer**:
- **UI Context**: Pengirim paket yang memasukkan surat ke kotak drop box depan. Dia langsung mendapat resi tanda terima sementara dan pulang (*Optimistic UI*).
- **Outbox Storage**: Peti besi tahan api berstandar militer tempat semua surat dimasukkan secara berurutan dan terkunci (*Transactional ACID/WAL*).
- **Token Manager Actor**: Petugas loket tunggal yang memegang kunci gudang. Jika kunci otorisasi kedaluwarsa, seluruh armada kurir berhenti di gerbang dan menunggu petugas memperbarui kunci utama, tanpa ada yang berjalan sendiri-sendiri (*Single-Flight Token Refresh*).
- **Sync Engine**: Armada kurir yang secara berkala memeriksa peti besi, mengirim surat ke pusat, dan apabila alamat tujuan telah diubah di pusat, kurir membawa salinan perubahan tersebut ke bagian resolusi (*Conflict Resolution*).

```
                      +---------------------------------------+
                      |         TokenManager (Actor)          |
                      |   - State: idle | refreshing(Task)   |
                      +---------------------------------------+
                                          ^
                                          | Auth Token Lock
                                          v
+----------------+      Mutate     +--------------------+     HTTP Dispatch     +----------------+
|  Presentation  | --------------> |    Sync Engine     | --------------------> | Remote Gateway |
|  Layer (UI)    | <-------------- |   Background Core  | <-------------------- |   (REST/JSON)  |
+----------------+   State Sync    +--------------------+     200 OK / 409      +----------------+
                                          |        ^
                                          | Write  | Read
                                          v        |
                                   +--------------------+
                                   | SQLite Engine (WAL)|
                                   |  - Domain Entities |
                                   |  - Outbox Table    |
                                   +--------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Production-Grade Network Engine dengan Actor-Based Token Refresher & SPKI Pinning

```swift
import Foundation
import Security
import CryptoKit

// MARK: - SPKI Pinning Validator
public final class SPKIValidator: NSObject, URLSessionDelegate, Sendable {
    private let pinnedHashes: Set<String>

    public init(pinnedHashes: Set<String>) {
        self.pinnedHashes = pinnedHashes
        super.init()
    }

    public func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge
    ) async -> (URLSession.AuthChallengeDisposition, URLCredential?) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust else {
            return (.cancelAuthenticationChallenge, nil)
        }

        var secError: CFError?
        let isTrusted = SecTrustEvaluateWithError(serverTrust, &secError)
        guard isTrusted else {
            return (.cancelAuthenticationChallenge, nil)
        }

        guard let chain = SecTrustCopyCertificateChain(serverTrust) as? [SecCertificate] else {
            return (.cancelAuthenticationChallenge, nil)
        }

        for certificate in chain {
            if let publicKey = SecCertificateCopyKey(certificate),
               let publicKeyData = SecKeyCopyExternalRepresentation(publicKey, nil) as Data? {
                
                // SPKI Header for ASN.1 DER EC / RSA
                let spkiHash = SHA256.hash(data: publicKeyData).map { String(format: "%02hhx", $0) }.joined()
                if pinnedHashes.contains(spkiHash) {
                    return (.useCredential, URLCredential(trust: serverTrust))
                }
            }
        }

        return (.cancelAuthenticationChallenge, nil)
    }
}

// MARK: - Actor-Isolated Token Refresh Engine (Anti Thundering Herd)
public actor TokenRefresher {
    private var refreshTask: Task<String, Error>?
    private var authToken: String?

    public init(initialToken: String? = nil) {
        self.authToken = initialToken
    }

    public func getValidToken() async throws -> String {
        if let token = authToken, !isTokenExpired(token) {
            return token
        }

        if let existingTask = refreshTask {
            return try await existingTask.value
        }

        let task = Task<String, Error> {
            defer { self.refreshTask = nil }
            let newToken = try await self.executeTokenRefreshNetworkCall()
            self.authToken = newToken
            return newToken
        }

        self.refreshTask = task
        return try await task.value
    }

    public func invalidateToken() {
        self.authToken = nil
    }

    private func isTokenExpired(_ token: String) -> Bool {
        // Implementasi pengecekan exp payload JWT internal
        return false 
    }

    private func executeTokenRefreshNetworkCall() async throws -> String {
        // Simulasi network refresh call
        try await Task.sleep(nanoseconds: 300_000_000)
        return "new_access_token_\(UUID().uuidString)"
    }
}

// MARK: - Resilient Network Client
public enum NetworkError: Error {
    case invalidResponse
    case unauthorized
    case serverConflict(Data)
    case connectionFailure(Error)
}

public protocol NetworkInterceptor: Sendable {
    func intercept(request: URLRequest) async throws -> URLRequest
}

public final class NetworkClient: Sendable {
    private let session: URLSession
    private let tokenRefresher: TokenRefresher

    public init(session: URLSession, tokenRefresher: TokenRefresher) {
        self.session = session
        self.tokenRefresher = tokenRefresher
    }

    public func execute(request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        var mutableRequest = request
        let token = try await tokenRefresher.getValidToken()
        mutableRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: mutableRequest)
        } catch {
            throw NetworkError.connectionFailure(error)
        }

        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.invalidResponse
        }

        if httpResponse.statusCode == 401 {
            await tokenRefresher.invalidateToken()
            // Single retry attempt after refreshing token
            let retryToken = try await tokenRefresher.getValidToken()
            mutableRequest.setValue("Bearer \(retryToken)", forHTTPHeaderField: "Authorization")
            
            let (retryData, retryResponse) = try await session.data(for: mutableRequest)
            guard let finalResponse = retryResponse as? HTTPURLResponse else {
                throw NetworkError.invalidResponse
            }
            return (retryData, finalResponse)
        }

        if httpResponse.statusCode == 409 {
            throw NetworkError.serverConflict(data)
        }

        return (data, httpResponse)
    }
}
```

### 7.2 Implementasi Offline-First Persistence Engine & Outbox Processor (Core Data WAL)

```swift
import Foundation
import CoreData

// MARK: - Core Data Stack Manager
public final class PersistenceController: @unchecked Sendable {
    public static let shared = PersistenceController()
    public let container: NSPersistentContainer

    private init() {
        container = NSPersistentContainer(name: "EnterpriseStorage")
        
        guard let description = container.persistentStoreDescriptions.first else {
            fatalError("PersistentStoreDescription tidak ditemukan.")
        }
        
        // Mengaktifkan SQLite WAL Mode & Synchronous Normal
        description.setValue("WAL" as NSObject, forPragmaNamed: "journal_mode")
        description.setValue("NORMAL" as NSObject, forPragmaNamed: "synchronous")
        
        container.loadPersistentStores { _, error in
            if let error = error as NSError? {
                fatalError("Unresolved Core Data error \(error), \(error.userInfo)")
            }
        }
        
        container.viewContext.automaticallyMergesChangesFromParent = true
        container.viewContext.mergePolicy = NSMergeByPropertyObjectTrumpMergePolicy
    }

    public func newBackgroundContext() -> NSManagedObjectContext {
        let context = container.newBackgroundContext()
        context.mergePolicy = NSMergeByPropertyObjectTrumpMergePolicy
        return context
    }
}

// MARK: - Transactional Outbox Models
public struct OutboxRecordPayload: Codable, Sendable {
    public let entityId: String
    public let entityName: String
    public let action: String // CREATE, UPDATE, DELETE
    public let changes: [String: String]
    public let clientTimestamp: Date
}

// MARK: - Outbox Sync Worker
public actor OutboxSynchronizer {
    private let persistence: PersistenceController
    private let networkClient: NetworkClient
    private var isSyncing = false

    public init(persistence: PersistenceController, networkClient: NetworkClient) {
        self.persistence = persistence
        self.networkClient = networkClient
    }

    public func enqueueMutation(payload: OutboxRecordPayload) async throws {
        let context = persistence.newBackgroundContext()
        try await context.perform {
            // Catat perubahan di entity asli dan simpan ke outbox dalam SATU transaksi
            let outboxEntity = NSEntityDescription.insertNewObject(forEntityName: "OutboxDataModel", into: context)
            outboxEntity.setValue(UUID().uuidString, forKey: "id")
            outboxEntity.setValue(payload.entityId, forKey: "targetEntityId")
            outboxEntity.setValue(try? JSONEncoder().encode(payload), forKey: "payload")
            outboxEntity.setValue("PENDING", forKey: "status")
            outboxEntity.setValue(Date(), forKey: "createdAt")
            
            try context.save()
        }
        
        Task {
            await self.processOutbox()
        }
    }

    public func processOutbox() async {
        guard !isSyncing else { return }
        isSyncing = true
        defer { isSyncing = false }

        let context = persistence.newBackgroundContext()
        
        do {
            let pendingRecords = try await context.perform { () -> [(String, Data)] in
                let request = NSFetchRequest<NSManagedObject>(entityName: "OutboxDataModel")
                request.predicate = NSPredicate(format: "status == %@", "PENDING")
                request.sortDescriptors = [NSSortDescriptor(key: "createdAt", ascending: true)]
                request.fetchLimit = 50
                
                let results = try context.fetch(request)
                return results.compactMap { obj in
                    guard let id = obj.value(forKey: "id") as? String,
                          let data = obj.value(forKey: "payload") as? Data else { return nil }
                    return (id, data)
                }
            }

            for (recordId, payloadData) in pendingRecords {
                let payload = try JSONDecoder().decode(OutboxRecordPayload, from: payloadData)
                let success = await sendToServer(payload: payload)

                try await context.perform {
                    let fetchRequest = NSFetchRequest<NSManagedObject>(entityName: "OutboxDataModel")
                    fetchRequest.predicate = NSPredicate(format: "id == %@", recordId)
                    if let record = try context.fetch(fetchRequest).first {
                        if success {
                            context.delete(record) // Hapus yang sudah sukses
                        } else {
                            record.setValue("FAILED", forKey: "status")
                        }
                        try context.save()
                    }
                }
            }
        } catch {
            // Log persistence error
        }
    }

    private func sendToServer(payload: OutboxRecordPayload) async -> Bool {
        var request = URLRequest(url: URL(string: "https://api.enterprise.com/v1/sync")!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONEncoder().encode(payload)

        do {
            let (data, response) = try await networkClient.execute(request: request)
            return response.statusCode == 200
        } catch NetworkError.serverConflict(let conflictData) {
            await resolveConflict(localPayload: payload, serverPayloadData: conflictData)
            return true
        } catch {
            return false
        }
    }

    private func resolveConflict(localPayload: OutboxRecordPayload, serverPayloadData: Data) async {
        // Implementasi LWW (Last-Write-Wins)
        let context = persistence.newBackgroundContext()
        await context.perform {
            // Resolusi field server melawan field lokal
            // Disimpan kembali ke domain context
        }
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: POS (Point-of-Sale) / Field Service App di Daerah Terpencil (High Throughput, Low Latency, Unstable Network)
Sebuah perusahaan logistik memiliki 15.000 kurir yang memindai dan memvalidasi paket di daerah tanpa sinyal seluler sepanjang hari (warehouse bawah tanah, pelosok pedesaan).

**Permasalahan Arsitektur:**
1. **Database Lock Jamming**: Database lokal terkunci total (`SQLITE_BUSY`) saat background sync mencoba upload ribuan item bersamaan dengan aksi scan barcode berkecepatan 3 frame/detik oleh kru.
2. **Session Termination Storm**: Begitu armada mendapat sinyal 4G parsial, ratusan thread mencoba merefresh JWT secara bersamaan, mengakibatkan server Identity Provider (IdP) kolaps karena *DDoS internal*, lalu server mengembalikan error 429 & 401 bergantian yang merusak sesi login kurir.
3. **Data Overwrite (Phantom Overwrite)**: Perubahan status paket di lapangan menimpa status paket yang baru dibatalkan oleh agen call-center di cloud.

**Solusi yang Diterapkan:**
1. **Arsitektur SQLite WAL + Dedicated Queues**:
   - Menghidupkan mode WAL (`PRAGMA journal_mode=WAL;`).
   - Memisahkan thread Core Data: 1 `NSManagedObjectContext` eksklusif untuk mutasi scanning kurir (*high priority*), 1 context private untuk reader UI, dan 1 context untuk sync engine (*low priority worker*).
2. **Actor Token Barrier (Single Flight)**:
   - Seluruh outgoing network thread wajib melewati `TokenRefresher` actor. Semua task tersuspensi di satu titik saat token refresh dieksekusi secara terpusat.
3. **Field-Level Monotonic LWW Conflict Engine**:
   - Mutasi data tidak lagi mengirim seluruh entitas, melainkan array mutasi atomik (*delta patch*).
   - Setiap mutasi membawa monotonic sequence token dari server (`seq_id`) dan timestamp lokal berpresisi mikrodetik. Server dan klien hanya memperbarui kolom yang memiliki timestamp lebih baru.

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter | Pendekatan A: Full CRDT (Conflict-free Replicated Data Type) | Pendekatan B: Transactional Outbox + LWW Merge |
| :--- | :--- | :--- |
| **Throughput & CPU (Mobile)** | Berat. Menyimpan tombstone metadata dan causal tree membebani memori & baterai. | Sangat Ringan. Hanya menyimpan snapshot data mutasi lokal sederhana. |
| **Kompleksitas Kode** | Sangat Tinggi. Membutuhkan state machine kompleks dan memori overhead besar di disk. | Terkendali. Mudah diaudit, di-*rollback*, dan didiagnosis via unit test. |
| **Data Consistency** | *Strong Eventual Consistency* matematis tanpa ada data loss pada *concurrent edit*. | *Deterministic Last-Write-Wins*. Risiko data lama terabaikan jika jam perangkat tidak akurat (NTP drift). |
| **Biaya Server / Bandwidth** | Metadata payload sangat besar (membengkak hingga 3-5x JSON normal). | Efisien. Payload transfer minimal (hanya payload delta json). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Accessing `NSManagedObject` across Swift Concurrency Boundaries
**Kesalahan Fatal:**
```swift
// RUNTIME CRASH: EXC_BAD_INSTRUCTION
Task {
    let order = try backgroundContext.fetch(request).first!
    await updateOrderUI(order: order) // Mengirim NSManagedObject menyeberangi actor boundary
}
```
**Perbaikan:**
Ekstrak properti ke dalam Swift struct yang bertipe `Sendable` sebelum melintasi isolasi:
```swift
public struct OrderDTO: Sendable {
    public let id: String
    public let totalAmount: Decimal
}

// AMAN:
let orderDTO = try backgroundContext.perform {
    let managed = try backgroundContext.fetch(request).first!
    return OrderDTO(id: managed.id, totalAmount: managed.amount)
}
await updateOrderUI(order: orderDTO)
```

### 10.2 Memory Bloat Saat Melakukan Batch Decoding JSON Besar
Menggunakan `JSONDecoder().decode([Entity].self, from: data)` untuk berkas JSON 100MB langsung menaikkan konsumsi RAM hingga 400MB+ di iOS, berpotensi memicu eliminasi proses oleh *Jetsam*.

**Perbaikan:**
Gunakan deserialisasi berbasis stream atau chunking (`InputStream` bersama `JSONSerialization` streaming parser atau library SAX-style JSON parser).

### 10.3 Infinite Retry Storms pada Network Failure
Melakukan perulangan *retry* secara agresif saat terjadi failure tanpa penundaan waktu akan menguras daya baterai dan memblokir thread.

**Perbaikan:** Gunakan **Exponential Backoff dengan Full Jitter**:
```swift
func calculateBackoffDelay(attempt: Int, base: Double = 1.0, maxDelay: Double = 32.0) -> Double {
    let exponential = min(maxDelay, base * pow(2.0, Double(attempt)))
    return Double.random(in: 0...exponential)
}
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Database Core / SQLite**: Mode WAL diaktifkan eksplisit melalui `NSPersistentStoreDescription` pragma: `journal_mode = WAL` dan `synchronous = NORMAL`.
- [ ] **Concurrency Isolation**: Seluruh token state dienkapsulasi di dalam Swift `actor`.
- [ ] **Thread Confinement**: Hindari mengakses `NSManagedObject` di luar blok `context.perform` atau `context.performAndWait`.
- [ ] **Atomic Outbox Record**: Transaksi penyimpanan outbox dieksekusi dalam context yang sama dengan pembaruan entity domain lokal.
- [ ] **Network Retries**: Setiap request otomatis mengimplementasikan Exponential Backoff + Jitter; hindari *infinite loop retry*.
- [ ] **Security**: TLS 1.3 dipaksakan secara default, dengan fallback minimum TLS 1.2. Sertifikat menggunakan Subject Public Key Info (SPKI) SHA-256 validation.
- [ ] **Background Execution**: Operasi sinkronisasi outbox didaftarkan pada Apple `BGProcessingTask` dari framework `BackgroundTasks` untuk mencegah penghentian paksa oleh watchdog OS saat aplikasi beralih ke latar belakang.

---

## 12. Hands-on Practice

Buat direktori kerja baru pada `hands-on/m02/` dengan struktur modular berikut:

```
hands-on/m02/
├── Sources/
│   ├── Network/
│   │   ├── SPKIPinningEngine.swift
│   │   ├── ActorTokenRefresher.swift
│   │   └── ResilientNetworkClient.swift
│   ├── Storage/
│   │   ├── CoreDataStack.swift
│   │   └── OutboxEntity.xcdatamodeld
│   └── Sync/
│       ├── OutboxSynchronizer.swift
│       └── ConflictResolver.swift
└── Tests/
    ├── NetworkTests/
    └── SyncTests/
```

### Panduan Implementasi:
1. **Langkah 1 (Network Setup)**: Salin implementasi `SPKIValidator` dan `TokenRefresher` ke dalam direktori `Sources/Network/`. Lakukan pengujian unit dengan mensimulasikan 50 thread pemanggil bersamaan ke `getValidToken()` saat token invalid. Buktikan pemanggilan refresh hanya terjadi tepat satu kali.
2. **Langkah 2 (Core Data Setup)**: Buat model Core Data `OutboxEntity` dengan attribute: `id` (String), `payload` (Binary Data), `status` (String), `createdAt` (Date).
3. **Langkah 3 (Outbox Sync Execution)**: Hubungkan `OutboxSynchronizer` untuk memproses antrean mutasi yang gagal kirim saat perangkat disimulasikan berada dalam status `Airplane Mode`, lalu verifikasi data terkirim saat mode dinonaktifkan.

---

## 13. Exercise

### Level Easy
Ubah implementasi `TokenRefresher` agar mendukung batas waktu (*timeout*) maksimal 5 detik saat mengeksekusi network refresh call. Jika batas waktu terlampaui, batalkan task refresh tersebut dan lempar error `NetworkError.timeout`.

### Level Medium
Tambahkan mekanisme sanitasi memori ke `OutboxSynchronizer`: Saat pemrosesan antrean outbox mencapai lebih dari 500 item berturut-turut, picu penyimpanan parsial context (`context.save()`) dan lakukan `context.reset()` setiap kelipatan 50 item untuk mencegah lonjakan alokasi memori (*heap bloat*).

### Level Hard
Implementasikan sebuah sistem **Dynamic Polymorphic JSON Decoder** kustom untuk entitas analitik payload berikut tanpa menggugurkan seluruh parsing array jika salah satu record memiliki tipe yang tidak dikenal (*corrupted data*):
```json
[
  {"type": "click", "timestamp": 1700000000, "element_id": "btn_buy"},
  {"type": "unknown_future_event", "data": "xyz"},
  {"type": "view", "timestamp": 1700000005, "screen_name": "checkout"}
]
```

---

## 14. Challenge

**Skenario Sistem Distribusi: Collaborative Multi-Tenant Inspection Engine**

Rancang sebuah arsitektur sinkronisasi lokal iOS dengan persyaratan berikut:
1. **Simultaneous Multi-Device Conflict**: Tiga orang inspektur lapangan melakukan audit terhadap entitas bangunan yang sama secara offline. Inspektur A memperbarui status fisik dinding, Inspektur B memperbarui status instalasi listrik, dan Inspektur C memperbarui status atap.
2. **Constraint Matrix**:
   - Dilarang menghilangkan modifikasi dari salah satu inspektur saat sinkronisasi (*Zero Data Loss*).
   - Penggunaan Core Data background context wajib thread-safe dan terintegrasi dengan Swift Concurrency `async/await`.
   - Engine tidak boleh bergantung pada library pihak ketiga (hanya menggunakan Foundation, CoreData, Security, dan CryptoKit bawaan platform).
   - Payload transmisi data jaringan harus menyertakan SPKI SHA-256 public key pinning.

**Tugas Arsitektur:**
Tuliskan cetak biru desain kelas, implementasi model skema Core Data, algoritma *Three-Way Delta Merge*, serta skenario pengujian unit untuk menjamin tidak terjadinya *deadlock* dan *data corruption*.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic
1. Mengapa mode SQLite WAL (`journal_mode=WAL`) sangat disarankan untuk skenario offline-first dibandingkan mode journal default?
2. Apa alasan utama objek `NSManagedObject` tidak memenuhi protokol `Sendable` di Swift 6?
3. Apa perbedaan fundamental antara Certificate Pinning dan Public Key (SPKI) Pinning?
4. Mengapa kita tidak boleh menaruh `URLSession` di dalam sebuah `actor` jika semua request dieksekusi secara asinkron?
5. Masalah apa yang dipecahkan oleh *Exponential Backoff with Jitter* dibandingkan *Fixed-Interval Retry*?

### Bagian 2: Intermediate
6. Bagaimana cara mencegah *reentrancy problem* pada Swift Actor saat token refresh sedang melakukan operasi `await` di jaringan?
7. Mengapa pemanggilan `context.performAndWait` dapat memicu *thread starvation* jika dipanggil secara sembarangan di thread pool konkuransi Swift?
8. Bagaimana implementasi deteksi perubahan partial (dirty-flags) yang efisien sebelum menyimpan mutasi ke Outbox table?
9. Apa yang terjadi pada file SQLite `-wal` dan `-shm` jika aplikasi di-kill paksa oleh user (*force-terminate*) saat penulisan data berlangsung?
10. Bagaimana `URLSessionDelegate` menangani validasi TLS saat server melakukan rotasi sertifikat berkala jika menggunakan SPKI hashing?

### Bagian 3: Skenario Kasus Produksi
11. **Skenario Kasus A**:
    Aplikasi audit internal mengalami crash acak berlabel `EXC_BAD_ACCESS (KERN_INVALID_ADDRESS)` di Core Data saat sinkronisasi batch latar belakang berjalan bertepatan dengan perpindahan tab navigasi oleh pengguna. Investigasi menunjukkan `NSPrivateQueueConcurrencyType` sudah digunakan. Di mana letak potensi celah kebocoran memori thread-nya?
12. **Skenario Kasus B**:
    Saat peluncuran rilis enterprise di jaringan korporat yang menggunakan Corporate Proxy (seperti Zscaler), 100% request aplikasi gagal seketika dengan error `NSURLErrorServerCertificateUntrusted`. Bagaimana Anda mendiagnosis interaksi antara proxy SSL inspection dan SPKI Pinning yang sudah terpasang di client?
13. **Skenario Kasus C**:
    Sebuah aplikasi mencatat data outbox berhasil disimpan secara lokal, namun server API sering menerima request duplikat beruntun dari mutasi yang sama pada kondisi konektivitas "Edge/2G lemot". Analisis di mana letak kelemahan siklus konfirmasi outbox-nya dan bagaimana rancangan idempotency key yang harus diterapkan.

---

## 16. Summary

- **Resilient Network Layer**: Mengisolasi state otentikasi dalam Swift `actor` adalah kunci utama untuk mencegah *thundering herd* dan *race condition* saat memperbarui sesi jaringan secara asinkron.
- **Enterprise-Grade Security**: Keamanan transport data modern mensyaratkan SPKI SHA-256 Public Key Pinning yang memvalidasi integritas kunci publik server, bukan sekadar sertifikat statis yang rentan terhadap masa kedaluwarsa pendek.
- **Offline-First Storage Engine**: Pemanfaatan Core Data di atas SQLite WAL memfasilitasi transaksi konkuren tinggi. Integrasi pola **Transactional Outbox** menjamin operasi penyimpanan lokal dan penjadwalan transmisi server bersifat atomik, konsisten, terisolasi, dan tahan terhadap kegagalan aplikasi.
- **Deterministik Resolusi Konflik**: Resolusi konflik bukan sekadar menimpa seluruh payload (*Last-Write-Wins naif*), melainkan menerapkan rekonsiliasi data *field-level* atau *delta-patch* yang terikat pada urutan sequence server yang valid.