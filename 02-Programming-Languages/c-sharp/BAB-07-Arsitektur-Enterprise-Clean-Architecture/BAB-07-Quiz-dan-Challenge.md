# BAB 07: Quiz, Challenge, & Knowledge Check
**Arsitektur Enterprise & Clean Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Dependency Inversion Principle (DIP) & The Dependency Rule**  
   Dalam Clean Architecture (Robert C. Martin) maupun Onion Architecture (Jeffrey Palermo), aturan dependensi menyatakan bahwa kode tingkat rendah (*low-level details*) harus bergantung pada kode tingkat tinggi (*high-level abstractions*). Jelaskan secara arsitektural mengapa layer **Domain** sama sekali tidak boleh memiliki dependensi proyek (`<ProjectReference>`) terhadap layer **Infrastructure** maupun **Presentation**, dan bagaimana mekanisme *Inversion of Control* (IoC) via *Dependency Injection Container* di ASP.NET Core memungkinkan eksekusi runtime tetap berjalan mulus meskipun kompilasi dependensi berjalan ke arah sebaliknya.

2. **Entity vs. Value Object dalam Konteks Domain-Driven Design (DDD)**  
   Bedakan secara fundamental perbedaan antara *Entity* dan *Value Object* dari perspektif identitas, *mutability*, dan kesetaraan struktural (*structural equality*). Mengapa penggunaan tipe data primitif secara berlebihan (*Primitive Obsession*—misalnya merepresentasikan uang hanya dengan `decimal` atau email dengan `string`) dianggap sebagai pelanggaran prinsip desain domain yang kokoh, dan bagaimana Anda mengimplementasikan Value Object yang aman menggunakan fitur `record` atau custom base class di C#?

3. **Domain Events vs. Integration Events**  
   Jelaskan perbedaan mendasar antara *Domain Event* dan *Integration Event* ditinjau dari batasan konteks (*Bounded Context*), media transport, dan jaminan konsistensi transaksional (*transactional consistency*). Mengapa memicu transmisi pesan ke message broker (seperti RabbitMQ atau Azure Service Bus) secara langsung dari dalam *Domain Entity method* dianggap sebagai *architectural smell* yang berbahaya?

4. **CQRS (Command Query Responsibility Segregation) Trade-offs**  
   Pola CQRS memisahkan jalur eksekusi antara mutasi data (*Command*) dan pembacaan data (*Query*). Jelaskan skenario performa dan skalabilitas di mana model domain relasional berbasis Aggregate Root gagal memberikan throughput optimal untuk operasi *Read/Reporting*. Mengapa memaksakan Aggregate Domain yang sarat logika enkapsulasi untuk query paginasi kompleks dianggap sebagai anti-pattern, dan bagaimana CQRS mengatasi masalah ini?

5. **Repository & Unit of Work di Atas Entity Framework Core: Pattern vs. Anti-Pattern**  
   Banyak pengembang enterprise mengabstraksi EF Core dengan membungkus `DbContext` ke dalam custom `IRepository<T>` dan `IUnitOfWork`. Analisis argumen teknis yang menyatakan bahwa `DbContext` itu sendiri sudah merupakan implementasi konkret dari *Repository* dan *Unit of Work*. Kapan custom generic repository justru menurunkan kapabilitas EF Core (seperti *IQueryable leakage*, *n+1 queries*, dan *eager/explicit loading*), dan pada kondisi arsitektural apa abstraksi repository spesifik (*Explicit/Specific Repository*) tetap esensial?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **DbContext Scoped Lifetime Leakage & Multithreading Race Conditions**  
   Dalam implementasi MediatR pipeline atau custom background worker, seorang developer mengeksekusi operasi asinkron secara paralel menggunakan `Task.WhenAll()` yang di dalamnya memanggil method repository yang menggunakan instance `DbContext` yang sama:
   ```csharp
   var task1 = _orderRepository.GetByIdAsync(orderId);
   var task2 = _customerRepository.UpdateBalanceAsync(customerId, amount);
   await Task.WhenAll(task1, task2);
   ```
   Jelaskan secara internal mengapa EF Core melemparkan `InvalidOperationException: A second operation was started on this context instance before a previous operation completed`. Bagaimana cara Anda mendesain eksekusi paralel yang aman tanpa melanggar *lifetime scope* service di ASP.NET Core?

