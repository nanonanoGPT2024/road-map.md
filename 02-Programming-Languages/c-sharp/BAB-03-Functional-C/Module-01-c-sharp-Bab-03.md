# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 02-Programming-Languages
*   **Bahasa Pemrograman:** C# (.NET 8/9 LTS)
*   **Bab:** 03 — Paradigma Pemrograman Lanjutan
*   **Modul:** 01 — Functional C# (Pemrograman Fungsional Modern)
*   **Tingkat Kesulitan:** Intermediate ke Advanced
*   **Prasyarat:** Pemahaman mendalam tentang OOP C#, Generics, Delegates (`Func`, `Action`, `Predicate`), LINQ dasar, serta manajemen memori managed (.NET CLR).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Mendekonstruksi** paradigma pemrograman fungsional (FP) dalam ekosistem C# modern dan membedakannya dari paradigma Object-Oriented Programming (OOP) imperatif murni.
2.  **Mengimplementasikan** struktur data *immutable* sejati memanfaatkan `record`, `init-only setters`, dan `readonly record struct` untuk menjamin keamanan mutasi state (*thread-safety by design*).
3.  **Merancang** alur kontrol data deklaratif berbasis ekspresi memanfaatkan *Pattern Matching* tingkat lanjut (*Property, Positional, Relational, List, and Type Patterns*).
4.  **Mengarsitekturi** penanganan galat (*error handling*) tanpa melempar *runtime exceptions* melalui pola *Railway-Oriented Programming* (ROP) dengan monad `Result<TValue, TError>` dan `Option<T>`.
5.  **Menganalisis** alokasi memori internal CLR akibat *closures*, *delegates*, dan evaluasi *lazy* LINQ, serta menerapkan teknik optimasi seperti `static lambda` dan *struct-based enumerators*.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam OOP imperatif klasik, program dipandang sebagai sekumpulan objek yang saling berkomunikasi dan mengubah *state* internal mereka seiring berjalannya waktu. Mental model ini kerap menimbulkan kompleksitas kognitif: Anda harus melacak *kapan*, *di mana*, dan *oleh siapa* suatu variabel dimutasi. Masalah konkurensi, *race conditions*, dan *null reference exceptions* hampir selalu berakar dari state yang dapat dimutasi secara bebas (*shared mutable state*).

```
Paradigma Imperatif (State Mutator):
[State A] ---> (Instruksi 1: Ubah A) ---> [State A'] ---> (Instruksi 2: Mutasi lagi) ---> [State A'']

Paradigma Fungsional (Data Transformation Pipeline):
[Input X] ---> | Pure Function f(x) | ---> [Data Y] ---> | Pure Function g(y) | ---> [Output Z]
                     (Tanpa Efek Samping)                     (Immutable Transformation)
```

Pemrograman fungsional di C# menggeser cara pandang ini:
*   **Data dan Perilaku Dipisahkan:** Data direpresentasikan oleh tipe data statis dan *immutable* (*Data Transfer Objects* / DTOs / Records). Perilaku didefinisikan melalui fungsi-fungsi murni (*pure functions*).
*   **Ekspresi di Atas Statement:** Dalam FP, segalanya menghasilkan nilai. Kode ditulis dalam bentuk ekspresi yang dapat dievaluasi, bukan barisan perintah (*statements*) yang memutasi lingkungan sekitar.
*   **Fungsi Adalah Pipa (Pipelining):** Komputasi dipandang sebagai pipa transformasi data. Nilai masuk dari satu ujung, ditransformasi tanpa merusak nilai aslinya, dan keluar sebagai tipe data baru di ujung yang lain.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Railway-Oriented Programming (ROP)

Salah satu pilar arsitektur fungsional dalam menangani *business logic* kompleks adalah ROP. Setiap langkah operasi komputasi memiliki dua cabang: **Jalur Sukses** (*Green Track*) dan **Jalur Gagal** (*Red Track*). Sekali sebuah fungsi mengalami kegagalan, alur eksekusi langsung beralih ke jalur gagal, melewati seluruh fungsi logika berikutnya tanpa perlu melempar *exception*.

```
[Request Input]
      |
      v
+-------------+      Failure      +------------------------+
|  Validate   | ----------------> | Error: Invalid Payload |
+-------------+                   +------------------------+
      | Success                               |
      v                                       |
+-------------+      Failure                  |
| Authorize   | ----------------------------> | Error: Unauthorized
+-------------+                               +------------------------+
      | Success                               |
      v                                       v
+-------------+      Failure                  |
| Execute Tx  | ----------------------------> | Error: Insufficient Fund
+-------------+                               +------------------------+
      | Success                               |
      v                                       v
[Success Output]                      [Bypass ke Error Response]
```

### Pattern Matching State Machine

Dalam arsitektur functional C#, evaluasi tipe data kompleks ditangani melalui ekspresi pencocokan pola:

