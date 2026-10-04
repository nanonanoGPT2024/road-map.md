# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Pemrograman Lanjutan & Arsitektur Perangkat Lunak Backend
*   **Kategori:** 02-Programming-Languages
*   **Topik Spesifik:** Production Hardening & Runtime Validation
*   **Kode Modul:** TS-PROD-1001
*   **Tingkat Kesulitan:** Advanced / Lanjutan
*   **Prasyarat Konseptual:** 
    *   Pemahaman mendalam sistem tipe TypeScript (Generics, Mapped Types, Conditional Types).
    *   Mekanisme inferensi tipe dan *type erasure* pada JavaScript engine (V8, JavaScriptCore).
    *   Konsep parsing data I/O (REST API, gRPC, Message Queue, Environment Variables).
*   **Alokasi Waktu Belajar:** 6 - 8 Jam (Membaca, Analisis Kode, Praktik Laboratorium)

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1.  **Mendiagnosis Batasan Tipe Statis:** Mengidentifikasi secara sistematis titik batas runtime (*runtime boundary failure points*) di mana sistem tipe TypeScript hilang (*type erasure*), mengekspos aplikasi terhadap mutasi data tak terduga.
2.  **Mengimplementasikan Paradigma "Parse, Don't Validate":** Menerapkan pola arsitektur parsing formal untuk mentransmisikan data mentah non-tipe (*untyped raw data*) menjadi tipe domain yang valid dan *type-safe* secara deterministik.
3.  **Mengevaluasi dan Mengonfigurasi Schema Engine:** Menguasai trade-off performa, bundle size, dan mekanisme inferensi tipe antara library validasi modern (Zod, TypeBox, Valibot, dan ArkType).
4.  **Membangun Custom Type Guards & Branded Types:** Merancang mekanisme validasi tipe nominal (*nominal typing*) dan *assertion functions* untuk mencegah kebocoran invariant bisnis pada tingkat kompilasi dan runtime.
5.  **Mengonfigurasi Compiler Hardening:** Menyetel `tsconfig.json` ke tingkat keamanan produksi maksimum (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `strict`) guna mengeliminasi blindspot inferensi bawaan.
6.  **Mengintegrasikan Runtime Validation pada Pipeline I/O:** Membangun middleware dan validator adapter yang terisolasi untuk API Request payload, Environment Variables, dan Message Bus Consumer.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Ilusi Keamanan Type System
Banyak insinyur perangkat lunak memiliki ilusi bahwa jika kode TypeScript lolos tahap kompilasi (`tsc --noEmit` sukses), maka aplikasi mereka sepenuhnya bebas dari galat inkonsistensi tipe (*type mismatch*). Ini adalah kesalahan fundamental: **TypeScript tidak ada saat runtime.**

```
[ Waktu Kompilasi: TypeScript ]   ====== Compiler (tsc) =====>   [ Runtime: JavaScript Engine ]
- Static Analysis                                                 - Garbage Collection
- Invariant Checking                                              - V8 Execution Pipeline
- Structural Subtyping                                            - TYPE ERASURE (Semua tipe hilang!)
- IDE Autocomplete                                                - Hanya mengeksekusi primitive JS
```

Saat program berjalan di Node.js, Bun, atau Browser, semua `interface`, `type`, dan `generics` telah dilucuti secara total. Data yang masuk melalui jaringan (HTTP Body, RPC parameter, WebSocket payload), storage (Redis, PostgreSQL query hasil deserialize JSON), atau OS (Environment Variables) pada dasarnya adalah `unknown`.

### Paradigma: "Parse, Don't Validate"
Mental model validasi konvensional (*Validation*) memeriksa apakah suatu input memenuhi kriteria tertentu, lalu mengembalikan nilai boolean (`isValid: boolean`). Pola ini berbahaya karena jika validasi berhasil, tipe data dari variabel tersebut tidak berubah—developer masih harus melakukan type casting paksa (`as TargetType`).

Mental model *Parsing* menerima data non-deterministik (`unknown`), membedah strukturnya, memverifikasi invarian, dan menghasilkan representasi data baru yang dijamin strukturnya secara matematis di dalam sistem tipe. Jika input cacat, eksekusi diputus seketika pada lapisan pembatas (*boundary layer*).

```
Model Validasi Konvensional (Rentan):
Input (unknown) ---> [ Is valid? (Boolean) ] ---> True ---> Cast paksa (as User) ---> Domain Logic
                                                    \-----> False ---> Error

Model Parsing (Aman/Hardened):
Input (unknown) ---> [ Parse Engine ] ---> Sukses: Output (Parsed & Deeply Typed User) ---> Domain Logic
                                     \---> Gagal: Return Structured Parse Error (Fail Fast)
```

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur pertahanan runtime membagi sistem menjadi dua zona: **Untrusted Zone** (lapisan I/O eksternal) dan **Trusted Core** (domain entity dan business logic internal). Antara kedua zona ini, ditempatkan **Validation Boundary Gate**.

