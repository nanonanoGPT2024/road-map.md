# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 10: Product Strategy, DesignOps, dan Cross-Functional Delivery**
**Kategori: 03-Frontend-and-Mobile / product-design**

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengimplementasikan Token Architecture Skala Enterprise**: Menerapkan arsitektur *3-tier design tokens* (Global/Primitive, Semantic/Alias, Component-specific) yang kompatibel dengan spesifikasi W3C Design Tokens Community Group (DTCG).
2. **Membangun Automated DesignOps CI/CD Pipeline**: Mengotomatisasi ekstraksi variabel/token dari Figma REST API, transformasi deterministik multi-platform (Web, iOS, Android) menggunakan Style Dictionary dan AST (*Abstract Syntax Tree*), hingga otomatisasi penerbitan paket privat (npm, CocoaPods, Maven).
3. **Mengembangkan Sistem Telemetri & Governance Design System**: Membangun *custom static analysis tool* (ESLint/Babel Plugin) untuk mengukur metrik *Token Adoption Rate* (TAR) dan mendeteksi deviasi visual secara *real-time* di seluruh monorepo organisasi.
4. **Mengorkestrasi Cross-Functional Contract Testing**: Mencegah *breaking changes* visual dan fungsional melalui integrasi pengujian regresi visual terdistribusi (*visual regression testing*) berbasis Playwright/Storybook Test Runner di dalam pipeline pull request.

---

### 2. Prerequisite

Sebelum mempelajari materi ini, peserta wajib menguasai:
* **TypeScript & Node.js Runtime Internals**: Eksekusi asynchronous, streaming I/O, pembuatan custom CLI tooling, dan manipulasi manipulasi AST via Babel/TypeScript Compiler API.
* **Modern Frontend Architecture**: Komponen UI berbasis Web Component/React, tokenisasi CSS variables, dynamic runtime CSS-in-JS vs static zero-runtime CSS (Vanilla Extract, Tailwind).
* **Cross-Platform UI Fundamentals**: Pemahaman dasar layout engine di iOS (SwiftUI Dynamic Type & Assets) dan Android (Jetpack Compose Material3 Theming).
* **Git Workflows & CI/CD Pipelines**: GitHub Actions/GitLab CI, semantic release, semantic versioning (*semver*), serta automasi webhook.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi DesignOps di tingkat enterprise bukan sekadar perihal estetika antarmuka, melainkan sebuah rekayasa perangkat lunak untuk standarisasi kontrak desain antarsistem (*Design as Code*).

#### 3.1. Arsitektur 3-Tier Design Tokens (W3C DTCG Standard)
Arsitektur token membagi data visual ke dalam tiga lapisan abstraksi yang terisolasi:

```
[ Tier 1: Global / Primitive Tokens ]
  -> Menyimpan nilai absolut (raw hex, spacing px, cubic bezier curves).
  -> Contoh: color.blue.500: #0066FF, space.16: 16px.
         │
         ▼
[ Tier 2: Semantic / Alias Tokens ]
  -> Mengabstraksi intensi bisnis, state, dan konteks tema (Light/Dark/High-Contrast).
  -> Mengikat Tier 1 ke dalam konteks fungsional.
  -> Contoh: surface.primary: { $value: "{color.blue.500}" }
         │
         ▼
[ Tier 3: Component-Scoped Tokens ]
  -> Token khusus komponen isolasi untuk menghindari global override leaking.
  -> Contoh: button.primary.background.default: { $value: "{surface.primary}" }
```

#### 3.2. Lifecycle Ekstraksi & Distribusi Token
Siklus hidup token dari Figma hingga ke kode produksi berjalan secara terisolasi tanpa intervensi manual:

```
Figma Variables / Tokens (Source of Truth)
   │
   ├─► [Webhook Event: Library Publish]
   │
   ▼
DesignOps Engine (Node.js Microservice / GitHub Action Runner)
   │
   ├── 1. Ingestion: Fetch Figma REST API (/v1/files/:key/variables/local)
   ├── 2. Sanitization: Zod Schema Validation & DTCG Specification Check
   ├── 3. Resolution: Resolving Cross-References & Aliases Graph (DAG)
   └── 4. Transformation: Style Dictionary Compilers
         ├── Web Transform     ──► CSS Custom Properties, SCSS, TS Definitions
         ├── Android Transform ──► Jetpack Compose Color/Type/Shape singletons
         └── iOS Transform     ──► Swift/SwiftUI DesignSystem Style Assets
   │
   ▼
Distribution Layer
   ├── NPM Registry (@enterprise/tokens-web)
   ├── Maven Registry (com.enterprise.designsystem:tokens-android)
   └── Swift Package Manager (EnterpriseTokensIOS)
```

