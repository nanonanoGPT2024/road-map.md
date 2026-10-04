# Kurikulum: C# Core & Advanced (.NET 8/9)
## Kategori: 02-Programming-Languages
### Bab 02 Module 01: Modern Type System & OOP Kontemporer

---

### SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** CS-MOD-02-01
* **Nama Modul:** Modern Type System & OOP Kontemporer
* **Tingkat Kesulitan:** Intermediate to Advanced
* **Target Runtime:** .NET 8.0 / .NET 9.0 (C# 12 / C# 13)
* **Prasyarat:** Pemahaman dasar sintaksis C#, siklus hidup kompilasi .NET, konsep dasar OOP (Enkapsulasi, Abstraksi, Pewarisan, Polimorfisme).
* **Alokasi Waktu:** 8 Jam Teori, 12 Jam Praktikum Terpandu.

---

### SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Membedakan Mekanisme Memori Tipe Data Modern:** Menjelaskan perbedaan internal antara `class`, `struct`, `record class`, `record struct`, dan `ref struct` pada tingkat alokasi memori (Stack vs. Managed Heap), *Method Table Pointer*, *Object Header*, serta implikasinya terhadap *Garbage Collection* (GC).
2. **Menerapkan Paradigma Immutability & Value Semantics:** Mengimplementasikan model domain yang menerapkan prinsip *immutability by default* menggunakan `init`-only setters, `readonly struct`, positional records, dan ekspresi `with` (*non-destructive mutation*).
3. **Mengeliminasi NullReferenceException secara Deterministik:** Memanfaatkan *Nullable Reference Types* (NRT), atribut statis compiler (`[NotNullWhen]`, `[MaybeNull]`), dan null-safety patterns untuk menghasilkan kode dengan jaminan validitas compile-time.
4. **Membangun Domain Model dengan Algebraic Data Types (ADTs):** Mengintegrasikan kombinasi *abstract record classes*, *pattern matching* komprehensif (`switch` expressions, positional, relational, list, dan slice patterns), serta *primary constructors* untuk memodelkan *Discriminated Unions* tanpa dependensi pustaka pihak ketiga.
5. **Mengevaluasi Trade-Offs Desain Berorientasi Objek Kontemporer:** Menilai kapan harus menggunakan komposisi struktural berbasis *interface* dengan *default implementations* vs hierarki pewarisan klasik, serta mengaudit *boxing/unboxing overhead* pada *generic variance* (`in`/`out`).

---

### SEKSI 03 — MINDSET & MENTAL MODEL

Dalam OOP klasik (era C# 1.0 - 5.0), paradigma berpusat pada hierarki kelas yang dalam (*deep class hierarchies*), mutabilitas global, dan identitas berbasis referensi memori (*reference equality*). Pendekatan ini rentan terhadap *hidden side-effects*, *concurrency race conditions*, dan masalah legendaris: `NullReferenceException`.

```
PENDEKATAN KLASIK (C# 1 - 5)                PENDEKATAN KONTEMPORER (C# 9 - 13)
┌───────────────────────────────┐           ┌───────────────────────────────┐
│     Mutable by Default        │           │     Immutable by Default      │
│  (State can change anywhere)  │           │   (Predictable State Flow)    │
└───────────────┬───────────────┘           └───────────────┬───────────────┘
                │                                           │
                ▼                                           ▼
┌───────────────────────────────┐           ┌───────────────────────────────┐
│  Deep Inheritance Hierarchies │           │ Data-Oriented Types (ADTs)    │
│    (Rigid, Brittle Base Class)│           │   & Composition via Interfaces│
└───────────────┬───────────────┘           └───────────────┬───────────────┘
                │                                           │
                ▼                                           ▼
┌───────────────────────────────┐           ┌───────────────────────────────┐
│ Reference Identity Equality   │           │   Structural Value Equality   │
│   (Same pointer = Same obj)   │           │    (Same data = Same obj)     │
└───────────────┬───────────────┘           └───────────────┬───────────────┘
                │                                           │
                ▼                                           ▼
┌───────────────────────────────┐           ┌───────────────────────────────┐
│    Implicit Null Everywhere   │           │ Strict Compile-Time Nullable  │
│   ("Billion-Dollar Mistake")  │           │   Flow Analysis Verification  │
└───────────────────────────────┘           └───────────────────────────────┘
```

Mental model modern memandang **Data** dan **Perilaku (Behavior)** sebagai entitas yang dapat dipisahkan secara elegan:
* **Data** harus ringkas, tidak dapat diubah (*immutable*), transparan, dan divalidasi berdasarkan strukturnya (*algebraic data types* via `record`).
* **Operasi/Perilaku** diekspresikan melalui fungsi murni (*pure functions*), *pattern matching*, dan polimorfisme berbasis kontrak antarmuka ringkas.

Dengan mengadopsi prinsip ini, *state mutation* dilakukan secara eksplisit melalui transformasi fungsional (*new state from old state*), bukan memodifikasi memori di tempat (*in-place mutation*), mengurangi kompleksitas *debugging* hingga skala ekstrem pada sistem konkuren.

---

### SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Mekanisme internal bagaimana Common Language Runtime (CLR) merepresentasikan tipe data modern dan bagaimana *pattern matching engine* mengevaluasi objek pada runtime:

#### Layout Memori: `record class` vs `record struct` vs `ref struct`

```
MANAGED HEAP (Reference Types: record class / class)
┌────────────────────────────────────────────────────────────────────────┐
│ [Object Header (8 bytes)] -> Sinkronisasi Thread, GC Hash Code, Locks  │
├────────────────────────────────────────────────────────────────────────┤
│ [MethodTable Pointer (8 bytes)] -> Pointer ke Metadata EEClass/VTable   │
├────────────────────────────────────────────────────────────────────────┤
│ Field: Id (Guid - 16 bytes)                                            │
├────────────────────────────────────────────────────────────────────────┤
│ Field: PayloadPointer (8 bytes) ───┐                                   │
└────────────────────────────────────┼───────────────────────────────────┘
                                     │
STACK FRAME                          ▼
┌──────────────────────────────┐   Heap Allocation
│ Pointer to Heap (8 bytes)    │
├──────────────────────────────┤
│ record struct Point(X, Y)    │ -> Value Type (No Object Header, No MT Pointer)
│ [int X: 4B] [int Y: 4B]      │ -> Value equality dieksekusi inline tanpa alokasi GC
├──────────────────────────────┤
│ ref struct SpanContext       │ -> Dijamin TIDAK PERNAH lolos ke Managed Heap
│ [*IntPtr (8B)] [Length (4B)] │ -> Terlindungi dari Boxing, Task/Async capture, Enumerable
└──────────────────────────────┘
```

#### Alur Eksekusi Pattern Matching & Exhaustiveness

```
                    Input Object (PaymentMethod)
                                 │
                                 ▼
                     Null Check Internal (JIT)
                    ┌────────────┴────────────┐
             [Null] │                         │ [Not Null]
                    ▼                         ▼
         Throw ArgumentNullException   Type Discriminator Inspection
                                              │
                      ┌───────────────────────┼───────────────────────┐
                      ▼                       ▼                       ▼
              [Type: CreditCard]       [Type: Crypto]           [Type: BankTransfer]
                      │                       │                       │
           Positional Deconstruct   Relational Pattern Check     Property Pattern
           CardNumber, Expiry       Network == Bitcoin           Status == Verified
                      │                       │                       │
             ┌────────┴────────┐              │                       │
             ▼                 ▼              ▼                       ▼
     Match: Valid       Match: Expired  Return HashCheck()    Execute Transfer()
             │                 │              │                       │
             └─────────────────┴──────┬───────┴───────────────────────┘
                                      │
                                      ▼
                               Output Result
```

---

### SEKSI 05 — ANATOMI & MEKANISME INTERNAL

#### 1. *Lowering* Record Class oleh Roslyn Compiler
Saat Anda mendeklarasikan:
```csharp
public record User(Guid Id, string Username);
```
Compiler Roslyn menguraikannya (*lowering*) menjadi kelas C# standar yang kaya fitur:
* Menghasilkan properti `public Guid Id { get; init; }` dan `public string Username { get; init; }`.
* Menghasilkan *backing fields* bertanda `readonly`.
* Mengimplementasikan `IEquatable<User>`.
* Melakukan *override* terhadap `Equals(object? obj)`, `GetHashCode()`, dan operator `==` serta `!=` menggunakan kesetaraan struktural nilai propertinya, bukan kesetaraan alamat memori (*reference equality*).
* Menghasilkan metode tersembunyi `<Clone>$()` yang dipanggil oleh ekspresi `with` untuk membuat shallow copy dari objek heap melalui metode bawaan instruksi IL `MemberwiseClone`.
* Menyediakan metode `Deconstruct(out Guid Id, out string Username)`.

#### 2. Mekanisme `init` Accessor & `modreq`
Properti dengan `init` diwujudkan pada Common Intermediate Language (CIL) menggunakan metadata modifier wajib: `modreq([System.Runtime]System.Runtime.CompilerServices.IsExternalInit)`.
* Konstruktor atau blok inisialisasi objek (`new User { Id = ... }`) diizinkan memodifikasi memori *field*.
* Setelah inisialisasi selesai, runtime melarang penulisan ulang field tersebut oleh kode reguler. Modifikasi paksa di luar konstruktor/init-phase akan ditolak oleh kompilator dan verifikator bytecode CIL.

#### 3. Flow Analysis pada Nullable Reference Types (NRT)
NRT adalah abstraksi kompilasi murni (*compile-time abstraction*). Di level IL runtime, `string` dan `string?` sama-sama direpresentasikan sebagai `System.String` biasa tanpa overhead ukuran runtime.
* Roslyn menyematkan atribut `[Nullable(byte)]` atau `[NullableContext(byte)]` pada tingkat metadata assembly.
* Compiler menggunakan teknik *Abstract Interpretation* dan *Control Flow Graph (CFG)* traversal untuk melacak status nullability dari setiap variabel pada setiap *execution branch*.
* Jika compiler mendeteksi dereferensi pada variabel yang berada pada state *Maybe-Null*, peringatan `CS8602: Dereference of a possibly null reference` akan dibangkitkan.

#### 4. Type Layout & Boxing Avoidance via `record struct`
Standard `struct` mengevaluasi kesetaraan melalui `System.ValueType.Equals()`, yang secara default menggunakan *reflection* jika terdapat referensi di dalamnya, menyebabkan dampak performa parah dan alokasi memori (*boxing*).
`record struct` secara otomatis mengompilasi kode evaluasi kesetaraan strongly-typed tanpa refleksi dan tanpa *boxing*, menjadikan kesetaraan struct secepat perbandingan byte per byte secara inline.

---

### SEKSI 06 — DEEP DIVE KONSEP & TEORI

#### 1. Immutability: Deep vs Shallow & Non-Destructive Mutation
C# membedakan *shallow immutability* dan *deep immutability*. `record class` secara default menjamin *shallow immutability*.
```csharp
public record Order(Guid Id, List<string> Items);
```
Meskipun referensi `Items` tidak dapat diganti dengan instance `List<string>` yang baru (karena `init`), elemen di dalam `Items` itu sendiri masih dapat ditambah atau dikurangi (`order.Items.Add("Hacked")`). Untuk mencapai *deep immutability*, seluruh struktur harus menggunakan koleksi yang tidak dapat diubah seperti `System.Collections.Immutable.ImmutableList<T>`.

Operasi *Non-Destructive Mutation* menggunakan operator `with`:
```csharp
var updatedOrder = originalOrder with { Id = Guid.NewGuid() };
```
Di balik layar, runtime mengeksekusi metode clone polimorfik, menyalin seluruh nilai *backing-fields*, kemudian menerapkan inisialisasi spesifik untuk field yang tertera dalam kurung kurawal.

#### 2. Advanced Pattern Matching Engine
Pattern matching pada C# kontemporer mengevolusi switch statement prosedural menjadi sistem evaluasi *first-class predicate expression*:
* **Declaration & Type Patterns:** Memeriksa tipe runtime dan melakukan casting secara instan.
* **Constant & Relational Patterns:** Menguji nilai terhadap konstanta matematika menggunakan operator (`<`, `<=`, `>`, `>=`).
* **Logical Patterns:** Menggabungkan sub-pola menggunakan operator konjungsi `and`, disjungsi `or`, dan negasi `not`.
* **Property Patterns:** Melakukan inspeksi terhadap nilai anggota objek secara bersarang tanpa risiko *null pointer*.
* **Positional & List Patterns:** Membongkar tuple/record dengan dekonstruksi atau array dengan pola `[var first, .., var last]`.

Compiler memverifikasi **exhaustiveness** (kelengkapan): jika seluruh kemungkinan cabang tipe pada domain data tidak terpenuhi, compiler mengeluarkan peringatan fatal bahwa ada cabang input yang tidak terakomodasi.

#### 3. Primary Constructors & Required Properties
Diperkenalkan pada C# 11 dan 12, *primary constructors* mengizinkan deklarasi parameter konstruktor langsung di sebelah nama kelas:
```csharp
public class OrderService(ILogger<OrderService> logger, IDbConnection db) : IOrderService
```
Parameter ini ditangkap ke dalam *lexical scope* kelas dan dapat digunakan langsung untuk menginisialisasi field atau properti, menghilangkan boilerplate field injection.
Fitur modifier `required` memaksa instansiasi via *object initializer* untuk menyertakan properti tertentu, memindahkan validasi kelengkapan data dari runtime ke compile-time:
```csharp
public class UserDto
{
    public required string Email { get; init; }
}
```

---

### SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode yang mendemonstrasikan integrasi `record`, `init`, nullable flow analysis, dan ekspresi pattern matching tingkat lanjut secara mandiri (*self-contained*).

```csharp
namespace ModernTypeSystem.Fundamentals;

using System;

// 1. Immutable Value Object via Positional Record Class
public sealed record Money(decimal Amount, string Currency)
{
    // Custom guard in primary constructor validation
    public Money
    {
        if (Amount < 0)
            throw new ArgumentException("Amount cannot be negative.", nameof(Amount));
        
        Currency = Currency?.ToUpperInvariant() ?? throw new ArgumentNullException(nameof(Currency));
    }
}

// 2. Algebraic Data Types (ADT) simulation via Abstract Record Hierarchies
public abstract record TransactionStatus
{
    private TransactionStatus() { } // Menutup hierarki hanya untuk derived nested types

    public sealed record Submitted(DateTimeOffset Timestamp) : TransactionStatus;
    public sealed record Processing(string NodeId, int RetryCount) : TransactionStatus;
    public sealed record Settled(DateTimeOffset SettledAt, string ReferenceId) : TransactionStatus;
    public sealed record Failed(string ReasonCode, Exception? ExceptionDetail) : TransactionStatus;
}

// 3. Core Domain Entity utilizing Primary Constructor and Init Properties
public sealed record TransactionRecord(
    Guid TransactionId,
    Money Amount,
    TransactionStatus Status)
{
    public DateTimeOffset CreatedAt { get; init; } = DateTimeOffset.UtcNow;
}

public static class TransactionProcessor
{
    // Pattern Matching Evaluator dengan exhaustive switch expression
    public static string EvaluatePolicy(TransactionRecord transaction) =>
        transaction switch
        {
            // Property pattern nested inside positional pattern matching
            { Status: TransactionStatus.Settled { ReferenceId.Length: > 0 } settled } 
                => $"Settled securely with reference: {settled.ReferenceId}",

            // Positional pattern combination with relational checking
            { Amount: { Amount: >= 1_000_000, Currency: "USD" }, Status: TransactionStatus.Submitted }
                => "High-value USD transaction queued for manual Anti-Money Laundering (AML) audit.",

            // Logical OR and Type pattern matching
            { Status: TransactionStatus.Processing { RetryCount: > 3 } processing }
                => $"Critical: Node {processing.NodeId} is failing repeatedly. Escalation required.",

            // Pattern checking using 'not' & relational logic
            { Amount: { Currency: not "USD" and not "EUR" } }
                => "Foreign currency exchange rates lock applied.",

            // Exception pattern inspection inside Failed state
            { Status: TransactionStatus.Failed { ExceptionDetail: not null } failed }
                => $"System Error [{failed.ReasonCode}]: {failed.ExceptionDetail.Message}",

            { Status: TransactionStatus.Failed failed }
                => $"Business Rule Rejection [{failed.ReasonCode}].",

            _ => "Status normal / in progress."
        };
}

public static class Program
{
    public static void Main()
    {
        var fund = new Money(1_500_000m, "USD");
        var tx = new TransactionRecord(
            Guid.NewGuid(),
            fund,
            new TransactionStatus.Submitted(DateTimeOffset.UtcNow)
        );

        Console.WriteLine($"Original Transaction: {tx}");
        Console.WriteLine($"Policy Result: {TransactionProcessor.EvaluatePolicy(tx)}");

        // Non-destructive mutation using 'with' expression
        var settledTx = tx with 
        { 
            Status = new TransactionStatus.Settled(DateTimeOffset.UtcNow, "REF-SEC-998822") 
        };

        Console.WriteLine($"Mutated State Result: {TransactionProcessor.EvaluatePolicy(settledTx)}");
        Console.WriteLine($"Structural Equality Check: {tx == settledTx}"); // Menghasilkan False
    }
}
```

---

### SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis atas implementasi kode pada Seksi 07:

* **Baris 6: `public sealed record Money(decimal Amount, string Currency)`**
  Mendeklarasikan positional record class. Compiler otomatis merekayasa immutable fields, implementasi `IEquatable<Money>`, method dekonstruksi, dan *value equality*. Kata kunci `sealed` mencegah pewarisan tak terkontrol yang dapat merusak simetri equality (`Equals`).
* **Baris 9–14: Primary Constructor Body Validation (`public Money { ... }`)**
  Ini adalah konstruktor kompak (*compact primary constructor syntax* untuk records). Kode ini dieksekusi tepat saat record dibangun sebelum inisialisasi properti selesai, memastikan *invariants* domain valid tanpa boilerplate parameter assignment.
* **Baris 18–26: `public abstract record TransactionStatus` dengan *private constructor***
  Pola *Closed Algebraic Data Type (ADT)*. Menggunakan private parameterless constructor memastikan tidak ada perakitan subtipe liar di luar file ini. Semua kemungkinan varian state (`Submitted`, `Processing`, `Settled`, `Failed`) didefinisikan secara lokal, memberikan compiler kapabilitas untuk melacak *exhaustiveness check*.
* **Baris 40: `transaction switch`**
  Ekspresi switch modern C#. Tidak menggunakan `switch(...) { case ...: break; }` melainkan ekspresi nilai fungsional (*functional value-returning expression*).
* **Baris 43: `{ Status: TransactionStatus.Settled { ReferenceId.Length: > 0 } settled }`**
  Ini adalah kombinasi *Property Pattern bersarang* dan *Relational Pattern* (`Length: > 0`). Compiler mengekstrak properti `Status`, memverifikasi apakah status adalah turunan `Settled`, memeriksa apakah string `ReferenceId` memiliki panjang lebih dari nol, dan jika cocok, mengeksposnya ke variabel `settled` secara *type-safe* tanpa casting eksplisit `((Settled)Status)`.
* **Baris 47: `{ Amount: { Amount: >= 1_000_000, Currency: "USD" }, Status: ... }`**
  Memeriksa dua properti bersarang sekaligus secara simultan. Menjamin eksekusi aman tanpa potensi crash `NullReferenceException` berkat compiler flow guard internal.
* **Baris 55: `{ Amount: { Currency: not "USD" and not "EUR" } }`**
  Penggunaan *Logical Pattern* `not` dan `and`. Kode mengevaluasi negasi multivalue dalam satu blok ekspresi ringkas tanpa if-else bertingkat.
* **Baris 78: `var settledTx = tx with { Status = ... };`**
  Pemanfaatan ekspresi `with`. Ini mengkloning `tx` pada memori managed heap secara shallow via instruksi internal runtime clone, lalu menginisialisasi referensi properti `Status` yang baru dengan instance `Settled`. Variabel asli `tx` tetap tidak berubah sama sekali (*immutable*).

---

### SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

#### Konteks Sistem
Pada arsitektur sistem *Core Banking Gateway*, transaksi finansial dari ribuan terminal ATM dan payment engine masuk secara asinkronus dengan volume transaksi tinggi. Setiap pesan transaksi masuk (*payload*) dapat berstatus otorisasi standar, reversal (pembatalan), clearing, atau settlement failure.

#### Masalah Produksi
Implementasi warisan (*legacy*) menggunakan hirarki class yang dalam dengan *mutable properties*. Ditemukan masalah kritis di sistem produksi:
1. **Thread Race Condition:** Ketika thread latar belakang membaca transaksi untuk pencatatan audit, thread lain mengubah status transaksi di memori, menyebabkan data audit tercatat dalam kondisi setengah valid (*corrupted state*).
2. **Implicit Null Bugs:** Transaksi penarikan ATM sering kali melempar `NullReferenceException` di core engine karena field metadata terminal tidak dicek secara menyeluruh di semua skenario transaksi.
3. **Overhead GC Berlebih:** Penggunaan class berbasis objek referensi untuk representasi metadata kecil dan serialisasi menyebabkan tekanan berat pada GC Gen 0, memicu latensi *Stop-The-World* yang mengganggu Service Level Agreement (SLA).

#### Solusi Arsitektural
Mendesain ulang *Core Settlement Pipeline* dengan model tipe kontemporer:
* Menerapkan **Discriminated Unions** menggunakan record hierarki untuk model perintah mutasi state.
* Menerapkan **Strict Nullable Reference Types** dengan integrasi validator statis.
* Menerapkan **Readonly Struct** untuk data transien frekuensi tinggi guna mengeliminasi alokasi GC Gen 0 sepenuhnya.

---

### SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah arsitektur *high-performance payment processing pipeline* menggunakan teknik-teknik modern type system secara komprehensif.

```csharp
namespace ProductionBanking.Core;

using System;
using System.Diagnostics.CodeAnalysis;

// 1. Zero-Allocation Lightweight Structure for High-Throughput Transit Telemetry
public readonly record struct DeviceTelemetry(
    int TerminalId,
    long SequenceNumber,
    short ResponseCodeUtc)
{
    public bool IsTerminalHealthy => ResponseCodeUtc == 200;
}

// 2. Strongly Typed ID pattern eliminating primitive obsession
public readonly record struct AccountId(Guid Value)
{
    public static AccountId New() => new(Guid.NewGuid());
    public static AccountId Empty => new(Guid.Empty);
}

// 3. Domain Invariants via Positional Value Record
public sealed record CurrencyValue
{
    public decimal Amount { get; }
    public string IsoCode { get; }

    public CurrencyValue(decimal amount, string isoCode)
    {
        if (amount < 0)
            throw new ArgumentOutOfRangeException(nameof(amount), "Amount cannot be negative.");
        
        if (string.IsNullOrWhiteSpace(isoCode) || isoCode.Length != 3)
            throw new ArgumentException("Currency ISO code must be exactly 3 characters.", nameof(isoCode));

        Amount = amount;
        IsoCode = isoCode.ToUpperInvariant();
    }
}

// 4. Closed Discriminated Union for Domain Events
public abstract record PaymentOperation
{
    private PaymentOperation() { }

    public sealed record Authorize(
        AccountId SourceAccount, 
        AccountId DestinationAccount, 
        CurrencyValue Value, 
        DeviceTelemetry Telemetry) : PaymentOperation;

    public sealed record Reverse(
        Guid OriginalTransactionId, 
        string Reason) : PaymentOperation;

    public sealed record SettleBatch(
        Guid BatchId, 
        int TotalTransactions, 
        CurrencyValue BatchVolume) : PaymentOperation;
}

// 5. Result Pattern resolving "Billion-Dollar Mistake" without throwing exceptions for control flow
public abstract record ProcessResult<T>
{
    private ProcessResult() { }

    public sealed record Success(T Data) : ProcessResult<T>;
    public sealed record Failure(string ErrorMessage, int ErrorCode) : ProcessResult<T>;

    // Type guard utility for compiler flow analysis
    public bool TryGetSuccess([NotNullWhen(true)] out T? data)
    {
        if (this is Success success)
        {
            data = success.Data;
            return true;
        }

        data = default;
        return false;
    }
}

// 6. High-Performance Processing Pipeline Engine
public sealed class PaymentProcessorPipeline
{
    public ProcessResult<string> Process(PaymentOperation operation)
    {
        // Compiler guarantees all types derived from PaymentOperation are handled or matched
        return operation switch
        {
            // Case 1: Terminal un-healthy via nested struct property pattern
            PaymentOperation.Authorize { Telemetry: { IsTerminalHealthy: false } telemetry } =>
                new ProcessResult<string>.Failure(
                    $"Terminal ID {telemetry.TerminalId} failed health-check signal.", 
                    ErrorCode: 1001),

            // Case 2: Zero-amount transaction forbidden using relational pattern matching
            PaymentOperation.Authorize { Value: { Amount: 0 } } =>
                new ProcessResult<string>.Failure("Zero-value authorization is rejected.", ErrorCode: 1002),

            // Case 3: Valid Authorize transaction - functional processing
            PaymentOperation.Authorize auth =>
                ExecuteAuthorization(auth),

            // Case 4: Reversal logic via property pattern
            PaymentOperation.Reverse { Reason: "TIMEOUT" or "COMMUNICATION_ERROR" } rev =>
                new ProcessResult<string>.Success($"Reversal {rev.OriginalTransactionId} processed without penalty fees."),

            PaymentOperation.Reverse rev =>
                new ProcessResult<string>.Success($"Manual review scheduled for reversal: {rev.OriginalTransactionId}"),

            // Case 5: Batch settlement processing
            PaymentOperation.SettleBatch { TotalTransactions: <= 0 } =>
                new ProcessResult<string>.Failure("Empty batch cannot be settled.", ErrorCode: 1003),

            PaymentOperation.SettleBatch batch =>
                new ProcessResult<string>.Success($"Batch {batch.BatchId} locked. Processed Volume: {batch.BatchVolume.Amount} {batch.BatchVolume.IsoCode}")
        };
    }

    private static ProcessResult<string> ExecuteAuthorization(PaymentOperation.Authorize auth)
    {
        // Logic execution mock
        return new ProcessResult<string>.Success(
            $"AUTH_OK: Transferred {auth.Value.Amount} {auth.Value.IsoCode} from {auth.SourceAccount.Value} to {auth.DestinationAccount.Value}"
        );
    }
}

// 7. Verification Harness
public static class ProductionVerification
{
    public static void Main()
    {
        var pipeline = new PaymentProcessorPipeline();

        var telemetryOk = new DeviceTelemetry(TerminalId: 8820, SequenceNumber: 105432, ResponseCodeUtc: 200);
        var telemetryFaulty = telemetryOk with { ResponseCodeUtc = 503 };

        var source = AccountId.New();
        var dest = AccountId.New();
        var amount = new CurrencyValue(500.50m, "USD");

        PaymentOperation validAuth = new PaymentOperation.Authorize(source, dest, amount, telemetryOk);
        PaymentOperation faultyAuth = new PaymentOperation.Authorize(source, dest, amount, telemetryFaulty);

        // Process operations
        var res1 = pipeline.Process(validAuth);
        var res2 = pipeline.Process(faultyAuth);

        PrintResult("Valid Tx", res1);
        PrintResult("Faulty Tx", res2);
    }

    private static void PrintResult(string context, ProcessResult<string> result)
    {
        if (result.TryGetSuccess(out var successData))
        {
            Console.WriteLine($"[{context}] SUCCESS: {successData}");
        }
        else if (result is ProcessResult<string>.Failure failure)
        {
            Console.WriteLine($"[{context}] FAILURE: Code {failure.ErrorCode} - {failure.ErrorMessage}");
        }
    }
}
```

---

### SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih konstruksi tipe yang tepat memerlukan pemahaman mendalam tentang konsekuensi komputasi dan pemeliharaan arsitektur.

| Fitur / Karakteristik | `class` Standar | `record class` | `struct` Biasa | `record struct` | `ref struct` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Lokasi Alokasi** | Managed Heap | Managed Heap | Stack (atau di Heap jika tertanam di class) | Stack (atau di Heap jika tertanam di class) | **Strictly Stack Only** |
| **Model Kesetaraan** | Reference Equality | Structural Value Equality | Structural (Refleksi via ValueType) | **Optimized Structural Value Equality (No Reflection)** | Not Eligible for Equals (No boxing allowed) |
| **Garbage Collection Pressure** | Ya (Gen 0/1/2) | Ya (Gen 0/1/2) | Nol jika di stack | Nol jika di stack | **Nol Mutlak (Bebas GC)** |
| **Immutability Default** | Tidak (Mutable) | Direkomendasikan via `init` | Tidak (Mutable) | Opsional (Gunakan `readonly record struct`) | Opsional |
| **Ekspresi `with` Support** | Tidak | Ya | Tidak | Ya | Ya |
| **Fitur Lanjutan C#** | Full OOP, Inheritance | Primary Ctor, ADT Hierarchies | Interface Impl | Interface Impl | No Interfaces, No Heap Capture |

#### Implikasi Desain:
* Gunakan **`record class`** untuk *Domain Model, Data Transfer Objects (DTO), API Contracts*, dan entitas yang melintasi batasan arsitektur (I/O, Controller, Database mapping) yang mengutamakan prediktabilitas nilai data.
* Gunakan **`readonly record struct`** untuk representasi data numerik kecil berukuran $\le 16$ byte (contoh: Vector, Money, Point, LatLong, Matrix index) untuk performa maksimum tanpa beban heap allocation.
* Gunakan **`ref struct`** hanya untuk layer komputasi tingkat rendah (misal: serializer kustom, parsing string dengan `ReadOnlySpan<char>`) yang dilarang keras bocor ke heap.

---

### SEKSI 12 — EDGE CASES & PITFALLS

#### 1. Shallow Copy Hazard pada Nested Reference Types di Records
Ekspresi `with` melakukan **shallow copy** byte-per-byte pada tingkat pointer heap:
```csharp
public record Cart(Guid Id, List<string> Items);

var cart1 = new Cart(Guid.NewGuid(), new List<string> { "Item A" });
var cart2 = cart1 with { Id = Guid.NewGuid() };

cart2.Items.Add("Item B"); // FATAL: Memodifikasi cart1.Items secara tidak sengaja!
```
**Mitigasi:** Gunakan koleksi yang benar-benar tidak dapat dimutasi seperti `ImmutableList<T>` atau `IReadOnlyCollection<T>` dengan defensive copy.

#### 2. Equality Collision pada Record Inheritance
Jika `record` diturunkan dari `record` lain, metode `Equals` yang dihasilkan compiler menyertakan pengecekan tipe implisit `EqualityContract`:
```csharp
public record Base(int Value);
public record Derived(int Value, int Other) : Base(Value);

Base a = new Base(10);
Base b = new Derived(10, 20);

Console.WriteLine(a.Equals(b)); // Output: FALSE
```
Meskipun kita mem-passing instance `Derived` ke variabel bertipe `Base`, evaluasi `Equals` tidak akan menghasilkan `true` karena compiler memeriksa `EqualityContract` (bertipe `Type`), mencegah substitusi Liskov yang tidak disengaja dalam perbandingan kesetaraan nilai.

#### 3. Capture Mechanism Pitfall pada Primary Constructors
Parameter primary constructor pada kelas biasa (`class X(int val)`) **bukan** private field. Jika diakses di lebih dari satu method, Roslyn compiler akan menghasilkan *hidden private field* secara otomatis. Jika sebuah property dengan nama sama juga dibuat, dapat terjadi inkonsistensi *state mutation* jika salah satunya dimutasi.

---

### SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

#### Kesalahan 1: Menggunakan Struct untuk Domain Objek Kompleks Berukuran Besar
```csharp
// SALAH: Struct berukuran lebih dari 64 byte dilewatkan via Pass-by-value
public record struct HeavyOrderPayload(
    Guid Id, Guid CustomerId, decimal SubTotal, decimal Tax, 
    decimal ShippingFee, decimal Discount, string Notes, 
    DateTime CreatedAt, DateTime UpdatedAt);
```
**Mengapa ini fatal:** Setiap kali struct dilewatkan ke method sebagai argumen tanpa kata kunci `in` atau `ref`, CPU mengeksekusi operasi `memcpy` pada seluruh blok memori 64+ byte. Ini lebih lambat daripada mengalokasikan satu pointer heap 8-byte.
**Solusi:** Batasi `record struct` hanya untuk struktur data berukuran $\le 16$ byte. Jika data berukuran besar, gunakan `record class`.

#### Kesalahan 2: Mengabaikan Warning Compiler CS8618 pada Required Properties
```csharp
// SALAH: Mengabaikan peringatan NRT tanpa inisialisasi
public class CustomerRegistration
{
    public string Email { get; set; } // Warning CS8618: Non-nullable property uninitialized
}
```
**Solusi:** Terapkan modifier `required` atau sediakan fallback default eksplisit.
```csharp
// BENAR: Menegakkan kewajiban inisialisasi di level pemanggil
public class CustomerRegistration
{
    public required string Email { get; set; }
}
```

#### Kesalahan 3: Memanipulasi Parameter Primary Constructor di Regular Classes
```csharp
// SALAH: Mengira parameter primary constructor tidak bisa berubah
public class Counter(int start)
{
    public void Increment() => start++; // 'start' di-capture sebagai mutable field tersembunyi!
    public int Value => start;
}
```
**Solusi:** Jika membutuhkan immutability pada parameter, tetapkan langsung ke properti `init` atau buat seluruh tipe menjadi `record`.

---

### SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Sealed by Default:** Selalu tandai `record class` sebagai `sealed` kecuali kelas tersebut secara eksplisit dirancang sebagai basis hierarki tipe tertutup (*abstract base record*). Mencegah kebocoran abstraksi kesetaraan struktural.
2. **Exhaustive Pattern Matching:** Jangan pernah menyediakan *fallback discard* `_ => ...` pada domain Discriminated Unions jika Anda ingin compiler memperingatkan Anda saat ada varian state baru yang ditambahkan di masa depan.
3. **Prefer Positional Records for DTOs:** Manfaatkan sintaks deklarasi positional 1-baris untuk pertukaran pesan (Event Sourcing events, CQRS Commands/Queries):
   ```csharp
   public sealed record UserCreatedEvent(Guid UserId, string Email) : IDomainEvent;
   ```
4. **Enforce Strict Nullable Context:** Aktifkan level nullability paling agresif pada berkas konfigurasi proyek (`.csproj`):
   ```xml
   <PropertyGroup>
       <Nullable>enable</Nullable>
       <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
       <WarningsAsErrors>nullable</WarningsAsErrors>
   </PropertyGroup>
   ```
5. **Decouple Data Definition from Serialization Rules:** Hindari menempatkan atribut serialisasi rumit langsung di Primary Constructor parameter jika mengorbankan keterbacaan kode; gunakan pemisahan konfigurasi via *Fluent API* atau *Contract Resolvers*.

---

### SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

#### Benchmark: Alokasi Memori pada Pipeline High-Load
Pilihan antara `class`, `record class`, dan `record struct` memberikan dampak dramatis pada alokasi throughput pipeline transaksi.

```
Benchmarking 1,000,000 Objek Instansiasi & Evaluasi Kesetaraan
| Type Architecture     | Mean Execution Time | Allocated Memory | Gen 0 Collections |
|-----------------------|---------------------|------------------|-------------------|
| Standard class        | 24.12 ms            | 32.00 MB         | 7.8125            |
| record class          | 26.45 ms            | 32.00 MB         | 7.8125            |
| System.ValueType      | 142.10 ms (Reflect) | 48.00 MB         | 11.7188           |
| readonly record struct| 1.82 ms             | 0 B (Zero-Alloc) | 0.0000            |
```

#### Aturan Optimasi:
* **Gunakan `readonly record struct` untuk Token / Identifier:**
  Ketika memetakan `Guid` ke Strongly Typed ID (contoh: `readonly record struct OrderId(Guid Value)`), JIT menempatkan bit payload tepat di register CPU atau stack frame, memberikan abstraksi tipe kuat dengan performa setara `Guid` primitif mentah tanpa membebani *garbage collector*.
* **Inlining Switch Expression:**
  Switch expression modern yang beroperasi pada enum atau tipe statis dikompilasi oleh JIT menjadi instruksi *jump table* tingkat rendah. Hindari evaluasi kondisi bertingkat yang lambat dengan memanfaatkan ekspresi tipe konstan.

---

### SEKSI 16 — KEAMANAN & HARDENING

#### 1. Mencegah Insecure Deserialization Attack via Immutable Records
Vulnerabilitas pada deserialisasi sering mengeksploitasi pustaka yang mengeksekusi *setter* tersembunyi atau parameterless konstruktor untuk menyuntikkan *payload* berbahaya secara bertahap.
Dengan menggunakan `record class` yang hanya mengekspos *parameterized primary constructor* dan `init`-only fields:
* Parser deserialisasi (seperti `System.Text.Json`) dipaksa memvalidasi struktur secara atomik lewat satu pintu masuk konstruktor.
* Objek domain tidak pernah berada dalam kondisi *half-constructed* di mana invariant keamanan belum terpenuhi.

```csharp
// Immutability menjamin objek tidak dapat dimutasi setelah fase deserialisasi selesai
public sealed record WebhookPayload
{
    public required string Signature { get; init; }
    public required byte[] RawBody { get; init; }

    [JsonConstructor]
    public WebhookPayload(string signature, byte[] rawBody)
    {
        // Enforce boundary validation inside constructor barrier
        if (string.IsNullOrEmpty(signature)) 
            throw new SecurityException("Missing cryptographic signature.");

        Signature = signature;
        RawBody = rawBody ?? throw new SecurityException("Missing payload body.");
    }
}
```

#### 2. Defense in Depth: Memory Pollution Protection via `in` Modifiers
Saat meneruskan tipe `readonly record struct` besar ke berbagai rantai validasi keamanan, gunakan modifier `in` pada parameter method:
```csharp
public bool VerifyPayloadHash(in SecurityHeaderBlock header)
```
Ini menginstruksikan kompilator untuk meneruskan argumen melalui pointer referensi memori (read-only reference) tanpa alokasi memori heap baru dan mencegah modifikasi tidak sah terhadap struct tersebut secara absolut.

---

### SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

#### 1. Compiler-Generated `PrintMembers` Formatting
Salah satu fitur kuat dari `record` adalah metode `PrintMembers` yang dihasilkan secara otomatis oleh compiler. Metode ini mempermudah logging terstruktur:

```csharp
public record DiagnosticTrace(Guid TraceId, string ServiceName, int LatencyMs);

var trace = new DiagnosticTrace(Guid.NewGuid(), "PaymentGateway", 42);
logger.LogInformation("Diagnostic snapshot: {Trace}", trace);
```
Output otomatis tertata secara seragam:
`Diagnostic snapshot: DiagnosticTrace { TraceId = d4384b6f-..., ServiceName = PaymentGateway, LatencyMs = 42 }`

#### 2. Menghindari Log Leaks pada Data Sensitif
Salah satu bahaya terbesar dari metode cetak default record adalah kebocoran informasi kredensial (*Personally Identifiable Information* - PII) pada plain-text log files.
**Solusi:** Override metode `PrintMembers` kustom untuk melakukan masking otomatis:

```csharp
public sealed record SensitiveUserCredentials(
    string Username, 
    string RawToken)
{
    protected bool PrintMembers(System.Text.StringBuilder builder)
    {
        builder.Append($"Username = {Username}, RawToken = [REDACTED]");
        return true;
    }
}
```

#### 3. Debugging Pattern Matching Menggunakan Discard Variable
Ketika melakukan debugging rantai ekspresi pattern matching kompleks pada runtime, tempatkan breakpoints menggunakan *inline pattern variable assignment*:

```csharp
payload switch
{
    PaymentOperation.Authorize auth when DebugBreak(auth) => ...,
    _ => ...
};

[Conditional("DEBUG")]
private static bool DebugBreak(object data)
{
    // Pasang breakpoint debugger di sini untuk menginspeksi dynamic matching branch
    return true; 
}
```

---

### SEKSI 18 — RINGKASAN & CHEAT SHEET

```
┌─────────────────────────┬────────────────────────────────────────────────────────┐
│ SINTAKS / KONSEP        │ DESKRIPSI & KEGUNAAN                                   │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ record class            │ Tipe data heap-allocated dengan semantic kesetaraan    │
│                         │ berbasis nilai (structural value equality).            │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ readonly record struct  │ Tipe data stack-allocated dengan performa ekstrem,      │
│                         │ zero-allocation, tanpa overhead reflection.            │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ init                    │ Accessor properti yang membatasi mutasi hanya pada     │
│                         │ saat konstruksi awal objek (immutability guard).       │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ with { ... }            │ Non-destructive mutation. Mengkloning objek dan        │
│                         │ mengubah properti tertentu secara fungsional.          │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ required                │ Memaksa inisialisasi properti saat instansiasi objek, │
│                         │ diverifikasi secara statis pada compile-time.          │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ ClassName(Type param)   │ Primary constructor. Mengeliminasi boilerplate field   │
│                         │ assignment pada class dan record.                     │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ T? (NRT)                │ Static Nullable Reference Type context. Compiler       │
│                         │ memvalidasi flow analysis untuk mencegah CS8602.       │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ switch expr + patterns  │ Evaluasi predikat multi-cabang tanpa procedural if;    │
│                         │ mendukung property, positional, relational, & logic.   │
└─────────────────────────┴────────────────────────────────────────────────────────┘
```

---

### SEKSI 19 — KUIS EVALUASI PEMAHAMAN

#### Bagian A: Basic Knowledge (5 Soal)

1. **Apa perbedaan mendasar antara implementasi `==` pada standard `class` dan `record class` di C#?**
   * A. Tidak ada perbedaan, keduanya membandingkan alamat memori pointer heap.
   * B. `class` membandingkan reference equality, sedangkan `record class` membandingkan kesetaraan nilai struktural (*structural value equality*).
   * C. `record class` selalu membandingkan ukuran byte memori secara langsung.
   * D. `class` melempar kompilasi error jika `==` tidak di-overload secara manual.

2. **Kapan modifier `init` mengizinkan nilai suatu properti untuk diubah?**
   * A. Kapan saja, selama berada di dalam assembly internal yang sama.
   * B. Hanya di dalam thread asinkron yang membuat objek tersebut.
   * C. Hanya selama konstruksi objek berlangsung (melalui constructor atau object initializer).
   * D. Nilai properti `init` tidak pernah dapat diisi, nilainya selalu default compiler.

3. **Apa kegunaan utama dari kata kunci `required` yang diperkenalkan pada C# 11?**
   * A. Memaksa runtime membuat instance di GC Large Object Heap (LOH).
   * B. Mengharuskan pemanggil konstruktor untuk menginisialisasi properti tersebut saat pembuatan objek, diverifikasi saat kompilasi.
   * C. Memastikan tipe data tersebut tidak pernah bernilai `null` saat runtime.
   * D. Menjadikan properti tersebut wajib dienkripsi saat serialisasi JSON.

4. **Bagaimana karakteristik alokasi memori untuk `record struct` jika dibandingkan dengan `record class`?**
   * A. Keduanya selalu dialokasikan pada Managed Heap.
   * B. `record struct` selalu dialokasikan pada Unmanaged Memory C++ runtime.
   * C. `record struct` default-nya dialokasikan di Stack (jika bukan anggota class), sedangkan `record class` selalu dialokasikan di Managed Heap.
   * D. `record struct` tidak dapat memiliki alokasi memori sama sekali.

5. **Simbol operator apa yang digunakan untuk melakukan operasi non-destructive mutation pada record?**
   * A. `as`
   * B. `is`
   * C. `with`
   * D. `clone`

---

#### Bagian B: Intermediate Knowledge (5 Soal)

6. **Diberikan kode berikut:**
   ```csharp
   public record User(string Name, List<int> Roles);
   var u1 = new User("Alice", new List<int> { 1, 2 });
   var u2 = u1 with { Name = "Bob" };
   u2.Roles.Add(3);
   ```
   **Apa yang terjadi pada `u1.Roles` setelah baris terakhir dieksekusi?**
   * A. `u1.Roles` tetap berisi `[1, 2]` karena record bersifat fully immutable.
   * B. Terjadi runtime exception `InvalidOperationException` karena collection terkunci.
   * C. `u1.Roles` berubah menjadi `[1, 2, 3]` karena ekspresi `with` mengeksekusi shallow copy referensi pointer list.
   * D. Program gagal dikompilasi pada ekspresi `with`.

7. **Mengapa `ref struct` tidak dapat mengimplementasikan antarmuka (interfaces) standar di C# (sebelum .NET 8 / C# 13 `allows ref struct`)?**
   * A. Karena compiler melarang polimorfisme untuk semua tipe struct.
   * B. Karena melempar struct ke interface memaksa proses *boxing* ke Managed Heap, yang melanggar garansi *stack-only* dari `ref struct`.
   * C. Karena interface tidak mengizinkan anggota method inline.
   * D. Karena memori method table pointer tidak dapat dibaca oleh antarmuka.

8. **Perhatikan deklarasi berikut:**
   ```csharp
   public abstract record Shape;
   public sealed record Circle(double Radius) : Shape;
   public sealed record Square(double Side) : Shape;
   ```
   **Apa tujuan membuat constructor dari `abstract record Shape` menjadi `private` jika seluruh turunan didefinisikan bersarang di dalamnya?**
   * A. Mencegah pemanggilan garbage collector pada turunan kelas.
   * B. Menghindari konsumsi memori object header pada runtime.
   * C. Mensimulasikan *Discriminated Unions* tertutup sehingga assembly eksternal tidak dapat menambah varian subtipe baru di luar domain yang diketahui.
   * D. Memaksa compiler Roslyn mematikan dukungan equality comparison.

9. **Apa fungsi dari atribut statis `[NotNullWhen(true)]` pada argumen `out` suatu metode pengetesan?**
   * A. Mengonversi tipe nullable `T?` menjadi unmanaged pointer `T*`.
   * B. Memberitahu engine static flow analysis compiler bahwa nilai argumen dijamin tidak null jika metode mengembalikan nilai boolean `true`.
   * C. Mencegah metode dipanggil dengan argumen bernilai null.
   * D. Melempar `NullReferenceException` seketika jika kondisi return menghasilkan false.

10. **Diberikan pattern expression berikut:**
    ```csharp
    item switch
    {
        [var x, .., var y] => x + y,
        [] => 0,
        _ => -1
    };
    ```
    **Fitur pattern matching apa yang digunakan pada baris pertama di dalam kurung siku?**
    * A. Relational and Logical Pattern.
    * B. List Pattern dengan Slice Pattern (`..`).
    * C. Positional Pattern dengan Deconstructor.
    * D. Direct Cast Declaration Matching.

---

#### Kunci Jawaban Kuis

* **Bagian A:**
  1. **B** — `record class` secara otomatis meng-override kesetaraan untuk membandingkan nilai properti secara struktural.
  2. **C** — `init` membatasi modifikasi hanya pada constructor atau inline object initializer.
  3. **B** — `required` memaksa penyertaan inisialisasi properti saat instansiasi pada compile-time.
  4. **C** — Struct mengalokasikan memori inline (biasanya Stack), membebaskan heap dari beban GC.
  5. **C** — Operator fungsional `with` digunakan untuk non-destructive mutation.

* **Bagian B:**
  6. **C** — Mutasi pada subtipe referensi internal membocorkan mutabilitas karena ekspresi `with` menyalin pointer referensi (*shallow copy*).
  7. **B** — Casting struct ke interface secara historis melakukan boxing objek ke managed heap, bertentangan dengan desain `ref struct`.
  8. **C** — Private constructor pada kelas abstrak mengunci hierarki tipe, memungkinkan pembuatan Discriminated Union tertutup.
  9. **B** — Kompilator menggunakan atribut tersebut untuk flow analysis sehingga pengembang tidak perlu menggunakan operator null-forgiving (`!`).
  10. **B** — Notasi `[var x, .., var y]` adalah List Pattern yang mengombinasikan pencocokan elemen awal dan akhir menggunakan Slice Pattern (`..`).

---

### SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

#### Deskripsi Tantangan
Anda ditugaskan merancang modul inti **"Resilient Order Processing Engine"** untuk platform e-commerce skala enterprise. Engine ini harus memproses pesanan dan menerapkan diskon menggunakan arsitektur tipe modern C# tanpa memicu `NullReferenceException` atau alokasi memori yang tidak efisien.

#### Spesifikasi Kebutuhan

1. **Domain State Representation (Discriminated Union):**
   Rancang tipe data `OrderState` menggunakan hierarki `abstract record` dengan varian:
   * `PendingPayment(DateTimeOffset ExpiryTime)`
   * `Paid(DateTimeOffset PaymentDate, string InvoiceNumber, decimal TotalPaid)`
   * `Shipped(string TrackingCode, string Courier)`
   * `Cancelled(string Reason, DateTimeOffset CancelledAt)`

2. **Customer Tier Model:**
   Gunakan positional `record class` untuk merepresentasikan profil pelanggan:
   * `Customer(Guid Id, string FullName, CustomerTier Tier, Address ShippingAddress)`
   * Di mana `CustomerTier` adalah enum: `Regular`, `Silver`, `Gold`, `Vip`.
   * Di mana `Address` adalah immutable record dengan validasi string non-null.

3. **Pattern Matching Discount Engine:**
   Buat kelas `DiscountEngine` dengan metode kalkulasi nilai diskon pesanan menggunakan ekspresi switch modern:
   * Jika Customer adalah `Vip` DAN nilai total pesanan $\ge \$1,000$, berikan diskon 20%.
   * Jika Customer adalah `Gold` ATAU pesanan memiliki total $\ge \$500$, berikan diskon 10%.
   * Jika State pesanan adalah `Cancelled`, diskon harus menghasilkan 0% dan dicatat sebagai transaksi diskon tidak sah.
   * Manfaatkan kombinasi *Relational Pattern*, *Logical Pattern*, dan *Property Pattern*.

4. **Zero-Allocation Order Line Metric:**
   Buat representasi `OrderLineMetric` menggunakan `readonly record struct` yang merekam:
   * `int ItemCount`
   * `decimal UnitPrice`
   * Hitung subtotal secara inline tanpa menghasilkan alokasi memori ke Managed Heap.

5. **Nullable Safety & Result Guard:**
   Bungkus seluruh hasil kalkulasi dalam immutable monadic generic struct `Result<T>` yang memanfaatkan atribut `[NotNullWhen(true)]` untuk flow checking kompilasi.

#### Kriteria Keberhasilan & Pengujian
* Proyek harus dikompilasi dengan konfigurasi `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>` dan `<Nullable>enable</Nullable>`.
* Tidak ada peringatan compiler CS8600 - CS8604 (bebas null reference hazard).
* Tidak ada pemanggilan destruktif *in-place property assignment* (seluruh transformasi state mutasi wajib menggunakan ekspresi `with`).
* Evaluasi kesetaraan dua instance order dengan atribut sama menghasilkan `true` (pembuktian *structural equality*).
* Sediakan berkas unit test ringkas (menggunakan `Debug.Assert`) untuk membuktikan seluruh percabangan pola switch berhasil dieksekusi secara deterministik.