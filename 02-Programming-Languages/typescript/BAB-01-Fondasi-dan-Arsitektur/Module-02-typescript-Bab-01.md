# Kurikulum Rekayasa Perangkat Lunak Enterprise: TypeScript
## Bab 01: Fondasi dan Arsitektur
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, *Senior/Staff Software Engineer* diharapkan mampu:
- **Menganalisis Internal Kompiler TypeScript (`tsc`)**: Membedah dan mengoptimalkan lima tahapan *pipeline* internal kompiler (*Scanner*, *Parser*, *Binder*, *Checker*, *Emitter*).
- **Menguasai Teori Type System Lanjutan**: Menerapkan konsep *subtyping*, *structural compatibility*, serta aturan *variance* (*covariance*, *contravariance*, *invariance*, dan *bivariance*) pada arsitektur API tingkat enterprise.
- **Mengeksekusi *Type-Level Metaprogramming***: Membangun sistem tipe yang *Turing-complete* menggunakan *distributive conditional types*, *mapped types*, *template literal types*, dan *recursive type evaluation*.
- **Merancang Arsitektur Monorepo Skala Besar**: Mengonfigurasi *Project References*, *Incremental Builds*, dan *Composite Projects* untuk memangkas waktu kompilasi CI/CD dari skala menit ke detik.
- **Mengeliminasi *Type Pollution* & Kebocoran Runtime**: Mengimplementasikan *Nominal Typing* (*Branded Types*) dan *Zero-Cost Type Narrowing* guna menjamin integritas *domain model* pada sistem finansial/transaksional.

---

### 2. Prerequisite
Sebelum mendalami modul ini, engineer wajib memiliki pemahaman mendalam tentang:
- Arsitektur JavaScript Engine (V8/SpiderMonkey: Call Stack, Heap, Event Loop, JIT compilation, Hidden Classes).
- Dasar-dasar TypeScript (Primitive types, basic interfaces, generic functions, dasar `tsconfig.json`).
- Teori Kompilasi Dasar (Konsep Abstract Syntax Tree/AST, Lexical Analysis, dan Symbol Resolution).
- Pengalaman praktis menggunakan Node.js runtime environment (v18.x LTS atau lebih baru) dan *package manager modern* (`pnpm` direkomendasikan).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Pipeline Internal Kompiler TypeScript (`tsc`)
TypeScript compiler tidak sekadar melakukan transpiliasi teks ke teks, melainkan mengeksekusi *multi-phase compilation pipeline*:

```
Source Code (.ts)
       │
       ▼
 ┌───────────┐
 │  Scanner  │ ──► Stream of Tokens
 └───────────┘
       │
       ▼
 ┌───────────┐
 │  Parser   │ ──► Abstract Syntax Tree (AST) + SourceFile Node
 └───────────┘
       │
       ▼
 ┌───────────┐
 │  Binder   │ ──► Symbol Table & Flow Nodes (Scope Graph Creation)
 └───────────┘
       │
       ▼
 ┌───────────┐
 │  Checker  │ ──► Type Checking, Semantic Validation, Relation Checks
 └───────────┘
       │
       ▼
 ┌───────────┐
 │  Emitter  │ ──► JavaScript Output (.js), Declaration Files (.d.ts), Source Maps (.map)
 └───────────┘
```

1. **Scanner (`scanner.ts`)**: Menerima *raw character stream* dari kode sumber dan menghasilkan token-token leksikal (*SyntaxKind enum*). Scanner mengabaikan *trivia* (spasi, komentar) untuk pemrosesan semantik inti.
2. **Parser (`parser.ts`)**: Mengonsumsi token dari *Scanner* untuk membentuk *Abstract Syntax Tree* (AST). Setiap simpul pada AST merepresentasikan konstruksi sintaksis formal (`Node`, `Statement`, `Expression`) dan mempertahankan referensi posisi dalam *SourceFile*.
3. **Binder (`binder.ts`)**: Fase kritis di mana *AST Node* dihubungkan dengan *Symbol*. *Symbol* adalah unit semantik dasar dalam sistem tipe TypeScript yang merepresentasikan entitas ber-nama (variabel, fungsi, class, interface). Binder membangun deklarasi kontainer (*Scope Table*) dan mengonstruksi *Control Flow Graph* (CFG) awal tanpa melakukan evaluasi tipe sama sekali.
4. **Checker (`checker.ts`)**: Jantung dari TypeScript (file monolitik berukuran >40.000 baris kode). Checker melakukan:
   - Penyelidikan semantik (*Semantic Diagnostics*).
   - Penguraian relasi tipe (*Type Relations*: identity, subtype, assignment compatibility).
   - Evaluasi komputasi tipe kompleks (*Conditional Types*, *Type Inference* melalui inferensi kuisit Uni-directional/Bi-directional).
   - Checker bekerja secara *lazy-on-demand*: tipe hanya dihitung saat benar-benar direferensikan.
5. **Emitter (`emitter.ts`)**: Mengonversi AST kembali menjadi teks representasi runtime (JavaScript ESNext/ES5) dan/atau file `.d.ts`. Seluruh anotasi tipe, deklarasi interface, dan generic types dihapus (*type erasure*), kecuali jika sintaks tersebut menghasilkan emisi runtime (seperti `enum` atau `namespaces`).

