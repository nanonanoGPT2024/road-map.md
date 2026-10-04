# Kurikulum Pemrograman JavaScript
## Kategori 02: Programming Languages
### Bab 06: Advanced Runtime Architecture & Systems Programming
#### Module 01: Concurrency Models, Web Workers & Parallel Computing

---

### SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: JS-ADV-06-001
* **Tingkat Kesulitan**: Advanced / Principal Level
* **Prasyarat Pengetahuan**:
  * Pemahaman mendalam mengenai JavaScript Event Loop, Call Stack, Microtask (Promise) & Macrotask Queue.
  * Memori dasar JavaScript: Heap vs Stack allocation.
  * TypedArray dan Buffer manipulation (`ArrayBuffer`, `Uint8Array`, `Float64Array`).
  * Konsep dasar Operating System (OS): Threading, Context Switching, Preemptive vs Cooperative Multitasking, Mutex, dan Race Condition.
* **Estimasi Waktu Penyelesaian**: 8 – 10 Jam Pembelajaran Mandiri / Praktikum Terpandu.

---

### SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, arsitek/rekayasawan perangkat lunak mampu:
1. **Mendiferensiasikan** secara mekanistik antara model *concurrency* asinkronus berbasis Event Loop (single-threaded) dengan komputasi paralel sejati (*true parallelism*) berbasis multi-threading.
2. **Mendiagnosis** dan mengeliminasi fenomena *jank*, *frame drops*, dan *Long Tasks* pada Main Thread dengan mendelegasikan komputasi berbobot CPU tinggi ke Worker Threads.
3. **Mengimplementasikan** komunikasi antar-thread menggunakan *Structured Clone Algorithm* serta mengeksploitasi *Zero-Copy Transfer* via `Transferable Objects`.
4. **Membangun** arsitektur memori bersama (*shared memory*) performa tinggi memanfaatkan `SharedArrayBuffer` dan koordinasi thread deterministik menggunakan primitif sinkronisasi `Atomics`.
5. **Merancang** sistem *Worker Pool* yang dapat diskalakan (*resilient & dynamic thread pool*) dengan mendeteksi kapasitas perangkat keras melalui `navigator.hardwareConcurrency`.
6. **Menerapkan** standardisasi keamanan modern (*Cross-Origin Isolation*) yang dipersyaratkan oleh runtime untuk eksekusi primitif memori tingkat rendah.

---

### SEKSI 03 — MINDSET & MENTAL MODEL

JavaScript sering diasosiasikan sebagai bahasa yang "single-threaded". Model mental ini benar hanya jika dibatasi pada satu *execution context* / *V8 Isolate*. 

```
+-----------------------------------------------------------------------+
|                             MENTAL MODEL                              |
+-----------------------------------------------------------------------+
|  ASINKRONUS (Event Loop)         PARALELISME (Web Workers)            |
|  "Satu koki melompat-lompat        "Banyak koki di meja terpisah      |
|   antara oven, wajan, & talenan."   memasak hidangan secara simultan."|
|                                                                       |
|  - Concurrency != Parallelism    - Memerlukan koordinasi IPC/Shared   |
|  - Cooperative Multitasking      - Preemptive OS-level Threads        |
|  - I/O Bound Optimization        - CPU Bound Optimization             |
+-----------------------------------------------------------------------+
```

1. **Concurrency vs Parallelism**: 
   * *Concurrency* adalah kemampuan menangani banyak hal sekaligus (misal: menunggu 10 network request bersamaan lewat non-blocking I/O). Ini bukan komputasi paralel; ini adalah delegasi I/O ke kernel OS dan penanganan respons di antrean event loop.
   * *Parallelism* adalah kemampuan mengeksekusi banyak komputasi secara bersamaan pada waktu fisik yang persis sama pada *multi-core CPU*.
2. **Isolasi Memori Default (Shared-Nothing Architecture)**: 
   Setiap Web Worker berjalan pada thread OS terpisah dengan V8 Isolate, call stack, dan heap memory sendiri. Mereka tidak berbagi memori secara default. Komunikasi default dilakukan lewat *Message Passing* (menyalin data).
3. **Shared-Memory Paradigm**: 
   Ketika throughput data menjadi bottleneck serialization, kita beralih ke paradigma Shared Memory (`SharedArrayBuffer`). Di titik ini, JavaScript kehilangan kenyamanan "single-threaded safety"-nya; pengembang mengambil alih tanggung jawab OS engineer untuk mencegah *Data Races* dan *Deadlocks* menggunakan operasi atomik (`Atomics`).

---

### SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur aliran data dan isolasi memori antara Main Thread dan Web Worker:

```
[ MAIN THREAD (UI / Rendering) ]                [ WORKER THREAD (Background) ]
  +-------------------------+                     +-------------------------+
  | V8 Isolate / Heap #1    |                     | V8 Isolate / Heap #2    |
  | DOM, CSSOM, Event Loop  |                     | No DOM, Isolated Scope  |
  +------------+------------+                     +------------+------------+
               |                                               |
  ===========================================================================
  KOMUNIKASI 1: Structured Clone (Deep Copy Overhead)
  [Objek Asli]  ----(Serialisasi)----> [Kanal IPC] ----(Deserialisasi)----> [Objek Baru]
  ===========================================================================
  KOMUNIKASI 2: Transferable Objects (Zero-Copy Transfer of Ownership)
  [ArrayBuffer]                                             [ArrayBuffer]
  [Data: 0x01A] --(Detach Pointer: 0x000)------------------> [Data: 0x01A]
  ===========================================================================
  KOMUNIKASI 3: SharedArrayBuffer + Atomics (Shared Memory)
                +------------------------------------+
                | Shared Memory Segment (RAM)        |
                | [ Byte 0 | Byte 1 | Byte 2 | ... ] |
                +-----------------+------------------+
                                  ^
                        Direct Concurrent Access
                                  |
              Atomics.load / store / wait / notify
                     /                      \
        Main Thread (non-blocking)      Worker Thread (can block)
```

