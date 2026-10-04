# Kurikulum Rekayasa Perangkat Lunak Enterprise: JavaScript Core Internals

---

## BAB 05: Functional Programming Paradigm & Closures Deep Dive
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Membedah representasi memori internal V8 engine (Stack Frame vs. Heap-allocated Context Object) saat closure terbentuk dan mengevaluasi deoptimasinya.
- Menganalisis *Scope Chain Traversal* dan *Identifier Resolution* pada runtime V8, serta mengidentifikasi alokasi `ContextSlot` versus alokasi stack lokal.
- Mengidentifikasi, mereproduksi, dan merekayasa mitigasi memory leak laten akibat siklus referensi closure (*Accidental Lexical Retention*) menggunakan Heap Profiler.
- Mengimplementasikan konsep Functional Programming lanjutan: Transducers untuk pemrosesan dataset besar dengan kompleksitas $O(N)$ waktu dan $O(1)$ ruang tambahan, Point-free Composition pipelines, serta Monadic Error Handling (`Either`/`Result`).
- Merancang dan menguji arsitektur State Machine fungsional berbasis closure murni (*encapsulated immutable state*) yang tahan terhadap konkurensi asinkron di lingkungan Node.js high-throughput.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib menguasai:
- **BAB 05 Modul 01**: Dasar Functional Programming (Pure Functions, Higher-Order Functions, Lexical Scoping).
- **Runtime Internals Dasar**: Pemahaman Call Stack, Event Loop (Microtask/Macrotask Queue), dan Lifecycle Garbage Collector (Generational GC: Scavenge/Minor GC & Mark-Sweep/Major GC).
- **Tooling Profiling**: Kemampuan menggunakan Node.js `--inspect` flag dan Chrome DevTools Memory Inspector (Allocation Instrumentation on Timeline, Heap Snapshot analysis).

---

### 3. Concept & Internal Architecture

#### 3.1. Representasi Memori V8: Stack Frame vs. Context Allocation
Secara *default*, eksekusi fungsi non-closure mengalokasikan variabel primitif lokal langsung pada CPU execution stack (Stack Frame). Ketika fungsi menyelesaikan siklus eksekusinya, stack pointer diturunkan (`POP`), dan memori dibebaskan secara instan dengan *zero GC overhead*.

Namun, ketika sebuah fungsi internal (*inner function*) mereferensikan variabel dari outer lexical scope dan diekspor atau ditahan di luar lifecycle pemanggilan fungsi tersebut (*escaping closure*), variabel tersebut tidak dapat disimpan pada stack. 

V8 Parser melakukan analisis statis (*Scope Analysis* dan *Variable Allocation Phase*) sebelum proses kompilasi bytecode oleh Ignition:
1. **Escape Analysis**: Parser menentukan apakah ada variabel lokal yang "lolos" (*escapes*) melewati masa hidup stack frame fungsi induk.
2. **Context Creation**: Jika ada variabel yang lolos, V8 memindahkan variabel tersebut ke dalam struktur data heap yang disebut `Context`.
3. **Context Slot Allocation**: Variabel yang tertutup (*closed-over variables*) dialokasikan ke slot array terindeks di dalam `Context` objek (`[context, slot_index]`).
4. **Context Chaining**: Jika terdapat *nested closures*, objek `Context` membentuk rantai berarah (*singly-linked list*) via pointer `previous`, yang menunjuk ke `Context` dari lexical scope induknya hingga mencapai `NativeContext` (Global Scope).

```
Stack Frame (Execution Scope)                V8 Heap Space
+-------------------------------+          +--------------------------------------+
| OuterFunction Activation      |          | Context (OuterScope)                 |
| - Arguments                   |          | +----------------------------------+ |
| - Non-escaping locals (Stack) |          | | slot 0: ScopeInfo pointer        | |
| - Context Pointer ----------> | -------> | | slot 1: previous Context*        | |
+-------------------------------+          | | slot 2: capturedVar = 0x4F...    | |
                                           | +----------------------------------+ |
                                           +--------------------------------------+
                                                              ^
                                                              | outer_context
+-------------------------------+          +--------------------------------------+
| InnerFunction Activation      |          | Context (InnerScope)                 |
| - Arguments                   |          | +----------------------------------+ |
| - Context Pointer ----------> | -------> | | slot 0: ScopeInfo pointer        | |
+-------------------------------+          | | slot 1: previous Context* -------- |
                                           | | slot 2: localCapturedVar         | |
                                           | +----------------------------------+ |
                                           +--------------------------------------+
```

