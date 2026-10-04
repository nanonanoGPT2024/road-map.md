# BAB 05: Quiz, Challenge, & Knowledge Check
**Data Layer, Offline-First, & Room ORM Persistence**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Prinsip Single Source of Truth (SSOT) dan Siklus Reaktivitas Data Layer**  
   Dalam arsitektur *offline-first*, *Repository* bertindak sebagai mediator antara *local storage* (Room) dan *remote source* (REST/gRPC). Jelaskan mengapa *Repository* tidak boleh mengembalikan data langsung dari respons jaringan ke UI layer, melainkan harus melakukan penulisan (*write-through*) ke database lokal terlebih dahulu baru kemudian membiarkan UI mengamati (*observe*) stream database tersebut via `Flow<T>`. Apa konsekuensi struktural terhadap konsistensi state dan penanganan *offline mode* jika prinsip ini dilanggar?

2. **Room ORM Abstraction Overhead vs Raw SQLite**  
   Room menyediakan validasi kueri pada saat *compile-time* via KSP/kapt dan memetakan baris database ke objek Kotlin. Secara arsitektural dan performa, abstraksi apa yang diperkenalkan oleh Room (misalnya: pembuatan implementasi DAO `_Impl`, penggunaan `Cursor`, dan penanganan *threading* via `suspend` functions)? Kapan abstraksi ini dapat menimbulkan *overhead* performa dibandingkan pengeksekusian kueri SQLite mentah via `SupportSQLiteDatabase`?

3. **Mekanisme Room InvalidationTracker**  
   Ketika sebuah DAO mengekspos fungsi yang mengembalikan `Flow<List<T>>`, bagaimana Room mendeteksi bahwa data di dalam tabel yang bersangkutan telah berubah dan memicu emisi data baru ke dalam *flow collector*? Jelaskan peran tabel internal `room_master_table`, *trigger* SQLite, dan `InvalidationTracker` dalam siklus ini!

4. **Karakteristik dan Batasan SQLite WAL (Write-Ahead Logging) pada Android**  
   Room secara *default* mengaktifkan mode WAL (`PRAGMA journal_mode=WAL;`). Jelaskan perbedaan mendasar antara model *rollback journal* tradisional dan WAL dalam konteks konkurensi (konkurensi pembacaan vs penulisan). Apa saja batasan atau risiko degradasi performa yang dapat muncul jika transaksi penulisan dibiarkan terbuka terlalu lama (*long-running transaction*) dalam mode WAL?

5. **Entity Relationships: `@Relation` vs Embedded Objects vs Denormalisasi**  
   Bandingkan tiga pendekatan representasi relasi relasional 1:N dan N:M pada Room:
   - Penggunaan `@Embedded` dan `@Relation` via *intermediate data classes*.
   - Kueri manual dengan SQL `JOIN` yang dipetakan ke *flat Data Transfer Object* (DTO).
   - Denormalisasi data menggunakan `TypeConverter` (misal: menyimpan list ID/objek sebagai JSON string).  
   Analisis ketiga pendekatan ini dari perspektif kompleksitas kueri, kecepatan deserialisasi, konsistensi data (*referential integrity*), dan memori *footprint*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Analisis Eksekusi Kueri dan Penggunaan `EXPLAIN QUERY PLAN`**  
   Sebuah DAO memiliki kueri berikut:
   ```sql
   SELECT * FROM transactions 
   WHERE user_id = :userId AND status = 'COMPLETED' 
   ORDER BY timestamp DESC LIMIT 50
   ```
   Ketika data di tabel `transactions` mencapai 500.000 baris, kueri ini mengalami lonjakan latensi eksekusi dari 4ms menjadi 320ms, memicu peringatan *Choreographer dropped frames* saat dipanggil di thread disk I/O. Bagaimana Anda menggunakan `EXPLAIN QUERY PLAN` pada SQLite untuk mengidentifikasi apakah terjadi *table scan* atau *temporary B-tree sorting*? Rancang konfigurasi `@Index` komposit optimal pada Room Entity untuk menihilkan kebutuhan *b-tree sorting* dan memaksa *index covering scan*.

