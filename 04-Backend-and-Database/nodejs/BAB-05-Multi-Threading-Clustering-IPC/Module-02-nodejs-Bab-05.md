# KURIKULUM TEKNIK TINGKAT ENTERPRISE: NODE.JS
## Kategori: 04-Backend-and-Database
### BAB-05: Multi-Threading, Clustering, dan Inter-Process Communication (IPC)
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik pada tingkat Senior Backend Engineer / Systems Architect diharapkan mampu:
- Membedah arsitektur internal Node.js terkait isolasi memori V8, thread pool internal `libuv`, runtime `worker_threads`, dan master-worker multiprocessing via module `node:cluster`.
- Mengimplementasikan pola zero-downtime deployment (rolling restart / graceful reload) pada cluster multi-core berbasis sinyal OS (`SIGINT`, `SIGTERM`, `SIGHUP`).
- Merancang dan membangun arsitektur pertukaran data performa tinggi menggunakan Inter-Process Communication (IPC), Unix Domain Sockets, serta zero-copy memory concurrency via `SharedArrayBuffer` dan `Atomics`.
- Mendiagnosis dan menyelesaikan masalah kongkurensi tingkat rendah seperti thread starvation, memory leak di level isolate, IPC backpressure, dan race conditions pada shared memory.
- Menentukan strategi pembagian beban kerja komputasi berat (CPU-bound) vs I/O-bound menggunakan hybrid multi-process dan thread-pooling pada infrastruktur bare-metal, VM, maupun container (Docker/K8s).

---

### 2. Prerequisite
Sebelum mendalami modul ini, engineer wajib memiliki pemahaman mendalam tentang:
- **Node.js Core Internals**: Event Loop, Microtask Queue (Promises, `process.nextTick`), Macrotask Queue (`timers`, `setImmediate`), dan libuv abstract I/O layer.
- **Operating Systems Concepts**: Virtual Memory, Process vs. Thread, Context Switching Overhead, POSIX Signals, IPC mechanisms (Pipes, Sockets, Shared Memory), CPU Affinity, dan File Descriptor inheritance (`SCM_RIGHTS`).
- **Modern JavaScript/TypeScript**: ES Modules, TypedArrays (`Uint8Array`, `Int32Array`), TypedArray byte layouts, ArrayBuffer allocation semantics.

---

### 3. Concept & Internal Architecture (Mendalam)

Node.js secara default mengeksekusi kode JavaScript pada satu thread utama (Single-Threaded Event Loop) yang berjalan di atas satu V8 Isolate. Namun, untuk arsitektur skala enterprise, asumsi "Node.js adalah single-threaded" merupakan kekeliruan fatal. Node.js memiliki tiga lapisan kongkurensi:

