# 04-Backend-and-Database / nodejs / Bab 02 Module 01: Advanced Asynchronous Programming & Concurrency

---

## 01. Identitas Modul

* **Domain Kurikulum**: 04-Backend-and-Database
* **Teknologi**: Node.js (V8 Engine & libuv runtime)
* **Tingkat Kesulitan**: Advanced / Principal Engineer Level
* **Prasyarat**: Pemahaman mendalam tentang JavaScript ES2022+, Dasar-dasar Event Loop, Callbacks, Native Promises, dan ES Modules.

---

## 02. Learning Objectives

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Mendekonstruksi Arsitektur Event Loop & libuv**: Menganalisa fase eksekusi Event Loop (`timers`, `pending callbacks`, `idle/prepare`, `poll`, `check`, `close callbacks`) serta prioritas microtask queue (`process.nextTick` vs Promise resolution).
2. **Menguasai Pola Asinkron Lanjutan**: Mengimplementasikan Async Generators, Async Iterators, serta primitif orkestrasi paralel (`Promise.all`, `Promise.allSettled`, `Promise.race`, `Promise.any`) dengan error isolation yang ketat.
3. **Mengendalikan Concurrency & Backpressure**: Membangun mekanisme dynamic concurrency throttler, rate limiter, dan backpressure control pada data stream intensif tanpa memicu degradasi memori.
4. **Mengelola Lifecycle Asinkron dengan `AbortController`**: Membatalkan operasi I/O majemuk, stream reader, child process, dan timer secara terpadu melalui sinyal pembatalan deterministik.
5. **Memitigasi Event Loop Starvation**: Mengidentifikasi dan merefaktor CPU-bound tasks agar tidak memblokir I/O throughput menggunakan cooperative scheduling, dynamic unrolling, dan worker delegation.
6. **Menerapkan Context Preservation**: Mengimplementasikan `AsyncLocalStorage` untuk penelusuran request context (Distributed Tracing/APM) secara zero-leak dan deterministic.

---

## 03. Concept Map Diagram (ASCII)

```
+-------------------------------------------------------------------------------+
|                            V8 JAVASCRIPT ENGINE                               |
|  [ Call Stack (Synchronous Execution) ]                                        |
|  [ Microtask Queue 1: process.nextTick() ] -> High Priority Flush             |
|  [ Microtask Queue 2: Promise Jobs (then, catch, finally) ]                    |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                              LIBUV EVENT LOOP                                 |
|                                                                               |
|   +-------------------> [ 1. Timers (setTimeout, setInterval) ]              |
|   |                                     |                                     |
|   |                                     v                                     |
|   |                     [ 2. Pending I/O Callbacks ]                          |
|   |                                     |                                     |
|   |                                     v                                     |
|   |                     [ 3. Idle, Prepare (Internal) ]                       |
|   |                                     |                                     |
|   |                                     v                                     |
|   |                     [ 4. Poll (Incoming Connections, Data) ] <--------+   |
|   |                                     |                                 |   |
|   |                                     v                                 |   |
|   |                     [ 5. Check (setImmediate) ]                       |   |
|   |                                     |                                 |   |
|   |                                     v                                 |   |
|   +-------------------- [ 6. Close Callbacks (socket.on('close')) ]       |   |
|                                                                           |   |
|   * Thread Pool (UV_THREADPOOL_SIZE): File I/O, DNS, Crypto, Zlib --------+   |
+-------------------------------------------------------------------------------+
                                      |
       +------------------------------+------------------------------+
       |                              |                              |
       v                              v                              v
[ Concurrency Limiting ]    [ Cancellation Engine ]     [ Execution Context ]
(p-limit, Worker Threads)      (AbortController)        (AsyncLocalStorage)
```

---

## 04. Mengapa Relevan

Dalam arsitektur *high-throughput backend*, Node.js sering kali disalahpahami sebagai platform murni "single-threaded". Meskipun eksekusi JavaScript berjalan pada satu thread utama, skalabilitas I/O Node.js bergantung penuh pada libuv Event Loop dan Thread Pool.

