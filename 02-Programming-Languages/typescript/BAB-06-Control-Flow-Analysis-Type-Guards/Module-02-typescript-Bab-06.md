# BAB 06: Control Flow Analysis & Type Guards
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengurai cara kerja internal compiler TypeScript (`tsc`), khususnya interaksi antara *Binder* dan *Type Checker* dalam memproses *Control Flow Analysis* (CFA) melalui struktur data *Flow Graph*.
- Mengimplementasikan *Advanced User-Defined Type Guards* (`val is T`), *Assertion Functions* (`asserts val is T`), dan *Discriminated Unions* kompleks untuk validasi struktur data berlapis tanpa casting paksa (`as`).
- Mendiagnosis degradasi performa kompilasi (*type checking latency*) yang dipicu oleh combinatorial explosion pada narrowing union berskala besar.
- Merancang arsitektur pipeline pemrosesan event terdistribusi (*event-driven architecture*) yang aman secara tipe (*type-safe* dan *exhaustive*) menggunakan CFA dan *never-type exhaustiveness checking*.
- Mengidentifikasi batas kapabilitas narrowing TypeScript ketika berhadapan dengan *closure*, mutasi objek asinkron (*aliased mutations*), dan mutasi properti via *side-effects*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
1. Sistem Tipe Dasar & Lanjutan TypeScript: `union`, `intersection`, `unknown`, `never`, `any`.
2. Dasar-dasar type narrowing: operator `typeof`, `instanceof`, dan properti `in`.
3. Struktur AST (*Abstract Syntax Tree*) JavaScript/TypeScript dasar.
4. Konsep dasar arsitektur fungsional: Immutability, Pure Functions, dan Algebraic Data Types (ADT).

---

### 3. Concept & Internal Architecture (Mendalam)

Control Flow Analysis (CFA) pada compiler TypeScript bukan sekadar evaluasi sintaksis lokal, melainkan traversal graph berarah (*directed acyclic graph* / DAG) yang dibangun selama fase *binding* dan dievaluasi secara *lazy* pada fase *checking*.

```
+-------------------------------------------------------------------------+
|                          TypeScript Compiler                            |
|                                                                         |
|  [ Source Code ]                                                        |
|         │                                                               |
|         ▼                                                               |
|    ┌─────────┐                                                          |
|    │ Parser  │ ───► AST (Abstract Syntax Tree)                          |
|    └─────────┘                                                          |
|         │                                                               |
|         ▼                                                               |
|    ┌─────────┐         ┌──────────────────────────────────────────────┐ |
|    │ Binder  │ ──────► │ Flow Nodes / Flow Graph                      │ |
|    └─────────┘         │ (FlowStart, FlowAssignment, FlowBranch, ...) │ |
|         │              └──────────────────────────────────────────────┘ |
|         ▼                                      │                        |
|  ┌──────────────┐                              ▼                        |
|  │ Type Checker │ ◄────────────────────────────┘                        |
|  └──────────────┘      Query flow graph secara mundur (backwards)       |
|         │              untuk menghitung tipe efektif identifier.        |
|         ▼                                                               |
|  [ Type-checked AST & Diagnostics ]                                     |
+-------------------------------------------------------------------------+
```

#### Struktur Data Internal: `FlowNode` dan `FlowFlags`

Di dalam file source code compiler (`checker.ts` dan `binder.ts`), TypeScript mengonstruksi rantai `FlowNode`. Setiap kali ada deklarasi variabel, assignment, percabangan (`if`, `switch`, `ternary`), atau loop (`while`, `for`), compiler membuat simpul aliran baru yang merujuk pada simpul sebelumnya (*antecedent*).

Variasi flag internal pada `FlowNode` mencakup:
- `FlowFlags.Start`: Titik awal scope eksekusi (misalnya entry point fungsi).
- `FlowFlags.BranchLabel`: Titik temu (*convergence point*) dari dua atau lebih jalur kontrol alur (misalnya setelah blok `if-else`).
- `FlowFlags.Assignment`: Mutasi atau inisialisasi identifier.
- `FlowFlags.Condition`: Evaluasi predikat Boolean (penyempitan tipe terjadi di sini).
- `FlowFlags.ArrayMutation`: Mutasi array terdeteksi (seperti `.push()`).
- `FlowFlags.Unreachable`: Jalur eksekusi yang mustahil dilewati (tipe identifier bernilai `never`).

#### Evaluasi Tipe Secara Mundur (*Backwards Flow Evaluation*)

Ketika tipe sebuah identifier diperiksa di baris tertentu:
1. Type Checker memanggil fungsi internal `getFlowTypeOfReference(node, flowContainer)`.
2. Checker berjalan **mundur** dari `FlowNode` saat ini menelusuri rantai *antecedent*.
3. Jika menemukan `FlowFlags.Condition`, checker mengevaluasi apakah condition tersebut menyaring tipe identifier (misal `typeof x === "string"`).
4. Jika menemukan `FlowFlags.BranchLabel`, checker mengumpulkan tipe dari seluruh cabang konvergen dan menghasilkan *Union Type* dari seluruh kemungkinan status cabang tersebut.
5. Proses berhenti saat mencapai `FlowFlags.Start` atau assignment eksplisit yang menetapkan tipe awal.

#### Keterbatasan Analisis: Mutasi dan Closures

CFA TypeScript mengasumsikan bahwa pemanggilan fungsi independen dapat menghasilkan efek samping (*side-effects*). Namun, TypeScript membatalkan (*invalidates*) narrowing pada closure jika variabel yang ditangkap (*captured variable*) bermutasi di luar konteks lokal:

