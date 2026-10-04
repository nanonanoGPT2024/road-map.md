# Bab 01: Arsitektur Runtime & Fondasi Eksekusi JavaScript
## Module 01: JavaScript Engine Internals, Execution Context, dan Memory Management

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis (C4)** siklus hidup kode JavaScript dari parsing kode mentah, Abstract Syntax Tree (AST), kompilasi JIT (Just-In-Time) pada V8 Engine, hingga eksekusi mesin.
- **Mengevaluasi (C5)** struktur *Execution Context* (Global, Function, Block) dan pergerakan *Call Stack* untuk mendiagnosis anomali alur eksekusi asinkron dan rekursif.
- **Mengidentifikasi dan Mencegah (C3)** *Memory Leaks* dengan memetakan alokasi data primitif vs referensi pada *V8 Memory Heap* dan memahami siklus hidup *Garbage Collection* (Scavenger & Mark-Sweep-Compact).
- **Mengimplementasikan (C3)** mitigasi kegagalan runtime terkait *Call Stack Overflow* menggunakan teknik arsitektural seperti rekursi bertahap (*trampolining*) dan pembatasan kedalaman eksekusi.
- **Merancang (C6)** pola kode yang optimal terhadap mekanisme optimasi compiler V8 (*Hidden Classes* dan *Inline Caches*).

---

### 2. Conceptual Foundation
JavaScript pada intinya adalah bahasa pemrograman tingkat tinggi, *single-threaded*, *garbage-collected*, dengan model eksekusi berbasis *event-driven non-blocking I/O*. Landasan formal arsitektur JavaScript diatur oleh spesifikasi **ECMA-262 (ECMAScript)**.

Secara teoritis, eksekusi kode JavaScript didasarkan pada konsep mesin abstrak yang mengelola:
1. **Agent Architecture**: Berdasarkan spesifikasi ECMA-262 Bagian 9, sebuah *Agent* terdiri dari thread eksekusi, satu set *Execution Context Stack* (*Call Stack*), dan *Memory Heap*.
2. **Execution Context (EC)**: Struktur internal virtual yang melacak evaluasi runtime dari sebuah kode. EC terdiri dari:
   - **LexicalEnvironment**: Komponen yang mencatat asosiasi identifier-ke-nilai berdasarkan struktur leksikal statis (mengelola binding `let`, `const`, fungsi, dan referensi ke lingkungan luar / *outer environment*).
   - **VariableEnvironment**: Komponen LexicalEnvironment yang secara spesifik menampung binding dari deklarasi `var` dalam fungsi.
   - **ThisBinding**: Nilai deterministik yang terikat pada kata kunci `this` saat konteks dibuat.
3. **Environment Record**: Mekanisme penyimpanan nyata dari *LexicalEnvironment* yang memetakan identifier token ke variabel dan fungsinya secara langsung.

```
+-------------------------------------------------------------------+
|                        Execution Context                          |
|  +-------------------------------------------------------------+  |
|  | LexicalEnvironment:                                         |  |
|  |   - EnvironmentRecord (Declarative: let, const, class)      |  |
|  |   - OuterEnvReference (Pointer ke scope induk leksikal)     |  |
|  +-------------------------------------------------------------+  |
|  +-------------------------------------------------------------+  |
|  | VariableEnvironment:                                        |  |
|  |   - EnvironmentRecord (Record: var bindings)                |  |
|  +-------------------------------------------------------------+  |
|  +-------------------------------------------------------------+  |
|  | ThisBinding: <Resolve-on-Invocation Context Object>         |  |
|  +-------------------------------------------------------------+  |
+-------------------------------------------------------------------+
```

---

### 3. Why This Matters
Dalam arsitektur sistem berskala besar (*enterprise-grade*), kegagalan memahami cara kerja runtime JavaScript di balik lapisan abstraksi menghasilkan kerentanan kritis:
- **Event Loop Starvation & Stack Exhaustion**: Pemanggilan komputasi CPU-bound atau pemanggilan fungsi rekursif tak terbatas yang memblokir *Call Stack* akan melumpuhkan responsivitas seluruh server berbasis Node.js.
- **Memory Bloat & Out-Of-Memory (OOM) Crashes**: Kebocoran memori pada Heap (misalnya melalui penutupan scope leksikal / *closures* yang tidak terlepas) mengakibatkan V8 engine melakukan proses *Garbage Collection* secara agresif (*stop-the-world phases*), meningkatkan latensi P99 API secara drastis sebelum akhirnya proses di-*kill* oleh kernel OS melalui OOM Killer.
- **De-optimizations**: Menulis kode yang secara konstan memutasi bentuk objek (*dynamic shape mutation*) memaksa V8 beralih dari kode mesin teroptimasi (*TurboFan*) kembali ke interpretasi *bytecode* (*Ignition*), menurunkan *throughput* komputasi hingga ratusan kali lipat.

---

### 4. What It Is vs What It Isn't

