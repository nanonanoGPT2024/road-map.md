# Kurikulum Enterprise Design System: Modul 02

**Kategori:** 03-Frontend-and-Mobile  
**Bab:** 02 - Design Tokens Architecture dan Engineering  
**Modul:** Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi  

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Senior/Staff Engineer diharapkan mampu:

1. **Merancang Arsitektur Token Multi-Tier:** Mengimplementasikan topologi 3-tier (*Global/Base/Core*, *Semantic/Alias/System*, dan *Component-Scoped*) yang mendukung kebutuhan multi-brand, multi-theme (Dark/Light/High Contrast), dan multi-platform.
2. **Membangun Automated Token Pipeline:** Mengembangkan pipeline kompilasi kustom berbasis **Style Dictionary v4** dan TypeScript yang mengekstrak data dari Design Tool (Tokens Studio / Figma Variables API), memvalidasi skema, mendeteksi siklus dependensi graf (*cyclic dependencies*), dan mengekspor artefak lintas platform (CSS/SCSS, TypeScript/JavaScript, Android Compose/XML, iOS Swift/SwiftUI).
3. **Mengoptimalkan Distribusi & Performa Runtime:** Mengimplementasikan strategi resolusi token runtime versus waktu bangun (*build-time baking*), teknik *tree-shaking* token, dynamic CSS custom properties injection, serta kontrol *layout shift* (CLS) akibat pergantian tema.
4. **Menerapkan Validasi Mutu Otomatis (Token QA Automation):** Menyusun automated testing suite yang memverifikasi rasio kontras warna (*WCAG 2.1 AA/AAA compliance* via algoritma APCA/sRGB), konsistensi modular scale, dan *backward compatibility* (semantic versioning token) menggunakan pipeline CI/CD.

---

## 2. Prerequisite

Peserta didik wajib menguasai kompetensi dasar berikut sebelum mempelajari modul ini:

* **Sistem Desain & Rekayasa Web Fundamental:** Pemahaman mendalam mengenai hierarki CSS variables (CSS Custom Properties), *specificity*, dan mekanisme *cascade*.
* **Modern JavaScript & TypeScript Lanjutan:** Kemampuan menulis AST manipulation, Node.js streaming API, TypeScript generics, conditional types, dan runtime validation library (seperti Zod atau Valibot).
* **Graph Data Structure & Algoritma:** Pemahaman mengenai representasi Graph (DAG - *Directed Acyclic Graph*), *Topological Sort*, dan deteksi *cycle* (Tarjan's/Kahn's Algorithm).
* **Tooling & Platform Ecosystem:** Pengalaman dengan paket monorepo (Turborepo/Nx), Git hooks, npm packaging, serta pemahaman sintaksis deklaratif Android Jetpack Compose dan iOS SwiftUI.

---

## 3. Concept & Internal Architecture

### 3.1 Token Hierarchy: The Three-Tier Model

Dalam ekosistem enterprise berskala besar (multi-brand, puluhan micro-frontend, ribuan engineer), model token satu dimensi (misal: `$blue-500: #0070F3;`) gagal mencegah fragmentasi UI. Arsitektur enterprise mengadopsi model berlapis (*layered abstraction*):

```
+-----------------------------------------------------------------------+
| TIER 1: GLOBAL / CORE / REFERENCE TOKENS                              |
| Nilai primitif raw yang terisolasi dari konteks fungsional.           |
| Contoh: color.palette.blue.500: #0066FF, space.scale.4: 1rem          |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| TIER 2: SYSTEM / SEMANTIC / ALIAS TOKENS                              |
| Menentukan makna fungsional & mode (Brand, Theme, Accessibility).     |
| Contoh: color.background.interactive.default -> {color.palette.blue.500}
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| TIER 3: COMPONENT-SCOPED TOKENS                                       |
| Terikat langsung pada anatomi komponen tertentu. Mengunci overrides.   |
| Contoh: button.primary.bg -> {color.background.interactive.default}   |
+-----------------------------------------------------------------------+
```

1. **Global Tokens (Core/Reference):**
   * Menyimpan nilai primitif literal: nilai heksadesimal warna, basis piksel/rem, durasi milidetik, fungsi kurva Bezier.
   * **Aturan Mutlak:** Komponen antarmuka pengguna *dilarang keras* mengonsumsi Global Tokens secara langsung.

2. **Semantic Tokens (System/Alias):**
   * Mengabstraksikan peran, intensitas, status interaktif, dan kondisi semantik.
   * Menggunakan format penamaan berbasis taksonomi terkontrol: `[domain]-[role]-[variant]-[state]`.
   * Bersifat dinamis terhadap *mode* (*theme* atau *brand*). Sebagai contoh, `color.surface.canvas` bernilai `{color.palette.neutral.0}` pada tema Light dan `{color.palette.neutral.950}` pada tema Dark.

3. **Component Tokens:**
   * Menyediakan abstraksi isolasi agar pembaruan visual pada satu komponen (misal: `Button`) tidak merusak tampilan komponen lain (misal: `Card`) yang kebetulan menggunakan semantic token yang sama.
   * Menggunakan format: `[component].[part].[property].[state]`.

### 3.2 Dynamic Resolution & DAG (Directed Acyclic Graph)

Kompilasi token dari sumber data (JSON/YAML) menuju artefak tujuan melibatkan resolusi referensi berbasis graf berarah:

```
[button.primary.hover.bg] ──> [color.surface.action.hover] ──> [color.palette.blue.700] ──> "#0047AB"
```

Mesin kompilasi harus memvalidasi bahwa hubungan relasional antar token membentuk **Directed Acyclic Graph (DAG)**. Apabila terdapat referensi siklik (misal: `A -> B -> C -> A`), sistem build harus menggagalkan proses (*fail-fast*) dengan melacak jejak tumpukan (*stack trace*) siklus secara akurat sebelum masuk fase output.

---

## 4. Why & What

