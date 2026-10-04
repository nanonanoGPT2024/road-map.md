# Bab 01: Fondasi & Arsitektur
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** siklus hidup memori V8 engine (New Space/Scavenger, Old Space/Mark-Sweep-Compact) dan mendeteksi degradasi performa akibat *memory leak* atau *hidden class deoptimization*.
- **Menguasai** 6 fase eksekusi Libuv Event Loop secara deterministik (`timers`, `pending callbacks`, `idle/prepare`, `poll`, `check`, `close callbacks`) serta mekanisme interupsi mikro-tugas (`process.nextTick` vs `Promise.resolve`).
- **Merancang** sistem backend berkonkurensi tinggi dengan pemisahan beban kerja I/O-bound (Non-blocking I/O via `epoll`/`kqueue`/`IOCP`) dan CPU-bound menggunakan `worker_threads` terisolasi atau C++ Addons via Node-API (N-API).
- **Mendiagnosis** dan memitigasi *Event Loop Starvation*, saturasi *Libuv Threadpool*, serta *Backpressure Failure* pada Node.js Streams di lingkungan enterprise.
- **Mengimplementasikan** arsitektur *production-grade* berbasis multi-core clustering, *graceful degradation*, dan instrumentasi observabilitas mendalam (`AsyncLocalStorage`, tracing metrik GC, dan V8 heap dump).

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta diwajibkan telah menguasai:
- Konsep dasar JavaScript modern (ES2022+): asynchronous flow, closures, prototype chain, WeakMap/WeakSet, ArrayBuffer, and TypedArrays.
- Pemahaman fundamental Node.js Bab 01 Modul 01 (konsep single-thread, non-blocking I/O dasar, dan CLI dasar).
- Konsep sistem operasi tingkat menengah: POSIX syscalls (`read`, `write`, `epoll`, `kqueue`), thread pool, proses OS vs thread, paging, memory allocation, dan interrupt handling.
- Penggunaan dasar alat CLI: `node`, `npm`, terminal Linux/macOS, dan dasar-dasar debugging.

---

### 3. Concept & Internal Architecture

Node.js bukan sekadar "JavaScript runtime"; Node.js adalah orkestrasi polimorfik antara **Google V8 Engine**, **Libuv**, dan kumpulan binding internal C++ (`src/` pada core Node.js).

```
+-----------------------------------------------------------------------+
|                           Node.js Application                         |
+-----------------------------------------------------------------------+
| Node.js Standard Library (fs, http, crypto, stream, worker_threads)   |
+-----------------------------------+-----------------------------------+
| Node.js C++ Bindings (Node-API)  | Socket & File Descriptor Wrapping |
+-----------------+-----------------+-----------------------------------+
|  V8 Engine      |               Libuv C Library                       |
| - Parser / JIT  | - Event Loop (6 Phases)                             |
| - Heap Manager  | - Worker Threadpool (POSIX Threads / Windows Fibers)|
| - GC (Orinoco)  | - OS Non-blocking I/O Subsystem Polling             |
|   (Scavenge,    |   (epoll [Linux], kqueue [macOS], IOCP [Windows])   |
|    Mark-Sweep)  |                                                     |
+-----------------+-----------------------------------------------------+
|                      Sistem Operasi / CPU Core                        |
+-----------------------------------------------------------------------+
```

#### A. Arsitektur Memori V8 (The V8 Memory Heap Lifecycle)
V8 mengalokasikan memori dalam beberapa segmen heap terisolasi:

```
+-------------------------------------------------------------------+
|                        V8 Managed Heap                            |
| +----------------------------------+ +--------------------------+ |
| |        New Space (Young Gen)     | |  Old Pointer Space       | |
| |  +-------------+---------------+ | |  (Objects with pointers) | |
| |  | Semi-Space  | Semi-Space    | | +--------------------------+ |
| |  | From-Space  | To-Space      | | |  Old Data Space          | |
| |  +-------------+---------------+ | |  (Raw data: strings,     | |
| +----------------------------------+ |   boxed numbers)         | |
| +----------------------------------+ +--------------------------+ |
| | Large Object Space (LOS)         | | Code Space (JIT compiled)| |
| +----------------------------------+ +--------------------------+ |
| | Map Space (Shapes/Transitions)   | | Read-Only Space          | |
| +----------------------------------+ +--------------------------+ |
+-------------------------------------------------------------------+
```

1. **New Space (Young Generation)**:
   - Berukuran kecil (1 MB hingga 64 MB), dirancang untuk objek dengan umur sangat pendek (*ephemeral*).
   - Terbagi menjadi dua **Semi-Spaces**: **From-Space** dan **To-Space**.
   - Dikelola oleh **Scavenger Collector** menggunakan algoritma *Cheney's Copying Algorithm*. Ketika From-Space penuh, Scavenger menyalin objek hidup (*live objects*) ke To-Space, menukar pointer kedua ruang tersebut, dan membuang memori mati secara instan.
   - Objek yang lolos dari dua siklus Scavenge dipromosikan (*tenured*) ke **Old Space**.

2. **Old Space (Old Generation)**:
   - Menyimpan objek yang bertahan lama (koneksi database, cache global, singleton).
   - Dikelola oleh **Major GC (Mark-Sweep-Compact)** menggunakan *Orinoco engine*:
     - **Incremental Marking**: V8 memecah proses pelacakan objek menjadi potongan-potongan kecil terinterleave dengan JavaScript execution untuk meminimalisasi *Stop-The-World* (STW) pause.
     - **Concurrent Sweeping & Compacting**: Thread latar belakang V8 membebaskan halaman memori dan memadatkan objek yang terfragmentasi tanpa memblokir thread eksekusi utama.

3. **Optimization & Deoptimization**:
   - V8 membuat representasi internal tersembunyi bernama **Shapes** (atau **Hidden Classes**) untuk melacak layout objek.
   - Mengubah struktur objek secara dinamis (menambah properti di luar konstruktor atau menghapus properti via `delete`) menyebabkan *Shape Transition* dan membatalkan optimasi TurboFan (Deoptimization), memicu *polymorphism/megamorphism* yang memperlambat eksekusi hingga 10x-100x.

#### B. Libuv: The Event Loop State Machine
Event loop adalah sebuah *finite state machine* berbasis *single-threaded loop* yang berjalan di dalam thread utama Libuv.