#### 3.2 Variance: Teori Subtyping Komputasional
Relasi subtipe formal dinotasikan dengan $A \le B$ (dibaca: $A$ adalah subtipe dari $B$, artinya nilai bertipe $A$ aman disubstitusikan ke variabel yang mengharapkan $B$). *Variance* mendeskripsikan bagaimana relasi subtyping antara tipe basis ($T \le U$) diproyeksikan ke tipe kompleks/komposit $F<T>$.

| Aturan Variance | Definisi Matematis | Konteks dalam TypeScript |
| :--- | :--- | :--- |
| **Covariance** | $T \le U \implies F<T> \le F<U>$ | Nilai kembalian fungsi (*Return types*), properti objek *read-only*. |
| **Contravariance** | $T \le U \implies F<U> \le F<T>$ | Parameter fungsi saat `--strictFunctionTypes` diaktifkan. |
| **Invariance** | $F<T> \le F<U} \iff T = U$ | Properti yang mutable secara dua arah (Read/Write) pada target tertentu. |
| **Bivariance** | $T \le U \implies F<T> \le F<U} \land F<U> \le F<T>$ | Parameter *Method Declaration* (tanpa `--strictFunctionTypes` atau pada konteks `method()` sintaks). |

Visualisasi Contravariance pada Fungsi:
Jika kita membutuhkan sebuah fungsi yang dapat menangani `Dog`, kita dapat memberikan fungsi yang dapat menangani `Animal` (karena `Dog` adalah `Animal`), tetapi kita **tidak boleh** memberikan fungsi yang hanya dapat menangani `Terrier` (karena ia akan gagal jika diberi `Bulldog`).

$$Animal \ge Dog \implies (Animal \to void) \le (Dog \to void)$$

---

### 4. Why & What

- **Mengapa Structural Typing (Duck Typing) alih-alih Nominal Typing?**
  JavaScript natively bersifat dinamis dan *shape-based*. TypeScript mengadopsi *Structural Subtyping*: jika tipe `X` memiliki setidaknya semua properti yang didefinisikan dalam tipe `Y` dengan tipe yang kompatibel, maka `X` kompatibel dengan `Y`. Keuntungannya adalah interoperabilitas tanpa overhead boilerplate OOP nominal. Namun, kelemahannya adalah *accidental compatibility* (misal: `UserId` bertipe `string` dan `OrderId` bertipe `string` dapat tertukar tanpa error kompiler).
- **Apa itu Type-Level Metaprogramming?**
  Sistem tipe TypeScript adalah bahasa pemodelan deklaratif yang terbukti *Turing-complete*. Artinya, manipulasi logika, percabangan (`extends ? :`), iterasi (rekursi tipe), dan pencocokan pola (*pattern matching* via `infer`) dapat dievaluasi sepenuhnya saat kompilasi tanpa meninggalkan jejak runtime sebesar 0 byte.
- **Mengapa Enterprise Memerlukan Strict Project References?**
  Pada basis kode monorepo raksasa (>1 juta LOC), menjalankan evaluasi tipe penuh via satu proses `tsc` tunggal akan menyebabkan *out-of-memory* (OOM) dan siklus kompilasi yang lambat. Arsitektur modular menggunakan *Project References* mendistribusikan batasan kompilasi ke unit-unit diskrit yang menghasilkan artefak `.tsbuildinfo` dan `.d.ts`, memungkinkan *caching* deterministik paralel.

---

### 5. How (Workflow Detail)

1. **Inisialisasi Proyek Multi-Target**: Konfigurasikan file root `tsconfig.json` dengan flag `noEmit: true` dan daftarkan submodule di array `references`.
2. **Modularisasi Sub-Proyek**: Setiap sub-library memiliki `tsconfig.json` independen dengan flag:
   - `"composite": true`
   - `"declaration": true`
   - `"declarationMap": true`
   - `"moduleResolution": "NodeNext"` (atau `"Bundler"`)
3. **Eksekusi Kompiler**: Gunakan perintah `tsc --build` (atau `tsc -b`) yang mengaktifkan *builder engine* TypeScript untuk menganalisis graf dependensi dependensi secara topologis, mengompilasi package terdalam terlebih dahulu, dan melompati paket yang *hash* deklarasinya tidak berubah.

---

### 6. Analogy & Diagram ASCII

#### 6.1 Analogi Kontainer Kargo (Variance)
- **Tipe Basis**: `Animal` (Kotak Umum), `Dog` (Kotak Khusus). Semua `Dog` adalah `Animal`.
- **Covariance (Output)**: Penjual Kargo yang menjanjikan `Animal` boleh mengirimkan `Dog` ke pembeli. Pembeli tetap puas karena `Dog` adalah `Animal`.
- **Contravariance (Input)**: Dokter hewan yang mampu mengobati sembarang `Animal` dijamin mampu mengobati `Dog`. Namun, spesialis `Dog` tidak bisa dioperasikan untuk kontrak umum dokter `Animal` (karena berisiko diberi `Cat`).

#### 6.2 Diagram Resolusi Graph Proyek (Monorepo)