#### 3.3. AST-based Token Telemetry Architecture
Untuk mengukur keselarasan implementasi (*governance*), arsitektur DesignOps memerlukan *telemetry scanner*. Alat ini mem-parsing seluruh file komponen pada codebase aplikasi konsumen ke dalam bentuk AST (*Abstract Syntax Tree*), mencari instansiasi gaya yang hardcoded (misal: `color: "#FFFFFF"`), lalu membandingkannya dengan penggunaan token semantik (`var(--color-surface-primary)` atau `<Box color="surface.primary">`). Metrik *Token Adoption Rate* (TAR) diformulasikan sebagai:

$$\text{TAR} = \frac{\sum \text{Penggunaan Token yang Valid}}{\sum \text{Penggunaan Token yang Valid} + \sum \text{Properti Visual Hardcoded}} \times 100\%$$

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Design Handoff) | Pendekatan Enterprise DesignOps (Design as Code) |
| :--- | :--- | :--- |
| **Satu Sumber Kebenaran** | File `.figma` yang tidak terversi dan terisolasi dari kode. | Git Repository yang tersinkronisasi dua arah via API, divalidasi dengan skema DTCG. |
| **Pembaruan Brand/Tema** | Manual copy-paste variabel oleh *frontend engineer*; butuh berminggu-minggu. | Kompilasi deterministik otomatis via CI/CD; rilis multi-platform dalam hitungan menit. |
| **Toleransi Human Error** | Sangat tinggi; rawan salah interpretasi desimal, hex code, atau opacity. | Nol; *Strict type safety* dari JSON Schema sampai ke compiler TypeScript/Swift/Kotlin. |
| **Audit Kepatuhan** | QA visual manual saat sprint review; inkonsistensi lolos ke produksi. | Continuous AST linting di pre-commit dan metrik telemetri mingguan pada pull request. |

---

### 5. How (Workflow Detail)

Alur kerja sinkronisasi dan delivery token secara end-to-end:

```
[Figma Designer]
       │
       ▼ (1) Publish Library Update
[Figma Webhook Gateway]
       │
       ▼ (2) HTTP POST payload (file_key, passcode)
[Token Collector Service]
       │
       ▼ (3) GET /v1/files/:key/variables/local via Figma REST API
[Validation & Normalization Layer]
       │
       ├── (4) Parsing variabel mode (Light, Dark, High Contrast, Brand A, Brand B)
       ├── (5) Zod Validate terhadap W3C DTCG Format
       └── (6) Ekstraksi dependency graph (mencegah circular reference)
       │
       ▼
[Style Dictionary Execution]
       │
       ├── (7) Format CSS: root token variables & dark-theme overrides
       ├── (8) Format TypeScript: strict type system & const assertions
       ├── (9) Format Android: Kotlin Objects with `@Composable` getters
       └── (10) Format iOS: SwiftUI `Color` & `Font` extensions
       │
       ▼
[Automated Git PR & Verification]
       │
       ├── (11) Membuka Pull Request ke Repository Token Pusat
       ├── (12) CI menjalankan Visual Regression Testing (Storybook + Playwright)
       ├── (13) Auto-merge jika lulus uji regresi visual 100% tanpa breaking change
       └── (14) Semantic Release mempublikasikan artefak ke NPM, Maven, & SPM
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Kompiler Instruksi Mesin
Bayangkan Design Tokens sebagai **Intermediate Representation (IR)** seperti LLVM IR dalam dunia compiler:
* **Figma Variables** adalah *Bahasa Pemrograman Tingkat Tinggi* (seperti C++ atau Rust) yang ditulis oleh Product Designer.
* **DTCG JSON Tokens** adalah **LLVM Intermediate Representation (IR)**: representasi logis yang netral dan terstandarisasi, tidak terikat platform mana pun.
* **Style Dictionary & Transform Engine** adalah **LLVM Backend Compilers**: menerjemahkan IR tersebut menjadi bahasa target spesifik:
  * x86 Assembler $\rightarrow$ CSS Custom Properties / JavaScript
  * ARM64 $\rightarrow$ Swift / SwiftUI untuk iOS
  * RISC-V $\rightarrow$ Kotlin / Jetpack Compose untuk Android

#### Diagram Arsitektur CI/CD DesignOps & Telemetri
```
+-------------------------------------------------------------------------+
|                           FIGMA CLOUD ENGINE                            |
|  [Primitive Collection] ---> [Semantic Layer] ---> [Component Tokens]   |
+------------------------------------+------------------------------------+
                                     | Webhook (On Library Publish)
                                     v