```
[Incoming Domain Event]
         |
         v
    <switch (...)>
    ├── Case: OrderCreated(OrderId, > 1000)   ───> [Prioritize Dispatch]
    ├── Case: OrderCancelled(OrderId, Reason) ───> [Release Inventory]
    ├── Case: OrderRefunded(var id, <= 0)     ───> [Throw / Reject Domain Error]
    └── Case: _                               ───> [Log Unhandled State]
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Dekonstruksi Kompiler: Record dan Immutability

Ketika Anda mendeklarasikan `public record Person(string Name, int Age);`, Roslyn compiler tidak menciptakan tipe primitif baru, melainkan me-lower sintaks tersebut menjadi *sealed class* standar di level Intermediate Language (IL) dengan implementasi bawaan:

*   Membuat properti `public string Name { get; init; }` dan `public int Age { get; init; }`. Modifikator `init` memastikan mutasi hanya valid di dalam konstruktor atau *object initializer*.
*   Secara otomatis mengimplementasikan antarmuka `IEquatable<Person>`.
*   Menghasilkan *method* `Equals(object? obj)`, `GetHashCode()`, operator `==`, dan operator `!=` berbasis nilai (*value-based equality*), bukan referensi memori (*reference equality*).
*   Menghasilkan method kloning tersembunyi bernama `<Clone>$()`, yang digunakan oleh kata kunci `with` untuk melakukan *non-destructive mutation* (menyalin instans referensi secara dangkal / *shallow copy* dengan modifikasi terpilih).
*   Menghasilkan method `Deconstruct(out string Name, out int Age)`.

### 2. Anatomi Alokasi Closure: `Func<T>` vs Local Functions & Static Lambdas

Jika lambda function menangkap (*captures*) variabel lokal dari lingkup luarnya, kompiler Roslyn harus mengalokasikan kelas perantara (*display class*) di managed heap untuk mempertahankan *state* variabel tersebut:

```csharp
// Mengakibatkan Alokasi Heap Tersembunyi:
int factor = 10;
Func<int, int> multiplier = x => x * factor; 
// IL Compiler membuat class baru: <>c__DisplayClass0_0 { public int factor; }
// multiplier menjadi method instans dari class display tersebut.

// Optimasi Fungsional Tanpa Alokasi (C# 9+):
static int Multiply(int x, int factor) => x * factor;
Func<int, int, int> pureMultiplier = static (x, f) => x * f;
```
Menambahkan kata kunci `static` pada ekspresi lambda mencegah penangkapan *state* eksternal secara tidak sengaja, menjamin alokasi closure adalah nol (*zero-heap allocation* untuk context state).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Pure Functions & Referential Transparency

Sebuah fungsi dikatakan **murni** (*pure*) jika memenuhi dua kriteria absolut:
1.  **Deterministik:** Untuk argumen masukan yang sama, fungsi selalu menghasilkan nilai kembalian yang persis sama. Fungsi tidak bergantung pada jam sistem (`DateTime.Now`), bilangan acak (`Random`), pembacaan database, atau status jaringan.
2.  **Nol Efek Samping (*Zero Side-Effects*):** Fungsi tidak memodifikasi variabel di luar cakupannya, tidak memutasi argumen yang dikirim melalui referensi, tidak menulis ke I/O (konsol, disk, jaringan), dan tidak mengubah *state* global.

Implikasi utama fungsi murni adalah **Transparansi Referensial (*Referential Transparency*)**. Sebuah ekspresi fungsi dapat digantikan secara langsung oleh nilai hasilnya tanpa mengubah perilaku sistem secara keseluruhan. Hal ini memungkinkan teknik optimasi tingkat lanjut seperti *memoization*, *compiler subexpression elimination*, dan paralelisasi bebas *race-condition*.

### 2. Higher-Order Functions (HOF) & Currying

*Higher-Order Function* adalah fungsi yang menerima fungsi lain sebagai parameter, mengembalikan fungsi, atau keduanya. Di C#, representasi fundamental HOF adalah delegate generik `Func<...>` dan `Action<...>`.

Konsep matematis terkait adalah **Currying** (mengubah fungsi dengan banyak argumen $f(a, b)$ menjadi rantai fungsi tunggal $f(a)(b)$) dan **Partial Application** (mengikat sejumlah argumen ke sebuah fungsi untuk menghasilkan fungsi baru dengan ariti yang lebih kecil).

### 3. Tipe Aljabar Data (Algebraic Data Types - ADT)

Dalam functional programming murni, terdapat dua kategori utama ADT:
1.  **Product Types:** Tipe data yang nilainya merupakan kombinasi dari tipe-tipe penyusunnya ($A \times B$). Dalam C#, ini diwujudkan oleh `Tuple`, `struct`, `class`, dan `record`.
2.  **Sum Types (Discriminated Unions):** Tipe data yang nilainya hanya bisa berupa *salah satu* dari beberapa variasi yang ditentukan ($A + B$). C# belum memiliki sintaks native *discriminated unions* murni secara penuh, tetapi pola ini diimplementasikan secara elegan menggunakan `abstract record` dengan varian turunan tertutup (`sealed record`), yang kemudian dievaluasi menggunakan *Pattern Matching exhaustiveness checking*.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah fondasi fungsional di C#: Tipe Data Sum/ADT, Pola Monadik `Result<T, E>`, dan *Exhaustive Pattern Matching*.

```csharp
using System;

