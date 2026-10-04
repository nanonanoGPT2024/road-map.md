# Bab 01: Fondasi Bahasa & Arsitektur .NET Runtime
## Modul 01: Arsitektur Eksekusi .NET, Kompilasi Roslyn, dan Anatomi Program C#

---

### 1. Learning Objectives (Tujuan Pembelajaran)
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** pipeline kompilasi C# dari kode sumber (*source code*) hingga eksekusi kode mesin *native* melalui arsitektur Roslyn dan Common Language Runtime (CLR).
- **Mengidentifikasi** struktur biner *assembly* .NET, termasuk representasi Common Intermediate Language (CIL) dan Metadata.
- **Mengonstruksi** program C# modern dengan pemahaman mendalam terhadap perbedaan struktural antara *explicit entry point* (`static void Main`) dan *Top-Level Statements*.
- **Mengevaluasi** dampak performa dari mekanisme *Tiered Compilation* (JIT Compilation) dan implikasi penggunaan *Ahead-Of-Time* (AOT) compilation.

---

### 2. Prerequisites (Prasyarat)
Sebelum mempelajari modul ini, Anda harus memahami:
- Konsep dasar pemrograman prosedural dan berorientasi objek (variabel, fungsi, *control flow*, *class*).
- Pemahaman dasar arsitektur komputer (arsitektur Von Neumann, CPU registers, RAM, Stack vs. Heap).
- Kemampuan dasar pengoperasian *Command Line Interface* (CLI) atau terminal (Bash, PowerShell).
- .NET 8.0 SDK atau versi lebih baru telah terpasang di sistem operasi Anda.

---

### 3. Concept Explanation (Penjelasan Konsep)
C# bukan merupakan bahasa yang dikompilasi secara langsung ke instruksi mesin berbasis arsitektur prosesor (*native machine code*) seperti halnya C atau C++, maupun bahasa yang diinterpretasikan murni secara baris-per-baris seperti Python. C# adalah bahasa yang dikompilasi secara *managed* berbasis *Virtual Execution System* (VES) yang diatur oleh standar ECMA-335.

Siklus hidup aplikasi C# terbagi menjadi dua fase utama:
1. **Fase Kompilasi Statis (*Build Time*)**: Kompiler C# modern (bernama sandi **Roslyn**) memproses sintaks C#, melakukan parsing, analisis semantik, dan optimasi tingkat tinggi, kemudian menghasilkan *assembly* biner (.dll atau .exe). Berkas ini tidak berisi instruksi CPU x86/ARM, melainkan berisi **Common Intermediate Language (CIL)** serta blok **Metadata** yang merepresentasikan seluruh definisi tipe, referensi, dan atribut.
2. **Fase Eksekusi Terkelola (*Runtime*)**: Saat program dijalankan, **Common Language Runtime (CLR)** mengambil alih kontrol eksekusi. Di dalam CLR, komponen **Just-In-Time (JIT) Compiler** (bernama **RyuJIT**) mengonversi instruksi CIL menjadi instruksi mesin spesifik prosesor saat metode pertama kali dieksekusi. CLR juga bertindak sebagai sistem operasi mini yang mengelola alokasi memori (*Garbage Collector*), penanganan *thread*, verifikasi tipe secara dinamis, dan isolasi keamanan eksekusi.

---

### 4. Why This Matters (Mengapa Penting)
Pemahaman tentang arsitektur eksekusi ini membedakan seorang *coder* sintaks dari *software engineer* kelas atas:
- **Diagnostik Performa Ekstrem**: Masalah latensi pada aplikasi *enterprise* berskala besar sering kali berakar pada *cold-start penalty* (JIT compilation overhead) atau tekanan alokasi pada *Garbage Collector* (GC).
- **Interoperabilitas & Cross-Platform**: Memahami CIL memungkinkan Anda memahami bagaimana C# dapat berjalan identik di arsitektur x64, ARM64, pada sistem operasi Linux, Windows, dan macOS tanpa mengubah logika biner.
- **Troubleshooting Tingkat Rendah**: Ketika terjadi *crash* di level sistem (seperti `ExecutionEngineException` atau *stack overflow* pada interop native P/Invoke), Anda tidak dapat mengandalkan *stack trace* C# biasa; Anda wajib memahami interaksi antara CIL dan CLR.

