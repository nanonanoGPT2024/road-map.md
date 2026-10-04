# Bab 06 Module 01: Design Systems Architecture & Token Engineering

---

## SEKSI 01 — IDENTITAS MODUL

* **Track:** Product Design Engineering
* **Kategori:** 03-Frontend-and-Mobile
* **Modul:** Bab 06 Module 01 — *Design Systems Architecture & Token Engineering*
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat Pengetahuan:** 
  * Pemahaman mendalam tentang CSS Modern (CSS Custom Properties, Cascade Layers `@layer`, Color Spaces seperti Oklch).
  * Penguasaan TypeScript (AST, Generic Constraints, Template Literal Types, Typings Compiler API).
  * Arsitektur Frontend Komponen (React/Web Components, Atomic Design, CSS-in-JS vs Zero-Runtime CSS).
  * Pemahaman dasar tentang Pipeline CI/CD, Registry Package Management (npm/jfrog), dan Tooling Node.js/Build Systems.
* **Target Ekosistem:** Cross-Platform Enterprise (Web/DOM, React Native, iOS UIKit/SwiftUI, Android Compose).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Mendesain Taksonomi Token Multi-Tier:** Merancang dan mengimplementasikan arsitektur token desain tiga tingkat (*Global/Primitive*, *Semantic/Alias*, dan *Component-Scoped*) yang memisahkan data mentah dari konteks kegunaan visual.
2. **Membangun Automated Token Pipeline Engine:** Mengonfigurasi engine transformasi berbasis JSON/DTCG (*Design Tokens Community Group*) menggunakan Style Dictionary dan parser kustom untuk mengompilasi artefak multi-platform (CSS Variables, SCSS, TypeScript Const/Types, iOS Swift Structs, Android Compose Objects).
3. **Mengimplementasikan Algoritma Perceptual Color Spaces & Theming Dinamis:** Memanfaatkan ruang warna modern (`oklch`, `cam16`) untuk kalkulasi kontras otomatis (WCAG 2.2 APCA / AA/AAA Compliance) dan runtime theming (Light, Dark, High-Contrast) tanpa *layout shift* atau *re-rendering* berlebihan.
4. **Menerapkan Validasi Skema & Kontrak Tipe Statis:** Mengintegrasikan skema validasi deklaratif (Zod/JSON Schema) dalam pipeline CI untuk mencegah degradasi backward-compatibility token sebelum perilisan paket.
5. **Menghubungkan Design-to-Code Sync Engine:** Membangun *bidirectional bridge* atau *headless pipeline* dari Figma Variables API ke Git repository yang mengeksekusi *automated pull requests* lengkap dengan analisis dampak perubahan visual (Visual Regression Testing & Token Diffing).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa perangkat lunak enterprise skala besar, kesalahan fatal yang sering terjadi adalah menganggap *Design System* sekadar repositori komponen UI (seperti kumpulan tombol, modal, dan input). Paradigma ini rapuh karena mengikat logika visual langsung ke layer implementasi framework web.

### 1. The Single Source of Truth (SSOT) as Data, Not Code
*Design Tokens* adalah kontrak data mendasar dari sebuah antarmuka pengguna. Token bukan kode; token adalah **metadata arsitektur visual** yang terkuantisasi. Warna `#0052CC` bukan sekadar string heksadesimal dalam berkas CSS, melainkan nilai primitif yang merepresentasikan variabel atomik `color.blue.600`, yang diabstraksi menjadi semantik `color.interactive.primary.default`, dan akhirnya dipetakan ke tingkat komponen `button.primary.background.default`.

```
[ Mental Model: Dependency Direction ]

BAD ARCHITECTURE:
Figma Styles ---> React UI Library ---> Android / iOS / Web Apps
(Frontend Web menjadi bottleneck dan single point of truth yang rapuh)

ENTERPRISE ARCHITECTURE:
                [ DESIGN TOKEN REPO (JSON DTCG) ]
                                |
               +----------------+----------------+
               | (Build Pipeline: Style Dict)     |
               v                v                v
        Web (CSS/TS)     Android (Compose)   iOS (SwiftUI)
               |                |                |
               +----------------+----------------+
                                |
                   Cross-Platform Client Apps
```

