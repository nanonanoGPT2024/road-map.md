# SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** Pemrograman Web & Backend Lanjutan
* **Kategori:** 02-Programming-Languages
* **Topik:** JavaScript Runtime Mechanics
* **Bab / Modul:** Bab 02 Module 01 — Asynchronous Runtime Internals & Event Loop Orchestration
* **Tingkat Kesulitan:** Advanced / Senior Engineering
* **Prasyarat Pengetahuan:** 
  * Pemahaman mendalam tentang eksekusi JavaScript dasar (Execution Context, Scope Chain, Closures).
  * Pengalaman dasar dengan sintaks `Promise`, `async/await`, dan fungsi `setTimeout`.
  * Konsep dasar struktur data: *Stack*, *Queue*, dan *Priority Queue*.
* **Target Ekosistem:** Node.js (v18.x+) & Modern V8 Engine (Chromium-based).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Mekanisme Eksekusi Mesin V8 & Libuv:** Mengartikulasikan interaksi konkret antara V8 Engine (Call Stack, Memory Heap) dan host environment (Libuv thread pool pada Node.js atau Web APIs pada browser).
2. **Membedah Hirarki Antrean Task:** Mendemonstrasikan prioritas eksekusi antara Microtask Queue (`process.nextTick`, `Promise.then/catch/finally`, `queueMicrotask`, `MutationObserver`) dan Task/Macrotask Queue (`setTimeout`, `setInterval`, `setImmediate`, I/O callbacks).
3. **Memetakan Fase-Fase Event Loop Libuv:** Menjelaskan secara presisi 6 fase siklus hidup Event Loop pada Node.js (*timers*, *pending callbacks*, *idle/prepare*, *poll*, *check*, *close callbacks*).
4. **Mendeteksi dan Memitigasi Event Loop Lag & Starvation:** Mendiagnosis penyebab degradasi latensi server akibat *CPU-bound execution* atau rekursi microtask yang tak terkontrol, serta menerapkan solusinya menggunakan teknik *chunking* dan multi-threading (`worker_threads`).
5. **Membangun Sistem Penjadwalan Berkinerja Tinggi:** Mengimplementasikan orkestrasi asinkron kustom yang aman dari kebocoran memori, *unhandled rejection*, dan *race conditions*.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

JavaScript sering disederhanakan dengan dogma: *"JavaScript is single-threaded and non-blocking"*. Kalimat ini secara konseptual membingungkan jika tidak dibedah komponen arsitekturalnya.

### Paradoks Single-Threaded
* **Fakta:** JavaScript Execution Thread (Call Stack pada V8) adalah **single-threaded**. Hanya ada satu instruksi yang dieksekusi dalam satu waktu pada satu *isolate*.
* **Realita Runtime:** Platform tempat JavaScript berjalan (Node.js/C++ Libuv atau Browser C++ Blink/WebKit) adalah **multi-threaded**. Ketika Anda melakukan pembacaan berkas (`fs.readFile`) atau pemanggilan jaringan (`crypto.pbkdf2`, DNS lookups), pekerjaan berat didelegasikan ke thread pool sistem operasi atau thread C++ Libuv latar belakang.

### Mental Model: Konduktor Orkestra dan Musisi Cadangan
Bayangkan JavaScript Call Stack sebagai seorang **Konduktor Tunggal** di panggung:
1. Konduktor membaca lembaran partitur baris demi baris (Synchronous Code).
2. Ketika konduktor menemukan instruksi yang membutuhkan waktu lama (misalnya, menunggu instrumen disetel atau memuat data lembaran baru), konduktor tidak diam berdiri menunggu; ia melemparkan perintah ke **Manajer Panggung (Libuv/Web API)**.
3. Manajer Panggung memberikan pekerjaan ke **Kru Cadangan (Thread Pool)**.
4. Ketika pekerjaan selesai, Manajer Panggung meletakkan hasilnya di salah satu dari dua nampan antrean:
   * **Nampan Emas (Microtask Queue):** Diberikan perhatian instan oleh konduktor sebelum nada berikutnya dibunyikan.
   * **Nampan Perak (Macrotask Queue):** Dikerjakan setelah seluruh partitur aktif dan nampan emas benar-benar kosong.
5. Konduktor hanya berpindah ke siklus berikutnya (*tick*) jika tumpukan partitur di tangannya sudah selesai dieksekusi.

Memahami orkestrasi ini mencegah asumsi keliru bahwa `await` "menghentikan program". Faktanya, `await` melepaskan kendali thread utama kembali ke Event Loop agar tugas lain dapat diproses.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur internal eksekusi asynchronous pada runtime Node.js yang memadukan V8 Engine dan Libuv:

```
+-----------------------------------------------------------------------------------+
|                              V8 JAVASCRIPT ENGINE                                 |
|                                                                                   |
|  +--------------------+        Allocation          +---------------------------+  |
|  |    Memory Heap     | ------------------------>  |        Call Stack         |  |
|  | (Objects, Closures)|                            | (Execution Contexts)      |  |
|  +--------------------+                            +-------------+-------------+  |
+------------------------------------------------------------------|----------------+
                                                                   |
                                          Delegates I/O / Timers   | (When async API
                                                                   |  is invoked)
                                                                   v
+-----------------------------------------------------------------------------------+
|                         HOST RUNTIME (NODE.JS / LIBUV)                            |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                              LIBUV THREAD POOL                              |  |
|  | [Worker Thread 1]  [Worker Thread 2]  [Worker Thread 3]  [Worker Thread 4]  |  |
|  +-----------------------------------------------------------------------------+  |
|                                         |                                         |
|                                         | Notifies completion                     |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  |                            MICROTASK QUEUES                                 |  |
|  |  1. process.nextTick Queue                                                  |  |
|  |  2. Promise Tasks / queueMicrotask                                          |  |
|  |  *(Durasikan dan dikosongkan SETELAH setiap operasi Stack & ANTAR-FASE)*     |  |
|  +-----------------------------------------------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  |                         EVENT LOOP PHASES (MACROTASKS)                      |  |
|  |                                                                             |  |
|  |   +---------------------------> [ 1. TIMERS ]                               |  |
|  |   |                             (setTimeout, setInterval)                   |  |
|  |   |                                  |                                      |  |
|  |   |                                  v                                      |  |
|  |   |                             [ 2. PENDING CALLBACKS ]                    |  |
|  |   |                             (I/O errors, deferred system events)        |  |
|  |   |                                  |                                      |  |
|  |   |                                  v                                      |  |
|  |   |                             [ 3. IDLE, PREPARE ]                        |  |
|  |   |                             (Internal Libuv housekeeping)               |  |
|  |   |                                  |                                      |  |
|  |   |                                  v                                      |  |
|  |   |                             [ 4. POLL ] <---------- New I/O Events      |  |
|  |   |                             (Incoming Connections, Read Data)           |  |
|  |   |                                  |                                      |  |
|  |   |                                  v                                      |  |
|  |   |                             [ 5. CHECK ]                                |  |
|  |   |                             (setImmediate callbacks)                    |  |
|  |   |                                  |                                      |  |
|  |   |                                  v                                      |  |
|  |   +---------------------------- [ 6. CLOSE CALLBACKS ]                      |  |
|  |                                 (socket.on('close'), handle cleanups)       |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Call Stack (V8)
Call Stack adalah struktur data LIFO (*Last In, First Out*) yang mencatat konteks eksekusi fungsi saat ini. Ketika suatu fungsi dipanggil, *stack frame* dibuat (menyimpan argumen, variabel lokal, dan return address). Ketika fungsi selesai (`return`), frame tersebut di-*pop*.

### 2. Memory Heap
Ruang memori tidak terstruktur tempat objek, variabel referensi, dan *closures* dialokasikan secara dinamis. Garbage Collector (Orinoco / Scavenger / Mark-Sweep-Compact) mengawasi area ini.

### 3. Libuv & POSIX Async
Libuv adalah pustaka C multi-platform yang mengabstraksi I/O asinkron. 
* Operasi soket/jaringan umumnya menggunakan *I/O Polling* berbasis kernel primitif non-blocking (`epoll` di Linux, `kqueue` di macOS, `IOCP` di Windows).
* Operasi berkas (*File System*) dan komputasi kriptografi dijalankan pada thread pool worker Libuv internal (default: 4 thread, dikonfigurasi melalui `UV_THREADPOOL_SIZE`).

### 4. Microtask Queue vs Macrotask Queue
* **Microtask Queue:**
  * Komponen: `process.nextTick` queue (khusus Node.js, prioritas mutlak tertinggi) dan Promise Microtask queue (`Promise.resolve()`, `async/await`, `queueMicrotask`).
  * Karakteristik: Harus dievakuasi hingga **benar-benar kosong** sebelum JavaScript runtime menyerahkan eksekusi kembali ke fase Event Loop berikutnya atau merender frame grafis pada browser.
* **Macrotask Queue (Task Queue):**
  * Komponen: Callback dari `setTimeout`, `setInterval`, `setImmediate`, operasi I/O jaringan, dan events I/O.
  * Karakteristik: Dieksekusi satu per satu atau per kelompok batch tergantung fase siklus Event Loop yang sedang aktif.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Fase-Fase Event Loop Libuv di Node.js

Setiap putaran (*tick*) dari Event Loop Node.js melewati fase-fase terstruktur berikut:

#### Fase 1: Timers
Memeriksa struktur *min-heap* internal yang menyimpan callback dari `setTimeout()` dan `setInterval()`. Libuv memeriksa apakah waktu batas (*threshold*) dari timer telah terlampaui berdasarkan jam monotonik sistem. Jika ya, callback dieksekusi.

#### Fase 2: Pending Callbacks
Mengeksekusi callback sistem yang ditunda dari iterasi sebelumnya, seperti penanganan kesalahan sistem I/O (contohnya socket menerima status `ECONNREFUSED` saat mencoba koneksi TCP).

#### Fase 3: Idle, Prepare
Fase internal Libuv. Hanya digunakan untuk sinkronisasi internal dan housekeeping engine; kode JavaScript pengguna tidak berjalan di sini.

#### Fase 4: Poll
Fase paling kritis dalam siklus hidup server:
1. Menghitung berapa lama harus memblokir dan menunggu I/O baru masuk.
2. Memproses peristiwa dalam antrean poll (membaca data dari socket, request baru, dsb.).
3. Jika antrean poll kosong:
   * Jika ada script yang dijadwalkan oleh `setImmediate()`, fase poll akan berakhir dan lanjut ke fase **Check**.
   * Jika tidak ada `setImmediate()`, runtime akan menunggu sementara callback I/O ditambahkan ke antrean, dengan batas waktu sebesar timer terdekat yang akan kadaluarsa.

#### Fase 5: Check
Mengeksekusi callback yang didaftarkan secara eksplisit oleh `setImmediate()`. Hal ini memungkinkan logika berjalan segera setelah fase I/O poll selesai tanpa harus menunggu timer berbasis clock.

#### Fase 6: Close Callbacks
Jika handle atau stream ditutup secara mendadak (misalnya `socket.destroy()`), event `'close'` akan dipancarkan di sini untuk membersihkan resource.

### Mekanisme `process.nextTick` vs `queueMicrotask`
Meskipun keduanya menghasilkan microtask, `process.nextTick` mengelola antreannya sendiri (`nextTickQueue`) yang berada di bawah kendali Node.js secara langsung, bukan V8. 
* Urutan Prioritas Pembersihan:
  1. `process.nextTickQueue`
  2. `PromiseMicrotaskQueue`
* Keduanya memiliki kemampuan untuk menyebabkan **Event Loop Starvation** jika dipanggil secara rekursif, karena loop eksekusi mikro tidak akan pernah mengizinkan Event Loop berpindah ke fase macrotask berikutnya.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL (STEP-BY-STEP)

Mari kita bedah skenario orkestrasi asinkron klasik yang mengeksploitasi perbedaan prioritas eksekusi antara Microtasks, Macrotasks, Timers, dan Immediate calls.

```javascript
// orchestration-demo.js
import fs from 'node:fs';

