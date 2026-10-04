# Bab 06 Module 01: Control Flow Analysis & Type Guards

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** `02-Programming-Languages`
*   **Mata Pelajaran:** TypeScript Advanced Systems Architecture
*   **Bab 06:** Sistem Tipe Tingkat Lanjut & Analisis Statis
*   **Modul 01:** Control Flow Analysis (CFA) & Type Guards
*   **Tingkat Kesulitan:** Intermediate to Advanced (L3)
*   **Prasyarat Konseptual:**
    *   Sistem Tipe Primitif & Komposit TypeScript (`union`, `intersection`)
    *   Literal Types & Subtyping (Sistem Tipe Struktural)
    *   Eksekusi Runtime JavaScript (Prototypal Inheritance, Operator `typeof`, `instanceof`, `in`)
    *   Kompilasi Dasar TypeScript & Konfigurasi `strictNullChecks`
*   **Target Versi TypeScript:** TypeScript 5.0+ (ES2022 Target Execution)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Mendekonstruksi Mekanisme CFA:** Menjelaskan secara presisi bagaimana compiler TypeScript memetakan Abstract Syntax Tree (AST) ke Control Flow Graph (CFG) guna memperbarui konteks tipe pada setiap simpul eksekusi (*basic block*).
2.  **Mengimplementasikan Mekanisme Built-in Narrowing:** Memanfaatkan operator JavaScript native (`typeof`, `instanceof`, `in`, equality narrowing, truthiness) untuk membatasi ruang lingkup *union types* secara deterministik.
3.  **Merancang Custom Type Predicates:** Membangun *user-defined type guards* dengan sintaks `value is TargetType` dan *assertion signatures* (`asserts value is TargetType`) yang tahan terhadap perubahan struktural dan *runtime failure*.
4.  **Menerapkan Exhaustive Checking:** Mengimplementasikan pola *exhaustive type matching* menggunakan tipe primitif `never` untuk menjamin keamanan kompilasi (*compile-time safety*) pada penambahan varian *discriminated union*.
5.  **Menganalisis dan Memitigasi Narrowing Invalidation:** Mengidentifikasi dan mengatasi kasus di mana TypeScript mereset proses *narrowing* akibat efek samping mutasi fungsi lokal, pemanggilan *closure*, atau *mutable array indices*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam JavaScript biasa, variabel hanyalah pointer memori yang menampung referensi ke nilai dinamis tanpa batasan skema. Dalam TypeScript, variabel diasosiasikan dengan representasi matematis dari himpunan nilai yang diperbolehkan (*type space*).

### Mental Model: Pipa Filter Aliran (Narrowing Pipe)

Bayangkan sebuah variabel bertipe union `A | B | C` sebagai aliran cairan multikomponen yang masuk ke dalam sistem pipa bercabang:

```
[ Union Input: A | B | C ]
           |
     [ Guard 1 ] ---> (Jika lolos: Tipe A dialirkan ke Jalur 1)
           |
  (Sisa: B | C)
           |
     [ Guard 2 ] ---> (Jika lolos: Tipe B dialirkan ke Jalur 2)
           |
      (Sisa: C)    ---> (Jalur default: Tipe C)
```

TypeScript *Control Flow Analysis* (CFA) bukan sekadar pemeriksa deklarasi statis; CFA bertindak sebagai **Abstract Interpreter**. CFA menelusuri setiap percabangan kode Anda secara topologis:
1.  **Branching (Percabangan):** Menggandakan status tipe saat menemukan simpul kondisional (`if`, `switch`, operator ternary).
2.  **Narrowing (Penyempitan):** Mengurangi kardinalitas union type pada cabang tertentu berdasarkan predikat yang bernilai `true`.
3.  **Subtraction (Pengurangan):** Mengeliminasi tipe yang sudah diverifikasi dari cabang `else` atau jalur eksekusi berikutnya.
4.  **Re-merging (Penggabungan Ulang):** Menghitung *union* dari seluruh status tipe yang mungkin keluar dari setiap titik temu eksekusi (*join point*).

Seorang software engineer tingkat lanjut tidak memandang *type guards* sebagai formalitas untuk membungkam compiler, melainkan sebagai **kontrak pembuktian matematis** yang menjamin validitas operasional saat eksekusi runtime menyentuh domain memory yang aman.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah representasi Control Flow Graph (CFG) yang dibangun oleh compiler TypeScript saat menganalisis fungsi yang menerima tipe polimorfik `string | number[] | { data: string }`:

```
                  +-----------------------------------+
                  |        Node: Entry Point          |
                  |    input: string | number[] | Obj |
                  +-----------------------------------+
                                    |
                                    v
                     /-----------------------------\
                    <   typeof input === 'string'   >
                     \-----------------------------/
                               /          \
                       True   /            \   False
                             v              v
         +-----------------------+     +-------------------------------+
         |    Node: Branch A     |     |   Node: Subtracted Flow (1)   |
         |     input: string     |     |    input: number[] | Obj      |
         +-----------------------+     +-------------------------------+
         | Eksekusi:             |                     |
         | input.toUpperCase()   |                     v
         +-----------------------+      /-----------------------------\
                     |                 <       'data' in input         >
                     |                  \-----------------------------/
                     |                            /          \
                     |                    True   /            \   False
                     |                          v              v
                     |      +-----------------------+     +-----------------------+
                     |      |    Node: Branch B     |     |    Node: Branch C     |
                     |      |      input: Obj       |     |   input: number[]     |
                     |      +-----------------------+     +-----------------------+
                     |      | Eksekusi:             |     | Eksekusi:             |
                     |      | input.data.trim()     |     | input.map(...)        |
                     |      +-----------------------+     +-----------------------+
                     |                  |                             |
                     \                  |                             /
                      \                 |                            /
                       +----------------+---------------------------+
                                        |
                                        v
                           +------------------------+
                           |     Node: Exit Point   |
                           |   (Type Join / Merge)  |
                           +------------------------+
```

