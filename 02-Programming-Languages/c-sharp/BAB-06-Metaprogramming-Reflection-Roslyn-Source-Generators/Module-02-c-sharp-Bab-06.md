# BAB 06: Metaprogramming, Reflection, Roslyn & Source Generators
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengimplementasikan teknik metaprogramming tingkat lanjut menggunakan C# 12+ / .NET 8/9 dengan membandingkan *runtime code generation* (`Reflection.Emit`, `DynamicMethod`, `Expression Trees`) dan *compile-time generation* (`IIncrementalGenerator`).
- Merancang arsitektur pipeline Roslyn *Incremental Source Generator* yang deterministik, efisien terhadap memori IDE, dan mematuhi aturan strict *value-based caching*.
- Mengelola siklus hidup assembly secara dinamis menggunakan custom `AssemblyLoadContext` yang mendukung *dynamic plugin unloading* tanpa memory leak.
- Menghasilkan kode yang sepenuhnya kompatibel dengan *Native AOT (Ahead-of-Time)* dan *Trimming*, mengeliminasi *unbounded reflection* pada path performa kritis.
- Mengidentifikasi, mengukur, dan memitigasi overhead performa metaprogramming menggunakan BenchmarkDotNet dan memory profiler (dotMemory/PerfView).

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda harus menguasai:
- **CLR Internals Fundamental**: Pemahaman tentang Heap, Stack, MethodTable, EEType, SyncBlock, dan struktur JIT compilation.
- **IL (Intermediate Language)**: Familiaritas membaca dan menulis instruksi opcodes dasar IL (`ldarg`, `callvirt`, `ldfld`, `box`, `ret`).
- **Roslyn API Dasar**: Pemahaman dasar tentang `SyntaxTree`, `SyntaxNode`, `SyntaxToken`, dan `SemanticModel`.
- **C# Advanced Features**: Span<T>, Memory<T>, Unsafe Code, Ref Structs, dan Generic Constraints.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi Runtime Type Metadata CLR
Di dalam CoreCLR, representasi sebuah tipe objek bukan sekadar instance dari `System.Type`. CLR mengalokasikan struktur data internal di unmanaged memory (*loader heap*):
- **MethodTable**: Struktur data per-tipe yang berisi ukuran instans, pointer ke interface dispatch table, dan Method Slot Table (virtual method pointer table).
- **EEType**: Representasi eksekusi internal dari MethodTable yang digunakan pada Native AOT.
- **TypeHandle**: Pointer langsung ke `MethodTable` unmanaged.

```
       Managed Heap                     Loader Heap (Unmanaged)
+-----------------------+              +--------------------------+
|      Object Ref       |              |       MethodTable        |
+-----------------------+              +--------------------------+
|  SyncBlockIndex (4B)  |              | ComponentSize / Flags    |
+-----------------------+              +--------------------------+
| MethodTable* (4B/8B)  |------------->| BaseSize                 |
+-----------------------+              +--------------------------+
| Data Fields...        |              | Interface Map Pointer    |
|                       |              +--------------------------+
|                       |              | Method Slot Table Pointer|
+-----------------------+              +--------------------------+
```

Ketika `System.Reflection` klasik dipanggil (misalnya `MethodInfo.Invoke`):
1. CLR melakukan validasi keamanan dan konversi tipe argumen (*boxing* untuk struct).
2. Runtime mengeksekusi *lookup* slot pada MethodTable.
3. Argumen disalin ke frame eksekusi pemanggilan dinamis (*stub invocation*).
4. Hasil pemanggilan di-*box* kembali jika tipe balikannya adalah value type.
Proses ini menambahkan overhead latensi hingga 10–100x dibandingkan *direct call* dan menghasilkan *Garbage Collection (GC) pressure*.

#### 3.2. Dynamic Code Generation: DynamicMethod vs Expression Trees vs Emit
Untuk meniadakan overhead `Invoke`, CLR menyediakan mekanisme pembentukan IL secara on-the-fly:

1. **`System.Reflection.Emit.AssemblyBuilder`**:
   - Membentuk assembly utuh di runtime.
   - Bersifat *heavyweight*. Sebelum .NET Core 3.0 / .NET 5+, assembly yang dibuat via Emit tidak dapat di-unload. Sekarang memerlukan collectible `AssemblyLoadContext`.
2. **`DynamicMethod` (Lightweight Code Generation - LCG)**:
   - Menghasilkan method IL mandiri tanpa memerlukan deklarasi Type atau Assembly formal.
   - Dapat di-garbage collect saat instance delegasinya dilepas.
   - Mampu melewati batasan visibilitas (*skip visibility checks*) via flag `restrictedSkipVisibility: true`, memungkinkan akses field `private`/`internal` secara instan tanpa runtime overhead setelah dikompilasi.
3. **`Expression<TDelegate>`**:
   - Abstraksi tingkat tinggi di atas LCG.
   - Membangun Abstract Syntax Tree (AST) di heap managed, lalu memanggil `.Compile()` yang mengompilasikan AST tersebut menjadi IL via `DynamicMethod`.
   - Overhead pembuatan ekspresi cukup tinggi, namun kecepatan eksekusinya setara dengan *native code* setelah dikompilasi ke delegasi delegate.

#### 3.3. Roslyn Incremental Source Generators Architecture
*Source Generators* beroperasi saat fase kompilasi (compile-time), mengeliminasi total kebutuhan runtime generation. Arsitektur **`IIncrementalGenerator`** (diperkenalkan pada .NET 6 SDK) menggantikan `ISourceGenerator` lama dengan prinsip **Pipeline Transformation & Caching**:

```
[Source Code] 
      │
      ▼
[SyntaxProvider (CreateSyntaxProvider)] 
      │
      ├─> Predicate: Fast Syntactic Filter (Per Node AST, e.g., IsKind(SyntaxKind.ClassDeclaration))
      │
      ▼
[Transform Step: Semantic Resolution]
      │
      ├─> Ekstraksi data murni ke Record/Value Object (IEquatable<T>)
      │   *DILARANG menyimpan ISymbol atau SyntaxNode di sini!*
      │
      ▼
[Pipeline Cache Boundary] ◄─── Validasi Equality: (oldValue.Equals(newValue))
      │
      ├── (Sama / Unchanged)    ──> Output Cache Digunakan (Eksekusi berhenti)
      └── (Berubah / Modified)  ──> RegisterSourceOutput (Emit C# Source)
```

**Aturan Emas Roslyn Incremental Pipeline:**
Objek model yang diteruskan ke pipeline harus menerapkan semantik *value equality* (`IEquatable<T>` atau C# `record`). Jika instance `ISymbol` atau `SyntaxNode` disimpan melewati batas transformasi semantic, referensi internal compiler akan tersangkut di memory pipeline, merusak sistem *cache invalidation*, memicu kompilasi ulang kode yang tidak perlu, dan membuat Visual Studio/OmniSharp/Rider mengalami memory leak parah (*Out Of Memory*).

#### 3.4. AssemblyLoadContext (ALC) dan Unloading Lifecycle
Untuk memuat dan mencabut (*hot reload/plugin system*) kode dinamis di runtime:
- **Default ALC**: Memuat assembly utama dan dependencies bawaan aplikasi.
- **Isolated Collectible ALC**: Dibuat dengan flag `isCollectible: true`. Semua assembly yang dimuat ke dalam ALC ini dialokasikan di memory heap terisolasi.
- **Unloading Condition**: Assembly context hanya dapat dibebaskan dari memori jika:
  1. Tidak ada referensi aktif dari Default ALC ke objek/tipe/method dari Collectible ALC.
  2. Tidak ada thread managed yang sedang mengeksekusi method di dalam assembly tersebut.
  3. Tidak ada delegasi, static field, atau closure yang menunjuk ke method ALC tersebut.

---

### 4. Why & What

| Paradigma | Kapan Digunakan | Keunggulan Utama | Kelemahan / Konsekuensi |
| :--- | :--- | :--- | :--- |
| **System.Reflection (Classic)** | CLI Tools internal, debugging, inspeksi tipe non-kritikal. | Zero tooling setup; sangat fleksibel. | Lambat (boxing + dynamic lookup), memicu GC, **merusak Native AOT**. |
| **DynamicMethod / IL Emit** | Framework serialization/ORM legacy dinamis di runtime Server. | Menghasilkan kode IL optimal yang setara direct call. | Sulit didebug, runtime compilation cost, **incompatible dengan Native AOT / iOS (W^X rules)**. |
| **Expression Trees** | Query translation (seperti EF Core IQueryable Provider). | Type-safe AST manipulation di runtime. | `.Compile()` memakan CPU & memori signifikan, tidak AOT-friendly. |
| **Incremental Source Generators** | Arsitektur modern: Serialization, DI, Mappers, IPC Stubs. | **Zero overhead runtime, Native AOT/Trimming compliant**, validasi compile-time. | Menambah build time jika cache pipeline dirancang dengan buruk. |

---

### 5. How (Workflow detail)

Implementasi arsitektur metaprogramming modern mengikuti jalur:
1. **Design-Time (Compile-Time)**: Prioritaskan `IIncrementalGenerator` untuk semua kebutuhan *code scaffolding*, pemetaan DTO, dynamic proxy generation, dan registrasi dependensi.
2. **Runtime Polyfill / Fallback**: Gunakan `DynamicMethod` / `Expression<T>` hanya jika skema data diidentifikasi dinamis pada runtime (misalnya membaca metadata database schema dinamis dari database tenant user).
3. **Isolation & Lifecycle**: Jika memuat assembly atau bytecode runtime, bungkus selalu di dalam scoped `AssemblyLoadContext` yang collectible, lalu pantau siklus unload melalui `WeakReference`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Metaprogramming
- **Reflection Klasik**: Bagaikan membawa seorang penerjemah manusia saat memesan makanan. Setiap kali Anda ingin memesan satu butir telur, sang penerjemah harus membuka kamus besar, mengecek izin, memverifikasi kata, baru menyampaikannya ke koki. (Akurat, tapi sangat lambat dan melelahkan).
- **DynamicMethod / IL Emit**: Bagaikan mencetak kartu instruksi otomatis di tengah-tengah jam sibuk restoran dan memberikannya langsung ke koki. (Koki langsung paham dengan kecepatan penuh, tapi Anda butuh mesin cetak rumit di dapur).
- **Source Generator**: Resep makanan sudah dicetak langsung pada buku menu resmi sebelum restoran dibuka. Tidak ada penerjemah, tidak ada mesin cetak di dapur, semua bekerja dengan kecepatan native maksimal.

#### Pipeline Data Flow: DynamicMethod vs Source Generator
```
=== RUNTIME METAPROGRAMMING (DynamicMethod / Emit) ===
[Application Starts]
       │
       ▼
Read Type via Reflection ──► Generate IL Opcodes ──► JIT Compile ──► Native Machine Code
                                                      ▲
                                            (High Latency Overhead)

=== COMPILE-TIME METAPROGRAMMING (Roslyn Incremental Generator) ===
[Developer Modifies Code]
       │
       ▼
Roslyn AST Scanner ──► Cache Hit? ──YES──► Skip Generation
       │
       NO
       ▼
Extract Pure Model ──► Emit C# Source ──► Compiled directly to PE Binary
                                                      │
                                                      ▼
                                       Native Machine Code instantly
                                       Zero Runtime Cost, AOT Ready
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Dynamic Property Accessor Menggunakan DynamicMethod (LCG)
Mengakses private property dengan kecepatan direct access tanpa runtime boxing.

```csharp
using System.Reflection;
using System.Reflection.Emit;

namespace Enterprise.Metaprogramming.Core;

public static class FastPropertyAccessor
{
    // Mengembalikan delegate compile-time typed untuk membaca properti private/public
    public static Func<TTarget, TValue> CreateGetter<TTarget, TValue>(string propertyName)
    {
        var targetType = typeof(TTarget);
        var propInfo = targetType.GetProperty(propertyName, 
            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
            ?? throw new ArgumentException($"Property '{propertyName}' tidak ditemukan pada {targetType.FullName}");

        var getMethod = propInfo.GetGetMethod(nonPublic: true)
            ?? throw new InvalidOperationException($"Getter untuk '{propertyName}' tidak ditemukan.");

        // Deklarasi DynamicMethod dengan skipVisibility = true
        var dynamicMethod = new DynamicMethod(
            name: $"Get_{targetType.Name}_{propertyName}",
            returnType: typeof(TValue),
            parameterTypes: [typeof(TTarget)],
            restrictedSkipVisibility: true);

        var il = dynamicMethod.GetILGenerator();

        // Push argumen 0 (instance target) ke evaluation stack
        il.Emit(OpCodes.Ldarg_0);

        // Panggil getter method (Callvirt jika virtual, Call jika non-virtual atau struct)
        if (getMethod.IsVirtual && !targetType.IsValueType)
        {
            il.Emit(OpCodes.Callvirt, getMethod);
        }
        else
        {
            il.Emit(OpCodes.Call, getMethod);
        }

        // Return value yang ada di atas stack
        il.Emit(OpCodes.Ret);

        return (Func<TTarget, TValue>)dynamicMethod.CreateDelegate(typeof(Func<TTarget, TValue>));
    }
}
```

#### 7.2. Practical Example: Production-Grade Roslyn Incremental Generator
Membuat generator yang menghasilkan *type-safe property mapper* tanpa runtime reflection.

##### File 1: Analyzer & Generator Implementation (`MapperGenerator.cs`)
```csharp
using System.Collections.Immutable;
using System.Text;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.Text;

namespace Enterprise.Generators;

// Mendefinisikan Model Data State yang mematuhi Value Equality (IEquatable)
// SANGAT KRUSIAL: Tidak boleh ada ISymbol atau SyntaxNode di dalam model ini!
public readonly record struct PropertyMappingModel(string Name, string TypeName);

public readonly record struct ClassMappingModel(
    string Namespace,
    string SourceClassName,
    string TargetClassName,
    ImmutableArray<PropertyMappingModel> Properties) : IEquatable<ClassMappingModel>
{
    public bool Equals(ClassMappingModel other) =>
        Namespace == other.Namespace &&
        SourceClassName == other.SourceClassName &&
        TargetClassName == other.TargetClassName &&
        Properties.SequenceEqual(other.Properties);

    public override int GetHashCode()
    {
        unchecked
        {
            var hash = 17;
            hash = hash * 23 + (Namespace?.GetHashCode() ?? 0);
            hash = hash * 23 + SourceClassName.GetHashCode();
            hash = hash * 23 + TargetClassName.GetHashCode();
            foreach (var prop in Properties)
            {
                hash = hash * 23 + prop.GetHashCode();
            }
            return hash;
        }
    }
}

[Generator]
public sealed class HighThroughputMapperGenerator : IIncrementalGenerator
{
    private const string AttributeSourceCode = """
        // <auto-generated/>
        #nullable enable
        namespace Enterprise.Generators.Annotations
        {
            [System.AttributeUsage(System.AttributeTargets.Class, AllowMultiple = false, Inherited = false)]
            public sealed class GenerateMapperAttribute : System.Attribute
            {
                public System.Type TargetType { get; }
                public GenerateMapperAttribute(System.Type targetType)
                {
                    TargetType = targetType;
                }
            }
        }
        """;

    public void Initialize(IncrementalGeneratorInitializationContext context)
    {
        // 1. Injeksi Marker Attribute langsung ke kompilasi user
        context.RegisterPostInitializationOutput(ctx =>
        {
            ctx.AddSource("GenerateMapperAttribute.g.cs", SourceText.From(AttributeSourceCode, Encoding.UTF8));
        });

        // 2. Syntactic Filter: Filter node class yang memiliki attribute
        var classDeclarations = context.SyntaxProvider.CreateSyntaxProvider(
            predicate: static (s, _) => s is ClassDeclarationSyntax { AttributeLists.Count: > 0 },
            transform: static (ctx, cancellationToken) => GetSemanticTargetForGeneration(ctx, cancellationToken))
            .Where(static m => m is not null)
            .Select(static (m, _) => m!.Value);

        // 3. Register Source Output dengan Model yang Immutable & Equatable
        context.RegisterSourceOutput(classDeclarations, static (spc, model) =>
        {
            var code = GenerateMapperClass(model);
            spc.AddSource($"{model.SourceClassName}To{model.TargetClassName}Mapper.g.cs", SourceText.From(code, Encoding.UTF8));
        });
    }

    private static ClassMappingModel? GetSemanticTargetForGeneration(
        GeneratorSyntaxContext context, 
        CancellationToken ct)
    {
        var classDeclaration = (ClassDeclarationSyntax)context.Node;
        var model = context.SemanticModel;
        var classSymbol = model.GetDeclaredSymbol(classDeclaration, ct) as INamedTypeSymbol;

        if (classSymbol is null) return null;

        var mapperAttribute = classSymbol.GetAttributes().FirstOrDefault(ad =>
            ad.AttributeClass?.ToDisplayString() == "Enterprise.Generators.Annotations.GenerateMapperAttribute");

        if (mapperAttribute is null || mapperAttribute.ConstructorArguments.Length == 0)
            return null;

        var targetTypeSymbol = mapperAttribute.ConstructorArguments[0].Value as INamedTypeSymbol;
        if (targetTypeSymbol is null) return null;

        // Ambil properti publik yang cocok antara Source dan Target
        var sourceProps = classSymbol.GetMembers().OfType<IPropertySymbol>()
            .Where(p => p.GetMethod is not null && p.DeclaredAccessibility == Accessibility.Public);
        var targetProps = targetTypeSymbol.GetMembers().OfType<IPropertySymbol>()
            .Where(p => p.SetMethod is not null && p.DeclaredAccessibility == Accessibility.Public)
            .ToDictionary(p => p.Name, p => p, StringComparer.Ordinal);

        var matchedProperties = ImmutableArray.CreateBuilder<PropertyMappingModel>();

        foreach (var sProp in sourceProps)
        {
            ct.ThrowIfCancellationRequested();

            if (targetProps.TryGetValue(sProp.Name, out var tProp))
            {
                // Cocokkan jika tipe data identik
                if (SymbolEqualityComparer.Default.Equals(sProp.Type, tProp.Type))
                {
                    matchedProperties.Add(new PropertyMappingModel(sProp.Name, sProp.Type.ToDisplayString()));
                }
            }
        }

        var ns = classSymbol.ContainingNamespace.IsGlobalNamespace 
            ? "Global" 
            : classSymbol.ContainingNamespace.ToDisplayString();

        return new ClassMappingModel(
            Namespace: ns,
            SourceClassName: classSymbol.Name,
            TargetClassName: targetTypeSymbol.Name,
            Properties: matchedProperties.ToImmutable());
    }

    private static string GenerateMapperClass(ClassMappingModel model)
    {
        var sb = new StringBuilder();
        sb.AppendLine("// <auto-generated/>");
        sb.AppendLine("#nullable enable");
        sb.AppendLine($"namespace {model.Namespace}");
        sb.AppendLine("{");
        sb.AppendLine($"    public static class {model.SourceClassName}To{model.TargetClassName}Extensions");
        sb.AppendLine("    {");
        sb.AppendLine($"        public static {model.TargetClassName} MapTo{model.TargetClassName}(this {model.SourceClassName} source)");
        sb.AppendLine("        {");
        sb.AppendLine("            if (source is null) throw new System.ArgumentNullException(nameof(source));");
        sb.AppendLine($"            var target = new {model.TargetClassName}();");

        foreach (var prop in model.Properties)
        {
            sb.AppendLine($"            target.{prop.Name} = source.{prop.Name};");
        }

        sb.AppendLine("            return target;");
        sb.AppendLine("        }");
        sb.AppendLine("    }");
        sb.AppendLine("}");
        return sb.ToString();
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario Kasus: Sistem Gateway Transaksi Finansial Ultra-Low Latency (500k TPS)
**Konteks**: Sebuah perusahaan FinTech memproses jutaan pesan payload biner ISO-8583 dan format proprietary JSON per detik. Implementasi lama menggunakan framework reflection dinamis (`AutoMapper` dan runtime deserializer) yang mengakibatkan lonjakan alokasi Gen-0/Gen-1 heap sebesar 4 GB per menit. Hal ini memicu jeda GC (GC Pauses) berkisar antara 15ms hingga 80ms, merusak batas SLA (Service Level Agreement) latensi P99 (< 5ms).

#### Solusi Arsitektural:
1. **Eliminasi Dynamic Reflection Runtime**: Mengganti semua mapping berbasis dynamic property invocation dengan Roslyn `IIncrementalGenerator` yang memetakan struct byte stream langsung ke managed records secara direct assignment.
2. **Native AOT Compliance**: Mengubah seluruh microservice core engine agar dapat dikompilasi via `dotnet publish -r linux-x64 -c Release /p:PublishAot=true`. Dynamic code generation (`DynamicMethod` atau runtime Emit) dilarang total karena CoreRT/Native AOT menonaktifkan JIT engine pada host binary.
3. **Pluggable Tenant Validator via Dynamic AssemblyLoadContext**: Aturan validasi per-negara dienkapsulasi ke dalam isolated assembly (`RuleSet_SG.dll`, `RuleSet_ID.dll`). Assembly ini dimuat menggunakan collectible `AssemblyLoadContext`. Saat kepatuhan regulasi berubah, context di-unload, GC membebaskan memori unmanaged MethodTable, dan assembly baru dimuat tanpa me-restart proses node Linux container.

#### Hasil Metrik (Benchmark & Produksi):
- **Alokasi Memori**: Turun 98.4% (dari ~4 GB/menit menjadi < 60 MB/menit akibat peniadaan runtime boxing).
- **Latensi P99**: Terpangkas dari 48ms menjadi 1.2ms.
- **Waktu Startup Pod Container**: Turun dari 4.2 detik menjadi 35 milidetik dengan Native AOT binary berukuran 28MB.

---

### 9. Trade-offs

```
                  KEMUDAHAN IMPLEMENTASI
                         ▲
                         │       * System.Reflection
                         │
                         │             * Expression Trees
                         │
                         │       * DynamicMethod / IL
                         │
                         │  * Incremental Source Generator
                         └─────────────────────────────────► PERFORMA RUNTIME & AOT READY
```

1. **Build Time vs Runtime Latency**:
   - *Source Generators* memindahkan komputasi metadata ke fase build. Kompilasi awal project bertambah ~5-15%, namun runtime latency berkurang ke titik zero-overhead.
2. **Fleksibilitas vs Keamanan Tipe (Type Safety)**:
   - *Reflection* runtime dapat mengevaluasi schema yang strukturnya baru diketahui setelah HTTP request tiba. Source generator menuntut struktur diketahui saat fase kompilasi.
3. **Native AOT Constraints vs Dynamic Assembly Loading**:
   - Native AOT mengunci seluruh kode pada saat build. Fitur `Assembly.Load(byte[])` atau collectible ALC yang memuat assembly baru tidak didukung di Native AOT murni (kecuali via webassembly interpreter atau interop C ABI).

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Membocorkan `ISymbol` atau `SyntaxNode` ke Output Pipeline Roslyn
```csharp
// FATAL ERROR!
IncrementalValuesProvider<INamedTypeSymbol> models = context.SyntaxProvider.CreateSyntaxProvider(
    predicate: ...,
    transform: (ctx, _) => (INamedTypeSymbol)ctx.SemanticModel.GetDeclaredSymbol(ctx.Node) // MEMORY LEAK!
);
context.RegisterSourceOutput(models, (spc, symbol) => { ... });
```
- **Penyebab**: `INamedTypeSymbol` menyimpan referensi kuat ke `Compilation` dan `SemanticModel`. Saat developer mengetik satu karakter di IDE, `Compilation` baru dibuat. Karena symbol lama tertahan di cache pipeline generator, memory IDE tidak pernah terbebas, menyebabkan VS/Rider freeze.
- **Solusi**: Transformasikan symbol menjadi Plain Old Data C# `record struct` yang menerapkan `IEquatable<T>`.

#### Kesalahan 2: Memory Leak pada Collectible `AssemblyLoadContext`
- **Penyebab**: Event listener di Default ALC berlangganan ke event yang didefinisikan di dalam Collectible ALC, atau melempar tipe data dari Collectible ALC ke dalam static dictionary Default ALC.
- **Troubleshooting Checklist**:
  1. Jalankan `GC.Collect()` dan `GC.WaitForPendingFinalizers()` dua kali berturut-turut.
  2. Periksa status via `WeakReference.IsAlive`.
  3. Gunakan SOS Debugging Extension di WinDbg / `dotnet-dump`:
     `!dumpheap -type MyIsolatedPluginType` lalu jalankan `!gcroot <ObjectAddress>` untuk menemukan referensi yang mengunci ALC.

#### Kesalahan 3: Stack Imbalance pada IL Emit
- **Penyebab**: Jumlah opcode `ldarg`, `ldloc`, atau `call` tidak seimbang dengan nilai yang diekspektasikan oleh instruksi `ret` atau branch targets. Mengakibatkan runtime crash `InvalidProgramException: Common Language Runtime detected an invalid program.`
- **Solusi**: Gunakan library `ILVerify` pada CI/CD untuk memvalidasi byte array assembly hasil Emit secara formal sebelum didistribusikan.

---

### 11. Best Practices (Production Checklist)

| Kategori | Rekomendasi Teknis Produksi | Status Audit |
| :--- | :--- | :--- |
| **Source Gen** | Selalu tandai model ekstraksi semantic dengan `record` atau `readonly record struct`. | [ ] |
| **Source Gen** | Gunakan `CancellationToken` di setiap loop iterasi resolusi semantic symbol. | [ ] |
| **Source Gen** | Hindari manipulasi string regex manual; gunakan `StringBuilder` terprediksi atau pre-allocated buffer. | [ ] |
| **Roslyn Diagnostics**| Laporkan diagnostic error (`spc.ReportDiagnostic`) alih-alih melempar exception unhandled (`throw new Exception`). | [ ] |
| **ALC Lifecycle** | Pastikan host berkomunikasi dengan plugin ALC hanya melalui generic primitive type atau Interface yang dimuat di Default ALC. | [ ] |
| **IL Generation** | Jangan memanggil `DynamicMethod.CreateDelegate()` berulang kali di hot-path; simpan delegate di static readonly cache field. | [ ] |
| **Native AOT** | Konfigurasikan `<IsAotCompatible>true</IsAotCompatible>` pada file `.csproj` class library Anda. | [ ] |

---

### 12. Hands-on Practice

Struktur direktori kerja:
```
hands-on/m02/
├── src/
│   ├── Enterprise.Core.Generators/      (Incremental Source Generator)
│   │   ├── Enterprise.Core.Generators.csproj
│   │   └── DeepCloneGenerator.cs
│   └── Enterprise.App/                  (Consumer App + Benchmarking)
│       ├── Enterprise.App.csproj
│       └── Program.cs
└── hands-on-m02.sln
```

#### Langkah 1: Inisialisasi Generator Project
Buat project library generator yang menargetkan `netstandard2.0` (standar wajib Roslyn compiler):

`hands-on/m02/src/Enterprise.Core.Generators/Enterprise.Core.Generators.csproj`:
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>netstandard2.0</TargetFramework>
    <LangVersion>latest</LangVersion>
    <Nullable>enable</Nullable>
    <IsRoslynComponent>true</IsRoslynComponent>
    <EnforceExtendedAnalyzerRules>true</EnforceExtendedAnalyzerRules>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.CodeAnalysis.CSharp" Version="4.8.0" PrivateAssets="all" />
    <PackageReference Include="Microsoft.CodeAnalysis.Analyzers" Version="3.3.4" PrivateAssets="all" />
  </ItemGroup>
</Project>
```

#### Langkah 2: Implementasi DeepCloneGenerator
`hands-on/m02/src/Enterprise.Core.Generators/DeepCloneGenerator.cs`:
```csharp
using System.Collections.Immutable;
using System.Text;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.Text;

namespace Enterprise.Core.Generators;

public readonly record struct CloneableField(string Name, string TypeName);

public readonly record struct CloneableClass(
    string Namespace,
    string ClassName,
    ImmutableArray<CloneableField> Fields) : System.IEquatable<CloneableClass>
{
    public bool Equals(CloneableClass other) =>
        Namespace == other.Namespace &&
        ClassName == other.ClassName &&
        Fields.SequenceEqual(other.Fields);

    public override int GetHashCode()
    {
        unchecked
        {
            int hash = 19;
            hash = hash * 31 + (Namespace?.GetHashCode() ?? 0);
            hash = hash * 31 + ClassName.GetHashCode();
            foreach (var f in Fields) hash = hash * 31 + f.GetHashCode();
            return hash;
        }
    }
}

[Generator]
public sealed class DeepCloneGenerator : IIncrementalGenerator
{
    public void Initialize(IncrementalGeneratorInitializationContext context)
    {
        context.RegisterPostInitializationOutput(ctx =>
        {
            ctx.AddSource("GenerateDeepCloneAttribute.g.cs", SourceText.From("""
                // <auto-generated/>
                namespace Enterprise.Core
                {
                    [System.AttributeUsage(System.AttributeTargets.Class, Inherited = false, AllowMultiple = false)]
                    public sealed class GenerateDeepCloneAttribute : System.Attribute { }
                }
                """, Encoding.UTF8));
        });

        var pipeline = context.SyntaxProvider.CreateSyntaxProvider(
            predicate: static (node, _) => node is ClassDeclarationSyntax { AttributeLists.Count: > 0 },
            transform: static (ctx, ct) =>
            {
                var classSyntax = (ClassDeclarationSyntax)ctx.Node;
                var symbol = ctx.SemanticModel.GetDeclaredSymbol(classSyntax, ct) as INamedTypeSymbol;
                if (symbol is null) return (CloneableClass?)null;

                var hasAttr = symbol.GetAttributes().Any(a => 
                    a.AttributeClass?.ToDisplayString() == "Enterprise.Core.GenerateDeepCloneAttribute");
                if (!hasAttr) return null;

                var fields = symbol.GetMembers().OfType<IPropertySymbol>()
                    .Where(p => p.SetMethod is not null && p.CanBeReferencedByName)
                    .Select(p => new CloneableField(p.Name, p.Type.ToDisplayString()))
                    .ToImmutableArray();

                return new CloneableClass(
                    symbol.ContainingNamespace.IsGlobalNamespace ? "Global" : symbol.ContainingNamespace.ToDisplayString(),
                    symbol.Name,
                    fields);
            })
            .Where(static m => m is not null)
            .Select(static (m, _) => m!.Value);

        context.RegisterSourceOutput(pipeline, static (spc, model) =>
        {
            var sb = new StringBuilder();
            sb.AppendLine("// <auto-generated/>");
            sb.AppendLine($"namespace {model.Namespace}");
            sb.AppendLine("{");
            sb.AppendLine($"    public partial class {model.ClassName}");
            sb.AppendLine("    {");
            sb.AppendLine($"        public {model.ClassName} DeepClone()");
            sb.AppendLine("        {");
            sb.AppendLine($"            var clone = new {model.ClassName}();");
            foreach (var f in model.Fields)
            {
                sb.AppendLine($"            clone.{f.Name} = this.{f.Name};");
            }
            sb.AppendLine("            return clone;");
            sb.AppendLine("        }");
            sb.AppendLine("    }");
            sb.AppendLine("}");

            spc.AddSource($"{model.ClassName}_DeepClone.g.cs", SourceText.From(sb.ToString(), Encoding.UTF8));
        });
    }
}
```

#### Langkah 3: Konfigurasi Consumer & Benchmark
`hands-on/m02/src/Enterprise.App/Enterprise.App.csproj`:
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>

  <ItemGroup>
    <ProjectReference Include="..\Enterprise.Core.Generators\Enterprise.Core.Generators.csproj" 
                      OutputItemType="Analyzer" 
                      ReferenceOutputAssembly="false" />
  </ItemGroup>

  <ItemGroup>
    <PackageReference Include="BenchmarkDotNet" Version="0.13.12" />
  </ItemGroup>
</Project>
```

`hands-on/m02/src/Enterprise.App/Program.cs`:
```csharp
using BenchmarkDotNet.Attributes;
using BenchmarkDotNet.Running;
using Enterprise.Core;

namespace Enterprise.App;

[GenerateDeepClone]
public partial class FinancialContract
{
    public string ContractId { get; set; } = string.Empty;
    public decimal NotionalAmount { get; set; }
    public string Currency { get; set; } = "USD";
    public DateTime TradeDate { get; set; }
}

[MemoryDiagnoser]
public class CloneBenchmark
{
    private readonly FinancialContract _contract = new()
    {
        ContractId = "CTX-990182",
        NotionalAmount = 50_000_000.00m,
        Currency = "EUR",
        TradeDate = DateTime.UtcNow
    };

    [Benchmark(Baseline = true)]
    public FinancialContract ReflectionClone()
    {
        var type = typeof(FinancialContract);
        var instance = (FinancialContract)Activator.CreateInstance(type)!;
        foreach (var prop in type.GetProperties())
        {
            if (prop.CanWrite)
            {
                prop.SetValue(instance, prop.GetValue(_contract));
            }
        }
        return instance;
    }

    [Benchmark]
    public FinancialContract SourceGeneratedClone()
    {
        return _contract.DeepClone();
    }
}

public class Program
{
    public static void Main(string[] args)
    {
        Console.WriteLine("Memverifikasi Keberadaan Method DeepClone()...");
        var testInstance = new FinancialContract { ContractId = "TEST-1", NotionalAmount = 100m };
        var cloned = testInstance.DeepClone();
        Console.WriteLine($"Berhasil Kloning: {cloned.ContractId}, Amount: {cloned.NotionalAmount}");

        Console.WriteLine("\nMenjalankan BenchmarkDotNet...");
        BenchmarkRunner.Run<CloneBenchmark>();
    }
}
```

---

### 13. Exercise

#### Level: Easy
1. Modifikasi file `DeepCloneGenerator.cs` agar mengabaikan properti yang memiliki modifier `init-only` atau properti bertipe reference type yang bukan `System.String` (mengeluarkan warning compiler melalui `spc.ReportDiagnostic`).
2. *Panduan implementasi*: Periksa property `p.SetMethod.IsInitOnly` dan analisis apakah `p.Type.IsValueType` bernilai `true` atau bertipe `SpecialType.System_String`.

#### Level: Medium
1. Buat mekanisme **Expression Tree Property Setter** berkinerja tinggi `Action<TTarget, object>` yang menerima boxing input `object`, melakukan unboxing IL casting otomatis, dan mengeksekusi setter property tanpa reflection invocation.
2. Simpan delegate yang dihasilkan ke dalam generic thread-safe concurrent cache (`ConcurrentDictionary<string, Delegate>`).

#### Level: Hard
1. Buat sebuah custom collectible `PluginAssemblyLoadContext` yang mampu memuat assembly dll pihak ketiga dari disk, mengeksekusi method `public static string Execute()`, lalu meng-unload context tersebut secara instan.
2. Buat unit-test penjamin memori yang memverifikasi bahwa `AssemblyLoadContext` benar-benar ter-garbage collect 100% menggunakan `WeakReference` dan assertion loop GC.

---

### 14. Challenge

**Skenario Tantangan Produksi (Complex Distributed Actor System)**:
Rancang dan bangun generator RPC Proxy berbasis `IIncrementalGenerator` yang memproses interface kontrak jaringan, misalnya:

```csharp
[NetworkContract]
public interface IOrderService
{
    ValueTask<OrderResult> SubmitOrderAsync(Guid accountId, decimal amount, CancellationToken ct);
}
```

**Batasan & Kriteria Arsitektur**:
1. Generator harus memproduksi kelas implementasi client-side: `OrderServiceRpcClient : IOrderService`.
2. Generator harus memproduksi network dispatcher server-side tanpa alokasi string method name (menggunakan hash code 64-bit integer stabil / FNV-1a hash saat compile-time dari signature method).
3. Payload argumen tidak boleh menggunakan dynamic JSON reflection. Serialisasi harus di-emit langsung memanggil buffer writer byte array (`IBufferWriter<byte>`).
4. Kode yang dihasilkan **wajib 100% Native AOT Compliant** (tidak ada peringatan trimming/AOT saat build dengan flag `<AotAnalysisWarningLevel>preview</AotAnalysisWarningLevel>`).
5. Buat arsitektur ini deterministik terhadap cache IDE: pastikan pengetikan komentar di dalam body interface tidak memicu kompilasi ulang kode proxy.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Mengapa `MethodInfo.Invoke` jauh lebih lambat dibandingkan pemanggilan method langsung (*direct call*)?
   - A. Karena CLR menghentikan semua thread managed (STW).
   - B. Karena adanya pengecekan argumen runtime, lookup slot MethodTable, boxing/unboxing value types, dan frame conversion.
   - C. Karena Reflection mengeksekusi kode melalui command prompt OS.
   - D. Karena Reflection selalu membaca disk storage.
   *(Jawaban yang benar: B)*

2. Target framework minimum yang disyaratkan untuk project yang memuat analyzer/generator Roslyn adalah:
   - A. `net8.0`
   - B. `net9.0`
   - C. `netstandard2.0`
   - D. `netcoreapp3.1`
   *(Jawaban yang benar: C)*

3. Struktur data CLR di unmanaged memory yang merepresentasikan tipe dan berisi pointer method virtual table adalah:
   - A. SyncBlock
   - B. MethodTable
   - C. GC Descriptor Heap
   - D. Card Table
   *(Jawaban yang benar: B)*

4. Apa dampak penggunaan `restrictedSkipVisibility: true` pada constructor `DynamicMethod`?
   - A. Mengizinkan method IL mengakses member privat dan internal tanpa peduli encapsulation modifier.
   - B. Menonaktifkan pemeriksaan out-of-memory pada CLR.
   - C. Mencegah method tersebut di-garbage collect.
   - D. Mengubah pointer unmanaged memory menjadi managed span.
   *(Jawaban yang benar: A)*

5. Mengapa pipeline Roslyn `IIncrementalGenerator` lebih unggul daripada `ISourceGenerator` standar (.NET 5)?
   - A. Karena `IIncrementalGenerator` berjalan di CoreRT Native AOT engine.
   - B. Karena mengadopsi fine-grained caching berbasis value-equality transform step, mencegah regenerasi kode berulang.
   - C. Karena ditulis menggunakan bahasa C++ unmanaged.
   - D. Karena tidak memerlukan semantic model.
   *(Jawaban yang benar: B)*

---

#### 5 Pertanyaan Intermediate
6. Mengapa menyimpan referensi `SyntaxNode` atau `ISymbol` ke dalam method `RegisterSourceOutput` dianggap fatal pada Roslyn Incremental Generator?
   - A. Menghasilkan error kompilasi C# CS0103.
   - B. Objek tersebut menahan root referensi ke seluruh `Compilation` instance lama, memicu kebocoran memori massif pada IDE host.
   - C. Menghapus semua file `.cs` di root proyek.
   - D. Membuat assembly keluaran berukuran lebih dari 4 GB.
   *(Jawaban yang benar: B)*

7. Kapan sebuah collectible `AssemblyLoadContext` dijamin akan benar-benar terbebas dari unmanaged memory heap?
   - A. Segera setelah method `alc.Unload()` selesai dieksekusi.
   - B. Ketika tidak ada lagi referensi hidup managed dari luar ALC, tidak ada thread aktif di dalamnya, dan GC cycling telah selesai memproses finalizer.
   - C. Ketika komputer di-restart.
   - D. Saat perintah `dotnet build` dipanggil kembali.
   *(Jawaban yang benar: B)*

8. Perhatikan potongan instruksi IL berikut:
   ```il
   ldarg.0
   ldfld int32 Enterprise.Core.Account::_balance
   ret
   ```
   Jika tipe field `_balance` adalah `int32`, apakah fungsi IL di atas valid?
   - A. Tidak valid, karena `_balance` harus di-box terlebih dahulu menggunakan `box [System.Runtime]System.Int32`.
   - B. Valid, stack menyisakan 1 elemen bertipe `int32` yang cocok dengan return signature method.
   - C. Tidak valid, harus ada instruksi `stloc.0` sebelum `ret`.
   - D. Tidak valid, instance field hanya bisa dibaca menggunakan `ldarg.1`.
   *(Jawaban yang benar: B)*

9. Mengapa `DynamicMethod` dan `System.Reflection.Emit` tidak dapat bekerja pada lingkungan iOS murni atau Native AOT?
   - A. Karena prosesor ARM64 tidak mendukung Intermediate Language.
   - B. Karena kebijakan keamanan OS (seperti Apple W^X / Write XOR Execute) melarang memori heap dialokasikan sebagai executable code tanpa signature Apple.
   - C. Karena framework .NET pada iOS tidak memiliki garbage collector.
   - D. Karena ukuran binary AOT melebihi batas 100 MB.
   *(Jawaban yang benar: B)*

10. Pendekatan manakah yang memberikan keseimbangan terbaik antara kecepatan dynamic execution dan kemudahan sintaks jika Source Generator tidak dapat digunakan karena schema runtime?
    - A. Berulang kali memanggil `MethodInfo.Invoke`.
    - B. Membangun `Expression Trees` sekali, memanggil `.Compile()` dan menyimpan delegasi delegate-nya ke dalam static cache dictionary.
    - C. Menulis IL Emit manual ke file `.dll` baru di hard disk setiap kali request datang.
    - D. Membaca properti via string regex matching dari method `.ToString()`.
    *(Jawaban yang benar: B)*

---

#### 3 Skenario Kasus Produksi
11. **Skenario Kasus A**:
    Aplikasi microservice trading Anda mengalami lonjakan memori yang tidak pernah turun setelah memuat plugin strategi baru menggunakan custom `AssemblyLoadContext`. Analisis menggunakan `dotnet-dump` menunjukkan instance dari `PluginAssemblyLoadContext` masih hidup. GC root mengarah ke sebuah event listener:
    `HostMarketDataFeed.OnPriceTick += pluginStrategyInstance.HandleTick;`
    Apa akar permasalahan dan bagaimana langkah korektifnya?
    - **Solusi Rekayasa**: Referensi event delegate pada objek static/singleton `HostMarketDataFeed` (berada di Default ALC) menahan referensi instans target method yang berada di Collectible ALC. Hal ini membentuk root graph yang mencegah ALC di-unload. Solusinya: Pastikan interface plugin mengimplementasikan `IDisposable`, dan unsubscribe seluruh event handler (`HostMarketDataFeed.OnPriceTick -= pluginStrategyInstance.HandleTick`) sebelum `alc.Unload()` dipanggil.

12. **Skenario Kasus B**:
    Sebuah tim engineer membuat Roslyn Source Generator untuk validasi fluent. Saat solusi proyek berukuran 400 project dibuka di Visual Studio, CPU seluruh developer mencapai 100% konstan dan VS sering mengalami crash OOM. Setelah audit, ditemukan bahwa pipeline didefinisikan seperti ini:
    ```csharp
    var syntaxProvider = context.SyntaxProvider.CreateSyntaxProvider(
        predicate: (node, _) => true, // Mengambil SEMUA node AST
        transform: (ctx, _) => ctx.SemanticModel.GetDeclaredSymbol(ctx.Node)
    );
    ```
    Identifikasi 2 kesalahan fatal arsitektur pada kode ini dan perbaikannya!
    - **Solusi Rekayasa**:
      1. *Syntactic Filter Terlalu Terbuka*: Predicate bernilai `(node, _) => true` memaksa Roslyn mengevaluasi *setiap* karakter/node syntax (termasuk kurung kurawal, koma, spasi). Solusi: Filter ketat menggunakan syntax kinds, misal `node is RecordDeclarationSyntax rds && rds.AttributeLists.Count > 0`.
      2. *Semantic Model Invocation Tanpa Filter*: `ctx.SemanticModel.GetDeclaredSymbol` dipanggil di seluruh node, memaksa Roslyn melakukan semantic resolution (binding tipe, lookup simbol) yang sangat mahal secara komputasi.
      3. *Symbol Leaking*: Objek `ISymbol` diteruskan langsung ke pipeline caching tanpa ekstraksi model `IEquatable`.

13. **Skenario Kasus C**:
    Anda ditugaskan memigrasikan backend payment engine legacy ke **Native AOT (.NET 8)**. Proyek tersebut menggunakan serializer berbasis `Reflection.Emit` yang menghasilkan dynamic assembly untuk serialisasi model DTO internal. Saat diuji pada environment Linux Docker berbasis Native AOT, sistem langsung melempar:
    `PlatformNotSupportedException: Operation is not supported on this platform.`
    Bagaimana Anda mendesain solusi arsitektur penggantinya tanpa menulis kode boilerplate mapping manual untuk ratusan DTO?
    - **Solusi Rekayasa**:
      Ganti serializer berbasis Emit dengan `System.Text.Json` source generator bawaan atau buat custom Roslyn `IIncrementalGenerator`. Daftarkan serializer context menggunakan:
      `[JsonSerializable(typeof(List<PaymentTransactionDto>))]`
      `internal partial class PaymentJsonContext : JsonSerializerContext {}`
      Dengan cara ini, seluruh parsing logika metadata digenerate pada compile-time ke dalam static unmanaged-compliant code. Panggil `JsonSerializer.Deserialize(payload, PaymentJsonContext.Default.PaymentTransactionDto)` yang sepenuhnya zero-reflection dan 100% kompatibel dengan Native AOT.

---

### 16. Summary
1. **Pergeseran Paradigma Metaprogramming**: Modern C# bergerak dari *Runtime Inspection & Invocation* (`System.Reflection`) menuju *Compile-Time Transformation* (`IIncrementalGenerator`) demi mendukung reliabilitas, efisiensi memori, dan kesiapan terhadap ekosistem Native AOT.
2. **Kunci Performa Roslyn Incremental Generator**: Terletak pada determinisme *value equality*. Pemisahan ketat antara identifikasi AST, resolusi semantik, dan representasi model POD (`record struct`) memastikan cache IDE tidak rusak dan performa build tetap instan.
3. **Runtime Generation Fallback**: Gunakan `DynamicMethod` / `Expression Trees` hanya jika struktur data baru dapat ditentukan saat runtime, selalu simpan delegasinya di dalam static cache, dan hindari boxing pada interface calling convention.
4. **Isolasi Plugin Dinamis**: Penggunaan Collectible `AssemblyLoadContext` memerlukan kedisiplinan ketat dalam menjaga GC boundaries; pastikan tidak ada referensi balik ke Default ALC agar pembersihan unmanaged loader heap berhasil secara sempurna.