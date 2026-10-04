# BAB 01: Fondasi dan Arsitektur
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis Runtime Execution Engine CLR**: Membedah siklus hidup eksekusi kode C# dari Common Intermediate Language (CIL), JIT Compilation (Tiered Compilation, Dynamic PGO), hingga native machine code.
2. **Menguasai Memory Layout & Type System Internals**: Memahami tata letak memori fisik (*SyncBlock Index*, *MethodTable Pointer*, *Field Padding/Alignment*) dari tipe data referensi (*Reference Types*) dan tipe data nilai (*Value Types*).
3. **Mengeliminasi Alokasi Memori Heap**: Mengimplementasikan arsitektur berorientasi performa tinggi menggunakan abstraksi modern seperti `Span<T>`, `ReadOnlySpan<T>`, `Memory<T>`, `ref struct`, serta memitigasi *boxing/unboxing* terselubung.
4. **Mengisolasi dan Mengelola Lifecycle Assembly**: Merancang sistem modular berbasis `AssemblyLoadContext` yang mendukung *dynamic assembly loading/unloading* secara aman tanpa *memory leak*.
5. **Menerapkan Profiling & Benchmarking Standar Industri**: Melakukan diagnosa alokasi memori dan bottleneck komputasi menggunakan `BenchmarkDotNet`, `dotnet-dump`, dan SOS Debugging Extension.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Sintaksis dasar hingga menengah C# (Class, Struct, Interface, Generics).
* Pemahaman fundamental mengenai Stack vs Heap.
* Penggunaan .NET CLI (`dotnet build`, `dotnet run`, `dotnet test`).
* Konsep dasar arsitektur sistem komputer (register CPU, pointer, cache hierarchy L1/L2/L3, memory alignment).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Common Language Runtime (CLR) Execution Engine
CLR bukan sekadar *virtual machine interpreter*, melainkan lingkungan eksekusi *hybrid* bertingkat (*Tiered Execution Environment*). 

```
[Source Code: C#]
       │
       ▼ (Roslyn Compiler: csc)
[Assembly: IL (CIL) + Metadata]
       │
       ▼ (Assembly Loader & Type Loader)
[Execution Engine (EE) CoreCLR]
       │
       ├─► Verification & Security Check
       ├─► MethodTable & Virtual Stub Dispatch Setup
       │
       ▼ (Tiered JIT Compiler)
 ┌────────────────────────────────────────────────────────┐
 │  Tier 0 (Quick JIT) ──> Native Code (No Optimizations) │
 │         │                                              │
 │         ▼ Call Count Threshold Hit (~30 calls)         │
 │  Tier 1 (Optimized JIT) ──> Loop Unrolling, Inlining   │
 │         │                                              │
 │         ▼ Dynamic PGO Enabled (.NET 8+)                │
 │  Tier 1 PGO ──> Profile-Guided Optimized Code          │
 └────────────────────────────────────────────────────────┘
       │
       ▼
[CPU Execution: AMD64 / ARM64]
```

* **Roslyn Compiler**: Mengubah kode C# menjadi instruksi *Intermediate Language* (CIL) dan tabel Metadata berbasis format ECMA-335.
* **Tiered JIT Compilation**:
  * **Tier 0 (Quick JIT)**: Menghasilkan kode mesin secepat mungkin dengan meminimalkan atau menonaktifkan optimasi (tanpa *inlining*, tanpa *loop unrolling*). Tujuannya adalah meminimalkan waktu startup aplikasi.
  * **Tier 1 (Optimized JIT)**: Jika suatu metode dipanggil berulang kali melampaui ambang batas (*execution count*), JIT compiler memasukkan metode tersebut ke dalam antrean *recompilation* di latar belakang untuk menerapkan optimasi agresif.
  * **Dynamic PGO (Profile-Guided Optimization)**: Diperkenalkan dan diaktifkan secara default pada .NET 8. CLR menginjeksikan probe profil ke dalam Tier 0 untuk mengamati tipe data riil yang melewati *interface dispatch*, probabilitas *branching*, serta ukuran loop, lalu menyusun native code Tier 1 dengan *speculative devirtualization*.

#### 3.2 Anatomi Memori Heap: Layout Reference Type
Setiap objek yang dialokasikan di Managed Heap memiliki overhead struktural internal selain data dari field yang didefinisikan.

Pada arsitektur 64-bit (x64):
1. **Object Header / SyncBlock Index (8 bytes)**: Digunakan untuk sinkronisasi thread primitif (`Monitor.Enter`/`lock`), menyimpan *hash code* bawaan objek, serta tracking metadata GC.
2. **MethodTable Pointer / TypeHandle (8 bytes)**: Menunjuk ke `MethodTable` kelas tersebut di unmanaged domain memory, berisi *virtual method table (VTable)*, ukuran tipe data, referensi interface, dan informasi GC pointers.
3. **Instance Fields Data**: Field-field instansial yang disusun berdasarkan aturan alignment CPU. Objek referensi kosong membutuhkan minimum 24 bytes (8 byte SyncBlock + 8 byte MethodTable + 8 byte padding minimum heap allocation limit).

```
Object Instance in Heap (x64):
┌────────────────────────────────────────┬────────┐
│ Field / Segment                        │ Ukuran │
├────────────────────────────────────────┼────────┤
│ Object Header (SyncBlock Index / Hash) │ 8 byte │
├────────────────────────────────────────┼────────┤
│ MethodTable* (TypeHandle)              │ 8 byte │
├────────────────────────────────────────┼────────┤
│ Instance Fields (Disusun oleh CLR)    │ N byte │
├────────────────────────────────────────┼────────┤
│ Padding (8-byte boundary alignment)    │ 0-7 byte│
└────────────────────────────────────────┴────────┘
```

