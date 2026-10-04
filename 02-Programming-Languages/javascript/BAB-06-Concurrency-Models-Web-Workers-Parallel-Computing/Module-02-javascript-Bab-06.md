# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 06: Concurrency Models, Web Workers & Parallel Computing**  
**Kategori: 02-Programming-Languages / JavaScript**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengonfigurasi dan memvalidasi konteks isolasi peramban (*Cross-Origin Opener Policy* / COOP dan *Cross-Origin Embedder Policy* / COEP) untuk membuka kapabilitas memori bersama tingkat lanjut.
- Membedah dan mengelola *lifecycle* isolat V8 pada arsitektur multi-thread, memahami implikasi konsumsi memori per thread, serta mekanisme alokasi heap independen.
- Mengimplementasikan komunikasi bebas salin (*zero-copy memory transfer*) menggunakan antarmuka `Transferable` dan memanipulasi memori bersama (*shared memory*) melalui `SharedArrayBuffer`.
- Membangun primitif sinkronisasi tingkat rendah (*Spinlock*, *Mutex*, dan *Condition Variable*) menggunakan operasi atomik `Atomics` (`wait`, `notify`, `compareExchange`).
- Mengembangkan arsitektur *Production-Grade Thread Pool* dengan strategi antrean tugas (*task scheduling*) dan penyeimbangan beban kerja (*work-stealing/load balancing*).
- Merancang sistem rendering *off-main-thread* menggunakan `OffscreenCanvas` guna mengeliminasi *frame drop* dan *jank* pada antarmuka pengguna berbasis 60/120 FPS.
- Mendiagnosis serta memitigasi *deadlocks*, *race conditions*, *false sharing*, dan *memory leaks* pada lingkungan konkurensi JavaScript tingkat enterprise.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **JavaScript Engine Fundamentals**: Eksekusi single-threaded, call stack, V8 memory heap, serta siklus hidup *Event Loop* (Microtask vs Macrotask).
- **Binary Data Manipulation**: Pemahaman mendalam mengenai `ArrayBuffer`, `TypedArray` (`Uint8Array`, `Int32Array`, `Float64Array`), dan `DataView`.
- **Dasar Web Workers**: Inisialisasi thread pekerja, antarmuka `postMessage`, dan penanganan *event* pesan dasar.
- **Sistem Jaringan & Header HTTP**: Pemahaman fungsi header respons HTTP dalam menegakkan kebijakan keamanan browser modern.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 V8 Isolate Architecture & Threading Model

JavaScript secara historis dirancang sebagai bahasa *single-threaded*, namun mesin eksekusi modern seperti Google V8 menangani konkurensi melalui abstraksi **Isolate**.

```
+-----------------------------------------------------------------------------------+
| Browser Process / Main Application Runtime                                        |
|                                                                                   |
|  +-----------------------------------+    +------------------------------------+  |
|  | Main Thread (Isolate 0)           |    | Worker Thread (Isolate 1)          |  |
|  |  +-----------------------------+  |    |  +------------------------------+  |  |
|  |  | V8 Heap (Isolated)          |  |    |  | V8 Heap (Isolated)           |  |  |
|  |  |  - DOM Nodes                |  |    |  |  - Pure Objects              |  |  |
|  |  |  - JS Objects & Context     |  |    |  |  - Worker Context            |  |  |
|  |  +-----------------------------+  |    |  +------------------------------+  |  |
|  |  +-----------------------------+  |    |  +------------------------------+  |  |
|  |  | Libuv/Event Loop            |  |    |  | Dedicated Event Loop         |  |  |
|  |  |  - UI Events, Microtasks    |  |    |  |  - Task Queue, Microtasks    |  |  |
|  |  +-----------------------------+  |    |  +------------------------------+  |  |
|  +-----------------\-----------------+    +------------------/-----------------+  |
|                     \                                       /                     |
|                      \   SharedArrayBuffer Backing Store   /                      |
|                       \  +-------------------------------+ /                       |
|                        +-> Shared Virtual Address Space <-+                       |
|                          | Raw Physical Memory Pages     |                        |
|                          +-------------------------------+                        |
|                                          ^                                        |
|                                          | Inter-thread Sync                      |
|                             [ Atomics: Futex Architecture ]                       |
+-----------------------------------------------------------------------------------+
```

Setiap kali instance `Worker` dibuat, runtime menginstansiasi sebuah **V8 Isolate** baru yang berjalan pada thread OS (*POSIX pthread* atau *Windows Thread*) terpisah:
- **Isolasi Mutlak**: Setiap Isolate memiliki Garbage Collector (GC), heap space, runtime stack, dan call stack independen. Main thread tidak dapat menyentuh objek JavaScript reguler yang dialokasikan di dalam Worker heap.
- **Footprint Baseline**: Setiap Isolate mengonsumsi memori dasar sekitar 5 MB hingga 30 MB (bergantung pada arsitektur OS dan flag kompilasi JIT).
- **Ketiadaan UI/DOM Access**: Worker Isolate beroperasi dalam konteks global `DedicatedWorkerGlobalScope`, tanpa akses ke objek `window`, `document`, atau subsistem rendering langsung.

### 3.2 Structured Clone Algorithm vs. Transferable Objects

Komunikasi antar-thread di JavaScript umumnya menggunakan dua paradigma transmisi data:

1. **Structured Clone Algorithm**:
   - Proses serialisasi internal rekursif di mana struktur objek sumber dipetakan, dialokasikan ulang, dan disalin ke memori Isolate target.
   - Kompleksitas waktu: $\mathcal{O}(N)$ terhadap total ukuran data.
   - Dampak performa: Untuk payload berukuran ratusan megabita, proses serialisasi/deserialisasi dapat memblokir Event Loop pada kedua thread (pengirim dan penerima), menyebabkan latensi tinggi (*IPC serialization tax*).

2. **Transferable Objects (`ArrayBuffer`, `MessagePort`, `ImageBitmap`, `OffscreenCanvas`)**:
   - Beroperasi melalui manipulasi pointer di tingkat C++ runtime.
   - Ketika `ArrayBuffer` ditransfer:
     1. Backing memory store (pointer memori mentah di luar JS Heap) dilepaskan dari konteks Isolate sumber.
     2. Ukuran byte sumber diubah (*neutered*) menjadi nol (`byteLength: 0`).
     3. Pointer virtual address space tersebut langsung diserahkan ke Isolate target.
   - Kompleksitas waktu: $\mathcal{O}(1)$ (*zero-copy allocation*).

### 3.3 SharedArrayBuffer, Futex & Operasi Atomics

`SharedArrayBuffer` (SAB) mengizinkan dua atau lebih V8 Isolate untuk memetakan *virtual address space* internal mereka ke blok memori fisik yang sama secara bersamaan. Paradigma ini memperkenalkan tantangan *concurrency* klasik: *race conditions* dan *memory tearing*.

Untuk menjamin konsistensi memori dan sinkronisasi lintas thread, ECMAScript menyediakan namespace **`Atomics`**:

- **Memory Ordering & Barriers**: Di tingkat mikroarsitektur CPU (seperti x86-64 dengan *Total Store Order* atau ARM64 dengan *Weak Memory Model*), CPU dan compiler dapat mereorder instruksi pembacaan/penulisan memori. Operasi `Atomics` bertindak sebagai *full memory fence* (penghalang memori), memastikan instruksi sebelum operasi atomik diselesaikan sepenuhnya sebelum instruksi setelahnya dieksekusi.
- **Compare-And-Swap (CAS)**: `Atomics.compareExchange(typedArray, index, expectedValue, replacementValue)` mengeksekusi instruksi CAS di tingkat assembly CPU (misalnya `lock cmpxchg` pada x86-64). Jika nilai pada indeks sama dengan `expectedValue`, nilai diubah menjadi `replacementValue` secara atomik tanpa interferensi thread lain.
- **Futex (Fast Userspace Mutex)**:
  - `Atomics.wait(typedArray, index, value, timeout)`: Thread akan menangguhkan eksekusi (*sleep*) dan mendaftarkan diri pada *wait queue* internal mesin virtual jika nilai pada `index` sama dengan `value`. **Penting:** Operasi ini bersifat *synchronous blocking* dan dilarang keras di main thread browser untuk mencegah pembekuan UI (*freezing*), namun diizinkan di Worker threads.
  - `Atomics.notify(typedArray, index, count)`: Membangunkan sebanyak `count` thread yang sedang tertidur pada antrean futex untuk indeks memori tersebut.

### 3.4 Cross-Origin Isolation (COOP & COEP)

Akibat kerentanan keamanan berbasis mikroarsitektur CPU (*Spectre* dan *Meltdown*), `SharedArrayBuffer` dinonaktifkan secara *default* di browser modern. Penyerang dapat menggunakan pewaktu beresolusi tinggi (*high-precision timers*) bersama memori bersama untuk melancarkan serangan *cache-timing side-channel*.

Untuk mengaktifkan kembali `SharedArrayBuffer`, server web wajib merespons dokumen HTML utama dengan sepasang header keamanan HTTP:

```http
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

- **COOP (`same-origin`)**: Membatasi dokumen hanya dapat berbagi browsing context group dengan dokumen dari origin yang sama. Window referensi silang (`window.opener`) dibersihkan.
- **COEP (`require-corp`)**: Mengharuskan seluruh resource eksternal (skrip, gambar, stylesheet, iframe) yang dimuat secara eksplisit menyatakan izin melalui header CORS atau `Cross-Origin-Resource-Policy: cross-origin`.

Status ketersediaan lingkungan ini dapat diverifikasi secara terprogram via properti `self.crossOriginIsolated` (mengembalikan nilai `true`).

---

## 4. Why & What

| Dimensi | Single-Threaded Asynchronous (Event Loop Standar) | Multi-Threaded Parallelism (Workers + Shared Memory) |
| :--- | :--- | :--- |
| **Karakteristik Komputasi** | I/O-Bound (HTTP requests, database reads, file access). | CPU-Bound (Machine Learning inference, kompresi video, kriptografi, fisika simulasi). |
| **Pemanfaatan Core CPU** | Terbatas pada 1 CPU Core. Sisanya berada pada status *idle*. | Penuh ($N$ CPU Cores dimanfaatkan secara proporsional sesuai kebutuhan). |
| **Respon UI Main Thread** | Rentan terhadap *blocking* jika microtask/loop berjalan $>16.6\text{ ms}$. | Main thread murni merender antarmuka tanpa degradasi FPS. |
| **Model Sinkronisasi** | Implisit; tidak ada masalah *race condition* pada memori mentah. | Eksplisit; memerlukan primitif konkurensi (`Mutex`, `Atomics`). |
| **Overhead Memori** | Minimal; satu heap address space. | Lebih tinggi; alokasi Isolate runtime terpisah per thread pekerja. |

---

## 5. How (Workflow Detail)

Alur kerja arsitektur sistem paralel enterprise mengadopsi pola koordinasi berbasis status:

```
[Inisialisasi Master/Main Thread]
   │
   ├─► Verifikasi `self.crossOriginIsolated` === true
   │
   ├─► Alokasi `SharedArrayBuffer` (Control Block + Data Buffer)
   │
   ├─► Spawn $N$ Worker Threads (sesuai `navigator.hardwareConcurrency`)
   │
   ├─► Distribusi SAB ke seluruh Worker via `postMessage` (Reference Sharing)
   │
   └─► Siapkan Loop Sinkronisasi (Atomics CAS / Futex Wait-Notify)
         │
[Siklus Kerja Worker Thread]
   │
   ├─► Menerima referensi SAB & instansiasi TypedArray view
   │
   ├─► Masuk ke *idle loop*: `Atomics.wait(ControlArray, TASK_SIGNAL_INDEX, 0)`
   │     ▲
   │     │ (Tertidur di kernel wait-queue tanpa konsumsi siklus CPU)
   │     │
   │     ├─► Main Thread menulis data & memicu `Atomics.notify(ControlArray, TASK_SIGNAL_INDEX, 1)`
   │     │
   │     ├─► Worker terbangun, membaca data, dan mengeksekusi komputasi paralel
   │     │
   │     └─► Worker menulis hasil kembali ke SAB, mengubah flag, lalu kembali tidur
```

---

## 6. Analogy & Diagram ASCII

### Analogi Restoran Cepat Saji Enterprise

- **Single-Threaded**: Satu koki mengerjakan semuanya. Saat ia memotong daging (komputasi intensif), pesanan pelanggan di kasir tidak dapat dilayani, menyebabkan antrean mengular (UI *frozen*).
- **Web Worker Standar (Message Passing)**: Koki utama menyuruh asisten koki di dapur belakang untuk memotong daging. Setelah selesai, asisten harus membungkus seluruh daging dalam wadah, menempelkan label, dan mengantarkannya melalui lorong sempit (Structured Clone / IPC). Biaya pengantaran sangat tinggi jika dagingnya berbobot ratusan kilogram.
- **SharedArrayBuffer & Atomics**: Koki utama dan seluruh asisten koki berdiri mengelilingi satu meja pemotongan besar yang sama (*shared memory*). Semua dapat memotong dan mengambil daging di meja secara langsung tanpa kurir. Namun, agar pisau mereka tidak saling beradu (*race condition*), mereka menggunakan papan tanda nomor berputar (*Atomics CAS*) untuk menentukan siapa yang berhak memotong bagian tertentu pada satu waktu.

### Diagram Alur Akses Memori Lintas Isolate

```
+---------------------------------------------------------------------------------+
| V8 Runtime Process Space                                                        |
|                                                                                 |
| Main Thread                                          Worker Thread Pool         |
| +-------------------------+                          +------------------------+ |
| | Task Queue Dispatcher   |                          | Worker Isolate #1      | |
| |                         |                          | - State: PROCESSING    | |
| |   [Mutator Logic]       |                          | - Thread-ID: tid_102   | |
| +------------+------------+                          +-----------+------------+ |
|              |                                                   |              |
|              | write task data                                   | read & write |
|              v                                                   v              |
| +-----------------------------------------------------------------------------+ |
| | SharedArrayBuffer (Raw Memory Array)                                        | |
| | +---------------------+-----------------------+---------------------------+ | |
| | | Header / Mutex Area | Ring Buffer Indexes   | Payloads Segment          | | |
| | | Offset 0x00 - 0x1F  | Offset 0x20 - 0x3F    | Offset 0x40 - 0xFFFFFF    | | |
| | +---------------------+-----------------------+---------------------------+ | |
| +-----------------------------------------------------------------------------+ |
|              ^                                                   ^              |
|              | atomic sync notify                                | futex wait   |
| +------------+------------+                          +-----------+------------+ |
| | Lock Control            |                          | Worker Isolate #2      | |
| | Atomics.notify()        |<========================>| Atomics.wait()         | |
| +-------------------------+                          +------------------------+ |
+---------------------------------------------------------------------------------+
```

---

## 7. Implementasi Kode

### 7.1 Simple Example: Mutex Berbasis Atomics

Implementasi primitif penguncian biner (*binary mutex*) thread-safe menggunakan `SharedArrayBuffer` dan `Atomics`.

#### `mutex.js`
```javascript
/**
 * Implementasi Mutual Exclusion (Mutex) tingkat rendah untuk koordinasi lintas Worker.
 * Menggunakan memori Int32Array 1 elemen:
 * Index 0: Status Kunci (0 = UNLOCKED, 1 = LOCKED)
 */
