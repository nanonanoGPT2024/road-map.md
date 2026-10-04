# MODULE 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 09: Build Systems, Bundlers, dan CI/CD Pipeline**  
**Kategori: 03-Frontend-and-Mobile (Frontend)**

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik pada tingkat Senior Frontend / Staff Platform Engineer diharapkan mampu:
- **Menganalisis Internal Arsitektur Bundler**: Membedah mekanisme *Abstract Syntax Tree* (AST) traversal, algoritma *Scope Hoisting*, *Tree Shaking* (Dead Code Elimination berbasis penandaan ESM), dan dynamic chunk splitting.
- **Mengimplementasikan Tooling Berbasis Bahasa Sistem**: Mengonfigurasi dan mengoptimasi pipeline kompilasi menggunakan engine Rust/Go (Rspack, SWC, esbuild, Rolldown) untuk mereduksi waktu build hingga skala $10^5$ baris kode (LOC) dengan target kompilasi sub-detik.
- **Merancang Arsitektur Monorepo Build Graph**: Mengonfigurasi komputasi terdistribusi menggunakan Turborepo/Nx dengan *remote computation caching*, *affected-only builds*, dan task dependency graph yang deterministik.
- **Membangun Pipeline CI/CD Produksi Kelas Enterprise**: Merekayasa pipeline pengujian, validasi tipe, linting, verifikasi *bundle budget*, *Subresource Integrity* (SRI), dan *Content Hash Stability* hingga artefak siap deploy.
- **Menyusun Strategi Atomic Deployment & Zero-Downtime CDN**: Mengorkestrasikan *immutable asset hosting* dengan strategi *cache invalidation* presisi tanpa memicu chunk loading error (`ChunkLoadError: Loading chunk failed`) selama masa transisi canary rollout.

---

## 2. Prerequisites
Sebelum mendalami modul ini, peserta wajib menguasai:
- Pengetahuan mendalam mengenai spesifikasi ECMAScript Modules (ESM) vs CommonJS (CJS) runtime behavior.
- Pemahaman dasar mengenai bundler modern (Vite, Rollup, Webpack 5 basic configuration).
- Pengalaman mengoperasikan CLI Linux, POSIX pipes, dan container runtime (Docker).
- Pemahaman fundamental tentang protokol HTTP/2, HTTP/3, serta *caching directives* (`Cache-Control`, `ETag`, `stale-while-revalidate`).
- Pengalaman menulis pipeline dasar pada GitHub Actions atau GitLab CI.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Anatomi Kompilasi: Parsing, AST, dan Transilasi
Proses bundling modern tidak lagi sekadar menggabungkan string file teks. Proses ini mengeksekusi pipeline formal compiler design:

```
[Source Code] 
      │ (Lexical Analysis / Tokenizer)
      ▼
[Token Stream]
      │ (Syntactic Analysis / Parser: SWC/Babel/Oxc)
      ▼
[Abstract Syntax Tree (AST)]
      │ (Semantic Analysis & Type Checking: TSC/SWC)
      │ (AST Transformations: JSX, Minification, Polyfilling)
      ▼
[Transformed AST]
      │ (Code Generation)
      ▼
[Optimized JavaScript Bundle + Source Maps]
```

Pada bundler modern berbasis Rust/Go (misalnya SWC pada Rspack atau esbuild):
1. **Lexing & Parsing**: Kode mentah dikonversi menjadi token, kemudian disusun menjadi AST struktural. Di Rust, representasi node AST dialokasikan dalam continuous memory pool (*bump allocator*) untuk meminimalisasi overhead Garbage Collection (GC) yang umum terjadi pada runtime V8 (Node.js).
2. **Symbol Resolution & Scope Analysis**: Bundler memetakan setiap variabel dan referensi ke lexical scope terkait. Analisis ini menandai variabel yang diekspor, diimpor, atau diisolasi secara internal.

### 3.2. Matematika di Balik Tree Shaking & Scope Hoisting
*Tree Shaking* bergantung sepenuhnya pada sifat deterministik dari *static ESM declaration* (`import`/`export` tidak dapat dipanggil kondisional di root scope).

Bundler modern memperlakukan dependency tree sebagai sebuah Directed Acyclic Graph (DAG) $G = (V, E)$, di mana:
- $V$ adalah himpunan modul (files) dan simbol identitas (functions, classes, constants).
- $E$ adalah relasi ketergantungan (edges) dari modul pengimpor ke modul pengekspor.

#### Algoritma Mark-and-Sweep untuk Dead Code Elimination:
1. Tandai seluruh entry point modul sebagai node **Roots** ($R \subset V$).
2. Telusuri graf secara rekursif menggunakan Depth-First Search (DFS) atau Breadth-First Search (BFS).
3. Untuk setiap modul $v \in V$, periksa seluruh *Identifier* yang digunakan. Jika modul $B$ mengekspor `foo` dan `bar`, namun modul $A$ hanya memanggil `import { foo } from 'B'`, maka simbol `bar` tidak akan ditandai (*unvisited/unmarked*).
4. **Side-Effect Analysis**: Jika modul target tidak bertanda `"sideEffects": false` di `package.json`, bundler wajib mengasumsikan bahwa evaluasi modul dapat mengubah global state (misal: memodifikasi `window` atau prototype primitif). Bundler dipaksa mempertahankan modul tersebut beserta dependensinya meskipun simbol ekspornya tidak dikonsumsi.
5. **Scope Hoisting**: Alih-alih membungkus setiap modul ke dalam fungsi penutup terpisah (IIFE wrappers seperti Webpack klasik) yang menimbulkan memory overhead pada call stack browser, bundler mengabungkan seluruh modul dalam satu lexical scope global bundle, melakukan *variable mangling* untuk menghindari tabrakan nama (*name collision*), dan menghapus reference overhead.

