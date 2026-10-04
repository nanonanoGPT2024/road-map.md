# BAB 10: Production Hardening & Runtime Validation
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Memitigasi Type Erasure Gap:** Mengidentifikasi celah keamanan dan integritas data akibat hilangnya informasi tipe statis TypeScript saat runtime di boundary eksternal.
- **Mengimplementasikan Paradigma "Parse, Don't Validate":** Mentransformasikan data mentah (untrusted inputs) menjadi domain model yang *type-safe* secara struktural dan semantik menggunakan *Branded/Nominal Types*.
- **Mengevaluasi & Memilih Mesin Validasi Runtime:** Melakukan analisis komparatif performa, alokasi memori, dan kompatibilitas JIT engine (V8) antara Functional AST Validators (Zod, Valibot) dan JIT Compiled Schema Validators (TypeBox, ArkType).
- **Mencegah Deoptimasi Mesin V8:** Mencegah perusakan *Hidden Classes* (*Shapes*) dan *Inline Caches* (IC) yang disebabkan oleh mutasi objek dinamis selama proses validasi/sanitasi.
- **Mendesain Arsitektur Ingress/Egress Enterprise:** Membangun pipeline validasi modular terdistribusi untuk protokol sinkron (REST/gRPC) dan asinkron (Kafka/RabbitMQ) dengan overhead latensi sub-milidetik.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib menguasai:
- **Sistem Tipe Lanjutan TypeScript:** *Generics with Contravariance/Covariance*, *Conditional Types*, *Mapped Types*, *Template Literal Types*, serta *Type Narrowing (`type predicates`, `in`, `instanceof`)*.
- **Internals Node.js & V8:** Siklus hidup alokasi memori heap, *Garbage Collection (Scavenge vs Mark-Sweep)*, serta konsep *Hidden Classes* dan *Inline Caching*.
- **Protokol Pertukaran Data:** Spesifikasi JSON Schema (Draft 7/2020-12), protokol serialisasi biner, serta manipulasi stream I/O pada Node.js.

---

### 3. Concept & Internal Architecture (Mendalam)

#### Problem Statement: Type Erasure & The Boundary Problem
Kompilator TypeScript (`tsc`) bekerja menggunakan pendekatan *erasive type system*. Seluruh antarmuka (*interface*), *type aliases*, dan parameter tipe generik dihapus sepenuhnya (*stripped out*) saat kompilasi ke JavaScript.

```
TypeScript Code (Compile-Time)       JavaScript Target (Runtime)
---------------------------------     ---------------------------
interface UserPayload {               // Interface dihapus total!
  id: string;                         function process(payload) {
  balance: number;                      return payload.balance * 1.1; 
}                                     }
function process(u: UserPayload) {    // Bila payload.balance adalah "100" (string),
  return u.balance * 1.1;             // hasil operasi: NaN atau runtime logic bug!
}
```

Pada level sistem produksi, batas aplikasi (*system boundaries*) mencakup:
- HTTP/RPC Request Body, Query String, dan Headers.
- Payload pesan dari message broker (Kafka topic, RabbitMQ exchange).
- Respons dari dependensi pihak ketiga atau microservice lain.
- Cache storage reads (Redis, Memcached) yang ter-deserialisasi.

Tanpa validasi runtime yang deterministik, casting `as Type` hanyalah ilusi keamanan (*type assertion fallacy*). Data korup yang lolos dari *boundary* akan mencemari domain core, memicu kegagalan sistematis (*silent failure*), *data corruption*, atau eksploitasi keamanan (*prototype pollution*, *type confusion*).

#### V8 Internals: Hidden Classes, Transitions, and Inline Caching
Saat validator runtime mengevaluasi objek, cara validator membaca, membuat, dan memetakan properti berdampak langsung pada optimasi JIT V8:

```
[Raw JSON Input] 
       │
       ▼
┌──────────────┐      Transisi Shape Baru      ┌──────────────┐
│ Map/Shape C0 │ ────────────────────────────> │ Map/Shape C1 │
└──────────────┘    Properti 'id' divalidasi   └──────────────┘
       │                                              │
       ▼                                              ▼
┌──────────────┐      Transisi Shape Baru      ┌──────────────┐
│ Map/Shape C1 │ ────────────────────────────> │ Map/Shape C2 │
└──────────────┘  Properti 'balance' divalidasi └──────────────┘
```

1. **Hidden Classes (Shapes):** V8 merepresentasikan struktur objek JavaScript melalui *Shapes*. Menghapus field menggunakan operator `delete` atau menambahkan field secara dinamis di luar konstruktor akan memicu transisi *Shape* baru, memaksa V8 membuat kelas transisi baru.
2. **Inline Caches (IC):** Operasi pembacaan properti (`obj.field`) dioptimasi melalui IC. Terdapat tiga kondisi:
   - **Monomorphic:** Lokasi pemanggilan hanya melihat 1 *Shape* (Kecepatan eksekusi tertinggi / JIT Inlined).
   - **Polymorphic:** Lokasi pemanggilan melihat 2-4 *Shapes* (Membutuhkan lookup branching).
   - **Megamorphic:** Lokasi pemanggilan melihat >4 *Shapes* (Fallback ke global dictionary lookup, penurunan throughput signifikan).
3. **Parse Engine Archetypes:**
   - **Functional AST Traversal (contoh: Zod):** Mengurai skema sebagai pohon komposit fungsi eksekusi. Fleksibel, memiliki Developer Experience (DX) tinggi, namun memicu alokasi memori substansial per pemanggilan serta overhead rekursif.
   - **JIT Schema Compilation (contoh: TypeBox):** Menghasilkan JSON Schema, yang kemudian dikompilasi langsung menggunakan `new Function()` menjadi fungsi JavaScript murni yang dioptimasi oleh JIT V8 (Monomorphic parsing path).

