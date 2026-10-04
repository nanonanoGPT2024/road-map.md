# BAB 09: Compiler Internals, Monorepo & Tooling
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Membedah arsitektur internal TypeScript Compiler (`Scanner`, `Parser`, `Binder`, `Checker`, `Emitter`) dan siklus hidup kompilasi secara terukur.
- Merancang, mengonfigurasi, dan mengoptimalkan arsitektur monorepo skala enterprise (*multi-package*) berbasis **TypeScript Project References** (`composite: true`, `tsbuildinfo`).
- Mengimplementasikan **Custom AST Transformer** menggunakan Compiler API (`ts.factory`, `ts.TransformationContext`, `ts.visitEachChild`) untuk modifikasi kode pada tahap transmogrifikasi sintaksis.
- Mengintegrasikan pipeline *type checking* terdistribusi dan *transpilation* terpisah (*decoupled orchestration*) menggunakan kombinasi `tsc --build`, Turborepo/Nx, serta isolated-transpilers (SWC/esbuild).
- Mendiagnosis degradasi performa kompilasi, memory leak (*heap exhaustion* pada monorepo), dan siklus dependensi sirkular antar paket.

---

### 2. Prerequisite
- Pemahaman mendalam mengenai sistem tipe tingkat lanjut TypeScript (Generics, Conditional Types, Template Literal Types, Mapped Types).
- Pemahaman konfigurasi `tsconfig.json` (`moduleResolution`, `target`, `lib`, `paths`, subpath exports `exports` pada `package.json`).
- Familiaritas dengan konsep Abstract Syntax Tree (AST) dan representasi token program.
- Pengalaman dasar menggunakan *package managers* modern dengan dukungan workspace (pnpm/yarn).

---

### 3. Concept & Internal Architecture (Mendalam)

#### Arsitektur Inti Compiler TypeScript
Arsitektur internal TypeScript bukan sekadar *transpiler* teks-ke-teks, melainkan pipeline analisis statis berlapis:

```
[Source Code: .ts]
       │
       ▼
 ┌───────────┐
 │  Scanner  │ ──> Menghasilkan Stream of Tokens (SyntaxKind)
 └───────────┘
       │
       ▼
 ┌───────────┐
 │  Parser   │ ──> Membangun Abstract Syntax Tree (SourceFile node)
 └───────────┘
       │
       ▼
 ┌───────────┐
 │  Binder   │ ──> Mengasosiasikan AST Nodes dengan 'Symbol' & membangun Scope Tree
 └───────────┘
       │
       ▼
 ┌───────────┐
 │  Checker  │ ──> Semantic Validation & Type Inference (Type, TypeChecker)
 └───────────┘
       │
       ▼
 ┌───────────┐
 │  Emitter  │ ──> Menjalankan AST Transformers -> Menghasilkan .js, .d.ts, .map
 └───────────┘
```

1. **Scanner (`src/compiler/scanner.ts`)**:
   Membaca karakter mentah dari *buffer memory* dan mengonversinya menjadi token primitif (`SyntaxKind.Identifier`, `SyntaxKind.StringLiteral`, `SyntaxKind.WhileKeyword`). Scanner mempertahankan posisi karakter (*trivia*: whitespace dan komentar) untuk akurasi *source-map*.

2. **Parser (`src/compiler/parser.ts`)**:
   Mengambil stream token dan membangun representasi pohon struktural (**AST**) yang berakar pada `ts.SourceFile`. Parser menerapkan recursive-descent parsing. Setiap node mengimplementasikan interface `ts.Node`, memiliki properti `pos`, `end`, `parent`, dan `kind`.

3. **Binder (`src/compiler/binder.ts`)**:
   Membaca AST murni dan menghubungkannya dengan semantik penamaan melalui `ts.Symbol`. Jika parser hanya memahami: *"ada identifier bernama X di baris 4"*, Binder bertugas mengidentifikasi: *"X adalah variabel lokal di dalam scope fungsi Y, yang berbenturan atau membayangi (shadowing) variabel modul Z"*. Binder mengelompokkan deklarasi identik (misalnya `interface User` dan `namespace User`) ke dalam `Symbol` yang sama melalui *declaration merging*.

4. **Checker (`src/compiler/checker.ts`)**:
   Komponen paling masif pada compiler (>45.000 baris kode). Bertanggung jawab terhadap semantik sistem tipe. Checker mereferensikan `ts.Type` terhadap `ts.Symbol`. Proses *flow-sensitive analysis*, ekspansi *generic constraints*, unifikasi tipe union/intersection, dan validasi assignability terjadi di fase ini. Komputasi checker bersifat *lazy*: tipe dievaluasi hanya ketika ada node AST yang mereferensikannya.

