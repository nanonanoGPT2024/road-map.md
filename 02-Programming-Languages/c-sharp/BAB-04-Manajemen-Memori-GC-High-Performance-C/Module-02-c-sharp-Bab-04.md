# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Manajemen Memori, GC & High-Performance C#**  
**Kategori: 02-Programming-Languages / C#**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menganalisis siklus hidup alokasi memori runtime .NET Core / .NET 8+ hingga tingkat instruksi mesin dan struktur heap CLR (*CoreCLR*).
- Merancang dan mengimplementasikan arsitektur berorientasi *zero-allocation* menggunakan `Span<T>`, `ReadOnlySpan<T>`, `Memory<T>`, `ref struct`, serta primitif `System.IO.Pipelines`.
- Mengontrol perilaku Garbage Collector (GC) melalui konfigurasi *Server GC*, *Workstation GC*, *Background GC*, dan mengelola memori pada *Large Object Heap* (LOH) serta *Pinned Object Heap* (POH).
- Mengintegrasikan teknik pooling objek dan buffer berkinerja tinggi menggunakan `ArrayPool<T>` dan custom memory allocators (`NativeMemory`).
- Mendiagnosis degradasi performa memori (GC pauses, memory leaks, high allocation rate, fragmentasi heap) menggunakan perkakas diagnostik enterprise (*dotnet-dump*, *dotnet-trace*, *PerfView*).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- Konsep dasar stack vs. heap, tipe nilai (*value types*) vs. tipe referensi (*reference types*).
- Sintaks modern C# (C# 10/11/12/13), manipulasi pointer dasar (`unsafe`), dan penggunaan keyword `fixed`.
- Pemrograman asinkron (`async`/`await`, `ValueTask`).
- Pemahaman dasar arsitektur CPU: L1/L2/L3 cache, cache line, CPU registers, paging, dan virtual memory OS.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Topologi Managed Heap pada CoreCLR
Runtime .NET membagi memori managed ke dalam beberapa segmen logis dan fisik:

1. **Small Object Heap (SOH):**
   - **Generation 0 (Gen 0):** Tempat alokasi objek baru berumur pendek. Alokasi di sini sangat murah karena menggunakan model *bump pointer* di dalam *Allocation Context* per-thread.
   - **Generation 1 (Gen 1):** Lapisan penyangga (*buffer zone*) antara objek berumur pendek dan panjang untuk mengurangi frekuensi pengumpulan Gen 2.
   - **Generation 2 (Gen 2):** Menampung objek *long-lived* (seperti static data, singletons, connection pools). Pengumpulan di Gen 2 dikenal sebagai *Full GC*.

2. **Large Object Heap (LOH):**
   - Menampung objek dengan ukuran $\ge 85.000$ byte.
   - Secara default tidak dikompaksi (*non-compacted*) karena biaya memindahkan blok memori besar sangat tinggi; LOH menggunakan mekanisme *free list*, yang rentan terhadap fragmentasi memori.

3. **Pinned Object Heap (POH):**
   - Diperkenalkan pada .NET 5. Menampung objek yang dialokasikan secara eksplisit dalam status tersemat (*pinned*), mencegah fragmentasi pada SOH akibat operasi interop/IO pinning.

```
+---------------------------------------------------------------------------------------+
|                                    MANAGED HEAP                                       |
+------------------------------------+--------------------------+-----------------------+
|      Small Object Heap (SOH)       | Large Object Heap (LOH)  | Pinned Obj Heap (POH) |
|  [Gen 0]  ->  [Gen 1]  ->  [Gen 2] |  (Objects >= 85,000 B)   |   (Pinned Buffers)    |
| (Ephemeral Segment / Regions)      |       (Free List)        |      (No Compact)     |
+------------------------------------+--------------------------+-----------------------+
```

### 3.2 Fase Operasi Garbage Collection
Koleksi GC dieksekusi melalui fase-fase berikut:
1. **Suspension:** Semua thread eksekusi managed dihentikan pada *Safe Points* (instruksi JIT tertentu di mana pointer GC dapat diinspeksi secara deterministik).
2. **Marking:** GC menelusuri graph objek dimulai dari *GC Roots* (CPU registers, local stack variables, static fields, interop handles). Objek yang dapat dijangkau ditandai (*live objects*). GC menggunakan *Card Table* untuk menandai referensi lintas generasi (misal Gen 2 menunjuk ke Gen 0).
3. **Plan:** Menentukan apakah pemadatan (*compaction*) atau penyapuan (*sweeping*) yang lebih menguntungkan secara matematis berdasarkan rasio fragmentasi.
4. **Sweep / Compact:**
   - *Sweep:* Memori dari objek yang mati dikembalikan ke *free list*.
   - *Compact:* Objek yang hidup digeser ke alamat memori yang bersebelahan untuk menghilangkan celah kosong (*relocation phase* memperbarui semua pointer referensi).
5. **Restart:** Thread aplikasi dilanjutkan kembali.

