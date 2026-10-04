# BAB 08: Quiz, Challenge, & Knowledge Check
**Persistensi & Offline-First Data Pipeline**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Mekanisme `@Model` Macro vs `NSManagedObject`
Jelaskan secara mendalam bagaimana SwiftData Macro `@Model` mentransformasi struktur data Swift standar saat fase kompilasi (*AST macro expansion*). Bandingkan dengan mekanisme representasi memori pada `NSManagedObject` di Core Data legacy, khususnya terkait manipulasi *stored properties*, *backing storage*, dan implementasi antarmuka `Observable`/`PersistentModel`.

### Soal 1.2: Lifecycle & Topology `ModelContainer` dan `ModelContext`
Uraikan arsitektur pemisahan tanggung jawab antara `ModelContainer` dan `ModelContext`. Bagaimana siklus hidup objek (*object lifecycle*) berpindah status dari *transient*, *inserted*, *modified*, hingga *persisted* di SQLite? Mengapa mengeksekusi operasi simpan (*saving*) pada `mainContext` secara terus-menerus dianggap sebagai *anti-pattern* performa pada arsitektur SwiftUI?

### Soal 1.3: SQLite Engine: Write-Ahead Logging (WAL) & Concurrency
SwiftData dan Core Data secara *default* menggunakan *journaling mode* WAL (Write-Ahead Logging). Jelaskan secara teknis bagaimana mode WAL memisahkan operasi pembacaan (*reader*) dan penulisan (*writer*) ke dalam disk. Mengapa konfigurasi ini sangat krusial untuk mencegah pemblokiran (*locking contention*) pada thread UI saat *background sync pipeline* sedang menulis data dalam volume besar?

### Soal 1.4: Dynamic Invalidation pada SwiftUI via `@Query`
Bagaimana cara kerja internal `@Query` dalam mendeteksi mutasi data dan memicu *invalidation pass* pada *view hierarchy* SwiftUI? Analisis batas-batas struktural di mana penggunaan `@Query` menjadi sub-optimal (misalnya: *deeply nested relationship traversal*, *massive dataset aggregation*) dan alternatif arsitektural apa yang harus diisolasi ke dalam *domain layer*.

### Soal 1.5: Optimistic UI vs Pessimistic UI dalam Offline Pipeline
Bandingkan paradigma *Optimistic UI Update* dengan *Pessimistic UI Update* dalam konteks aplikasi *mobile-first* yang bergantung pada ketersediaan jaringan yang fluktuatif. Bagaimana arsitektur *local cache* bertindak sebagai *single source of truth* (SSOT) untuk memfasilitasi *instant user feedback*, dan mekanisme apa yang mutlak dibutuhkan untuk menangani kompensasi kegagalan (*rollback*) ketika mutasi jarak jauh (*remote mutation*) ditolak oleh server?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Actor Isolation & Concurrency Safety dengan `@ModelActor`
SwiftData memperkenalkan protokol `@ModelActor` untuk mengeliminasi *concurrency hazard* yang sering terjadi pada Core Data multithreading.
```swift
@ModelActor
public actor DataSyncHandler {
    // Bagaimana ModelContext diinisialisasi dan diisolasi di sini?
}
```
Jelaskan bagaimana protokol `@ModelActor` memanfaatkan Swift Structured Concurrency untuk menjamin *thread-safety* terhadap `ModelContext` dan `ModelExecutor`. Mengapa meneruskan *instance* model persistensi (`PersistentModel`) melintasi batas *actor* (*actor boundaries*) dapat memicu *undefined behavior* atau *runtime crash*, dan bagaimana cara yang benar untuk memindahkan identitas objek antar-konteks?

### Soal 2.2: Faulting, Deferred Loading, dan Masalah N+1 Query
Jelaskan fenomena *faulting* pada persistensi relasional berbasis SQLite di iOS. Bagaimana skenario loop tampilan sederhana di SwiftUI (seperti `ForEach` yang merender relasi *to-many*) dapat memicu masalah *N+1 query*? Bagaimana cara mendeteksi masalah ini menggunakan Apple Instruments (Core Data / Time Profiler) dan strategi *relationship prefetching* atau *batch fetching* apa yang harus diterapkan?

