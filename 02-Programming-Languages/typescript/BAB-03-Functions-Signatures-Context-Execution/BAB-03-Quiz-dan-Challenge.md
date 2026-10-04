# BAB 03: Quiz, Challenge, & Knowledge Check
**Functions, Signatures, & Context Execution**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Parameter `this` Palsu (Fake `this` Parameter)**  
   Bagaimana mekanisme TypeScript memproses parameter pertama yang secara eksplisit dinamai `this` pada deklarasi fungsi reguler? Jelaskan perbedaan semantiknya saat fase type-checking dibandingkan dengan hasil transpilasinya ke JavaScript murni (ECMAScript emit).

2. **Call Signatures vs. Construct Signatures**  
   Ditinjau dari *type system structural typing*, jelaskan perbedaan mendasar antara definisi tipe objek yang menggunakan *Call Signature* (`(arg: T): R`) dan *Construct Signature* (`new (arg: T): R`). Mengapa interface berikut valid secara sintaksis tetapi tidak dapat diimplementasikan secara langsung oleh satu deklarasi class JavaScript standar tanpa factory function?
   ```typescript
   interface OverloadedCallableConstructor {
     new (version: number): AppInstance;
     (rawConfig: string): AppInstance;
   }
   ```

3. **Mekanisme Function Overload & Signature Erasure**  
   Jelaskan mengapa TypeScript mewajibkan satu *Implementation Signature* yang kompatibel di bawah rangkaian *Overload Signatures*. Mengapa *Implementation Signature* tersebut secara absolut tersembunyi (inaccessible) dari call-site eksternal, dan apa dampaknya jika developer mencoba memanggil fungsi menggunakan tipe signature implementasi secara langsung?

4. **Lexical Scope Arrow Function vs Execution Context Regular Function**  
   Bagaimana sistem tipe TypeScript melacak context execution (`this`) pada *arrow function* di dalam class field versus method biasa? Jelaskan implikasi performa memori (V8 heap) dan konsekuensi polymorphism method lookup ketika menggunakan *arrow function* sebagai class field untuk mempertahankan context binding.

5. **Type Predicates vs. Standard Boolean Return Types**  
   Uraikan perbedaan perlakuan compiler TypeScript antara fungsi bertipe kembalian `boolean` dan `arg is TargetType` (*user-defined type guard*). Apa implikasi control flow analysis (CFA) pada runtime branching (`if/else`) ketika sebuah fungsi pengecekan dipisahkan ke dalam helper function tanpa type predicate?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Variansi Parameter Fungsi: Strict Function Types & Contravariance**  
   Bila flag `--strictFunctionTypes` diaktifkan, TypeScript memperlakukan parameter fungsi secara *contravariant*, namun metode objek/class tetap dievaluasi secara *bivariant*. Mengapa arsitektur desainer TypeScript sengaja mempertahankan inkonsistensi (unsoundness) bivariansi pada level method declaration? Berikan analisis skenario kegagalan tipenya (*type safety breach*).

2. **Debugging Hilangnya Context Execution pada Async Callbacks**  
   Diberikan cuplikan kode backend microservice berikut yang mengalami runtime failure `TypeError: Cannot read properties of undefined (reading 'repository')` saat menangani event stream:
   ```typescript
   class TransactionManager {
     private repository = new DatabaseRepository();

     public async processJob(jobId: string): Promise<void> {
       await this.repository.lock(jobId);
       // ... processing logic
     }
   }

   const manager = new TransactionManager();
   eventQueue.subscribe(manager.processJob); // RUNTIME ERROR DI DALAM processJob
   ```
   Secara spesifik, jelaskan apa yang terjadi pada *Execution Context* (Call Stack & Environment Record) saat runtime. Tunjukkan 3 pendekatan refactoring yang aman secara tipe (*type-safe*) tanpa menyebabkan memory leak atau degradasi performa pada *hot path*.

3. **Rest Parameters, Tuple Types, dan Labeled Tuples**  
   Analisis bagaimana TypeScript mengevaluasi inferensi tipe ketika `...rest` parameter dikombinasikan dengan generic tuple types:
   ```typescript
   type Handler<T extends unknown[]> = (...args: [...T, context: RequestContext]) => Promise<void>;
   ```
   Bagaimana compiler menyelesaikan over-indexing dan optional elements jika `T` dievaluasi dari spread arguments dinamis? Jelaskan batas inferensi ketika parameter tuple tersebut dioperasikan ke fungsi `curry` atau `compose`.

4. **Assertion Signatures vs. Type Guards**  
   Diberikan deklarasi:
   ```typescript
   function assertValidSession(session: unknown): asserts session is ActiveSession {
     if (!session || !(session as any).token) {
       throw new SecurityException("Invalid token");
     }
   }
   ```
   Bagaimana TypeScript compiler mengubah execution branch state setelah baris eksekusi pemanggilan assertion signature ini? Mengapa assertion signature tidak diizinkan pada arrow function yang tidak memiliki explicit type annotation, dan mengapa compiler menolak jika assertion function mengembalikan nilai non-void?

