# SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 02-Programming-Languages
* **Topik/Modul:** Advanced Generics & Parametric Polymorphism
* **Kode Modul:** TS-ADV-04-01
* **Tingkat Kesulitan:** Advanced / Enterprise-Grade
* **Prasyarat Pengetahuan:**
  * Pemahaman mendalam mengenai TypeScript Type System dasar (Primitive Types, Structural Typing, Union & Intersection Types).
  * Pemahaman konsep dasar Generic Types (`<T>`) dan Generic Constraints (`extends`).
  * Konsep dasar fungsional: Higher-Order Functions, Pure Functions, dan Immutability.
* **Estimasi Waktu Penyelesaian:** 120 – 180 Menit

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Mengonseptualisasikan** Generic sebagai fungsi murni pada level tipe (*Type-level Pure Functions*) dan membedakan *Parametric Polymorphism* dari *Subtype Polymorphism* serta *Ad-hoc Polymorphism*.
2. **Menganalisis dan Membedah** varians sistem tipe (Covariance, Contravariance, Invariance, dan Bivariance) dalam konteks TypeScript generic types dan function parameters.
3. **Mengimplementasikan** pola-pola generik lanjutan, termasuk *F-Bounded Quantification* (Recursive Generic Constraints), *Higher-Order Type Abstractions*, dan *Distributed Conditional Generics*.
4. **Membangun** pipeline arsitektur mediator/CQRS yang sepenuhnya type-safe dengan inferensi tipe otomatis tanpa *type assertion* (`as`).
5. **Mendiagnosis dan Mengoptimasi** performa kompilasi TypeScript (*type-checking performance*) dari ledakan tipe (*type instantiation explosion*) akibat rekursi dan evaluasi serikat (*union distribution*).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Tipe adalah Set; Generics adalah Komputasi Set

Dalam eksekusi runtime, program memanipulasi nilai (*values*). Pada fase kompilasi TypeScript, Type Checker memanipulasi set nilai (*sets of values*). Ketika Anda menulis tipe konkret seperti `string`, Anda mendefinisikan set tak hingga dari semua rangkaian karakter yang valid.

Parametric Polymorphism memungkinkan penulisan logika yang independen terhadap tipe konkret yang mendasarinya. Mental model yang tepat untuk memahaminya:

$$\text{Type Function} : \mathbb{T} \rightarrow \mathbb{T}$$

Generic bukan sekadar *placeholder* teks atau makro C++ (`#define` / template expansion). Generic adalah abstraksi matematika di mana tipe parameter bertindak sebagai argumen bagi fungsi tingkat tipe (*type-level function*).

```
Runtime Level:  f(x: Value): Value
Type Level:     F<T: Type>: Type
```

### Taksonomi Polimorfisme (Cardelli & Wegner)

1. **Parametric Polymorphism:** Logika identik dieksekusi secara seragam pada berbagai tipe tanpa bergantung pada informasi struktural tipe tersebut (misal: `Array<T>`).
2. **Subtype Polymorphism (Inclusion):** Sebuah fungsi mengeksekusi tipe yang berbeda melalui relasi hierarki substitusi (Liskov Substitution Principle).
3. **Ad-hoc Polymorphism (Overloading):** Logika algoritma berbeda dieksekusi berdasarkan tipe argumen konkret yang dilewatkan.

TypeScript Advanced Generics menggabungkan **Parametric Polymorphism** murni dengan batasan struktural (*bounded parametric polymorphism* via `T extends Constraint`), menjembatani fleksibilitas parametrik dengan kepastian bentuk objek (*structural shape guarantees*).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Mekanisme resolusi Generic pada TypeScript Compiler (Tsc) dapat digambarkan melalui tahapan pipeline inferensi dan validasi tipe berikut:

```
[ Pemanggilan Generic Function / Instansiasi Type ]
                    │
                    ▼
     ┌──────────────────────────────┐
     │ 1. Syntactic AST Analysis    │
     │    Ekstraksi Type Parameter  │
     └──────────────┬───────────────┘
                    │
                    ▼
     ┌──────────────────────────────┐
     │ 2. Type Inference Engine     │
     │    Menentukan kandidat T dari│
     │    argumen nilai runtime     │
     └──────────────┬───────────────┘
                    │
                    ▼
     ┌──────────────────────────────┐      Tidak Lolos
     │ 3. Constraint Check          ├────────────────────────┐
     │    Validasi: T extends Base? │                        │
     └──────────────┬───────────────┘                        │
                    │ Lolos                                  ▼
                    ▼                          ┌───────────────────────────┐
     ┌──────────────────────────────┐          │ Emit Compilation Error    │
     │ 4. Type Substitution         │          │ Type 'X' does not satisfy │
     │    Pembuatan TypeMapper &    │          │ constraint 'Y'            │
     │    Instansiasi Tipe Spesifik │          └───────────────────────────┘
     └──────────────┬───────────────┘
                    │
                    ▼
     ┌──────────────────────────────┐
     │ 5. Variance Resolution       │
     │    (Co/Contra/In-variant)    │
     │    Pemeriksaan Kompatibilitas│
     └──────────────┬───────────────┘
                    │
                    ▼
     ┌──────────────────────────────┐
     │ 6. Output Type Cache         │
     │    Menyimpan hasil evaluasi  │
     │    ke Type Cache             │
     └──────────────────────────────┘
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Internal Tsc: `TypeChecker`, `TypeMapper`, dan `Instantiation`

Ketika TypeScript memeriksa generic, proses internal berikut dieksekusi oleh mesin kompilator:

1. **Type Parameters as Symbols:** Setiap generic parameter `<T>` dialokasikan sebagai `TypeSymbol` yang memiliki `TypeFlags.TypeParameter`.
2. **TypeMapper:** Kompilator merepresentasikan substitusi menggunakan struktur data internal `TypeMapper`. Ketika generic diinstansiasi (misalnya `List<string>`), compiler membuat pemetaan:
   $$\text{Map}: [T \mapsto \text{string}]$$
3. **Lazy Instantiation:** TypeScript tidak menghasilkan salinan kode JavaScript untuk setiap instansiasi generic (berbeda dengan monomorphization pada Rust atau C++ templates). Di JavaScript runtime, seluruh parameter tipe dihapus sepenuhnya (*Type Erasure*).
4. **Instantiation Cache:** Untuk menjaga efisiensi algoritma, instansiasi tipe yang sama (misal `Map<string, number>`) dicache secara global di memori kompilator berdasarkan identitas referensi parameter tipe.
5. **Recursion Depth Limit:** Tsc membatasi rekursi instansiasi generic (biasanya 50–100 tingkat kedalaman stack) untuk mencegah loop kompilasi tak hingga akibat *F-bounded polymorphism* atau *recursive conditional types*.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Varians Sistem Tipe: Covariance, Contravariance, Invariance, Bivariance

Varians menjelaskan bagaimana kompatibilitas subtyping dari tipe komponen memengaruhi subtyping dari tipe komposit yang membungkusnya.

Misalkan $Sub \le Super$ menyatakan bahwa $Sub$ adalah subtype dari $Super$:

* **Covariance ($F\langle Sub \rangle \le F\langle Super \rangle$):**
  Arah subtipe dipertahankan. Jika `Dog` adalah subtype dari `Animal`, maka `Producer<Dog>` adalah subtype dari `Producer<Animal>`. TypeScript bersifat kovarian pada nilai *read-only* dan *return type* dari fungsi.
* **Contravariance ($F\langle Super \rangle \le F\langle Sub \rangle$):**
  Arah subtipe dibalik. Jika `Dog` adalah subtype dari `Animal`, maka `Consumer<Animal>` adalah subtype dari `Consumer<Dog>`. Ini berlaku pada parameter fungsi (saat flag `--strictFunctionTypes` aktif).
* **Invariance ($F\langle Sub \rangle$ dan $F\langle Super \rangle$ tidak kompatibel):**
  Hanya tipe identik yang diizinkan. Tipe yang mendukung read dan write (mutable state) secara teoritis harus invarian.
* **Bivariance:**
  Kompatibel di kedua arah. Method shorthand `{ method(x: Animal): void }` secara default bivariant di TypeScript demi alasan kompatibilitas mundur ekosistem JavaScript lama.

Mulai TypeScript 4.7+, kita dapat secara eksplisit menganotasi varians menggunakan kata kunci `in` (contravariant) dan `out` (covariant):

```typescript
type Producer<out T> = () => T;        // Covariant
type Consumer<in T> = (arg: T) => void; // Contravariant
type Invariant<in out T> = (arg: T) => T; // Invariant
```

### 2. Bounded Parametric Polymorphism & F-Bounded Quantification

Sering kali, generic murni terlalu abstrak. Kita membutuhkan batas minimal properti:
$$\forall T \le \text{Comparable}\langle T \rangle$$

Pola di mana tipe parameter merujuk pada dirinya sendiri di dalam batasan disebut **F-Bounded Polymorphism**:

```typescript
interface Comparable<T> {
  compareTo(other: T): number;
}