5. **Emitter (`src/compiler/emitter.ts`)**:
   Mengonversi node AST menjadi output fisik: JavaScript (`.js`), Deklarasi Tipe (`.d.ts`), dan peta pemetaan (`.js.map`, `.d.ts.map`). Sebelum output dicetak, Emitter menjalankan pipeline **AST Transformers** (bawaan TS untuk *lowering* syntax ESNext ke ES5/ES6, dekorator, JSX, atau Custom Transformer eksternal).

#### Mekanisme Project References & `.tsbuildinfo`
Pada arsitektur monorepo skala enterprise:
- **`composite: true`**: Memaksa compiler memastikan setiap project dapat dikompilasi secara independen. Mengharuskan `declaration: true`, menerapkan penentuan eksplisit batas direktori via `rootDir`, dan melarang project mereferensikan file di luar deklarasi `rootDir` tanpa referensi eksplisit.
- **Topological DAG (Directed Acyclic Graph)**: Saat `tsc --build` dieksekusi, compiler mengevaluasi dependensi antar-proyek dalam urutan topologis, memastikan *upstream packages* mengemisikan `.d.ts` sebelum *downstream packages* mulai di-typecheck.
- **Incremental Cache Artifact (`.tsbuildinfo`)**: File state internal biner/JSON yang menyimpan hash kriptografis dari file input, opsi compiler, deklarasi eksternal, dan graf dependensi modul internal. Hal ini memungkinkan compiler melakukan *early-exit bailout* jika hash tidak bermutasi sejak kompilasi terakhir.

---

### 4. Why & What

| Pendekatan Konvensional (Monolithic `tsconfig.json`) | Pendekatan Enterprise (Project References + Decoupled Tooling) |
|---|---|
| Mengompilasi seluruh workspace sebagai satu graf kompilasi raksasa. | Membagi workspace menjadi subunit terisolasi yang membentuk DAG. |
| Kompleksitas memoriChecker $O(N)$ terhadap seluruh basis kode; sering mengalami `JavaScript heap out of memory`. | Memori terisolasi per-paket. Pengecekan downstream hanya mengonsumsi `.d.ts` dari upstream, bukan AST lengkapnya. |
| Ketiadaan batasan arsitektural; dependensi sirkular antar-domain sering kali tidak terdeteksi. | Menegakkan modularitas batas isolasi kode secara ketat (*strict encapsulation*). |
| Setiap perubahan kecil memicu typecheck ulang seluruh basis kode (menghambat pipeline CI/CD). | Re-compilation berbasis delta via cache `.tsbuildinfo` dan cache terdistribusi (Remote Cache). |

---

### 5. How (Workflow Detail)

1. **Inisialisasi Project Graph**:
   Compiler membaca `tsconfig.json` root yang berisi array `references: [{ path: "./packages/core" }, { path: "./packages/api" }]`.
2. **Kalkulasi Urutan Dependensi**:
   Compiler membaca manifest dependensi antar file `tsconfig.json` dan menyusun urutan build topologis bebas siklus (*Acyclic*).
3. **Pemeriksaan Cache Upstream**:
   Compiler memverifikasi file `.tsbuildinfo` upstream. Jika ada modifikasi sumber daya:
   - Compile AST upstream.
   - Emisi file `.d.ts` dan `.d.ts.map`.
   - Update hash `.tsbuildinfo`.
4. **Penyediaan Deklarasi ke Downstream**:
   Paket downstream tidak lagi membaca file `.ts` upstream, melainkan hanya membaca file `.d.ts` yang telah terkompilasi. Ini mengeliminasi beban typechecking berulang pada modul internal yang stabil.
5. **AST Transformation Hooks**:
   Sebelum serialisasi akhir JavaScript, Custom AST Transformer disuntikkan ke dalam *pipeline emit*, memanipulasi struktur node tanpa merusak source mapping.

---

### 6. Analogy & Diagram ASCII

#### Analogi Lini Produksi Manufaktur
Membangun monorepo tanpa Project References ibarat merakit mobil utuh dari lelehan bijih besi dan karet mentah setiap kali ada revisi baut pada pintu. Menggunakan Project References setara dengan membagi perakitan menjadi modul mesin, sasis, dan transmisi terpisah: jika hanya mesin yang berubah, pabrik cukup menguji modul mesin, menghasilkan antarmuka docking (`.d.ts`), dan langsung menyatukannya ke sasis yang telah selesai dirakit.

#### Diagram Topologi Build DAG & Compiler Internals

