# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Functional C#)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai implementasi tingkat lanjut dari paradigma pemrograman fungsional di C# (.NET 8/9) dengan zero/minimal allocation overhead.
- Mengimplementasikan arsitektur *Railway-Oriented Programming* (ROP) berbasis tipe monadik (`Result<T, E>`, `Option<T>`, `Either<L, R>`) untuk menggantikan kontrol alur berbasis exception (*exceptions as control flow anti-pattern*).
- Membedah dan mengendalikan mekanisme *lowering* compiler Roslyn pada konstruksi fungsional seperti closure lambdas, pattern matching, dan *non-destructive mutation* (`record with`).
- Merancang domain model yang aman (*parse, don't validate*) menggunakan *Algebraic Data Types* (ADT) dan *Discriminated Unions* tervendorisasi.
- Mengoptimalkan alur pemrosesan data asinkron fungsional berkinerja tinggi menggunakan `ValueTask`, `IAsyncEnumerable`, dan monad linier tanpa menimbulkan tekanan alokasi pada *Garbage Collector* (GC Gen 0/1).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
- Sintaks dasar C# functional features: Lambda Expressions, Local Functions, Linq standard query operators, Records, dan basic Pattern Matching.
- Manajemen memori CLR dasar: Stack vs Heap, perbedaan semantic `class`, `struct`, `readonly struct`, dan `ref struct`.
- Pemrograman Asinkron modern: `Task`, `ValueTask`, `async/await`, dan `CancellationToken`.
- Prinsip dasar Functional Programming: Immutability, Pure Functions, Side Effects, dan First-Class Functions.

---

## 3. Concept & Internal Architecture

Pemrograman fungsional pada C# modern bukanlah sekadar menggunakan LINQ atau sintaks lambda; ini menyangkut perancangan sistem deterministik dengan jaminan tipe statis pada waktu kompilasi (*compile-time correctness*), sembari menjaga karakteristik performa runtime CLR.

### Roslyn Lowering & Closure Allocation
Ketika Anda menulis fungsi fungsional tingkat tinggi (*higher-order functions*) atau ekspresi lambda yang menangkap variabel (*capturing context*), Roslyn melakukan de-sugar (*lowering*) menjadi kelas tersembunyi yang dialokasikan di heap:

```csharp
// Kode Asli
int factor = 10;
Func<int, int> multiplier = x => x * factor;
```

Compiler Roslyn mentransformasikannya menjadi:
```csharp
[CompilerGenerated]
private sealed class <>c__DisplayClass0_0
{
    public int factor;
    internal int <Main>b__0(int x) => x * this.factor;
}

// Eksekusi
<>c__DisplayClass0_0 displayClass = new <>c__DisplayClass0_0();
displayClass.factor = 10;
Func<int, int> multiplier = new Func<int, int>(displayClass.<Main>b__0);
```

Setiap pemanggilan memicu alokasi heap ganda: instansiasi `DisplayClass` dan delegat `Func<T>`. Untuk pipeline berthroughput tinggi (misal: order matching engine atau telemetry ingestion), alokasi ini memicu GC thrashing.

Solusi arsitektur produksi:
1. Gunakan `static lambda` (`static (x, state) => ...`) untuk mencegah *variable capturing*.
2. Operasikan fungsi melewati argumen eksplisit (`TState`) untuk mencapai zero-allocation pipeline.
3. Desain monad menggunakan `readonly record struct` untuk menjamin eksekusi di stack frame tanpa alokasi heap.

### Railway-Oriented Programming (ROP)
Secara arsitektural, ROP memodelkan kalkulasi bisnis sebagai dua lintasan paralel: *Success Track* dan *Failure Track*. Operasi fungsional dihubungkan melalui *monadic bind* (`FlatMap`/`SelectMany`) yang memutus evaluasi jalur sukses seketika terjadi kegagalan, meneruskan error secara deterministik tanpa melempar exception CLR yang mahal.

```
+------------------------------------------------------------------------+
|                               Input                                    |
+-----------------------------------+------------------------------------+
                                    |
                                    v
                     +--------------+--------------+
                     |    ValidateRequest(Input)   |
                     +--------------+--------------+
                                    |
               +--------------------+--------------------+
               | Success                                 | Failure
               v                                         v
+--------------+--------------+              +-----------+------------+
|     DebitAccount(Command)   |              |                        |
+--------------+--------------+              |                        |
               |                             |                        |
         +-----+-----+                       |                        |
 Success |           | Failure               |                        |
         v           v                       |                        |
+--------+-----+   +-+-----------------------+                        |
| EmitEvent()  |   | Passthrough Failure Track                        |
+--------+-----+   +-------------------------+                        |
         |                                   |                        |
         v                                   v                        v
+--------+-----------------------------------+------------------------+
|                      Railway Output: Result<T, E>                   |
+---------------------------------------------------------------------+
```

### Algebraic Data Types (ADT) via Discriminated Unions
C# belum memiliki first-class discriminated unions murni. Kita memodelkannya menggunakan hierarki `abstract record` dengan `private protected` constructor, memastikan tidak ada implementasi asing di luar assembly yang dapat memecahkan ekshausi (*exhaustiveness*) pattern matching.

---

## 4. Why & What

| Dimensi | Pendekatan Tradisional (Imperatif / Exception-Driven) | Pendekatan Enterprise Functional C# |
| :--- | :--- | :--- |
| **Kontrol Alur** | Mengandalkan `try-catch` lintas boundary domain service. | Lintasan deterministik: monad `Result<T, E>` / `Option<T>`. |
| **Performa Error** | Mahal; `throw new Exception()` membongkar frame stack dan metadata CLR. | Murah; representasi kegagalan adalah nilai biasa (`readonly struct`), alokasi 0 byte di heap. |
| **State Mutation** | Mutasi in-place via setter properti, rawan *data race* multi-threading. | Immutability absolut; mutasi non-destruktif (`with`), thread-safe by default. |
| **Domain Correctness**| Pengecekan `if (obj == null)` atau flag boolean rapuh di seluruh layer. | Compile-time exhaustiveness matching; compiler menolak kompilasi jika ada skenario cabang yang terlewat. |

---

## 5. How (Workflow Detail)

Alur kerja fungsional modern dalam pipeline pemrosesan API/Event:

```
[HTTP Request / Kafka Event]
             │
             ▼
[1. Pure Parsing Layer]
  - Konversi Raw JSON/Primitive menjadi Strong Value Objects
  - Mengembalikan Option<T> atau Result<T, ValidationError>
             │
             ▼ (Monadic Bind / Ensure)
[2. Domain Invariant Execution]
  - Pengecekan aturan bisnis murni (tanpa I/O)
  - Penilaian state transisi menggunakan Algebraic Data Types
             │
             ▼ (Monadic Bind / MapAsync)
[3. Side-Effect Boundary (Impure Action)]
  - Penyimpanan I/O (Database, Message Broker)
  - Isolasi dependensi asinkron via ValueTask/Task
             │
             ▼ (Monadic Match / Fold)
[4. Boundary Adaptation Layer]
  - Proyeksi Result<T, Error> ke HTTP Result (200 OK / 400 Bad Request / 409 Conflict)
  - Tidak ada kebocoran internal exception ke consumer eksternal
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sebuah pabrik perakitan elektronik:
- **Pendekatan Tradisional**: Jika baut longgar ditemukan di tengah jalur, pabrik meledakkan alarm sirene pabrik (`throw Exception`), menghentikan seluruh mesin konveyor, membuang semua barang di sabuk, dan memanggil tim pemadam kebakaran (`catch Block`) untuk membersihkan serpihan.
- **Pendekatan Fungsional Modern (ROP)**: Konveyor memiliki dua rel. Jika komponen cacat, switch otomatis mengarahkan produk cacat tersebut ke rel bawah (*Failure Track*), sementara produk bagus tetap berjalan di rel atas (*Success Track*). Semua pekerja berikutnya di rel atas otomatis mengabaikan barang yang sudah masuk ke rel bawah tanpa henti. Di ujung rel, barang dikelompokkan secara tertib: barang jadi masuk kotak kirim, barang cacat masuk laporan log.

```
SUTET KONVEYOR (Railway Track):

Success Track : [Paket Masuk]──(Validasi)────[OK]───(Otorisasi)────[OK]───(Eksekusi)───> [HTTP 200]
                                    │                     │
                                (Gagal)               (Gagal)
                                    │                     │
Failure Track :                     └───[Err: Invalid]────┴───[Err: Forbidden]──────────> [HTTP 4xx/5xx]
```

---

## 7. Simple Example & Practical Example

### Simple Example: Implementasi Core Primitive Monad `Result<T, E>` Zero-Allocation

```csharp
namespace Enterprise.FunctionalCore;

using System;
using System.Diagnostics.CodeAnalysis;

[System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Auto)]
public readonly record struct Result<TValue, TError>
{
    private readonly TValue? _value;
    private readonly TError? _error;

    public bool IsSuccess { get; }
    public bool IsFailure => !IsSuccess;

    private Result(TValue value)
    {
        IsSuccess = true;
        _value = value;
        _error = default;
    }

    private Result(TError error)
    {
        IsSuccess = false;
        _error = error;
        _value = default;
    }

    public static Result<TValue, TError> Success(TValue value) => new(value);
    public static Result<TValue, TError> Failure(TError error) => new(error);

    public static implicit operator Result<TValue, TError>(TValue value) => Success(value);

    public TResult Match<TResult>(
        Func<TValue, TResult> onSuccess,
        Func<TError, TResult> onFailure) =>
        IsSuccess ? onSuccess(_value!) : onFailure(_error!);

    public Result<TOut, TError> Map<TOut>(Func<TValue, TOut> mapper) =>
        IsSuccess ? Result<TOut, TError>.Success(mapper(_value!)) : Result<TOut, TError>.Failure(_error!);

    public Result<TOut, TError> Bind<TOut>(Func<TValue, Result<TOut, TError>> binder) =>
        IsSuccess ? binder(_value!) : Result<TOut, TError>.Failure(_error!);
}
```

### Practical Example: Domain Modeling dengan Algebraic Data Types & Exhaustive Matching

```csharp
namespace Enterprise.PaymentDomain;

