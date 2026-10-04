# BAB 04: Quiz, Challenge, & Knowledge Check
**Advanced Generics & Parametric Polymorphism**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Taksonomi Polimorfisme
Bandingkan secara formal konsep **Parametric Polymorphism**, **Ad-hoc Polymorphism** (function overloading), dan **Subtyping (Inclusion Polymorphism)** dalam sistem tipe TypeScript. Bagaimana TypeScript compiler merekonsiliasi parametric polymorphism dengan structural subtyping ketika tipe generik memiliki constraint subtipe (`<T extends Base>`)?

### Soal 1.2: Mekanika Distributive Conditional Types
Jelaskan aturan internal compiler yang memicu **Distributive Conditional Types**. Mengapa tipe bersyarat `T extends any ? F<T> : never` mengevaluasi `T = A | B` menjadi `F<A> | F<B>`, sedangkan ekspresi tuple `[T] extends [any] ? F<T> : never` tidak mendistribusikannya? Apa definisi formal dari "naked type parameter" dalam konteks ini?

### Soal 1.3: Semantik Inferensi Type via `infer`
Bagaimana compiler menentukan lokasi dan fase evaluasi untuk kata kunci `infer` di dalam cabang ekstensi tipe kondisional? Jelaskan apa yang terjadi secara struktural ketika sebuah variabel tipe di-`infer` secara simultan dari beberapa posisi kandidat: kapan hasilnya menjadi **Union** (misal: beberapa posisi kovarian) dan kapan menjadi **Intersection** (misal: posisi kontravarian)?

### Soal 1.4: Kaidah Variance (Kovarian, Kontravarian, Invarian, Bikovarian)
Diberikan tipe `Sub` yang merupakan subtipe dari `Super` (`Sub extends Super`). Definisikan relasi assignability dari `Generic<Sub>` terhadap `Generic<Super>` jika parameter generik `T` berada pada:
1. Posisi Return Value saja.
2. Posisi Parameter Fungsi saja (di bawah flag `--strictFunctionTypes`).
3. Posisi Properti Readonly vs Mutable.
Jelaskan signifikansi tipe-tipe tersebut terhadap *soundness* komputasi tipe TypeScript.

### Soal 1.5: Prefix dan Modifier Pemetaan Generik
Jelaskan peran kompilasi dari *generic parameter modifier* `const` (diperkenalkan pada TS 5.0) dan utility bawaan `NoInfer<T>` (diperkenalkan pada TS 5.4). Masalah ketidaksesuaian inferensi tipe apa yang diselesaikan oleh masing-masing fitur ini dalam desain pustaka tingkat lanjut?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik TS2589 (Type Instantiation Recursion Limit)
Kode rekursif generik Anda memicu galat: `TS2589: Type instantiation is excessively deep and possibly infinite`. 
1. Apa batasan kuantitatif internal TypeScript compiler engine untuk kedalaman rekursi tipe?
2. Bagaimana teknik tail-call-optimization (TCO) tipe menggunakan pola akumulator tuple (`[...Acc, Current]`) mereduksi kedalaman stack instansiasi tipe compiler?

### Soal 2.2: Anomali `never` pada Conditional Distribution
Ekspresi tipe berikut menghasilkan perilaku tak terduga:
```typescript
type IsNever<T> = T extends never ? true : false;
type Result = IsNever<never>; // Hasilnya: never, bukan true!
```
Bedah arsitektur internal compiler yang menyebabkan ekspresi tersebut menghasilkan `never`. Tuliskan implementasi perbaikan kanonikal untuk `IsNever<T>` agar mengevaluasi ke `true` secara tepat, dan jelaskan mengapa modifikasi tersebut bekerja.

### Soal 2.3: Interaksi Method Shorthand vs Function Property
Perhatikan generic interface berikut:
```typescript
interface ProcessorMethod<T> {
  process(item: T): void;
}
interface ProcessorProp<T> {
  process: (item: T) => void;
}
```
Ketika `--strictFunctionTypes` diaktifkan, jelaskan mengapa `ProcessorMethod<T>` berperilaku bikovarian sedangkan `ProcessorProp<T>` berperilaku kontravarian murni terhadap `T`. Mengapa desain historis ini dipertahankan oleh TypeScript Core Team?

### Soal 2.4: Type Variable Widening & Contextual Typing Failure
Diberikan pipeline higher-order generic:
```typescript
declare function pipe<A, B, C>(
  fn1: (a: A) => B,
  fn2: (b: B) => C
): (a: A) => C;

// Kasus kegagalan:
const result = pipe(
  (x) => x.length,
  (len) => len > 0
);
```
Mengapa compiler gagal melakukan contextual typing terhadap parameter `x` sehingga menghasilkan error `Parameter 'x' implicitly has an 'any' type`? Langkah apa yang harus diambil pada level generic signature architecture untuk mengaktifkan inferensi dua arah (*bidirectional contextual typing*)?