Kesalahan dalam memahami cara kerja microtask scheduling, alokasi memori saat concurrency tinggi, atau penanganan task CPU-bound dapat menyebabkan **Event Loop Lag (ELP)**, penurunan drastis pada *request per second* (RPS), hingga kegagalan fatal seperti crash Out-Of-Memory (OOM). Menguasai model eksekusi asinkron tingkat lanjut adalah pembeda utama antara kode amatir yang rentan gagal di bawah beban puncak dan arsitektur backend kelas industri yang elastis, deterministik, dan dapat diobservasi secara mendalam.

---

## 05. Anatomi Konsep Inti

### 1. Dekonstruksi Microtask Scheduling & Starvation
Microtask dieksekusi segera setelah operasi sinkron saat ini selesai, tepat sebelum runtime kembali ke fase libuv berikutnya.
* **`process.nextTick`**: Berada di antrean `nextTickQueue`. Selalu dieksekusi sebelum Promise Microtask. Rekursi tak terbatas di sini akan menyebabkan **Event Loop Starvation** total (I/O thread tidak pernah terlayani).
* **Promise Microtasks**: Menangani resolusi Promise native dan `queueMicrotask()`. Dieksekusi secara tuntas sebelum siklus Event Loop berpindah ke fase berikutnya.

### 2. Fase-fase Libuv Event Loop
* **Timers**: Mengeksekusi callback dari `setTimeout` dan `setInterval` yang ambang batas waktunya telah terlewati.
* **Pending Callbacks**: Mengeksekusi callback I/O yang ditunda dari iterasi sebelumnya (misalnya error penulisan socket TCP).
* **Poll**: Mengambil I/O event baru; Node.js akan memblokir di sini jika tidak ada timer yang siap dan tidak ada task `setImmediate`.
* **Check**: Fase khusus di mana callback `setImmediate()` dieksekusi secara instan setelah fase Poll selesai.
* **Close Callbacks**: Membersihkan state resource, seperti pemanggilan `socket.on('close', ...)`.

### 3. Asynchronous Generators & Reactive Streams
Async Generator (`async function*`) menggabungkan asynchronous primitives dengan model pull-based iteration protocol (`Symbol.asyncIterator`). Pola ini sangat ideal untuk memproses data stream berukuran masif (misal: chunk database, line-by-line log parsing) secara hemat memori (O(1) memory overhead).

### 4. Deterministic Cancellation via `AbortController` & `AbortSignal`
Menghindari *zombie operations* saat upstream client memutus koneksi (HTTP request drop). `AbortSignal` kini terintegrasi secara native di API Node.js seperti `fetch`, `fs/promises`, `stream/promises`, dan `child_process`.

### 5. Distributed Context Propagation via `AsyncLocalStorage`
Menyediakan penyimpanan state thread-local-like across asynchronous execution chains tanpa perlu mem-passing parameter context secara manual melalui setiap lapisan fungsi (dependency drill).

---

## 06. Panduan Implementasi Step-by-Step

### Step 1: Inisialisasi Environment Node.js Modern
Pastikan menggunakan runtime Node.js LTS (v20+ atau v22+) dengan dukungan native ES Modules.

```bash
mkdir nodejs-concurrency-deep-dive
cd nodejs-concurrency-deep-dive
npm init -y
npm pkg set type="module"
```

### Step 2: Mengonfigurasi Thread Pool Libuv
Konfigurasi thread pool libuv harus dilakukan sebelum runtime Node.js menginisialisasi I/O subsistem:

```bash
# Set environment variable di level OS / deployment container
export UV_THREADPOOL_SIZE=16
```

### Step 3: Implementasi Cooperative Yielding untuk CPU-Bound Tasks
Gunakan `setImmediate` via helper `yieldToEventLoop()` untuk memecah komputasi berat menjadi chunk yang ramah Event Loop:

```javascript
export const yieldToEventLoop = () => new Promise(resolve => setImmediate(resolve));
```

---

## 07. Contoh Kasus Sederhana: Event Loop Phase Execution Order

Skrip ini memvalidasi pemahaman deterministik terhadap urutan eksekusi fase Node.js:

```javascript
import fs from 'node:fs/promises';

console.log('1. [Main] Sync Script Start');

setTimeout(() => {
  console.log('2. [Timers] setTimeout 0ms');
}, 0);

setImmediate(() => {
  console.log('3. [Check] setImmediate Callback');
});

queueMicrotask(() => {
  console.log('4. [Microtask] queueMicrotask');
});

process.nextTick(() => {
  console.log('5. [Microtask: nextTick] process.nextTick');
});

(async () => {
  console.log('6. [Main] Async IIFE Start');
  await Promise.resolve();
  console.log('7. [Microtask: Promise] Async IIFE Resumed');
})();

console.log('8. [Main] Sync Script End');

// Output Prediksi:
// 1. [Main] Sync Script Start
// 6. [Main] Async IIFE Start
// 8. [Main] Sync Script End
// 5. [Microtask: nextTick] process.nextTick
// 4. [Microtask] queueMicrotask
// 7. [Microtask: Promise] Async IIFE Resumed
// 2. [Timers] setTimeout 0ms (atau Check tergantung context bootstrap, namun 0ms timer diproses di loop pertama)
// 3. [Check] setImmediate Callback
```

---

## 08. Implementasi Production-Grade

Berikut adalah arsitektur **Industrial Resilient Pipeline Orchestrator**: Menggabungkan `AsyncLocalStorage`, dynamic concurrency pool limiter, backoff-retry, dan integrasi penuh dengan `AbortController`.

```javascript
// pipeline-orchestrator.js
import { AsyncLocalStorage } from 'node:async_hooks';
import { EventEmitter } from 'node:events';

// Context Holder untuk Distributed Tracing
export const traceContext = new AsyncLocalStorage();

/**
 * Custom Concurrency Limiter Pool dengan AbortSignal Support
 */
export class DynamicConcurrencyLimiter {
  #maxConcurrency;
  #currentRunning = 0;
  #queue = [];

  constructor(maxConcurrency = 5) {
    if (maxConcurrency < 1) throw new Error('Concurrency limit must be >= 1');
    this.#maxConcurrency = maxConcurrency;
  }

  get activeCount() {
    return this.#currentRunning;
  }

  get pendingCount() {
    return this.#queue.length;
  }

  async run(taskFactory, signal) {
    if (signal?.aborted) {
      throw new Error(`Task aborted before starting: ${signal.reason}`);
    }

    if (this.#currentRunning >= this.#maxConcurrency) {
      await new Promise((resolve, reject) => {
        const onAbort = () => {
          const idx = this.#queue.findIndex(item => item.resolve === resolve);
          if (idx !== -1) {
            this.#queue.splice(idx, 1);
          }
          reject(new Error(`Task aborted in queue: ${signal.reason}`));
        };

        if (signal) {
          signal.addEventListener('abort', onAbort, { once: true });
        }

        this.#queue.push({ resolve, reject, signal, onAbort });
      });
    }

    this.#currentRunning++;
    try {
      if (signal?.aborted) {
        throw new Error(`Task aborted right before execution: ${signal.reason}`);
      }
      return await taskFactory();
    } finally {
      this.#currentRunning--;
      this.#dispatchNext();
    }
  }

  #dispatchNext() {
    if (this.#queue.length > 0 && this.#currentRunning < this.#maxConcurrency) {
      const nextTask = this.#queue.shift();
      if (nextTask) {
        if (nextTask.signal && nextTask.onAbort) {
          nextTask.signal.removeEventListener('abort', nextTask.onAbort);
        }
        nextTask.resolve();
      }
    }
  }
}

/**
 * Pipeline Stream Processor menggunakan Async Generators
 */
export class AdvancedPipelineProcessor extends EventEmitter {
  #limiter;

  constructor(concurrencyLimit = 4) {
    super();
    this.#limiter = new DynamicConcurrencyLimiter(concurrencyLimit);
  }

  /**
   * Mengonsumsi asynchronous generator stream dengan isolasi konteks & fail-safe error boundary
   */
  async *processStream(asyncIterableSource, transformFn, { signal } = {}) {
    for await (const chunk of asyncIterableSource) {
      if (signal?.aborted) {
        this.emit('aborted', { reason: signal.reason });
        throw new Error(`Pipeline aborted: ${signal.reason}`);
      }

      const store = traceContext.getStore() || new Map();
      const traceId = store.get('traceId') || 'trace-unknown';

      // Jalankan transformasi via Concurrency Limiter
      yield this.#limiter.run(async () => {
        return traceContext.run(store, async () => {
          this.emit('processing', { traceId, chunkId: chunk.id });
          return await transformFn(chunk, signal);
        });
      }, signal);
    }
  }
}

/**
 * Helper Utility: Retry Strategy dengan Exponential Jitter
 */
export async function withRetry(operation, { retries = 3, minDelay = 100, maxDelay = 2000, signal } = {}) {
  let attempt = 0;
  while (attempt < retries) {
    try {
      if (signal?.aborted) throw new Error(signal.reason);
      return await operation();
    } catch (err) {
      attempt++;
      if (attempt >= retries || signal?.aborted) {
        throw err;
      }
      // Calculate Full Jitter Backoff
      const baseDelay = Math.min(maxDelay, minDelay * 2 ** attempt);
      const jitteredDelay = Math.floor(Math.random() * baseDelay);
      await new Promise((res, rej) => {
        const timer = setTimeout(res, jitteredDelay);
        signal?.addEventListener('abort', () => {
          clearTimeout(timer);
          rej(new Error(signal.reason));
        }, { once: true });
      });
    }
  }
}
```