```
                    ┌─────────────────────────┐
                    │    tsconfig.base.json   │
                    └─────────────────────────┘
                                 ▲
           ┌─────────────────────┴─────────────────────┐
           │                                           │
┌──────────────────────┐                    ┌──────────────────────┐
│  core-domain/        │                    │  common-types/       │
│  tsconfig.json       │                    │  tsconfig.json       │
│  (composite: true)   │                    │  (composite: true)   │
└──────────────────────┘                    └──────────────────────┘
           ▲                                           ▲
           │ references                                │ references
           └─────────────────────┬─────────────────────┘
                                 │
                    ┌─────────────────────────┐
                    │  services/payment-api   │
                    │  tsconfig.json          │
                    │  (tsc --build target)   │
                    └─────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Variance & Nominal Branding

```typescript
// --- NOMINAL BRANDING TECHNIQUE ---
declare const BrandSymbol: unique symbol;

export type Brand<T, TBrand extends string> = T & {
  readonly [BrandSymbol]: TBrand;
};

// Domain Types yang tidak dapat tertukar secara struktural
export type UserId = Brand<string, "UserId">;
export type AccountId = Brand<string, "AccountId">;

function createUserId(id: string): UserId {
  // Safe downcasting via unknown di boundary layer
  return id as UserId;
}

function createAccountId(id: string): AccountId {
  return id as AccountId;
}

let user = createUserId("usr_109283");
let account = createAccountId("acc_884920");

// user = account; 
// COMPILE ERROR: Type 'AccountId' is not assignable to type 'UserId'.
// Type '"AccountId"' is not assignable to type '"UserId"'.

// --- VARIANCE DEMONSTRATION ---
class Animal { declare private _animalKind: string; }
class Dog extends Animal { declare private _dogBreed: string; }

type Producer<T> = () => T;              // Covariant
type Consumer<T> = (param: T) => void;    // Contravariant

let produceAnimal: Producer<Animal> = () => new Animal();
let produceDog: Producer<Dog> = () => new Dog();

// Covariance Check: Dog <= Animal -> Producer<Dog> <= Producer<Animal>
produceAnimal = produceDog; // OK

let consumeAnimal: Consumer<Animal> = (a: Animal) => {};
let consumeDog: Consumer<Dog> = (d: Dog) => {};

// Contravariance Check: Dog <= Animal -> Consumer<Animal> <= Consumer<Dog>
consumeDog = consumeAnimal; // OK
// consumeAnimal = consumeDog; 
// COMPILE ERROR with --strictFunctionTypes: 
// Type 'Consumer<Dog>' is not assignable to type 'Consumer<Animal>'.
```

#### 7.2 Practical Example: Enterprise-Grade Type-Safe Event Bus System

Berikut adalah implementasi sistem *Event-Driven Messaging Engine* dengan *Type Narrowing*, validasi skema berbasis *Mapped Types*, serta pemrosesan *Recursive Deep Readonly*:

```typescript
// ============================================================================
// CORE TYPE-LEVEL UTILITIES
// ============================================================================

export type DeepReadonly<T> = T extends Function | boolean | number | string | symbol | bigint
  ? T
  : T extends Array<infer U>
  ? ReadonlyArray<DeepReadonly<U>>
  : T extends Map<infer K, infer V>
  ? ReadonlyMap<DeepReadonly<K>, DeepReadonly<V>>
  : T extends Set<infer M>
  ? ReadonlySet<DeepReadonly<M>>
  : { readonly [P in keyof T]: DeepReadonly<T[P]> };

// ============================================================================
// EVENT DEFINITIONS & SYSTEM SCHEMA
// ============================================================================

export interface DomainEvent<TName extends string, TPayload> {
  readonly eventName: TName;
  readonly timestamp: number;
  readonly payload: TPayload;
}

export type UserRegisteredEvent = DomainEvent<
  "identity.user.registered",
  { readonly userId: string; readonly email: string; readonly role: "ADMIN" | "USER" }
>;

export type PaymentProcessedEvent = DomainEvent<
  "billing.payment.processed",
  { readonly transactionId: string; readonly amount: bigint; readonly currency: "USD" | "IDR" }
>;

export type OrderCancelledEvent = DomainEvent<
  "sales.order.cancelled",
  { readonly orderId: string; readonly reasonCode: number }
>;

// Registry terpusat seluruh domain event
export type SystemEventsRegistry =
  | UserRegisteredEvent
  | PaymentProcessedEvent
  | OrderCancelledEvent;

// ============================================================================
// TYPE-LEVEL QUERY ENGINES
// ============================================================================

// Extract payload berdasarkan nama event menggunakan Distributive Conditional Types
export type ExtractPayload<
  TEventRegistry extends DomainEvent<string, unknown>,
  TTargetName extends TEventRegistry["eventName"]
> = TEventRegistry extends { readonly eventName: TTargetName; readonly payload: infer P }
  ? P
  : never;

export type EventCallback<TPayload> = (payload: DeepReadonly<TPayload>) => Promise<void>;

// ============================================================================
// TYPE-SAFE BUS IMPLEMENTATION
// ============================================================================

export class EnterpriseEventBus<TRegistry extends DomainEvent<string, unknown>> {
  private handlers = new Map<string, Array<(payload: unknown) => Promise<void>>>();

