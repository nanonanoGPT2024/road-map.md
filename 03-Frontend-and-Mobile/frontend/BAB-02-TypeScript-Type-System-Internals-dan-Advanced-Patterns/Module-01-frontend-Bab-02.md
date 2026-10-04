# Modul Pembelajaran: TypeScript Type System Internals & Advanced Patterns

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** 03-Frontend-and-Mobile
* **Jalur Pembelajaran:** Frontend Engineering
* **Bab:** 02 — Advanced Language Semantics & Type Systems
* **Modul:** 01 — TypeScript Type System Internals & Advanced Patterns
* **Target Tingkat Keahlian:** Advanced to Staff Engineer
* **Prasyarat Pengetahuan:**
  * Pemahaman mendalam tentang JavaScript runtime semantics (ES2022+), prototype chain, dan event loop.
  * Kemampuan dasar TypeScript: interface, type aliases, union types, intersection types, generics sederhana.
  * Pengalaman membangun aplikasi skala besar menggunakan Node.js atau modern frontend framework (React, Vue, dsb).
* **Estimasi Waktu Penyelesaian:** 12 - 16 Jam (termasuk implementasi kode dan penyelesaian tantangan praktikum).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Membedah Compiler Architecture:** Menganalisis alur eksekusi internal TypeScript Compiler (`tsc`), mulai dari fase Parsing (Scanner/Parser ke AST), Semantic Analysis (Binder & Checker), hingga Emitter.
2. **Menguasai Teori Type System:** Menjelaskan secara matematis dan praktis prinsip *Structural Subtyping*, *Soundness vs. Completeness*, serta aturan *Variance* (Covariance, Contravariance, Invariance, dan Bivariance).
3. **Mengonstruksi Type-Level Computation Tingkat Tinggi:** Merancang operasi logika kompleks pada level tipe menggunakan *Conditional Types*, *Distributive Conditional Types*, *Mapped Types*, *Template Literal Types*, dan keyword `infer`.
4. **Menerapkan Advanced Nominal Typing Pattern:** Mengimplementasikan pola *Branded/Flavor Types* untuk mencegah cacat logika domain primitif (*primitive obsession*) yang tidak dapat dideteksi oleh structural typing standar.
5. **Membangun Type-Safe Domain Specific Abstractions:** Mengembangkan parser dan query builder berbasis tipe statis yang memvalidasi struktur string secara *zero-runtime overhead*.
6. **Mengoptimalkan Performa Type Checking:** Mendiagnosis degradasi waktu kompilasi (*compile-time latency*), mengeliminasi *deep recursion instantiations*, dan menstrukturkan tipe agar efisien bagi memori *Type Checker*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Komputasi Dua Lapisan (The Dual-Layer Mental Model)

Salah satu lompatan paradigma paling krusial bagi seorang Staff Engineer adalah memahami bahwa TypeScript bukanlah JavaScript dengan anotasi sintaks semata. TypeScript mengeksekusi **dua mesin komputasi yang independen namun berjalan paralel**:

```
+-----------------------------------------------------------------------+
| LAPISAN 1: TYPE-LEVEL RUNTIME (Pure Turing-Complete Functional System) |
|   - Waktu Eksekusi : Saat Kompilasi (tsc / Language Server / IDE)    |
|   - Karakteristik  : Murni Fungsional, Imutabel, Evaluasi Statis      |
|   - Entitas        : Types, Generics, Tuples, Mapped/Conditional Types|
|   - Efek Samping   : NOL (Tergusur habis saat emisi JavaScript)       |
+-----------------------------------------------------------------------+
                                   |
                  (Erase Types via Compilation / Transpile)
                                   v
+-----------------------------------------------------------------------+
| LAPISAN 2: VALUE-LEVEL RUNTIME (Imperative/OOP JavaScript Engine)     |
|   - Waktu Eksekusi : Saat Runtime (V8, JavaScriptCore, Hermes, Node)  |
|   - Karakteristik  : Mutable, Event-Driven, I/O Bound                 |
|   - Entitas        : Variables, Functions, Closures, Prototype Chains |
|   - Efek Samping   : Mutasi Memori, Jaringan, DOM, Disk Storage       |
+-----------------------------------------------------------------------+
```

