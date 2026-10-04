# BAB 02 — MODULE 01: STRUCTURAL TYPING & SHAPE CONTRACTS

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** `02-Programming-Languages` / `typescript`
*   **Modul:** Bab 02, Modul 01
*   **Topik Utama:** *Structural Typing & Shape Contracts*
*   **Tingkat Kesulitan:** Intermediate ke Advanced
*   **Prasyarat:** Pemahaman tipe data primitif TypeScript, deklarasi `interface` & `type alias`, fungsi dasar, dan kompilasi TypeScript (`tsconfig.json`).
*   **Target Kompatibilitas:** TypeScript 5.0+, Node.js 18+ LTS, ES2022+

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis (C4)** perbedaan mendasar antara *Structural Type Systems* (seperti TypeScript/Go) dan *Nominal Type Systems* (seperti Java/C#/Rust) pada level kompilasi dan runtime.
2.  **Mengevaluasi (C5)** perilaku relasi subtipe (*width subtyping* dan *depth subtyping*) serta implikasinya terhadap integritas data.
3.  **Mengoperasikan (C3)** mekanisme *Excess Property Checks* (Freshness) dan mengidentifikasi kondisi pemicu bypass mekanisme tersebut.
4.  **Merekayasa (C6)** teknik *Nominal Simulation* (Branded Types / Flavoring) untuk mencegah *type-confusion bugs* pada domain primitif yang identik secara struktural.
5.  **Memitigasi (C4)** risiko kebocoran data (*mass assignment vulnerabilities*) yang disebabkan oleh sifat permisif structural subtyping pada arsitektur backend.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Tipe sebagai Himpunan Nilai (Set-Theoretic Mental Model)

Dalam *nominal typing*, tipe adalah sebuah label resmi atau akta kelahiran. Jika Anda membuat `class User { name: string }` dan `class Customer { name: string }`, keduanya adalah entitas berbeda di mata kompilator karena mereka memiliki deklarasi nama yang berbeda secara eksplisit.

Dalam *structural typing*, tipe bukanlah label, melainkan **predikat bentuk (*shape predicate*)** atau **himpunan nilai (*set of values*)**.
*   Tipe `Point2D = { x: number; y: number }` mendefinisikan himpunan semua nilai dalam JavaScript yang *memiliki properti `x` berjenis number dan properti `y` berjenis number*.
*   Jika sebuah objek memiliki bentuk properti yang memenuhi atau melebihi kontrak tersebut, objek tersebut **secara matematis merupakan anggota dari himpunan tersebut**.

```
                Himpunan Objek di Runtime
+-------------------------------------------------------+
|  Objek: { x: 10, y: 20, z: 30, label: "origin" }       |
|                                                       |
|   +-----------------------------------------------+   |
|   | Memenuhi Tipe Point3D: { x, y, z }             |   |
|   |                                               |   |
|   |   +---------------------------------------+   |   |
|   |   | Memenuhi Tipe Point2D: { x, y }       |   |   |
|   |   +---------------------------------------+   |   |
|   +-----------------------------------------------+   |
+-------------------------------------------------------+
```

Konsekuensi mental:
1.  **"Duck Typing at Compile-Time":** Jika objek berjalan seperti bebek dan bersuara seperti bebek, maka pada fase kompilasi objek tersebut *adalah* bebek.
2.  **Compatibility by Compatibility of Members:** Penugasan nilai $S$ ke target $T$ valid jika dan hanya jika seluruh anggota kontraktual pada $T$ dapat ditemukan dan kompatibel pada $S$.
3.  **Open by Default:** Tipe objek dalam TypeScript bersifat terbuka (*open-ended*), bukan tertutup (*sealed*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur keputusan kompilator TypeScript (`tsc`) dalam mengevaluasi apakah tipe sumber $S$ dapat ditugaskan ke tipe target $T$ ($S <: T$):

```
                        Mulai Evaluasi: S assignable to T?
                                      |
                                      v
                        +----------------------------+
                        | Apakah S identik dengan T? |
                        +----------------------------+
                                      |
                       +--------------+--------------+
                       | Ya                          | Tidak
                       v                             v
               [ASSIGNMENT VALID]      +----------------------------+
                                       | Apakah T tipe Primitif /   |
                                       | Any / Unknown / Never?     |
                                       +----------------------------+
                                                     |
                                                     v
                                       +----------------------------+
                                       | Apakah S merupakan         |
                                       | Object Literal ("Fresh")?  |
                                       +----------------------------+
                                        /                          \
                                  Ya   /                            \ Tidak
                                      v                              v
                    +----------------------------------+   +-------------------+
                    | Excess Property Checks Aktif     |   | Standard          |
                    | Apakah S memiliki properti yang  |   | Structural Check: |
                    | TIDAK dideklarasikan di T?       |   | Iterasi properti  |
                    +----------------------------------+   | kontraktual T     |
                       /                            \      +-------------------+
                 Ada  /                              \ Tdk           |
                     v                                v              v
             [COMPILE ERROR]                 +---------------------------------+
             "Object literal may only        | Apakah setiap properti t di T   |
              specify known properties"      | ada di S dan tipenya kompatibel |
                                             | (S[t] assignable to T[t])?      |
                                             +---------------------------------+
                                                             /                 \
                                                       Ya   /                   \ Tidak
                                                           v                     v
                                                  [ASSIGNMENT VALID]     [COMPILE ERROR]
                                                                         "Property missing 
                                                                          or type mismatch"
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Mekanisme Internal TypeScript Type Checker

Pada *codebase* kompilator TypeScript (`src/compiler/checker.ts`), relasi penugasan diperiksa melalui fungsi internal `checkTypeRelatedTo`. Ketika memvalidasi tipe objek struktural:

1.  **Type Identity & Cache:** Checker memeriksa *relation cache* (`relation === SubtypeRelation`). Jika pasangan `(source, target)` sudah pernah divalidasi, hasil langsung diambil dari memori.
2.  **Property Enumeration:** Checker mengambil semua properti yang dapat diakses (*apparent properties*) dari target $T$ via `getPropertiesOfType(target)`.
3.  **Recursive Member Check:**
    *   Untuk setiap simbol properti $P \in T$:
        *   Cari properti dengan nama identik $P' \in S$.
        *   Jika $P'$ tidak ditemukan dan $P$ bukan *optional* (`?`), kompilator menghasilkan error diagnostik `Diagnostics.Property_0_is_missing_in_type_1`.
        *   Jika $P'$ ditemukan, checker memanggil `checkTypeRelatedTo(getTypeOfSymbol(P'), getTypeOfSymbol(P))` secara rekursif.
4.  **Excess Property Check Flag:** Checker menandai tipe sumber dengan *flag* bit `TypeFlags.FreshLiteral` jika node AST berasal langsung dari `SyntaxKind.ObjectLiteralExpression`. Jika flag ini aktif dan target tidak memiliki *index signature*, checker memastikan himpunan kunci sumber adalah himpunan bagian (*subset*) murni dari himpunan kunci target:
    $$\text{Keys}(S) \subseteq \text{Keys}(T)$$

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Subtyping: Width vs. Depth Subtyping

Dalam sistem tipe teoritis, subtipe objek diatur oleh dua aturan utama:

#### Width Subtyping
Objek dengan jumlah properti lebih banyak merupakan subtipe dari objek dengan properti lebih sedikit, asalkan properti yang dibutuhkan terpenuhi.
$$\{ x: \text{number}, y: \text{number}, z: \text{number} \} <: \{ x: \text{number}, y: \text{number} \}$$
*Arti:* Semakin lebar (*wider*) data yang dimiliki sebuah instance, semakin sempit (*narrower*) dan spesifik tipenya secara teoritis. Tipe dengan properti lebih sedikit justru lebih abstrak dan menampung lebih banyak kemungkinan instance.

#### Depth Subtyping
Tipe properti internal dari sebuah objek dapat berupa subtipe dari properti target.
Jika $A <: B$, maka:
$$\{ data: A \} <: \{ data: B \}$$
*Catatan Mutabilitas:* TypeScript mengizinkan depth subtyping secara kovarian pada tipe objek secara default demi ergonomi bahasa JavaScript, meskipun pada referensi mutabel murni, ini secara teoritis berpotensi menyebabkan runtime exception.

### 2. The Freshness Check (Excess Property Check)

Pertimbangkan kontradiksi berikut:
Jika width subtyping mengizinkan properti tambahan, mengapa kode berikut memicu compile error?

```typescript
interface Point {
    x: number;
    y: number;
}

// Error: Object literal may only specify known properties, and 'z' does not exist in type 'Point'.
const p: Point = { x: 1, y: 2, z: 3 };
```

**Rasional Desain TypeScript:**
Secara filosofis JavaScript, mendefinisikan objek literal baru secara langsung dan menambahkan properti yang tidak ada pada tipe penampung hampir 100% merupakan *human error* (salah ketik nama properti atau kesalahpahaman API). Properti `z` tidak akan pernah bisa diakses melalui variabel `p` karena tipenya adalah `Point`.

Oleh karena itu, TypeScript menerapkan aturan khusus: **Literal Freshness**. Objek literal baru dianggap *fresh*. Begitu objek literal tersebut di-assign ke variabel perantara, *freshness*-nya hilang, dan aturan *width subtyping* standar kembali berlaku:

```typescript
const rawPoint = { x: 1, y: 2, z: 3 }; // freshness dihilangkan di sini
const p: Point = rawPoint; // VALID via width subtyping
```

### 3. Tipe Objek: `{}` vs `object` vs `Record<string, unknown>`

| Tipe | Karakteristik Struktural | Menolak |
| :--- | :--- | :--- |
| `{}` (Empty Object Type) | Menerima tipe non-nullish apapun (angka, boolean, string, objek, fungsi). | `null`, `undefined` |
| `object` | Menerima nilai reference tipe non-primitif apapun. | Nilai primitif (`number`, `string`, `boolean`, `symbol`, `bigint`), `null`, `undefined` |
| `Record<string, unknown>` | Menerima sembarang objek struktural dengan kunci string. | Primitif, `null`, `undefined`, objek tanpa representasi string-indexable |

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi komparasi fundamental structural compatibility, bypass freshness, dan depth evaluation:

```typescript
// 1. Kontrak Interface
interface Coordinates2D {
  readonly latitude: number;
  readonly longitude: number;
}

interface LabeledCoordinates2D extends Coordinates2D {
  readonly label: string;
}

// 2. Definisi Struktur Independen (Tanpa implementasi eksplisit)
interface GPSWaypoint {
  latitude: number;
  longitude: number;
  elevation: number;
}

// 3. Fungsi Konsumen
function renderMapPin(coords: Coordinates2D): string {
  return `PIN: Lat=${coords.latitude.toFixed(4)}, Long=${coords.longitude.toFixed(4)}`;
}

// === UJI 1: Freshness Enforcement ===
// @ts-expect-error - Excess property 'elevation' ditolak pada object literal langsung
const pinDirectError: string = renderMapPin({
  latitude: -6.2088,
  longitude: 106.8456,
  elevation: 12
});

// === UJI 2: Width Subtyping via Reference Assignment ===
const jakartaGPS: GPSWaypoint = {
  latitude: -6.2088,
  longitude: 106.8456,
  elevation: 12
};
// Lolos: jakartaGPS kompatibel secara struktural dengan Coordinates2D
const pinFromRef: string = renderMapPin(jakartaGPS);

// === UJI 3: Anonymous Object Shape ===
const anonymousLocation = {
  latitude: -7.7956,
  longitude: 110.3695,
  city: "Yogyakarta",
  population: 422732
};
// Lolos: Variabel memenuhi kontrak { latitude, longitude }
const pinFromAnon: string = renderMapPin(anonymousLocation);

console.log(pinFromRef);
console.log(pinFromAnon);
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut bedah mekanika dari kode fundamental di atas:

1.  `interface Coordinates2D { ... }`: Menentukan *shape boundary*. Setiap nilai yang masuk ke ekosistem ini wajib memiliki sekurang-kurangnya properti `latitude` bertipe `number` dan `longitude` bertipe `number`.
2.  `interface GPSWaypoint { ... }`: Struktur ini **tidak** menggunakan kata kunci `extends Coordinates2D`. Dalam nominal typing, ini adalah kelas berbeda. Di TypeScript, deklarasi ini 100% kompatibel dengan `Coordinates2D` karena superset propertinya.
3.  `renderMapPin(coords: Coordinates2D)`: Fungsi murni bergantung pada kontrak bentuk. Fungsi tidak peduli prototipe atau hierarki pewarisan dari argumen `coords`.
4.  `pinDirectError`: Objek `{ latitude, longitude, elevation }` adalah literal ekspresi *fresh*. *Type checker* mengaktifkan pemeriksaan properti ekses, mendeteksi `elevation` tidak terdaftar pada `Coordinates2D`, dan melempar error `TS2353`.
5.  `const jakartaGPS: GPSWaypoint = ...`: Objek dialokasikan ke referensi variabel independen. Atribut tipe dikunci ke `GPSWaypoint`.
6.  `renderMapPin(jakartaGPS)`: Ketika `jakartaGPS` diteruskan, *flag* *freshness* tidak aktif. Kompilator beralih ke *structural subtype matching*. Karena `GPSWaypoint` memiliki `latitude: number` dan `longitude: number`, kompilator memberikan izin (*sound assignment*).
7.  `anonymousLocation`: Membuktikan bahwa tipe ad-hoc tanpa deklarasi interface sebelumnya tetap valid selama bentuk internalnya bersesuaian.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur Payment Dispatcher Multi-Gateway

Sebuah sistem *Fintech Core* menerima payload dari berbagai Third-Party Payment Processor (Midtrans, Xendit, Stripe). Setiap gateway memiliki nama schema data JSON yang berbeda secara runtime, namun pada domain layer internal, sistem hanya membutuhkan kontrak kanonik:

```typescript
CanonicalPaymentRequest = {
  transactionId: string;
  amountInCents: bigint;
  currency: "IDR" | "USD";
}
```

Tantangan yang dihadapi:
1.  Gateway eksternal mengirim ratusan metadata tambahan (IP, User Agent, Hash Signatures). Jika sistem menggunakan nominal class instantiation biasa, parsing menjadi lambat dan kaku.
2.  Namun, jika menggunakan structural typing mentah tanpa proteksi, data sensitif yang tidak tervalidasi dapat merembes masuk ke lapisan database (*mass assignment attack*).
3.  Diperlukan mekanisme *Shape Normalizer* & *Nominal Branding* untuk token/ID agar ID Transaksi tidak tertukar dengan ID Merchant.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut implementasi arsitektural yang memanfaatkan structural typing dengan aman menggunakan *Branded Types* dan *Sanitizing Contracts*:

```typescript
// ==========================================
// 1. DOMAIN LAYER: BRANDED TYPES (NOMINAL EMULATION)
// ==========================================

declare const TransactionIdBrand: unique symbol;
declare const MerchantIdBrand: unique symbol;

export type TransactionId = string & { readonly [TransactionIdBrand]: true };
export type MerchantId = string & { readonly [MerchantIdBrand]: true };

// Constructor helper (Smart Casts)
export function toTransactionId(id: string): TransactionId {
  if (!id.startsWith("txn_")) {
    throw new Error(`Format ID Transaksi tidak valid: ${id}`);
  }
  return id as TransactionId;
}

export function toMerchantId(id: string): MerchantId {
  if (!id.startsWith("mch_")) {
    throw new Error(`Format ID Merchant tidak valid: ${id}`);
  }
  return id as MerchantId;
}

// Canonical Structural Contract
export interface CanonicalPaymentRequest {
  readonly transactionId: TransactionId;
  readonly merchantId: MerchantId;
  readonly amountInCents: bigint;
  readonly currency: "IDR" | "USD";
}

// ==========================================
// 2. GATEWAY ADAPTER SHAPES (EXTERNAL)
// ==========================================

export interface VendorAPayload {
  vendor_txn_id: string;
  vendor_merchant_code: string;
  total_gross_cents: number;
  currency_code: string;
  extra_tracking_pixel: string; // Ekses
  client_ip: string;            // Ekses
}

export interface VendorBPayload {
  transaction_reference: string;
  partner_id: string;
  amount: {
    value: number;
    iso_currency: string;
  };
  debug_trace_id: string;       // Ekses
}

// ==========================================
// 3. CORE SERVICE DISPATCHER
// ==========================================

export class PaymentProcessingEngine {
  public static execute(request: CanonicalPaymentRequest): void {
    // Mengeksekusi pembayaran secara strictly typed
    console.log(
      `[PROSES] ID: ${request.transactionId} | Merchant: ${request.merchantId} | ` +
      `Nominal: ${request.amountInCents.toString()} ${request.currency}`
    );
  }
}

// ==========================================
// 4. NORMALIZER PIPELINE DENGAN STRIP EKSPOR EKSES
// ==========================================

export class PaymentNormalizer {
  // Mengonversi Vendor A ke Canonical Shape (Menghilangkan Ekses)
  public static normalizeVendorA(raw: VendorAPayload): CanonicalPaymentRequest {
    return {
      transactionId: toTransactionId(raw.vendor_txn_id),
      merchantId: toMerchantId(raw.vendor_merchant_code),
      amountInCents: BigInt(raw.total_gross_cents),
      currency: raw.currency_code === "IDR" ? "IDR" : "USD"
    };
  }

  // Mengonversi Vendor B ke Canonical Shape
  public static normalizeVendorB(raw: VendorBPayload): CanonicalPaymentRequest {
    return {
      transactionId: toTransactionId(raw.transaction_reference),
      merchantId: toMerchantId(raw.partner_id),
      amountInCents: BigInt(raw.amount.value),
      currency: raw.amount.iso_currency === "IDR" ? "IDR" : "USD"
    };
  }
}

// ==========================================
// 5. RUNTIME EXECUTION TEST
// ==========================================

function bootstrap() {
  const incomingVendorA: VendorAPayload = {
    vendor_txn_id: "txn_01HZ89ABCD",
    vendor_merchant_code: "mch_tokopedia",
    total_gross_cents: 25000000,
    currency_code: "IDR",
    extra_tracking_pixel: "https://tracking.com/pixel.gif",
    client_ip: "103.20.10.1"
  };

  // Normalisasi & Eksekusi
  const canonicalA = PaymentNormalizer.normalizeVendorA(incomingVendorA);
  PaymentProcessingEngine.execute(canonicalA);

  // Mencegah Type Confusion Bug berkat Branded Types:
  const fakeTxnId = "txn_9999" as TransactionId;
  const fakeMchId = "mch_8888" as MerchantId;

  // Kode di bawah ini jika posisinya dibalik akan gagal kompilasi:
  // const invalidPayload: CanonicalPaymentRequest = {
  //   transactionId: fakeMchId, // COMPILE ERROR: Type 'MerchantId' is not assignable to type 'TransactionId'
  //   merchantId: fakeTxnId,
  //   amountInCents: 1000n,
  //   currency: "USD"
  // };
}

bootstrap();
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Dimensi Parameter | Structural Typing (TypeScript) | Nominal Typing (Java/C#) | Duck Typing (Python/JavaScript) |
| :--- | :--- | :--- | :--- |
| **Mekanisme Evaluasi** | Static Analysis (Berdasarkan kompatibilitas bentuk/anggota). | Static Analysis (Berdasarkan deklarasi hirarki eksplisit). | Dynamic / Runtime Execution (Evaluasi kehadiran metode saat dipanggil). |
| **Fleksibilitas Desain** | Sangat Tinggi. Memudahkan *decoupling* dan *mocking* tanpa perlu interface inheritance massal. | Rendah. Memerlukan *adapter pattern* atau perubahan source code jika tipe upstream berbeda. | Tertinggi. Tidak ada batasan tipe statis sama sekali. |
| **Type Safety & Collisions** | Sedang ke Tinggi. Dua domain berbeda dengan bentuk identik dapat saling menggantikan tanpa sengaja. | Sangat Tinggi. Dua entitas dengan struktur sama tidak bisa tertukar tanpa cast eksplisit. | Rendah. Kesalahan properti/metode baru muncul saat runtime (`TypeError`). |
| **Biaya Kompilasi** | Lebih lambat. Membutuhkan traversal mendalam (*recursive member inspection*) pada AST. | Cepat. Pemeriksaan hanya berupa pencarian node turunan pada *type hierarchy tree*. | Nol waktu kompilasi tipe. Beban dialihkan ke runtime interpreter. |
| **Refactoring Safety** | Hati-hati: Mengubah nama properti pada satu interface dapat mempengaruhi tipe lain secara implisit. | Sangat Aman: Compiler melacak seluruh implementasi interface deklaratif secara presisi. | Rapuh: Bergantung sepenuhnya pada test coverage dan text search. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Bahaya Tipe Objek Kosong `{}`
Banyak pengembang menganggap `{}` merepresentasikan "objek kosong tanpa properti". Ini keliru.
Secara struktural, `{}` merepresentasikan **nilai apapun yang memiliki nol atau lebih properti dan bukan `null`/`undefined`**.

```typescript
function printObject(val: {}) {
  console.log(val);
}

printObject(42);         // VALID di TypeScript! Karena Number.prototype memiliki properti
printObject("string");   // VALID!
printObject(true);       // VALID!
// printObject(null);    // Error
// printObject(undefined);// Error
```
**Mitigasi:** Gunakan `Record<string, never>` untuk representasi objek kosong murni, atau `Record<string, unknown>` untuk objek dinamis.

### 2. Bypass Freshness Melalui Tipe Union

Pemeriksaan properti ekses dapat berperilaku tidak intuitif ketika berhadapan dengan *discriminated unions*:

```typescript
type Action = 
  | { type: "FETCH"; url: string }
  | { type: "DELETE"; silent: boolean };

// Kesalahan logika: 'silent' ada di variant DELETE, tetapi diabaikan di sini
const action: Action = {
  type: "FETCH",
  url: "https://api.com",
  silent: true // TS ERROR: Object literal may only specify known properties...
};
```
Namun, jika properti target tumpang tindih secara longgar (*loose union*), TypeScript sering kali meloloskan properti ekses varian lain selama salah satu varian terpenuhi dan varian lainnya tidak terdiskriminasi secara ketat.

### 3. Mutabilitas dan Invariant Arrays

Array bersifat kovarian di TypeScript. Jika tipe turunan disematkan ke dalam array basis, perubahan bentuk struktural dapat merusak tipe data runtime:

```typescript
interface Animal { name: string; }
interface Dog extends Animal { bark(): void; }

const dogs: Dog[] = [{ name: "Rex", bark: () => console.log("Woof") }];
const animals: Animal[] = dogs; // Diizinkan secara struktural

// Memasukkan Animal murni (kucing) ke dalam array yang direferensikan sebagai Animal
animals.push({ name: "Milo" });

// RUNTIME DISASTER: dogs[1].bark is undefined!
dogs.forEach(d => d.bark());
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Mistake 1: Mengira `instanceof` Mengecek TypeScript Interface

```typescript
interface UserContract {
  id: string;
  name: string;
}

function process(data: unknown) {
  // SALAH BESAR: TS2693: 'UserContract' only refers to a type, but is being used as a value here.
  if (data instanceof UserContract) {
    // ...
  }
}
```
**Cara Menghindari:** Gunakan *User-Defined Type Guard* atau pustaka runtime validator (seperti Zod/Valibot/ArkType). Interface dihapus (*erased*) total setelah proses kompilasi JavaScript.

```typescript
function isUserContract(data: any): data is UserContract {
  return (
    typeof data === "object" &&
    data !== null &&
    typeof data.id === "string" &&
    typeof data.name === "string"
  );
}
```

### Mistake 2: Property Leakage Saat Passing Objek ke Database

```typescript
interface CreateUserInput {
  email: string;
}

async function createUser(input: CreateUserInput) {
  // Input secara runtime bisa berisi: { email: "a@b.com", isAdmin: true, role: "SUPERADMIN" }
  // Jika diteruskan langsung ke ORM:
  await db.user.create({ data: input }); // VULNERABILITY: Overposting / Mass Assignment
}
```
**Cara Menghindari:** Lakukan rekontruksi objek secara eksplisit atau *whitelisting* properti. Jangan mengandalkan TypeScript untuk membuang properti ekses saat runtime.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Whitelisting via Explicit Object Destruction:** Selalu isolasi parameter struktural sebelum diproses ke layer persistensi data.
    ```typescript
    function safeCreateUser(input: CreateUserInput) {
      const sanitized = { email: input.email };
      return db.user.create({ data: sanitized });
    }
    ```
2.  **Gunakan Nominal Tagging (Branded Types) untuk Value Objects:** Gunakan intersection type dengan properti bernilai symbol unik untuk tipe-tipe primitif kritis seperti `UserId`, `AccountId`, `EmailAddress`, `CentAmount`.
3.  **Hindari Deep Index Signatures Tanpa Alasan Jelas:** Penggunaan `[key: string]: any` mematikan semua fitur keamanan structural typing dan *excess property check*.
4.  **Aktifkan Flag `exactOptionalPropertyTypes`:** Dalam `tsconfig.json`, aktifkan fitur ini untuk mencegah properti opsional didefinisikan secara eksplisit sebagai `undefined` jika kontraknya hanya bernilai ada atau tidak ada.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Dampak Compiler Performance pada Deep Structural Evaluation

Kompilator TypeScript membandingkan tipe objek secara rekursif. Ketika sebuah modul memiliki relasi interface yang memiliki tingkat kedalaman bertingkat (*deeply nested structural contracts*), waktu eksekusi `tsc` meningkat secara non-linear $\mathcal{O}(N \times M)$ di mana $N$ dan $M$ adalah jumlah properti internal.

**Strategi Optimasi Compiler:**
*   Gunakan deklarasi `interface` alih-alih `type` intersection (`&`) masif untuk objek model. Kompilator meng-cache pemeriksaan kesesuaian interface berdasarkan nama simbol dengan jauh lebih efisien dibandingkan anonymous compound types.
*   Pangkas struktur data besar yang berulang dengan mendefinisikan batas kontrak (*contract boundary*).

### 2. Runtime Memory Overhead dari Excess Properties

Ketika objek literal besar yang tidak di-sanitize diteruskan melalui serangkaian fungsi karena sifat permisif width subtyping, referensi terhadap objek besar tersebut tetap bertahan di *heap memory*, menghalangi Garbage Collector membebaskan memori.

```typescript
function processUserHeader(user: { id: string }) {
  // Jika argumen yang dikirim adalah objek 5MB (misal: data transaksi lengkap),
  // dan disimpan di global cache/closure, seluruh 5MB tersebut bocor.
  globalCache.set(user.id, user); 
}
```
**Solusi:** Petakan hanya data yang diperlukan: `globalCache.set(user.id, { id: user.id })`.

---

## SEKSI 16 — KEAMANAN & HARDENING

### Penanganan Mass Assignment / Prototype Pollution

Sifat terbuka (*open-ended*) dari tipe struktural TypeScript dapat memberikan rasa aman palsu (*false sense of security*) terhadap serangan eksploitasi data:

```typescript
// Eksploitasi Payload JSON Eksternal
const untrustedJsonPayload = JSON.parse(`{
  "name": "Budi",
  "role": "MEMBER",
  "isAdmin": true,
  "__proto__": { "polluted": true }
}`);

interface UpdateProfileDTO {
  name: string;
}

// Secara structural typing, parameter ini lolos masuk!
function updateProfile(dto: UpdateProfileDTO) {
  // Jika dioperasikan dengan spread operator:
  const updatedData = { ...dto };
  // updatedData kini membawa properti 'isAdmin' dan berpotensi memicu prototype pollution!
}
```

### Panduan Hardening:
1.  **Strict Boundary Ingestion:** Terapkan skema parsing runtime di tepi aplikasi (Controller / API Entry Point). TypeScript menjamin tipe di waktu kompilasi, runtime parser menjamin kebenaran bentuk di memori.
2.  **Object.freeze & Object.seal:** Bekukan objek konfigurasi struktural untuk mencegah mutasi bentuk di runtime.
3.  **Null Prototyping:** Gunakan `Object.create(null)` saat memetakan dictionary dinamis untuk mencegah manipulasi properti warisan Object.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Ketika terjadi inkonsistensi tipe struktural yang sangat besar, pesan error kompilator TypeScript dapat sangat panjang dan sulit dibaca.

### Trik Debugging: Shape Inspection Utilities

Gunakan utilitas tipe berikut untuk membedah perbedaan (*diff*) struktural secara visual di IDE:

```typescript
// Mengembalikan key yang ada di T tapi tidak ada di U (Structural Diff)
type MissingProperties<T, U> = {
  [K in keyof T as K extends keyof U ? never : K]: T[K];
};

// Inspect type display di VSCode tooltip
type Expand<T> = T extends infer O ? { [K in keyof O]: O[K] } : never;

// Penggunaan Debug:
interface ExpectedContract {
  id: string;
  name: string;
  version: number;
}

interface ActualPayload {
  id: string;
  name: string;
}

// Hover over 'DiffTest' di IDE untuk melihat properti yang hilang: { version: number }
type DiffTest = Expand<MissingProperties<ExpectedContract, ActualPayload>>;
```

### Logging Terstruktur Tanpa Membocorkan Ekses

Saat mencatat objek yang masuk ke logging pipeline (seperti Pino atau Winston), hindari `logger.info(input)`. Buat fungsi reduksi kontrak:

```typescript
function logSafePayment(req: CanonicalPaymentRequest): void {
  // Hanya log field kontraktual yang terdaftar
  logger.info({
    event: "PAYMENT_RECEIVED",
    transactionId: req.transactionId,
    merchantId: req.merchantId,
    amount: req.amountInCents.toString(),
    currency: req.currency
  });
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Structural Typing Rules:** $A$ kompatibel dengan $B$ ($A <: B$) jika setiap properti wajib di $B$ ditemukan pada $A$ dengan tipe yang setara atau subtipe dari tipe properti di $B$.
*   **Excess Property Check (EPC):** Hanya aktif pada **Fresh Object Literals** yang langsung dipassing ke penampung bertipe. EPC dimatikan saat objek dioperasikan lewat variabel perantara atau *type assertion*.
*   **Empty Object `{}`:** Mengizinkan semua tipe data kecuali `null` dan `undefined`. Hindari penggunaannya untuk representasi Dictionary.
*   **Nominal Simulation:** Gunakan *Branded Types* (`type UserId = string & { readonly __brand: unique symbol }`) untuk membatasi penugasan nilai primitif yang memiliki semantik domain berbeda.
*   **Type Erasure:** Seluruh kontrak tipe (`interface`, `type`) dihapus dari kode kompilasi JavaScript. Di runtime, hanya ada JavaScript Object biasa yang tidak memiliki proteksi tipe inheren.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Ujilah pemahaman Anda secara mandiri dengan menjawab 10 pertanyaan di bawah ini sebelum melihat kunci jawaban:

### Soal Basic (1-5)

1. Mengapa kode `const a: { x: number } = { x: 1, y: 2 };` menghasilkan compile error, sedangkan kode di bawah ini lolos kompilasi?
   ```typescript
   const raw = { x: 1, y: 2 };
   const a: { x: number } = raw;
   ```
2. Apa output tipe dari variabel berikut, dan nilai apa saja yang ditolak saat penugasan runtime TypeScript?
   ```typescript
   type Target = object;
   ```
3. Apakah TypeScript menganggap dua class dengan nama berbeda dan deklarasi berbeda sebagai tipe yang sama jika keduanya tidak memiliki properti (kosong)?
4. Apa arti istilah *Width Subtyping* dalam sistem tipe objek?
5. Mengapa penulisan interface berikut tidak membatasi pemanggilan fungsi dengan parameter tambahan?
   ```typescript
   interface Consumer { (id: string): void; }
   ```

### Soal Intermediate (6-10)

6. Bagaimana cara memprogram tipe utilitas `StrictEquals<A, B>` yang menghasilkan `true` hanya jika `A` dan `B` identik secara murni (bukan hanya satu arah subtipe dari yang lain)?
7. Perhatikan kode ini:
   ```typescript
   type Box<T> = { value: T };
   let a: Box<string> = { value: "halo" };
   let b: Box<string | number> = a;
   ```
   Apakah penugasan `b = a` valid? Jelaskan variansinya (Kovarian/Kontravarian/Invarian).
8. Sebutkan kelemahan fatal penggunaan Type Assertion `as Contract` dalam menangani payload eksternal terkait structural typing!
9. Bagaimana cara kerja `unique symbol` dalam pembuatan Branded Type untuk memastikan tidak ada collision antar module?
10. Diberikan skema berikut:
    ```typescript
    type Config = { port: number; host?: string };
    const cfg = { port: 8080, host: undefined };
    ```
    Dalam kondisi `tsconfig` standar vs `exactOptionalPropertyTypes: true`, bagaimana perilaku assignability `cfg` ke `Config`?

---

### Kunci Jawaban & Pembahasan

1. **Jawaban:** Kasus pertama memicu *Excess Property Check (Freshness)* karena deklarasi objek literal langsung dilakukan pada target. Kasus kedua melewati variabel perantara `raw`, sehingga freshness hilang dan TypeScript hanya menerapkan aturan relasi subtipe murni (*Width Subtyping*), di mana `{ x: number, y: number }` adalah subtipe valid dari `{ x: number }`.
2. **Jawaban:** Tipe `object` menerima semua nilai referensi non-primitif (seperti `{}`, `[]`, `() => {}`, `new Map()`). Tipe ini **menolak** nilai primitif: `number`, `string`, `boolean`, `symbol`, `bigint`, serta menolak `null` dan `undefined`.
3. **Jawaban:** Ya. Karena TypeScript bersifat struktural, dua class kosong (contoh: `class Foo {}` dan `class Bar {}`) memiliki struktur anggota publik yang identik (yaitu kosong), sehingga instance `Foo` dapat ditugaskan ke variabel bertipe `Bar` dan sebaliknya.
4. **Jawaban:** Aturan di mana tipe sumber dianggap sebagai subtipe jika memiliki properti yang lebih banyak (*wider in data members*) daripada tipe target, selama seluruh properti yang disyaratkan oleh tipe target tersedia dan kompatibel.
5. **Jawaban:** JavaScript secara idiomatik sering mengabaikan argumen callback (misalnya `[1, 2].map(x => x)` mengabaikan argumen `index` dan `array`). Oleh karena itu, TypeScript mengizinkan subtyping fungsi yang memiliki parameter lebih sedikit (*parameter truncation*).
6. **Jawaban:** Menggunakan evaluasi conditional type kondisional terhadap variansi fungsi:
   ```typescript
   type StrictEquals<X, Y> = 
     (<T>() => T extends X ? 1 : 2) extends 
     (<T>() => T extends Y ? 1 : 2) ? true : false;
   ```
7. **Jawaban:** Penugasan tersebut **valid**. Tipe `Box<T>` bersifat **kovarian** terhadap `T` pada tipe objek readonly/biasa di TypeScript. Karena `string` adalah subtipe dari `string | number`, maka `Box<string>` dapat ditugaskan ke `Box<string | number>`.
8. **Jawaban:** Type Assertion (`as Contract`) membungkam kompilator sepenuhnya, menonaktifkan *Excess Property Check* dan menonaktifkan validasi ketersediaan properti wajib. Jika data runtime tidak memiliki properti yang dipaksa lewat assertion, kompilasi tetap sukses tetapi aplikasi akan melempar `TypeError: Cannot read properties of undefined` saat runtime.
9. **Jawaban:** `unique symbol` menghasilkan tipe primitif nominal yang unik di level kompilator dan tidak dapat disubstitusi atau ditiru oleh symbol lain, bahkan jika label deskripsinya sama. Ini mengunci identitas tipe persimpangan (*intersection*) sehingga tidak ada modul lain yang dapat memalsukan brand tersebut secara tidak sengaja.
10. **Jawaban:** Pada `tsconfig` default, `{ host?: string }` diinterpretasikan sebagai `host?: string | undefined`, sehingga `cfg` valid. Namun jika `exactOptionalPropertyTypes: true` diaktifkan, `host?` berarti properti tersebut boleh tidak ada sama sekali, tetapi jika dideklarasikan, nilainya harus bertipe `string` dan tidak boleh di-assign nilai eksplisit `undefined`.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: Strict Shape Ingestion Gateway

#### Deskripsi
Bangunlah sebuah modul *Payload Sanitizer Engine* independen yang bertugas menyeleksi objek eksternal mentah, memvalidasi bentuk secara struktural murni, membuang properti ekses (*excess stripping*), dan menyematkan Brand Tag ke properti identitas.

#### Spesifikasi Kebutuhan:
1.  Buat Brand Nominal Types untuk:
    *   `UserId` (string, diawali `usr_`)
    *   `EmailAddress` (string, mengandung karakter `@`)
2.  Definisikan tipe target internal `UserProfile`:
    ```typescript
    interface UserProfile {
      id: UserId;
      email: EmailAddress;
      displayName: string;
      tier: "FREE" | "PREMIUM";
    }
    ```
3.  Implementasikan fungsi transformer bertipe generic:
    `function sanitizeAndSeal<TInput, TContract>(input: TInput, validator: (raw: TInput) => TContract): Readonly<TContract>`
4.  Fungsi harus:
    *   Memastikan properti ekses tidak bocor ke instance objek keluaran (gunakan ekstraksi key dinamis murni).
    *   Mengembalikan objek immutable menggunakan `Object.freeze()`.
    *   Menguji penolakan compile-time jika data manipulatif dimasukkan.

#### Starter Code Template:

```typescript
// Jalankan dengan: npx ts-node practical_exercise.ts

// 1. Definisikan Brand Symbols & Types di sini...

// 2. Definisikan Guards & Validators di sini...

// 3. Implementasikan Parser/Sanitizer Core:
export function parseUserProfile(payload: unknown): UserProfile {
  // Implementasikan logika validasi bentuk dan deep-strip di sini
  throw new Error("Belum diimplementasikan");
}

// 4. Verifikasi Test Cases
function runTest() {
  const dirtyExternalPayload = {
    id: "usr_109283",
    email: "alex@company.com",
    displayName: "Alex",
    tier: "PREMIUM",
    maliciousInjectedField: "DROP TABLE users;",
    role: "SUPERADMIN"
  };

  try {
    const cleanProfile = parseUserProfile(dirtyExternalPayload);
    console.log("Sanitized Object:", cleanProfile);
    
    // VERIFIKASI:
    // 1. Properti 'maliciousInjectedField' dan 'role' TIDAK BOLEH ADA di cleanProfile
    // @ts-expect-error - Akses properti ilegal harus memicu error compile
    console.log(cleanProfile.role);
    
    // 2. cleanProfile harus immutable
    // @ts-expect-error - Mutasi dilarang
    cleanProfile.displayName = "Hacked";
    
    console.log("Semua verifikasi integritas kontrak shape berhasil lolos!");
  } catch (err) {
    console.error("Pipeline gagal:", (err as Error).message);
  }
}

runTest();
```