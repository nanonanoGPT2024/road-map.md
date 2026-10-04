# BAB 04: Advanced Generics & Parametric Polymorphism
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   **Menganalisis dan Memanipulasi Varian Tipe (*Type Variance*)**: Memahami dan mengimplementasikan anotasi eksplisit varian tipe (`in`, `out`) pada deklarasi tipe generik guna mengoptimalkan performa type-checker dan menjamin *soundness* tipe pada posisi kovarian (*covariant*) dan kontravarian (*contravariant*).
*   **Merekayasa Metaprogramming Tingkat Lanjut (*Type-Level Metaprogramming*)**: Mengonstruksi *conditional types*, *distributive conditional types*, dan ekstraksi pola menggunakan keyword `infer` dalam posisi kontravarian untuk transformasi tipe yang kompleks (seperti konversi *Union to Intersection*).
*   **Mengemulasi *Higher-Kinded Types* (HKT)**: Mengatasi batasan sistem tipe TypeScript yang tidak mendukung HKT secara *native* generasi pertama menggunakan teknik *Lightweight Higher-Kinded Polymorphism* berbasis *defunctionalization* dan *URI-to-Kind mapping*.
*   **Mengembangkan Arsitektur Generik Skala Enterprise**: Menerapkan pola *builder*, *strongly-typed CQRS/Event-Sourced Message Bus*, dan *type-safe schema derivation* yang mempertahankan *zero-cost runtime overhead* sekaligus memvalidasi struktur data secara deterministik saat kompilasi.
*   **Mendiagnosis dan Mengoptimalkan Performa Kompilasi**: Mengidentifikasi hambatan kompilasi (*type instantiation depth limit*, rekursi tak berhingga) dan memitigasinya dengan teknik *tail-call recursive type elimination* serta membatasi pembuatan tipe sementara (*intermediate types*).

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib menguasai:
1.  **TypeScript Core Fundamentals**: Pemahaman solid mengenai Primitive Types, Union/Intersection Types, Mapped Types, dan Type Narrowing (`BAB-01` s.d. `BAB-03`).
2.  **Basic & Intermediate Generics**: Familiaritas dengan generic interfaces, generic constraints (`T extends K`), dan `keyof`/`typeof` operators.
3.  **Sistem Runtime JavaScript Modern**: ECMAScript 2022+, struktur data `Map`/`Set`, objek prototypal, dan mekanisme asynchronous (`Promise`, `AsyncIterator`).
4.  **Tooling & Runtime**: Node.js v18 LTS atau v20 LTS, `typescript` versi 5.0 atau lebih tinggi, dengan konfigurasi `tsconfig.json` berbasis `strict: true`.

---

### 3. Concept & Internal Architecture

#### 3.1 Teori Parametric Polymorphism & Arsitektur Type Engine TypeScript
Parametric Polymorphism memungkinkan suatu fungsi atau tipe data ditulis secara generik sehingga dapat menangani nilai secara identik tanpa bergantung pada tipe data runtime-nya. Dalam TypeScript Compiler (`tsc`), tipe generik diproses melalui beberapa tahapan inti dalam subsistem *checker*:

```
Source Code (.ts) 
      │
      ▼
Parser ──► Abstract Syntax Tree (AST)
      │
      ▼
Binder ──► Symbol Table (Identitas Simbol)
      │
      ▼
Type Checker (src/compiler/checker.ts)
      ├── Type Resolution: Type Parameters dirangkai ke Type Arguments
      ├── Constraint Checking: Evaluasi klausul 'extends'
      ├── Type Instantiation: Cache lookup via TypeId & Instantiation Cache
      └── Structural Subtyping: Evaluasi kesesuaian relasi tipe (Assignability)
```

Pada fase **Type Instantiation**, kompilator tidak menduplikasi representasi AST dari deklarasi generik. Sebaliknya, kompilator menciptakan instance tipe virtual baru (`TypeObject`) yang menyimpan pemetaan (*substitution map*) dari type parameter formal ke argumen tipe konkret. Untuk efisiensi, kompilator menggunakan *Instantiation Cache* berbasis ID internal simbol.

#### 3.2 Distributivity pada Conditional Types
Secara internal, *conditional type* didefinisikan sebagai:
```typescript
type Conditional<T> = T extends U ? X : Y;
```
Ketika parameter tipe `T` berupa "naked type parameter" (parameter tipe murni tanpa dibungkus struktur lain seperti `[T]`, `Promise<T>`, dsb.) dan diberikan sebuah *Union Type* ($A \cup B$), kompilator secara otomatis mendistribusikan operasi kondisi tersebut ke setiap anggota serikat tipe:

$$\text{Conditional}\langle A \cup B \rangle \implies \text{Conditional}\langle A \rangle \cup \text{Conditional}\langle B \rangle$$

Jika perilaku distributif ini tidak diinginkan (misalnya saat mengecek apakah suatu tipe secara presisi kompatibel dengan serikat atau mengecek tipe `never`), distributivitas dicegah (*de-distributed*) dengan membungkus kedua sisi dalam tuple: `[T] extends [U]`.

#### 3.3 Variance: Kovariansi, Kontravariansi, Invariansi, dan Bivariansi
*Variance* mendeskripsikan bagaimana subtiping dari tipe argumen kompleks berhubungan dengan subtiping dari tipe komponen penyusunnya. Diberikan relasi subtiping: $\text{Derived} \le \text{Base}$ (artinya `Derived` adalah subtype dari `Base`).

*   **Kovariansi (*Covariance*)**: Relasi subtiping dipertahankan.
    $$T \le U \implies F\langle T \rangle \le F\langle U \rangle$$
    *Contoh:* Posisi kembalian fungsi (*output/read-only*).
