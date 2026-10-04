# MODUL PEMBELAJARAN: TYPE-LEVEL PROGRAMMING & METAPROGRAMMING
**Kategori:** 02-Programming-Languages | **Kurikulum:** TypeScript | **Bab:** 05 | **Modul:** 01

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** `TS-TYP-0501`
* **Judul Modul:** Type-Level Programming & Metaprogramming
* **Tingkat Kesulitan:** Advanced / Expert
* **Estimasi Waktu Penyelesaian:** 8 – 12 Jam Belajar Aktif
* **Prasyarat Pengetahuan:**
  * Penguasaan mendalam atas Generics, Conditional Types dasar, Mapped Types, dan Indexed Access Types.
  * Pemahaman mendasar mengenai paradigma Functional Programming (rekursi, immutability, pattern matching).
  * Pemahaman tentang fase kompilasi TypeScript (`tsc`) vs eksekusi runtime JavaScript (V8/Node.js/Bun).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis (C4)** arsitektur *type-checker* TypeScript sebagai bahasa pemrograman fungsional murni (*pure functional language*) yang *Turing-complete*.
2. **Merancang (C6)** algoritma tingkat tipe (*type-level algorithms*) menggunakan rekursi tail-call, pattern matching via `infer`, dan manipulasi template literal types.
3. **Mendiagnosis (C4)** dan mengatasi limitasi kompilator seperti *instantiation depth limits*, union explosion, dan compiler-induced memory leaks via `--extendedDiagnostics` dan `--generateTrace`.
4. **Mengimplementasikan (C6)** sistem tipe metaprogramming tingkat produksi untuk ekstraksi rute dinamis (*type-safe router*) dan manipulasi objek bersarang (*deep path accessor*) tanpa *runtime overhead*.
5. **Mengevaluasi (C5)** trade-off antara keamanan tipe (*type safety*) ekstrem versus performa kompilasi developer loop (*DX latency*).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Memandang Sistem Tipe sebagai Mesin Komputasi Terpisah

TypeScript memiliki dua lingkungan komputasi yang berjalan pada garis waktu berbeda:

```
Runtime Level (JavaScript)      ---> Dieksekusi di Node.js / Browser (Dynamic Values)
───────────────────────────────────────────────────────────────────────────────────
Type-Level (TypeScript Type-System) ---> Dieksekusi saat Compile Time oleh TypeChecker (Static Types)
```

Untuk menguasai *Type-Level Programming*, Anda harus mengadopsi mental model bahwa **sistem tipe TypeScript adalah bahasa pemrograman fungsional murni (*pure lazy functional language*)**:

| Konsep Komputasi Standar | Padanan di Type-Level TypeScript |
| :--- | :--- |
| **Variabel / Data** | Tipe Literal, Objek Tipe, Tuple, Primitive Types |
| **Fungsi (*Pure Function*)** | Generic Type Alias (`type F<T> = ...`) |
| **Kondisional (`if / else`)** | Conditional Types (`T extends U ? TrueBranch : FalseBranch`) |
| **Pattern Matching** | Kata kunci `infer` di dalam Conditional Types |
| **Looping / Perulangan** | Rekursi Tipe (*Type-Level Recursion*) |
| **Array / List** | Tuples (`[A, B, C]`) |
| **Manipulasi String** | Template Literal Types (`` `${Head}${Tail}` ``) |
| **Equality Check** | Structural Assignability Subtyping (`[A] extends [B] ? [B] extends [A] ? true : false : false`) |

Aturan fundamental di tingkat tipe: **Semua tipe bersifat *immutable***. Anda tidak pernah "mengubah" tipe data; Anda selalu menerima satu atau lebih tipe sebagai parameter input dan mengembalikan tipe baru sebagai output.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Hidup Evaluasi Tipe di Kompilator TypeScript (`tsc`)

