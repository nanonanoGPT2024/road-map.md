# BAB 02: Asynchronous Runtime Internals & Event Loop Orchestration
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedakan** secara granular mekanika internal eksekusi V8 Engine Isolate dan integrasi Libuv runtime (Phases of Libuv Event Loop vs. ECMAScript Microtask Specification).
- **Mendiagnosis dan Mengeliminasi** degradasi performa akibat *Event Loop Lag* (ELL) dan *Event Loop Starvation* pada throughput tinggi (>50.000 RPS).
- **Merancang dan Mengimplementasikan** *Custom Enterprise Priority Task Scheduler* yang mampu mencegah *microtask starvation*, mengatur kuota eksekusi berbasis waktu (*quantum execution*), dan menyeimbangkan beban I/O-bound serta CPU-bound.
- **Mengorkestrasikan** komputasi konkuren paralel menggunakan `Worker Threads`, `SharedArrayBuffer`, dan operasi atomik (`Atomics`) untuk komputasi CPU-bound tanpa memblokir thread eksekusi utama.
- **Membangun Sistem Observabilitas Terintegrasi** menggunakan Node.js `perf_hooks` (khususnya `monitorEventLoopDelay` dan `eventLoopUtilization`) untuk menghasilkan metrik telemetri produksi (OpenTelemetry standard).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Pemahaman Fundamental JavaScript Concurrency**: Konsep dasar Callback, Promises/A+ Specification, dan sintaks `async/await`.
- **Sistem Operasi Tingkat Rendah**: Konsep thread, proses, non-blocking I/O multiplexing (`epoll` di Linux, `kqueue` di macOS, `IOCP` di Windows).
- **Arsitektur Node.js & Browser Engine Dasar**: Pemahaman umum tentang Single-Threaded Event Loop dan peran Web APIs/Node C++ Bindings.
- **TypeScript Tingkat Lanjut**: Generic types, concurrent programming interfaces, dan memory management paradigms.

---

### 3. Concept & Internal Architecture (Mendalam)

Model konkurensi JavaScript sering disalahartikan sebagai "single-threaded runtime murni". Secara presisi arsitektural, JavaScript execution environment (seperti Node.js) adalah **arsitektur hibrida multi-threaded yang mengabstraksikan eksekusi kode pengguna ke dalam satu thread eksekusi utama (Main Thread)** melalui mekanisme koordinasi V8 Isolate dan Libuv.

```
+-------------------------------------------------------------------------+
|                              NODE.JS INSTANCE                           |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  |                            V8 ISOLATE                             |  |
|  |  +-------------------+  +--------------------------------------+  |  |
|  |  |   Call Stack      |  | Microtask Queue                      |  |  |
|  |  |   (Single Thread) |  |  [process.nextTick] -> highest prio  |  |  |
|  |  |                   |  |  [Promise Reactions]                 |  |  |
|  |  +-------------------+  +--------------------------------------+  |  |
|  +----------------------------------|--------------------------------+  |
|                                     |                                   |
|                                     v Bridge (V8 Bindings)              |
|  +----------------------------------|--------------------------------+  |
|  |                           LIBUV RUNTIME                            |  |
|  |                                                                   |  |
|  |    +-------------------+   +--------------------+                 |  |
|  |    |  Timers Phase     |-->| Pending Callbacks  |                 |  |
|  |    +-------------------+   +--------------------+                 |  |
|  |              ^                        |                           |  |
|  |              |                        v                           |  |
|  |    +-------------------+   +--------------------+                 |  |
|  |    |  Close Callbacks  |   |   Idle / Prepare   |                 |  |
|  |    +-------------------+   +--------------------+                 |  |
|  |              ^                        |                           |  |
|  |              |                        v                           |  |
|  |    +-------------------+   +--------------------+                 |  |
|  |    |    Check Phase    |<--|     Poll Phase     |                 |  |
|  |    |   (setImmediate)  |   |  (I/O epoll/kqueue)|                 |  |
|  |    +-------------------+   +--------------------+                 |  |
|  |                                       |                           |  |
|  +---------------------------------------|---------------------------+  |
|                                          |                              |
|           +------------------------------+--------------+               |
|           | OS Kernel Non-blocking I/O                  |               |
|           | (Sockets, Pipes via epoll/kqueue)           |               |
|           +---------------------------------------------+               |
|           | Libuv Worker Thread Pool (Default: 4)       |               |
|           | (fs.*, crypto.*, dns.lookup, zlib.*)        |               |
|           +---------------------------------------------+               |
+-------------------------------------------------------------------------+
```

#### A. Anatomi V8 Isolate vs. Libuv
1. **V8 Isolate**: Mewakili satu instance runtime V8 yang terisolasi sepenuhnya dengan Call Stack, Memory Heap, dan Garbage Collector sendiri. V8 mengeksekusi bytecode JavaScript secara sinkron.
2. **Libuv Layer**: Abstraksi C library lintas platform yang menangani asynchronous I/O berbasis event. Libuv mengelola Event Loop fisik dan thread pool (`uv_threadpool`).
3. **Mekanisme Bridge**: Ketika kode JavaScript memanggil API non-blocking seperti `crypto.pbkdf2` atau `fs.readFile`, V8 memanggil C++ binding internal yang mendelegasikan tugas ke Libuv. Libuv kemudian menjadwalkan pekerjaan ke OS kernel (jika file descriptor mendukung polling non-blocking) atau melemparkannya ke `uv_threadpool`.

#### B. Fase-Fase Event Loop Libuv (The Six Phases)
Setiap iterasi dari Event Loop Libuv disebut **Tick**. Tiap tick bergerak melalui urutan fase yang deterministik:

1. **Timers Phase**: Mengeksekusi callback dari `setTimeout()` dan `setInterval()` yang ambang batas waktunya (*threshold*) telah terpenuhi. Interval disimpan dalam struktur data *min-heap*, sehingga Libuv hanya perlu mengecek root untuk menentukan timer yang kedaluwarsa.
2. **Pending Callbacks Phase**: Mengeksekusi callback I/O yang ditunda dari iterasi sebelumnya, seperti penanganan error tipe sistem tertentu (misal: TCP socket menerima `ECONNREFUSED`).
3. **Idle, Prepare Phase**: Fase internal Libuv yang dijalankan sebelum poll phase. Digunakan secara eksklusif untuk koordinasi internal runtime Node.js.
4. **Poll Phase**: 
   - Menghitung durasi pemblokiran (*blocking timeout*) untuk menunggu I/O baru.
   - Memproses event I/O yang telah siap pada *poll queue* (misal koneksi HTTP baru, transfer data database).
   - Jika antrean kosong: Jika ada antrean `setImmediate()`, poll phase berakhir dan masuk ke Check phase. Jika tidak ada, Libuv akan memblokir (*block execution*) thread pada pemanggilan kernel (`epoll_wait`/`kevent`) hingga event I/O masuk atau batas waktu timer terdekat habis.
5. **Check Phase**: Didedikasikan khusus untuk mengeksekusi callback yang didaftarkan melalui `setImmediate()`.
6. **Close Callbacks Phase**: Menangani penutupan socket atau handle secara eksplisit (misal: `socket.on('close', ...)`).

#### C. Mikro-Semantik: Microtask Queue vs. Macrotask (Macrotask Loop Phase)
Di luar fase Libuv, ECMAScript mendefinisikan konsep **Job Queues** yang diimplementasikan sebagai **Microtask Queue** di V8. Terdapat dua kelas antrean mikro prioritas:
1. **`process.nextTick` Queue**: Khusus Node.js. Bukan bagian dari event loop Libuv, melainkan dikelola langsung oleh Node.js runtime. Memiliki prioritas mutlak tertinggi.
2. **Promise Reactions Queue**: Menyimpan callback `.then()`, `.catch()`, `.finally()`, serta kelanjutan dari *resumed* `await`. Mengantre `queueMicrotask()`.

**Aturan Penjadwalan Mikro Node.js Modern (Post-Node 11+):**
V8 mengosongkan *seluruh* Microtask Queue segera setelah Call Stack kosong, **bahkan di antara callback individual dalam fase Libuv yang sama**. Jika sebuah callback timer selesai dieksekusi, V8 memproses antrean `nextTickQueue` sampai kosong, kemudian `microtaskQueue` sampai kosong, sebelum berpindah ke callback timer berikutnya di dalam fase yang sama.

---

### 4. Why & What

#### Mengapa Pemahaman Tingkat Dalam Ini Krusial?
Pada aplikasi berskala enterprise, kegagalan asynchronous runtime jarang termanifestasi sebagai *hard crash* seketika. Sebaliknya, gejalanya bersifat laten:
- Peningkatan drastis p99 dan p99.9 latency (*tail latency*).
- Kegagalan *health check* HTTP endpoint akibat event loop starvation, memicu restart container cascading (*OOM/Restart Loop*).
- Throughput ambruk padahal pemakaian CPU core utama baru menyentuh 100% sementara multi-core server lainnya menganggur (*underutilization*).

#### Apa yang Harus Dikelola?
1. **Event Loop Starvation**: Kondisi di mana Microtask Queue terus menerus diisi (misal rekursi `process.nextTick` atau unthrottled promise chaining), sehingga Libuv tidak pernah bisa melanjutkan ke fase berikutnya (Poll/Timers).
2. **Event Loop Lag (ELL)**: Selisih waktu antara kapan sebuah task *seharusnya* dieksekusi vs kapan task tersebut *secara aktual* mulai dieksekusi pada Call Stack.
3. **CPU-bound vs I/O-bound Segregation**: Mengisolasi manipulasi data berukuran besar (kompresi, enkripsi, transformasi JSON megabyte-scale) dari jalur I/O utama.

---

### 5. How (Workflow Detail)

Alur penanganan task mulai dari registrasi hingga eksekusi mengikuti siklus berikut:

```
[ Incoming Task / Code Execution ]
                |
                v
       Is it CPU Synchronous?
         /              \
       YES               NO
       /                  \
[Execute directly    What API type is it?
 on Call Stack]       /                 \
                     /                   \
           [Node Native / Libuv]      [Microtask / Promise]
                    |                            |
       Is it Thread-Pool/Kernel?                 v
          /                  \           [Enqueue to V8 Microtask
     [Kernel I/O]      [Thread Pool]      or nextTick Queue]
          |                  |                   |
    (epoll/kqueue)    (uv_threadpool)            v
          |                  |           [Drain immediately when
          +--------+---------+            Call Stack becomes empty]
                   |
                   v
         [Libuv Phase Queue]
     (Timers / Poll / Check / etc.)
                   |
                   v
         [Yielded to Call Stack
           at target Phase]
```

1. **Inisiasi**: Fungsi async dipanggil. V8 mengeksekusi kode sinkron di dalam fungsi hingga menemukan operasi I/O atau `await`.
2. **Pendelegasian**:
   - Jika I/O berbasis socket: Libuv mendaftarkan file descriptor ke kernel notification engine (`epoll`). Main thread bebas mengerjakan hal lain.
   - Jika I/O berbasis filesystem/kriptografi: Libuv mengirimkan payload task ke salah satu worker di `uv_threadpool` (default 4 thread, dapat diubah via `UV_THREADPOOL_SIZE`).
3. **Notifikasi Selesai**: Kernel atau thread worker memberi sinyal ke Libuv bahwa operasi selesai.
4. **Enqueuing**: Libuv memindahkan callback operasi ke queue fase terkait (misal Check Phase untuk `setImmediate`, Poll Phase untuk I/O).
5. **Draining Microtasks**: Setelah callback pada Call Stack selesai, V8 mengeksekusi seluruh antrean `process.nextTick`, diikuti oleh antrean Microtask Promise sebelum memproses elemen berikutnya dari Libuv Phase Queue.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional (The Single Runway Airport)

