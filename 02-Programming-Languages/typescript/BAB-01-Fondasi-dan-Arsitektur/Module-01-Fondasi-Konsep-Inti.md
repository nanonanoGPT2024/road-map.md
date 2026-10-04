# Bab 01: Fondasi Sistem Tipe & Kompilasi
## Module 01: Arsitektur TypeScript Compiler (tsc) & Sistem Tipe Struktural

---

### 1. Title & Metadata
* **Modul**: Bab 01 — Module 01: Arsitektur TypeScript Compiler (`tsc`) & Sistem Tipe Struktural (*Structural Type System*)
* **Tingkat Kesulitan**: Intermediate to Advanced
* **Prasyarat**: Pemahaman mendalam tentang JavaScript (ECMAScript 2015+), Event Loop, prototipe objek, dan ekosistem Node.js/NPM.
* **Target Ekosistem**: TypeScript 5.x+, Node.js LTS, Runtime V8.

---

### 2. Ringkasan Eksekutif (Executive Summary)
TypeScript bukan sekadar "JavaScript dengan tipe data", melainkan sistem analisis statis formal yang bekerja melalui kompilator multi-tahap (*multi-stage compiler*) untuk mentransformasikan *Abstract Syntax Tree* (AST) menjadi JavaScript sembari memvalidasi tipe tanpa menimbulkan *runtime overhead*. 

Modul ini membedah arsitektur internal TypeScript Compiler (`tsc`)—mulai dari tokenisasi hingga fase *emit*—serta mengupas mekanika inti dari *Structural Type System* (Duck Typing matematis) vs *Nominal Type System*. Di akhir modul ini, Anda akan memahami bagaimana compiler mengevaluasi tipe data, mengapa validasi kompilasi hilang di runtime (*type erasure*), dan bagaimana merancang arsitektur sistem tipe statis yang modular, aman, serta memiliki performa tinggi pada aplikasi skala enterprise.

---

### 3. Tujuan Pembelajaran (Learning Objectives)
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis (C4)** pipeline kompilasi internal TypeScript: `Scanner` -> `Parser` -> `Binder` -> `Checker` -> `Emitter`.
2. **Membedakan (C4)** karakteristik mekanis antara *Structural Typing* dan *Nominal Typing*, serta implikasinya terhadap relasi subtiping (*subtyping relations*).
3. **Mendiagnosis (C4)** perilaku evaluasi tipe seperti *Fresh Object Literal Excess Property Checks* dan *Type Erasure*.
4. **Mengimplementasikan (C3)** teknik *Nominal Branding/Flavoring* untuk memaksakan keamanan domain-driven design pada sistem tipe struktural.
5. **Mengevaluasi (C5)** trade-off performa waktu kompilasi (*type checking cost*) terhadap fleksibilitas developer experience (DX).

---