*   **Kontravariansi (*Contravariance*)**: Relasi subtiping dibalik.
    $$T \le U \implies F\langle U \rangle \le F\langle T \rangle$$
    *Contoh:* Posisi argumen fungsi (*input/write-only*).
*   **Invariansi (*Invariance*)**: Relasi subtiping tidak diizinkan di kedua arah.
    $$F\langle T \rangle \le F\langle U \rangle \iff T = U$$
    *Contoh:* Properti yang dapat dibaca sekaligus ditulis (*mutable positions*).
*   **Bivariansi (*Bivariance*)**: Relasi berlaku dua arah (subtype dan supertype diizinkan). Terjadi pada parameter method fungsi jika `strictFunctionTypes: false` (secara bawaan parameter fungsi berkategori kontravarian di bawah mode `strictFunctionTypes: true`).

Mulai TypeScript 4.7, developer dapat secara eksplisit mendeklarasikan varian menggunakan keyword `in` (kontravarian) dan `out` (kovarian). Fitur ini mengeliminasi kebutuhan kompilator untuk menghitung varian secara induktif struktural yang mendalam, secara signifikan memangkas beban kerja type-checking pada struktur generik berskala besar.

```
       Variance Matrix & Structural Positioning
       
 ┌──────────────────────────┬──────────────────────────┐
 │      Kovarian (out)      │      Kontravarian (in)   │
 ├──────────────────────────┼──────────────────────────┤
 │ - Nilai Return Fungsi    │ - Argumen Fungsi         │
 │ - Properti Readonly      │ - Consumer Interfaces    │
 │ - Yield Statements       │ - Event Listeners / Sink │
 └──────────────────────────┴──────────────────────────┘
```

#### 3.4 Inferensi dalam Posisi Kontravarian: Union to Intersection
Sifat kontravarian dari argumen fungsi dimanfaatkan oleh type engine TypeScript untuk mengekstrak dan mengonversi tipe *Union* menjadi *Intersection*. Jika kompilator menginferensikan variabel tipe yang sama dari dua kandidat berbeda yang berada pada posisi kontravarian, solusi tipe yang memenuhi batas tipe tersebut adalah irisan (*intersection*) dari tipe-tipe tersebut:

```typescript
type UnionToIntersection<U> = 
  (U extends unknown ? (k: U) => void : never) extends (k: infer I) => void 
    ? I 
    : never;
```
Ketika $U = A \cup B$, bagian distributif membentuk $(A \to \text{void}) \cup (B \to \text{void})$. Pada klausul inferensi kedua, kompilator harus menentukan nilai `I` yang valid untuk menerima argumen dari kedua cabang fungsi tersebut secara simultan, sehingga diputuskan $I = A \cap B$.

---

### 4. Why & What

| Dimensi | Menggunakan Basic Generics | Menggunakan Advanced Parametric Polymorphism |
| :--- | :--- | :--- |
| **Type Precision** | Tipe sering kali melorot (*widen*) menjadi `any`, `unknown`, atau serikat longgar. | Inferensi tipe eksak hingga ke level *template literal*, *exact keys*, dan *conditional branches*. |
| **Type Safety Validation** | Pengecekan runtime mendalam diperlukan; validasi tipe statis terbatas pada bentuk flat. | Relasi dependensi antar argumen, schema, dan validasi kontrak divalidasi pada saat kompilasi (*zero runtime bug*). |
| **Compiler Optimization** | Kalkulasi varian struktural rekursif membebani memory kompilator pada codebase besar. | Anotasi `in`/`out` memotong jalur evaluasi AST type-checker (*fast-path checking*). |
| **Expressive Power** | Tidak mampu memodelkan HKT atau rekursi tipe mendalam (sering memicu error TS2589). | Mampu memodelkan HKT (via defunctionalization), tail-call recursion, dan dynamic builders. |

---

### 5. How (Workflow Detail)

Alur kerja evaluasi kompilator untuk ekspresi generik rekursif bertipe conditional:

```
[Mulai Evaluasi Tipe Generik: T<A>]
               │
               ▼
[Apakah ada anotasi explicit variance (in/out)?]
      ├── YA  ──► Skip variance induction; gunakan cache deterministik.
      └── TIDAK ─► Lakukan deep structural comparison untuk deduksi varian.
               │
               ▼
[Apakah tipe input berupa Naked Type Parameter di dalam Conditional?]
      ├── YA  ──► Evaluasi secara DISTRIBUTIF ke masing-masing anggota Union.
      └── TIDAK ─► Evaluasi blok monolitik ([T] extends [U]).
               │
               ▼
[Pola ekstraksi 'infer'?]
      ├── Posisi Return ──► Koleksi kandidat secara KOVARIAN (Union).
      └── Posisi Argumen ──► Koleksi kandidat secara KONTRAVARIAN (Intersection).
               │
               ▼
[Evaluasi Kedalaman Rekursi]
      ├── Depth < Max Limit (1000 iterasi) ──► Teruskan resolusi tipe.
      └── Depth >= Max Limit ─────────────────► Emit Error: TS2589 (Recursion Limit).
               │
               ▼
[Tipe Akhir Ditetapkan & Masuk ke Symbol Table]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pabrik Pipa Saluran Adaptif
Bayangkan *Basic Generics* seperti cetakan kontainer plastik standar: ukuran wadah bisa berubah tergantung input, tetapi cetakan hanya membentuk satu lapis. 

*Advanced Parametric Polymorphism* diibaratkan sistem konveyor modular industri canggih:
*   **Kovariansi (`out`)**: Saluran pipa keluar dari tangki pabrik. Jika pabrik memproduksi Minuman Bersoda (subtype dari Minuman), pipa output otomatis dapat dialirkan ke truk penampung Minuman universal tanpa tumpah.
*   **Kontravariansi (`in`)**: Corong input pengisian. Jika mesin didesain untuk menerima dan membersihkan segala jenis Minuman (supertype), maka mesin tersebut pasti aman dan valid untuk diisi Minuman Bersoda secara spesifik.
*   **Lightweight HKT**: Sistem soket modular universal. Mesin pengolah tidak perlu tahu bentuk fisik spesifik dari kaleng, botol, atau kardus; mesin hanya bekerja dengan adaptor tipe antarmuka (*URI Token*) yang memetakan isi cairan ke wadah yang sesuai saat runtime dirakit.

```
       +-------------------------------------------------------+
       |             Higher-Kinded Type (HKT) Analogy          |
       +-------------------------------------------------------+
       
        Type-Level Container F<_>         Concrete Type A
               (e.g., Option, Array)              (e.g., string, User)
                        \                         /
                         \                       /
                          v                     v
                      +-----------------------------+
                      | URI Registry Interface Map  |
                      | URItoKind<A>['Array'] -> A[]|
                      +-----------------------------+
                                     │
                                     ▼
                          Hasil Tipe: F<A> (e.g., User[])
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Variance Annotations & Union-to-Intersection
Implementasi pembuktian variansi eksplisit dan pembalikan tipe (*Union to Intersection*):

