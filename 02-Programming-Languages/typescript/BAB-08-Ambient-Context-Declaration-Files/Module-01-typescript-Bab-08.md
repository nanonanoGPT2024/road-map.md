---

# SEKSI 01 — IDENTITAS MODUL

*   **Kurikulum:** Enterprise TypeScript & Type-System Architecture
*   **Kategori:** 02-Programming-Languages
*   **Bab:** 08 — Type System Engineering & Integration
*   **Modul:** 01 — Ambient Context & Declaration Files
*   **Prasyarat:** Pemahaman mendalam tentang TypeScript Modules (ESM/CJS), Structural Subtyping, Interface Merging, Type Narrowing, dan konfigurasi dasar `tsconfig.json`.
*   **Estimasi Durasi:** 150 - 180 Menit
*   **Target Level:** Advanced / Senior Software Engineer

---

# SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik diharapkan mampu:

1.  **Mendekonstruksi Mekanisme Ambient Context (Kognitif - C4):** Mengartikulasikan bagaimana TypeScript Compiler (`tsc`) membedakan deklarasi ambient dari runtime symbols, serta bagaimana AST (Abstract Syntax Tree) memproses token `declare`.
2.  **Merancang dan Mengimplementasikan Berkas Deklarasi Tipe (Psikomotorik - P4):** Menulis berkas `.d.ts` yang robust untuk pustaka JavaScript vanilla, modul eksternal pihak ketiga (untyped npm packages), dan asset loaders (SVG, CSS Modules, binary files).
3.  **Mengeksekusi Module & Global Augmentation (Psikomotorik - P4):** Melakukan patching dan augmentasi pada objek global (`Window`, `ProcessEnv`) serta pustaka pihak ketiga menggunakan sintaks `declare global` dan `declare module` tanpa merusak integritas upstream type safety.
4.  **Menganalisis dan Memitigasi Type Illusion Vulnerabilities (Kognitif - C4, Afektif - A3):** Mendeteksi deviasi runtime dari kontrak tipe compile-time akibat kesalahan penulisan ambient declaration, serta menerapkan validasi defensif (runtime checking vs compile-time contract).
5.  **Mengoptimalkan Resolusi Type Checker (Kognitif - C5):** Mengonfigurasi `typeRoots`, `types`, dan direktif triple-slash (`/// <reference />`) untuk performa kompilasi optimal dalam monorepo berskala besar.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam pengembangan TypeScript standar, kode yang Anda tulis memiliki eksistensi ganda: **Design-Time Contract** (tipe, interface) dan **Runtime Artifact** (fungsi, class, variabel). Namun, saat berhadapan dengan **Ambient Context**, Anda harus mengadopsi mental model yang sepenuhnya berbeda:

### The "Ghost in the Machine" Contract
Ambient declaration (`declare`) adalah **janji murni** yang Anda berikan kepada TypeScript compiler. Saat Anda menulis:

```typescript
declare const __PRODUCTION_API_KEY__: string;
```

Anda secara eksplisit menginstruksikan `tsc`:
> *"Compiler, jangan mencari implementasi JavaScript dari variabel ini. Jangan menghasilkan output byte apa pun untuk deklarasi ini. Percayalah pada saya, entitas ini pasti sudah ada di memory space saat runtime dijalankan."*

Jika entitas tersebut ternyata tidak ada di runtime, Node.js atau browser akan melemparkan `ReferenceError`, namun `tsc` tidak akan memberikan peringatan kompilasi sama sekali. Inilah yang disebut **The Ambient Blindspot**.

### Module Context vs Script Context
Sebuah berkas `.d.ts` memiliki dua mode eksistensi tergantung ada atau tidaknya token `import` atau `export` di level root:
1.  **Script Context (Global Ambient):** Jika berkas **tidak memiliki** `import` atau `export` tingkat atas, seluruh deklarasi di dalamnya otomatis tumpah ke dalam ruang lingkup global (*Global Namespace Pollution*).
2.  **Module Context:** Begitu ada satu saja token `import` atau `export`, berkas tersebut terkunci sebagai ES Module terisolasi. Deklarasi di dalamnya tidak lagi global, kecuali jika secara eksplisit dimasukkan ke dalam `declare global { ... }`.

```
                    ┌───────────────────────────────┐
                    │ File: my-declarations.d.ts    │
                    └───────────────┬───────────────┘
                                    │
                    Contains root import / export?
                                   / \
                                  /   \
                             YES /     \ NO
                                v       v
              ┌───────────────────┐   ┌──────────────────────────┐
              │   Module Scope    │   │  Global Ambient Scope    │
              │ (Isolated types)  │   │ (Available everywhere)   │
              └─────────┬─────────┘   └──────────────────────────┘
                        │
       Requires `declare global {}`
         to affect outside scope
```

Senior Engineer memperlakukan berkas `.d.ts` sebagai dokumen legalitas arsitektur: ketat, eksplisit, minimalis, dan tidak pernah mengasumsikan keberadaan runtime tanpa audit.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Proses kompilasi TypeScript melibatkan pipeline lexing, parsing, binding, type checking, dan emit. Ambient context dan declaration files berinteraksi secara spesifik di dalam fase-fase tersebut.

### Siklus Hidup Resolusi dan Eliminasi Ambient Context