### 2. Separation of Intent from Value
Pemisahan intensi visual (*Intent*) dari nilai fisik (*Value*) adalah inti dari pemeliharaan skala besar:
* **Nilai Primitif (Primitive/Raw):** Menyatakan apa adanya (`blue-500: #2979FF`). Nilai ini tidak memiliki opini tentang bagaimana atau di mana ia harus digunakan.
* **Nilai Semantik (Semantic/Intent):** Menyatakan intensi penggunaannya (`surface.interactive.hover: {ref: blue-500}`). Saat *Dark Mode* aktif, nilai semantik ini bertukar referensi ke `blue-400` tanpa mengubah kontrak penamaan di level komponen.
* **Nilai Komponen (Component-Scoped):** Mengisolasi hak milik (*ownership*) variabel visual pada batas komponen (`button.color.background: {ref: surface.interactive.hover}`). Ini mencegah efek samping (*unintended blast radius*) saat sebuah komponen membutuhkan modifikasi mikro tanpa merusak komponen lain.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur hidup end-to-end token desain mencakup transformasi data dari Figma ke multi-target compiler:

```
+---------------------------------------------------------------------------------------+
| PHASE 1: DESIGN AUTHORING & EXTRACTION                                                |
|                                                                                       |
|  +--------------------+       REST API       +-------------------------------------+  |
|  | Figma Variables    | -------------------> | Extraction Engine (Node.js/TS CLI)  |  |
|  | - Primitives       |   (Personal Access   | - Normalisasi ke DTCG Format        |  |
|  | - Modes (Dark/Light|        Token)        | - Resolve Aliases & Groups          |  |
|  +--------------------+                      +-------------------------------------+  |
+------------------------------------------------------------------|--------------------+
                                                                   | Emit Raw JSON
+------------------------------------------------------------------v--------------------+
| PHASE 2: VALIDATION, CONTRACT INTEGRITY & TOKEN COMPILATION                           |
|                                                                                       |
|  +---------------------------------------------------------------------------------+  |
|  | Token Repository (Git)                                                          |  |
|  |  ├── tokens/                                                                    |  |
|  |  │    ├── primitive/color.json                                                  |  |
|  |  │    ├── semantic/light.json & semantic/dark.json                              |  |
|  |  │    └── component/button.json                                                 |  |
|  |  └── schema/token.schema.json (Zod Engine Validator)                            |  |
|  +---------------------------------------------------------------------------------+  |
|                                          |                                            |
|                                          v                                            |
|  +---------------------------------------------------------------------------------+  |
|  | Style Dictionary v4 Compilation Engine (Custom Preprocessors, Transforms)       |  |
|  +---------------------------------------------------------------------------------+  |
|         |                        |                        |                |          |
+---------|------------------------|------------------------|----------------|----------+
          |                        |                        |                |
+---------v--------+      +--------v---------+     +--------v-------+  +-----v----------+
| PHASE 3: EMIT    |      |                  |     |                |  |                |
| Web Target       |      | TypeScript       |     | Android Target |  | iOS Target     |
|                  |      |                  |     |                |  |                |
| - tokens.css     |      | - tokens.d.ts    |     | - Color.kt     |  | - Color.swift  |
|   (:root,        |      | - tokens.esm.js  |     |   (Jetpack     |  |   (SwiftUI     |
|    [data-theme]) |      |   (Frozen Object)|     |    Compose)    |  |    ShapeStyle) |
+------------------+      +------------------+     +----------------+  +----------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Standar DTCG (Design Tokens Community Group)
Spesifikasi W3C Design Tokens Community Group menentukan format JSON baku dengan kata kunci berawalan `$`:
* `$value`: Nilai definitif token (bisa berupa skalar absolut, array, atau string referensi alias `{color.brand.primary}`).
* `$type`: Menentukan kategori tipe: `color`, `dimension`, `fontFamily`, `fontWeight`, `duration`, `cubicBezier`, `number`.
* `$description`: Dokumentasi teknis yang akan diekstraksi ke IDE Intellisense atau JSDoc.
* `$extensions`: Metadata kustom, misalnya integrasi Figma Mode, target platform exclusion, atau algoritma contrast constraint.

```json
{
  "semantic": {
    "color": {
      "action": {
        "primary": {
          "default": {
            "$value": "{primitive.color.blue.600}",
            "$type": "color",
            "$description": "Warna latar belakang utama untuk interactive clickable elements dalam mode istirahat."
          }
        }
      }
    }
  }
}
```

### 2. Token Graph Resolution Engine
Di dalam build engine, referensi token membentuk **Directed Acyclic Graph (DAG)**:
* Resolver harus mengeksekusi *topological sort* untuk memvalidasi bahwa tidak ada siklus ketergantungan melingkar (*circular references*), seperti `A -> B -> C -> A`.
* Resolusi alias mengevaluasi rantai nilai secara rekursif hingga menemukan nilai primitif literal.

```
Graph:
[button.primary.bg] ---> [semantic.color.action.primary.default] ---> [primitive.color.blue.600] ---> "#1565C0"
```

Jika terjadi referensi hilang (*dangling node*), compiler melempar exception fatal sebelum proses emisi platform dieksekusi.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Perceptual Uniformity: Dari sRGB ke OKLCH
Format warna lama seperti HEX, RGB, dan HSL tidak memiliki keseragaman perseptual (*perceptually non-uniform*). Misalnya, warna murni kuning (`#FFFF00`) dan biru murni (`#0000FF`) memiliki nilai *Lightness* yang sama dalam ruang HSL ($L = 50\%$), namun mata manusia memandang kuning jauh lebih terang daripada biru. Ini mengakibatkan kegagalan kalkulasi otomatis rasio kontras.