```
+-----------------------------------------------------------------------------------------------+
| UNTRUSTED EXTERNAL ZONE (Non-Deterministic Input)                                             |
|                                                                                               |
|  [ HTTP Payload ]        [ Environment Vars ]       [ Redis/DB JSON ]     [ 3rd-Party API ]   |
|         |                        |                          |                    |            |
+---------|------------------------|--------------------------|--------------------|------------+
          |                        |                          |                    |
          \------------------------\-----------+--------------/--------------------/
                                               |
                                               v
                        +---------------------------------------------+
                        | RUNTIME VALIDATION BOUNDARY GATE            |
                        |                                             |
                        |  - Strips unknown fields (Strip Unknown)    |
                        |  - Coerces primitives (Coercion Engine)     |
                        |  - Enforces Business Invariants             |
                        |  - Generates Nominal / Branded Types        |
                        +---------------------------------------------+
                                       |              \
                       [Validation Succeeded]    [Validation Failed]
                                       |                \
                                       v                 v
+--------------------------------------------------+  +-----------------------------------------+
| TRUSTED RUNTIME CORE (Strict Domain Guarantees)  |  | ERROR ISOLATION LAYER                   |
|                                                  |  |                                         |
|  - Domain Entities (Branded Types)               |  | - RFC 7807 Problem Details              |
|  - Invariant-Safe Operations                     |  | - Obfuscated Safe Errors (No leak)      |
|  - Strict Null & Non-Index Access Safe           |  | - Structured Telemetry Logging          |
|  - Pure Functional Domain Services               |  | - Metric Emission                       |
+--------------------------------------------------+  +-----------------------------------------+
```

### Diagram Alur Siklus Hidup Eksekusi Data Boundary

```
[ Raw Network Buffer ]
         |
         v
[ JSON.parse() ]  --> Output: any (DILARANG: Titik bahaya terbesar)
         |
         v
[ Type Casting to unknown ] (Boundary Sanitization)
         |
         v
[ Schema Parser: schema.safeParse(data) ]
         |
         +-----------------------+
         |                       |
   [ Status: Success ]     [ Status: Failure ]
         |                       |
         v                       v
[ Deep Freeze / Brand ]    [ Map ke AppError ]
         |                       |
         v                       v
[ Inject ke Use-Case ]     [ Fail-Fast: Abort Request (400 Bad Request) ]
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Type Erasure dan Boundary Erosion
TypeScript beroperasi menggunakan *structural subtyping* (duck typing). Namun, saat kompilasi:
*   Semua pernyataan `interface`, `type Alias`, dan deklarasi generic dimusnahkan.
*   Hanya konstruksi murni JavaScript yang tersisa (class, function, variable).
*   Jika suatu runtime data payload melanggar skema (misal: properti bertipe number menerima string), V8 engine tetap mengeksekusinya hingga terjadi runtime crash (`TypeError: x is not a function` atau silent corruption berupa `NaN` yang mencemari database).

### 2. Mekanisme Internal Library Validasi
Terdapat tiga pendekatan arsitektural utama dalam implementasi runtime schema parser:

*   **Higher-Order Function / Object-Wrapper (Zod, Valibot):**
    Menggunakan rantai prototipe class/closure function yang membungkus fungsi parsing individual. Setiap sub-skema (misal: `z.string().min(5)`) mengembalikan node pohon AST runtime. Saat dipanggil, fungsi ini menelusuri pohon data secara rekursif.
*   **JSON Schema Compilation (TypeBox):**
    Menghasilkan objek JSON Schema formal (draft-07/2020-12) dan menggunakan compiler JIT (seperti `Ajv`) yang mengompilasi skema menjadi kode JavaScript murni dengan teknik runtime string generation. Ini menghasilkan eksekusi tercepat tanpa penalti rekursi objek.
*   **JIT Type Compilation / Morphism (ArkType):**
    Mengompilasi definisi tipe berbasis string (misal: `"string>5"`) langsung menjadi fungsi pembanding biner yang teroptimasi secara inline untuk engine V8.

### 3. Komparasi Karakteristik Engine

| Fitur / Karakteristik | Zod | TypeBox | Valibot | ArkType |
| :--- | :--- | :--- | :--- | :--- |
| **Arsitektur Internal** | Functional OOP / Chaining | Pure JSON Schema AST | Modular Tree-Shakable Functions | Scoped Type Parsing DSL |
| **Throughput Parsing** | Sedang (~1x baseline) | Sangat Tinggi (~10-25x via Ajv) | Tinggi (~2-5x) | Sangat Tinggi (~8-15x) |
| **Bundle Footprint** | ~40-60 KB minified | Ringan (~10 KB tanpa Ajv) | Ultra Ringan (< 2 KB modul) | Sedang (~20-30 KB) |
| **Tree-shakeability** | Kurang optimal | Bagus | Sempurna (modular functional) | Sedang |
| **Ekosistem & Integrasi** | Defacto Standard | Tinggi (OpenAPI standard) | Berkembang Pesat | Menjanjikan |

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Nominal Typing Menggunakan Type Branding
Secara default, TypeScript menggunakan *Structural Typing*. Artinya, dua tipe berikut dianggap identik:

```typescript
type UserId = string;
type OrderId = string;

