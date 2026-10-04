# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bagian dari:** BAB 01 — Fondasi dan Arsitektur JavaScript Engine & Runtime

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
*   **Menganalisis dan Membedah** siklus hidup kompilasi V8 Engine (*Ignition bytecode generation* dan *TurboFan optimization/deoptimization*) untuk mencegah terjadinya *bailout* dan degradasi performa eksekusi.
*   **Mengontrol dan Mengoptimalkan** memori heap V8 melalui pemahaman mendalam tentang *Generational Garbage Collection* (Scavenge, Mark-Sweep-Compact), mitigasi kebocoran memori (*memory leak*), serta penggunaan `WeakRef` dan `FinalizationRegistry`.
*   **Membangun Pola Konkurensi Skala Enterprise** dengan mengorkestrasi *Event Loop*, microtasks queue, macrotasks queue, serta *Worker Threads* dengan `SharedArrayBuffer` dan `Atomics` untuk beban kerja CPU-bound.
*   **Mendiagnosis Masalah Latensi dan Memory Pressure** pada lingkungan produksi Node.js menggunakan heap snapshot, CPU profiling, dan *Event Loop Delay metrics*.

---

## 2. Prerequisites
Sebelum mempelajari modul ini, engineer wajib menguasai:
*   Mekanisme dasar JavaScript: Prototype chain, Closures, Scoping, dan ES6+ syntax.
*   Konsep dasar pemrograman asinkron: Callbacks, Promises, dan `async/await`.
*   Dasar arsitektur sistem operasi: Thread, Process, Virtual Memory, Stack vs Heap.
*   Penggunaan dasar CLI, Node.js runtime (v18.x LTS atau v20.x LTS), dan package manager (npm/pnpm).

---

## 3. Concept & Internal Architecture

Arsitektur runtime JavaScript enterprise (khususnya V8 Engine yang menenagai Node.js dan Chromium) beroperasi jauh melampaui paradigma interpreter tradisional.

```
+-----------------------------------------------------------------------------------+
|                                     V8 ENGINE                                     |
|                                                                                   |
|  Source Code ---> [ Parser / AST ] ---> [ Ignition Interpreter ] ---> Bytecode    |
|                                                  |                                |
|                                         (Feedback Vector)                         |
|                                                  |                                |
|                                                  v                                |
|                                       [ TurboFan Compiler ]                       |
|                                                  |                                |
|                                                  +---> Optimized Machine Code     |
|                                                  |     (Bailout if Deopt!)        |
|                                                  v                                |
|                                             Machine Code                          |
+-----------------------------------------------------------------------------------+
```

### 3.1. Pipeline Kompilasi V8: Parser, Ignition, dan TurboFan
1.  **Parsing & AST:** Source code diubah menjadi Abstract Syntax Tree (AST) melalui dua fase: *Pre-parser* (hanya memverifikasi sintaks fungsi yang belum dieksekusi secara instan) dan *Full Parser* (menghasilkan AST lengkap).
2.  **Ignition (Interpreter):** Mengubah AST menjadi register-based bytecode yang ringkas. Ignition mengumpulkan informasi profil (*type feedback vector*) selama eksekusi awal.
3.  **TurboFan (Optimizing Compiler):** Ketika suatu fungsi berstatus *Hot* (dipanggil berulang kali dengan tipe data yang stabil/monomorfik), TurboFan mengompilasi bytecode tersebut langsung menjadi arsitektur instruksi mesin spesifik (x86_64, ARM64).
4.  **Deoptimization (Bailout):** Jika fungsi teroptimasi tiba-tiba menerima tipe data yang berbeda (*polymorphic* atau *megamorphic*), TurboFan membatalkan optimasi, membuang kode mesin teroptimasi, dan mengembalikan kontrol ke Ignition melalui proses *deopt*, yang memicu lonjakan CPU (*latency spike*).

### 3.2. Hidden Classes (Shapes) & Inline Caching (IC)
JavaScript adalah bahasa dinamis berbasis prototipe tanpa definisi layout memori statis. Untuk menyamai performa bahasa terkompilasi, V8 menggunakan representasi internal bernama **Hidden Classes** (sering disebut *Shapes* atau *Maps*).

```
Object Instance { x: 10, y: 20 }
[ Map Pointer ] -----> Map 1 (Offset 0: 'x')
                           |
                     (Transition 'y')
                           v
                        Map 2 (Offset 0: 'x', Offset 8: 'y')
```