```
       +-----------------------+
  +--->|     1. Timers         |<---+
  |    +-----------+-----------+    |
  |                |                |
  |    +-----------v-----------+    |
  |    |  2. Pending Callbacks |    |
  |    +-----------+-----------+    |
  |                |                |
  |    +-----------v-----------+    |
  |    |   3. Idle / Prepare   |    |
  |    +-----------+-----------+    |
  |                |                |
  |    +-----------v-----------+    |
  |    |        4. Poll        |    | <--- I/O Events (epoll/kqueue)
  |    +-----------+-----------+    |
  |                |                |
  |    +-----------v-----------+    |
  |    |       5. Check        |    | <--- setImmediate()
  |    +-----------+-----------+    |
  |                |                |
  |    +-----------v-----------+    |
  |    |   6. Close Callbacks  |    |
  |    +-----------+-----------+    |
  |                |                |
  +----------------+----------------+
```

Detail Tiap Fase:
1. **Timers**: Mengeksekusi callback dari `setTimeout` dan `setInterval` yang ambang batas waktunya (*threshold*) telah terpenuhi. Diurutkan menggunakan *min-heap*.
2. **Pending Callbacks**: Mengeksekusi callback I/O yang tertunda dari iterasi sebelumnya (contoh: error sistem spesifik level OS seperti transmisi jaringan `ECONNREFUSED`).
3. **Idle, Prepare**: Fase koordinasi internal Libuv, digunakan untuk sinkronisasi state sebelum polling.
4. **Poll**: Mengambil event I/O baru. Libuv memblokir thread di sini (*blocking poll*) selama durasi yang ditentukan oleh timer terdekat jika tidak ada antrean lain, lalu mendistribusikan callback I/O stream/file descriptor.
5. **Check**: Dikhususkan secara eksklusif untuk mengeksekusi callback dari `setImmediate()`.
6. **Close Callbacks**: Membersihkan state resource, seperti `socket.on('close', ...)`.

**Mikro-tugas (Intermediate Microtask Queues):**
Di antara setiap fase atau setelah transisi callback individual, Node.js mengeksekusi dua antrean prioritas mikro:
1. `process.nextTick Queue`: Memiliki prioritas tertinggi mutlak. Menunda eksekusi event loop fase berikutnya hingga antrean ini bersih.
2. `Promise Microtask Queue`: Mengeksekusi rejection/resolution dari Promises (`.then`, `await`).

#### C. Libuv Threadpool vs OS Non-Blocking Kernel
Banyak developer salah mengira bahwa seluruh operasi asynchronous di Node.js menggunakan Libuv Threadpool. Faktanya:
- **Jaringan (TCP, UDP, TLS, DNS resolve IP)**: 100% NON-BLOCKING di level OS kernel melalui event notification systems (`epoll` di Linux, `kqueue` di BSD/macOS, `IOCP` di Windows). **TIDAK MENGGUNAKAN THREADPOOL**.
- **Operasi File System (`fs.*`)**: Sebagian besar kernel OS (terutama Linux POSIX AIO) tidak memiliki API asynchronous file I/O yang memadai untuk general-purpose streams. Node.js mendelegasikan semua `fs.*` asynchronous ke **Libuv Threadpool** (default: 4 thread, diatur via `UV_THREADPOOL_SIZE`).
- **Kriptografi & Kompresi**: `crypto.pbkdf2`, `crypto.scrypt`, `zlib.*` dijalankan di Libuv Threadpool untuk mencegah saturasi event loop.

---

### 4. Why & What

#### Mengapa Memahami Internal Node.js Mutlak Dibutuhkan?
Dalam beban kerja ringan, arsitektur *event-driven* Node.js terasa ajaib dan instan. Namun, ketika throughput aplikasi melonjak melampaui ribuan *Request Per Second* (RPS), abstraksi ini pecah jika internalnya diabaikan:
- **Threadpool Starvation**: Pemanggilan 4 operasi `fs.readFile` besar secara paralel akan menghabiskan seluruh threadpool bawaan. Permintaan DNS resolver (`dns.lookup`) berikutnya akan tertahan (*starved*), memicu lonjakan latensi (*latency spike*) di seluruh jaringan microservice Anda.
- **Microtask Loop-Lock**: Rekursi `process.nextTick` tanpa henti tidak akan melempar *Call Stack Overflow*, melainkan mematikan Event Loop secara senyap (*I/O starvation*), menyebabkan health check Kubernetes timeout dan pod direstart paksa (*crash loop*).
- **Megamorphic IC (Inline Caches)**: Menulis fungsi serbaguna yang menerima format objek acak dapat menurunkan performa eksekusi V8 dari status *JIT-optimized machine code* ke *interpreted byte code* yang lambat.

#### Apa Solusi Arsitekturnya?
1. Mengubah ukuran `UV_THREADPOOL_SIZE` secara sadar sesuai spesifikasi vCPU dan pola I/O.
2. Memisahkan *bound domain*:
   - Gunakan Stream dengan kontrol **Backpressure** untuk menangani streaming data.
   - Pindahkan operasi CPU intensif (enkripsi custom, machine learning, manipulasi gambar, parsing file biner besar) ke `worker_threads` pool atau N-API binary modules.
   - Hindari `dns.lookup` (threadpool-based) dan gunakan `dns.resolve*` (c-ares based, fully non-blocking).

---

### 5. How (Workflow Detail)

Berikut adalah alur eksekusi presisi saat sebuah request masuk ke REST/gRPC server berbasis Node.js:

```
[ Ingress Network Packet: TCP SYN / DATA ]
                    │
                    ▼
[ OS Kernel Network Buffer ]
                    │
                    ▼
[ OS Notification Mechanism: epoll_wait() / kevent() ]
                    │
                    ▼
[ Libuv Loop: Poll Phase wakes up ]
                    │
                    ▼
[ Read data from Socket FD into V8 TypedArray/Buffer ]
                    │
                    ▼
[ JavaScript Application Callback Triggered (e.g. req, res) ]
                    │
                    ├──── Memanggil CPU-Intensive task?
                    │         │
                    │         ├── YA  ──► Offload ke Worker Thread via MessagePort
                    │         │
                    │         └── TIDAK ──► Eksekusi sinkron langsung di V8 Call Stack
                    │
                    ├──── Menulis respons balik?
                    │         │
                    │         ▼
                    │   [ Stream Writable (Socket FD) ]
                    │   Cek return value: `res.write(chunk)`
                    │         ├─ true  : Buffer OS aman, lanjutkan.
                    │         └─ false : BACKPRESSURE! Tunggu event 'drain'.
                    │
                    ▼
[ Call Stack Kosong ] ──► [ Jalankan process.nextTick ] ──► [ Jalankan Promise Queue ]
                    │
                    ▼
[ Lanjut ke Fase Event Loop Berikutnya (Check -> Close -> Timers) ]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Dapur Restoran Bintang Lima

Bayangkan sebuah dapur restoran kelas dunia:
- **V8 Engine Call Stack**: **Satu Kepala Koki (Executive Chef)**. Sangat cepat, presisi, namun hanya bisa memotong atau meracik satu hal dalam satu waktu.
- **Event Loop (Libuv)**: **Manajer Dapur** yang memutar meja kerja secara berkala. Memastikan Koki hanya mengeksekusi instruksi yang bahannya sudah siap di meja.
- **Non-blocking Network I/O (epoll)**: **Bel Pesanan Elektronik**. Berdering otomatis saat ada pesanan masuk dari pelayan tanpa perlu koki berdiri di pintu restoran menunggu tamu.
- **Libuv Threadpool**: **4 Asisten Koki (Kitchen Porter)** di belakang dapur. Mereka menangani pekerjaan kasar yang memakan waktu: mengupas sekarung kentang (baca hard drive/`fs`) atau menumbuk rempah-rempah yang alot (`crypto`).
- **Worker Threads**: **Koki Tambahan Independen**. Punya pisau, papan potong, dan resep sendiri untuk memasak hidangan khusus tanpa mengganggu Kepala Koki utama.

```
+-------------------------------------------------------------------------------+
|                             RESTO NODE.JS                                     |
|                                                                               |
|  +--------------------+        MEMANGGIL         +-------------------------+  |
|  |   KEPALA KOKI      | -----------------------> |    4 ASISTEN KOKI       |  |
|  |    (V8 Engine)     | <----------------------- |   (Libuv Threadpool)    |  |
|  |                    |        SELESAI           |   fs, crypto, zlib      |  |
|  +---------^----------+                          +-------------------------+  |
|            |                                                                  |
|   MEMERIKSA PESANAN                                                           |
|            |                                                                  |
|  +---------v----------+                          +-------------------------+  |
|  |   MANAJER DAPUR    | <----------------------- |     BEL ELEKTRONIK      |  |
|  |   (Event Loop)     |      NOTIFIKASI I/O      |      (epoll/kqueue)     |  |
|  |                    |                          |    Incoming Sockets     |  |
|  +--------------------+                          +-------------------------+  |
+-------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Investigasi Deterministik Siklus Fase Event Loop
Jalankan skrip ini untuk melihat pembuktian urutan eksekusi fase Libuv dan Microtasks.

```javascript
import fs from 'node:fs';

console.log('1. [Synchronous] Root script start');

setTimeout(() => {
  console.log('2. [Timers Phase] setTimeout 0ms');
}, 0);

setImmediate(() => {
  console.log('3. [Check Phase] setImmediate');
});

process.nextTick(() => {
  console.log('4. [Microtask: nextTick] process.nextTick priority');
});

Promise.resolve().then(() => {
  console.log('5. [Microtask: Promise] Promise microtask');
});

// Operasi I/O untuk menggeser eksekusi ke Poll Phase
fs.readFile(new URL(import.meta.url), () => {
  console.log('6. [Poll Phase] I/O callback executed');

  setTimeout(() => {
    console.log('7. [Timers Phase from I/O] setTimeout in I/O');
  }, 0);

  setImmediate(() => {
    console.log('8. [Check Phase from I/O] setImmediate in I/O (Guaranteed Before Timers)');
  });

  process.nextTick(() => {
    console.log('9. [Microtask in I/O] process.nextTick inside I/O');
  });
});

console.log('10. [Synchronous] Root script end');
```

**Output Terminal:**
```text
1. [Synchronous] Root script start
10. [Synchronous] Root script end
4. [Microtask: nextTick] process.nextTick priority
5. [Microtask: Promise] Promise microtask
2. [Timers Phase] setTimeout 0ms
3. [Check Phase] setImmediate
6. [Poll Phase] I/O callback executed
9. [Microtask in I/O] process.nextTick inside I/O
8. [Check Phase from I/O] setImmediate in I/O (Guaranteed Before Timers)
7. [Timers Phase from I/O] setTimeout in I/O
```
*Catatan Arsitektur: Di dalam callback I/O (`fs.readFile`), `setImmediate` SELALU dieksekusi sebelum `setTimeout(0)`, karena siklus loop bergerak langsung dari fase Poll ke Check sebelum kembali memutar ke Timers.*

---

#### B. Practical Example: Production-Grade Resilient Worker Thread Pool
Pola enterprise untuk mengeksekusi operasi komputasi berat tanpa memblokir Event Loop, lengkap dengan *lifecycle tracking*, pembatasan ukuran pool (*bounded queues*), penanganan error terisolasi, dan timeout cancellation.

