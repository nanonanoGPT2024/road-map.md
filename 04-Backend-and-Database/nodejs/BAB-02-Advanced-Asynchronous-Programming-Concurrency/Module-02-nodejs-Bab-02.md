# BAB 02: Advanced Asynchronous Programming & Concurrency
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedah (Analyze & Deconstruct)** siklus hidup Libuv Event Loop hingga level system call OS (`epoll`, `kqueue`, `IOCP`) serta mekanisme microtask draining V8 engine.
- **Mengimplementasikan (Implement)** propagasi konteks transaksi terdistribusi secara *zero-leak* menggunakan `AsyncLocalStorage` melintasi *asynchronous boundaries*.
- **Membangun (Architect)** arsitektur konkurensi CPU-bound dan I/O-bound hibrida menggunakan `Worker Threads`, `SharedArrayBuffer`, dan primitif `Atomics` tanpa memory corruption atau race condition.
- **Mengontrol (Control & Mitigate)** backpressure, throughput throttling, dan starvation pada antrean asynchronous menggunakan custom concurrency pools dan `AbortController`.
- **Mendiagnosis (Profile & Debug)** event loop latency, thread pool exhaustion, serta microtask starvation menggunakan dynamic tracing tools (`perf`, `clinic.js`, dan Node.js internal diagnostics).

---

### 2. Prerequisites
Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Node.js Core Fundamentals**: Runtime model, dynamic module loader (ESM & CJS), dan Node.js Event Emitter pattern.
- **Dasar Pemrograman Asinkron**: Sintaks dasar `Promise`, `async/await`, callback pattern, dan chaining.
- **Konsep Sistem Operasi**: Virtual memory, process vs thread context switching, file descriptor (FD), serta socket programming dasar.
- **Bahasa Pemrograman**: JavaScript modern (ES2022+) atau TypeScript tingkat menengah (Type Narrowing, Generics).

---

### 3. Concept & Internal Architecture

Node.js bukanlah platform single-threaded secara murni. Node.js mengeksekusi JavaScript pada single thread (V8 Main Thread), namun mendelegasikan I/O intensif dan operasi sistem blocking ke abstraksi C/C++ tingkat rendah yang dikelola oleh **Libuv** dan thread pool internal sistem operasi.

```
+-----------------------------------------------------------------------+
|                           V8 Engine (Main Thread)                     |
|  +-----------------------------------------------------------------+  |
|  | Call Stack (JS Execution Frame)                                 |  |
|  +-----------------------------------------------------------------+  |
|  | Microtask Queue:                                                |  |
|  | [ process.nextTick ] -> [ Promise.then / queueMicrotask ]       |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------^-----------------------------------+
                                    |
                            (Tick Boundary)
                                    |
+-----------------------------------v-----------------------------------+
|                         Libuv Event Loop Thread                       |
|                                                                       |
|  1. Timers Phase          -> setTimeout, setInterval                  |
|     * Drains Microtasks                                               |
|  2. Pending Callbacks     -> I/O system errors (ECONNREFUSED, dll.)   |
|     * Drains Microtasks                                               |
|  3. Idle, Prepare         -> Libuv internal operations                |
|     * Drains Microtasks                                               |
|  4. Poll Phase            -> Retrieve I/O events (epoll/kqueue)       |
|     * Drains Microtasks                                               |
|  5. Check Phase           -> setImmediate callbacks                   |
|     * Drains Microtasks                                               |
|  6. Close Callbacks       -> socket.on('close'), handle terminations  |
|     * Drains Microtasks                                               |
+------------------+----------------------------------+-----------------+
                   |                                  |
                   v                                  v
     +--------------------------+       +-----------------------------+
     |   OS Non-Blocking I/O    |       |   Libuv Worker Pool         |
     |   (Kernel Demuxing)      |       |   (Default: 4 Threads)      |
     +--------------------------+       +-----------------------------+
     | - Epoll (Linux)          |       | - File System I/O           |
     | - Kqueue (macOS/BSD)     |       | - DNS Lookups (getaddrinfo) |
     | - IOCP (Windows)         |       | - Crypto (pbkdf2, random)   |
     | (Network Sockets, Pipes) |       | - Compression (zlib)        |
     +--------------------------+       +-----------------------------+
```