### Soal 2.5: Union vs Intersection Reduction dalam Homomorphic Mapped Types
Jelaskan perbedaan mendasar antara *Homomorphic Mapped Types* (misal: `type Map<T> = { [K in keyof T]: ... }`) dan non-homomorphic mapped types ketika diterapkan pada tipe Union generik (`T = A | B`). Mengapa homomorphic mapped type mendistribusikan union secara otomatis, sedangkan non-homomorphic mapped type justru melebur relasi properti menjadi perpotongan (`intersection`) atau himpunan kunci gabungan?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Exhaustion Memori Compiler pada Event Broker
Sebuah monorepo enterprise berskala jutaan baris kode mengalami kegagalan CI build akibat crash compiler V8: `JavaScript heap out of memory`. Investigasi menemukan tipe data `TypedEventBus` generik yang dirancang untuk mendistribusikan ratusan domain payload:

```typescript
type EventRegistry = {
  'USER_CREATED': { id: string; timestamp: number };
  'PAYMENT_PROCESSED': { txId: string; amount: number };
  // ... 500+ event lainnya
};

type DeepNestedEnvelope<T> = {
  metadata: { traceId: string; traceFlags: number };
  data: T;
  audit: { user: string; timestamp: Date };
};

type EventDispatcher = {
  dispatch<K extends keyof EventRegistry>(
    event: K,
    payload: DeepNestedEnvelope<EventRegistry[K]>
  ): void;
};
```
Ketika ratusan listener dan publisher mereferensikan wrapper generik berbasis mapped type rekursif di seluruh codebase, type-checker instantiator memory meledak secara eksponensial.
* **Pertanyaan Diagnostik:** 
  1. Bagaimana compiler mengkalkulasi kompleksitas memori dari resolusi referensi mapped type generik terhadap union berskala besar?
  2. Susun ulang struktur arsitektur generic dispatcher di atas agar inferensi tipe payload ditangguhkan (*deferred instantiation*) dan membatasi ukuran heap compiler tanpa mengorbankan type safety saat dispatch.

---

### Skenario B: Kerusakan Data Relasional pada Query Engine Akibat Dynamic Inference Fallthrough
Sebuah engine ORM internal mendukung dynamic query projection berbasis tuple generik:

```typescript
type Entity = {
  id: string;
  name: string;
  profile: { bio: string; avatarUrl: string };
  posts: Array<{ postId: string; title: string }>;
};

// Target: select('profile.bio', 'posts.title') -> Type safe returned projection
```
Engine query runtime mengizinkan nested path via dot-notation string literals (`"profile.bio"`). Namun, implementasi generik parser tipe path nested rekursif saat ini menghasilkan `any` atau fallback ke `string` jika kedalaman melebihi 2 level, yang menyebabkan field data yang salah diekstraksi lolos audit kompilasi dan merusak state persistensi database produksi.
* **Pertanyaan Diagnostik:**
  1. Identifikasi penyebab inferensi tipe tuple/array path jatuh ke status *unsound* (`any` atau widening ke primitive `string`) saat mengurai string dot-notation generik.
  2. Rancang modul tipe kondisional generik `Path<T>` dan `PathValue<T, P>` yang tahan banting (mampu memvalidasi nested path string literal dan mengekstrak return type yang 100% presisi untuk struktur objek arbitrer, termasuk array indexing).

---

### Skenario C: Regresi Type Soundness pada Plugin Middleware Pipeline
Tim infrastruktur platform merancang plugin pipeline terdistribusi:

```typescript
type Middleware<TInput, TOutput> = (context: TInput) => Promise<TOutput>;

class Pipeline<TContext> {
  use<TNextContext>(
    fn: Middleware<TContext, TNextContext>
  ): Pipeline<TNextContext> {
    // runtime append middleware
    return this as any;
  }
}
```
Seorang insinyur melaporkan bug kritis di produksi: Middleware yang dirancang untuk menerima `{ auth: AuthContext }` dapat dipasangkan secara valid oleh compiler setelah middleware yang mengembalikan `{ user: string }` tanpa field `auth`, tetapi program gagal runtime dengan `TypeError: Cannot read properties of undefined (reading 'token')`.
* **Pertanyaan Diagnostik:**
  1. Mengapa generic tracking state di atas gagal menegakkan rantai dependensi konteks (context accumulation vs context replacement)?
  2. Rekonstruksi class signature `Pipeline` menggunakan Parametric Polymorphism agar konteks runtime terakumulasi secara bertahap (`TContext & TNextContext`), memvalidasi bahwa input tiap middleware kompatibel dengan state akumulatif sebelumnya, serta mencegah hilangnya referensi properti wajib.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Type-Safe Deep Lens & Path Engine

#### Problem:
Pada framework state-management terdistribusi, pengaksesan dan mutasi state yang bersarang dalam (*deeply nested states*) membutuhkan runtime performan tinggi tanpa overhead deep-cloning global, namun tetap membutuhkan static typing 100% presisi untuk path akses dan payload pembaruan. 