Ruang warna **OKLCH** (Lightness, Chroma, Hue) memecahkan masalah ini:
* $L$ (*Perceived Lightness*): $0\%$ hingga $100\%$, konsisten secara linear terhadap sensitivitas sel kerucut retina manusia.
* $C$ (*Chroma*): Kemurnian/kejenuhan warna (mulai dari $0$ hingga sekitar $0.4$).
* $H$ (*Hue*): Sudut roda warna ($0^\circ$ hingga $360^\circ$).

Dalam rekayasa token modern:
$$\text{Langkah Palette Generative} \implies L_{n} = L_{\text{base}} \pm (n \times \Delta L)$$
Dengan OKLCH, mempertahankan $L$ yang konstan antar warna yang berbeda menjamin rasio kontras terhadap warna teks tetap identik tanpa penyesuaian manual.

### 2. Cascade Layers (`@layer`) & CSS Custom Properties Engine
Untuk meniadakan isu *specificity war*, CSS tokens modern wajib di-injeksi ke dalam `@layer` standard:

```css
@layer ds-tokens, ds-reset, ds-components, ds-utilities;

@layer ds-tokens {
  :root {
    --ds-color-brand-primary: oklch(0.55 0.22 260);
    --ds-color-bg-canvas: oklch(0.99 0.002 260);
    --ds-color-text-main: oklch(0.15 0.02 260);
  }

  [data-theme="dark"] {
    --ds-color-bg-canvas: oklch(0.12 0.01 260);
    --ds-color-text-main: oklch(0.95 0.005 260);
  }
}
```

