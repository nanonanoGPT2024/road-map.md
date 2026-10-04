# Bab 03 Module 01: Functions, Signatures, & Context Execution

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 02-Programming-Languages
* **Topik Utama:** TypeScript
* **Kode Modul:** TS-0301
* **Judul Modul:** Functions, Signatures, & Context Execution
* **Prasyarat:** Pemahaman fundamental tipe primitif, deklarasi `interface`/`type alias`, pemahaman dasar *lexical scoping* dan *prototype chain* JavaScript.
* **Tingkat Kesulitan:** Intermediate ke Advanced
* **Alokasi Waktu Belajar:** 4-6 Jam Pembelajaran Mandiri + Praktik Terarah

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Memilih Tipe Deklarasi Fungsi:** Mengidentifikasi perbedaan mendasar antara *Call Signatures*, *Construct Signatures*, *Method Signatures*, dan *Function Declarations/Expressions* dalam TypeScript.
2. **Menguasai Function Overloading:** Merancang dan mengimplementasikan *overload signatures* dengan satu *implementation signature* yang aman secara tipe (*type-safe*).
3. **Mengisolasi dan Mengontrol Konteks Eksekusi (`this`):** Menggunakan tipe parameter `this` secara eksplisit, memahami batasan *lexical scoping* pada *arrow functions*, serta mencegah *context loss* pada saat *runtime dispatching*.
4. **Memahami Mekanisme Variansi Parameter:** Menjelaskan perbedaan perilaku *bivariant* vs *contravariant* pada parameter fungsi di bawah bendera kompilasi `--strictFunctionTypes`.
5. **Membangun Arsitektur Handler yang Robust:** Menerapkan abstraksi fungsi fleksibel untuk arsitektur berbasis event, middleware, dan asynchronous pipelines dengan jaminan keamanan tipe statis tingkat tinggi.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam JavaScript biasa, fungsi adalah *first-class citizen* yang dinamis dan fleksibel. Anda dapat melekatkan properti ke dalamnya, memanggilnya sebagai konstruktor menggunakan kata kunci `new`, mengubah konteks `this` sesuka hati menggunakan `.bind()`, `.call()`, atau `.apply()`, serta menerima argumen dalam jumlah dan tipe yang tidak terduga. Fleksibilitas ini sering kali menjadi sumber *runtime error* fatal (`TypeError: Cannot read properties of undefined`).

Di TypeScript, mental model Anda harus bergeser:

```
[ Mental Model JavaScript Tradisional ]
Fungsi = Blok instruksi eksekusi + Konteks dinamis (this) yang ditentukan pada waktu pemanggilan (call-site).

                    VS

[ Mental Model TypeScript Enterprise ]
Fungsi = Kontrak Tipe Multidimensi (Call, Construct, Properties) 
         + Strict Input/Output Types 
         + Context Constraint (Inferred/Explicit Execution Context)
```

Fungsi di TypeScript bukan sekadar blok instruksi yang menerima argumen dan mengembalikan nilai. Fungsi adalah **kontrak formal**. Setiap fungsi membawa tiga batasan utama:
1. **Domain Kontrak (Argumen/Parameter):** Apa yang diizinkan masuk dan bagaimana variansinya (*contravariance*).
2. **Codomain Kontrak (Return Value):** Jaminan apa yang akan dikembalikan kepada pemanggil (*covariance*).
3. **Context Kontrak (`this`):** Ruang lingkup internal apa yang dipersyaratkan oleh fungsi ketika ia dijalankan.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Mekanisme parsing, inferensi tipe, dan resolusi eksekusi fungsi di TypeScript digambarkan sebagai berikut:

```
+-------------------------------------------------------------------------+
|                        Kompilasi TypeScript                             |
+-------------------------------------------------------------------------+
    |
    v
[Function Call-Site] ---> fn(arg1, arg2)
    |
    +---> 1. Overload Resolution Match
    |     |
    |     |-- Check Overload 1 (arg1: TypeA) -> Match? --> Gunakan Return Type 1
    |     |-- Check Overload 2 (arg1: TypeB) -> Match? --> Gunakan Return Type 2
    |     \-- Tidak ada match? -------------> Emit TS2769 (No overload matches)
    |
    +---> 2. Variance & Argument Checking (--strictFunctionTypes)
    |     |
    |     |-- Arg Type <: Param Type (Contravariant check)
    |     \-- Incompatible? ----------------> Emit TS2345 (Argument not assignable)
    |
    +---> 3. Contextual Typing & 'this' Verification
          |
          |-- Function butuh 'this: TargetContext'?
          |-- Apakah pemanggil menyediakan target context yang cocok?
          \-- Context Invalid? -------------> Emit TS2684 (The 'this' context...)
    |
    v
[Type Check Passed] ---> Emit ke JavaScript (Strip Types)
```

