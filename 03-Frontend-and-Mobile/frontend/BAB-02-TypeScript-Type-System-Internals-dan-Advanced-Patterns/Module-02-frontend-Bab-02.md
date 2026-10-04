# BAB 02: TypeScript Type System Internals & Advanced Patterns
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengurai siklus hidup kompilasi `tsc` (Scanner $\to$ Parser $\to$ Binder $\to$ Type Checker $\to$ Emitter) dan membedah struktur internal AST (*Abstract Syntax Tree*) serta *Type Cache Symbols*.
- Menganalisis dan memanipulasi aturan variansi sistem tipe: *Covariance*, *Contravariance*, *Invariance*, dan *Bivariance* pada fungsi, objek, dan generic.
- Mengonstruksi komputasi level tipe (*Type-Level Metaprogramming*) berbasis *Distributive Conditional Types*, *Mapped Types with Key Remapping*, *Recursive Types*, serta emulasi *Higher-Kinded Types* (HKT).
- Mengimplementasikan pola *Nominal/Branded Typing* dan *Phantom Types* untuk menjamin integritas *Domain-Driven Design* (DDD) bebas kebocoran tipe pada lapisan batas data (*boundary layer*).
- Merancang *Type-Safe State Machine* dan *Zero-Cost Type-Level Validation Engines* tanpa overhead runtime.
- Mengoptimalkan performa kompilasi monorepo berskala besar melalui tuning AST Type Checker, mitigasi *Union Explosion*, dan arsitektur *TypeScript Project References*.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib menguasai:
- Sintaksis dasar TypeScript: `interface`, `type`, primitive types, generic function dasar (`<T>(arg: T): T`), dan type assertions (`as`).
- Konsep dasar ECMAScript modern: Prototype chain, closures, proxy, event loop, dan ES Modules.
- Pengetahuan CLI: Node.js (v18+), npm/pnpm, serta konfigurasi mendasar `tsconfig.json`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### Arsitektur Internal TypeScript Compiler (`tsc`)
Kompiler TypeScript bekerja sebagai *multi-phase pipeline*. Diagram berikut membedah transformasi kode dari teks mentah hingga eksekusi type checking dan emisi:

```
[Source Code (.ts)]
        │
        ▼
   ┌─────────┐
   │ Scanner │  ── Lexical Analysis (Tokens: Keyword, Identifier, Punctuator)
   └────┬────┘
        │
        ▼
   ┌─────────┐
   │ Parser  │  ── Syntactic Analysis (Abstract Syntax Tree / AST Nodes)
   └────┬────┘
        │
        ▼
   ┌─────────┐
   │ Binder  │  ── Semantic Analysis (Symbols, Scopes, Symbol Table Creation)
   └────┬────┘
        │
        ▼
   ┌───────────────┐
   │ Type Checker  │ <── Core Engine (Type Resolution, Inference, Variance Check)
   └───────┬───────┘
           │
           ▼
     ┌───────────┐
     │  Emitter  │  ── Code Generation (.js, .d.ts, .js.map)
     └───────────┘
```

1. **Scanner**: Membaca stream karakter UTF-8 dan menghasilkan stream token. Token mengeliminasi whitespace dan komentar.
2. **Parser**: Mengonsumsi token untuk membangun *Abstract Syntax Tree* (AST). Node AST merepresentasikan konstruksi sintaksis (`BinaryExpression`, `TypeAliasDeclaration`, `CallExpression`).
3. **Binder**: Berjalan mendahului type checking. Mengaitkan identifier deklarasi ke struktur data `Symbol`. `Symbol` bertindak sebagai entitas semantik yang memetakan scope (blok, fungsi, modul) dan menyimpan link balik ke AST Node deklarasinya.
4. **Type Checker**: Jantung performa sistem. Checker membangun struktur internal `Type` dari `Node` dan `Symbol`. Checker menjalankan evaluasi lazy: tipe tidak dihitung hingga dibutuhkan oleh pengecekan ekspresi. Checker memvalidasi assignability, assignability relation cache, serta komputasi kondisional.
5. **Emitter**: Menghasilkan output JavaScript runtime dan deklarasi tipe (`.d.ts`), membuang seluruh anotasi tipe tanpa melakukan validasi runtime.

