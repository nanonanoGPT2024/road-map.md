# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (BAB-07: OOP Modern & Decorators)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedakan** secara mendalam arsitektur internal antara TC39 Stage 3 Decorators (TypeScript 5.0+) dan Legacy Experimental Decorators (`experimentalDecorators: true`), termasuk siklus hidup emisi metadata dan pergeseran paradigma runtime.
- **Mengimplementasikan Pola Rekayasa Aspect-Oriented Programming (AOP)** tingkat produksi untuk *cross-cutting concerns* (distributed tracing, circuit breaking, idempotency, dan dynamic rate limiting) tanpa mengorbankan integritas *type safety* pada compile-time.
- **Membangun Custom Inversion of Control (IoC) Container** berbasis *Decorator Metadata* (`Symbol.metadata`) standar TC39 tanpa dependensi eksternal `reflect-metadata`, lengkap dengan *lifecycle management* (singleton, transient, request-scoped).
- **Mendiagnosis dan Memitigasi Regresi Performa V8** akibat modifikasi prototipe dan *de-optimization* (polymorphism, hidden class transitions/megamorphic call sites) yang ditimbulkan oleh wrappers decorator.
- **Mendesain Arsitektur Domain Model Enterprise** yang memisahkan pure domain logic dari infrastruktur orkestrasi menggunakan *Class Decorators*, *Auto-Accessors*, dan *Method Contexts*.

---

## 2. Prerequisite

Sebelum menempuh modul ini, engineer wajib menguasai:
- **TypeScript 5.x Fundamentals**: Generics tingkat lanjut (*conditional types*, *template literal types*, *higher-order type manipulation*, `infer` keyword).
- **ECMAScript Mechanics**: Prototypes, Property Descriptors, Proxy & Reflect API, Symbol, Closure Scope, serta Event Loop Microtask/Macrotask queue.
- **Object-Oriented Design**: Prinsip SOLID, Gang of Four (GoF) structural patterns (khususnya Proxy, Decorator, Adapter), serta Inversion of Control / Dependency Injection.
- **Runtime Internals**: Pemahaman dasar tentang cara kerja V8 Engine (V8 hidden classes/shapes, inline caching, feedback vectors).

---

## 3. Concept & Internal Architecture

### 3.1 Evolusi Decorators: Stage 3 (Standard) vs Legacy (Experimental)

Sejak rilis TypeScript 5.0, ekosistem TypeScript mengadopsi standar **TC39 Stage 3 Decorators**. Terdapat perbedaan arsitektural fundamental antara implementasi legacy dan standar baru:

```
+------------------------------------+-------------------------------------------+
| Fitur / Dimensi                    | Legacy (experimentalDecorators: true)     | Stage 3 (TypeScript 5.0+ Standard)        |
+------------------------------------+-------------------------------------------+
| Spesifikasi                        | Proposal 2014-2015 (Angular-driven)       | TC39 Stage 3 (Modern ECMAScript)          |
| Parameter Decorator                | Didukung via parameterIndex               | Tidak didukung secara native              |
| Akses Modifikasi Property          | Melalui Object.defineProperty pada proto  | Menggunakan 'accessor' keyword / init fn  |
| Metadata Engine                    | reflect-metadata (non-standar, heavy)     | Symbol.metadata (native ECMAScript)       |
| Nilai Kembalian Decorator          | Bervariasi, sering mengabaikan descriptor | Return function pengganti/initializer     |
| Konteks Pemanggilan                | (target, propertyKey, descriptor)         | (target, context: ClassXDecoratorContext) |
+------------------------------------+-------------------------------------------+
```

### 3.2 Anatomy of Stage 3 Decorator Context

Pada standar Stage 3, decorator menerima dua parameter:
1. `target`: Nilai yang didekorasi (fungsi method, getter/setter, class constructor, atau `undefined` untuk field).
2. `context`: Objek kontekstual yang dijamin oleh runtime TypeScript, bertipe variatif sesuai target:
   - `ClassDecoratorContext`
   - `ClassMethodDecoratorContext`
   - `ClassGetterDecoratorContext` / `ClassSetterDecoratorContext`
   - `ClassFieldDecoratorContext`
   - `ClassAccessorDecoratorContext`

