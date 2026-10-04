# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: Modern Type System & OOP Kontemporer**
**Kategori: 02-Programming-Languages / C# (.NET 8/9 LTS)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Software Engineer / Lead Architect diharapkan mampu:
1. **Menganalisis dan Membedah Internal CLR**: Memahami representasi memori tingkat rendah (*Object Header*, *MethodTable Pointer*, *EEType*, *Memory Alignment*, dan *Padding*) untuk entitas `class`, `struct`, `readonly record struct`, dan `ref struct`.
2. **Menguasai Polimorfisme Modern**: Mengimplementasikan *Static Abstract Members in Interfaces* (C# 11/12), *Virtual Stub Dispatch* (VSD), dan *Default Interface Methods* (DIM) untuk mengeliminasi alokasi dinamis (*zero-allocation polymorphic design*).
3. **Membangun Domain Model Berkinerja Tinggi**: Mendesain arsitektur domain fungsional-objek hibrida menggunakan *Discriminated Unions pattern*, *Exhaustive Pattern Matching*, dan *Immutability by Default* tanpa menimbulkan penalti *Garbage Collection* (GC) atau *Boxing/Unboxing*.
4. **Menerapkan Advanced Generics Variance**: Mengonfigurasi kovariansi (`out`) dan kontravariansi (`in`) secara presisi pada generic pipeline pemrosesan event terdistribusi.

---

## 2. Prerequisite

Sebelum menempuh modul lanjutan ini, Anda wajib menguasai:
*   Siklus hidup alokasi memori C# dasar: Stack vs Managed Heap.
*   Pemahaman eksekusi Intermediate Language (IL) via `dotnet-ildasm` atau Sharplab.io.
*   Sintaks dasar generic constraints (`where T : class`, `new()`).
*   Prinsip Object-Oriented Analysis and Design (SOLID) standar.

---

## 3. Concept & Internal Architecture

Modern C# telah bertransformasi dari paradigma OOP murni berbasis referensi (*nominal subtyping*) menjadi sistem tipe kontemporer berperforma tinggi yang memadukan keamanan fungsional (*algebraic data types*) dan kendali memori level rendah.

### 3.1. Anatomi Memori Runtime: Class vs. Struct vs. Record Struct

Pada arsitektur 64-bit (`x64`), setiap instansiasi objek pada Managed Heap memiliki overhead struktural yang dikelola oleh Common Language Runtime (CLR):

```
+-------------------------------------------------------------+
|                     CLASS INSTANCE (Heap)                   |
+-------------------------------------------------------------+
| Object Header (SyncBlockIndex) : 8 Bytes                    |
+-------------------------------------------------------------+
| MethodTable Pointer (EEType*)   : 8 Bytes                    |
+-------------------------------------------------------------+
| Instance Fields Data           : Variable (Padded to 8B)    |
+-------------------------------------------------------------+

+-------------------------------------------------------------+
|                 STRUCT INSTANCE (Stack/Inline)              |
+-------------------------------------------------------------+
| Instance Fields Data           : Variable (Pack alignment)  |
+-------------------------------------------------------------+
* Tidak memiliki Object Header maupun MethodTable Pointer *
```

*   **Object Header (8 bytes pada x64):** Menyimpan *SyncBlockIndex*, hash code turunan, serta data sinkronisasi `lock`.
*   **MethodTable Pointer (8 bytes pada x64):** Pointer ke struktur internal `MethodTable` tipe tersebut. Digunakan untuk resolusi pemanggilan metode virtual, informasi tipe runtime (`GetType()`), dan operasi `isinst`/`castclass`.
*   **Struct:** Murni berisi data field. Jika struct dilewatkan ke parameter bertipe `object` atau interface (tanpa generic constraints), runtime melakukan **Boxing**: mengalokasikan blok memori 16-byte (Header + MethodTable) di heap, menyalin bitfield struct ke dalamnya, dan mengembalikan referensi objek.

### 3.2. Dynamic Dispatch: VTable vs. Virtual Stub Dispatch (VSD)

Pemanggilan metode pada C# melibatkan tiga mekanisme berbeda di level CPU:
1.  **Direct Call (`call` IL instruction):** Resolusi alamat fungsi dilakukan saat JIT-compile. Non-virtual methods dieksekusi melalui lompatan memori langsung (`call target_address`).
2.  **Virtual Call (`callvirt` IL instruction):** Resolusi melalui indexing pada Virtual Method Table (VTable) kelas target. Membutuhkan dereferensi pointer: `MethodTable -> VTable[Slot] -> Execute`.
3.  **Interface Call via Virtual Stub Dispatch (VSD):** Karena satu struct/class dapat mengimplementasikan banyak antarmuka yang letak slot method-nya tidak seragam di VTable, CLR menggunakan stubs:
    *   *Monomorphic Cache:* Jika call-site hanya pernah menerima 1 tipe implementasi konkret, stub langsung melompat ke alamat target (setara direct call dengan check).
    *   *Polymorphic Cache:* Menangani tabel lookup kecil berbasis hash.
    *   *Megamorphic Stub:* Melempar lookup ke mekanisme *Global Interface Dispatch Table*, menurunkan throughput instruksi CPU secara drastis.

### 3.3. Static Abstract Members in Interfaces (Generic Math & Traits)

Sejak C# 11, interface dapat mendefinisikan kontrak statis menggunakan keyword `static abstract`. Fitur ini mengubah cara abstraksi beroperasi di CLR:
*   Resolusi pemanggilan metode statis terjadi pada masa kompilasi JIT berdasarkan tipe generik konkret (`T`), tanpa runtime overhead VTable lookup.
*   Memungkinkan pembuatan generic operators (`+`, `-`, `*`), parsing (`IParsable<TSelf>`), dan factory pattern (`IFactory<TSelf>`) yang type-safe tanpa alokasi heap.

---

## 4. Why & What

| Paradigma Lama (C# 1 - 7) | Paradigma Kontemporer (C# 8 - 12+) | Mengapa Diubah? (Motivasi Teknis) |
| :--- | :--- | :--- |
| Pewarisan kelas hierarkis dalam (`class Base -> Derived`) | Komposisi pipih, `record`, `sealed interface` | Menghindari kerapuhan basis data (*Fragile Base Class problem*) dan alokasi referensi heap tak terkontrol. |
| Nullable Reference Type implisit (rentan `NullReferenceException`) | Explicit Nullable Context (`T?` vs `T`) via Static Flow Analysis | Menghilangkan kategori bug produksi nomor satu secara statis pada fase kompilasi. |
| Abstraksi polymorphic via interface instansiasi objek (`heap`) | Static Abstract Interface Members & Zero-Alloc Generics | Mengizinkan abstraksi tanpa penalti *pointer chasing* dan alokasi GC LOH/SOH. |
| Pemodelan data dinamis via `enum` terpisah + `switch-case` rentan *runtime failure* | Closed Type Hierarchies (Simulasi Discriminated Unions) + Exhaustive Matching | Memastikan kelengkapan cabang logika saat compile time (*exhaustiveness check*). |

---

## 5. How (Workflow detail)

Implementasi arsitektur tipe modern pada sistem *high-throughput*:

```
[1. Definisi Kontrak]
       │
       ▼
[Interface dengan Static Abstract Members]
       │
       ▼
[Implementasi Type Hierarchies via 'readonly record struct' / 'sealed record class']
       │
       ▼
[Exhaustive Pattern Matching Expression via Switch Expression]
       │
       ▼
[JIT-Compilation: Inlining & Devirtualization (Zero Boxing)]
```

1.  **Definisikan State:** Gunakan `readonly record struct` untuk payload data di bawah 16-24 bytes, dan `sealed record class` untuk data payload besar berumur panjang.
2.  **Bentuk Closed Hierarchy:** Gunakan interface `sealed` secara logika (atau base record bertipe `abstract`) dengan konstruktor privat untuk membatasi turunan.
3.  **Konsumsi via Pattern Matching:** Terapkan pemrosesan state menggunakan *type pattern*, *property pattern*, dan *relational pattern*. Pastikan compiler mengeluarkan warning/error bila ada state yang belum ter-handle (Exhaustiveness).
4.  **Optimasi Alokasi:** Terapkan generic parameter dengan constraint `where T : struct, IInterface` guna memicu JIT monomorphization, mengeliminasi boxing seutuhnya.

---

## 6. Analogy & Diagram ASCII

Bayangkan sebuah jalur perakitan manufaktur otomatis:

*   **Classic OOP (Class Inheritance):** Setiap paket dimasukkan ke dalam wadah akrilik berat ber-ID unik (*Object Header + MethodTable*). Meskipun isinya hanya sebutir baut (*int*), wadah ini wajib didaftarkan, dilacak oleh robot pembersih (*Garbage Collector*), dan dibuka tutup menggunakan manual identifikasi (*Virtual VTable lookup*).
*   **Modern Contemporary Type System (Structs, Records, Pattern Matching):** Paket adalah data telanjang yang dicetak presisi di atas sabuk berjalan (*Stack*). Pemilah otomatis berkecepatan tinggi menggunakan sinar laser (*Pattern Matching*) langsung mengevaluasi geometri paket tanpa perlu membuka wadah, dan mesin perakit tahu cara memprosesnya langsung tanpa manual instruksi dinamis (*Static Abstract devirtualization*).

```
VIRTUAL METHOD DISPATCH (Heap Chasing)
Object Ref (RSI) ──> [Object Header]
                     [MethodTable Pointer] ──> [MethodTable]
                     [Field: Data        ]          │
                                                    ▼
                                            [VTable Slot #3] ──> JMP target_func()

STATIC ABSTRACT RESOLUTION (Direct Monomorphized JIT Execution)
Call site: Process<Order>(order)
JIT compiles concrete: Process_Order(Order order) ──> Directly emits: CALL Order::Execute()
(Zero indirection, Zero heap pointer dereferencing)
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Analisis Semantik Kesetaraan & Memori

```csharp
// Program.cs
using System;

public class Program
{
    public static void Main()
    {
        // Class: Reference Equality secara default
        var c1 = new PointClass(10, 20);
        var c2 = new PointClass(10, 20);
        Console.WriteLine($"Class Reference Equals: {c1 == c2}"); // False

        // Record Class: Structural Equality otomatis di Heap
        var r1 = new PointRecord(10, 20);
        var r2 = new PointRecord(10, 20);
        Console.WriteLine($"Record Structural Equals: {r1 == r2}"); // True

        // ReadOnly Record Struct: Structural Equality di Stack (Zero Allocation)
        var s1 = new PointStruct(10, 20);
        var s2 = new PointStruct(10, 20);
        Console.WriteLine($"Struct Equals: {s1 == s2}"); // True
    }
}

public class PointClass(int x, int y)
{
    public int X { get; } = x;
    public int Y { get; } = y;
}

public record PointRecord(int X, int Y);

public readonly record struct PointStruct(int X, int Y);
```

### 7.2. Practical Example: Enterprise Generic Type-Safe Pipeline

Berikut adalah arsitektur *Zero-Allocation Parsing & Processing Engine* menggunakan *Static Abstract Members* dan *Discriminated Unions Pattern*:

```csharp
namespace Enterprise.TypeSystem.Core;

// 1. Static Abstract Interface: Contract untuk Factory & Parser tanpa alokasi instans
public interface IInboundMessage<TSelf> where TSelf : IInboundMessage<TSelf>
{
    static abstract string MessageTypeIdentifier { get; }
    static abstract bool TryParse(ReadOnlySpan<byte> source, out TSelf result);
    void ExecuteWorkflow();
}

// 2. Closed Type Hierarchy (Discriminated Union Implementation)
public abstract record FinancialTransaction
{
    // Konstruktor privat mencegah inheritance di luar file/tipe ini
    private FinancialTransaction() { }

    public sealed record Deposit(Guid AccountId, decimal Amount, string Currency) : FinancialTransaction();
    public sealed record Withdrawal(Guid AccountId, decimal Amount, decimal Fee) : FinancialTransaction();
    public sealed record Transfer(Guid SourceAccountId, Guid DestinationAccountId, decimal Amount) : FinancialTransaction();
    public sealed record Reversal(Guid OriginalTransactionId, string Reason) : FinancialTransaction();
}

// 3. High-Performance Static Abstract Implementation
public readonly record struct SettlementBatch : IInboundMessage<SettlementBatch>
{
    public required Guid BatchId { get; init; }
    public required int TransactionCount { get; init; }

    public static string MessageTypeIdentifier => "SETTLE_V1";

    public static bool TryParse(ReadOnlySpan<byte> source, out SettlementBatch result)
    {
        // Parsing biner zero-allocation sederhana (contoh skematis)
        if (source.Length < 20)
        {
            result = default;
            return false;
        }

        var id = new Guid(source[..16]);
        var count = BitConverter.ToInt32(source[16..20]);

        result = new SettlementBatch { BatchId = id, TransactionCount = count };
        return true;
    }

    public void ExecuteWorkflow()
    {
        // Batch processing logic
    }
}

// 4. Exhaustive Pattern Matching Engine
public static class TransactionProcessor
{
    public static string EvaluateRiskProfile(FinancialTransaction transaction) =>
        transaction switch
        {
            FinancialTransaction.Deposit { Amount: > 100_000_000 } d =>
                $"HIGH_RISK_AML: Deposit senilai {d.Amount} {d.Currency}",
            
            FinancialTransaction.Deposit d =>
                $"STANDARD_DEPOSIT: {d.Amount} {d.Currency}",
            
            FinancialTransaction.Withdrawal { Amount: var a, Fee: var f } when a + f > 50_000_000 =>
                $"HIGH_RISK_LIQUIDITY: Withdrawal {a} dengan fee {f}",
            
            FinancialTransaction.Withdrawal w =>
                $"STANDARD_WITHDRAWAL: {w.Amount}",
            
            FinancialTransaction.Transfer { SourceAccountId: var src, DestinationAccountId: var dst } when src == dst =>
                throw new InvalidOperationException("Circular transfer terdeteksi."),
            
            FinancialTransaction.Transfer t =>
                $"VALID_TRANSFER: Transfer {t.Amount} ke {t.DestinationAccountId}",
            
            FinancialTransaction.Reversal r =>
                $"REVERSAL_OPERATION: Referensi Tx {r.OriginalTransactionId}, Alasan: {r.Reason}",

            // Tidak memerlukan default (_) jika seluruh record turunan FinancialTransaction ter-cakup.
            // Jika ada turunan baru ditambahkan, compiler akan melempar warning CS8509 (Non-exhaustive switch expression).
        };
}
```

---

## 8. Real World Case Study: High-Frequency Payment Routing Engine

### Deskripsi Masalah
Platform *Payment Gateway* memproses 40.000 transaksi pembayaran heterogen per detik (*Credit Card, QRIS, Virtual Account, Direct Debit*). Arsitektur lama berbasis OOP klasik:
*   Menggunakan hierarki kelas: `BasePaymentRequest -> CardPaymentRequest, QrisPaymentRequest`.
*   Menggunakan interface polymorphic: `IPaymentHandler.Handle(IPaymentRequest request)`.
*   Hasil Profiling DotMemory/BenchmarkDotNet: Terjadi alokasi 1.2 GB memori per menit murni akibat *boxing struct payload* ke interface dan instansiasi `class` pendek di Gen 0 GC. GC Pauses meningkat hingga 45ms, melanggar Service Level Agreement (SLA p99 < 15ms).

### Solusi Arsitektural Menggunakan Modern Type System
1.  **Refactoring Polymorphism:** Mengonversi request payload menjadi `readonly record struct` yang dibungkus dalam Discriminated Union pattern.
2.  **Monomorphized Handlers:** Menggunakan Generic Constraints `where TPayload : struct, ITransactionPayload<TPayload>` untuk memicu CLR JIT melakukan devirtualization dan menghilangkan boxing secara menyeluruh.

```csharp
namespace Enterprise.PaymentGateway;

public interface IPaymentPayload<TSelf> where TSelf : struct, IPaymentPayload<TSelf>
{
    static abstract string ChannelCode { get; }
    decimal TransactionAmount { get; }
}

public readonly record struct CardPayload(decimal TransactionAmount, string MaskedPan, string AuthCode) 
    : IPaymentPayload<CardPayload>
{
    public static string ChannelCode => "CREDIT_CARD";
}

public readonly record struct QrisPayload(decimal TransactionAmount, string QrString, string MerchantId) 
    : IPaymentPayload<QrisPayload>
{
    public static string ChannelCode => "QRIS";
}

// Router dengan zero-allocation execution path
public sealed class HighThroughputPaymentRouter
{
    // Generic Monomorphization: JIT mengompilasi varian native terpisah untuk tiap struct
    // Menghilangkan VTable lookup stub dan meniadakan boxing allocation
    public ReadOnlySpan<byte> RouteAndProcess<TPayload>(in TPayload payload) 
        where TPayload : struct, IPaymentPayload<TPayload>
    {
        if (payload.TransactionAmount <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(payload), "Nilai transaksi tidak valid.");
        }

        // ChannelCode diakses secara direct static call tanpa memuat objek ke heap
        Console.WriteLine($"Memproses tipe transaksi: {TPayload.ChannelCode}");
        
        // Pemrosesan internal logic...
        return "SUCCESS"u8;
    }
}
```

### Hasil Metrik
*   **GC Pauses:** Berkurang dari 45ms ke 0.8ms (pengurangan 98.2%).
*   **Allocated Memory:** 0 B pada hot path routing (`BenchmarkDotNet: Allocated = 0 B`).
*   **Throughput (Ops/sec):** Meningkat dari 38.000 RPS menjadi 142.000 RPS pada single-core dedicated VM.

---

## 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **`readonly record struct` vs `class`** | Alokasi heap 0 byte; Kesetaraan nilai (*value semantics*); Cache locality tinggi pada CPU L1/L2. | *Defensive copying* jika struct berukuran besar (> 24-32 bytes) saat dilewatkan tanpa keyword `in`/`ref`; Pembengkakan stack frame. |
| **Static Abstract Members** | Devirtualisasi total; Eksekusi setara direct C-function pointer; Type-safe static contract. | Menuntut versi bahasa modern (C# 11+ / .NET 7+); Kompleksitas kognitif generic parameter tinggi (*CRTP - Curiously Recurring Template Pattern*). |
| **Exhaustive Pattern Matching** | Keamanan logika kompilasi absolut (*compile-time correctness*); Menghilangkan bug cabang tak terduga. | Menambahkan cabang baru pada discriminated union membutuhkan kompilasi ulang seluruh library konsumen (*breaking change*). |
| **Interface `in`/`out` Generic Variance** | Fleksibilitas konversi downstream/upstream data type secara aman. | Terbatas hanya untuk tipe referensi (`class`), sama sekali tidak dapat diterapkan pada `struct` (karena representasi biner struct berbeda di memori). |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Hidden Boxing Melalui Interface Calling pada Value Types
```csharp
// ANTI-PATTERN: Memanggil interface langsung pada struct variabel
public interface IAuditable { void Audit(); }
public struct AuditLog : IAuditable { public void Audit() { } }

public void Process(IAuditable auditable) // Memicu boxing: memindahkan struct ke Managed Heap!
{
    auditable.Audit();
}

// REMEDIATION: Gunakan Generic Constraint
public void ProcessOptimized<T>(T auditable) where T : struct, IAuditable
{
    auditable.Audit(); // Zero allocation. JIT memanggil method Audit() secara direct call
}
```

### Mistake 2: Defensive Copying Akibat Parameter `in` pada Struct Non-Readonly
Jika struct **bukan** `readonly struct`, compiler C# akan membuat salinan tersembunyi (*defensive copy*) setiap kali method atau properti struct diakses melalui parameter `in` untuk menjamin invariansi immutability:
```csharp
// ANTI-PATTERN
public struct HeavyBuffer // Bukan readonly
{
    public int Counter;
    public void MutateOrRead() => Console.WriteLine(Counter);
}

public static void Execute(in HeavyBuffer buffer)
{
    buffer.MutateOrRead(); // COMPILER MEMBUAT DEFENSIVE COPY DI STACK SEBELUM MEMANGGIL METHOD!
}

// REMEDIATION
public readonly struct HeavyBufferOptimized // Tambahkan modifier readonly
{
    public readonly int Counter;
    public void Read() => Console.WriteLine(Counter);
}
```

### Mistake 3: Memory Slicing dan Mutasi State pada Positional Record Class
Menggunakan destrukturisasi dan modifikasi properti record class yang memiliki mutable properties (seperti `List<T>` internal):
```csharp
public record OrderState(string OrderId, List<string> Items);

var state1 = new OrderState("ORD-1", new List<string> { "ItemA" });
var state2 = state1 with { OrderId = "ORD-2" };

// BAHAYA: Shallow Copy! Reference 'Items' mengarah pada objek List yang sama persis di Managed Heap.
state2.Items.Add("ItemB"); 
Console.WriteLine(state1.Items.Count); // Output 2! Integritas data state1 rusak.
```
*Remediasi:* Gunakan koleksi immutabel murni seperti `System.Collections.Immutable.ImmutableList<T>` dalam record.

---

## 11. Best Practices (Production Checklist)

- [ ] **Struct Sizing:** Ukuran `struct` / `record struct` dibatasi maksimal 24–32 byte. Jika melampaui batas ini, gunakan `sealed record class`.
- [ ] **Default Immutability:** Jadikan seluruh struct sebagai `readonly struct` atau `readonly record struct` untuk mencegah *defensive copying*.
- [ ] **Generic Constraint Optimization:** Jika method menerima interface yang berpotensi diimplementasikan oleh `struct`, selalu gunakan bentuk generic `void Execute<T>(T item) where T : IContract`.
- [ ] **Sealing Hierarchy:** Selalu tandai kelas implementasi akhir dengan kata kunci `sealed`. Ini membantu JIT melakukan *Devirtualization* pada pemanggilan `callvirt`.
- [ ] **Exhaustiveness Verification:** Pastikan compiler warning `CS8509` (pola switch tidak lengkap) diatur sebagai **Error** pada file `.csproj`:
  ```xml
  <PropertyGroup>
      <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
      <WarningsAsErrors>CS8509</WarningsAsErrors>
  </PropertyGroup>
  ```
- [ ] **Zero Ref Struct Escape:** Pastikan `ref struct` (seperti `ReadOnlySpan<T>`) tidak pernah digunakan sebagai generic argument, field dalam class, atau diseberangkan ke fungsi `async` (compiler akan memblokir, tetapi hindari mencoba membypass melalui pointer/unsafe).

---

## 12. Hands-on Practice

Buatlah proyek produksi sederhana untuk memverifikasi alokasi memori dan implementasi *modern type-system*.

### Langkah 1: Buat Struktur Project
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
dotnet new console -n ModernTypeSystemLab -f net8.0
cd ModernTypeSystemLab
```

### Langkah 2: Edit `ModernTypeSystemLab.csproj`
Pastikan compiler memberlakukan penanganan null dan error warning yang ketat:
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  </PropertyGroup>
</Project>
```

### Langkah 3: Implementasikan Logika Domain di `Program.cs`
Ganti seluruh isi `Program.cs` dengan kode berikut:

```csharp
using System;
using System.Diagnostics;

namespace ModernTypeSystemLab;

// Closed Type Hierarchy untuk Result Pattern
public abstract record OperationResult<T>
{
    private OperationResult() { }

    public sealed record Success(T Value) : OperationResult<T>;
    public sealed record Failure(string ErrorCode, string Message) : OperationResult<T>;
    public sealed record Pending(DateTime EstimatedCompletion) : OperationResult<T>;
}

// Static Abstract Member Interface
public interface IComputable<TSelf> where TSelf : IComputable<TSelf>
{
    static abstract TSelf Zero { get; }
    static abstract TSelf Add(TSelf left, TSelf right);
}

// High Performance Value Type
public readonly record struct TransactionMetric(long Value) : IComputable<TransactionMetric>
{
    public static TransactionMetric Zero => new(0);

    public static TransactionMetric Add(TransactionMetric left, TransactionMetric right) =>
        new(left.Value + right.Value);
}

public class Program
{
    public static void Main()
    {
        Console.WriteLine("=== 1. Testing Exhaustive Pattern Matching ===");
        OperationResult<decimal> result = new OperationResult<decimal>.Success(250_000.75m);

        string statusMessage = result switch
        {
            OperationResult<decimal>.Success s => $"Operasi Sukses: {s.Value:C}",
            OperationResult<decimal>.Failure f => $"Operasi Gagal! Code: {f.ErrorCode} - {f.Message}",
            OperationResult<decimal>.Pending p => $"Operasi Tertunda hingga: {p.EstimatedCompletion:s}"
        };
        Console.WriteLine(statusMessage);

        Console.WriteLine("\n=== 2. Testing Static Abstract Math Devirtualization ===");
        var m1 = new TransactionMetric(1500);
        var m2 = new TransactionMetric(3500);
        var total = Sum(m1, m2);
        Console.WriteLine($"Total Metrics: {total.Value}");

        Console.WriteLine("\n=== 3. GC Allocation Test on Struct Dispatch ===");
        long beforeAlloc = GC.GetAllocatedBytesForCurrentThread();
        
        for (int i = 0; i < 1_000_000; i++)
        {
            ExecuteOptimized(new TransactionMetric(i));
        }
        
        long afterAlloc = GC.GetAllocatedBytesForCurrentThread();
        Console.WriteLine($"Alokasi Memori Eksekusi Loop 1 Juta: {afterAlloc - beforeAlloc} Bytes (Harus 0 B)");
    }

    // Generic invocation utilizing static abstract methods
    public static T Sum<T>(T a, T b) where T : IComputable<T>
    {
        return T.Add(a, b);
    }

    // Struct generic invocation: Monomorphized, NO BOXING
    public static void ExecuteOptimized<T>(in T input) where T : struct, IComputable<T>
    {
        var dummy = T.Zero;
        // Simulasi kalkulasi
        _ = T.Add(input, dummy);
    }
}
```

### Langkah 4: Uji dan Verifikasi Alokasi
Jalankan di terminal:
```bash
dotnet run -c Release
```
*Output yang diharapkan:*
```text
=== 1. Testing Exhaustive Pattern Matching ===
Operasi Sukses: $250,000.75
=== 2. Testing Static Abstract Math Devirtualization ===
Total Metrics: 5000
=== 3. GC Allocation Test on Struct Dispatch ===
Alokasi Memori Eksekusi Loop 1 Juta: 0 Bytes (Harus 0 B)
```

---

## 13. Exercise

### Level Easy: Exhaustive Sensor Reading Pattern
Ubah tipe domain sensor IoT berikut menjadi Discriminated Union menggunakan `abstract record` hierarki tertutup. Implementasikan method `FormatTelemetry(SensorReading reading)` dengan *switch expression* yang mencakup seluruh sensor tanpa fallback `_`:
*   `Temperature`: nilai suhu bertipe `double` (Celcius).
*   `Humidity`: nilai kelembapan bertipe `double` (Persentase).
*   `Pressure`: nilai tekanan udara bertipe `int` (hPa).
*   *Acceptance Criteria:* Menambahkan tipe sensor baru ke basis data akan memicu kompilasi error bila method `FormatTelemetry` belum diperbarui.

### Level Medium: Custom Numeric Metric Accumulator
Buat generic class `MetricAccumulator<T>` di mana `T` dibatasi oleh `IComputable<T>`.
*   Sediakan method `void Accumulate(T value)` dan properti `T CurrentTotal { get; }`.
*   Gunakan tipe `readonly record struct CustomValue(decimal Val)` sebagai parameter konkret implementor `IComputable<CustomValue>`.
*   *Acceptance Criteria:* Pengujian pemanggilan method `Accumulate` sebanyak 500.000 kali harus membukukan alokasi heap tepat **0 bytes** pada thread pemanggil.

### Level Hard: Zero-Allocation Covariant/Contravariant Event Engine
Rancang sistem bus event in-memory:
*   Interface konsumen event contravariant: `IEventConsumer<in TEvent>`.
*   Interface produser event covariant: `IEventSource<out TEvent>`.
*   Struktur hierarchy event berbasis hierarki tertutup: `DomainEvent -> OrderPlaced, PaymentCollected`.
*   Implementasikan event dispatcher yang dapat mengarahkan `IEventConsumer<DomainEvent>` untuk memproses `OrderPlaced` tanpa alokasi tipe dynamic (`Reflection`) dan bebas alokasi delegate baru pada setiap dispatch.
*   *Acceptance Criteria:* Benchmark membuktikan runtime dispatch latency berada di bawah 10 nanodetik per event.

---

## 14. Challenge

**Skenario Kasus Nyata (Distribusi Order Book Berkinerja Tinggi):**
Anda ditugaskan mendesain ulang modul core matching engine pada sistem bursa efek berlatensi ultra-rendah (*Ultra-low Latency Trading Platform*). Sistem harus mampu memvalidasi dan memproses transisi state order secara deterministik:
*   State machine order terdiri dari: `New`, `PartiallyFilled`, `Filled`, `Cancelled`, `Rejected`.
*   Setiap order request diterima dalam bentuk payload biner mentah melalui network socket (`ReadOnlySpan<byte>`).

**Instruksi Teknis:**
1.  Rancang model state machine ini tanpa mengalokasikan satupun objek di managed heap selama transisi siklus hidup berlangsung (`GC.GetAllocatedBytesForCurrentThread() == 0`).
2.  Gunakan kombinasi `ref struct`, `readonly record struct`, static abstract factories, dan compile-time exhaustive checks.
3.  Implementasikan aturan bisnis:
    *   Hanya state `New` dan `PartiallyFilled` yang dapat menerima transisi `Cancelled`.
    *   State `Filled`, `Cancelled`, dan `Rejected` bersifat terminal (tidak dapat bertransisi lagi). Pelanggaran transisi harus ditangkap oleh compiler atau divalidasi via safe-fail error monad tanpa melempar runtime exception (`throw` dilarang keras di hot-path).
4.  Uji performa: Sistem wajib memproses 10.000.000 transisi dalam waktu kurang dari 50 milidetik pada single core modern CPU.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1.  **Berapa ukuran overhead memori terendah dari sebuah instansiasi `class` kosong pada runtime C# 64-bit sebelum ditambahkan field apapun? Jelaskan komponennya!**
    *   *Jawaban:* 16 bytes. Terdiri dari 8 bytes untuk *Object Header* (*SyncBlockIndex*) dan 8 bytes untuk *MethodTable Pointer* (*EEType*).
2.  **Apa implikasi performa dari melewatkan `readonly record struct` yang berukuran 8 byte menggunakan modifier `in` dibandingkan menyalinnya secara langsung (*pass-by-value*)?**
    *   *Jawaban:* Melewatkan tipe data 8 byte dengan `in` menyebabkan pengiriman referensi memori (pointer 8 byte) yang memicu dereferensi pointer ekstra. Pass-by-value lebih cepat karena nilai 8 byte dimuat langsung ke dalam register CPU (seperti `RAX`/`RDX`) tanpa memory indirection.
3.  **Apakah `record struct` bersifat immutable secara default?**
    *   *Jawaban:* Tidak. `record struct` secara default bersifat mutable. Untuk menjadikannya immutable, pengembang wajib menyematkan modifier `readonly`: `readonly record struct`.
4.  **Mengapa generic variance (`in` / `out`) tidak diizinkan pada tipe data `struct`?**
    *   *Jawaban:* Variansi generic bekerja atas dasar kesamaan representasi referensi pointer pada heap. Struktur memory data (`struct`) memiliki ukuran dan layout bitfield yang berbeda-beda di stack/inline, sehingga CLR tidak dapat menjamin *type safety* tanpa konversi bit mentah atau boxing.
5.  **Instruksi IL apa yang dikeluarkan compiler saat memanggil metode virtual reguler, dan instruksi apa yang digunakan saat memanggil method non-virtual?**
    *   *Jawaban:* Method virtual dipanggil menggunakan `callvirt`, sedangkan method non-virtual dipanggil menggunakan `call`.

### Bagian 2: Intermediate (5 Pertanyaan)
6.  **Bagaimana *Virtual Stub Dispatch* (VSD) menangani pemanggilan interface method ketika call-site berubah menjadi *megamorphic*?**
    *   *Jawaban:* VSD beralih dari stub cache (monomorphic/polymorphic inline-table) ke pemanggilan *Global Interface Dispatch Table* (lookup table runtime penuh), yang memerlukan pencarian hash di runtime dan mematikan optimasi *branch prediction* pada CPU.
7.  **Sebutkan dan jelaskan 2 keuntungan penggunaan *Static Abstract Members in Interfaces* dibanding penggunaan Singleton Pattern klasik!**
    *   *Jawaban:* (1) Devirtualisasi total: Eksekusi metode di-inlining oleh JIT tanpa overhead VTable atau alokasi instans objek heap; (2) Akses kontrak murni pada compile-time via tipe parameter generik tanpa risiko nullability atau sinkronisasi state multithreading runtime.
8.  **Apa yang dilakukan compiler C# di balik layar saat Anda mengeksekusi sintaks `with` pada sebuah `record class`?**
    *   *Jawaban:* Compiler mengeksekusi metode clone khusus (biasanya berlabel `<Clone>$()`) yang menginisialisasi alokasi baru di heap, menyalin seluruh data field secara shallow (*memberwise clone*), kemudian mengaplikasikan mutasi properti yang didefinisikan pada blok `with`.
9.  **Mengapa `ref struct` tidak dapat mengimplementasikan interface standar sebelum C# 13, dan pembatasan apa yang menyebabkannya?**
    *   *Jawaban:* Karena melewatkan `ref struct` ke interface secara historis memerlukan *boxing* ke Managed Heap, yang melanggar aturan fundamental bahwa `ref struct` wajib berada di stack frame untuk mencegah escape analysis issues. (Catatan: C# 13 mulai mengizinkan ref struct mengimplementasikan interface dengan batasan ketat tanpa boxing).
10. **Apa perbedaan mendasar antara representasi kesetaraan `Equals` pada `class` biasa vs `record class`?**
    *   *Jawaban:* `class` biasa mewarisi `System.Object.Equals` yang menggunakan *Reference Equality* (kesetaraan alamat memori heap), sedangkan `record class` meng-override kesetaraan tersebut menjadi *Structural/Value Equality* berbasis evaluasi seluruh field compiler-generated.

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario A:** Tim Anda mendeteksi degradasi performa tinggi pada microservice pemrosesan sinyal. Kode berikut ditemukan:
    ```csharp
    public void ProcessReading(IComparable<int> reading) { ... }
    // Dipanggil berkali-kali:
    ProcessReading(42);
    ```
    *Analisis masalah internal runtime dan berikan solusi satu baris perbaikan kode.*
    *   *Solusi:* Masalahnya adalah nilai integer primitif (`int` 42) dibungkus ke heap (*Boxing*) setiap kali dipanggil karena parameter menerima antarmuka referensi `IComparable<int>`. Perbaikannya adalah mengubah tanda tangan method menjadi generic:
        `public void ProcessReading<T>(T reading) where T : IComparable<int> { ... }`
        Ini mengarahkan JIT menghasilkan kode biner monomorphic tanpa boxing.

12. **Skenario B:** Arsitek perangkat lunak mendesain Discriminated Union menggunakan `record class` hierarki:
    ```csharp
    public abstract record PaymentAuth;
    public record Success(Guid TraceId) : PaymentAuth;
    public record Failed(string Reason) : PaymentAuth;
    ```
    Library ini dipublikasikan sebagai NuGet Package internal. Di kemudian hari, tim menambahkan:
    `public record Timeout(int Milliseconds) : PaymentAuth;`
    Aplikasi klien yang mengonsumsi package ini dan memproses `PaymentAuth` menggunakan `switch` mendadak melempar `SwitchExpressionException` di produksi. Mengapa ini terjadi dan bagaimana strategi mitigasi arsitekturalnya?
    *   *Solusi:* Ini terjadi karena aplikasi klien tidak mengaktifkan peringatan compiler CS8509 sebagai error (`<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`), sehingga saat compile-time mereka tidak menyadari cabang baru `Timeout` belum ditangani. Mitigasinya: (1) Sediakan cabang `_` (discard/fallback) dengan penanganan yang aman (misal melempar custom domain exception yang terkendali); (2) Pasang policy CI/CD wajib compile dengan treat warnings as errors pada proyek konsumen; (3) Gunakan semantic versioning secara disiplin (menambah turunan tipe DU yang diexpose publik adalah *Major Breaking Change*).

13. **Skenario C:** Anda memiliki struct berikut untuk high-performance telemetry:
    ```csharp
    public struct MetricItem
    {
        public long Timestamp;
        public double Value;
        public MetricItem(long ts, double val) => (Timestamp, Value) = (ts, val);
    }
    ```
    Saat dilewatkan ke method:
    `public static void RecordMetric(in MetricItem metric) => metric.Value.ToString();`
    Hasil profiling menunjukkan CPU instruction count melompat 20% lebih tinggi dari yang diperkirakan. Jelaskan akar penyebab masalahnya di level instruksi emisi compiler dan bagaimana solusinya!
    *   *Solusi:* Karena `MetricItem` dideklarasikan sebagai `struct` biasa (bukan `readonly struct`), saat compiler mengeksekusi parameter yang diberi flag `in MetricItem metric`, compiler tidak dapat menjamin bahwa akses properti atau pemanggilan method internal pada `metric` tidak akan memodifikasi state internal struct tersebut. Akibatnya, Roslyn compiler mengemisikan defensive copy (menyalin struct ke variabel lokal stack baru) sebelum pembacaan properti dilakukan. Solusinya: Tambahkan modifier `readonly` secara eksplisit pada definisi tipe:
        `public readonly struct MetricItem { ... }`
        Defensive copy akan dieliminasi 100% oleh JIT compiler.

---

## 16. Summary

1.  **Evolusi Tipe Data:** Pemrograman C# kontemporer bergerak dari ketergantungan pewarisan objek dinamis ke arah *zero-allocation value types*, pemodelan domain fungsional berbasis *Discriminated Unions*, dan arsitektur *Static Abstract*.
2.  **Efisiensi Memori Tingkat Rendah:** Pemahaman menyeluruh terhadap anatomi instansiasi heap (`Object Header` dan `MethodTable Pointer`) versus stack layout memampukan perancangan sistem enterprise yang meminimalisir intervensi Garbage Collector.
3.  **Devirtualisasi dan Monomorphization:** Penggunaan antarmuka generic dengan batasan nilai (`where T : struct, IInterface`) dan static abstract members mengizinkan CLR JIT mengeliminasi VTable lookup, mengeksekusi inlining method, dan meniadakan penalti boxing.
4.  **Keamanan Statis Tingkat Tinggi:** Kombinasi *Record Hierarchies*, *Pattern Matching Expressions*, dan penegakan strict compiler flags menjamin kode enterprise tidak hanya berlatensi rendah, tetapi juga terbebas dari kesalahan runtime struktural seperti *Missing State Handling* dan `NullReferenceException`.