*   **Shape Transitions:** Saat properti ditambahkan ke object, pointer class internal bertransisi dari satu Shape ke Shape baru. Inisialisasi properti dengan urutan berbeda pada tipe object yang sama akan menghasilkan cabang Shape yang berbeda.
*   **Inline Caching (IC):** V8 menyimpan cache lokasi offset memori dari pemanggilan properti berdasarkan Shape objek tersebut.
    *   *Monomorphic:* IC hanya melihat 1 Shape (paling optimal, dieksekusi via inlined assembly).
    *   *Polymorphic:* IC menangani 2 hingga 4 Shape berbeda.
    *   *Megamorphic:* IC menangani > 4 Shape berbeda (fallback ke hash table lookup, performa menurun drastis).

### 3.3. Struktur Heap Memory V8 & Garbage Collection (GC)
Memori heap V8 terbagi menjadi beberapa *Spaces*:
*   **New Space (Nursery & Intermediate):** Tempat object baru dialokasikan. Diatur oleh algoritma GC minor bernama **Scavenger (Cheney's algorithm)**. Sangat cepat, membagi memori menjadi dua semi-space (*From Space* dan *To Space*).
*   **Old Pointer Space:** Menyimpan object yang lolos dari dua kali siklus Scavenger dan mengandung pointer ke object lain.
*   **Old Data Space:** Menyimpan data mentah tanpa referensi pointer ke heap lain (string mentah, raw boxed numbers).
*   **Large Object Space:** Alokasi untuk object yang ukurannya melebihi batas alokasi reguler; tidak pernah dipindahkan oleh GC.
*   **Code Space:** Menyimpan *JIT-compiled code blocks*.

**Major GC (Mark-Sweep-Compact / Orinoco):**
Menggunakan model *tri-color marking* (White, Grey, Black). Orinoco menjalankan GC secara konkuren (*background threads*) dan inkremental untuk meminimalkan *Stop-The-World* (STW) pause time pada main thread.

---

## 4. Why & What

| Dimensi | Mengapa Relevan bagi Enterprise? | Apa yang Harus Diimplementasikan? |
| :--- | :--- | :--- |
| **Throughput & Latency** | Deoptimasi V8 dan manipulasi objek dinamis memicu lonjakan latensi (P99/P999) pada microservices berbeban tinggi. | Pertahankan konsistensi *object shape* (monomorfik), hindari mutasi objek instan (`delete`, dynamic property injection). |
| **Resource Efficiency** | Kebocoran memori (leak) yang tidak terdeteksi memicu *OutOfMemory (OOM)* pada orkestrasi container (Kubernetes Pod crashing). | Terapkan *weak references* (`WeakMap`, `WeakSet`, `WeakRef`), profiling heap berkala, serta isolasi lifecycle data. |
| **CPU-Bound Scalability** | Event Loop bersifat single-threaded; komputasi berat (kriptografi, parsing data masif) membekukan pemrosesan I/O server. | Offload komputasi intensif ke *Worker Threads* dengan zero-copy data passing melalui `SharedArrayBuffer` dan sinkronisasi thread via `Atomics`. |

---

## 5. How: Workflow Detail Rekayasa Performa

### 5.1. Alur Kerja Menjaga Stabilitas TurboFan (Monomorphism)
1.  Inisialisasi semua properti object secara konsisten di dalam *Constructor* atau *Factory Function*.
2.  Jangan pernah mengubah urutan inisialisasi properti antar instance objek sejenis.
3.  Hindari operator `delete` karena secara paksa mengubah Shape menjadi *Dictionary Mode* (hash-table lookup lambat). Sebagai gantinya, set nilai properti ke `undefined` atau gunakan object baru.

### 5.2. Alur Eksekusi Konkurensi & Event Loop Node.js
```
+-------------------------------------------------------+
|                   Main Event Loop                     |
|                                                       |
|  [Timers] ---> [Pending I/O] ---> [Poll] ---> [Check] |
|     ^                                            |    |
|     |                                            v    |
|     +------------------ [Close Callbacks] <------+    |
+-------------------------------------------------------+
      *Microtasks (process.nextTick, Promise Jobs)*
      dieksekusi SETELAH setiap fase dan antar-callback!
```
1.  **Fase Timers:** Mengeksekusi callback dari `setTimeout` dan `setInterval`.
2.  **Fase Pending Callbacks:** Mengeksekusi callback I/O yang tertunda dari iterasi sebelumnya.
3.  **Fase Poll:** Mengambil event I/O baru. Jika queue kosong, loop akan memblokir dan menunggu koneksi/data masuk hingga timer tercapai.
4.  **Fase Check:** Mengeksekusi callback yang didaftarkan secara eksplisit oleh `setImmediate`.
5.  **Microtask Drain:** Setiap kali V8 menyelesaikan satu callback di fase manapun, seluruh queue Microtask (`process.nextTick` didahulukan, disusul Promise microtasks) harus dikosongkan hingga zero sebelum beralih ke tugas berikutnya.

---

## 6. Analogy & Diagram ASCII

### 6.1. Analogi: Jalur Pabrik Perakitan Mobil (V8 Engine Pipeline)
*   **Ignition:** Perakitan manual menggunakan tangan. Cepat untuk memulai produksi batch pertama, namun kecepatan perakitan per unit tetap rendah.
*   **TurboFan:** Membangun robot perakitan kustom khusus untuk satu jenis mobil sedan hitam beroda empat. Begitu robot aktif, mobil dirakit dengan kecepatan supersonik.
*   **Deoptimization (Bailout):** Pabrik tiba-tiba memasukkan truk roda enam ke jalur perakitan sedan tersebut. Sensor robot eror, mesin berhenti mendadak (*STW pause*), robot dibongkar paksa, dan mobil dikembalikan ke perakitan manual Ignition.

### 6.2. Diagram Tri-Color Marking (Orinoco Garbage Collection)

```
        ROOT OBJECTS (Global Scope, Active Stack Frames)
                           |
                           v
                     [ BLACK OBJECT ]  (Visited & all references analyzed)
                      /            \
                     v              v
     [ GREY OBJECT ]                  [ WHITE OBJECT ]
     (Discovered, but                 (Unvisited, candidate
      children pending scan)           for deletion)
            |
            v
     [ WHITE OBJECT ]  <--- Unreachable, will be swept!
```

---

## 7. Simple & Practical Examples

### 7.1. Simple Example: Demonstrasi Hidden Class & Monomorphism
Contoh ini mendemonstrasikan bagaimana konstruksi objek yang salah memicu bifurkasi *Hidden Class* (Shape).

```javascript
/**
 * Pola Buruk: Memicu Pembuatan Dua Shape Berbeda
 */
function createBadCoordinates(x, y, invert) {
  const point = {};
  if (invert) {
    point.y = y; // Transisi: Map0 -> Map1 (y)
    point.x = x; // Transisi: Map1 -> Map2 (y, x)
  } else {
    point.x = x; // Transisi: Map0 -> Map3 (x)
    point.y = y; // Transisi: Map3 -> Map4 (x, y)
  }
  return point; // Dua tipe objek dengan shape berbeda dikembalikan!
}

/**
 * Pola Rekayasa Produksi: Stabil & Monomorfik
 */
class OptimizedCoordinate {
  /**
   * Properti selalu diinisialisasi pada urutan yang identik
   * @param {number} x 
   * @param {number} y 
   */
  constructor(x, y) {
    this.x = x;
    this.y = y;
  }
}

// TurboFan dapat mengoptimasi fungsi ini secara instan
function computeManhattanDistance(pointA, pointB) {
  return Math.abs(pointA.x - pointB.x) + Math.abs(pointA.y - pointB.y);
}
```

### 7.2. Practical Example: Cache In-Memory Anti-Memory Leak dengan `WeakRef` & `FinalizationRegistry`
Implementasi cache memori enterprise yang memungkinkan GC merebut memori secara transparan ketika tekanan memori terjadi, menghindari kebocoran memori pada objek besar.

```javascript
// memory-manager.mjs
import { performance } from 'node:perf_hooks';

/**
 * @template K, V
 * Cache canggih berbasis WeakRef yang aman terhadap OOM.
 */
export class AutoPurgingCache {
  /** @type {Map<K, WeakRef<V & object>>} */
  #cache = new Map();
  /** @type {FinalizationRegistry<K>} */
  #registry;

  constructor() {
    this.#registry = new FinalizationRegistry((key) => {
      // Dijalankan secara asinkron oleh runtime ketika target object di-GC
      const ref = this.#cache.get(key);
      if (ref && ref.deref() === undefined) {
        this.#cache.delete(key);
      }
    });
  }

  /**
   * Menyimpan objek ke cache tanpa mencegah proses Garbage Collection
   * @param {K} key
   * @param {V & object} value
   */
  set(key, value) {
    if (typeof value !== 'object' || value === null) {
      throw new TypeError('AutoPurgingCache hanya menerima payload berupa object.');
    }
    
    // Simpan weak reference
    this.#cache.set(key, new WeakRef(value));
    
    // Daftarkan ke finalization registry untuk membersihkan dead keys dari Map
    this.#registry.register(value, key, key);
  }

  /**
   * Mengambil objek dari cache jika belum disapu oleh GC
   * @param {K} key
   * @returns {V | null}
   */
  get(key) {
    const ref = this.#cache.get(key);
    if (!ref) return null;

    const value = ref.deref();
    if (value === undefined) {
      // Objek sudah di-sweep oleh Garbage Collector
      this.#cache.delete(key);
      return null;
    }

    return value;
  }

  /**
   * Ukuran saat ini (termasuk referensi mati yang belum difinalisasi)
   * @returns {number}
   */
  get size() {
    return this.#cache.size;
  }
}
```

---

## 8. Real World Case Study: High-Throughput Financial Event Ingestion

### 8.1. Konteks Masalah
Sebuah platform fintech memproses transaksi pembayaran real-time menggunakan Node.js microservice. Pada traffic 25,000 rps, latency P99 melonjak dari 15ms menjadi 2,300ms setiap 4 menit. Analisis pod Kubernetes menunjukkan lonjakan utilisasi CPU hingga 100% dan pod restart akibat OOMKilled (*Exit Code 137*).

### 8.2. Root Cause Analysis (RCA)
1.  **Event Loop Starvation:** Penggunaan `process.nextTick` secara rekursif dalam antrean parsing pesan menyebabkan deplesi queue microtask. Fase I/O Poll terblokir total.
2.  **Megamorphism pada DTO:** Transaksi memiliki skema dinamis di mana properti dimasukkan berdasarkan konfigurasi merchant secara acak (`payload[key] = val`). TurboFan mengalami deoptimasi konstan (*Bailout: Map update*).
3.  **Memory Leakage pada Error Handling:** Setiap transaksi gagal membuat instansiasi `new Error()` lengkap dengan stack trace, yang kemudian dimasukkan ke dalam unbounded global array untuk batch reporting.

### 8.3. Solusi Arsitektural & Implementasi
*   Normalisasi skema transaksi menggunakan layout properti yang dipadatkan (sealed struct pattern).
*   Ganti unbounded global array dengan ring buffer deterministik berbasis `TypedArray`.
*   Migrasi parsing batch payload intensif ke *Worker Thread* memanfaatkan `SharedArrayBuffer` dan `Atomics`.

```javascript
// worker-pool-pipeline.mjs
import { Worker, isMainThread, parentPort, workerData } from 'node:worker_threads';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);

if (isMainThread) {
  /**
   * Main Thread: Mengatur ingestion tanpa memblokir I/O loop
   */
  export class IngestionEngine {
    #sharedBuffer;
    #atomicFlag;
    #worker;

    constructor() {
      // Buffer berukuran 4 byte (Int32) untuk status kontrol atomik
      this.#sharedBuffer = new SharedArrayBuffer(Int32Array.BYTES_PER_ELEMENT);
      this.#atomicFlag = new Int32Array(this.#sharedBuffer);

      this.#worker = new Worker(__filename, {
        workerData: { sharedBuffer: this.#sharedBuffer },
      });

      this.#worker.on('error', (err) => console.error('Worker Failure:', err));
    }

    /**
     * Dispatch event parsing ke thread terpisah
     * @param {ArrayBuffer} payloadBuffer 
     */
    dispatch(payloadBuffer) {
      this.#worker.postMessage({ payloadBuffer }, [payloadBuffer]);
    }

    terminate() {
      this.#worker.terminate();
    }
  }
} else {
  /**
   * Worker Thread: Komputasi CPU-bound terisolasi
   */
  const { sharedBuffer } = workerData;
  const atomicFlag = new Int32Array(sharedBuffer);

  parentPort.on('message', ({ payloadBuffer }) => {
    // Sinkronisasi memori multi-thread menggunakan Atomics
    // Status 0: Idle, 1: Processing
    if (Atomics.compareExchange(atomicFlag, 0, 0, 1) === 0) {
      try {
        // Melakukan deserialisasi biner berkecepatan tinggi
        const view = new DataView(payloadBuffer);
        const transactionId = view.getUint32(0, true);
        const amount = view.getFloat64(4, true);

        // Simulasi validasi CPU-bound
        let checksum = 0;
        for (let i = 0; i < payloadBuffer.byteLength; i++) {
          checksum = (checksum + view.getUint8(i)) & 0xff;
        }

        // Output ke processing backend (via IPC non-blocking)
        parentPort.postMessage({ status: 'ACK', transactionId, checksum });
      } finally {
        Atomics.store(atomicFlag, 0, 0); // Reset lock
      }
    }
  });
}
```

---

## 9. Trade-offs: Analisis Rekayasa Komparatif

| Pendekatan Rekayasa | Keuntungan (+)| Kerugian / Trade-off (-) | Skenario Pemilihan Ideal |
| :--- | :--- | :--- | :--- |
| **Object Polymorphism / Dynamic Objects** | Fleksibilitas kode sangat tinggi, cepat dibuat saat prototyping, interoperabilitas loose-schema JSON. | Menggagalkan Inline Cache (IC), memicu TurboFan deoptimization, alokasi heap membengkak. | Edge router sederhana, pipeline data dengan variasi field tidak terduga dan throughput rendah (<1,000 rps). |
| **Monomorphic Structs / Frozen Classes** | Optimasi JIT maksimal, memory footprint konstan, akses memori mendekati kecepatan C++. | Struktur kaku, boilerplate tinggi, developer overhead dalam mendefinisikan layout di awal. | Core domain microservice, high-frequency matching engine, financial transactional systems. |
| **Worker Threads + SharedArrayBuffer** | Mencegah blokade Main Event Loop, utilisasi penuh multi-core CPU pada bare-metal/container. | Serialisasi overhead (jika tanpa SAB), alokasi memori OS per-worker (~30MB base), risiko *race condition* (wajib `Atomics`). | Kompresi file real-time, manipulasi gambar/video, kriptografi masif, parsing file CSV/Parquet skala gigabyte. |
| **WeakRef Memory Caching** | Mencegah OOM secara absolut; objek otomatis tereliminasi saat memori server kritis. | Perilaku deterministik hilang (kapan GC berjalan tidak dapat diprediksi), overhead eksekusi dereferencing via pointer. | Layer caching lokal L1 untuk objek besar yang siap di-fetch ulang dari Redis/DB jika hilang. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal yang Sering Terjadi di Produksi
1.  **Deoptimasi Silang Tipe (Hidden Class Mutation):**
    ```javascript
    // FATAL: Mengubah tipe properti menyebabkan deoptimasi
    function compute(item) { return item.id * 2; }
    compute({ id: 100 });    // SMI (Small Integer) -> TurboFan compiles
    compute({ id: "100" });  // String -> TurboFan BAILOUT! Deoptimizing function!
    ```
2.  **Starvasi Main Loop via `process.nextTick`:**
    ```javascript
    // FATAL: Rekursi tak berujung pada queue Microtask
    function recursiveMicrotask() {
      process.nextTick(recursiveMicrotask); // Starves I/O and Macrotasks!
    }
    recursiveMicrotask(); // Server berhenti merespons traffic jaringan
    ```
3.  **Closure Retention Leak:**
    ```javascript
    let leakingScope = null;
    function run() {
      const hugeData = new Array(1e6).fill('*');
      const prior = leakingScope;
      leakingScope = function () {
        // Objek 'prior' dan 'hugeData' terperangkap dalam lexical environment bersama
        if (prior) return hugeData; 
      };
    }
    setInterval(run, 10); // Menghabiskan seluruh heap dalam beberapa detik!
    ```

### 10.2. Troubleshooting Playbook: Menangani Deoptimasi dan Leak
*   **Deteksi Deoptimasi V8 Secara Real-time:**
    Jalankan node engine dengan tracing flags:
    ```bash
    node --trace-opt --trace-deopt server.mjs
    ```
    Cari log output yang mengandung: `[deoptimizing: begin ... reason: wrong map]`.
*   **Mendeteksi Starvasi Event Loop:**
    Gunakan `perf_hooks` untuk mengukur *Event Loop Delay (ELD)*:
    ```javascript
    import { monitorEventLoopDelay } from 'node:perf_hooks';
    const h = monitorEventLoopDelay({ resolution: 20 });
    h.enable();
    setInterval(() => {
      // Jika P99 > 50ms, sistem berada dalam kondisi kritis!
      console.log(`ELD P99: ${h.percentile(99) / 1e6} ms`);
    }, 1000);
    ```

---

## 11. Best Practices & Production Checklist

### Pre-Deployment Checklist
- [ ] **Monomorphic Consistency:** Semua entity core domain memiliki bentuk (shape) konstan; properti tidak pernah dihapus via `delete`.
- [ ] **Asynchronous Boundaries:** Operasi synchronous berdurasi > 10ms telah dipindahkan ke Worker Threads.
- [ ] **Microtask Control:** Tidak ada implementasi rekursif tak berujung pada `process.nextTick` atau unhandled recursive promises.
- [ ] **Memory Bounds:** Semua memory cache memiliki batasan ukuran (bounded size) atau dibungkus menggunakan `WeakRef`.
- [ ] **V8 Heap Sizing:** Flag `--max-old-space-size` disesuaikan secara eksplisit dengan memori container (misal: 75% dari memory limit pod k8s).

---

## 12. Hands-on Practice

Buatlah direktori praktikum dan berkas pengujian berikut:

```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
```

### File: `hands-on/m02/profiler-experiment.mjs`
```javascript
import { monitorEventLoopDelay, performance } from 'node:perf_hooks';

// Setup Event Loop Monitor
const detector = monitorEventLoopDelay({ resolution: 10 });
detector.enable();

function generateHeavyShapes() {
  const collection = [];
  for (let i = 0; i < 50000; i++) {
    const obj = {};
    if (i % 2 === 0) {
      obj.a = i;
      obj.b = "text";
    } else {
      obj.b = "text"; // Urutan properti terbalik! Memecah monomorphism
      obj.a = i;
    }
    collection.push(obj);
  }
  return collection;
}

function processEntities(list) {
  let sum = 0;
  for (let i = 0; i < list.length; i++) {
    // Dynamic IC check di sini akan melambat karena polymorphic/megamorphic
    sum += list[i].a;
  }
  return sum;
}

const start = performance.now();
const data = generateHeavyShapes();
const total = processEntities(data);
const duration = performance.now() - start;

console.log(`Selesai memproses ${total} dalam ${duration.toFixed(2)} ms`);
console.log(`Event Loop Delay Max: ${(detector.max / 1e6).toFixed(2)} ms`);
detector.disable();
```

### Langkah Eksekusi:
```bash
# Jalankan dengan tracing V8 engine
node --trace-deopt profiler-experiment.mjs
```

---

## 13. Exercises

### Level: Easy
Refaktor fungsi berikut agar mempertahankan shape objek yang monomorfik dan tidak mengubah layout internal V8.
```javascript
function initUser(id, email, role) {
  const user = { id, email };
  if (role) {
    user.role = role;
  }
  return user;
}
```
*Kriteria Selesai:* Objek yang dihasilkan selalu memiliki transisi Hidden Class yang sama terlepas dari apakah `role` bernilai `undefined` atau memiliki string value.

### Level: Medium
Buat sebuah utility function `batchProcess(items, batchSize, fn)` yang memproses array besar (100,000 elemen) menggunakan micro-yielding pattern (`setImmediate`) agar Event Loop tetap responsif menerima koneksi jaringan baru di sela-sela pemrosesan batch.

### Level: Hard
Implementasikan sebuah Shared-Memory Circular Queue menggunakan `SharedArrayBuffer` dan `Atomics` yang memungkinkan thread Producer menulis bilangan bulat `Int32` dan thread Consumer membacanya secara thread-safe tanpa menggunakan komunikasi pesan standar `postMessage`.

---

## 14. Challenge: Enterprise-Scale High-Throughput Memory Allocator

**Skenario Masalah:**
Perusahaan Anda sedang membangun service WebSocket gateway berlatensi sangat rendah (Ultra Low-Latency) yang menerima 100,000 frame per detik. Setiap frame biner harus didekode, divalidasi, dan ditransmisikan ulang.

Penggunaan Garbage Collection standar V8 memicu freeze time (*Stop-The-World*) selama rata-rata 30-50 milidetik per batch alokasi besar, yang melanggar Service Level Objective (SLO) P999 (< 5ms).

**Tantangan Arsitektur:**
1.  Rancang dan bangun sebuah memory pool kustom (**Off-Heap/Pre-allocated ArrayBuffer Pool**) pada Node.js tanpa memicu Scavenge atau Major GC selama masa operasional runtime.
2.  Arsitektur harus menggunakan Worker Thread pool deterministik.
3.  Alokasi, peminjaman (*renting*), dan pengembalian (*releasing*) byte slice harus menggunakan instruksi `Atomics` murni.
4.  Jika terjadi peminjaman melebihi kapasitas buffer, sistem harus mengantrekan request menggunakan struktur data non-blocking, bukan melempar exception atau memicu dynamic buffer expansion yang memicu alokasi heap baru.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. **Komponen V8 manakah yang bertanggung jawab menghasilkan optimized machine code secara langsung dari type feedback?**
   * A) Ignition
   * B) TurboFan
   * C) Orinoco
   * D) Pre-parser
   * *Kunci Jawaban:* B
   * *Penjelasan:* Ignition adalah interpreter bytecode, sedangkan TurboFan adalah JIT optimizing compiler yang mengompilasi bytecode menjadi arsitektur mesin teroptimasi berdasarkan profil runtime.