let uId: UserId = "usr_123";
let oId: OrderId = "ord_999";
uId = oId; // VALID SECARA STATIS! Tetapi ini cacat secara domain.
```

Untuk membatasi kebocoran domain, kita harus memberlakukan *Nominal Typing* secara artifisial melalui teknik yang disebut **Type Branding**:

```typescript
declare const BrandSymbol: unique symbol;

export type Brand<T, TBrand extends string> = T & {
  readonly [BrandSymbol]: TBrand;
};

export type UserId = Brand<string, "UserId">;
export type OrderId = Brand<string, "OrderId">;

// Sekarang:
let validUserId = "usr_123" as UserId;
let validOrderId = "ord_999" as OrderId;

// validUserId = validOrderId; // COMPILE ERROR: Type '"OrderId"' is not assignable to type '"UserId"'.
```

### 2. Strict Compiler Configuration Hardening
Hardening dimulai dari berkas `tsconfig.json`. Konfigurasi longgar adalah sumber dari kerentanan logika runtime. Tiga flag yang krusial untuk lingkungan produksi enterprise:

*   `"strict": true`: Mengaktifkan seluruh keluarga pengecekan strict (`noImplicitAny`, `strictNullChecks`, `strictFunctionTypes`, dll).
*   `"noUncheckedIndexedAccess": true`: Secara default, pengaksesan array atau dynamic object mengembalikan `T`. Dengan flag ini, pengaksesan mengembalikan `T | undefined`, memaksa developer menangani kemungkinan *out-of-bounds error*.
*   `"exactOptionalPropertyTypes": true`: Membedakan secara eksplisit properti yang didefinisikan sebagai opsional (`field?: string`) dengan properti yang bernilai undefined (`field: string | undefined`). Properti opsional tidak boleh dikirimkan secara eksplisit dengan nilai `undefined` jika nilainya dilarang ada.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL (STEP-BY-STEP)

Berikut adalah pipeline parsing runtime fungsional berbasis Zod yang mengimplementasikan Brand typing, sanitasi input, dan *safe transformation*.

```typescript
import { z } from "zod";

// Langkah 1: Buat Branded Type Primitives
declare const ValidatedEmailBrand: unique symbol;
export type ValidatedEmail = string & { readonly [ValidatedEmailBrand]: "ValidatedEmail" };

declare const CentAmountBrand: unique symbol;
export type CentAmount = number & { readonly [CentAmountBrand]: "CentAmount" };

// Langkah 2: Definisikan Skema Zod dengan Refinements & Transformation
export const EmailSchema = z
  .string()
  .trim()
  .toLowerCase()
  .email({ message: "Format alamat email tidak valid." })
  .transform((val) => val as ValidatedEmail);

export const CurrencyCentSchema = z
  .number()
  .int({ message: "Nilai sen harus berupa bilangan bulat." })
  .positive({ message: "Nilai transfer harus lebih dari 0." })
  .transform((val) => val as CentAmount);

export const CreateTransactionSchema = z
  .object({
    senderEmail: EmailSchema,
    recipientEmail: EmailSchema,
    amountInCents: CurrencyCentSchema,
    metadata: z.record(z.string(), z.string()).optional(),
  })
  .strict(); // Mencegah Prototype Pollution dan Parameter Injecting

// Inferensi Tipe TypeScript secara otomatis dari Skema Runtime
export type CreateTransactionDTO = z.infer<typeof CreateTransactionSchema>;

