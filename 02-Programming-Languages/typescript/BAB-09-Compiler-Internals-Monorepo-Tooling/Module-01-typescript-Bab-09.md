# Bab 09 Module 01: Compiler Internals & Monorepo Tooling

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: TS-ENG-0901
* **Jalur Kurikulum**: 02-Programming-Languages / TypeScript
* **Tingkat Kesulitan**: Advanced / L4-L5 Engineering
* **Prasyarat**:
  * Penguasaan mendalam terhadap *Advanced Types* (Conditional Types, Template Literal Types, Mapped Types).
  * Pemahaman mendasar terkait siklus hidup kompilasi kode (Lexing, Parsing, Abstract Syntax Tree).
  * Pengalaman operasional dengan manajer paket modern (`pnpm`, `yarn`, atau `npm`) serta konfigurasi dasar `tsconfig.json`.
* **Estimasi Waktu Belajar**: 8 Jam Pembelajaran Mandiri + 4 Jam Hands-on Lab.
* **Target Kompetensi**:
  * Menguasai arsitektur 5 tahap kompilator TypeScript (`Scanner` $\to$ `Parser` $\to$ `Binder` $\to$ `Checker` $\to$ `Emitter`).
  * Mampu mengoperasikan TypeScript Compiler API secara programatik untuk analisis AST dan linting kustom.
  * Mampu merancang, mengonfigurasi, dan mengoptimalkan arsitektur monorepo skala enterprise menggunakan *Project References*, *Composite Projects*, dan *Incremental Compilation*.
  * Mampu menganalisis profil performa tipe dan mendiagnosis bottleneck kompilasi melalui *Tracing* dan *Extended Diagnostics*.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:

1. **Menganalisis (C4)** siklus hidup kompilasi kode TypeScript internal dan membedakan alokasi tanggung jawab antara `Scanner`, `Parser`, `Binder`, `TypeChecker`, dan `Emitter`.
2. **Merancang (C6)** struktur monorepo multi-package berkinerja tinggi menggunakan teknik *Project References* dan *Composite Projects* dengan resolusi dependensi Directed Acyclic Graph (DAG).
3. **Mengonfigurasi (C3)** file manifest kompilasi (`tsconfig.json`) terdistribusi untuk memisahkan siklus hidup *type-checking* murni dari *code emission*, serta mengaktifkan isolasi transpilasi.
4. **Mengevaluasi (C5)** performa kompilasi monorepo berbasis trace telemetry (`--generateTrace` dan visualizer Chromium tracing) guna memitigasi bottleneck tipe rekursif.
5. **Mengimplementasikan (C3)** skrip diagnostik AST berbasis TypeScript Compiler API untuk memeriksa dan memvalidasi arsitektur internal paket monorepo secara deterministik.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model 1: Pipeline Kompilator Sebagai State Machine Transformasional
Jangan memandang `tsc` sebagai sebuah *black-box transpiler* yang mengubah berkas `.ts` langsung menjadi `.js`. Pandang kompilator TypeScript sebagai serangkaian *state machine* bertahap (*staged pipeline*) yang memisahkan sintaksis murni dari semantik tipe.
1. **Scanner** membaca stream teks menjadi kumpulan token leksikal (karakter tanpa makna semantik).
2. **Parser** mengelompokkan token menjadi *Abstract Syntax Tree* (AST) dengan representasi pohon sintaksis murni.
3. **Binder** menghubungkan node-node deklarasi ke dalam struktur `Symbol` yang mendefinisikan scope dan visibility tanpa mengevaluasi validitas tipenya.
4. **Checker** (fase terberat secara komputasi) melakukan inferensi tipe, menyelaraskan `AST Node` dengan `Symbol` untuk menghasilkan instansiasi `Type`, dan mengevaluasi batasan statis (*type constraints*).
5. **Emitter** mencetak AST ke format teks target (`.js`, `.d.ts`, `.map`) sembari melucuti konstruksi tipe murni.

```
[Raw Text] -> Scanner -> [Tokens] -> Parser -> [AST]
                                                 |
                                               Binder -> [Symbols]
                                                           |
                               TypeChecker <---------------+
                                    |
                           [Diagnostics / Errors]
                                    |
                                 Emitter -> [.js / .d.ts]
```

### Mental Model 2: Monorepo Sebagai Directed Acyclic Graph (DAG) Terisolasi
Dalam repositori multi-paket, kesalahan konsepsi terbesar adalah memperlakukan seluruh kode sebagai satu kesatuan kompilasi monolithic (`tsc` dipanggil pada root folder yang melintasi ribuan berkas sekaligus). 

Mental model yang benar: **Monorepo adalah DAG dari unit-unit kompilasi independen.** Setiap paket adalah simpul (*node*), dan dependensi antar paket adalah sisi berarah (*directed edge*). Melalui *Project References*, setiap paket harus memiliki batas *cache* terisolasi berupa artefak deklarasi (`.d.ts`) dan status inkremental (`.tsbuildinfo`). Paket konsumen tidak boleh mengevaluasi AST dari paket sumber secara mentah; paket konsumen **hanya boleh membaca deklarasi tipe publik** yang telah dicompile oleh paket produsen.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram 1: Pipeline Internal Kompilator TypeScript

