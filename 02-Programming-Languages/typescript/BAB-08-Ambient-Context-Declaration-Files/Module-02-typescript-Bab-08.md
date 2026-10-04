# BAB 08: Ambient Context & Declaration Files (`.d.ts`)
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level arsitek/senior engineer diharapkan mampu:

1. **Menganalisis dan Membedah Mekanisme Compiler**: Memahami cara kerja TypeScript Compiler (`tsc`) saat memisahkan *Type Space* dan *Value Space*, serta bagaimana pipeline AST memproses *Ambient Context* (`declare`) tanpa menghasilkan runtime artifacts.
2. **Merancang Pola Augmentasi Mutakhir**: Mengimplementasikan *Module Augmentation*, *Declaration Merging*, dan *Global Scope Expansion* pada pustaka pihak ketiga dan enterprise micro-frameworks secara deterministik.
3. **Menguasai Arsitektur Declaration Emit Enterprise**: Mengonfigurasi dan memvalidasi pipeline emit deklarasi menggunakan flag `--declaration`, `--emitDeclarationOnly`, `--declarationMap`, dan paradigma modern `--isolatedDeclarations` (TypeScript 5.5+) untuk skalabilitas build super cepat pada monorepo.
4. **Menerapkan Distribusi Tipe Modern (ESM & CJS Dual-Package)**: Mendesain konfigurasi manifest `package.json` yang mematuhi standar *Conditional Exports* modern tanpa menimbulkan masalah *Dual Package Hazard* pada resolusi tipe (`NodeNext`/`Bundler`).
5. **Mitigasi Polusi Global & Konflik Simbol**: Mencegah dan mengisolasi degradasi performa kompilasi serta konflik tipe global akibat penggunaan *ambient declaration* yang tidak terkontrol pada skala repositori besar.

---

### 2. Prerequisite

Sebelum mendalami modul ini, Anda wajib memiliki pemahaman mendalam tentang:
* **TypeScript Structural Typing & Subtyping**: Variance (covariance, contravariance, bivariance, dan invariance).
* **Module Systems & Resolution Algorithms**: Perbedaan spesifikasi ESM (`import`/`export`), CommonJS (`require`/`module.exports`), serta algoritma `node10` vs `node16`/`nodenext` vs `bundler`.
* **TypeScript Abstract Syntax Tree (AST)**: Konsep *Identifiers*, *SourceFile nodes*, *Ambient context boundary*, dan parsing simbol compiler.
* **Modern Build Tools & Package Managers**: Tooling seperti `npm`, `pnpm workspaces`, Rollup/ESBuild/tsup, dan orkestrasi monorepo (Turborepo/Nx).

---

### 3. Concept & Internal Architecture

#### Type Space vs Value Space & Ambient Boundary

Compiler TypeScript beroperasi dengan mempertahankan dua tabel simbol utama saat fase *binding*:

```
          Source Code Input (.ts / .d.ts)
                         │
                         ▼
              [Lexer & Parser (AST)]
                         │
                         ▼
            [Binder: Symbol Assignment]
           ┌─────────────┴─────────────┐
           ▼                           ▼
      [Value Space]               [Type Space]
   (Variables, Functions,      (Interfaces, Types,
    Classes, Enums)             Classes, Enums, Signatures)
           │                           │
           │ (declare / ambient)       │
           ├───────────────────────────┤
           ▼                           ▼
[Checker: Eliminasi Emisi]    [Checker: Type Verification]
           │                           │
           ▼                           ▼
    Emit JavaScript            Emit .d.ts / No Emit
    (Runtime Artifact)         (Type Artifact)
```

1. **Ambient Declarations (`declare`)**:
   Kata kunci `declare` memberitahu *Binder* untuk mendaftarkan suatu *Symbol* langsung ke dalam tabel tipe atau referensi nilai eksternal tanpa mengalokasikan memori runtime atau instruksi kode pada AST transformasi emisi JavaScript. 
2. **Declaration Space Boundary**:
   File `.d.ts` secara fundamental dieksekusi di bawah mode *pure declaration*. Tidak ada implementasi logika kode JavaScript yang diizinkan selain deklarasi antarmuka, signature, atau pemetaan ambient.