```typescript
let data: string | null = "INITIAL_STATE";

function executeProcess(): void {
  // CFA memeriksa apakah variabel lokal berubah di dalam nested closure:
  window.setTimeout(() => {
    // Pada saat eksekusi ini berjalan, data bisa saja telah diubah oleh thread event loop lain
    // TypeScript me-reset narrowing ke tipe awal yang dideklarasikan jika variabel di-reassign
  }, 1000);
}
```

Jika identifier dideklarasikan menggunakan `const`, CFA dapat mempertahankan presisi tipe secara permanen karena referensi memori dijamin stabil (*immutable binding reference*).

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Manual Type Casting / `as`) | Pendekatan CFA & Custom Type Guards |
| :--- | :--- | :--- |
| **Karakteristik** | Pengembang memaksa compiler mempercayai tipe data tanpa verifikasi runtime. | Compiler dan runtime berjalan sinkron melalui verifikasi predikat struktural. |
| **Keamanan Runtime** | Sangat rentan `TypeError: Cannot read properties of undefined` saat payload API berubah. | Bug runtime dicegah sejak dini; data tidak valid tertahan di guard layer. |
| **Maintainability** | Refactor rawan rusak karena casting membungkam alarm compile-time. | Perubahan skema data memicu error kompilasi di seluruh sistem secara deterministik. |
| **Overhead Kompilasi**| Rendah, karena checker tidak perlu menelusuri rantai predikat. | Terukur; memerlukan pemodelan tipe yang terstruktur agar tidak memicu bottleneck. |

---

### 5. How (Workflow Detail)

Alur kerja perancangan sistem validasi tipe berbasis CFA di tingkat enterprise:

```
[ Raw Untrusted Data (API/Message Broker) ]
                    │
                    ▼
       ┌────────────────────────┐
       │   Boundary Ingestion   │
       └────────────────────────┘
                    │
                    ▼
     ┌─────────────────────────────┐
     │ Type Assertion Function     │  (Gagal? Lempar Custom Domain Exception)
     │ (asserts data is Envelope)  │
     └─────────────────────────────┘
                    │
                    ▼ Valid
     ┌─────────────────────────────┐
     │ Discriminated Property      │
     │ Extraction (e.g., eventType)│
     └─────────────────────────────┘
                    │
                    ▼
     ┌─────────────────────────────┐
     │ Switch / Case Discrimination│
     └─────────────────────────────┘
      ├── case "PAYMENT_RECEIVED":  ──► Narrowed to PaymentReceivedEvent
      ├── case "PAYMENT_FAILED":    ──► Narrowed to PaymentFailedEvent
      └── default:                  ──► assertsUnreachable(exhaustiveCheck)
```

1. **Ingestion Boundary**: Terima data dari dunia luar (`unknown`).
2. **Assertion Verification**: Eksekusi runtime assertion function untuk memvalidasi struktur minimal envelope.
3. **Discriminant Extraction**: Akses diskriminator bertipe *literal primitive* (`string`, `number`, atau `symbol`).
4. **Flow Partitioning**: Gunakan kontrol percabangan standar (`switch` atau `if`). Compiler menyempitkan tipe pada masing-masing branch.
5. **Exhaustive Guarantee**: Implementasikan penanganan cabang `default` menggunakan variabel bertipe `never`.

---

### 6. Analogy & Diagram ASCII

Bayangkan sistem penyaringan material mineral pada jalur konveyor pemrosesan tambang:

```
Raw Material: [ Emas | Perak | Tembaga | Batu Kerikil ] (unknown/Union)
                           │
                           ▼
                  +------------------+
                  |  Grid Filter 1   | ---> Deteksi "Batu Kerikil" (Non-mineral)
                  |  (Type Guard)    |      [Ditolak / Exception Dilempar]
                  +------------------+
                           │
                           ▼ Lolos (Emas | Perak | Tembaga)
                  +------------------+
                  |  Magnet Separator| ---> Logam Terpisah
                  |  (CFA Branching) |
                  +------------------+
                    /      |       \
                   /       |        \
            [Emas]     [Perak]    [Tembaga]  ---> Tiap jalur memiliki penanganan kimia spesifik
              │            │           │          (Type Narrowed ke tipe tunggal)
              ▼            ▼           ▼
         Smelter A    Smelter B   Smelter C
```

CFA bertindak seperti jalur konveyor cerdas. Begitu suatu material terbukti bukan batu pada *Grid Filter*, material tersebut tidak lagi diperlakukan sebagai batu di titik-titik selanjutnya tanpa perlu diuji ulang.

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Assertion Function & Custom Type Guard