| Fitur / Karakteristik | Apa Itu Sebenarnya (What It Is) | Apa yang Sering Disalahpahami (What It Isn't) |
|---|---|---|
| **JavaScript Engine** | Penterjemah dan kompilator JIT (misal: V8, JavaScriptCore, SpiderMonkey) yang memproses JS menjadi instruksi mesin native. | Bukan keseluruhan runtime; tidak mencakup `setTimeout`, `DOM`, `fetch`, atau filesystem APIs. |
| **Execution Context** | Entitas internal spesifikasi ECMA-262 yang mengelola status runtime dan resolusi variabel. | Bukan objek literal JavaScript global seperti `window` atau `globalThis`. |
| **Call Stack** | Struktur data LIFO (*Last-In, First-Out*) di memory stack yang mengelola frame pemanggilan fungsi secara sinkron. | Bukan antrean asinkron (*Task Queue* atau *Microtask Queue*). |
| **Hoisting** | Perilaku akibat fase inisialisasi alokasi memori pada *Environment Record* sebelum interpretasi instruksi baris per baris. | Kode fisik tidak "dipindahkan" atau "ditarik" ke baris atas file oleh engine. |
| **Temporal Dead Zone (TDZ)** | Periode waktu eksekusi antara inisialisasi scope leksikal dan baris deklarasi aktual dari identifier `let`/`const`. | Bukan berarti variabel belum ada di engine; identifier telah terdaftar di Environment Record namun belum diinisialisasi nilainya. |

---

### 5. How It Works Under the Hood
Alur kerja pemrosesan kode pada JavaScript Engine modern (berbasis Google V8) terdiri dari siklus terstruktur:

```
[Source Code] 
      │
      ▼
[Scanner / Lexer] ──► Token Stream
      │
      ▼
[Parser] ───────────► AST (Abstract Syntax Tree)
      │
      ▼
[Ignition] ─────────► V8 Bytecode (Interpreted Execution)
      │
      ├───────────────────────┐
      ▼                       ▼
[Execution Feedback]    [TurboFan Compiler]
(Type Profiling)              │ (Optimized Machine Code)
      │                       ▼
      └────────────────► [De-optimization] (Jika asumsi tipe berubah)
```

1. **Parsing Phase**:
   - **Lexer/Scanner**: Mengonversi deretan karakter string kode sumber menjadi rentetan token leksikal.
   - **Parser**: Memvalidasi sintaks dan membentuk *Abstract Syntax Tree* (AST) serta meregistrasi deklarasi variabel pada cakupan leksikal masing-masing (*Scope Analysis*).

2. **Compilation Phase (Ignition)**:
   - AST diubah menjadi instruksi *V8 Bytecode*. Bytecode ini lebih ringkas daripada kode mesin native dan dapat dieksekusi langsung oleh interpreter *Ignition*.

3. **Optimization Phase (TurboFan)**:
   - Ketika suatu segmen kode (fungsi) sering dieksekusi (*hot code*), V8 mengumpulkan informasi profil tipe data (*Type Feedback*).
   - *TurboFan* mengambil bytecode dan profil tersebut, lalu mengompilasinya langsung menjadi *Optimized Machine Code* (x86_64, ARM64) dengan asumsi tipe data stabil.
   - Jika tipe data argumen berubah secara dinamis di runtime (misal: sebelumnya selalu menerima `number`, tiba-tiba menerima `string`), TurboFan membatalkan optimasi (*de-optimization*) dan mengembalikan eksekusi ke interpreter *Ignition*.

4. **Memory Allocation: Stack vs Heap**:
   - **Stack Memory**: Menyimpan nilai primitif yang ukurannya diketahui dan statis (seperti `number`, `boolean`, `null`, `undefined`, pointer referensi), serta frame eksekusi pemanggilan fungsi (*Call Frame*). Akses baca/tulis bernilai $O(1)$.
   - **Heap Memory**: Ruang memori tidak terstruktur yang besar untuk menyimpan objek dinamis (*Object*, *Array*, *Function instances*, *Closures*).
   - **Garbage Collection (GC)**: Menggunakan arsitektur generasional:
     - *New Space (Nursery & Intermediate)*: Dikelola oleh *Scavenger algorithm* (berbasis Cheney's copying algorithm) untuk alokasi objek baru berusia pendek.
     - *Old Space*: Objek yang bertahan dari dua siklus Scavenger dipromosikan ke sini, dikelola menggunakan *Major GC (Mark-Sweep-Compact)*.

---

### 6. System Architecture Diagram
Diagram berikut mengilustrasikan interaksi menyeluruh antara V8 Engine, Memory layout, Call Stack, dan integrasi Runtime Environment Host (seperti Node.js atau Web Browser API):

```
+----------------------------------------------------------------------------------------------------+
|                                    HOST RUNTIME ENVIRONMENT (e.g., Node.js / Chromium)             |
|                                                                                                    |
|  +------------------------------------ V8 JAVASCRIPT ENGINE ------------------------------------+  |
|  |                                                                                              |  |
|  |  +--------------------------- MEMORY HEAP ----------------------------+   +--- CALL STACK -+ |  |
|  |  |                                                                    |   |                | |  |
|  |  |  +-------------------+  +-------------------+  +----------------+  |   | [ Frame: baz ] | |  |
|  |  |  | New Space         |  | Old Pointer Space |  | Map Space      |  |   | [ Frame: bar ] | |  |
|  |  |  | (Scavenger Zone)  |  | (Mark-Sweep Zone) |  | (Hidden Class) |  |   | [ Frame: foo ] | |  |
|  |  |  | [Obj A] [Obj B]   |  | [Persistent Data] |  | [Shape Struct] |  |   | [ GlobalFrame] | |  |
|  |  |  +-------------------+  +-------------------+  +----------------+  |   +----------------+ |  |
|  |  |                                                                    |           │          |  |
|  |  |  +-------------------+  +-------------------+  +----------------+  |           │ Invokes  |  |
|  |  |  | Large Object Space|  | Code Space        |  | Dynamic Closure|  |           ▼          |  |
|  |  |  | (Exceeds NewSpace)|  | (JIT Native Code) |  | Context Record |  |   +----------------+ |  |
|  |  |  +-------------------+  +-------------------+  +----------------+  |   | Host Web/C++   | |  |
|  |  +--------------------------------------------------------------------+   | Bindings       | |  |
|  |                                                                           +----------------+ |  |
|  +-----------------------------------------------------------------------------------|----------+  |
|                                                                                      │             |
|                               Delegates Asynchronous Work                            │             |
|                                                                                      ▼             |
|  +----------------------------- HOST INFRASTRUCTURE --------------------------------------------+  |
|  |                                                                                               |  |
|  |  [ Web APIs / Libuv Threadpool ]  ──► (Network, Filesystem, Timers OS Thread Execution)       |  |
|  |                                                        │                                      |  |
|  |                                                        ▼ Resolves                             |  |
|  |  [ Microtask Queue (Promises, queueMicrotask) ]  ──► High Priority Processing                 |  |
|  |  [ Macrotask Queue (setTimeout, I/O Events)   ]  ──► Normal Priority Processing                 |  |
|  |                                                        │                                      |  |
|  |                                                        ▼ Polled By                            |  |
|  |                                                 [ EVENT LOOP ]                                |  |
|  |                                                        │                                      |  |
|  |                                                        └──► Pushes Callback to Call Stack     |  |
|  |                                                             (when Call Stack is completely    |  |
|  |                                                              empty)                           |  |
|  +-----------------------------------------------------------------------------------------------+  |
+----------------------------------------------------------------------------------------------------+
```

---

### 7. Core Syntax & API Reference

#### Spesifikasi Lifecycle Execution Context (ECMA-262 §10)
Setiap eksekusi fungsi menghasilkan frame baru dengan fase:
1. **Creation Phase**:
   - Pembuatan *LexicalEnvironment* dan *VariableEnvironment*.
   - Binding `var` diinisialisasi sebagai `undefined`.
   - Binding fungsi deklaratif disimpan langsung sebagai instansiasi fungsi utuh di Heap (*Function Hoisting*).
   - Binding `let` dan `const` dialokasikan secara leksikal tanpa inisialisasi (*Uninitialized* status, memicu *TDZ* jika diakses).
2. **Execution Phase**:
   - Instruksi dijalankan baris demi baris.
   - Variabel `let`/`const` diisi nilainya pada baris evaluasi.
   - Perhitungan logika, alokasi memori dinamis, dan manipulasi referensi pointer.

#### Format Konsep Representation Internal (Pseudo-spec):
```typescript
interface ExecutionContext {
  lexicalEnvironment: {
    environmentRecord: DeclarativeEnvironmentRecord | ObjectEnvironmentRecord;
    outer: ExecutionContext['lexicalEnvironment'] | null;
  };
  variableEnvironment: {
    environmentRecord: DeclarativeEnvironmentRecord;
    outer: ExecutionContext['variableEnvironment'] | null;
  };
  privateEnvironment: PrivateEnvironmentRecord | null;
  codeEvaluationState: GeneratorState | asyncState | null;
  Function: FunctionObject | null;
  Realm: RealmRecord;
  ScriptOrModule: ScriptRecord | ModuleRecord;
}
```

---

### 8. Code Implementation: Minimal
Contoh deterministik murni untuk memverifikasi fasa pembuatan vs fasa eksekusi (*Hoisting*, *Temporal Dead Zone*, dan isolasi *Lexical Scope*). Simpan dan jalankan langsung dengan Node.js:

```javascript
/**
 * File: minimal_execution_context.js
 * Deskripsi: Demonstrasi presisi perilaku Creation Phase vs Execution Phase.
 */

'use strict';

console.log('--- 1. Variable Environment (var) vs Lexical Environment (let) ---');

// Fase Creation: 'hoistedVar' dialokasikan dan diberi nilai default undefined.
console.log('Nilai hoistedVar sebelum assignment:', hoistedVar); // Output: undefined

var hoistedVar = 'Saya dialokasikan di VariableEnvironment';
console.log('Nilai hoistedVar setelah assignment:', hoistedVar); // Output: String

try {
  // TDZ Verification: 'tdzLet' sudah dicatat di LexicalEnvironment,
  // tetapi belum terinisialisasi. Akses sebelum assignment melempar ReferenceError.
  // @ts-ignore
  console.log(tdzLet);
} catch (err) {
  console.error('TDZ Trap Berhasil Terdeteksi:', err.name, '-', err.message);
}

let tdzLet = 'Nilai tdzLet diinisialisasi di sini';
console.log('Nilai tdzLet setelah inisialisasi:', tdzLet);

console.log('\n--- 2. Function Declaration Hoisting vs Function Expression ---');

// Function Declaration: Seluruh bodi fungsi di-hoist pada Creation Phase.
console.log('Hasil panggil deklarasi fungsi:', declaredFunction()); // Output: 42

function declaredFunction() {
  return 42;
}

try {
  // Function Expression: 'expressionFunc' berstatus undefined saat fasa ini jika dideklarasikan via var.
  // @ts-ignore
  expressionFunc();
} catch (err) {
  console.error('Function Expression Trap:', err.name, '-', err.message); 
  // TypeError: expressionFunc is not a function
}

var expressionFunc = function () {
  return 100;
};
```

---

### 9. Code Implementation: Practical
Implementasi penjejak konteks eksekusi (*Execution Context Call-Depth Tracer*) dan *Memory Allocation Inspector* siap-produksi menggunakan Node.js core modules (`perf_hooks`, `v8`). Program ini mengontrol dan mengukur batas beban eksekusi stack serta mendeteksi lonjakan alokasi Heap.

```javascript
/**
 * File: execution_tracer.js
 * Node.js Runtime: >= 18.0.0
 * Deskripsi: Production-grade contextual frame inspector dan memory tracker.
 */

import { performance } from 'node:perf_hooks';
import v8 from 'node:v8';

/**
 * @typedef {Object} ExecutionReport
 * @property {string} operationName
 * @property {number} executionTimeMs
 * @property {number} stackDepth
 * @property {number} heapUsedDeltaBytes
 * @property {boolean} success
 * @property {string|null} error
 */

export class ExecutionContextTracer {
  /** @type {number} */
  #maxStackLimit;

  /**
   * @param {number} [maxStackLimit=1000] - Batas kedalaman stack protektif.
   */
  constructor(maxStackLimit = 1000) {
    this.#maxStackLimit = maxStackLimit;
  }

  /**
   * Mengukur kedalaman Call Stack saat ini via Stack Trace API V8.
   * @returns {number}
   */
  getCallStackDepth() {
    const target = {};
    Error.captureStackTrace(target, this.getCallStackDepth);
    if (!target.stack) return 0;
    // Hitung baris trace (setiap frame direpresentasikan per baris diawali "at ")
    return target.stack.split('\n').filter(line => line.trim().startsWith('at ')).length;
  }

  /**
   * Menjalankan operasi fungsional di bawah pengawasan performa, memory heap, dan stack limit.
   * @template T
   * @param {string} label
   * @param {(currentDepth: number) => T} task
   * @returns {{ result: T | null, report: ExecutionReport }}
   */
  traceExecution(label, task) {
    const initialHeap = process.memoryUsage().heapUsed;
    const initialDepth = this.getCallStackDepth();
    const startTime = performance.now();

    let result = null;
    let errorCaptured = null;
    let finalDepth = initialDepth;

    try {
      if (initialDepth >= this.#maxStackLimit) {
        throw new RangeError(`Execution Aborted: Initial stack depth (${initialDepth}) exceeds limit (${this.#maxStackLimit}).`);
      }
      
      // Eksekusi tugas target
      result = task(initialDepth);
      finalDepth = this.getCallStackDepth();
    } catch (err) {
      errorCaptured = err instanceof Error ? `${err.name}: ${err.message}` : String(err);
    } finally {
      const endTime = performance.now();
      const finalHeap = process.memoryUsage().heapUsed;

      const report = {
        operationName: label,
        executionTimeMs: Number((endTime - startTime).toFixed(4)),
        stackDepth: finalDepth,
        heapUsedDeltaBytes: finalHeap - initialHeap,
        success: errorCaptured === null,
        error: errorCaptured
      };

      return { result, report };
    }
  }
}

