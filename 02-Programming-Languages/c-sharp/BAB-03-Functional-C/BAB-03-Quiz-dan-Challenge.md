# BAB 03: Quiz, Challenge, & Knowledge Check
**Functional C#, Delegasi & LINQ Internals**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi Internal Delegasi:**
   Secara arsitektural di level CLR, kelas abstrak `System.MulticastDelegate` mewarisi `System.Delegate`. Jelaskan fungsi spesifik dari tiga *field* internal intinya: `_target`, `_methodPtr`, dan `_invocationList`. Bagaimana CLR mengeksekusi pemanggilan delegasi bertipe *multicast* dan apa dampaknya terhadap *return value* jika delegasi tersebut mengembalikan sebuah nilai non-`void`?

2. **Mekanika Hoisting dan Closure:**
   Ketika sebuah *lambda expression* meng-capture variabel lokal dari *enclosing method*, apa yang sebenarnya dilakukan oleh C# *compiler* di belakang layar? Jelaskan konsep *display class* (closure class), alokasi memori yang terjadi pada *managed heap*, dan mengapa hal ini dapat berujung pada degradasi performa atau *memory leak* laten.

3. **Deferred Execution vs Immediate Execution:**
   Jelaskan perbedaan mendasar antara model eksekusi *deferred* (seperti `.Where()`, `.Select()`) dan *immediate* (seperti `.ToList()`, `.Count()`). Bagaimana LINQ iterator menunda evaluasi hingga pemanggilan `GetEnumerator()`/`MoveNext()` dilakukan, dan apa konsekuensinya terhadap modifikasi status (*side-effects*) pada koleksi sumber selama masa penundaan tersebut?

4. **AST Representation: `Func<T>` vs `Expression<Func<T>>`:**
   Secara representasi IL dan konsumsi memori, apa yang membedakan penulisan delegasi `Func<T, bool>` dengan Expression Tree `Expression<Func<T, bool>>`? Mengapa *compiler* menolak ekspresi *statement body* (berkurung kurawal) pada `Expression<Func<T>>`, dan bagaimana abstraksi ini memungkinkan *LINQ Provider* (seperti Entity Framework Core) menerjemahkan kode C# menjadi dialek SQL?

5. **Batas Evaluasi `IEnumerable<T>` vs `IQueryable<T>`:**
   Jelaskan *architectural boundary* antara `IEnumerable<T>` dan `IQueryable<T>`. Pada skenario apa eksekusi query berpindah dari *server-side pushdown* (pada remote database engine) menjadi *client-side in-memory filtering*? Tinjau dampaknya terhadap konsumsi *bandwidth* jaringan dan I/O database.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Loop Variable Capture Semantics:**
   Analisis perbedaan semantik kompilasi C# 4.0 dan C# 5.0+ dalam penanganan variabel iterasi pada perulangan `for` versus `foreach` ketika dimasukkan ke dalam *closure*. Mengapa kode berikut berpotensi menghasilkan *output* yang tidak diharapkan pada *looping* berbasis indeks (`for`) jika dieksekusi secara asinkron atau bertahap?
   ```csharp
   var actions = new List<Action>();
   for (int i = 0; i < 5; i++)
   {
       actions.Add(() => Console.WriteLine(i));
   }
   actions.ForEach(a => a());
   ```

2. **Dekomposisi State Machine pada `yield return`:**
   Bagaimana compiler C# mengubah metode yang mengandung kata kunci `yield return` menjadi sebuah *state machine class* privat yang mengimplementasikan `IEnumerable<T>`, `IEnumerator<T>`, dan `IDisposable`? Bagaimana *state machine* tersebut menjamin blok `finally` tetap dieksekusi ketika *consumer* menghentikan enumerasi di tengah jalan menggunakan `break` atau terkena *unhandled exception*?