```typescript
// Simple Example: Membedakan HTTP Response
interface HttpResponseSuccess<T> {
  readonly status: "success";
  readonly data: T;
}

interface HttpResponseError {
  readonly status: "error";
  readonly error: {
    readonly code: string;
    readonly message: string;
  };
}

type HttpResponse<T> = HttpResponseSuccess<T> | HttpResponseError;

// Custom Type Guard
function isSuccessResponse<T>(
  response: HttpResponse<T>
): response is HttpResponseSuccess<T> {
  return response.status === "success";
}

// Assertion Function
function assertIsSuccessResponse<T>(
  response: HttpResponse<T>
): asserts response is HttpResponseSuccess<T> {
  if (response.status !== "success") {
    throw new Error(`API Error Encountered: [${response.error.code}] ${response.error.message}`);
  }
}

// Konsumsi CFA
function handleResponse(res: HttpResponse<string[]>): void {
  // Sebelum guard: res adalah HttpResponseSuccess<string[]> | HttpResponseError
  if (isSuccessResponse(res)) {
    // Di dalam blok: res otomatis narrowed ke HttpResponseSuccess<string[]>
    console.log("Data items:", res.data.length);
  } else {
    // Di dalam else: res otomatis narrowed ke HttpResponseError
    console.error("Failed with code:", res.error.code);
  }

  // Menggunakan assertion function
  assertIsSuccessResponse(res);
  // Setelah pemanggilan assertion function, res dijamin HttpResponseSuccess<string[]>
  console.log("Guaranteed Data:", res.data.join(", "));
}
```

#### B. Practical Example: Recursive Schema Narrowing untuk Configuration Parser

```typescript
type JSONPrimitive = string | number | boolean | null;
type JSONObject = { [key: string]: JSONValue };
type JSONArray = JSONValue[];
type JSONValue = JSONPrimitive | JSONObject | JSONArray;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && !Number.isNaN(value);
}

interface DatabaseConfig {
  host: string;
  port: number;
  credentials: {
    user: string;
    sslEnabled: boolean;
  };
}

// Type guard rekursif untuk memvalidasi konfigurasi runtime tanpa skema eksternal
function isDatabaseConfig(value: unknown): value is DatabaseConfig {
  if (!isObject(value)) return false;
  if (!isString(value.host)) return false;
  if (!isNumber(value.port)) return false;

  const creds = value.credentials;
  if (!isObject(creds)) return false;
  if (!isString(creds.user)) return false;
  if (typeof creds.sslEnabled !== "boolean") return false;

  return true;
}

export function loadConfiguration(rawInput: unknown): DatabaseConfig {
  if (!isDatabaseConfig(rawInput)) {
    throw new TypeError("INVALID_CONFIGURATION_STRUCTURE: Payload failed contract check");
  }

  // CFA menjamin rawInput kini berstatus DatabaseConfig murni
  return {
    host: rawInput.host,
    port: rawInput.port,
    credentials: {
      user: rawInput.credentials.user,
      sslEnabled: rawInput.credentials.sslEnabled,
    },
  };
}
```

---

### 8. Real World Case Study: Financial Ledger Event Pipeline

Di sistem Core Banking / Financial Ledger, event stream (Kafka/EventStore) membawa berbagai format mutasi transaksi. Data payload mentah bersifat polimorfik dan wajib diproses secara aman. Kesalahan interpretasi payload dapat menyebabkan salah hitung saldo atau korupsi data pembukuan.

#### Implementasi Ledger Pipeline

```typescript
// domain/ledger-events.ts

export interface BaseEvent {
  readonly eventId: string;
  readonly aggregateId: string;
  readonly timestamp: number;
  readonly version: number;
}

export interface FundsDepositedEvent extends BaseEvent {
  readonly type: "FUNDS_DEPOSITED";
  readonly payload: {
    readonly amountCents: bigint;
    readonly currency: "IDR" | "USD";
    readonly sourceBankCode: string;
  };
}

export interface FundsWithdrawnEvent extends BaseEvent {
  readonly type: "FUNDS_WITHDRAWN";
  readonly payload: {
    readonly amountCents: bigint;
    readonly feeCents: bigint;
    readonly destinationAccountNumber: string;
  };
}

export interface AccountFrozenEvent extends BaseEvent {
  readonly type: "ACCOUNT_FROZEN";
  readonly payload: {
    readonly reasonCode: string;
    readonly authorizedBy: string;
  };
}

// Discriminated Union representasi semua event ledger
export type LedgerEvent =
  | FundsDepositedEvent
  | FundsWithdrawnEvent
  | AccountFrozenEvent;

// domain/ledger-state.ts
export interface AccountLedger {
  readonly accountId: string;
  balanceCents: bigint;
  isFrozen: boolean;
  lastProcessedVersion: number;
}

// utilities/exhaustiveness.ts
export class ExhaustiveMatchError extends Error {
  constructor(value: never) {
    super(`Unhandled discriminate union value encountered: ${JSON.stringify(value)}`);
    this.name = "ExhaustiveMatchError";
  }
}

// pipeline/validator.ts
export function assertLedgerEnvelope(data: unknown): asserts data is Record<string, unknown> & { type: unknown } {
  if (typeof data !== "object" || data === null) {
    throw new Error("MALFORMED_EVENT: Event payload must be a non-null object");
  }
  if (!("type" in data)) {
    throw new Error("MALFORMED_EVENT: Missing discriminatory 'type' property");
  }
}

export function isLedgerEvent(data: unknown): data is LedgerEvent {
  try {
    assertLedgerEnvelope(data);
    const { type } = data;

    if (typeof type !== "string") return false;

    // Verifikasi struktural per event
    switch (type) {
      case "FUNDS_DEPOSITED": {
        const p = data.payload as Partial<FundsDepositedEvent["payload"]> | undefined;
        return typeof p?.amountCents === "bigint" && typeof p?.currency === "string";
      }
      case "FUNDS_WITHDRAWN": {
        const p = data.payload as Partial<FundsWithdrawnEvent["payload"]> | undefined;
        return typeof p?.amountCents === "bigint" && typeof p?.feeCents === "bigint";
      }
      case "ACCOUNT_FROZEN": {
        const p = data.payload as Partial<AccountFrozenEvent["payload"]> | undefined;
        return typeof p?.reasonCode === "string" && typeof p?.authorizedBy === "string";
      }
      default:
        return false;
    }
  } catch {
    return false;
  }
}

// pipeline/ledger-reducer.ts
export function applyLedgerEvent(ledger: AccountLedger, event: LedgerEvent): AccountLedger {
  if (event.version !== ledger.lastProcessedVersion + 1) {
    throw new Error(`CONCURRENCY_ERROR: Version mismatch. Expected ${ledger.lastProcessedVersion + 1}, got ${event.version}`);
  }

  if (ledger.isFrozen && event.type !== "ACCOUNT_FROZEN") {
    throw new Error(`LEDGER_LOCKED: Account is frozen. Operation '${event.type}' rejected.`);
  }

  // Cloning data untuk immutability
  const nextLedger: AccountLedger = { ...ledger };

  // Control Flow Analysis mengevaluasi event.type secara exhaustif
  switch (event.type) {
    case "FUNDS_DEPOSITED":
      // event otomatis narrowed ke FundsDepositedEvent
      nextLedger.balanceCents += event.payload.amountCents;
      break;

    case "FUNDS_WITHDRAWN": {
      // event otomatis narrowed ke FundsWithdrawnEvent
      const totalDebit = event.payload.amountCents + event.payload.feeCents;
      if (nextLedger.balanceCents < totalDebit) {
        throw new Error("INSUFFICIENT_FUNDS: Withdrawal exceeds available balance");
      }
      nextLedger.balanceCents -= totalDebit;
      break;
    }

    case "ACCOUNT_FROZEN":
      // event otomatis narrowed ke AccountFrozenEvent
      nextLedger.isFrozen = true;
      break;

    default:
      // Jika varian baru ditambahkan ke LedgerEvent tanpa case di sini,
      // TypeScript memunculkan compile error karena argumen bukan tipe 'never'.
      throw new ExhaustiveMatchError(event);
  }

  nextLedger.lastProcessedVersion = event.version;
  return nextLedger;
}
```

