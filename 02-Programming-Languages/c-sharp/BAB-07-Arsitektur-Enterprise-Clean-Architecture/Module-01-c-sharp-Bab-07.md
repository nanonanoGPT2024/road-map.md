# Bab 07 Module 01: Arsitektur Enterprise & Clean Architecture

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran**: Pemrograman Tingkat Lanjut & Rekayasa Perangkat Lunak Enterprise
* **Kategori**: `02-Programming-Languages`
* **Bahasa**: C# (.NET 8 LTS / C# 12)
* **Topik**: Arsitektur Enterprise & Clean Architecture (Hexagonal / Onion / Ports & Adapters)
* **Tingkat Kesulitan**: Tingkat Lanjut (Advanced)
* **Prasyarat**: Pemahaman mendalam tentang Object-Oriented Programming (OOP), Prinsip SOLID, Asynchronous Programming (`async`/`await`), Entity Framework Core, dan dasar-dasar ASP.NET Core Web API.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis & Menguraikan Dependensi**: Mengisolasi *Business Logic* murni dari *I/O framework*, basis data, dan pustaka eksternal dengan menerapkan *The Dependency Rule*.
2. **Merancang Solusi Berbasis Lapisan (Layered Architecture)**: Mengonstruksi struktur solusi .NET multi-proyek yang memisahkan tanggung jawab menjadi `Domain`, `Application`, `Infrastructure`, dan `Presentation`.
3. **Mengimplementasikan Domain-Driven Building Blocks**: Membangun *Entities*, *Value Objects*, *Aggregates*, dan *Domain Events* menggunakan fitur modern C# 12 tanpa ketergantungan pada dependensi eksternal.
4. **Menerapkan CQRS & MediatR Pipeline**: Menata logika aplikasi menggunakan Command-Query Separation serta membangun cross-cutting concerns (validasi, logging, transaksi) melalui Pipeline Behaviors.
5. **Menerapkan Dependency Inversion Principle (DIP)**: Mendefinisikan port (antarmuka/abstraksi) pada layer dalam dan adapter (implementasi) pada layer luar menggunakan pustaka Inversion of Control (IoC) bawaan .NET.
6. **Mengevaluasi Trade-Offs Arsitektural**: Menimbang kompleksitas Clean Architecture terhadap monolit sederhana/Vertical Slice Architecture secara objektif berdasarkan kebutuhan domain bisnis.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Analogi: Benteng Konsentris (Concentric Fortress)

Bayangkan sebuah benteng kuno yang dirancang untuk melindungi inti kekaisaran:

```
[ Lapisan 4: Tembok Luar / Pelabuhan (Presentation / UI / API / Controllers) ]
         │ (Tunduk pada)
         ▼
[ Lapisan 3: Barak Militer & Pengrajin (Infrastructure / DB / 3rd Party APIs) ]
         │ (Mengimplementasikan kontrak)
         ▼
[ Lapisan 2: Dewan Strategis Kerajaan (Application / Use Cases / CQRS) ]
         │ (Mengatur & mengeksekusi)
         ▼
[ Lapisan 1: Ruang Mahkota & Konstitusi (Domain / Entities / Value Objects) ]
```

* **Ruang Mahkota (Domain)**: Berisi hukum fundamental kekaisaran. Hukum ini tidak peduli apakah pedagang di luar datang naik kuda atau kereta uap. Jika sistem perbankan Anda menyatakan "Saldo tidak boleh negatif", aturan ini berlaku mutlak tanpa peduli apakah data disimpan di SQL Server, MongoDB, atau file teks.
* **Dewan Strategi (Application)**: Menentukan alur skenario: *"Ketika nasabah mentransfer dana, periksa saldo, kurangi rekening sumber, tambahkan rekening tujuan, dan terbitkan notifikasi"*. Dewan ini tahu *kapan* dan *apa*, tetapi tidak tahu *bagaimana data fisik ditulis ke disk*.
* **Barak & Pengrajin (Infrastructure)**: Perkakas teknis. EF Core, Redis, SMTP Server, AWS S3. Mereka tidak menentukan aturan; mereka hanya mengeksekusi instruksi teknis sesuai kontrak yang ditetapkan dewan kerajaan.
* **Gerbang Luar (Presentation)**: Titik interaksi dengan dunia luar. HTTP API, gRPC, CLI, atau Blazor UI. Presentation menerjemahkan sinyal luar (HTTP POST JSON) menjadi bahasa yang dipahami dewan kerajaan (Command/Query DTO).

### The Dependency Rule (Aturan Ketergantungan Mutlak)

> **Kode pada lapisan dalam TIDAK BOLEH mengetahui apa pun tentang lapisan luar.** 

Arah referensi proyek pada berkas `.csproj` **hanya boleh mengarah ke dalam**:

$$\text{Presentation} \longrightarrow \text{Application} \longleftarrow \text{Infrastructure}$$
$$\text{Application} \longrightarrow \text{Domain}$$
$$\text{Infrastructure} \longrightarrow \text{Domain}$$

Domain berada di puncak isolasi; ia tidak mereferensikan proyek apa pun dan tidak mengimpor pustaka pihak ketiga di luar BCL (Base Class Library) .NET murni.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram Struktur Proyek Solusi (.NET Solution Architecture)

```
Solution: EnterpriseBanking
│
├── src/
│   ├── EnterpriseBanking.Domain/             [Class Library - Zero External Dependencies]
│   │   ├── Common/ (BaseEntity, ValueObject, IDomainEvent)
│   │   ├── Entities/ (Account, Transaction)
│   │   ├── ValueObjects/ (Money, Currency)
│   │   ├── Exceptions/ (DomainRuleViolationException)
│   │   └── Events/ (MoneyDepositedEvent)
│   │
│   ├── EnterpriseBanking.Application/        [Class Library - References: Domain]
│   │   ├── Common/
│   │   │   ├── Interfaces/ (IApplicationDbContext, IEmailService)
│   │   │   ├── Behaviors/ (ValidationBehavior, LoggingBehavior)
│   │   │   └── Models/ (Result, Error)
│   │   └── Accounts/
│   │       ├── Commands/CreateAccount/
│   │       └── Queries/GetAccountBalance/
│   │
│   ├── EnterpriseBanking.Infrastructure/     [Class Library - References: Application, Domain]
│   │   ├── Persistence/
│   │   │   ├── ApplicationDbContext.cs
│   │   │   └── Configurations/ (AccountConfiguration.cs)
│   │   ├── Services/ (SmtpEmailService.cs, DateTimeService.cs)
│   │   └── DependencyInjection.cs
│   │
│   └── EnterpriseBanking.Presentation.Api/   [ASP.NET Core Web API - References: Application, Infrastructure]
│       ├── Controllers/ or Endpoints/
│       ├── Middlewares/ (ExceptionHandlingMiddleware.cs)
│       └── Program.cs (Composition Root)
```

### Diagram Alur Eksekusi Data: Runtime vs Compile-time Inversion