namespace FunctionalCSharp.Fundamentals;

// 1. Immutable Value Objects via Records
public readonly record struct Money(decimal Amount, string Currency)
{
    public static Money Zero(string currency) => new(0m, currency);
}

// 2. Functional Error Monad: Result<TValue, TError>
public readonly struct Result<TValue, TError>
{
    public bool IsSuccess { get; }
    public bool IsFailure => !IsSuccess;

    private readonly TValue? _value;
    private readonly TError? _error;

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

    // Monadic Bind (FlatMap)
    public Result<TNext, TError> Bind<TNext>(Func<TValue, Result<TNext, TError>> bindFunc)
    {
        return IsSuccess ? bindFunc(_value!) : Result<TNext, TError>.Failure(_error!);
    }

    // Functor Map
    public Result<TNext, TError> Map<TNext>(Func<TValue, TNext> mapFunc)
    {
        return IsSuccess ? Result<TNext, TError>.Success(mapFunc(_value!)) : Result<TNext, TError>.Failure(_error!);
    }

    // Pattern Match Fold
    public TResult Match<TResult>(
        Func<TValue, TResult> onSuccess,
        Func<TError, TResult> onFailure)
    {
        return IsSuccess ? onSuccess(_value!) : onFailure(_error!);
    }
}

// 3. Domain Model via Discriminated Unions Pattern
public abstract record AccountStatus
{
    private AccountStatus() { } // Private constructor restricts inheritance to nested types only