```typescript
// 1. Explicit Variance Annotations
export interface Producer<out T> {
  produce(): T;
}

export interface Consumer<in T> {
  consume(value: T): void;
}

export interface Transformer<in TInput, out TOutput> {
  transform(value: TInput): TOutput;
}

// 2. Union to Intersection Engine
export type UnionToIntersection<U> = 
  (U extends unknown ? (k: U) => void : never) extends (k: infer I) => void 
    ? I 
    : never;

// Verification Test Suite
type EventA = { readonly type: "A"; payload: { readonly id: string } };
type EventB = { readonly type: "B"; payload: { readonly count: number } };

type EventsUnion = EventA | EventB;
type IntersectedEvents = UnionToIntersection<EventsUnion>;
// Equivalent to: EventA & EventB (Memaksa objek memenuhi kedua kontrak tipe)
```

#### 7.2 Practical Example: Type-Safe Dynamic Query Builder Engine
Pola arsitektur query builder tingkat enterprise yang memvalidasi ketersediaan kolom, inferensi tipe hasil seleksi kolom secara inkremental, dan mencegah mutasi runtime (*zero overhead compile-time tracking*):

```typescript
// Core Utility Types
export type Normalize<T> = { [K in keyof T]: T[K] } & {};

export type DeepReadonly<T> = T extends Function | boolean | number | string | symbol | null | undefined
  ? T
  : T extends Array<infer U>
  ? ReadonlyArray<DeepReadonly<U>>
  : { readonly [K in keyof T]: DeepReadonly<T[K]> };

// Schema Definition Interface
export type TableSchema = Record<string, unknown>;

// Builder State Tracker
export class QueryBuilder<
  TSchema extends TableSchema,
  TSelected extends TableSchema = {}
> {
  private readonly selectedColumns: Set<string>;

  public constructor(
    private readonly tableName: string,
    selectedColumns?: Set<string>
  ) {
    this.selectedColumns = selectedColumns ?? new Set<string>();
  }

  // Select method enforces K must be an available key of TSchema
  // Accumulates keys into TSelected state
  public select<K extends keyof TSchema>(
    column: K
  ): QueryBuilder<TSchema, Normalize<TSelected & { [P in K]: TSchema[P] }>> {
    const updated = new Set(this.selectedColumns);
    updated.add(String(column));
    return new QueryBuilder<TSchema, Normalize<TSelected & { [P in K]: TSchema[P] }>>(
      this.tableName,
      updated
    );
  }

  // Where clause guarantees strict typing on column value comparison
  public where<K extends keyof TSchema>(
    column: K,
    operator: "=" | "!=" | ">" | "<",
    value: TSchema[K]
  ): this {
    // Runtime SQL abstraction logic omitted for brevity
    return this;
  }

  // Execute builds the output payload using the exact accumulated types
  public execute(): Promise<ReadonlyArray<TSelected>> {
    const cols = Array.from(this.selectedColumns).join(", ") || "*";
    const query = `SELECT ${cols} FROM ${this.tableName};`;
    // Simulation of runtime execution
    return Promise.resolve([] as ReadonlyArray<TSelected>);
  }
}

// Enterprise Usage Demonstration
interface UserTable {
  id: string;
  tenantId: string;
  email: string;
  age: number;
  metadata: { roles: string[] };
}

async function runQuery() {
  const query = new QueryBuilder<UserTable>("users")
    .select("id")
    .select("email")
    .where("age", ">", 21);

  // Return type is strictly Promise<ReadonlyArray<{ id: string; email: string }>>
  const result = await query.execute();
  return result;
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### 8.1 Konteks Masalah
Perusahaan FinTech Tier-1 membutuhkan infrastruktur CQRS (*Command Query Responsibility Segregation*) Message Bus yang menghubungkan ribuan microservices. Masalah yang dihadapi:
1.  Developer sering mengirim payload event yang tidak cocok dengan definisi Command/Event handler, yang baru terdeteksi saat *runtime* (menyebabkan transaksi perbankan anjlok).
2.  Infrastruktur lama mengandalkan `Record<string, any>`, menyebabkan runtuhnya *type-safety boundary*.
3.  Type-checker berjalan lambat pada CI/CD (> 15 menit) karena komputasi struktural ribuan tipe event tanpa optimasi *variance*.

#### 8.2 Solusi Arsitektur
Membangun *Parametrically-Polymorphic CQRS Event Bus* menggunakan:
*   *Type-level Defunctionalization Registry* (Emulasi HKT untuk generic execution context).
*   *Explicit Variance Annotations* untuk optimasi kecepatan kompilasi.
*   *Branded Types* untuk menjamin integritas identifier.

```typescript
// ==========================================
// 1. BRANDED TYPES & BASE TYPES
// ==========================================
declare const BrandSymbol: unique symbol;
export type Branded<T, TBrand extends string> = T & { readonly [BrandSymbol]: TBrand };