### 3.3. Chunk Splitting Engine: Dynamic Import & Shared Dependencies
Bundler mengevaluasi titik pemisahan (*split points*) yang dipicu secara eksplisit oleh sintaks `import()` dinamis.

```
       [Entry: App]
         /       \
   (static)     (dynamic)
       /           \
 [Dashboard]    [Analytics (import())]
       \           /
     (shared import)
           \   /
         [Lodash]
```

Mesin pemisah (*chunk split engine*) menyelesaikan dependensi ini melalui optimasi min-cut/max-flow:
- Dependensi bersama (*shared modules*) yang melebihi batas ukuran tertentu (`minSize`) atau jumlah penggunaan minimum (`minChunks`) diekstraksi ke dalam chunk terpisah (*common chunk* / *vendor chunk*).
- Tujuannya adalah mencegah duplikasi byte pada dynamic chunk sekaligus mencegah pembentukan *mega-chunks* yang memblokir proses rendering awal (First Contentful Paint / Largest Contentful Paint).

### 3.4. Module Federation v2 Runtime Architecture
Berbeda dengan isolated bundling, Module Federation membagi aplikasi menjadi Host dan Remotes di level runtime browser melalui *dynamic container protocol*.

```
+-------------------------------------------------------------+
| Browser Runtime                                             |
|                                                             |
|  [ Host Application Shell ]                                  |
|         │                                                   |
|         ├─── Fetch remoteEntry.js ────┐                     |
|         │                             ▼                     |
|  [ Shared Scope (Singleton Registry) ]                      |
|  { 'react': { version: '18.3.1', get: () => ... } }         |
|         │                             ▲                     |
|         │                             │ Resolve shared deps |
|         └─── Load Remote Component ───┤                     |
|                                       ▼                     |
|                             [ Remote Micro-frontend ]       |
+-------------------------------------------------------------+
```

1. **`remoteEntry.js`**: Manifest ringan yang diekspor oleh remote container, berisi antarmuka fungsi `init(sharedScope)` dan `get(moduleName)`.
2. **Shared Scope**: Objek singleton global di browser tempat Host dan Remote mendaftarkan dan memvalidasi kompatibilitas Semantic Versioning (SemVer) dari dependensi bersama (misal: `react`, `react-dom`).
3. **Fallback Negotiation**: Jika Remote membutuhkan `react@^18.2.0` dan Host menyediakan `react@18.3.1`, remote akan mengonsumsi instance Host. Jika versinya tidak kompatibel (misal breaking change antar versi major), remote memicu fallback untuk mengunduh salinan versinya sendiri tanpa merusak eksekusi Host.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Legacy Webpack/Babel) | Pendekatan Modern Enterprise (Rspack/Turborepo/CDN Pipeline) |
| :--- | :--- | :--- |
| **Parsing Engine** | JavaScript murni (V8 single-threaded parsing overhead, GC pause tinggi). | Native Systems Language (Rust/C++/Go multithreaded AST engine via Rayon/Goroutine pool). |
| **CI Cache Strategy** | Menyimpan seluruh direktori `node_modules` mentah via CI Cache (Raw extraction I/O lambat). | Deterministic computation hashing: hanya meng-cache input/output build artifacts (Remote Execution Hash). |
| **Code Splitting** | Manual runtime configuration, sering kali terjadi duplikasi pustaka vendor antar rute. | Graph-based optimization otomatis dengan static side-effect profiling dan shared chunk isolation. |
| **Asset Deployment** | Overwrite direktori build di web server (berisiko memicu mismatch hash jika user belum refresh). | Atomic immutable static storage upload, canary deployment, decoupling antara index.html dan hashed chunks. |
| **Quality Control** | Verifikasi pasca-deploy atau manual test lokal. | Automated performance budgets, AST-based security analysis, subresource integrity verification di pipeline. |

Mengapa arsitektur ini krusial? Pada aplikasi skala enterprise dengan jutaan pengguna aktif dan tim rekayasa terdistribusi:
1. **Build Time directly affects DORA Metrics**: Waktu build 20 menit pada monorepo menurunkan *Deployment Frequency* dan meningkatkan *Lead Time for Changes*. Pemotongan waktu ke <2 menit mengembalikan velocity tim secara drastis.
2. **Chunk Fragmentation Latency**: Chunk splitting yang salah dapat menghasilkan 300 chunk kecil yang menyebabkan TCP connection saturation (terutama via HTTP/1.1 atau cold-start HTTP/2 multiplexing limits), atau 1 bundle monolitik 5MB yang merusak skor Core Web Vitals (INP dan LCP).

---

## 5. How (Workflow Detail)

Alur kerja arsitektur build & pipeline produksi kelas enterprise:

```
[ Developer Commit ]
         │ (git push origin feature/xyz)
         ▼
[ Enterprise CI/CD Runner ]
         │
         ├── Phase 1: Hermetic Environment Setup (PNPM Frozen Lockfile)
         │
         ├── Phase 2: Static Analysis & Distributed Cache Check
         │     ├── Type-check (Parallel tsc --noEmit across affected pkgs)
         │     ├── Linting & Formatting (ESLint / Biome parallelized)
         │     └── Turborepo/Nx Remote Hash Query (S3/GCS Cache)
         │
         ├── Phase 3: Rust-based Matrix Compilation (Rspack / Vite)
         │     ├── Tree-shaking & Scope Hoisting
         │     ├── Dynamic Imports & Content Hashing ([name].[contenthash:16].js)
         │     └── SRI (Subresource Integrity) Generation
         │
         ├── Phase 4: Production Gating & Performance Budget Validation
         │     ├── Bundlesize Validation (Threshold checks)
         │     └── Sourcemap validation & Sentry upload (Private storage)
         │
         └── Phase 5: Atomic Deployment & CDN Invalidation
               ├── Upload immutable assets (*.js, *.css, *.webp) to CDN Bucket
               │   (Cache-Control: public, max-age=31536000, immutable)
               ├── Health Check Validation
               └── Deploy mutable entry point (index.html)
                   (Cache-Control: no-cache, no-transform)
```