#### A. Microtask vs Macrotask Queue Draining
Semenjak Node.js v11, semantik pengeksekusian antrean diselaraskan dengan browser HTML5 spec:
1. `process.nextTick()` ditempatkan pada **Next-Tick Queue**.
2. Resolusi `Promise` dan `queueMicrotask()` ditempatkan pada **Promise Microtask Queue**.
3. *Next-Tick Queue* selalu diproses secara eksklusif sebelum *Promise Microtask Queue*.
4. Microtasks dieksekusi **segera setelah setiap callback selesai**, bukan menunggu Libuv menyelesaikan seluruh fase (berlaku di semua fase: Timers, Poll, Check, dll). Jika microtask terus-menerus memicu microtask baru, Event Loop akan mengalami **Microtask Starvation** dan macet total.

#### B. Libuv Worker Pool Mechanics
Operasi seperti pembacaan filesystem lokal (`fs.readFile`) tidak memiliki antarmuka asinkronus non-blocking yang seragam di seluruh kernel Unix (Linux AIO memiliki limitasi signifikan terhadap buffering). Libuv menyelesaikan ini dengan **Worker Thread Pool** (ukuran default dikontrol via environment variable `UV_THREADPOOL_SIZE=4`, maksimal 1024).

Alur delegasi:
1. JS memanggil `fs.promises.readFile()`.
2. V8 menginstruksikan C++ binding Node.js (`src/node_file.cc`).
3. Node.js membuat instance `uv_work_t` dan memanggil `uv_queue_work()`.
4. Pekerjaan masuk ke antrean FIFO thread pool. Salah satu thread worker mengambil request, memblokir thread pada pemanggilan synchronous C read, lalu meletakkan hasilnya kembali ke loop event.
5. Libuv memicu callback di Main Thread melalui fase *Poll/Pending Callbacks*.

#### C. Asynchronous Context Tracking (`AsyncLocalStorage`)
Untuk pelacakan konteks terdistribusi (seperti Transaction Tracing / Correlation ID), callback asynchronous memecah stack trace tradisional. Node.js memanfaatkan **AsyncWrap bindings** internal yang memonitor *resource initialization*, *before callback*, *after callback*, dan *destroy*. `AsyncLocalStorage` memanfaatkan lifecycle hook ini untuk mengaitkan memori konteks spesifik ke alur eksekusi asinkron tanpa *explicit parameter drilling*.

---

### 4. Why & What

| Fitur / Paradigma | Mengapa Diperlukan? | Apa Masalah yang Diselesaikan? |
| :--- | :--- | :--- |
| **Non-blocking Poll Phase** | Menangani puluhan ribu koneksi TCP konkuren dengan konsumsi memori rendah (tanpa 1 thread per koneksi). | C10K/C1000K problem, overhead context-switching thread kernel. |
| **Worker Threads** | Mengeksekusi kalkulasi matematis berat/kriptografi custom tanpa memblokir I/O throughput. | Menghindari Main Thread Event Loop stalling/lag. |
| **AsyncLocalStorage** | Meneruskan metadata audit, distributed tracing ID, dan konteks multi-tenant. | Menghilangkan polusi signatures fungsi (*drilling*) dan kebocoran memori akibat variabel global. |
| **AbortController** | Menghentikan eksekusi operasi downstream jika client membatalkan request atau batas timeout tercapai. | Resource leakage, dangling database transactions, compute waste. |
| **Atomics & SharedArrayBuffer** | Berbagi struktur data memori secara instan antar worker tanpa serialisasi JSON/structuredClone. | Zero-copy concurrency, overhead serialisasi IPC (Inter-Process Communication). |

---

### 5. How (Workflow Execution Engine)

Langkah demi langkah pengeksekusian operasi asinkron:
1. **Inisiasi Task**: Kode JS memicu `crypto.pbkdf2` dan `fetch('https://api.internal')`.
2. **Pemisahan Jalur Delegasi**:
   - `crypto.pbkdf2`: Didaftarkan ke Libuv Thread Pool via `uv_work_t`.
   - `fetch`: Membuka non-blocking socket file descriptor dan didaftarkan langsung ke kernel event loop mechanism (`epoll_ctl` dengan event `EPOLLIN | EPOLLOUT`).
