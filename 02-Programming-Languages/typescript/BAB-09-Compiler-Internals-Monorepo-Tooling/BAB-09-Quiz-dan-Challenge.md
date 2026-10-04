# BAB 09: Quiz, Challenge, & Knowledge Check
**Compiler Internals & Monorepo Tooling**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Pipeline Arsitektur TypeScript Compiler (`tsc`)**  
   Jelaskan secara berurutan lima tahapan utama dari pipeline kompilasi TypeScript (*Scanner/Lexer*, *Parser*, *Binder*, *TypeChecker*, dan *Emitter*). Apa tanggung jawab spesifik dari tahap *Binder*, dan mengapa pemisahan antara tahap *Binder* dan *TypeChecker* esensial untuk efisiensi kompilasi berulang (*incremental checking*)?

2. **Dualitas AST Node vs. Symbol Table**  
   Dalam TypeScript Compiler API, bedakan antara `ts.Node`, `ts.Symbol`, dan `ts.Type`. Mengapa sebuah *AST Node* tidak menyimpan tipe secara langsung, melainkan harus di-resolve melalui `ts.TypeChecker`? Berikan contoh di mana dua `ts.Node` yang identik secara sintaksis merujuk pada `ts.Symbol` atau `ts.Type` yang berbeda.

3. **Mekanisme Project References (`composite: true`)**  
   Ketika mengaktifkan `"composite": true` pada `tsconfig.json`, compiler mewajibkan pengaturan `"declaration": true` dan menghasilkan file `.tsbuildinfo`. Jelaskan dependensi mekanis antara ketiga flag ini! Bagaimana file `.tsbuildinfo` memodelkan graf dependensi internal untuk memvalidasi apakah suatu proyek memerlukan kompilasi ulang atau tidak?

4. **Path Mapping (`paths`) vs. Package Resolution**  
   Banyak pengembang keliru menganggap konfigurasi `compilerOptions.paths` di `tsconfig.json` bertindak sebagai *bundler alias* atau *package resolver* saat runtime. Jelaskan apa yang sebenarnya dilakukan `tsc` terhadap deklarasi `paths` selama proses *type-checking* dan *emit*. Mengapa mengandalkan `paths` tanpa integrasi resolver runtime/bundler (seperti `exports` di `package.json` atau runtime aliases) menjadi anti-pattern dalam arsitektur monorepo?

5. **`isolatedModules` dan Batasan Emisi Transpiler Pihak Ketiga**  
   Mengapa transpiler modern berbasis non-type-directed (seperti SWC, esbuild, atau Babel) memerlukan flag `"isolatedModules": true` pada `tsconfig.json`? Berikan dua contoh konstruksi kode TypeScript valid yang akan gagal atau menghasilkan runtime bug fatal jika ditranspilasi oleh toolchain tersebut tanpa evaluasi tipe secara global.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Phantom Types dan Memory Leak pada AST Transformer**  
   Saat menulis custom AST Transformer menggunakan TypeScript Compiler API (`ts.transform`), pengembang sering melakukan mutasi in-place pada properti node atau menggunakan factory function (`ts.factory.*`) tanpa memperbarui referensi node induk (`parent pointers`) atau *SourceMap location*. Apa dampak fatal dari pembuatan node sintesis yang tidak memiliki asosiasi `original` node (`ts.setOriginalNode`) terhadap emisi *declaration files* (`.d.ts`) dan *source map mapping*?

2. **Circular Dependency Tracking pada Composite Projects**  
   TypeScript Compiler dengan mode build (`tsc -b` / `--build`) membangun *Directed Acyclic Graph* (DAG) dari seluruh project references sebelum eksekusi. Bagaimana algoritma resolusi graf `tsc` mendeteksi dependensi siklik antarpaket? Mengapa dependensi siklik yang valid pada level JavaScript/bundler runtime tetap ditolak secara mutlak oleh `tsc --build`?

3. **Declaration Emit Failure (`--declaration` / `--isolatedDeclarations`)**  
   Pada TypeScript 5.5+, diperkenalkan flag `--isolatedDeclarations`. Jelaskan masalah arsitektural apa yang ingin diselesaikan oleh flag ini dalam monorepo berskala puluhan ribu file! Debug skenario berikut: Mengapa fungsi di bawah ini lolos validasi `--declaration` standar (meski lambat), tetapi melempar error di bawah `--isolatedDeclarations`?
   ```typescript
   export function computeState(config: { retries: number }) {
     return {
       status: "idle" as const,
       payload: config.retries > 0 ? new Map<string, number>() : null
     };
   }
   ```

