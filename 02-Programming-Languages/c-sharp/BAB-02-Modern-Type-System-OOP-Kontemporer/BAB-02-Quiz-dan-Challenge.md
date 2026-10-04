# BAB 02: Quiz, Challenge, & Knowledge Check
**Modern Type System & OOP Kontemporer**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantika Kesetaraan (Equality Semantics) pada Tipe Data Modern
Bandingkan secara mendalam mekanisme evaluasi kesetaraan (equality comparison) antara `class` standar, `record class`, dan `record struct`. Jelaskan bagaimana compiler C# menghasilkan implementasi `IEquatable<T>`, operator `==`, dan metode `GetHashCode()` untuk masing-masing tipe data tersebut, serta bagaimana *memory address comparison* berbeda dengan *value-based equality* pada level eksekusi Common Language Runtime (CLR).

### Soal 1.2: Ilusi Runtime pada Nullable Reference Types (NRT)
Fitur Nullable Reference Types (C# 8+) sering disalahpahami sebagai proteksi runtime. Jelaskan mengapa NRT pada dasarnya adalah sistem analisis statis (compile-time analysis) dan bagaimana metadata NRT (`NullableAttribute` dan `NullableContextAttribute`) diinjeksikan ke dalam assembly IL. Berikan contoh kasus di mana kode yang lolos validasi kompilasi NRT tanpa *warning* tetap dapat memicu `NullReferenceException` saat runtime.

### Soal 1.3: Immutabilitas, `init`-only Setters, dan Operasi *Non-Destructive Mutation*
Bagaimana compiler C# mengimplementasikan *keyword* `init` pada properti di tingkat Intermediate Language (IL)? Mengapa modifikator IL `modreq` (*required modifier*) digunakan untuk menegakkan aturan inisialisasi ini? Selain itu, bedah mekanisme internal dari ekspresi *non-destructive mutation* (`with { ... }`) pada tipe `record`: bagaimana konstruktor kloning (*copy constructor*) bekerja tanpa melanggar prinsip enkapsulasi?

### Soal 1.4: Polimorfisme Berbasis Pola vs. Polimorfisme Klasik Subtipe
Dalam OOP klasik, dispatch dinamis diselesaikan melalui *virtual method table* (vtable) pada pewarisan kelas (*subtype polymorphism*). Di sisi lain, C# kontemporer sangat menganjurkan *pattern matching* melalui ekspresi `switch`. Analisis perbandingan arsitektural antara kedua pendekatan ini dari perspektif:
1. *Open-Closed Principle* (kemudahan menambah operasi baru vs. menambah tipe data baru).
2. Mekanisme eksekusi CLR (instruksi IL `callvirt` vs. percabangan kondisional/jump-table).
3. Penerapan simulasi *Discriminated Unions* menggunakan hierarki `sealed record`.

### Soal 1.5: Batasan Struktural dan Garansi Memori `ref struct`
Jelaskan alasan mendasar mengapa tipe `ref struct` (seperti `ReadOnlySpan<T>`) tidak dapat dialokasikan di Managed Heap dalam kondisi apa pun. Sebutkan setidaknya 5 aturan restriksi kompilator yang diterapkan pada `ref struct` (misal: penangkapan lambda, boxing, async/await) dan jelaskan bagaimana garansi *stack-only* ini memengaruhi keamanan memori (*memory safety*) serta model eksekusi concurrency pada CLR.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Decompilation Boxing pada Pemanggilan Antarmuka (Interface Dispatch)
Perhatikan dua potongan kode pemanggilan antarmuka pada tipe `struct` berikut:

```csharp
public interface ICounter { void Increment(); }
public struct ValueCounter : ICounter
{
    private int _count;
    public void Increment() => _count++;
}

// Kasus A
public void ExecuteA(ICounter counter) => counter.Increment();

// Kasus B
public void ExecuteB<T>(T counter) where T : struct, ICounter => counter.Increment();
```

Bedah representasi Intermediate Language (IL) dari `ExecuteA` dan `ExecuteB`. Jelaskan secara mikro mengapa salah satu metode menimbulkan alokasi memori heap tersembunyi (*boxing allocation*) dan mutasi *state* lokal yang hilang (*lost mutation*), sedangkan metode lainnya dapat dieksekusi secara *inlined* tanpa alokasi melalui instruksi IL `constrained.`.

### Soal 2.2: Kerusakan Kontrak Kesetaraan Simetris pada Pewarisan Record
Diberikan hierarki pewarisan record:
```csharp
public record BaseEntity(Guid Id);
public record UserEntity(Guid Id, string Username) : BaseEntity(Id);
```
Jika kita melakukan evaluasi kesetaraan:
```csharp
BaseEntity a = new BaseEntity(id);
UserEntity b = new UserEntity(id, "admin");
bool eq1 = a.Equals(b);
bool eq2 = b.Equals(a);
```
Bagaimana implementasi properti `EqualityContract` yang digenerasikan oleh compiler menjaga integritas *Liskov Substitution Principle* (LSP) dan simetri kesetaraan? Apa nilai dari `eq1` dan `eq2`, serta mengapa implementasi default menolak kesetaraan meskipun *value ID* keduanya identik?

### Soal 2.3: Diagnostic Debugging Null-State Static Analysis Attributes
Perhatikan kode berikut yang menimbulkan compiler warning saat NRT diaktifkan:
```csharp
public class CacheRegistry
{
    private readonly Dictionary<string, object> _store = new();

    public bool TryGetValue(string key, out object value)
    {
        return _store.TryGetValue(key, out value!);
    }
}
```
Meskipun menggunakan pemaksaan `value!`, konsumen kode di atas akan mendapatkan *false sense of security* yang berujung pada dereferensi pointer null di hilir. Tuliskan ulang tanda tangan (*signature*) metode tersebut menggunakan atribut analisis statis yang benar (`[NotNullWhen]`, `[MaybeNullWhen]`, dll.) dan jelaskan bagaimana mesin Roslyn mengonsumsi atribut tersebut untuk mengubah alur *flow-state analysis* variabel di sisi pemanggil.

### Soal 2.4: Mekanisme Resolusi Default Interface Methods (DIM) dan Diamond Problem
C# mendukung Default Interface Methods (DIM). Jika sebuah kelas mengimplementasikan dua antarmuka yang memiliki *signature* metode identik dengan implementasi default:
```csharp
public interface ILoggerA { void Log(string msg) => Console.WriteLine($"A: {msg}"); }
public interface ILoggerB { void Log(string msg) => Console.WriteLine($"B: {msg}"); }
public class SystemLogger : ILoggerA, ILoggerB { }
```
1. Mengapa kode di atas menghasilkan *compile-time error* saat pemanggilan langsung dilakukan?
2. Bagaimana aturan runtime CLR menyelesaikan konflik *diamond inheritance* (pemberian implementasi paling spesifik / *most specific override rule*)?
3. Mengapa metode implementasi default tidak dapat diakses langsung melalui referensi instance kelas (`new SystemLogger().Log(...)`), melainkan harus melalui explicit interface cast?

### Soal 2.5: Optimasi Pattern Matching Engine pada Tipe Primitif vs Relasional
Tinjau ekspresi evaluasi berikut:
```csharp
public string EvaluateRisk(decimal leverage, int creditScore) => (leverage, creditScore) switch
{
    (<= 1.0m, > 750) => "Low",
    (<= 2.5m, > 650) => "Medium",
    (> 5.0m, _) or (_, < 500) => "Critical",
    _ => "High"
};
```
Jelaskan bagaimana Roslyn menyusun Decision Tree (pohon keputusan) untuk mengevaluasi *tuple pattern* dan *relational pattern* di atas. Apakah compiler menggunakan percabangan biner berurutan, lompatan multi-kondisi, atau *lookup jump table*? Bagaimana urutan penulisan pattern mempengaruhi jumlah evaluasi kondisi (*branching overhead*) pada level CPU instruction cache?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Alokasi Memori dan GC Churn pada High-Frequency Data Ingestion
Sebuah mikroservis pemrosesan metrik IoT menerima 80.000 pembacaan telemetri per detik melalui protokol binary TCP. Sistem memvalidasi, memformat, dan meneruskan data tersebut ke Kafka. Profiling memori melalui `dotnet-trace` dan PerfView menunjukkan bahwa:
- CPU menghabiskan 38% waktu pada siklus GC (Garbage Collection Gen 0 dan Gen 1 collections sangat agresif).
- Analisis *heap allocation* menunjukkan jutaan objek DTO jangka pendek dibuat dari kelas berikut:

```csharp
public class TelemetryPayload
{
    public Guid DeviceId { get; set; }
    public double MetricValue { get; set; }
    public DateTime Timestamp { get; set; }
    public string SensorType { get; set; }
    public IDictionary<string, string> Tags { get; set; }
}
```

#### Pertanyaan Diagnostik & Arsitektural:
1. Rancang ulang model domain di atas menggunakan paradigma C# modern (`readonly record struct`, `ref struct`, atau teknik *immutable flyweight*) untuk memangkas alokasi managed heap mendekati 0 byte pada *hot execution path*.
2. Bagaimana Anda menangani koleksi `Tags` tanpa menimbulkan alokasi memori dinamis di heap untuk setiap pembacaan?
3. Jelaskan trade-off performa antara mem-passing tipe data hasil rancangan Anda menggunakan `in` modifier vs passing by-value pada CPU architecture x64.

---

### Skenario B: Race Condition dan State Mutation Bug pada Pipeline Order Matching
Pada sistem bursa pertukaran kripto, transaksi diproses secara paralel menggunakan `System.Threading.Channels`. Tim developer menggunakan `record class` untuk menjamin immutabilitas data. Namun, tim audit mendapati bahwa dalam kondisi konkurensi ekstrem, isi saldo portofolio pengguna terkadang menampilkan data transaksi pesanan (*order*) milik akun lain, atau perubahan kuantitas pesanan hilang (*lost updates*). 

Investigasi menemukan kode berikut pada modul *order modifier*:

```csharp
public record Order(Guid OrderId, Guid UserId, decimal Amount, List<OrderLog> Logs);

// Dipanggil dari thread yang berbeda
public Order ApplyFee(Order order, decimal fee)
{
    var updated = order with { Amount = order.Amount - fee };
    updated.Logs.Add(new OrderLog($"Fee applied: {fee} at {DateTime.UtcNow}"));
    return updated;
}
```

#### Pertanyaan Diagnostik & Arsitektural:
1. Identifikasi secara tepat cacat desain pada record `Order` yang memicu kondisi *race condition* dan hilangnya integritas referensi data, meskipun modifikator `with` digunakan.
2. Jelaskan konsep *Shallow Copy* vs *Deep Copy* pada operasi `with` compiler C#, dan mengapa penggunaan koleksi standar (`List<T>`) pada tipe data yang diklaim "immutable" merupakan *antipattern* berbahaya.
3. Tuliskan refaktor lengkap kode di atas dengan mengadopsi struktur koleksi yang benar-benar aman terhadap konkurensi tanpa memerlukan penguncian eksplisit (`lock` atau `Monitor`).

---

### Skenario C: Modeling Domain Kompleks: FinTech Payment State Machine
Anda adalah Principal Architect pada payment gateway skala global. Sistem harus memodelkan alur hidup pembayaran (*Payment Life Cycle*) yang memiliki state:
1. `Initiated` (hanya membawa `PaymentId`, `Amount`, `Currency`).
2. `Authorized` (memiliki `AuthCode`, `ExpiryTime`, dan turunan data `Initiated`).
3. `Captured` (memiliki `TransactionRef`, `SettledAt`, dan turunan data `Authorized`).
4. `Failed` (memiliki `ErrorCode`, `FailureReason`, dan referensi *state* saat kegagalan terjadi).

Aturan bisnis: Operasi *capture* hanya sah jika state saat ini adalah `Authorized`. Pemrosesan *refund* hanya sah jika state saat ini adalah `Captured`. Sistem menolak penggunaan field opsional yang bernilai null (misal: field `AuthCode` yang dibiarkan null pada saat state masih `Initiated`).

#### Pertanyaan Diagnostik & Arsitektural:
1. Rancang tipe data sistem pembayaran ini menggunakan pendekatan **Simulated Discriminated Unions** dengan `abstract record` dan hierarki tertutup (`sealed`).
2. Tuliskan metode eksekusi transisi status menggunakan ekspresi *exhaustive pattern matching*. Tunjukkan bagaimana compiler Roslyn secara aktif mencegah *developer error* (misal: lupa menangani salah satu state atau mencoba melakukan validasi ilegal) tanpa perlu pengecekan runtime manual dengan `if-else`.
3. Bandingkan desain ini dengan pola OOP klasik State Pattern (menggunakan *context class* dan *state interface*). Mengapa pendekatan tipe data fungsional-kontemporer ini lebih unggul dalam sistem terdistribusi berbasis *event-sourcing*?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Zero-Allocation Financial Order Routing Engine

#### Problem Statement
Sebuah sistem High-Frequency Trading (HFT) Gateway memerlukan modul validasi dan routing pesanan (*order execution router*). Modul ini menerima representasi data order mentah yang sangat beragam (Market Order, Limit Order, Stop-Loss Order) dan harus mengeksekusi aturan validasi bisnis mikrodetik secara deterministik. Penggunaan GC collections di dalam sistem ini dapat menyebabkan *latency spike* fatal yang memicu kerugian finansial.

#### Technical Requirements
1. **Representasi Model Data Domain**:
   - Modelkan tipe pesanan menggunakan **simulated Discriminated Unions** berbasis hierarki tipe data nilai (`record struct` atau `readonly struct` terpadu) atau hierarki tertutup yang dirancang untuk mencegah boxing dan meminimalkan cache misses.
   - Aturan tipe pesanan:
     * `MarketOrder`: Memiliki `OrderId` (Guid), `Symbol` (maksimal 8 karakter ASCII), `Quantity` (decimal), `Side` (Buy/Sell).
     * `LimitOrder`: Turunan parameter `MarketOrder` ditambah `LimitPrice` (decimal).
     * `StopLossOrder`: Turunan parameter `MarketOrder` ditambah `TriggerPrice` (decimal) dan `IsTrailing` (bool).
2. **Exhaustive Pipeline Validation Engine**:
   - Bangun static class `OrderRouter` dengan metode `public static ValidationResult ValidateAndRoute(in OrderRequest order)`.
   - Gunakan **Switch Expressions** dengan **Relational, Property, and Type Patterns** untuk menegakkan aturan berikut:
     * `Quantity` harus strictly > 0.
     * `LimitOrder`: `LimitPrice` harus > 0. Jika `Side` adalah `Buy`, harga limit tidak boleh melebihi batas pengaman sirkuit (asumsikan threshold `$1,000,000`).
     * `StopLossOrder`: `TriggerPrice` harus > 0. Jika `IsTrailing == true`, sistem harus memicu rute khusus "DynamicTrackingQueue".
     * Penolakan (*Reject*) terhadap setiap order yang tidak memenuhi spesifikasi dengan pesan error yang deskriptif.
3. **Compile-Time Null Safety & Zero Allocations**:
   - Mode `<Nullable>enable</Nullable>` aktif secara penuh. Tidak boleh ada tanda seru (`!`) *null-forgiving operator*.
   - Tidak boleh ada alokasi di Managed Heap selama pemrosesan routing (`0 bytes allocated` per pemanggilan metode `ValidateAndRoute`).
   - Gunakan tipe `ValueStringBuilder` atau `Span<char>` / `ReadOnlySpan<char>` jika diperlukan manipulasi string identifier (dilarang menggunakan concatenations `+` atau `$"{...}"` yang mengalokasikan string baru di heap).

#### Constraints
- Menggunakan **C# 10 / 12 (.NET 8+)**.
- Diuji menggunakan **BenchmarkDotNet** untuk membuktikan metrik: `Allocated = 0 B`.
- Tidak boleh ada operasi *boxing* saat memproses berbagai jenis bentuk order (gunakan *generics* dengan *constraints* atau *discriminated unions with struct backing* secara ketat).

#### Expected Output
1. Implementasi kode arsitektur domain type system lengkap dan modular.
2. Kode metode validasi berbasis pattern matching modern.
3. Kode benchmark harness (*BenchmarkDotNet*) yang membuktikan `Allocated = 0 B` dan eksekusi berada pada level puluhan nanodetik.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis sebelum melangkah ke topik memori tingkat lanjut dan konkurensi.

### Saya harus memahami:
- [ ] Perbedaan fundamental representasi biner memori antara Value Types dan Reference Types pada stack dan managed heap.
- [ ] Dampak runtime dari `Nullable Reference Types` (NRT) dan bagaimana menganotasi API menggunakan metadata atribut Roslyn.
- [ ] Mekanisme kode yang digenerasikan oleh compiler C# untuk `record`, termasuk *structural equality*, *copy constructor*, dan *cloning mechanics*.
- [ ] Mekanisme internal instruksi IL `constrained.` dan bagaimana CLR mencegah alokasi boxing saat memanggil antarmuka pada tipe nilai.
- [ ] Seluruh taksonomi modern Pattern Matching: *Declaration, Type, Constant, Relational, Logical, Property, Positional, dan List Patterns*.
- [ ] Model resolusi deterministik dan batasan inheren dari Default Interface Methods (DIM).
- [ ] Konsep stack-only memory safety yang ditegakkan secara ketat pada tipe data `ref struct`.

### Saya tidak perlu menghafal:
- [ ] Seluruh nama hex opcodes dari Intermediate Language (IL) CLR (cukup memahami instruksi esensial seperti `box`, `unbox`, `call`, `callvirt`, `constrained.`).
- [ ] Implementasi algoritma hash-code shift-register kompilator untuk `GetHashCode` pada generated records.
- [ ] Sintaks legacy C# versi 1.0 - 6.0 untuk verifikasi tipe null atau casting berbasis tipe manual (`as` dan pengecekan manual berulang).

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan mengeliminasi alokasi heap tersembunyi (*hidden boxing allocations*) menggunakan decompiler IL (seperti ILSpy, dnSpy, atau Rider IL Viewer).
- [ ] Mengonversi hierarki kelas domain OOP klasik yang mutable menjadi model data immutable berbasis `record` tanpa menimbulkan efek samping *shallow copy*.
- [ ] Merancang arsitektur Finite State Machine atau domain data kompleks menggunakan teknik *Simulated Discriminated Unions* dengan *compile-time completeness guarantee*.
- [ ] Menerapkan atribut analisis statis NRT secara presisi pada library/komponen reusable untuk mencegah *unhandled null exceptions* di sistem hilir.
- [ ] Menulis kode performa tinggi tanpa alokasi (*zero-allocation execution path*) dengan memanfaatkan kombinasi `readonly record struct`, `in` parameter, dan `Span<T>`.