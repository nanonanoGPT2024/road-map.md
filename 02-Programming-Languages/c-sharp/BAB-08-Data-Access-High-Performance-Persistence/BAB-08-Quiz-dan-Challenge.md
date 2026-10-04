# BAB 08: Quiz, Challenge, & Knowledge Check
**Data Access & High-Performance Persistence**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Siklus Hidup `DbContext` dan Bahaya Multi-threading**  
   Mengapa instance `DbContext` pada Entity Framework Core secara desain bersifat *non-thread-safe* dan tidak boleh didaftarkan sebagai *Singleton* pada kontainer Dependency Injection (DI) dalam aplikasi web *high-concurrency*? Jelaskan implikasi arsitekturalnya terhadap *Change Tracker*, pembukaan koneksi ADO.NET dasar, serta strategi yang tepat untuk *scoped lifecycle* atau *DbContext pooling* (`IDbContextFactory<T>` / `AddDbContextPool`).

2. **Dekomposisi `IQueryable<T>` vs `IEnumerable<T>`**  
   Secara internal pada runtime C#, bagaimana pipeline evaluasi ekspresi membedakan eksekusi `IQueryable<T>` dan `IEnumerable<T>` ketika melakukan operasi filtering (`.Where()`) dan proyeksi (`.Select()`)? Uraikan peran *Expression Trees*, *Query Provider*, dan kapan tepatnya *materialization point* terjadi ke memori.

3. **Mekanisme Pelacakan Status & Alokasi Memori: `AsNoTracking` vs `AsNoTrackingWithIdentityResolution`**  
   Jelaskan secara mendalam perbedaan alokasi memori, struktur data internal, dan semantik hasil kueri antara `.AsNoTracking()` standar dan `.AsNoTrackingWithIdentityResolution()`. Pada skenario relasional seperti apa `AsNoTracking` biasa dapat menghasilkan duplikasi instance objek di memori (heap), dan kapan Anda wajib beralih ke *identity resolution* tanpa mengorbankan performa pelacakan perubahan?