    public sealed record Active(DateTime ActivatedAt) : AccountStatus;
    public sealed record Suspended(string Reason, DateTime SuspendedUntil) : AccountStatus;
    public sealed record Closed(string Reason) : AccountStatus;
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah telaah teknis mendalam terhadap implementasi di Seksi 07:

1.  `public readonly record struct Money(decimal Amount, string Currency)`:
    *   Mendeklarasikan *immutable value-type* yang dialokasikan di stack (kecuali jika ter-box).
    *   Mengimplementasikan perbandingan nilai secara default tanpa overhead GC (*Garbage Collection*).
    *   Secara otomatis mengamankan representasi nilai mata uang dari perubahan status mutatif tak terduga.
2.  `public readonly struct Result<TValue, TError>`:
    *   Struktur monadik untuk meniadakan penggunaan eksepsi pada alur kendali normal.
    *   Menggunakan `readonly struct` untuk mengeliminasi alokasi objek pada heap saat membungkus nilai balik operasi domain.
3.  `public Result<TNext, TError> Bind<TNext>(...)`:
    *   Merupakan operasi monadik fundamental ($M\langle A \rangle \to (A \to M\langle B \rangle) \to M\langle B \rangle$).
    *   Jika operasi saat ini sukses, fungsi pemetaan akan dieksekusi; jika gagal, kegagalan (*error*) diteruskan secara langsung menuruni pipa pemrosesan tanpa mengeksekusi `bindFunc`.
4.  `private AccountStatus() { }`:
    *   Konstruktor internal privat membatasi pembuatan sub-tipe baru di luar file/tipe ini.
    *   Trik ini mengemulasikan *Discriminated Unions* F#/Rust secara presisi di C#, memaksa kompiler Roslyn memberi peringatan jika ada cabang evaluasi *switch* yang tidak ditangani (*exhaustiveness checking*).
5.  `public sealed record Active(...) : AccountStatus;`:
    *   Tiap varian didefinisikan sebagai sub-record sealed yang spesifik. Setiap varian membawa muatan data (*payload*) masing-masing tanpa ada data bersama yang tumpang tindih secara sembarangan.

---

# SEKSI 09 — STUDI KASUS NYATA

### Pipeline Pemrosesan Transaksi Pembayaran E-Commerce High-Throughput

**Latar Belakang Arsitektural:**
Sebuah platform fintech memproses transaksi pembayaran kartu kredit skala tinggi. Pendekatan imperatif lama mengandalkan `try-catch` blok berantai dan mutasi entity database secara langsung di berbagai service. Masalah utama yang timbul:
1.  **Bottleneck Kinerja:** Melempar eksepsi (`throw new InsufficientFundsException()`) sangat mahal di .NET runtime karena harus mengumpulkan jejak stack (*stack trace allocation*), memperlambat throughput hingga 80x lipat saat beban sistem tinggi.
2.  **Kerentanan State:** Kegagalan di tengah-tengah alur transaksi kerap meninggalkan entity dalam kondisi *partial mutation*.
3.  **Sulit Dites:** Side-effects (I/O, database, API gateway eksternal) tercampur aduk dengan kalkulasi biaya dan validasi aturan bisnis.

**Solusi:**
Merancang ulang sistem menjadi *functional-first architecture*:
*   Seluruh entitas domain dimodelkan sebagai *immutable records*.
*   Validasi dan kalkulasi fee dijadikan fungsi-fungsi murni (*pure functions*).
*   Alur kerja pembayaran dirangkai menggunakan Railway-Oriented Programming berbasis `Result<TValue, DomainError>`.
*   Eksekusi side-effects (persistensi database, kontak payment gateway) diisolasi di batas akhir sistem (*pure functional core, imperative shell*).

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi lengkap *production-ready* dari sistem pemrosesan transaksi fungsional:

```csharp
using System;

namespace FunctionalCSharp.ProductionCase;

// Domain Errors as Sum Types
public abstract record DomainError(string Message)
{
    public sealed record ValidationError(string PropertyName, string Detail) 
        : DomainError($"Validation failed on '{PropertyName}': {Detail}");
    
    public sealed record InsufficientFunds(decimal AttemptedAmount, decimal CurrentBalance) 
        : DomainError($"Insufficient funds. Attempted: {AttemptedAmount}, Available: {CurrentBalance}");
    
    public sealed record AccountFrozen(string Reason) 
        : DomainError($"Account is frozen: {Reason}");
    
    public sealed record NetworkGatewayTimeout(string Gateway) 
        : DomainError($"Gateway timeout connecting to {Gateway}");
}

// Immutable Domain States
public readonly record struct CustomerAccount(Guid Id, decimal Balance, bool IsFrozen);
public readonly record struct PaymentRequest(Guid TransactionId, Guid AccountId, decimal Amount, string Currency);
public readonly record struct ProcessedPayment(Guid TransactionId, decimal DebitedAmount, decimal RemainingBalance, DateTime Timestamp);

// Functional Processing Pipeline
public static class PaymentEngine
{
    // Step 1: Pure Validation
    public static Result<PaymentRequest, DomainError> ValidateRequest(PaymentRequest request)
    {
        return request switch
        {
            { Amount: <= 0 } => Result<PaymentRequest, DomainError>.Failure(
                new DomainError.ValidationError(nameof(request.Amount), "Amount must be strictly positive.")),
            { Currency: not "IDR" } => Result<PaymentRequest, DomainError>.Failure(
                new DomainError.ValidationError(nameof(request.Currency), "Only 'IDR' currency is supported.")),
            _ => Result<PaymentRequest, DomainError>.Success(request)
        };
    }

    // Step 2: Pure Business Rule Check
    public static Result<(PaymentRequest Request, CustomerAccount Account), DomainError> VerifyAccountState(
        PaymentRequest request, 
        CustomerAccount account)
    {
        return account switch
        {
            { IsFrozen: true } => Result<(PaymentRequest, CustomerAccount), DomainError>.Failure(
                new DomainError.AccountFrozen("Suspicious fraudulent activity detected.")),
            { Balance: var balance } when balance < request.Amount => Result<(PaymentRequest, CustomerAccount), DomainError>.Failure(
                new DomainError.InsufficientFunds(request.Amount, balance)),
            _ => Result<(PaymentRequest, CustomerAccount), DomainError>.Success((request, account))
        };
    }

    // Step 3: Pure State Transformation
    public static Result<ProcessedPayment, DomainError> ApplyDebit(PaymentRequest request, CustomerAccount account)
    {
        // Zero mutations to input parameters. Produces fresh state.
        decimal updatedBalance = account.Balance - request.Amount;
        
        var receipt = new ProcessedPayment(
            TransactionId: request.TransactionId,
            DebitedAmount: request.Amount,
            RemainingBalance: updatedBalance,
            Timestamp: DateTime.UtcNow
        );

        return Result<ProcessedPayment, DomainError>.Success(receipt);
    }

    // Orchestrator: Pure Functional Pipeline Chain
    public static Result<ProcessedPayment, DomainError> ExecuteTransaction(
        PaymentRequest request, 
        CustomerAccount account)
    {
        return ValidateRequest(request)
            .Bind(validReq => VerifyAccountState(validReq, account))
            .Bind(context => ApplyDebit(context.Request, context.Account));
    }
}

// Interactive Test Program
public class Program
{
    public static void Main()
    {
        var account = new CustomerAccount(Guid.NewGuid(), Balance: 500_000m, IsFrozen: false);
        
        // Scenario A: Successful Flow
        var validRequest = new PaymentRequest(Guid.NewGuid(), account.Id, Amount: 150_000m, Currency: "IDR");
        var resultSuccess = PaymentEngine.ExecuteTransaction(validRequest, account);
        PrintResult(resultSuccess);

        // Scenario B: Validation Failure (Bypasses Step 2 & 3)
        var invalidRequest = new PaymentRequest(Guid.NewGuid(), account.Id, Amount: -10m, Currency: "IDR");
        var resultInvalid = PaymentEngine.ExecuteTransaction(invalidRequest, account);
        PrintResult(resultInvalid);

        // Scenario C: Business Failure (Insufficient balance)
        var expensiveRequest = new PaymentRequest(Guid.NewGuid(), account.Id, Amount: 1_000_000m, Currency: "IDR");
        var resultOverdraw = PaymentEngine.ExecuteTransaction(expensiveRequest, account);
        PrintResult(resultOverdraw);
    }

    private static void PrintResult(Result<ProcessedPayment, DomainError> result)
    {
        string output = result.Match(
            onSuccess: payment => $"[SUCCESS] Transaction {payment.TransactionId} processed. Remaining: {payment.RemainingBalance:C}",
            onFailure: error => error switch
            {
                DomainError.ValidationError valErr => $"[VALIDATION REJECTED] {valErr.PropertyName}: {valErr.Detail}",
                DomainError.InsufficientFunds insFunds => $"[REJECTED] {insFunds.Message}",
                DomainError.AccountFrozen frozen => $"[SECURITY LOCK] {frozen.Reason}",
                _ => $"[UNKNOWN ERROR] {error.Message}"
            }
        );

        Console.WriteLine(output);
    }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Parameter / Dimensi | Imperative OOP (C# Tradisional) | Functional C# (Pola ROP & Immutability) | Pure Functional (F# / Haskell Native) |
| :--- | :--- | :--- | :--- |
| **Pengelolaan State** | Shared mutable state melalui fields dan mutator setter. Rentan race-condition. | Immutable state via `records`, modifikasi data via non-destructive cloning (`with`). | State selalu immutable secara bawaan (*by default*). Mutasi dilarang keras. |
| **Penanganan Error** | Menggunakan `throw/try/catch`. Mahal secara CPU/Memory jika terjadi exception. | Menggunakan Monad `Result<T, E>`. Alur kendali eksplisit, alokasi memori minimal. | Monadic handling (`Result`, `Either`) terintegrasi native dalam sintaks bahasa. |
| **Keterbacaan Alur** | Alur lompat-lompat akibat eksepsi dan interaksi method implisit antar class. | Rangkaian operasi deklaratif linier yang dapat dibaca dari atas ke bawah. | Alur ekspresi murni dengan operator composability tingkat tinggi (`>>`, `\|>`). |
| **GC Pressure** | Rendah saat mutasi inplace, tapi tinggi jika banyak objek temporer dialokasikan. | Dapat menimbulkan GC pressure jika `record class` dikloning intensif dalam loop besar. | Runtime dioptimasi secara spesifik untuk alokasi objek fungsional dan TCO. |
| **Learning Curve** | Rendah bagi sebagian besar engineer berlatar belakang C/C++/Java klasik. | Menengah. Memerlukan disiplin pola pikir matematika diskret dan monadik. | Tinggi. Konsep abstraksi matematika tingkat lanjut (Category Theory, Monads, Monoids). |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Ilusi Shallow Immutability pada Record
Kata kunci `record` atau `readonly record struct` hanya menjamin **Shallow Immutability**. Jika sebuah record memiliki referensi ke koleksi mutable (seperti `List<T>`), isi koleksi tersebut masih bisa diubah dari luar:

```csharp
public record Order(Guid Id, List<string> Items);

var order = new Order(Guid.NewGuid(), new List<string> { "Item A" });
order.Items.Add("Item B"); // Berhasil diubah! Purity domain jebol.

// Solusi: Wajib gunakan Immutable Collections
using System.Collections.Immutable;
public record SafeOrder(Guid Id, ImmutableList<string> Items);
```

### 2. Ketiadaan Tail Call Optimization (TCO) Terjamin di .NET CLR
Dalam bahasa fungsional murni, algoritma rekursif dioptimasi secara otomatis melalui Tail Call Elimination agar stack tidak bertambah. C# compiler **tidak menjamin TCO**, dan runtime JIT x64 hanya melakukannya dalam kondisi heuristik yang sangat ketat. Menulis fungsi rekursif fungsional tanpa batas kedalaman di C# berisiko menyebabkan `StackOverflowException`. Solusinya adalah mentransformasi fungsi rekursif menjadi loop imperatif terisolasi di dalam body fungsi lokal (*trampolining* atau *accumulator loop*).

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan Exception untuk Flow Control Normal
*   **Kesalahan:** Melempar eksepsi saat validasi form salah atau saldo pengguna tidak cukup.
*   **Dampak:** .NET runtime harus menghentikan thread execution untuk mengisi tabel `StackTrace`, yang mendegradasi performa hingga puluhan ribu CPU cycles per eksepsi.
*   **Perbaikan:** Gunakan return type `Result<T, Error>`. Simpan penggunaan `throw` hanya untuk kegagalan fatal yang tidak terduga (*crash recovery*), seperti ketiadaan koneksi database atau kerusakan hardware.

### 2. Terjadinya Hidden Closure Allocations pada LINQ
*   **Kesalahan:** Menggunakan lambda di dalam loop yang menangkap variabel iterasi.

```csharp
// BAD: Mengalokasikan DisplayClass baru pada setiap iterasi!
for (int i = 0; i < 1000; i++)
{
    var threshold = i;
    var filtered = list.Where(x => x > threshold); 
}

// GOOD: Hindari closure atau gunakan static lambda
for (int i = 0; i < 1000; i++)
{
    var filtered = FilterByThreshold(list, i);
}
static IEnumerable<int> FilterByThreshold(IEnumerable<int> src, int th) 
    => src.Where(x => x > th);
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Pure Functional Core, Imperative Shell (Hexagonal Boundaries):** Letakkan seluruh kalkulasi, transformasi data, dan *business logic* di dalam fungsi-fungsi murni bebas dependensi eksternal (*Core*). Jalankan operasi I/O, database access, dan mutasi infrastruktur di lapisan paling luar (*Shell*).
2.  **Deklarasikan Modifikator `static` pada Local Functions dan Lambdas:** Biasakan memberi label `static` pada lambda expressions jika tidak bermaksud menangkap variabel lingkup luar (`static (a, b) => a + b`). Ini menginstruksikan kompiler untuk mencegah alokasi memori secara tegas.
3.  **Gunakan `readonly record struct` untuk Nilai Ringan:** Hindari pemborosan *managed heap* untuk entitas DTO/Value Object sementara yang memiliki siklus hidup pendek. Manfaatkan alokasi stack.
4.  **Tegakkan Keberadaan Exhaustive Pattern Matching:** Saat memetakan ADT/Sum Types dengan switch expression, jangan gunakan fallback `_ => ...` jika seluruh tipe anak (*sub-records*) seharusnya ditangani secara definitif. Biarkan kompiler memunculkan warning jika ada tipe varian baru yang belum ditangani.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Benchmarking: Exception vs Result Monad Allocation

Berikut perbandingan alokasi resource antara paradigma Exception-Driven vs Functional Result Monad:

```
| Method                    | Mean        | Error     | StdDev    | Allocated |
|-------------------------- |------------:|----------:|----------:|----------:|
| ImperativeWithExceptions  | 4,215.30 ns | 45.120 ns | 42.205 ns |    1848 B |
| FunctionalResultStruct    |     2.15 ns |  0.015 ns |  0.014 ns |       0 B |
```

### Teknik Eliminasi Overhead:
1.  **Struktur Nilai Zero-Copy:** Tipe `Result<TValue, TError>` harus berupa `readonly struct`. Menghasilkan status sukses atau gagal tidak boleh memicu alokasi heap (`0 B`).
2.  **Inlining Directive:** Berikan atribut `[MethodImpl(MethodImplOptions.AggressiveInlining)]` pada method-method monadik kecil seperti `Bind`, `Map`, dan `Match`. Ini memungkinkan compiler JIT menghapus overhead pemanggilan method (*call-site overhead*) dan menggabungkan rantai fungsi menjadi satu blok instruksi assembly yang teroptimasi secara native.

---

# SEKSI 16 — KEAMANAN & HARDENING

1.  **Pencegahan TOCTOU (Time-of-Check to Time-of-Use) Melalui Immutability:** Dalam arsitektur multithreaded yang menangani state mutable, pengecekan hak akses bisa berubah statusnya sebelum eksekusi terjadi. Dengan menerapkan domain data yang *immutable*, data yang divalidasi identik secara matematis dengan data yang dieksekusi, menutup celah eksploitasi konkurensi.
2.  **Type-Driven Security (Primitive Obsession Mitigation):**
    Jangan merepresentasikan entitas sensitif menggunakan primitif mentah (`string`, `int`):

```csharp
// RENTAN: Parameter dapat tertukar tanpa peringatan kompiler!
public void Transfer(string senderIban, string receiverIban, decimal amount) { ... }

// SECURE: Domain-Driven Strongly Typed Wrappers
public readonly record struct Iban(string Value);
public readonly record struct ValidatedAmount(decimal Value);

public void Transfer(Iban sender, Iban receiver, ValidatedAmount amount) { ... }
```
Konstruksi tipe `ValidatedAmount` hanya dapat diinisialisasi melalui static factory fungsional yang memvalidasi bahwa nilai uang tidak boleh bernilai negatif dan lolos sensor anti-fraud.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Masalah umum dalam pipeline fungsional adalah kesulitan menyisipkan *logging* tanpa merusak aliran rantai ekspresi (*breaking the chain*). Pendekatan fungsional murni menyelesaikannya dengan memperkenalkan operasi ekstensi **`Tap`** (disebut juga `Do` atau `Tee`):

```csharp
public static class FunctionalObservabilityExtensions
{
    // Tap mengeksekusi aksi sampingan (logging/metrik) tanpa mengubah payload data monad
    public static Result<TValue, TError> Tap<TValue, TError>(
        this Result<TValue, TError> result,
        Action<TValue> onSuccess,
        Action<TError> onFailure)
    {
        if (result.IsSuccess)
        {
            // Logging dieksekusi terisolasi
            onSuccess(result.Value!);
        }
        else
        {
            onFailure(result.Error!);
        }
        
        return result; // Mengembalikan monad asli untuk melanjutkan pipeline
    }
}

// Penggunaan dalam Pipeline Produksi:
var finalResult = PaymentEngine.ValidateRequest(request)
    .Tap(
        onSuccess: req => logger.LogInformation("Request {Id} valid.", req.TransactionId),
        onFailure: err => logger.LogWarning("Validation rejected: {Msg}", err.Message)
    )
    .Bind(req => PaymentEngine.VerifyAccountState(req, account))
    .Tap(
        onSuccess: _ => logger.LogInformation("Account verification passed."),
        onFailure: err => logger.LogError("Processing stopped: {Msg}", err.Message)
    );
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

```csharp
// 1. Immutable Record
public record User(Guid Id, string Name);

// 2. Non-Destructive Mutation
User updated = user with { Name = "New Name" };

// 3. Advanced Switch Pattern Matching
string categorization = account switch
{
    { Balance: < 0 } => "Overdrawn",
    { IsFrozen: true } => "Locked",
    { Balance: >= 1_000_000, Id: var id } => $"VIP Client: {id}",
    _ => "Standard"
};

// 4. Positional Pattern Matching with Deconstruction
var point = (X: 10, Y: 0);
string location = point switch
{
    (0, 0) => "Origin",
    (var x, 0) => $"X-Axis at {x}",
    (0, var y) => $"Y-Axis at {y}",
    var (x, y) => $"Point at {x}, {y}"
};

// 5. Zero-Allocation Static Lambda
Func<int, int, int> add = static (x, y) => x + y;

// 6. Railway Step
Result<Output, Error> step = inputResult.Bind(pureProcessFunc);
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1.  **Apa perbedaan mendasar antara memodifikasi properti pada `class` biasa vs memodifikasi properti pada `record` menggunakan operator `with`?**
    *   *Jawaban:* `class` biasa memutasi data pada blok memori referensi yang sama secara *in-place*. Operator `with` pada `record` melakukan *non-destructive mutation*, yaitu menduplikasi instans objek asli ke memori baru (*shallow copy*) dengan properti terpilih yang telah disesuaikan, membiarkan objek awal tetap utuh.
2.  **Mengapa fungsi murni (*pure function*) harus bebas dari dependensi seperti `DateTime.UtcNow`?**
    *   *Jawaban:* Karena membuat fungsi menjadi non-deterministik. Setiap pemanggilan fungsi menghasilkan nilai keluaran yang berbeda meskipun nilai parameter masukannya sama, melanggar prinsip *Referential Transparency*.
3.  **Apakah sintaks `readonly struct` dialokasikan di heap atau di stack? Jelaskan implikasinya pada Garbage Collector.**
    *   *Jawaban:* Dialokasikan di *stack* (selama tidak dibungkus dalam boxing ke `object` atau antarmuka). Implikasinya, tipe ini tidak menghasilkan *GC pressure*, karena memorinya langsung dibersihkan begitu eksekusi keluar dari stack frame fungsi terkait.
4.  **Apa tujuan utama penambahan kata kunci `static` pada ekspresi lambda di C# 9+?**
    *   *Jawaban:* Mencegah lambda tersebut menangkap (*capturing*) variabel lokal atau instance context (`this`) secara tidak sengaja, menghindari alokasi memori tersembunyi berupa *display class* di managed heap.
5.  **Bagaimana cara kerja modifier `init` pada properti C#?**
    *   *Jawaban:* Membatasi pemberian nilai pada properti tersebut hanya pada saat fase inisialisasi objek (di dalam konstruktor atau *object initializer*). Setelah objek terbentuk, properti tersebut menjadi *read-only* dan tidak dapat dimutasi lagi.

### Soal Tingkat Menengah (Intermediate)

6.  **Bagaimana representasi pola Discriminated Unions dapat diimplementasikan di C# sebelum fitur native dirilis secara resmi oleh tim Roslyn?**
    *   *Jawaban:* Melalui hierarki tipe tertutup: sebuah `abstract record` dengan konstruktor `private`, yang di dalamnya mendefinisikan sub-tipe turunan bertipe `sealed record`.
7.  **Dalam implementasi Railway-Oriented Programming, apa perbedaan konseptual antara operasi `Map` dan operasi `Bind` pada tipe `Result<T, E>`?**
    *   *Jawaban:* `Map` mentransformasi nilai sukses di dalam monad menggunakan fungsi proyeksi sederhana ($T \to U$), menghasilkan `Result<U, E>`. `Bind` menerima fungsi yang mengembalikan monad baru ($T \to Result<U, E>$), meratakan struktur agar tidak terjadi nesting tipe ganda seperti `Result<Result<U, E>, E>`.
8.  **Mengapa komputasi berbasis LINQ yang mengevaluasi `IEnumerable` secara berulang (*multiple enumeration*) bisa menimbulkan masalah performa dan keandalan dalam arsitektur fungsional?**
    *   *Jawaban:* Karena evaluasi LINQ bersifat *deferred* (*lazy*). Melakukan iterasi berulang akan mengeksekusi ulang seluruh pipa transformasi fungsi dari awal, yang dapat memicu alokasi berulang atau menghasilkan data inkonsisten jika ada side-effects tersembunyi pada sumber data.
9.  **Diberikan kode berikut: `public record Node(int Value, Node Next);`. Mengapa struktur ini berpotensi membahayakan runtime jika dilakukan operasi pembandingan nilai (`nodeA == nodeB`) pada rantai linked-list yang sangat panjang?**
    *   *Jawaban:* Kompiler menghasilkan kode pengecekan *equality* berbasis nilai secara rekursif untuk seluruh field record. Pada rantai linked-list yang sangat dalam, pemanggilan rekursif method `Equals` pada `Next` berpotensi memicu `StackOverflowException`.
10. **Bagaimana Pattern Matching di C# dieksekusi di level IL oleh compiler untuk kombinasi relational patterns (misal: `> 10 and <= 50`)?**
    *   *Jawaban:* Roslyn compiler mengompilasinya menjadi instruksi percabangan kondisional standar berbasis jump tables atau instruksi perbandingan biner langsung (`bge`, `ble`, `cgt`) di level Intermediate Language (IL), meminimalisir overhead performa setara dengan blok `if-else` primitif yang sangat optimal.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Misi Arsitektural: Idempotent Fraud Scoring Engine

Rancang dan bangun sebuah modul **Fraud Detection Engine** untuk platform e-commerce yang sepenuhnya mengadopsi paradigma pemrograman fungsional murni.

#### Spesifikasi Domain:
1.  **Immutability Ketat:** Tidak boleh ada variabel yang menggunakan kata kunci `var` yang dapat dimutasi ulang, tidak boleh ada properti dengan setter selain `init`, dan koleksi data wajib menggunakan `ImmutableArray<T>` atau `ImmutableList<T>`.
2.  **Struktur ADT:** Definisikan domain event menggunakan pola Discriminated Unions:
    *   `TransactionAnalyzed(Guid Id, double FraudScore)`
    *   `TransactionBlocked(Guid Id, string BlockReason)`
    *   `TransactionFlaggedForManualReview(Guid Id, ImmutableArray<string> Flags)`
3.  **Monadic Pipeline:**
    *   Bangun method pipeline: `EvaluateTransaction(Transaction tx) -> Result<FraudReport, EngineError>`.
    *   Aturan Evaluasi (wajib diimplementasikan sebagai ekspresi *pure functions*):
        *   Jika transaksi bernilai $> 100,000,000$ IDR dan terjadi antara pukul 01:00 - 04:00 AM $\to$ Tambah 60 poin fraud.
        *   Jika IP asal transaksi berada dalam blacklist (`ImmutableHashSet<string>`) $\to$ Langsung beralih ke `TransactionBlocked`.
        *   Jika skor akhir $> 80 \to$ Kembalikan status diblokir.
        *   Jika skor antara $50 - 80 \to$ Kembalikan status flagged for manual review.
        *   Jika skor $< 50 \to$ Lolos validasi.
4.  **Zero-Allocation Log Tracer:** Sisipkan operasi ekstensi `.Tap()` untuk mencatat metrik setiap tahapan evaluasi tanpa merusak *chaining* monad `Result`.
5.  **Benchmarking Mandiri:** Buat tes konsol untuk memproses $100.000$ evaluasi transaksi fungsional secara paralel (`Parallel.ForEach` atau `PLINQ`) untuk membuktikan keandalan *thread-safety* tanpa penggunaan *lock*, `Mutex`, maupun *race condition*. Evaluasi konsumsi memori dan pastikan heap allocation tetap minimal.