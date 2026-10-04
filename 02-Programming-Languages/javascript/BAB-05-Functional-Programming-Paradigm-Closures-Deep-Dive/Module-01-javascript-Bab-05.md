# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran**: Pemrograman JavaScript Tingkat Lanjut (*Advanced JavaScript Engineering*)
*   **Kategori**: `02-Programming-Languages`
*   **Kode Modul**: `JS-ADV-0501`
*   **Nama Modul**: *Functional Programming Paradigm & Closures Deep Dive*
*   **Tingkat Kesulitan**: Tingkat Lanjut (*Advanced*)
*   **Prasyarat**:
    *   Pemahaman mendalam tentang *Execution Context*, *Call Stack*, dan *Event Loop*.
    *   Penguasaan *Scope* dasar (Global, Function, Block Scope).
    *   Kemahiran sintaksis ES6+ (*Arrow Functions*, *Destructuring*, *Rest/Spread Operators*).
*   **Estimasi Waktu Penyelesaian**: 8 – 10 Jam Pembelajaran Intensif

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini secara komprehensif, peserta ajar memiliki kompetensi teruji untuk:

1.  **Mendekomposisi Mekanisme Internal Mesin JavaScript**: Menganalisis siklus hidup *Execution Context*, alokasi memori pada *Stack* versus *Heap*, serta rantai *Lexical Environment* yang memfasilitasi persistensi *Closure*.
2.  **Menerapkan Prinsip Dasar Pemrograman Fungsional**: Mengidentifikasi dan memitigasi efek samping (*side effects*), mengimplementasikan fungsi murni (*pure functions*), dan menegakkan *referential transparency* dalam perancangan arsitektur perangkat lunak.
3.  **Mengonstruksi Struktur Data Imutabel**: Mengamankan integritas data aplikasi menggunakan strategi imutabilitas struktural tanpa menurunkan performa pemrosesan secara drastis.
4.  **Menguasai Teknik Komposisi Lanjut**: Membangun abstraksi fungsional menggunakan teknik *Higher-Order Functions* (HOF), *Currying*, *Partial Application*, serta komposer aliran data (*Compose* dan *Pipe*).
5.  **Mendiagnosis dan Mencegah Kebocoran Memori (*Memory Leaks*)**: Mengidentifikasi retensi variabel yang tidak disengaja oleh *Closure* pada lingkungan produksi skala besar menggunakan teknik *heap snapshot profiling*.
6.  **Mengembangkan Solusi Produksi Berbasis Paradigma Fungsional**: Merancang modul bisnis yang aman dari mutasi konkuren (*concurrent mutation*), terisolasi secara leksikal, dan memiliki kemampuan auditabilitas tinggi.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Pergeseran dari paradigma Imperatif/Berorientasi Objek (*Object-Oriented Programming* - OOP) menuju Paradigma Fungsional (*Functional Programming* - FP) menuntut restrukturisasi cara berpikir seorang perekayasa perangkat lunak:

```
PARADIGMA IMPERATIF / OOP              PARADIGMA FUNGSIONAL (FP)
+-------------------------------+      +-------------------------------+
|  "Bagaimana cara melakukan?"  |      |   "Apa transformasi datanya?"  |
|  Status bermutasi (Mutasi)    | ---> |   Data Imutabel (Transformasi)|
|  Objek mengemas State & Method|      |   Fungsi terpisah dari Data   |
|  Banyak Efek Samping Tersembunyi     |   Transparansi Referensial     |
+-------------------------------+      +-------------------------------+
```

### 1. Mental Model: Data sebagai Aliran Sungai, Fungsi sebagai Penyaring (*Pipelines*)
Dalam OOP, Anda membuat objek yang menyimpan status internal (*state*) dan memodifikasi status tersebut melalui metode. Dalam FP, data dipandang sebagai material mentah yang tidak boleh diubah. Data dialirkan melalui serangkaian fungsi murni—seperti perakitan di pabrik modern—di mana setiap stasiun (fungsi) menghasilkan material baru tanpa merusak material pada stasiun sebelumnya.

### 2. Mental Model: *Closure* sebagai Ransel Lingkungan (*Backpack Model*)
Ketika sebuah fungsi dieksekusi di JavaScript, fungsi tersebut tidak berjalan di ruang hampa. Fungsi membawa referensi ke lingkungan tempat ia dilahirkan. Bayangkan fungsi yang dikembalikan (*returned function*) membawa sebuah "ransel tertutup" (*closure backpack*). Di dalam ransel tersebut tersimpan semua variabel yang ada di sekitarnya pada saat definisi dibuat (*lexical environment*). Selama fungsi tersebut masih hidup dan dapat diakses, ransel tersebut tidak akan pernah dihancurkan oleh *Garbage Collector*.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Mekanisme terbentuknya *Closure* berkaitan erat dengan relasi antara *Call Stack*, *Heap Memory*, dan *Lexical Environment Record*.

```
   CALL STACK                             HEAP MEMORY
+-----------------------------+        +-----------------------------------+
|                             |        |                                   |
|                             |        |                                   |
|                             |        |   [[OuterEnvRef]]                 |
|                             |   +-------> Environment Record (Parent)    |
|                             |   |    |    - secretKey: "0xDEADBEEF"      |
|                             |   |    |    - counter: 0                   |
| innerFunc Execution Context |   |    |                                   |
| - Scope: Local + Outer -----+---+    |                                   |
| - this: undefined/global    |        |                                   |
|                             |        |   Function Object: innerFunc      |
|                             |        |   - [[Scopes]]:                   |
|                             |        |     [0] Closure (createVault) ----+
|                             |        |     [1] Global Scope              |
+-----------------------------+        +-----------------------------------+
```