// ==========================================
// DEMONSTRASI PENGGUNAAN PRODUCTION PATTERN
// ==========================================

const tracer = new ExecutionContextTracer(500);

// Kasus A: Operasi Alokasi Array Besar (Uji Heap Allocator)
const arrayTest = tracer.traceExecution('Massive Allocation', (depth) => {
  const dataset = [];
  for (let i = 0; i < 50000; i++) {
    dataset.push({ id: i, hash: `idx_${i}_${depth}` });
  }
  return dataset.length;
});

console.log('Laporan Alokasi Array:', JSON.stringify(arrayTest.report, null, 2));

// Kasus B: Rekursi Terkendali
function recursiveWorker(n, tracerInstance) {
  const currentDepth = tracerInstance.getCallStackDepth();
  if (currentDepth > 450) {
    throw new RangeError(`Sirkuit Pengaman Terbuka: Stack depth mencapai ${currentDepth}`);
  }
  if (n <= 1) return 1;
  return n + recursiveWorker(n - 1, tracerInstance);
}

const recursionTest = tracer.traceExecution('Recursive Computation', () => {
  return recursiveWorker(50, tracer);
});

console.log('Laporan Rekursi Terkendali:', JSON.stringify(recursionTest.report, null, 2));

// Kasus C: Dump V8 Heap Statistics Realtime
console.log('\nV8 Core Heap Statistics:');
console.table(v8.getHeapSpaceStatistics().map(space => ({
  Space: space.space_name,
  SizeMB: (space.space_size / (1024 * 1024)).toFixed(2),
  UsedMB: (space.space_used_size / (1024 * 1024)).toFixed(2),
  AvailableMB: (space.space_available_size / (1024 * 1024)).toFixed(2)
})));
```

---

### 10. Edge Cases, Gotchas & Failure Modes

#### 1. Temporal Dead Zone pada Default Parameter Functions
Ketika parameter fungsi merujuk ke dirinya sendiri atau parameter berikutnya sebelum deklarasi tereksekusi:
```javascript
// FAILURE MODE:
// Parameter dievaluasi dari kiri ke kanan dalam lingkup Lexical Scope parameter tersendiri.
function invalidScope(a = b, b = 2) {
  return a + b;
}