```
   Source Code (.ts)
           │
           ▼
    ┌──────────────┐
    │    Parser    │  ───> Menghasilkan AST (Abstract Syntax Tree)
    └──────────────┘
           │
           ▼
    ┌──────────────┐
    │    Binder    │  ───> Membangun Symbols & Symbol Table
    └──────────────┘
           │
           ▼
    ┌──────────────┐
    │ TypeChecker  │  <─── [MESIN TYPE-LEVEL EVALUATION]
    └──────┬───────┘
           │
           ├─── Resolusi Identitas Tipe (Type Identity Resolution)
           ├─── Pattern Matching via Type Unification (`infer`)
           ├─── Instantiation Cache Lookup (Cek apakah Type<Args> sudah ada)
           ├─── Structural Subtyping Check (`checkTypeRelatedTo`)
           └─── Conditional Distribution Engine
           │
           ├─── GAGAL ──> Emit Type Diagnostics (TS2322, TS2589, dll)
           │
           ▼
    ┌──────────────┐
    │   Emitter    │  ───> Menghilangkan SEMUA tipe (Type Erasure) -> Output: .js
    └──────────────┘
```

### Mekanisme Rekursi Tingkat Tipe dan Tail-Call Elimination

Mulai TypeScript 4.5+, kompilator mengimplementasikan optimasi tail-recursion untuk tipe kondisional.

```
Pola Rekursif Biasa (Maksimal Depth ~50-100):
TypeRecurse<T> = T extends ... ? [Head, ...TypeRecurse<Rest>] : []
                                  ▲
                                  └─ Tertahan oleh operasi pembentukan Tuple (Not Tail-Call)

Pola Tail-Call Recursive (Maksimal Depth ~1000):
TypeRecurse<T, Acc extends any[] = []> =
    T extends [infer Head, ...infer Rest]
        ? TypeRecurse<Rest, [...Acc, Head]>  <── Hasil rekursi langsung dikembalikan
        : Acc                                <── Terminal accumulator
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Conditional Types & Distributivity

Conditional types dievaluasi berdasarkan relasi *assignability*:

$$\text{Output} = T \subseteq U \;?\; X : Y$$

Secara internal di dalam `src/compiler/checker.ts`, kompilator menjalankan fungsi `checkTypeRelatedTo()`. Jika tipe `T` adalah *naked type parameter* (tipe generik tanpa pembungkus seperti array/tuple), operasi kondisional secara otomatis terdistribusi (*distribute*) terhadap *union*:

$$(A \mid B) \text{ extends } U \implies (A \text{ extends } U \dots) \mid (B \text{ extends } U \dots)$$

### 2. The `infer` Engine (Pattern Matching)

Keyword `infer` memicu mekanisme *Type Inference During Dynamic Structural Unification*. Kompilator memperkenalkan variabel tipe bebas (*free type variable*) dan mencoba menyelesaikan (*solve*) variabel tersebut agar sisi kanan ekuivalen dengan ekspresi target.

### 3. Instantiation Depth Limiter

TypeScript mencegah evaluasi tanpa henti (*infinite compiler hang*) menggunakan counter internal `instantiationDepth`.
* **Standard Recursion Limit:** Evaluasi rekursif biasa dibatasi sekitar 50–100 kedalaman pemanggilan.
* **Tail-Recursion Limit:** Jika pola rekursi terdeteksi berada di *terminal position* (Tail-Call Optimization di level tipe), batasnya diperluas hingga 1000 tingkat instansiasi sebelum kompilator memunculkan kesalahan `TS2589: Type instantiation is excessively deep and possibly infinite`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Turing Completeness of TypeScript Types

Sistem tipe TypeScript terbukti *Turing-complete*. Artinya, secara teoritis kita dapat menjalankan algoritma komputasi apa pun (seperti simulasi Game of Life, mesin Turing, atau interpreter Lisp) murni dalam sistem tipe saat waktu kompilasi.

Elemen pembentuk Turing completeness di TypeScript:
* **Penyimpanan Status (State):** Tuple types dan literal types merepresentasikan *state* dan *memory*.
* **Kontrol Alur (Branches):** Conditional types `T extends U ? X : Y`.
* **Perulangan Tanpa Batas / Rekursi:** Rekursi tipe kondisional.
* **Manipulasi Simbol:** Template string literal types untuk I/O berbasis string.

### 2. Distributive vs Non-Distributive Conditional Types

Distribusi union adalah fitur sekaligus potensi jebakan terbesar dalam metaprogramming.

```typescript
// Distributive: naked type parameter T
type ToArrayDistributive<T> = T extends any ? T[] : never;
type Res1 = ToArrayDistributive<string | number>;
// Evaluasi: (string extends any ? string[] : never) | (number extends any ? number[] : never)
// Hasil: string[] | number[]