3. **Execution Pause & Interleaved Execution**: Main thread terus mengeksekusi instruksi synchronous lainnya hingga Call Stack kosong.
4. **Microtask Interception**: Jika ada `Promise.resolve().then(...)`, eksekusi segera mengosongkan microtask queue sebelum melangkah ke tick berikutnya.
5. **Poll Waiting**: Libuv menghitung timeout minimum dari active timers, lalu memanggil `epoll_wait(..., timeout)`. Thread tertidur secara efisien di level OS hingga event socket siap atau timer terdekat habis.
6. **Notification Re-entry**: Kernel membangunkan Libuv main thread. Worker pool yang menyelesaikan kriptografi menginjeksikan hasilnya ke antrean I/O event. Callback dieksekusi di V8 Main Thread.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dapur Restoran Bintang Lima:
- **Main Thread (Kepala Pelayan & Kasir)**: Satu-satunya individu yang mencatat pesanan dari pelanggan (klien) dan menyerahkan nota ke dapur. Sangat cepat, ramah, tetapi jika dia mulai memasak sup sendiri (CPU bound task), antrean pelanggan di depan pintu akan terbengkalai.
- **Microtask Queue (Catatan Mendesak Kepala Pelayan)**: Memo koreksi langsung di saku pelayan. Setiap kali pelayan selesai melayani satu meja, dia WAJIB menyelesaikan memo di sakunya terlebih dahulu sebelum berjalan ke meja berikutnya.
- **Libuv Thread Pool (Koki Dapur Khusus)**: 4 asisten (secara default) yang mengerjakan tugas berat: memotong daging, menguleni adonan (File I/O, hashing).
- **Kernel Demuxer (epoll/kqueue) (Lonceng Otomatis Meja)**: Sensor otomatis nirkabel yang berbunyi ketika gelas pelanggan kosong. Pelayan tidak perlu berdiri menunggu di depan meja pelanggan.

#### Diagram Transisi Aliran Event Loop & Execution Stack:

```
               [ Call Stack JS Kosong? ]
                          │
            Ya ───────────┴─────────── Tidak ──> Eksekusi Frame JS Teratas
            │
            ├─> [ Ada Next-Tick Queue? ] ──Ya──> Drain process.nextTick()
            │                                           │
            ├─> [ Ada Microtask Queue? ] ──Ya──> Drain Promise Microtasks
            │
            ▼
    [ Fase Libuv Aktif ] ──> (Timers -> Pending -> Poll -> Check -> Close)
            │
     Ambil 1 Callback
            │
            ▼
    Eksekusi Callback
            │
            ▼
   [ Microtasks Muncul? ] ──Ya──> DRAIN KESELURUHAN SEGERA
            │
            ▼
    Callback Selesai -> Lanjut ke Callback Berikutnya dalam Fase Tersebut
```

---

### 7. Simple & Practical Examples

#### Contoh 1: Prioritas Draining Microtask vs Macrotask (Sederhana)

```typescript
// microtask-order.ts
import { stdout } from 'node:process';

function log(msg: string): void {
  stdout.write(`${msg}\n`);
}

log('1. Synchronous Start');

setTimeout(() => {
  log('2. Timer Callback 1');
  Promise.resolve().then(() => log('3. Microtask di dalam Timer 1'));
}, 0);

setImmediate(() => {
  log('4. Check (setImmediate) Phase');
});

Promise.resolve().then(() => {
  log('5. Microtask Promise Root');
});

process.nextTick(() => {
  log('6. Next-Tick Root Priority');
});

log('7. Synchronous End');

/* OUTPUT:
1. Synchronous Start
7. Synchronous End
6. Next-Tick Root Priority
5. Microtask Promise Root
2. Timer Callback 1
3. Microtask di dalam Timer 1
4. Check (setImmediate) Phase
*/
```

#### Contoh 2: High-Performance Concurrent Batch Processor dengan AbortController & AsyncLocalStorage (Praktikal Enterprise)

