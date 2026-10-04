# BAB 06: Quiz, Challenge, & Knowledge Check
**Offline-First Systems & Local Persistence**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **SharedPreferences vs. Relational/NoSQL Embedded Databases**  
   Mengapa penggunaan `SharedPreferences` (atau `NSUserDefaults` di iOS) untuk menyimpan structured domain data dianggap sebagai anti-pattern fatal pada aplikasi skala enterprise? Tinjau dari aspek *disk I/O serialization*, *thread blocking*, dan *atomic operations*.

2. **Single Source of Truth (SSOT) & Unidirectional Data Flow**  
   Dalam paradigma *Offline-First*, jelaskan secara presisi siklus hidup data ketika aksi mutasi (misalnya `CreateOrder`) dieksekusi oleh pengguna. Mengapa UI layer sama sekali diharamkan membaca *response payload* langsung dari Remote API Client?

3. **Anatomi Conflict Resolution: Last-Write-Wins (LWW) vs. CRDT**  
   Bandingkan pendekatan resolusi konflik berbasis *Last-Write-Wins* (LWW) menggunakan *client timestamp* dengan *Conflict-free Replicated Data Types* (CRDT). Pada skenario apa strategi LWW menyebabkan *silent data loss*, dan bagaimana clock drift antar perangkat memperparah kondisi ini?

4. **Tombstone Records vs. Hard Deletes**  
   Mengapa eksekusi kueri `DELETE FROM table WHERE id = ?` merupakan pelanggaran fatal dalam protokol sinkronisasi terdistribusi? Jelaskan bagaimana mekanisme *Tombstoning* (`is_deleted = true`, `deleted_at = TIMESTAMP`) memfasilitasi propagasi status entitas melintasi *heterogeneous sync boundaries*.

5. **Write-Ahead Logging (WAL) pada SQLite Engine**  
   Jelaskan mekanisme internal *Write-Ahead Logging* (WAL) pada engine SQLite/Drift. Mengapa mengaktifkan mode WAL secara signifikan meningkatkan *throughput* konkurensi antara operasi *read* dan *write* pada thread terpisah di Flutter?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Jank Prevention via Isolate Offloading pada Local I/O**  
   Kueri database lokal yang mengembalikan 20.000 baris data dibungkus menggunakan `Future<List<Entity>>`. Namun, DevTools Timeline tetap merekam frame drops (UI Jank) hingga 45 FPS saat kueri dieksekusi. Bongkar penyebab teknis di balik *event loop starvation* ini dan formulasikan solusinya menggunakan Dart Isolates atau Drift's Background Connection.

2. **Incremental Database Migration & Schema Integrity**  
   Bayangkan skenario di mana pengguna melewati 4 versi pembaruan aplikasi (melompat langsung dari skema database v1 ke v5). Bagaimana Anda menyusun arsitektur migrasi deterministik di Flutter (misal dengan Drift atau raw SQLite) yang menjamin *forward-compatibility*, mempertahankan integritas *foreign key*, dan memiliki mekanisme *rollback* darurat jika skrip migrasi gagal di tengah jalan?

3. **Overhead & Memory Footprint SQLCipher**  
   Ketika mengimplementasikan enkripsi *database-at-rest* menggunakan SQLCipher pada Flutter, terjadi degradasi performa I/O sebesar 20-35%. Bedah proses kriptografi internal per *page-level* yang menyebabkan overhead ini, dan bagaimana strategi caching enkripsi serta penanganan master key di secure storage OS (`Keychain`/`Keystore`) harus dimitigasi.

4. **Transactional Outbox Pattern & Network Flapping Resilience**  
   Rancang arsitektur data outbox queue lokal di Flutter untuk menangani kondisi *rapid network flapping* (koneksi terputus dan tersambung kembali setiap 2 detik). Bagaimana Anda menjamin operasi pemrosesan antrean bersifat *strictly atomic*, bebas dari duplikasi request (*idempotency*), dan tidak menghasilkan *thread-locking starvation*?

5. **Reactive Streams & Leakage pada Reactive Persistence**  
   Drift menyediakan stream reaktif (`watch()`) yang secara otomatis memancarkan data baru setiap kali tabel yang bersangkutan dimutasi. Jelaskan bagaimana Drift mengidentifikasi dependensi tabel di tingkat kueri, dan apa dampak arsitekturalnya jika terdapat *dangling subscription* di dalam Lifecycle State Widget yang sering direkonstruksi?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Out Of Memory (OOM) Crash saat Batch Synchronization di Wilayah Terpencil
