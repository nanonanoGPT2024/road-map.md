# BAB 05: Quiz, Challenge, & Knowledge Check
**Type-Level Programming & Metaprogramming**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Distributive Conditional Types & Naked Type Parameters**  
   Jelaskan secara presisi mekanisme internal *distributive conditional types* pada TypeScript. Mengapa ekspresi `type ToArray<T> = T extends any ? T[] : never;` menghasilkan `(string[] | number[])` saat dievaluasi dengan `ToArray<string | number>`, sedangkan `type ToArrayNonDistributive<T> = [T] extends [any] ? T[] : never;` menghasilkan `(string | number)[]`? Kapan perilaku distributif ini justru menjadi *anti-pattern*?

2. **Mekanisme dan Batasan Keyword `infer`**  
   Bagaimana TypeScript compiler (`tsc`) menyelesaikan inferensi tipe ketika keyword `infer` digunakan di beberapa posisi yang memiliki variansi berbeda (misalnya, di posisi *covariant* vs *contravariant*) dalam conditional type yang sama? Jelaskan konsekuensi strukturalnya terhadap pembentukan union type atau intersection type.

3. **Homomorphic vs Non-Homomorphic Mapped Types**  
   Apa perbedaan struktural dan semantik antara *homomorphic mapped type* (seperti `type Readonly<T> = { readonly [P in keyof T]: T[P] }`) dan *non-homomorphic mapped type* (seperti `type Record<K extends keyof any, T> = { [P in K]: T }`) dalam mempertahankan modifier properti (`readonly`, optional `?`), *symbol keys*, dan pemetaan array/tuple?

4. **Template Literal Types & String Manipulation Semantics**  
   Bagaimana compiler menangani kompleksitas kombinatorial ketika melakukan ekspansi terhadap template literal types yang menggabungkan beberapa union types berukuran besar (misalnya: `` `${Protocol}_${Domain}_${Action}` ``)? Pada titik apa compiler memicu error *union size limit*, dan bagaimana representasi internal string literal type di memory AST?

5. **Key Remapping via Clause `as` dan Filtering Properti**  
   Jelaskan bagaimana sintaks `[K in keyof T as NewKeyType]` mengeksekusi transformasi metadata tipe. Bagaimana mekanisme penyaringan (filtering) properti terjadi ketika `NewKeyType` dievaluasi menjadi tipe `never`, dan bagaimana perbedaan mendasarnya dibanding pendekatan runtime filtering?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Rekursi Type-Level dan Tail-Call Optimization (TCO)**  
   TypeScript 4.5 memperkenalkan optimasi evaluasi rekursi bersyarat (*tail-recursion elimination on conditional types*). Analisis potongan tipe di bawah ini:
   ```typescript
   // Tipe A: Non-tail-recursive
   type ReverseA<T extends any[]> = T extends [...infer Rest, infer Last]
     ? [Last, ...ReverseA<Rest>]
     : [];

   // Tipe B: Tail-recursive (Accumulator pattern)
   type ReverseB<T extends any[], Acc extends any[] = []> = T extends [infer First, ...infer Rest]
     ? ReverseB<Rest, [First, ...Acc]>
     : Acc;
   ```
   Mengapa `ReverseA` mencapai batas *maximum call stack* (*Type instantiation is excessively deep and possibly infinite*) pada tuple dengan kedalaman ~50 elemen, sedangkan `ReverseB` mampu menangani hingga ~1000 elemen? Jelaskan arsitektur stack evaluasi tipe pada compiler engine TypeScript.

2. **Edge-Case Parsing: Handling `any`, `never`, dan `unknown` pada Conditional Types**  
   Tuliskan hasil evaluasi tipe berikut dan jelaskan secara analitis mengapa TypeScript compiler memprosesnya demikian:
   ```typescript
   type IsNever<T> = T extends never ? true : false;
   type IsAny<T> = boolean extends (T extends never ? true : false) ? true : false; // Atau evaluasi (0 extends 1 & T)

   type TestNever = IsNever<never>; // Mengapa menghasilkan never, bukan true?
   type TestAny = IsNever<any>;     // Mengapa menghasilkan boolean (true | false)?
   ```
   Bagaimana cara mendesain tipe predikat `IsNever<T>` yang 100% robust dan tidak terdistribusi secara keliru?

3. **Index Access Types & Union Distribution Fallacies**  
   Perhatikan kasus berikut:
   ```typescript
   type EventMap = {
     CLICK: { x: number; y: number };
     HOVER: { elementId: string };
   };

   // Mengapa Payload Union di bawah ini menghasilkan properti yang tidak sinkron 
   // saat digunakan sebagai parameter fungsi bersamaan?
   type BadHandler = (
     event: keyof EventMap,
     payload: EventMap[keyof EventMap]
   ) => void;
   ```
   Jelaskan fenomena *type-safety leakage* di atas. Bagaimana Anda merekonstruksi signature fungsi tersebut menggunakan *discriminated unions* atau *generic type constraints* agar `payload` terkunci secara atomik dengan `event` yang diparsing tanpa *type casting* (`as`)?

