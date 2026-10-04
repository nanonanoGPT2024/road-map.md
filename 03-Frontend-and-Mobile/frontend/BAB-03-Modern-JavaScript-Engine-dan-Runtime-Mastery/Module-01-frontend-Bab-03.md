# Kurikulum Rekayasa Perangkat Lunak: Jalur Frontend & Mobile
## Kategori: 03-Frontend-and-Mobile
### Bab 03 — Advanced Core JavaScript Engineering

---

# SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** `FE-M03-01`
* **Judul Modul:** *Modern JavaScript Engine & Runtime Mastery*
* **Tingkat Kompleksitas:** *Advanced / Staff Engineer Level*
* **Estimasi Waktu Belajar:** 14 Jam Kerja Terfokus (Termasuk Praktikum Deep-Dive Profiling)
* **Prasyarat Pengetahuan:**
  * Pemahaman mendalam tentang ECMAScript 2022+ (Lexical Scope, Closures, Promises, Proxies).
  * Arsitektur sistem operasi dasar (Virtual Memory, Registers, Threading, L1/L2/L3 CPU Caches).
  * Dasar-dasar algoritma dan struktur data (Graph Traversal, Hash Maps, Doubly Linked Lists).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta pembelajaran diharapkan mampu:
1. **Mengurai Pipeline Kompilasi V8/SpiderMonkey/JavaScriptCore:** Menganalisis transformasi source code dari Lexing/Parsing (AST) ke bytecode interpretation (Ignition) hingga JIT machine code generation (TurboFan/Sparkplug).
2. **Mengoptimalkan Representasi Objek Tingkat Rendah:** Memanipulasi layout memori objek JavaScript melalui *Hidden Classes (Shapes/Maps)* dan *Inline Caches (IC)* guna meminimalkan deoptimisasi (*bailouts*).
3. **Menguasai Manajemen Memori Engine:** Menganalisis siklus hidup alokasi heap, generational garbage collection (*Scavenge/Minor GC* vs *Mark-Sweep-Compact/Major GC*), serta mendeteksi dan menyelesaikan kebocoran memori menggunakan memory heap snapshots.
4. **Mendominasi Runtime Asinkron:** Merekayasa orkestrasi asinkron presisi tinggi dengan memetakan interaksi antara *Microtask Queue*, *Macrotask Queue*, *Render Steps*, serta threading platform web (*Worker Threads*, *Worklets*, dan *Atomics/SharedArrayBuffer*).
5. **Menerapkan Profiling Berbasis Low-Level Tracing:** Mengidentifikasi bottlenecks kinerja rendering dan komputasi runtime menggunakan platform tracing native seperti V8 Tick Profiler, `perf`, dan Chrome Tracing (`chrome://tracing`).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Abstraksi Ilusi JavaScript vs Realitas Mesin
Mayoritas pengembang mengonseptualisasikan JavaScript sebagai bahasa interpreted yang lambat, dinamis tanpa tipe, dan beroperasi di atas abstraksi tunggal bernama "single-threaded". Ini adalah model mental yang keliru dan berbahaya dalam rekayasa aplikasi berskala enterprise.

```
       ILUSI PENGEMBANG:
       [ Kode JS Dinamis ] ---> ( Browser Magic / "Interpreted" ) ---> Eksekusi Cepat
       
       REALITAS MESIN:
       [ Source Code ] 
              │
              ▼
       [ Parsing: Stream -> Tokens -> Abstract Syntax Tree (AST) ]
              │
              ▼
       [ Bytecode Generation (Ignition Engine) ]
              │
              ├─── Feedback Vector (Type Profiling: Monomorphic/Polymorphic)
              │           │
              ▼           ▼
       [ Tier-Up JIT Compiler (Sparkplug -> TurboFan) ]
              │           │
              │     (Speculative Optimization via Shapes/Hidden Classes)
              │           │
              ▼           ▼
       [ Native Machine Code (x86-64 / ARM64 Assembly) ]
              │
              └─── BILA ASUMSI TIPE DILANGGAR ───> [ DEOPTIMIZATION / BAILOUT ]
```

