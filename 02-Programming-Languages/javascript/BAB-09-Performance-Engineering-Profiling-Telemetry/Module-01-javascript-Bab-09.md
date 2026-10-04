# SEKSI 01 — IDENTITAS MODUL

| Parameter | Spesifikasi |
| :--- | :--- |
| **Kategori** | 02-Programming-Languages |
| **Kurikulum** | JavaScript |
| **Bab** | 09 — Runtime Internals, Systems & Production Engineering |
| **Modul** | 01 — Performance Engineering, Profiling & Telemetry |
| **Kode Modul** | JS-ENG-0901 |
| **Tingkat Kesulitan** | Advanced / Principal Engineer |
| **Prasyarat** | JavaScript Asynchronous Internals (Event Loop, Microtasks), Memory Model Basics, Node.js Core Architecture, Unix OS Fundamentals (Signals, Memory Paging) |
| **Estimasi Waktu** | 12 - 16 Jam Pembelajaran Mendalam |
| **Stack / Tools** | Node.js Runtime (v20+ LTS), V8 Engine, `perf_hooks`, `node:inspector`, Clinic.js Suite, OpenTelemetry JS SDK, Linux `perf` |

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan memiliki kapabilitas teknis tingkat lanjut untuk:

1. **Menganalisis Mekanisme Internal V8 Execution Pipeline**: Mengidentifikasi transisi representasi objek (Hidden Classes/Shapes), status optimasi Inline Caching (Monomorphic, Polymorphic, Megamorphic), dan faktor pemicu Deoptimization pada compiler JIT (Ignition & TurboFan).
2. **Membedah Siklus Hidup Alokasi Memori & Garbage Collection**: Mengukur throughput dan durasi jeda (*pause times*) pada generasi Scavenge (Young Generation) serta Mark-Sweep-Compact (Old Generation) menggunakan trace internal V8.
3. **Mengoperasikan Profiling Sistem Tingkat Rendah**: Melakukan CPU Sampling Profiling dan Heap Allocation Tracking secara programmatic via `node:inspector` dan `v8` core module, serta mengekstraksi Flame Graphs untuk isolasi bottleneck.
4. **Mengukur Latensi Event Loop Secara Presisi**: Mengimplementasikan pelacakan *Event Loop Delay* (ELD) dan *Event Loop Utilization* (ELU) via API `perf_hooks` untuk mendeteksi degradasi performa di level p99 dan p99.9.
5. **Membangun Pipeline Telemetri Standar Industri**: Mengintegrasikan OpenTelemetry Tracing dan Metrics secara manual dan otomatis tanpa menimbulkan overhead komputasi berlebih (*telemetry-induced degradation*).
6. **Mendeteksi dan Memitigasi Edge-Case Performa Kritis**: Mengeliminasi kebocoran memori berbasis *closure retainers*, buffer fragmentation, dan starvation microtask pada arsitektur berkonkurensi tinggi.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Mechanical Sympathy pada JavaScript Runtime

Performa tinggi dalam JavaScript tidak dicapai dengan menulis *code micro-tricks* yang spekulatif, melainkan melalui pemahaman menyeluruh terhadap batasan dan perilaku runtime underlying engine (V8) dan sistem operasi (*Mechanical Sympathy*). JavaScript adalah bahasa bertipe dinamis yang diabstraksikan jauh dari hardware, namun pada akhirnya dieksekusi di atas CPU register, cache line (L1/L2/L3), dan memori virtual.

```
+-----------------------------------------------------------------------+
|                           KODE JAVASCRIPT                             |
|       Objek dinamis, closures, asynchronous promises, event loop      |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|                          V8 RUNTIME ENGINE                            |
| Shapes (Hidden Classes) | Inline Caches | Garbage Collector (Orinoco) |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|                    SYSTEM INTERFACES (OS & HARDWARE)                  |
| CPU L1/L2/L3 Caches | Branch Predictor | Page Tables | Kernel Context |
+-----------------------------------------------------------------------+
```

### Telemetry vs. Monitoring

Mental model performa modern membedakan **Monitoring** (apa yang sedang rusak, berbasis agregasi metrik makro) dengan **Telemetry/Observability** (mengapa sistem beroperasi dengan profil latensi tertentu melalui korelasi Traces, Metrics, dan Logs internal). 

* Insinyur performa tidak mengandalkan rata-rata (*arithmetic mean*). Rata-rata menyembunyikan realitas sistem terdistribusi.
* Fokus analisis adalah distribusi percentiles ($p95, p99, p99.9$) dan *tail latency amplification*.
* Pengukuran performa harus bersifat non-invasif: instrumen pengamatan (*probe*) tidak boleh mengubah profil eksekusi kode secara signifikan (*observer effect*).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. V8 JIT Compilation & Deoptimization Pipeline

```
                     JavaScript Source Code
                               |
                               v
                     [ Parser / AST ]
                               |
                               v
                 [ Ignition Bytecode Compiler ]
                               |
            +------------------+------------------+
            |                                     |
            v                                     |
    [ Bytecode Execution ]                        | Feedback Vector
            |                                     | (Type Feedback, ICs)
            | <== Profiler Spies (Warm/Hot) <====+
            v
     [ TurboFan Optimizer ]
            |
            | ---> [ Optimized Machine Code (Assembly) ]
            |                      |
            |                      v
            |             { Runtime Execution }
            |                      |
   (Type Check Fails /             |
    Shape De-shapes)               |
            |                      v
            +--- Deoptimization <- Deopt Bailout
```

### 2. V8 Heap Generational Architecture (Orinoco GC)

```
+----------------------------------------------------------------------------+
|                                V8 ENGINE HEAP                              |
+----------------------------------------------------------------------------+
|                     YOUNG GENERATION (1MB - 64MB)                          |
|  +--------------------+---------------------+----------------------------+ |
|  |    Eden Space      |  Survivor (From)    |     Survivor (To)          | |
|  |  [New Allocs...]   |  [Surviving Obj]    |    [Evacuation Target]     | |
|  +--------------------+---------------------+----------------------------+ |
|            |                                              |                |
|            +--- Scavenge GC (Parallel Minor GC) ----------+                |
|                                |                                           |
|                                v (Promoted after 2 rounds)                 |
+----------------------------------------------------------------------------+
|                     OLD GENERATION (Hingga gigabytes)                      |
|  +-----------------------------------------------------------------------+ |
|  | Old Pointer Space: Objek berumur panjang dengan pointer internal     | |
|  +-----------------------------------------------------------------------+ |
|  | Old Data Space: Raw payload (string, boxed numbers, raw data)         | |
|  +-----------------------------------------------------------------------+ |
|  | Large Object Space: Alokasi melebihi batas page (~256KB-1MB+)         | |
|  +-----------------------------------------------------------------------+ |
|  | Map/Cell Space: Metadata Hidden Classes (Shapes) & Compiler feedback   | |
|  +-----------------------------------------------------------------------+ |
|                                                                            |
|        Major GC (Mark-Sweep-Compact / Concurrent & Incremental)            |
+----------------------------------------------------------------------------+
```