Apabila terdapat simpul yang secara logis tidak mungkin dicapai (misalnya penanganan kondisi setelah seluruh anggota himpunan union tereliminasi), CFA akan menyimpulkan simpul tersebut bertipe `never` (*unreachable node*).

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

Proses internal TypeScript Compiler (khususnya *Checker* layer) dalam menjalankan CFA melibatkan siklus hidup sistematis:

```
[ Source Code: .ts ] 
         |
         v
     [ Parser ] --------> Membentuk Abstract Syntax Tree (AST)
         |
         v
     [ Binder ] --------> Membentuk Symbol Table & Flow Nodes (Control Flow Graph)
         |
         v
    [ TypeChecker ] ----> Menghitung `FlowCondition`, `FlowLabel`, dan mengevaluasi Narrowing
         |
         v
   [ Emit Engine ] -----> Menghapus artefak tipe, menghasilkan JavaScript murni
```

### Struktur Internal Representasi Tipe CFA:
1.  **`FlowNode`:** Entitas internal yang merepresentasikan simpul dalam alur program. Terdapat berbagai varian `FlowNode`:
    *   `FlowLabel`: Titik temu percabangan (misalnya setelah blok `if-else`).
    *   `FlowCondition`: Simpul yang merepresentasikan ekspresi pengujian boolean (`if (x)`).
    *   `FlowAssignment`: Simpul yang merepresentasikan mutasi nilai (`x = 10`).
    *   `FlowBranch`: Penanda peralihan jalur (misalnya `break`, `continue`, `return`).
2.  **`FlowFlags`:** Bitmask internal (seperti `Start`, `Branch`, `LoopLabel`, `Assignment`) yang memandu algoritma rekursif *checker* (`createTypeChecker`) untuk menentukan apakah sebuah variabel dapat diakses (*reachable*) atau telah tereliminasi.
3.  **Evaluasi Mundur (Backward Querying):** Saat compiler mengevaluasi tipe dari variabel `x` pada baris $N$, ia tidak menelusuri dari atas ke bawah secara konvensional. Compiler melakukan *query* balik dari baris $N$ ke rantai `FlowNode` pendahulunya hingga mencapai deklarasi awal atau kondisi pembatas terdekat.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Built-in Type Guards

TypeScript secara inheren mengikat perilaku beberapa operator JavaScript native ke dalam inferensi sistem tipenya:

*   **`typeof` Narrowing:** Berlaku untuk tipe primitif JavaScript (`"string"`, `"number"`, `"bigint"`, `"boolean"`, `"symbol"`, `"undefined"`, `"object"`, `"function"`).
    *Kelemahan historis:* `typeof null` menghasilkan nilai `"object"`. Oleh karena itu, pengecekan `typeof x === "object"` tidak mengeliminasi `null` tanpa adanya evaluasi *truthiness* tambahan (`x !== null`).
*   **`instanceof` Narrowing:** Menguji apakah fungsi konstruktor ada pada rantai prototipe objek target (`prototype chain`).
    *Batasan:* Gagal mendeteksi validitas tipe pada objek yang ditransfer lintas konteks eksekusi (seperti *iframe*, Web Worker, atau serialisasi IPC/JSON), karena objek tersebut memiliki prototipe global yang berbeda.
*   **Equality Narrowing (`===`, `!==`, `==`, `!=`):** Mengeliminasi tipe secara deterministik berdasarkan nilai literal atau perbandingan dua variabel yang berbeda tipe union.
*   **In-operator Narrowing (`"prop" in object`):** Memverifikasi eksistensi sebuah properti pada objek. Sangat berguna untuk membedakan struktur objek tanpa penanda (*untagged record*).

### 2. Discriminated Unions (Tagged Unions)

Secara teoritis, *discriminated union* adalah implementasi dari *Algebraic Data Types* (ADT), khususnya *Sum Types* $A + B$. Pola ini membutuhkan properti literal tunggal yang ada pada setiap anggota union sebagai pembeda (*discriminant key*):

```typescript
type Circle = { kind: "circle"; radius: number };
type Square = { kind: "square"; sideLength: number };
type Shape = Circle | Square;
```

CFA menggunakan pemetaan properti literal `kind` untuk memisahkan domain validasi secara komprehensif.

### 3. User-Defined Type Guards (Type Predicates)

Ketika logika runtime terlalu rumit untuk built-in operator, kita mendefinisikan *type predicate* dengan bentuk:
`parameterName is SpecificType`

Fungsi ini harus mengembalikan nilai `boolean`. Jika fungsi mengembalikan `true`, compiler akan menetapkan bahwa variabel yang diperiksa berstatus `SpecificType` pada cabang eksekusi tersebut.

### 4. Assertion Signatures

Diperkenalkan untuk mendukung skenario di mana kegagalan validasi melempar *exception* alih-alih mengembalikan `false`:
`asserts condition` atau `asserts parameterName is SpecificType`

Sintaks ini memberi tahu CFA: *“Jika fungsi ini selesai dieksekusi tanpa melempar runtime error, maka variabel target dijamin memiliki tipe yang dideklarasikan.”*

### 5. Exhaustiveness Checking via `never`

Tipe `never` adalah *bottom type* dalam teori tipe; tipe ini tidak memiliki nilai anggota selain himpunan kosong $\emptyset$. CFA menandai cabang yang tidak dapat dicapai dengan tipe `never`. Memanfaatkan properti ini, kita dapat menetapkan variabel `never` pada blok `default` untuk menegakkan validasi kompilasi:

```typescript
function assertUnreachable(x: never): never {
  throw new Error(`Exhaustive check failed. Unhandled value: ${JSON.stringify(x)}`);
}
```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah berkas terpadu yang mendemonstrasikan implementasi menyeluruh dari seluruh varian Type Guard:

```typescript
// ==========================================
// 1. Tipe Data Domain & Discriminated Union
// ==========================================

export interface TextPayload {
  readonly kind: "text";
  readonly content: string;
}

export interface BinaryPayload {
  readonly kind: "binary";
  readonly buffer: Uint8Array;
}

export interface MetricPayload {
  readonly kind: "metric";
  readonly values: readonly number[];
}

export type NetworkPayload = TextPayload | BinaryPayload | MetricPayload;

// ==========================================
// 2. Custom Type Predicate
// ==========================================

export function isTextPayload(payload: NetworkPayload): payload is TextPayload {
  return payload.kind === "text" && typeof payload.content === "string";
}

// ==========================================
// 3. Assertion Functions
// ==========================================

export class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ValidationError";
  }
}

export function assertValidPayload(
  payload: unknown
): asserts payload is NetworkPayload {
  if (typeof payload !== "object" || payload === null) {
    throw new ValidationError("Payload must be a non-null object");
  }

  if (!("kind" in payload)) {
    throw new ValidationError("Payload is missing required discriminant key 'kind'");
  }

  const kind = (payload as { kind: unknown }).kind;
  if (kind !== "text" && kind !== "binary" && kind !== "metric") {
    throw new ValidationError(`Unknown payload kind: ${String(kind)}`);
  }
}

// ==========================================
// 4. Exhaustive CFA Consumer
// ==========================================

export function processPayload(payload: NetworkPayload): string {
  // Discriminated union narrowing menggunakan switch statement
  switch (payload.kind) {
    case "text":
      // CFA mempersempit payload menjadi TextPayload
      return `Text: ${payload.content.toUpperCase()}`;

    case "binary":
      // CFA mempersempit payload menjadi BinaryPayload
      return `Binary size: ${payload.buffer.byteLength} bytes`;

    case "metric":
      // CFA mempersempit payload menjadi MetricPayload
      const sum = payload.values.reduce((acc, val) => acc + val, 0);
      return `Metric mean: ${sum / (payload.values.length || 1)}`;

    default:
      // Exhaustiveness Checking: payload pada titik ini berstatus never
      const _unreachable: never = payload;
      throw new Error(`Unhandled payload variant: ${_unreachable}`);
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis dari implementasi pada Seksi 07:

1.  **Baris 7–20:** Mendefinisikan tiga interface terpisah (`TextPayload`, `BinaryPayload`, `MetricPayload`) yang masing-masing memiliki properti literal diskriminan `kind`. Tipe `NetworkPayload` adalah representasi *Sum Type* dari ketiganya.
2.  **Baris 26:** Fungsi `isTextPayload` dideklarasikan dengan tipe kembalian `payload is TextPayload`. Ini adalah *Custom Type Predicate*.
3.  **Baris 27:** Blok evaluasi runtime. Memvalidasi bahwa properti `kind` bernilai `"text"` dan memastikan tipe runtime dari `payload.content` adalah primitif `string`. Jika evaluasi ini menghasilkan `true`, CFA akan mengeliminasi tipe `BinaryPayload` dan `MetricPayload` dari variabel yang diuji.
4.  **Baris 40–42:** Deklarasi assertion function `assertValidPayload(payload: unknown): asserts payload is NetworkPayload`. Nilai parameter berjenis `unknown`, tipe paling aman untuk input eksternal tak terverifikasi.
5.  **Baris 43–45:** Validasi keberadaan objek non-null. Mengatasi kelemahan native JavaScript di mana `typeof null === "object"`. Jika bernilai `null` atau bukan objek, eksekusi diputus seketika via `throw new ValidationError`.
6.  **Baris 47–49:** Evaluasi keberadaan properti via `in`. Setelah lolos dari baris 45, CFA mengetahui bahwa `payload` adalah `object`, namun belum tentu memiliki key `'kind'`.
7.  **Baris 51–54:** Narrowing nilai diskriminan secara spesifik. Jika string tersebut tidak cocok dengan ketiga literal yang diizinkan, eksekusi dihentikan. Setelah melewati baris 54 tanpa melempar galat, sistem tipe menaikkan status tipe `payload` dari `unknown` menjadi `NetworkPayload`.
8.  **Baris 62:** Evaluasi `switch (payload.kind)`. CFA menggunakan evaluasi diskriminan konstan untuk memotong branch himpunan.
9.  **Baris 63–74:** Pada setiap blok `case`, properti payload disesuaikan secara otomatis:
    *   Di dalam `case "text"`, properti `.content` dapat diakses langsung tanpa casting.
    *   Di dalam `case "binary"`, properti `.buffer` dapat diakses langsung.
10. **Baris 76–78:** Blok `default` mengeksekusi *Exhaustiveness Checking*. Tipe `never` mengonfirmasi bahwa seluruh kemungkinan tipe telah ditangani di atasnya. Apabila di kemudian hari ditambahkan tipe payload baru (misal: `ImagePayload`) ke dalam `NetworkPayload` tanpa memperbarui blok `switch`, baris `const _unreachable: never = payload;` akan menghasilkan galat kompilasi secara instan: *Type 'ImagePayload' is not assignable to type 'never'*.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Pipeline Ingesti Multi-Vendor Payment Gateway Webhook

Dalam sistem arsitektur finansial, sistem backend menerima ratusan ribu event webhook per hari dari berbagai penyedia pihak ketiga (misalnya: Stripe, PayPal, dan Midtrans). Setiap penyedia memiliki format payload yang berbeda secara signifikan, dan seluruh payload tersebut masuk melalui endpoint HTTP publik tunggal dalam bentuk raw JSON tanpa jaminan integritas tipe compile-time.

### Kebutuhan Sistem:
1.  **Zero-Tolerance Mutation:** Menerima raw payload tak terstruktur (`unknown`) tanpa menggunakan tipe `any`.
2.  **Polymorphic Dispatching:** Memetakan tipe payload secara akurat ke struktur transaksi masing-masing vendor menggunakan Type Guards berkinerja tinggi.
3.  **Strict Error Handling:** Mengisolasi payload anomali atau rusak sebelum menyentuh lapisan persistensi basis data.
4.  **Compile-time Extension Enforcement:** Setiap ada vendor baru yang diintegrasikan, compiler wajib mencegah build sistem berhasil hingga seluruh alur penanganan event webhook vendor tersebut diimplementasikan secara komprehensif.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah arsitektur produksi lengkap untuk memproses Webhook Payment Gateway:

```typescript
// ============================================================================
// 1. Data Contracts (Vendors Domain Specifications)
// ============================================================================