#### 3.2. Deoptimasi Mesin & Garbage Collection Footprint
Ketika inner closure mengikat variabel outer, V8 membagikan `Context` yang sama ke seluruh fungsi yang dideklarasikan dalam scope leksikal yang identik:
- **Shared Context Problem**: Jika fungsi $F_1$ menutup variabel $V_{large}$ (sebuah Buffer 100MB), dan fungsi $F_2$ hanya menutup variabel $V_{small}$ (sebuah integer), kedua fungsi tersebut akan merujuk pada `Context` heap yang sama jika berada dalam satu lexical block.
- **Root Retention**: Selama referensi ke $F_2$ tetap hidup (misalnya sebagai event listener atau timer), seluruh objek `Context`—termasuk $V_{large}$—tidak akan bisa dikumpulkan oleh Garbage Collector, meskipun $F_1$ sudah mati dan $F_2$ tidak pernah mengakses $V_{large}$.

---

### 4. Why & What

| Dimensi | Pendekatan Imperatif / Stateful OOP | Pendekatan Advanced Functional Programming |
| :--- | :--- | :--- |
| **State Mutation** | *In-place mutation* via properti objek publik/privat. Rentan terhadap *race condition* multi-event. | *Immutable data transformations*. State terisolasi secara leksikal dalam closure factory. |
| **Code Reusability** | Polimorfisme pewarisan (*Inheritance*) atau *Mixins* yang menciptakan kopling vertikal tinggi. | Komposisi fungsi tingkat tinggi (*Higher-Order Functions*), Currying, dan Point-Free pipelines. |
| **Error Handling** | `try/catch` blok imperatif yang memecah alur eksekusi sinkron dan mahal secara komputasi. | Monadic types (`Result`, `Either`) yang memperlakukan error sebagai nilai dalam *happy path pipeline*. |
| **Kinerja Koleksi** | Rantai `.map().filter().slice()` menghasilkan array sementara (*intermediate array*) di heap per operasi. | **Transducers**: Melipat transformasi dan filtrasi menjadi satu siklus iterasi tanpa alokasi memori intermediat. |

---

### 5. How (Workflow Detail)

Alur kerja arsitektural implementasi pipeline fungsional tingkat produksi:

```
[Input Data Stream/Array]
         │
         ▼
┌────────────────────────────────────────────────────────┐
│ Transducer Composition Stage                           │
│ (Mapping -> Filtering -> Slicing)                      │
│ * Komposisi reducer fungsional: Step Function          │
│ * Eksekusi O(N) dalam 1 pass tanpa alokasi temporer    │
└────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────┐
│ Monadic Validation Pipeline (Either / Result)          │
│ * Left: Fast-fail containing domain error invariants   │
│ * Right: Success context carrying domain entities      │
└────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────┐
│ Encapsulated State Update (Lexical Closure Machine)    │
│ * Atomic swap State via Curried Function               │
│ * No global scope mutation                             │
└────────────────────────────────────────────────────────┘
         │
         ▼
[Normalized Output Event / Immutable Snapshot]
```

---

### 6. Analogy & Diagram ASCII

Bayangkan memori V8 sebagai sebuah **Gedung Perkantoran (CPU Stack)** dan **Gudang Penyimpanan Eksternal (V8 Heap)**:
- **Fungsi Biasa**: Meja kerja sementara. Pekerja membawa dokumen, memprosesnya, lalu mencacahnya saat jam pulang (fungsi selesai). Bebas biaya sewa jangka panjang.
- **Escaping Closure**: Pekerja harus meninggalkan instruksi untuk shift malam. Karena meja kerja harus dibersihkan, instruksi dan dokumen terkait dipindahkan ke dalam **Brankas Khusus (Context Object)** di Gudang Eksternal.
- **Shared Context Leak**: Jika pekerja memasukkan hard drive 500TB dan selembar kartu pos ke brankas yang sama, shift malam yang hanya butuh kartu pos memaksa brankas tersebut tetap disewa penuh bersama hard drive-nya.

```
       CALL STACK                             V8 HEAP MEMORY
┌───────────────────────┐             ┌──────────────────────────────┐
│ execution_frame()     │             │ V8 Context Object            │
│  ├── local_primitives │             │  ├── Pointer: Large Data ────┼──┐
│  └── ctx_ptr ─────────┼────────────►│  └── Pointer: Target Metric  │  │
└───────────────────────┘             └──────────────────────────────┘  │
           │                                                            │
      Stack Pop                                                         │
           ▼                                                            │
    [Frame Destroyed]                 ┌──────────────────────────────┐  │
                                      │ Heap Memory Allocation       │  │
                                      │ [Raw Buffers / Payloads]  ◄──┼──┘
                                      │ *TERKUNCI: Tidak bisa di-GC  │
                                      │  jika ada closure lain yang  │
                                      │  merujuk Context yang sama!  │
                                      └──────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Transducer Engine Minimalis
Contoh berikut menunjukkan bagaimana komposisi transformer fungsional menghindari pembuatan array intermediat:

```javascript
/**
 * Transducer Primitives
 */
const mapTransducer = (mapperFn) => (step) => (accumulator, current) =>
  step(accumulator, mapperFn(current));

const filterTransducer = (predicateFn) => (step) => (accumulator, current) =>
  predicateFn(current) ? step(accumulator, current) : accumulator;