console.log('1. [Main] Script Start');

// Timer Phase
setTimeout(() => {
  console.log('2. [Timer] setTimeout 0ms executed');
}, 0);

// Check Phase
setImmediate(() => {
  console.log('3. [Check] setImmediate executed');
});

// Microtask: nextTick
process.nextTick(() => {
  console.log('4. [Microtask] process.nextTick 1');
  process.nextTick(() => {
    console.log('5. [Microtask] nested process.nextTick');
  });
});

// Microtask: Promise
Promise.resolve().then(() => {
  console.log('6. [Microtask] Promise.then 1');
}).then(() => {
  console.log('7. [Microtask] Promise.then 2');
});

// Native I/O Polling
fs.readFile(new URL(import.meta.url), () => {
  console.log('8. [I/O Callback] File read completed');
  
  setTimeout(() => {
    console.log('9. [I/O Nested Timer] setTimeout inside I/O');
  }, 0);
  
  setImmediate(() => {
    console.log('10. [I/O Nested Immediate] setImmediate inside I/O');
  });

  process.nextTick(() => {
    console.log('11. [I/O Nested Microtask] nextTick inside I/O');
  });
});

console.log('12. [Main] Script End');
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi kronologis eksekusi dari kode pada **SEKSI 07**:

1. **Baris 4 (`console.log('1. [Main] Script Start')`):**
   * *Aksi:* Masuk ke Call Stack, dicetak ke stdout secara sinkron, frame di-*pop*.
2. **Baris 7-9 (`setTimeout(..., 0)`):**
   * *Aksi:* V8 memanggil binding Node.js untuk mendaftarkan timer dengan delay minimal 1ms. Handle disimpan dalam min-heap timer Libuv.
3. **Baris 12-14 (`setImmediate(...)`):**
   * *Aksi:* Libuv mendaftarkan callback ke fase **Check**.
4. **Baris 17-22 (`process.nextTick(...)`):**
   * *Aksi:* Callback dimasukkan ke dalam `nextTickQueue` Node.js internal.
5. **Baris 25-29 (`Promise.resolve()...`):**
   * *Aksi:* Promise instan terpenuhi. Callback `.then` dimasukkan ke V8 Microtask Queue.
6. **Baris 32-44 (`fs.readFile(...)`):**
   * *Aksi:* Node.js mendelegasikan I/O pembacaan berkas ke Libuv Thread Pool. Call stack kembali bersih.
7. **Baris 46 (`console.log('12. [Main] Script End')`):**
   * *Aksi:* Dicetak sinkron. Main script execution context selesai dan di-*pop* dari Call Stack.
8. **Drain Microtasks Phase (Titik Balik Sinkron ke Asinkron):**
   * Call Stack kosong. Runtime membersihkan `nextTickQueue` terlebih dahulu:
     * Mencetak: `4. [Microtask] process.nextTick 1`
     * Callback ini memicu `nextTick` nested (`5`), yang langsung disisipkan dan diproses tuntas: `5. [Microtask] nested process.nextTick`.
   * Runtime beralih ke V8 Promise Microtask Queue:
     * Mencetak: `6. [Microtask] Promise.then 1`
     * Resolusi rantai menghasilkan: `7. [Microtask] Promise.then 2`.
9. **Event Loop Dimulai (Fase Timers vs Check):**
   * Pada level global konteks, urutan antara `setTimeout(..., 0)` dan `setImmediate()` bersifat non-deterministik tergantung jitter clock CPU saat proses bootstrap runtime. Namun, jika timer sudah kadaluarsa (>=1ms elapsed):
     * Mencetak: `2. [Timer] setTimeout 0ms executed`.
10. **Fase Check (Macrotask):**
    * Mencetak: `3. [Check] setImmediate executed`.
11. **Fase Poll (I/O Resolution):**
    * Thread pool menyelesaikan pembacaan berkas. Callback `fs.readFile` didorong ke Poll queue dan dieksekusi:
      * Mencetak: `8. [I/O Callback] File read completed`.
      * Mendaftarkan Timer baru (`9`), Immediate baru (`10`), dan NextTick baru (`11`).
12. **Drain Microtask di dalam I/O:**
    * Begitu callback I/O selesai, sebelum beralih fase, Microtask dicek:
      * Mencetak: `11. [I/O Nested Microtask] nextTick inside I/O`.
13. **Fase Berikutnya dari Poll:**
    * Berada di dalam siklus I/O, Event Loop **selalu** bergerak dari fase **Poll** langsung ke fase **Check** sebelum kembali memutar ke fase **Timers**.
    * Maka, `setImmediate` dijamin berjalan DULUAN sebelum `setTimeout`:
      * Mencetak: `10. [I/O Nested Immediate] setImmediate inside I/O`.