Bayangkan sebuah bandara internasional dengan hanya **Satu Landasan Pacu (Call Stack)**:
- **Pesawat di Udara (Microtask Queue)**: Memiliki bahan bakar terbatas. Mereka harus mendarat *segera* begitu landasan kosong, sebelum pesawat di darat diizinkan lepas landas.
- **Pesawat Bahan Bakar Kritis (`process.nextTick`)**: Mendapat izin darurat; mendarat sebelum pesawat di antrean udara lainnya.
- **Hanggar Persiapan (Libuv Event Loop Phases)**:
  - *Gate Timers*: Pesawat charter yang terjadwal jam tertentu.
  - *Cargo Hub (Poll Phase)*: Bongkar muat kontainer dari kapal/truk (I/O).
  - *Maintenance Runway (Check Phase - `setImmediate`)*: Pesawat yang siap jalan tepat setelah bongkar muat kargo selesai.
- **Kru Darat Bawah Tanah (Libuv Worker Pool)**: Membongkar barang berat di bawah tanah agar pilot di landasan pacu utama tidak perlu memindahkan kargo secara manual.

Jika ada pilot di landasan memutuskan untuk menghitung 10 juta lembar manifest penumpang secara manual (CPU-blocking code), **seluruh bandara macet**: tidak ada pesawat yang bisa mendarat, tidak ada kargo yang bisa masuk, dan sistem monitoring menara kontrol menganggap bandara terbakar (*health check timeout*).

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengamati Fase Eksekusi Deterministik
Contoh ini mendemonstrasikan secara presisi urutan eksekusi antar antrean:

```typescript
// simple-order.ts
import { writeFileSync, unlinkSync } from 'node:fs';

console.log('1: Synchronous Main Thread Init');

setTimeout(() => {
  console.log('2: Timers Phase Callback (setTimeout 0ms)');
  process.nextTick(() => console.log('3: nextTick inside Timers Phase'));
}, 0);

setImmediate(() => {
  console.log('4: Check Phase Callback (setImmediate)');
  queueMicrotask(() => console.log('5: Microtask inside Check Phase'));
});

process.nextTick(() => {
  console.log('6: NextTick Phase (Before any macrotask/timer)');
});

queueMicrotask(() => {
  console.log('7: Standard Microtask (Promise Reaction level)');
});

console.log('8: Synchronous Main Thread End');

// Output Deterministik:
// 1: Synchronous Main Thread Init
// 8: Synchronous Main Thread End
// 6: NextTick Phase (Before any macrotask/timer)
// 7: Standard Microtask (Promise Reaction level)
// [Fase Timers atau Check tergantung status inisialisasi loop, namun di dalam fase:]
// 2: Timers Phase Callback (setTimeout 0ms)
// 3: nextTick inside Timers Phase
// 4: Check Phase Callback (setImmediate)
// 5: Microtask inside Check Phase
```

#### Practical Example: Enterprise Priority-Aware Async Task Scheduler
Implementasi antrean asinkron berbasis prioritas dengan teknik *Time-Slicing / Cooperative Scheduling* untuk mencegah event loop freezing.

```typescript
// priority-scheduler.ts
import { performance } from 'node:perf_hooks';

export enum TaskPriority {
  CRITICAL = 0,
  HIGH = 1,
  NORMAL = 2,
  LOW = 3,
}

interface ScheduledTask<T> {
  id: string;
  priority: TaskPriority;
  execute: () => Promise<T>;
  resolve: (value: T | PromiseLike<T>) => void;
  reject: (reason?: unknown) => void;
  enqueuedAt: number;
}

export class CooperativeTaskScheduler {
  private queues: Map<TaskPriority, ScheduledTask<any>[]> = new Map([
    [TaskPriority.CRITICAL, []],
    [TaskPriority.HIGH, []],
    [TaskPriority.NORMAL, []],
    [TaskPriority.LOW, []],
  ]);

  private isRunning = false;
  private readonly timeSliceMs: number;

  constructor(timeSliceMs = 8) {
    // Default 8ms execution budget per tick to maintain 60-120fps responsiveness
    this.timeSliceMs = timeSliceMs;
  }

  public schedule<T>(priority: TaskPriority, execute: () => Promise<T>): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      const task: ScheduledTask<T> = {
        id: crypto.randomUUID(),
        priority,
        execute,
        resolve,
        reject,
        enqueuedAt: performance.now(),
      };

      const targetQueue = this.queues.get(priority)!;
      targetQueue.push(task);

      if (!this.isRunning) {
        this.isRunning = true;
        this.scheduleExecution();
      }
    });
  }

  private scheduleExecution(): void {
    // Menggunakan setImmediate agar I/O Poll Phase memiliki kesempatan memproses network events
    setImmediate(() => this.drainWorkLoop());
  }

  private async drainWorkLoop(): Promise<void> {
    const startTime = performance.now();

    while (this.hasPendingTasks()) {
      const task = this.getNextTask();
      if (!task) break;

      try {
        const result = await task.execute();
        task.resolve(result);
      } catch (error) {
        task.reject(error);
      }

      // Check Quantum Expiration (Time-slicing boundary)
      const elapsed = performance.now() - startTime;
      if (elapsed >= this.timeSliceMs && this.hasPendingTasks()) {
        // Yield Main Thread execution back to Libuv to process incoming I/O
        this.scheduleExecution();
        return;
      }
    }

    this.isRunning = false;
  }

  private hasPendingTasks(): boolean {
    for (const queue of this.queues.values()) {
      if (queue.length > 0) return true;
    }
    return false;
  }

  private getNextTask(): ScheduledTask<any> | undefined {
    // Strict priority retrieval: CRITICAL -> HIGH -> NORMAL -> LOW
    for (const priority of [
      TaskPriority.CRITICAL,
      TaskPriority.HIGH,
      TaskPriority.NORMAL,
      TaskPriority.LOW,
    ]) {
      const queue = this.queues.get(priority)!;
      if (queue.length > 0) {
        return queue.shift();
      }
    }
    return undefined;
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Telemetry Ingestion Microservice Degradation
- **Profil Beban**: 65.000 events/detik HTTP JSON payload pada gateway pembayaran digital.
- **Kondisi Awal**: p99 Latency meroket dari 12ms ke 4.800ms. Kubernetes Liveness Probe gagal merespons dalam 3 detik, menyebabkan Pod dibunuh (*crash-loop*) bergantian.
- **Root Cause Analysis (RCA)**:
  1. Payload validasi menggunakan library JSON schema sinkron yang memakan waktu 4ms per request berukuran besar.
  2. Main Thread terblokir secara komulatif: `65.000 req/sec * 0.004 sec = 260 core-seconds` pekerjaan CPU sinkron per detik.
  3. Microtask Queue penuh sesak akibat chain parsing Promise yang tidak pernah memberi jeda bagi Libuv Poll Phase untuk menerima koneksi TCP baru.

#### Solusi Arsitektur Produksi:
1. Memindahkan validasi skema JSON CPU-bound ke pool `Worker Threads` menggunakan zero-copy message passing (`SharedArrayBuffer` & `MessagePort`).
2. Menerapkan integrasi monitoring `eventLoopUtilization` (ELU) dan `monitorEventLoopDelay`.
3. Memasang *Circuit Breaker* adaptif berbasis Event Loop Lag: Tolak trafik non-kritis dengan HTTP 503 jika Event Loop Lag > 50ms.

```typescript
// production-telemetry-pipeline.ts
import { Worker, isMainThread, parentPort, workerData } from 'node:worker_threads';
import { monitorEventLoopDelay, eventLoopUtilization, IntervalHistogram } from 'node:perf_hooks';
import * as http from 'node:http';

