# BAB 02: Quiz, Challenge, & Knowledge Check
**Asynchronous Runtime Internals & Event Loop Orchestration**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Eksekusi Call Stack vs Task Queue vs Microtask Queue
Jelaskan secara deterministik siklus hidup eksekusi JavaScript engine ketika mengeksekusi potongan kode berikut. Uraikan status Call Stack, Web APIs/Node C++ APIs, Microtask Queue, dan Macrotask (Task) Queue pada setiap tahapannya:
```javascript
console.log('A');
setTimeout(() => console.log('B'), 0);
Promise.resolve().then(() => {
  console.log('C');
  queueMicrotask(() => console.log('D'));
});
console.log('E');
```
*Tuntutan:* Jelaskan mengapa output tertentu dicetak sebelum output lainnya dengan merujuk pada aturan *microtask checkpoint* dalam spesifikasi HTML/ECMAScript.

---

### Soal 1.2: Perbedaan Fundamental Event Loop Browser (HTML5) vs Libuv (Node.js)
Meskipun sama-sama menjalankan JavaScript berbasis event-driven, arsitektur Event Loop pada browser dan Node.js memiliki perbedaan mendasar:
1. Uraikan perbedaan struktural fase eksekusi antara Browser Event Loop (relasinya dengan rendering engine pipeline: rAF, Style, Layout, Paint) dengan Libuv Event Loop phases (`Timers`, `Pending Callbacks`, `Idle/Prepare`, `Poll`, `Check`, `Close Callbacks`).
2. Kapan tepatnya Microtask Queue dikuras (*drained*) pada masing-masing platform tersebut (terutama perhatikan evolusi transisi perilaku Node.js v11 ke atas)?

---

### Soal 1.3: Konkurensi Single-Threaded dan Paradigma Non-Blocking I/O
JavaScript sering disebut sebagai bahasa yang *"Single-Threaded Non-Blocking Asynchronous Concurrent"*.
1. Jika thread eksekusi JavaScript utama (V8 main thread) hanya satu, jelaskan secara mekanistik bagaimana sistem operasi (melalui OS kernel primitives seperti `epoll`, `kqueue`, atau `IOCP`) berinteraksi dengan runtime untuk memungkinkan operasi non-blocking I/O tanpa membebani thread utama.
2. Apa perbedaan peran OS-level non-blocking primitives tersebut dibandingkan dengan Libuv Worker Thread Pool (`uv_threadpool_t`)? Sebutkan kategori operasi apa saja yang didelegasikan ke thread pool vs OS asynchronous primitives!

---

### Soal 1.4: Desugaring `async/await` dan Penanganan State Machine
Sintaks `async/await` adalah *syntactic sugar* di atas Promise dan Generator.
1. Bagaimana JavaScript Engine (seperti V8) mentransformasi fungsi `async` menjadi state machine berbasis Promise?
2. Ketika eksekusi mencapai *keyword* `await <expression>`, jelaskan apa yang terjadi pada Execution Context di Call Stack, bagaimana engine menangguhkan (*suspend*) eksekusi fungsi, dan mekanisme internal apa yang menyambung kembali (*resume*) fungsi tersebut ketika Promise berstatus *resolved*.

---