14. **Siklus Loop Baru - Fase Timers:**
    * Mencetak: `9. [I/O Nested Timer] setTimeout inside I/O`.

---

# SEKSI 09 — STUDI KASUS NYATA (PRODUCTION SCENARIO)

### Skenario: "The Ingestion Death Spiral"
Sebuah arsitektur microservice analitik berbasis Node.js bertugas menerima payload log transaksi finansial melalui HTTP endpoint batch processing, memvalidasi integritas data kriptografi (hashing HMAC via payload traversal), dan menyimpannya ke database.

### Masalah Produksi
Saat traffic spike (lonjakan 10.000 batch/detik), p99 HTTP response time melonjak dari 15ms menjadi 8.500ms. Liveness probe Kubernetes mulai gagal (Health checks timeout), menyebabkan container di-restart paksa (*crash loop backoff*).

### Akar Masalah (Root Cause Analysis)
1. Tim pengembang menggunakan `Promise.all` dengan iterasi array masif yang berisi operasi sinkron kalkulasi parsing parsing/validasi JSON.
2. Pengembang memecah iterasi menggunakan rekursi `process.nextTick` dengan dalih "agar berjalan asinkron".
3. **Dampak Internals:** Jutaan `process.nextTick` membanjiri antrean microtask secara berkelanjutan. Akibatnya, Event Loop **terkunci permanen** (*starvation*) di fase pembersihan microtask, tidak pernah mencapai fase **Poll** (tempat socket HTTP incoming requests baru dan ping HTTP health check dari Kubernetes diterima).

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah solusi arsitektural untuk mendesain batch processor non-blocking dengan memanfaatkan **Event Loop Interleaving** berbasis kooperatif dan isolasi worker thread.

```javascript
// resilient-batch-processor.mjs
import { createServer } from 'node:http';
import { createHmac } from 'node:crypto';
import { Worker, isMainThread, parentPort, workerData } from 'node:worker_threads';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);

// ==========================================
// WORKER THREAD POOL EXECUTION (CPU-BOUND)
// ==========================================
if (!isMainThread) {
  const { batch, secret } = workerData;
  
  // Memproses komputasi CPU intensif di thread terisolasi
  const processed = batch.map((item) => {
    const hash = createHmac('sha256', secret)
      .update(JSON.stringify(item))
      .digest('hex');
    return { ...item, signature: hash, processedAt: Date.now() };
  });

  // Kirim hasil kembali ke thread utama
  parentPort.postMessage(processed);
  process.exit(0);
}

// ==========================================
// MAIN EVENT LOOP THREAD
// ==========================================
function executeInWorker(batch, secret) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(__filename, {
      workerData: { batch, secret },
    });

    worker.on('message', resolve);
    worker.on('error', reject);
    worker.on('exit', (code) => {
      if (code !== 0) {
        reject(new Error(`Worker stopped with exit code ${code}`));
      }
    });
  });
}

/**
 * Teknik Interleaving: Memecah array besar ke potongan kecil
 * dan mengembalikan kontrol ke Event Loop via setImmediate
 */
async function* processChunked(items, chunkSize = 500) {
  for (let i = 0; i < items.length; i += chunkSize) {
    const chunk = items.slice(i, i + chunkSize);
    // Yield chunk untuk diproses
    yield chunk;
    // CRITICAL: Melepaskan kendali ke Check Phase Event Loop
    await new Promise((resolve) => setImmediate(resolve));
  }
}

// HTTP Server
const server = createServer(async (req, res) => {
  if (req.method === 'GET' && req.url === '/healthz') {
    // Health check harus selalu dijawab seketika
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ status: 'UP', timestamp: Date.now() }));
  }

  if (req.method === 'POST' && req.url === '/ingest') {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', async () => {
      try {
        const payload = JSON.parse(body); // Asumsi: payload adalah array of items
        
        if (!Array.isArray(payload)) {
          res.writeHead(400);
          return res.end('Payload must be an array');
        }

        const totalItems = payload.length;
        let processedResults = [];

        // Jika ukuran batch kecil, gunakan chunking kooperatif di main thread
        // Jika sangat masif, delegasikan ke Worker Thread
        if (totalItems > 5000) {
          processedResults = await executeInWorker(payload, 'production-salt-secret');
        } else {
          for await (const chunk of processChunked(payload, 200)) {
            const transformed = chunk.map((item) => ({
              ...item,
              checksum: createHmac('sha256', 'salt').update(JSON.stringify(item)).digest('hex'),
            }));
            processedResults.push(...transformed);
          }
        }

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ 
          status: 'SUCCESS', 
          count: processedResults.length 
        }));
      } catch (err) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end();
});

server.listen(3000, () => {
  console.log('Ingestion engine active on :3000. PID:', process.pid);
});
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Strategi memecah beban komputasi di JavaScript melibatkan trade-off arsitektural yang fundamental:

| Mekanisme | Keunggulan Utama | Titik Kelemahan / Konsekuensi | Skenario Penggunaan yang Tepat |
| :--- | :--- | :--- | :--- |
| **`process.nextTick`** | Dieksekusi paling cepat; menyela siklus saat ini secara instan sebelum I/O. | **Risiko Starvation Tinggi.** Memblokir Event Loop jika terjadi pemanggilan bertingkat. | Membersihkan resource segera setelah konstruktor objek, propagasi error sebelum I/O. |
| **`setImmediate`** | Ramah terhadap Event Loop; berjalan di fase *Check* setelah I/O Poll selesai diproses. | Memiliki sedikit overhead penjadwalan dibandingkan eksekusi microtask murni. | Memecah komputasi masif (*cooperative multitasking*) tanpa memblokir I/O atau health check. |
| **`setTimeout(fn, 0)`** | Standar universal (ada di Web API dan Node.js). | Presisi timing rendah; dipaksa delay minimal ~1ms di Node.js (4ms di browser setelah 5 nesting). Min-heap traversal cost. | Penjadwalan backward-compatible di browser primitif; fallback kompatibilitas. |
| **`Worker Threads`** | **True Parallelism.** Melepaskan beban dari main thread V8 sepenuhnya ke core CPU lain. | Overhead alokasi memori tinggi (inisiasi instance V8 baru), serialization cost via structured clone. | Enkripsi berat, kompresi berkas, image resizing, manipulasi data masif (>10MB). |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Perilaku Non-Deterministik Top-Level Timers vs Immediate
```javascript
// standalone-race.js
setTimeout(() => console.log('timeout'), 0);
setImmediate(() => console.log('immediate'));
```
* **Pitfall:** Output dari file di atas **tidak dapat diprediksi**. Eksekusi bisa menghasilkan `timeout -> immediate` atau `immediate -> timeout`.
* **Mengapa?** Memasuki event loop membutuhkan waktu beberapa mikrodetik (karena CPU scheduler OS). Jika entri ke loop membutuhkan waktu >1ms, timer dianggap kadaluarsa dan `timeout` berjalan lebih dulu. Jika entri loop membutuhkan <1ms, timer belum siap, sehingga fase timers terlewati dan fase check mengeksekusi `immediate` lebih dulu.
* **Solusi Edge Case:** Jika kode tersebut dibungkus di dalam callback I/O (`fs.readFile`), `setImmediate` **dijamin 100% selalu** dieksekusi lebih dulu karena I/O selesai di fase *Poll*, dan fase berikutnya adalah *Check*.

### 2. The Unhandled Microtask Queue Depth Bug
```javascript
function recursiveDrain() {
  return Promise.resolve().then(() => recursiveDrain());
}
recursiveDrain(); 
// Call Stack TIDAK meledak (No "Maximum call stack size exceeded"), 
// tetapi server MEMBEKU total secara hening (Silent Event Loop Hang).
```
* **Pitfall:** `RangeError: Maximum call stack size exceeded` hanya terjadi pada synchronous function calls. Microtasks membebaskan call stack saat resolved, tetapi menambahkan task baru ke queue secara terus-menerus. Hal ini menipu developer karena tidak ada *Stack Overflow Error*, tetapi sistem mengalami denial-of-service internal.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Mengabaikan Floating Promises dalam Loop
* ❌ **Salah:** Menggunakan `forEach` dengan callback `async`.
```javascript
// Loop berjalan sinkron! Array.prototype.forEach tidak menunggu promise selesai.
records.forEach(async (record) => {
  await db.save(record);
});
console.log('Semua record tersimpan? SALAH, ini jalan duluan.');
```
* ✔️ **Benar:** Gunakan loop `for...of` untuk sekuensial, atau `Promise.all()` / `p-limit` untuk eksekusi paralel terkendali.
```javascript
// Sekuensial & Aman
for (const record of records) {
  await db.save(record);
}

