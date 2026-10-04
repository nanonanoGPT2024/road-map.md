# BAB 06: Quiz, Challenge, & Knowledge Check
**Jaringan, Serialisasi Data, & Offline-First Persistence**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Model Konkurensi Jaringan & Threading URLSession:**  
   Jelaskan bagaimana `URLSession` mengeksekusi request di tingkat thread sistem ketika dipanggil via asynchronous API Swift Concurrency (`URLSession.shared.data(for:)`) dibandingkan dengan pemanggilan berbasis completion handler dengan delegasi kustom (`delegateQueue`). Bagaimana sistem runtime mengisolasi thread background dari thread utama saat payload data diterima dari socket TCP/TLS?

2. **Dinamisme Serialisasi dengan Custom Codable:**  
   Dalam skenario di mana endpoint backend mengembalikan polymorphic payload (misalnya, entitas `TimelineItem` yang dapat berupa `TextPost`, `ImagePost`, atau `PollPost` berdasarkan field `item_type`), bagaimana mekanisme parsing manual menggunakan `init(from decoder: Decoder)` harus diimplementasikan? Analisis penggunaan `KeyedDecodingContainer` vs `SingleValueDecodingContainer` dalam mereduksi overhead deserialisasi.

3. **HTTP Cache Specification vs Local Persistence:**  
   Bedakan arsitektur penyimpanan dan invalidasi data antara HTTP-level caching (`URLCache` yang menghormati header `Cache-Control`, `ETag`, dan `Last-Modified`) dengan Database persistence (Core Data / SwiftData). Dalam arsitektur *offline-first*, mengapa `URLCache` saja tidak memadai untuk menjamin status data yang deterministik?

4. **Isolasi Memori & Concurrency Confinement pada Core Data vs SwiftData:**  
   Jelaskan konsep *Thread Confinement* pada `NSManagedObjectContext` (Core Data) melalui mekanisme `perform` / `performAndWait`, lalu bandingkan dengan model isolasi aktor (`@ModelActor`) pada SwiftData. Mengapa mengoper *managed object instance* langsung melintasi batas context/actor dapat memicu crash tingkat memori (`EXC_BAD_ACCESS`) atau data corruption?

5. **Prinsip Idempotensi & Resiliensi Request Jaringan:**  
   Definisikan peran *Idempotency Key* (biasanya diimplementasikan via header `Idempotency-Key` atau payload signature) saat merancang offline mutation retry queue. Mengapa metode HTTP `POST` memerlukan penanganan khusus dibandingkan `PUT` atau `DELETE` ketika koneksi jaringan pulih setelah status *timed out*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Debugging Faulting & Memory Footprint Core Data:**  
   Sebuah aplikasi mengalami *memory spike* eksponensial yang berujung pada Out-Of-Memory (OOM) crash ketika memuat 50.000 relasi objek yang di-*fetch* dari SQLite storage. Jelaskan apa itu mekanisme *faulting* pada Core Data, bagaimana status *fault* dipecahkan (*fire*), dan konfigurasi fetch request apa (`returnsObjectsAsFaults`, `fetchBatchSize`, `relationshipKeyPathsForPrefetching`) yang harus digunakan untuk mencegah degradasi performa ini?

2. **Custom URLProtocol & Deadlock Interception:**  
   Ketika mengimplementasikan custom `URLProtocol` untuk kebutuhan intercepting token refresh (mengubah respons `401 Unauthorized` menjadi pemanggilan refresh token dan melakukan replay request asli), perangkap apa yang dapat menyebabkan *infinite recursion* atau *thread deadlock*? Bagaimana cara memitigasinya menggunakan `setProperty(_:forKey:in:)`?

3. **Decoding Performance pada Large JSON Payloads:**  
   Analisis perbedaan performa internal antara `JSONDecoder.DateDecodingStrategy.iso8601` standar dengan custom formatter strategy pada dataset JSON berukuran 20MB. Bagaimana alokasi memori sementara (*transient heap allocation*) terbentuk akibat implementasi closure-based date parsing, dan bagaimana optimasi level zero-copy atau direct string parsing dapat mengatasi thread stall pada decoding pipeline?

