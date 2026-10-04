# BAB 10: Quiz, Challenge, & Knowledge Check
**Production Hardening & Runtime Validation**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Fenomena Type Erasure dan Ilusi Keamanan Boundary
Jelaskan secara mekanis apa yang terjadi pada *type annotations*, *interfaces*, dan *type aliases* saat TypeScript dikompilasi ke JavaScript (fase *emit*). Mengapa ketergantungan semata pada tipe statis TypeScript untuk memvalidasi data yang masuk melalui boundary I/O (seperti payload HTTP POST, respons RPC, atau pesan AMQP/Kafka) merupakan cacat arsitektur fatal (*architectural anti-pattern*)?

### Soal 1.2: Paradigma "Parse, Don't Validate"
Dalam konteks rekayasa perangkat lunak dengan TypeScript, bedakan secara filosofis dan teknis antara paradigma **Validasi** (mengembalikan boolean atau melempar error tanpa mengubah tipe) dan **Parsing** (mengonversi data tak terstruktur `unknown` menjadi representasi tipe data domain yang kuat). Bagaimana paradigma parsing memitigasi redundansi pemeriksaan tipe di layer internal aplikasi?

### Soal 1.3: Implikasi Compiler Flags terhadap Runtime Robustness
Analisis bagaimana flag konfigurasi compiler berikut mengubah semantik pengecekan kode dan mencegah kecacatan pada level runtime:
1. `noUncheckedIndexedAccess`
2. `exactOptionalPropertyTypes`
3. `useUnknownInCatchVariables`

Sertakan contoh kasus kegagalan eksekusi (*unhandled runtime exception*) yang dapat terjadi pada runtime Node.js/V8 jika ketiga flag di atas dibiarkan bernilai `false` (default behavior).

### Soal 1.4: Structural Subtyping vs Nominal Typing via Branded Types
TypeScript menggunakan sistem *structural subtyping*. Jelaskan skenario di mana sistem ini membahayakan integritas data domain—misalnya, ketidaksengajaan melewatkan `UnsanitizedUserInput` ke dalam fungsi database query yang membutuhkan `SanitizedSQLString`, atau tertukarnya `AccountId` dengan `TransactionId`. Bagaimana teknik **Branded/Flavored Types** (Nominal Typing) bekerja secara kompilasi untuk menutup celah ini tanpa overhead performa runtime?

### Soal 1.5: Mekanisme Excess Property Checks (EPC) dan Keterbatasannya
Kapan tepatnya TypeScript mengeksekusi *Excess Property Checks* (EPC)? Jelaskan mengapa kode berikut lolos kompilasi tanpa peringatan apa pun, dan apa implikasi keamanannya bila data tersebut langsung di-*persist* ke database dokumen (seperti MongoDB):

```typescript
interface UserProfileUpdate {
  displayName: string;
  bio?: string;
}

const payload = {
  displayName: "Alex",
  bio: "Software Engineer",
  role: "SUPERADMIN", // Injeksi atribut privilege escalation
};

function updateUser(data: UserProfileUpdate) {
  // Database update logic
}

updateUser(payload); // Lolos kompilasi tanpa error
```

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Bottleneck Type Instantiation pada Recursive Validation Schema
Ketika mendefinisikan skema validasi runtime hierarki pohon yang dalam (*deeply nested/recursive schema*) menggunakan library seperti Zod atau TypeBox, kompilator TypeScript (`tsc`) kerap mengalami lonjakan pemakaian memori drastis atau memunculkan error: `Type instantiation is excessively deep and possibly infinite. ts(2589)`. 
1. Bedah mekanisme internal kompilator TypeScript yang menyebabkan batasan rekursi ini terpicu.
2. Bagaimana strategi restrukturisasi tipe (*type-level refactoring*) atau penggunaan interface indirection untuk meredam kedalaman *evaluation stack* kompilator tersebut?

### Soal 2.2: JIT Validation Overhead vs AST-based Walking
Bandingkan arsitektur validasi berbasis **AST interpretation / dynamic walking** (contoh: Zod, Valibot) dengan arsitektur berbasis **JIT code generation / Ahead-of-Time compilation** (contoh: TypeBox via `@sinclair/typebox/compiler`, Ajv). 
Jelaskan dampak internalnya pada V8 engine dalam konteks *hidden classes*, *inline caching (IC)*, alokasi memori heap, dan latensi *garbage collection* (GC) saat menangani throughput 50.000 request/detik.