// Paralel Terkendali
await Promise.all(records.map((r) => db.save(r)));
```

### 2. Mencampuradukkan Error Synchronous dan Asynchronous di EventEmitter
* ❌ **Salah:** Mengandalkan `try...catch` blok di luar async handler.
```javascript
try {
  emitter.on('event', async () => {
    throw new Error('Crash!'); // Error ini menjadi UnhandledPromiseRejection!
  });
} catch (err) {
  // Blok ini TIDAK AKAN PERNAH menangkap error di atas
}
```
* ✔️ **Benar:** Tangkap error di dalam callback atau gunakan utilitas `events.captureRejections`.
```javascript
import { EventEmitter } from 'node:events';
const emitter = new EventEmitter({ captureRejections: true });

emitter.on('event', async () => {
  throw new Error('Handled!');
});
emitter.on('error', (err) => {
  console.error('Error tertangkap dengan aman:', err.message);
});
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan `queueMicrotask()` alih-alih `Promise.resolve().then()`:**
   Jika tujuan arsitektur Anda murni untuk menunda pekerjaan ke antrean microtask tanpa memproses *value return*, hindari alokasi objek `Promise` tambahan. Gunakan API platform standar: `queueMicrotask(callback)`.
2. **Standardisasi API Asinkron yang Konsisten:**
   Fungsi Anda harus **100% sinkron** atau **100% asinkron**. Jangan pernah merilis fungsi dengan sifat *Zälgo* (berjalan sinkron pada kondisi cache hit, dan asinkron pada cache miss).
   ```javascript
   // Anti-pattern (Zälgo):
   function getData(id, cb) {
     if (cache.has(id)) return cb(cache.get(id)); // SINKRON
     fs.readFile(id, (err, data) => cb(data));    // ASINKRON
   }
   
   // Benar (Konsisten Asinkron):
   function getData(id, cb) {
     if (cache.has(id)) {
       return queueMicrotask(() => cb(cache.get(id)));
     }
     fs.readFile(id, (err, data) => cb(data));
   }
   ```