3. **Multiple Enumeration Trap:**
   Diberikan sebuah pipeline *cold observable/pure streaming* `IEnumerable<T>` yang membaca data langsung dari *network stream* atau *forward-only database reader*. Jelaskan malfungsi sistem dan implikasi performa yang terjadi jika *developer* memanggil metode agregasi (misalnya `if (items.Any())`) sebelum melakukan iterasi data (`foreach (var item in items)`). Bagaimana cara mendeteksi anomali ini menggunakan *memory allocation profiling*?

4. **Hidden Allocation Elimination:**
   Identifikasi seluruh sumber *heap allocation* yang tersembunyi pada potongan kode LINQ berikut, lalu rekonstruksi kode tersebut menggunakan paradigma non-allocating (memanfaatkan `Span<T>`, *struct enumerator*, atau manipulasi loop konvensional):
   ```csharp
   public int CalculateTotalDiscount(IEnumerable<Order> orders, decimal threshold)
   {
       return orders
           .Where(o => o.Amount > threshold)
           .Select(o => o.Discount)
           .Sum();
   }
   ```

5. **Expression Tree Mutation via `ExpressionVisitor`:**
   Bagaimana arsitektur `ExpressionVisitor` bekerja untuk memanipulasi *predicate tree* secara *immutable* saat runtime? Jelaskan pola implementasi untuk mendeteksi simpul tertentu (misalnya, menimpa pemanggilan *soft-deleted entity filter* `e => !e.IsDeleted`) dan merekonstruksi pohon ekspresi baru tanpa merusak integritas *node identity* dan tipe data aslinya.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike dan GC Pressure Akibat Hidden Closure Allocation
Sebuah microservice *high-throughput payment gateway* memproses 25.000 transaksi per detik. Metrik APM menunjukkan bahwa rata-rata *latency* berada di angka 4 ms, namun secara berkala mengalami *latency spike* hingga 180 ms setiap 45 detik. Analisis dump memori menunjukkan terjadinya siklus *Garbage Collection Gen 0 & Gen 1* yang sangat masif, dipicu oleh alokasi puluhan juta objek berumur sangat pendek dari potongan kode validasi transaksi berikut:
```csharp
public class PaymentValidator
{
    private readonly decimal _dailyLimit;

    public PaymentValidator(decimal dailyLimit) => _dailyLimit = dailyLimit;

    public bool ValidateTransactions(List<Transaction> transactions, decimal batchOffset)
    {
        // Kode ini dipanggil 25.000 kali/detik
        return transactions.All(t => t.Value + batchOffset <= _dailyLimit);
    }
}
```
* **Pertanyaan Diagnostik:**
  1. Identifikasi secara tepat variabel apa saja yang memicu pembentukan *display class* dan alokasi instans delegasi `Func<Transaction, bool>` pada setiap eksekusi.
  2. Mengapa *caching* delegasi otomatis oleh compiler (*static delegate caching*) gagal bekerja pada kasus ini?
  3. Desain ulang metode tersebut agar mencapai status **Zero Allocation** (0 bytes per invocation pada *heap*) tanpa mengubah fungsionalitas validasinya.

---

### Skenario B: Race Condition dan State Mutation dalam Parallel LINQ (PLINQ)
Sebuah sistem analisis risiko mengagregasi data log transaksi finansial menggunakan PLINQ untuk mempercepat komputasi skoring. Kode di bawah ini dijalankan dalam background worker:
```csharp
var suspiciousUserIds = new HashSet<int>();
transactions.AsParallel()
    .WithDegreeOfParallelism(Environment.ProcessorCount)
    .Where(t => t.RiskScore > 85)
    .Select(t => 
    {
        if (t.IsInternational)
        {
            suspiciousUserIds.Add(t.UserId); // External state mutation
        }
        return t.Id;
    })
    .ToList();
```
Di lingkungan produksi, eksekusi kode ini sering kali memunculkan `NullReferenceException` atau `IndexOutOfRangeException` acak di dalam internal `HashSet<T>`, dan jumlah data yang tersimpan pada `suspiciousUserIds` sering kali tidak konsisten dengan data aktual.
* **Pertanyaan Diagnostik:**
  1. Bedah titik kegagalan (*thread-safety violation*) yang terjadi pada interaksi antara deferred nature PLINQ dan mutasi *external closure state*.
  2. Jelaskan mengapa *pipeline side-effects* di dalam operator `.Select()` atau `.Where()` merupakan pelanggaran fatal terhadap prinsip *functional purity*.
  3. Rancang ulang solusi pipeline tersebut menggunakan arsitektur functional murni (pure functions) yang *thread-safe*, tanpa mengorbankan paralelisasi komputasi dan tanpa menambahkan lock manual (*lock-free*).