try {
  invalidScope(); // ReferenceError: Cannot access 'b' before initialization
} catch (e) {
  console.error('Edge Case 1 Error:', e.message);
}
```

#### 2. Call Stack Overflow via Rekursi Naif
Eksekusi fungsi rekursif tanpa kondisi terminasi pasti atau dengan *depth* melampaui alokasi ukuran stack OS V8 (rata-rata ~10.000 frame tergantung ukuran memory frame).
```javascript
// FAILURE MODE:
function blowStack(counter = 0) {
  return blowStack(counter + 1);
}

try {
  blowStack();
} catch (e) {
  // V8 melempar RangeError spesifik
  console.error('Edge Case 2 Error:', e instanceof RangeError, e.message);
  // Output: true "Maximum call stack size exceeded"
}
```

#### 3. Closure Memory Leak via Retention Context Gabungan
V8 membagikan konteks leksikal induk (`Context`) ke seluruh *closure* yang berada di dalam *outer scope* yang sama. Jika satu closure menahan data masif, closure lain yang berumur panjang tanpa sengaja akan mencegah GC membersihkan data tersebut:
```javascript
let leakyHolder;

function createLeak() {
  const massivePayload = new Uint8Array(50 * 1024 * 1024); // 50 MB di Heap

  // Closure 1: Fungsi yang tidak pernah dipanggil, menahan referensi massivePayload
  function unusedWorker() {
    if (massivePayload.length > 0) return true;
  }

  // Closure 2: Fungsi ringan yang diekspor ke scope global
  return function lightweightExport() {
    return 'Payload successfully retained in hidden scope context';
  };
}