3. **Declaration Merging Mechanics**:
   Ketika dua identifier dengan nama yang sama berada dalam satu scope deklaratif:
   * **Interface + Interface**: Simbol digabungkan ke dalam satu node antarmuka tunggal dengan daftar overload method yang diposisikan secara terurut (deklarasi terakhir diprioritaskan terlebih dahulu, kecuali signature non-overloaded).
   * **Namespace + Class / Function / Enum**: Menghasilkan objek bernilai runtime (class/function) yang propertinya ditambahkan oleh simbol namespace yang bersangkutan pada fase semantic resolution.

#### Pipeline Kompiler: `isolatedDeclarations` (TypeScript 5.5+)

Secara tradisional, `tsc` memerlukan inferensi tipe global melintasi file untuk menghasilkan file `.d.ts`. Jika File A mengimpor File B, compiler harus memeriksa File B secara menyeluruh hanya untuk mengetahui return type fungsi pada File A.

```
Tradisional (Global Program Graph Requirement):
[File A] ──(inference dependency)──► [File B] ──► [Full Typecheck] ──► Emit A.d.ts

Arsitektur Modern (--isolatedDeclarations):
[File A] ──► [Local AST Inspection Only] ──► Fast Emit A.d.ts (O(1) complexity per file)
```

Dengan mengaktifkan `--isolatedDeclarations`, TypeScript memaksa programmer mengekspitkan semua signature boundary yang diekspor. Hal ini memungkinkan tools ultra-cepat seperti *OXC* atau *SWC* untuk meng-emit file `.d.ts` secara paralel per file tanpa perlu menginisialisasi engine tipe penuh.

---

### 4. Why & What

#### Why: Mengapa Ambient Context Krusial pada Skala Enterprise?
* **Zero Runtime Overhead**: Menyediakan kontrak antarmuka yang sangat ketat tanpa menambah 1 byte pun pada bundle production runtime client.
* **Integrasi Legacy & Global Polyfill**: Menghubungkan ekosistem JavaScript lama (misal: jQuery, global script tags, platform wrappers seperti Electron/React Native native bridge) ke lingkungan TypeScript yang type-safe.
* **Extensibility Framework**: Memungkinkan dependensi internal atau framework (seperti Express, Fastify, Next.js) diekstensi kontraknya tanpa harus melakukan fork pada repository sumber (*open-closed principle*).

#### What: Konstruksi Inti `.d.ts` Lanjutan
1. **Module Augmentation (`declare module 'pkg'`)**: Menembus batas modul eksternal yang sudah ada untuk memperkaya tipe antarmuka tanpa merusak kode sumber vendor.
2. **Global Augmentation (`declare global`)**: Membuka jalur dari dalam modul ESM (file yang memiliki `import`/`export`) untuk menyuntikkan tipe ke ruang lingkup *Ambient Global*.
3. **Subpath Typing**: Menyediakan resolusi tipe terisolasi untuk entry point parsial (misal: `@company/sdk/plugins/tracing`).

---

### 5. How: Workflow Detail Penulisan & Resolusi Modul Tipe

Langkah terstruktur membangun pustaka modular yang aman dan meng-emit file tipe:

```
[Write TS Source Code]
        │
        ├─► Gunakan Type Annotations Lengkap (isolatedDeclarations friendly)
        │
[Compiler Run (`tsc`)]
        │
        ├──► Menghasilkan JS Bundle (ESM/CJS)
        ├──► Menghasilkan .d.ts (Tipe API publik)
        └──► Menghasilkan .d.ts.map (Source Mapping tipe untuk IDE navigation)
        │
[package.json Packaging]
        │
        └──► Konfigurasi `exports` field dengan kondisi `types` prioritas utama
```

#### Kondisi Resolusi `exports` di `package.json`

Urutan penulisan *conditional exports* bersifat absolut. Kunci `"types"` **wajib berada paling atas** sebelum spesifikasi target runtime.