4. **Pola Konflik Sinkronisasi SwiftData (@ModelActor):**  
   Diberikan dua task background konkuren yang masing-masing menjalankan `@ModelActor` terpisah. Keduanya memodifikasi atribut yang sama dari sebuah entitas `Order` yang memiliki status sinkronisasi lokal. Jika kedua aktor memanggil `context.save()` hampir secara bersamaan, bagaimana SwiftData menangani *optimistic locking* di bawah kap mesin? Apa signifikansi konfigurasi merge policy (`NSMergePolicy`) yang setara di SwiftData?

5. **Edge Cases: SQLite Database Lock pada Flapping Network:**  
   Saat aplikasi melakukan *background sync* besar-besaran (melakukan insert/update batch ribuan baris di background thread) sementara user terus melakukan *write* di thread utama (UI mutation), SQLite melempar error `database is locked` (Code 5) atau timeout. Mengapa write-ahead logging (WAL mode) memitigasi hal ini, dan apa limitasi WAL ketika ada transaksi read/write yang menggantung (*long-running uncommitted transaction*)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Large Payload Decoding & UI Freezing pada Dashboard Finansial
*Konteks*: Sebuah aplikasi fintech perbankan enterprise menarik riwayat transaksi 1 tahun terakhir yang menghasilkan payload JSON sebesar 45MB dengan lebih dari 30.000 entri. Data ini diunduh menggunakan Swift Concurrency pada sebuah service class:
```swift
@MainActor
class TransactionViewModel: ObservableObject {
    @Published var transactions: [TransactionDTO] = []
    
    func loadTransactions() async throws {
        let (data, _) = try await URLSession.shared.data(from: endpointURL)
        let decoded = try JSONDecoder().decode([TransactionDTO].self, from: data)
        self.transactions = decoded
    }
}
```
*Dampak Masalah*: Aplikasi mengalami *frozen interface* (ANR) selama 2.8 hingga 4 detik di perangkat kelas menengah. Profiling Instruments (Time Profiler) menunjukkan CPU 100% pada Main Thread di blok `JSONDecoder.decode`.

*Pertanyaan Diagnostik*:
1. Analisis mengapa parsing tersebut mengunci UI thread meskipun eksekusi jaringan `URLSession.shared.data` bersifat asynchronous.
2. Rancang ulang arsitektur pemrosesan data ini menggunakan Task isolation terpisah, teknik parsing modular/streaming atau background processing, serta strategi penyajian data secara bertahap (*incremental rendering/pagination*) tanpa membebani MainActor.

---

### Skenario B: Desinkronisasi Data & Data Loss pada Bidirectional Sync Engine
*Konteks*: Aplikasi manajemen logistik menggunakan arsitektur offline-first. Kurir dapat memperbarui status paket menjadi `DELIVERED` dan menginput catatan tanda tangan saat berada di daerah tanpa sinyal (area *dead-zone*). Pada saat yang sama, admin di dispatch center melalui Web Dashboard membatalkan paket tersebut (`CANCELLED`) karena kesalahan rute. 

Aplikasi lokal menggunakan strategi naive *Last-Write-Wins* (LWW) berdasarkan `updated_at` timestamp perangkat kurir:
```
[Lokal: Kurir di Dead-zone] 
10:00: Status diubah ke DELIVERED (Timestamp lokal: 10:00)

[Remote: Dispatcher Web]
10:05: Status diubah ke CANCELLED (Timestamp server: 10:05)

[Koneksi Pulih]
10:15: Sinkronisasi berjalan. Jam perangkat kurir ternyata mengalami desinkronisasi/skew (+20 menit lebih cepat, tertulis 10:20). 
Payload lokal menimpa status CANCELLED di server menjadi DELIVERED.
```
*Dampak Masalah*: Integritas data rusak fatal; paket yang dibatalkan oleh pusat tetap terkirim secara administratif, memicu audit failure.