Dengan mengisolasi token ke `@layer ds-tokens`, gaya komponen tidak dapat secara tidak sengaja menimpa variabel global dengan tingkat spesifisitas yang tidak teratur.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental **Build Transformer Engine Sederhana** yang memproses berkas token DTCG mentah, memvalidasi dependensi siklis, menyelesaikan alias (*alias dereferencing*), dan mengekspor hasilnya ke format CSS Variables dan TypeScript Definitions.

### 1. `tokens.json` (Input Spesifikasi DTCG)
```json
{
  "primitive": {
    "color": {
      "blue": {
        "600": { "$value": "oklch(0.54 0.22 262.8)", "$type": "color" }
      },
      "neutral": {
        "100": { "$value": "oklch(0.98 0.001 0)", "$type": "color" },
        "900": { "$value": "oklch(0.14 0.005 0)", "$type": "color" }
      }
    }
  },
  "semantic": {
    "color": {
      "surface": {
        "brand": {
          "$value": "{primitive.color.blue.600}",
          "$type": "color"
        }
      },
      "text": {
        "primary": {
          "$value": "{primitive.color.neutral.900}",
          "$type": "color"
        }
      }
    }
  }
}
```

### 2. `build-tokens.ts` (Compiler Engine)
```typescript
import * as fs from 'fs';
import * as path from 'path';

interface TokenNode {
  $value: string | number;
  $type?: string;
  $description?: string;
  [key: string]: unknown;
}

type TokenTree = {
  [key: string]: TokenNode | TokenTree;
};

// Ekstraksi Flat Dictionary dengan pemisahan Key Path
function flattenTokens(tree: TokenTree, prefix = ''): Map<string, TokenNode> {
  let tokens = new Map<string, TokenNode>();

  for (const [key, value] of Object.entries(tree)) {
    const fullPath = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === 'object' && '$value' in value) {
      tokens.set(fullPath, value as TokenNode);
    } else if (value && typeof value === 'object') {
      const childTokens = flattenTokens(value as TokenTree, fullPath);
      tokens = new Map([...tokens, ...childTokens]);
    }
  }

  return tokens;
}

// Resolver Rekursif untuk Alias Token: {primitive.color.blue.600} -> Nilai Nyata
function resolveValue(
  value: string,
  tokenMap: Map<string, TokenNode>,
  visited = new Set<string>()
): string {
  const aliasRegex = /\{([^}]+)\}/g;

  if (!aliasRegex.test(value)) {
    return value;
  }

  return value.replace(aliasRegex, (_, tokenPath: string) => {
    if (visited.has(tokenPath)) {
      throw new Error(`Circular Dependency Detected: ${Array.from(visited).join(' -> ')} -> ${tokenPath}`);
    }

    const referencedToken = tokenMap.get(tokenPath);
    if (!referencedToken) {
      throw new Error(`Dangling Token Reference: Token '${tokenPath}' tidak ditemukan!`);
    }

    visited.add(tokenPath);
    const resolved = resolveValue(String(referencedToken.$value), tokenMap, new Set(visited));
    return resolved;
  });
}

function compileTokens(inputPath: string, outDir: string) {
  const rawData = fs.readFileSync(inputPath, 'utf-8');
  const tokenTree: TokenTree = JSON.parse(rawData);
  const flatTokens = flattenTokens(tokenTree);

  const resolvedTokens = new Map<string, { value: string; type?: string }>();

  for (const [key, token] of flatTokens.entries()) {
    const finalValue = resolveValue(String(token.$value), flatTokens);
    resolvedTokens.set(key, { value: finalValue, type: token.$type });
  }

  // Generasi CSS Variables
  let cssOutput = `/* AUTO-GENERATED DESIGN TOKENS. JANGAN DIEDIT MANUAL. */\n`;
  cssOutput += `@layer ds-tokens {\n  :root {\n`;

  for (const [key, token] of resolvedTokens.entries()) {
    const cssVarName = `--ds-${key.replace(/\./g, '-')}`;
    cssOutput += `    ${cssVarName}: ${token.value};\n`;
  }
  cssOutput += `  }\n}\n`;

  // Generasi TypeScript Definition
  let tsOutput = `// AUTO-GENERATED DESIGN TOKENS TYPE CONTRACT\n`;
  tsOutput += `export const DesignTokens = {\n`;

  for (const [key, token] of resolvedTokens.entries()) {
    tsOutput += `  "${key}": "${token.value}",\n`;
  }
  tsOutput += `} as const;\n\n`;
  tsOutput += `export type DesignTokenKey = keyof typeof DesignTokens;\n`;

  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  fs.writeFileSync(path.join(outDir, 'tokens.css'), cssOutput);
  fs.writeFileSync(path.join(outDir, 'tokens.ts'), tsOutput);
  console.log(`✓ Kompilasi token sukses dieksekusi ke direktori '${outDir}'.`);
}