### 4. Konsep Kunci & Terminologi
* **Type Erasure**: Proses penghapusan seluruh anotasi, interface, type alias, dan metadata tipe lainnya oleh kompilator selama fase *emit*, menghasilkan JavaScript murni tanpa jejak tipe TypeScript di runtime.
* **Structural Typing**: Sistem pengetikan di mana kompatibilitas dan ekivalensi tipe didasarkan secara eksklusif pada bentuk (*shape* / struktur member) tipe tersebut, bukan pada nama atau deklarasi eksplisitnya.
* **Nominal Typing**: Sistem pengetikan (seperti di Java, C#, Rust) di mana kompatibilitas tipe ditentukan oleh nama kelas atau deklarasi hierarki tipe secara eksplisit.
* **Soundness vs Unsoundness**: *Soundness* adalah garansi matematis bahwa program tidak akan pernah mengalami evaluasi runtime invalid jika lolos validasi statis. TypeScript secara sadar bersifat *partially unsound* demi pragmatisme kompatibilitas JavaScript (contoh: array mutability, function parameter bivariance).
* **Abstract Syntax Tree (AST)**: Representasi pohon struktural hierarkis dari kode sumber yang dihasilkan oleh parser.
* **Symbol Table**: Struktur data internal yang memetakan deklarasi identifier ke entitas semantik yang diacu di seluruh AST.

---

### 5. Mengapa Konsep Ini Penting (The 'Why')
Banyak developer mengalami hambatan dalam skala enterprise karena memperlakukan TypeScript layaknya Java/C# atau sekadar "linter". Ketidakpahaman atas arsitektur compiler memicu dua masalah kritis:
1. **Runtime Bugs Akibat Type Erasure Assumption**: Mengasumsikan `if (input instanceof MyInterface)` valid, atau percaya bahwa validasi TypeScript melindungi aplikasi dari data dinamis (API eksternal, deserialisasi JSON) di runtime.
2. **Kompilasi Lambat & Degenerasi Tipe**: Pembuatan tipe rekursif yang tidak efisien yang membebani tahap *Checker* compiler, melumpuhkan IDE (Language Server Protocol/TSServer), dan memperlambat pipeline CI/CD secara eksponensial.

Memahami *structural typing* dan alur kerja `tsc` memungkinkan perancangan sistem piranti lunak yang memvalidasi integritas data pada *edge boundary* runtime secara tepat, sekaligus mengoptimalkan waktu kompilasi statis.

---

### 6. Apa Sebenarnya Konsep Ini (The 'What')
TypeScript adalah sistem tipe statis struktural yang bekerja di atas JavaScript. Terdapat dua pondasi utama:

#### 1. Arsitektur Kompilasi
Kompilator TypeScript bekerja sebagai *source-to-source compiler* (transpiler) serta *static analysis engine*. Berbeda dengan compiler native (seperti Rust/Go yang menghasilkan binary machine code via LLVM), target akhir `tsc` adalah kode JavaScript standar dan deklarasi definisi (`.d.ts`). Arsitektur ini dirancang deterministik melalui modul internal:
* **Program**: Orkestrator utama yang memuat file konfigurasi (`tsconfig.json`) dan mengelola siklus kompilasi.
* **SourceFile**: Representasi teks kode sumber yang diurai.
* **Scanner**: Lexer yang memecah stream karakter menjadi token stream.
* **Parser**: Mengonversi token stream menjadi AST nodes.
* **Binder**: Mengaitkan AST node ke dalam `Symbols` untuk membentuk scope chain dan *Symbol Table*.
* **Checker**: Komponen terberat (mengonsumsi 80%+ waktu kompilasi); memvalidasi semantik tipe, menghitung inferensi, dan memeriksa kompatibilitas bentuk tipe.
* **Emitter**: Menghasilkan file output (`.js`, `.jsx`, `.d.ts`, `.js.map`).

#### 2. Mekanisme Structural Typing
Secara matematis, jika tipe $T$ memiliki sekumpulan properti $P_T$, dan tipe $S$ memiliki properti $P_S$, maka $S$ adalah subtipe dari $T$ ($S \subseteq T$) jika dan hanya jika:
$$\forall p \in P_T, \quad p \in P_S \land \text{Type}(S.p) \le \text{Type}(T.p)$$

Artinya: $S$ kompatibel dengan $T$ selama $S$ memiliki *setidaknya seluruh properti yang dibutuhkan oleh $T$* dengan tipe yang kompatibel, terlepas dari apakah $S$ dideklarasikan secara eksplisit untuk mengimplementasikan $T$ atau tidak.

---

### 7. Diagram Arsitektur / Alur Kerja

```
+-------------------------------------------------------------------------+
|                       TypeScript Compiler (tsc) Engine                  |
+-------------------------------------------------------------------------+
                                     |
                                     v
                           +-------------------+
                           | Source Code (.ts) |
                           +-------------------+
                                     |
                                     | Lexical Analysis
                                     v
                           +-------------------+
                           |      Scanner      |
                           +-------------------+
                                     |
                                     | Token Stream
                                     v
                           +-------------------+
                           |      Parser       | <---+ Syntactic Diagnostics
                           +-------------------+     | (Syntax Errors)
                                     |               |
                                     | AST (Abstract Syntax Tree)
                                     v
                           +-------------------+
                           |      Binder       |
                           +-------------------+
                                     |
                                     | Symbols / Symbol Table
                                     v
                           +-------------------+
                           |   Type Checker    | <---+ Semantic Diagnostics
                           +-------------------+     | (Type Errors)
                                     |
                   +-----------------+-----------------+
                   | (Jika `noEmitOnError: false`     |
                   |  atau tidak ada error)           |
                   v                                   v
         +-------------------+               +-------------------+
         |   Emitter (.js)   |               | Emitter (.d.ts)   |
         +-------------------+               +-------------------+
                   |                                   |
                   v                                   v
           Clean JavaScript                     Type Declarations
         (Runtime Execution)                    (Distribution)
```

---

### 8. Bagaimana Cara Kerjanya di Balik Layar (How It Works Under the Hood)

#### Tahapan Eksekusi Kompilator
1. **Scanning (Lexing)**: `Scanner` membaca karakter demi karakter kode sumber dan menghasilkan token skalar numerik (contoh: `TokenFlags`, `SyntaxKind.Identifier`, `SyntaxKind.NumericLiteral`).
2. **Parsing**: `Parser` mengonsumsi token dari `Scanner` dan membangun pohon hierarkis (`Node` AST). Tiap node menyimpan referensi ke posisi baris/kolom dan hubungan parent-child. Pada titik ini, compiler hanya mendeteksi sintaksis yang salah (misal: kurung kurawal yang tidak ditutup).
3. **Binding**: `Binder` melintasi AST sekali jalan (*single pass*) tanpa mengevaluasi tipe. Tujuannya adalah membuat `Symbol`. `Symbol` menghubungkan deklarasi identifier (misal: `let x` dan `function x`) dengan cakupan lexical-nya (*Scope Chain*). Setiap node di AST yang mendeklarasikan identitas akan diberikan pointer ke `Symbol`-nya.
4. **Type Checking**: `TypeChecker` menginisialisasi inferensi dan verifikasi tipe. Ketika sebuah node diproses:
   * Checker mengambil `Symbol` dari node tersebut.
   * Checker melakukan resolusi tipe (*Type Resolution*), menghitung relasi *assignability*.
   * Menggunakan aturan struktural: mengiterasi seluruh properti yang dibutuhkan oleh target type dan mencocokkannya secara rekursif dengan source type.
   * Mengeksekusi penanganan khusus: **Excess Property Checks** diaktifkan khusus jika sumber objek merupakan *fresh object literal* (bukan referensi variabel).
5. **Emitting**: `Emitter` membaca AST dan men-strip seluruh konstruksi tipe (interface, types, type arguments, enum metadata transformasi), kemudian menulis file output target ECMAScript yang ditentukan oleh opsi `target` pada compiler options.

---

### 9. Implementasi Dasar (Simple Code Example)

```typescript
// Demonstrasi Sistem Tipe Struktural vs Excess Property Checking

interface UserCoordinate {
  x: number;
  y: number;
}

function renderPoint(point: UserCoordinate): string {
  return `Point rendered at: X=${point.x}, Y=${point.y}`;
}

// 1. Structural Compatibility murni via referensi
const externalSensorData = {
  x: 10,
  y: 20,
  z: 30, // Properti ekses
  timestamp: Date.now(),
};

// VALID: externalSensorData memiliki 'x' dan 'y' bertipe number.
// Properti ekstra ('z', 'timestamp') diabaikan (Width Subtyping).
renderPoint(externalSensorData);

// 2. Excess Property Check pada Fresh Object Literal
// ERROR: Object literal may only specify known properties, and 'z' does not exist in type 'UserCoordinate'.
/*
renderPoint({
  x: 10,
  y: 20,
  z: 30, 
});
*/

// 3. Bukti Type Erasure di Runtime
console.log(typeof renderPoint); // "function"
// Di runtime, interface 'UserCoordinate' lenyap sepenuhnya.
// Tidak ada instruksi evaluasi struktur yang tersisa di dalam file .js yang dihasilkan.
```

---

### 10. Bedah Kode Dasar (Code Breakdown)
* `interface UserCoordinate`: Mendefinisikan kontrak bentuk tipe. Pada fase kompilasi, ini direpresentasikan sebagai `InterfaceType` di dalam `TypeChecker`. Di runtime, kode ini menghasilkan **nol byte** JavaScript.
* `renderPoint(externalSensorData)`: Lolos kompilasi karena variabel `externalSensorData` dievaluasi menggunakan aturan dasar *structural assignability*. Variabel tersebut adalah *non-fresh object reference*, sehingga compiler memverifikasi bahwa properti `x` dan `y` tersedia dan bertipe kompatibel, mengabaikan ekses `z` dan `timestamp`.
* `renderPoint({ x: 10, y: 20, z: 30 })`: Kompilator memicu *Fresh Object Literal Excess Property Check*. Karena objek dibuat langsung (*inline* / *fresh*) pada pemanggilan fungsi, TypeScript mengasumsikan adanya kesalahan ketik (*typo*) atau bug logika dari developer karena properti `z` tidak akan pernah bisa diakses oleh fungsi `renderPoint`, sehingga kompilator memunculkan error meskipun secara struktural kompatibel.

---

### 11. Implementasi Tingkat Produksi (Production-Grade Implementation)

Sistem finansial memerlukan jaminan validitas ID entitas. Pada sistem tipe struktural murni, tipe primitif rentan mengalami substitusi tidak sengaja (misal: `AccountId` tertukar dengan `TransactionId` karena keduanya bertipe `string`). Kita memecahkan batasan ini menggunakan teknik *Nominal Branding (Type Tagging)* yang zero-overhead di runtime.

```typescript
/**
 * Core Production Engine: Zero-Runtime Branded Types Subsystem
 */

// 1. Brand Helper Mechanics
declare const __brand: unique symbol;

export type Branded<T, TBrand extends string> = T & {
  readonly [__brand]: TBrand;
};

// 2. Domain Types Berbasis Structural Emulated Nominals
export type AccountId = Branded<string, 'AccountId'>;
export type TransactionId = Branded<string, 'TransactionId'>;
export type Microcents = Branded<bigint, 'Microcents'>;

// 3. Runtime Assertion Engine & Constructor Boundary
export class EntityIdFactory {
  private static readonly ACCOUNT_REGEX = /^acc_[a-zA-Z0-9]{16}$/;
  private static readonly TX_REGEX = /^tx_[a-zA-Z0-9]{24}$/;

  public static createAccountId(rawId: string): AccountId {
    if (!this.ACCOUNT_REGEX.test(rawId)) {
      throw new Error(`Invariant Violation: Incompatible AccountId format: ${rawId}`);
    }
    // Safe Cast: Runtime invariants divalidasi sebelum branding diterapkan
    return rawId as AccountId;
  }

  public static createTransactionId(rawId: string): TransactionId {
    if (!this.TX_REGEX.test(rawId)) {
      throw new Error(`Invariant Violation: Incompatible TransactionId format: ${rawId}`);
    }
    return rawId as TransactionId;
  }
}

export class CurrencyEngine {
  public static toMicrocents(amount: number): Microcents {
    if (!Number.isFinite(amount) || amount < 0) {
      throw new Error(`Invalid monetary amount: ${amount}`);
    }
    // Konversi presisi float ke integer bigint representation
    const micro = BigInt(Math.round(amount * 1_000_000));
    return micro as Microcents;
  }
}

// 4. Domain Transaction Ledger Service
export interface TransferRequest {
  readonly transactionId: TransactionId;
  readonly sourceAccountId: AccountId;
  readonly destinationAccountId: AccountId;
  readonly amount: Microcents;
}

export class LedgerDomainService {
  public processTransfer(request: TransferRequest): void {
    if (request.sourceAccountId === request.destinationAccountId) {
      throw new Error('Self-transfer is forbidden.');
    }

    // Eksekusi logic internal...
    this.recordTransaction(request);
  }

  private recordTransaction(req: TransferRequest): void {
    // Structural type checking menjamin integritas tipe domain
    const logPayload = {
      tx: req.transactionId,
      from: req.sourceAccountId,
      to: req.destinationAccountId,
      amt: req.amount.toString(),
    };
    // Emit ledger entry
    process.stdout.write(JSON.stringify(logPayload) + '\n');
  }
}

// 5. Verifikasi Kompilasi & Pengujian Kasus Salah
function execute() {
  const service = new LedgerDomainService();

  const sourceAccount = EntityIdFactory.createAccountId('acc_01h7abcde1234567');
  const destAccount = EntityIdFactory.createAccountId('acc_01h7xyzab9876543');
  const txId = EntityIdFactory.createTransactionId('tx_01h7transact0123456789abc');
  const balance = CurrencyEngine.toMicrocents(150.75);

  // Kompilasi Berhasil
  service.processTransfer({
    transactionId: txId,
    sourceAccountId: sourceAccount,
    destinationAccountId: destAccount,
    amount: balance,
  });

  // UJI KESALAHAN TIPE (Type-Check Failures):
  const rawString = 'acc_01h7abcde1234567';

  /*
  // @ts-expect-error Type 'string' is not assignable to type 'AccountId'
  service.processTransfer({
    transactionId: txId,
    sourceAccountId: rawString, // ERROR: String biasa bukan AccountId
    destinationAccountId: destAccount,
    amount: balance,
  });

  // @ts-expect-error Type 'AccountId' is not assignable to type 'TransactionId'
  service.processTransfer({
    transactionId: sourceAccount, // ERROR: Mencegah swap ID antar domain entitas yang berbeda
    sourceAccountId: sourceAccount,
    destinationAccountId: destAccount,
    amount: balance,
  });
  */
}

execute();
```

---

### 12. Analisis Kasus Penggunaan Riil (Real-World Case Study)
Pada sistem transaksi core-banking, kegagalan terbesar pada arsitektur monolit berbasis Node.js murni adalah tercampurnya unit moneter (misal: *Cents*, *Dollars*, dan *Satoshi*) dan identifier entitas karena semuanya dievaluasi sebagai tipe dasar primitif `number` atau `string`.

**Masalah**: Developer memanggil `transferFunds(senderId, receiverId, amount)` namun secara tidak sengaja memanggil `transferFunds(receiverId, senderId, amount)` atau menyuplai `amount` dalam format dollar padahal fungsi membutuhkan cents.

**Solusi Arsitektural**:
1. Mengintegrasikan *compile-time nominal emulation* (Branded Types) pada data transfer object (DTO).
2. Memposisikan *Parser Boundary* di network gateway (menggunakan skema validasi Zod/ArkType yang me-return branded types).
3. Melarang penggunaan tipe primitif mentah (`string`, `number`) pada business logic layer, menggantinya secara mutlak dengan type brand yang diurai oleh Type Checker saat kompilasi.

**Hasil**: Seluruh kesalahan urutan passing argumen dan konversi mata uang terdeteksi seketika pada siklus CI/CD via `tsc --noEmit`, memotong 100% bug pertukaran parameter di level domain sebelum runtime deployment.

---

### 13. Analisis Komparasi & Trade-offs (Trade-off Matrix)

| Dimensi | Nominal Typing (e.g., C#, Java) | Structural Typing (TypeScript Standard) | Emulated Nominal (Branded Types) |
| :--- | :--- | :--- | :--- |
| **Resolusi Kesetaraan Tipe** | Eksplisit berdasarkan nama dan namespace deklarasi tipe. | Bentuk struktur dan ketersediaan member field. | Kombinasi struktur bentuk + phantom type token unik. |
| **Fleksibilitas Desain Kode** | Kaku; perlu adapter pattern / deklarasi inheritance eksplisit. | Sangat fleksibel; ideal untuk arsitektur terdistribusi & JSON payload. | Moderat; memaksa validasi sebelum assignment dilakukan. |
| **Overhead Waktu Kompilasi** | Cepat (pencocokan nama tipe adalah operasi hash map lookup $O(1)$). | Lebih lambat (komparasi rekursif antar properti struktur tipe $O(N)$). | Sedikit lebih lambat dari structural murni karena evaluasi intersection. |
| **Beban Runtime Memory/CPU** | Terikat metadata kelas di runtime. | **0 byte** overhead runtime (*completely erased*). | **0 byte** overhead runtime (simbol bersifat phantom). |
| **Injeksi Data Dinamis** | Membutuhkan explicit casting/deserializer formal. | Langsung memetakan objek JSON sembarang asal struktur cocok. | Membutuhkan factory function/type guard assertion gate. |

---

### 14. Anti-Patterns & Common Pitfalls

#### Anti-Pattern 1: Type Guarding Tipe TypeScript di Runtime
```typescript
// ANTI-PATTERN:
interface PaymentPayload {
  amount: number;
}

function processPayment(data: unknown) {
  // ERROR DI JAVASCRIPT RUNTIME: 'PaymentPayload' only refers to a type, 
  // but is being used as a value here.
  // if (data instanceof PaymentPayload) { ... }
}
```
*Mengapa ini salah*: Interface adalah konstruksi tipe statis yang dihapus (*erased*) saat kompilasi. Interface tidak pernah ada di runtime JavaScript, sehingga tidak bisa digunakan dengan operator runtime seperti `instanceof`.

#### Anti-Pattern 2: Asumsi Keamanan Type Assertion (`as`) Tanpa Validasi
```typescript
// ANTI-PATTERN:
function parseApiResponse(jsonString: string): UserCoordinate {
  // BAHAYA: Mengabaikan arsitektur structural checker secara paksa.
  // Jika JSON menghasilkan struktur lain, runtime akan crash ketika mengakses .x
  return JSON.parse(jsonString) as UserCoordinate; 
}
```
*Mengapa ini salah*: Operator `as` adalah instruksi eksplisit kepada *Type Checker* untuk mematikan validasi dan mempercayai developer secara membabi-buta. Ini merusak integritas *type safety* bila data sumber berasal dari external boundaries.

---

### 15. Praktik Terbaik & Panduan Desain (Best Practices & Guidelines)
* **Kompilasi dengan `--isolatedModules`**: Pastikan kode dapat dikompilasi oleh transpiler berkas-tunggal (*single-file transpilernya* Babel, SWC, esbuild) yang tidak melakukan evaluasi type tree komprehensif. Hindari `const enum` non-inlined atau export/import type ambigu tanpa modifier `export type`.
* **Aktifkan `--strict` Secara Global**: Aktifkan flag `strict: true` di `tsconfig.json`. Ini mencakup `noImplicitAny`, `strictNullChecks`, `strictFunctionTypes`, dan `strictBindCallApply`.
* **Gunakan Explicit Type Imports**: Gunakan sintaks `import type { Foo } from './foo'` untuk membantu *Emitter* membuang modul dependensi yang hanya dibutuhkan untuk kebutuhan kompilasi, mencegah timbulnya *circular runtime dependency*.
* **Definisikan Domain Boundaries**: Jangan biarkan data luar meresap ke dalam core logic sebelum melewati schema parser. Validasi data di boundary eksternal runtime, lakukan branding pada tipenya, lalu kirim tipe branded tersebut ke domain layer.

---

### 16. Aspek Keamanan & Performa

#### Keamanan
* TypeScript **TIDAK** menjamin runtime security. TypeScript dirancang untuk developer safety, bukan adversarial runtime security. Penyerang (*attacker*) yang menginjeksi payload JSON berbahaya ke API Node.js tidak akan terhalang oleh anotasi tipe.
* Gunakan runtime schema validation (Zod, Valibot, TypeBox) di boundary aplikasi untuk menjamin data conform terhadap bentuk tipe sebelum dikonsumsi.

#### Performa Kompilasi (*Compiler Performance*)
* Komparasi struktural yang melibatkan *deeply nested union types* memicu kompleksitas kombinatorial pada fase *Checker*.
* Kurangi pembuatan *anonymous type expansion*. Gunakan `interface` alih-alih `type alias` untuk pendefinisian bentuk objek standar; kompilator meng-cache resolusi `interface` berdasarkan nama simbol jauh lebih efisien dibanding *flattening* `type` intersections (`&`).

---

### 17. Panduan Debugging & Troubleshooting (Debugging Runbook)

#### Skenario: "Property 'z' is missing in type 'A' but required in type 'B'" padahal variabel terlihat identik.
1. **Diagnosis Simbol**: Periksa apakah ada dua deklarasi tipe berbeda dengan nama yang sama yang diimpor dari dua module path yang berbeda (duplikasi symlink atau mismatch versi di `node_modules`).
2. **Inspeksi AST & Tracing**:
   Jalankan diagnosis tracing compiler via CLI:
   ```bash
   npx tsc --noEmit --generateTrace ./trace-output
   ```
   Buka file trace di `chrome://tracing` untuk melihat method mana di `TypeChecker` yang memakan waktu lama atau tipe mana yang memicu infinite expansion loop.
3. **Melihat Output Emit Riil**:
   Gunakan command berikut untuk memvalidasi bagaimana type erasure mentransformasi kode Anda:
   ```bash
   npx tsc path/to/file.ts --target esnext --moduleResolution nodenext --noEmit false
   ```
   Bandingkan file `.ts` dengan file output `.js` yang dihasilkan untuk melihat kode struktural yang bertahan di runtime.

---

### 18. Ringkasan & Takeaways
* Compiler TypeScript (`tsc`) memproses kode melalui pipa lima lapis: `Scanner` -> `Parser` -> `Binder` -> `Checker` -> `Emitter`.
* Fase *Checker* mengevaluasi logika tipe; fase *Emitter* men-strip seluruh anotasi tipe (**Type Erasure**).
* TypeScript menggunakan **Structural Typing**, di mana kesetaraan didasarkan pada bentuk dan kompatibilitas member, bukan penamaan eksplisit.
* **Fresh object literals** tunduk pada *Excess Property Checks*, sebuah deviasi pragmatis dari pure structural subtyping untuk mendeteksi bug programmer.
* Tipe primitif dapat disimulasikan menjadi nominal menggunakan teknik **Nominal Branding**, menjamin keamanan domain tanpa menimbulkan biaya (*zero-cost*) di runtime.

---

### 19. Latihan Mandiri & Tantangan Kode

#### Latihan 1 (Tingkat Menengah)
Diberikan struktur tipe berikut:
```typescript
type Point2D = { x: number; y: number };
type Point3D = { x: number; y: number; z: number };
```
Buat fungsi `calculateDistance(p1: Point2D, p2: Point2D): number`. Jelaskan secara tertulis mengapa Anda bisa memasukkan argumen bertipe `Point3D` ke dalam parameter `Point2D`, dan buktikan mekanisme apa yang terjadi di internal *Type Checker*.

#### Latihan 2 (Tantangan Tingkat Lanjut)
Implementasikan sistem *Branded Currency Types* yang aman secara matematis untuk transaksi bursa multi-mata uang:
* Buat Type Brand untuk `USD` dan `EUR`.
* Implementasikan tipe data `Rate<From, To>` yang merepresentasikan kurs pertukaran.
* Buat fungsi `exchange<From extends string, To extends string>(amount: Branded<bigint, From>, rate: Rate<From, To>): Branded<bigint, To>`.
* Pasang batasan di mana mengalikan `USD` dengan rate `EUR -> JPY` akan memicu error pada tingkat kompilator statis TypeScript.

---

### 20. Referensi & Bacaan Lanjutan
* **TypeScript Compiler Internals Wiki**: https://github.com/microsoft/TypeScript/wiki/Architectural-Overview
* **TypeScript Language Specification (Archived Formal Spec)**: https://github.com/microsoft/TypeScript/blob/main/doc/spec-ARCHIVED.md
* **Type Systems: A Polymer Model of Subtyping**: Pierce, B. C. (2002). *Types and Programming Languages* (TAPL). MIT Press. (Bab: Structural Subtyping & Equi-recursive Types).
* **Source Code Reference**: `src/compiler/checker.ts` pada repositori resmi `microsoft/TypeScript`.