# Bab 09 Module 01: Build Systems, Bundlers & CI/CD Pipeline

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Frontend & Mobile Engineering
*   **Kategori:** 03-Frontend-and-Mobile
*   **Bab:** 09 — Architecture, Tooling, Infrastructure & Automation
*   **Modul:** 01 — Build Systems, Bundlers & CI/CD Pipeline
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Track
*   **Prasyarat Konseptual:** JavaScript Engine Internals (V8), Module Systems (CJS, ESM), Dependency Graphs, Browser Runtime Lifecycle, HTTP Caching & Protocols (HTTP/2, HTTP/3), Linux Containerization Basics (Docker), Git Automation.

---

## SEKSI 02 — LEARNING OBJECTIVES

1.  **Mendekomposisi Mekanisme Kompilasi & Bundling:** Menganalisis transformasi Abstract Syntax Tree (AST), resolusi modul rekursif, *scope hoisting*, dan algoritma eliminasi kode mati (*Tree Shaking*) pada modern bundler.
2.  **Mengevaluasi Arsitektur Tooling:** Membandingkan arsitektur internal *engine* generasi lama (Webpack, Rollup) dengan *compiler* berbasis native system language (Vite, Rollup/Rolldown, esbuild, Turbopack) berdasarkan latensi I/O, paralelisasi memori, dan overhead kompilasi.
3.  **Merancang Strategi Code Splitting Lanjutan:** Mengonfigurasi pembagian vendor, *dynamic imports*, modul runtime, dan optimasi *long-term caching* menggunakan content hash deterministik.
4.  **Mengonstruksi Production-Grade CI/CD Pipelines:** Mengembangkan *pipeline deployment* berbasis GitHub Actions yang deterministik, mengimplementasikan multi-tier caching (dependencies, lockfiles, compiler cache), matrix build, dan verifikasi artifact integrity.
5.  **Mengaudit dan Memitigasi Risiko Rantai Pasok:** Menerapkan scanning dependensi, pencegahan kerentanan zero-day melalui integrasi Software Bill of Materials (SBOM), serta penegakan CSP dan subresource integrity (SRI).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Bundler Sebagai Directed Acyclic Graph (DAG) Processor
Seorang web developer melihat aplikasi frontend sebagai direktori file (`.js`, `.jsx`, `.ts`, `.css`). Namun, seorang Staff Engineer melihatnya sebagai **Directed Acyclic Graph (DAG)**:
*   **Node:** File/Modul individual.
*   **Edge:** Pernyataan statis/dinamis `import` atau `export`.
*   **Transformasi Pipeline:** Operasi fungsional murni yang menerima string mentah, mem-parsing-nya menjadi Abstract Syntax Tree (AST), melakukan mutasi/analisis traversal, dan memancarkan string kode target beserta pemetaan byte-ke-byte (*source maps*).

```
[Raw Source Code File]
         │
         ▼
[Lexer / Tokenizer] ──► Mengonversi stream teks ke token stream
         │
         ▼
  [Parser (AST)]    ──► Membangun Graph node semantik (ESTree compliant)
         │
         ▼
[Module Graph Resolver] ──► Menentukan Module Specifier Resolution Algorithm
         │
         ▼
[Optimization & Shaking] ──► Menandai node tanpa incoming active edge (DCE)
         │
         ▼
  [Code Emitter]    ──► Memancarkan chunk artifacts teroptimasi
```

### Build Tools Bukan Sekadar Task Runner
Alat build bukan sekadar pembungkus file teks menjadi file tunggal. Build tools adalah sistem proteksi runtime. Kode yang dieksekusi di browser klien tidak berjalan di lingkungan lokal engineer. Build tool bertindak sebagai *compiler runtime targeting*, memvalidasi invariants, memangkas byte redundant untuk menghemat bandwidth TCP, dan menyusun *execution chunks* demi memaksimalkan konkurensi browser parsing engine.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur visual pemrosesan modul mulai dari fase *Development HMR (Hot Module Replacement)* hingga *Production Build* dan *Deployment Execution Flow*.