2. **Anatomi Thread Concurrency: Dispatchers.IO vs Room Query Dispatcher**  
   Secara *default*, Room mengalihkan eksekusi `suspend` kueri satu kali (*one-shot query*) ke dispatcher internalnya sendiri (`queryExecutor` / `transactionExecutor`). Apa yang terjadi secara *under-the-hood* jika seorang perekayasa software membungkus pemanggilan DAO tersebut dengan `withContext(Dispatchers.IO)`? Diskusikan potensi terjadinya *thread starvation* atau *deadlock* ketika *nested transaction* dieksekusi secara konkuren menggunakan coroutine terpisah yang berbagi *pool* thread terbatas.

3. **Strategi Migrasi Tanpa Kehilangan Data: `AutoMigration` vs `Migration` Manual**  
   Anda mengubah kolom non-null `status: String` menjadi enum ordinal `statusCode: Int`, serta menambahkan *foreign key constraint* dengan aksi `CASCADE` pada tabel yang sudah berisi data produksi. Mengapa skenario ini gagal diselesaikan oleh `AutoMigration` Room? Tuliskan langkah-langkah presisi dan perintah DDL SQLite yang harus dieksekusi di dalam objek `Migration(from, to)` untuk memodifikasi tabel SQLite tanpa melanggar *foreign key constraints* dan tanpa kehilangan data yang ada (pola *table recreation pattern*).

4. **Debugging Memory Leak pada Reactive Room Flow**  
   Perhatikan potongan kode pada ViewModel berikut:
   ```kotlin
   val userFeed = repository.getArticlesFlow()
       .map { list -> list.filter { it.isRelevant } }
       .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())
   ```
   Jika ViewModel ini mengamati tabel yang sering diperbarui (misalnya sinkronisasi background setiap 2 detik), jelaskan mengapa `SharingStarted.Eagerly` dapat mengakibatkan *memory leak* implisit atau pemborosan resource saat UI sedang berada di background (state `STOPPED`). Bagaimana siklus emisi Room berinteraksi dengan *lifecycle-aware collection* via `repeatOnLifecycle` pada UI layer?

5. **Edge Case: Deadlock pada `@Transaction` dengan Multiple DAOs**  
   Dua operasi *background sync* berjalan bersamaan pada dua thread coroutine yang berbeda. Thread A memanggil method `@Transaction` yang menulis ke `Table_A` lalu membaca `Table_B`. Thread B memanggil method `@Transaction` yang menulis ke `Table_B` lalu membaca `Table_A`. Mengapa skenario ini berpotensi memicu SQLite `SQLiteDatabaseLockedException` atau *deadlock* total pada level coroutine, meskipun SQLite menggunakan WAL mode? Bagaimana Room mengelola *locks* pada `transactionExecutor`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck I/O Skala Besar pada Initial Sync
**Konteks Insiden:**  
Aplikasi logistik enterprise melakukan proses *first-time login sync* yang mengunduh 100.000 data inventaris barang via chunked REST API (masing-masing 1.000 item per chunk). Implementasi awal melakukan iterasi penulisan chunk menggunakan:
```kotlin
chunk.forEach { item -> 
    inventoryDao.insert(item.toEntity()) 
}
```
Setiap `insert` dianotasi dengan `@Insert(onConflict = OnConflictStrategy.REPLACE)`.  
Dampaknya, perangkat mengalami peningkatan suhu drastis (*thermal throttling*), aplikasi membeku hingga memicu dialog Application Not Responding (ANR), dan konsumsi memori melonjak hingga terjadi `OutOfMemoryError` (OOM).

