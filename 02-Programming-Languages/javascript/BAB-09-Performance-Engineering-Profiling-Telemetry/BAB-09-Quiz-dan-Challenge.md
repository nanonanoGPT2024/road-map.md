# BAB 09: Quiz, Challenge, & Knowledge Check
**Performance Engineering, Profiling & Telemetry**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Hidden Classes (Shapes) & Transition Trees pada V8 Engine
Jelaskan secara mendalam bagaimana V8 Engine merepresentasikan objek dinamis JavaScript di memori menggunakan konsep *Hidden Classes* (*Shapes/Maps*). Bagaimana mutasi properti yang dilakukan di luar urutan inisialisasi (*out-of-order assignment*) atau penambahan properti dinamis melalui manipulasi `delete` memicu divergensi *transition tree*, dan apa konsekuensi langsungnya terhadap deoptimasi memori (transisi ke *Dictionary Mode/Slow Mode*)?

### Soal 1.2: State Machine pada Inline Caching (IC)
Analisis siklus hidup dan transisi status pada *Inline Caching* (IC) untuk operasi akses properti objek: *Monomorphic*, *Polymorphic*, hingga *Megamorphic*. Mengapa status *Megamorphic* mematikan optimasi *inlining* oleh *TurboFan*, memaksa lookup jatuh kembali ke mekanisme *global IC stub*, dan bagaimana struktur kode aplikasi dapat secara tidak sengaja memicu status *Megamorphic* pada *hot path*?