---

## 09. Diagram Alur Kerja Concurrency Execution Pipeline (ASCII)

```
[ Ingest Stream Data Chunk ]
              |
              v
[ AsyncLocalStorage Binding ] ---> (Attach Trace ID: UUIDv4)
              |
              v
[ Concurrency Limiter Gate ]
       |             |
  (Slots Available)  (Slots Full)
       |             |
       v             v
[ Execute Worker ]   [ Push to Priority Pending Queue ]
       |                     ^
       | (On Worker Done)    |
       +---------------------+
              |
              v
[ AbortSignal Verification ] ---> If Aborted? --> Short-Circuit (Throw Error)
              | (Not Aborted)
              v
[ Execute Operation + Retry Wrapper (Exponential Jitter) ]
              |
              v
[ Yield Processed Result to Stream Outflow ]
```

---

## 10. Analisis Trade-offs

| Pendekatan | Keuntungan | Kerugian / Risiko | Skenario Penggunaan Terbaik |
| :--- | :--- | :--- | :--- |
| **`Promise.all`** | Eksekusi paralel tercepat; fail-fast jika terjadi satu kegagalan. | Seluruh hasil dibuang jika ada satu rejected; memori membengkak jika input tidak dibatasi. | Operasi dependen multi-fetch atomik yang wajib sukses semua. |
| **`Promise.allSettled`** | Tidak melempar kegagalan massal; memberikan rekap status dari seluruh promises. | Menunggu semua selesai terlepas dari kegagalan; tetap menampung seluruh Promise di memori. | Batch processing independen di mana sebagian data gagal dapat ditoleransi/dicatat ke log. |
| **Async Generators** | Konsumsi memori O(1) konstan (pull-based streaming), integrasi mudah dengan `for await...of`. | Tidak paralel secara native tanpa custom concurrency scheduler. | Pengolahan big data, CSV parsing jutaan baris, stream processing. |
| **Dynamic Limiter Pool** | Mengontrol pressure beban I/O, mencegah network socket starvation dan DB connection pool exhaust. | Overhead penjadwalan antrean lokal dan manajemen state internal. | Menembak third-party rate-limited APIs, throttling database writes. |

---

## 11. Best Practices & Antipatterns

### Best Practices
* **Selalu Pasang `signal` pada Async I/O**: Teruskan instance `AbortSignal` ke native API (`fetch`, `fs.readFile`, downstream microservice) untuk memutus sambungan soket jika request dibatalkan.
* **Gunakan `AsyncLocalStorage` secara Bijak**: Bungkus siklus eksekusi sespesifik mungkin. Hindari mutasi objek global di dalam store untuk mencegah race-condition konteks data.
* **Terapkan Cooperative Multitasking**: Jika harus mengeksekusi komputasi CPU intensif (misalnya sorting ribuan data array), panggil `yieldToEventLoop()` setiap iterasi $N$ untuk memberi kesempatan Event Loop memproses callback network/IO.

### Antipatterns
* **Unbounded `Promise.all` Execution**: Menjalankan `Promise.all(massiveArray.map(...))` dengan ribuan elemen secara langsung. Hal ini akan memicu *socket exhaustion*, lonjakan memori instan, dan potensi crash V8 Heap Limit.
* **Blocking Callbacks di `process.nextTick` Recursion**: Menggunakan rekursi berulang tanpa base case atau tanpa beralih ke `setImmediate`, menyebabkan microtask starvation pada fase I/O.
* **Floating (Uncaught) Promises**: Menjalankan operasi asinkron tanpa blok `try/catch` atau tanpa handler `.catch()`, yang dapat memicu event `unhandledRejection` dan mematikan proses Node.js di environment produksi.