export interface StripeEvent {
  readonly provider: "STRIPE";
  readonly id: string;
  readonly data: {
    readonly object: {
      readonly chargeId: string;
      readonly amountInCents: number;
    };
  };
}

export interface PayPalEvent {
  readonly provider: "PAYPAL";
  readonly txnId: string;
  readonly purchase_units: ReadonlyArray<{
    readonly amount: {
      readonly currency_code: string;
      readonly value: string; // PayPal merepresentasikan uang dalam string desimal
    };
  }>;
}

export interface MidtransEvent {
  readonly provider: "MIDTRANS";
  readonly order_id: string;
  readonly gross_amount: string;
  readonly transaction_status: "capture" | "settlement" | "deny" | "pending";
}

// Sum Type seluruh event pembayaran yang sah
export type NormalizedWebhookEvent = StripeEvent | PayPalEvent | MidtransEvent;

// Objek Internal Terpadu (Unified Internal Ledger Entry)
export interface LedgerTransaction {
  readonly vendorReferenceId: string;
  readonly providerName: "STRIPE" | "PAYPAL" | "MIDTRANS";
  readonly normalizedAmount: number;
  readonly timestamp: number;
}

// ============================================================================
// 2. Custom Type Predicates & Assertion Infrastructures
// ============================================================================

function isObject(val: unknown): val is Record<string, unknown> {
  return typeof val === "object" && val !== null && !Array.isArray(val);
}

export function isStripeEvent(val: unknown): val is StripeEvent {
  if (!isObject(val) || val.provider !== "STRIPE" || typeof val.id !== "string") {
    return false;
  }
  if (!isObject(val.data) || !isObject(val.data.object)) {
    return false;
  }
  const obj = val.data.object;
  return typeof obj.chargeId === "string" && typeof obj.amountInCents === "number";
}

export function isPayPalEvent(val: unknown): val is PayPalEvent {
  if (!isObject(val) || val.provider !== "PAYPAL" || typeof val.txnId !== "string") {
    return false;
  }
  if (!Array.isArray(val.purchase_units) || val.purchase_units.length === 0) {
    return false;
  }
  const firstUnit = val.purchase_units[0];
  if (!isObject(firstUnit) || !isObject(firstUnit.amount)) {
    return false;
  }
  return (
    typeof firstUnit.amount.currency_code === "string" &&
    typeof firstUnit.amount.value === "string"
  );
}

export function isMidtransEvent(val: unknown): val is MidtransEvent {
  if (!isObject(val) || val.provider !== "MIDTRANS" || typeof val.order_id !== "string") {
    return false;
  }
  if (typeof val.gross_amount !== "string") {
    return false;
  }
  const validStatuses = ["capture", "settlement", "deny", "pending"];
  return (
    typeof val.transaction_status === "string" &&
    validStatuses.includes(val.transaction_status)
  );
}

// Top-Level Assertion Function
export function assertWebhookEvent(payload: unknown): asserts payload is NormalizedWebhookEvent {
  if (isStripeEvent(payload) || isPayPalEvent(payload) || isMidtransEvent(payload)) {
    return;
  }
  throw new Error("Security Violation: Malformed or untrusted payload format rejected.");
}

// ============================================================================
// 3. Execution Pipeline & Exhaustive Router
// ============================================================================

