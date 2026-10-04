# BAB 06: Quiz, Challenge, & Knowledge Check
**Concurrency Models, Web Workers & Parallel Computing**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Asynchronous Event Loop vs. True Preemptive Parallelism
Jelaskan perbedaan fundamental antara model konkurensi berbasis *Single-Threaded Non-Blocking Event Loop* (Call Stack, Task Queue, Microtask Queue) dengan *True Parallelism* berbasis OS Threads yang dieksekusi melalui Web Workers. Mengapa `Promise.all()` yang mengeksekusi 10 fungsi komputasi intensif (CPU-bound) tetap menyebabkan *frame drop* (UI jank) pada *main thread*, sedangkan Web Workers tidak?

### Soal 1.2: Boundary Isolasi Memori & Komunikasi Antar-Isolate
Dalam arsitektur engine V8/JavaScript runtimes, Web Worker berjalan di dalam *Isolate* independen. Jelaskan bagaimana batasan isolasi memori (*shared-nothing architecture*) ini ditegakkan! Mengapa sebuah objek JavaScript reguler yang diinstansiasi di *main thread* tidak dapat dimutasi secara langsung oleh Web Worker melalui referensi memori yang sama?

### Soal 1.3: Structured Clone Algorithm vs. Transferable Objects
Bandingkan mekanisme transmisi data antara *main thread* dan worker menggunakan **Structured Clone Algorithm** versus **Transferable Objects** (misalnya `ArrayBuffer` atau `ImageBitmap`). Analisis perbedaan keduanya dari aspek:
1. Alokasi dan penyalinan memori (*deep copy* vs. *pointer transfer*).
2. Dampak terhadap pemanggilan Garbage Collector (GC) pada payload berukuran ratusan megabyte.
3. Status objek sumber pada konteks pengirim sesaat setelah `postMessage()` dieksekusi.

### Soal 1.4: Batasan Kontekstual Web Worker Execution Environment
Sebutkan dan jelaskan rasional arsitektural mengapa Web Worker **tidak** memiliki akses ke objek `window`, `document` (DOM), dan sebagian API Web Storage seperti `localStorage`. API apa saja yang tetap diizinkan berjalan di dalam konteks `DedicatedWorkerGlobalScope` untuk mendukung operasi I/O dan komputasi?

### Soal 1.5: Taksonomi Spesialisasi Worker
Jelaskan perbedaan siklus hidup (*lifecycle*), konteks kepemilikan (*ownership*), dan use case arsitektural antara:
1. **Dedicated Web Worker**
2. **Shared Worker**
3. **Service Worker**
Mengapa Service Worker tidak dirancang untuk menangani komputasi paralel CPU-bound jangka panjang berkecepatan tinggi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Memory Model, SharedArrayBuffer, dan Cross-Origin Isolation
Sebelum `SharedArrayBuffer` dapat digunakan di browser modern, mengapa sistem harus menerapkan header HTTP `Cross-Origin-Opener-Policy (COOP): same-origin` dan `Cross-Origin-Embedder-Policy (COEP): require-corp`? Kaitkan jawaban Anda dengan mitigasi kerentanan *hardware speculative execution* (seperti Spectre) dan implikasi keamanannya terhadap *high-resolution timers*.

### Soal 2.2: Atomics dan Race Condition Prevention
Diberikan skenario di mana 4 Web Worker secara simultan mengeksekusi operasi penambahan nilai pada satu indeks `Int32Array` yang dialokasikan di dalam `SharedArrayBuffer`:
```javascript
// Worker execution code
sharedInt32Array[0] = sharedInt32Array[0] + 1;
```
1. Jelaskan secara teknis pada level instruksi mesin (*read-modify-write*) mengapa kode di atas memicu *race condition* dan data corruption.
2. Bagaimana instruksi `Atomics.add()` atau `Atomics.compareExchange()` mengeliminasi fenomena tersebut? Jelaskan konsep *memory barriers/fences* dan *sequential consistency* yang terjadi.

### Soal 2.3: Mekanisme Blocking via Atomics.wait() dan Atomics.notify()
Mengapa pemanggilan `Atomics.wait()` secara tegas dilarang (*throws runtime TypeError*) pada *Main Thread* browser, tetapi diizinkan di dalam Web Worker? Jelaskan bagaimana integrasi antara *operating system thread sleeping/parking* bekerja saat `Atomics.wait()` dieksekusi dan bagaimana engine mereaktivasi thread tersebut melalui `Atomics.notify()`.