// Langkah 3: Implementation Gateway Function
export function parseIncomingTransaction(rawInput: unknown): {
  success: boolean;
  data?: CreateTransactionDTO;
  error?: string[];
} {
  const result = CreateTransactionSchema.safeParse(rawInput);

  if (!result.success) {
    return {
      success: false,
      error: result.error.errors.map(
        (err) => `[${err.path.join(".")}] ${err.message}`
      ),
    };
  }

  return {
    success: true,
    data: result.data,
  };
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut bedah teknis implementasi Seksi 07:

1.  `declare const ValidatedEmailBrand: unique symbol;`:
    Membuat simbol unik yang hanya eksis pada level sistem tipe TypeScript. Simbol ini tidak membebani memori runtime karena kata kunci `declare` mencegah emit JavaScript.
2.  `export type ValidatedEmail = string & { readonly [ValidatedEmailBrand]: "ValidatedEmail" };`:
    Membentuk tipe persimpangan (*intersection type*). Menginstruksikan compiler bahwa tipe ini adalah `string` yang membawa tag meta-data identitas. Tipe data string biasa tidak dapat secara sengaja langsung di-*assign* ke tipe ini tanpa melalui konversi.
3.  `.trim().toLowerCase()`:
    Melakukan sanitasi mutasi data pra-validasi. Hal ini krusial untuk mencegah duplikasi data akibat perbedaan spasi kosong atau kapitalisasi huruf.
4.  `.transform((val) => val as ValidatedEmail)`:
    Ini adalah jembatan emas runtime hardening: Jika dan hanya jika string telah lolos validasi regex format email, Zod mentransformasikannya menjadi tipe `ValidatedEmail`. Data mentah kini telah resmi naik level menjadi *Domain Validated Value Object*.
5.  `.strict()`:
    Melarang properti tak dikenal (*unknown keys*). Jika klien mengirim payload jahat seperti `{ "__proto__": { "admin": true } }`, skema akan langsung menolak payload alih-alih meloloskannya ke heap memory.
6.  `const result = CreateTransactionSchema.safeParse(rawInput);`:
    Mencegah pelemparan exception bawaan (`throw new ZodError()`). Pelemparan exception mengakibatkan *V8 de-optimization* dan menurunkan kinerja server secara drastis saat terjadi banjir request ilegal.

---

# SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Konteks Permasalahan
Sebuah platform Neobank memproses webhook pembayaran eksternal dari gateway mitra (misal: Stripe/Xendit). 

### Insiden Produksi (Post-Mortem)
Layanan core ledger neobank mengalami insiden kehilangan pembukuan saldo sebesar $42.000 karena kode backend mempercayai struktur data webhook menggunakan TypeScript type casting sederhana:

```typescript
// KODE RENTAN YANG MENYEBABKAN INSIDEN:
app.post("/api/v1/webhook", async (req, res) => {
  const payload = req.body as ExternalPaymentEvent; // TYPE ERASURE MENGHANCURKAN KEAMANAN!
  
  // Jika payload.data.amount berupa string "100" alih-alih number 100:
  // 100 + payload.data.amount => "100100" (Konkatenasi string, BUKAN penambahan integer)
  await creditBalance(payload.accountId, payload.data.amount);
});
```

Mitra penyedia gateway meluncurkan pembaruan minor pada format API mereka di mana properti `amount` diubah dari integer sen menjadi representasi floating decimal berserialisasi string. TypeScript compiler tidak mendeteksi galat tersebut karena casting `as ExternalPaymentEvent` mengabaikan pemeriksaan runtime. Akibatnya, saldo akun pengguna dikreditkan secara salah akibat kelemahan evaluasi ekspresi dynamic JavaScript.

### Solusi Desain
Membangun **Zero-Trust Ingestion Engine** yang menggunakan kombinasi `TypeBox` (dipilih untuk skenario throughput tinggi dengan compiler `Ajv`) guna memvalidasi, menormalkan tipe, dan menolak paket webhook malformed sebelum menyentuh lapisan service ledger.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem ingest webhook performa tinggi menggunakan `@sinclair/typebox` dan validator engine `ajv` (kompatibel standar industri ISO-8583 / FinTech).

```typescript
import { Type, Static } from "@sinclair/typebox";
import Ajv, { ErrorObject } from "ajv";
import addFormats from "ajv-formats";

// Inisialisasi AJV dengan Hardened Security Options
const ajv = addFormats(
  new Ajv({
    allErrors: true,
    removeAdditional: false, // Jangan biarkan mutasi diam-diam, tolak secara eksplisit!
    useDefaults: false,
    coerceTypes: false, // DILARANG otomatis mengubah tipe, fail-fast pada payload anomali
    strict: true,
  }),
  ["date-time", "uuid"]
);

// 1. Definisikan Nominal Branded Types
declare const AccountIdBrand: unique symbol;
export type AccountId = string & { readonly [AccountIdBrand]: "AccountId" };

// 2. Buat Definisi Skema TypeBox (JSON Schema Specification Compliant)
export const WebhookEventSchema = Type.Object(
  {
    eventId: Type.String({ format: "uuid" }),
    accountId: Type.String({ pattern: "^acc_[a-zA-Z0-9]{16}$" }),
    amountInCents: Type.Integer({
      minimum: 1,
      maximum: 1_000_000_000, // Batas transaksi tunggal $10M
    }),
    currency: Type.Union([
      Type.Literal("IDR"),
      Type.Literal("USD"),
      Type.Literal("SGD"),
    ]),
    timestamp: Type.String({ format: "date-time" }),
    signature: Type.String({ minLength: 64, maxLength: 64 }), // SHA-256 Signature string
  },
  { additionalProperties: false } // Strict mode: cegah parameter injection
);

export type WebhookEventPayload = Static<typeof WebhookEventSchema>;

// 3. Kompilasi Skema menjadi JIT Function
const compileValidator = ajv.compile<WebhookEventPayload>(WebhookEventSchema);

// 4. Boundary Parse Execution Result Container
export type ValidationOutcome<T> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly errors: ReadonlyArray<string> };

export class PaymentIngressSecurityGate {
  public static validatePayload(rawPayload: unknown): ValidationOutcome<WebhookEventPayload> {
    if (typeof rawPayload !== "object" || rawPayload === null) {
      return {
        ok: false,
        errors: ["Payload root data harus berupa valid JSON non-null Object."],
      };
    }

    const isValid = compileValidator(rawPayload);

    if (!isValid && compileValidator.errors) {
      return {
        ok: false,
        errors: this.normalizeAjvErrors(compileValidator.errors),
      };
    }

    // Return value yang aman dikonsumsi oleh Trusted Domain
    return {
      ok: true,
      value: rawPayload as WebhookEventPayload,
    };
  }

  private static normalizeAjvErrors(errors: ErrorObject[]): string[] {
    return errors.map((err) => {
      const path = err.instancePath ? err.instancePath : "/root";
      return `Security Rule Violation: [${path}] ${err.message} (${JSON.stringify(err.params)})`;
    });
  }
}

// 5. Mock Consumer Execution Demonstration
function simulateWebhookTraffic() {
  const malformedAttackPayload = {
    eventId: "not-a-uuid",
    accountId: "acc_invalidlen",
    amountInCents: 100.5, // Gagal: Bukan Integer
    currency: "EUR", // Gagal: Di luar skema union
    timestamp: "invalid-date",
    signature: "abc",
    injectedProperty: "malicious_script", // Gagal: additionalProperties: false
  };

  const validationResult = PaymentIngressSecurityGate.validatePayload(malformedAttackPayload);

  if (!validationResult.ok) {
    console.error("INGRESS BLOCKED! Ancaman Keamanan / Anomali Data Terdeteksi:");
    validationResult.errors.forEach((err) => console.error(` - ${err}`));
  } else {
    console.log("PAYLOAD VERIFIED! Diteruskan ke Ledger Core:", validationResult.value);
  }
}

simulateWebhookTraffic();
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih strategi runtime validation menuntut pemahaman mendalam atas implikasi operasional sistem:

### 1. Zod vs TypeBox
*   **Zod:** 
    *   *Kelebihan:* Kemudahan deklarasi logika (ekosistem developer sangat masif), fitur chaining sangat ramah IDE, integrasi kelas satu dengan React Hook Form, tRPC, Prisma.
    *   *Kekurangan:* Eksekusi murni berbasis interpretasi JavaScript function tree. Untuk parsing throughput ekstrem (100k TPS pada gateway level microservice), latensi overhead Zod dapat memakan alokasi CPU yang masif.
*   **TypeBox:**
    *   *Kelebihan:* Menghasilkan pure JSON-Schema standard. Dapat dikompilasi menggunakan Ajv yang mengubah skema menjadi optimized machine execution string via code-generation JIT. Performa parsing setara native code.
    *   *Kekurangan:* Sintaks lebih kaku dibandingkan method chaining Zod. Memerlukan integrasi library Ajv pihak ketiga untuk menjalankan fungsi validatornya.

### 2. Manual Custom Type Guards vs Library Validation
*   **Type Guard Manual (`value is T`):**
    *   *Kelebihan:* Menghasilkan 0 KB dependencies overhead.
    *   *Kekurangan:* Sangat rentan *human error*. Kompiler menganggap developer selalu benar. Jika kode guard salah:
        ```typescript
        function isUser(val: any): val is { id: string } {
           return typeof val === "object"; // Cacat: null juga bertipe object, id tidak diperiksa!
        }
        ```
        Sistem tipe Anda rusak secara diam-diam.
*   **Automated Schema Inference Library:**
    *   *Kelebihan:* Mengikat representasi tipe compile-time dan runtime validator secara absolut menggunakan *Single Source of Truth*.
    *   *Kekurangan:* Menambah ukuran package distribution dependencies (*cold start overhead*).

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Prototype Pollution Melalui `JSON.parse`
Data runtime yang tidak dibersihkan dapat membawa kunci `__proto__`, `constructor`, atau `prototype`. Jika Anda menggunakan schema validation yang permisif atau object assign biasa:

```typescript
const dangerousPayload = JSON.parse('{"__proto__": {"isAdmin": true}}');
const target = Object.assign({}, dangerousPayload);
// Mengakibatkan polusi prototipe global jika library parsing tidak memiliki proteksi intrinsic
```
*Solusi:* Selalu konfigurasikan skema dengan flag `.strict()` pada Zod atau `additionalProperties: false` pada TypeBox/JSON Schema.

### 2. Bahaya Tipe `any` yang Mematikan Runtime Safety
Banyak developer tanpa sengaja menjebol perlindungan skema dengan mem-bypass validasi menggunakan tipe `any`:

```typescript
const result = schema.safeParse(req.body);
if (result.success) {
  const data: any = result.data; // DEFENSE BREACH!
  data.unknownMethodCall(); // Fatal Runtime Error: Uncaught TypeError
}
```
*Solusi:* Aktifkan linting rule `@typescript-eslint/no-explicit-any: "error"` dan `@typescript-eslint/no-unsafe-assignment: "error"`.

### 3. Masalah Coercion Tipe Bawaan
Hati-hati dengan fitur auto-coercion (seperti `z.coerce.boolean()`):
```typescript
z.coerce.boolean().parse("false"); // MENGHASILKAN: true!
```
*Mengapa?* Karena dalam JavaScript: `Boolean("false") === true`. String tidak kosong dievaluasi menjadi nilai boolean `true`. Selalu gunakan transform eksplisit dengan mapping strict value.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Bergantung pada Type Casting Operator `as`
```typescript
// SALAH (Anti-Pattern Berbahaya):
const rawUser = await fetch("/api/user/1").then(res => res.json()) as User;
console.log(rawUser.profile.avatar); // KABOOM jika API mengembalikan null atau struktur berubah!

// BENAR:
const rawUser: unknown = await fetch("/api/user/1").then(res => res.json());
const user = UserSchema.parse(rawUser); // Throw fail-fast atau safeParse
console.log(user.profile.avatar); // 100% Terjamin eksistensinya secara sistemik
```

### Kesalahan Fatal 2: Environment Variables Tanpa Validasi Bootstrap
Banyak microservice startup tanpa memeriksa env variables. Aplikasi berjalan normal sampai crash di tengah malam ketika fitur yang menggunakan variabel tersebut pertama kali dieksekusi.

```typescript
// SALAH:
const redisPort = parseInt(process.env.REDIS_PORT!); // Jika undefined, bernilai NaN

// BENAR:
const EnvSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]),
  REDIS_PORT: z.string().transform((v) => parseInt(v, 10)).pipe(z.number().min(1).max(65535)),
  API_SECRET_KEY: z.string().min(32),
});