3. **Konfigurasi Ukuran Thread Pool secara Sadar:**
   Jika aplikasi Anda sangat bergantung pada operasi I/O disk lokal atau enkripsi native (`bcrypt`, `crypto`), sesuaikan variabel lingkungan sebelum proses inisialisasi:
   ```bash
   UV_THREADPOOL_SIZE=64 node server.js
   ```

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Benchmarking Alokasi Penjadwalan: Microtask vs Macrotask
Setiap kali menginstansiasi Promise, V8 harus mengalokasikan memori untuk promise capability record, resolve/reject closures, dan reaksi microtask.

```javascript
// benchmark-scheduler.mjs
import { bench, run } from 'mitata'; // Engine benchmark modern

const iterations = 1_000_000;

bench('queueMicrotask', () => {
  return new Promise((resolve) => {
    let count = 0;
    function step() {
      if (++count >= 1000) return resolve();
      queueMicrotask(step);
    }
    step();
  });
});

bench('Promise.resolve().then', () => {
  return new Promise((resolve) => {
    let count = 0;
    function step() {
      if (++count >= 1000) return resolve();
      Promise.resolve().then(step);
    }
    step();
  });
});

bench('setImmediate', () => {
  return new Promise((resolve) => {
    let count = 0;
    function step() {
      if (++count >= 1000) return resolve();
      setImmediate(step);
    }
    step();
  });
});

await run();
```

### Optimasi Latensi: Hindari Event Loop Congestion
Untuk menjaga **Event Loop Lag** di bawah ambang batas kritis (umumnya <20ms di sistem SLA tinggi):
* Batasi ukuran batch database fetch (gunakan cursor/streams daripada memuat 100.000 entity sekaligus ke memory heap).
* Gunakan algoritma parsing JSON streaming (`JSONStream` atau parsing berbasis SAX) untuk file ukuran besar (>50MB).

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Prototype Pollution via Microtask Race Conditions
Ketika dua operasi pembaruan data memodifikasi shared object prototype di sela-sela yield mikro-eksekusi, *race condition* dapat dimanfaatkan penyerang untuk menyuntikkan properti berbahaya (`__proto__`).
* **Hardening:** Selalu bekukan objek konfigurasi sistem menggunakan `Object.freeze()` atau gunakan `Object.create(null)` untuk dictionary yang diakses di berbagai siklus async.

### 2. Regular Expression Denial of Service (ReDoS) yang Membekukan Event Loop
* **Vulnerabilitas:** Regex engine di V8 bersifat sinkron. Eksekusi regex dengan kompleksitas polinomial/eksponensial pada string input dari user yang tidak divalidasi akan memblokir main thread secara permanen.
* **Mitigasi:**
  * Gunakan parser non-backtracking seperti engine native C++ berbasis re2 (misalnya via binding `node-re2`).
  * Terapkan *timeout boundary* atau delegasikan evaluasi regex berisiko ke worker thread terisolasi.

```javascript
import { Worker } from 'node:worker_threads';

function safeRegexMatch(pattern, string, timeoutMs = 100) {
  return new Promise((resolve, reject) => {
    const workerScript = `
      const { parentPort, workerData } = require('node:worker_threads');
      const { pattern, string } = workerData;
      const regex = new RegExp(pattern);
      parentPort.postMessage(regex.test(string));
    `;
    
    const worker = new Worker(workerScript, {
      eval: true,
      workerData: { pattern, string }
    });

    const timer = setTimeout(() => {
      worker.terminate();
      reject(new Error('Regex execution timed out (ReDoS Protection)'));
    }, timeoutMs);

    worker.on('message', (result) => {
      clearTimeout(timer);
      resolve(result);
    });
    
    worker.on('error', reject);
  });
}
```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Memantau Event Loop Lag dengan `perf_hooks`
Node.js memiliki API native bawaan untuk mengukur latensi Event Loop secara real-time melalui histogram presisi tinggi.

```javascript
// loop-monitor.mjs
import { monitorEventLoopDelay } from 'node:perf_hooks';

// Resolusi sampling dalam milidetik
const histogram = monitorEventLoopDelay({ resolution: 20 });
histogram.enable();

setInterval(() => {
  const p50 = (histogram.percentile(50) / 1e6).toFixed(2);
  const p99 = (histogram.percentile(99) / 1e6).toFixed(2);
  const max = (histogram.max / 1e6).toFixed(2);

  console.log(`[EVENT LOOP HEALTH] P50: ${p50}ms | P99: ${p99}ms | Max: ${max}ms`);

  if (histogram.percentile(99) > 50e6) { // Jika P99 > 50ms
    console.error('CRITICAL WARNING: Event Loop Lag melebihi threshold SLA!');
  }

  histogram.reset();
}, 2000).unref(); // unref agar interval ini tidak menahan proses exit
```

### 2. Tracing Context Lintas Tick dengan `AsyncLocalStorage`
Debugging panggilan asinkron yang terputus dapat dipecahkan menggunakan modul bawaan `node:async_hooks`.