#### Teori Variansi: Covariance, Contravariance, Invariance, & Bivariance
TypeScript mengevaluasi relasi subtipe ($A \le B$, di mana $A$ adalah subtype dari $B$ jika $A$ assignable ke $B$) melalui lensa variansi ketika tipe dibungkus oleh konstruktor tipe generic $F<T>$.

| Jenis Variansi | Formulasi Formal | Konteks Default TypeScript |
| :--- | :--- | :--- |
| **Covariant** | $A \le B \implies F<A> \le F<B>$ | Return type fungsi, properti objek `readonly`, array. |
| **Contravariant** | $A \le B \implies F<B> \le F<A>$ | Parameter fungsi (di bawah flag `--strictFunctionTypes`). |
| **Invariant** | $F<A> \le F<B>$ hanya jika $A = B$ | Properti objek yang *mutable* (read/write). |
| **Bivariant** | $A \le B \implies F<A> \le F<B> \land F<B> \le F<A>$ | Method syntax `method(): void` (bukan properti fungsi). |

Visualisasi matematika variansi:
Jika `Admin` $\le$ `User`:
- Return types (Covariant): `() => Admin` $\le$ `() => User`. (Aman: Pemanggil mengharapkan User, menerima Admin yang memiliki seluruh properti User).
- Argument types (Contravariant): `(x: User) => void` $\le$ `(x: Admin) => void`. (Aman: Fungsi yang bisa memproses semua User pasti bisa memproses Admin).

---

### 4. Why & What

#### Why (Mengapa Butuh Pola Tingkat Lanjut?)
- **Mencegah "Primitive Obsession"**: Penggunaan tipe bawaan seperti `string` atau `number` untuk domain spesifik (misal: `UserId`, `OrderId`, `CurrencyAmount`) mengizinkan transmisi data yang salah urutan tanpa terdeteksi kompiler.
- **Eliminasi Runtime Guard Overload**: Tanpa inferensi tipe generic dan union diskriminatif, aplikasi enterprise terbebani oleh puluhan `if (typeof x === ...)` pada lapisan domain logic internal yang memperlambat execution latency.
- **Zero-Bug API Refactoring**: Kontrak bertingkat tinggi (*Type-Level Computations*) memaksa setiap perubahan skema backend langsung memicu compile-time error di seluruh layer frontend tanpa menunggu integrasi manual atau testing regresi.

#### What (Apa Saja Pola Tingkat Lanjut Tersebut?)
- **Branded Types**: Menambahkan metadata level tipe kompilator (*phantom brand*) pada tipe primitif tanpa memengaruhi representasi runtime (zero footprint).
- **Distributive Conditional Types**: Mekanisme pemetaan union secara otomatis ketika tipe naked generic dievaluasi dalam `T extends U ? X : Y`.
- **Higher-Kinded Types (HKT) Emulation**: Mekanisme abstraksi type constructor generic yang menerima generic lain sebagai parameter, menggunakan pattern *Defunctionalization* atau *Type Def Registry*.

---

### 5. How (Workflow Detail)

Alur perancangan pustaka atau modul arsitektur frontend bertipe tinggi (*high-assurance type design*):

