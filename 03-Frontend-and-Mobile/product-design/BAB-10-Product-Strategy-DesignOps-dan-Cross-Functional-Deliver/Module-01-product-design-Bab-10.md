# MODUL 10.01: PRODUCT STRATEGY, DESIGNOPS & CROSS-FUNCTIONAL DELIVERY

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** Frontend and Mobile Engineering
* **Kategori:** 03-Frontend-and-Mobile
* **Topik:** Product Strategy, DesignOps & Cross-Functional Delivery
* **Tingkat Kesulitan:** Advanced / Staff-Level
* **Prasyarat:** Pengalaman arsitektur Design Systems (Figma Tokens, Tailwind/CSS-in-JS), CI/CD pipeline automation (GitHub Actions), pemahaman mendalam tentang siklus hidup software development (SDLC), TypeScript, dan Node.js runtime.

---

## SEKSI 02 — LEARNING OBJECTIVES
Pada akhir modul ini, peserta didik mampu:
1. Merumuskan integrasi antara **Product Strategy** berbasis metrik bisnis (CAC, LTV, TTM) dengan eksekusi teknis desain frontend.
2. Membangun infrastruktur **DesignOps** berskala enterprise yang mengotomatisasi sinkronisasi Design Tokens dari Figma API langsung ke multi-platform frontend codebases (Web, iOS, Android).
3. Menganalisis dan mengeliminasi friksi dalam *handoff cross-functional* menggunakan prinsip *Single Source of Truth* (SSOT) berbasis token design JSON terstandarisasi W3C.
4. Menerapkan arsitektur automated linting, validasi visual regression, dan headless testing pada design token pipeline.
5. Mengimplementasikan metrik operasional kuantitatif untuk mengukur performa DesignOps, defek desain di level produksi, dan efisiensi delivery engineering.

---

## SEKSI 03 — MINDSET & MENTAL MODEL
* **Kode Adalah Proyeksi Desain, Desain Adalah Spesifikasi Sistem:** Perlakukan desain UI bukan sebagai file grafis statis, melainkan sebagai *contract-first state machine*. Komponen Figma adalah abstraksi deklaratif; implementasi frontend adalah interpretasi runtime-nya.
* **Paradigma Zero-Manual Handoff:** Dokumentasi visual manual seperti redlining statis adalah anti-pattern. Semua keputusan desain atomik (warna, tipografi, spacing, elevasi, motion) harus didefinisikan sebagai data terstruktur (JSON) yang dapat dikompilasi, diuji, dan di-deploy secara otomatis.
* **DesignOps Sebagai Platform Engineering:** Perlakukan tim Product Design dan Frontend Engineers sebagai *internal customers*. Infrastruktur DesignOps dibangun dengan standar platform engineering: CI/CD, semantic versioning, contract testing, dan monitoring observabilitas drift.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur aliran data otomatisasi DesignOps dari Figma Tokens hingga deployment artefak multi-platform:

