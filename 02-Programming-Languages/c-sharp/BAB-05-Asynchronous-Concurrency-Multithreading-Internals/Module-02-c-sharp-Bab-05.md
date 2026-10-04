# BAB 05: Asynchronous, Concurrency & Multithreading Internals
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan memiliki kompetensi tingkat lanjut untuk:
1. **Menganalisis dan Membedah Arsitektur CLR ThreadPool**: Memahami mekanisme internal *Hill Climbing Algorithm*, partisi *Global Queue* vs *Local Work-Stealing Queues*, serta siklus hidup *I/O Completion Ports (IOCP)*.
2. **Mendekonstruksi Compiler-Generated Async State Machine**: Memahami struktur kode IL yang dihasilkan Roslyn saat menurunkan `async`/`await`, titik-titik alokasi memori pada heap, dan optimasi siklus hidup struct state machine menggunakan `ValueTask` dan `IValueTaskSource`.
3. **Menguasai Context Flow & Propagation**: Mengontrol propagasi `ExecutionContext` dan `SynchronizationContext`, mengeliminasi *overhead* context capturing via `ConfigureAwait(false)`, dan mencegah kebocoran *ambient context*.
4. **Mengimplementasikan Pola Konkurensi Kinerja Tinggi (Lock-Free & Bounded Channels)**: Menggantikan primitif penguncian berat (`Monitor`, `ReaderWriterLockSlim`) dengan operasi atomik `Interlocked`, *memory barriers*, dan struktur data asinkron berbasis *backpressure* (`System.Threading.Channels`).
5. **Mendiagnosis Masalah Konkurensi Kompleks pada Skala Enterprise**: Mengidentifikasi dan memitigasi *thread pool starvation*, *async-over-sync/sync-over-async deadlocks*, *async cancellation leaks*, serta mendiagnosis dump memori produksi menggunakan `dotnet-dump` dan visualisasi metrik performa.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Pemahaman fundamental sintaksis `async`/`await` dan kelas dasar `Task` pada C#.
* Model memori dasar CLR (perbedaan Stack vs Heap, konsep Garbage Collection Gen 0/1/2).
* Penggunaan primitif multithreading dasar (`Thread`, `Monitor`, `lock`).
* Kemampuan membaca decompiled C# (IL / lowered code) menggunakan decompilers seperti ILSpy atau SharpLab.io.

---

### 3. Concept & Internal Architecture

#### 3.1 CLR ThreadPool: Hill Climbing & Work-Stealing Engine

CLR ThreadPool dirancang bukan sekadar sebagai kumpulan *OS threads*, melainkan sebagai *adaptive resource manager* yang meminimalkan *context switching* sembari memaksimalkan *CPU throughput*.

```
+-----------------------------------------------------------------------+
|                             CLR ThreadPool                            |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  |             Global FIFO Queue (ThreadPool.QueueUserWorkItem)     |  |
|  +-----------------------------------------------------------------+  |
|             |                                   |                     |
|             v                                   v                     |
|  +--------------------+               +--------------------+          |
|  | Worker Thread 1    |               | Worker Thread 2    |          |
|  | +----------------+ |   Steal Last  | +----------------+ |          |
|  | | Local Work-    |<==================| Local Work-    | |          |
|  | | Stealing Queue | | (FIFO from top) | | Stealing Queue | |          |
|  | | (LIFO)         | |                 | | (LIFO)         | |          |
|  | +----------------+ |                 | +----------------+ |          |
|  +--------------------+                 +--------------------+          |
|            |                                       |                  |
+------------|---------------------------------------|------------------+
             v                                       v
   +------------------------------------------------------------+
   |             Hill Climbing Heuristic Engine                 |
   |  (Evaluasi throughput vs thread count setiap interval 500ms)|
   +------------------------------------------------------------+
```

1. **Global Queue vs Local Work-Stealing Queues**:
   * *Global Queue* beroperasi secara FIFO (First-In, First-Out). Task yang di-dispatch melalui `ThreadPool.QueueUserWorkItem` atau dijadwalkan dari thread non-pool masuk ke antrean ini dengan proteksi sinkronisasi berbasis *global lock*.
   * Setiap *Worker Thread* memiliki *Local Work-Stealing Queue* sendiri (beroperasi secara LIFO untuk memaksimalkan *cache locality*). Jika Worker Thread menghasilkan task baru via `Task.Run` atau kelanjutan `await`, task dimasukkan ke antrean lokal thread tersebut tanpa *lock contention*.
   * **Work-Stealing Algorithm**: Ketika antrean lokal suatu thread kosong, ia akan mencari pekerjaan dari Global Queue. Jika Global Queue kosong, ia akan *mencuri* (steal) pekerjaan dari bagian bawah (FIFO order) antrean lokal thread lain menggunakan operasi atomik `Interlocked.CompareExchange`.

2. **Hill Climbing Algorithm**:
   ThreadPool tidak serta-merta menambah thread baru ketika ada antrean. Setiap interval waktu tertentu (~500ms), algoritma *Hill Climbing* mengukur *throughput* penyelesaian tugas terhadap jumlah thread aktif. Jika penambahan thread meningkatkan throughput tanpa memicu degradasi akibat CPU context switching, batas thread dinaikkan. Sebaliknya, jika context switching mendominasi, jumlah thread dipangkas secara adaptif.