| Dimensi Arsitektur | Tanpa Arsitektur Token Modern | Dengan Enterprise Token Pipeline |
| :--- | :--- | :--- |
| **Penyimpanan Nilai (Single Source of Truth)** | Hardcoded hex strings dan magic numbers tersebar di file SCSS, Compose XML, dan Swift asset catalogs. | File representasi JSON/W3C Community Group Specification dalam repositori tunggal terpusat. |
| **Multi-Brand Multi-Tenancy** | Duplikasi basis kode komponen (misal: `ButtonBrandA.tsx`, `ButtonBrandB.tsx`) atau percabangan CSS yang rapuh. | Satu basis kode komponen tunggal; nilai tema disuntikkan secara deklaratif melalui konfigurasi alias layer. |
| **Siklus Pembaruan Brand** | Butuh hitungan minggu; melibatkan koordinasi manual lintas tim Web, Android, dan iOS. | Hitungan menit via pipeline otomatisasi: Designer push token di Figma -> Webhook -> CI Build -> Publish packages. |
| **Jaminan Aksesibilitas (a11y)** | Pengujian kontras dilakukan manual via Chrome DevTools post-deployment; rawan kelalaian. | Verifikasi rasio kontras otomatis pada tahap kompilasi token (*Static Token Linting*). Build gagal jika kontras < 4.5:1. |
| **Platform Target** | Web centric (CSS-first). Porting ke platform mobile dilakukan manual oleh engineer mobile. | *Agnostik platform*. Mengompilasi format web, Jetpack Compose, SwiftUI, Flutter, hingga Figma variable sync secara deterministik. |

---

## 5. How (Workflow Detail)

Alur kerja rekayasa token produksi enterprise mengikuti siklus tertutup berikut:

```
   +------------------------------------+
   |  Figma / Tokens Studio (Designers) |
   +------------------------------------+
                     |
         (Git Sync / Webhook API)
                     v
   +------------------------------------+
   |    Token Ingestion & Normalization  |
   |   - W3C Format Conformity Checker  |
   +------------------------------------+
                     |
                     v
   +------------------------------------+
   |    Static Validation & Graph QA     |
   |   - Cycle Detection via Tarjan     |
   |   - APCA / WCAG Contrast Engine    |
   |   - Schema Validation (via Zod)    |
   +------------------------------------+
                     |
                     v
   +------------------------------------+
   |   Style Dictionary Custom Engine   |
   |   - Custom Transforms (px to rem)  |
   |   - Math Resolvers (clamp(), calc) |
   |   - Brand Theme Multiplexer        |
   +------------------------------------+
                     |
                     +---------------------------------------+
                     |                                       |
                     v                                       v
   +------------------------------------+ +------------------------------------+
   |       Web Artefacts Engine         | |      Mobile Artefacts Engine       |
   | - CSS Variables (split by theme)   | | - Swift Token Extensions (iOS)     |
   | - Scoped SCSS variables            | | - Jetpack Compose Objects (Android)|
   | - Type-Safe TS/JS Constants        | | - Flutter Theme Data               |
   +------------------------------------+ +------------------------------------+
                     |                                       |
                     +-------------------+-------------------+
                                         |
                                         v
   +---------------------------------------------------------------------------+
   |                        Automated Semantic Release                         |
   | - Private NPM Registry: @enterprise/tokens-web                            |
   | - Swift Package Manager (SPM): EnterpriseTokensIOS                        |
   | - Maven Central / GitHub Packages: com.enterprise.tokens:android         |
   +---------------------------------------------------------------------------+
```

---

## 6. Analogy & Diagram ASCII

Analogi rekayasa: **Design Token Engine berfungsi persis seperti Kompiler Bahasa Pemrograman (misal: LLVM).**

```
 [ Source Code (Design Intents) ]  ===> Tokens Studio / W3C Design Tokens JSON
                |
                v
 [ Frontend Parser & Lexer ]      ===> Ingestion Layer (Zod Schema Validation)
                |
                v
 [ Intermediate Representation ]  ===> Dependency DAG & Resolved Abstract Tree
                |
                v
 [ Optimization & Transformations] ===> Unit Resolvers (clamp, rem), Contrast Fixers
                |
                +------------------------------+------------------------------+
                |                              |                              |
                v                              v                              v
 [ Backend Target: LLVM x86 ]   [ Backend Target: ARM ]        [ Backend Target: WebAssembly ]
        (CSS Variables)               (Swift Objects)             (Jetpack Compose Kotlin)
```

Jika seorang programmer mengubah kode C/Rust sekali dan mengompilasinya ke binary spesifik tiap CPU, maka tim Design System merekayasa struktur token sekali dan mengompilasinya menjadi konstanta native untuk tiap runtime target.

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Skema Token W3C Format

Contoh struktur sumber token JSON sesuai draf spesifikasi W3C Design Tokens:

```json
{
  "color": {
    "palette": {
      "blue": {
        "500": {
          "$value": "#0066ff",
          "$type": "color",
          "$description": "Core primary blue primitive"
        }
      }
    }
  },
  "semantic": {
    "color": {
      "action": {
        "primary": {
          "default": {
            "$value": "{color.palette.blue.500}",
            "$type": "color",
            "$description": "Interactive primary background"
          }
        }
      }
    }
  }
}
```

### 7.2 Practical Example: Custom Token Engine (Style Dictionary v4 + TypeScript)

Berikut implementasi production-ready mesin kompilasi kustom Style Dictionary yang mengintegrasikan validasi graf, deteksi siklus, kalkulasi unit `clamp()`, serta export multi-target.

