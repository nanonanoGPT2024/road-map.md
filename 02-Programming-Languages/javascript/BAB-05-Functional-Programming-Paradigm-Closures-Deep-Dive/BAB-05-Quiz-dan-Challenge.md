# BAB 05: Quiz, Challenge, & Knowledge Check
**Functional Programming Paradigm & Closures Deep Dive**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Lexical Environment & Mekanisme Resolusi Identifier
Jelaskan secara mendalam bagaimana V8 engine merepresentasikan *Lexical Environment* saat sebuah fungsi dieksekusi. Apa perbedaan struktural antara `Environment Record` (khususnya *Declarative Environment Record*) dan referensi `outer` (*Outer Lexical Environment Reference*)? Bagaimana traversal identifier (*scope chain walk*) terjadi saat sebuah fungsi terdalam mencoba mengakses variabel bebas (*free variable*), dan apa yang terjadi di level CPU/memori jika identifier tidak ditemukan hingga mencapai *Global Environment Record*?

### Soal 1.2: Transparansi Referensial dan Model Komputasi Deterministik
Definisikan prinsip *Referential Transparency* dalam paradigma Functional Programming (FP). Mengapa pemanggilan `Math.random()`, pembacaan jam sistem (`Date.now()`), atau mutasi argumen via *pass-by-reference* secara langsung melanggar prinsip transparansi referensial? Berikan analisis bagaimana pelanggaran transparansi referensial merusak teknik optimasi kompilator seperti *Common Subexpression Elimination* (CSE) dan *Memoization*.

### Soal 1.3: Siklus Hidup Memori Closures: Stack vs. Heap Escape Analysis
Secara default, *Execution Context* dan *activation record* sebuah fungsi dialokasikan di *Call Stack* dan dibersihkan (*popped*) segera setelah fungsi mengembalikan nilai (*return*). Jelaskan mekanisme *Escape Analysis* pada JavaScript engine modern yang mendeteksi variabel yang ditangkap (*captured variables*) oleh closure. Bagaimana engine mengubah alokasi variabel-variabel tersebut dari *Stack Frame* ke *Heap Context Record*, dan bagaimana siklus hidupnya terikat pada *Garbage Collector* (GC)?

### Soal 1.4: Currying vs. Partial Application via Arity Manipulation
Ditinjau dari teori matematika kalkulus lambda dan implementasinya di JavaScript:
1. Bedakan definisi formal antara *Currying* dan *Partial Application* dalam konteks manipulasi aritas fungsi (*function arity*).
2. Jelaskan struktur closure yang terbentuk pada *auto-curried function* berderajat $N$ ($f(a, b, c) \rightarrow f(a)(b)(c)$). Bagaimana state perantara (*intermediate arguments*) dipelihara di dalam closure chain sebelum aritas akhir terpenuhi dan fungsi inti dieksekusi?

### Soal 1.5: Higher-Order Functions (HOF) dan Batasan Abstraksi Prosedural
Mengapa fungsi diklasifikasikan sebagai *First-Class Citizen* merupakan prasyarat mutlak untuk keberadaan *Higher-Order Functions* (HOF)? Jelaskan bagaimana HOF memfasilitasi inversi kontrol (*inversion of control*) dan *separation of concerns* (misalnya: pemisahan logika iterasi dan logika transformasi data pada `Array.prototype.reduce`) dibandingkan paradigma imperative looping (`for`/`while`) tanpa overhead pembentukan stack frame yang tidak terkontrol.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: The Shared Context Leakage Pattern (Meteor Leak / V8 Context Optimization Artifact)
Perhatikan potongan kode berikut:

```javascript
let theThing = null;

const replaceThing = function () {
  const originalThing = theThing;
  
  const unused = function () {
    if (originalThing) {
      console.log("Unused closure retaining reference");
    }
  };
  
  theThing = {
    longStr: new Array(10000000).join('*'),
    someMethod: function () {
      console.log("Active method");
    }
  };
};

setInterval(replaceThing, 100);
```