using System;
using Enterprise.FunctionalCore;

// Modeling Domain Errors as Closed Hierarchy
public abstract record PaymentError
{
    private PaymentError() { } // Mencegah pewarisan luar assembly

    public sealed record InsufficientFunds(decimal Balance, decimal AttemptedAmount) : PaymentError;
    public sealed record AccountBlocked(string Reason) : PaymentError;
    public sealed record GatewayTimeout(string Provider) : PaymentError;
}

// Modeling Domain Entity State as ADT
public abstract record PaymentTransaction
{
    public required Guid Id { get; init; }
    public required decimal Amount { get; init; }
    public required string Currency { get; init; }

    private PaymentTransaction() { }

    public sealed record Initiated : PaymentTransaction;
    public sealed record Authorized(string AuthCode) : PaymentTransaction;
    public sealed record Settled(DateTime SettledAtUtc) : PaymentTransaction;
    public sealed record Failed(PaymentError Error) : PaymentTransaction;
}

public static class PaymentEngine
{
    public static Result<PaymentTransaction.Authorized, PaymentError> Authorize(
        PaymentTransaction.Initiated tx,
        decimal availableBalance)
    {
        if (availableBalance < tx.Amount)
        {
            return Result<PaymentTransaction.Authorized, PaymentError>.Failure(
                new PaymentError.InsufficientFunds(availableBalance, tx.Amount));
        }

        return Result<PaymentTransaction.Authorized, PaymentError>.Success(
            new PaymentTransaction.Authorized("AUTH-" + Guid.NewGuid().ToString("N")[..8])
            {
                Id = tx.Id,
                Amount = tx.Amount,
                Currency = tx.Currency
            });
    }