```
+-----------------------------------------------------------------------+
|                            Node.js Process                            |
|                                                                       |
|  +---------------------------+       +-----------------------------+  |
|  |     V8 Engine Isolate     |       |    libuv Worker Pool        |  |
|  |  (Main JS Execution Thread)| <---> | (Default: 4 threads, POSIX) |  |
|  |  Heap / Call Stack / GC   |       | (fs, dns, crypto, zlib)     |  |
|  +---------------------------+       +-----------------------------+  |
|               ^                                                       |
|               | (MessagePort / SharedArrayBuffer)                     |
|               v                                                       |
|  +-----------------------------------------------------------------+  |
|  |                   worker_threads Module                         |  |
|  |  +-----------------------+           +-----------------------+  |  |
|  |  |   V8 Isolate #1       |           |   V8 Isolate #2       |  |  |
|  |  | (Independent Heap/GC) |           | (Independent Heap/GC) |  |  |
|  |  +-----------------------+           +-----------------------+  |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

#### A. Node.js `cluster` Module & Socket Passing Internals
Modul `node:cluster` bekerja berbasis multiprocessing POSIX (`fork()`). Di Linux, `cluster` memanfaatkan implementasi internal libuv untuk membagi trafik koneksi masuk antar-proses pekerja (Worker Processes) melalui dua pendekatan:
1. **Round-Robin Approach (Default di semua platform non-Windows)**: Master process membuat TCP listen socket (`server.listen()`). Ketika koneksi masuk (`accept()`), master process mendistribusikan file descriptor TCP handoff tersebut ke worker process melalui IPC channel internal berbasis Unix Domain Socket (`net.Socket` bawaan) menggunakan payload `SCM_RIGHTS`.
2. **Shared Socket Approach**: Master menyerahkan listening socket langsung kepada semua worker, dan kernel OS mengatur load balancing via socket multiplexing (mirip dengan implementasi `SO_REUSEPORT`). Namun, mode ini kerap memicu *thundering herd problem* di mana OS membangkitkan semua worker secara bersamaan untuk satu event koneksi, menyebabkan lonjakan CPU yang tidak efisien.

#### B. Worker Threads vs. Multi-Process
- **`cluster` (Multi-Process)**: Setiap worker berjalan di proses OS yang terpisah. Memiliki Process ID (PID) unik, memori terisolasi penuh (tidak ada heap sharing), dan garbage collection (GC) independen. Kegagalan (segfault/unhandled rejection) di satu worker tidak membunuh proses worker lain.
- **`worker_threads` (Multi-Threading)**: Berjalan di dalam satu proses OS yang sama. Setiap thread memiliki V8 Isolate sendiri, Event Loop sendiri, dan libuv instance sendiri, tetapi berbagi process space yang sama (PID sama). Thread-thread ini dapat berbagi memori secara zero-copy menggunakan `SharedArrayBuffer`. Jika terjadi fatal crash/abort pada native layer di satu thread, seluruh proses Node.js akan crash.

#### C. IPC Communication Pipeline & Serialization
Ketika proses Node.js saling berkomunikasi via IPC bawaan (`process.send()`):
1. JavaScript Object diserialisasi menjadi representasi JSON atau V8 Serialization API format.
2. Data dikirimkan melewati IPC duplex stream (Unix Domain Socket di POSIX / Named Pipe di Windows).
3. Proses penerima membaca chunk, mem-parsing frame, dan merekonstruksi objek via deserialization.
Overhead serialisasi-deserialisasi ini mahal (CPU serialization time & heap allocation). Untuk komputasi intensif dengan throughput tinggi, pendekatan ini digantikan oleh `SharedArrayBuffer` dan `Atomics`.

#### D. Concurrency Memory Model: SharedArrayBuffer dan Atomics
`SharedArrayBuffer` mengalokasikan blok memori mentah di luar V8 managed heap (dikelola langsung oleh C++ backing store) yang dapat dipetakan secara simultan ke dalam beberapa V8 Isolate:
- Tidak ada serialisasi overhead (zero-copy access).
- Menimbulkan bahaya memory tearing dan race conditions.
- `Atomics` API menyediakan operasi primitif CPU atomic (seperti `Atomics.add`, `Atomics.compareExchange`, `Atomics.load`, `Atomics.store`) serta kapabilitas sinkronisasi thread OS (`Atomics.wait` dan `Atomics.notify`) yang mereplikasi mutex/condition variables langsung di JavaScript.

---

### 4. Why & What

| Dimensi | Single-Thread Default | Module `cluster` | Module `worker_threads` |
| :--- | :--- | :--- | :--- |
| **Model Eksekusi** | 1 Process, 1 Thread, 1 Event Loop | Multi-Process, Multi-Event Loop | 1 Process, Multi-Thread, Multi-Isolate |
| **Isolasi Memori** | T/A | Isolasi Total (OS-level memory protection) | Heap terisolasi, Shared raw memory opsional |
| **Kasus Penggunaan Optimal** | Pure I/O-bound (CRUD ringan, Proxy) | HTTP/TCP Network Scaling, Web Server | CPU-bound (Hashing, Kriptografi, Parsing File, ML) |
| **Overhead Komunikasi** | T/A | Tinggi (JSON IPC over UNIX Domain Socket) | Rendah (MessagePort) s/d Zero (SharedArrayBuffer) |
| **Memory Footprint** | Rendah (~30-50MB base) | Sangat Tinggi (~50MB × jumlah core CPU) | Sedang (~20-30MB per Isolate thread) |
| **Ketahanan Kegagalan** | Rendah (Crash = Service Down) | Sangat Tinggi (Worker crash, master re-forks) | Rendah (Segfault/Uncaught native crash kills all) |

---

### 5. How (Workflow Detail)

#### Workflow Zero-Downtime Deployment dengan Cluster
1. **Initial Bootstrapping**: Master process mendeteksi core CPU via `os.availableParallelism()`, memicu `cluster.fork()` untuk setiap core, dan mencatat PID serta status worker.
2. **Master Watchdog**: Master memantau signal OS (`SIGTERM` untuk termination, `SIGHUP` untuk rolling update).
3. **Sequential Replacement (Rolling Reload)**:
   - Master memilih Worker 1, mengirimkan sinyal graceful shutdown internal (misal: `shutdown_order` via IPC).
   - Worker 1 memanggil `server.close()`, menolak koneksi baru, menyelesaikan in-flight request yang sedang berlangsung.
   - Bersamaan dengan itu, Master melakukan `cluster.fork()` untuk Worker 1 Baru.
   - Master menunggu event `'listening'` dari Worker 1 Baru.
   - Setelah Worker 1 Baru siap melayani traffic, Worker 1 Lama memutus sisa koneksi dan memanggil `process.exit(0)`.
   - Master melanjutkan prosedur yang sama ke Worker 2, Worker 3, dst., secara berurutan.

#### Workflow Worker Thread Pool dengan SharedArrayBuffer
1. Master thread membuat worker pool dengan ukuran tetap (fixed pool size) saat startup.
2. Master thread mengalokasikan satu blok `SharedArrayBuffer` dan menginisialisasi TypedArray (misal: `Int32Array`) sebagai memory buffer dan synchronizer.
3. Master thread mengirimkan instance `SharedArrayBuffer` tersebut ke worker threads via `worker.postMessage()`. Pointer memory yang sama kini dapat diakses langsung oleh master dan worker.
4. Ketika ada job masuk:
   - Master menaruh data pada shared buffer.
   - Master memicu `Atomics.notify()` untuk membangunkan worker yang sedang tertidur via `Atomics.wait()`.
   - Worker membaca data, melakukan komputasi intensif secara paralel, menulis status balik, dan memberitahu master.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dapur Restoran Skala Industri
- **Cluster (Multi-Process)**: Seperti membuka 8 cabang restoran kecil yang independen. Masing-masing cabang memiliki dapur, kasir, persediaan bahan, dan manajernya sendiri. Jika cabang A mengalami kebakaran dapur, cabang B sampai H tetap melayani pelanggan tanpa gangguan. Namun, bahan makanan antar cabang tidak bisa dipindahkan secara instan tanpa kurir (IPC serialization).
- **Worker Threads (Multi-Threading)**: Seperti satu restoran raksasa dengan 1 dapur utama. Di dalam dapur tersebut terdapat 8 koki (worker threads) yang memiliki meja persiapan masing-masing, tetapi mereka berdiri di sekitar satu meja pendingin pusat yang sama (`SharedArrayBuffer`). Koki dapat mengambil daging dari meja bersama secara instan tanpa perlu kurir, tetapi harus berhati-hati agar tidak saling berebut pisau atau memotong bahan yang sama pada detik yang persis sama (`Atomics`).

```
+-----------------------------------------------------------------------------------+
|                           CLUSTER ROLLING RESTART ARCHITECTURE                    |
+-----------------------------------------------------------------------------------+
       Master Process (PID: 1000) - Manages Cluster & Handles Signals (SIGHUP)
       |
       |-- 1. Forks Worker 1 (Old) [PID: 1001] ========> [Serving Traffic]
       |-- 2. Forks Worker 2 (Old) [PID: 1002] ========> [Serving Traffic]
       |
       [SIGHUP Received - Initiating Graceful Rolling Restart]
       |
       |-- 3. Send IPC {cmd: 'shutdown'} to Worker 1 (PID: 1001)
       |      |---> Stop accept(), drain keep-alive, finish active reqs -> process.exit(0)
       |
       |-- 4. cluster.fork() -> Worker 1 (New) [PID: 1003]
       |      |---> Worker emits 'listening' -> Added to Load Balancer table
       |
       |-- 5. Repeat Step 3 & 4 for Worker 2 (PID: 1002) -> Worker 2 (New) [PID: 1004]
       |
       [Zero Downtime Achieved: Always (N-1) workers actively handling requests]