#### File: `engine/transforms/fluid-typography.ts`
```typescript
import { Transform } from 'style-dictionary/types';

interface FluidTypographyValue {
  minSizePx: number;
  maxSizePx: number;
  minViewportPx: number;
  maxViewportPx: number;
}

export const fluidTypographyTransform: Transform = {
  name: 'typography/fluid-clamp',
  type: 'value',
  transitive: true,
  matcher: (token) => token.$type === 'fluid-typography',
  transformer: (token) => {
    const { minSizePx, maxSizePx, minViewportPx, maxViewportPx } = token.$value as FluidTypographyValue;

    const minSizeRem = minSizePx / 16;
    const maxSizeRem = maxSizePx / 16;
    const minViewportRem = minViewportPx / 16;
    const maxViewportRem = maxViewportPx / 16;

    const slope = (maxSizeRem - minSizeRem) / (maxViewportRem - minViewportRem);
    const yAxisIntersection = -minViewportRem * slope + minSizeRem;

    const slopeVw = Number((slope * 100).toFixed(4));
    const interceptRem = Number(yAxisIntersection.toFixed(4));

    return `clamp(${minSizeRem}rem, ${interceptRem}rem + ${slopeVw}vw, ${maxSizeRem}rem)`;
  },
};
```

#### File: `engine/validators/graph-validator.ts`
```typescript
interface TokenNode {
  name: string;
  references: string[];
}

export class TokenCycleDetector {
  private adjacencyList: Map<string, string[]> = new Map();

  public registerToken(name: string, rawValue: unknown): void {
    const references: string[] = [];
    if (typeof rawValue === 'string') {
      const matches = rawValue.matchAll(/\{([^}]+)\}/g);
      for (const match of matches) {
        references.push(match[1]);
      }
    }
    this.adjacencyList.set(name, references);
  }

  public detectCycles(): void {
    const visited: Set<string> = new Set();
    const recursionStack: Set<string> = new Set();

    for (const node of this.adjacencyList.keys()) {
      if (this.dfs(node, visited, recursionStack)) {
        throw new Error(`Fatal Token Architecture Error: Cyclic dependency detected around node "${node}"`);
      }
    }
  }

  private dfs(node: string, visited: Set<string>, recursionStack: Set<string>): boolean {
    if (recursionStack.has(node)) {
      return true;
    }
    if (visited.has(node)) {
      return false;
    }

    visited.add(node);
    recursionStack.add(node);

    const neighbors = this.adjacencyList.get(node) || [];
    for (const neighbor of neighbors) {
      if (this.dfs(neighbor, visited, recursionStack)) {
        return true;
      }
    }

    recursionStack.delete(node);
    return false;
  }
}
```

#### File: `engine/formatters/android-compose.ts`
```typescript
import { Format, TransformedToken } from 'style-dictionary/types';

export const composeColorFormat: Format = {
  name: 'compose/object',
  format: async ({ dictionary, file }) => {
    const colorTokens = dictionary.allTokens.filter(t => t.$type === 'color');

    const lines = colorTokens.map((token: TransformedToken) => {
      // Hex representation for Jetpack Compose: Color(0xFFRRGGBB)
      const hex = token.value.replace('#', '');
      const alphaHex = hex.length === 8 ? hex : `FF${hex}`;
      const camelCaseName = token.name.replace(/[-_.]([a-z])/g, (g) => g[1].toUpperCase());
      return `    val ${camelCaseName}: Color = Color(0x${alphaHex.toUpperCase()})`;
    });

    return [
      `package com.enterprise.designsystem.tokens\n`,
      `import androidx.compose.ui.graphics.Color\n`,
      `// Auto-generated by Token Engine. DO NOT EDIT MANUALLY.`,
      `object EnterpriseColors {`,
      ...lines,
      `}\n`
    ].join('\n');
  }
};
```

#### File: `engine/build.ts`
```typescript
import StyleDictionary from 'style-dictionary';
import { fluidTypographyTransform } from './transforms/fluid-typography.js';
import { composeColorFormat } from './formatters/android-compose.js';
import { TokenCycleDetector } from './validators/graph-validator.js';
import * as fs from 'fs';
import * as path from 'path';

// Validasi siklus dependensi sebelum kompilasi
function preflightCheck(tokensPath: string) {
  const detector = new TokenCycleDetector();
  const rawData = JSON.parse(fs.readFileSync(tokensPath, 'utf8'));

  function traverse(obj: any, prefix = '') {
    for (const key of Object.keys(obj)) {
      const currentPath = prefix ? `${prefix}.${key}` : key;
      if (obj[key] && typeof obj[key] === 'object' && '$value' in obj[key]) {
        detector.registerToken(currentPath, obj[key].$value);
      } else if (typeof obj[key] === 'object' && obj[key] !== null) {
        traverse(obj[key], currentPath);
      }
    }
  }

  traverse(rawData);
  detector.detectCycles();
  console.log('✓ Token Dependency Graph: Clear of cycles.');
}

async function runBuild() {
  const tokenSource = path.resolve('tokens/**/*.json');
  preflightCheck(path.resolve('tokens/global.json'));

  const sd = new StyleDictionary({
    source: [tokenSource],
    transforms: ['attribute/cti', 'name/kebab'],
    platforms: {
      css: {
        transformGroup: 'css',
        transforms: ['typography/fluid-clamp', 'name/kebab'],
        buildPath: 'dist/web/',
        files: [
          {
            destination: 'tokens.css',
            format: 'css/variables',
            options: {
              outputReferences: true // Pertahankan rantai CSS custom properties
            }
          }
        ]
      },
      android: {
        transformGroup: 'android',
        buildPath: 'dist/android/',
        files: [
          {
            destination: 'EnterpriseColors.kt',
            format: 'compose/object'
          }
        ]
      },
      typescript: {
        transformGroup: 'js',
        buildPath: 'dist/types/',
        files: [
          {
            destination: 'index.d.ts',
            format: 'typescript/es6-declarations'
          }
        ]
      }
    }
  });

  sd.registerTransform(fluidTypographyTransform);
  sd.registerFormat(composeColorFormat);

  await sd.buildAllPlatforms();
  console.log('✓ All platforms compiled successfully.');
}

runBuild().catch((err) => {
  console.error('Build execution failed:', err);
  process.exit(1);
});
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Transisi Multi-Tenant FinTech (MegaCorp Global Banking)