---

## 12. Security Hardening

* **Resource Exhaustion Mitigation (DoS Prevention)**: Tetapkan *hard timeout* mutlak menggunakan `AbortSignal.timeout(ms)` untuk setiap pemanggilan HTTP/I/O eksternal guna memitigasi serangan *Slowloris* atau hang sockets.
* **Anti-Memory Exhaustion (Backpressure)**: Hindari penggunaan `array.push()` massal dalam loop asinkron tanpa membatasi ukuran antrean (`queue concurrency bound`).
* **Unhandled Rejection Strict Exit**: Pastikan konfigurasi runtime tidak membungkam uncaught promise rejections. Flag `--unhandled-rejections=strict` (default pada Node.js modern) wajib dipertahankan untuk mencegah aplikasi berjalan dalam state *zombie/corrupted*.

```javascript
// Contoh Defensif: Timeout Hardening
const abortController = new AbortController();
const timeoutSignal = AbortSignal.timeout(3000); // Fail-safe hard timeout 3 detik
const linkedSignal = AbortSignal.any([abortController.signal, timeoutSignal]);

try {
  const res = await fetch('https://upstream.internal/api', { signal: linkedSignal });
  await res.json();
} catch (err) {
  if (err.name === 'TimeoutError') {
    // Audit Log Security Event: Upstream latency threshold breached
  }
}
```

---

## 13. Observabilitas & Debugging

### 1. Monitoring Event Loop Delay (ELD)
Gunakan `perf_hooks` native untuk merekam degradasi Event Loop secara kuantitatif:

```javascript
import { monitorEventLoopDelay } from 'node:perf_hooks';

const histogram = monitorEventLoopDelay({ resolution: 10 }); // sample per 10ms
histogram.enable();

setInterval(() => {
  console.log(`ELD Metrics (ns): Min=${histogram.min}, Max=${histogram.max}, Mean=${histogram.mean}, P99=${histogram.percentile(99)}`);
  histogram.reset();
}, 5000).unref();
```

### 2. Async Hook Lifetime Tracking
Gunakan command-line flag bawaan untuk mendeteksi unresolved promise:

```bash
node --trace-warnings --unhandled-rejections=strict app.js
```

---

## 14. Benchmarking & Performance

Jalankan skrip benchmark untuk membandingkan throughput antara eksekusi blocking vs non-blocking async chunking.

```javascript
// benchmark-concurrency.js
import { performance } from 'node:perf_hooks';
import { yieldToEventLoop } from './pipeline-orchestrator.js';

async function cpuBoundBlocking(iterations) {
  let count = 0;
  for (let i = 0; i < iterations; i++) {
    count += Math.sqrt(i);
  }
  return count;
}

async function cpuBoundCooperative(iterations, chunkSize = 10000) {
  let count = 0;
  for (let i = 0; i < iterations; i++) {
    count += Math.sqrt(i);
    if (i % chunkSize === 0) {
      await yieldToEventLoop();
    }
  }
  return count;
}

const ITERATIONS = 10_000_000;

console.log('--- Starting Benchmark ---');
const startBlock = performance.now();
await cpuBoundBlocking(ITERATIONS);
console.log(`Blocking execution time: ${(performance.now() - startBlock).toFixed(2)}ms`);

const startCoop = performance.now();
await cpuBoundCooperative(ITERATIONS);
console.log(`Cooperative execution time: ${(performance.now() - startCoop).toFixed(2)}ms`);
```

---

## 15. Hands-on Lab Mini-Project

### Masalah
Bangun modul *Resilient Batch Fetcher Engine* yang mengonsumsi array 50 task URL simulasi. Ketentuan:
1. Concurrency dibatasi maksimal 5 workers aktif secara simultan.
2. Setiap task wajib dibatalkan jika melebihi timeout 150ms.
3. Otomatis me-retry kegagalan transient maksimal 2 kali sebelum ditandai gagal permanen.
4. Menjaga konteks `tenantId` menggunakan `AsyncLocalStorage`.

### Solusi Kode Lengkap (`lab-mini-project.js`)