4. **Substitusi Simbol pada Namespace & Module Augmentation**  
   Bagaimana *Binder* menangani penggabungan deklarasi (*Declaration Merging*) ketika sebuah modul eksternal di-augmentasi melalui `declare module 'foo'`? Secara internal, bagaimana compiler mencegah polusi namespace global dan memastikan bahwa modifikasi tersebut hanya terlihat pada file yang berada di dalam lingkup graf kompilasi yang mengimpor augmentasi tersebut?

5. **Cache Invalidation Under Nx/Turborepo Task Pipelines**  
   Dalam orkestrasi monorepo dengan tools seperti Turborepo atau Nx, kita memisahkan target `typecheck` (`tsc --noEmit`) dan `build` (misal: `tsup`, `rollup`, atau `esbuild`). Jelaskan risiko desinkronisasi cache jika hash komputasi target `typecheck` hanya memperhitungkan `src/**/*.ts`, namun mengabaikan perubahan tipe pada dependensi hulu (*upstream internal packages*) yang mendistribusikan tipe via Project References!

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden OOM (Out-of-Memory) dan CI Pipeline Chokepoint
Sebuah tim enterprise mengelola monorepo dengan 140 paket TypeScript internal menggunakan pnpm workspace. CI pipeline mereka mengalami kegagalan fatal: eksekusi `pnpm run typecheck` (yang menjalankan `tsc --build .` di root) secara konsisten melempar error:
`FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory`.

Tim DevOps mencoba menyelesaikan ini secara instan dengan menaikkan `--max-old-space-size=16384` (16GB), tetapi CI runner sekarang memakan waktu 48 menit dan sering kali freeze.
*   **Pertanyaan Diagnostik & Solusi:**
    1. Analisis mengapa `tsc -b` mengonsumsi memori secara eksponensial pada graf monorepo besar jika batasan arsitektur Project References tidak diatur secara modular!
    2. Identifikasi bagaimana circular imports implisit antar-workspace dan konfigurasi `rootDirs` atau referensi `include` yang terlalu luas (`../../packages/*/src`) merusak isolasi memory compiler.
    3. Rancang strategi restrukturisasi build pipelining (manfaatkan Turborepo/Nx task caching, topological execution, dan decoupling `tsc --build` per paket vs. orkestrasi paralel) untuk menurunkan durasi CI ke bawah 4 menit.

### Skenario B: Declaration Drift & Race Condition Artefak Build
Sebuah platform Core SDK dibangun menggunakan arsitektur monorepo di mana Paket `@core/auth` diimpor oleh Paket `@core/api-client`. Tim mengimplementasikan sistem build paralel menggunakan custom script Node.js. 

Saat deployment ke staging, terjadi insiden di mana `@core/api-client` mendistribusikan file `.d.ts` yang memuat tipe lama dari `@core/auth`, meskipun kode JavaScript hasil transpiler memuat implementasi logika yang baru. Hal ini mengakibatkan kompilasi konsumen hilir (*downstream apps*) gagal dengan error `Property 'sessionToken' does not exist on type 'AuthResponse'`, padahal kode sumber `@core/auth` sudah memperbarui properti tersebut.
*   **Pertanyaan Diagnostik & Solusi:**
    1. Mengapa race condition antara proses bundling JavaScript (`esbuild`/`swc`) dan proses generasi definisi tipe (`tsc --emitDeclarationOnly`) dapat menyebabkan *Declaration Drift* ini?
    2. Mengapa symlink internal workspace pnpm/yarn dapat memvalidasi tipe dari file sumber TypeScript (`src/index.ts`) alih-alih file deklarasi distribusi (`dist/index.d.ts`) jika `package.json` tidak dikonfigurasi dengan benar menggunakan conditional exports?
    3. Tentukan arsitektur konfigurasi `package.json` (termasuk keys: `exports`, `types`, `typesVersions`) dan dependency ordering yang deterministik untuk memastikan integritas artefak build.