### Soal 1.5: Hierarki Prioritas: `process.nextTick()`, `queueMicrotask()`, dan `setImmediate()`
Pada runtime Node.js:
1. Di mana posisi antrean `process.nextTick()` dalam hierarki pemrosesan tugas asynchronous jika dibandingkan dengan Standard Microtask Queue (`Promise.then` / `queueMicrotask`) dan `setImmediate()`?
2. Mengapa penggunaan rekursif dari `process.nextTick()` jauh lebih berbahaya bagi kestabilan I/O polling daripada penggunaan rekursif `setImmediate()`? Jelaskan konsep *starvation* yang terjadi.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Kasus Event Loop Starvation & Microtask Choking
Perhatikan implementasi pemrosesan batch data berikut ini:
```javascript
function processLargeArray(items) {
  return new Promise((resolve) => {
    function iterate(index) {
      if (index >= items.length) {
        return resolve();
      }
      heavySynchronousComputation(items[index]);
      Promise.resolve().then(() => iterate(index + 1));
    }
    iterate(0);
  });
}
```
1. Meskipun menggunakan `Promise.resolve().then()`, mengapa fungsi di atas tetap membekukan (*freeze*) rendering UI di browser atau menghentikan penerimaan koneksi TCP baru di Node.js jika `items.length` bernilai 1.000.000?
2. Modifikasi arsitektur fungsi tersebut agar komputasi dapat berjalan secara kooperatif (*cooperative multitasking*) tanpa memblokir I/O dan rendering pipeline. Jelaskan trade-off latensi dari solusi Anda.

---

### Soal 2.2: Determinisme Eksekusi `setTimeout(..., 0)` vs `setImmediate()`
Pada Node.js, eksekusi potongan kode berikut di level top-level (main module) menghasilkan output yang non-deterministik (kadang `Timeout` lalu `Immediate`, kadang sebaliknya):
```javascript
setTimeout(() => console.log('Timeout'), 0);
setImmediate(() => console.log('Immediate'));
```
1. Jelaskan secara mekanistik internal (analisis Libuv timer resolution, clock drift, dan proses inisialisasi Event Loop) mengapa urutannya bisa berfluktuasi.
2. Bagaimana cara merekayasa konteks eksekusi kode tersebut agar urutan eksekusinya menjadi 100% deterministik (`Immediate` selalu berjalan sebelum `Timeout`)? Buktikan dengan teori fase Event Loop.

---

### Soal 2.3: Bottleneck Thread Pool Libuv pada Skala Tinggi
Secara *default*, Node.js mengalokasikan ukuran `UV_THREADPOOL_SIZE` sebesar 4.
1. Jika server Node.js Anda menangani 500 request konkruen per detik, dan setiap request memanggil fungsi `crypto.pbkdf2` atau membaca file via `fs.readFile`, apa dampak langsung arsitekturalnya terhadap waktu tunggu (*queue waiting time*) request lainnya, termasuk operasi DNS lookup (`dns.lookup`)?
2. Bagaimana strategi Anda mendiagnosis bahwa bottleneck latensi aplikasi berasal dari antrean Libuv Thread Pool dan bukan dari Event Loop main thread?

---

### Soal 2.4: Siklus `requestAnimationFrame` vs `requestIdleCallback` vs Microtasks
Dalam browser modern, render pipeline beroperasi pada frekuensi refresh rate layar (misal 60Hz atau 120Hz).
1. Uraikan secara presisi di mana posisi eksekusi `requestAnimationFrame` (rAF) dan `requestIdleCallback` (rIC) dalam satu *Frame Lifecycle* (Input events -> Timers -> rAF -> Style -> Layout -> Paint -> Idle).
2. Jika sebuah mutasi DOM dilakukan di dalam callback `Promise.resolve().then()`, apakah browser langsung melakukan render/paint seketika itu juga? Jelaskan interaksi antara microtask execution checkpoint dengan *Rendering Opportunity*.

---