### Soal 2.4: Bottleneck Serialisasi pada Message Passing Skala Tinggi
Sebuah aplikasi streaming finansial mengirimkan 10.000 pesan per detik dari worker analitik ke main thread menggunakan `postMessage` dengan format plain JSON object. Main thread mengalami degradasi performa drastis meskipun tidak ada kalkulasi berat yang berjalan di sana. 
1. Bedah *bottleneck* internal V8 serialization/deserialization cycle yang terjadi di balik `postMessage`.
2. Berikan solusi arsitektural konkret untuk mereduksi latensi dan CPU overhead tersebut tanpa mengurangi volume transmisi metrik.

### Soal 2.5: Deteksi dan Investigasi Memory Leak pada Worker Threading
Bagaimana siklus hidup Worker dibersihkan dari memori? Jelaskan dua skenario di mana memory leak fatal dapat terjadi pada arsitektur Web Worker:
1. Kegagalan dereferensi pada Worker instance di *main thread*.
2. Penggunaan event listener internal yang tidak di-`terminate()` saat worker diinstansiasi secara dinamis dalam frekuensi tinggi. 
Bagaimana cara melakukan profiling memori worker secara terisolasi via Chrome DevTools / Performance & Memory Profiler?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Pemrosesan Citra 4K Real-Time (UI Frame Drop)
*Konteks Sistem:* Sebuah platform pengeditan video berbasis web memproses filter manipulasi piksel (konvolusi matriks, saturasi, Sobel edge detection) pada video stream beresolusi 4K (3840x2160 piksel, 60 FPS). Saat filter diaktifkan, rendering pipeline UI anjlok dari 60 FPS ke 7 FPS. Pengguna tidak dapat menekan tombol stop atau memindahkan *timeline slider* (antarmuka macet total).

Kode saat ini mengeksekusi komputasi citra di dalam event loop utama menggunakan `requestAnimationFrame`:
```javascript
function processFrame() {
  const frame = ctx.getImageData(0, 0, width, height);
  applyHeavyMatrixFilter(frame.data); // Operasi CPU-bound masif: O(W * H * K^2)
  ctx.putImageData(frame, 0, 0);
  requestAnimationFrame(processFrame);
}
```

**Pertanyaan Diagnostik & Solusi:**
1. Mengapa alur pemrosesan ini melumpuhkan Compositor Thread dan Main Thread browser?
2. Rancang arsitektur paralelisasi baru menggunakan **Worker Pool**, **OffscreenCanvas**, dan **Transferable Objects**. Gambarkan diagram alur transfer data zero-copy dari pemotretan video hingga rendering akhir ke layer canvas tanpa membebani Main Thread sama sekali.

---

### Skenario B: Race Condition dan Deadlock pada High-Frequency In-Memory Cache
*Konteks Sistem:* Arsitektur trading frekuensi tinggi (HFT) web-client mengeksekusi perhitungan arbitrase lintas bursa menggunakan 8 Dedicated Web Workers. Semua worker berbagi status order book yang sama melalui `SharedArrayBuffer` tunggal berukuran 64MB yang dibungkus oleh representasi `DataView`. 

Untuk mencegah inkonsistensi saat pembaruan data, tim engineer mengimplementasikan Spinlock manual:
```javascript
// Implementasi Kustom Mutex oleh Engineer
function acquireLock(int32View, lockIndex) {
  while (Atomics.compareExchange(int32View, lockIndex, 0, 1) !== 0) {
    // Spin-wait (busy-waiting loop)
  }
}

function releaseLock(int32View, lockIndex) {
  Atomics.store(int32View, lockIndex, 0);
}
```
*Insiden:* Di lingkungan produksi multi-core (Intel i9/Apple Silicon), browser secara berkala mengalami *tab crash* atau freeze total pada seluruh worker pool. Log metrik menunjukkan bahwa CPU penggunaan mencapai 100% pada semua thread, namun tidak ada order baru yang diproses (*Deadlock / Livelock*).

**Pertanyaan Diagnostik & Solusi:**
1. Analisis kelemahan fatal dari implementasi Spinlock di atas. Mengapa *busy-waiting* menggunakan `while` loop murni tanpa back-off atau sleep primitives merusak thread scheduler sistem operasi pada Web Worker?
2. Tuliskan ulang primitif sinkronisasi ini menggunakan `Atomics.wait()` dan `Atomics.notify()` untuk membangun Mutex non-blocking terhadap OS CPU scheduling. Bagaimana Anda mencegah potensi *priority inversion* dan *deadlock* saat worker tiba-tiba melempar unhandled exception sebelum `releaseLock` dipanggil?

---