```typescript
// transaction-processor.ts
import { AsyncLocalStorage } from 'node:async_hooks';
import { randomUUID } from 'node:crypto';

interface TransactionContext {
  traceId: string;
  userId: string;
  startTime: bigint;
}

interface PaymentJob {
  id: string;
  amount: number;
}

interface ProcessingResult {
  jobId: string;
  status: 'SUCCESS' | 'FAILED' | 'ABORTED';
  durationMs: number;
  error?: string;
}

// 1. Context Propagation Container
const contextStore = new AsyncLocalStorage<TransactionContext>();

export class DistributedPaymentEngine {
  private activeConcurrency = 0;

  constructor(private readonly maxConcurrency: number) {}

  public async executePipeline(
    userId: string,
    jobs: PaymentJob[],
    globalTimeoutMs: number
  ): Promise<ProcessingResult[]> {
    const traceId = randomUUID();
    const abortController = new AbortController();
    const timeoutHandle = setTimeout(() => {
      abortController.abort(new Error(`Timeout limit reached (${globalTimeoutMs}ms)`));
    }, globalTimeoutMs);

    const initialContext: TransactionContext = {
      traceId,
      userId,
      startTime: process.hrtime.bigint(),
    };

    try {
      // Menjalankan array jobs dalam isolasi konteks asinkron
      return await contextStore.run(initialContext, async () => {
        return await this.processBatches(jobs, abortController.signal);
      });
    } finally {
      clearTimeout(timeoutHandle);
    }
  }

  private async processBatches(
    jobs: PaymentJob[],
    signal: AbortSignal
  ): Promise<ProcessingResult[]> {
    const results: ProcessingResult[] = [];
    const pool: Promise<void>[] = [];

    for (const job of jobs) {
      if (signal.aborted) {
        results.push({
          jobId: job.id,
          status: 'ABORTED',
          durationMs: 0,
          error: (signal.reason as Error)?.message || 'Operation Aborted',
        });
        continue;
      }

      // Concurrency Gate: Kontrol concurrency throttling tanpa external library
      if (this.activeConcurrency >= this.maxConcurrency) {
        await Promise.race(pool);
      }

      this.activeConcurrency++;
      const jobExecution = this.processSingleJob(job, signal)
        .then((res) => {
          results.push(res);
        })
        .finally(() => {
          this.activeConcurrency--;
          // Bersihkan promise yang sudah selesai dari active pool
          const index = pool.indexOf(jobExecution);
          if (index !== -1) {
            pool.splice(index, 1);
          }
        });

      pool.push(jobExecution);
    }

    // Tunggu sisa transaksi yang sedang berjalan
    await Promise.allSettled(pool);
    return results;
  }

  private async processSingleJob(
    job: PaymentJob,
    signal: AbortSignal
  ): Promise<ProcessingResult> {
    const start = process.hrtime.bigint();
    const ctx = contextStore.getStore();

    if (!ctx) {
      throw new Error('Fatal: Transaction Context Starvation/Lost!');
    }

    return new Promise<ProcessingResult>((resolve) => {
      // Event listener penghentian instan
      const abortListener = () => {
        const deltaMs = Number(process.hrtime.bigint() - start) / 1_000_000;
        resolve({
          jobId: job.id,
          status: 'ABORTED',
          durationMs: deltaMs,
          error: (signal.reason as Error)?.message || 'Aborted via signal',
        });
      };

      if (signal.aborted) {
        return abortListener();
      }

      signal.addEventListener('abort', abortListener, { once: true });

      // Mensimulasikan I/O interaksi perbankan terdistribusi
      const latency = Math.floor(Math.random() * 80) + 20;
      setTimeout(() => {
        signal.removeEventListener('abort', abortListener);
        const deltaMs = Number(process.hrtime.bigint() - start) / 1_000_000;
        
        // Simulasi error acak
        if (job.amount < 0) {
          resolve({
            jobId: job.id,
            status: 'FAILED',
            durationMs: deltaMs,
            error: 'Invalid amount validation failure',
          });
          return;
        }

        resolve({
          jobId: job.id,
          status: 'SUCCESS',
          durationMs: deltaMs,
        });
      }, latency);
    });
  }
}
```

---

### 8. Real-World Case Study: High-Throughput Financial Ledger Synchronization

#### Konteks & Skala
Sebuah bank digital memproses rekonsiliasi mutasi rekening internal dengan beban **15.000 batch/detik**. Setiap batch membutuhkan verifikasi tanda tangan kriptografi (Ed25519/Secp256k1) dan persistensi ke storage terdistribusi.

#### Akar Masalah Arsitektur Lama
Implementasi awal memproses batch secara asynchronous menggunakan `Promise.all()` standar pada Node.js Main Thread.
- **Bottleneck 1**: Pemanggilan enkripsi non-native di JavaScript membekukan V8 Main Thread selama 200–400ms per batch.
- **Bottleneck 2**: `Promise.all(15000)` menginstansiasi objek Promise secara masif sekaligus, menyebabkan **V8 Heap Spike** (>1.5 GB), memory fragmentation, dan triggering `Scavenge` & `Mark-Sweep` Garbage Collection pauses hingga 800ms.
- **Bottleneck 3**: Event Loop Lag melonjak drastis dari 2ms ke 1.200ms, memicu health check Kubernetes `readinessProbe` gagal (pod restart loop / crash looping).