### 3. Distributed Telemetry Pipeline (OTel Engine)

```
 +--------------------------------------------------------------------------+
 | Node.js Process Context                                                  |
 |                                                                          |
 |  [ Async Hook Scope Manager ]                                            |
 |         |                                                                |
 |         +---> [ Active Span Context: TraceID, SpanID, Flags ]             |
 |                                                                          |
 |  [ Core Event Loop ]                                                     |
 |         |                                                                |
 |         +---> [ perf_hooks: ELD/ELU Metrics Histogram ]                  |
 |                                                                          |
 |  [ User Application Code ]                                               |
 |         |                                                                |
 |         +---> [ Tracer.startSpan() ] ---> Record CPU / Latency           |
 +--------------------------------------------------------------------------+
                                      |
                           BatchSpanProcessor (Async)
                                      |
                                      v
 +--------------------------------------------------------------------------+
 | OpenTelemetry Collector / OTLP gRPC or HTTP Engine                       |
 |  [ Receiver ] ---> [ Batch/Memory Limiter Processor ] ---> [ Exporters ] |
 +--------------------------------------------------------------------------+
                                                               |
                                   +---------------------------+------------+
                                   |                                        |
                                   v                                        v
                            [ Jaeger / Tempo ]                     [ Prometheus / Mimir ]
                             (Trace Waterfall)                       (Metrics Series)
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Hidden Classes (Shapes) & Transition Trees
JavaScript tidak memiliki deklarasi struktur kelas statis di level C++. V8 merekayasa struktur internal bernama **Map** (atau **Shape**). Setiap instance objek dialokasikan dengan sebuah pointer ke Map tersebut.
* Ketika properti baru ditambahkan ke sebuah objek literal, runtime tidak memodifikasi objek secara terisolasi, melainkan melakukan navigasi sepanjang rantai transisi (*Transition Tree*).
* Dua objek yang memiliki key yang sama, tetapi diinisialisasi dalam urutan yang berbeda (`{ a: 1, b: 2 }` vs `{ b: 2, a: 1 }`), menghasilkan referensi **Map yang berbeda**.
* Struktur Map merekam *offset* memori dari properti tersebut, baik *in-object properties* (properti yang dialokasikan langsung di samping header objek) maupun *out-of-object properties* (dialokasikan di backing store eksternal ketika kapasitas *in-object* habis).

### 2. Inline Caching (IC) Mechanics
Inline Cache adalah mekanisme optimasi akses properti paling signifikan pada V8. Saat kode mengakses `obj.x`, V8 mengompilasi titik pemanggilan tersebut dengan struktur IC.
* **Monomorphic IC**: Titik pemanggilan hanya pernah menerima satu jenis Map. V8 menghasilkan instruksi mesin langsung: verifikasi pointer Map target dengan 1 instruksi perbandingan, lalu baca langsung dari offset memori yang tercatat. Kompleksitas: $O(1)$ native assembly dereference.
* **Polymorphic IC**: Titik pemanggilan menerima antara 2 hingga 4 variasi Map berbeda. V8 menggunakan struktur tabel pencarian linier pendek (*decision tree*). Kompleksitas: branch testing overhead.
* **Megamorphic IC**: Titik pemanggilan menerima lebih dari 4 variasi Map. TurboFan menyerah untuk melakukan inline assertion. Operasi dialihkan ke pencarian hash table global (*Megamorphic Stub Cache*), memicu degradasi performa drastis dan menghentikan inlining pemanggilan fungsi.

### 3. Event Loop Metrics: ELD vs. ELU
* **Event Loop Delay (ELD)**: Waktu delta antara penjadwalan timer nol-detik atau asynchronous check phase dengan waktu eksekusi aktualnya di runtime:
  $$\Delta t = t_{\text{actual}} - t_{\text{scheduled}}$$
  Kenaikan ELD mengindikasikan adanya synchronous task yang menduduki thread terlalu lama.
* **Event Loop Utilization (ELU)**: Rasio waktu yang dihabiskan oleh thread libuv untuk benar-benar mengeksekusi instruksi CPU JavaScript/Internal versus waktu pasif di mana thread tertidur menunggu *I/O polling* (via epoll/kqueue/IOCP):
  $$\text{ELU} = \frac{t_{\text{active}}}{t_{\text{active}} + t_{\text{idle}}}$$
  ELU memberikan indikasi saturasi thread yang jauh lebih stabil daripada metrik CPU OS karena terisolasi dari noise core CPU eksternal.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Orinoco Garbage Collection Sub-systems

Garbage collector V8 modern (*Orinoco*) beroperasi menggunakan prinsip *Generational Hypothesis*: mayoritas objek mati sesaat setelah dialokasikan.

```
Total Heap Memory
├── Young Generation (Minor GC - Scavenger)
│   ├── Nursery: Tempat alokasi awal objek
│   └── Intermediate: Objek yang lolos 1 siklus GC
└── Old Generation (Major GC - Mark-Sweep-Compact)
    ├── Mark-Compact: Objek yang lolos 2 siklus GC
    └── Sweep: De-alokasi memori objek mati menjadi Free-list
```

1. **Young Generation (Minor GC - Scavenger)**: Menggunakan algoritma Cheney. Memori dibagi menjadi dua *Semi-Spaces*: `From-Space` dan `To-Space`. Selama pembersihan, pointer aktif disalin secara berurutan (*evacuation*) ke `To-Space`, menghilangkan fragmentasi memori seketika. Objek yang bertahan lebih dari ambang promosi dipindahkan ke *Old Generation*.
2. **Old Generation (Major GC - Mark-Sweep-Compact)**:
   * **Concurrent Marking**: Background workers melakukan penelusuran graf objek selagi thread JavaScript utama terus mengeksekusi kode menggunakan tri-color marking algorithm (White, Grey, Black) dan Write Barriers.
   * **Incremental Steps**: Thread utama membagi proses penandaan menjadi potongan-potongan waktu mikro untuk mencegah frame drop.
   * **Parallel Compaction & Sweeping**: Background workers menyusun ulang memori untuk mencegah fragmentasi halaman memori OS.

### Sampling Profiler Theory: Nyquist-Shannon & Profiling Overhead

CPU Profiling pada Node.js/V8 berbasis pada **Statistical Sampling** (interupsi berbasis timer).

Alih-alih menyuntikkan instruksi instrumentasi ke setiap fungsi (yang merusak eksekusi cache dan memicu overhead ekstrim), V8 runtime mengaktifkan thread internal profiling OS terpisah yang membangkitkan interrupt berkala (default interval: $1000\mu s$ / $1ms$).

Pada setiap tick interupsi, OS context dihentikan sejenak, Program Counter (PC) dibaca, dan Call Stack ditelusuri ke bawah (*stack walking*).

$$f_{\text{nyquist}} > 2 \cdot f_{\text{max}}$$

Jika durasi eksekusi suatu fungsi lebih pendek daripada sampling interval dan dieksekusi secara sporadis, fungsi tersebut dapat terlewatkan dari profiling trace (*Sampling Bias*). Oleh karena itu, *Micro-benchmarking* tanpa saturasi iterasi yang memadai tidak valid secara statistik.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Program berikut mendemonstrasikan pelacakan performa tingkat rendah:
1. Pemantauan mutasi Hidden Class (Shapes) dan pembuktian deoptimisasi Inline Cache.
2. Pengukuran presisi Event Loop Delay (ELD) menggunakan `node:perf_hooks`.
3. Pemicuan CPU Sampling Profiler programatis menggunakan `node:inspector` tanpa CLI external tooling.

```javascript
// runtime-diagnostics.js
import { Session } from 'node:inspector';
import { monitorEventLoopDelay, performance, PerformanceObserver } from 'node:perf_hooks';
import fs from 'node:fs';