```json
{
  "name": "@enterprise/telemetry",
  "version": "2.4.0",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.mjs",
      "require": "./dist/index.cjs"
    },
    "./subpath": {
      "types": "./dist/subpath.d.ts",
      "import": "./dist/subpath.mjs",
      "require": "./dist/subpath.cjs"
    }
  }
}
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Paspor dan Formulir Imigrasi
Bayangkan aplikasi Anda adalah sebuah negara. 
* **Runtime JavaScript** adalah *orang-orang fisik* yang berjalan melintasi perbatasan (melakukan pekerjaan nyata, mengonsumsi sumber daya).
* **Ambient Declarations (`.d.ts`)** adalah *formulir manifes imigrasi kosong* yang dibawa oleh petugas bea cukai. Manifes ini tidak memiliki raga fisik (zero bundle footprint), tetapi memuat deskripsi eksak tentang ciri-ciri orang yang diizinkan lewat. 
* Jika dokumen manifes menyatakan seorang tamu memiliki lisensi diplomatik (*Declaration Merging*), orang tersebut otomatis diakui memiliki hak tersebut di seluruh wilayah hukum runtime tanpa perlu mengganti identitas aslinya.

#### Diagram: Mekanisme Declaration Merging pada Simbol Terpadu

```
+-----------------------------------------------------------------------+
| Symbol Name: "DatabaseClient"                                         |
+=======================================================================+
|  Value Space (Namespace / Class)    |  Type Space (Interface Merging) |
+-------------------------------------+---------------------------------+
|  [Class: DatabaseClient]            |  [Interface: DatabaseClient]    |
|   - constructor(cfg: Config)        |   - connect(): Promise<void>    |
|   - query(sql: string): Result      |   - disconnect(): Promise<void> |
|                                     |                                 |
|  [Namespace: DatabaseClient]        |  [Interface Augmentation]       |
|   - static VERSION: string          |   - telemetryHook(): void       |
|   - static createPool(): Pool       |   - transactionId: string       |
+-------------------------------------+---------------------------------+
                                      │
                                      ▼
             Hasil Gabungan Kompiler (Single Unified Symbol):
  const client: DatabaseClient; // Memiliki method connect, telemetryHook, dsb.
  DatabaseClient.VERSION;       // Namespace binding langsung ke constructor object
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Typed Ambient Environment Variables & Window Mutation

Menghubungkan variabel environment global dan runtime browser tanpa impor eksplisit:

```typescript
// File: src/types/ambient-env.d.ts

// Memastikan file ini diproses sebagai ambient context murni (tanpa import/export top-level)
declare namespace NodeJS {
  interface ProcessEnv {
    readonly NODE_ENV: 'development' | 'production' | 'test';
    readonly ENTERPRISE_API_GATEWAY_URL: string;
    readonly MAX_CONCURRENT_WORKERS?: string;
  }
}

// Menambahkan interface ke Window scope
interface Window {
  __RUNTIME_FEATURE_FLAGS__: Record<string, boolean>;
  startEnterpriseTracing(serviceName: string): void;
}
```

Implementasi pemanggilan di file aplikasi (`src/index.ts`):
```typescript
// src/index.ts
function initializeApp(): void {
  // Type-safe process.env
  const gatewayUrl = process.env.ENTERPRISE_API_GATEWAY_URL;
  console.log(`Connecting to: ${gatewayUrl.toLowerCase()}`);

  // Type-safe window property
  if (typeof window !== 'undefined') {
    if (window.__RUNTIME_FEATURE_FLAGS__['enableTelemetry']) {
      window.startEnterpriseTracing('core-auth-service');
    }
  }
}
```

---

#### B. Practical Example: Enterprise Plugin Context Augmentation (Micro-Core Engine)

Skenario: Anda sedang membangun sistem plugin core HTTP framework perusahaan. Library eksternal menyediakan tipe dasar, dan plugin Anda memodifikasi tipe request secara aman.

```typescript
// File: node_modules/@enterprise/core-http/index.d.ts (Vendor Simulation)
export interface BaseContext {
  traceId: string;
  timestamp: number;
}

export interface HttpRequest {
  path: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  context: BaseContext;
}

export type MiddlewarePlugin = (req: HttpRequest) => void;
```