```
[HTTP POST /api/accounts]
        │
        ▼
[Presentation: Minimal API / Controller]
        │ Menerjemahkan JSON ke
        ▼ CreateAccountCommand
[Application: MediatR Pipeline]
        │ 1. LoggingBehavior
        │ 2. ValidationBehavior (FluentValidation)
        ▼
[Application: CreateAccountCommandHandler]
        │ 1. Panggil Domain: Account.Create(...)
        │ 2. Simpan via Port: IApplicationDbContext.Accounts.Add(...)
        ▼
[Infrastructure: EF Core ApplicationDbContext] (Mengimplementasikan IApplicationDbContext)
        │
        ▼
[Database: PostgreSQL / SQL Server]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Komponen Lapisan Domain (The Core)
* **Entities**: Objek yang memiliki identitas unik (`Id`) yang persisten sepanjang waktu. Kesamaan dua entitas diukur dari kesamaan identitasnya, bukan nilai atributnya.
* **Value Objects**: Objek yang tidak memiliki identitas konseptual dan bersifat *immutable*. Kesamaan diukur berdasarkan kesamaan seluruh nilainya (struktur struktural). Contoh: `Money (Amount, Currency)`.
* **Aggregates & Aggregate Roots**: Kluster entitas dan nilai objek yang diperlakukan sebagai satu kesatuan dalam transaksi perubahan data. Aggregate Root bertanggung jawab penuh menjaga invariant (aturan bisnis) di dalam batasannya.
* **Domain Events**: Peristiwa eksplisit yang telah terjadi di dalam domain yang penting bagi domain itu sendiri atau domain lain (contoh: `OrderCancelledEvent`).

### 2. Komponen Lapisan Application (Use Cases)
* **Commands & Queries (CQRS)**: Memisahkan operasi mutasi (State Changing) dari operasi pembacaan (Read-only Projection).
* **Ports (Interfaces)**: Abstraksi untuk semua kebutuhan eksternal. Application membutuhkan penyimpanan? Buat `IAccountRepository` atau `IApplicationDbContext`. Application butuh jam server? Buat `IDateTimeProvider`.
* **Pipeline Behaviors**: Mirip middleware ASP.NET Core, tetapi bekerja pada tingkat *message bus* aplikasi internal (MediatR), menangani otentikasi use case, validasi, telemetri, dan isolasi transaksi.

### 3. Komponen Lapisan Infrastructure (Adapters)
* **Data Access**: Konfigurasi EF Core `DbContext`, Database Migrations, Dapper queries, atau Redis cache implementations.
* **External Adapters**: Klien Stripe, SendGrid, Message Broker (RabbitMQ/Kafka) producers dan consumers.
* **Composition Root**: Registrasi dependency injection (`IServiceCollection`) untuk semua layanan infrastructure.

### 4. Mekanisme Boundary Crossing (Menyeberangi Batas Arsitektural)
Ketika data mengalir melintasi batas lapisan, konversi format data mutlak diperlukan untuk mencegah kebocoran abstraksi:
* **Presentation $\to$ Application**: Menggunakan *Request Transfer Object* / *Command*.
* **Application $\to$ Domain**: Menggunakan nilai primitif terkonstruksi atau domain factory methods.
* **Domain $\to$ Application**: Domain mengembalikan *Aggregate* atau *Event*. Application memetakannya ke *Result DTO*.
* **Application $\to$ Presentation**: Application merespons dalam bentuk `Result<T>` atau response DTO murni (bukan domain entity langsung).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Anemic Domain Model vs Rich Domain Model

Dalam arsitektur prosedural konvensional (anti-pattern yang sering terjadi), programmer sering membuat kelas domain yang hanya berisi *getter* dan *setter* publik:

```csharp
// ANTI-PATTERN: Anemic Domain Model (Hanya tas data bodoh)
public class Account
{
    public Guid Id { get; set; }
    public decimal Balance { get; set; }
    public bool IsLocked { get; set; }
}
```

Logika bisnis akhirnya tersebar di Controller atau Service:

```csharp
// Logika bocor keluar dari domain
if (!account.IsLocked && account.Balance >= amount) {
    account.Balance -= amount;
}
```

Dalam **Clean Architecture**, model domain wajib berupa **Rich Domain Model**. Enkapsulasi dijaga secara absolut. *Mutasi data hanya dapat dilakukan melalui metode internal yang mengeksekusi aturan invarian bisnis*:

```csharp
// CLEAN PATTERN: Rich Domain Model (Mengeksekusi Invariant Sendiri)
public sealed class Account : AggregateRoot<AccountId>
{
    public Money Balance { get; private set; }
    public bool IsLocked { get; private set; }

    private Account(AccountId id, Money initialBalance) : base(id)
    {
        Balance = initialBalance;
        IsLocked = false;
    }

    public static Result<Account> Create(Money initialBalance)
    {
        if (initialBalance.Amount < 0)
            return Result.Failure<Account>(AccountErrors.NegativeInitialBalance);

        return Result.Success(new Account(new AccountId(Guid.NewGuid()), initialBalance));
    }

    public Result Debit(Money amount)
    {
        if (IsLocked)
            return Result.Failure(AccountErrors.AccountIsLocked);

        if (Balance.Amount < amount.Amount)
            return Result.Failure(AccountErrors.InsufficientFunds);

        Balance = Balance.Subtract(amount);
        RaiseDomainEvent(new AccountDebitedDomainEvent(Id, amount.Amount));
        return Result.Success();
    }
}
```

### Dependency Inversion Principle: Detail Depend on Abstractions

Perhatikan arah dependensi kompilasi vs aliran kontrol runtime:

1. **Compile-Time**: Proyek `Application` memiliki antarmuka `INotificationService`. Proyek `Infrastructure` memiliki kelas `EmailNotificationService` yang mengimplementasikan `INotificationService`. `Infrastructure` mereferensikan `Application`.
2. **Runtime**: ASP.NET Core Service Provider menginstansiasi `EmailNotificationService` dan menyuntikkannya ke `ProcessOrderCommandHandler` yang berada di `Application`. Aliran kontrol berjalan dari Application ke Infrastructure, tetapi arah dependensi kode tetap mengarah ke dalam (Application tidak tahu implementasi konkret apa yang digunakan).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL (Step-by-Step)

Kita akan membangun implementasi modular fundamental: Sistem Transfer Finansial.

### 1. Domain Layer: Value Object & Entity

```csharp
// Path: src/EnterpriseBanking.Domain/Common/ValueObject.cs
namespace EnterpriseBanking.Domain.Common;

public abstract class ValueObject : IEquatable<ValueObject>
{
    protected abstract IEnumerable<object> GetEqualityComponents();

    public override bool Equals(object? obj) =>
        obj is ValueObject other && Equals(other);

    public bool Equals(ValueObject? other) =>
        other is not null && GetEqualityComponents().SequenceEqual(other.GetEqualityComponents());

    public override int GetHashCode() =>
        GetEqualityComponents()
            .Select(x => x.GetHashCode())
            .Aggregate((x, y) => x ^ y);

    public static bool operator ==(ValueObject? left, ValueObject? right) => Equals(left, right);
    public static bool operator !=(ValueObject? left, ValueObject? right) => !Equals(left, right);
}
```

```csharp
// Path: src/EnterpriseBanking.Domain/ValueObjects/Money.cs
namespace EnterpriseBanking.Domain.ValueObjects;

using EnterpriseBanking.Domain.Common;