### Paradigma: "Code for the JIT, Not Just the Human"
Ketika Anda menulis kode JavaScript, Anda tidak hanya menulis instruksi logika bisnis; Anda menulis blueprint yang akan dipelajari oleh Just-In-Time (JIT) Profiler. 
1. **Objek Bukanlah Hash Map Murni di Memori:** Engine seperti V8 tidak menyimpan properti objek secara dinamis dalam map `O(1)` standar. Engine merekayasa struktur C++ statis (*Shapes* atau *Hidden Classes*) di balik layar. Mengubah urutan inisialisasi properti merusak struktur bentuk ini, melipatgandakan waktu akses karena deoptimisasi cache.
2. **CPU Menyukai Prediktabilitas:** Pola data monomorfik memungkinkan runtime mengeksekusi instruksi perakitan mesin (*inlined direct assembly calls*). Pola data megamorfik memaksa engine melakukan lookup tabel hash yang lambat, membuang siklus CPU dan menghancurkan cache L1/L2.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram komprehensif arsitektur mesin JavaScript V8 modern (Chrome/Node.js), yang mengilustrasikan alur eksekusi dari teks skrip mentah hingga kode mesin native, serta korelasinya dengan Event Loop runtime.

```
+─────────────────────────────────────────────────────────────────────────────────────────+
│                                V8 JIT COMPILATION PIPELINE                              │
│                                                                                         │
│  [Source Code]                                                                          │
│         │                                                                               │
│         ▼                                                                               │
│  +──────────────+      +──────────────+                                                 │
│  │ Scanner/Lexer│ ───> │ Parser (AST) │                                                 │
│  +──────────────+      +──────────────+                                                 │
│                               │                                                         │
│                               ▼                                                         │
│                      +──────────────────+                                               │
│                      │ Ignition Compiler│ <── [Bytecode Generator]                      │
│                      +──────────────────+                                               │
│                               │                                                         │
│                     ┌─────────┴─────────┐                                               │
│                     │                   ▼                                               │
│                     │          +──────────────────+                                     │
│                     │          │ Bytecode Stream  │ ───> Executed by Interpreter        │
│                     │          +──────────────────+                                     │
│                     │                   │                                               │
│                     │                   ▼                                               │
│                     │          +──────────────────+                                     │
│                     │          │ Feedback Vector  │ (Type feedback collected)           │
│                     │          +──────────────────+                                     │
│                     ▼                   │                                               │
│            +──────────────────+         │                                               │
│            │ Sparkplug (Fast) │         ▼                                               │
│            +──────────────────+   [ Is Hot & Stable? ]                                  │
│                     │                   │                                               │
│                     │                   ├─── YES ───> +─────────────────────────+       │
│                     │                   │             │ TurboFan (Optimizing)   │       │
│                     │                   │             +─────────────────────────+       │
│                     │                   │                          │                    │
│                     │                   │                          ▼                    │
│                     │                   │             +─────────────────────────+       │
│                     │                   │             │ Optimized Machine Code  │       │
│                     ▼                   │             +─────────────────────────+       │
│            +──────────────────+         │                          │                    │
│            │ Machine Execution│ <───────┘                          │                    │
│            +──────────────────+                                    │                    │
│                     ▲                                              │                    │
│                     │ (Bailout/Deopt)                              │                    │
│                     └──────────────────────────────────────────────┘                    │
│                          (Type mismatch triggered at runtime)                           │
+─────────────────────────────────────────────────────────────────────────────────────────+

+─────────────────────────────────────────────────────────────────────────────────────────+
│                       RUNTIME EVENT LOOP & CONCURRENCY MODEL                            │
│                                                                                         │
│   +─────────────────────────────+           +────────────────────────────────────────+  │
│   │        CALL STACK           │           │             MEMORY HEAP                │  │
│   │ [frame: renderChart()     ] │           │  +──────────────────────────────────+  │  │
│   │ [frame: calculateOffsets()] │           │  │ Young Gen (Nursery & Intermediate│  │  │
│   │ [frame: anonymous()       ] │           │  +──────────────────────────────────+  │  │
│   +─────────────────────────────+           │  │ Old Gen (Mark-Sweep-Compact)     │  │  │
│                  ▲                          │  +──────────────────────────────────+  │  │
│                  │                          +────────────────────────────────────────+  │
│                  │ (Pushes execution frames)                                            │
│                  │                                                                      │
│    ┌─────────────┴─────────────┐                                                        │
│    │     EVENT LOOP ENGINE     │                                                        │
│    └─────────────┬─────────────┘                                                        │
│                  │                                                                      │
│        Phase Check Routine:                                                             │
│        1. Run Callstack until empty                                                     │
│        2. Drain ALL Microtasks until completely empty                                   │
│        3. Check Render Pipeline opportunities (RAF -> Style -> Layout -> Paint)         │
│        4. Pick ONE Macrotask, execute, return to step 1                                 │
│                  │                                                                      │
│        ┌─────────┴──────────────┬────────────────────────┬───────────────────────┐      │
│        ▼                        ▼                        ▼                       ▼      │
│  +───────────────+      +───────────────+        +───────────────+       +────────────+ │
│  │  Microtasks   │      │ Render Steps  │        │  Macrotasks   │       │ Background │ │
│  ├───────────────┤      ├───────────────┤        ├───────────────┤       ├────────────┤ │
│  │ Promise Jobs  │      │ RAF Callbacks │        │ setTimeout    │       │ Web Worker │ │
│  │ MutationObs.  │      │ Style Calc    │        │ setInterval   │       │ Worklets   │ │
│  │ queueMicrotask│      │ Layout/Paint  │        │ I/O / Events  │       │ I/O Thread │ │
│  +───────────────+      +───────────────+        +───────────────+       +────────────+ │
+─────────────────────────────────────────────────────────────────────────────────────────+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Hidden Classes (Shapes / Maps)
V8 mengasumsikan properti objek disimpan pada indeks memori tertentu relatif terhadap basis pointer objek. Untuk mewujudkan hal ini tanpa static type declarations, V8 membuat transisi internal:

* **Initial State:** Objek `{}` dibuat. V8 mengasosiasikan objek ini dengan *Shape C0*.
* **Property Addition:** Saat `this.x = 5` dieksekusi, V8 memindahkan objek dari *Shape C0* ke *Shape C1*. Transisi ini mencatat: *Property 'x' disimpan di In-Object Offset 0*.
* **Subsequent Addition:** Saat `this.y = 10` dieksekusi, V8 memindahkan objek dari *Shape C1* ke *Shape C2*. Transisi ini mencatat: *Property 'y' disimpan di In-Object Offset 1*.

Jika objek kedua dibuat dengan urutan `this.y = 10; this.x = 5;`, jalur transisinya bercabang menjadi `C0 -> C3 -> C4`. Objek 1 dan Objek 2 kini memiliki Hidden Class yang berbeda!

### 2. Inline Caching (IC)
Inline Cache bertindak sebagai memori lokal dari suatu fungsi untuk menghindari lookup properti melalui traversal prototype chain atau hash map:
* **Monomorphic IC:** Lokasi pemanggilan (*call site*) hanya pernah melihat 1 Shape. Engine mengompilasi akses langsung: `return object_ptr + offset`. Eksekusi terjadi dalam 1 siklus CPU.
* **Polymorphic IC:** Call site melihat antara 2 hingga 4 Shapes berbeda. Engine memvalidasi bentuk menggunakan switch-table internal:
  ```c
  if (shape == Shape1) return ptr + offset1;
  else if (shape == Shape2) return ptr + offset2;
  ```
* **Megamorphic IC:** Call site melihat lebih dari 4 Shapes berbeda. Engine menyerah untuk melakukan inline, fallback ke runtime global dictionary lookup yang memakan waktu drastis.

### 3. V8 Generational Garbage Collector (Orinoco Project)
V8 membagi memori menjadi dua generasi utama berdasarkan hipotesis bahwa sebagian besar objek mati saat masih sangat muda (*Weak Generational Hypothesis*):
* **Young Generation (1MB - 64MB):**
  * Dibagi menjadi *Nursery* dan *Intermediate* (dua semi-spaces: *From-Space* dan *To-Space*).
  * Menggunakan algoritma **Scavenger (Cheney's Copying Algorithm)**: Objek hidup disalin ke To-Space; pointer diperbarui; From-Space dibersihkan seluruhnya dalam hitungan milidetik. Objek yang bertahan dalam 2 siklus Scavenge dipromosikan ke Old Generation.
* **Old Generation:**
  * Berisi objek yang berumur panjang.
  * Menggunakan **Mark-Sweep-Compact**:
    1. *Marking:* Mengidentifikasi objek hidup dengan menelusuri pointer dari root graph (Tri-color marking: Putih, Abu-abu, Hitam).
    2. *Sweeping:* Menambahkan pointer memori mati ke *Free Lists*.
    3. *Compacting:* Menggeser memori hidup untuk mencegah fragmentasi heap. V8 mengeksekusinya secara paralel, konkuren (*background threads*), dan inkremental untuk menghindari UI frame dropping.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Bytecode Execution vs Native JIT Tiering
Mesin V8 mengeksekusi kode melalui tahapan bertingkat (*Tiering Pipeline*):

```
JavaScript Code
      │
      ▼