---

### 4. Why & What

| Paradigma / Pendekatan | Mekanisme Inti | Kelebihan | Kelemahan |
| :--- | :--- | :--- | :--- |
| **Validate (Boolean Checks)** | Memeriksa apakah `obj` memenuhi kriteria; me-return `boolean` | Sederhana, komputasi murah | Memisahkan pengecekan dari tipe; rentan *desynchronization* antara validator dan type domain. |
| **Type Assertion (`as T`)** | Menginstruksikan kompilator untuk mempercayai tipe data secara buta | Nol overhead eksekusi | **Anti-pattern di boundary.** Menyebabkan *runtime crash* jika payload nyata tidak valid. |
| **Parse, Don't Validate** | Membaca data mentah tak terstruktur, memverifikasi, lalu memetakan ke objek baru yang *guaranteed valid* | *Type-safe by design*, menjamin *invariant domain*, mencegah mutasi tak sengaja | Membutuhkan alokasi memori tambahan jika transformasi tidak dirancang dengan efisien. |
| **JIT Compiled Validation** | Menghasilkan kode JS validator deterministik secara dinamis saat *bootstrap* | Performa mendekati *native JS hand-written*, memory footprint minimal saat runtime | Inisialisasi awal (*cold start*) lebih berat; penggunaan `eval`/`new Function` dilarang di lingkungan sandbox ketat (mis. CSP/Cloudflare Workers tertentu). |

---

### 5. How: Workflow Detail

Implementasi arsitektur runtime hardening modular mengikuti alur *Ingress-to-Domain Pipeline*:

```
[Untrusted Wire Input] (JSON String / Buffer)
         │
         ▼
[Step 1: Byte-Size Guard & Structural Deserialization]
         │ (Deteksi ReDoS, Batas Ukuran Payload, Safe JSON.parse)
         ▼
[Step 2: Schema Compilation / Validation Execution]
         │ ─── [Invalid] ──> Format Sanitized RFC-7807 Error Response
         ▼ [Valid]
[Step 3: Domain Invariant Parsing & Data Transformation]
         │ (Coercion, Defaulting, Normalization)
         ▼
[Step 4: Branded Type Instantiation]
         │ (Mengunci tipe primitif ke Domain Primitive)
         ▼
[Step 5: Trusted Execution Domain]
         │ (Domain Core Logic / Business Services)
```

1. **Byte-Size Guard:** Membatasi ukuran payload stream untuk mencegah eksploitasi DoS berbasis alokasi memori JSON besar.
2. **Schema Compilation:** Payload dieksekusi terhadap skema terkompilasi monomorfik.
3. **Domain Invariant Parsing:** Data ditransformasi secara deterministik; properti asing dibersihkan (*strip unknown*) untuk mencegah polusi objek internal.
4. **Branded Type Assignment:** Mengunci tipe string/number primitif menjadi tipe nominal yang hanya bisa dibuat melalui modul validasi ini.
5. **Trusted Domain:** Domain layer tidak lagi melakukan validasi defensif redundan, memangkas latensi logika bisnis internal.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional (Customs & Border Protection)
- **Compile-Time Type Checking:** Sebuah paspor yang dicetak di rumah. Terlihat rapi dan valid di komputer pribadi, namun tidak memiliki kekuatan hukum tanpa pengesahan fisik.
- **Untrusted External Data:** Turis asing yang baru mendarat di bandara internasional membawa koper bawaan (payload).
- **Type Assertion (`as T`):** Petugas imigrasi langsung melambaikan tangan mempersilakan masuk tanpa memeriksa paspor atau membuka koper, hanya karena turis tersebut mengenakan jas rapi.
- **Parse, Don't Validate:** Petugas imigrasi memeriksa paspor di database pusat (schema validation), membuka koper untuk memindai barang terlarang (invariant checking), lalu memberikan stempel visa fisik khusus (*Branded Type*). Di dalam negeri (Domain Layer), turis tersebut diizinkan beraktivitas tanpa harus ditanyai identitasnya di setiap toko.

#### Diagram Arsitektur Memory & Transition Monomorfik

```
     KONDISI NON-OPTIMAL (Objek bermutasi - Polymorphic/Megamorphic)
     
     req.body ──> { a: 1 } (Shape A)
                     │
                     ▼
     delete req.body.b ──> { a: 1 } (Shape B - Mutasi Transisi Lambat)
                     │
                     ▼
     req.body.c = true ──> { a: 1, c: true } (Shape C - Deopt V8!)


     KONDISI OPTIMAL (Compiled Schema Parser - Monomorphic Shapes)

     Raw Data ──> [ Compiled Validator Function ]
                             │
                             ▼ Instansiasi Objek Baru Sekaligus
                  {
                    id: parsed.id,
                    amount: parsed.amount,
                    currency: parsed.currency
                  }  ===> Selalu menghasilkan [Shape M0] yang stabil!
                             (V8 mengaktifkan TurboFan Inlining)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Branded Types & Manual Validation Guard

Berikut implementasi murni *Zero-Dependency Branded Types* dan *Type Predicates* untuk mengamankan data identifier.

```typescript
// branded.ts

// 1. Definisikan Brand Symbol unik untuk mencegah accidental structural compatibility
declare const BrandSymbol: unique symbol;

export type Brand<T, TBrand extends string> = T & {
  readonly [BrandSymbol]: TBrand;
};

// 2. Tipe Primitif Domain Terproteksi
export type UserId = Brand<string, 'UserId'>;
export type MoneyAmount = Brand<number, 'MoneyAmount'>;

