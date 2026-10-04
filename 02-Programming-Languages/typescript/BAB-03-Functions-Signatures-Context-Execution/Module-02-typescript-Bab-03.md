# BAB 03: Functions, Signatures, Context, and Execution
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis dan Memetakan** mekanisme internal V8 *Call Stack*, *Lexical Environment*, *Variable Environment*, dan *Environment Records* serta korelasinya terhadap resolusi tipe TypeScript pada waktu kompilasi (*compile-time*).
2. **Menguasai dan Mengimplementasikan** manipulasi tanda tangan tingkat lanjut (*advanced function signatures*), termasuk *variadic tuple types*, *overload resolution algorithms*, dan *contextual typing inversion*.
3. **Merancang dan Mengembangkan** arsitektur fungsional terdistribusi menggunakan *Higher-Order Functions* (HOF), *Pipeline/Composition pattern*, dan konteks asinkronus (`AsyncLocalStorage`) dengan keamanan tipe absolut (*soundness & zero unhandled dynamic context*).
4. **Mendeteksi dan Memitigasi** masalah kinerja runtime V8 (seperti de-optimasi akibat perubahan *hidden class* pada konteks dinamis, *closure memory leaks*, dan overhead alokasi memori) serta batasan kompilator TypeScript (*compiler recursion depth limits*).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
*   Struktur tipe dasar TypeScript: Union, Intersection, Mapped Types, dan Conditional Types (`T extends U ? X : Y`).
*   Konfigurasi compiler tingkat lanjut pada `tsconfig.json`: `strict: true`, `noImplicitThis: true`, `strictFunctionTypes: true`.
*   Dasar eksekusi JavaScript: Event Loop, Macro/Microtask Queues, dan Prototype Chain.
*   Manipulasi *Utility Types* bawaan: `Parameters<T>`, `ReturnType<T>`, `ThisParameterType<T>`, dan `OmitThisParameter<T>`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Arsitektur Runtime: ECMAScript Execution Context & V8 Internals

Secara spesifikasi ECMAScript (ECMA-262), sebuah fungsi dieksekusi di dalam sebuah **Execution Context (EC)**. Pada level runtime V8:

```
+-------------------------------------------------------+
|                   Execution Context                   |
+-------------------------------------------------------+
| 1. LexicalEnvironment                                 |
|    +--> Environment Record (Declarative/Object)       |
|    +--> Outer Environment Reference (Scope Chain)     |
+-------------------------------------------------------+
| 2. VariableEnvironment                                |
|    +--> Environment Record (var declarations)         |
+-------------------------------------------------------+
| 3. ThisBinding (Value determined at call-site)        |
+-------------------------------------------------------+
```

1. **Environment Records**:
   * **Declarative Environment Record**: Menyimpan binding variabel lexical (`let`, `const`, fungsi, modul). Dalam V8, jika variabel diakses oleh closure, variabel tersebut dialokasikan pada *Heap Context* (bukan pada CPU stack frame).
   * **Object Environment Record**: Mengikat binding ke global object (`window` atau `globalThis`).
2. **Context Closure & Escape Analysis**:
   * V8 melakukan analisis lolos (*Escape Analysis*). Jika sebuah fungsi internal mengakses identifier dari outer scope dan fungsi tersebut di-return (atau dioper ke fungsi lain), V8 mengalokasikan slot memori pada *Context Object* di Heap. Kegagalan memahami ini berpotensi memicu *Hidden Memory Leak* jika scope luar membawa referensi payload berukuran besar.
3. **Resolusi Dynamic `this`**:
   * Evaluasi ekspresi pemanggilan `foo.bar()` menghasilkan tipe internal *Reference Record* yang membawa basis objek (`base value = foo`). Ketika tanda kurung `()` dievaluasi, `this` diikat ke nilai basis tersebut. Jika referensi dilepaskan (`const baz = foo.bar; baz()`), basisnya menjadi `undefined` (pada mode *strict*) atau `globalThis`.

#### B. Arsitektur Compiler: Type-Checking Algorithm pada Fungsi

Komparasi tipe pada fungsi adalah salah satu aspek paling rumit dalam TypeScript Compiler (`tsc`):

1. **Parameter Bivariance vs Contravariance**:
   * Secara matematis, subtyping fungsi mensyaratkan:
     $$\text{Jika } T_{sub} \subseteq T_{super}, \text{ maka } (T_{super} \to R) \subseteq (T_{sub} \to R)$$
   * Parameter fungsi bersifat **kontravarian** (*contravariant*), sedangkan nilai return bersifat **kovarian** (*covariant*).
   * Bendera `strictFunctionTypes: true` memaksa fungsi diperiksa secara kontravarian murni (kecuali untuk *method syntax* pada interface yang dipertahankan bivariant demi kompatibilitas hierarki DOM/Array).