*Pertanyaan Diagnostik*:
1. Mengapa mengandalkan wall-clock timestamp perangkat klien pada arsitektur offline-first adalah fatal defect?
2. Rekayasa sebuah mekanisme rekonsiliasi state (misalnya, menggunakan *State Transition State Machine*, *Vector Clocks*, atau *CRDTs*) untuk mendeteksi konflik ini secara deterministik dan mencegah overwrite yang tidak sah.

---

### Skenario C: Write Amplification & Battery Drain pada Naive Outbox Pattern
*Konteks*: Aplikasi social commerce mengimplementasikan *Transactional Outbox Pattern* untuk mutasi offline (like, comment, add to cart). Implementasi eksisting menggunakan polling timer:
```swift
Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { _ in
    Task { await OutboxQueue.shared.flushPendingMutations() }
}
```
Ketika mutasi gagal akibat jaringan timeout, sistem langsung menjadwalkan ulang tanpa batasan, melakukan fetch ulang dari Core Data/SwiftData secara terus-menerus, dan mencoba mengirimkan ulang semua payload yang gagal secara paralel.

*Dampak Masalah*: 
- Thermal throttling pada perangkat client, *battery drain* parah.
- Server mengalami kondisi *Distributed Denial of Service* (DDoS) mandiri dari ribuan client yang sedang mengalami koneksi marginal (*flapping connection*), memicu *cascading failure* pada API gateway backend.

*Pertanyaan Diagnostik*:
1. Identifikasi minimal 3 anti-pattern arsitektural dari implementasi di atas.
2. Rancang arsitektur Outbox Queue kelas enterprise yang memanfaatkan `NWPathMonitor`, mengimplementasikan *Exponential Backoff dengan Jitter*, eksekusi serial/FIFO per-agregat entitas, dan isolasi persistence context yang efisien.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Offline-First Synchronization Engine with Optimistic UI & Transactional Outbox

#### Problem
Sistem operasional lapangan memerlukan modul sinkronisasi data mutasi (Update & Insert) yang bekerja mulus pada kondisi jaringan ekstrem (koneksi terputus-putus, latensi tinggi, hingga offline total). Modul harus mendukung *Optimistic UI* (UI ter-update instan tanpa menunggu respons jaringan) dan menjamin konsistensi data absolut menggunakan *Transactional Outbox Pattern* dengan jaminan zero data loss.

#### Requirements
1. **Core Persistence & Isolation**:
   - Bangun menggunakan **SwiftData** (menggunakan `@ModelActor`) atau **Core Data** (menggunakan background `NSManagedObjectContext` privat yang terisolasi dari main context).
   - Definisikan dua entitas data:
     - `WorkOrder` (id, title, status: pending/in_progress/completed, updatedAt).
     - `OutboxMutation` (id, entityId, mutationType: updateStatus/updateTitle, payload: Data/JSON, timestamp, retryCount, status: pending/syncing/failed).
2. **Optimistic UI Management**:
   - Ketika mutasi dieksekusi via UI:
     - Modifikasi status entitas `WorkOrder` secara lokal terlebih dahulu (optimistic state).
     - Masukkan record operasi ke dalam `OutboxMutation` dalam satu kesatuan unit transaksi lokal yang atomik.
   - Sediakan mekanisme *Rollback*: Jika mutasi ditolak permanen oleh server (misal: validation error 422 atau unresolvable conflict 409), status entitas harus di-revert ke snapshot valid terakhir dan UI menerima notifikasi kesalahan.
3. **Resilient Outbox Engine (Network Engine)**:
   - Gunakan `NWPathMonitor` untuk mendeteksi ketersediaan interface (`wifi`, `cellular`). Engine hanya memproses antrean ketika interface tersedia dan tidak *expensive/constrained* (opsional via konfigurasi).
   - Eksekusi antrean mutasi wajib mematuhi kaidah FIFO (First-In, First-Out) berdasarkan dependencies ID entitas guna mencegah race condition perubahan atribut.
   - Gunakan algoritma **Exponential Backoff dengan Full Jitter** untuk retry mutasi yang gagal akibat masalah transient (network error 5xx, timeout):
     $$\text{Sleep} = \text{random}(0, \, \min(M, \, B \times 2^{\text{attempt}}))$$
   - Sertakan header `Idempotency-Key` (UUID) pada setiap request keluar untuk mencegah duplikasi eksekusi di sisi server.