#### Alur Eksekusi Worker Pool & Dispatcher:

```
[ Task Queue (FIFO) ] 
       |
       v
+------------------+     Pilih Worker Idle      +------------------+
| Task Dispatcher  | ------------------------> | Worker 1 (Busy)  |
| (Load Balancer)  |                           +------------------+
+------------------+                           +------------------+
       |                                       | Worker 2 (Idle)  | <--- Diberi Tugas
       |                                       +------------------+
       |                                       +------------------+
       |                                       | Worker N (Idle)  |
       |                                       +------------------+
       |
       +--- Emit Promise Resolusi ke Consumer saat task selesai (onmessage)
```

---

### SEKSI 05 — ANATOMI & MEKANISME INTERNAL

#### 1. V8 Isolate dan Alokasi Thread OS
Ketika instansiasi `new Worker('worker.js')` dipanggil:
* Browser (misal Chromium) meminta Host OS untuk membuat *native OS thread*.
* Inisialisasi **V8 Isolate** baru di dalam thread tersebut. Isolate ini memiliki memory heap dan garbage collector (GC) terisolasi.
* Window context, DOM API, CSSOM, `localStorage`, dan referensi UI **tidak diinjeksikan** ke dalam global worker context (`DedicatedWorkerGlobalScope`).
* Script `worker.js` diunduh secara asinkronus (jika bukan inline/blob), diparse, dikompilasi, dan dieksekusi di thread tersebut.

#### 2. Mekanisme Komunikasi: Structured Clone vs Transferables
* **Structured Clone Algorithm**: Mesin JavaScript secara rekursif menelusuri graph object, menduplikasi properti, menangani circular reference, dan membangun replika lengkap pada target Isolate. Kompleksitas: $O(N)$ waktu dan memori. Mengirim payload 100MB menyebabkan lag karena serialisasi di pengirim dan deserialisasi di penerima.
* **Transferable Objects**: Digunakan pada tipe data tertentu (e.g., `ArrayBuffer`, `MessagePort`, `ImageBitmap`). Alih-alih menyalin data, kepemilikan memori (*pointer ownership*) dialihkan.
  * Buffer asal seketika menjadi *neutered* atau *detached* (ukurannya menjadi 0 byte di thread pengirim).
  * Kompleksitas waktu: $O(1)$. Ini adalah operasi penukaran pointer di tingkat C++ binding.

#### 3. SharedArrayBuffer & Atomics
* `SharedArrayBuffer` (SAB) memetakan blok virtual memory yang sama ke dalam ruang alamat kedua Isolate.
* Jika dua thread menulis ke byte yang sama tanpa koordinasi, terjadi *Data Race*. V8 mengimplementasikan spesifikasi ECMAScript Memory Model.
* `Atomics` mengikat langsung instruksi CPU tingkat rendah (seperti `LOCK CMPXCHG` pada arsitektur x86 atau `LDREX`/`STREX` pada ARM) untuk menjamin atomisitas modifikasi memori dan visibilitas cache CPU (memory fencing).

---

### SEKSI 06 — DEEP DIVE KONSEP & TEORI

#### 1. Pembatasan Arsitektur dan Mitigasi Keamanan Spectre
Setelah kerentanan perangkat keras *Spectre* dan *Meltdown* dieksploitasi, `SharedArrayBuffer` sempat dinonaktifkan di seluruh browser karena dapat dimanfaatkan untuk serangan *side-channel timing attacks* beresolusi tinggi.
Untuk mengaktifkannya kembali, server web wajib menyertakan dua HTTP Response Header:
1. `Cross-Origin-Opener-Policy: same-origin` (COOP)
2. `Cross-Origin-Embedder-Policy: require-corp` (COEP)

Tanpa kedua header ini, `window.crossOriginIsolated` bernilai `false`, dan constructor `new SharedArrayBuffer()` akan melempar *ReferenceError*.

#### 2. ECMAScript Memory Model & Operasi Atomics
Operasi Atomics menjamin keterurutan eksekusi (*sequential consistency*).
* `Atomics.load(typedArray, index)`: Membaca nilai dari memori, menjamin tidak ada instruksi pembacaan/penulisan lain yang di-*reorder* melewati batas ini.
* `Atomics.store(typedArray, index, value)`: Menulis nilai ke memori dengan *flush* seketika ke cache CPU yang terlihat oleh thread lain.
* `Atomics.compareExchange(typedArray, index, expectedValue, replacementValue)`: 
  * Atomic CAS (Compare-And-Swap). 
  * Memeriksa apakah `typedArray[index] === expectedValue`. Jika ya, ubah menjadi `replacementValue`. Operasi ini atomic dan bebas dari race condition.
* `Atomics.wait(int32Array, index, value, timeout)`: 
  * Menidurkan (*sleep/block*) thread pemanggil sampai index tersebut diubah atau dinotifikasi, atau waktu timeout habis.
  * **FATAL ERROR**: `Atomics.wait` **dilarang keras** dipanggil pada Main Thread. Memblokir Main Thread akan menghentikan rendering frame, input handling, dan memicu *Application Not Responding (ANR)*. Engine JavaScript akan melempar exception run-time jika ini dilanggar.