class Entity<T extends Comparable<T>> {
  // T dijamin kompatibel dengan perbandingan terhadap jenisnya sendiri
}
```

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi fundamental yang mengintegrasikan batasan F-bounded, varians eksplisit, dan default type arguments:

```typescript
// 1. Definisi hirarki domain untuk demonstrasi varians
abstract class DomainEvent {
  abstract readonly timestamp: number;
}

class UserCreatedEvent extends DomainEvent {
  readonly timestamp = Date.now();
  constructor(public readonly userId: string) {
    super();
  }
}

class AdminCreatedEvent extends UserCreatedEvent {
  constructor(userId: string, public readonly permissions: string[]) {
    super(userId);
  }
}

// 2. Anotasi Varians Tingkat Lanjut (out = Kovarian, in = Kontravarian)
interface EventProducer<out TEvent extends DomainEvent> {
  emit(): TEvent;
}

interface EventConsumer<in TEvent extends DomainEvent> {
  consume(event: TEvent): void;
}

// 3. F-Bounded Fluent Builder Generic
interface Serializable<TSelf extends Serializable<TSelf>> {
  serialize(): string;
  deserialize(input: string): TSelf;
}

class PipelineBuilder<
  TContext extends Record<string, unknown> = Record<string, unknown>
> {
  private constructor(private readonly context: TContext) {}

  public static initialize(): PipelineBuilder<{}> {
    return new PipelineBuilder<{}>({});
  }

  public withStep<K extends string, V>(
    key: K,
    value: V
  ): PipelineBuilder<TContext & Record<K, V>> {
    const updatedContext = {
      ...this.context,
      [key]: value,
    } as TContext & Record<K, V>;

    return new PipelineBuilder(updatedContext);
  }

  public build(): TContext {
    return Object.freeze({ ...this.context });
  }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Membedah mekanisme pada blok kode Seksi 07:

1. **`interface EventProducer<out TEvent extends DomainEvent>`**:
   * Flag `out` memberitahukan compiler bahwa `TEvent` hanya muncul pada posisi *output* (return type).
   * Implikasi: `EventProducer<AdminCreatedEvent>` dapat secara aman dioperasikan di mana `EventProducer<UserCreatedEvent>` diharapkan (Kovarian).
2. **`interface EventConsumer<in TEvent extends DomainEvent>`**:
   * Flag `in` memberitahukan compiler bahwa `TEvent` hanya muncul pada posisi *input* (argumen fungsi).
   * Implikasi: `EventConsumer<DomainEvent>` adalah subtype dari `EventConsumer<UserCreatedEvent>` (Kontravarian).
3. **`interface Serializable<TSelf extends Serializable<TSelf>>`**:
   * Mengunci `deserialize` agar mengembalikan instance dari tipe anak yang sebenarnya (*concrete self*), bukan sekadar generic base type.
4. **`class PipelineBuilder<TContext extends Record<string, unknown> = Record<string, unknown>>`**:
   * Memberikan *default generic parameter* jika pemanggil tidak memasok argumen tipe.
5. **`withStep<K extends string, V>(key: K, value: V): PipelineBuilder<TContext & Record<K, V>>`**:
   * Menggunakan intersection type (`&`) untuk mengakumulasi struktur type dari satu tahap chaining ke tahap berikutnya secara deterministik tanpa kehilangan informasi tipe sebelumnya.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Type-Safe CQRS In-Memory Command/Query Mediator Bus

Pada arsitektur microservices atau modular monolith enterprise berbasis Node.js/TypeScript, komunikasi internal antar modul sering membutuhkan Mediator Pattern (mirip MediatR di .NET).

**Tantangan Sistem:**
1. Setiap `Command` atau `Query` harus secara strictly-typed dipetakan ke tepat satu `Handler`.
2. Kembalian nilai dari `.send(command)` harus secara otomatis diinferensikan sesuai output handler terkait tanpa developer melakukan *type-casting*.
3. Middleware pipeline (seperti logging, validation, metrics) harus mampu menginspeksi tipe generic payload secara transparan (*higher-rank generic composition*).

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut implementasi CQRS Engine tingkat produksi yang mengisolasi eksekusi command menggunakan generic constraints tingkat lanjut:

```typescript
// ==========================================
// CQRS Core Contracts
// ==========================================

export interface IMessage<TKind extends string = string> {
  readonly kind: TKind;
}

// Marker generic interface dengan inferensi output type
export interface IRequest<TResponse> extends IMessage {
  readonly __responseMarker?: TResponse; // Phantom property untuk type inferencing
}

export interface IRequestHandler<
  in TReq extends IRequest<TRes>,
  out TRes
> {
  handle(request: TReq): Promise<TRes>;
}

// Pipeline Middleware contract
export type NextMiddleware<TRes> = () => Promise<TRes>;

export interface IPipelineBehavior {
  handle<TReq extends IRequest<TRes>, TRes>(
    request: TReq,
    next: NextMiddleware<TRes>
  ): Promise<TRes>;
}

// ==========================================
// Mediator Implementation
// ==========================================

export class Mediator {
  private readonly handlers = new Map<string, IRequestHandler<any, any>>();
  private readonly middlewares: IPipelineBehavior[] = [];

  public registerHandler<
    TRes,
    TReq extends IRequest<TRes>
  >(
    kind: TReq["kind"],
    handler: IRequestHandler<TReq, TRes>
  ): void {
    if (this.handlers.has(kind)) {
      throw new Error(`Handler already registered for: ${kind}`);
    }
    this.handlers.set(kind, handler);
  }

  public use(middleware: IPipelineBehavior): void {
    this.middlewares.push(middleware);
  }

  public async send<TRes>(request: IRequest<TRes>): Promise<TRes> {
    const handler = this.handlers.get(request.kind);
    if (!handler) {
      throw new Error(`No handler registered for message kind: ${request.kind}`);
    }

    // Eksekusi middleware chain menggunakan higher-order functions
    const executionChain = this.middlewares.reduceRight<NextMiddleware<TRes>>(
      (next, middleware) => {
        return () => middleware.handle(request, next);
      },
      () => handler.handle(request)
    );

    return executionChain();
  }
}

// ==========================================
// Domain Concrete Implementation
// ==========================================

// Domain Entities & DTOs
export interface UserDTO {
  id: string;
  email: string;
  role: "ADMIN" | "MEMBER";
}

// Command Definition: Mengikat request ke output type 'UserDTO'
export class CreateUserCommand implements IRequest<UserDTO> {
  public readonly kind = "CreateUserCommand";
  public readonly __responseMarker?: UserDTO;

  constructor(
    public readonly email: string,
    public readonly role: "ADMIN" | "MEMBER"
  ) {}
}

// Handler Definition: Terikat erat dengan CreateUserCommand & UserDTO
export class CreateUserHandler
  implements IRequestHandler<CreateUserCommand, UserDTO>
{
  public async handle(command: CreateUserCommand): Promise<UserDTO> {
    // Simulasi persistensi ke Database
    return {
      id: "usr_" + Math.random().toString(36).substring(2, 9),
      email: command.email,
      role: command.role,
    };
  }
}

// Global Validation Middleware
export class LoggingMiddleware implements IPipelineBehavior {
  public async handle<TReq extends IRequest<TRes>, TRes>(
    request: TReq,
    next: NextMiddleware<TRes>
  ): Promise<TRes> {
    const startTime = performance.now();
    console.log(`[CQRS-LOG] Executing: ${request.kind}`);

    try {
      const result = await next();
      const duration = (performance.now() - startTime).toFixed(2);
      console.log(`[CQRS-LOG] Completed: ${request.kind} in ${duration}ms`);
      return result;
    } catch (error) {
      console.error(`[CQRS-LOG] Failed: ${request.kind}`, error);
      throw error;
    }
  }
}

// ==========================================
// Verification & Execution Runner
// ==========================================

async function bootstrap() {
  const mediator = new Mediator();

  mediator.use(new LoggingMiddleware());

  const createUserHandler = new CreateUserHandler();
  mediator.registerHandler("CreateUserCommand", createUserHandler);

  // INFERENSI OTOMATIS:
  // result terinferensi sebagai UserDTO secara deterministik!
  const command = new CreateUserCommand("tech-lead@enterprise.org", "ADMIN");
  const result = await mediator.send(command);

  console.log(`User created with ID: ${result.id}, Role: ${result.role}`);
}

void bootstrap();
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Desain generic mengharuskan software architect menimbang batas fleksibilitas versus kompleksitas sistem tipe.

| Dimensi | Parametric Generics (`<T>`) | Dynamic Any / Unknown | Overloads Manual |
| :--- | :--- | :--- | :--- |
| **Type Safety** | Absolut, compile-time verified | Buruk (`any`) s/d Parsial (`unknown`) | Sangat tinggi, tetapi kaku |
| **Refactoring Resilience** | Sangat Tinggi (nama/properti terpelihara) | Rendah (rentan runtime errors) | Sedang (rawan duplikasi signature) |
| **Beban Compiler (Tsc)** | Menengah s/d Sangat Tinggi (Instansi cache) | Sangat Rendah | Rendah s/d Menengah |
| **Developer Experience** | Sangat baik via Auto-completion kontekstual | Nihil autocompletion | Baik, namun verbose |
| **Ukuran Bundle Runtime** | Nol (Type Erasure total) | Nol | Nol |

### Kapan Menggunakan Parametric Generics?
1. Ketika tipe nilai kembalian (*return type*) bergantung langsung pada tipe nilai masukan (*input type*).
2. Ketika struktur data kontainer (Queue, Cache, Store) harus netral terhadap tipe data yang disimpannya.
3. Ketika mengomposisi fungsi tingkat tinggi di mana integritas tipe harus dijaga sepanjang pipeline.

### Kapan Menghindari Parametric Generics?
1. Ketika generic parameter hanya muncul satu kali pada signature fungsi dan tidak digunakan untuk inferensi return type (mengindikasikan *premature generic abstraction*).
2. Ketika polymorphic dispatch dapat diselesaikan secara sederhana melalui Union Type sederhana (`A | B`).

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Excess Property Checks Suppression pada Generics
Ketika object literal dilewatkan langsung ke generic function dengan constraint, TypeScript sering menonaktifkan pengecekan properti berlebih (*excess property checks*):

```typescript
interface ExpectedShape {
  id: string;
}

function processData<T extends ExpectedShape>(data: T): T {
  return data;
}

// Pitfall: 'leakedProperty' tidak memicu compile error!
const payload = processData({
  id: "uuid-1",
  leakedProperty: "Bahaya: Data sensitif lolos ke payload",
});
```

### 2. The Naked Type Parameter Distribution Trap
Kondisi kondisional pada tipe parameter polos (*naked type parameter*) secara otomatis mendistribusikan union:

```typescript
type ToArray<T> = T extends any ? T[] : never;

// Mengejutkan: Bukan (string | number)[], melainkan: string[] | number[]
type Result = ToArray<string | number>;

// Solusi: Non-distributive conditional type via tuple wrapping
type ToArrayNonDistributive<T> = [T] extends [any] ? T[] : never;
type CorrectResult = ToArrayNonDistributive<string | number>; // (string | number)[]
```

### 3. Structural Variance Mismatch pada Mutable Arrays
Secara teknis, `Array<Derived>` dianggap subtype dari `Array<Base>` dalam TypeScript (Kovarian secara historis demi kenyamanan developer), padahal dalam mutable collections hal ini *unsound* (dapat memicu runtime failure jika array diisi subtype lain).

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Generic yang Tidak Berguna (The Pointless Generic)

❌ **Buruk (Antipattern):**
```typescript
function printLength<T extends string>(text: T): void {
  console.log(text.length);
}
```
*Mengapa salah?* `T` tidak digunakan untuk menghubungkan dua argumen atau menentukan return type.

✔️ **Benar:**
```typescript
function printLength(text: string): void {
  console.log(text.length);
}
```

---

### Kesalahan 2: Kehilangan Narrowing Akibat Generic Tanpa Batas

❌ **Buruk:**
```typescript
function getFirstItem<T>(items: T[]): T {
  return items[0]; // Menghasilkan undefined jika array kosong, tapi type tetap 'T'!
}
```

✔️ **Benar (Mengekspresikan Nullability State):**
```typescript
function getFirstItem<T>(items: readonly T[]): T | undefined {
  return items.length > 0 ? items[0] : undefined;
}
```

---

### Kesalahan 3: Cast Paksa `as T` pada Konstruksi Return

❌ **Buruk:**
```typescript
function createDefault<T extends { count: number }>(): T {
  // Runtime Error rawan: Type assertion membungkam checker secara berbahaya
  return { count: 0 } as T;
}
```

✔️ **Benar (Menggunakan Factory Parametrik atau Concrete Defaults):**
```typescript
function createDefault<T extends { count: number }>(factory: () => T): T {
  return factory();
}
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Semantic Type Parameter Naming:**
   Hindari menamai generic dengan huruf tunggal `T`, `U`, `V` jika terdapat lebih dari 2 generic parameter. Gunakan awalan `T` diikuti nama deskriptif:
   * `TEntity`
   * `TRequest`
   * `TResponse`
   * `TContext`
2. **Push Generics Down (Gunakan Batasan Paling Rendah):**
   Gunakan generic parameter sedalam mungkin di dalam signature fungsi untuk memaksimalkan inferensi tipe lokal oleh compiler.
3. **Explicit Variance Annotations:**
   Pada codebase enterprise skala besar, gunakan kata kunci `in` dan `out` (TS 4.7+) pada tipe antarmuka/kelas abstrak generic untuk mempercepat resolusi type-checking compiler hingga 30%.
4. **Always Prefer Infer over Double-Generic Parameter Mapping:**
   Jika suatu tipe generic turunan dapat diekstraksi dari tipe generic utama, gunakan operator `infer` daripada mewajibkan pemanggil memasok dua argumen generic.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Mitigasi Type Instantiation Explosion

Kompilator TypeScript memiliki batas instansiasi tipe internal. Penggunaan union types yang besar dengan rekursif generics dapat menyebabkan kompilator kehabisan memori (*OOM - Out of Memory*).

1. **Gunakan Tuple Unrolling daripada Rekursi Dalam:**
   Jika memanipulasi list of generic parameters, manfaatkan *mapped tuples* bawaan daripada conditional type recursive loops.
2. **Gunakan Nominal Tagging / Branded Types untuk Mengurangi Kompleksitas Pencocokan Struktural:**

```typescript
// Berat bagi type-checker: Kompleksitas perbandingan struktural O(N x M)
interface DeeplyNestedStructureA {
  props: { a: { b: { c: string } } };
}

// Ringan bagi type-checker: O(1) comparison via Brand
type EntityId<TBrand extends string> = string & { readonly __brand: TBrand };
type UserId = EntityId<"UserId">;
type OrderId = EntityId<"OrderId">;
```

3. **Gunakan Profiler Built-in:**
   Jalankan diagnosa compiler untuk melacak instansiasi generic yang memberatkan:
   ```bash
   tsc --diagnostics --extendedDiagnostics --generateTrace ./tracing-out
   ```
   Periksa metrics: `Instantiations` dan `Check time`. Jika `Instantiations` melebihi $1.000.000$, arsitektur generic Anda perlu direfaktor.

---

# SEKSI 16 — KEAMANAN & HARDENING

### Mencegah Generic Type Injection

Sistem tipe struktural dapat dieksploitasi jika input generic dibiarkan terlalu terbuka, yang dapat meloloskan objek berbahaya ke layer orkestrasi internal.

```typescript
// Implementasi Hardened Validator
type DisallowedKeys = "__proto__" | "prototype" | "constructor";

type SafePayload<T> = {
  [K in keyof T]: K extends DisallowedKeys ? never : T[K];
};

export class SecureCommandDispatcher {
  public static execute<TCommand extends Record<string, unknown>>(
    payload: SafePayload<TCommand>
  ): void {
    // Validasi runtime terhadap Prototype Pollution
    const rawKeys = Object.keys(payload);
    if (
      rawKeys.includes("__proto__") ||
      rawKeys.includes("prototype") ||
      rawKeys.includes("constructor")
    ) {
      throw new SecurityError("Detected Prototype Pollution Attempt");
    }

    // Melanjutkan eksekusi secara aman
  }
}

class SecurityError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SecurityError";
  }
}
```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Debugging tipe generic komposit yang rumit di Visual Studio Code sering menghasilkan tampilan yang terpotong (*truncated tooltip*) seperti `{ a: string } & { b: number }`.

### 1. The `Prettify<T>` Type Debugger
Manfaatkan utilitas ini untuk memaksa TypeScript Compiler meratakan (*flatten*) representasi internal generic:

```typescript
export type Prettify<T> = {
  [K in keyof T]: T[K];
} & {};
```

### 2. Assert Subtype Equivalence (Type-Level Unit Testing)
Pastikan generic Anda beroperasi secara benar di tingkat kompilasi menggunakan static compile-time assertions:

```typescript
export type Expect<T extends true> = T;
export type Equal<X, Y> = (<T>() => T extends X ? 1 : 2) extends <
  T
>() => T extends Y ? 1 : 2
  ? true
  : false;

// Verifikasi:
type TestStep1 = Expect<Equal<string, string>>; // Lolos kompilasi
// @ts-expect-error Type string dan number tidak ekuivalen
type TestStep2 = Expect<Equal<string, number>>;
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Parametric Polymorphism:** Logika seragam atas sembarang tipe; murni diabstraksi tanpa asumsi struktural.
* **Bounded Generics:** `<T extends BaseShape>` membatasi input generic hanya pada set subtype yang valid.
* **Kovarian (`out T`):** `Sub <= Super` menghasilkan `T<Sub> <= T<Super>`. Posisi: Return type.
* **Kontravarian (`in T`):** `Sub <= Super` menghasilkan `T<Super> <= T<Sub>`. Posisi: Argument type.
* **F-Bounded:** `<T extends Interface<T>>` pola rekursif untuk mempertahankan referensi ke subtype konkret.
* **Non-distributive Rule:** Bungkus argumen dengan tuple `[T] extends [Base]` untuk mematikan sifat auto-unfolding union.
* **Type Erasure:** Semua sintaks generic (`<T>`, `as`, `in/out`) dieliminasi total pada waktu emisi JavaScript runtime.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Apa tujuan utama dari Parametric Polymorphism dibandingkan penulisan type `any`?**
   * *Jawaban:* Parametric polymorphism mempertahankan integritas dan relasi tipe antara input dan output secara compile-time, sedangkan `any` mematikan semua type-checking compiler.
2. **Kapan suatu Generic Parameter harus dihindari penggunaannya pada deklarasi fungsi?**
   * *Jawaban:* Ketika parameter tipe tersebut hanya muncul tepat satu kali di dalam signature parameter dan tidak digunakan pada return type ataupun relasi parameter lainnya.
3. **Apa arti kata kunci `out` pada deklarasi generic interface TypeScript 4.7+?**
   * *Jawaban:* Menyatakan bahwa type parameter tersebut adalah Kovarian, menjamin compiler bahwa tipe ini hanya digunakan pada posisi output (return types).
4. **Apa yang dimaksud dengan Type Erasure dalam arsitektur kompilasi TypeScript?**
   * *Jawaban:* Proses penghapusan seluruh metadata tipe, generic annotations, dan interfaces saat TypeScript ditranspilasi menjadi JavaScript murni.
5. **Bagaimana cara mencegah distributive behavior pada Conditional Type `T extends string ? A : B`?**
   * *Jawaban:* Membungkus kedua sisi operan dengan tuple: `[T] extends [string] ? A : B`.

### Soal Tingkat Menengah (Intermediate)

6. **Mengapa relasi parameter fungsi bersifat Contravariant di bawah compiler flag `--strictFunctionTypes`?**
   * *Jawaban:* Karena sebuah fungsi penerima harus mampu menangani set data yang lebih umum/luas daripada fungsi yang digantikannya agar aman dari runtime exceptions.
7. **Jelaskan mengapa method interface `{ run(arg: Animal): void }` bersifat Bivariant secara default di TypeScript!**
   * *Jawaban:* Dipertahankan untuk kompatibilitas mundur (*backward compatibility*) ekosistem array JavaScript bawaan seperti `Array.prototype.push`.
8. **Diberikan tipe `type X<T> = T extends Foo ? 1 : 2`. Jika `T` adalah `Foo | Bar`, apa hasil evaluasinya? Mengapa?**
   * *Jawaban:* Hasilnya adalah `1 | 2`, karena naked type parameter memicu pendistribusian union: `(Foo extends Foo ? 1 : 2) | (Bar extends Foo ? 1 : 2)`.
9. **Apa masalah memori/performa yang dapat ditimbulkan oleh recursive type generic tingkat lanjut?**
   * *Jawaban:* Dapat menyebabkan Type Instantiation Explosion, menghabiskan memori compiler (OOM) dan membuat Visual Studio Code Language Server melambat drastis.
10. **Bagaimana pola F-Bounded Quantification menyelesaikan masalah method chaining yang mengembalikan instance subtype konkret?**
    * *Jawaban:* Pola `T extends Builder<T>` memastikan class anak meneruskan dirinya sendiri sebagai generic argument, sehingga chaining method di level abstract class selalu mengembalikan subtype konkret, bukan tipe dasar.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: Type-Safe State Machine Builder Engine

Rancang dan bangun sebuah Finite State Machine (FSM) DSL builder menggunakan Advanced TypeScript Generics dengan spesifikasi teknis berikut:

#### Kebutuhan Fungsional & Spesifikasi Sistem:
1. **Definisi State & Transition yang Terkunci:**
   * Developer tidak boleh dapat memicu *transition* yang tidak valid untuk state saat ini.
   * State machine harus diinisialisasi melalui Fluent Builder API.
2. **Zero Runtime Casting:**
   * Dilarang menggunakan keyword `as` atau `any` di dalam implementasi engine (manfaatkan type inference, user-defined type guards, dan generic mapping).
3. **Kriteria Validasi Kompilasi (Type-Level Unit Testing):**
   * Jika state adalah `'IDLE'`, pemanggilan transition `'DISPATCH'` harus lolos type-check.
   * Jika state adalah `'IDLE'`, pemanggilan transition `'RESOLVE'` harus memicu **TypeScript Compile Error**.
4. **Context Passing:**
   * Setiap state memiliki tipe context data yang berbeda (contoh: state `'ERROR'` memiliki `{ error: Error }`, state `'SUCCESS'` memiliki `{ data: string }`).

#### Starter Boilerplate:

```typescript
// Selesaikan implementasi StateMachineBuilder berikut:
export type StateConfig = {
  [stateName: string]: {
    transitions: Record<string, string>;
    context: unknown;
  };
};

export class StateMachineBuilder<TStates extends StateConfig> {
  // Tambahkan generic constraints, chaining logic,
  // dan runtime execution method di sini.
}
```

#### Tolok Ukur Keberhasilan:
* Error kompilasi terjadi secara *real-time* di IDE jika developer mencoba meregistrasi transisi ke State yang belum pernah didefinisikan sebelumnya di dalam builder pipeline.
* Autocompletion VS Code secara otomatis menampilkan daftar event yang valid sesuai dengan *current state* mesin.