export type AggregateId = Branded<string, "AggregateId">;
export type CorrelationId = Branded<string, "CorrelationId">;

export interface MessageMetadata {
  readonly correlationId: CorrelationId;
  readonly timestamp: number;
}

// ==========================================
// 2. HIGHER-KINDED TYPE (HKT) EMULATION INFRASTRUCTURE
// ==========================================
export interface HKT {
  readonly _URI: unknown;
  readonly _A: unknown;
}

export type Kind<F extends HKT, A> = F extends { readonly _URI: infer URI }
  ? URItoKind<A>[URI & keyof URItoKind<any>]
  : never;

// Interface Registry (Merged globally in application layers)
export interface URItoKind<A> {
  readonly PromiseURI: Promise<A>;
  readonly TaskResultURI: () => Promise<A>;
}

// ==========================================
// 3. MESSAGE CONTRACTS & EXPLICIT VARIANCE
// ==========================================
export interface Message<out TType extends string, out TPayload> {
  readonly type: TType;
  readonly payload: TPayload;
  readonly metadata: MessageMetadata;
}

// Consumer is strictly contravariant on TMessage
export interface MessageHandler<in TMessage extends Message<string, unknown>, out TReturn> {
  handle(message: TMessage): TReturn;
}

// ==========================================
// 4. STRONGLY-TYPED CQRS BUS
// ==========================================
export class StronglyTypedEventBus<
  TRegisteredMessages extends Message<string, unknown>
> {
  private readonly handlers = new Map<string, Array<MessageHandler<any, any>>>();

  // Subscribe uses strict contravariant matching
  public registerHandler<TTargetType extends TRegisteredMessages["type"]>(
    type: TTargetType,
    handler: MessageHandler<
      Extract<TRegisteredMessages, { readonly type: TTargetType }>,
      Promise<void>
    >
  ): void {
    const existing = this.handlers.get(type) ?? [];
    existing.push(handler);
    this.handlers.set(type, existing);
  }

  // Dispatch ensures compile-time check that only valid messages are sent
  public async dispatch<TActualMessage extends TRegisteredMessages>(
    message: TActualMessage
  ): Promise<void> {
    const registered = this.handlers.get(message.type);
    if (!registered || registered.length === 0) {
      throw new Error(`HandlerNotRegisteredError: Event ${message.type} has no consumers.`);
    }

    await Promise.all(registered.map((handler) => handler.handle(message)));
  }
}

// ==========================================
// 5. DOMAIN MODULE IMPLEMENTATION
// ==========================================
export interface TransferFundsCommand extends Message<
  "BANKING.TRANSFER_FUNDS",
  {
    readonly sourceAccount: AggregateId;
    readonly targetAccount: AggregateId;
    readonly amountCents: bigint;
  }
> {}

export interface AuditLogEmittedEvent extends Message<
  "AUDIT.LOG_EMITTED",
  {
    readonly logId: string;
    readonly details: string;
  }
> {}

// Aggregate App Events
export type BankingAppMessages = TransferFundsCommand | AuditLogEmittedEvent;

// Production Instantiation
export const enterpriseBus = new StronglyTypedEventBus<BankingAppMessages>();

// Handler Definition
const transferHandler: MessageHandler<TransferFundsCommand, Promise<void>> = {
  async handle(message) {
    console.log(`Processing transfer: ${message.payload.amountCents.toString()}`);
  }
};

// Register & Dispatch Validations
enterpriseBus.registerHandler("BANKING.TRANSFER_FUNDS", transferHandler);

// Compile-Time Safety Verification:
// Skenario 1: Dispatch valid payload
void enterpriseBus.dispatch<TransferFundsCommand>({
  type: "BANKING.TRANSFER_FUNDS",
  payload: {
    sourceAccount: "acc-001" as AggregateId,
    targetAccount: "acc-002" as AggregateId,
    amountCents: 10000000n
  },
  metadata: {
    correlationId: "corr-xyz" as CorrelationId,
    timestamp: Date.now()
  }
});

// Skenario 2: KODE BERIKUT AKAN GAGAL PADA TAHAP KOMPILASI (Type Check Error)
// enterpriseBus.dispatch({
//   type: "UNKNOWN_EVENT", // TS2344: Argument type not assignable
//   payload: {}
// });
```

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan (*Pros*) | Kerugian / Risiko (*Cons*) | Mitigasi Solutif |
| :--- | :--- | :--- | :--- |
| **Deep Recursive Conditional Types** | Dapat memparsing dan mentransformasi struktur bersarang tak terbatas (misal: JSON parsing statis). | Memicu error *instantiation depth* (TS2589) dan menaikkan waktu *build* secara eksponensial. | Terapkan teknik *Tail-Call Elimination* menggunakan pola akumulator tuple tipe. |
| **Explicit Variance (`in`/`out`)** | Peningkatan performa kompilasi 10%-30% pada type-checker monorepo; tipe lebih self-documenting. | Kesalahan penempatan anotasi memicu error TS1079 (`Variance annotation cannot be satisfied`). | Gunakan hanya pada interface inti (*core design system/framework contracts*). |
| **Lightweight HKT Emulation** | Memungkinkan abstraksi fungsional murni tingkat tinggi (Functor, Monad, Applicative) di TS. | Sintaks rumit (*boilerplate* URI registration), steep learning curve bagi tim pemula. | Batasi penggunaannya di layer arsitektur *infrastructure/core-sdk*, bukan di domain feature logic. |
| **Nominal Branded Types** | Mencegah bug fatal tertukarnya data primitif (misal: `UserId` dengan `OrderId`). | Mengharuskan explicit casting (`as UserId`) di input boundaries; runtime overhead serialisasi JSON. | Gunakan factory function atau library validasi schema (misal: Zod/TypeBox) di layer I/O. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Evaluasi Terdistribusi yang Tidak Disengaja pada `never`
**Kasus Kesalahan:**
```typescript
type IsNever<T> = T extends never ? true : false;

