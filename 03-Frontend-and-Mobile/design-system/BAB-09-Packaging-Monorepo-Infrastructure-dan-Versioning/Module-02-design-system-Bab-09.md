# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 09: Packaging, Monorepo Infrastructure, dan Versioning**
**Kategori: 03-Frontend-and-Mobile | Topik: Design System**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Mengonfigurasi dan memvalidasi arsitektur monorepo skala enterprise berbasis `pnpm workspaces` dan orchestrator task modern (`Turborepo` / `Nx`) dengan determinisme build 100%.
- Menangani *Dual-Package Hazard* (ESM vs CJS) secara presisi menggunakan conditional `exports` Node.js tanpa memecah referensi singleton state (seperti React Context).
- Mengimplementasikan pipeline bundling modern yang mampu mempertahankan compiler directives (misal: `"use client"`, `"use server"`) dan menjamin eliminasi kode mati (*tree-shaking*) tingkat lanjut.
- Membangun alur rilis semantik otomatis menggunakan Changesets terintegrasi dengan GitHub Actions, automated provenance publishing, dan verifikasi OIDC ke registry publik/privat.
- Mengonfigurasi remote caching terdistribusi untuk task orchestration build artifacts guna memangkas durasi CI dari hitungan jam menjadi hitungan menit.

---

## 2. Prerequisite

Sebelum memulai modul ini, Anda harus menguasai:
- Pengetahuan mendalam tentang Node.js module resolution algorithm (CommonJS vs ECMAScript Modules).
- Pemahaman praktis mengenai AST (*Abstract Syntax Tree*) bundler (Rollup, esbuild, atau Vite).
- Pengalaman dasar menggunakan Git branching models (Trunk-Based Development) dan GitHub Actions CI/CD workflows.
- Penggunaan package manager tingkat lanjut (`pnpm` store, virtual store, symlink-based `node_modules`).

---

## 3. Concept & Internal Architecture (Mendalam)

Membangun infrastruktur packaging dan monorepo untuk Design System skala enterprise memerlukan pemahaman mendalam tentang bagaimana runtime, compiler, dan package manager berinteraksi.

```
       [ pnpm Workspace Topology ]
                   │
    ┌──────────────┴──────────────┐
    ▼                             ▼
@corp/tokens (No-dep)     @corp/icons (SVG Compiler)
    │                             │
    └──────────────┬──────────────┘
                   ▼
         @corp/primitives (Headless)
                   │
                   ▼
          @corp/react (UI Components)
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
Consumer App A (Next.js)   Consumer App B (Vite SPA)
```

### 3.1. Topology Package Graph & Dependency Resolution
Dalam monorepo berbasis pnpm, dependensi antar-package diatur menggunakan protokol `workspace:*`. Package manager tidak menduplikasi dependencies ke setiap subfolder, melainkan membangun *symlink tree* terisolasi (`node_modules/.pnpm`).

Ketika `@corp/react` bergantung pada `@corp/tokens`:
- Di local workspace, pnpm membuat *junction* / *symlink* langsung ke folder source atau folder `dist` dari `@corp/tokens`.
- Build graph membentuk Directed Acyclic Graph (DAG). Task orchestrator (Turborepo) mengeksekusi proses kompilasi secara paralel berdasarkan topological sort dari DAG ini.

### 3.2. Anatomi Dual-Package Hazard & Subpath Exports
Node.js memperkenalkan field `"exports"` pada `package.json` untuk menggantikan field legacy `"main"` dan `"module"`. Dual-Package Hazard terjadi ketika sebuah library di-load dua kali dalam satu runtime—satu melalui `require()` (CJS) dan satu melalui `import` (ESM).

Dampaknya fatal bagi Design System:
- **State Breakage:** React Context (misalnya `ThemeProvider`) memiliki referensi `React.createContext()` terpisah pada runtime CJS dan ESM. Consumer yang mengimpor via CJS tidak akan mendapatkan state dari Provider yang di-mount via ESM.
- **Bundle Bloat:** Client mengunduh dua salinan kode komponen yang sama persis, meningkatkan First Load JS.

Untuk mengatasi ini, arsitektur modern menggunakan pola **ESM-First with CJS Compatibility Wrapper** atau **Isomorphic Entrypoint**:

```json
{
  "name": "@corp/react",
  "type": "module",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js",
      "require": "./dist/index.cjs"
    },
    "./button": {
      "types": "./dist/button/index.d.ts",
      "import": "./dist/button/index.js",
      "require": "./dist/button/index.cjs"
    },
    "./package.json": "./package.json"
  }
}
```