export class LowLevelMutex {
  static UNLOCKED = 0;
  static LOCKED = 1;

  /**
   * @param {SharedArrayBuffer} sharedBuffer - Buffer berukuran minimal 4 byte.
   * @param {number} byteOffset - Lokasi offset integer (harus kelipatan 4).
   */
  constructor(sharedBuffer, byteOffset = 0) {
    if (!(sharedBuffer instanceof SharedArrayBuffer)) {
      throw new TypeError("Parameter 'sharedBuffer' harus bertipe SharedArrayBuffer");
    }
    this.buffer = sharedBuffer;
    this.byteOffset = byteOffset;
    // Gunakan TypedArray Int32 karena Atomics.wait/notify mewajibkan Int32Array.
    this.lockState = new Int32Array(this.buffer, this.byteOffset, 1);
  }

  /**
   * Mengakuisisi kunci. Memblokir thread pekerja jika kunci sedang dipakai.
   * PENTING: DILARANG dipanggil dari Main Thread!
   */
  lock() {
    while (true) {
      // Coba ubah nilai dari UNLOCKED (0) menjadi LOCKED (1) secara atomik
      const priorValue = Atomics.compareExchange(
        this.lockState,
        0,
        LowLevelMutex.UNLOCKED,
        LowLevelMutex.LOCKED
      );

      if (priorValue === LowLevelMutex.UNLOCKED) {
        // Berhasil mendapatkan kunci
        return;
      }

      // Jika gagal, tangguhkan thread ini sampai kunci dilepaskan.
      // 1 adalah nilai yang diekspektasi saat thread tertidur (artinya masih terkunci).
      Atomics.wait(this.lockState, 0, LowLevelMutex.LOCKED);
    }
  }

  /**
   * Melepaskan kunci dan membangunkan salah satu thread yang tertidur.
   */
  unlock() {
    const priorValue = Atomics.compareExchange(
      this.lockState,
      0,
      LowLevelMutex.LOCKED,
      LowLevelMutex.UNLOCKED
    );

    if (priorValue !== LowLevelMutex.LOCKED) {
      throw new Error("IllegalMutexState: Mencoba melepaskan kunci yang tidak dikunci!");
    }

    // Bangunkan 1 worker yang sedang tertidur di wait-queue
    Atomics.notify(this.lockState, 0, 1);
  }
}
```

---

### 7.2 Practical Example: Enterprise Production Worker Pool dengan Shared Circular Task Queue

Arsitektur thread pool multi-core penuh dengan penugasan *lock-free single-producer multi-consumer* (SPMC) berbasis `SharedArrayBuffer` dan `Atomics`.

#### `constants.js`
```javascript
export const QUEUE_CAPACITY = 1024;
// Ukuran per item task dalam byte: 
// [TaskID (4 bytes), DataPayload (4 bytes), ResultPayload (4 bytes)]
export const ITEM_SIZE_INT32 = 3; 

// Struktur Header Kontrol Antrean (Int32Array):
// Index 0: Head Pointer
// Index 1: Tail Pointer
// Index 2: Shutdown Signal (0 = RUNNING, 1 = TERMINATED)
export const HEADER_SIZE_INT32 = 4;
export const HEAD_INDEX = 0;
export const TAIL_INDEX = 1;
export const SHUTDOWN_INDEX = 2;
```

#### `worker-pool.js` (Main Thread)
```javascript
import {
  QUEUE_CAPACITY,
  ITEM_SIZE_INT32,
  HEADER_SIZE_INT32,
  HEAD_INDEX,
  TAIL_INDEX,
  SHUTDOWN_INDEX,
} from "./constants.js";

export class ProductionWorkerPool {
  /**
   * @param {string} workerScriptPath 
   * @param {number} poolSize 
   */
  constructor(workerScriptPath, poolSize = navigator.hardwareConcurrency || 4) {
    if (!self.crossOriginIsolated) {
      throw new Error(
        "Lingkungan belum terisolasi. Pastikan header COOP dan COEP aktif di server."
      );
    }

    this.poolSize = poolSize;
    this.workerScriptPath = workerScriptPath;
    this.workers = [];
    this.pendingTasks = new Map();
    this.nextTaskId = 1;

    // Alokasi SharedArrayBuffer: Header + (Queue Capacity * Item Size) * 4 bytes
    const totalInt32Elements = HEADER_SIZE_INT32 + QUEUE_CAPACITY * ITEM_SIZE_INT32;
    this.sharedBuffer = new SharedArrayBuffer(totalInt32Elements * Int32Array.BYTES_PER_ELEMENT);
    
    this.controlQueue = new Int32Array(this.sharedBuffer);
    Atomics.store(this.controlQueue, HEAD_INDEX, 0);
    Atomics.store(this.controlQueue, TAIL_INDEX, 0);
    Atomics.store(this.controlQueue, SHUTDOWN_INDEX, 0);

    this._initializeWorkers();
  }

  _initializeWorkers() {
    for (let i = 0; i < this.poolSize; i++) {
      const worker = new Worker(this.workerScriptPath, { type: "module" });

      worker.onmessage = (event) => {
        const { taskId, result, error } = event.data;
        const taskDeferred = this.pendingTasks.get(taskId);
        if (taskDeferred) {
          this.pendingTasks.delete(taskId);
          if (error) {
            taskDeferred.reject(new Error(error));
          } else {
            taskDeferred.resolve(result);
          }
        }
      };

      worker.onerror = (err) => {
        console.error(`Uncaught exception pada Worker-${i}:`, err);
      };

      // Kirim Shared Memory Buffer ke setiap worker
      worker.postMessage({
        type: "INIT_SHARED_BUFFER",
        buffer: this.sharedBuffer,
        workerId: i,
      });

      this.workers.push(worker);
    }
  }