// -------------------------------------------------------------
// 1. SETUP EVENT LOOP DELAY HISTOGRAM
// -------------------------------------------------------------
const eldHistogram = monitorEventLoopDelay({ resolution: 20 });
eldHistogram.enable();

// -------------------------------------------------------------
// 2. SETUP V8 PROFILER VIA NODE INSPECTOR API
// -------------------------------------------------------------
class V8ProfilerEngine {
  #session;

  constructor() {
    this.#session = new Session();
    this.#session.connect();
  }

  async startProfiling() {
    return new Promise((resolve, reject) => {
      this.#session.post('Profiler.enable', (err) => {
        if (err) return reject(err);
        this.#session.post('Profiler.start', (err) => {
          if (err) return reject(err);
          resolve();
        });
      });
    });
  }

  async stopProfiling(outputPath) {
    return new Promise((resolve, reject) => {
      this.#session.post('Profiler.stop', (err, { profile }) => {
        if (err) return reject(err);
        fs.writeFileSync(outputPath, JSON.stringify(profile));
        this.#session.post('Profiler.disable', () => {
          this.#session.disconnect();
          resolve(profile);
        });
      });
    });
  }
}

// -------------------------------------------------------------
// 3. INLINE CACHE SHAPE EXPERIMENTATION
// -------------------------------------------------------------
// Monomorphic Object Generator
function createMonomorphicPoint(x, y) {
  return { x, y };
}

// Megamorphic Object Generator
function createMegamorphicPoint(i) {
  const obj = {};
  // Menghasilkan mutasi shape yang dinamis dan acak
  obj[`prop_${i % 50}`] = i;
  obj.x = i;
  obj.y = i * 2;
  return obj;
}

// Target function yang akan dianalisis IC-nya
function computeDistanceSquared(point) {
  return point.x * point.x + point.y * point.y;
}

// -------------------------------------------------------------
// 4. WORKLOAD EXECUTION & METRIC CAPTURE
// -------------------------------------------------------------
async function executeWorkload() {
  const profiler = new V8ProfilerEngine();
  await profiler.startProfiling();

  console.log('[System] Memulai profiling session...');

  // Phase A: Warm up - Monomorphic Path
  console.log('[Phase A] Monomorphic Execution...');
  const monoPoints = Array.from({ length: 1_000_000 }, (_, i) => 
    createMonomorphicPoint(i, i + 1)
  );

  const startMono = performance.now();
  for (let i = 0; i < monoPoints.length; i++) {
    computeDistanceSquared(monoPoints[i]);
  }
  const endMono = performance.now();
  console.log(`[Phase A] Selesai: ${(endMono - startMono).toFixed(3)} ms`);

  // Phase B: Heavy Stress - Megamorphic Path
  console.log('[Phase B] Megamorphic Pollution...');
  const megaPoints = Array.from({ length: 1_000_000 }, (_, i) => 
    createMegamorphicPoint(i)
  );

  const startMega = performance.now();
  for (let i = 0; i < megaPoints.length; i++) {
    computeDistanceSquared(megaPoints[i]);
  }
  const endMega = performance.now();
  console.log(`[Phase B] Selesai: ${(endMega - startMega).toFixed(3)} ms`);

  // Phase C: Menginduksi Event Loop Starvation
  console.log('[Phase C] Inducing Synchronous Lag...');
  const blockStart = performance.now();
  while (performance.now() - blockStart < 250) {
    // Synchronous execution menduduki thread selama 250ms
  }

  eldHistogram.disable();
  await profiler.stopProfiling('./v8-trace-output.cpuprofile');

  console.log('\n===== METRIK TELEMETRI EVENT LOOP (NANOSECONDS) =====');
  console.log(`Min Latency:     ${(eldHistogram.min / 1e6).toFixed(3)} ms`);
  console.log(`Max Latency:     ${(eldHistogram.max / 1e6).toFixed(3)} ms`);
  console.log(`Mean Latency:    ${(eldHistogram.mean / 1e6).toFixed(3)} ms`);
  console.log(`p50 Latency:     ${(eldHistogram.percentile(50) / 1e6).toFixed(3)} ms`);
  console.log(`p99 Latency:     ${(eldHistogram.percentile(99) / 1e6).toFixed(3)} ms`);
  console.log(`p99.9 Latency:   ${(eldHistogram.percentile(99.9) / 1e6).toFixed(3)} ms`);
  console.log('CPU Profile berhasil disimpan ke ./v8-trace-output.cpuprofile');
}

executeWorkload().catch(console.error);
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah diseksi operasional terhadap blok kode implementasi Seksi 07:

1. **Baris 2–4**: 
   * `import { Session } from 'node:inspector'`: Mengimpor instrumen IPC internal yang berkomunikasi langsung dengan V8 Debugger Agent menggunakan Chrome DevTools Protocol (CDP).
   * `monitorEventLoopDelay`: Mengaktifkan sampler interval berbasis timer libuv tingkat hardware untuk mencatat histogram keterlambatan eksekusi frame.
2. **Baris 9–10**:
   * `monitorEventLoopDelay({ resolution: 20 })`: Mengonfigurasi histogram pengukur delay dengan resolusi sampling internal 20 milidetik. Resolusi ini meminimalkan distorsi pengamatan (*observer effect*) terhadap *event-loop thread*.
   * `eldHistogram.enable()`: Menginstruksikan V8 untuk mulai merekam distribusi delay secara real-time ke dalam native memory buffer.