---

## 6. Analogy & Diagram ASCII

Bayangkan bundler dan sistem CI/CD Anda seperti **Jaringan Logistik Perakitan Mobil Berkecepatan Tinggi**:

- **Kode Sumber Anda**: Komponen-komponen mekanik individual (baut, kabel, roda gigi).
- **Tree Shaking**: Inspektur kontrol kualitas yang menolak komponen yang tidak dipasang pada model mobil yang sedang dirakit. Jika Anda memesan kursi mobil standar, sistem tidak akan mengirimkan modul pendingin kursi mewah yang tidak terhubung.
- **Scope Hoisting**: Daripada memasukkan setiap sekrup ke dalam kotak plastik tersendiri (IIFE wrappers) yang memakan tempat di bagasi truk, seluruh sekrup langsung dipasang berdampingan pada satu sasis utama.
- **Deterministic Content Hash**: Barcode unik yang ditautkan langsung ke sidik jari struktural komponen. Jika desain baut berubah 0.01 mm, barcodenya berubah total.
- **CI Remote Caching**: Jika pabrik sebelumnya sudah merakit pintu mobil dengan spesifikasi identik, pabrik tidak merakitnya kembali dari nol; mereka cukup mengambil pintu siap pakai dari gudang sentral seketika.

```
       KODE MODULAR (ESM)                    CHUNKS TEROPTIMASI (PRODUCTION)
+-------------------------------+        +-----------------------------------+
| Module A: export function x() |        |           Entry Chunk             |
| Module B: export function y() | -----> |  (Scope-Hoisted Execution Scope)  |
| Module C: unusedFunction()    |        |  function x() { ... }             |
+-------------------------------+        |  // Module C dibuang (Shaken out) |
                                         +-----------------------------------+
                                                           │
                                        Dynamically Loaded via import()
                                                           ▼
                                         +-----------------------------------+
                                         |         Vendor/Async Chunk        |
                                         |  [Hash: a1b2c3d4e5f6g7h8]         |
                                         |  Framework core + Shared Libs     |
                                         +-----------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Demonstrasi Side-Effects dan Tree Shaking

Perhatikan struktur paket internal utilitas:

```typescript
// packages/utils/src/math.ts
export function add(a: number, b: number): number {
  return a + b;
}

export function subtract(a: number, b: number): number {
  return a - b;
}

// Global side-effect (Mencegah Dead Code Elimination jika tidak diisolasi!)
export const trackMathInit = (() => {
  if (typeof window !== 'undefined') {
    (window as any).__MATH_INITIALIZED__ = true;
  }
})();
```

Konfigurasi `package.json` untuk mengisolasi efek samping:
```json
{
  "name": "@enterprise/utils",
  "version": "1.0.0",
  "main": "./dist/index.cjs",
  "module": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "sideEffects": false
}
```
*Catatan*: Menandai `"sideEffects": false` memberitahu engine bundler bahwa pemanggilan ekspor yang tidak dikonsumsi dapat diabaikan sepenuhnya, termasuk penghapusan inisialisasi `trackMathInit` jika tidak diimpor langsung.

---

### 7.2. Practical Example: Production Rspack Configuration dengan SplitChunks Presisi

Konfigurasi produksi tingkat lanjut menggunakan `@rspack/cli` dan plugin industri:

```typescript
// rspack.config.ts
import { defineConfig } from '@rspack/cli';
import rspack from '@rspack/core';
import path from 'node:path';

const isProduction = process.env.NODE_ENV === 'production';

export default defineConfig({
  context: __dirname,
  entry: {
    main: './src/index.tsx',
  },
  mode: isProduction ? 'production' : 'development',
  devtool: isProduction ? 'source-map' : 'eval-cheap-module-source-map',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: isProduction ? 'static/js/[name].[contenthash:16].js' : 'static/js/[name].js',
    chunkFilename: isProduction ? 'static/js/[name].[contenthash:16].chunk.js' : 'static/js/[name].chunk.js',
    assetModuleFilename: 'static/media/[name].[contenthash:16][ext]',
    clean: true,
    publicPath: process.env.CDN_URL || '/',
    crossOriginLoading: 'anonymous', // Wajib untuk SRI (Subresource Integrity)
  },
  resolve: {
    extensions: ['.ts', '.tsx', '.js', '.jsx'],
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  module: {
    rules: [
      {
        test: /\.(jsx?|tsx?)$/,
        use: [
          {
            loader: 'builtin:swc-loader',
            options: {
              jsc: {
                parser: {
                  syntax: 'typescript',
                  tsx: true,
                  dynamicImport: true,
                },
                transform: {
                  react: {
                    runtime: 'automatic',
                    refresh: !isProduction,
                  },
                },
              },
            },
          },
        ],
      },
    ],
  },
  optimization: {
    minimize: isProduction,
    splitChunks: {
      chunks: 'all',
      minSize: 20000,
      maxAsyncRequests: 30,
      maxInitialRequests: 30,
      cacheGroups: {
        defaultVendors: false, // Matikan default vendor konfigurasi yang naive
        default: false,
        // Chunk Khusus Framework Runtime (Sangat Rendah Frekuensi Perubahan)
        framework: {
          test: /[\\/]node_modules[\\/](react|react-dom|scheduler|react-router-dom)[\\/]/,
          name: 'vendor-framework',
          chunks: 'all',
          priority: 40,
          enforce: true,
        },
        // Libs berat independen yang jarang berubah
        heavyVendors: {
          test: /[\\/]node_modules[\\/](lodash-es|date-fns|zod)[\\/]/,
          name: 'vendor-shared-lib',
          chunks: 'all',
          priority: 30,
        },
        // Sisa module node_modules dikelompokkan berdasarkan batas byte
        commons: {
          test: /[\\/]node_modules[\\/]/,
          name(module: any) {
            const packageName = module.context.match(/[\\/]node_modules[\\/](?:(@[^\\/]+[\\/][^\\/]+)|([^\\/]+))/);
            return `npm.${(packageName ? (packageName[1] || packageName[2]) : 'unknown').replace('@', '').replace('/', '.')}`;
          },
          chunks: 'async',
          priority: 20,
          minChunks: 2,
          reuseExistingChunk: true,
        },
      },
    },
    runtimeChunk: {
      name: 'runtime', // Menghindari cache invalidation pada entrypoint saat hash chunk berubah
    },
  },
  plugins: [
    new rspack.HtmlRspackPlugin({
      template: './public/index.html',
      scriptLoading: 'defer',
      minify: isProduction,
    }),
    new rspack.SubresourceIntegrityPlugin({
      hashFuncNames: ['sha384'],
      enabled: isProduction,
    }),
  ],
});
```

### 7.3. Production CI/CD Pipeline (GitHub Actions Engine)
Pipeline deterministik hermetik dengan Turborepo caching, security verification, dan atomic CDN deployment.

```yaml
# .github/workflows/production-deploy.yml
name: Production Frontend Pipeline

