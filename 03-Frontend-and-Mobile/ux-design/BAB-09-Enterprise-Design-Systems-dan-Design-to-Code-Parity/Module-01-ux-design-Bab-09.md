# Bab 09 Module 01: Enterprise Design Systems & Design-to-Code Parity

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** 03-Frontend-and-Mobile
* **Jalur Pembelajaran:** UX Design & Design Engineering Core
* **Modul:** Bab 09 Module 01
* **Topik:** Enterprise Design Systems & Design-to-Code Parity
* **Tingkat Kompleksitas:** Advanced / Staff-Level
* **Prasyarat Pengetahuan:** 
  * Arsitektur CSS Modern (CSS Variables, CSS Modules, Tailwind, atau Styled Components).
  * Pemrograman Komponen TypeScript/React tingkat lanjut.
  * Pemahaman mendalam terkait Figma (Auto-layout, Component Properties, Variables, Styles).
  * Konsep dasar REST APIs, GitOps, dan automasi CI/CD workflows (GitHub Actions).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Membangun Arsitektur Single Source of Truth (SSOT):** Mengeliminasi deviasi UI antara Figma dan codebase production menggunakan token berbasis Design Tokens Format Module (DTCG) W3C.
2. **Merancang Engine Transformasi Token Multi-Platform:** Mengembangkan pipeline Style Dictionary untuk mengekstraksi raw token JSON menjadi artifact production (CSS custom properties, TypeScript const objects, iOS Swift constants, dan Android Jetpack Compose styles).
3. **Mengotomatisasi Sinkronisasi Design-to-Code Menggunakan CI/CD:** Mengimplementasikan webhook Figma API terotomasi yang men-trigger pull request GitHub secara headless tanpa intervensi manual designer atau engineer.
4. **Menerapkan Kontrak Desain Statis (Static Contract Enforcement):** Menggunakan Abstract Syntax Tree (AST) analysis dan linting custom untuk memastikan engineer tidak pernah menggunakan *arbitrary/magic values* di luar token yang didefinisikan.
5. **Menguji dan Mengukur Desain-to-Code Parity:** Mengonfigurasi automated visual regression testing (Playwright + Storybook) dan token-coverage telemetri untuk memvalidasi delta fidelity 0% antara artboard desainer dan viewport runtime.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: The Distributed Compiler Parity Model
Dalam enterprise engineering, sebuah Design System bukanlah sekadar "komponen UI library" atau "Figma UI Kit". Design System adalah sebuah **Compiler Terdistribusi**.

```
[Intent Desain (Figma Variables)] 
       │ (Representasi Simbolik / Token AST)
       ▼
[Token Engine Intermediate Representation (DTCG JSON)]
  ├──► Backend Compile 1: CSS Variables & Tailwind Plugin
  ├──► Backend Compile 2: TypeScript Types & Const Definitions
  ├──► Backend Compile 3: Android Jetpack Compose / iOS Swift
  └──► Backend Compile 4: Figma REST Sync Back (Metadata)
```

Desainer memanipulasi *source code visual* di dalam Figma. Frontend engineer mengonsumsi *compiled output visual* di dalam code repository. Keduanya berkomunikasi bukan melalui screenshot, redlining, atau inspeksi manual, melainkan melalui **Symbolic Representation (Tokens)** dan **Interface Contracts (Component Props Schema)**.

### Mindset Shift
* **Dari "Slicing UI":** Mengonversi gambar/vektor menjadi HTML/CSS secara manual berdasarkan spek visual statis.
* **Menuju "Contract-Driven Implementation":** Mendesain sistem representasi data di mana perubahan satu nilai token warna atau spasi di Figma secara otomatis terkompilasi, teruji oleh visual regression pipeline, dan mergeable via pull request ke master codebase tanpa penulisan ulang manual.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah siklus hidup pipeline Design-to-Code enterprise end-to-end yang menjamin parity 100%:

```
+---------------------------------------------------------------------------------------------------+
| FIGMA ENTERPRISE WORKSPACE                                                                        |
|  [Design Tokens / Variables] ---> [Variables Plugin / Enterprise REST API]                         |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  | Trigger Webhook on Variable Publish
                                                  v
+---------------------------------------------------------------------------------------------------+
| CI/CD PIPELINE (GITHUB ACTIONS)                                                                   |
|                                                                                                   |
|  +-------------------------------------+      +------------------------------------------------+  |
|  | STEP 1: Ingest & Normalization      |      | STEP 2: Multi-Platform Compilation             |  |
|  | - Fetch via Figma REST API API       | ---> | - Run Style Dictionary Core Engine             |  |
|  | - Transform to W3C DTCG Format      |      | - Build CSS/SCSS Custom Properties             |  |
|  | - Validate against JSON Schema      |      | - Build TypeScript Strict Interfaces & Types   |  |
|  +-------------------------------------+      +------------------------------------------------+  |
|                                                                       |                           |
|                                                                       v                           |
|  +-------------------------------------+      +------------------------------------------------+  |
|  | STEP 4: Automated Testing & Gating  |      | STEP 3: Artifact Generation & Packaging        |  |
|  | - Run Playwright Visual Regression  | <--- | - Bundle @enterprise/design-tokens             |  |
|  | - Run Token Parity Coverage Check   |      | - Update Storybook Documentation               |  |
|  | - Enforce <0.01% Delta Drift        |      | - Generate PR to Monorepo via Octokit          |  |
|  +-------------------------------------+      +------------------------------------------------+  |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
| PRODUCTION CONSUMPTION LAYER (WEB, MOBILE, DOCS)                                                  |
|                                                                                                   |
|   +-----------------------+   +------------------------+   +----------------------------------+   |
|   | Next.js / React Apps  |   | iOS & Android Natives  |   | Living Documentation Site        |   |
|   | (Zero Magic Numbers)  |   | (Jetpack/Swift Tokens) |   | (Zero Manual Updates)            |   |
|   +-----------------------+   +------------------------+   +----------------------------------+   |
+---------------------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Token Anatomy (W3C DTCG Compliance)
Token harus mengadopsi struktur W3C Design Tokens Community Group untuk mencegah fragmentasi sintaks.

* **Namespace / Group:** Menentukan domain konteks (misal: `color`, `spacing`, `typography`).
* **Modifier / Scale:** Skala sistematis (misal: `100`, `200` atau `sm`, `md`, `lg`).
* **Value `$value`:** Nilai representasi primitif (misal: `#0F172A`, `16px`).
* **Type `$type`:** Metadata tipe data untuk parser downstream (misal: `color`, `dimension`, `duration`).
* **Description `$description`:** Dokumentasi kontekstual yang diekstraksi ke IDE hover docs.

### 2. The Three-Tier Token Architecture
Dalam skala enterprise, tidak boleh memetakan nilai hex langsung ke komponen. Token distrukturkan dalam tiga tier:

```
[Tier 1: Global / Reference Tokens]
  └── system.palette.blue.600: #2563EB
          │
          ▼  (Aliasing)
[Tier 2: Semantic / System Tokens]
  └── semantic.color.action.primary.default: {system.palette.blue.600}
          │
          ▼  (Aliasing)
[Tier 3: Component-Specific Tokens]
  └── component.button.primary.bg.idle: {semantic.color.action.primary.default}
```