```
Hierarki Tipe: Animal <- Dog

Parameter Kontravarian:
(arg: Animal) => void  <--- DAPAT DITUGASKAN KE --- (arg: Dog) => void  (SALAH/UNSAFE)
(arg: Dog) => void     <--- DAPAT DITUGASKAN KE --- (arg: Animal) => void (BENAR/SAFE)

Return Value Kovarian:
() => Dog             <--- DAPAT DITUGASKAN KE --- () => Animal          (BENAR/SAFE)
```

2. **Bidirectional Contextual Typing**:
   * Kompilator memeriksa ekspresi fungsi menggunakan dua arah: *top-down* (contextual type mengalir dari ekspektasi variabel penerima ke parameter fungsi anak) dan *bottom-up* (tipe return fungsi anak menyimpulkan tipe keseluruhan).
3. **Overload Resolution Algorithm**:
   * TypeScript mengevaluasi tanda tangan overload dari atas ke bawah (*top-to-bottom*). Pencocokan pertama yang kompatibel dengan argumen pada call-site akan langsung dipilih, meskipun ada overload di baris berikutnya yang secara semantik lebih spesifik. Ini adalah sumber utama *subtle type bugs*.

---

### 4. Why & What

| Dimensi | Pendekatan Naif / Tradisional | Pendekatan Enterprise TypeScript Modern |
| :--- | :--- | :--- |
| **Penanganan Konteks (`this`)** | Mengandalkan binding runtime implisit (`bind`, `that = this`, atau arrow function tanpa validasi). Rawan runtime error `Cannot read properties of undefined`. | Menggunakan *Explicit `this` Parameters* (`this: void` atau `this: ServiceContext`) yang divalidasi ketat saat kompilasi. |
| **Pipeline & Komposisi** | Menggunakan wrapper bertingkat atau lodash `flow`/`compose` dengan tipe `any` atau batas argumen statis (hanya mendukung hingga 5-10 fungsi). | Menggunakan **Variadic Tuple Types** dan **Recursive Conditional Inferences** yang mendukung deret fungsi panjang berantai tak hingga secara type-safe. |
| **Dynamic Interceptors** | Middleware berbasis monkey-patching atau modifikasi properti request secara dinamis (mis. `req.user = user` tipe `any`). | Menggunakan **Context Accumulator Pattern** via Generic HOF atau `AsyncLocalStorage` dengan interface immutable yang terisolasi secara tipe. |
| **Overload Management** | Mendefinisikan belasan overload manual untuk setiap kemungkinan kombinasi parameter. | Menggantikan overload berulang dengan **Conditional Return Types** berbasis tuple atau discriminative generic arguments. |

---

### 5. How (Workflow Detail)

Untuk mengimplementasikan arsitektur fungsi enterprise berskala besar (misalnya: Transaction Engine Middleware):

```
[Inisiasi Call-Site: client.execute(payload)]
                    │
                    ▼
[TypeScript Checker: Resolusi Type Signature]
  ├── Evaluasi Contextual Type Parameter
  ├── Pencocokan Overload / Conditional Inference
  └── Pengecekan Type Invariance & Contravariance
                    │
                    ▼
[Runtime V8: Alokasi Execution Context]
  ├── Pembuatan Declarative Environment Record (Context Heap/Stack)
  ├── Binding 'this' (Strict Mode: null/undefined guard)
  └── Integrasi AsyncLocalStorage (Tracing Context Propagation)
                    │
                    ▼
[Eksekusi Pipeline / Interceptor Chain]
  ├── Pre-hook: Validasi Schema & Inject Dynamic Dependency
  ├── Core Execution: Pemanggilan Unit Bisnis
  └── Post-hook / Error: Cleanup Lexical References (Cegah Leak)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Rel Transmisi Kereta Cepat (Execution Context & Scope Chain)
Bayangkan eksekusi fungsi sebagai lintasan kereta api modern:
* **Call Stack** adalah rel utama vertikal tempat rangkaian gerbong (Execution Contexts) ditumpuk dan dipindahkan.
* **Lexical Scope Chain** adalah jalur kabel catenary listrik di atasnya. Saat gerbong membutuhkan daya (variabel), ia menariknya dari kabel di atas kepalanya. Jika kabel lokal kosong, ia menarik ke kabel jalur induk (Outer Environment), sampai ke stasiun transmisi pusat (Global Scope).
* **`this` Binding** adalah identitas masinis kereta. Identitas ini tidak ditentukan oleh di mana rel itu dipabrikasi (definisi fungsi), melainkan stasiun mana yang mendelegasikan perintah pemberangkatan kereta hari itu (call-site invocation).

```
                      CALL STACK & LEXICAL SCOPE RESOLUTION
                      