public sealed class Money : ValueObject
{
    public decimal Amount { get; }
    public string Currency { get; }

    private Money(decimal amount, string currency)
    {
        Amount = amount;
        Currency = currency;
    }

    public static Money Create(decimal amount, string currency)
    {
        if (string.IsNullOrWhiteSpace(currency) || currency.Length != 3)
            throw new ArgumentException("Currency code must be a 3-letter ISO code.", nameof(currency));

        return new Money(amount, currency.ToUpperInvariant());
    }

    public Money Add(Money other)
    {
        if (Currency != other.Currency)
            throw new InvalidOperationException($"Cannot add {other.Currency} to {Currency}.");

        return new Money(Amount + other.Amount, Currency);
    }

    public Money Subtract(Money other)
    {
        if (Currency != other.Currency)
            throw new InvalidOperationException($"Cannot subtract {other.Currency} from {Currency}.");

        return new Money(Amount - other.Amount, Currency);
    }

    protected override IEnumerable<object> GetEqualityComponents()
    {
        yield return Amount;
        yield return Currency;
    }
}
```

```csharp
// Path: src/EnterpriseBanking.Domain/Entities/BankAccount.cs
namespace EnterpriseBanking.Domain.Entities;

using EnterpriseBanking.Domain.ValueObjects;

public sealed class BankAccount
{
    public Guid Id { get; private set; }
    public string AccountNumber { get; private set; }
    public Money Balance { get; private set; }
    public uint Version { get; private set; } // Optimistic Concurrency Control

    private BankAccount() { } // Diperlukan oleh EF Core

    public BankAccount(Guid id, string accountNumber, Money initialDeposit)
    {
        Id = id;
        AccountNumber = accountNumber ?? throw new ArgumentNullException(nameof(accountNumber));
        Balance = initialDeposit ?? throw new ArgumentNullException(nameof(initialDeposit));
    }

    public void Withdraw(Money amount)
    {
        if (Balance.Amount < amount.Amount)
            throw new InvalidOperationException("Saldo tidak mencukupi untuk melakukan penarikan.");

        Balance = Balance.Subtract(amount);
    }

    public void Deposit(Money amount)
    {
        Balance = Balance.Add(amount);
    }
}
```

### 2. Application Layer: Ports & CQRS Command

```csharp
// Path: src/EnterpriseBanking.Application/Common/Interfaces/IBankAccountRepository.cs
namespace EnterpriseBanking.Application.Common.Interfaces;

using EnterpriseBanking.Domain.Entities;

public interface IBankAccountRepository
{
    Task<BankAccount?> GetByIdAsync(Guid id, CancellationToken cancellationToken = default);
    Task UpdateAsync(BankAccount account, CancellationToken cancellationToken = default);
}
```

```csharp
// Path: src/EnterpriseBanking.Application/Common/Interfaces/IUnitOfWork.cs
namespace EnterpriseBanking.Application.Common.Interfaces;

public interface IUnitOfWork
{
    Task<int> SaveChangesAsync(CancellationToken cancellationToken = default);
}
```

```csharp
// Path: src/EnterpriseBanking.Application/Accounts/Commands/TransferMoney/TransferMoneyCommand.cs
namespace EnterpriseBanking.Application.Accounts.Commands.TransferMoney;

public sealed record TransferMoneyCommand(
    Guid SourceAccountId,
    Guid TargetAccountId,
    decimal Amount,
    string Currency
);
```

```csharp
// Path: src/EnterpriseBanking.Application/Accounts/Commands/TransferMoney/TransferMoneyHandler.cs
namespace EnterpriseBanking.Application.Accounts.Commands.TransferMoney;

using EnterpriseBanking.Application.Common.Interfaces;
using EnterpriseBanking.Domain.ValueObjects;

public sealed class TransferMoneyHandler
{
    private readonly IBankAccountRepository _accountRepository;
    private readonly IUnitOfWork _unitOfWork;

    public TransferMoneyHandler(IBankAccountRepository accountRepository, IUnitOfWork unitOfWork)
    {
        _accountRepository = accountRepository;
        _unitOfWork = unitOfWork;
    }

