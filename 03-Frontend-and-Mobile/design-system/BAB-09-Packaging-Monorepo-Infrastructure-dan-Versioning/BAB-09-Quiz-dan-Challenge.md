# BAB 09: Quiz, Challenge, & Knowledge Check
**Packaging, Monorepo Infrastructure, & Versioning**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Dual-Package Hazard & Subpath Exports
Jelaskan fenomena *Dual-Package Hazard* yang terjadi saat memublikasikan pustaka komponen UI modern yang mendukung CommonJS (CJS) dan ECMAScript Modules (ESM) secara simultan. Bagaimana spesifikasi `exports` map modern pada `package.json` (termasuk *conditional exports* seperti `import`, `require`, dan `types`) menyelesaikan masalah resolusi modul tradisional, dan apa konsekuensi teknis terhadap *runtime state* (misal: React Context atau CSS-in-JS style registry) jika *hazard* ini gagal dimitigasi?

### Soal 1.2: Topologi Dependency Engine: Hoisted vs Symlinked/Hardlinked
Bandingkan mekanisme isolasi dependensi antara arsitektur *hoisted* (Yarn Classic/npm legacy) dengan arsitektur *Content-Addressable Store* berbasis *hardlink* dan *symlink* (pnpm). Uraikan secara struktural bagaimana pnpm mengeliminasi masalah *phantom dependencies* dan *doppelgängers* pada monorepo *design system* berskala besar dengan puluhan *internal workspace packages*.

### Soal 1.3: SemVer Governance: Independent vs Fixed/Synchronized Versioning
Evaluasi trade-off arsitektural antara model *Independent Versioning* dan *Fixed (Synchronized) Versioning* dalam ekosistem monorepo *design system* yang memayungi puluhan *atomic packages* (seperti `@ds/tokens`, `@ds/core`, `@ds/icons`, `@ds/primitives`). Pada skala organisasi seperti apa masing-masing strategi optimal diterapkan, dan bagaimana dampaknya terhadap *dependency resolution graph* di aplikasi konsumen (*downstream consumers*)?

### Soal 1.4: Tree-Shaking Mechanics & Side Effects Optimization
Bagaimana *bundler* modern (Rollup, Vite, Webpack) mengevaluasi deklarasi `"sideEffects": false` vs *side-effects array* pada `package.json`? Jelaskan mengapa impor file CSS global atau polifil sering kali tereliminasi secara tidak sengaja (*accidental dead-code elimination*) jika konfigurasi ini tidak presisi, dan bagaimana arsitektur kompilasi *atomic components* harus dirancang untuk menjamin *pure zero-cost imports*.

### Soal 1.5: Deterministic Computation & Remote Caching pada Build Orchestrators
Uraikan prinsip kerja *Directed Acyclic Graph* (DAG) pada *build orchestrators* monorepo (seperti Turborepo atau Nx). Bagaimana sistem menghitung *hash fingerprint* untuk menentukan *cache hit* vs *cache miss* pada tugas kompilasi internal, dan faktor apa saja dari *environment inputs* (misal: *node version*, *system environment variables*, *lockfile changes*) yang wajib diisolasi untuk memastikan *hermetic build* lintas mesin developer dan CI runner?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Debugging Inferred Type Leaks (TS2742)
Saat menjalankan `tsc --emitDeclarationOnly` di dalam package internal monorepo `@ds/core` yang mereferensikan tipe data dari workspace lokal `@ds/tokens`, sering muncul galat fatal: 
`error TS2742: The inferred type of 'X' cannot be named without a reference to '...'. This is likely not portable.`
Analisis akar penyebab struktural dari galat ini pada level TypeScript compiler host, dan jelaskan langkah remediasi yang tepat tanpa harus mematikan `declarationMap` atau mengekspor tipe data internal secara ceroboh.

### Soal 2.2: Phantom Dependency CI Failure Triage
Sebuah pull request lolos pengujian *build* dan *test* secara sempurna di mesin lokal seorang engineer (menggunakan macOS), namun secara konsisten gagal pada GitHub Actions runner (Ubuntu) dengan pesan `Module not found: Can't resolve 'lodash-es'`. Setelah ditelusuri, `lodash-es` tidak dideklarasikan di `package.json` lokal package tersebut. Jelaskan mengapa ini bisa terjadi di lingkungan berbasis pnpm/monorepo, bagaimana *dependency hoisting leakage* lokal dapat menyamarkan isu tersebut, dan bagaimana aturan *strict peer dependencies* dapat dipaksakan via `.npmrc`.