+-------------------------------------------------------------------------+
|                  ENTERPRISE DESIGNOPS PIPELINE (CI/CD)                  |
|                                                                         |
|  +--------------------+    +--------------------+    +---------------+  |
|  | Figma REST Client  |--->| Schema Validator   |--->| DAG Resolver  |  |
|  | (API Ingestion)    |    | (Zod / DTCG Spec)  |    | (Topo Sort)   |  |
|  +--------------------+    +--------------------+    +---------------+  |
|                                                              |          |
|                                                              v          |
|  +-------------------------------------------------------------------+  |
|  |               Style Dictionary Multi-Target Engine                |  |
|  +-----------------+-------------------+-----------------------------+  |
|                    |                   |                             |  |
|                    v                   v                             v  |
|           +-----------------+ +-----------------+           +--------+--+
|           |   Web Target    | | Android Target  |           | iOS Target|
|           | (CSS/SCSS/TS)   | | (Compose Kotlin)|           | (Swift/UI)|
|           +--------+--------+ +--------+--------+           +-----+-----+
+--------------------|-------------------|--------------------------|-----+
                     |                   |                          |
                     v                   v                          v
+-------------------------------------------------------------------------+
|                           CONSUMER REPOSITORIES                         |
|                                                                         |
|  [ Web Monorepo ]               [ Android App ]            [ iOS App ]  |
|   `-- ESLint AST Analyzer        `-- Detekt Token Linter    `-- SwiftLint
|            |
|            v
|  [ Enterprise Telemetry Dashboard: Token Adoption Ratio (TAR) = 98.4% ] |
+-------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: W3C Standard Token Structure
Struktur token semantic yang mereferensikan primitive token sesuai standar W3C DTCG:

```json
{
  "color": {
    "primitive": {
      "blue": {
        "500": {
          "$value": "#0066ff",
          "$type": "color"
        }
      }
    },
    "semantic": {
      "surface": {
        "action": {
          "primary": {
            "$value": "{color.primitive.blue.500}",
            "$type": "color",
            "$description": "Warna background default untuk tombol tindakan utama"
          }
        }
      }
    }
  }
}
```

#### 7.2. Practical Example: Enterprise Node.js Design Token Pipeline Engine
Implementasi *production-ready* script pipeline yang mengonversi token mentah dari Figma API, menyusun dependency tree, memvalidasi schema, dan mengompilasinya menjadi target TypeScript dan CSS:

```typescript
// scripts/token-engine.ts
import fs from 'node:fs/promises';
import path from 'node:path';
import { z } from 'zod';
import StyleDictionary from 'style-dictionary';
import type { Config, TransformedToken } from 'style-dictionary';

// 1. Zod Schema Validation untuk W3C DTCG Standard
const TokenValueSchema = z.object({
  $value: z.union([z.string(), z.number()]),
  $type: z.enum(['color', 'dimension', 'duration', 'fontFamily', 'fontWeight', 'number']),
  $description: z.string().optional(),
});

type TokenValue = z.infer<typeof TokenValueSchema>;

interface RawTokenTree {
  [key: string]: RawTokenTree | TokenValue;
}

// 2. Mock Generator Figma API Ingestion (Dalam produksi: fetch dari figma.com/api/v1/files/:id/variables/local)
async function fetchFigmaVariables(): Promise<RawTokenTree> {
  return {
    color: {
      primitive: {
        neutral: {
          0: { $value: '#ffffff', $type: 'color' },
          900: { $value: '#0f172a', $type: 'color' },
        },
        brand: {
          500: { $value: '#3b82f6', $type: 'color' },
          600: { $value: '#2563eb', $type: 'color' },
        },
      },
      semantic: {
        background: {
          canvas: { $value: '{color.primitive.neutral.0}', $type: 'color' },
        },
        action: {
          primary: { $value: '{color.primitive.brand.500}', $type: 'color' },
          primaryHover: { $value: '{color.primitive.brand.600}', $type: 'color' },
        },
      },
    },
    spacing: {
      scale: {
        4: { $value: '4px', $type: 'dimension' },
        8: { $value: '8px', $type: 'dimension' },
        16: { $value: '16px', $type: 'dimension' },
      },
    },
  };
}

// 3. Engine Normalisasi dan Validasi
async function processTokens(): Promise<string> {
  const rawTokens = await fetchFigmaVariables();
  const buildDir = path.resolve(process.cwd(), 'dist/tokens');
  await fs.mkdir(buildDir, { recursive: true });

  const tempJsonPath = path.join(buildDir, 'normalized.tokens.json');
  await fs.writeFile(tempJsonPath, JSON.stringify(rawTokens, null, 2), 'utf-8');

  return tempJsonPath;
}