Alur siklus penentuan `this` pada waktu eksekusi (Runtime Execution Context):

```
+-------------------------------------------------------------------------+
|                  Runtime Execution Context (Call-Site)                  |
+-------------------------------------------------------------------------+
                               |
            Apakah fungsi dipanggil via 'new'?
                               |
                   +-----------+-----------+
                   | YA                    | TIDAK
                   v                       v
          [this = Object Baru]   Apakah Arrow Function?
                                           |
                               +-----------+-----------+
                               | YA                    | TIDAK
                               v                       v
                      [this = Scope Lexical]  Apakah dipanggil via 'obj.fn()'?
                                                       |
                                           +-----------+-----------+
                                           | YA                    | TIDAK
                                           v                       v
                                  [this = Base Object]   [this = Global/Undefined]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Call Signatures vs Construct Signatures

Dalam TypeScript, sebuah objek fungsi dapat memiliki lebih dari satu jenis signature dalam *type alias* atau *interface*:

```typescript
type ComplexCallable = {
  // Call Signature: memungkinkan objek dipanggil langsung `obj(arg)`
  (input: string): number;
  
  // Construct Signature: memungkinkan objek dipanggil via `new obj(arg)`
  new (capacity: number): Date;
  
  // Method/Property Signatures: properti statis yang menempel pada objek fungsi
  version: string;
};
```

### 2. Method Syntax Shorthand vs Property Function Type

Terdapat perbedaan kritis internal antara:
* **Method Shorthand Syntax:** `{ run(x: string): void; }`
* **Property Signature Syntax:** `{ run: (x: string) => void; }`

Di bawah compiler flag `--strictFunctionTypes`, method shorthand syntax diperlakukan secara **bivariant** pada parameternya (untuk mempertahankan kompatibilitas dengan hierarki tipe bawaan DOM dan Array di JavaScript), sedangkan property signature dievaluasi secara **contravariant** (jauh lebih aman).

### 3. Tipe Eksekusi Konteks (`this`)

TypeScript mengizinkan parameter semu (*pseudo-parameter*) bernama `this` di posisi pertama argumen fungsi. Parameter ini sepenuhnya dihilangkan (*erased*) saat kompilasi ke JavaScript:

```typescript
// TypeScript Source
function execute(this: DatabaseConnection, query: string): void {
  this.send(query);
}

// Emitted JavaScript Output
function execute(query) {
  this.send(query);
}
```

Jika fungsi di atas dipanggil tanpa binding konteks `DatabaseConnection` yang valid, type-checker TypeScript akan menghentikan kompilasi dengan galat.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Contravariance pada Parameter Fungsi

Secara intuitif, jika `Dog` adalah turunan dari `Animal` (`Dog extends Animal`), kita mungkin mengira bahwa `(d: Dog) => void` dapat ditugaskan ke `(a: Animal) => void`. Namun secara matematis dan logika sistem tipe, yang terjadi adalah **kebalikannya**:

```
Subtipe Hirarki:
Dog <: Animal  (Dog adalah subtipe dari Animal)

Variansi Fungsi:
(a: Animal) => void <: (d: Dog) => void
```

Fungsi yang menerima tipe yang lebih luas (`Animal`) dapat menggantikan fungsi yang meminta tipe yang lebih spesifik (`Dog`), karena fungsi penerima `Animal` dijamin aman ketika diberikan instansi `Dog`. Sebaliknya, jika sebuah fungsi yang membutuhkan `Dog` (dan memanggil `dog.bark()`) dipanggil dengan `Cat` (yang merupakan `Animal`), program akan crash saat *runtime*.

Flag kompilasi `strictFunctionTypes: true` memaksa parameter dievaluasi secara contravariant, mencegah runtime crash akibat unsafe downcasting.

### Function Overloading: Internal Matching Mechanics

Overloading di TypeScript berbeda dari bahasa seperti Java atau C++. Di TypeScript, overloading murni ada di level sistem tipe statis (*compile-time*). Tidak ada pemisahan biner fungsi di tingkat JavaScript runtime.

Aturan kompilator untuk Overloading:
1. Menilai overload signatures dari atas ke bawah. Pencocokan pertama yang valid (*first match*) akan dipilih.
2. Parameter overload signature yang paling spesifik harus diletakkan di bagian atas.
3. *Implementation signature* harus mencakup *union* dari semua signature di atasnya dan tidak dapat diakses langsung oleh pemanggil.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL (STEP-BY-STEP)

Berikut adalah penerapan bertahap dari deklarasi fungsi standar hingga implementasi overloading dan strict context checking:

```typescript
// -------------------------------------------------------------
// LANGKAH 1: Menentukan Tipe Call Signatures
// -------------------------------------------------------------
type FormatterFn = (value: number, currencyPrefix?: string) => string;

