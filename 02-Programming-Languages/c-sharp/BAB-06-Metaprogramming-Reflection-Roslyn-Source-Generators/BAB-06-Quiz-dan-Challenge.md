# BAB 06: Quiz, Challenge, & Knowledge Check
**Metaprogramming, Reflection & Roslyn Source Generators**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Metadata Heap, Runtime Type Handle, dan Cost of Reflection
Jelaskan secara struktural bagaimana CLR merepresentasikan tipe data pada runtime memory saat sebuah assembly di-load (`Module`, `TypeDef`, `MethodTable`, dan `EEClass`). Mengapa pemanggilan `typeof(T)` memiliki kompleksitas $O(1)$ dan zero-allocation, sedangkan `Type.GetType(string)` memicu runtime overhead yang masif?

### Soal 1.2: Dynamic Method Dispatch Trade-offs
Bandingkan mekanisme eksekusi, overhead pemanggilan (*invocation cost*), alokasi memori heap, dan optimasi JIT (*inlining*) dari tiga pendekatan berikut untuk mengeksekusi metode secara dinamis:
1. Direct Invocation via `MethodInfo.Invoke(instance, parameters)`
2. Delegate compilation via `Expression<TDelegate>.Compile()`
3. IL generation via `System.Reflection.Emit.DynamicMethod`

### Soal 1.3: Roslyn Compiler Pipeline Lifecycle
Gambarkan siklus hidup kompilasi C# pada Roslyn (*Parser*, *Declaration Table*, *Binding/Semantic Model*, dan *Emit*). Di mana fase eksekusi Roslyn Source Generator diinjeksikan, dan mengapa Source Generator didesain secara arsitektural bersifat *additive-only* (tidak diizinkan memodifikasi atau menghapus Abstract Syntax Tree/AST yang sudah ada)?

### Soal 1.4: Native AOT dan Assembly Trimming Incompatibility
Mengapa kode berbasis reflection klasik seperti `Activator.CreateInstance(Type.GetType(typeName))` atau pembacaan property berbasis string lookup secara inheren memecah kompatibilitas dengan *Native AOT* (Ahead-of-Time) dan *IL Linker/Trimmer* pada .NET 8/9? Konsep apa yang digunakan Roslyn Source Generators untuk menyelesaikan masalah ini?

### Soal 1.5: Partial Methods dan Partial Classes Evolution
Bagaimana evolusi fitur C# *Partial Classes* dan *Partial Methods* (khususnya *extended partial methods* yang diperkenalkan pada C# 9) menjadi pondasi teknis utama bagi integrasi kode buatan Source Generator dengan kode tulisan tangan (*handcrafted code*) tanpa menimbulkan *diamond dependency* atau konflik metadata?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Memory Allocation Anatomy pada `MethodInfo.Invoke`
Perhatikan kode berikut:
```csharp
MethodInfo method = typeof(OrderService).GetMethod(nameof(OrderService.ProcessOrder));
object[] args = new object[] { 42, "ORD-2024" };
method.Invoke(serviceInstance, args);
```
Bedah seluruh titik alokasi memori heap (*managed heap allocation*) dan konversi tipe (*boxing/unboxing*) yang terjadi dari baris kedua hingga baris ketiga. Bagaimana Anda merefaktor pemanggilan ini pada .NET 8+ menggunakan `UnsafeAccessorAttribute` untuk mencapai *zero-allocation* dan performa setara pemanggilan langsung (*direct call*)?

### Soal 2.2: AssemblyLoadContext (ALC) Leaks & Zombie Assemblies
Dalam arsitektur *Plugin System* yang mendukung *hot-reloading* menggunakan `AssemblyLoadContext(isCollectible: true)`, sering terjadi kondisi di mana native memory tidak pernah terbebas meskipun `alc.Unload()` telah dipanggil dan GC telah dipicu secara eksplisit.
1. Objek reflection apa saja (`Type`, `MethodInfo`, custom dynamic delegates) yang dapat menahan referensi hidup (*root reference*) ke ALC?
2. Bagaimana strategi menggunakan `WeakReference` dan investigasi via WinDbg/`dotnet-dump` (perintah `!dumpheap` dan `!gcroot`) untuk mendeteksi *Metadata Reference Leak* ini?