```
                       tsconfig.json (Root Orchestrator)
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            ▼                                                   ▼
   packages/core (composite)                           packages/shared (composite)
   ┌───────────────────────┐                           ┌─────────────────────────┐
   │ AST -> Check -> Emit  │                           │ AST -> Check -> Emit    │
   │ Output: core.d.ts     │                           │ Output: shared.d.ts     │
   └───────────┬───────────┘                           └────────────┬────────────┘
               │                                                    │
               │ (References: reads core.d.ts)                      │ (References: reads shared.d.ts)
               └─────────────────────────┬──────────────────────────┘
                                         ▼
                                packages/backend-api
                               ┌─────────────────────┐
                               │ Parser & Checker    │
                               │ Transformer Hook    │ ──> [Custom AST Transformer]
                               │ Emitter             │
                               │ Output: dist/index.js│
                               └─────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Menginspeksi Token dan Membangun AST Parser Mandiri
Program berikut mendemonstrasikan konsumsi Compiler API tingkat rendah untuk membedah node AST:

```typescript
import ts from "typescript";

const sourceCode = `const calculateTps = (txCount: number, durationSec: number): number => txCount / durationSec;`;

const sourceFile = ts.createSourceFile(
  "inline-sample.ts",
  sourceCode,
  ts.ScriptTarget.ESNext,
  /* setParentNodes */ true
);

function traverseAST(node: ts.Node, depth: number = 0): void {
  const indent = "  ".repeat(depth);
  const syntaxKindName = ts.SyntaxKind[node.kind];
  console.log(`${indent}├─ [${syntaxKindName}] (${node.pos}..${node.end})`);

  ts.forEachChild(node, (child) => traverseAST(child, depth + 1));
}

traverseAST(sourceFile);
```

#### Practical Example: Production-Grade AST Transformer & Project References Configuration

Berikut adalah implementasi sistem monorepo enterprise yang menyematkan **Custom AST Transformer**. Transformer ini mencari penanda khusus `@traceable` pada deklarasi metode kelas dan menyuntikkan instruksi OpenTelemetry/Metrics instrumentation secara otomatis pada fase kompilasi tanpa runtime overhead dari dekorator standar.

##### Struktur Workspace
```
enterprise-monorepo/
├── tsconfig.base.json
├── tsconfig.json
├── packages/
│   ├── core/
│   │   ├── tsconfig.json
│   │   ├── package.json
│   │   └── src/index.ts
│   └── service-order/
│       ├── tsconfig.json
│       ├── package.json
│       └── src/order-service.ts
└── tools/
    └── transformers/
        └── trace-transformer.ts
```

##### 1. Base Configuration (`tsconfig.base.json`)
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
    "strict": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  }
}
```

##### 2. Core Package (`packages/core/tsconfig.json`)
```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "composite": true,
    "rootDir": "./src",
    "outDir": "./dist",
    "tsBuildInfoFile": "./dist/.tsbuildinfo"
  },
  "include": ["src/**/*"]
}
```

##### 3. Custom AST Transformer (`tools/transformers/trace-transformer.ts`)
```typescript
import ts from "typescript";

/**
 * Custom Transformer: Mentransformasikan pemanggilan metode yang memiliki
 * komentar JSDoc '@traceable' agar mencetak eksekusi metrik secara otomatis.
 */
export function createTraceTransformer(
  program: ts.Program
): ts.TransformerFactory<ts.SourceFile> {
  const checker = program.getTypeChecker();

  return (context: ts.TransformationContext): ts.Transformer<ts.SourceFile> => {
    const { factory } = context;

    function visitor(node: ts.Node): ts.Node {
      if (ts.isMethodDeclaration(node) && node.body) {
        const fullText = node.getFullText();
        const hasTraceAnnotation = fullText.includes("@traceable");

        if (hasTraceAnnotation) {
          const methodName = node.name.getText();

          // Buat AST Statement: console.log(`[Trace] Invoking: ${methodName}`);
          const logStatement = factory.createExpressionStatement(
            factory.createCallExpression(
              factory.createPropertyAccessExpression(
                factory.createIdentifier("console"),
                factory.createIdentifier("info")
              ),
              undefined,
              [
                factory.createStringLiteral(
                  `[Auto-Trace] Entering execution scope: ${methodName}`
                ),
              ]
            )
          );

          // Update body method dengan menyuntikkan statement ke indeks pertama
          const updatedBody = factory.updateBlock(
            node.body,
            [logStatement, ...node.body.statements]
          );

          return factory.updateMethodDeclaration(
            node,
            node.modifiers,
            node.asteriskToken,
            node.name,
            node.questionToken,
            node.typeParameters,
            node.parameters,
            node.type,
            updatedBody
          );
        }
      }

      return ts.visitEachChild(node, visitor, context);
    };

    return (sourceFile: ts.SourceFile) => {
      return ts.visitNode(sourceFile, visitor) as ts.SourceFile;
    };
  };
}
```