const standardFormatter: FormatterFn = (val, prefix = "$") => {
  return `${prefix}${val.toFixed(2)}`;
};

// -------------------------------------------------------------
// LANGKAH 2: Contextual This Control via Pseudo-Parameter
// -------------------------------------------------------------
interface WorkerThread {
  id: string;
  isBusy: boolean;
}

function processTask(this: WorkerThread, taskName: string): void {
  if (this.isBusy) {
    throw new Error(`Worker ${this.id} is currently unavailable.`);
  }
  console.log(`Worker ${this.id} executing: ${taskName}`);
}

const workerNodeA: WorkerThread = { id: "node-alpha", isBusy: false };

// Pemanggilan valid via function call-site binding
processTask.call(workerNodeA, "CompileAssets");

// -------------------------------------------------------------
// LANGKAH 3: Function Overloading
// -------------------------------------------------------------
interface DataPayload {
  raw: Uint8Array;
}

// Overload Signature 1: Menerima string, mengembalikan Record
function parseInput(input: string): Record<string, unknown>;

// Overload Signature 2: Menerima DataPayload, mengembalikan string
function parseInput(input: DataPayload): string;

// Overload Signature 3: Menerima buffer langsung beserta encoding
function parseInput(input: Uint8Array, encoding: "utf-8" | "hex"): string;

// Implementation Signature (Internal, menyatukan seluruh skenario)
function parseInput(
  input: string | DataPayload | Uint8Array,
  encoding?: "utf-8" | "hex"
): Record<string, unknown> | string {
  if (typeof input === "string") {
    return JSON.parse(input) as Record<string, unknown>;
  }

  if (input instanceof Uint8Array) {
    const enc = encoding ?? "utf-8";
    return new TextDecoder(enc).decode(input);
  }

  // Fallback untuk DataPayload
  return new TextDecoder("utf-8").decode(input.raw);
}

// Pengujian pemanggilan tipe overload:
const res1 = parseInput('{"status": "ok"}'); // Inferred type: Record<string, unknown>
const res2 = parseInput({ raw: new Uint8Array([72, 101, 108, 108, 111]) }); // Inferred type: string
const res3 = parseInput(new Uint8Array([104, 101, 120]), "hex"); // Inferred type: string
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Menganalisis implementasi blok kode pada **SEKSI 07 (Langkah 3)**:

* **Baris 29:** `function parseInput(input: string): Record<string, unknown>;`
  * Overload signature pertama. Mengikat tipe argumen string dengan kembalian objek `Record<string, unknown>`. Tidak menyertakan kurung kurawal tubuh fungsi (`{}`).
* **Baris 32:** `function parseInput(input: DataPayload): string;`
  * Overload signature kedua. Memvalidasi bahwa jika masukan bertipe objek `DataPayload`, maka nilai kembali dijamin berupa `string`.
* **Baris 35:** `function parseInput(input: Uint8Array, encoding: "utf-8" | "hex"): string;`
  * Overload signature ketiga. Mengharuskan pemanggil menyertakan argumen kedua (`encoding`) jika argumen pertama adalah instance `Uint8Array`.
* **Baris 38–41:** `function parseInput(input: string | DataPayload | Uint8Array, encoding?: "utf-8" | "hex"): Record<string, unknown> | string`
  * Merupakan *Implementation Signature*. Parameter `input` harus berupa union dari parameter-parameter overload di atasnya. Parameter `encoding` wajib ditandai opsional (`?`) karena pada signature 1 dan 2, parameter ini tidak ada.
* **Baris 42–51:** Blok internal implementasi.
  * Tipe di dalam blok ini harus melakukan diskriminasi tipe manual (*type narrowing* menggunakan `typeof`, `instanceof`, atau `in`) untuk memastikan cabang pengembalian mengembalikan tipe yang sesuai. Implementation signature tidak terlihat oleh consumer di luar file saat kompilasi modul.

---

## SEKSI 09 — STUDI KASUS NYATA

### Sistem Event Pipeline & Dispatcher untuk Platform Transaksi Finansial

Sebuah arsitektur microservices finansial membutuhkan modul transaksi lokal yang memproses operasi akun ledger. Masalah yang sering terjadi adalah:
1. Kegagalan referensi `this` saat callback dieksekusi di thread pool asinkron.
2. Tidak adanya tipe statis antara event yang di-*emit* dengan fungsi pendengar (*listener*), yang memicu kegagalan runtime bila skema payload berubah.
3. Fungsi listener tidak sengaja mengubah data internal state dispatcher.

Kita akan merancang **Strict Event Dispatcher Engine** yang:
* Mengamankan execution context melalui typing `this: void` pada callback listener untuk mencegah akses mutasi internal instance emitter.
* Menerapkan overloading call-signatures untuk multi-format event logging.
* Menerapkan contravariant listener validation untuk memastikan pipeline listener tipe aman.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut implementasi lengkap arsitektur event-driven pipeline yang memenuhi batasan di atas:

```typescript
// ============================================================================
// File: src/engine/TransactionEventPipeline.ts
// ============================================================================

export interface TransactionPayload {
  readonly transactionId: string;
  readonly accountId: string;
  readonly amount: number;
  readonly timestamp: number;
}

export interface AuditLogPayload {
  readonly level: "INFO" | "WARN" | "CRITICAL";
  readonly message: string;
}

// Peta Event ke Tipe Payload Masing-Masing
export interface EventRegistry {
  "transaction:created": TransactionPayload;
  "transaction:committed": TransactionPayload;
  "audit:log": AuditLogPayload;
}

// Tipe callback listener yang dilarang mengakses runtime 'this' context dispatcher
export type SafeEventListener<TData> = (this: void, data: TData) => void | Promise<void>;

export class TransactionPipelineEngine {
  private listeners: {
    [K in keyof EventRegistry]?: Array<SafeEventListener<EventRegistry[K]>>;
  } = {};

  // Register Event Listener
  public on<K extends keyof EventRegistry>(
    event: K,
    listener: SafeEventListener<EventRegistry[K]>
  ): void {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    // Cast dihindari, tipe terisolasi secara struktural
    const bucket = this.listeners[event] as Array<SafeEventListener<EventRegistry[K]>>;
    bucket.push(listener);
  }

  // FUNCTION OVERLOADING: Emit signature terisolasi berdasarkan kompleksitas data
  public emit(event: "audit:log", message: string, level?: "INFO" | "WARN" | "CRITICAL"): Promise<void>;
  public emit<K extends keyof EventRegistry>(event: K, payload: EventRegistry[K]): Promise<void>;
  public async emit(
    event: keyof EventRegistry,
    payloadOrMessage: unknown,
    maybeLevel?: "INFO" | "WARN" | "CRITICAL"
  ): Promise<void> {
    let resolvedPayload: unknown;

    if (event === "audit:log" && typeof payloadOrMessage === "string") {
      resolvedPayload = {
        message: payloadOrMessage,
        level: maybeLevel ?? "INFO",
      } satisfies AuditLogPayload;
    } else {
      resolvedPayload = payloadOrMessage;
    }

    const currentListeners = this.listeners[event];
    if (!currentListeners || currentListeners.length === 0) {
      return;
    }

    for (const listener of currentListeners) {
      // Pemanggilan aman: konteks 'this' diikat secara eksplisit ke 'undefined' via call
      // Mencegah context hijacking ke instance TransactionPipelineEngine
      await (listener as (this: void, data: unknown) => void | Promise<void>).call(
        undefined,
        resolvedPayload
      );
    }
  }
}

// ============================================================================
// Verifikasi Runtime & Skenario Penggunaan
// ============================================================================
async function runSystem() {
  const engine = new TransactionPipelineEngine();

  // Daftarkan listener tipe aman
  engine.on("transaction:created", function (this: void, data) {
    // Parameter 'data' terinferensi otomatis sebagai TransactionPayload
    console.log(`[Tx Engine] Transaksi ${data.transactionId} sebesar ${data.amount} diterima.`);
    // Mengakses this.listeners di sini akan menyebabkan error kompilasi karena `this: void`
  });

  engine.on("audit:log", (data) => {
    // Parameter 'data' terinferensi otomatis sebagai AuditLogPayload
    console.log(`[Audit] [${data.level}] ${data.message}`);
  });

  // Uji Pemanggilan Overload 1 (Audit Log Shorthand)
  await engine.emit("audit:log", "Service pipeline successfully booted.", "INFO");

  // Uji Pemanggilan Overload 2 (Strict Event Key)
  await engine.emit("transaction:created", {
    transactionId: "TX-998811",
    accountId: "ACC-00129",
    amount: 154000.5,
    timestamp: Date.now(),
  });
}

runSystem().catch(console.error);
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Pola Deklarasi | Kelebihan | Kekurangan | Dampak Kompilasi & Runtime | Kapan Harus Digunakan |
| :--- | :--- | :--- | :--- | :--- |
| **Arrow Function Property** `prop: () => void` | Menjaga referensi `this` leksikal otomatis tanpa `.bind()`. | Mengonsumsi alokasi memori tambahan per instance; tidak ada di prototype object. | Parameter dievaluasi secara contravariant di bawah `--strictFunctionTypes`. | Digunakan untuk event callback class method yang diteruskan ke DOM/asinkron. |
| **Method Prototype Shorthand** `method(): void` | Efisien secara memori karena hanya ada 1 salinan fungsi di level prototype. | Konteks `this` dapat terlepas (*lost context*) jika fungsi diekstrak dari objek. | Parameter dievaluasi secara bivariant (berpotensi celah type safety). | Digunakan pada class domain model/entitas yang memiliki ribuan instansiasi aktif. |
| **Function Overloading** `fn(a: X): Y; fn(a: Z): W;` | Pengalaman DX optimal, signature fleksibel untuk berbagai tipe data. | Memerlukan runtime type narrowing yang kompleks pada implementation signature. | Tidak ada emit overhead runtime, pure compiler meta-layer. | API publik library, parsing multitipe, builder pattern. |
| **Union Signature Single Param** `fn(a: X \| Z): Y \| W;` | Mudah ditulis, tidak butuh pengulangan deklarasi function signature. | Hubungan antara tipe input tertentu dan return type tertentu hilang (*loosely coupled*). | Rentan memerlukan type assertion (`as`) pada call-site. | Fungsi sederhana di mana return type sama untuk semua tipe variasi parameter. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Kehilangan Konteks `this` Akibat Destructuring Method
Ketika Anda melakukan destructuring method dari objek, pointer `this` runtime akan terputus dari objek induknya:

```typescript
class SessionService {
  private token: string = "secret-token";

