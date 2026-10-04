# Bab 04 Module 01: Manajemen Memori, GC & High-Performance C#

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** Back-End & Systems Programming Track
* **Kategori:** 02-Programming-Languages
* **Topik Utama:** C# High-Performance Memory Architecture
* **Kode Modul:** CS-ADV-04-01
* **Tingkat Kompleksitas:** Advanced / Lanjutan
* **Prasyarat Pengetahuan:**
  * Pemahaman mendalam tentang OOP dan Type System C# (Class, Struct, Interface).
  * Pengalaman dasar menggunakan asynchronous programming (`async`/`await`, `Task`).
  * Pemahaman dasar tentang struktur data (Array, Linked List, Buffer).
* **Target Runtime:** .NET 8.0 LTS / .NET 9.0
* **Estimasi Waktu Penyelesaian:** 120 – 180 menit

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis** siklus hidup objek pada Managed Heap dan Stack secara presisi, termasuk peran generasi GC (Gen 0, Gen 1, Gen 2, LOH, POH).
2. **Mendeteksi dan Memitigasi** alokasi memori tersembunyi (*hidden allocations*) seperti boxing/unboxing, closure capture, dan delegasi runtime.
3. **Mengimplementasikan** pola arsitektur *Zero-Allocation* menggunakan `Span<T>`, `ReadOnlySpan<T>`, `Memory<T>`, `ref struct`, dan `ArrayPool<T>`.
4. **Mengevaluasi** dampak GC latency dan *Stop-The-World* pauses pada aplikasi throughput tinggi melalui metrik runtime formal.
5. **Menerapkan** standardisasi pelepasan resource tak terkelola (*unmanaged resources*) dengan implementasi pola `IDisposable` dan `IAsyncDisposable` yang deterministik dan aman.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam ekosistem .NET, Common Language Runtime (CLR) memberikan abstraksi manajemen memori otomatis melalui Garbage Collector (GC). Abstraksi ini sering kali memicu ilusi bahwa memori adalah sumber daya "gratis" dan "tanpa biaya komputasi". 

**Mental Model Kritis:**
* **Memori Bukan Sekadar Ruang, Memori Adalah Waktu CPU:** Setiap alokasi di Managed Heap pada akhirnya harus ditelusuri, dipindahkan (compacted), atau dibersihkan oleh Garbage Collector. Biaya alokasi bukan hanya instruksi `newobj`, melainkan siklus CPU di masa depan saat GC menghentikan eksekusi thread aplikasi (*Stop-The-World Phase*) untuk membersihkan objek tersebut.
* **Stack vs Heap:**
  * **Stack:** Bersifat linear, LIFO (*Last In, First Out*), dialokasikan seketika melalui pergeseran pointer register CPU (`RSP`), dan otomatis dibersihkan saat frame fungsi berakhir tanpa overhead GC.
  * **Heap:** Bersifat dinamis, fragmentatif, membutuhkan pencarian blok kosong, sinkronisasi antar-thread, dan pelacakan dependensi objek.
* **High-Performance Mindset:** *"The fastest allocation is the one that never happened."* Insinyur perangkat lunak sistem berkinerja tinggi tidak fokus pada cara membersihkan memori dengan cepat, melainkan merancang algoritma dan struktur data yang menghindari alokasi heap sejak awal.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Struktur Managed Heap & Pemisahan Generasi

```
+=============================================================================+
|                               MANAGED HEAP                                  |
+=============================================================================+
| [ SOH: Small Object Heap (< 85,000 bytes) ]                                 |
|                                                                             |
|  +------------------+    +------------------+    +-----------------------+  |
|  |   Generation 0   | -> |   Generation 1   | -> |     Generation 2      |  |
|  | (Short-lived,    |    |  (Buffer/Triage, |    |   (Long-lived, Static |  |
|  |  Ephemeral Seg)  |    |  Ephemeral Seg)  |    |    Domain/Singletons) |  |
|  +------------------+    +------------------+    +-----------------------+  |
|          |                        |                          |              |
|          +--- GC Collection ----->+---- GC Collection ------>+              |
+-----------------------------------------------------------------------------+
| [ LOH: Large Object Heap (>= 85,000 bytes) ]                                |
|  - Alokasi objek array/string besar.                                        |
|  - Default: Tidak di-compact secara otomatis (menyebabkan fragmentasi).     |
+-----------------------------------------------------------------------------+
| [ POH: Pinned Object Heap (.NET 5+) ]                                       |
|  - Objek yang di-pin secara eksplisit (misal: GC.AllocateArray(pinned: true))|
|  - Mencegah fragmentasi pada SOH dan LOH akibat pinning pointer native.     |
+=============================================================================+
```

### 2. Layout Memori Internal Sebuah Objek C# pada Heap (64-bit Architecture)

```
Byte Offset:
 0                   8                  16                                  N
+-------------------+-------------------+-----------------------------------+
| Object Header     | MethodTable PTR   | Instance Fields Data              |
| (SyncBlock Index, | (Type Descriptor, | (Primitive types, References to   |
|  Lock state, Hash)|  Interface maps)  |  other objects, Padding bytes)    |
+-------------------+-------------------+-----------------------------------+
|<--- 8 Bytes ----->|<--- 8 Bytes ----->|<--- Variabel (min 8 byte padded)->|
```

### 3. Arsitektur Komparasi Akses Data: Stack vs Span<T> vs Heap Array