5. **Dynamic `this` Rebinding dengan Built-in Utility Type `ThisParameterType` dan `OmitThisParameter`**  
   Bagaimana arsitektur tipe `ThisParameterType<T>` dan `OmitThisParameter<T>` bekerja secara internal menggunakan conditional types dan keyword `infer`? Buat derivasi definisi tipenya sendiri dari nol dan jelaskan mengapa fungsi `bind` bawaan JavaScript (`Function.prototype.bind`) sering kali kehilangan inferensi argumen penuh jika digunakan tanpa polyfill typings yang presisi.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck dan Memory Leak Akibat Arrow Function Bindings pada High-Throughput Gateway
Sebuah sistem API Gateway berbasis Fastify/Node.js memproses 45.000 req/sec. Untuk menghindari error hilangnya context `this` pada handler, tim engineering menerapkan class controller dengan format:
```typescript
class ProxyController {
  private readonly metricsClient = new MetricsCollector();
  private readonly upstreamPool = new ConnectionPool();

  public handleRequest = async (req: Request, res: Response): Promise<void> => {
    this.metricsClient.record(req);
    await this.upstreamPool.forward(req, res);
  };
}
```
Setiap kali route diinisialisasi atau dibuat per scope tenant secara dinamis, terjadi lonjakan konsumsi V8 Heap Memory hingga memicu Out-Of-Memory (OOM) crash berulang di Kubernetes Pods.
* **Pertanyaan Diagnostik:**
  1. Mengapa alokasi arrow function pada field class menghasilkan memory footprint yang signifikan dibanding prototype methods pada instansiasi massal?
  2. Rancanglah arsitektur Controller menggunakan kombinasi `Method Call Signature`, explicit `this` typing, dan zero-overhead dependency passing yang mempertahankan type safety 100% tanpa melakukan instantiasi closures berulang pada V8 heap.

### Skenario B: Silent Failure pada Payment Engine Akibat Type Predicate Unsoundness
Sebuah payment processing engine menerima payload JSON webhook polymorphic dari multiple provider (Stripe, Adyen, Xendit). Developer membuat Custom Type Guard berikut:
```typescript
interface StripePayload {
  provider: "STRIPE";
  chargeId: string;
  amount: number;
}

interface AdyenPayload {
  provider: "ADYEN";
  pspReference: string;
  amount: number;
}

type PaymentPayload = StripePayload | AdyenPayload;

function isStripePayload(payload: PaymentPayload): payload is StripePayload {
  return "chargeId" in payload;
}
```
Di production, Adyen merilis update skema payload baru yang secara opsional menyertakan metadata key `chargeId` untuk cross-provider backward compatibility. Akibatnya, jutaan transaksi Adyen masuk ke pipeline parser Stripe, menyebabkan crash downstream runtime `NaN` karena parsing gagal secara parsial tanpa terdeteksi compiler TypeScript.
* **Pertanyaan Diagnostik:**
  1. Identifikasi kelemahan mendasar dari type predicate manual di atas terkait structural compatibility dan kontrak tipe terbuka (*open types*) di TypeScript.
  2. Ubah mekanisme type checking tersebut menjadi *Discriminated Union Engine* yang kedap runtime failure (*exhaustiveness check*), dan bandingkan trade-off keamanannya bila menggunakan schema validation engine (seperti Zod/TypeBox) berbasis assertion types.

### Skenario C: Overload Explosion pada Unified Event Sourcing Client
Anda ditugaskan mendesain SDK klien untuk messaging broker Kafka/RabbitMQ. Klien harus memiliki API method tunggal `dispatch` yang mendukung berbagai bentuk payload tergantung pada mode pengiriman:
- Mode Sync: Membutuhkan timeout parameter, mengembalikan `Promise<Receipt>`
- Mode Async: Tidak memerlukan timeout, mengembalikan `Promise<void>`
- Mode Batch: Menerima array of events, mengembalikan `Promise<BatchReceipt>`
- Mode Fire-and-Forget: Mengembalikan `void` (bukan Promise)

Developer sebelumnya membuat 12 kombinasi Function Overloads yang menyebabkan code redundancy, kegagalan compiler menginfer argumen generic saat function dioperasikan sebagai higher-order function, dan intellisense yang membingungkan.
* **Pertanyaan Diagnostik:**
  1. Mengapa teknik Function Overload konvensional mengalami degradasi performa kompilasi (*compiler overhead*) dan kegagalan type unification saat dipadukan dengan generic composition?
  2. Transformasikan signature API tersebut dari multiple method overloads menjadi *Single Signature Driven by Conditional Types & Mapped Argument Configurations*. Tunjukkan arsitektur typings-nya secara terstruktur.

---

## 4. Chapter Challenge