### Soal 2.5: Kebocoran Memori (Memory Leak) dalam Asynchronous Closures
Perhatikan implementasi asynchronous event listener berikut:
```javascript
class TelemetryManager {
  constructor() {
    this.buffer = new Array(1e6).fill('METRIC_DATA');
    this.init();
  }
  
  init() {
    window.addEventListener('resize', async () => {
      await this.flush();
      console.log('Processed metrics for window resize');
    });
  }

  async flush() {
    // Simulasi pengiriman data
    await fetch('/api/metrics', { method: 'POST', body: JSON.stringify(this.buffer) });
  }
}
```
1. Jelaskan mengapa pola di atas berisiko tinggi menciptakan kebocoran memori parah ketika instance `TelemetryManager` dibuat dan dibuang berkali-kali dalam Single Page Application (SPA).
2. Bagaimana retain graph V8 mempertahankan memori `this.buffer` meskipun instance `TelemetryManager` di-dereferensikan di luar class? Bagaimana cara memperbaikinya secara definitif?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Latensi Spiking & Kubernetes Pod CrashLoopBackOff
**Konteks Sistem:**
Sebuah microservice API Gateway berbasis Node.js (v20 LTS) berjalan di Kubernetes. Tiba-tiba metrik P99 latency melonjak dari 15ms ke 12.000ms. Liveness dan readiness probe Kubernetes memanggil endpoint HTTP `/healthz` setiap 5 detik dengan timeout 2 detik. Karena endpoint `/healthz` gagal merespons tepat waktu, Kubernetes menandai pod sebagai *unhealthy* dan me-restart pod secara berantai (*cascading failure*), menyebabkan status *CrashLoopBackOff*.

**Investigasi Awal:**
- Utilisasi memori pod berada di angka normal (35%).
- Metrik CPU menunjukkan saturasi 100% pada satu core CPU pod limit.
- Log aplikasi menunjukkan bahwa lonjakan traffic diiringi oleh payload JSON berukuran besar (15MB - 30MB) yang dikirim oleh klien melalui endpoint `/sync-catalog`. Endpoint ini melakukan `JSON.parse()` dan manipulasi array secara sinkron sebelum menyimpannya ke database.

**Pertanyaan Diagnostik & Solusi:**
1. Mengapa endpoint `/healthz` mengalami timeout padahal ia hanya mengembalikan string sederhana `{ status: "ok" }` yang tidak bergantung pada database?
2. Bagaimana cara Anda menggunakan Node.js Performance Hooks (`perf_hooks`) untuk memantau Event Loop Delay / Lag secara kuantitatif?
3. Rancang arsitektur perbaikan komprehensif untuk menangani payload JSON raksasa tersebut tanpa memblokir Event Loop main thread, sehingga pod `/healthz` tetap responsif di bawah SLA 10ms.

---

### Skenario B: Race Condition & Data Corruption pada High-Concurrency Balance Deduction
**Konteks Sistem:**
Sebuah platform flash sale memiliki sistem dompet digital internal (*digital wallet*). Sistem dibangun di atas Node.js dan MongoDB. Saat flash sale dimulai, ribuan request masuk dalam hitungan milidetik dari pengguna yang sama untuk membeli barang promosi dengan memotong saldo dompet mereka.

**Potongan Kode Transaksi Pengguna:**
```javascript
async function deductBalance(userId, amount) {
  const user = await db.collection('wallets').findOne({ userId });
  
  if (user.balance >= amount) {
    const newBalance = user.balance - amount;
    // Simulasi latency jaringan eksternal / fraud check
    await auditLogClient.recordTransaction(userId, amount);
    
    await db.collection('wallets').updateOne(
      { userId },
      { $set: { balance: newBalance } }
    );
    return { success: true, newBalance };
  } else {
    throw new Error('Insufficient balance');
  }
}
```

**Permasalahan:**
Pengguna dengan saldo awal Rp 100.000 berhasil mengeksekusi 5 request simultan masing-masing senilai Rp 80.000. Saldo akhir pengguna menjadi minus (atau hanya terpotong satu kali), dan perusahaan mengalami kerugian finansial akibat *overselling*.

**Pertanyaan Diagnostik & Solusi:**
1. Bedah secara anatomis mengapa *Run-to-Completion invariant* JavaScript **tidak** mencegah terjadinya race condition di atas begitu kata kunci `await` terlibat.
2. Mengapa isolasi transaksi database tradisional (seperti Read Committed) sering kali gagal atau menyebabkan deadlock jika orchestration logic ada di Node.js runtime?
3. Rancang solusi arsitektural di layer JavaScript runtime (misalnya menggunakan Distributed Locking via Redis Redlock, Mutex, atau Atomic Database Operations) untuk menjamin konsistensi data secara absolut. Berikan contoh implementasi kodenya yang aman terhadap konkruensi.