// Non-Distributive: dibungkus dalam tuple
type ToArrayNonDistributive<T> = [T] extends [any] ? T[] : never;
type Res2 = ToArrayNonDistributive<string | number>;
// Evaluasi: [string | number] extends [any] ? (string | number)[] : never
// Hasil: (string | number)[]
```

Untuk tipe khusus seperti `never`, distribusi tipe kosong langsung menghasilkan `never` sebelum komparasi:
```typescript
type IsNeverDistributive<T> = T extends never ? true : false;
type TestNever1 = IsNeverDistributive<never>; // Hasil: never (Bukan true!)

type IsNeverSafe<T> = [T] extends [never] ? true : false;
type TestNever2 = IsNeverSafe<never>; // Hasil: true
```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi pustaka fungsi dasar komputasi tingkat tipe: manipulasi list/tuple, manipulasi string, dan Peano-like arithmetic dasar menggunakan tuple lengths.

```typescript
/**
 * 01: Manipulasi Tuple - Head, Tail, Push, Pop, Reverse
 */
export type Head<T extends readonly unknown[]> = 
  T extends readonly [infer First, ...unknown[]] ? First : never;

export type Tail<T extends readonly unknown[]> = 
  T extends readonly [unknown, ...infer Rest] ? Rest : [];

export type Cons<Head, Tail extends readonly unknown[]> = [Head, ...Tail];

export type Reverse<
  Tuple extends readonly unknown[], 
  Acc extends readonly unknown[] = []
> = Tuple extends readonly [infer First, ...infer Rest]
  ? Reverse<Rest, Cons<First, Acc>>
  : Acc;

/**
 * 02: Manipulasi String - Split, Join, Trim
 */
export type Split<
  Source extends string, 
  Delimiter extends string
> = Source extends `${infer Head}${Delimiter}${infer Tail}`
  ? [Head, ...Split<Tail, Delimiter>]
  : Source extends '' 
    ? [] 
    : [Source];

export type TrimLeft<S extends string> = 
  S extends `${' ' | '\t' | '\n'}${infer Rest}` ? TrimLeft<Rest> : S;

export type TrimRight<S extends string> = 
  S extends `${infer Rest}${' ' | '\t' | '\n'}` ? TrimRight<Rest> : S;

export type Trim<S extends string> = TrimLeft<TrimRight<S>>;

/**
 * 03: Tipe-Level Arithmetic Sederhana (Tuple-length-based)
 */
export type BuildTuple<Length extends number, Acc extends unknown[] = []> = 
  Acc['length'] extends Length 
    ? Acc 
    : BuildTuple<Length, [...Acc, unknown]>;

export type Add<A extends number, B extends number> = 
  [...BuildTuple<A>, ...BuildTuple<B>]['length'] & number;

export type Subtract<A extends number, B extends number> = 
  BuildTuple<A> extends [...BuildTuple<B>, ...infer Rest]
    ? Rest['length']
    : never;
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Mari kita bedah arsitektur internal dari fungsi tipe `Reverse` dan `Add`:

### Dekonstruksi `Reverse<Tuple, Acc>`

```typescript
export type Reverse<
  Tuple extends readonly unknown[], 
  Acc extends readonly unknown[] = []
> = Tuple extends readonly [infer First, ...infer Rest]
  ? Reverse<Rest, Cons<First, Acc>>
  : Acc;
```

1. **Parameter Deklarasi (`Tuple`, `Acc = []`):**
   * Menerima array tuple masukan `Tuple`.
   * Menggunakan pola *accumulator* (`Acc`) dengan default value `[]`. Ini adalah kunci transformasi ke struktur *Tail-Call Optimization (TCO)*.
2. **Kondisional & Ekstraksi (`Tuple extends readonly [infer First, ...infer Rest]`):**
   * Kompilator memeriksa apakah `Tuple` minimal memiliki 1 elemen.
   * `infer First` menangkap elemen pertama (indeks 0).
   * `...infer Rest` menangkap sisa tuple ke dalam variabel tipe baru `Rest`.
3. **Langkah Rekursif (`Reverse<Rest, Cons<First, Acc>>`):**
   * Memanggil kembali `Reverse` dengan parameter `Rest`.
   * Menaruh `First` di depan `Acc` (`Cons<First, Acc>`).
   * Tidak ada operasi yang membungkus pemanggilan `Reverse<...>` ini secara eksternal. Evaluasi berada di *tail position*.