---

### 5. What Is It (Definisi Inti)
- **Roslyn**: Kompiler C# *open-source* berbasis API yang mengubah kode C# menjadi CIL dan menyediakan akses AST (*Abstract Syntax Tree*) untuk analisis statis.
- **CIL (Common Intermediate Language)**: Kumpulan instruksi berbasis tumpukan (*stack-based instruction set*) yang independen dari platform perangkat keras.
- **Metadata**: Tabel data terstruktur di dalam berkas PE (*Portable Executable*) .NET yang mendeskripsikan setiap tipe, metode, properti, parameter, dan dependensi program.
- **CLR (Common Language Runtime)**: Mesin eksekusi *managed* yang menyediakan lingkungan eksekusi untuk program CIL, mencakup *JIT Compiler*, *Garbage Collector*, *Type Loader*, dan *Exception Manager*.
- **Top-Level Statements**: Fitur C# (sejak C# 9) yang menyederhanakan kode *boilerplate* dengan mengabstraksi deklarasi namespace, kelas, dan metode `Main` secara formal, namun tetap dikompilasi oleh Roslyn menjadi kelas dan metode standar di balik layar.

---

### 6. How It Works (Mekanisme Kerja Internal)
Alur eksekusi dari teks kode sumber hingga instruksi CPU:

1. **Tokenisasi & Parsing (Roslyn)**:
   Source code dipecah menjadi token leksikal, dibentuk menjadi *Abstract Syntax Tree* (AST), diverifikasi terhadap aturan tipe (*binder semantic analysis*), kemudian diubah menjadi format CIL.
2. **Generasi Assembly**:
   Roslyn membungkus CIL dan Metadata ke dalam format berkas PE (Windows Portable Executable) yang portabel lintas platform (.dll).
3. **Inisialisasi CLR**:
   Ketika aplikasi dijalankan via `dotnet app.dll` atau berkas *host executable*, *CoreCLR Runtime* dimuat ke dalam memori proses sistem operasi.
4. **Verifikasi Tipe & CIL**:
   Sebelum dieksekusi, komponen *Type Loader* memuat metadata kelas, dan *Verifier* memeriksa keamanan memori dari CIL (memastikan tidak ada akses register ilegal atau penulisan memori di luar batas *managed boundary*).
5. **Kompilasi JIT (RyuJIT)**:
   - **Tier 0**: Saat metode pertama kali dipanggil, JIT menghasilkan instruksi mesin secepat mungkin dengan optimasi minimal (mengurangi waktu *startup*).
   - **Tier 1**: Jika metode tersebut sering dipanggil (*hot method*), *profiler* CLR akan mendeteksinya dan memicu kompilasi ulang di latar belakang dengan optimasi lanjutan (loop unrolling, inlining, vectorization SIMD).
6. **Eksekusi Native**: CPU mengeksekusi instruksi mesin langsung dari RAM.

---

### 7. Architecture Diagram (Diagram ASCII)

```
[ Source Code: Program.cs ]
            |
            v  (Roslyn Compiler Frontend)
[ Abstract Syntax Tree (AST) + Type Binding ]
            |
            v  (Roslyn Emitter)
+-------------------------------------------------------+
|  .NET Assembly (.dll / .exe)                          |
|  +-------------------------------------------------+  |
|  | Metadata Tables (TypeDef, MethodDef, FieldDef)  |  |
|  +-------------------------------------------------+  |
|  | Common Intermediate Language (CIL / MSIL Bytecode)| |
|  +-------------------------------------------------+  |
+-------------------------------------------------------+
            |
            | (Loaded by Operating System Process)
            v
+-------------------------------------------------------+
|  Common Language Runtime (CoreCLR Environment)        |
|                                                       |
|  +---------------------+    +----------------------+  |
|  | Class / Type Loader |    | Metadata Engine      |  |
|  +---------------------+    +----------------------+  |
|            |                                          |
|            v                                          |
|  +-------------------------------------------------+  |
|  | JIT Compiler (RyuJIT)                           |  |
|  |   - Tier 0: Quick JIT (Fast startup)           |  |
|  |   - Tier 1: Optimized JIT (Re-compilation)      |  |
|  +-------------------------------------------------+  |
|            |                                          |
|            | Compiles CIL to Native Instructions      |
|            v                                          |
|  +-------------------------------------------------+  |
|  | Execution Memory (Code Heap - Native Assembly)   |  |
|  |   - Executed directly by CPU Instructions       |  |
|  +-------------------------------------------------+  |
|            ^                                          |
|            | Memory & Lifecycle Supervision           |
|  +-------------------------------------------------+  |
|  | Garbage Collector (GC) & Execution Services     |  |
|  +-------------------------------------------------+  |
+-------------------------------------------------------+
            |
            v
[ Native CPU Execution (x64 / ARM64 Direct Execution) ]
```