```
1. Formalisasi Domain Contract ──> Identifikasi Type Boundaries (ID, Entity, State)
                │
                ▼
2. Deklarasi Phantom / Brand   ──> Mencegah Cross-Type Pollution (UserId != OrderId)
                │
                ▼
3. Desain State Mesin Tipe    ──> Strict Discriminated Unions (Exhaustive Checking)
                │
                ▼
4. Type-Level Parsing/Mapping  ──> Ekstraksi API Schema via Template Literals & Key Remap
                │
                ▼
5. Strict Type Checker Tuning ──> Benchmarking AST Type Checker & Project References
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Nominal Typing vs Structural Typing
- **Structural Typing (TypeScript Default)**: Kunci duplikat fisik. Jika alur gigi kunci cocok dengan silinder gembok (memiliki bentuk/properti yang sama), gembok akan terbuka, tidak peduli apakah kunci itu bertuliskan "Pintu Rumah" atau "Gudang Beracun".
- **Nominal Typing (Branded Type)**: Kunci berbasis chip RFID biometrik. Meskipun bentuk fisik kedua kartu sama persis (keduanya persegi panjang plastik `string`), pemindai memeriksa signature internal unik (*brand tag*). Pintu ruang kendali reaktor nuklir tidak akan terbuka untuk kartu pintu masuk kantin.

```
+-------------------------------------------------------------+
|                     Structural Match                        |
|                                                             |
|  type RawString   = string;                                 |
|  type EmailString = string;                                 |
|                                                             |
|  RawString  ──────────────────────────► [ accepted! ]       |
|  EmailString ─────────────────────────► [ accepted! ]       |
|                                                             |
+-------------------------------------------------------------+
                              VS
+-------------------------------------------------------------+
|                      Nominal / Branded                      |
|                                                             |
|  type Email = string & { readonly [__brand]: 'Email' };    |
|                                                             |
|  RawString  ──────── (Invalid Type) ──► [ REJECTED (tsc) ]  |
|  Email      ──────── (Valid Brand)  ──► [ ACCEPTED ]        |
+-------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Distributive Conditional Types & Key Remapping
```typescript
// Ekstraksi method berawalan 'get' dan mengubah return type
type RemovePrefix<T extends string, Prefix extends string> = 
  T extends `${Prefix}${infer Rest}` ? Uncapitalize<Rest> : T;

type Getters<T> = {
  [K in keyof T as K extends `get${infer Suffix}` ? Uncapitalize<Suffix> : never]: T[K] extends () => infer R ? R : never;
};

interface UserDataSource {
  getName: () => string;
  getAge: () => number;
  commitTransaction: () => Promise<void>; // Harus diabaikan karena bukan 'getter'
}

type ExtractedUserData = Getters<UserDataSource>;
// Hasil Type Checker:
// type ExtractedUserData = {
//   name: string;
//   age: number;
// }
```

#### Practical Example: Production-Ready Branded Type Factory & Type-Safe Finite State Machine (FSM)