---

### 9. Trade-offs: Runtime Safety vs Compiler Performance

Membangun arsitektur type guard tingkat lanjut membawa konsekuensi yang harus dievaluasi secara teknis:

| Varian Solusi | Runtime CPU Cost | Compile-time Cost | Scalability | Maintainability |
| :--- | :--- | :--- | :--- | :--- |
| **Simple Type Assertion (`as Event`)** | **0 ms** (dihapus saat transpilasi) | **Sangat Rendah** | Rendah (Silent failure saat data corrupt) | Buruk (Tech debt tinggi) |
| **Manual User-Defined Type Guards** | Rendah (O(1) cek properti dangkal) | **Rendah - Sedang** | Sangat Tinggi (Bagus untuk < 50 union members) | Bagus (Perlu sinkronisasi runtime manual) |
| **Full Schema Parsing (Zod / Typebox)** | Sedang - Tinggi (Deep cloning/parsing) | **Tinggi** (Skema kompleks memperbesar AST checker) | Sedang (Dapat membebani CPU service I/O tinggi) | Sangat Tinggi (Single source of truth) |
| **Large Flat Union (> 100 variants)** | Rendah (Switch O(1) di runtime JS) | **Sangat Tinggi** (CFA checker lambat menelusuri branch) | Rendah (Kompilasi IDE lag) | Sedang |

#### Strategi Mitigasi Masalah Skalabilitas CFA
Jika sebuah union memiliki lebih dari 100 tipe, CFA compiler dapat mengalami degradasi memori eksponensial. Cara mengatasinya:
1. Bagi domain union besar menjadi sub-domains (*hierarchical union*).
2. Hindari evaluasi kondisi bertingkat (*nested ternaries*) pada Union; gunakan indexing map atau `switch` statement yang langsung mendiskriminasi field diskriminator.

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: CFA Hilang Akibat Re-assignment pada Scoped Functions (Closures)
```typescript
// Salah
let activeToken: string | null = "AUTH_TOKEN";

function processToken() {
  if (activeToken !== null) {
    window.setTimeout(() => {
      // Error Compile: Object is possibly 'null'.
      // TS membatalkan narrowing karena activeToken dideklarasikan dengan 'let'
      // dan closure dieksekusi secara asinkron (bisa saja dimutasi oleh code lain).
      console.log(activeToken.toUpperCase());
    }, 100);
  }
}

// Solusi Produksi: Bind ke konstanta lokal (Immutable local snapshot)
function processTokenCorrectly() {
  if (activeToken !== null) {
    const pinnedToken = activeToken; // Immutable local variable
    window.setTimeout(() => {
      console.log(pinnedToken.toUpperCase()); // Sukses: narrowed permanen ke string
    }, 100);
  }
}
```

#### Kasus 2: Type Predicate Berbohong (*Lying Type Guards*)
```typescript
interface UserProfile {
  id: string;
  email: string;
}

// Salah: Menulis predicate tanpa validasi menyeluruh
function isUserProfile(val: unknown): val is UserProfile {
  // Developer hanya mengecek id, tetapi mengklaim val adalah UserProfile lengkap
  return typeof val === "object" && val !== null && "id" in val;
}

const payload: unknown = { id: "usr_102" }; // email tidak ada!
if (isUserProfile(payload)) {
  // Lolos kompilasi tapi throw TypeError di runtime!
  console.log(payload.email.toLowerCase()); 
}

// Solusi Produksi: Validasi seluruh required fields
function isUserProfileStrict(val: unknown): val is UserProfile {
  return (
    typeof val === "object" &&
    val !== null &&
    "id" in val &&
    typeof (val as Record<string, unknown>).id === "string" &&
    "email" in val &&
    typeof (val as Record<string, unknown>).email === "string"
  );
}
```