// Reducer akhir yang membangun hasil
const arrayPushReducer = (accumulator, current) => {
  accumulator.push(current);
  return accumulator;
};

// Utilities Komposisi Pipeline
const compose = (...fns) => (initialValue) =>
  fns.reduceRight((acc, fn) => fn(acc), initialValue);

// Dataset
const dataset = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

// Transformasi: (n * 3) -> filter hanya angka genap
const transformPipeline = compose(
  mapTransducer((x) => x * 3),
  filterTransducer((x) => x % 2 === 0)
);

// Eksekusi transduce: Single pass, O(N) Time, O(1) Intermediate Garbage
const result = dataset.reduce(transformPipeline(arrayPushReducer), []);
console.log("Transduced Result:", result); // [6, 12, 18, 24, 30]
```

#### 7.2. Practical Example: Monadic Pipeline & Lexical Encapsulation
Implementasi industri: Monadic parser transaksi finansial yang membungkus state auditori menggunakan closure private.

```javascript
/**
 * @template L, R
 */
class Either {
  /** @param {L} left @param {R} right */
  constructor(left, right) {
    this._left = left;
    this._right = right;
  }

  static right(val) { return new Either(null, val); }
  static left(err) { return new Either(err, null); }

  isRight() { return this._left === null; }
  isLeft() { return !this.isRight(); }

  map(fn) {
    return this.isRight() ? Either.right(fn(this._right)) : this;
  }

  flatMap(fn) {
    return this.isRight() ? fn(this._right) : this;
  }

  fold(onLeft, onRight) {
    return this.isLeft() ? onLeft(this._left) : onRight(this._right);
  }
}

/**
 * Audit State Factory dengan Encapsulated Context
 */
function createAuditVault(vaultId) {
  // Dialokasikan di Context Object V8
  const auditLogs = [];
  let integrityHash = 0;

  return {
    recordTransaction(transactionId, amount) {
      if (amount <= 0) {
        return Either.left(new Error(`[${vaultId}] Invalid transaction amount: ${amount}`));
      }

      // Mutasi leksikal yang sepenuhnya terisolasi
      integrityHash = (integrityHash ^ (amount * 31)) >>> 0;
      auditLogs.push({
        transactionId,
        amount,
        hashSnapshot: integrityHash,
        timestamp: Date.now()
      });

      return Either.right({
        status: "RECORDED",
        vaultId,
        currentHash: integrityHash
      });
    },

    getAuditSummary() {
      // Mengembalikan immutable shallow snapshot untuk mencegah leaking referensi langsung
      return {
        vaultId,
        entryCount: auditLogs.length,
        currentHash: integrityHash,
        lastSnapshot: auditLogs[auditLogs.length - 1] ?? null
      };
    }
  };
}

// Penggunaan di Production Layer
const vault = createAuditVault("VT-EUR-001");

const processIncomingPayment = (txId, amount) =>
  Either.right({ txId, amount })
    .flatMap(({ txId, amount }) => vault.recordTransaction(txId, amount))
    .fold(
      (error) => ({ success: false, reason: error.message }),
      (successPayload) => ({ success: true, payload: successPayload })
    );

console.log(processIncomingPayment("TX-101", 5000));
console.log(processIncomingPayment("TX-102", -200)); // Graceful Handling
console.log("Vault Metrics:", vault.getAuditSummary());
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: High-Throughput Transaction Ledger Sanitizer & Aggregator
**Konteks**: Sebuah payment gateway memproses 20.000 transaksi JSON per detik per container. Pipeline sebelumnya menggunakan *method chaining* standar (`Array.prototype.map().filter().reduce()`), yang menghasilkan jutaan array temporer, memicu V8 GC *Stop-the-World* (Scavenger thrashing) berkala hingga menaikkan latency P99 dari 5ms menjadi 240ms.

#### Solusi Arsitektur
Membangun Transducer-driven Processing Engine yang dipadukan dengan Curry-curried Business Invariants.