Top of Stack:
+-----------------------------------------------------------------+
| Execution Context: processTransaction()                         |
|   - VariableEnvironment: { txId: "TX-99" }                      |
|   - LexicalEnvironment:  [Local Scope]                          |
|         │                                                       |
|         └── Outer Ref ────────────────────────┐                 |
|   - ThisBinding: <AccountService>             │                 |
+-----------------------------------------------│-----------------+
                                                ▼
+-----------------------------------------------------------------+
| Execution Context: executeMiddlewareChain()                     |
|   - VariableEnvironment: { authHeader: "Bearer..." }            |
|   - LexicalEnvironment:  [Parent Closure Scope]                 |
|         │                                                       |
|         └── Outer Ref ────────────────────────┐                 |
|   - ThisBinding: undefined                    │                 |
+-----------------------------------------------│-----------------+
                                                ▼
+-----------------------------------------------------------------+
| Execution Context: Global Execution Context                     |
|   - LexicalEnvironment:  [Global Record: Config, Singletons]    |
|   - ThisBinding: globalThis                                     |
+-----------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Type-Safe Function Composition (Variadic Tuples)
Membuat fungsi `compose` generik tanpa kehilangan informasi tipe dari hulu ke hilir.

```typescript
// Abstraksi fungsi unary (satu parameter)
type UnaryFn<TIn, TOut> = (arg: TIn) => TOut;

// Type-level compose menggunakan variadic tuple & rekursi
type ComposeChain<Fns extends UnaryFn<any, any>[]> = 
  Fns extends [UnaryFn<infer In, any>, ...infer Rest extends UnaryFn<any, any>[]]
    ? Rest extends []
      ? Fns[0]
      : (arg: In) => ReturnType<Rest[1] extends UnaryFn<any, any> ? ComposeChain<Rest> : Rest[0]>
    : never;

// Implementasi tipe-aman untuk pipeline 3-tahap
function pipeline<A, B, C, D>(
  fn1: (a: A) => B,
  fn2: (b: B) => C,
  fn3: (c: C) => D
): (initial: A) => D {
  return (initial: A): D => fn3(fn2(fn1(initial)));
}

// Penggunaan
const parseToInt = (s: string): number => parseInt(s, 10);
const doubleInt = (n: number): number => n * 2;
const formatCurrency = (n: number): string => `IDR ${n.toLocaleString('id-ID')}`;

const processBilling = pipeline(parseToInt, doubleInt, formatCurrency);
const result = processBilling("50000"); // Output: "IDR 100.000"
```

#### Practical Example: Production-Ready Middleware Interceptor dengan Context Isolation

```typescript
import { AsyncLocalStorage } from 'node:async_hooks';

// 1. Tipe Konteks Transaksi
interface TransactionContext {
  readonly traceId: string;
  readonly userId: string;
  readonly isolationLevel: 'READ_COMMITTED' | 'SERIALIZABLE';
}

// 2. Storage Asinkronus Terisolasi
const asyncContext = new AsyncLocalStorage<TransactionContext>();

// 3. Tipe Handler Inti
export type Handler<TInput, TOutput> = (input: TInput) => Promise<TOutput>;

// 4. Tipe Middleware yang mengubah atau memvalidasi aliran eksekusi
export type Middleware<TInBefore, TOutBefore, TInAfter = TInBefore, TOutAfter = TOutBefore> = (
  next: Handler<TInAfter, TOutAfter>
) => Handler<TInBefore, TOutBefore>;

// 5. Explicit Context Enforcement (This Guard)
export class OrderService {
  private taxRate: number = 0.11;

  public async calculateTotal(
    this: OrderService, // Explicit this: Mencegah 'this' stripping saat dioper sebagai callback
    basePrice: number
  ): Promise<number> {
    const ctx = asyncContext.getStore();
    if (!ctx) {
      throw new Error("IllegalInvocationError: Execution context is missing.");
    }
    
    // Logika dengan traceId dari konteks
    return basePrice + (basePrice * this.taxRate);
  }
}

// 6. High-Order Middleware Pipeline Builder
export function applyMiddlewares<TIn, TOut>(
  coreHandler: Handler<TIn, TOut>,
  ...middlewares: Middleware<any, any>[]
): Handler<TIn, TOut> {
  return middlewares.reduceRight<Handler<any, any>>(
    (accumulatedHandler, currentMiddleware) => currentMiddleware(accumulatedHandler),
    coreHandler
  );
}

// 7. Implementasi Middleware Telemetri & Auth
const telemetryMiddleware: Middleware<number, number> = (next) => async (input) => {
  const ctx = asyncContext.getStore();
  const start = performance.now();
  try {
    return await next(input);
  } finally {
    const duration = performance.now() - start;
    console.log(`[TraceID: ${ctx?.traceId}] Duration: ${duration.toFixed(3)}ms`);
  }
};

// 8. Eksekusi Runner Type-Safe
async function runWithContext<T>(
  ctx: TransactionContext,
  fn: () => Promise<T>
): Promise<T> {
  return asyncContext.run(ctx, fn);
}

// Orchestrator Execution:
async function bootstrap() {
  const service = new OrderService();
  
  // Binding yang divalidasi kompilator secara ketat
  const unboundHandler = service.calculateTotal;
  // @ts-expect-error: TS2684 - The 'this' context of type 'void' is not assignable to method's 'this' of type 'OrderService'.
  // await unboundHandler(1000); 

  const boundHandler = service.calculateTotal.bind(service);
  const securedPipeline = applyMiddlewares(boundHandler, telemetryMiddleware);

  const mockContext: TransactionContext = {
    traceId: "req-trace-abc-123",
    userId: "usr-001",
    isolationLevel: "SERIALIZABLE"
  };

  const total = await runWithContext(mockContext, async () => {
    return await securedPipeline(100000);
  });

  console.log(`Calculated Final Amount: ${total}`);
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Eksekusi Pembayaran FinTech dengan Dynamic Strategy & Rollback

Pada platform core banking berskala jutaan TPS (*Transactions Per Second*), eksekusi pembayaran membutuhkan *dynamic strategy dispatch*, kompensasi rollback otomatis (Saga Pattern), dan *context retention* untuk audit trail tanpa terjadi context loss pada async-await boundary.

```typescript
import { AsyncLocalStorage } from 'node:async_hooks';