```
+-----------------------------------------------------------------------------+
|                           FIGMA DESIGN WORKSPACE                            |
|  [Design Tokens / Variables] ---> [Tokens Studio / Native Variables Plugin]  |
+---------------------------------------+-------------------------------------+
                                        | Push via Webhook / REST API
                                        v
+-----------------------------------------------------------------------------+
|                     INTERMEDIATE DATA STORE (GIT REPO)                      |
|                  Raw Design Tokens (W3C DTCG Format JSON)                   |
|                  Path: tokens/tokens.raw.json                               |
+---------------------------------------+-------------------------------------+
                                        | GitHub Actions Trigger (on: push)
                                        v
+-----------------------------------------------------------------------------+
|                      DESIGNOPS CI/CD PIPELINE ENGINE                        |
|                                                                             |
|  +--------------------+      +--------------------+      +---------------+  |
|  |  Schema Validation | ---> | Token Resolution   | ---> | Accessibility |  |
|  |  (Zod / AJV DTCG)  |      | (Aliases & Math)   |      | Linting (WCAG)|  |
|  +--------------------+      +--------------------+      +---------------+  |
|                                        |                                    |
|                                        v                                    |
|  +-----------------------------------------------------------------------+  |
|  |                  Style-Dictionary Compilation Engine                 |  |
|  |               Transforms, Formats, and Custom Actions                 |  |
|  +-------------------------------------+---------------------------------+  |
+----------------------------------------|------------------------------------+
                                         | Generates
     +-----------------------------------+----------------------------------+
     |                                   |                                  |
     v                                   v                                  v
+--------------------+         +--------------------+         +--------------------+
| WEB ARTIFACTS      |         | ANDROID ARTIFACTS  |         | IOS ARTIFACTS      |
| - CSS Custom Props |         | - Jetpack Compose  |         | - Swift Enums      |
| - Tailwind Config  |         |   Color/Type Files |         | - SwiftUI Theme    |
| - TS Types / Maps  |         | - XML Resources    |         |   Structures       |
+--------------------+         +--------------------+         +--------------------+
     |                                   |                                  |
     +-----------------------------------+----------------------------------+
                                         | Publishes via Semantic Release
                                         v
+-----------------------------------------------------------------------------+
|                     PRIVATE ARTIFACT REPOSITORIES                           |
|       npm registry (@company/tokens) | Maven Central | Swift Package Mgr    |
+-----------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Design Token Anatomy (W3C Community Group Standard)
Token tidak sekadar pasangan *key-value*. Token adalah entitas hierarkis dengan metadata kontekstual:
* **Global/Core Tokens:** Nilai primitif absolut yang berdiri sendiri (e.g., `blue-500: #1D63ED`).
* **Semantic/Alias Tokens:** Nilai yang mereferensikan Core Token dengan maksud fungsional (e.g., `color-brand-primary: {blue-500}`).
* **Component-Specific Tokens:** Nilai spesifik untuk instansiasi komponen tertentu (e.g., `button-primary-bg: {color-brand-primary}`).

```
[Core Token]  ──────>  [Semantic Token]  ──────>  [Component Token]
#1D63ED                color.interactive.fill     button.primary.default.background
(Hex/Raw Value)        (Intent & Usage Layer)     (Scoped Component Context)
```

### 2. The Transformation Pipeline
* **Lexical Parser:** Membaca tree JSON, mengurai token bertingkat, dan mengekstraksi metadata `$value`, `$type`, serta `$description`.
* **Resolver Engine:** Menyelesaikan *token alias references* (misalnya: `{color.primary.value}`) melalui penelusuran Topological Sort pada Directed Acyclic Graph (DAG) untuk menghindari siklus tak terbatas (*circular dependencies*).
* **Transformer Layer:**
  * Ukuran font (px) dikonversi ke unit `rem` untuk Web (`$fontSize / 16`).
  * Format warna (Hex/RGBA) dikonversi menjadi `Color(0xFF...)` untuk Compose atau `UIColor` untuk Swift.
* **Formatter/Serializer:** Menghasilkan file luaran target dengan indentasi dan typing yang valid untuk TypeScript, CSS, Swift, dan Kotlin.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Integrasi Product Strategy dan Cross-Functional Delivery
Produktivitas engineering berbanding lurus dengan kepastian spesifikasi desain. Dalam model lama (*waterfall handoff*), siklus umpan balik (*feedback loop*) antara Product Manager (PM), Desainer, dan Frontend Engineer memakan waktu hitungan hari atau minggu.

```
Tradisional Handoff:
[PRD Disetujui] -> [Desain Figma] -> [Spesifikasi PDF/Redline] -> [Slicing UI] -> [QA Menemukan Drift] -> [Redesign] (Loop 14 Hari)

DesignOps Continuous Delivery:
[PRD & Token Spec] -> [Update Figma Variables] -> [CI Automated Pipeline] -> [Auto PR Codebase] -> [Auto Visual Tests] (Loop < 30 Menit)
```

Metrik Bisnis yang Terdampak Langsung oleh DesignOps:
1. **Time-to-Market (TTM):** Pengurangan waktu siklus implementasi fitur baru (Cycle Time) hingga 40%.
2. **Defect Escape Rate (DER):** Penurunan rasio bug visual pada tahap QA/Production hingga 85%.
3. **Engineering Velocity:** Peniadaan tugas repetitif *CSS-slicing*, memungkinkan engineer fokus pada business logic, state handling, dan performa jaringan.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah pipeline Node.js mandiri berbasis TypeScript yang memvalidasi skema token, memeriksa kepatuhan aksesibilitas warna (WCAG AA Contrast Ratio $\ge 4.5:1$), dan mengompilasi output menjadi CSS Variables serta TypeScript Definitions.

