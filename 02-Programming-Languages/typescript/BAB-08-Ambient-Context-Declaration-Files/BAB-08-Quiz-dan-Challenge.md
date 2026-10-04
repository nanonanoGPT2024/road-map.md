# BAB 08: Quiz, Challenge, & Knowledge Check
**Ambient Context & Declaration Files**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Ambient Context dan Perilaku Emisi Compiler
Jelaskan secara mendalam apa yang terjadi pada fase kompilasi (`tsc`) ketika compiler mengevaluasi *keyword* `declare`. Mengapa seluruh konstruksi ambient (seperti `declare var`, `declare function`, `declare class`) dijamin memiliki *zero runtime footprint*, dan bagaimana TypeScript compiler memastikan referensi runtime dari identifier ambient tersebut valid pada saat execution time?

### Soal 1.2: Perbedaan Fundamental File `.ts` vs `.d.ts`
Analisis perbedaan arsitektur antara file modul executable (`.ts`) dan file deklarasi tipe murni (`.d.ts`). Mengapa meletakkan implementasi kode runtime (seperti penugasan nilai variabel atau blok fungsi dengan body) di dalam `.d.ts` menghasilkan compiler error atau diabaikan, dan bagaimana Type Checker memperlakukan *symbol table* yang dibangun dari file `.d.ts`?

### Soal 1.3: Mekanisme Resolusi Tipe `@types/*`, `typeRoots`, dan `types`
Bagaimana algoritma resolusi tipe TypeScript bekerja saat mencari deklarasi tipe pihak ketiga? Jelaskan interaksi deterministik antara direktori `node_modules/@types`, flag `typeRoots`, dan flag `types` di dalam `tsconfig.json`. Apa konsekuensi arsitektural jika properti `types` didefinisikan secara eksplisit sebagai array kosong (`"types": []`)?

### Soal 1.4: Anatomi dan Aturan Sintaks Module Augmentation
Jelaskan prinsip kerja *Module Augmentation* melalui konstruksi `declare module 'package-name'`. Aturan scoping apa yang mewajibkan file augmentasi memiliki setidaknya satu *top-level* `import` atau `export` statement? Apa perbedaan mendasar antara melakukan augmentasi pada modul eksternal versus mendeklarasikan modul ambient baru dari nol (*ambient module declaration*)?

### Soal 1.5: Relevansi Triple-Slash Directives di Era Modern
Meskipun sintaks ES Modules (`import`/`export`) telah menjadi standar defacto, Triple-Slash Directives (seperti `/// <reference path="..." />`, `/// <reference types="..." />`, dan `/// <reference lib="..." />`) masih memiliki peran krusial. Jelaskan skenario teknis spesifik di mana Triple-Slash Directives mutlak diperlukan dan tidak dapat digantikan sepenuhnya oleh ES6 import statements.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Resolusi Konflik pada Interface vs Type Alias Declaration Merging
Dua file deklarasi berbeda mencoba memperluas representasi tipe dari entitas yang sama. Salah satu menggunakan mekanisme *Interface Declaration Merging*, sedangkan pihak lain mencoba menggabungkannya via *Intersection Types* (`&`). 
- Bagaimana Type Checker mengevaluasi tumpang tindih (*shadowing*) nama properti yang identik namun memiliki tipe data yang bertentangan pada Interface Merging versus Intersection Types?
- Mengapa TypeScript mengizinkan overload signature pada method merging namun melempar compiler error fatal pada property type collision?

### Soal 2.2: Isolasi Modul vs Global Namespace Pollution Trap
Sebuah file `.d.ts` dibuat untuk mendefinisikan tipe global utilitas, namun tanpa sengaja ditambahkan baris `import { Utility } from './local-types';` di baris teratas file tersebut. 
- Jelaskan perubahan semantik internal yang terjadi pada status file tersebut di mata TypeScript compiler.
- Mengapa seluruh deklarasi global di dalam file tersebut mendadak menjadi privat/terisolasi, dan bagaimana teknik kanonikal untuk mempertahankan impor lokal sekaligus mengekspos tipe ke global context (menggunakan `declare global`)?

### Soal 2.3: Interlocking Pipeline: `declaration`, `declarationMap`, dan `emitDeclarationOnly`
Dalam konteks arsitektur Monorepo (misalnya Turborepo atau Nx) yang menggunakan project references:
- Jelaskan siklus kerja emisi saat flag `declaration: true`, `declarationMap: true`, dan `emitDeclarationOnly: true` diaktifkan bersamaan.
- Bagaimana file `.d.ts.map` memetakan *Abstract Syntax Tree* (AST) dari file `.d.ts` kembali ke kode sumber `.ts` asli, dan mengapa ketiadaan `declarationMap` menyebabkan fitur *Go to Definition* pada IDE consumer hanya melompat ke file deklarasi, bukan ke source code implementasi?