// ==========================================
// WORKER THREAD CODE (CPU Processing)
// ==========================================
if (!isMainThread) {
  parentPort?.on('message', (payload: string) => {
    try {
      // Simulasi Validasi JSON Kompleks & Komputasi Hashing Berat
      const parsed = JSON.parse(payload);
      let hash = 0;
      for (let i = 0; i < 500_000; i++) {
        hash = (hash + (payload.charCodeAt(i % payload.length) * 31)) | 0;
      }
      parentPort?.postMessage({ status: 'VALID', txId: parsed.txId, hash });
    } catch (err: any) {
      parentPort?.postMessage({ status: 'INVALID', error: err.message });
    }
  });
}

// ==========================================
// MAIN THREAD CODE (I/O & Worker Pool Routing)
// ==========================================
if (isMainThread) {
  // 1. Observabilitas Runtime Mendalam
  const histogram: IntervalHistogram = monitorEventLoopDelay({ resolution: 10 });
  histogram.enable();

  let lastELU = eventLoopUtilization();

  setInterval(() => {
    const currentELU = eventLoopUtilization(lastELU);
    lastELU = currentELU;
    
    // Konversi nanoseconds ke milliseconds
    const p99LagMs = histogram.percentile(99) / 1e6;
    console.log(`[TELEMETRY] ELU: ${(currentELU.utilization * 100).toFixed(2)}% | p99 Lag: ${p99LagMs.toFixed(2)}ms`);

    // Reset histogram buckets periodik
    histogram.reset();
  }, 2000).unref(); // unref agar timer telemetry ini tidak menahan proses shutdown

  // 2. Worker Pool Sederhana
  const POOL_SIZE = 4;
  const workers: Worker[] = [];
  let currentWorkerIdx = 0;

  for (let i = 0; i < POOL_SIZE; i++) {
    workers.push(new Worker(__filename));
  }

  function getWorker(): Worker {
    const worker = workers[currentWorkerIdx];
    currentWorkerIdx = (currentWorkerIdx + 1) % POOL_SIZE;
    return worker;
  }

  // 3. HTTP Server dengan Circuit Breaker berbasis Event Loop Lag
  const server = http.createServer((req, res) => {
    // Circuit Breaker: Tolak request jika Event Loop Lag > 50ms
    const currentP99LagMs = histogram.percentile(99) / 1e6;
    if (currentP99LagMs > 50) {
      res.writeHead(503, { 'Content-Type': 'application/json', 'Retry-After': '1' });
      res.end(JSON.stringify({ error: 'Service Degraded: Event Loop Overloaded' }));
      return;
    }

    if (req.method === 'POST' && req.url === '/ingest') {
      let body = '';
      req.on('data', chunk => { body += chunk; });
      req.on('end', () => {
        const worker = getWorker();

        const onMessage = (result: any) => {
          worker.off('message', onMessage);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(result));
        };

        worker.on('message', onMessage);
        worker.postMessage(body);
      });
    } else {
      res.writeHead(404).end();
    }
  });

  server.listen(3000, () => {
    console.log('Production Telemetry Node listening on port 3000');
  });
}
```

---

### 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Biaya / Konsekuensi Negatif | Kasus Penggunaan Ideal |
|---|---|---|---|
| **Single Thread Asynchronous (Pure I/O)** | Jejak memori minimal (~30MB), overhead context switching zero, konkurensi I/O masif (100k+ sockets). | Kerentanan fatal terhadap satu blocking call, p99 latency rentan lonjakan bila serialisasi data besar. | Proxy, API Gateway, Chat Routing, Notification Broker. |
| **Worker Threads Concurrency** | Memanfaatkan 100% Core CPU, menjaga Main Thread p99 latency tetap stabil dan responsif. | Overhead memori tinggi (setiap thread memakan baseline 20–40MB untuk V8 Isolate baru), biaya serialisasi pesan `postMessage`. | Validasi Skema JSON besar, Kriptografi, Kompresi Gambar/Audio, Enkripsi/Dekripsi Batch. |
| **SharedArrayBuffer + Atomics** | Zero serialization overhead, manipulasi memori bersama berkecepatan tingkat C/Assembly. | Kompleksitas debugging tinggi, risiko *deadlock* atau *race conditions* jika koordinasi memori gagal, proteksi keamanan Specter/Meltdown via COOP/COEP headers. | Engine Grafis, Algoritma Pemrosesan Data Finansial HFT berlatensi sub-milidetik. |
| **Cooperative Chunking (`setImmediate`)** | Mengurangi latency spike tanpa overhead alokasi Worker Thread baru. | Waktu eksekusi total dari task CPU menjadi lebih panjang karena terpotong-potong oleh tick interval. | Transformasi array/dataset ukuran sedang (5.000 - 50.000 record) langsung di Main Thread. |

---

### 10. Common Mistakes & Troubleshooting

#### Anti-Pola 1: Rekursi `process.nextTick` Tak Terbatas
```typescript
// FATAL: Memicu starvation total pada I/O dan Timer
function badStarvationLoop() {
  process.nextTick(() => badStarvationLoop());
}
badStarvationLoop();
// Hasil: Libuv Event Loop terhenti permanen. HTTP server tidak akan menerima koneksi baru.
```
*Solusi*: Ganti dengan `setImmediate` jika tugas harus dieksekusi secara asynchronous berulang tanpa memblokir I/O queue:
```typescript
function safeLoop() {
  setImmediate(() => safeLoop());
}
safeLoop();
```

#### Anti-Pola 2: Mengasumsikan `setTimeout(fn, 0)` Ekivalen dengan 0ms Presisi
```typescript
// Kesalahan Fatal dalam Perancangan Sistem Real-time
setTimeout(() => {
  console.log('Fired');
}, 0);
```
*Mekanika*: Di Node.js dan spesifikasi HTML5, batas minimum timer dijepit (*clamped*) pada `1ms`. Selain itu, jika Call Stack atau Microtask Queue sibuk, timer bisa tertunda puluhan hingga ratusan milidetik. Jangan gunakan `setTimeout` untuk penjadwalan presisi tinggi.

#### Panduan Troubleshooting Event Loop Lag di Produksi:
1. **Identifikasi Indikasi**: Metrik CPU rendah (<30%) tetapi latency p99 HTTP tinggi (>2s).
2. **Koleksi Profiling**:
   ```bash
   node --cpu-prof --cpu-prof-interval=1000 app.js
   ```
3. **Analisis File `.cpuprofile`**: Buka file output di Chrome DevTools (Tab Performance). Cari blok oranye/kuning panjang di Main Thread (`JSON.stringify`, `fs.readFileSync`, atau RegEx backtracking).
4. **Inspeksi Lag Menggunakan Perf Hooks**:
   Cetak nilai `monitorEventLoopDelay().percentile(99)` secara reguler ke format Prometheus/Datadog.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan `setImmediate` daripada `process.nextTick`** untuk semua kebutuhan penundaan eksekusi kode pengguna, kecuali jika Anda secara spesifik sedang membangun library tingkat rendah yang harus menormalkan callback sinkron menjadi asinkron sebelum I/O berlangsung.
- [ ] **Jangan Pernah Menggunakan Method File-System/Crypto Sinkron di Production Handler** (Haram: `fs.readFileSync`, `crypto.pbkdf2Sync`, `zlib.gzipSync`).
- [ ] **Batas Ukuran Payload JSON**: Batasi payload parser bawaan (`express.json({ limit: '100kb' })`). Parsing payload megabyte-scale secara sinkron di Main Thread akan langsung memblokir Call Stack selama puluhan milidetik.
- [ ] **Waspadai ReDoS (Regular Expression Denial of Service)**: Audit semua RegEx dengan tool audit static (misal `safe-regex`) untuk mencegah algoritma evaluasi eksponensial $O(2^n)$ yang mengunci event loop.
- [ ] **Terapkan Event Loop Utilization (ELU) Monitoring**: Jangan hanya bergantung pada Metrik CPU OS. CPU OS sering menipu; metrik ELU Node.js (`perf_hooks.eventLoopUtilization`) menunjukkan rasio waktu Main Thread aktif bekerja versus berstatus idle menunggu event. Nilai ELU di atas 85% adalah indikator mutlak perlunya horizontal scaling.
- [ ] **Konfigurasi Libuv Threadpool Sesuai Hardware**: Jika aplikasi Anda intensif menggunakan modul `crypto` bawaan atau `fs`, naikkan kapasitas pool sebelum aplikasi boot:
  ```bash
  export UV_THREADPOOL_SIZE=8
  ```

---

### 12. Hands-on Practice

Buat direktori dan struktur file berikut pada environment Anda:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install typescript @types/node tsx
npx tsc --init
```