### File: `engine/token-compiler.ts`

```typescript
import * as fs from 'fs';
import * as path from 'path';

// Representasi struktur token standar W3C DTCG
export interface DesignToken {
  $value: string;
  $type: 'color' | 'dimension' | 'fontFamily' | 'number';
  $description?: string;
}

export interface TokenGroup {
  [key: string]: DesignToken | TokenGroup;
}

// 1. Helper Fungsi Luminansi & Kontras (WCAG 2.1)
function parseHex(hex: string): [number, number, number] {
  const cleanHex = hex.replace('#', '');
  const bigint = parseInt(cleanHex, 16);
  return [(bigint >> 16) & 255, (bigint >> 8) & 255, bigint & 255];
}

function getLuminance(r: number, g: number, b: number): number {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

export function getContrastRatio(hex1: string, hex2: string): number {
  const [r1, g1, b1] = parseHex(hex1);
  const [r2, g2, b2] = parseHex(hex2);
  const lum1 = getLuminance(r1, g1, b1);
  const lum2 = getLuminance(r2, g2, b2);
  const brightest = Math.max(lum1, lum2);
  const darkest = Math.min(lum1, lum2);
  return (brightest + 0.05) / (darkest + 0.05);
}

// 2. Resolver Token Flattening Engine
export interface FlatToken {
  path: string[];
  name: string;
  value: string;
  type: string;
}

export function flattenTokens(obj: TokenGroup, currentPath: string[] = []): FlatToken[] {
  let results: FlatToken[] = [];
  for (const key of Object.keys(obj)) {
    const item = obj[key];
    if ('$value' in item) {
      results.push({
        path: [...currentPath, key],
        name: [...currentPath, key].join('-'),
        value: item.$value,
        type: item.$type
      });
    } else {
      results = results.concat(flattenTokens(item as TokenGroup, [...currentPath, key]));
    }
  }
  return results;
}

// 3. Serializers
export function generateCSSCustomProperties(tokens: FlatToken[]): string {
  const lines = tokens.map((t) => `  --${t.name}: ${t.value};`);
  return `:root {\n${lines.join('\n')}\n}\n`;
}

export function generateTypeScriptDefinitions(tokens: FlatToken[]): string {
  const lines = tokens.map((t) => `  readonly '${t.name}': '${t.value}';`);
  return `export const Tokens = {\n${lines.join('\n')}\n} as const;\n\nexport type TokenNames = keyof typeof Tokens;\n`;
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 4–11:** `DesignToken` dan `TokenGroup` mengimplementasikan spesifikasi resmi W3C Design Tokens Community Group (DTCG), di mana nilai menggunakan prefiks `$` (`$value`, `$type`) untuk membedakan antara metadata token dan child-node percabangan.
* **Baris 14–26:** Implementasi formula Rec. 709 untuk konversi sRGB ke *relative luminance*. Transformasi non-linear gamma expansion dilakukan sebelum perhitungan luminansi tertimbang.
* **Baris 28–36:** Menghitung rasio kontras relatif sesuai WCAG 2.1 formula: $(L_1 + 0.05) / (L_2 + 0.05)$. Ini bertindak sebagai gatekeeper statis: jika kombinasi warna teks dan background melanggar batas $4.5:1$, sistem memicu *build error*.
* **Baris 46–62:** Algoritma rekursif *tree-walking* (`flattenTokens`) yang mereduksi hierarki JSON multidimensi menjadi array satu dimensi. Penamaan token digabungkan dengan pemisah *kebab-case* (misal: `color.action.primary` menjadi `color-action-primary`).
* **Baris 65–73:** Serializer yang menghasilkan format target platform Web: *pure CSS variables* dan *immutable TypeScript definitions* (`as const`) yang menjamin type safety penuh tanpa *string literals loose matching*.

---

## SEKSI 09 — STUDI KASUS NYATA

### Enterprise Scenario: FinSecure Digital Banking
* **Konteks:** Perusahaan fintech multi-aplikasi (Web App, Android, iOS) memiliki 45 desainer produk dan 120 engineer frontend yang terbagi dalam 12 *squad domain*.
* **Masalah:**
  1. *Visual Drift:* Terdapat 4 variasi warna "Brand Blue" yang berbeda di aplikasi Web dan Mobile.
  2. *Accessibility Lawsuit Risk:* Desainer sering menggunakan kombinasi teks abu-abu terang pada tombol sekunder yang melanggar standar WCAG AA.
  3. *Sync Latency:* Handoff pembaruan tema Dark Mode memakan waktu 3 kuartal karena perubahan warna di Figma harus dikonversi manual ke XML, Swift, dan SCSS.
* **Solusi DesignOps:**
  1. Sentralisasi manajemen token ke Git repository tunggal yang sinkron dengan Figma Variables via Webhook.
  2. Pemasangan automated accessibility contract test di dalam GitHub Actions.
  3. Kompilasi otomatis multi-platform via Style-Dictionary dengan semantic versioning terpadu.

---

## SEKSI 10 — HANDS-ON PRODUCTION CODE

### 1. Style-Dictionary Enterprise Configuration Engine
File: `build-tokens.ts`

```typescript
import StyleDictionary from 'style-dictionary';
import type { TransformedToken, Config } from 'style-dictionary';

