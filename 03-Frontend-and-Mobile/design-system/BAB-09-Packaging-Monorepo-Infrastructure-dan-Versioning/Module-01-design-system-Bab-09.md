# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik:** Design System
*   **Bab:** 09 — Distribution, Tooling, & Infrastructure
*   **Modul:** 01 — Packaging, Monorepo Infrastructure, & Versioning
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** Pemahaman mendalam tentang Node.js runtime, TypeScript compiler internals (`tsc`), Git workflow, NPM/PNPM workspace architecture, dan Continuous Integration/Continuous Deployment (CI/CD).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1.  **Merancang dan Mengonfigurasi Infrastruktur Monorepo Skala Enterprise:** Mengimplementasikan PNPM Workspaces dan Turborepo untuk caching terdistribusi, eksekusi pipeline paralel, dan isolasi dependensi yang ketat (*phantom dependency elimination*).
2.  **Menguasai Paradigma Modern JavaScript Packaging:** Mengonfigurasi `package.json` modern menggunakan conditional `exports`, `typesVersions`, target dual-module (ESM & CJS), serta memvalidasi kesesuaian output bundle terhadap standar Node.js subpath resolution.
3.  **Mengotomatisasi Semantic Versioning & Rilis Paket Terdistribusi:** Mengintegrasikan `@changesets/cli` untuk mengelola *version lifecycle*, changelog generation, dan multi-package version bumping (Fixed vs Independent modes) melalui GitHub Actions.
4.  **Mencegah Dependency Duplication & Dual-Package Hazard:** Mengidentifikasi dan memitigasi isu state duplication pada React contexts yang diakibatkan oleh resolusi CJS/ESM ganda dalam consumer bundlers.
5.  **Menerapkan Strategi Registry Publishing & Keamanan Supply Chain:** Mengamankan publikasi paket ke Private/Public NPM Registry menggunakan Provenance Attestations (SLSA level 3), Two-Factor Authentication via OIDC tokens, dan audit siklus dependensi otomatis.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: The Distributed Kernel vs Consumer Modules
Sebuah Design System enterprise tidak boleh dipandang sekadar sebagai kumpulan komponen React, melainkan sebagai sebuah *operating system kernel* yang didistribusikan ke puluhan hingga ratusan aplikasi konsumen (consumer apps). 

```
+-------------------------------------------------------------------+
|                        DESIGN SYSTEM REPO                         |
|   [Tokens] ----> [Core Primitives] ----> [Component Library]      |
+-------------------------------------------------------------------+
                                  │  Build & Package Pipeline
                                  ▼
+-------------------------------------------------------------------+
|                  DISTRIBUTION LAYER (NPM Registry)                |
|           ESM (Modern Bundlers)  │  CJS (SSR/Legacy Node)         |
+-------------------------------------------------------------------+
             ▲                                        ▲
             │ Resolution                             │ Resolution
+----------------------------+        +-----------------------------+
|    CONSUMER APPLICATION A  |        |    CONSUMER APPLICATION B   |
|     (Next.js App Router)   |        |      (Vite SPA Client)      |
+----------------------------+        +-----------------------------+
```

Jika Anda merilis kode yang salah di level aplikasi, dampaknya terlokalisasi pada satu domain bisnis. Namun, jika Anda mengekspor artefak yang rusak (*malformed export map*, *missing type definitions*, atau *state fragmentation via dual-module hazard*) dari repositori Design System:
*   Pipeline CI/CD dari seluruh tim produk akan lumpuh (*blast radius* global).
*   Proses *dead-code elimination* (Tree-shaking) pada bundler konsumen akan gagal, mengakibatkan regresi ukuran bundel (*bundle bloat*) secara masif.
*   Resolusi tipe TypeScript konsumen melambat akibat evaluasi deklarasi rekursif yang tidak terisolasi.

### The Shift from Monolith to Decoupled Monorepo
Mindset seorang arsitek infrastruktur Design System menuntut pergeseran dari "menggabungkan semua komponen dalam satu bundle besar" menjadi "memecah dependensi secara modular (atomic packaging) namun dikelola dalam satu kesatuan orkestrasi (*monorepo single-pane-of-glass*)". Anda harus memperlakukan dependensi internal antar paket dalam workspace dengan tingkat kedisiplinan yang sama persis seperti memperlakukan paket pihak ketiga (*third-party packages*).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram komprehensif yang memetakan relasi dependensi monorepo, aliran pipeline eksekusi Turborepo, dan arsitektur artefak bundel ganda (ESM + CJS) dengan mapping TypeScript definitions:

```
========================================================================================
                          MONOREPO ARCHITECTURE GRAPH (PNPM)
========================================================================================

    [ @acme/tokens ]  <─────────── (workspace:*)
           ▲
           │ (workspace:*)
    [ @acme/primitives ]
           ▲
           │ (workspace:*)
    [ @acme/components ] ◄──────── (workspace:*) ────── [ @acme/docs (Apps) ]
           ▲
           │ (workspace:*)
    [ @acme/theme-plugin ]

========================================================================================
                          TURBOREPO TASK ORCHESTRATION PIPELINE
========================================================================================

   Repo Level: `turbo run build`
   
   Cache Miss                                             Cache Hit
   ┌─────────────────┐                                    ┌─────────────────┐
   │  @acme/tokens   │ ───► Compile TS to CSS/JSON ─────► │ Saved to Cache  │
   └────────┬────────┘                                    └─────────────────┘
            │ Depends On (^)
            ▼
   ┌─────────────────┐
   │@acme/primitives │ ───► tsup compile (ESM/CJS)  ────► [ Hash: a8f7... ]
   └────────┬────────┘
            │ Depends On (^)
            ▼
   ┌─────────────────┐
   │@acme/components │ ───► tsup + rollup dts emit  ────► [ Hash: b9e2... ]
   └─────────────────┘

========================================================================================
                      DUAL-PACKAGE COMPILATION & CONSUMPTION FLOW
========================================================================================

 Source Code (TSX)
       │
       ├───► [ tsup Engine ]
       │            │
       │            ├───► Output ESM:  dist/index.mjs  (import statements, pure)
       │            └───► Output CJS:  dist/index.cjs  (require/exports syntax)
       │
       └───► [ tsc / tsup-dts Engine ]
                    │
                    ├───► Output DTS:  dist/index.d.mts (Types for ESM)
                    └───► Output DTS:  dist/index.d.cts (Types for CJS)

 Consumer Bundler Resolution Matrix:
 ---------------------------------------------------------------------------------------
 | Target Environment   | Conditional Exports Field Match | Resolved Physical File     |
 |----------------------|---------------------------------|----------------------------|
 | Vite / Webpack 5+    | "import"                        | dist/index.mjs             |
 | Node.js require()    | "require"                       | dist/index.cjs             |
 | TypeScript 5+ (Bundler)| "types" (nested under import) | dist/index.d.mts           |
 | TypeScript 5+ (Node16)| "types" (nested under require)| dist/index.d.cts           |
 ---------------------------------------------------------------------------------------
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Hard Links, Symlinks, & Content-Addressable Storage (PNPM)
PNPM tidak menggunakan skema flat-directory seperti NPM v3/Yarn v1 yang rentan terhadap *phantom dependencies* (sebuah kondisi di mana kode mengimpor paket yang tidak dideklarasikan di `package.json`, tetapi kebetulan terpasang oleh paket lain). 
*   **Content-Addressable Storage (CAS):** Semua berkas dependensi disimpan di global store (`~/.local/share/pnpm/store`). Berkas yang identik di berbagai proyek hanya disimpan satu kali di disk.
*   **Symlink Virtual Store:** Direktori `node_modules` di root dan workspace packages menggunakan nested symlink structure ke `node_modules/.pnpm`.
*   Jika `@acme/components` membutuhkan `clsx`, tetapi tidak mendeklarasikannya di `package.json` miliknya, Node.js resolution algorithm akan secara fisik gagal menemukan `clsx` pada direktori isolated symlink `@acme/components/node_modules/`, mencegah *implicit dependency leakage*.

### 2. Task Hashing & Dependency Graphs (Turborepo Engine)
Turborepo merepresentasikan seluruh repositori sebagai sebuah Directed Acyclic Graph (DAG). Saat menjalankan perintah `turbo run build`:
1.  **Hash Computation:** Hash 128-bit dihitung untuk setiap task berdasarkan:
    *   Hash hash berkas sumber (menggunakan git tracking status).
    *   Hash dari task dependencies yang dideklarasikan pada `pipeline.<task>.dependsOn`.
    *   Variabel lingkungan (Environment Variables) yang dispesifikasikan di `env`.
    *   Konfigurasi `package.json` dan `turbo.json`.
2.  **Fingerprinting:** Jika Hash cocok dengan artefak yang ada di cache lokal (`node_modules/.cache/turbo`) atau Turborepo Remote Cache Server, Turborepo melewatkan (*replays*) proses kompilasi, menyalin stdout/stderr, dan merekonstruksi direktori output (`dist/`) langsung dari arsip tarball cache dalam hitungan milidetik.

### 3. The Resolution Mechanics of `exports` Map
Sejak Node.js v12.7.0 dan distandarisasi pada runtime modern, field `"main"` dan `"module"` telah didepresiasi demi conditional `"exports"`. Mekanisme internal resolusinya mengevaluasi urutan kunci array secara deterministic:

```json
{
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.mjs",
      "require": "./dist/index.cjs"
    },
    "./button": {
      "types": "./dist/button.d.ts",
      "import": "./dist/button.mjs",
      "require": "./dist/button.cjs"
    }
  }
}
```
*   **Subpath Encapsulation:** File apa pun yang *tidak* secara eksplisit didefinisikan dalam field `"exports"` **tidak dapat diakses** oleh consumer. Jika consumer mencoba mengeksekusi `import { InternalHelper } from '@acme/components/dist/internal-helper.js'`, runtime Node.js/bundler akan melempar error: `ERR_PACKAGE_PATH_NOT_EXPORTED`.
*   **Order Sensitivity:** Objek dievaluasi dari atas ke bawah. Field `"types"` **wajib** diletakkan sebelum `"import"` atau `"require"`. Jika diletakkan di bawah, compiler TypeScript dengan opsi `moduleResolution: "node16"` atau `"nodenext"` akan mengabaikan type definitions tersebut.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Dual-Package Hazard (DPH)
Dual-Package Hazard terjadi ketika sebuah aplikasi secara tidak sengaja memuat representasi ECMAScript Module (ESM) dan CommonJS (CJS) dari library yang sama ke dalam memory heap runtime yang sama secara simultan.

#### Teori Kegagalan:
Bayangkan modul React Context di `@acme/primitives/theme-context`:
```typescript
// theme-context.ts
import React from 'react';
export const ThemeContext = React.createContext({ theme: 'light' });
```
Jika aplikasi consumer menggunakan konfigurasi kompilasi heterogen:
1.  Aplikasi utama (misal: Next.js Client Component bundle) mengimpor file via ESM: `import { ThemeContext } from '@acme/primitives'`. Ini memuat instance `dist/index.mjs` ke memory, menciptakan `ContextInstance_A`.
2.  Sebuah dependensi eksternal lain atau SSR render path mengimpor via CJS: `const { ThemeContext } = require('@acme/primitives')`. Ini memuat instance `dist/index.cjs` ke memory, menciptakan `ContextInstance_B`.
3.  Komponen `<ThemeProvider>` membungkus children menggunakan `ContextInstance_A.Provider`, namun consumer membaca data via hook `useTheme()` yang merujuk pada `ContextInstance_B`.
4.  **Hasil:** Context bernilai `undefined` atau default fallback. Terjadi silent crash atau UI flickering yang sangat sulit dilacak.

#### Mitigasi Teknis:
1.  **State Isolation via CJS Wrapper Pattern:** Menjaga runtime singleton state tetap berada di satu format (biasanya CJS) dan ESM hanya bertindak sebagai wrapper murni yang mengekspor ulang singleton tersebut.
2.  **Pure ESM Shift:** Mentransformasi seluruh ekosistem internal monorepo menjadi ESM-Only package (`"type": "module"`), memaksa consumer modern bundler untuk tidak pernah meng-fallback ke CJS resolution.

### Tree-Shaking Mechanics: `sideEffects` Flag Optimization
Tree-shaking bukanlah fitur compiler TypeScript, melainkan fungsionalitas optimasi AST (Abstract Syntax Tree) dead-code elimination dari bundler (Rollup, Webpack, esbuild).
*   Jika bundler melihat statement `import { Button } from '@acme/components'`, ia membaca seluruh berkas entry point.
*   Jika berkas entry point mengimpor modul lain yang memiliki *side effects* (misalnya: memodifikasi `window`, mengeksekusi Polyfill, menyisipkan global CSS via JavaScript injection `import './styles.css'`), bundler **dilarang** membuang modul tersebut dari dependency graph akhir, meskipun modul tersebut tidak pernah dipanggil secara langsung oleh aplikasi consumer.
*   Dengan mendeklarasikan:
    ```json
    "sideEffects": [
      "**/*.css"
    ]
    ```
    Kita memberikan jaminan matematis kepada bundler bahwa modul TypeScript/JavaScript di dalam package bersifat deterministik murni (*pure functions* / *pure classes*). Modul yang tidak direferensikan dapat secara aman dieliminasi 100% dari production chunk.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah setup fundamental multi-package monorepo menggunakan PNPM Workspace, Turborepo, dan Tsup.

### 1. Root Configuration: `pnpm-workspace.yaml`
```yaml
packages:
  - "packages/*"
  - "apps/*"