### Alur Komposisi Fungsional (*Function Pipeline Execution Flow*)

Komposisi fungsional menyusun beberapa fungsi independen menjadi sebuah alur kerja terpadu. Data dialirkan secara terurut:

```
Input Data (x)
     |
     v
+----+---------------------------------------------------------------+
|                        PIPE ENGINE                                 |
|                                                                    |
|  [ Step 1: sanitize ] ---> Output 1                                |
|                                |                                   |
|                                v                                   |
|                         [ Step 2: validate ] ---> Output 2         |
|                                                       |            |
|                                                       v            |
|                                                [ Step 3: hash ]    |
+-------------------------------------------------------+------------+
                                                        |
                                                        v
                                                 Output Akhir (y)
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

Mesin JavaScript (seperti Google V8) memproses *Closure* dan fungsi fungsional melalui spesifikasi ECMAScript internal sebagai berikut:

### 1. Execution Context (EC) & Lexical Environment
Setiap kali fungsi dipanggil, sebuah *Function Execution Context* dibuat, terdiri dari:
*   **LexicalEnvironment**: Komponen yang mencatat asosiasi *identifier-variable* berdasarkan hierarki penulisan kode (*lexical nesting*).
*   **VariableEnvironment**: Pada sebagian besar implementasi modern, bertindak serupa dengan `LexicalEnvironment` tetapi khusus menangani deklarasi instansiasi `var`.
*   **Environment Record**: Komponen internal tempat alokasi memori aktual terhadap variabel lokal (`let`, `const`, deklarasi fungsi) disimpan.
*   **OuterEnvRef**: Tautan referensi ke `LexicalEnvironment` luar (lingkup pembungkusnya).

### 2. Mekanisme Alokasi: Dari Stack ke Heap
Secara teknis, variabel lokal dialokasikan pada *Call Stack* untuk efisiensi eksekusi dan pembersihan otomatis ketika fungsi selesai dipanggil (*stack frame pop*). Namun, jika V8 mendeteksi melalui *Static Scope Analysis* bahwa fungsi di dalam (*inner function*) mereferensikan variabel dari fungsi luar (*outer function*), dan fungsi dalam tersebut dikembalikan atau dilempar ke luar:
1.  V8 **tidak** menghancurkan *Environment Record* dari fungsi luar saat fungsi luar selesai dieksekusi.
2.  V8 mengalokasikan konteks leksikal tersebut ke dalam **Managed Heap Memory**.
3.  Fungsi dalam mendapatkan properti internal bernama `[[Scopes]]` yang merujuk pada *Environment Record* yang dialokasikan di *Heap*.
4.  *Garbage Collector* (GC) berbasis algoritma *Mark-and-Sweep* menandai memori ini sebagai "reachable" selama fungsi dalam masih memiliki referensi aktif.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Karakteristik Komputasi Fungsional Murni
Sebuah paradigma fungsional dibangun di atas aksioma matematis komputasi Alonzo Church (*Lambda Calculus*):
*   **Fungsi Kelas Utama (*First-Class Functions*)**: Fungsi diperlakukan selayaknya data primitif. Fungsi dapat disimpan dalam variabel, dioperasikan sebagai argumen, atau dikembalikan sebagai keluaran fungsi lain.
*   **Fungsi Derajat Tinggi (*Higher-Order Functions*)**: Fungsi yang menerima satu atau lebih fungsi lain sebagai argumen, atau menghasilkan sebuah fungsi baru.
*   **Fungsi Murni (*Pure Functions*)**:
    1.  *Deterministik*: Nilai input yang sama selalu menghasilkan nilai output yang sama secara mutlak: $\forall x, f(x) = y$.
    2.  *Bebas Efek Samping (*No Side Effects*)*: Tidak memodifikasi variabel di luar lingkup lokalnya, tidak melakukan I/O yang tidak terkapsulasi, tidak mengubah argumen yang diterima secara mutatif.
*   **Transparansi Referensial (*Referential Transparency*)**: Setiap pemanggilan fungsi $f(x)$ dapat digantikan langsung oleh nilai hasilnya tanpa mengubah perilaku aplikasi sama sekali.

### 2. Imutabilitas Struktural (*Structural Immutability*)
Alih-alih melakukan mutasi *in-place* terhadap array atau objek (`arr.push()`, `obj.x = 10`), FP menuntut pembuatan salinan baru dengan perubahan yang diterapkan. Untuk memitigasi overhead alokasi memori berlebih, arsitektur data fungsional menerapkan konsep *Structural Sharing*, di mana bagian data yang tidak berubah akan tetap berbagi referensi memori yang sama di *Heap*.

### 3. Currying vs. Partial Application
*   **Currying**: Teknik matematika dekonstruksi fungsi dengan aritas $N$ (menerima $N$ argumen) menjadi rangkaian $N$ fungsi unari berurutan (masing-masing menerima tepat 1 argumen):
    $$f(a, b, c) \rightarrow f(a)(b)(c)$$
*   **Partial Application**: Proses mengevaluasi sebagian argumen dari suatu fungsi dengan aritas $N$, menghasilkan fungsi baru dengan aritas yang lebih rendah ($N - M$):
    $$f(a, b, c) \xrightarrow{\text{bind } a} f'(b, c)$$

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi esensial mencakup *Pure Functions*, *Immutability*, *Closure Data Hiding*, *Currying*, dan *Function Composition Pipeline*:

```javascript
/**
 * 1. PURE FUNCTION & IMMUTABILITY
 * Transformasi array data tanpa memodifikasi sumber referensi asli.
 */
