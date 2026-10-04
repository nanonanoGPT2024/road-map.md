# BAB 04: Quiz, Challenge, & Knowledge Check
**Data Access with Entity Framework Core & Dapper**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Change Tracker & Identity Map
Jelaskan secara mendalam siklus hidup entitas dalam EF Core (*Detached*, *Unchanged*, *Modified*, *Added*, *Deleted*). Bagaimana mekanisme internal *Snapshot Tracking* bekerja saat metode `SaveChanges()` atau `SaveChangesAsync()` dipanggil, dan mengapa ketiadaan layer *Change Tracker* pada Micro-ORM seperti Dapper menghasilkan throughput dan alokasi memori yang jauh lebih efisien pada skenario pembacaan data berbeban tinggi (*read-heavy*)?

### Soal 1.2: Evaluasi Kueri: Client vs Server Evaluation
Uraikan bagaimana kompilator ekspresi LINQ pada EF Core menerjemahkan `IQueryable<T>` menjadi SQL melalui *Query Translation Pipeline*. Apa dampak struktural dan risiko performa jika sebuah ekspresi LINQ mengandung metode C# yang tidak dapat dipetakan (*unmappable*) ke fungsi bawaan SQL engine? Bandingkan perilaku EF Core versi modern (EF Core 3.0+) terhadap *Client Evaluation* dengan versi *legacy* EF 6.x.

### Soal 1.3: Relational Loading Strategies & Cartesian Explosion
Bandingkan mekanisme eksekusi database dari tiga strategi pemuatan data: *Eager Loading* (`Include`/`ThenInclude`), *Explicit Loading* (`LoadEntryAsync`), dan *Lazy Loading* (via virtual proxies). Kapan penggunaan multiple `.Include()` pada relasi *one-to-many* memicu masalah *Cartesian Product Explosion*, dan bagaimana fitur *Split Queries* (`AsSplitQuery()`) menyelesaikan masalah alokasi bandwidth ini serta apa konsekuensi integritas data yang harus dikorbankan?

### Soal 1.4: Semantik `AsNoTracking` vs `AsNoTrackingWithIdentityResolution`
Analisis perbedaan mendasar antara `AsNoTracking()` dan `AsNoTrackingWithIdentityResolution()`. Jelaskan skenario konkret di mana penggunaan `AsNoTracking()` standar pada kueri yang mengembalikan relasi siklik atau duplikasi entitas anak (*child entities*) justru dapat memicu redundansi alokasi memori objek C#, dan bagaimana *Identity Resolution* memitigasi hal tersebut tanpa mengaktifkan pelacakan mutasi penuh (*full mutation tracking*).

### Soal 1.5: Dynamic Compilation & Plan Caching pada Dapper
Dapper dikenal melakukan kompilasi *dynamic method* berbasis emisi IL (*Intermediate Language Emit*) untuk memetakan `DbDataReader` ke objek POCO C#. Jelaskan bagaimana Dapper mengelola *Query Plan Cache* dan *Type Handler Cache* internalnya secara statis. Bagaimana Dapper menjamin parameterisasi SQL guna menghindari risiko *SQL Injection* sekaligus mengoptimalkan penggunaan kembali *Execution Plan* pada level *Database Engine*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Lifecycle, Thread-Safety, dan Concurrency pada `DbContext`
`DbContext` dirancang dengan siklus hidup *Scoped* dalam ekosistem ASP.NET Core. Mengapa *instance* `DbContext` secara arsitektural tidak bersifat *thread-safe*? Analisis kegagalan internal yang terjadi ketika seorang *engineer* secara tidak sengaja mengeksekusi dua kueri secara bersamaan menggunakan `Task.WhenAll` pada *instance* `DbContext` yang sama, dan jelaskan mengapa implementasi `IDbContextFactory<T>` menjadi solusi mutlak untuk kasus multithreading atau *background processing*.

### Soal 2.2: Interaksi Execution Strategy (Resiliency) dengan Manual Transactions
Ketika mengaktifkan *Connection Resiliency* menggunakan `EnableRetryOnFailure` pada `SqlServerDbContextOptionsBuilder`, mengapa pemanggilan eksplisit `context.Database.BeginTransactionAsync()` langsung melempar `InvalidOperationException`? Jelaskan cara kerja internal dari `IExecutionStrategy` dan demonstrasikan pola implementasi yang benar agar manual transaksi terisolasi tetap dapat memanfaatkan mekanisme *automatic retry*.