```typescript
// 1. BRANDING INFRASTRUCTURE
declare const __brand: unique symbol;

export type Brand<B> = { [__brand]: B };
export type Branded<T, B> = T & Brand<B>;

// Domain Nominal Types
export type UserId = Branded<string, 'UserId'>;
export type OrderId = Branded<string, 'OrderId'>;
export type CentAmount = Branded<number, 'CentAmount'>;

export const UserId = (val: string): UserId => {
  if (!val.startsWith('usr_')) {
    throw new TypeError(`Invalid UserId format: ${val}`);
  }
  return val as UserId;
};

export const OrderId = (val: string): OrderId => {
  if (!val.startsWith('ord_')) {
    throw new TypeError(`Invalid OrderId format: ${val}`);
  }
  return val as OrderId;
};

export const CentAmount = (val: number): CentAmount => {
  if (!Number.isInteger(val) || val < 0) {
    throw new TypeError(`Invalid CentAmount: ${val}`);
  }
  return val as CentAmount;
};

// 2. EXHAUSTIVE STATE MACHINE
export type PaymentState =
  | { status: 'IDLE' }
  | { status: 'PENDING_AUTHORIZATION'; orderId: OrderId; amount: CentAmount }
  | { status: 'AUTHORIZED'; authorizationCode: string; amount: CentAmount }
  | { status: 'FAILED'; reason: string; retryable: boolean };

export type PaymentEvent =
  | { type: 'SUBMIT'; orderId: OrderId; amount: CentAmount }
  | { type: 'AUTHORIZE_SUCCESS'; authorizationCode: string }
  | { type: 'AUTHORIZE_ERROR'; reason: string; retryable: boolean }
  | { type: 'RESET' };

// Exhaustive Check Utility
export function assertNever(x: never): never {
  throw new Error(`Unhandled discriminative variant encountered: ${JSON.stringify(x)}`);
}

// Reducer State Machine
export function paymentReducer(
  state: PaymentState,
  event: PaymentEvent
): PaymentState {
  switch (state.status) {
    case 'IDLE':
      if (event.type === 'SUBMIT') {
        return {
          status: 'PENDING_AUTHORIZATION',
          orderId: event.orderId,
          amount: event.amount,
        };
      }
      return state;

    case 'PENDING_AUTHORIZATION':
      if (event.type === 'AUTHORIZE_SUCCESS') {
        return {
          status: 'AUTHORIZED',
          authorizationCode: event.authorizationCode,
          amount: state.amount,
        };
      }
      if (event.type === 'AUTHORIZE_ERROR') {
        return {
          status: 'FAILED',
          reason: event.reason,
          retryable: event.retryable,
        };
      }
      return state;

    case 'AUTHORIZED':
      // State terminal: hanya bisa di-reset
      if (event.type === 'RESET') {
        return { status: 'IDLE' };
      }
      return state;

    case 'FAILED':
      if (event.type === 'RESET') {
        return { status: 'IDLE' };
      }
      if (event.type === 'SUBMIT' && state.retryable) {
        return {
          status: 'PENDING_AUTHORIZATION',
          orderId: event.orderId,
          amount: event.amount,
        };
      }
      return state;

    default:
      return assertNever(state);
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Pada arsitektur Micro-Frontend e-Commerce Skala Global (120+ Micro-Apps, 400+ Engineer), tim sering mengalami runtime bug akibat serialisasi API:
1. Endpoint API mengirimkan `order_id` berbentuk string numerik, namun frontend secara keliru menjumlahkannya secara aritmatika.
2. Penanganan form pembayaran mentransmisikan status mutasi yang invalid (race condition: checkout ganda).
3. Payload nested routing URL tidak terverifikasi secara compile-time, menyebabkan runtime error 404 pada deep link.

#### Solusi Arsitektur: Dynamic Type-Safe Query Parameter Engine via Recursive Template Literals
Engine parser URL dan Query-String tingkat tinggi berbasis Type System murni:

```typescript
// Recursive string parser untuk ekstraksi parameter dari route template
// Contoh: "/organizations/:orgId/users/:userId/roles/:role"

type ExtractRouteParams<Path extends string> =
  Path extends `${infer _Start}:${infer Param}/${infer Rest}`
    ? { [K in Param | keyof ExtractRouteParams<`/${Rest}`>]: string }
    : Path extends `${infer _Start}:${infer Param}`
    ? { [K in Param]: string }
    : Record<string, never>;

// Implementasi Router Type-Safe
export class EnterpriseRouteNavigator<TPath extends string> {
  constructor(private readonly pathTemplate: TPath) {}

  public buildUrl(
    params: ExtractRouteParams<TPath>,
    queryParams?: Record<string, string | number | boolean>
  ): string {
    let resolvedUrl: string = this.pathTemplate;

    // Inject Path Params
    for (const [key, value] of Object.entries(params)) {
      resolvedUrl = resolvedUrl.replace(`:${key}`, encodeURIComponent(String(value)));
    }

    // Inject Query Params
    if (queryParams && Object.keys(queryParams).length > 0) {
      const searchParams = new URLSearchParams();
      for (const [qKey, qVal] of Object.entries(queryParams)) {
        searchParams.append(qKey, String(qVal));
      }
      resolvedUrl = `${resolvedUrl}?${searchParams.toString()}`;
    }

    return resolvedUrl;
  }
}

// Penggunaan di Production Layer
const UserProfileRoute = new EnterpriseRouteNavigator(
  '/organizations/:orgId/users/:userId/settings'
);

// Pengecekan Kompiler:
// VALID:
const validUrl = UserProfileRoute.buildUrl({
  orgId: 'org_enterprise_01',
  userId: 'usr_alpha_99',
});