* `Atomics.notify(int32Array, index, count)`: 
  * Membangunkan sejumlah `count` thread yang sedang tertidur pada index memori tersebut via `Atomics.wait`.

---

### SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi fundamental perbandingan komputasi CPU intensif: 
1. Direct Execution di Main Thread.
2. Parallel Execution menggunakan Dedicated Web Worker via *Transferable Objects*.

#### File: `worker.js`
```javascript
// worker.js - Dedicated Worker Scope
self.onmessage = function (event) {
  const { type, buffer } = event.data;

  if (type === 'PROCESS_DATA') {
    // Membungkus buffer yang ditransfer ke dalam view Float64Array
    const floatArray = new Float64Array(buffer);
    const length = floatArray.length;

    // Komputasi CPU-bound intensif (Transformasi Matematika)
    for (let i = 0; i < length; i++) {
      floatArray[i] = Math.sqrt(floatArray[i]) * Math.sin(floatArray[i]);
    }

    // Transfer kepemilikan buffer kembali ke Main Thread (Zero-Copy)
    self.postMessage(
      {
        type: 'PROCESS_COMPLETE',
        buffer: floatArray.buffer,
      },
      [floatArray.buffer] // Parameter Transferables
    );
  }
};
```

#### File: `main.js`
```javascript
// main.js - Main Thread Scope
function runParallelTask() {
  const worker = new Worker('worker.js', { type: 'classic' });
  const DATA_SIZE = 5_000_000; // 5 juta elemen Float64 (~40 Megabytes)

  // 1. Alokasi memori di Main Thread
  const rawBuffer = new ArrayBuffer(DATA_SIZE * Float64Array.BYTES_PER_ELEMENT);
  const view = new Float64Array(rawBuffer);

  // Inisialisasi dummy data
  for (let i = 0; i < DATA_SIZE; i++) {
    view[i] = i * 1.5;
  }

  console.log(`[Before Transfer] Main Thread byteLength: ${rawBuffer.byteLength}`); // 40000000

  // 2. Setup listener respons dari worker
  worker.onmessage = function (event) {
    const { type, buffer } = event.data;

    if (type === 'PROCESS_COMPLETE') {
      const resultView = new Float64Array(buffer);
      console.log(`[Complete] Hasil index ke-10: ${resultView[10]}`);
      console.log(`[After Complete] Main Thread received byteLength: ${buffer.byteLength}`);

      // Bersihkan resources worker
      worker.terminate();
    }
  };

  worker.onerror = function (error) {
    console.error('Error terjadi di worker:', error.message);
    worker.terminate();
  };

  // 3. Kirim data menggunakan Transferable Objects (Zero-Copy)
  worker.postMessage(
    {
      type: 'PROCESS_DATA',
      buffer: rawBuffer,
    },
    [rawBuffer] // Memasukkan ArrayBuffer ke dalam transfer list
  );

  // Verifikasi detasemen memori (neutered buffer)
  console.log(`[After Transfer] Main Thread byteLength: ${rawBuffer.byteLength}`); // Menjadi 0!
}

runParallelTask();
```

---

### SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut bedah teknis implementasi SEKSI 07:

1. `worker.js: self.onmessage = function(event)`:
   * Menetapkan listener event level global di context worker. Variabel `self` merujuk pada `DedicatedWorkerGlobalScope`.
2. `worker.js: const floatArray = new Float64Array(buffer)`:
   * Menginstansiasi TypedArray View di atas binary buffer yang dialihkan. Tidak ada alokasi baru untuk isi data; hanya mengalokasikan struktur metadata objek *View* setebal puluhan byte.
3. `worker.js: self.postMessage({...}, [floatArray.buffer])`:
   * Parameter kedua `[floatArray.buffer]` mengeksploitasi protokol *Transferable*. Ini menginstruksikan C++ runtime binding untuk melepaskan ownership buffer dari worker Isolate dan mentransfer pointer alamat memori secara langsung ke Main Thread Isolate.
4. `main.js: const rawBuffer = new ArrayBuffer(...)`:
   * Mengalokasikan 40 MB memori contiguous (bersebelahan) di V8 Heap space.
5. `main.js: worker.postMessage({ type: 'PROCESS_DATA', buffer: rawBuffer }, [rawBuffer])`:
   * Melakukan transfer pointer kepemilikan memory block.
6. `main.js: console.log(rawBuffer.byteLength)` setelah transfer:
   * Menghasilkan nilai `0`. Mengakses indeks `view[0]` akan mengembalikan `undefined` atau bernilai 0 karena array telah di-*neuter* (dikosongkan). Hal ini mencegah race condition: dua thread membaca/menulis memori yang sama pada saat bersamaan secara liar.
7. `main.js: worker.terminate()`:
   * Secara paksa menghancurkan native thread OS dan membersihkan seluruh memory heap V8 Isolate worker seketika, mencegah *memory leak*.

---

### SEKSI 09 — STUDI KASUS NYATA