**Tantangan Praktis: Type-Safe Event Pipeline Engine dengan Dynamic Context Execution & Strict Validation**

### Problem Statement
Anda diminta membangun sebuah module enterprise-grade bernama `ExecutionPipelineEngine`. Sistem ini bertanggung jawab mengeksekusi rangkaian lifecycle middleware/hook yang memiliki context state dinamis, type-safe event routing, serta assertion enforcement. Pipeline ini harus mencegah context leakage, mampu mendeteksi context mutations secara statis, dan mengeksekusi hooks secara berurutan (*waterfall execution*).

### Requirements
1. **Context Isolation**: Pipeline harus menyediakan explicit context execution parameter (`this: PipelineContext<TState>`) yang terikat pada runtime executor, sehingga caller tidak bisa menyuntikkan arbitrary object ke dalam pipeline tanpa lolos type-checking.
2. **Dynamic Signature Overloading / Composition**:
   Implementasikan method `use()` yang mendaftarkan middleware functions. Method ini harus memiliki signature typesafe sedemikian rupa sehingga:
   - Jika middleware melakukan mutasi context (menambahkan data ke `state`), state baru tersebut harus terakumulasi dan terinfer secara otomatis ke middleware berikutnya melalui pipeline chaining (Type-level Accumulator).
3. **Execution Guarding**: Implementasikan assert runner `execute(initialState: TState)` yang menggunakan *Assertion Signatures* untuk memvalidasi bahwa seluruh *mandatory fields* pada state akhir telah terpenuhi sebelum mengembalikan hasil eksekusi; jika validasi gagal, engine melempar error dan compiler melarang akses ke field downstream.
4. **Zero Unsound Casting**: Dilarang keras menggunakan `any`, `unknown as TargetType` (forced casting), atau single-letter generic tanpa constraints (`T` murni tanpa batas). Gunakan conditional types, mapped types, atau type parameter constraints.

### Constraints
- Wajib mengaktifkan compiler options: `"strict": true`, `"exactOptionalPropertyTypes": true`, `"noImplicitReturns": true`.
- Module tidak boleh menggunakan library eksternal (murni native TypeScript/JavaScript execution).
- Memory footprint: Middleware chain tidak boleh menginstansiasi duplicate prototype context baru pada setiap cycle execution.

### Expected Output
Sajikan implementasi production-ready yang mencakup:
1. Interface dan Types declaration (`PipelineContext`, `MiddlewareSignature`, dsb).
2. Class/Engine implementation (`PipelineBuilder`).
3. Verifikasi testing code yang membuktikan bahwa mutasi context terinferensi antar-middleware bertingkat, dan testing type failure (ekspektasi compile-time error) saat middleware mencoba mengakses field yang belum diinisialisasi oleh middleware sebelumnya.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan internal engine V8 antara Function Declaration, Function Expression, dan Class Method dalam konteks alokasi prototype memory dan dynamic binding `this`.
- [ ] Aturan Contravariance pada parameter fungsi vs. Covariance pada return type di bawah flag `--strictFunctionTypes`.
- [ ] Batasan sistem tipe structural TypeScript dalam memvalidasi integritas runtime object saat menggunakan Custom Type Predicate (`val is T`).
- [ ] Perilaku Function Overload: Mengapa Overload Signatures diekspos ke consumer sedangkan Implementation Signature sepenuhnya privat secara tipe.
- [ ] Perbedaan semantik eksekusi antara *Assertion Signatures* (`asserts condition`) dan *Narrowing Guards* (`val is T`) dalam Control Flow Analysis (CFA).
- [ ] Cara kerja utility types contextual: `ThisType<T>`, `ThisParameterType<T>`, dan `OmitThisParameter<T>`.

### Saya tidak perlu menghafal:
- [ ] Ratusan permutasi overload signature untuk API bawaan DOM/Node.js (misal: semua varian `addEventListener` atau `fs.readFile`); cukup pahami pola generalisasi generic dan conditional types-nya.
- [ ] V8 Internal C++ OpCodes saat context execution switching terjadi di microtask loop.
- [ ] Hack sintaksis usang untuk manipulasi `arguments.callee` atau `Function.caller` yang deprecated di strict mode.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi dan memperbaiki error context `this` pada asynchronous callbacks/event listeners tanpa mengorbankan performa heap allocation.
- [ ] Mendesain generic higher-order functions (HOC/Decorators/Middlewares) yang dapat mengakumulasi, mentransformasi, dan memvalidasi type state secara chained.
- [ ] Mengeliminasi runtime type breaches akibat unsound type guards dengan menggantinya menjadi Discriminated Unions atau schema-based assertion parsing.
- [ ] Menulis ambient declarations dan typing signatures untuk dynamic functions yang menggunakan binding eksplisit via `.call()`, `.apply()`, atau `.bind()`.
- [ ] Mengubah arsitektur API overloaded yang rapuh (*brittle overload sets*) menjadi unified conditional signatures yang modular dan ramah autocompletion.