const deepFreeze = (obj) => {
  Object.keys(obj).forEach((prop) => {
    if (typeof obj[prop] === 'object' && obj[prop] !== null) {
      deepFreeze(obj[prop]);
    }
  });
  return Object.freeze(obj);
};

// Pure function: Menghasilkan salinan array terurut baru
const pureSortAscending = (numbers) => {
  return [...numbers].sort((a, b) => a - b);
};

/**
 * 2. CLOSURE UNTUK ENKAPSULASI PRIVATE STATE
 * Membentuk factory function yang mengenkapsulasi status tanpa class.
 */
const createSecureCounter = (initialValue = 0) => {
  // Variabel lokal ini terenkapsulasi secara leksikal di heap
  let privateCounter = initialValue;

  return {
    increment: () => {
      privateCounter += 1;
      return privateCounter;
    },
    decrement: () => {
      privateCounter -= 1;
      return privateCounter;
    },
    getValue: () => privateCounter,
  };
};

/**
 * 3. ADVANCED CURRYING DENGAN ARITY DINAMIS
 * Mengubah fungsi multi-argumen menjadi rantai pemanggilan unari.
 */
const curry = (fn) => {
  const arity = fn.length;
  return function curried(...args) {
    if (args.length >= arity) {
      return fn.apply(this, args);
    }
    return (...nextArgs) => curried.apply(this, args.concat(nextArgs));
  };
};

// Fungsi dasar untuk di-curry
const calculateTaxes = (rate, luxuryRate, amount) => {
  return amount + (amount * rate) + (amount * luxuryRate);
};

/**
 * 4. FUNCTION COMPOSITION (PIPE & COMPOSE)
 * Merangkai eksekusi transformasi data dari kiri-ke-kanan (pipe).
 */
const pipe = (...functions) => (initialValue) => {
  return functions.reduce((accumulator, currentFunction) => {
    return currentFunction(accumulator);
  }, initialValue);
};

// Helper transformation functions
const trimString = (str) => str.trim();
const normalizeToLower = (str) => str.toLowerCase();
const removeNonAlphanumeric = (str) => str.replace(/[^a-z0-9]/g, '');

// Pipeline deklaratif
const sanitizeUsername = pipe(
  trimString,
  normalizeToLower,
  removeNonAlphanumeric
);
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanistik komparatif terhadap blok kode pada **Seksi 07**:

### 1. Fungsi `deepFreeze` & `pureSortAscending`
*   `Object.freeze(obj)`: Mencegah ekstensi, penambahan, penghapusan, dan pembaruan nilai properti pada tingkat pertama (*shallow*).
*   `deepFreeze` mengeksekusi rekursi pada setiap anak objek untuk memastikan imutabilitas transitif penuh.
*   `[...numbers].sort(...)`: Operator *spread* membuat salinan dangkal (*shallow copy*) dari array `numbers`. Operasi *in-place mutation* bawaan dari metode `.sort()` hanya terjadi pada salinan lokal baru tersebut, sehingga parameter asal `numbers` mempertahankan integritas nilainya (*side-effect free*).

### 2. Fungsi `createSecureCounter`
*   `let privateCounter = initialValue;`: Teredukasi ke dalam *Environment Record* dari fungsi pembungkus `createSecureCounter`.
*   Objek literal yang dikembalikan berisi tiga properti metode: `increment`, `decrement`, dan `getValue`.
*   Ketiga metode tersebut memegang referensi penunjuk internal leksikal `[[OuterEnvRef]]` ke instansiasi `createSecureCounter`.
*   `privateCounter` sama sekali tidak dapat diakses atau dimutasi dari luar melalui manipulasi *prototype* maupun *reflection*, menyediakan isolasi privat absolut yang jauh lebih kuat dibanding konvensi penamaan seperti `_privateCounter`.

### 3. Mesin `curry(fn)`
*   `const arity = fn.length`: Mendeteksi secara programatis jumlah argumen formal yang ditentukan dalam deklarasi `fn`.
*   Pemeriksaan `args.length >= arity`: Jika argumen terkumpul sudah mencukupi kebutuhan aritas dasar fungsi, fungsi target langsung dieksekusi dengan *context forwarding* via `fn.apply(this, args)`.
*   Jika belum mencukupi, fungsi baru dikembalikan untuk menangkap sisa argumen menggunakan rekursi via penggabungan array: `args.concat(nextArgs)`.

### 4. Mesin Komposisi `pipe`
*   `pipe = (...functions) => (initialValue) => ...`: Menggunakan arsitektur penutupan ganda (*double closure*).
*   `functions.reduce(...)`: Menyelesaikan urutan eksekusi secara berurutan (*left-to-right*). Nilai kembalian dari langkah $k$ menjadi nilai masukan absolut bagi langkah $k+1$.
*   Jika urutan yang diinginkan adalah dari kanan-ke-kiri (*right-to-left* atau standar matematis $f(g(x))$), operator `reduceRight` dapat digunakan menggantikan `reduce`.

