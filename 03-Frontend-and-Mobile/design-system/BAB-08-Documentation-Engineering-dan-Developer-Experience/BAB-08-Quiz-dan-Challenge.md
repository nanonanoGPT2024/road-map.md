# BAB 08: Quiz, Challenge, & Knowledge Check
**Documentation Engineering & Developer Experience (DX)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Static AST Parsing vs Semantic Type Checking pada Prop Extraction**
   Jelaskan perbedaan arsitektural antara static AST parsing (misal: `react-docgen` berbasis `@babel/parser`) dan semantic type evaluation (misal: `react-docgen-typescript` berbasis TypeScript `TypeChecker` API). Mengapa static AST parser sering kali gagal mengekstrak metadata pada utility types tingkat lanjut (seperti `Omit`, `Pick`, conditional types, dan template literal types), dan apa trade-off performa yang harus dibayar saat beralih ke semantic checking?

2. **Arsitektur Eksekusi Component Story Format (CSF 3.0) vs MDX**
   Bandingkan alur kompilasi dan render pipeline antara CSF 3.0 (objek JavaScript murni dengan deklarasi static metadata) dan MDX (Markdown + JSX transpilasi). Tinjau dari sudut pandang tree-shaking, static analysis tooling (LSP, automated linting), dan efisiensi *incremental static regeneration* saat mendokumentasikan ribuan varian komponen.

3. **Isolasi Lingkungan Eksekusi pada Interactive Live Playground**
   Ketika menyediakan *live code editor* interaktif di dalam portal dokumentasi (misal: menggunakan Sandpack atau custom Monaco + iframe runner), jelaskan model isolasi keamanan yang wajib diterapkan. Bagaimana arsitektur komunikasi dua arah (`postMessage`, `MessageChannel`) diatur agar modifikasi DOM atau injeksi script arbitrer tidak merusak context portal dokumentasi utama, sekaligus mencegah eksfiltrasi token otentikasi?

4. **Paradigma 'Documentation Drift' dan Strategi Mitigasi Programatik**
   Definisikan apa yang dimaksud dengan *documentation drift* dalam siklus hidup Design System skala enterprise. Mengapa pengujian manual tidak memadai untuk mencegahnya? Uraikan mekanisme validasi berbasis CI (*automated doc-testing*, schema validation, linting coverage) untuk menjamin bahwa perubahan pada props, CSS tokens, atau accessibility contract secara otomatis memicu pembaruan atau kegagalan build dokumentasi.

5. **Token-to-Documentation Synchronization Pipeline**
   Dalam arsitektur *Design Tokens as Single Source of Truth* (SSOT), bagaimana pipeline otomatisasi mentransformasikan definisi token (JSON/W3C format) menjadi dokumentasi interaktif yang mencakup semantic alias, resolved fallback value, dark/light theme matrix, dan visual preview? Sebutkan titik integrasi antara *Style Dictionary* (atau Token Transformer) dan generator dokumentasi.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Debugging Memory Overhead dan Infinite Loop pada TypeScript Compiler API**
   Anda mengonfigurasi `ts.createProgram` untuk mengekstrak props dari komponen polimorfik kompleks:
   ```typescript
   export type PolymorphicComponentPropWithRef<E extends React.ElementType, P> = 
     React.PropsWithChildren<P & AsProp<E>> & 
     Omit<React.ComponentPropsWithRef<E>, keyof (AsProp<E> & P)>;
   ```
   Saat memproses library dengan 200+ komponen polimorfik, proses ekstraksi docgen mengalami *heap out of memory* (OOM) atau berjalan lambat (>10 menit). Analisis di layer mana bottleneck TypeScript `TypeChecker` terjadi dan bagaimana strategi caching `ts.Program`, restriksi resolusi node `lib.dom.d.ts`, serta pemangkasan rekursi *union types* diterapkan.