4. **Terminal Condition (`: Acc`):**
   * Saat `Tuple` kosong (`[]`), kondisi pattern match gagal.
   * Kompilator mengembalikan akumulator `Acc` yang sekarang berisi elemen dalam urutan terbalik.

### Dekonstruksi `Add<A, B>`

```typescript
export type Add<A extends number, B extends number> = 
  [...BuildTuple<A>, ...BuildTuple<B>]['length'] & number;
```

1. Kompilator tidak memiliki instruksi matematika bawaan seperti `A + B`.
2. `BuildTuple<A>` membangun array artifisial dengan panjang `A`.
3. `BuildTuple<B>` membangun array artifisial dengan panjang `B`.
4. `[...BuildTuple<A>, ...BuildTuple<B>]` menggabungkan dua tuple via spread operator.
5. `['length']` membaca properti literal panjang tuple gabungan: $A + B$.
6. Interseksi `& number` digunakan untuk memaksa kompilator mempersempit tipe dari `number` umum ke literal angka hasil evaluasi (*type narrowing assertion*).

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Type-Safe Dynamic Deep Path Accessor & Expressive Router Parsing

Pada library seperti TanStack Router, TRPC, atau Prisma, API client sering membutuhkan:
1. Validasi parameter URL dari path string literal (misal: `"/users/:userId/posts/:postId"` harus memvalidasi objek `{ userId: string; postId: string }`).
2. Type-Safe Deep Property Accessor (seperti Lodash `get/set`, namun menjamin validitas string-path seperti `"user.address.geo.lat"` dan mengembalikan tipe kembalian yang tepat).

Jika path salah (misal `"user.adress"` typo), kompilator wajib menolak dan menandai letak kesalahan saat pengetikan, bukan saat runtime.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem *Zero-Runtime-Cost Deep Object Path Resolution* dan *URL Path Parameter Extractor*.