3. **Baris 15–43 (`V8ProfilerEngine`)**:
   * `new Session()` & `this.#session.connect()`: Membuka channel transmisi in-process ke V8 Core thread.
   * `Profiler.enable`: Menginstruksikan V8 untuk mempersiapkan runtime memory bagi alokasi call-stack trace tree.
   * `Profiler.start`: Mengaktifkan interrupt timer OS berbasis sinyal Unix (`SIGPROF`) pada interval 1ms.
   * `Profiler.stop`: Menghentikan thread sampler dan mengembalikan graf snapshot eksekusi CPU berupa Call Frame Nodes beserta metadata waktu (`hitCount`, `timeDeltas`).
   * `fs.writeFileSync(...)`: Menyimpan output berformat JSON serial CDP yang kompatibel secara langsung dengan visualizer FlameGraph pada `chrome://tracing` atau VSCode Profiles.
4. **Baris 48–60 (`createMonomorphicPoint` vs `createMegamorphicPoint`)**:
   * `createMonomorphicPoint`: Menghasilkan objek dengan *Map layout* identik `(Map_0 -> {x, y})`.
   * `createMegamorphicPoint`: Menyuntikkan dynamic key assignment secara acak (`prop_${i % 50}`). Hal ini memaksa runtime menciptakan puluhan jalur transisi Map (`Map_0 -> Map_1`, `Map_0 -> Map_2`, dst.).
5. **Baris 63–65 (`computeDistanceSquared`)**:
   * Pada iterasi awal, TurboFan mengompilasi akses `point.x` menjadi inline fetch berbasis direct memory address offset Map_0.
   * Ketika dieksekusi dengan *megamorphic objects*, TurboFan mendeteksi pelanggaran tipe (deopt), mengosongkan instruksi native yang telah dioptimasi, dan menurunkan derajat optimasi pemanggilan properti menjadi *Megamorphic Stub Cache lookup*.
6. **Baris 98–101**:
   * Memvalidasi bahwa loop pemblokiran synchronous ($250\text{ ms}$) secara langsung tertangkap oleh histogram `monitorEventLoopDelay` tanpa terdistorsi oleh modul asynchronous lainnya.
7. **Baris 106–112**:
   * Membaca struktur internal histogram pada variasi percentile yang merepresentasikan anomali tail-latency: $p99$ dan $p99.9$ dikonversi dari satuan nanodetik ke milidetik via kalkulasi pembagian floating-point ($10^6$).

---

# SEKSI 09 — STUDI KASUS NYATA

### Konteks Produksi: *FinTech High-Throughput Payment Router*

Sebuah sistem agregasi pembayaran global berbasis Node.js menangani $18.000\text{ request/detik}$ pada arsitektur container Kubernetes (8 CPU cores, 16GB RAM terdistribusi). 

### Insiden Performa

Sistem mengalami degradasi performa drastis setiap hari pada jam perdagangan puncak:
* Metrik rata-rata ($p50$) tetap terkendali pada angka $12\text{ ms}$.
* Metrik ekor ($p99$ dan $p99.9$) melonjak secara eksponensial hingga $3.800\text{ ms}$, mengakibatkan *cascading timeouts* pada downstream payment gateways.
* Node.js worker pods mengalami *OOMKilled* (Out Of Memory) secara acak setiap 45 menit.

```
Request Latency
 ^
 |                                                    [ p99.9: 3800ms ]
 |                                                           |
 |                                                           |
 |                                      +--------------------+
 |                                      | Major GC Pause
 |                                      | & Microtask Queue Starvation
 | [ p50: 12ms ]                        |
 +--------------------------------------+-----------------------------> Time
```

### Investigasi Root-Cause

Setelah mengumpulkan data telemetri, heap snapshots, dan profiling CPU real-time, tim engineering menemukan 3 anomali struktural:
1. **Megamorphic Transformation pada Request Parser**: Payload JSON yang masuk disaring melalui parser middleware yang menyuntikkan flag audit dinamis dengan urutan key acak (`req.audit_context_<random_id>`). Ini mengubah objek `PaymentTransaction` dari monomorphic menjadi megamorphic, menurunkan throughput serialisasi hingga 400%.
2. **Buffer Fragmentation & Closure Retainers**: Token autentikasi internal didekodekan menggunakan slice string dari buffer raksasa yang disimpan di dalam *context closure scope* berumur panjang. Hal ini menahan referensi buffer asli di Old Generation Heap secara permanen (*Lapsed Listener Pattern*).
3. **Microtask Starvation via Promise Resolution Cascading**: Pemrosesan batching ledger dilakukan menggunakan rekursi Promise tanpa throttling native tick, yang mendeprivasi thread dari pemrosesan Macrotasks I/O libuv (epoll event pool). Akibatnya, koneksi jaringan baru tertahan di network backlog kernel.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem payment router yang telah direkayasa ulang:
1. Menerapkan pola **Struct Shape Stability** (menjaga Hidden Class tetap Monomorphic).
2. Mengintegrasikan **OpenTelemetry SDK** manual dengan context propagation.
3. Menggunakan **Event Loop Utilization (ELU)** metrics untuk active backpressure.
4. Menerapkan **Fast-Path Object Allocator** untuk meminimalkan beban Young-Gen GC.