2. **Apa yang terjadi pada memori object saat ia berhasil bertahan dari dua siklus Garbage Collection minor (Scavenge)?**
   * A) Dihapus dari memory
   * B) Dipindahkan ke Old Pointer/Data Space
   * C) Dipindahkan ke Code Space
   * D) Dikonversi menjadi WeakRef secara otomatis
   * *Kunci Jawaban:* B
   * *Penjelasan:* Objek yang lolos dari dua siklus minor GC (generasi baru/New Space) akan dipromosikan (tenured) ke Old Space.

3. **Mengapa penggunaan operator `delete obj.property` sangat dihindari dalam optimasi performa V8?**
   * A) Karena langsung memicu Major GC seketika
   * B) Karena menghapus referensi memori di stack
   * C) Karena merusak Hidden Class (Shape) dan mengubah objek ke Dictionary Mode
   * D) Karena menyebabkan proses Node.js crash
   * *Kunci Jawaban:* C
   * *Penjelasan:* Operator `delete` mengubah struktur internal representasi memori objek V8 dari Hidden Class teroptimasi menjadi hash table (Dictionary Mode), merusak Inline Cache.

4. **Queue manakah yang memiliki prioritas eksekusi tertinggi di antara setiap fase Event Loop?**
   * A) `setTimeout` Queue
   * B) `setImmediate` Queue
   * C) `process.nextTick` Microtask Queue
   * D) I/O Polling Queue
   * *Kunci Jawaban:* C
   * *Penjelasan:* `process.nextTick` diproses segera setelah operasi yang sedang berjalan selesai, mendahului Promise microtasks dan fase Event Loop lainnya.