```
+---------------------------------------------------------------------------------------+
|                                TypeScript Compilation                                 |
+---------------------------------------------------------------------------------------+
                                        │
           +────────────────────────────┴────────────────────────────+
           ▼                                                         ▼
   [ User Code (.ts) ]                                   [ Ambient Files (.d.ts) ]
   - Implementasi Logic                                  - Third-party packages (@types)
   - Runtime values                                      - In-house ambient types
           │                                                         │
           ▼                                                         ▼
  +──────────────────+                                     +──────────────────+
  | Parser: Creates  |                                     | Parser: Creates  |
  | SourceFile AST   |                                     | SourceFile AST   |
  +────────┬─────────+                                     +────────┬─────────+
           │                                                         │
           └────────────────────────────┬────────────────────────────┘
                                        ▼
                            +───────────────────────+
                            |  Binder: Construct    |
                            |  Symbol Table Entries |
                            |  (flags: Ambient)     |
                            +───────────┬───────────+
                                        │
                                        ▼
                            +───────────────────────+
                            |     Type Checker      |
                            | Cross-reference ASTs  |
                            | & Validate Operations |
                            +───────────┬───────────+
                                        │
                                        ▼
                            +───────────────────────+
                            |         Emitter       |
                            +───────────┬───────────+
                                        │
                ┌───────────────────────┴───────────────────────┐
                ▼                                               ▼
       [ Output Code (.js) ]                          [ Output Types (.d.ts) ]
  (Ambient nodes completely stripped)             (Only if `declaration: true`)
```

### Type Resolution Search Tree (`tsc`)

Ketika TypeScript menemukan referensi ke module yang tidak berwujud file `.ts` (misal: `import { parse } from 'untyped-csv'`), TypeScript mengevaluasi resolusi sebagai berikut:

```
[Import Statement: 'untyped-csv']
               │
               ▼
   [Does node_modules/untyped-csv/package.json exist?]
          │                      │
         YES                     NO
          │                      │
          ▼                      ▼
[Has "types" or "typings"?]   [Scan node_modules/@types/untyped-csv]
     │          │                        │                 │
    YES         NO                     FOUND           NOT FOUND
     │          │                        │                 │
     │          ▼                        │                 ▼
     │   [Check index.d.ts]              │       [Scan tsconfig typeRoots]
     │          │                        │                 │
     │       FOUND                       │               FOUND?
     │          │                        │              /     \
     ▼          ▼                        ▼            YES      NO
+──────────────────────────────────────────+           │        │
| Bind Symbol to Package Type Definitions |◄──────────┘        ▼
+──────────────────────────────────────────+           [Check Ambient Modules]
                                                       (`declare module "untyped-csv"`)
                                                                │
                                                              FOUND?
                                                             /      \
                                                           YES       NO
                                                            │         │
                                                            ▼         ▼
                                                       [Bound]   [TS2307 Error:
                                                                 Cannot find module]
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The `Ambient` Modifier Flag di Internal AST
Di dalam codebase compiler TypeScript (`src/compiler/types.ts`), setiap node AST memiliki sekumpulan bitwise flags (`ModifierFlags`). Ketika parser menemukan token `declare`, ia menyematkan bit:

```typescript
ModifierFlags.Ambient = 1 << 1 // Menandai node sebagai deklarasi ambient
```

Ketika AST ditransformasi ke JavaScript oleh Emitter (`src/compiler/emitter.ts`), fungsi traversal secara eksplisit memfilter setiap node yang memiliki flag ini:

```typescript
// Pseudocode dari compiler logic TSC:
function isEmitHalted(node: Node): boolean {
    if (node.flags & NodeFlags.Ambient || node.modifiers & ModifierFlags.Ambient) {
        return true; // Node diabaikan sepenuhnya, tidak menghasilkan byte JS
    }
    return false;
}
```

### 2. Anatomi Berkas `.d.ts`
Berkas `.d.ts` hanya diizinkan memuat **tipe surface level**. Tidak boleh ada:
*   Inisialisasi variabel (`declare const x = 10;` -> *Illegal jika ada body/expression*)
*   Function bodies (`declare function foo() { ... }` -> *Syntax Error*)
*   Class constructor bodies dan logic implementation.

Semua deklarasi otomatis berstatus `ambient`, bahkan jika Anda tidak menyertakan kata kunci `declare` di depan deklarasi antarmuka (`interface`) atau alias tipe (`type`). Namun, untuk identifier yang mewakili runtime identifiers (`var`, `let`, `const`, `function`, `class`, `enum`, `namespace`), kata kunci `declare` wajib dicantumkan jika berada dalam script context.

### 3. Namespace/Module Merging Mechanism
TypeScript memiliki Symbol Table di mana setiap identifier diasosiasikan dengan tiga status kategori:
*   **Value:** Ada di runtime (misal: variabel, fungsi konvensional, class).
*   **Type:** Hanya di compile-time (misal: `type`, `interface`).
*   **Namespace:** Kontainer untuk mengelompokkan entitas lain.

`declare` memungkinkan kita memanipulasi kategori-kategori ini. Module Augmentation bekerja melalui prinsip **Declaration Merging**: Jika nama namespace/modul dan nama antarmuka identik berada dalam satu scope, Type Checker akan menyatukan daftar anggota (*members list*) mereka menjadi satu `Symbol` tunggal.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. `declare` Primitive: Runtime Identifier Representation
Anda dapat merepresentasikan berbagai entitas runtime yang diinjeksikan secara eksternal (misalnya oleh CDN, Web Worker context, atau polyfill):

```typescript
// Global Primitive Variable
declare const __BUILD_TIMESTAMP__: number;

// Global Function
declare function initializeTelemetry(tenantId: string, debugMode?: boolean): boolean;

// Global Class (Hanya mendefinisikan signature)
declare class SecureStorageDriver {
    constructor(secretKey: string);
    public getItem(key: string): string | null;
    public setItem(key: string, value: string): void;
    private encrypt(data: string): string; // Compile-time metadata only
}
```

### 2. Ambient Modules (`declare module "..."`)
Digunakan untuk merepresentasikan modul CommonJS atau ESM yang tidak memiliki types internal.

#### Wildcard Module Declarations (Asset Loading)
TypeScript Engine secara default hanya memahami modul JavaScript/TypeScript. Untuk mengimpor file non-TS seperti CSS Modules atau aset grafis, deklarasi ambient wildcard digunakan:

```typescript
declare module "*.module.css" {
    const classes: Readonly<Record<string, string>>;
    export default classes;
}