Sebuah aplikasi inspeksi pertambangan digunakan secara offline penuh selama 14 hari di pedalaman Kalimantan. Selama periode tersebut, surveyor mengumpulkan data telemetri, log tekstual, dan ratusan form dengan total 85.000 mutasi lokal yang tersimpan di SQLite lokal. Saat surveyor kembali ke basecamp dan perangkat terhubung ke Wi-Fi berkecepatan tinggi, sistem sinkronisasi otomatis menyala. Tepat 3 detik kemudian, aplikasi mengalami *hard crash* seketika akibat OOM (Out Of Memory) pada Android/iOS.
* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi *memory bottleneck* pada pipeline serialisasi (JSON decoding, object mapping, SQLite cursor pagination).
  2. Rancang ulang arsitektur sinkronisasi menggunakan pola *Chunked/Windowed Streaming Batch* dengan *backpressure mechanism* yang menjamin konsumsi RAM konstan di bawah 60MB terlepas dari volume data lokal.

### Skenario B: Partial Overwrite & Race Condition pada Multi-Device Sync
Aplikasi POS (Point-of-Sale) restoran mengizinkan pelayan (Device A) dan kasir (Device B) mengelola order yang sama secara offline. Pelayan A menambahkan menu baru ke pesanan `#104` saat tabletnya offline. Di saat yang sama, Kasir B di meja kasir mengubah status pesanan `#104` menjadi *Paid* dan mencetak struk secara lokal. Ketika kedua perangkat mendapatkan kembali akses jaringan, data pesanan `#104` di remote database menunjukkan status *Paid*, tetapi item baru yang ditambahkan oleh Pelayan A terhapus total tanpa jejak.
* **Pertanyaan Diagnostik & Solusi:**
  1. Bedah titik kegagalan (*root cause*) arsitektur model data dan payload sinkronisasi yang digunakan.
  2. Implementasikan payload design berbasis *Event Sourcing* atau *Granular Field/Sub-entity Patching* untuk memastikan mutasi array `order_items` dan mutasi field `order_status` dapat ter-merge tanpa saling menghancurkan (*non-destructive merge*).

### Skenario C: Architectural Trade-off: Key-Value vs. Relational vs. Document NoSQL
Tim arsitek Anda sedang merancang modul rekam medis digital (EMR) portabel untuk tim medis darurat bencana alam. Persyaratan sistem:
- Menyimpan 100.000 riwayat pasien lengkap dengan relasi kompleks (diagnosa, obat, alergi, tindakan).
- Kemampuan pencarian teks kompleks secara instan (*Full-Text Search* / FTS) dalam kondisi offline.
- Audit trail immutable (tiap perubahan data dicatat historisnya).
- Eksekusi harus lancar pada perangkat Android murah (RAM 2GB, Go Edition).
* **Pertanyaan Diagnostik & Solusi:**
  1. Bandingkan secara analitis tiga opsi: **Drift (SQLite FFI)**, **Isar / ObjectBox (NoSQL FFI)**, dan **Hive (Pure Dart Key-Value)**.
  2. Berikan keputusan teknis definitif mengenai teknologi mana yang harus dipilih, lengkap dengan pertimbangan ukuran binary, footprint memori, index performance, dan dukungan konkurensi multi-isolate.

---

## 4. Chapter Challenge

**Tantangan Praktis: Production-Grade Transactional Outbox Engine dengan Idempotency dan Conflict-Free Sync**

### Problem Statement
Aplikasi logistik pengiriman barang membutuhkan *core persistence layer* baru. Kurir sering bekerja di basemen gedung atau area blind-spot seluler. Saat ini, pengiriman sering gagal ter-update, atau sebaliknya terjadi duplikasi status pengiriman karena kurir menekan tombol "Submit" berulang kali saat koneksi tidak stabil.

### Requirements
1. **Local Schema Architecture (Drift / Raw SQLite)**:
   - Buat skema tabel `deliveries` (ID, tracking_number, recipient_name, status, updated_at).
   - Buat skema tabel `outbox_mutations` (id, entity_id, mutation_type, payload_json, idempotency_key, created_at, retry_count, sync_status).
2. **Atomic Repository Layer**:
   - Setiap mutasi lokal yang dilakukan oleh kurir **harus** menulis data ke tabel `deliveries` dan tabel `outbox_mutations` dalam **satu transaksi database lokal tunggal (ACID Transaction)**. Jika salah satu gagal, batalkan seluruhnya.