// Registrasi Transform Custom: Dimensi px ke rem
StyleDictionary.registerTransform({
  name: 'size/pxToRem',
  type: 'value',
  matcher: (token: TransformedToken) => token.$type === 'dimension' && token.value.endsWith('px'),
  transformer: (token: TransformedToken) => {
    const floatValue = parseFloat(token.value.replace('px', ''));
    if (isNaN(floatValue)) return token.value;
    return `${floatValue / 16}rem`;
  }
});

// Registrasi Formatter Custom: TypeScript System
StyleDictionary.registerFormat({
  name: 'typescript/es6-typed',
  formatter: ({ dictionary }) => {
    const entries = dictionary.allTokens.map((t) => `  '${t.name}': '${t.value}',`).join('\n');
    return `// Auto-generated by DesignOps Compiler. DO NOT EDIT DIRECTLY.\nexport const DesignSystemTokens = {\n${entries}\n} as const;\n\nexport type DesignSystemTokenKey = keyof typeof DesignSystemTokens;\n`;
  }
});

// Konfigurasi Multi-Platform Build Pipeline
const config: Config = {
  source: ['tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      transforms: ['attribute/cti', 'name/cti/kebab', 'size/pxToRem'],
      buildPath: 'dist/css/',
      files: [
        {
          destination: 'tokens.css',
          format: 'css/variables',
          options: {
            outputReferences: true
          }
        }
      ]
    },
    typescript: {
      transforms: ['name/cti/kebab'],
      buildPath: 'dist/ts/',
      files: [
        {
          destination: 'tokens.ts',
          format: 'typescript/es6-typed'
        }
      ]
    },
    android: {
      transformGroup: 'android',
      buildPath: 'dist/android/',
      files: [
        {
          destination: 'colors.xml',
          format: 'android/resources'
        }
      ]
    },
    ios: {
      transformGroup: 'ios-swift',
      buildPath: 'dist/ios/',
      files: [
        {
          destination: 'StyleDictionaryColor.swift',
          format: 'ios-swift/enum.swift'
        }
      ]
    }
  }
};

const sd = StyleDictionary.extend(config);
sd.buildAllPlatforms();
console.log('✔ DesignOps Pipeline successfully built for Web, Android, and iOS.');
```

### 2. CI/CD GitHub Actions Contract Testing Workflow
File: `.github/workflows/designops-pipeline.yml`

```yaml
name: DesignOps Tokens Ingestion Pipeline

on:
  push:
    branches: [main]
    paths:
      - 'tokens/**'
  repository_dispatch:
    types: [figma-tokens-updated]