```javascript
import { performance } from "node:perf_hooks";

// --- Transducer Utilities Industri ---
const tMap = (fn) => (step) => (acc, item) => step(acc, fn(item));
const tFilter = (predicate) => (step) => (acc, item) => predicate(item) ? step(acc, item) : acc;

const pipe = (...fns) => (val) => {
  let acc = val;
  for (let i = 0; i < fns.length; i++) {
    acc = fns[i](acc);
  }
  return acc;
};

// Transducer Aggregator Engine
const transduce = (iterable, xform, reducer, init) => {
  const step = xform(reducer);
  let acc = init;
  for (const item of iterable) {
    acc = step(acc, item);
  }
  return acc;
};

// --- Business Domain Functions (Pure) ---
const isSettled = (tx) => tx.status === "SETTLED";
const isAboveThreshold = (min) => (tx) => tx.amountInCents >= min;
const sanitizePII = (tx) => ({
  id: tx.id,
  cleansedAccount: `***${tx.accountNumber.slice(-4)}`,
  amountInCents: tx.amountInCents,
  currency: tx.currency
});

// Financial Ledger Reducer (Zero intermediation)
const financialSummarizer = (summary, tx) => {
  summary.totalVolume += tx.amountInCents;
  summary.processedCount += 1;
  summary.accounts.push(tx.cleansedAccount);
  return summary;
};

// --- Simulasi Beban Tinggi ---
const BATCH_SIZE = 100_000;
const mockTransactions = Array.from({ length: BATCH_SIZE }, (_, idx) => ({
  id: `tx_${idx}`,
  status: idx % 3 === 0 ? "SETTLED" : "FAILED",
  amountInCents: (idx % 100) * 100,
  accountNumber: `453211234567${idx.toString().padStart(4, "0")}`,
  currency: "IDR"
}));

// Pipeline Definition
const transactionSanitizerTransducer = pipe(
  tFilter(isSettled),
  tFilter(isAboveThreshold(2000)),
  tMap(sanitizePII)
);

// Eksekusi Benchmarking
const startMemory = process.memoryUsage().heapUsed;
const startTime = performance.now();

const initialAggregate = { totalVolume: 0, processedCount: 0, accounts: [] };
const resultSummary = transduce(
  mockTransactions,
  transactionSanitizerTransducer,
  financialSummarizer,
  initialAggregate
);

const endTime = performance.now();
const endMemory = process.memoryUsage().heapUsed;

console.log("Processing Performance Result:");
console.log(`Executed in: ${(endTime - startTime).toFixed(3)} ms`);
console.log(`Heap Delta: ${((endMemory - startMemory) / 1024 / 1024).toFixed(3)} MB`);
console.log("Summary Out:", {
  totalVolume: resultSummary.totalVolume,
  processedCount: resultSummary.processedCount,
  sampleAccounts: resultSummary.accounts.slice(0, 3)
});
```

---

### 9. Trade-offs

| Pendekatan | Keuntungan (*Pros*) | Kerugian (*Cons*) |
| :--- | :--- | :--- |
| **Pure FP Pipelines (Transducers)** | 1. Memory profile datar ($O(1)$ intermediate allocation).<br>2. Menghilangkan GC pressure secara signifikan.<br>3. Transformasi dapat diuji secara independen tanpa mocks. | 1. Kurva pembelajaran curam bagi engineer junior.<br>2. Stack traces sulit dibaca saat terjadi runtime error.<br>3. Overhead fungsi pemanggilan berantai kecil pada batch data sangat kecil ($< 100$ item). |
| **Encapsulated Scope (Closures)** | 1. Privatisasi data tanpa butuh runtime private fields (`#private`).<br>2. Tidak ada mutasi global state.<br>3. Self-contained lifecycle. | 1. Deoptimasi V8 jika banyak context objects dibuat.<br>2. Resiko kebocoran memori laten via *Shared Lexical Scope*.<br>3. Instansiasi fungsi ganda (*allocating new function pointers*) tiap invokasi factory. |
| **Object Oriented State (Prototypes/Classes)** | 1. *Monomorphic Inline Caching* V8 berjalan optimal.<br>2. Penggunaan memori method sharing via prototype.<br>3. Stack trace eksplisit. | 1. State rentan terhadap mutasi dari luar (*aliasing bug*).<br>2. Sulit diparalelisasi atau diprediksi dalam stream asynchronous.<br>3. Perlu defensive copying manual yang membebani CPU. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Common Mistake: Shared Lexical Context Retention (The "Meteor" Leak Pattern)
Contoh kebocoran memori klasik di mana dua closure berbagi Context yang sama:

```javascript
// BAD: Kebocoran Memori Sistematis
let leakRunner;

function setupServerListener() {
  // Buffer besar dialokasikan di sini
  let heavyBuffer = Buffer.alloc(50 * 1024 * 1024); // 50MB

  // Closure 1: Mengakses heavyBuffer
  const unusedDebugger = function () {
    if (heavyBuffer) {
      console.log("Buffer active");
    }
  };

  // Closure 2: TIDAK mengakses heavyBuffer, tapi ada di lexical scope yang SAMA
  leakRunner = function () {
    return "Status OK";
  };
}

// Setiap invokasi, Context lama tertahan di Heap karena leakRunner memegang referensi ke Context tersebut
setInterval(() => {
  setupServerListener();
  // heavyBuffer TIDAK PERNAH di-GC!
}, 100);
```

#### 10.2. Troubleshooting Workflow: Debugging via Chrome DevTools / Heap Snapshot
Jika memory leak terjadi di staging/production:

1. **Jalankan Profiler**:
   ```bash
   node --inspect --max-old-space-size=512 app.js
   ```
2. **Koneksikan Chrome**:
   Buka `chrome://inspect` di Chromium browser, klik "Open dedicated DevTools for Node".
3. **Capture Base Snapshot**:
   Masuk ke tab **Memory**, pilih **Heap snapshot**, klik **Take snapshot**.
4. **Trigger Traffic/Workload**:
   Kirimkan $10.000$ transaksi ke server.