```javascript
// async-context-trace.mjs
import { AsyncLocalStorage } from 'node:async_hooks';
import { randomUUID } from 'node:crypto';

const asyncLocalStorage = new AsyncLocalStorage();

function logWithTrace(message) {
  const store = asyncLocalStorage.getStore();
  const traceId = store ? store.traceId : 'SYSTEM';
  console.log(`[${new Date().toISOString()}] [TraceID: ${traceId}] ${message}`);
}

async function performDatabaseQuery() {
  logWithTrace('Mengeksekusi query database...');
  await new Promise((resolve) => setTimeout(resolve, 50));
  logWithTrace('Query database berhasil.');
}

// Simulasi Request Handler
function handleRequest() {
  const context = { traceId: randomUUID() };
  asyncLocalStorage.run(context, async () => {
    logWithTrace('Menerima request baru');
    await performDatabaseQuery();
    logWithTrace('Request selesai diproses');
  });
}

handleRequest();
handleRequest();
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### Hirarki Prioritas Eksekusi (Atas ke Bawah)
```
1. SINKRON        : Call Stack Execution Context (Main Thread V8).
2. MICROTASK (1)  : process.nextTick Queue (Node.js engine level).
3. MICROTASK (2)  : Promise.then(), queueMicrotask, MutationObserver.
4. MACRO (Timer)  : setTimeout, setInterval (Ketika delta time expired).
5. MACRO (I/O)    : Poll Phase (Network socket, disk read).
6. MACRO (Check)  : setImmediate.
7. MACRO (Close)  : Close handles (socket.destroy()).
```

### Karakteristik Pemanggilan Operasional

* **`process.nextTick`**: Menunda eksekusi ke ujung tumpukan saat ini sebelum menyentuh I/O. Gunakan seminimal mungkin.
* **`queueMicrotask`**: Standar ECMAScript untuk memasukkan tugas ke microtask queue tanpa alokasi promise overhead.
* **`setImmediate`**: Penjadwalan macrotask yang aman dari starvation; berjalan tepat setelah fase Poll I/O selesai.
* **`setTimeout(fn, 0)`**: Penjadwalan berbasis timer; memiliki delay minimum ~1ms dan bergantung pada struktur data internal min-heap runtime.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1 - 5)

1. **Bagian mana dari runtime yang bertanggung jawab langsung mengeksekusi instruksi JavaScript seperti operasi aritmatika dan alokasi variabel?**
   * A) Libuv Thread Pool
   * B) V8 Call Stack
   * C) Operating System Kernel
   * D) Event Loop Check Phase

2. **Kapan V8 memproses antrean microtask?**
   * A) Tepat setiap 10 milidetik sekali via interval.
   * B) Hanya saat thread utama Node.js mengalami crash.
   * C) Tepat setelah Call Stack kosong, sebelum kendali dialihkan ke fase Event Loop berikutnya.
   * D) Di akhir fase Timers saja.

3. **Manakah dari antrean berikut yang dieksekusi lebih dahulu dalam satu tick penanganan microtask di Node.js?**
   * A) `Promise.then` callback
   * B) `process.nextTick` callback
   * C) `setImmediate` callback
   * D) `setTimeout` callback

4. **Operasi mana yang secara default didelegasikan ke Libuv Worker Thread Pool di Node.js?**
   * A) Pembacaan respons HTTP via incoming socket.
   * B) `console.log()`
   * C) Operasi sistem berkas sinkron (`fs.readFileSync`).
   * D) Operasi hashing menggunakan fungsi asinkron pustaka `crypto` (misal `crypto.pbkdf2`).

5. **Apa dampak utama dari pemanggilan rekursif tak berujung pada `process.nextTick`?**
   * A) Call Stack meledak dengan pesan `Maximum call stack size exceeded`.
   * B) Memory Heap bocor seketika dan memicu Kernel OOM-Killer.
   * C) Event Loop macet total (*starvation*) tanpa ada pesan error crash langsung.
   * D) Node.js otomatis mendiversifikasi eksekusi ke worker thread baru.

---

### Soal Intermediate (6 - 10)

6. **Mengapa urutan eksekusi antara `setTimeout(fn, 0)` dan `setImmediate(fn)` tidak pasti ketika dipanggil di tingkat terluar (top-level scope) sebuah modul?**
   * A) Karena V8 menolak mengeksekusi `setImmediate` di tingkat modul.
   * B) Karena ketidakpastian jitter waktu CPU OS saat Node.js menginisialisasi loop, menentukan apakah 1 milidetik telah berlalu sebelum fase Timer dimasuki.
   * C) Karena `setTimeout` selalu dijalankan di thread background secara acak.
   * D) Karena file module di-load secara asynchronous via Libuv.

7. **Perhatikan kode berikut:**
   ```javascript
   fs.readFile('data.txt', () => {
     setTimeout(() => console.log('A'), 0);
     setImmediate(() => console.log('B'));
   });
   ```
   **Output mana yang dijamin secara deterministik akan selalu tercetak pertama kali di console?**
   * A) `A`
   * B) `B`
   * C) Tidak deterministik, bergantung performa I/O harddisk.
   * D) Bergantung pada ukuran byte dari `data.txt`.

8. **Apa perbedaan struktural utama antara `Worker Threads` dan proses asynchronous biasa via callback Libuv?**
   * A) Worker Threads berbagi Call Stack yang sama dengan thread utama.
   * B) Worker Threads menginstansiasi instance V8 Engine Isolate dan thread execution terpisah secara paralel.
   * C) Worker Threads tidak dapat melakukan manipulasi ArrayBuffer.
   * D) Worker Threads hanya dapat dijalankan di lingkungan Linux.

9. **Jika server web Node.js Anda melaporkan "Event Loop Lag" yang tinggi tetapi utilisasi CPU hanya berada di angka 10%, apa kemungkinan masalah arsitektural yang paling logis?**
   * A) Thread pool terkunci oleh operasi crypto masif.
   * B) Memory Leak yang memicu Garbage Collection sweep non-stop.
   * C) Terdapat operasi I/O blocking secara sinkron (seperti `fs.readFileSync` atau synchronous child process) yang menahan main thread.
   * D) Jaringan internet server terputus.

10. **Bagaimana cara mencegah Starvation pada antrean microtask yang mengolah data stream masif secara terus-menerus?**
    * A) Membungkus rantai promise ke dalam `async/await`.
    * B) Menyisipkan `await new Promise(resolve => setImmediate(resolve))` di tengah iterasi untuk memberi ruang bagi fase Event Loop lain.
    * C) Mengganti semua promise menjadi `process.nextTick`.
    * D) Mengubah variabel lingkungan `UV_THREADPOOL_SIZE=1`.

---

### Kunci Jawaban & Pembahasan Singkat

1. **B** — V8 Call Stack adalah komponen yang mengeksekusi instruksi JavaScript langsung. Libuv menangani koordinasi asynchronous dan thread pool.
2. **C** — Antrean microtask dievakuasi setiap kali Call Stack kosong, sebelum runtime melanjutkan ke tahapan fase Event Loop lainnya.
3. **B** — Node.js memprioritaskan antrean `nextTickQueue` sebelum antrean V8 Microtask (`Promise.then`).
4. **D** — Operasi kriptografi asinkron (`crypto.pbkdf2`) dan I/O filesystem asinkron dikerjakan oleh Libuv Thread Pool. Socket jaringan ditangani polling non-blocking kernel (`epoll/kqueue`).
5. **C** — Microtask rekursif tidak pernah membiarkan Call Stack menyerahkan kontrol kembali ke Event Loop, memicu starvation total tanpa *Call Stack Overflow*.
6. **B** — Timer 0ms dikonversi internal menjadi minimal 1ms. Jika tick loop pertama diproses di bawah 1ms, timer dilewati ke Check phase (`setImmediate`). Jika lambat, timer dieksekusi lebih dulu.
7. **B** — Callback I/O selesai dieksekusi di fase *Poll*. Dari fase *Poll*, siklus Event Loop **selalu** bergerak langsung menuju fase *Check* tempat `setImmediate` berada.
8. **B** — Setiap Worker Thread Node.js memiliki V8 Isolate dan Event Loop tersendiri, berjalan paralel di tingkat OS thread.
9. **C** — Utilisasi CPU rendah dengan lag Event Loop tinggi menandakan thread utama tertahan (idle-waiting) menunggu syscall sinkron selesai (misal `fs.readFileSync`).
10. **B** — Menggunakan `setImmediate` dalam yielding loop memutus monopolitasi microtask dan menyerahkan kendali kembali ke event loop siklus berikutnya.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Objektif Proyek: Membangun "Event-Loop Aware Priority Task Queue"
Bangun sebuah modul JavaScript murni (ESM) bernama `PriorityTaskScheduler` yang mampu menyeimbangkan antrean tugas dengan jaminan **Zero Event-Loop Starvation**.

### Spesifikasi Teknis yang Harus Dipenuhi:
1. **Dukungan Prioritas Multi-Level:**
   * Prioritas `CRITICAL`: Diproses secepat mungkin menggunakan microtask interleaving (`queueMicrotask`).
   * Prioritas `NORMAL`: Diproses menggunakan alokasi macrotask kooperatif (`setImmediate`).
   * Prioritas `LOW`: Diproses hanya saat event loop berada dalam kondisi idle atau terjadwal via batasan kuota waktu.
2. **Auto-Yielding Mechanism:**
   * Scheduler harus menghitung durasi waktu eksekusi task yang berjalan sinkron. Jika pemrosesan batch telah memakan waktu Call Stack > **16ms** (batas 1 frame render 60fps), scheduler **wajib menghentikan eksekusi sementara** (*yield*), memberikan kontrol kembali ke Event Loop (Check Phase) selama 1 tick, kemudian melanjutkan task yang tersisa.
3. **Observability Hook:**
   * Terapkan event listener yang memancarkan metrics: `taskExecuted`, `lagRecorded`, dan `yieldTriggered`.

### Kerangka Awal Kode (Scaffolding):

```javascript
// priority-scheduler.mjs
import { EventEmitter } from 'node:events';
import { performance } from 'node:perf_hooks';