##### 4. Service Implementation (`packages/service-order/src/order-service.ts`)
```typescript
export interface ProcessOrderRequest {
  readonly orderId: string;
  readonly amountInCents: bigint;
}

export class OrderExecutionService {
  /**
   * @traceable
   */
  public async executeSettlement(request: ProcessOrderRequest): Promise<void> {
    if (request.amountInCents <= 0n) {
      throw new Error("Invalid settlement amount");
    }
    // Business logic settlement
  }
}
```

##### 5. Programmatic Compiler Invocation with Transformer Hooks
```typescript
import ts from "typescript";
import path from "node:path";
import { createTraceTransformer } from "./tools/transformers/trace-transformer.js";

function executeEnterpriseBuild(configFilePath: string): void {
  const parsedCommandLine = ts.getParsedCommandLineOfConfigFile(
    configFilePath,
    {},
    {
      ...ts.sys,
      onUnRecoverableConfigFileDiagnostic: (diag) => {
        console.error(ts.formatDiagnosticsWithColorAndContext([diag], host));
      },
    }
  );

  if (!parsedCommandLine) {
    throw new Error(`Failed to parse config: ${configFilePath}`);
  }

  const host = ts.createCompilerHost(parsedCommandLine.options);
  const program = ts.createProgram({
    rootNames: parsedCommandLine.fileNames,
    options: parsedCommandLine.options,
    host,
  });

  const diagnostics = [
    ...program.getSyntacticDiagnostics(),
    ...program.getSemanticDiagnostics(),
  ];

  if (diagnostics.length > 0) {
    console.error(ts.formatDiagnosticsWithColorAndContext(diagnostics, host));
    process.exit(1);
  }

  const customTransformer = createTraceTransformer(program);

  const emitResult = program.emit(
    undefined,
    undefined,
    undefined,
    undefined,
    {
      before: [customTransformer],
    }
  );

  if (emitResult.emitSkipped) {
    console.error("Emit process failed terminating build.");
    process.exit(1);
  }

  console.log("Enterprise build completed with custom AST modifications.");
}

executeEnterpriseBuild(path.resolve(process.cwd(), "packages/service-order/tsconfig.json"));
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Arsitektur**: Core Banking Micro-monorepo (1.8 juta baris kode TypeScript, 84 packages internal, 32 microservices).
- **Masalah**: Waktu pipeline CI/CD pada tahap `test:types` memakan waktu 38 menit. Developer sering mengalami crash `FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory` saat menjalankan `tsc` lokal.

#### Investigasi Teknis (Root Cause Analysis)
1. Single monolithic root `tsconfig.json` yang memasukkan seluruh source code via `include: ["packages/*/src"]`.
2. Checker melakukan rekalkulasi berulang terhadap package utilities dasar (`@bank/primitives`, `@bank/crypto`) setiap kali unit service diperiksa.
3. Struktur *barrel files* (`index.ts` dengan ratusan `export * from ...`) memaksa Parser memuat ribuan node AST yang tidak terpakai ke dalam memori.

#### Solusi Arsitektur
1. **Penerapan Strict Project References**:
   Seluruh 84 packages dimigrasikan ke model `composite: true` dengan isolated `rootDir` dan `outDir`.
2. **Kompilasi `.d.ts` Bertingkat (Layered Compilation)**:
   Paket foundational di-build satu kali menggunakan `tsc --build --emitDeclarationOnly`. Microservices downstream hanya me-resolve `.d.ts` dari direktori output upstream, menurunkan memory consumption Checker hingga 74%.
3. **Decoupled Pipeline pada CI**:
   - Fase Transpilasi JS: Didelegasikan ke ESBuild/SWC (Paralel, ~12 detik).
   - Fase Validasi Tipe: `tsc --build --noEmit` memanfaatkan shared cache `.tsbuildinfo` yang disimpan di AWS S3/GitHub Actions cache.

#### Hasil Metrik Produksi
- Durasi CI Typechecking: Turun dari **38 menit** menjadi **3 menit 12 detik** (pangkas ~91%).
- Node.js Max Old Space Memory footprint: Turun dari **7.4 GB** menjadi **1.2 GB**.
- *Developer Loop (Incremental build lokal)*: Dari **45 detik** menjadi **1.8 detik**.

---

### 9. Trade-offs

| Opsi Arsitektur | Keuntungan | Biaya & Kompromi |
|---|---|---|
| **Project References (`tsc -b`)** | - Kecepatan kompilasi inkremental maksimal.<br>- Enkapsulasi batas domain modular yang rigid.<br>- Skalabilitas build tak terbatas pada monorepo. | - Kompleksitas konfigurasi tinggi (`tsconfig.json` ganda: build, test, lint).<br>- Mengharuskan penerbitan deklarasi tipe `.d.ts` sebelum downstreams dikerjakan. |
| **Monolithic Single TSConfig** | - Sangat mudah diinisialisasi.<br>- Refactoring global otomatis didukung IDE tanpa perlu build step upstream. | - Memory heap membengkak eksponensial.<br>- Risiko degradasi build time parah seiring pertumbuhan basis kode. |
| **Transpile-Only (SWC/esbuild) + Background Typecheck** | - Transpilasi runtime super cepat (hitungan milidetik).<br>- Loop feedback HMR instan. | - Tidak ada validasi tipe saat dev server menyala.<br>- Rentan terhadap *silent runtime type-error* jika pipeline CI tidak memblokir commit yang gagal check. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Circular Reference Antar Project References
- **Symptom**: Error runtime kompilator: `error TS6202: Project references may not form a circular graph. Cycle detected in: packages/a -> packages/b -> packages/a`.
- **Root Cause**: `packages/a` mendaftarkan `packages/b` pada `references`, sementara `packages/b` mereferensikan balik `packages/a`.
- **Troubleshooting & Fix**: Pecah domain yang saling bergantung ke paket ketiga yang netral (misalnya `packages/a-contracts` atau `packages/shared-types`). Komunikasi antar-paket harus selalu bersifat uni-directional DAG.

#### 2. Deklarasi Output Bocor di Luar `rootDir`
- **Symptom**: Error: `error TS6059: File '...' is not under 'rootDir' '...'. 'rootDir' is expected to contain all source files.`
- **Root Cause**: Source code di dalam package mengimpor file di luar batas `rootDir` via relative path (`../../packages/core/src/index.ts`) alih-alih mengimpor dari deklarasi paket (`@enterprise/core`).
- **Fix**: Selalu impor melalui nama package yang dipetakan pada `references` dan file `package.json` workspace. Jangan pernah menggunakan deep relative paths melompati root package.

#### 3. State Mutability Bug pada Custom AST Transformer
- **Symptom**: Kompiler menghasilkan kode rusak atau crash internal: `TypeError: Cannot read properties of undefined (reading 'flags')`.
- **Root Cause**: Engineer mengubah properti AST Node secara langsung (misal: `node.name = newIdentifier`). AST Node di TypeScript bersifat *immutable*.
- **Fix**: Selalu gunakan helper method dari `context.factory.update*` atau `context.factory.create*` untuk menghasilkan node clone baru.

---

### 11. Best Practices (Production Checklist)

- [ ] Aktifkan `"composite": true` di seluruh paket pustaka internal yang dikonsumsi oleh paket lain.
- [ ] Pastikan `"declaration": true` dan `"declarationMap": true` selalu aktif bersamaan untuk memungkinkan navigasi "Go-to-Definition" IDE melompat ke file `.ts` asli, bukan ke `.d.ts`.
- [ ] Tetapkan nilai spesifik `"tsBuildInfoFile": "./dist/.tsbuildinfo"` untuk menghindari polusi artefak cache di root direktori.
- [ ] Larang penggunaan deep relative imports melintasi batas package boundary (`eslint-plugin-import` / boundary rules).
- [ ] Pisahkan konfigurasi typechecking development dan produksi menggunakan skema *Solution Style tsconfig* (`tsconfig.solution.json`).
- [ ] Pastikan compiler flag `"isolatedModules": true` aktif jika tim menggunakan SWC, Babel, atau esbuild untuk bundling agar terhindar dari konstruksi TS yang tidak didukung isolated transpilation (misal: `const enum` non-inlined).
- [ ] Audit AST Transformer agar tidak menjalankan operasi I/O asinkron yang memblokir single-thread compiler emitter.

---

### 12. Hands-on Practice

Buat dan jalankan instruksi ini untuk direktori `hands-on/m02/`.

#### Langkah 1: Siapkan Struktur Workspace
```bash
mkdir -p hands-on/m02/project-ref-lab
cd hands-on/m02/project-ref-lab
mkdir -p packages/contracts/src packages/domain-ledger/src
```

#### Langkah 2: Konfigurasi Root Solution tsconfig
Tulis file `hands-on/m02/project-ref-lab/tsconfig.json`:
```json
{
  "files": [],
  "references": [
    { "path": "./packages/contracts" },
    { "path": "./packages/domain-ledger" }
  ]
}
```

#### Langkah 3: Konfigurasi Package `contracts`
Tulis file `hands-on/m02/project-ref-lab/packages/contracts/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "composite": true,
    "declaration": true,
    "declarationMap": true,
    "rootDir": "./src",
    "outDir": "./dist",
    "tsBuildInfoFile": "./dist/.tsbuildinfo",
    "strict": true
  },
  "include": ["src/**/*"]
}
```

Tulis file `hands-on/m02/project-ref-lab/packages/contracts/src/index.ts`:
```typescript
export interface TransactionPayload {
  readonly id: string;
  readonly amount: number;
}
```

#### Langkah 4: Konfigurasi Package `domain-ledger`
Tulis file `hands-on/m02/project-ref-lab/packages/domain-ledger/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "composite": true,
    "declaration": true,
    "declarationMap": true,
    "rootDir": "./src",
    "outDir": "./dist",
    "tsBuildInfoFile": "./dist/.tsbuildinfo",
    "strict": true
  },
  "references": [
    { "path": "../contracts" }
  ],
  "include": ["src/**/*"]
}
```

Tulis file `hands-on/m02/project-ref-lab/packages/domain-ledger/src/index.ts`:
```typescript
import { TransactionPayload } from "../../contracts/dist/index.js";