jobs:
  validate-and-publish:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Setup Node.js Environment
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Execute Contract Testing & Accessibility Audits
        run: npx ts-node scripts/lint-tokens.ts

      - name: Compile Cross-Platform Design Assets
        run: npx ts-node build-tokens.ts

      - name: Run Snapshot & Visual Regression Tests
        run: npm test

      - name: Automated Semantic Release & Package Deployment
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          NPM_TOKEN: ${{ secrets.NPM_AUTH_TOKEN }}
        run: npx semantic-release
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Parameter | Manual Handoff (Figma Inspect) | Monorepo Shared Constants | Automated DesignOps Pipeline (DTCG + Style Dictionary) |
| :--- | :--- | :--- | :--- |
| **Integrasi Multi-Platform** | Sangat Buruk (Manual re-typing) | Sedang (Hanya mencakup TypeScript) | Unggul (Native Web, iOS, Android serentak) |
| **Siklus Update Design** | Hari hingga Minggu | 2–3 Hari | Menit (< 30 Menit via automated PR) |
| **Beban Infrastruktur** | Nol (Mengandalkan disiplin manusia) | Rendah (Hanya Node.js package) | Tinggi (Setup CI/CD, Parser, Transpiler, Repo Sync) |
| **Akurasi & Konsistensi** | Rendah (Rentan Human Error) | Tinggi untuk Web, Rentan Drift di Mobile | Sangat Tinggi (Determinik 100%) |
| **Skalabilitas Organisasi** | Terhambat pada > 2 Squad | Efektif sampai 5 Squad | Mampu mengelola puluhan Tim Skala Enterprise |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Circular Aliasing pada Token Resolving:**
   * *Bahaya:* Token A merujuk Token B, dan Token B merujuk Token A (`color-primary: {color-brand}`, `color-brand: {color-primary}`). Compiler akan mengalami *infinite recursion* / stack overflow.
   * *Mitigasi:* Jalankan algoritma *Cycle Detection* menggunakan representasi Directed Graph berbasis algoritma Tarjan atau DFS sebelum pemrosesan token dilakukan.

2. **Perbedaan Color Space Antar Platform:**
   * *Bahaya:* Hex `#FF0000` di Figma (Display P3) menghasilkan visual yang berbeda saat di-render pada CSS (secara default sRGB) atau Swift (`UIColor(displayP3Red:...)`).
   * *Mitigasi:* Konversi eksplisit semua nilai ke color-space target spesifik menggunakan CSS Color Module Level 4 `color(display-p3 r g b)` dan penyesuaian transform group native mobile.

3. **Inkompatibilitas Font Rendering Engine:**
   * *Bahaya:* Ukuran `line-height` dalam pixel absolut menyebabkan pemotongan teks (*clipping*) pada Dynamic Type iOS dan Android Text Magnification jika pengguna mengubah preferensi aksesibilitas perangkat.
   * *Mitigasi:* Jangan pernah mengompilasi `line-height` menjadi nilai absolut pixel untuk mobile. Gunakan *unitless ratio* (misalnya: `1.5` bukan `24px`).

---

## SEKSI 13 — COMMON MISTAKES

### 1. Menghubungkan Figma Langsung ke Repositori Produksi Tanpa Staging
* *Kesalahan:* Menggunakan webhook langsung yang melakukan trigger rilis package production tanpa fase testing dan peninjauan Pull Request.
* *Solusi:* Webhook Figma hanya boleh membuka **Draft Pull Request** di repository tokens. Pipeline CI wajib memvalidasi linting dan unit testing sebelum disetujui oleh Design Lead dan Tech Lead.

### 2. Menggunakan Nilai Arbitrer Tanpa Semantic Indirection
* *Kesalahan:* Menggunakan token seperti `blue-500` langsung di styling komponen tombol (`background: var(--blue-500)`).
* *Solusi:* Buat layer semantik: `blue-500` $\rightarrow$ `color-interactive-primary` $\rightarrow$ `button-primary-bg`. Ketika terjadi rebranding, layer komponen tidak perlu disentuh.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

* **W3C Design Token Community Group (DTCG) Standard:** Selalu gunakan format metadata standar industri terbaru (`$value`, `$type`, `$description`).
* **Semantic Versioning Sembrono:** Perubahan nilai token yang sudah ada (misalnya: warna primer berubah dari biru ke hijau) adalah **Minor Version**. Penghapusan atau pengubahan nama kunci token adalah **Breaking Change (Major Version)**.
* **Component-Level Scoping:** Batasi cakupan token ke level terkecil. Komponen kompleks (misal: Data Grid Table) harus memiliki variabel lokal yang merujuk ke token semantik, bukan memodifikasi token semantik global.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI

1. **Tree-Shaking Output TypeScript:** Jangan mengekspor satu object raksasa jika aplikasi hanya menggunakan sebagian token. Gunakan modular export per kategori domain (misalnya: `colors.ts`, `spacing.ts`, `typography.ts`).
2. **CSS Variable Footprint:** Hindari menghasilkan puluhan ribu CSS variable jika tidak digunakan. Pisahkan token global primitif dari artefak CSS akhir; kompilasi **hanya** token semantik dan token komponen ke dalam `:root`.
3. **Build Caching:** Manfaatkan hash-based caching pada pipeline CI. Jika isi direktori `tokens/*.json` tidak mengalami perubahan hash MD5/SHA256, *skip* seluruh tahapan Style Dictionary build.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Sanitasi Token Value Injection:**
   * *Vektor Serangan:* Nilai string pada token Figma disisipi payload malicious CSS/JS (misalnya: `url('javascript:alert(1)')` atau unescaped quotes).
   * *Hardening:* Jalankan parser regex validasi ketat sebelum kompilasi:
     ```typescript
     const SAFE_CSS_VALUE_REGEX = /^([#a-zA-Z0-9_., ()%-]+)$/;
     if (!SAFE_CSS_VALUE_REGEX.test(token.$value)) {
       throw new Error(`Security Violation: Unsafe token value detected -> ${token.$value}`);
     }
     ```
2. **Autentikasi Figma API Token:** Jangan pernah menyimpan Figma Personal Access Token di file konfigurasi repositori publik. Selalu manfaatkan KMS (Key Management Service) seperti GitHub Encrypted Secrets atau AWS Secrets Manager.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Lacak performa dan keandalan sistem DesignOps menggunakan telemetri terukur:
1. **Design Token Coverage Rate:** Persentase styling UI dalam codebase yang menggunakan CSS variables token dibandingkan nilai *hardcoded hex/px* (dideteksi via custom ESLint rule atau Stylelint).
2. **Pipeline Duration Tracking:** Pantau durasi eksekusi GitHub Actions dari trigger webhook Figma hingga rilis package.
3. **Drift Telemetry Script:**

```typescript
// scripts/audit-token-drift.ts
import * as glob from 'glob';
import * as fs from 'fs';

const files = glob.sync('src/**/*.tsx');
let hardcodedValuesCount = 0;
const HEX_REGEX = /#([a-fA-F0-9]{6}|[a-fA-F0-9]{3})\b/g;

files.forEach((file) => {
  const content = fs.readFileSync(file, 'utf8');
  const matches = content.match(HEX_REGEX);
  if (matches) {
    hardcodedValuesCount += matches.length;
    console.warn(`[DRIFT DETECTED] ${file}: ${matches.length} hardcoded colors found.`);
  }
});

console.log(`Total Visual Drift Count: ${hardcodedValuesCount}`);
if (hardcodedValuesCount > 0) {
  process.exitCode = 1; // Gagalkan pipeline jika terdapat hardcoded styling
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Global Tokens:** Primitif absolut (`color-neutral-100: #F3F4F6`).
* **Semantic Tokens:** Maksud penggunaan kontekstual (`surface-background-subtle: {color-neutral-100}`).
* **Component Tokens:** Terikat pada isolasi komponen (`card-bg: {surface-background-subtle}`).
* **WCAG AA Compliance:** Rasio kontras teks reguler terhadap latar belakang minimal **4.5:1**; teks besar minimal **3.0:1**.
* **Alur Eksekusi:** `Figma Variables` $\rightarrow$ `Git Raw Tokens` $\rightarrow$ `Contract Linting (WCAG & Schema)` $\rightarrow$ `Style-Dictionary Build` $\rightarrow$ `Target Artifacts (Web/Android/iOS)`.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Mengapa arsitektur token 3-layer (Global $\rightarrow$ Semantic $\rightarrow$ Component) lebih diunggulkan dibanding langsung memetakan Global Tokens ke CSS Component?
* A. Karena Style-Dictionary hanya dapat membaca token dengan arsitektur 3-layer.
* B. Memberikan decoupling layer sehingga perubahan strategi tema (misal: Rebranding atau Dark Mode) tidak merusak isolasi implementasi komponen.
* C. Menghindari batasan memori parsing file JSON di Node.js.
* D. Mengurangi ukuran bundle CSS akhir hingga 90%.

### Soal 2
Perhatikan potongan skema W3C DTCG berikut:
```json
{
  "interactive": {
    "primary": {
      "$value": "{color.blue.600}",
      "$type": "color"
    }
  }
}
```
Proses apa yang harus dilakukan compiler untuk mengubah `{color.blue.600}` menjadi kode warna hexadecimal absolut?
* A. Lexical Linting
* B. Token Deserialization
* C. Alias Resolution via Topological Traversal
* D. Gamma Space Expansion