Urutan keys pada object conditional exports bersifat deterministik: Node.js memeriksa urutan dari atas ke bawah. Field `"types"` **wajib** diletakkan paling atas agar TypeScript Language Server dan compiler (`tsc`) mengenali deklarasi tipe sebelum mengevaluasi target runtime.

### 3.3. Preservasi Directive `"use client"` pada AST Bundler
Komponen Design System sering kali menggunakan event listener, state (`useState`), atau browser API yang mengharuskan mereka menjadi *Client Components* dalam arsitektur React Server Components (RSC/Next.js App Router).

Bundler standar (seperti esbuild murni) sering kali menganggap string `"use client"` di baris paling atas sebagai komentar/dead code dan membuangnya saat minifikasi atau translasi. Arsitektur packaging modern memanfaatkan plugin Rollup/tsup untuk mem-parse AST:
1. Mendeteksi apakah entry file memiliki directive `"use client"`.
2. Mempertahankan directive tersebut di paling atas output chunk yang terisolasi.
3. Memecah output file per komponen (*per-component splitting*) agar komponen server-compatible (seperti Layout statis atau Icons) tidak dipaksa menjadi Client Component oleh consumer.

---

## 4. Why & What

| Dimensi | Pendekatan Monorepo & Packaging Enterprise | Pendekatan Multirepo / Single-Bundle Naif |
| :--- | :--- | :--- |
| **Atomic Changes** | Satu commit/PR dapat memperbarui Token, Komponen, dan Dokumentasi secara atomik. | Butuh orkestrasi koordinasi PR di 5+ repositori berbeda; rawan desinkronisasi. |
| **Dependency Hoisting** | `pnpm` menggunakan content-addressable storage + symlinks, menghemat ruang disk dan mencegah *phantom dependencies*. | `npm` / `yarn v1` melakukan flat hoisting liar yang menyebabkan modul memanggil dependensi yang tidak dideklarasikan. |
| **Distribution Format** | ESM murni + CJS wrapper fallback, hybrid tree-shaking dengan field `"sideEffects": false`. | UMD monolitik atau single-file CJS yang memaksa consumer mengimpor 100% kode library saat hanya butuh 1 Button. |
| **Release Management** | Semantic release terorkestrasi via *Changesets* yang menghitung *semver bump* otomatis dari pull request metadata. | Versi dinaikkan manual di `package.json`, rentan *human error*, changelog sering terlewat atau tidak akurat. |

---

## 5. How (Workflow Detail)

Alur kerja packaging dan rilis dalam monorepo enterprise:

```
[ Developer Branch ]
         │
         ▼
1. Lakukan perubahan kode pada packages/react
         │
         ▼
2. Jalankan `pnpm changeset` -> Pilih bump level & tulis deskripsi
         │
         ▼
3. Push PR -> CI memvalidasi:
   ├── Turbo Lint + Typecheck
   ├── Turbo Build (Remote Cache Hit Check)
   └── AreTheTypesWrong (Attw) validation
         │
         ▼
4. Merge ke `main` branch
         │
         ▼
5. CI Action mendeteksi changeset:
   ├── Jika ada changeset baru -> Buka otomatis PR "Version Packages"
   └── Jika PR "Version Packages" di-merge:
       ├── Eksekusi `changeset publish`
       ├── Generate Git Tag & GitHub Releases
       └── Publish packages ke Registry dengan Provenance Metadata
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem monorepo design system seperti **Jaringan Kereta Logistik Antarkota**:

- **Repository Root:** Terminal Pusat Kontrol Logistik.
- **Packages (`tokens`, `primitives`, `react`):** Gerbong-gerbong kontainer khusus dengan muatan terspesialisasi.
- **pnpm Workspace Symlinks:** Rel kereta yang menghubungkan antar-gerbong secara presisi tanpa memindahkan muatan secara fisik berkali-kali.
- **Turborepo DAG & Remote Cache:** Sistem pelacak radar pintar. Jika gerbong "Tokens" tidak diganti muatannya sejak perjalanan kemarin, sistem tidak akan memeriksa ulang isi gerbong tersebut—langsung salin cap izin lolos (Cache Hit) dari cloud storage.
- **Changesets:** Formulir manifest bea cukai. Setiap pergantian baut atau mesin harus dicatat di kertas segel, yang nantinya akan menentukan apakah kereta mendapat label izin versi Patch, Minor, atau Major.

```
+-------------------------------------------------------------------------+
|                           TURBO ENGINE DAG                              |
|                                                                         |
|      [ @corp/tokens ]                 [ @corp/icons ]                   |
|       Hash: a8f9c1                     Hash: b12d44                     |
|      (CACHE HIT: 0ms)                 (CACHE HIT: 0ms)                  |
|             \                                /                          |
|              \                              /                           |
|               v                            v                            |
|             [ @corp/primitives ]                                        |
|              Hash: 9e4f20 (CACHE MISS: Compiling via tsup...)           |
|                     |                                                   |
|                     v                                                   |
|             [ @corp/react ]                                             |
|              Hash: d33b8a (Waiting for primitives...)                    |
+-------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Konfigurasi Root Monorepo
Struktur workspace root modern.