---

### 8. Basic Syntax & Directives (Sintaks & Struktur Dasar)

Dalam C# modern (C# 10/11/12), sebuah aplikasi dasar dapat ditulis dalam dua paradigma:

#### A. Paradigma Eksplisit (Tradisional)
```csharp
using System;

namespace Enterprise.Architecture.Basics
{
    internal static class Program
    {
        private static void Main(string[] args)
        {
            Console.WriteLine("Entry Point Eksplisit Aktif.");
        }
    }
}
```

#### B. Paradigma Top-Level Statements (Modern)
```csharp
// Seluruh deklarasi class dan boilerplate disembunyikan oleh compiler
using System;

Console.WriteLine("Top-Level Statements Aktif.");
```

**Aturan Sintaksis Utama:**
1. Program hanya boleh memiliki **satu** *entry point*. Jika menggunakan *Top-Level Statements*, hanya boleh ada satu file di seluruh proyek yang memuat pernyataan di level root tersebut.
2. Karakter titik koma (`;`) bersifat wajib untuk terminasi *statement*.
3. C# bersifat *case-sensitive*. `Main` tidak sama dengan `main`.

---

### 9. Minimal Working Example (Contoh Kode Sederhana / Baseline)

Berikut program demonstrasi fundamental yang mencetak informasi lingkungan runtime yang diakses langsung dari API CLR:

```csharp
// Program.cs
using System;
using System.Runtime.InteropServices;

namespace CoreArchitecture
{
    public static class Program
    {
        public static void Main(string[] args)
        {
            Console.WriteLine("=== Informasi Runtime .NET ===");
            
            // Mengambil versi runtime CLR
            string frameworkDescription = RuntimeInformation.FrameworkDescription;
            
            // Mengambil arsitektur prosesor saat ini
            Architecture osArch = RuntimeInformation.OSArchitecture;
            Architecture processArch = RuntimeInformation.ProcessArchitecture;
            
            // Menampilkan informasi sistem
            Console.WriteLine($"Framework   : {frameworkDescription}");
            Console.WriteLine($"OS Arch     : {osArch}");
            Console.WriteLine($"Process Arch: {processArch}");
            Console.WriteLine($"Environment : .NET 8.0 Managed Engine");
        }
    }
}
```

---

### 10. Step-by-Step Code Walkthrough (Analisis Baris per Baris)

- **Baris 2-3 (`using System;`, `using System.Runtime.InteropServices;`)**: 
  Arahan *using* mengimpor *namespace*. Namespace adalah pengelompokan logis dari tipe (*types*). Kompiler mencari tipe seperti `Console` di `System` dan `RuntimeInformation` di `System.Runtime.InteropServices`. Ini tidak sama dengan menyertakan berkas biner (seperti `#include` di C++), melainkan sekadar resolusi nama bagi kompiler.
- **Baris 5 (`namespace CoreArchitecture`)**:
  Mendeklarasikan ruang lingkup hierarki untuk mengisolasi tipe agar tidak bentrok dengan library eksternal.
- **Baris 7 (`public static class Program`)**:
  Mendefinisikan tipe kelas penampung *entry point*. Ditandai `static` karena kelas ini tidak perlu dan tidak boleh diinstansiasi di memori *heap*.