```
+--------------------------------------------------------------------------------+
|                         TypeScript Compiler Pipeline                           |
+--------------------------------------------------------------------------------+
| Source Code (.ts)                                                              |
|        |                                                                       |
|        v                                                                       |
|  +------------+                                                                |
|  |  Scanner   |  Tokenization (Keyword, Identifier, Punctuation)               |
|  +------------+                                                                |
|        | Token Stream                                                          |
|        v                                                                       |
|  +------------+                                                                |
|  |   Parser   |  Syntactic Analysis -> Menghasilkan SourceFile AST Node       |
|  +------------+                                                                |
|        | AST (Node)                                                            |
|        v                                                                       |
|  +------------+                                                                |
|  |   Binder   |  Menginisialisasi Symbol Table & Flow Nodes (Scope Isolation)  |
|  +------------+                                                                |
|        | AST + Symbols                                                         |
|        v                                                                       |
|  +------------+                                                                |
|  |   Checker  |  Semantic Analysis & Type Checking (Siklus Komputasi Berat)   |
|  +------------+  - Resolusi Relasi Tipe                                        |
|        |         - Validasi Substitutabilitas                                  |
|        +-----------------------------------+                                   |
|        | Validasi Sukses                   | Menemukan Typo / Incompatibilities|
|        v                                   v                                   |
|  +------------+                     +-------------+                            |
|  |  Emitter   |                     | Diagnostics | -> [Output Console/Errors] |
|  +------------+                     +-------------+                            |
|        |                                                                       |
|        +-------------------+--------------------+                              |
|        v                   v                    v                              |
| JavaScript (.js)    Declaration (.d.ts)   Source Maps (.js.map/.d.ts.map)     |
+--------------------------------------------------------------------------------+
```

### Diagram 2: Topologi Monorepo Berbasis Project References (DAG)

```
                  +-----------------------------------+
                  |        @monorepo/tsconfig         |
                  |     (Base Configurations)         |
                  +-----------------+-----------------+
                                    | extends
         +--------------------------+--------------------------+
         |                                                     |
         v                                                     v
+-----------------------------+               +-----------------------------+
|    @monorepo/domain-core    |               |      @monorepo/utility      |
|  (composite: true)          |               |    (composite: true)        |
|  Outputs: dist/*.d.ts       |               |    Outputs: dist/*.d.ts     |
+--------------+--------------+               +--------------+--------------+
               ^                                             ^
               | references                                  | references
               +----------------------+----------------------+
                                      |
                       +--------------+--------------+
                       |     @monorepo/api-server    |
                       |  (composite: true)          |
                       |  Consumes: .d.ts from DAG   |
                       +-----------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Hubungan Inti Kompilator: Node, Symbol, dan Type
Kompilator mengelola tiga entitas utama yang sering disalahpahami:
* **Node (AST Node)**: Representasi sintaksis konkret dari potongan kode dalam berkas sumber. Contoh: `ts.Identifier`, `ts.BinaryExpression`. Node menyimpan informasi posisi fisik teks (baris, kolom, offset).
* **Symbol**: Entitas bernama yang merepresentasikan *storage location* logis atau entitas semantik (seperti variabel, fungsi, interface, atau class). Node dideklarasikan oleh Symbol. Satu Symbol dapat dihubungkan ke beberapa Node AST (contohnya pada kasus *Declaration Merging* di mana sebuah `interface` dan `namespace` memiliki nama yang sama).
* **Type**: Representasi semantik komputasional yang diproduksi secara dinamis oleh `TypeChecker`. Instansiasi `Type` tidak selalu memiliki representasi kode statis langsung (seperti Union Type anonim, Intersection Type, atau hasil evaluasi *Conditional Type*). `Type` mengevaluasi kompatibilitas penugasan (*assignability*).

### 2. State Inkremental & Cache: `.tsbuildinfo`
Ketika flag `"composite": true` atau `"incremental": true` diaktifkan, kompilator membuat berkas manifest serialisasi JSON binary/text dengan ekstensi `.tsbuildinfo`. Berkas ini memuat:
* **File Hashes**: Hash kriptografis dari konten berkas masukan (`.ts`) dan berkas konfigurasi (`tsconfig.json`).
* **Dependency Graph**: Struktur graf relasi internal paket yang memetakan berkas mana yang mengimpor berkas mana.
* **Emit Signatures**: Hash dari interface publik/tipe yang diekspor (`.d.ts`). Jika berkas `A.ts` diubah implementasi internalnya namun tanda tangan tipe publiknya tidak berubah, kompilator menggunakan cache `.tsbuildinfo` untuk mencegah kompilasi ulang pada modul `B.ts` yang mengimpor `A.ts`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Fase 1: Scanner (Lexical Analysis)
Scanner bertindak atas buffer teks UTF-16 murni. Menggunakan skema traversal berbasis pointer performa tinggi, Scanner memecah deretan karakter menjadi nilai enum diskret (`ts.SyntaxKind`). Scanner dioptimalkan untuk meminimalkan alokasi objek pada heap V8; ia mempertahankan status internal (`cursor position`, `token value`) dan mengembalikan representasi integer dari token tersebut.

### Fase 2: Parser (Syntactic Analysis)
Parser mengonsumsi Scanner untuk membangun AST rekursif yang berakar pada simpul `SourceFile`. Parsing TypeScript bersifat linear $O(N)$ terhadap ukuran token, menggunakan paradigma *Recursive Descent Parsing* dengan *lookahead token backtracking*. Jika parser menemukan token yang melanggar gramatika baku TypeScript, proses parsing tidak langsung berhenti; ia mengeksekusi *error recovery strategy* dengan menyisipkan synthetic node (`ts.SyntaxKind.MissingDeclaration`) agar dapat terus mengurai sisa berkas dan mengumpulkan sebanyak mungkin kesalahan sintaksis.

### Fase 3: Binder (Symbol Table Construction)
Binder melakukan satu putaran traversal penuh melintasi AST. Binder tidak memeriksa tipe data. Tugas utamanya adalah:
1. Membentuk *Lexical Scopes* (`ContainerFlags`).
2. Menghubungkan deklarasi ke dalam `ts.SymbolTable`.
3. Mengasosiasikan `node.symbol` pada node deklarasi (`FunctionDeclaration`, `VariableDeclaration`, dll).
4. Membangun *Control Flow Graph* (CFG) berupa rantai `FlowNode` yang nantinya akan digunakan oleh TypeChecker untuk melakukan *Control Flow-based Type Analysis* (seperti type narrowing pada cabang `if-else`).

### Fase 4: TypeChecker (Semantic Evaluation)
Fase paling intensif secara komputasional. Arsitektur TypeChecker dibangun dengan paradigma *Lazy Evaluation* (permintaan sesuai kebutuhan). Checker tidak mengevaluasi seluruh tipe dalam AST secara serempak. Tipe hanya akan dihitung jika:
* Node tersebut diakses oleh instruksi *emit*.
* Node tersebut memengaruhi validasi pernyataan yang sedang diperiksa.
* Diminta secara eksplisit oleh language server (LSP).

Checker menyelesaikan sistem persamaan tipe:
$$T_{\text{target}} \sqsubseteq T_{\text{source}}$$
Artinya, apakah tipe $T_{\text{source}}$ dapat disubstitusikan ke dalam $T_{\text{target}}$ (*structural subtyping / behavioral compatibility*).

### Fase 5: Emitter (Code & Types Generation)
Emitter mentransformasikan AST TypeScript menjadi kode target. Tahapan Emitter:
1. Menjalankan *AST Transformers* internal atau eksternal yang melucuti syntax TypeScript murni (`enums`, `type annotations`, `interfaces`, `namespaces`).
2. Melakukan *downleveling* fitur JavaScript (seperti mengubah async/await menjadi state-machine Promise ES5 jika target bernilai `ES5`).
3. Mengeluarkan *Declaration Files* (`.d.ts`). Proses ini melibatkan ekstraksi antarmuka publik secara terisolasi tanpa mencetak detail implementasi privat.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi langsung pemanggilan TypeScript Compiler API secara programatik untuk menganalisis AST, membaca Symbol, mengevaluasi tipe dari sebuah variabel, serta membaca struktur diagnostik program.

```typescript
// scripts/inspect-ast.ts
import * as ts from 'typescript';