#### 3.3 Anatomi Memori Stack: Layout Value Type
Value Type (`struct`) yang dialokasikan pada stack **tidak** memiliki *Object Header* maupun *MethodTable Pointer*. 

Jika struct dideklarasikan:
```csharp
public struct Transaction
{
    public byte Status; // 1 byte
    public long Amount; // 8 bytes
    public int Id;      // 4 bytes
}
```
Tanpa deklarasi layout eksplisit, CLR mengimplementasikan `LayoutKind.Auto` (atau `Sequential` secara default pada struct C#), dengan aturan alignment CPU (secara native 8 byte pada x64):
* `Status` diletakkan pada offset 0.
* CLR menambahkan padding 7 bytes agar `Amount` (8 bytes) berada pada offset kelipatan 8 (offset 8).
* `Id` diletakkan pada offset 16 (4 bytes).
* Ditambahkan padding 4 bytes pada akhir struct agar total ukuran struct (24 bytes) merupakan kelipatan dari alignment terbesar (8 bytes).

#### 3.4 Virtual Stub Dispatch (VSD) & Interface Dispatch
Pemanggilan metode virtual menggunakan indeks tabel (*VTable offset*). Namun, pemanggilan metode melalui interface (`IFoo.Bar()`) tidak dapat menggunakan offset statis karena class yang berbeda dapat mengimplementasikan interface yang sama pada slot VTable yang berbeda. CLR memecahkan masalah ini menggunakan **Virtual Stub Dispatch**:
1. **Lookup Stub**: Melakukan pengecekan hash table pencarian tipe runtime vs slot interface.
2. **Monomorphic Cache Stub**: Jika CLR mendeteksi pemanggilan interface tersebut selalu berasal dari kelas konkret yang sama (*monomorphic call-site*), stub di-rewrite menjadi *direct pointer branch*.
3. **Polymorphic Cache Stub**: Menangani sejumlah kecil variasi tipe konkret (2-4 target).
4. **Megamorphic Fallback**: Jika polymorphic stub jenuh, CLR kembali melakukan dynamic hash table lookup.

---

### 4. Why & What

| Dimensi | Pendekatan Naif / Tradisional | Pendekatan Enterprise Berkinerja Tinggi |
| :--- | :--- | :--- |
| **Pengelolaan Memory** | Bergantung penuh pada GC untuk seluruh lifecycle objek. Membiarkan objek-objek kecil jangka pendek mengotori Gen0. | Penggunaan Stack (`ref struct`, `Span<T>`), Object/Buffer Pooling (`ArrayPool<T>`), dan kontrol alignment field. |
| **Abstraksi Tipe** | Penggunaan `interface` dan `object` secara luas di hot-path tanpa memperhitungkan overhead virtual dispatch dan alokasi boxing. | Menggunakan Generics dengan *struct constraint*, *static abstract interfaces*, dan *inlining devirtualization*. |
| **Lifecycle Module** | Monolitik tunggal, seluruh DLL dimuat di runtime tanpa isolasi, mustahil meng-unload tanpa merestart proses OS. | Modul modular terisolasi via custom `AssemblyLoadContext` dengan kapabilitas hot-plugging dan dynamic unload. |
| **JIT Optimization** | Mengabaikan kompilasi runtime, tidak memanfaatkan statistik PGO. | Arsitektur disetel untuk kompatibilitas Tiered JIT & Dynamic PGO, meminimalkan call-site megamorphic. |

Mempelajari fondasi mendalam ini memastikan software engineer enterprise mampu mendiagnosis:
* GC Pauses (Stop-The-World) yang merusak ambang batas latency P99 service financial.
* Memory fragmentation pada Large Object Heap (LOH) akibat parsing array byte berukuran besar.
* Degradasi performa mikroskopik yang berakumulasi menjadi jutaan instruksi CPU yang terbuang di distributed compute nodes.

---

### 5. How (Workflow detail)

Berikut alur eksekusi internal dan integrasi manajemen memori modern di CLR:

```
[Incoming Payload (Network Socket / Stream)]
                     │
                     ▼
       [Rent Buffer from ArrayPool<byte>]  ◄── Zero Allocation
                     │
                     ▼
          [Span<byte> Slice Parsing]       ◄── No String Allocation
                     │
                     ▼
   [Unsafe / BinaryPrimitives Deserialization]
                     │
                     ▼
    [Invoke Pipeline: Monomorphic Inlining]
                     │
                     ▼
          [Return Buffer to Pool]
```

#### Alur Eksekusi:
1. **Buffer Acquisition**: Mencegah alokasi heap baru per-request dengan meminjam blok byte array dari `ArrayPool<byte>.Shared`.
2. **Slicing & Windowing**: Menggunakan `Span<byte>` atau `ReadOnlySpan<byte>` untuk memetakan segmen memori tanpa melakukan copy data fisik.
3. **Parsing In-Place**: Mengonversi nilai biner mentah langsung ke struct melalui `System.Buffers.Binary.BinaryPrimitives` atau mapping terstruktur.
4. **Processing**: Eksekusi logika bisnis memanfaatkan *struct generics* untuk memastikan JIT melakukan inlining secara penuh.
5. **Buffer Reclaim**: Mengembalikan buffer ke `ArrayPool<byte>` dalam blok `finally` guna mencegah memory leak di level buffer pool.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Memori Managed Heap vs Titipan Kargo Bandara
* **Reference Type (Heap Object)**: Bagaikan koper kargo bandara yang memiliki tag identitas resmi (SyncBlock & TypeHandle). Di mana pun koper Anda dipindahkan oleh petugas bandara (GC Compaction), Anda memegang nomor klaim bagasi (Pointer/Referensi). Setiap kali Anda ingin mengambil pakaian dari koper tersebut, Anda harus menunjukkan nomor klaim dan mencari lokasi rak koper saat ini (*Dereferencing overhead*).
* **Value Type (Struct)**: Bagaikan dompet saku Anda sendiri. Data (uang tunai, kartu) berada langsung di dalam saku baju (Stack). Anda langsung mengambil isinya tanpa perlu tagging kargo bandara, tanpa tracking dari petugas, dan jika baju Anda ganti pakaian (Stack Frame Pop), dompet tersebut otomatis berpindah bersama Anda tanpa overhead operasional bandara.

#### Diagram ASCII: Memory Layout & Pointer Resolution

```
      STACK FRAME (Method Scope)                  MANAGED HEAP (GC Domain)
 ┌───────────────────────────────────┐      ┌───────────────────────────────────┐
 │ Local Var: 'account' (Ref Pointer)│─────►│ Object Header (SyncBlock Index)   │ (Offset -8)
 ├───────────────────────────────────┤      ├───────────────────────────────────┤
 │ Local Var: 'balance' (Value Type) │      │ MethodTable Pointer (EEType*)     │ (Offset +0)
 │   - Raw Int64 Value: 10000000000  │      ├───────────────────────────────────┤
 └───────────────────────────────────┘      │ Field: _id (Int64)                │ (Offset +8)
                                            ├───────────────────────────────────┤
                                            │ Field: _tier (Byte)               │ (Offset +16)
                                            ├───────────────────────────────────┤
                                            │ Padding bytes (7 bytes alignment) │ (Offset +17)
                                            └───────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Diagnosa Struct Alignment & Explicit Memory Layout
Contoh ini menunjukkan bagaimana padding default compiler dapat membengkakkan konsumsi memori dan cara merekayasanya menggunakan `StructLayout`.

```csharp
using System;
using System.Runtime.InteropServices;

namespace Enterprise.Architecture.Foundations;

// Layout default: Kompiler akan memberikan padding otomatis
[StructLayout(LayoutKind.Sequential)]
public struct InefficientRecord
{
    public byte FlagA;   // 1 byte + 7 bytes padding
    public long Value;   // 8 bytes
    public byte FlagB;   // 1 byte + 7 bytes padding
} // Total: 24 bytes

// Layout yang dioptimasi secara manual
[StructLayout(LayoutKind.Sequential, Pack = 1)]
public struct PackedRecord
{
    public byte FlagA;   // 1 byte
    public byte FlagB;   // 1 byte
    public long Value;   // 8 bytes (tidak aligned pada kelipatan 8, waspada penalti arsitektur tertentu)
} // Total: 10 bytes

// Layout Eksplisit (Memory Union Style)
[StructLayout(LayoutKind.Explicit)]
public struct FastRegister
{
    [FieldOffset(0)] public ulong FullValue;
    [FieldOffset(0)] public uint LowerPart;
    [FieldOffset(4)] public uint UpperPart;
}

public static class LayoutDiagnostics
{
    public static void Run()
    {
        Console.WriteLine($"Size of InefficientRecord: {Marshal.SizeOf<InefficientRecord>()} bytes");
        Console.WriteLine($"Size of PackedRecord     : {Marshal.SizeOf<PackedRecord>()} bytes");
        Console.WriteLine($"Size of FastRegister     : {Marshal.SizeOf<FastRegister>()} bytes");
    }
}
```

#### 7.2 Practical Example: Zero-Allocation High-Throughput Binary Protocol Frame Parser
Implementasi parser protokol komunikasi finansial biner kustom menggunakan `ReadOnlySpan<T>`, meminimalisasi *heap allocation*, serta menghindari *virtual dispatch degradation*.

```csharp
using System;
using System.Buffers;
using System.Buffers.Binary;
using System.Runtime.CompilerServices;
using System.Text;

namespace Enterprise.Architecture.Protocols;

public enum MessageType : ushort
{
    Heartbeat = 0x01,
    LimitOrder = 0x02,
    ExecutionReport = 0x03
}

public readonly record struct TradeOrder(
    long OrderId,
    long AccountId,
    decimal Price,
    int Quantity,
    MessageType Type
);

public sealed class ZeroAllocBinaryParser
{
    private const byte MagicByte = 0xAF;
    private const int MinimumHeaderSize = 7; // Magic(1) + Length(4) + MsgType(2)

    [MethodImpl(MethodImplOptions.AggressiveOptimization)]
    public bool TryParseNextFrame(ref ReadOnlySpan<byte> buffer, out TradeOrder order)
    {
        order = default;

        if (buffer.Length < MinimumHeaderSize)
        {
            return false;
        }

        if (buffer[0] != MagicByte)
        {
            throw new InvalidOperationException("Corrupt frame: invalid magic byte sequence.");
        }

        int payloadLength = BinaryPrimitives.ReadInt32BigEndian(buffer.Slice(1, 4));
        int totalFrameLength = MinimumHeaderSize + payloadLength;

        if (buffer.Length < totalFrameLength)
        {
            // Frame parsial, menunggu sisa buffer masuk
            return false;
        }

        var messageType = (MessageType)BinaryPrimitives.ReadUInt16BigEndian(buffer.Slice(5, 2));
        var payload = buffer.Slice(MinimumHeaderSize, payloadLength);

        if (messageType == MessageType.LimitOrder)
        {
            order = ParseLimitOrderPayload(payload);
            buffer = buffer.Slice(totalFrameLength); // Majukan buffer pointer
            return true;
        }

        // Tipe frame lain dilewati (slice buffer maju)
        buffer = buffer.Slice(totalFrameLength);
        return false;
    }

    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    private static TradeOrder ParseLimitOrderPayload(ReadOnlySpan<byte> payload)
    {
        // Kontrak Payload: OrderId(8) + AccountId(8) + PriceScale(4) + PriceMantissa(8) + Qty(4) = 32 bytes
        if (payload.Length < 32)
        {
            throw new ArgumentException("Invalid LimitOrder payload length.");
        }

        long orderId = BinaryPrimitives.ReadInt64BigEndian(payload.Slice(0, 8));
        long accountId = BinaryPrimitives.ReadInt64BigEndian(payload.Slice(8, 8));
        
        int priceScale = BinaryPrimitives.ReadInt32BigEndian(payload.Slice(16, 4));
        long priceRaw = BinaryPrimitives.ReadInt64BigEndian(payload.Slice(20, 8));
        int quantity = BinaryPrimitives.ReadInt32BigEndian(payload.Slice(28, 4));

        decimal price = new decimal((int)(priceRaw & 0xFFFFFFFF), (int)(priceRaw >> 32), 0, false, (byte)priceScale);

        return new TradeOrder(orderId, accountId, price, quantity, MessageType.LimitOrder);
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Sistem *Core Financial Clearing House* memproses rata-rata 65.000 transaksi/detik pada jam sibuk bursa. Layanan backend mengalami lonjakan *latency latency spikes (P99)* hingga 4.5 detik setiap 45 detik sekali.

#### Root Cause Analysis (RCA) via SOS & Dotnet-Dump
Pemeriksaan dump file produksi menggunakan perintah `dotnet-dump` dan ekstensi SOS membongkar problem:
1. `!dumpheap -stat`: Ditemukan alokasi objek kelas `OrderContext` dan `byte[]` string buffer mencapai 14 Gigabytes di Gen 0/Gen 1.
2. `!gcwatch` dan `dotnet-trace`: Terjadi *Stop-The-World (STW) Garbage Collection* berulang pada Generation 2 akibat objek-objek sementara lolos (*promoted*) dari Gen 0 ke Gen 1 dan Gen 2 secara masif karena frekuensi alokasi yang sangat tinggi.
3. String parsing `Encoding.UTF8.GetString(...)` dilakukan berulang kali per payload masuk untuk membaca ID akun nasabah (16-character alphanumeric).

#### Solusi Arsitektural yang Diterapkan
1. **Penerapan System.IO.Pipelines & Memory Pooling**: Menghapus pembuatan `byte[]` per koneksi socket; beralih ke `PipeReader` yang mengonsumsi buffer internal berbasis chunk non-alokatif.
2. **Eliminasi String Parsing Menggunakan Utf8Parser**: Mengonversi byte array langsung menjadi UUID dan numerik menggunakan static class `System.Buffers.Text.Utf8Parser`.
3. **Refaktorisasi Kelas Model ke Readonly Structs**: Mentransformasikan data transfer internal menjadi *readonly record structs* yang di-pass dengan keyword `in` (Pass-by-reference-readonly) ke downstream engine, meniadakan alokasi heap untuk order parsing.

#### Hasil Optimasi
* Latensi P99 turun dari 4.500 ms menjadi **1.8 ms**.
* Alokasi memori GC berkurang sebesar **98.2%** (dari ~350 MB/detik menjadi ~6 MB/detik).
* STW GC Gen 2 turun drastis dari 80 kali per jam menjadi 0 kali selama jam perdagangan bursa.

---

### 9. Trade-offs

```
                       LATENCY CRITICAL
                             ▲
                             │        [Span<T> / ref struct]
                             │        - Zero Allocation
                             │        - High Complexity
                             │
       [Custom ALC Plugins]  │
       - Strong Isolation    │
       - Weak Dynamic Link   │
  ◄──────────────────────────┼──────────────────────────►
  FLEXIBILITY / ERGONOMICS   │              COST EFFICIENCY
                             │
                             │   [Class & Interfaces Naive]
                             │   - Simple Readability
                             │   - Heap Alloc & Virtual Calls
                             ▼
                      HIGH THROUGHPUT
```

1. **`struct` (Value Types) vs `class` (Reference Types)**
   * *Keuntungan Struct*: Meniadakan overhead GC, memori teralokasi inline/di stack, cache-locality tinggi.
   * *Trade-off / Kerugian*: Jika ukuran struct melebihi 16-24 bytes, biaya penyalinan (*defensive copy*) saat dipassing antar stack frame dapat melampaui biaya GC pointer dereferencing. Penanganan mutabilitas struct rentan memicu bug tersembunyi.
2. **`ref struct` (`Span<T>`) vs `Heap Buffer`**
   * *Keuntungan*: Eksekusi setara pointer C murni namun dengan runtime safety checking (bounds-checking).
   * *Trade-off / Kerugian*: Tidak dapat di-*box*, tidak dapat menjadi field dari class normal, tidak dapat disimpan di dalam context async/await methods (melewati `await` boundaries).
3. **Dynamic PGO (Profile-Guided Optimization) On vs Off**
   * *Keuntungan*: Performa puncak native code dapat meningkat 15% - 40% untuk dynamic dispatch code.
   * *Trade-off / Kerugian*: Konsumsi memori CLR meningkat saat startup karena perlunya menyimpan metrik runtime, dan waktu Tier 0 warmup membutuhkan throughput stabil sebelum optimasi Tier 1 matang.
4. **AssemblyLoadContext Isolation vs Uniform Assembly**
   * *Keuntungan*: Plugin dapat dimuat dan di-unload tanpa mematikan proses utama, isolasi dependency version mismatch (contoh: Plugin A butuh NewtonSoft v12, Plugin B butuh v13).
   * *Trade-off / Kerugian*: Biaya serialisasi data saat melempar objek melintasi boundary ALC; risiko *zombie references* yang menggagalkan mekanisme dynamic unloading.

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Anti-Pattern 1: Hidden Boxing melalui Interfaces pada Struct
Memanggil interface method secara langsung dari struct tanpa batasan generic akan memaksa CLR melakukan alokasi *boxing* ke heap.

```csharp
public interface IIdentifiable
{
    int GetId();
}

public struct MachineMetrics : IIdentifiable
{
    public int MachineId;
    public int GetId() => MachineId;
}

public class ExecutionPath
{
    // ANTI-PATTERN: Memicu alokasi boxing pada setiap pemanggilan
    public void ProcessBad(IIdentifiable identifiable)
    {
        Console.WriteLine(identifiable.GetId());
    }

    // BEST PRACTICE: Menggunakan Generics constraint murni
    // JIT akan mengompilasi spesialisasi native code khusus MachineMetrics tanpa alokasi heap
    public void ProcessOptimal<T>(T identifiable) where T : struct, IIdentifiable
    {
        Console.WriteLine(identifiable.GetId());
    }
}
```

#### 10.2 Anti-Pattern 2: Defensive Copying Akibat Modifikasi Mutasi Struct
Jika sebuah struct berukuran besar ditandai dengan modifier `in` (pass-by-reference), tetapi method di dalamnya bukan `readonly`, CLR JIT akan membuat *defensive copy* dari struct tersebut pada setiap invocation untuk menjamin imutabilitas.

```csharp
// ANTI-PATTERN
public struct SensorData
{
    public double Temp;
    public double Pressure;
    
    // Non-readonly method!
    public double CalculateMetric() => Temp * Pressure;
}

public class Consumer
{
    // Kompiler akan membuat clone/defensive copy 'data' sebelum memanggil CalculateMetric()!
    public double Evaluate(in SensorData data)
    {
        return data.CalculateMetric();
    }
}

// SOLUSI: Selalu gunakan 'readonly struct' jika dirancang untuk di-pass menggunakan 'in'
public readonly struct ReadonlySensorData
{
    public readonly double Temp;
    public readonly double Pressure;
    
    public double CalculateMetric() => Temp * Pressure;
}
```

#### 10.3 Troubleshooting Playbook: Menemukan Memory Leak pada AssemblyLoadContext
*Gejala*: Anda memanggil `alc.Unload()`, tetapi memori tidak kunjung turun meskipun GC telah dipaksa berjalan.

*Langkah Diagnosa Produksi*:
1. Buat core dump proses: `dotnet-dump collect -p <PID>`
2. Analisis file dump: `dotnet-dump analyze <dump_file>`
3. Jalankan SOS command:
   ```shell
   > dumpalc
   ```
   Cari ALC yang memiliki status `Unloading`.
4. Periksa referensi hidup yang menahan ALC tersebut:
   ```shell
   > gcroot <Address_Of_Collectible_AssemblyLoadContext>
   ```
5. *Penyebab Umum*: Event subscription statis di Host Process yang tidak di-unsubscribe oleh plugin, thread pool worker yang masih menjalankan thread dari assembly tersebut, atau instance Type/Reflection cache yang bocor ke static dictionary host.

---

### 11. Best Practices (Production Checklist)

#### Layout & Struct Performance
- [ ] Beri modifier `readonly struct` pada struct yang bersifat immutable untuk mencegah *defensive copies* saat passing via `in`.
- [ ] Urutkan field dari ukuran byte terbesar hingga terkecil (misal: `long` [8], `int` [4], `short` [2], `byte` [1]) jika menggunakan `LayoutKind.Sequential` default guna meminimalkan padding tersembunyi.
- [ ] Batasi ukuran struct maksimal 16-24 bytes kecuali jika hanya digunakan sebagai representasi pointer/interop layer atau selalu di-passing via `in` / `ref`.

#### Memory & Hot-Paths
- [ ] Jangan pernah menggunakan LINQ (`.Select()`, `.Where()`) di dalam path pemrosesan data bervolume tinggi (*hot path*). Gunakan perulangan berbasis indeks `for` tradisional atau `foreach` atas `Span<T>`.
- [ ] Manfaatkan `ArrayPool<T>.Shared` untuk buffer byte sementara yang berukuran > 1 KB, dan selalu kembalikan pada blok `finally`.
- [ ] Hindari konversi enum ke string (`enum.ToString()`) pada logging hot-path. Gunakan `nameof()` atau array mapping konstan.

#### Runtime & Tiered Compilation
- [ ] Pastikan runtime setting `<TieredPGO>true</TieredPGO>` aktif di file `.csproj` (default pada .NET 8+).
- [ ] Pastikan tidak ada call site polymorphic megamorphic pada hot-loop interface dispatch. Gunakan type pattern checking untuk mengisolasi path concrete class yang paling sering muncul (*monomorphic devirtualization trick*).

---

### 12. Hands-on Practice

Simpan seluruh file praktik berikut dalam path repositori: `hands-on/m02/`

#### Struktur Proyek
```
hands-on/m02/
├── CoreInternalsBenchmark/
│   ├── CoreInternalsBenchmark.csproj
│   └── Benchmarks.cs
└── Program.cs
```

#### Langkah 1: Inisialisasi Proyek Benchmark
Buka terminal dan jalankan:
```shell
mkdir -p hands-on/m02
cd hands-on/m02
dotnet new console -n CoreInternalsBenchmark -o .
dotnet add package BenchmarkDotNet
```

#### Langkah 2: Buat Implementasi Kode Pembuktian
Modifikasi file `hands-on/m02/Benchmarks.cs`:

```csharp
using System;
using System.Buffers.Binary;
using System.IO;
using BenchmarkDotNet.Attributes;
using BenchmarkDotNet.Configs;
using BenchmarkDotNet.Running;

namespace CoreInternalsBenchmark;

public interface ICalculator
{
    long Compute(int a, int b);
}

public struct FastCalculator : ICalculator
{
    public long Compute(int a, int b) => (long)a * b;
}

[MemoryDiagnoser]
[DisassemblyDiagnoser(printSource: true, maxDepth: 2)]
public class InternalsBenchmark
{
    private FastCalculator _calc;
    private ICalculator _calcInterface;
    private byte[] _rawBuffer = null!;

    [GlobalSetup]
    public void Setup()
    {
        _calc = new FastCalculator();
        _calcInterface = _calc; // Boxed reference jika disimpan ke interface variable

        _rawBuffer = new byte[16];
        BinaryPrimitives.WriteInt64BigEndian(_rawBuffer.AsSpan(0, 8), 4294967296L);
        BinaryPrimitives.WriteInt64BigEndian(_rawBuffer.AsSpan(8, 8), 8589934592L);
    }

    [Benchmark(Baseline = true)]
    public long DirectStructInvocation()
    {
        return _calc.Compute(2500, 4000);
    }

    [Benchmark]
    public long InterfaceVirtualInvocation()
    {
        // Menyebabkan callvirt dan overhead interface dispatch table
        return _calcInterface.Compute(2500, 4000);
    }

    [Benchmark]
    public long GenericConstrainedInvocation()
    {
        return InvokeViaGeneric(_calc, 2500, 4000);
    }

    [Benchmark]
    public long MemoryAllocStreamReader()
    {
        // Mensimulasikan pembacaan payload secara naif menggunakan MemoryStream
        using var stream = new MemoryStream(_rawBuffer);
        using var reader = new BinaryReader(stream);
        long v1 = BinaryPrimitives.ReadInt64BigEndian(reader.ReadBytes(8));
        long v2 = BinaryPrimitives.ReadInt64BigEndian(reader.ReadBytes(8));
        return v1 + v2;
    }

    [Benchmark]
    public long MemorySpanZeroAllocReader()
    {
        // Membaca payload secara efisien via Span murni
        ReadOnlySpan<byte> span = _rawBuffer;
        long v1 = BinaryPrimitives.ReadInt64BigEndian(span.Slice(0, 8));
        long v2 = BinaryPrimitives.ReadInt64BigEndian(span.Slice(8, 8));
        return v1 + v2;
    }

    private static long InvokeViaGeneric<T>(T calculator, int a, int b) where T : struct, ICalculator
    {
        return calculator.Compute(a, b);
    }
}
```

Modifikasi `hands-on/m02/Program.cs`:
```csharp
using BenchmarkDotNet.Running;

namespace CoreInternalsBenchmark;

public class Program
{
    public static void Main(string[] args)
    {
        BenchmarkRunner.Run<InternalsBenchmark>();
    }
}
```

#### Langkah 3: Eksekusi dan Amati Hasil Benchmark
Jalankan benchmark dalam mode **Release**:
```shell
dotnet run -c Release
```

*Perhatikan Output*:
* Bandingkan kolom `Allocated`: `MemorySpanZeroAllocReader` menghasilkan **0 B**, sedangkan `MemoryAllocStreamReader` menghasilkan alokasi memori puluhan hingga ratusan byte per iterasi.
* Bandingkan `InterfaceVirtualInvocation` vs `GenericConstrainedInvocation`: Perhatikan bahwa generic constraint menghasilkan eksekusi yang setara dengan direct struct call karena inlining JIT.

---

### 13. Exercise

#### Level Easy
**Tugas**: Diberikan sebuah struct representasi koordinat geografis yang tidak efisien dalam pemakaian memori:
```csharp
public struct GeoLocation
{
    public byte StatusFlag;
    public double Latitude;
    public short RegionCode;
    public double Longitude;
}
```
Ubah urutan field struct di atas agar ukuran totalnya mengecil seminimal mungkin tanpa menggunakan `Pack = 1`. Buktikan penurunan ukuran byte-nya menggunakan `Marshal.SizeOf<GeoLocation>()` atau `Unsafe.SizeOf<GeoLocation>()`.

#### Level Medium
**Tugas**: Buat parser *in-place* berbasis `ReadOnlySpan<char>` yang membaca format delimited string log berikut:
`"2023-10-27|WARN|ServiceBus|Queue threshold exceeded"`
Ekstraksi nilai `Timestamp` (DateTime), `LogLevel` (Enum), `SourceName` (`ReadOnlySpan<char>`), dan `Message` (`ReadOnlySpan<char>`) **tanpa alokasi `string.Split()` ataupun string allocations baru** pada heap sama sekali.

#### Level Hard
**Tugas**: Buat sistem plugin dinamis berbasis `AssemblyLoadContext` yang:
1. Menentukan `PluginLoadContext` yang ditandai dengan `isCollectible: true`.
2. Memuat assembly DLL eksternal dari direktori lokal.
3. Mengeksekusi entry point interface plugin tersebut.
4. Melakukan *unload* ALC dan memicu `GC.Collect()` serta `GC.WaitForPendingFinalizers()`.
5. Memverifikasi melalui `WeakReference` bahwa assembly dan context tersebut benar-benar telah terhapus dari memori secara permanen.

---

### 14. Challenge

**Skenario Sistem Telemetri Ultra-Low Latency (Kernel-level Stream Demux)**

Anda diminta merancang subsistem ingestion jaringan IoT yang menerima paket data mentah binary bervolume ekstrem (100.000 events/detik) dengan batasan performa berikut:
1. **Zero Garbage Collection Allocation**: Dilarang terjadi alokasi memori heap baru selama fase ingestion berlangsung (0 B allocation per frame).
2. **Dynamic Schema Dispatch**: Paket biner dapat berupa salah satu dari 3 tipe payload (Sensor, GPS, Battery). Desain alur pengolahan data menggunakan generics dan polymorphic parsing tanpa memicu alokasi *boxing* dan tanpa penalti *megamorphic dynamic dispatch*.
3. **Data Integrity & Concurrency**: Buffer yang dipinjam dari unmanaged memory atau `ArrayPool` harus di-slice dan didistribusikan ke 4 background worker threads melalui thread-safe lock-free channel (misal: `System.Threading.Channels.Channel<T>`).

**Tantangan**: Tuliskan arsitektur parser dan pipeline ringkas lengkap yang mendemonstrasikan bagaimana Anda memetakan segmen memori unmanaged ke `ref struct`, memvalidasi frame boundaries, dan memproses komputasi data tanpa satu pun GC Pause di Gen 0. Buktikan tidak adanya alokasi heap dengan unit test beranotasi `GC.GetAllocatedBytesForCurrentThread()`.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Berapa ukuran overhead bawaan (header) untuk setiap objek Reference Type pada runtime .NET 64-bit sebelum field data dihitung?**
   * A. 8 bytes
   * B. 12 bytes
   * C. 16 bytes
   * D. 24 bytes
2. **Kompiler Roslyn mengompilasi kode sumber C# menjadi apa?**
   * A. Native Machine Code x86/x64
   * B. Common Intermediate Language (CIL) dan Metadata
   * C. Bytecode JVM
   * D. Assembly C++
3. **Mengapa `Span<T>` didefinisikan sebagai `ref struct`?**
   * A. Agar dapat disimpan ke dalam generic List
   * B. Agar runtime dapat menjamin ia hanya berada di Stack dan tidak pernah lolos ke Managed Heap
   * C. Untuk mengaktifkan dukungan pemanggilan async/await
   * D. Agar dapat dikirim antar boundary proses OS
4. **Apa fungsi utama dari SyncBlock Index pada Object Header?**
   * A. Menyimpan alamat VTable interface
   * B. Menghitung jumlah referensi objek (Reference Counting)
   * C. Digunakan oleh primitif sinkronisasi lock runtime dan caching hash code
   * D. Menentukan generasi GC (Gen 0, 1, atau 2)
5. **Kapan Tiered Compilation di CLR mempromosikan metode dari Tier 0 ke Tier 1?**
   * A. Segera setelah aplikasi pertama kali dinyalakan
   * B. Ketika metode tersebut tidak pernah dipanggil selama 1 jam
   * C. Ketika invocation counter metode tersebut melampaui batas ambang frekuensi pemanggilan runtime
   * D. Hanya jika developer menambahkan atribut `[MethodImpl(MethodImplOptions.AggressiveInlining)]`

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Perhatikan kode berikut: `IComparable val = 42;`. Fenomena internal apa yang terjadi di CLR?**
   * A. Devirtualization langsung
   * B. Boxing: integer 42 dialokasikan sebagai objek baru di Managed Heap
   * C. Stack promotion
   * D. Dynamic PGO inlining
7. **Bagaimana Dynamic PGO membantu optimasi interface method dispatch pada .NET 8+?**
   * A. Mengubah interface menjadi abstract class secara otomatis
   * B. Merekam tipe target konkret yang paling sering muncul, lalu melakukan speculative inlining
   * C. Menghapus VTable dari memori metadata
   * D. Memaksa seluruh method interface berjalan di Tier 0
8. **Mengapa struct besar yang di-pass dengan keyword `in` wajib dideklarasikan sebagai `readonly struct` untuk performa maksimal?**
   * A. Agar tidak dapat diwariskan oleh struct lain
   * B. Mencegah kompiler membuat defensive copy lokal sebelum memanggil method/properti pada struct tersebut
   * C. Memastikan struct disimpan di Large Object Heap (LOH)
   * D. Menghindari pembacaan thread yang tidak sinkron
9. **Manakah dari tipe berikut yang TIDAK BISA menjadi tipe parameter generic pada `Span<T>`?**
   * A. `int`
   * B. `byte`
   * C. Sebuah tipe `ref struct` lain
   * D. Sebuah tipe `readonly struct`
10. **Apa yang menyebabkan sebuah collectible `AssemblyLoadContext` gagal di-unload dari memori setelah `.Unload()` dipanggil?**
    * A. GC berjalan terlalu sering
    * B. Masih ada referensi hidup dari luar ALC yang menunjuk ke objek atau tipe data yang didefinisikan di dalam ALC tersebut
    * C. Assembly tersebut tidak dikompilasi menggunakan Dynamic PGO
    * D. Assembly memiliki file `.pdb` yang terkunci di disk

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario 1**: Sebuah microservice pemrosesan transaksi mencatat konsumsi memori yang terus meningkat drastis hingga OutOfMemoryException (OOM). Analisis profiler menunjukkan bahwa ada jutaan array byte berukuran 90.000 bytes yang menumpuk. Mengapa GC tidak mampu membersihkan memori ini secara efisien?
    * A. Array tersebut masuk ke Small Object Heap (SOH) dan terjebak di Gen 0
    * B. Objek berukuran > 85.000 bytes dialokasikan ke Large Object Heap (LOH), di mana GC tidak melakukan pemadatan (*compaction*) secara default, menyebabkan fragmentasi memori hebat
    * C. Objek tersebut terkunci oleh Virtual Stub Dispatch
    * D. Roslyn compiler gagal mengompilasi array byte ke CIL
12. **Skenario 2**: Anda mengganti seluruh class DTO internal menjadi struct berukuran 128 bytes untuk menghindari GC allocation. Namun, setelah di-benchmark, throughput sistem justru anjlok 30%. Apa penyebab utama degradasi performa ini?
    * A. Memory alignment tidak valid
    * B. Biaya penyalinan memori fisik (*memory copying*) struct 128 bytes pada setiap argument passing antar method jauh lebih mahal daripada menyalin referensi pointer 8 bytes
    * C. Struct 128 bytes otomatis dialokasikan di Large Object Heap
    * D. CLR mematikan Tiered Compilation untuk struct besar
13. **Skenario 3**: Sebuah distributed engine mengeksekusi plugin pihak ketiga via `AssemblyLoadContext`. Setelah melakukan pembaruan plugin 50 kali dalam 24 jam tanpa merestart server, memori sistem habis. Langkah diagnosa SOS manakah yang paling tepat untuk mengidentifikasi penyebab penahanan assembly tersebut?
    * A. Jalankan `!dumpheap -stat` lalu cari string terpanjang
    * B. Jalankan `!eeheap -gc` lalu restart proses
    * C. Jalankan `!dumpalc` untuk menemukan ALC yang berstatus unloading, lalu telusuri dependensinya dengan `!gcroot` pada instans ALC terkait
    * D. Jalankan `!threads` untuk memeriksa thread deadlock

---

### Kunci Jawaban & Evaluasi Pemahaman

#### Bagian 1: Basic
1. **C** — 16 bytes (8 bytes Object Header/SyncBlock Index + 8 bytes MethodTable Pointer pada arsitektur 64-bit).
2. **B** — Common Intermediate Language (CIL) dan Metadata tabel tipe data format ECMA-335.
3. **B** — Aturan CLR memastikan `ref struct` hanya berada di Stack Frame untuk mencegah pointer tracking yang tidak valid pada GC heap.
4. **C** — Sinkronisasi locking primitif (`Monitor`), hash code caching, dan interop tracking.
5. **C** — Tiered compilation memonitor call counter; ketika frekuensi invocation melampaui batas tertentu, metode diantrekan ke Tier 1 compilation.

#### Bagian 2: Intermediate
6. **B** — Value type primitif 42 dibungkus (*boxed*) ke dalam managed object baru di Heap agar dapat memenuhi kontrak reference tipe `IComparable`.
7. **B** — Dynamic PGO mengamati tipe riil di runtime dan melakukan devirtualization spekulatif, mengubah indirect virtual jump menjadi conditional direct branch yang dapat di-inline.
8. **B** — Kompiler harus menjamin keamanan modifikasi. Jika struct tidak ditandai `readonly`, setiap panggilan fungsi internal pada struct berparameter `in` akan memicu *defensive copy* lokal.
9. **C** — Aturan CLR melarang sebuah `ref struct` menjadi type argument untuk generic class/struct, sehingga `Span<Span<T>>` tidak valid.
10. **B** — Dynamic assembly unloading berbasis GC tracing; jika ada satu referensi aktif (misal delegate event listener) dari luar context yang tertinggal, seluruh ALC tertahan di memori.

#### Bagian 3: Skenario Kasus Produksi
11. **B** — Batas LOH adalah 85.000 bytes. Alokasi sementara >85 KB masuk ke LOH yang jarang dibersihkan (hanya saat Gen 2 collection) dan tidak dipadatkan (*non-compacting by default*), menyebabkan *memory fragmentation*.
12. **B** — Struct disalin berdasarkan nilai (*pass-by-value*). Struct 128 bytes membutuhkan instruksi copy CPU yang masif per call-site jika tidak di-pass menggunakan `in` atau `ref`.
13. **C** — `!dumpalc` menampilkan status lifecycle ALC, dan `!gcroot` menelusuri rantai referensi yang menahan ALC agar tidak terkoleksi oleh GC.

---

### 16. Summary

1. **CLR Runtime Engine** beroperasi secara dinamis menggunakan arsitektur hybrid kompilasi berjenjang (**Tiered Compilation & Dynamic PGO**), menyeimbangkan waktu boot cepat dengan performa puncak native machine code.
2. **Reference Type Layout** di heap selalu membawa overhead tetap 16 bytes pada x64 (SyncBlock Index + MethodTable Pointer) ditambah data padding alignment 8 bytes, sedangkan **Value Type** merepresentasikan layout memori mentah yang ideal untuk *data-locality*.
3. **Memory Slicing Modern (`Span<T>`, `ReadOnlySpan<T>`)** memberikan performa native pointer manipulation dengan keamanan memory bounds checking tanpa alokasi garbage collection.
4. **Interface Dispatch Overhead** pada hot paths dapat dieliminasi secara total menggunakan teknik **Generics Struct Constraints**, membuka jalan bagi JIT untuk melakukan agresif inlining dan devirtualization.
5. **AssemblyLoadContext** menyediakan batas isolasi modularitas runtime enterprise, namun membutuhkan pengelolaan dependensi referensi yang ketat agar tidak menimbulkan *unloading leaks*.