export class PriorityTaskScheduler extends EventEmitter {
  #criticalQueue = [];
  #normalQueue = [];
  #isRunning = false;
  #timeSliceMs = 16; // 16ms budget per cycle

  constructor(timeSliceMs = 16) {
    super();
    this.#timeSliceMs = timeSliceMs;
  }

  enqueue(taskFn, priority = 'NORMAL') {
    if (typeof taskFn !== 'function') throw new TypeError('Task must be a function');
    
    if (priority === 'CRITICAL') {
      this.#criticalQueue.push(taskFn);
    } else {
      this.#normalQueue.push(taskFn);
    }

    this.#schedule();
  }

  #schedule() {
    if (this.#isRunning) return;
    this.#isRunning = true;

    // TODO: Implementasikan loop penjadwalan.
    // Syarat:
    // 1. Habiskan criticalQueue menggunakan queueMicrotask tanpa membuat hang.
    // 2. Gunakan performance.now() untuk menghitung alokasi budget timeSliceMs.
    // 3. Jika durasi eksekusi melebihi this.#timeSliceMs, lepaskan kontrol via setImmediate.
    // 4. Emit event 'yieldTriggered' saat eksekusi ditunda.
    // 5. Emit event 'drain' saat kedua antrean telah selesai dieksekusi.
  }
}

// Uji coba implementasi Anda dengan mensimulasikan 50.000 komputasi intensif!
```

### Kriteria Kelulusan Uji Praktikum:
1. Aplikasi pengujian mampu menjalankan 10.000 heavy mathematical tasks tanpa membuat HTTP server yang berjalan di port yang sama mengalami timeout pada health check `/healthz`.
2. Monitoring log membuktikan metrik event `yieldTriggered` terpanggil secara berkala saat queue sedang terisi penuh.
3. Call stack tracing tidak pernah mengalami `RangeError: Maximum call stack size exceeded`.