**Pertanyaan Diagnostik & Solusi:**
1. Mengapa memanggil method `@Insert` secara individual dalam sebuah perulangan mengakibatkan overhead I/O disk yang fatal pada SQLite? Jelaskan dampaknya terhadap siklus transaksi SQLite (*implicit transactions* dan sinkronisasi disk *fsync*).
2. Bagaimana Anda mendesain ulang arsitektur pemrosesan data ini menggunakan:
   - Chunked batch processing di dalam blok `roomDatabase.withTransaction {}`.
   - SQLite statement caching / statement reuse.
   - Mengendalikan memory footprint menggunakan Kotlin `Sequence` atau *streaming JSON parser* (misal: Moshi streaming / Kotlinx Serialization) sebelum data di-*insert* ke Room?

---

### Skenario B: Race Condition dan Konflik Data Sinkronisasi Dua Arah
**Konteks Insiden:**  
Aplikasi pencatatan inspeksi lapangan digunakan oleh teknisi di area tanpa sinyal seluler. Saat *offline*, teknisi A mengedit catatan inspeksi #402 pada pukul 10:15 WIB. Tanpa sepengetahuannya, teknisi B telah mengedit data inspeksi #402 yang sama pada portal web pada pukul 10:20 WIB. Ketika perangkat teknisi A mendapatkan koneksi pada pukul 11:00 WIB, *Background Sync Engine* berbasis `WorkManager` langsung melakukan *push* data lokal ke remote server, menimpa perubahan teknisi B secara membabi buta (*blind overwrite* / *last-write-wins*). Di sisi lain, *pull sync* yang berjalan paralel menuliskan data dari server ke Room menggunakan `OnConflictStrategy.REPLACE`, yang secara tidak sengaja menghapus draft lokal lain yang belum sempat diunggah.

**Pertanyaan Diagnostik & Solusi:**
1. Rancang arsitektur skema entitas Room untuk mendukung *conflict detection* dan *optimistic locking* (misal: penambahan atribut `syncState` [SYNCED, DIRTY, DELETED], `updatedAtUTC`, dan `versionHash`).
2. Tuliskan alur logika sinkronisasi (*two-way reconciliation algorithm*) yang harus dijalankan oleh Repository saat terjadi konflik: kapan data remote harus diterima, kapan data lokal harus dipertahankan, dan bagaimana menyajikan data ke pengguna jika intervensi manual (*manual conflict resolution UI*) mutlak dibutuhkan!

---

### Skenario C: Cache Invalidation Storm dan UI Freezing pada Tabular Real-Time Dashboard
**Konteks Arsitektur & Trade-off:**  
Sebuah aplikasi bursa saham/fintech memantau 200 instrumen trading secara real-time via WebSocket. Setiap ada tick data baru (bisa mencapai 50-100 update per detik), data disimpan ke Room Database agar data historis tetap tersedia secara offline. Dashboard UI mengamati data ini menggunakan:
```kotlin
@Query("SELECT * FROM market_tickers ORDER BY volume DESC")
fun observeMarketTickers(): Flow<List<MarketTickerEntity>>
```
Meskipun kueri dijalankan pada thread background, UI thread mengalami *stuttering* berat (frame rate anjlok dari 120 FPS ke 20 FPS). Tim menemukan bahwa Room memancarkan list baru yang berisi 200 objek setiap kali ada 1 baris data diupdate via WebSocket.

**Pertanyaan Diagnostik & Solusi:**
1. Mengapa Room secara fundamental mengeksekusi ulang *keseluruhan* kueri SQL dan memancarkan list objek baru dari awal setiap kali tabel target terpicu invalidasi oleh `InvalidationTracker`, terlepas dari seberapa kecil perubahan barisnya?
2. Bagaimana Anda mengeliminasi *invalidation storm* ini? Bandingkan dua strategi:
   - Penggunaan operator backpressure/debouncing pada coroutine (`flow.conflate()`, `debounce()`, `sample()`).
   - Implementasi arsitektur *In-Memory Caching with Throttled Persistence* (menjaga UI membaca real-time state langsung dari *in-memory cache / StateFlow*, lalu melakukan *batched flush* ke Room setiap interval $N$ detik). Berikan analisis *trade-off* integritas data vs performa UI untuk kedua strategi tersebut.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Offline-First Sync Engine dengan Tombstone Pattern dan Pagination Integrasi