+-----------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: SharedArrayBuffer dan Atomics Synchronization
Contoh ini mendemonstrasikan pertukaran status ultra-fast antar thread tanpa `postMessage` payload terus-menerus.

```javascript
// shared-demo.mjs
import { Worker, isMainThread, workerData } from 'node:worker_threads';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);

if (isMainThread) {
  // Alokasi 4 byte memori bersama (1 slot Int32)
  const sharedBuffer = new SharedArrayBuffer(4);
  const sharedArray = new Int32Array(sharedBuffer);

  // Status index 0: 0 = Idle, 1 = Processing, 2 = Done
  sharedArray[0] = 0;

  const worker = new Worker(__filename, { workerData: { sharedBuffer } });

  console.log('[Main] Mengirim sinyal mulai kerja...');
  Atomics.store(sharedArray, 0, 1); // Set state ke 1
  Atomics.notify(sharedArray, 0, 1); // Bangunkan 1 worker yang menunggu di index 0

  // Polling / listener sederhana untuk mengecek kapan worker selesai
  const checkInterval = setInterval(() => {
    if (Atomics.load(sharedArray, 0) === 2) {
      console.log('[Main] Worker mendeteksi pekerjaan telah selesai!');
      clearInterval(checkInterval);
      worker.terminate();
    }
  }, 10);

} else {
  const { sharedBuffer } = workerData;
  const sharedArray = new Int32Array(sharedBuffer);

  console.log('[Worker] Menunggu sinyal eksekusi...');
  // Thread worker diblokir di level C++ (tanpa membakar CPU) hingga nilai berubah dari 0
  Atomics.wait(sharedArray, 0, 0);

  console.log('[Worker] Sinyal diterima, mengeksekusi komputasi intensif...');
  // Simulasi komputasi blocking
  let sum = 0;
  for (let i = 0; i < 1e8; i++) {
    sum += (i % 2);
  }

  console.log(`[Worker] Selesai. Hasil komputasi: ${sum}`);
  Atomics.store(sharedArray, 0, 2); // Tandai status menjadi 2 (Done)
}
```

#### B. Practical Example: Enterprise Zero-Downtime Cluster Manager
Server HTTP berbasis Express/Native dengan arsitektur clustering zero-downtime, safe memory limit, dan graceful IPC drain.