### Soal 2.3: `IIncrementalGenerator` Pipeline Caching Breakdown
Mengapa penggunaan interface legacy `ISourceGenerator` sudah ditinggalkan dan digantikan oleh `IIncrementalGenerator`? Jelaskan peran state caching berbasis pipeline:
```csharp
IncrementalValuesProvider<T> transform = context.SyntaxProvider
    .CreateSyntaxProvider(predicate, transform)
    .WithComparer(EqualityComparer<T>.Default);
```
Apa konsekuensi bencana terhadap *Visual Studio IDE performance* dan kompilasi *in-proc* jika model transformasi Anda mengekspos tipe data Roslyn langsung seperti `SyntaxNode` atau `ISymbol` ke tahap *Source Production* alih-alih tipe data murni yang *equatable* (POCO record)?

### Soal 2.4: Cold-Start Penalty & Memory Explosion pada `Expression.Compile()`
Dalam framework ORM atau Object Mapper kustom, developer sering menggunakan:
```csharp
Expression<Func<TSource, TTarget>> expr = ...;
Func<TSource, TTarget> mapper = expr.Compile();
```
Jelaskan proses internal yang terjadi di balik `expr.Compile()`:
1. Mengapa eksekusi pertama (*cold-start*) sangat lambat?
2. Apakah `DynamicMethod` yang dihasilkan oleh `Compile()` disimpan di GC Heap, JIT Code Heap, atau LoaderAllocator?
3. Apa risiko fatal (*memory leak* / *OutOfMemoryException*) jika dynamic mapper ini di-compile berulang kali di dalam request loop tanpa mekanisme caching delegate yang tepat?

### Soal 2.5: C# Interceptors (C# 12 Preview / Experimental Feature)
Jelaskan cara kerja arsitektur *Interceptors* pada C# 12+. Bagaimana atribut `[InterceptsLocation(version, data)]` bekerja pada level *Abstract Syntax Tree* (AST) untuk mengalihkan pemanggilan method secara langsung di waktu kompilasi tanpa dynamic proxy, reflection, atau IL weaving runtime (seperti Castle DynamicProxy atau Fody)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi Ekstrem pada Payment Gateway Serializer
*Konteks:* Perusahaan Anda menangani 450.000 transaksi pembayaran per detik. Profiling APM menunjukkan latensi p99 membengkak hingga 1.800 ms. Hasil tracing CPU menggunakan `dotnet-trace` dan PerfView mengungkap bahwa 68% CPU time dihabiskan pada:
* `System.Reflection.RuntimePropertyInfo.GetValue`
* `System.RuntimeType.GetProperties`
* `System.GC.Collect` (Gen 0 GC thrashing terjadi setiap 2 milidetik akibat pembuatan array parameter dan boxing struct).

Aplikasi menggunakan engine JSON/MessagePack mapping kustom berbasis reflection rekursif yang membaca attribute dynamic schema pada setiap request transaksi.

*Pertanyaan Diagnostik & Solusi:*
1. Identifikasi *fundamental architectural flaw* dari implementasi engine tersebut.
2. Rancang strategi refactoring dua tahap:
   * **Mitigasi Cepat (Zero-Code Generation):** Transformasi naive reflection menjadi *compiled open-instance delegates* yang di-cache dalam static generic memory container. Tunjukkan struktur kode dan perhitungan throughput-nya.
   * **Solusi Permanen (Native AOT-Ready):** Arsitektur Roslyn Incremental Source Generator untuk me-replace dynamic reflection ke deterministic compile-time serializer code.

---

### Skenario B: Race Condition dan Dynamic Type Explosion pada Multi-Tenant Engine
*Konteks:* Platform SaaS multi-tenant memungkinkan kustomisasi skema database secara dinamis. Untuk memetakan model database tenant ke memory, engine menggunakan `System.Reflection.Emit` (`AssemblyBuilder.DefineDynamicAssembly`) untuk men-generate DTO class secara on-the-fly.

Ketika terjadi spike traffic bersamaan saat event *Black Friday*, server mengalami crash total dengan log:
* `System.TypeLoadException: "Could not load type..."`
* `System.Threading.SynchronizationLockException`
* Alokasi native memori Process Private Bytes melonjak dari 2 GB menjadi 32 GB dalam waktu 5 menit tanpa adanya penambahan data transaksi yang signifikan.

*Pertanyaan Diagnostik & Solusi:*
1. Mengapa `Reflection.Emit` pada tipe assembly non-collectible memicu ledakan memori permanen (*LoaderAllocator unmanaged memory exhaustion*)?
2. Jika pembuatan tipe dinamis dilindungi oleh `ConcurrentDictionary<string, Type>`, jelaskan skenario race condition di mana *thundering herd problem* tetap dapat menciptakan duplicate dynamic types ke dalam CLR runtime memory.
3. Desain arsitektur isolasi baru menggunakan collectible `AssemblyLoadContext` yang thread-safe, mendukung *schema un-loading*, dan mencegah metadata footprint saturation.