```
STACK MEMORY                             MANAGED HEAP
+-------------------------+             +-------------------------------+
| Frame: ProcessData()    |             | byte[] Array (Object on Heap) |
|                         |             |                               |
| [byte[] ref] -----------+------------>| [Header][MethodTable][Length] |
|                         |             | [0][1][2][3][4][5][6][7]...   |
|                         |             +-------------------------------+
|                         |                             ^
| [Span<byte>]            |                             |
|  - ref byte _pointer ---+-----------------------------+ (Points directly)
|  - int _length = 4      |
+-------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Fase Eksekusi Garbage Collector
Garbage Collector .NET beroperasi menggunakan algoritma *Generational Mark-Sweep-Compact*:
* **Fase Mark (Penandaan):** GC mengidentifikasi semua *GC Roots* (variabel lokal pada stack, thread register, handle static, dan handle interop CPU). GC menelusuri graf objek secara rekursif dan menandai bit penanda (*mark bit*) di dalam tabel alokasi internal untuk setiap objek yang masih terjangkau (*reachable*).
* **Fase Plan (Perencanaan):** Menghitung efisiensi pemadatan. Jika pemadatan (*compaction*) dinilai terlalu mahal, GC dapat memilih untuk beralih ke mode sweep murni.
* **Fase Sweep (Penyisiran):** Menelusuri memori yang tidak ditandai sebagai *reachable*, mengklaim kembali memori tersebut, dan mencatat blok kosong ke dalam *free list*.
* **Fase Compact (Pemadatan):** Memindahkan objek yang masih hidup ke alamat memori yang bersebelahan untuk menghilangkan fragmentasi. Semua referensi pointer yang mengarah ke objek yang dipindahkan diperbarui ke alamat baru. Tahap ini membutuhkan penundaan eksekusi thread (*Stop-The-World*).

### 2. Segmentasi Heap: SOH, LOH, dan POH
* **SOH (Small Object Heap):** Menampung objek dengan ukuran $< 85.000$ byte. Menggunakan mekanisme generational (Gen 0 $\rightarrow$ Gen 1 $\rightarrow$ Gen 2).
* **LOH (Large Object Heap):** Menampung objek $\ge 85.000$ byte (dan array bertipe `double` tertentu di 32-bit). Objek di LOH langsung dialokasikan di Generasi 2. Secara default, LOH tidak dipadatkan (*non-compacting*) saat sweep untuk menghemat waktu CPU, sehingga sangat rentan terhadap fragmentasi memori (*out of memory fragmentation*).
* **POH (Pinned Object Heap):** Diperkenalkan pada .NET 5. Menampung objek yang dijamin tidak akan dipindahkan oleh GC. Ini mencegah pinning objek pada SOH yang biasanya menciptakan zona penghalang (*islands*) yang menghentikan proses pemadatan memori.

### 3. Varian GC: Workstation vs Server GC
* **Workstation GC:** Dioptimalkan untuk responsivitas aplikasi desktop/UI dan latensi rendah. Menggunakan alokasi thread tunggal untuk GC dan meminimalkan durasi pemblokiran UI.
* **Server GC:** Dioptimalkan untuk *throughput* tinggi dan skalabilitas aplikasi multi-threaded (misal: ASP.NET Core). Managed Heap dibagi menjadi beberapa heap independen sesuai jumlah logical core CPU. Setiap core memiliki dedicated thread GC yang berjalan dengan prioritas tertinggi.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. The Low-Allocation Primitives: `Span<T>` and `ReadOnlySpan<T>`
`Span<T>` adalah representasi tipe terpadu (*unified representation*) dari area memori yang berdekatan dan aman secara tipe (*type-safe*). Didefinisikan secara internal sebagai:

```csharp
public readonly ref struct Span<T>
{
    internal readonly ref T _pointer;
    private readonly int _length;
}
```

Karena merupakan `ref struct`:
* `Span<T>` hanya dapat hidup di Stack CPU.
* Tidak dapat menjadi field dari kelas heap normal.
* Tidak dapat di-box menjadi `object` atau interface.
* Tidak dapat digunakan dalam method asynchronous (`async`/`await`) melintasi *await boundary*, karena state machine async mendongkrak konteks eksekusi ke heap.
* Memberikan akses langsung ke Managed Array, Native Memory (malloc), atau Stack Memory (`stackalloc`) tanpa copy operasi dan tanpa biaya GC.

### 2. `Memory<T>` and `ReadOnlyMemory<T>`
Sebagai pelengkap `Span<T>`, `Memory<T>` adalah tipe yang kompatibel dengan heap (bukan `ref struct`). Tipe ini bertindak sebagai jendela slice memori yang aman disimpan di kelas, struct standar, dan dapat melewati batas metode `async`/`await`. Ketika data riil ingin diproses atau dibaca dengan performa tinggi, panggil metode `.Span` dari instans `Memory<T>`.

### 3. Array Pooling Architecture (`ArrayPool<T>`)
Mengalokasikan array baru secara berulang di server throughput tinggi akan membebani GC secara drastis. `ArrayPool<T>` menerapkan pola *Object Pool Pattern* untuk array buffer. Buffer disewa (*rent*), digunakan, dan kemudian dikembalikan (*return*).

```
[Consumer Application]
       |
       | 1. Rent(minSize: 4096)
       v
+-------------------------------+
| ArrayPool<byte>.Shared        |
| - Buckets: 16, 32, 64 ... 4MB |
+-------------------------------+
       |
       | 2. Provides buffer (e.g. byte[4096])
       v
[Memory Processing] (Execution without allocations)
       |
       | 3. Return(buffer, clearArray: false)
       v