```typescript
type ClassMethodDecoratorContext<
    This = unknown,
    Value extends (...args: any[]) => any = (...args: any[]) => any
> = {
    readonly kind: "method";
    readonly name: string | symbol;
    readonly static: boolean;
    readonly private: boolean;
    readonly access: {
        has(object: This): boolean;
        get(object: This): Value;
    };
    addInitializer(initializer: (this: This) => void): void;
    readonly metadata: DecoratorMetadata;
};
```

### 3.3 The Auto-Accessor Primitive (`accessor`)

Sebelum Stage 3, mendekorasi *field* secara dinamis tanpa mengeksekusi getter/setter implisit sangat rentan *race condition*. ECMAScript memperkenalkan *auto-accessors*:

```typescript
class AccountService {
    accessor balance: number = 0;
}
```

Di balik layar, transpiler mentransformasikannya menjadi:
- Sebuah private storage slot (e.g., `#balance`).
- Getter dan setter otomatis pada prototype yang membaca dan menulis ke private storage slot tersebut.
- `ClassAccessorDecoratorContext` memungkinkan intercept terhadap get/set serta inisialisasi awal via method `init`.

### 3.4 Symbol.metadata Pipeline

Pada TypeScript 5.2+, `Symbol.metadata` resmi menjadi bagian dari standar ECMAScript. Objek metadata bertindak sebagai kamus yang diwariskan melalui prototype chain:

```
[BaseClass] ---> Symbol.metadata (Object.create(null))
      ^
      |
[DerivedClass] -> Symbol.metadata (Object.create(BaseClass[Symbol.metadata]))
```

Setiap decorator yang membaca atau menulis ke `context.metadata` memasukkan state deklaratif ke objek ini. Saat runtime, metadata diakses langsung via `ClassConstructor[Symbol.metadata]`, memangkas total kebutuhan pustaka eksternal `reflect-metadata` yang berukuran puluhan kilobyte dan rawan *memory leak*.

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal di Skala Enterprise?
Pada aplikasi monolitik maupun microservices skala besar, penulisan kode infrastruktur (telemetri, validasi argumen, otorisasi RBAC, isolasi transaksi basis data) yang disatukan di dalam domain method menciptakan antipattern **Code Tangling** dan **Code Scattering**.

- **Code Tangling**: Domain method memuat 80% kode infrastruktur dan hanya 20% *core business logic*.
- **Code Scattering**: Kode yang sama (misal: logging span OpenTelemetry) diulang secara identik di ratusan service class.

### Apa Solusinya?
Aspect-Oriented Programming (AOP) via Stage 3 Decorators mengekstraksi cross-cutting concerns ke level deklaratif. Dengan memanfaatkan decorators modern:
1. **Zero Runtime Overhead saat Idle**: Intersepsi terjadi saat bootstrap atau instansiasi.
2. **Compiler-Guaranteed Signatures**: Validasi tipe argumen dan return value dijamin oleh TypeScript type checker tanpa menggunakan unsafe casting (`as any`).
3. **Decoupled Infrastructure**: Business code sepenuhnya terisolasi dan mudah diuji secara unit testing murni tanpa mocking wrapper kompleks.

---

## 5. How (Workflow Detail)

Alur eksekusi decorator pada saat class di-*load* oleh runtime engine adalah sebagai berikut:

```
1. Class Definition Parsing
   │
2. Field/Method Decorators Evaluation (Lexical Order: Top-to-Bottom)
   │
3. Decorators Execution (Reverse Order: Bottom-Up)
   ├── Method Decorators
   ├── Accessor & Getter/Setter Decorators
   └── Field Decorators
   │
4. Class Decorator Execution (Reverse Order: Bottom-Up)
   │
5. Constructor Definition Frozen
   │
6. Instantiation (new ClassInstance())
   ├── Field Initializers run (via addInitializer or accessor init)
   └── Constructor body executes
```