### 1. Arsitektur Kompilasi: Webpack (Node.js Bundler) vs. Vite/esbuild (Native Bundler)

```
=============================================================================
A. WEBPACK / CLASSIC BUNDLER (Bundle-based Dev Server)
=============================================================================
 Entry Module ──┐
 Source B ──────┼──► [ AST Parsing ] ──► [ Full Module Graph ] ──► [ In-Memory Bundle ] ──► Dev Server Ready
 Source C ──────┘     (Node.js Single-Threaded Event Loop)          (Latensi O(N))       (Sangat Lambat)

=============================================================================
B. MODERN HYBRID BUNDLER (Vite + esbuild/Rollup)
=============================================================================
 Browser HTTP Request (Native ESM) ──┐
                                     │ (On-Demand Transformation)
                                     ▼
                      [ Vite Dev Server (HTTP/2) ]
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
      [ Pre-bundled Dependencies ]             [ Source Code Modules ]
      (esbuild: Go Multi-threaded)            (On-demand Dynamic Transform)
      Transformasi instan (O(1))              Babel/SWC/Rust compile per-file
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     ▼
                            Browser Native Engine
```

### 2. CI/CD Release Lifecycle Pipeline

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DEVELOPER WORKSPACE                             │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ Git Push (Branch: Release/* / Main)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        CI/CD PIPELINE ORCHESTRATOR                     │
│                                                                        │
│ ┌──────────────────────┐  Cache Hit   ┌──────────────────────────────┐ │
│ │  Job 1: Setup & Deps ├─────────────►│ Restore Node Cache / Store   │ │
│ │  (pnpm fetch/install)│              └──────────────┬───────────────┘ │
│ └──────────┬───────────┘                             │                 │
│            ▼                                         ▼                 │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │  Job 2: Matrix Validation [Parallel Workers]                       │ │
│ │  ├── Worker A: TypeScript Compiler (`tsc --noEmit`)                 │ │
│ │  ├── Worker B: Linter & AST Analyzer (`eslint --max-warnings 0`)   │ │
│ │  └── Worker C: Unit/Integration Suite (`vitest run --coverage`)    │ │
│ └────────────────────────────────────┬───────────────────────────────┘ │
│                                      │ All Gates Passed                │
│                                      ▼                                 │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │  Job 3: Optimized Production Build Engine                          │ │
│ │  ├── Turbopack / Rollup Multi-core Compilation                     │ │
│ │  ├── Scope Hoisting, Terser/ESBuild Minification                   │ │
│ │  ├── Source Map Upload to Telemetry Server (Sentry)                │ │
│ │  └── Generation of Subresource Integrity (SRI) Manifest            │ │
│ └────────────────────────────────────┬───────────────────────────────┘ │
│                                      │                                 │
│                                      ▼                                 │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │  Job 4: Artifact Attestation & Security Scan                       │ │
│ │  ├── Software Bill of Materials (SBOM) Generation via Syft         │ │
│ │  └── Trivy Vulnerability Scan                                      │ │
│ └────────────────────────────────────┬───────────────────────────────┘ │
└──────────────────────────────────────┼─────────────────────────────────┘
                                       │ Deploy Stage Artifact
                                       ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        EDGE INFRASTRUCTURE (CDN)                       │
│  ├── /assets/*.hash.js       (Cache-Control: public, max-age=31536000) │
│  └── /index.html             (Cache-Control: no-cache, must-revalidate)│
└────────────────────────────────────────────────────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Module Specifier Resolution Algorithm
Bundler mengimplementasikan algoritma resolusi yang mengikuti modifikasi Node.js resolution atau ESM specification:
1.  **Core Package Detection:** Mengecek apakah modul adalah native/built-in.
2.  **Relative/Absolute Pathing:** Menelusuri `./`, `../`, atau root path absolut `/`.
3.  **Module Specifier Resolution (`node_modules` Walk):**
    *   Mencari target di direktori aktif `./node_modules`.
    *   Jika gagal, traversi direktori induk bertingkat (`../node_modules`) hingga *filesystem root*.
4.  **Package.json Metadata Parsing:**
    *   Membaca field `exports` (Modern conditional exports: `import`, `require`, `types`, `browser`).
    *   Fallback ke field legacy: `module`, lalu `main`.
5.  **Extension Probing:** Mencoba ekstensi target (misal: `.ts`, `.tsx`, `.js`, `.json`) jika path tidak eksplisit.

### 2. Mekanisme Tree Shaking & Dead Code Elimination (DCE)
Tree shaking bergantung pada karakteristik **Static Analysis** dari ECMAScript Modules (ESM):
*   Import dan export harus berada di top-level scope (bukan di dalam conditional blok seperti `if (true) require()`).
*   **Marking Phase:** Bundler memulai traversal dari entry point. Setiap fungsi/variabel yang di-export dianalisis pemanggilannya. Node AST yang memiliki dependensi aktif diberi tanda (misal: `isUsed = true`).
*   **Side-Effect Analysis:** Bundler membaca file `package.json` untuk flags `"sideEffects": false` atau regex rules. Jika sebuah file tidak memiliki *side-effects* murni dan export-nya tidak dipanggil, seluruh AST modul tersebut langsung dieksklusi dari final bundle.
*   **Sweeping Phase:** Kode yang tidak memiliki tanda dipangkas (*pruned*) dari bundle sebelum serialisasi.

### 3. Hot Module Replacement (HMR) State Engine
HMR mempertahankan status aplikasi di memori browser tanpa melakukan reload halaman secara penuh:
*   **WebSocket Link:** Dev Server menjaga koneksi WebSocket real-time dengan runtime klien.
*   **File Watcher:** Saat file berubah, OS file watcher (`inotify`/`fsevents`) mengirim trigger ke bundler.
*   **HMR Boundary Walk:** Bundler mencari modul yang berubah, memeriksa apakah modul tersebut atau modul induknya mengimplementasikan `import.meta.hot.accept`.
*   **Update Propagation:** Jika boundary ditemukan, bundler hanya mengirim diff JSON/JS modul tersebut. Runtime browser menjalankan fungsi callback penukaran kode lama dengan yang baru tanpa membuang state UI (seperti React Component State). Jika tidak ada boundary yang menangani, sinyal fallback dipicu: *Full Page Reload*.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### V8 Heap Allocation & Bottleneck Kompilasi Node.js
Bundler generasi awal seperti Webpack memproses seluruh graph modul di atas runtime V8 Node.js. 
*   **Keterbatasan:** JavaScript adalah single-threaded engine (meskipun I/O bersifat asynchronous via Libuv).
*   **Overhead:** Membangun ratusan ribu object node AST menghabiskan jatah V8 Garbage Collection (GC) limit. Tekanan alokasi memori menyebabkan *GC thrashing*, di mana V8 engine menghabiskan siklus CPU hanya untuk membersihkan memory footprint dari AST node parsing.
*   **Solusi Native:** Bundler modern (esbuild yang ditulis dalam Go, SWC/Turbopack/Rolldown yang ditulis dalam Rust) menggunakan **multithreaded parallelism murni**. Bahasa native mengalokasikan data mentah secara berdekatan (*contiguous memory buffers*) tanpa overhead objek V8 dan tanpa latency GC yang masif, meningkatkan throughput parsing hingga 10x–50x lipat.

### Long-Term Caching dan Chunk Hashing Mathematics
Browser caching bergantung pada header `Cache-Control`. Pendekatan performa tertinggi adalah *immutable caching*:
`Cache-Control: public, max-age=31536000, immutable`

Untuk menerapkan ini secara aman, nama file wajib mengandung hash dari konten file tersebut. Namun, pembuatan hash harus bersifat deterministik:
*   `[hash] / [fullhash]`: Hash unik dihitung dari keseluruhan build compilation. (Sangat buruk untuk caching: perubahan 1 baris kode di satu file mengubah nama seluruh file chunk aplikasi).
*   `[chunkhash]`: Hash dihitung berdasarkan entri chunk masing-masing.
*   `[contenthash]`: Hash dihitung secara ketat dari *konten byte-stream* murni file keluaran tertentu. Jika CSS diekstraksi dari JavaScript module, perubahan JS tidak akan mengubah `contenthash` dari file CSS tersebut.

Perhitungan `contenthash` mengimplementasikan algoritma hashing kriptografis (misal: SHA-256 atau MurmurHash3 truncated) secara deterministik:
$$\text{Hash} = H(\text{ByteStream}(\text{AST}_{\text{final}}))$$

### Subresource Integrity (SRI)
SRI menjamin bahwa file yang di-download klien dari jaringan CDN pihak ketiga belum dimodifikasi oleh aktor jahat (*Man-in-the-Middle Attack* atau kompromi server CDN). Hash kriptografis disuntikkan langsung pada tag HTML:
```html
<script src="https://cdn.enterprise.com/assets/vendor.a1b2c3d4.js" 
        integrity="sha384-oqVuAfXRKap7fdgcCY5uykM6+R9GqQ8K/uxy9rx7HNQlGYl1kPzQho1wx4JwY8wC" 
        crossorigin="anonymous"></script>
```
Saat browser mengeksekusi file tersebut, browser menghitung hash byte stream lokal dan memvalidasinya secara biner terhadap nilai pada atribut `integrity`. Jika hash tidak identik secara presisi, V8/Blink menolak eksekusi modul demi keamanan sistem.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah perbandingan pipeline konfigurasi build system modern berbasis Vite + Rolldown/Rollup Architecture.

### Struktur Proyek

```
enterprise-build/
├── build/
│   └── plugins/
│       └── dynamicChunkNaming.ts
├── src/
│   ├── modules/
│   │   ├── analytics.ts
│   │   └── dashboard.ts
│   └── main.ts
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### 1. `vite.config.ts` (Manual Chunking & Asset Pipeline)

```typescript
import { defineConfig, type PluginOption } from 'vite';
import { resolve } from 'node:path';
import crypto from 'node:crypto';

// Custom plugin untuk verifikasi integritas hash
function manifestIntegrityPlugin(): PluginOption {
  return {
    name: 'enterprise-manifest-integrity',
    apply: 'build',
    enforce: 'post',
    generateBundle(_options, bundle) {
      for (const [fileName, assetOrChunk] of Object.entries(bundle)) {
        if (assetOrChunk.type === 'chunk') {
          const content = assetOrChunk.code;
          const hash = crypto
            .createHash('sha384')
            .update(content, 'utf8')
            .digest('base64');
          
          // Menyuntikkan metadata custom ke chunk
          this.emitFile({
            type: 'asset',
            fileName: `${fileName}.sri.txt`,
            source: `sha384-${hash}`,
          });
        }
      }
    },
  };
}

export default defineConfig({
  build: {
    target: 'es2022',
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: true,
    minify: 'esbuild',
    cssCodeSplit: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
      },
      output: {
        // Enforce Content-Hashing deterministik
        entryFileNames: 'assets/js/[name].[contenthash:16].js',
        chunkFileNames: 'assets/js/chunks/[name].[contenthash:16].js',
        assetFileNames: (assetInfo) => {
          const extType = assetInfo.name?.split('.').pop() || 'bin';
          if (/png|jpe?g|svg|gif|tiff|bmp|webp/i.test(extType)) {
            return 'assets/images/[name].[contenthash:16].[ext]';
          }
          if (/css/i.test(extType)) {
            return 'assets/css/[name].[contenthash:16].[ext]';
          }
          return 'assets/misc/[name].[contenthash:16].[ext]';
        },
        // Strategic Manual Chunking
        manualChunks(id: string) {
          if (id.includes('node_modules')) {
            // Isolasi framework inti ke chunk mandiri
            if (id.includes('react') || id.includes('react-dom')) {
              return 'vendor-core';
            }
            // Isolasi package berat (grafik/matematika)
            if (id.includes('d3') || id.includes('chart.js')) {
              return 'vendor-charts';
            }
            // Catch-all vendor chunk
            return 'vendor-deps';
          }
        },
      },
    },
  },
  plugins: [manifestIntegrityPlugin()],
});
```

### 2. `src/main.ts` (Implementasi Dynamic Code Splitting)

```typescript
// Main Application Entry Point
import { setupSecurityHeaders } from './modules/security';

interface ModuleExecutionResult {
  initialized: boolean;
  timestamp: number;
}

class ApplicationRuntime {
  public async boot(): Promise<void> {
    console.info('[Engine] Application initialized');
    setupSecurityHeaders();
    this.bindDynamicTriggers();
  }

  private bindDynamicTriggers(): void {
    const triggerBtn = document.getElementById('load-dashboard-btn');
    if (!triggerBtn) return;

    triggerBtn.addEventListener('click', async () => {
      try {
        // Dynamic Import memicu pemisahan chunk secara otomatis
        const { loadDashboardView } = await import(
          /* webpackChunkName: "view-dashboard" */
          './modules/dashboard'
        );
        
        const result: ModuleExecutionResult = await loadDashboardView();
        console.info(`[Engine] Dashboard loaded at ${result.timestamp}`);
      } catch (err: unknown) {
        console.error('[Engine] Critical chunk load failure:', err);
      }
    });
  }
}

