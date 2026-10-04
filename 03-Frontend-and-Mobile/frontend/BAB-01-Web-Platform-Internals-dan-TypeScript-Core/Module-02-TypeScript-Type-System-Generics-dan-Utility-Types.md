# TypeScript Strict Type System, Generics, Type Narrowing, & Advanced Utility Types

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda mampu:

- **Mengaktifkan dan memahami** setiap flag dalam `strict` mode TypeScript serta menjelaskan apa yang masing-masing flag lindungi
- **Merancang Generic functions, classes, dan interfaces** dengan constraints, default types, dan conditional types yang tepat
- **Mengimplementasikan Type Narrowing** menggunakan `typeof`, `instanceof`, discriminated unions, type guards, dan assertion functions
- **Memanipulasi tipe kompleks** menggunakan utility types bawaan (`Partial`, `Required`, `Pick`, `Omit`, `Exclude`, `Extract`, `ReturnType`, `Parameters`, `Awaited`) dan membuat custom utility types sendiri
- **Mendiagnosis runtime error** yang disebabkan oleh kelemahan sistem tipe dan memperbaikinya menggunakan teknik yang tepat
- **Membangun type-safe API layer** yang mencegah kategori bug secara keseluruhan di level compile time
- **Membaca dan menulis** tipe kompleks seperti `infer`, template literal types, dan mapped types untuk kebutuhan production

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus sudah memahami:

| Konsep | Level yang Dibutuhkan |
|---|---|
| TypeScript dasar: `interface`, `type`, `enum` | Paham dan bisa menulis sendiri |
| JavaScript ES6+: arrow functions, destructuring, spread | Mahir |
| Konsep `any`, `unknown`, `never`, `void` | Pernah menggunakan, paham perbedaan dasar |
| Union types (`A \| B`) dan Intersection types (`A & B`) | Paham secara konseptual |
| Cara menjalankan TypeScript: `tsc`, `ts-node`, atau Vite | Bisa setup sendiri |
| Konsep asynchronous JavaScript: `Promise`, `async/await` | Mahir |

**Konsep yang TIDAK perlu diketahui terlebih dahulu:**
- Decorators (dibahas di modul lain)
- Module augmentation
- Declaration merging

---

## 3. Concept

### Fondasi Filosofi TypeScript

TypeScript bukan sekadar "JavaScript dengan tipe". TypeScript adalah **sistem pembuktian formal yang berjalan di compile time** — sebuah mesin yang memverifikasi kebenaran program Anda sebelum satu baris pun dieksekusi.

Sistem tipe TypeScript dibangun di atas tiga pilar fundamental:

**Pilar 1: Structural Typing (Duck Typing)**
TypeScript menggunakan *structural subtyping*, bukan *nominal subtyping*. Dua tipe dianggap kompatibel jika struktur mereka cocok, bukan berdasarkan nama atau deklarasi eksplisit.

```typescript
// Dua interface berbeda nama, tapi strukturnya kompatibel
interface Point2D { x: number; y: number }
interface Coordinate { x: number; y: number }

const p: Point2D = { x: 1, y: 2 }
const c: Coordinate = p // ✅ Valid! Strukturnya identik
```

**Pilar 2: Type Inference**
TypeScript mampu *menyimpulkan* tipe tanpa anotasi eksplisit. Semakin ketat mode-nya, semakin akurat inferensi ini.

**Pilar 3: Control Flow Analysis**
TypeScript menganalisis alur eksekusi kode Anda dan *mempersempit* tipe secara otomatis berdasarkan kondisi yang ada — inilah yang disebut **Type Narrowing**.

### Strict Mode: Bukan Sekadar Flag

`"strict": true` dalam `tsconfig.json` sebenarnya adalah shorthand yang mengaktifkan **8 flag sekaligus**:

| Flag | Masalah yang Dicegah |
|---|---|
| `strictNullChecks` | Mencegah `null`/`undefined` digunakan sebagai nilai valid tanpa pengecekan |
| `noImplicitAny` | Mencegah TypeScript menyimpulkan tipe `any` secara diam-diam |
| `strictFunctionTypes` | Memastikan parameter fungsi dicheck secara contravariant |
| `strictBindCallApply` | Memastikan `bind`, `call`, `apply` dicheck dengan benar |
| `strictPropertyInitialization` | Memastikan semua property class diinisialisasi di constructor |
| `noImplicitThis` | Mencegah `this` bertipe `any` di dalam fungsi biasa |
| `alwaysStrict` | Mengaktifkan ECMAScript strict mode di setiap file |
| `useUnknownInCatchVariables` | Mengubah tipe variabel `catch` dari `any` menjadi `unknown` |

