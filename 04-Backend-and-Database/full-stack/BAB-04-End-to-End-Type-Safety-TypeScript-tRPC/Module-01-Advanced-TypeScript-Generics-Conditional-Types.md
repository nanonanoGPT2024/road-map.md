---
[⬅️ BAB 03 Quiz & Challenge](../BAB-03-Meta-Frameworks-Nextjs-App-Router/BAB-03-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: tRPC & Zod Validation ➡️](./Module-02-tRPC-Zod-Validation-dan-Contract-First-APIs.md)
---

# Module 01: Advanced TypeScript: Generics, Conditional Types, Template Literals, & Mapped Types

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Menguasai sistem tipe tingkat lanjut (*Type-Level Programming*) TypeScript: **Generics dengan Batasan (`T extends Record<string, any>`)**, **Conditional Types (`T extends U ? X : Y`)**, dan kata kunci **`infer`**.
- Memahami dan memanfaatkan **Template Literal Types** untuk membuat tipe rute URL atau format event string yang aman saat kompilasi.
- Menguasai **Mapped Types** dan teknik transformasi tipe data: memodifikasi modifier (`readonly`, `?`, `-readonly`, `-?`), serta utilitas bawaan (`Pick`, `Omit`, `Partial`, `Required`, `Record`).
- Mengimplementasikan pola **Discriminated Unions (Tagged Unions)** untuk pemodelan state mesin (*State Machines*) yang bebas dari inkonsistensi runtime.
- Menerapkan teknik **Type Narrowing**: pemeriksaan tipe kustom (*User-Defined Type Guards* menggunakan predikat `value is Type`) dan asersi ketat (*Assertion Functions*).

---

## 2. Prerequisite
- Pemahaman sintaks dasar TypeScript: interfaces, types, enums, dan fungsi.
- Pemahaman konsep pemrograman berbasis objek dan fungsional di JavaScript.
- Pemahaman ekosistem runtime Node.js dan browser.

---

## 3. Concept
Bagi banyak pengembang pemula, TypeScript sering dipandang hanya sebagai "alat bantu linter" untuk menambahkan keterangan tipe sederhana seperti `: string` atau `: number`.

Namun di tingkat arsitektur enterprise, sistem tipe TypeScript adalah **bahasa pemrograman komputasi murni yang dieksekusi saat kompilasi (*Turing-Complete Type System*)**.

Sebelum satu baris kode pun dieksekusi di browser atau server, TypeScript mampu:
- Menganalisis skema database SQL dan menurunkannya secara otomatis menjadi tipe komponen frontend.
- Memverifikasi apakah rute API `/api/users/:id/posts` memiliki parameter yang cocok dengan URL yang dipanggil.
- Menjamin bahwa jika sebuah event bertipe `'PAYMENT_FAILED'`, objek tersebut **wajib** memiliki atribut `failureReason`, namun jika bertipe `'PAYMENT_SUCCESS'`, objek tersebut **dilarang** memiliki atribut `failureReason` (**Discriminated Unions**).

---

## 4. Why?
Tanpa penguasaan TypeScript tingkat lanjut:
1. **Penyakit `any` (Type Erosion):** Developer yang kebingungan mengetik tipe data kompleks menyerah dan menggunakan `any`. Satu tipe `any` akan menular ke seluruh basis kode (*Type Contagion*), melenyapkan seluruh manfaat keamanan TypeScript dan mengubahnya kembali menjadi JavaScript biasa yang rawan runtime error.
2. **Runtime Crash Akibat Typo Nama Properti:** Mengakses `user.profilPic` (seharusnya `profilePic`) di produksi menghasilkan error klasik: `TypeError: Cannot read properties of undefined`.
3. **Inkonsistensi State Objek (Impossible States):** Membuat state seperti `{ isLoading: true, isError: true, data: [...] }`. Kondisi ini secara logika mustahil (bagaimana bisa sedang memuat data sekaligus menghasilkan error dan data sudah ada?). Discriminated Unions memusnahkan kemungkinan *Impossible States* ini selamanya.
4. **Duplikasi Definisi Tipe Data:** Menulis ulang interface TypeScript secara manual setiap kali ada perubahan skema database atau API, menciptakan inkonsistensi antara backend dan frontend.

---

## 5. What? (Katalog Operator Tingkat Lanjut TypeScript)