### Soal 1.3: Generational Garbage Collection & Write Barriers
Arsitektur garbage collection V8 menerapkan *Generational Hypothesis*. Bedakan mekanisme kerja, trade-off latensi, dan algoritma yang digunakan antara **Young Generation (Minor GC / Scavenger - Cheney's Algorithm / Parallel Scavenge)** dan **Old Generation (Major GC / Full Mark-Sweep-Compact)**. Dalam konteks ini, jelaskan fungsi kritis dari *Write Barrier* dan *Remembered Sets* ketika objek di *Old Generation* mereferensikan objek baru di *Young Generation*.

### Soal 1.4: Disosiasi antara CPU Utilization dan Event Loop Delay
Mengapa pada runtime Node.js berbasis libuv, tingkat utilisasi CPU yang relatif rendah (misal: 20-30%) tidak menjamin ketiadaan degradasi latensi, dan justru bisa terjadi lonjakan ekstrem pada *Event Loop Delay/Lag*? Jelaskan skenario arsitektur di mana thread utama (*main thread execution*) mengalami *starvation* sementara CPU multi-core sistem tetap berstatus *idle*.

### Soal 1.5: Performance API: User Timing Level 3 vs Performance Hooks
Bandingkan arsitektur dan kapabilitas observabilitas antara Browser Performance APIs (meliputi `PerformanceObserver`, User Timing Level 3, Long Tasks API / Long Animation Frames API) dengan modul `node:perf_hooks` pada Node.js. Bagaimana kedua API tersebut menangani resolusi *monotonic clock* (`performance.now()`) dibandingkan `Date.now()`, dan mengapa *monotonic clock* wajib digunakan dalam pengukuran performa sub-milidetik?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik Memory Leak: Closure Retainers vs Detached DOM
Bandingkan jejak *memory retention* pada dua platform:
1. Browser: Masalah *Detached DOM Nodes* yang tertahan oleh referensi *event listener* pada *scoped context*.
2. Node.js: Masalah *Closure Memory Leaks* di mana sebuah fungsi asinkron berdurasi panjang mempertahankan referensi ke leksikal *scope* luar yang membungkus objek *buffer* besar.

Bagaimana cara mengisolasi *retaining path* dari kedua kasus tersebut menggunakan visualisasi *Dominator Tree* pada DevTools Heap Snapshot?

### Soal 2.2: Mekanisme Deoptimasi TurboFan & Analisis Profiling Flags
Sebutkan 3 pemicu utama terjadinya deoptimasi mendadak (*bailout to Ignition bytecode*) pada fungsi teroptimasi (*TurboFan optimized code*). Jika Anda menjalankan Node.js dengan flags `--trace-deopt`, `--trace-opt`, dan `--prof`, interpretasikan bagaimana *soft deopt* berbeda dari *hard deopt/eager deopt*, dan jelaskan bagaimana Anda memanfaatkan V8 tick processor (`--prof-process`) untuk mendeteksi *JIT thrashing*.

### Soal 2.3: Sampling Profiler Internals vs Instrumentation Profiler
CPU Profiler internal V8 beroperasi menggunakan paradigma *Statistical/Sampling Profiler* (berbasis interval interrupt timer OS), sedangkan beberapa tool tracing menggunakan *Instrumentation Profiler*. Analisis kelemahan mendasar dari *sampling bias* (seperti efek *Nyquist-Shannon sampling rate limit* terhadap fungsi eksekusi ultra-singkat) dan jelaskan mengapa *instrumentation profiling* memiliki *overhead* pengukuran (*probe overhead*) yang mendistorsi profil latensi produksi.

### Soal 2.4: Shallow Size vs Retained Size dalam Analisis Heap Snapshot
Pada proses investigasi *Out-Of-Memory* (OOM) via heap snapshot dump:
1. Definisikan secara matematis perbedaan antara *Shallow Size* dan *Retained Size*.
2. Jelaskan skenario di mana suatu objek memiliki *Shallow Size* sebesar 32 byte, namun memiliki *Retained Size* sebesar 500 MB.
3. Mengapa siklus referensi melingkar (*cyclic references*) tidak menyebabkan kebocoran memori pada algoritma penandaan *Mark-Sweep*, namun dapat mengecoh perhitungan hierarki kepemilikan memori pada alat analisis non-standar?

### Soal 2.5: Overhead Asynchronous Context Tracking (AsyncLocalStorage)
`node:async_hooks` dan `AsyncLocalStorage` adalah fondasi distribusi konteks telemetri (OpenTelemetry trace context) di JavaScript. Bedakan implementasi modern berbasis native V8 *context-promise-hook* dengan implementasi *legacy monkey-patching*. Apa akar penyebab degradasi performa (*micro-benchmark penalty* pada promise lifecycle) yang diakibatkan oleh tracking konteks asinkron pada aplikasi dengan throughput di atas 50.000 RPS?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: P99 Latency Degradation pada Core Payment Gateway API
* **Konteks:** Sebuah microservice Node.js menangani transaksi pembayaran dengan beban rata-rata 8.000 RPS. Telemetry APM menunjukkan P50 berada pada 12ms, namun P99.9 melonjak drastis hingga 2.400ms. Selama lonjakan ini:
  * Penggunaan CPU host stabil pada angka 40%.
  * Utilisasi memori flat tanpa indikasi OOM.
  * Metrik IO database dan network call eksternal mengembalikan respon stabil di bawah 15ms.
* **Gejala Tambahan:** Hasil monitoring event loop melaporkan metrik *Event Loop Delay* mengalami lonjakan sinkron dengan P99.9.
* **Pertanyaan Diagnostik:**
  1. Bagaimana langkah sistematis Anda untuk mengisolasi baris kode yang memblokir *main thread* tanpa menghentikan traffic produksi secara penuh?
  2. Dari perspektif komputasi, apa saja kandidat akar masalah di lapisan runtime (analisis kemungkinan *JSON schema validation*, kompleksitas algoritma parsing, ReDoS, atau manipulasi *crypto module*)?
  3. Bagaimana arsitektur *worker thread pool* atau proses *offloading* harus didesain untuk menangani beban CPU-bound tersebut agar tidak mendegradasi *event loop processing*?

### Skenario B: Backpressure Failure & Buffer Memory Explosion pada Streaming SSR
* **Konteks:** Sistem Frontend berbasis Node.js yang merender halaman secara Server-Side Streaming (menggunakan Web Streams / Node Streams) mengalami *crash* berkala akibat `JavaScript heap out of memory` saat lonjakan traffic kampanye promosi.
* **Gejala:**
  * Alokasi heap melonjak drastis hanya pada node yang melayani klien dengan koneksi jaringan seluler lambat (3G/high-latency).
  * Profil heap menunjukkan penumpukan objek tipe `Buffer`, `Uint8Array`, dan instansi `Socket`.
* **Pertanyaan Diagnostik:**
  1. Analisis bagaimana fenomena *Backpressure failure* terjadi antara stream parser SSR (producer) dan TCP socket client yang lambat (consumer).
  2. Identifikasi kesalahan umum pada pemanggilan event `data` vs penggunaan pipeline abstraksi (`stream.pipeline` atau `.pipe()`) yang menyebabkan V8 internal buffer menampung data tanpa batas di memory heap.
  3. Rancang strategi perbaikan menggunakan mekanisme *flow control* native untuk membatasi ukuran alokasi internal buffer (*highWaterMark*) dan mendemonstrasikan status *paused/resumed stream state*.

### Skenario C: Telemetry Overhead Crisis vs Observability Fidelity
* **Konteks:** Sebuah platform FinTech skala enterprise mengadopsi OpenTelemetry NodeSDK dengan instrumentasi otomatis penuh (*auto-instrumentation* untuk HTTP, Express, Redis, PostgreSQL, dan Winston). Setelah peluncuran ke produksi:
  * Throughput sistem turun sebesar 22%.
  * Latensi rata-rata meningkat 35%.
  * Volume data traces yang dikirim ke Jaeger/Collector mencapai 4 TB/hari, membebani bandwidth jaringan VPC dan storage collector.
* **Pertanyaan Diagnostik:**
  1. Lakukan audit teknis terhadap mekanisme *Head-based sampling* vs *Tail-based sampling*. Sampling model mana yang harus diterapkan dan di layer infrastruktur mana implementasi tersebut diletakkan?
  2. Bagaimana cara mengonfigurasi `BatchSpanProcessor` dan *export interval* untuk memitigasi I/O serialization blocking pada event loop Node.js?
  3. Lakukan analisis *trade-off* implementasi telemetri: Kapan Anda merekomendasikan instrumentasi berbasis *in-process application tracing* (OTel SDK) versus observabilitas berbasis *off-process zero-overhead* seperti *eBPF* (Extended Berkeley Packet Filter)?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance In-Process APM & Telemetry Agent
Bangun sebuah sub-sistem telemetri internal (*zero-external-dependency*, kecuali antarmuka opsional untuk exporter) berbasis Node.js native API yang bertugas memantau kesehatan runtime secara presisi tinggi dengan overhead eksekusi CPU kurang dari 1.5%.

#### Problem Statement
Sebagian besar APM pihak ketiga berbasis NPM library membawa overhead alokasi memori yang tinggi akibat object allocation pada setiap sampling tick. Anda ditugaskan merekayasa engine profiler mikro internal yang mampu mendeteksi *Event Loop Delay*, mengklasifikasikan *Garbage Collection Pauses*, dan melacak degradasi *hot path* pemanggilan fungsi secara real-time.

#### Requirements
1. **Histogram Event Loop Delay:**
   * Gunakan `node:perf_hooks` (`monitorEventLoopDelay`) dengan resolusi sub-milidetik.
   * Ambil kalkulasi matematis untuk P50, P90, P99, dan Max delay secara periodik.
2. **GC Pause Tracker:**
   * Buat `PerformanceObserver` yang mendengarkan event tipe `gc`.
   * Klasifikasikan durasi jeda berdasarkan tipe garbage collection:
     * `kGCTypeScavenge` (Minor GC)
     * `kGCTypeMarkSweepCompact` (Major GC)
     * `kGCTypeIncrementalMarking`
     * `kGCTypeProcessWeakCallbacks`
   * Catat total *pause time* (dalam nanodetik) dan total memori yang berhasil di-reclaim.
3. **Hot-Path Micro-Profiler:**
   * Implementasikan wrapper fungsi berbasis *high-resolution monotonic timer* (`process.hrtime.bigint()`) tanpa menyebabkan alokasi heap baru (*zero-allocation wrapper*) pada critical-path pemanggilan fungsi.
   * Implementasikan deteksi ambang batas latensi (*execution threshold alert*). Jika eksekusi melewati batas $N$ ms, emit event ke telemetry stream.
4. **Data Export Serialization:**
   * Sediakan fungsi dumping metrik berkala ke format JSON yang dioptimalkan (menggunakan *pre-allocated buffer* atau manipulasi string deterministik) untuk menghindari degradasi V8 heap.

#### Constraints
* **Overhead Limit:** CPU utilization total dari agent tidak boleh melebihi 1.5% pada kondisi throughput aplikasi host 15.000 RPS.
* **Runtime:** Node.js LTS (v20+), strict JavaScript ESM murni (tanpa transpilasi Babel/Webpack, tanpa pustaka eksternal pihak ketiga dari NPM).
* **Memory Safety:** Tidak boleh menimbulkan *memory leak* dari closure capture atau uncollected metric events di memori internal. Wajib mengimplementasikan buffer cincin (*ring buffer*) statis dengan kapasitas terbatas.

#### Expected Output
1. Script mandiri `telemetry-agent.js` yang mengekspos API kelas `RuntimeTelemetry`.
2. Script simulasi beban `load-stress.js` yang mendemonstrasikan aplikasi yang mengalami CPU-bound spike dan Memory-bound leak.
3. Cetakan report metrik telemetri ke `stdout` setiap 5 detik dengan struktur tabular/JSON terkompresi yang menampilkan:
   * Event Loop percentiles (P50, P90, P99, Max dalam ms).
   * GC Pause duration distribution & count per GC Type.
   * Active Memory Footprint: Heap Used, Heap Total, External, RSS, ArrayBuffers.
   * Rekaman peringatan jika terjadi eksekusi yang melanggar threshold SLA lokal.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Representasi memori V8 terhadap objek (Hidden Classes, Shapes, Maps, Descriptor Arrays, Transition Arrays).
- [ ] Mekanisme JIT compilation V8: Peran Ignition (interpreter), Sparkplug (non-optimizing compiler), Maglev (mid-tier compiler), dan TurboFan (optimizing compiler).
- [ ] Struktur Inline Caching (Monomorphic, Polymorphic, Megamorphic) dan dampaknya terhadap assembly code generation.
- [ ] Fase-fase Garbage Collection V8 (Scavenge, Concurrent Marking, Sweeping, Compacting) dan implementasi Write Barriers.
- [ ] Perbedaan fundamental antara Event Loop Delay/Lag, System CPU Utilization, dan Threadpool Saturation pada arsitektur libuv.
- [ ] Konsep Memory Leaks di JS: Retaining Trees, Dominator Nodes, Distance from GC Root, serta Shallow vs Retained Size.
- [ ] Perbedaan arsitektural metrik RED (Rate, Errors, Duration) dan USE (Utilization, Saturation, Errors) dalam konteks runtime telemetry.
- [ ] Standar spesifikasi OpenTelemetry: Tracing context propagation, Spans, Baggage, serta perbedaan sampling strategies (Head vs Tail-based).

### Saya tidak perlu menghafal:
- [ ] Nilai integer pasti dari internal V8 C++ enum constants (misal: kode bitwise flag eksak untuk tipe GC di C++ layer).
- [ ] Detail instruksi assembly x86/ARM yang dihasilkan oleh TurboFan backend untuk platform spesifik.
- [ ] Seluruh nama method pada antarmuka Chrome DevTools Protocol (CDP) secara verbatim di luar API public standar.
- [ ] Kode implementasi internal algoritma Cheney pada Scavenger V8 versi lama secara baris per baris.

### Saya harus bisa melakukan:
- [ ] Melakukan heap profiling via Chrome DevTools / Node.js Inspector, mengambil heap snapshots, membandingkan snapshots (*comparison view*), dan melacak *allocation retention path* untuk membasmi memory leak.
- [ ] Menggunakan CLI flags Node.js/V8 (`--prof`, `--trace-gc`, `--trace-deopt`, `--trace-ic`, `--max-old-space-size`) untuk menganalisis performa runtime secara empiris.
- [ ] Membaca dan menginterpretasikan hasil CPU Flame Graph / Flame Chart dari instrumen profiling untuk mengidentifikasi bottleneck dan deoptimasi fungsi (*JIT bailout*).
- [ ] Mengimplementasikan `node:perf_hooks` (`PerformanceObserver`, `monitorEventLoopDelay`) secara efisien untuk monitoring internal aplikasi berorientasi produksi.
- [ ] Menganalisis dan menstabilkan performa Web Vitals (LCP, INP, CLS) serta Long Animation Frames (LoAF) pada sisi browser client menggunakan standar Web Performance APIs.
- [ ] Mengkonfigurasi OpenTelemetry Node.js SDK secara optimal tanpa membebani event loop dan mendegradasi throughput produksi mikroservis.