#### 1. Problem Statement
Sebuah platform manajemen tugas (*Field Workforce Management*) membutuhkan modul *Data Layer* offline-first yang sangat handal untuk pekerja tambang. Modul ini harus mampu menangani ribuan data tugas (*tasks*), mendukung *soft-delete* (karena data yang dihapus saat offline harus disinkronkan ke server sebagai operasi penghapusan), mendeteksi konflik edit lokal vs remote, serta terhubung secara mulus ke UI melalui Room Paging (`PagingSource`).

#### 2. Technical Requirements
1. **Database Schema & Entity:**
   - Buat Room Entity `TaskEntity` dengan kolom: `id` (String, PK), `title`, `description`, `priority` (Enum), `updatedAt` (Long), `isDeleted` (Boolean - *Tombstone flag*), dan `syncStatus` (Enum: `SYNCED`, `CREATED_OFFLINE`, `UPDATED_OFFLINE`, `DELETED_OFFLINE`).
   - Tambahkan composite index pada kolom `(isDeleted, priority, updatedAt)` untuk optimalisasi kueri UI.
2. **Data Access Object (DAO):**
   - Method untuk paging query: Mengekspos tugas yang aktif (`isDeleted = 0`) yang mengembalikan `PagingSource<Int, TaskEntity>`.
   - Method *soft-delete*: Bukan menjalankan kueri SQL `DELETE`, melainkan mengubah status `isDeleted = 1` dan `syncStatus = DELETED_OFFLINE`.
   - Method *hard-delete*: Kueri SQL `DELETE` permanen khusus untuk membersihkan data tombstone yang sudah terkonfirmasi terhapus di remote server.
   - Batch Upsert: Penulisan data remote menggunakan algoritma rekonsiliasi state lokal agar data lokal yang berstatus `DIRTY` (belum terunggah) tidak tertimpa oleh data server yang usang.
3. **Repository Sync Engine:**
   - Buat fungsi `syncTasks(): Result<Unit>` yang melakukan *bidirectional sync*:
     1. **Push Phase:** Mencari semua entitas dengan `syncStatus != SYNCED`, mengirimkannya ke remote API mock (buat antarmuka remote API sederhana). Jika remote sukses menerima penghapusan, jalankan *hard-delete* lokal. Jika sukses menerima pembaruan/pembuatan, ubah status menjadi `SYNCED`.
     2. **Pull Phase:** Mengambil data terbaru dari remote API sejak *checkpoint* terakhir (menggunakan timestamp *high-water mark*). Jalankan rekonsiliasi data: Jangan menimpa data lokal jika data lokal memiliki perubahan yang belum terkirim (`syncStatus != SYNCED`).
4. **Transaction Integrity:**
   - Seluruh siklus pemrosesan pull batch harus dibungkus dalam `RoomDatabase.withTransaction` untuk memastikan atomisitas.

#### 3. Constraints
- **Zero UI Block:** Seluruh operasi I/O dan kalkulasi rekonsiliasi data dilarang keras berjalan di `Dispatchers.Main`.
- **Memory Efficiency:** Dilarang memuat seluruh isi tabel ke dalam memori RAM sekaligus saat proses migrasi atau sinkronisasi. Gunakan teknik *windowing* atau *batch chunking* (maksimum 500 item per transaksi).
- **Anti-Pattern Constraint:** Dilarang menggunakan `allowMainThreadQueries()`.