* **Skala Sistem:** 4 Core Brands (Retail, Corporate, Islamic, Wealth Management), 3 Platform (Web Microfrontends, iOS Native, Android Native), 450 UI Engineers, 1200+ Komponen Unik.
* **Masalah:**
  1. *Color Collision & Duplikasi:* Ditemukan 2.400 variabel warna statis di SCSS. Nilai `#0052CC`, `#0050CA`, dan `#0052CD` digunakan untuk tombol yang sama di 3 micro-frontend berbeda.
  2. *Dark Mode Breakage:* Pengalihan tema gelap secara runtime via CSS class switcher mengakibatkan teks *unreadable* (rasio kontras 1.2:1) pada produk Corporate Banking karena semantic alias menunjuk langsung ke hex warna gelap tanpa inversi token layer.
  3. *Latency Distribusi:* Waktu rilis desain dari Figma ke production mobile memakan waktu rata-rata 3 sprint (6 minggu).
* **Arsitektur Solusi:**
  1. **Canonical Extraction:** Dilakukan clustering warna via algoritma Delta-E (CIELAB) untuk memadatkan 2.400 warna liar menjadi 64 Core Global Palette tokens.
  2. **Multi-Tenant Token Matrix:** Semantic tokens dipetakan menggunakan matriks skema:
     ```
     tokens/
     ├── globals/               # Core Primitive Base (Agnostik Brand)
     │   └── colors.json
     ├── brands/                # Tenant Layers (Override Referensi Semantic)
     │   ├── retail/
     │   ├── corporate/
     │   └── wealth/
     └── themes/                # Mode Modifiers
         ├── light.json
         └── dark.json
     ```
  3. **Pipeline Continuous Delivery Token:**
     * Integrasi GitHub Actions yang mengonsumsi Webhook dari Figma Variables API.
     * Evaluasi rasio kontras otomatis menggunakan modul headless APCA (*Advanced Perceptual Contrast Algorithm*). Jika skor Lc kurang dari 60 untuk body text, pull request ditolak otomatis pada tahap CI.
* **Hasil:**
  * Reduksi ukuran bundle CSS micro-frontend sebesar **42%** melalui eliminasi style redundan dan pemanfaatan `outputReferences: true`.
  * Waktu rilis *design-to-production* dipangkas dari **6 minggu menjadi 15 menit**.
  * Zero-incident terkait isu kepatuhan WCAG 2.1 AA di seluruh lini produk perbankan selama 4 kuartal berturut-turut.

---

## 9. Trade-offs

Setiap keputusan rekayasa token memiliki konsekuensi arsitektural yang signifikan:

```
Resolusi Runtime CSS Variables                      Resolusi Build-Time Static CSS
 (outputReferences: true)                               (outputReferences: false)
+----------------------------------------+         +----------------------------------------+
| PRO: Bundle size kecil                 |         | PRO: Zero runtime cascade overhead     |
| PRO: Pergantian tema instan (O(1))     |  VS     | PRO: Mendukung engine legacy & email   |
| CON: DevTools debugging dalam          |         | CON: Ukuran file membengkak jika tema  |
| CON: Browser recalculate style mahal   |         |      dikompilasi menjadi selector statis|
+----------------------------------------+         +----------------------------------------+
```

| Pendekatan / Keputusan | Trade-off Positif | Trade-off Negatif & Konsekuensi |
| :--- | :--- | :--- |
| **Output References: True (CSS Variables Asli)** | *Dynamic Theming:* Cukup ganti root class (misal: `.theme-dark`), browser merender ulang tanpa download stylesheet baru. | CSS Variables tidak bisa digunakan langsung pada konteks tanpa dukungan cascade (seperti SVG fill statis pada email template, Canvas 2D context). |
| **Granular Component Tokens (Tier 3 Lengkap)** | *Decoupling Maksimal:* Mengubah warna `table.header.bg` dijamin aman tanpa risiko mengubah tampilan `button.secondary.bg`. | *Maintenance Overhead:* Jumlah token meningkat eksponensial (dari ratusan menjadi puluhan ribu token), membebani memori compiler & menyulitkan pencarian token. |
| **Pre-computed Fluid Clamp vs Static Breakpoints** | Desain fluida halus tanpa layout jumping antar breakpoint layar standar. Mengurangi kebutuhan puluhan media queries. | Sulit dipetakan ke platform native mobile (Android/iOS) yang tidak memiliki konsep native `clamp(min, preferred, max)` berbasis viewport width. |
| **Monorepo Token Package vs Standalone Repositories** | Monorepo memfasilitasi *atomic commits*: perubahan token langsung divalidasi silang terhadap visual regression test komponen UI. | Monorepo memerlukan konfigurasi permission ketat agar designer atau bot CI Figma tidak merusak kode inti sistem monorepo. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Hardcoded Cross-Platform Unit Bias (Pixel vs Rem)
* *Kesalahan:* Menyimpan token jarak dan tipografi menggunakan satuan statis `px` (`"fontSize": "16px"`).
* *Dampak:* Merusak aksesibilitas pada Web ketika pengguna mengatur *browser default root scale* (misal: 125% untuk tuna netra). Di platform Android, `px` tidak mengindahkan kepadatan piksel layar (seharusnya `sp` untuk teks dan `dp` untuk layout).
* *Solusi Remediasi:* Simpan nilai data primitif dalam format numerik mentah (`16` atau `1`). Gunakan Transform layer pada Style Dictionary untuk mengalikan basis dan menambahkan unit target sesuai platform:
  * Web: Ubah nilai basis `16` menjadi `1rem`.
  * Android Compose: Ubah menjadi `16.sp` atau `16.dp`.
  * iOS: Ubah menjadi format CGFloat `16.0`.

### Mistake 2: Specificity Leak & Duplikasi Scope Root CSS
* *Kesalahan:* Mengekspor seluruh semantic token ke pseudo-class `:root` untuk semua mode secara bersamaan:
  ```css
  /* ANTI-PATTERN */
  :root { --color-bg: #ffffff; }
  :root { --color-bg: #000000; } /* Tema gelap menimpa tema terang seketika */
  ```