// Set leakyHolder global
leakyHolder = createLeak();
// massivePayload TIDAK BISA di-garbage-collect karena lightweightExport 
// berbagi Lexical Context Environment yang sama dengan unusedWorker.
```

---

### 11. Performance & Memory Implications

#### 1. Big-O Algoritma Runtime Internal

| Mekanisme Engine | Kompleksitas Waktu | Kompleksitas Ruang | Catatan Performa |
|---|---|---|---|
| Frame Push/Pop pada Call Stack | $O(1)$ | $O(1)$ per frame | Sangat cepat; dialokasikan pada memory contiguous stack. |
| Resolusi Variabel (Scope Walk) | $O(D)$ di mana $D$ = kedalaman Scope Chain | $O(1)$ | Scope lokal diakses via index offset array ($O(1)$). Scope global berantai memerlukan traversal pointer. |
| Alokasi Memory Heap | Amortized $O(1)$ | $O(N)$ ukuran data | Memerlukan alokasi pointer di heap; memicu GC overhead jika space penuh. |
| Scavenge Garbage Collection | $O(S)$ di mana $S$ = Objek aktif yang bertahan | $O(S)$ | Sangat cepat; hanya memproses objek yang masih memiliki referensi di New Space. |
| Mark-Sweep-Compact GC | $O(H)$ di mana $H$ = Seluruh ukuran Heap | $O(1)$ aux | Terjadi *Stop-The-World*; memicu penurunan frame rate / lonjakan latensi jika heap > 2GB. |

#### 2. V8 Hidden Classes (`Maps`) & Inline Caching (IC)
- JavaScript tidak memiliki class statis di tingkat CPU. V8 menciptakan internal *Hidden Class* (`Map`) untuk setiap bentuk (*shape*) objek.
- Jika Anda menginisialisasi objek dan menambahkan properti dalam urutan yang berbeda:
```javascript
// DEOPTIMIZATION SMELLED: Dua Map berbeda tercipta di Map Space V8!
const obj1 = {};
obj1.x = 10;
obj1.y = 20; // Transition: Empty -> Map1 -> Map2

const obj2 = {};
obj2.y = 20;
obj2.x = 10; // Transition: Empty -> Map3 -> Map4 (Polymorphic/Megamorphic IC)
```
- **Dampak Performa**: Fungsi yang menerima `obj1` dan `obj2` tidak dapat menggunakan *Monomorphic Inline Cache*, memaksa CPU melakukan kalkulasi hash lookup dinamis ($O(N)$ alih-alih $O(1)$ *offset load*).

---

### 12. Security Considerations

#### Kerentanan Terkait:
1. **CWE-400: Uncontrolled Resource Consumption (Call Stack Depletion)**
   - *Attack Vector*: Pengguna mengirim payload JSON dengan struktur nested yang terlampau dalam (misal: payload GraphQL bertingkat 5.000 level atau JSON bersarang).
   - *Exploit*: Parser rekursif memicu *Maximum call stack size exceeded*, merusak (*crash*) thread Node.js utama secara instan (*Denial of Service*).
   - *Mitigasi*: Validasi kedalaman payload menggunakan parser streaming non-rekursif (misalnya `JSONStream`) atau parser berbasis loop iteratif dengan batasan kedalaman token maksimal.

2. **CWE-1321: Prototype Pollution via Global Context Interference**
   - *Attack Vector*: Menulis properti ke `Object.prototype` melalui parameter input yang tidak tervalidasi (`__proto__`).
   - *Exploit*: Karena semua objek menuruni *Scope Chain* dan rantai prototipe dari root context, polusi atribut dapat membajak logika otentikasi di seluruh runtime.
   - *Mitigasi*: Lindungi objek global menggunakan `Object.freeze(Object.prototype)` pada bootstrap awal runtime atau gunakan `Object.create(null)` untuk dictionary murni.

```javascript
// Mitigasi Keamanan: Mengunci Object Prototype dasar dari manipulasi leksikal runtime
Object.freeze(Object.prototype);

const maliciousPayload = JSON.parse('{"__proto__": {"isAdmin": true}}');
const targetUser = {};