declare module "*.svg" {
    import { FunctionComponent, SVGProps } from "react";
    const ReactComponent: FunctionComponent<SVGProps<SVGSVGElement>>;
    export default ReactComponent;
}
```

#### Exact Module Declarations
Untuk membungkus pustaka npm yang tidak bertipe:

```typescript
declare module "fast-string-hash" {
    export function murmur3(input: string, seed?: number): string;
    export function sha1(input: string): string;
}
```

### 3. Module Augmentation (`declare module` Overriding Existing Packages)
Teknik ini memperluas kontrak pustaka eksternal yang tipenya sudah terdaftar, tanpa mengedit berkas di `node_modules`.

```typescript
import "express-session";

declare module "express-session" {
    interface SessionData {
        userId: string;
        roles: Array<"ADMIN" | "USER" | "AUDITOR">;
        mfaVerified: boolean;
    }
}
```

### 4. Global Augmentation (`declare global`)
Ketika berkas deklarasi bertindak sebagai ES Module (memiliki `import`/`export`), modifikasi ke global scope harus dibungkus blok `declare global`:

```typescript
import { Logger } from "./logger";

declare global {
    interface Window {
        __APPLICATION_METRICS__: {
            log: Logger;
            flush: () => Promise<void>;
        };
    }

    namespace NodeJS {
        interface ProcessEnv {
            NODE_ENV: "development" | "production" | "test";
            DATABASE_URL: string;
            PORT?: string;
        }
    }
}

export {}; // Memaksa file ini menjadi module jika belum memiliki import/export
```

### 5. Triple-Slash Directives
Sintaksis direktif berformat XML komentar ini digunakan oleh TypeScript untuk mengelola dependensi antar file definisi sebelum compiler option `moduleResolution` modern berkembang:

*   `/// <reference types="node" />`: Menginstruksikan compiler untuk menyertakan paket tipe dari `@types/node`.
*   `/// <reference path="./custom-primitives.d.ts" />`: Membuat dependensi eksplisit ke file deklarasi lokal.
*   `/// <reference lib="es2022.intl" />`: Menyertakan library tipe built-in TypeScript tertentu.

*Catatan Industri Modern:* Di era ES modules dan `tsconfig.json` paths/typeRoots modern, penggunaan `/// <reference path="..." />` umumnya dihindari kecuali pada setup pipeline tooling tingkat rendah atau deklarasi polyfill standalone.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah tiga skenario fundamental penanganan Ambient Context yang biasa ditemui di skala arsitektur.

### Struktur Proyek
```
my-ts-project/
├── tsconfig.json
├── package.json
└── src/
    ├── types/
    │   ├── assets.d.ts
    │   ├── globals.d.ts
    │   └── legacy-parser.d.ts
    ├── index.ts
    └── legacy-parser.js (Un-typed file simulasi)
```

#### 1. Asset Loader Shims (`src/types/assets.d.ts`)
```typescript
// Script Context (Global Ambient)
declare module "*.png" {
    const src: string;
    export default src;
}

declare module "*.json" {
    const value: Record<string, unknown>;
    export default value;
}
```

#### 2. Global Extension (`src/types/globals.d.ts`)
```typescript
export interface CustomPerformanceBeacon {
    mark(event: string): void;
    measure(name: string, startMark: string, endMark: string): number;
}

// Module Context: Requires 'declare global'
declare global {
    interface Window {
        __PERF_BEACON__?: CustomPerformanceBeacon;
    }

    namespace NodeJS {
        interface ProcessEnv {
            API_GATEWAY_URL: string;
            MAX_RETRY_COUNT: string;
        }
    }
}
```

#### 3. Typing Untyped Legacy CommonJS (`src/types/legacy-parser.d.ts`)
```typescript
declare module "legacy-parser" {
    export interface ParseOptions {
        strict?: boolean;
        encoding?: "utf-8" | "ascii";
    }

    export interface ParseResult<T = Record<string, unknown>> {
        timestamp: number;
        payload: T;
        errors: Error[];
    }

    export function parseDataStream<T = Record<string, unknown>>(
        inputBuffer: Buffer,
        options?: ParseOptions
    ): ParseResult<T>;

    export const VERSION: string;
}
```

