# Bab 06 Module 01: Metaprogramming, Reflection & Roslyn Source Generators

---

## SEKSI 01 — IDENTITAS MODUL

*   **Kode Modul:** CS-ADV-06-01
*   **Nama Modul:** Metaprogramming, Reflection & Roslyn Source Generators
*   **Kategori:** 02-Programming-Languages / C# Advanced Runtime & Compiler Internals
*   **Tingkat Kesulitan:** Advanced / Expert
*   **Prasyarat:** 
    *   Penguasaan C# intermediate-to-advanced (Generics, Delegates, IL fundamentals).
    *   Pemahaman siklus hidup kompilasi .NET (Roslyn, MSIL, JIT, CLR Execution).
    *   Pemahaman alokasi memori managed (.NET Heap, Stack, Boxing/Unboxing).
*   **Target Runtime:** .NET 8.0 / .NET 9.0 (C# 12 / C# 13)
*   **Relevansi Industri:** Perancangan library performa tinggi, framework injeksi dependensi, serialisasi zero-allocation, serta kepatuhan penuh terhadap Native AOT (*Ahead-Of-Time*) dan trimming.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis (Analyze):** Mengurai struktur metadata CLR (*Common Language Runtime*), *MethodTable*, dan *EEClass* untuk memprediksi overhead performa dari pemanggilan *Reflection* dinamis.
2.  **Mengevaluasi (Evaluate):** Menimbang komparasi trade-off arsitektural antara Runtime Metaprogramming (*Reflection*, *Expression Trees*, *Reflection.Emit*) dan Compile-time Metaprogramming (*Roslyn Source Generators*) berdasarkan metrik latensi, alokasi memori, throughput, dan kompatibilitas Native AOT.
3.  **Mendesain (Design):** Merancang *pipeline* generator kode berbasis Roslyn `IIncrementalGenerator` yang mematuhi paradigma *pure caching*, mencegah *memory leak* pada IDE/compiler, dan memvalidasi sintaks secara deterministik.
4.  **Mengimplementasikan (Create):** Membangun *zero-allocation object mapper* fungsional level produksi menggunakan Roslyn incremental pipeline dan integrasi *Diagnostic Analyzer*.
5.  **Memitigasi (Mitigate):** Mendeteksi serta merekayasa mitigasi terhadap *pitfalls* Roslyn incremental caching, *assembly load context leaks*, dan kerentanan *arbitrary code injection* pada evaluasi dinamis.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Runtime Inspection vs Compile-Time Code Synthesis

Dalam rekayasa perangkat lunak modern dengan C#, kode yang Anda tulis tidak lagi sekadar sekumpulan instruksi statis untuk memanipulasi data; kode Anda adalah entitas data itu sendiri (*code-as-data*).

```
[PARADIGMA KLASIK (Runtime Metaprogramming)]
Code -> Compiler -> IL Metadata -> Runtime -> CLR Reflection API -> JIT Dynamic Execution
(Kelemahan: Late binding, boxing overhead, overhead lookup metadata, Native AOT blocker)

[PARADIGMA MODERN (Compile-Time Metaprogramming)]
Code -> Roslyn Syntax Parser -> AST / Semantic Analysis -> Source Generator -> Synthesized Code -> Native Comp / AOT
(Keunggulan: Zero runtime cost, compile-time type safety, fully trimmable, 100% Native AOT compliant)
```

Mental model yang harus ditanamkan:
1.  **Metadata adalah Tabel Basis Data Statis:** Di dalam CLR (ECMA-335), metadata assembly adalah sekumpulan tabel relasional terindeks (*TypeDef*, *MethodDef*, *Param*, *CustomAttribute*). Melakukan *Reflection* tradisional identik dengan mengeksekusi *sequential scan query* pada tabel-tabel tersebut di runtime.
2.  **Pergeseran ke Kiri (*Shift-Left Execution*):** Sebisa mungkin, setiap operasi komputasi metadata harus ditarik dari *runtime* ke fase *compile-time*. Jika bentuk objek, relasi pemetaan (*mapping*), atau injeksi dependensi dapat diprediksi saat kompilasi, jangan pernah bayar biayanya di runtime.
3.  **Roslyn Generator adalah Pure Function Pipeline:** Arsitektur *Incremental Generator* Roslyn beroperasi layaknya mesin pemrosesan data fungsional (*functional reactive stream*). Masukan dari AST (*Abstract Syntax Tree*) harus ditransformasikan menjadi bentuk *model data immutable* yang mengimplementasikan *value equality* (`IEquatable<T>`). Kegagalan mempertahankan immutabilitas model akan mematikan *incremental caching* Roslyn, memperlambat kinerja compiler, dan melumpuhkan *developer experience* di IDE Visual Studio / Rider.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram 1: Alur Pemanggilan Metode Runtime (Reflection vs Delegate vs Direct)

Diagram di bawah mengilustrasikan traversal pointer internal CLR saat memanggil metode:

```
[Direct Call]
Caller ---> JIT-Compiled Native Code ---> Direct CPU Instruction (CALL/JMP)

[Dynamic Delegate via Expression Tree]
Caller ---> Delegate Invoke ---> MethodTable Trampoline ---> Direct Native Code

[System.Reflection (MethodInfo.Invoke)]
Caller
  │
  ▼
[Validation Layer] (Security checks, parameter type checking, array checks)
  │
  ▼
[Boxing/Unboxing Engine] (Allocates object[] on Heap for args & value types)
  │
  ▼
[RuntimeMethodHandle] (Extract MethodTable via TypeDef/MethodDef RID)
  │
  ▼
[EEClass / MethodDesc Lookup]
  │
  ▼
[Invoke Stub Execution]
  │
  ▼
Target Method Native Body
```

### Diagram 2: Roslyn Incremental Source Generator Architecture Pipeline

Arsitektur generator berbasis Roslyn modern (`IIncrementalGenerator`) bekerja menggunakan model *push-based execution with caching stages*:

```
   ┌────────────────────────────────────────────────────────┐
   │                   C# Source Code                       │
   └───────────────────────────┬────────────────────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │     Roslyn Syntax Pipeline    │
               │   (SyntaxTree & SemanticModel)│
               └───────────────┬───────────────┘
                               │
            Predicate Filter   │ SyntaxProvider.CreateSyntaxProvider()
                               ▼
               ┌───────────────────────────────┐
               │    Targeted Syntax Nodes      │ (e.g., Classes with [GenerateMapper])
               └───────────────┬───────────────┘
                               │
          Transform & Extract  │ Transform Node to Value-Equatable DTO
                               ▼
               ┌───────────────────────────────┐
               │   Equatable Generation Model  │ <--- Immutable Struct / Record
               └───────────────┬───────────────┘      (Checks IEquatable<T>)
                               │
                               ├──────────────────────┐
            [Cache Hit]        │                      │ [Cache Miss / Modified]
     (Model Values Identical)  │                      │
                               ▼                      ▼
                 ┌────────────────────────┐  ┌──────────────────────────────┐
                 │ Reuse Previous Emitted │  │ Execute Production Context   │
                 │      Output Stream     │  │ (Generate C# Source Code)    │
                 └────────────────────────┘  └──────────────┬───────────────┘
                                                            │
                                                            ▼
                                             ┌──────────────────────────────┐
                                             │ AddSource() to Compilation   │
                                             └──────────────┬───────────────┘
                                                            │
                                                            ▼
                                             ┌──────────────────────────────┐
                                             │ Final Binary Compilation     │
                                             │ (.dll / Native AOT Executable)
                                             └──────────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Metadata CLR & Reflection Plumbing
Di bawah naungan standar ECMA-335, setiap *Assembly* .NET terstruktur atas *Manifest Metadata*, *Metadata Tables*, dan *IL Bytecode Stream*.
*   **Metadata Tokens:** Integer 4-byte yang merujuk pada baris tabel tertentu. Byte teratas menandakan tipe tabel (misal `0x02` mewakili `TypeDef`, `0x06` mewakili `MethodDef`), dan 3 byte sisanya merupakan *Row Identifier* (RID).
*   **MethodTable & EEClass:** 
    *   Setiap tipe objek teralokasi memegang pointer tersembunyi berukuran 1 pointer CPU (*IntPtr.Size*: 8 byte pada x64) menuju `MethodTable`.
    *   `MethodTable` menampung pointer slot tabel virtual (V-Table), referensi ke *interface map*, dan pointer menuju struktur internal CLR bernama `EEClass` (Execution Engine Class).
    *   `EEClass` memuat informasi yang jarang diakses saat eksekusi normal, seperti layout field mentah, atribut, dan representasi string metadata.
*   **Anatomi Overhead `MethodInfo.Invoke()`:**
    1.  *Argument Wrapping:* Parameter dikemas ke dalam `object[]`. Setiap *primitive* atau *struct* mengalami *heap boxing*.
    2.  *Verification Barrier:* Runtime memeriksa hak akses (`BindingFlags.NonPublic`, target *ref/out*, visibility rules).
    3.  *Signature Unpacking:* Target membongkar `object[]`, memvalidasi kompatibilitas tipe ke parameter CLR sesungguhnya.
    4.  *PInvoke/Stub Transition:* Eksekusi dialihkan via stub jembatan runtime sebelum melompat ke native instruction code.

### 2. Expression Trees & `Reflection.Emit`
*   **System.Linq.Expressions:** Menyediakan kompilasi runtime terabstraksi. Membangun representasi pohon sintaks berbasis node (`BinaryExpression`, `MethodCallExpression`), lalu mengeksekusi method `.Compile()`. Di balik layar, `.Compile()` membangkitkan `DynamicMethod` melalui subsystem `System.Reflection.Emit`.
*   **DynamicMethod & JIT Hooks:** Menghasilkan instruksi IL langsung ke memori melalui `ILGenerator`. Metode ini tidak terasosiasi permanen dengan tipe metadata manapun, memotong seluruh overhead verifikasi metadata CLR dan dapat langsung dikompilasi oleh JIT menjadi instruksi mesin native.

### 3. Roslyn Incremental Pipeline Internals
*   `IncrementalValueProvider<T>`: Node pipeline reaktif. Melacak perubahan node secara bertahap.
*   `IncrementalGeneratorInitializationContext`: Titik masuk registrasi generator.
*   **Aturan Desain Immutable:** Roslyn compiler daemon (khususnya di IDE) mengeksekusi pipeline parsing pada setiap penekanan tombol (*keystroke*). Agar kompilator tidak meregenerasi kode berulang-ulang:
    *   Setiap transformasi syntax-to-model **dilarang keras** memegang referensi ke `SyntaxNode`, `SemanticModel`, atau `Compilation`. Objek-objek ini menyimpan referensi ke seluruh pohon sintaks. Menyimpannya akan menyebabkan memori membengkak (memory leak) dan membuat perbandingan equality selalu bernilai *false*.
    *   Pipeline transformasi harus menghasilkan objek data sederhana (*Plain Old C# Object/Struct*) yang mengimplementasikan `IEquatable<T>`. Generator hanya dieksekusi jika data equality model tersebut berubah (*Cache Miss*).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Evolusi Metaprogramming C#

Tuntutan arsitektur perangkat lunak telah mendorong evolusi metaprogramming C# melalui 4 generasi utama:

```
Generasi 1 (.NET Framework 1.0 - 3.5): Reflection Klasik
 - Inspeksi berbasis string dan System.Type.
 - Dynamic invocation sangat lambat.
 - Debugging metadata sulit dilacak secara statis.

Generasi 2 (.NET Framework 3.5 - 4.5): Expression Trees & IL Emit
 - Kemampuan sintesis delegasi di runtime (Expression.Compile()).
 - Mendekati kecepatan native execution.
 - Sangat rumit dalam pemeliharaan kode (harus menulis IL manual jika Emit).

Generasi 3 (.NET Core 3.1 - .NET 5): Roslyn ISourceGenerator (V1)
 - Pergeseran ke waktu kompilasi.
 - Masalah performa besar: Generator dieksekusi penuh pada setiap perubahan kecil di IDE.

Generasi 4 (.NET 6 - .NET 9): IIncrementalGenerator (V2) & Native AOT
 - Berbasis fine-grained caching engine.
 - Kompatibilitas 100% dengan Native Ahead-of-Time (AOT).
 - Tidak ada dependensi IL Emit di runtime, trimmable, dan aman untuk sistem tertutup (iOS, WebAssembly, Console gaming).
```

### Native AOT dan Dampaknya Terhadap Metaprogramming

Pada kompilasi Native AOT (*Ahead-Of-Time*):
1.  **Trimming (Tree-Shaking):** IL Linker (`ILLink`) memangkas metadata, kelas, metode, dan field yang tidak dipanggil secara eksplisit dalam kode program statis.
2.  **Ketiadaan JIT Engine:** Pada target runtime tertentu, JIT compiler dinonaktifkan sepenuhnya. Pemanggilan `DynamicMethod.Compile()` atau `AssemblyBuilder.DefineDynamicAssembly()` akan melemparkan runtime exception: `PlatformNotSupportedException`.
3.  **Kebutuhan Roslyn Source Generators:** Source Generators adalah solusi arsitektural mutlak untuk Native AOT. Karena kode dihasilkan sebelum kompilasi IL dan native compilation berlangsung, kode yang dihasilkan bersifat sepenuhnya eksplisit dan dapat dianalisis serta dioptimalkan oleh linker Native AOT.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi 3 pendekatan metaprogramming dalam C#:
1.  **Reflection Tradisional (Runtime)**
2.  **Compiled Expression Tree (High-Speed Dynamic Runtime Delegate)**
3.  **Roslyn Source Generator (Compile-Time Synthesis Pipeline Skeleton)**

### File: `RuntimeMetaprogrammingDemo.cs`

```csharp
using System;
using System.Linq.Expressions;
using System.Reflection;

namespace Metaprogramming.Fundamentals;

public sealed class TargetEntity
{
    private int _secretId = 42;
    public string Name { get; set; } = "Enterprise Core";

    private double ComputeFactor(double multiplier)
    {
        return _secretId * multiplier;
    }
}

public static class ReflectionAndExpressionDemo
{
    // 1. Classic Reflection Invocation
    public static object? ExecuteViaReflection(TargetEntity instance, double multiplier)
    {
        Type type = typeof(TargetEntity);
        MethodInfo? method = type.GetMethod("ComputeFactor", 
            BindingFlags.NonPublic | BindingFlags.Instance);

        if (method is null)
            throw new MissingMethodException(nameof(TargetEntity), "ComputeFactor");

        // Dynamic dispatch, boxing multiplier ke heap, packaging object[]
        return method.Invoke(instance, new object[] { multiplier });
    }

    // 2. High-Performance Expression Tree Compiled Delegate
    public static Func<TargetEntity, double, double> CreateCompiledDelegate()
    {
        ParameterExpression instanceParam = Expression.Parameter(typeof(TargetEntity), "instance");
        ParameterExpression multiplierParam = Expression.Parameter(typeof(double), "multiplier");

        MethodInfo? method = typeof(TargetEntity).GetMethod("ComputeFactor", 
            BindingFlags.NonPublic | BindingFlags.Instance);

        if (method is null)
            throw new MissingMethodException(nameof(TargetEntity), "ComputeFactor");

        // Membentuk AST Node: instance.ComputeFactor(multiplier)
        MethodCallExpression methodCall = Expression.Call(instanceParam, method, multiplierParam);

        // Kompilasi Lambda AST menjadi native invokable delegate via JIT Emit
        Expression<Func<TargetEntity, double, double>> lambda = 
            Expression.Lambda<Func<TargetEntity, double, double>>(methodCall, instanceParam, multiplierParam);

        return lambda.Compile();
    }
}
```

### File: `SampleIncrementalGenerator.cs` (Kerangka Roslyn Incremental Generator)

```csharp
using System;
using System.Text;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.Text;

namespace Metaprogramming.Generators;

[Generator]
public sealed class MinimalIncrementalGenerator : IIncrementalGenerator
{
    public void Initialize(IncrementalGeneratorInitializationContext context)
    {
        // Tahap 1: Sintaks filter cepat (Syntactic Predicate)
        IncrementalValuesProvider<ClassDeclarationSyntax> classDeclarations = context.SyntaxProvider
            .CreateSyntaxProvider(
                predicate: static (s, _) => s is ClassDeclarationSyntax { AttributeLists.Count: > 0 },
                transform: static (ctx, _) => (ClassDeclarationSyntax)ctx.Node
            );

        // Tahap 2: Transformasi ke model Equatable murni & ekstraksi semantik
        IncrementalValuesProvider<string> typeNames = classDeclarations
            .Select(static (classDecl, cancellationToken) =>
            {
                // Ambil data minimal yang bernilai value-equality (string)
                return classDecl.Identifier.Text;
            });

        // Tahap 3: Pendaftaran eksekusi produksi kode
        context.RegisterSourceOutput(typeNames, static (productionContext, className) =>
        {
            string source = $$"""
            // <auto-generated/>
            #nullable enable
            namespace Metaprogramming.Generated
            {
                public static class {{className}}Extensions
                {
                    public static string GetMetadataName() => "{{className}}";
                }
            }
            """;

            productionContext.AddSource($"{className}_Extensions.g.cs", SourceText.From(source, Encoding.UTF8));
        });
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Runtime Metaprogramming (`RuntimeMetaprogrammingDemo.cs`)
*   `type.GetMethod("ComputeFactor", BindingFlags.NonPublic | BindingFlags.Instance);`:
    Runtime mengeksekusi traversal pada struktur metadata *MethodDef* dari assembly internal CLR untuk mencari string matching `"ComputeFactor"`. Ini adalah operasi O(N) linier terhadap jumlah metode dalam type jika tidak terindeks oleh hash table internal runtime.
*   `method.Invoke(instance, new object[] { multiplier });`:
    1. Runtime mengalokasikan array baru `new object[1]` di managed heap.
    2. Variabel nilai primitif `multiplier` bertipe `double` (value type, 8 byte) di-boxing, menyalin nilainya ke object wrapper baru di heap.
    3. CLR beralih dari managed stack execution normal ke internal unmanaged invoker bridge.
*   `Expression.Call(...)` dan `lambda.Compile()`:
    1. Membangun model simbolik ekspresi pemanggilan di memori.
    2. `.Compile()` memicu engine `System.Reflection.Emit.DynamicMethod` untuk mengonversi AST menjadi stream opcode IL CLR langsung (`ldarg.0`, `ldarg.1`, `callvirt`, `ret`).
    3. Setelah dikompilasi, delegasi yang disimpan dapat dipanggil berulang kali dengan kecepatan setara *direct virtual call*, meniadakan alokasi heap `object[]` dan boxing.

### Analisis Roslyn Source Generator (`SampleIncrementalGenerator.cs`)
*   `[Generator]`: Menandai kelas implementor `IIncrementalGenerator` agar Roslyn compiler runtime mengenali assembly ini sebagai penganalisis dan penyintesis kode aktif saat proses build.
*   `predicate: static (s, _) => s is ClassDeclarationSyntax { AttributeLists.Count: > 0 }`:
    Fungsi predikat sintaks dieksekusi secara agresif pada setiap *keystroke* pengguna. Karena bersifat murni inspeksi node (`is ClassDeclarationSyntax`), evaluasinya sangat cepat (dalam fraksi mikrodetik). Penggunaan keyword `static` memastikan tidak ada closure allocation yang terjadi.
*   `transform: static (ctx, _) => ...`:
    Mengonversi `GeneratorSyntaxContext` menjadi data model yang dibutuhkan.
*   `context.RegisterSourceOutput(...)`:
    Hanya dijalankan apabila hasil output dari tahapan sebelumnya mengalami perubahan (berdasarkan evaluasi `EqualityComparer<T>.Default`).
*   `productionContext.AddSource(...)`:
    Menyuntikkan representasi `SourceText` baru langsung ke pipeline kompilasi Roslyn tanpa menyentuh disk fisik (hanya ada di memori compiler), kecuali opsi kompilator spesifik diaktifkan.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: High-Throughput Ultra-Low-Latency Financial DTO Mapper

Sebuah sistem transaksi pembayaran keuangan memproses **50.000 transaksi per detik**. Layanan ini mengonsumsi payload RPC internal dan mentransformasikannya menjadi domain model keuangan.

*   **Masalah Nyata:** 
    Penggunaan library mapper berbasis runtime reflection konvensional menghasilkan alokasi memori yang masif akibat lookup atribut dan boxing tipe nilai (`decimal`, `Guid`, `long`). Hal ini memicu jeda berkala dari GC (*Garbage Collection*) Stop-The-World (Gen 0 & Gen 1 GC spikes), menyebabkan *latency tail* (P99.9) menembus batas SLA (>150ms). Selain itu, sistem sedang dimigrasikan menuju **Native AOT** di Linux container untuk memangkas *memory footprint* dari 500MB ke 35MB per instance. Penggunaan runtime mapper menyebabkan container mengalami crash saat startup karena metode dinamis dipangkas oleh trimming.
*   **Solusi Desain:**
    Membangun Roslyn Incremental Source Generator kustom yang:
    1.  Mendeteksi kelas/struct yang didekorasi oleh atribut `[GenerateCustomMapper(typeof(Target))]`.
    2.  Menyintesis kode C# murni pemetaan antar properti pada fase kompilasi secara instan (*strongly typed assignments*).
    3.  Mendukung pemetaan properti dengan zero allocation dan kompatibel 100% dengan Native AOT.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Implementasi terdiri dari 2 proyek:
1.  `PaymentMapper.Generators` (Roslyn Source Generator Project).
2.  `PaymentService.App` (Aplikasi Konsumen).

### File: `PaymentMapper.Generators/MapperGenerator.cs`

```csharp
using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.Linq;
using System.Text;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.Text;

namespace PaymentMapper.Generators;

// Model Equatable murni untuk caching Roslyn
public readonly record struct PropertyMappingModel(string SourcePropertyName, string TargetPropertyName);

public readonly record struct MapperDescriptor(
    string Namespace,
    string SourceTypeName,
    string TargetTypeName,
    EquatableArray<PropertyMappingModel> Properties) : IEquatable<MapperDescriptor>;

// Wrapper list untuk menjamin immutability & equality comparison yang benar
public readonly struct EquatableArray<T> : IEquatable<EquatableArray<T>> where T : IEquatable<T>
{
    private readonly T[]? _items;
    public EquatableArray(T[] items) => _items = items;
    public T[] Items => _items ?? Array.Empty<T>();

    public bool Equals(EquatableArray<T> other)
    {
        if (_items is null && other._items is null) return true;
        if (_items is null || other._items is null) return false;
        if (_items.Length != other._items.Length) return false;
        for (int i = 0; i < _items.Length; i++)
        {
            if (!_items[i].Equals(other._items[i])) return false;
        }
        return true;
    }

    public override bool Equals(object? obj) => obj is EquatableArray<T> other && Equals(other);
    public override int GetHashCode()
    {
        if (_items is null) return 0;
        int hash = 17;
        foreach (var item in _items) hash = hash * 31 + item.GetHashCode();
        return hash;
    }
}

[Generator]
public sealed class HighPerformanceMapperGenerator : IIncrementalGenerator
{
    private const string AttributeNamespace = "PaymentService.Domain.Attributes";
    private const string AttributeName = "GenerateMapperAttribute";

    public void Initialize(IncrementalGeneratorInitializationContext context)
    {
        // 1. Ekstraksi sintaksis kandidat tipe yang memiliki atribut
        IncrementalValuesProvider<ClassDeclarationSyntax> candidateClasses = context.SyntaxProvider
            .CreateSyntaxProvider(
                predicate: static (node, _) => node is ClassDeclarationSyntax { AttributeLists.Count: > 0 },
                transform: static (ctx, _) => (ClassDeclarationSyntax)ctx.Node
            );

        // 2. Gabungkan dengan SemanticModel untuk filter ketat simbol dan ekstraksi data model
        IncrementalValuesProvider<MapperDescriptor?> mapperDescriptors = candidateClasses
            .Combine(context.CompilationProvider)
            .Select(static (combined, cancellationToken) =>
            {
                var (classSyntax, compilation) = combined;
                SemanticModel semanticModel = compilation.GetSemanticModel(classSyntax.SyntaxTree);
                
                if (semanticModel.GetDeclaredSymbol(classSyntax, cancellationToken) is not INamedTypeSymbol sourceSymbol)
                    return null;

                // Cari atribut GenerateMapperAttribute
                AttributeData? mapperAttribute = sourceSymbol.GetAttributes().FirstOrDefault(ad =>
                {
                    INamedTypeSymbol? attrClass = ad.AttributeClass;
                    return attrClass != null &&
                           attrClass.Name == AttributeName &&
                           attrClass.ContainingNamespace.ToDisplayString() == AttributeNamespace;
                });

                if (mapperAttribute is null || mapperAttribute.ConstructorArguments.Length == 0)
                    return null;

                // Tipe target pemetaan dari argumen konstruktor
                if (mapperAttribute.ConstructorArguments[0].Value is not INamedTypeSymbol targetSymbol)
                    return null;

                // Ambil daftar properti publik yang cocok antara source dan target
                var sourceProps = sourceSymbol.GetMembers().OfType<IPropertySymbol>()
                    .Where(p => p.GetMethod != null && p.DeclaredAccessibility == Accessibility.Public);

                var targetProps = targetSymbol.GetMembers().OfType<IPropertySymbol>()
                    .Where(p => p.SetMethod != null && p.DeclaredAccessibility == Accessibility.Public)
                    .ToDictionary(p => p.Name, StringComparer.Ordinal);

                List<PropertyMappingModel> mappings = new();
                foreach (var sProp in sourceProps)
                {
                    if (targetProps.TryGetValue(sProp.Name, out var tProp))
                    {
                        // Pastikan tipenya kompatibel
                        if (SymbolEqualityComparer.Default.Equals(sProp.Type, tProp.Type))
                        {
                            mappings.Add(new PropertyMappingModel(sProp.Name, tProp.Name));
                        }
                    }
                }

                string ns = sourceSymbol.ContainingNamespace.IsGlobalNamespace
                    ? "Global"
                    : sourceSymbol.ContainingNamespace.ToDisplayString();

                return new MapperDescriptor(
                    ns,
                    sourceSymbol.Name,
                    targetSymbol.ToDisplayString(SymbolDisplayFormat.FullyQualifiedFormat),
                    new EquatableArray<PropertyMappingModel>(mappings.ToArray())
                );
            })
            .Where(static descriptor => descriptor is not null);

        // 3. Emit Source Code
        context.RegisterSourceOutput(mapperDescriptors, static (spc, descriptor) =>
        {
            if (descriptor is null) return;

            MapperDescriptor model = descriptor.Value;
            StringBuilder sb = new();

            sb.AppendLine("// <auto-generated/>");
            sb.AppendLine("#nullable enable");
            sb.AppendLine("using System;");
            sb.AppendLine();
            sb.AppendLine($"namespace {model.Namespace}");
            sb.AppendLine("{");
            sb.AppendLine($"    public static class {model.SourceTypeName}MapperExtensions");
            sb.AppendLine("    {");
            sb.AppendLine($"        public static {model.TargetTypeName} MapToDomain(this {model.SourceTypeName} source)");
            sb.AppendLine("        {");
            sb.AppendLine("            if (source is null) throw new ArgumentNullException(nameof(source));");
            sb.AppendLine($"            return new {model.TargetTypeName}");
            sb.AppendLine("            {");

            foreach (var prop in model.Properties.Items)
            {
                sb.AppendLine($"                {prop.TargetPropertyName} = source.{prop.SourcePropertyName},");
            }

            sb.AppendLine("            };");
            sb.AppendLine("        }");
            sb.AppendLine("    }");
            sb.AppendLine("}");

            spc.AddSource($"{model.SourceTypeName}_To_DomainMapper.g.cs", SourceText.From(sb.ToString(), Encoding.UTF8));
        });
    }
}
```

### File: `PaymentService.App/Program.cs`

```csharp
using System;
using PaymentService.Domain.Attributes;

namespace PaymentService.Domain.Attributes
{
    [AttributeUsage(AttributeTargets.Class, AllowMultiple = false, Inherited = false)]
    public sealed class GenerateMapperAttribute : Attribute
    {
        public Type TargetType { get; }
        public GenerateMapperAttribute(Type targetType) => TargetType = targetType;
    }
}

namespace PaymentService.Domain.Entities
{
    public sealed class PaymentTransactionDomain
    {
        public Guid TransactionId { get; set; }
        public decimal Amount { get; set; }
        public string Currency { get; set; } = string.Empty;
        public long TimestampEpoch { get; set; }
    }
}

namespace PaymentService.App.Dtos
{
    [PaymentService.Domain.Attributes.GenerateMapper(typeof(PaymentService.Domain.Entities.PaymentTransactionDomain))]
    public sealed class PaymentTransactionDto
    {
        public Guid TransactionId { get; set; }
        public decimal Amount { get; set; }
        public string Currency { get; set; } = string.Empty;
        public long TimestampEpoch { get; set; }
    }

    public static class Program
    {
        public static void Main()
        {
            var dto = new PaymentTransactionDto
            {
                TransactionId = Guid.NewGuid(),
                Amount = 1450000.50m,
                Currency = "IDR",
                TimestampEpoch = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
            };

            // Pemanggilan extension method yang dihasilkan secara compile-time oleh Roslyn Generator
            var domainEntity = dto.MapToDomain();

            Console.WriteLine("Zero-Allocation Mapper Invoked Successfully!");
            Console.WriteLine($"Transaction ID: {domainEntity.TransactionId}");
            Console.WriteLine($"Amount: {domainEntity.Amount} {domainEntity.Currency}");
            Console.WriteLine($"Generated Assembly Target Type: {domainEntity.GetType().FullName}");
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Parameter Metrik | System.Reflection Klasik | Compiled Expression Tree | System.Reflection.Emit | Roslyn Incremental Generator |
| :--- | :--- | :--- | :--- | :--- |
| **Eksekusi Runtime** | Sangat Lambat (High Overhead) | Nyaris Setara Direct Call | Setara Direct Call | Setara Direct Call (Native JIT) |
| **Alokasi Heap (GC)** | Sangat Tinggi (Boxing + arrays) | Rendah / Nol | Nol (Bebas alokasi) | Nol (Bebas alokasi) |
| **Startup Latency** | Instan (Tidak ada kompilasi) | Lambat (Biaya JIT compilation AST) | Menengah-Lambat (IL generation) | Nol (Kompilasi dilakukan di build) |
| **Build Time** | Tidak berdampak | Tidak berdampak | Tidak berdampak | Bertambah (Proses parsing AST) |
| **Native AOT Trimming** | Rawan crash / Runtime breaks | Terbatas / Dilarang di platform no-JIT | **Gagal Total** (No runtime JIT) | **100% Kompatibel & Optimal** |
| **Debuggability** | Rumit (Stack trace terputus) | Sulit (IL virtual stubs) | Sangat Sulit (Raw OpCodes) | **Sangat Baik** (Kode .g.cs nyata) |
| **Type Safety** | Runtime exception | Runtime compilation exception | Runtime invalid IL crash | **Compile-Time Compile Error** |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1.  **Roslyn Incremental Cache Leak (The `SyntaxNode` Trap):**
    *   *Kondisi:* Anda menyimpan instance `SyntaxNode` atau `SemanticModel` di dalam pipeline descriptor yang diteruskan ke tahap generator output.
    *   *Dampak:* Objek ini mengikat referensi ke seluruh struktur AST lama. Saat pengembang mengetik di IDE, AST lama tidak dapat dibersihkan oleh GC (terjadi *memory leak* masif pada Visual Studio / Rider). Selain itu, equality check akan selalu menghasilkan *false*, mematikan caching inkremental sehingga performa IDE turun drastis.
    *   *Mitigasi:* Ekstraksi nilai tipe data primitif atau record struct yang murni mengimplementasikan `IEquatable<T>` pada fase pemodelan awal pipeline.
2.  **Tabrakan Namespace Global:**
    *   *Kondisi:* Proyek konsumen memiliki tipe kelas bernama sama dengan namespace sistem (misal user membuat kelas bernama `System` atau `Nullable`).
    *   *Mitigasi:* Selalu tambahkan prefix `global::` pada seluruh tipe referensi yang dihasilkan generator:
        ```csharp
        // Salah
        public System.Guid Id { get; set; }
        // Benar
        public global::System.Guid Id { get; set; }
        ```
3.  **Aksesibilitas Internal (`InternalsVisibleTo`):**
    *   *Kondisi:* Generator mencoba mengakses tipe data dengan visibilitas `internal` dari assembly lain.
    *   *Mitigasi:* Verifikasi apakah assembly target mendeklarasikan `[InternalsVisibleTo]`. Jika tidak, generator harus menolak menghasilkan metode publik yang membocorkan batasan aksesibilitas atau mengeluarkan *Diagnostic Error*.
4.  **Tipe Generik Terbuka (*Unbound Generic Types*):**
    *   *Kondisi:* Mengakses atau memetakan kelas seperti `Repository<T>` sebelum parameter tipe konkret disuplai.
    *   *Mitigasi:* Pada generator, gunakan `INamedTypeSymbol.IsGenericType` dan lakukan validasi apakah `TypeArguments` telah terikat sebelum memproduksi kode instansiasi langsung.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Dynamic Assembly Memory Leak pada Runtime Reflection.Emit

```csharp
// KODE SALAH:
// Mengompilasi Expression Tree berulang kali di dalam loop / per request
public void Process(PaymentDto dto)
{
    // FATAL: DynamicMethod dialokasikan ke memori unmanaged/executable pages setiap request!
    var mapper = Expression.Lambda<Func<PaymentDto, PaymentDomain>>(...).Compile();
    mapper(dto);
}

// KODE BENAR:
// Lakukan caching terhadap hasil kompilasi delegasi dalam static readonly field
public static class FastMapperCache
{
    public static readonly Func<PaymentDto, PaymentDomain> MapDelegate = 
        Expression.Lambda<Func<PaymentDto, PaymentDomain>>(...).Compile();
}
```

### 2. Melempar Eksepsi Tak Tertangani di dalam Roslyn Generator

```csharp
// KODE SALAH:
// Generator melempar unhandled exception saat parsing metadata tidak valid
if (targetSymbol == null)
    throw new InvalidOperationException("Symbol not found"); // Compiler/IDE akan crash!

// KODE BENAR:
// Laporkan melalui context.ReportDiagnostic() dan batalkan eksekusi pipeline secara graceful
if (targetSymbol == null)
{
    context.ReportDiagnostic(Diagnostic.Create(
        GeneratorDiagnostics.MissingSymbolRule, 
        classDeclarationSyntax.GetLocation(), 
        classDeclarationSyntax.Identifier.Text));
    return;
}
```

### 3. Loop Invocation Tanpa Cache `MethodInfo`

```csharp
// KODE SALAH:
for (int i = 0; i < 100_000; i++)
{
    // Sangat lambat: Mencari metadata table string matching 100.000 kali!
    var method = typeof(Worker).GetMethod("DoWork");
    method.Invoke(workerInstance, null);
}

// KODE BENAR:
MethodInfo method = typeof(Worker).GetMethod("DoWork")!;
for (int i = 0; i < 100_000; i++)
{
    method.Invoke(workerInstance, null);
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan File Extension `.g.cs`:**
    Setiap source yang disuntikkan via Roslyn harus diakhiri dengan akhiran `.g.cs` (misalnya: `PayloadDto_Mapper.g.cs`). Konvensi ini memberi petunjuk pada debugger, tool static analysis (SonarQube), dan git engine untuk mengecualikan file dari aturan manual linting.
2.  **Tambahkan Komentar Header Khusus:**
    Awali file yang disintesis dengan:
    ```csharp
    // <auto-generated/>
    #nullable enable
    #pragma warning disable CS1591 // Missing XML comment
    ```
3.  **Pasang Atribut Compiler:**
    Tempelkan atribut `[global::System.CodeDom.Compiler.GeneratedCode("GeneratorName", "Version")]` dan `[global::System.Diagnostics.DebuggerNonUserCode]` pada kelas atau metode yang dihasilkan agar debugger tidak melompat ke file hasil sintesis saat mode single-stepping (F11), kecuali diatur sebaliknya.
4.  **Isolasi Assembly Generator:**
    Assembly Roslyn Source Generator harus menargetkan `netstandard2.0` murni karena compiler Roslyn dijalankan di berbagai runtime host (Visual Studio menggunakan .NET Framework 4.7.2/Core runtime, sedangkan `dotnet build` CLI menggunakan runtime .NET terbaru).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Tolok Ukur Kinerja (BenchmarkDotNet Setup)

Berikut adalah harness benchmark untuk mengukur overhead mapping 1.000.000 objek DTO:

```csharp
using BenchmarkDotNet.Attributes;
using BenchmarkDotNet.Running;

[MemoryDiagnoser]
[ShortRunJob]
public class MappingBenchmark
{
    private PaymentTransactionDto _dto = null!;
    private Func<PaymentTransactionDto, PaymentTransactionDomain> _compiledExpr = null!;
    private System.Reflection.MethodInfo _reflectionMethod = null!;

    [GlobalSetup]
    public void Setup()
    {
        _dto = new PaymentTransactionDto { Amount = 100, Currency = "IDR" };
        _reflectionMethod = typeof(MappingBenchmark).GetMethod(nameof(ManualMap), 
            System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.Public)!;
        _compiledExpr = ReflectionAndExpressionDemo.CreateCompiledDelegate(); // Analogous
    }

    public static PaymentTransactionDomain ManualMap(PaymentTransactionDto s) =>
        new() { Amount = s.Amount, Currency = s.Currency };

    [Benchmark(Baseline = true)]
    public PaymentTransactionDomain DirectMethodCall() => ManualMap(_dto);

    [Benchmark]
    public PaymentTransactionDomain GeneratedSourceMapping() => _dto.MapToDomain();

    [Benchmark]
    public PaymentTransactionDomain CompiledExpressionTree() => _compiledExpr(_dto);

    [Benchmark]
    public object? ClassicReflectionInvoke() => _reflectionMethod.Invoke(null, new object[] { _dto });
}
```

### Proyeksi Hasil Komparasi Metrik

```
| Method                 | Mean         | Error     | StdDev    | Ratio   | Gen0   | Allocated |
|----------------------- |-------------:|----------:|----------:|--------:|-------:|----------:|
| DirectMethodCall       |     1.421 ns | 0.0210 ns | 0.0186 ns |    1.00 |      - |       0 B |
| GeneratedSourceMapping |     1.423 ns | 0.0195 ns | 0.0173 ns |    1.00 |      - |       0 B |
| CompiledExpressionTree |     2.894 ns | 0.0412 ns | 0.0365 ns |    2.04 |      - |       0 B |
| ClassicReflectionInvoke|   135.210 ns | 2.1054 ns | 1.8664 ns |   95.15 | 0.0076 |      32 B |
```

*Analisis Kinerja:*
*   **Generated Source:** Mencapai rasio performa murni `1.00` (identik dengan native method call) dan menghasilkan **0 Byte overhead alokasi**.
*   **Classic Reflection:** Hampir **100x lebih lambat** dengan alokasi heap 32 byte per invokasi akibat packing array `object[]` dan unboxing handling.

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Code Injection dalam Dynamic Synthesized Code:**
    *   Saat membuat string kode pada Source Generator, jangan pernah melakukan *untrusted string concatenation* dari komentar atau nama file tanpa sanitasi. Jika atribut menerima argumen string mentah (misal: default value), karakter seperti `"; System.Diagnostics.Process.Start("malicious"); //` dapat disuntikkan ke dalam file kompilasi.
    *   *Hardening:* Selalu gunakan escaping string literal Roslyn (`SymbolDisplay.FormatLiteral`) atau lakukan validasi token secara ketat sebelum merender string.
2.  **Arbitrary Dynamic Assembly Loading:**
    *   Penggunaan `Assembly.Load(byte[] rawAssembly)` pada runtime membuka pintu penyerang menyuntikkan IL bytecode berbahaya ke dalam batas keamanan CLR process.
    *   *Hardening:* Jika dynamic assembly loading diwajibkan, gunakan `AssemblyLoadContext` yang terisolasi dengan kemampuan pembongkaran (*collectible ALC*) dan batasi izin eksekusi menggunakan secure enclave.
3.  **Reflection Penetration ke Private Encapsulation:**
    *   Penggunaan Reflection untuk memodifikasi `private readonly` field dapat merusak invarian keamanan memori atau membocorkan data sensitif (misal `SecureString`, cryptographic key material).
    *   *Hardening:* Di .NET modern, modifikasi `readonly field` via reflection memicu peringatan runtime dan dinonaktifkan di runtime yang menggunakan strict mode. Selalu rancang boundary tanpa merusak enkapsulasi tipe internal runtime.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Cara Men-debug Roslyn Source Generator
Karena Source Generator dieksekusi di dalam proses compiler host (`csc.exe`, `devenv.exe`, atau `dotnet`), Anda tidak dapat menekan F5 secara langsung. Gunakan teknik peluncuran debugger otomatis:

```csharp
public void Initialize(IncrementalGeneratorInitializationContext context)
{
    #if DEBUG
    if (!System.Diagnostics.Debugger.IsAttached)
    {
        // Compiler akan memunculkan prompt sistem Windows/Linux untuk memilih IDE debugger
        System.Diagnostics.Debugger.Launch();
    }
    #endif
    // Pipeline initialization logic...
}
```

### 2. Memaksa Output File Tersimpan ke Disk Fisik
Untuk memeriksa source code yang dihasilkan compiler secara visual, tambahkan properti berikut di file `.csproj` proyek konsumen:

```xml
<PropertyGroup>
    <!-- Emit file yang disintesis ke dalam folder obj/GeneratedFiles -->
    <EmitCompilerGeneratedFiles>true</EmitCompilerGeneratedFiles>
    <CompilerGeneratedFilesOutputPath>$(BaseIntermediateOutputPath)\GeneratedFiles</CompilerGeneratedFilesOutputPath>
</PropertyGroup>
```

### 3. Diagnostic Reporting
Integrasikan umpan balik yang ramah pengguna langsung ke *Error List* visual compiler menggunakan `DiagnosticDescriptor`:

```csharp
private static readonly DiagnosticDescriptor PropertyTypeMismatchRule = new(
    id: "PAYMAP001",
    title: "Type Mismatch Between Source and Target Property",
    messageFormat: "Property '{0}' has type '{1}', which does not match target type '{2}'",
    category: "PaymentMapper.Usage",
    defaultSeverity: DiagnosticSeverity.Error,
    isEnabledByDefault: true);

// Di dalam pipeline generator:
context.ReportDiagnostic(Diagnostic.Create(
    PropertyTypeMismatchRule,
    propertySymbol.Locations.FirstOrDefault(),
    propertySymbol.Name,
    propertySymbol.Type.ToDisplayString(),
    targetProp.Type.ToDisplayString()));
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **System.Reflection:** Alat introspeksi runtime serbaguna. Gunakan **hanya** untuk tool diagnostik, CLI serialization internal yang tidak butuh performa tinggi, atau testing unit assertions. Hindari di loop produksi.
*   **Compiled Expression Trees:** Jembatan ideal untuk arsitektur legacy jika Anda membutuhkan kompilasi runtime dinamis yang jauh lebih cepat daripada reflection dan belum bisa menggunakan Roslyn Source Generators.
*   **Roslyn `IIncrementalGenerator`:** Standar modern C# untuk kompilasi zero-cost abstraction, high performance, dan Native AOT compatibility.
*   **Roslyn Caching Axiom:**
    *   Gunakan `static` predicate & transform functions.
    *   Hanya lewatkan data model *immutable* yang mengimplementasikan `IEquatable<T>`.
    *   **Dilarang keras** memegang referensi ke `SyntaxNode`, `SemanticModel`, atau `Compilation` di dalam step akhir output generator.
*   **Safety Prefix:** Selalu sertakan `global::` pada tipe data yang di-generate untuk mencegah *namespace collision attacks*.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1 - 5)

1.  **Mengapa pemanggilan metode via `MethodInfo.Invoke()` pada tipe struct primitif (misal: `int`) mengakibatkan alokasi pada managed heap?**
    *   A. Karena struct tidak memiliki `MethodTable`.
    *   B. Karena parameter harus di-boxing menjadi `object` dan dibungkus dalam array `object[]`.
    *   C. Karena CLR mengalokasikan stack baru setiap pemanggilan reflection.
    *   D. Karena struct selalu diubah menjadi class oleh JIT.

2.  **Apa fungsi dari prefix `global::` pada kode yang disintesis oleh Roslyn Source Generator?**
    *   A. Mempercepat eksekusi JIT compiler.
    *   B. Mengabaikan validasi sintaks compiler.
    *   C. Menjamin resolusi tipe merujuk pada namespace terluar, mencegah ambiguitas atau tabrakan nama lokal.
    *   D. Mengizinkan pemanggilan private members lintas assembly.

3.  **Kapan antarmuka `IIncrementalGenerator` lebih diunggulkan secara mutlak dibandingkan runtime `Reflection`?**
    *   A. Saat metadata hanya dapat diketahui informasinya saat program sedang menerima HTTP request.
    *   B. Saat target lingkungan eksekusi menargetkan Native AOT dan membutuhkan efisiensi memori nol alokasi.
    *   C. Saat ukuran output file binary harus dibuat sekecil mungkin tanpa kode C# tambahan.
    *   D. Saat kita tidak memiliki akses ke source code proyek pemanggil.

4.  **Apa yang terjadi jika exception yang tidak ditangani (*unhandled exception*) terlempar di dalam fungsi `Initialize` pada Roslyn Source Generator?**
    *   A. Build program berhasil, tetapi file generator dilewati.
    *   B. Compiler atau background process language server IDE (seperti Visual Studio / OmniSharp) dapat crash atau berhenti berfungsi.
    *   C. Kompiler otomatis beralih ke mode runtime reflection.
    *   D. Terjadi infinite compilation loop.

5.  **Peran utama dari `SourceProductionContext.AddSource()` adalah:**
    *   A. Menulis file `.cs` fisik langsung ke folder root project.
    *   B. Menyuntikkan representasi `SourceText` baru ke dalam memori kompilasi pipeline yang sedang aktif.
    *   C. Memodifikasi file `.cs` yang ada di disk secara in-place.
    *   D. Menjalankan proses build ulang seluruh solusi secara paralel.

---

### Soal Intermediate (6 - 10)

6.  **Mengapa menyimpan instance `ClassDeclarationSyntax` di dalam model data final dari `IncrementalValuesProvider` dianggap sebagai bad practice kritis?**
    *   A. Karena `ClassDeclarationSyntax` tidak dapat dikonversi menjadi string.
    *   B. Karena objek tersebut menahan referensi ke seluruh pohon sintaks (*full AST tree*), menyebabkan kebocoran memori (memory leak) pada proses host IDE dan mematahkan incremental caching engine.
    *   C. Karena compiler Roslyn otomatis melemparkan `AccessViolationException`.
    *   D. Karena `ClassDeclarationSyntax` adalah interface, bukan concrete class.

7.  **Di bawah standar ECMA-335, di mana pointer metode native disimpan dan diresolusi saat runtime pemanggilan virtual direct berlangsung?**
    *   A. Metadata Manifest Table RID `0x01`.
    *   B. V-Table slot di dalam struktur `MethodTable` tipe terkait.
    *   C. Managed Garbage Collector Free List.
    *   D. Assembly Dynamic Manifest Header.

8.  **Apa perbedaan mendasar antara `Expression.Compile()` dan implementasi Roslyn Incremental Generator dalam konteks target deployment Apple iOS atau WebAssembly AOT?**
    *   A. Keduanya sama-sama berhasil dieksekusi tanpa kendala.
    *   B. `Expression.Compile()` memicu pembuatan IL dinamis via `Reflection.Emit` yang dilarang/tidak didukung di lingkungan platform no-JIT, sedangkan Roslyn Generator sukses karena kode dihasilkan sebelum tahap native compilation.
    *   C. Roslyn Generator gagal karena tidak dapat membaca file fisik di iOS.
    *   D. `Expression.Compile()` otomatis dioptimalkan oleh Linker trimmer AOT.

9.  **Pada arsitektur `IIncrementalGenerator`, bagaimana compiler menentukan bahwa suatu output generator dari keystroke pengguna tidak perlu diregenerasi (*cache hit*)?**
    *   A. Berdasarkan timestamp terakhir file `.csproj` diubah.
    *   B. Membandingkan kesamaan referensi pointer memori objek model.
    *   C. Mengevaluasi metode `.Equals()` dan `GetHashCode()` (struktural `IEquatable<T>`) dari objek data model pada pipeline inkremental.
    *   D. Roslyn selalu meregenerasi seluruh kode tanpa memedulikan nilai model.

10. **Perhatikan cuplikan berikut:**
    ```csharp
    var method = typeof(Service).GetMethod("Run");
    var del = (Action)Delegate.CreateDelegate(typeof(Action), null, method);
    ```
    **Dibandingkan pemanggilan langsung `method.Invoke(null, null)`, pemanggilan delegasi `del()` memiliki karakteristik performa:**
    *   A. Sama persis karena keduanya tetap menggunakan `MethodInfo`.
    *   B. Jauh lebih cepat dan bebas alokasi karena overhead signature checks dan array parameters dipangkas saat pendaftaran delegasi (delegation binding stub).
    *   C. Jauh lebih lambat karena harus membuat wrapper `Delegate` baru.
    *   D. Melempar `InvalidCastException` di semua versi .NET.

---

### Kunci Jawaban & Rasional Singkat

1.  **Jawaban: B** — Signature `MethodInfo.Invoke(object, object[])` mewajibkan semua parameter dibungkus dalam array heap, dan tipe nilai (*struct/int*) wajib di-boxing ke dalam container tipe referensi objek.
2.  **Jawaban: C** — Prefix `global::` mengarahkan compiler untuk mulai mencari tipe langsung dari namespace terluar (akar), sehingga tidak terpengaruh jika ada kelas pengguna yang menggunakan nama bentrok (misal kelas bernama `System`).
3.  **Jawaban: B** — Pada Native AOT, Reflection dinamis rawan dipangkas oleh trimmer atau tidak dapat mengeksekusi stub runtime. Roslyn memproduksi source code murni saat fase kompilasi sehingga 100% aman untuk Native AOT dan minim alokasi.
4.  **Jawaban: B** — Generator berjalan langsung di thread kompilator host. Unhandled exception akan dianggap sebagai kegagalan fatal pada analyzer/compiler component yang membatalkan build dan berpotensi melumpuhkan language server IDE.
5.  **Jawaban: B** — `AddSource` bekerja secara virtual dalam memori pipeline compiler Roslyn. Ia tidak menulis ke disk fisik kecuali pengembang mengaktifkan properti `EmitCompilerGeneratedFiles`.
6.  **Jawaban: B** — `SyntaxNode` memegang referensi ke parent node hingga akar `SyntaxTree`. Menyimpannya di model pipeline akan mencegah garbage collection membersihkan pohon kompilasi sebelumnya dan merusak evaluasi kesetaraan (*equality comparison*).
7.  **Jawaban: B** — Direct call / dynamic virtual call diatur oleh V-Table slot di dalam `MethodTable` yang dipetakan oleh CLR saat tipe kelas dimuat ke dalam domain memori.
8.  **Jawaban: B** — Platform seperti iOS secara keras melarang pembuatan dan pengeksekusian halaman memori executable baru di runtime (JIT). `Expression.Compile()` mengandalkan IL Emit runtime sehingga akan memicu crash, sedangkan Roslyn Generator berjalan di mesin build developer.
9.  **Jawaban: C** — Roslyn menguji *value equality* terhadap output transformasi model perantara. Jika model mengimplementasikan `IEquatable<T>` dan nilainya sama persis dengan kalkulasi sebelumnya, tahap kompilasi berikutnya dilewati (*cached*).
10. **Jawaban: B** — `Delegate.CreateDelegate` mengikat pointer fungsi native metode secara langsung ke invocation stub delegasi. Biaya lookup tipe, verifikasi hak akses, dan packing array dihilangkan untuk pemanggilan-pemanggilan berikutnya.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: Compile-Time Zero-Allocation Binary Serializer Generator

#### Deskripsi
Buatlah sebuah Roslyn Incremental Source Generator lengkap yang secara otomatis membangkitkan metode serialisasi binary cepat (*fast zero-allocation binary serialization*) untuk struktur data keuangan beranotasi atribut `[BinarySerializable]`.

#### Spesifikasi Kebutuhan Teknis

1.  **Attribute Definition:**
    Definisikan atribut:
    ```csharp
    [AttributeUsage(AttributeTargets.Class | AttributeTargets.Struct)]
    public sealed class BinarySerializableAttribute : Attribute { }
    ```
2.  **Generator Pipeline:**
    *   Buat project class library `BinarySerializer.Generators` yang menargetkan `netstandard2.0` dan mereferensikan package `Microsoft.CodeAnalysis.CSharp` (versi minimal 4.8.0).
    *   Terapkan pattern `IIncrementalGenerator` dengan filter predikat sintaks yang efisien dan pipeline model equatable murni.
3.  **Output Code Synthesis:**
    Untuk setiap tipe yang didekorasi atribut tersebut, generator wajib menghasilkan extension method:
    ```csharp
    public static void SerializeTo(this in TargetType instance, global::System.Span<byte> destination, out int bytesWritten);
    ```
    *Metode serialisasi harus mendukung tipe properti primitif: `int`, `long`, `double`, dan `decimal`.*
    *Gunakan API `global::System.Buffers.Binary.BinaryPrimitives` untuk menulis data integer/long dengan deterministik endianness (Little Endian).*
4.  **Acceptance Criteria:**
    *   Kode hasil sintesis tidak boleh melakukan alokasi heap memori sekecil apa pun (`0 B Allocated` pada BenchmarkDotNet test).
    *   Generator harus menerbitkan *Diagnostic Warning* jika terdapat properti bertipe data selain primitif yang didukung.
    *   Proyek konsumen harus berhasil dikompilasi dengan instruksi `<PublishAot>true</PublishAot>` tanpa memunculkan trim warnings (`IL2026` / `IL2087`).
    *   IDE Visual Studio / JetBrains Rider tidak mengalami kelambatan input (*lagging*) saat file model yang diberi anotasi dimodifikasi.