  public getToken(this: SessionService): string {
    return this.token;
  }
}

const service = new SessionService();
const { getToken } = service;

// COMPILE ERROR: TypeScript TS2684 mendeteksi kehilangan context
// 'The 'this' context of type 'void' is not assignable to method's 'this' of type 'SessionService'.'
// console.log(getToken()); 

// SOLUSI:
console.log(getToken.call(service)); // Valid
```

### 2. Overload Order Masking Problem
Kompilator TypeScript memilih overload signature pertama yang kompatibel secara struktural. Menempatkan tipe yang lebih luas di atas tipe yang lebih sempit akan mematikan (*shadowing*) signature di bawahnya:

```typescript
// MASALAH: Overload 'any' atau 'unknown' atau tipe luas di atas
function processData(x: unknown): string;
function processData(x: string): number; // DEAD SIGNATURE! Tidak akan pernah tercapai.
function processData(x: unknown): string | number {
  return typeof x === "string" ? x.length : "unknown";
}

const result = processData("hello"); 
// result bertipe 'string' di compile-time, meskipun saat runtime bernilai number (5)!
```

### 3. Ketidakcocokan Antara Signature dan Implementasi
TypeScript hanya memverifikasi bahwa *Implementation Signature* kompatibel secara umum dengan overload-nya. TypeScript tidak memeriksa apakah tubuh fungsi benar-benar mengembalikan tipe X ketika inputnya tipe Y secara spesifik:

```typescript
function getLength(x: string): number;
function getLength(x: any[]): number;
function getLength(x: string | any[]): any {
  // Kompilator TIDAK memaksa Anda mengembalikan logic yang presisi untuk string vs array
  return "bukan-angka"; // Tipe kembali 'any' pada implementasi melumpuhkan safety check
}
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mengabaikan Parameter `this` pada Fungsi Callback DOM / EventEmitter

```typescript
// SALAH: Listener mengakses `this` tanpa definisi tipe statis
button.addEventListener("click", function () {
  this.classList.toggle("active"); // Error TS2683: 'this' implicitly has type 'any'
});

// BENAR: Deklarasikan parameter `this` secara eksplisit
button.addEventListener("click", function (this: HTMLButtonElement) {
  this.classList.toggle("active"); // Type-safe dan terverifikasi
});
```

### Kesalahan 2: Menggunakan Arrow Function di Dalam Objek Literal Ketika Membutuhkan Konteks `this`

```typescript
// SALAH: Arrow function menangkap konteks leksikal luar (misal: window / global scope)
const counter = {
  count: 0,
  increment: () => {
    // TS2683: 'this' implicitly has type 'any' karena diikat ke root scope module
    // this.count++; 
  }
};

// BENAR: Gunakan method declaration biasa dengan explicit this typing
const counterProper = {
  count: 0,
  increment(this: { count: number }) {
    this.count++;
  }
};
```

### Kesalahan 3: Memanggil Overload Melalui Dynamic Union