// 3. User Entity
export interface User {
  readonly id: UserId;
  readonly balance: MoneyAmount;
}

// 4. Type Predicates / Parsers
export function parseUserId(raw: unknown): UserId {
  if (typeof raw !== 'string' || !/^[a-f0-9-]{36}$/i.test(raw)) {
    throw new TypeError(`Invariant Violation: Format UserId tidak valid [${String(raw)}]`);
  }
  return raw as UserId;
}

export function parseMoneyAmount(raw: unknown): MoneyAmount {
  if (typeof raw !== 'number' || Number.isNaN(raw) || raw < 0 || !Number.isFinite(raw)) {
    throw new TypeError(`Invariant Violation: MoneyAmount harus angka positif [${String(raw)}]`);
  }
  return raw as MoneyAmount;
}

// 5. Factory Parsing
export function parseUser(rawId: unknown, rawBalance: unknown): User {
  return Object.freeze({
    id: parseUserId(rawId),
    balance: parseMoneyAmount(rawBalance),
  });
}
```

#### B. Practical Example: High-Throughput Schema Validation Engine (TypeBox + JIT Compilation)

Implementasi ingress validation tingkat industri menggunakan `@sinclair/typebox` yang dikompilasi menggunakan mesin TypeCompiler untuk performa setara *hand-written code*.

```typescript
// ingress-validator.ts
import { Type, Static } from '@sinclair/typebox';
import { TypeCompiler, TypeCheck } from '@sinclair/typebox/compiler';

// 1. Deklarasi Brand Types
declare const AccountNumberBrand: unique symbol;
export type AccountNumber = string & { readonly [AccountNumberBrand]: 'AccountNumber' };

// 2. Definisi Skema Eksternal
export const TransactionRequestSchema = Type.Object(
  {
    transactionId: Type.String({ format: 'uuid' }),
    senderAccount: Type.String({ minLength: 10, maxLength: 12 }),
    recipientAccount: Type.String({ minLength: 10, maxLength: 12 }),
    amountInCents: Type.Integer({ minimum: 1, maximum: 1_000_000_000 }),
    idempotencyKey: Type.String({ minLength: 16 }),
    metadata: Type.Optional(Type.Record(Type.String(), Type.String())),
  },
  { additionalProperties: false } // Mencegah payload injection
);

// 3. Ekstraksi Type Inference
export type RawTransactionRequest = Static<typeof TransactionRequestSchema>;

export interface DomainTransactionRequest {
  readonly transactionId: string;
  readonly senderAccount: AccountNumber;
  readonly recipientAccount: AccountNumber;
  readonly amountInCents: bigint;
  readonly idempotencyKey: string;
  readonly metadata: Readonly<Record<string, string>>;
}

// 4. Kompilasi Skema saat Inisialisasi Aplikasi (Bootstrap Time)
// JIT compilation menghasilkan mesin validator monomorfik berkecepatan tinggi
const compiledTransactionValidator: TypeCheck<typeof TransactionRequestSchema> = 
  TypeCompiler.Compile(TransactionRequestSchema);

// 5. Structured Parsing & Transformation Boundary
export class ValidationError extends Error {
  constructor(public readonly issues: Array<{ path: string; message: string }>) {
    super('Skema payload melanggar kontrak ingress');
    this.name = 'ValidationError';
  }
}

export function parseTransactionIngress(input: unknown): DomainTransactionRequest {
  // Evaluasi JIT (Bebas alokasi error berlebih jika sukses)
  const isValid = compiledTransactionValidator.Check(input);

  if (!isValid) {
    const errors = [...compiledTransactionValidator.Errors(input)].map((err) => ({
      path: err.path,
      message: err.message,
    }));
    throw new ValidationError(errors);
  }

  // Objek input dijamin valid secara struktural oleh TypeCheck
  const validData = input as RawTransactionRequest;

  // Invariant Parse & Instansiasi Objek Baru (Mencegah Shape Deoptimization)
  return Object.freeze({
    transactionId: validData.transactionId,
    senderAccount: validData.senderAccount as AccountNumber,
    recipientAccount: validData.recipientAccount as AccountNumber,
    amountInCents: BigInt(validData.amountInCents),
    idempotencyKey: validData.idempotencyKey,
    metadata: Object.freeze({ ...(validData.metadata ?? {}) }),
  });
}
```

---

### 8. Real World Case Study: Financial Ledger Ingress Engine

#### Problem Context
Sebuah bank digital memproses stream mutasi multi-rekening dari Apache Kafka dengan volume **50.000 transaksi/detik**. Implementasi sebelumnya menggunakan Zod versi dasar di dalam callback consumer Kafka:
1. Skema dideklarasikan dan di-*parse* secara dinamis, memicu GC pressure masif akibat alokasi parser AST berulang.
2. Karakteristik deserialisasi JSON heterogen menghasilkan deoptimasi V8 Inline Cache menjadi kondisi *Megamorphic*.
3. Latensi P99 meroket hingga **280ms**, menyebabkan lag partisi Kafka yang tidak terkendali.

#### Architectural Solution
Arsitektur didesain ulang dengan memisahkan tahap deserialisasi, validasi skema berbasis JIT memory-efficient, serta mapping ke *Immutable Domain Entities* menggunakan TypeBox dan *Object Pools*.

```
[Kafka Topic: ledger-entries]
           │ (High-Throughput Raw String / Buffer)
           ▼
[FastJson Stream Deserializer]
           │ (Native C++ backed / SIMD parsing)
           ▼
[Pre-compiled TypeBox Ingress Gate] (Monomorphic State)
           │
     ┌─────┴─────────────────────────┐
     │ [Pass]                        │ [Fail]
     ▼                               ▼