2. **Troubleshooting Barrel Export Resolution pada Docgen Tooling**
   Sebuah design system mengekspor komponen via mono-barrel file:
   `packages/core/src/index.ts -> export * from './components/button'`.
   Tool dokumentasi gagal menghasilkan deskripsi JSDoc dan mendeteksi tipe komponen sebagai `any` atau `Component<any>`. Komponen di-*re-export* menggunakan nama alias dan HOC (Higher-Order Component) `React.memo(React.forwardRef(...))`. Uraikan langkah diagnostik untuk menelusuri penelusuran simbol (`aliasedSymbol`) via TypeScript AST dan cara merekonstruksi docgen resolver agar dapat mengekstrak metadata dari deklarasi dasar (*underlying component implementation*).

3. **Dynamic MDX Bundling Runtime Mismatch dan Hydration Failure**
   Saat menggunakan engine MDX dinamis di portal dokumentasi berbasis SSR/SSG (seperti `next-mdx-remote` atau `mdx-bundler`), halaman dokumentasi melempar error *Text content did not match server-rendered HTML*. Masalah terjadi secara eksklusif pada dokumen yang memiliki blok kode interaktif dengan dynamic import tema (dark/light). Bagaimana proses serialisasi state `scope` MDX bekerja, dan bagaimana cara mendesain hydration-safe live preview component?

4. **AST-Based Linting untuk Menegakkan Standar Dokumentasi (Unified/Remark Engine)**
   Rancang arsitektur custom linter menggunakan ekosistem `unified` / `remark` / `unist-util-visit` untuk memvalidasi dokumen MDX pada Pull Request. Aturan linter harus memverifikasi bahwa:
   - Setiap file komponen memiliki metadata frontmatter valid (`title`, `status`, `figma_url`).
   - Setiap heading H2 memiliki tautan target valid.
   - Komponen `<LivePlayground>` tidak boleh memuat import dari package eksternal selain token internal dan library UI tersebut.

5. **Multi-Version Portal Deployment dengan Monorepo Version Skew**
   Desain strategi deployment portal dokumentasi yang mendukung *version switcher* (misal: v1.x, v2.x, `canary`), di mana paket `@acme-ui/core` memiliki major release baru sementara `@acme-ui/icons` berjalan dengan siklus semver berbeda. Bagaimana Anda menstrukturkan routing, static asset hosting (S3/Cloudflare Pages), dan automated build trigger via GitHub Actions agar setiap release tag package menghasilkan sub-path dokumentasi terisolasi tanpa perlu me-rebuild keseluruhan portal historis?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Enterprise CI/CD Pipeline Bottleneck akibat Docgen Skala Besar
* **Konteks:** Sebuah tim Design System di platform fintech memiliki monorepo beranggotakan 450+ komponen (termasuk atoms, molecules, dan multi-state data tables). Setiap kali developer membuka PR, pipeline CI menjalankan task `build-docs` yang memakan waktu 28 menit, dengan konsumsi RAM menyentuh batas runner (7.5 GB) dan kerap mengalami Node.js OOM (`FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory`).
* **Investigasi Awal:** Pipeline mengeksekusi Storybook telemetry dan `react-docgen-typescript` dari awal (*cold start*) pada setiap commit, mem-parse ulang seluruh dependency graph TypeScript monorepo, termasuk file deklarasi library eksternal yang besar (`date-fns`, `framer-motion`).
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda merombak arsitektur build dokumentasi menggunakan teknik *incremental metadata extraction*, *content-addressable caching* (misal: Turbo / Nx computation caching), dan isolasi `tsconfig` docgen?
  2. Implementasikan konfigurasi optimal filtering `propFilter` pada `react-docgen-typescript` untuk memblokir resolusi tipe dari `node_modules` (khususnya tipe global `@types/react`) tanpa kehilangan definisi props turunan native HTML (misal: `aria-*` attributes).