Jelaskan secara presisi mengapa kode di atas memicu kebocoran memori masif (*memory leak*) hingga terjadi `Process Out Of Memory (OOM)` di Node.js, meskipun `unused` tidak pernah dieksekusi sama sekali! Analisis bagaimana V8 menyatukan *Lexical Environment* antar closure (`unused` dan `someMethod`) dalam konteks lingkup yang sama (*Shared Context allocation*).

### Soal 2.2: Asynchronous Composition & Pipeline Error Isolation
Diberikan fungsi utilitas komposisi fungsi asinkron berikut:

```javascript
const pipeAsync = (...fns) => (initialValue) =>
  fns.reduce(
    (chain, fn) => chain.then(fn),
    Promise.resolve(initialValue)
  );
```

1. Apa kelemahan kritis dari implementasi di atas jika salah satu fungsi di tengah pipeline menolak (*rejects*) promise, atau melempar eksepsi sinkron (*synchronous throw*)?
2. Bagaimana Anda merancang arsitektur pipeline fungsional berbasis pola *Monadic Railway-Oriented Programming* (`Result` atau `Either` monad: `Left` untuk Failure, `Right` untuk Success) sehingga eksekusi me-bypass fungsi transformasi berikutnya secara otomatis tanpa memicu unhandled rejection?

### Soal 2.3: Immutabilitas Naif vs. Structural Sharing (Performance & GC Pressure)
Banyak engineer menerapkan immutabilitas secara naif menggunakan *object spread operator* (`{ ...state, nested: { ...state.nested, key: value } }`).
1. Analisis kompleksitas waktu dan memori ($O(N)$ vs $O(1)$) dari operasi *deep clone* / *nested spread* pada *state tree* dengan kedalaman $D$ dan jumlah node $M$.
2. Jelaskan bagaimana konsep *Directed Acyclic Graph* (DAG) dan *Persistent Data Structures* (seperti *Hash Array Mapped Tries* / HAMT) mengeliminasi alokasi memori berlebih melalui *Structural Sharing*. Apa dampak mitigasi ini terhadap *GC Young Generation Scavenge cycle*?

### Soal 2.4: Closure Serialization Barrier pada Multithreading (Web Workers)
Mengapa closure yang mengkapsulasi *free variables* tidak dapat dikirimkan secara langsung ke Web Worker atau Node.js `worker_threads` via `postMessage`? Jelaskan batasan algoritma *Structured Clone Algorithm* terhadap fungsi dan scope pointer. Solusi arsitektural apa yang harus diimplementasikan jika kita perlu mengeksekusi komputasi fungsional dinamis pada thread worker yang terisolasi?

### Soal 2.5: Cache Collisions and Memory Retention in High-Arity Dynamic Memoization
Perhatikan implementasi memoizer berikut:

```javascript
function memoize(fn) {
  const cache = new Map();
  return function (...args) {
    const key = JSON.stringify(args);
    if (cache.has(key)) {
      return cache.get(key);
    }
    const result = fn.apply(this, args);
    cache.set(key, result);
    return result;
  };
}
```

Identifikasi minimal 4 kelemahan fatal dari implementasi di atas jika diintegrasikan ke sistem produksi berkapasitas tinggi (*high-throughput*), dengan fokus pada:
- Serialisasi tipe data kompleks (circular references, BigInt, Symbols, function arguments).
- Semantik kesetaraan nilai (`NaN`, `undefined` vs key absen).
- Penumpukan *Heap Memory* (ketiadaan strategi eviksi seperti LRU).
- *Memory Retention* pada objek yang dijadikan argumen (mengapa `Map` biasa menghalangi pengumpulan sampah dibandingkan `WeakMap`, dan apa trade-off arsitekturalnya untuk primitive values)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Kebocoran Memori Skala Besar pada Microservice Event-Driven
Sebuah microservice ingestion data berbasis Node.js menangani 15.000 events/detik. Service ini menggunakan event pipeline fungsional yang dikonstruksi secara dinamis untuk setiap koneksi WebSocket klien. Kode ditulis dengan pendekatan FP murni:

```javascript
function createEventProcessor(clientSocket, metricsCollector) {
  const connectionBuffer = [];
  
  return function processEvent(eventPayload) {
    connectionBuffer.push(eventPayload);
    if (connectionBuffer.length > 100) {
      connectionBuffer.shift();
    }
    
    const enriched = enrichPayload(eventPayload);
    metricsCollector.record(() => ({
      clientId: clientSocket.id,
      timestamp: Date.now(),
      bufferSnapshotLength: connectionBuffer.length
    }));
    
    return enriched;
  };
}
```

Setelah berjalan 4 jam di cluster Kubernetes, penggunaan memori (Resident Set Size / RSS) naik secara monotonik linier hingga mencapai batas 2GB dan terbunuh oleh Linux kernel OOM Killer. Heap snapshot menunjukkan jutaan instance `Closure (processEvent)` dan array `connectionBuffer` yang tidak terlepas, meskipun koneksi WebSocket klien telah ditutup (*disconnected*).

**Tugas Diagnostik & Arsitektur:**
1. Mengapa `metricsCollector.record` menahan seluruh konteks leksikal `createEventProcessor` (termasuk `clientSocket` dan `connectionBuffer`), dan bagaimana retensi ini membentuk siklus hidup zombie pada memori heap?
2. Rekonstruksi arsitektur fungsi di atas agar memisahkan *data extraction* dari *closure-scoped dependencies*. Tunjukkan kode perbaikannya dengan teknik isolasi dependensi dan pembersihan referensi secara eksplisit saat koneksi berakhir.

---

### Skenario B: Race Condition dan State Mutation pada Distributed Financial Ledger
Sebuah sistem agregasi transaksi finansial memproses sekumpulan mutasi rekening secara paralel menggunakan pemrosesan stream asinkron. Engineer junior menuliskan pipeline fungsional untuk kalkulasi saldo akhir:

```javascript
async function reconcileBatches(transactions, initialBalance) {
  let runningLedger = { balance: initialBalance, auditLog: [] };

  const ledgerTransforms = transactions.map((tx) => async () => {
    // Simulasi delay IO/Network fetching exchange rate
    const rate = await fetchExchangeRate(tx.currency);
    const convertedAmount = tx.amount * rate;
    
    // Mutasi parsial
    runningLedger.balance += convertedAmount;
    runningLedger.auditLog.push({ txId: tx.id, appliedAmount: convertedAmount });
    return runningLedger;
  });

  await Promise.all(ledgerTransforms.map(apply => apply()));
  return runningLedger;
}
```

Pada throughput tinggi, pengujian unit mendeteksi ketidaksesuaian saldo akhir (*balance mismatch*) dan urutan log audit yang tidak konsisten secara non-deterministik antar eksekusi.

**Tugas Diagnostik & Arsitektur:**
1. Analisis bagaimana manipulasi *shared mutable state* (`runningLedger`) dalam closure asinkron di atas memicu *race condition* (Interleaving Hazard) meskipun JavaScript berjalan di *single-threaded event loop*.
2. Tulis ulang algoritma rekonsiliasi tersebut secara fungsional murni (*pure functional pipeline*) menggunakan `reduce` asinkron atau model transaksional *Monadic State/Scan*. Kode baru harus sepenuhnya deterministik, bebas dari mutasi variabel di scope luar, dan menjamin keterurutan integritas ledger.

---

### Skenario C: Bottleneck Performa GC Akibat Alokasi Closure Berfrekuensi Tinggi pada Low-Latency Core
Sebuah library visualisasi data finansial real-time me-render 60 frame per detik pada Canvas 2D/WebGL. Setiap frame memproses 50.000 titik data (*data points*). Engine transformasi ditulis menggunakan chaining fungsional modern:

```javascript
function renderFrame(points, canvasContext, theme) {
  points
    .filter(pt => pt.val > theme.threshold)
    .map(pt => ({
      x: pt.rawX * theme.scaleX + theme.offsetX,
      y: pt.rawY * theme.scaleY + theme.offsetY,
      color: pt.category === 'BUY' ? theme.buyColor : theme.sellColor
    }))
    .forEach(screenPt => {
      drawPoint(canvasContext, screenPt);
    });
}
```