### Soal 2.3: Type Definition Dual-Package Matching (`typesVersions` vs `exports.types`)
Ketika sebuah package dipublikasikan dengan *modern subpath exports*, pengembang yang menggunakan TypeScript dengan setting `"moduleResolution": "node"` (konfigurasi pra-Node16 legacy) gagal mendeteksi file deklarasi `.d.ts`, sementara pengembang dengan setting `"node16"` atau `"bundler"` berhasil. Jelaskan bagaimana mekanisme *fallback* `typesVersions` dalam `package.json` bekerja untuk memberikan kompatibilitas mundur bagi konsumen berkonfigurasi lawas tanpa merusak hierarki resolusi modern.

### Soal 2.4: Changesets Lifecycle & Automated Version Bumping Anomaly
Dalam alur kerja CI/CD berbasis Changesets, terjadi anomali di mana *minor release* pada package dasar `@ds/tokens` memicu *cascade update* yang tidak diinginkan berupa penulisan ulang seluruh versi package downstream menjadi *major release*. Bedah mekanisme internal Changesets (khususnya relasi *fixed* vs *linked groups* dan format semver *bump* `patch`/`minor`/`major`), lalu berikan konfigurasi `.changeset/config.json` yang benar untuk mencegah cascade bumping yang tidak terkontrol.

### Soal 2.5: Runtime Deduplication & External Helper Bundling
Ketika aplikasi downstream mengimpor komponen dari `@ds/core`, terjadi inflasi ukuran bundle secara drastis (*bundle bloat*) dan terdeteksi multiple copy dari library utilitas runtime yang sama (seperti `tslib`, `@floating-ui/react`, atau `@emotion/react`). Analisis bagaimana kesalahan konfigurasi `external` pada bundler (misal: tsup/Rollup) dan kegagalan penetapan `peerDependencies` menyebabkan fragmentasi instance ini, serta bagaimana melakukan audit dependency tree downstream menggunakan tool analitik bundle.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Ekstrem Turborepo CI Cache Invalidation
* **Konteks:** Perusahaan fintech skala enterprise memiliki monorepo *design system* yang mencakup 65 packages dan dikonsumsi oleh 12 tim produk. Pipeline CI yang awalnya berjalan 3 menit melonjak menjadi 48 menit. Tim menyadari bahwa remote cache Turborepo memiliki *cache hit rate* 0% pada GitHub Actions, meskipun tidak ada kode yang diubah di 80% package.
* **Gejala Teknis:** Hash kompilasi package berubah pada setiap commit, bahkan pada commit yang hanya memodifikasi file `README.md`.
* **Pertanyaan Diagnostik:**
  1. Identifikasi minimal 3 penyebab paling umum mengapa *input hashing* pada Turborepo terinvalidasi secara global di pipeline CI.
  2. Bagaimana Anda mengonfigurasi parameter `inputs` dan `env` pada `turbo.json` agar *task* kompilasi benar-benar kebal terhadap metadata non-fungsional (misal: dynamic Git timestamps, random IDs, unpinned environment variables)?
  3. Rancang arsitektur pipeline CI (*matrix/pruned workspace strategy*) menggunakan `turbo prune --scope=<target>` untuk meminimalkan beban komputasi ketika memvalidasi downstream pull requests.

### Skenario B: Race Condition Diamond Dependency & Multiple Singletons
* **Konteks:** Aplikasi mobile web enterprise mengalami crash misterius di runtime produksi:
  `TypeError: Cannot read properties of null (reading 'useTheme')`
  Komponen Button dari `@ds/core` gagal membaca context yang disediakan oleh `ThemeProvider` dari `@ds/theme`, meskipun struktur kode terlihat benar: `<ThemeProvider><Button /></ThemeProvider>`.