---

### Skenario C: Remote Query Translation Failure & Out-Of-Memory (OOM)
Sebuah sistem inventaris logistik memproses jutaan rekaman data pengiriman pada Microsoft SQL Server menggunakan EF Core. Salah satu endpoint pencarian mendadak menyebabkan pod Kubernetes mengalami *OOMKilled* (Out Of Memory) saat pengguna mengeksekusi pencarian status pesanan menggunakan query berikut:
```csharp
public async Task<List<ShipmentDto>> SearchShipmentsAsync(string trackingPrefix)
{
    return await _context.Shipments
        .Where(s => NormalizeTracking(s.TrackingNumber).StartsWith(trackingPrefix))
        .OrderByDescending(s => s.CreatedAt)
        .Take(50)
        .Select(s => new ShipmentDto(s.Id, s.TrackingNumber, s.Status))
        .ToListAsync();
}

private static string NormalizeTracking(string rawTracking) =>
    rawTracking.Replace("-", "").Trim().ToUpperInvariant();
```
* **Pertanyaan Diagnostik:**
  1. Jelaskan bagaimana EF Core Expression Tree Parser merespons pemanggilan metode lokal `NormalizeTracking` yang tidak memiliki pemetaan (SQL Translation) langsung di database engine.
  2. Mengapa limitasi `.Take(50)` gagal mencegah pemuatan jutaan baris data ke dalam memori aplikasi sebelum C# 3.0 / EF Core modern memunculkan behavior evaluasi tertentu?
  3. Bagaimana arsitektur kueri dan skema data harus diubah agar evaluasi expression tree sepenuhnya terdorong (*pushdown execution*) ke database engine secara optimal (SARGable)?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Zero-Allocation Custom LINQ Engine

#### Problem:
Pada sistem *high-frequency telemetry streaming*, jutaan metrik bertipe `struct MetricRecord` dialirkan setiap detik. Penggunaan standard LINQ (`System.Linq`) dilarang keras di jalur kritis (*hot path*) ini karena alokasi `IEnumerable<T>` interface dispatching, pembuatan *display classes*, dan instansiasi delegasi `Func<T, bool>` memicu kerja berlebih pada *garbage collector* yang menyebabkan *jitter* pada latensi pemrosesan.

#### Requirements:
1. **Custom Struct Enumerator & Extensions:**
   Implementasikan ekstensi LINQ kustom bernama `WhereZeroAlloc` dan `SelectZeroAlloc` yang beroperasi langsung di atas `ReadOnlySpan<T>` atau `T[]` tanpa alokasi heap sama sekali (0 bytes allocated).
2. **Duck-Typing Implementation:**
   Hindari penggunaan interface `IEnumerable<T>` atau `IEnumerator<T>` pada pipeline operator. Manfaatkan pola C# *duck-typing pattern-based compilation* untuk `GetEnumerator()`, `MoveNext()`, dan `Current` berbasis `ref struct`.
3. **Struct-Based Predicate / Value Delegates:**
   Alih-alih mengandalkan tipe delegasi referensi seperti `Func<T, bool>`, gunakan *generic struct constraint* yang mengimplementasikan antarmuka predikat internal (misalnya `struct MyPredicate : IValueFilter<MetricRecord>`) untuk memungkinkan compiler JIT melakukan pemanggilan metode secara *direct call* dan memfasilitasi inlining agresif.