Parser (AST)
      │
      ▼
Ignition Bytecode Interpreter (Memori rendah, startup instan)
      │
      ├───────────────────────────────┐
      │ (Setelah beberapa pemanggilan)│
      ▼                               ▼
Sparkplug Compiler              TurboFan Optimizing Compiler
(Direct Bytecode-to-Machine)    (Spekulatif, Sea-of-Nodes Graph IR)
```

1. **Ignition (Bytecode Interpreter):** Menghasilkan bytecode kompak. Mesin register-based di mana akumulator menyimpan nilai operasi terkini.
2. **Sparkplug:** Mengompilasi bytecode secara langsung ke kode mesin native tanpa optimasi kompleks. Tidak melakukan type feedback compilation; hanya mentranslasikan instruksi bytecode langsung ke instruksi CPU assembly untuk meningkatkan kecepatan eksekusi 2-3x tanpa latency overhead compiler yang berat.
3. **TurboFan:** Membaca *Feedback Vector* yang diakumulasikan oleh Ignition. Jika suatu fungsi sering dipanggil (*hot*) dan tipe data parameternya stabil, TurboFan membangun *Sea-of-Nodes Intermediate Representation (IR)*. Ia melakukan:
   * *Type Specialization* (misalnya mengubah operasi `+` menjadi instruksi assembler tunggal `ADD`).
   * *Function Inlining* (menghilangkan overhead pemanggilan fungsi dengan menempelkan langsung isi fungsi ke call site).
   * *Loop Unrolling* dan *Escape Analysis* (mengalokasikan objek langsung di CPU Registers/Stack bukan di Garbage-Collected Heap).

### The Peril of Deoptimization (Bailout)
Ketika TurboFan mengasumsikan parameter `x` selalu bernilai integer, lalu tiba-tiba string dimasukkan ke dalam fungsi tersebut:
1. Pengecekan guard di level instruksi CPU mendeteksi ketidaksesuaian tipe (*type mismatch*).
2. Engine mengeksekusi **Deopt**: Menghancurkan optimized machine code.
3. Rekonstruksi Call Frame: Keadaan stack dikembalikan secara paksa ke format yang dapat dibaca oleh Ignition interpreter.
4. Fungsi ditandai "deoptimized", memaksa runtime berjalan pada interpreter yang lambat hingga feedback stabil kembali.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode pengujian yang dirancang untuk mendemonstrasikan perubahan Hidden Class dan degradasi status Inline Cache dari Monomorphic menjadi Megamorphic.

```javascript
/**
 * fundamental-engine-test.js
 * Demonstrasi transisi Hidden Class & Status Inline Cache
 * Jalankan dengan flag V8 di terminal Node.js:
 * node --allow-natives-syntax fundamental-engine-test.js
 */