    public static PaymentTransaction Process(PaymentTransaction current) =>
        current switch
        {
            PaymentTransaction.Initiated init => 
                Authorize(init, 500m).Match<PaymentTransaction>(
                    onSuccess: auth => auth,
                    onFailure: err => new PaymentTransaction.Failed(err) { Id = init.Id, Amount = init.Amount, Currency = init.Currency }),
            
            PaymentTransaction.Authorized auth => 
                new PaymentTransaction.Settled(DateTime.UtcNow) 
                { 
                    Id = auth.Id, 
                    Amount = auth.Amount, 
                    Currency = auth.Currency 
                },

            PaymentTransaction.Settled settled => settled, // Idempotent
            PaymentTransaction.Failed failed => failed,     // Terminal state
            _ => throw new InvalidOperationException("Unhandled state transition")
        };
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Pipeline Rekonsiliasi Transaksi Kliring Finansial
Sebuah sistem kliring antarbank memproses 150.000 transaksi/menit. Menggunakan model OOP konvensional berbasis mutasi in-memory dan eksepsi, latensi p99 menyentuh 1.8 detik karena GC Gen 2 stop-the-world pauses dan biaya unwinding stack trace ketika terjadi *validation failure*.

Arsitektur direkayasa ulang menggunakan fungsional murni:
1. Data feed stream dibaca sebagai `IAsyncEnumerable<ReadOnlyMemory<byte>>`.
2. Parsing menggunakan zero-allocation `Span<T>` pattern matching.
3. Rangkaian ROP mengombinasikan validasi akun, limit checks, anti-fraud, dan settlement.

```csharp
namespace Enterprise.FinancialClearing;

using System;
using System.Threading;
using System.Threading.Tasks;
using Enterprise.FunctionalCore;

public readonly record struct ClearingPayload(
    Guid TransactionId,
    string DebtorIban,
    string CreditorIban,
    decimal Amount,
    string Currency);

public abstract record ClearingRejection
{
    private ClearingRejection() { }
    public sealed record InvalidPayload(string Detail) : ClearingRejection;
    public sealed record LimitExceeded(decimal MaxLimit) : ClearingRejection;
    public sealed record SanctionHit(string RuleId) : ClearingRejection;
    public sealed record LedgerUnavailable(string Message) : ClearingRejection;
}

public sealed record SettlementReceipt(Guid TxId, DateTime ProcessedUtc, string LedgerTraceId);

public static class ClearingPipeline
{
    public static async ValueTask<Result<SettlementReceipt, ClearingRejection>> ExecutePipelineAsync(
        ClearingPayload raw,
        Func<ClearingPayload, ValueTask<bool>> sanctionCheckFunc,
        Func<ClearingPayload, ValueTask<Result<string, string>>> ledgerCommitFunc,
        CancellationToken ct)
    {
        // Step 1: Pure In-Memory Validation (Synchronous, Zero Alloc)
        var validationResult = ValidateInvariants(raw);
        if (validationResult.IsFailure)
        {
            return Result<SettlementReceipt, ClearingRejection>.Failure(validationResult.Match(_ => null!, err => err));
        }

        var payload = validationResult.Match(v => v, _ => default);

        // Step 2: Async Fraud / Sanction Screen
        var isSanctioned = await sanctionCheckFunc(payload).ConfigureAwait(false);
        if (isSanctioned)
        {
            return Result<SettlementReceipt, ClearingRejection>.Failure(
                new ClearingRejection.SanctionHit("AML-OFAC-SEC-44"));
        }

        // Step 3: Ledger IO Side Effect
        ct.ThrowIfCancellationRequested();
        var ledgerResult = await ledgerCommitFunc(payload).ConfigureAwait(false);

        return ledgerResult.Match(
            onSuccess: traceId => Result<SettlementReceipt, ClearingRejection>.Success(
                new SettlementReceipt(payload.TransactionId, DateTime.UtcNow, traceId)),
            onFailure: err => Result<SettlementReceipt, ClearingRejection>.Failure(
                new ClearingRejection.LedgerUnavailable(err)));
    }

    private static Result<ClearingPayload, ClearingRejection> ValidateInvariants(in ClearingPayload payload)
    {
        if (payload.TransactionId == Guid.Empty)
            return Result<ClearingPayload, ClearingRejection>.Failure(new ClearingRejection.InvalidPayload("Empty Transaction ID"));

        if (payload.Amount <= 0m)
            return Result<ClearingPayload, ClearingRejection>.Failure(new ClearingRejection.InvalidPayload("Amount must be positive"));

        if (payload.Amount > 10_000_000m)
            return Result<ClearingPayload, ClearingRejection>.Failure(new ClearingRejection.LimitExceeded(10_000_000m));

        if (string.IsNullOrWhiteSpace(payload.DebtorIban) || string.IsNullOrWhiteSpace(payload.CreditorIban))
            return Result<ClearingPayload, ClearingRejection>.Failure(new ClearingRejection.InvalidPayload("IBAN strings cannot be blank"));

        return Result<ClearingPayload, ClearingRejection>.Success(payload);
    }
}
```

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter | Immutability / Monadic Functional | Mutasi Imperatif Standar | Penjelasan Rekayasa |
| :--- | :--- | :--- | :--- |
| **GC Pressure** | Sangat rendah jika menggunakan `readonly struct`, tetapi meningkat drastis jika sembarangan menggunakan `record class with`. | Rendah pada in-place update sederhana, tinggi jika membuang exception object di jalur kritis. | Mutasi non-destruktif pada reference type menyalin object baru ke heap. Gunakan `struct` untuk tipe berumur pendek. |
| **Stack Size** | Berisiko Stack Overflow jika rekursi mendalam tidak menggunakan teknik iterative-unrolling (C# tidak menjamin *Tail-Call Optimization* - TCO). | Aman dari Stack Overflow karena memakai loop primitif (`while`/`for`). | Selalu preferensikan LINQ unrolled, `Aggregate` terstruktur, atau loops daripada rekursi murni pada volume data masif. |
| **Latency (p99)** | Sangat stabil dan deterministik karena tidak ada *unhandled unwinding overhead* dari exception. | Fluktuatif; `throw` mengorbankan siklus CPU untuk menyusun call stack snapshot. | ROP memotong latensi hingga 90% pada skenario di mana rasio kegagalan bisnis (*business rejection*) > 5%. |
| **Learning Curve & Onboarding** | Tinggi. Paradigma ROP, Currying, dan Higher-Kinded Types emulation memerlukan pergeseran mental tim. | Rendah. Semua pengembang memahami pola `try-catch-finally` dan `if-else`. | Biaya training awal tinggi, tetapi menurunkan *maintenance cost* dan *defect leakage* di lingkungan produksi. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Memory Leaks Melalui Implicit Closure Capture
```csharp
// FATAL: Variabel logger dan threshold tercapture ke dalam DisplayClass heap
public void SetupFilter(ILogger logger, decimal threshold)
{
    _stream.Where(tx => {
        logger.LogInformation("Checking tx {Id}", tx.Id); // Heap Allocation!
        return tx.Amount > threshold;                     // Heap Allocation!
    });
}
```
**Troubleshooting**: Gunakan `static lambda` untuk memaksa compiler mendeteksi capturing:
```csharp
// COMPILER ERROR JIKA CAPTURING: CS8820
_stream.Where(static tx => tx.Amount > 100m);
```

### Mistake 2: Missing Case Handling pada Pattern Matching (Exhaustiveness Failure)
Mendefinisikan ADT tanpa proteksi konstruktor, menyebabkan library consumer meng-extend tipe baru yang membuat runtime melempar `SwitchExpressionException`.
**Troubleshooting**: Terapkan `private protected` constructor pada basis kelas dan pasang rule Roslyn Analyzer `CS8509` sebagai **Error** pada file `.editorconfig`:
```ini
dotnet_diagnostic.CS8509.severity = error
```

### Mistake 3: Exception Swallowing dalam Asynchronous Monads
Mengabaikan cancellation token saat mengimplementasikan ekstensi `BindAsync`.
**Troubleshooting**: Pastikan selalu meneruskan `CancellationToken` ke dalam monadic operator rantai berikutnya:
```csharp
public static async ValueTask<Result<U, E>> BindAsync<T, U, E>(
    this ValueTask<Result<T, E>> source,
    Func<T, CancellationToken, ValueTask<Result<U, E>>> binder,
    CancellationToken ct = default)
{
    var result = await source.ConfigureAwait(false);
    return result.IsSuccess 
        ? await binder(result.Value, ct).ConfigureAwait(false) 
        : Result<U, E>.Failure(result.Error);
}
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Gunakan `readonly struct` untuk Monad**: Struktur `Result<T, E>` atau `Option<T>` harus berupa value type demi menghindari alokasi Gen 0 GC.
- [ ] **Deklarasikan Lambda Sebagai `static`**: Pasang keyword `static` pada ekspresi lambda LINQ internal untuk mencegah pembuatan instance delegat berulang dan closure.
- [ ] **Enforce ADT Exhaustiveness**: Buat constructor root class bernilai `private protected` dan jangan pernah menggunakan cabang `_ => default` sembarangan pada `switch expression` bisnis inti.
- [ ] **Pisahkan Pure Function dari Side Effect**: Letakkan domain logic di pure function (in-memory, sync, deterministic) dan batasi side-effect (DB, Cache, Network) pada boundary layer terluar.
- [ ] **Hindari Throwing Business Exceptions**: Konversikan seluruh *domain violation* menjadi `Result.Failure(DomainError)`. Gunakan exception murni untuk *catastrophic failure* (network down, OOM, disk corruption).
- [ ] **Lindungi Defensive Immutability**: Properti koleksi pada Domain Record wajib menggunakan `IReadOnlyList<T>`, `ImmutableArray<T>`, atau `ReadOnlyMemory<T>`, bukan `List<T>`.

---

## 12. Hands-on Practice

Target Direktori: `hands-on/m02/`

### File: `hands-on/m02/FunctionalPrimitives.cs`
```csharp
namespace HandsOn.Functional;

using System;
using System.Runtime.InteropServices;

[StructLayout(LayoutKind.Auto)]
public readonly record struct Option<T>
{
    private readonly T? _value;
    public bool HasValue { get; }

    private Option(T value)
    {
        HasValue = true;
        _value = value;
    }

    public static Option<T> None => default;
    public static Option<T> Some(T value) => 
        value is null ? throw new ArgumentNullException(nameof(value)) : new(value);

    public TResult Match<TResult>(Func<TResult> onNone, Func<T, TResult> onSome) =>
        HasValue ? onSome(_value!) : onNone();

    public Option<TOut> Map<TOut>(Func<T, TOut> mapper) =>
        HasValue ? Option<TOut>.Some(mapper(_value!)) : Option<TOut>.None;
}
```

### File: `hands-on/m02/DomainModel.cs`
```csharp
namespace HandsOn.Functional;

using System;

public abstract record OrderEvent
{
    public required Guid OrderId { get; init; }
    public DateTime TimestampUtc { get; init; } = DateTime.UtcNow;

    private OrderEvent() { }

    public sealed record Created(string CustomerId, decimal Amount) : OrderEvent;
    public sealed record Paid(string ProviderRef) : OrderEvent;
    public sealed record Shipped(string TrackingNumber) : OrderEvent;
    public sealed record Cancelled(string Reason) : OrderEvent;
}

public sealed record OrderState(
    Guid OrderId,
    string CustomerId,
    decimal Amount,
    string Status,
    Option<string> TrackingNumber);
```

### File: `hands-on/m02/Program.cs`
```csharp
namespace HandsOn.Functional;

using System;
using System.Collections.Generic;

public static class Program
{
    public static void Main()
    {
        var events = new OrderEvent[]
        {
            new OrderEvent.Created("CUST-101", 2500m) { OrderId = Guid.NewGuid() },
            new OrderEvent.Paid("EXT-PAY-998811"),
            new OrderEvent.Shipped("TRACK-ID-44210")
        };

        var finalState = AggregateOrder(events);
        
        Console.WriteLine($"Order Processed: {finalState.OrderId}");
        Console.WriteLine($"Status: {finalState.Status}");
        finalState.TrackingNumber.Match(
            onNone: () => Console.WriteLine("Tracking: N/A"),
            onSome: track => Console.WriteLine($"Tracking: {track}")
        );
    }

    public static OrderState AggregateOrder(IEnumerable<OrderEvent> history)
    {
        var initial = new OrderState(Guid.Empty, string.Empty, 0m, "Uninitialized", Option<string>.None);

        // Functional fold/aggregate tanpa mutasi state in-place
        return history.Aggregate(initial, static (state, ev) => ev switch
        {
            OrderEvent.Created c => state with 
            { 
                OrderId = c.OrderId, 
                CustomerId = c.CustomerId, 
                Amount = c.Amount, 
                Status = "Created" 
            },
            OrderEvent.Paid => state with 
            { 
                Status = "Paid" 
            },
            OrderEvent.Shipped s => state with 
            { 
                Status = "Shipped", 
                TrackingNumber = Option<string>.Some(s.TrackingNumber) 
            },
            OrderEvent.Cancelled c => state with 
            { 
                Status = $"Cancelled: {c.Reason}" 
            }
        });
    }
}
```

---

## 13. Exercise

### Level Easy
Modifikasi implementasi `Option<T>` di Hands-on practice untuk menyertakan metode `Reduce(T defaultValue)`. Jika `Option<T>` bernilai `Some`, kembalikan nilainya; jika `None`, kembalikan `defaultValue`.

### Level Medium
Buat extension method `Ensure` untuk `Result<T, E>` dengan signature:
```csharp
public static Result<T, E> Ensure(
    this Result<T, E> result, 
    Func<T, bool> predicate, 
    E errorIfInvalid);
```
Metode ini harus mengevaluasi predicate hanya jika hasil sebelumnya bernilai `Success`. Jika predicate mengembalikan `false`, ubah menjadi `Result.Failure(errorIfInvalid)`.

### Level Hard
Implementasikan monadic pipeline builder `Select` dan `SelectMany` untuk tipe struct `Result<T, E>` sehingga dapat ditulis menggunakan sintaks C# LINQ Comprehension Syntax:
```csharp
Result<decimal, string> computation = 
    from a in ValidatePositive(inputA)
    from b in ValidatePositive(inputB)
    from c in Divide(a, b)
    select c;
```
Pastikan seluruh alur dieksekusi dengan *short-circuiting* (eksekusi berhenti begitu ada sub-ekspresi yang bernilai failure) dan **zero heap allocation**.

---

## 14. Challenge

Rancang dan bangun arsitektur sistem pemrosesan pesan *Order Matching Engine* frekuensi tinggi berbasis Fungsional Murni.

### Batasan Arsitektur & Kasus:
1. Engine menerima stream pesanan saham (*Bids* dan *Asks*).
2. Domain model harus menggunakan Algebraic Data Types (ADT) tertutup merepresentasikan: `LimitOrder`, `MarketOrder`, `StopLoss`.
3. Order state transition hanya boleh dilakukan melalui pure function reducer:
   `(OrderBook, IncomingOrder) -> Result<(OrderBook NewBook, ReadOnlyMemory<TradeExecution> Trades), MatchingError>`.
4. **Alokasi Memori**: Zero Gen 0/1 Heap Allocation di dalam looping match execution (gunakan `readonly ref struct` jika diperlukan untuk parsing atau `Memory<T>` pools).
5. Uji performa pipeline Anda dengan throughput minimal 500.000 order/detik dengan alokasi heap 0 bytes pada hot path processing logic.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Apa alasan fundamental penggunaan `readonly struct` dibandingkan `class` saat mendesain monad generic seperti `Result<T, E>` di C#?
2. Apa yang dikompilasi oleh Roslyn ketika sebuah ekspresi lambda mengacu pada variabel lokal di luar cakupannya?
3. Mengapa keyword `with` pada C# Record type disebut sebagai *non-destructive mutation*?
4. Apa perbedaan struktural antara operasi `Map` (Functor) dan `Bind` / `FlatMap` (Monad)?
5. Bagaimana keyword `static` pada ekspresi lambda (`static (x) => ...`) menjamin efisiensi performa memori?

### 5 Pertanyaan Intermediate
6. Jelaskan konsekuensi CLR runtime jika sebuah pipeline fungsional rekursif mendalam dijalankan tanpa Tail-Call Optimization (TCO)!
7. Mengapa penggunaan *Exception as Control Flow* (misal: melempar `NotFoundException`) merusak latensi p99 sistem transaksi tinggi?
8. Bagaimana cara menjamin *Compile-Time Exhaustiveness* pada C# pattern matching tanpa menambahkan klausa catch-all default (`_ =>`)?
9. Apa perbedaan memory layout antara `record struct` dan `record class` saat mengalami operasi modifikasi non-destruktif?
10. Bagaimana Anda mengatasi issue asinkronitas pada Monad, seperti menangani tipe bersarang `Task<Result<Option<T>, E>>` agar tidak menjadi callback hell?

### 3 Skenario Kasus Produksi
11. **Skenario Profiling**: Tim Anda mendapati lonjakan frekuensi Gen 0 GC pauses dari 5ms menjadi 120ms setelah mengadopsi functional LINQ chains di service pipeline pembayaran. Jelaskan langkah inspeksi memory dump dan strategi perbaikan konversi kodenya!
12. **Skenario API Failure Resilience**: Sebuah downstream microservice inventaris sering merespons lambat (p99 > 4000ms) atau time-out. Rancang integrasi ROP yang memadukan monadic pattern dengan *Circuit Breaker* berbasis state transition tanpa melempar exception!
13. **Skenario Domain Boundary**: Bagaimana Anda memetakan monad internal `Result<TDomain, DomainError>` ke representasi eksternal protokol komunikasi berbeda secara bersih (misalnya HTTP REST Status Code vs gRPC Status Codes) pada Clean/Hexagonal Architecture?

---

## 16. Summary

- Pemrograman fungsional enterprise pada C# (.NET 8/9) adalah perpaduan ketat antara kejelasan matematis (*correctness*, *immutability*, *exhaustiveness*) dengan efisiensi sistem CLR tingkat rendah (*value types*, *zero closure allocations*).
- **Railway-Oriented Programming (ROP)** mengubah manajemen kegagalan dari eksepsi imperatif yang lambat menjadi representasi nilai statis yang terprediksi, meningkatkan ketahanan sistem dan latensi p99 secara dramatis.
- **Algebraic Data Types (ADT)** dan **Pattern Matching** memungkinkan pengembang memodelkan dunia nyata secara presisi sehingga state yang tidak valid menjadi tidak dapat dikompilasi (*make illegal states unrepresentable*).
- Untuk mencapai standar industri modern, setiap arsitek C# wajib memahami apa yang terjadi di balik layer abstraksi Roslyn: mengeliminasi alokasi display class yang tak terlihat dan mengendalikan alokasi heap secara disiplin di setiap lintasan kritis aplikasi.