  /**
   * Menyerahkan pekerjaan kalkulasi ke antrean thread pool.
   * @param {number} numericData
   * @returns {Promise<number>}
   */
  dispatch(numericData) {
    return new Promise((resolve, reject) => {
      const tail = Atomics.load(this.controlQueue, TAIL_INDEX);
      const head = Atomics.load(this.controlQueue, HEAD_INDEX);

      // Hitung kapasitas terisi
      if (tail - head >= QUEUE_CAPACITY) {
        return reject(new Error("Queue Overflow: Antrean tugas di memori penuh"));
      }

      const taskId = this.nextTaskId++;
      this.pendingTasks.set(taskId, { resolve, reject });

      // Hitung posisi ring buffer
      const slotIndex = HEADER_SIZE_INT32 + (tail % QUEUE_CAPACITY) * ITEM_SIZE_INT32;

      // Masukkan payload secara serial/atomik ke slot buffer
      Atomics.store(this.controlQueue, slotIndex, taskId);
      Atomics.store(this.controlQueue, slotIndex + 1, numericData);
      Atomics.store(this.controlQueue, slotIndex + 2, 0); // Result placeholder

      // Majukan pointer Tail secara atomik
      Atomics.add(this.controlQueue, TAIL_INDEX, 1);

      // Bangunkan salah satu Worker yang tertidur di antrean futex
      Atomics.notify(this.controlQueue, TAIL_INDEX, 1);
    });
  }

  async destroy() {
    // Beri sinyal shutdown
    Atomics.store(this.controlQueue, SHUTDOWN_INDEX, 1);
    // Bangunkan semua worker agar membaca sinyal shutdown dan menghentikan diri
    Atomics.notify(this.controlQueue, TAIL_INDEX, this.poolSize);

    await Promise.all(
      this.workers.map((w) => {
        w.terminate();
      })
    );
    this.workers = [];
    this.pendingTasks.clear();
  }
}
```

#### `worker-thread.js` (Worker Implementation)
```javascript
import {
  QUEUE_CAPACITY,
  ITEM_SIZE_INT32,
  HEADER_SIZE_INT32,
  HEAD_INDEX,
  TAIL_INDEX,
  SHUTDOWN_INDEX,
} from "./constants.js";

let controlQueue = null;
let isRunning = false;
let workerId = -1;

self.onmessage = (event) => {
  const { type, buffer, workerId: id } = event.data;
  if (type === "INIT_SHARED_BUFFER") {
    controlQueue = new Int32Array(buffer);
    workerId = id;
    isRunning = true;
    startTaskProcessingLoop();
  }
};

/**
 * Simulasi komputasi intensif CPU: Menghitung faktorial bilangan prima/hashing
 */
function heavyCompute(val) {
  let acc = 0;
  for (let i = 0; i < 5_000_000; i++) {
    acc = (acc + Math.imul(val, i)) ^ (i & 0xff);
  }
  return acc;
}

function startTaskProcessingLoop() {
  while (isRunning) {
    // 1. Cek apakah ada instruksi shutdown
    if (Atomics.load(controlQueue, SHUTDOWN_INDEX) === 1) {
      isRunning = false;
      break;
    }

    // 2. Baca head dan tail
    const currentHead = Atomics.load(controlQueue, HEAD_INDEX);
    const currentTail = Atomics.load(controlQueue, TAIL_INDEX);

    if (currentHead >= currentTail) {
      // Antrean kosong, tunggu main thread memajukan TAIL_INDEX
      // Thread ini masuk ke kernel sleep (0% CPU cycle)
      Atomics.wait(controlQueue, TAIL_INDEX, currentTail);
      continue;
    }

    // 3. Rebut slot tugas dengan CAS pada HEAD_INDEX (Atomic Reservation)
    const claimedHead = Atomics.compareExchange(
      controlQueue,
      HEAD_INDEX,
      currentHead,
      currentHead + 1
    );

    // Jika gagal mengklaim karena terahului worker lain, coba lagi pada loop berikutnya
    if (claimedHead !== currentHead) {
      continue;
    }

    // 4. Berhasil klaim slot: Ambil data
    const slotIndex = HEADER_SIZE_INT32 + (currentHead % QUEUE_CAPACITY) * ITEM_SIZE_INT32;
    const taskId = Atomics.load(controlQueue, slotIndex);
    const rawInput = Atomics.load(controlQueue, slotIndex + 1);

    try {
      // 5. Eksekusi kalkulasi murni
      const computationResult = heavyCompute(rawInput);

      // Kembalikan hasil via postMessage ringkas ke callback dispatcher
      self.postMessage({
        taskId,
        result: computationResult,
        workerId,
      });
    } catch (err) {
      self.postMessage({
        taskId,
        error: err.message,
        workerId,
      });
    }
  }
}
```

---

## 8. Real World Case Study: Financial High-Frequency Analytics & Visualizer

### Skenario Masalah
Sebuah platform broker valuta asing (Forex) enterprise menerima *tick data* transaksi pasar keuangan via WebSocket sebanyak **100.000 events/detik**. Platform dituntut untuk:
1. Menghitung indikator teknikal agregasi (*Exponential Moving Average* (EMA), Bollinger Bands, dan Volatilitas Stokastik) secara *real-time*.
2. Merender chart interaktif pada kanvas 120 FPS tanpa menyebabkan *jank* (durasi pemrosesan frame main thread harus $< 8\text{ ms}$).

Jika diproses di main thread, antarmuka langsung macet total (*unresponsive*), *garbage collection* memicu *hiccup* terus-menerus, dan WebSocket buffer mengalami *backpressure failure*.

### Solusi Arsitektur
Pemisahan domain eksekusi menjadi tiga pilar menggunakan `SharedArrayBuffer` dan `OffscreenCanvas`:

```
+-------------------------------------------------------------------------+
|                                MAIN THREAD                              |
|                                                                         |
|  WebSocket Stream ────► Ring Buffer SAB ────► UI Controls               |
|  (Inbound Ticks)        (No Deserialization)  (Input & Interaction)     |
+------------------------------------+------------------------------------+
                                     │
                    Shared Memory Backing Buffer
                                     │
           +-------------------------+-------------------------+
           │                                                   │
           v                                                   v
+-----------------------+                           +---------------------+
| WORKER 1: CALCULATION |                           | WORKER 2: RENDERER  |
|                       |                           |                     |
| - Pulls tick stream   |                           | - Pulls indicators  |
| - Computes Indicators |                           | - OffscreenCanvas   |
| - Writes to Chart SAB |                           | - WebGL Context     |
| - Uses Atomics Lock   |                           | - Direct Rendering  |
+-----------------------+                           +---------------------+
```

### Implementasi Kasus

#### `main-pipeline.js`
```javascript
export class FinancialEngine {
  constructor(canvasElement) {
    if (!self.crossOriginIsolated) {
      throw new Error("COOP/COEP Headers wajib aktif!");
    }

    this.canvas = canvasElement;
    // Pindahkan kepemilikan kontrol rendering canvas dari DOM ke Worker
    this.offscreenCanvas = this.canvas.transferControlToOffscreen();

    // 1 MB Shared Buffer untuk streaming data transaksi harga mentah (Float64)
    this.tickBuffer = new SharedArrayBuffer(1024 * 1024 * Float64Array.BYTES_PER_ELEMENT);
    this.tickArray = new Float64Array(this.tickBuffer);

    // Header Indeks Ticks:
    // Index 0: Ticks Written Head Pointer
    this.headerBuffer = new SharedArrayBuffer(4 * Int32Array.BYTES_PER_ELEMENT);
    this.headerArray = new Int32Array(this.headerBuffer);

    this.calcWorker = new Worker(new URL("./calc-worker.js", import.meta.url), {
      type: "module",
    });

    this.renderWorker = new Worker(new URL("./render-worker.js", import.meta.url), {
      type: "module",
    });

    this._bootstrap();
  }