#### Skenario: Pipeline Pemrosesan Citra Skala Besar (Client-Side Edge Blurring / Convolution)
Sebuah SaaS analitik medis berbasis web perlu memproses citra resolusi ultra tinggi (misal: 4K/8K, ukuran data $3840 \times 2160 \times 4 = 33.17\text{ MB}$ raw RGBA pixels per layer).
* **Masalah**: Jika filtering konvolusi Gaussian matriks $5 \times 5$ dijalankan di Main Thread, eksekusi membutuhkan waktu sekitar 1200ms CPU-time murni. Selama 1.2 detik ini, Main Thread terkunci (*frozen*). Animasi CSS macet total, tombol UI tidak merespons (unresponsive input), dan metrik INP (*Interaction to Next Paint*) rusak parah ($>1000\text{ms}$).
* **Solusi Arsitektural**: 
  1. Main thread memotong gambar menjadi partisi horizontal (*Chunked Slicing*).
  2. Mengimplementasikan sistem **Worker Pool** dinamis sesuai ketersediaan core CPU native (`navigator.hardwareConcurrency`).
  3. Memanfaatkan **SharedArrayBuffer** agar setiap thread dapat membaca buffer input secara bersamaan tanpa alokasi ganda, dan menulis hasil komputasi ke segmen buffer output masing-masing menggunakan koordinasi non-blocking.

---

### SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah implementasi end-to-end arsitektur paralelisme multi-threaded: Shared Memory Worker Pool dengan konvolusi matriks.

#### 1. File: `shared-worker-core.js` (Worker Implementation)
```javascript
// shared-worker-core.js
self.onmessage = function (event) {
  const {
    taskId,
    inputBuffer,
    outputBuffer,
    width,
    height,
    startY,
    endY,
    kernel,
    kernelSize,
  } = event.data;

  // Bungkus buffer bersama ke dalam TypedArray
  const inputPixels = new Uint8ClampedArray(inputBuffer);
  const outputPixels = new Uint8ClampedArray(outputBuffer);

  const halfKernel = Math.floor(kernelSize / 2);

  // Proses segmentasi vertikal citra dari startY sampai endY
  for (let y = startY; y < endY; y++) {
    for (let x = 0; x < width; x++) {
      let r = 0, g = 0, b = 0, a = 0;

      for (let ky = -halfKernel; ky <= halfKernel; ky++) {
        for (let kx = -halfKernel; kx <= halfKernel; kx++) {
          const px = Math.min(Math.max(x + kx, 0), width - 1);
          const py = Math.min(Math.max(y + ky, 0), height - 1);

          const pixelOffset = (py * width + px) * 4;
          const weight = kernel[(ky + halfKernel) * kernelSize + (kx + halfKernel)];

          r += inputPixels[pixelOffset] * weight;
          g += inputPixels[pixelOffset + 1] * weight;
          b += inputPixels[pixelOffset + 2] * weight;
          a += inputPixels[pixelOffset + 3] * weight;
        }
      }

      const dstOffset = (y * width + x) * 4;
      outputPixels[dstOffset] = r;
      outputPixels[dstOffset + 1] = g;
      outputPixels[dstOffset + 2] = b;
      outputPixels[dstOffset + 3] = a;
    }
  }

  // Laporkan tugas selesai kepada Task Pool Dispatcher
  self.postMessage({ taskId, status: 'DONE' });
};
```

#### 2. File: `worker-pool.js` (Worker Pool Manager)
```javascript
// worker-pool.js
export class WorkerPool {
  constructor(workerScriptUrl, poolSize = navigator.hardwareConcurrency || 4) {
    this.workerScriptUrl = workerScriptUrl;
    this.poolSize = poolSize;
    this.workers = [];
    this.freeWorkers = [];
    this.taskQueue = [];

    this._initializePool();
  }

  _initializePool() {
    for (let i = 0; i < this.poolSize; i++) {
      const worker = new Worker(this.workerScriptUrl, { type: 'module' });
      worker.id = i;
      
      worker.onmessage = (event) => {
        this._handleWorkerCompletion(worker, event.data);
      };

      worker.onerror = (err) => {
        console.error(`Uncaught error in worker ${worker.id}:`, err);
        this._handleWorkerCompletion(worker, null, err);
      };

      this.workers.push(worker);
      this.freeWorkers.push(worker);
    }
  }

  _handleWorkerCompletion(worker, data, error = null) {
    const currentTask = worker.activeTask;
    worker.activeTask = null;
    this.freeWorkers.push(worker);

    if (currentTask) {
      if (error) {
        currentTask.reject(error);
      } else {
        currentTask.resolve(data);
      }
    }

    this._dispatchNext();
  }

  _dispatchNext() {
    if (this.freeWorkers.length === 0 || this.taskQueue.length === 0) {
      return;
    }

    const worker = this.freeWorkers.pop();
    const task = this.taskQueue.shift();

    worker.activeTask = task;
    worker.postMessage(task.payload);
  }

  exec(payload) {
    return new Promise((resolve, reject) => {
      this.taskQueue.push({ payload, resolve, reject });
      this._dispatchNext();
    });
  }

  destroy() {
    for (const worker of this.workers) {
      worker.terminate();
    }
    this.workers = [];
    this.freeWorkers = [];
    this.taskQueue = [];
  }
}
```