```typescript
function format(v: string): string;
function format(v: number): number;
function format(v: string | number): string | number {
  return v;
}

const dynamicVal: string | number = Math.random() > 0.5 ? "text" : 100;

// SALAH: TS2769: No overload matches this call.
// Overload lookup tidak otomatis mendistribusikan union ke masing-masing signature overload!
// format(dynamicVal);

// BENAR: Lakukan Type Narrowing terlebih dahulu di call-site
if (typeof dynamicVal === "string") {
  format(dynamicVal); // Resolves to Overload 1
} else {
  format(dynamicVal); // Resolves to Overload 2
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Selalu Aktifkan `noImplicitThis` dan `strictFunctionTypes`:** Cantumkan kedua opsi ini di dalam konfigurasi `tsconfig.json` di bawah blok `"compilerOptions": { "strict": true }`.
2. **Prioritaskan Generic Conditional Types untuk Multiple Signatures Sederhana:** Jika Anda hanya butuh memetakan Type A -> Return A dan Type B -> Return B, pertimbangkan Generic ketimbang Function Overloading berantai:
   ```typescript
   // Alternatif Overloading yang lebih terawat via Generic:
   function executeOperation<T extends string | number>(
     param: T
   ): T extends string ? string[] : number[] {
     // implementation...
     return [] as any;
   }
   ```
3. **Isolasi Konteks Callback dengan `this: void`:** Jika sebuah API callback atau event handler tidak dirancang untuk diakses state internalnya melalui `this`, selalu tambahkan parameter `this: void`. Hal ini mencegah developer lain secara tidak sengaja bergantung pada `this`.
4. **Urutkan Overload dari yang Paling Spesifik ke yang Paling Umum:** Tempatkan literal types (`"GET" | "POST"`), objek kompleks, dan subkelas di baris paling atas, disusul tipe primitif generic (`string`, `number`), dan generic fallback di paling bawah.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Biaya Alokasi Memori: Prototype vs Instance Closure

Jika Anda mendesain kelas dengan ribuan objek yang dialokasikan dalam waktu singkat (high-throughput application):

```typescript
// TIDAK EFISIEN: Setiap instansi mengalokasikan fungsi anonim baru di memori
class MemoryHeavyHandler {
  public handle = (): void => {
    /* ... */
  };
}

// EFISIEN: Hanya ada satu referensi fungsi di prototype chain
class MemoryEfficientHandler {
  public handle(this: MemoryEfficientHandler): void {
    /* ... */
  }
}
```

Jika fungsi pada `MemoryEfficientHandler` harus dipassing sebagai callback, binding manual pada constructor atau pemanggilan lewat wrapper inline `() => inst.handle()` tetap jauh lebih murah dalam skala besar dibanding mendefinisikan arrow method di field class property.

---

## SEKSI 16 — KEAMANAN & HARDENING

### Mencegah Prototype Pollution via Execution Context Binding

Ketika mengeksekusi fungsi yang diterima dari plugin luar atau modul runtime dinamis, jangan biarkan konteks runtime `this` merujuk ke global context (`globalThis` atau `window`).

```typescript
// Pola Hardening Pemanggilan Fungsi Tidak Tepercaya
type ExternalPluginHandler = (this: void, payload: Record<string, unknown>) => void;

function executePluginSecurely(
  pluginFn: ExternalPluginHandler,
  data: Record<string, unknown>
): void {
  // 1. Bekukan data masukan untuk mencegah mutasi state sistem
  const immutablePayload = Object.freeze({ ...data });

  // 2. Paksa this menjadi null atau undefined, mencegah akses ke properti constructor / prototype
  Reflect.apply(pluginFn, Object.freeze(Object.create(null)), [immutablePayload]);
}
```

Dengan mendeklarasikan parameter `this: void`, sistem tipe TypeScript akan menolak callback plugin yang mencoba mengakses properti via `this.systemEngine`.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Untuk melacak siklus hidup eksekusi fungsi tanpa merusak signature aslinya, gunakan teknik **Higher-Order Function Wrap (Decorator Pattern)** dengan melestarikan call signature dan context tipe:

```typescript
import { performance } from "perf_hooks";

// HOF yang menjaga Type Signatures dan Context asli
export function withTelemetry<TContext, TArgs extends unknown[], TReturn>(
  targetName: string,
  fn: (this: TContext, ...args: TArgs) => TReturn
): (this: TContext, ...args: TArgs) => TReturn {
  return function (this: TContext, ...args: TArgs): TReturn {
    const start = performance.now();
    try {
      const result = fn.apply(this, args);
      const executionTime = (performance.now() - start).toFixed(4);
      console.log(`[Metrics] ${targetName} executed in ${executionTime}ms`);
      return result;
    } catch (error) {
      console.error(`[Error Trace] Failure in ${targetName}:`, error);
      throw error;
    }
  };
}

// Penggunaan:
interface DatabaseRepository {
  dbUrl: string;
  fetchUser(this: DatabaseRepository, id: string): { id: string; name: string };
}

const repo: DatabaseRepository = {
  dbUrl: "postgres://cluster-01",
  fetchUser(this: DatabaseRepository, id: string) {
    return { id, name: "System Admin" };
  },
};