| Operator / Fitur | Sintaks TypeScript | Penjelasan Teknis & Contoh |
|---|---|---|
| **Generic Constraints** | `<T extends Entity>` | Membatasi parameter tipe hanya untuk tipe turunan tertentu |
| **Conditional Types** | `T extends string ? A : B` | Percabangan logika tipe: jika T turunan string, gunakan tipe A, jika bukan gunakan B |
| **Keyword `infer`** | `T extends (...args: any[]) => infer R ? R : any` | Mengekstrak tipe internal di dalam deklarasi bersarang (contoh: ReturnType) |
| **Template Literal Types**| `type Route = \`/api/\${string}\`` | Memvalidasi pola teks format tertentu saat kompilasi |
| **Mapped Types** | `{ [K in keyof T]: T[K] }` | Membuat tipe baru dengan melakukan iterasi pada seluruh kunci properti tipe T |
| **Key Remapping (`as`)** | `{ [K in keyof T as \`get\${Capitalize<string & K>}\`]: () => T[K] }` | Mengubah nama kunci secara dinamis selama proses pemetaan |
| **Discriminated Union** | `type Action = { type: 'A'; val: number } \| { type: 'B'; msg: string }` | Gabungan tipe yang memiliki satu properti pembeda (*Discriminant Tag*) unik |

---

## 6. How? (Membedah Anatomi Type-Level Programming)

### A. Pola `infer`: Mengekstrak Tipe Return dari Promise Asinkron
Bagaimana cara utilitas bawaan `Awaited<T>` bekerja di balik layar?
```typescript
// Jika T adalah sebuah Promise<R>, ekstrak tipe R di dalamnya secara rekursif!
type CustomAwaited<T> = T extends Promise<infer R> ? CustomAwaited<R> : T;

// Pengujian:
type Result = CustomAwaited<Promise<Promise<{ id: number; name: string }>>>;
// Hasil Tipe: { id: number; name: string } (Otomatis terurai murni!)
```

### B. Pola Discriminated Unions (Menghilangkan Impossible States)
```typescript
// CARA SALAH (MEMICU IMPOSSIBLE STATES):
interface BadFetchState {
  isLoading: boolean;
  isError: boolean;
  data: string[] | null;
  errorMessage: string | null;
}
// State { isLoading: true, isError: true } dapat terjadi secara tidak sengaja!

// CARA BENAR (DISCRIMINATED UNIONS):
type SafeFetchState =
  | { status: 'IDLE' }
  | { status: 'LOADING' }
  | { status: 'SUCCESS'; data: string[] }
  | { status: 'ERROR'; errorMessage: string };

function renderUI(state: SafeFetchState) {
  switch (state.status) {
    case 'LOADING':
      return <Spinner />;
    case 'SUCCESS':
      // TypeScript otomatis mempersempit tipe (Type Narrowing)!
      // state.data DIJAMIN ADA dan bukan null!
      return <List items={state.data} />;
    case 'ERROR':
      // state.errorMessage DIJAMIN ADA!
      return <Alert message={state.errorMessage} />;
  }
}
```

---

## 7. Analogy
- **Tipe Primitif (`string`, `number`) ibarat Bentuk Geometri Sederhana:** Anda punya balok lingkaran dan balok kotak kayu mainan anak. Balok kotak hanya muat di lubang kotak.
- **Generics ibarat Cetakan Puding Fleksibel:** Anda memiliki satu cetakan silikon berbentuk bintang. Anda bisa menuangkan puding cokelat, agar-agar stroberi, atau lilin cair ke dalamnya. Cetakan menjamin bentuk akhirnya selalu bintang, apapun bahan yang Anda masukkan.
- **Conditional Types & `infer` ibarat Mesin Pemindai Sinar-X di Bandara:** Mesin memeriksa koper bawaan penumpang. Jika di dalam koper terdapat laptop (**`T extends LaptopCarrier<infer L>`**), mesin otomatis mengeluarkan laptop tersebut (**`L`**) untuk diperiksa secara terpisah di baki khusus.

---

## 8. Diagram: Alur Type Narrowing via User-Defined Type Guard

```
Variabel 'input': tipe tidak diketahui (unknown)
                    │
                    ▼
      { isApiResponse(input)? }  <── (Fungsi Type Guard: input is ApiResponse)
                    │
        ┌───────────┴───────────┐
     (TRUE)                  (FALSE)
        │                       │
        ▼                       ▼
TypeScript Compiler:    TypeScript Compiler:
Variabel 'input'        Variabel 'input'
RESMI DIPERSEMPIT       TETAP unknown.
menjadi 'ApiResponse'.  Dilarang mengakses properti internal!
Bebas akses input.data!
```

---