#### 3. File: `image-pipeline.js` (Orkestrator Pemrosesan Paralel)
```javascript
// image-pipeline.js
import { WorkerPool } from './worker-pool.js';

export async function processImageParallel(imageData, kernel, kernelSize) {
  // Validasi prasyarat Cross-Origin Isolation untuk SharedArrayBuffer
  if (!window.crossOriginIsolated) {
    throw new Error('Eksekusi dibatalkan: Lingkungan tidak mendukung window.crossOriginIsolated.');
  }

  const { width, height, data } = imageData;
  const totalBytes = data.byteLength;

  // 1. Buat SharedArrayBuffer untuk input dan output
  const inputSharedBuffer = new SharedArrayBuffer(totalBytes);
  const outputSharedBuffer = new SharedArrayBuffer(totalBytes);

  // Buat view dan salin data piksel asal ke shared buffer
  new Uint8ClampedArray(inputSharedBuffer).set(data);

  // 2. Inisialisasi pool sesuai jumlah physical/logical core perangkat
  const concurrency = navigator.hardwareConcurrency || 4;
  const pool = new WorkerPool('./shared-worker-core.js', concurrency);

  const chunkHeight = Math.ceil(height / concurrency);
  const promises = [];

  console.time('Parallel Image Processing Time');

  // 3. Distribusikan beban kerja secara seimbang (Chunking Partition)
  for (let i = 0; i < concurrency; i++) {
    const startY = i * chunkHeight;
    const endY = Math.min(startY + chunkHeight, height);

    if (startY >= height) break;

    const payload = {
      taskId: i,
      inputBuffer: inputSharedBuffer,
      outputBuffer: outputSharedBuffer,
      width,
      height,
      startY,
      endY,
      kernel,
      kernelSize,
    };

    promises.push(pool.exec(payload));
  }

  // 4. Sinkronisasi eksekusi semua parallel workers
  await Promise.all(promises);
  console.timeEnd('Parallel Image Processing Time');

  // Bersihkan pool setelah eksekusi
  pool.destroy();

  // 5. Kembalikan data hasil konvolusi yang baru
  return new ImageData(
    new Uint8ClampedArray(outputSharedBuffer),
    width,
    height
  );
}
```

---

### SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Dimensi Arsitektural | Event Loop (Asynchronous) | Web Worker (Structured Clone) | Web Worker (Transferable) | SharedArrayBuffer + Atomics |
| :--- | :--- | :--- | :--- | :--- |
| **Model Memori** | Single Heap Memory | Isolated / Deep Copy Heap | Isolated / Pointer Ownership Transfer | Shared Memory Segment (Concurrency) |
| **Beban Kloning Data**| Nol (Referensi lokal) | Sangat Tinggi: $O(N)$ CPU & Memory | Nol ($O(1)$) Pointer Move | Instan ($0$ Overhead) |
| **Tingkat Aksesibilitas DOM** | Akses Penuh ke `window`, `document` | Nol (Terisolasi) | Nol (Terisolasi) | Nol (Terisolasi) |
| **Risiko Concurrency** | Aman dari Race Condition | Sangat Aman (Share-nothing) | Sangat Aman (Buffer Neutered) | **Tinggi**: Raw Memory Race, Deadlock |
| **Kebutuhan HTTP Headers**| Tidak Butuh | Tidak Butuh | Tidak Butuh | **Wajib**: COOP & COEP |
| **Blocking Capability** | Tidak Boleh Memblokir | Aman Memblokir Thread Worker | Aman Memblokir Thread Worker | Mendukung Sleeping (`Atomics.wait`) |
| **Use Case Terbaik** | I/O-bound (Fetch, UI Events, Timers) | CPU-bound komputasi kecil-menengah | Aliran data sekuensial (Video/Audio streaming) | High-Performance Compute, 3D Canvas, Audio DSP, Gaming |

---

### SEKSI 12 — EDGE CASES & PITFALLS

#### 1. Deadlocks dengan `Atomics.wait`
Jika Thread A melakukan `Atomics.wait` menunggu kondisi dari Thread B, sementara Thread B secara tidak sengaja menunggu respon dari Thread A melalui channel lain (misal via `MessageChannel`), sistem akan mengalami kebuntuan fatal (*deadlock*).
* **Solusi**: Jangan pernah membuat siklus dependensi blocking. Selalu tentukan batasan nilai timeout pada `Atomics.wait(ta, idx, val, timeoutMs)`.

#### 2. False Sharing pada Struktur Memori Cache CPU
Ketika dua Worker berbeda memodifikasi index yang bersebelahan (misalnya Worker 1 memodifikasi `array[0]` dan Worker 2 memodifikasi `array[1]`), ini sering kali berada dalam satu *L1/L2 Cache Line* yang sama (biasanya 64 bytes).
* **Dampak**: CPU Core akan terus melakukan invalidasi cache ke Core lainnya (*cache bouncing*), menyebabkan degradasi performa komputasi drastis (*False Sharing*).
* **Solusi**: Terapkan *memory padding* atau pastikan alokasi per Worker memiliki jarak minimal 64 bytes jika ditulis berulang kali secara paralel.

#### 3. State "Neutered Buffer" yang Tak Disengaja
```javascript
const buffer = new ArrayBuffer(1024);
worker.postMessage(buffer, [buffer]);

// EDGE CASE BUG:
// Mencoba membaca kembali buffer pada Main Thread
console.log(buffer.byteLength); // 0
const view = new Uint8Array(buffer); // TypeError: Cannot perform Construct on a detached ArrayBuffer
```
Pengembang sering kali lupa bahwa buffer yang sudah dipassing ke array Transferable **tidak dapat lagi diakses selamanya** di thread pengirim.

---

### SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

#### Mistake 1: Memanggil `Atomics.wait` pada Main Thread
```javascript
// KODE SALAH (MAIN THREAD)
const shared = new SharedArrayBuffer(4);
const int32 = new Int32Array(shared);
Atomics.wait(int32, 0, 0); // Uncaught TypeError: Atomics.wait cannot be called in this context
```
* **Koreksi**: Hanya jalankan `Atomics.wait` di dalam Worker Context. Di Main Thread, gunakan `Atomics.waitAsync` (jika didukung runtime) atau polling non-blocking via `requestAnimationFrame` / `setTimeout`.