// Eksekusi pada entry-point aplikasi paling pertama (index.ts baris 1)
export const ENV = EnvSchema.parse(process.env);
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Single Source of Truth (SSOT):**
    Dilarang keras mendefinisikan interface TypeScript secara terpisah dari schema validator runtime. Gunakan type inference bawaan skema:
    ```typescript
    // Rekomendasi
    export const UserDTOSchema = z.object({ ... });
    export type UserDTO = z.infer<typeof UserDTOSchema>;
    ```
2.  **Immutability Pasca Validasi:**
    Bekukan (*freeze*) data yang telah divalidasi saat berada di arsitektur tingkat sensitif untuk mencegah mutasi referensi objek secara tidak disengaja.
    ```typescript
    const validatedData = Object.freeze(OrderSchema.parse(payload));
    ```
3.  **Boundary Isolation:**
    Hanya parsing data pada batas perimeter aplikasi (Controller API, MQ Consumer, Repository Gateway). Jangan melakukan re-validasi pada *Inner Domain Services* atau *Pure Functions* jika data tersebut sudah memiliki jaminan Branded Types dari gate perimeter.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

Parsing runtime membawa konsekuensi komputasi CPU. Terapkan strategi berikut untuk backend skala tinggi:

1.  **Pra-kompilasi Skema Regex dan Instance Validator:**
    Hindari merekonstruksi instance schema validator di dalam loop atau request lifecycle scope. Buat skema sebagai modul singleton terisolasi:
    ```typescript
    // BURUK: Kompilasi berulang pada tiap HTTP Request
    app.post("/data", (req, res) => {
      const schema = z.object({ ... }); // Alokasi memori baru berulang-ulang
      schema.parse(req.body);
    });

    // OPTIMAL: Instansiasi satu kali di module scope (V8 Heap Re-use)
    const DataSchema = z.object({ ... });
    app.post("/data", (req, res) => {
      DataSchema.parse(req.body);
    });
    ```