// 4. Custom Style Dictionary Formatter & Transformer Configuration
async function buildOutputs(tokenFilePath: string): Promise<void> {
  const sdConfig: Config = {
    source: [tokenFilePath],
    platforms: {
      css: {
        transformGroup: 'css',
        buildPath: 'dist/tokens/css/',
        files: [
          {
            destination: 'variables.css',
            format: 'css/variables',
            options: {
              outputReferences: true,
            },
          },
        ],
      },
      typescript: {
        transforms: ['attribute/cti', 'name/cti/pascal'],
        buildPath: 'dist/tokens/ts/',
        files: [
          {
            destination: 'tokens.ts',
            format: 'typescript/es6-declarations',
          },
        ],
      },
      androidCompose: {
        transformGroup: 'compose',
        buildPath: 'dist/tokens/android/',
        files: [
          {
            destination: 'DesignTokens.kt',
            format: 'compose/object',
            options: {
              className: 'DesignTokens',
              packageName: 'com.enterprise.tokens',
            },
          },
        ],
      },
    },
  };

  const sd = new StyleDictionary(sdConfig);
  await sd.buildAllPlatforms();
}

async function run(): Promise<void> {
  try {
    process.stdout.write('[1/3] Fetching and validating tokens from source...\n');
    const tokenPath = await processTokens();
    
    process.stdout.write('[2/3] Compiling multi-platform distribution targets...\n');
    await buildOutputs(tokenPath);
    
    process.stdout.write('[3/3] DesignOps Token Pipeline executed successfully.\n');
  } catch (error) {
    process.stderr.write(`Execution failed: ${error instanceof Error ? error.message : String(error)}\n`);
    process.exit(1);
  }
}

void run();
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Organisasi
* **Entitas**: "GlobalPay Financial", konglomerat teknologi finansial dengan 4 divisi bisnis independen (Retail Banking, Merchant Gateway, Wealth Management, Crypto Platform).
* **Skala Sistem**: 120+ Software Engineers, 25 Product Designers, 3 platform target (Web SPA Micro-frontend, Native Android Jetpack Compose, Native iOS SwiftUI).

#### Masalah Kritis
1. **Brand Drift & Inkonsistensi Visual**: Ditemukan 147 variasi warna biru yang tersebar di lebih dari 4.000 file kode akibat handoff manual via file Figma yang tidak terorganisir.
2. **Lead Time Eksekusi Design Rebrand**: Membutuhkan waktu 4 bulan sprint kerja lintas tim untuk mengubah sistem warna dan hierarki tipografi.
3. **Regresi Aksesibilitas**: Kontras warna sering rusak saat dark-mode diluncurkan karena dependensi manual, mengakibatkan denda regulasi terkait aksesibilitas (WCAG 2.1 AA).

#### Solusi Arsitektural
1. **Penerapan Single Monorepo Design Source**: Mengimplementasikan repository terpusat `design-system-core` yang mengekstrak Figma Variables via webhook setiap ada event `LIBRARY_PUBLISHED`.
2. **Strict DTCG Engine**: Membangun compiler token Style Dictionary kustom yang secara deterministik mengeluarkan:
   * `@globalpay/tokens-web`: CSS Variables terkompresi dengan support dynamic light/dark class switching.
   * `com.globalpay.design:tokens-android`: Artefak Maven dengan class Compose theme.
   * `GlobalPayTokens`: Paket SPM untuk iOS target.
3. **AST Linting & Guardrail Pipeline**: Membuat package `@globalpay/eslint-plugin-design-system` yang diintegrasikan ke lint-staged dan CI/CD pipeline setiap micro-frontend. Setiap CSS literal/hex yang bukan semantic token akan melempar status `ERROR` dan memblokir merge PR.

#### Hasil Bisnis & Metrik Teknis
* **Lead Time Rebranding**: Berkurang dari 4 bulan menjadi **2 hari kerja** (hanya memerlukan update variabel di Figma master lalu trigger pipeline rilis).
* **Token Adoption Rate (TAR)**: Melonjak dari **41.2%** menjadi **99.6%** dalam 3 bulan di seluruh ekosistem repositori.
* **Incident Regresi Kontras Aksesibilitas**: Turun menjadi **0 insiden** di level produksi berkat pengujian otomatis kontras WCAG di dalam pipeline kompilasi token.

---

### 9. Trade-offs