#### Solusi Arsitektur Produksi Terintegrasi
1. **CPU Offloading via Worker Pool & SharedArrayBuffer**:
   Membangun Thread Pool berbasis `worker_threads` khusus kriptografi. Payload transaksi dialokasikan sekali ke dalam `SharedArrayBuffer`, worker memverifikasi byte secara zero-copy menggunakan `Atomics` semaphore tanpa serialisasi JSON.
2. **Backpressure Stream-Driven Batching**:
   Mengganti `Promise.all` masif dengan pipeline `AsyncIterable` dengan watermark konkurensi terkontrol (sliding window).
3. **Observabilitas Real-Time**:
   Monitoring Event Loop Delay via `perf_hooks.monitorEventLoopDelay`.

#### Arsitektur Mutasi Terdistribusi:

```
[ Ingestion Stream ] 
        │
        ▼ (Fixed Concurrency Gate: Max 200 in-flight)
[ Dynamic Sliding Window Engine ]
        │
        ├── (Payload Zero-Copy) ──> [ SharedArrayBuffer (Data Ring) ]
        │                                  │
        │                        ┌─────────┴─────────┐
        │                        ▼                   ▼
        │                [ Worker Thread 1 ] [ Worker Thread 2 ] ... (Crypto)
        │                        │                   │
        │                        └─────────┬─────────┘
        │                                  ▼
        ├── (Wait Non-blocking) <── [ Atomics.waitAsync ]
        │
        ▼ (Non-blocking I/O Stream)
[ Persist ke CockroachDB / Raft Log via Kernel epoll ]
```

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Biaya / Kerugian | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- |
| **Worker Threads** | Mencegah blokade Main Thread pada komputasi CPU intensif. Menjaga latensi I/O tetap stabil. | Memory overhead (~30MB base RAM per worker). Overhead transfer data jika tidak pakai `SharedArrayBuffer`. | Enkripsi data, parsing CSV raksasa (>500MB), rendering PDF, komputasi AI/ML lokal. |
| **Cluster Module (Multi-Process)** | Isolasi total (memori terpisah), crash pada 1 child process tidak mematikan seluruh instance. Menggunakan seluruh core CPU dengan mudah. | Inter-Process Communication (IPC) sangat mahal karena melalui socket internal (serialisasi JSON). Penggunaan memori tinggi. | Web API server standar I/O-bound tanpa shared in-memory state. |
| **Single Thread + Epoll I/O** | Overhead memori sangat rendah, tidak ada overhead context-switching thread, latensi ultra-rendah untuk I/O murni. | Satu loop CPU intensif yang ceroboh akan melumpuhkan seluruh traffic instance. | Gateway routing, API Orchestrator, real-time WebSockets. |
| **AsyncLocalStorage** | Clean architecture, decoupling propagasi konteks, logging terisolasi otomatis. | Slight throughput degradation (~3-8% CPU overhead pada micro-benchmarks intensif). Risiko leak jika context store dipegang secara referensial. | Distributed Tracing (OpenTelemetry), Audit log context, User Session scope. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Microtask Starvation via Recursive `process.nextTick`
*Penyebab*: Pemanggilan rekursif `process.nextTick` menyebabkan kontrol eksekusi tidak pernah kembali ke fase Libuv (I/O, timer, network starvation).
```typescript
// SANGAT BERBAHAYA: Jangan lakukan ini di production
function infiniteNextTick() {
  process.nextTick(infiniteNextTick);
}
infiniteNextTick(); 
// Hasil: Node.js tidak akan pernah memproses I/O, koneksi HTTP baru, atau timers!
```
*Solusi*: Gunakan `setImmediate` jika perlu melepaskan kontrol ke Event Loop kembali, atau batasi iterasi loop per tick.

#### 2. Event Loop Lag karena JSON.parse / JSON.stringify Ukuran Raksasa
*Gejala*: API mendadak timeout dengan status 504. Metrik CPU pod melonjak ke 100% tanpa adanya traffic spike.
*Diagnosa*: Jalankan Node.js dengan `--trace-event-loop-lag`.
*Solusi*: Gunakan stream parsing (`JSONStream` atau `oboe.js`) atau parsing payload raksasa di dalam Worker Thread.

#### 3. Unbounded `Promise.all` Memory Explosion
*Penyebab*:
```typescript
// BAD: Jika items berisi 100.000 elements, 100.000 Promises diinstansiasi secara simultan
await Promise.all(items.map(async (item) => processDb(item)));
```
*Solusi*: Terapkan Concurrency Limiter (misalnya mengimplementasikan Sliding Window Pool atau memakai library `p-limit`).