// 1. Definisi Konstruktor Berurutan Konsisten
function VectorMonomorphic(x, y) {
  this.x = x;
  this.y = y;
}

// 2. Fungsi Pembaca Properti (Target Inline Cache)
function readCoordinates(point) {
  return point.x + point.y;
}

// Inisialisasi State Monomorfik
const pointA = new VectorMonomorphic(10, 20);
const pointB = new VectorMonomorphic(30, 40);

// Warming Up JIT Compiler
for (let i = 0; i < 10000; i++) {
  readCoordinates(pointA);
  readCoordinates(pointB);
}

// 3. Pelanggaran Hidden Class (Struktur Bentuk Tak Sesuai)
// Objek dengan struktur berbeda dan urutan properti terbalik
const pointPolymorphic = { x: 50, y: 60 };
const pointMegamorphic1 = { y: 70, x: 80 }; // Urutan terbalik = Map berbeda
const pointMegamorphic2 = { x: 90, z: 0, y: 100 };
const pointMegamorphic3 = { a: 1, x: 2, y: 3 };

// Memicu Polimorfisme
readCoordinates(pointPolymorphic);

// Memicu Megamorfisme (Lebih dari 4 variasi bentuk pada satu call site)
readCoordinates(pointMegamorphic1);
readCoordinates(pointMegamorphic2);
readCoordinates(pointMegamorphic3);