### 3.3 Anatomi `Span<T>` dan `ref struct`
`Span<T>` adalah representasi tipe aman (*type-safe*) dan memori aman (*memory-safe*) dari contiguous memory buffer arbitrer. Didefinisikan secara internal sebagai *ref struct*:

```csharp
public readonly ref struct Span<T>
{
    internal readonly ref T _pointer;
    private readonly int _length;
}
```

Karena merupakan `ref struct`:
- Hanya boleh hidup di Call Stack CPU (atau registers).
- Tidak pernah dialokasikan di Managed Heap (tidak dapat dibox, tidak bisa menjadi field dari class biasa, tidak bisa digunakan di dalam state machine `async`/`await`).
- Menghilangkan *pointer indirection overhead* dan *GC tracking pressure*.

---

## 4. Why & What

| Fitur / Komponen | Why (Mengapa Dibutuhkan?) | What (Apa Karakteristiknya?) |
| :--- | :--- | :--- |
| **Server GC** | Aplikasi backend membutuhkan throughput pemrosesan paralel tinggi pada multi-core CPU. | Mengalokasikan 1 heap independen dan 1 dedicated GC thread per logical core CPU. Menghilangkan lock contention antar-thread saat alokasi. |
| **Workstation GC** | Aplikasi UI / client membutuhkan latensi responsif dan konsumsi RAM serendah mungkin. | Berbagi 1 heap tunggal dan berjalan dengan prioritas thread normal. |
| **`Span<T>` & `Memory<T>`** | Operasi slicing array/string tradisional (`Substring`, `Skip`, `Take`) menghasilkan jutaan alokasi objek baru di heap. | Menyediakan abstraksi zero-allocation view ke heap, stack, atau native unmanaged memory. |
| **`System.IO.Pipelines`** | Pemrosesan stream I/O tradisional menggunakan alokasi buffer array berulang kali dan operasi salin memory yang redundan. | Pipeline read/write berbasis ring-buffer otomatis dengan koordinasi backpressure tanpa memory copy. |
| **POH (`GC.AllocateArray(..., pinned: true)`)** | Pinning objek di SOH mengunci GC compaction, menghasilkan segment holes (fragmentasi parah). | Menampung buffer I/O yang dipin langsung ke heap terisolasi khusus. |

---

## 5. How (Workflow Detail)

### Alur Eksekusi Zero-Allocation Network Pipeline
Diagram berikut mengilustrasikan alur pemrosesan data jaringan berbasis *zero-allocation* menggunakan `PipeReader`, `ReadOnlySequence<byte>`, dan `Span<byte>`:

```
[Network Socket] 
       │ (DMA / OS Buffer)
       ▼
[PipeWriter.GetMemory()] ──> Mengambil slice buffer dari MemoryPool (Pinned/Direct)
       │
       ▼
[Socket.ReceiveAsync()] ───> Menulis data langsung ke buffer tanpa intermediate byte[]
       │
       ▼
[PipeWriter.Advance()]  ───> Memperbarui head pointer buffer
       │
       ▼
[PipeReader.ReadAsync()] ──> Konsumen menerima ReadOnlySequence<byte>
       │
       ▼
[SequenceReader<byte>]  ───> Parsing frame menggunakan Span<byte> (Stack only)
       │
       ├── Frame Valid? ──> Ya: Proses Business Logic (Zero Heap Allocation)
       └── Parsed?      ──> Geser PipeReader.AdvanceTo(consumed, examined)
```

---

## 6. Analogy & Diagram ASCII

### Analogi Meja Kerja (Stack) vs. Gudang Pusat (Heap) & Petugas Kebersihan (GC)
Bayangkan Anda adalah seorang insinyur:
- **Stack:** Meja kerja pribadi Anda. Apa pun yang Anda letakkan di atas meja (variabel lokal, `Span<T>`) langsung dapat diambil secara instan tanpa birokrasi. Saat pekerjaan selesai, meja langsung bersih otomatis dengan sekali usap (Stack unwinding).
- **Heap:** Gudang raksasa bersama. Setiap kali Anda butuh tempat baru, Anda harus memanggil kurir, meminta space, dan mencatat nomor raknya.
- **Garbage Collector:** Petugas kebersihan yang datang berkala. Jika gudang penuh, ia meniup peluit (*Stop-the-World*), menghentikan seluruh aktivitas kantor, memeriksa kardus mana yang sudah tidak terpakai, membuangnya, lalu merapatkan kardus-kardus yang tersisa (*Compaction*). 

```
STACK EXECUTION (Ultra-Fast, O(1), No GC)
+------------------------------------------+
| Frame 1: Main()                          |
|   ├── int a = 10                         |
|   └── Span<byte> stackView (ref struct)  |
|       │                                  |
|       ▼                                  |
| Frame 2: ProcessData(stackView)          |
|   └── stackalloc byte[128] <─────────────┼── Allocated directly on thread stack
+------------------------------------------+
  (Automatic cleanup on function exit)

HEAP MEMORY (Slow, O(N) Cleanup via GC)
+---------------------------------------------------------------------------------+
| Gen 0 (Ephemeral)        | Gen 1              | Gen 2 (Long-Lived)              |
| [Obj A][Obj B][Obj C]    | [Obj Old1][Obj Old2] [Obj Static][DB Connection]     |
|   │       X      │       |                                                      |
|   ▼      (Dead)  ▼       |                                                      |
| Bump Pointer Allocation  | Card Tables Tracking Cross-References                |
+---------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Parsing Angka dari String Tanpa Alokasi Heap

```csharp
using System;