5. **Capture Second Snapshot**:
   Ambil snapshot kedua, lalu ubah view dari **Summary** menjadi **Comparison**.
6. **Analisis Alokasi `Context`**:
   - Filter berdasarkan string `(closure)` atau `system / Context`.
   - Periksa kolom **# Alloc** dan **Freed Size**.
   - Telusuri **Retainers Tree**: Cari node yang dipertahankan oleh pointer closure tanpa sadar.
7. **Mitigasi Kode**:
   Pisahkan scope atau atur manual *nulling reference* (`heavyBuffer = null;`) sebelum fungsi keluar, atau pecah lexical scope menjadi fungsi mandiri.

```javascript
// GOOD: Isolasi Lexical Scope
function setupServerListenerFixed() {
  {
    // Scope terisolasi: heavyBuffer masuk ke sub-context sendiri
    const heavyBuffer = Buffer.alloc(50 * 1024 * 1024);
    // Jalankan operasi yang memerlukan heavyBuffer
    heavyBuffer.fill(1);
  }

  // leakRunner sekarang dialokasikan pada context yang bebas dari referensi heavyBuffer
  leakRunner = function () {
    return "Status OK";
  };
}
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Hindari Large Data Scope Sharing**: Jangan pernah mendeklarasikan closure berumur panjang (misal: event listeners, timer) di blok yang sama dengan alokasi objek besar.
- [ ] **Favoritkan Pure Transducers**: Gunakan transducers untuk array bertingkat lebih dari $10.000$ elemen alih-alih merangkai banyak method `.map().filter()`.
- [ ] **Gunakan Shallow Copy State Snapshot**: Saat mengekspos internal closure state, kembalikan objek baru (`Object.freeze({ ...state })`) untuk mencegah mutasi state internal dari luar.
- [ ] **Strict Typing / Parameter Invariance**: Gunakan assertion monadik atau validation predicate sebelum data masuk ke rantai transformasi.
- [ ] **Bypass Function Instantiation dalam Hot Loops**: Jangan membuat function closure baru di dalam looping intensif ($100.000+$ iterasi); ekstrak fungsi tersebut ke scope luar untuk mempertahankan *Inline Cache (IC)* V8.
- [ ] **Explicit Nullification**: Jika objek besar harus berada dalam lexical scope closure, set referensinya menjadi `null` segera setelah konsumsi selesai.

---

### 12. Hands-on Practice

Buat dan jalankan pipeline pengolahan data telemetri yang hemat memori dan aman dari kebocoran konteks leksikal.

#### File: `hands-on/m02/package.json`
```json
{
  "name": "m02-advanced-fp-closures",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "start": "node telemetry-processor.js",
    "profile": "node --expose-gc telemetry-processor.js"
  }
}
```

#### File: `hands-on/m02/telemetry-processor.js`
```javascript
import { performance } from "node:perf_hooks";

// 1. High-Performance Transducers
const filterT = (predicate) => (step) => (acc, val) =>
  predicate(val) ? step(acc, val) : acc;

const mapT = (mapper) => (step) => (acc, val) =>
  step(acc, mapper(val));

const transduce = (collection, transducer, reducer, initial) => {
  const transform = transducer(reducer);
  let acc = initial;
  for (let i = 0; i < collection.length; i++) {
    acc = transform(acc, collection[i]);
  }
  return acc;
};

// 2. Closure-Based Encapsulated Aggregator (Anti-Leak Verified)
function createTelemetryEngine(engineId) {
  // Context-allocated variable
  let anomalyCount = 0;
  let totalLatency = 0;
  let processedPoints = 0;

  return {
    getProcessor() {
      // Functional Transducer Pipeline
      const isSevere = (record) => record.severity === "CRITICAL" || record.severity === "ERROR";
      const extractMetrics = (record) => ({
        id: record.id,
        latency: record.durationMs,
        isAnomaly: record.durationMs > 1000
      });

      const transducer = (step) =>
        filterT(isSevere)(mapT(extractMetrics)(step));

      const stepReducer = (acc, metric) => {
        processedPoints++;
        totalLatency += metric.latency;
        if (metric.isAnomaly) anomalyCount++;
        acc.push(metric.id);
        return acc;
      };

      return {
        processBatch: (records) => transduce(records, transducer, stepReducer, [])
      };
    },

    getStatistics: () => Object.freeze({
      engineId,
      processedPoints,
      anomalyCount,
      averageLatencyMs: processedPoints > 0 ? (totalLatency / processedPoints).toFixed(2) : 0
    })
  };
}