5. **Apakah fungsi utama dari `FinalizationRegistry`?**
   * A) Memaksa Garbage Collector untuk segera berjalan
   * B) Mendaftarkan callback yang dijalankan setelah suatu target objek dibersihkan oleh GC
   * C) Mencegah objek agar tidak pernah di-sweep oleh GC
   * D) Mengatur alokasi memori ke disk
   * *Kunci Jawaban:* B
   * *Penjelasan:* `FinalizationRegistry` memungkinkan Anda meminta callback saat sebuah objek telah dibersihkan oleh GC tanpa menahan referensi ke objek tersebut.

---

### Bagian 2: Intermediate (Pilihan Ganda)

6. **Kondisi Inline Cache yang memeriksa pemanggilan method pada 3 jenis Shape objek yang berbeda diklasifikasikan sebagai:**
   * A) Monomorphic
   * B) Bimorphic
   * C) Polymorphic
   * D) Megamorphic
   * *Kunci Jawaban:* C
   * *Penjelasan:* 1 Shape = Monomorphic, 2-4 Shape = Polymorphic, >4 Shape = Megamorphic.

7. **Pada situasi bagaimana penggunaan `SharedArrayBuffer` berisiko menimbulkan *Data Race* jika tidak dimitigasi?**
   * A) Saat dibaca bersamaan oleh dua fungsi async di main thread
   * B) Saat dimutasi oleh dua thread berbeda secara simultan tanpa sinkronisasi atomik
   * C) Saat dikonversi menjadi JSON string
   * D) Saat dilewatkan melalui `structuredClone`
   * *Kunci Jawaban:* B
   * *Penjelasan:* `SharedArrayBuffer` mengizinkan akses memori bersama secara paralel antar thread; mutasi simultan tanpa `Atomics` memicu kondisi race condition pada tingkat byte.