[Strict Invariant Domain Mapping] [Dead Letter Queue (DLQ)]
     │ (Zero mutation, BigInt cast)   (RFC-7807 Context attached)
     ▼
[Ledger Core State Machine Execution]
```

#### Production Implementation Code

```typescript
// ledger-pipeline.ts
import { Type, Static } from '@sinclair/typebox';
import { TypeCompiler } from '@sinclair/typebox/compiler';

// 1. Domain Types
declare const CurrencyCodeBrand: unique symbol;
export type CurrencyCode = string & { readonly [CurrencyCodeBrand]: 'CurrencyCode' };

export interface PostingLeg {
  readonly accountId: string;
  readonly amountUnits: bigint;
  readonly direction: 'DEBIT' | 'CREDIT';
}

export interface LedgerTransaction {
  readonly eventId: string;
  readonly timestamp: number;
  readonly currency: CurrencyCode;
  readonly legs: readonly [PostingLeg, PostingLeg, ...PostingLeg[]]; // Min 2 legs (Double-entry)
}

// 2. Strict Raw Schema
const ISO4217Regex = /^[A-Z]{3}$/;

export const LedgerEventSchema = Type.Object(
  {
    eventId: Type.String({ format: 'uuid' }),
    timestamp: Type.Integer({ minimum: 1_600_000_000_000 }),
    currency: Type.RegExp(ISO4217Regex),
    legs: Type.Array(
      Type.Object(
        {
          accountId: Type.String({ minLength: 8, maxLength: 34 }),
          amountUnits: Type.String({ pattern: '^[0-9]+$' }), // Mencegah precision loss floating point
          direction: Type.Union([Type.Literal('DEBIT'), Type.Literal('CREDIT')]),
        },
        { additionalProperties: false }
      ),
      { minItems: 2 }
    ),
  },
  { additionalProperties: false }
);

type RawLedgerEvent = Static<typeof LedgerEventSchema>;

// 3. Compile Sekali di Boot Time
const validator = TypeCompiler.Compile(LedgerEventSchema);

// 4. Ingress Core Processor
export class LedgerIngressProcessor {
  public static processRawMessage(rawPayload: string): LedgerTransaction {
    let parsedJson: unknown;

    try {
      parsedJson = JSON.parse(rawPayload);
    } catch {
      throw new Error('CORRUPT_PAYLOAD_NOT_JSON');
    }

    // Step A: Fast-Fail Type Checking
    if (!validator.Check(parsedJson)) {
      const firstError = validator.Errors(parsedJson).First();
      throw new Error(`SCHEMA_VALIDATION_FAILED: ${firstError?.path} ${firstError?.message}`);
    }

    const validRaw = parsedJson as RawLedgerEvent;

    // Step B: Double-Entry Balance Verification (Accounting Invariant)
    let netBalance = 0n;
    const mappedLegs: PostingLeg[] = new Array(validRaw.legs.length);

    for (let i = 0; i < validRaw.legs.length; i++) {
      const rawLeg = validRaw.legs[i];
      const units = BigInt(rawLeg.amountUnits);

      if (rawLeg.direction === 'DEBIT') {
        netBalance += units;
      } else {
        netBalance -= units;
      }

      mappedLegs[i] = Object.freeze({
        accountId: rawLeg.accountId,
        amountUnits: units,
        direction: rawLeg.direction,
      });
    }

    // Zero-Sum Ledger Rule: Sum(Debits) - Sum(Credits) === 0
    if (netBalance !== 0n) {
      throw new Error(`LEDGER_UNBALANCED_INVARIANT_VIOLATION: Net imbalance is ${netBalance.toString()}`);
    }

    // Step C: Construction of Immutable Domain Entity
    return Object.freeze({
      eventId: validRaw.eventId,
      timestamp: validRaw.timestamp,
      currency: validRaw.currency as CurrencyCode,
      legs: Object.freeze(mappedLegs) as unknown as readonly [PostingLeg, PostingLeg, ...PostingLeg[]],
    });
  }
}
```

#### Hasil Metrik Arsitektur Baru
- **Throughput:** Meningkat dari 8.500 ops/detik menjadi **54.200 ops/detik** per Node.js core.
- **Latensi P99:** Menurun dari 280ms menjadi **1.8ms**.
- **GC Pause Time:** Turun drastis sebesar **87%** karena skema di-*compile* satu kali saat boot time, meniadakan pembuatan objek iterator secara berulang.

---

### 9. Trade-offs: Komparasi Library Runtime Validation

| Fitur / Parameter | Zod (v3.x) | Valibot | TypeBox | ArkType |
| :--- | :--- | :--- | :--- | :--- |
| **Parsing Strategy** | Functional AST Traversal | Modular Functional AST (Tree-shakeable) | JIT Compiled via `new Function` | JIT Dynamic Scoped Inlining |
| **Throughput (Ops/sec)** | Sedang (~1x baseline) | Cepat (~2x - 4x Zod) | Ekstrem (~20x - 50x Zod) | Sangat Cepat (~15x - 35x Zod) |
| **Bundle Size Impact** | ~14 KB (Minified + Gzip) | Modular (~0.5 - 2 KB) | ~7 KB (Compiler Core) | ~18 KB |
| **Memory Allocation** | Tinggi (Object error, context) | Rendah | Sangat Rendah (Nol alokasi jika lolos) | Rendah |
| **Keamanan Lingkungan**| 100% CSP Safe (Tanpa eval) | 100% CSP Safe (Tanpa eval) | Membutuhkan CSP unsafe-eval untuk mode JIT | Bersifat Hybrid |
| **Dynamic Schema Build**| Sangat Dinamis | Sangat Dinamis | Kompleks | Deklaratif Menggunakan Syntax TS |
| **Developer Experience**| Sangat Tinggi (De facto) | Tinggi | Sedang (Lebih dekat ke JSON Schema) | Sangat Tinggi (Native string literal syntax) |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Melakukan Kompilasi Skema di Dalam Request Handler
```typescript
// FATAL ANTI-PATTERN: Kompilasi JIT berulang pada setiap HTTP Request
app.post('/api/checkout', (req, res) => {
  // INI MENGHANCURKAN PERFORMA! CPU tercekik proses kompilasi kode validator
  const check = TypeCompiler.Compile(OrderSchema);
  if (!check.Check(req.body)) return res.status(400).send();
  // ...
});