```typescript
// cluster-manager.ts
import cluster from 'node:cluster';
import http from 'node:http';
import os from 'node:os';
import process from 'node:process';

const NUM_WORKERS = os.availableParallelism();
const SHUTDOWN_TIMEOUT_MS = 15000;

if (cluster.isPrimary) {
  console.log(`[Master ${process.pid}] Menginisialisasi cluster dengan ${NUM_WORKERS} workers.`);
  
  const workerPids = new Set<number>();
  let isRestarting = false;

  // Fork worker awal
  for (let i = 0; i < NUM_WORKERS; i++) {
    const worker = cluster.fork();
    if (worker.process.pid) workerPids.add(worker.process.pid);
  }

  // Handle crash dan auto-healing
  cluster.on('exit', (worker, code, signal) => {
    console.warn(`[Master] Worker ${worker.process.pid} mati (code: ${code}, signal: ${signal}).`);
    if (worker.process.pid) workerPids.delete(worker.process.pid);

    if (!isRestarting) {
      console.log('[Master] Melakukan self-healing: Spawning worker baru...');
      const newWorker = cluster.fork();
      if (newWorker.process.pid) workerPids.add(newWorker.process.pid);
    }
  });

  // Zero-Downtime Rolling Reload via sinyal SIGHUP
  process.on('SIGHUP', async () => {
    if (isRestarting) {
      console.warn('[Master] Rolling restart sedang berlangsung. Perintah SIGHUP diabaikan.');
      return;
    }
    isRestarting = true;
    console.log('[Master] Memulai Rolling Restart (Zero-Downtime)...');

    const currentWorkers = Object.values(cluster.workers || {}).filter(Boolean);

    for (const oldWorker of currentWorkers) {
      if (!oldWorker) continue;

      await new Promise<void>((resolve) => {
        console.log(`[Master] Spawning replacement untuk Worker PID: ${oldWorker.process.pid}`);
        const newWorker = cluster.fork();

        newWorker.once('listening', () => {
          console.log(`[Master] Worker baru PID: ${newWorker.process.pid} siap. Mematikan worker lama PID: ${oldWorker.process.pid}`);
          
          // Kirim sinyal graceful shutdown via IPC ke worker lama
          oldWorker.send({ cmd: 'GRACEFUL_SHUTDOWN' });
          oldWorker.disconnect();

          const killTimer = setTimeout(() => {
            if (!oldWorker.isDead()) {
              console.warn(`[Master] Timeout tercapai. Memaksa kill worker PID: ${oldWorker.process.pid}`);
              oldWorker.kill('SIGKILL');
            }
          }, SHUTDOWN_TIMEOUT_MS);

          oldWorker.once('exit', () => {
            clearTimeout(killTimer);
            resolve();
          });
        });
      });
    }

    isRestarting = false;
    console.log('[Master] Rolling restart selesai dengan sukses.');
  });

  // Graceful shutdown seluruh cluster (SIGTERM/SIGINT)
  const shutdownCluster = () => {
    console.log('[Master] Shutdown signal diterima. Mematikan seluruh cluster...');
    for (const id in cluster.workers) {
      cluster.workers[id]?.send({ cmd: 'GRACEFUL_SHUTDOWN' });
      cluster.workers[id]?.disconnect();
    }
  };

  process.on('SIGTERM', shutdownCluster);
  process.on('SIGINT', shutdownCluster);

} else {
  // WORKER PROCESS
  const server = http.createServer((req, res) => {
    // Health check endpoint
    if (req.url === '/healthz') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'UP', pid: process.pid }));
      return;
    }

    // Heavy computation simulation
    let acc = 0;
    for (let i = 0; i < 5e6; i++) {
      acc += i;
    }

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ message: 'Processed', pid: process.pid, result: acc }));
  });

  server.listen(8080, () => {
    console.log(`[Worker ${process.pid}] Siap melayani traffic di port 8080.`);
  });

  // Handling Graceful Shutdown pada level Worker
  process.on('message', (msg: { cmd?: string }) => {
    if (msg && msg.cmd === 'GRACEFUL_SHUTDOWN') {
      console.log(`[Worker ${process.pid}] Memulai penutupan koneksi (Graceful Shutdown)...`);
      
      // Stop menerima koneksi baru
      server.close(() => {
        console.log(`[Worker ${process.pid}] Semua koneksi selesai. Exiting.`);
        process.exit(0);
      });

      // Force exit jika active connections hanging
      setTimeout(() => {
        console.error(`[Worker ${process.pid}] Force exit karena timeout.`);
        process.exit(1);
      }, SHUTDOWN_TIMEOUT_MS).unref();
    }
  });
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Mesin Penilaian Risiko Finansial Real-Time (Fraud & Risk Scoring Engine)
- **Karakteristik Beban Kerja**: 
  - Menerima 25,000 inbound JSON payload/detik via WebSocket/HTTP.
  - Setiap payload memerlukan kalkulasi hashing kriptografis, evaluasi ~450 aturan matriks matematika (CPU-bound), dan verifikasi tanda tangan digital HMAC.
  - Latency threshold p99 harus < 15 milidetik.
- **Masalah Awal**:
  - Arsitektur single-process standar mengalami saturasi Event Loop. CPU Core 0 mencapai 100%, sementara 31 core lainnya di server AWS `c6i.8xlarge` (32 vCPU, 64 GB RAM) menganggur (idle).
  - Terjadi Event Loop Lag hingga 2,800 ms, memicu timeout pada client API gateway.
- **Arsitektur Solusi**:
  1. **Tingkat 1 - Edge Ingestion Cluster**: Module `node:cluster` mem-fork 32 worker (1 worker per vCPU) untuk mengelola TCP/TLS termination dan parsing JSON payload.
  2. **Tingkat 2 - In-Memory CPU Offloading (Worker Thread Pool)**:
     - Dibuat custom thread pool yang di-pin pada core tertentu menggunakan native bindings.
     - Setiap cluster worker memiliki 2 dedicated `worker_threads` khusus komputasi.
     - Komunikasi input/output data matriks dilakukan via flat array di dalam `SharedArrayBuffer` sehingga tidak ada duplikasi alokasi heap V8 dan overhead serialisasi JSON bernilai 0 ms.
  3. **Tingkat 3 - IPC Health Check**: Sinyal heartbeat dikirimkan via IPC channel setiap 500 ms. Jika satu worker mendeteksi Event Loop Delay > 50 ms (via `perf_hooks.monitorEventLoopDelay`), master menandai worker tersebut "unhealthy" dan membelokkan traffic masuk sementara ke worker lain.
- **Hasil**:
  - P99 latency turun dari 2,800 ms ke **7.4 ms**.
  - CPU utilization merata di angka 78% di seluruh 32 core.
  - Tidak ada alokasi GC pause spike karena heap V8 tetap rendah berkat shared memory allocation.

---

### 9. Trade-offs

| Pendekatan | Latency Impact | Scalability Limit | Resource & Cost Overhead | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- | :--- |
| **Monolithic Single Process** | Rendah pada beban I/O murni, sangat buruk jika ada blocking code. | Dibatasi oleh 1 CPU Core (~1.4 - 2.0 GHz throughput ceiling). | Minimal (Sangat murah, footprint RAM kecil). | Microservice I/O sederhana, server internal berskala rendah. |
| **Node.js `cluster`** | Konsisten dan terlindungi antar core. Sedikit overhead saat master me-route socket via IPC. | Skala vertikal maksimal sesuai jumlah core fisik mesin (hingga 128 core). | Footprint RAM berlipat ganda ($N$ workers $\times$ base memory footprint). | Standar de-facto aplikasi web/API produksi di bare-metal / VM instances. |
| **`worker_threads` + IPC MessagePort** | Sedang. Ada delay serialisasi V8 structured clone algorithm saat payload besar. | Sangat baik untuk parallel computing, dibatasi oleh alokasi RAM per thread. | Sedang. Thread jauh lebih ringan daripada proses, namun isolate tetap butuh heap. | Heavy file decompression, image resizing, JWT signature bulk verification. |
| **`worker_threads` + `SharedArrayBuffer`** | **Ultra-low latency** (Zero-copy memory read/write). | Sangat tinggi, namun dibatasi oleh kompleksitas manajemen manual concurrency. | Rendah secara komputasi, namun biaya engineering & debugging sangat mahal. | High-frequency trading, financial engines, real-time gaming backend. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Deadlock pada Penggunaan `Atomics.wait()` di Main Thread
*   **Kesalahan**: Mengeksekusi `Atomics.wait()` di thread utama (Main Event Loop).
*   **Konsekuensi**: Node.js akan melempar runtime exception: `TypeError: [Atomics.wait] cannot be called in this context`. Browser dan Node.js secara eksplisit melarang pemblokiran main thread demi mencegah pembekuan UI/I/O loop.
*   **Solusi**: `Atomics.wait()` hanya boleh dieksekusi di dalam `Worker Thread`. Main thread harus menggunakan skema polling non-blocking, asynchronous signal, atau `Atomics.waitAsync()` (tersedia pada V8 modern).

#### 2. Thundering Herd Problem pada Cluster Listen
*   **Kesalahan**: Mengabaikan opsi round-robin bawaan Node.js dan mencoba menggunakan raw socket passing dengan OS multiplexing tanpa synchronization limiter.
*   **Konsekuensi**: Terjadi lonjakan CPU tinggi saat ada traffic burst, karena OS membangunkan seluruh worker processes hanya untuk memperebutkan satu socket yang masuk.
*   **Solusi**: Biarkan `cluster.schedulingPolicy = cluster.SCHED_RR` (default di OS selain Windows). Pastikan load balancer eksternal (NGINX/Envoy) juga melakukan load distribution merata sebelum paket masuk ke mesin host.

#### 3. Thread Pool Starvation pada Libuv vs Worker Threads
*   **Kesalahan**: Menganggap Worker Threads akan mempercepat operasi seperti `crypto.pbkdf2` atau `fs.readFile` secara otomatis.
*   **Analisis**: Operasi asynchronous native Node.js (seperti `fs`, `dns`, `zlib`, native `crypto`) tidak menggunakan V8 JavaScript thread melainkan **libuv thread pool** internal (default: 4 thread). Membuat 16 worker thread yang sama-sama memanggil `fs.readFile` justru akan memblokir antrean libuv thread pool secara parah.
*   **Solusi**: Sesuaikan variabel environment `UV_THREADPOOL_SIZE` (misal: `process.env.UV_THREADPOOL_SIZE = 64`) sebelum aplikasi memanggil API native libuv, atau serahkan I/O murni ke Event Loop asinkron biasa, gunakan `worker_threads` **hanya** untuk kode komputasi murni JavaScript/WASM.

#### 4. Memory Leak pada Worker Thread yang Dibuat Tanpa Batas (Dynamic Spawning)
*   **Kesalahan**: Menjalankan `new Worker()` untuk setiap HTTP request masuk (`req -> new Worker()`).
*   **Konsekuensi**: Out Of Memory (OOM) fatal dalam hitungan detik. Menginisialisasi V8 Isolate baru memakan waktu ~20-50 ms dan mengalokasikan ~20MB RAM per thread.
*   **Solusi**: Implementasikan arsitektur **Thread Pool** tetap (Fixed Size Thread Pool). Pool diinisialisasi sekali saat bootup, lalu request didelegasikan melalui antrean kerja (Job Queue).

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan `os.availableParallelism()`**: Hindari `os.cpus().length` lama karena tidak memperhitungkan limitasi cgroups (Docker container quota/K8s CPU limits).
- [ ] **Graceful Shutdown Timeout**: Selalu pasang timeout hard kill (misal: 10-30 detik) saat shutdown sinyal (`SIGTERM`/`SIGINT`) agar worker yang mengalami stuck connection tidak menjadi proses zombie.
- [ ] **Isolasi Log ID / Correlation ID**: Pastikan setiap log master dan worker memiliki metadata PID unik (`[Worker ${process.pid}]`) untuk mempermudah debugging log aggregators (seperti Datadog/ELK).
- [ ] **Jangan Simpan State di Memory Worker**: State transaksi wajib disimpan di Redis atau persistent store. Worker cluster dapat mati dan di-restart kapan saja tanpa peringatan.
- [ ] **Disable Cluster di Lingkungan Kubernetes Tertentu**: Jika orkestrasi deployment sudah menggunakan 1 Pod = 1 Core CPU (micro-containers), hindari penggunaan `cluster` di Node.js. Serahkan scaling horizontal ke ReplicaSets Kubernetes. Gunakan `cluster` jika mengoperasikan VM/Bare-metal besar (node vertikal) atau Pod multi-core (misal: 4-8 vCPU per Pod).
- [ ] **Tangani Event `uncaughtException` dan `unhandledRejection`**: Pastikan worker melakukan logging detail, mengirim sinyal ke master untuk spawn pengganti, lalu memanggil graceful exit secara beradab.

---

### 12. Hands-on Practice

Buat direktori praktikum dengan struktur berikut:
```text
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── worker-pool.ts
│   ├── cpu-worker.ts
│   └── server.ts
```

#### Langkah 1: Inisialisasi Project
File: `hands-on/m02/package.json`
```json
{
  "name": "enterprise-worker-pool",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "build": "tsc",
    "start": "node dist/server.js"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "typescript": "^5.3.3"
  }
}
```

File: `hands-on/m02/tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "skipLibCheck": true
  }
}
```

#### Langkah 2: Buat Logika CPU Worker
File: `hands-on/m02/src/cpu-worker.ts`
```typescript
import { parentPort } from 'node:worker_threads';