public class ZeroAllocParser
{
    // Mengurai format string: "KEY:VALUE|KEY:VALUE" tanpa membuat string baru / split
    public static int ExtractIntValue(string rawData, ReadOnlySpan<char> targetKey)
    {
        ReadOnlySpan<char> span = rawData.AsSpan();

        while (!span.IsEmpty)
        {
            int delimiterIndex = span.IndexOf('|');
            ReadOnlySpan<char> pair = delimiterIndex == -1 ? span : span.Slice(0, delimiterIndex);

            int colonIndex = pair.IndexOf(':');
            if (colonIndex != -1)
            {
                ReadOnlySpan<char> key = pair.Slice(0, colonIndex);
                ReadOnlySpan<char> value = pair.Slice(colonIndex + 1);

                if (key.SequenceEqual(targetKey))
                {
                    return int.Parse(value); // .NET 7/8/9 int.Parse mendukung ReadOnlySpan<char>
                }
            }

            if (delimiterIndex == -1) break;
            span = span.Slice(delimiterIndex + 1);
        }

        return -1;
    }
}
```

### 7.2 Practical Example: Custom Zero-Allocation Binary Protocol Deserializer

```csharp
using System;
using System.Buffers;
using System.Buffers.Binary;
using System.IO.Pipelines;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;

// Layout Paket Biner Transaksi Finansial (Total 32 Bytes):
// [0..3]   : Magic Number (0xDEADBEEF) -> 4 Bytes
// [4..11]  : AccountId (Int64)         -> 8 Bytes
// [12..19] : Amount (Int64, Fixed-Point)-> 8 Bytes
// [20..23] : TransactionType (Int32)  -> 4 Bytes
// [24..31] : Checksum (Int64)         -> 8 Bytes

[StructLayout(LayoutKind.Sequential, Pack = 1)]
public readonly record struct FinancialTransaction
{
    public readonly uint Magic;
    public readonly long AccountId;
    public readonly long Amount;
    public readonly int TransactionType;
    public readonly long Checksum;

    public FinancialTransaction(uint magic, long accountId, long amount, int transactionType, long checksum)
    {
        Magic = magic;
        AccountId = accountId;
        Amount = amount;
        TransactionType = transactionType;
        Checksum = checksum;
    }
}

public sealed class TransactionPipelineProcessor
{
    private const uint EXPECTED_MAGIC = 0xDEADBEEF;
    private const int PACKET_SIZE = 32;