### Soal 2.3: Skema Migrasi: Lightweight vs Custom SchemaMigrationPlan
Ditinjau dari *migration pipeline*, jelaskan perbedaan deterministik antara *Lightweight Migration* dan migrasi kompleks bertahap (*VersionedSchema* dengan `SchemaMigrationPlan`). Jika Anda harus mengubah tipe atribut non-opsional menjadi relasi *many-to-many* antar model yang telah memiliki jutaan entri di perangkat klien, langkah-langkah presisi apa yang harus dikonfigurasi dalam `MigrationStage.custom` untuk mencegah terminasi crash aplikasi (`fatalError`) saat migrasi skema berjalan?

### Soal 2.4: Conflict Resolution: Last-Write-Wins (LWW) vs Vector Clocks
Ketika perangkat offline selama 7 hari melakukan sinkronisasi balik ke server sentral, penggunaan strategi resolusi konflik *Last-Write-Wins* (LWW) murni sering kali mengakibatkan *silent data corruption*. Analisis kegagalan teknis LWW ketika jam perangkat (*client clock*) tidak akurat (*clock drift*). Bagaimana integrasi metadata seperti *version numbers*, *tombstones*, atau struktur data CRDT (*Conflict-free Replicated Data Types*) mengatasi kelemahan mendasar LWW tersebut?

### Soal 2.5: Store Poisoning & Core Data / SQLite Memory Growth Profiling
Dalam skenario *continuous data streaming* (misalnya aplikasi pelacak GPS atau IoT yang menyimpan 100 entri per detik ke *database* lokal), `ModelContext` dapat mengalami akumulasi memori tak terbatas (*memory bloat*). Jelaskan siklus hidup pembersihan objek (*fault firing*, *eviction*, dan pemanggilan `.reset()` / `processPendingChanges()`). Bagaimana cara merancang *batch-saving loop* yang efisien tanpa menyebabkan fragmentasi SQLite dan lonjakan konsumsi RAM?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden ANR (Watchdog Crash 0x8badf00d) Akibat Sinkronisasi Skala Besar
*Konteks*: Aplikasi ERP enterprise mengalami lonjakan laporan crash di Firebase Crashlytics dengan kode terminasi iOS Watchdog `0x8badf00d` (scene-update / main thread unresponsive) saat pengguna pertama kali login dan melakukan sinkronisasi *master data* katalog produk (~80.000 record dengan relasi harga dan kategori).

*Kondisi Teknis Saat Ini*:
```swift
// Terdeteksi di DataSyncManager.swift
@MainActor
func ingestFullCatalog(items: [ProductDTO]) {
    for item in items {
        let product = Product(from: item)
        modelContext.insert(product)
    }
    try? modelContext.save()
}
```

*Pertanyaan Diagnostik*:
1. Analisis titik kegagalan utama kode di atas hingga menyebabkan CPU Main Thread terkunci melampaui batas waktu Watchdog Timer iOS (biasanya 20 detik saat peluncuran / 10 detik saat berjalan).
2. Tuliskan refaktor arsitektur dari *pipeline* ingest data tersebut menggunakan `@ModelActor`, pembagian ukuran *batching* (*chunking*), dan teknik isolasi komputasi agar *frame rate* antarmuka SwiftUI tetap stabil pada 120 FPS (ProMotion).
3. Bagaimana strategi observabilitas (*progress reporting*) yang aman dikirimkan dari *background actor* ke UI tanpa membebani *Main Thread runloop*?

---

### Skenario B: Race Condition dan Collision Identitas pada Transaksi Kasir Offline
*Konteks*: Pada aplikasi Point-of-Sale (POS) restoran berbasis iPad, beberapa kasir dapat membuat transaksi pesanan secara offline saat koneksi LAN lokal terputus. Ketika koneksi internet pulih, *background sync worker* dari masing-masing iPad secara simultan mengirimkan transaksi yang dibuat secara offline ke database sentral.

*Masalah*: Muncul kasus di mana nomor faktur (*invoice number*) duplikat, relasi *order item* tertukar, dan entitas transaksi lokal ditimpa secara sepihak oleh data dari server, menyebabkan laporan keuangan harian tidak seimbang (*discrepancy*).