### Soal 2.4: Pembuatan Universal Module Definition (UMD) Ambient Typing
Sebuah library legacy didistribusikan dalam format UMD: library ini dapat diimpor melalui CommonJS/ESM (`import * as Analytics from 'analytics-lib'`) atau langsung diakses melalui global object di browser via tag `<script>` (`window.Analytics`). 
Bagaimana konstruksi deklarasi `.d.ts` yang presisi menggunakan sintaks `export as namespace` untuk memfasilitasi kedua skenario konsumsi tersebut tanpa memicu error `TS2304: Cannot find name 'Analytics'` pada skenario script tag?

### Soal 2.5: Root-Cause Analysis: `TS2688` vs `TS7016`
Dua insiden kompilasi terjadi di CI/CD pipeline:
1. Pipeline A gagal dengan pesan: `error TS7016: Could not find a declaration file for module 'untyped-package'.`
2. Pipeline B gagal dengan pesan: `error TS2688: Cannot find type definition file for 'custom-types'.`

Lakukan dekonstruksi mekanis terhadap algoritma pencarian compiler: Mengapa error tersebut berbeda? Di fase resolusi mana masing-masing kegagalan terjadi, dan bagaimana urutan langkah debugging teknis untuk menyelesaikan kedua masalah tersebut secara permanen tanpa menggunakan `// @ts-ignore`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Dual Package Hazard & Desinkronisasi Emisi Deklarasi pada Monorepo
Sebuah organisasi memigrasikan monorepo library inti mereka dari CommonJS murni ke arsitektur Dual-Package (ESM dan CJS) menggunakan package `tsup` dan TypeScript 5.x. Konfigurasi `package.json` entry point adalah sebagai berikut:

```json
{
  "name": "@enterprise/core-kernel",
  "exports": {
    ".": {
      "import": {
        "types": "./dist/esm/index.d.ts",
        "default": "./dist/esm/index.mjs"
      },
      "require": {
        "types": "./dist/cjs/index.d.ts",
        "default": "./dist/cjs/index.cjs"
      }
    }
  }
}
```

Setelah rilis, ribuan downstream consumer yang menggunakan modul bundler modern (Vite/Webpack 5 dengan `"moduleResolution": "bundler"` atau `"NodeNext"`) melaporkan bahwa TypeScript mereka melempar error:
`TS2305: Module '"@enterprise/core-kernel"' has no exported member 'TransactionEngine'.` 
Namun, saat dicek di runtime node konvensional, modul tersebut berfungsi normal.

**Pertanyaan Diagnostik:**
1. Apa akar penyebab kegagalan resolusi tipe pada downstream consumer terkait urutan deklarasi *conditional exports* pada `package.json` di atas?
2. Bagaimana representasi AST dan perbedaan format deklarasi CJS (`export =`) versus ESM (`export default` / named exports) dapat memicu benturan tipe (*type-level dual-package hazard*)?
3. Tuliskan perbaikan definitif untuk struktur `package.json` dan rekomendasi flag `tsconfig.json` emit compiler (`moduleResolution`, `declaration`, `declarationMap`) guna menjamin interoperabilitas total.

---

### Skenario B: Race Condition dan Collision pada Global Augmentation Multi-Library
Aplikasi enterprise berorientasi micro-service menggunakan Framework Express. Dua tim independen mengintegrasikan pustaka middleware mereka sendiri ke dalam platform:
- Tim Autentikasi menginstal `@enterprise/auth-context` yang memodifikasi tipe `Express.Request` via global augmentation untuk menambahkan property `user: AuthenticatedUser`.
- Tim Observabilitas menginstal `@enterprise/tracer` yang juga memodifikasi interface `Express.Request` untuk menambahkan property `user: TelemetryIdentity`.

```typescript
// @enterprise/auth-context/index.d.ts
declare global {
  namespace Express {
    interface Request {
      user: {
        id: string;
        roles: string[];
        jwtToken: string;
      };
    }
  }
}

// @enterprise/tracer/index.d.ts
declare global {
  namespace Express {
    interface Request {
      user: {
        telemetryId: number;
        sampleRate: number;
      };
    }
  }
}
```

Ketika aplikasi downstream mengimpor kedua pustaka secara bersamaan, build CI/CD meledak dengan fatal error:
`TS2717: Subsequent property declarations must have the same type. Property 'user' must be of type '...', but here has type '...'.`