const app = new ApplicationRuntime();
void app.boot();
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File `vite.config.ts`

*   **Baris 7–27 (`manifestIntegrityPlugin`):** Mendefinisikan kustom plugin *Rollup-compatible*. 
    *   Hook `generateBundle` dieksekusi secara in-memory sebelum byte-stream ditulis ke disk.
    *   `crypto.createHash('sha384')`: Memproses string target menggunakan algoritma SHA-384 sesuai spesifikasi W3C SRI.
    *   `this.emitFile(...)`: Memancarkan file aset baru secara programatis (`.sri.txt`) yang berisi hash validasi tanpa mengganggu alur runtime bundling utama.
*   **Baris 30 (`target: 'es2022'`):** Menginstruksikan compiler agar tidak membuang bytecode modern (seperti Top-Level Await, Class Fields, Array.at). Ini menghindarkan penambahan kode kompilasi *polyfill overhead* yang usang.
*   **Baris 41–43 (`entryFileNames & chunkFileNames`):** Penggunaan token `[contenthash:16]` memotong panjang hash string menjadi 16 karakter hexadecimal yang representatif, menjamin bahwa browser cache *invalidated* HANYA jika byte kode di dalamnya termutasi.
*   **Baris 53–66 (`manualChunks(id: string)`):** Implementasi algoritma split-chunking:
    *   Parameter `id` merupakan path absolut dari setiap modul yang dilewati dependency graph.
    *   Pemisahan `vendor-core` (React, ReactDOM) memastikan bahwa pembaruan kode internal developer tidak merusak cache client untuk library dependency inti yang frekuensi update-nya jauh lebih rendah.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Masalah Produksi Enterprise