`pnpm-workspace.yaml`:
```yaml
packages:
  - 'packages/*'
  - 'apps/*'
  - 'tooling/*'
```

`turbo.json`:
```json
{
  "$schema": "https://turbo.build/schema.json",
  "globalDependencies": ["**/.env.*local"],
  "tasks": {
    "topo": {
      "dependsOn": ["^topo"]
    },
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**", ".next/**", "!.next/cache/**"]
    },
    "lint": {
      "dependsOn": ["^topo"]
    },
    "check-types": {
      "dependsOn": ["^topo"]
    },
    "clean": {
      "cache": false
    }
  }
}
```

### 7.2. Implementasi Bundler dengan Preservasi Directive dan Tree-Shaking
Konfigurasi `tsup` pada package `@corp/react`.

`packages/react/tsup.config.ts`:
```typescript
import { defineConfig } from 'tsup';

export default defineConfig((options) => ({
  entry: {
    index: 'src/index.ts',
    button: 'src/components/button/index.ts',
    card: 'src/components/card/index.ts',
    dialog: 'src/components/dialog/index.ts',
  },
  format: ['esm', 'cjs'],
  dts: true,
  splitting: true,
  sourcemap: true,
  clean: !options.watch,
  treeshake: {
    preset: 'recommended',
  },
  minify: !options.watch,
  external: ['react', 'react-dom'],
  esbuildOptions(opts) {
    opts.banner = {
      // Menjamin interoperabilitas client-side directive jika chunk diekstraksi
      js: '"use client";',
    };
  },
  outExtension({ format }) {
    return {
      js: format === 'esm' ? '.js' : '.cjs',
    };
  },
}));
```

`packages/react/package.json`:
```json
{
  "name": "@corp/react",
  "version": "1.4.0",
  "type": "module",
  "sideEffects": false,
  "files": [
    "dist"
  ],
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js",
      "require": "./dist/index.cjs"
    },
    "./button": {
      "types": "./dist/button/index.d.ts",
      "import": "./dist/button/index.js",
      "require": "./dist/button/index.cjs"
    },
    "./card": {
      "types": "./dist/card/index.d.ts",
      "import": "./dist/card/index.js",
      "require": "./dist/card/index.cjs"
    }
  },
  "scripts": {
    "build": "tsup",
    "dev": "tsup --watch",
    "check-types": "tsc --noEmit",
    "check-exports": "attw --pack ."
  },
  "peerDependencies": {
    "react": "^18.0.0 || ^19.0.0",
    "react-dom": "^18.0.0 || ^19.0.0"
  },
  "devDependencies": {
    "@arethetypeswrong/cli": "^0.15.4",
    "react": "^18.3.1",
    "tsup": "^8.1.0",
    "typescript": "^5.4.5"
  }
}
```