type Result = IsNever<never>; // Mengembalikan: never (Bukan true!)
```
**Mengapa Terjadi:** `never` adalah *empty union* (serikat tanpa anggota). Karena `T` berada dalam bentuk naked type parameter, TypeScript mendistribusikan ekspresi. Operasi pada himpunan kosong menghasilkan himpunan kosong (`never`).
**Solusi:** Matikan distributivitas dengan tuple boundary.
```typescript
type IsNeverFixed<T> = [T] extends [never] ? true : false;
type FixedResult = IsNeverFixed<never>; // true
```

#### 10.2 Type Instantiation Exceeds Depth Limit (TS2589)
**Kasus Kesalahan:**
Membuat generic string-splitter tanpa optimasi akumulasi:
```typescript
type Split<S extends string, D extends string> = 
  S extends `${infer Head}${D}${infer Tail}`
    ? [Head, ...Split<Tail, D>] // Non-tail-recursive!
    : [S];
```
Jika string memiliki panjang > 50 token, tsc akan melempar: `Type instantiation is excessively deep and possibly infinite. (2589)`.

**Solusi:** Gunakan pola akumulator *Tail-Call Optimization* (TCO) di type-level:
```typescript
type SplitTCO<
  S extends string, 
  D extends string, 
  TAcc extends readonly string[] = []
> = S extends `${infer Head}${D}${infer Tail}`
  ? SplitTCO<Tail, D, [...TAcc, Head]>
  : [...TAcc, S];
```

#### 10.3 Kebocoran Posisi Varian (Variance Leak)
Mendeklarasikan interface kovarian namun mengekspos argumen method secara kontravarian:
```typescript
// Error TS1079: Type parameter 'T' is declared as 'out' but occurs in 'in' position.
interface Repository<out T> {
  save(item: T): void; // ERROR: T berada di posisi argumen (in)
}

// Perbaikan: Ubah menjadi invariant atau pisahkan tanggung jawab
interface ReadRepository<out T> {
  findById(id: string): T | null;
}
interface WriteRepository<in T> {
  save(item: T): void;
}
```

---

### 11. Best Practices (Production Checklist)

*   [ ] **Aktifkan Strict Mode Penuh**: Wajib menyertakan `"strict": true` dan `"strictFunctionTypes": true` di `tsconfig.json`. Tanpa ini, parameter fungsi menjadi bivariant yang merusak *soundness*.
*   [ ] **Gunakan Anotasi Variance pada Generic Core**: Tambahkan `out` atau `in` pada generic container, state machine, dan micro-framework abstractions guna memangkas durasi kompilasi.
*   [ ] **Cegah Distributivitas tak Terduga**: Bungkus argumen type parameter dengan `[T]` jika tujuannya adalah memeriksa struktur tipe secara atomik, bukan memecah tipe union.
*   [ ] **Batas Akumulasi Tuple**: Jangan menggunakan tuple rekursif untuk iterasi berskala di atas 1000 iterasi statis. Evaluasi batasan kedalaman tipe engine TS.
*   [ ] **Zero-Cost Abstractions**: Pastikan tipe generic kompleks di-strip habis saat kompilasi ke JS tanpa menyisakan jejak performa CPU runtime, kecuali untuk kebutuhan refleksi metadata yang disengaja.
*   [ ] **Gunakan Branded Types untuk Id Primitif**: Selalu proteksi parameter kritis (`tenantId`, `userId`, `amount`) menggunakan nominal type pattern guna menghindari bug logika akibat kompatibilitas struktural primitive string/number.

---

### 12. Hands-on Practice

Buat repositori mini praktikum secara lokal untuk menguji seluruh materi dengan mengikuti instruksi direktori berikut:

```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install typescript @types/node tsx --save-dev
npx tsc --init --strict true --target ES2022 --moduleResolution NodeNext --module NodeNext
```

#### File: `hands-on/m02/task.ts`
Implementasikan kode produksi di bawah ini:

```typescript
/**
 * HANDS-ON PRACTICE: Production-Grade Type-Safe Event Store
 * Target: Mengimplementasikan State Reducer dengan Type Extraction Kontravarian
 */

// 1. Core Domain Types
export type Action<TType extends string, TPayload> = {
  readonly type: TType;
  readonly payload: TPayload;
};

// 2. Sample Domain Actions
export type IncrementAction = Action<"INCREMENT", { readonly step: number }>;
export type DecrementAction = Action<"DECREMENT", { readonly step: number }>;
export type ResetAction = Action<"RESET", { readonly defaultCounter: number }>;

export type CounterActions = IncrementAction | DecrementAction | ResetAction;

export interface CounterState {
  readonly count: number;
}

// 3. Type-Safe Reducer Map Contract
// Mapping type-safe actions secara eksklusif ke handler fungsinya
export type ReducerMap<TState, TActions extends Action<string, any>> = {
  readonly [A in TActions as A["type"]]: (
    state: TState,
    action: A
  ) => TState;
};

// 4. State Machine Implementation
export class StateMachine<TState, TActions extends Action<string, any>> {
  public constructor(
    private currentState: TState,
    private readonly reducers: ReducerMap<TState, TActions>
  ) {}

  public dispatch<TDispatchedAction extends TActions>(action: TDispatchedAction): TState {
    const handler = this.reducers[action.type as TActions["type"]];
    if (!handler) {
      throw new Error(`Unhandled action type: ${action.type}`);
    }
    this.currentState = handler(this.currentState, action);
    return this.currentState;
  }