*   **Profil Perusahaan:** Platform FinTech Internasional (Single Page Application dengan 3.500 modul TypeScript).
*   **Gejala:**
    1.  Durasi pipeline CI/CD mencapai **42 menit**, menghambat hotfix deployment.
    2.  Pengunjung mengunduh file bundle utama sebesar **8.4 MB (uncompressed)** saat memuat halaman pertama (`/login`).
    3.  Laporan error Sentry menunjukkan *ChunkLoadError* berulang saat pengguna lama membuka aplikasi tepat setelah deployment baru selesai (*Hash Invalidation Collision*).
*   **Akar Masalah (Root Cause Analysis):**
    1.  Pipeline CI/CD mengeksekusi `npm install` berulang tanpa cache layer, diikuti eksekusi Webpack 4 single-threaded.
    2.  Seluruh library analitik, chart, dan dashboard di-import secara statis di file `index.ts`.
    3.  Strategi penamaan file Webpack mengandalkan `[hash]`, bukan `[contenthash]`. Setiap rilis kecil mengubah total seluruh file asset name, membuang efisiensi cache browser. File chunk lama langsung dihapus seketika dari storage saat deploy, memutuskan referensi klien aktif.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Solusi menyeluruh: Konstruksi Enterprise-Grade GitHub Actions CI/CD Pipeline lengkap dengan matrix test, cache multi-layer, build Vite/Rollup yang optimal, serta integrasi deployment CDN tanpa downtime.