// Type System: Strict Nominal Types
type PaymentMethodId = 'VA' | 'CC' | 'EWALLET';

interface AuditTrail {
  callerIp: string;
  correlationId: string;
  timestamp: number;
}

interface PaymentPayload {
  amount: bigint;
  sourceAccount: string;
  destinationAccount: string;
}

interface ExecutionResult {
  transactionReference: string;
  settledAt: Date;
}

// Dynamic Strategy Context
const auditStorage = new AsyncLocalStorage<AuditTrail>();

// Step 1: Definition of Method-Signature Contracts via Overloads & Conditional Maps
type StepAction<TInput, TOutput> = {
  execute: (input: TInput) => Promise<TOutput>;
  compensate: (input: TInput, error: Error) => Promise<void>;
};

// Strategy Registry
class PaymentEngineRegistry {
  private strategies = new Map<PaymentMethodId, StepAction<PaymentPayload, ExecutionResult>>();

  public register<K extends PaymentMethodId>(
    method: K,
    action: StepAction<PaymentPayload, ExecutionResult>
  ): void {
    this.strategies.set(method, action);
  }

  public resolve(method: PaymentMethodId): StepAction<PaymentPayload, ExecutionResult> {
    const strategy = this.strategies.get(method);
    if (!strategy) {
      throw new Error(`StrategyNotFoundException: No strategy for method ${method}`);
    }
    return strategy;
  }
}

// Step 2: Resilient Execution Harness dengan Context Invariance
export class CorePaymentOrchestrator {
  constructor(private readonly registry: PaymentEngineRegistry) {}

  public async executeTransaction(
    this: CorePaymentOrchestrator,
    method: PaymentMethodId,
    payload: PaymentPayload
  ): Promise<ExecutionResult> {
    const currentAudit = auditStorage.getStore();
    if (!currentAudit) {
      throw new Error("AuditContextViolation: Process must run inside an established audit trail.");
    }

    const strategy = this.registry.resolve(method);

    try {
      // Menjalankan bisnis logic
      return await strategy.execute(payload);
    } catch (err: unknown) {
      const error = err instanceof Error ? err : new Error(String(err));
      // Menjalankan rollback otomatis
      await strategy.compensate(payload, error);
      throw error;
    }
  }
}

// Step 3: Implementasi Konkret
const registry = new PaymentEngineRegistry();

registry.register('CC', {
  execute: async (payload) => {
    // Simulasi integrasi payment gateway
    if (payload.amount > 100_000_000n) {
      throw new Error("CreditLimitExceeded: Amount exceeds maximum single transaction limit.");
    }
    return {
      transactionReference: `REF-CC-${Date.now()}`,
      settledAt: new Date()
    };
  },
  compensate: async (payload, error) => {
    // Logika reversal
    console.error(`Rollback invoked for CC payment: ${payload.sourceAccount}, Reason: ${error.message}`);
  }
});