### 7.3. Konfigurasi CI Changesets Release dengan OIDC Provenance
`.github/workflows/release.yml`:
```yaml
name: Release Pipeline

on:
  push:
    branches:
      - main

concurrency: ${{ github.workflow }}-${{ github.ref }}

jobs:
  release:
    name: Build, Version & Publish
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
      id-token: write # Wajib untuk npm provenance via Sigstore/OIDC
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Node.js & Corepack
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Install pnpm
        run: corepack enable && corepack prepare pnpm@latest --activate

      - name: Setup Turborepo Remote Cache
        uses: actions/cache@v4
        with:
          path: node_modules/.cache/turbo
          key: turbo-${{ runner.os }}-${{ github.sha }}
          restore-keys: |
            turbo-${{ runner.os }}-

      - name: Install Dependencies
        run: pnpm install --frozen-lockfile

      - name: Validate Module Resolution Types
        run: pnpm run check-exports

      - name: Compile Packages
        run: pnpm turbo run build --filter=./packages/*

      - name: Create Release Pull Request or Publish
        id: changesets
        uses: changesets/action@v1
        with:
          version: pnpm changeset version
          publish: pnpm changeset publish
          commit: 'chore(release): version packages [skip ci]'
          title: 'chore(release): release candidate'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
          NPM_CONFIG_PROVENANCE: true
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario:
Sebuah perusahaan FinTech multi-nasional memiliki 45 aplikasi mikro-frontend (kombinasi Next.js 14 App Router, Webpack 5 legacy, dan Vite). Design System `@corp/core` diimpor oleh semua aplikasi ini.

### Masalah yang Dihadapi:
1. **Broken Theme Context pada SSR:** Pengguna Next.js melaporkan tombol menampilkan mode terang meskipun tema sistem diset ke mode gelap. Investigasi menunjukkan `Next.js Server Engine` mem-bundle versi ESM, sementara plugin otentikasi internal mengimpor versi CJS melalui file kompilasi legacy, mengakibatkan instansiasi dua singleton `ThemeContext`.
2. **Build Time Meledak:** Waktu build CI memakan waktu 48 menit setiap kali developer mengubah file typo komentar pada satu komponen.
3. **Ghost Typings:** TypeScript meloloskan kode di Monorepo, tetapi consumer mendapati pesan `Error: Cannot find module '@corp/core/button' or its corresponding type declarations`.

### Solusi & Implementasi Arsitektural:
1. **Dual-Package Elimination via Isolated Exports:**
   Infrastruktur packaging diubah total ke isolated subpath exports menggunakan format `.mjs` (ESM native) dan `.cjs`. Konfigurasi `package.json` menyertakan conditional mapping strict yang divalidasi menggunakan `@arethetypeswrong/cli`.
2. **Turborepo Remote Caching dengan AWS S3 Endpoint:**
   Diintegrasikan custom remote cache server (`dugite` / self-hosted Turbo remote cache engine) yang menautkan hashing build artifact ke AWS S3 bucket terenkripsi KMS. Cache key diturunkan dari hash konten Git, dependency lockfile, dan env variable `NODE_ENV`.
3. **Hasil Metrik:**
   - **CI Build Duration:** Turun drastis dari 48 menit menjadi 3 menit 12 detik (penurunan 93.3% berkat cache hit).
   - **Bundle Footprint:** Ukuran JS konsumen berkurang 42% karena eliminasi dead code berhasil (per-component subpath + tree-shaking flags aktif).
   - **Zero Context Desync:** Dual-Package Hazard tuntas tereliminasi 100%.

---

## 9. Trade-offs

| Pendekatan / Teknologi | Keuntungan (Pros) | Biaya & Konsekuensi (Cons) | Pertimbangan Biaya (Cost) & Latensi |
| :--- | :--- | :--- | :--- |
| **Separate Subpath Compilation (misal `@corp/react/button`)** | Mencegah dynamic bundle bloating; consumer hanya memuat file JS komponen yang diimpor tanpa overhead. | Konfigurasi bundler jauh lebih kompleks; harus mengelola ratusan deklarasi `types` dan output mapping di `package.json`. | Meningkatkan build time awal library (+30%), namun menurunkan latency load time aplikasi consumer. |
| **Dual Bundling (ESM + CJS Output)** | Kompatibilitas universal (legacy Node/Webpack 4 bisa pakai CJS, bundler modern pakai ESM). | Ukuran package di registry npm menjadi 2x lipat lebih besar. Risiko dual-package hazard jika runtime salah me-resolve. | Biaya storage artifact di npm/Nexus bertambah; risiko runtime context split jika konfigurasi salah. |
| **Remote Cache Orchestration** | Waktu build di CI sangat singkat (hanya compile yang berubah). Developer lokal mendapat instant build via cache cloud. | Membutuhkan setup storage backend terdistribusi berkecepatan tinggi (S3/GCS); potensi cache poisoning jika hashing rule buruk. | Biaya egress jaringan cloud jika artifact build berukuran multi-gigabyte. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Salah Menentukan Urutan Kunci `types` pada `exports`
*Gejala:* TypeScript melempar error `Could not find a declaration file for module`, meskipun file `.d.ts` ada di dalam folder `dist`.
*Penyebab:* Field `"types"` diletakkan setelah `"import"` atau `"require"`. Node.js resolver mengabaikan `"types"` jika kunci lain di atasnya sudah match.
*Solusi:* Letakkan `"types"` selalu pada urutan **pertama**:
```json
// SALAH
"exports": {
  ".": {
    "import": "./dist/index.js",
    "types": "./dist/index.d.ts"
  }
}