    public async Task ProcessStreamAsync(PipeReader reader, CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            ReadResult result = await reader.ReadAsync(ct);
            ReadOnlySequence<byte> buffer = result.Buffer;

            while (TryReadTransaction(ref buffer, out FinancialTransaction transaction))
            {
                DispatchTransaction(in transaction);
            }

            // Laporkan data yang sudah dikonsumsi dan dievaluasi
            reader.AdvanceTo(buffer.Start, buffer.End);

            if (result.IsCompleted)
            {
                break;
            }
        }
    }

    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    private static bool TryReadTransaction(ref ReadOnlySequence<byte> sequence, out FinancialTransaction tx)
    {
        tx = default;

        if (sequence.Length < PACKET_SIZE)
        {
            return false;
        }

        // Jika data terfragmentasi di lintas segmen sequence, gunakan buffer lokal stackalloc
        Span<byte> localBuffer = stackalloc byte[PACKET_SIZE];

        ReadOnlySpan<byte> transactionBytes;
        if (sequence.FirstSpan.Length >= PACKET_SIZE)
        {
            transactionBytes = sequence.FirstSpan.Slice(0, PACKET_SIZE);
        }
        else
        {
            sequence.Slice(0, PACKET_SIZE).CopyTo(localBuffer);
            transactionBytes = localBuffer;
        }

        uint magic = BinaryPrimitives.ReadUInt32BigEndian(transactionBytes.Slice(0, 4));
        if (magic != EXPECTED_MAGIC)
        {
            throw new InvalidDataException($"Corrupted packet magic: 0x{magic:X}");
        }

        long accountId = BinaryPrimitives.ReadInt64BigEndian(transactionBytes.Slice(4, 8));
        long amount = BinaryPrimitives.ReadInt64BigEndian(transactionBytes.Slice(12, 8));
        int txType = BinaryPrimitives.ReadInt32BigEndian(transactionBytes.Slice(20, 4));
        long checksum = BinaryPrimitives.ReadInt64BigEndian(transactionBytes.Slice(24, 8));

        // Validasi checksum XOR sederhana
        long calculatedChecksum = accountId ^ amount ^ txType;
        if (calculatedChecksum != checksum)
        {
            throw new InvalidDataException("Transaction checksum mismatch");
        }

        tx = new FinancialTransaction(magic, accountId, amount, txType, checksum);
        sequence = sequence.Slice(PACKET_SIZE);
        return true;
    }

    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    private static void DispatchTransaction(in FinancialTransaction tx)
    {
        // Eksekusi logic tanpa boxing/alokasi memori
        // Parameter dilewatkan via referensi 'in' untuk menghindari penyalinan struct 32 bytes
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Ultra-Low Latency Market Data Feed Handler (FinTech)
- **Karakteristik Beban:** Ingesti 850.000 pesan UDP per detik dari bursa efek.
- **Masalah Utama:** Setiap pesan bursa dialokasikan sebagai objek `class MarketTick`. Hal ini memicu GC Gen 0 setiap 50 ms dan GC Gen 2 (Full GC) setiap 40 detik dengan pause time rata-rata 120 ms. Akibatnya, terjadi buffer overflow pada socket UDP kernel OS (*packet drop* mencapai 4.2%).
- **Arsitektur Solusi:**
  1. Mengubah struktur parsing dari reference type (`class`) ke unmanaged `readonly struct` yang dialokasikan di stack atau buffer array pre-allocated.
  2. Mengaktifkan **Server GC** dengan mode background di `runtimeconfig.json`.
  3. Memanfaatkan **POH (`Pinned Object Heap`)** untuk mengalokasikan receive buffer socket UDP permanen.
  4. Menerapkan `ArrayPool<byte>.Shared` untuk pesan berukuran variabel.

```xml
<!-- Konfigurasi runtime produksi (App.runtimeconfig.json) -->
{
  "runtimeOptions": {
    "configProperties": {
      "System.GC.Server": true,
      "System.GC.Concurrent": true,
      "System.GC.HeapHardLimit": 8589934592, <!-- 8 GB -->
      "System.GC.LOHThreshold": 100000,
      "System.GC.NoAffinitize": false
    }
  }
}
```

- **Hasil Metrik:**
  - Alokasi memori berkurang dari **4.2 GB/detik** menjadi **< 15 KB/detik**.
  - Gen 0 / Gen 1 Collections berkurang sebesar **99.8%**.
  - GC Gen 2 Pause Time turun dari **120 ms** menjadi **0 ms** (tidak ada alokasi yang meloloskan objek ke Gen 2 selama trading hours).
  - Socket packet drops turun menjadi **0%**.

---

## 9. Trade-offs

| Pendekatan | Keuntungan | Biaya / Konsekuensi (*Drawbacks*) |
| :--- | :--- | :--- |
| **`ArrayPool<T>`** | Mengurangi beban GC drastis dengan mendaur ulang array berukuran besar. | Kerentanan *Use-After-Free*, memori kotor (*dirty memory*) jika buffer tidak dibersihkan (`clear: true`), dan kebocoran buffer jika tidak di-return dalam blok `finally`. |
| **`ref struct` (`Span<T>`)** | Eksekusi deterministik di stack, zero overhead GC. | Keterbatasan arsitektural: Tidak dapat dijadikan field pada class, tidak bisa ditangkap (*captured*) oleh lambda, tidak bisa digunakan melintasi boundary method `async`. |
| **Server GC** | Throughput maksimal pada lingkungan multi-threaded enterprise. | Penggunaan base memory (RAM footprint) jauh lebih tinggi karena managed heap diduplikasi sebanyak jumlah core CPU. |
| **POH (Pinned Objects)** | Menghindari fragmentasi SOH dan overhead `GCHandle.Alloc`. | Objek di POH tidak akan pernah dipindahkan/dikompaksi; alokasi dan dealokasi sembarangan pada POH dapat menimbulkan fragmentasi virtual address space. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Anti-Pattern 1: Hidden Boxing dan Closure Allocations
Seringkali developer mengira kodenya sudah *zero-allocation*, padahal kompiler menyisipkan alokasi heap secara implisit.

```csharp
// SALAH: Terjadi alokasi Heap akibat lambda closure capture
public void Process(int threshold)
{
    // Kompiler membuat instance class DisplayClass tersembunyi di Heap untuk menampung 'threshold'
    _items.Find(x => x.Price > threshold); 
}

// BENAR: Gunakan static lambda atau state-based pass
public void ProcessOptimized(int threshold)
{
    // Menggunakan overload yang menerima argumen state (tidak ada heap allocation)
    _items.Find(static (item, thresh) => item.Price > thresh, threshold);
}
```

### 10.2 Anti-Pattern 2: Memory Leak melalui Penggunaan `ArrayPool<T>` yang Tidak Mengembalikan Buffer
Jika developer meminjam buffer dari pool namun gagal mengembalikannya saat terjadi exception:

```csharp
// SALAH: Jika method throw exception, buffer hilang selamanya dari pool (leak)
byte[] buffer = ArrayPool<byte>.Shared.Rent(4096);
DoRiskyOperation(buffer);
ArrayPool<byte>.Shared.Return(buffer);

// BENAR: Gunakan idiom try-finally deterministik
byte[] buffer = ArrayPool<byte>.Shared.Rent(4096);
try
{
    DoRiskyOperation(buffer);
}
finally
{
    ArrayPool<byte>.Shared.Return(buffer, clearArray: false);
}
```

### 10.3 Troubleshooting GC Pauses dengan CLI Tools
Jika sistem mengalami freeze berkala akibat GC:
1. **Analisis Profil Alokasi:**
   ```bash
   dotnet-trace collect --profile gc-collect --process-id <PID>
   ```
2. **Inspeksi Heap Dump:**
   ```bash
   dotnet-dump collect --process-id <PID>
   dotnet-dump analyze <dump_file>
   > dumpheap -stat
   > dumpheap -min 85000 # Mengecek objek LOH
   > gcwhere <Object_Address> # Mengecek lokasi generasi heap
   ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Gunakan `ValueTask<T>`** untuk path asynchronous yang sering selesai secara sinkron (menghilangkan alokasi objek `Task`).
- [ ] **Hindari Pinned Pointers (`fixed`) Jangka Panjang pada SOH:** Gunakan `GC.AllocateArray<T>(..., pinned: true)` jika buffer harus tetap di alamat yang sama dalam waktu lama.
- [ ] **Gunakan `String.Create`** untuk formatting string kompleks daripada operasi string concatenation `+` atau `StringBuilder` sekali pakai.
- [ ] **Atur Kapasitas Awal Collections:** Selalu inisialisasi `new List<T>(capacity)` atau `new Dictionary<K, V>(capacity)` jika ukurannya dapat diprediksi untuk menghindari realokasi internal array berulang kali.
- [ ] **Gunakan `in` modifier** pada struct berukuran lebih besar dari pointer arsitektur (16 bytes) saat dilewatkan sebagai parameter method untuk menghindari penyalinan data memori.
- [ ] **Monitor Alokasi di CI/CD Pipeline:** Terapkan automated testing berbasis memory assert menggunakan library `BenchmarkDotNet` dengan atribut `[MemoryDiagnoser]`.

---

## 12. Hands-on Practice

Buat dan simpan proyek praktikum ini di direktori `hands-on/m02/` dengan struktur:
```
hands-on/m02/
├── HighPerfMemory.csproj
└── Program.cs
```

### Langkah 1: Inisialisasi Proyek
```bash
mkdir -p hands-on/m02
cd hands-on/m02
dotnet new console -n HighPerfMemory --force
```

### Langkah 2: Edit `HighPerfMemory.csproj`
Pastikan runtime diatur untuk performa tinggi:
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <AllowUnsafeBlocks>true</AllowUnsafeBlocks>
    <ServerGarbageCollection>true</ServerGarbageCollection>
  </PropertyGroup>
</Project>
```

### Langkah 3: Implementasikan `Program.cs`
Salin kode berikut yang menguji performa pooling dan manipulasi stack allocation:

```csharp
using System;
using System.Buffers;
using System.Diagnostics;
using System.Runtime.CompilerServices;

namespace HighPerfMemory;

class Program
{
    private const int ITERATIONS = 1_000_000;
    private const int BUFFER_SIZE = 1024; // 1 KB

    static void Main(string[] args)
    {
        Console.WriteLine("=== Memory Optimization Benchmarking ===");
        
        // 1. Uji Pendekatan Tradisional (Naive Heap Allocation)
        long memBefore1 = GC.GetAllocatedBytesForCurrentThread();
        Stopwatch sw1 = Stopwatch.StartNew();
        RunNaiveAllocation();
        sw1.Stop();
        long memAfter1 = GC.GetAllocatedBytesForCurrentThread();
        
        // 2. Uji Pendekatan Modern (ArrayPool)
        long memBefore2 = GC.GetAllocatedBytesForCurrentThread();
        Stopwatch sw2 = Stopwatch.StartNew();
        RunPooledAllocation();
        sw2.Stop();
        long memAfter2 = GC.GetAllocatedBytesForCurrentThread();

        // 3. Uji Pendekatan Stackalloc (Ref Struct / Zero Alloc)
        long memBefore3 = GC.GetAllocatedBytesForCurrentThread();
        Stopwatch sw3 = Stopwatch.StartNew();
        RunStackAllocation();
        sw3.Stop();
        long memAfter3 = GC.GetAllocatedBytesForCurrentThread();

        Console.WriteLine($"\n[1] Naive Heap Allocation:");
        Console.WriteLine($"    Time : {sw1.ElapsedMilliseconds} ms");
        Console.WriteLine($"    Alloc: {(memAfter1 - memBefore1) / 1024 / 1024} MB");

        Console.WriteLine($"\n[2] Pooled Allocation (ArrayPool):");
        Console.WriteLine($"    Time : {sw2.ElapsedMilliseconds} ms");
        Console.WriteLine($"    Alloc: {(memAfter2 - memBefore2) / 1024} KB");

        Console.WriteLine($"\n[3] Stack Allocation (stackalloc):");
        Console.WriteLine($"    Time : {sw3.ElapsedMilliseconds} ms");
        Console.WriteLine($"    Alloc: {(memAfter3 - memBefore3)} Bytes");
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    static void RunNaiveAllocation()
    {
        for (int i = 0; i < ITERATIONS; i++)
        {
            byte[] buffer = new byte[BUFFER_SIZE];
            buffer[0] = (byte)(i & 0xFF);
            Consume(buffer);
        }
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    static void RunPooledAllocation()
    {
        ArrayPool<byte> pool = ArrayPool<byte>.Shared;
        for (int i = 0; i < ITERATIONS; i++)
        {
            byte[] buffer = pool.Rent(BUFFER_SIZE);
            try
            {
                buffer[0] = (byte)(i & 0xFF);
                Consume(buffer);
            }
            finally
            {
                pool.Return(buffer);
            }
        }
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    static void RunStackAllocation()
    {
        for (int i = 0; i < ITERATIONS; i++)
        {
            Span<byte> buffer = stackalloc byte[BUFFER_SIZE];
            buffer[0] = (byte)(i & 0xFF);
            ConsumeSpan(buffer);
        }
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    static void Consume(byte[] data)
    {
        // Simulasi konsumsi data
        if (data[0] == 255) Console.Write("");
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    static void ConsumeSpan(ReadOnlySpan<byte> data)
    {
        // Simulasi konsumsi data
        if (data[0] == 255) Console.Write("");
    }
}
```

### Langkah 4: Jalankan dalam Konfigurasi Release
```bash
dotnet run -c Release
```

---

## 13. Exercise

### Level Easy: String Parsing dengan `ReadOnlySpan<char>`
Ubah fungsi parse URL query berikut agar tidak menghasilkan alokasi string sama sekali pada heap untuk key dan value:
- **Input:** `"name=john&role=admin&env=prod"`
- **Tugas:** Buat method `ParseQuery(ReadOnlySpan<char> query, Span<KeyValuePair> results)` yang mengisi pasangan key dan value menggunakan struct non-allocating.

### Level Medium: Custom Chunking Stream Reader Menggunakan `Memory<T>`
Buat pembaca file berbasis chunk yang membaca blok data 64 KB menggunakan `FileStream` dan membaginya ke dalam unit parsing 4 KB menggunakan `Memory<byte>` dan `Slice()` tanpa menyalin byte array asli.

### Level Hard: Lock-Free High-Performance Object Pool
Implementasikan class `LockFreeObjectPool<T> where T : class, new()` menggunakan struktur array internal dengan operasi interlocked (`Interlocked.CompareExchange`) tanpa menggunakan lock/monitor statements. Pool harus aman digunakan oleh ratusan thread konkuren secara bersamaan dengan fallback alokasi otomatis jika pool kosong.

---

## 14. Challenge

### Skenario Kasus: Implementasi Ring Buffer untuk High-Frequency Logging Engine
Perusahaan telekomunikasi membutuhkan komponen in-memory circular buffer (Ring Buffer) untuk menampung event audit logging jaringan dengan throughput minimal **10.000.000 log events per detik**.

**Kriteria Tantangan:**
1. **Zero-Allocation Post-Initialization:** Setelah aplikasi startup, siklus penulisan dan pembacaan log tidak boleh memicu GC sama sekali ($0$ Bytes allocated pada managed heap).
2. **Kapasitas Statis:** Buffer memiliki ukuran slot statis (misal: $2^{20} = 1.048.576$ item). Gunakan bitwise masking (`sequence & (capacity - 1)`) untuk kalkulasi slot index.
3. **Thread Safety:** Aman untuk skenario *Multi-Producer Single-Consumer* (MPSC).
4. **Data Overwrite Prevention:** Produsen tidak boleh menimpa slot yang belum selesai diproses oleh konsumen (*backpressure handling*).
5. **No Locks:** Tidak boleh menggunakan `lock`, `Monitor`, `Mutex`, atau `ReaderWriterLockSlim`. Harus diselesaikan menggunakan atomic operations (`Interlocked` / volatile memory barriers).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. Di generasi heap manakah objek yang baru pertama kali dialokasikan di runtime .NET akan ditempatkan?  
   a. Gen 2  
   b. Gen 1  
   c. Gen 0  
   d. POH  

2. Berapa batas ukuran ambang batas (*threshold*) default bagi suatu objek untuk dialokasikan langsung ke Large Object Heap (LOH)?  
   a. 32.768 bytes  
   b. 65.536 bytes  
   c. 85.000 bytes  
   d. 1.048.576 bytes  

3. Apa karakteristik utama dari tipe data yang dideklarasikan dengan keyword `ref struct`?  
   a. Selalu dialokasikan di Large Object Heap.  
   b. Hanya boleh dialokasikan pada stack eksekusi dan tidak dapat hidup di heap.  
   c. Menjadi thread-safe secara otomatis di seluruh thread.  
   d. Dapat diwarisi (*inherited*) oleh class lain.  

4. Mengapa alokasi objek pada LOH dapat menyebabkan masalah performa pada aplikasi jangka panjang?  
   a. Objek di LOH langsung dihapus saat Gen 0 dikoleksi.  
   b. LOH secara default tidak dikompaksi (*compacted*), sehingga rentan memicu fragmentasi memori.  
   c. LOH hanya dapat menampung tipe data primitif `int` dan `byte`.  
   d. Akses CPU cache L1 tidak mendukung memori LOH.  

5. Manakah konfigurasi GC yang mengalokasikan managed heap independen untuk setiap logical CPU core?  
   a. Workstation Non-Concurrent GC  
   b. Server GC  
   c. Workstation Background GC  
   d. Low Latency Client GC  

---

### Bagian 2: Intermediate (Pilihan Ganda)

6. Apa bahaya utama jika Anda menyematkan (*pinning*) pointer memori pada objek di Small Object Heap (SOH) dalam waktu yang lama menggunakan `GCHandleType.Pinned`?  
   a. Memicu exception `AccessViolationException`.  
   b. Mencegah GC memadatkan (*compacting*) memori di sekitar objek tersebut, menciptakan fragmentasi ("holes") di heap.  
   c. Mengubah tipe objek menjadi value type.  
   d. Memaksa GC menaikkan generasi objek langsung ke Gen 2 seketika.  

7. Kapan Anda harus menggunakan `Memory<T>` dibandingkan `Span<T>`?  
   a. Ketika performa yang diinginkan adalah absolut zero-overhead.  
   b. Ketika Anda perlu menyimpan referensi buffer di dalam class biasa atau melintasi boundary method `async`/`await`.  
   c. Ketika ukuran buffer melebihi 2 GB.  
   d. Ketika memori buffer dialokasikan menggunakan `stackalloc`.  

8. Apa efek pemanggilan `ArrayPool<T>.Shared.Return(buffer, clearArray: true)` pada performa dan keamanan sistem?  
   a. Mengosongkan buffer dengan menuliskan nilai default/nol sehingga data sensitif bersih, tetapi menambah sedikit overhead CPU cycle.  
   b. Menghapus referensi array dari memory fisik OS seketika.  
   c. Memicu Full GC Gen 2 secara instan.  
   d. Menjamin buffer tidak akan pernah dipinjamkan ke thread lain lagi.  

9. Apa fungsi dari struktur data *Card Table* di dalam CoreCLR GC?  
   a. Menyimpan mapping alamat memori ke virtual disk swap.  
   b. Melacak modifikasi pointer antar-generasi (misalnya pointer dari objek di Gen 2 yang menunjuk ke objek di Gen 0) agar GC tidak perlu memindai seluruh Gen 2 saat melakukan Gen 0 collection.  
   c. Mencatat pool buffer yang tersedia di `ArrayPool<T>`.  
   d. Mengatur alokasi thread ID pada Server GC.  

10. Mengapa method bertipe `async Task` dapat menimbulkan overhead alokasi memori heap meskipun tidak ada data yang dikembalikan?  
    a. Kompiler C# selalu membuat instance state machine class (`<MethodName>d__1`) di heap jika eksekusi harus menunggu operasi asynchronous yang belum selesai (*yields*).  
    b. Runtime menduplikasi seluruh stack memory ke Gen 2.  
    c. Network card OS mengalokasikan LOH untuk setiap task.  
    d. Tipe data `Task` secara default dialokasikan di Pinned Object Heap.  

---

### Bagian 3: Skenario Kasus Produksi

11. **Skenario:** Aplikasi payment gateway berbasis microservice di Kubernetes sering mengalami status *OOMKilled* (Out Of Memory Killed) oleh Linux CGroup, padahal metrik monitoring APM menunjukkan *Allocated Memory* aplikasi di .NET hanya tercatat 400 MB dari limit 1 GB container.  
    **Analisis:** Apa akar penyebab paling logis dari fenomena ini dan bagaimana konfigurasi runtime yang tepat untuk memperbaikinya?  

12. **Skenario:** Tim backend high-frequency trading mengeluhkan latensi respons API melonjak (*spike*) dari 2 ms menjadi 350 ms setiap 15 menit sekali. Setelah dicek via PerfView, lonjakan tersebut bertepatan dengan fase `GC (Gen 2) Mark-Sweep-Compact`.  
    **Analisis:** Langkah arsitektural dan optimasi kode C# apa saja yang wajib dilakukan untuk mengeliminasi GC pause Gen 2 tersebut?  

13. **Skenario:** Sebuah fungsi pengurai log firewall memproses file CSV sebesar 20 GB. Kode saat ini menggunakan `File.ReadAllLines()` lalu melakukan string `.Split(',')`. Server mengalami crash dengan `OutOfMemoryException`.  
    **Analisis:** Rancanglah arsitektur pembacaan file baru yang dapat memproses seluruh file tersebut dengan konsumsi RAM konstan di bawah 20 MB!  

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Kunci Bagian 1
1. **c** - Objek baru selalu dialokasikan di Gen 0 (kecuali ukurannya $\ge 85.000$ bytes atau secara eksplisit dialokasikan di POH).
2. **c** - 85.000 bytes adalah ambang batas standar CoreCLR untuk LOH.
3. **b** - `ref struct` hanya valid di stack frame memori dan dicegah oleh type system compiler untuk pindah ke heap.
4. **b** - LOH menggunakan alokasi free list tanpa kompaksi standar, menyebabkan fragmentasi jika alokasi/dealokasi dilakukan dinamis.
5. **b** - Server GC membuat heap dan dedicated GC thread independen per logical core CPU.

#### Kunci Bagian 2
6. **b** - Pinning di SOH memaksa GC membiarkan objek tersebut diam di tempatnya; GC tidak bisa menggeser objek lain melewati titik pin tersebut saat fase compaction.
7. **b** - `Memory<T>` bukan `ref struct`, sehingga bisa disimpan sebagai field class atau digunakan dalam async state machines.
8. **a** - Menghindari *data leak* antar-peminjam buffer dengan membersihkan memori, dengan trade-off sedikit instruksi CPU tambahan.
9. **b** - Card table adalah mekanisme optimasi pelacakan referensi silang generasi memori (*ephemeral GC helper*).
10. **a** - State machine asynchronous harus dipindahkan ke heap jika operasi I/O belum selesai (*asynchronous suspension*).

#### Panduan Jawaban Bagian 3 (Skenario Kasus)
11. **Analisis Solusi:**  
    Penyebabnya adalah **Server GC memory footprint** dan ketidaksesuaian deteksi memory limit container. Secara default, Server GC mengalokasikan segment heap besar di muka untuk setiap core. Jika container diberi 16 virtual core tetapi limit RAM hanya 1 GB, GC mengira ia memiliki hak atas seluruh RAM node host, sehingga GC tidak terpicu cukup sering sebelum melanggar limit CGroup.  
    *Solusi:* Atur `DOTNET_GCHeapHardLimitPercent` atau `DOTNET_GCHeapHardLimit=0x3E800000` (1000 MB) pada environment variable Docker, atau ubah konfigurasi ke Workstation GC jika throughput CPU per container tidak masif.

12. **Analisis Solusi:**  
    Penyebabnya adalah objek-objek berumur menengah (*medium-lived*) yang terus-menerus lolos dari Gen 0 ke Gen 1 lalu tertahan di Gen 2, memicu Full GC compaction pause.  
    *Solusi:*  
    - Ganti seluruh DTO transient dengan `readonly struct` atau pooled buffers (`ArrayPool<byte>`).
    - Pastikan koneksi atau resource eksternal bersifat static singleton, bukan transient.
    - Ubah mode GC ke `System.GC.Concurrent=true` (Background GC) untuk memproses Gen 2 secara paralel tanpa mematikan thread eksekusi utama, atau gunakan mode GC `LatencySettings.SustainedLowLatency` selama jam transaksi aktif.

13. **Analisis Solusi:**  
    `File.ReadAllLines` memuat seluruh 20 GB string ke heap sekaligus.  
    *Solusi Arsitektur Baru:*  
    - Gunakan `FileStream` dengan ukuran buffer 64 KB.
    - Bungkus stream dengan `System.IO.Pipelines.PipeReader`.
    - Lakukan parsing byte-per-byte atau baris-per-baris menggunakan `ReadOnlySpan<byte>` dan `SequenceReader<byte>`.
    - Parsing angka/token langsung dari span byte tanpa membuat objek `string` (`Utf8Parser.TryParse`). RAM yang digunakan hanya sebatas buffer sliding window pipeline (< 1 MB).

---

## 16. Summary

1. **Topologi Memori CLR:** Terdiri dari SOH (Gen 0, Gen 1, Gen 2), LOH ($\ge 85$ KB), dan POH (Pinned). Memahami pergerakan objek antar generasi adalah fondasi tuning performa tingkat enterprise.
2. **Karakteristik GC:** Server GC memaksimalkan throughput backend paralel dengan multi-heap; Workstation GC meminimalkan jejak footprint memori.
3. **Zero-Allocation Primitives:** Penggunaan `Span<T>`, `ReadOnlySpan<T>`, dan `ref struct` memungkinkan developer memproses slice data langsung di stack atau unmanaged memory tanpa overhead alokasi managed heap.
4. **Buffer Pooling & Pipelines:** `ArrayPool<T>` dan `System.IO.Pipelines` adalah fondasi sistem I/O modern berkemampuan jutaan request per detik, mengubah paradigma *allocate-per-request* menjadi *rent-and-reuse*.
5. **Observabilitas Berkelanjutan:** Optimasi performa bukan tebakan; analisis mendalam menggunakan metrik profiling (`dotnet-trace`, `dotnet-dump`, Card Tables, GC Pauses) adalah syarat mutlak engineering sistem kelas enterprise.