### Soal 3
Dalam pengujian aksesibilitas otomatis, mengapa pengujian rasio kontras warna harus dilakukan pada level Semantic Tokens daripada Component Tokens?
* A. Semantic tokens lebih cepat di-parsing oleh runtime compiler.
* B. Menghentikan kegagalan sedini mungkin (*fail-fast*) pada layer abstraksi makna sebelum komponen mengonsumsi nilai yang tidak patuh secara visual.
* C. Component tokens tidak memiliki nilai hexa.
* D. Standard W3C melarang pengujian aksesibilitas pada level komponen.

### Soal 4
Ketika tim engineering memperbarui Design Token repository dan menghapus semantic token `color-action-secondary`, klasifikasi *Semantic Versioning* manakah yang wajib diterapkan pada rilis package tersebut?
* A. Patch Version (0.0.X)
* B. Minor Version (0.X.0)
* C. Major Version (X.0.0)
* D. Alpha Pre-release

### Soal 5
Apa risiko arsitektural utama jika file artefak CSS Custom Properties hasil generate Style-Dictionary menyertakan seluruh variasi Global Core Tokens ke dalam selector `:root` di aplikasi web skala besar?
* A. Menimbulkan circular reference pada browser engine.
* B. Menghasilkan *DOM size bloat* dan pemborosan memori style engine browser akibat inisialisasi ribuan variable yang tidak pernah direferensikan secara langsung di stylesheet komponen.
* C. Memblokir rendering thread akibat evaluasi kalkulasi JavaScript secara sinkron.
* D. Merusak dukungan browser lawas terhadap flexbox.

---

### Kunci Jawaban & Pembahasan Evaluasi
1. **B** — Layer decoupling memungkinkan perubahan nilai visual mendasar (rebranding, high-contrast mode, dark theme) terjadi secara deklaratif pada semantic layer tanpa perlu refactoring ratusan styling komponen frontend.
2. **C** — Penelusuran *Topological Sort* menyelesaikan referensi silang secara deterministik dan memastikan tidak ada siklus (*circular reference*).
3. **B** — Pendekatan *fail-fast* pada layer semantik mencegah polusi defek visual menyebar ke puluhan varian komponen yang bergantung pada peran warna tersebut.
4. **C** — Menghapus token yang sudah ada adalah *breaking change* bagi aplikasi klien yang mengonsumsinya, sehingga mewajibkan kenaikan *Major Version*.
5. **B** — Menginjeksi ribuan variabel primitif yang tidak terpakai ke `:root` membebani memori computed styles browser engine tanpa memberikan nilai fungsional.

---

## SEKSI 20 — TANTANGAN MANDIRI & PROYEK PRAKTIKUM

### Deskripsi Proyek: "Multi-Platform Headless DesignOps Engine"
Bangunlah sebuah pipeline DesignOps mandiri dengan spesifikasi teknis berikut:

1. **Spesifikasi Input Data:**
   * Buat file `tokens/design-tokens.json` dengan hierarki 3-tier: Global (`color`, `spacing`), Semantic (`feedback`, `background`), dan Component (`alert-box`, `badge`).
2. **Mesin Validasi & Testing:**
   * Tulis modul TypeScript `scripts/verify-tokens.ts` yang:
     * Memvalidasi bahwa seluruh semantic token jenis teks memenuhi kontras WCAG 2.1 AA ($\ge 4.5:1$) terhadap pasangannya.
     * Mendeteksi dan memblokir adanya siklus circular aliasing.
3. **Custom Transformation Style-Dictionary:**
   * Konfigurasi transformasi token dimensi: jika platform Web ubah `px` ke `rem`, jika Android ubah `px` ke `dp`/`sp`, dan jika iOS ubah ke *points* (`CGFloat`).
4. **Output Deployment:**
   * Hasilkan 3 artefak build ke direktori `dist/`:
     * `dist/web/tokens.css` (Hanya berisi semantic & component tokens).
     * `dist/web/tokens.d.ts` (TypeScript types map lengkap).
     * `dist/android/values/colors.xml` (Format resources Android terstruktur).
5. **Kriteria Kelulusan Pipeline:**
   * Eksekusi `npm run build:tokens` harus gagal jika terdapat pelanggaran kontras WCAG atau skema yang invalid, dan berhasil menghasilkan ketiga artefak secara lengkap dan valid jika data token benar.