---

# SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Skenario:
Sistem FinTech Pemrosesan Transaksi Perbankan (*Ledger Transaction Engine*).

### Masalah:
Sistem pemrosesan transaksi sebelumnya mengandalkan mutasi objek global yang rapuh. Objek transaksi dilempar melalui berbagai servis berbeda (Pengecekan Saldo, Kalkulasi Biaya Admin, Audit Anti-Money Laundering, Konversi Valas, dan Pemotongan Saldo). 
Karena setiap modul servis memutasi properti objek asli secara *in-place*, terjadi *race conditions* saat konkurensi tinggi, *debugging audit log* yang mustahil (karena mutasi menimpa status masa lalu), dan *memory leaks* yang diakibatkan oleh *event listener* yang mereferensikan transaksi secara permanen.

### Solusi Arsitektural:
Membangun ulang subsistem eksekusi transaksi menggunakan:
1.  **State Immobility**: Setiap tahap kalkulasi menghasilkan snapshot transaksi baru.
2.  **Pure Transformation Pipelines**: Pemrosesan dibagi ke dalam fungsi independen berukuran kecil yang digabung menggunakan `pipe`.
3.  **Closures for Auditing & Memoization**: Merekam jejak audit dan melindungi status tanpa mengekspos variabel lingkungan ke ancaman polusi lingkup (*scope pollution*).

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah implementasi sistem produksi menggunakan paradigma fungsional murni tanpa ketergantungan pada pustaka eksternal (*zero-dependency*):

```javascript
'use strict';

/**
 * SISTEM AUDIT & VALIDASI TRANSAKSI FINTECH BERBASIS PARADIGMA FUNGSIONAL
 */

// 1. Primitive Pipeline Orchestrator
const pipe = (...fns) => (initialValue) => 
  fns.reduce((acc, fn) => fn(acc), initialValue);

// 2. Curried Calculation Helpers (Pure Functions)
const applyProcessingFee = (rate) => (transaction) => {
  const fee = transaction.amount * rate;
  return Object.freeze({
    ...transaction,
    fees: transaction.fees + fee,
    netAmount: transaction.netAmount - fee,
    auditTrail: [...transaction.auditTrail, `FeeApplied: ${fee}`]
  });
};

const applyTaxDeduction = (taxPercentage) => (transaction) => {
  const tax = transaction.netAmount * (taxPercentage / 100);
  return Object.freeze({
    ...transaction,
    tax: transaction.tax + tax,
    netAmount: transaction.netAmount - tax,
    auditTrail: [...transaction.auditTrail, `TaxDeducted: ${tax}`]
  });
};

const applyCurrencyConversion = (exchangeRate, targetCurrency) => (transaction) => {
  return Object.freeze({
    ...transaction,
    currency: targetCurrency,
    originalAmount: transaction.amount,
    amount: transaction.amount * exchangeRate,
    netAmount: transaction.netAmount * exchangeRate,
    fees: transaction.fees * exchangeRate,
    tax: transaction.tax * exchangeRate,
    auditTrail: [...transaction.auditTrail, `ConvertedTo: ${targetCurrency} at Rate: ${exchangeRate}`]
  });
};

// 3. Memoized High-Cost Validator using Closures
const createTransactionValidator = () => {
  // Heap-allocated cache via closure
  const validationCache = new Map();

  return (transaction) => {
    const cacheKey = `${transaction.id}_${transaction.amount}_${transaction.currency}`;
    
    if (validationCache.has(cacheKey)) {
      return { ...transaction, validationStatus: validationCache.get(cacheKey) };
    }

    // Simulasi komputasi verifikasi integritas transaksi yang kompleks
    const isValid = transaction.amount > 0 && 
                    transaction.senderAccount !== transaction.receiverAccount &&
                    typeof transaction.amount === 'number';

    const status = isValid ? 'VALIDATED_SUCCESS' : 'FAILED_VALIDATION';
    
    // Simpan ke private closure cache
    validationCache.set(cacheKey, status);

    return Object.freeze({
      ...transaction,
      validationStatus: status,
      auditTrail: [...transaction.auditTrail, `Validated: ${status}`]
    });
  };
};

// 4. Factory Penyusun Pipeline Transaksi FinTech
const createTransactionProcessor = () => {
  const validator = createTransactionValidator();

  // Komposisi proses transformasi bisnis
  const processInternationalUSD = pipe(
    validator,
    applyProcessingFee(0.015),          // Biaya admin 1.5%
    applyCurrencyConversion(0.000064, 'USD'), // IDR -> USD
    applyTaxDeduction(10)                // Pajak 10%
  );

  return {
    execute: (rawTransaction) => {
      // Inisialisasi awal struktur data transaksi yang di-freeze
      const baseTransaction = Object.freeze({
        ...rawTransaction,
        fees: 0,
        tax: 0,
        netAmount: rawTransaction.amount,
        auditTrail: ['TransactionInitialized']
      });

      return processInternationalUSD(baseTransaction);
    }
  };
};

// ==========================================
// SIMULASI EKSEKUSI PRODUKSI
// ==========================================

const processor = createTransactionProcessor();

const incomingWireTransfer = {
  id: "trx-99882103",
  senderAccount: "ACC-IDR-110",
  receiverAccount: "ACC-USD-992",
  amount: 50_000_000, // 50 Juta IDR
  currency: "IDR"
};

// Eksekusi mutasi fungsional (menghasilkan snapshot baru)
const processedResult = processor.execute(incomingWireTransfer);

console.log("--- HASIL EKSEKUSI TRANSAKSI ---");
console.log("Payload Asli (Tidak Mengalami Mutasi):", incomingWireTransfer);
console.log("\nSnapshot Hasil Akhir Pemrosesan:", JSON.stringify(processedResult, null, 2));
console.log("\nApakah Objek Baru Identik Secara Referensi?:", incomingWireTransfer === processedResult); // FALSE
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Parameter Metrik | Paradigma Fungsional Murni (FP) | Paradigma Berorientasi Objek (OOP) | Paradigma Imperatif Prosedural |
| :--- | :--- | :--- | :--- |
| **Prediktabilitas State** | **Sangat Tinggi**. Tidak ada mutasi implisit; nilai deterministik. | **Sedang**. Status internal dapat termutasi secara acak oleh metode publik/privat. | **Rendah**. Perubahan status variabel global/lokal bebas di mana saja. |
| **Overhead Memori** | **Tinggi**. Menghasilkan objek baru di heap untuk setiap transformasi data. | **Rendah – Sedang**. Mutasi *in-place* memanfaatkan memori yang sudah dialokasikan. | **Sangat Rendah**. Variabel dialokasikan ulang langsung di memori yang sama. |
| **Debuggability** | **Sangat Mudah**. Menggunakan fungsi murni memungkinkan isolasi uji modular tanpa mocking rumit. | **Kompleks**. Memerlukan mocking status instance objek (*mocking lifecycle*). | **Sukar**. Sulit melacak urutan mutasi variabel (*spaghetti state*). |
| **Kurva Pembelajaran** | **Curam**. Konsep Currying, Monad, dan Komposisi memerlukan abstraksi matematika. | **Menengah**. Konsep class, inheritance, dan encapsulation lebih intuitif secara alami. | **Rendah**. Alur eksekusi langsung mencerminkan urutan instruksi mesin. |
| **Konkurensi & Paralelisme** | **Sempurna Secara Desain**. Ketiadaan status bersama (*no shared state*) mencegah *race condition*. | **Rentan**. Memerlukan mekanisme penguncian (*locking*, *mutex*) untuk menghindari tabrakan data. | **Sangat Rentan**. Rentan terhadap tabrakan status global saat asinkron/multithread. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Kebocoran Memori Akibat Retensi Closure (*Unintended Memory Retention*)
Ketika fungsi dalam menahan satu variabel kecil dari *lexical scope*, seluruh *Environment Record* yang berada pada scope tersebut tidak dapat dibersihkan oleh GC, termasuk variabel masif yang sebenarnya tidak digunakan lagi oleh fungsi dalam.

```javascript
// PITFALL: Memory Leak Tersembunyi via Lexical Retention
function heavyDataLeak() {
  const massiveData = new Array(5_000_000).fill("MEM_DRAIN"); // ~40MB di Heap
  const smallMetadata = "TX-2024";

  // GC TIDAK DAPAT membersihkan `massiveData` pada sebagian mesin V8
  // jika fungsi di bawah mempertahankan pointer ke context lexical yang sama!
  return function getMetadata() {
    return smallMetadata; 
  };
}