* **Global (Reference):** Menyimpan nilai mentah absolut. Tidak memiliki makna fungsional.
* **Semantic (System):** Memberikan konteks intent fungsional (misal: *background*, *surface*, *interactive*, *destructive*). Menjadi basis dari Theming (Dark Mode, High Contrast).
* **Component-Specific:** Membatasi paparan token hanya pada scope implementasi komponen tertentu guna mencegah efek samping global yang tidak disengaja saat pengubahan komponen individual.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Token Transform Engine: Teori Kompilasi Berbasis Visitor Pattern
Style Dictionary dan pipeline modern memproses token menggunakan tahapan kompilasi:
1. **Lexical Analysis & Parsing:** Membaca tree JSON multi-file, mengresolusi syntax include/pointer references.
2. **Reference Resolution (AST Graph Traversal):** Jika token bernilai `{color.base.blue.500}`, parser menelusuri Dependency Graph menggunakan *Depth-First Search (DFS)* untuk mencari referensi absolut. Jika terdeteksi siklus (`A -> B -> A`), parser melempar Circular Reference Error.
3. **Value Transformation:** Mengonversi data sesuai target format platform:
   * Web: Mengonversi `16px` menjadi `1rem` (jika basis font 16px).
   * Web: Mengonversi HEX/RGB menjadi functional color models seperti `oklch(0.623 0.214 259.815)` untuk dynamic range yang presisi.
   * iOS: Mengonversi format hex ke `UIColor(red:green:blue:alpha:)`.
   * Android: Mengonversi ke format XML Hex `#AARRGGBB` atau Compose `Color(0xFF...)`.
4. **Formatting & Code Generation:** Melewatkan resolved dictionary tree ke template engine (misal: Lodash templates, Handlebars, atau native TS string templates) untuk menghasilkan valid target files.

### Design-to-Code Drift Metric (Delta Variance)
Tingkat deviasi parity ($D_p$) dihitung melalui rasio antara token yang digunakan secara valid ($T_v$) terhadap total token call sites ditambah magic value occurrences ($M_v$):

$$D_p = 1 - \left( \frac{T_v}{T_v + M_v} \right)$$

Jika codebase enterprise memiliki 450 pemanggilan warna berbasis token dan 50 pemanggilan warna manual (misal: `color: "#ef4444"` inline), maka drift metric adalah $1 - (450 / 500) = 0.10$ ($10\%$ deviasi). Sasaran pipeline parity enterprise adalah **$D_p = 0.00$**.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi engine konfigurasi **Style Dictionary v4** menggunakan TypeScript murni untuk mengompilasi W3C DTCG Token JSON menjadi CSS Custom Properties dan TypeScript Definitions.

### File 1: Input Tokens (`tokens/globals.json`)
```json
{
  "system": {
    "palette": {
      "brand": {
        "blue": {
          "500": {
            "$value": "#3B82F6",
            "$type": "color",
            "$description": "Primary brand color reference"
          }
        }
      }
    }
  },
  "semantic": {
    "color": {
      "background": {
        "interactive": {
          "primary": {
            "$value": "{system.palette.brand.blue.500}",
            "$type": "color",
            "$description": "Primary interactive action background"
          }
        }
      }
    }
  }
}
```