* *Solusi Remediasi:* Bangun file modular yang memisahkan scope selectors:
  ```css
  :root, [data-theme='light'] {
    --color-bg: var(--color-palette-white);
  }
  [data-theme='dark'] {
    --color-bg: var(--color-palette-gray-900);
  }
  ```

### Mistake 3: Reference Broken Chains (*Dangling Pointers*)
* *Symptom:* Build engine crash atau menghasilkan output CSS kosong: `--btn-bg: ;`.
* *Diagnosa:* Terjadi ketika sebuah semantic token merujuk ke global token yang namanya diubah (*renamed*) atau dihapus di Figma, tetapi semantic mapping belum diperbarui.
* *Solusi:* Implementasikan JSON-Schema validator pada level pre-commit hook untuk memvalidasi keberadaan target path:
  ```typescript
  function validateReferences(tokens: Record<string, any>) {
    // Scan matching regex, verify target key exists in flat Dictionary map.
  }
  ```

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa teknis ini sebelum merilis paket token ke production:

* [ ] **Semantic Naming Standardized:** Skema penamaan konsisten dengan taksonomi: `[kategori]-[konteks]-[variasi]-[kondisi]` (misal: `color-interactive-primary-active`).
* [ ] **No Hardcoded Hex/Pixel in UI Layers:** Melakukan linting statis pada repositori aplikasi untuk memastikan tidak ada pemanggilan nilai warna `#hex` atau `rgb()` manual di file komponen.
* [ ] **WCAG 2.1 Contrast Testing:** Script CI otomatis memvalidasi bahwa kombinasi foreground semantic token dan background semantic token yang bersesuaian memenuhi rasio minimal `4.5:1` (teks normal) atau `3:1` (teks besar/grafis).
* [ ] **Topological Integrity:** Mesin build dilengkapi deteksi siklus (DAG validation) dan deteksi referensi gantung (*dangling reference check*).
* [ ] **Strict Typing Manifest:** Menghasilkan file output `.d.ts` dengan utility types `as const` agar pengembang mendapatkan validasi type checking dan fitur autocomplete (IntelliSense) di IDE.
* [ ] **Immutability Protection:** File hasil generasi otomatis (*distributable assets*) dikunci menggunakan proteksi hash file dan dibubuhi header komentar `@generated - DO NOT MODIFY DIRECTLY`.
* [ ] **Fallback Ingestion Safety:** Kompilasi CSS variables menyertakan fallback default jika referensi gagal dimuat di browser lama: `var(--action-color, #0066ff)`.

---

## 12. Hands-on Practice

Berikut adalah instruksi langkah demi langkah untuk membangun dan menguji pipeline token di workspace lokal Anda. Seluruh berkas harus ditempatkan di direktori: `hands-on/m02/`.

### Langkah 1: Inisialisasi Environment
Buat struktur direktori berikut di workspace Anda:

```bash
mkdir -p hands-on/m02/tokens/globals hands-on/m02/tokens/semantics hands-on/m02/scripts
cd hands-on/m02
npm init -y
npm install --save-dev typescript @types/node style-dictionary@^4.0.0 tsx zod
```

Perbarui file `hands-on/m02/package.json` untuk mengaktifkan modul ESM:
```json
{
  "name": "enterprise-token-pipeline",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "build:tokens": "tsx scripts/build-pipeline.ts"
  }
}
```

### Langkah 2: Buat Skema Sumber Data Token

#### File: `hands-on/m02/tokens/globals/colors.json`
```json
{
  "color": {
    "palette": {
      "neutral": {
        "0": { "$value": "#ffffff", "$type": "color" },
        "900": { "$value": "#121212", "$type": "color" }
      },
      "brand": {
        "primary": {
          "500": { "$value": "#0052cc", "$type": "color" },
          "700": { "$value": "#0747a6", "$type": "color" }
        }
      }
    }
  }
}
```

#### File: `hands-on/m02/tokens/semantics/theme-light.json`
```json
{
  "semantic": {
    "color": {
      "background": {
        "canvas": { "$value": "{color.palette.neutral.0}", "$type": "color" }
      },
      "action": {
        "primary": {
          "default": { "$value": "{color.palette.brand.primary.500}", "$type": "color" },
          "hover": { "$value": "{color.palette.brand.primary.700}", "$type": "color" }
        }
      }
    }
  }
}
```

### Langkah 3: Rancang Script Pipeline Kompilasi Terpadu

#### File: `hands-on/m02/scripts/build-pipeline.ts`
```typescript
import StyleDictionary from 'style-dictionary';
import * as path from 'path';

async function execute() {
  console.log('🚀 Memulai kompilasi Design Tokens...');

  const sd = new StyleDictionary({
    source: ['tokens/**/*.json'],
    platforms: {
      css: {
        transformGroup: 'css',
        buildPath: 'dist/css/',
        files: [
          {
            destination: 'variables.css',
            format: 'css/variables',
            options: {
              outputReferences: true
            }
          }
        ]
      },
      typescript: {
        transformGroup: 'js',
        buildPath: 'dist/ts/',
        files: [
          {
            destination: 'tokens.ts',
            format: 'javascript/es6'
          },
          {
            destination: 'tokens.d.ts',
            format: 'typescript/es6-declarations'
          }
        ]
      }
    }
  });

  await sd.buildAllPlatforms();
  console.log('✨ Kompilasi selesai. Artefak berhasil dibuat di direktori dist/');
}

execute().catch((err) => {
  console.error('Kompilasi gagal:', err);
  process.exit(1);
});
```

### Langkah 4: Jalankan Kompilasi dan Verifikasi Hasil
Jalankan perintah berikut:
```bash
npm run build:tokens
```

Buka dan periksa file hasil generasi:
1. `dist/css/variables.css`: Pastikan referensi antar variabel tersambung via sintaks `var(--...)`.
2. `dist/ts/tokens.ts` dan `tokens.d.ts`: Pastikan tipe ekspor TypeScript terdefinisi sempurna.

---

## 13. Exercise