#### Kasus 3: Property Checking Menggunakan `in` pada Tipe Primitif
```typescript
// Salah
function parseIdentifier(input: unknown) {
  // Runtime TypeError: Cannot use 'in' operator to search for 'id' in 42
  if ("id" in input) {
    console.log(input.id);
  }
}

// Solusi Produksi: Verifikasi tipe object terlebih dahulu
function parseIdentifierStrict(input: unknown) {
  if (typeof input === "object" && input !== null && "id" in input) {
    // Aman secara runtime dan lolos CFA
    console.log((input as { id: unknown }).id);
  }
}
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan `readonly` pada Discriminated Unions**: Pastikan properti diskriminator tidak dapat dimutasi sembarangan setelah diinisialisasi.
- [ ] **Terapkan Exhaustiveness Checking Pattern**: Pasang fungsi assertion `never` di blok default setiap `switch` pernyataan event processing.
- [ ] **Gunakan `const` Declarations**: Hindari `let` untuk data yang membutuhkan penyempitan tipe berantai agar CFA tidak melakukan pembatalan (*invalidation*) narrowing.
- [ ] **Pisahkan Boundary Parsing & Domain Logic**: Jalankan runtime type assertion di gerbang masuk sistem (API Controller / Message Queue Consumer), bukan di dalam core domain logic.
- [ ] **Gunakan Assertion Functions untuk Fail-Fast Pipelines**: Gunakan `asserts data is T` di controller untuk memangkas nesting `if-else` yang tidak perlu.
- [ ] **Hindari Type Casting `as` Tanpa Assertion**: Anggap penggunaan `as Type` sebagai *code smell* kecuali pada unit test mock setup.

---

### 12. Hands-on Practice

Simpan seluruh file berikut ke dalam direktori: `hands-on/m02/`

#### File: `hands-on/m02/package.json`
```json
{
  "name": "m02-cfa-type-guards",
  "version": "1.0.0",
  "description": "Production CFA and Type Guard Enterprise Lab",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "tsc && node dist/index.js"
  },
  "devDependencies": {
    "typescript": "^5.4.0"
  }
}
```

#### File: `hands-on/m02/tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "moduleResolution": "Node",
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "skipLibCheck": true
  },
  "include": ["src/**/*"]
}
```

#### File: `hands-on/m02/src/pipeline.ts`
```typescript
export interface BaseMessage {
  readonly traceId: string;
  readonly createdAt: number;
}

export interface InboundEmailTask extends BaseMessage {
  readonly channel: "EMAIL";
  readonly payload: {
    readonly to: string;
    readonly subject: string;
    readonly body: string;
  };
}

export interface InboundSmsTask extends BaseMessage {
  readonly channel: "SMS";
  readonly payload: {
    readonly phoneNumber: string;
    readonly message: string;
  };
}

export interface InboundWebhookTask extends BaseMessage {
  readonly channel: "WEBHOOK";
  readonly payload: {
    readonly endpointUrl: string;
    readonly headers: Record<string, string>;
    readonly bodyPayload: string;
  };
}

export type NotificationTask =
  | InboundEmailTask
  | InboundSmsTask
  | InboundWebhookTask;

// Exhaustive Check Helper
export function assertExhaustive(x: never): never {
  throw new Error(`CRITICAL: Undefined branch hit in CFA: ${JSON.stringify(x)}`);
}

// Assertion Function
export function assertTaskEnvelope(input: unknown): asserts input is { channel: string; traceId: string } {
  if (typeof input !== "object" || input === null) {
    throw new TypeError("INVALID_PAYLOAD_FORMAT: Must be an object");
  }
  if (!("channel" in input) || typeof (input as Record<string, unknown>).channel !== "string") {
    throw new TypeError("INVALID_PAYLOAD_FORMAT: Field 'channel' is required and must be a string");
  }
  if (!("traceId" in input) || typeof (input as Record<string, unknown>).traceId !== "string") {
    throw new TypeError("INVALID_PAYLOAD_FORMAT: Field 'traceId' is required and must be a string");
  }
}

// User-Defined Type Guard
export function isNotificationTask(input: unknown): input is NotificationTask {
  try {
    assertTaskEnvelope(input);
    const candidate = input as Record<string, unknown>;

    if (typeof candidate.createdAt !== "number") return false;
    if (typeof candidate.payload !== "object" || candidate.payload === null) return false;

    const payload = candidate.payload as Record<string, unknown>;

    switch (candidate.channel) {
      case "EMAIL":
        return (
          typeof payload.to === "string" &&
          typeof payload.subject === "string" &&
          typeof payload.body === "string"
        );
      case "SMS":
        return (
          typeof payload.phoneNumber === "string" &&
          typeof payload.message === "string"
        );
      case "WEBHOOK":
        return (
          typeof payload.endpointUrl === "string" &&
          typeof payload.headers === "object" &&
          typeof payload.bodyPayload === "string"
        );
      default:
        return false;
    }
  } catch {
    return false;
  }
}

