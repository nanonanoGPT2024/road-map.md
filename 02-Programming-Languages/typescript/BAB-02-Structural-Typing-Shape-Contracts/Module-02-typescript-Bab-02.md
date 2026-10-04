# TypeScript Enterprise Architecture: Structural Typing & Shape Contracts

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis dan Membedah Internal Compiler TypeScript:** Memahami algoritma *structural assignability*, *type checking relations* (`isTypeRelatedTo`), serta mekanisme *Type Cache* pada TypeScript engine (`checker.ts`).
- **Menguasai Mekanika Subtyping Kompleks:** Mengidentifikasi dan memitigasi anomali perilaku antara *Width Subtyping*, *Depth Subtyping*, dan *Excess Property Checks* (EPC).
- **Mengimplementasikan Nominal Typing Zero-Cost:** Merancang dan menerapkan abstraksi *Branded Types* / *Flavored Types* untuk mencegah *primitive obsession* dan menjamin *type safety* pada Domain-Driven Design (DDD).
- **Membangun Arsitektur Kontrak API Enterprise:** Mengintegrasikan validasi bentuk (*shape contracts*) antara lapisan compile-time statis dengan runtime boundary assertion (menggunakan Zod/TypeBox) guna memitigasi risiko *type-drift*.
- **Mengoptimalkan Kinerja Type Checker:** Mengurangi degradasi kompilasi (`tsc --extendedDiagnostics`) yang diakibatkan oleh rekursi structural checking yang terlalu dalam.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
1. **Dasar Ekosistem TypeScript:** Konfigurasi `tsconfig.json` (`strict: true`, `noImplicitAny`, dsb.).
2. **Type System Fundamentals:** Primitif, interfaces, type aliases, union & intersection types.
3. **Konsep OOP Dasar:** Pewarisan kelas, enkapsulasi, polimorfisme nominal (standar C#/Java).
4. **JavaScript Runtime Internals:** Eksekusi prototype chain, memory references, dan object mutation semantics.

---

## 3. Concept & Internal Architecture

### 3.1. Hakikat Structural Type System
TypeScript didesain dengan landasan **Structural Type System** (sering disebut *Shape-based Type System*), berbeda fundamental dengan bahasa seperti Java, C#, atau Rust yang mengadopsi **Nominal Type System**. 

Dalam sistem nominal, ekivalensi tipe ditentukan secara eksplisit melalui deklarasi nama dan relasi hierarkinya (`class Cat extends Animal`). Sebaliknya, dalam sistem struktural, kesetaraan tipe dievaluasi murni berdasarkan **isi, struktur properti, dan kapabilitas shape** dari tipe tersebut:

$$\text{Tipe } B \text{ kompatibel dengan tipe } A \iff \forall (k \in \operatorname{props}(A)): \operatorname{type}(B.k) \subseteq \operatorname{type}(A.k)$$

```
Nominal Typing:    "Siapa namamu?" -> Terdaftar di silsilah keluarga yang tepat?
Structural Typing: "Apa saja metodemu?" -> Memiliki properti dan bentuk yang sesuai?
```

### 3.2. TypeScript Compiler Internals (`checker.ts`)
Di dalam codebase compiler TypeScript (`src/compiler/checker.ts`), proses verifikasi assignment tipe target ($T$) dan tipe sumber ($S$) berjalan melalui alur terstruktur:

1. **Relation Checking (`checkTypeRelatedTo`):** Compiler mengevaluasi apakah $S$ dapat di-*assign* ke $T$ berdasarkan relasi `assignableToRelation`.
2. **Identity & Fast-Path Matching:** Verifikasi awal pointer referensi ID tipe; jika `S === T`, assignability bernilai `true`.
3. **Structural Recursion Loop:**
   - Compiler mengekstraksi seluruh properti publik yang dideklarasikan pada $T$ (`getPropertiesOfType(T)`).
   - Untuk setiap properti $p \in T$, compiler mencari properti pencocok $p' \in S$.
   - **Width Subtyping Validation:** Jika terdapat properti wajib di $T$ yang absen di $S$, compiler mencatat error.
   - **Depth Subtyping Validation:** Compiler memanggil rekursi `checkTypeRelatedTo(S[p'], T[p])`. Jika tipe properti anak tidak kompatibel secara variansi, type checking gagal.
4. **Caching Subsystem:** Compiler menyimpan tuple `(sourceId, targetId, relation)` di dalam `relationCache` internal untuk mencegah rekursi eksponensial dan mendeteksi dependensi melingkar (*circular type dependencies*).

### 3.3. Dualitas: Excess Property Checking (EPC) vs. Structural Assignability
Paradoks yang sering membingungkan engineer adalah keberadaan **Excess Property Checks**:
- Secara murni, structural subtyping memvalidasi bahwa suatu tipe diizinkan memiliki *lebih banyak* properti daripada targetnya (*width subtyping*).
- Namun, TypeScript sengaja menyisipkan exception: **Fresh Object Literal Assignment**. 

Jika sebuah objek dibuat secara *fresh* (sebagai *Object Literal* langsung tanpa perantara variabel), compiler berasumsi bahwa penyertaan properti asing yang tidak terdaftar pada tipe target adalah sebuah *bug* ketik (typo) atau kesalahan konseptual, sehingga memicu compile-time error.

```
Fresh Object Literal Assignment -> Excess Property Checking AKTIF (Non-permissive)
Variable Reference Assignment   -> Pure Structural Subtyping AKTIF (Permissive)
```

---

## 4. Why & What

| Dimensi | Nominal Type System (C#, Java) | Duck Typing (Python, JS Runtime) | Compile-time Structural Typing (TypeScript) |
| :--- | :--- | :--- | :--- |
| **Evaluasi Kesetaraan** | Berdasarkan Nama/Deklarasi | Berdasarkan Pemanggilan Runtime | Berdasarkan Struktur Bentuk (Compile-time) |
| **Safety Timing** | Kompilasi | Runtime (dapat memicu crash) | Kompilasi murni |
| **Flexibility** | Kaku, butuh adapter pattern eksplisit | Sangat tinggi, rawan error | Fleksibel tanpa boilerplate berlebih |
| **Overhead Runtime** | Ada (Rtti, vtables, metadata) | Ada (runtime reflection/resolution) | **Nol (Zero Runtime Overhead)** |
| **Cocok Untuk** | Closed-world enterprise monolit | Rapid prototyping dynamic scripting | Open-world web APIs, distributed microservices |

### Alasan Desain TypeScript Memilih Structural
Web didominasi oleh protokol data tanpa status (JSON via REST/GraphQL) di mana payload tidak membawa metadata tipe nominal. Data datang dalam bentuk *raw structured shapes*. Menggunakan sistem struktural memungkinkan TypeScript memodelkan data eksternal secara natural tanpa harus memaksa instansiasi kelas melalui reflection atau manual mapping berulang.

---

## 5. How (Workflow Detail Engine)

Alur verifikasi kompatibilitas bentuk (*Shape Compatibility Resolution Workflow*):

```
[Start Assignability Check: S assignable to T?]
                   │
                   ▼
       Is S and T identically equal?
        ├── YES ──> [RETURN TRUE: Assignable]
        └── NO
             │
             ▼
    Is S an Object Literal Expression? (Freshness Check)
        ├── YES ──> Are there properties in S NOT present in T?
        │               ├── YES ──> [FAIL: Excess Property Error]
        │               └── NO  ──> (Lanjut ke Deep Structural Verification)
        └── NO  ──> (Bypass EPC, Lanjut ke Deep Structural Verification)
                         │
                         ▼
        Get all required properties of T: props(T)
                         │
                         ▼
             For each prop 'p' in props(T):
            Does 'p' exist in S?
             ├── NO  ──> [FAIL: Property Missing in S]
             └── YES ──> Is S[p] assignable to T[p]?
                           ├── NO  ──> [FAIL: Depth Type Incompatibility]
                           └── YES ──> Next property
                                         │
                                         ▼
                             All properties checked?
                                         │
                                       [PASS]
```

---

## 6. Analogy & Diagram ASCII

### Analogi Colokan Listrik (Wall Socket)
- **Nominal Typing:** Seperti colokan berlabel resmi *Standard IEC Type G* yang hanya menerima steker bersertifikat pabrikan yang sama. Jika Anda membawa steker dengan pin yang identik tetapi tidak memiliki sertifikasi bertuliskan merek tersebut, sistem menolaknya.
- **Structural Typing:** Soket hanya peduli pada **ukuran pin, jarak antar pin, dan voltase**. Jika steker Anda memiliki 3 pin dengan jarak 22mm dan tahan 230V, steker tersebut kompatibel—tidak peduli apa merek yang tercetak di atasnya.
- **Excess Property Checking:** Anda membawa steker yang pas, tetapi di sisinya ada tonjolan plastik ekstra yang tidak ada gunanya. Jika Anda mendesainnya langsung di tempat (literal), inspektur menegur: *"Mengapa menambahkan tonjolan ini? Apakah Anda salah desain?"*.

```
Tipe Target (T):               Tipe Sumber (S):
┌────────────────────┐         ┌────────────────────┐
│ Interface: Payment │         │ Object: UserPayload│
├────────────────────┤         ├────────────────────┤
│ id: string         │ <───────│ id: string         │  (Compatible)
│ amount: number     │ <───────│ amount: number     │  (Compatible)
└────────────────────┘         │ metadata: object   │  (Width subtyping:
                               └────────────────────┘   Ignored in assignments)
```

---

## 7. Simple & Practical Examples

### 7.1. Simple Example: Width Subtyping & Excess Property Traps
Melihat perbedaan perilaku assignability pada Fresh Literals vs Assigned Identifiers:

```typescript
interface DatabaseRecord {
  id: string;
  createdAt: Date;
}

// 1. Structural Match yang Diizinkan (Width Subtyping melalui Reference)
const userPayload = {
  id: "usr_9981",
  createdAt: new Date(),
  extraFieldAudit: "192.168.1.1", // Properti ekstra
};

// Valid: userPayload memiliki properti yang disyaratkan oleh DatabaseRecord
const recordA: DatabaseRecord = userPayload; 

// 2. Excess Property Check Error (Fresh Object Literal)
// Error: Type '{ id: string; createdAt: Date; extraFieldAudit: string; }' is not assignable to type 'DatabaseRecord'.
// Object literal may only specify known properties, and 'extraFieldAudit' does not exist in type 'DatabaseRecord'.
const recordB: DatabaseRecord = {
  id: "usr_9982",
  createdAt: new Date(),
  extraFieldAudit: "192.168.1.1",
};
```

### 7.2. Practical Example: Mengemulasikan Nominal Safety Menggunakan Branded Types
Mencegah bug fatal di mana dua ID bertipe primitif sama (`string`) tertukar secara tidak sengaja pada lapisan query domain.

```typescript
// Core Branding Engine
declare const __brand: unique symbol;

export type Brand<T, TBrand extends string> = T & {
  readonly [__brand]: TBrand;
};

// Domain Primitives
export type OrderId = Brand<string, "OrderId">;
export type UserId = Brand<string, "UserId">;
export type UsdCents = Brand<number, "UsdCents">;

// Constructor Functions / Assertions
export function makeOrderId(raw: string): OrderId {
  if (!raw.startsWith("ord_")) {
    throw new Error(`Invalid OrderId format: ${raw}`);
  }
  return raw as OrderId;
}

export function makeUserId(raw: string): UserId {
  if (!raw.startsWith("usr_")) {
    throw new Error(`Invalid UserId format: ${raw}`);
  }
  return raw as UserId;
}

export function makeUsdCents(val: number): UsdCents {
  if (!Number.isInteger(val) || val < 0) {
    throw new Error(`Invalid Cents amount: ${val}`);
  }
  return val as UsdCents;
}

// Enterprise Service Layer
interface OrderProcessingService {
  cancelOrder(orderId: OrderId, requestedBy: UserId): Promise<void>;
  refund(orderId: OrderId, amount: UsdCents): Promise<void>;
}

export class ProductionOrderService implements OrderProcessingService {
  async cancelOrder(orderId: OrderId, requestedBy: UserId): Promise<void> {
    console.log(`Cancelling order ${orderId} by user ${requestedBy}`);
  }

  async refund(orderId: OrderId, amount: UsdCents): Promise<void> {
    console.log(`Refunding ${amount} cents for order ${orderId}`);
  }
}

// Simulasi Konsumsi API
const svc = new ProductionOrderService();
const orderId = makeOrderId("ord_12345");
const userId = makeUserId("usr_67890");
const amount = makeUsdCents(5000);

// Skenario Sukses
await svc.cancelOrder(orderId, userId);

// Skenario Error Kompilasi (Mencegah Salah Urutan Argumen):
// Argument of type 'UserId' is not assignable to parameter of type 'OrderId'.
// Type 'UserId' is not assignable to type '{ readonly [__brand]: "OrderId"; }'.
// await svc.cancelOrder(userId, orderId); // COMPILE ERROR!
```

---

## 8. Real-World Case Study: Enterprise Financial Ledger Engine

### Konteks
Sebuah platform fintech memproses transaksi pembayaran multi-tenant. Masalah krusial muncul: data JSON dari payment gateway pihak ketiga sering kali bermutasi, memicu *silent failure* karena TypeScript meloloskan objek mutan berlebih (*structural leakage*) langsung ke database column tanpa validasi bentuk yang presisi.

### Solusi Arsitektur
Menerapkan kombinasi **Strict Contract Boundary Layer** (menggunakan *Exhaustive Shape Mapping*) dan **Branded Types** untuk integritas ledger internal.

```typescript
// 1. External Third-Party Boundary (Open Shape)
export interface StripeRawWebhookPayload {
  id: string;
  object: string;
  amount: number;
  currency: string;
  customer?: string;
  [key: string]: unknown; // Mengakomodasi dynamic shape eksternal
}

// 2. Domain Branded Primitives
export type TenantId = Brand<string, "TenantId">;
export type LedgerEntryId = Brand<string, "LedgerEntryId">;
export type CurrencyCode = "USD" | "EUR" | "IDR";

// 3. Domain Model Murni (Strict Shape Contract)
export interface LedgerTransaction {
  readonly entryId: LedgerEntryId;
  readonly tenantId: TenantId;
  readonly externalReferenceId: string;
  readonly grossAmount: number;
  readonly currency: CurrencyCode;
  readonly executedAt: Date;
}

// 4. Utility untuk Memaksa Strict Checking (Anti-Leakage Utility)
export type Exact<T, Shape> = T extends Shape
  ? Exclude<keyof T, keyof Shape> extends never
    ? T
    : never
  : never;

// 5. Anti-Corruption Layer (ACL) Mapper
export class LedgerDomainMapper {
  public static toDomainEntity(
    tenantId: TenantId,
    payload: StripeRawWebhookPayload
  ): LedgerTransaction {
    // Memastikan payload eksternal di-sanitasi dan dipetakan secara eksplisit
    if (payload.currency.toUpperCase() !== "USD") {
      throw new Error(`Unsupported currency: ${payload.currency}`);
    }

    return {
      entryId: (crypto.randomUUID()) as LedgerEntryId,
      tenantId,
      externalReferenceId: payload.id,
      grossAmount: payload.amount,
      currency: payload.currency.toUpperCase() as CurrencyCode,
      executedAt: new Date(),
    };
  }

  // Enforce zero-leakage pada sinkronisasi output
  public static validateStrictShape<T>(
    input: Exact<T, LedgerTransaction>
  ): LedgerTransaction {
    return input;
  }
}
```

---

## 9. Trade-Offs & Architectural Decisions

```
               TRADE-OFF SPECTRUM: SAFETY VS. PERFORMANCE
  Nominal Mimicking                                  Pure Structural
┌───────────────────────────┐                      ┌───────────────────────────┐
│ Branded Types / Zod Parse │                      │ Plain Interfaces / Types  │
├───────────────────────────┤                      ├───────────────────────────┤
│ + Zero ID Swapping bugs   │                      │ + Maximum Compilation Spd │
│ + Enforced Domain Rules   │                      │ + Low Boilerplate         │
│ - Compilation Memory (O(N))                      │ - Type Smuggling / Leaks  │
│ - Inconvenient Serialization                     │ - Silent Typos on Assign  │
└───────────────────────────┘                      └───────────────────────────┘
```

### 1. Soundness vs. Completeness
TypeScript secara eksplisit **tidak 100% sound** secara matematis. TypeScript mengorbankan *soundness* demi interoperabilitas praktis dengan ekosistem JavaScript yang dinamis. 
- *Contoh:* Array mutation variance bersifat *bivariant* secara historis pada method parameters.
- *Dampak:* Developer harus sadar bahwa status "Lolosan Type Checking" tidak menjamin 100% bebas runtime exceptions jika boundary eksternal tidak dijaga.

### 2. Compile-Time Memory vs. Deep Type Inspection
Membuat utility types seperti `Exact<T, Shape>` atau `DeepBrand<T>` yang melakukan evaluasi rekursif menyeluruh akan menaikkan alokasi memori compiler secara signifikan.
- Untuk aplikasi enterprise raksasa (>500.000 lines of code), implementasi `Exact<T>` pada seluruh DTO dapat memperlambat proses `tsc --build` hingga 3x lipat akibat *relation cache busting*.

---

## 10. Common Mistakes & Troubleshooting

### Anti-Pattern 1: Excess Property Erasure Melalui Indirection Variable
Banyak developer mengira TypeScript selalu menolak properti berlebih:

```typescript
interface CreateUserInput {
  name: string;
  email: string;
}

function registerUser(input: CreateUserInput) {
  // Database INSERT mutation di sini...
}

// KESALAHAN:
const payloadFromOutside = {
  name: "Budi",
  email: "budi@enterprise.com",
  isAdmin: true, // Properti berbahaya diselundupkan!
};

// TypeScript meloloskan ini tanpa komplain! (Bypassing EPC)
registerUser(payloadFromOutside);
```

**Solusi & Troubleshooting:**
Jika method Anda sensitif terhadap properti berlebih (misalnya diteruskan langsung ke MongoDB/ORM update query), gunakan helper generic check atau runtime stripping:

```typescript
function registerUserStrict<T extends CreateUserInput>(
  input: T & Record<Exclude<keyof T, keyof CreateUserInput>, never>
) {
  // Kompiler akan melempar error jika ada properti ekstra di tipe variabel T
}
```

### Anti-Pattern 2: Structural Collisions Antara Dua Domain Terpisah
Dua model berbeda secara konseptual memiliki bentuk properti yang sama persis secara kebetulan:

```typescript
type GeoCoordinate = { x: number; y: number };
type Vector2D = { x: number; y: number };

let point: GeoCoordinate = { x: 106.8456, y: -6.2088 };
let velocity: Vector2D = { x: 50, y: 0 };

// Bencana Tersembunyi: Valid secara struktural, fatal secara domain!
point = velocity; 
```

**Solusi & Troubleshooting:**
Terapkan *Nominal Tagging* via Branding pada domain primitives tersebut.

---

## 11. Best Practices (Production Checklist)

1. [ ] **Aktifkan `strict: true` pada `tsconfig.json`:** Pastikan `strictNullChecks` dan `noImplicitAny` aktif agar pengecekan relasi bentuk tidak runtuh karena nilai `null` atau `undefined` implisit.
2. [ ] **Terapkan Boundary Isolation:** Jangan izinkan interface dari *database layer* (e.g., Prisma models) bocor menjadi shape contract di *presentation/controller layer*. Pisahkan via explicit DTO mapping.
3. [ ] **Gunakan Branded Types untuk Domain Identifiers:** Terapkan branding untuk `UUID`, `CUID`, `EmailAddress`, dan `MoneyAmount` guna mencegah *argument swapping*.
4. [ ] **Bakar Validasi di Batas Runtime:** TypeScript type hilang di runtime. Gunakan parser (seperti Zod/Valibot) yang selaras dengan shape contract untuk data eksternal (REST requests, Message Broker payloads).
5. [ ] **Hindari Penggunaan `any` untuk Menembus Ketidakcocokan Bentuk:** Gunakan `unknown` dan type narrowing guards (`typeof`, `in`, `instanceof`, user-defined type guards) daripada melempar type safety keluar dari jendela.
6. [ ] **Audit Performa Type Compiler:** Jalankan `tsc --noEmit --extendedDiagnostics` di CI/CD. Pastikan metrik "Check time" dan "Instantiations" tidak melonjak drastis setelah penambahan utility types baru.

---

## 12. Hands-on Practice

Implementasikan struktur file berikut di folder `hands-on/m02/` pada environment lokal Anda:

### Struktur Direktori:
```
hands-on/m02/
├── package.json
├── tsconfig.json
└── src/
    ├── types/
    │   └── branding.ts
    ├── domain/
    │   └── billing.ts
    └── index.ts
```

### Langkah 1: Inisialisasi Project & Konfigurasi
Jalankan di terminal:
```bash
mkdir -p hands-on/m02/src/types hands-on/m02/src/domain
cd hands-on/m02
npm init -y
npm install -D typescript tsx @types/node
```

Buat `hands-on/m02/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "exactOptionalPropertyTypes": true,
    "noUncheckedIndexedAccess": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"]
}
```

### Langkah 2: Implementasi Branding Subsystem
Tuliskan di `src/types/branding.ts`:
```typescript
declare const BrandTag: unique symbol;

export type Branded<T, TBrand extends string> = T & {
  readonly [BrandTag]: TBrand;
};

export type AccountId = Branded<string, "AccountId">;
export type MonetaryUnits = Branded<bigint, "MonetaryUnits">;

export function parseAccountId(id: string): AccountId {
  if (!id.match(/^acc_[a-z0-9]{8}$/)) {
    throw new Error(`Format ID Akun tidak valid: ${id}`);
  }
  return id as AccountId;
}

export function parseMonetaryUnits(units: bigint): MonetaryUnits {
  if (units < 0n) {
    throw new Error("Unit moneter tidak boleh negatif.");
  }
  return units as MonetaryUnits;
}
```

### Langkah 3: Domain Entity & Strict Verification
Tuliskan di `src/domain/billing.ts`:
```typescript
import { AccountId, MonetaryUnits } from "../types/branding.js";

export interface AccountLedger {
  readonly id: AccountId;
  readonly balance: MonetaryUnits;
}

export function transferFunds(
  source: AccountLedger,
  destination: AccountLedger,
  amount: MonetaryUnits
): { updatedSource: AccountLedger; updatedDestination: AccountLedger } {
  if (source.balance < amount) {
    throw new Error("Saldo tidak mencukupi untuk transfer.");
  }

  const updatedSource: AccountLedger = {
    id: source.id,
    balance: (source.balance - amount) as MonetaryUnits,
  };

  const updatedDestination: AccountLedger = {
    id: destination.id,
    balance: (destination.balance + amount) as MonetaryUnits,
  };

  return { updatedSource, updatedDestination };
}
```

### Langkah 4: Runtime Execution & Validation
Tuliskan di `src/index.ts`:
```typescript
import { parseAccountId, parseMonetaryUnits } from "./types/branding.js";
import { AccountLedger, transferFunds } from "./domain/billing.js";

function main() {
  console.log("=== ENTERPRISE LEDGER SYSTEM ENGINE ===");

  const accSource: AccountLedger = {
    id: parseAccountId("acc_1234abcd"),
    balance: parseMonetaryUnits(100_000n),
  };

  const accDest: AccountLedger = {
    id: parseAccountId("acc_5678efgh"),
    balance: parseMonetaryUnits(20_000n),
  };

  const transferAmount = parseMonetaryUnits(50_000n);

  console.log("Status Awal:", { accSource, accDest });

  const result = transferFunds(accSource, accDest, transferAmount);

  console.log("Status Akhir:", {
    sourceBalance: result.updatedSource.balance.toString(),
    destBalance: result.updatedDestination.balance.toString(),
  });
}

main();
```

Jalankan:
```bash
npx tsx src/index.ts
```

---

## 13. Exercises

### Level Easy
Diberikan interface `UserConfig` berikut:
```typescript
interface UserConfig {
  theme: "light" | "dark";
  notifications: boolean;
}
```
Buat fungsi `applyConfig(config: UserConfig)` dan tunjukkan dua cara pemanggilan:
1. Pemanggilan yang memicu *Excess Property Check error*.
2. Pemanggilan dengan data properti berlebih yang lolos tanpa error menggunakan teknik *variable indirection*.

### Level Medium
Implementasikan generic type `StrictShape<T, Target>` yang akan mengembalikan type error jika objek `T` memiliki properti yang tidak terdaftar sama sekali di dalam `Target`. Uji generic type tersebut pada fungsi `validateContract<T>(input: StrictShape<T, Target>): void`.

### Level Hard
Rancang library branded types generik tanpa runtime overhead yang mendukung subtipe hirarkis:
- Sebuah `AdminUserId` harus assignable ke `UserId`, namun `UserId` **tidak boleh** assignable ke `AdminUserId`.
- Implementasi harus murni berada di level type system (compile time) tanpa membangkitkan class instance JavaScript di bundle output runtime.

---

## 14. Challenge: Zero-Leakage Data Access Object (DAO) Pattern

### Skenario Bisnis
Arsitektur sistem kesehatan (*Healthcare Management Enterprise*) mewajibkan data rekam medis pasien (Medical Record) terlindungi dari kebocoran data (*data leakage*). Objek `InternalMedicalRecord` di database memiliki 25 field, termasuk data sensitif seperti `ssn` dan `encryptionIV`. 

Saat mengirimkan data ke frontend, hanya shape `PublicMedicalRecordDTO` yang diizinkan keluar:
```typescript
interface InternalMedicalRecord {
  patientId: string;
  ssn: string;
  encryptionIV: string;
  diagnosisCode: string;
  doctorNotes: string;
  updatedAt: Date;
}

interface PublicMedicalRecordDTO {
  patientId: string;
  diagnosisCode: string;
  doctorNotes: string;
}
```

### Tugas Rekayasa:
1. Bangun generic mapper compile-time `EnforceExactProjection<TSource, TTarget>` yang menjamin secara statis bahwa developer tidak dapat mereturn objek `InternalMedicalRecord` secara langsung ketika fungsi menandatangani output `PublicMedicalRecordDTO`, bahkan jika variabel dilewatkan melalui *variable reference* (mengatasi bypass default width subtyping).
2. Terapkan branded primitives untuk `patientId` dan `ssn` agar tidak bisa dipetakan ke string sembarangan.
3. Solusi tidak boleh menggunakan library eksternal (murni TypeScript type calculus).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)

1. **Apa perbedaan mendasar antara Structural Typing dan Nominal Typing?**
   - *Jawaban:* Structural typing mencocokkan kompatibilitas tipe berdasarkan bentuk dan properti internal tipe data tersebut, sedangkan nominal typing mendasarkan kompatibilitas murni pada deklarasi nama tipe dan silsilah hierarki eksplisitnya.

2. **Kapan Excess Property Checking (EPC) dieksekusi oleh TypeScript?**
   - *Jawaban:* EPC hanya aktif ketika sebuah objek didefinisikan secara langsung sebagai *Fresh Object Literal* di tempat assignment atau passing argument, bukan ketika dilewatkan melalui referensi variabel yang sudah ada sebelumnya.

3. **Apakah interface yang kosong (`interface Empty {}`) menolak assignment objek yang memiliki properti?**
   - *Jawaban:* Tidak. Karena sistem TypeScript bersifat structural dan menganut *width subtyping*, setiap nilai non-nullish (termasuk objek dengan banyak properti) kompatibel dan dapat di-assign ke interface kosong `{}`.

4. **Apa tujuan teknis utama dari implementasi Branded Types di TypeScript?**
   - *Jawaban:* Untuk menyematkan identitas nominal secara artifisial pada compile-time ke tipe primitif, sehingga compiler dapat membedakan dua tipe primitif yang identik (misal dua tipe `string`) guna mencegah bug human-error seperti *argument swapping*.

5. **Apakah TypeScript menyisakan metadata bentuk interface di dalam file kompilasi `.js`?**
   - *Jawaban:* Tidak. Seluruh type aliases, interfaces, dan type assertions dihapus total (*erasure*) selama fase emit compiler, menghasilkan zero runtime footprint.

---

### Bagian 2: Intermediate (5 Pertanyaan)

6. **Mengapa kode berikut menghasilkan compile-time error?**
   ```typescript
   interface Point { x: number; y: number; }
   function plot(p: Point) {}
   plot({ x: 10, y: 20, z: 30 });
   ```
   - *Jawaban:* Karena argumen `{ x: 10, y: 20, z: 30 }` dilewatkan sebagai fresh object literal. Kompiler mengaktifkan Excess Property Check untuk melindungi developer dari potensi salah ketik atau kesalahan definisi parameter.

7. **Bagaimana cara meloloskan pemanggilan fungsi `plot` di atas tanpa mengubah interface `Point` dan tanpa type assertion `as`?**
   - *Jawaban:* Mengikat objek literal tersebut ke dalam perantara variabel terlebih dahulu sebelum dilewatkan ke fungsi:
     ```typescript
     const coords = { x: 10, y: 20, z: 30 };
     plot(coords); // Lolos evaluasi width subtyping
     ```

8. **Ditinjau dari AST dan internals `checker.ts`, mengapa cyclic type references tidak menyebabkan infinite compile loop?**
   - *Jawaban:* Compiler menggunakan `relationCache` internal. Ketika relasi antara Type ID sumber dan Type ID target sedang dievaluasi, ID pasangan tersebut dicatat di memori traversal. Jika compiler bertemu dengan pasangan node ID yang sama kembali dalam siklus rekursi yang belum resolved, ia mengasumsikan assignability bernilai true sementara untuk memutus loop.

9. **Apa perbedaan antara Width Subtyping dan Depth Subtyping?**
   - *Jawaban:* Width subtyping berkaitan dengan kuantitas properti (sebuah subtype memiliki properti yang lebih banyak atau sama dari supertype). Depth subtyping berkaitan dengan tipe dari properti anak di dalam hierarki (tipe properti anak dari subtype harus merupakan subtype dari properti anak supertype).

10. **Mengapa penggunaan `declare const __brand: unique symbol` lebih disukai dalam pembuatan Branded Type dibandingkan string biasa seperti `{ __brand: "MyBrand" }`?**
    - *Jawaban:* Penggunaan `unique symbol` menjamin tidak akan pernah ada tabrakan penamaan properti (*property collisions*) baik secara struktural maupun runtime dengan key objek yang sebenarnya, serta mencegah manipulasi tipe secara tidak sengaja oleh pengguna library.

---

### Bagian 3: Skenario Kasus Produksi (3 Kasus)

#### Skenario 1: API Contract Drift
**Konteks:** Sistem frontend Anda terintegrasi dengan REST API microservice yang dikelola tim lain. Backend menambahkan properti baru yang tidak tertera pada interface klien TypeScript Anda. Beberapa fungsi logic frontend me-serialize seluruh data respons tersebut kembali ke database lokal IndexedDB, menyebabkan kuota storage meledak akibat data sampah.
- **Masalah:** Structural typing di frontend mengabaikan properti baru tersebut (*width subtyping*), sehingga lolos tanpa deteksi.
- **Pertanyaan Arsitektural:** Mekanisme arsitektur apa yang wajib dipasang di boundary network layer untuk menanggulangi bahaya struktural ini?
- **Solusi Rekayasa:** Integrasikan runtime parsing schema validation layer (menggunakan Zod dengan mode `.strict()` atau TypeBox). Jangan pernah me-cast response dengan `as ResponseType`. Runtime schema validator dengan strict mode akan secara eksplisit melempar error atau menghapus (*strip*) properti asing sebelum data menyentuh business logic frontend.

#### Skenario 2: Database Layer Mutex Trap
**Konteks:** Sebuah sistem transaksi perbankan memiliki dua method mutasi:
```typescript
async function lockAccount(accountId: string) { ... }
async function lockTransferSession(sessionId: string) { ... }
```
Dalam sebuah insiden fatal di produksi, seorang engineer secara keliru menuliskan:
```typescript
await lockAccount(session.sessionId);
```
Kompiler tidak mendeteksi kesalahan tersebut karena keduanya bertipe `string`. Akibatnya, akun yang salah terkunci dan transaksi macet secara global.
- **Pertanyaan Arsitektural:** Bagaimana Anda merestrukturisasi codebase untuk menjamin kesalahan di atas terdeteksi 100% pada fase kompilasi tanpa membuat class wrapper yang mengorbankan performa GC (Garbage Collection)?
- **Solusi Rekayasa:** Terapkan compile-time Branded Types (`AccountId = Brand<string, "AccountId">` dan `SessionId = Brand<string, "SessionId">`). Factory function untuk pembuatan session dan entity account harus mengembalikan tipe branded ini. Dengan begitu, passing `SessionId` ke parameter `AccountId` akan memicu kompilasi gagal secara instan tanpa runtime overhead sama sekali.

#### Skenario 3: CI/CD Build Time Degradation
**Konteks:** Sebuah tim enterprise mengimplementasikan custom utility type `DeepExact<T>` pada seluruh controller mereka untuk mencegah data leaking. Setelah di-merge, waktu build `tsc` di pipeline CI melonjak dari 45 detik menjadi 18 menit, dan beberapa developer lokal mengalami crash *JavaScript Heap Out of Memory*.
- **Masalah:** Tipe rekursif mendalam (*homomorphic mapped types* rekursif) melipatgandakan jumlah type instantiation di dalam memory space compiler secara eksponensial.
- **Pertanyaan Arsitektural:** Apa mitigasi teknis terbaik untuk mempertahankan integritas data tanpa mengorbankan waktu build tim?
- **Solusi Rekayasa:** 
  1. Hapus utility deep-exact rekursif dari compile-time TypeScript engine.
  2. Alihkan tanggung jawab pembersihan properti ke runtime validation level serialization menggunakan *DTO Whitelisting* (contoh: pemanfaatan library runtime serialization yang teroptimasi, atau `class-transformer` dengan `whitelist: true`).
  3. Batasi type checking TypeScript pada *shallow contract enforcement* untuk menjaga performa type solver compiler tetap $O(N)$ linear.

---

## 16. Summary

- **Structural Typing** mendefinisikan kompatibilitas berdasarkan struktur isi tipe, bukan label nama kelas (*Shape Contracts*).
- **Excess Property Checks (EPC)** adalah perlindungan ergonomis dari TypeScript untuk mendeteksi bug salah ketik pada *Fresh Object Literals*, namun proteksi ini dapat ditembus secara natural melalui referensi variabel (*indirection*) akibat sifat dasar *Width Subtyping*.
- **Branded Types** adalah teknik arsitektural esensial dalam DDD enterprise untuk mengemulasikan *Nominal Typing* di atas sistem struktural TypeScript dengan *Zero Runtime Overhead*.
- Keselamatan sistem pada boundary arsitektur (Network I/O, Database Storage) tidak dapat diserahkan murni kepada structural type system compile-time; integrasi dengan strict schema validator pada runtime boundary adalah keharusan mutlak.