### Skenario B: Race Condition dan State Desynchronization pada Live Playground Monorepo
* **Konteks:** Portal dokumentasi internal menyediakan live playground berbasis web-worker compiler (transpilasi Sucrase/Babel di sisi client) untuk mempercepat iterasi. Namun, pengguna melaporkan bahwa saat mengetik kode secara cepat (*high-frequency typing*) atau saat berpindah tema (*light-to-dark*) dalam playground yang kompleks, compiler melempar runtime exception: `Identifier 'x' has already been declared`, preview merender UI usang (*stale state*), atau web-worker berhenti merespons secara permanen.
* **Investigasi Awal:** Event `onChange` dari editor Monaco langsung di-dispatch ke Web Worker tanpa manajemen siklus eksekusi (lifecycle cancelation). State theme context diinjeksikan secara terpisah via dynamic evaluation yang bertabrakan dengan eksekusi kode JSX transpilasi yang belum rampung.
* **Pertanyaan Diagnostik:**
  1. Bagaimana arsitektur penanganan async execution pipeline yang tepat untuk playground ini? Rancang pola *cancellation token* / *abort controller* pada Web Worker client compiler.
  2. Bagaimana mendesain state synchronization layer yang menjamin atomisitas pembaruan antara kode JSX, inject dynamic tokens, dan root hydration pada iframe runner target?

### Skenario C: Dekomposisi Monolithic Documentation Portal ke Headless Architecture
* **Konteks:** Perusahaan multinasional memiliki sistem dokumentasi berbasis monolithic Storybook yang lambat dimuat oleh consumer non-teknis (Desainer, Product Manager, QA) karena ukuran JS bundle awal mencapai 45 MB. Manajemen memutuskan untuk memigrasikan dokumentasi menjadi portal berbasis *headless architecture* (portal publik menggunakan Next.js / Astro dengan Pagefind/Algolia search engine), namun para insinyur frontend menolak keras jika harus menulis ulang ribuan stories atau kehilangan kapabilitas *visual regression testing* berbasis Storybook CSF yang sudah terintegrasi di CI.
* **Investigasi Awal:** Storybook stories saat ini berfungsi sebagai single-source-of-truth untuk visual testing, manual testing, dan dokumentasi API.
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda merancang arsitektur di mana CSF stories tetap menjadi SSOT kode, namun metadata cerita (*stories meta*, *rendered previews*, dan *args*) dapat di-compile secara headless (*ahead-of-time*) dan dikonsumsi oleh static site generator pilihan tanpa memuat runtime Storybook yang berat?
  2. Jelaskan trade-off performa, kompleksitas pemeliharaan, dan latency sinkronisasi dari arsitektur headless ini dibandingkan menggunakan Storybook composition (`refs`).

---

## 4. Chapter Challenge

### Tantangan Praktis: Membangun Automated Documentation Engine & Interactive Playground Pipeline Berbasis TypeScript AST & MDX

#### Problem Statement
Tim Design System Anda membutuhkan portal dokumentasi internal ultra-cepat yang membaca langsung source code komponen TypeScript, mengekstrak JSDoc metadata secara presisi, dan menyajikannya ke dalam halaman dokumentasi interaktif yang mencakup interactive code runner dan visual token table, sepenuhnya otomatis tanpa penulisan manual file props markdown.

#### Requirements
1. **Metadata Extractor CLI (Node.js/TypeScript Engine):**
   - Bangun utility script yang memanfaatkan TypeScript Compiler API (`ts.createProgram`, `ts.TypeChecker`).
   - Ekstrak seluruh interface props dari target file komponen:
     - Nama prop, tipe data (termasuk literal union yang dievaluasi secara eksplisit).
     - Status required vs optional.
     - Nilai `defaultProps` atau default assignment pada parameter destructuring.
     - Deskripsi JSDoc, tag `@deprecated`, dan contoh penggunaan `@example`.
   - Simpan output ekstraksi dalam format terstandarisasi JSON Schema (`component-metadata.json`).