- **Baris 9 (`public static void Main(string[] args)`)**:
  *Entry point* standar aplikasi. 
  - `public`: Dapat diakses dari luar assembly (oleh runtime host).
  - `static`: Dapat dipanggil tanpa membuat objek dari kelas `Program`.
  - `void`: Metode tidak mengembalikan kode status numerik secara langsung (berbeda dengan `int Main`).
  - `string[] args`: Array string yang menangkap argumen baris perintah dari OS shell.
- **Baris 14 (`RuntimeInformation.FrameworkDescription`)**:
  Properti statis yang membaca metadata internal CoreCLR yang sedang mengeksekusi proses, menghasilkan nilai seperti `.NET 8.0.x`.
- **Baris 17-18 (`RuntimeInformation.OSArchitecture`, `ProcessArchitecture`)**:
  Memeriksa apakah proses berjalan di mode emulasi (misal: proses x86 di atas sistem operasi x64).

---

### 11. Production-Grade / Practical Example (Implementasi Nyata / Kompleks)

Contoh berikut menyimulasikan sistem *Bootstrap Telemetry & Pre-Flight Diagnostic Checker* yang lazim digunakan pada layanan *microservices* berbasis performa tinggi sebelum menerima beban lalu lintas. Program ini menganalisis kondisi runtime, menguji integritas JIT tiering, dan menginspeksi alokasi memori GC.

```csharp
using System;
using System.Diagnostics;
using System.Reflection;
using System.Runtime;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

namespace Enterprise.Telemetry.Bootstrap
{
    public readonly record struct SystemHealthMetrics(
        string RuntimeVersion,
        string OsDescription,
        long InitialAllocatedBytes,
        bool IsServerGc,
        long JitCompilationOverheadMs
    );

    public static class PreFlightDiagnostics
    {
        public static void Main(string[] args)
        {
            Console.WriteLine("[INFO] Memulai bootstrap sistem diagnostic...");

            SystemHealthMetrics metrics = ExecuteDiagnostics();

            Console.WriteLine("--------------------------------------------------");
            Console.WriteLine($"Runtime .NET        : {metrics.RuntimeVersion}");
            Console.WriteLine($"Sistem Operasi      : {metrics.OsDescription}");
            Console.WriteLine($"Alokasi Memori Awal : {metrics.InitialAllocatedBytes:N0} bytes");
            Console.WriteLine($"Mode GC Server      : {metrics.IsServerGc}");
            Console.WriteLine($"JIT Warmup Overhead : {metrics.JitCompilationOverheadMs} ms");
            Console.WriteLine("--------------------------------------------------");

            if (metrics.InitialAllocatedBytes > 50_000_000)
            {
                Console.Error.WriteLine("[FATAL] Alokasi memori awal melampaui batas aman!");
                Environment.ExitCode = 1;
                return;
            }

            Console.WriteLine("[SUCCESS] Pre-flight system check valid. Aplikasi siap berjalan.");
            Environment.ExitCode = 0;
        }

        private static SystemHealthMetrics ExecuteDiagnostics()
        {
            var stopwatch = Stopwatch.StartNew();

            // Memaksa kompilasi JIT dari metode kalkulasi kritis sebelum dieksekusi di jalur produksi
            MethodInfo? targetMethod = typeof(PreFlightDiagnostics).GetMethod(
                nameof(CriticalKernelExecution), 
                BindingFlags.NonPublic | BindingFlags.Static
            );

            if (targetMethod != null)
            {
                // Force JIT Compilation via CLR RuntimeHelpers
                RuntimeHelpers.PrepareMethod(targetMethod.MethodHandle);
            }

            stopwatch.Stop();
            long jitCompilationTime = stopwatch.ElapsedMilliseconds;

            // Eksekusi fungsi kritis setelah di-JIT
            CriticalKernelExecution();

            long allocatedBytes = GC.GetTotalAllocatedBytes(precise: true);
            bool isServerGc = GCSettings.IsServerGC;

            return new SystemHealthMetrics(
                RuntimeVersion: RuntimeInformation.FrameworkDescription,
                OsDescription: RuntimeInformation.OSDescription,
                InitialAllocatedBytes: allocatedBytes,
                IsServerGc: isServerGc,
                JitCompilationOverheadMs: jitCompilationTime
            );
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        private static void CriticalKernelExecution()
        {
            // Simulasi proses komputasi yang tidak boleh di-inline oleh compiler
            Span<byte> buffer = stackalloc byte[256];
            for (int i = 0; i < buffer.Length; i++)
            {
                buffer[i] = (byte)(i ^ 0x5A);
            }
        }
    }
}
```

