# BAB 05: Type-Level Programming & Metaprogramming
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   **Menganalisis dan Memanipulasi AST Type Checker**: Memahami bagaimana TypeScript Compiler (`tsc`) mengevaluasi representasi *type-level code* via internal pipeline `checker.ts`, memori kalkulasi, serta batasan ekspansi kompilator.
*   **Merancang Type-Level DSL (Domain Specific Language)**: Mengonstruksi parser statis berbasis *Template Literal Types* untuk validasi format (SQL, URL Path, GraphQL syntax) sepenuhnya pada waktu kompilasi.
*   **Menerapkan Higher-Kinded Types (HKT) Pattern**: Mengimplementasikan abstraksi tipe tingkat tinggi melalui teknik *defunctionalization* (Lightweight Higher-Kinded Polymorphism) tanpa dukungan native *first-class type operators*.
*   **Mengoptimalkan Type Execution Budget**: Mengeliminasi *compiler memory leak*, rekursi tak berhingga, dan degradasi latensi Language Server Protocol (LSP) dengan pola *Tail-Call Optimization* (TCO) pada *Conditional Types*.
*   **Mengontrol Dynamic Contract & Subtyping Variance**: Mengatur model *Covariance*, *Contravariance*, dan *Invariance* secara presisi pada generic boundary arsitektur enterprise untuk mencegah *type-pollution* runtime.

---