3. **I/O Completion Ports (IOCP)**:
   Pada sistem operasi berbasis NT, operasi I/O asinkron sejati (disk, network socket) tidak menggunakan thread pool pekerja selama proses transfer data. OS kernel mendaftarkan *handle* ke IOCP. Ketika controller perangkat keras menyelesaikan pembacaan paket network, interrupt hardware memicu OS memasukkan *completion packet* ke IOCP, yang kemudian membangkitkan thread IOCP khusus pada CLR untuk memproses kelanjutan `Task`.

#### 3.2 Compiler Lowering: The Async State Machine

Ketika Roslyn mengompilasi method bertanda `async`, ia mengubah method tersebut menjadi struktur data `IAsyncStateMachine`.

```csharp
// Kode Asal
public async Task<int> FetchDataAsync()
{
    int baseValue = 10;
    int result = await CallRemoteServiceAsync();
    return baseValue + result;
}
```

Diturunkan (lowered) oleh compiler menjadi:

```csharp
[CompilerGenerated]
private struct <FetchDataAsync>d__0 : IAsyncStateMachine
{
    public int <>1__state;
    public AsyncTaskMethodBuilder<int> <>t__builder;
    public int <baseValue>5__1;
    private TaskAwaiter<int> <>u__1;

    public void MoveNext()
    {
        int num = <>1__state;
        int result;
        try
        {
            TaskAwaiter<int> awaiter;
            if (num != 0)
            {
                <baseValue>5__1 = 10;
                awaiter = CallRemoteServiceAsync().GetAwaiter();
                if (!awaiter.IsCompleted)
                {
                    <>1__state = 0;
                    <>u__1 = awaiter;
                    <>t__builder.AwaitUnsafeOnCompleted(ref awaiter, ref this);
                    return; // Yield eksekusi thread
                }
            }
            else
            {
                awaiter = <>u__1;
                <>u__1 = default;
                <>1__state = -1;
            }
            int remoteResult = awaiter.GetResult();
            result = <baseValue>5__1 + remoteResult;
        }
        catch (Exception exception)
        {
            <>1__state = -2;
            <>t__builder.SetException(exception);
            return;
        }
        <>1__state = -2;
        <>t__builder.SetResult(result);
    }

    public void SetStateMachine(IAsyncStateMachine stateMachine) => 
        <>t__builder.SetStateMachine(stateMachine);
}
```

*State Machine Lifecycle*:
* **Initial State (-1)**: Method dieksekusi secara sinkron sampai menemukan operator `await` pertama yang mengembalikan `awaiter.IsCompleted == false`.
* **Suspension State (0)**: Compiler menyimpan state lokal ke field struct (`<baseValue>5__1`), mengaitkan struct state machine ke `AsyncTaskMethodBuilder`, lalu melakukan alokasi heap (*boxing*) struct state machine tersebut agar tetap hidup saat stack frame method awal hancur.
* **Resume**: Ketika operasi asinkron selesai, callback memanggil `MoveNext()`. State bernilai `0` memicu eksekusi melompat langsung ke label pengambilan hasil via `awaiter.GetResult()`.

#### 3.3 Contextual Boundaries: ExecutionContext vs SynchronizationContext

```
+-------------------------------------------------------------------------------+
| ExecutionContext (Ambient Security, AsyncLocal, Transaction, Culture)        |
| Flow: Mengalir secara implisit melintasi thread boundary via task switching.   |
|                                                                               |
|   +-----------------------------------------------------------------------+   |
|   | SynchronizationContext (Scheduler Abstraction)                        |   |
|   | Flow: Mendikte "DI MANA" callback dijalankan (e.g., UI Thread, ASP.NET|   |
|   | Legacy Context). Diabaikan jika ConfigureAwait(false) disetel.        |   |
|   +-----------------------------------------------------------------------+   |
+-------------------------------------------------------------------------------+
```

* **ExecutionContext**: Mewakili lingkungan komputasi logis. Komponen vitalnya adalah `AsyncLocal<T>`. Saat thread memanggil `await`, `ExecutionContext.Capture()` mengambil metadata konteks berjalan dan memulihkannya (`ExecutionContext.Restore()`) pada worker thread yang menjalankan kelanjutan task.
* **SynchronizationContext**: Objek abstraksi perantara (contoh: `WinFormsSynchronizationContext`, `WpfSynchronizationContext`). Pada .NET modern (ASP.NET Core), `SynchronizationContext` bernilai `null` secara default demi meminimalkan *dispatching overhead*. Namun, pemanggilan `ConfigureAwait(false)` tetap merupakan praktik penting pada library untuk menghindari biaya pengecekan context dan memastikan eksekusi kelanjutan tidak memaksakan context switcher.

---

### 4. Why & What

| Dimensi | Pendekatan Konkurensi Naif | Pendekatan Arsitektur Produksi |
| :--- | :--- | :--- |
| **I/O Handling** | Memblokir thread worker (`.Result`, `.Wait()`) hingga respons jaringan kembali. | Asinkron murni berbasis IOCP. Thread dikembalikan ke pool saat I/O sedang berjalan. |
| **Manajemen Memori** | Mengalokasikan `Task<T>` baru untuk setiap pemanggilan fungsi berulang berfrekuensi tinggi. | Menggunakan `ValueTask<T>` untuk eksekusi yang sering selesai sinkron (*hot-path caching*), atau `IValueTaskSource`. |
| **Sinkronisasi Data** | Menggunakan keyword `lock` (Monitor) yang mengeksekusi *system call* / *thread suspension* saat kontensi tinggi. | Operasi atomik berbasis CPU cache line (`Interlocked`) atau model antrean non-blocking (`Channels`). |
| **Context Propagation** | Membiarkan `ExecutionContext` mengalir pada seluruh loop dan stream intensif data. | Melakukan `ExecutionContext.SuppressFlow()` pada skenario performa ekstrem untuk memangkas *allocation & copy overhead*. |