---

### 12. Edge Cases, Gotchas, and Pitfalls (Jebakan & Kasus Ekstrem)

1. **Jebakan Top-Level Statements**:
   Jika Anda menulis *Top-Level Statements*, kompiler Roslyn secara otomatis membungkusnya ke dalam method `<Main>$` di dalam kelas internal bernama `Program`. Jika Anda mencoba mendeklarasikan kelas `Program` lain di namespace default pada proyek yang sama, kompiler akan melempar kesalahan: `CS8802: Only one compilation unit can have top-level statements`.
2. **Dynamic JIT vs. Native AOT (*Ahead-Of-Time*)**:
   Jika aplikasi dikompilasi menggunakan Native AOT (`PublishAot=true`), JIT Compiler tidak disertakan di runtime. Penggunaan kode dinamis seperti `RuntimeHelpers.PrepareMethod`, `Assembly.Load`, atau `Reflection.Emit` akan memicu kegagalan runtime (*runtime crash*) atau menghasilkan pengecualian *TrimAnalysisWarning*.
3. **Penyimpangan Arsitektur Bitwise**:
   Mengabaikan target arsitektur dapat memicu kesalahan biner. Kompilasi dengan konfigurasi `Any CPU` tanpa mematikan `Prefer 32-bit` dapat menyebabkan aplikasi berjalan di mode 32-bit pada OS 64-bit, membatasi alokasi RAM proses hingga 2 GB.

---

### 13. Memory & Performance Implications (Manajemen Memori & Kinerja)

- **JIT Compilation Cost (Cold-Start Penalty)**:
  Setiap baris kode CIL harus diterjemahkan ke instruksi mesin saat pertama kali diakses. Hal ini menimbulkan biaya waktu (*time penalty*) pada *cold start*. Untuk layanan yang sensitif terhadap latensi *startup* (seperti AWS Lambda atau Azure Functions), gunakan fitur **ReadyToRun (R2R)** atau **Native AOT**.
- **Stack Allocation via `stackalloc`**:
  Pada contoh praktis, penggunaan `stackalloc` mengalokasikan array byte langsung di eksekusi *stack frame*, melewati manajemen *Garbage Collector* secara total. Ini menghasilkan performa nol alokasi (*zero-allocation*), namun rentan memicu `StackOverflowException` fatal jika ukuran alokasi melampaui batas stack thread (biasanya 1 MB di Windows atau 1.5 MB di Linux).
- **Metadata Overhead**:
  Assembly yang memiliki puluhan ribu tipe dan method metadata berukuran besar akan membebani konsumsi memori *working set* CLR bahkan sebelum aplikasi mengeksekusi instruksi pertamanya.

---

### 14. Security Considerations (Aspek Keamanan)

- **Dekompilasi CIL & Metadata Exposure**:
  Karena berkas `.dll` .NET mempertahankan seluruh metadata dan instruksi CIL standar, kode Anda sangat rentan untuk didekompilasi ke kode sumber aslinya menggunakan *decompiler* seperti ILSpy, dnSpy, atau dotPeek.
  - *Mitigasi*: Gunakan *Obfuscator* komersial jika mendistribusikan biner ke lingkungan klien yang tidak tepercaya, atau gunakan *Native AOT* yang mengompilasi biner langsung menjadi bahasa mesin tanpa menyertakan CIL.
- **Unverified Assembly Loading**:
  Memuat assembly secara arbitrer via `Assembly.LoadFile(path)` tanpa memverifikasi tanda tangan digital (*strong naming* atau *Authenticode certificate*) dapat memicu eksekusi kode berbahaya (*arbitrary code execution*) jika file DLL tersebut diubah oleh pihak ketiga.

---

### 15. Trade-offs Analysis (Analisis Kompromi / Trade-offs)