on:
  push:
    branches: [main]

concurrency:
  group: prod-deployment-${{ github.ref }}
  cancel-in-progress: false # Jangan batalkan deployment produksi yang sedang berlangsung!

jobs:
  validate-and-compile:
    name: Build, Gate & Deploy
    runs-on: ubuntu-latest
    timeout-minutes: 25
    steps:
      - name: Checkout Source
        uses: actions/checkout@v4
        with:
          fetch-depth: 0 # Dibutuhkan Turborepo untuk git diff graph calculation

      - name: Setup Node.js Runtime
        uses: actions/setup-node@v4
        with:
          node-version: 20.14.0

      - name: Setup PNPM Package Manager
        uses: pnpm/action-setup@v3
        with:
          version: 9.1.0
          run_install: false

      - name: Get PNPM Store Directory
        shell: bash
        run: echo "STORE_PATH=$(pnpm store path --silent)" >> $GITHUB_ENV

      - name: Cache PNPM Store
        uses: actions/cache@v4
        with:
          path: ${{ env.STORE_PATH }}
          key: ${{ runner.os }}-pnpm-store-${{ hashFiles('**/pnpm-lock.yaml') }}
          restore-keys: |
            ${{ runner.os }}-pnpm-store-

      - name: Hermetic Dependency Installation
        run: pnpm install --frozen-lockfile

      - name: Turborepo Distributed Remote Cache Setup
        uses: actions/cache@v4
        with:
          path: .turbo
          key: ${{ runner.os }}-turbo-${{ github.sha }}
          restore-keys: |
            ${{ runner.os }}-turbo-

      - name: Static Type Validation & Linting
        run: |
          pnpm turbo run lint type-check --cache-dir=.turbo

      - name: Compile Production Artifacts
        run: |
          pnpm turbo run build --cache-dir=.turbo
        env:
          NODE_ENV: production
          CDN_URL: https://static.cdn-enterprise.com/assets/

      - name: Verify Bundle Budgets
        run: |
          pnpm dlx bundlesize
        env:
          BUNDLESIZE_GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Configure Cloud Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_PROD_ACCESS_KEY }}
          aws-secret-access-key: ${{ secrets.AWS_PROD_SECRET_KEY }}
          aws-region: us-east-1

      # STRATEGI ATOMIC CDN DEPLOYMENT
      # Step 1: Upload hashed static assets (Immutable, Long TTL)
      - name: Sync Immutable Static Assets to S3/CDN
        run: |
          aws s3 sync dist/static s3://production-frontend-bucket/assets/static \
            --exclude "*.html" \
            --cache-control "public, max-age=31536000, immutable" \
            --metadata-directive REPLACE

      # Step 2: Upload mutable root entry files (Index, Manifests, Short/No TTL)
      - name: Deploy Mutable Entry Point (Atomic Cutover)
        run: |
          aws s3 sync dist/ s3://production-frontend-bucket/assets/ \
            --exclude "static/*" \
            --cache-control "public, max-age=0, must-revalidate" \
            --metadata-directive REPLACE

      # Step 3: Invalidate Edge Cache untuk index.html secara presisi
      - name: Invalidate CloudFront CDN Index
        run: |
          aws cloudfront create-invalidation \
            --distribution-id ${{ secrets.CLOUDFRONT_DIST_ID }} \
            --paths "/index.html" "/manifest.json"
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Global Fintech Monorepo Migration (700+ Engineers, 4 Juta LOC)
Sebuah institusi perbankan multinasional mengalami degradasi performa pipeline:
- **Status Awal**:
  - Bundler: Webpack 5 monolitik dengan Babel.
  - CI Build Duration: Rata-rata 42 menit per PR build.
  - Runtime Problem: Terjadi insiden *ChunkLoadError* berulang saat release tengah hari akibat user lama masih memegang referensi hash chunk yang langsung dihapus dari bucket server saat deployment versi baru berjalan.