#### Langkah 1: Buat Engine Monitoring Event Loop (`monitor.ts`)
Buat file `monitor.ts` untuk melacak lag dan utilitas loop secara presisi:
```typescript
// hands-on/m02/monitor.ts
import { monitorEventLoopDelay, eventLoopUtilization } from 'node:perf_hooks';

export function startMonitoring(intervalMs = 1000) {
  const histogram = monitorEventLoopDelay({ resolution: 20 });
  histogram.enable();
  let lastELU = eventLoopUtilization();

  const intervalId = setInterval(() => {
    const elu = eventLoopUtilization(lastELU);
    lastELU = elu;

    console.log('--- EVENT LOOP DIAGNOSTICS ---');
    console.log(`Utilization (ELU): ${(elu.utilization * 100).toFixed(2)}%`);
    console.log(`p50 Lag          : ${(histogram.percentile(50) / 1e6).toFixed(3)} ms`);
    console.log(`p90 Lag          : ${(histogram.percentile(90) / 1e6).toFixed(3)} ms`);
    console.log(`p99 Lag          : ${(histogram.percentile(99) / 1e6).toFixed(3)} ms`);
    console.log(`Max Lag          : ${(histogram.max / 1e6).toFixed(3)} ms\n`);
  }, intervalMs);

  return () => {
    clearInterval(intervalId);
    histogram.disable();
  };
}
```

#### Langkah 2: Buat Eksperimen Starvation vs. Time Slicing (`experiment.ts`)
Buat simulasi beban komputasi masif dan amati perbedaannya ketika menggunakan komputasi sinkron vs chunking time-slice:

```typescript
// hands-on/m02/experiment.ts
import { startMonitoring } from './monitor';

startMonitoring(500);

// Timer yang bertindak sebagai "Canary": Jika event loop sehat, ia mencetak pesan tepat waktu
setInterval(() => {
  console.log(`[CANARY TICK] Heartbeat: ${new Date().toISOString()}`);
}, 500);

// Algoritma simulasi komputasi array 20 juta iterasi
const TOTAL_ITERATIONS = 20_000_000;

function computeChunkSync() {
  console.log('[EXPERIMENT] Memulai Blocking Computation Sinkron...');
  let acc = 0;
  for (let i = 0; i < TOTAL_ITERATIONS; i++) {
    acc = (acc + Math.sqrt(i)) | 0;
  }
  console.log(`[EXPERIMENT] Selesai Blocking Sync. Result: ${acc}`);
}

function computeChunkCooperative(total: number, chunkSize = 1_000_000): Promise<number> {
  console.log('[EXPERIMENT] Memulai Non-Blocking Cooperative Computation...');
  return new Promise((resolve) => {
    let acc = 0;
    let currentIdx = 0;

    function step() {
      const limit = Math.min(currentIdx + chunkSize, total);
      for (; currentIdx < limit; currentIdx++) {
        acc = (acc + Math.sqrt(currentIdx)) | 0;
      }

      if (currentIdx < total) {
        // Berikan kesempatan Main Thread mengeksekusi I/O & Canary Timer
        setImmediate(step);
      } else {
        resolve(acc);
      }
    }

    step();
  });
}

async function run() {
  // Tunggu 1.5 detik agar monitor idle terlihat
  await new Promise((r) => setTimeout(r, 1500));

  // Jalankan Cooperative chunked
  await computeChunkCooperative(TOTAL_ITERATIONS);

  await new Promise((r) => setTimeout(r, 2000));

  // Jalankan Synchronous Blocking
  computeChunkSync();
}

run();
```

#### Langkah 3: Eksekusi dan Analisis
Jalankan menggunakan `npx tsx`:
```bash
npx tsx experiment.ts
```
**Perhatikan output:**
Saat `computeChunkCooperative` berjalan, Canary Heartbeat tetap mencetak log setiap ~500ms dan Event Loop Lag tetap di bawah 2ms. Saat `computeChunkSync` berjalan, Canary Heartbeat **terhenti total** selama beberapa detik, dan monitor melaporkan lonjakan Max Lag drastis.

---

### 13. Exercise

#### Level: Easy
**Tugas**: Prediksi output terminal dari kode berikut, kemudian verifikasi menggunakan `tsx`. Jelaskan mengapa outputnya demikian berdasarkan hirarki fase Libuv.

```typescript
// exercise-easy.ts
setImmediate(() => console.log('Immediate 1'));
setTimeout(() => console.log('Timeout 1'), 0);
Promise.resolve().then(() => console.log('Promise 1'));
process.nextTick(() => console.log('NextTick 1'));
```

<details>
<summary>Jawaban & Analisis Solusi</summary>

**Prediksi Output:**
```
NextTick 1
Promise 1
Timeout 1 (atau Immediate 1 tergantung inisialisasi proses)
Immediate 1 (atau Timeout 1)
```
**Analisis**:
`process.nextTick` selalu dikosongkan terlebih dahulu saat Call Stack saat ini kosong. Kemudian antrean Microtask Promise dieksekusi. Selanjutnya, Libuv memasuki loop. Jika script diparsing sebelum batas timer 1ms terlewati, `setImmediate` dapat berjalan sebelum timer; jika timer 1ms sudah terlewati saat loop start, `setTimeout` berjalan lebih dulu.
</details>

---

#### Level: Medium
**Tugas**: Buat fungsi `yieldThread()` berbasis Promise yang memungkinkan eksekusi fungsi `async` melepaskan giliran (*cooperative yield*) ke Event Loop Check Phase, sehingga I/O request lain dapat disisipkan di tengah loop async yang panjang.

```typescript
// exercise-medium.ts
export function yieldThread(): Promise<void> {
  // Implementasikan menggunakan setImmediate
}

// Penggunaan yang diharapkan:
async function processBatch(items: string[]) {
  for (let i = 0; i < items.length; i++) {
    // Lakukan komputasi
    if (i % 1000 === 0) {
      await yieldThread(); // Jangan blokir server
    }
  }
}
```

<details>
<summary>Jawaban & Analisis Solusi</summary>

```typescript
export function yieldThread(): Promise<void> {
  return new Promise((resolve) => {
    setImmediate(resolve);
  });
}
```
**Analisis**:
Menggunakan `setImmediate` di dalam resolusi Promise memastikan bahwa kelanjutan eksekusi fungsi generator/async ditangguhkan hingga Libuv Check Phase pada iterasi berikutnya, memberi kesempatan Poll Phase menangani I/O network baru.
</details>

---

#### Level: Hard
**Tugas**: Buat class `DebouncedAsyncQueue` yang mengonsumsi pekerjaan asinkron dan menjamin **maksimal satu pekerjaan yang dieksekusi dalam satu waktu**, dan jika ada panggilan baru yang masuk saat pekerjaan sedang aktif, panggilan tersebut di-debounce hingga interval waktu tertentu tanpa menggunakan `setTimeout` (harus disinkronkan dengan interval poll Libuv).

<details>
<summary>Jawaban & Analisis Solusi</summary>

```typescript
export class DebouncedAsyncQueue {
  private isProcessing = false;
  private pendingWork: (() => Promise<void>) | null = null;
  private immediateHandle: NodeJS.Immediate | null = null;

  public enqueue(work: () => Promise<void>): void {
    this.pendingWork = work;

    if (!this.isProcessing && !this.immediateHandle) {
      this.immediateHandle = setImmediate(() => {
        this.immediateHandle = null;
        this.processNext();
      });
    }
  }

  private async processNext(): Promise<void> {
    if (this.isProcessing || !this.pendingWork) return;

    this.isProcessing = true;
    const currentWork = this.pendingWork;
    this.pendingWork = null;

    try {
      await currentWork();
    } catch (err) {
      console.error('Queue execution error:', err);
    } finally {
      this.isProcessing = false;
      if (this.pendingWork) {
        this.immediateHandle = setImmediate(() => {
          this.immediateHandle = null;
          this.processNext();
        });
      }
    }
  }
}
```
</details>

---

### 14. Challenge