```typescript
// ============================================================================
// 1. URL ROUTE PARAMETER EXTRACTOR
// ============================================================================

type ExtractRouteParams<Path extends string> = 
  Path extends `${string}:${infer Param}/${infer Rest}`
    ? { [K in Param | keyof ExtractRouteParams<`/${Rest}`>]: string }
    : Path extends `${string}:${infer Param}`
      ? { [K in Param]: string }
      : Record<string, never>;

// Verifikasi Ekstraksi Parameter
type UserPostRoute = '/tenants/:tenantId/users/:userId/posts/:postId';
type ExtractedParams = ExtractRouteParams<UserPostRoute>;
// Resulting Type:
// type ExtractedParams = {
//   tenantId: string;
//   userId: string;
//   postId: string;
// }

// ============================================================================
// 2. TYPE-SAFE DEEP OBJECT PATH (GETTER/SETTER)
// ============================================================================

type Primitive = string | number | boolean | bigint | symbol | undefined | null;

/**
 * Membentuk union seluruh path valid dalam dot-notation string
 */
export type DeepNestedPaths<T, Depth extends unknown[] = []> = 
  // Batasi kedalaman traversal hingga 5 level untuk mencegah compiler hang
  Depth['length'] extends 5
    ? never
    : T extends Primitive
      ? never
      : T extends readonly (infer Element)[]
        ? `${number}` | `${number}.${DeepNestedPaths<Element, [...Depth, unknown]>}`
        : {
            [K in keyof T & string]: 
              | K 
              | `${K}.${DeepNestedPaths<T[K], [...Depth, unknown]>}`
          }[keyof T & string];

/**
 * Mengambil tipe dari nilai pada dot-notation path
 */
export type DeepNestedValue<T, Path extends string> = 
  Path extends `${infer Key}.${infer Rest}`
    ? Key extends keyof T
      ? DeepNestedValue<T[Key], Rest>
      : Key extends `${number}`
        ? T extends readonly (infer Element)[]
          ? DeepNestedValue<Element, Rest>
          : never
        : never
    : Path extends keyof T
      ? T[Path]
      : Path extends `${number}`
        ? T extends readonly (infer Element)[]
          ? Element
          : never
        : never;

// ============================================================================
// 3. RUNTIME IMPLEMENTATION (ZERO RUNTIME COST PARITY)
// ============================================================================

export function get<
  TData extends Record<string, any>, 
  TPath extends DeepNestedPaths<TData>
>(
  data: TData, 
  path: TPath
): DeepNestedValue<TData, TPath> {
  const segments = (path as string).split('.');
  let current: any = data;

  for (const segment of segments) {
    if (current === null || current === undefined) {
      return undefined as DeepNestedValue<TData, TPath>;
    }
    current = current[segment];
  }

  return current as DeepNestedValue<TData, TPath>;
}

// ============================================================================
// 4. TESTING HARNESS
// ============================================================================

interface SystemConfig {
  database: {
    replicas: {
      url: string;
      port: number;
    }[];
    timeoutMs: number;
  };
  features: {
    experimentalEngine: boolean;
  };
}

const config: SystemConfig = {
  database: {
    replicas: [
      { url: 'db1.internal', port: 5432 },
      { url: 'db2.internal', port: 5433 }
    ],
    timeoutMs: 5000
  },
  features: {
    experimentalEngine: true
  }
};

// Valid calls: Kompilator menginferensikan tipe balik secara absolut tepat!
const dbTimeout = get(config, 'database.timeoutMs');           // Tipe: number
const primaryUrl = get(config, 'database.replicas.0.url');       // Tipe: string
const isEnabled = get(config, 'features.experimentalEngine');    // Tipe: boolean

// @ts-expect-error Kompilator menggagalkan jika path salah!
const invalidField = get(config, 'database.replikas');

// @ts-expect-error Indeks salah secara struktural
const invalidSubField = get(config, 'database.replicas.invalidKey');
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Mengimplementasikan Metaprogramming tingkat tinggi mengharuskan arsitek perangkat lunak memperhitungkan kompromi arsitektural:

| Parameter | Type-Level Metaprogramming | Runtime Schema Validation (Zod, Valibot) |
| :--- | :--- | :--- |
| **Runtime Overhead** | **0 bytes, 0 cycles (Zero-cost)**. Lenyap saat dikompilasi ke JS. | Memerlukan bundle tambahan & siklus CPU saat runtime parsing. |
| **Kompilasi (`tsc`) Performance** | Sangat rentan terhadap **degradasi eksponensial** jika terdapat recursive union explosions. | Kompilasi cepat; pemeriksaan tipe TypeScript tetap sederhana (*flat*). |
| **Data Integrity** | Tidak dapat memvalidasi *untrusted boundary input* (misal: JSON payload dari HTTP request). | Menjamin validasi struktural pada runtime boundary data asli. |
| **Developer Experience (DX)** | Autocomplete instan, verifikasi instan di editor tanpa menjalankan kode. | Membutuhkan inferensi eksplisit via `z.infer<typeof Schema>`. |
| **Maintainability** | Sulit dibaca, membutuhkan keahlian functional metaprogramming tingkat lanjut. | Deklaratif, mudah dipahami dan dirawat oleh engineer pemula. |

### Rekomendasi Arsitektural:
* Gunakan **Type-Level Metaprogramming murni** untuk *internal domain DSL*, library design, dan composable APIs.
* Gunakan **kombinasi Schema Validator + Type Inversion** untuk *external network boundaries*.

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The `any` Contamination Trap

Jika variabel dengan tipe `any` memasuki fungsi type-level, tipe kondisional akan langsung mengalami branching ganda (*boolean union*) pada mayoritas kasus:

```typescript
type CheckString<T> = T extends string ? true : false;
type Trapped = CheckString<any>; // Hasil: boolean (yaitu: true | false)
```
**Solusi:** Buat guard untuk mendeteksi `any` terlebih dahulu:
```typescript
export type IsAny<T> = 0 extends 1 & T ? true : false;

type SafeCheckString<T> = IsAny<T> extends true 
  ? false 
  : T extends string 
    ? true 
    : false;
```

### 2. Union Combinatorial Explosion

Pertimbangkan penggabungan mapped types dengan union:
```typescript
type Permutation<T, K = T> = 
  [T] extends [never] 
    ? [] 
    : T extends K 
      ? [T, ...Permutation<Exclude<K, T>>] 
      : never;

type Keys = 'id' | 'name' | 'email' | 'age' | 'roles';
// HATI-HATI: Kompleksitas O(N!)
// 5 keys = 120 kombinasi tuple instansiasi
// 8 keys = 40,320 instansiasi -> Crash tsc OOM (Out of Memory)
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Lupa Mematikan Distribusi Union saat Validasi `never`