### Soal 2.3: Debugging Dekomposisi Prototype Pollution pada Unsafe Deserialization
Sebuah endpoint menerima payload JSON yang di-deserialize langsung via `JSON.parse` kemudian di-merge ke domain entity menggunakan utilitas deep merge naif:

```typescript
function naiveDeepMerge<T extends object, U extends object>(target: T, source: U): T & U {
  for (const key of Object.keys(source)) {
    const sourceValue = (source as any)[key];
    if (sourceValue && typeof sourceValue === "object" && !Array.isArray(sourceValue)) {
      if (!(target as any)[key]) (target as any)[key] = {};
      naiveDeepMerge((target as any)[key], sourceValue);
    } else {
      (target as any)[key] = sourceValue;
    }
  }
  return target as T & U;
}
```
Jelaskan bagaimana payload `{"__proto__": {"isAdmin": true}}` menembus batas keamanan tipe TypeScript. Rancang implementasi schema guard di layer parsing yang secara deterministik mengeliminasi risiko polusi `__proto__`, `constructor`, dan `prototype` sebelum masuk ke *engine* bisnis.

### Soal 2.4: Kerentanan Metadata Reflection vs Bundler Tree-Shaking
Banyak arsitektur enterprise menggunakan kombinasi `class-validator` dan `class-transformer` yang mengandalkan dekorator TypeScript dan `reflect-metadata`. 
Jelaskan dua kegagalan fatal arsitektur ini ketika dihadapkan pada stack build modern berbasis esbuild, SWC, atau Vite:
1. Masalah kompatibilitas implementasi spesifikasi proposal dekorator TC39 *Stage 3* vs legacy experimental decorators TypeScript.
2. Dampak flag `emitDecoratorMetadata: true` terhadap ukuran bundle dan kegagalan *tree-shaking* di lingkungan serverless/edge runtime.

### Soal 2.5: Zero-Cost Invariant Enforcement pada Mutasi Objek Internal
Pertimbangkan fungsi yang memproses transaksi perbankan dengan invariant bisnis yang ketat (misalnya: saldo tidak boleh negatif, transaksi berstatus `PENDING` hanya dapat berpindah ke `SETTLED` atau `FAILED`). 
Bagaimana Anda memanfaatkan kombinasi `Readonly<T>`, `as const`, discriminated union, dan helper assertion function (`asserts condition`) agar invariant runtime terjamin tanpa melakukan alokasi objek baru (*zero heap allocation overhead*)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Degradation Akibat Over-Validation pada API Gateway
* **Konteks:** Sebuah microservice API Gateway berbasis Node.js (Fastify) melayani ingress data telemetri IoT sebesar 45.000 req/sec. Tim backend menerapkan skema validasi runtime Zod yang sangat ketat pada setiap payload masuk. Payload rata-rata memiliki ukuran 2 KB dengan struktur nesting 4 level dan berbagai conditional logic (`z.discriminatedUnion`).
* **Insiden:** P99 latency melonjak dari 8ms menjadi 420ms. CPU usage instans container mencapai 100% saturasi, dan alokasi memori menunjukkan siklus *sawtooth* agresif akibat *Minor GC (Scavenge)* yang berjalan konstan.
* **Pertanyaan Diagnostik:**
  1. Identifikasi faktor struktural dalam runtime execution model Zod yang memicu pembentukan objek jangka pendek (*short-lived objects*) berlebih yang membebani V8 Garbage Collector pada load masif tersebut.
  2. Rancang strategi arsitektur remediasi untuk menurunkan latensi kembali ke < 15ms P99 tanpa mengorbankan keamanan validasi tipe data (pertimbangkan substitusi engine validasi, skema compilation, atau offloading).

---

### Skenario B: Financial Ledger Silent Corruption Akibat Type Coercion & Floating Point
* **Konteks:** Sistem core banking mencatat ledger mutasi dana. Payload API menerima transfer dana dalam format string numerik (misal: `"100.50"`). Developer mendefinisikan validator runtime yang menggunakan *automatic type coercion*:

```typescript
import { z } from "zod";

export const TransferRequestSchema = z.object({
  sourceAccountId: z.string().uuid(),
  targetAccountId: z.string().uuid(),
  amount: z.coerce.number().positive(),
});

export type TransferRequest = z.infer<typeof TransferRequestSchema>;
```
* **Insiden:** Setelah 3 bulan beroperasi, tim akuntansi menemukan selisih audit ledger sebesar ratusan ribu dolar. Ditemukan bahwa payload dengan nilai amount `"9007199254740993"` (melebihi `Number.MAX_SAFE_INTEGER`) dan payload pecahan presisi tinggi seperti `"0.1"` dan `"0.2"` terakumulasi dengan galat floating point IEEE-754. Lebih parah, input `"100,000"` diubah secara salah menjadi `100` karena perilaku parsing implisit dari fungsi JavaScript tertentu.
* **Pertanyaan Diagnostik:**
  1. Bedah mengapa penggunaan `z.coerce.number()` adalah anti-pattern kritis dalam komputasi finansial.
  2. Tuliskan ulang skema validasi dan arsitektur tipe domain menggunakan teknik *Branded Types* dan tipe arbitrary-precision (`bigint` atau library desimal seperti `Decimal.js`) sehingga payload tidak valid langsung ditolak pada runtime boundary, dan sistem kompilator menolak komputasi aritmatika primitif non-aman.

---

### Skenario C: Downstream Crash Akibat Upstream Schema Drift & Silent Erasure
* **Konteks:** Microservice A mengonsumsi stream Kafka dari Microservice B milik tim pihak ketiga. Kedua service berada di repository terpisah namun berbagi *contract interface* via paket internal npm `@company/contracts`. 
  Tim Microservice B memperbarui event schema dengan mengubah sebuah field dari `status: "ACTIVE" | "INACTIVE"` menjadi `status: "ACTIVE" | "INACTIVE" | "SUSPENDED"`, menaikkan versi minor paket npm, dan langsung men-deploy-nya ke staging/production.
* **Insiden:** Microservice A tidak melakukan update terhadap paket npm `@company/contracts`. Microservice A mengasumsikan tipe event adalah static via type casting:
  ```typescript
  const event = JSON.parse(message.value.toString()) as UserStatusChangedEvent;
  ```
  Ketika event bertipe `"SUSPENDED"` masuk, eksekusi jatuh ke blok exhaustive checking switch-case di Microservice A:
  ```typescript
  switch(event.status) {
    case "ACTIVE": processActive(event); break;
    case "INACTIVE": processInactive(event); break;
    default:
      const _exhaustiveCheck: never = event.status;
      throw new Error(`Unhandled status: ${_exhaustiveCheck}`);
  }
  ```
  Service A mengalami crash loop (OOM/Restart) akibat *unhandled exception*, memicu red-alert P1 incident.
* **Pertanyaan Diagnostik:**
  1. Jelaskan kesalahan fundamental pada postulat arsitektur integrasi di Microservice A. Mengapa type assertion `as T` pada boundary I/O secara efektif merusak prinsip *Fault Tolerance*?
  2. Rancang pola pertahanan *Zero-Trust Ingress Boundary* menggunakan pattern parsing yang mengisolasi downstream service dari *upstream schema drift*, termasuk penanganan schema versioning dan strategi *Dead Letter Queue (DLQ)*.

---

## 4. Chapter Challenge

### Tantangan Praktis: Membangun Production-Grade Zero-Trust Ingress Pipeline & Nominal Type Barrier

#### Problem Statement
Dalam arsitektur microservices berkinerja tinggi, data ingress dari dunia luar (HTTP request body/query) adalah titik paling rentan. Kebanyakan tim melakukan salah satu dari dua kesalahan fatal:
1. Mempercayai data tanpa parsing mendalam (*unsafe casting* `as Type`).
2. Melakukan validasi menggunakan library berat tanpa *sanitization* dan tanpa isolasi tipe nominal, membiarkan nilai primitif mentah yang lolos validasi disalahgunakan di layer domain (misal: plain string dilewatkan ke raw database driver).

Anda diminta membangun modul ingress pipeline inti (*Zero-Trust Ingress Pipeline*) yang menggabungkan:
* High-performance schema parsing.
* Strict nominal type branding.
* Protection terhadap prototype pollution dan excess properties.
* RFC 7807 compliant problem details error formatting.

#### Requirements
1. **Nominal Domain Types (Branded Types):**
   * Buat tipe branded absolut untuk:
     * `EmailAddress`: Harus lolos validasi format RFC 5322.
     * `PositiveCents`: Nominal type untuk uang berbasis integer (sen/rupiah integer terkecil), menolak bilangan desimal/floating point.
     * `SecureUUID`: UUID v4 tervalidasi.
   * Nilai primitif bertipe `string` atau `number` tidak boleh bisa di-*assign* secara langsung ke tipe branded ini tanpa melalui fungsi parser resmi.