### Soal 2.3: Bulk Operations Engine (`ExecuteUpdateAsync` / `ExecuteDeleteAsync`)
Sebelum EF Core 7, operasi pembaruan atau penghapusan 10.000 baris data mengharuskan pemuatan seluruh entitas ke dalam memori (*Change Tracker*) sebelum mengeksekusi instruksi UPDATE/DELETE per baris melalui `SaveChanges()`. Jelaskan mekanisme transformasi SQL langsung yang digunakan oleh metode `ExecuteUpdateAsync` dan `ExecuteDeleteAsync`. Sebutkan limitasi teknis metode ini terhadap *In-Memory Entity State*, *Domain Events*, dan fitur *Audit Trail/Interceptors*.

### Soal 2.4: Diagnostik Database Connection Leaks & Connection Pooling
Dalam aplikasi ASP.NET Core dengan beban tinggi, metrik sistem mendeteksi *spike* pada `TimeoutException: Physical connection is not open` atau *Connection Pool Exhaustion*. Bagaimana Anda mengidentifikasi apakah akar masalah (*root cause*) berada pada kueri yang mengalami *long-running lock*, ketidaksesuaian penanganan `IAsyncEnumerable` / `DbDataReader` yang tidak di-*dispose*, atau kebocoran koneksi manual pada kode Dapper? Sebutkan *diagnostic counter* atau metrik OpenTelemetry standar (.NET Runtime metrics) yang relevan untuk pembuktian ini.

### Soal 2.5: Dynamic Queries, IL Caching Thrashing, dan Memory Leaks
Pada Dapper atau EF Core raw SQL, penyusunan kueri dinamis yang salah dapat merusak performa. Jelaskan bagaimana interpolasi string langsung (bukan parameterisasi) dapat menyebabkan *Memory Leak* dan degradasi CPU pada EF Core *Query Compiler Cache* atau *SQL Server Plan Cache*. Kapan pembuatan kueri menggunakan `SqlBuilder` pada Dapper berisiko menghasilkan *parameter pollution*, dan bagaimana cara mencegah ledakan *ad-hoc compilation* pada level database?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Large-Scale E-Commerce Performance Degradation (Out of Memory & CPU Spike)
* **Konteks:** Sebuah sistem e-commerce berskala nasional mengalami degradasi kritis saat *campaign flash-sale*. CPU database mencapai 100%, dan pod aplikasi ASP.NET Core mengalami terminasi berkala akibat *OOMKilled* (Out Of Memory).
* **Temuan Awal:** Endpoint `/api/v1/orders/report` mengeksekusi kueri EF Core untuk mengambil histori pesanan pelanggan beserta item, diskon, dan log pengiriman:
  ```csharp
  var orders = await _context.Orders
      .Include(o => o.OrderItems)
      .ThenInclude(oi => oi.Product)
      .Include(o => o.ShipmentLogs)
      .Where(o => o.CreatedAt >= startDate)
      .ToListAsync();
  ```
  Data yang ditarik mencapai lebih dari 500.000 entitas *Order* dalam satu rentang tanggal.

#### Pertanyaan Diagnostik & Solusi:
1. Analisis tiga kelemahan arsitektur data access dari kode di atas yang memicu OOM pada aplikasi dan CPU bottleneck pada database engine.
2. Rancang strategi refaktorisasi penuh menggunakan pola **CQRS Hybrid**:
   - Bagaimana Anda mengubah kueri tersebut menggunakan Dapper untuk membaca data langsung secara *streaming* (*unbuffered*)?
   - Tunjukkan bagaimana deserialisasi relasional *parent-child* dilakukan secara efisien menggunakan teknik *Multi-Mapping* (`QueryAsync<Order, OrderItem, Product, Order>`) tanpa membebani *Garbage Collector (Large Object Heap)*.

---

### Skenario B: Double-Spending & Race Condition pada Sistem Inventory
* **Konteks:** Sistem pergudangan terdistribusi melayani reservasi inventaris. Ketika stok suatu barang bernilai `1`, terdapat dua request checkout paralel yang masuk dalam selisih waktu 5 milidetik. Kedua request membaca stok bernilai `1`, memvalidasi ketersediaan, lalu mengurangi stok menjadi `0`. Akibatnya, terjadi *negative stock* atau pemenuhan ganda (*double-allocation*) yang melanggar integritas bisnis.
* **Arsitektur Eksisting:** Aplikasi menggunakan EF Core standar dengan `_context.SaveChangesAsync()`.