4. **Contravariance Extraction via Function Arguments**  
   Jelaskan matematika type-level di balik trik konversi *Union ke Intersection* (`UnionToIntersection<U>`):
   ```typescript
   type UnionToIntersection<U> = 
     (U extends any ? (k: U) => void : never) extends ((k: infer I) => void) 
       ? I 
       : never;
   ```
   Bagaimana prinsip variansi subtipe fungsi (*parameter positions are contravariant*) memaksa compiler untuk menginferensikan `I` sebagai intersection alih-alih union?

5. **Diagnostic Tracing: Menemukan Type Instantiation Leaks**  
   Saat menjalankan `tsc --extendedDiagnostics` atau `--generateTrace`, parameter metrik apa yang menandakan adanya komputasi type-level yang eksponensial? Jika ditemukan bahwa `Check time` memakan waktu 45 detik dan `Instantiations` mencapai jutaan, langkah diagnostik teknis apa yang harus dilakukan untuk mengisolasi tipe rekursif yang bermasalah?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Compiler Crash dan CI/CD Freeze pada Monorepo Skala Enterprise
Sebuah monorepo berskala besar (300+ paket) menggunakan library internal Type-Safe Database ORM yang dibangun dengan template literal query parser. Setelah migrasi ke schema yang lebih kompleks dengan relasi tabel mencapai kedalaman 8 level, proses CI pipeline membeku (*hang*) selama 25 menit sebelum akhirnya crash dengan error:
```text
FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory
Error: Type instantiation is excessively deep and possibly infinite. ts(2589)
```
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda mengonfigurasi `tsc` trace profiling (`--generateTrace <dir>`) dan menganalisis visualisasi performance tracing (via Chrome DevTools / `analyze-trace`) untuk mendeteksi simpul rekursi tipe yang memicu lonjakan alokasi memori heap?
  2. Pendekatan arsitektur tipe apa yang harus diterapkan untuk membatasi kedalaman evaluasi (*depth-limiting counter pattern*) pada relational query parser tersebut guna mencegah compiler crash tanpa mengorbankan keamanan tipe runtime?

### Skenario B: Generic RPC Framework & Payload Deserialization Type Mismatch
Sebuah sistem High-Frequency Trading menggunakan generic RPC client yang memetakan method backend ke TypeScript type definitions menggunakan end-to-end type extraction:
```typescript
type RPCResponse<T> = T extends () => Promise<infer R> ? R : never;
```
Ketika backend menambahkan endpoint yang mengembalikan tipe union kompleks mengandung `any` dan `void` opsional, sistem validasi payload type-level mengalami *silent degradation*: `RPCResponse` dievaluasi menjadi `any` secara implisit di production. Akibatnya, data payload yang corrupt lolos dari compiler checks dan memicu catastrophic failure di runtime trade execution.
* **Pertanyaan Diagnostik:**
  1. Mengapa keberadaan tipe `any` pada sub-elemen union response dapat merusak resolusi conditional type dan menyebabkan seluruh cabang inferensi runtuh menjadi `any` (*contagious any*)?
  2. Buatlah sebuah arsitektur defensive type extractor yang memvalidasi *nominal typing invariants*, menolak `any` secara eksplisit, dan mengembalikan `CompileError<"Payload contains unverified any">` alih-alih me-resolve tipe yang tidak aman.

### Skenario C: Trade-off Arsitektur: Dynamic Zero-Cost Abstraction vs DX Developer
Tim Core Infrastructure merancang sistem form/state management baru. Arsitek tipe menginginkan validasi nested path string literal yang sangat granular (contoh: `Path<User>` dapat mengekstrak `profile.addresses[0].geo.lat`). Namun, implementasi berbasis recursive template literal types ini menyebabkan autocompletion VS Code/IDE lag hingga 4–6 detik setiap kali developer mengetik tanda kutip `"`.
* **Pertanyaan Diagnostik:**
  1. Evaluasi *cost-to-benefit ratio* dari perancangan type-level autocompletion yang terlalu agresif terhadap produktivitas developer. Mengapa *compiler cache misses* terjadi secara masif pada pola recursive template literal types yang mengevaluasi array indices?
  2. Rancang strategi refaktorisasi arsitektur tipe hybrid yang mempertahankan strict type checking saat *final build/compilation*, namun menyediakan *lightweight non-blocking evaluation fallback* ketika IDE berada dalam kondisi interaktif/editing.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Type-Safe Deep Patch & Path Accessor Engine

#### Problem:
Sebagian besar library *deep object manipulation* (seperti `lodash.get` atau `lodash.set`) kehilangan konteks tipe atau menggunakan `any` pada skenario objek hierarki dalam yang memiliki array, dynamic record, tuple, dan properti opsional. Tugas Anda adalah membangun *Type-Level Engine* komprehensif tanpa implementasi runtime eksternal (fokus murni pada type definition file `.d.ts` / type-level program).

#### Requirements:
Rancang dan implementasikan type utilities berikut:

1. **`DeepPath<T>`**:
   Mengekstrak seluruh path yang valid dari object `T` sebagai union string literal yang dinotasikan dengan dot notation.
   * Mendukung nested objects: `a.b.c`
   * Mendukung array/tuple indexing: `items.0.id` atau `items[0].id` (pilih salah satu standar representasi secara konsisten, preferensi: `items.0.name` atau `items[0].name`).
   * Menghentikan rekursi pada tipe primitif, `Date`, `RegExp`, `Function`, `Map`, dan `Set`.
   * Harus memiliki kedalaman maksimum (*depth limiter*) hingga 6 level untuk mencegah compiler stack overflow.

2. **`DeepPathValue<T, P extends DeepPath<T>>`**:
   Mengekstrak tipe nilai akhir yang ditunjuk oleh path `P`.
   * Menangani properti opsional secara akurat (jika `user?: { profile: { name: string } }`, maka path `user.profile.name` harus menghasilkan tipe `string | undefined`).

3. **`DeepPatch<T, U>`**:
   Menerapkan *patch structural update* pada object `T` menggunakan object patch `U`.
   * Properti pada `U` bersifat opsional di setiap level hierarki.
   * Jika tipe di `U` adalah array, sistem harus memungkinkan penggantian parsial elemen tuple atau full array mutation.
   * Mengubah tipe properti target secara type-safe dan immutable.

#### Constraints:
* **Strict Type Safety**: Dilarang menggunakan `any` di seluruh deklarasi (wajib menggunakan `unknown`, `never`, conditional checks, dan generic constraints).
* **Recursion Guard**: Wajib menggunakan *depth counter tuple* (misal: `Depth extends [...infer D, any]`) untuk mencegah komputasi infinite loop.
* Compiler options: Menggunakan TypeScript target `>= 5.0` dengan `--strict true`.

#### Expected Output (Contoh Verifikasi Compile-Time):
```typescript
interface UserProfile {
  id: string;
  metadata: {
    tags: string[];
    settings?: {
      theme: "light" | "dark";
      notifications: {
        email: boolean;
        sms: boolean;
      };
    };
  };
  metrics: [number, number]; // Tuple
}

// 1. Verifikasi DeepPath
type Paths = DeepPath<UserProfile>;
// Valid Paths harus menyertakan:
// "id" | "metadata" | "metadata.tags" | `metadata.tags.${number}` | 
// "metadata.settings" | "metadata.settings.theme" | "metadata.settings.notifications.email" |
// "metrics.0" | "metrics.1"

// 2. Verifikasi DeepPathValue
type Test1 = DeepPathValue<UserProfile, "metadata.settings.theme">;
// Expected: "light" | "dark" | undefined (karena settings optional)

type Test2 = DeepPathValue<UserProfile, "metrics.0">;
// Expected: number

// 3. Verifikasi DeepPatch
type PatchedUser = DeepPatch<UserProfile, {
  metadata: {
    settings: {
      theme: "dark";
    }
  }
}>;
// PatchedUser harus mempertahankan struktur UserProfile yang lengkap,
// namun memastikan penimpaan tipe terjadi secara presisi dan non-destructive.
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara naked type parameter (`T extends ...`) yang memicu auto-distribution dengan wrapped type parameter (`[T] extends [...]`).
- [ ] Dampak variansi argumen fungsi (contravariance) dalam type-level programming untuk mengonversi union types menjadi intersection types.
- [ ] Batasan recursi type instantiation pada engine TypeScript (TCO conditional types vs tree-shaped instantiation limits).
- [ ] Evaluasi semantik tipe `never` (empty set) dan tipe `any` (top/bottom escape hatch) dalam branch conditional types.
- [ ] Perbedaan performa compiler antara *Homomorphic Mapped Types* dan *Non-Homomorphic Mapped Types*.
- [ ] Cara profiling performa kompilasi menggunakan flag `--extendedDiagnostics` dan visualisasi visual tracing `--generateTrace`.

### Saya tidak perlu menghafal:
- [ ] Nilai eksak internal limit stack depth dari compiler `tsc` di setiap minor version TypeScript (cukup pahami batas rata-ratanya dan polanya).
- [ ] Kompleksitas kode internal implementasi C++ parser dari V8 engine yang menjalankan JavaScript engine compiler TypeScript.
- [ ] Sintaks pustaka pihak ketiga (seperti `type-fest` atau `ts-toolbelt`) di luar pemahaman fundamental native TypeScript primitives.

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan *tail-recursive accumulator pattern* pada type-level functions untuk mencegah error *type instantiation is excessively deep*.
- [ ] Mendesain pattern depth counter menggunakan generic tuple (`Depth extends [any, ...infer Rest]`) untuk membatasi kedalaman pemrosesan recursive types.
- [ ] Menggunakan string template literal types yang dipadukan dengan clause `as` untuk mentransformasi and memfilter keys dari complex structural interfaces.
- [ ] Mengidentifikasi dan memperbaiki *type instantiation bottlenecks* yang menyebabkan IDE lag dan compiler heap memory out of bounds.
- [ ] Menulis type-level assertions menggunakan conditional types dan generic verification (`Equals<A, B>`, `Expect<T>`) untuk kebutuhan unit testing pada tipe.