4. **Performance Benchmark Verification:**
   Buktikan efisiensi kode dengan menyertakan harness BenchmarkDotNet yang menguji:
   * Standard LINQ (`records.Where(...).Select(...).Count()`)
   * Custom Zero-Alloc LINQ Pipeline

#### Constraints:
* **Allocated Memory:** Wajib **0 B** (*zero bytes allocated*) pada status *steady-state execution*.
* **Execution Latency:** Pipeline kustom harus lebih cepat minimal 3x hingga 5x dibandingkan standard LINQ.
* **No Unsafe Code:** Tidak boleh menggunakan `unsafe` pointer arithmetics; manipulasi data wajib menggunakan managed abstraction yang aman (`Span<T>`, `ReadOnlySpan<T>`, atau manipulasi indeks terproteksi).

#### Expected Output:
Kode C# lengkap yang mandiri (*runnable console code*) mencakup:
1. Definisi model `MetricRecord`.
2. Antarmuka dan struct-based filter abstractions (`IValueFilter<T>`, dsb.).
3. Rantai struct enumerator kustom yang mengimplementasikan *duck-typed iteration pattern*.
4. Kelas implementasi extension methods.
5. Setup *benchmark class* menggunakan BenchmarkDotNet yang membuktikan efisiensi memori (0 Byte) dan peningkatan *throughput*.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi internal `System.MulticastDelegate` (`_target`, `_methodPtr`, `_invocationList`) dan biaya alokasi memori pembuatannya.
- [ ] Mekanisme dekomposisi kompilator terhadap *anonymous functions*, *lambda expressions*, dan pemrosesan variabel *captured* (closure hoisting).
- [ ] Perbedaan siklus hidup dan lokasi alokasi antara *static delegate caching* vs *per-invocation closure allocation*.
- [ ] Siklus hidup *state machine* pada metode berbasis `yield return` dan cara kerja *disposal handling* pada iterator enumerator.
- [ ] Arsitektur Abstract Syntax Tree (AST) pada `System.Linq.Expressions.Expression<TDelegate>` dan mekanisme rekursi via `ExpressionVisitor`.
- [ ] Perbedaan eksekusi semantik antara `IEnumerable<T>` (in-memory iteration) dan `IQueryable<T>` (declarative deferred evaluation).
- [ ] Bahaya tersembunyi dari fenomena *multiple enumeration* pada streaming sequences.

### Saya tidak perlu menghafal:
- [ ] Nilai spesifik *opcode* IL yang diemisikan compiler untuk sebuah delegasi (seperti `ldftn`, `dup`, dsb.).
- [ ] Daftar lengkap seluruh tipe *node* enumerasi pada `ExpressionType` (cukup pahami cara navigasi dan membaca strukturnya).
- [ ] Kode implementasi internal runtime C# untuk *backoff policy* pada PLINQ engine.

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi dan memusnahkan *hidden heap allocations* yang diakibatkan oleh penggunaan LINQ dan *closure* di dalam *hot execution paths*.
- [ ] Membaca serta menganalisis hasil dekomposisi kode (via IL Viewer atau decompiled C# tools seperti ILSpy/SharpLab) untuk menelaah struktur *compiler-generated display classes*.
- [ ] Merancang pipeline pemrosesan data menggunakan *struct-based enumerators* untuk mencapai performa *zero-allocation*.
- [ ] Melakukan dekomposisi dan manipulasi dinamis terhadap Expression Tree untuk kebutuhan custom query filtering (misalnya *dynamic enterprise query builder*).
- [ ] Menulis arsitektur kueri LINQ-to-Entities (EF Core) yang menjamin *full pushdown translation* ke remote engine secara optimal tanpa fallback client-side evaluation.