// Step 4: Simulasi Runner Produksi
export async function productionRunner() {
  const orchestrator = new CorePaymentOrchestrator(registry);

  const secureContext: AuditTrail = {
    callerIp: "10.200.1.45",
    correlationId: "c8e2b83b-e102-4fc4-8e1f-4efc1e138a0f",
    timestamp: Date.now()
  };

  await auditStorage.run(secureContext, async () => {
    const result = await orchestrator.executeTransaction('CC', {
      amount: 50_000n,
      sourceAccount: "ACC-SRC-001",
      destinationAccount: "ACC-DST-999"
    });
    console.log("Transaction successfully settled:", result.transactionReference);
  });
}
```

---

### 9. Trade-offs

| Parameter Desain | Opsi A: Arrow Function Property (`class { fn = () => {} }`) | Opsi B: Method Prototype (`class { fn() {} }`) | Opsi C: Free Functions + Context Injection |
| :--- | :--- | :--- | :--- |
| **Kinerja Memori (V8)** | **Buruk**: Arrow function membuat instance fungsi baru untuk setiap instansiasi objek di heap. | **Sangat Baik**: Fungsi didefinisikan satu kali pada Prototype object induk. | **Maksimal**: Statis, dapat dilakukan *inline caching* murni oleh V8 Turbofan compiler. |
| **Perilaku Konteks `this`** | Terikat secara leksikal ke instance. Tidak bisa di-rebind atau dimanipulasi dengan `bind/call`. | Bergantung pada pemanggil (*dynamic*). Butuh `this: ClassName` pada parameter pertama untuk keamanan TS. | Bersih: `this` dihindari sepenuhnya; status dioper eksplisit lewat parameter pertama. |
| **Beban Analisis Kompilator (`tsc`)** | Sangat Rendah. Tipe terselesaikan secara trivial. | Rendah. Membutuhkan verifikasi kontravarian saat assignment inheritance. | Tinggi: Jika menggunakan recursive type inference atau generic curry yang dalam. |
| **Dukungan Dynamic Decorator** | Tidak dapat di-decorate via prototype patching secara efisien. | Sangat kompatibel dengan Decorator Metadata (TC39 Stage 3 / TS Experimental). | Tidak berlaku. Dilakukan menggunakan HOF wrapping secara langsung. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Kehilangan Konteks `this` Akibat Destructuring Method
```typescript
class CacheClient {
  private ttl: number = 3600;
  
  public getTtl(this: void): number { // Solusi: Deklarasikan this: void jika method tidak boleh pakai this
    return this.ttl; // Kompilator melempar error: Property 'ttl' does not exist on type 'void'
  }
  
  public getTtlValid(this: CacheClient): number {
    return this.ttl;
  }
}

const client = new CacheClient();
const { getTtlValid } = client;
// getTtlValid(); 
// TS ERROR: The 'this' context of type 'void' is not assignable to method's 'this' of type 'CacheClient'.
```

#### Kesalahan 2: Overload Signature Shadowing
Penyusunan tanda tangan overload dari tipe yang lebih umum (*broad*) ke tipe yang lebih spesifik (*narrow*), sehingga tanda tangan spesifik tidak pernah terjangkau (*unreachable*).

```typescript
// SALAH:
function serialize(value: object): string;
function serialize(value: Date): number; // UNREACHABLE: Date adalah subclass dari object!
function serialize(value: any): any { return value; }