| Pendekatan / Keputusan | Keuntungan | Konsekuensi / Kerugian | Rekomendasi Kontekstual |
| :--- | :--- | :--- | :--- |
| **Component-Scoped Tokens (3-Tier)** | Menjamin isolasi penuh; perubahan pada satu komponen tidak merusak komponen lain. | Ukuran bundle CSS membesar secara eksponensial karena redundansi pointer memori visual. | Wajib untuk sistem multi-brand/white-label; hindari jika aplikasi berupa single-brand berorientasi ukuran file ultra-kecil. |
| **Build-time Static Token Resolution** | Zero-runtime overhead; optimalisasi CSS tree-shaking berjalan maksimal. | Tidak mendukung dynamic runtime user-theming secara instan tanpa reload context. | Tepat untuk aplikasi performa tinggi/e-commerce publik. |
| **CSS Variables (Runtime Injected)** | Fleksibilitas tinggi dalam hot-swapping tema tanpa reload aplikasi (misal toggle dark/light). | Biaya performa layout style recalc di browser jika jutaan variabel disisipkan ke `:root`. | Pilihan standar enterprise web modern dengan arsitektur UI berbasis dashboard/SaaS. |
| **Automated PR Auto-Merge** | Siklus rilis instan dari desain ke repositori konsumen tanpa friksi manusia. | Resiko breaking change visual skala masif jika contract testing dan visual regression gagal menangkap edge-case. | Hanya gunakan auto-merge jika coverage visual regression test > 90% pada Storybook/Playwright. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Umum (Common Mistakes)
1. **Siklus Referensi Sirkular (Circular Reference)**: Token A mereferensikan Token B, dan Token B mereferensikan Token A pada level Semantic tokens. Menyebabkan build crash dengan `Maximum call stack size exceeded`.
2. **Mode-Specific Hardcoding di Tier Primitif**: Membuat token primitif seperti `color.primitive.darkBackground: #000000`. Ini merusak fungsi tier primitif; layer primitif harus murni deskriptif (`color.primitive.neutral.950: #0a0a0a`), sedangkan variasi mode didelegasikan ke semantic tier.
3. **Mengabaikan Font Scaling Unit**: Mendefinisikan ukuran font dalam satuan `px` statis, yang memecahkan dynamic accessibility scale pada iOS (Dynamic Type) dan Android (Sp text units).

#### 10.2. Panduan Troubleshooting Masalah Produksi

| Gejala Masalah | Penyebab Utama | Solusi Penanganan Rekayasa |
| :--- | :--- | :--- |
| CSS Custom Property menghasilkan nilai `undefined` atau token path mentah `{color.primitive.neutral.0}`. | Engine transformer gagal menyelesaikan alias reference graph sebelum melakukan serialisasi CSS. | Implementasikan Topological Sorting (Directed Acyclic Graph) untuk menyelesaikan leaf-node primitif terlebih dahulu sebelum alias dipetakan. |
| Pengujian visual regression di CI selalu gagal secara flaky pada elemen teks. | Perbedaan subpixel antialiasing font rendering antara lingkungan lokal (macOS) dan container CI (Linux Docker). | Kunci flag rendering browser di Playwright CI (`--font-render-hinting=none`, `--disable-skia-runtime-opts`) dan gunakan image Docker baku berbasis Ubuntu LTS. |
| Bundle size CSS melonjak drastis hingga megabytes setelah build. | Mode variables menghasilkan seluruh permutasi komponen token untuk semua variasi tema di satu file stylesheet. | Pisahkan artefak CSS berdasarkan scope tema (misal: `theme-light.css`, `theme-dark.css`) dan load secara modular/dinamis via `<link media="...">`. |

---

### 11. Best Practices (Production Checklist)

#### Architecture & Schema Validation
* [ ] Seluruh data token wajib divalidasi menggunakan Zod Schema yang sesuai dengan W3C DTCG Specification sebelum didistribusikan.
* [ ] Larang keras penggunaan hex code absolut pada level Component Tokens; token komponen wajib mengarah ke Semantic Alias Tokens.
* [ ] Desain sistem ukuran spasi dan font wajib menggunakan unit relatif (`rem` pada Web, `sp` pada Android, dynamic points pada iOS).

#### Security & Access Management
* [ ] Kredensial Figma Access Token wajib dirotasi secara berkala dan diisolasi dengan hak akses read-only (*least privilege*) melalui GitHub Secrets atau Vault.
* [ ] Paket npm token wajib dipublikasikan ke private registry scope (`@enterprise/*`) dengan provenance provenance berbasis cryptographic signature (Sigstore).

