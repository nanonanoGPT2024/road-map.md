# BAB 01: Quiz, Challenge, & Knowledge Check
**Core Semantics & Execution Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Structural vs. Nominal Type System & Type Soundness
TypeScript mengadopsi sistem *structural typing* (berbasis pada relasi bentuk data atau *shape*), berbeda dengan bahasa seperti Java atau C# yang mengimplementasikan *nominal typing*.
* Jelaskan konsekuensi arsitektural dari *structural typing* terhadap prinsip *type soundness* dalam TypeScript!
* Mengapa tim perancang TypeScript secara sadar mengorbankan *100% mathematical type soundness* demi kompatibilitas terhadap idiom JavaScript modern? Berikan satu contoh konkret di mana kode lolos kompilasi tanpa peringatan (kompilator menganggap valid secara struktural) namun menghasilkan *runtime TypeError*.

### Soal 1.2: Type Erasure & The Emit Boundary
Kompromi mendasar dalam arsitektur eksekusi TypeScript adalah konsep *Type Erasure*.
* Uraikan secara presisi apa yang terjadi pada siklus hidup sintaksis TypeScript saat tahap kompilasi (*emit phase*) dieksekusi oleh `tsc`.
* Terdapat beberapa anomali historis di mana sintaks TypeScript menghasilkan *runtime code artifact* (bukan sekadar terhapus). Identifikasi dan bandingkan minimal dua fitur tersebut (misal: `enum`, `namespace`, atau *parameter properties*). Mengapa arsitektur sistem skala besar modern umumnya melarang penggunaan fitur-fitur tersebut melalui linter?

### Soal 1.3: Pipeline Kompilator: Dari Scanner hingga Emitter
Jelaskan alur pemrosesan internal `tsc` (TypeScript Compiler) melalui 5 komponen intinya:
1. `Scanner`
2. `Parser`
3. `Binder`
4. `Checker`
5. `Emitter`

Jelaskan fungsi struktural dari `Binder` dalam membentuk `Symbol Table`, dan mengapa tahap `Checker` merupakan tahapan yang paling memakan konsumsi CPU serta memori terbesar dalam proses kompilasi monorepo berskala besar.

### Soal 1.4: Freshness & Excess Property Checks
Perhatikan fenomena perilaku kompilator berikut:
```typescript
interface RequestConfig {
  url: string;
  timeout?: number;
}

function sendRequest(config: RequestConfig) { /* ... */ }

// Case A: Langsung inline object literal
sendRequest({ url: "/api/v1", timeout: 5000, extraParam: true }); // Error!

// Case B: Melalui intermediate variable
const payload = { url: "/api/v1", timeout: 5000, extraParam: true };
sendRequest(payload); // Berhasil tanpa error!
```
* Mengapa Case A memicu kesalahan kompilasi (*Excess Property Check*), sedangkan Case B diizinkan oleh sistem tipe TypeScript?
* Jelaskan konsep formal *freshness* pada *object literal types* dan motivasi ergonomis di balik aturan semantik ini!

### Soal 1.5: Teori Himpunan Sistem Tipe: `any` vs `unknown` vs `never`
Sistem tipe TypeScript dapat dipetakan secara matematis menggunakan Teori Himpunan (*Set Theory*):
* Analisis semantik `unknown` sebagai *Top Type* ($\top$) dan `never` sebagai *Bottom Type* ($\bot$).
* Mengapa tipe `any` dianggap merusak kaidah teori himpunan (*set-theoretic soundness*), dan bagaimana perilakunya melanggar hukum transitivitas tipe dalam subtyping?
* Jelaskan bagaimana tipe `never` dimanfaatkan oleh kompilator untuk melakukan *exhaustiveness checking* pada konstruksi *pattern matching* / *discriminated unions*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Transpilation Boundary & Isolated Modules
Banyak *build tool modern* (esbuild, SWC, Vite, Babel) mengabaikan kapabilitas *type-checking* `tsc` dan hanya menjalankan *strip-only transpilation* per file secara paralel:
* Apa tujuan flag `isolatedModules: true` di `tsconfig.json`?
* Analisis mengapa kode berikut gagal diproses oleh *transpiler* file-tunggal jika `isolatedModules` diaktifkan, dan bagaimana solusi refaktorisasi semantik yang tepat:
```typescript
// types.ts
export interface UserDTO {
  id: string;
  name: string;
}

// index.ts
export { UserDTO } from './types';
const enum TargetEnvironment {
  Production = "PROD",
  Staging = "STG"
}
```