const sourceCode = `
export interface UserPayload {
  id: string;
  roles: string[];
}

export function processUser(payload: UserPayload): boolean {
  return payload.roles.length > 0;
}

const activeUser: UserPayload = {
  id: "usr_1029",
  roles: ["admin", "editor"]
};

export const isAuthorized = processUser(activeUser);
`;

const dummyFileName = 'virtualModule.ts';

// 1. Buat Virtual SourceFile
const sourceFile = ts.createSourceFile(
  dummyFileName,
  sourceCode,
  ts.ScriptTarget.ES2022,
  /* setParentNodes */ true,
  ts.ScriptKind.TS
);

// 2. Buat Compiler Host Virtual untuk isolasi eksekusi tanpa menyentuh I/O Disk
const compilerOptions: ts.CompilerOptions = {
  target: ts.ScriptTarget.ES2022,
  module: ts.ModuleKind.NodeNext,
  strict: true,
  declaration: true
};

const customCompilerHost: ts.CompilerHost = {
  getSourceFile: (fileName) => (fileName === dummyFileName ? sourceFile : undefined),
  getDefaultLibFileName: () => 'lib.d.ts',
  writeFile: () => {},
  getCurrentDirectory: () => '/',
  getDirectories: () => [],
  getCanonicalFileName: (fileName) => fileName,
  useCaseSensitiveFileNames: () => true,
  getNewLine: () => '\n',
  fileExists: (fileName) => fileName === dummyFileName,
  readFile: (fileName) => (fileName === dummyFileName ? sourceCode : undefined),
};

// 3. Inisialisasi TS Program & Akses TypeChecker
const program = ts.createProgram([dummyFileName], compilerOptions, customCompilerHost);
const checker = program.getTypeChecker();

// 4. Traversal AST Menggunakan ts.forEachChild
function traverseAst(node: ts.Node, depth: number = 0) {
  const indent = '  '.repeat(depth);
  const syntaxKindName = ts.SyntaxKind[node.kind];

  // Identifikasi deklarasi spesifik
  if (ts.isFunctionDeclaration(node) && node.name) {
    const symbol = checker.getSymbolAtLocation(node.name);
    if (symbol) {
      const type = checker.getTypeOfSymbolAtLocation(symbol, node);
      const signatureString = checker.typeToString(type);
      console.log(`${indent}>> [FUNCTION] ${symbol.getName()} : ${signatureString}`);
    }
  } else if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
    const symbol = checker.getSymbolAtLocation(node.name);
    if (symbol) {
      const type = checker.getTypeOfSymbolAtLocation(symbol, node);
      const typeString = checker.typeToString(type);
      console.log(`${indent}>> [VARIABLE] ${symbol.getName()} Evaluated Type: ${typeString}`);
    }
  } else {
    console.log(`${indent}(${syntaxKindName})`);
  }

  ts.forEachChild(node, (child) => traverseAst(child, depth + 1));
}

console.log('--- AST TRAVERSAL & TYPE CHECKING OUTPUT ---');
traverseAst(sourceFile);
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari alur eksekusi script fundamental di atas:

1. **Baris 23–29 (`ts.createSourceFile`)**:
   Scanner dan Parser dipicu secara bersamaan. Flag `setParentNodes: true` menginstruksikan parser untuk menyematkan pointer `.parent` pada setiap instansiasi `Node`. Hal ini esensial untuk traversal graf semantik dua arah yang dibutuhkan oleh Checker.
2. **Baris 32–37 (`compilerOptions`)**:
   Konfigurasi komputasi internal ditentukan di sini. Mode `strict: true` mengaktifkan bendera `strictNullChecks`, `noImplicitAny`, dan pemeriksaan subtipe penuh.
3. **Baris 39–50 (`customCompilerHost`)**:
   Membuat implementasi antarmuka `ts.CompilerHost`. Kompilator TypeScript mendelegasikan seluruh interaksi I/O (akses filesystem, resolusi path) ke host ini. Dengan membuat virtual host, kita mengisolasi kompilasi murni di dalam memori tanpa overhead sistem operasi.