// Dispatcher Function
export function dispatchNotification(task: NotificationTask): string {
  switch (task.channel) {
    case "EMAIL":
      return `Email sent to ${task.payload.to} with subject "${task.payload.subject}" [Trace: ${task.traceId}]`;
    case "SMS":
      return `SMS sent to ${task.payload.phoneNumber} [Trace: ${task.traceId}]`;
    case "WEBHOOK":
      return `Webhook dispatched to ${task.payload.endpointUrl} [Trace: ${task.traceId}]`;
    default:
      return assertExhaustive(task);
  }
}
```

#### File: `hands-on/m02/src/index.ts`
```typescript
import { isNotificationTask, dispatchNotification } from "./pipeline";

const incomingPayloads: unknown[] = [
  {
    channel: "EMAIL",
    traceId: "trc-001",
    createdAt: Date.now(),
    payload: {
      to: "admin@enterprise.internal",
      subject: "Node Failure Alert",
      body: "Pod k8s-node-7 offline.",
    },
  },
  {
    channel: "SMS",
    traceId: "trc-002",
    createdAt: Date.now(),
    payload: {
      phoneNumber: "+628123456789",
      message: "Your OTP is 849201",
    },
  },
  {
    channel: "UNKNOWN_CHANNEL",
    traceId: "trc-003",
    createdAt: Date.now(),
    payload: {},
  },
];