```typescript
// SALAH
type BadIsNever<T> = T extends never ? true : false;
type Test1 = BadIsNever<never>; // Output: never

// BENAR: Kapsulasi Tipe Menggunakan Tuple
type GoodIsNever<T> = [T] extends [never] ? true : false;
type Test2 = GoodIsNever<never>; // Output: true
```

### Kesalahan 2: Rekursi Non-Tail-Recursive pada Array Panjang

```typescript
// SALAH: Non-Tail Recursive (Limit ~50 elemen)
type NonTailReverse<T extends unknown[]> = 
  T extends [infer Head, ...infer Tail]
    ? [...NonTailReverse<Tail>, Head] // Pembentukan spread luar mencegah eliminasi stack
    : [];

// BENAR: Tail-Recursive dengan Accumulator (Limit ~1000 elemen)
type TailReverse<T extends unknown[], Acc extends unknown[] = []> = 
  T extends [infer Head, ...infer Tail]
    ? TailReverse<Tail, [Head, ...Acc]>
    : Acc;
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Naming Convention Khusus:** Awali type-level helper dengan kata kerja fungsional jika bertindak sebagai fungsi tipe (`Parse...`, `Extract...`, `Build...`).
2. **Defensive Depth Limiter:** Selalu pasang counter depth berbasis tuple (`Depth extends unknown[] = []`) untuk tipe yang beroperasi pada nested structures yang tidak berhingga.
3. **Fail-Fast Pattern:** Evaluasi kemungkinan status error di baris teratas conditional chain sebelum memproses transformasi yang memakan siklus komputasi besar.
4. **Isolasi Metaprogramming Complex Types:** Pisahkan tipe komputasi kompleks ke dalam file deklarasi internal (`*.types.ts`), jangan campuradukkan logika domain bisnis runtime dengan kode metaprogramming.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Mendiagnosis Bottleneck Kompilasi

Kompilator TypeScript menyediakan tools bawaan untuk menganalisis waktu pemrosesan type-level:

```bash
# 1. Menjalankan diagnosa performa instansiasi tipe
tsc --noEmit --extendedDiagnostics
```

Perhatikan output berikut:
```text
Files:                         125
Lines of Library code:       24520
Lines of User code:           3400
Identifiers:                 32049
Symbols:                     45102
Types:                       89400  <-- Waspada jika angka ini > 500,000
Instantiations:            1250320  <-- Indikasi Type Recursion berat
Memory used:               420311K
Check time:                  1.85s  <-- Waktu yang dihabiskan TypeChecker
Total time:                  2.30s
```

### Melacak Instansiasi Tipe yang Memperlambat Editor

```bash
# 2. Hasilkan jejak profile untuk Google Chrome DevTools / Speedscope
tsc --noEmit --generateTrace traceDir
```
Buka file `traceDir/trace.json` di `chrome://tracing` atau [Speedscope](https://www.speedscope.app/) untuk menemukan tipe spesifik yang memicu lonjakan siklus `checkTypeRelatedTo`.

---

## SEKSI 16 — KEAMANAN & HARDENING

### Mencegah Compiler Denial of Service (Type-Level DoS)

Kode type-level yang ditulis secara buruk dapat membekukan Language Server Protocol (TSServer) di VS Code / WebStorm, mengakibatkan konsumsi memori 100% CPU core hingga editor *crash*.

**Metode Hardening (Maximum Depth Guard):**

```typescript
type EnforceDepthLimit<
  DepthArray extends unknown[], 
  MaxDepth extends number = 10
> = DepthArray['length'] extends MaxDepth ? true : false;

type SafeDeepTraverse<
  T, 
  Depth extends unknown[] = []
> = EnforceDepthLimit<Depth, 5> extends true
  ? unknown // Paksa penghentian evaluasi tipe
  : T extends object
    ? { [K in keyof T]: SafeDeepTraverse<T[K], [...Depth, unknown]> }
    : T;
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Tidak ada `console.log` di dalam sistem tipe. Untuk menginspeksi nilai sementara saat menulis type-level program, gunakan teknik berikut:

### 1. Print Debug via Type Identity Projection

```typescript
export type Debug<T> = { [K in keyof T]: T[K] } & unknown;
```

### 2. Static Assertion Harness (`Expect` & `Equal`)

Gunakan framework assertion tingkat tipe standar industri:

```typescript
export type Equal<X, Y> = 
  (<T>() => T extends X ? 1 : 2) extends 
  (<T>() => T extends Y ? 1 : 2) ? true : false;