2. **Dual-Write Hazard & The Transactional Outbox Pattern**  
   Tinjau kode berikut pada Application Command Handler:
   ```csharp
   await _orderRepository.AddAsync(order, cancellationToken);
   await _unitOfWork.SaveChangesAsync(cancellationToken);
   await _messageBus.PublishAsync(new OrderCreatedIntegrationEvent(order.Id), cancellationToken);
   ```
   Identifikasi potensi kegagalan parsial (*dual-write hazard*) pada kode di atas jika server mengalami *unhandled crash* atau *network partition* tepat setelah `SaveChangesAsync` berhasil tetapi sebelum `PublishAsync` dieksekusi. Jelaskan mekanisme internal *Transactional Outbox Pattern* dan peran *background processor* (`IHostedService` atau Worker) dalam menjamin *at-least-once delivery* menggunakan database transaction lokal yang sama.

3. **Enkapsulasi Aggregate Root vs. ORM Materialization**  
   Untuk mencegah anemic domain model, sebuah Aggregate Root harus menutup akses mutasi langsung ke koleksi internalnya (misalnya properti `Items` dalam `Order`). Bagaimana Anda mendesain entitas C# agar properti navigasi hanya terekspos sebagai `IReadOnlyCollection<T>` ke layer luar, namun EF Core tetap dapat melakukan query, change tracking, dan materialisasi data secara internal menggunakan *backing fields* (`private readonly List<OrderItem> _items`) tanpa membutuhkan *public parameterless constructor* yang melanggar invarian bisnis?

4. **Granularitas Pipeline: MediatR IPipelineBehavior vs. ASP.NET Core Middleware**  
   Keduanya mengadopsi pola *Chain of Responsibility*. Jelaskan kriteria keputusan arsitektural untuk menentukan kapan suatu *cross-cutting concern* (seperti Exception Handling, Request Validation via FluentValidation, Performance Profiling, dan Distributed Tracing) harus ditempatkan pada ASP.NET Core Middleware pipeline, dan kapan harus diimplementasikan sebagai MediatR `IPipelineBehavior<TRequest, TResponse>`.

5. **Optimistic Concurrency Control & DbUpdateConcurrencyException Handling**  
   Ketika dua request konkuren mencoba memotong saldo dari Aggregate `Wallet` yang sama secara bersamaan, jelaskan bagaimana EF Core mendeteksi tabrakan data menggunakan *Concurrency Token* (`[Timestamp]` atau konfigurasi `.IsRowVersion()` / PostgreSQL `xmin`). Tuliskan struktur blok proteksi pemulihan (*resiliency strategy*) saat menangani `DbUpdateConcurrencyException` agar sistem tidak langsung mengembalikan HTTP 500 ke klien.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Degradation & Thread Pool Starvation pada Event Flash Sale
Sistem e-commerce skala enterprise mengalami degradasi performa kritis saat flash sale berlangsung. Endpoint `POST /api/v1/orders/checkout` mengalami lonjakan P99 latency dari 120ms menjadi 14 detik, diiringi error `TimeoutException` dan lonjakan CPU hingga 100%. Tim DevOps mendeteksi terjadinya *Thread Pool Starvation*.  
Setelah dilakukan audit profil memori dan kueri:
- Aggregate `Order` memuat seluruh riwayat audit dan entitas relasi bertingkat via eager loading: `.Include(o => o.Items).ThenInclude(i => i.Product).Include(o => o.AuditLogs).Include(o => o.Shipments)`.
- Command Handler mengeksekusi kalkulasi diskon yang lambat, diselingi pemanggilan API eksternal pihak ketiga (Payment Gateway check) secara sinkron menggunakan `.Result` di tengah domain execution.
- Query laporan status order dijalankan bersamaan oleh admin menggunakan Aggregate Root yang sama via tracking query (`AsNoTracking` tidak digunakan).

*Pertanyaan Diagnostik:*
1. Mengapa memuat *Aggregate* yang terlalu besar (*bloated aggregate boundary*) merusak performa throughput EF Core dan bagaimana Anda meredefinisi batasan agregat tersebut?
2. Bagaimana mekanisme terjadinya *Thread Pool Starvation* akibat pencampuran blocking call (`.Result` / `.Wait()`) dengan pemanggilan I/O eksternal, dan apa langkah refactoring-nya?
3. Rancang strategi pemisahan arsitektur (read-side separation) untuk query reporting tanpa mengganggu transactional boundary checkout engine.

---

### Skenario B: Double-Spending Exploit akibat Balapan State Transaksional
Sebuah platform perbankan digital menemukan anomali finansial di mana seorang nasabah berhasil menarik saldo Rp1.000.000 sebanyak dua kali secara simultan dari dua perangkat berbeda, padahal saldo awalnya hanya Rp1.000.000. Saldo akhir di database menunjukkan Rp0 alih-alih terjadinya penolakan pada transaksi kedua.