### Generics: Abstraksi Atas Tipe

Generics adalah mekanisme yang memungkinkan Anda menulis kode yang **bekerja dengan berbagai tipe sekaligus** sambil tetap mempertahankan type safety. Ini adalah perbedaan fundamental antara:

- **`any`**: Menonaktifkan type checking — berbahaya
- **Generics**: Menunda penentuan tipe hingga waktu penggunaan — aman

### Type Narrowing: Penyempitan Tipe

Type narrowing adalah proses di mana TypeScript **mempersempit tipe yang lebih luas** (seperti `string | number`) menjadi tipe yang lebih spesifik berdasarkan pemeriksaan runtime yang Anda tulis.

### Advanced Utility Types: Meta-Programming di Level Tipe

Utility types adalah fungsi yang beroperasi pada level tipe — mereka menerima tipe sebagai input dan menghasilkan tipe baru sebagai output. Ini adalah **type-level programming**.

---

## 4. Why?

### Masalah Nyata yang Dipecahkan

**Masalah 1: The `null` Billion-Dollar Mistake**

Tony Hoare, penemu `null`, menyebutnya sebagai "billion-dollar mistake". Tanpa `strictNullChecks`, kode ini valid di TypeScript:

```typescript
// Tanpa strictNullChecks — TypeScript TIDAK mendeteksi ini
function getUser(id: string): User {
  return database.find(id) // Bisa return undefined!
}

const user = getUser("123")
console.log(user.name) // 💥 Runtime: Cannot read property 'name' of undefined
```

Dengan `strictNullChecks`, TypeScript memaksa Anda menangani `null`/`undefined` secara eksplisit.

**Masalah 2: Code Duplication vs. Type Safety**

Tanpa generics, Anda harus memilih antara duplikasi kode atau kehilangan type safety:

```typescript
// Opsi A: Duplikasi — type safe tapi tidak DRY
function sortNumbers(arr: number[]): number[] { ... }
function sortStrings(arr: string[]): string[] { ... }

// Opsi B: any — DRY tapi tidak type safe
function sort(arr: any[]): any[] { ... }

// Dengan Generics: DRY DAN type safe ✅
function sort<T>(arr: T[]): T[] { ... }
```

**Masalah 3: Runtime Type Errors yang Tidak Terdeteksi**

```typescript
// Tanpa type narrowing yang proper
function processInput(input: string | number) {
  return input.toUpperCase() // 💥 Error jika input adalah number
}
```

**Masalah 4: Tipe yang Tidak Sinkron dengan Data**

Ketika struktur data berubah (API response berubah, model database berubah), tipe-tipe yang didefinisikan manual menjadi out-of-sync. Utility types memungkinkan Anda **menurunkan tipe dari tipe lain** sehingga perubahan otomatis terpropagasi.

### Dampak Bisnis

Menurut studi Airbnb (2019), **38% bug production mereka bisa dicegah** dengan TypeScript. Stripe melaporkan bahwa migrasi ke TypeScript strict mode mengurangi bug tipe-terkait sebesar **45%** dalam 6 bulan pertama.

---

## 5. What?

### Definisi Teknis

**Strict Type System**
> Konfigurasi TypeScript yang mengaktifkan serangkaian pemeriksaan compile-time yang memaksimalkan deteksi error, menghilangkan implicit `any`, dan memastikan semua kasus null/undefined ditangani secara eksplisit.

**Generics**
> Mekanisme parametric polymorphism dalam TypeScript yang memungkinkan definisi fungsi, kelas, atau interface yang bekerja dengan berbagai tipe sambil mempertahankan hubungan tipe antara input dan output. Ditulis dengan syntax `<T>` di mana `T` adalah *type parameter*.

**Type Narrowing**
> Proses di mana TypeScript compiler mempersempit tipe union menjadi tipe yang lebih spesifik berdasarkan analisis control flow dari pemeriksaan runtime (type guards). Ini adalah fitur *flow-sensitive typing*.

**Utility Types**
> Tipe-tipe generik bawaan TypeScript yang melakukan transformasi pada tipe lain. Mereka adalah *type-level functions* — menerima tipe sebagai argumen dan menghasilkan tipe baru.

**Type Guard**
> Ekspresi yang melakukan pemeriksaan runtime dan memberikan informasi kepada TypeScript compiler tentang tipe variabel dalam scope tertentu. Dapat berupa:
> - Built-in: `typeof`, `instanceof`, `in`
> - User-defined: fungsi dengan return type `x is T`
> - Assertion functions: fungsi dengan `asserts x is T`