export class PaymentIngestionPipeline {
  public static ingest(rawPayload: unknown): LedgerTransaction {
    // 1. Tipe rawPayload awalnya unknown. Lakukan validasi ketat via assertion.
    assertWebhookEvent(rawPayload);

    // 2. Sekarang rawPayload telah dipersempit menjadi NormalizedWebhookEvent.
    // Lakukan pemrosesan menggunakan Control Flow Analysis berbasis diskriminan 'provider'.
    switch (rawPayload.provider) {
      case "STRIPE": {
        // Otomatis tersempitkan ke StripeEvent
        return {
          vendorReferenceId: rawPayload.data.object.chargeId,
          providerName: rawPayload.provider,
          normalizedAmount: rawPayload.data.object.amountInCents / 100,
          timestamp: Date.now(),
        };
      }

      case "PAYPAL": {
        // Otomatis tersempitkan ke PayPalEvent
        const parsedAmount = parseFloat(rawPayload.purchase_units[0].amount.value);
        if (Number.isNaN(parsedAmount)) {
          throw new Error("Invalid decimal currency parsing on PayPal payload");
        }
        return {
          vendorReferenceId: rawPayload.txnId,
          providerName: rawPayload.provider,
          normalizedAmount: parsedAmount,
          timestamp: Date.now(),
        };
      }

      case "MIDTRANS": {
        // Otomatis tersempitkan ke MidtransEvent
        const amount = parseFloat(rawPayload.gross_amount);
        return {
          vendorReferenceId: rawPayload.order_id,
          providerName: rawPayload.provider,
          normalizedAmount: amount,
          timestamp: Date.now(),
        };
      }

      default: {
        // 3. Exhaustiveness checking mutlak
        const exhaustiveCheck: never = rawPayload;
        throw new Error(`CRITICAL: Unhandled payment provider: ${JSON.stringify(exhaustiveCheck)}`);
      }
    }
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih mekanisme narrowing yang salah dapat memicu penurunan performa atau celah keamanan tipe (*type safety hole*).

| Metode Narrowing | Kelebihan | Kelemahan / Batasan | Skenario Penggunaan Terbaik |
| :--- | :--- | :--- | :--- |
| **`typeof`** | Operasi native V8 tercepat ($O(1)$), nol alokasi memory overhead. | Terbatas hanya untuk 8 tipe primitif JavaScript; bug historis `typeof null === 'object'`. | Validasi primitif: `string`, `number`, `boolean`, `bigint`. |
| **`instanceof`** | Melacak prototipe turunan class OOP secara akurat. | Gagal jika objek berasal dari context memory berbeda (iFrame, Worker, JSON deserialization). | Memvalidasi instance class lokal/domain models/Error classes. |
| **`in` Operator** | Memeriksa eksistensi properti tanpa asumsi class instance. | Melempar error jika variabel target bernilai primitif (`"foo" in 123` melempar `TypeError`). | Membedakan Record/Interface anonim tanpa constructor. |
| **Discriminated Union** | Pendekatan paling idiomatik TypeScript, zero runtime logic overhead di luar switch/if. | Membutuhkan modifikasi struktur payload untuk menyertakan *tag/discriminant key*. | Pemodelan status domain terpusat (Redux Actions, Response States). |
| **Custom Predicates (`is`)** | Sangat fleksibel, mampu mengevaluasi aturan validasi bisnis mendalam. | **Bukan compile-safe secara internal!** Jika logika JS salah, compiler tetap percaya return type. | Boundary layer: Validasi raw JSON eksternal dari API/Database. |
| **Schema Validation (Zod, etc.)** | Sinkronisasi dua arah antara runtime validation dan compile-time types. | Terdapat alokasi memori tambahan dan penalti CPU parsing/bundle size footprint. | Validasi komprehensif payload HTTP request/API form submission. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Narrowing Invalidation Melalui Closures

Salah satu perangkap paling berbahaya dalam CFA adalah asumsi bahwa narrowing bertahan di dalam eksekusi fungsi callback (closure).

```typescript
function processItems(input: string | null) {
  if (input !== null) {
    // Di sini input adalah 'string'
    setTimeout(() => {
      // TypeScript 4.2+ mereset narrowing ke string | null
      // Alasan: Callback dieksekusi secara asinkron; fungsi lain bisa saja
      // memutasi referensi variabel di scope luar sebelum timer habis!
      console.log(input.toUpperCase()); // Potensi runtime error jika 'input' termutasi
    }, 1000);
  }
}
```

*Solusi Arsitektural:* Selalu tetapkan nilai ke konstanta lokal (`const safeInput = input;`) sebelum masuk ke closure.

### 2. Mutasi Array Index dan In-bounds Assumption

TypeScript secara default mengasumsikan bahwa pengaksesan index array menghasilkan tipe elemen tersebut, bukan `Type | undefined`:

```typescript
const values: number[] = [10, 20];
const item = values[5]; // Tipe statis: 'number', Nilai Runtime: 'undefined'!
// CFA tidak menyadari bahwa 'item' adalah undefined tanpa flag 'noUncheckedIndexedAccess'.
item.toFixed(2); // FATAL: Cannot read properties of undefined (reading 'toFixed')
```

*Solusi:* Wajib aktifkan `"noUncheckedIndexedAccess": true` pada `tsconfig.json`.

### 3. Kebohongan Tipe pada User-Defined Type Guards

Compiler memperlakukan *type predicate* sebagai kebenaran mutlak tanpa memverifikasi kebenaran implementasi fungsinya:

```typescript
function isNumber(val: unknown): val is number {
  return true; // KEBOHONGAN FATAL!
}

const text: unknown = "hello world";
if (isNumber(text)) {
  // Compiler menganggap text: number
  text.toFixed(2); // RUNTIME ERROR: text.toFixed is not a function
}
```

### 4. Narrowing pada Properti yang Dapat Termutasi (Getters)

Jika sebuah objek menggunakan accessor properties (`get`), CFA berasumsi nilai return tidak berubah antar pemanggilan, padahal getter bisa mengembalikan tipe berbeda setiap kali dipanggil:

```typescript
const dynamicObj = {
  get value(): string | number {
    return Math.random() > 0.5 ? "str" : 100;
  }
};

if (typeof dynamicObj.value === "string") {
  // dynamicObj.value dipanggil ulang saat eksekusi baris ini, dan bisa mengembalikan number!
  dynamicObj.value.toLowerCase(); 
}
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mengabaikan Penanganan `null` pada Pengecekan `"object"`
```typescript
// BAD
function parseData(data: unknown) {
  if (typeof data === "object") {
    // Salah! null adalah object menurut JavaScript engine.
    console.log("length" in data); // Error: Cannot use 'in' operator to search in null
  }
}

// GOOD
function parseData(data: unknown) {
  if (typeof data === "object" && data !== null) {
    console.log("length" in data); // Aman
  }
}
```

### Kesalahan 2: Menggunakan Type Assertion (`as`) sebagai Pengganti Type Guard
```typescript
// BAD
function handleEvent(event: unknown) {
  const stripeEvent = event as StripeEvent; // Membungkam compiler tanpa validasi runtime
  console.log(stripeEvent.data.object.chargeId); // Crash jika payload bukan StripeEvent
}

// GOOD
function handleEvent(event: unknown) {
  if (isStripeEvent(event)) {
    console.log(event.data.object.chargeId); // Tervalidasi secara runtime dan compile-time
  } else {
    throw new Error("Invalid payload format");
  }
}
```

### Kesalahan 3: Tidak Menetapkan Variabel Penampung `never` pada Exhaustiveness Checking
```typescript
// BAD
function handleAction(action: { type: 'INCREMENT' } | { type: 'DECREMENT' }) {
  switch (action.type) {
    case 'INCREMENT': return 1;
    case 'DECREMENT': return -1;
    default:
      return 0; // Jika ditambah varian 'RESET', compiler tidak memberi peringatan!
  }
}

// GOOD
function handleAction(action: { type: 'INCREMENT' } | { type: 'DECREMENT' }) {
  switch (action.type) {
    case 'INCREMENT': return 1;
    case 'DECREMENT': return -1;
    default: {
      const _exhaustive: never = action;
      throw new Error(`Unhandled action: ${_exhaustive}`);
    }
  }
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan Tag Literal yang Homogen:** Pastikan properti diskriminan memiliki nama yang konsisten di seluruh entitas terkait (misalnya menggunakan key `type` atau `kind` di seluruh domain event model).
2.  **Tempatkan Custom Guard pada Lapisan Masuk Sistem (*Boundary Layer*):** Buat type guard di controller, subscriber event bus, atau file reader. Hindari memanggil type guard di internal core domain logic jika data sudah berstatus bersih (*trusted boundary*).
3.  **Gunakan Readonly Discriminated Unions:** Selalu tandai properti diskriminan dan payload sebagai `readonly` guna mencegah mutasi struktur yang dapat membatalkan validasi CFA.
4.  **Terapkan Strict Compiler Flags:**
    Pastikan `tsconfig.json` memiliki pengaturan minimal:
    ```json
    {
      "compilerOptions": {
        "strict": true,
        "noUncheckedIndexedAccess": true,
        "exactOptionalPropertyTypes": true
      }
    }
    ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

Meskipun Type Guard bertindak sebagai konstruksi waktu kompilasi, implementasi logika evaluasi runtime di dalamnya berdampak langsung pada latensi eksekusi V8 engine:

1.  **Urutan Evaluasi Guard (Short-circuit Execution Order):**
    Tempatkan pengecekan primitif termurah ($O(1)$ type lookup) sebelum penelusuran struktur dalam objek:
    ```typescript
    // OPTIMAL: Pengecekan typeof mendahului pembacaan key properti
    if (typeof payload === "object" && payload !== null && "targetKey" in payload) { ... }
    ```
2.  **Hindari Redundant Deep Traversals:**
    Hindari melakukan parsing berulang (misal parsing string desimal atau ekspresi reguler) di dalam guard jika nilai tersebut akan di-parse kembali pada alur bisnis. Pertahankan hasil parsing pada struktur data baru (*Data Transformation Pattern*).
3.  **Compiler Performance (CFG Explosion Prevention):**
    Union yang terlalu besar (misalnya union dari 500 interface individual) dapat menyebabkan compiler TypeScript melambat drastis saat mengkalkulasi kemungkinan *subtraction flow*. Gunakan pemisahan *Domain Chunks* atau *Lookup Tables* jika kardinalitas union melampaui batas kewajaran.

---

## SEKSI 16 — KEAMANAN & HARDENING

Implementasi Type Guard yang lemah membuka celah eksploitasi deserialisasi dan serangan prototype poisoning.

### Mitigasi Prototype Poisoning dalam Type Guards:
Penyerang dapat mengirimkan JSON berbahaya yang memanipulasi properti `__proto__`.

```typescript
// VULNERABLE TO PROTOTYPE INJECTION
function unsafeCheck(data: unknown): data is { role: string } {
  return typeof data === "object" && data !== null && "role" in data;
}
// Objek dengan prototype injection: Object.create(null, { role: { value: 'admin' } })
```

### Pola Pertahanan Aman (Hardened Guard):
Gunakan `Object.prototype.hasOwnProperty.call` atau `Object.hasOwn` (ES2022) untuk memastikan properti berasal dari instansi objek langsung, bukan hasil injeksi prototipe:

```typescript
export function isSecuredRecord<K extends string>(
  obj: unknown,
  requiredKey: K
): obj is Record<K, unknown> {
  if (typeof obj !== "object" || obj === null || Array.isArray(obj)) {
    return false;
  }
  return Object.hasOwn(obj, requiredKey);
}
```

Pastikan deserialisasi input mentah selalu diisolasi dan divalidasi skemanya sebelum dieksekusi oleh mesin bisnis kritis.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Bagaimana memverifikasi apa yang dipikirkan oleh compiler saat menganalisis alur program yang kompleks?

### 1. Trik Inspeksi Statis Instan (Type Probe)

Gunakan utility type bantuan untuk menginspeksi kondisi tipe aktual pada baris mana pun di editor IDE tanpa harus mengarahkan kursor:

```typescript
type InspectType<T> = { [K in keyof T]: T[K] };

// Menyematkan tipe probe untuk melihat kalkulasi narrowing compiler
type AssertDebug<T> = T;

function complexFlow(input: string | number[] | { [key: string]: boolean }) {
  if (typeof input !== "string" && !Array.isArray(input)) {
    // Posisikan probe di sini:
    type CurrentCalculatedType = AssertDebug<typeof input>;
    // IDE akan langsung menampilkan: { [key: string]: boolean }
  }
}
```

### 2. Memaksa Error Compiler untuk Trace Dump

Gunakan tag invalidasi tipe:

```typescript
// @ts-expect-error Pengecekan paksa: jika 'input' belum 'never', compiler akan diam.
const _debugTrace: never = input; 
```

### 3. Structured Failure Logging pada Assertion

Saat assertion function gagal, simpan struktur payload dalam format terenkapsulasi untuk observabilitas log sistem (misal: Datadog, CloudWatch):

```typescript
export function assertWithTelemetry<T>(
  condition: boolean,
  message: string,
  debugContext: Record<string, unknown>
): asserts condition {
  if (!condition) {
    const errorDetails = {
      message,
      context: debugContext,
      timestamp: new Date().toISOString(),
    };
    // Mengirim ke observability pipeline
    console.error("[TYPE_ASSERTION_FAILURE]", JSON.stringify(errorDetails));
    throw new ValidationError(message);
  }
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

| Konsep / Operator | Sintaks Kode | Output Type State | Runtime Footprint |
| :--- | :--- | :--- | :--- |
| **Typeof Guard** | `typeof x === 'string'` | `x` menjadi `string` | Rendah (Native Opcode) |
| **Instanceof Guard** | `x instanceof CustomClass` | `x` menjadi `CustomClass` | Rendah (Prototype scan) |
| **In Guard** | `'id' in x` | `x` menjadi `Record<'id', unknown> & ...` | Rendah (Property lookup) |
| **Equality Check** | `x === 'SUCCESS'` | `x` menjadi `'SUCCESS'` | Sangat Rendah |
| **Custom Predicate** | `fn(x): x is CustomType` | `x` menjadi `CustomType` jika `true` | Tergantung logika fungsi |
| **Assertion Function**| `assert(x): asserts x is T`| Mengubah tipe `x` di scope lokal | Melempar Exception |
| **Exhaustive Trap** | `const _: never = x;` | Mencegah kompilasi jika `x` tidak kosong | Nol (Dihapus saat compile) |

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Ujilah penguasaan konseptual Anda terhadap Control Flow Analysis dan Type Guards.

### Soal Tingkat Dasar (Basic)

1.  **Diberikan union type `type Val = string | number | boolean`. Jika Anda melakukan pengecekan `if (typeof val !== "string")`, apa tipe dari `val` di dalam blok `else`?**
    *   A. `number | boolean`
    *   B. `string`
    *   C. `never`
    *   D. `unknown`

2.  **Apa yang menyebabkan runtime error pada kode berikut?**
    ```typescript
    function test(x: unknown) {
      if (typeof x === "object") {
        console.log("prop" in x);
      }
    }
    ```
    *   A. Operator `in` tidak mendukung variabel bertipe `object`.
    *   B. `typeof x === "object"` bernilai `true` saat `x` bernilai `null`, dan operasi `"prop" in null` melempar `TypeError`.
    *   C. Variabel `unknown` tidak bisa diperiksa dengan `typeof`.
    *   D. Operator `in` hanya bekerja pada instance `class`.

3.  **Sintaks yang benar untuk menulis custom type guard yang memverifikasi bahwa parameter `item` adalah array of strings adalah:**
    *   A. `function isStringArray(item: unknown): boolean`
    *   B. `function isStringArray(item: unknown): item is string[]`
    *   C. `function isStringArray(item: unknown): asserts item is string[]`
    *   D. `function isStringArray(item: unknown): string[]`

4.  **Apa fungsi dari tipe `never` dalam blok `default` pada penanganan discriminated union?**
    *   A. Mengoptimalkan performa parsing V8 engine.
    *   B. Mengubah seluruh nilai kembalian menjadi `void`.
    *   C. Memastikan saat waktu kompilasi (*compile-time*) bahwa semua kemungkinan varian telah ditangani secara menyeluruh (*exhaustive*).
    *   D. Menjamin fungsi tidak melempar runtime exception.

5.  **Kapan sebaiknya assertion signature (`asserts condition`) digunakan dibandingkan type predicate (`value is Type`)?**
    *   A. Saat Anda ingin menghentikan (*fail-fast*) alur eksekusi dengan exception daripada mengembalikan nilai boolean bercabang.
    *   B. Saat Anda ingin meningkatkan performa memory buffer.
    *   C. Saat memvalidasi tipe primitif sederhana.
    *   D. Saat bekerja di dalam array filter.

---

### Soal Tingkat Menengah (Intermediate)

6.  **Perhatikan kode berikut. Mengapa compiler menghasilkan error pada baris pemanggilan `value.trim()`?**
    ```typescript
    function process(value: string | null) {
      if (value !== null) {
        window.addEventListener("resize", () => {
          console.log(value.trim());
        });
      }
    }
    ```
    *   A. Tipe `string` tidak memiliki fungsi bawaan `.trim()`.
    *   B. `addEventListener` tidak mengizinkan penutupan lexical scope.
    *   C. CFA mereset narrowing pada *callback closures* karena nilai referensi `value` dianggap berpotensi termutasi sebelum callback dieksekusi.
    *   D. Parameter `value` harus dideklarasikan sebagai `const`.

7.  **Diberikan kode berikut:**
    ```typescript
    type Square = { size: number };
    type Rectangle = { width: number; height: number };
    type Shape = Square | Rectangle;

    function getArea(shape: Shape) {
      if ("size" in shape) {
        return shape.size * shape.size;
      }
      return shape.width * shape.height;
    }
    ```
    **Mengapa pola di atas bekerja tanpa diskriminan tag eksplisit?**
    *   A. Menggunakan fitur duck-typing runtime TypeScript.
    *   B. Operator `in` menyempitkan tipe union dengan memisahkan anggota yang memiliki properti kunci tersebut dari yang tidak memilikinya.
    *   C. Operator `in` mengeksekusi prototipe constructor `Square`.
    *   D. Compiler memanggil method `hasOwnProperty` secara otomatis.

8.  **Apa output tipe statis dari `result` pada baris akhir berikut?**
    ```typescript
    const rawList: (string | number | undefined)[] = ["a", 1, "b", undefined];
    const result = rawList.filter((item): item is string => typeof item === "string");
    ```
    *   A. `(string | number | undefined)[]`
    *   B. `unknown[]`
    *   C. `string[]`
    *   D. `(string | number)[]`

9.  **Mengapa `instanceof` gagal mendeteksi class instance secara andal saat bekerja pada arsitektur Micro-frontend berbasis iFrame atau Multi-realm Web Workers?**
    *   A. Micro-frontend menonaktifkan V8 optimizer.
    *   B. Setiap realm (iFrame/Worker) memiliki instance memori *global object* dan prototipe konstruktor yang terisolasi, sehingga `instance.constructor !== HostConstructor`.
    *   C. Operasi `instanceof` bersifat asinkron lintas realm.
    *   D. Sistem serialisasi memotong prototype chain menjadi `null`.

10. **Bagaimana cara mencegah celah keamanan Type Guard di mana pengembang menulis logika verifikasi yang salah dan mengelabui compiler?**
    *   A. Menghindari `asserts` dan menggantinya dengan `as unknown as Type`.
    *   B. Menggabungkan User-Defined Type Guard dengan automated runtime validation schema libraries (misal: Zod, ArkType) dan unit test ekstensif untuk branch validasi.
    *   C. Menonaktifkan opsi `strictNullChecks` di tsconfig.
    *   D. Menambahkan `// @ts-ignore` pada setiap implementasi predicate.

---

### Kunci Jawaban & Pembahasan

1.  **Jawaban: B.**
    *Pembahasan:* Jika `typeof val !== "string"` bernilai salah (masuk ke blok `else`), maka menurut hukum eliminasi logika himpunan CFA, `val` pastilah bertipe `string`.
2.  **Jawaban: B.**
    *Pembahasan:* Dalam spesifikasi JavaScript, `typeof null` menghasilkan `"object"`. Menggunakan operator `"prop" in null` akan secara langsung memicu fatal runtime error `TypeError: Cannot use 'in' operator to search in null`.
3.  **Jawaban: B.**
    *Pembahasan:* Sintaks `item is string[]` adalah type predicate yang valid untuk mengembalikan nilai boolean dan menyempitkan `item` menjadi array of string jika bernilai `true`.
4.  **Jawaban: C.**
    *Pembahasan:* Tipe `never` merepresentasikan himpunan kosong. Jika ada varian baru dari discriminated union yang belum ditangani, variabel tersebut akan memiliki tipe varian baru tersebut (bukan `never`), yang memicu kesalahan penugasan statis (*compile-time assignment error*).
5.  **Jawaban: A.**
    *Pembahasan:* Assertion function dirancang untuk alur program linier (*fail-fast pattern*) di mana kondisi anomali harus memutus proses seketika melalui exception.
6.  **Jawaban: C.**
    *Pembahasan:* TypeScript mengasumsikan bahwa isi callback closure dapat berjalan di masa depan (asinkron). Untuk mencegah asumsi berbahaya di mana variabel luar telah diubah oleh operasi lain, CFA mereset tipe variabel kembali ke union semula (`string | null`).
7.  **Jawaban: B.**
    *Pembahasan:* Operator `in` bertindak sebagai built-in type guard struktural yang memotong varian union yang tidak memiliki properti kunci yang diuji.
8.  **Jawaban: C.**
    *Pembahasan:* Method `Array.prototype.filter` memiliki overload khusus yang menerima type predicate `(val: T) => val is S`, yang secara otomatis mengubah return signature array dari `T[]` menjadi `S[]` (dalam kasus ini: `string[]`).
9.  **Jawaban: B.**
    *Pembahasan:* Operator `instanceof` mengevaluasi referensi prototipe di memori global realm aktif. Jika objek dibuat dalam Realm A (misal iFrame), prototipe `Array` miliknya berbeda referensi fisik memorinya dengan `Array` milik Realm B (Host Window).
10. **Jawaban: B.**
    *Pembahasan:* Karena type predicate adalah titik di mana programmer memberikan garansi sepihak kepada compiler, mitigasi terbaik dari kesalahan logika internal guard adalah menggunakan skema runtime deterministik yang teruji secara otomatis.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Tantangan: Implementasi Event-Driven In-Memory Command Bus

Rancang dan bangun sistem Command Bus bertipe statis yang aman dengan kriteria teknis berikut:

#### Spesifikasi Arsitektur:
1.  **Command Domain:**
    Definisikan minimal 3 tipe command unik:
    *   `CreateUserCommand`: Membawa data `{ type: "USER_CREATE"; payload: { username: string; email: string; age: number } }`
    *   `UpdateRoleCommand`: Membawa data `{ type: "ROLE_UPDATE"; payload: { userId: string; newRole: "ADMIN" | "MEMBER" } }`
    *   `PurgeDataCommand`: Membawa data `{ type: "DATA_PURGE"; payload: { confirmToken: string; hardDelete: boolean } }`
2.  **Assertion Layer:**
    Buat assertion function tunggal `assertIsCommand(raw: unknown): asserts raw is AnyAppCommand` yang memvalidasi struktur input tak dikenal secara menyeluruh, termasuk pencegahan payload `null`, manipulasi prototype, dan pengecekan tipe setiap properti internal.
3.  **Command Bus Engine:**
    Implementasikan class `CommandBus` yang memiliki method:
    *   `dispatch(rawMessage: unknown): CommandExecutionResult`
    *   Di dalam method `dispatch`, gunakan blok switch dengan pola **Exhaustiveness Checking** via `never`.
4.  **Zero Any Tolerance:**
    Kompilasi kode harus diselesaikan dengan flag `"strict": true` tanpa ada satu pun kata kunci `any` atau komentar `// @ts-ignore` / `// @ts-expect-error`.

### Starter Code Template:

```typescript
export type UserCreateCommand = {
  readonly type: "USER_CREATE";
  readonly payload: {
    readonly username: string;
    readonly email: string;
    readonly age: number;
  };
};

export type RoleUpdateCommand = {
  readonly type: "ROLE_UPDATE";
  readonly payload: {
    readonly userId: string;
    readonly newRole: "ADMIN" | "MEMBER";
  };
};

export type DataPurgeCommand = {
  readonly type: "DATA_PURGE";
  readonly payload: {
    readonly confirmToken: string;
    readonly hardDelete: boolean;
  };
};

export type AppCommand =
  | UserCreateCommand
  | RoleUpdateCommand
  | DataPurgeCommand;

export interface CommandExecutionResult {
  readonly success: boolean;
  readonly commandType: string;
  readonly executionLog: string;
}

// TODO: Implementasikan fungsi assertIsCommand(raw: unknown): asserts raw is AppCommand
// TODO: Implementasikan class CommandBus dengan method dispatch(raw: unknown)
```

### Tolok Ukur Keberhasilan:
*   Build berhasil dieksekusi dengan `tsc --noEmit`.
*   Saat Anda menambahkan varian baru `AuditExportCommand` ke dalam union `AppCommand`, compiler TypeScript **harus langsung melempar compile-error** pada class `CommandBus` sampai blok handler untuk command tersebut selesai diimplementasikan.