---

### Skenario C: Architectural Shift: Runtime Proxy vs. Compile-Time Metaprogramming
*Konteks:* Tim Core Banking sedang melakukan migrasi core microservice dari .NET Framework 4.8 monolit ke .NET 9 Containerized Microservices yang ditargetkan berjalan di AWS Graviton (ARM64) dengan runtime mode **Native AOT**, dengan requirement batas startup time < 40ms.

Codebase lama memiliki ketergantungan masif pada:
1. Autofac/Castle Windsor dengan runtime dynamic proxy (`Castle.DynamicProxy`) untuk implementasi *Cross-Cutting Concerns* (AOP: Logging, Transaction Management, Circuit Breaker).
2. AutoMapper berbasis dynamic reflection mapping.
3. Runtime dynamic WCF client communication.

*Pertanyaan Diagnostik & Solusi:*
1. Jelaskan batasan teknis level mesin (*instruction generation*) mengapa `Castle.DynamicProxy` secara mutlak *gagal total* dijalankan di Native AOT (.NET 9).
2. Buat matriks komparasi arsitektural untuk menggantikan 3 komponen legacy di atas dengan paradigma compile-time metaprogramming berbasis Roslyn Source Generators.
3. Bagaimana Anda mendesain framework AOP (Aspect-Oriented Programming) modern yang Native-AOT compliant tanpa runtime dynamic proxy sama sekali?

---

## 4. Chapter Challenge

### Tantangan Praktis: Zero-Allocation Compile-Time Binary Pack Generator menggunakan Roslyn IIncrementalGenerator

#### Problem Statement
Dalam arsitektur High-Frequency Trading (HFT) atau Real-Time Game Server, network serialization harus deterministik, *zero-heap allocation*, tanpa parsing reflection pada runtime, dan kompatibel dengan Native AOT. Anda diminta untuk membuat package compile-time code generator yang memetakan struct C# ke serialisasi biner *fixed-layout* secara otomatis.

#### Requirements
1. **Roslyn Source Generator Core:**
   * Implementasikan class generator menggunakan interface `IIncrementalGenerator`.
   * Generator harus mendeteksi struct yang didekorasi dengan custom attribute `[BinaryPackable]`.
   * Generator membaca field atau property yang ditandai dengan `[BinaryMember(int order)]`.
2. **Deterministic Output:**
   * Generator memproduksi partial class/struct yang mengimplementasikan interface kontraktual:
     ```csharp
     public interface IBinaryBlit<T>
     {
         static abstract int BinarySize { get; }
         static abstract void Serialize(in T value, Span<byte> destination);
         static abstract T Deserialize(ReadOnlySpan<byte> source);
     }
     ```
3. **Pipeline Efficiency (Roslyn Performance Standard):**
   * Gunakan `context.SyntaxProvider.CreateSyntaxProvider` dengan pre-filtering sintaks yang efisien (hanya struct dengan attribute list).
   * Model data antara (*intermediate model*) yang dilempar dari tahap ekstraksi sintaks ke komparasi kode **wajib** bertipe immutable POCO Record yang mengimplementasikan `IEquatable<T>` secara penuh. Dilarang meneruskan `ISymbol` atau `SyntaxNode` ke fase `.RegisterSourceOutput`.
4. **Constraints:**
   * **Zero Runtime Allocation:** Implementasi `Serialize` dan `Deserialize` tidak boleh mengalokasikan heap memory sama sekali ($0$ bytes allocated di Gen 0/1/2).
   * Gunakan manipulasi primitive via `System.Buffers.Binary.BinaryPrimitives` (little-endian explicit serialization).
   * Wajib memvalidasi buffer bounds; jika `destination.Length < BinarySize`, lemparkan exception yang deterministik.
   * Wajib memancarkan *Roslyn Diagnostic Error* (peringatan kompilasi) jika developer menandai tipe data class (reference type) dengan attribute `[BinaryPackable]`.

#### Input Data Struct Target
```csharp
[BinaryPackable]
public partial struct OrderBookEntry
{
    [BinaryMember(1)]
    public long OrderId;

    [BinaryMember(2)]
    public double Price;

    [BinaryMember(3)]
    public int Quantity;

    [BinaryMember(4)]
    public byte Side; // 1 = Buy, 2 = Sell
}
```