### Skenario C: Trade-off Arsitektur Sistem: Just-in-Time (JIT) vs. Ahead-of-Time (AOT) Monorepo Packages
Perusahaan sedang memperdebatkan standardisasi arsitektur paket internal monorepo antara dua paradigma:
*   **Paradigma 1 (JIT / Internal Transpilation):** Paket internal tidak memiliki build step. Paket-paket tersebut hanya mengekspor raw TypeScript (`src/index.ts`). Bundler dari aplikasi konsumen (Next.js, Vite) bertanggung jawab mentranspilasi seluruh dependensi monorepo secara langsung menggunakan konfigurasi bundler masing-masing.
*   **Paradigma 2 (AOT / Pre-compiled Packages with Project References):** Setiap paket internal wajib mengompilasi kode dan menghasilkan artefak `dist/` (`.js`, `.d.ts`, `.d.ts.map`) menggunakan `tsc -b` sebelum dapat dikonsumsi oleh paket atau aplikasi lain.
*   **Pertanyaan Diagnostik & Solusi:**
    1. Analisis trade-off kedua pendekatan ini ditinjau dari: Developer Experience (kecepatan feedback HMR saat local dev), determinisme type-checking di CI, isolasi compiler target (misal: Node CJS vs Browser ESM), dan skalabilitas ketika monorepo tumbuh melampaui 100 paket.
    2. Dalam skenario apa Paradigma 1 akan mengalami kegagalan total saat ada paket monorepo yang perlu dipublikasikan ke private npm registry eksternal?
    3. Berikan rekomendasi arsitektur hibrida yang mempertahankan kecepatan JIT pada local dev tanpa mengorbankan integritas AOT pada pipeline CI/CD.

---

## 4. Chapter Challenge

### Tantangan Praktis: Custom AST Linter & Build Orchestration Validator Engine

#### Problem Description
Di banyak monorepo enterprise, arsitektur sering kali bocor akibat pengembang mengimpor implementasi internal secara langsung melewati batas batas publik (misalnya mengimpor dari `@org/ui/src/button/internal-hook` alih-alih `@org/ui`). Lebih buruk lagi, kebocoran ini diperparah oleh dependensi liar di mana modul internal menggunakan `import type` dari paket yang tidak terdaftar di dalam `dependencies` atau `peerDependencies` pada `package.json` paket tersebut, menciptakan *phantom type dependencies* yang hanya lolos saat local dev berkat hoisting package manager.

Tugas Anda adalah membuat sebuah CLI Engine mandiri menggunakan TypeScript Compiler API murni yang menginspeksi AST dari seluruh workspace, memvalidasi isolasi boundary modul, serta memverifikasi keselarasan antara `tsconfig.json` Project References dengan graf dependency `package.json`.

#### Requirements
1. **Engine Dependency Boundary Scanner (AST-based):**
   * Buat program Node.js menggunakan TypeScript API (`ts.createProgram` atau Compiler API traversal).
   * Lakukan traversing pada setiap file `.ts`/`.tsx` di dalam direktori workspace.
   * Ekstraksi seluruh `ImportDeclaration` dan `ExportDeclaration`.
   * Deteksi dan gagalkan proses (exit code 1) jika ditemukan:
     * *Deep Imports*: Mengimpor melewati batas entri utama suatu paket monorepo (misal: mengimpor dari `@monorepo/pkg/src/*` alih-alih modul export publik yang didefinisikan dalam `package.json#exports`).
     * *Phantom Dependencies*: Mengimpor paket monorepo lain yang tidak dideklarasikan pada `dependencies` atau `devDependencies` di `package.json` lokal paket tersebut.
2. **Deterministic Graph & tsconfig Project Reference Validator:**
   * Baca file root `tsconfig.json` dan seluruh `tsconfig.json` child package.
   * Lakukan verifikasi silang: Jika Paket B bergantung pada Paket A di `package.json`, pastikan array `references` pada `packages/B/tsconfig.json` secara eksplisit memuat `{ "path": "../A" }`.
   * Pastikan konfigurasi `"composite": true` aktif di seluruh paket yang menjadi target referensi.
3. **AST Transformer Injection (Bonus/Advanced):**
   * Buat sebuah custom transformer factory (`ts.TransformerFactory<ts.SourceFile>`) yang secara otomatis menyuntikkan konstanta telemetri build di setiap file entri root:
     `export const __BUILD_METRICS__ = { timestamp: <CURRENT_UNIX_TIMESTAMP>, package: <PKG_NAME> };`
   * Emisikan kode JavaScript beserta deklarasi tipe (`.d.ts`) baru yang memuat definisi tipe untuk `__BUILD_METRICS__` menggunakan API emisi compiler.