8. **Algoritma Tri-Color Marking mendefinisikan objek "Grey" sebagai objek yang:**
   * A) Belum dikunjungi sama sekali oleh GC pointer
   * B) Telah dikunjungi dan semua objek yang direferensikannya telah selesai dipindai
   * C) Telah ditemukan/dikunjungi, tetapi referensi turunannya belum selesai dipindai
   * D) Sudah pasti akan dihapus pada fase sweeping
   * *Kunci Jawaban:* C
   * *Penjelasan:* White = belum dikunjungi, Grey = telah dikunjungi tapi anak-anaknya belum dipindai, Black = objek beserta seluruh turunannya telah selesai dikunjungi.

9. **Jika P99 Event Loop Delay meningkat drastis namun utilisasi CPU sistem secara keseluruhan berada di bawah 15%, apa diagnosis yang paling rasional?**
   * A) Terjadi deoptimasi massal pada TurboFan
   * B) Ada callback sinkron yang memblokir main thread secara intermiten
   * C) Node.js kekurangan alokasi Worker Threads
   * D) Garbage Collection Major berjalan secara konkuren
   * *Kunci Jawaban:* B
   * *Penjelasan:* Utilisasi CPU rendah dengan Event Loop Delay tinggi menandakan main thread terblokir oleh operasi sinkron (misal: JSON.parse masif, synchronous fs/crypto, atau STW pause) tanpa membebani multi-core CPU.