    public async Task HandleAsync(TransferMoneyCommand command, CancellationToken ct = default)
    {
        var source = await _accountRepository.GetByIdAsync(command.SourceAccountId, ct)
            ?? throw new KeyNotFoundException($"Rekening sumber {command.SourceAccountId} tidak ditemukan.");

        var target = await _accountRepository.GetByIdAsync(command.TargetAccountId, ct)
            ?? throw new KeyNotFoundException($"Rekening tujuan {command.TargetAccountId} tidak ditemukan.");

        var transferAmount = Money.Create(command.Amount, command.Currency);

        // Eksekusi mutasi domain
        source.Withdraw(transferAmount);
        target.Deposit(transferAmount);

        // Perbarui state melalui repository
        await _accountRepository.UpdateAsync(source, ct);
        await _accountRepository.UpdateAsync(target, ct);

        // Komit unit transaksi
        await _unitOfWork.SaveChangesAsync(ct);
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Mari kita telaah keputusan teknis dari implementasi Seksi 07:

1. **`ValueObject.cs` (Baris 8: `GetEqualityComponents`)**:
   * Metode abstrak ini memaksa kelas turunan mendefinisikan field penyusun identitas.
   * Menggunakan `yield return` menghasilkan `IEnumerable<object>` yang dievaluasi dengan `SequenceEqual` tanpa perlu refleksi runtime yang lambat.
2. **`Money.cs` (Baris 20-21: `Create` Factory Method)**:
   * Menggunakan *private constructor* dan *static factory method* memastikan tidak ada instance `Money` yang terbuat dengan status mata uang kosong atau tidak valid (menegakkan invarian domain).
3. **`BankAccount.cs` (Baris 11: `public uint Version { get; private set; }`)**:
   * Menyiapkan field konkurensi optimistik. Saat transfer saldo terjadi bersamaan, kolom versi mencegah *race condition* (lost updates) pada level basis data.
4. **`BankAccount.cs` (Baris 13: `private BankAccount() { }`)**:
   * Konstruktor parameter kosong dienkapsulasi privat agar pengembang luar tidak dapat membuat objek instan tanpa parameter valid. Konstruktor ini hanya dibaca oleh EF Core via reflection.
5. **`TransferMoneyHandler.cs` (Baris 18: Injeksi Interface)**:
   * Handler hanya menerima `IBankAccountRepository` dan `IUnitOfWork`. Handler tidak tahu apakah database menggunakan Postgres, CosmosDB, atau in-memory dictionary. Kontrak ini memungkinkan pengujian unit murni tanpa dependensi I/O.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks Produksi: Sistem Manajemen Faktur Enterprise (Enterprise Billing Engine)

Sebuah perusahaan logistik global memproses lebih dari 500.000 pesanan per hari. Permasalahan yang dihadapi sistem lama (Arsitektur Tradisional N-Tier):
1. **Aturan Bisnis Tercecer**: Logika diskon berada di *Stored Procedure* database, validasi limit kredit ada di Controller, dan logika penagihan ada di WCF Services.
2. **Ketergantungan Eksternal Mengunci Domain**: Entity Framework dipasang langsung di Entity data. Ketika sistem migrasi dari .NET Framework 4.8 ke .NET 8, seluruh logika sistem rusak karena terikat erat pada tipe `System.Data.Entity`.
3. **Kegagalan Testing**: Menjalankan integration test untuk sekadar memverifikasi status nota membutuhkan waktu 45 menit karena harus menyalakan *database instance* utuh.

### Solusi Arsitektural Clean Architecture

Sistem dirancang ulang menggunakan Clean Architecture dengan pembagian ketat:
* **Invoice Domain Engine**: Mengisolasi aturan PPh, kalkulasi diskon multi-mata uang, dan siklus status nota (*Draft*, *Issued*, *Paid*, *Overdue*) ke dalam Core Domain Library.
* **MediatR Pipeline**: Memasang pelindung transversal berupa Validasi (FluentValidation), Audit Trail, dan Idempotency.
* **Database Agnostic**: Menggunakan EF Core di infrastructure layer dengan mapping Fluent API murni (tanpa atribut EF pada domain entity).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi skala industri untuk use case **Issue Invoice** menggunakan MediatR Pipeline, Result Pattern, FluentValidation, dan Entity Framework Core Infrastructure Mapping.

### 1. Abstraksi Result Pattern (Application Core)

```csharp
// Path: src/EnterpriseBilling.Domain/Common/Result.cs
namespace EnterpriseBilling.Domain.Common;

public class Result
{
    public bool IsSuccess { get; }
    public bool IsFailure => !IsSuccess;
    public string Error { get; }

    protected Result(bool isSuccess, string error)
    {
        if (isSuccess && !string.IsNullOrEmpty(error))
            throw new InvalidOperationException();
        if (!isSuccess && string.IsNullOrEmpty(error))
            throw new InvalidOperationException();

        IsSuccess = isSuccess;
        Error = error;
    }

    public static Result Success() => new(true, string.Empty);
    public static Result Failure(string error) => new(false, error);
    public static Result<TValue> Success<TValue>(TValue value) => new(value, true, string.Empty);
    public static Result<TValue> Failure<TValue>(string error) => new(default, false, error);
}

public class Result<TValue> : Result
{
    private readonly TValue? _value;

    public TValue Value => IsSuccess
        ? _value!
        : throw new InvalidOperationException("Tidak dapat mengakses data dari result yang berstatus gagal.");

    internal Result(TValue? value, bool isSuccess, string error) : base(isSuccess, error)
    {
        _value = value;
    }
}
```

### 2. Domain: Invoice Entity dengan Lifecycle & Invariant

```csharp
// Path: src/EnterpriseBilling.Domain/Entities/Invoice.cs
namespace EnterpriseBilling.Domain.Entities;

using EnterpriseBilling.Domain.Common;

public enum InvoiceStatus { Draft = 1, Issued = 2, Paid = 3, Cancelled = 4 }

public sealed class Invoice
{
    public Guid Id { get; private set; }
    public string InvoiceNumber { get; private set; } = null!;
    public string CustomerTaxId { get; private set; } = null!;
    public decimal TotalAmount { get; private set; }
    public InvoiceStatus Status { get; private set; }
    public DateTime IssuedAtUtc { get; private set; }

    private Invoice() { } // Ef Core

    public static Result<Invoice> CreateDraft(string invoiceNumber, string customerTaxId, decimal amount)
    {
        if (string.IsNullOrWhiteSpace(invoiceNumber))
            return Result.Failure<Invoice>("Nomor faktur tidak boleh kosong.");

        if (string.IsNullOrWhiteSpace(customerTaxId))
            return Result.Failure<Invoice>("NPWP/Customer Tax ID tidak valid.");

        if (amount <= 0)
            return Result.Failure<Invoice>("Nilai tagihan faktur harus lebih besar dari 0.");

        var invoice = new Invoice
        {
            Id = Guid.NewGuid(),
            InvoiceNumber = invoiceNumber,
            CustomerTaxId = customerTaxId,
            TotalAmount = amount,
            Status = InvoiceStatus.Draft
        };

        return Result.Success(invoice);
    }

    public Result Issue(DateTime currentUtc)
    {
        if (Status != InvoiceStatus.Draft)
            return Result.Failure($"Faktur tidak dapat diterbitkan karena berstatus: {Status}.");

        Status = InvoiceStatus.Issued;
        IssuedAtUtc = currentUtc;

        return Result.Success();
    }
}
```

### 3. Application: Command, Validator, dan Pipeline Behavior

```csharp
// Path: src/EnterpriseBilling.Application/Common/Behaviors/ValidationPipelineBehavior.cs
namespace EnterpriseBilling.Application.Common.Behaviors;

using FluentValidation;
using MediatR;
using EnterpriseBilling.Domain.Common;

public sealed class ValidationPipelineBehavior<TRequest, TResponse> : IPipelineBehavior<TRequest, TResponse>
    where TRequest : IRequest<TResponse>
    where TResponse : Result
{
    private readonly IEnumerable<IValidator<TRequest>> _validators;

    public ValidationPipelineBehavior(IEnumerable<IValidator<TRequest>> validators)
    {
        _validators = validators;
    }

    public async Task<TResponse> Handle(TRequest request, RequestHandlerDelegate<TResponse> next, CancellationToken cancellationToken)
    {
        if (!_validators.Any())
            return await next();

        var context = new ValidationContext<TRequest>(request);
        var validationResults = await Task.WhenAll(
            _validators.Select(v => v.ValidateAsync(context, cancellationToken))
        );

        var failures = validationResults
            .SelectMany(r => r.Errors)
            .Where(f => f != null)
            .ToList();

        if (failures.Count != 0)
        {
            var errorMessage = string.Join(" | ", failures.Select(f => f.ErrorMessage));
            // Mengembalikan generic failure via reflection aman/dynamic
            return (TResponse)Result.Failure(errorMessage);
        }

        return await next();
    }
}
```

```csharp
// Path: src/EnterpriseBilling.Application/Invoices/Commands/IssueInvoice/IssueInvoiceCommand.cs
namespace EnterpriseBilling.Application.Invoices.Commands.IssueInvoice;

using EnterpriseBilling.Domain.Common;
using MediatR;

public sealed record IssueInvoiceCommand(
    string InvoiceNumber,
    string CustomerTaxId,
    decimal Amount
) : IRequest<Result<Guid>>;
```

```csharp
// Path: src/EnterpriseBilling.Application/Invoices/Commands/IssueInvoice/IssueInvoiceCommandValidator.cs
namespace EnterpriseBilling.Application.Invoices.Commands.IssueInvoice;

using FluentValidation;

public sealed class IssueInvoiceCommandValidator : AbstractValidator<IssueInvoiceCommand>
{
    public IssueInvoiceCommandValidator()
    {
        RuleFor(x => x.InvoiceNumber).NotEmpty().MaximumLength(50);
        RuleFor(x => x.CustomerTaxId).NotEmpty().Matches(@"^[0-9]{15,16}$")
            .WithMessage("Customer Tax ID harus terdiri dari 15-16 digit angka.");
        RuleFor(x => x.Amount).GreaterThan(0);
    }
}
```

```csharp
// Path: src/EnterpriseBilling.Application/Common/Interfaces/IApplicationDbContext.cs
namespace EnterpriseBilling.Application.Common.Interfaces;

using EnterpriseBilling.Domain.Entities;
using Microsoft.EntityFrameworkCore;

public interface IApplicationDbContext
{
    DbSet<Invoice> Invoices { get; }
    Task<int> SaveChangesAsync(CancellationToken cancellationToken);
}
```

```csharp
// Path: src/EnterpriseBilling.Application/Invoices/Commands/IssueInvoice/IssueInvoiceCommandHandler.cs
namespace EnterpriseBilling.Application.Invoices.Commands.IssueInvoice;

using EnterpriseBilling.Application.Common.Interfaces;
using EnterpriseBilling.Domain.Common;
using EnterpriseBilling.Domain.Entities;
using MediatR;

public sealed class IssueInvoiceCommandHandler : IRequestHandler<IssueInvoiceCommand, Result<Guid>>
{
    private readonly IApplicationDbContext _context;

    public IssueInvoiceCommandHandler(IApplicationDbContext context)
    {
        _context = context;
    }

    public async Task<Result<Guid>> Handle(IssueInvoiceCommand request, CancellationToken cancellationToken)
    {
        // 1. Instansiasi via Domain Logic
        var invoiceResult = Invoice.CreateDraft(request.InvoiceNumber, request.CustomerTaxId, request.Amount);
        if (invoiceResult.IsFailure)
            return Result.Failure<Guid>(invoiceResult.Error);

        var invoice = invoiceResult.Value;

        // 2. Transisi Status (Business Action)
        var issueResult = invoice.Issue(DateTime.UtcNow);
        if (issueResult.IsFailure)
            return Result.Failure<Guid>(issueResult.Error);

        // 3. Simpan state melalui Abstraksi (Port)
        _context.Invoices.Add(invoice);
        await _context.SaveChangesAsync(cancellationToken);

        return Result.Success(invoice.Id);
    }
}
```

### 4. Infrastructure: EF Core Persistence Configuration

```csharp
// Path: src/EnterpriseBilling.Infrastructure/Persistence/Configurations/InvoiceConfiguration.cs
namespace EnterpriseBilling.Infrastructure.Persistence.Configurations;

using EnterpriseBilling.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

public sealed class InvoiceConfiguration : IEntityTypeConfiguration<Invoice>
{
    public void Configure(EntityTypeBuilder<Invoice> builder)
    {
        builder.ToTable("invoices");

        builder.HasKey(x => x.Id);

        builder.Property(x => x.InvoiceNumber)
            .IsRequired()
            .HasMaxLength(50);

        builder.HasIndex(x => x.InvoiceNumber)
            .IsUnique();

        builder.Property(x => x.CustomerTaxId)
            .IsRequired()
            .HasMaxLength(20);

        builder.Property(x => x.TotalAmount)
            .HasPrecision(18, 4)
            .IsRequired();

        builder.Property(x => x.Status)
            .HasConversion<int>()
            .IsRequired();

        builder.Property(x => x.IssuedAtUtc)
            .IsRequired();
    }
}
```

```csharp
// Path: src/EnterpriseBilling.Infrastructure/Persistence/ApplicationDbContext.cs
namespace EnterpriseBilling.Infrastructure.Persistence;

using EnterpriseBilling.Application.Common.Interfaces;
using EnterpriseBilling.Domain.Entities;
using Microsoft.EntityFrameworkCore;

public sealed class ApplicationDbContext : DbContext, IApplicationDbContext
{
    public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options) : base(options) { }

    public DbSet<Invoice> Invoices => Set<Invoice>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(ApplicationDbContext).Assembly);
        base.OnModelCreating(modelBuilder);
    }
}
```

### 5. Presentation: Minimal API Endpoints (ASP.NET Core .NET 8)

```csharp
// Path: src/EnterpriseBilling.Presentation.Api/Program.cs
using EnterpriseBilling.Application.Accounts.Commands.TransferMoney;
using EnterpriseBilling.Application.Common.Behaviors;
using EnterpriseBilling.Application.Common.Interfaces;
using EnterpriseBilling.Application.Invoices.Commands.IssueInvoice;
using EnterpriseBilling.Infrastructure.Persistence;
using FluentValidation;
using MediatR;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

// --- 1. REGISTRASI INFRASTRUCTURE ---
builder.Services.AddDbContext<ApplicationDbContext>(options =>
    options.UseSqlServer(builder.Configuration.GetConnectionString("Database")));

builder.Services.AddScoped<IApplicationDbContext>(sp => 
    sp.GetRequiredService<ApplicationDbContext>());

// --- 2. REGISTRASI APPLICATION (MediatR & Validators) ---
builder.Services.AddMediatR(cfg => {
    cfg.RegisterServicesFromAssembly(typeof(IssueInvoiceCommand).Assembly);
    cfg.AddOpenBehavior(typeof(ValidationPipelineBehavior<,>));
});

builder.Services.AddValidatorsFromAssembly(typeof(IssueInvoiceCommandValidator).Assembly);

var app = builder.Build();

// --- 3. PRESENTATION ENDPOINTS ---
app.MapPost("/api/invoices", async (IssueInvoiceCommand command, ISender mediator, CancellationToken ct) =>
{
    var result = await mediator.Send(command, ct);

    if (result.IsFailure)
    {
        return Results.BadRequest(new { Error = result.Error });
    }

    return Results.Created($"/api/invoices/{result.Value}", new { Id = result.Value });
});

app.Run();
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Parameter Arsitektur | Clean Architecture | Traditional 3-Tier Layered | Vertical Slice Architecture |
| :--- | :--- | :--- | :--- |
| **Kopling Database** | Sangat Rendah (Abstraksi repository/context interface) | Tinggi (Domain bergantung langsung pada EF/Database schema) | Bervariasi per Feature (Tiap slice bebas menentukan dependensi) |
| **Beban Kognitif / Boilerplate** | **Tinggi** (Banyak mapping, proyek terpisah, DTO, Value Objects) | **Rendah** (Langsung buat Entity, Service, Controller) | **Sedang** (Semua kode fitur dalam satu folder, minim abstraksi) |
| **Testabilitas (Unit Test)** | **Maksimal** (Domain dapat diuji tanpa mocking I/O apa pun) | Sedang (Memerlukan mocking `DbContext` yang kompleks) | Tinggi (Fokus pada integration testing per slice) |
| **Kemudahan Maintenance Skala Besar** | **Sangat Tinggi** (Aturan dependensi menjaga sistem dari spageti kode) | Rendah (Cenderung menjadi "God Services" seiring waktu) | Sangat Tinggi (Perubahan satu fitur terisolasi dari fitur lain) |
| **Waktu Pengerjaan Awal (Time-to-Market)** | **Lambat** (Perlu setup arsitektur fondasi di awal) | **Sangat Cepat** (Langsung coding CRUD) | Cepat (Setup per fitur fleksibel) |
| **Cocok Untuk** | Sistem Enterprise kompleks, core banking, domain jangka panjang | Aplikasi CRUD internal sederhana, PoC, sistem umur pendek | Sistem modular dengan variasi kompleksitas use-case tinggi |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Efisiensi Kueri Data Kompleks (Read Performance vs Aggregates)**:
   * *Problem*: Clean Architecture mendorong penggunaan Domain Entity/Aggregates. Memuat seluruh aggregate root hanya untuk menampilkan data tabel dengan 5 kolom pada halaman UI adalah anti-pattern performa (*N+1 problem* dan overhead alokasi memori).
   * *Mitigasi*: Pisahkan jalur Read (Queries) menggunakan **CQRS**. Pada Query Handler, abaikan Domain Aggregate dan tembak langsung basis data menggunakan Dapper atau `EF Core AsNoTracking()` yang langsung memetakan hasil kueri ke Response DTO (Read Projections).
2. **Penanganan Domain Events di Tengah Transaksi yang Gagal**:
   * *Problem*: Domain event diterbitkan (misalnya mengirim email atau publish message ke RabbitMQ) sebelum `SaveChangesAsync` berhasil. Jika basis data melempar exception, operasi eksternal tidak bisa ditarik kembali.
   * *Mitigasi*: Gunakan **Outbox Pattern**. Simpan Domain Event ke tabel basis data yang sama dalam transaksi ACID yang sama. Dispatcher terpisah (background worker) akan membaca tabel Outbox dan mengeksekusi I/O ke pihak ketiga secara asinkron.
3. **Penyalahgunaan Abstraksi (Leaky Abstraction)**:
   * *Problem*: Mendefinisikan method repository seperti `IQueryable<T> GetAll()`.
   * *Konsekuensi*: Kode Application/Presentation dapat memanggil `.Where()` dengan sintaks EF, membuat ekspresi LINQ diterjemahkan ke SQL. Ini membocorkan detail implementasi ORM Infrastructure langsung ke dalam domain core.
   * *Mitigasi*: Repository tidak boleh mengembalikan `IQueryable`. Selalu kembalikan `Task<IReadOnlyList<T>>` atau eksekusi kueri terisolasi.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Memasang Dependensi Pihak Ketiga pada Lapisan Domain
* **Kesalahan**: Mengimpor paket NuGet seperti `Newtonsoft.Json`, `Microsoft.EntityFrameworkCore`, atau `FluentValidation` ke dalam proyek `Domain`.
* **Dampak**: Domain terkontaminasi oleh perubahan API eksternal pihak ketiga (breaking changes) dan melanggar prinsip kebebasan framework.
* **Cara Menghindari**: `Domain.csproj` **hanya boleh berisi kode C# murni**. Serialisasi JSON, atribut database, dan aturan validasi request UI adalah tanggung jawab Infrastructure dan Application.

### 2. Memetakan Seluruh Properti Menjadi Virtual/Auto-Properties
* **Kesalahan**: Membuat entitas dengan seluruh properti `{ get; set; }` publik demi mempermudah AutoMapper atau binding deserializer.
* **Dampak**: Siapa pun dapat mengubah `account.Balance = -999999` dari mana saja tanpa melewati metode `Withdraw()` yang menjaga invariant bisnis.
* **Cara Menghindari**: Gunakan *private setters* (`{ get; private set; }`). Inisialisasi melalui constructor eksplisit atau metode bisnis.

### 3. Menggunakan Domain Entities sebagai Response DTO pada Controller
* **Kesalahan**:
  ```csharp
  [HttpGet("{id}")]
  public async Task<ActionResult<BankAccount>> Get(Guid id) => Ok(await _repo.GetById(id));
  ```
* **Dampak**: Seluruh struktur internal database/domain terekspos ke dunia luar. Memodifikasi domain internal berisiko merusak kontrak API publik. Terjadi serialisasi sirkular (*circular reference exception*).
* **Cara Menghindari**: Selalu proyeksikan Entity ke Response DTO terpisah sebelum dikirimkan ke presentation layer.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Single-File Commands/Queries**:
   * Kelompokkan Command, Handler, Validator, dan DTO respons dalam satu file fisik yang sama jika ukurannya tidak terlalu besar (kurang dari 200 baris). Teknik ini memangkas navigasi folder yang berlebihan di Visual Studio/Rider.
2. **Explicit Dependency Injection Registration**:
   * Setiap layer harus memiliki extension method `Add[LayerName](this IServiceCollection services)` tersendiri:
     * `AddApplication()` di `Application/DependencyInjection.cs`.
     * `AddInfrastructure(IConfiguration config)` di `Infrastructure/DependencyInjection.cs`.
   * `Program.cs` hanya bertugas memanggil ekstensi tersebut, menjaga susunan startup tetap bersih dan rapi.
3. **Gunakan Sealed Classes Secara Default**:
   * Tandai semua Command, Query, Handler, dan Domain Event dengan kata kunci `sealed`. Mencegah pewarisan sembarangan mengoptimalkan JIT devirtualization dan menegaskan intensi desain.
4. **Validasi Dua Tahap (Two-Tier Validation)**:
   * **Application Validation (FluentValidation)**: Memeriksa bentuk payload input (e.g., Format string kosong, panjang karakter, format email).
   * **Domain Invariant Validation**: Memeriksa keadaan logika bisnis (e.g., Batas saldo harian tercapai, rekening sudah ditutup).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. CQRS Read Path Optimization
Hindari pemanggilan Change Tracker EF Core pada saat melakukan pembacaan:

```csharp
// Path: src/EnterpriseBanking.Application/Accounts/Queries/GetAccountSummary/GetAccountSummaryHandler.cs
public async Task<AccountSummaryDto?> Handle(GetAccountSummaryQuery request, CancellationToken ct)
{
    // Menggunakan AsNoTracking() menghilangkan alokasi memory Snapshot & Identity Map
    return await _context.Accounts
        .AsNoTracking()
        .Where(a => a.Id == request.AccountId)
        .Select(a => new AccountSummaryDto(a.Id, a.AccountNumber, a.Balance.Amount))
        .FirstOrDefaultAsync(ct);
}
```

*Benchmark Dampak*: `AsNoTracking()` mengurangi konsumsi memori alokasi GC hingga **~55%** dan mempercepat throughput eksekusi kueri hingga **~2.3x** dibanding kueri terlacak normal.

### 2. Penggunaan C# 12 Records & Structs untuk Value Objects Ringan
Untuk Value Object yang berukuran kecil dan berumur pendek (misalnya koordinat GPS atau kuantitas sederhana), gunakan `readonly record struct` untuk mengeliminasi alokasi pada memori Managed Heap (*Zero Garbage Collection overhead*):

```csharp
public readonly record struct Quantity
{
    public decimal Value { get; }

    public Quantity(decimal value)
    {
        if (value < 0) throw new ArgumentOutOfRangeException(nameof(value), "Kuantitas tidak boleh negatif.");
        Value = value;
    }
}
```

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **ID Enumeration Prevention (Insecure Direct Object Reference - IDOR)**:
   * Jangan gunakan `int` auto-increment sebagai Id eksternal yang di-expose ke URL.
   * Gunakan `Guid` v7 (tersedia di .NET 9 / UUIDv7) yang bersifat acak namun memiliki urutan waktu terurut (*time-ordered sequential*), sehingga mengamankan endpoint dari serangan *scraping enumeration* tanpa merusak kinerja indeks B-Tree database.
2. **Mass Assignment Prevention Melalui DTO Ketat**:
   * Penggunaan model domain langsung pada parameter Controller membuka celah serangan *Over-Posting/Mass Assignment*. Penyerang dapat menyuntikkan payload `{"IsAdmin": true}` yang mengikat properti entity secara tidak sengaja. Clean Architecture secara natural menangkal ini karena data input masuk melalui Command DTO yang terdefinisi eksplisit.
3. **Data Protection In Transit & At Rest**:
   * Konfigurasikan Value Converter EF Core pada layer Infrastructure untuk enkripsi kolom sensitif (seperti nomor kartu kredit atau identitas pribadi) secara otomatis saat ditulis ke basis data:
   ```csharp
   builder.Property(x => x.CustomerTaxId)
          .HasConversion(
              v => EncryptionHelper.Encrypt(v),
              v => EncryptionHelper.Decrypt(v));
   ```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Terapkan MediatR Pipeline Behavior untuk mengotomatisasi Observabilitas (Tracing, Logging terstruktur, dan Performa Profiling):

```csharp
// Path: src/EnterpriseBanking.Application/Common/Behaviors/LoggingBehavior.cs
namespace EnterpriseBanking.Application.Common.Behaviors;

using System.Diagnostics;
using MediatR;
using Microsoft.Extensions.Logging;

public sealed class LoggingBehavior<TRequest, TResponse> : IPipelineBehavior<TRequest, TResponse>
    where TRequest : notnull
{
    private readonly ILogger<LoggingBehavior<TRequest, TResponse>> _logger;

    public LoggingBehavior(ILogger<LoggingBehavior<TRequest, TResponse>> logger)
    {
        _logger = logger;
    }

    public async Task<TResponse> Handle(TRequest request, RequestHandlerDelegate<TResponse> next, CancellationToken cancellationToken)
    {
        var requestName = typeof(TRequest).Name;
        _logger.LogInformation("Memulai pemrosesan command/query: {RequestName}", requestName);

        var stopwatch = Stopwatch.StartNew();

        try
        {
            var response = await next();
            stopwatch.Stop();

            if (stopwatch.ElapsedMilliseconds > 500)
            {
                _logger.LogWarning("Long-running Request Terdeteksi: {RequestName} ({Elapsed} ms)", 
                    requestName, stopwatch.ElapsedMilliseconds);
            }
            else
            {
                _logger.LogInformation("Selesai memproses {RequestName} dalam {Elapsed} ms", 
                    requestName, stopwatch.ElapsedMilliseconds);
            }

            return response;
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            _logger.LogError(ex, "Request {RequestName} gagal diproses setelah {Elapsed} ms", 
                requestName, stopwatch.ElapsedMilliseconds);
            throw;
        }
    }
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### 1. Matriks Ketergantungan Antar Proyek

```
┌────────────────────────────────┬────────────────────────────────────────────────────────┐
│ Proyek                         │ Proyek yang Boleh Direferensikan                       │
├────────────────────────────────┼────────────────────────────────────────────────────────┤
│ Domain                         │ TIDAK ADA (0 Project References, Pure BCL)             │
│ Application                    │ Domain                                                 │
│ Infrastructure                 │ Application, Domain                                    │
│ Presentation (Api/Web)         │ Application, Infrastructure (Hanya untuk register DI)  │
└────────────────────────────────┴────────────────────────────────────────────────────────┘
```

### 2. Aturan Emas Bersih (Clean Rules)
* **Aturan 1 (Core Isolation)**: Jika Anda melihat kata kunci `using Microsoft.EntityFrameworkCore;` di proyek `Domain`, Anda telah merusak arsitektur.
* **Aturan 2 (No Business Logic in Presentation)**: Controller atau Minimal API Endpoint hanya boleh melakukan parsing request, memanggil MediatR `Send()`, dan mengembalikan HTTP Result (`Ok`, `Created`, `BadRequest`).
* **Aturan 3 (Result Pattern over Exceptions)**: Gunakan class `Result` untuk alur kegagalan bisnis yang telah diprediksi (validasi gagal, saldo kurang). Gunakan `Exception` murni hanya untuk kejadian abnormal yang tak tertangani (jaringan putus, database mati).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Pilihan Ganda (Tingkat Dasar)

1. **Menurut The Dependency Rule dalam Clean Architecture, ke mana arah dependensi harus selalu bermuara?**
   * A. Ke arah Presentation Layer agar respons JSON dapat disesuaikan dengan mudah.
   * B. Ke arah Infrastructure Layer karena basis data adalah fondasi dari seluruh data aplikasi.
   * C. Ke arah dalam, yaitu Application dan Domain Layer yang berada di inti sistem.
   * D. Bebas ke mana saja asalkan menggunakan antarmuka (`interface`).
   * *Kunci: C* | *Penjelasan: The Dependency Rule menyatakan dependensi kompilasi kode sumber harus selalu mengarah ke lapisan internal yang lebih tinggi tingkat abstraksinya (Domain).*

2. **Manakah dari pernyataan berikut yang membedakan Entity dari Value Object secara absolut?**
   * A. Entity memiliki method mutasi, sedangkan Value Object tidak dapat memiliki method.
   * B. Entity memiliki identitas unik konseptual (Id), sedangkan kesetaraan Value Object hanya ditentukan oleh nilai atribut-atribut penyusunnya.
   * C. Entity disimpan di SQL Server, sedangkan Value Object disimpan di Redis.
   * D. Entity ditulis menggunakan class, sedangkan Value Object wajib ditulis menggunakan struct.
   * *Kunci: B* | *Penjelasan: Kesamaan dua Entity ditentukan oleh Id-nya (meskipun properti lain berbeda). Value Object tidak memiliki Id; jika nilainya sama persis, kedua Value Object dianggap identik.*

3. **Mengapa membiarkan setter publik (`{ get; set; }`) pada Domain Entities dianggap sebagai anti-pattern dalam Clean Architecture?**
   * A. Karena membuat Entity tidak dapat dikonversi ke JSON.
   * B. Karena merusak enkapsulasi dan memungkinkan status entitas dimutasi menjadi tidak valid di luar kendali logika domain (Anemic Domain Model).
   * C. Karena menurunkan performa kompilasi .NET SDK.
   * D. Karena EF Core tidak mengizinkan setter publik.
   * *Kunci: B* | *Penjelasan: Rich Domain Model menuntut agar invarian bisnis selalu terlindungi. Setter publik membuka peluang bagi layer luar untuk mengubah status tanpa melewati validasi aturan bisnis.*

4. **Di lapisan manakah interface untuk integrasi eksternal (seperti `IEmailSender` atau `IPaymentGateway`) harus didefinisikan?**
   * A. Lapisan Infrastructure.
   * B. Lapisan Presentation.
   * C. Lapisan Application.
   * D. Lapisan Database.
   * *Kunci: C* | *Penjelasan: Application Layer mendefinisikan port (kontrak interface) yang ia butuhkan untuk mengeksekusi use case. Lapisan Infrastructure bertindak sebagai adapter yang mengimplementasikan interface tersebut.*

5. **Apa fungsi utama dari `MediatR Pipeline Behavior`?**
   * A. Menggantikan seluruh routing HTTP ASP.NET Core.
   * B. Menangani cross-cutting concerns (seperti validasi, logging, caching) di sekeliling handler use case tanpa mencemari logika handler itu sendiri.
   * C. Melakukan koneksi langsung ke driver TCP database.
   * D. Mengotomatisasi pembuatan file migration EF Core.
   * *Kunci: B* | *Penjelasan: Pipeline Behavior bertindak sebagai middleware internal untuk pesan MediatR, mengeksekusi logika umum sebelum dan sesudah handler use-case berjalan.*

---

### Soal Pilihan Ganda (Tingkat Menengah)

6. **Perhatikan skenario: Developer A membuat method `IQueryable<T> Query()` di dalam antarmuka Repository pada Application Layer. Mengapa arsitek senior menolak Pull Request tersebut?**
   * A. Karena `IQueryable` tidak kompatibel dengan tipe data `Guid`.
   * B. Karena `IQueryable` mengekspos fitur spesifik ORM ke lapisan Application, memungkinkan kueri LINQ-to-Entities dieksekusi di luar kontrol Repository (Leaky Abstraction).
   * C. Karena `IQueryable` selalu lebih lambat daripada `IEnumerable` di semua skenario.
   * D. Karena C# 12 menghapus dukungan untuk `IQueryable`.
   * *Kunci: B* | *Penjelasan: Mengembalikan IQueryable membiarkan detail ORM bocor ke application layer dan dapat memicu runtime error yang sulit dilacak jika ekspresi LINQ yang ditulis tidak didukung oleh database provider.*

7. **Pada pola CQRS, teknik apakah yang paling direkomendasikan untuk kueri pembacaan data (Read Queries) demi mencapai throughput tinggi?**
   * A. Memuat Aggregate Root utuh via Repository, lalu memetakannya menggunakan AutoMapper.
   * B. Menjalankan query langsung ke database yang diproyeksikan langsung ke Read DTO murni tanpa Change Tracking atau Aggregate Domain.
   * C. Memanggil `DbContext.Attach()` pada Controller.
   * D. Menyimpan seluruh isi database ke session web presentation.
   * *Kunci: B* | *Penjelasan: Operasi pembacaan tidak memutasi data sehingga tidak membutuhkan validasi invariant Aggregate Root. Melewati Domain Model langsung ke DTO (menggunakan AsNoTracking atau Micro-ORM seperti Dapper) memangkas beban CPU dan memori secara masif.*

8. **Bagaimana cara menangani Domain Events yang membutuhkan pengiriman notifikasi ke Message Broker eksternal tanpa risiko inkonsistensi data ketika commit database gagal?**
   * A. Mengirim pesan ke broker terlebih dahulu di dalam controller, baru memanggil database.
   * B. Mengimplementasikan Outbox Pattern, di mana event disimpan di tabel database yang sama dalam satu transaksi ACID sebelum didispatch ke broker oleh background worker.
   * C. Membungkus panggilan message broker dengan `try-catch` kosong.
   * D. Mengabaikan kegagalan database karena pesan broker lebih penting.
   * *Kunci: B* | *Penjelasan: Outbox Pattern menjamin transaksi "At-Least-Once Delivery" secara atomik dengan commit data bisnis, mencegah event terkirim jika transaksi database mengalami rollback.*

9. **Jika proyek `Infrastructure` dan `Application` sama-sama membutuhkan referensi ke tipe dasar Domain, bagaimana urutan referensi proyek `.csproj` yang benar?**
   * A. `Infrastructure` mereferensikan `Application`; `Application` mereferensikan `Domain`.
   * B. `Domain` mereferensikan `Infrastructure`; `Infrastructure` mereferensikan `Application`.
   * C. `Application` mereferensikan `Infrastructure`; `Domain` mereferensikan `Application`.
   * D. `Presentation` mereferensikan `Domain` langsung; `Domain` mereferensikan `Infrastructure`.
   * *Kunci: A* | *Penjelasan: Infrastructure membutuhkan Application (untuk mengimplementasikan kontrak interface) dan Domain (untuk memetakan entitas). Application hanya mereferensikan Domain. Domain tidak mereferensikan apa pun.*

10. **Kapan Clean Architecture menjadi pilihan arsitektur yang BURUK (Anti-Pattern)?**
    * A. Saat sistem menangani jutaan transaksi keuangan harian.
    * B. Saat membangun aplikasi internal sederhana berbasis CRUD dasar dengan sedikit/tanpa aturan bisnis yang kompleks (overengineering).
    * C. Saat tim developer memiliki anggota lebih dari 20 orang.
    * D. Saat aplikasi harus berjalan di lingkungan container Docker/Kubernetes.
    * *Kunci: B* | *Penjelasan: Menggunakan Clean Architecture untuk aplikasi CRUD sederhana tanpa domain logic yang kompleks memperkenalkan over-engineering, biaya pembuatan boilerplate yang tidak perlu, dan memperlambat delivery tanpa memberikan nilai tambah teknis.*

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Mini Project: E-Commerce Order Fulfillment Core

Anda ditugaskan membangun inti arsitektural untuk modul **Order Fulfillment** menggunakan .NET 8 dengan struktur Clean Architecture murni.

#### Persyaratan Fungsional (Business Rules):
1. **Order Aggregate**:
   * Order terdiri dari satu atau lebih `OrderItem` (Product ID, Unit Price, Quantity).
   * Nilai total Order dihitung secara otomatis: $\sum (\text{UnitPrice} \times \text{Quantity})$.
   * Order memiliki status: `PendingPayment`, `Processing`, `Shipped`, `Cancelled`.
   * Aturan Bisnis: Order tidak dapat di-cancel jika status sudah `Shipped`.
   * Aturan Bisnis: Pembuatan order gagal jika total amount bernilai 0 atau negatif.
2. **Use Case (Application)**:
   * Buat `CreateOrderCommand` dengan payload: `CustomerId`, list of items (`ProductId`, `Quantity`, `UnitPrice`).
   * Gunakan `FluentValidation` untuk memastikan `CustomerId` tidak kosong dan setiap item memiliki `Quantity > 0`.
   * Implementasikan `CreateOrderCommandHandler` yang memanfaatkan `IOrderRepository` dan `IUnitOfWork`.
3. **Infrastructure**:
   * Implementasikan Entity Framework Core `DbContext` dengan konfigurasi relasi *One-to-Many* antara `Order` dan `OrderItem` (disimpan dalam tabel terpisah).
   * Enkapsulasi koleksi `_orderItems` di dalam Order entity agar hanya terekspos sebagai `IReadOnlyCollection<OrderItem>`.
4. **Presentation**:
   * Buat minimal satu endpoint Minimal API: `POST /api/orders` yang memanggil MediatR pipeline dan mengembalikan `201 Created` dengan `OrderId` jika berhasil, atau `400 Bad Request` jika validasi/aturan bisnis dilanggar.

#### Kriteria Keberhasilan Teknis:
* Solusi terbagi menjadi minimal 4 folder proyek: `.Domain`, `.Application`, `.Infrastructure`, `.Presentation.Api`.
* Proyek `.Domain` memiliki 0 (nol) referensi ke NuGet eksternal atau proyek lain.
* Seluruh invariant bisnis diuji menggunakan Unit Test (menggunakan xUnit/FluentAssertions) pada Domain layer tanpa menyalakan runtime ASP.NET Core atau in-memory database.