### Level Easy: Custom Size Unit Converter Transform
Implementasikan sebuah Custom Transform Style Dictionary bernama `size/px-to-rem` di script kompilasi Anda.
* **Instruksi:** Transform ini harus membaca token dengan type `"dimension"` yang bernilai numerik murni (misal: `24`) dan mengonversinya menjadi string unit rem dengan rasio pembagi basis `16` (contoh: hasil kompilasi menjadi `1.5rem`).
* **Verifikasi:** Tambahkan token spacing sederhana, kompilasi ke CSS, dan verifikasi bahwa unit yang dihasilkan berakhiran `rem`.

### Level Medium: Static Automated Contrast Validator
Rancang skrip pra-validasi independen (*node script*) menggunakan pustaka matematika warna untuk menghitung Luminance Relatif (rumus WCAG 2.0).
* **Instruksi:** 
  1. Skrip membaca semantic color pairing (misal: Text Color vs Surface Canvas Color).
  2. Hitung rasio kontras `(L1 + 0.05) / (L2 + 0.05)`.
  3. Lemparkan runtime error dan hentikan proses jika ada kombinasi yang menghasilkan rasio `< 4.5:1`.

### Level Hard: Multi-Tenant Theme Multiplexing Engine
Bangun arsitektur distribusi yang mendukung pembuatan 2 Brand berbeda (*Brand Alpha* dan *Brand Beta*) di mana setiap brand memiliki mode *Light* dan *Dark*.
* **Instruksi:**
  1. Buat folder terpisah: `tokens/brands/alpha` dan `tokens/brands/beta`.
  2. Implementasikan pipeline looping di node engine yang menghasilkan:
     * `dist/alpha/light.css` & `dist/alpha/dark.css`
     * `dist/beta/light.css` & `dist/beta/dark.css`
  3. Gunakan CSS Custom Property references yang tepat di mana nama variabel identik di kedua brand, tetapi nilai referensi mengarah pada palet warna unik masing-masing tenant.

---

## 14. Challenge

### Studi Kasus Kompleks: Dynamic White-Label Token Engine dengan Zero-Runtime CSS Injection & Hot Rebundling

Sebuah perusahaan logistik multinasional memiliki platform SaaS portal armada (*fleet management*) yang dijual kembali secara *white-label* ke 50+ klien mitra perusahaan.

**Persyaratan Sistem:**
1. **Dynamic Dynamic Theming:** Tenant dapat menyuplai nilai JSON skema warna brand mereka secara dinamis melalui REST API saat runtime tanpa perlu men-deploy ulang server container Next.js/React.
2. **Zero Runtime CSS-in-JS Engine:** Dilarang menggunakan runtime engine berat yang menyuntikkan style via JavaScript di browser (seperti Styled-Components atau Emotion lama) demi menjaga target nilai Core Web Vitals (INP < 200ms, CLS = 0).
3. **Optimistic Variable Hydration:** Cegah fenomena FOIT/FOUC (*Flash of Unstyled Content*) atau kedipan tema saat halaman dimuat pertama kali pada SSR (Server-Side Rendering).
4. **Fallback Mechanism:** Jika tenant hanya mendefinisikan 1 warna primer (misal: `#E11D48`), sistem engine harus mampu menginterpolasi skala shade warna secara otomatis (50, 100, 200, ..., 900) menggunakan algoritma ruang warna OKLCH (agar persepsi cahaya seragam/perceptually uniform) dan membangkitkan CSS variables yang valid secara instan.

**Tugas Anda:**
Tuliskan cetak biru arsitektur menyeluruh (*High-Level System Design Document*) beserta implementasi kode modul Node.js yang bertugas menerima *payload* satu warna hex dari tenant, menghitung palet turunan OKLCH, memetakan ke template CSS semantic, dan menyuntikkannya ke response header/inline critical path HTML SSR engine. Sertakan mitigasi risiko caching HTTP pada CDN (Cloudflare/Fastly).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. **Mengapa Global/Primitive Tokens dilarang keras untuk dikonsumsi langsung oleh komponen antarmuka (*UI Components*)?**
   * A. Karena Style Dictionary tidak mampu memproses global tokens ke platform mobile.
   * B. Karena menghilangkan lapisan abstraksi yang diperlukan untuk pergantian tema dinamis (*theming*) dan multi-tenancy.
   * C. Karena CSS variables tidak mendukung format heksadesimal.
   * D. Karena akan menyebabkan cyclic dependency error pada graph compiler.

2. **Format token manakah yang saat ini menjadi standar formal draf konsorsium global W3C Design Tokens Community Group?**
   * A. Penulisan berbasis file YAML murni tanpa ekstensi tipe data.
   * B. Berkas JSON di mana tiap token didefinisikan menggunakan atribut `$value` dan `$type`.
   * C. Format flat key-value tanpa nesting objek.
   * D. Format XML skema deklaratif native Android.

3. **Satuan CSS apa yang paling direkomendasikan untuk token tipografi demi menjaga aksesibilitas bagi pengguna dengan keterbatasan penglihatan?**
   * A. `px`
   * B. `rem`
   * C. `vw` murni tanpa batasan
   * D. `pt`

4. **Apa fungsi utama dari opsi `outputReferences: true` pada kompilasi Style Dictionary ke CSS?**
   * A. Mempercepat proses kompilasi build time hingga 80%.
   * B. Mengonversi seluruh unit rem kembali menjadi pixel.
   * C. Mempertahankan rantai variabel native CSS (`var(--...)`) alih-alih me-resolve nilai hex secara hardcoded.
   * D. Menghasilkan unit testing otomatis untuk kontras warna.

5. **Kapan sebuah representasi token JSON dikatakan memiliki struktur "Cyclic Dependency"?**
   * A. Ketika sebuah token merujuk ke token primitif yang belum didefinisikan.
   * B. Ketika dua token atau lebih membentuk rantai referensi tertutup yang melingkar saling bergantung tanpa ujung akhir.
   * C. Ketika satu token diimpor oleh platform Web dan Mobile secara bersamaan.
   * D. Ketika token global memiliki tipe data berupa array.

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis Teknis)