Berikut file augmentasi modul yang ditulis pada service internal untuk menyuntikkan user session:

```typescript
// File: src/plugins/auth-plugin.ts
import { HttpRequest } from '@enterprise/core-http';

export interface EnterpriseUserSession {
  userId: string;
  roles: readonly string[];
  tenantId: string;
}

// MODULE AUGMENTATION: Memperluas package eksternal
declare module '@enterprise/core-http' {
  // Memperluas interface BaseContext secara aman via declaration merging
  interface BaseContext {
    user?: EnterpriseUserSession;
    isAuthenticated: boolean;
  }
}

// Implementasi middleware yang memanfaatkan augmented types
export const enterpriseAuthMiddleware = (req: HttpRequest): void => {
  // Compiler mengenal properti `user` dan `isAuthenticated`
  req.context.isAuthenticated = true;
  req.context.user = {
    userId: 'usr_sec_9941',
    roles: ['PlatformArchitect', 'SecurityAdmin'],
    tenantId: 'tenant_id_apac_01'
  };
};

export const authorizationGuard = (req: HttpRequest, requiredRole: string): boolean => {
  if (!req.context.isAuthenticated || !req.context.user) {
    return false;
  }
  return req.context.user.roles.includes(requiredRole);
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Skenario: Arsitektur Platform Observabilitas Monorepo
Sebuah perusahaan finansial tier-1 memiliki arsitektur monorepo dengan 150+ microservices dan frontend web application. Terdapat library internal bernama `@company/telemetry-sdk`.

#### Masalah Utama
1. **Namespace Collision & Pollution**: Berbagai tim mengimpor `@company/telemetry-sdk/globals.d.ts` yang menimpa tipe `console.log` bawaan untuk menyuntikkan log structured trace. Hal ini merusak library pihak ketiga yang memerlukan signature `console.log` standard.
2. **Build Bottleneck**: Waktu kompilasi CI/CD melonjak hingga 45 menit karena compiler harus memetakan dependensi tipe melintasi paket internal untuk meng-emit deklarasi `.d.ts`.
3. **Broken Exports**: Beberapa package di-consume oleh service berbasis Node (CJS) dan service modern (ESM), menyebabkan error fatal `TS2709: Cannot use namespace as a type` akibat dual-package types misconfiguration.

#### Arsitektur Solusi
Arsitek merancang ulang arsitektur deklarasi pustaka tipe melalui 3 layer pemisahan:

```
                  @company/telemetry-sdk
                            │
        ┌───────────────────┴───────────────────┐
        ▼                                       ▼
  src/core/ (Isolated)                   src/ambient/ (Explicit Opt-In)
  - Tanpa declare global                 - declare global { ... }
  - Strict input/output types            - Isolasi dalam file standalone
  - Mendukung --isolatedDeclarations     - Hanya diimpor via setup bootstrap
        │                                       │
        └───────────────────┬───────────────────┘
                            ▼
           tsup / rollup-plugin-dts Emit
                            │
        ┌───────────────────┴───────────────────┐
        ▼                                       ▼
  dist/index.d.mts (ESM)                  dist/index.d.cts (CJS)