*Pertanyaan Diagnostik*:
1. Mengapa ketergantungan pada *auto-incrementing integer IDs* dari *database* sentral gagal secara fundamental pada arsitektur offline-first?
2. Rancang skema identifikasi entitas yang robust menggunakan *Client-Generated UUID (v4 atau v7)*, *Idempotency Keys*, dan *State Tracking Flags* (misal: `syncStatus`: `.draft`, `.queued`, `.synced`, `.conflict`).
3. Bagaimana mekanisme *reconciliation logic* harus disusun jika server menolak satu pesanan karena salah satu menu tiba-tiba dinyatakan *out-of-stock* oleh manajer cabang pada terminal yang berbeda?

---

### Skenario C: Arsitektur Data Pipeline Terenkripsi & Regulasi Kepatuhan
*Konteks*: Anda bertindak sebagai Principal Mobile Architect untuk aplikasi rekam medis (Electronic Health Records) berstandar HIPAA yang harus mendukung akses data riwayat pasien saat dokter berada di ruang operasi bawah tanah (tanpa sinyal).

*Spesifikasi Kebutuhan*:
- Seluruh persistensi data lokal wajib terenkripsi *at-rest* menggunakan AES-256.
- Log tindakan dokter (*audit trail*) harus dicatat dan tidak dapat dimodifikasi (*append-only*, *tamper-evident*).
- Aplikasi harus memisahkan data sensitif pasien (PHI - Protected Health Information) yang tidak boleh disinkronkan ke *cloud* publik, dengan metadata non-sensitif yang boleh disinkronkan via CloudKit.

*Pertanyaan Diagnostik*:
1. Bandingkan trade-off arsitektur antara mengimplementasikan **SwiftData + SQLCipher (melalui custom SQLite builds / GRDB layer)** vs **Core Data dengan File Protection API iOS (`FileProtectionType.complete`)** vs **Custom Attribute Transformer terenkripsi**.
2. Rancang model *Outbox Pattern* lokal untuk *audit trail pipeline* yang menjamin bahwa mutasi data klinis dan pencatatan log audit dieksekusi secara atomik (*atomic transaction*), sehingga tidak ada celah di mana data klinis tersimpan tetapi log audit gagal ditulis.
3. Bagaimana Anda merancang topologi *dual-container* untuk memisahkan data PHI lokal-eksklusif dari container tersinkronisasi publik?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Offline-First Outbox Synchronization Engine

#### Problem Statement
Sebagian besar implementasi persistensi lokal di SwiftUI gagal ketika bertransisi ke status jaringan yang tidak stabil: UI membeku (*freeze*), data yang belum disinkronkan hilang saat aplikasi dihentikan secara paksa (*force kill*), atau terjadi pengiriman mutasi ganda (*duplicate submission*) yang merusak integritas server API. Anda diminta untuk merancang dan mengimplementasikan modul **Outbox Sync Engine** produksi yang sepenuhnya reaktif, aman terhadap *thread*, dan tahan terhadap pemutusan daya/koneksi mendadak.

#### Functional Requirements
1. **The Outbox Store**: Setiap aksi tulis (Create, Update, Delete) yang dilakukan pengguna di antarmuka tidak boleh langsung memanggil REST API. Aksi tersebut harus disimpan secara transaksional ke dalam tabel lokal `SyncOutboxItem` bersamaan dengan mutasi pada *domain model* lokal.
2. **Actor-Based Sync Pipeline**: Buat `@ModelActor` bernama `OutboxSyncEngine` yang bertugas membaca antrean outbox, melakukan serialisasi *payload*, dan mengirimkannya ke remote mock network endpoint.
3. **Exponential Backoff & Jitter**: Jika terjadi kegagalan jaringan (disimulasikan dengan HTTP 503 atau *network timeout*), *engine* harus menerapkan penundaan eksponensial dengan *random jitter* ($T = 2^{\text{attempt}} \times \text{base} + \text{jitter}$) dan membatasi percobaan maksimal (*max retries*).
4. **Idempotency Execution**: Setiap item outbox harus mengemas `idempotencyKey` unik berbasis UUIDv7 atau hash deterministik untuk mencegah eksekusi ganda di *backend*.
5. **SwiftUI Integration**: Sediakan antarmuka visual sederhana di SwiftUI yang menampilkan status sinkronisasi secara *real-time* (ikon indikator per-entitas: *Syncing*, *Pending Offline*, *Failed with Rollback option*) memanfaatkan `@Query` yang bereaksi secara efisien terhadap perubahan status pada model.