// BENAR
"exports": {
  ".": {
    "types": "./dist/index.d.ts",
    "import": "./dist/index.js"
  }
}
```

### Mistake 2: Missing `"sideEffects": false`
*Gejala:* Webpack/Rollup milik consumer memasukkan seluruh library ke dalam production bundle, meskipun consumer hanya mengimpor satu helper function kecil.
*Penyebab:* Bundler mengasumsikan file JS memiliki efek samping level root (misal mengeksekusi window global atau inject CSS seketika saat diimpor).
*Solusi:* Beri tahu bundler secara eksplisit:
```json
{
  "sideEffects": [
    "**/*.css",
    "**/*.scss"
  ]
}
```

### Mistake 3: Kehilangan Directive `"use client"` Akibat Code Minification
*Gejala:* Next.js App Router gagal build dengan error: `React Hook "useState" is called in a Server Component`.
*Penyebab:* Tooling minifikasi menghapus directive string literal `"use client"` karena menganggapnya ekspresi tanpa assignment.
*Solusi:* Gunakan custom banner injector pada bundler atau plugin khusus (seperti `esbuild-plugin-use-client` atau config `rollup-plugin-preserve-directives`).

---

## 11. Best Practices (Production Checklist)

- [ ] **Gunakan `pnpm --filter`:** Isolasi proses build dan testing hanya pada sub-package yang mengalami diff git.
- [ ] **Pasang Validasi `@arethetypeswrong/cli`:** Jalankan tool ini di CI sebelum rilis untuk memastikan consumer dengan resolusi `node16`, `nodenext`, dan `bundler` dapat mengonsumsi TypeScript types tanpa galat.
- [ ] **Aktifkan NPM Provenance:** Setel `NPM_CONFIG_PROVENANCE: true` di GitHub Actions untuk menjamin keaslian build yang terikat secara kriptografis ke commit SHA repositori.
- [ ] **Isolasi External Dependencies:** Jangan pernah mem-bundle `react`, `react-dom`, atau `@types/react` ke dalam output `dist`. Wajib dideklarasikan di `peerDependencies` dan `devDependencies`.
- [ ] **Enforce Changesets via GitHub Bot:** Pasang PR check yang mewajibkan developer menambahkan berkas changeset (`.changeset/*.md`) jika terdapat modifikasi pada logic di folder `packages/*`.
- [ ] **Semver Guard:** Gunakan automated tooling untuk memverifikasi apakah ada breaking API changes pada file export publik (misalnya menggunakan `ts-prune` atau custom API extractor) sebelum menaikkan versi.

---

## 12. Hands-on Practice

Buatlah workspace monorepo minimalis namun berkemampuan enterprise yang mengimplementasikan seluruh mekanisme packaging, validasi types, dan bundling.

### Direktori Target:
Simpan seluruh artefak praktikum ini di:
`hands-on/m02/`

### Langkah Praktikum:

#### Langkah 1: Setup Workspace & Dependencies Root
Eksekusi di terminal:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
pnpm init
git init
```

Buat file `pnpm-workspace.yaml`:
```yaml
packages:
  - 'packages/*'
```

Install tools root monorepo:
```bash
pnpm add -Dw turbo typescript @changesets/cli
pnpm changeset init
```

#### Langkah 2: Setup Package Primitives Token
```bash
mkdir -p packages/tokens/src
```

`packages/tokens/package.json`:
```json
{
  "name": "@m02/tokens",
  "version": "1.0.0",
  "type": "module",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js"
    }
  },
  "scripts": {
    "build": "tsc"
  },
  "devDependencies": {
    "typescript": "^5.4.5"
  }
}
```

`packages/tokens/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "declaration": true,
    "outDir": "./dist",
    "strict": true
  },
  "include": ["src"]
}
```

`packages/tokens/src/index.ts`:
```typescript
export const colors = {
  brandPrimary: '#0052FF',
  brandSecondary: '#0A0B0D',
  surfaceSuccess: '#05B169',
  surfaceDanger: '#DF2020',
} as const;

export type Colors = typeof colors;
```

#### Langkah 3: Setup Package React dengan Bundling Lanjutan (tsup)
```bash
mkdir -p packages/react/src/components
```

`packages/react/package.json`:
```json
{
  "name": "@m02/react",
  "version": "1.0.0",
  "type": "module",
  "sideEffects": false,
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js",
      "require": "./dist/index.cjs"
    },
    "./button": {
      "types": "./dist/components/button.d.ts",
      "import": "./dist/components/button.js",
      "require": "./dist/components/button.cjs"
    }
  },
  "scripts": {
    "build": "tsup src/index.ts src/components/button.tsx --format esm,cjs --dts --splitting",
    "check:exports": "attw --pack ."
  },
  "dependencies": {
    "@m02/tokens": "workspace:*"
  },
  "peerDependencies": {
    "react": "^18.0.0 || ^19.0.0"
  },
  "devDependencies": {
    "@arethetypeswrong/cli": "^0.15.4",
    "react": "^18.3.1",
    "@types/react": "^18.3.3",
    "tsup": "^8.1.0",
    "typescript": "^5.4.5"
  }
}
```

`packages/react/src/components/button.tsx`:
```tsx
'use client';

import React from 'react';
import { colors } from '@m02/tokens';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'danger';
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', style, children, ...props }, ref) => {
    const backgroundColor = variant === 'primary' ? colors.brandPrimary : colors.surfaceDanger;
    return (
      <button
        ref={ref}
        style={{
          backgroundColor,
          color: '#ffffff',
          padding: '8px 16px',
          borderRadius: '4px',
          border: 'none',
          cursor: 'pointer',
          ...style,
        }}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
```

`packages/react/src/index.ts`:
```typescript
export * from './components/button';
```

#### Langkah 4: Validasi & Kompilasi DAG Monorepo
Jalankan di root `hands-on/m02/`:
```bash
pnpm install
pnpm --filter @m02/tokens run build
pnpm --filter @m02/react run build
pnpm --filter @m02/react run check:exports
```
Amati output dari `attw`. Seluruh matrix loader (`node16 (import)`, `node16 (require)`, `bundler`) harus menunjukkan status centang hijau tanpa komplikasi resolution.

---

## 13. Exercise

### Level Easy
Tambahkan subpath export `./card` pada `@m02/react` yang menerima prop `elevation: 'low' | 'high'`. Lakukan konfigurasi build pada `tsup` agar menghasilkan output `.js`, `.cjs`, dan `.d.ts` khusus untuk path tersebut.

### Level Medium
Konfigurasikan script verifikasi guard di root monorepo yang memindai semua package di direktori `packages/*`. Script harus gagal (exit code non-zero) jika ada file `package.json` yang memuat dependency `react` di dalam block `dependencies`, bukan di `peerDependencies`.

### Level Hard
Buat custom esbuild/Rollup plugin untuk konfigurasi build `@m02/react` yang secara dinamis memeriksa AST file. Jika komponen menggunakan state/effects React (`useState`, `useEffect`, `useRef`), suntikkan banner `'use client';` secara otomatis. Sebaliknya, jika file hanya berupa rendering fungsi murni statis, cegah penyuntikan directive agar komponen tetap beroperasi murni sebagai React Server Component (RSC).

---

## 14. Challenge

**Skenario Rancang Bangun:**
Arsitektur Design System Anda berpindah dari model monolitik menjadi model *fine-grained atomic packages*:
- `@corp/theme`
- `@corp/button`
- `@corp/modal`
- `@corp/typography`

Tiap package harus dirilis secara independen ke registry npm privat, namun mereka saling berbagi konfigurasi compiler tsup yang sama via internal tooling package (`@corp/config-tsup`).

**Persyaratan Tantangan:**
1. Desain monorepo structure lengkap dengan lifecycle task Turborepo yang memastikan bahwa jika `@corp/theme` berubah, hanya `@corp/button` dan package yang bergantung padanya yang di-rebuild serta di-publish via Changesets.
2. Buat mekanisme agar versi lokal antar-package tetap tersinkronisasi menggunakan `workspace:^` saat dev mode, namun ketika di-publish ke registry privat, string tersebut ditransformasi menjadi rentang versi Semver statis murni (`^1.2.0`).
3. Konfigurasikan strategi Remote Caching menggunakan GitHub Actions Cache Storage Backend tanpa perlu membayar layanan SaaS pihak ketiga.
4. Buat skema automated roll-back canary release jika deployment version package mengalami anomali saat integrasi pengujian consumer micro-frontend.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic
1. Apa fungsi utama field `"sideEffects": false` di dalam file `package.json` Design System?
2. Mengapa urutan mapping keys di dalam field `"exports"` pada `package.json` sangat krusial?
3. Apa perbedaan esensial antara resolusi paket via symlink di `pnpm` dibanding algoritma hoisting datar (flat hoisting) di `npm v6`?
4. Mengapa dependensi utama seperti `react` dan `react-dom` harus dikategorikan sebagai `peerDependencies` pada package UI library?
5. Mengapa file `.d.ts` harus di-generate terpisah untuk CJS dan ESM dalam skenario conditional exports tertentu?

### 15.2. Pertanyaan Intermediate
6. Jelaskan bagaimana *Dual-Package Hazard* secara internal dapat memecah fungsionalitas React Context Provider pada aplikasi consumer!
7. Bagaimana cara Turborepo menentukan apakah suatu task build di monorepo menghasilkan *Cache Hit* atau *Cache Miss*?
8. Mengapa directive `"use client"` dapat hilang saat proses kompilasi library oleh bundler tertentu, dan bagaimana cara memitigasinya?
9. Apa fungsi file manifest `.changeset/*.md` dan bagaimana siklus hidupnya hingga package terbit di registry?
10. Bagaimana cara kerja `@arethetypeswrong/cli` dalam memvalidasi integritas package types?

### 15.3. Skenario Kasus Produksi
11. **Kasus 1:** Sebuah aplikasi consumer menggunakan Vite dan Next.js secara bersamaan. Vite berhasil me-resolve `@corp/react/button`, namun Next.js App Router gagal dengan error `Package path ./button is not exported from package @corp/react`. Tunjukkan di mana letak kesalahan konfigurasi `package.json` dan berikan kodenya.
12. **Kasus 2:** Pada pipeline CI, task `turbo run build` selalu menghasilkan *Cache Miss* 100% pada semua package meskipun tidak ada perubahan kode source di commit baru. Identifikasi variabel apa saja yang mungkin memicu invalidasi cache Turborepo tersebut!
13. **Kasus 3:** Developer mempublikasikan versi baru dari package `@corp/primitives`. Ternyata mereka lupa mem-bundle folder `dist/` sebelum menjalankan `npm publish` secara manual. Bagaimana arsitektur monorepo enterprise mencegah human error ini secara total dan terotomatisasi?

---

## Jawaban Quiz Evaluasi Pemahaman

### Kunci Jawaban Basic
1. **Fungsi `"sideEffects": false`:** Memberi petunjuk optimasi kepada bundler (Webpack, Rollup, Vite) bahwa file di package ini murni dan tidak memodifikasi global namespace runtime atau mengeksekusi efek samping seketika saat diimpor, sehingga bundler diizinkan membuang modul yang tidak terpakai (*tree-shaking*).
2. **Urutan Keys di `"exports"`:** Node.js mengevaluasi object conditional exports secara sekuensial (top-to-bottom) dan memilih kecocokan pertama. Jika kunci `"import"` ditaruh di atas `"types"`, compiler TypeScript mungkin mengabaikan `"types"` sehingga deklarasi tipe tidak terbaca.
3. **Symlink pnpm vs Flat Hoisting npm:** pnpm membuat virtual store (`.pnpm`) berbasis hash konten dan menghubungkan packages via symlink, mencegah *phantom dependencies* (mengimpor package yang tidak dideklarasikan di `package.json`). npm mem-flatten seluruh dependency tree ke root `node_modules`, membuat dependensi transien dapat diakses secara tidak sengaja.
4. **`react` di `peerDependencies`:** Memastikan consumer menggunakan satu instansiasi React runtime yang sama. Jika React dimasukkan ke `dependencies`, bundler consumer bisa menduplikasi runtime React, merusak hook rules (error: *"Hooks can only be called inside the body of a function component"*).
5. **Generasi `.d.ts` Ganda:** TypeScript memiliki mode resolusi ketat (`node16`/`nodenext`). Tipe yang diimpor via `require` (CommonJS) harus mematuhi aturan pembungkusan tipe yang berbeda dibanding native ESM (`import`), menghindari kesalahan resolusi typings pada module boundary.

### Kunci Jawaban Intermediate
6. **Mekanisme Dual-Package Hazard pada React Context:** Node.js menganggap module CJS dan ESM sebagai instance terpisah. `React.createContext()` yang dipanggil di CJS akan membuat Symbol unik `A`, sedangkan di ESM akan membuat Symbol unik `B`. Jika Provider dibungkus menggunakan konteks dari instance CJS sementara consumer `useContext` membaca dari instance ESM, consumer akan selalu mendapatkan default fallback value karena identitas Symbol memory Context tersebut tidak sama.
7. **Kalkulasi Cache Hash Turborepo:** Turborepo menghitung cryptographic hash berdasarkan:
   - Konten semua file yang cocok dengan glob `inputs` pada task.
   - Hash dari dependencies package internal (transitive workspace hash).
   - Nilai dari `globalDependencies` (misal hash konfigurasi global/lockfile).
   - String key-value dari environment variables yang didefinisikan di `env` array.
   Jika hash identik dengan hash yang tersimpan di cache lokal/remote, eksekusi task dilewati dan artifact di direktori `outputs` langsung di-restore.
8. **Hilangnya Directive `"use client"`:** Engine compiler dasar (seperti esbuild core) memandang directive strings di awal module sebagai dangling expressions yang tidak memiliki side-effect dalam semantics JS standar saat minifikasi diaktifkan. Mitigasinya adalah menggunakan opsi `banner` pada tsup/esbuild untuk memaksa penulisan directive, atau menggunakan Rollup plugin `rollup-plugin-preserve-directives` yang memetakan directive AST nodes ke chunks keluaran.
9. **Siklus Hidup Changeset:** Developer menjalankan `pnpm changeset`, memilih package yang diubah, memilih tingkat bump (major/minor/patch), dan menulis ringkasan changelog. CLI membuat file markdown acak di `.changeset/`. File ini di-commit. Di CI branch `main`, Action `changesets/action` membaca file-file ini, mengakumulasi perubahan versi di `package.json`, meng-update `CHANGELOG.md`, menghapus file changeset yang sudah diaplikasikan, dan membuat commit/PR rilis.
10. **Cara Kerja `@arethetypeswrong/cli`:** Mengunduh atau membaca *tarball* package, mensimulasikan berbagai macam lingkungan consumer (Node10, Node16 CJS, Node16 ESM, Bundler resolution), dan melacak apakah setiap subpath export dapat menemukan file deklarasi TypeScript (`.d.ts`) yang valid serta memeriksa kecocokan representasi type module format (CJS vs ESM syntax mismatch).

### Kunci Jawaban Skenario Kasus Produksi
11. **Perbaikan Subpath Export:**
    Penyebabnya adalah subpath `./button` belum dipetakan secara eksplisit pada block `exports` di `package.json`, sedangkan Next.js mengharuskan enkapsulasi export yang ketat.
    ```json
    {
      "exports": {
        ".": {
          "types": "./dist/index.d.ts",
          "import": "./dist/index.js",
          "require": "./dist/index.cjs"
        },
        "./button": {
          "types": "./dist/components/button.d.ts",
          "import": "./dist/components/button.js",
          "require": "./dist/components/button.cjs"
        }
      }
    }
    ```
12. **Investigasi Cache Invalidation Turborepo:**
    Penyebab cache miss 100% konsisten meliputi:
    - File `.git` atau timestamp generator yang tidak sengaja masuk dalam `inputs` task.
    - Deklarasi environment variable yang tidak stabil di `globalDependencies` (misalnya string timestamp dinamis `BUILD_TIME=Date.now()`).
    - Modifikasi terselubung pada root lockfile `pnpm-lock.yaml` saat CI berjalan (misalnya CI menjalankan `pnpm install` tanpa flag `--frozen-lockfile`).
    - Cache remote tidak terautentikasi (token otentikasi remote cache expired/hilang, sehingga fallback ke local disk kosong pada ephemeral CI runner).
13. **Pencegahan Human Error Penerbitan:**
    - Hilangkan izin akses write manual engineer ke registry npm dengan hanya mengizinkan publishing lewat mesin CI menggunakan token OIDC terverifikasi.
    - Gunakan lifecycle script npm `"prepublishOnly": "pnpm build && pnpm check-exports"` di dalam file `package.json` tiap package sehingga publish lokal akan otomatis gagal jika folder `dist/` belum terkompilasi atau validasi types bermasalah.
    - Konfigurasikan whitelist field `"files": ["dist"]` di `package.json` untuk menjamin artifact yang dikirim ke registry terisolasi hanya pada compiled output, bukan raw code development.

---

## 16. Summary

Mengelola infrastruktur packaging dan monorepo skala enterprise untuk Design System bukan sekadar menyatukan beberapa folder komponen ke dalam satu repository. Arsitektur ini menuntut disiplin rekayasa tingkat tinggi:

1. **Topologi Workspace & Orkes:** Menggunakan `pnpm` mengamankan isolasi dependensi secara deterministik, sementara orchestrator seperti `Turborepo` menjamin skalabilitas build pipeline melalui topological execution graphs dan remote caching.
2. **Standardisasi Module Resolution:** Memanfaatkan conditional exports Node.js secara benar mengeliminasi Dual-Package Hazard dan mengamankan integritas runtime singleton seperti React Context, sekaligus mengoptimalkan konsumsi bundle via subpath imports.
3. **Preservasi Metadata Compiler:** Arsitektur bundling modern harus sadar-AST untuk mempertahankan boundaries React Server Components (`"use client"`) dan mendukung eliminasi kode mati secara agresif via `"sideEffects": false`.
4. **Automasi Tata Kelola Semantik:** Otomasi rilis terdistribusi berbasis Changesets menghilangkan risiko kesalahan manusia, mendokumentasikan changelog secara akurat, dan mengamankan rantai pasok software menggunakan supply-chain provenance publishing.