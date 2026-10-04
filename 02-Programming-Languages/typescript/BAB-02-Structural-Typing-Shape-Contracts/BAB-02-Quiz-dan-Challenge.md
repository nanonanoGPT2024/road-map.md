# BAB 02: Quiz, Challenge, & Knowledge Check
**Structural Typing & Shape Contracts**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Nominal Typing vs. Structural Subtyping
Jelaskan secara fundamental perbedaan antara *nominal typing system* (seperti pada Java/C#) dan *structural typing system* (TypeScript) dalam konteks penentuan kompatibilitas tipe. Bagaimana TypeScript Compiler (`tsc`) menentukan bahwa tipe $T_A$ adalah *subtype* dari $T_B$, dan apa implikasi filosofis desain ini terhadap interoperabilitas kode JavaScript yang dinamis?

### Soal 1.2: Mekanisme Excess Property Checking (EPC)
Perhatikan cuplikan kode berikut:
```typescript
interface Point2D {
  x: number;
  y: number;
}

function renderPoint(p: Point2D) { /* ... */ }

// Case A:
renderPoint({ x: 10, y: 20, z: 30 }); // Error: Object literal may only specify known properties...

// Case B:
const rawPoint = { x: 10, y: 20, z: 30 };
renderPoint(rawPoint); // OK (Lolos type check)
```
Mengapa *Excess Property Checking* (EPC) dipicu secara ketat pada *Case A*, namun dilewati (*bypassed*) secara terprediksi pada *Case B*? Jelaskan konsep internal *freshness* pada *object literal* dan motivasi arsitektural tim TypeScript di balik perilaku ini.

### Soal 1.3: Prinsip Substitusi Liskov (LSP) pada Lebar Bentuk (*Width Subtyping*)
Dalam teori *type system*, TypeScript menerapkan *width subtyping* dan *depth subtyping*. Jelaskan bagaimana prinsip *Liskov Substitution Principle* (LSP) diaplikasikan ketika sebuah objek yang memiliki properti berlebih dianggap kompatibel dengan fungsi yang membutuhkan properti lebih sedikit. Apa konsekuensi logisnya terhadap operasi seperti `Object.keys()` atau iterasi runtime terhadap objek tersebut?

### Soal 1.4: Perilaku Varian pada Properti Objek vs. Method
Bandingkan dua deklarasi *contract* berikut dalam mode `strictFunctionTypes: true`:
```typescript
interface ContractA {
  process: (input: string | number) => void;
}

interface ContractB {
  process(input: string | number): void;
}
```
Mengapa TypeScript memperlakukan metode shorthand (*method syntax* pada `ContractB`) secara *bivariant*, sedangkan properti bertipe fungsi (*property syntax* pada `ContractA`) dievaluasi secara *contravariant* terhadap tipe parameternya? Apa trade-off historis dan teknis di balik keputusan ini?

### Soal 1.5: Dekonstruksi `{}` vs. `object` vs. `Record<string, unknown>`
Bongkar perbedaan semantik dan batasan resolusi tipe antara:
1. Tipe *empty object literal* `{}`
2. Tipe non-primitive `object`
3. Tipe dynamic key `Record<string, unknown>`

Jelaskan nilai runtime apa saja (termasuk nilai primitif) yang dapat di-assign ke masing-masing tipe tersebut, serta mengapa `{}` sering disalahpahami sebagai representasi "objek kosong tanpa properti".

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Lifecycle dan "Rotting" dari Object Literal Freshness
Dalam compiler TypeScript (`checker.ts`), sebuah objek literal menerima *flag* `FreshLiteralType`. Kapan tepatnya status *freshness* tersebut dihilangkan (*decayed/rotted*)? Berikan skenario pembuktian di mana modifikasi pada *variable assignment* atau *type widening* membatalkan perlindungan *excess property check*, dan analisis celah *type safety* yang terbuka akibat hal tersebut.

### Soal 2.2: Keruntuhan Type Narrowing akibat Index Signatures
Diberikan sebuah skema shape berikut:
```typescript
interface FlexibleConfig {
  env: 'production' | 'staging' | 'development';
  [key: string]: unknown;
}

function configure(config: FlexibleConfig) {
  if (config.env === 'production') {
    // Audit type di sini
  }
}
```
Ketika developer mencoba mengakses properti dinamis (misal: `config['custom']`), bagaimana interaksi antara *known keys* dan *index signature* mempengaruhi efektivitas exhaustiveness checking dan autocompletion? Mengapa penambahan `[key: string]: unknown` secara inheren melemahkan determinisme analisis statis TypeScript?

### Soal 2.3: Phantom Generic Type Fallacy
Perhatikan kode berikut:
```typescript
class EntityId<T> {
  constructor(private value: string) {}
  getValue(): string { return this.value; }
}

type UserId = EntityId<'User'>;
type OrderId = EntityId<'Order'>;

let uId: UserId = new EntityId<'User'>('usr_123');
let oId: OrderId = new EntityId<'Order'>('ord_999');

uId = oId; // Mengapa operasi assignment ini BERHASIL tanpa error kompilasi?
```
Mengapa TypeScript mengizinkan assignment tersebut meskipun tipe parameternya eksplisit berbeda? Jelaskan interaksi antara structural typing dengan tipe generik yang tidak digunakan (*phantom types*), dan bagaimana compiler mengoptimalkan perbandingan tipe struktur ini.

### Soal 2.4: Soundness Hole: Mutabilitas dan Kovarian Array
Buktikan mengapa sistem tipe TypeScript dianggap *unsound* (tidak menjamin kebenaran runtime secara mutlak) terkait hubungan antara structural subtyping dan penanganan array/objek yang dapat dimutasi (*mutable*). Rancang sebuah contoh kode minimal yang lolos kompilasi TypeScript secara legal (tanpa `any`, tanpa type assertion `as`), tetapi memicu `TypeError: undefined is not a function` atau runtime corruption secara deterministik saat dijalankan.

### Soal 2.5: Debugging Shape Compatibility Resolution
Diberikan error kompilasi berikut dari build pipeline produksi:
```text
Type 'ResponseDTO<T>' is not assignable to type 'ValidatedDTO<T>'.
  Types of property 'headers' are incompatible.
    Type 'ReadonlyMap<string, string[]>' is not assignable to type 'Map<string, string[]>'.
      The types returned by 'entries()' are incompatible between these types.
        Type 'IterableIterator<[string, string[]]>' is not assignable to type 'IterableIterator<[string, string[]]>'.
          Property 'map' is missing in type 'IterableIterator<...>' but required in type 'IterableIterator<...>'.
```
Berdasarkan pembacaan structural trace compiler:
1. Apa akar permasalahan struktural antara `ReadonlyMap` dan `Map` pada rantai properti di atas?
2. Mengapa error menunjukkan ketiadaan method `map` pada sebuah `IterableIterator`?
3. Langkah struktural murni apa (tanpa casting sembrono) yang harus diambil untuk menyelesaikan inkompatibilitas ini?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Kebocoran PII pada API Gateway (Mass-Assignment Vulnerability)
Sebuah arsitektur microservices berbasis Node.js/TypeScript menggunakan layer DTO (Data Transfer Object) untuk memvalidasi dan memetakan entity dari ORM sebelum dikirim ke client melalui HTTP REST API.

```typescript
// Domain Entity dari Database
interface UserEntity {
  id: string;
  name: string;
  email: string;
  passwordHash: string;
  twoFactorSecret: string;
  role: 'admin' | 'user';
}

// Target Contract untuk HTTP Response
interface PublicUserDTO {
  id: string;
  name: string;
  email: string;
}

// Controller
class UserController {
  async getUser(id: string): Promise<PublicUserDTO> {
    const user: UserEntity = await db.users.findById(id);
    
    // Developer A menulis:
    return user; // TypeScript mengizinkan ini secara struktural!
  }
}
```

*   **Insiden:** Pada saat endpoint `GET /users/:id` dipanggil, payload JSON runtime yang diterima oleh browser mengandung seluruh properti: `passwordHash` dan `twoFactorSecret` terekspos secara transparan dalam payload HTTP.
*   **Pertanyaan Diagnostik:**
    1. Dari kacamata *Structural Subtyping*, mengapa TypeScript menganggap tipe `UserEntity` sepenuhnya kompatibel (*assignable*) ke tipe `PublicUserDTO` tanpa menghasilkan error saat compile-time?
    2. Mengapa compiler tidak menerapkan *Excess Property Checking* pada baris `return user;`?
    3. Rancang sebuah arsitektur tipe (*type-level defensive pattern*) atau abstraksi mapper yang secara matematis memblokir passing objek yang memiliki field berlebih (*excess properties*), sehingga jika developer mencoba mengembalikan `UserEntity` secara langsung, kompilasi akan **wajib gagal**.

---

### Skenario B: Race Condition dan State Mutation pada Financial Ledger
Sistem pemrosesan transaksi *high-frequency trading* memodelkan transaksi moneter menggunakan antarmuka kontraktual:

```typescript
interface LedgerEntry {
  transactionId: string;
  amount: number;
  currency: string;
  metadata: {
    origin: string;
    isSettled: boolean;
  };
}
```

Dua service worker memproses objek yang sama secara paralel:
1. Service A mengharapkan mutasi lokal dengan mengubah `metadata.isSettled = true`.
2. Service B menerapkan structural subtyping untuk memetakan objek ke `AuditLog`:
```typescript
interface AuditLog {
  transactionId: string;
  metadata: {
    readonly origin: string;
    readonly isSettled: boolean;
  };
}

function processAudit(entry: AuditLog) {
  // Developer Service B berasumsi metadata freeze/immutable karena modifier readonly
  if (entry.metadata.isSettled) {
    // Jalankan settlement audit logic
  }
}
```

*   **Masalah:** Objek ditransfer melalui referensi memori lokal. Karena modifier `readonly` di TypeScript bersifat shallow dan *compile-time only*, Service A memutasi `metadata.isSettled` di tengah eksekusi Service B, menyebabkan inkonsistensi kalkulasi rekonsiliasi bernilai miliaran rupiah.
*   **Pertanyaan Diagnostik:**
    1. Mengapa tipe dengan mutable property (`LedgerEntry`) secara struktural kompatibel dan dapat di-assign ke tipe dengan `readonly` property (`AuditLog`), padahal semantik mutabilitasnya bertolak belakang?
    2. Analisis implikasi kegagalan structural subtyping ini terhadap prinsip *referential transparency*.
    3. Rancang solusi arsitektur menggunakan teknik *Deep Immutable Deep-Readonly* dan *Nominal/Branded Typing* agar objek `LedgerEntry` tidak dapat di-pass begitu saja ke consumer tanpa proses kloning struktural yang tervalidasi secara eksplisit.

---

### Skenario C: Regresi Skalabilitas Build Monorepo (Type-Checker OOM Bottleneck)
Sebuah tim enterprise memigrasikan repositori mereka ke arsitektur monorepo dengan ratusan micro-frontend dan ribuan schema validation contracts. Tiba-tiba waktu kompilasi CI/CD melonjak dari 45 detik menjadi 22 menit, hingga akhirnya `tsc` crash dengan error: `JavaScript heap out of memory`.

Setelah dilakukan investigasi menggunakan tracing flag (`tsc --extendedDiagnostics --generateTrace traceDir`), ditemukan bahwa *type-checking phase* menghabiskan 95% waktu di fungsi `checkTypeRelatedTo` pada file `checker.ts`.

Penyebabnya adalah relasi antara model data antarmuka yang sangat kompleks:
```typescript
interface BaseDocumentNode {
  id: string;
  parent?: BaseDocumentNode;
  children?: BaseDocumentNode[];
  attributes: Record<string, any>;
  permissions: {
    roles: string[];
    inheritance: BaseDocumentNode;
  };
}
```
Setiap kali komponen UI mendefinisikan *custom node*, mereka meng-extend interface ini dan menambahkan 15-30 properti baru dengan struktur rekursif.

*   **Pertanyaan Diagnostik:**
    1. Bagaimana algoritma perbandingan struktural TypeScript mengevaluasi kompatibilitas tipe pada struktur data rekursif yang dalam (*deeply nested recursive shapes*), dan mengapa kompleksitas komputasinya dapat meledak secara eksponensial?
    2. Apa peran cache internal TypeScript (`relationCache`) dalam mendeteksi siklus rekursi, dan mengapa penggunaan tipe `Record<string, any>` atau dynamic union keys dapat merusak kemampuan compiler untuk melakukan *cache-hit* perbandingan struktur tersebut?
    3. Ajukan 3 modifikasi arsitektural konkret pada level perancangan *shape contract* untuk memutus rantai pengecekan rekursif tanpa mengorbankan integritas *type safety* sistem.

---

## 4. Chapter Challenge

### Tantangan Praktis: Zero-Leak Data Boundary Engine & Nominal Tagging System

#### Deskripsi Problem
Dalam sistem perbankan terdistribusi, penggunaan *structural typing* murni telah menyebabkan insiden keamanan:
1. `UserId` (string) dan `AccountId` (string) sering tertukar di argument fungsi tanpa peringatan compiler.
2. Objek raw database model sering bocor ke HTTP Layer karena *width subtyping* meloloskan properti internal yang sensitif.
3. Objek payload yang dimutasi secara eksternal merusak state internal engine karena type system meloloskan mutable contract ke immutable contract.

Anda ditugaskan merancang sebuah framework tipe data inti (*core boundary type engine*) yang memaksa implementasi **Nominal Typing secara Struktural**, **Strict Excess Property Rejection** pada fungsi generic, dan **Enforced Deep Immutability**.

#### Requirements:
1. **Nominal Branding Utility (`Brand<T, B>`):**
   * Buat tipe utilitas zero-overhead `Brand<K, T>` yang mengubah primitive types (misal `string`, `number`) menjadi nominal types yang tidak saling kompatibel secara struktural.
   * Harus menyediakan konstruktor tipe aman (*type assertion guard*) untuk instansiasi tipe branded tersebut.
2. **Strict Shape Enforcer (`StrictShape<TExpected, TActual>`):**
   * Bangun generic constraint tipe fungsi bernama `enforceExactShape<Expected>()(actual)` yang mengevaluasi parameter. Jika `actual` memiliki satu pun properti tambahan yang tidak dideklarasikan pada `Expected`, compiler harus menolak kompilasi dan memberikan pesan error kustom (bukan sekadar silent subtyping bypass via variable reference).
3. **Deep Freeze Boundary Contract (`ImmutableContract<T>`):**
   * Rancang utility type yang secara rekursif mengonversi seluruh properti, nested object, nested array, dan nested map menjadi `readonly`, sekaligus menghilangkan metode-metode mutasi native (seperti `.push()`, `.set()`, `.splice()`).

#### Constraints:
* Dilarang keras menggunakan tipe `any`.
* Tidak boleh menggunakan `as unknown as Type` di luar implementasi fungsi constructor/guard boundary.
* Kode harus lolos verifikasi compiler dengan konfigurasi:
  ```json
  {
    "compilerOptions": {
      "strict": true,
      "noUncheckedIndexedAccess": true,
      "exactOptionalPropertyTypes": true
    }
  }
  ```
* Solusi harus murni type-level gymnastics dan wrapper fungsional minimal dengan runtime overhead $O(1)$ untuk branding dan $O(N)$ untuk mapping enforcement.

#### Expected Output
Implementasikan solusi lengkap dalam satu berkas TypeScript yang solid:
```typescript
// 1. Tipe Brand & Domain Identifier
export type Brand<K, T> = /* Implementasi Anda */;

export type UserId = Brand<string, 'UserId'>;
export type AccountId = Brand<string, 'AccountId'>;
export type MonetaryAmount = Brand<number, 'MonetaryAmount'>;

// Factory / Type Guard
export function makeUserId(id: string): UserId { /* ... */ }
export function makeAccountId(id: string): AccountId { /* ... */ }
export function makeMonetaryAmount(amount: number): MonetaryAmount { /* ... */ }

// 2. Strict Shape Boundary Mapper
export type ValidateExactShape<Expected, Actual> = /* Implementasi Anda */;

export function createStrictMapper<Expected>() {
  return function <Actual>(
    input: ValidateExactShape<Expected, Actual>
  ): Expected {
    /* ... */
  };
}

// 3. Immutable Contract
export type ImmutableContract<T> = /* Implementasi Anda */;

// Test Harness / Verification Scenario
// Verifikasi bahwa compiler MENERIMA kasus valid dan MENOLAK kasus invalid di bawah ini:

// a. Brand safety test
const user = makeUserId('usr_100');
const account = makeAccountId('acc_200');
// user = account; // HARUS ERROR

// b. Strict shape test
interface UserResponse {
  id: UserId;
  username: string;
}

const mapper = createStrictMapper<UserResponse>();

const rawDbObject = {
  id: user,
  username: 'alex_foster',
  passwordHash: '0x992384918239', // excess property!
};

// mapper(rawDbObject); // HARUS ERROR: Excess property 'passwordHash' rejected at compile-time!

const cleanObject = {
  id: user,
  username: 'alex_foster',
};
const safeData = mapper(cleanObject); // HARUS LOLOS KOMPILASI
```

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kematangan konseptual dan kesiapan arsitektural Anda sebelum melanjutkan ke bab berikutnya.

### Saya harus memahami:
- [ ] Mengapa TypeScript memilih *Structural Typing* (*duck typing*) alih-alih *Nominal Typing*, serta implikasinya terhadap arsitektur runtime JavaScript.
- [ ] Siklus hidup internal *Object Literal Freshness* dan kondisi pasti kapan *Excess Property Checking* (EPC) dieksekusi atau dilewati oleh compiler.
- [ ] Aturan perbandingan bentuk objek berdasarkan *Width Subtyping* (properti tambahan) dan *Depth Subtyping* (properti turunan/nested).
- [ ] Perbedaan semantik, representasi memori type-checker, dan assignability antara `{}`, `object`, `Object`, dan `Record<string, unknown>`.
- [ ] Mengapa method shorthand dideklarasikan secara bivariant dan bahaya runtime yang dapat ditimbulkan jika tidak menggunakan functional property syntax.
- [ ] Cara kerja *Index Signatures* dan dampaknya terhadap pelemahan kemampuan narrowing serta type inference.
- [ ] Teori varian: kapan TypeScript mengevaluasi suatu bentuk data secara *covariant*, *contravariant*, *invariant*, atau *bivariant*.
- [ ] Penyebab mendasar mengapa structural typing dapat menurunkan performa kompilasi monorepo secara drastis saat menangani *deeply nested recursive types*.

### Saya tidak perlu menghafal:
- [ ] Seluruh flag internal compiler yang terdapat di dalam file `checker.ts` (misal: nilai bitmask spesifik dari `TypeFlags` atau `ObjectFlags`).
- [ ] Daftar lengkap ribuan variasi pesan error kompilasi internal TypeScript terkait tipe inkompatibel.
- [ ] Urutan langkah evaluasi mikro pada AST traversal compiler untuk setiap node sintaksis.

### Saya harus bisa melakukan:
- [ ] Membangun dan mengimplementasikan arsitektur *Nominal Typing/Branded Types* murni berbasis type-level gymnastics untuk mencegah *shape collision* pada domain primitif yang kritis.
- [ ] Menulis generic type guard dan mapped type constraint yang mampu meniru perilaku *Exact Types* (menolak properti berlebih bahkan ketika objek dioper melalui referensi variabel).
- [ ] Mengidentifikasi dan memitigasi potensi *soundness hole* akibat mutasi properti pada objek yang di-pass ke consumer antarmuka `readonly`.
- [ ] Melakukan profiling dan debugging build pipeline TypeScript (`--extendedDiagnostics`, `--generateTrace`) untuk mendeteksi bottleneck perbandingan bentuk struktur rekursif yang lambat.
- [ ] Merancang kontrak DTO layer yang menjamin segregasi ketat antara internal persistence model (database entity) dan external delivery model (HTTP/gRPC contract) murni pada tingkat statis.