#### 4. Konsumen Implementasi (`src/index.ts`)
```typescript
import icon from "./assets/logo.png";
import { parseDataStream, ParseResult } from "legacy-parser";

// 1. Evaluasi Global Augmentation
if (typeof window !== "undefined" && window.__PERF_BEACON__) {
    window.__PERF_BEACON__.mark("bootstrap-start");
}

// 2. Evaluasi Env Vars
const gatewayUrl: string = process.env.API_GATEWAY_URL;

// 3. Evaluasi Untyped Module Typing
interface UserPayload {
    id: string;
    accountLevel: number;
}

const dummyBuffer = Buffer.from('{"id":"usr_998","accountLevel":2}');
const result: ParseResult<UserPayload> = parseDataStream<UserPayload>(dummyBuffer, {
    strict: true,
    encoding: "utf-8"
});

console.log(`Loaded Asset: ${icon}`);
console.log(`Connected to: ${gatewayUrl}`);
console.log(`Parsed User ID: ${result.payload.id}`);
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Bedah File: `src/types/globals.d.ts`

```typescript
1: export interface CustomPerformanceBeacon {
2:     mark(event: string): void;
3:     measure(name: string, startMark: string, endMark: string): number;
4: }
```
*   **Baris 1:** Keyword `export` di level atas otomatis menetapkan file ini sebagai **Module Context**. Tipe `CustomPerformanceBeacon` tidak mencemari global namespace, tetapi harus diekspor dan diimpor jika dibutuhkan secara eksplisit.
*   **Baris 2–3:** Kontrak murni tipe fungsionalitas pengukuran performa.

```typescript
5: declare global {
6:     interface Window {
7:         __PERF_BEACON__?: CustomPerformanceBeacon;
8:     }
```
*   **Baris 5:** Blok `declare global` menembus batasan modul lokal dan mengekspos tipe langsung ke global scope runtime TypeScript.
*   **Baris 6:** Melakukan **Interface Merging** terhadap interface bawaan TypeScript `Window` (dari `lib.dom.d.ts`).
*   **Baris 7:** Menambahkan properti opsional `__PERF_BEACON__`. Penggunaan `?` merefleksikan realitas runtime: script beacon mungkin belum dimuat atau gagal dieksekusi.

```typescript
9:     namespace NodeJS {
10:        interface ProcessEnv {
11:            API_GATEWAY_URL: string;
12:            MAX_RETRY_COUNT: string;
13:        }
14:    }
15: }
```
*   **Baris 9–10:** Menargetkan interface `ProcessEnv` yang berada di dalam namespace `NodeJS` (disediakan oleh `@types/node`).
*   **Baris 11–12:** Memperluas tipe dictionary `process.env`. Default dari Node types adalah `Record<string, string | undefined>`. Dengan ini, `process.env.API_GATEWAY_URL` memiliki status `string` (terdefinisi secara mutlak di build kita).

### Bedah File: `src/types/legacy-parser.d.ts`

```typescript
1: declare module "legacy-parser" {
2:     export interface ParseOptions {
3:         strict?: boolean;
4:         encoding?: "utf-8" | "ascii";
5:     }
```
*   **Baris 1:** `declare module "legacy-parser"` membuat modul virtual/ambient. Nama string ini harus presisi sama dengan module specifier saat diimpor via `import ... from "legacy-parser"`.
*   **Baris 2–5:** Deklarasi opsi parsing. Nilai union `"utf-8" | "ascii"` membatasi input agar runtime tidak menerima sembarang string.

```typescript
7:     export interface ParseResult<T = Record<string, unknown>> {
8:         timestamp: number;
9:         payload: T;
10:        errors: Error[];
11:    }
```
*   **Baris 7–11:** Polimorfisme menggunakan Generic `T` dengan default parameter. Hal ini memberikan fleksibilitas ekstra kepada konsumen modul untuk mendefinisikan tipe payload yang dikembalikan parser.

```typescript
13:    export function parseDataStream<T = Record<string, unknown>>(
14:        inputBuffer: Buffer,
15:        options?: ParseOptions
16:    ): ParseResult<T>;
17: }
```
*   **Baris 13–16:** Function signature tanpa implementasi kurung kurawal `{}`. Menggunakan `Buffer` (berasal dari `@types/node`). Mengembalikan `ParseResult<T>`.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur Enterprise Payment Gateway & Broken Third-Party Typings
Anda memimpin arsitektur sistem pembayaran. Perusahaan Anda menghadapi dua tantangan integrasi:

1.  **Vendor SDK Lama Tanpa Tipe (`acme-fraud-detector.js`):** Script deteksi fraud legacy dimuat via inline `<script>` tag di reverse proxy/CDN. Script ini mengekspos objek global `window.AcmeFraudEngine` yang memiliki metode analitik sinkron dan asinkron.
2.  **Third-Party Typings Buggy / Tidak Kompatibel:** Paket npm `payment-crypto-provider` menyertakan dependensi `@types/payment-crypto-provider` bawaan, namun tim vendor lupa menyertakan properti `sessionEntropy` dan metode `rotateKeys()` pada interface `CipherClient` di rilis versi terbarunya, memicu compiler error `TS2339: Property 'rotateKeys' does not exist on type 'CipherClient'`.

### Sasaran Arsitektur:
1.  Menulis ambient declaration terpisah tanpa mengotori business logic.
2.  Menggunakan *Module Augmentation* untuk menambal antarmuka `CipherClient` tanpa menggunakan `// @ts-ignore` atau type casting `(client as any)`.
3.  Memastikan build system (Vite/Webpack + TSC) memvalidasi tipe tanpa runtime regression.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

### 1. Struktur Direktori Proyek

```
enterprise-payment/
├── tsconfig.json
├── package.json
├── types/
│   ├── acme-fraud-detector/
│   │   └── index.d.ts
│   └── crypto-patch/
│       └── payment-crypto-augmentation.d.ts
└── src/
    ├── services/
    │   └── payment-orchestrator.ts
    └── index.ts
```

### 2. Konfigurasi `tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "declaration": true,
    "strict": true,
    "skipLibCheck": false,
    "typeRoots": [
      "./node_modules/@types",
      "./types"
    ]
  },
  "include": ["src/**/*", "types/**/*"]
}
```

### 3. Deklarasi Global Ambient Script CDN (`types/acme-fraud-detector/index.d.ts`)

```typescript
// Script Scope (Tidak ada import/export di root file ini)

interface AcmeFingerprintResult {
    visitorId: string;
    riskScore: number; // 0.0 - 1.0
    botProbability: number;
    telemetry: {
        canvasHash: string;
        webglVendor: string;
    };
}

interface AcmeInitConfig {
    apiKey: string;
    strictMode: boolean;
    onAnomalyDetected?: (anomalyType: string) => void;
}

interface AcmeEngineInstance {
    version: string;
    init(config: AcmeInitConfig): Promise<void>;
    evaluateTransaction(payload: {
        amountCents: number;
        currency: "USD" | "EUR" | "IDR";
        recipientId: string;
    }): AcmeFingerprintResult;
}

// Inject ke Global Window
declare const AcmeFraudEngine: AcmeEngineInstance;
```

### 4. Patch Module Pihak Ketiga (`types/crypto-patch/payment-crypto-augmentation.d.ts`)

Mari kita asumsikan struktur internal asli dari vendor pihak ketiga:
```typescript
// Asumsi module "payment-crypto-provider" bawaan npm hanya memiliki:
// export class CipherClient { encrypt(d: string): string; }
```

Berikut file augmentasi kita:

```typescript
import "payment-crypto-provider";

declare module "payment-crypto-provider" {
    // Definisi tipe payload rotasi kunci
    export interface KeyRotationReport {
        rotatedAt: Date;
        previousKeyId: string;
        activeKeyId: string;
        bits: 256 | 512;
    }