Kode Domain Application Handler saat ini:
```csharp
public async Task<Result> Handle(WithdrawFundsCommand cmd, CancellationToken ct)
{
    var account = await _accountRepo.GetByIdAsync(cmd.AccountId, ct);
    if (account.Balance < cmd.Amount) 
        return Result.Failure("Insufficient funds");

    account.DeductBalance(cmd.Amount);
    await _unitOfWork.SaveChangesAsync(ct);
    return Result.Success();
}
```

*Pertanyaan Diagnostik:*
1. Jelaskan *race condition* (Check-Then-Act window) yang terjadi pada level isolasi basis data default ketika dua thread mengeksekusi blok kode di atas dalam selang waktu 5 milidetik.
2. Bandingkan dua pendekatan penanganan: **Pessimistic Locking** (misalnya `SELECT ... FOR UPDATE` via raw SQL interceptor EF Core) vs **Optimistic Locking** (via RowVersion token). Kapan Anda memilih salah satunya di sistem finansial?
3. Rancang implementasi *Idempotency Key Pattern* di Application layer untuk mematikan request ganda yang dikirimkan secara identik oleh jaringan/klien yang tidak stabil.

---

### Skenario C: Architectural Drift & Boundary Violation pada Modular Monolith
Perusahaan Anda memiliki aplikasi monolitik enterprise yang sedang dipersiapkan untuk modular monolith menuju microservices. Ditemukan bahwa modul `Billing` langsung mereferensikan modul `Inventory` dan mengeksekusi query LINQ langsung ke tabel milik `Inventory`:
```csharp
// Di dalam BillingService.cs (Modul Billing)
var stock = await _inventoryDbContext.Products
    .Where(p => p.Id == productId)
    .Select(p => p.CurrentStock)
    .FirstOrDefaultAsync();
```
Dampaknya, setiap kali skema database `Inventory` diubah, modul `Billing` mengalami *breaking changes*. Deploy modul tidak dapat dilakukan secara independen, dan batas *Bounded Context* runtuh (*Architectural Drift*).