---

### 5. How (Workflow Detail)

Alur penanganan I/O asinkron berkecepatan tinggi dari inisiasi hingga penyelesaian:

```
[User App Code]
     |
     v
1. socket.ReadAsync(buffer)
     |
     +--> Driver Socket Windows (Winsock / AFD.sys) menginisiasi read request
     |
2. Kernel IO Request Packet (IRP) dialokasikan
     |
3. Operasi pending dikembalikan -> awaiter.IsCompleted == false
     |
4. State Machine me-yield thread -> Thread kembali melayani tugas lain di ThreadPool
     |
     ~ ~ ~ Hardware Controller mentransfer data paket via DMA ke RAM ~ ~ ~
     |
5. Hardware Interrupt -> Interrupt Service Routine (ISR) -> DPC
     |
6. Driver menandai IRP selesai -> Kernel meletakkan completion entry ke IOCP
     |
7. CLR I/O Completion ThreadPool Thread terbangun dari WaitForMultipleObjectsEx
     |
8. Thread IOCP membaca hasil paket I/O -> Memanggil completion callback
     |
9. Callback menjadwalkan continuation state machine via ThreadPool.UnsafeQueueUserWorkItem
     |
10. Worker Thread mengambil continuation -> StateMachine.MoveNext() -> Eksekusi berlanjut
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Dapur Restoran Bintang Lima

Bayangkan sebuah dapur restoran skala enterprise:
* **Naive Multithreading**: Setiap pesanan pelanggan mempekerjakan satu koki khusus. Koki memasukkan steik ke oven, lalu berdiri diam di depan oven selama 20 menit menunggunya matang (*thread blocking*). Dapur kehabisan ruang (kehabisan thread OS) meskipun kompor lainnya menganggur.
* **Async/Await (ThreadPool & IOCP)**: Koki memasukkan steik ke oven cerdas, menyetel timer digital (IOCP), lalu segera berbalik melayani pembuatan sup (membebaskan thread). Ketika timer berbunyi, lonceng berdering. Koki mana pun yang sedang luang (atau koki yang sama) menghampiri oven dan melanjutkan plating steik tersebut.
* **Work-Stealing Queue**: Setiap koki memiliki papan tugas pribadi. Jika Koki A menyelesaikan semua tugasnya lebih cepat dari Koki B, Koki A tidak duduk santai; ia berjalan ke papan tugas Koki B dan mengambil tugas dari bawah tumpukan untuk dikerjakan.

```
Papan Koki A (Local LIFO)       Papan Koki B (Local LIFO)
+-----------------------+       +-----------------------+
| Tugas 3 (Teratas/Push)|       | Tugas 3               |
| Tugas 2               |       | Tugas 2               |
| Tugas 1 (Bawah/Pop)   |       | Tugas 1 (Target Steal)|
+-----------------------+       +-----------------------+
           ^                                |
           |                                v
   Koki A memproses tugasnya      Koki C (Menganggur)
   sendiri secara LIFO            Mencuri Tugas 1 Koki B via FIFO
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Optimasi Zero-Allocation dengan `ValueTask<T>`

Contoh pengembalian data dari in-memory cache menggunakan `ValueTask<T>` untuk mencegah alokasi objek `Task` pada heap jika data tersedia secara instan (jalur sinkron).

```csharp
using System;
using System.Collections.Concurrent;
using System.Threading.Tasks;

public sealed class CacheManager
{
    private readonly ConcurrentDictionary<string, string> _memoryCache = new();

    public ValueTask<string> GetPayloadAsync(string key)
    {
        // Jalur Sinkron (Hot Path): Zero-allocation, tidak ada instansiasi Task di heap
        if (_memoryCache.TryGetValue(key, out var cachedValue))
        {
            return new ValueTask<string>(cachedValue);
        }

        // Jalur Asinkron (Cold Path): Alokasi Task hanya terjadi saat I/O benar-benar dibutuhkan
        return new ValueTask<string>(FetchFromStorageSlowAsync(key));
    }

    private async Task<string> FetchFromStorageSlowAsync(string key)
    {
        await Task.Delay(100).ConfigureAwait(false); // Simulasi remote storage fetch
        var value = $"Data-for-{key}-at-{DateTime.UtcNow.Ticks}";
        _memoryCache[key] = value;
        return value;
    }
}
```

#### 7.2 Practical Example: Enterprise Ingestion Processing Pipeline Menggunakan `System.Threading.Channels`

Arsitektur produksi: Pipeline asinkron thread-safe yang mengonsumsi log transaksi bervolume tinggi dengan mekanisme *bounded backpressure*, multi-reader, dan pembatasan konkurensi terkontrol.