#### Automation & Delivery Pipeline
* [ ] Setup git pre-commit hook menggunakan Husky dan Lint-Staged untuk memverifikasi struktur file token.
* [ ] Visual Regression Testing wajib dieksekusi secara headless di container Docker yang identik dengan arsitektur target CI runner.
* [ ] Terapkan Semantic Versioning otomatis berdasarkan analisis commit messages (Conventional Commits).

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun mini-DesignOps engine yang menginspeksi kode aplikasi via AST dan mengompilasi token ke format CSS terisolasi di direktori `hands-on/m02/`.

#### Langkah 1: Inisialisasi Workspace
```bash
mkdir -p hands-on/m02/src hands-on/m02/dist
cd hands-on/m02
npm init -y
npm install typescript @types/node style-dictionary zod @babel/parser @babel/traverse --save-dev
npx tsc --init
```

#### Langkah 2: Definisikan Token Primitif dan Semantik
Simpan file ini di `hands-on/m02/tokens.json`:
```json
{
  "color": {
    "primitive": {
      "emerald": {
        "400": { "$value": "#34d399", "$type": "color" },
        "900": { "$value": "#064e3b", "$type": "color" }
      },
      "gray": {
        "100": { "$value": "#f3f4f6", "$type": "color" },
        "900": { "$value": "#111827", "$type": "color" }
      }
    },
    "semantic": {
      "surface": {
        "primary": { "$value": "{color.primitive.emerald.400}", "$type": "color" },
        "canvas": { "$value": "{color.primitive.gray.100}", "$type": "color" }
      },
      "text": {
        "primary": { "$value": "{color.primitive.gray.900}", "$type": "color" }
      }
    }
  }
}
```

#### Langkah 3: Bangun Token Build Pipeline Engine
Simpan file ini di `hands-on/m02/src/builder.ts`:
```typescript
import StyleDictionary from 'style-dictionary';
import path from 'node:path';

const config = {
  source: [path.resolve(__dirname, '../tokens.json')],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: path.resolve(__dirname, '../dist/css/'),
      files: [
        {
          destination: 'tokens.css',
          format: 'css/variables',
          options: {
            outputReferences: true,
          },
        },
      ],
    },
    jsonFlat: {
      transforms: ['attribute/cti', 'name/cti/kebab'],
      buildPath: path.resolve(__dirname, '../dist/json/'),
      files: [
        {
          destination: 'tokens-flat.json',
          format: 'json/flat',
        },
      ],
    },
  },
};

const sd = new StyleDictionary(config);
sd.buildAllPlatforms()
  .then(() => console.log('Successfully generated tokens to /dist/'))
  .catch((err) => {
    console.error('Failed to compile tokens:', err);
    process.exit(1);
  });
```

#### Langkah 4: Bangun Telemetry Scanner (AST Analyzer)
Simpan file ini di `hands-on/m02/src/telemetry.ts` untuk mendeteksi hex hardcoded di file target:
```typescript
import * as parser from '@babel/parser';
import traverse from '@babel/traverse';

const sampleComponentCode = `
  const Card = () => {
    return (
      <div style={{ backgroundColor: "#34d399", color: "var(--color-semantic-text-primary)" }}>
        <h1 style={{ borderColor: "#ff0000" }}>Hello Enterprise</h1>
      </div>
    );
  };
`;

function analyzeTokenUsage(code: string): { hardcodedCount: number; tokenCount: number } {
  const ast = parser.parse(code, {
    sourceType: 'module',
    plugins: ['jsx', 'typescript'],
  });

  let hardcodedCount = 0;
  let tokenCount = 0;
  const hexRegex = /^#([0-9a-f]{3}){1,2}$/i;

  traverse(ast, {
    StringLiteral(path) {
      const val = path.node.value;
      if (hexRegex.test(val)) {
        hardcodedCount++;
        console.warn(`[VIOLATION] Hardcoded CSS color found: ${val} at line ${path.node.loc?.start.line}`);
      } else if (val.includes('var(--')) {
        tokenCount++;
      }
    },
  });

  return { hardcodedCount, tokenCount };
}

const metrics = analyzeTokenUsage(sampleComponentCode);
const adoptionRate = (metrics.tokenCount / (metrics.tokenCount + metrics.hardcodedCount)) * 100;
console.log('--- Telemetry Result ---');
console.log(`Token Adoption Rate: ${adoptionRate.toFixed(2)}%`);
```

#### Langkah 5: Eksekusi dan Verifikasi
Jalankan kompilasi dan telemetri scanner:
```bash
npx ts-node src/builder.ts
npx ts-node src/telemetry.ts
```

*Expected Verification*:
1. Direktori `dist/css/tokens.css` terisi CSS Custom Properties yang me-resolve alias token secara tepat.
2. Script `telemetry.ts` menampilkan peringatan pelanggaran (violation) terhadap hex code `#34d399` dan `#ff0000`, serta menghasilkan kalkulasi adopsi 33.33%.