### `.github/workflows/production-pipeline.yml`

```yaml
name: Enterprise Production Delivery Pipeline

on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  NODE_VERSION: '20.11.1'
  PNPM_VERSION: '8.15.4'

jobs:
  audit-and-dependencies:
    name: Setup, Cache & Dependency Integrity
    runs-on: ubuntu-latest
    outputs:
      dependency-cache-key: ${{ steps.compute-hash.outputs.cache-key }}
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Setup Corepack & PNPM Engine
        run: |
          corepack enable
          corepack prepare pnpm@${{ env.PNPM_VERSION }} --activate

      - name: Setup Node.js Runtime Environment
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}

      - name: Expose PNPM Store Path
        id: pnpm-cache
        shell: bash
        run: |
          echo "STORE_PATH=$(pnpm store path --silent)" >> $GITHUB_ENV

      - name: Restore PNPM Dependency Store
        uses: actions/cache@v4
        id: cache-dependencies
        with:
          path: ${{ env.STORE_PATH }}
          key: ${{ runner.os }}-pnpm-store-${{ hashFiles('**/pnpm-lock.yaml') }}
          restore-keys: |
            ${{ runner.os }}-pnpm-store-

      - name: Deterministic Frozen Dependency Installation
        run: pnpm install --frozen-lockfile --prefer-offline

      - name: Security Vulnerability Audit
        run: pnpm audit --audit-level=high

  matrix-validation:
    name: Quality Gate Evaluation
    needs: [audit-and-dependencies]
    runs-on: ubuntu-latest
    strategy:
      fail-fast: true
      matrix:
        task: [typecheck, lint, test:unit]
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Setup Corepack & PNPM Engine
        run: |
          corepack enable
          corepack prepare pnpm@${{ env.PNPM_VERSION }} --activate

      - name: Setup Node.js Runtime Environment
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}

      - name: Restore PNPM Dependency Store
        uses: actions/cache@v4
        with:
          path: $(pnpm store path --silent)
          key: ${{ runner.os }}-pnpm-store-${{ hashFiles('**/pnpm-lock.yaml') }}

      - name: Install Dependencies
        run: pnpm install --frozen-lockfile --prefer-offline

      - name: Execute Matrix Verification Task
        run: |
          if [ "${{ matrix.task }}" = "typecheck" ]; then
            pnpm exec tsc --noEmit --project tsconfig.json
          elif [ "${{ matrix.task }}" = "lint" ]; then
            pnpm exec eslint . --max-warnings 0
          elif [ "${{ matrix.task }}" = "test:unit" ]; then
            pnpm exec vitest run --coverage
          fi

  production-compilation:
    name: Production Build & Asset Attestation
    needs: [matrix-validation]
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Setup Corepack & PNPM Engine
        run: |
          corepack enable
          corepack prepare pnpm@${{ env.PNPM_VERSION }} --activate

      - name: Setup Node.js Runtime Environment
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}

      - name: Restore PNPM Dependency Store
        uses: actions/cache@v4
        with:
          path: $(pnpm store path --silent)
          key: ${{ runner.os }}-pnpm-store-${{ hashFiles('**/pnpm-lock.yaml') }}

      - name: Install Dependencies
        run: pnpm install --frozen-lockfile --prefer-offline

      - name: Execute Build Optimization
        env:
          NODE_ENV: production
        run: pnpm run build

      - name: Upload Artifacts for Deployment
        uses: actions/upload-artifact@v4
        with:
          name: production-build-dist
          path: dist/
          retention-days: 7
          if-no-files-found: error

  edge-deployment:
    name: Atomic Zero-Downtime CDN Propagation
    needs: [production-compilation]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - name: Download Build Artifacts
        uses: actions/download-artifact@v4
        with:
          name: production-build-dist
          path: dist/

      - name: Sync Static Assets to Object Storage (S3 / CDN)
        # Tahap 1: Sinkronisasi file immutable dengan contenthash lebih dulu (tanpa menghapus file lama)
        # Menghindarkan ChunkLoadError pada active clients!
        run: |
          echo "Simulasi Sinkronisasi File Immutable Assets..."
          # aws s3 sync dist/assets s3://enterprise-frontend-cdn/assets \
          #   --cache-control "public, max-age=31536000, immutable"

      - name: Sync Entry Documents Atomically
        # Tahap 2: Sinkronisasi file index.html yang tidak boleh di-cache kaku
        run: |
          echo "Simulasi Sinkronisasi Entrypoint HTML..."
          # aws s3 cp dist/index.html s3://enterprise-frontend-cdn/index.html \
          #   --cache-control "no-cache, no-store, must-revalidate"

      - name: Invalidate CDN Edge Cache
        run: |
          echo "Memancarkan pembersihan cache CloudFront / Cloudflare Edge..."
          # aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/index.html"
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek Arsitektur | Webpack 5 | Vite (esbuild + Rollup) | Turbopack (Next.js/Rust) |
| :--- | :--- | :--- | :--- |
| **Language Baseline** | JavaScript / Node.js | Go (Dev/Pre-pack) + JS (Rollup Build) | Rust (Native Multi-core) |
| **Cold Start Performance** | Lambat ($O(N)$ modul graph traversing) | Instan ($O(1)$ on-demand ESM serving) | Instan (Optimized Turbo Engine) |
| **HMR Latency (Apps > 5k Modules)** | Tinggi (2.000 ms – 7.000 ms) | Rendah (< 50 ms melalui HTTP/2 native ESM) | Sangat Rendah (< 20 ms via Fine-grained caching) |
| **Production Build Stability** | Sangat Tinggi (Mature Ecosystem & Loaders) | Tinggi (Mengandalkan Rollup pipeline) | Menengah (Fitur plugin ekosistem masih berkembang) |
| **Plugin Customization Flexibility**| Maksimal (Compiler Tapable Hook Engine) | Fleksibel (Unified Rollup-compatible API) | Terbatas (Memerlukan implementasi Native/Rust FFI) |
| **Memory Footprint (Build Time)** | Ekstrem (Tinggi risiko `OOM: Heap Limit`) | Efisien (Native multithreaded Go/esbuild) | Sangat Efisien (Akses memory langsung tanpa V8 GC) |

### Analisis Paradigma
1.  **Webpack:** Pilihan terbaik jika perusahaan terjebak dalam *custom legacy build pipelines* yang membutuhkan modifikasi AST mendalam pada format file yang tidak standar.
2.  **Vite / Rolldown:** Titik keseimbangan terbaik (*sweet spot*) untuk sebagian besar aplikasi SPA enterprise modern. Memberikan DX lokal yang cepat tanpa mengorbankan fleksibilitas rollup pada produksi.
3.  **Turbopack:** Investasi masa depan yang optimal jika arsitektur dibangun di atas framework fullstack SSR/RSC (React Server Components) dengan dependency hierarchy yang besar.

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Hash Invalidation Cascades via Transitive Re-Exports
*   **Mekanisme:** Jika `Module A` mengimpor `Module B`, dan `Module B` mengimpor `Module C`. Jika Anda mengubah satu baris komentar pada `Module C`, maka `Module C` menghasilkan `contenthash` baru. Jika `Module B` mengompilasi path impor `Module C` langsung di dalam kodenya, maka isi file `Module B` ikut berubah, yang secara kaskade mengubah `Module A`.
*   **Mitigasi:** Gunakan runtime manifest terisolasi. Pisahkan runtime mapping dari entrypoint script sehingga pembaruan hash file dalam dependency tree tidak merembet ke bundle parent yang tidak perlu.

### 2. The Micro-Chunk Problem (HTTP/2 Request Overhead)
*   **Mekanisme:** Pemisahan file secara berlebihan (*over-splitting*) menghasilkan ratusan file `.js` berukuran sangat kecil (< 1 KB). Meskipun HTTP/2 mendukung multiplexing, header framing overhead dan latency inter-dependency graph serialization (modul A menunggu impor modul B, yang membutuhkan modul C) menciptakan fenomena *waterfall delay* yang parah pada koneksi mobile latency tinggi.
*   **Mitigasi:** Konfigurasi batas minimal ukuran chunk bundler (`minSize` threshold sekitar 20 KB – 30 KB pada Rollup/Webpack) untuk menggabungkan modul-modul kecil.

### 3. Dynamic Import Variable Resolution Fallback
*   **Mekanisme:** Kode seperti:
    ```typescript
    const viewName = 'dashboard';
    const module = await import(`./views/${viewName}.js`);
    ```
    Bundler tidak bisa mengetahui nilai string `viewName` pada fase static analysis. Akibatnya, bundler akan mengikutsertakan **seluruh** file `.js` yang berada di dalam folder `./views/` ke dalam build bundle output.
*   **Mitigasi:** Batasi cakupan glob secara eksplisit atau buat peta (*dictionary lookup*) statis yang memetakan string kunci ke dynamic import statis.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Merusak Tree Shaking Akibat Babel CommonJS Transpilation
*   **Kesalahan:** Mengonfigurasi Babel preset tanpa mematikan module transformation (`presets: [['@babel/preset-env', { modules: 'commonjs' }]]`).
*   **Dampak:** Babel mengubah sintaks `import/export` ESM menjadi `require()` dan `module.exports`. Bundler tidak dapat menganalisis dynamic object keys secara statis, menyebabkan **Tree Shaking gagal total**; seluruh library mati (seperti utilitas Lodash lengkap) masuk ke dalam bundle produksi.
*   **Solusi:** Pastikan konfigurasi mempertahankan native ESM:
    ```json
    {
      "presets": [["@babel/preset-env", { "modules": false }]]
    }
    ```

### 2. Circular Dependencies Mengakibatkan State Initialized As `undefined`
*   **Kesalahan:** `ServiceA.ts` mengimpor `ServiceB.ts`, dan `ServiceB.ts` mengimpor `ServiceA.ts`.
*   **Dampak:** Bundler tidak dapat menentukan urutan node DAG secara linier. Runtime JavaScript browser mengeksekusi modul parsial di mana salah satu export bernilai `undefined`, memicu error `TypeError: Object(...) is not a function` yang sulit di-debug.
*   **Solusi:** Gunakan tool verifikasi statis seperti plugin `circular-dependency-plugin` atau ESLint rule `import/no-circular`.

### 3. Non-Atomic Deployment Menyebabkan Outage Sementara
*   **Kesalahan:** Menjalankan pipeline yang menghapus bucket penyimpanan lama (`aws s3 rm --recursive`) sebelum mengunggah bundle baru.
*   **Dampak:** Terdapat jendela waktu kosong (*downtime window*) selama beberapa detik hingga menit di mana seluruh pengguna yang membuka web atau menavigasi rute menerima respon HTTP 404 pada request asset JS.
*   **Solusi:** Deploy selalu secara aditif: unggah chunk baru, sinkronkan `index.html` terbaru, dan jangan hapus aset lama selama minimum $N$ hari/minggu agar sesi client aktif tidak rusak.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Deterministic CI Installs:** Selalu gunakan perintah instalasi yang mengunci dependensi secara absolut (`pnpm install --frozen-lockfile`, `npm ci`, atau `yarn install --immutable`). Jangan pernah menggunakan `npm install` biasa di dalam pipeline CI/CD.
2.  **Separate Vendor and Business Chunks:** Jangan biarkan library pihak ketiga bercampur baur dengan logika bisnis modul internal. Dependency pihak ketiga jarang berubah; pisahkan