// BENAR: Urutkan dari yang paling spesifik ke yang paling umum
function serialize(value: Date): number;
function serialize(value: object): string;
function serialize(value: any): any { return value; }
```

#### Kesalahan 3: Dangling Closures & Context Memory Leak
Menangkap objek besar secara tidak sengaja di dalam scope leksikal closure fungsi jangka panjang.

```typescript
function setupMetricsCollector() {
  const hugeDataSet = new Array(1_000_000).fill("payload data");
  
  // Callback ini disimpan di event emitter global
  setInterval(function emitHeartbeat() {
    // Meskipun hugeDataSet tidak ditulis di sini, jika ada eval atau closure lain
    // di dalam scope yang sama berinteraksi dengan hugeDataSet, V8 Context Object
    // menahan hugeDataSet di memori heap tanpa ter-garbage collect.
    console.log("Heartbeat alive.");
  }, 1000);
}
```
*Solusi*: Buat closure boundary terisolasi, atau secara eksplisit set identifier ke `null` setelah pemrosesan awal selesai.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Enforce `noImplicitThis: true`**: Pastikan tidak ada `this` dinamis yang lepas dari pengawasan tipe kompilator.
2. [ ] **Explicit Parameter `this: void`**: Tandai fungsi utility murni (*pure standalone functions*) dengan `this: void` untuk mencegah penyalahgunaan `.call()` atau `.apply()`.
3. [ ] **Avoid Generic Instantiation Depth Limit**: Batasi kedalaman rekursi tipe pada komposisi fungsional hingga maksimal $\le 10$ lapis untuk mencegah compiler crash: `TS2589: Type instantiation is excessively deep and possibly infinite.`
4. [ ] **Kontravarian pada Event Emitter Handlers**: Selalu pastikan callback signature didefinisikan via method signature atau argumen kontravarian murni untuk mencegah runtime casting failure.
5. [ ] **Gunakan `AsyncLocalStorage` untuk Context Asinkronus**: Hindari passing metadata (seperti User ID, Auth Token, Span ID) ke setiap layer fungsional secara manual (*parameter drilling*); isolasikan menggunakan context propagation API Node.js/V8.
6. [ ] **Hindari Penggunaan Tipe `Function`**: Tipe bawaan `Function` menerima semua pemanggilan fungsi dan mengembalikan `any`. Gunakan `(...args: unknown[]) => unknown` untuk keamanan tipe minimum.

---

### 12. Hands-on Practice

Buatlah implementasi pipeline middleware dengan type inference dinamis secara mandiri pada direktori `hands-on/m02/`.

#### Langkah 1: Inisialisasi Environment
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install typescript @types/node tsx --save-dev
npx tsc --init --strict true --noImplicitThis true
```

#### Langkah 2: Buat Pipeline Orchestrator (`hands-on/m02/pipeline.ts`)
Tuliskan kode berikut untuk membuat komposisi pipe bertipe kuat:

```typescript
export type Transform<Input, Output> = (data: Input) => Promise<Output> | Output;

export class StrictPipeline<CurrentInput, CurrentOutput> {
  private constructor(
    private readonly operation: Transform<CurrentInput, CurrentOutput>
  ) {}

  public static create<TInitial>(): StrictPipeline<TInitial, TInitial> {
    return new StrictPipeline<TInitial, TInitial>((data: TInitial) => data);
  }

  public pipe<NextOutput>(
    transformer: Transform<CurrentOutput, NextOutput>
  ): StrictPipeline<CurrentInput, NextOutput> {
    return new StrictPipeline<CurrentInput, NextOutput>(async (initial: CurrentInput) => {
      const intermediate = await this.operation(initial);
      return transformer(intermediate);
    });
  }

  public async execute(input: CurrentInput): Promise<CurrentOutput> {
    return this.operation(input);
  }
}
```

#### Langkah 3: Eksekusi dan Verifikasi (`hands-on/m02/index.ts`)
```typescript
import { StrictPipeline } from './pipeline.js';

interface RawPayload {
  raw: string;
}

interface SanitizedPayload {
  clean: string;
}

interface ParsedNumber {
  value: number;
}

async function main() {
  const processor = StrictPipeline.create<RawPayload>()
    .pipe<SanitizedPayload>((input) => {
      return { clean: input.raw.trim().replace(/[^\d.-]/g, '') };
    })
    .pipe<ParsedNumber>((input) => {
      const val = parseFloat(input.clean);
      if (isNaN(val)) throw new Error("Validation failed: Not a Number");
      return { value: val };
    })
    .pipe<string>((input) => {
      return `Final Processed Currency: $${input.value.toFixed(2)}`;
    });

  const result = await processor.execute({ raw: "   $ 1,250.50 USD   " });
  console.log("Hasil Eksekusi:", result);
}

main().catch(console.error);
```
Jalankan menggunakan:
```bash
npx tsx hands-on/m02/index.ts
```

---

### 13. Exercise

#### Level: Easy
Diberikan sebuah objek konfigurasi dengan method yang kehilangan konteks. Perbaiki tanda tangan method `DatabaseConnector` berikut menggunakan explicit `this` parameter sehingga TypeScript mencegah pemanggilan fungsi yang tidak diikat (`unbound`).

```typescript
// Implementasikan perbaikan tipe pada interface ini:
export interface IDatabaseConnector {
  host: string;
  connect(this: IDatabaseConnector): void;
}

export const db: IDatabaseConnector = {
  host: "cluster-primary.rds.internal",
  connect() {
    console.log(`Connecting to: ${this.host}`);
  }
};
```

#### Level: Medium
Implementasikan fungsi generic `curry2` yang menerima fungsi biner `(a: A, b: B) => R` dan mengubahnya menjadi bentuk unary bertingkat `(a: A) => (b: B) => R` dengan retensi tipe parameter 100% presisi.