### Skenario C: Trade-off Arsitektur Background Language Server Protocol (LSP) Client
*Konteks Sistem:* Anda adalah Technical Lead yang merancang Web-based IDE (serupa VS Code for Web). Editor harus mengindeks basis kode JavaScript/TypeScript berukuran jutaan baris kode secara lokal di browser, menjalankan parsing Abstract Syntax Tree (AST), autocompletion, dan linting secara terus-menerus.

Terdapat empat opsi arsitektur konkurensi:
- **Opsi 1:** Monolithic Web Worker (Semua komputasi dan parsing digabung dalam 1 Dedicated Worker).
- **Opsi 2:** Task-based Dynamic Ephemeral Workers (Membuat worker baru via `new Worker()` untuk setiap file parsing, lalu langsung memanggil `worker.terminate()`).
- **Opsi 3:** Static Sized Worker Thread Pool (Membatasi pool worker sesuai `navigator.hardwareConcurrency` dengan Work-Stealing Queue pattern).
- **Opsi 4:** Shared Worker terdistribusi yang membagi status komputasi antartab browser yang membuka repositori yang sama.

**Pertanyaan Diagnostik & Solusi:**
1. Bedah kelemahan kritis dari Opsi 1 dan Opsi 2 dalam konteks konsumsi memori, thread creation overhead, dan responsivitas interaksi parsing file berukuran besar.
2. Buat matriks evaluasi perbandingan antara **Opsi 3** dan **Opsi 4** berdasarkan metrik: *Memory Footprint*, *Inter-Tab State Synchronization*, *Cold-start Latency*, dan *Fault Isolation*.
3. Arsitektur mana yang Anda rekomendasikan sebagai arsitektur final kelas enterprise? Justifikasi keputusan Anda dengan pertimbangan keterbatasan arsitektur browser sandbox.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Parallel Ray Tracing Engine dengan Dynamic Work-Stealing Pool, SharedArrayBuffer, dan Fallback Pipeline

#### Deskripsi Masalah
Komputasi grafik ray-tracing membutuhkan kalkulasi matematis intensif pada level individu piksel (perhitungan vektor pantulan cahaya, interseksi bola/geometri, shading). Jika dilakukan secara sekuensial pada CPU single-thread, render frame resolusi 1920x1080 dapat memakan waktu puluhan detik. 

Anda diminta membangun **High-Throughput Parallel Ray Tracing Engine** modular yang memanfaatkan seluruh thread CPU klien secara optimal tanpa mengorbankan fluiditas UI main-thread (UI tetap responsif di 60 FPS selama render berjalan).

#### Requirements
1. **Worker Pool Manager:**
   - Deteksi jumlah core logis mesin menggunakan `navigator.hardwareConcurrency`. Alokasikan `N - 1` workers (menyisakan minimal 1 thread untuk Main Thread/Compositor).
   - Implementasikan mekanisme pembagian beban kerja berbasis **Tiling / Spatial Chunking** (gambar dipecah menjadi blok-blok kecil, misal 32x32 piksel).
   - Jalankan antrean kerja menggunakan pola **Work-Stealing / Job Queue dynamic allocation** (bukan pembagian statis), sehingga core yang selesai lebih cepat langsung mengambil chunk berikutnya dari antrean global.

2. **Memori dan Sinkronisasi:**
   - Buat satu alokasi `SharedArrayBuffer` terpusat yang memetakan buffer RGBA kanvas (`Uint8ClampedArray` atau `Uint32Array`).
   - Semua worker menulis hasil kalkulasi piksel langsung ke dalam `SharedArrayBuffer` pada segmen memori miliknya secara aman (bebas race condition tanpa saling menimpa).
   - Gunakan `Atomics` untuk mengelola *counter* progres global (*atomic index increment*) yang menentukan koordinat tile berikutnya yang harus diambil oleh worker.

3. **Rendering & Compositing Pipeline:**
   - Gunakan `OffscreenCanvas` yang dihubungkan ke canvas DOM utama menggunakan `transferControlToOffscreen()` jika didukung. Render buffer hasil akhir langsung ke context GPU di dalam Dedicated Display Worker terpisah, atau transfer via `ImageBitmap` zero-copy.

4. **Security & Fallback Resilience:**
   - Sistem harus mendeteksi ketersediaan `crossOriginIsolated` di runtime.
   - Jika lingkungan mengisolasi SAB (Header COOP/COEP aktif), gunakan pipeline **SharedArrayBuffer + Atomics**.
   - Jika lingkungan *non-isolated* (SAB dilarang oleh browser), sistem harus secara transparan beralih (*graceful fallback*) ke pipeline **Transferable ArrayBuffer chunking** via `postMessage` konvensional tanpa mengubah logika utama algoritma ray tracer.