### Solusi Rekayasa Platform:
1. **Engine Modernization**: Migrasi core bundling ke **Rspack** berbasis Rust. Parser diisolasi menggunakan SWC compiler tanpa melewati overhead context bridge Node-to-Rust secara redundan.
2. **Deterministic Build Graphing**: Implementasi **Turborepo** self-hosted remote cache menggunakan S3 + MinIO. Modul yang tidak terdampak git commit diff langsung menerima status `[FULL TURBO]` cache hit.
3. **Dual-Phase CDN Staging**:
   - Skrip deployment diubah untuk menggunakan *Additive Retention Strategy*. File statis lama di bucket S3 dipertahankan selama $N+14$ hari (Retention Period).
   - Penambahan `crossOriginLoading: 'anonymous'` dan `SubresourceIntegrityPlugin` untuk mencegah serangan man-in-the-middle pada node edge CDN pihak ketiga.
4. **Hasil Kuantitatif**:
   - CI Build Time terpangkas dari **42 menit** menjadi **3 menit 12 detik** (peningkatan kecepatan ~13x).
   - Insiden kegagalan chunk loading (`ChunkLoadError`) berkurang hingga **0.00%** pada monitoring Sentry.
   - Core Web Vitals (LCP) global meningkat 28% berkat optimalisasi *cacheGroups* framework singleton.

---

## 9. Trade-offs

| Pendekatan / Teknologi | Keuntungan (Pros) | Biaya / Kerugian (Cons & Trade-offs) |
| :--- | :--- | :--- |
| **Aggressive Granular Chunk Splitting** | Memaksimalkan browser caching hit ratio; perubahan 1 file kode hanya menginvalidasi chunk kecil (<10KB). | Menimbulkan fenomena *Request Waterfall* dan koneksi overhead jika protokol HTTP/2 atau edge CDN tidak terkonfigurasi optimal. |
| **Module Federation (MFE Runtime)** | Deployment otonom per tim independen tanpa harus memicu rebuild shell utama aplikasi. | Kompleksitas tinggi dalam runtime dependency management, debugging call-stack antar batas container sangat sulit. |
| **Native Tooling (Rspack / esbuild)** | Kecepatan eksekusi AST parsing dan kompilasi luar biasa cepat (memanfaatkan multithreading natively). | Ekosistem plugin tidak seluas Webpack berbasis JavaScript. Menulis custom plugin membutuhkan pemahaman Rust API atau FFI. |
| **Subresource Integrity (SRI)** | Keamanan mutlak: mencegah manipulasi script injection jika CDN / S3 bucket disusupi hacker. | Sangat sensitif terhadap proses delivery: sedikit saja manipulasi proxy edge atau transformasi gzip/brotli yang merusak bit akan memicu script error total di browser. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal Caching `index.html`
- **Gejala**: Pengguna melaporkan tampilan aplikasi masih versi lama atau aplikasi mendadak blank dengan error: `Failed to fetch dynamically imported module`.
- **Akar Masalah**: Web server / CDN menyajikan `index.html` dengan header `Cache-Control: public, max-age=31536000`. Browser menyimpan `index.html` lokal selama setahun yang masih mengarah ke chunk hash lama yang sudah tidak tersedia di server.
- **Solusi**: Atur header `index.html` ke `Cache-Control: no-cache, no-store, must-revalidate`. Hanya file berekstensi dengan content hash (misal `.1a2b3c.js`) yang boleh diberi `max-age=31536000, immutable`.

### 10.2. Barrel Files Membunuh Tree Shaking
- **Gejala**: Bundle size membengkak puluhan megabyte meskipun hanya mengimpor satu helper icon.
- **Akar Masalah**: Pola *Barrel Export* (`index.ts` yang mengekspor seluruh direktori `export * from './components'`). Jika salah satu komponen memiliki *side effect* atau transitive dependency besar, bundler akan mengimpor seluruh pohon dependency tersebut.
- **Solusi**: 
  1. Hindari deep barrel re-exports pada library internal.
  2. Gunakan konfigurasi compiler plugin seperti `transform-imports` / SWC `modularizeImports` untuk meratakan path saat kompilasi:
     ```json
     {
       "transform": {
         "modularizeImports": {
           "lucide-react": {
             "transform": "lucide-react/dist/esm/icons/{{kebabCase member}}"
           }
         }
       }
     }
     ```

### 10.3. Non-Deterministic Hashes di Antara Runner CI
- **Gejala**: Turborepo cache miss terus-menerus terjadi meskipun tidak ada perubahan kode logika.
- **Akar Masalah**: Injeksi absolut path saat build (misal `/home/runner/work/...` vs `/root/app/...`), format line-ending OS (CRLF vs LF), atau timestamp nondeterministik yang ditambahkan pada runtime source code.
- **Solusi**: Standarisasi environment build menggunakan isolated container (Docker), enforce LF via `.gitattributes`, dan pastikan bundler menggunakan `deterministic` module IDs:
  ```typescript
  optimization: {
    moduleIds: 'deterministic',
    chunkIds: 'deterministic',
  }
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Lockfile Determinism**: CI wajib menggunakan flag instalasi ketat: `pnpm install --frozen-lockfile` (atau `npm ci`).
- [ ] **Zero DevDependencies in Production Output**: Verifikasi bahwa tidak ada tools test atau mocking (Jest, Vitest, MSW) yang lolos ke bundle release final.
- [ ] **Strict Module Boundary Isolation**: Gunakan atribut `"sideEffects": false` pada package monorepo yang berstatus pure function.
- [ ] **Automated Performance Gates**: Integrasikan Lighthouse CI atau `bundlesize` pada pipeline Pull Request untuk memblokir merger PR jika ukuran bundle naik melebihi toleransi (>5% threshold).
- [ ] **Private Sourcemaps**: Generate `.map` files untuk integrasi telemetry (misal: Sentry, Datadog), tetapi **jangan** upload sourcemap ke CDN publik. Hapus sourcemap sebelum step sync ke S3 publik.
- [ ] **Immutable Infrastructure Lifecycle**: File statis ber-hash di bucket penyimpanan tidak boleh dihapus saat deployment baru selesai. Terapkan AWS S3 Lifecycle Rules untuk menghapus file lama hanya setelah $N$ hari.

---

## 12. Hands-on Practice: Membangun Production-Ready Build & Invalidation Engine

Simpan seluruh file praktikum ini ke dalam direktori: `hands-on/m02/`

### File 1: `package.json`
```json
{
  "name": "enterprise-build-lab",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "build": "rspack build",
    "serve": "node server.mjs"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@rspack/cli": "^0.7.5",
    "@rspack/core": "^0.7.5",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "typescript": "^5.4.5"
  }
}
```

### File 2: `rspack.config.js`
```javascript
const path = require('node:path');
const rspack = require('@rspack/core');