```csharp
using System;
using System.Diagnostics;
using System.Threading;
using System.Threading.Channels;
using System.Threading.Tasks;

public sealed record TelemetryRecord(Guid TransactionId, double Amount, long Timestamp);

public sealed class TelemetryIngestionEngine : IAsyncDisposable
{
    private readonly Channel<TelemetryRecord> _channel;
    private readonly CancellationTokenSource _cts;
    private readonly Task[] _workers;
    private readonly int _workerCount;

    public TelemetryIngestionEngine(int capacity, int workerCount)
    {
        _workerCount = workerCount;
        _cts = new CancellationTokenSource();

        // Menggunakan BoundedChannel untuk mencegah OutOfMemoryException saat burst traffic
        var options = new BoundedChannelOptions(capacity)
        {
            FullMode = BoundedChannelFullMode.Wait, // Backpressure: produsen menunggu jika antrean penuh
            SingleWriter = false,
            SingleReader = false
        };

        _channel = Channel.CreateBounded<TelemetryRecord>(options);
        _workers = new Task[_workerCount];

        for (int i = 0; i < _workerCount; i++)
        {
            int workerId = i;
            _workers[i] = Task.Run(() => ProcessQueueAsync(workerId, _channel.Reader, _cts.Token));
        }
    }

    public async ValueTask PublishTelemetryAsync(TelemetryRecord record, CancellationToken cancellationToken = default)
    {
        // Menyisipkan data secara non-blocking kecuali antrean penuh (terkena backpressure)
        using var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, _cts.Token);
        await _channel.Writer.WriteAsync(record, linkedCts.Token).ConfigureAwait(false);
    }

    private async Task ProcessQueueAsync(int workerId, ChannelReader<TelemetryRecord> reader, CancellationToken ct)
    {
        // Pola idiomatis pembacaan channel: terus membaca sampai writer ditutup dan antrean terkuras
        try
        {
            while (await reader.WaitToReadAsync(ct).ConfigureAwait(false))
            {
                while (reader.TryRead(out var record))
                {
                    await ExecuteHeavyBusinessLogicAsync(workerId, record, ct).ConfigureAwait(false);
                }
            }
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            // Graceful exit saat pembatalan diminta
        }
    }

    private async Task ExecuteHeavyBusinessLogicAsync(int workerId, TelemetryRecord record, CancellationToken ct)
    {
        // Simulasi kalkulasi analitik non-blocking
        await Task.Delay(5, ct).ConfigureAwait(false); 
    }

    public async ValueTask DisposeAsync()
    {
        _channel.Writer.Complete(); // Menandai produsen berhenti
        await _channel.Reader.Completion.ConfigureAwait(false); // Menunggu buffer diproses tuntas
        _cts.Cancel();

        try
        {
            await Task.WhenAll(_workers).ConfigureAwait(false);
        }
        catch (Exception)
        {
            // Menelan exception pembatalan pekerja saat cleanup
        }
        finally
        {
            _cts.Dispose();
        }
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Payment Ledger Gateway (50.000 TPS) Mengalami Thread Pool Starvation & Memory Spikes

* **Latar Belakang**:
  Sebuah sistem payment gateway memproses lonjakan transaksi hingga 50.000 TPS pada jam promo flash-sale. Server menggunakan kluster Azure VM (32 vCPU per instance). Tiba-tiba waktu respons API melonjak dari 15ms menjadi 12.000ms, diikuti kegagalan masif HTTP 503 dan sistem crash.
  
* **Investigasi Masalah**:
  1. Dump memori dianalisis menggunakan perintah `dotnet-dump analyze`:
     ```text
     > threadpool
     Work Items in Queue: 184,210
     CPU Utilization: 22%
     Worker Thread Count: 1,850 (Max: 32,767, Min: 32)
     Monitor Contention Count: 42,900/sec
     ```
  2. Ditemukan pola fatal pada middleware otentikasi dan logging:
     ```csharp
     // KODE FATAL 1: Sync-Over-Async
     var validationResult = _securityValidator.ValidateTokenAsync(token).Result;
     
     // KODE FATAL 2: Alokasi Task masif tanpa batas
     Parallel.ForEach(transactions, tx => {
         _dbRepository.SaveAsync(tx).Wait();
     });
     ```
  3. **Akar Permasalahan (Root Cause)**:
     * Penggunaan `.Result` dan `.Wait()` memblokir worker thread pool.
     * Karena thread terblokir menunggu response jaringan, algoritma *Hill Climbing* salah mendiagnosis kebutuhan komputasi dan hanya menambahkan thread baru secara lambat (~1-2 thread per detik).
     * Terjadi kondisi *ThreadPool Starvation*: ribuan callback I/O yang telah rampung di network card mengantre di Global Queue tanpa ada thread yang tersedia untuk mengeksekusinya.

* **Arsitektur Solusi**:
  1. **Purifikasi Async End-to-End**: Mengeliminasi seluruh pola `.Result` dan `.Wait()`. Mengganti seluruh interface pipeline menjadi non-blocking asinkron berbasis `ValueTask`.
  2. **Tuning ThreadPool MinThreads**:
     Mengatur threshold minimum thread pool pada startup agar sistem tidak tercekik latensi Hill Climbing saat cold-start lonjakan:
     ```csharp
     ThreadPool.SetMinThreads(workerThreads: 256, completionPortThreads: 256);
     ```
  3. **Penjadwalan Partisi Menggunakan Channel Bounded Backpressure**: Menggantikan `Parallel.ForEach` blocking dengan ingestion engine berkapasitas terbatas (bounded channel) yang memantulkan rate limit HTTP 429 kepada pemanggil sebelum server kehabisan kapasitas memori heap.

* **Hasil Setelah Remediasi**:
  * Throughput stabil pada 52.000 TPS.
  * Latensi p99 terpangkas dari 12 detik menjadi **18ms**.
  * Thread count stabil di angka 120-150 worker threads tanpa lonjakan fluktuatif.
  * Alokasi memori heap GC Gen 0 terpangkas sebesar **68%**.

---

### 9. Trade-offs

| Pendekatan / Teknik | Keuntungan (Pros) | Biaya / Konsekuensi (Cons) | Metrik Terdampak |
| :--- | :--- | :--- | :--- |
| **`Task<T>`** | Fleksibel, aman untuk di-await berkali-kali, dapat dioperasikan dengan `Task.WhenAll` / `Task.WhenAny`. | Mengalokasikan 1 objek referensi di heap setiap pemanggilan unik. | Menambah beban GC Gen 0 pada skala puluhan ribu throughput per detik. |
| **`ValueTask<T>`** | Zero heap allocation bila method selesai secara sinkron (*hot-path* caching). | Menambah ukuran return type pada call stack (berbasis struct). **FATAL** jika di-await lebih dari 1 kali atau di-await secara paralel. | Memangkas tekanan alokasi GC; sedikit menambah waktu salin nilai pada stack bila method lambat. |
| **`Channels<T>`** | Mengisolasi produsen dan konsumen dengan aman, mendukung backpressure, performa tinggi tanpa lock manual. | Memerlukan arsitektur modular yang lebih kompleks (decoupling per baris pemrosesan). | Mempertahankan kestabilan latensi p99, mencegah lonjakan *Out-Of-Memory*. |
| **Lock-Free (`Interlocked`)** | Kecepatan CPU instan (nanodetik), tidak pernah menangguhkan thread pekerja ke kernel OS. | Logika pemodelan algoritma sangat rumit (rentan ABA problem dan reordering instruksi compiler/CPU). | CPU L1/L2 cache line bouncing tinggi jika variabel diperebutkan oleh banyak core bersamaan. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Anti-Pattern 1: Async-Over-Sync & Sync-Over-Async
* **Kesalahan**: Menggunakan `.GetAwaiter().GetResult()`, `.Result`, atau `.Wait()` pada kode yang memiliki konteks thread khusus, memicu deadlock atau thread pool starvation.
* **Deteksi**: Periksa call stack via memory dump: jika terlihat method `Task.Wait()` bertengger di atas stack frame worker thread, starvation sedang berlangsung.
* **Perbaikan**: Seluruh rantai panggilan harus diubah menjadi `async Task` atau `async ValueTask`.

#### 10.2 Anti-Pattern 2: `async void` (Fire-and-Forget Lethal Bug)
* **Kesalahan**: Menulis method `public async void ProcessPayment()` selain pada event handler UI.
* **Dampak**: Exception yang dilempar di dalam `async void` tidak dapat ditangkap oleh blok `try-catch` pemanggil dan langsung menumbangkan seluruh proses aplikasi (*process crash* unhandled exception).
* **Perbaikan**: Selalu gunakan `public async Task ProcessPaymentAsync()`.

#### 10.3 Anti-Pattern 3: CancellationTokenSource Memory Leak
* **Kesalahan**: Membuat linked token source tanpa dispose eksplisit:
  ```csharp
  // KODE BOCOR:
  var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(incomingToken);
  // linkedCts mendaftarkan callback ke incomingToken. Jika incomingToken berumur panjang,
  // linkedCts tidak akan pernah di-GC!
  ```
* **Perbaikan**: Selalu gunakan blok `using` pada `CancellationTokenSource.CreateLinkedTokenSource`:
  ```csharp
  using var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(incomingToken);
  ```

#### Panduan Diagnostik: Melacak Thread Starvation di Shell Server

```bash
# 1. Pantau Thread Count & Queue Length secara real-time
dotnet-counters monitor System.Runtime --providers Microsoft-Windows-DotNETRuntime