// Eksekusi pipeline
compileTokens(path.join(__dirname, 'tokens.json'), path.join(__dirname, 'dist'));
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari `build-tokens.ts`:

1. **Struktur Data `TokenNode` & `TokenTree` (Baris 4–13):**
   Mendefinisikan kontrak rekursif untuk membaca struktur direktori JSON arbitrary. Tipe `$value` mendukung variasi primitif sesuai spesifikasi DTCG.
2. **Fungsi `flattenTokens` (Baris 16–30):**
   Menggunakan rekursi untuk meratakan hierarki *nested object* menjadi flat key-path dipisahkan titik (misal: `semantic.color.surface.brand`). Flat map ini mempercepat waktu pencarian referensi menjadi $O(1)$.
3. **Pendeteksian Regex Alias `aliasRegex = /\{([^}]+)\}/g` (Baris 38):**
   Mencari token dengan sintaksis kurung kurawal ganda, mengekstrak path internal token yang dirujuk.
4. **Pendeteksian Siklus Dependensi `visited.has(tokenPath)` (Baris 44–46):**
   Memeriksa apakah token dalam rantai resolusi saat ini telah dipanggil sebelumnya. Jika ya, siklus rekursi dihentikan seketika dan melempar `Error`, mencegah stack overflow.
5. **Penanganan Dangling Node (Baris 49–51):**
   Memastikan integritas referensial. Jika token merujuk ke path yang tidak terdefinisi, pipeline build gagal (*fail-fast*).
6. **Emisi CSS Variables dengan Format Kebab-Case (Baris 73–76):**
   Menormalisasi struktur namespace token (dipisahkan tanda titik) menjadi format native CSS custom property standar: `--ds-semantic-color-surface-brand`.
7. **Emisi TypeScript Type Safety `as const` (Baris 82–89):**
   Menerapkan narrowing tipe literal pada TypeScript object, menghasilkan tipe union `DesignTokenKey` yang presisi untuk autocomplete di level komponen.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks Kasus
**Perusahaan:** Fintech Global Scale-up ("PaySphere")  
**Kondisi Awal:** 
* Memiliki 4 produk web utama (React, Vue legacy, dan Internal Tools Vanilla JS) serta 2 aplikasi native (iOS & Android).
* Tim UI/UX meluncurkan *Rebranding* besar-besaran dan implementasi regulasi aksesibilitas finansial (W3C WCAG 2.2 AA / APCA).
* Developer melakukan *hardcode* nilai warna di ratusan berkas SCSS dan Styled-Components.
* Sinkronisasi token memakan waktu 3–4 sprint setiap kali ada pembaruan palet warna, dengan regresi visual mencapai 18% di halaman kritis checkout.

### Target Solusi & Kebutuhan Teknis
1. Membangun repository terpusat `design-tokens` yang didistribusikan via NPM/GitHub Packages dan Maven/Cocoapods.
2. Menerapkan Style Dictionary v4 dengan format JSON DTCG resmi.
3. Otomatisasi pemetaan Multi-Theme (Day, Night, High-Contrast) yang dapat dieksekusi secara instan di sisi klien melalui CSS Variables tanpa perlu rebuild bundle JavaScript.
4. Mengamankan pipeline dengan integrasi CI yang menolak token jika kontras teks terhadap latar belakang di bawah rasio 4.5:1.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah arsitektur produksi Style Dictionary v4 modern dengan validasi kontras warna berbasis WCAG/APCA custom transform.