```javascript
// WorkerPool.js
import { Worker } from 'node:worker_threads';
import os from 'node:os';
import { AsyncResource } from 'node:async_hooks';

class PoolTaskError extends Error {
  constructor(message, originalError) {
    super(message);
    this.name = 'PoolTaskError';
    this.stack = originalError?.stack;
  }
}

export class ProductionWorkerPool {
  #workers = [];
  #freeWorkers = [];
  #queue = [];
  #workerScript;
  #poolSize;
  #taskTimeoutMs;

  constructor(workerScript, options = {}) {
    this.#workerScript = workerScript;
    this.#poolSize = options.poolSize || Math.max(1, os.cpus().length - 1);
    this.#taskTimeoutMs = options.taskTimeoutMs || 30_000;
    this.#initialize();
  }

  #initialize() {
    for (let i = 0; i < this.#poolSize; i++) {
      this.#spawnWorker();
    }
  }

  #spawnWorker() {
    const worker = new Worker(this.#workerScript);

    worker.on('message', ({ result, error, taskId }) => {
      const task = worker.currentTask;
      if (!task || task.id !== taskId) return;

      clearTimeout(task.timeoutHandle);
      worker.currentTask = null;
      this.#freeWorkers.push(worker);

      if (error) {
        task.reject(new PoolTaskError(error.message, error));
      } else {
        task.resolve(result);
      }

      this.#processNext();
    });

    worker.on('error', (err) => {
      if (worker.currentTask) {
        clearTimeout(worker.currentTask.timeoutHandle);
        worker.currentTask.reject(new PoolTaskError('Worker crashed mid-execution', err));
      }
      this.#removeWorker(worker);
      this.#spawnWorker(); // Pulihkan worker yang mati secara mandiri
    });

    worker.unref(); // Cegah worker mencegah proses Node.js exit jika queue kosong
    this.#workers.push(worker);
    this.#freeWorkers.push(worker);
  }

  #removeWorker(worker) {
    this.#workers = this.#workers.filter((w) => w !== worker);
    this.#freeWorkers = this.#freeWorkers.filter((w) => w !== worker);
    worker.terminate();
  }

  execute(data) {
    return new Promise((resolve, reject) => {
      const taskId = crypto.randomUUID();
      const task = {
        id: taskId,
        data,
        resolve,
        reject,
        asyncResource: new AsyncResource('WorkerPoolTask'),
        timeoutHandle: null,
      };

      this.#queue.push(task);
      this.#processNext();
    });
  }

  #processNext() {
    if (this.#queue.length === 0 || this.#freeWorkers.length === 0) {
      return;
    }

    const worker = this.#freeWorkers.pop();
    const task = this.#queue.shift();
    worker.ref();
    worker.currentTask = task;

    task.timeoutHandle = setTimeout(() => {
      task.reject(new Error(`Task ${task.id} timed out after ${this.#taskTimeoutMs}ms`));
      this.#removeWorker(worker);
      this.#spawnWorker();
    }, this.#taskTimeoutMs);

    task.asyncResource.runInAsyncScope(() => {
      worker.postMessage({ taskId: task.id, data: task.data });
    });
  }

  async destroy() {
    await Promise.all(this.#workers.map((w) => w.terminate()));
    this.#workers = [];
    this.#freeWorkers = [];
    this.#queue = [];
  }
}
```

```javascript
// worker-task.js (Script yang dieksekusi oleh thread)
import { parentPort } from 'node:worker_threads';
import crypto from 'node:crypto';