```javascript
// production-gateway.js
import http from 'node:http';
import { performance, eventLoopUtilization } from 'node:perf_hooks';
import opentelemetry from '@opentelemetry/api';
import { BasicTracerProvider, SimpleSpanProcessor } from '@opentelemetry/sdk-trace-base';

// -----------------------------------------------------------------------------
// 1. TELEMETRY INITIALIZATION (OPENTELEMETRY TRACER)
// -----------------------------------------------------------------------------
class ProductionTraceExporter {
  export(spans, resultCallback) {
    for (const span of spans) {
      // In-line micro-footprint: Hindari alokasi JSON raksasa di hot-path
      if (span.duration[0] > 0 || span.duration[1] > 50_000_000) { // Log spans > 50ms
        process._rawDebug(`[SLOW SPAN DETECTED] ${span.name} - Duration: ${(span.duration[1] / 1e6).toFixed(2)}ms`);
      }
    }
    resultCallback({ code: 0 });
  }
  shutdown() { return Promise.resolve(); }
}

const provider = new BasicTracerProvider();
provider.addSpanProcessor(new SimpleSpanProcessor(new ProductionTraceExporter()));
provider.register();

const tracer = opentelemetry.trace.getTracer('payment-gateway-core', '2.4.0');

// -----------------------------------------------------------------------------
// 2. MONOMORPHIC ENGINE STRUCT SHAPE
// Mengunci urutan deklarasi hidden classes agar tidak memicu Megamorphic Transitions
// -----------------------------------------------------------------------------
class FastPaymentContext {
  // Properti dideklarasikan secara deterministik pada constructor
  constructor(transactionId, amount, currency) {
    this.transactionId = transactionId;
    this.amount = amount;
    this.currency = currency;
    this.isFlagged = false;
    this.processingLatencyMs = 0;
    this.metadata = null; // Selalu diinisialisasi, bukan undefined atau dynamic key
  }
}

// -----------------------------------------------------------------------------
// 3. BACKPRESSURE CONTROLLER VIA EVENT LOOP UTILIZATION (ELU)
// -----------------------------------------------------------------------------
class BackpressureEngine {
  #lastEluSample;
  #threshold;

  constructor(threshold = 0.85) {
    this.#threshold = threshold; // Reject / Shed load jika thread > 85% saturasi
    this.#lastEluSample = eventLoopUtilization();
  }

  isSaturated() {
    const currentElu = eventLoopUtilization();
    const utilization = eventLoopUtilization(currentElu, this.#lastEluSample).utilization;
    this.#lastEluSample = currentElu;
    return utilization > this.#threshold;
  }
}

const backpressure = new BackpressureEngine(0.85);

// -----------------------------------------------------------------------------
// 4. MEMORY-SAFE PAYLOAD PROCESSOR
// -----------------------------------------------------------------------------
function parseSafePayload(buffer) {
  // Parsing payload deterministik tanpa retain buffer ref
  const rawString = buffer.toString('utf8');
  const parsed = JSON.parse(rawString);
  
  // Konstruksi instance dengan struktur monomorphic stabil
  const context = new FastPaymentContext(
    parsed.id || 'N/A',
    typeof parsed.amount === 'number' ? parsed.amount : 0,
    parsed.currency || 'USD'
  );

  if (parsed.audit) {
    context.metadata = parsed.audit; // Tidak mengubah hidden-class struct root
  }
  return context;
}

// -----------------------------------------------------------------------------
// 5. HTTP SERVER DENGAN DISTRIBUTED TELEMETRY & ADAPTIVE SHEDDING
// -----------------------------------------------------------------------------
const server = http.createServer((req, res) => {
  // A. Backpressure Check
  if (backpressure.isSaturated()) {
    res.writeHead(503, { 'Content-Type': 'application/json', 'Retry-After': '1' });
    res.end(JSON.stringify({ error: 'System Capacity Saturated: ELU Exhaustion' }));
    return;
  }

  // B. Span Creation & Context Tracking
  const span = tracer.startSpan('process_payment_request', {
    attributes: {
      'http.method': req.method,
      'http.url': req.url
    }
  });

  const startTime = performance.now();
  const chunks = [];

  req.on('data', (chunk) => {
    chunks.push(chunk);
  });

  req.on('end', () => {
    try {
      const bodyBuffer = Buffer.concat(chunks);
      const paymentCtx = parseSafePayload(bodyBuffer);

      // Core Business Logic (High Speed Math)
      if (paymentCtx.amount > 10_000) {
        paymentCtx.isFlagged = true;
      }

      paymentCtx.processingLatencyMs = performance.now() - startTime;

      // Kirim Respon
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        status: 'SUCCESS',
        txId: paymentCtx.transactionId,
        flagged: paymentCtx.isFlagged,
        latency: paymentCtx.processingLatencyMs
      }));

      span.setStatus({ code: opentelemetry.SpanStatusCode.OK });
    } catch (err) {
      span.recordException(err);
      span.setStatus({
        code: opentelemetry.SpanStatusCode.ERROR,
        message: err.message
      });
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Invalid Payload' }));
    } finally {
      span.end();
    }
  });
});

server.listen(3000, () => {
  console.log('[Payment Gateway] Engine running on :3000 under V8 profiling instrumentation');
});
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Metodologi Profiling: Sampling vs. Tracing vs. Instrumentation

| Karakteristik | CPU Sampling Profiler (`node:inspector`) | Instrumentation Tracing (OpenTelemetry) | Manual APM Patches (Monkey-patching) |
| :--- | :--- | :--- | :--- |
| **Runtime Overhead** | Sangat Rendah ($\approx 1\% - 3\%$) | Rendah - Menengah ($\approx 3\% - 8\%$) | Tinggi ($\approx 15\% - 30\%$) |
| **Akurasi Pemanggilan** | Statistik probabilistik (rentan *Sampling Bias*) | Deterministik untuk batas Span ($100\%$ terukur) | Deterministik pada level fungsi |
| **Dampak Memory Footprint** | Rendah (Fixed memory sampling buffer) | Menengah (Alokasi objek span dan trace context) | Tinggi (Retensi wrapper context & closures) |
| **Granularitas Data** | Baris kode instruksi V8 / C++ Assembly | Segmentasi Arsitektural (HTTP, DB, Cache) | Level fungsi tunggal |
| **Kesesuaian di Produksi** | On-demand ad-hoc debugging | Continuous Always-On Observability | Sangat tidak disarankan di high-throughput |

### Strategi Pengukuran Latensi: ELD vs. ELU vs. OS Metrics

```
+-----------------------------------------------------------------------------+
| PARAMETER EVALUASI | EVENT LOOP DELAY (ELD) | EVENT LOOP UTILIZATION (ELU)  |
+--------------------+------------------------+-------------------------------+
| Teori Pengukuran   | Delay selisih waktu    | Rasio aktif vs idle pada loop |
|                    | penjadwalan timer      | libuv thread pool             |
| Dampak I/O Wait    | Menghasilkan false     | Murni merefleksikan kerja CPU |
|                    | positive saat idle     | aktual V8                     |
| Reaktivitas        | Cepat terhadap spike   | Stabil, cocok untuk algoritma |
|                    | tunggal pemblokiran    | adaptive load-shedding        |
+-----------------------------------------------------------------------------+
```

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The `delete` Operator and Shape Morphing
Penggunaan operator `delete` pada objek literal (misal `delete user.taxId`) secara instan mengubah representasi internal V8 Map menjadi **Dictionary Mode** (Hash Table).
* Akses properti berikutnya tidak lagi menggunakan offset memori terhitung, melainkan pencarian hash table lambat.
* Hindari `delete obj.prop`; gunakan pemetaan eksplisit ke objek baru atau inisialisasi properti dengan nilai `undefined` atau `null`.

### 2. Large Object Space Allocation Thrashing
Objek, Buffer, atau String yang memiliki alokasi memori berukuran lebih dari konfigurasi alokasi V8 Page (standar: $> 512\text{ KB}$ tergantung arsitektur dan versi) tidak masuk ke *Young Generation*, melainkan dialokasikan langsung ke **Large Object Space** di Old Generation.
* Konsekuensi: Objek ini tidak dibersihkan oleh *Minor Scavenge GC*.
* Objek ini hanya dapat direklamasi melalui siklus *Full Major GC (Mark-Sweep-Compact)*.
* Alokasi berulang terhadap Buffer berukuran $>1\text{ MB}$ pada hot-path memicu p99 freeze akibat Garbage Collector dipaksa melakukan *stop-the-world compaction phase*.

### 3. High-Resolution Time Precision Hazards
`performance.now()` menggunakan *monotonic clock* sistem operasi (`CLOCK_MONOTONIC`).
* **Pitfall Keamanan (Spectre/Meltdown)**: Runtime modern membatasi resolusi time float dari mikrodetik hingga pembulatan ke atas (biasanya terpotong hingga $5\mu s - 20\mu s$ tergantung environment/browser mitigations).
* **Clock Drift**: Jangan membandingkan hasil `performance.now()` lintas worker threads tanpa mekanisme korelasi clock drift epoch bersama.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan `Date.now()` untuk Benchmarking & Latency Tracking

```javascript
// BAD: Date.now() mengandalkan OS wall-clock time
// Rentan terhadap penyesuaian NTP sync, menghasilkan durasi negatif atau lompatan waktu
const start = Date.now();
doTask();
const duration = Date.now() - start; // BISA MENJADI NEGATIF JIKA TERJADI NTP SYNC!