module.exports = {
  entry: './src/index.tsx',
  mode: 'production',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'assets/[name].[contenthash:8].js',
    chunkFilename: 'assets/[name].[contenthash:8].chunk.js',
    clean: true,
  },
  resolve: {
    extensions: ['.ts', '.tsx', '.js'],
  },
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        use: {
          loader: 'builtin:swc-loader',
          options: {
            jsc: {
              parser: { syntax: 'typescript', tsx: true },
              transform: { react: { runtime: 'automatic' } },
            },
          },
        },
      },
    ],
  },
  optimization: {
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        vendor: {
          test: /[\\/]node_modules[\\/]/,
          name: 'framework-vendors',
          chunks: 'all',
        },
      },
    },
  },
  plugins: [
    new rspack.HtmlRspackPlugin({
      template: './src/index.html',
    }),
  ],
};
```

### File 3: `src/index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Enterprise Build Artifact</title>
</head>
<body>
  <div id="root"></div>
</body>
</html>
```

### File 4: `src/HeavyMathModule.tsx`
```typescript
import React from 'react';

export default function HeavyMathModule() {
  return (
    <div style={{ padding: '1rem', border: '1px solid #ccc', marginTop: '1rem' }}>
      <h3>Dynamically Loaded Heavy Subsystem</h3>
      <p>Loaded via Dynamic Import Split Point.</p>
    </div>
  );
}
```

### File 5: `src/index.tsx`
```typescript
import React, { Suspense, lazy, useState } from 'react';
import { createRoot } from 'react-dom/client';

const HeavyMathModule = lazy(() => import('./HeavyMathModule'));

function App() {
  const [showSubsystem, setShowSubsystem] = useState(false);

  return (
    <main style={{ fontFamily: 'sans-serif', padding: '2rem' }}>
      <h1>Enterprise Production Bundling Engine</h1>
      <button onClick={() => setShowSubsystem((prev) => !prev)}>
        Toggle Async Code-Split Chunk
      </button>

      {showSubsystem && (
        <Suspense fallback={<div>Loading isolated chunk...</div>}>
          <HeavyMathModule />
        </Suspense>
      )}
    </main>
  );
}

const container = document.getElementById('root');
if (container) {
  createRoot(container).render(<App />);
}
```

### File 6: `server.mjs` (Simulasi Production CDN Header Engine)
```javascript
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = 3000;
const DIST_DIR = path.resolve(__dirname, 'dist');

const server = http.createServer((req, res) => {
  let reqPath = req.url === '/' ? '/index.html' : req.url;
  const filePath = path.join(DIST_DIR, reqPath);

  if (!fs.existsSync(filePath)) {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('404 Not Found');
    return;
  }

  // ATUR STRATEGI HEADER SESUAI STANDAR ARSITEKTUR
  if (reqPath.endsWith('.html')) {
    // Entry Point: Tidak boleh di-cache browser secara permanen!
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    res.setHeader('Content-Type', 'text/html');
  } else if (reqPath.startsWith('/assets/')) {
    // Immutable Asset: Cache selama 1 tahun di browser & CDN
    res.setHeader('Cache-Control', 'public, max-age=31536000, immutable');
    if (reqPath.endsWith('.js')) res.setHeader('Content-Type', 'application/javascript');
    if (reqPath.endsWith('.css')) res.setHeader('Content-Type', 'text/css');
  }

  fs.createReadStream(filePath).pipe(res);
});

server.listen(PORT, () => {
  console.log(`Production Mock Server berjalan di http://localhost:${PORT}`);
});
```

### Eksekusi Praktikum:
```bash
# 1. Install dependensi
pnpm install

# 2. Compile bundle produksi
pnpm run build