## 9. Simple Example: Template Literal Types untuk Validasi Format Rute API

```typescript
type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE';
type ApiVersion = 'v1' | 'v2';
type Resource = 'users' | 'orders' | 'products';

// Membangun tipe kombinasi otomatis menggunakan Template Literals
type ApiEndpoint = `${HttpMethod} /api/${ApiVersion}/${Resource}`;

// Pengujian Validitas:
const validEndpoint1: ApiEndpoint = 'GET /api/v1/users';     // ✅ VALID
const validEndpoint2: ApiEndpoint = 'POST /api/v2/orders';   // ✅ VALID

// @ts-expect-error: Salah metode atau format path
const invalidEndpoint: ApiEndpoint = 'PATCH /api/v3/users';  // ❌ ERROR KOMPILASI!
```

---

## 10. Practical Example: User-Defined Type Guard & Mapped Types Deep Partial

```typescript
// 1. Mapped Types: Membuat seluruh properti bersarang menjadi opsional secara rekursif
type DeepPartial<T> = T extends Function
  ? T
  : T extends Array<infer U>
  ? Array<DeepPartial<U>>
  : T extends object
  ? { [K in keyof T]?: DeepPartial<T[K]> }
  : T;

interface UserProfile {
  id: string;
  name: string;
  preferences: {
    theme: 'light' | 'dark';
    notifications: {
      email: boolean;
      push: boolean;
    };
  };
}

// User dapat mengupdate hanya field bersarang tertentu
const updatePayload: DeepPartial<UserProfile> = {
  preferences: {
    notifications: {
      email: false // Seluruh properti lain tetap opsional tanpa error!
    }
  }
};

// 2. User-Defined Type Guard: Memvalidasi objek saat runtime
function isUserProfile(obj: unknown): obj is UserProfile {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'id' in obj &&
    'preferences' in obj &&
    typeof (obj as any).name === 'string'
  );
}
```

---

## 11. Real World Example: Arsitektur Type-Safe SDK Stripe / Vercel

Pada SDK resmi perusahaan infrastruktur global:
- Stripe SDK menggunakan Conditional Types dan Overload Signatures:
  - Jika developer memanggil `stripe.customers.create({ email: '...' })`, fungsi mengembalikan tipe `Promise<Customer>`.
  - Jika developer memanggil `stripe.customers.del('cus_123')`, fungsi otomatis mengembalikan tipe `Promise<DeletedCustomer>` (yang memiliki field `deleted: true`).
- Developer tidak perlu membaca dokumentasi eksternal berulang kali; editor VS Code secara otomatis menampilkan saran autocompletion yang 100% akurat sesuai konteks pemanggilan fungsi.

---

## 12. Trade-offs

| Pendekatan Pengetikan | Keamanan Kode | Kecepatan Kompilator (`tsc`) | Keterbacaan bagi Pemula |
|---|---|---|---|
| **Tipe Sederhana (Basic Interfaces)** | Menengah | Sangat Cepat | Sangat Mudah Dipahami |
| **Advanced Types (Conditional & `infer`)**| **Maksimal (Zero Bugs)** | Sedang (Perlu kalkulasi kompilator)| Sulit (Butuh keahlian khusus) |
| **Penggunaan `any` Sembarangan** | Nol (Bahaya Runtime Crash) | Instan | Menipu (False sense of safety)|

---

## 13. When To Use
- **Gunakan Generics dengan Constraints:** Saat membangun fungsi pembantu (*Helper Functions*), custom React hooks, pustaka ORM, atau komponen UI generik (seperti `<Table<T> items={items} />`).
- **Gunakan Discriminated Unions:** Untuk memodelkan status transaksi finansial, respon API (`success: true | false`), dan event reducer.
- **Gunakan User-Defined Type Guards (`is`):** Saat mem-parsing data mentah dari sumber eksternal (seperti response `fetch`, payload webhook, atau data dari `localStorage`).

---

## 14. When NOT To Use
- **Jangan Ciptakan Tipe Kompleks yang Terlalu Esoterik Tanpa Kebutuhan Nyata:** Menulis 50 baris tipe meta-programming hanya untuk memvalidasi satu fungsi string sederhana adalah bentuk *Overengineering* yang menyiksa rekan tim pengembang lain.
- **Jangan Gunakan Type Assertion (`as unknown as TargetType`) untuk Membungkam Compiler:** Melakukan *Type Bypassing* dengan `as Type` adalah membohongi diri sendiri; jika data asli saat runtime berbeda, aplikasi akan tetap mengalami crash fatal!

---