* **Hasil Audit Awal:** Konsumen menginstal `@ds/core` versi `^3.2.0` dan `@ds/complex-table` versi `^1.0.0`. Di balik layar, `@ds/complex-table` mengunci `@ds/theme` pada versi `3.0.0`, sementara `@ds/core` mengonsumsi `@ds/theme` versi `3.2.0`.
* **Pertanyaan Diagnostik:**
  1. Jelaskan bagaimana NPM/PNPM menduplikasi package `@ds/theme` di dalam struktur `node_modules` konsumen akibat perbedaan rentang *version constraint* (*Diamond Dependency Problem*).
  2. Mengapa React Context `createContext` gagal mengenali hierarki Provider jika terdapat dua instance fisik modul JavaScript yang sama di memori runtime?
  3. Formulasikan strategi definitif pada sisi *library maintainer* (melalui rekayasa `peerDependencies`, `peerDependenciesMeta`, dan bundling contract) untuk menjamin bahwa konsumen tidak akan pernah menginisialisasi lebih dari satu instance runtime context.

### Skenario C: Migrasi Arsitektur Monorepo: Workspace Protocol vs Published Registry
* **Konteks:** Tim inti *Design System* memutuskan bermigrasi dari repositori monolitis lama (*monolithic polyrepo architecture*) ke pnpm multi-package monorepo. Selama fase transisi lokal, para developer aplikasi konsumen mengeluhkan *cycle release* internal yang sangat lambat: setiap perbaikan kecil pada komponen primitif mengharuskan build, publish ke internal Verdaccio/NPM registry, dan update manual pada aplikasi pengetes.
* **Kebutuhan Teknis:** Developer menginginkan *instant hot-reload* lintas package di lingkungan lokal (mengubah `@ds/primitives` langsung berdampak ke aplikasi dokumentasi Next.js tanpa rebuild manual), namun saat diterbitkan ke registry publik, semua referensi dependensi harus terkunci menggunakan SemVer statis murni tanpa jejak symlink monorepo.
* **Pertanyaan Diagnostik:**
  1. Bagaimana mekanisme `workspace:*` (atau `workspace:^`) pada pnpm menyelesaikan isolasi referensi internal selama proses development lokal?
  2. Apa yang dilakukan proses *pack / publish pipeline* pnpm terhadap tag `workspace:` sebelum tarball diunggah ke registry publik, dan apa risiko teknis jika developer menggunakan npm/yarn tradisional tanpa transpiler protokol workspace?
  3. Bagaimana merancang konfigurasi *transpilation/aliasing* modern (misal: Next.js `transpilePackages` vs symlink TS path mapping) agar developer tidak perlu menjalankan watch-compiler yang membebani CPU secara terus-menerus di monorepo?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Infrastruktur Monorepo Enterprise: Dual-Build Pipeline, Subpath Exports, & Strict SemVer Automation

#### Problem Statement
Tim *Core Infrastructure* membutuhkan template monorepo *design system* standar enterprise yang modular, memiliki performa kompilasi tinggi, kebal dari kesalahan resolusi modul node modern, dan memiliki alur rilis sepenuhnya otomatis. Repositori harus memiliki dua internal package: `@ds-enterprise/tokens` (pure design tokens) dan `@ds-enterprise/react` (komponen UI yang mengonsumsi tokens) yang mematuhi spesifikasi modul paling ketat.

#### Requirements
1. **Workspace Architecture:**
   * Inisialisasi arsitektur monorepo berbasis **pnpm workspaces**.
   * Gunakan **Turborepo** untuk orkestrasi pipeline (`build`, `lint`, `typecheck`).
2. **Build & Bundling Engine:**
   * Package `@ds-enterprise/react` harus dikompilasi menggunakan bundler modern (`tsup` atau `Rollup`).
   * Wajib memproduksi format **Dual ESM & CJS** yang disertai *TypeScript Declaration Maps* (`.d.ts` dan `.d.ts.map`).
   * Konfigurasi `package.json` package `@ds-enterprise/react` harus mengimplementasikan subpath exports modern:
     * `.` (root entrypoint)
     * `./button` (atomic entrypoint)
     * Keduanya harus mendukung isolasi CJS, ESM, dan Types secara eksplisit.
3. **Automated Versioning & Publishing Pipeline:**
   * Integrasikan `@changesets/cli`.
   * Konfigurasikan alur GitHub Actions yang memvalidasi *pull request*: memverifikasi bahwa setiap PR yang menyentuh package source memiliki file changeset yang valid, serta job rilis otomatis yang melakukan publish saat branch `main` menerima merge.