Metrik performa menunjukkan penurunan frame rate drastis (hingga 12 FPS) dan terjadi *stuttering* (*jank*) periodik. Profiler DevTools CPU/Performance mengonfirmasi bahwa eksekusi JavaScript hanya memakan waktu 4ms, tetapi browser membeku selama 35ms setiap beberapa ratus frame karena siklus *Major Garbage Collection (Mark-Sweep-Compact)*.

**Tugas Diagnostik & Arsitektur:**
1. Hitung dan jelaskan alokasi objek sementara (*ephemeral allocations*) dan closure instances per detik yang diproduksi oleh rantai `.filter().map().forEach()` pada frekuensi 60 FPS untuk 50.000 data point.
2. Mengapa closure anonymous yang diciptakan berulang kali di dalam loop animasi membebani *V8 V8 New Space (Nursery)*?
3. Rancang arsitektur alternatif yang mempertahankan prinsip fungsional deklaratif (komposisi modul), namun mencapai **Zero-Allocation** atau **Near-Zero-Allocation** pada siklus render runtime (misalnya melalui teknik *Transducers*, *ArrayBuffers / TypedArrays*, atau *Object Pools*). Berikan bukti kode solusinya.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Reactive Pipeline Engine dengan Monadic State, Strict Currying, & LRU Memoization

#### Problem Statement
Anda ditugaskan merancang *Core Computational Engine* untuk microservice komparasi harga tiket pesawat real-time. Engine ini menerima ribuan aturan transformasi data (*filtering, enrichment, currency normalization, tax calculation*) yang harus dapat dikomposisikan secara dinamis per maskapai, deterministik, bebas efek samping, memiliki performa ekstrem, serta toleran terhadap kegagalan parsing parsial.

#### Requirements
1. **Strict Currying Utility (`curry`)**:
   Implementasikan fungsi `curry(fn, arity = fn.length)` berkemampuan menerima argumen secara bertahap hingga seluruh aritas terpenuhi. Harus mendukung penggunaan placeholder (`_`) untuk substitusi argumen posisi tertentu tanpa mengeksekusi fungsi utama sebelum semua slot non-placeholder terpenuhi.
2. **Monadic Result Container (`Result.Ok` & `Result.Fail`)**:
   Bangun struktur data aljabar `Result<T, E>` yang mengkapsulasi eksekusi fungsi murni:
   - `map(fn)`: Mengeksekusi transformasi murni jika state adalah `Ok`. Mengabaikan jika `Fail`.
   - `flatMap(fn)`: Melakukan chain operasi yang mengembalikan instance `Result` lain (mencegah nested `Result<Result<T, E>, E>`).
   - `match({ Ok: (val) => {}, Fail: (err) => {} })`: Pattern matching untuk membongkar nilai akhir.
3. **Resilient Pipeline (`pipeResult`)**:
   Fungsi komposisi fungsional (`pipeResult(...fns)`) dari kiri ke kanan (*left-to-right*) yang secara otomatis membungkus eksekusi ke dalam konteks `Result`. Jika sebuah step melempar error atau mengembalikan `Result.Fail`, sisa pipeline di-bypass dan failure langsung diarahkan ke handler akhir.
4. **Isolated Closure-Based LRU Cache (`createMemoizer`)**:
   Mekanisme memoization berbasis closure yang murni mengisolasi state cache di dalam lexical scope:
   - Menggunakan konfigurasi `maxSize` (eviksi Least-Recently-Used).
   - Menghasilkan custom cache key hashing yang stabil untuk deep objects/primitives tanpa menggunakan `JSON.stringify` mentah.
   - Tidak membocorkan memori (bebas dari lingering references).

#### Constraints
- **Zero Third-Party Libraries**: Dilarang menggunakan Lodash, Ramda, Immutable.js, Folktale, dsb. Hanya gunakan JavaScript murni (ECMAScript 2022+).
- **Zero Global State**: Seluruh status harus dienkapsulasi menggunakan lexical closures.
- **Strict Immutability**: Argumen input dilarang dimutasi (`Object.freeze` digunakan pada mode testing/development).

#### Expected Output & API Contract