+-------------------------------+
| Ready for next consumer       |
+-------------------------------+
```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah perbandingan implementasi pemrosesan string format *Key-Value* (misal: parser log `"ID=849302;Status=Active;Metric=98.6"`).
* **Pendekatan Naif:** Menggunakan `string.Split()` dan `Substring()` (Menghasilkan banyak alokasi di Gen 0).
* **Pendekatan High-Performance:** Menggunakan `ReadOnlySpan<char>` (Nol alokasi memori heap).

```csharp
using System;
using System.Globalization;

namespace HighPerformance.Memory
{
    public sealed class LogDataParser
    {
        // -------------------------------------------------------------
        // PENDEKATAN NAIF: Banyak alokasi sementara di Heap
        // -------------------------------------------------------------
        public static (long Id, string Status, double Metric) ParseNaive(string rawLog)
        {
            // ALOKASI 1: Array hasil string.Split
            string[] segments = rawLog.Split(';'); 
            
            long id = 0;
            string status = string.Empty;
            double metric = 0.0;

            foreach (var segment in segments)
            {
                // ALOKASI 2: Array hasil string.Split pada key-value
                string[] kv = segment.Split('='); 
                string key = kv[0];
                string val = kv[1]; // ALOKASI 3: Alokasi Substring baru

                if (key == "ID")
                    id = long.Parse(val);
                else if (key == "Status")
                    status = val;
                else if (key == "Metric")
                    metric = double.Parse(val, CultureInfo.InvariantCulture);
            }

            return (id, status, metric);
        }