// GOOD: Menggunakan monotonic clock
const startMono = performance.now();
doTask();
const durationMono = performance.now() - startMono; // Dijamin selalu bergerak maju secara stabil
```

### 2. Unintentional Megamorphism Melalui Polimorfisme Parameter Fungsi

```javascript
// BAD: Menyerahkan objek konfigurasi dengan field acak atau order berbeda
function renderHeader(data) {
  return `<h1>${data.title}</h1><span>${data.subtitle}</span>`;
}
renderHeader({ title: 'A', subtitle: 'B' }); // Map 1
renderHeader({ subtitle: 'B', title: 'A' }); // Map 2 (Transitions broken!)
renderHeader({ title: 'A', extra: true, subtitle: 'B' }); // Map 3
// Hasil: renderHeader jatuh ke Megamorphic Inline Cache

// GOOD: Bentuk kelas formal dengan struktur properti deterministik
class HeaderModel {
  constructor(title, subtitle) {
    this.title = title;
    this.subtitle = subtitle;
  }
}
renderHeader(new HeaderModel('A', 'B'));
renderHeader(new HeaderModel('A', 'B')); // Selalu Monomorphic (Map yang sama)
```

### 3. Starvasi Event Loop Melalui Resolusi Microtask Tanpa Akhir

```javascript
// BAD: Recursive Promise resolution membakar Microtask Queue secara total
function drainQueue(queue) {
  if (queue.length === 0) return;
  Promise.resolve().then(() => {
    queue.shift()();
    drainQueue(queue); // Macrotasks (I/O, timer, socket) TIDAK PERNAH DIEKSEKUSI!
  });
}

// GOOD: Memecah siklus menggunakan setImmediate untuk mengembalikan kontrol ke libuv
function drainQueueSafe(queue) {
  if (queue.length === 0) return;
  setImmediate(() => {
    queue.shift()();
    drainQueueSafe(queue); // Event loop dapat memproses I/O poll pada setiap step
  });
}
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Deterministic Object Property Initialization**: Selalu inisialisasi semua properti objek pada *constructor* atau inisialisasi literal secara teratur. Jangan pernah menyuntikkan properti baru pasca-instansiasi secara dinamis.
2. **Span and Allocation Throttling pada Telemetri**: Jangan pernah membuat span OpenTelemetry atau tracing log pada setiap operasi array atau fungsi mikro. Terapkan *Head-based Sampling* atau *Tail-based Sampling* (misal: hanya sampling $1\%$ request sukses, dan $100\%$ request lambat atau error).
3. **Optimalkan Buffer Re-use Melalui Memory Pooling**: Gunakan kembali alokasi buffer yang ada pada jaringan berkecepatan tinggi dengan buffer pool atau streaming pipeline, alih-alih mengeksekusi `Buffer.concat()` secara repetitif pada setiap HTTP packet.
4. **Isolasi Alokasi Global Context**: Jauhkan dependensi caching dari global variables. Jika membutuhkan lokal caching, gunakan `WeakMap` untuk memastikan objek target dapat direklamasi oleh Scavenger GC tanpa kebocoran memori.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Optimasi Hidden Class Layout & Array Storage Modes

V8 mengklasifikasikan array ke dalam representasi internal berdasarkan kontinuitas tipe data:
* `PACKED_SMI_ELEMENTS`: Array padat hanya berisi Small Integers (SMI: 31-bit integer). Operasi paling cepat.
* `PACKED_DOUBLE_ELEMENTS`: Array padat berisi float/numbers.
* `PACKED_ELEMENTS`: Array padat berisi referensi objek atau mixed-types.
* `HOLEY_*_ELEMENTS`: Array yang memiliki celah kosong/lubang (*holes*), misal akibat `delete arr[1]` atau `const arr = new Array(10)`.

```javascript
// CONTOH OPTIMASI: Mencegah De-transisi Array Elements
// BAD: Menciptakan HOLEY array
const holeyArray = new Array(3);
holeyArray[0] = 1;
holeyArray[2] = 3; // Index 1 adalah Hole. Array beralih ke representasi HOLEY_SMI_ELEMENTS secara permanen

// GOOD: Inisialisasi packed array
const packedArray = [1, 2, 3]; // PACKED_SMI_ELEMENTS
```

### Konfigurasi Runtime Flag V8 untuk Server Produksi Berkinerja Tinggi

```bash
node \
  --max-old-space-size=4096 \
  --noconcurrent_sweeping=false \
  --interpreted-frames-native-stack \
  --perf-basic-prof \
  server.js
```
* `--max-old-space-size=4096`: Mematok batas atas Old Generation ke 4GB guna mencegah paging virtual memory thrashing oleh OS.
* `--perf-basic-prof`: Menginstruksikan V8 untuk menghasilkan symbol maps pada `/tmp/perf-<pid>.map` agar kernel Linux `perf` dapat memetakan dynamic JIT address ke nama fungsi JavaScript pada FlameGraph hardware.

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Mitigasi Regular Expression Denial of Service (ReDoS)
Eksekusi Regex dengan kompleksitas kuadratik atau eksponensial ($O(2^n)$) menghentikan thread JavaScript seketika, membekukan seluruh event loop process.

```javascript
// Vulnerable Regex: Evaluasi string panjang dengan trailing payload memicu catastrophic backtracking
const evilRegex = /(a+)+b/;

// Hardening: Gunakan V8 RegExp flag 'v' (tersedia di Node.js modern) dan batasi panjang input
function validateSafeInput(input) {
  if (typeof input !== 'string' || input.length > 512) {
    throw new Error('Payload length security violation');
  }
  // Gunakan RegExp timeout native atau library engine terisolasi (misal: re2 via bindings)
}
```