Langkah-langkah implementasi enterprise decorator:
1. **Tentukan Abstraksi Target**: Identifikasi apakah decorator akan mengubah method behavior (mengembalikan wrapper function), mengamati lifecycle via `addInitializer`, atau menyimpan konfigurasi deklaratif ke `context.metadata`.
2. **Type-Constrain Signature**: Gunakan *Generic Constraints* agar decorator hanya dapat disematkan pada method dengan signature yang kompatibel.
3. **Handle Async Execution Paths**: Pastikan wrapper menangani rejections/exceptions secara transparan, mempertahankan error stack trace asli.
4. **Isolasi Hidden Class Mutation**: Hindari penambahan properti baru secara dinamis ke `this` di dalam decorator runtime guna mempertahankan *V8 Monomorphic Call Sites*.

---

## 6. Analogy & Diagram ASCII

### Analogi: Security Screening & Baggage Handling di Bandara

Bayangkan sebuah pesawat komersial (**Business Logic / Core Method**):
- Pilot hanya bertugas menerbangkan pesawat dari titik A ke titik B.
- Namun sebelum terbang, ada serangkaian protokol:
  - Pemeriksaan Paspor / Imigrasi (**Authentication / Authorization Decorator**)
  - Pemindaian Sinar-X Bagasi (**Validation Decorator**)
  - Pencatatan Manifest Penerbangan (**Audit Logging Decorator**)
  - Pengalihan Rute saat Cuaca Buruk (**Circuit Breaker Decorator**)

Penumpang tidak perlu memeriksa paspornya sendiri di dalam kokpit; seluruh protokol dieksekusi secara deklaratif di gerbang keberangkatan sebelum penumpang masuk ke pesawat.

### Diagram Arsitektur Intersepsi AOP Modern

```
Client Call: service.executeTransfer(payload)
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ @AuditLog (Outer Wrapper)                                   │
│  - Captures TraceId, Start Time                             │
│  - context.name = "executeTransfer"                         │
│  │                                                          │
│  ▼                                                          │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ @CircuitBreaker({ threshold: 5, resetTimeout: 10000 })  │ │
│ │  - Checks failure state from Shared Memory Registry     │ │
│ │  │                                                      │ │
│ │  ▼                                                      │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ @Transactional({ isolation: "SERIALIZABLE" })       │ │ │
│ │ │  - Opens DB Transaction from Pool                   │ │ │
│ │ │  - Injects Transaction Context                      │ │ │
│ │ │  │                                                  │ │ │
│ │ │  ▼                                                  │ │ │
│ │ │ ┌─────────────────────────────────────────────────┐ │ │ │
│ │ │ │ Target Method: executeTransfer()                │ │ │ │
│ │ │ │ (Pure Business Logic - No DB commit/rollback)   │ │ │ │
│ │ │ └─────────────────────────────────────────────────┘ │ │ │
│ │ │  │                                                  │ │ │
│ │ │  - Commits DB Transaction                           │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ │  │                                                      │ │
│ │  - Reports success to Circuit Metrics                   │ │
│ └─────────────────────────────────────────────────────────┘ │
│  │                                                          │
│  - Flushes OpenTelemetry Spans                              │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
Response returned to Client
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Type-Safe Method Execution Profiler (Stage 3)

```typescript
// Implementasi decorator standar TC39 Stage 3
function MeasureExecutionTime<This, Args extends any[], Return>(
    target: (this: This, ...args: Args) => Return,
    context: ClassMethodDecoratorContext<This, (this: This, ...args: Args) => Return>
) {
    const methodName = String(context.name);

    return function (this: This, ...args: Args): Return {
        const start = performance.now();
        try {
            const result = target.call(this, ...args);
            
            // Tangani synchronous vs asynchronous execution
            if (result instanceof Promise) {
                return result.then((data) => {
                    const duration = (performance.now() - start).toFixed(2);
                    console.info(`[ASYNC] ${methodName} dieksekusi dalam ${duration}ms`);
                    return data;
                }) as Return;
            }

            const duration = (performance.now() - start).toFixed(2);
            console.info(`[SYNC] ${methodName} dieksekusi dalam ${duration}ms`);
            return result;
        } catch (error) {
            const duration = (performance.now() - start).toFixed(2);
            console.error(`[ERROR] ${methodName} gagal setelah ${duration}ms`, error);
            throw error;
        }
    };
}