**Studi Kasus Arsitektur**: Rancang sistem **High-Performance In-Memory Cache with Async Write-Behind Engine** yang mampu menahan beban 100.000 RPS operasi tulis di Main Thread tanpa mendegradasi p99 latency di atas 5ms, dengan kriteria desain:
1. Operasi tulis cache ke memori lokal harus instan (O(1)).
2. Persistensi ke disk (simulasi penulisan file append-only) harus di-buffer dan di-flush secara asinkron.
3. Event loop tidak boleh mengalami *starvation* ketika buffer flush melakukan serialisasi jutaan kunci.
4. Jika buffer persistensi melampaui ambang batas memori kritis (Backpressure), sistem harus secara elegan menolak transaksi baru (Fail-Fast) sebelum memory heap V8 meledak (OOM).

*Instruksi*: Implementasikan purwarupa arsitektural ini menggunakan TypeScript modular, manfaatkan Node.js Streams, Worker Threads, atau Cooperative Async Iteration.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Fase manakah dalam Libuv Event Loop yang bertanggung jawab langsung untuk menangani callback dari `setImmediate()`?**
   - A. Poll Phase
   - B. Timers Phase
   - C. Check Phase
   - D. Pending Callbacks Phase

2. **Antrean manakah yang memiliki prioritas mutlak tertinggi saat Call Stack V8 kosong?**
   - A. `queueMicrotask`
   - B. `process.nextTick`
   - C. `setTimeout(fn, 0)`
   - D. `setImmediate`

3. **Berapa jumlah default thread pekerja di dalam `uv_threadpool` Libuv?**
   - A. 1
   - B. 2
   - C. 4
   - D. 8

4. **Operasi I/O manakah di Node.js yang TIDAK menggunakan Libuv worker thread pool, melainkan ditangani langsung secara asinkron oleh OS Kernel?**
   - A. `fs.readFile`
   - B. `crypto.scrypt`
   - C. Network Socket TCP/HTTP
   - D. `dns.lookup`

5. **Kapan V8 Engine menjalankan Microtask Queue?**
   - A. Hanya pada akhir siklus Event Loop lengkap.
   - B. Segera setelah Call Stack kosong, bahkan di antara eksekusi callback pada fase yang sama.
   - C. Hanya selama Idle Phase.
   - D. Tepat sebelum Timers Phase dievaluasi.

---

#### Bagian 2: Intermediate (5 Soal)
6. **Apa dampak utama dari pemanggilan rekursif tanpa henti dari `process.nextTick(() => recurse())` terhadap aplikasi Node.js?**
   - A. Melempar `Maximum call stack size exceeded`.
   - B. Memicu memory leak pada Libuv Thread Pool.
   - C. Terjadinya Event Loop Starvation; I/O dan Timer tidak pernah dieksekusi.
   - D. Node.js otomatis memindahkannya ke antrean `setImmediate`.

7. **Mengapa metrik CPU Utilization dari OS (misal: 25% CPU) dapat memberikan informasi yang keliru mengenai kesehatan performa aplikasi Node.js?**
   - A. Node.js selalu memakai 100% CPU secara virtual.
   - B. Main Thread bisa terblokir 100% pada satu core mesin multi-core (misal quad-core), sehingga rata-rata utilitas sistem hanya terbaca 25% meskipun server sudah unresponsive.
   - C. OS tidak dapat membaca metrik V8 Engine Isolate.
   - D. Garbage Collector berjalan di luar lingkup monitoring kernel.

8. **Apa perbedaan teknis mendasar antara `dns.lookup` dan `dns.resolve` di Node.js?**
   - A. `dns.lookup` menggunakan non-blocking I/O kernel, sedangkan `dns.resolve` memakai worker thread pool.
   - B. `dns.lookup` memanggil fungsi sinkronik `getaddrinfo(3)` di dalam Libuv thread pool; `dns.resolve` memakai c-ares library yang menggunakan asynchronous network socket langsung ke DNS server.
   - C. Tidak ada perbedaan teknis, keduanya identik.
   - D. `dns.resolve` diblokir oleh ukuran payload JSON.

9. **Apa fungsi dari method `.unref()` pada timer objek di Node.js (misal: `setTimeout(...).unref()`)?**
   - A. Membatalkan timer secara instan tanpa memicu callback.
   - B. Menginstruksikan Event Loop agar tidak mempertahankan proses Node.js tetap hidup jika hanya timer tersebut yang tersisa di antrean.
   - C. Memaksa timer untuk berjalan langsung di Worker Thread.
   - D. Menaikkan level prioritas timer menjadi setara `process.nextTick`.

10. **Metrik `eventLoopUtilization` (ELU) mengukur rasio antara:**
    - A. Jumlah Macrotask dibagi jumlah Microtask.
    - B. Waktu yang dihabiskan Event Loop untuk aktif mengeksekusi instruksi di Main Thread versus total waktu loop berjalan (aktif + idle).
    - C. Jumlah memori heap V8 terpakai terhadap batas alokasi `--max-old-space-size`.
    - D. Rasio request I/O yang berhasil versus yang gagal karena timeout.

---

#### Bagian 3: Skenario Kasus Produksi (3 Soal)

11. **Skenario Kasus A**:
    Layanan microservice e-commerce Anda mengalami penurunan throughput drastis saat memvalidasi otentikasi JWT yang menggunakan enkripsi asinkronus (`jose` atau `crypto.subtle`). Pemakaian CPU pada instance host tercatat 100% pada 4 core yang ada, padahal aplikasi hanya melayani 1.000 RPS. Setelah ditelusuri, pengembang tidak mengonfigurasi env variable runtime apapun.
    *Tindakan arsitektural mana yang paling tepat untuk mengoptimalkan throughput I/O dan komputasi kriptografi tersebut?*
    - A. Naikkan nilai `UV_THREADPOOL_SIZE` agar seimbang atau melebihi jumlah core sistem, dan isolasi operasi otentikasi ke service terpisah.
    - B. Ubah semua pemanggilan async menjadi method sinkron `crypto.*Sync` agar tidak memakan overhead promise.
    - C. Ganti seluruh arsitektur async menjadi rekursif `process.nextTick`.
    - D. Tambahkan `setImmediate` di setiap baris parsing string JWT.