parentPort.on('message', ({ taskId, data }) => {
  try {
    // Simulasi komputasi CPU intensif: Key Derivation scrypt sinkron
    const derivedKey = crypto.scryptSync(data.payload, 'production-salt-enterprise', 64);
    parentPort.postMessage({
      taskId,
      result: { hash: derivedKey.toString('hex') },
    });
  } catch (err) {
    parentPort.postMessage({
      taskId,
      error: { message: err.message, stack: err.stack },
    });
  }
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Arsitektur Gateway Pembayaran FinTech (50.000 RPS)
Sebuah gerbang pembayaran FinTech mengalami insiden skala prioritas P1: Selama flash-sale e-commerce, rata-rata latensi p99 meroket dari **45ms ke 12.800ms**. Metrik pemanfaatan CPU server hanya 35%, namun ribuan request mengalami *Gateway Timeout (504)*, dan health-probe dari orchestrator Kubernetes gagal, menyebabkan *cascading pod restart*.

#### Analisis Masalah Root Cause
1. **Threadpool Exhaustion**: Gateway memvalidasi tanda tangan kriptografi Payload Webhook menggunakan `crypto.pbkdf2` bawaan (yang menggunakan Libuv Threadpool).
2. **DNS Blocking**: Setiap webhook memicu HTTP request outbound menggunakan `axios` bawaan yang menyelesaikan domain via `dns.lookup` (bergantung secara eksklusif pada Libuv Threadpool).
3. **Konsekuensi**: Default `UV_THREADPOOL_SIZE=4` jenuh total oleh tugas komputasi PBKDF2. Akibatnya, request I/O jaringan internal tertahan di fase Poll, menciptakan ilusi sistem lambat meski kapasitas vCPU server masih sangat besar.

#### Solusi Arsitektural yang Diimplementasikan
1. Mengubah DNS lookup default ke *c-ares asynchronous DNS resolver* tanpa threadpool via `dns.promises.resolve*` atau mengonfigurasi `dns.setServers()`.
2. Melakukan isolasi CPU-intensive cryptography ke Node-API C++ Module terdedikasi atau Threadpool terisolasi melalui `worker_threads`.
3. Memperbaiki *memory backpressure* pada ingress logging JSON.

#### Implementasi Solusi (Arsitektur Jaringan & Stream Anti-Backpressure)

```javascript
// GatewayHttpClient.js
import http from 'node:http';
import https from 'node:https';
import dns from 'node:dns';

// Eliminasi ketergantungan Threadpool pada resolving DNS
dns.setDefaultResultOrder('ipv4first');

// Konfigurasi Agent dengan Keep-Alive dan DNS Caching Socket Pool
export const enterpriseHttpAgent = new https.Agent({
  keepAlive: true,
  keepAliveMsecs: 10_000,
  maxSockets: 1000,
  maxFreeSockets: 256,
  timeout: 5000,
  // Menggunakan custom lookup resolver untuk bypass uv_getaddrinfo threadpool
  lookup: (hostname, options, callback) => {
    dns.resolve4(hostname, (err, addresses) => {
      if (err) return callback(err);
      // Format response kompatibel dengan requirement signature lookup Node.js
      callback(null, addresses[0], 4);
    });
  },
});
```

```javascript
// SecureFastPipeline.js - Menangani log streaming bervolume tinggi dengan Zero-Loss Backpressure
import { Transform } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import fs from 'node:fs';

export class HighThroughputAuditPipeline {
  #outputSink;

  constructor(auditFilePath) {
    this.#outputSink = fs.createWriteStream(auditFilePath, {
      flags: 'a',
      highWaterMark: 1024 * 1024, // 1MB buffer internal kernel chunk
    });
  }

  async writeSafeAuditLog(logStreamSource) {
    const sanitizeStream = new Transform({
      objectMode: true,
      highWaterMark: 500, // Menahan maks 500 objek di memory stack sebelum memberi sinyal pause
      transform(chunk, encoding, callback) {
        try {
          // Sanitasi PII (Personally Identifiable Information)
          delete chunk.pan;
          delete chunk.cvv;
          chunk.processedAt = Date.now();
          this.push(JSON.stringify(chunk) + '\n');
          callback();
        } catch (err) {
          callback(err);
        }
      },
    });

    // Pipeline secara otomatis menangani Backpressure dan penutupan resource stream secara aman
    await pipeline(logStreamSource, sanitizeStream, this.#outputSink, { end: false });
  }
}
```

---

### 9. Trade-offs

| Pendekatan Arsitektur | Keuntungan | Kerugian & Batasan | Implikasi Latensi & Biaya |
| :--- | :--- | :--- | :--- |
| **Worker Threads** | Mampu mengeksekusi komputasi CPU murni tanpa memblokir thread event loop utama. | Memory overhead (~30MB per worker V8 isolate), biaya serilisasi/deserialisasi cloning data antar thread via Structured Clone Algorithm. | **Latensi**: Rendah untuk komputasi berat, overhead startup tinggi.<br>**Biaya**: Konsumsi RAM tinggi jika pool terlalu besar. |
| **SharedArrayBuffer & Atomics** | *Zero-copy data sharing* antar worker threads dengan performa kecepatan memori C. | Risiko *race condition*, kompleksitas memori tingkat rendah (*memory synchronization barriers*), tidak bisa menyimpan referensi pointer object V8 kompleks. | **Latensi**: Sangat rendah (sub-millisecond transfer).<br>**Biaya**: Biaya rekayasa perangkat lunak sangat tinggi (*code maintenance*). |
| **N-API / C++ Addons** | Kecepatan bare-metal, akses langsung ke kernel primitives dan instruksi SIMD CPU (AVX-512). | Kehilangan proteksi sandboxing V8. Memory leak C++ akan membunuh seluruh proses tanpa jejak stack trace JavaScript. Kompilasi bergantung OS/arsitektur mesin. | **Latensi**: Ultra-rendah.<br>**Biaya**: Biaya portabilitas tinggi pada multi-platform CI/CD pipelines. |
| **Cluster Module (Process Fork)** | Zero-memory leak propagation antar request, pemanfaatan penuh semua core CPU server via IPC OS. | Tidak ada *memory state sharing* antar instance (membutuhkan Redis untuk session/state), konsumsi RAM melonjak linier sesuai jumlah instance process. | **Latensi**: Stabil, throughput berlipat ganda.<br>**Biaya**: Peningkatan pemanfaatan RAM per VM/Container. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Event Loop Starvation akibat JSON Parsing Masif
- **Gejala**: APM mendeteksi lonjakan latency tiba-tiba di seluruh endpoint saat request dengan body JSON > 20MB diterima.
- **Penyebab**: `JSON.parse()` dan `JSON.stringify()` bekerja secara **sinkron mutlak** di main thread V8. Selama parsing 50ms, sistem tidak merespons request client manapun.
- **Troubleshooting**: Gunakan module `@nearform/bubbleprof` atau pasang `perf_hooks` untuk mengukur durasi loop delay:
```javascript
import { monitorEventLoopDelay } from 'node:perf_hooks';

const histogram = monitorEventLoopDelay({ resolution: 20 });
histogram.enable();

setInterval(() => {
  const p99 = histogram.percentile(99) / 1e6; // Milidetik
  if (p99 > 50) {
    console.error(`CRITICAL: Event loop delay p99 reached ${p99.toFixed(2)}ms!`);
  }
  histogram.reset();
}, 5000);
```
- **Solusi**: Alirkan payload besar menggunakan Streaming JSON Parsers (`stream-json`) atau proses di background worker jika payload melebihi ukuran batas wajar (> 1MB).

#### Kesalahan 2: Unbounded Memory Leak via Closure Event Listeners
- **Gejala**: Penggunaan RSS (*Resident Set Size*) pod terus bertambah hingga dibunuh oleh Kubernetes OOMKilled (*Exit Code 137*).
- **Penyebab**: Mendaftarkan event listener pada objek singleton tanpa pembersihan (`removeListener`).
```javascript
// CONTOH SALAH
class MetricsTracker {
  trackUserAction(userEventEmitter) {
    // FATAL: Callback menahan referensi instance MetricsTracker selamanya
    userEventEmitter.on('action', (data) => {
      this.recordMetrics(data);
    });
  }
}
```
- **Solusi**: Gunakan `AbortController` (tersedia sejak Node.js 16+) untuk mendaftarkan listener yang terikat siklus hidup request:
```javascript
// IMPLEMENTASI AMAN
const ac = new AbortController();
userEventEmitter.on('action', (data) => this.recordMetrics(data), {
  signal: ac.signal,
});

// Bersihkan listener ketika request selesai
res.on('finish', () => ac.abort());
```

#### Kesalahan 3: Threadpool Exhaustion karena Konfigurasi Runtime yang Salah
- **Gejala**: Menyetel `process.env.UV_THREADPOOL_SIZE = 64;` di dalam kode JavaScript aplikasi runtime.
- **Penyebab**: Libuv menginisialisasi thread pool **sebelum** V8 engine mengeksekusi baris JavaScript pertama. Pernyataan tersebut dieksekusi terlambat dan diabaikan total oleh Libuv.
- **Solusi**: Variabel lingkungan harus diinjeksikan pada level OS shell sebelum proses Node.js dijalankan:
```bash
UV_THREADPOOL_SIZE=64 node server.js
```

---

### 11. Best Practices (Production Checklist)

#### V8 & Runtime Performance Tuning
- [ ] Atur batas memori Old Space V8 secara eksplisit sesuai alokasi container:  
  `node --max-old-space-size=4096 server.js` (misalnya untuk container 6GB).
- [ ] Jangan pernah memanggil `delete obj.property`. Alokasikan objek baru atau setel nilainya ke `undefined` agar Shape / Hidden Class V8 tetap stabil.
- [ ] Gunakan `node:crypto` asynchronous method (`crypto.pbkdf2` dengan callback/promise) daripada sinkron (`crypto.pbkdf2Sync`) di thread utama.

#### Backpressure & Streaming Safety
- [ ] Selalu evaluasi nilai kembalian `stream.write(chunk)`. Jika mengembalikan nilai `false`, tangguhkan push data hingga event `'drain'` ditembakkan.
- [ ] Selalu gunakan `stream.pipeline` atau `stream/promises` alih-alih `.pipe()`. Method `.pipe()` mentah **tidak meneruskan error handling**, berpotensi membocorkan Memory / File Descriptors saat koneksi putus tiba-tiba.

#### Enterprise Observability & Resilience
- [ ] Pasang global tracking untuk unhandled rejections dengan logging detail sebelum terminasi anggun (*Graceful Shutdown*):
```javascript
process.on('unhandledRejection', (reason, promise) => {
  logger.fatal({ err: reason }, 'Unhandled Rejection at Promise');
  process.exitCode = 1;
  gracefulShutdown();
});
```
- [ ] Lacak konteks distributed tracing melintasi boundaries async tanpa passing variabel manual menggunakan `AsyncLocalStorage`.

---

### 12. Hands-on Practice

Buat repositori lokal untuk eksperimen mendalam ini. Simpan semua file di direktori `hands-on/m02/`.

#### Langkah 1: Setup Workspace & Memory Profiling Lab
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm pkg set type="module"
```

#### Langkah 2: Buat Skrip Eksperimen `backpressure-lab.js`
Skrip ini mereplikasi memory leak akibat penanganan backpressure yang buruk versus penanganan stream yang benar.

```javascript
// hands-on/m02/backpressure-lab.js
import fs from 'node:fs';
import { Readable } from 'node:stream';

const OUTPUT_FILE = './output-dump.dat';
const TOTAL_CHUNKS = 5_000_000;

// Sumber stream cepat buatan: Menghasilkan data instan
class FastDataSource extends Readable {
  #count = 0;
  _read(size) {
    if (this.#count >= TOTAL_CHUNKS) {
      this.push(null);
      return;
    }
    const chunk = Buffer.alloc(1024, 'A'); // 1KB per chunk
    this.#count++;
    this.push(chunk);
  }
}

async function runUnsafeStream() {
  console.log('--- Menjalankan Unsafe Stream (Mengabaikan Backpressure) ---');
  const source = new FastDataSource();
  const dest = fs.createWriteStream(OUTPUT_FILE, { highWaterMark: 16 * 1024 });

  const initialMem = process.memoryUsage().heapUsed / 1024 / 1024;
  console.log(`Initial Heap: ${initialMem.toFixed(2)} MB`);

  let drainedEvents = 0;
  dest.on('drain', () => drainedEvents++);

  source.on('data', (chunk) => {
    // BURUK: Menulis tanpa peduli apakah buffer tujuan penuh
    const canAcceptMore = dest.write(chunk);
    if (!canAcceptMore) {
      // Buffer OS / internal Node.js jenuh, data ditumpuk di RAM V8!
    }
  });

  source.on('end', () => {
    dest.end();
    const peakMem = process.memoryUsage().heapUsed / 1024 / 1024;
    console.log(`Peak Heap (Unsafe): ${peakMem.toFixed(2)} MB`);
    console.log(`Drain events triggered: ${drainedEvents}`);
  });
}

// Eksekusi
runUnsafeStream();
```

#### Langkah 3: Uji Skrip & Observasi
Jalankan skrip dengan inspeksi V8 Memory:
```bash
node --max-old-space-size=128 backpressure-lab.js
```
*Amati lonjakan penggunaan memori heap yang signifikan. Data menumpuk di buffer internal heap karena consumer I/O disk lebih lambat daripada produksi CPU reader.*

#### Langkah 4: Perbaiki Skrip Menggunakan `pipeline`
Ubah bagian eksekusi untuk menggunakan `pipeline` bawaan:

```javascript
// hands-on/m02/backpressure-fix.js
import { pipeline } from 'node:stream/promises';
import fs from 'node:fs';
import { Readable } from 'node:stream';

class FastDataSource extends Readable {
  #count = 0;
  _read(size) {
    if (this.#count >= 5_000_000) {
      this.push(null);
      return;
    }
    this.#count++;
    this.push(Buffer.alloc(1024, 'A'));
  }
}

async function runSafeStream() {
  console.log('--- Menjalankan Safe Stream dengan Auto-Backpressure ---');
  const source = new FastDataSource();
  const dest = fs.createWriteStream('./output-safe.dat', { highWaterMark: 16 * 1024 });

  const startMem = process.memoryUsage().heapUsed / 1024 / 1024;
  console.log(`Start Heap: ${startMem.toFixed(2)} MB`);

  await pipeline(source, dest);

  const endMem = process.memoryUsage().heapUsed / 1024 / 1024;
  console.log(`End Heap (Safe): ${endMem.toFixed(2)} MB`);
  console.log('Streaming selesai dengan penggunaan memori yang stabil (flat line memory).');
}

runSafeStream().catch(console.error);
```
Jalankan skrip perbaikan:
```bash
node --max-old-space-size=128 backpressure-fix.js
```

---

### 13. Exercise

#### Level Easy
Buat file `exercise-easy.js`. Buat sebuah fungsi asynchronous yang membuktikan bahwa callback `Promise.resolve().then(...)` selalu dieksekusi lebih dulu daripada `setTimeout(..., 0)` dan `setImmediate(...)`, bagaimanapun posisi pemanggilannya dalam kode sinkron. Tampilkan log dengan urutan fase yang valid ke console.

#### Level Medium
Buat file `exercise-medium.js`. Buat implementasi server HTTP sederhana (`node:http`) yang memiliki endpoint `/compute`. Endpoint ini menerima angka query `n` dan menghitung bilangan Fibonacci secara rekursif (`O(2^N)`). 
- Jika dipanggil dengan angka besar (`n=45`), buktikan endpoint `/health` tetap merespons dengan status `200 OK` dalam waktu kurang dari 5ms dengan mendelegasikan komputasi Fibonacci tersebut ke `node:worker_threads`.

#### Level Hard
Buat file `exercise-hard.js`. Implementasikan custom stream `Transform` bernama `EncryptedChunkTransformer` yang:
1. Menerima chunk buffer stream biner.
2. Melakukan enkripsi AES-256-GCM pada setiap chunk data secara independen.
3. Mengatur backpressure secara manual tanpa library pihak ketiga: Jika internal buffer transformer mencapai limit `highWaterMark`, tahan pembacaan stream sumber (`this.push` mengembalikan false), dan pulihkan stream kembali secara manual saat output buffer telah kosong (`_read` triggered).

---

### 14. Challenge

**Skenario Sistem: "Zero-Downtime High-Resilience Plugin Sandbox Platform"**

Rancang arsitektur sistem Node.js backend yang bertindak sebagai runner untuk script eksternal (untrusted third-party dynamic plugins):

**Kebutuhan Spesifikasi Teknis:**
1. **CPU & Event Loop Isolation**: Setiap plugin pihak ketiga yang dieksekusi harus berjalan di isolated context thread. Jika script plugin memiliki *infinite loop* (`while(true) {}`), thread utama Node.js serta plugin lain **TIDAK BOLEH** terganggu atau terhenti.
2. **Deterministic Hard Timeout**: Jika plugin berjalan lebih lama dari 2500ms, sandbox harus menghentikan (*terminate*) eksekusi plugin tersebut secara paksa, melepaskan seluruh alokasi resource memori, dan mengembalikan HTTP error code `504 Gateway Timeout` ke klien.
3. **Memory Hard Cap**: Batasi penggunaan heap memory maksimal untuk setiap eksekutor plugin sebesar **64 MB**. Jika plugin mengalokasikan memori melebihi batas ini, tangkap kegagalan tersebut sebelum memicu container crash (tangkap OOM signal pada worker isolate).
4. **Context Tracing**: Gunakan `AsyncLocalStorage` untuk meneruskan Transaction ID dari incoming HTTP request hingga ke dalam worker execution logs tanpa mengubah parameter fungsi plugin yang dieksekusi.

*Tantangan ini tidak boleh diselesaikan dengan menggunakan dependency eksternal; gunakan native primitives Node.js (`node:worker_threads`, `node:vm`, `node:async_hooks`, `node:http`).*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual Singkat)
1. Fase manakah dalam Libuv Event Loop yang bertugas khusus mengeksekusi callback dari `setImmediate()`?
   - A. Poll Phase
   - B. Timers Phase
   - C. Check Phase
   - D. Pending Callbacks Phase

2. Di manakah memori untuk raw Buffer (`Buffer.alloc(...)`) dialokasikan pada Node.js arsitektur 64-bit?
   - A. Di dalam V8 New Space
   - B. Di luar V8 Heap (Off-Heap / C++ Memory ArrayBuffer via `ArrayBufferAllocator`)
   - C. Di dalam V8 Code Space
   - D. Di dalam V8 Map Space

3. Apa perbedaan fundamental antara `process.nextTick()` dan `setImmediate()`?
   - A. `process.nextTick()` berjalan di Check Phase, `setImmediate()` di Timers Phase.
   - B. `process.nextTick()` dieksekusi segera setelah operasi sinkron saat ini selesai sebelum event loop melanjutkan ke fase berikutnya; `setImmediate()` dieksekusi pada Check Phase dari event loop.
   - C. Keduanya identik, hanya berbeda penamaan alias.
   - D. `setImmediate()` memiliki prioritas lebih tinggi daripada `process.nextTick()`.

4. Berapa jumlah alokasi default thread pada Libuv Threadpool jika Anda tidak mengonfigurasi environment variable sama sekali?
   - A. 1
   - B. Sama dengan jumlah core vCPU mesin
   - C. 4
   - D. 8

5. Manakah dari modul berikut yang operasinya **TIDAK** menggunakan Libuv Threadpool sama sekali?
   - A. `fs.promises.readFile`
   - B. `crypto.pbkdf2`
   - C. `zlib.gzip`
   - D. `net.createServer` / Network Sockets

#### Bagian 2: Intermediate (Analisis Arsitektur)
6. Jelaskan apa yang terjadi pada *Garbage Collector (Scavenger)* V8 jika sebuah aplikasi terus-menerus membuat objek yang bertahan lebih dari dua kali siklus Scavenging!
7. Mengapa penggunaan kata kunci `delete obj.prop` dianggap sebagai *anti-pattern* performa pada arsitektur engine V8 TurboFan?
8. Mengapa operasi pemanggilan `dns.lookup('api.stripe.com')` dapat menyebabkan degradasi performa throughput pada aplikasi file streaming yang menggunakan `fs.readFile`?
9. Apa yang terjadi jika sebuah stream `Readable` memompa data jauh lebih cepat daripada kemampuan `Writable` stream menulis data ke storage, dan kode Anda menggunakan event `.on('data', chunk => dest.write(chunk))` tanpa mengevaluasi nilai kembaliannya?
10. Bagaimana `AsyncLocalStorage` mempertahankan context tracing secara konsisten melintasi *asynchronous execution hops* (seperti transisi dari network callback ke database query)?

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario A**: Layanan API Node.js Anda mengalami lonjakan RSS Memory secara konstan dari 200MB menjadi 4GB dalam durasi 48 jam, tetapi heap memory yang dilaporkan oleh `v8.getHeapStatistics().used_heap_size` tetap stabil di angka 120MB. Komponen arsitektur manakah yang kemungkinan besar bocor (*leaking*), dan instrumen apa yang Anda gunakan untuk mendiagnosisnya?
12. **Skenario B**: Pada sistem audit log terdistribusi, Anda memiliki antrean `process.nextTick()` rekursif yang memproses pembersihan string. Health check HTTP Kubernetes `/livez` yang dieksekusi tiap 5 detik tiba-tiba timeout secara konsisten sehingga container Anda direstart paksa berulang-ulang, padahal utilisasi CPU server masih 20%. Jelaskan kegagalan mekanika internal yang terjadi!
13. **Skenario C**: Sebuah tim microservice mengganti implementasi worker thread mereka dengan membuat instance `new Worker()` baru di setiap ada request REST HTTP yang masuk untuk memproses enkripsi token. Pada 500 RPS, server langsung melempar error `UV_EMFILE` atau mengalami crash total. Analisis kesalahan fatal arsitektural ini dan berikan solusinya!

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian 1: Basic
1. **C. Check Phase**. Sesuai spesifikasi state machine Libuv, check phase didedikasikan mutlak untuk pemanggilan callback `setImmediate`.
2. **B. Di luar V8 Heap (Off-Heap / C++ Memory ArrayBuffer)**. Buffer dialokasikan secara native di C++ memory agar tidak membebani V8 Garbage Collector secara langsung saat memanipulasi data stream biner masif.
3. **B**. `process.nextTick` masuk ke Microtask Queue khusus yang dieksekusi secara instan segera setelah stack eksekusi saat ini mengosongkan kontrol, memotong antrean semua fase Event Loop reguler. `setImmediate` harus menunggu giliran hingga loop mencapai Check Phase.
4. **C. 4**. Default `UV_THREADPOOL_SIZE` dari libuv adalah 4.
5. **D. `net.createServer` / Network Sockets**. Operasi TCP/UDP network sepenuhnya ditangani secara asynchronous non-blocking oleh kernel event demultiplexer OS (`epoll`/`kqueue`/`IOCP`), tanpa menggunakan Libuv threadpool.

#### Bagian 2: Intermediate
6. Objek yang bertahan lebih dari dua kali siklus Scavenging akan dipromosikan (*tenured*) dari New Space (Semi-Space To-Space) ke Old Space. Di Old Space, objek ini akan diperiksa oleh Major GC (Mark-Sweep-Compact) yang memiliki frekuensi eksekusi lebih jarang namun memakan komputasi STW (Stop-The-World) lebih tinggi jika terjadi fragmentasi.
7. V8 menyematkan *Hidden Class (Shape)* pada objek untuk mengoptimasi kompilasi mesin (Inline Caching). Penggunaan `delete` merusak stabilitas Shape tersebut secara dinamis, memaksa V8 mengalihkan objek ke mode lambat *Dictionary Mode* (hash table lookups biasa) dan melakukan deoptimasi kompilasi JIT.
8. Karena `dns.lookup` secara internal memanggil fungsi sistem POSIX sinkron `getaddrinfo(3)`, yang dieksekusi di dalam **Libuv Threadpool**. Operasi `fs.readFile` juga dieksekusi di dalam Libuv Threadpool yang sama. Jika request DNS tinggi, keempat thread pekerja Libuv akan sibuk, membuat antrean `fs.readFile` tertahan (*starved*).
9. Terjadi kegagalan penanganan **Backpressure**. Chunk data yang tidak dapat diterima langsung oleh disk/network OS buffer akan dialokasikan dan ditampung ke dalam RAM JavaScript engine tanpa batas. Ini menyebabkan lonjakan penggunaan heap memory secara liar hingga memicu crash proses akibat `JavaScript heap out of memory`.
10. `AsyncLocalStorage` dibangun di atas native C++ core API `AsyncWrap` dan `executionAsyncId()`. Node.js melacak hubungan hirarki *Parent-Child* dari setiap resource asynchronous (seperti socket, timer, promise handle) dan secara otomatis memulihkan pointer context penyimpanan memori yang tepat ketika callback dari async task tersebut didorong kembali ke Call Stack.

#### Bagian 3: Skenario Kasus Produksi
11. **Analisis Skenario A**: Kebocoran terjadi di **Native/Off-Heap Memory**, bukan di V8 Managed Heap. Sumber masalah umumnya berasal dari unclosed C++ Addons, alokasi `Buffer` liar yang tidak dilepas referensinya, atau kompresi streaming `zlib` yang tidak di-close secara eksplisit. Cara mendiagnosis: Gunakan tools native OS memory profiler seperti **Valgrind**, **Jemalloc / Malloc-Trace**, atau flag `node --trace-gc` serta periksa metrik `process.memoryUsage().arrayBuffers` dan `process.memoryUsage().external`.
12. **Analisis Skenario B**: Terjadi **Event Loop Starvation akibat Microtask Starvation**. `process.nextTick` memiliki prioritas tak terbatas di atas Event Loop. Jika dipanggil secara rekursif tak berujung, Event Loop **tidak akan pernah bisa maju** ke fase Poll untuk menerima incoming connection TCP health check HTTP dari kubelet Kubernetes. Akibatnya port probe tidak membalas dan pod ditandai mati oleh cluster.
13. **Analisis Skenario C**: `new Worker()` menginisialisasi satu V8 Isolate baru lengkap dengan libuv instance, context heap V8 tersendiri, dan thread native OS baru. Membuat thread per request pada 500 RPS memicu *Resource Exhaustion*: sistem kehabisan native memory overhead dan File Descriptors OS (`UV_EMFILE`). **Solusi**: Terapkan pola **Worker Thread Pool** dengan ukuran statis (misal: sejumlah `vCPU - 1`) dan gunakan bounded task queue untuk mendistribusikan pekerjaan komputasi enkripsi secara terkontrol.

---

### 16. Summary

```
                      ARSITEKTUR PRODUKSI NODE.JS
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│   V8 ENGINE                     LIBUV LAYER              OS KERNEL     │
│  ┌──────────────────────┐      ┌─────────────┐          ┌────────────┐ │
│  │ Call Stack (Sync)    │ ───► │ Event Loop  │ ◄──────► │ epoll /    │ │
│  └──────────────────────┘      │ (6 Phases)  │          │ kqueue     │ │
│            │                   └─────────────┘          │ (Sockets)  │ │
│            ▼                          │                 └────────────┘ │
│  ┌──────────────────────┐             ▼                        │       │
│  │ Microtask Queues     │      ┌─────────────┐                 │       │
│  │ - nextTick           │      │ Threadpool  │                 │       │
│  │ - Promises           │      │ (fs/crypto) │                 │       │
│  └──────────────────────┘      └─────────────┘                 │       │
│            │                          │                        │       │
│            ▼                          ▼                        ▼       │
│    Memory Management          Worker Threads           Non-blocking    │
│    (New/Old Space GC)         (CPU Isolation)          Network I/O     │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

Arsitektur Node.js enterprise menuntut eliminasi asumsi bahwa runtime ini "sepenuhnya single-threaded" atau "bebas konfigurasi memori":
1. **Pemisahan Jalur Komputasi**: Beban I/O Jaringan diserahkan langsung ke kernel event demultiplexer OS tanpa menyentuh threadpool; beban File I/O dan Built-in Crypto menggunakan Libuv Threadpool terdedikasi; komputasi berat murni (CPU-bound) **wajib** dipindahkan ke `worker_threads` terisolasi atau diimplementasikan pada native microservices eksternal.
2. **Kedisiplinan Event Loop**: Mikro-tugas (`nextTick` dan Promises) berjalan dengan prioritas mendahului transisi fase Event Loop. Hindari rekursi async tanpa pelepasan kendali ke macro-task loop.
3. **Integritas Aliran Data**: Backpressure bukanlah fitur opsional, melainkan kebutuhan wajib untuk stabilitas memori. Gunakan `stream.pipeline` untuk menggaransi keamanan memory footprint dan penutupan resource stream secara deterministik di produksi.