```javascript
import { AsyncLocalStorage } from 'node:async_hooks';
import { DynamicConcurrencyLimiter, withRetry } from './pipeline-orchestrator.js';

const contextStore = new AsyncLocalStorage();
const limiter = new DynamicConcurrencyLimiter(5);

// Simulasi Network Request Flaky
async function mockFetch(url, signal) {
  return new Promise((resolve, reject) => {
    const isFailure = Math.random() < 0.4;
    const latency = Math.floor(Math.random() * 200) + 50;

    const timer = setTimeout(() => {
      if (isFailure) {
        reject(new Error(`Network 500 error for URL: ${url}`));
      } else {
        resolve({ url, status: 200, payload: `Payload data for ${url}` });
      }
    }, latency);

    signal.addEventListener('abort', () => {
      clearTimeout(timer);
      reject(new Error(`Fetch timed out / aborted: ${url}`));
    }, { once: true });
  });
}

async function processTask(url) {
  const store = contextStore.getStore();
  const tenantId = store?.get('tenantId') || 'unknown';

  const timeoutSignal = AbortSignal.timeout(150);

  return await limiter.run(async () => {
    return await withRetry(async () => {
      console.log(`[Tenant: ${tenantId}] Fetching ${url}... (Active: ${limiter.activeCount}, Pending: ${limiter.pendingCount})`);
      return await mockFetch(url, timeoutSignal);
    }, { retries: 2, minDelay: 50, signal: timeoutSignal });
  }, timeoutSignal);
}

// Inisialisasi Eksekusi
(async () => {
  const urls = Array.from({ length: 25 }, (_, i) => `https://api.internal.service/v1/resource/${i + 1}`);
  
  const rootContext = new Map([['tenantId', 'enterprise-tenant-alpha']]);

  const results = await contextStore.run(rootContext, async () => {
    return await Promise.allSettled(urls.map(url => processTask(url)));
  });

  const succeeded = results.filter(r => r.status === 'fulfilled').map(r => r.value);
  const failed = results.filter(r => r.status === 'rejected').map(r => r.reason.message);

  console.log('\n--- EXECUTION REPORT ---');
  console.log(`Total Tasks: ${urls.length}`);
  console.log(`Successful: ${succeeded.length}`);
  console.log(`Failed/Timeout: ${failed.length}`);
})();
```

---

## 16. Automated Testing & Verification

Simpan kode di bawah sebagai `orchestrator.test.js` menggunakan test runner native Node.js:

```javascript
import { test, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { DynamicConcurrencyLimiter, withRetry } from './pipeline-orchestrator.js';

describe('Advanced Concurrency Verification', () => {
  it('harus membatasi concurrency sesuai threshold maksimum', async () => {
    const maxConcurrency = 2;
    const limiter = new DynamicConcurrencyLimiter(maxConcurrency);
    let peakConcurrency = 0;
    let current = 0;

    const task = async () => {
      current++;
      peakConcurrency = Math.max(peakConcurrency, current);
      await new Promise(r => setTimeout(r, 50));
      current--;
    };

    await Promise.all([
      limiter.run(task),
      limiter.run(task),
      limiter.run(task),
      limiter.run(task)
    ]);

    assert.equal(peakConcurrency, maxConcurrency, 'Peak concurrency melebihi batasan yang ditentukan');
  });

  it('harus menghormati pembatalan AbortController saat task dalam antrean', async () => {
    const limiter = new DynamicConcurrencyLimiter(1);
    const controller = new AbortController();

    // Lock single slot
    const slowTask = limiter.run(() => new Promise(r => setTimeout(r, 100)));

    // Task kedua di-abort saat masih mengantre
    const queuedTask = limiter.run(
      () => new Promise(r => setTimeout(r, 50)),
      controller.signal
    );

    controller.abort('Abort Reason: Cancelled by Client');

    await assert.rejects(
      async () => await queuedTask,
      /Abort Reason: Cancelled by Client/
    );

    await slowTask;
  });

  it('harus me-retry task yang gagal dan berhasil jika transient error teratasi', async () => {
    let callCount = 0;
    const unstableTask = async () => {
      callCount++;
      if (callCount < 2) throw new Error('Transient Database Disconnect');
      return 'SUCCESS_PAYLOAD';
    };

    const result = await withRetry(unstableTask, { retries: 3, minDelay: 10 });
    assert.equal(result, 'SUCCESS_PAYLOAD');
    assert.equal(callCount, 2);
  });
});
```

Jalankan via command line:
```bash
node --test orchestrator.test.js
```

---

## 17. Troubleshooting Guide

| Gejala Masalah | Investigasi Root-Cause | Solusi Rekayasa |
| :--- | :--- | :--- |
| **Event Loop Lag Melonjak (>100ms)** | Callback synchronous komputasi intensif (JSON parse besar, regex catastrophic backtracking). | Pindahkan proses ke `node:worker_threads` atau pecah iterasi menggunakan chunking `yieldToEventLoop()`. |
| **Peringatan MaxListenersExceededWarning** | Listener `abort` pada `AbortSignal` tidak dibersihkan saat operasi Promise selesai (`finally`). | Gunakan `{ once: true }` pada `addEventListener` dan pastikan memanggil `removeEventListener` pada settled task. |
| **State Request Tertukar / Hilang di APM** | `AsyncLocalStorage.run` terputus akibat pemanggilan callback non-standard tanpa async-wrap. | Pastikan third-party callback library dibungkus menggunakan `asyncResource.runInAsyncScope()` atau promisify secara native. |
| **Memory Leak pada Antrean Concurrency** | Resolver Promise dalam limiter pool tersangkut dan tidak pernah dipanggil karena unhandled exception. | Bungkus alur worker dalam blok `try...finally` deterministik untuk memanggil `dispatchNext()`. |

---

## 18. Checklist Produksi

- [ ] **Thread Pool Tuning**: Setel environment variable `UV_THREADPOOL_SIZE` sesuai jumlah core server jika memproses intensitas tinggi pada modul `fs`, `crypto`, atau `dns`.
- [ ] **Global Cancellation Propagation**: Seluruh outbound network request (DB, Redis, HTTP) mengikat `AbortSignal` yang berasal dari context incoming request.
- [ ] **Event Loop Delay Monitor**: Implementasikan alert metric jika p99 Event Loop Delay melebihi 50ms selama 3 interval berturut-turut.
- [ ] **Bounded Concurrency Limits**: Tidak ada pemanggilan native `Promise.all` terhadap koleksi array dinamis tanpa dynamic pool throttle.
- [ ] **Context Propagation Zero-Leak**: Validasi heap dump untuk memastikan objek `AsyncLocalStorage` dibersihkan dari GC saat request selesai lifecycle-nya.

---

## 19. Ringkasan Eksekutif

Penguasaan pemrograman asinkron tingkat lanjut di Node.js menuntut transisi pemahaman dari sekadar sintaksis `async/await` menuju penguasaan mekanika runtime:

1. **Microtasks (`process.nextTick`, Promises)** memiliki prioritas eksekusi mutlak sebelum Event Loop berpindah fase. Penggunaan rekursif tak terkontrol akan mematikan I/O processing aplikasi Anda.
2. **Backpressure dan Concurrency Control** wajib diterapkan di lapisan aplikasi; runtime V8 tidak membatasi konkurensi native Promises secara otomatis, sehingga uncontrolled parallelization dapat menghabiskan memori dan connection socket.
3. **`AbortController` dan `AsyncLocalStorage`** adalah dua pilar modern untuk membangun backend enterprise: menjamin pembersihan resource instan dari operasi batal dan menjamin isolasi pelacakan distributed tracing secara end-to-end tanpa polusi parameter global.

---

## 20. Referensi & Bacaan Lanjutan

* **Node.js Official Documentation**: *The Node.js Event Loop, Timers, and `process.nextTick()`* — [https://nodejs.org/en/learn/asynchronous-work/event-loop-timers-and-nexttick](https://nodejs.org/en/learn/asynchronous-work/event-loop-timers-and-nexttick)
* **Node.js Diagnostics Documentation**: *AsyncLocalStorage and Execution Context Isolation* — [https://nodejs.org/api/async_context.html](https://nodejs.org/api/async_context.html)
* **Libuv Architectural Design Guide**: *Design overview of the multiplatform async I/O engine* — [https://docs.libuv.org/en/v1.x/design.html](https://docs.libuv.org/en/v1.x/design.html)
* **V8 Engine Blog**: *Fast properties and Promise execution mechanics in modern V8* — [https://v8.dev/blog](https://v8.dev/blog)