## 15. Common Mistakes
1. **Mengabaikan Strict Null Checks:** Mematikan opsi `"strict": true` di `tsconfig.json`, membiarkan nilai `null` dan `undefined` menyusup tanpa peringatan compiler.
2. **Penyalahgunaan `Record<string, any>`:** Menggunakan `any` di dalam Record alih-alih `Record<string, unknown>`. Nilai `unknown` memaksa developer melakukan verifikasi tipe sebelum mengakses properti.
3. **Mengubah Tuple Menjadi Array Biasa:** Menulis `const roles = ['admin', 'user']` (tipe: `string[]`), alih-alih `const roles = ['admin', 'user'] as const` (tipe tuple readonly: `readonly ['admin', 'user']`).

---

## 16. Best Practices

### Must Have
- Selalu aktifkan opsi **`"strict": true`** dan **`"noImplicitAny": true`** di file konfigurasi `tsconfig.json`.
- Gunakan **`unknown` alih-alih `any`** untuk data input yang belum diketahui strukturnya.
- Manfaatkan modifier **`as const`** untuk membekukan literal array atau objek menjadi tipe konstanta immutable.

### Recommended
- Gunakan utilitas standar bawaan TypeScript (`Awaited`, `ReturnType`, `Parameters`, `Extract`, `Exclude`) sebelum mencoba menulis conditional types kustom dari nol.
- Terapkan pola **Exhaustive Switch Checking** menggunakan tipe `never` untuk memastikan seluruh variasi Discriminated Union tertangani.

### Advanced
- Gabungkan Template Literal Types dengan **Type-Safe Routing** untuk memvalidasi parameter URL dinamis (`/users/[id]/settings`) secara otomatis saat compile-time.

---

## 17. Troubleshooting

| Gejala Error | Indikasi Akar Masalah | Langkah Investigasi | Tindakan Perbaikan |
|---|---|---|---|
| **Error: `Type 'string' is not assignable to type 'never'`** | Switch case Discriminated Union tidak menangani seluruh kemungkinan variasi tipe | Periksa semua case pada blok switch | Tambahkan blok case untuk variasi tipe yang terlewat |
| **Peringatan: `Type instantiation is excessively deep and possibly infinite`** | Tipe kondisional rekursif tidak memiliki kondisi dasar penghenti (*Base Case*) | Audit definisi tipe rekursif | Tambahkan batas kedalaman rekursi atau kondisi terminasi tipe primitif |
| **Error: `Property 'data' does not exist on type 'unknown'`** | Variabel bertipe `unknown` diakses langsung tanpa proses Type Narrowing | Cek baris kode sebelum pemanggilan | Gunakan type guard `typeof`, `instanceof`, atau predikat kustom `is` |

---

## 18. Exercise
1. Tulis definisi tipe `DeepReadonly<T>` menggunakan Mapped Types rekursif yang membekukan seluruh properti objek dan anak-anaknya.
2. Rancang Discriminated Union untuk transaksi pembayaran e-commerce (`PENDING`, `SETTLED`, `EXPIRED`, `REFUNDED`) dan buktikan TypeScript mendeteksi error jika ada status yang lupa ditangani di blok switch.
3. Tulis fungsi type guard `isNonEmptyArray<T>(arr: T[]): arr is [T, ...T[]]` yang menjamin array memiliki minimal satu elemen.

---

## 19. Challenge
Rancang sistem **Type-Safe Event Emitter & Event Bus Engine**:
1. Definisikan antarmuka tipe peta event (*Event Map*) yang memetakan nama event string ke tipe payload spesifik.
2. Implementasikan class `TypedEventEmitter<TEvents>` yang hanya mengizinkan `emit` dan `on` untuk nama event dan payload yang cocok 100% dengan skema compile-time!

---

## 20. Summary
Sistem tipe tingkat lanjut TypeScript adalah perisai pelindung utama arsitektur software modern. Dengan menguasai Generics berbatas, Conditional Types dengan `infer`, Mapped Types, serta Discriminated Unions yang memusnahkan *Impossible States*, seorang Full-Stack Engineer mengubah kesalahan manusia (*Human Errors*) menjadi umpan balik kompilasi instan, menjamin stabilitas perangkat lunak sebelum menyentuh server produksi.

---
[⬅️ BAB 03 Quiz & Challenge](../BAB-03-Meta-Frameworks-Nextjs-App-Router/BAB-03-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: tRPC & Zod Validation ➡️](./Module-02-tRPC-Zod-Validation-dan-Contract-First-APIs.md)
---