#### Mistake 2: Mencoba Mengirim Objek DOM / Fungsi via `postMessage`
```javascript
// KODE SALAH
const button = document.getElementById('submit-btn');
worker.postMessage({ btn: button, callback: () => console.log('Done') }); 
// Uncaught DOMException: Failed to execute 'postMessage' on 'Worker': function could not be cloned.
```
* **Koreksi**: Structured Clone Algorithm menolak fungsi, DOM Node, prototype chains, dan symbol. Kirim data murni (Plain Objects, Primitives, Buffers).

#### Mistake 3: Over-spawning Workers Tanpa Batas (*Thread Exhaustion*)
```javascript
// KODE SALAH: Spawning worker baru untuk setiap item kalkulasi
items.forEach(item => {
  const w = new Worker('task.js');
  w.postMessage(item);
});
```
* **Koreksi**: Native thread memakan alokasi OS RAM yang besar (masing-masing rata-rata 1MB - 2MB stack memory + V8 base overhead). Gunakan arsitektur *Worker Pool* berukuran tetap (tetapkan nilai maksimum berdasarkan `navigator.hardwareConcurrency`).

---

### SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Hardware Concurrency Detection dengan Fallback**:
   ```javascript
   const CPU_CORES = typeof navigator !== 'undefined' && navigator.hardwareConcurrency
     ? Math.min(navigator.hardwareConcurrency, 16) // Defensive upper limit
     : 4;
   ```
2. **Kompilasi WebAssembly di Main Thread, Instansiasi di Worker Threads**:
   * Kompilasi modul Wasm menjadi `WebAssembly.Module` di Main Thread secara asinkronus (`WebAssembly.compileStreaming`).
   * Kirim modul yang telah dikompilasi ke Worker via `postMessage`. `WebAssembly.Module` dapat dibagikan langsung antar thread tanpa kompilasi ulang.
3. **Graceful Teardown**: Selalu sediakan fungsionalitas abort atau shutdown (`worker.terminate()`) saat lifecycle komponen UI selesai (misalnya pada unmount React/Vue) untuk mencegah kebocoran memori.
4. **Isolasi Logika Komputasi Murni**: Arsitektur worker harus mengadopsi model *Pure Functional Execution*: input masuk -> komputasi kalkulasi -> output keluar, meminimalisir side-effects internal.

---

### SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

#### Analisis Profiling: Overhead Thread vs Throughput
Membuat Web Worker membutuhkan biaya *cold-start* (antara 10ms - 50ms untuk initial parsing & startup runtime V8 Isolate). 

```
Komputasi Cepat (< 5ms)     --> Eksekusi langsung di Main Thread (Event Loop)
Komputasi Sedang (5ms - 50ms) --> Pertimbangkan Async Chunks / requestIdleCallback
Komputasi Berat (> 50ms)     --> Delegasikan ke Worker Pool
Komputasi Sangat Masif (GB)  --> SharedArrayBuffer + TypedArray + Worker Pool
```

#### Memory Alignment untuk Operasi Atomics
`Atomics` mengharuskan TypedArray memiliki tipe representasi yang valid:
* `Int8Array`, `Uint8Array`, `Int16Array`, `Uint16Array`, `Int32Array`, `Uint32Array`, `BigInt64Array`, `BigUint64Array`.
* Indeks alamat memori **wajib ter-align** sesuai ukuran bit elemennya (misal: 4-byte aligned untuk `Int32Array`), jika tidak akan dilempar `RangeError`.

---

### SEKSI 16 — KEAMANAN & HARDENING

#### 1. Header Hardening (SAB Prerequisite)
Pastikan server produksi (e.g., NGINX / Cloudflare) menyuntikkan header keamanan secara mutlak:
```http
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

#### 2. Content Security Policy (CSP) untuk Worker
Kendalikan dari mana script worker boleh dieksekusi menggunakan direktif CSP `worker-src`:
```http
Content-Security-Policy: default-src 'self'; worker-src 'self' blob:;
```
Menyetel `worker-src 'self'` mencegah script pihak ketiga mengeksekusi worker jahat untuk melakukan *in-browser cryptomining*.

#### 3. Sanitasi Data IPC (*Inter-Process Communication*)
Jangan berasumsi pesan dari worker selalu valid. Selalu validasi schema respons pesan menggunakan runtime validator (seperti Zod atau manual type checking):
```javascript
worker.onmessage = (event) => {
  const data = event.data;
  if (typeof data !== 'object' || data === null || typeof data.taskId !== 'number') {
    throw new SecurityError('Malformed message packet received from isolated thread.');
  }
};
```

---

### SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

#### 1. Melacak Eksekusi Multi-Thread di Chrome DevTools
1. Buka DevTools -> Tab **Sources**.
2. Pada panel navigasi bawah/kanan, periksa drop-down **Threads**.
3. Saat worker aktif, daftar thread bertambah. Anda dapat mengklik thread worker tersebut untuk menyetel *Breakpoints* lokal di dalam skrip `shared-worker-core.js`.
4. DevTools **Performance Profiler**: Periksa baris `Main` vs baris `Worker 1`, `Worker 2`. Baris Worker akan menampilkan blok komputasi tanpa mengorbankan garis 60 FPS di panel *Frames*.

```
-----------------------------------------------------------------
[Main Thread]   || Layout | Paint |||| Frame Rendering (Clean 60 FPS)
-----------------------------------------------------------------
[Worker 1]      |||||||||||||||| CPU BOUND TASK |||||||||||||||||
-----------------------------------------------------------------
[Worker 2]      |||||||||||||||| CPU BOUND TASK |||||||||||||||||
-----------------------------------------------------------------
```

#### 2. Cross-Thread Performance Measurement
Gunakan User Timing API secara terstandarisasi untuk mengukur waktu IPC:
```javascript
// Main Thread
performance.mark('dispatch-task-start');
worker.postMessage(payload, [payload.buffer]);