2. **Unified Markdown Transformation Pipeline:**
   - Gunakan `remark` dan `rehype` pipeline.
   - Buat custom plugin remark/rehype yang mencegat tag khusus `::component-api[Button]` di dalam file MDX, lalu me-resolve data dari `component-metadata.json` menjadi tabel HTML yang responsif dan terformat rapi.
   - Buat custom plugin untuk mengubah blok kode dengan penanda ```` ```tsx live ```` menjadi interactive runner wrapper.

3. **Secure Sandboxed Preview Component:**
   - Implementasikan komponen React `<LivePreview />` yang menerima string kode dari editor (textarea atau minimal code editor).
   - Render preview di dalam `<iframe>` yang menggunakan attribute `sandbox="allow-scripts"` (tanpa `allow-same-origin` untuk isolasi domain).
   - Kirim hasil transpilasi client-side (gunakan standalone compiler seperti Sucrase via CDN/worker) ke iframe via `postMessage`.
   - Sediakan toggle Theme (Light/Dark) yang menginjeksi token variabel CSS secara instan ke dalam iframe tanpa me-reload dokumen.

#### Constraints
- Dilarang menggunakan dependency framework dokumentasi out-of-the-box (seperti Storybook, Docusaurus, Nextra, VitePress) untuk core extraction engine. Pipeline harus murni berbasis TypeScript API dan unified ecosystem.
- Ekstraksi props harus menangani generic component dan extended HTML attributes (misal: `interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>`) tanpa mengekstrak ratusan event handlers bawaan DOM, kecuali properti tersebut secara eksplisit di-*override* atau di-dokumentasikan via JSDoc di level komponen lokal.
- Script ekstraksi harus memiliki guard timeout atau recursion limiter untuk mencegah hang pada infinite recursive types.

#### Expected Output
1. File `scripts/extract-props.ts`: Skrip parser AST TypeScript yang menghasilkan JSON metadata.
2. File `lib/unified-docgen-plugin.ts`: Custom AST plugin untuk menyisipkan API tables dan live editor component.
3. File `components/LivePlayground.tsx` & `public/runner.html`: Sistem live runner berbasis iframe berpasir (*sandboxed*) dan transpilasi client.
4. Minimal 1 contoh output validasi: Uji coba engine terhadap komponen `Button.tsx` polimorfik yang menghasilkan render dokumentasi lengkap.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara lexical analysis (tokens), syntactic analysis (AST), dan semantic analysis (TypeChecker) pada TypeScript compiler context.
- [ ] Mekanisme parsing MDX v2/v3 (pemisahan remark untuk markdown AST vs rehype untuk HTML AST, serta interop JSX node).
- [ ] Model ancaman keamanan (*attack vectors*) pada live-code runner portal dokumentasi: isolasi iframe, proteksi terhadap `window.parent` sniffing, dan mitigasi Cross-Site Scripting (XSS).
- [ ] Life-cycle metadata ekstraksi: kapan docgen harus dijalankan (pre-build vs on-demand) serta dampaknya terhadap Developer Experience (DX) lokal vs kecepatan CI/CD.
- [ ] Arsitektur propagasi Design Tokens ke format dokumentasi (Design Tokens Format Module -> Style Dictionary -> Prop Table / Swatch Tokens).
- [ ] Prinsip headless documentation: abstraksi data props, states, dan contoh cerita terpisah dari runtime layer visualisasi.

### Saya tidak perlu menghafal:
- [ ] Setiap syntax method flag pada TypeScript compiler internal API (cukup memahami abstraksi `ts.TypeChecker`, `getSymbolAtLocation`, `typeToString`, dan navigasi AST).
- [ ] Spesifikasi syntax lengkap dari regex atau parser grammar parser markdown.
- [ ] Seluruh nama native props HTML standar (misal: menghafal 150+ atribut `HTMLButtonElement`).
- [ ] Konfigurasi webpack/rollup internal dari tool dokumentasi out-of-the-box.

### Saya harus bisa melakukan:
- [ ] Menulis custom utility menggunakan TypeScript Compiler API untuk menelusuri type hierarchy, mengekstrak JSDoc tags, dan menghasilkan JSON schema props secara akurat.
- [ ] Menulis custom Remark/Rehype plugin untuk memanipulasi markdown Abstract Syntax Tree (mdast/hast).
- [ ] Mengonfigurasi `react-docgen-typescript` dengan filter props presisi yang menyaring noise `node_modules` namun mempertahankan dokumentasi custom props.
- [ ] Membangun secure bidirectional communication bridge antara portal dokumentasi dan sandboxed preview container.
- [ ] Menyiapkan automated documentation drift detection di dalam pipeline pull request menggunakan GitHub Actions dan static linters.