// Upaya exploit
try {
  // @ts-ignore
  targetUser.__proto__.isAdmin = maliciousPayload.__proto__.isAdmin;
} catch (e) {
  // Mutasi ditolak karena Object.prototype dibekukan
}

console.log('Exploit dicegah, status isAdmin:', ({}).isAdmin); // Output: undefined
```

---

### 13. Architectural Trade-offs & Comparisons

| Parameter Evaluasi | Model A: Single-Threaded Event Loop (Native Node.js / V8) | Model B: Multi-Threaded Isolate Worker (`worker_threads`) |
|---|---|---|
| **Memory Footprint** | Rendah (~30MB baseline per proses). Memori heap dikelola bersama dalam thread tunggal. | Tinggi (~30MB *tambahan* per worker). Setiap Worker Thread menginstansiasi V8 Isolate baru lengkap dengan Call Stack dan Heap mandiri. |
| **Concurrency Latency** | Sangat rendah untuk tugas I/O bound. Overhead context switching minimal. | Terdapat serialization/deserialization delay via `postMessage` (Structured Clone Algorithm) kecuali menggunakan `SharedArrayBuffer`. |
| **Fault Isolation** | Rendah. Unhandled `RangeError` (Stack Overflow) atau OOM Exception mematikan seluruh proses aplikasi. | Tinggi. Kegagalan fatal di satu Worker thread tidak langsung merusak isolat utama host thread. |
| **Throughput Profiling** | Sangat rentan terhadap degradasi komputasi CPU-bound (Event Loop Starvation). | Ideal untuk tugas enkripsi, pengolahan gambar, pemrosesan komputasi berat paralel. |

---

### 14. Best Practices & Production Guidelines

#### Aturan Mutlak Menulis Kode yang Selaras dengan V8 Engine:
1. **Selalu Gunakan `const` secara Default, `let` Jika Perlu, Jangan Pernah `var`**:
   - Menghilangkan anomali hoisting fasa creation.
   - Memastikan scope leksikal terkunci secara lokal pada level blok (`{ ... }`), mempermudah analisis statis compiler dan GC engine.
2. **Inisialisasi Seluruh Atribut Objek pada Constructor / Factory Function**:
   - Selalu inisialisasi properti dengan tipe data yang konsisten pada urutan yang identik untuk mempertahankan *Hidden Class Monomorphism*.
   - Jangan pernah menghapus properti objek menggunakan kata kunci `delete` karena hal ini langsung memodifikasi Map objek menjadi struktur *Dictionary Mode* (memperlambat performa akses properti hingga ~10x). Gunakan reassignment `null` atau `undefined` jika nilainya kosong.
3. **Konfigurasikan Batas Heap Engine secara Eksplisit pada Skala Kontainer**:
   - Jika berjalan di Docker/Kubernetes dengan limit memori (misal: 1GB), set parameter Node.js:
     ```bash
     node --max-old-space-size=768 --max-semi-space-size=64 server.js
     ```
   - *Rasio Aturan*: Sisakan 25–30% dari total alokasi RAM kontainer untuk Stack, Buffer C++, code space V8, dan overhead OS threadpool libuv.

---

### 15. Anti-Patterns & Code Smells

#### Anti-Pattern 1: Accidental Global Binding (Leaking ke Global Execution Context)
```javascript
// ❌ BURUK: Variabel bocor ke global variable environment (Window / globalThis)
function calculateMetrics(data) {
  // Lupa menuliskan 'const', 'let', atau mode strict mati
  accumulatedTotal = data.reduce((a, b) => a + b, 0); 
  return accumulatedTotal;
}

// ✅ BAIK: Variabel terisolasi di Function Lexical Environment
function calculateMetricsOptimized(data) {
  'use strict';
  const accumulatedTotal = data.reduce((a, b) => a + b, 0);
  return accumulatedTotal;
}
```

#### Anti-Pattern 2: Mutasi Bentuk Objek Dinamis (Shape Polymorphism Mutation)
```javascript
// ❌ BURUK: Properti ditambah dinamis secara acak, merusak Inline Cache
function registerMetric(point, isWarning) {
  const metric = { timestamp: Date.now(), val: point };
  if (isWarning) {
    metric.flag = 'WARNING'; // Hidden Class berubah (Bifurcation)
  }
  return metric;
}

// ✅ BAIK: Deklarasikan skema properti lengkap secara seragam (Monomorphic)
function registerMetricOptimized(point, isWarning) {
  return {
    timestamp: Date.now(),
    val: point,
    flag: isWarning ? 'WARNING' : null // Bentuk Map identik 100%
  };
}
```

#### Anti-Pattern 3: Inefisiensi Rekursi Berakibat Call Stack Exhaustion
```javascript
// ❌ BURUK: Rekursi langsung menyebabkan Call Stack meledak jika N besar
function sumUpTo(n) {
  if (n <= 1) return n;
  return n + sumUpTo(n - 1); // Mempertahankan frame saat ini untuk operasi penjumlahan
}

// ✅ BAIK: Rekursi berbasis Trampoline (Mengubah alur stack menjadi iterasi heap loop)
function trampoline(fn) {
  return function (...args) {
    let result = fn(...args);
    while (typeof result === 'function') {
      result = result(); // Stack di-pop terlebih dahulu sebelum step berikutnya dipanggil
    }
    return result;
  };
}

function sumUpToSafe(n, acc = 0) {
  if (n <= 0) return acc;
  return () => sumUpToSafe(n - 1, acc + n); // Mengembalikan thunk function
}