const leakRunner = heavyDataLeak(); 
// massiveData terus tertahan di Heap memori selama 'leakRunner' hidup!
```
**Mitigasi**: Selalu putus referensi variabel masif secara eksplisit jika fungsi dalam berumur panjang:
```javascript
function safeDataProcessor() {
  let massiveData = new Array(5_000_000).fill("MEM_DRAIN");
  const smallMetadata = "TX-2024";
  
  // Operasikan data...
  massiveData = null; // Putus referensi sebelum closure dikembalikan

  return function getMetadata() {
    return smallMetadata;
  };
}
```

### 2. Shallow Copy vs. Deep Mutation
Operator spread (`...`) atau `Object.assign()` **hanya melakukan penyalinan dangkal** (*shallow copy*). Properti bersarang (*nested properties*) tetap berbagi alamat memori yang sama.

```javascript
const user = Object.freeze({
  id: "U01",
  preferences: { theme: "dark" } // Objek bersarang TIDAK ter-freeze!
});

user.preferences.theme = "light"; // MUTASI BERHASIL! (Bugs tak terprediksi)
```

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Perangkap Mutasi `Array.prototype.sort()` dan `reverse()`
Secara keliru menganggap metode bawaan array bersifat fungsional:
```javascript
// SALAH: Memodifikasi parameter asli secara langsung
const getLowestScore = (scores) => {
  return scores.sort((a, b) => a - b)[0]; // Argumen 'scores' ikut terurut secara mutatif!
};

// BENAR: Mengkloning array sebelum sorting (atau menggunakan toSorted() di ES2023+)
const getLowestScoreSafe = (scores) => {
  return [...scores].sort((a, b) => a - b)[0];
  // atau ES2023+: return scores.toSorted((a, b) => a - b)[0];
};
```

### 2. Masalah *Looping Async* dengan Var (Classic Closure Trap)
```javascript
// SALAH: Lingkup fungsi 'var' menghasilkan closure yang mengikat satu variabel bersama
for (var i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 100); // Output: 3, 3, 3
}