// TYPE ERROR (Compile-Time Catch):
// @ts-expect-error: Property 'userId' is missing in type '{ orgId: string; }'
const invalidUrl = UserProfileRoute.buildUrl({
  orgId: 'org_enterprise_01',
});
```

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **Deep Conditional / Recursive Types** | Jaminan keabsahan API 100% pada fase kompilasi; dokumentasi eksplisit berbasis kode. | Meningkatkan waktu eksekusi `tsc` secara eksponensial. Rentan memicu `TS2589: Type instantiation is excessively deep and possibly infinite`. |
| **Branded / Nominal Typing** | Mengeliminasi kesalahan penukaran variabel primitive secara permanen tanpa runtime overhead. | Diperlukan fungsi casting/factory eksplisit di runtime boundary (saat fetch data/parsing JSON input). |
| **Strict Bivariance Disable (`--strictFunctionTypes`)** | Menutup celah ketidakamanan tipe pada callback dan generic pipelines. | Membutuhkan refactoring kode warisan (*legacy code*), terutama implementasi event listener DOM bawaan. |
| **Heavy Discriminated Unions** | Memaksa exhaustive check via `assertNever`; mencegah state mustahil (*impossible states*). | Ukuran kode boilerplate bertambah; kurva belajar developer pemula lebih tinggi saat menulis reducer/handler. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Union Distribution Terpicu Tanpa Disengaja
*Anti-pattern*:
```typescript
type ToArray<T> = T extends any ? T[] : never;
type Result = ToArray<string | number>;
// Result adalah: string[] | number[] (Bukan (string | number)[])!
```
*Solusi*: Bungkus ekspresi conditional generic dalam tuple `[T]` untuk mematikan *distribution flag* compiler:
```typescript
type ToArrayNonDistributive<T> = [T] extends [any] ? T[] : never;
type CorrectResult = ToArrayNonDistributive<string | number>; // (string | number)[]
```

#### Kesalahan 2: Kehilangan Brand Saat Melakukan Transformasi Primitif
*Anti-pattern*:
```typescript
type USD = Branded<number, 'USD'>;
const balance = 100 as USD;
const doubled = balance * 2; // Tipe doubled turun derajat menjadi 'number' biasa! Brand hilang.
```
*Solusi*: Bungkus domain operator ke dalam utility functions murni:
```typescript
const multiplyUSD = (amount: USD, factor: number): USD => (amount * factor) as USD;
```

#### Kesalahan 3: Bivariance Method Pitfall
*Anti-pattern*:
```typescript
interface Processor {
  process(data: string | number): void; // Method syntax = Bivariant! Kurang aman.
}
// Seharusnya gunakan Function Property Syntax untuk strict contravariance check:
interface StrictProcessor {
  process: (data: string | number) => void;
}
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Compiler Settings**: Selalu aktifkan `"strict": true`, `"noImplicitOverride": true`, dan `"exactOptionalPropertyTypes": true` pada `tsconfig.json`.
- [ ] **Type Boundaries**: Terapkan runtime decoding library (seperti Zod/Valibot) yang di-cast langsung menjadi *Branded Types* tepat pada Network I/O boundary.
- [ ] **Avoid `any` & Minimize `unknown` Assertion**: Larang penggunaan keyword `any` via rule ESLint `@typescript-eslint/no-explicit-any: error`.
- [ ] **Exhaustive Guarding**: Selalu sediakan handler `default: assertNever(state)` pada seluruh blok `switch-case` yang memproses *discriminated unions*.
- [ ] **AST Depth Mitigation**: Batasi rekursi tipe maksimum dengan menyediakan accumulator counter jika membuat template literal parsing types.
- [ ] **Monorepo References**: Gunakan arsitektur `"composite": true` pada setiap sub-package monorepo untuk mempercepat *incremental build* tanpa recompilation total.

---

### 12. Hands-on Practice

Lakukan langkah kerja berikut pada direktori terminal Anda untuk menganalisis AST Type Checker dan membangun arsitektur branded engine:

#### Setup Direktori & Dependensi
```bash
mkdir -p hands-on/m02
cd hands-on/m02
pnpm init
pnpm add -D typescript @types/node
npx tsc --init
```