### File 2: Build Pipeline Engine (`build-tokens.ts`)
```typescript
import StyleDictionary from 'style-dictionary';
import type { Config, TransformedToken } from 'style-dictionary/types';

// Custom transform untuk mengubah format hex ke OKLCH bila diperlukan,
// atau sekadar normalisasi fallback.
StyleDictionary.registerTransform({
  name: 'color/css-variable-name',
  type: 'name',
  transform: (token: TransformedToken) => {
    // Mengubah semantic.color.background.interactive.primary -> sys-color-bg-interactive-primary
    return token.path.join('-').toLowerCase();
  }
});

const config: Config = {
  source: ['tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      transforms: ['color/css-variable-name'],
      buildPath: 'dist/css/',
      files: [
        {
          destination: 'variables.css',
          format: 'css/variables',
          options: {
            outputReferences: true, // Mempertahankan CSS var mapping: var(--system-...)
            selector: ':root'
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
};

async function runTokenBuild() {
  try {
    console.log('🚀 Memulai kompilasi Design Tokens...');
    const sd = new StyleDictionary(config);
    await sd.buildAllPlatforms();
    console.log('✅ Kompilasi Design Tokens Berhasil Selesai!');
  } catch (error) {
    console.error('❌ Gagal melakukan kompilasi Design Tokens:', error);
    process.exit(1);
  }
}

runTokenBuild();
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi arsitektural dari implementasi di atas:

1. **`tokens/globals.json: $value & $type`**: Mengikuti spesifikasi W3C DTCG. Tanda kurung kurawal `{system.palette.brand.blue.500}` mendeklarasikan *alias pointer*. Style Dictionary akan mem-parse pointer ini sebagai simpul ketergantungan (DAG node) yang harus di-resolve nilainya sebelum rendering.
2. **`StyleDictionary.registerTransform`**: Mendaftarkan custom transformer. Kita menetapkan `type: 'name'`, yang berarti mutasi hanya diaplikasikan pada kunci penamaan token, bukan nilainya.
3. **`token.path.join('-').toLowerCase()`**: Mengonversi hierarki nested object array menjadi string kebab-case yang valid untuk standar CSS Custom Property standard naming convention.
4. **`outputReferences: true`**: Konfigurasi kritikal. Alih-alih meratakan (flattening) CSS value menjadi hardcoded `#3B82F6` di variabel semantic, opsi ini memaksa output CSS menjadi:
   `--semantic-color-background-interactive-primary: var(--system-palette-brand-blue-500);`.
   Ini memungkinkan dynamic runtime theming yang sangat efisien di level browser engine cascade.
5. **`platforms.typescript`**: Mengompilasi token ke format ES Module dan TypeScript type declarations (`.d.ts`). Ini memberikan autocompletion instan di IDE engineer serta validasi compile-time ketat sehingga string typo akan langsung menggagalkan proses kompilasi monorepo.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Global FinTech Platform "OmniPay" (Scale-Up Migration)
* **Konteks:** OmniPay memiliki 140 frontend engineers yang terbagi di 12 feature squads, menggunakan monorepo (Turborepo), melayani Web (React), iOS, dan Android.
* **Problem Statement:**
  * Designer memperbarui token warna brand dan *border-radius* di Figma.
  * Squad Checkout lupa memperbarui secara manual di web, sementara Squad Card Management salah menyalin kode hex manual ke CSS modules mereka.
  * Audit QA menemukan terdapat 47 variasi warna biru yang berbeda di production (`#0066FF`, `#0065EE`, `#0067FA`, dll).
  * Design debt melumpuhkan rilis Dark Mode karena tidak mungkin me-remap ribuan arbitrary CSS hex values.
* **Solusi Arsitektur:**
  * Membangun **Design Tokens Engine Service** yang terhubung langsung via Figma Webhook.
  * Ketika desainer menekan "Publish Library" di Figma, webhook mengalir ke backend internal yang mengekstrak token via Figma REST API `/v1/files/:file_key/variables/local`.
  * GitHub Action secara otomatis membuat Pull Request ke monorepo, menjalankan Playwright Visual Regression Test, dan memblokir merge jika terjadi UI regression di luar threshold.
  * ESLint rule khusus diaktifkan untuk melempar compiler error jika engineer mengetik arbitrary color hex atau spacing pixel secara manual di file JSX/TSX.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistematis pipeline ingestion Figma API ke DTCG Token Translator yang siap pakai untuk level enterprise production.

### File 1: Ingestion Pipeline Script (`scripts/figma-token-extractor.ts`)
```typescript
import fs from 'node:fs/promises';
import path from 'node:path';

interface FigmaVariable {
  id: string;
  name: string;
  key: string;
  variableCollectionId: string;
  resolvedType: 'COLOR' | 'FLOAT' | 'STRING';
  valuesByMode: Record<string, FigmaVariableValue>;
}

type FigmaVariableValue = 
  | boolean 
  | string 
  | number 
  | { r: number; g: number; b: number; a: number } 
  | { type: 'VARIABLE_ALIAS'; id: string };

interface FigmaVariablesApiResponse {
  status: number;
  error: boolean;
  meta: {
    variables: Record<string, FigmaVariable>;
    variableCollections: Record<string, { name: string; defaultModeId: string }>;
  };
}

// Utilitas mengubah RGBA 0-1 Figma menjadi standard CSS Hex/RGBA
function parseFigmaColor(color: { r: number; g: number; b: number; a: number }): string {
  const r = Math.round(color.r * 255);
  const g = Math.round(color.g * 255);
  const b = Math.round(color.b * 255);
  const a = Math.round(color.a * 100) / 100;
  
  if (a === 1) {
    return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1).toUpperCase()}`;
  }
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