if (!parentPort) {
  throw new Error('Script ini harus dijalankan sebagai Worker Thread!');
}

parentPort.on('message', (task: { taskId: string; iterations: number }) => {
  const startTime = performance.now();
  let result = 0;

  // Beban komputasi CPU intensif
  for (let i = 0; i < task.iterations; i++) {
    result += Math.sqrt(i) * Math.sin(i);
  }

  const duration = performance.now() - startTime;

  parentPort?.postMessage({
    taskId: task.taskId,
    result,
    durationMs: duration
  });
});
```

#### Langkah 3: Bangun Generic Worker Thread Pool Engine
File: `hands-on/m02/src/worker-pool.ts`
```typescript
import { Worker } from 'node:worker_threads';
import { URL } from 'node:url';

interface Task<T, R> {
  data: T;
  resolve: (value: R) => void;
  reject: (reason?: any) => void;
}

export class StaticThreadPool<T, R> {
  private workers: Worker[] = [];
  private freeWorkers: Worker[] = [];
  private taskQueue: Task<T, R>[] = [];

  constructor(private poolSize: number, private workerScriptUrl: URL) {
    this.init();
  }

  private init() {
    for (let i = 0; i < this.poolSize; i++) {
      const worker = new Worker(this.workerScriptUrl);

      worker.on('message', (response: R & { taskId: string }) => {
        // Ambil task resolve handler jika diperlukan, di sini asumsikan 1-to-1 matching
        this.freeWorkers.push(worker);
        this.processNextTask();
      });

      worker.on('error', (err) => {
        console.error('Worker error:', err);
        this.replaceWorker(worker);
      });

      this.workers.push(worker);
      this.freeWorkers.push(worker);
    }
  }