#### Requirements:
Rancang dan implementasikan sekumpulan generic types dan satu generic functional wrapper (`createLens`) dengan kapabilitas:
1. **Type-Safe Path Generation**: Menghasilkan representasi union dari seluruh string literal path yang valid dari target object hingga kedalaman n-level (dot-notation), contoh: `"user.address.coordinates.lat"` atau `"orders[0].items.sku"`.
2. **Path Type Resolution**: Utility generic `ResolvePath<T, PathString>` yang secara akurat mengekstrak tipe kembalian dari path yang ditentukan, termasuk array element unpacking via `[number]`.
3. **Immutable Lens Mutator**: Fungsi lens `set` yang menerima target path, dan value yang tipenya **wajib terikat identik** dengan `ResolvePath<T, PathString>`. 
4. **Compile-time Depth Guard**: Mekanisme pembatas kedalaman parsing rekursif maksimum (misal: 6 tingkatan traversal) untuk melindungi compiler dari rekursi tanpa batas tanpa menggunakan runtime overhead.

#### Constraints:
* **Zero `any` / Zero `as unknown as T` pada public generic signature**: Seluruh inferensi tipe harus diturunkan secara organik melalui Parametric Polymorphism murni.
* **Compiler Performance**: Implementasi tidak boleh memicu error `TS2589` pada skenario evaluasi tipe nested model hingga 6 level kedalaman.
* **Compatibility**: Kompatibel penuh dengan flag compiler `--strict: true` dan `--noImplicitAny: true`.

#### Expected Output:
```typescript
interface AppState {
  system: {
    nodes: Array<{
      id: string;
      metrics: { cpu: number; active: boolean };
    }>;
  };
  config: { version: number; releaseName: string };
}

// 1. Instansiasi Lens Engine
const lens = createLens<AppState>();

// 2. Valid Cases (Compile & Autocomplete Sempurna)
const cpu = lens.get(state, "system.nodes[number].metrics.cpu"); // Resolves to: number
const updatedState = lens.set(
  state, 
  "system.nodes[number].metrics.active", 
  false // Hanya menerima tipe boolean!
);

// 3. Negative Compilation Checks (Wajib memicu Compile Error)
// @ts-expect-error Path invalid
lens.get(state, "system.nodes[number].metrics.invalidField"); 

// @ts-expect-error Type mismatch: active adalah boolean, bukan string
lens.set(state, "system.nodes[number].metrics.active", "INACTIVE"); 
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi operasional *Parametric Polymorphism* vs *Ad-hoc Polymorphism* vs *Subtyping Polymorphism*.
- [ ] Algoritma evaluasi compiler terhadap *Distributive Conditional Types* pada naked type parameters.
- [ ] Aturan sintaksis dan resolusi batas kandidat untuk deklarasi `infer` pada posisi kovarian vs kontravarian.
- [ ] Teorema *Variance* (Covariance, Contravariance, Invariance, Bivariance) dan pengaruh flag `--strictFunctionTypes` terhadap assignability generic closure.
- [ ] Dinamika interaksi tipe generic terhadap primitive sentinel types: `never`, `any`, `unknown`, dan `void`.
- [ ] Perbedaan instansiasi antara *Homomorphic Mapped Types* dan mapped types standar.
- [ ] Batasan komputasi sistem tipe TypeScript (instantiation depth limit, structural comparison threshold).

### Saya tidak perlu menghafal:
- [ ] Seluruh kode numerik error compiler TypeScript (misal: TS2589, TS2345, TS2322) selama memahami pesan diagnostiknya.
- [ ] Limit konstanta numerik hardcoded stack depth pada repositori TypeScript core (angka pastinya dapat berubah antar versi minor compiler).
- [ ] Pola ASCII parser reguler untuk dynamic string literal slicing di luar domain parsing generic type yang umum.

### Saya harus bisa melakukan:
- [ ] Menerapkan generic constraints kompleks (`<T extends Record<K, any>>`) tanpa menyebabkan narrowing loss atau premature type-widening.
- [ ] Mematikan distribusi union secara sadar menggunakan tuple encapsulation (`[T] extends [Constraint]`).
- [ ] Menggunakan utilitas `NoInfer<T>` untuk mengisolasi inferensi parameter generic pada context parameter sekunder.
- [ ] Merancang tipe generik rekursif berperforma tinggi menggunakan pola *Tuple Accumulator (TCO pattern)* untuk mencegah memory exhaustion compiler.
- [ ] Memvalidasi dan mengekstrak informasi skema tipe data bersarang arbitrer menggunakan template literal types yang digabungkan dengan recursive conditional `infer`.
- [ ] Memodifikasi tipe generic API framework agar terbebas dari kebocoran tipe `any` implisit pada tingkat batas layer domain aplikasi.