| Pendekatan | Keuntungan | Kerugian |
| :--- | :--- | :--- |
| **Top-Level Statements** | Kode bersih, minim *boilerplate*, ideal untuk script, CLI kecil, dan program mikro. | Menghilangkan kontrol eksplisit terhadap *namespace*, menyulitkan navigasi arsitektural pada basis kode monolitik besar. |
| **Explicit Entry Point (`Program.Main`)** | Struktur hierarki jelas, kompatibilitas penuh dengan sistem lama (*legacy*), kontrol visibilitas tinggi. | Terlalu banyak kode upacara (*boilerplate code*) untuk logika pemula atau program sederhana. |
| **JIT Compilation (RyuJIT Default)** | Kode dioptimasi secara adaptif terhadap CPU tempat ia dijalankan (dapat menggunakan instruksi AVX-512 jika terdeteksi). | Waktu eksekusi awal lebih lambat (*JIT overhead latency*), penggunaan memori lebih besar untuk *JIT engine*. |
| **Ahead-Of-Time (Native AOT)** | *Startup time* mendekati instan, penggunaan memori awal sangat rendah, biner mandiri (*self-contained*). | Tidak mendukung kode berbasis refleksi dinamis tanpa konfigurasi *trimming descriptor* yang rumit, ukuran berkas biner lebih besar. |

---

### 16. Antipatterns vs Best Practices (Antipola vs Pola Terbaik)

#### Antipola: Melakukan Komputasi Berat di Blok Inisialisasi Statis Entry Point
```csharp
// BURUK: Memblokir runtime loader dengan proses lambat di static constructor
public class Program 
{
    static Program() 
    {
        // Thread lock dan operasi I/O di static constructor dapat memicu deadlock
        // dan memperlambat proses bootstraping runtime
        Thread.Sleep(5000); 
    }

    public static void Main() => Console.WriteLine("Running");
}
```

#### Pola Terbaik: Menggunakan Alur Inisialisasi Eksplisit dan Asinkron
```csharp
// BAIK: Bootstrap terstruktur dengan penanganan error dan asinkronitas native
public class Program 
{
    public static async Task<int> Main(string[] args) 
    {
        try 
        {
            await InitializeSubsystemsAsync();
            Console.WriteLine("Running");
            return 0; // Mengembalikan exit code 0 menandakan kesuksesan
        } 
        catch (Exception ex) 
        {
            Console.Error.WriteLine($"Fatal Error during Bootstrap: {ex.Message}");
            return 1; // Mengembalikan non-zero ke OS host
        }
    }

    private static async Task InitializeSubsystemsAsync() 
    {
        await Task.Yield(); // Simulasi inisialisasi async non-blocking
    }
}
```

---

### 17. Debugging & Diagnostics (Teknik Debugging & Profiling)

Untuk memeriksa hasil kompilasi C# ke dalam CIL secara langsung melalui baris perintah:

1. **Kompilasi Assembly**:
   ```bash
   dotnet build -c Release
   ```
2. **Inspeksi CIL via ILDASM / ILSpy CLI**:
   Instal tool global decompilation:
   ```bash
   dotnet tool install -g ilspycmd
   ```
   Dekompresi dan lihat instruksi CIL:
   ```bash
   ilspycmd bin/Release/net8.0/CoreArchitecture.dll -il > AssemblyCIL.il
   ```
3. **Mendeteksi Kompilasi RyuJIT Menggunakan Environment Variable**:
   Jalankan program dengan menyalakan pelacakan verbose RyuJIT ke konsol:
   ```bash
   DOTNET_JitDisasm=Main dotnet run
   ```
   *Perintah ini akan mencetak kode assembly prosesor (x64/ARM) yang dihasilkan RyuJIT secara nyata ke terminal Anda.*

---

### 18. Verification & Testing (Validasi & Unit Testing)

Pengujian tingkat arsitektur (*Architecture Unit Test*) memvalidasi bahwa struktur *entry point* memenuhi kriteria standar kepatuhan sistem menggunakan pustaka pengujian standar seperti **xUnit**:

```csharp
// File: ArchitectureVerificationTests.cs
using System;
using System.Reflection;
using Xunit;
using Enterprise.Telemetry.Bootstrap;

namespace Enterprise.Tests
{
    public class RuntimeArchitectureTests
    {
        [Fact]
        public void EntryPoint_MustExist_AndHaveZeroExitCodeContract()
        {
            // Arrange
            Assembly targetAssembly = typeof(PreFlightDiagnostics).Assembly;
            MethodInfo? entryPoint = targetAssembly.EntryPoint;

            // Assert
            Assert.NotNull(entryPoint);
            Assert.True(entryPoint.IsStatic, "Entry point harus bersifat statis.");
            
            // Verifikasi parameter Main harus berupa array string atau tanpa parameter
            ParameterInfo[] parameters = entryPoint.GetParameters();
            if (parameters.Length > 0)
            {
                Assert.Equal(typeof(string[]), parameters[0].ParameterType);
            }
        }

        [Fact]
        public void ExecutionEnvironment_MustBe64BitProcess()
        {
            // Validasi lingkungan tidak boleh berjalan dalam mode kompromi 32-bit
            Assert.True(Environment.Is64BitProcess, "Aplikasi wajib dieksekusi dalam proses 64-bit.");
        }
    }
}
```

Jalankan pengujian ini via CLI:
```bash
dotnet test
```

---

### 19. Self-Assessment Exercises (Tantangan & Evaluasi Mandiri)

Lakukan dua latihan berikut untuk menguji pemahaman Anda:

#### Tantangan 1: Analisis CIL Top-Level Statement
1. Buat direktori baru dan inisialisasi aplikasi konsol sederhana:
   ```bash
   dotnet new console -n IlAnalysis
   cd IlAnalysis
   ```
2. Isi file `Program.cs` hanya dengan satu baris:
   ```csharp
   System.Console.WriteLine("Hello Internal CLR");
   ```
3. Kompilasi proyek tersebut: `dotnet build`.
4. Buka file `.dll` yang dihasilkan menggunakan *decompiler* (seperti `ilspycmd` atau alat inspeksi CIL lainnya).
5. **Pertanyaan**: Apa nama kelas dan metode asli yang digenerasikan secara otomatis oleh Roslyn untuk membungkus perintah tersebut? Jelaskan visibilitas (*access modifier*) dari kelas tersebut!

#### Tantangan 2: Diagnostik Tiered Compilation
1. Buat metode statis yang melakukan looping sederhana 1.000.000 kali.
2. Tambahkan atribut `[MethodImpl(MethodImplOptions.NoOptimization)]` pada metode tersebut.
3. Jalankan aplikasi menggunakan profil pengukuran waktu stop-watch (`System.Diagnostics.Stopwatch`).
4. Hapus atribut pembatas tersebut dan biarkan JIT melakukan Tiered Compilation.
5. Catat perbedaan waktu eksekusi antara eksekusi iterasi ke-1, iterasi ke-10, dan iterasi ke-100.000. Amati kapan optimasi JIT mulai bekerja.

---

### 20. Summary & Next Steps (Rangkuman & Modul Selanjutnya)

#### Rangkuman
- C# adalah bahasa yang dikompilasi secara *managed*. Roslyn mengubah sintaks kode menjadi format biner berstandar ECMA-335 yang berisi instruksi CIL dan Metadata.
- Common Language Runtime (CLR) adalah mesin virtual yang bertanggung jawab mengeksekusi CIL, mengonversi instruksi menjadi bahasa mesin via RyuJIT, dan mengelola alokasi serta pembersihan memori.
- Pola modern seperti *Top-Level Statements* hanyalah *syntactic sugar* tingkat tinggi; Roslyn tetap menghasilkan tipe statis dan metode *entry point* di bawah tenda biner.
- Mengetahui batas-batas eksekusi runtime, kompilasi berjenjang (Tiered JIT), dan karakteristik AOT sangat fundamental dalam merekayasa perangkat lunak berskala industri yang stabil dan berkinerja tinggi.

#### Modul Selanjutnya
Pada **Bab 01 Modul 02**, kita akan membedah secara mendalam **Sistem Tipe Terpadu (Common Type System - CTS)**: representasi memori fisik dari *Value Types* vs. *Reference Types*, perilaku memori *Stack* vs. *Heap*, serta anatomi *Object Header* dan *Method Table Pointer* pada tingkat byte.