export function recordTransaction(tx: TransactionPayload): void {
  console.log(`Commit Tx: ${tx.id} for amount: ${tx.amount}`);
}
```

#### Langkah 5: Jalankan Orchestrated Build
```bash
# Jalankan build komprehensif menggunakan mode orchestrator
npx tsc --build hands-on/m02/project-ref-lab/tsconfig.json --verbose

# Verifikasi keluaran
ls -la hands-on/m02/project-ref-lab/packages/contracts/dist/
ls -la hands-on/m02/project-ref-lab/packages/domain-ledger/dist/
```

Amati pembuatan file `.d.ts`, `.d.ts.map`, `.js`, dan `.tsbuildinfo`. Jalankan perintah build sekali lagi dan perhatikan log: *"is up to date because newest input is older than oldest output"* (Early bailout incremental).

---

### 13. Exercise

#### Level: Easy
Buka Compiler API TypeScript dan buat fungsi `extractPublicMethods(sourceCode: string): string[]`. Gunakan `ts.createSourceFile` untuk mem-parse string sumber dan kumpulkan nama-nama metode publik dari seluruh deklarasi kelas yang ada.

#### Level: Medium
Diberikan monorepo dengan 3 tingkat kedalaman dependensi: `database-schema` -> `repository-layer` -> `http-gateway`.
1. Konfigurasikan file `tsconfig.json` masing-masing package menggunakan `composite: true`.
2. Pastikan `repository-layer` menghasilkan `.d.ts` yang dikonsumsi oleh `http-gateway`.
3. Simulasikan skenario error di mana `http-gateway` mencoba mengimpor model dari `database-schema` tanpa mendeklarasikan `database-schema` di dalam blok `references` miliknya.

#### Level: Hard
Tulis custom AST Transformer plugin (`transformEnumToUnion`) yang mencari deklarasi tipe `enum Status { ACTIVE, INACTIVE }` dan secara programatis mentransformasikannya menjadi literal union statement type alias `type Status = "ACTIVE" | "INACTIVE";` dan emisi const object mapping yang sepadan, mempertahankan komentar JSDoc yang menempel pada masing-masing member enum.

---

### 14. Challenge

**Skenario**:
Perusahaan Financial Technology tempat Anda bekerja mengalami masalah kepatuhan data privasi (GDPR/PCI-DSS). Seringkali logging audit mencetak properti sensitif seperti PIN atau nomor kartu kredit ke sistem observabilitas cloud.

**Spesifikasi Tantangan**:
Rancang dan bangun sistem custom tooling berbasis **TypeScript Compiler API & AST Transformer Engine**:
1. Buat custom decorator atau property annotation `@Sensitive()`.
2. Bangun Custom Compiler Transformer yang menginspeksi statement serialisasi JSON (`JSON.stringify(x)`) atau statement log (`logger.info(x)`).
3. Jika argumen yang diteruskan ke logger memiliki tipe data (berdasarkan validasi semantik `ts.TypeChecker`) yang mengandung properti beranotasi `@Sensitive()`, compiler harus secara otomatis menginjeksi AST Masking Proxy yang menutupi nilai string tersebut menjadi `"***REDACTED***"` pada level emisi JavaScript, **tanpa** memerlukan modifikasi manual di kode runtime aplikasi.
4. Jika objek diteruskan ke fungsi enkripsi internal (`cryptoService.encrypt(x)`), AST Transformer **tidak boleh** melakukan masking.
5. Transformer harus terintegrasi bersih dalam build monorepo berbasis `tsc --build` menggunakan `ts-patch` atau programmatic compiler runner tanpa merusak *source-maps*.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. **Apa perbedaan mendasar antara tahap Scanning dan Parsing pada arsitektur compiler TypeScript?**
   *Jawaban*: Scanning (Lexer) memecah string karakter mentah menjadi token individual (`SyntaxKind`) tanpa mengetahui hierarki sintaksis. Parsing mengonsumsi stream token tersebut dan membentuk struktur pohon hierarkis hirarki sintaksis yang disebut Abstract Syntax Tree (AST).

2. **Mengapa flag `"composite": true` mengharuskan aktivasi `"declaration": true`?**
   *Jawaban*: Karena esensi dari project references adalah memungkinkan proyek downstream untuk melakukan typechecking hanya dengan membaca interface/kontrak publik (`.d.ts`) dari upstream project, tanpa harus mem-parse dan me-resolve seluruh kode implementasi upstream dari nol.

3. **Apa isi utama dari file `.tsbuildinfo` yang dihasilkan oleh build inkremental?**
   *Jawaban*: File ini berisi hash kriptografis dari file-file sumber, konfigurasi compiler, path dependensi modul eksternal, dan graf topologis file untuk mendeteksi apakah suatu node atau dependensinya telah mengalami mutasi sejak build terakhir.

4. **Kapan fase *Binding* terjadi pada TypeScript compiler?**
   *Jawaban*: Binding terjadi setelah Abstract Syntax Tree (AST) terbentuk oleh Parser dan sebelum Type Checker beroperasi. Binder bertugas membuat `Symbol` dan menghubungkan berbagai deklarasi node ke scope yang sesuai.

5. **Apa fungsi utama dari properti `"declarationMap": true` pada project references monorepo?**
   *Jawaban*: Menghasilkan file peta sourcemap (`.d.ts.map`) yang memetakan file deklarasi `.d.ts` kembali ke file sumber asli `.ts`. Hal ini memungkinkan fitur IDE "Go to Definition" menavigasi developer langsung ke source code paket upstream daripada berhenti di file deklarasi tipe.

#### Intermediate Questions
1. **Mengapa compiler TypeScript tidak mengizinkan dependensi sirkular antar paket dalam mode Project References (`tsc -b`)?**
   *Jawaban*: Kompilator harus membangun Directed Acyclic Graph (DAG) untuk menentukan urutan emisi file deklarasi `.d.ts`. Jika terdapat siklus ($A \to B \to A$), tidak ada *base case* yang dapat di-emit pertama kali tanpa mengandalkan deklarasi dari paket lainnya, menyebabkan deadlock resolusi semantik.

2. **Apa yang dimaksud dengan konsep *Lazy Evaluation* pada `ts.TypeChecker`?**
   *Jawaban*: `TypeChecker` tidak melakukan validasi tipe pada seluruh AST secara sekaligus. Checker hanya mengomputasi tipe dari suatu node, mengurai type alias, atau memeriksa union ketika node tersebut secara eksplisit diakses atau direferensikan dalam aliran eksekusi logika semantic check. Hal ini menghemat CPU dan memori secara signifikan.

3. **Bagaimana cara yang benar untuk memutasi sebuah node AST di dalam Custom Transformer tanpa memicu compiler runtime crashes?**
   *Jawaban*: Node AST bersifat *read-only*. Alih-alih melakukan assignment langsung (misal: `node.name = newName`), developer wajib menggunakan factory context (`ts.TransformationContext.factory`) seperti `factory.updateMethodDeclaration` atau `factory.createIdentifier` yang mengembalikan instance node baru dengan referensi pointer flags yang valid.

4. **Apa implikasi aktivasi `"isolatedModules": true` terhadap fitur TypeScript tertentu seperti `const enum` dan `export type`?**
   *Jawaban*: Transpiler berkas tunggal (seperti SWC atau esbuild) tidak memiliki visibilitas terhadap keseluruhan type graph. Oleh karena itu, fitur yang membutuhkan analisis multi-file seperti *ambient const enum* (yang harus di-inlining nilainya) atau re-export tipe tanpa penanda eksplisit `export type { T }` akan menghasilkan error, karena transpiler berkas tunggal tidak tahu apakah identifier tersebut bernilai runtime atau sekadar tipe statis.

5. **Jelaskan perbedaan mendasar antara `ts.visitNode` dan `ts.visitEachChild` pada implementasi Custom Transformer!**
   *Jawaban*: `ts.visitNode` mengevaluasi transformer visitor terhadap node target tunggal (root level dari eksekusi). Sementara `ts.visitEachChild` secara rekursif menelusuri seluruh turunan langsung (anak-anak) dari suatu node dan mengaplikasikan fungsi visitor pada masing-masing child node tersebut.

#### Skenario Kasus Produksi
1. **Skenario Kasus 1: Memori CI Meledak pada Monorepo Skala Besar**
   *Permasalahan*: Tim platform menambahkan 10 microservices baru ke dalam monorepo pnpm. Pipeline CI mendadak gagal dengan error `JavaScript heap out of memory` saat menjalankan `tsc --noEmit`. Server CI memiliki limitasi RAM 4GB.
   *Analisis*: Pemeriksaan menemukan bahwa root build script menjalankan `tsc --noEmit` yang mengonsumsi seluruh file monorepo dalam satu proses node runtime tunggal, memicu saturasi alokasi heap V8 oleh TypeChecker.
   *Solusi Arsitektur*:
   1. Konfigurasi seluruh paket dengan Project References (`composite: true`).
   2. Ganti script pipeline CI menjadi `tsc --build --noEmit`.
   3. Jika memori masih kritis, gunakan flag build orchestration terdistribusi (misal: `turbo run typecheck` atau `nx affected --target=typecheck`) yang menjalankan proses `tsc` per-package secara independen di level OS thread yang terpisah, sehingga garbage collection V8 dapat membebaskan memori per-paket secara deterministik.

2. **Skenario Kasus 2: Dev-Server Mengalami Infinite-Reload Loop Saat Project References Diaktifkan**
   *Permasalahan*: Saat developer mengubah file di `packages/core/src/util.ts`, development watcher (Vite/Webpack) melakukan reload tanpa henti (*infinite rebuild loop*).
   *Analisis*: Package dependent mengimpor langsung dari `packages/core/dist`. Ketika file diubah, `tsc -b -w` memperbarui file `dist/util.js` dan `dist/util.d.ts`. Vite mendeteksi perubahan pada `dist/`, memicu hot reload, yang kemudian memicu event build lain karena modifikasi timestamp file output.
   *Solusi Arsitektur*:
   Pada level dev-server lokal, konfigurasikan module resolution aliases (misal: `tsconfig.paths` atau Vite `resolve.alias`) untuk langsung memetakan package name `@enterprise/core` ke *source entrypoint* `./packages/core/src/index.ts` selama mode development. Hanya gunakan output `dist/` saat fase validasi CI dan rilis produksi.

3. **Skenario Kasus 3: Type Mismatch Ghost Error Pasca-Refactoring**
   *Permasalahan*: Seorang engineer mengubah nama properti pada interface di `packages/domain`. CI lokal lolos, namun CI remote gagal dengan error: `Property 'orderNumber' does not exist on type 'OrderPayload'`.
   *Analisis*: File `.tsbuildinfo` lokal engineer tersebut sudah usang atau terdapat artefak `.d.ts` yatim (*orphaned output files*) di direktori `dist/` lokal yang tidak lagi memiliki korespondensi dengan file sumber, tetapi masih terbaca oleh module resolver.
   *Solusi Arsitektur*:
   1. Tambahkan target clean script: `tsc --build --clean` pada root workspace untuk memvalidasi penghapusan artefak kompilasi lama.
   2. Terapkan konfigurasi `"clean": true` pada pipeline build runner dan pastikan CI selalu melakukan *fresh clone* tanpa menggunakan persistent build output cache yang sudah usang tanpa mekanisme validasi hash yang ketat.

---

### 16. Summary

- **Pipeline Internal TS**: Terdiri dari lima layer diskret: `Scanner` -> `Parser` -> `Binder` -> `Checker` -> `Emitter`. Memahami batasan masing-masing lapisan esensial untuk mendiagnosis performa kompilasi.
- **Project References**: Solusi fundamental monorepo untuk mengontrol pertumbuhan kompleksitas kompilasi dari $O(N)$ ke DAG berbasis modularitas paket independen.
- **Incrementalism via `.tsbuildinfo`**: Kompilator memvalidasi status hash artefak internal untuk melakukan bypass typechecking secara aman pada subsistem kode yang tidak termutasi.
- **Custom Transformers**: Mekanisme Compiler API untuk merekonstruksi, memodifikasi, atau menghasilkan kode pada fase transformasi AST sebelum JavaScript dicetak, menjamin optimasi zero-cost abstraksi di runtime.
- **Produksi Monorepo Modern**: Kunci performa enterprise terletak pada *decoupling*: manfaatkan isolated-transpilers (SWC/esbuild) untuk kecepatan transpilasi aset, dan sandarkan integritas tipe sistem pada `tsc --build` yang terisolasi via Project References.