  _bootstrap() {
    // Inisialisasi worker kalkulasi
    this.calcWorker.postMessage({
      type: "INIT",
      tickBuffer: this.tickBuffer,
      headerBuffer: this.headerBuffer,
    });

    // Inisialisasi worker render WebGL dengan canvas yang ditransfer secara zero-copy
    this.renderWorker.postMessage(
      {
        type: "INIT_CANVAS",
        canvas: this.offscreenCanvas,
        headerBuffer: this.headerBuffer,
        tickBuffer: this.tickBuffer,
      },
      [this.offscreenCanvas] // Transferred ownership
    );
  }

  /**
   * Dipanggil langsung oleh event handler onmessage dari WebSocket
   * Latensi sub-mikrodetik tanpa pemblokiran DOM
   */
  ingestTick(price, volume, timestamp) {
    const currentHead = Atomics.load(this.headerArray, 0);
    const capacity = (this.tickArray.length - 1) / 3;
    const writeSlot = (currentHead % capacity) * 3;

    // Tulis tuple data ke buffer
    this.tickArray[writeSlot] = price;
    this.tickArray[writeSlot + 1] = volume;
    this.tickArray[writeSlot + 2] = timestamp;

    // Majukan pointer secara atomik
    Atomics.add(this.headerArray, 0, 1);
    // Beri tahu worker komputasi
    Atomics.notify(this.headerArray, 0, 1);
  }
}
```

#### `calc-worker.js`
```javascript
let headerArray = null;
let tickArray = null;
let lastProcessedIndex = 0;
let emaValue = 0;
const EMA_ALPHA = 0.05;

self.onmessage = (e) => {
  if (e.data.type === "INIT") {
    headerArray = new Int32Array(e.data.headerBuffer);
    tickArray = new Float64Array(e.data.tickBuffer);
    runAnalysisLoop();
  }
};

function runAnalysisLoop() {
  const capacity = (tickArray.length - 1) / 3;

  while (true) {
    const currentHead = Atomics.load(headerArray, 0);

    if (currentHead === lastProcessedIndex) {
      // Tunggu tick baru datang tanpa membebani thread
      Atomics.wait(headerArray, 0, currentHead);
      continue;
    }

    while (lastProcessedIndex < currentHead) {
      const readSlot = (lastProcessedIndex % capacity) * 3;
      const price = tickArray[readSlot];

      // Kalkulasi Realtime Exponential Moving Average
      if (emaValue === 0) {
        emaValue = price;
      } else {
        emaValue = price * EMA_ALPHA + emaValue * (1 - EMA_ALPHA);
      }

      lastProcessedIndex++;
    }
  }
}
```

#### `render-worker.js`
```javascript
let gl = null;
let headerArray = null;

self.onmessage = (e) => {
  if (e.data.type === "INIT_CANVAS") {
    const canvas = e.data.canvas;
    gl = canvas.getContext("2d"); // Gunakan 2D atau WebGL
    headerArray = new Int32Array(e.data.headerBuffer);
    requestAnimationFrame(renderLoop);
  }
};

function renderLoop() {
  const currentHead = Atomics.load(headerArray, 0);

  // Bersihkan dan render indikator pada canvas
  gl.clearRect(0, 0, gl.canvas.width, gl.canvas.height);
  gl.fillStyle = "#00ff66";
  gl.font = "14px monospace";
  gl.fillText(`Ticks Processed: ${currentHead}`, 20, 30);

  // Loop rendering berjalan mulus di thread terpisah tanpa terpengaruh beban main thread
  requestAnimationFrame(renderLoop);
}
```

---

## 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian & Batasan |
| :--- | :--- | :--- |
| **SharedArrayBuffer + Atomics** | - *Zero-latency IPC* (Akses langsung ke fisik RAM).<br>- Menghilangkan beban CPU untuk serialisasi.<br>- Optimal untuk data stream bervolume ekstrim. | - Kompleksitas tinggi (*race conditions*, *deadlocks*).<br>- Hanya mendukung *flat binary numbers* (bukan *complex JS objects*).<br>- Wajib konfigurasi header CORS khusus (COOP/COEP). |
| **Transferable Objects** | - Kompleksitas sinkronisasi rendah.<br>- *Zero-copy* memory moving.<br>- Sangat aman (*memory neutered*, tidak ada kondisi balapan). | - Model *one-way handoff*; sumber kehilangan akses data seketika.<br>- Alokasi ulang diperlukan jika transmisi bersifat bolak-balik berulang. |
| **Structured Clone (Standar)** | - Sangat mudah digunakan.<br>- Mendukung graph objek kompleks (Date, Map, Set, Array). | - *High latency serialization penalty* ($\mathcal{O}(N)$).<br>- Memicu GC *pressure* tinggi di kedua Isolate pengirim dan penerima. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Mengeksekusi `Atomics.wait` pada Main Thread
- **Gejala**: Aplikasi langsung melempar exception:  
  `TypeError: Atomics.wait cannot be called in this context`
- **Penyebab**: Spesifikasi ECMAScript melarang `Atomics.wait` di lingkungan yang memiliki antarmuka pengguna (Main Thread) agar *rendering pipeline* dan *user interaction loop* tidak terhenti secara permanen.
- **Solusi**: Hanya jalankan `Atomics.wait` di dalam konteks Web Worker. Untuk main thread, gunakan `Atomics.notify()` atau polling non-blocking via `requestAnimationFrame` / `setTimeout` jika benar-benar darurat.

### 2. Membaca Memori yang Mengalami "Tearing"
- **Gejala**: Angka atau status data terdistorsi secara acak saat diakses secara konkuren lintas thread.
- **Penyebab**: Mengakses elemen `Float64Array` atau array multi-byte tanpa pelindung atomik saat thread lain sedang menulis sebagian bit ke slot tersebut.
- **Solusi**: Bungkus operasi pembacaan dan penulisan blok data menggunakan `LowLevelMutex` atau sinkronkan dengan flag status bertipe `Int32Array` yang dioperasikan eksklusif via `Atomics.store` dan `Atomics.load`.

### 3. Masalah False Sharing pada Alokasi Cache L1/L2
- **Gejala**: Penurunan performa drastis ketika banyak thread mengakses indeks array yang berdekatan, meskipun indeks yang diakses berbeda.
- **Penyebab**: Dua variabel atomik berada pada satu *Cache Line* CPU yang sama (biasanya berukuran 64 byte). Ketika Thread A menulis ke Indeks 0, baris cache CPU Thread B yang membaca Indeks 1 teranulir (*cache invalidation*), memaksa CPU membaca ulang dari RAM.
- **Solusi**: Terapkan *memory padding*. Beri jarak antar-variabel atomik yang sering dimutasi minimal sebesar 64 byte (16 elemen pada `Int32Array`).

### 4. Memory Neutering Failure pada Transferable
- **Gejala**: Main thread melempar *runtime error* ketika mencoba membaca buffer setelah memanggil `postMessage(data, [data.buffer])`.
- **Penyebab**: Buffer telah dipindahkan secara fisik. Properti `.byteLength` berubah menjadi 0 secara permanen.
- **Solusi**: Jika main thread masih membutuhkan data tersebut di kemudian hari, salin sebagian menggunakan `.slice()` sebelum transfer, atau gunakan arsitektur `SharedArrayBuffer`.

---

## 11. Best Practices (Production Checklist)

- [ ] **Validasi Isolasi**: Selalu periksa `self.crossOriginIsolated === true` pada tahap bootstrapping inisialisasi aplikasi.
- [ ] **Alokasi Dimensi Pool**: Batasi jumlah worker tidak melebihi `navigator.hardwareConcurrency` untuk mencegah overhead *context-switching* pada tingkat OS.
- [ ] **Struktur Memori Berkelipatan (Alignment)**: Pastikan seluruh offset pointer pada `SharedArrayBuffer` dialokasikan dengan kelipatan byte tipe datanya (misal: kelipatan 4 byte untuk `Int32Array`, kelipatan 8 byte untuk `Float64Array`).
- [ ] **Pemberian Sinyal Terminasi Graceful**: Implementasikan flag shutdown atomik (`Atomics.store`) sehingga thread pekerja dapat menyelesaikan iterasi pemrosesan sebelum dipanggil `worker.terminate()`.
- [ ] **Pencegahan Kebocoran Memori (Memory Leaks)**: Selalu panggil `.terminate()` pada instance Worker yang sudah tidak digunakan, dan pastikan membuang referensi event listener (`onmessage = null`).
- [ ] **Manajemen Error Terisolasi**: Bungkus seluruh blok kode internal worker dalam `try...catch` dan salurkan error ke parent via pesan terstruktur agar tidak menghasilkan *silent failure*.
- [ ] **Minimalkan Alokasi Objek di Jalur Cepat (Hot-Path)**: Hindari pembentukan objek baru `{}` atau array `[]` di dalam loop komputasi worker untuk mencegah siklus *Garbage Collector pauses*.

---

## 12. Hands-on Practice

Buat dan jalankan infrastruktur pengujian performa pengolahan komputasi matriks paralel di direktori:  
`hands-on/m02/`

### File: `hands-on/m02/server.js`
Server Node.js native dengan inject header COOP/COEP wajib:

```javascript
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = 8080;