class InvoiceProcessor {
    @MeasureExecutionTime
    processBatch(invoiceIds: string[]): void {
        let acc = 0;
        for (let i = 0; i < 1_000_000; i++) { acc += i; }
    }

    @MeasureExecutionTime
    async fetchRemoteInvoices(): Promise<string[]> {
        return new Promise((resolve) => setTimeout(() => resolve(["INV-01", "INV-02"]), 50));
    }
}
```

### 7.2 Practical Example: Enterprise Distributed Circuit Breaker Pattern

Di bawah ini adalah implementasi *stateful* Circuit Breaker untuk mengisolasi kegagalan integrasi downstream (misal: Payment Gateway).

```typescript
enum CircuitState {
    CLOSED,
    OPEN,
    HALF_OPEN
}

interface CircuitBreakerOptions {
    failureThreshold: number;
    recoveryTimeoutMs: number;
}

class CircuitBreakerOpenError extends Error {
    constructor(actionName: string) {
        super(`[CircuitBreaker] Eksekusi ditolak. Circuit dalam kondisi OPEN untuk aksi: ${actionName}`);
        this.name = "CircuitBreakerOpenError";
    }
}

function CircuitBreaker(options: CircuitBreakerOptions) {
    return function <This, Args extends any[], Return>(
        target: (this: This, ...args: Args) => Promise<Return>,
        context: ClassMethodDecoratorContext<This, (this: This, ...args: Args) => Promise<Return>>
    ) {
        const methodName = String(context.name);
        let state = CircuitState.CLOSED;
        let failureCount = 0;
        let nextAttempt = Date.now();

        return async function (this: This, ...args: Args): Promise<Return> {
            const now = Date.now();

            if (state === CircuitState.OPEN) {
                if (now > nextAttempt) {
                    state = CircuitState.HALF_OPEN;
                } else {
                    throw new CircuitBreakerOpenError(methodName);
                }
            }

            try {
                const result = await target.call(this, ...args);
                if (state === CircuitState.HALF_OPEN) {
                    state = CircuitState.CLOSED;
                    failureCount = 0;
                }
                return result;
            } catch (err) {
                failureCount++;
                if (failureCount >= options.failureThreshold || state === CircuitState.HALF_OPEN) {
                    state = CircuitState.OPEN;
                    nextAttempt = now + options.recoveryTimeoutMs;
                }
                throw err;
            }
        };
    };
}