export async function fetchFigmaTokens(fileKey: string, personalAccessToken: string) {
  console.log(`📡 Menghubungi Figma API untuk file: ${fileKey}...`);
  
  const response = await fetch(`https://api.figma.com/v1/files/${fileKey}/variables/local`, {
    headers: {
      'X-Figma-Token': personalAccessToken,
    },
  });

  if (!response.ok) {
    throw new Error(`Figma API Error: ${response.status} ${response.statusText}`);
  }

  const data: FigmaVariablesApiResponse = await response.json();
  const variables = data.meta.variables;
  const collections = data.meta.variableCollections;

  const dtcgOutput: Record<string, any> = {};

  for (const [varId, variable] of Object.entries(variables)) {
    const collection = collections[variable.variableCollectionId];
    const defaultModeId = collection.defaultModeId;
    const value = variable.valuesByMode[defaultModeId];

    // Menangani segmentasi path token berdasarkan slash naming di Figma: "color/action/primary"
    const pathSegments = variable.name.split('/');
    let currentScope = dtcgOutput;

    for (let i = 0; i < pathSegments.length; i++) {
      const segment = pathSegments[i].trim();
      if (i === pathSegments.length - 1) {
        // Daun terminal (Token Node)
        let resolvedValue: any;

        if (typeof value === 'object' && value !== null) {
          if ('type' in value && value.type === 'VARIABLE_ALIAS') {
            // Mapping alias balik ke nama variabel dependensi
            const targetVar = variables[value.id];
            resolvedValue = `{${targetVar.name.replace(/\//g, '.')}}`;
          } else if ('r' in value) {
            resolvedValue = parseFigmaColor(value);
          }
        } else {
          resolvedValue = value;
        }

        currentScope[segment] = {
          $value: resolvedValue,
          $type: variable.resolvedType.toLowerCase() === 'float' ? 'dimension' : variable.resolvedType.toLowerCase(),
          $description: `Extracted automatically from Figma [${collection.name}]`
        };
      } else {
        // Cabang objek (Namespace Node)
        currentScope[segment] = currentScope[segment] || {};
        currentScope = currentScope[segment];
      }
    }
  }

  const outputPath = path.resolve(process.cwd(), 'tokens/extracted-tokens.json');
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, JSON.stringify(dtcgOutput, null, 2), 'utf-8');
  console.log(`🎉 Token berhasil diekstraksi ke: ${outputPath}`);
}
```

### File 2: Custom Static Linter AST Rule (ESLint Plugin Concept)
Memaksa Parity Contract: Melarang penggunaan Hex Code di CSS-in-JS atau JSX.

```typescript
// plugins/eslint-plugin-design-tokens/no-arbitrary-colors.ts
import { Rule } from 'eslint';

const HEX_COLOR_REGEX = /^#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/i;

const rule: Rule.RuleModule = {
  meta: {
    type: 'problem',
    docs: {
      description: 'Melarang penggunaan arbitrary hex color values demi menjaga parity token design system',
      category: 'Parity Enforcement',
      recommended: true,
    },
    schema: [], // Tidak butuh opsi konfigurasi
    messages: {
      avoidHex: 'DILARANG menggunakan arbitrary color "{{ value }}". Gunakan token var(--sys-color-*) atau semantic theme token terkait.',
    },
  },
  create(context) {
    return {
      Literal(node) {
        if (typeof node.value === 'string' && HEX_COLOR_REGEX.test(node.value)) {
          context.report({
            node,
            messageId: 'avoidHex',
            data: {
              value: node.value,
            },
          });
        }
      },
      TemplateElement(node) {
        const rawText = node.value.raw;
        const matches = rawText.match(HEX_COLOR_REGEX);
        if (matches) {
          context.report({
            node,
            messageId: 'avoidHex',
            data: {
              value: matches[0],
            },
          });
        }
      }
    };
  },
};