6. **Diberikan rantai token berikut:**  
   `btn.primary.bg` -> `action.bg.brand` -> `color.blue.500` -> `#0052cc`.  
   Jika algoritma pendeteksi graf dijalankan, tipe traversal apakah yang paling optimal untuk menyelesaikan urutan resolusi nilai token tersebut dari daun (*leaf*) ke akar (*root*)?
   * A. Breadth-First Search (BFS) tanpa penanda traversal.
   * B. Topological Sort berbasis Post-Order Depth-First Search (DFS).
   * C. Binary Search tree balancing.
   * D. Dijkstra's Shortest Path Algorithm.

7. **Mengapa konversi ruang warna sRGB konvensional mulai ditinggalkan untuk pembuatan skala warna desain sistem modern dan digantikan oleh ruang warna OKLCH?**
   * A. Karena sRGB membutuhkan memori komputasi 4 kali lipat lebih besar saat di-parse oleh browser.
   * B. Karena sRGB tidak memiliki *perceptual uniformity*, di mana dua warna berbeda dengan tingkat lightness numerik yang sama di sRGB dapat terlihat sangat berbeda terangnya di mata manusia.
   * C. Karena OKLCH tidak didukung oleh CSS standard level 4.
   * D. Karena sRGB tidak mendukung nilai transparansi alpha channel.

8. **Saat mengompilasi token untuk platform Android Jetpack Compose, representasi data native apa yang idealnya dihasilkan oleh Token Formatter?**
   * A. XML resource file di direktori `res/values/colors.xml`.
   * B. Singleton Kotlin `object` atau `class` yang memetakan nilai menggunakan tipe data `androidx.compose.ui.graphics.Color`.
   * C. String JSON flat yang dibaca saat runtime via Kotlinx Serialization.
   * D. Objek HashMap dynamic type `Map<String, Any>`.

9. **Jika tim Anda menggunakan CSS variables untuk menerapkan *theming*, pendekatan manakah yang paling efektif untuk mencegah terjadinya Cumulative Layout Shift (CLS) saat pengguna beralih dari mode Light ke Dark?**
   * A. Memuat ulang (*reload*) halaman via `window.location.reload()`.
   * B. Memastikan token Dark dan Light hanya memanipulasi properti non-layout seperti warna (`color`, `background-color`, `border-color`) dan mengisolasi token dimensi (`padding`, `margin`, `border-width`) agar bernilai identik di kedua tema.
   * C. Menggunakan CSS animations dengan durasi 2 detik di seluruh elemen DOM.
   * D. Mengganti file stylesheet utama secara dinamis via JavaScript DOM manipulation.

10. **Apa kegunaan dari properti `transitive: true` pada konfigurasi Custom Transform di Style Dictionary?**
    * A. Memastikan transform dijalankan berulang kali pada setiap siklus interval waktu build.
    * B. Menginstruksikan Style Dictionary untuk mengeksekusi transform terhadap nilai token *setelah* referensi alias berhasil di-resolve ke nilai aslinya, bukan sebelum resolusi.
    * C. Mengonversi tipe data token dari string menjadi binary buffer.
    * D. Memaksa engine mengekspor token ke format SCSS dan Less secara serentak.

---

### Bagian 3: Production Scenario Analysis (Studi Kasus Kontekstual)

#### Skenario 1: The Cascading White-out Incident
Aplikasi retail perbankan Anda baru saja meluncurkan fitur Dark Mode. Segera setelah rilis, 40% nasabah melaporkan bahwa saldo rekening mereka "hilang" (layar tampak putih kosong) saat membuka aplikasi di kondisi pencahayaan redup. Tim investigasi menemukan bahwa teks saldo dirender menggunakan warna putih, tetapi background container juga berwarna putih.

* **Pertanyaan Kasus:** Berdasarkan arsitektur token 3-tier, di layer manakah kemungkinan besar letak *root-cause* kesalahan ini, dan bagaimana mekanisme validasi automated CI dibangun agar kegagalan ini tertolak otomatis sebelum proses merger kode?