  private replaceWorker(deadWorker: Worker) {
    deadWorker.terminate();
    const index = this.workers.indexOf(deadWorker);
    if (index !== -1) this.workers.splice(index, 1);

    const newWorker = new Worker(this.workerScriptUrl);
    this.workers.push(newWorker);
    this.freeWorkers.push(newWorker);
    this.processNextTask();
  }

  public runTask(data: T): Promise<R> {
    return new Promise<R>((resolve, reject) => {
      this.taskQueue.push({ data, resolve, reject });
      this.processNextTask();
    });
  }

  private processNextTask() {
    if (this.freeWorkers.length === 0 || this.taskQueue.length === 0) {
      return;
    }

    const worker = this.freeWorkers.pop();
    const task = this.taskQueue.shift();

    if (worker && task) {
      const onMessage = (result: any) => {
        worker.off('message', onMessage);
        worker.off('error', onError);
        task.resolve(result);
      };

      const onError = (error: any) => {
        worker.off('message', onMessage);
        worker.off('error', onError);
        task.reject(error);
      };

      worker.on('message', onMessage);
      worker.on('error', onError);

      worker.postMessage(task.data);
    }
  }

  public async destroy() {
    await Promise.all(this.workers.map((w) => w.terminate()));
  }
}
```

#### Langkah 4: Buat Server HTTP yang Memanfaatkan Worker Pool
File: `hands-on/m02/src/server.ts`
```typescript
import http from 'node:http';
import os from 'node:os';
import { URL, pathToFileURL } from 'node:url';
import path from 'node:path';
import { StaticThreadPool } from './worker-pool.js';

const PORT = 3000;
const POOL_SIZE = Math.max(1, os.availableParallelism() - 1); // Sisakan 1 core untuk I/O
const workerPath = path.resolve(process.cwd(), 'dist/cpu-worker.js');
const workerUrl = pathToFileURL(workerPath);

const pool = new StaticThreadPool<{ taskId: string; iterations: number }, any>(POOL_SIZE, workerUrl);

const server = http.createServer(async (req, res) => {
  const reqUrl = new URL(req.url || '/', `http://${req.headers.host}`);

  if (reqUrl.pathname === '/compute') {
    const iterations = parseInt(reqUrl.searchParams.get('iter') || '5000000', 10);
    const taskId = Math.random().toString(36).substring(7);

    try {
      const result = await pool.runTask({ taskId, iterations });
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', ...result }));
    } catch (err: any) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', message: err.message }));
    }
    return;
  }

  // Non-blocking ping test
  if (reqUrl.pathname === '/ping') {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('PONG! Event Loop lancar tanpa delay.');
    return;
  }

  res.writeHead(404);
  res.end('Not Found');
});