// BENAR: Menggunakan 'let' yang menciptakan binding leksikal baru per iterasi
for (let i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 100); // Output: 0, 1, 2
}
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan Immutability Helpers ES2023+**: Adopsi metode non-mutasi modern seperti `Array.prototype.toSorted()`, `toReversed()`, `toSpliced()`, dan `with()`.
2.  **Point-Free Style Secara Pragmatis**: Tulis kode tanpa mendeklarasikan argumen sementara jika meningkatkan keterbacaan, namun hindari jika mengaburkan tipe argumen:
    ```javascript
    // Terlalu bertele-tele
    numbers.map((x) => double(x));
    
    // Bersih (Point-Free)
    numbers.map(double);
    ```
3.  **Batasi Panjang Pipeline Komposisi**: Pecah rantai komposisi pipa yang memiliki lebih dari 7 fungsi menjadi beberapa sub-pipeline logis untuk mempermudah *unit testing* dan isolasi kendala.
4.  **Enkapsulasi State Penuh**: Jangan mengekspos variabel lingkungan leksikal closure secara langsung. Sediakan API perantara dengan kontrak masukan yang tervalidasi.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. LRU (Least Recently Used) Memoization Menggunakan Closure
Menghindari komputasi deterministik yang mahal menggunakan LRU Cache untuk membatasi ukuran heap:

```javascript
const createLRUMemoizer = (fn, limit = 100) => {
  const cache = new Map();

  return (...args) => {
    const key = JSON.stringify(args);

    if (cache.has(key)) {
      // Refresh posisi key agar menjadi yang paling baru digunakan
      const value = cache.get(key);
      cache.delete(key);
      cache.set(key, value);
      return value;
    }

    const result = fn(...args);

    if (cache.size >= limit) {
      // Hapus item tertua (paling pertama dalam iterator Map)
      const oldestKey = cache.keys().next().value;
      cache.delete(oldestKey);
    }

    cache.set(key, result);
    return result;
  };
};
```

### 2. Menghindari Alokasi Objek Menengah di Hot Loops
Dalam pemrosesan jutaan baris data, penggunaan `.map().filter().reduce()` berturut-turut menciptakan banyak array perantara yang memicu kerja berat V8 *Garbage Collector* (terutama fase *Scavenger*). 
**Solusi**: Gunakan teknik *transducer* atau iterasi tunggal imperative di balik pembungkus fungsi murni (*pure boundary*) untuk performa skala tinggi:

```javascript
// Eksternal murni, internal teroptimasi tanpa instansiasi intermediate array
const processMassiveTransactions = (transactions) => {
  const results = [];
  for (let i = 0; i < transactions.length; i++) {
    const trx = transactions[i];
    if (trx.amount > 1000) { // filter
      results.push(trx.amount * 1.1); // map
    }
  }
  return Object.freeze(results);
};
```

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Mencegah Polusi Prototipe (*Prototype Pollution*) via Object Freezing
Penyerang sering mengeksploitasi fungsi transformasi fungsional yang menggabungkan objek secara rekursif (*deep merge*) untuk memanipulasi `__proto__`.

```javascript
const safeObjectMerge = (target, source) => {
  const output = { ...target };
  
  // Sanitasi key berisiko tinggi
  Object.keys(source).forEach(key => {
    if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
      return; // Abaikan injeksi atribut berbahaya
    }
    
    if (typeof source[key] === 'object' && source[key] !== null) {
      output[key] = safeObjectMerge(target[key] || {}, source[key]);
    } else {
      output[key] = source[key];
    }
  });

  return Object.freeze(output);
};
```

### 2. Hardening Closure State Melawan Inspeksi DevTools
Jangan pernah menyimpan informasi otentikasi rahasia (*API Secret, Encryption Key*) dalam *closure scope* di sisi klien (*browser runtime*), karena dapat diinspeksi menggunakan API debugging `console.dir()` atau debugger memori runtime. Simpan *sensitive state* secara eksklusif di lingkungan server terlindungi (*Node.js runtime*).

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Debugging rantai pipa fungsional sering kali menantang karena ketiadaan variabel perantara. Gunakan teknik HOF *Trace / Tap Utility* untuk menginspeksi nilai tanpa merusak alur data pipa.