### Soal 2.2: Variance Subtyping: Bivariance, Covariance, & Contravariance
Secara default, parameter metode (*method declaration*) pada antarmuka berperilaku *bivariant*, sedangkan sintaks properti fungsi (*function property*) tunduk pada aturan `strictFunctionTypes`:
```typescript
class Animal { name!: string; }
class Dog extends Animal { bark() {} }

// Method syntax vs Property syntax
interface MethodComparer {
  compare(a: Animal): boolean;
}

interface PropertyComparer {
  compare: (a: Animal) => boolean;
}
```
* Jelaskan perbedaan aturan variansi (*covariance* vs *contravariance*) yang diterapkan kompilator pada kedua interface di atas ketika diberikan assignable subtype (misal: implementasi yang menerima `Dog`).
* Mengapa TypeScript secara default membiarkan parameter metode bersifat *bivariant*? Konteks runtime JavaScript apa yang diakomodasi oleh desain ini (misalnya mutasi array)?

### Soal 2.3: Modul Resolusi & Node.js Dual-Package Hazard
Dalam TypeScript versi modern (`moduleResolution: "node16"` / `"nodenext"` / `"bundler"`):
* Mengapa kita diwajibkan menuliskan ekstensi file `.js` pada pernyataan impor lokal (misal: `import { helper } from "./helper.js";`), meskipun file sumber di disk adalah `helper.ts`?
* Apa yang dimaksud dengan fenomena *Dual-Package Hazard* dalam kompilasi hibrida CJS/ESM, dan bagaimana field `exports` serta `typesVersions` dalam `package.json` berinteraksi dengan resolusi kompilator TypeScript?

### Soal 2.4: Declaration Merging & Ambient Context Pollution
Perhatikan skenario manipulasi konteks global:
```typescript
// custom-types.d.ts
declare global {
  interface Window {
    analyticsToken: string;
  }
}

declare module 'express-serve-static-core' {
  interface Request {
    traceId: string;
  }
}
```
* Bagaimana *Binder* TypeScript memproses *declaration merging* pada interface yang sama di scope berbeda?
* Identifikasi potensi bahaya dari *ambient context pollution* dalam monorepo skala besar. Bagaimana sebuah deklarasi ambient tanpa `import`/`export` eksplisit dapat membocorkan (*leak*) definisi tipe ke seluruh workspace tanpa disengaja?

### Soal 2.5: Recursive Type Resolution & Stack Exhaustion
Kompilator TypeScript memiliki limitasi internal untuk mencegah infinite loop saat mengevaluasi *generic conditional types*.
```typescript
type DeepFlatten<T> = T extends any[] ? DeepFlatten<T[number]> : T;
type Problematic = DeepFlatten<any>;
```
* Jelaskan bagaimana kompilator mendeteksi *tail-call recursion* pada tipe, dan apa faktor yang memicu eror: `Type instantiation is excessively deep and possibly infinite. (TS2589)`!
* Strategi arsitektur tipe apa yang dapat diterapkan untuk merancang *depth-limiter* atau *tail recursion elimination (TRE)* buatan menggunakan tuple *accumulator* dalam Type System?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Degradasi Eksponensial CI Pipeline Monorepo (Performance & Bottleneck)
**Konteks Insiden:**
Sebuah perusahaan fintech memiliki monorepo berukuran 70 paket (`pnpm workspace`). Tim DevOps melaporkan bahwa waktu eksekusi langkah CI `tsc --noEmit` meningkat secara drastis dari **3 menit menjadi 38 menit**, yang sering berujung pada *heap out-of-memory* (`JavaScript heap out of memory - TS7017 / V8 crash`) saat memverifikasi keseluruhan sistem.

Investigasi awal menunjukkan bahwa beberapa tim baru saja mengintegrasikan *library schema validation* berbasis inferensi otomatis yang rumit (`type-fest`, dynamic JSON schema parser, dan nested Prisma/Trpc type generations).

**Pertanyaan Diagnostik & Solusi:**
1. Pendekatan metrik apa yang harus Anda ambil untuk mengisolasi file dan tipe yang menjadi bottleneck kompilator? Perintah *flag diagnostic* apa yang disediakan oleh `tsc` untuk menganalisis waktu instansiasi tipe, representasi AST, dan trace visual kompilator?
2. Bagaimana Anda merestrukturisasi monorepo tersebut menggunakan fitur kompilator TypeScript: *Project References* (`tsconfig.json` -> `"composite": true`, `"references": [...]`), *Incremental Build* (`.tsbuildinfo`), dan skema eksekusi terdistribusi agar pemeriksaan tipe tidak lagi memproses seluruh AST dari nol pada setiap pipeline run?

---

### Skenario B: Runtime Crash Pasca-Deploy & "The Illusion of Soundness" (Data Integrity)
**Konteks Insiden:**
Layanan transfer perbankan mengalami *runtime fatal error* (HTTP 500) yang meluas di produksi, namun tes unit TypeScript dan kompilasi CI 100% berstatus *green*. Kode sumber yang mengalami kegagalan adalah sebagai berikut:

```typescript
interface PaymentPayload {
  transactionId: string;
  amount: number;
  metadata: {
    origin: string;
    targetAccount: string;
  };
}

export async function processPayment(rawBody: string) {
  const data = JSON.parse(rawBody) as PaymentPayload;
  
  // Runtime Error terjadi di sini: Cannot read properties of undefined (reading 'targetAccount')
  console.log(`Processing payout to: ${data.metadata.targetAccount.toUpperCase()}`);
  
  await executeDatabaseTx(data.transactionId, data.amount, data.metadata.targetAccount);
}
```
Payload yang dikirimkan oleh sistem gateway payment eksternal ternyata mengalami perubahan kontrak API mendadak: properti `metadata` bernilai `null`.

**Pertanyaan Diagnostik & Solusi:**
1. Bedah kelemahan semantik tipe pada fungsi di atas. Mengapa penggunaan *type assertion* (`as PaymentPayload`) memberikan *false confidence* kepada engineer, dan mengapa pengembalian `any` oleh `JSON.parse` menjadi akar kerentanan ini?
2. Redesain seluruh lapisan ingestion data fungsi tersebut dengan menerapkan arsitektur *"Parse, Don't Validate"*. Gunakan pendekatan *type narrowing*, *type guards* kustom, atau *runtime boundary validation* (misal: schema validator pattern), dan tunjukkan bagaimana tipe TypeScript dapat disinkronkan secara otomatis tanpa duplikasi manual deklarasi interface.

---

### Skenario C: Migrasi Arsitektur Build Pipeline: tsc vs. Isolated Transpilation
**Konteks Insiden:**
Sebagai Technical Curriculum Architect / Principal Engineer, Anda diminta untuk memotong *feedback loop* developer lokal yang saat ini mengeluhkan waktu kompilasi *hot reload* lambat (menggunakan `ts-node` atau `tsc-watch`). Manajemen mengusulkan migrasi total ke `SWC` atau `esbuild` untuk transpilasi runtime produksi dan development, serta menghapus seluruh penggunaan `tsc` dari lifecycle build lokal.

Namun, sistem Anda memanfaatkan dependensi berbasis *inversion-of-control* (IoC) berskala besar (seperti NestJS / InversifyJS) yang mengandalkan fungsionalitas `emitDecoratorMetadata` dan `experimentalDecorators`.

**Pertanyaan Diagnostik & Solusi:**
1. Analisis risiko arsitektural dari usulan penghapusan `tsc` tersebut! Mengapa transpiler seperti `esbuild` tidak dapat sepenuhnya mereplikasi semantik `emitDecoratorMetadata` tanpa perlakuan khusus, dan apa dampak yang ditimbulkan terhadap *runtime dependency injection*?
2. Rancanglah arsitektur *dual-pipeline* yang ideal (memisahkan *transpilation path* dari *type verification path*). Jelaskan trade-off sistem ini, konfigurasi `tsconfig.json` yang harus diselaraskan, dan bagaimana developer lokal serta CI tetap terlindungi dari bug tanpa mengorbankan kecepatan build berkecepatan tinggi.

---

## 4. Chapter Challenge

### Tantangan Praktis: Zero-Runtime-Leak Type-Safe State Machine & Event Dispatcher

#### Problem Description
Di core platform enterprise, sering kali dibutuhkan sistem pemrosesan transaksi berbasis *finite-state machine* (FSM) yang aman. Pengembang junior kerap kali membiarkan payload event yang tidak valid lolos ke state yang salah karena manipulasi string atau *type casting* yang serampangan. 

Anda ditugaskan untuk mengimplementasikan sebuah sistem event dispatcher *in-memory* yang statically-guaranteed (kompilator akan menolak kompilasi jika transisi status atau payload tidak valid).

#### Requirements
1. **Definisi State & Transition Rules**:
   * State: `'IDLE' | 'PENDING' | 'AUTHENTICATED' | 'FAILED'`
   * Transisi yang valid:
     * `'IDLE'` $\to$ Event `'START'` $\to$ Berubah ke `'PENDING'` (Payload: `{ initiatedBy: string }`)
     * `'PENDING'` $\to$ Event `'VERIFY'` $\to$ Berubah ke `'AUTHENTICATED'` (Payload: `{ token: string; expiresAt: number }`)
     * `'PENDING'` $\to$ Event `'REJECT'` $\to$ Berubah ke `'FAILED'` (Payload: `{ reason: string; code: number }`)
     * `'FAILED'` $\to$ Event `'RESET'` $\to$ Berubah ke `'IDLE'` (Payload: `void` atau `undefined`)
     * State `'AUTHENTICATED'` adalah *terminal state* (tidak ada transisi lanjutan).