#### Pertanyaan Diagnostik & Solusi:
1. Jelaskan mengapa isolasi transaksi default (*Read Committed*) gagal mencegah anomali *Non-Repeatable Read* atau *Write Skew* ini pada sistem data access.
2. Implementasikan dua pendekatan resolusi konkurensi berikut secara mendalam:
   - **Optimistic Concurrency:** Gunakan mekanisme token konkurensi (`[Timestamp]` / `IsRowVersion()`) pada EF Core. Tuliskan kode penanganan *exception* `DbUpdateConcurrencyException` lengkap dengan *retry loop policy*.
   - **Pessimistic Locking:** Rancang kueri SQL menggunakan Dapper atau `FromSqlInterpolated` yang menerapkan *Exclusive Row-Level Lock* (misal: `SELECT ... FOR UPDATE` pada PostgreSQL atau `WITH (UPDLOCK, ROWLOCK)` pada SQL Server) untuk mengamankan data sebelum proses mutasi. Diskusikan *trade-off* latensi dan throughput antara kedua metode ini.

---

### Skenario C: Arsitektur Transaksional Terdistribusi pada Hybrid EF Core & Dapper
* **Konteks:** Tim arsitektur memutuskan untuk memisahkan logika aplikasi: modul *Write/Mutate* menggunakan EF Core karena kebutuhan agregasi *Domain-Driven Design (DDD)* dan *Domain Events*, sedangkan modul *Read/Reporting* intensif menggunakan Dapper. 
* **Masalah:** Terdapat *use-case* bisnis: "Proses Pembayaran Tagihan". Operasi ini harus memperbarui status mutasi pada *ledger table* via EF Core, mengeksekusi stored procedure kompleks legasi via Dapper untuk pembaruan limit kredit, dan memperbarui status akun via EF Core kembali. Seluruh operasi ini harus berada di dalam batas atomik tunggal (*Atomic ACID Transaction*). Jika stored procedure Dapper gagal, mutasi EF Core harus dibatalkan (*rollback*).

#### Pertanyaan Diagnostik & Solusi:
1. Mengapa pembuatan `SqlConnection` atau `NpgsqlConnection` baru secara terpisah untuk Dapper di dalam scope yang sama dengan EF Core berisiko memicu eskalasi transaksi menjadi *Distributed Transaction* (2PC/MSDTC) yang lambat dan rapuh?
2. Demonstrasikan arsitektur kode bagaimana EF Core dan Dapper dapat berbagi (*share*) satu koneksi database fisik (`DbConnection`) dan satu konteks transaksi aktif (`DbTransaction`) yang sama tanpa melanggar *lifetime scope* dependensi ASP.NET Core. Tuliskan implementasi konkret kelas atau ekstensi yang menjembatani kedua teknologi tersebut.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Financial Ledger Engine
Rancang dan implementasikan sebuah *Micro-Service Component* berkinerja tinggi bernama **FinancialLedgerEngine** yang menggabungkan keunggulan EF Core (untuk penulisan berbasis aturan domain yang ketat) dan Dapper (untuk agregasi kalkulasi finansial bervolume tinggi).

#### Deskripsi Masalah
Sebuah platform perbankan digital membutuhkan sistem pencatatan transaksi buku besar (*ledger*). Sistem ini menerima lonjakan transaksi kredit/debit secara masif sambil tetap wajib melayani permintaan laporan mutasi dan saldo kalkulatif secara *real-time* tanpa terpengaruh latensi baca-tulis.

#### Batasan & Spesifikasi Teknis (Constraints & Requirements)
1. **Model Domain & Skema:**
   - Entitas: `Account` (Id, AccountNumber, CurrentBalance, RowVersion, IsActive).
   - Entitas: `LedgerEntry` (Id, AccountId, Amount, EntryType [Credit/Debit], Timestamp, ReferenceId).
2. **Write Pipeline (EF Core):**
   - Implementasikan metode `TransferFundsAsync(Guid sourceAccountId, Guid targetAccountId, decimal amount, string referenceId)`.
   - Wajib menerapkan *Optimistic Concurrency Control* pada entitas `Account` menggunakan mekanisme concurrency token.
   - Wajib melakukan validasi saldo tidak boleh negatif sebelum mutasi disimpan.
   - Mutasi penulisan `LedgerEntry` pada kedua akun beserta pembaruan saldo `Account` harus berjalan dalam satu *Database Transaction* atomik.