// 3. Execution Script & Verification
function runSimulation() {
  const engine = createTelemetryEngine("ENG-NODE-PROD-01");
  const processor = engine.getProcessor();

  const mockLogs = Array.from({ length: 500_000 }, (_, i) => ({
    id: `log_${i}`,
    severity: i % 5 === 0 ? "CRITICAL" : i % 2 === 0 ? "INFO" : "ERROR",
    durationMs: (i % 1200) + 10
  }));

  console.log("Memulai pemrosesan 500.000 records...");
  const t0 = performance.now();
  const retainedAnomalyIds = processor.processBatch(mockLogs);
  const t1 = performance.now();

  console.log(`Pemrosesan selesai dalam: ${(t1 - t0).toFixed(2)} ms`);
  console.log("Statistik Engine:", engine.getStatistics());
  console.log(`Total data terfilter: ${retainedAnomalyIds.length}`);
}

runSimulation();
```

#### Langkah Eksekusi & Validasi:
```bash
cd hands-on/m02
npm run start
```
*Expected Output*: Eksekusi 500.000 records harus selesai dalam rentang waktu $\approx 30-70\text{ ms}$ (tergantung CPU) tanpa menyebabkan memory spike atau `JavaScript heap out of memory`.

---

### 13. Exercise

#### Level: Easy
Refaktor fungsi imperatif berikut ke dalam bentuk fungsi murni (*pure function*) yang menerapkan currying:
```javascript
// SOAL
function applyDiscount(taxRate, discount, price) {
  return price - (price * discount) + (price * taxRate);
}
```
*Tugas*: Buat fungsi `curriedApplyDiscount(taxRate)(discount)(price)` yang reusable untuk menghitung pajak tetap (misal PPN 11%).

#### Level: Medium
Diberikan array transaksi berukuran $50.000$ item. Tulis fungsi berbasis **Transducer** untuk memfilter transaksi dengan nilai kelipatan 5, mengalikan nilainya dengan faktor 1.5, dan menjumlahkan totalnya (*reduction*). Bandingkan konsumsi alokasi array antara Transducer versus chained `.filter().map().reduce()`.

#### Level: Hard
Tulis class/closure `MemoizedResolver` yang menerapkan cache berbasis *Least Recently Used (LRU)* murni dengan Functional Closure. Batasan: 
- Ukuran cache maksimal $N$ item.
- Dilarang membocorkan internal hashmap ke luar.
- Setiap pemanggilan harus mencatat cache hit/miss secara terisolasi tanpa global side-effects.

---

### 14. Challenge

**Skenario**: Anda ditugaskan membangun State Container untuk Real-time Financial Matching Engine.
**Spesifikasi Persyaratan**:
1. Bangun fungsi `createMatchingEngine(orderTypes)` yang mengisolasi private state (Orderbook).
2. Engine harus menerima order secara deklaratif via Higher-Order Function `submitOrder(order)`.
3. Gunakan Monad `Result` murni untuk menangani eksekusi transaksi (Success, Rejected: Insufficient Liquidity, Invalid Order Format).
4. State Orderbook tidak boleh menggunakan Class atau `this`. Seluruh data harus terenkapsulasi secara leksikal.
5. **Zero Memory Leak Verification**: Tunjukkan bahwa tidak ada referensi ke order yang dibatalkan (*canceled orders*) yang tersisa di memory via V8 Context Chain setelah proses pembatalan selesai. Buktikan menggunakan skrip dump heap profiling.

---

### 15. Quiz Evaluasi Pemahaman

#### 15.1. Pertanyaan Basic

**Q1: Apa perbedaan struktural alokasi memori antara variabel primitif lokal biasa dan variabel yang ditangkap (*captured*) oleh inner closure di V8 Engine?**
- *Jawaban*: Variabel lokal biasa dialokasikan langsung pada execution stack (Stack Frame) dan dibersihkan instan saat stack di-pop. Variabel yang ditangkap closure dipindahkan oleh V8 ke heap memory dalam bentuk `Context Object` sehingga tetap hidup setelah execution stack fungsi induk dihancurkan.

**Q2: Mengapa metode kompilasi V8 Ignition menciptakan `Context` yang sama untuk fungsi-fungsi yang berada di dalam satu lexical block yang identik?**
- *Jawaban*: Untuk mengoptimalkan pembuatan frame scope dan menghemat overhead parsing. V8 mengelompokkan semua variabel yang lolos (*escaped variables*) dari satu scope leksikal ke dalam satu objek `Context` bersama yang diakses via indeks slot array oleh semua closure di level tersebut.

**Q3: Jelaskan apa yang dimaksud dengan "Point-Free Style" dalam Functional Programming.**
- *Jawaban*: Paradigma penulisan fungsi di mana definisi fungsi tidak secara eksplisit menyebutkan argumen data yang sedang dimanipulasi, melainkan berfokus murni pada komposisi fungsi (misalnya: `const doubleAll = map(double)` alih-alih `const doubleAll = (arr) => arr.map(x => double(x))`).

**Q4: Apa kerugian komputasi terbesar dari rantai metode array standar seperti `arr.map(...).filter(...).slice(...)` pada dataset besar?**
- *Jawaban*: Setiap pemanggilan method menghasilkan alokasi array intermediat baru di V8 Heap, yang memicu lonjakan konsumsi memori dan menyebabkan *Garbage Collection thrashing* (frequent minor/major GC collections).

**Q5: Bagaimana cara transducer mengatasi masalah alokasi array intermediat tersebut?**
- *Jawaban*: Transducer mengubah fungsi transformasi (`map`, `filter`) menjadi reducer transformers yang dapat dikomposisikan. Transformasi dieksekusi secara terpadu (*single pass*) untuk setiap elemen koleksi, memproses item satu per satu langsung ke akumulator akhir tanpa membuat array perantara.

---

#### 15.2. Pertanyaan Intermediate

**Q6: Perhatikan kode berikut. Apakah memori buffer 100MB dapat dibersihkan oleh Garbage Collector saat `trigger` dieksekusi? Jelaskan proses internal V8-nya.**
```javascript
function initModule() {
  const hugeData = Buffer.alloc(100 * 1024 * 1024);
  const debug = () => console.log(hugeData.length);
  return () => "READY";
}
const trigger = initModule();
```
- *Jawaban*: **TIDAK**. `hugeData` tidak dapat di-GC. Fungsi `debug` dan anonymous function yang dikembalikan (`() => "READY"`) berbagi lexical scope yang sama. Akibatnya, keduanya merujuk ke satu objek `Context` V8 yang sama. Karena referensi `trigger` masih hidup di global scope, objek `Context` tersebut tetap ditahan (*retained*), yang pada gilirannya menahan `hugeData` di heap, meskipun `trigger` sendiri tidak pernah memanggil `hugeData`.

**Q7: Bagaimana mekanisme kerja `ScopeInfo` di V8 dalam mencari identifier saat eksekusi closure bersarang (*nested closure*)?**
- *Jawaban*: V8 membaca metadata `ScopeInfo` yang terikat pada fungsi. Saat identifier dicari, V8 memeriksa lokal context slot terlebih dahulu. Jika tidak ditemukan, mesin menelusuri pointer `previous` ke context induk (Scope Chain Walk) secara berulang hingga ke `NativeContext`. Jika identifier ditemukan pada slot index tertentu, mesin menggunakan instruksi `LdaContextSlot [depth, slot_index]` di bytecode.

**Q8: Dalam arsitektur functional programming, mengapa mutasi objek `acc` secara langsung pada reduce step function di dalam transducer diizinkan (*idiomatic*), padahal FP melarang mutasi?**
- *Jawaban*: Mutasi tersebut diizinkan selama bersifat *transient* dan terisolasi secara lokal (*ephemeral mutation*). Karena array akumulator baru dibuat khusus untuk siklus transduce tersebut dan belum dipublikasikan ke luar pipeline, tidak ada efek samping (*side-effects*) yang dapat diobservasi oleh sistem luar (*referential transparency* tetap terjaga dari perspektif pemanggil).

**Q9: Apa dampak penggunaan closure factory yang ekstensif terhadap kinerja Turbofan (JIT Compiler) V8?**
- *Jawaban*: Setiap pemanggilan factory menghasilkan instansiasi objek fungsi baru di heap dengan *code pointers* yang bisa memiliki identitas berbeda. Hal ini dapat membebani *Inline Caches (IC)* jika shapes (*Hidden Classes*) dari fungsi atau state yang dikembalikan bervariasi, berpotensi menurunkan status optimasi dari *Monomorphic* ke *Megamorphic*, yang memicu deoptimasi ke bytecode interpreted (Ignition).

**Q10: Mengapa tipe data `Either` atau `Result` lebih unggul untuk error handling pada high-load production pipeline dibandingkan paradigma `try/catch`?**
- *Jawaban*: Blok `try/catch` menghentikan alur pipeline deklaratif, berpotensi mendeoptimasi V8 compiler pada *hot path*, dan membuat alur data sinkron bercabang secara imperatif. Monad `Either` memperlakukan kegagalan sebagai nilai biasa (*first-class value*), menjaga konsistensi type contract dan kontinuitas functional chaining tanpa biaya overhead rekonstruksi call stack.

---

#### 15.3. Skenario Kasus Produksi

**Skenario 1**:
Sebuah microservice analitik streaming berbasis Node.js mengalami crash dengan pesan `FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory`. Profiling menunjukkan jutaan objek `system / Context` menumpuk di heap. Setelah diaudit, service tersebut menggunakan event broker di mana setiap event mendaftarkan callback closure yang merujuk pada objek konfigurasi besar:
```javascript
function registerHandler(eventEmitter, config) {
  eventEmitter.on("data", (payload) => {
    saveMetrics(payload, config.serviceId);
  });
}
```
*Pertanyaan*: Apa akar masalahnya di tingkat memori V8, dan bagaimana perbaikan arsitekturalnya tanpa mengubah kontrak emitter?
- *Analisis & Solusi*: Akar masalahnya adalah closure callback mendaftarkan referensi ke seluruh objek `config` via lexical scoping context. Meskipun hanya `config.serviceId` yang dibutuhkan, V8 menahan referensi ke keseluruhan objek `config` di dalam `Context` event handler selamanya jika listener tidak di-unregister.
*Perbaikan Arsitektural*: Ekstrak primitif spesifik yang dibutuhkan ke variabel lokal independen sebelum closure dibuat, atau gunakan factory function yang terisolasi:
```javascript
function registerHandler(eventEmitter, config) {
  const serviceId = config.serviceId; // Ekstraksi nilai primitif
  eventEmitter.on("data", (payload) => {
    saveMetrics(payload, serviceId); // Hanya Context slot bertipe string yang ditahan
  });
}
```

**Skenario 2**:
Tim backend Anda mengeluhkan latensi P99 yang melonjak tinggi saat melakukan serialisasi dan validasi data transaksi berukuran 50MB yang diterima dari bulk import batch. Pipeline saat ini:
```javascript
const result = rawBatches
  .filter(validateBatch)
  .map(normalizePayload)
  .filter(checkFraud)
  .map(signTransaction);