2. **Core Engine Implementation**:
   Implementasikan class/objek `FSMDriver<CurrentState>`:
   * Constructor harus mengunci initial state.
   * Method `dispatch(event, payload)`:
     * Harus **hanya menerima** nama event yang legal untuk `CurrentState`.
     * Harus **mengharuskan** struktur payload yang presisi sesuai event tersebut.
     * Mengembalikan instance `FSMDriver` baru dengan type parameter yang mencerminkan state berikutnya (*fluent immutable state transition*).
   * Method `getState()`: Mengembalikan state saat ini sebagai literal type (bukan `string`).

3. **Exhaustive State Handler**:
   * Buat generic function `handleTerminalState(driver: FSMDriver<any>)` yang mengimplementasikan *exhaustiveness checking* menggunakan tipe `never`. Fungsi ini harus memastikan bahwa seluruh state yang mungkin ditangani dengan penanganan eksplisit tanpa ada state yang terlewat.

#### Constraints
* **Strict Type Safety**: Dilarang keras menggunakan tipe `any`, assertion `as unknown as ...`, `@ts-ignore`, atau `@ts-expect-error` dalam kode solusi.
* **Strict tsconfig options**: Harus lolos validasi dengan flag:
  `"strict": true`, `"noImplicitAny": true`, `"exactOptionalPropertyTypes": true`.
* **Zero Runtime Overhead Typing**: Seluruh validasi transisi antar-state harus diselesaikan pada saat *compile-time*.

#### Expected Output
Kode yang dibuat harus memastikan skenario valid berjalan lancar, dan skenario tidak valid **secara instan** ditandai merah (*compile error*) oleh IDE/kompilator:

```typescript
// VALID SCENARIO:
const fsm = FSMDriver.create() // Type: FSMDriver<'IDLE'>
  .dispatch('START', { initiatedBy: 'admin' }) // Type: FSMDriver<'PENDING'>
  .dispatch('VERIFY', { token: 'xyz123', expiresAt: Date.now() + 3600 }); // Type: FSMDriver<'AUTHENTICATED'>

// INVALID SCENARIO (Harus compile-time error!):
const invalidFsm = FSMDriver.create()
  .dispatch('VERIFY', { token: 'xyz' }); // TS Error: Argument of type '"VERIFY"' is not assignable to parameter of type '"START"'

const invalidPayload = FSMDriver.create()
  .dispatch('START', { initiatedBy: 123 }); // TS Error: Type 'number' is not assignable to type 'string'
```

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk memverifikasi kesiapan arsitektural Anda sebelum melangkah ke bab berikutnya.

### Saya harus memahami:
- [ ] Batasan formal antara kompilasi (*compile-time*) TypeScript dan eksekusi (*runtime*) JavaScript engine (V8/SpiderMonkey).
- [ ] Dampak arsitektural dari *Type Erasure*: mengapa tipe, antarmuka, dan tipe kondisional tidak memakan alokasi memori runtime.
- [ ] Tahapan pipeline `tsc`: Peran *Scanner*, *Parser*, pengisian *Symbol Table* oleh *Binder*, verifikasi tipe oleh *Checker*, hingga produksi JS oleh *Emitter*.
- [ ] Mengapa *Structural Subtyping* TypeScript tidak sepenuhnya *sound* dan perbedaannya dengan sistem tipe *Nominal*.
- [ ] Cara kerja *Freshness* (Excess Property Checking) dan batas perilakunya pada assignment variabel.
- [ ] Semantik matematis hierarki tipe: Hubungan antara `any`, `unknown`, `never`, dan `void`.
- [ ] Implikasi isolasi file (`isolatedModules: true`) terhadap fitur-fitur legasi seperti `const enum` dan `namespace`.
- [ ] Mekanisme subtyping pada fungsi: *Covariance* pada *return type* dan *Contravariance* pada *parameter type*.

### Saya tidak perlu menghafal:
- [ ] Urutan spesifik numerik *enum opcode error code* TypeScript (misal: kode numerik TS2322, TS2589, TS7017).
- [ ] Seluruh flag CLI kompilator `tsc` yang usang/deprecated.
- [ ] Algoritma internal tokenisasi karakter byte-per-byte pada *Scanner*.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi `tsconfig.json` berstandar *strict enterprise* dengan modularitas modern (`NodeNext`/`Bundler`).
- [ ] Menginvestigasi dan mendiagnosis bottleneck kompilasi monorepo dengan memanfaatkan flag `--extendedDiagnostics` dan `--generateTrace`.
- [ ] Merancang kontrak batas runtime (*runtime boundary validation*) yang aman tanpa membiarkan casting `as Type` merusak keabsahan tipe.
- [ ] Memisahkan proses transpilasi kode berkecepatan tinggi (*fast-strip transpilers*) dari proses verifikasi kebenaran tipe (*strict type-checking*).
- [ ] Membangun generic typing tingkat lanjut dengan jaminan *exhaustiveness checking* memanfaatkan tipe `never`.