---

### Skenario C: Dilema Arsitektur High-Throughput Ingestion Engine
**Konteks Sistem:**
Anda adalah Principal Architect pada perusahaan platform IoT. Sistem Anda harus mengonsumsi 50.000 event/detik via WebSocket connection. Setiap event memerlukan:
1. Validasi skema dan sanitasi data (CPU bound, ringan: ~0.1ms).
2. Dekompresi payload zlib/gzip (CPU bound, sedang: ~1.5ms).
3. Query ke local in-memory cache untuk pengayaan metadata (I/O bound, cepat: ~0.5ms).
4. Pengiriman batch event ke Kafka broker (Network I/O bound).

Jika Anda memproses seluruh alur dalam single thread Node.js standar, Event Loop akan tersedak pada langkah kompresi (Zlib) dan validasi skema.

**Pertanyaan Evaluasi & Trade-off:**
Bandingkan 3 pendekatan arsitektur berikut:
- **Pendekatan 1:** Eksekusi langsung di Main Thread dengan optimasi Libuv threadpool (`UV_THREADPOOL_SIZE=64`).
- **Pendekatan 2:** Memanfaatkan Node.js `worker_threads` dengan arsitektur Actor Model atau Message Passing pool (`Piscina`).
- **Pendekatan 3:** Arsitektur hybrid Multi-Process via Node.js Cluster Module yang dikombinasikan dengan offloading Zlib ke native C++ addon.

Analisis setiap pendekatan dari sudut pandang:
- *Overhead memory footprint* dan konsumsi resource.
- *Inter-thread serialization cost* (Structured Clone Algorithm vs SharedArrayBuffer).
- Kompleksitas mitigasi backpressure saat Kafka mengalami transient delay.
- Pendekatan mana yang Anda pilih sebagai arsitektur final? Berikan justifikasi teknisnya.

---

## 4. Chapter Challenge

### Tantangan Praktis: Membangun Resilient Concurrency Scheduler & Rate-Limiter Engine Berbasis Event-Loop-Aware Priority Queue

#### Problem Statement
Dalam arsitektur mikroservis modern, kegagalan umum terjadi ketika sebuah service dibombardir oleh antrean request yang tidak terkontrol, memicu tingginya Event Loop Lag, degradasi performa, dan akhirnya *Out-of-Memory* (OOM).

Anda ditugaskan merancang dan mengimplementasikan sebuah library mandiri (*zero-dependency*) bernama **`ResilientTaskScheduler`** di Node.js (ESM). Scheduler ini harus mengeksekusi task asynchronous berdasarkan prioritas, membatasi konkruensi maksimum, serta memiliki kemampuan adaptif (*adaptive backpressure*) yang otomatis menghentikan atau menunda eksekusi task baru jika Event Loop Lag terdeteksi melewati ambang batas toleransi (*threshold*).

#### Requirements
1. **Concurrency Control:** Batasi eksekusi task yang berjalan bersamaan (*in-flight concurrent tasks*) sesuai parameter `maxConcurrency`.
2. **Priority Queue System:** Task dapat didaftarkan dengan level prioritas: `CRITICAL`, `HIGH`, `NORMAL`, `LOW`. Task dengan prioritas lebih tinggi harus dieksekusi lebih dulu saat ada slot konkruensi yang kosong.
3. **Adaptive Event Loop Lag Detection:** 
   - Gunakan `perf_hooks` (misal: `monitorEventLoopDelay`) untuk mengukur p99 event loop lag secara berkala.
   - Jika p99 lag melebihi `lagThresholdMs` (misal: 50ms), scheduler masuk ke mode `DEGRADED`. Dalam mode ini, task berprioritas `LOW` dan `NORMAL` harus ditangguhkan (*paused/delayed*), dan hanya task `CRITICAL` atau `HIGH` yang boleh dieksekusi hingga lag kembali normal.