10. **Manakah metode yang benar untuk melepaskan referensi dari sebuah `WeakRef` object bernama `wr`?**
    * A) `wr.get()`
    * B) `wr.deref()`
    * C) `wr.value()`
    * D) `wr.unwrap()`
    * *Kunci Jawaban:* B
    * *Penjelasan:* Method `deref()` mengembalikan target objek dari `WeakRef`, atau `undefined` jika objek target sudah disapu oleh GC.

---

### Bagian 3: Skenario Kasus Produksi

11. **Skenario:** Aplikasi Anda menggunakan library pihak ketiga yang menerima payload konfigurasi fleksibel:
    ```javascript
    function logEvent(data) {
      console.log(data.userId, data.action, data.timestamp);
    }
    ```
    Metrik produksi menunjukkan fungsi ini mengalami bailout permanen dari TurboFan. Setelah diinvestigasi, beberapa produsen log mengirimkan field urutan `{ userId, action, timestamp }`, sedangkan yang lain mengirimkan `{ timestamp, userId, action }`. Apa tindakan arsitektural tercepat dan terefisien untuk memulihkan optimasi TurboFan?
    * *Analisis dan Solusi:* Buat layer normalisasi DTO (Data Transfer Object) menggunakan class atau factory function yang memetakan data input ke dalam satu shape seragam sebelum diteruskan ke fungsi inti:
      ```javascript
      class NormalizedLog {
        constructor(userId, action, timestamp) {
          this.userId = userId;
          this.action = action;
          this.timestamp = timestamp;
        }
      }
      // Instansiasi selalu menjamin Hidden Class yang monomorfik
      logEvent(new NormalizedLog(data.userId, data.action, data.timestamp));
      ```