// Mengikat telemetry ke repo method dengan type checking penuh
repo.fetchUser = withTelemetry("DatabaseRepository.fetchUser", repo.fetchUser);
repo.fetchUser("USR-101");
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Call Signature:** `(x: number) => string` mendefinisikan signature fungsi murni.
* **Construct Signature:** `new (x: number): TargetClass` digunakan untuk fungsi pabrik / constructor.
* **Method Shorthand:** `{ method(x: string): void; }` di bawah strict mode dievaluasi secara *bivariant* (kurang aman).
* **Property Function:** `{ method: (x: string) => void; }` dievaluasi secara *contravariant* (sangat aman).
* **Parameter `this`:** Parameter semu di posisi pertama: `function run(this: Worker, step: number): void;`. Diabaikan pada runtime JS.
* **Mencegah Akses `this`:** Gunakan parameter `this: void`.
* **Overloading:** Tulis deklarasi overload dari yang **paling spesifik** ke **paling umum**. Implementation signature tidak dipublikasikan ke call-site.
* **Arrow Functions:** Tidak memiliki `this` sendiri, menangkap `this` dari lexical enclosing scope. Tidak bisa digunakan sebagai constructor (tidak memiliki construct signature).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1 - 5)

1. **Apa tujuan dari menyertakan parameter `this: void` dalam signature fungsi TypeScript?**
   * A. Menginstruksikan fungsi agar tidak mengembalikan nilai.
   * B. Memastikan kompilator melarang pemanggilan fungsi yang mencoba mengakses properti dari objek `this`.
   * C. Menghapus referensi memori dari parameter argumen setelah fungsi selesai dieksekusi.
   * D. Menjadikan fungsi tersebut berjalan secara asynchronous di background worker.

2. **Perhatikan kode berikut. Berapakah jumlah overload signatures yang dimiliki fungsi ini?**
   ```typescript
   function sync(id: string): boolean;
   function sync(id: number): boolean;
   function sync(id: string | number): boolean {
     return true;
   }
   ```
   * A. 3
   * B. 1
   * C. 2
   * D. 0

3. **Bagaimana keluaran JavaScript (emitted output) dari parameter semu `this: CustomType` pada kompilasi target ES6?**
   * A. Diubah menjadi argumen biasa bernama `_this`.
   * B. Dikonversi menjadi panggilan `Object.bind()`.
   * C. Dikonversi menjadi variabel runtime di tubuh fungsi.
   * D. Dihilangkan sepenuhnya (*erased*) dari daftar parameter.

4. **Tipe function signature mana yang dievaluasi secara Contravariant terhadap parameter di bawah opsi `strictFunctionTypes: true`?**
   * A. `interface Machine { start(force: boolean): void; }`
   * B. `interface Machine { start: (force: boolean) => void; }`
   * C. `function start(this: Machine, force: boolean): void {}`
   * D. `class Machine { start(force: boolean) {} }`

5. **Apa yang terjadi jika Anda memanggil arrow function menggunakan metode `.call(newContext)`?**
   * A. Konteks eksekusi runtime `this` akan berubah sesuai objek `newContext`.
   * B. Kompilator TypeScript akan menghasilkan syntax error saat kompilasi.
   * C. JavaScript akan mengabaikan objek `newContext` dan tetap menggunakan lexical context awal.
   * D. Runtime akan memicu error `TypeError: Cannot rebind arrow function`.

---

### Soal Intermediate (6 - 10)

6. **Mengapa urutan overload signature di bawah ini memicu bug inferensi tipe pada call-site?**
   ```typescript
   function render(value: unknown): string;
   function render(value: Date): string;
   function render(value: unknown): string {
     return String(value);
   }
   ```
   * A. Karena `unknown` tidak kompatibel dengan `Date`.
   * B. Karena overload `unknown` lebih luas dan berada di atas, sehingga signature `Date` di bawahnya ter-masking (tidak pernah dipilih).
   * C. Karena fungsi tidak memiliki return type union pada implementation signature.
   * D. Karena tipe `Date` memerlukan construct signature `new Date()`.

7. **Diberikan relasi subtipe `AdminUser extends BaseUser`. Di bawah aturan fungsi contravariant, penugasan fungsi manakah yang valid secara type-safety?**
   * A. `let handler: (u: AdminUser) => void = (u: BaseUser) => {};`
   * B. `let handler: (u: BaseUser) => void = (u: AdminUser) => {};`
   * C. `let handler: (u: BaseUser) => BaseUser = (u: AdminUser) => new AdminUser();`
   * D. Tidak ada yang valid karena parameter fungsi selalu bersifat invariant.

8. **Manakah dari signature berikut yang mendefinisikan sebuah tipe fungsi yang DAPAT dipanggil langsung dan DAPAT diinstansiasi menggunakan kata kunci `new`?**
   * A. `type Callable = { (): void; new (): void; };`
   * B. `type Callable = () => void & new () => void;`
   * C. `type Callable = { construct: () => void; invoke: () => void; };`
   * D. `type Callable = Function;`