worker.onmessage = () => {
  performance.mark('dispatch-task-end');
  performance.measure('Worker Roundtrip Execution', 'dispatch-task-start', 'dispatch-task-end');
  const measures = performance.getEntriesByName('Worker Roundtrip Execution');
  console.log(`Latency: ${measures[0].duration}ms`);
};
```

---

### SEKSI 18 — RINGKASAN & CHEAT SHEET

```javascript
// 1. Instansiasi Worker
const worker = new Worker(new URL('./worker.js', import.meta.url), { type: 'module' });

// 2. Transferable Pattern (Zero-Copy)
const buffer = new ArrayBuffer(1024 * 1024 * 16); // 16MB
worker.postMessage({ buffer }, [buffer]); // Buffer neutered di sini

// 3. SharedArrayBuffer (Shared Memory)
const sab = new SharedArrayBuffer(1024);
const int32 = new Int32Array(sab);
worker.postMessage({ sab }); // Memory segment dibagikan

// 4. Operasi Atomics Dasar
Atomics.store(int32, 0, 42);                  // Thread-safe write
const val = Atomics.load(int32, 0);            // Thread-safe read
Atomics.add(int32, 0, 1);                      // Increment atomik
Atomics.compareExchange(int32, 0, 43, 99);     // CAS: if 43, set to 99