12. **Skenario:** Service pemrosesan streaming transaksi mengalami memory leak lambat: memori naik 100MB per jam, stabil di awal, namun OOM crash terjadi setelah 24 jam. Heap snapshot menunjukkan jutaan instance dari string URL yang terperangkap pada callback context timer yang tidak pernah dieksekusi secara tuntas.
    * *Langkah Troubleshooting dan Perbaikan:*
      1. Ambil dua heap snapshot pada interval 2 jam (`node --inspect`).
      2. Gunakan *Comparison View* di Chrome DevTools Heap Profiler untuk melihat objek yang bertambah secara konstan.
      3. Identifikasi alokasi timer (`setTimeout`/`setInterval`) yang tidak dibatalkan (`clearTimeout`).
      4. Perbaiki lifecycle pattern dengan memastikan setiap timeout didaftarkan dengan `AbortController` signal pattern, atau pastikan referensi timer dibersihkan ketika koneksi streaming terputus.

13. **Skenario:** Node.js API gateway bertugas mengompresi payload respons JSON yang sangat besar (15MB) menggunakan library Brotli/Gzip bawaan. Di bawah pengujian beban 500 RPS, latency rata-rata API lain yang berukuran kecil (hanya 1KB) melonjak hingga ribuan milidetik.
    * *Mitigasi Arsitektural:*
      Kompresi payload berukuran 15MB adalah operasi CPU-intensive yang menyita waktu eksekusi thread Libuv secara ekstrem, menghalangi I/O pool untuk request lain. Pindahkan pemrosesan respons masif ini ke dedicated worker menggunakan `Worker Threads` atau delegasikan kompresi sepenuhnya ke level reverse proxy/edge layer (misal: NGINX, Cloudflare, atau Envoy) agar application runtime murni menangani orchestration logis tanpa kompresi berat.

---

## 16. Summary

*   **V8 Compilation Pipeline:** Mengombinasikan interpreter **Ignition** untuk startup cepat dan compiler **TurboFan** untuk optimasi berbasis feedback vector. Menjaga bentuk objek tetap stabil (*monomorphic*) adalah kunci performa puncak execution speed.
*   **Hidden Classes (Shapes) & Inline Caching:** JavaScript engine memetakan layout memori berdasarkan urutan inisialisasi properti. Hindari dynamic insertion dan operator `delete` demi mempertahankan efisiensi cache lookup.
*   **Garbage Collection Orinoco:** Menggunakan model Generational Heap (New vs Old Space) dan Tri-color Marking inkremental/konkuren. Kelola siklus hidup objek besar secara bijak; gunakan `WeakRef` dan `FinalizationRegistry` untuk resource transient guna memitigasi memory leaks.
*   **Concurrency Architecture:** Node.js mengandalkan model single-threaded Event Loop yang dikawal oleh *Microtasks* dan *Macrotasks*. Tugas berat berbasis CPU wajib didelegasikan ke *Worker Threads* dengan arsitektur sinkronisasi tingkat rendah (`SharedArrayBuffer` dan `Atomics`) untuk mengeliminasi latensi dan menjaga throughput produksi.