server.listen(PORT, () => {
  console.log(`Server aktif di http://localhost:${PORT}`);
  console.log(`Worker Pool berjalan dengan ${POOL_SIZE} worker thread.`);
});
```

---

### 13. Exercise

#### Level Easy
Buat sebuah script Node.js sederhana yang menggunakan `worker_threads` untuk menghitung bilangan prima dari rentang 1 sampai 1.000.000. Data hasil kalkulasi harus dikembalikan ke thread utama melalui pesan `parentPort.postMessage()` standar.

#### Level Medium
Modifikasi implementasi modul `cluster` agar Master process mengumpulkan metrik performa CPU dan Memory dari setiap worker process setiap 2 detik via IPC channel (`process.send()`). Tampilkan tabel agregat metrik seluruh worker di konsol Master.

#### Level Hard
Rancang modul Circular Ring Buffer menggunakan `SharedArrayBuffer` dan `Int32Array` sebagai antrean transfer data biner antar 2 worker thread:
- Thread A menulis indeks integer sekuensial secara berkelanjutan.
- Thread B membaca indeks tersebut.
- Implementasikan producer-consumer signaling secara eksklusif menggunakan `Atomics.wait()` dan `Atomics.notify()` tanpa memanfaatkan `EventEmitter` maupun `postMessage`.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Architect di perusahaan pemrosesan gambar berskala global. Sistem Anda harus memvalidasi, melakukan dekode, dan mengekstrak metadata EXIF dari ratusan file `.tiff` dan `.png` berukuran besar secara paralel yang masuk melalui HTTP stream.

**Ketentuan Teknis**:
1. Buat arsitektur hybrid yang menggabungkan `node:cluster` dan `node:worker_threads`.
2. Master cluster harus membagi traffic socket ke Cluster Worker.
3. Setiap Cluster Worker **dilarang keras** melakukan parsing image file di Event Loop utamanya.
4. Parsing image harus didelegasikan ke Shared Thread Pool yang memanfaatkan memory-mapped `SharedArrayBuffer` sehingga byte payload tidak disalin/diserialisasi ulang dari proses penerima socket ke thread worker.
5. Jika salah satu thread mengalami failure (misal: unhandled allocation failure), pool harus secara atomik meregenerasi thread tersebut tanpa memutus koneksi HTTP aktif milik klien lain.
6. Sertakan mekanisme backpressure: jika seluruh antrean thread worker penuh, server wajib mengembalikan status HTTP `503 Service Unavailable` secara cepat (< 2 ms) tanpa menahan buffer stream di memori.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa perbedaan mendasar antara model isolasi memori pada module `node:cluster` vs module `node:worker_threads`?
2. Mengapa menjalankan komputasi synchronous yang intensif (seperti perulangan matriks besar) pada Event Loop utama Node.js dapat melumpuhkan seluruh inbound network traffic?
3. Apa fungsi struktural dari method `cluster.fork()` dan bagaimana cara mendeteksi apakah skrip sedang berjalan sebagai primary atau worker process?
4. Mengapa kita tidak disarankan melakukan `new Worker()` secara ad-hoc untuk setiap HTTP request yang masuk ke server?
5. Sinyal POSIX apa yang secara konvensional digunakan oleh daemon sistem Linux untuk meminta aplikasi memuat ulang konfigurasinya atau melakukan rolling restart (misal: NGINX atau Node.js)?

#### Pertanyaan Intermediate
6. Bagaimana cara master process pada modul `node:cluster` membagikan listening socket port TCP yang sama kepada seluruh worker processes tanpa memicu error `EADDRINUSE`?
7. Apa peran spesifik dari objek `SharedArrayBuffer` dan mengapa objek tersebut memerlukan utilitas `Atomics` untuk manipulasi nilainya?
8. Mengapa `Atomics.wait()` dilarang untuk dieksekusi di dalam Main Thread Node.js, namun diperbolehkan di dalam `Worker Threads`?
9. Apa perbedaan esensial antara libuv thread pool (`UV_THREADPOOL_SIZE`) dengan thread yang dibuat via modul `node:worker_threads`?
10. Bagaimana Anda mendeteksi dan mencegah *thundering herd problem* saat mendesain IPC socket distribution di Linux?

#### Skenario Kasus Produksi
11. **Skenario 1**: Sebuah cluster Node.js dengan 8 worker berjalan di VM Linux. Selama rolling restart dengan sinyal `SIGHUP`, sejumlah request pengguna terputus secara tiba-tiba dengan respons `502 Bad Gateway` di reverse proxy NGINX. Setelah diinspeksi, worker lama langsung dimatikan beberapa milidetik setelah worker baru di-fork. Analisis di mana letak kelemahan alur orkestrasinya dan bagaimana langkah mitigasinya!
12. **Skenario 2**: Aplikasi pengolah data menggunakan `worker_threads` untuk memproses file CSV 500 MB. Meskipun sudah dipindahkan ke worker thread, penggunaan memory (RSS) proses membengkak hingga 3x lipat ukuran file asli dan proses akhirnya dimatikan oleh Linux OOM Killer. Apa yang sebenarnya terjadi pada proses data transfer ke Worker Thread tersebut?
13. **Skenario 3**: Sebuah microservice Node.js di-deploy ke dalam container Kubernetes dengan konfigurasi resources: `limits.cpu = 2` dan `requests.cpu = 2` pada node bare-metal berkapasitas 64 CPU Core. Pengembang menggunakan kode `for (let i = 0; i < os.cpus().length; i++) cluster.fork()`. Jelaskan malapetaka apa yang akan terjadi di cluster Kubernetes Anda dan bagaimana cara memperbaikinya!

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Jawaban Basic
1. **Module `cluster`** menciptakan proses OS yang sepenuhnya terpisah, masing-masing dengan heap V8, memori, GC, dan PID sendiri. **Module `worker_threads`** berjalan dalam proses OS yang sama (PID identik), memiliki heap V8 terpisah, namun memiliki kapabilitas untuk berbagi memori mentah yang sama via `SharedArrayBuffer`.
2. Karena JavaScript berjalan pada Single Thread (Event Loop). Jika thread tersebut sibuk memproses komputasi CPU murni, ia tidak dapat mengeksekusi microtask, macrotask, maupun memproses event `poll I/O` libuv untuk menerima paket TCP dari kernel OS, menyebabkan antrean jaringan macet.
3. `cluster.fork()` memicu instansiasi child process baru menggunakan mekanisme internal libuv/OS `fork()`, kemudian membangun IPC socket duplex antara master dan child. Pengecekan dilakukan via properti boolean `cluster.isPrimary` (atau `cluster.isMaster` pada versi legacy) vs `cluster.isWorker`.
4. Spawning thread baru mengalokasikan context V8 Isolate baru yang memerlukan alokasi memori puluhan megabyte dan overhead latensi CPU (20-50 ms). Pola ini rentan memicu OOM (Out Of Memory) dan CPU exhaustion di bawah beban tinggi. Solusinya adalah menggunakan Worker Thread Pool statis.
5. Sinyal `SIGHUP` (Signal Hang Up).

#### Jawaban Intermediate
6. Master process membuka socket port TCP tersebut terlebih dahulu. Ketika worker memanggil `server.listen()`, Node.js mengintersepsi pemanggilan tersebut dan mengalihkan penanganan socket ke master. Master kemudian menyerahkan koneksi yang diterima menggunakan IPC channel internal melalui socket descriptor passing (`SCM_RIGHTS`), sehingga tidak terjadi konflik perebutan port (`EADDRINUSE`).
7. `SharedArrayBuffer` menyediakan blok memori mentah bersama (shared memory) yang dapat diakses simultan oleh beberapa thread tanpa mekanisme duplikasi data. `Atomics` mutlak diperlukan untuk memastikan operasi read-modify-write dieksekusi secara atomik di level register instruksi CPU guna mencegah race condition dan memory tearing.
8. `Atomics.wait()` memblokir eksekusi thread secara synchronous sampai dibangunkan atau timeout. Jika dieksekusi di Main Thread, seluruh Event Loop akan terhenti total (membekukan penanganan I/O, timers, dan callbacks). Worker thread dapat diblokir dengan aman karena hanya bertanggung jawab atas beban tugas komputasi spesifiknya sendiri.
9. **Libuv thread pool** dikelola secara internal oleh runtime C/C++ libuv secara eksklusif untuk operasi I/O asinkron yang tidak didukung secara non-blocking oleh OS (seperti `fs`, `crypto`, `getaddrinfo`). **`worker_threads`** adalah thread independen yang menjalankan V8 Isolate penuh di mana Anda dapat mengeksekusi kode JavaScript aplikasi arbitrary secara paralel.
10. Thundering herd terjadi saat OS membangkitkan semua proses yang menunggu socket yang sama secara serentak. Masalah ini diatasi di Node.js dengan menggunakan `cluster.schedulingPolicy = cluster.SCHED_RR` (Round-Robin), di mana master process secara eksklusif menjadi satu-satunya entitas yang menerima socket dari kernel, lalu membagikannya bergantian secara seimbang ke worker lewat IPC.

#### Jawaban Skenario Kasus Produksi
11. **Akar Masalah**: Master process mematikan worker lama seketika tanpa memberikan jeda drain koneksi (graceful drain) dan tidak menunggu worker pengganti benar-benar siap berstatus `'listening'`.
    **Mitigasi**: 
    - Lakukan sequential reload: spawn worker baru terlebih dahulu, tunggu event `'listening'`.
    - Kirim sinyal graceful shutdown via IPC ke worker lama agar worker lama mengeksekusi `server.close()`.
    - Biarkan worker lama melayani in-flight request yang tersisa hingga selesai, dan terapkan fail-safe timeout (`setTimeout`) sebelum memanggil `process.exit(0)` atau `SIGKILL`.
12. **Akar Masalah**: Data CSV dikirimkan ke worker thread melalui `worker.postMessage()` standar. Mekanisme ini menggunakan V8 Structured Clone Algorithm yang menyalin seluruh memori data ke buffer serialisasi dan mendeserialisasikannya kembali di thread tujuan. Hal ini menggandakan pemakaian memori secara masif di heap V8.
    **Mitigasi**: Pindahkan data CSV menggunakan streaming (`ReadableStream`), gunakan `Transferable Objects` (seperti memindahkan kepemilikan `ArrayBuffer`), atau letakkan byte raw ke dalam `SharedArrayBuffer` sehingga tidak ada duplikasi memori antar-thread.
13. **Akar Masalah**: `os.cpus().length` mengembalikan jumlah core dari sistem host bare-metal (64 Core), bukan batas cgroups container (2 Core). Akibatnya, Node.js akan mem-fork 64 worker process di dalam container yang hanya memiliki kuota 2 CPU. Ini memicu context-switching overhead ekstrem antar proses, CPU throttling hebat oleh CFS (Completely Fair Scheduler) Linux, degradasi performa drastis, dan crash OOM.
    **Mitigasi**: Ganti pemanggilan tersebut dengan `os.availableParallelism()` yang otomatis mendeteksi kuota cgroups container, atau set manual jumlah worker via Environment Variable yang selaras dengan alokasi vCPU Kubernetes.

---

### 16. Summary

1. **Arsitektur Skalabilitas Hybrid**: Skalabilitas sejati pada ekosistem Node.js enterprise didorong oleh arsitektur hibrida: `node:cluster` untuk pemanfaatan core multi-processing pada layer jaringan/HTTP, dan `node:worker_threads` untuk isolasi beban komputasi CPU-bound.
2. **Karakteristik Zero-Downtime**: Ketersediaan tinggi (high availability) pada proses lokal dicapai via pemutusan hubungan terkontrol (graceful drain), pemantauan siklus hidup worker (`listening`, `disconnect`, `exit`), dan koordinasi berbasis sinyal POSIX (`SIGHUP`, `SIGTERM`).
3. **Optimasi Memori Tingkat Rendah**: Untuk kebutuhan pemrosesan data throughput tinggi tanpa degradasi Garbage Collection, `SharedArrayBuffer` dan primitif sinkronisasi `Atomics` menghapus overhead serialisasi data menjadi 0 ms (zero-copy concurrency).
4. **Prinsip Operasional Container**: Dalam ekosistem modern yang dipimpin Kubernetes dan container, perancangan worker concurrency wajib memperhitungkan batasan CPU allocation (`cgroups`) secara akurat via `os.availableParallelism()` guna menghindari resource starvation dan CPU throttling.