#### Panduan Troubleshooting Produksi:
1. **Deteksi Lag**: Gunakan `perf_hooks`:
   ```typescript
   import { monitorEventLoopDelay } from 'node:perf_hooks';
   const h = monitorEventLoopDelay({ resolution: 20 });
   h.enable();
   setInterval(() => {
     console.log(`Event Loop Lag (p99): ${h.percentile(99) / 1e6}ms`);
     h.reset();
   }, 5000);
   ```
2. **Kondisi Thread Pool Exhaustion**: Jika `fs` atau `crypto` melambat padahal CPU rendah, naikkan kapasitas thread pool via environment variable sebelum proses berjalan:
   ```bash
   export UV_THREADPOOL_SIZE=64
   node dist/index.js
   ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Konfigurasi Libuv Thread Pool**: Selalu atur `UV_THREADPOOL_SIZE` sesuai jumlah core dan estimasi synchronous C-blocking requests (disarankan setara jumlah logical core x 2 untuk high-load disk I/O, min. default dinaikkan ke 16/32).
- [ ] **Signal Cancellation Terintegrasi**: Wajib menyediakan `AbortSignal` pada seluruh client call (Database query, Axios/Fetch HTTP requests, Redis locks).
- [ ] **Observabilitas Event Loop**: Export metrik Event Loop Delay (p50, p95, p99) langsung ke Prometheus via OpenTelemetry runtime metrics.
- [ ] **No Unbounded Memory Concurrency**: Hindari memproses unbounded array dengan `Promise.all`. Gunakan sliding concurrency window (maksimum 50-100 konkurensi paralel per worker).
- [ ] **Memory Management Worker Threads**: Saat menggunakan `Worker`, hindari instansiasi worker berulang per-request (`new Worker()`). Gunakan pooling pattern tetap (*fixed-size pre-warmed worker pool*).
- [ ] **Hindari kebocoran AsyncLocalStorage**: Pastikan tidak menyimpan pointer mutabel besar yang hidup lebih lama dari lifecycle context request.

---

### 12. Hands-on Practice

Buatlah direktori praktikum terstruktur dan implementasikan simulasi worker-thread offloader dengan memory zero-copy.

#### Setup Struktur Proyek
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install typescript @types/node tsx --save-dev
npx tsc --init
```

Ubah file `package.json` untuk mengaktifkan type module:
```json
{
  "name": "m02-advanced-concurrency",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "start": "tsx src/main.ts"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "tsx": "^4.7.0",
    "typescript": "^5.3.3"
  }
}
```

#### Step 1: Buat Worker File (`hands-on/m02/src/worker.ts`)
```typescript
import { parentPort } from 'node:worker_threads';

if (!parentPort) {
  throw new Error('Script ini harus diinisialisasi sebagai Worker Thread!');
}

parentPort.on('message', (buffer: SharedArrayBuffer) => {
  // Parsing int32 array view di atas shared memory
  const sharedArray = new Int32Array(buffer);
  
  // Melakukan kalkulasi berat matematis / CPU Bound
  for (let i = 0; i < sharedArray.length; i++) {
    // Simulasi enkripsi / mutasi kalkulasi in-place
    sharedArray[i] = (sharedArray[i] * 3) ^ 0x5a5a;
  }

  // Kirim notifikasi balik tanpa data payload (Zero-Copy Notification)
  parentPort?.postMessage({ status: 'COMPLETED', length: sharedArray.length });
});
```