// 5. Worker Sleeping & Waking (Worker Scope Only!)
Atomics.wait(int32, 0, 99);                    // Tidur sampai value != 99 atau dinotifikasi
Atomics.notify(int32, 0, 1);                   // Membangunkan 1 thread di index 0
```

---

### SEKSI 19 — KUIS EVALUASI PEMAHAMAN

#### Bagian A: Pilihan Ganda (Basic)

1. **Apa yang terjadi pada variabel `buffer` di Main Thread setelah dieksekusi: `worker.postMessage(buffer, [buffer])`?**
   * A. Nilai buffer dikloning secara rekursif, memori berlipat ganda.
   * B. Buffer di Main Thread menjadi terlepas (*neutered/detached*) dan panjang byte-nya menjadi 0.
   * C. Buffer dihapus oleh garbage collector secara langsung seketika.
   * D. Main thread terkunci sampai worker selesai memproses buffer.
   * *Jawaban yang benar*: **B**. Mekanisme Transferable Objects memindahkan kepemilikan pointer memori sehingga buffer asal dikosongkan untuk mencegah race condition.

2. **Dua HTTP Header wajib untuk mengaktifkan `SharedArrayBuffer` pada browser modern adalah...**
   * A. `Content-Type: application/javascript` dan `X-Frame-Options: DENY`
   * B. `Cross-Origin-Opener-Policy: same-origin` dan `Cross-Origin-Embedder-Policy: require-corp`
   * C. `Access-Control-Allow-Origin: *` dan `Cache-Control: no-cache`
   * D. `Strict-Transport-Security` dan `Content-Security-Policy: default-src 'none'`
   * *Jawaban yang benar*: **B**. Keduanya memicu isolasi lingkungan (*crossOriginIsolated*) guna memitigasi serangan timing attack Spectre.

3. **Manakah dari objek berikut yang TIDAK BISA dipassing melalui Structured Clone Algorithm pada `postMessage`?**
   * A. `Map` dan `Set`
   * B. `ArrayBuffer`
   * C. Sebuah fungsi closure JavaScript atau DOM Element
   * D. Objek sirkular (`obj.self = obj`)
   * *Jawaban yang benar*: **C**. Fungsi eksekusi dan Node DOM tidak dapat diserialisasi oleh Structured Clone Algorithm dan akan melempar `DataCloneError`.

4. **Kapan eksekusi kode di dalam Web Worker dapat memanipulasi DOM secara langsung?**
   * A. Jika script worker diimpor dengan parameter `{ type: 'module' }`.
   * B. Kapan saja melalui object `self.document`.
   * C. Tidak pernah bisa; Web Worker tidak memiliki akses ke DOM API.
   * D. Hanya jika menggunakan Service Worker.
   * *Jawaban yang benar*: **C**. Web Worker berjalan di thread terpisah tanpa reference global ke `window` atau `document`.

5. **Apa fungsi utama dari `navigator.hardwareConcurrency`?**
   * A. Menghitung penggunaan memori heap saat runtime.
   * B. Mengembalikan estimasi jumlah core logis (logical processor cores) yang tersedia pada perangkat pengguna.
   * C. Mengukur kecepatan clock rate CPU dalam GHz.
   * D. Membatasi alokasi RAM per thread worker.
   * *Jawaban yang benar*: **B**. Properti ini digunakan untuk mengoptimasi ukuran thread pool agar setara dengan core fisik/logis mesin.

---

#### Bagian B: Analisis Masalah & Kode (Intermediate)

6. **Perhatikan cuplikan kode di Main Thread berikut:**
   ```javascript
   const sharedBuffer = new SharedArrayBuffer(4);
   const int32 = new Int32Array(sharedBuffer);
   int32[0] = 0;
   // Tunggu sampai worker mengisi nilai selain 0
   Atomics.wait(int32, 0, 0);
   console.log('Worker selesai!');
   ```
   **Apa yang akan terjadi saat kode di atas dieksekusi di browser?**
   * A. Kode berjalan normal dan console log mencetak pesan saat worker selesai.
   * B. Terjadi crash memori seketika (*Out of Memory*).
   * C. Runtime JavaScript melempar `TypeError` karena `Atomics.wait` tidak diizinkan di Main Thread.
   * D. Browser secara otomatis mendeligasikan eksekusi ke background microtask.
   * *Jawaban yang benar*: **C**. `Atomics.wait` dilarang keras di Main Thread agar rendering UI tidak membeku.

7. **Dua worker membaca dan menulis ke index array yang sama secara serentak:**
   ```javascript
   // Worker A & Worker B secara bersamaan:
   sharedView[0] = sharedView[0] + 1;
   ```
   **Jika kedua thread menjalankannya 1000 kali, mengapa nilai akhir `sharedView[0]` sering kali kurang dari 2000?**
   * A. Karena Garbage Collection membersihkan data di tengah jalan.
   * B. Terjadi *Race Condition* karena operasi baca-tambah-tulis (`+=`) bukan operasi atomik tunggal di tingkat instruksi prosesor.
   * C. TypedArray tidak mendukung angka lebih dari 1000.
   * D. Karena SharedArrayBuffer memiliki buffer overflow limit.
   * *Jawaban yang benar*: **B**. `sharedView[0] + 1` terdiri dari 3 instruksi: Read, Modify, Write. Thread dapat saling menimpa nilai yang dibaca jika tidak dikoordinasikan via `Atomics.add(sharedView, 0, 1)`.

8. **Manakah skenario di mana penggunaan Web Worker JUSTRU memperlambat performa sistem?**
   * A. Melakukan enkripsi string teks berukuran 200 Megabyte.
   * B. Melakukan komputasi pertambahan dua integer sederhana `1 + 1` sebanyak satu kali dengan mengirimkannya ke worker.
   * C. Melakukan kompresi data file lokal ke format ZIP.
   * D. Menghitung posisi pathfinding 500 entity musuh pada game 2D.
   * *Jawaban yang benar*: **B**. Biaya *context-switching*, thread creation, dan latensi *IPC message-passing* jauh lebih mahal daripada komputasi sepele, menghasilkan *negative performance gain*.

9. **Apa perbedaan mendasar antara Dedicated Web Worker dan Shared Worker?**
   * A. Dedicated worker dapat mengakses DOM, Shared Worker tidak.
   * B. Dedicated worker hanya terikat pada satu tab/skrip pembuka, sedangkan Shared Worker dapat dibagi ke banyak tab, iframe, atau window dari origin yang sama.
   * C. Shared Worker berjalan di GPU, Dedicated Worker berjalan di CPU.
   * D. Dedicated worker tidak mendukung TypedArray.
   * *Jawaban yang benar*: **B**. Shared Worker menggunakan port komunikasi (`MessagePort`) untuk melayani beberapa browser browsing context secara simultan.

10. **Bagaimana cara mencegah kebocoran memori (*memory leak*) saat menghentikan worker yang sudah tidak digunakan?**
    * A. Menyetel variabel `worker = null` tanpa tindakan lain.
    * B. Memanggil method `worker.terminate()` dari main thread atau `self.close()` di dalam worker context.
    * C. Mengosongkan event listener `worker.onmessage = null`.
    * D. Memanggil `window.gc()` di konsol.
    * *Jawaban yang benar*: **B**. `terminate()` atau `close()` membunuh execution thread OS seketika dan melepaskan V8 Isolate beserta alokasi native memory-nya.

---

### SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

#### Judul Proyek: "Parallel Matrix Multiplication Engine with SharedArrayBuffer"

#### Deskripsi
Bangun sebuah engine perkalian matriks paralel berbasis web yang mampu mengalikan dua matriks kuadrat besar ($N \times N$, misal: $1000 \times 1000$, total 1.000.000 elemen numerik `Float64`) secara paralel.

#### Spesifikasi Kebutuhan:
1. **Antarmuka Utama (`index.html` & `main.js`)**:
   * Menyediakan formulir input untuk menentukan dimensi matriks $N$.
   * Menampilkan tombol: "Jalankan Single Thread (Event Loop)" vs "Jalankan Paralel (Worker Pool)".
   * Visualisasi status thread dan pencatatan benchmark runtime menggunakan `performance.now()`.
   * Indikator FPS/Animasi CSS yang terus berputar untuk membuktikan bahwa versi paralel **tidak membekukan (freeze)** antarmuka pengguna sama sekali.
2. **Infrastruktur Paralel**:
   * Hitung partisi baris yang dialokasikan ke masing-masing core menggunakan `navigator.hardwareConcurrency`.
   * Alokasikan 3 `SharedArrayBuffer`:
     * Matriks A ($N \times N \times 8\text{ bytes}$)
     * Matriks B ($N \times N \times 8\text{ bytes}$)
     * Matriks Hasil C ($N \times N \times 8\text{ bytes}$)
   * Main thread mengisi Matriks A dan B dengan angka acak.
   * Distribusikan baris kalkulasi ke dalam Worker Pool.
3. **Worker Implementation (`matrix-worker.js`)**:
   * Menerima shared buffers, dimensi $N$, rentang kalkulasi baris (`rowStart` sampai `rowEnd`).
   * Menghitung nilai dot product:
     $$C[i][j] = \sum_{k=0}^{N-1} A[i][k] \times B[k][j]$$
   * Menulis langsung ke `SharedArrayBuffer` Matriks C.
4. **Verifikasi & Evaluasi**:
   * Main thread memverifikasi akurasi sampel perhitungan hasil Matriks C.
   * Bandingkan performa: Tunjukkan grafik perbedaan latency komputasi dan responsivitas UI antara model konvensional vs Web Worker multi-threading. Pastikan server lokal Anda dikonfigurasi dengan header COOP & COEP yang benar!