*Pertanyaan Diagnostik:*
1. Mengapa direct database sharing antar bounded context melanggar prinsip otonomi Clean Architecture, dan apa dampak jangka panjangnya terhadap *database migration* serta *maintainability*?
2. Bagaimana Anda merombak ketergantungan ini menggunakan asynchronous integration events atau synchronous API contract (menggunakan Anti-Corruption Layer / ACL)?
3. Tentukan mekanisme pengujian arsitektur otomatis (misalnya menggunakan pustaka `NetArchTest` di C#) yang dapat dimasukkan ke dalam CI/CD pipeline untuk mencegah developer mengulangi pelanggaran referensi antar modul di masa mendatang.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Order Settlement Engine with Clean Architecture & Outbox Pattern

#### Problem Statement
Anda diminta merancang subsistem inti (*Core Subsystem*) untuk settlement pemesanan barang pada platform e-commerce enterprise. Sistem ini harus mengeliminasi bug data inconsistency, kebal terhadap dual-write failure, mencegah *primitive obsession*, dan memisahkan logika domain secara murni dari framework ORM.

#### Functional & Architectural Requirements
1. **Domain Layer (Pure .NET / Zero External Dependencies):**
   - Aggregate Root: `Order` dengan internal state invariant (State: `Draft`, `Submitted`, `Paid`, `Cancelled`).
   - Value Objects: `Money` (berisi properti `decimal Amount` dan `Currency Currency`), `CustomerId`, dan `OrderId`.
   - Invariant Rules:
     - `Order` tidak boleh di-*Submit* jika total item kosong atau total nilai order bernilai 0 atau negatif.
     - Penambahan item tidak boleh mengekspos koleksi publik (`public IReadOnlyCollection<OrderItem> Items => _items.AsReadOnly();`).
     - Setiap perubahan state valid harus mencatat *Domain Event* internal (misal: `OrderSubmittedDomainEvent`).
2. **Application Layer (CQRS with MediatR & FluentValidation):**
   - Command: `SubmitOrderCommand(Guid OrderId)`
   - Command Handler yang memuat Aggregate dari Repository, memanggil method domain `Submit()`, menyimpan state, dan mengonversi domain event menjadi Outbox record.
   - Validation Pipeline Behavior: Validasi request otomatis via `IPipelineBehavior<TRequest, TResponse>` menggunakan FluentValidation sebelum mencapai Handler.
3. **Infrastructure Layer (EF Core & Outbox Pattern):**
   - Mapping Fluent API untuk Aggregate `Order` menggunakan *backing fields* dan Value Object conversion.
   - Tabel `OutboxMessages` (Id, OccurredOnUtc, Type, Content [JSON], ProcessedOnUtc, Error).
   - Simpan entitas Domain dan pesan Outbox dalam satu transaksi lokal atomik (`SaveChangesAsync`).
   - Background Processor (`BackgroundService`) yang melakukan polling berkala terhadap pesan Outbox yang belum diproses (`ProcessedOnUtc == null`), melakukan simulasi pengiriman ke Message Broker, lalu menandai status pesan secara *idempotent*.

#### Constraints
- Domain layer dilarang mereferensikan pustaka NuGet non-kompiler (tidak boleh ada EF Core, MediatR, atau ASP.NET Core di layer Domain).
- Tidak boleh ada property dengan `public set;` pada Aggregate Root dan Value Objects.
- Seluruh I/O operations harus strictly asynchronous (`async/await` dengan `CancellationToken` propagation).

#### Expected Output
1. Struktur class & record Domain Model (`Order`, `Money`, `OrderId`, `OrderSubmittedDomainEvent`).
2. Konfigurasi Entity Framework Core (Entity Type Configuration dengan Fluent API mapping backing field).
3. Implementasi `SubmitOrderCommandHandler` yang menyimpan aggregate dan outbox message secara atomik.
4. Implementasi `OutboxProcessorBackgroundService` yang aman dari *concurrency lock* dan memory leak.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Aturan mutlak *The Dependency Rule* pada Clean Architecture: dependensi kode hanya boleh mengarah ke dalam (menuju Core Domain).
- [ ] Perbedaan esensial antara Aggregate Root, Entity, Value Object, dan Domain Services dalam taksonomi DDD.
- [ ] Bahaya arsitektural *Primitive Obsession* dan bagaimana Value Objects mengeliminasi invalid state sedini mungkin.
- [ ] Mekanisme kerja CQRS: pemisahan model baca (*denormalized read models*) dan model tulis (*consistent transactional write models*).
- [ ] Risiko fatal *Dual-Write Problem* dalam arsitektur terdistribusi dan cara kerja *Transactional Outbox Pattern* sebagai solusinya.
- [ ] Siklus hidup (*Lifetime Scope*) instance `DbContext` (`Transient`, `Scoped`, `Singleton`) serta implikasinya terhadap *concurrency* dan multithreading.
- [ ] Perbedaan peruntukan antara *Domain Events* (sinkron/in-process via MediatR) dan *Integration Events* (asinkron/out-of-process via Message Broker).
- [ ] Strategi konkurensi data: *Optimistic Concurrency* (RowVersion/ConcurrencyToken) vs *Pessimistic Concurrency* (Locking) pada sistem enterprise.

### Saya tidak perlu menghafal:
- [ ] Seluruh method signature dari Fluent API EF Core (`builder.Property().HasConversion()...`); cukup pahami konsep pemetaan relational-to-object dan backing field mapping.
- [ ] Sintaks exact dari boiler-plate MediatR registration code; cukup pahami mekanisme *Chain of Responsibility* dan pipeline behaviors.
- [ ] Format JSON string payload spesifik dari integration message broker; cukup pahami skema envelope event dan kontraktualnya.

### Saya harus bisa melakukan:
- [ ] Merancang arsitektur solution enterprise .NET dengan pemisahan project yang rigid: `Domain`, `Application`, `Infrastructure`, dan `Presentation/API`.
- [ ] Membangun Domain Model yang kaya (*Rich Domain Model*) dengan *private constructors*, *backing fields*, dan enkapsulasi penuh terhadap state mutation.
- [ ] Mengimplementasikan *Pipeline Behaviors* di MediatR untuk menangani cross-cutting concerns (validasi, transactional execution, logging profiling) secara clean.
- [ ] Mencegah n+1 problem dan memory exhaustion dengan memanfaatkan proyeksi kueri `Select()` langsung ke DTO serta penggunaan `AsNoTracking()` pada jalur Query (CQRS Read Path).
- [ ] Mengimplementasikan *Transactional Outbox Pattern* end-to-end: mulai dari interceptor penyimpanan database lokal hingga pemrosesan pesan via ASP.NET Core `BackgroundService`.
- [ ] Menulis tes arsitektur otomatis (*Architecture Unit Tests*) menggunakan `NetArchTest.Rules` untuk memvalidasi bahwa tidak ada pelanggaran dependensi antar layer pada pull request CI/CD.