### 2. Telemetry Redaction: PII (Personally Identifiable Information) Leaks
OpenTelemetry Trace Spans secara default dapat merekam HTTP query params atau header yang sensitif (seperti `Authorization: Bearer ...` atau data kartu kredit).
* Implementasikan **Trace Processor Redactor** untuk memindai atribut sebelum span diekspor ke collector sentral guna memenuhi kepatuhan regulasi data (GDPR, PCI-DSS).

```javascript
class SecureSpanProcessor {
  onStart(span) {}
  onEnd(span) {
    const rawUrl = span.attributes['http.url'];
    if (typeof rawUrl === 'string') {
      // Redact parameter token atau kunci rahasia
      span.attributes['http.url'] = rawUrl.replace(/(token|access_key|auth)=[^&]+/ig, '$1=[REDACTED]');
    }
  }
}
```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### CLI Diagnostic Commands untuk Profiling Mendalam

#### 1. Melacak Deoptimasi TurboFan Real-time
Gunakan internal tracing flag engine untuk mengisolasi baris kode yang memicu deoptimisasi JIT:
```bash
node --trace-deopt --trace-opt-verbose app.js > deopt-trace.log
```
Analisis log untuk mencari pesan `[bailout ... reason: Insufficient type feedback for call]`.

#### 2. Profiling Berbasis Sampling Menggunakan V8 Tick Profiler
```bash
# 1. Jalankan aplikasi dengan profiling tick aktif
node --prof app.js

# 2. Bebani aplikasi dengan traffic load tester (misal: autocannon, k6)
autocannon -c 100 -d 30 http://localhost:3000

# 3. Hentikan node process, file isolate-0x...-v8.log akan tercipta
# 4. Proses output log menjadi format yang dapat dibaca manusia
node --prof-process isolate-*.log > processed-profile.txt
```

#### 3. Diagnostic Flame Graphs dengan Clinic.js
```bash
# Instalasi Clinic.js
npm install -g clinic

# Mengidentifikasi CPU bottlenecks dengan visualisasi FlameGraph interaktif
clinic flame -- node app.js

# Mengidentifikasi lag Event Loop dan I/O blocking
clinic doctor -- node app.js
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### Intisari Optimasi V8 & Telemetry

```
+-------------------------------------------------------------------------------+
| MASALAH PERFORMA        | PENYEBAB UTAMA            | TINDAKAN PERBAIKAN      |
+-------------------------+---------------------------+-------------------------+
| Megamorphic Access      | Mengubah susunan/properti | Inisialisasi struktur   |
|                         | objek secara dinamis      | class secara seragam    |
+-------------------------+---------------------------+-------------------------+
| High p99 Latency        | Stop-The-World GC Pauses  | Hindari alokasi besar   |
|                         | atau synchronous blocks   | pada hot-path (>512KB)  |
+-------------------------+---------------------------+-------------------------+
| High Event Loop Delay   | CPU bound computation     | Pecah via setImmediate/ |
|                         | pada synchronous thread   | Worker Threads pool     |
+-------------------------+---------------------------+-------------------------+
| Array Hole Deopt        | Array jarang (sparse)     | Inisialisasi packed     |
|                         | atau penggunaan delete    | element secara rapat    |
+-------------------------+---------------------------+-------------------------+
| Memory Leak (Closures)  | Event listener / closure  | Gunakan WeakRef/WeakMap |
|                         | memegang referensi besar  | dan deregistrasi event  |
+-------------------------+---------------------------+-------------------------+
```

### Essential Profiling Flags

* `--prof`: Merekam profiling CPU sampling berkala ke file disk.
* `--trace-gc`: Mencatat setiap event Garbage Collection (Scavenge, Mark-Sweep) beserta alokasi memori dan jeda waktu (*pause duration*).
* `--max-old-space-size`: Menyetel batasan Old Generation Heap dalam megabytes.
* `--expose-gc`: Mengaktifkan akses programmatic ke fungsi `global.gc()` (hanya untuk pengujian di controlled environments).

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah satu jawaban yang paling tepat untuk setiap pertanyaan, kemudian periksa penjelasan di bawahnya.

### Bagian 1: Basic Concept

#### Q1. Apa yang dimaksud dengan "Hidden Class" (atau "Map") di dalam engine V8?
* A. Fitur private class fields `#` pada standard ECMAScript.
* B. Struktur data internal V8 yang merekam layout memori dan offset properti objek secara dinamis.
* C. Class bayangan yang dibuat otomatis oleh browser untuk memproses enkripsi HTTPS.
* D. Konfigurasi internal untuk menyembunyikan stack trace dari output error konsol.

#### Q2. Apa konsekuensi performa saat sebuah Inline Cache (IC) berubah status dari Monomorphic menjadi Megamorphic?
* A. V8 mengalokasikan lebih banyak thread CPU libuv untuk memproses fungsi tersebut.
* B. V8 menghapus seluruh heap memory yang dialokasikan untuk objek terkait.
* C. V8 beralih dari instruksi machine-code call langsung ke pencarian global hash-table stub cache yang jauh lebih lambat.
* D. V8 secara otomatis menolak operasi I/O jaringan berikutnya.

#### Q3. Mengapa metrik `Date.now()` tidak valid digunakan untuk mengukur durasi operasi performa tingkat rendah (micro-benchmarks)?
* A. Karena `Date.now()` memiliki kompleksitas $O(n)$ terhadap heap memory.
* B. Karena `Date.now()` mengacu pada OS Wall-Clock yang dapat melompat maju/mundur akibat sinkronisasi waktu jaringan (NTP).
* C. Karena `Date.now()` hanya dapat dipanggil satu kali dalam satu tick Event Loop.
* D. Karena `Date.now()` selalu mengembalikan nilai integer yang dibulatkan ke kelipatan 1000ms.

#### Q4. Generasi memori manakah di dalam V8 Heap yang menjadi target pembersihan algoritma Scavenger Minor GC?
* A. Large Object Space.
* B. Old Pointer Space.
* C. Young Generation (Eden & Survivor Spaces).
* D. Code Space (JIT Assembly).

#### Q5. Manakah dari status representasi array berikut yang memberikan performa akses tercepat di V8?
* A. `PACKED_SMI_ELEMENTS`
* B. `HOLEY_ELEMENTS`
* C. `HOLEY_DOUBLE_ELEMENTS`
* D. `DICTIONARY_ELEMENTS`

---

### Bagian 2: Intermediate & Advanced

#### Q6. Mengapa Event Loop Utilization (ELU) dianggap metrik observabilitas yang lebih akurat dibandingkan CPU Usage persentase OS untuk mendeteksi saturasi thread Node.js?
* A. Karena OS CPU usage tidak dapat dibaca dari dalam container Docker.
* B. Karena ELU mengisolasi waktu thread JavaScript aktif mengeksekusi kode versus waktu tidur (idle) menunggu event poll, terlepas dari aktivitas core CPU OS eksternal.
* C. Karena ELU mengabaikan memori garbage collector secara penuh.
* D. Karena ELU hanya merekam transaksi jaringan yang gagal.