4. **Baris 53 (`ts.createProgram`)**:
   Menciptakan objek sentral `ts.Program`. Pada tahap ini, seluruh berkas sumber diikat (*bind*), dan struktur internal `ts.Binder` dieksekusi untuk memetakan lexical scope dan tabel simbol awal.
5. **Baris 54 (`program.getTypeChecker()`)**:
   Menginstansiasi `TypeChecker`. Instansiasi ini bersifat singleton per program dan memegang seluruh *interning pool* dari type ID.
6. **Baris 62–68 (`ts.isFunctionDeclaration`)**:
   Penggunaan *Type Guard* intrinsik dari compiler API. Ketika `node` dikenali sebagai fungsi, kita memanggil `checker.getSymbolAtLocation(node.name)`. Ini memvalidasi pencarian entitas semantik dari AST identifier menuju representasi memori `Symbol`.
7. **Baris 65 (`checker.getTypeOfSymbolAtLocation`)**:
   Checker mengevaluasi signature tipe lengkap dari fungsi, memverifikasi parameter dan tipe pengembalian (`UserPayload -> boolean`).
8. **Baris 78 (`ts.forEachChild`)**:
   Traversal AST rekursif yang efisien dan tidak mengalokasikan array penampung anak node, sehingga mempertahankan konsumsi memori minimum.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Monorepo Enterprise "HyperScale Logistics"
Perusahaan logistik skala global memiliki monorepo arsitektur pnpm workspace dengan 35 internal packages:
* `@hyper/core-types`: Berisi seluruh domain model statis murni.
* `@hyper/database-client`: ORM wrappers & database connectivity.
* `@hyper/api-gateway`: Web service endpoint utama.

### Permasalahan Kritis:
1. **Bottleneck Durasi CI**: Menjalankan perintah `tsc --noEmit` pada tingkat root membutuhkan waktu **8 menit 45 detik** pada pipeline CI.
2. **Ketiadaan Batas Isolasi (Leaky Boundaries)**: Pengembang pada `@hyper/api-gateway` dapat mengimpor kode internal terdalam dari `@hyper/database-client` yang seharusnya tidak terekspos ke publik (`index.ts` bypass).
3. **Out-of-Memory (OOM) Errors**: Node.js v20 crash dengan error `JavaScript heap out of memory` saat memproses keseluruhan codebase secara simultan akibat keterikatan memori antar dependensi sirkular yang tersembunyi.

### Solusi Arsitektural:
* Rekonfigurasi monorepo ke arsitektur **Project References** berbasis topologi DAG yang ketat.
* Penerapan flag `"composite": true`, `"declaration": true`, dan `"declarationMap": true`.
* Optimasi kompilasi parsial dengan pnpm filtering dan pengaktifan cache `.tsbuildinfo` yang didistribusikan ke remote build cache.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah konfigurasi industri dan kerangka kerja orkestrasi internal monorepo untuk menyelesaikan masalah di atas.

### 1. Root Configuration (`tsconfig.base.json`)
Konfigurasi dasar mutlak yang diwariskan (*extended*) oleh seluruh sub-paket monorepo.

```json
{
  "$schema": "https://json.schemastore.org/tsconfig",
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "composite": true,
    "incremental": true,
    "strict": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  }
}
```

### 2. Paket Core (`packages/core-types/tsconfig.json`)

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "rootDir": "src",
    "outDir": "dist",
    "tsBuildInfoFile": "dist/.tsbuildinfo"
  },
  "include": ["src/**/*"]
}
```

```typescript
// packages/core-types/src/index.ts
export interface ShipmentRecord {
  trackingId: string;
  weightKg: number;
  originCountry: string;
  status: 'PENDING' | 'IN_TRANSIT' | 'DELIVERED';
}

export function validateShipment(record: ShipmentRecord): boolean {
  return record.weightKg > 0 && record.trackingId.trim().length > 0;
}
```

### 3. Paket Database Client (`packages/db-client/tsconfig.json`)

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "rootDir": "src",
    "outDir": "dist",
    "tsBuildInfoFile": "dist/.tsbuildinfo"
  },
  "references": [
    { "path": "../core-types" }
  ],
  "include": ["src/**/*"]
}
```

```typescript
// packages/db-client/src/index.ts
import { ShipmentRecord } from '@hyper/core-types';

export class ShipmentRepository {
  private memoryStore = new Map<string, ShipmentRecord>();

  public async persist(shipment: ShipmentRecord): Promise<void> {
    this.memoryStore.set(shipment.trackingId, shipment);
  }

  public async findById(id: string): Promise<ShipmentRecord | null> {
    return this.memoryStore.get(id) ?? null;
  }
}
```