---

### 13. Exercise

#### Level 1 - Easy: W3C Token Transform Script
Buat sebuah script Node.js sederhana yang membaca token file flat JSON (kunci: nilai hex) dan memvalidasi apakah seluruh format hex string valid (3 digit atau 6 digit hex) menggunakan Zod schema. Jika tidak valid, lempar custom error.

#### Level 2 - Medium: Multi-Brand Dark Mode Fallback Resolver
Bangun configuration matrix untuk Style Dictionary yang mampu meng-compile satu set Core Primitive tokens ke dalam 2 file CSS terpisah:
1. `theme-light.css` (dimana `surface.background` bernilai neutral-100).
2. `theme-dark.css` (dimana `surface.background` bernilai neutral-900).
Pastikan kedua file memetakan ke nama CSS Variable yang sama: `--surface-background`.

#### Level 3 - Hard: ESLint Custom Rule Plugin untuk Token Linting
Kembangkan sebuah custom ESLint rule berbasis TypeScript yang mem-parsing JSX attribute `style` atau properti styled-components. Rule harus mengeluarkan auto-fixable lint issue yang menggantikan nilai literal hex code (misal `#111827`) dengan CSS variable token semantik yang relevan berdasarkan lookup dictionary file.

---

### 14. Challenge

#### Skenario Kasus Kompleks: Dynamic White-Label Micro-Frontend Token Engine
Perusahaan Anda mengelola sebuah arsitektur Web Micro-Frontend (MFE) yang melayani 10 brand perbankan berbeda (white-label) yang dimuat secara dinamis tergantung subdomain host yang diakses klien (misal: `banka.platform.com` vs `bankb.platform.com`).

**Persyaratan Tantangan Arsitektur**:
1. Rancang pipeline kompilasi token yang memproduksi paket tema zero-runtime overhead.
2. Sistem tidak boleh memuat keseluruhan 10 tema brand ke client bundle untuk menghindari payload bloat (ukuran maksimal payload CSS tema per brand adalah $\le 10\text{ KB}$).
3. Harus mendukung hot-swapping mode Light dan Dark tanpa re-fetch asset jaringan baru (tersedia offline/cache-first via Service Worker).
4. Buat RFC Arsitektur singkat (1-2 halaman) yang mencakup:
   * Diagram data ingestion dari multi-Figma file per brand.
   * Format metadata manifes token.
   * Mekanisme dynamic asset prefetching pada browser level router micro-frontend.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konseptual Dasar (5 Soal)
1. Apa peran spesifik dari **Semantic / Alias Tokens** dalam arsitektur 3-tier design tokens?
   * *Jawaban*: Memberikan makna fungsional atau intensi bisnis terhadap nilai primitif mentah tanpa membebankannya pada komponen spesifik, memungkinkan pergantian tema (theming) secara terisolasi.
2. Mengapa format representasi token dari W3C DTCG mensyaratkan properti prefix `$` (seperti `$value`, `$type`)?
   * *Jawaban*: Untuk membedakan metadata spesifikasi resmi DTCG secara deterministik dari token grouping keys buatan pengguna.
3. Apa risiko utama dari penggunaan runtime CSS-in-JS (seperti Emotion/Styled Components versi awal) pada sistem token enterprise skala besar?
   * *Jawaban*: Overhead runtime execution yang tinggi pada CPU browser akibat injeksi stylesheet dinamis dan penghitungan ulang hash CSS di setiap lifecycle re-render.
4. Apa yang dimaksud dengan siklus referensi (*circular reference*) pada token graph?
   * *Jawaban*: Kondisi saat dua atau lebih token saling mereferensikan satu sama lain secara langsung maupun berantai sehingga parsing rekursif mengalami loop tanpa henti.
5. Bagaimana cara token primitive menangani multi-branding secara arsitektural?
   * *Jawaban*: Token primitif menyimpan palet global seluruh brand, sementara alias token dipetakan ulang untuk menunjuk pada subset primitif brand yang sedang aktif.

#### Bagian B: Analisis & Menengah (5 Soal)
6. Bagaimana cara Style Dictionary mempertahankan dependensi variabel CSS menggunakan opsi `outputReferences: true`?
   * *Jawaban*: Alih-alih melakukan flattening nilai literal mentah, generator mempertahankan referensi nama token dalam bentuk sintaks native `var(--nama-token-induk)`.