#### Step 2: Buat Main Orchestrator (`hands-on/m02/src/main.ts`)
```typescript
import { Worker } from 'node:worker_threads';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { monitorEventLoopDelay } from 'node:perf_hooks';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

async function runZeroCopyConcurrency() {
  const histogram = monitorEventLoopDelay({ resolution: 10 });
  histogram.enable();

  console.log('[Orchestrator] Mengalokasikan 10 Juta 32-bit Integers ke SharedArrayBuffer...');
  const TOTAL_ELEMENTS = 10_000_000;
  
  // Mengalokasikan shared memory buffer (4 bytes per 32-bit integer = ~40MB)
  const sharedBuffer = new SharedArrayBuffer(TOTAL_ELEMENTS * Int32Array.BYTES_PER_ELEMENT);
  const localView = new Int32Array(sharedBuffer);

  // Inisialisasi data
  for (let i = 0; i < TOTAL_ELEMENTS; i++) {
    localView[i] = i;
  }

  console.log(`[Orchestrator] Sampel data sebelum diolah: [${localView[0]}, ${localView[1]}, ${localView[2]}]`);

  const workerPath = resolve(__dirname, 'worker.ts');
  // Membuka Worker Thread via tsx loader
  const worker = new Worker(
    `import('tsx/esm').then(() => import('${workerPath.replace(/\\/g, '/')}'))`,
    { eval: true }
  );

  const startHr = process.hrtime.bigint();

  // Kirim SharedArrayBuffer reference via postMessage
  worker.postMessage(sharedBuffer);

  await new Promise<void>((res) => {
    worker.on('message', (msg) => {
      const endHr = process.hrtime.bigint();
      const executionTimeMs = Number(endHr - startHr) / 1_000_000;

      console.log(`[Worker Result]:`, msg);
      console.log(`[Orchestrator] Total Execution Time: ${executionTimeMs.toFixed(2)}ms`);
      console.log(`[Orchestrator] Sampel data sesudah diolah: [${localView[0]}, ${localView[1]}, ${localView[2]}]`);
      res();
    });
  });

  await worker.terminate();
  histogram.disable();

  console.log(`[Metrics] Event Loop Lag p99: ${(histogram.percentile(99) / 1e6).toFixed(3)}ms`);
}

runZeroCopyConcurrency().catch(console.error);
```

#### Jalankan Praktikum:
```bash
npm start
```

---

### 13. Exercises

#### Level Easy
Buatlah fungsi `sleep(ms: number, signal?: AbortSignal): Promise<void>` yang menunda eksekusi selama `ms` milidetik menggunakan `setTimeout`. Jika `signal` dipicu sebelum waktu timeout habis, promise harus reject seketika dengan `signal.reason` tanpa membiarkan timer menggantung di event loop.
- *Kriteria Evaluasi*: Timer dibersihkan menggunakan `clearTimeout` saat abort terjadi untuk mencegah memory leak.

#### Level Medium
Buat class `AsyncPriorityQueue<T>` yang memproses task asynchronous dengan batas konkurensi $N$ (misal $N=3$). Setiap item memiliki level prioritas (`HIGH`, `MEDIUM`, `LOW`). Task prioritas tinggi harus selalu mendahului antrean prioritas rendah yang belum dieksekusi.
- *Kriteria Evaluasi*: Tidak menggunakan third-party library, microtask scheduling tidak boleh menyebabkan starvation pada task prioritas rendah (gunakan starvation aging counter).

#### Level Hard
Rancang dan bangun class `CircuitBreakerClient` yang membungkus pemanggilan I/O berbasis asynchronous. Sistem harus memiliki:
1. Status: `CLOSED`, `OPEN`, `HALF-OPEN`.
2. Tracking kegagalan berbasis *Sliding Time Window* (10 detik terakhir).
3. Fallback mechanism otomatis.
4. Penggunaan `monitorEventLoopDelay` di mana jika p95 Event Loop Delay melampaui 100ms, circuit breaker otomatis beralih ke `OPEN` mode untuk melindungi service dari *self-inflicted cascading failure*.
- *Kriteria Evaluasi*: Concurrency-safe, resolusi timer efisien, zero memory leaks pada event listeners.

---

### 14. Enterprise Production Challenge

**Deskripsi Kasus Nyata**:
Anda adalah Principal Backend Engineer di bursa aset kripto. Anda menghadapi insiden produksi P0: Server gateway mengalami **Memory Out-Of-Memory (OOM) Crash** secara berkala setiap kali market mengalami volatilitas ekstrem. 

**Kondisi Lapangan**:
1. WebSocket feed menerima 120.000 order cancellations per detik dari institutional market makers.
2. Setiap order cancellation membutuhkan validasi signature via library libsodium C++ bindings yang bersifat synchronous, lalu menulis pembatalan ke storage via `ioredis`.
3. Event loop latency melonjak ke 4.5 detik. Akibatnya, health-check HTTP internal gagal merespons, dan cluster orchestrator (Kubernetes) menghentikan kontainer.
4. Selama spike, alokasi buffer internal Node.js untuk incoming network traffic membengkak tanpa kendali hingga server kehabisan swap memory.