```
*Pertanyaan*: Jelaskan metrik apa yang terdegradasi pada level runtime engine, dan rancang pipeline pengganti berbasis functional programming yang memitigasi masalah tersebut secara total!
- *Analisis & Solusi*: Metrik yang terdegradasi adalah **Minor GC Collection Time (Scavenge)** dan **Heap Memory Allocation Rate**. Kode di atas mengalokasikan 4 array perantara baru sebesar puluhan megabyte di memori heap dalam hitungan milidetik.
*Rancangan Solusi*: Ganti menjadi satu Transducer terkomposisi:
```javascript
const transactionTransducer = pipe(
  tFilter(validateBatch),
  tMap(normalizePayload),
  tFilter(checkFraud),
  tMap(signTransaction)
);
const result = transduce(rawBatches, transactionTransducer, (acc, tx) => {
  acc.push(tx);
  return acc;
}, []);
```
Dengan transducer, data diproses dalam satu kali iterasi (*single-pass*), meniadakan seluruh alokasi 4 array temporer, dan memotong latensi GC secara substansial.

**Skenario 3**:
Anda mendesain framework internal untuk multi-tenant data caching. Setiap tenant memiliki alur validasi fungsionalnya sendiri. Engineer junior menulis kode:
```javascript
function createTenantPipeline(tenantRules) {
  return function processRequest(request) {
    const enrichedRules = { ...tenantRules, timestamp: Date.now() };
    return (data) => enrichedRules.validator(data, request);
  };
}
```
Setelah berjalan 24 jam, server mengalami *slow memory leak*.
*Pertanyaan*: Mengapa arsitektur closure berlapis ini menyebabkan memory leak laten, dan bagaimana perbaikannya?
- *Analisis & Solusi*: Setiap kali `processRequest` dipanggil, objek baru `enrichedRules` dialokasikan di dalam heap Context fungsi `processRequest`. Fungsi terdalam `(data) => ...` kemudian dikembalikan ke luar, menahan referensi ke context `processRequest` tersebut yang berisi `request` dan `enrichedRules`. Jika fungsi terdalam ini disimpan dalam cache jangka panjang, seluruh instance `request` (beserta socket, header, dan payload yang menempel padanya) tidak akan pernah bisa di-GC.
*Perbaikan Arsitektural*: Pisahkan dependensi waktu dan request. Jangan buat closure bersarang di dalam request loop jika closure tersebut akan berumur lebih panjang dari lifecycle request tersebut. Deserialisasi dan flatten eksekusi validasi secara sinkron tanpa menyimpan inner escaping function:
```javascript
function createTenantPipeline(tenantRules) {
  const validator = tenantRules.validator;
  return function processRequest(request, data) {
    return validator(data, request, tenantRules);
  };
}
```

---

### 16. Summary

1. **V8 Context Mechanics**: Closure tidak bekerja secara "ajaib". Jika variabel leksikal lolos (*escapes*) dari lifecycle stack frame, V8 mentransformasikannya ke dalam objek heap berbasis array yang disebut `Context`. Variabel diakses melalui instruksi bytecode berindeks slot.
2. **The Danger of Shared Lexical Scopes**: Closure yang berada dalam satu lexical block berbagi `Context` yang sama. Satu variabel besar yang tertahan di satu closure dapat mencegah pembersihan GC dari closure lain yang berada dalam scope tersebut, memicu kebocoran memori laten di enterprise systems.
3. **Transducers for Production Scale**: Pada transformasi array berskala besar, method chaining standar menghasilkan alokasi memori intermediat $O(K \times N)$. Transducers memampatkan transformasi fungsional ke dalam $O(1)$ intermediate allocation dan satu siklus traversal $O(N)$.
4. **Architectural Purity**: Mengawinkan enkapsulasi closure murni dengan Monadic Error Handling (`Either`/`Result`) memungkinkan rekayasa sistem yang imun terhadap mutasi state eksternal, tahan terhadap konkurensi asinkron, dan mudah diverifikasi melalui unit testing deterministik.