  public subscribe<TEventName extends TRegistry["eventName"]>(
    eventName: TEventName,
    handler: EventCallback<ExtractPayload<TRegistry, TEventName>>
  ): void {
    const currentHandlers = this.handlers.get(eventName) ?? [];
    currentHandlers.push(handler as (payload: unknown) => Promise<void>);
    this.handlers.set(eventName, currentHandlers);
  }

  public async publish<TEventName extends TRegistry["eventName"]>(
    eventName: TEventName,
    payload: ExtractPayload<TRegistry, TEventName>
  ): Promise<void> {
    const registeredHandlers = this.handlers.get(eventName);
    if (!registeredHandlers || registeredHandlers.length === 0) {
      return;
    }

    // Freeze deep runtime object untuk enforcement immutable invariant
    const frozenPayload = Object.freeze({ ...payload }) as DeepReadonly<ExtractPayload<TRegistry, TEventName>>;

    await Promise.all(
      registeredHandlers.map((handler) =>
        handler(frozenPayload).catch((error: unknown) => {
          // Fallback isolation logging
          console.error(`Execution failure inside subscriber for event [${eventName}]`, error);
        })
      )
    );
  }
}

// ============================================================================
// INDUSTRIAL USAGE DEMO
// ============================================================================

async function bootstrap() {
  const bus = new EnterpriseEventBus<SystemEventsRegistry>();

  // Type-Safe Subscription: Type payload terinferensi otomatis dan presisi
  bus.subscribe("billing.payment.processed", async (payload) => {
    // Type checking valid: amount terdeteksi otomatis sebagai bigint
    console.log(`Payment confirmed: ${payload.transactionId} -> Amount: ${payload.amount.toString()}`);
    
    // ERROR COMPILATION PREVENTED:
    // payload.amount = 100n; // Error: Cannot assign to 'amount' because it is a read-only property.
  });

  // Valid dispatch
  await bus.publish("billing.payment.processed", {
    transactionId: "tx_01HDQ88XYZ",
    amount: 150000000n,
    currency: "IDR"
  });

  // COMPILE ERROR SINKRONISASI SCHEMA:
  // await bus.publish("identity.user.registered", {
  //   userId: "usr_99",
  //   email: "dev@enterprise.io",
  //   role: "SUPERADMIN" // Type '"SUPERADMIN"' is not assignable to type '"ADMIN" | "USER"'.
  // });
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Arsitektur Financial Ledger Transaksional
Pada sistem perbankan global (skala 50.000 transaksi per detik), representasi data uang dan mata uang tidak boleh terkompromi. Penggunaan `number` primitif menghasilkan *floating point error* (`0.1 + 0.2 !== 0.3`), dan ketidakhadiran validasi compile-time dapat menyebabkan akun mata uang asing tertukar (misal: nominal `USD` di-kreditkan ke rekening `IDR`).

#### Desain Solusi:
1. Implementasi *Branded Decimals* yang dibungkus dengan *zero-overhead custom types*.
2. State Machine Transaksi divalidasi via *Discriminated Unions* dengan *Exhaustiveness Checking* mutlak.

```typescript
// Tagging Nominal Khusus Currency
export type CurrencyCode = "USD" | "EUR" | "IDR" | "SGD";

export type MonetaryAmount<TCurrency extends CurrencyCode> = bigint & {
  readonly __currency: TCurrency;
  readonly __precisionMultiplier: 10000n; // Implicit 4 decimal places
};

// Nominal Constructor
export function toMonetaryAmount<TCurrency extends CurrencyCode>(
  baseUnits: bigint,
  currency: TCurrency
): MonetaryAmount<TCurrency> {
  return baseUnits as MonetaryAmount<TCurrency>;
}

// State Machine Transaksi Finansial
export type LedgerEntry =
  | {
      readonly status: "PENDING_AUTHORIZATION";
      readonly entryId: string;
      readonly holdExpiresAt: Date;
    }
  | {
      readonly status: "SETTLED";
      readonly entryId: string;
      readonly settledAt: Date;
      readonly batchReference: string;
    }
  | {
      readonly status: "REJECTED";
      readonly entryId: string;
      readonly rejectionCode: "INSUFFICIENT_FUNDS" | "AML_BLOCK" | "NETWORK_TIMEOUT";
      readonly failureDetails: string;
    };

// Exhaustive Reducer dengan Never Assertion
export function processLedgerTransition(entry: LedgerEntry): string {
  switch (entry.status) {
    case "PENDING_AUTHORIZATION":
      return `Entry ${entry.entryId} on hold until ${entry.holdExpiresAt.toISOString()}`;
    case "SETTLED":
      return `Entry ${entry.entryId} settled in batch ${entry.batchReference}`;
    case "REJECTED":
      return `Entry ${entry.entryId} rejected: ${entry.rejectionCode}`;
    default: {
      // Exhaustiveness check: Jika developer menambah status baru di LedgerEntry 
      // tanpa menanganinya di sini, baris di bawah ini akan melempar Compile Error.
      const _exhaustiveCheck: never = entry;
      throw new Error(`Unhandled ledger status: ${JSON.stringify(_exhaustiveCheck)}`);
    }
  }
}
```

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Nominal (Branded) Types** | Keamanan domain 100% absolut pada level compile-time; mencegah bug tertukarnya foreign-key/ID primitif; *zero runtime overhead*. | Memerlukan *type assertion casting* (`as BrandedType`) pada boundary runtime (saat menerima I/O atau mem-parsing JSON). |
| **Deep Mapped Recursive Types** | Jaminan imutabilitas tingkat dalam (*immutability enforcement*); audit tipe payload event otomatis. | Menaikkan kompleksitas Checker. Berpotensi memicu error `TS2589: Type instantiation is excessively deep and possibly infinite` pada kedalaman nested object ekstrem. |
| **`composite: true` & Project References** | Kompilasi sub-detik secara incremental; pembatasan modular boundary antar tim arsitektur. | Mengharuskan struktur konfigurasi kaku; dependensi siklikal antar-paket dilarang keras (*Circular References Forbidden*). |
| **`any` vs `unknown`** | `any` menonaktifkan checker total (cepat ditulis saat prototyping). | `any` merusak sound typing, menyebar seperti virus ke pemanggil fungsi (*type poison*). `unknown` memaksa *narrowing* eksplisit tetapi membutuhkan runtime checks. |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: Kesalahan Bivariance pada Deklarasi Method Interface
```typescript
// SALAH: Method syntax menghasilkan bivariant parameter check (unsafe!)
interface ProcessorMethod {
  handle(arg: string | number): void;
}

// BENAR: Property syntax dengan function signature memberlakukan contravariance penuh
interface ProcessorProperty {
  readonly handle: (arg: string | number) => void;
}
```
*Troubleshooting*: Selalu gunakan sintaks properti fungsional `(x: T) => R` alih-alih `x(p: T): R` di dalam interface jika sistem Anda mewajibkan contravariant parameter checks di bawah flag `--strictFunctionTypes`.

#### Kasus 2: Distributive Union Trap pada Generics
Ketika mengoperasikan tipe kondisional terhadap argumen generic *naked*, tipe bersatu (*union*) akan terdistribusi secara otomatis.

```typescript
type ToArrayIncorrect<T> = T extends any ? T[] : never;
type TestUnion = ToArrayIncorrect<string | number>; 
// Hasil: string[] | number[] (Terdistribusi!)

// SOLUSI: Bungkus dengan tuple [T] untuk menonaktifkan distributive behavior
type ToArrayCorrect<T> = [T] extends [any] ? T[] : never;
type TestDirect = ToArrayCorrect<string | number>; 
// Hasil: (string | number)[]
```

#### Kasus 3: Diagnosa dan Resolusi Compiler Performance Choke
Jika kompilasi terasa lambat:
1. Jalankan `tsc --diagnostics` untuk melihat alokasi memori Checker dan jumlah I/O files.
2. Jalankan `tsc --generateTrace traceDir` untuk menghasilkan log analisis Chrome DevTools tracing.
3. Buka `chrome://tracing` dan telusuri simpul evaluasi tipe terpanjang untuk mengidentifikasi tipe rekursif yang tidak stabil.

---

### 11. Best Practices (Production Checklist)

1. **`tsconfig.json` Base Strict Requirements**:
   - `strict: true` (Wajib mengaktifkan seluruh turunan: `noImplicitAny`, `strictNullChecks`, dll.)
   - `exactOptionalPropertyTypes: true` (Membedakan properti eksplisit `undefined` dengan absennya properti)
   - `noUncheckedIndexedAccess: true` (Mengubah lookup array `arr[i]` menjadi `T | undefined`)
   - `noImplicitOverride: true` (Mencegah modifikasi method class turunan tanpa keyword `override`)
   - `isolatedModules: true` (Memastikan kompatibilitas bundler seperti ESBuild/SWC)
2. **Arsitektur Batasan Domain**:
   - Terapkan nominal types untuk semua entitas ID: `UserId`, `TenantId`, `OrganizationId`.
   - Gunakan `satisfies` operator alih-alih type-casting `as` untuk memvalidasi literal terhadap tipe konfigurasi tanpa memperlebar (*widening*) tipe data asal.
   - Jangan pernah mengekspor generic rekursif tanpa terminating-condition guard.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum ini ke dalam direktori: `hands-on/m02/`

#### Langkah 1: Inisialisasi Workspace
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
pnpm init
```

#### Langkah 2: Konstruksi Arsitektur Project References
Buat file `hands-on/m02/tsconfig.base.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "isolatedModules": true,
    "skipLibCheck": true
  }
}
```

Buat modul domain `hands-on/m02/packages/core/tsconfig.json`:
```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "composite": true,
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src/**/*"]
}
```

Buat implementasi core `hands-on/m02/packages/core/src/index.ts`:
```typescript
declare const Brand: unique symbol;
export type Branded<T, B> = T & { readonly [Brand]: B };