const safeSum = trampoline(sumUpToSafe);
console.log('Trampolined calculation (safe):', safeSum(1000000)); // Berhasil tanpa RangeError!
```

---

### 16. Testing & Quality Assurance
Gunakan native test runner Node.js (`node:test`) untuk memvalidasi batasan Execution Context, pemenuhan TDZ, dan pencegahan overflow secara deterministik.

```javascript
/**
 * File: runtime_foundation.test.js
 * Eksekusi: node --test runtime_foundation.test.js
 */

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

describe('JavaScript Engine & Execution Context Suite', () => {

  test('Validasi Siklus Hidup Temporal Dead Zone (TDZ)', () => {
    const executeTdzBlock = () => {
      // Evaluasi kode dinamis untuk mendemonstrasikan ReferenceError TDZ
      const fn = new Function(`
        {
          const val = x;
          let x = 10;
          return val;
        }
      `);
      fn();
    };

    assert.throws(
      () => executeTdzBlock(),
      {
        name: 'ReferenceError',
        message: /Cannot access 'x' before initialization/
      },
      'Mengakses identifier let di TDZ harus menghasilkan ReferenceError'
    );
  });

  test('Call Stack Isolation antar Instance Function Execution Context', () => {
    let executionDepth = 0;
    
    function isolateFrame(step) {
      const internalId = step; // Dialokasikan terpisah di stack frame unik masing-masing
      executionDepth++;
      if (step > 1) {
        isolateFrame(step - 1);
      }
      // Verifikasi integritas variabel leksikal frame saat unwinding
      assert.equal(internalId, step, 'Data lokal pada stack frame tidak boleh terkorupsi');
    }

    isolateFrame(10);
    assert.equal(executionDepth, 10, 'Total frame eksekusi harus persis bernilai 10');
  });

  test('Deteksi dan Penanganan Call Stack Overflow Terkendali', () => {
    let depth = 0;
    
    function triggerOverflow() {
      depth++;
      triggerOverflow();
    }

    assert.throws(
      () => triggerOverflow(),
      (err) => {
        assert.ok(err instanceof RangeError);
        assert.match(err.message, /Maximum call stack size exceeded/);
        assert.ok(depth > 1000, `Stack harus mampu menampung minimal 1000 frame (tercatat: ${depth})`);
        return true;
      },
      'Stack exhaustion harus ditangkap sebagai RangeError V8'
    );
  });

  test('Integritas Objek Referensi di Heap Memory vs Primitif di Stack', () => {
    // Uji mutasi reference pointer vs value copy
    let primitiveOriginal = 50;
    let primitiveCopy = primitiveOriginal;
    primitiveCopy = 100;

    assert.equal(primitiveOriginal, 50, 'Nilai primitif stack asli tidak boleh bermutasi');

    const heapObjectSource = { counter: 50 };
    const heapObjectReference = heapObjectSource; // Menyalin memory pointer alamat heap yang sama
    heapObjectReference.counter = 100;

    assert.equal(heapObjectSource.counter, 100, 'Objek referensi pada Heap harus terupdate serempak');
  });

});
```

---

### 17. Debugging & Observability

#### 1. Menghasilkan Heap Snapshot & Menjalankan Debugger Inspector
Untuk melacak Execution Context dan kebocoran Heap langsung ke Chrome DevTools:
```bash
node --inspect-brk execution_tracer.js
```
*Buka browser Chromium dan arahkan ke `chrome://inspect`.*

#### 2. Dump Heap Snapshot Programatis saat Anomali Terjadi
Gunakan modul native `node:v8` untuk membuat snapshot diagnostik saat batas alokasi memori kritis terlewati:

```javascript
import v8 from 'node:v8';
import fs from 'node:fs';

export function takeEmergencyHeapSnapshot(triggerReason) {
  const fileName = `heapdump-${Date.now()}-${triggerReason}.heapsnapshot`;
  const snapshotStream = v8.getHeapSnapshot();
  const fileWriteStream = fs.createWriteStream(fileName);
  
  snapshotStream.pipe(fileWriteStream);
  
  fileWriteStream.on('finish', () => {
    console.error(`[DIAGNOSTIK] Heap snapshot darurat berhasil disimpan ke: ${fileName}`);
  });
}

// Trigger otomatis jika New Space / Old Space terlampaui
const memUsage = process.memoryUsage();
if (memUsage.heapUsed > 500 * 1024 * 1024) { // 500MB Threshold
  takeEmergencyHeapSnapshot('EXCEEDED_500MB_LIMIT');
}
```

#### 3. Log Schema Observabilitas Konteks Produksi
Gunakan format log JSON struktural untuk melacak stack dan heap di pipeline agregasi log (seperti ElasticSearch / Datadog):
```json
{
  "@timestamp": "2026-03-30T10:14:02.102Z",
  "log.level": "warn",
  "ecs.version": "1.12.0",
  "message": "High Stack Depth Warning Detected",
  "context": {
    "engine": "v8",
    "call_stack_depth": 780,
    "max_stack_threshold": 1000,
    "heap_used_bytes": 142385152,
    "heap_total_bytes": 210124800,
    "external_memory_bytes": 2490128
  },
  "trace": {
    "execution_function": "recursiveWorker",
    "file": "execution_tracer.js",
    "line": 82
  }
}
```

---

### 18. Real-World Case Study
**Insiden**: Out-Of-Memory (OOM) Melumpuhkan Pipeline Pemrosesan Order FinTech.