        // -------------------------------------------------------------
        // PENDEKATAN ZERO-ALLOCATION: Menggunakan ReadOnlySpan<char>
        // -------------------------------------------------------------
        public static (long Id, ReadOnlyMemory<char> Status, double Metric) ParseOptimized(ReadOnlyMemory<char> rawLog)
        {
            ReadOnlySpan<char> span = rawLog.Span;
            long id = 0;
            ReadOnlyMemory<char> status = default;
            double metric = 0.0;

            int position = 0;
            while (position < span.Length)
            {
                // Cari pemisah ';' tanpa alokasi array
                int nextDelimiter = span.Slice(position).IndexOf(';');
                ReadOnlySpan<char> segment;

                if (nextDelimiter == -1)
                {
                    segment = span.Slice(position);
                    position = span.Length; // Selesai
                }
                else
                {
                    segment = span.Slice(position, nextDelimiter);
                    position += nextDelimiter + 1;
                }

                // Parse Key=Value
                int equalIndex = segment.IndexOf('=');
                if (equalIndex == -1) continue;

                ReadOnlySpan<char> key = segment.Slice(0, equalIndex);
                ReadOnlySpan<char> val = segment.Slice(equalIndex + 1);

                if (key.SequenceEqual("ID"))
                {
                    id = long.Parse(val);
                }
                else if (key.SequenceEqual("Status"))
                {
                    // Menghitung offset relatif untuk membuat ReadOnlyMemory tanpa alokasi baru
                    int valOffset = (rawLog.Length - span.Length) + (position - (segment.Length - equalIndex));
                    // Alternatif aman berbasis pointer offset relative:
                    int rawOffset = (int)System.Runtime.CompilerServices.Unsafe.ByteOffset(
                        ref System.Runtime.InteropServices.MemoryMarshal.GetReference(rawLog.Span),
                        ref System.Runtime.InteropServices.MemoryMarshal.GetReference(val)
                    ) / sizeof(char);

                    status = rawLog.Slice(rawOffset, val.Length);
                }
                else if (key.SequenceEqual("Metric"))
                {
                    metric = double.Parse(val, CultureInfo.InvariantCulture);
                }
            }

            return (id, status, metric);
        }
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Tinjauan detail baris kunci implementasi `ParseOptimized`:

1. `public static (long Id, ReadOnlyMemory<char> Status, double Metric) ParseOptimized(ReadOnlyMemory<char> rawLog)`
   * Parameter menggunakan `ReadOnlyMemory<char>` alih-alih `string`. Ini fleksibel karena dapat menerima string, slice string, atau array char tanpa dependensi GC lanjutan. Return type `Status` berupa `ReadOnlyMemory<char>` menjamin representasi teks tidak di-alokasikan ulang sebagai string baru di heap.
2. `ReadOnlySpan<char> span = rawLog.Span;`
   * Mengambil struct `ReadOnlySpan<char>` dari `Memory<T>`. Operasi ini instan, hanya mengekstrak referensi pointer dan panjang data ke dalam stack CPU.
3. `int nextDelimiter = span.Slice(position).IndexOf(';');`
   * Method `.Slice()` tidak menyalin array/string. Slice hanya menghitung aritmatika pointer: `new_pointer = pointer + position` dan `new_length = length - position`. `IndexOf` berjalan menggunakan instruksi vectorized CPU (SIMD) secara implisit.
4. `ReadOnlySpan<char> key = segment.Slice(0, equalIndex);`
   * Memotong segment menjadi key secara deterministik di stack. Alokasi heap = 0 byte.
5. `if (key.SequenceEqual("ID"))`
   * `SequenceEqual` membandingkan konten karakter demi karakter secara langsung melalui perbandingan pointer SIMD, menghindari konversi `Span` kembali menjadi `string` (yang akan merusak paradigma low-allocation).
6. `id = long.Parse(val);`
   * Pada .NET Core 2.1 ke atas, metode `long.Parse()` dan `double.Parse()` memiliki overload yang menerima `ReadOnlySpan<char>`. Karakter langsung diuraikan dari stack buffer tanpa overhead konversi teks sementara.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks Kasus
**Domain:** Financial High-Frequency Telemetry & FIX Engine Gateway.  
**Masalah:** Sistem ingestion data gateway memproses $200.000$ pesan per detik. Setiap pesan serial JSON/FIX dialokasikan sebagai `byte[]` terpisah saat dibaca dari Socket, kemudian dikonversi menjadi `string`, dan di-*deserialize*.

**Gejala di Lingkungan Production:**
* Terjadi latency spikes periodik: Latensi rata-rata P99 melompat dari 3ms ke 450ms setiap 12 detik.
* Metrik `System.Runtime -> % Time in GC` mencapai 28%.
* SOH Gen 0 collections mencapai 15.000 events/menit. Fragmentasi memori menyebabkan promosi prematur ke Gen 2 dan memicu *Full GC Stop-The-World* yang memblokir transaksi order finansial, menyebabkan denda kegagalan eksekusi order (SLA Breach).

**Akar Masalah:**
1. Alokasi array sementara (`new byte[bufferSize]`) pada setiap iterasi socket connection loop.
2. Penggunaan `System.Text.Encoding.UTF8.GetString(bytes)` yang mengalokasikan jutaan string ephemeral per detik.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Solusi arsitektur: Membangun *High-Throughput Streaming Socket Buffer* menggunakan `ArrayPool<byte>`, membaca data berbasis `Span<byte>`, dan parsing langsung via `Utf8Parser`.

```csharp
using System;
using System.Buffers;
using System.Buffers.Text;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace HighPerformance.ProductionEngine
{
    public readonly record struct TradeExecutionMessage(long OrderId, decimal ExecutionPrice, int Quantity);

    public sealed class FastMessageProcessor : IAsyncDisposable
    {
        private readonly Stream _networkStream;
        private readonly ArrayPool<byte> _pool;
        private byte[]? _leasedBuffer;
        private const int MaxMessageSize = 4096;

        public FastMessageProcessor(Stream networkStream, ArrayPool<byte>? pool = null)
        {
            _networkStream = networkStream ?? throw new ArgumentNullException(nameof(networkStream));
            _pool = pool ?? ArrayPool<byte>.Shared;
            // Menyewa buffer dari Pool; tidak ada alokasi heap baru
            _leasedBuffer = _pool.Rent(MaxMessageSize);
        }

        /// <summary>
        /// Memproses stream pesan kontinu dengan alokasi heap 0-byte pada hot path.
        /// Format payload: "ORD:10029348|PRC:450.25|QTY:150\n"
        /// </summary>
        public async ValueTask ProcessIncomingTradesAsync(
            Func<TradeExecutionMessage, ValueTask> onMessageProcessed, 
            CancellationToken ct)
        {
            if (_leasedBuffer == null) 
                throw new ObjectDisposedException(nameof(FastMessageProcessor));

            int bytesInBuffer = 0;

            while (!ct.IsCancellationRequested)
            {
                // Baca langsung ke sisa ruang buffer yang disewa
                Memory<byte> memorySlice = _leasedBuffer.AsMemory(bytesInBuffer, _leasedBuffer.Length - bytesInBuffer);
                int bytesRead = await _networkStream.ReadAsync(memorySlice, ct).ConfigureAwait(false);

                if (bytesRead == 0) break; // End of Stream
                bytesInBuffer += bytesRead;

                ReadOnlySpan<byte> currentSpan = _leasedBuffer.AsSpan(0, bytesInBuffer);
                int processedOffset = 0;

                while (true)
                {
                    ReadOnlySpan<byte> unparsedSpan = currentSpan.Slice(processedOffset);
                    int newlineIndex = unparsedSpan.IndexOf((byte)'\n');

                    if (newlineIndex == -1)
                    {
                        // Pesan belum lengkap, geser sisa byte yang belum terurai ke awal buffer
                        break;
                    }

                    // Ambil frame payload persis 1 pesan tanpa tanda newline
                    ReadOnlySpan<byte> messagePayload = unparsedSpan.Slice(0, newlineIndex);
                    
                    // Parse field langsung dari byte span (UTF-8 binary parsing)
                    if (TryParseTradeMessage(messagePayload, out TradeExecutionMessage trade))
                    {
                        await onMessageProcessed(trade).ConfigureAwait(false);
                    }

                    processedOffset += newlineIndex + 1;
                }

                // Geser data parsial yang tersisa ke indeks awal buffer
                if (processedOffset < bytesInBuffer)
                {
                    int remaining = bytesInBuffer - processedOffset;
                    Array.Copy(_leasedBuffer, processedOffset, _leasedBuffer, 0, remaining);
                    bytesInBuffer = remaining;
                }
                else
                {
                    bytesInBuffer = 0;
                }
            }
        }

        private static bool TryParseTradeMessage(ReadOnlySpan<byte> payload, out TradeExecutionMessage trade)
        {
            // Format yang diharapkan: ORD:10029348|PRC:450.25|QTY:150
            trade = default;
            long orderId = 0;
            decimal price = 0;
            int quantity = 0;

            int pos = 0;
            while (pos < payload.Length)
            {
                ReadOnlySpan<byte> remaining = payload.Slice(pos);
                int pipeIndex = remaining.IndexOf((byte)'|');
                ReadOnlySpan<byte> segment = pipeIndex == -1 ? remaining : remaining.Slice(0, pipeIndex);
                pos += pipeIndex == -1 ? remaining.Length : pipeIndex + 1;

                if (segment.StartsWith("ORD:"u8))
                {
                    if (!Utf8Parser.TryParse(segment.Slice(4), out orderId, out _))
                        return false;
                }
                else if (segment.StartsWith("PRC:"u8))
                {
                    if (!Utf8Parser.TryParse(segment.Slice(4), out price, out _))
                        return false;
                }
                else if (segment.StartsWith("QTY:"u8))
                {
                    if (!Utf8Parser.TryParse(segment.Slice(4), out quantity, out _))
                        return false;
                }
            }

            trade = new TradeExecutionMessage(orderId, price, quantity);
            return true;
        }

        public ValueTask DisposeAsync()
        {
            if (_leasedBuffer != null)
            {
                // Mengembalikan buffer ke Pool. SANGAT KRUSIAL untuk mencegah resource starvation
                _pool.Return(_leasedBuffer, clearArray: false);
                _leasedBuffer = null;
            }
            return ValueTask.CompletedTask;
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Pola / Mekanisme | Keunggulan | Biaya / Konsekuensi Negatif | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **`string.Split` / Substring** | Sintaksis ringkas, sangat mudah dibaca, cepat diimplementasikan. | Mengalokasikan array string dan sub-string masif di Heap. Menekan GC Gen 0. | Skrip sederhana, cold path, pemrosesan CLI non-kritikal. |
| **`Span<T>` / `ReadOnlySpan<T>`** | 0 Byte alokasi Heap. Eksekusi memanfaatkan CPU register & stack. Mendukung SIMD. | Dibatasi aturan `ref struct` (tidak bisa lolos ke field kelas atau lambda async). | Hot path CPU, parsing byte/teks, pemrosesan media/grafis. |
| **`ArrayPool<T>.Shared`** | Menghilangkan alokasi SOH & LOH secara signifikan untuk buffer yang hidup singkat. | Risiko memory corruption jika buffer digunakan setelah di-return (*use-after-free*). Risiko memory leak jika lupa me-return. | Buffer I/O network, pipeline upload file, serialisasi batch. |
| **Class vs Struct vs Record Struct** | Class: Aman dari copy overhead untuk ukuran besar, lifecyle fleksibel.<br>Struct: Mengurangi pointer chasing, 0 GC overhead. | Class: GC tracing & header overhead.<br>Struct: Copying overhead jika ukuran struct $> 16-24$ bytes. | Gunakan `readonly struct` untuk objek domain kecil dan berumur pendek ($< 16$ bytes). |
| **GC Server vs GC Workstation** | Server GC: Throughput multithreaded masif.<br>Workstation GC: Konsumsi baseline RAM minimal. | Server GC: Alokasi RAM lebih besar (alokasi memori proporsional core CPU). | Server untuk sistem backend ASP.NET Core; Workstation untuk desktop app & container hemat RAM. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Boxing & Unboxing pada Struktur Data Primitif
Ketika value type (seperti `int`, `enum`, atau struct) dikonversi menjadi `object` atau type interface, CLR membuat kontainer referensi baru di Heap.

```csharp
// PITFALL: Terjadi alokasi tersembunyi karena boxing
struct PerformanceCounter : IDisposable
{
    public void Dispose() { }
}

void Execute()
{
    PerformanceCounter counter = new();
    // BOXING terjadi di sini jika dipanggil melalui antarmuka:
    IDisposable boxed = counter; // Objek baru dialokasikan di Heap!
    boxed.Dispose();

    // POLA YANG BENAR:
    using (new PerformanceCounter()) // Compiler mengoptimalkan struct dispose tanpa boxing
    {
    }
}
```

### 2. Closure Capture pada Lambda
Ketika fungsi lambda mengakses variabel lokal dari enclosing scope-nya, C# compiler mengompilasi sebuah kelas buatan (*display class*) dan mengalokasikannya ke Managed Heap.

```csharp
// PITFALL: Mengalokasikan Display Class di Heap setiap kali loop berjalan
public void Process(List<int> numbers, int threshold)
{
    // Variabel 'threshold' di-capture oleh lambda. 
    // Compiler men-generate: new DisplayClass { threshold = threshold }
    numbers.RemoveAll(x => x < threshold); 
}

// SOLUSI (.NET 9+ / Modern C# via static lambda):
public void ProcessOptimized(List<int> numbers, int threshold)
{
    // Menggunakan state parameter eksplisit (menghindari closure heap allocation)
    numbers.RemoveAll(static (x, thresh) => x < thresh, threshold);
}
```

### 3. Asynchronous State Machine Boxing
Jika metode `async ValueTask` menyelesaikan operasi secara serentak (*synchronously*), tidak ada alokasi heap yang terjadi. Namun, jika metode mengembalikan `Task` normal atau menggunakan `async void`, framework akan mengalokasikan objek `Task` baru di heap setiap eksekusi selesai.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Memanggil `GC.Collect()` Secara Manual di Hot Path
```csharp
// ANTI-PATTERN:
public void ProcessItem(byte[] data)
{
    Parse(data);
    GC.Collect(); // MALAPETAKA PERFORMA: Memaksa Gen 0, 1, 2 full compaction!
}
```
*Mengapa Salah?* GC mengkalibrasi waktu pemicu berdasarkan metrik alokasi dinamis. Memanggil `GC.Collect()` secara paksa mengganggu heuristik GC, menahan thread aplikasi (*full stop-the-world*), dan mempromosikan objek pendek ke generasi lebih tinggi (Gen 2), menyebabkan pemborosan siklus CPU jangka panjang.  
*Solusi:* Biarkan engine GC berjalan secara otonom. Kendalikan pemanggilan hanya untuk keperluan profiling offline atau pembersihan masif setelah event besar (misal: selesai memuat map level baru di game engine).

### Kesalahan Fatal 2: Lupa Mengembalikan Array ke `ArrayPool<T>` pada Blok `finally`
```csharp
// ANTI-PATTERN:
byte[] buffer = ArrayPool<byte>.Shared.Rent(1024);
DoRiskyOperation(buffer); // Jika crash melempar Exception, buffer hilang selamanya
ArrayPool<byte>.Shared.Return(buffer);

// SOLUSI BENAR:
byte[] buffer = ArrayPool<byte>.Shared.Rent(1024);
try
{
    DoRiskyOperation(buffer);
}
finally
{
    ArrayPool<byte>.Shared.Return(buffer, clearArray: false);
}
```

### Kesalahan Fatal 3: Event Handler Memory Leak (Lapsed Listener Problem)
Objek subscriber yang mendaftarkan event handler ke publisher jangka panjang (seperti singleton) tidak akan pernah dibersihkan oleh GC karena publisher memegang referensi kuat ke subscriber melalui delegates.
*Solusi:* Wajib meng-*unsubcribe* event (`publisher.OnChange -= MyHandler`) melalui implementasi `Dispose()` atau gunakan pola `WeakEventManager`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Keyword `in` dan `readonly struct`:** Mencegah CLR membuat salinan defensif (*defensive copy*) saat melewatkan struct bernilai besar ke dalam method.
   ```csharp
   public readonly struct Matrix4x4 // Menjamin immutability
   {
       // Fields...
   }
   public void Render(in Matrix4x4 transformMatrix) // Dilewatkan by reference tanpa copy
   ```
2. **Standardisasi Pola `Dispose` (Disposable Pattern):**
   ```csharp
   public sealed class NativeResourceManager : IDisposable
   {
       private IntPtr _nativeMemoryHandle;
       private bool _disposed;