for (const raw of incomingPayloads) {
  if (isNotificationTask(raw)) {
    // Di sini raw otomatis narrowed ke tipe NotificationTask
    const result = dispatchNotification(raw);
    console.log(`[SUCCESS]: ${result}`);
  } else {
    console.error(`[REJECTED]: Payload does not conform to NotificationTask schema.`);
  }
}
```

#### Langkah Eksekusi Hands-on:
1. Buat struktur folder:
   ```bash
   mkdir -p hands-on/m02/src
   cd hands-on/m02
   ```
2. Tulis file `package.json`, `tsconfig.json`, `src/pipeline.ts`, dan `src/index.ts`.
3. Pasang dependency dan jalankan pipeline:
   ```bash
   npm install
   npm run start
   ```
4. Verifikasi output: Payload Email dan SMS berhasil diproses, sementara payload ketiga (`UNKNOWN_CHANNEL`) berhasil ditolak secara elegan tanpa throw exception tak terkendali.

---

### 13. Exercise

#### Level: Easy
Diberikan union `type MetricValue = number | string | boolean`. Buat fungsi type guard `isNumericMetric(val: MetricValue): val is number` dan integrasikan ke dalam fungsi konversi data yang mengalikan nilai metrik angka dengan 100, atau mengembalikan `null` jika bukan angka.

#### Level: Medium
Buat assertion function bernama `assertValidPagination(query: Record<string, unknown>): asserts query is { page: number; limit: number }`.
Ketentuan:
1. `page` harus berupa string angka yang dapat diubah ke integer positif (`> 0`).
2. `limit` harus berupa string angka antara `1` dan `100`.
3. Fungsi harus melempar custom error `PaginationValidationError` bila data tidak valid. Tipe `query` setelah eksekusi assertion harus memiliki properti `page` dan `limit` bernilai `number`.

#### Level: Hard
Rancang modul state machine untuk `OrderFulfillmentState`:
- State 1: `DraftOrder` (hanya boleh bertransisi ke `SubmittedOrder`)
- State 2: `SubmittedOrder` (hanya boleh bertransisi ke `PaidOrder` atau `CancelledOrder`)
- State 3: `PaidOrder` (hanya boleh bertransisi ke `ShippedOrder`)
- State 4: `ShippedOrder` (hanya boleh bertransisi ke `DeliveredOrder`)
- State 5: `DeliveredOrder` (state final, tidak bisa transisi lagi)
- State 6: `CancelledOrder` (state final, tidak bisa transisi lagi)

Implementasikan generic state machine dispatcher menggunakan Custom Type Guards dan CFA di mana pemanggilan fungsi `transitionTo(currentState, targetState)` menghasilkan compile-time error jika transisi dilarang oleh domain rules.

---

### 14. Challenge

**Studi Kasus**: High-Performance Real-Time Trading Gateway Serialization Guard

Di sebuah bursa efek berlatensi rendah, sistem menerima payload transaksi dalam format stream buffer biner tak beraturan yang telah diurai menjadi objek JSON flat. Sistem Anda memiliki 4 jenis order union:
1. `LimitOrder`
2. `MarketOrder`
3. `StopLossOrder`
4. `TrailingStopOrder`

**Tantangan Arsitektur**:
1. Buat discriminated union lengkap dengan atribut unik non-overlapping untuk masing-masing tipe order.
2. Buat hierarki type guard tanpa menggunakan library eksternal (murni native TypeScript). Validasi harus memeriksa integritas relasi matematika (misal: pada `LimitOrder`, `price` harus `> 0`, sedangkan pada `MarketOrder`, field `price` tidak boleh ada atau wajib `undefined`).
3. Buat assertion function yang memvalidasi *batch array* order campuran (`unknown[]`) dan mengembalikannya sebagai tuple readonly terpartisi `[LimitOrder[], MarketOrder[], StopLossOrder[], TrailingStopOrder[]]` dalam satu traversal pass tunggal ($O(N)$), memanfaatkan CFA narrowing di dalam array accumulator.
4. **Target Ekstrem**: Pastikan tidak ada satupun type assertion (`as`) yang digunakan di dalam fungsi kompilasi partitioner array Anda. Semua penyempitan harus murni hasil evaluasi Control Flow Analysis TypeScript.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. Apa output compile-time dari statement assertion function `asserts val is string` jika fungsi tersebut selesai dieksekusi tanpa throw error?
   - A. Nilai `val` diubah menjadi tipe `any`.
   - B. Nilai `val` dihapus dari memory stack.
   - C. Compiler menyempitkan tipe `val` menjadi `string` pada baris-baris instruksi setelahnya.
   - D. Runtime mengonversi tipe data secara otomatis menggunakan `String(val)`.

2. Mengapa variabel bertipe `let` yang telah di-narrowing di luar closure seringkali kehilangan status narrowing-nya di dalam nested callback function?
   - A. Karena compiler TypeScript memiliki bug alokasi memori.
   - B. Karena TypeScript mengasumsikan variabel `let` dapat bermutasi secara asinkron sebelum closure dieksekusi.
   - C. Karena closure di JavaScript tidak mendukung tipe data union.
   - D. Karena tipe `unknown` tidak dapat diwariskan ke dalam fungsi anak.

3. Komponen internal TypeScript compiler manakah yang bertanggung jawab membangun node graf alur (*FlowNodes*)?
   - A. Emitter
   - B. Scanner
   - C. Binder
   - D. Transformer

4. Nilai balik (*return value*) apa yang wajib dimiliki oleh fungsi Custom Type Guard standar?
   - A. `boolean`
   - B. `val is T` (yang dievaluasi sebagai predikat boolean di runtime)
   - C. `void`
   - D. `never`

5. Apa fungsi dari klausa `assertExhaustive(x: never): never` pada blok default switch-case?
   - A. Menghapus log error pada aplikasi di level runtime.
   - B. Memastikan kompilasi gagal jika terdapat varian dari Discriminated Union yang belum ditangani di blok case.
   - C. Mempercepat waktu eksekusi kode JavaScript di browser engine.
   - D. Mengubah object JSON menjadi format biner secara otomatis.

---

#### Bagian 2: Intermediate (Pilihan Ganda)

6. Diberikan kode berikut:
   ```typescript
   function process(input: string | number) {
     if (typeof input === "string") {
       input = 100;
       // Baris X: Tipe input di sini menurut CFA adalah?
     }
   }
   ```
   Apakah tipe data `input` pada `Baris X`?
   - A. `string`
   - B. `number`
   - C. `string | number`
   - D. `never`

7. Manakah representasi yang benar dari penulisan type guard untuk memvalidasi bahwa suatu interface adalah array yang berisi minimal satu elemen string?
   - A. `function isValid(val: unknown): val is [string, ...string[]]`
   - B. `function isValid(val: unknown): val is Array<any>`
   - C. `function isValid(val: unknown): asserts val is string[]`
   - D. `function isValid(val: unknown): val is string`

8. Apa dampak arsitektural kompilasi jika sebuah proyek enterprise memiliki recursive union type guard yang terlalu dalam dan melibatkan ratusan persimpangan conditional?
   - A. File bundle JavaScript runtime membengkak secara eksponensial.
   - B. Type checking latency compiler melonjak drastis, memicu error `JavaScript heap out of memory`.
   - C. Engine V8 menolak mengeksekusi bytecode JavaScript yang dihasilkan.
   - D. TypeScript mengubah seluruh tipe menjadi `never` secara sepihak.

9. Kapan kita sebaiknya memilih `Assertion Function` (`asserts x is T`) dibandingkan `Type Guard` biasa (`x is T`)?
   - A. Saat kita membutuhkan operasi pengembalian nilai boolean murni untuk ternary operator.
   - B. Saat kita ingin membangun flow program yang *fail-fast* dengan melempar error langsung jika kontrak data tidak terpenuhi, sehingga menghindari lekukan (*indentation*) blok `if-else`.
   - C. Saat kita bekerja dengan library eksternal yang tidak memiliki type definition.
   - D. Assertion function hanya boleh digunakan di dalam unit testing framework, bukan di kode produksi.

10. Bagaimana CFA memproses pengecekan properti diskriminator menggunakan operator `in` jika tipe dasarnya adalah `unknown`?
    - A. Langsung mengizinkan narrowed tipe tanpa error.
    - B. Melempar compile error, karena operator `in` membutuhkan tipe data objek yang valid (bukan `null`, `undefined`, atau primitif).
    - C. Mengubah tipe `unknown` menjadi `any`.
    - D. Menjalankan bypass type check.

---

#### Bagian 3: Skenario Kasus Produksi

11. **Skenario Sistem Billing**:
    Sebuah microservice pembayaran menangani dua skema payload mutasi dari Stripe webhook: `InvoicePaymentFailed` dan `InvoicePaymentSucceeded`. Seorang engineer menggunakan operator casting:
    ```typescript
    const event = req.body as InvoicePaymentFailed;
    sendFailureNotification(event.customerEmail);
    ```
    Di production, event bertipe `InvoicePaymentSucceeded` masuk, di mana properti `customerEmail` berada di sub-objek yang berbeda (`event.data.customerEmail`), menyebabkan notifikasi dikirim dengan alamat `undefined`.
    **Pertanyaan**: Bagaimana Anda merevisi arsitektur parsing handler tersebut menggunakan CFA dan Discriminated Union tanpa mengubah business logic handler notifikasi?

12. **Skenario Performance Bottleneck**:
    Sebuah framework internal perusahaan mendefinisikan tipe `ASTNode` dengan 140 varian class node yang digabung dalam satu tipe union (`type AnyASTNode = NodeA | NodeB | ... Node140`). Setiap kali engineer memanggil visitor function berbasis `if (node.type === "...")`, IDE mengalami freeze selama 3 detik, dan `tsc --noEmit` memakan waktu 45 detik.
    **Pertanyaan**: Berdasarkan cara kerja internal *Flow Graph* dan *Branch Convergence*, identifikasi penyebab utama masalah ini dan ajukan solusi perbaikan arsitektur tipenya.

13. **Skenario SDK Validation**:
    Anda sedang merancang SDK TypeScript untuk public client. Pengguna SDK sering memasukkan konfigurasi yang salah saat runtime:
    ```typescript
    initClient({ timeoutMs: "5000" }); // Seharusnya number
    ```
    Jika menggunakan Zod, bundle size SDK Anda akan naik sebesar 45KB (terlalu besar untuk standar SDK web ultra-lightweight yang ditargetkan di bawah 5KB).
    **Pertanyaan**: Desainlah sebuah arsitektur lightweight type guard & assertion framework murni (zero-dependency) yang memberikan pesan diagnostik error detail (*path & field mismatch*) saat runtime sekaligus memberikan garansi narrowed type di sisi compiler bagi consumer SDK Anda.

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **C** — Assertion function menyempitkan tipe identifier di alur kontrol baris-baris setelahnya bila tidak terjadi exception.
2. **B** — TypeScript bersikap konservatif terhadap variabel yang dideklarasikan dengan `let` karena ada kemungkinan nilainya dimutasi oleh operasi asynchronous lain sebelum closure dieksekusi.
3. **C** — *Binder* adalah fase internal compiler yang bertugas membentuk rantai *FlowNode* dan *FlowGraph*.
4. **B** — Tipe predikat khusus `val is T` yang dievaluasi menjadi nilai boolean saat runtime.
5. **B** — Tipe `never` hanya dapat menerima assignable type `never`. Jika ada union yang terlewat, compiler akan mengeluarkan error karena tipe varian yang tersisa tidak dapat di-assign ke `never`.

#### Bagian 2: Intermediate
6. **B** — CFA melacak assignment lokal. Segera setelah `input = 100`, simpul alur berganti menjadi `FlowFlags.Assignment` dengan tipe literal `100` atau tipe `number`.
7. **A** — `[string, ...string[]]` adalah tipe tuple yang merepresentasikan array dengan minimal satu elemen string (*non-empty array*).
8. **B** — Checker harus menghitung kombinasi alur cabang (*branch labels*) secara mendalam. Rantai yang terlalu kompleks menyebabkan ledakan kombinatorial tipe (*combinatorial explosion*), menghabiskan alokasi memori compiler.
9. **B** — Assertion function cocok untuk pendekatan arsitektur *fail-fast* yang membersihkan nesting `if` percabangan di level controller/ingestion.
10. **B** — Operator `in` tidak dapat diaplikasikan pada tipe `unknown` sebelum dipastikan bahwa data tersebut adalah objek (`typeof input === "object" && input !== null"`).