  public getState(): TState {
    return this.currentState;
  }
}

// 5. Instantiation Verification
const initialCounterState: CounterState = { count: 0 };

const counterReducers: ReducerMap<CounterState, CounterActions> = {
  INCREMENT: (state, action) => ({ count: state.count + action.payload.step }),
  DECREMENT: (state, action) => ({ count: state.count - action.payload.step }),
  RESET: (state, action) => ({ count: action.payload.defaultCounter })
};

const counterMachine = new StateMachine(initialCounterState, counterReducers);

// Verification execution
console.log("Initial:", counterMachine.getState());
counterMachine.dispatch<IncrementAction>({ type: "INCREMENT", payload: { step: 5 } });
console.log("After Increment:", counterMachine.getState());
counterMachine.dispatch<ResetAction>({ type: "RESET", payload: { defaultCounter: 100 } });
console.log("After Reset:", counterMachine.getState());
```

Jalankan menggunakan `tsx`:
```bash
npx tsx hands-on/m02/task.ts
```

---

### 13. Exercises

#### 13.1 Level Easy: Strict Deep Non-Nullable
Buat utilitas tipe `DeepNonNullable<T>` yang secara rekursif menghapus tipe `null` dan `undefined` dari seluruh level properti objek hingga ke level primitif, termasuk array.
*   **Kriteria Keberhasilan**: Objek bertingkat `{ a: string | null; b: { c: number | undefined }[] }` berubah secara ketat menjadi `{ a: string; b: { c: number }[] }`.

#### 13.2 Level Medium: Curry Function Type Engine
Definisikan signature tipe generik untuk fungsi pembantu `curry` yang mendukung fungsi arbitrer hingga 4 parameter:
```typescript
declare function curry<A, B, C, D, R>(
  fn: (a: A, b: B, c: C, d: D) => R
): (a: A) => (b: B) => (c: C) => (d: D) => R;
```
Implementasikan pula dukungan partial curry menggunakan tuple rest generics: `Curry<Args, Return>`.
*   **Kriteria Keberhasilan**: Pemanggilan `curried(1)(true)("foo")` harus memvalidasi kesesuaian tipe argumen pada masing-masing nesting level secara presisi tanpa bypass ke `any`.

#### 13.3 Level Hard: JSON Path Navigation Inferrer
Bangun utilitas tipe `Path<T>` dan `PathValue<T, P extends Path<T>>`. Utilitas ini harus menghasilkan *union string literal* yang valid dari path properti bersarang menggunakan dot-notation (misal: `"user.profile.address.zipCode"`), serta mampu menginferensikan nilai yang berada di path tersebut.
*   **Kriteria Keberhasilan**: Type checker wajib mengeluarkan autocomplete dan menolak path yang salah saat diakses via function: `get(obj, "user.invalid.path")`.

---

### 14. Challenge

#### Skenario Kasus: Zero-Overhead Compile-Time Router & Request Pipeline
Perusahaan Anda sedang merancang framework micro-web internal. Anda ditugaskan membangun sistem registrasi rute yang memiliki spesifikasi arsitektur sebagai berikut:

1.  **URL Parameter Pattern Inferrer**: Format rute didefinisikan sebagai string template, contoh: `/api/v1/tenants/:tenantId/users/:userId/roles/:roleId`.
2.  **Autonomous Extraction**: Sistem tipe harus otomatis mengekstrak seluruh parameter bertanda `:param` menjadi bentuk *strongly typed object*:
    ```typescript
    { tenantId: string; userId: string; roleId: string }
    ```
3.  **Strict Middleware Pipeline Composition**: Middleware dapat menambahkan konteks tipe baru secara berantai (*chaining*). Misalnya, `AuthMiddleware` menambahkan tipe `{ user: AuthenticatedUser }`, lalu diteruskan ke `TelemetryMiddleware` yang menambahkan `{ traceId: string }`.
4.  **Terminal Route Handler**: Handler rute wajib menerima gabungan tipe (`Route Params` & seluruh `Middleware Context`) secara deterministik, tanpa menggunakan manipulasi runtime berlebih ataupun *type assertion* manual (`as ...`).
5.  **Batasan Arsitektural**:
    *   Tidak boleh menimbulkan rekursi tanpa batas jika pola rute memiliki panjang lebih dari 10 segment.
    *   Wajib menangani parsing wildcard `*catchall`.
    *   Tidak boleh menggunakan modul pihak ketiga (murni *pure TypeScript* type engine).

---

### 15. Quiz Evaluasi Pemahaman

#### 15.1 Bagian 1: Basic (5 Soal)

**Q1: Apa implikasi dari anotasi `out` pada deklarasi interface `interface DataSink<out T> {}`?**
*   A. `T` dipaksa berada di posisi argumen method.
*   B. Kompilator memperlakukan `T` secara kovarian, memastikan `T` hanya digunakan pada posisi output/return value.
*   C. Nilai `T` dikeluarkan secara otomatis dari memori saat runtime.
*   D. Mematikan fungsi type checking untuk interface tersebut.
*   *Jawaban yang benar*: B. Anotasi `out` menandai bahwa type parameter tersebut adalah kovarian (hanya untuk tipe keluaran).

**Q2: Mengapa conditional type `T extends string ? true : false` berpotensi mengevaluasi secara distributif?**
*   A. Karena TypeScript selalu mendistribusikan semua conditional statement.
*   B. Karena `T` adalah *naked type parameter* tanpa pembungkus seperti tuple.
*   C. Karena string adalah primitive type.
*   D. Karena opsi `strictNullChecks` dinyalakan.
*   *Jawaban yang benar*: B. Distributivitas hanya terjadi secara otomatis apabila target type parameter pada sisi kiri klausul `extends` merupakan naked type parameter.

**Q3: Kapan hubungan subtipe bersifat kontravarian?**
*   A. Pada nilai return sebuah fungsi asynchronous.
*   B. Pada deklarasi properti array read-only.
*   C. Pada posisi tipe argumen fungsi (di bawah konfigurasi `strictFunctionTypes: true`).
*   D. Pada saat inheritance class biasa.
*   *Jawaban yang benar*: C. Argumen fungsi membalik arah hierarki subtipe (kontravarian).

**Q4: Apa tujuan penggunaan keyword `infer` dalam sistem tipe TypeScript?**
*   A. Mendeklarasikan variabel baru di level runtime JavaScript.
*   B. Memaksa kompilator melakukan type assertion.
*   C. Memperkenalkan variabel tipe baru untuk diekstrak secara otomatis di dalam blok conditional types.
*   D. Menimpa deklarasi interface secara global.
*   *Jawaban yang benar*: C. `infer` digunakan di dalam klausul `extends` conditional types untuk mendeklarasikan type variable yang polanya akan dicocokkan dan diekstrak oleh engine.

**Q5: Apa fungsi dari teknik Branded Types (atau Nominal Typing Simulation)?**
*   A. Mengubah eksekusi TypeScript menjadi berorientasi Java byte-code.
*   B. Membedakan dua tipe data yang memiliki struktur bentuk primitif identik agar tidak dapat saling ditukar secara sengaja saat compile-time.
*   C. Menambahkan hak cipta pada interface open-source.
*   D. Mempercepat eksekusi V8 engine.
*   *Jawaban yang benar*: B. Mencegah substitusi tidak valid antara dua tipe data yang secara struktural sama (misalnya dua string ID yang berbeda domain).

---

#### 15.2 Bagian 2: Intermediate (5 Soal)

**Q6: Perhatikan kode berikut. Apa hasil dari evaluasi tipe `Check`?**
```typescript
type Box<T> = [T] extends [string | number] ? true : false;
type Check = Box<string | boolean>;
```
*   A. `true`
*   B. `false`
*   C. `boolean` (alias `true | false`)
*   D. `never`
*   *Jawaban yang benar*: B. Karena dibungkus dengan tanda kurung siku `[T]`, distributivitas dinonaktifkan. Serikat `string | boolean` dievaluasi secara monolitik terhadap `string | number`. Karena `boolean` bukan bagian dari `string | number`, hasilnya langsung `false`.

**Q7: Mengapa inferensi dari posisi parameter argumen fungsi menghasilkan *Intersection*, sedangkan inferensi dari posisi nilai balik menghasilkan *Union*?**
*   A. Karena TypeScript checker mengimplementasikan logika bug historis.
*   B. Sifat kovarian pada return value mengumpulkan seluruh kemungkinan nilai hasil (Union), sedangkan sifat kontravarian pada argumen menuntut tipe input yang dapat memuaskan seluruh varian kontraktual secara simultan (Intersection).
*   C. Karena argumen fungsi dianalisis lebih dahulu daripada return value.
*   D. Karena return value bersifat bivariant.
*   *Jawaban yang benar*: B. Posisi kontravarian argumen memaksakan resolusi lower-bound yang harus kompatibel dengan seluruh kandidat tipe, menghasilkan Intersection.

**Q8: Masalah apa yang dipecahkan oleh *Lightweight Higher-Kinded Polymorphism* pada TypeScript?**
*   A. Mengizinkan TypeScript berjalan langsung tanpa dikompilasi ke JavaScript.
*   B. Memungkinkan representasi abstraksi tipe generik yang menerima generik lain sebagai argumen (seperti `F<A>`) tanpa *native HKT syntax support*.
*   C. Menghapus batasan ukuran file output `.js`.
*   D. Mengganti penggunaan asynchronous Promise.
*   *Jawaban yang benar*: B. TypeScript tidak mengizinkan generic type parameter dideklarasikan tanpa type argument (misal: `class Container<F<_>>`). Pola lightweight HKT mengatasi keterbatasan ini menggunakan type defunctionalization dictionary.

**Q9: Apa konsekuensi arsitektural dari penggunaan tipe rekursif tanpa basis akumulator *tail-call*?**
*   A. Ukuran bundle JavaScript membesar secara drastis.
*   B. Error kode kompilator TS2589 (rekursi tak terhingga) ketika kedalaman parsing tipe melebihi batas batas ambang kompilator.
*   C. Terjadinya memory leak pada runtime Node.js.
*   D. Kehilangan dukungan fitur IntelliSense di VS Code selamanya.
*   *Jawaban yang benar*: B. Kompilator TypeScript memiliki batas rekursi evaluasi tipe internal. Tanpa pola tail-call, tree evaluasi bertumpuk dan menabrak batasan instansiasi.

**Q10: Mengapa deklarasi berikut melempar compile-error TS1079?**
```typescript
interface Processor<in T> {
  process(): T;
}
```
*   A. Karena `T` tidak memiliki batasan `extends object`.
*   B. Karena `process` bukan method async.
*   C. Karena `T` dianotasikan sebagai kontravarian (`in`), tetapi posisinya berada pada return type method (posisi kovarian).
*   D. Karena keyword `Processor` tidak terdaftar.
*   *Jawaban yang benar*: C. Return type method adalah posisi kovarian (`out`). Menandai tipe tersebut sebagai `in` (kontravarian) melanggar aturan matematis type variance yang divalidasi oleh kompilator.

---

#### 15.3 Bagian 3: Production Scenarios (3 Soal Kasus)

**Skenario Kasus 1:**
Sebuah pipeline CI/CD monorepo enterprise mengalami lonjakan durasi type-checking dari 3 menit menjadi 22 menit setelah tim mengintegrasikan library API Client baru yang memiliki puluhan generic wrapper bersarang. Hasil profil menggunakan `tsc --extendedDiagnostics` menunjukkan waktu habis di bagian *Check time* dan jutaan *Instantiations*.
*Identifikasi penyebab utama masalah ini dan langkah arsitektural yang paling efektif untuk mengatasinya.*

*   *Analisis Solusi*: 
    Kompilator terjebak dalam *deep structural variance calculation* pada struktur data generic yang masif dan bertingkat. Setiap kali tipe wrapper digunakan, kompilator membongkar seluruh pohon hierarki properti untuk memastikan subtyping.
    *Tindakan*:
    1. Tambahkan anotasi explicit variance (`in` / `out`) pada seluruh core interface generic wrapper di library API Client. Hal ini memotong jalur kalkulasi struktural kompilator menjadi sekadar pengecekan penanda (*nominal-speed fast path*).
    2. Hindari pembentukan intermediate mapped types bersarang di dalam loop resolusi method client.

**Skenario Kasus 2:**
Arsitek perangkat lunak Anda menemukan bahwa pengecekan otorisasi berbasis Role-Based Access Control (RBAC) bocor di tingkat tipe:
```typescript
type Role = "ADMIN" | "USER" | "ANONYMOUS";
function authorize<T extends Role>(requiredRole: T, currentRole: Role): boolean {
  return currentRole === requiredRole;
}
```
Ketika developer memanggil `authorize("ADMIN", "ANONYMOUS" as Role)`, sistem mengizinkannya secara kompilasi, padahal `currentRole` seharusnya diuji menggunakan generic narrowing yang ketat terhadap session pengguna.
*Bagaimana mendesain ulang generic signature fungsi ini agar parameter kedua hanya dapat menerima peran yang setara atau lebih spesifik dari parameter pertama?*

*   *Analisis Solusi*:
    Gunakan pemetaan hierarki peran berbasis relasi subtipe terbalik dengan Generic Bounds:
    ```typescript
    type RoleHierarchy = {
      ANONYMOUS: "ANONYMOUS";
      USER: "ANONYMOUS" | "USER";
      ADMIN: "ANONYMOUS" | "USER" | "ADMIN";
    };

    function authorizeStrict<
      TRequired extends Role, 
      TCurrent extends RoleHierarchy[TRequired]
    >(requiredRole: TRequired, currentRole: TCurrent): boolean {
      return requiredRole === currentRole;
    }
    ```
    Dengan desain ini, jika peran yang dibutuhkan adalah `"ADMIN"`, argumen kedua hanya valid jika memiliki sub-bagian dari union hierarki `"ADMIN"`.

**Skenario Kasus 3:**
Sebuah modul Event-Sourcing memiliki fungsi `replayEvents` yang menerima array heterogen dari berbagai event yang pernah terjadi. Ketika fungsi memproses array tersebut:
```typescript
const events: Array<EventA | EventB> = loadEvents();
```
Developer ingin memetakan array ini ke sebuah state accumulator. Namun, type guard `event is EventA` gagal mempersempit scope tipe jika dipanggil di dalam fungsi generic iterator dinamis karena hilangnya indeks diskriminator.
*Bagaimana merancang tipe Generic Filter Engine yang mempertahankan tipe konkrete melalui Higher-Order Functions?*

*   *Analisis Solusi*:
    Gunakan Generic Type Guard berbasiskan kombinasi `Extract` dan parameter type predicate:
    ```typescript
    export function filterEvents<
      TAllEvents extends { readonly type: string },
      TTargetType extends TAllEvents["type"]
    >(
      events: ReadonlyArray<TAllEvents>,
      targetType: TTargetType
    ): Array<Extract<TAllEvents, { readonly type: TTargetType }>> {
      return events.filter(
        (event): event is Extract<TAllEvents, { readonly type: TTargetType }> => 
          event.type === targetType
      );
    }
    ```
    Pola ini memanfaatkan `Extract` yang mendistribusikan union event dan mengekstrak varian yang memiliki diskriminator `type` yang cocok secara presisi, lalu mengembalikannya sebagai array dari tipe konkret tersebut.

---

### 16. Summary

1.  **Parametric Polymorphism di TypeScript** bukan sekadar syntactic sugar untuk interface fleksibel, melainkan sistem pembuktian matematis berbasis *structural type equivalence* yang dievaluasi melalui fase parsing, binding, instansiasi, dan checking.
2.  **Mekanisme Variansi** mendikte bagaimana subtipe berinteraksi:
    *   **Kovariansi (`out`)**: Menjaga arah relasi subtipe (posisi keluaran).
    *   **Kontravariansi (`in`)**: Membalikkan arah relasi subtipe (posisi masukan).
    *   Anotasi eksplisit `in`/`out` adalah kunci untuk mengoptimalkan waktu kompilasi monorepo berskala besar.
3.  **Distributive Conditional Types** secara otomatis mendistribusikan operasi kondisi pada naked union types. Pembungkusan dengan tuple (`[T] extends [U]`) wajib digunakan jika menginginkan pencocokan tipe atomik atau evaluasi terhadap `never`.
4.  **Inferensi Kontravarian** memungkinkan pembalikan tipe mutlak seperti *Union to Intersection*, membuka kapabilitas metaprogramming tingkat lanjut yang sebelumnya mustahil dilakukan secara deklaratif.
5.  **Higher-Kinded Types (HKT)** dapat diemulasikan secara aman tanpa runtime penalty menggunakan teknik *Lightweight Higher-Kinded Polymorphism* berbasis defunctionalization token dictionary.
6.  **Optimasi Kompiler**: Desain generic yang buruk dapat dengan mudah memicu error TS2589 dan memperlambat sistem build CI/CD. Terapkan pola *Tail-Call Optimization* pada level tipe dengan akumulator tuple untuk menjamin efisiensi evaluasi type checker.