2. **Ingress Pipeline Engine:**
   * Implementasikan fungsi generic `createIngressPipeline<TSchema, TOutput>(...)`.
   * Mendukung penolakan tegas terhadap *unknown / excess properties* (strip atau fail-fast, configurable).
   * Menjamin mitigasi prototype pollution: Jika payload mengandung properti `__proto__`, `constructor`, atau `prototype`, pipeline harus melempar security violation error seketika.
   * Harus *pure parsing*: Menerima input `unknown` dan menghasilkan output `Result<TOutput, RFC7807Error>`. Tidak boleh melempar unhandled exception (gunakan Result/Either pattern).

3. **Compiler Constraints:**
   * Kode wajib lolos kompilasi di bawah `tsconfig.json` paling ketat:
     ```json
     {
       "compilerOptions": {
         "strict": true,
         "noUncheckedIndexedAccess": true,
         "exactOptionalPropertyTypes": true,
         "noImplicitReturns": true,
         "noFallthroughCasesInSwitch": true
       }
     }
     ```
   * Dilarang keras menggunakan tipe `any` atau unsafe casting `as unknown as T` di luar boundary internal fungsi validator primitif.

#### Expected Output
Sediakan satu set implementasi TypeScript utuh yang modular, mencakup:
1. Brand helper type utility.
2. Result type monad (`Ok` / `Err`).
3. Core Validation Engine (boleh menggunakan Zod, TypeBox, atau vanilla custom parsing engine).
4. Concrete Ingress DTO Parser (misal: `CreateUserAccountRequest`).
5. Unit tests / Assertion assertions yang membuktikan bahwa:
   * Data valid berhasil terurai menjadi branded types.
   * Injeksi `__proto__` diblokir.
   * Nilai float pada field mata uang ditolak.
   * Pemanggilan fungsi domain yang membutuhkan branded types gagal dikompilasi jika diberikan string/number primitif mentah.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis sebelum meluncurkan kode TypeScript ke lingkungan produksi berisiko tinggi.

### Saya harus memahami:
- [ ] Batasan absolut sistem kompilasi TypeScript: bagaimana *type erasure* menghilangkan seluruh metadata tipe pada runtime.
- [ ] Perbedaan performa dan arsitektur antara AST traversal validation (Zod) dan Ahead-of-Time / JIT schema engines (TypeBox/Ajv).
- [ ] Dampak flag `noUncheckedIndexedAccess` terhadap penanganan array out-of-bounds dan Record dinamis.
- [ ] Mekanisme implementasi *Nominal Typing* via *Type Branding* atau *Type Flavoring* untuk menegakkan invariant domain.
- [ ] Bahaya runtime dari *Prototype Pollution* dan bagaimana deserialisasi naif dapat membobol integritas aplikasi Node.js.
- [ ] Keterbatasan struktural *Excess Property Checks (EPC)* dan skenario di mana EPC diabaikan oleh kompilator.
- [ ] Pola penanganan error fungsional (*Result/Either monad*) versus try-catch exceptions pada layer boundary parsing.

### Saya tidak perlu menghafal:
- [ ] Seluruh sintaks dan method chaining API spesifik dari setiap library validasi (misal: detail chaining regex Zod vs Joi).
- [ ] Bytecode output detail yang dihasilkan V8 untuk hidden classes dari schema parsers.
- [ ] Regex standar lengkap RFC 5322 untuk validasi email (gunakan library tervalidasi).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi `tsconfig.json` level enterprise yang dioptimalkan untuk pencegahan bug runtime (`strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`).
- [ ] Mengonstruksi pipeline parser data eksternal yang menerima input `unknown` dan mengembalikan typed object domain tanpa unsafe type casting (`as`).
- [ ] Melakukan benchmark profiling memori dan CPU (menggunakan clinic.js atau Node.js native profiler) untuk mendeteksi bottleneck validasi runtime.
- [ ] Mengimplementasikan defensive schema migration dan exhaustiveness checking untuk mencegah downstream service crash akibat breaking changes dari upstream.
- [ ] Mengisolasi domain logic inti dari framework dan library validasi eksternal menggunakan Dependency Inversion Principle dan boundary interfaces.