**Discriminated Union**
> Pattern di mana setiap member dari union type memiliki *literal type property* yang unik (discriminant) yang digunakan untuk membedakan antar member.

**Mapped Types**
> Tipe yang dibuat dengan mengiterasi key dari tipe lain dan mentransformasi setiap property.

**Conditional Types**
> Tipe yang memiliki logika bercabang: `T extends U ? X : Y` — jika `T` dapat di-assign ke `U`, hasilnya `X`, jika tidak, hasilnya `Y`.

**`infer` keyword**
> Digunakan dalam conditional types untuk *mengekstrak* tipe dari posisi tertentu dalam tipe yang lebih kompleks.

---

## 6. How?

### Mekanisme Internal Step-by-Step

#### 6.1 Bagaimana Strict Mode Bekerja

```
Source Code (.ts)
       │
       ▼
┌─────────────────────┐
│   TypeScript Parser  │ ← Mengubah source code menjadi AST
└─────────────────────┘
       │
       ▼
┌─────────────────────┐
│   Type Checker       │ ← Di sinilah strict flags bekerja
│                     │
│  1. Symbol Resolution│ ← Menghubungkan identifier ke deklarasi
│  2. Type Inference   │ ← Menyimpulkan tipe yang tidak dianotasi
│  3. Type Checking    │ ← Memverifikasi kompatibilitas tipe
│  4. Control Flow     │ ← Menganalisis alur untuk narrowing
└─────────────────────┘
       │
       ▼
┌─────────────────────┐
│   Emitter            │ ← Menghasilkan JavaScript output
└─────────────────────┘
```

#### 6.2 Bagaimana Generics Diselesaikan

Proses *type argument inference* untuk generics:

```
Panggilan: sort([1, 2, 3])
                │
                ▼
TypeScript melihat argumen: number[]
                │
                ▼
TypeScript mencocokkan dengan parameter: T[]
                │
                ▼
Inferensi: T = number
                │
                ▼
Return type menjadi: number[]
```

**Ketika ada multiple type parameters:**

```typescript
function zip<A, B>(a: A[], b: B[]): [A, B][] {
  return a.map((item, i) => [item, b[i]])
}

// Panggilan: zip([1, 2], ['a', 'b'])
// TypeScript menyimpulkan: A = number, B = string
// Return type: [number, string][]
```

#### 6.3 Bagaimana Type Narrowing Bekerja (Control Flow Analysis)

TypeScript membangun *control flow graph* dari kode Anda:

```
function process(value: string | number | null) {
    │
    ├── Titik masuk: value = string | number | null
    │
    ├── if (value === null) {
    │       │
    │       └── Di dalam blok: value = null ✓
    │           (TypeScript tahu ini null)
    │   }
    │
    ├── Setelah if: value = string | number
    │   (null sudah di-narrow out)
    │
    ├── if (typeof value === 'string') {
    │       │
    │       └── Di dalam blok: value = string ✓
    │   }
    │
    └── Setelah kedua if: value = number
        (string dan null sudah di-narrow out)
```

#### 6.4 Bagaimana Mapped Types Bekerja

```typescript
type Readonly<T> = {
  readonly [K in keyof T]: T[K]
}
```

Proses evaluasi untuk `Readonly<{ name: string; age: number }>`:

```
1. keyof T → "name" | "age"
2. Iterasi K = "name":
   - Key: "name" (dengan modifier readonly)
   - Value: T["name"] = string
3. Iterasi K = "age":
   - Key: "age" (dengan modifier readonly)
   - Value: T["age"] = number
4. Hasil: { readonly name: string; readonly age: number }
```

#### 6.5 Bagaimana `infer` Bekerja

```typescript
type ReturnType<T> = T extends (...args: any[]) => infer R ? R : never
```

Proses evaluasi untuk `ReturnType<() => string>`:

```
1. T = () => string
2. Apakah T extends (...args: any[]) => infer R?
   - Cocokkan: () => string dengan (...args: any[]) => infer R
   - TypeScript "menangkap" return type: R = string
3. Kondisi terpenuhi → hasilnya R = string
```

---

## 7. Analogy

### Analogi 1: Strict Mode = Inspeksi Bangunan

Bayangkan membangun gedung. Tanpa inspeksi (tanpa strict mode), Anda bisa membangun dengan cepat — tapi dinding mungkin tidak lurus, fondasi mungkin tidak kuat, dan kabel listrik mungkin tidak aman. Masalah baru terlihat ketika gedung sudah jadi dan ditempati (runtime).

Dengan inspektur bangunan (strict mode), setiap tahap konstruksi diverifikasi.