# Perhatikan metrik:
# - ThreadPool Thread Count
# - ThreadPool Queue Length (Jika nilai ini konsisten > 0 dan terus bertambah, starvation terjadi)
# - CPU Usage

# 2. Ambil snapshot memori saat antrean membengkak
dotnet-dump collect -p <PID> -o starvation_dump.dmp

# 3. Analisis tumpukan panggilan worker thread yang terblokir
dotnet-dump analyze starvation_dump.dmp
> clrthreads
> ~*e clrstack
```

---

### 11. Best Practices (Production Checklist)

| No | Aturan Arsitektur | Kategori | Konsekuensi Pelanggaran |
| :---: | :--- | :--- | :--- |
| 1 | Tambahkan `.ConfigureAwait(false)` pada seluruh layer library non-UI / middleware backend. | Latency & Safety | Context overhead yang tidak diperlukan; risiko deadlock pada lingkungan bersinkronisasi. |
| 2 | Jangan pernah melakukan `await` ganda pada instance `ValueTask<T>`. | Memory / Safety | `InvalidOperationException` atau merusak state internal reuse objek `IValueTaskSource`. |
| 3 | Gunakan `System.Threading.Channels` untuk pola Producer-Consumer, hindari `BlockingCollection<T>` pada pipeline asinkron murni. | Throughput | `BlockingCollection` memblokir OS thread; `Channels` mendukung penghentian non-blocking. |
| 4 | Selalu gunakan `CancellationToken` secara komprehensif pada semua API asinkron. | Resource Leak | I/O sockets dan DB connection pool tertahan pada operasi remote yang sudah diabaikan klien. |
| 5 | Nonaktifkan penangkapan context (`ExecutionContext.SuppressFlow()`) pada event loop performa tinggi bila `AsyncLocal` tidak dibutuhkan. | Memory | Biaya alokasi copy struct context saat dispatching antar thread terpangkas signifikan. |
| 6 | Konfigurasi Static Analyzer: aktifkan rule `CA2007` (Do not directly await a Task) dan `VSTHRD103` (Call async methods when in an async method). | CI/CD Quality | Memastikan standardisasi tim dev bebas dari sync-over-async bugs secara otomatis di pipeline CI. |

---

### 12. Hands-on Practice

Simpan seluruh kode berikut dalam direktori proyek Anda: `hands-on/m02/`

#### Langkah 1: Inisialisasi Proyek Console Kinerja Tinggi
```bash
mkdir -p hands-on/m02/HighThroughputPipeline
cd hands-on/m02/HighThroughputPipeline
dotnet new console -f net8.0
```

#### Langkah 2: Implementasi Pipeline Asinkron dengan Metrik Monitor
Edit file `Program.cs` dan masukkan kode berikut:

```csharp
using System;
using System.Diagnostics;
using System.Threading;
using System.Threading.Channels;
using System.Threading.Tasks;