```javascript
// Demonstrasi integrasi pipeline fungsional maskapai
const _ = Symbol('placeholder');

// Curried pure transformation functions
const applyTax = curry((taxRate, amount) => amount + (amount * taxRate));
const convertCurrency = curry((rate, amount) => amount * rate);
const validateMinPrice = curry((min, amount) => 
  amount >= min 
    ? Result.Ok(amount) 
    : Result.Fail(`Price ${amount} is below minimum threshold ${min}`)
);

// Pipeline composition
const processFlightPrice = pipeResult(
  validateMinPrice(50),               // Validasi input
  applyTax(0.11),                     // PPN 11%
  convertCurrency(15500)              // Kurs USD ke IDR
);

// Execution testing
const result1 = processFlightPrice(100);
result1.match({
  Ok: (price) => console.log(`Processed Price: IDR ${price}`), // Expected: 100 -> Ok(100) -> 111 -> 1720500
  Fail: (err) => console.error(`Failed: ${err}`)
});

const result2 = processFlightPrice(30);
result2.match({
  Ok: (price) => console.log(`Processed Price: IDR ${price}`),
  Fail: (err) => console.error(`Failed: ${err}`) // Expected: Failed: Price 30 is below minimum threshold 50
});
```

---

## 5. Knowledge Check & Checklist

Verifikasi penguasaan materi fungsional dan closures Anda sebelum beralih ke arsitektur asynchronous tingkat lanjut.

### Saya harus memahami:
- [ ] Mekanisme formal alokasi `LexicalEnvironment`, `VariableEnvironment`, dan rantai scope (*outer pointer*) berdasarkan spesifikasi ECMAScript.
- [ ] Perbedaan alokasi memori *Stack Frame* vs *Heap Allocated Context* saat closure meloloskan variabel (*variable escaping*).
- [ ] Batasan optimasi V8 pada *Shared Closure Context* dan resiko kebocoran memori terkait retensi objek tak terpakai (*unintentional memory retention*).
- [ ] Definisi formal fungsi murni (*pure function*), transparansi referensial, dan determinisme komputasional.
- [ ] Konsep aljabar Category Theory dasar pada FP: Functor (`map`), Monad (`flatMap`), dan Arity transformations (*Currying* vs *Partial Application*).
- [ ] Perbedaan mendalam antara shallow equality, deep equality, dan *Structural Sharing* dalam pemeliharaan state immutable.
- [ ] Dampak alokasi closure anonim frekuensi tinggi terhadap siklus *Minor GC (Scavenger)* dan degradasi performa pada sistem low-latency.

### Saya tidak perlu menghafal:
- [ ] C++ source code internal V8 engine untuk class `Context` dan `ScopeInfo` (cukup pahami model mental arsitekturnya).
- [ ] Seluruh tabel implementasi aljabar Category Theory kompleks (seperti Comonad, Profunctor, atau Kleisli arrows) yang tidak aplikatif dalam rekayasa perangkat lunak JS pragmatis.
- [ ] Kode implementasi internal algoritma hashing string 32-bit (cukup gunakan hashing deterministik sederhana untuk implementasi custom cache key).

### Saya harus bisa melakukan:
- [ ] Melakukan analisis Memory Leak menggunakan Chrome DevTools / Node.js Memory Heap Snapshot untuk melacak *Retaining Paths* yang disebabkan oleh closure zombie.
- [ ] Mengonstruksi utility fungsional tingkat lanjut (`curry`, `pipe`, `compose`) dari nol (*from scratch*) dengan penanganan aritas dinamis dan asinkron.
- [ ] Melakukan refaktorisasi kode imperatif penuh mutasi (*loops, mutable variables, side-effects*) menjadi pipeline fungsional murni yang bersih, modular, dan teruji (*fully unit-testable*).
- [ ] Mengimplementasikan *Railway-Oriented Error Handling* menggunakan Monad `Result`/`Either` untuk mengeliminasi blok `try-catch` masif yang tidak terstruktur pada enterprise codebases.
- [ ] Menganalisis dan mengeliminasi *allocation bottleneck* pada hot-path execution menggunakan closure reuse, pre-allocated buffers, atau transducing logic.