### 1. Skema Konfigurasi: `style-dictionary.config.ts`
```typescript
import StyleDictionary from 'style-dictionary';
import type { TransformedToken } from 'style-dictionary';

// Helper: Formula Konversi Linear RGB & Luminance WCAG 2.2
function getLuminance(r: number, g: number, b: number): number {
  const [aR, aG, aB] = [r, g, b].map(v => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * aR + 0.7152 * aG + 0.0722 * aB;
}

function parseHex(hex: string): [number, number, number] {
  const cleanHex = hex.replace('#', '');
  const bigint = parseInt(cleanHex, 16);
  return [(bigint >> 16) & 255, (bigint >> 8) & 255, bigint & 255];
}

// 1. Custom Transform: Validasi Kontras Aksesibilitas di Tahap Kompilasi
StyleDictionary.registerTransform({
  name: 'accessibility/contrast-guard',
  type: 'attribute',
  filter: (token: TransformedToken) => token.$type === 'color' && !!token.contrastAgainst,
  transform: (token: TransformedToken) => {
    const bgTokenRef = token.contrastAgainst as string;
    const fgHex = token.value as string;
    
    // Asumsi bgTokenRef terselesaikan ke hex untuk validasi sederhana
    const [r1, g1, b1] = parseHex(fgHex);
    const [r2, g2, b2] = parseHex(bgTokenRef);

    const l1 = getLuminance(r1, g1, b1);
    const l2 = getLuminance(r2, g2, b2);

    const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);

    if (ratio < 4.5) {
      throw new Error(
        `[ACCESSIBILITY VIOLATION] Token '${token.name}' dengan rasio kontras ${ratio.toFixed(
          2
        )}:1 melanggar WCAG AA (Minimum 4.5:1) terhadap ${bgTokenRef}!`
      );
    }
    return token.attributes;
  }
});

// 2. Custom Format: CSS Custom Properties dengan @layer Enkapsulasi
StyleDictionary.registerFormat({
  name: 'css/layered-variables',
  format: ({ dictionary, options }) => {
    const selector = options.selector || ':root';
    const lines = dictionary.allTokens.map((token: TransformedToken) => {
      return `  --ds-${token.name}: ${token.value};`;
    });

    return `@layer ds-tokens {\n  ${selector} {\n${lines.join('\n')}\n  }\n}\n`;
  }
});

// 3. Konfigurasi Multi-Platform Pipeline
const sd = new StyleDictionary({
  source: ['tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      transforms: ['accessibility/contrast-guard'],
      buildPath: 'build/css/',
      files: [
        {
          destination: 'variables.css',
          format: 'css/layered-variables',
          options: {
            selector: ':root'
          }
        }
      ]
    },
    typescript: {
      transformGroup: 'js',
      buildPath: 'build/ts/',
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
    },
    compose: {
      transformGroup: 'compose',
      buildPath: 'build/android/',
      files: [
        {
          destination: 'DesignTokens.kt',
          format: 'compose/object',
          options: {
            className: 'DesignTokens',
            packageName: 'com.paysphere.designsystem.tokens'
          }
        }
      ]
    }
  }
});

// Eksekusi Kompilasi Style Dictionary
sd.buildAllPlatforms();
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter / Arsitektur | 1. Zero-Runtime Design Tokens (CSS Variables Engine) | 2. CSS-in-JS Tokens (Runtime Injection, eg: Emotion/Styled) | 3. Utility-First Dynamic Classes (Tailwind Generated Tokens) |
| :--- | :--- | :--- | :--- |
| **Parsing & Runtime Cost** | **Nol / Zero CPU Cost.** CSS variables di-parse native oleh browser engine C++. | **Tinggi.** JavaScript thread melakukan serialisasi string, hashing, dan injeksi `<style>` runtime. | **Nol.** Utility classes diekstraksi ke CSS statis saat build-time. |
| **Theming Performance** | **Instan ($O(1)$).** Cukup mengganti atribut DOM `[data-theme="dark"]`, CSS cascade menangani sisanya. | **Lambat.** Memicu React Virtual DOM diffing & render ulang komponen pada root context change. | **Menengah.** Bergantung pada mekanisme pertukaran class name (`dark:` modifier) pada elemen root. |
| **Type Safety DevEx** | **Menengah.** Membutuhkan tooling tambahan (`typed-css-modules` atau declaration binding). | **Sangat Baik.** TypeScript autocomplete terikat langsung via polymorphic props (`theme.color.*`). | **Sangat Baik.** Tersedia autocomplete via Tailwind Language Server dan static typings. |
| **Cross-Platform Portability** | **Sangat Tinggi.** File abstraksi JSON mudah di-compile ke Swift, Compose, dan Web. | **Sangat Rendah.** Terikat secara erat ke Web DOM dan ecosystem JavaScript / React Native. | **Menengah.** Memerlukan compiler parser pihak ketiga untuk mengekstrak tailwind.config.js ke mobile. |
| **Ukuran Bundle (JS Overhead)** | **0 KB JS.** Tersimpan secara statis di CDN atau berkas `.css` terpisah. | **Bertambah proportional** seiring bertambahnya token dan kompleksitas interpolasi kode. | **0 KB JS.** CSS bundle hanya memuat kelas utilitas yang terpakai (*Purged/Tree-shaken*). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Flash of Inaccurate Theme (FOIT)
Saat pengguna dengan preferensi tema gelap (*Dark Mode*) mengakses web, browser sering kali merender warna putih (*default light*) sesaat sebelum JavaScript mengeksekusi inisialisasi tema.
* **Mitigasi:**
  Injeksi *blocking inline script* berbobot ringan di dalam tag `<head>` sebelum pemuatan elemen DOM utama:
  ```html
  <head>
    <script>
      (function() {
        const theme = localStorage.getItem('theme') || 
          (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        document.documentElement.setAttribute('data-theme', theme);
      })();
    </script>
  </head>
  ```

### 2. Token Fallback Broken Chain
Ketika CSS Custom Properties hilang atau tidak terdefinisi pada runtime karena kesalahan build, komponen menjadi transparan atau rusak secara visual tanpa pesan galat di konsol.
* **Mitigasi:**
  Manfaatkan *CSS Variable Fallbacks* bertingkat dalam implementasi komponen internal:
  ```css
  .button-primary {
    background-color: var(
      --ds-button-bg,
      var(--ds-semantic-action-primary, #0052cc)
    );
  }
  ```

### 3. Alpha Composite & Opacity Anti-Pattern
Menerapkan nilai `opacity: 0.5` pada elemen kontainer mereduksi seluruh teks di dalamnya, menurunkan rasio kontras visual di bawah batas standar aksesibilitas.
* **Mitigasi:**
  Hindari token opasitas generik. Selalu gunakan kompilasi warna dengan alpha channel terdedikasi menggunakan ruang warna modern:
  `--ds-surface-overlay: oklch(from var(--ds-surface-canvas) l c h / 0.5);`

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menamai Token Menggunakan Nilai Fisik (*Literal Naming*)
* **Salah:** `"color-blue-500": "#0052CC"` digunakan langsung di dalam kode styling komponen Button.
* **Akibat:** Ketika tim desain memutuskan mengubah skema warna brand utama menjadi ungu, nama token `color-blue-500` tetap bertahan di seluruh codebase, menyebabkan disonansi semantik (*cognitive dissonance*).
* **Solusi:** Terapkan pemetaan semantik:  
  `primitive.blue.500` $\implies$ `semantic.brand.primary` $\implies$ `component.button.background`.

### 2. Polusi Scope Token (*Global Leakage*)
* **Salah:** Mendaftarkan seluruh token komponen spesifik langsung di `:root` CSS selector tanpa namespace.
* **Akibat:** Tabrakan nama variabel (*variable collisions*) antar tim micro-frontend atau modul independen.
* **Solusi:** Gunakan hierarki prefix ketat: `--ds-[domain]-[context]-[element]-[variant]-[state]`.  
  Contoh: `--ds-cmp-button-primary-bg-hover`.

### 3. Mengabaikan Dynamic Font Scaling
* **Salah:** Menetapkan ukuran font token dalam satuan fisik pixel absolut: `"font-size-body": "16px"`.
* **Akibat:** Pelanggaran aksesibilitas untuk pengguna sistem operasi yang memperbesar skala font sistem (*OS-level Accessibility Zoom*).
* **Solusi:** Kompilasi ukuran teks ke satuan berbasis relatif `rem` dengan asumsi dasar $1\text{rem} = 16\text{px}$, serta tentukan ukuran `rem` secara deterministik pada transformer token.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Single-Direction Token Flow:**
   Perubahan desain tidak boleh diubah manual di level kode komponen CSS. Alur wajib satu arah:  
   **Figma Variables $\to$ GitHub PR $\to$ Style Dictionary Build $\to$ NPM Package Versioning $\to$ Consumption di Aplikasi.**
2. **Kompilasi Semantik Statis untuk Dark Mode:**
   Jangan buat berkas CSS terpisah untuk dark mode jika tidak diperlukan. Satukan dalam satu file dengan selektor media dan atribut data:
   ```css
   :root {
     --ds-surface-default: oklch(0.98 0.01 240);
   }
   :root[data-theme="dark"] {
     --ds-surface-default: oklch(0.12 0.02 240);
   }
   @media (prefers-color-scheme: dark) {
     :root:not([data-theme="light"]) {
       --ds-surface-default: oklch(0.12 0.02 240);
     }
   }
   ```
3. **Immutability Kontrak (Semver Policy):**
   * Perubahan nilai visual tanpa perubahan nama token = **PATCH** (`1.0.1`).
   * Penambahan token baru yang bersifat backward-compatible = **MINOR** (`1.1.0`).
   * Penghapusan token atau restrukturisasi penamaan namespace = **MAJOR** (`2.0.0`).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Eliminasi Paint Triggers & Rekalkulasi Style
Ketika CSS Custom Properties diubah melalui runtime JavaScript (misalnya, `element.style.setProperty('--token', value)`), browser melakukan *Style Invalidation* pada seluruh subtree node tersebut.
* **Optimasi:**
  Terapkan token dinamis hanya pada level teratas (`:root` atau kontainer *layout boundary*) yang memiliki properti CSS `contain: paint layout style;`. Ini membatasi kalkulasi ulang layout hanya pada sub-pohon tertentu tanpa merusak performa frame rate ($60$–$120\text{ FPS}$).

### 2. Pengurangan Ukuran Payload (Bundle Shaking Tokens)
Menyimpan token sebagai obyek JSON JavaScript raksasa akan membebani engine v8 untuk parsing heap memory.
* **Metrik:** JSON token sebesar 500 KB setara dengan ~1.5 MB memori uncompressed saat dieksekusi di runtime heap.
* **Strategi:** Ekspor token untuk Web murni dalam bentuk CSS statis terkompresi Brotli (`tokens.min.css`). Akses di dalam TypeScript hanya menggunakan *Type-only Declaration* (`tokens.d.ts`), menghasilkan beban JavaScript di klien sebesar **0 byte**.

```
[Distribusi Token]
tokens.json (Source, 350 KB)
       │
       ├── Web Browser: tokens.min.css.br (Hanya ~8 KB