// Client Consumption
class ThirdPartyPaymentClient {
    @CircuitBreaker({ failureThreshold: 3, recoveryTimeoutMs: 5000 })
    async chargeCreditCard(token: string, amountCents: number): Promise<{ id: string }> {
        // Simulasi network boundary call
        if (Math.random() < 0.7) {
            throw new Error("HTTP 503: Service Unavailable");
        }
        return { id: `ch_${Date.now()}` };
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Native TC39 Dependency Injection & Transactional Engine

Sebuah arsitektur platform perbankan modern menolak penggunaan pustaka eksternal pihak ketiga (`reflect-metadata`, `InversifyJS`) untuk mempercepat *cold-start* serverless (AWS Lambda) dan mematuhi regulasi zero-third-party-bloat.

Sistem membutuhkan:
1. DI Container yang bekerja secara native via Stage 3 `Symbol.metadata`.
2. `@Injectable` class decorator.
3. `@Transactional` method decorator yang mengelola siklus commit/rollback secara atomik.

```typescript
// Polyfill untuk Symbol.metadata jika runtime engine belum menyediakannya
(Symbol as any).metadata ??= Symbol("Symbol.metadata");

// --- 1. CORE TYPES & METADATA REGISTRY ---
type Constructor<T = any> = new (...args: any[]) => T;
const INJECTABLE_TOKEN = Symbol("INJECTABLE_TOKEN");

interface ClassMetadataRecord {
    [INJECTABLE_TOKEN]?: boolean;
    dependencies?: Constructor[];
}

function Injectable() {
    return function <T extends Constructor>(target: T, context: ClassDecoratorContext<T>) {
        const metadata = context.metadata as ClassMetadataRecord;
        metadata[INJECTABLE_TOKEN] = true;
    };
}

// --- 2. TRANSACTION CONTEXT & DECORATOR ---
interface IDatabaseSession {
    id: string;
    isActive: boolean;
    query(sql: string, params: any[]): Promise<void>;
    commit(): Promise<void>;
    rollback(): Promise<void>;
    release(): void;
}

class MockDatabaseSession implements IDatabaseSession {
    id = Math.random().toString(36).substring(7);
    isActive = true;

    async query(sql: string, params: any[]): Promise<void> {
        if (!this.isActive) throw new Error("Sesi database tidak aktif.");
        console.log(`[DB Session: ${this.id}] Executing: ${sql} | Params: ${JSON.stringify(params)}`);
    }

    async commit(): Promise<void> {
        console.log(`[DB Session: ${this.id}] COMMIT berhasil.`);
        this.isActive = false;
    }

    async rollback(): Promise<void> {
        console.warn(`[DB Session: ${this.id}] ROLLBACK dijalankan!`);
        this.isActive = false;
    }

    release(): void {
        console.log(`[DB Session: ${this.id}] Koneksi dikembalikan ke connection pool.`);
    }
}

// Transaction Context Holder menggunakan thread-local storage/symbol
const SESSION_STORAGE = new WeakMap<object, IDatabaseSession>();

function Transactional() {
    return function <This extends object, Args extends any[], Return>(
        target: (this: This, ...args: Args) => Promise<Return>,
        context: ClassMethodDecoratorContext<This, (this: This, ...args: Args) => Promise<Return>>
    ) {
        return async function (this: This, ...args: Args): Promise<Return> {
            const session = new MockDatabaseSession();
            SESSION_STORAGE.set(this, session);

            try {
                const result = await target.call(this, ...args);
                await session.commit();
                return result;
            } catch (error) {
                await session.rollback();
                throw error;
            } finally {
                session.release();
                SESSION_STORAGE.delete(this);
            }
        };
    };
}

// --- 3. ENTERPRISE IOC CONTAINER ---
class EnterpriseContainer {
    private singletons = new Map<Constructor, any>();

    public resolve<T>(ServiceClass: Constructor<T>): T {
        const metadata = (ServiceClass as any)[Symbol.metadata] as ClassMetadataRecord | undefined;
        
        if (!metadata || !metadata[INJECTABLE_TOKEN]) {
            throw new Error(`[IoC] Kelas ${ServiceClass.name} belum didaftarkan dengan @Injectable.`);
        }

        if (this.singletons.has(ServiceClass)) {
            return this.singletons.get(ServiceClass);
        }

        const instance = new ServiceClass();
        this.singletons.set(ServiceClass, instance);
        return instance;
    }
}

// --- 4. BUSINESS DOMAIN SERVICES ---
@Injectable()
class AccountLedgerRepository {
    async updateBalance(session: IDatabaseSession, accountId: string, delta: number): Promise<void> {
        await session.query("UPDATE accounts SET balance = balance + $1 WHERE id = $2", [delta, accountId]);
    }
}

@Injectable()
class FundTransferService {
    constructor(private readonly ledgerRepo = new AccountLedgerRepository()) {}

    @Transactional()
    async executeTransfer(fromId: string, toId: string, amount: number): Promise<void> {
        // Mengambil session yang disuntikkan secara dinamis oleh context decorator
        const currentSession = SESSION_STORAGE.get(this);
        if (!currentSession) {
            throw new Error("Konteks database transaksi tidak terdeteksi!");
        }

        console.log(`Memulai transfer dana senilai Rp ${amount}...`);
        await this.ledgerRepo.updateBalance(currentSession, fromId, -amount);

        // Simulasi error validasi bisnis: Saldo anjlok melebihi limit
        if (amount > 100_000_000) {
            throw new Error("Transfer melampaui limit Anti-Money Laundering (AML)!");
        }

        await this.ledgerRepo.updateBalance(currentSession, toId, amount);
        console.log("Transfer dana tuntas tanpa hambatan.");
    }
}

// --- 5. RUNTIME EXECUTION TEST ---
(async () => {
    const container = new EnterpriseContainer();
    const transferService = container.resolve(FundTransferService);

    console.log("--- TEST CASE 1: Transfer Normal ---");
    await transferService.executeTransfer("ACC-101", "ACC-202", 500_000);

    console.log("\n--- TEST CASE 2: Transfer Exception (Rollback Check) ---");
    try {
        await transferService.executeTransfer("ACC-101", "ACC-999", 500_000_000);
    } catch (err: any) {
        console.error(`Transparansi Error Terkonfirmasi: ${err.message}`);
    }
})();
```

---

## 9. Trade-offs: Architectural Cost Analysis

```
+--------------------+---------------------------------------+---------------------------------------+
| Matriks            | Pendekatan Decorator (AOP)            | Pendekatan Explicit Composition (FP)  |
+--------------------+---------------------------------------+---------------------------------------+
| Performa (Ops/Sec) | Lebih Rendah (~5-15% overhead invoke) | Mendekati Native (~0% overhead)       |
| Call Stack Depth   | Dalam (Banyak closure layer wrappers) | Dangkal (Pipeline langsung/linear)    |
| V8 Shape Integrity | Berisiko jika memutasi prototype/this | Stabil (Pure input/output maps)       |
| Developer Velocity | Tinggi (Clean, deklaratif, konsisten) | Sedang (Banyak boilerplates manual)   |
| Debuggability      | Kompleks saat stack trace tersamarkan | Mudah (Trace langsung merujuk fungsi) |
| Memory Footprint   | Retensi closure wrappers per instansiasi| Sangat rendah                         |
+--------------------+---------------------------------------+---------------------------------------+
```

### Dampak Kritis V8 Engine: Hidden Classes & Megamorphism
Ketika decorator menambahkan method atau properti secara dinamis menggunakan `Object.defineProperty` ke target `this`, V8 akan mengubah representasi memori objek (*Hidden Class Transition*). Jika sebuah method menerima objek yang bentuknya (shape) selalu berubah akibat urutan decorator yang tidak konsisten, call site pemanggilan method tersebut bertransformasi dari **Monomorphic** -> **Polymorphic** -> **Megamorphic**. 

*Dampak Megamorphic Call Site*: V8 menonaktifkan *Inline Cache (IC)* dan beralih ke dynamic hash-table lookup yang memperlambat performa eksekusi hingga 10x-50x pada loop intensif.

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Kehilangan Bindings Execution Context (`this`)
*Gejala*: `Cannot read properties of undefined (reading 'ledgerRepo')`.
*Penyebab*: Mengembalikan plain wrapper function tanpa `target.call(this, ...args)`.
*Solusi*:
```typescript
// SALAH
return function(...args: any[]) {
    return target(...args); // 'this' bernilai global/undefined!
};

// BENAR
return function(this: This, ...args: Args) {
    return target.call(this, ...args);
};
```

### Mistake 2: Type Inference Eradication
*Gejala*: Penggunaan `(...args: any[]) => any` tanpa Generics, menghapus intellisense parameter dan return types di level consumer.
*Solusi*: Gunakan *higher-order generic signatures* seperti yang dicontohkan di Section 7.1.

### Mistake 3: Resolusi Metadata Sebelum Registrasi (Race Condition)
*Gejala*: `Symbol.metadata` bernilai kosong saat diakses di entry-point aplikasi.
*Penyebab*: Modul dievaluasi tidak berurutan karena *circular dependency* (siklus impor antar service).
*Solusi*:
- Pisahkan interfaces dan tokens ke dalam file independen (misal: `tokens.ts`).
- Konfigurasikan esbuild/tsc untuk tidak melakukan *tree-shaking* pada file dekorator murni dengan menambahkan *sideEffects* flag di `package.json`.

---

## 11. Best Practices (Production Checklist)

- [ ] **Gunakan Standar TC39 (TypeScript 5+)**: Matikan flag `"experimentalDecorators": true` di `tsconfig.json` jika membangun project baru berbasis standar Stage 3.
- [ ] **Pure Wrappers**: Jangan pernah memodifikasi `target.prototype` secara destruktif di dalam method decorator; selalu kembalikan wrapper function baru.
- [ ] **Preserve Error Fidelity**: Jangan mengubah instance error domain di dalam interceptor kecuali untuk memetakan technical exception ke domain exception secara formal.
- [ ] **Non-Blocking Observability**: Jika decorator mengeksekusi asynchronous telemetry/logging, pastikan logging failure tidak melempar uncaught rejection yang merusak domain flow (gunakan `catch` internal).
- [ ] **Avoid Parameter Decorator Dependency**: Mengingat standar Stage 3 saat ini belum meresmikan parameter decorators, gunakan *Method Object Pattern* atau *Auto-Accessor* untuk metadata parameter.
- [ ] **Audit Memory via WeakMap**: Jika context decorator harus menempelkan metadata yang berumur pendek pada lifecycle suatu objek, gunakan `WeakMap<object, Context>` agar objek dapat di-garbage collect secara normal.

---

## 12. Hands-on Practice

Buatlah workspace praktikum mandiri dengan struktur direktori berikut:

```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install typescript @types/node ts-node --save-dev
```

Konfigurasikan file `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "skipLibCheck": true,
    "noImplicitOverride": true,
    "verbatimModuleSyntax": false
  },
  "include": ["src/**/*"]
}
```

Buat file implementasi `src/rate-limiter.ts`:
```typescript
// Implementasi In-Memory Token Bucket Decorator
(Symbol as any).metadata ??= Symbol("Symbol.metadata");

interface RateLimitOptions {
    capacity: number;
    refillRatePerSec: number;
}

export function RateLimit(options: RateLimitOptions) {
    return function <This, Args extends any[], Return>(
        target: (this: This, ...args: Args) => Promise<Return>,
        context: ClassMethodDecoratorContext<This, (this: This, ...args: Args) => Promise<Return>>
    ) {
        let tokens = options.capacity;
        let lastRefill = Date.now();

        function refill() {
            const now = Date.now();
            const elapsedSec = (now - lastRefill) / 1000;
            tokens = Math.min(options.capacity, tokens + elapsedSec * options.refillRatePerSec);
            lastRefill = now;
        }

        return async function (this: This, ...args: Args): Promise<Return> {
            refill();
            if (tokens < 1) {
                throw new Error(`[429 Too Many Requests] Eksekusi ${String(context.name)} dibatasi.`);
            }
            tokens -= 1;
            return target.call(this, ...args);
        };
    };
}

export class ExternalApiGateway {
    @RateLimit({ capacity: 2, refillRatePerSec: 1 })
    async queryOrders(customerId: string): Promise<string[]> {
        return [`ORDER-${customerId}-A`, `ORDER-${customerId}-B`];
    }
}
```

Buat runner script `src/index.ts`:
```typescript
import { ExternalApiGateway } from "./rate-limiter.js";

async function main() {
    const gateway = new ExternalApiGateway();
    console.log("Memulai simulasi burst call rate limiter...");

    for (let i = 1; i <= 4; i++) {
        try {
            const res = await gateway.queryOrders("CUST-99");
            console.log(`Call #${i} Sukses:`, res);
        } catch (e: any) {
            console.error(`Call #${i} Gagal:`, e.message);
        }
    }

    console.log("Menunggu 2 detik untuk token refill...");
    await new Promise((r) => setTimeout(r, 2000));

    try {
        const res = await gateway.queryOrders("CUST-99");
        console.log("Call Pasca-Refill Sukses:", res);
    } catch (e: any) {
        console.error("Call Pasca-Refill Gagal:", e.message);
    }
}