#### 4. Expected Output
- Kode sumber Kotlin yang lengkap dan modular:
  - `TaskEntity.kt` (lengkap dengan definisi Index dan Enum).
  - `TaskDao.kt` (lengkap dengan SQLite query dan anotasi Room yang tepat).
  - `AppDatabase.kt` (konfigurasi Room database dengan TypeConverters).
  - `TaskRepositoryImpl.kt` (mengimplementasikan sinkronisasi dua arah, rekonsiliasi konflik, transaksi aman, dan eksposisi data via PagingSource).
- Ringkasan singkat (1-2 paragraf) analisis performa: Mengapa pemilihan pola *Tombstone* lebih unggul daripada penghapusan langsung (*hard delete*) pada sistem offline-first, dan bagaimana strategi mitigasi bloat (penumpukan baris tabel) dari data tombstone tersebut.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal Room ORM (kapt/KSP generation, DAO Implementation, `SupportSQLiteDatabase`, dan SQLite driver layer).
- [ ] Siklus hidup dan prinsip *Single Source of Truth* (SSOT) pada Data Layer Android.
- [ ] Mekanisme kerja `InvalidationTracker` dan dampaknya terhadap reaktivitas data melalui Kotlin Coroutines `Flow`.
- [ ] SQLite Write-Ahead Logging (WAL) concurrency model, lock types (SHARED, RESERVED, PENDING, EXCLUSIVE), dan dampaknya terhadap transaksi konkuren.
- [ ] Perbedaan fungsional dan implikasi integritas data antara `OnConflictStrategy.REPLACE`, `ABORT`, dan `IGNORE`.
- [ ] Optimasi performa database SQLite: Indexing (`B-Tree`), Covering Indexes, Analisis `EXPLAIN QUERY PLAN`, dan mitigasi *Full Table Scan*.
- [ ] Pola rekonsiliasi sinkronisasi dua arah (*Two-way Sync Reconciliation*), *Optimistic Locking*, dan *Tombstone Pattern*.
- [ ] Teknik migrasi skema database manual (*destructive* vs *non-destructive*), termasuk *Table Recreation Pattern* untuk SQLite schema refactoring.

### Saya tidak perlu menghafal:
- [ ] Seluruh sintaks pembuatan kueri SQLite DDL yang kompleks secara luar kepala (manfaatkan dokumentasi SQLite/Room dan `RoomDatabase.Callback`).
- [ ] Method hashing spesifik atau algoritma internal `room_master_table` yang di-generate otomatis oleh compiler Room.
- [ ] Detail implementasi *binary wire-format* dari SQLite B-Tree pages di level C++.
- [ ] Nomor versi internal Android framework untuk pemetaan versi SQLite native platform.

### Saya harus bisa melakukan:
- [ ] Menulis kueri SQL kompleks pada DAO Room yang mencakup *multi-table JOIN*, agregasi, dan sub-kueri bersarang dengan efisiensi tinggi.
- [ ] Mengonfigurasi composite index (`@Index`) yang tepat pada Entity untuk mengeliminasi bottleneck performa I/O berdasarkan kebutuhan filter dan sorting UI.
- [ ] Mengimplementasikan migrasi skema manual dari satu versi Room ke versi berikutnya tanpa kehilangan data produksi (*zero data-loss migration*).
- [ ] Mengisolasi eksekusi kueri Room ke background dispatcher yang tepat serta mencegah terjadinya *thread starvation* atau *deadlock* pada pemanggilan transaksi bersarang.
- [ ] Mendiagnosis kueri lambat (*slow queries*) menggunakan Android Studio Database Inspector dan mengeksekusi perintah SQLite `EXPLAIN QUERY PLAN`.
- [ ] Merancang dan membangun *Offline-First Repository* tangguh yang menggabungkan Room, Network DataSource, `PagingSource`, dan Background Sync Worker yang tahan terhadap kegagalan jaringan mendadak.