**Pertanyaan Diagnostik:**
1. Mengapa compiler TypeScript tidak dapat melakukan merge otomatis pada property `user` meskipun keduanya bertindak sebagai interface declaration?
2. Mengapa urutan pemanggilan `import` di entrypoint runtime dapat menyamarkan atau mengekspos error ini secara acak (nondeterministik) pada proses kompilasi monorepo incremental?
3. Rancang strategi arsitektural untuk menyelesaikan collision ini tanpa mengubah fungsionalitas bisnis kedua pustaka. Bagaimana Anda menstrukturkan namespace, decoupling context, atau context typing agar tidak terjadi polusi global yang saling menghancurkan?

---

### Skenario C: Reverse-Engineering & Typing Legacy Browser Runtime Polyfill
Anda ditugaskan memodernisasi web platform peninggalan era 2012. Aplikasi ini bergantung pada script runtime proprietari dari vendor luar yang dimuat via CDN secara asinkron sebelum bundle aplikasi dijalankan. Script ini menginjeksi sebuah dynamic host object ke global runtime:

```javascript
// Diinjeksi oleh vendor secara runtime ke window:
window.__ENTERPRISE_SYSTEM__ = {
  version: "4.2.1-legacy",
  session: {
    token: "raw_token_xyz",
    renew: function(cb) { cb(null, "new_token"); }
  },
  // Registry plugin dinamis
  registry: {},
  registerPlugin: function(name, pluginInstance) {
    this.registry[name] = pluginInstance;
  },
  execute: function(command, ...payloads) {
    // Menjalankan command secara dinamis
  }
};
```

Tim arsitektur melarang keras penggunaan `any` dan melarang modifikasi file runtime vendor tersebut. Anda diminta menyusun declaration strategy enterprise.

**Pertanyaan Diagnostik:**
1. Rancang file deklarasi tipe ambient murni (`vendor-system.d.ts`) yang memodelkan struktur `window.__ENTERPRISE_SYSTEM__` secara presisi, termasuk callback signature, generic dynamic plugins, dan type-safe command execution.
2. Tentukan di mana file deklarasi ini harus diletakkan dalam struktur project dan konfigurasi `tsconfig.json` apa yang wajib diaktifkan/dinonaktifkan agar seluruh developer di tim mendapatkan full autocomplete dan auto-type checking saat mengakses `window.__ENTERPRISE_SYSTEM__` tanpa perlu melakukan explicit import statement di setiap file komponen.
3. Evaluasi trade-off keamanan tipe: Apa risiko arsitektural jika script vendor tersebut gagal dimuat (load failure/network partition) saat runtime, dan bagaimana pola deklarasi tipe TypeScript dapat diintegrasikan dengan runtime verification (*type narrowing* / *type guards*) untuk mencegah crash fatal `TypeError: Cannot read properties of undefined`?

---

## 4. Chapter Challenge

### Tantangan Praktis: Type-Safe Legacy SDK & Third-Party Library Modernization Engine

#### Problem Description
Sebuah platform fintech memproses transaksi pembayaran menggunakan SDK analitik legacy (`EnterpriseTracker`) yang dimuat secara eksternal melalui script tag HTML, serta sebuah library pemrosesan data internal `data-pipeline` yang ditulis dalam vanilla CJS tanpa file `.d.ts`. 

Selain itu, aplikasi membutuhkan mekanisme dynamic plugin di mana modul internal dapat mendaftarkan *custom analytic events* yang akan diverifikasi secara strictly-typed saat fungsi dispatch dipanggil. Saat ini codebase penuh dengan `// @ts-ignore` dan cast `(window as any).EnterpriseTracker`. Anda diinstruksikan untuk membangun fondasi type system declaration yang komprehensif, kuat, dan bersih tanpa memodifikasi kode JavaScript runtime yang ada.

#### Requirements
1. **Ambient Window Extension:**
   - Buat file deklarasi ambient yang memperluas objek `Window` global tanpa mencemari global namespace lain.
   - Properti `window.EnterpriseTracker` harus memiliki method:
     - `init(apiKey: string, options?: TrackerOptions): Promise<boolean>`
     - `track<E extends ValidEventName>(event: E, payload: EventPayloadMap[E]): void`
     - `on(event: 'ready' | 'error', handler: (err?: Error) => void): void`