#### Constraints
* **Pure Compiler API**: Tidak boleh menggunakan linter pihak ketiga seperti ESLint atau tool analysis eksternal (wajib menggunakan modul `typescript` murni).
* **Strict Performance Budget**: Engine harus mampu memproses dan menganalisis minimal 500 file AST dalam waktu kurang dari 3.5 detik tanpa memicu OOM (gunakan traversing node manual via `ts.forEachChild` alih-alih membuat instance `TypeChecker` penuh untuk pengecekan sintaksis murni guna menghemat memori).
* Wajib menangani edge case: *Dynamic Imports* (`await import(...)`), *Type-only Imports* (`import type { ... }`), dan *Re-exports* (`export { x } from '...'`).

#### Expected Output
Sebuah script executable (`bin/monorepo-architect-validator.ts`) yang ketika dieksekusi menghasilkan reporting terstruktur di terminal:
```text
[Monorepo Architecture Validator]
Scanning 12 packages (624 SourceFiles)...

[FAIL] Deep Import Violation:
  File: packages/dashboard/src/components/Header.tsx:4:1
  Import: "@corp/shared/src/utils/crypto"
  Remedy: Import must be through public package boundary "@corp/shared".

[FAIL] Missing tsconfig Project Reference:
  Package: packages/api-gateway
  Missing Reference: "../core-auth" must be listed in packages/api-gateway/tsconfig.json references.

[FAIL] Phantom Type Dependency:
  File: packages/reporting/src/index.ts:1:1
  Import: "@corp/database"
  Remedy: "@corp/database" is not defined in packages/reporting/package.json.

Summary: 3 Architectural Violations Detected across 2 packages.
Validation failed in 1.42s.
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur 5 tahap TypeScript Compiler (`Scanner` $\to$ `Parser` $\to$ `Binder` $\to$ `TypeChecker` $\to$ `Emitter`) beserta fungsi output masing-masing tahapan.
- [ ] Perbedaan fundamental antara `ts.Node` (struktur sintaksis file lokal), `ts.Symbol` (entitas model semantik yang menyatukan deklarasi), dan `ts.Type` (representasi komputasi tipe pada sistem inferensi/pengecekan).
- [ ] Hubungan internal antara `composite: true`, `declaration: true`, `incremental: true`, dan peran metadata deterministik dalam file `.tsbuildinfo`.
- [ ] Batasan kompilasi dari toolchain berbasis file tunggal (*single-file non-type-directed emitters*) seperti esbuild, SWC, dan Babel yang mewajibkan flag `isolatedModules`.
- [ ] Prinsip dan keuntungan dari flag `isolatedDeclarations` untuk paralelisasi pipeline arsitektur monorepo skala ultra-besar.
- [ ] Bagaimana algoritma module resolution (`Node16`, `NodeNext`, `Bundler`) beroperasi sehubungan dengan properti conditional `exports` dan `types` pada `package.json`.
- [ ] Konsep Directed Acyclic Graph (DAG) dalam orkestrasi build monorepo dan bahaya dependensi siklik pada kompilasi tingkat paket.

### Saya tidak perlu menghafal:
- [ ] Seluruh numerik bitwise flag internal compiler (misalnya: `ts.NodeFlags`, `ts.ModifierFlags`, `ts.SymbolFlags`, `ts.TypeFlags`). Cukup pahami cara melakukan bitwise checking menggunakan bitmask helper API.
- [ ] Parameter spesifik dari ribuan method internal yang ada di dalam instance `ts.TypeChecker` privat (fokuslah hanya pada API publik resmi compiler).
- [ ] Konfigurasi skema low-level lengkap dari seluruh tool orkestrasi monorepo pihak ketiga (Nx, Turborepo, Lerna), melainkan esensi interaksi input-output graf antar task.

### Saya harus bisa melakukan:
- [ ] Menulis script menggunakan TypeScript Compiler API murni untuk mem-parsing source code menjadi AST, melakukan manipulasi node via AST Transformer (`ts.factory`), dan mengemisikan hasilnya.
- [ ] Mendiagnosis dan memperbaiki masalah memory leak atau Out of Memory (OOM) yang terjadi saat eksekusi `tsc` pada monorepo berskala besar.
- [ ] Mengonfigurasi monorepo multi-package berbasis Project References dari nol menggunakan pnpm/yarn workspace yang mendukung *incremental compilation* secara deterministik.
- [ ] Mengonfigurasi file `package.json` modern dengan standar `exports` mapping yang secara ketat membedakan entry point untuk CJS, ESM, dan deklarasi TypeScript (`types`).
- [ ] Menganalisis dan mengeliminasi fenomena *Phantom Dependencies* dan *Declaration Drift* pada supply chain arsitektur internal perusahaan.