export type AggregateId = Branded<string, "AggregateId">;

export interface IAggregateRoot {
  readonly id: AggregateId;
  readonly version: bigint;
}

export function createAggregateId(id: string): AggregateId {
  if (!id || id.trim().length === 0) {
    throw new Error("AggregateId cannot be empty");
  }
  return id as AggregateId;
}
```

Buat aplikasi `hands-on/m02/packages/app/tsconfig.json`:
```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "composite": true,
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "references": [
    { "path": "../core" }
  ],
  "include": ["src/**/*"]
}
```

Buat consumer app `hands-on/m02/packages/app/src/index.ts`:
```typescript
import { createAggregateId, type IAggregateRoot } from "@enterprise/core";

export class OrderAggregate implements IAggregateRoot {
  public readonly id = createAggregateId("order_998471");
  public readonly version = 1n;
}

const order = new OrderAggregate();
console.log(`Aggregate Initialized: ${order.id} (v${order.version})`);
```

Buat `hands-on/m02/tsconfig.json` root orchestrator:
```json
{
  "files": [],
  "references": [
    { "path": "./packages/core" },
    { "path": "./packages/app" }
  ]
}
```

#### Langkah 3: Eksekusi Kompilasi Lanjutan
```bash
# Jalankan kompilasi terdistribusi incremental
npx tsc --build --verbose
```
*Verifikasi*: Periksa folder `dist/` pada masing-masing sub-paket untuk melihat output `.js`, `.d.ts`, `.d.ts.map`, dan `.tsbuildinfo`.

---

### 13. Exercise

#### Level: Easy
Implementasikan tipe kondisional `NonNullableProperties<T>` yang membuang kemungkinan `null` atau `undefined` dari seluruh nilai field milik sebuah objek, namun mempertahankan struktur keys aslinya.
- *Input*: `{ name: string | null; age?: number; metadata: undefined | { id: string } }`
- *Expected Output*: `{ name: string; age: number; metadata: { id: string } }`

#### Level: Medium
Buatlah tipe utilitas bernama `PathReporter<T>` menggunakan *Template Literal Types* rekursif yang mampu mengekstraksi seluruh alamat string navigasi properti (dot-notated paths) dari sebuah nested objek secara mendalam.
- *Input*:
  ```typescript
  type Schema = {
    user: {
      profile: {
        avatar: string;
      };
      settings: {
        theme: "light" | "dark";
      };
    };
    version: number;
  };
  ```
- *Expected Output*: `"user" | "user.profile" | "user.profile.avatar" | "user.settings" | "user.settings.theme" | "version"`

#### Level: Hard
Rancang type engine bernama `ValidateTransitions<TStates, TTransitions>` yang memvalidasi deklarasi State Machine. Tipe ini harus melempar error kompilasi jika terdapat transisi dari suatu state menuju target state yang tidak terdefinisi di dalam union `TStates`.
- *Constraint*: Selesaikan secara murni pada level tipe TypeScript tanpa bantuan library eksternal.

---

### 14. Challenge

**Skenario**: Anda memimpin tim infrastruktur inti pada perusahaan FinTech. Database ORM internal saat ini menghasilkan objek mentah tanpa type-safety dinamis saat relasi multi-tabel di-join.

**Tugas Arsitektur**:
Rancang antarmuka tipe generik `TypeSafeQueryBuilder<TEntity>` yang:
1. Memiliki method `.select(...)` yang menerima parameter rest keys dinamis (`...keys`).
2. Tipe kembalian dari method `.execute()` **hanya** memiliki properti yang secara eksplisit dimasukkan ke dalam method `.select()`.
3. Jika pemanggil memanggil `.select()` berulang kali (chaining), tipe hasil akhirnya harus merupakan gabungan (*intersection/merge*) dari seluruh field yang dipilih.
4. Jika developer memasukkan key yang tidak valid pada entity target, TypeScript harus menunjukkan *squiggled red line* error langsung pada argumen yang bersangkutan, bukan pada return type-nya.
5. Memiliki method `.join<TRelationName, TRelatedEntity>(...)` yang menyematkan relasi terkait ke dalam root query context, memperbolehkan nested selection berikutnya (`relation.nestedField`).

*Larangan*: Dilarang menggunakan assertion `any` di implementasi level tipe publik.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level (5 Soal)
1. Fase kompiler manakah dalam `tsc` yang bertanggung jawab langsung untuk mengasosiasikan AST Node dengan deklarasi struktural (Symbol Table)?
   - A. Scanner
   - B. Binder
   - C. Parser
   - D. Emitter
2. Manakah representasi variance yang valid untuk tipe parameter fungsi di bawah flag `--strictFunctionTypes`?
   - A. Covariant
   - B. Contravariant
   - C. Invariant
   - D. Bivariant
3. Sintaks apa yang digunakan untuk memisahkan evaluasi tipe komputasi tanpa meninggalkan jejak kode apa pun di JavaScript?
   - A. Abstract Class
   - B. Namespace
   - C. Type Alias / Interface
   - D. Enum
4. Apakah kegunaan flag `isolatedModules` dalam `tsconfig.json`?
   - A. Mempercepat proses checker dengan thread terpisah.
   - B. Memastikan setiap file dapat ditranspilasi secara aman oleh transpiler single-file non-typecheck (seperti Babel, ESBuild, atau SWC).
   - C. Memisahkan node_modules ke dalam container Docker tersendiri.
   - D. Mengisolasi memory heap kompiler agar tidak terjadi OOM.
5. Kapan sebuah mapped conditional type mendistribusikan union types?
   - A. Kapan pun generic digunakan.
   - B. Ketika tipe parameter generic yang diuji merupakan *naked type parameter* (tidak dibungkus oleh array, tuple, atau tipe lain).
   - C. Hanya jika flag `--strictNullChecks` dimatikan.
   - D. Hanya jika menggunakan kata kunci `interface`.

#### Intermediate Level (5 Soal)
6. Diberikan kode berikut:
   ```typescript
   type Box<T> = { value: T };
   ```
   Secara default dalam TypeScript, apakah variance dari `Box<T>` terhadap `T`?
   - A. Contravariant
   - B. Covariant
   - C. Bivariant
   - D. Invariant
7. Mengapa nominal typing penting pada identifier entitas berskala enterprise?
   - A. Karena nominal typing mempercepat eksekusi V8 engine di runtime.
   - B. Karena nominal typing mencegah kesalahan transfer data antar-domain yang tipe primitif dasarnya identik (mencegah bug substitusi tak disengaja).
   - C. Karena JavaScript natively mendukung nominal typing via keyword `package`.
   - D. Agar ukuran bundle code `.js` menjadi lebih padat.
8. Apa dampak pengaktifan flag `exactOptionalPropertyTypes: true`?
   - A. Properti bertanda `?` tidak dapat diset nilainya menjadi `undefined` secara eksplisit, melainkan properti tersebut harus diisi dengan tipe target atau tidak didefinisikan sama sekali di dalam objek.
   - B. Mengharuskan seluruh properti diisi tanpa terkecuali.
   - C. Mengubah seluruh field opsional menjadi tipe `null`.
   - D. Mencegah penggunaan default value pada function arguments.
9. Apa perbedaan esensial antara tipe `unknown` dan `any`?
   - A. `unknown` adalah tipe primitif sedangkan `any` adalah tipe objek.
   - B. `any` mematikan seluruh verifikasi type checker, sedangkan `unknown` mewajibkan *narrowing* (type guard / assertion) sebelum propertinya dapat diakses secara aman.
   - C. `unknown` tidak dapat digunakan pada generic argument.
   - D. Tidak ada perbedaan; keduanya interchangeable.
10. Apa fungsi dari file artefak `.tsbuildinfo` yang dihasilkan pada composite build?
    - A. Berisi kode binary machine yang siap dipanggil oleh WebAssembly.
    - B. Berisi metadata hash dari dependensi AST dan deklarasi file untuk menentukan paket mana saja yang perlu dikompilasi ulang secara efisien pada build berikutnya.
    - C. Berisi profiling analitik memory crash untuk V8 profiler.
    - D. Berisi fallback source map jika file `.map` korup.

#### Production Scenario Cases (3 Soal)

11. **Skenario Kasus 1**:
    Sebuah aplikasi finansial monorepo berskala besar mengalami peningkatan durasi build CI/CD dari 2 menit menjadi 24 menit setelah penggabungan 40 paket baru. Saat diperiksa, seluruh sub-paket mereferensikan file sumber TypeScript `.ts` langsung dari paket lain melalui relative path (`../../packages/x/src/index.ts`).
    Langkah arsitektur apa yang **paling tepat dan fundamental** untuk mengatasi masalah degradasi performa kompilasi ini secara permanen?
    - A. Menaikkan batas alokasi memori Node.js via `--max-old-space-size=16384` di skrip build runner CI.
    - B. Mengonversi seluruh sub-paket menjadi *Composite Projects* (`composite: true`), memublikasikan deklarasi tipe (`.d.ts`), menyambungkan paket menggunakan *Project References*, dan mengganti script build menjadi `tsc --build`.
    - C. Mengganti semua tipe `interface` menjadi `type` alias.
    - D. Menambahkan flag `noCheck: true` di file `tsconfig.json` root.

12. **Skenario Kasus 2**:
    Tim Anda menemukan bug produksi di mana user secara tidak sengaja dapat mengakses balance akun milik nasabah lain. Setelah investigasi kode, ditemukan fungsi:
    ```typescript
    function transferFunds(sourceAccount: string, targetAccount: string, amount: number) { ... }
    ```
    Bug terjadi karena pemanggil fungsi secara keliru menukar posisi argumen pertama dan kedua (`transferFunds(targetAccount, sourceAccount, balance)`).
    Mekanisme compile-time native manakah yang paling elegan dan berbiaya runtime 0 (*zero-runtime cost*) untuk mengeliminasi potensi kesalahan ini secara mutlak pada masa mendatang?
    - A. Mengubah parameter menjadi `object` tunggal lalu menambahkan runtime check `typeof`.
    - B. Menerapkan *Branded / Flavor Types* (Nominal Typing) pada `sourceAccount` bertipe `SourceAccountId` dan `targetAccount` bertipe `TargetAccountId`.
    - C. Mengganti parameter `string` menjadi kelas runtime OOP `new AccountId()`.
    - D. Membuat Unit Test tambahan untuk setiap pemanggilan fungsi transfer.

13. **Skenario Kasus 3**:
    Saat mengompilasi sistem pesan bertingkat, Checker melempar pesan fatal: `TS2589: Type instantiation is excessively deep and possibly infinite`.
    Investigasi menemukan tipe rekursif berikut:
    ```typescript
    type Flatten<T> = T extends Array<infer U> ? Flatten<U> : T;
    ```
    Kondisi apa di lingkungan produksi yang memicu kompiler gagal mengevaluasi tipe tersebut hingga menyentuh rekursi batas atas (recursion limit)?
    - A. Mengoper variabel bertipe `any` atau `any[]` ke dalam generic `Flatten<T>`.
    - B. Array yang diproses memiliki lebih dari 100 elemen runtime.
    - C. File `.ts` tidak memiliki instruksi `export {}`.
    - D. Parameter tipe di-pass menggunakan interface dan bukan tipe primitif.

---

### Kunci Jawaban & Rasionalisasi Quiz

1. **B (Binder)**: Binder adalah fase yang bertanggung jawab membangun *Symbol Table* dan *Control Flow Graph* (CFG) awal dengan menautkan AST Node ke Symbol. Scanner hanya memecah token, Parser membangun AST tanpa relasi simbolik, dan Emitter mencetak output.
2. **B (Contravariant)**: Parameter fungsi bertransformasi secara berlawanan arah dengan hierarki pewarisan tipe asalnya (Contravariant) saat `--strictFunctionTypes` diaktifkan.
3. **C (Type Alias / Interface)**: Seluruh interface dan type alias akan dibuang sepenuhnya oleh compiler pada fase *Emitter* (*type erasure*), menyisakan 0 byte runtime. Sebaliknya, class, enum, dan namespace meninggalkan artefak objek di runtime JavaScript.
4. **B**: Flag `isolatedModules` memberitahu Checker untuk memperingatkan developer jika menulis sintaks yang memerlukan informasi tipe global (seperti `const enum` atau `export type` ambigu) yang dapat menggagalkan *single-file transpiler* seperti ESBuild/SWC.
5. **B**: Distributive Conditional Types hanya terjadi jika generic argument yang diuji merupakan parameter tipe telanjang (*naked*). Jika dibungkus (misal `[T] extends [any]`), sifat distributifnya dinonaktifkan.
6. **B (Covariant)**: Properti objek yang hanya dibaca atau struktur objek yang membawa data output mempertahankan arah relasi pewarisan subtyping asalnya (Covariant).
7. **B**: Nominal typing melalui *branding* menghentikan kelemahan struktural TypeScript di mana dua tipe primitif yang sama (seperti ID berbasis string) dapat saling menggantikan secara tidak sengaja.
8. **A**: Di bawah flag ini, properti `foo?: string` memvalidasi bahwa `{ foo: undefined }` adalah ilegal. Nilai `undefined` tidak boleh di-assign secara eksplisit kecuali tipe didefinisikan sebagai `foo?: string | undefined`.
9. **B**: `unknown` adalah representasi *type-safe* dari sembarang tipe data. Checker menolak pemanggilan operasi apa pun pada nilai `unknown` sebelum nilai tersebut ditelusuri dan dipastikan tipenya secara semantik (via *type narrowing*).
10. **B**: `.tsbuildinfo` menyimpan *cache* tanda tangan dan graph kompilasi untuk memfasilitasi *incremental build*, sehingga modul yang tidak termodifikasi tidak perlu dianalisis ulang oleh compiler.
11. **B**: Mengimpor langsung sumber `.ts` lintas paket merusak batasan modular dan memaksa compiler mengevaluasi seluruh monorepo sebagai satu unit graf monolitik raksasa. Menerapkan *Composite Projects* dengan `tsc --build` memastikan setiap library dikompilasi secara independen dan memanfaatkan cache file deklarasi `.d.ts`.
12. **B**: *Branded Types* membebankan penalti 0 byte pada bundle runtime JavaScript, tidak memerlukan overhead instansiasi memori kelas (`new Class`), dan langsung memicu error kompilasi jika urutan argumen ID tertukar.
13. **A**: Ketika generic `Flatten<T>` menerima tipe `any`, evaluasi `any extends Array<infer U>` menghasilkan cabang *both true and false* yang menyebabkan `Flatten<any>` dievaluasi kembali tanpa henti (*infinite loop expansion*), memicu proteksi batas rekursi internal TypeScript (TS2589).

---

### 16. Summary

- **Pipeline Kompilasi Internal**: Kompiler TypeScript beroperasi melalui tahapan formal: `Scanner` -> `Parser` -> `Binder` -> `Checker` -> `Emitter`. Memahami arsitektur internal ini memungkinkan developer mendiagnosa masalah bottleneck performa build pada enterprise monorepo.
- **Teori Variance**: Memahami subtyping formal—*Covariance* (tipe output), *Contravariance* (tipe input parameter), *Invariance* (mutable reference), dan *Bivariance* (legacy method parameters)—merupakan fondasi wajib dalam mendesain arsitektur API framework yang bebas dari kebocoran tipe (*sound*).
- **Nominal Branding**: Mengatasi keterbatasan alamiah dari *Structural Typing* TypeScript dengan menyematkan tag kompilasi sintetis unik (`unique symbol`), melindungi integritas entitas domain kritis seperti ID transaksi dan nominal moneter.
- **Produksi Monorepo Berskala Besar**: Pemanfaatan `tsc --build`, flag `composite`, dan *Project References* mendistribusikan proses kompilasi ke dalam unit independen ter-cache, menghilangkan OOM (*Out Of Memory*), serta memangkas waktu CI/CD secara dramatis.