Modifikasi file `tsconfig.json` yang dihasilkan agar mengaktifkan konfigurasi strict penuh dan diagnostik compiler:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "noImplicitOverride": true,
    "exactOptionalPropertyTypes": true,
    "diagnostics": true,
    "extendedDiagnostics": true,
    "skipLibCheck": true,
    "outDir": "./dist"
  },
  "include": ["src/**/*"]
}
```

#### File Implementasi: `src/nominal-engine.ts`
Ketik kode berikut secara lengkap:
```typescript
// hands-on/m02/src/nominal-engine.ts

declare const __nominalTag: unique symbol;

export type Nominal<T, TTag extends string> = T & {
  readonly [__nominalTag]: TTag;
};

// Domain definitions
export type ISODateString = Nominal<string, 'ISODateString'>;
export type ValidUrl = Nominal<string, 'ValidUrl'>;

export function parseISODate(value: string): ISODateString {
  const date = new Date(value);
  if (isNaN(date.getTime()) || !/^\d{4}-\d{2}-\d{2}T/.test(value)) {
    throw new Error(`Value "${value}" is not a valid ISO 8601 Date.`);
  }
  return value as ISODateString;
}

export function parseValidUrl(value: string): ValidUrl {
  try {
    new URL(value);
    return value as ValidUrl;
  } catch {
    throw new Error(`Value "${value}" is not a valid Absolute URL.`);
  }
}

// Log audit trial system
interface AuditRecord {
  id: string;
  timestamp: ISODateString;
  targetEndpoint: ValidUrl;
}

export function dispatchAudit(record: AuditRecord): void {
  console.log(`[AUDIT] Registered event to ${record.targetEndpoint} at ${record.timestamp}`);
}
```

#### File Driver Eksekusi: `src/index.ts`
```typescript
// hands-on/m02/src/index.ts
import { dispatchAudit, parseISODate, parseValidUrl, ISODateString, ValidUrl } from './nominal-engine.js';

function run(): void {
  const validTimestamp = parseISODate('2026-03-30T10:00:00.000Z');
  const validDestination = parseValidUrl('https://telemetry.enterprise.internal/v1/traces');

  dispatchAudit({
    id: 'tx_99812',
    timestamp: validTimestamp,
    targetEndpoint: validDestination,
  });

  console.log('Nominal type dispatch successfully executed without typing breaches.');
}

run();
```

#### Menjalankan Profiling & Compilation
Jalankan kompilasi TypeScript dengan flag extended diagnostics untuk mengamati internal checker:
```bash
npx tsc
node dist/index.js
```

Amati output diagnosa compiler di terminal Anda. Perhatikan metrik:
- `Check time`
- `Types count`
- `Symbols count`

---

### 13. Exercise

#### Level: Easy
Diberikan union tipe berikut:
```typescript
type EventType = 'click' | 'hover' | 'scroll' | 'focus';
```
Buat generic type utility `ExcludeEvent<TUnion, TTarget>` murni menggunakan *conditional distributive types* (tanpa menggunakan utilitas bawaan `Exclude<T, U>`).

#### Level: Medium
Buat utilitas pemetaan tipe `DeepReadonly<T>` yang mengubah seluruh properti primitif, objek bertingkat (nested objects), array, dan set menjadi read-only secara rekursif, tanpa merusak tipe primitive Function.

#### Level: Hard
Rancang type utility `ValidateSchemaKeys<TContract, TImplementation>`:
Apabila `TImplementation` memiliki kelebihan properti di luar kontrak `TContract`, atau tipe salah satu key tidak sesuai dengan `TContract`, utility harus menghasilkan type error kompilasi yang mengembalikan nama key yang rusak sebagai pesan error literal, bukan sekadar `never`.

---

### 14. Challenge

**Skenario**:
Anda adalah Principal Architect pada perusahaan fintech payment gateway. Anda diminta merancang **Type-Level Deep Flatten Path Utility** bernama `FlattenObjectPaths<T>`.

**Spesifikasi Persyaratan**:
1. Mengubah struktur tipe konfigurasi nested bertingkat acak menjadi format dot-notation string literals union:
```typescript
type Schema = {
  db: {
    primary: { host: string; port: number };
    replica: { host: string };
  };
  auth: { secret: string };
};