       public void Dispose()
       {
           if (_disposed) return;
           
           if (_nativeMemoryHandle != IntPtr.Zero)
           {
               System.Runtime.InteropServices.Marshal.FreeHGlobal(_nativeMemoryHandle);
               _nativeMemoryHandle = IntPtr.Zero;
           }
           
           _disposed = true;
           // Mencegah GC memanggil Finalizer yang tidak lagi diperlukan:
           GC.SuppressFinalize(this);
       }
   }
   ```
3. **Optimalkan Compiler dengan atribut `[SkipLocalsInit]`:** Untuk kalkulasi high-performance internal, tandai method dengan atribut `[SkipLocalsInit]` untuk mencegah CLR mengeksekusi zeroing instruksi CPU (`initflag`) pada memori stack frame.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Pemanfaatan `stackalloc` dengan Safe `Span<T>`
Untuk buffer lokal yang sangat kecil ($< 1$ KB) dan berumur pendek, gunakan `stackalloc` yang di-wrap oleh `Span<T>` alih-alih `new byte[]`.

```csharp
public void EncryptPayload(ReadOnlySpan<byte> secretData)
{
    // AMAN: stackalloc dibungkus langsung oleh Span<byte>
    // Memori dialokasikan langsung di Call Stack. Biaya GC = 0.
    Span<byte> tempBuffer = stackalloc byte[256]; 

    if (secretData.Length > tempBuffer.Length)
    {
        // Fallback ke ArrayPool jika ukuran payload tak terduga melebihi batas stack
        byte[] pooled = ArrayPool<byte>.Shared.Rent(secretData.Length);
        try
        {
            PerformEncryption(secretData, pooled);
        }
        finally
        {
            ArrayPool<byte>.Shared.Return(pooled);
        }
    }
    else
    {
        PerformEncryption(secretData, tempBuffer.Slice(0, secretData.Length));
    }
}
```

*Aturan Emas:* Jangan pernah mengalokasikan memori dinamis tak terbatas pada `stackalloc` karena berpotensi memicu `StackOverflowException` yang berakibat fatal dan langsung membunuh proses aplikasi secara instan tanpa bisa di-catch.

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Sanitasi Memori Rahasia (Cryptographic Safety)
Memori yang digunakan untuk memproses password, token, atau *private key* harus segera dibersihkan dari RAM setelah selesai digunakan. Garbage Collector tidak membersihkan memori heap yang tidak terpakai seketika, sehingga informasi rahasia dapat diekstrak melalui analisis crash dump.

```csharp
using System.Security.Cryptography;

public void ProcessSensitiveCredentials(ReadOnlySpan<char> password)
{
    // Sewa buffer dari memory stack
    Span<byte> passwordBytes = stackalloc byte[password.Length * 3];
    int written = Encoding.UTF8.GetBytes(password, passwordBytes);

    try
    {
        AuthenticateWithNativeDriver(passwordBytes.Slice(0, written));
    }
    finally
    {
        // HARDENING: Hapus jejak kredensial dari RAM secara kriptografis
        CryptographicOperations.ZeroMemory(passwordBytes);
    }
}
```

### 2. Memory Bounds & Buffer Overrun Immunity
Penggunaan Pointer mentah (`void*` / `unsafe`) berisiko membuka celah *buffer overflow*. `Span<T>` menyediakan mitigasi terpasang:
* Mengakses indeks di luar jangkauan (`span[index]`) diverifikasi oleh JIT compiler melalui runtime *bounds check*.
* Jika JIT dapat membuktikan perulangan aman melalui analisis batas invariant loop, JIT akan otomatis menonaktifkan bounds check tanpa mengorbankan keamanan sistem.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Untuk mendeteksi kebocoran memori (*memory leak*) atau aktivitas GC yang abnormal di tingkat production, gunakan ekosistem diagnostik CLI bawaan .NET.

### 1. Observasi Metrik Real-time dengan `dotnet-counters`
Jalankan perintah berikut untuk mengamati perilaku memori secara live:
```bash
dotnet-counters monitor -p <PID> --counters System.Runtime
```

**Metrik Kritis yang Wajib Dipantau:**
* `System.Runtime / % Time in GC`: Harus berada di bawah **5%**. Jika $> 10\%-20\%$, aplikasi mengalami sindrom *GC Thrashing*.
* `System.Runtime / Allocation Rate`: Tingkat alokasi byte per detik. Nilai fluktuatif ekstrem mengindikasikan ketiadaan pooling.
* `System.Runtime / GC Heap Size`: Akumulasi ukuran heap. Jika grafik terus meningkat tanpa plateau, terindikasi *memory leak*.
* `System.Runtime / Gen 2 Collections`: Jika angka ini naik drastis sebanding dengan Gen 0, terjadi masalah promosi memori dini (*premature object promotion*).

### 2. Profiling Memory Dump dengan `dotnet-dump`
```bash
# 1. Ambil snapshot memori aplikasi yang sedang berjalan
dotnet-dump collect -p <PID>

# 2. Buka memory dump untuk dianalisis
dotnet-dump analyze core_xxxx_dump

# 3. Di dalam CLI interactive:
# Melihat statistik alokasi tipe data di Heap:
> dumpheap -stat
# Mencari objek berukuran lebih dari 85000 bytes (LOH):
> dumpheap -min 85000
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+------------------------------------------------------------------------------------+
|                               C# MEMORY CHEAT SHEET                                |
+-----------------------+---------------------+-------------------+------------------+
| Tipe / Konstruk       | Lokasi Penyimpanan  | Biaya GC          | Keterbatasan     |
+-----------------------+---------------------+-------------------+------------------+
| class                 | Managed Heap (SOH)  | Mark, Sweep, Move | Object Overhead  |
| struct                | Stack / Heap Parent | 0 (jika di stack) | Copy cost >16B   |
| readonly ref struct   | Call Stack Sahaja   | Mutlak Nol        | No async / boxing|
| Array (new T[])       | Heap (SOH / LOH)    | Sesuai Gen GC     | Fragmentasi      |
| ArrayPool<T>.Shared   | Pooled Heap Objects | Dihilangkan       | Rawan Use-After- |
|                       |                     | (Daur ulang)      | Free jika silap  |
| stackalloc T[]        | Call Stack          | Mutlak Nol        | StackOverflow risk|
+-----------------------+---------------------+-------------------+------------------+

COMMAND LINE TOOLKIT:
- Profiling Counter : dotnet-counters monitor -p <PID> --counters System.Runtime
- Dump Memory       : dotnet-dump collect -p <PID>
- Trace Alokasi     : dotnet-trace collect -p <PID> --profile gc-collect
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1-5)

1. **Di manakah instans dari sebuah `ref struct` (seperti `Span<T>`) disimpan di memori?**
   * A. Large Object Heap (LOH)
   * B. Small Object Heap (SOH)
   * C. Selalu di Call Stack CPU
   * D. Pinned Object Heap (POH)
   * *Jawaban:* **C**. Aturan CLR melarang `ref struct` untuk diletakkan di heap, menjamin instans tersebut hanya hidup di stack context.

2. **Kondisi apa yang memicu sebuah objek otomatis dialokasikan ke Large Object Heap (LOH)?**
   * A. Objek memiliki finalizer.
   * B. Objek berupa array atau instans bernilai $\ge 85.000$ byte.
   * C. Objek didaftarkan sebagai singleton pada DI Container.
   * D. Objek berumur lebih panjang dari 10 detik.
   * *Jawaban:* **B**. Objek yang memerlukan ruang memori $\ge 85.000$ byte langsung ditempatkan di LOH.

3. **Apa konsekuensi performa utama dari operasi boxing pada value type?**
   * A. Mengakibatkan CPU crash.
   * B. Memindahkan stack pointer ke thread lain.
   * C. Mengalokasikan wrapper object baru pada Heap dan menyalin nilai primitif ke dalamnya.
   * D. Menutup koneksi database yang sedang terbuka.
   * *Jawaban:* **C**. Boxing memaksa pembuatan objek baru pada heap untuk membungkus struct/primitif, membebani GC.

4. **Metode apa yang harus dipanggil di akhir implementasi `Dispose()` untuk mencegah eksekusi Finalizer yang tidak perlu?**
   * A. `GC.Collect()`
   * B. `GC.SuppressFinalize(this)`
   * C. `GC.WaitForPendingFinalizers()`
   * D. `GC.KeepAlive(this)`
   * *Jawaban:* **B**. `GC.SuppressFinalize(this)` memberi instruksi ke CLR untuk menghapus referensi objek dari tabel finalizer queue.

5. **Kapan Anda harus menggunakan `ArrayPool<T>`?**
   * A. Ketika array disimpan seumur hidup aplikasi.
   * B. Ketika array berukuran kecil dan hanya digunakan satu kali.
   * C. Ketika aplikasi sering mengalokasikan dan membuang buffer array sementara dalam skala frekuensi tinggi.
   * D. Ketika membutuhkan sinkronisasi thread otomatis.
   * *Jawaban:* **C**. ArrayPool ideal untuk buffer yang sering dibuat dan dihancurkan secara cepat (*short-lived*).

---

### Soal Intermediate (6-10)

6. **Mengapa pemanggilan `string.Split()` tidak disarankan pada hot path pemrosesan data bervolume tinggi?**
   * A. Karena method tersebut memblokir eksekusi I/O async.
   * B. Karena `string.Split` mengalokasikan array heap baru beserta instans substring baru untuk setiap elemen pecahan.
   * C. Karena `string.Split` tidak mendukung karakter UTF-8.
   * D. Karena method tersebut mengubah string asli (*mutability leak*).
   * *Jawaban:* **B**. Setiap pemanggilan `Split` menghasilkan array baru dan sekumpulan string baru di Managed Heap.

7. **Apa peran Pinned Object Heap (POH) yang diperkenalkan pada modern .NET (.NET 5+)?**
   * A. Menyimpan string interned secara default.
   * B. Mengisolasi objek yang di-*pin* agar tidak memecah segmentasi SOH/LOH dan memicu fragmentasi memori.
   * C. Mempercepat eksekusi instruksi async-await.
   * D. Mengabaikan eksekusi Garbage Collector secara absolut.
   * *Jawaban:* **B**. POH memisahkan objek yang tidak boleh dipindahkan oleh GC sehingga SOH dapat dipadatkan (*compacted*) secara leluasa tanpa terhalang pointer pinned.

8. **Mengapa method asynchronous (`async Task`) tidak dapat menerima parameter bertipe `Span<T>`?**
   * A. Karena `Span<T>` hanya mendukung format ASCII.
   * B. Karena compiler mengonversi method async menjadi state machine class di heap, yang melanggar aturan integritas stack-only dari `ref struct`.
   * C. Karena framework .NET membatasi penggunaan generic pointer.
   * D. Karena Task selalu dijalankan di OS thread yang berbeda.
   * *Jawaban:* **B**. State machine async di-lift ke heap saat terjadi suspension point (`await`), sedangkan `ref struct` mutlak tidak boleh berada di heap.

9. **Apa dampak jangka panjang dari fenomena *Premature Promotion* pada sistem GC .NET?**
   * A. Aplikasi langsung crash dengan kode error fatal.
   * B. Objek berumur pendek terdorong ke Generasi 2, menyebabkan akumulasi sampah di Gen 2 dan memicu frekuensi *Full GC (Stop-The-World)* yang merusak throughput.
   * C. Ukuran call stack CPU melonjak dua kali lipat.
   * D. Semua alokasi memori beralih ke native memory.
   * *Jawaban:* **B**. Jika objek ephemeral selamat dari GC Gen 0 dan Gen 1 secara tidak sengaja, objek tersebut masuk ke Gen 2 yang sangat jarang dibersihkan, memicu pembersihan berat di kemudian waktu.

10. **Apa kegunaan dari `Utf8Parser` dibanding `int.Parse(Encoding.UTF8.GetString(...))`?**
    * A. Mengonversi teks ke basis bilangan heksadesimal secara visual.
    * B. Membaca format JSON langsung menjadi kelas C#.
    * C. Mengurai tipe data primitif langsung dari representasi biner byte UTF-8 tanpa perlu mengalokasikan string baru di heap.
    * D. Memvalidasi skema XML dari stream IO.
    * *Jawaban:* **C**. `Utf8Parser` bekerja langsung di tingkat byte array/span UTF-8 tanpa langkah mediasi pembuatan objek string.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Tantangan
Rancang dan bangun sebuah parser berkas log performa tinggi: **Zero-Allocation In-Memory CSV Log Engine**.

### Kebutuhan Fungsional & Spesifikasi Sistem:
1. **Input:** File log CSV tiruan berukuran minimal 50MB (dapat dihasilkan secara acak melalui generator) dengan format:
   ```csv
   TimestampUtc,DeviceID,StatusCode,LatencyMs
   2026-03-30T10:00:00Z,DEV-0012,200,12.4
   2026-03-30T10:00:01Z,DEV-0043,500,45.1
   ...
   ```
2. **Keluaran:** Hitung metrik berikut:
   * Total baris yang sukses diuraikan.
   * Jumlah kemunculan untuk setiap `StatusCode` (misal: jumlah 200, 404, 500).
   * Rata-rata `LatencyMs` untuk keseluruhan baris.
3. **Batasan Ketat Arsitektur (Zero-Allocation Target):**
   * Alokasi heap selama proses parsing per baris harus bernilai **0 Byte** (di luar alokasi stream pembacaan file dan dictionary penampung metrik agregat di awal).
   * Dilarang menggunakan `StreamReader.ReadLine()`, `string.Split()`, `string.Substring()`, atau Library CSV pihak ketiga.
   * Gunakan `ArrayPool<byte>` untuk membaca chunk stream I/O.
   * Gunakan `ReadOnlySpan<byte>` dan `Utf8Parser` untuk membedah data baris dan kolom.

### Tolok Ukur Keberhasilan (Benchmarking Harness):
Bungkus parser yang dibuat menggunakan benchmark harness sederhana via `BenchmarkDotNet` atau pengukuran delta `GC.GetAllocatedBytesForCurrentThread()`:

```csharp
long startAllocatedBytes = GC.GetAllocatedBytesForCurrentThread();
var engine = new UltraFastLogEngine();
engine.ExecuteProcess("large_logs.csv");
long totalAllocated = GC.GetAllocatedBytesForCurrentThread() - startAllocatedBytes;

Console.WriteLine($"Total Memory Allocated during execution: {totalAllocated} bytes");
// Target: Dekat dengan ukuran buffer awal yang dialokasikan, TIDAK bertumbuh secara proporsional terhadap jumlah baris file!
```

---
*Selamat! Anda telah menguasai mekanisme manajemen memori tingkat lanjut, GC internals, serta arsitektur High-Performance di C# .NET.*