```typescript
export function curry2<A, B, R>(fn: (a: A, b: B) => R): (a: A) => (b: B) => R {
  return (a: A) => (b: B): R => fn(a, b);
}

// Uji coba:
const add = (x: number, y: number): number => x + y;
const curriedAdd = curry2(add);
const addFive = curriedAdd(5);
const result: number = addFive(10); // Harus bernilai 15
```

#### Level: Hard
Buat type utility `PromisifyMethods<T>` yang mengekstrak semua method pada objek `T`, mengubah return value-nya menjadi `Promise<R>` jika belum berupa Promise, serta mempertahankan parameter dan konteks pemanggilan aslinya.

```typescript
type PromisifyMethods<T> = {
  [K in keyof T]: T[K] extends (this: infer This, ...args: infer Args) => infer Ret
    ? (this: This, ...args: Args) => Ret extends Promise<any> ? Ret : Promise<Ret>
    : T[K];
};

// Target Validasi:
interface SyncWorker {
  name: string;
  calculate(rate: number): number;
  syncData(): void;
}

type AsyncWorker = PromisifyMethods<SyncWorker>;
// Expected:
// name: string;
// calculate: (rate: number) => Promise<number>;
// syncData: () => Promise<void>;
```

---

### 14. Challenge

**Studi Kasus**: Rancanglah sebuah **Type-Safe Dispatcher Actor Model System** tanpa menggunakan decorator runtime.

**Ketentuan Arsitektur**:
1. Actor memiliki kumpulan pesan (*message dictionary*), di mana setiap pesan memiliki nama dan payload tertentu.
2. Method pemrosesan pesan harus didefinisikan dalam sebuah handler class yang mengeksekusi pesan sesuai namanya.
3. Fungsi dispatcher `send(messageName, payload)` harus menginfer tipe payload secara presisi berdasarkan parameter pertama `messageName`.
4. Jika payload tidak membutuhkan argumen (tipe `void`), parameter kedua pada `send` harus bersifat opsional atau tidak boleh diisi sama sekali (gunakan *Conditional Tuple Arguments*).
5. Buat penanganan kegagalan di mana jika sebuah handler runtime tidak mengembalikan hasil dalam interval toleransi $X$ milidetik (*timeout*), context dibatalkan dan melempar *TimeoutError* dengan tipe kembalian yang tetap terjaga integritasnya.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (5 Soal)
1. **Apa fungsi utama dari parameter pertama yang diberi nama khusus `this` pada deklarasi fungsi TypeScript?**
   * *Jawaban:* Parameter virtual yang dipahami compiler untuk menentukan tipe konteks objek saat fungsi dipanggil. Parameter ini akan dihapus secara total saat dikompilasi ke JavaScript runtime (*zero runtime overhead*).
2. **Kapan parameter fungsi dianggap bersikap contravariant pada TypeScript?**
   * *Jawaban:* Ketika bendera `strictFunctionTypes: true` diaktifkan di `tsconfig.json`. Subtype dapat diterima jika fungsi penerima menerima tipe argumen yang sama atau lebih luas (supertype) dari parameter target.
3. **Mengapa `(...args: any[]) => any` lebih dianjurkan daripada tipe `Function` bawaan saat mengetik fungsi tingkat lanjut?**
   * *Jawaban:* Karena tipe `Function` merepresentasikan semua callable object namun menonaktifkan type-safety pemanggilan, sementara `(...args: any[]) => any` mempertahankan struktur pemanggilan fungsi dan dapat di-destrukturisasi via `Parameters<T>` dan `ReturnType<T>`.
4. **Apa yang terjadi pada Call Stack V8 saat rekursi fungsi eksekusi melebihi ambang batas maksimum?**
   * *Jawaban:* V8 melempar exception `RangeError: Maximum call stack size exceeded` akibat stack frame meluap melampaui alokasi memori stack thread (umumnya 1MB - 1.5MB).
5. **Bagaimana TypeScript menentukan overload mana yang cocok jika argumen call-site memenuhi lebih dari satu tanda tangan overload?**
   * *Jawaban:* TypeScript memilih tanda tangan overload kompatibel pertama yang ia temui dari atas ke bawah (*first matching overload declaration*).

#### B. Pertanyaan Intermediate (5 Soal)
6. **Jelaskan perbedaan mendasar antara *Declarative Environment Record* dan *Object Environment Record* di level ECMAScript engine!**
   * *Jawaban:* Declarative Environment Record mengikat identifier lexical (`let`, `const`, `function`) langsung ke representasi memori internal V8 (sering kali dialokasikan di context array/heap jika ada closure). Object Environment Record mengikat identifier ke properti dari sebuah runtime object nyata (seperti `window` atau `globalThis`), yang memiliki kinerja akses lebih lambat akibat pencarian prototype.