12. **Skenario Kasus B**:
    Sebuah aplikasi finansial mendeteksi bahwa health check endpoint `/healthz` sering menghasilkan HTTP 504 Gateway Timeout selama periode batch reconciliation pada tengah malam. Log menunjukkan data diproses menggunakan loop:
    ```typescript
    for (const record of millionRecords) {
      await processRecord(record);
    }
    ```
    Di mana `processRecord` melakukan serangkaian transformasi data di memori tanpa I/O. Mengapa timeout terjadi dan bagaimana memperbaikinya secara definitif?
    - A. Node.js kehabisan file descriptors; solusinya adalah menaikkan `ulimit -n`.
    - B. Loop async tersebut tidak melepaskan Call Stack ke Libuv Poll/Check phase karena transformasi bersifat sinkron di antara penantian microtask; solusinya adalah menyisipkan cooperative yielding secara periodik menggunakan `setImmediate`.
    - C. Memory Leak pada V8 heap; solusinya adalah memanggil `global.gc()` setiap 100 iterasi.
    - D. Garbage Collector mematikan network thread; solusinya adalah mematikan GC via flag node `--no-gc`.

13. **Skenario Kasus C**:
    Anda mengamati lonjakan drastis pada grafik `p99.9 Event Loop Delay` setiap kali microservice menerima file upload gambar pengguna sebesar 15MB, meskipun penulisan file menggunakan Node.js Streams (`stream.pipeline`). Apa penyebab internal V8/Libuv dari fenomena tersebut?
    - A. Operasi transfer streaming socket memblokir Libuv Check phase secara mutlak.
    - B. Main Thread terblokir karena proses alokasi buffer biner berukuran besar dan operasi slicing/chunking memicu komputasi sinkron pada V8 Garbage Collector (Major GC Mark-Sweep phase).
    - C. Stream pipeline berjalan otomatis di thread terpisah sehingga terjadi thread contention.
    - D. HTTP parser bawaan Node.js mengeksekusi dekripsi chunk di dalam Microtask Queue.

---

#### Kunci Jawaban & Pembahasan Evaluasi

1. **C** — `setImmediate()` terikat secara eksklusif ke Check Phase dari Libuv Event Loop.
2. **B** — `process.nextTick` memiliki antrean internal independen yang selalu dikosongkan sebelum Microtask Queue Promise dan fase Libuv manapun.
3. **C** — Nilai bawaan Libuv threadpool adalah 4 thread.
4. **C** — Network socket menggunakan non-blocking OS system calls (`epoll` di Linux) yang dimultipleks langsung oleh Libuv di Poll Phase tanpa memakan resource threadpool.
5. **B** — Mengikuti spesifikasi ECMAScript dan implementasi Node.js modern, microtask checkpoints dijalankan segera setelah call stack kosong, bahkan di antara eksekusi dua callback berurutan dalam satu fase Libuv.
6. **C** — Rekursi `process.nextTick` mengisi antrean mikro tanpa henti, memblokir transisi Libuv ke Poll Phase atau fase lainnya.
7. **B** — Main thread Node.js bersifat single-threaded. Pada mesin dengan 4 core, satu core yang terblokir 100% hanya akan menunjukkan utilitas total 25% di task manager OS, padahal kapasitas layanan aplikasi sudah lumpuh total.
8. **B** — `dns.lookup` memanggil C API bawaan OS `getaddrinfo` yang bersifat sinkron sehingga harus didelegasikan ke Libuv thread pool; sedangkan `dns.resolve` menggunakan socket networking non-blocking via c-ares.
9. **B** — `.unref()` memberitahu event loop untuk mengabaikan handle aktif tersebut saat mengevaluasi apakah proses harus keluar (*terminate*).
10. **B** — Definisi resmi Event Loop Utilization adalah perbandingan waktu kerja aktif Main Thread terhadap total waktu wall-clock interval yang diukur.
11. **A** — Operasi kriptografi bawaan Libuv terikat pada `uv_threadpool`. Mengatur `UV_THREADPOOL_SIZE` ke angka optimal (misal sejumlah vCPU atau lebih) mencegah bottleneck antrean threadpool.
12. **B** — Walaupun fungsi bertanda `async`, operasi komputasi murni tanpa pemanggilan I/O eksternal hanya menghasilkan microtask chains yang terus memonopoli Main Thread tanpa memberikan kesempatan Libuv mengeksekusi network polling untuk request `/healthz`. Solusinya adalah cooperative time-slicing via `setImmediate`.
13. **B** — Mengalirkan data berukuran puluhan megabyte dalam kecepatan tinggi menciptakan jutaan objek Buffer sementara. Hal ini memicu V8 GC Scavenge dan Major Mark-Sweep yang menghentikan eksekusi kode pengguna (*Stop-the-World pauses*), yang terukur langsung sebagai lonjakan Event Loop Delay.

---

### 16. Summary

1. **Model Konkurensi Hibrida**: Node.js menggabungkan V8 Isolate (Call Stack tunggal dan Microtask queue) dengan Libuv Event Loop (6 fase terstruktur dan Thread Pool) untuk menangani konkurensi masif secara efisien.
2. **Hirarki Prioritas Deterministik**: Call Stack $\rightarrow$ `process.nextTick` $\rightarrow$ Microtasks (Promise) $\rightarrow$ Libuv Phase Callbacks (Timers $\rightarrow$ Pending $\rightarrow$ Poll $\rightarrow$ Check $\rightarrow$ Close). Setiap penyelesaian callback di fase manapun akan langsung memicu *draining* antrean microtask.
3. **Penyebab Latency Terbesar**: Event Loop Starvation dan Event Loop Lag yang disebabkan oleh eksekusi kode sinkron CPU-bound, deserialisasi data masif, atau unbounded microtask recursion.
4. **Strategi Mitigasi Teruji**:
   - Terapkan *Cooperative Scheduling / Time-Slicing* (`setImmediate`) untuk task CPU yang masih dapat ditoleransi di Main Thread.
   - Pindahkan komputasi CPU intensif ke `Worker Threads` menggunakan komunikasi zero-copy.
   - Gunakan `monitorEventLoopDelay` dan `eventLoopUtilization` (ELU) sebagai indikator kesehatan utama layanan di produksi, bukan sekadar metrik CPU host.