4. **Tax Abstraction: Komparasi ADO.NET Murni, Dapper, dan EF Core**  
   Evaluasi *computational & allocation cost* dari tiga layer akses data berikut:
   - ADO.NET murni (`DbCommand`, `DbDataReader`)
   - Micro-ORM Dapper
   - Full ORM EF Core (Compiled Query vs Dynamic Linq)  
   Jelaskan bagaimana Dapper mengeliminasi overhead refleksi menggunakan *IL generation*/*DynamicMethod emission*, dan mengapa EF Core memiliki overhead alokasi memori awal yang lebih tinggi meskipun fitur kueri yang dieksekusi identik.

5. **Isolasi Transaksi vs Read Phenomena**  
   Bandingkan level isolasi transaksi SQL standar ANSI/ISO (`Read Uncommitted`, `Read Committed`, `Repeatable Read`, `Serializable`) dan *Snapshot Isolation* (khususnya pada SQL Server / PostgreSQL). Analisis fenomena data (*Dirty Read*, *Non-repeatable Read*, *Phantom Read*, dan *Write Skew*) yang dapat dicegah oleh masing-masing level, serta dampaknya terhadap *pessimistic locking contention* pada engine basis data.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Anatomi Cartesian Explosion vs Eager Loading Splitting**  
   Diberikan sebuah kueri EF Core yang memuat relasi *one-to-many-to-many* (`Customer -> Orders -> OrderItems`) menggunakan multi-level `.Include()`.  
   - Bagaimana SQL engine merespons kueri tunggal yang dihasilkan dan mengapa hal ini memicu degradasi bandwidth jaringan serta saturasi memori (*Cartesian Explosion*)?
   - Kapan penggunaan `.AsSplitQuery()` menjadi penyelamat, dan apa risiko konsistensi data (*race condition / phantom reads*) yang timbul akibat eksekusi multiple round-trip SQL di bawah isolasi default `Read Committed` tanpa transaksi eksplisit?

2. **Deteksi Perubahan Skala Masif: Snapshot vs INotifyPropertyChanged**  
   Saat memanggil `.SaveChanges()`, EF Core mengeksekusi mekanisme *DetectChanges*.  
   - Bagaimana algoritma *Snapshot-based Change Tracking* bekerja secara internal (pembandingan instance asli saat kueri vs state saat ini)?
   - Mengapa proses ini menyebabkan CPU spike dan degradasi performa eksponensial ($O(N)$) ketika memproses ribuan entitas dalam satu konteks?
   - Sebutkan strategi eliminasi overhead tersebut selain memecah unit kerja (misal: implementasi notifikasi proksi, penonaktifan `AutoDetectChangesEnabled`, atau eksekusi *Bulk Operations* via API modern EF Core 7+ `ExecuteUpdate`/`ExecuteDelete`).

3. **Root-Cause Analysis: Database Connection Pool Exhaustion**  
   Aplikasi mikroservis Anda melempar pengecualian:  
   `System.InvalidOperationException: Timeout expired. The timeout period elapsed prior to obtaining a connection from the pool.`  
   Uraikan metodologi diagnostik teknis Anda untuk membuktikan apakah akar masalahnya berada pada:
   - Kebocoran koneksi (*unclosed/un-disposed connections* atau interupsi async).
   - *Thread pool starvation* yang memblokir *callback continuation*.
   - *Query duration/lock escalation* ekstrem di sisi database yang menahan koneksi terlalu lama.

4. **Dapper Unbuffered Streaming vs GC Pressure**  
   Pada Dapper, parameter `buffered: false` pada metode `.QueryAsync<T>` mengubah perilaku materialisasi data:
   - Bagaimana implementasi `IEnumerable<T>` / `IAsyncEnumerable<T>` yang mengonsumsi `DbDataReader` secara streaming memengaruhi penggunaan *Gen 0, Gen 1, Gen 2 Heap*, dan LOH (*Large Object Heap*)?
   - Apa bahayanya membiarkan koneksi fisik terbuka saat pemrosesan *yield return* berlangsung lambat (*slow consumer*), dan apa yang terjadi jika kode konsumen melempar *unhandled exception* sebelum kursor selesai membaca seluruh *result set*?

5. **Interceptors dan Resilience Execution Strategy Deadlock**  
   Ketika mengaktifkan EF Core Execution Strategy bawaan untuk ketahanan koneksi (misal: `EnableRetryOnFailure`), EF Core secara otomatis membungkus operasi dalam blok *retry logic*.  
   - Mengapa inisiasi transaksi manual standar (`context.Database.BeginTransaction()`) akan langsung melempar exception ketika *execution strategy* aktif?
   - Bagaimana cara mengatasi hal tersebut secara arsitektural menggunakan `CreateExecutionStrategy().Execute(...)`, dan bagaimana memastikan operasi non-idempoten (seperti pengiriman pesan via *message broker* di dalam interceptor transaksi) tidak dieksekusi berulang kali saat terjadi transien SQL error?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latensi Tinggi dan Badai Kueri Saat Lonjakan Event Flash Sale
Sistem e-commerce Anda mengalami penurunan throughput drastis saat peluncuran produk terbatas. Dashboard telemetri APM (Application Performance Monitoring) menunjukkan metrik berikut:
- Utilisasi CPU SQL Server melonjak hingga 98%.
- Waktu respons endpoint `/api/v1/orders/checkout` naik dari 45ms ke 12.000ms.
- Teridentifikasi kueri berikut dieksekusi jutaan kali dalam hitungan menit:
  ```sql
  exec sp_executesql N'SELECT TOP(1) [p].[Id], [p].[Stock], [p].[Price] 
  FROM [Products] AS [p] 
  WHERE [p].[Id] = @__productId_0',N'@__productId_0 uniqueidentifier',@__productId_0='...'
  ```
  Diikuti oleh ribuan kueri terpisah untuk validasi kupon, pemeriksaan status akun pengguna, dan perhitungan promo.  
*Pertanyaan Diagnostik:*
1. Identifikasi anti-pattern akses data yang sedang terjadi pada kode C#.
2. Rancang refaktorisasi arsitektur data access untuk mengubah transaksi ini dari *chatty round-trips* menjadi eksekusi batch terpadu berkinerja tinggi (evaluasi penggunaan ADO.NET `DbBatch`, stored procedure, atau evaluasi kueri terkompilasi multi-result EF Core/Dapper).
3. Bagaimana Anda melindungi stok produk dari kondisi overselling pada volume transaksi konkuren tinggi tanpa mengunci tabel secara menyeluruh (*table lock*)?

### Skenario B: Race Condition dan Lost Update pada Sistem Saldo Dompet Digital
Layanan *fintech core-ledger* berbasis .NET menerima dua request transfer dana secara simultan untuk akun dompet digital yang sama dari dua channel berbeda (API Payment Gateway dan Scheduled Direct Debit). Saldo awal akun adalah Rp 1.000.000.  
- Request 1: Mengurangi saldo Rp 700.000.
- Request 2: Mengurangi saldo Rp 500.000.  
*Insiden:* Kedua request berhasil dieksekusi secara konkuren, saldo akhir tercatat menjadi Rp 300.000, dan sistem mengalami kerugian finansial karena transaksi kedua seharusnya ditolak (*insufficient funds*). Kode yang ada menggunakan EF Core standar dengan alur: *Read Entity -> Mutasi Properti Saldo di C# -> SaveChangesAsync()*.  
*Pertanyaan Diagnostik:*
1. Mengapa mekanisme isolasi database default tidak mencegah anomali *Lost Update* pada alur *read-modify-write* terdistribusi tersebut?
2. Berikan dua solusi arsitektur C# konkret untuk memitigasi anomali ini:
   - **Solusi 1 (Optimistic Concurrency Control):** Menggunakan token konkurensi (`RowVersion` / `xmin`) dan bagaimana skema penanganan *retry logic*-nya di layer aplikasi saat `DbUpdateConcurrencyException` terpental.
   - **Solusi 2 (Pessimistic Locking / Atomic Mutation):** Menggunakan SQL *atomic decrement* dengan komparasi predikat (misal: `UPDATE Wallets SET Balance = Balance - @Amount WHERE Id = @Id AND Balance >= @Amount`) via Dapper/EF Core ExecuteUpdate. Bandingkan trade-off latensi dan throughput di antara keduanya.

### Skenario C: Bottleneck Ingestion Log Audit & Telemetri Berkecepatan Tinggi
Sistem perbankan mewajibkan penulisan log transaksi audit yang tidak dapat diubah (*immutable ledger*) ke database relasional dengan laju throughput 15.000 rekaman per detik. Penggunaan EF Core `await context.AuditLogs.AddRangeAsync(logs); await context.SaveChangesAsync();` mengakibatkan:
- Latensi pemrosesan batch mencapai puluhan detik.
- Pertumbuhan drastis pada Gen 2 Heap dan memori aplikasi mencapai batas OOM (*Out Of Memory*).
- Transaksi audit memblokir alur bisnis utama (*thread blocking*).  
*Pertanyaan Diagnostik:*
1. Mengapa pendekatan ORM standar gagal total untuk skenario ingestion data throughput tinggi (*bulk write*)?
2. Rancang arsitektur persistensi data berkinerja tinggi menggunakan C# yang memanfaatkan komponen *Zero-Allocation* / *Streaming Ingestion*. Jelaskan implementasi konkret menggunakan:
   - Pola Producer-Consumer berbasis `System.Threading.Channels.Channel<T>`.
   - Driver level bulk copy API (seperti `SqlBulkCopy` untuk SQL Server atau `NpgsqlBinaryImporter` untuk PostgreSQL).
   - Penataan memori dengan `ArrayPool<T>` atau `Memory<T>` guna meminimalkan GC pauses selama proses ingestion.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Batch Order Ingestion & Audit Pipeline Engine
Anda diminta merancang subsistem ingestion data transaksional hybrid (EF Core + Dapper/ADO.NET murni) berkinerja tinggi yang mampu menelan lonjakan data pesanan berskala enterprise.

#### Problem Statement
Sistem backend sering menerima file/payload JSON terkompresi berisi hingga 50.000 entitas pesanan beserta detail itemnya yang harus divalidasi, disimpan ke dalam database transaksional, memperbarui agregat inventaris, dan mencatat jejak audit secara atomik dengan latensi sekecil mungkin dan footprint memori terkontrol.

#### Requirements
1. **Hybrid Persistence Architecture:**
   - Gunakan **EF Core** untuk query konfigurasi domain dan validasi aturan bisnis yang kompleks.
   - Gunakan **ADO.NET `DbBatch`** (atau driver-specific streaming seperti `SqlBulkCopy` / `NpgsqlBinaryImporter`) untuk proses eksekusi penulisan massal 50.000 rekaman (Orders & OrderLines). Dilarang keras melakukan loop `Insert` individual ataupun `AddRange` standar EF Core untuk data ingestion masif.
2. **Atomic Inventory Mutation:**
   - Pembaruan kuantitas inventaris produk harus dieksekusi secara atomik dan terproteksi dari *negative inventory anomaly* tanpa memicu database *deadlock* (Deadlock Graph Resolution).
3. **Resilience & Transaction Management:**
   - Terapkan mekanisme transaksi eksplisit yang mengisolasi kegagalan parsing parsial: jika satu batch gagal pada level integritas referensial, transaksi harus di-rollback secara utuh tanpa meninggalkan koneksi *dangling*.
   - Integrasikan *retry policy* berbasis eksponensial (via Poly atau custom execution strategy) yang secara spesifik hanya menangani error transien (koneksi terputus, timeout singkat, atau deadlock victim SQL error 1205).
4. **Memory & Concurrency Management:**
   - Manfaatkan `Channel<T>` bounded untuk memisahkan proses penerimaan data dari proses penulisan ke database guna mencegah konsumsi memori tak terbatas.
   - Hindari alokasi array besar berulang dengan memanfaatkan `ArrayPool<T>` saat menyusun *buffer* parameter kueri.

#### Constraints
- Target konsumsi memori puncak (Peak Working Set RAM) selama memproses batch 50.000 rekaman: **< 150 MB**.
- Maksimum durasi pemrosesan dari penerimaan batch hingga transaksi committed: **< 3.500 ms**.
- P99 Database Connection Acquisition Time: **< 10 ms** (tidak boleh ada pool starvation).
- Driver target: Microsoft SQL Server (`Microsoft.Data.SqlClient`) atau PostgreSQL (`Npgsql`).

#### Expected Output
1. **Source Code Implementation:**
   - Class pipeline ingestion lengkap yang mengimplementasikan `IAsyncDisposable`.
   - Implementasi eksekusi kueri berkinerja tinggi (metode penulisan batch murni).
   - Implementasi penanganan konkurensi stok (Atomic conditional update).
2. **Benchmark & Profiling Evidence Setup:**
   - Blok harness testing menggunakan `BenchmarkDotNet` yang membandingkan:
     - Pendekatan Naif: `EF Core AddRangeAsync() + SaveChangesAsync()`
     - Pendekatan Teroptimasi: *Custom Streaming Bulk Architecture*
   - Pelaporan metrik: Eksekusi Waktu (*Mean*), Alokasi Memori (*Allocated Bytes*), dan Frekuensi Koleksi GC (*Gen 0, 1, 2*).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal ADO.NET (`DbProviderFactory`, pooling allocator, TDS/Postgres wire-protocol frame serialization).
- [ ] Siklus hidup, arsitektur metadata, dan struktur state machine internal pada EF Core `ChangeTracker`.
- [ ] Perbedaan fundamental antara pohon ekspresi (`Expression<Func<T, bool>>`) dan delegasi runtime (`Func<T, bool>`) pada proses translasi SQL.
- [ ] Mekanisme pemetaan memori internal Dapper (FastMember, Dynamic Method Emit, cache hash query plan).
- [ ] Level isolasi transaksi ANSI/ISO, Snapshot Isolation, Lock Escalation, dan penanganan status Deadlock pada DBMS relasional.
- [ ] Dampak pembacaan data *buffered* vs *unbuffered* (streaming) terhadap siklus hidup memori Garbage Collector.
- [ ] Implikasi performa translasi kueri kompleks: Cartesian Product, Splitting Queries, Subquery Pushdown, dan Client-side Evaluation.

### Saya tidak perlu menghafal:
- [ ] Seluruh property string konfigurasi koneksi (`Connection String`) untuk setiap variasi database engine.
- [ ] Nilai byte/heksadesimal error code spesifik database vendor (cukup mengetahui kategori exception dan cara mengabstraksinya via driver abstraction).
- [ ] Seluruh method signature dari Fluent API EF Core untuk konfigurasi pemetaan schema yang jarang digunakan.
- [ ] Sintaks exact dari internal metadata builder methods saat mendefinisikan model relational secara manual.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan mengeliminasi masalah N+1 Query serta Cartesian Explosion menggunakan profiler (EF Core Logging, MiniProfiler, OpenTelemetry, atau SQL Server Profiler).
- [ ] Mengimplementasikan *Optimistic Concurrency Control* yang tangguh dengan token versioning (`RowVersion`/`Timestamp`/`xmin`) beserta alur *retry logic* teruji.
- [ ] Menulis kueri data berkecepatan tinggi memanfaatkan Dapper untuk jalur agregasi (Read-side CQRS) dan EF Core untuk jalur domain (Write-side CQRS).
- [ ] Mengkonfigurasi `DbContextPool` dan mengaudit kebocoran koneksi (*connection leak*) melalui analisis metrik `.NET EventCounters` (`Active Connections`, `Queued Commands`).
- [ ] Mengimplementasikan ingestion data masif menggunakan API native database bulk-copy (`SqlBulkCopy` / `NpgsqlBinaryImporter`) atau `DbBatch` dengan penggunaan memori yang minim (*near-zero allocation*).
- [ ] Menganalisis *Execution Plan* database untuk mengoptimalkan kueri yang digenerate oleh Linq Provider, termasuk penambahan *Index Hint*, *Filtered Index*, atau restrukturisasi Linq Expression.