```

1. **Penerapan `--isolatedDeclarations`**:
   Semua fungsi publik yang diekspor wajib memiliki signature tipe eksplisit:
   ```typescript
   // SALAH: Bergantung pada inferensi compiler mendalam
   export function createSpan(name: string) {
     return new SpanWrapper(name, Date.now());
   }

   // BENAR: Mematuhi isolatedDeclarations
   export function createSpan(name: string): ISpanInstance {
     return new SpanWrapper(name, Date.now());
   }
   ```
2. **Pemisahan Tipe Ambient Global ke Subpath Terpisah**:
   Global types tidak boleh aktif otomatis saat runtime di-import. Tim yang membutuhkan hooking globals harus mengimpor secara sadar:
   ```typescript
   // apps/payment-service/src/main.ts
   import '@company/telemetry-sdk/ambient-hook'; // Explicit Opt-In
   import { createSpan } from '@company/telemetry-sdk';
   ```

3. **Manifest Resolusi Dual-Package Tipe Anti-Hazard**:
   ```json
   {
     "name": "@company/telemetry-sdk",
     "exports": {
       ".": {
         "types": {
           "import": "./dist/esm/index.d.mts",
           "require": "./dist/cjs/index.d.cts"
         },
         "import": "./dist/esm/index.mjs",
         "require": "./dist/cjs/index.cjs"
       },
       "./ambient-hook": {
         "types": "./dist/ambient-hook.d.ts"
       }
     }
   }
   ```

#### Hasil
* Waktu build pipeline CI monorepo berkurang 68% (dari 45 menit menjadi ~14 menit) melalui transpilasi tipe paralel via SWC/tsc decoupled.
* 100% resolusi ambient types terisolasi, menghilangkan false-positive compiler errors pada seluruh aplikasi downstream.

---

### 9. Trade-offs

| Aspek | Pendekatan Ambient Global (`declare global`) | Pendekatan Explicit Module Typing (`export type`) |
| :--- | :--- | :--- |
| **Ergonomi Penggunaan** | **Sangat Tinggi**: Tersedia langsung di seluruh file tanpa `import` statis. | **Moderat**: Setiap file harus menyertakan baris impor yang spesifik. |
| **Maintainability** | **Rendah**: Sulit melacak dari mana asal modifikasi tipe; rentan conflict. | **Sangat Tinggi**: Alur ketergantungan tipe bersifat eksplisit dan deterministik. |
| **Kecepatan Build** | **Lambat**: Compiler harus mengevaluasi global scope pada seluruh AST tree. | **Cepat**: Compiler membatasi evaluasi tipe hanya pada graf impor yang dituju. |
| **Isolation / Purity** | **Buruk**: Berisiko membocorkan tipe aplikasi ke dependensi pihak ketiga. | **Sempurna**: Tipe terisolasi dalam batas boundaries modul masing-masing. |

| Parameter | `--skipLibCheck: false` | `--skipLibCheck: true` |
| :--- | :--- | :--- |
| **Integritas Tipe** | Mutlak terverifikasi di seluruh `node_modules`. | Hanya memverifikasi source code lokal proyek Anda. |
| **Build Latency** | Eksponensial seiring bertambahnya jumlah dependency pihak ketiga. | Linear terhadap ukuran basis kode internal Anda sendiri. |
| **Rekomendasi Enterprise**| Gunakan hanya pada unit pengujian internal pustaka (SDK level). | **Wajib diaktifkan** pada level konsumsi aplikasi mikro/monorepo besar. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Menulis `import` Top-Level dalam Ambient Script File
* **Kasus**: Programmer bermaksud membuat tipe global, namun menambahkan `import { SomeType } from './somewhere'` di baris pertama file `.d.ts`.
* **Dampak**: File secara otomatis dikonversi oleh compiler dari *Ambient Script* menjadi *Module*. Semua `declare var/interface` di dalamnya tidak lagi dapat diakses secara global!
* **Solusi**: Gunakan Inline Dynamic Type Import atau bungkus dalam blok `declare global`.

```typescript
// SALAH: Menyebabkan seluruh file menjadi module lokal!
import { DatabaseEngine } from './engine';
declare const globalDbInstance: DatabaseEngine; 

// BENAR: Menggunakan inline dynamic import
declare const globalDbInstance: import('./engine').DatabaseEngine;