// FIX: Pindahkan kompilasi ke modul singleton / file root (Bootstrap phase)
const check = TypeCompiler.Compile(OrderSchema);
app.post('/api/checkout', (req, res) => {
  if (!check.Check(req.body)) return res.status(400).send();
});
```

#### 2. Mutasi In-Place pada Validated Object Menyebabkan V8 Megamorphism
```typescript
// MISTAKE: Mutasi langsung payload input
function sanitizeAndEnrich(payload: any) {
  delete payload.privateField; // Shape objek rusak
  payload.sanitizedAt = Date.now(); // Shape bertransisi lagi
  return payload;
}

// FIX: Buat objek target baru dengan field terprediksi secara instan
function sanitizeAndEnrich(payload: any): SecurePayload {
  const { privateField, ...rest } = payload;
  return Object.freeze({
    ...rest,
    sanitizedAt: Date.now(),
  });
}
```

#### 3. Regex Catastrophic Backtracking (ReDoS) pada Validasi String
Skema yang menerima string dengan Regex tidak aman dapat dieksploitasi untuk melumpuhkan Node.js Event Loop.
```typescript
// VULNERABLE: Memicu exponential backtracking
const BadEmailSchema = Type.RegExp(/^([a-zA-Z0-9_\.-]+)+@([\da-zA-Z\.-]+)\.([a-zA-Z\.]{2,6})$/);

// TROUBLESHOOT & FIX:
// 1. Batasi panjang karakter maksimal sebelum regex dieksekusi.
// 2. Gunakan regular expression deterministic finite automata (DFA).
const HardenedEmailSchema = Type.String({
  minLength: 5,
  maxLength: 254, // Sesuai RFC 5321
  pattern: '^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
});
```

---

### 11. Best Practices: Production Checklist

- [ ] **Zero Unvalidated Boundary:** Tidak ada data dari luar (HTTP, RPC, Queue, Storage) yang masuk ke domain tanpa validasi runtime eksplisit.
- [ ] **Avoid Runtime Schema Recreation:** Seluruh skema dideklarasikan sebagai konstanta statis di level modul (singleton lifecycle).
- [ ] **Enforce `additionalProperties: false`:** Secara default, tolak properti asing untuk meniadakan potensi *Mass Assignment Vulnerability* dan *Prototype Pollution*.
- [ ] **Branded Types for All IDs & Currencies:** Tipe data primitif krusial (UUIDs, DB IDs, Foreign keys, Moneter) wajib menggunakan teknik *Branding*.
- [ ] **Decouple Ingress Types from Domain Models:** Tipe data wire (misal JSON di mana Date berupa string ISO, atau ID berupa string) harus bertransformasi menjadi Native Domain Object (misal `Date`, `BigInt`, `DomainClass`) saat melewati parse boundary.
- [ ] **Sanitize Serialization Output (Egress):** Buat skema output serialisasi untuk menjamin data sensitif (mis. password hash, internal stack trace) tidak bocor ke klien.
- [ ] **Profiling Node.js V8:** Jalankan benchmarking berkala menggunakan `--prof` dan `--trace-deopt` guna memastikan tidak ada mesin validator yang mengalami deoptimasi bailout dari TurboFan.

---

### 12. Hands-on Practice

Buatlah implementasi pipeline runtime validation berstandar enterprise pada workspace lokal Anda:

#### File Structure
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── types/
│   │   └── brands.ts
│   ├── schemas/
│   │   └── payment.schema.ts
│   ├── parsers/
│   │   └── payment.parser.ts
│   └── index.ts
└── tests/
    └── payment.bench.ts
```

#### Step 1: Inisialisasi Project & Dependensi
```bash
mkdir -p hands-on/m02/src/{types,schemas,parsers} hands-on/m02/tests
cd hands-on/m02
npm init -y
npm install @sinclair/typebox
npm install -D typescript @types/node ts-node vitest
```

#### Step 2: Konfigurasi `tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedIndexedAccess": true,
    "skipLibCheck": true,
    "outDir": "./dist"
  },
  "include": ["src/**/*", "tests/**/*"]
}
```

#### Step 3: Implementasi Brand Types (`src/types/brands.ts`)
```typescript
declare const BrandTag: unique symbol;
export type Brand<T, TName extends string> = T & { readonly [BrandTag]: TName };

export type PaymentId = Brand<string, 'PaymentId'>;
export type MerchantId = Brand<string, 'MerchantId'>;
export type CentsAmount = Brand<bigint, 'CentsAmount'>;
```

#### Step 4: Implementasi Skema TypeBox Terkompilasi (`src/schemas/payment.schema.ts`)
```typescript
import { Type, Static } from '@sinclair/typebox';
import { TypeCompiler } from '@sinclair/typebox/compiler';

export const RawPaymentInputSchema = Type.Object(
  {
    paymentId: Type.String({ format: 'uuid' }),
    merchantId: Type.String({ minLength: 8, maxLength: 20 }),
    amount: Type.Integer({ minimum: 100 }), // Min $1.00
    currency: Type.Union([Type.Literal('IDR'), Type.Literal('USD'), Type.Literal('SGD')]),
  },
  { additionalProperties: false }
);