export type Expect<T extends true> = T;

// Contoh Unit Test Tingkat Tipe:
type TestReverse = Expect<Equal<Reverse<[1, 2, 3]>, [3, 2, 1]>>;
// @ts-expect-error Jika evaluasi salah, kompilator membunyikan alarm disini
type TestFail = Expect<Equal<Reverse<[1, 2]>, [1, 2]>>;
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```typescript
// Pattern Matching Tuple
type Shift<T> = T extends [unknown, ...infer R] ? R : [];

// Anti-Distribution Wrapper
type IsStrictUnion<T, U = T> = (T extends any ? (U extends T ? false : true) : never) extends false ? false : true;

// Template Literal String Manipulation
type CamelCase<S extends string> = S extends `${infer P1}_${infer P2}${infer P3}`
  ? `${Lowercase<P1>}${Uppercase<P2>}${CamelCase<P3>}`
  : Lowercase<S>;

// Non-Empty Array
type NonEmptyArray<T> = [T, ...T[]];

// Extract Object Keys by Value Type
type KeysOfType<T, V> = { [K in keyof T]-?: T[K] extends V ? K : never }[keyof T];
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Apa tipe keluaran dari ekspresi `type Res = never extends string ? true : false` dan mengapa demikian?**
   * *Jawaban:* `true`. Nilai `never` adalah *bottom type* di TypeScript, yang merupakan subtipe dari semua tipe data lainnya, sehingga assignability check menghasilkan true (selama tipe bukan naked type parameter yang memicu union distribution).

2. **Kapan conditional types bersifat distributif (*distributive conditional types*)?**
   * *Jawaban:* Ketika tipe yang diuji pada sisi kiri kata kunci `extends` merupakan sebuah *naked type parameter* (variabel generik murni tanpa dibungkus struktur lain seperti array, tuple, function, atau promise).

3. **Bagaimana cara mencegah evaluasi distributif pada tipe generik `T`?**
   * *Jawaban:* Bungkus kedua belah pihak operator `extends` di dalam konstruksi tuple mono-elemen: `[T] extends [Target]`.

4. **Apa fungsi keyword `infer` dan di mana keyword tersebut legal digunakan?**
   * *Jawaban:* `infer` berfungsi mendeklarasikan variabel tipe dinamis yang nilainya diekstrak dari pencocokan pola struktural (*pattern matching*). `infer` hanya legal digunakan di dalam klausa kondisional `extends`.

5. **Apa penyebab utama error `TS2589: Type instantiation is excessively deep and possibly infinite`?**
   * *Jawaban:* Rekursi tipe yang melampaui batas instansiasi kompilator TypeScript (biasanya ~50 untuk non-tail calls, atau ~1000 untuk tail-call optimization) atau kondisi terminasi rekursi yang tidak pernah tercapai.

---

### Soal Tingkat Menengah (Intermediate)

6. **Mengapa `[A] extends [B] ? true : false` terkadang berbeda perilakunya dengan `A extends B ? true : false` saat `A` bernilai union `string | number`?**
   * *Jawaban:* Pada kasus kedua, terjadi distribusi union sehingga evaluasi berjalan terpisah untuk tiap anggota union dan hasilnya di-union-kan kembali (`(string extends B...) | (number extends B...)`). Pada kasus pertama, distribusi dibatalkan, dan union diperlakukan sebagai satu kesatuan utuh.

7. **Jelaskan mengapa implementasi equality check berikut dianggap standar emas:**
   ```typescript
   type Equal<X, Y> = (<T>() => T extends X ? 1 : 2) extends (<T>() => T extends Y ? 1 : 2) ? true : false;
   ```
   * *Jawaban:* Implementasi ini mengandalkan aturan internal kompilator terkait *conditional type assignability of generic functions*. Kompilator menolak substitusi dua fungsi generik tersebut kecuali `X` dan `Y` sepenuhnya identik secara tipe, mampu membedakan kasus ekstrem seperti `any` vs `unknown`, serta varian kesetaraan modifiers seperti `readonly`.

8. **Bagaimana cara mendeteksi tipe `any` tanpa terjebak oleh kemampuannya menyamar menjadi tipe lain?**
   * *Jawaban:* Menggunakan ekspresi interseksi `0 extends 1 & T ? true : false`. Karena `1 & any` menghasilkan tipe `any`, dan `0 extends any` bernilai `true`. Untuk tipe lain selain `any`, `1 & T` menghasilkan tipe yang tidak assignable dari `0`.

9. **Apa pengaruh flag kompilator `--generateTrace` terhadap analisis efisiensi metaprogramming?**
   * *Jawaban:* Opsi ini mengekspor berkas log tracing JSON yang mencatat waktu tepat dan stack instansiasi tipe yang diproses oleh TypeChecker, memungkinkan pengembang menemukan titik *bottleneck* instansiasi rekursif melalui visualizer seperti Chrome Tracing atau Speedscope.

10. **Bagaimana mekanisme Tail-Recursion Elimination bekerja pada sistem tipe TypeScript versi 4.5 ke atas?**
    * *Jawaban:* Jika pemanggilan tipe rekursif berada tepat di cabang terminal tanpa ada operasi pembungkus lebih lanjut (seperti tuple spread di luar pemanggilan rekursif), kompilator mengevaluasi iterasi secara serial internal tanpa menambah kedalaman instansiasi frame checker, menaikkan batas komputasi dari ~50 ke ~1000 iterasi.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Project: Type-Safe SQL Query Builder & Schema Parser

Bangun mesin type-level yang mampu memvalidasi sintaks SQL dasar dan mengekstrak parameter output secara tepat tanpa runtime validator.

#### Spesifikasi Kebutuhan:

1. **Buat Parser Kalimat SQL:**
   * Mendukung parsing query berbentuk:
     `SELECT id, name, email FROM users WHERE id = :userId`
2. **Kebutuhan Type-Level Engine:**
   * Ekstrak kolom yang dipilih (`id`, `name`, `email`).
   * Ekstrak parameter dinamis yang diawali titik dua (`:userId`).
   * Cocokkan dengan Interface Database Schema:
     ```typescript
     interface DatabaseSchema {
       users: {
         id: number;
         name: string;
         email: string;
         isVerified: boolean;
       };
       posts: {
         id: number;
         userId: number;
         title: string;
         content: string;
       };
     }
     ```
3. **Keluaran yang Diharapkan:**
   * Fungsi helper `sqlQuery(query, params)`:
     * Menolak saat *compile time* jika kolom atau tabel tidak terdaftar pada `DatabaseSchema`.
     * Mengembalikan tipe array objek yang hanya berisi key kolom yang dipilih (`Pick<DatabaseSchema[Table], SelectedColumns>[]`).
     * Memaksa argument `params` menyediakan nilai dengan tipe yang cocok dari field terkait.

#### Starter Code:

```typescript
type Trim<S extends string> = S extends `${' ' | '\t' | '\n'}${infer R}` 
  ? Trim<R> 
  : S extends `${infer R}${' ' | '\t' | '\n'}` 
    ? Trim<R> 
    : S;

type Split<S extends string, Delimiter extends string> = 
  S extends `${infer Head}${Delimiter}${infer Tail}`
    ? [Trim<Head>, ...Split<Tail, Delimiter>]
    : [Trim<S>];

// Implementasikan tipe-tipe di bawah ini:
export type ParseSelectQuery<TSQL extends string> = unknown;

export type ExecuteQueryResult<TSQL extends string, TSchema> = unknown;

// Runtime Stub
export function executeSql<
  TSQL extends string, 
  TSchema = DatabaseSchema
>(
  query: TSQL, 
  params: any // Ganti any dengan inferensi tipe parameter SQL
): ExecuteQueryResult<TSQL, TSchema> {
  // Logic runtime SQL query executor
  return {} as any;
}
```

#### Kriteria Keberhasilan:
* Error kompilasi muncul seketika jika developer mengetik `SELECT passwordHash FROM users`.
* Ekstrak parameter `:userId` secara presisi mewajibkan `{ userId: number }`.
* Type inference pada return function tidak boleh bertipe `any` atau `unknown`, melainkan array dari entitas yang dipilih: `{ id: number; name: string; email: string }[]`.