export default rule;
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektur | Approach A: Manual Redlining & Inspect | Approach B: Direct Figma-to-Code Codegen Plugins | Approach C: GitOps-Driven Token Architecture (Modul Ini) |
| :--- | :--- | :--- | :--- |
| **Kecepatan Deployment Perubahan** | Lambat (Hari hingga Minggu) | Cepat (Hitungan Menit) | Menengah-Cepat (Sesuai Pipeline CI/CD, 5-15 Menit) |
| **Maintainability Skala Enterprise** | Sangat Buruk (High Entropy) | Buruk (Menghasilkan Spaghetti Code / Dead Props) | Sangat Tinggi (Struktur Terstandarisasi) |
| **Control & Code Quality Gate** | Tinggi (Review Engineer Manual) | Nol (Langsung overwrite tanpa review arsitektur) | Maksimal (Branch PR, Automated Tests, Strict Linting) |
| **Kompatibilitas Multi-platform** | Bergantung pada Engineer per platform | Web-Centric (Umumnya mengabaikan Mobile) | Universal (Style Dictionary compile ke CSS, Swift, Compose) |
| **Human Error Margin** | Sangat Tinggi (>30% inkonsistensi) | Menengah (Engine visual parsing error) | Mendekati Nol (Strict Contract Schemas & AST Linter) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Cycle Dependency Loops dalam Variable Aliasing:**
   * *Problem:* Designer di Figma meng-alias `color-bg-primary` ke `color-fill-base`, sementara desainer lain secara tidak sengaja meng-alias `color-fill-base` ke `color-bg-primary`.
   * *Mitigasi:* Compiler token wajib menyertakan siklus deteksi graf (Topological Sort / Tarjan’s Algorithm) saat resolve reference dan langsung memutus pipeline dengan exit code 1 sebelum men-generate artifact invalid.
2. **Precision Loss pada Nilai Alpha / Decimal Spacing:**
   * *Problem:* Figma menyimpan nilai float RGBA dalam rentang $0.0 - 1.0$ (misal: $0.1234567$). Pembulatan CSS ceroboh menghasilkan rendering banding pada display Retina.
   * *Mitigasi:* Tetapkan presisi deterministik minimum 4 desimal pada math rounding di transformer script.
3. **Ghost Tokens (Orphan Tokens):**
   * *Problem:* Variabel di Figma dihapus, namun token di repo masih ada karena engine hanya melakukan *append*, bukan *reconcile/prune*.
   * *Mitigasi:* Ingestion pipeline harus membersihkan direktori target (`rm -rf tokens/dist/*`) sebelum proses kompilasi fresh dari AST payload Figma.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

* **Mistake 1: Hardcoding Semantic Tokens ke Level Primitif Komponen.**
  * *Contoh Buruk:* `<Button style={{ backgroundColor: tokens.global.palette.blue[500] }} />`
  * *Solusi Parity:* Selalu gunakan Tier 2/3. `<Button style={{ backgroundColor: tokens.semantic.action.background.primary }} />`. Mengakses palette global secara langsung menghancurkan kapabilitas theming dark-mode otomatis.
* **Mistake 2: Memperlakukan Token sebagai Styling Murni (Bukan Design Contract).**
  * *Contoh Buruk:* Desainer mengubah spasi tanpa menyadari bahwa sistem *bounding box* tabel dependensi di production menggunakan fixed-size assumptions.
  * *Solusi Parity:* Validasi token perubahan melalui visual regression suites (Playwright) di level CI/CD sebelum PR di-merge otomatis.