```javascript
/**
 * Utility Higher-Order Function untuk logging deklaratif
 * Menerima tag penanda, mencatat log, dan mengembalikan data tanpa modifikasi.
 */
const trace = (tag) => (data) => {
  console.info(`[DEBUG: ${tag}] -> Timestamp: ${new Date().toISOString()}`);
  console.dir(data, { depth: null, colors: true });
  return data; // Wajib mengembalikan argumen secara transparan
};

// Pengaplikasian dalam pipe
const calculateDiscount = (x) => x * 0.9;
const addShipping = (x) => x + 15;

const checkoutPipeline = pipe(
  trace('NILAI_AWAL'),
  calculateDiscount,
  trace('SETELAH_DISKON'),
  addShipping,
  trace('TOTAL_AKHIR')
);

checkoutPipeline(200);
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Closure**: Retensi referensi ke *Lexical Scope* oleh sebuah fungsi bahkan setelah fungsi luar menyelesaikan eksekusinya dan dikeluarkan dari *Call Stack*.
*   **Pure Function**: Output murni bergantung pada input yang dipasok tanpa membangkitkan *side-effects*.
*   **Referential Transparency**: Kondisi di mana ekspresi fungsi dapat digantikan langsung oleh nilai kembaliannya tanpa mengubah sifat program.
*   **Currying**: Mengonversi $f(a, b, c)$ menjadi rantai unari $f(a)(b)(c)$.
*   **Pipe vs. Compose**:
    *   `pipe`: Eksekusi transformasi dari kiri-ke-kanan (*Left-to-Right* / Data-first).
    *   `compose`: Eksekusi transformasi dari kanan-ke-kiri (*Right-to-Left* / Math standard: $f \circ g$).
*   **Memory Management**: Berhati-hatilah dengan retensi closure jangka panjang; putus referensi variabel masif yang tidak lagi digunakan untuk membebaskan *Heap Memory*.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1.  **Apa yang menyebabkan sebuah variabel di dalam fungsi luar tetap bertahan di memori setelah fungsi tersebut selesai dieksekusi?**
    *   A. Variabel tersebut dideklarasikan menggunakan kata kunci `var`.
    *   B. Variabel tersebut dipindahkan ke *Call Stack* permanen.
    *   C. Terdapat *inner function* yang mempertahankan referensi leksikal terhadap variabel tersebut.
    *   D. Mesin JavaScript mematikan *Garbage Collector* saat fungsi bersarang didefinisikan.

2.  **Manakah dari fungsi berikut yang dikategorikan sebagai fungsi murni (*pure function*)?**
    *   A. `const add = (a, b) => a + b + Math.random();`
    *   B. `const append = (arr, elem) => { arr.push(elem); return arr; };`
    *   C. `const multiply = (x, y) => x * y;`
    *   D. `const logData = (data) => console.log(data);`

3.  **Operasi array JavaScript manakah yang bersifat mutatif secara default (*impure*)?**
    *   A. `Array.prototype.map`
    *   B. `Array.prototype.slice`
    *   C. `Array.prototype.filter`
    *   D. `Array.prototype.splice`

4.  **Apa representasi matematis dari implementasi fungsi `pipe(f, g)(x)`?**
    *   A. $f(g(x))$
    *   B. $g(f(x))$
    *   C. $f(x) \times g(x)$
    *   D. $g(x) + f(x)$

5.  **Di manakah mesin V8 mengalokasikan data variabel lingkungan leksikal yang ditahan oleh closure?**
    *   A. CPU Registers
    *   B. Execution Call Stack
    *   C. Heap Memory
    *   D. Disk Virtual Swap

---

### Soal Tingkat Menengah (Intermediate)

6.  **Perhatikan kode berikut. Apa output yang dicetak ke konsol?**
    ```javascript
    function setup() {
      let val = 10;
      return [() => val++, () => (val += 2), () => val];
    }
    const [fnA, fnB, fnC] = setup();
    fnA();
    fnB();
    console.log(fnC());
    ```
    *   A. `10`
    *   B. `11`
    *   C. `13`
    *   D. `NaN`

7.  **Mengapa penggunaan `Object.freeze()` sering kali belum cukup untuk menjamin imutabilitas absolut dalam paradigma fungsional?**
    *   A. Karena `Object.freeze()` menurunkan performa eksekusi JavaScript hingga 90%.
    *   B. Karena `Object.freeze()` hanya membekukan properti tingkat pertama (*shallow immutability*).
    *   C. Karena nilai primitif di dalamnya dapat diubah menggunakan operator `delete`.
    *   D. Karena `Object.freeze()` hanya berfungsi pada runtime Node.js, bukan peramban web (*browser*).

8.  **Apa perbedaan teknis mendasar antara teknik *Currying* dan *Partial Application*?**
    *   A. Currying selalu menghasilkan serangkaian fungsi unari (1 argumen), sedangkan Partial Application dapat menghasilkan fungsi dengan aritas berapapun.
    *   B. Partial Application hanya dapat menerima tipe data primitif, sedangkan Currying menerima tipe data kompleks.
    *   C. Currying membalikkan urutan evaluasi dari kanan ke kiri, sedangkan Partial Application dari kiri ke kanan.
    *   D. Tidak ada perbedaan; keduanya adalah istilah yang sama untuk konsep enkapsulasi closure.

9.  **Diberikan kode berikut:**
    ```javascript
    const multiply = (a) => (b) => (c) => a * b * c;
    const doubleAndTriple = multiply(2)(3);
    console.log(doubleAndTriple(4));
    ```
    **Berapa aritas (*arity*) dari konstanta `doubleAndTriple`?**
    *   A. 0
    *   B. 1
    *   C. 2
    *   D. 3

10. **Bagaimana mekanisme *Garbage Collector* (GC) menangani siklus referensi silang leksikal antara dua closure yang tidak lagi dapat diakses dari *Root Objects* (*Unreachable*)?**
    *   A. GC mengalami kegagalan sistem (*out of memory*) karena referensi silang tidak dapat diselesaikan.
    *   B. Algoritma modern *Mark-and-Sweep* melacak keterjangkauan dari Root; jika siklus tersebut *unreachable*, seluruh siklus dialokasikan untuk pembersihan.
    *   C. GC membekukan thread utama eksekusi untuk membersihkan closure secara paksa.
    *   D. Memori hanya dibersihkan saat proses instansiasi V8 ditutup sepenuhnya.

---

### Kunci Jawaban & Pembahasan Singkat

1.  **Jawaban: C**. Closure menahan *outer lexical environment record* di memori heap selama *inner function* masih berpotensi dieksekusi.
2.  **Jawaban: C**. `multiply` deterministik dan tidak menghasilkan efek samping. A tidak deterministik (`Math.random()`), B memutasi parameter masukan, D menghasilkan I/O *side effect*.
3.  **Jawaban: D**. `Array.prototype.splice` memotong dan memodifikasi array asal secara mutatif (*in-place*).
4.  **Jawaban: B**. `pipe` mengevaluasi secara *left-to-right*: $f$ dijalankan terlebih dahulu, kemudian hasilnya dioperasikan ke dalam $g$, yang merepresentasikan $g(f(x))$.
5.  **Jawaban: C**. Variabel yang hidup melampaui siklus hidup *stack frame* fungsi pembungkusnya harus dialokasikan ke dalam *Heap Memory*.
6.  **Jawaban: C**. Ketiga fungsi berbagi *Lexical Environment* yang sama: `fnA` mengubah $10 \rightarrow 11$, `fnB` menambahkan $2 \rightarrow 13$, dan `fnC` membaca nilai akhir yaitu $13$.
7.  **Jawaban: B**. `Object.freeze()` bersifat *shallow*. Properti bersarang berupa objek lain tetap dapat dimutasi secara bebas kecuali jika dilakukan pembekuan rekursif (*deep freeze*).
8.  **Jawaban: A**. Currying secara ketat memecah fungsi multi-argumen menjadi rantai fungsi-fungsi unari ($1 \text{ argumen}$). Partial application menetapkan beberapa nilai argumen di muka, menyisakan fungsi dengan aritas $\ge 1$.
9.  **Jawaban: B**. `doubleAndTriple` merepresentasikan fungsi `(c) => a * b * c` yang membutuhkan tepat 1 argumen tersisa. Aritasnya adalah 1.
10. **Jawaban: B**. Mesin JavaScript modern menggunakan pelacakan keterjangkauan (*reachability from root*). Referensi sirkular internal yang terisolasi dari *global context root* akan tetap teridentifikasi sebagai sampah dan dibersihkan oleh algoritma *Mark-and-Sweep*.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Instruksi Proyek:
Rancang dan bangun sebuah modul **In-Memory Functional Event-Driven State Store** bernama `FStore` tanpa pustaka eksternal.

### Kriteria Fungsional & Persyaratan Arsitektural:
1.  **State Immobility**: Status utama aplikasi tersimpan dalam *closure* privat. Tidak ada akses mutasi langsung ke objek status (`fStore.state = ...` harus gagal atau tidak berefek).
2.  **Dispatch Transform Pipeline**: Pembaruan status hanya dapat dijalankan melalui pengiriman aksi (*Action Dispatch*) yang mengalirkan status saat ini melalui rantai fungsi *reducer* murni:
    $$\text{NewState} = \text{reducer}(\text{CurrentState}, \text{Action})$$
3.  **Deep Freeze On Emission**: Setiap kali status baru terbentuk, bekukan seluruh hierarki status secara mendalam (*deep freeze*) sebelum dikirimkan ke fungsi pendengar (*listeners*).
4.  **Curried Selectors**: Buat fungsionalitas pemilih status (*selectors*) yang ter-curry untuk mengekstrak cabang data tertentu secara efisien.
5.  **Memory-Safe Subscriptions**: Metode `subscribe(listener)` harus mengembalikan fungsi pembersih unari `unsubscribe()` yang memutus penahanan referensi fungsi pendengar di memori internal *closure* untuk mencegah *memory leaks*.

### Boilerplate Awal untuk Memulai:

```javascript
// Implementasikan logika fungsional murni Anda di sini
const createFStore = (rootReducer, initialValue = {}) => {
  // TODO: Definisikan private lexical environment variables
  
  return {
    dispatch: (action) => {
      // TODO: Alirkan state melalui rootReducer murni
    },
    getState: () => {
      // TODO: Kembalikan snapshot imutabel
    },
    subscribe: (listener) => {
      // TODO: Daftarkan listener dan kembalikan fungsi unregister
    }
  };
};

// Pengujian Sederhana:
const counterReducer = (state = { count: 0 }, action) => {
  switch (action.type) {
    case 'INC': return { ...state, count: state.count + 1 };
    case 'SET': return { ...state, count: action.payload };
    default: return state;
  }
};

const store = createFStore(counterReducer, { count: 0 });
const unsubscribe = store.subscribe((state) => {
  console.log("State updated:", state);
});

store.dispatch({ type: 'INC' }); // State updated: { count: 1 }
unsubscribe();
store.dispatch({ type: 'INC' }); // Tidak mencetak log (Listener berhasil dibersihkan dari memori)
```

Gunakan profil memori (*Memory Profiler Heap Snapshot*) di DevTools untuk memastikan bahwa setelah `unsubscribe()` dijalankan, fungsi pendengar tidak lagi tertahan di *Heap Memory*. Buktikan pemahaman Anda tentang paradigma fungsional melalui abstraksi kode yang tangguh, elegan, dan aman.