const MIME_TYPES = {
  ".html": "text/html",
  ".js": "text/javascript",
};

http
  .createServer((req, res) => {
    // Inject header wajib SharedArrayBuffer
    res.setHeader("Cross-Origin-Opener-Policy", "same-origin");
    res.setHeader("Cross-Origin-Embedder-Policy", "require-corp");

    const filePath = path.join(
      __dirname,
      req.url === "/" ? "index.html" : req.url
    );
    const ext = path.extname(filePath);

    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.writeHead(404);
        res.end("Not Found");
        return;
      }
      res.writeHead(200, { "Content-Type": MIME_TYPES[ext] || "text/plain" });
      res.end(data);
    });
  })
  .listen(PORT, () => {
    console.log(`Server aktif di http://localhost:${PORT}`);
    console.log("Konteks Cross-Origin Isolation: AKTIF");
  });
```

### File: `hands-on/m02/worker.js`
```javascript
self.onmessage = (e) => {
  const { sab, startIdx, endIdx, matrixSize } = e.data;
  const matrix = new Float64Array(sab);

  // Lakukan komputasi pemangkatan kuadrat matriks paralel pada rentang baris tertentu
  for (let row = startIdx; row < endIdx; row++) {
    for (let col = 0; col < matrixSize; col++) {
      const idx = row * matrixSize + col;
      // Operasi matematika berat
      matrix[idx] = Math.sqrt(Math.pow(matrix[idx], 2) * 1.0000001);
    }
  }

  self.postMessage({ status: "DONE", workerId: e.data.workerId });
};
```

### File: `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Benchmarking Parallel Shared Memory</title>
</head>
<body style="font-family: sans-serif; padding: 20px;">
  <h2>Benchmarking Paralel vs Serial pada SharedArrayBuffer</h2>
  <div id="status">Menginisialisasi...</div>
  <button id="btnRun" disabled>Jalankan Benchmark</button>
  <pre id="output" style="background: #222; color: #00ff66; padding: 15px; margin-top: 20px;"></pre>

  <script type="module">
    const output = document.getElementById("output");
    const status = document.getElementById("status");
    const btn = document.getElementById("btnRun");

    if (!self.crossOriginIsolated) {
      status.innerText = "GAGAL: Window belum terisolasi. Buka via server.js!";
      status.style.color = "red";
      throw new Error("Isolation failed");
    }

    status.innerText = "Konteks terisolasi aktif. SharedArrayBuffer siap digunakan.";
    btn.disabled = false;

    const MATRIX_SIZE = 2000; // 2000 x 2000 Matrix = 4.000.000 Elemen Float64 (~32 MB)
    const TOTAL_ELEMENTS = MATRIX_SIZE * MATRIX_SIZE;
    const NUM_WORKERS = navigator.hardwareConcurrency || 4;

    btn.onclick = async () => {
      btn.disabled = true;
      output.innerText = `Menjalankan benchmark dengan matriks ${MATRIX_SIZE}x${MATRIX_SIZE} (${(TOTAL_ELEMENTS * 8 / 1e6).toFixed(2)} MB)...\n`;

      // Alokasi memori bersama
      const sab = new SharedArrayBuffer(TOTAL_ELEMENTS * Float64Array.BYTES_PER_ELEMENT);
      const matrix = new Float64Array(sab);

      // Isi data awal
      for (let i = 0; i < TOTAL_ELEMENTS; i++) {
        matrix[i] = i * 0.5;
      }

      // --- EKSEKUSI PARALEL ---
      output.innerText += `\n[PARALEL] Memulai kalkulasi dengan ${NUM_WORKERS} Web Workers...\n`;
      const t0 = performance.now();

      const workers = [];
      const rowsPerWorker = Math.floor(MATRIX_SIZE / NUM_WORKERS);
      const promises = [];

      for (let w = 0; w < NUM_WORKERS; w++) {
        const worker = new Worker("./worker.js", { type: "module" });
        workers.push(worker);

        const startIdx = w * rowsPerWorker;
        const endIdx = (w === NUM_WORKERS - 1) ? MATRIX_SIZE : (w + 1) * rowsPerWorker;

        const p = new Promise(resolve => {
          worker.onmessage = () => resolve();
        });
        promises.push(p);

        worker.postMessage({
          sab,
          startIdx,
          endIdx,
          matrixSize: MATRIX_SIZE,
          workerId: w
        });
      }

      await Promise.all(promises);
      const parallelDuration = performance.now() - t0;
      output.innerText += `-> Paralel selesai dalam: ${parallelDuration.toFixed(2)} ms\n`;

      // Terminasi worker setelah selesai
      workers.forEach(w => w.terminate());

      // --- EKSEKUSI SERIAL PADA MAIN THREAD ---
      output.innerText += `\n[SERIAL] Memulai kalkulasi pada Main Thread...\n`;
      const t1 = performance.now();
      for (let row = 0; row < MATRIX_SIZE; row++) {
        for (let col = 0; col < MATRIX_SIZE; col++) {
          const idx = row * MATRIX_SIZE + col;
          matrix[idx] = Math.sqrt(Math.pow(matrix[idx], 2) * 1.0000001);
        }
      }
      const serialDuration = performance.now() - t1;
      output.innerText += `-> Serial selesai dalam: ${serialDuration.toFixed(2)} ms\n`;

      const speedup = (serialDuration / parallelDuration).toFixed(2);
      output.innerText += `\nSpeedup Factor: ${speedup}x lebih cepat!\n`;
      btn.disabled = false;
    };
  </script>