#### Non-Functional Constraints
- **Concurrency**: Wajib mengaktifkan Swift 6 Strict Concurrency Checking (`-strict-concurrency=complete`) tanpa toleransi *warning* atau *data race detection*.
- **Main Thread Protection**: Nol operasi disk I/O berat atau JSON serialization pada Main Thread. Operasi UI frame rate harus stabil pada instrumen *Core Animation FPS*.
- **No Third-Party Libraries**: Implementasi murni menggunakan ekosistem bawaan Apple: SwiftData / Core Data, Swift Concurrency, dan Foundation (`URLSession`).

#### Expected Deliverables
1. **Core Domain & Outbox Models**: Definisi skema model `@Model` untuk entitas bisnis dan `SyncOutboxItem`.
2. **Engine Implementation**: Kode lengkap `@ModelActor public actor OutboxSyncEngine` dengan metode `processQueue()`, `handleFailure()`, dan resolusi idempotensi.
3. **Mock Network Layer**: Implementasi `URLProtocol` atau Service Actor yang mensimulasikan kegagalan jaringan intermiten (tingkat kegagalan 40% dan latensi acak 500ms - 2500ms).
4. **Resiliency Verification Steps**: Rangkaian skenario pengujian manual/otomatis untuk memvalidasi skenario aplikasi di-kill saat *sync midway* dan verifikasi konsistensi data setelah aplikasi di-launching kembali.

---

## 5. Knowledge Check & Checklist

Dokumen ini berfungsi sebagai matriks evaluasi mandiri (*self-assessment*) sebelum melangkah ke bab berikutnya. Tandai setiap poin secara jujur berdasarkan kapasitas pemahaman dan eksekusi teknis Anda.

### Saya harus memahami:
- [ ] Anatomi internal SQLite storage: tabel metadata, format file WAL, shm (shared memory), dan bagaimana checkpointing bekerja.
- [ ] Perbedaan fundamental antara model konkurensi Core Data (`NSManagedObjectContext` thread confinement) dengan SwiftData (`@ModelActor` isolation boundary).
- [ ] Mengapa `PersistentIdentifier` aman dikirimkan antar-actor sedangkan instance `PersistentModel` tidak aman (*non-sendable*).
- [ ] Batasan kapasitas `@Query` dan mekanisme *view dependency graph tracking* di balik makro SwiftUI.
- [ ] Prinsip *idempotency* pada REST/GraphQL APIs dalam konteks *retry pipeline* dari *offline store*.
- [ ] Bahaya arsitektur *two-way sync* naif dan perlunya metadata tracking (*monotonic clocks*, *tombstones*, *dirty flags*).
- [ ] Karakteristik *File Protection APIs* di iOS dan dampaknya terhadap akses basis data saat layar perangkat terkunci (*device locked*).

### Saya tidak perlu menghafal:
- [ ] Sintaks mentah SQLite C-APIs (`sqlite3_step`, `sqlite3_prepare_v2`, dll.) selama memahami abstraksi ORM yang digunakan.
- [ ] Kode heksadesimal spesifik untuk setiap status error migrasi skema SQLite (cukup memahami strategi penanganan `MigrationError`).
- [ ] Rumus matematika mendalam dari algoritma konsensus terdistribusi tingkat lanjut seperti Raft/Paxos (cukup memahami aplikasinya pada *client-server reconciliation*).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi `ModelContainer` secara terprogram dengan skema multi-entitas, konfigurasi konfigurasi in-memory untuk *unit testing*, dan *schema versioning*.
- [ ] Melakukan isolasi *heavy database write operations* ke dalam `@ModelActor` kustom tanpa memblokir SwiftUI Main Thread.
- [ ] Menggunakan Xcode Instruments (*Core Data template*, *Time Profiler*, dan *Allocations*) untuk mengendus *faulting latency*, *memory retention cycles*, dan *untracked entity leaks*.
- [ ] Menulis skema migrasi bertahap (*SchemaMigrationPlan*) lengkap dengan manipulasi data transformasi manual (*custom transform block*).
- [ ] Merancang dan membangun *Outbox Data Pattern* yang tangguh untuk sistem mutasi offline lengkap dengan *exponential backoff retry policy*.
- [ ] Mengintegrasikan status sinkronisasi persistensi lokal ke state UI menggunakan Swift Combine atau AsyncAlgorithms tanpa menyebabkan *re-render cascade* yang berlebihan pada SwiftUI.