4. **Timeout & Cancellation Handling:**
   - Setiap task harus mendukung opsi `timeoutMs`. Jika task berjalan melebihi batas waktu tersebut, task dibatalkan secara deterministik menggunakan `AbortController` / `AbortSignal`.
5. **Drain & Telemetry Event Hooks:**
   - Menyediakan interface berbasis event (`EventEmitter`) yang memancarkan status: `taskSuccess`, `taskFailed`, `lagSpike`, dan `queueDrained`.

#### Constraints
- Runtime: Node.js v18.x atau v20.x LTS.
- **Strictly Zero External Dependencies** (Hanya boleh menggunakan Node.js Built-in Modules: `node:events`, `node:perf_hooks`, `node:async_hooks`, dll).
- Memory Safety: Harus mampu menampung antrean hingga 100.000 tasks tanpa memory leak atau unbounded array allocation crash.

#### Expected Output
1. Implementasi modular class `ResilientTaskScheduler` yang lengkap dan fungsional.
2. Skrip simulasi stres-test (*benchmark script*) yang mendemonstrasikan:
   - 1000 tasks acak dimasukkan ke scheduler (campuran antara I/O bound simulated delay dan CPU bound tasks).
   - Induksi Event Loop Lag sintetis (misal: operasi crypto atau kalkulasi array masif).
   - Scheduler terbukti memprioritaskan task `CRITICAL` dan menahan task `LOW` saat lag melonjak.
   - Task yang *stuck* berhasil di-abort via `AbortSignal`.
   - Log metrik real-time yang menampilkan: Active tasks, Queued tasks per priority, P99 Lag, Total completed.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk memvalidasi kesiapan pemahaman Anda sebelum melangkah ke Bab berikutnya.

### Saya harus memahami:
- [ ] Siklus hidup lengkap Event Loop pada Browser (Microtasks, Animation Frames, Render, Macrotasks).
- [ ] Struktur 6 fase Libuv Event Loop di Node.js (`Timers`, `Pending`, `Idle/Prepare`, `Poll`, `Check`, `Close`) dan operasi spesifik tiap fase.
- [ ] Perbedaan fundamental antara Macrotask Queue, Microtask Queue, dan NextTick Queue di Node.js.
- [ ] Mengapa `async/await` bersifat non-blocking secara eksternal namun berperilaku sinkron di dalam scope fungsinya sendiri (*continuation pass-through*).
- [ ] Cara kerja V8 Ignition interpreter dan TurboFan compiler dalam mengoptimasi asynchronous execution context.
- [ ] Batasan dari model konkruensi single-threaded dan kapan harus mengeskalasi ke multi-threading (`worker_threads`) atau multi-processing.
- [ ] Mekanisme deteksi Event Loop Lag / Delay menggunakan Node.js `perf_hooks` dan Browser Long Tasks API.

### Saya tidak perlu menghafal:
- [ ] Angka pasti alokasi byte struct Libuv (`uv_loop_t`, `uv_timer_t`) dalam kode sumber C Libuv.
- [ ] Algoritma internal V8 micro-optimization assembly untuk transisi frame stack promise.
- [ ] Seluruh tabel kode error POSIX non-blocking I/O (`EAGAIN`, `EWOULDBLOCK`, dll).

### Saya harus bisa melakukan:
- [ ] Melakukan profiling dan debugging bottleneck Event Loop menggunakan Chrome DevTools Performance Profiler atau Node.js Diagnostic tools (`--prof`, Clinic.js / 0x).
- [ ] Mengonversi kode sinkron blocking yang masif menjadi pola pemrosesan kooperatif non-blocking terfragmentasi (*task chunking*).
- [ ] Mencegah terjadinya unhandled promise rejections yang dapat merusak lifecycle state machine aplikasi.
- [ ] Menggunakan `AbortController` secara idiomatis untuk membatalkan operasi asynchronous berantai (fetch, timer, child process).
- [ ] Membangun mekanisme antrean konkruensi adaptif dengan backpressure control di layer aplikasi enterprise.