4. **Validation Tooling:**
   * Pasang dan jalankan utilitas audit `@arethetypeswrong/cli` (attw) di dalam pipeline untuk memvalidasi bahwa tidak ada cacat arsitektur ESM/CJS atau deklarasi tipe pada build artifact.

#### Constraints
* Dilarang menggunakan opsi `"skipLibCheck": true` pada root maupun sub-package `tsconfig.json`.
* Dilarang menggunakan hoisting legacy (flat `node_modules`).
* Package `@ds-enterprise/tokens` harus berupa dependency internal yang dikonsumsi via protokol `workspace:*`.
* Target Node.js support: Node 18, 20, dan modern bundlers (Next.js App Router, Vite).

#### Expected Output
1. File `pnpm-workspace.yaml` dan root `package.json`.
2. File `turbo.json` dengan isolasi input/output caching yang optimal.
3. File `packages/react/package.json` yang berisi skema conditional exports lengkap (`import`, `require`, `types`) dan konfigurasi peer dependencies.
4. File konfigurasi bundler (`tsup.config.ts` atau `rollup.config.mjs`) untuk `@ds-enterprise/react`.
5. File `.changeset/config.json` dengan konfigurasi *access*, *commit tracking*, dan *linked/fixed packages* yang relevan.
6. Skrip verifikasi CLI menggunakan `attw --pack .` untuk membuktikan status *zero-error* resolusi tipe.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi spesifikasi `package.json` modern (`exports`, `imports`, `module`, `main`, `types`, `sideEffects`).
- [ ] Perbedaan matematis dan fungsional antara format modul ESM (asinkron, static analysis, live bindings) dan CJS (sinkron, dynamic evaluation, execution copy).
- [ ] Risiko fatal *Dual-Package Hazard* terhadap *stateful runtime singletons* dan bagaimana *wrapper pattern* menyelesaikan isu tersebut.
- [ ] Topologi pnpm symlink layout (struktur `.pnpm/`, isolasi dependensi, eliminasi phantom dependencies).
- [ ] Prinsip determinisme build: DAG, *input hashing*, *cache keys*, dan mitigasi flakiness pada Remote Caching Turborepo/Nx.
- [ ] Mekanisme SemVer (Major.Minor.Patch) dan implikasi perubahan *breaking* pada level CSS, Component Props, serta Type Definitions.
- [ ] Cara kerja automated release workflows menggunakan Changesets (changeset generation, status tracking, version bumping, Git tagging, publishing).

### Saya tidak perlu menghafal:
- [ ] Seluruh flag CLI dari Turborepo, pnpm, atau Changesets (cukup memahami konsep flags utama seperti `--filter`, `--parallel`, `--scope`, `--frozen-lockfile`).
- [ ] Sintaks internal file AST rollup/esbuild plugin (cukup memahami lifecycle *resolveId*, *load*, dan *transform*).
- [ ] Standar spesifikasi byte-by-byte dari format kompresi tarball NPM (`.tgz`).
- [ ] Penomoran kode error kompilasi internal TypeScript (seperti TS2742, TS2307) di luar pemahaman atas penyebab arsitekturalnya.

### Saya harus bisa melakukan:
- [ ] Merancang dan mengonfigurasi multi-package monorepo dari nol menggunakan pnpm dan Turborepo.
- [ ] Mengonfigurasi bundler untuk menghasilkan artefak dual distribution (ESM + CJS) dengan *sourcemaps* dan *type definitions* yang valid secara bersamaan.
- [ ] Menulis skema `exports` map pada `package.json` yang lulus validasi tool auditor standar industri (`@arethetypeswrong/cli`).
- [ ] Melakukan troubleshooting dan perbaikan cepat ketika terjadi *phantom dependency* atau kegagalan *transitive dependency resolution*.
- [ ] Mengonfigurasi `sideEffects` flag dengan presisi matematis untuk mengoptimalkan *dead-code elimination* (tree-shaking) bundler hilir.
- [ ] Mengimplementasikan pipeline CI/CD GitHub Actions lengkap untuk automated PR checks, Turborepo remote caching, dan Changeset release governance.