2.  **Benchmarking Memory Footprint & Throughput Execution:**
    Pada rute lalu lintas tinggi (>10.000 req/sec), migrasikan Zod ke TypeBox + Ajv. Ajv mengompilasi schema menjadi bytecode teroptimasi V8 yang dieksekusi secara instan tanpa traversal pohon skema.

---

# SEKSI 16 — KEAMANAN & HARDENING

### Penanganan RFC 7807 Error Sanitization
Saat validasi gagal, engine validasi sering kali membocorkan rincian internal sistem yang dapat dimanfaatkan penyerang untuk profiling database atau arsitektur internal.

```typescript
// Implementasikan Error Obfuscation Transformer untuk Keamanan Eksternal
export function createSafeProblemDetails(error: z.ZodError) {
  return {
    type: "https://api.domain.com/errors/validation-error",
    title: "Unprocessable Entity Data Violation",
    status: 422,
    detail: "Satu atau lebih parameter input melanggar batasan keamanan domain.",
    // Hanya petakan field path dan error code generik, JANGAN bocorkan internal stack/DB constraints!
    invalidParams: error.issues.map((issue) => ({
      name: issue.path.join("."),
      reason: issue.message,
      code: issue.code,
    })),
  };
}
```

*Kewaspadaan DoS Regex:* Pastikan semua schema yang menggunakan regular expressions (`.regex()`) telah melalui audit ReDoS (*Regular Expression Denial of Service*) untuk menghindari catastrophic backtracking yang memblokir Node.js Event Loop.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Validasi runtime adalah instrumen telemetri pertama untuk mendeteksi serangan atau anomali integrasi pihak ketiga.