#### Skenario 2: The Multi-Package Version Drift
Sebuah organisasi memiliki 3 tim independen: Tim Toko Online (Web), Tim Mobile Android, dan Tim Mobile iOS. Tim Desain memperbarui token warna promosi `color.sale.primary` dari warna Merah (#FF0000) menjadi Ungu (#7E22CE). Satu minggu setelah peluncuran promosi, warna di Web sudah berubah menjadi ungu, namun aplikasi Android tetap menampilkan warna merah, sementara aplikasi iOS mengalami *crash runtime*.

* **Pertanyaan Kasus:** Jelaskan kelemahan dalam rantai pasok (*supply-chain*) distribusi token di atas, dan rancang pipeline release management yang menjamin konsistensi versi atomik lintas platform!

#### Skenario 3: High-Frequency Variable Recalculation Bottleneck
Sebuah aplikasi web dashboard analitik keuangan menampilkan tabel virtualisasi data dengan 10.000 baris sel interaktif. Tim engineering mengikat token CSS variable interaktif langsung pada setiap selector baris:
```css
.data-row {
  background-color: var(--theme-row-bg-hover);
  transition: all var(--motion-duration-fast);
}
```
Ketika pengguna melakukan *hovering* cepat di atas tabel, performa animasi anjlok drastis ke 15 FPS dengan peringatan *Long Task* di DevTools Performance Profiler.

* **Pertanyaan Kasus:** Mengapa evaluasi CSS custom property yang berlebihan pada ribuan node DOM secara simultan dapat merusak framerate rendering browser, dan bagaimana restrukturisasi styling/token diterapkan untuk memulihkan performa ke 60 FPS stabil?

---

### Kunci Jawaban & Rubrik Evaluasi Quiz

#### Kunci Jawaban Bagian 1: Basic
1. **B** — Lapisan pemisah (Semantic layer) sangat mutlak agar satu perubahan variabel semantik fungsional dapat beradaptasi terhadap perubahan tema tanpa merusak token palet dasar.
2. **B** — Spesifikasi W3C Design Tokens Community Group menetapkan penggunaan objek JSON dengan key `$value` dan `$type`.
3. **B** — Satuan `rem` menghormati konfigurasi root font size sistem/browser yang diatur oleh pengguna demi alasan aksesibilitas.
4. **C** — `outputReferences: true` mencegah nilai diganti langsung dengan hardcoded string, melainkan memetakan relasi via sintaks native `var(--...)`.
5. **B** — Siklus referensi melingkar tanpa titik terminasi (A -> B -> A) mengunci traversal ke dalam loop tak terhingga (*infinite loop*).

#### Kunci Jawaban Bagian 2: Intermediate
6. **B** — Topological Sort berbasis DFS Post-Order adalah metode standar untuk me-resolve urutan evaluasi simpul pada Directed Acyclic Graph (DAG).
7. **B** — Ruang warna OKLCH memisahkan Lightness secara perseptual seragam (perceptually uniform), sehingga nilai Lightness 70% pada warna hijau memiliki terang visual yang setara dengan Lightness 70% pada warna biru.
8. **B** — Di Jetpack Compose modern, cara idiomatik adalah menyediakan objek Kotlin dengan referensi kelas `Color` untuk menjamin type-safety murni tanpa overhead inflasi XML runtime.
9. **B** — Mengubah ukuran geometris (padding, border, margin) saat pergantian tema memaksa browser menghitung ulang tahap Layout/Reflow. Tema hanya boleh memodifikasi properti pada tahap Paint/Composite (warna).
10. **B** — `transitive: true` menunda transformasi token hingga semua variabel alias yang dirujuknya selesai dievaluasi nilainya.

#### Pembahasan Skenario Kasus Produksi (Bagian 3)

* **Skenario 1 (The Cascading White-out Incident):**
  * *Root-cause:* Terjadi kegagalan alias mapping di **Tier 2 (Semantic Layer)** atau penyalahgunaan Global Token di **Tier 3 (Component Layer)**. Komponen teks kemungkinan mengonsumsi semantic token `color.text.inverse` yang dinamis berubah menjadi putih pada Dark Mode, namun komponen container secara keliru mengonsumsi global token primitif hardcoded `color.palette.white` alih-alih semantic token `color.background.canvas`.
  * *Solusi CI:* Tambahkan tahap pengujian integrasi kontras warna headless (seperti paket `@axe-core` atau algoritma contrast checker internal) di CI. Buat matriks pasangan token: foreground `color.text.*` WAJIB dipasangkan dengan background `color.surface.*` padanannya. Jika rasio kontras < 4.5:1, build CI dihentikan paksa (*exit code 1*).

* **Skenario 2 (The Multi-Package Version Drift):**
  * *Kelemahan:* Distribusi token terfragmentasi; tidak ada orkestrasi *Single Release Train*. Setiap platform mengonsumsi token melalui mekanisme yang tidak sinkron (Web mengonsumsi branch manual, Android tidak mengunci versi dependencies, iOS mengalami runtime crash karena referensi token dihapus tanpa deprecation warning).
  * *Solusi Release Management:* Integrasikan skema **Atomic Monorepo Release** berbasis tool seperti Changesets atau Semantic Release. Satu merge commit di repositori token induk otomatis memicu tag versi semantik yang sama (misal: v2.4.0) secara serentak ke 3 package manager target: NPM (`@corp/tokens-web`), Maven Central (`com.corp:tokens-android`), dan Swift Package Manager (`TokensIOS`). Terapkan kontrak *Semantic Versioning*: perubahan yang menghapus token wajib menaikkan MAJOR version.

* **Skenario 3 (High-Frequency Variable Recalculation Bottleneck):**
  * *Analisis Masalah:* Menempatkan variabel CSS pada ribuan baris DOM table yang dianimasikan memaksa browser melakukan *Style Recalculation* yang mahal pada ribuan node individual saat terjadi event `hover`. Penggunaan `transition: all` juga memicu browser menginterpolasi setiap properti yang dapat dianimasikan pada setiap frame (16.6ms).
  * *Solusi Restrukturisasi:*
    1. Hindari mendeklarasikan CSS variables dinamis langsung pada sub-elemen berulang (sel tabel). Deklarasikan variabel di level kontainer tabel induk (`:root` atau `.table-container`).
    2. Hapus `transition: all`. Batasi animasi hanya pada properti yang diproses pada GPU layer: `transition: transform 150ms ease, opacity 150ms ease`.
    3. Untuk hover row, gunakan pewarnaan background class murni atau manfaatkan pseudo-class `:hover` langsung pada level parent selektor tanpa menyematkan evaluasi variabel baru di subtree tabel.

---

## 16. Summary

* **Arsitektur Token Berlapis:** Keberhasilan skala sistem desain enterprise ditentukan oleh disiplin pembagian lapisan: Global (Primitif), Semantic (Konteks & Tema), dan Component (Isolasi Anatomi). Pemisahan ini memutus kopling langsung antara nilai literal dan implementasi UI.
* **Integritas Graf:** Keterkaitan antar token membentuk struktur data Directed Acyclic Graph (DAG). Pipeline kompilasi produksi wajib memvalidasi ketiadaan *cyclic dependencies* dan *dangling references* sebelum memproses file keluaran.
* **Transformasi Multi-Platform Deterministik:** Menggunakan engine kompilasi modern seperti Style Dictionary v4, spesifikasi desain tunggal dapat diterjemahkan secara otomatis menjadi native primitives yang aman secara tipe data (CSS Variables, TypeScript interfaces, Jetpack Compose Colors, dan SwiftUI objects).
* **Otomasi Mutu (Quality Assurance):** Desain sistem kelas enterprise tidak mengandalkan pengecekan manual. Validasi aksesibilitas (kontras warna WCAG), transformasi modular-fluid skala tipografi, serta rilis versi semantik wajib diotomatisasi penuh melalui pipeline integrasi berkelanjutan (CI/CD).