// ATAU BENAR: Menegaskan module context dan global block
import { DatabaseEngine } from './engine';
declare global {
  const globalDbInstance: DatabaseEngine;
}
export {}; // Pastikan file tetap bertindak sebagai module
```

#### Kesalahan 2: Menggunakan `declare module` dengan Path yang Salah
* **Kasus**: Mencoba mengaugmentasi file internal dengan relative path yang keliru atau mengaugmentasi module non-existent.
* **Solusi**: Pastikan identifier module pada `declare module '...'` cocok persis dengan spesifikasi nama package yang di-resolve oleh Node/Bundler.

#### Kesalahan 3: Tidak Menyertakan `--declarationMap` pada Pustaka Internal Monorepo
* **Dampak**: Fitur *Go to Definition* IDE mengarahkan engineer ke file `.d.ts` yang di-emit (compiled type), bukan ke file source code `.ts` aslinya.
* **Solusi**: Selalu aktifkan `"declarationMap": true` pada `tsconfig.json` di library monorepo lokal.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Isolated Declarations**: Aktifkan `"isolatedDeclarations": true` di `tsconfig.json` pustaka untuk pipeline build monorepo cepat.
2. [ ] **No Naked Global Declarations**: Jangan pernah mendistribusikan pustaka NPM dengan `.d.ts` yang memuat modifikasi global tanpa membungkusnya dalam subpath opt-in.
3. [ ] **Types Condition First**: Tempatkan blok `"types"` selalu sebagai baris pertama dalam setiap blok *conditional exports* `package.json`.
4. [ ] **Explicit Module Boundaries**: Selalu akhiri file pengetikan ambient yang memiliki `import` eksternal dengan `export {}` untuk menghindari kebocoran scope.
5. [ ] **Enable Declaration Map**: Setel `"declaration": true` dan `"declarationMap": true` bersamaan untuk navigasi kode optimal di IDE.
6. [ ] **Strict Extension Syntax**: Saat melakukan *declaration merging*, pastikan generic types dan default parameter memiliki signature yang identik.
7. [ ] **Pure Declaration Headers**: Hindari menulis deklarasi fungsi dengan implementasi body di file `.d.ts` (mengakibatkan runtime/compiler error `TS1183`).
8. [ ] **Targeted Subpaths**: Jika paket Anda mendukung Node dan Browser, pisahkan file deklarasi ambient environment masing-masing (misal: `pkg/node` vs `pkg/browser`).
9. [ ] **Skip Lib Check in Apps**: Nyalakan `"skipLibCheck": true` pada aplikasi konsumsi tingkat akhir untuk mencegah dependensi lama saling bertabrakan tipe.
10. [ ] **Validate Package Bundling**: Gunakan tools analisis tipe seperti `@arethetypeswrong/cli` (attw) di pipeline CI untuk mendeteksi mismatch pengetikan ESM/CJS.

---

### 12. Hands-on Practice

Buat dan eksekusi struktur direktori berikut untuk memahami implementasi ambient, augmentasi, dan ekspor tipe terisolasi. Simpan pekerjaan pada direktori `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── package.json
├── tsconfig.json
└── src/
    ├── ambient/
    │   └── platform-globals.d.ts
    ├── core/
    │   └── registry.ts
    ├── plugins/
    │   └── metrics-plugin.ts
    └── index.ts
```

#### Langkah 1: Inisialisasi `package.json`
```json
{
  "name": "@hands-on/ambient-architecture",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "tsc --build"
  },
  "devDependencies": {
    "typescript": "^5.5.0"
  }
}
```

#### Langkah 2: Konfigurasi `tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "declaration": true,
    "declarationMap": true,
    "isolatedDeclarations": true,
    "strict": true,
    "skipLibCheck": true,
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src/**/*"]
}
```

#### Langkah 3: Membuat Ambient Global Declarations (`src/ambient/platform-globals.d.ts`)
```typescript
// Mendeklarasikan runtime global khusus platform tanpa import/export
declare const __BUILD_TIMESTAMP__: number;
declare const __CLUSTER_ID__: string;

declare namespace ExecutionContext {
  interface TraceMetadata {
    correlationId: string;
    originZone: string;
  }
}
```

#### Langkah 4: Membuat Core Registry Module (`src/core/registry.ts`)
```typescript
export interface ServiceMetadata {
  name: string;
  version: string;
}

// Interface yang terbuka untuk augmentasi (Declaration Merging)
export interface CentralRegistryRecord {
  serviceId: string;
  metadata: ServiceMetadata;
}

export class ServiceRegistry {
  private readonly records = new Map<string, CentralRegistryRecord>();

  public register(id: string, record: CentralRegistryRecord): void {
    this.records.set(id, record);
  }