export type RawPaymentInput = Static<typeof RawPaymentInputSchema>;

// Compile saat modul di-load
export const CompiledPaymentValidator = TypeCompiler.Compile(RawPaymentInputSchema);
```

#### Step 5: Implementasi Parser Domain Boundary (`src/parsers/payment.parser.ts`)
```typescript
import { RawPaymentInput, CompiledPaymentValidator } from '../schemas/payment.schema.js';
import { PaymentId, MerchantId, CentsAmount } from '../types/brands.js';

export interface ValidatedPaymentDomain {
  readonly paymentId: PaymentId;
  readonly merchantId: MerchantId;
  readonly amount: CentsAmount;
  readonly currency: 'IDR' | 'USD' | 'SGD';
  readonly createdAt: Date;
}

export function parsePaymentPayload(raw: unknown): ValidatedPaymentDomain {
  if (!CompiledPaymentValidator.Check(raw)) {
    const errorIterator = CompiledPaymentValidator.Errors(raw);
    const firstError = errorIterator.First();
    throw new Error(`VALIDATION_ERROR: [${firstError?.path}] ${firstError?.message}`);
  }

  const valid = raw as RawPaymentInput;

  return Object.freeze({
    paymentId: valid.paymentId as PaymentId,
    merchantId: valid.merchantId as MerchantId,
    amount: BigInt(valid.amount) as CentsAmount,
    currency: valid.currency,
    createdAt: new Date(),
  });
}
```

#### Step 6: Entry Point Eksekusi (`src/index.ts`)
```typescript
import { parsePaymentPayload } from './parsers/payment.parser.js';