* **Mistake 3: Desinkronisasi Naming Convention (Kebab-case vs CamelCase vs Snake_case).**
  * *Solusi Parity:* Standarisasikan normalizer tunggal di transformer. Apapun naming format yang dibuat di Figma (`Brand/Primary Color`), engine harus memetakannya secara konsisten sesuai platform conventions: `brand-primary-color` (CSS) dan `brandPrimaryColor` (TypeScript).

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan W3C DTCG Format:** Jangan menciptakan schema JSON sendiri. Spesifikasi W3C Design Tokens Community Group adalah masa depan interoperabilitas toolings UI/UX global.
2. **Atomic Commits melalui Bot User:** Ekstraksi otomatis dari Figma harus di-commit oleh identity bot khusus (misal: `@omnipre-ds-bot`) dengan semantic commit message: `chore(tokens): sync tokens with figma library v1.4.2 [skip ci]`.
3. **Isolasi Token Package:** Tempatkan token dalam package tersendiri di monorepo (misal: `@enterprise/tokens`) yang tidak memiliki dependensi runtime framework UI apapun (agnostik terhadap React, Vue, maupun Svelte).
4. **Strict Typing via Const Assertions:**
   ```typescript
   export const Tokens = { ... } as const;
   export type DesignTokenPath = keyof typeof Tokens;
   ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

1. **Eliminasi Runtime Object Overhead via Pure CSS Custom Properties:**
   * Hindari CSS-in-JS libraries yang mem-parse JS Object besar di setiap re-render React (runtime footprint: 12-18KB parsed JS).
   * Gunakan pendekatan *Zero-Runtime Token Ingestion*: Compile token langsung ke native CSS variables. Browser me-resolve native CSS variables secara internal pada level engine C++, memotong rendering cost JavaScript menjadi 0ms.
2. **Subsetting Token Distribution (Tree-Shaking Per Scope):**
   * Jangan mengirimkan seluruh token palette enterprise (yang bisa mencapai ratusan kilobyte) ke client runtime aplikasi mikro.
   * Pisahkan file bundle: `global.css` (hanya reference variabel aktif), `components.css` (hanya component mapped classes), dan gunakan CSS modern `@layer tokens, components, utilities;` untuk mencegah specificity war.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Sanitasi Figma API Token Extraction:**
   * Figma API Token (`personalAccessToken`) **TIDAK BOLEH** disimpan di client-side repo. Simpan eksklusif di GitHub Secrets atau HashiCorp Vault.
2. **Mitigasi Code Injection via Token Values:**
   * Hati-hati terhadap input teks desainer di Figma. Jika desainer mengisi variabel string dengan: `red; } body { display: none !important; } /*`, kompilasi mentah ke CSS dapat mengakibatkan CSS Injection (XSS Vector).
   * **Hardening Implementation:** Jalankan input sanitizer menggunakan regex allow-list sebelum mengizinkan token dicetak ke file `.css` atau `.ts`.
   ```typescript
   function sanitizeTokenValue(value: string): string {
     // Hanya izinkan karakter alfanumerik, spasi, tanda kurung dasar, dan format warna standar
     const SAFE_VALUE_REGEX = /^[a-zA-Z0-9\s#(),.\-_%]+$/;
     if (!SAFE_VALUE_REGEX.test(value)) {
       throw new SecurityError(`Unsafe token value detected: ${value}`);
     }
     return value;
   }
   ```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### Continuous Parity Auditing (CI Telemetry Script)
Eksekusi script ini pada branch pull-request untuk memantau nilai metric drift parity secara periodik:

```typescript
// scripts/parity-telemetry.ts
import glob from 'fast-glob';
import fs from 'node:fs/promises';

async function calculateParityDrift() {
  const tsxFiles = await glob('src/**/*.{tsx,jsx,css}');
  let magicValueOccurrences = 0;
  let tokenOccurrences = 0;

  const HEX_REGEX = /#([0-9a-f]{3,8})/gi;
  const TOKEN_REGEX = /var\(--sys-[a-z0-9\-]+\)/gi;

  for (const filePath of tsxFiles) {
    const content = await fs.readFile(filePath, 'utf-8');
    const hexMatches = content.match(HEX_REGEX);
    const tokenMatches = content.match(TOKEN_REGEX);

    if (hexMatches) magicValueOccurrences += hexMatches.length;
    if (tokenMatches) tokenOccurrences += tokenMatches.length;
  }

  const total = magicValueOccurrences + tokenOccurrences;
  const parityMetric = total === 0 ? 1 : tokenOccurrences / total;
  const drift = (1 - parityMetric) * 100;

  console.log(`📊 Total Token Usage: ${tokenOccurrences}`);
  console.log(`⚠️  Total Magic Hex Values: ${magicValueOccurrences}`);
  console.log(`🎯 Parity Drift Metric: ${drift.toFixed(2)}%`);

  if (drift > 5.0) { // Toleransi maksimal drift 5%
    console.error(`❌ GAGAL: Parity Drift melebihi ambang batas aman (> 5.0%).`);
    process.exit(1);
  }
}