  public getRecord(id: string): CentralRegistryRecord | undefined {
    return this.records.get(id);
  }
}
```

#### Langkah 5: Mengaugmentasi Registry dari Modul Lain (`src/plugins/metrics-plugin.ts`)
```typescript
import '../core/registry.js';

// Declaration Merging untuk memperluas tipe bawaan registry
declare module '../core/registry.js' {
  interface CentralRegistryRecord {
    // Properti baru yang di-augmentasikan
    metrics?: {
      uptimeSeconds: number;
      cpuLoad: number;
    };
  }
}

export function injectMetrics(uptimeSeconds: number, cpuLoad: number): NonNullable<import('../core/registry.js').CentralRegistryRecord['metrics']> {
  return {
    uptimeSeconds,
    cpuLoad
  };
}
```

#### Langkah 6: Entry point Konsumsi (`src/index.ts`)
```typescript
import { ServiceRegistry, CentralRegistryRecord } from './core/registry.js';
import { injectMetrics } from './plugins/metrics-plugin.js';
import './ambient/platform-globals.d.ts';

const registry = new ServiceRegistry();

// Menggunakan tipe yang sudah diaugmentasi dan ambient globals
const entry: CentralRegistryRecord = {
  serviceId: __CLUSTER_ID__,
  metadata: {
    name: 'payment-processor',
    version: '1.2.0'
  },
  metrics: injectMetrics(3600, 0.45)
};

registry.register('payment-main', entry);