3. **Resilient Sync Engine**:
   - Jalankan proses sinkronisasi di **Background Isolate** terpisah agar UI rendering thread bebas hambatan (0 drop frame).
   - Engine membaca entri `outbox_mutations` yang berstatus `PENDING` dengan urutan FIFO (First-In, First-Out).
   - Gunakan pendekatan *Exponential Backoff dengan Jitter* untuk menangani transient network error (misal: HTTP 503 atau Timeout).
   - Implementasikan *Idempotency Key* (UUIDv4) pada HTTP Header ke remote mock endpoint.
4. **Conflict Resolution Mechanism**:
   - Terapkan strategi resolusi: Bila server merespons bahwa versi server lebih baru (Status HTTP 409 Conflict), sistem harus mengeksekusi *Server-Wins with Local Notification Strategy* dan memperbarui local state via Tombstone / Merge tanpa menyebabkan crash aplikasi.

### Constraints
- **Zero UI Block**: Waktu eksekusi di Main UI Thread tidak boleh melebihi 16ms per siklus sinkronisasi.
- **Data Safety**: Tidak boleh ada data yang hilang jika aplikasi di-*kill* paksa oleh OS (Android Low Memory Killer) di tengah-tengah proses eksekusi HTTP request.
- **Dependencies**: Boleh menggunakan package: `drift`, `sqlite3_flutter_libs`, `http` / `dio`, `uuid`. Dilarang menggunakan package outbox *all-in-one* yang sudah jadi.

### Expected Output
- File arsitektur data: Skema database (Drift/SQLite).
- Repository logic yang mengimplementasikan *atomic local transaction*.
- Background Sync Worker (Isolate/Service) dengan logic queue processing, error backoff, dan state synchronization.
- Unit / Integration Test minimal 2 test cases:
  1. Simulasi kegagalan jaringan di tengah jalan dan pembuktian bahwa queue tidak terduplikasi serta me-retry secara elegan.
  2. Simulasi aplikasi mati saat transaksi database lokal, membuktikan status atomisitas (semua tersimpan atau tidak sama sekali).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mengapa *Single Source of Truth (SSOT)* mewajibkan UI hanya me-render data yang berasal dari local storage, bukan langsung dari Network Response.
- [ ] Perbedaan fundamental arsitektur dan trade-off performa antara SQLite (Relational/B-Tree), Hive/Isar (Key-Value/Document LSM-Tree/MDBX), dan SharedPreferences.
- [ ] Mekanisme kerja SQLite *Write-Ahead Logging* (WAL) dan pengaruhnya terhadap *concurrency locking* antar isolates.
- [ ] Anatomi strategi resolusi konflik: *Last-Write-Wins (LWW)*, *Tombstones*, *Vector Clocks*, dan *Conflict-Free Replicated Data Types (CRDTs)*.
- [ ] Cara kerja pola *Transactional Outbox Pattern* untuk memastikan konsistensi eventual antara database lokal dan distributed remote cloud.
- [ ] Konsep *Idempotency* pada level API dan database lokal untuk mencegah duplikasi eksekusi request akibat network retry.

### Saya tidak perlu menghafal:
- [ ] Seluruh sintaks dan kode C internals dari library SQLite atau SQLCipher.
- [ ] Angka pasti alokasi memori biner SQLite cache per OS architecture secara detail.
- [ ] Seluruh algoritma kriptografi internal AES-256 yang dieksekusi oleh SQLCipher.

### Saya harus bisa melakukan:
- [ ] Menjalankan kueri database baca/tulis yang berat di dalam Dart Background Isolate secara aman tanpa melanggar *isolate memory boundaries*.
- [ ] Menulis skrip migrasi database lokal bertahap (*step-by-step migration*) yang teruji dan bebas dari risiko *data corruption*.
- [ ] Merancang skema *Outbox Queue* dan *Sync Engine* mandiri yang mampu bertahan dari kondisi *hard crash* dan *network flapping*.
- [ ] Mendiagnosis dan mengeliminasi masalah *UI Jank* (Frame Drop) yang dipicu oleh serialisasi data lokal skala besar menggunakan Flutter DevTools CPU Profiler.
- [ ] Mengimplementasikan *Reactive Local Query Streams* ke Presentation Layer menggunakan arsitektur BLoC/Notifier dengan *proper cancellation/subscription disposal*.