### 4. Paket API Server (`packages/api-server/tsconfig.json`)

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "rootDir": "src",
    "outDir": "dist",
    "tsBuildInfoFile": "dist/.tsbuildinfo"
  },
  "references": [
    { "path": "../core-types" },
    { "path": "../db-client" }
  ],
  "include": ["src/**/*"]
}
```

### 5. Orchestrator Manifest (`tsconfig.json` di Root Direktori)
Root `tsconfig.json` bertindak murni sebagai koordinator orkestrasi build DAG.

```json
{
  "files": [],
  "references": [
    { "path": "packages/core-types" },
    { "path": "packages/db-client" },
    { "path": "packages/api-server" }
  ]
}
```

### 6. Pipeline Build Script (`package.json`)
Menjalankan kompilasi terisolasi dan deterministik melalui mode build graf TypeScript (`tsc -b`).

```json
{
  "name": "hyperscale-logistics-root",
  "private": true,
  "scripts": {
    "build": "tsc --build tsconfig.json",
    "build:clean": "tsc --build --clean tsconfig.json",
    "build:dry": "tsc --build --verbose --dry tsconfig.json",
    "typecheck": "tsc --build --noEmit tsconfig.json"
  },
  "devDependencies": {
    "typescript": "^5.4.5"
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Project References (`tsc -b`) vs. Bundling Tradisional Monorepo (misal: Esbuild / Turbopack monorepo)

| Dimensi Evaluasi | TypeScript Project References (`tsc -b`) | Bundler Aggregation (ts-loader / Esbuild / SWC) | Single Monolithic `tsc` |
| :--- | :--- | :--- | :--- |
| **Kebenaran Tipe (Type Safety)** | **Maksimum Mutlak**: Memvalidasi kesesuaian `.d.ts` antar batas paket secara deterministik. | Rendah / Terpisah: Bundler mentranspilasi kode tanpa type-check (*stripping types*). Type-checking harus dijalankan manual. | Tinggi: Namun rawan OOM karena memuat seluruh AST ke satu heap memory process. |
| **Kecepatan Build Inkremental** | **Tinggi via Cache DAG**: Hanya mengompilasi ulang sub-paket yang mengalami mutasi tanda tangan publik. | **Sangat Tinggi**: Karena hanya melakukan proses stripping syntax tanpa inferensi tipe semantik. | **Sangat Rendah**: Mengompilasi ulang ribuan berkas secara monolitik dari scratch. |
| **Setup & Overhead Konfigurasi** | **Kompleks**: Setiap modul memerlukan konfigurasi path, sinkronisasi references, dan flags composite. | **Sederhana**: Bundler sering kali mengabaikan batas package dan membaca direct source. | **Paling Sederhana**: Hanya butuh 1 berkas `tsconfig.json` di root. |
| **Isolasi Boundaries** | **Sangat Kuat**: Mencegah kebocoran implementasi privat antar paket internal. | **Rentan**: Pengembang dapat dengan mudah melakukan relative import cross-boundary (`../../pkg/src/priv`). | **Tidak Ada Isolasi**: Seluruh file dianggap dalam satu scope program global. |
| **Konsumsi Memori CI** | Terukur secara linier terhadap sub-paket individual yang sedang dikompilasi. | Ringan karena kompilasi paralel terisolasi tanpa interning tipe. | Eksponensial seiring bertambahnya node graf AST; sering memicu OOM crash. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Phantom Rebuild Cycle (Siklus Cache Rusak)
* **Gejala**: Menjalankan `tsc -b` secara berulang-ulang tanpa mengubah kode tetap menghasilkan eksekusi kompilasi ulang (tidak pernah mendapatkan status `Project is up to date`).
* **Akar Masalah**: Ketidakcocokan antara lokasi emit file deklarasi (`outDir`) dengan pemetaan `tsBuildInfoFile`. Jika berkas output `.tsbuildinfo` diabaikan atau dibersihkan oleh build tool lain (misalnya bundler seperti Vite/Rollup), kompilator kehilangan basis komparasi hash dan mengasumsikan paket dalam keadaan kotor (*dirty*).
* **Solusi**: Pastikan `tsBuildInfoFile` didefinisikan secara eksplisit di dalam direktori `dist/` atau `build/` masing-masing sub-paket, dan pastikan artefak tersebut ikut di-cache oleh tool orkestrator (misal: Turborepo / Nx cache input/output hash).

### 2. Kebocoran Tipe Non-Exported (Private Type Leakage)
* **Gejala**: Error `TS4023: Exported variable [...] has or is using name [...] from external module [...] but cannot be named`.
* **Akar Masalah**: Dalam mode `"composite": true`, file deklarasi `.d.ts` wajib dihasilkan secara lengkap. Jika fungsi mengekspor objek yang tipenya mengacu pada interface internal yang **tidak diekspor secara publik**, TypeScript menolak menghasilkan `.d.ts` karena pihak ketiga tidak akan mampu menyelesaikan referensi tipe tersebut.
* **Solusi**: Pastikan seluruh tipe yang menyusun API publik dari sebuah paket di-export secara eksplisit:

```typescript
// PITFALL
interface InternalConfiguration {
  timeoutMs: number;
}
// TS4023 jika diekspor tanpa mengekspor InternalConfiguration
export const defaultConfiguration: InternalConfiguration = { timeoutMs: 5000 };

// MITIGASI
export interface InternalConfiguration {
  timeoutMs: number;
}
export const defaultConfiguration: InternalConfiguration = { timeoutMs: 5000 };
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan Path Aliasing (`paths`) Tanpa Menyesuaikan Project References
* **Kesalahan Fatal**:
  ```json
  // tsconfig.json
  "compilerOptions": {
    "paths": {
      "@hyper/core-types": ["../core-types/src"]
    }
  }
  ```
  Ini menyebabkan kompilator membaca kembali **berkas sumber mentah** `.ts` dari paket dependensi, mengabaikan `.d.ts`, dan menduplikasi pembuatan AST di memori paket target. Hal ini secara instan merusak efisiensi Project References dan menghancurkan manfaat cache inkremental.
* **Koreksi Arsitektural**:
  Hapus pemetaan `paths` internal ke source `.ts`. Konfigurasi `package.json` dependensi workspace agar menunjuk ke berkas emit type:
  ```json
  // packages/core-types/package.json
  {
    "name": "@hyper/core-types",
    "main": "./dist/index.js",
    "types": "./dist/index.d.ts"
  }
  ```
  Gunakan flag module resolution `NodeNext` sehingga Node dan TypeScript menyelesaikan resolusi langsung melalui package manifest.

### 2. Lupa Mengaktifkan `isolatedModules`
* **Kesalahan Fatal**: Menulis kode yang bergantung pada konseptual runtime dari interface atau *const enum* tanpa flag `"isolatedModules": true`.
* **Dampak**: Bundler seperti SWC atau Esbuild memproses berkas per-file secara terisolasi tanpa typechecker. Jika kompilator TypeScript memperbolehkan konstruksi seperti `export { MyType }` tanpa keyword `export type { MyType }`, bundler dapat menghasilkan bug emisi JavaScript yang fatal (mencoba mengimpor variabel yang tidak ada di runtime).
* **Solusi**: Selalu aktifkan `"isolatedModules": true` pada `tsconfig.base.json`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Aturan Single-Responsibility Sub-TSConfig**:
   Bagi konfigurasi sub-paket menjadi dua layer:
   * `tsconfig.json`: Untuk eksekusi build dan orkestrasi Project References (`outDir: "dist"`).
   * `tsconfig.test.json`: Khusus untuk eksekusi unit test runner (misal: Vitest/Jest) agar berkas `*.spec.ts` tidak ikut terdistribusi ke dalam artefak `.d.ts` produksi.
2. **Keluarkan Selalu `declarationMap: true`**:
   Dengan declaration map (`.d.ts.map`), fitur *Go to Definition* (F12) pada IDE (seperti VS Code atau Neovim) dari pengguna downstream akan melompat langsung ke **berkas sumber `.ts` asli**, bukan terhenti di dalam berkas deklarasi tipe `.d.ts`.
3. **Impor Tipe Eksplisit Menggunakan Syntax `type`**:
   Selalu gunakan sintaksis modern `import type { Foo } from '...'`. Ini memberikan kejelasan absolut kepada Scanner dan Parser bahwa entitas tersebut dapat dilucuti seketika tanpa membutuhkan evaluasi binder lebih lanjut.
4. **Isolasi Dependencies Top-Level Monorepo**:
   Jangan pernah menaruh dependensi library aplikasi pada root `package.json`. Root hanya boleh berisi perkakas orkestrasi build murni (`typescript`, linting tools, formatting tools).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Diagnostik Kinerja Kompilasi Mendalam
Jalankan perintah berikut untuk mengaudit profiling performa kompilasi:

```bash
tsc --build --extendedDiagnostics
```

Analisis output metrik kritis:
* **Check time**: Waktu komputasi yang dihabiskan TypeChecker. Jika check time mendominasi $>70\%$ dari total waktu build, ada kemungkinan codebase mengandung tipe rekursif kompleks atau deep union type checking.
* **Symbol count & Type count**: Jika metrik ini melompat secara drastis (contoh: Type count $>100,000$), teliti apakah Anda mengimpor library dengan antarmuka yang sangat besar ke dalam siklus deklarasi monorepo tanpa pruning.

### 2. Visual Profiling via Chromium Trace (`--generateTrace`)
Aktifkan tracing granular untuk mendeteksi bottleneck inferensi tipe:

```bash
tsc --noEmit --generateTrace trace_dir
```

Langkah Analisis:
1. Buka browser Chromium dan akses `chrome://tracing` atau platform [speedscope.app](https://www.speedscope.app).
2. Muat berkas `trace.json` dari direktori `trace_dir`.
3. Telusuri event `checkSourceFile` yang paling lebar secara horizontal. Identifikasi pemanggilan fungsi `findAncestor` atau `isTypeAssignableTo` yang terjebak dalam rekursi tak terbatas akibat manipulasi generic type yang tidak di-memoize.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Eksploitasi Type-Level Recursion (Denial of Service Kompilator)**:
   TypeScript turing-complete type system memungkinkan penulisan tipe kondisional rekursif tak berujung yang dapat membuat CPU pipeline CI mengalami status hang (Infinite Loop).
   ```typescript
   // Hardening Pattern: Tambahkan batasan kedalaman rekursi (Recursion Depth Counter)
   type MaxDepth<N extends number, Arr extends any[] = []> =
     Arr['length'] extends N ? true : false;

   type SafeDeepFlatten<T, Depth extends any[] = []> =
     Depth['length'] extends 10 // Batas aman rekursi internal
       ? T
       : T extends Array<infer U>
         ? SafeDeepFlatten<U, [...Depth, any]>
         : T;
   ```
2. **Hardening Module Resolution**:
   Hindari resolusi tipe yang rentan dibajak (*Type Confusion Attack*) dengan menonaktifkan pencarian implisit:
   ```json
   {
     "compilerOptions": {
       "moduleResolution": "NodeNext",
       "module": "NodeNext",
       "noUncheckedIndexedAccess": true
     }
   }
   ```
   Flag `"noUncheckedIndexedAccess": true` memastikan bahwa pengembang tidak dapat mengakses elemen array atau record tanpa secara aman memeriksa kemungkinan nilai `undefined`, mencegah eksekusi payload null-pointer di tingkat produksi runtime.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Bagaimana mendeteksi mengapa kompilator memutuskan untuk mengompilasi ulang sub-paket yang seharusnya bersih (*clean*)? 

Gunakan bendera `--explainFiles` dan `--verbose` untuk melacak rute resolusi file internal kompilator.

```bash
tsc -b --verbose packages/api-server/tsconfig.json --explainFiles > compiler-trace.log
```

Cuplikan Analisis Log Observabilitas:

```text
[11:04:12 AM] Projects in this build: 
    * packages/core-types/tsconfig.json
    * packages/db-client/tsconfig.json
    * packages/api-server/tsconfig.json

[11:04:13 AM] Project 'packages/core-types/tsconfig.json' is up to date because newest input 'packages/core-types/src/index.ts' [Hash: e2b4a...] is older than target 'packages/core-types/dist/index.d.ts' [Hash: f3a11...]

[11:04:14 AM] Project 'packages/db-client/tsconfig.json' is out of date because output 'packages/db-client/dist/index.d.ts' does not exist

packages/core-types/dist/index.d.ts
  Imported by packages/db-client/src/index.ts
  Part of project 'packages/db-client/tsconfig.json'
```

Melalui log ini, kita dapat segera mengidentifikasi berkas mana yang membatalkan cache (`is out of date`) secara deterministik tanpa menebak-nebak kondisi cache.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Pipeline Execution Summary
```
Input Source Code
   |
   v
[Scanner]       -> Token Stream (ts.SyntaxKind)
   |
   v
[Parser]        -> SourceFile AST Nodes
   |
   v
[Binder]        -> Scopes, Declarations, & Symbols Table
   |
   v
[TypeChecker]   -> Structural Subtyping, Semantic Checking, Diagnostics
   |
   v
[Emitter]       -> Transforms AST -> JavaScript + Declarations (.d.ts)
```

### Konfigurasi Kunci Monorepo Reference

| Flag Konfigurasi | Nilai Rekomendasi | Fungsi Internal |
| :--- | :--- | :--- |
| `composite` | `true` | Wajib untuk monorepo DAG. Mengaktifkan emisi berkas deklarasi dan manifest metadata. |
| `declaration` | `true` | Menghasilkan `.d.ts` yang dikonsumsi oleh proyek downstream. |
| `declarationMap` | `true` | Memetakan deklarasi tipe kembali ke source code `.ts` asli untuk kemudahan debugging IDE. |
| `incremental` | `true` | Otomatis aktif jika `composite: true`. Menghasilkan file cache `.tsbuildinfo`. |
| `isolatedModules`| `true` | Memastikan tiap file dapat ditranspilasi tanpa informasi type graph global. |
| `tsBuildInfoFile` | `"dist/.tsbuildinfo"`| Menempatkan file state cache build inkremental ke folder dist lokal paket. |

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1-5)

1. **Pada tahap mana token leksikal dikonversikan menjadi Abstract Syntax Tree (AST)?**
   * A. Scanner
   * B. Parser
   * C. Binder
   * D. Checker
   * *Jawaban yang Benar*: B.
   * *Penjelasan*: Scanner hanya memproduksi token leksikal satu-per-satu. Parser membaca aliran token tersebut dan merangkainya menjadi pohon sintaksis terstruktur (`SourceFile` AST Node).

2. **Apa fungsi utama dari berkas manifest `.tsbuildinfo` yang dihasilkan kompilator?**
   * A. Menyimpan kode JavaScript terkompresi.
   * B. Menyimpan token enkripsi CI/CD.
   * C. Menyimpan graf dependensi berkas dan hash konten guna mengaktifkan validasi cache inkremental.
   * D. Menggantikan peran berkas deklarasi `.d.ts`.
   * *Jawaban yang Benar*: C.
   * *Penjelasan*: `.tsbuildinfo` adalah file internal TypeScript yang menyimpan hash berkas dan status graf relasi agar kompilator tahu modul mana yang belum dimutasi sehingga tidak perlu dikompilasi ulang.

3. **Perbedaan utama antara entitas `Symbol` dan `Type` di dalam arsitektur kompilator adalah...**
   * A. Symbol menyimpan nama dan relasi deklarasi sintaksis; Type menyimpan relasi semantik yang dievaluasi dinamis oleh TypeChecker.
   * B. Symbol hanya digunakan di JavaScript; Type hanya di TypeScript.
   * C. Symbol hanya dievaluasi pada runtime browser.
   * D. Type dibuat oleh Binder; Symbol dibuat oleh Checker.
   * *Jawaban yang Benar*: A.
   * *Penjelasan*: Binder memproduksi `Symbol` untuk mewakili identifier yang dideklarasikan. `Type` dihasilkan dan diperiksa oleh `TypeChecker` untuk memvalidasi aturan sistem tipe.

4. **Karakteristik wajib apa yang harus dimiliki sebuah sub-paket agar dapat didaftarkan di dalam array `references` pada `tsconfig.json` proyek lain?**
   * A. Harus menggunakan modul format CommonJS.
   * B. Wajib mengaktifkan `"composite": true`.
   * C. Wajib mematikan `strict`.
   * D. Tidak boleh memiliki dependensi eksternal.
   * *Jawaban yang Benar*: B.
   * *Penjelasan*: TypeScript mewajibkan `"composite": true` pada sub-proyek yang menjadi target referensi agar ia menghasilkan manifest build dan deklarasi yang dibutuhkan oleh paket pemanggil.

5. **Apa dampak langsung dari pengaktifan flag `"isolatedModules": true`?**
   * A. Mengurangi kecepatan kompilasi sebesar 50%.
   * B. Mencegah penggunaan fitur-fitur TypeScript yang tidak dapat ditranspilasi secara aman oleh single-file transpilers seperti Babel, SWC, atau Esbuild.
   * C. Menghapus kebutuhan kompilasi `.d.ts`.
   * D. Mengisolasi memori RAM Node.js agar tidak crash.
   * *Jawaban yang Benar*: B.
   * *Penjelasan*: `isolatedModules` memberi peringatan jika ada konstruksi syntax yang ambigu jika berkas dikompilasi satu demi satu secara terisolasi tanpa typechecker global (seperti `const enum` ambient atau ekspor tipe tanpa kata kunci `type`).

---

### Soal Intermediate (6-10)

6. **Mengapa penggunaan flag `"paths"` untuk me-resolve direct source antar sub-paket (`"../pkg/src"`) di dalam monorepo dianggap sebagai antipattern performa?**
   * A. Karena syntax paths sudah deprecated di TypeScript 5.0.
   * B. Karena kompilator dipaksa mengurai ulang AST source code dari paket dependensi di setiap paket konsumen, sehingga menonaktifkan isolasi cache Project References.
   * C. Karena paths tidak didukung oleh VS Code.
   * D. Karena paths memicu memory leak pada sistem berkas OS.
   * *Jawaban yang Benar*: B.
   * *Penjelasan*: Mengarahkan paths ke source `.ts` mentah merusak batas Project References. Kompilator memperlakukan source dependensi sebagai bagian dari AST lokal paket pemanggil, yang meningkatkan penggunaan heap memory secara drastis dan meniadakan penggunaan `.d.ts` yang sudah dicache.

7. **Ketika terjadi siklus dependensi sirkular (Circular Dependency) antar dua sub-paket yang mengaktifkan Project References, apa yang akan terjadi saat menjalankan `tsc --build`?**
   * A. Kompilator mengabaikan referensi tersebut dan melanjutkan build secara linier.
   * B. Kompilator melempar error dan menolak kompilasi karena struktur referensi wajib berupa Directed Acyclic Graph (DAG).
   * C. Kompilator otomatis memecah siklus secara cerdas pada runtime.
   * D. Kompilator masuk ke dalam infinite loop hingga crash OOM.
   * *Jawaban yang Benar*: B.
   * *Penjelasan*: Project References secara mendasar mensyaratkan arsitektur graf DAG. Jika ada referensi siklikal ($A \to B \to A$), `tsc -b` mendeteksinya dan memunculkan error siklus dependensi.

8. **Saat menganalisis trace performance (`--generateTrace`), fungsi internal checker mana yang paling umum menjadi indikator adanya type computation bottleneck pada conditional type rekursif?**
   * A. `createSourceFile`
   * B. `isTypeAssignableTo` / `checkTypeRelatedTo`
   * C. `emitFiles`
   * D. `scanToken`
   * *Jawaban yang Benar*: B.
   * *Penjelasan*: Algoritma type-checking menghabiskan mayoritas siklus komputasi di `isTypeAssignableTo` saat memvalidasi apakah tipe parameter kompleks cocok dengan tipe argumen input.

9. **Apa konsekuensi arsitektural jika sebuah proyek monorepo mengabaikan penggunaan `"declarationMap": true`?**
   * A. Proyek tidak dapat dikompilasi ke JavaScript.
   * B. IDE konsumen paket downstream hanya dapat bernavigasi ke berkas deklarasi `.d.ts` daripada melompat ke baris source code implementasi `.ts` aslinya.
   * C. Ukuran bundle JavaScript runtime membengkak dua kali lipat.
   * D. Type safety pada sub-paket menjadi hilang total.
   * *Jawaban yang Benar*: B.
   * *Penjelasan*: `.d.ts.map` adalah sourcemap untuk deklarasi. Tanpa file ini, fitur "Go to Definition" pada IDE berhenti di interface `.d.ts` yang dihasilkan oleh build tool, menyulitkan developer membaca logika internal sumber.

10. **Perhatikan skenario berikut:**
    ```typescript
    // packages/pkg-a/src/internal.ts
    export interface InternalConfig { secret: string; }
    
    // packages/pkg-a/src/index.ts
    import { InternalConfig } from './internal';
    export const createEngine = (): InternalConfig => ({ secret: 'xyz' });
    ```
    Jika paket ini dikompilasi dengan `"composite": true`, namun `packages/pkg-a/src/index.ts` **tidak** mengekspor `InternalConfig`, compiler error apa yang akan terjadi?
    * A. TS2307: Cannot find module './internal'.
    * B. TS4023: Exported variable/function has or is using name 'InternalConfig' from external module but cannot be named.
    * C. TS1005: ';' expected.
    * D. Tidak ada error, TypeScript otomatis mengekspor interface internal tersebut.
    * *Jawaban yang Benar*: B.
    * *Penjelasan*: Kompilator wajib membuat representasi publik di `.d.ts`. Jika tipe return function merujuk pada interface yang scope-nya privat (tidak di-re-export), kompilator tidak mampu mereferensikannya dalam `.d.ts` tanpa merusak batas enkapsulasi, sehingga menghasilkan error TS4023.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Proyek
Bangun tool audit kompilasi monorepo independen berbasis TypeScript Compiler API: **"TypeScript Monorepo Boundary Linter"**.

Tool ini harus berupa file script TypeScript mandiri yang dapat dijalankan melalui terminal (`node --loader ts-node` atau `tsx`).

### Kriteria Fungsional Wajib:
1. **Membaca Topologi Project References**:
   * Skrip harus menerima path direktori root monorepo.
   * Parse `tsconfig.json` di root menggunakan `ts.readConfigFile` dan `ts.parseJsonConfigFileContent`.
   * Ekstraksi seluruh array `references` dan bentuk visualisasi Directed Acyclic Graph (DAG) di terminal.
2. **Boundary Violation Detector**:
   * Periksa apakah terdapat berkas `.ts` di dalam satu sub-paket yang mengimpor langsung berkas internal dari sub-paket lain tanpa melalui entry point resmi (misal: mengimpor `@monorepo/core/src/internal-secret` alih-alih `@monorepo/core`).
3. **Emit Validation**:
   * Panggil API `ts.createProgram` berbasis konfigurasi proyek target, jalankan `program.emit()` secara inkremental, dan cetak laporan status performa:
     * Total Waktu Check Semantik.
     * Jumlah Memory Symbol Heap.
     * Daftar diagnostic warnings jika ada kebocoran tipe (TS4023).

### Kerangka Awal Skrip:

```typescript
// scripts/monorepo-linter.ts
import * as ts from 'typescript';
import * as path from 'path';
import * as fs from 'fs';

export function runMonorepoAudit(rootTsconfigPath: string) {
  const configFile = ts.readConfigFile(rootTsconfigPath, ts.sys.readFile);
  if (configFile.error) {
    console.error('Error membaca konfigurasi:', configFile.error.messageText);
    return;
  }

  const parsedConfig = ts.parseJsonConfigFileContent(
    configFile.config,
    ts.sys,
    path.dirname(rootTsconfigPath)
  );

  console.log(`[AUDIT] Ditemukan ${parsedConfig.projectReferences?.length ?? 0} referensi proyek.`);

  // TODO: Implementasikan traversal references, AST analysis, dan import verification logic.
}

// Eksekusi jika dipanggil langsung
const rootPath = path.resolve(process.cwd(), 'tsconfig.json');
runMonorepoAudit(rootPath);
```

### Tolok Ukur Keberhasilan:
* Skrip menghasilkan exit code `0` jika seluruh dependensi internal taat pada kaidah isolasi boundary.
* Skrip mengembalikan exit code `1` dan mencetak daftar file spesifik serta nomor baris yang melanggar boundary jika menemukan impor bypass.
* Skrip berhasil memvalidasi konsistensi struktur DAG tanpa memicu recursive stack overflow.