console.log('App initialized at epoch:', __BUILD_TIMESTAMP__);
console.log('Record registered:', registry.getRecord('payment-main'));
```

#### Langkah 7: Jalankan Verifikasi Kompilasi
```bash
npm run build
```
Periksa output folder `dist/` dan perhatikan file `.d.ts` serta `.d.ts.map` yang dihasilkan dengan seluruh signature lengkap terisolasi.

---

### 13. Exercise

#### Level: Easy
1. Buat sebuah file ambient declaration `safe-window.d.ts` yang menambahkan method `customAnalyticsTracker(event: string, payload: Record<string, unknown>): void` ke objek global `Window`.
2. Validasi kode TypeScript sehingga IDE mengenali signature tersebut tanpa memerlukan baris `import`.

#### Level: Medium
1. Sebuah library pihak ketiga hipotetis bernama `@external/legacy-cache` diekspor dalam format CJS tanpa tipe TypeScript (`index.js`). Library tersebut mengekspor class `CacheStore` dengan method `get(k: string): unknown` dan `set(k: string, v: unknown): boolean`.
2. Buat file `legacy-cache.d.ts` menggunakan syntax `declare module '@external/legacy-cache'` yang mengubah return type `get` menjadi generics: `get<T>(k: string): T | null`.

#### Level: Hard
1. Buat modul routing enterprise. Tentukan antarmuka dasar `AppRoutes` yang sengaja dikosongkan (`interface AppRoutes {}`).
2. Buat fungsi navigasi `navigateTo<T extends keyof AppRoutes>(route: T, params: AppRoutes[T]): void`.
3. Dari file modul terpisah, lakukan augmentasi antarmuka `AppRoutes` sehingga menyertakan rute `'/checkout'` dengan payload `{ cartId: string; totalAmount: number }` dan pastikan fungsi `navigateTo` menolak rute atau payload yang tidak sesuai kontrak secara compile-time.

---

### 14. Challenge

#### Skenario Arsitektur
Anda adalah Principal Architect pada platform Micro-Frontend (MFE) yang menggunakan Module Federation. Tiap micro-frontend (misal: `AuthMFE`, `BillingMFE`) diekspos secara remote dan tidak memiliki dependensi build time satu sama lain. Host shell mengimpor micro-frontend ini secara dinamis:
```typescript
import('AuthMFE/UserProfile').then(...)
```
Secara default, TypeScript akan mengeluarkan error: `Cannot find module 'AuthMFE/UserProfile' or its corresponding type declarations`.

#### Tugas:
1. Rancang arsitektur pengetikan ambient dinamis (*Dynamic Remote Ambient Declarations*) menggunakan pattern matching module declaration (`declare module 'AuthMFE/*'`).
2. Sediakan mekanisme inferensi otomatis di mana setiap komponen yang diimpor dari subpath remote mengembalikan `React.ComponentType<inferProps>` yang valid secara type-safe.
3. Struktur sistem Anda harus menjamin bahwa developer tidak dapat mengimpor subpath remote acak yang dilarang (misal: hanya subpath `'AuthMFE/UserProfile'` dan `'AuthMFE/SessionStatus'` yang diizinkan). Terapkan menggunakan kombinasi *Module Augmentation*, template literal types, dan ambient typings tanpa meng-install dependensi node_modules micro-frontend bersangkutan.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa perbedaan mendasar antara file `.ts` biasa dan file `.d.ts` dalam hal emisi output JavaScript?
2. Mengapa menambahkan `import` top-level pada file deklarasi ambient dapat merusak sifat deklarasi global di dalamnya?
3. Sebutkan fungsi dari konfigurasi compiler `"isolatedDeclarations": true` yang diperkenalkan pada TypeScript 5.5!
4. Apa yang dimaksud dengan *Declaration Merging* dan jenis konstruk sintaks apa saja yang dapat digabungkan?
5. Mengapa kunci `"types"` harus ditempatkan pada posisi urutan paling awal di dalam blok conditional exports `package.json`?

#### Pertanyaan Intermediate
6. Bagaimana cara mengekspos tipe ambient global dari sebuah file yang sudah berstatus sebagai module (sudah memiliki `import`/`export`)?
7. Apa penyebab terjadinya error `Duplicate identifier` saat dua library independen mengaugmentasi interface yang sama, dan bagaimana cara memitigasinya?
8. Bagaimana pengaruh flag `"skipLibCheck": true` terhadap performa kompilasi monorepo berskala besar dan apa risiko teknis di baliknya?
9. Jelaskan perbedaan semantik antara `declare namespace Foo` dan `declare module 'Foo'`!
10. Kapan sebaiknya kita mengaktifkan `"declarationMap": true` pada project TypeScript kita?

#### Skenario Kasus Produksi
11. **Skenario 1**: Sebuah tim enterprise mengeluhkan bahwa saat mereka mengimpor library internal baru mereka via ESM (`import { Core } from '@company/core'`), TypeScript Compiler me-resolve tipenya ke file CJS deklarasi lama yang menyebabkan broken types. Aspek manifest apa yang salah dikonfigurasi?
12. **Skenario 2**: Anda memiliki pustaka NPM TypeScript yang meng-augmentasi package Express via `declare module 'express-serve-static-core'`. Ketika user meng-install pustaka Anda, augmentasi tipe tersebut tidak teraplikasi di aplikasi mereka. Apa akar masalah pada file declaration distribution-nya?
13. **Skenario 3**: Sebuah build pipeline CI/CD memakan waktu kompilasi yang sangat lama pada monorepo dengan 80 paket internal. Analisis menunjukkan bahwa proses `tsc --emitDeclarationOnly` menghabiskan 75% waktu keseluruhan. Langkah refactoring arsitektur tipe apa yang wajib dilakukan untuk memangkas waktu build tersebut secara drastis?

---

### 16. Summary

* **Ambient Context** (`declare`) menginstruksikan TypeScript compiler bahwa sebuah nilai atau struktur tipe telah ada di runtime memory secara eksternal, memisahkannya secara absolut dari pipeline emisi executable JavaScript.
* **Declaration Merging** dan **Module Augmentation** menyediakan mekanisme skalabel bagi software enterprise untuk memperluas fungsionalitas kontrak antarmuka pihak ketiga secara modular dan *decoupled*.
* Paradigma kompilasi modern menuntut isolasi deklarasi yang ketat (`--isolatedDeclarations`). Dengan mewajibkan tipe balik yang eksplisit pada boundary publik paket, monorepo enterprise dapat menggunakan transpiler ultra-cepat untuk menghasilkan artifacts `.d.ts` secara independen tanpa full typechecking bottleneck.
* Konfigurasi deklarasi dual-package (ESM & CJS) membutuhkan ketelitian absolut pada hierarki `package.json` exports mapping untuk mencegah *Dual Package Hazard* pada Type-Space resolution.