calculateParityDrift();
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **DTCG:** Design Tokens Community Group. Standar formal W3C untuk pertukaran struktur token berbasis JSON schema (`$value`, `$type`, `$description`).
* **3-Tier Structure:** Primitive/Global -> Semantic/System -> Component-scoped. Jangan pernah melompati lapisan semantic.
* **Zero-Magic Policy:** Tidak boleh ada hardcoded raw value (Hex, Px) di leaf component JSX. Semua styling wajib merujuk pada token.
* **Single Source of Truth:** Figma Variables bertindak sebagai *visual source*, Style Dictionary bertindak sebagai *compiler*, Repository monorepo bertindak sebagai *target deployment*.
* **Validation Gating:** Desain-to-Code Parity dijamin oleh 3 instrumen:
  1. AST Linter (Blokir penulisan hex manual).
  2. Telemetry Parity Check (Ukur metrik drift di CI).
  3. Visual Regression Test (Ukur render parity visual via Playwright snapshot).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah jawaban yang paling tepat serta analisis implikasinya:

1. **Mengapa menyimpan token warna langsung sebagai raw value (misal: `#3B82F6`) langsung pada komponen Button (`component.button.bg: "#3B82F6"`) dianggap anti-pattern pada enterprise design system?**
   * A. Karena CSS tidak mendukung nilai hex di dalam variabel komponen.
   * B. Karena menghilangkan lapisan semantic yang memblokir fungsionalitas dynamic theming (Dark Mode) dan multibranding runtime.
   * C. Karena Style Dictionary menolak kompilasi token jika tidak diarahkan ke palette global.
   * D. Karena file JSON akan memiliki ukuran memori yang terlalu besar di browser.
   * *Jawaban yang benar: B.*

2. **Peran utama dari konfigurasi `outputReferences: true` pada Style Dictionary web-platform target adalah...**
   * A. Mengonversi semua format warna ke OKLCH secara paksa.
   * B. Mengizinkan variabel CSS untuk mempertahankan sintaks relasional native `var(--...)` daripada melakukan resolve absolut menjadi flat values.
   * C. Mengompresi seluruh file tokens.css menjadi format binary.
   * D. Menginstruksikan Git untuk me-resolve merge conflicts secara otomatis.
   * *Jawaban yang benar: B.*

3. **Manakah dari metrik berikut yang menunjukkan tingkat Design-to-Code parity terbaik pada suatu frontend codebase?**
   * A. Drift Metric = 100%
   * B. Drift Metric = 0.50
   * C. Drift Metric = 0.00
   * D. Drift Metric = -1.00
   * *Jawaban yang benar: C.*

4. **Kapan cycle reference resolver pada token ingestion engine harus memicu throw exception dan menggagalkan pipeline CI?**
   * A. Saat file `tokens.json` memiliki lebih