#### Constraints
- **Main Thread Budget:** Selama proses rendering berlangsung, frame-rate Main Thread tidak boleh turun di bawah 55 FPS (uji menggunakan Continuous Performance Profiler).
- **Memory Footprint:** Tidak boleh terjadi instansiasi objek berulang (*zero allocation in hot render loop*) untuk meminimalisasi overhead Garbage Collector (GC thrashing).
- **Terminasi & Abort:** Wajib mengimplementasikan mekanisme pembatalan rendering instan (*hard cancel/abort signal*). Ketika pengguna menekan tombol "Cancel", seluruh worker harus seketika berhenti memproses chunk saat ini dan pool siap menerima job baru dalam < 100ms.

#### Expected Output
1. File `RayTracerPool.ts` (atau `.js` modular): Mengontrol *Worker lifecycle*, *job queue*, sinkronisasi `Atomics`, resolusi fallback, dan komunikasi main thread.
2. File `raytracer.worker.ts`: Worker implementation yang mengeksekusi perhitungan matematika per blok tile dan menulis ke Shared Memory / mentransfer buffer chunk.
3. Live Benchmarking Harness: Menampilkan perbandingan performa:
   - Waktu eksekusi: Single Thread vs. Multi-Worker Transferable vs. Multi-Worker SharedArrayBuffer.
   - FPS Counter main-thread real-time selama render berjalan.
   - Visualisasi real-time rendering tile yang menunjukkan worker mana yang sedang memproses blok tertentu.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi konkurensi V8/browser: Perbedaan antara Main Thread, Compositor Thread, Service/Web Worker Thread, dan OS System Threads.
- [ ] Batasan Structured Clone Algorithm (tipe data yang didukung vs. tipe data terlarang seperti Function, DOM Node, Symbol).
- [ ] Mekanisme kerja Transferable Objects dan pemindahan kepemilikan byte buffer (`ArrayBuffer.prototype.byteLength` menjadi 0 pada konteks pengirim).
- [ ] Arsitektur SharedArrayBuffer dan keterkaitannya dengan *Cross-Origin Isolation requirements* (COOP dan COEP).
- [ ] Operasi primitif `Atomics`: `load`, `store`, `add`, `sub`, `and`, `or`, `xor`, `exchange`, `compareExchange`, `isLockFree`.
- [ ] Mekanisme koordinasi thread: `Atomics.wait()`, `Atomics.notify()`, dan batasan thread blocking pada browser environment.
- [ ] Peran dan pemanfaatan `OffscreenCanvas` untuk melepaskan beban rendering grafis 2D/WebGL dari UI thread.
- [ ] Perbedaan model konkurensi Web Workers di Browser dengan `worker_threads` di Node.js (misal: perbedaan akses event-loop, API transfer, dan shared memory).

### Saya tidak perlu menghafal:
- [ ] Daftar lengkap ribuan property dan method Web API yang didukung atau tidak didukung di dalam `WorkerGlobalScope` (cukup rujuk dokumentasi MDN bila memerlukan API spesifik).
- [ ] Nilai bitwise spesifik dari header flag HTTP COOP/COEP (cukup gunakan konfigurasi reverse proxy standar `same-origin` dan `require-corp`).
- [ ] Nilai byte-offset spesifik dari arsitektur CPU tertentu (misalnya Little-Endian vs Big-Endian pada manipulasi `TypedArray`, kecuali saat parsing binary stream tingkat rendah).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi development server dan deployment pipeline untuk menyuntikkan header COOP/COEP agar `SharedArrayBuffer` dapat aktif secara legal di browser modern.
- [ ] Merancang dan mengimplementasikan Worker Thread Pool yang scalable dengan dynamic load-balancing (work-stealing).
- [ ] Melakukan debugging dan profiling multi-threaded JavaScript menggunakan Chrome DevTools (Sources worker tabs, Memory allocations, and Thread traces).
- [ ] Menulis algoritma bebas race-condition (*thread-safe*) menggunakan kombinasi `SharedArrayBuffer` dan `Atomics`.
- [ ] Memisahkan kalkulasi CPU-bound dari sebuah aplikasi web monolitik ke dalam Web Worker tanpa merusak User Experience dan arsitektur kode eksisting.
- [ ] Menangani siklus hidup error pada worker menggunakan event listener `onerror` dan `onmessageerror` secara komprehensif.