    // Melakukan Interface Merging pada class/interface CipherClient
    export interface CipherClient {
        readonly sessionEntropy: string;
        rotateKeys(algorithm: "AES-GCM" | "CHACHA20-POLY1305"): Promise<KeyRotationReport>;
    }
}
```

### 5. Penggunaan di Layer Aplikasi (`src/services/payment-orchestrator.ts`)

```typescript
import { CipherClient } from "payment-crypto-provider";

export interface TransactionIntent {
    id: string;
    amount: number;
    currency: "USD" | "EUR" | "IDR";
    destinationAccount: string;
}

export class PaymentOrchestrator {
    private cryptoClient: CipherClient;

    constructor(client: CipherClient) {
        this.cryptoClient = client;
    }

    public async initializeFraudSystem(apiKey: string): Promise<void> {
        // Mengakses global ambient AcmeFraudEngine secara aman
        if (typeof AcmeFraudEngine === "undefined") {
            throw new Error("FATAL: AcmeFraudEngine script CDN failed to load.");
        }

        await AcmeFraudEngine.init({
            apiKey,
            strictMode: true,
            onAnomalyDetected: (anomaly: string) => {
                console.warn(`[SECURITY WARNING] Anomaly triggered: ${anomaly}`);
            }
        });

        console.info(`[FRAUD SYSTEM READY] Running Engine v${AcmeFraudEngine.version}`);
    }