// Menambahkan properti secara dinamis (Mutasi Hidden Class di runtime)
const mutatedPoint = new VectorMonomorphic(5, 5);
// Runtime inspection internal via V8 Intrinsics (Hanya aktif jika flag --allow-natives-syntax dinyalakan)
if (typeof %HaveSameMap !== 'undefined') {
  console.log("Apakah point A & B satu map?", %HaveSameMap(pointA, pointB)); // true
  mutatedPoint.z = 99; // Bentuk berubah!
  console.log("Apakah point A & mutatedPoint satu map?", %HaveSameMap(pointA, mutatedPoint)); // false
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

| Baris / Blok | Kode Terpilih | Analisis Teknis Mesin Tingkat Rendah |
| :--- | :--- | :--- |
| **09–12** | `function VectorMonomorphic(x, y) { ... }` | Konstruktor ini membuat rantai transisi deterministik: `Map0 -> Map1(x) -> Map2(x, y)`. Semua instansiasi baru mengarah pada offset memori yang identik. |
| **15–17** | `function readCoordinates(point) { ... }` | Call site `point.x` dan `point.y` memiliki slot *Feedback Vector*. Di sinilah TurboFan mengaitkan pointer memori langsung. |
| **24–27** | `for (let i = 0; i < 10000; i++) ...` | *Warm-up Phase*. Ignition mendeteksi fungsi ini *hot*. TurboFan mengompilasi kode mesin langsung via pemetaan Monomorfik dari instance `VectorMonomorphic`. |
| **30–33** | `pointMegamorphic1 = { y: 70, x: 80 }` | Literal objek ini diinisialisasi dengan urutan kunci terbalik (`y` lalu `x`). Mesin menghasilkan struktur transisi `Map0 -> Map_Y -> Map_Y_X`. Ini **bukan** bentuk yang sama dengan `Map_X_Y`. |
| **40–42** | `readCoordinates(pointMegamorphicX)` | Call-site melebihi batas 4 Map unik. V8 mengubah status Inline Cache di Feedback Vector menjadi **MEGAMORPHIC**. TurboFan melakukan deoptimisasi fungsi, membatalkan optimasi native machine instruction. |
| **47–50** | `mutatedPoint.z = 99;` | Menambahkan properti ad-hoc ke objek mengalokasikan Hidden Class baru yang tidak terduga, mengubah In-Object Property Storage menjadi Slow-Mode Dictionary Properties jika kapasitas memori backing store terlampaui. |

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Telemetri Finansial Berfrekuensi Tinggi Mengalami Frame Freezing
* **Konteks:** Sebuah platform perdagangan ekuitas real-time menerima 5.000 pembaruan harga per detik melalui WebSockets dan memetakan data tersebut ke kanvas visualisasi DOM/WebGL.
* **Gejala:** UI browser mengalami micro-stutters (framerate anjlok dari 60fps ke 12fps secara acak setiap ~4 detik). GC Pauses di DevTools terdeteksi mencapai durasi 80ms-120ms (*Jank Threshold* > 16.6ms).
* **Akar Masalah (Root-Cause Discovery):**
  1. Parser WebSocket mengembalikan objek JSON dengan urutan *key* yang acak tergantung format kompresi backend, memicu status megamorfik pada rendering loop.
  2. Pembuatan ribuan objek kecil per batch pesan WebSocket membebani Young Generation Heap, memaksa proses Scavenger GC berjalan tanpa jeda.
  3. Pemanggilan `Promise.resolve().then(...)` yang tidak terkontrol di dalam callback pesan membanjiri *Microtask Queue*, memblokir rendering pipeline browser sepenuhnya hingga frame terlewat (*starvation*).

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Solusi arsitektur produksi: Menerapkan **Object Pooling**, menstabilkan **Hidden Classes**, dan mengimplementasikan **Microtask Budgeting/Cooperative Scheduling** berbasis frame browser.

```typescript
/**
 * Enterprise Level High-Throughput Engine-Optimized Stream Ingestion Engine
 * Menghilangkan alokasi memori GC dan menjaga stabilitas Inline Cache.
 */

// 1. Skema Memori Statis (Menjamin Bentuk / Hidden Class Tunggal yang Konstan)
export class MarketTick {
  public symbolId: number = 0;
  public price: number = 0.0;
  public volume: number = 0;
  public timestamp: number = 0;

  // Constructor menjamin inisialisasi deterministik properti pada memori internal
  constructor() {
    this.symbolId = 0;
    this.price = 0.0;
    this.volume = 0;
    this.timestamp = 0;
  }

  public reset(): void {
    this.symbolId = 0;
    this.price = 0.0;
    this.volume = 0;
    this.timestamp = 0;
  }
}

// 2. High-Performance Object Pool untuk Mencegah Alokasi Young Generation GC
export class MarketTickPool {
  private readonly pool: MarketTick[];
  private head: number;

  constructor(private readonly capacity: number) {
    this.pool = new Array<MarketTick>(capacity);
    this.head = capacity;

    // Pra-alokasi seluruh instansiasi memori di awal (Allocation Phase)
    for (let i = 0; i < capacity; i++) {
      this.pool[i] = new MarketTick();
    }
  }

  public acquire(): MarketTick | null {
    if (this.head > 0) {
      this.head--;
      return this.pool[this.head];
    }
    // Pool Exhausted: Mencegah alokasi heap tak terkendali
    return null;
  }

  public release(item: MarketTick): void {
    if (this.head < this.capacity) {
      item.reset();
      this.pool[this.head] = item;
      this.head++;
    }
  }
}

// 3. Ring Buffer & Cooperative Frame Scheduler
export class HighThroughputEngineStream {
  private readonly buffer: MarketTickPool;
  private readonly queue: MarketTick[] = [];
  private isProcessing: boolean = false;

  constructor(poolCapacity: number) {
    this.buffer = new MarketTickPool(poolCapacity);
  }

  public ingestRawTick(symbolId: number, price: number, volume: number, timestamp: number): void {
    const tick = this.buffer.acquire();
    if (!tick) {
      // Backpressure strategy: Buang atau alihkan metrics ketika buffer overload
      console.warn('[Engine Monitor] Ingestion backpressure reached: Frame Dropped');
      return;
    }

    // Mutasi in-place: Mencegah alokasi objek baru dan mempertahankan Hidden Class
    tick.symbolId = symbolId;
    tick.price = price;
    tick.volume = volume;
    tick.timestamp = timestamp;

    this.queue.push(tick);
    this.scheduleProcessing();
  }

  private scheduleProcessing(): void {
    if (this.isProcessing) return;
    this.isProcessing = true;

    // Menjadwalkan konsumsi data kooperatif di frame idle tanpa memblokir Render Steps
    if (typeof requestAnimationFrame !== 'undefined') {
      requestAnimationFrame((frameTime) => this.processBatch(frameTime));
    } else {
      // Fallback untuk runtime Node.js
      setImmediate(() => this.processBatch(Date.now()));
    }
  }

  private processBatch(deadline: number): void {
    const BUDGET_MS = 8; // Mempertahankan budget eksekusi di bawah 16.6ms untuk stabilitas 60 FPS
    const startTime = performance.now();

    while (this.queue.length > 0) {
      // Hentikan eksekusi jika microtask/batch execution mendekati budget rendering UI
      if (performance.now() - startTime > BUDGET_MS) {
        break;
      }

      const tick = this.queue.shift();
      if (!tick) break;

      // Eksekusi Logika Bisnis (TurboFan Monomorphic Call Target)
      this.processSingleTickMonomorphic(tick);

      // Kembalikan objek ke memory pool
      this.buffer.release(tick);
    }

    if (this.queue.length > 0) {
      // Masih ada data tersisa, jadwalkan batch berikutnya di frame berikutnya
      if (typeof requestAnimationFrame !== 'undefined') {
        requestAnimationFrame((frameTime) => this.processBatch(frameTime));
      } else {
        setImmediate(() => this.processBatch(Date.now()));
      }
    } else {
      this.isProcessing = false;
    }
  }

  // JIT Monomorphic Optimization Target:
  // Bentuk parameter 'tick' 100% konsisten, dieksekusi via direct assembly instruction
  private processSingleTickMonomorphic(tick: MarketTick): void {
    // Simulasi kalkulasi: Komputasi numerik murni tanpa alokasi string atau dynamic lookup
    const totalVolumeValue = tick.price * tick.volume;
    if (totalVolumeValue > 1000000) {
      // Aksi alert tingkat tinggi
    }
  }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

```
              MATRIKS TRADE-OFF: STRATEGI EKSEKUSI JAVASCRIPT
┌─────────────────────────┬──────────────────────────┬──────────────────────────┐
│ Pendekatan Rekayasa     │ Keuntungan (Pros)        │ Kerugian/Biaya (Cons)    │
├─────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Object Pooling &        │ - GC pressure mendekati  │ - Kode sangat verbose.   │
│ In-place Mutation       │   0ms.                   │ - Rawan pointer reuse bugs│
│                         │ - Monomorphic status     │   (state leakage).       │
│                         │   terjaga sempurna.      │ - Memakan memori flat di │
│                         │ - Menghilangkan lag UI.  │   awal (RAM overhead).   │
├─────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Idiomatic Functional JS │ - Sangat deklaratif dan  │ - Alokasi memory garbage │
│ (Object spread, immut-  │   mudah dibaca tim.      │   tinggi di Young Gen.   │
│ ability, map/filter)    │ - Mencegah mutasi state  │ - Deoptimisasi IC akibat │
│                         │   yang tidak terduga.    │   perubahan bentuk obj.  │
│                         │ - Zero setup boilerplate.│ - GC pauses berkala.     │
├─────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Microtask Scheduling    │ - Eksekusi tercepat      │ - Rawan membekukan UI    │
│ (queueMicrotask,        │   sebelum paint step.    │   (*Event Loop starving*)│
│  Promise chaining)      │ - Menjamin atomic updates│   jika recursive / batch │
│                         │   dalam satu tick.       │   terlalu besar.         │
├─────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Cooperative Scheduling  │ - UI tetap responsif     │ - Latensi throughput:    │
│ (requestAnimationFrame, │   pada 60/120 FPS.       │   Data mengalami jeda    │
│  scheduler.yield)       │ - Prediktabilitas tinggi.│   sampai frame berikutnya│
│                         │ - Ramah baterai device.  │   tersedia.              │
└─────────────────────────┴──────────────────────────┴──────────────────────────┘
```

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Microtask Starvation Deadlock
Jika Anda memicu rekursi Microtask secara berkelanjutan, browser **tidak akan pernah** merender UI atau memproses event sentuhan pengguna:

```javascript
// CONTOH DEADLOCK MEMATIKAN
function starveEventLoop() {
  Promise.resolve().then(() => {
    // Microtask Queue tidak pernah kosong!
    // Render Step, Web API, dan Timer Macrotask terblokir selamanya.
    starveEventLoop();
  });
}
```
*Mitigasi:* Gunakan `scheduler.yield()` (jika didukung) atau pecah siklus menggunakan `setTimeout(fn, 0)` atau `requestAnimationFrame` untuk memberikan ruang bagi Compositor Thread mengeksekusi repainting.

### 2. Transition Tree Explosion (Hidden Class Leak)
Menambahkan properti kondisional secara sembarangan:
```javascript
const user = {};
if (isAdmin) user.adminRole = 'ALL';
if (isBeta) user.betaFlag = true;
// Menghasilkan 4 permutasi Hidden Class yang berbeda!
// Jika ada 10 properti kondisional: 2^10 = 1024 variasi Shape di memori!
```
*Mitigasi:* Inisialisasi seluruh properti yang mungkin ada di konstruktor dengan nilai awal eksplisit: `null` atau `undefined`.

### 3. V8 Array Smi (Small Integer) Transition Hazzard
Array di V8 memiliki representasi internal:
* `PACKED_SMI_ELEMENTS`: Array padat hanya berisi small integers (paling cepat).
* `PACKED_DOUBLE_ELEMENTS`: Array padat berisi float.
* `PACKED_ELEMENTS`: Array padat berisi referensi objek/string.
* `HOLEY_*`: Array yang memiliki celah (*holes*) akibat indeks dilewati (`arr[100] = 1`).

**Catatan:** Transisi tipe array hanya berjalan satu arah. Jika sebuah array berubah dari `PACKED_SMI` ke `PACKED_ELEMENTS`, ia tidak akan pernah bisa kembali ke mode hemat memory `PACKED_SMI`!

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Menggunakan Operasi `delete` pada Objek Hot-Path
```javascript
// SALAH: Mengubah objek seketika menjadi Slow-Mode Dictionary Properties!
const config = { host: 'localhost', port: 8080 };
delete config.port; // V8 membuang Shape C++ dan mengubah config menjadi hash map lambat!

// BENAR: Pertahankan stabilitas bentuk dengan menetapkan null atau undefined
config.port = null; // Shape tetap identik, Inline Cache tetap bekerja
```

### Kesalahan 2: Menyimpan Objek Berbeda Urutan dalam Pipeline
```javascript
// SALAH: Objek hasil mapping memiliki bentuk yang divergen
const itemA = { id: 1, name: 'A' };
const itemB = { name: 'B', id: 2 }; // URUTAN BERBEDA = SHAPE BERBEDA

// BENAR: Gunakan factory method atau class terstandarisasi
class Item {
  constructor(id, name) {
    this.id = id;
    this.name = name;
  }
}
const itemA = new Item(1, 'A');
const itemB = new Item(2, 'B'); // Bentuk 100% identik
```

### Kesalahan 3: Asumsi bahwa `setTimeout(fn, 0)` Langsung Berjalan
`setTimeout(fn, 0)` memiliki spesifikasi standar penundaan minimum ~4ms (jika bersarang > 5 tingkat) dan merupakan *Macrotask*. Ia harus menunggu seluruh Microtask yang ada di antrean tuntas dikuras, berpotensi tertunda jauh melampaui 0ms.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Deterministic Object Layout:** Selalu inisialisasi properti objek di konstruktor, dalam urutan identik, dengan tipe data awal yang stabil.
2. **Prevent Sparse Arrays (Holey Arrays):** Hindari alokasi array dengan `new Array(size)`. Inisialisasi dengan `Array.from()` atau isi secara sequential tanpa melompati indeks.
3. **Budgeted Frame Execution:** Alokasikan pemrosesan komputasi runtime maksimal 10ms dari 16.6ms frame budget browser, sisakan 6.6ms untuk Style Calculation, Layout, Paint, dan Composite.
4. **Prefer Web Workers for Heavy Computation:** Pindahkan kalkulasi berat non-DOM (kriptografi, parsing file besar) ke Web Workers terisolasi guna menjaga kelancaran respons UI thread.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Benchmark Memory Footprint: Monomorphic vs Polymorphic Invalidation
Menjalankan loop komputasi 1.000.000 iterasi dengan call site Monomorfik vs Megamorfik menunjukkan perbedaan performa yang masif:

```
+───────────────────────────┬───────────────────┬───────────────────────+
| Metrik Pengukuran         | Monomorphic Code  | Megamorphic Code      |
+───────────────────────────┼───────────────────┼───────────────────────+
| Waktu Eksekusi (CPU Time) | 1.84 ms           | 28.62 ms (15.5x drop) |
| JIT Compilation Tier      | TurboFan (Native) | Deoptimized/Ignition  |
| L1 Data Cache Misses      | < 0.05%           | 14.2%                 |
| Alokasi Memory Heap       | 0 Bytes (Stack)   | Megamorphic Dictionary|
+───────────────────────────┴───────────────────┴────────────────