**Tugas Arsitektur**:
Rancang blueprint teknis arsitektur processing pipeline di Node.js untuk menyelesaikan masalah ini. Blueprint harus memuat:
- Pola intervensi backpressure dari level socket stream hingga processing worker.
- Mekanisme pembagian komputasi antara Main Thread, Worker Threads, dan OS thread pool.
- Algoritma load-shedding yang menjamin graceful degradation (menolak request baru tanpa menjatuhkan server).
- Estimasi perbandingan footprint memori sebelum dan sesudah optimasi.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa `process.nextTick()` secara teknis bukan bagian dari fase siklus Libuv Event Loop?
2. Apa yang menentukan jumlah thread default yang dialokasikan di Libuv Worker Pool, dan bagaimana cara memodifikasinya di environment container?
3. Apa perbedaan mendasar antara eksekusi callback di `setImmediate()` vs `setTimeout(fn, 0)` saat dipanggil di dalam konteks I/O cycle (misal di dalam callback `fs.readFile`)?
4. Mengapa operasi kriptografi seperti `crypto.pbkdf2` tidak memblokir V8 Main Thread secara default?
5. Apa konsekuensi teknis jika kita tidak melakukan `clearTimeout` saat menggunakan `AbortController` timeout pattern pada request yang telah selesai lebih awal?

#### B. Pertanyaan Intermediate
6. Jelaskan perubahan arsitektur penanganan Microtask Draining yang diperkenalkan pada Node.js v11 dibanding versi sebelumnya (Node.js v10 ke bawah)!
7. Pada kondisi seperti apa `AsyncLocalStorage` dapat menyebabkan kebocoran memori (Memory Leak) pada service transaksi perbankan dengan throughput tinggi?
8. Mengapa pengiriman data berukuran 200MB antar Worker Thread via default `postMessage` dapat memicu spike latency yang tinggi, dan bagaimana `SharedArrayBuffer` menyelesaikan masalah tersebut?
9. Apa yang terjadi di level kernel Linux (`epoll`) ketika Libuv Event Loop berada pada fase Poll dan Call Stack sedang kosong tanpa timer aktif?
10. Bagaimana `Atomics.wait()` dan `Atomics.notify()` berinteraksi dengan Event Loop? Mengapa `Atomics.wait()` dilarang dipanggil di Main Thread Node.js?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah service pemrosesan faktur menggunakan `p-limit` dengan konkurensi 50 untuk mengunduh 50.000 file PDF dari Amazon S3 secara paralel. Walaupun memori container masih tersisa 60%, seluruh network outbound drop drastis dan muncul error `DNS lookup timeout (EAI_AGAIN)`. Apa akar masalah di level arsitektur internal Node.js, dan bagaimana solusinya?
12. **Skenario 2**: Anda mengintegrasikan OpenTelemetry APM ke production menggunakan `AsyncLocalStorage`. Setelah deployment, Anda mendapati bahwa pada beberapa log transaksi, `traceId` dari User A tertukar dengan data transaksi User B di bawah beban 10.000 RPS. Identifikasi kemungkinan pola antipattern kode yang menyebabkan kontaminasi konteks ini!
13. **Skenario 3**: Sebuah worker thread crash akibat `JavaScript out of memory`, tetapi parent process Node.js tetap hidup dan menerima HTTP request. Namun, semua request yang diarahkan ke pool worker tersebut menjadi hanging selamanya (unresolved promises). Mekanisme disaster-recovery konkurensi apa yang wajib diimplementasikan di orchestrator worker internal?

---

### 16. Summary

- **Dualitas Arsitektur**: Node.js mengawinkan kecepatan single-threaded execution V8 untuk logic dispatching dengan skalabilitas non-blocking multi-threading Libuv (kqueue/epoll) untuk I/O dan Thread Pool worker internal.
- **Microtask Dominance**: Antrean `process.nextTick` dan `Promise` microtask memiliki prioritas absolut di atas fase-fase siklus Libuv. Node.js menguras habis microtasks di antara setiap eksekusi callback individual.
- **Konkurensi Tanpa Kebocoran**: Arsitektur enterprise modern menuntut propagasi metadata terisolasi (`AsyncLocalStorage`), kontrol eksekusi yang dapat dibatalkan secara deterministik (`AbortController`), serta isolasi kerja CPU-bound ke unit terpisah (`Worker Threads`).
- **Zero-Copy High Concurrency**: Untuk kebutuhan data transfer intensitas tinggi antar worker, penggunaan transferrable objects atau `SharedArrayBuffer` dengan primitif sinkronisasi `Atomics` adalah satu-satunya cara menghindari memory duplication dan latency overhead akibat structured serialization.