# 3. Jalankan server simulasi produksi
pnpm run serve
```
Periksa network tab browser: amati header `Cache-Control` dari request `index.html` (no-cache) berbanding request file di dalam folder `/assets/` (immutable).

---

## 13. Exercises

### Level: Easy
Analisis berkas bundle Anda. Temukan ukuran total raw vs gzipped size dari chunk `framework-vendors`. Tulis skrip Node.js kecil menggunakan pustaka `zlib` untuk mencetak persentase reduksi ukuran file secara otomatis.

### Level: Medium
Modifikasi file `rspack.config.js` pada hands-on di atas untuk menambahkan visualizer analyzer bundle (`webpack-bundle-analyzer` atau `@rspack/plugin-bundle-analyzer`). Konfigurasikan outputnya agar menghasilkan report statis format HTML di direktori `.reports/bundle-report.html` hanya jika environment variable `ANALYZE=true` diaktifkan.

### Level: Hard
Tulis custom SWC AST visitor plugin (atau Babel transformer script terisolasi) yang mendeteksi setiap pemanggilan `console.log()` di seluruh source code dan menggantinya dengan identifier `void 0` saat build production berjalan, tanpa menghapus pemanggilan `console.error()` atau `console.warn()`.

---

## 14. Challenge (Arsitektur Riil Kompleks)

**Studi Kasus Arsitektur Tanpa Solusi Instan:**
Anda adalah Principal Architect pada startup Super-App FinTech. Aplikasi Anda melayani 10 juta DAU (*Daily Active Users*) dengan arsitektur micro-frontend (Module Federation v2) yang terdiri dari Host Shell dan 8 Remote Container yang dideploy oleh tim berbeda secara independen.

**Skenario Bencana:**
Tim tim inti merilis patch zero-day untuk pustaka keamanan autentikasi (`@corp/auth`). Namun, tim Remote Payments belum melakukan deployment ulang, sementara tim Remote Checkout melakukan deployment dengan versi patch yang baru. Terjadi benturan runtime (*runtime prototype crash*) di perangkat browser pengguna lama yang mengakibatkan terblokirnya transaksi senilai puluhan miliar rupiah.

**Tugas Arsitektural Anda:**
1. Rancang arsitektur Module Federation manifest discovery yang menjamin strict isolation antar sub-aplikasi tanpa merusak benefit shared memory cache.
2. Definisikan strategi mitigasi kegagalan runtime (Boundary Fallback Engine) jika remote container eksternal gagal di-fetch (misal status HTTP 500 dari CDN remote).
3. Buat rancangan spesifikasi deployment pipeline end-to-end yang mencegah Host Shell meload Remote yang belum tersertifikasi kompatibel secara SemVer di manifest sentral.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Pemahaman Konseptual (Basic)
1. Mengapa sintaks ESM (`import`/`export`) wajib digunakan sebagai basis algoritma Tree Shaking alih-alih `require()` CommonJS?
2. Apa tujuan teknis utama di balik pemisahan penamaan chunk menggunakan pola `[name].[contenthash].js`?
3. Apa perbedaan fungsional antara `max-age=31536000` dengan ditambahkan atribut `immutable` pada header HTTP response?
4. Mengapa meletakkan deklarasi `"sideEffects": false` secara sembarangan di package yang memodifikasi CSS global via import direct (`import './style.css'`) dapat merusak UI saat proses build produksi?
5. Mengapa native bundler berbasis Rust/Go mampu memproses AST jauh lebih cepat dibandingkan bundler native berbasis Node.js?

### Bagian B: Pemahaman Penerapan (Intermediate)
6. Bagaimana cara kerja mekanisme *Runtime Chunk Isolation* (`runtimeChunk: { name: 'runtime' }`) dalam mencegah cache invalidation pada seluruh bundle ketika satu baris kode diubah?
7. Dalam arsitektur monorepo, apa yang menjadi parameter hash penentu bahwa suatu task di Turborepo/Nx berstatus *cache hit*?
8. Apa konsekuensi teknis jika kita mengaktifkan Subresource Integrity (SRI) pada HTML, tetapi file JavaScript di CDN ditransformasi/dimodifikasi on-the-fly oleh optimasi edge CDN (misal Cloudflare Auto-Minify)?
9. Bagaimana strategi pemecahan chunk (*splitChunks*) yang optimal untuk menangani pustaka utility berukuran besar seperti `lodash-es` agar tidak menduplikasi isi kodenya di beberapa chunk dinamis?
10. Mengapa pipeline CI/CD produksi harus selalu menggunakan flag `pnpm install --frozen-lockfile` dan bukan sekadar `pnpm install`?

### Bagian C: Analisis Skenario Kasus Produksi
11. **Skenario 1**: Setelah deployment versi baru, 5% pengguna Anda di negara dengan koneksi buruk mengeluhkan munculnya error layar putih bertuliskan `ChunkLoadError: Loading chunk 402 failed`. Investigasi log CDN menunjukkan file chunk 402 mengembalikan HTTP 404. Jelaskan urutan rantai kejadian yang memicu hal ini dan bagaimana rancangan pipeline atomic CDN deployment dapat melenyapkan isu tersebut secara permanen!
12. **Skenario 2**: Ukuran bundle monorepo Anda melonjak 400KB secara tiba-tiba dalam satu Pull Request. Padahal developer bersangkutan bersumpah hanya mengimpor fungsi `formatDate` dari library internal. Bagaimana Anda melacak, membuktikan penyebabnya di AST/Graph, dan memblokir regresi tersebut secara otomatis di level CI?
13. **Skenario 3**: Sebuah aplikasi e-commerce memiliki batas LCP target di bawah 1.8 detik. Laporan performa menunjukkan eksekusi JavaScript memblokir main thread selama 1.2 detik saat mem-parse vendor bundle berukuran 1.5MB. Jelaskan rancangan arsitektur chunking dan resource loading hints (`preload`, `prefetch`) yang harus diterapkan untuk membagi beban komputasi tersebut.

---

## 16. Kunci Jawaban Quiz

### Bagian A
1. **Dasar ESM untuk Tree Shaking**: ESM bersifat *statis*, artinya struktur dependensi dianalisis pada compile time sebelum kode dijalankan. CommonJS bersifat *dinamis* (bisa memanggil `require('./mod/' + variable)` di dalam conditional loop), sehingga bundler tidak dapat memastikan secara deterministik simbol mana yang dipakai tanpa mengeksekusi kode secara penuh.
2. **Tujuan `contenthash`**: Menjamin *cache busting* presisi. Hash dikalkulasi langsung dari isi konten file fisik. Jika konten tidak berubah, hash tetap sama (browser menggunakan memory/disk cache). Jika konten berubah satu karakter saja, hash berganti dan browser dipaksa mengunduh versi terbaru.
3. **Fungsi `immutable`**: Atribut `immutable` memberi tahu browser bahwa selama masa validitas `max-age`, file tersebut dijamin tidak akan pernah berubah di server. Browser dilarang mengirim conditional revalidation request (`304 Not Modified` via `If-None-Match`/`ETag`) bahkan saat pengguna menekan tombol reload/refresh biasa.
4. **Resiko `"sideEffects": false`**: File CSS yang diimpor langsung (misal `import './style.css'`) tidak mengekspor identifier JavaScript apa pun. Jika bundler diinstruksikan bahwa modul tersebut murni tanpa side-effect, seluruh impor CSS tersebut akan dihapus (*pruned*) dari bundle output karena dianggap dead code.
5. **Kecepatan Native Bundler**: Bahasa native (Rust/Go) tidak berjalan di atas virtual machine dengan overhead Garbage Collection (GC) pauses seperti V8. Memori diatur secara presisi (linear allocation/arena allocators), dan pemrosesan parsing AST dieksekusi secara concurrent/multithreaded murni memanfaatkan seluruh core CPU yang tersedia tanpa batas message-passing Web Workers.

### Bagian B
6. **Isolasi Runtime Chunk**: *Runtime chunk* berisi manifest pemetaan ID chunk ke content hash fisiknya. Jika runtime disatukan dengan entry chunk, perubahan pada *child chunk* mana pun akan mengubah hash manifest runtime, yang otomatis mengubah hash entry point. Memisahkan runtime ke file tersendiri mengisolasi mutasi hash tersebut.
7. **Komponen Hash Turborepo/Nx**: Hash dihitung dari gabungan: hash hash berkas source code git commit, hash dependency di lockfile, environment variable yang didefinisikan di `turbo.json`, serta task invocation command flags.
8. **Konsekuensi SRI vs Edge Transformation**: Hash SHA browser yang tercatat di atribut `<script integrity="sha384-xyz...">` tidak akan cocok lagi dengan hash bit konten file yang telah diubah oleh edge server. Browser akan memblokir eksekusi script dengan status Security Violation demi mencegah serangan injeksi.
9. **Optimalisasi Splitting Utility**: Pindahkan pustaka utility ke cacheGroup tersendiri dengan mode `chunks: 'all'`, `reuseExistingChunk: true`, dan `minChunks: 2`. Lebih optimal lagi dengan memberlakukan ESM tree-shaking native (misal mengimpor dari `lodash-es` atau substitusi fungsi ke native browser ES APIs).
10. **Tujuan `--frozen-lockfile`**: Mencegah runner CI memperbarui atau menulis ulang isi lockfile jika ada inkonsistensi antara `package.json` dan lockfile. Jika ada dependensi yang tidak sinkron, pipeline akan langsung melempar error dan gagal (*fail-fast*), menjamin artefak build CI identik 100% dengan lingkungan lokal developer.

### Bagian C
11. **Analisis Skenario 1 (ChunkLoadError Root Cause)**:
    - *Rantai Kejadian*: Pengguna membuka aplikasi pada versi $V_1$. Versi baru $V_2$ dideploy dengan menghapus isi folder aset lama di CDN. Pengguna lama menavigasi ke rute baru via lazy load dynamic import. Browser meminta chunk hash milik $V_1$ yang sudah dimusnahkan dari server storage, memicu HTTP 404 dan runtime crash.
    - *Solusi*: Terapkan *Atomic Additive Deployment*. Pipeline dilarang menghapus (*prune*) chunk lama saat sync. Bucket CDN diatur menggunakan retensi ganda: simpan seluruh file lama selama minimal 14 hari, dan pasang error handling pada lazy import untuk melakukan dynamic reload page (`window.location.reload()`) jika terdeteksi chunk gagal dimuat.
12. **Analisis Skenario 2 (Regresi Ukuran Bundle)**:
    - *Identifikasi*: Terjadi fenomena *Barrel File Poisoning*. File import internal menggunakan root export index yang memuat ketergantungan transitive ke library berat lain.
    - *Pelacakan*: Gunakan `webpack-bundle-analyzer` atau flag `--analyze` untuk melihat dependency trace map.
    - *Pencegahan CI*: Konfigurasikan library `bundlesize` atau PR status check GitHub Actions yang membaca diff size secara otomatis. Tentukan batas ambang maksimal per chunk (contoh: alert jika delta PR $>15\text{ KB}$).
13. **Analisis Skenario 3 (Long-Task LCP Minimization)**:
    - *Arsitektur Pemecahan*: Pecah 1.5MB vendor monolitik menjadi 3 lapisan cache group: `framework` (React/Router ~150KB), `commons` (dependensi fungsional UI ~200KB), dan `async-features` (komponen berat dimuat via `React.lazy` saat interaksi).
    - *Loading Hints*: Sisipkan `<link rel="preload" as="script" href="...">` hanya untuk critical entry script dan framework vendor. Gunakan dynamic `<link rel="prefetch">` untuk modul rute yang memiliki probabilitas tinggi diklik oleh pengguna (hover intent), sehingga CPU browser melakukan parsing dan eksekusi secara bertahap tanpa memblokir First Input Delay (FID) / Interaction to Next Paint (INP).

---

## 17. Summary

1. **Compiler Architecture**: Modern bundling telah berevolusi dari sekadar penggabungan string (bundling) menjadi pipeline compiler utuh berbasis bahasa native systems (Rust/Go) dengan optimasi direct memory graph.
2. **Static Dead Code Elimination**: Tree Shaking dan Scope Hoisting bergantung mutlak pada integritas deklarasi ECMAScript Modules (ESM) murni dan side-effect profiling yang ketat di tingkat arsitektur package.
3. **Deterministic Continuous Delivery**: Pembangunan pipeline CI/CD kelas enterprise menuntut reproduktibilitas mutlak: pemanfaatan frozen lockfile, distributed computation cache hashing, dan decoupling kompilasi terhadap absolute environment paths.
4. **Atomic CDN Delivery Strategy**: Arsitektur hosting static frontend modern memisahkan penanganan aset menjadi dua domain: Entry point (`index.html`) yang bersifat dinamis/revalidated, dan Chunks statis yang bersifat immutable dan additive guna menjamin zero-downtime dan mitigasi crash chunk loading.