### Type System sebagai Proof Assistant

Berhentilah memandang tipe sekadar sebagai "dokumentasi aktif" atau "pencegah properti `undefined`". Pandanglah sistem tipe TypeScript sebagai **sistem pembuktian matematis** (merujuk pada *Curry-Howard Isomorphism*):
* Tipe adalah sebuah **Proposisi** atau Teorema.
* Nilai (*value*) atau ekspresi kode adalah **Bukti** dari proposisi tersebut.
* Jika kode berhasil dikompilasi tanpa galat (*error*), Anda telah membuktikan secara matematis bahwa program Anda memenuhi spesifikasi kontrak tipe yang dideklarasikan.

### Structural Subtyping vs. Nominal Subtyping

Mayoritas bahasa pemrograman berorientasi objek tradisional (Java, C++, C#) menerapkan *Nominal Subtyping*, di mana hubungan subtipe ditentukan eksplisit melalui deklarasi nama (`class Dog extends Animal`).

TypeScript mengadopsi **Structural Subtyping** (sering disebut *Compile-Time Duck Typing*):
> "Jika $T$ memiliki setidaknya seluruh anggota properti yang dimiliki oleh $S$, maka $T$ adalah subtipe dari $S$ ($T \le S$), terlepas dari deklarasi namanya."

Mental model ini menuntut kewaspadaan: dua tipe domain yang secara semantik bisnis sepenuhnya bertolak belakang (misalnya `UserId` dan `OrderId`) dianggap identik oleh TypeScript jika representasi strukturalnya sama (misalnya keduanya `string`). Di sinilah teknik tingkat lanjut seperti *Branding* menjadi mutlak diperlukan.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur internal `tsc` bekerja melalui pipa pemrosesan modular bertahap:

```
[Source Code: .ts]
       |
       v
+--------------+
|   Scanner    |  --> Mengubah rangkaian karakter teks menjadi token leksikal
+--------------+
       | Tokens
       v
+--------------+
|    Parser    |  --> Membangun Abstract Syntax Tree (AST)
+--------------+      Output: Node-node AST dengan relasi parent-child
       |
       v
+--------------+
|    Binder    |  --> Analisis relasi ruang lingkup (Scope) tanpa tipe
+--------------+      Output: Symbols (Menghubungkan Deklarasi AST ke Identifier)
       |
       v
+--------------+
|   Checker    |  <-- INTI MESIN TIPE:
+--------------+      - Memeriksa kesesuaian tipe (Type Inference & Assignment)
       |              - Melakukan Type Resolution & Instantiation
       |              - Menjalankan alur komputasi tipe bersyarat
       | Diagnostics (Error/Warnings)
       v
+--------------+
|   Emitter    |  --> Menghapus informasi tipe (Erasure) & Transformasi ES Target
+--------------+      Output: .js, .d.ts, .js.map
```

### Alur Kerja Mesin Pemeriksa Tipe (Checker Mechanics)

Ketika `Checker` memproses ekspresi kompleks seperti `type Result = Resolve<T>`, alur resolusi internalnya bergerak melalui cabang hierarki penentuan tipe:

```
[Ekspresi Tipe: T extends U ? X : Y]
                |
                v
       Apakah T merupakan Union?
       (Distributive Check)
         /              \
     [Ya]                [Tidak]
     /                      \
Pecah Union per elemen:      Evaluasi Hubungan Subtipe:
T1 extends U ? X : Y        Apakah T Subtipe dari U?
       |                               /          \
T2 extends U ? X : Y                [Ya]          [Tidak]
       |                             /              \
Gabungkan Hasil (Union Result)   Ekstraksi:     Eksekusi Jalur False:
                                 infer P?       Resolusi Tipe Y
                                   /    \
                                [Ya]   [Tidak]
                                /         \
                   Dapatkan P dari T    Resolusi Tipe X
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Representasi Memori: AST, Node, dan Symbol

Di dalam compiler TypeScript:
* **`Node`**: Titik representasi struktural kode pada AST. Diberikan properti integer `pos`, `end`, dan `kind` (mengacu pada enum `SyntaxKind`).
* **`Symbol`**: Entitas semantik yang memetakan identifier fisik ke sebuah entitas yang memiliki ruang lingkup (*named entity*). Satu `Symbol` dapat mereferensikan beberapa `Node` AST (misal: penggabungan *Declaration Merging* antara `interface` dan `namespace`).
* **`Type`**: Representasi abstrak sistem tipe dalam memori kompilator. Objek `Type` dibentuk dan dievaluasi secara dinamis oleh `Checker`. Contoh internal type flag: `TypeFlags.Union`, `TypeFlags.Object`, `TypeFlags.TypeParameter`.

### 2. Aturan Kompatibilitas Tipe & Variance

Variance mendeskripsikan bagaimana subtyping antara tipe kompleks (misalnya fungsi atau struktur generics) berkaitan dengan subtyping antara tipe komponennya.

Secara formal matematis:
Misalkan $A \le B$ menandakan $A$ adalah subtipe dari $B$.
Fungtor tipe $F$ dikatakan:
* **Covariant** jika $A \le B \implies F\langle A \rangle \le F\langle B \rangle$.
* **Contravariant** jika $A \le B \implies F\langle B \rangle \le F\langle A \rangle$.
* **Invariant** jika $F\langle A \rangle \le F\langle B \rangle$ hanya jika $A \equiv B$.
* **Bivariant** jika $A \le B \implies F\langle A \rangle \le F\langle B \rangle$ DAN $F\langle B \rangle \le F\langle A \rangle$.

Di TypeScript:
* **Nilai Kembali Fungsi (*Return Types*)**: Bersifat **Covariant**.
* **Parameter Fungsi (*Parameter Types*)**:
  * Secara bawaan struktural (jika `strictFunctionTypes: false`): **Bivariant** (alasan kompatibilitas historis DOM event).
  * Dengan `strictFunctionTypes: true`: **Contravariant**.

### 3. Soundness vs. Completeness

Sistem tipe ideal bersifat:
* **Sound**: Jika program lulus kompilasi, dijamin tidak ada operasi pada runtime yang melanggar kontrak tipe (misal: `100% type-safe`).
* **Complete**: Mampu membuktikan semua program valid yang secara logis benar sebagai program yang lolos tipe.

TypeScript secara eksplisit **Trade-off: Pragmatic Non-Soundness**. TypeScript tidak sepenuhnya sound (*soundness compromises*) demi kenyamanan ekosistem JavaScript. Contoh lubang soundness bawaan:
1. Akses array out-of-bounds (mengembalikan `T`, bukan `T | undefined`, kecuali flag `noUncheckedIndexedAccess` diaktifkan).
2. Mekanisme `any` yang mematikan pemeriksaan tipe.
3. Mutasi properti objek covariant.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Conditional Types & Distributive Law

Sintaks dasar: `T extends U ? X : Y`.
Jika `T` adalah parameter generic telanjang (*naked type parameter*) dan argumen yang diberikan berupa *union*, maka operasi tersebut otomatis terdistribusi (*distribute*):

$$\left( A \cup B \right) \text{ extends } U \ ? \ X : Y \implies \left( A \text{ extends } U \ ? \ X : Y \right) \cup \left( B \text{ extends } U \ ? \ X : Y \right)$$

Untuk mencegah sifat distributif, bungkus kedua sisi dengan tanda kurung siku:
`[T] extends [U] ? X : Y`.

### 2. Pattern Matching via `infer`

Keyword `infer` memperkenalkan variabel tipe baru dalam klausa kondisional yang diekstraksi secara deduktif oleh Checker.

```typescript
type UnwrapPromise<T> = T extends Promise<infer U> ? U : T;
```
Ketika Checker mencocokkan `Promise<string>` terhadap pola `Promise<infer U>`, Checker menginferensi bahwa $U \equiv \text{string}$.

### 3. Template Literal Types & Tail-Call Recursion

Template Literal Types memungkinkan komputasi manipulasi string statis. Pada TypeScript 4.5+, mesin Checker dioptimalkan dengan rekursi ekor (*tail-call recursion elimination*) hingga batas kedalaman tertentu (umumnya 1.000 iterasi rekursif, melampaui batas standar 50 iterasi untuk komputasi non-tail recursive).

### 4. Nominal Typing melalui Flavoring dan Branding

Karena TypeScript bersifat struktural, kita dapat merekayasa sistem tipenya agar berperilaku nominal dengan menyisipkan properti diskriminator fiktif (*phantom property*) yang dioperasikan pada fase kompilasi:

```typescript
declare const __brand: unique symbol;
export type Brand<T, B> = T & { readonly [__brand]: B };
```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kumpulan demonstrasi pola tipe tingkat lanjut yang dibangun secara inkremental.

```typescript
// ============================================================================
// CONTOH 1: Branded Types Implementation
// ============================================================================
declare const BrandTag: unique symbol;

export type Branded<T, TBrand extends string> = T & {
  readonly [BrandTag]: TBrand;
};

export type UserId = Branded<string, "UserId">;
export type OrderId = Branded<string, "OrderId">;

export function createUserId(id: string): UserId {
  // Validasi runtime wajib sebelum melegalkan cast nominal
  if (!id.startsWith("usr_")) {
    throw new Error(`Format ID Pengguna tidak valid: ${id}`);
  }
  return id as UserId;
}

export function createOrderId(id: string): OrderId {
  if (!id.startsWith("ord_")) {
    throw new Error(`Format ID Pesanan tidak valid: ${id}`);
  }
  return id as OrderId;
}

// ============================================================================
// CONTOH 2: Non-Distributive Conditional Types
// ============================================================================
// Distributive:
export type DistributiveToArray<T> = T extends any ? T[] : never;
export type TestDist = DistributiveToArray<string | number>; 
// Hasil: string[] | number[]

// Non-Distributive:
export type NonDistributiveToArray<T> = [T] extends [any] ? T[] : never;
export type TestNonDist = NonDistributiveToArray<string | number>; 
// Hasil: (string | number)[]

// ============================================================================
// CONTOH 3: Deep Readonly Menggunakan Rekursi
// ============================================================================
export type Primitive = string | number | boolean | bigint | symbol | undefined | null;

export type DeepReadonly<T> = T extends Primitive | ((...args: any[]) => any)
  ? T
  : T extends Map<infer K, infer V>
  ? ReadonlyMap<DeepReadonly<K>, DeepReadonly<V>>
  : T extends Set<infer M>
  ? ReadonlySet<DeepReadonly<M>>
  : T extends Array<infer E>
  ? ReadonlyArray<DeepReadonly<E>>
  : { readonly [P in keyof T]: DeepReadonly<T[P]> };
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Menelaah blok kode `DeepReadonly<T>` dari Seksi 07:

1. `export type Primitive = string | number | ...`: Mendefinisikan himpunan tipe atomik yang tidak memiliki properti internal yang perlu diimutasikan.
2. `export type DeepReadonly<T> = T extends Primitive | ((...args: any[]) => any) ? T`: 
   * Mengevaluasi apakah `T` adalah tipe primitif atau fungsi.
   * Fungsi dikecualikan dari pemetaan objek agar fungsionalitas invocation-nya tetap valid tanpa diubah menjadi objek rekursif kosong `{}`.
3. `: T extends Map<infer K, infer V> ? ReadonlyMap<DeepReadonly<K>, DeepReadonly<V>>`:
   * Pola pencocokan tipe: Jika objek merupakan turunan `Map`, tangkap variabel generik internalnya (`K` dan `V`) menggunakan `infer`.
   * Ganti struktur tersebut dengan `ReadonlyMap`, dan eksekusi komputasi rekursif ke `K` dan `V`.
4. `: T extends Set<infer M> ? ReadonlySet<DeepReadonly<M>>`:
   * Identik dengan cabang `Map`, tetapi menginferensikan elemen skalar dalam `Set` dan memetakan ke interface `ReadonlySet`.
5. `: T extends Array<infer E> ? ReadonlyArray<DeepReadonly<E>>`:
   * Mengekstrak tipe elemen larik `E`, lalu membungkusnya dalam struktur mutlak `ReadonlyArray`.
6. `: { readonly [P in keyof T]: DeepReadonly<T[P]> }`:
   * Jika seluruh kondisi struktural di atas tidak terpenuhi, `T` dievaluasi sebagai objek murni (*record*).
   * Mapped types mengiterasi setiap kunci `P` dari `keyof T`, menambahkan modifier `readonly`, lalu memanggil kembali `DeepReadonly` secara rekursif pada nilai tipenya `T[P]`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Dynamic Enterprise Query Builder & Safe Event Bus
Pada sistem platform enterprise berskala besar (Micro-Frontend Architecture), aplikasi sering berinteraksi dengan API REST dinamis dan Message Bus yang kompleks. Sering muncul cacat perangkat lunak kritis berupa:
1. Pengiriman muatan (*payload*) event yang salah tipe ke channel tertentu.
2. Pengambilan path objek yang sangat dalam (*deeply nested properties*) yang memicu `TypeError: Cannot read properties of undefined` saat runtime.
3. Kueri filter database yang tidak memvalidasi apakah kolom yang dicari benar-benar ada pada entitas target.

Kita akan merekayasa:
1. **Strongly Typed Dot-Notation Path Flattener**: Mekanisme pengekstrakan path (misal: `"user.address.street"`) langsung divalidasi ke hierarki schema objek.
2. **Type-Safe Dynamic Filter & Query Operator System**: Menolak nama properti atau operator yang tidak kompatibel pada tingkat kompilasi.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON

Berikut implementasi sistem penanganan path dan query type-safe tanpa dependensi eksternal:

```typescript
// ============================================================================
// SYSTEM TYPE ENGINE: TYPE-SAFE EVENT BUS & OBJECT PATH ACCESSOR
// ============================================================================

/** Tipe dasar untuk mencegah rekursi tak berhingga */
type Prev = [never, 0, 1, 2, 3, 4, 5, ...never[]];

/**
 * Mengonversi struktur objek berlapis menjadi union string path yang dipisahkan titik (.)
 * Dilengkapi pembatas kedalaman rekursi hingga 4 lapis.
 */
export type NestedPaths<T, Depth extends number = 4> = [Depth] extends [never]
  ? never
  : T extends object
  ? {
      [K in keyof T]-?: K extends string | number
        ? `${K}` | (NestedPaths<T[K], Prev[Depth]> extends infer SubPath
            ? SubPath extends string
              ? `${K}.${SubPath}`
              : never
            : never)
        : never;
    }[keyof T]
  : never;

/**
 * Mengekstrak tipe data dari target path berbasis string eksplisit
 */
export type PathValue<T, P extends string> = P extends `${infer Head}.${infer Tail}`
  ? Head extends keyof T
    ? PathValue<T[Head], Tail>
    : never
  : P extends keyof T
  ? T[P]
  : never;

// ============================================================================
// DOMAIN IMPLEMENTATION: EVENT CONTRACT & EVENT BUS
// ============================================================================

export interface SystemEventContracts {
  "auth:login": {
    userId: string;
    session: { token: string; expiresAt: number };
  };
  "auth:logout": {
    userId: string;
    timestamp: number;
  };
  "billing:payment-processed": {
    transactionId: string;
    metadata: {
      amount: number;
      currency: "USD" | "IDR" | "EUR";
      payer: {
        address: {
          country: string;
          city: string;
        };
      };
    };
  };
}

export type EventCallback<T> = (payload: T) => void | Promise<void>;

export class StronglyTypedEventBus<TEvents extends Record<string, any>> {
  private listeners: {
    [K in keyof TEvents]?: Set<EventCallback<TEvents[K]>>;
  } = {};

  public subscribe<E extends keyof TEvents>(
    event: E,
    callback: EventCallback<TEvents[E]>
  ): () => void {
    if (!this.listeners[event]) {
      this.listeners[event] = new Set();
    }
    this.listeners[event]!.add(callback);

    return () => {
      this.listeners[event]?.delete(callback);
    };
  }

  public publish<E extends keyof TEvents>(
    event: E,
    payload: TEvents[E]
  ): void {
    const handlers = this.listeners[event];
    if (handlers) {
      handlers.forEach((callback) => {
        try {
          void callback(payload);
        } catch (error) {
          console.error(`[EventBus] Uncaught exception on event: ${String(event)}`, error);
        }
      });
    }
  }

  /**
   * Mengambil mutasi nested value dari event payload secara aman
   */
  public extractDeepProperty<
    E extends keyof TEvents,
    P extends NestedPaths<TEvents[E]>
  >(
    payload: TEvents[E],
    path: P
  ): PathValue<TEvents[E], P> {
    const segments = (path as string).split(".");
    let current: any = payload;

    for (const segment of segments) {
      if (current === null || current === undefined) {
        return undefined as PathValue<TEvents[E], P>;
      }
      current = current[segment];
    }

    return current as PathValue<TEvents[E], P>;
  }
}

// ============================================================================
// VERIFIKASI PENGGUNAAN TIPE SECARA PRAKTIS
// ============================================================================

const bus = new StronglyTypedEventBus<SystemEventContracts>();

// 1. Validasi Subscribe Type
bus.subscribe("billing:payment-processed", (payload) => {
  console.log(`Payment processed: ${payload.transactionId}`);
  
  // Mengambil tipe deep path dengan autocompletion dan validasi ketat
  const country = bus.extractDeepProperty(
    payload,
    "metadata.payer.address.country" // Type checked!
  );
  console.log(`Payer Country: ${country}`);
});

// 2. Validasi Publish Type
bus.publish("auth:login", {
  userId: "usr_9921",
  session: {
    token: "jwt.secret.payload",
    expiresAt: Date.now() + 3600000,
  },
});

// @ts-expect-error Kompilator menggagalkan jika ada properti hilang
bus.publish("auth:logout", {
  userId: "usr_9921",
  // Error: Property 'timestamp' is missing in type '{ userId: string; }'
});

// @ts-expect-error Kompilator menggagalkan jika path tidak valid
bus.extractDeepProperty(
  {} as SystemEventContracts["billing:payment-processed"],
  "metadata.invalid_property.address"
);
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Pendekatan | Kelebihan | Kelemahan / Trade-Off | Kapan Harus Digunakan | Kapan Harus Dihindari |
| :--- | :--- | :--- | :--- | :--- |
| **Branded Types (`type Id = string & { __brand }`)** | Mencegah assignment silang tipe primitif; 100% *zero runtime overhead*. | Memerlukan fungsi casting eksplisit (*type assertions*) di boundary masukan runtime. | ID entitas domain (UserId, OrderId), satuan ukur (*meters vs feet*), token terverifikasi. | Model data internal lokal sederhana yang tidak memiliki risiko ambiguitas semantik. |
| **Complex Recursive Mapped Types** | Fleksibilitas pemetaan struktur tak terbatas; *deep validation* yang sangat kaya. | Membebani memori compiler (`tsc`); waktu kompilasi meningkat drastis; error message sulit dibaca. | SDK Library public, API Client generator, ORM internal core. | Aplikasi frontend biasa dengan timeline iterasi fitur cepat dan resource CI terbatas. |
| **`unknown` vs `any`** | `unknown` mempertahankan type-safety penuh, memaksa penyempitan tipe (*type narrowing*). | Mengharuskan developer menulis kode penanganan kondisi redundan di runtime. | Parsing respons API eksternal tak terpercaya, boundary deserialisasi JSON. | Internal helper function yang sudah divalidasi oleh logic boundary sebelumnya. |
| **Union Discriminated vs Subclass Polymorphism** | Kompatibel dengan paradigma fungsional murni; mudah diserialisasi; penambahan operasi baru tidak mengubah kelas. | Menambahkan cabang tipe baru mengharuskan pemeriksaan manual di semua ekspresi `switch-case`. | State management (Redux Actions), UI State machines, API response payloads. | Hirarki domain yang membutuhkan *encapsulation*, enkapsulasi internal state dinamis, atau inheritance perilaku. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Empty Object Pitfall `{}`

```typescript
// PITFALL: Banyak developer mengira '{}' berarti "objek kosong".
const a: {} = "hello world"; // Valid!
const b: {} = 123;           // Valid!
const c: {} = { foo: "bar" };// Valid!
// const d: {} = null;      // Error
// const e: {} = undefined; // Error
```
*Mekanisme Internal:* Tipe `{}` merepresentasikan **semua nilai yang bukan `null` atau `undefined`**.
*Mitigasi:* Gunakan `Record<string, never>` untuk benar-benar menolak objek yang memiliki properti, atau `Record<string, unknown>` untuk objek dinamis umum.

### 2. Evaluasi Tipe `never` dalam Distributive Conditional Types

```typescript
type IsNever<T> = T extends never ? true : false;
type Test = IsNever<never>; // Hasilnya: never BUKAN true!
```
*Mekanisme Internal:* `never` dipandang sebagai *empty union* (union tanpa anggota). Ketika union kosong didistribusikan, operasi tersebut tidak dieksekusi sama sekali (nol iterasi), menghasilkan output `never`.
*Mitigasi:* Bungkus parameter menggunakan *tuple wrap*:
```typescript
type IsNeverCorrect<T> = [T] extends [never] ? true : false;
type TestFixed = IsNeverCorrect<never>; // Menghasilkan: true
```

### 3. Pemutusan Array Element Assignment via Contravariance

Jika sebuah interface memiliki method signature alih-alih property function, TypeScript memperlakukannya sebagai *bivariant* bahkan saat `--strictFunctionTypes` diaktifkan:

```typescript
interface AnimalComparer {
  compare(a: Animal, b: Animal): number; // Method syntax: Bivariant!
}
interface StrictComparer {
  compare: (a: Animal, b: Animal) => number; // Property syntax: Contravariant!
}
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Type Assertions Berlebihan (`as Type`)

```typescript
// SALAH: Type assertion membatalkan verifikasi compiler
const userData = JSON.parse(response) as UserProfile;
console.log(userData.profile.name); // Berisiko Uncaught TypeError!

// BENAR: Menggunakan Type Guard / Schema Parser (misal Zod / Internal Guard)
function isUserProfile(val: unknown): val is UserProfile {
  return (
    typeof val === "object" &&
    val !== null &&
    "profile" in val &&
    typeof (val as any).profile?.name === "string"
  );
}

const rawData: unknown = JSON.parse(response);
if (isUserProfile(rawData)) {
  console.log(rawData.profile.name); // Terjamin aman
}
```

### 2. Terjebak dalam Rekursi Tipe Tanpa Terminasi Dasar

```typescript
// SALAH: Tidak ada base case depth checker, memicu TS2589:
// "Type instantiation is excessively deep and possibly infinite."
type InfiniteTuple<T> = [T, ...InfiniteTuple<T>];

// BENAR: Menambahkan base case atau length counter
type FixedTuple<T, N extends number, R extends T[] = []> = 
  R["length"] extends N ? R : FixedTuple<T, N, [T, ...R]>;
```

### 3. Menggunakan `any` di Tempat yang Seharusnya Menggunakan Generics

```typescript
// SALAH: Kehilangan asosiasi relasional input dan output
function identity(arg: any): any {
  return arg;
}
const res = identity("my_string"); // res bertipe any

// BENAR: Menjaga inferensi identitas tipe
function identityTyped<T>(arg: T): T {
  return arg;
}
const safeRes = identityTyped("my_string"); // safeRes bertipe "my_string"
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Aktifkan Seluruh Strict Flags**:
   Pastikan berkas `tsconfig.json` memiliki:
   ```json
   {
     "compilerOptions": {
       "strict": true,
       "noUncheckedIndexedAccess": true,
       "exactOptionalPropertyTypes": true,
       "isolatedModules": true
     }
   }
   ```
2. **Favoritkan `type` untuk Komputasi Rumit, `interface` untuk Model Data Publik**:
   * Gunakan `interface` saat mendeklarasikan struktur objek atau kelas publik yang mungkin perlu diperluas melalui *Declaration Merging*.
   * Gunakan `type` alias saat membutuhkan *Union*, *Intersection*, *Tuples*, atau *Mapped/Conditional Types*.
3. **Penyempitan Exhaustiveness Menggunakan `never`**:
   Selalu pasang default exhaustive check pada `switch-case` discriminator:
   ```typescript
   function assertNever(x: never): never {
     throw new Error(`Unexpected object: ${JSON.stringify(x)}`);
   }
   ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI

Komputasi tipe yang berlebihan berdampak langsung pada performa Developer Experience (DX), seperti respons autocomplete IDE yang lambat dan pipeline CI yang membengkak.

### 1. Diagnostik Compiler Tracing

Analisis performa kompilasi dengan built-in tracing flags:
```bash
tsc --extendedDiagnostics
tsc --generateTrace traceDir
```
Gunakan Google Chrome tracing viewer (`chrome://tracing`) untuk menganalisis berkas trace JSON. Cari titik henti bottleneck pada event `checkVariableDeclaration` atau `resolveType`.

### 2. Kurangi Kompleksitas Mapped Type Unions

Pola komputasi tipe seperti pemetaan kartesian union ($N \times M$ combinations) mengeksplosikan memori compiler secara eksponensial.

```typescript
// BURUK: Menghasilkan 100 x 100 = 10,000 instansiasi tipe
type BigUnion = ...; // 100 members
type Cartesian = `${BigUnion}-${BigUnion}`; 

// MITIGASI: Hindari pembentukan template string dari massive union 
// dalam satu langkah tanpa boundary splitting.
```

### 3. Manfaatkan Caching Tipe Antarmuka (Interface Caching)

Compiler TypeScript melakukan caching internal pada nama deklarasi `interface`. Sementara `type` alias yang dibentuk secara ad-hoc anonim sering dievaluasi berulang kali saat Checker menelusuri representasi strukturalnya. Gunakan pembungkusan `interface` pada titik-titik generic yang berat.

---

## SEKSI 16 — KEAMANAN & HARDENING

Sistem tipe statis adalah lini pertahanan terdepan untuk mencegah kecacatan keamanan di arsitektur aplikasi frontend.

### 1. Mencegah XSS melalui Tainted String Branding

```typescript
declare const TaintedBrand: unique symbol;
declare const SanitizedHtmlBrand: unique symbol;

export type RawHtmlString = string & { readonly [TaintedBrand]: "Raw" };
export type SafeHtmlString = string & { readonly [SanitizedHtmlBrand]: "Sanitized" };

// Fungsi innerHTML hanya menerima SafeHtmlString
export function renderToDOM(target: HTMLElement, content: SafeHtmlString): void {
  target.innerHTML = content;
}

export function sanitizeInput(input: RawHtmlString): SafeHtmlString {
  // Eksekusi library sanitasi riil (misal DOMPurify)
  const clean = input.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "");
  return clean as SafeHtmlString;
}

const unsecureInput = "<script>stealCookies()</script>" as RawHtmlString;

// @ts-expect-error Pemasukan string mentah ditolak oleh sistem tipe!
renderToDOM(document.body, unsecureInput);

// Valid: String telah melalui fungsi sanitasi
renderToDOM(document.body, sanitizeInput(unsecureInput));
```

### 2. Mencegah Prototype Pollution pada Tingkat Tipe

Larang kunci internal prototype (`__proto__`, `constructor`, `prototype`) dimanipulasi melalui dynamic mapped type keys:

```typescript
export type SafePropertyKey<K extends string> = 
  K extends "__proto__" | "prototype" | "constructor" ? never : K;

export function safeSetProperty<T extends object, K extends string>(
  target: T,
  key: SafePropertyKey<K>,
  value: unknown
): void {
  Object.defineProperty(target, key as string, { value, enumerable: true });
}
```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### Teknik Debugging Tipe Statis

TypeScript tidak memiliki `console.log` bawaan untuk tipe. Sebagai gantinya, manfaatkan konstruksi tipe berikut untuk menginspeksi alur komputasi tipe:

```typescript
// Helper Debugger: Memaksa compiler menampilkan seluruh struktur objek tipe
export type Prettify<T> = {
  [K in keyof T]: T[K];
} & {};

// Helper Assert: Menguji equality statis antar dua tipe pada level kompilasi
export type Equals<X, Y> = 
  (<T>() => T extends X ? 1 : 2) extends 
  (<T>() => T extends Y ? 1 : 2) ? true : false;

export type Expect<T extends true> = T;

// Penggunaan Uji Regresi Tipe:
type ActualResult = PathValue<{ a: { b: string } }, "a.b">;
type ExpectedResult = string;

// Jika tipe Actual