7. **Mengapa arrow function tidak dapat digunakan sebagai constructor (`new ArrowFn()`)?**
   * *Jawaban:* Arrow function secara spesifikasi tidak memiliki internal method `[[Construct]]` dan tidak memiliki properti `.prototype`. Pemanggilan `new` akan langsung melempar runtime `TypeError`.
8. **Bagaimana cara mencegah kehilangan konteks tipe `this` saat me-pass sebuah method class sebagai parameter callback ke event bus?**
   * *Jawaban:* Dapat dilakukan dengan 3 pendekatan: Menggunakan Arrow function wrapper `(arg) => instance.method(arg)`, melakukan pemanggilan manual `.bind(instance)`, atau mendefinisikan method sejak awal menggunakan class property arrow syntax (`public method = () => {}`).
9. **Apa batasan dari type utility `Parameters<T>` jika diaplikasikan pada fungsi yang memiliki implementasi overload berganda?**
   * *Jawaban:* `Parameters<T>` hanya akan mengambil tanda tangan overload **terakhir** dari deret deklarasi yang ada, bukan union dari seluruh parameter overload.
10. **Jelaskan risiko alokasi memori pada penggunaan closure fungsi yang mengeksekusi long-running tasks!**
    * *Jawaban:* Jika inner function bertahan hidup lebih lama (misal pada event listener atau cache interval) daripada outer function, seluruh lexical scope (termasuk variabel yang tidak digunakan secara langsung oleh inner function tersebut namun berada di scope yang sama) akan ditahan di heap V8 dan tidak dapat dibersihkan oleh Garbage Collector (*stale reference retention*).

#### C. Skenario Kasus Produksi (3 Soal)
11. **Skenario 1 (Latency Spike):**
    * *Masalah:* Sebuah endpoint microservice berbasis Express/TypeScript mengalami *event loop lag* drastis hingga 800ms di bawah beban 5.000 RPS. Profiling CPU V8 menunjukkan penggunaan berlebih pada alokasi anonim di dalam method `Array.map` dan closure handler.
    * *Solusi Arsitektural:* Refactor middleware pipeline. Hapus pembuatan anonymous arrow function di dalam request-response loop. Pindahkan handler murni ke luar scope handler (*module-level declaration*) dengan parameter data yang eksplisit untuk memungkinkan V8 melakukan optimasi inline caching dan alokasi stack tanpa membebani Young Generation GC (Scavenge).
12. **Skenario 2 (TypeScript Compiler Breakdown):**
    * *Masalah:* Pipeline kompilasi CI/CD memunculkan error `TS2589: Type instantiation is excessively deep and possibly infinite` setelah tim engineering mengimplementasikan utility `DeepCompose` untuk merangkai 15 middleware fungsi.
    * *Solusi Arsitektural:* Kompilator kehabisan batas kedalaman evaluasi rekursif tipe (rekursi kondisional). Ganti evaluasi rekursi infinite dengan teknik *Tail Call Optimization* pada type-level (menggunakan accumulator tuple) atau batasi overloads hingga kedalaman tetap yang rasional (misalnya 10 level) menggunakan teknik *Explicit Overload Decomposition*.
13. **Skenario 3 (Async Context Leaks):**
    * *Masalah:* Sebuah gateway multi-tenant mencatat log tenant B menggunakan data transaksi tenant A pada kondisi traffic asinkronus konkuren tinggi. Anda menggunakan dynamic assignment pada objek execution context.
    * *Solusi Arsitektural:* Hentikan manipulasi singleton context atau mutable state pada global scope. Bungkus setiap alur eksekusi request menggunakan `AsyncLocalStorage.run()`. Buat context record bersifat `Readonly<T>` murni untuk mencegah polusi silang (*cross-tenant context pollution*) pada tick microtask loop berikutnya.

---

### 16. Summary

* **Execution Context & Lexical Environment** adalah fondasi runtime V8 yang memisahkan antara status eksekusi leksikal dan pengikatan dinamis (`this`).
* **Parameter `this` Eksplisit** pada TypeScript bukan merupakan runtime argument, melainkan mekanisme kompilator mutlak untuk memvalidasi pemanggilan method secara aman dari risiko *stripping*.
* Penanganan tanda tangan fungsi tingkat lanjut mengandalkan **Variadic Tuples**, **Conditional Types**, dan pengakuan atas hukum **Kontravarian Parameter** vs **Kovarian Return Type**.
* Arsitektur modern berskala enterprise menuntut isolasi konteks eksekusi berbasis **AsyncLocalStorage** dan penghapusan efek samping mutable closure guna mempertahankan determinisme sistem, kebersihan garbage collection, serta performa maksimal pada runtime engine.