</body>
</html>
```

### Instruksi Menjalankan
1. Pastikan Node.js (v18+) terpasang.
2. Buka terminal di direktori proyek:
   ```bash
   cd hands-on/m02/
   node server.js
   ```
3. Akses peramban pada `http://localhost:8080`.
4. Buka Console DevTools dan klik tombol **Jalankan Benchmark**. Amati peningkatan throughput komputasi saat seluruh core CPU bekerja secara simultan tanpa *blocking* UI.

---

## 13. Exercises

### Level Easy
Modifikasi kelas `LowLevelMutex` pada sub-bab 7.1 untuk menambahkan fitur penghitung reentrant (Reentrant Lock).
- **Kriteria Penerimaan**: Kunci dapat diakuisisi beberapa kali oleh thread pemegang kunci yang sama tanpa mengalami *self-deadlock*. Jumlah panggilan `unlock()` harus setara dengan jumlah `lock()` sebelum kunci benar-benar terbuka untuk worker lain.

### Level Medium
Buat struktur data antrean *Thread-Safe Single-Producer Single-Consumer (SPSC) Ring Buffer* menggunakan `SharedArrayBuffer` dan typed array berukuran dinamis yang mendukung pengiriman teks UTF-8 mentah.
- **Kriteria Penerimaan**:
  - Main thread menulis string; worker membaca string tanpa data corrupt.
  - String di-encode ke biner via `TextEncoder` sebelum masuk buffer dan di-decode via `TextDecoder` saat keluar.
  - Wajib menggunakan `Atomics.wait` dan `Atomics.notify` untuk sinyal ketersediaan buffer kosong/terisi.

### Level Hard
Implementasikan pembagian beban kerja dinamis (*Work-Stealing Scheduler*) menggunakan $N$ workers.
- **Kriteria Penerimaan**:
  - Setiap worker memiliki deque (*double-ended queue*) lokal di dalam `SharedArrayBuffer`.
  - Jika deque lokal worker kosong, worker tersebut dapat mencuri (*steal*) tugas dari bagian bawah (*tail*) deque milik worker lain menggunakan operasi CAS `Atomics.compareExchange`.
  - Mampu mendistribusikan $100.000$ kalkulasi dengan beban kerja acak (*unbalanced workload*) secara merata ke seluruh core tanpa terjadi *race condition*.

---

## 14. Enterprise Challenge

### Kasus: High-Throughput Real-Time 4K Video Filter Engine

Anda ditugaskan merancang *pipeline* kompresi dan filter gambar berbasis peramban untuk aplikasi studio broadcast web enterprise. Sistem harus memproses frame video resolusi **4K (3840 x 2160)** dengan format piksel `RGBA` (setara ~33.17 megabita per frame mentah) pada target minimal **30 FPS**.

#### Persyaratan Teknis:
1. **Zero Data Copy**: Dilarang menggunakan serialisasi `postMessage` standar untuk pertukaran frame array buffer. Wajib menggunakan `SharedArrayBuffer` terisolasi atau `Transferable ImageBitmap`.
2. **Dynamic Work Partitioning**: Matriks 4K harus dipecah menjadi blok-blok *tile* matriks yang diproses secara konkuren menggunakan Worker Pool ($N$ thread sesuai core CPU).
3. **Filter Pipeline**: Terapkan algoritma konvolusi matriks $5 \times 5$ Gaussian Blur secara paralel pada memori bersama.
4. **Off-Main-Thread Rendering**: Tampilkan visual akhir ke elemen `<canvas id="viewport">` menggunakan `OffscreenCanvas` di dalam thread terpisah, sehingga main thread sama sekali tidak mengalami lonjakan beban pemrosesan (*zero CPU frame dropped*).
5. **Backpressure Control**: Jika kalkulasi konvolusi memakan waktu lebih lama dari laju input frame, sistem harus memiliki mekanisme penolakan atau *frame dropping strategy* terstruktur tanpa menyebabkan kebocoran memori pada typed array buffer.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Mengapa pemanggilan `Atomics.wait` dilarang pada Main Thread di browser?**
   - *Jawaban*: Karena `Atomics.wait` memblokir thread secara synchronous hingga menerima notifikasi atau timeout. Jika dieksekusi di Main Thread, seluruh *Event Loop*, pemrosesan interaksi pengguna, dan pipeline rendering UI akan membeku (*freezing*), menyebabkan browser menampilkan peringatan *Unresponsive Page*.

2. **Apa yang terjadi pada `ArrayBuffer` di thread sumber jika ditransfer sebagai `Transferable`?**
   - *Jawaban*: Buffer sumber mengalami proses *neutering*; kepemilikan pointer memori diserahkan ke thread penerima, dan `byteLength` pada buffer sumber seketika berubah menjadi 0, sehingga thread sumber tidak dapat lagi membaca atau menulis ke buffer tersebut.

3. **Berapa batas alokasi ukuran byte minimum untuk elemen yang dapat disinkronkan via `Atomics.wait` dan `Atomics.notify`?**
   - *Jawaban*: Wajib berupa `Int32Array` (elemen integer 32-bit bertanda), yang berarti membutuhkan alokasi memori berukuran 4 byte per elemen dengan alignment memori kelipatan 4.

4. **Sebutkan dua header respons HTTP yang wajib ada untuk mengaktifkan `SharedArrayBuffer` di browser modern!**
   - *Jawaban*: `Cross-Origin-Opener-Policy: same-origin` dan `Cross-Origin-Embedder-Policy: require-corp`.

5. **Apa fungsi utama dari `Atomics.isLockFree(size)`?**
   - *Jawaban*: Untuk memeriksa apakah operasi atomik pada ukuran byte tertentu (`size`) didukung langsung oleh instruksi perangkat keras CPU (*hardware atomic instruction*) tanpa menggunakan fallback penguncian internal mesin virtual.