#### Expected Output Source Generator
File hasil generate (`OrderBookEntry.BinaryPack.g.cs`):
```csharp
// <auto-generated/>
#nullable enable
using System;
using System.Buffers.Binary;

public partial struct OrderBookEntry : IBinaryBlit<OrderBookEntry>
{
    public static int BinarySize => sizeof(long) + sizeof(double) + sizeof(int) + sizeof(byte); // 21 bytes

    public static void Serialize(in OrderBookEntry value, Span<byte> destination)
    {
        if (destination.Length < BinarySize)
        {
            throw new ArgumentOutOfRangeException(nameof(destination), "Destination span is too small.");
        }

        BinaryPrimitives.WriteInt64LittleEndian(destination.Slice(0, 8), value.OrderId);
        BinaryPrimitives.WriteDoubleLittleEndian(destination.Slice(8, 8), value.Price);
        BinaryPrimitives.WriteInt32LittleEndian(destination.Slice(16, 4), value.Quantity);
        destination[20] = value.Side;
    }

    public static OrderBookEntry Deserialize(ReadOnlySpan<byte> source)
    {
        if (source.Length < BinarySize)
        {
            throw new ArgumentOutOfRangeException(nameof(source), "Source span is too small.");
        }

        OrderBookEntry result = default;
        result.OrderId = BinaryPrimitives.ReadInt64LittleEndian(source.Slice(0, 8));
        result.Price = BinaryPrimitives.ReadDoubleLittleEndian(source.Slice(8, 8));
        result.Quantity = BinaryPrimitives.ReadInt32LittleEndian(source.Slice(16, 4));
        result.Side = source[20];
        return result;
    }
}
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal runtime CLR dalam merepresentasikan metadata: perbedaan mendasar antara `MethodTable`, `EEClass`, `RuntimeTypeHandle`, dan metadata token heap.
- [ ] Cost breakdown dari Reflection klasik: boxing overhead, array allocation pada parameter reflection, string lookup table degradation, dan inhibisi terhadap JIT inlining.
- [ ] Alternatif performant terhadap reflection: compiled open delegates, `Expression.Compile()`, dynamic emission via `DynamicMethod`, dan modern zero-overhead primitive access via `[UnsafeAccessor]` (.NET 8+).
- [ ] Life-cycle dan arsitektur Roslyn Compiler: Syntax Tree, Semantic Model, Symbol Resolution, Compilation phases, dan Emit phase.
- [ ] Perbedaan fundamental antara `ISourceGenerator` dan `IIncrementalGenerator`, serta bahaya caching failure terhadap IDE performance.
- [ ] Keterbatasan Native AOT terhadap runtime dynamic code generation (JIT-free execution environment) dan peran krusial Source Generator dalam transisi Native AOT.
- [ ] Siklus hidup managed/unmanaged memory pada collectible `AssemblyLoadContext` dan mitigasi metadata memory leaks.

### Saya tidak perlu menghafal:
- [ ] Penomoran opcode IL mentah (misalnya: `0x72` untuk `ldstr` atau `0x28` untuk `call`) secara manual tanpa bantuan compiler/decompilation tools.
- [ ] Hierarki menyeluruh ratusan kelas turunan dari `CSharpSyntaxNode` di dalam Roslyn SDK (gunakan Syntax Visualizer pada IDE).
- [ ] Tabel parsing signature byte biner internal metadata ECMA-335 secara mendetail.

### Saya harus bisa melakukan:
- [ ] Membangun dynamic pipeline kompilasi menggunakan `IIncrementalGenerator` dari scratch dengan custom Roslyn Analyzer/Generator project setup.
- [ ] Mengimplementasikan *structural caching* yang benar menggunakan immutable POCO state records dan custom `IEqualityComparer<T>` di dalam pipeline source generator.
- [ ] Menulis tes integrasi dan unit test kompilasi Roslyn menggunakan framework pengujian syntax generator (`CSharpGeneratorDriver.RunGeneratorsAndUpdateCompilation`).
- [ ] Memprofil performa metaprogramming dan alokasi memori menggunakan **BenchmarkDotNet** (analisis Gen 0/1/2 Allocations dan CPU cycles per invocation).
- [ ] Mendiagnosa zombie metadata leaks pada AssemblyLoadContext menggunakan `dotnet-dump analyze`, menemukan reference roots via `!gcroot`, dan mengevaluasi memory footprint.