### 2. Prerequisites
Sebelum mendalami modul ini, Anda wajib menguasai:
*   **Conditional Types & Infer Keyword**: Ekstraksi tipe terdistribusi (`T extends infer U ? ... : never`) dan sifat distributif pada *naked type parameters*.
*   **Mapped Types Fundamental**: Homomorphic vs Non-homomorphic mapping, serta key remapping (`as` clause).
*   **Tuple Operations**: Manipulasi spread tuple, representasi array statis, dan `readonly` tuple.
*   **Compiler Basics**: Pemahaman mendasar terhadap flag `tsconfig.json` (`strict`, `strictFunctionTypes`, `noImplicitAny`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### TypeScript Type Checker Mechanics (`checker.ts`)
TypeScript bukanlah sekadar sistem tipe anotatif; sistem tipenya bersifat *Turing Complete*. Compiler mengeksekusi interpreter fungsional non-deterministik independen selama proses *type checking*.

```
   Source Code (.ts)
          │
          ▼
   Parser (Scanner) ──► Abstract Syntax Tree (AST)
                              │
                              ▼
    Binder ───────────► Symbol Table (Identifiers & Scopes)
                              │
                              ▼
Type Checker (checker.ts) <───┴── Evaluasi Type-Level Engine
  ├─ Type Instantiation Cache (Memoization)
  ├─ Recursion Depth Counter (Max Depth: 1000 / Tail-call budget: 5000)
  ├─ Subtype Variance Checker
  └─ Union Distribution Engine
                              │
                              ▼
   Emitter (.js / .d.ts) ──► Artifact Emisi Runtime
```

1.  **Instantiation Cache & Memoization**:
    Setiap kali tipe generik instantiated (misal `MapType<T>`), kompilator memeriksa cache internal berbasis `(Type, TypeArguments[])`. Jika argumen sama ditemui, kompilator mengembalikan pointer tipe yang telah di-*resolve*. Kegagalan memoisasi akibat instansiasi tipe yang terlalu unik secara rekursif akan menyebabkan konsumsi heap Node.js meledak (*compiler OOM*).
2.  **Tail-Recursive Conditional Types (TS 4.5+)**:
    Sebelum TS 4.5, setiap rekursi pada conditional types menambahkan stack frame pada type-checker C++ / JS engine, dengan batas kedalaman ~100 rekursi. TS 4.5 mengintroduksi *Tail-Call Optimization* (TCO) pada *type level*. Jika cabang conditional type mengembalikan instansiasi rekursif langsung tanpa operasi lanjutan (misal tidak dibungkus oleh tipe lain di luarnya), kompilator mengevaluasinya secara iteratif, menaikkan batas hingga 5.000 iterasi.
3.  **Variance Rules**:
    *   **Covariant**: `Producer<T>` (Tipe turunan diizinkan, arah subtipe sama: $A \le B \implies F[A] \le F[B]$). Properti objek bersifat kovarian terhadap nilainya.
    *   **Contravariant**: `Consumer<T>` (Arah subtipe terbalik: $A \le B \implies F[B] \le F[A]$). Argumen fungsi pada mode `strictFunctionTypes: true` bersifat kontravarian.
    *   **Invariant**: $F[A] \le F[B]$ hanya jika $A = B$. Properti mutabel atau kombinasi posisi producer dan consumer menghasilkan invarian.
    *   **Bivariant**: Metode yang dideklarasikan dengan sintaks *method shorthand* (`method(x: T): void`) mengevaluasi argumen secara bivariant (tidak aman), berbeda dengan properti fungsi (`method: (x: T) => void`) yang kontravarian.

---

### 4. Why & What

| Dimensi | Type-Level Metaprogramming | Runtime Validation Only |
| :--- | :--- | :--- |
| **Fase Eksekusi** | Compile-Time (Zero Runtime Cost) | Runtime Engine (Node.js/V8/Bun) |
| **Feedback Loop** | Instan (Language Server / IDE red squiggly) | Ditunda hingga runtime integration test / bug report |
| **Overhead** | Menambah durasi build `tsc` & memori IDE | Konsumsi CPU & Alokasi RAM pada hot-path aplikasi |
| **Konsistensi Schema** | *Single Source of Truth* diturunkan otomatis | Rawan desinkronisasi antara validator dan tipe statis |

**Why**: Dalam arsitektur enterprise skala besar, kesalahan representasi kontrak data lintas *boundary* (seperti microservices, schema DB, atau queue payload) memicu bug runtime yang mahal. Memindahkan validasi bentuk data, parsing routing, dan derivasi mutasi ke *type level* menjamin *fail-fast* mutlak: program yang tidak valid secara arsitektural tidak akan pernah berhasil dikompilasi menjadi artefak JavaScript.

---

### 5. How (Workflow Detail)

Alur kerja perancangan *Production-Grade Type-Level Utilities*:
1.  **Formulasi Tipe Dasar & Guard Clauses**: Definisikan terminasi basis rekursi menggunakan `never`, `any`, atau tuple kosong `[]`.
2.  **Penerapan Pola Akumulator**: Transformasikan komputasi rekursi ke format tail-recursive dengan membawa tuple akumulator `Acc extends unknown[] = []`.
3.  **Pattern Extraction via `infer`**: Lakukan destructuring string atau array secara deklaratif menggunakan string literal templates atau rest tuple elements.
4.  **Benchmarking Durasi Kompilasi**: Jalankan `tsc --extendedDiagnostics` dan evaluasi jumlah `Instantiations` serta durasi `Check time`.
5.  **Sanitisasi & Fallback Type**: Selalu bungkus hasil inferensi dengan generic fallback untuk mencegah kebocoran `any` atau `never` ke domain aplikasi.

---

### 6. Analogy & Diagram ASCII

Bayangkan kompilator TypeScript seperti prosesor Stack-Based Virtual Machine sederhana:

```
[Kompilasi TypeScript sebagai Stack Machine]

Type: Reverse<['A', 'B', 'C']>
           │
           ▼
Stack Call 0: Input: ['A', 'B', 'C'] | Acc: []
              Evaluasi: ['B', 'C'] -> Tail call dengan Acc: ['A']
           │
           ▼
Stack Call 1: Input: ['B', 'C']      | Acc: ['A']
              Evaluasi: ['C']        -> Tail call dengan Acc: ['B', 'A']
           │
           ▼
Stack Call 2: Input: ['C']           | Acc: ['B', 'A']
              Evaluasi: []           -> Tail call dengan Acc: ['C', 'B', 'A']
           │
           ▼
Terminasi  : Input: []              | Return Acc
Hasil      : ['C', 'B', 'A']
```

Tanpa TCO, kompilator membungkus setiap *call frame* dalam ekspresi bertingkat: `[...Reverse<['B', 'C']>, 'A']`, yang membebani alokasi pointer memori compiler hingga batas depth terlampaui.

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Type-Level Tuple Math & Deep Property Path
Implementasi operasi penambahan tipe bilangan bulat non-negatif berbasis panjang tuple, serta ekstraksi nilai dari *nested object path*.

```typescript
// --- Type-Level Arithmetic ---
type BuildTuple<Length extends number, Acc extends unknown[] = []> = 
  Acc['length'] extends Length 
    ? Acc 
    : BuildTuple<Length, [...Acc, unknown]>;

export type Add<A extends number, B extends number> = 
  [...BuildTuple<A>, ...BuildTuple<B>]['length'] & number;

// Verifikasi Statis
type FivePlusThree = Add<5, 3>; // Evaluasi: 8

// --- Type-Level Deep Nested Property Resolution ---
export type DeepGet<T, Path extends string> =
  Path extends `${infer Head}.${infer Tail}`
    ? Head extends keyof T
      ? DeepGet<T[Head], Tail>
      : never
    : Path extends keyof T
      ? T[Path]
      : never;

// Pengujian Kontrak Objek
interface SystemConfig {
  database: {
    primary: {
      connectionString: string;
      poolSize: number;
    };
  };
}

type ConnStr = DeepGet<SystemConfig, 'database.primary.connectionString'>; // string
type Invalid = DeepGet<SystemConfig, 'database.replica.port'>;            // never
```

#### B. Practical Example: Type-Safe Enterprise Route Parameter Extractor
Parser string jalur routing (misalnya: `/tenants/:tenantId/invoices/:invoiceId/download`) yang mengekstrak daftar parameter URL secara otomatis ke dalam bentuk strict interface runtime.

```typescript
// Ekstraksi segmen path berawalan ':'
type ExtractRouteParams<RoutePath extends string> = 
  RoutePath extends `${infer _Start}:${infer Param}/${infer Rest}`
    ? { [K in Param | keyof ExtractRouteParams<`/${Rest}`>]: string }
    : RoutePath extends `${infer _Start}:${infer Param}`
      ? { [K in Param]: string }
      : Record<string, never>;

// Metadata Handler Representing Production Route
interface RouteDefinition<Path extends string> {
  path: Path;
  handler: (params: ExtractRouteParams<Path>) => Promise<{ statusCode: number; payload: unknown }>;
}

export function defineRoute<P extends string>(definition: RouteDefinition<P>): RouteDefinition<P> {
  return definition;
}

// Inisialisasi Endpoint
export const tenantInvoiceRoute = defineRoute({
  path: '/tenants/:tenantId/invoices/:invoiceId',
  handler: async (params) => {
    // Validasi Compiler: params memiliki type '{ tenantId: string; invoiceId: string; }'
    const { tenantId, invoiceId } = params;
    return {
      statusCode: 200,
      payload: { id: invoiceId, owner: tenantId, active: true }
    };
  }
});

// @ts-expect-error Kompilator menggagalkan jika mengakses properti yang tidak ada di path
tenantInvoiceRoute.handler({ tenantId: "uuid-1", invoiceId: "inv-99", invalidKey: "err" });
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Zero-Runtime-Cost Schema Projection Engine pada API Gateway Microservices
**Konteks**: Sebuah platform FinTech memproses jutaan request payload JSON berukuran besar per detik. Menggunakan schema validator runtime (seperti runtime deep-clone mapping) pada setiap routing layer menyebabkan CPU spike pada V8 garbage collection. Solusinya adalah membangun *Type-Safe Projection Engine* yang memvalidasi dan memproyeksikan payload hanya pada level deklarasi tipe, sehingga payload dapat langsung diproses dengan zero-copy mapping di runtime.

```typescript
// Domain Event Representation dari Database Internal
interface OrderEntity {
  id: string;
  externalReference: string;
  amountMinorUnits: number;
  currency: 'USD' | 'EUR' | 'IDR';
  audit: {
    createdAt: string;
    createdByIp: string;
    internalTags: string[];
  };
  settlementAccount: {
    transitNumber: string;
    maskedAccountNumber: string;
    routingCode: string;
  };
}

// Projection Mask: Mendefinisikan schema yang boleh diekspos ke Public API Gateway
type SchemaProjection<T> = {
  [K in keyof T]?: T[K] extends object 
    ? T[K] extends unknown[] 
      ? boolean 
      : SchemaProjection<T[K]> | boolean
    : boolean;
};

// Type Engine: Mengekstrak interface baru berdasarkan proyeksi bertingkat
type ApplyProjection<Source, Mask> = {
  [K in keyof Source as K extends keyof Mask 
    ? Mask[K] extends true 
      ? K 
      : Mask[K] extends object 
        ? K 
        : never 
    : never]: K extends keyof Mask 
      ? Mask[K] extends true 
        ? Source[K] 
        : Mask[K] extends object 
          ? ApplyProjection<Source[K], Mask[K]> 
          : never 
      : never;
};

// Implementasi Factory Gateway
class EnterpriseContractGateway {
  static createProjector<T>() {
    return <M extends SchemaProjection<T>>(mask: M) => {
      return (entity: T): ApplyProjection<T, M> => {
        const executeProjection = (source: unknown, projectionMask: unknown): unknown => {
          if (typeof source !== 'object' || source === null) return source;
          const result: Record<string, unknown> = {};
          
          for (const key of Object.keys(projectionMask as object)) {
            const maskVal = (projectionMask as Record<string, unknown>)[key];
            if (maskVal === true) {
              result[key] = (source as Record<string, unknown>)[key];
            } else if (typeof maskVal === 'object' && maskVal !== null) {
              result[key] = executeProjection(
                (source as Record<string, unknown>)[key], 
                maskVal
              );
            }
          }
          return result;
        };

        return executeProjection(entity, mask) as ApplyProjection<T, M>;
      };
    };
  }
}

// Konfigurasi Public Gateway Mask
const projectOrderToPublic = EnterpriseContractGateway.createProjector<OrderEntity>()({
  id: true,
  amountMinorUnits: true,
  currency: true,
  audit: {
    createdAt: true
    // createdByIp & internalTags dieksklusi secara statis dan runtime
  },
  settlementAccount: {
    maskedAccountNumber: true
    // routingCode & transitNumber disembunyikan
  }
});

// Contoh Eksekusi
const mockDatabaseRecord: OrderEntity = {
  id: "ord_1029384",
  externalReference: "ext_ref_89",
  amountMinorUnits: 50000000,
  currency: "IDR",
  audit: {
    createdAt: "2026-03-30T00:00:00Z",
    createdByIp: "10.240.12.1",
    internalTags: ["fraud-checked", "tier-1"]
  },
  settlementAccount: {
    transitNumber: "021",
    maskedAccountNumber: "xxxx-xxxx-1299",
    routingCode: "INDOID"
  }
};

const publicPayload = projectOrderToPublic(mockDatabaseRecord);

// Validasi Statis:
// publicPayload.id (valid - string)
// publicPayload.settlementAccount.maskedAccountNumber (valid - string)
// @ts-expect-error Kompilator menolak akses ke secret field:
console.log(publicPayload.settlementAccount.transitNumber);
// @ts-expect-error Kompilator menolak akses ke field internalTags:
console.log(publicPayload.audit.internalTags);
```

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Complex Metaprogramming** | *Absolute Type-Safety*, *Self-documenting APIs*, hilangnya bug transmisi payload tanpa runtime overhead. | Waktu kompilasi membengkak secara eksponensial. Memory consumption IDE (TSServer) dapat mencapai batasan heap (2GB+), memicu lag pada autocompletion. |
| **Generics Datar (Shallow Generics)** | Kecepatan kompilasi instan, pemeliharaan kode oleh engineer junior jauh lebih mudah. | Potensi kebocoran tipe runtime, banyak manual type assertion (`as unknown as Target`), duplikasi definisi kontrak schema. |
| **Third-Party Code Generation** | Tipe dihasilkan terpisah (misal via Protobuf compiler), struktur kompilasi jelas. | Membutuhkan build-step tambahan di pipeline CI/CD, hilangnya kemampuan inferensi on-the-fly yang dinamis secara real-time. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan: Distributive Conditional Types yang Tidak Disengaja
*Problem*: Ketika conditional type menerima union pada generic naked parameter, operasi akan didistribusikan ke setiap elemen union.
```typescript
type ToArray<T> = T extends unknown ? T[] : never;
type TestUnion = ToArray<string | number>; 
// Diharapkan: (string | number)[]
// Aktual: string[] | number[]
```
*Solusi*: Bungkus ekspresi dengan square brackets `[T]` untuk mematikan distributive behavior:
```typescript
type ToArrayFixed<T> = [T] extends [unknown] ? T[] : never;
type Correct = ToArrayFixed<string | number>; // (string | number)[]
```

#### 2. Kesalahan: Melebihi Batas Rekursi Kompilator
*Problem*: Error: `Type instantiation is excessively deep and possibly infinite. ts(2589)` akibat penulisan rekursi non-tail call.
```typescript
// BURUK: Non-tail recursive. Membungkus hasil iterasi di dalam generic lain.
type StringLength<S extends string> = S extends `${string}${infer Tail}`
  ? 1 + StringLength<Tail> // Illegal type arithmetic
  : 0;
```
*Solusi*: Gunakan accumulator tuple dengan format Tail-Call Optimized (TS 4.5+):
```typescript
// BENAR: Tail-recursive pattern
type StringLengthTCO<S extends string, Acc extends unknown[] = []> =
  S extends `${string}${infer Tail}`
    ? StringLengthTCO<Tail, [...Acc, unknown]>
    : Acc['length'];
```

#### 3. Diagnosis Masalah Kompilasi dengan Trace Flags
Jika proyek enterprise Anda mengalami waktu kompilasi lambat akibat metaprogramming, lakukan profiling:
```bash
# Generate trace log
npx tsc --generateTrace ./tsc-trace-output

# Jalankan analyzer menggunakan tool resmi
npx @typescript/analyze-trace ./tsc-trace-output
```
Periksa file `types.json` pada output trace untuk menemukan tipe spesifik yang memiliki metrik `instantiationCount` di atas ambang normal (> 50.000 instansiasi).

---

### 11. Best Practices (Production Checklist)

*   [ ] **Aktifkan Flags Wajib**: Pastikan `strict: true` dan `strictFunctionTypes: true` selalu menyala di `tsconfig.json`.
*   [ ] **Gunakan Accumulator Pattern**: Terapkan default parameter akumulator generic `Acc extends unknown[] = []` pada semua utility rekursif.
*   [ ] **Batasi Key Splitting pada String Literals**: Hindari parsing string dinamis yang memiliki kompleksitas permutasi kombinatorial (misal template string dengan lebih dari 3 interpolasi bebas).
*   [ ] **Sediakan Escape Hatch yang Jelas**: Ketika abstraksi type-level terlalu rumit, sertakan deklarasi interface eksplisit agar kompilator tidak perlu mengevaluasi seluruh grafik tipe secara brute force.
*   [ ] **Hindari Tipe Rekursif pada Objek Skala Besar**: Jangan aplikasikan `DeepReadonly<T>` atau `DeepPartial<T>` langsung pada class instance library eksternal (misal: Sequelize models, Mongoose documents, atau AWS SDK clients).
*   [ ] **Audit Dampak Metaprogramming pada CI**: Pasang target pipeline kompilasi untuk mencatat metrik `tsc --extendedDiagnostics` secara berkala guna mendeteksi degradasi performa sebelum merge ke branch `main`.

---

### 12. Hands-on Practice

Buka direktori repositori Anda dan ikuti langkah implementasi step-by-step:

#### Langkah 1: Setup Proyek
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install --save-dev typescript @types/node
npx tsc --init --strict true --strictFunctionTypes true --target ES2022 --module NodeNext
```

#### Langkah 2: Buat File `hands-on/m02/src/type-orm.ts`
Implementasikan engine Type-Safe Query Builder mikro yang memvalidasi sintaks operator query berbasis skema tabel.

```typescript
// hands-on/m02/src/type-orm.ts

export type Primitive = string | number | boolean | bigint | Date | null | undefined;

export type EntitySchema = {
  [key: string]: Primitive;
};

// Filter operators yang valid sesuai tipe data field
export type FieldFilter<T> = 
  T extends number 
    ? { eq?: T; gt?: number; lt?: number; gte?: number; lte?: number }
    : T extends string 
      ? { eq?: T; startsWith?: string; endsWith?: string; contains?: string }
      : { eq?: T };

// Generator Schema Query bersarang
export type WhereClause<Schema extends EntitySchema> = {
  [K in keyof Schema]?: FieldFilter<Schema[K]>;
} & {
  $and?: WhereClause<Schema>[];
  $or?: WhereClause<Schema>[];
};

export class QueryEngine<Schema extends EntitySchema> {
  constructor(private readonly tableName: string) {}

  public execute(where: WhereClause<Schema>): { sql: string; values: unknown[] } {
    const values: unknown[] = [];
    const buildExpression = (clause: WhereClause<Schema>): string => {
      const conditions: string[] = [];

      for (const [key, filter] of Object.entries(clause)) {
        if (key === '$and' && Array.isArray(filter)) {
          const nested = filter.map(buildExpression).join(' AND ');
          if (nested) conditions.push(`(${nested})`);
        } else if (key === '$or' && Array.isArray(filter)) {
          const nested = filter.map(buildExpression).join(' OR ');
          if (nested) conditions.push(`(${nested})`);
        } else if (filter && typeof filter === 'object') {
          for (const [op, val] of Object.entries(filter)) {
            values.push(val);
            const idx = values.length;
            if (op === 'eq') conditions.push(`${key} = $${idx}`);
            if (op === 'gt') conditions.push(`${key} > $${idx}`);
            if (op === 'lt') conditions.push(`${key} < $${idx}`);
            if (op === 'startsWith') conditions.push(`${key} LIKE $${idx} || '%'`);
          }
        }
      }
      return conditions.join(' AND ');
    };

    const sql = `SELECT * FROM ${this.tableName} WHERE ${buildExpression(where)}`;
    return { sql, values };
  }
}
```

#### Langkah 3: Verifikasi Implementasi
Buat file consumer `hands-on/m02/src/main.ts`:
```typescript
// hands-on/m02/src/main.ts
import { QueryEngine } from './type-orm.js';

interface UserAccount {
  id: number;
  email: string;
  isActive: boolean;
}

const userQuery = new QueryEngine<UserAccount>('users');

// Skenario 1: Query Valid
const queryA = userQuery.execute({
  id: { gt: 100 },
  email: { startsWith: 'enterprise' },
  $or: [
    { isActive: { eq: true } }
  ]
});
console.log('Generated Query:', queryA);

// Skenario 2: Eksperimen Error Kompilasi
// Uncomment blok di bawah ini untuk melihat compiler menolak tipe:
/*
userQuery.execute({
  id: { startsWith: 'invalid-string-for-number' }, // Compile Error!
  unknownColumn: { eq: 'test' }                    // Compile Error!
});
*/
```

Jalankan kompilasi:
```bash
npx tsc --noEmit
```

---

### 13. Exercise

#### Level Easy: Dotted Key Flattener
Buat generic utility `FlattenKeys<T>` yang mengonversi interface bertingkat 2-level menjadi union string path representasi flat.
*Input Interface*:
```typescript
interface AppState {
  user: {
    profile: string;
    auth: boolean;
  };
  metrics: {
    latency: number;
  };
}
```
*Expected Result*:
`"user.profile" | "user.auth" | "metrics.latency"`

```typescript
// JAWABAN LATIHAN EASY:
export type FlattenKeys<T> = {
  [K in keyof T & string]: T[K] extends Record<string, unknown>
    ? `${K}.${keyof T[K] & string}`
    : K;
}[keyof T & string];
```

#### Level Medium: JSON Schema to TypeScript Type Mapper
Buat type converter yang menerima representasi skema tipe statis sederhana dan mengonversinya menjadi inferred type.
```typescript
type FieldDescriptor = 
  | { type: 'string'; optional?: boolean }
  | { type: 'number'; optional?: boolean }
  | { type: 'boolean'; optional?: boolean };

type ModelDescriptor = Record<string, FieldDescriptor>;

// Definisikan ModelToType<T extends ModelDescriptor> di bawah ini:
export type ModelToType<T extends ModelDescriptor> = {
  [K in keyof T as T[K]['optional'] extends true ? never : K]: 
    T[K]['type'] extends 'string' ? string :
    T[K]['type'] extends 'number' ? number :
    T[K]['type'] extends 'boolean' ? boolean : never;
} & {
  [K in keyof T as T[K]['optional'] extends true ? K : never]?: 
    T[K]['type'] extends 'string' ? string :
    T[K]['type'] extends 'number' ? number :
    T[K]['type'] extends 'boolean' ? boolean : never;
};

// Verifikasi:
type Inferred = ModelToType<{
  id: { type: 'number' };
  name: { type: 'string' };
  metadata: { type: 'string'; optional: true };
}>;
// Hasil yang terbentuk: { id: number; name: string; metadata?: string | undefined }
```

#### Level Hard: Defunctionalized Higher-Kinded Type Pipeline
TypeScript tidak mengizinkan generic instantiation bebas seperti `type Apply<F<_>, A> = F<A>`. Implementasikan pola HKT menggunakan *Defunctionalization / Lightweight Higher-Kinded Polymorphism* dictionary lookup.

```typescript
// JAWABAN LATIHAN HARD:
// 1. Definisikan container dictionary antarmuka
export interface HKTRegistry<A> {
  // Registry akan diekstensi via declaration merging
}

// 2. Type URI Identifier
export type HKTURI = keyof HKTRegistry<unknown>;

// 3. Extractor Type
export type Kind<URI extends HKTURI, A> = (HKTRegistry<A>)[URI];

// 4. Implementasi Implementor 1: Array
declare module './type-orm.js' { // Asumsi namespace modul saat ini
  interface HKTRegistry<A> {
    ArrayURI: A[];
    PromiseURI: Promise<A>;
  }
}

// 5. Utility Abstraksi Monadic Container Mapping
export type MappedKind<URI extends HKTURI, TInput, TOutput> = 
  Kind<URI, TInput> extends Array<TInput>
    ? Kind<URI, TOutput>
    : Kind<URI, TInput> extends Promise<TInput>
      ? Kind<URI, TOutput>
      : never;

// Verifikasi Type
type MappedArray = MappedKind<'ArrayURI', number, string>;   // string[]
type MappedPromise = MappedKind<'PromiseURI', number, string>; // Promise<string>
```

---

### 14. Challenge (Tantangan Studi Kasus Kompleks)

**Tantangan**: Buat sebuah *Zero-Runtime Compile-Time SQL Validator & Abstract Syntax Parser*.
Parser harus menerima string mentah generic bertipe SQL statement:
`SELECT [Columns] FROM [Table] WHERE [Conditions]`

**Persyaratan Arsitektural**:
1.  Parser harus memvalidasi nama tabel terhadap `DatabaseSchema` interface yang diberikan.
2.  Parser harus memvalidasi bahwa setiap kolom yang diminta dalam klausa `SELECT` benar-benar ada pada tabel tersebut. Kolom `*` diizinkan dan menghasilkan seluruh kolom.
3.  Output dari tipe adalah interface objek yang hanya berisi kolom-kolom yang dipilih dengan tipe data aslinya.
4.  Jika kolom atau tabel tidak terdaftar dalam skema, kembalikan deskriptor error kustom berupa string literal: `Error: Table [Table] does not exist` atau `Error: Column [Col] does not exist in table [Table]`.
5.  Tidak boleh menggunakan pustaka eksternal apapun. Semua dikerjakan pada type level murni menggunakan Recursive Template Literals.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1.  **Mengapa `T extends any` dapat menghasilkan pemecahan (distribution) tipe pada TypeScript?**
    *   *Jawaban*: Karena `T` merupakan parameter generik bebas (*naked type parameter*). Aturan default kompilator adalah mendistribusikan operasi conditional terhadap setiap varian tipe di dalam union.
2.  **Apa perbedaan mendasar antara sintaks metode `{ method(val: T): void }` dan sintaks properti fungsi `{ method: (val: T) => void }`?**
    *   *Jawaban*: Method shorthand dievaluasi secara bivariant (tidak aman tipe), sedangkan properti fungsi mematuhi flag `strictFunctionTypes` dan dievaluasi secara kontravarian (sound subtyping).
3.  **Berapa batas kedalaman rekursi maksimum conditional types sebelum Tail-Call Optimization diperkenalkan di TS 4.5?**
    *   *Jawaban*: Sekitar 100 stack frames.
4.  **Apa output dari tipe `type Res = keyof any;`?**
    *   *Jawaban*: `string | number | symbol`.
5.  **Bagaimana cara menghapus modifier `readonly` dari semua properti suatu objek pada mapped type?**
    *   *Jawaban*: Menggunakan modifier `-readonly`, misalnya `type Writable<T> = { -readonly [P in keyof T]: T[P] };`.

#### 5 Pertanyaan Intermediate
6.  **Jelaskan mekanisme Tail-Call Optimization pada kompilator TypeScript (TS 4.5+)!**
    *   *Jawaban*: Kompilator mendeteksi jika cabang kondisional dari sebuah generic conditional type langsung mengembalikan panggilan rekursif tanpa perlu melakukan evaluasi lanjutan terhadap hasilnya. Jika terpenuhi, kompilator mengganti eksekusi rekursif internal dengan loop komputasi sekuensial, menghemat alokasi stack evaluator hingga limit 5.000 iterasi.
7.  **Kapan sebaiknya kita mematikan Union Distribution menggunakan pola `[T] extends [infer U]`?**
    *   *Jawaban*: Ketika kita ingin memperlakukan keseluruhan union sebagai satu kesatuan utuh (misalnya: memvalidasi apakah tipe tersebut adalah tipe tuple/union lengkap yang spesifik), alih-alih mengeksekusi logika mapping/filter per masing-masing elemen anggota union.
8.  **Bagaimana subtipe kontravarian bekerja pada parameter callback fungsi?**
    *   *Jawaban*: Jika $A$ adalah subtype dari $B$ ($A \le B$), maka fungsi yang menerima argumen $B$ adalah subtipe dari fungsi yang menerima argumen $A$ ($F[B] \le F[A]$). Ini karena fungsi penerima $B$ dijamin mampu menangani subset parameter $A$ yang lebih spesifik dengan aman.
9.  **Apa yang menyebabkan IDE menampilkan pesan error `Type instantiation is excessively deep and possibly infinite` padahal rekursi belum mencapai batasan 5.000?**
    *   *Jawaban*: Adanya siklus referensi tipe melingkar (*circular type dependency*) yang tidak memiliki guard basis terminasi (tidak pernah mencapai kondisi fallback cabang non-rekursif), atau penggunaan non-tail recursion yang melampaui kedalaman stack ~1000 iterasi.
10. **Bagaimana cara mengoptimalkan performa kompilasi `tsc` pada proyek yang menggunakan metaprogramming ekstensif?**
    *   *Jawaban*: Memecah pemanggilan type-level bertingkat dengan mendefinisikan intermediate aliases untuk meningkatkan tingkat hit-rate internal memoization cache, membatasi penggunaan string pattern matching tak terbatas, dan menganalisis bottleneck dengan flag `--generateTrace`.

#### 3 Skenario Kasus Produksi
11. **Skenario 1**: Tim Anda membangun sistem messaging inter-service berbasis event broker. Developer sering salah memetakan payload event dengan nama topik event. Bagaimana Anda merekayasanya secara statis?
    *   *Solusi Arsitektur*: Bangun centralized `EventRegistry` interface di mana key adalah nama topik (`orders.created`, `payments.failed`), dan value adalah tipe payload-nya. Buat generic client `publish<TTopic extends keyof EventRegistry>(topic: TTopic, payload: EventRegistry[TTopic]): Promise<void>`.
12. **Skenario 2**: CI pipeline memakan waktu 40 menit hanya pada langkah `tsc --noEmit`. Trace analysis menunjukkan bahwa utility `DeepMerge<A, B>` pihak ketiga mengonsumsi 70% waktu parsing tipe. Langkah apa yang wajib dilakukan?
    *   *Solusi Arsitektur*: Ganti utility recursive `DeepMerge` murni tersebut dengan shallow generic interface extension (`A & B`), batasi kedalaman merging maksimal 3 lapis menggunakan accumulator depth limiter, atau ganti definisi tipe rekursif eksternal tersebut dengan file deklarasi statis `.d.ts` yang digenerate sekali pada build-time via generator script.
13. **Skenario 3**: Sebuah dynamic schema builder menghasilkan type yang terinferensi sebagai `any` ketika pengguna mempassing properti dinamis tanpa generic annotation eksplisit. Bagaimana mencegah kebocoran `any` ke API layer publik?
    *   *Solusi Arsitektur*: Gunakan generic constraint `extends Record<string, unknown>` (bukan `Record<string, any>`), dan pasang assertion guard di level return type: `type NoAny<T> = 0 extends (1 & T) ? never : T;`. Ini memanfaatkan sifat bahwa perpotongan tipe primitif dengan `any` menghasilkan `any`, sehingga `0 extends (1 & any)` bernilai `true`.

---

### 16. Summary

*   TypeScript Type-Level Programming adalah bahasa komputasi murni fungsional, turing-complete, tanpa *side-effects*, yang beroperasi pada fase kompilasi untuk menjamin validitas integritas data sistem.
*   Pola komputasi lanjutan bergantung pada penguasaan **Recursive Conditional Types**, **Tail-Call Optimization (TCO)** via accumulator, dan pemahaman akurat atas **Distribution Mechanics**.
*   **Subtype Variance** (khususnya *Contravariance* pada argumen fungsi) adalah fondasi matematis penentu keamanan polimorfisme generic boundary antar API modul.
*   Seluruh komputasi type-level tingkat tinggi memiliki biaya kompilasi (*compile-time cost*). Arsitek sistem harus selalu menyeimbangkan ekspresivitas DSL statis dengan latensi compiler menggunakan tracing diagnostic tools seperti `tsc --generateTrace`.