2. **Generic Declaration Merging for Plugins:**
   - Rancang interface `CustomTrackerEvents` kosong di dalam namespace global ambient.
   - Sediakan mekanisme di mana feature-module lain dapat melakukan interface merging ke `CustomTrackerEvents` untuk mendaftarkan payload event baru.
   - `EventPayloadMap` harus secara otomatis memetakan tipe event bawaan (`'PAGE_VIEW'`, `'CLICK'`) digabung secara dinamis dengan apapun yang didaftarkan pada `CustomTrackerEvents`.
3. **Module Augmentation & Typings for Untyped NPM Package:**
   - Buat ambient module declaration untuk modul fiktif `data-pipeline`.
   - Modul ini mengekspor fungsi CJS standar:
     ```javascript
     function processStream(stream, config) { ... }
     module.exports = { processStream };
     ```
   - Ketik fungsi ini dengan generic stream payload transformer yang memvalidasi input schema stream dan output schema record.
4. **Isolated Modules Compatibility:**
   - Pastikan seluruh file deklarasi yang Anda buat 100% kompatibel dengan flag `"isolatedModules": true`, `"moduleResolution": "NodeNext"`, dan `"strict": true`.

#### Constraints
- Dilarang menggunakan tipe `any`, `unknown` tanpa narrowing, atau type assertion `as` pada file demonstrasi konsumsi.
- Dilarang menyertakan kode JavaScript executable pada file deklarasi tipe (`.d.ts`).
- Declarative type definitions harus kompatibel dengan consumer yang menggunakan ESM modern (`import ... from ...`).

#### Expected Output
1. File `src/types/enterprise-tracker.d.ts`:
   - Deklarasi core tracking system, UMD/Ambient global interface, generic dynamic mapping.
2. File `src/types/data-pipeline.d.ts`:
   - Deklarasi ambient module untuk module CJS `data-pipeline`.
3. File `src/features/feature-audit/audit-event-augmentation.d.ts`:
   - Pembuktian deklarasi augmentasi modul/global yang menambahkan event `'AUDIT_EVENT'` dengan payload `{ auditId: string; timestamp: number }`.
4. File `src/index.ts`:
   - Kode sampel yang mendemonstrasikan konsumsi runtime bertipe valid (autocompletion berjalan, dispatch valid, dan mendemonstrasikan bahwa compile error akan muncul jika payload event tidak sesuai kontrak tipe).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan formal antara *ambient binding* (informasi tipe murni untuk compiler) dan *concrete binding* (alokasi memori runtime).
- [ ] Dampak presence dari `import`/`export` statement pada file `.d.ts` (mengubah status file dari global script menjadi module-scoped ambient file).
- [ ] Cara kerja *Declaration Merging* pada interface vs function overloads vs namespace, beserta batasannya.
- [ ] Perbedaan antara module augmentation (`declare module 'pkg'`) dan global augmentation (`declare global`).
- [ ] Urutan dan hirarki pencarian tipe oleh compiler: `types` array vs `typeRoots` scanning vs sub-path export `types` pada `package.json`.
- [ ] Implikasi penggunaan `export =` (CommonJS style) vs `export default` (ESM style) dalam file deklarasi untuk sistem resolusi modern (`NodeNext`).
- [ ] Hubungan teknis antara compiler options `declaration`, `declarationMap`, dan `emitDeclarationOnly`.

### Saya tidak perlu menghafal:
- [ ] Seluruh parameter flag CLI dari `tsc` yang dapat diwakilkan oleh file `tsconfig.json`.
- [ ] Seluruh isi header syntax Triple-Slash Directive format kuno yang sudah di-deprecate oleh TypeScript roadmap.
- [ ] Struktur internal binary dari `.d.ts.map` (cukup memahami peran mapping URI dan mapping node AST-nya).
- [ ] Konfigurasi internal bundler pihak ketiga (misal: Rollup/Vite/Webpack) dalam mengekstrak tipe, di luar mekanisme standar TypeScript engine.

### Saya harus bisa melakukan:
- [ ] Menulis ambient declaration file dari nol untuk library JavaScript vanilla pihak ketiga yang tidak memiliki tipe bawaan.
- [ ] Mengonfigurasi `tsconfig.json` secara optimal untuk pipeline pembuatan library mandiri berbasis Project References.
- [ ] Melakukan troubleshooting dan memperbaiki siklus error resolusi tipe standar enterprise: `TS7016`, `TS2688`, `TS2304`, dan `TS2717`.
- [ ] Melakukan safely-typed global augmentation pada objek runtime standar platform (`Window`, `ProcessEnv`, `Express.Request`).
- [ ] Menerapkan pattern *declaration merging* yang dapat diperluas (*extensible*) untuk dynamic architecture / plugin-based software systems.