try {
  const untrustedInput = {
    paymentId: 'c2e99e4d-720a-4286-905f-7ec41bc2c2be',
    merchantId: 'MERCHANT_99823',
    amount: 15000,
    currency: 'IDR',
  };

  const domainModel = parsePaymentPayload(untrustedInput);
  console.log('✅ Parsed successfully into Domain Model:', domainModel);
} catch (error) {
  console.error('❌ Validation Failed:', (error as Error).message);
}
```

---

### 13. Exercise

#### Level 1 (Easy): Recursive Node Validator
- **Tantangan:** Buat skema TypeBox untuk struktur data *Category Tree* (Menu navigasi bersarang).
- **Spesifikasi:** Setiap node memiliki properti `id` (string), `name` (string), dan opsional `subcategories` yang berisi *array* dari node itu sendiri. Batasi kedalaman rekursi maksimal 3 tingkat pada fungsi validasinya.

#### Level 2 (Medium): Polymorphic Event Envelope Parser
- **Tantangan:** Bangun parser skema untuk multi-tenant webhooks.
- **Spesifikasi:** Buat union skema dengan diskriminator properti `eventType`:
  1. `USER_SIGNUP`: Memiliki field `userId` dan `email`.
  2. `ORDER_COMPLETED`: Memiliki field `orderId`, `totalAmountInCents`, dan `itemsCount`.
  3. `PAYMENT_REFUNDED`: Memiliki field `refundId`, `originalPaymentId`, dan `reason`.
- Parser harus mengonversi payload string JSON mentah dan mengembalikan discriminated union yang sudah di-*brand* secara semantik.

#### Level 3 (Hard): Zero-Allocation Fast JSON Parser with String Slice
- **Tantangan:** Rancang validasi parser berbasis stream untuk Node.js `Readable` stream yang memproses format NDJSON (Newline Delimited JSON).
- **Spesifikasi:**
  1. Hindari pemuatan seluruh string berkas ke memori sekaligus.
  2. Parsing baris per baris menggunakan Buffer chunk slicing.
  3. Validasi skema setiap baris secara langsung menggunakan TypeCompiler tanpa mengalokasikan object wrapper baru kecuali baris tersebut terbukti valid.
  4. Agregasikan metrics total baris valid dan baris gagal (beserta alasannya) tanpa memicu crash proses (*unhandled rejection*).

---

### 14. Challenge

**Skenario Arsitektur:** Anda adalah Principal Architect pada perusahaan broker saham berfrekuensi tinggi. Sistem Anda menerima feed order eksekusi dari berbagai gateway via WebSocket dengan kapasitas beban puncak **100.000 transaksi/detik per instance**.

**Kebutuhan Teknis:**
1. **Dynamic Schema Hot-Reloading:** Exchange partner sewaktu-waktu memperbarui skema versi (misal v1 ke v2 dengan penambahan field settlement microsecond) tanpa toleransi restart server (*zero-downtime*). Buat registry validator yang mampu menukar instance validator JIT secara atomic tanpa mengunci (*non-blocking*) thread event loop.
2. **Strict Latency Budget:** Waktu alokasi untuk pengecekan validasi skema dan parsing ke domain entity tidak boleh melebihi **0.05ms (50 microsecond) pada P99**.
3. **Safety & Zero Pollution:** Objek yang divalidasi tidak boleh menyertakan prototype warisan JavaScript (`Object.prototype`) untuk meniadakan vector serangan prototype pollution.
4. **Invariant Constraints:** 
   - `price` (Price Tick) harus kelipatan dari tick value tertentu yang dimuat secara dinamis dari config cache.
   - `quantity` harus bilangan bulat genap positif.
   - Menggunakan Brand Types ketat untuk membedakan antara `OrderId`, `ClientOrderId`, dan `ExecutionReportId`.

**Deliverable:**
Dokumentasikan rancangan arsitektur, buat source code lengkap mesin registry validator, serta skrip benchmark latency percentile (P50, P90, P99) menggunakan module Node.js bawaan `perf_hooks`.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Mengapa instruksi `const user = payload as User;` sama sekali tidak menyediakan proteksi runtime keamanan tipe data di Node.js?
2. Apa perbedaan filosofis mendasar antara konsep "Validasi" (*Boolean Type Checking*) dan "Parsing" (*Parse, Don't Validate*)?
3. Mengapa teknik *Branded Type* membutuhkan simbol unik (`unique symbol`) alih-alih hanya property string biasa?
4. Mengapa runtime validator berbasis JIT compilation seperti TypeBox umumnya jauh lebih kencang dibanding functional parser berbasis chaining function seperti Zod?
5. Mengapa opsi skema `additionalProperties: false` sangat krusial dalam pertahanan *defense-in-depth* sistem aplikasi backend?

#### Pertanyaan Intermediate
6. Bagaimana modifikasi bentuk objek (*Shape/Hidden Class*) yang dilakukan oleh validator (misalnya operasi `delete payload.unknownProperty`) dapat menyebabkan deoptimasi performa pada engine V8?
7. Apa yang dimaksud dengan *Monomorphic Inline Cache*, dan bagaimana cara menstrukturkan return value parser agar status monomorfik ini tetap terjaga?
8. Bagaimana eksploitasi Regular Expression Denial of Service (ReDoS) terjadi di dalam parser skema runtime, dan langkah konkrit apa yang dapat diambil untuk memitigasinya?
9. Di situasi lingkungan komputasi seperti apa mesin validasi runtime berbasis kompilasi fungsi dinamis (`new Function()`) akan ditolak atau gagal dijalankan?
10. Bagaimana cara menangani transformasi string ISO 8601 (`"2026-03-31T00:00:00Z"`) menjadi native instance `Date` tanpa membongkar keselarasan inferensi tipe TypeScript?

#### Skenario Kasus Produksi
11. **Kasus 1:** Sistem microservice Anda mengalami lonjakan penggunaan CPU hingga 100% dan latensi melonjak tajam setelah menambahkan validasi payload menggunakan Zod pada endpoint yang memproses data berukuran 10MB berisi 100.000 array of objects. Apa root cause dari masalah ini dan bagaimana Anda merancang solusinya tanpa mengubah skema bisnis?
12. **Kasus 2:** Sebuah financial core banking ledger mendeteksi data korup di mana sebuah transaksi memiliki saldo `NaN` yang lolos masuk ke database PostgreSQL, padahal terdapat guard runtime `if (req.body.amount)`. Bagaimana nilai `NaN` bisa menembus proteksi tersebut dan bagaimana rancangan guard skema yang benar?
13. **Kasus 3:** Pada integrasi Kafka consumer, ditemukan bahwa message payload yang tidak valid menyebabkan consumer thread terus-menerus melakukan retry tanpa henti (*infinite retry loop*), menyebabkan partisi macet total. Bagaimana Anda mendesain arsitektur ingress validasi yang aman terhadap skenario corrupt poison pill message?

---

#### Kunci Jawaban & Rationale Evaluasi

##### Jawaban Basic
1. **Rationale:** Kompilator TypeScript menghapus (*erases*) seluruh tipe statis saat mentranspilasi kode ke JavaScript. `as User` hanyalah casting untuk membungkam kompilator TypeScript; saat runtime JavaScript dieksekusi, tidak ada instruksi CPU yang mengecek apakah payload benar-benar memiliki field yang sesuai dengan `User`.
2. **Rationale:** Validasi hanya menjawab pertanyaan "Apakah data ini valid?" (True/False) tanpa merestrukturisasi tipe data pada sistem, sehingga program masih memegang referensi ke raw data tak terpercaya. Parsing menjawab "Bagaimana cara merepresentasikan data mentah ini ke tipe domain yang terjamin?", mengembalikan objek model baru dengan penegakan tipe ketat dan invariant yang terbukti.
3. **Rationale:** TypeScript menggunakan *structural type system*. Jika kita mendefinisikan brand hanya dengan string sederhana (misal `{ __brand: 'UserId' }`), maka objek lain yang secara kebetulan memiliki properti string yang sama akan dianggap kompatibel secara struktural. Penggunaan `unique symbol` menjamin identitas tipe tersebut unik secara global dan tidak dapat diduplikasi secara tidak sengaja.
4. **Rationale:** Zod mengeksekusi sekumpulan fungsi validator secara rekursif melalui AST interpretatif serta mengalokasikan object context error pada tiap langkah traversal. TypeBox mengompilasi representasi JSON Schema menjadi blok string kode JavaScript murni menggunakan `new Function()`, memungkinkan V8 mengeksekusinya dalam satu branch pipeline monomorfik yang langsung di-inline oleh TurboFan.
5. **Rationale:** Menolak field ekstra mencegah *Mass Assignment Attack* (misal penyerang menyelipkan `isAdmin: true` pada form update profil) serta mencegah *Object Prototype Pollution* melalui inject properti terlarang seperti `__proto__` atau `constructor`.

##### Jawaban Intermediate
6. **Rationale:** V8 memetakan struktur properti objek ke memori internal menggunakan *Hidden Classes (Shapes)*. Menggunakan operator `delete` atau menambahkan properti baru secara bertahap memutus rantai transisi Shape yang sudah ada dan memaksa V8 mengalihkan objek tersebut ke *Dictionary Mode* (hash table lambat), merusak kapabilitas TurboFan untuk melakukan inlining optimasi.
7. **Rationale:** Monomorphic IC adalah kondisi di mana suatu titik pemanggilan (*call site*) fungsi hanya pernah melihat tepat 1 tipe *Shape* objek. Cara menjaga kestabilannya adalah dengan memastikan fungsi parser selalu mengembalikan objek literal baru yang memiliki urutan kunci properti dan tipe data yang persis sama pada setiap pemanggilan.
8. **Rationale:** Terjadi ketika regex yang digunakan mengandung grup yang saling tumpang tindih (*overlapping evaluation groups*) dengan pengulangan bertingkat (contoh `(a+)+$`). Ketika diberikan string masukan jahat yang hampir cocok tetapi diakhiri karakter berbeda, engine regex backtrack mengevaluasi seluruh permutasi eksponensial ($O(2^n)$), mengunci Node.js Event Loop. Mitigasi: Hindari *nested quantifiers*, gunakan validator panjang string (`maxLength`), dan terapkan validasi DFA.
9. **Rationale:** Di lingkungan komputasi dengan Content Security Policy (CSP) ketat yang melarang evaluasi string dinamis (`unsafe-eval`), atau platform serverless edge worker tertentu (seperti Cloudflare Workers dengan mode isolasi keamanan ketat) di mana pemanggilan `new Function()` atau `eval()` diblokir secara eksplisit pada level runtime V8 sandbox.
10. **Rationale:** Menggunakan kombinasi Custom Transforms atau Decoder. Pada TypeBox dapat menggunakan ekstensi `Type.Transform`, atau pada Valibot/Zod menggunakan method `.transform((val) => new Date(val))`. Dalam sistem statis murni, skema ingress memvalidasi string regex ISO-8601, kemudian mapping step mentransformasikan data tersebut menjadi properti bertipe `Date` pada objek domain baru.

##### Jawaban Skenario Kasus Produksi
11. **Solusi:**
    - *Root Cause:* Skema Zod melakukan iterasi fungsional mendalam untuk tiap elemen pada 100.000 item. Ini menciptakan ratusan ribu objek konteks alokasi error/hasil per parsing, memicu GC Thrashing (Stop-The-World Scavenger/Mark-Sweep) yang menahan event loop.
    - *Arsitektur Solusi:*
      1. Ganti mesin parsing per-elemen menjadi TypeBox/ArkType yang telah dikompilasi secara JIT.
      2. Jangan parsing seluruh array 100.000 item secara monolitik. Gunakan stream processing via pipeline JSON streaming parser (misal `stream-json`) untuk memvalidasi data chunk per chunk (batching misal per 500 item), melepaskan kembali memori chunk lama ke GC secara inkremental.
12. **Solusi:**
    - *Root Cause:* Tipe data JavaScript `typeof NaN === 'number'`. Guard sederhana `if (req.body.amount)` bernilai `false` jika amount adalah `0` (falsy bug), namun jika amount dikirim sebagai object/string yang menghasilkan `NaN` saat parsing matematika, pengecekan yang tidak teliti atau logic bypass dapat meloloskan nilai ini jika hanya memeriksa `undefined`.
    - *Arsitektur Solusi:*
      Definisikan validasi strict invariant:
      ```typescript
      function parseAmount(val: unknown): CentsAmount {
        if (typeof val !== 'number' || !Number.isFinite(val) || Number.isNaN(val) || val <= 0) {
          throw new TypeError('INVALID_NUMERIC_AMOUNT');
        }
        return val as CentsAmount;
      }
      ```
13. **Solusi:**
    - *Root Cause:* Exception validasi skema dilemparkan (*thrown*) secara telanjang tanpa penanganan status kegagalan deterministik, sehingga Kafka Consumer menganggap terjadi transient system failure dan mencoba memproses ulang pesan yang sama selamanya (*poison pill*).
    - *Arsitektur Solusi:*
      Terapkan pola *Error Classification & Dead Letter Queue (DLQ)*:
      1. Pisahkan error ke dalam dua kategori: *Recoverable/Transient* (misal DB timeout, network failure) dan *Non-Recoverable/Poison* (misal schema violation, checksum mismatch).
      2. Tangkap error validasi di tingkat ingress worker consumer; jika teridentifikasi sebagai *Non-Recoverable*, langsung commit offset Kafka untuk pesan tersebut agar partisi tidak macet.
      3. Reroute payload rusak beserta error trace stack terenkapsulasi ke dalam topic Kafka terpisah (`ledger-entries-dlq`) untuk diaudit oleh tim operasional secara asinkron.

---

### 16. Summary

1. **Boundary Isolation:** Batas eksternal aplikasi Node.js adalah area tanpa jaminan tipe (*zero-trust boundary*). Runtime validation bukan fitur opsional, melainkan fondasi integritas arsitektural.
2. **Parse, Don't Validate:** Jauhi casting `as T`. Gunakan paradigma parsing untuk memverifikasi bentuk data mentah dan mentransformasikannya menjadi entitas domain *immutable* yang diperkuat oleh *Branded Types*.
3. **Engine Selection Matters:**
   - Gunakan **TypeBox** saat memproses sistem ber-throughput tinggi (microservice ingress, processing queue besar) untuk memanfaatkan kompilasi skema berbasis JIT monomorfik V8.
   - Gunakan **Valibot** saat membangun aplikasi client-facing atau edge computing yang memprioritaskan *bundle size* kecil dan tree-shaking optimal.
   - Gunakan **Zod** untuk aplikasi general backend/fullstack di mana kenyamanan Developer Experience (DX) lebih diutamakan daripada batas ekstrem latensi sub-milidetik.
4. **V8 Optimization Awareness:** Jaga stabilitas *Hidden Classes* dengan menolak mutasi properti dinamis via `delete` atau penambahan properti baru acak pada runtime object untuk mencegah degradasi performa ke level megamorphic dictionary mode.