9. **Apa konsekuensi dari penggunaan arrow function untuk method di dalam body class TypeScript?**
   * A. Parameter method tidak dapat lagi memiliki generic types.
   * B. Method tidak ditambahkan ke prototype class, melainkan dibuat sebagai instance property baru pada setiap objek yang dibuat, meningkatkan konsumsi memori.
   * C. Keyword `super` tidak lagi dapat digunakan di method manapun di dalam class tersebut.
   * D. Tidak dapat dikompilasi ke target target JavaScript di bawah ESNext.

10. **Diberikan kode berikut:**
    ```typescript
    interface CacheStore {
      clean(this: CacheStore): void;
    }
    const store: CacheStore = { clean() {} };
    const cleaner = store.clean;
    cleaner();
    ```
    **Bila flag `--strict` aktif, apa yang akan dilaporkan oleh kompilator pada baris `cleaner()`?**
    * A. TS2304: Cannot find name 'cleaner'.
    * B. TS2684: The 'this' context of type 'void' is not assignable to method's 'this' of type 'CacheStore'.
    * C. Kompilasi sukses tanpa error, namun melempar `TypeError` di runtime.
    * D. TS2554: Expected 1 arguments, but got 0.

---

### Kunci Jawaban Kuis

1. **B** — Parameter `this: void` secara eksplisit memberi tahu type-checker bahwa fungsi tidak boleh diasosiasikan atau mengakses pointer `this`.
2. **C** — Hanya 2 overload signatures teratas yang dihitung sebagai signature publik; implementation signature terakhir diabaikan dari daftar overload pemanggil.
3. **D** — Parameter semu `this` sepenuhnya dihapus (*erased*) saat kompilasi, tidak meninggalkan jejak overhead di JS target.
4. **B** — Penulisan function property syntax `prop: () => void` menerapkan contravariance ketat di bawah `--strictFunctionTypes`.
5. **C** — Sesuai spesifikasi ECMAScript standar, arrow functions mengikat `this` secara statis dari enclosing lexical context; `.call()`, `.bind()`, dan `.apply()` tidak mengubah konteksnya.
6. **B** — TypeScript mengevaluasi overload dari atas ke bawah. Signature pertama yang lolos pencocokan tipe akan dipilih. `unknown` cocok dengan tipe apa pun, sehingga menutupi signature di bawahnya.
7. **A** — Parameter fungsi bersifat contravariant. Fungsi penerima `BaseUser` aman menggantikan fungsi yang meminta `AdminUser`, karena `BaseUser` memiliki batas dependensi yang lebih luas dan aman.
8. **A** — Object type dengan bare call signature `(): void` dan construct signature `new (): void` merepresentasikan fungsi hybrid.
9. **B** — Arrow function pada field class diinisialisasi pada constructor per instansiasi, tidak masuk ke prototype chain class.
10. **B** — TypeScript mendeteksi bahwa fungsi `cleaner` diekstrak dari objek induknya dan dipanggil tanpa execution context yang valid.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Rancang "Type-Safe Task Dispatcher Engine"

Buatlah sebuah modul TypeScript enterprise mandiri bernama `TaskDispatcherEngine` dengan kriteria berikut:

#### Kebutuhan Fungsional:
1. **Context Isolation:** Buat antarmuka `ExecutionContext` yang memuat properti `taskId: string`, `traceId: string`, dan `timestamp: number`.
2. **Explicit Task Handlers:** Setiap task handler harus mewajibkan argumen context via pseudo-parameter `this: ExecutionContext`. Handlers tidak boleh dipanggil tanpa context ini.
3. **Function Overloading:** Rancang method overload `dispatch()` pada kelas utama:
   * Signature 1: Menerima nama tugas string tunggal (`taskName: string`) dan langsung mengembalikan Promise bernilai boolean sukses.
   * Signature 2: Menerima nama tugas string dan metadata custom (`taskName: string, metadata: Record<string, unknown>`), mengembalikan Promise berisi ID eksekusi string.
   * Signature 3: Menerima konfigurasi batch array of tasks, mengembalikan Promise berisi array of result status.
4. **Enforce Type Safety:** Tambahkan compiler check agar `this` tidak bocor ketika method didelegasikan. Pastikan file dikompilasi dengan konfigurasi:
   ```json
   {
     "compilerOptions": {
       "strict": true,
       "noImplicitThis": true,
       "strictFunctionTypes": true
     }
   }
   ```

#### Standar Pengujian Mandiri:
* Uji coba ekstraksi method `const dispatch = engine.dispatch;` dan verifikasi bahwa kompilator menggagalkan pemanggilan `dispatch("backup")` tanpa context binding yang sesuai.
* Jalankan eksekusi pemanggilan overload untuk ketiga signature dan pastikan hasil inferensi kembalian (*return type*) tepat dan tidak berstatus `any` atau `unknown`.