namespace HighThroughputPipeline;

internal static class Program
{
    private static async Task Main(string[] args)
    {
        Console.WriteLine("=== Menguji Pipeline Bounded Backpressure Kinerja Tinggi ===");

        const int totalItems = 100_000;
        const int channelCapacity = 1_000;
        const int consumerWorkers = 4;

        var channel = Channel.CreateBounded<int>(new BoundedChannelOptions(channelCapacity)
        {
            FullMode = BoundedChannelFullMode.Wait,
            SingleReader = false,
            SingleWriter = true
        });

        using var cts = new CancellationTokenSource();
        var sw = Stopwatch.StartNew();

        // 1. Jalankan Consumer Workers
        var consumers = new Task[consumerWorkers];
        long itemsProcessed = 0;

        for (int i = 0; i < consumerWorkers; i++)
        {
            int workerId = i;
            consumers[i] = Task.Run(async () =>
            {
                var reader = channel.Reader;
                while (await reader.WaitToReadAsync(cts.Token).ConfigureAwait(false))
                {
                    while (reader.TryRead(out _))
                    {
                        // Mensimulasikan komputasi mikro CPU
                        Interlocked.Increment(ref itemsProcessed);
                    }
                }
            });
        }

        // 2. Jalankan Producer
        var producer = Task.Run(async () =>
        {
            var writer = channel.Writer;
            for (int i = 0; i < totalItems; i++)
            {
                await writer.WriteAsync(i, cts.Token).ConfigureAwait(false);
            }
            writer.Complete();
        });

        // 3. Monitor thread count & progress di latar belakang
        var monitorTask = Task.Run(async () =>
        {
            while (!channel.Reader.Completion.IsCompleted)
            {
                Console.WriteLine($"[Monitor] Processed: {Volatile.Read(ref itemsProcessed):N0} | Threads: {ThreadPool.ThreadCount}");
                await Task.Delay(250).ConfigureAwait(false);
            }
        });

        await producer.ConfigureAwait(false);
        await channel.Reader.Completion.ConfigureAwait(false);
        await Task.WhenAll(consumers).ConfigureAwait(false);
        await monitorTask.ConfigureAwait(false);

        sw.Stop();
        Console.WriteLine($"=== Selesai ===");
        Console.WriteLine($"Total Item: {itemsProcessed:N0} dalam {sw.ElapsedMilliseconds} ms");
        Console.WriteLine($"Throughput: {(itemsProcessed / (sw.ElapsedMilliseconds / 1000.0)):N0} ops/sec");
    }
}
```

#### Langkah 3: Eksekusi dan Verifikasi Metrik
Jalankan program pada terminal Anda:
```bash
dotnet run -c Release
```

---

### 13. Exercise

#### Level 1 - Easy (Diagnostik Async Void)
* **Tugas**: Perbaiki potongan kode berikut agar tidak menumbangkan aplikasi ketika terjadi exception:
  ```csharp
  public class NotificationService
  {
      public async void SendAlert(string message)
      {
          await Task.Delay(10);
          throw new InvalidOperationException("Jaringan terputus!");
      }
  }
  ```
* **Kriteria Selesai**: Mengubah signature method, menangkap exception secara elegan pada pemanggil, dan tidak ada crash runtime yang terjadi.

#### Level 2 - Medium (Implementasi Resilient Concurrent Worker Pool)
* **Tugas**: Buatlah class `PriorityWorkerPool<T>` berbasis `Channel<T>` yang memiliki dua prioritas antrean: *High* dan *Low*. Worker harus selalu mengonsumsi antrean *High* terlebih dahulu sebelum memproses item dari antrean *Low*, dengan jaminan graceful shutdown tanpa kehilangan data yang sudah masuk antrean saat cancellation token dibatalkan.
* **Kriteria Selesai**: Integrasikan unit test yang memverifikasi bahwa 1.000 item berprioritas tinggi tuntas dieksekusi lebih dulu dibandingkan item berprioritas rendah ketika keduanya dimasukkan serentak.

#### Level 3 - Hard (Custom Reset-Free `IValueTaskSource<T>` Implementation)
* **Tugas**: Buatlah custom struct wrapper yang mengimplementasikan `IValueTaskSource<int>` untuk membangun custom manual reset awaitable logic. Objek ini harus dapat dialokasikan di awal (pre-allocated) dan digunakan kembali (reused) berkali-kali tanpa menghasilkan alokasi memori GC saat dilakukan `await` berulang.
* **Kriteria Selesai**: Verifikasi menggunakan `BenchmarkDotNet` bahwa total alokasi memori heap adalah tepat **0 bytes** pada 1.000.000 iterasi penyelesaian sinkron dan asinkron.

---

### 14. Challenge

**Skenario**: Bangun sebuah modul arsitektur bernama **"Zero-Alloc High-Frequency Order Router"**.
1. Modul harus mampu menerima 100.000 order finansial per detik dari berbagai thread klien.
2. Setiap order divalidasi keamanannya menggunakan token berbasis `AsyncLocal<T>`.
3. Validasi token memerlukan pengecekan data cache lokal (sinkron 95% dari waktu) dan remote DB check (asinkron 5% dari waktu). Anda diwajibkan menggunakan pola `ValueTask<bool>` tanpa alokasi objek heap pada jalur 95% tersebut.
4. Terapkan mekanisme circuit-breaker atomik berbasis `Interlocked`: jika kegagalan validasi remote I/O berturut-turut mencapai 50 kali, sistem langsung melempar fast-fail exception selama 5 detik berikutnya tanpa menyentuh network I/O.
5. Gunakan `BoundedChannel` untuk menghubungkan router ke dispatch worker pool. Jika antrean router melebihi kapasitas 5.000 pesanan, order baru harus dialirkan ke file buffer sekunder secara non-blocking tanpa membuat thread HTTP controller hang.

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic
1. Apa fungsi utama algoritma *Hill Climbing* pada CLR ThreadPool?
2. Mengapa method bertanda `async void` berbahaya bila digunakan di luar penanganan UI Event Handler?
3. Sebutkan perbedaan perilaku antrean *Global Queue* vs *Local Queue* pada CLR ThreadPool saat memasukkan pekerjaan baru!
4. Apa yang terjadi jika kode aplikasi memanggil `.GetAwaiter().GetResult()` pada ThreadPool worker thread di lingkungan yang kekurangan ketersediaan thread?
5. Mengapa pemanggilan `ConfigureAwait(false)` direkomendasikan pada penulisan class library backend?

#### Soal Intermediate
6. Jelaskan secara mekanis apa yang dilakukan compiler Roslyn saat membungkus struct `IAsyncStateMachine` ke dalam heap memory (*boxing*)!
7. Bagaimana struktur kerja *Work-Stealing* algorithm mencegah thread contention saat sebuah thread mencuri tugas dari thread lain?
8. Mengapa instance `ValueTask<T>` tidak boleh di-await lebih dari satu kali atau dipanggil menggunakan `Task.WhenAll` secara sembarangan?
9. Apa perbedaan esensial antara `ExecutionContext` dan `SynchronizationContext` dalam proses delegasi callback asinkron?
10. Bagaimana `System.Threading.Channels` mengelola kondisi *Backpressure* dibandingkan dengan `System.Collections.Concurrent.ConcurrentQueue<T>`?

#### Skenario Kasus Produksi
11. **Skenario 1**: Sebuah microservice ASP.NET Core menunjukkan penggunaan CPU hanya 15%, namun API metrics menunjukkan request queuing yang sangat panjang dan latensi HTTP membengkak puluhan detik. Dari profiling didapatkan bahwa penambahan thread terhenti di angka 50 thread. Jelaskan akar masalah arsitektur internal CLR yang menyebabkan fenomena ini dan bagaimana memulihkannya!
12. **Skenario 2**: Tim Anda menemukan lonjakan alokasi memori GC Gen 2 secara masif setelah menambahkan telemetry tracing berbasis `CancellationTokenSource.CreateLinkedTokenSource(masterToken)`. Padahal masterToken dibuat sebagai singleton aplikasi. Di mana letak kebocoran memori (leak) dan bagaimana solusinya?
13. **Skenario 3**: Sebuah bank digital mengimplementasikan validasi saldo rekening menggunakan `lock (accountObject)` di dalam method yang menjalankan operasi transfer database:
    ```csharp
    lock (_accountLock)
    {
        await _db.DebitAsync(accountId, amount);
    }
    ```
    Compiler C# menolak kode ini dengan error CS1996. Jelaskan secara mendalam alasan arsitektural CLR melarang penggunaan `lock` melintasi blok `await`, dan tuliskan solusi sinkronisasi yang tepat!

---

#### Kunci Jawaban Quiz

##### Jawaban Basic
1. Mengatur jumlah worker thread secara adaptif dengan mengevaluasi rasio throughput penyelesaian tugas terhadap biaya context-switching CPU setiap interval ~500ms.
2. Karena exception yang terjadi di dalam `async void` tidak dapat ditangkap oleh blok pemanggil (tidak mengembalikan `Task`) dan langsung memicu fatal application crash via AppDomain unhandled exception.
3. *Global Queue* menggunakan locking mechanism berprinsip FIFO untuk semua thread. *Local Queue* dimiliki khusus oleh satu worker thread, memproses item secara LIFO tanpa locking langsung dari thread pemiliknya.
4. Memicu risiko thread pool starvation: thread pekerja ditangguhkan (blocking), sehingga kapasitas eksekusi thread pool habis sebelum callback penyelesaian I/O sempat dieksekusi.
5. Untuk menginstruksikan runtime agar tidak perlu mengalirkan context penjadwalan (`SynchronizationContext`) saat melanjutkan eksekusi setelah `await`, mengurangi overhead peralihan context dan mencegah potensi deadlock.

##### Jawaban Intermediate
6. Jika tugas belum selesai saat `await` pertama dieksekusi (`awaiter.IsCompleted == false`), stack frame method akan diakhiri. Agar state lokal tidak hilang, compiler mengalokasikan struct state machine ke dalam heap memory sehingga reference-nya dapat dipegang oleh callback delegate hingga I/O rampung.
7. Thread pemilik memproses tugasnya sendiri dari ujung atas antrean (*top*) secara LIFO. Thread pencuri (*thief*) mengambil tugas dari ujung bawah (*bottom*) antrean secara FIFO menggunakan instruksi atomik `Interlocked.CompareExchange`, sehingga meminimalkan tabrakan akses antar-thread.
8. Karena `ValueTask<T>` dapat dibungkus oleh objek `IValueTaskSource` yang dapat di-reuse/di-pool. Meng-await lebih dari satu kali dapat merusak siklus hidup pooling internal, mengakibatkan kondisi race condition atau undefined behavior.
9. `ExecutionContext` mengalirkan context logis ambient (seperti security identity, culture, dan `AsyncLocal`), sedangkan `SynchronizationContext` mengarahkan ke thread mana atau scheduler mana callback kelanjutan harus dieksekusi.
10. `ConcurrentQueue<T>` tidak memiliki batas ukuran alami (unbounded) sehingga produsen yang terlalu cepat dapat menghabiskan memori server. `Channels` memiliki konfigurasi batas (`BoundedChannelOptions`) yang memaksa produsen menunggu secara asinkron (*backpressure*) bila antrean penuh.

##### Jawaban Skenario Kasus Produksi
11. **Analisis**: Terjadi *Thread Pool Starvation* akibat blocking call (`.Result` / `.Wait()`). CLR Hill Climbing mendeteksi CPU rendah, namun karena thread terblokir secara sleep/wait, penambahan thread dibatasi secara perlahan (~1 thread per detik). **Solusi**: Audit dan hilangkan pemanggilan sinkron terhadap method asinkron, serta setel sementara `ThreadPool.SetMinThreads()` ke angka yang lebih tinggi untuk menangani burst load sambil menuntaskan refactoring asinkron murni.
12. **Analisis**: `masterToken` menyimpan referensi callback event listener ke setiap child CTS yang dibuat melalui `CreateLinkedTokenSource`. Karena masterToken berumur singleton, referensi ke child CTS tertahan selamanya di heap, memicu akumulasi memory leak Gen 2. **Solusi**: Bungkus pemakaian linked token source dalam statement `using var linkedCts = ...` agar callback unregistration langsung dieksekusi saat scope selesai.
13. **Analisis**: `Monitor` (pondasi keyword `lock`) menuntut thread yang melepaskan kunci (`Exit`) harus merupakan thread yang sama yang mengakuisisi kunci (`Enter`) berbasis thread-affinity OS. Pada pola `await`, kelanjutan method dapat dieksekusi pada thread pool worker yang berbeda, sehingga melepaskan lock pada thread yang berbeda akan memicu kerusakan integritas monitor (`SynchronizationLockException`). **Solusi**: Gunakan primitif sinkronisasi berbasis asinkron murni seperti `SemaphoreSlim(1, 1)`:
    ```csharp
    await _semaphore.WaitAsync();
    try
    {
        await _db.DebitAsync(accountId, amount);
    }
    finally
    {
        _semaphore.Release();
    }
    ```

---

### 16. Summary

* **Arsitektur CLR ThreadPool** mengandalkan modularitas antrean: antrean Global (FIFO) dan antrean Lokal per thread pekerja (LIFO) dengan algoritma *Work-Stealing* untuk memaksimalkan afinitas CPU cache dan meminimalkan alokasi resource.
* **Compiler Roslyn** mentransformasi method `async` menjadi struct `IAsyncStateMachine`. Pemahaman terhadap alokasi boxing pada heap mendorong pemanfaatan arsitektur `ValueTask<T>` untuk rute komputasi instan (*hot-path*).
* **Eksekusi Asinkron Skala Enterprise** membutuhkan pemisahan yang jelas antara CPU-bound computation dan I/O Completion Ports (IOCP). Penggunaan `.Result` dan `.Wait()` mengacaukan heuristik algoritma *Hill Climbing* dan merupakan penyebab utama kelumpuhan sistem melalui *ThreadPool Starvation*.
* **Pola Aliran Data Berkecepatan Tinggi** menuntut kontrol kapasitas. Memanfaatkan `System.Threading.Channels` menyediakan mekanisme *bounded backpressure* yang melindungi stabilitas memori aplikasi di bawah beban kerja transaksi masif.