4. **Strict Concurrency**:
   - Kode harus bebas dari data race dan lolos audit Swift 6 Strict Concurrency Checking (`-strict-concurrency=complete` / Swift 6 mode) tanpa ada warning `@unchecked Sendable` kecuali pada wrapper yang terdokumentasi dan terjustifikasi keamanannya.

#### Constraints
- Dilarang menjalankan proses I/O disk (save database) dan decoding/encoding JSON pada Main Thread / MainActor.
- Tidak boleh terjadi *infinite loop retry* jika server mengembalikan error kategori non-transient (status code 4xx).
- Memory footprint saat sinkronisasi batch harus terjaga flat (tidak ada kebocoran memory / retain cycle pada task background).

#### Expected Output
1. File arsitektur modular yang terdiri dari:
   - `SyncEngineActor` (mengelola processing loop outbox dan listener konektivitas).
   - `OutboxRepository` (abstraksi persistence layer untuk write/update/delete mutasi).
   - `NetworkDispatcher` (mengelola eksekusi HTTP via `URLSession` dengan injection header idempotensi dan error classification).
2. Unit tests atau integration test harness yang mendemonstrasikan skenario:
   - Sukses eksekusi mutasi offline $\to$ koneksi pulih $\to$ server menerima update $\to$ status outbox terhapus/terselesaikan.
   - Skenario konflik/error 4xx $\to$ trigger rollback state pada `WorkOrder` ke kondisi semula.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara `URLSessionConfiguration.default`, `ephemeral`, dan `background` beserta batasan proses background execution oleh sistem operasi iOS.
- [ ] Arsitektur internal `Codable`: Hierarki `Decoder`, `SingleValueDecodingContainer`, `KeyedDecodingContainer`, dan `UnkeyedDecodingContainer`.
- [ ] Thread Confinement Model pada database lokal (Core Data `NSManagedObjectContext` concurrency types vs SwiftData `@ModelActor`).
- [ ] Peran HTTP conditional requests (`If-None-Match` dengan `ETag` dan `If-Modified-Since` dengan `Last-Modified`) untuk efisiensi bandwidth seluler.
- [ ] Batasan algoritma *Last-Write-Wins* (LWW) dan risiko *clock drift* pada distributed offline mobile sync.
- [ ] Konsep Transactional Outbox Pattern untuk mengatasi dual-write problem antara local storage dan remote backend.

### Saya tidak perlu menghafal:
- [ ] Nilai hex atau byte-level serialization format dari format binary payload tertentu (misal: Protobuf internal wire format atau raw SQLite page header format).
- [ ] Seluruh kode status HTTP IANA secara komprehensif di luar rentang standar (200, 201, 204, 304, 400, 401, 403, 404, 409, 422, 500, 502, 503, 504).
- [ ] Sintaks signature method Objective-C legasi dari Core Data fetch APIs yang sudah digantikan oleh Swift closure/concurrency API modern.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi `URLSession` kustom dengan custom timeout, pinned SSL/TLS certificates (Network Security), dan autentikasi adaptif via interceptor.
- [ ] Mengurai nested JSON dinamis, heterogeneous arrays, dan format tanggal non-standar secara optimal menggunakan custom implementation `Decodable`.
- [ ] Melakukan isolasi total operasi database intensif ke background context / background actor agar rendering frame Main Thread stabil di 60/120 FPS.
- [ ] Menggunakan Instruments (*Time Profiler*, *Allocations*, dan *Core Data Instrument*) untuk melacak bottle-neck deserialisasi, memory leaks, dan faulting overhead.
- [ ] Mengimplementasikan algoritma retry yang aman (Exponential Backoff + Jitter) yang terintegrasi dengan pemantauan status jaringan real-time (`NWPathMonitor`).
- [ ] Menulis test suite deterministik untuk memvalidasi skenario konektivitas buruk, timeout, dan *conflict resolution* menggunakan custom `URLProtocol` mock.