```

### 2. Root Configuration: `turbo.json`
```json
{
  "$schema": "https://turbo.build/schema.json",
  "globalDependencies": ["**/.env.*local"],
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**", ".next/**", "!.next/cache/**"]
    },
    "lint": {
      "dependsOn": ["^build"]
    },
    "type-check": {
      "dependsOn": ["^build"]
    },
    "clean": {
      "cache": false
    }
  }
}
```

### 3. Leaf Package Implementation: `packages/tokens`
#### `packages/tokens/package.json`
```json
{
  "name": "@acme/tokens",
  "version": "1.2.0",
  "private": false,
  "type": "module",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js"
    }
  },
  "scripts": {
    "build": "tsup",
    "clean": "rm -rf dist .turbo"
  },
  "devDependencies": {
    "tsup": "^8.0.2",
    "typescript": "^5.4.5"
  }
}
```

#### `packages/tokens/src/index.ts`
```typescript
export const colors = {
  brandPrimary: '#0052CC',
  brandSecondary: '#0747A6',
  neutral100: '#F4F5F7',
  neutral900: '#091E42',
} as const;

export const spacing = {
  sm: '4px',
  md: '8px',
  lg: '16px',
  xl: '24px',
} as const;

export type Colors = typeof colors;
export type Spacing = typeof spacing;
```

#### `packages/tokens/tsup.config.ts`
```typescript
import { defineConfig } from 'tsup';

export default defineConfig({
  entry: ['src/index.ts'],
  format: ['esm'],
  dts: true,
  clean: true,
  minify: true,
  treeshake: true,
  sourcemap: true,
});
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Mari kita bedah secara granular file konfigurasi inti packaging dari `packages/tokens/tsup.config.ts` dan relasi dependensinya:

```typescript
1: import { defineConfig } from 'tsup';
```
*   **Baris 1:** Mengimpor helper strongly-typed `defineConfig` dari `tsup` (bundler berbasis esbuild ultra-cepat) untuk memastikan auto-complete dan type safety pada level konfigurasi build.

```typescript
3: export default defineConfig({
4:   entry: ['src/index.ts'],
5:   format: ['esm'],
```
*   **Baris 4:** Menentukan entry point esensial. Build pipeline menolak absolute pathing arbitrary untuk memastikan portabilitas lintas environment execution.
*   **Baris 5:** Menetapkan target bundle format menjadi `esm` murni. Format ini memanfaatkan native dynamic `import()` dan static `import/export`, menjamin performa tree-shaking optimal pada bundler modern.

```typescript
6:   dts: true,
7:   clean: true,
```
*   **Baris 6:** Menginstruksikan `tsup` untuk menjalankan Rollup internal TypeScript type declaration bundler (`rollup-plugin-dts`). Ini mengompilasi puluhan nested `.d.ts` file menjadi satu file tunggal `dist/index.d.ts`, secara dramatis mempercepat waktu resolusi compiler TypeScript di sisi consumer project.
*   **Baris 7:** Membersihkan direktori `dist/` sebelum melakukan kompilasi baru untuk mencegah tercampurnya artefak *stale/zombie* dari build sebelumnya.

```typescript
8:   treeshake: true,
9:   sourcemap: true,
10: });
```
*   **Baris 8:** Memerintahkan esbuild untuk menjalankan optimasi penghapusan kode yang tidak terpakai (*unreferenced identifier cleanup*) bahkan di level leaf package.
*   **Baris 9:** Membangkitkan file `.map` eksternal. Source mapping sangat kritikal di Design System enterprise agar developer consumer dapat melakukan debugging step-through langsung ke source code TypeScript asli, bukan kode minified production.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Insiden Skala Global pada FinTech Unicorn
**Konteks:** Sebuah platform FinTech enterprise ("PayGlobal") memigrasikan Design System monolitik mereka ke arsitektur multi-package monorepo. Sistem mereka melayani 8 platform frontend: Web Portal (Next.js), Merchant Dashboard (Vite), Mobile Web (Remix), dan beberapa internal micro-frontends (Webpack 5 module federation).

### The Triggering Incident:
Tim Design System merilis paket `@payglobal/ui` versi `v4.2.0`. Beberapa menit setelah rilis, pipeline CI/CD di seluruh repositori frontend perusahaan gagal serentak (*pipeline cascade failure*). Merchant Dashboard melempar runtime exception pada production runtime:
```
TypeError: Object(...) is not a function at Object../node_modules/@payglobal/ui/dist/index.js
Cannot read properties of undefined (reading 'createContext')
```
Secara bersamaan, Web Portal Next.js mengalami degradasi performa: First Load JS Bundle melonjak dari 180 KB menjadi 1.2 MB.

### Akar Masalah (Root Cause Analysis):
1.  **Dual-Package Hazard Terwujud:** Tim Design System mengompilasi bundle dual ESM/CJS tanpa *isolated exports maps*. `@payglobal/ui` mengimpor `@payglobal/icons` versi ESM, sementara `@payglobal/forms` secara transisi memuat `@payglobal/icons` versi CJS. Bundle React Context terpecah menjadi dua isolated state di memori.
2.  **Missing `sideEffects: false` Flag:** Entry point utama `@payglobal/ui/src/index.ts` mengekspor seluruh komponen (termasuk Charting Library berbasis D3 yang masif). Ketiadaan deklarasi `sideEffects: false` memaksa Webpack 5 milik Next.js menyertakan library D3 ke dalam bundle production setiap halaman, merusak dead-code elimination.
3.  **Broken TypeScript Resolution:** File `package.json` tidak memiliki subpath `.d.ts` mapping yang benar untuk CJS dan ESM. Developer lokal mengompilasi TypeScript menggunakan opsi legacy `moduleResolution: "node"`, sementara CI memvalidasi menggunakan `moduleResolution: "bundler"`, memicu mismatch verifikasi tipe.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah solusi arsitektural menyeluruh tingkat industri untuk memecahkan insiden di Seksi 09. Kita akan membangun infrastruktur monorepo lengkap: Core Package, UI Components Package, konfigurasi modern dual-build, dan pipeline Changesets otomatis.

### 1. Root Configuration: `package.json`
```json
{
  "name": "acme-design-system-root",
  "version": "0.0.0",
  "private": true,
  "packageManager": "pnpm@9.1.0",
  "scripts": {
    "build": "turbo run build",
    "lint": "turbo run lint",
    "type-check": "turbo run type-check",
    "version-packages": "changeset version",
    "release": "turbo run build && changeset publish"
  },
  "devDependencies": {
    "@changesets/cli": "^2.27.1",
    "turbo": "^1.13.3",
    "typescript": "^5.4.5"
  }
}
```

### 2. Changesets Configuration: `.changeset/config.json`
```json
{
  "$schema": "https://unpkg.com/@changesets/config@2.3.0/schema.json",
  "changelog": "@changesets/cli/changelog",
  "commit": false,
  "fixed": [],
  "linked": [["@acme/core", "@acme/ui"]],
  "access": "public",
  "baseBranch": "main",
  "updateInternalDependencies": "patch",
  "ignore": []
}
```

### 3. Production Package: `@acme/core`
#### `packages/core/package.json`
```json
{
  "name": "@acme/core",
  "version": "2.0.0",
  "description": "Core primitives and theme contracts for Acme Design System",
  "type": "module",
  "sideEffects": false,
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.mjs",
      "require": "./dist/index.cjs"
    }
  },
  "main": "./dist/index.cjs",
  "module": "./dist/index.mjs",
  "types": "./dist/index.d.ts",
  "files": [
    "dist"
  ],
  "scripts": {
    "build": "tsup",
    "lint": "eslint src/ --ext .ts,.tsx",
    "type-check": "tsc --noEmit"
  },
  "peerDependencies": {
    "react": "^18.0.0 || ^19.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.1",
    "react": "^18.3.1",
    "tsup": "^8.0.2",
    "typescript": "^5.4.5"
  }
}
```

#### `packages/core/src/index.ts`
```typescript
import * as React from 'react';

export interface ThemeConfig {
  mode: 'light' | 'dark';
  brandColor: string;
}

export interface ThemeContextValue {
  theme: ThemeConfig;
  setTheme: (theme: ThemeConfig) => void;
}

export const ThemeContext = React.createContext<ThemeContextValue | undefined>(undefined);

export interface ThemeProviderProps {
  initialTheme?: ThemeConfig;
  children: React.ReactNode;
}

export function ThemeProvider({ 
  initialTheme = { mode: 'light', brandColor: '#0052CC' }, 
  children 
}: ThemeProviderProps): React.JSX.Element {
  const [theme, setTheme] = React.useState<ThemeConfig>(initialTheme);

  const value = React.useMemo(() => ({ theme, setTheme }), [theme]);

  return React.createElement(ThemeContext.Provider, { value }, children);
}

export function useTheme(): ThemeContextValue {
  const context = React.useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be executed within an enclosing ThemeProvider context.');
  }
  return context;
}
```

#### `packages/core/tsup.config.ts`
```typescript
import { defineConfig } from 'tsup';

export default defineConfig({
  entry: {
    index: 'src/index.ts',
  },
  format: ['esm', 'cjs'],
  outExtension({ format }) {
    return {
      js: format === 'esm' ? '.mjs' : '.cjs',
    };
  },
  dts: true,
  clean: true,
  sourcemap: true,
  splitting: false,
  treeshake: true,
  target: 'es2022',
  external: ['react', 'react-dom'],
});
```

### 4. Consumer Package: `@acme/ui`
#### `packages/ui/package.json`
```json
{
  "name": "@acme/ui",
  "version": "2.0.0",
  "description": "Component library implementation for Acme Design System",
  "type": "module",
  "sideEffects": false,
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.mjs",
      "require": "./dist/index.cjs"
    },
    "./button": {
      "types": "./dist/button.d.ts",
      "import": "./dist/button.mjs",
      "require": "./dist/button.cjs"
    }
  },
  "main": "./dist/index.cjs",
  "module": "./dist/index.mjs",
  "types": "./dist/index.d.ts",
  "files": [
    "dist"
  ],
  "scripts": {
    "build": "tsup",
    "lint": "eslint src/ --ext .ts,.tsx",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "@acme/core": "workspace:*"
  },
  "peerDependencies": {
    "react": "^18.0.0 || ^19.0.0",
    "react-dom": "^18.0.0 || ^19.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.1",
    "@types/react-dom": "^18.3.1",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "tsup": "^8.0.2",
    "typescript": "^5.4.5"
  }
}
```

#### `packages/ui/src/button.tsx`
```typescript
import * as React from 'react';
import { useTheme } from '@acme/core';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary';
  children: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', style, children, ...props }, ref) => {
    const { theme } = useTheme();

    const dynamicStyle: React.CSSProperties = {
      backgroundColor: variant === 'primary' ? theme.brandColor : 'transparent',
      color: variant === 'primary' ? '#FFFFFF' : theme.brandColor,
      border: `1px solid ${theme.brandColor}`,
      padding: '8px 16px',
      borderRadius: '4px',
      cursor: 'pointer',
      fontSize: '14px',
      fontWeight: 600,
      ...style,
    };

    return React.createElement(
      'button',
      {
        ref,
        style: dynamicStyle,
        ...props,
      },
      children
    );
  }
);

Button.displayName = 'Button';
```

#### `packages/ui/src/index.ts`
```typescript
export * from './button';
```

#### `packages/ui/tsup.config.ts`
```typescript
import { defineConfig } from 'tsup';

export default defineConfig({
  entry: {
    index: 'src/index.ts',
    button: 'src/button.tsx',
  },
  format: ['esm', 'cjs'],
  outExtension({ format }) {
    return {
      js: format === 'esm' ? '.mjs' : '.cjs',
    };
  },
  dts: true,
  clean: true,
  sourcemap: true,
  splitting: true,
  treeshake: true,
  target: 'es2022',
  external: ['react', 'react-dom', '@acme/core'],
});
```

### 5. Automated CI/CD Publishing Pipeline: `.github/workflows/release.yml`
```yaml
name: Release Pipeline

on:
  push:
    branches:
      - main

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: write
  packages: write
  pull-requests: write
  id-token: write # Diperlukan untuk provenance attestations

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Node.js Runtime
        uses: actions/setup-node@v4
        with:
          node-version: 20.x

      - name: Install PNPM Package Manager
        uses: pnpm/action-setup@v3
        with:
          version: 9.1.0
          run_install: false

      - name: Resolve Global Store Path
        id: pnpm-cache-dir
        shell: bash
        run: echo "STORE_PATH=$(pnpm store path --silent)" >> $GITHUB_OUTPUT

      - name: Initialize Dependency Caching
        uses: actions/cache@v4
        with:
          path: ${{ steps.pnpm-cache-dir.outputs.STORE_PATH }}
          key: ${{ runner.os }}-pnpm-store-${{ hashFiles('**/pnpm-lock.yaml') }}
          restore-keys: |
            ${{ runner.os }}-pnpm-store-

      - name: Install Monorepo Dependencies
        run: pnpm install --frozen-lockfile

      - name: Turborepo Pipeline Validation (Lint, Test, Type-Check)
        run: |
          pnpm turbo run lint type-check

      - name: Execute Changesets Automation
        id: changesets
        uses: changesets/action@v1
        with:
          publish: pnpm release
          version: pnpm version-packages
          title: "chore(release): version packages"
          commit: "chore(release): version bump and changelog generation"
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          NPM_TOKEN: ${{ secrets.NPM_AUTOMATION_TOKEN }}
          NPM_CONFIG_PROVENANCE: true
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

Dalam merancang fondasi arsitektur distribusi monorepo, terdapat trade-off signifikan yang harus diputuskan secara sadar:

### 1. Monorepo Package Managers: PNPM vs Yarn Berry vs Lerna
| Dimensi Evaluasi | PNPM (Workspaces + Hardlinks) | Yarn Berry (PnP - Plug'n'Play) | NPM / Lerna (Legacy Hoisting) |
| :--- | :--- | :--- | :--- |
| **Penyimpanan Disk** | Sangat Hemat (Content-addressable storage). | Sangat Hemat (Zip archives). | Sangat Boros (Duplikasi di setiap direktori). |
| **Phantom Dependencies** | **Zero-tolerance.** Strict symlinking mengisolasi akses secara total. | **Zero-tolerance.** Validasi via runtime resolution table. | **Rentan Tinggi.** Hoisted packages membocorkan modules secara global. |
| **Kompatibilitas Native C++ Bindings** | Sangat Tinggi. Struktur `node_modules` tetap berwujud fisik. | Rendah. Membutuhkan patching zero-installs untuk library binary. | Sangat Tinggi. |
| **Ekosistem CI/CD** | Cepat, integrasi cache sederhana. | Sangat Cepat (Zero-install possible), namun kurva belajar terjal. | Lambat saat menjalankan network resolution. |

### 2. Output Packaging Target: Dual Target (ESM + CJS) vs ESM-Only
| Parameter Arsitektur | Dual Target (ESM + CJS) | Pure ESM (`"type": "module"`) |
| :--- | :--- | :--- |
| **Dukungan Legacy Framework** | Kompatibel dengan Next.js Page Router lama, Jest CJS config, Webpack 4. | Memaksa consumer untuk memutakhirkan toolchains mereka. |
| **Risiko Dual-Package Hazard** | **Tinggi.** Wajib mitigasi tsup/isolated export configuration. | **Nol.** Tidak ada CJS chunk yang dapat memecah memory heap. |
| **Ukuran Build Artefak** | 2x lipat (menghasilkan berkas `.mjs` dan `.cjs` beserta typings). | 1x lipat (hanya memproduksi native modern JavaScript). |
| **Kecepatan Build Pipeline** | Lebih lambat karena bundling engine mengeksekusi dua passes. | Sangat Cepat. Eksekusi single-pass bundling. |

### 3. Versioning Strategy: Independent Versioning vs Fixed (Synchronized) Versioning
| Karakteristik | Independent Versioning | Fixed (Lockstep) Versioning |
| :--- | :--- | :--- |
| **Representasi SemVer