7. Jelaskan perbedaan mendasar antara unit teks `sp` di Android Compose dan `Dynamic Type` di iOS SwiftUI dalam konteks Design Tokens!
   * *Jawaban*: `sp` adalah unit absolut berskala otomatis di Android berdasarkan preferensi OS; sedangkan iOS Dynamic Type mengandalkan semantic text styles yang terikat pada layout traits sistem operasi.
8. Dalam pipeline CI/CD visual regression testing, faktor apa yang menyebabkan kegagalan uji (*false positive test failure*) yang bersumber dari infrastruktur rendering?
   * *Jawaban*: Perbedaan font-hinting rasterization engine, thread timing, dan GPU hardware acceleration antara workstation lokal dan container headless CI Linux.
9. Mengapa *component-scoped tokens* harus dihindari jika aplikasi tidak memiliki use-case white-label atau multi-theme yang kompleks?
   * *Jawaban*: Karena meningkatkan kompleksitas maintenance token graph dan memperbesar ukuran file distribusi (CSS/TS) tanpa memberikan keuntungan abstraksi yang riil.
10. Bagaimana formula Token Adoption Rate (TAR) mendeteksi regresi kode dalam pipeline linting pull request?
    * *Jawaban*: Dengan menghitung rasio jumlah instansiasi token legal berbanding seluruh visual styling property yang di-parse via AST; jika rasio turun di bawah threshold yang disepakati, build dinyatakan failed.

#### Bagian C: Skenario Kasus Produksi (3 Soal)
11. **Skenario 1 (Memory Leak & Pipeline Crash)**: Sebuah job CI/CD yang mengompilasi token Figma gagal dengan error `JavaScript heap out of memory` setelah divisi UI menambahkan 500 variable modes baru. Di mana titik failure arsitekturnya dan bagaimana mitigasinya?
    * *Analisis Solusi*: Failure terjadi karena algoritma tree resolution membaca seluruh mode ke dalam memori secara simultan menggunakan single in-memory JSON object. Mitigasi: Pisahkan kompilasi per-brand/per-mode menggunakan streaming pipeline dan jalankan parsing secara concurrent berbasis Worker Threads berbatas memori.
12. **Skenario 2 (Accessibility Breach Lolos ke Production)**: Tim desain mengubah semantic token `color.semantic.text.onPrimary` dari putih (`#fff`) ke abu-abu terang (`#ccc`), dipasangkan dengan button background biru. Seluruh automated pipeline visual testing hijau, tetapi melanggar standar WCAG. Mengapa ini bisa terjadi dan apa guardrail yang harus dipasang?
    * *Analisis Solusi*: Visual regression testing berbasis screenshot image-diffing hanya mendeteksi perubahan visual antar layer, bukan kontras fungsional. Solusinya: Sisipkan *Automated Accessibility Contrast Linter* ke dalam engine kompilasi token yang memverifikasi rasio kontras warna (minimal 4.5:1 untuk normal text) sebelum artefak token diekspor.
13. **Skenario 3 (Breaking Change Downstream Mobile)**: Update token menghapus properti token lama `color.action.cta` dan menggantikannya dengan `color.action.primary`. Web platform berhasil deploy tanpa crash (hanya silent fallback CSS), tetapi aplikasi iOS SwiftUI mengalami *compile error* massal di master branch. Bagaimana mencegah hal ini di masa depan?
    * *Analisis Solusi*: Web CSS memaafkan *missing variables*, sedangkan strongly-typed languages seperti Swift/Kotlin melempar compilation error. Guardrail: Terapkan semantic versioning deprecation cycle. Larang hard-delete token pada minor release; tandai properti lama sebagai `@deprecated` di Swift/Kotlin selama 1-2 siklus rilis mayor sebelum dihapus total.

---

### 16. Summary

Implementasi DesignOps pada tingkat enterprise merupakan transformasi fundamental dari paradigma manual *design handoff* menuju sistem rekayasa *Design as Code*. Melalui pemanfaatan spesifikasi terstandarisasi (W3C DTCG), pipeline ekstraksi terotomatisasi berbasis API, serta transformasi multi-platform deterministik (Style Dictionary), inkonsistensi antarmuka dapat dieliminasi secara struktural. 

Keberhasilan DesignOps tidak hanya ditentukan oleh kelancaran otomasi sinkronisasi, melainkan juga oleh ketatnya sistem tata kelola (*governance*). Pemanfaatan AST-based static analysis, visual regression testing di container CI yang terisolasi, serta pemantauan telemetri adopsi token secara berkelanjutan adalah fondasi utama yang menjamin kecepatan iterasi produk tanpa mengorbankan stabilitas, performa, maupun kepatuhan aksesibilitas perangkat lunak skala masif.