### Bagian 2: Intermediate (5 Pertanyaan)
6. **Jelaskan perbedaan mendasar antara `Atomics.store()` dan penugasan array biasa (`typedArray[0] = val`) pada `SharedArrayBuffer`!**
   - *Jawaban*: Penugasan biasa dapat direorder oleh compiler JIT atau pipeline CPU dan tidak menjamin visibilitas instan ke thread lain (*memory tearing* bisa terjadi). Sebaliknya, `Atomics.store()` bertindak sebagai *memory release barrier*, menjamin nilai langsung tersimpan ke memori dan semua operasi penulisan sebelumnya diselesaikan sebelum nilai baru dapat dibaca thread lain.

7. **Bagaimana cara mendeteksi secara programatis apakah peramban saat ini mendukung dan mengizinkan penggunaan `SharedArrayBuffer`?**
   - *Jawaban*: Dengan mengevaluasi properti global: `typeof SharedArrayBuffer !== "undefined" && self.crossOriginIsolated === true`.

8. **Apa yang dimaksud dengan "False Sharing" dalam konkurensi memori bersama JavaScript, dan bagaimana cara mengatasinya?**
   - *Jawaban*: Kondisi ketika dua thread memodifikasi variabel atomik berbeda yang berada dalam satu baris cache CPU (*cache line*, umumnya 64 byte) yang sama. Hal ini memicu pembatalan cache lintas core secara konstan dan merusak performa. Solusinya adalah menambahkan padding memori minimal 64 byte antar-variabel independen.

9. **Mengapa mentransfer `OffscreenCanvas` ke Worker lebih unggul dibanding mengirim data gambar mentah secara berulang via `postMessage`?**
   - *Jawaban*: Karena kepemilikan kanvas berpindah secara permanen (`transferControlToOffscreen`). Worker dapat menggambar langsung ke antarmuka grafis OS/GPU menggunakan siklus `requestAnimationFrame` lokal tanpa perlu menyalin data frame atau membebani Event Loop main thread.

10. **Apa perbedaan perilaku `Atomics.compareExchange` dengan `Atomics.exchange`?**
    - *Jawaban*: `Atomics.exchange` menimpa nilai lama dengan nilai baru tanpa syarat dan mengembalikan nilai lama. Sedangkan `Atomics.compareExchange` hanya menimpa nilai lama dengan nilai baru jika nilai lama sama dengan nilai ekspektasi yang dioperkan (*conditional write*).

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario A**:  
    Sebuah aplikasi web GIS (*Geographic Information System*) enterprise memproses data poligon besar di Worker thread. Ketika peta digeser (*panning*), Worker mengirim array poligon hasil kalkulasi berukuran 150 MB kembali ke Main Thread menggunakan `postMessage(data)`. Main thread mengalami *stuttering* (penurunan FPS drastis selama ~120 ms).  
    *Analisis masalah dan berikan solusi arsitektural terbaik tanpa mengubah struktur objek GeoJSON!*
    - *Jawaban Analisis & Solusi*:  
      Penurunan FPS disebabkan oleh biaya serialisasi Structured Clone pada payload 150 MB di main thread. Solusi: Alokasikan koordinat poligon ke dalam struktur biner datar (*flat binary array*) `Float64Array`. Gunakan `Transferable` untuk mentransfer array tersebut ke main thread ($\mathcal{O}(1)$ pointer swap) atau alokasikan sejak awal dalam satu `SharedArrayBuffer` global, sehingga main thread hanya menerima indeks offset koordinat yang harus dirender.

12. **Skenario B**:  
    Sistem thread pool yang Anda kembangkan sering mengalami kebuntuan (*deadlock*) di mana seluruh Worker thread berada dalam status `Atomics.wait` selamanya, meskipun Main Thread mengklaim telah memanggil `Atomics.notify`. Setelah dianalisis, hal ini hanya terjadi ketika jaringan internet pengguna sangat lambat.  
    *Apa akar masalahnya dan bagaimana memperbaikinya?*
    - *Jawaban Analisis & Solusi*:  
      Terjadi *race condition* pada urutan inisialisasi: Main Thread mengirim pesan tugas dan memanggil `Atomics.notify()` sebelum Worker selesai menginisialisasi TypedArray atau sebelum Worker memanggil `Atomics.wait()`. Notifikasi yang dikirim saat tidak ada thread yang tertidur akan hilang (*lost wakeup*). Perbaikan: Terapkan protokol *handshake* dua arah: Worker wajib mengirim pesan kesiapan (`READY`) ke Main Thread sebelum Main Thread mulai mendistribusikan beban kerja dan memicu notifikasi.

13. **Skenario C**:  
    Server CDN perusahaan Anda tidak mengizinkan pengubahan header respon global untuk menyetel `COOP` dan `COEP` karena berdampak buruk pada iklan pihak ketiga (*third-party ads iframe*) yang belum mendukung isolasi. Namun, aplikasi Anda sangat membutuhkan paralelisasi komputasi intensif di sisi klien.  
    *Arsitektur konkurensi apa yang dapat Anda terapkan sebagai fallback tanpa SharedArrayBuffer?*
    - *Jawaban Analisis & Solusi*:  
      Gunakan fallback arsitektur **Actor Model** berbasis Dedicated Web Workers dengan komunikasi **Transferable Objects** (`ArrayBuffer`). Main thread mengalokasikan data biner ke `ArrayBuffer`, lalu mentransfer kepemilikannya ke worker pool untuk diproses. Setelah selesai, worker mentransfer kembali buffer hasil ke main thread. Pola ini mempertahankan performa *zero-copy* ($\mathcal{O}(1)$ transfer overhead) tanpa memerlukan `SharedArrayBuffer` maupun prasyarat header keamanan COOP/COEP.

---

## 16. Summary

1. **V8 Concurrency Architecture**: JavaScript mencapai paralelisasi murni melalui isolasi Isolate independen. Setiap Web Worker beroperasi dengan heap dan event loop terpisah, membebaskan CPU core untuk kalkulasi tanpa memblokir thread UI.
2. **Zero-Copy Memory Semantics**: Mentransfer `ArrayBuffer` melalui antarmuka `Transferable` meniadakan latensi serialisasi ($\mathcal{O}(1)$ pointer transfer), sementara `SharedArrayBuffer` memungkinkan beberapa Isolate memetakan ruang alamat virtual ke blok fisik memori yang sama.
3. **Synchronous Coordination via Atomics**: Operasi atomik (`load`, `store`, `compareExchange`) bertindak sebagai penghalang memori (*memory barriers*) tingkat perangkat keras. Pasangan `Atomics.wait` dan `Atomics.notify` menghadirkan primitif futex kernel untuk menidurkan dan membangunkan thread tanpa membuang siklus clock CPU.
4. **Isolasi Browser (COOP & COEP)**: Demi mitigasi kerentanan spekulatif seperti *Spectre*, browser modern mewajibkan isolasi origin penuh (`Cross-Origin-Opener-Policy: same-origin` dan `Cross-Origin-Embedder-Policy: require-corp`) sebelum memvalidasi pembuatan memori bersama.
5. **Pemisahan Pipeline Total**: Memadukan `SharedArrayBuffer`, worker pools, dan `OffscreenCanvas` memungkinkan aplikasi enterprise memproses ribuan data per detik dan merender visualisasi grafis 120 FPS tanpa menyebabkan satu pun frame UI terdegradasi.