// Harus menghasilkan union:
// "db.primary.host" | "db.primary.port" | "db.replica.host" | "auth.secret"
```
2. Harus mampu menangani array primitives (contoh: `tags: string[]` menjadi `"tags"` atau `"tags.${number}"`).
3. Harus memitigasi rekursi sirkular: Jika objek memuat referensi diri (*circular reference*), sistem tipe harus memotong kedalaman AST pada level 5 (*max depth recursion guard*) menggunakan tipe counter berbasis tuple.
4. Tuliskan tanpa menggunakan keyword `any` atau librari eksternal.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. Fase mana pada pipeline arsitektur `tsc` yang bertanggung jawab membangun relasi `Symbol` dan membuat scope table?
2. Mengapa sintaks method shorthand `{ fn(a: string): void }` berbeda perilakunya dengan property method `{ fn: (a: string) => void }` saat strict flag diaktifkan?
3. Apa perbedaan mendasar antara *Structural Typing* dan *Nominal Typing*?
4. Mengapa `unknown` jauh lebih aman digunakan sebagai safe-bottom type daripada `any`?
5. Kapan distributive behavior terjadi pada conditional types?

#### Intermediate (5 Pertanyaan)
6. Bagaimana cara mematikan distribusi otomatis tipe union saat dievaluasi menggunakan conditional types?
7. Jelaskan bagaimana *Contravariance* bekerja saat melakukan validasi parameter callback function assignment!
8. Apa yang dimaksud dengan *Phantom Type*, dan apa dampaknya terhadap bundle size JavaScript yang diekspor oleh Emitter?
9. Jelaskan fungsi dari utility type `assertNever(x: never): never` dalam arsitektur penanganan *discriminated unions*!
10. Apa penyebab utama error kompilator `TS2589: Type instantiation is excessively deep and possibly infinite` dan bagaimana strategi mengatasinya?

#### Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario A**: Tim frontend Anda melaporkan bahwa proses build CI/CD melonjak dari 2 menit menjadi 18 menit setelah menginstal pustaka form validator baru yang kaya akan generic recursive parsing. Langkah teknis apa yang harus Anda ambil untuk mengidentifikasi file penyebab degradasi waktu build tersebut?
12. **Skenario B**: Anda menerima data payload JSON dari websocket backend di mana field `amount` bertipe `number`. Namun, tim keuangan mensyaratkan bahwa nilai ini harus dalam denominasi `Cent` dan tidak boleh tercampur dengan representasi `Dollar`. Bagaimana Anda merekayasa batasan tipe ini pada runtime deserializer?
13. **Skenario C**: Pada aplikasi monorepo berskala besar, sub-aplikasi A bergantung pada library utilitas internal B. Setiap kali utilitas internal B diubah sedikit, seluruh sub-aplikasi A terpaksa melakukan kompilasi ulang dari awal (*cold build*). Konfigurasi `tsconfig.json` apa yang hilang dan bagaimana memperbaikinya?

---

### 16. Summary

1. Arsitektur Kompiler TypeScript memisahkan proses transformasi sintaksis (Scanner, Parser) dari analisis semantik dan inferensi tipe (Binder, Type Checker), diakhiri oleh pembersihan tipe murni tanpa overhead performa runtime (Emitter).
2. Variansi (*Covariance*, *Contravariance*, *Invariance*, *Bivariance*) adalah fondasi formal yang menentukan apakah suatu hierarki generic aman untuk saling disubstitusi. Pemahaman atas variansi krusial dalam merancang callback and middleware interfaces.
3. *Nominal / Branded Typing* menyuntikkan integritas Domain-Driven Design (DDD) tingkat tinggi ke dalam sistem structural typing TypeScript, mencegah *Primitive Obsession* dan bug konversi data yang mematikan pada skala enterprise.
4. *Type-Level Metaprogramming* menggunakan recursive template literals, key remapping, dan distributive evaluation memungkinkan pembangunan API interfaces yang self-documenting dan kebal terhadap desinkronisasi kontrak runtime.