- **Konteks**: Sistem backend pemrosesan order keuangan berbasis Node.js mengalami crash berantai setiap kali volume transaksi pasar mencapai puncaknya (sekitar 15.000 req/detik). Metrik Kubernetes menunjukkan pod terhenti karena sinyal `SIGKILL` (OOM Killer dari Linux cgroup).
- **Analisis Akar Masalah (Root Cause Analysis)**:
  Tim SRE mengambil profil memori melalui core dump V8 Heap Snapshot. Ditemukan bahwa modul audit logging internal membungkus setiap order transaksi dalam *closure callback*:
  ```javascript
  // KODE BERMASALAH ASLI
  function setupOrderAudit(orderPayload) {
    const rawBuffer = Buffer.from(JSON.stringify(orderPayload)); // Alokasi buffer besar
    return function logExecution(status) {
      // Walaupun hanya menggunakan status & orderPayload.id,
      // seluruh rawBuffer tetap terkunci dalam Lexical Scope Context closure ini!
      logger.info(`Order ${orderPayload.id} processed with status ${status}`);
    };
  }
  ```
  Callback `logExecution` disimpan ke dalam antrean event listener berumur panjang. Akibatnya, `rawBuffer` (yang seharusnya langsung dapat didaur ulang oleh GC di New Space) dipromosikan ke Old Space. GC Major (*Mark-Sweep*) berjalan terus menerus secara blocking, memicu *Event Loop Lag* > 3000ms sebelum pod kehabisan memori.
- **Resolusi**:
  1. Membersihkan relasi lexical context closure dengan mengekstraksi nilai primitif sebelum membentuk fungsi callback:
  ```javascript
  // KODE PERBAIKAN
  function setupOrderAuditFixed(orderPayload) {
    const orderId = orderPayload.id; // Menyalin primitif string/number ke context
    // rawBuffer dihilangkan sepenuhnya dari cakupan closure
    return function logExecution(status) {
      logger.info(`Order ${orderId} processed with status ${status}`);
    };
  }
  ```
  2. Mengaktifkan limit memori Old Space eksplisit di flag startup V8 container: `--max-old-space-size=1536`.
- **Hasil**: Penggunaan Heap stabil di bawah 400MB pada beban puncak penuh, latensi Event Loop P99 turun dari 3.200ms ke 4ms, dan insiden OOM tereliminasi 100%.

---

### 19. Hands-On Self-Study Exercises

#### Tingkat 1: Pemula (Beginner)
- **Tugas**: Buat fungsi `inspectContextScope(flag)` yang mengeksploitasi perbedaan perilaku scope `var`, `let`, dan parameter function default. 
- **Kriteria Penerimaan**:
  - Tunjukkan bahwa variabel `var` dapat diakses di luar block condition `if (flag) { ... }`, sedangkan `let` menghasilkan runtime `ReferenceError`.
  - Tanpa menggunakan library eksternal, catat perbedaan ini ke konsol terminal secara deterministik.

#### Tingkat 2: Menengah (Intermediate)
- **Tugas**: Rancang custom event emitter class bernama `MemorySafeEmitter` yang mencegah kebocoran memori akibat retensi listener function.
- **Kriteria Penerimaan**:
  - Menggunakan struktur data `WeakRef` dan/atau `FinalizationRegistry` untuk melacak pendaftaran listener secara leksikal.
  - Sediakan metode `.getRegisteredCount()` yang membuktikan bahwa callback yang tidak lagi memiliki referensi di thread eksekusi utama dapat dibersihkan oleh Garbage Collector.

#### Tingkat 3: Mahir (Advanced)
- **Tugas**: Implementasikan fungsi `evaluateAstScope(node)` rekursif yang mampu memproses Abstract Syntax Tree tiruan sedalam 100.000 layer tanpa memicu kegagalan sistem `RangeError: Maximum call stack size exceeded`.
- **Kriteria Penerimaan**:
  - Konversi algoritma rekursif standar menggunakan teknik *Trampoline Pattern* atau alur loop eksplisit berbasis Heap Stack terkelola (*Custom Array Queue*).
  - Skrip pengujian harus berhasil menyelesaikan eksekusi payload 100.000 layer dalam waktu < 2.000ms tanpa menambah footprint Call Stack OS lebih dari 50 frame.

---

### 20. Further Reading & References
1. **ECMAScript® 2024 Language Specification (ECMA-262, 15th Edition)**
   - *Section 9: Ordinary and Exotic Objects Behaviours*
   - *Section 10: ECMAScript Code Execution Environments (Execution Contexts, Environment Records)*
   - URL: https://tc39.es/ecma262/
2. **V8 Engine Internal Architecture Documentation**
   - *Ignition: Register-based Bytecode Interpreter for V8*
   - *TurboFan: Highly-Optimizing Compiler Platform*
   - URL: https://v8.dev/docs
3. **Node.js Diagnostics & Performance Profiling Guides**
   - *Memory Management and Garbage Collection Tracking Guide*
   - URL: https://nodejs.org/en/learn/diagnostics/memory
4. **"JavaScript: The Definitive Guide, 7th Edition" (David Flanagan, O'Reilly Media)**
   - Bab 3: *Types, Values, and Variables*
   - Bab 8: *Functions and Scope Chains*
5. **CWE-400 & CWE-1321 MITRE Standards**
   - *Uncontrolled Resource Consumption & Improper Control of Generation of Code ('Prototype Pollution')*
   - URL: https://cwe.mitre.org/data/definitions/400.html