    public async processTransaction(intent: TransactionIntent): Promise<{ success: boolean; txHash: string }> {
        // 1. Eksekusi Analitik Fraud via Global Ambient
        const fraudAnalysis = AcmeFraudEngine.evaluateTransaction({
            amountCents: intent.amount,
            currency: intent.currency,
            recipientId: intent.destinationAccount
        });

        if (fraudAnalysis.riskScore > 0.85) {
            throw new Error(`Transaction Rejected: Risk score too high (${fraudAnalysis.riskScore})`);
        }

        // 2. Eksekusi Modul yang Di-augmentasi
        // Properti sessionEntropy & metode rotateKeys divalidasi compiler tanpa error
        console.log(`Executing session entropy verification: ${this.cryptoClient.sessionEntropy}`);

        const rotationResult = await this.cryptoClient.rotateKeys("AES-GCM");
        console.info(`Security keys cycled to ID: ${rotationResult.activeKeyId}`);

        // Simulasi hashing
        const txHash = `0x${Buffer.from(intent.id + rotationResult.activeKeyId).toString("hex")}`;
        return {
            success: true,
            txHash
        };
    }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Pendekatan | Mekanisme & Kontrak | Kelebihan Utama | Kekurangan / Trade-offs | Use-Case Optimal |
| :--- | :--- | :--- | :--- | :--- |
| **Direct Ambient (`declare const / var`)** | Penulisan variabel langsung di script context (`.d.ts` tanpa import/export). | Sangat cepat dibuat, langsung resolve secara global tanpa import manual di tiap file. | **High Risk:** Rentan name collisions, tidak aman jika variabel tidak ada di runtime (menghasilkan ilusi tipe). | Third-party script CDN (Google Tag Manager, CDN Analytics) yang diinjeksi ke HTML. |
| **Module Augmentation (`declare module "pkg"`)** | Menggabungkan members baru ke modul yang sudah terinstal melalui interface merging. | Mempertahankan dependensi formal, strongly typed, tidak perlu modifikasi `node_modules` secara kotor (`patch-package`). | Rapuh terhadap breaking changes dari upstream vendor; butuh tracking ketat saat dependensi diupdate. | Menambal bug / missing types pada library npm yang lambat di-merge oleh maintainer. |
| **DefinitelyTyped (`@types/*`)** | Repositori komunitas terpusat untuk berkas tipe TypeScript. | Skala komunitas masif, review standar industri, integrasi zero-config via npm. | Status dependensi pihak ketiga independen; bisa out-of-sync dengan runtime package yang dipakai. | Standar industri untuk semua pustaka JavaScript murni tanpa native types bawaan. |
| **Wrapper Module (Adapter Pattern)** | Menulis file `.ts` pembungkus yang memanggil `require()` untyped code dan mengekspor typed facade. | Memberikan validasi runtime (defensive programming) sekaligus static typing, bukan hanya ilusi. | Membutuhkan alokasi memory tambahan, sedikit overhead CPU, dan boiler-plate code ekstra. | Core domain critical (Payment gateway, Crypto operations, Auth adapters). |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Accidental Module Transition
Ini adalah pitfall paling umum yang dialami engineer saat menulis berkas `.d.ts`:

```typescript
// types/globals.d.ts
// KITA INGIN MEMBUAT GLOBAL PROPERTY:
declare const APP_SECRET: string;

// Lalu seorang engineer menambahkan import tipe:
import { SystemConfig } from "./config";

declare const CONFIG: SystemConfig;
```

*Masalah:* Seketika baris `import` ditambahkan, `globals.d.ts` berubah dari **Script Context** menjadi **Module Context**. 
*Konsekuensi:* `APP_SECRET` dan `CONFIG` mendadak hilang dari global scope! Seluruh file `.ts` yang menggunakan variabel ini akan melempar error: `TS2304: Cannot find name 'APP_SECRET'`.
*Solusi:* Wajib dibungkus dengan `declare global`:

```typescript
import { SystemConfig } from "./config";

declare global {
    const APP_SECRET: string;
    const CONFIG: SystemConfig;
}
```

### 2. Declaration Collision & Merging Incompatibilities
Interface merging hanya bekerja jika signature tipe identik atau kompatibel:

```typescript
// Lib bawaan DOM:
interface Navigator {
    readonly hardwareConcurrency: number;
}

// Upaya augmentasi yang salah:
interface Navigator {
    hardwareConcurrency: string; // TS2717: Subsequent property declarations must have the same type.
}
```

### 3. Namespace vs Value Shadowing
Jika Anda mendeklarasikan `declare namespace Express`, pastikan Anda tidak menimpa implementasi runtime variabel dengan nama yang sama jika keduanya dimuat dalam konteks file yang tumpang tindih. Namespace ambient murni hanya ada di tingkat tipe compiler dan lenyap di runtime.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menaruh Logika Runtime di dalam File `.d.ts`
```typescript
// ❌ ANTI-PATTERN: Berkas index.d.ts
export function calculateTax(amount: number): number {
    return amount * 0.11; // TS1036: Statements are not allowed in ambient contexts.
}

// ✔️ CORRECT:
export function calculateTax(amount: number): number;
```
*Mengapa:* Compiler tidak memancarkan file `.js` dari `.d.ts`. Implementasi apapun di sini akan memicu syntax error dari compiler atau hilang saat runtime.

### 2. The Wildcard Fallback "Escape Hatch" yang Berlebihan
Ketika engineer malas menulis tipe untuk modul JavaScript, mereka sering melakukan ini:

```typescript
// ❌ ANTI-PATTERN: declarations.d.ts
declare module "*"; // Blanket wildcard!
```
*Bahaya:* Baris ini memberitahu TypeScript bahwa **semua** modul yang diimpor (termasuk modul yang typo seperti `import { foo } from "recat"`) adalah valid dan bertipe `any`. Ini mematikan type safety seluruh modul sistem Anda!
*Solusi:* Selalu declare module spesifik atau gunakan wildcard spesifik ekstensi:
```typescript
// ✔️ CORRECT:
declare module "untyped-package-a";
declare module "untyped-package-b";
```

### 3. Mengasumsikan Variable Pasti Tersedia di Runtime
```typescript
// ❌ ANTI-PATTERN
declare const userToken: string;
console.log(userToken.toLowerCase()); // Crash jika runtime environment tidak mendefinisikannya!

// ✔️ CORRECT:
declare const userToken: string | undefined;
if (typeof userToken === "string") {
    console.log(userToken.toLowerCase());
}
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Pemisahan Folder Deklarasi Internal vs Eksternal:**
    *   `src/types/ambient/`: Berisi berkas-berkas `.d.ts` murni script context (assets, global constants).
    *   `src/types/augmentations/`: Berisi berkas module augmentations.
2.  **Explicit Scope via `tsconfig.json` `types` Array:**
    Hindari membiarkan `tsc` memindai seluruh direktori `node_modules/@types` jika proyek memiliki dependensi raksasa. Tentukan paket tipe yang diizinkan secara eksplisit:
    ```json
    "compilerOptions": {
      "types": ["node", "jest"]
    }
    ```
3.  **Ship Typings Bersama Library (`package.json`):**
    Jika Anda membangun library yang akan dipublikasikan ke npm, jangan mengandalkan deklarasi global. Gunakan opsi `declaration: true` pada `tsconfig.json` dan referensikan hasilnya di `package.json`:
    ```json
    {
      "name": "my-enterprise-lib",
      "main": "dist/index.js",
      "types": "dist/index.d.ts"
    }
    ```
4.  **Immutability by Default:**
    Gunakan `readonly` pada tipe data ambient yang mewakili konfigurasi global atau variabel lingkungan agar tidak dapat dimutasi secara sengaja oleh tim pengembang:
    ```typescript
    declare const ENV_CONFIG: Readonly<{
        API_ENDPOINT: string;
        TIMEOUT_MS: number;
    }>;
    ```

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Impact Terhadap Compilation Performance
Compiler TypeScript harus membaca, mem-parsing, dan memvalidasi AST dari seluruh file deklarasi yang dimuat. Menghubungkan terlalu banyak `.d.ts` dapat menurunkan performa kompilasi secara signifikan.

1.  **`skipLibCheck: true`:**
    Opsi compiler ini menginstruksikan `tsc` untuk **tidak memvalidasi konsistensi internal dari file `.d.ts`** (baik di `node_modules` maupun lokal). Compiler hanya mengecek interaksi tipe kode aplikasi Anda terhadap library, menghemat waktu build antara 30% hingga 60%.
2.  **Eliminasi Parsing Berulang Melalui `declarationMap: true`:**
    Jika mengembangkan arsitektur Monorepo (Project References), selalu nyalakan:
    ```json
    "compilerOptions": {
      "declaration": true,
      "declarationMap": true
    }
    ```
    Ini menghasilkan pemetaan `.d.ts.map` yang memungkinkan IDE (VS Code) langsung melompat (*go-to-definition*) ke berkas `.ts` sumber aktual alih-alih membuka file `.d.ts`, mencegah overhead kompilasi ulang pada memory language server IDE.

---

# SEKSI 16 — KEAMANAN & HARDENING

Ambient context merupakan salah satu celah paling rentan terhadap **Compile-Time False Positives** yang berujung pada eksploitasi runtime atau downtime.

### The Illusion of Type Safety
TypeScript **tidak pernah melakukan enkripsi, sanitasi, atau sanitasi runtime**. Jika Anda mendeklarasikan:

```typescript
declare global {
    interface Window {
        currentUserRole: "ADMIN" | "USER";
    }
}
```

Penyerang dapat dengan mudah membuka console browser dan mengeksekusi:
```javascript
window.currentUserRole = "SUPER_ROOT_INJECTED";
```

TypeScript code yang bergantung pada:
```typescript
if (window.currentUserRole === "ADMIN") {
    renderAdminDeleteButton();
}
```
Akan beroperasi di atas pondasi runtime yang tidak aman.

### Hardening Rule: Zod/Defensive Gateway Pattern
Untuk data yang masuk via ambient context global, selalu pasangkan ambient type dengan runtime schema validator:

```typescript
import { z } from "zod";

const UserRoleSchema = z.enum(["ADMIN", "USER"]);

export function getValidatedUserRole(): "ADMIN" | "USER" {
    const rawRole = typeof window !== "undefined" ? window.currentUserRole : undefined;
    const parseResult = UserRoleSchema.safeParse(rawRole);
    
    if (!parseResult.success) {
        // Fallback defensif jika tipe di-tamper atau tidak sinkron
        return "USER";
    }
    return parseResult.data;
}
```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Bagaimana mendeteksi dari mana TypeScript mengambil deklarasi ambient saat terjadi konflik resolusi tipe?

### Debugging Resolusi Tipe Compiler
Gunakan flag CLI bawaan compiler untuk menelusuri bagaimana berkas ambient ditemukan:

```bash
# Melacak seluruh proses resolusi modul
npx tsc --traceResolution > resolution-trace.log

# Melacak file apa saja yang diikutsertakan dalam kompilasi
npx tsc --listFiles
```

Di dalam `resolution-trace.log`, cari baris yang memuat kata kunci deklarasi:
```text
======== Resolving module 'legacy-parser' from '/app/src/index.ts'. ========
Explicitly specified module resolution kind: 'NodeNext'.
Searching according to layout:
  ...
  File '/app/types/legacy-parser.d.ts' exist - MATCHED.
======== Module name 'legacy-parser' was successfully resolved to '/app/types/legacy-parser.d.ts'. ========
```

### IDE Type Inspection
Jika tipe Anda tertimpa (*overwritten*), lakukan inspeksi di VS Code:
1. Hover identifier yang ambigu.
2. Tahan tombol `Ctrl` (atau `Cmd`) dan klik identifier tersebut.
3. Jika muncul popup dengan beberapa target file, artinya ada **Declaration Collision**. Anda harus mengaudit file `.d.ts` mana yang memicu duplikasi symbol.

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

| Syntax / Direktif | Target Lingkup | Fungsi Utama | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| `declare const / let / var` | Global / Local Ambient | Mendaftarkan identifier runtime ke compile-time check. | CDN script global, env build flags. |
| `declare function` | Global / Local Ambient | Mendaftarkan signature callable tanpa implementation body. | Polyfill global, C-style native bindings. |
| `declare class` | Global / Local Ambient | Mendefinisikan constructor dan public methods class. | Library JS OOP tanpa type definitions. |
| `declare module "pkg"` | Module Ambient | Membungkus package yang tidak memiliki types. | Pustaka npm legacy vanilla JS. |
| `declare module "*.ext"` | Wildcard Ambient | Mengizinkan non-JS imports di compile-time. | CSS Modules, images, binary assets. |
| `declare global { ... }` | Global Namespace | Memodifikasi objek global dari dalam sebuah Module. | Augmentasi `Window`, `ProcessEnv`, `NodeJS`. |
| `/// <reference types="" />`| Compiler Instruction | Mengimpor dependensi type definition package. | Skrip build tooling, environment shims. |

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Uji penguasaan arsitektural Anda terhadap materi Ambient Context.

### Bagian A: Basic Knowledge
1.  **Apa yang terjadi pada kode JavaScript yang dihasilkan (`.js`) saat Anda menulis `declare const x: number = 42;`?**
    *   A. Variabel `x` di-compile menjadi `var x = 42;`
    *   B. Compiler menghasilkan error sintaks karena inisialisasi nilai dilarang pada ambient context.
    *   C. Compiler mengonversi nilainya menjadi konstanta inline.
    *   D. Variabel dimasukkan ke dalam file `.d.ts` dan dieksekusi di runtime.

2.  **Kapan sebuah berkas `.d.ts` dianggap sebagai "Module Context"?**
    *   A. Saat berkas tersebut disimpan di dalam folder `node_modules`.
    *   B. Saat berkas tersebut memiliki ekstensi ganda `.module.d.ts`.
    *   C. Saat berkas tersebut memiliki setidaknya satu statement `import` atau `export` pada level teratas.
    *   D. Seluruh berkas `.d.ts` selalu berstatus Module Context secara default.

3.  **Apa fungsi dari compiler option `"skipLibCheck": true`?**
    *   A. Menghapus folder `node_modules` dari pemeriksaan runtime.
    *   B. Mengabaikan pengecekan tipe pada seluruh berkas `.ts` internal tim pengembang.
    *   C. Melewatkan type-checking terhadap berkas deklarasi (`.d.ts`) untuk mempercepat kompilasi.
    *   D. Mencegah kompilasi library eksternal.

4.  **Manakah sintaks yang valid untuk merepresentasikan aset file biner gambar PNG agar dapat diimpor via `import img from './logo.png'`?**
    *   A. `declare file "*.png";`
    *   B. `declare module "*.png" { const src: string; export default src; }`
    *   C. `import "*.png": string;`
    *   D. `export namespace "*.png" { const content: Buffer; }`

5.  **Jika Anda mengimplementasikan module augmentation dengan `declare module "my-lib"`, di manakah implementasi aktual kodenya berada saat runtime?**
    *   A. Di dalam block `declare module`.
    *   B. Di dalam cache TypeScript Compiler.
    *   C. Di dalam file JavaScript yang disediakan oleh package `my-lib` di `node_modules` (atau patch lokal Anda).
    *   D. Dibuat secara otomatis oleh Type Emitter.

---

### Bagian B: Intermediate / Scenario-Based
6.  **Sebuah file `src/types/env.d.ts` dibuat untuk menambahkan variabel env, namun tiba-tiba interface `Window` di seluruh aplikasi menjadi tidak dikenali (TS2304: Cannot find name 'Window'). Apa penyebab yang paling mungkin?**
    *   A. File `env.d.ts` terlalu besar.
    *   B. Seseorang menambahkan statement `export {}` di file deklarasi tersebut, merubah status script menjadi module, dan membungkus ulang types tanpa menyertakan lib DOM.
    *   C. Seseorang mendefinisikan `interface Window` kosong di dalam `env.d.ts` pada script scope, menimpa secara total interface global `Window` bawaan compiler melalui shadowing/overriding.
    *   D. Opsi `strict: true` dimatikan secara tidak sengaja.

7.  **Diberikan kode berikut pada berkas `types/patch.d.ts`:**
    ```typescript
    import { AxiosRequestConfig } from "axios";
    interface AxiosRequestConfig {
        metadata?: { startTime: number };
    }
    ```
    **Mengapa interface merging di atas GAGAL menambahkan properti `metadata` ke library Axios?**
    *   A. Properti `metadata` harus bertipe mandatory (tidak boleh opsional `?`).
    *   B. Karena berkas tersebut memiliki `import`, ia menjadi Module Context. Interface `AxiosRequestConfig` yang ditulis hanya menjadi interface lokal berkas tersebut, bukan melakukan augmentasi pada modul `axios`.
    *   C. Axios tidak ditulis menggunakan bahasa TypeScript.
    *   D. Interface merging dilarang pada paket HTTP client.

8.  **Bagaimana cara memperbaiki kegagalan pada Soal No. 7?**
    *   A. Hapus `import { AxiosRequestConfig } from "axios";` dan biarkan error.
    *   B. Bungkus interface merging di dalam `declare module "axios" { interface AxiosRequestConfig { metadata?: { startTime: number }; } }`.
    *   C. Ganti nama file menjadi `axios.ts`.
    *   D. Gunakan `/// <reference path="axios" />`.

9.  **Apa perbedaan mendasar antara `declare namespace Foo` dan `namespace Foo` tanpa kata kunci declare?**
    *   A. Tidak ada perbedaan, keduanya identik.
    *   B. `declare namespace Foo` tidak menghasilkan objek runtime JavaScript (hanya surface compile-time), sedangkan `namespace Foo` menghasilkan IIFE (Immediately Invoked Function Expression) JavaScript aktual pada runtime.
    *   C. `declare namespace` hanya dapat digunakan di dalam Node.js runtime.
    *   D. `namespace` tanpa declare deprecated dan tidak dapat dikompilasi oleh TypeScript modern.

10. **Anda mengonfigurasi `typeRoots: ["./custom-types"]` di `tsconfig.json`. Apa efek samping langsung konfigurasi ini terhadap library pihak ketiga yang diinstal di bawah `node_modules/@types`?**
    *   A. Tidak ada efek, `tsc` tetap memindai keduanya.
    *   B. `tsc` secara default **berhenti** memindai `./node_modules/@types` otomatis kecuali Anda secara eksplisit mencantumkannya kembali di dalam array `typeRoots` (`["./node_modules/@types", "./custom-types"]`).
    *   C. Folder `custom-types` akan disalin secara fisik ke dalam folder `node_modules`.
    *   D. Seluruh kode JavaScript akan diabaikan oleh linter.

---

### Kunci Jawaban & Pembahasan

1.  **B — Compiler menghasilkan error sintaks.** Keyword `declare` dilarang menyertakan inisialisasi implementasi/nilai.
2.  **C — Memiliki statement import/export level teratas.** Ciri pembeda formal antara Script Context dan Module Context di TypeScript.
3.  **C — Melewatkan type-checking terhadap berkas deklarasi (`.d.ts`).** Menghindari overhead parsing ulang library dependencies.
4.  **B — `declare module "*.png" { const src: string; export default src; }`**. Pola standar shimming non-code assets.
5.  **C — Di dalam file JavaScript yang disediakan oleh package `my-lib`**. Ambient context tidak menyediakan runtime logic.
6.  **C — Mendefinisikan interface kosong yang menimpa symbol global.** Interface merging di script context dengan nama sama tanpa member bawaan akan menutupi / merusak types jika terjadi konflik structural resolution.
7.  **B — File menjadi Module Context sehingga interface berstatus lokal.** Interface merging lintas module wajib menggunakan `declare module "pkg"`.
8.  **B — Dibungkus dalam `declare module "axios"`**. Sintaks baku Module Augmentation.
9.  **B — `declare namespace` adalah pure compile-time types, sedangkan `namespace` biasa menghasilkan IIFE JavaScript**.
10. **B — `tsc` berhenti membaca `node_modules/@types` otomatis.** Menimpa `typeRoots` menonaktifkan behavior pencarian default.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Misi Praktikum: Micro-Frontend Shared Host SDK Type Definition Suite

Sebagai Senior Platform Architect, Anda diminta merancang sistem definisi tipe untuk aplikasi Micro-Frontend Host shell yang memuat modul child secara dinamis via Module Federation.

#### Kebutuhan Spesifikasi:
1.  **Arsitektur Folder:**
    *   Buat struktur direktori terisolasi: `mfe-types-lab/`
    *   Inisialisasi TypeScript dengan konfigurasi `NodeNext`.
2.  **Global Ambient SDK:**
    *   Di browser window, aplikasi Shell menyuntikkan global instance: `window.HostAppBridge`.
    *   Bridge ini memiliki metode:
        *   `navigate(route: string, state?: Record<string, unknown>): void`
        *   `subscribe(event: string, callback: (data: any) => void): () => void` (mengembalikan function unsubscribe)
        *   `readonly currentTenant: { id: string; tier: 'FREE' | 'ENTERPRISE' }`
3.  **Module Augmentation Penambalan Vendor:**
    *   Simulasikan instalasi library logging: buat modul tiruan `"mfe-shared-logger"`.
    *   Tambahkan method `logSecurityAudit(level: 'LOW' | 'CRITICAL', message: string): void` ke interface modul tersebut menggunakan Module Augmentation.
4.  **Aset Loader Shim:**
    *   Tambahkan deklarasi wildcard agar import file dengan format `*.wasm` menghasilkan promise compiler:
        ```typescript
        declare module "*.wasm" {
            const initWasm: () => Promise<WebAssembly.Instance>;
            export default initWasm;
        }
        ```
5.  **Verifikasi Kompilasi Ketat:**
    *   Buat berkas konsumen `src/consumer.ts` yang menggunakan seluruh entitas tipe di atas.
    *   Jalankan pemeriksaan tipe compiler secara murni tanpa runtime emit:
        ```bash
        tsc --noEmit
        ```
    *   Pastikan tidak ada compiler error (Exit status: `0`).

Jika pipeline `tsc --noEmit` Anda berhasil melewati kompilasi di atas tanpa error, Anda telah menguasai rekayasa **Ambient Context & Declaration Files** pada standar enterprise tertinggi!