#### Q7. Perhatikan kode berikut:
```javascript
function Point(x, y) {
  this.x = x;
  if (x > 100) {
    this.special = true;
  }
  this.y = y;
}
```
**Apa dampak arsitektur dari konstruktor di atas terhadap V8 Hidden Classes jika dipanggil dengan variasi nilai `x <= 100` dan `x > 100`?**
* A. Seluruh objek akan secara otomatis diubah menjadi `WeakMap`.
* B. Objek akan memiliki dua jalur transisi Map yang berbeda karena properti `special` disisipkan di tengah deklarasi properti `y`.
* C. V8 akan mematikan fitur Garbage Collection untuk objek tersebut.
* D. Tidak ada dampak sama sekali, V8 selalu mengurutkan properti secara alfabetis.

#### Q8. Apa yang terjadi ketika objek dialokasikan melebihi batas page (~512KB - 1MB) di Node.js/V8?
* A. Objek dialokasikan langsung ke Large Object Space dan hanya bisa dibersihkan melalui siklus Major GC.
* B. V8 melempar error `RangeError: Allocation buffer overrun` seketika.
* C. Objek dipotong menjadi chunk kecil di Young Generation Scavenge space.
* D. V8 menyalin objek secara sinkron ke dalam swap space hard disk.

#### Q9. Mengapa eksekusi microtasks yang berkepanjangan (misal: recursive `Promise.resolve().then(...)`) dapat mematikan performa I/O server secara masif?
* A. Karena Microtask queue diproses pada worker thread pool libuv, bukan main thread.
* B. Karena runtime menghabiskan seluruh jatah tick untuk menguras Microtask Queue sebelum beralih ke Macrotask I/O Phase, membekukan pemrosesan event socket jaringan baru.
* C. Karena V8 akan menghapus cache TLS secara berkala jika microtask penuh.
* D. Karena ukuran microtask queue dibatasi maksimal 16 item oleh spesifikasi POSIX.

#### Q10. Pada OpenTelemetry tracing, mengapa direct console logging span secara sinkron pada hot-path dianggap sebagai anti-pattern kritis?
* A. Karena penulisan I/O stream ke `stdout` bersifat sinkron di banyak lingkungan terminal Unix/Windows, yang dapat memblokir thread event loop utama secara masif.
* B. Karena OTel tidak mendukung format data konsol.
* C. Karena konsol stdout secara otomatis mematikan JIT compiler TurboFan.
* D. Karena V8 akan memaksa full GC setiap kali `console.log` dieksekusi.

---

### Kunci Jawaban & Pembahasan

1. **B** — Hidden Class (Map) merekam struktur offset memori properti secara internal untuk memfasilitasi akses cepat.
2. **C** — Polimorfisme tinggi (>4 shapes) memaksa runtime meninggalkan inlining cepat dan menggunakan Megamorphic stub cache lookup.
3. **B** — `Date.now()` membaca Wall-Clock yang dapat berubah sewaktu-waktu akibat NTP sync; pengukuran latensi presisi wajib menggunakan `performance.now()`.
4. **C** — Minor GC (Scavenger) secara eksklusif beroperasi membersihkan objek berumur pendek di Young Generation.
5. **A** — `PACKED_SMI_ELEMENTS` adalah array rapat berisi small integers tanpa boxing dan tanpa pointer chasing, menjadikannya struktur array tercepat di V8.
6. **B** — ELU mengukur persentase waktu thread main event loop aktif melakukan komputasi versus idle pada I/O epoll poll loop.
7. **B** — Penyisipan properti kondisional di tengah assignment mengubah struktur urutan Map transition tree, menghasilkan polymorphism pada pemanggilan properti berikutnya.
8. **A** — Objek berukuran masif dialokasikan di Large Object Space untuk menghindari biaya penyalinan memori berkali-kali pada Semi-spaces Scavenger GC.
9. **B** — Sesuai spesifikasi Event Loop, Microtask queue harus dikuras sampai tuntas sebelum runtime beralih ke phase berikutnya (Timer/IO Macrotasks), memicu event loop starvation.
10. **A** — Operasi synchronous `stdout` I/O memblokir eksekusi thread utama; telemetri produksi wajib menggunakan non-blocking in-memory buffer batch exporter.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Lab: *Isolasi Memory Leak, Deopt Optimization, & Telemetry Dashboard*

#### Deskripsi Skenario
Anda diberikan sebuah starter file `flawed-service.js` yang mengalami degradasi performa akut: p99 latency melonjak di atas $1.500\text{ ms}$, Event Loop Delay membengkak, dan memori heap bocor hingga crash.

```javascript
// flawed-service.js
import http from 'node:http';

const transactionCache = [];

function recordTransaction(id, val, opts) {
  const tx = { id, val };
  if (opts && opts.flag) {
    tx.flag = true;
  }
  tx.timestamp = Date.now();
  // BUG: Memory Leak melalui unbounded array retaining closures
  transactionCache.push(() => {
    return `Transaction ${tx.id} processed at ${tx.timestamp}`;
  });
  return tx;
}

const server = http.createServer((req, res) => {
  const id = Math.random().toString();
  const opts = Math.random() > 0.5 ? { flag: true } : null;
  const result = recordTransaction(id, 100, opts);
  
  // Simulasi Payload Serialization
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(result));
});

server.listen(4000);
```

#### Tugas Anda:
1. **Lakukan Profiling Formal**:
   * Jalankan server dengan flag `--prof` dan lakukan load testing menggunakan perkakas stress-test (seperti `autocannon` atau `k6`) selama 30 detik ($c=50$).
   * Ekstrak file log V8 menjadi format teks menggunakan `--prof-process` dan identifikasi alokasi CPU hot-spot.
2. **Rekayasa Ulang Kode**:
   * Eliminasi *Shape Morphing* pada fungsi `recordTransaction` dengan memastikan instansiasi objek memiliki Hidden Class layout yang seragam (*Monomorphic*).
   * Bersihkan kebocoran memori pada `transactionCache` (ganti dengan fixed-size circular buffer atau gunakan streaming pattern tanpa retain closure).
3. **Instrumentasi Telemetri**:
   * Pasang `monitorEventLoopDelay` dari `node:perf_hooks`.
   * Implementasikan endpoint `/metrics` yang menyajikan output $p50, p95, p99$ Event Loop Delay serta status Event Loop Utilization (ELU).
4. **Verifikasi Hasil Optimasi**:
   * Buktikan melalui perbandingan benchmark bahwa $p99$ Event Loop Delay berhasil ditekan di bawah $10\text{ ms}$ pada beban traffic yang sama.
   * Pastikan konsumsi Heap Memory tetap datar (*flat*) setelah 100.000 request selesai diproses.