main();
```

Eksekusi dengan perintah:
```bash
npx ts-node src/index.ts
```

---

## 13. Exercise

### 13.1 Level Easy
Buat decorator `@Frozen` untuk class yang menggunakan `context.addInitializer` agar setiap instansiasi class secara otomatis menjalankan `Object.freeze(this)`. Pastikan objek tidak dapat dimutasi pasca-konstruksi.

### 13.2 Level Medium
Buat decorator `@Retry({ maxAttempts: number, delayMs: number })` untuk async method. Decorator harus mengulang eksekusi fungsi jika melempar exception hingga `maxAttempts` terpenuhi. Terapkan linear backoff menggunakan `delayMs`.

### 13.3 Level Hard
Buat decorator `@AutoValidate` menggunakan standar Stage 3 yang memanfaatkan `context.metadata`. Hubungkan dengan schema parser (misal schema object sederhana buatan sendiri) untuk memvalidasi tipe argumen yang dilewatkan ke method sebelum eksekusi dimulai. Jika argumen invalid, lempar `SchemaValidationError` sebelum logic method dijalankan.

---

## 14. Challenge

Rancang arsitektur **Distributed Multi-Tenant Idempotency Engine** berbasis Decorator:
- **Spesifikasi**:
  - Diberikan decorator `@Idempotent({ keyExtractor: (args) => string, ttlSeconds: number })`.
  - Sistem harus memeriksa status eksekusi request ke cache/storage (simulasikan in-memory distributed store).
  - Jika request dengan payload identik sedang berlangsung (*in-flight*), panggilan konkuren berikutnya harus di-blok/di-tahan hingga panggilan pertama selesai, lalu mengembalikan data yang sama tanpa menduplikasi pemanggilan target method (*Single Flight / Promise Sharing Pattern*).
  - Jika request telah selesai, kembalikan response tersimpan secara instan tanpa re-eksekusi.
  - Tangani kegagalan: Jika target method melempar error, kunci idempoten harus dibatalkan (*evicted*) sehingga pemanggilan berikutnya diizinkan mencoba ulang.
- **Batasan**: Wajib menggunakan Stage 3 TC39 Decorators, fully strictly typed, zero runtime reflection library.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Basic (5 Pertanyaan)
1. Apa fungsi utama argumen kedua (`context`) pada implementasi decorator standar Stage 3?
2. Bagaimana cara mengaktifkan metadata native ECMAScript pada TypeScript 5.2+ tanpa `reflect-metadata`?
3. Mengapa parameter decorators bawaan TypeScript legacy tidak disertakan pada initial standard Stage 3?
4. Apa perbedaan mendasar antara field biasa dengan keyword `accessor` pada TypeScript modern?
5. Pada urutan apa eksekusi decorator berlangsung ketika sebuah method dihiasi oleh beberapa decorator sekaligus?

### 15.2 Intermediate (5 Pertanyaan)
6. Bagaimana cara menjaga method binding context `this` agar tidak hilang ketika decorator mengembalikan wrapper function baru?
7. Bagaimana struktur pewarisan `Symbol.metadata` ketika sebuah subclass menurunkan class induk yang memiliki decorator metadata?
8. Mengapa mutasi dinamis terhadap instance properties via decorator dapat menyebabkan *megamorphic de-optimization* pada V8?
9. Apa perbedaan pemanfaatan `addInitializer` pada Class Decorator dibandingkan dengan Method Decorator?
10. Bagaimana Anda mendesain method decorator yang dapat menangani return value berjenis synchronous maupun asynchronous (Promise) secara serentak?

### 15.3 Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario Deadlock**: Sebuah method didekorasi oleh `@Transactional` dan `@MutexLock`. Jika urutan penulisan dekorator dibalik, apa implikasi kegagalan performa atau *distributed deadlock* yang mungkin terjadi?
12. **Skenario Memory Leak**: Developer menyimpan referensi instance objek di dalam cache global level module di dalam field decorator initializer. Mengapa garbage collector V8 gagal merebut kembali memori tersebut saat request lifecycle selesai?
13. **Skenario Stack Overflow**: Decorator logging memanggil method `JSON.stringify(this)` pada class domain yang memiliki referensi relasional sirkular ganda (Parent-Child bidirectional graph). Bagaimana langkah rekayasa interceptor yang aman dari infinite recursion error?

---

## 16. Summary

1. **Paradigma Modern (TC39 Stage 3)**: Standar baru decorator mematikan kebutuhan manipulasi prototype liar dan pustaka pihak ketiga yang berat (`reflect-metadata`), menggantikannya dengan context-aware primitives (`ClassMethodDecoratorContext`, `Symbol.metadata`).
2. **Integritas Type-Safety**: Melalui higher-order generics, TypeScript 5.0+ memungkinkan penegakan signature typing yang absolut antara decorator implementation dan class method consumers.
3. **Engine-Level Performance**: Pendekatan deklaratif AOP menawarkan modularitas masif, namun rekayasawan enterprise wajib memahami implikasi V8 hidden classes, closure allocation, dan micro-benchmarking agar decorator tidak menjadi bottleneck latensi layanan.