```typescript
import { performance } from "perf_hooks";

export function telemetryValidatedParser<T>(
  schemaName: string,
  parseFn: () => T,
  logger: (log: Record<string, unknown>) => void
): T {
  const start = performance.now();
  try {
    const result = parseFn();
    const duration = performance.now() - start;
    
    // Track parse latency metric
    if (duration > 50) { // Parsing latency warning threshold (50ms)
      logger({
        level: "WARN",
        event: "SCHEMA_PARSING_SLOW",
        schemaName,
        durationMs: duration,
      });
    }
    return result;
  } catch (error) {
    const duration = performance.now() - start;
    logger({
      level: "ERROR",
      event: "SECURITY_BOUNDARY_VIOLATION",
      schemaName,
      durationMs: duration,
      errorDetails: error instanceof Error ? error.message : "Unknown error",
    });
    throw error;
  }
}
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Type Erasure:** Semua tipe data TypeScript musnah saat kompilasi ke JS. Jaringan, File System, dan Database selalu mengembalikan data non-deterministik `unknown`.
*   **Parse, Don't Validate:** Ubah data dari `unknown` menjadi tipe data domain yang divalidasi. Jangan biarkan runtime logic berjalan berdasarkan asumsi casting `as`.
*   **Branded Types:** Gunakan Nominal Typing (`T & { readonly [Brand]: "..." }`) untuk mencegah tertukarnya tipe primitif identik (seperti `UserId` vs `OrderId`).
*   **Strict Compiler Flags:** Nyalakan `"strict": true`, `"noUncheckedIndexedAccess": true`, dan `"exactOptionalPropertyTypes": true` di `tsconfig.json`.
*   **Zod vs TypeBox:** Gunakan Zod untuk kemudahan deklarasi dan DX tingkat tinggi; pilih TypeBox/Ajv jika aplikasi menuntut extreme throughput performance dan low latency parsing.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1.  **Apa yang terjadi pada interface `User` berikut setelah TypeScript dikompilasi ke JavaScript?**
    ```typescript
    interface User { id: string; name: string; }
    ```
    *   A. Dikonversi menjadi fungsi konstruktor JavaScript standar.
    *   B. Dikonversi menjadi class prototype.
    *   C. Dihapus secara total dari output JavaScript (*type erasure*).
    *   D. Dikonversi menjadi objek JSON Schema.

2.  **Tipe data TypeScript manakah yang paling tepat digunakan untuk merepresentasikan payload body dari request jaringan mentah sebelum divalidasi?**
    *   A. `any`
    *   B. `object`
    *   C. `unknown`
    *   D. `never`

3.  **Apa tujuan utama dari method `.strict()` saat mendefinisikan objek skema Zod?**
    *   A. Memastikan parsing dieksekusi secara sinkronus.
    *   B. Menolak data masukan yang memiliki kunci properti tambahan di luar skema.
    *   C. Memaksa semua nilai number bernilai positif.
    *   D. Menjalankan skema pada thread worker terpisah.

4.  **Apa risiko keamanan terbesar dari potongan kode ini?**
    ```typescript
    const payload = req.body as CreateInvoiceDTO;
    ```
    *   A. Menghasilkan error kompilasi karena type casting dilarang di Node.js.
    *   B. Mengabaikan validasi runtime; payload dapat bernilai apa pun dan merusak sistem.
    *   C. Menurunkan performa CPU engine JavaScript secara instan.
    *   D. Memori V8 langsung bocor (*memory leak*).

5.  **Manakah flag `tsconfig.json` yang mengubah perilaku indexing array dari mengembalikan `T` menjadi `T | undefined`?**
    *   A. `strictNullChecks`
    *   B. `noImplicitAny`
    *   C. `noUncheckedIndexedAccess`
    *   D. `exactOptionalPropertyTypes`

---

### Soal Tingkat Menengah (Intermediate)

6.  **Perhatikan kode custom type guard berikut:**
    ```typescript
    function isStringArray(value: unknown): value is string[] {
      return Array.isArray(value) && value.every(item => typeof item === "string");
    }
    ```
    **Apa kelemahan utama dari pola type guard manual ini dalam skala basis kode enterprise besar?**
    *   A. Engine JavaScript menolak menjalankan method `Array.isArray`.
    *   B. Kompiler tidak dapat memverifikasi kebenaran logika runtime di dalam fungsi guard; jika developer membuat kesalahan verifikasi, sistem tipe tetap menganggapnya benar secara mutlak.
    *   C. Mengakibatkan crash stack overflow jika array memiliki elemen lebih dari 10.
    *   D. Tidak kompatibel dengan ES Module.

7.  **Dalam implementasi Branded Types berikut, mengapa kita menggunakan `unique symbol` alih-alih `string` literal biasa untuk properti brand?**
    ```typescript
    declare const BrandSym: unique symbol;
    type Brand<T, B> = T & { readonly [BrandSym]: B };
    ```
    *   A. Agar brand tersebut memiliki ukuran byte yang lebih kecil di disk.
    *   B. Mencegah tabrakan nama properti secara tidak sengaja (*name collision*) dengan properti asli yang ada pada runtime objek.
    *   C. Karena string literal tidak didukung pada versi TypeScript modern.
    *   D. Agar objek dapat di-serialize langsung menjadi file binary.

8.  **Mengapa eksekusi `z.coerce.number().parse("123abc")` menghasilkan masalah runtime tak terduga jika tidak ditangani dengan refinement?**
    *   A. Karena mengembalikan nilai `NaN` yang bertipe `number` di JavaScript, sehingga lolos validasi tipe statis TypeScript.
    *   B. Karena fungsi tersebut memutus koneksi database.
    *   C. Karena Zod otomatis menghentikan worker process Node.js.
    *   D. Karena string tidak diizinkan masuk ke method coerce.

9.  **Arsitektur TypeBox menawarkan performa runtime validation yang secara signifikan jauh lebih cepat dibanding Zod. Apa fondasi teknis penyebabnya?**
    *   A. TypeBox ditulis menggunakan bahasa C++ addon native.
    *   B. TypeBox menghasilkan representasi skema JSON murni yang dapat dikompilasi oleh JIT engine (seperti Ajv) menjadi fungsi flat JavaScript yang teroptimasi tanpa traversal rekursif runtime.
    *   C. TypeBox mengeksekusi validasi langsung di dalam kartu grafis (GPU).
    *   D. TypeBox mengabaikan validasi untuk field yang bersarang (*nested*).

10. **Apa dampak menyalakan flag `"exactOptionalPropertyTypes": true` pada potongan kode berikut?**
    ```typescript
    interface Settings { theme?: "dark" | "light"; }
    const userSettings: Settings = { theme: undefined };
    ```
    *   A. Kode tetap valid dan lolos kompilasi.
    *   B. Kompiler melempar error: properti opsional `theme` tidak boleh secara eksplisit diberikan nilai `undefined`.
    *   C. Objek `userSettings` otomatis terhapus saat runtime.
    *   D. Nilai default `"dark"` otomatis diisikan.

---

### Kunci Jawaban
1.  **C** — Seluruh interface dihapus saat kompilasi (*type erasure*).
2.  **C** — `unknown` adalah tipe *top-type* yang aman karena memaksa type narrowing sebelum dieksekusi.
3.  **B** — `.strict()` menolak (*reject*) key tambahan yang tidak terdaftar di skema objek.
4.  **B** — Operator `as` hanya melakukan type assertion statis dan diabaikan saat runtime, memicu runtime error jika struktur data berbeda.
5.  **C** — `noUncheckedIndexedAccess` menambahkan `undefined` pada setiap lookup dinamis.
6.  **B** — Custom type guard sepenuhnya bergantung pada integritas logika manual developer tanpa verifikasi silang compiler.
7.  **B** — `unique symbol` menjamin identitas unik global pada level tipe sehingga tidak berbenturan dengan kunci object runtime.
8.  **A** — `Number("123abc")` menghasilkan `NaN`. Dalam JavaScript, `typeof NaN === "number"`, sehingga dapat meloloskan invariant secara keliru.
9.  **B** — Skema TypeBox sesuai standar JSON Schema dan dapat di-JIT compile oleh Ajv menjadi kode linear bebas alokasi tree object.
10. **B** — Flag ini secara ketat membedakan ketiadaan key (*absent*) dengan key yang memiliki nilai literal *undefined*.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Proyek
Buatlah sebuah micro-module utilitas bernama **`EnterpriseConfigHardener`** yang bertanggung jawab membaca, memvalidasi, mengamankan, dan membekukan konfigurasi lingkungan (*Environment Variables*) saat sistem backend pertama kali booting.

### Spesifikasi Kebutuhan Teknis
1.  **Skema Konfigurasi:** Definisikan skema menggunakan library validasi pilihan Anda (Zod atau TypeBox) yang memvalidasi struktur environment:
    *   `PORT`: Wajib integer numerik, rentang 1024 - 65535.
    *   `DATABASE_URL`: Wajib format connection string URI PostgreSQL yang valid (`postgres://user:pass@host:port/db`).
    *   `JWT_SECRET`: Wajib string dengan entropi tinggi (minimal 32 karakter).
    *   `NODE_ENV`: Wajib bernilai literal `"development" | "staging" | "production"`.
    *   `RATE_LIMIT_ENABLED`: Wajib di-parse menjadi boolean murni dari input string string `"true"` atau `"false"`.
2.  **Branded Immutability:** Konversikan `DATABASE_URL` menjadi Branded Type `DatabaseConnectionString`. Pastikan konfigurasi yang diekspor berstatus `ReadonlyDeep` dan dibekukan menggunakan `Object.freeze()`.
3.  **Fail-Fast Mechanism:** Jika ada satu pun variabel yang cacat atau hilang, sistem **DILARANG** melakukan fallback diam-diam. Sistem harus mencetak laporan error terstruktur (menggunakan format ASCII table atau structured JSON) lalu memanggil `process.exit(1)`.
4.  **Verifikasi Negatif:** Buat test harness mandiri sederhana yang menguji:
    *   Kondisi saat env valid.
    *   Kondisi saat `DATABASE_URL` menggunakan skema selain postgres (misal: `mysql://...`).
    *   Kondisi saat `JWT_SECRET` kurang dari 32 karakter.
    *   Percobaan mutasi langsung (`config.PORT = 8080`) yang wajib menghasilkan error kompilasi dan runtime error (*strict mode TypeError*).