#### Bagian 3: Solusi Kasus Produksi
11. **Solusi Billing**: Hapus operator `as`. Definisikan `StripeEvent = InvoicePaymentFailed | InvoicePaymentSucceeded` dengan field diskriminator `type`. Implementasikan assertion function `assertIsStripeEvent(req.body)` di boundary layer. Lakukan branching via `switch (event.type)`. Letakkan `sendFailureNotification` hanya di blok case `INVOICE_PAYMENT_FAILED`.
12. **Solusi Bottleneck**: Penyebabnya adalah *combinatorial union distribution* saat checker menelusuri 140 simpul antecedent secara berulang pada percabangan linier. Solusi: Buat pengelompokan hierarkis (*Hierarchical Discriminator Unions*), misalnya membagi 140 node ke dalam 5 kategori besar (`StatementNode | ExpressionNode | DeclarationNode | ...`), lalu cek kategori induk terlebih dahulu sebelum masuk ke sub-varian node.
13. **Solusi SDK**: Buat abstraction builder `createValidator<T>()` berbasis *Structural User-Defined Type Guards* murni TypeScript. Gunakan lightweight runtime inspection: sebuah fungsi utilitas berukuran <1KB yang melakukan rekursi traversal objek dengan mengecek `typeof` dan mendaftarkan invalid path ke dalam array string `errors: string[]`. Lemparkan custom exception `SDKConfigValidationError` yang menggabungkan seluruh path yang bermasalah.

---

### 16. Summary

- **CFA Engine**: Control Flow Analysis TypeScript mengandalkan graf berarah (*FlowNodes*) yang dibangun oleh *Binder* dan dievaluasi mundur oleh *Checker* untuk menyempitkan tipe secara kontekstual.
- **Predikat Struktural**: Custom Type Guards (`val is T`) dan Assertion Functions (`asserts val is T`) adalah jembatan penghubung antara validasi runtime JavaScript murni dan sistem tipe compile-time TypeScript.
- **Exhaustiveness Testing**: Pola pemanfaatan tipe `never` pada cabang percabangan tak tertangani menjamin integritas penambahan model data baru pada arsitektur berbasis event (*Event-Driven Architecture*).
- **Immutability Is Key**: CFA bekerja paling optimal pada variabel referensi konstan (`const`) dan struktur data `readonly`. Hindari mutasi variabel lokal agar narrowing alur tidak dibatalkan (*invalidated*) oleh compiler.