3. **Read Pipeline (Dapper):**
   - Implementasikan metode `GetAccountStatementStreamAsync(Guid accountId, DateTime fromUtc, DateTime toUtc)`.
   - Menggunakan Dapper untuk mengambil seluruh riwayat `LedgerEntry` secara *streaming* (`IAsyncEnumerable<LedgerEntryDto>`) menggunakan *unbuffered query* (`CommandFlags.None`) guna menjaga stabilitas memori aplikasi di bawah beban jutaan baris.
   - Implementasikan kalkulasi *running balance* langsung secara optimal via SQL *Window Function* (`SUM(...) OVER (PARTITION BY ... ORDER BY ...)`), bukan diolah di dalam memori C#.
4. **Resiliency & Hybrid Transaction Bridge:**
   - Implementasikan *Unit of Work* atau *Transaction Bridge* yang memungkinkan eksekusi kueri Dapper audit di dalam konteks transaksi yang sama yang diinisiasi oleh EF Core `ExecutionStrategy`.
   - Terapkan penanganan *deadlock* (Error 1205 pada SQL Server atau 40P01 pada PostgreSQL) dengan *exponential backoff retry policy*.

#### Output yang Diharapkan
- Satu set file implementasi C# lengkap:
  1. Definisi model entitas dan Fluent API Configuration (`IEntityTypeConfiguration<T>`).
  2. Implementasi antarmuka `ILedgerService` yang mendemonstrasikan metode transfer (EF Core) dan pembacaan statemen (Dapper).
  3. Konfigurasi `DbContext` yang mengekspos koneksi dan transaksi aktif ke Dapper.
- Tidak boleh ada alokasi *Cartesian Product*, tidak boleh ada *blocking calls* (`.Result` atau `.Wait()`), dan parameterisasi kueri wajib 100% aman dari injeksi SQL.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal *Entity Framework Core Query Translation Pipeline*: Parser LINQ, Expression Trees, Relational Query Translators, dan SQL Generators.
- [ ] Mekanisme kerja *Change Tracker*: pelacakan berbasis *Snapshot* vs *Notification*, siklus hidup entitas, dan kompleksitas komputasional pemanggilan `DetectChanges()`.
- [ ] Mengapa Dapper secara konsisten memiliki jejak memori (*allocation footprint*) lebih rendah dibanding EF Core (pemanfaatan IL Emit, pembacaan serial dari `DbDataReader`, tanpa metadata identity tracking).
- [ ] Tingkat isolasi database (Read Uncommitted, Read Committed, Repeatable Read, Serializable, Snapshot) serta korelasinya terhadap anomali pembacaan dan metode penguncian di level ORM.
- [ ] Risiko dan mitigasi *Cartesian Explosion* pada relasi multi-level dalam ORM, serta pemanfaatan `AsSplitQuery()`.
- [ ] Batasan dan arsitektur pengoperasian bulk SQL mutations (`ExecuteUpdate` / `ExecuteDelete`) tanpa melalui konteks *in-memory tracker*.

### Saya tidak perlu menghafal:
- [ ] Seluruh nama metode konfigurasi spesifik pada Fluent API; dokumentasi resmi dapat diakses kapan saja untuk sintaks spesifik penyedia database.
- [ ] Kode numerik spesifik untuk seluruh *SQL Server/PostgreSQL Error Codes* (cukup mengetahui kategori error untuk konkurensi, deadlock, dan koneksi transien).
- [ ] Implementasi internal kode byte-emitting (OpCodes) Dapper; cukup memahami cara kerja dan batasan *Type Handler* serta siklus hidup pemetaan (*mapping life-cycle*).

### Saya harus bisa melakukan:
- [ ] Menganalisis dan membaca hasil *Execution Plan* dari kueri SQL yang dihasilkan oleh EF Core menggunakan profiling tools seperti SQL Server Profiler, PostgreSQL `EXPLAIN ANALYZE`, atau EF Core Simple Logging/MiniProfiler.
- [ ] Mengonfigurasi dan mengimplementasikan arsitektur akses data Hybrid (EF Core + Dapper) yang berbagi satu `DbConnection` dan `DbTransaction` aktif secara aman tanpa memicu kebocoran koneksi (*connection leaks*).
- [ ] Menyelesaikan permasalahan N+1 Query pada sistem skala besar menggunakan *Eager Loading*, *Projection Parsing*, atau optimasi Dapper multi-mapping.
- [ ] Menerapkan mekanisme mitigasi konkurensi tingkat lanjut menggunakan *Optimistic Locking* (via concurrency token) maupun *Pessimistic Locking* (via raw SQL dialect locking) secara tepat sesuai kebutuhan bisnis.
- [ ] Melakukan diagnostik *Connection Pool Exhaustion* di lingkungan server produksi menggunakan *dotnet-counters*, OpenTelemetry, atau database server activity monitors.