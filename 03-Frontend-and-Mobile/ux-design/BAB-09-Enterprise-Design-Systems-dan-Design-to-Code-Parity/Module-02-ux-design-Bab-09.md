# BAB 09: Enterprise Design Systems & Design-to-Code Parity
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur *Design Token Engine* skala *enterprise* menggunakan format standar W3C DTCG (Design Tokens Community Group) dan Style Dictionary v4+.
- Membangun *automated token synchronization pipeline* dari Figma Variables/Tokens Studio ke multi-platform targets (React/Web, iOS Swift, Android Jetpack Compose) melalui CI/CD.
- Mengembangkan *Component Parity Engine* berbasis Abstract Syntax Tree (AST) untuk mendeteksi deviasi visual, varian, dan properti antara komponen Figma dan repositori kode.
- Mengelola arsitektur *multi-brand*, *multi-theme* (light/dark/high-contrast), dan *multi-platform* dengan penanganan isolasi spesifisitas CSS dan *runtime performance optimization*.
- Mengimplementasikan pengujian regresi visual otomatis dan validasi kontraktual desain-kode pada *pull request workflow*.

---

### 2. Prerequisite
Untuk memahami modul ini secara komprehensif, peserta wajib menguasai:
- **TypeScript Lanjutan**: Generic types, mapped types, conditional types, type-level programming, dan AST parsing (`@babel/parser`, `ts-morph`).
- **Modern CSS & Rendering Engine**: CSS Custom Properties, PostCSS, zero-runtime CSS (Vanilla Extract/Tailwind CSS), CSS cascade layers (`@layer`), dan spesifisitas rendering browser.
- **Figma Architecture**: Figma REST API v1, Plugin API, Webhooks, Figma Variables, dan Tokens Studio schema.
- **DevOps & Tooling**: GitHub Actions (reusable workflows), Node.js runtime, Monorepo tooling (Turborepo/Nx), dan NPM publishing lifecycles.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Taksonomi Token Berlapis (3-Tier Token Architecture)
Dalam sistem skala *enterprise*, token tidak didefinisikan secara langsung dari nilai primitif ke komponen. Diperlukan pemisahan *concern* 3-tingkat untuk memastikan *reusability* dan mendukung *multi-branding*:

```
[ Global / Core Tokens ] -> Primitive primitives (hex, px, ms)
          │
          ▼
[ Semantic / Alias Tokens ] -> Intention-driven contexts (surface-primary, text-danger)
          │
          ▼
[ Component-Scoped Tokens ] -> Encapsulated variables (button-primary-bg, modal-elevation)
```

1. **Global Tokens (Tier 1)**: Menyimpan nilai absolut tanpa konteks semantik. Contoh: `color.blue.500: #0066FF`, `spacing.4: 16px`.
2. **Semantic / Alias Tokens (Tier 2)**: Mengarahkan *global tokens* ke tujuan fungsionalitas UI. Layer ini merespons perubahan mode (Light/Dark) dan *Brand Theme*. Contoh: `color.background.interactive.default: {color.blue.500}`.
3. **Component Tokens (Tier 3)**: Mengikat token semantik ke implementasi komponen spesifik. Memberikan isolasi agar perubahan pada satu komponen tidak merusak komponen lain. Contoh: `button.primary.background.hover: {color.background.interactive.hover}`.

#### B. Pipeline Transformasi Token (DTCG ke Multi-Platform)
Komposisi pipeline memproses token dari format deklaratif W3C (JSON) menjadi *platform-specific artifacts*. Engine mengeksekusi siklus hidup parsing, resolving reference, transformasi nilai, dan formatting:

```
┌─────────────────┐       ┌────────────────────────┐       ┌──────────────────────┐
│  W3C DTCG JSON  │ ────> │ Resolve Token Tree     │ ────> │ Transform Lifecycle  │
│  Raw Token Sets │       │ (DAG Reference Solver) │       │ (Name, Value, Unit)  │
└─────────────────┘       └────────────────────────┘       └──────────────────────┘
                                                                       │
                                                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Formatter Pipeline                                                              │
├──────────────────────┬──────────────────────┬───────────────────────────────────┤
│ Web (CSS Variables/  │ Android (Jetpack     │ iOS (SwiftUI                      │
│ TypeScript Types)    │ Compose DesignSystem)│ Token Structs)                    │
└──────────────────────┴──────────────────────┴───────────────────────────────────┘
```

#### C. AST-Based Component Parity Engine
Parity Engine memvalidasi keselarasan (*drift verification*) antara spesifikasi komponen Figma dan implementasi kode melalui AST:
- **Figma Component Specification**: Diekstrak via Figma API menghasilkan representasi JSON berisi `name`, `componentPropertyDefinitions` (variant, boolean, text, instance-swap).
- **Code Component Specification**: Ditelusuri via TypeScript Compiler API (`ts-morph`) untuk membaca deklarasi `interface Props` atau variant schema (seperti `cva` - *class-variance-authority*).
- **Parity Assertion**: Algoritma rekursif membandingkan kedua model skema. Deviasi menghasilkan *parity violation report*.

---

### 4. Why & What

| Dimensi | Desain Konvensional (Non-Engineered) | Enterprise Design-to-Code Parity |
| :--- | :--- | :--- |
| **Source of Truth** | Terpecah antara file Figma dan repositori Git. | W3C DTCG Token Repository tunggal yang mengontrol Desain dan Kode. |
| **Sinkronisasi Perubahan** | Manual, rentan *human error*, koordinasi via *ticket/chat*. | Terotomatisasi end-to-end via Webhook, PR otomatis, dan CI validation. |
| **Skalabilitas Multi-Brand** | Duplikasi komponen secara masif per brand. | Satu *component core logic*, didorong oleh *dynamic semantic token mapping*. |
| **Deteksi Deviasi (Drift)** | Diketahui saat komplain user atau QA manual di staging. | Terdeteksi di CI Pipeline sebelum *code merge* via visual regression dan AST diff. |
| **Tipe Keamanan Token** | String mentah (`color: "#0066ff"` atau `className="bg-blue"`). | *Strictly typed* TypeScript definitions dengan autocomplete dan runtime verification. |

---

### 5. How (Workflow Detail)

1. **Authoring (Figma)**: Desainer memperbarui token atau komponen pada Figma Variables / Tokens Studio.
2. **Dispatch Event**: Plugin atau Figma Webhook menembakkan payload *event update* ke API Gateway orkestrator token.
3. **Extraction & Sanitization**: Ekstraktor mengubah model Figma Variables ke format standar W3C DTCG JSON specification (`$value`, `$type`, `$description`, `$extensions`).
4. **DAG Graph Resolution**: Engine memvalidasi tidak ada *circular references* (ketergantungan siklik) menggunakan Directed Acyclic Graph resolver.
5. **Compilation (Style Dictionary v4)**:
   - *Transforms*: Mengonversi nama (kebab-case, camelCase), nilai ukuran (px to rem), dan warna (hex/rgba to oklch/display-p3).
   - *Formatters*: Menghasilkan CSS custom properties bertingkat (`@layer tokens`), TypeScript constants dengan tipe literal `as const`, dan model Jetpack Compose / Swift.
6. **Parity Check (AST Parser)**: Validasi kesesuaian nama varian pada kode TSX terhadap Figma Component Set.
7. **Automated Distribution**:
   - Skrip membuat Pull Request otomatis ke repositori Design System.
   - Eksekusi Playwright Visual Regression Testing.
   - Publikasi paket NPM terversi semantic (`@enterprise-ds/tokens`).

---

### 6. Analogy & Diagram ASCII

#### Analogi Kompiler
Proses *Design-to-Code Parity* ekuivalen dengan pipeline kompilasi bahasa pemrograman:
- **Design Tokens (JSON)** = *Source Code* (kode sumber deklaratif tingkat tinggi).
- **Style Dictionary Engine** = *Compiler Frontend & Optimizer* (parsing, validasi referensi, inferensi tipe).
- **CSS / TypeScript / Kotlin / Swift** = *Target Machine Code* (biner yang dioptimalkan sesuai platform eksekusi).
- **AST Parity Check** = *Static Type Checking & Linter* (memverifikasi keselarasan struktur antarmuka sebelum dijalankan).

#### Enterprise Parity Architecture Diagram

```
+-------------------------------------------------------------------------------+
|                             DESIGN DOMAIN (FIGMA)                             |
|                                                                               |
|  +--------------------+   +---------------------+   +---------------------+   |
|  |  Global Variables  |-->|  Semantic Variables |-->| Component Variants  |   |
|  +--------------------+   +---------------------+   +---------------------+   |
+--------------------------------------┬----------------------------------------+
                                       │ Figma REST API / Webhooks
                                       ▼
+-------------------------------------------------------------------------------+
|                    ENTERPRISE TOKEN ORCHESTRATOR PIPELINE                     |
|                                                                               |
|  +-------------------------------------------------------------------------+  |
|  | Token Normalizer: Convert to W3C DTCG Spec                              |  |
|  +-------------------------------------------------------------------------+  |
|                                      │                                        |
|                                      ▼                                        |
|  +-------------------------------------------------------------------------+  |
|  | Directed Acyclic Graph (DAG) Dependency Resolver                        |  |
|  +-------------------------------------------------------------------------+  |
|                                      │                                        |
|                                      ▼                                        |
|  +-------------------------------------------------------------------------+  |
|  | Style Dictionary v4 Core Engine (Custom Transforms & Formatters)       |  |
|  +-------------------------------------------------------------------------+  |
+-------------------┬──────────────────────┬────────────────────┬---------------+
                    │                      │                    │
                    ▼                      ▼                    ▼
          +------------------+   +------------------+  +------------------+
          | Web Target       |   | Android Target   |  | iOS Target       |
          | - CSS (@layer)   |   | - Compose Color  |  | - SwiftUI Colors |
          | - TS Tokens Type |   | - Dimens.kt      |  | - Dynamic Assets |
          +------------------+   +------------------+  +------------------+
                    │
                    ▼
+-------------------------------------------------------------------------------+
|                     PARITY VERIFICATION CI/CD GATEWAY                         |
|                                                                               |
|   +--------------------------+               +----------------------------+   |
|   | ts-morph Code AST Parser |               | Figma Component Meta API   |   |
|   +-------------┬------------+               +--------------┬-------------+   |
|                 │                                           │                 |
|                 └───────────────────┬───────────────────────┘                 |
|                                     ▼                                         |
|                 +---------------------------------------+                     |
|                 | Parity Engine: Props & Variants Diff  |                     |
|                 +-------------------┬-------------------+                     |
|                                     │                                         |
|                   [ Pass ] ─────────┴───────── [ Fail ]                       |
|                      │                            │                           |
|                      ▼                            ▼                           |
|             Auto-Merge & Publish             Block CI & Open                  |
|             NPM Package Release              Parity Drift Issue               |
+-------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: W3C DTCG Token Specification
File: `tokens/primitives.json`
```json
{
  "color": {
    "blue": {
      "500": {
        "$value": "#0066FF",
        "$type": "color",
        "$description": "Core primary brand color"
      }
    }
  }
}
```
File: `tokens/semantic.json`
```json
{
  "surface": {
    "brand": {
      "default": {
        "$value": "{color.blue.500}",
        "$type": "color",
        "$description": "Default background for primary interactive surfaces"
      }
    }
  }
}
```

#### B. Practical Example: Advanced Token Transformer & Parity Checker

##### 1. Style Dictionary Engine Setup (v4+)
File: `scripts/build-tokens.ts`
```typescript
import StyleDictionary from 'style-dictionary';
import { FormatterArguments, TransformedToken } from 'style-dictionary/types';
import * as fs from 'fs';
import * as path from 'path';

// Custom Transform: Rem Conversion with Precision Control
StyleDictionary.registerTransform({
  name: 'size/pxToRem',
  type: 'value',
  filter: (token: TransformedToken) => token.$type === 'dimension' && String(token.$value).endsWith('px'),
  transform: (token: TransformedToken) => {
    const baseFontSize = 16;
    const floatVal = parseFloat(String(token.$value));
    if (floatVal === 0) return '0';
    return `${(floatVal / baseFontSize).toFixed(4).replace(/\.?0+$/, '')}rem`;
  }
});

// Custom Formatter: CSS Layers with Scoped Custom Properties
StyleDictionary.registerFormat({
  name: 'css/layered-variables',
  format: ({ dictionary, options }: FormatterArguments) => {
    const selector = options.selector || ':root';
    const layer = options.layer || 'tokens';
    const lines = dictionary.allTokens.map((token) => {
      const varName = `--${token.name}`;
      return `  ${varName}: ${token.$value};`;
    });

    return [
      `@layer ${layer} {`,
      `  ${selector} {`,
      ...lines,
      `  }`,
      `}`
    ].join('\n');
  }
});

// Custom Formatter: Fully Typed TypeScript Declarations
StyleDictionary.registerFormat({
  name: 'typescript/strict-types',
  format: ({ dictionary }: FormatterArguments) => {
    const tokenObj: Record<string, string> = {};
    dictionary.allTokens.forEach((token) => {
      tokenObj[token.name] = token.$value;
    });

    return [
      '// AUTO-GENERATED BY DESIGN TOKEN PIPELINE. DO NOT EDIT DIRECTLY.',
      `export const Tokens = ${JSON.stringify(tokenObj, null, 2)} as const;`,
      `export type DesignTokenName = keyof typeof Tokens;`,
      `export type DesignTokenValue<T extends DesignTokenName> = typeof Tokens[T];`
    ].join('\n');
  }
});

async function runCompiler() {
  const brands = ['alpha', 'beta'];
  
  for (const brand of brands) {
    const sd = new StyleDictionary({
      source: [
        'tokens/globals/**/*.json',
        `tokens/brands/${brand}/**/*.json`,
        'tokens/semantics/**/*.json'
      ],
      platforms: {
        css: {
          transformGroup: 'css',
          transforms: ['size/pxToRem'],
          buildPath: `dist/css/${brand}/`,
          prefix: 'ds',
          files: [
            {
              destination: 'tokens.css',
              format: 'css/layered-variables',
              options: {
                layer: 'design-system',
                selector: `[data-brand="${brand}"]`
              }
            }
          ]
        },
        typescript: {
          transformGroup: 'js',
          buildPath: `dist/ts/${brand}/`,
          prefix: 'ds',
          files: [
            {
              destination: 'tokens.ts',
              format: 'typescript/strict-types'
            }
          ]
        }
      }
    });

    await sd.buildAllPlatforms();
    console.log(`✓ Compiled artifacts for brand: ${brand}`);
  }
}

runCompiler().catch((err) => {
  console.error('Fatal compilation failure', err);
  process.exit(1);
});
```

##### 2. AST-Based Parity Engine Checker
File: `scripts/parity-assertion.ts`
```typescript
import { Project, Type, Symbol as TsSymbol } from 'ts-morph';
import * as fs from 'fs';
import * as path from 'path';

interface FigmaComponentPropertyMeta {
  type: 'VARIANT' | 'BOOLEAN' | 'TEXT' | 'INSTANCE_SWAP';
  variantOptions?: string[];
}

interface FigmaMetaPayload {
  name: string;
  properties: Record<string, FigmaComponentPropertyMeta>;
}

// Simulasi ekstraksi metadata dari Figma REST API (Figma Component Set)
const mockFigmaButtonMeta: FigmaMetaPayload = {
  name: 'Button',
  properties: {
    variant: {
      type: 'VARIANT',
      variantOptions: ['primary', 'secondary', 'danger']
    },
    size: {
      type: 'VARIANT',
      variantOptions: ['sm', 'md', 'lg']
    },
    disabled: {
      type: 'BOOLEAN'
    }
  }
};

export class ComponentParityEngine {
  private project: Project;

  constructor(tsConfigPath: string) {
    this.project = new Project({
      tsConfigFilePath: tsConfigPath
    });
  }

  public verifyComponentParity(componentFilePath: string, figmaMeta: FigmaMetaPayload) {
    const sourceFile = this.project.getSourceFileOrThrow(componentFilePath);
    const propsInterface = sourceFile.getInterface(`${figmaMeta.name}Props`);

    if (!propsInterface) {
      throw new Error(`[PARITY FAULT]: Interface ${figmaMeta.name}Props tidak ditemukan pada ${componentFilePath}`);
    }

    const parityViolations: string[] = [];

    for (const [propName, propDef] of Object.entries(figmaMeta.properties)) {
      const propDeclaration = propsInterface.getProperty(propName);

      if (!propDeclaration) {
        parityViolations.push(`Missing Prop in Code: Figma mendefinisikan properti "${propName}", namun tidak ada di TSX Props.`);
        continue;
      }

      if (propDef.type === 'VARIANT' && propDef.variantOptions) {
        const propType: Type = propDeclaration.getType();
        
        // Ekstraksi nilai union string dari TypeScript Type AST
        const unionValues: string[] = propType.isUnion()
          ? propType.getUnionTypes().map((t) => t.getLiteralValue() as string).filter(Boolean)
          : [propType.getLiteralValue() as string].filter(Boolean);

        for (const opt of propDef.variantOptions) {
          if (!unionValues.includes(opt)) {
            parityViolations.push(
              `Variant Drift: Properti "${propName}" pada Figma memiliki opsi "${opt}", namun kode hanya mendukung: [${unionValues.join(', ')}]`
            );
          }
        }
      }
    }

    if (parityViolations.length > 0) {
      console.error(`❌ Parity Check FAILED for component: ${figmaMeta.name}`);
      parityViolations.forEach((v) => console.error(`   - ${v}`));
      return false;
    }

    console.log(`✅ Parity 100% Verified for component: ${figmaMeta.name}`);
    return true;
  }
}

// Eksekusi jika dipanggil langsung
const checker = new ComponentParityEngine(path.resolve(__dirname, '../tsconfig.json'));
const isParityValid = checker.verifyComponentParity(
  path.resolve(__dirname, '../src/components/Button.tsx'),
  mockFigmaButtonMeta
);

if (!isParityValid) {
  process.exit(1);
}
```

##### 3. Komponen React yang Mematuhi Kontrak Paritas
File: `src/components/Button.tsx`
```tsx
import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

const buttonVariants = cva(
  'inline-flex items-center justify-center font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'bg-[var(--ds-surface-brand-default)] text-white hover:bg-[var(--ds-surface-brand-hover)]',
        secondary: 'bg-transparent border border-[var(--ds-border-neutral)] text-[var(--ds-text-primary)]',
        danger: 'bg-[var(--ds-surface-danger)] text-white hover:opacity-90'
      },
      size: {
        sm: 'h-8 px-3 text-xs rounded-[var(--ds-radius-sm)]',
        md: 'h-10 px-4 text-sm rounded-[var(--ds-radius-md)]',
        lg: 'h-12 px-6 text-base rounded-[var(--ds-radius-lg)]'
      }
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md'
    }
  }
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  variant: 'primary' | 'secondary' | 'danger';
  size: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  children: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={buttonVariants({ variant, size, className })}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Super-App Fintech "NusantaraPay"
- **Skala**: 4 Negara (Indonesia, Vietnam, Thailand, Filipina), 3 Sub-Brand (Consumer Pay, Merchant Biz, Wealth Management).
- **Kompleksitas**: 3 Platforms (React Native, Next.js Web, iOS/Android Native), 420+ Token Semantik, 85 Core UI Components.

#### Permasalahan Awal
1. **Design Token Drift**: Designer mengubah token *corner-radius* dari `8px` ke `12px` di Figma. Perubahan butuh 3 minggu untuk mencapai Web, sementara Android deploy dengan nilai lama, menyebabkan inkonsistensi identitas brand antar platform.
2. **Bundle Size Explosion**: Penggunaan runtime CSS-in-JS (seperti Emotion/Styled-Components) untuk kalkulasi dinamis token multi-brand menyumbang 48KB parse time JavaScript di *low-end devices* (Android Go), memicu perlambatan Time-to-Interactive (TTI).
3. **Accessibility Violations (WCAG AAA)**: Kontras rasio pada dark mode di sub-brand *Wealth* gagal di audit perbankan regional karena *semantic color mapping* dilakukan secara manual oleh developer frontend.

#### Solusi Arsitektural
1. **Unified Token Repository**: Dibangun arsitektur Git terisolasi (`nusantara-design-tokens`) yang diekstrak langsung via Figma API menggunakan GitHub Actions Runner terotomatisasi.
2. **Static CSS Layers Architecture**: Menghapus seluruh dynamic runtime CSS-in-JS. Token diinjeksi melalui CSS Custom Properties statis menggunakan CSS Cascade Layers (`@layer design-system`). Runtime switching dilakukan murni dengan mengganti atribut DOM `data-brand="merchant"` dan `data-theme="dark"`.
3. **Automated WCAG Token Interceptor**: Mengintegrasikan algoritma delta-E (CIEDE2000) dan APCA (Accessible Perceptual Contrast Algorithm) langsung pada pipeline Style Dictionary. Jika kontras token semantic teks terhadap token surface `< 7:1`, build otomatis *fail* di level pipeline.

#### Hasil Metrik (Production Results)
- **Time to Parity (Lead Time)**: Turun dari 21 hari kalender menjadi **18 menit** (dari perubahan Figma sampai rilis NPM package).
- **Bundle Impact**: Ukuran JS Bundle berkurang **32%** pada Web Core Framework karena migrasi dari runtime CSS-in-JS ke CSS variable compilation.
- **Defect Rate**: 0 kasus inkonsistensi variant visual selama 4 kuartal berturut-turut.

---

### 9. Trade-offs

| Dimensi Arsitektural | Opsi A: Compile-Time Static Token Distribution | Opsi B: Runtime Dynamic Injected System | Analisis Konsekuensi Teknikal |
| :--- | :--- | :--- | :--- |
| **Performance** | **Tinggi (Zero JS Runtime Overhead)**. Diparsing native oleh rendering engine browser. | **Menengah-Rendah**. Membutuhkan JS engine untuk evaluasi style tree. | Opsi A unggul untuk TTI (Time-to-Interactive) dan FCP (First Contentful Paint) pada web vital. |
| **Latency / Swapping** | **Instan (< 1 frame / 16ms)** melalui manipulasi atribut root stylesheet. | **Variabel (100-300ms)**. Berpotensi memicu re-render besar pada React Virtual DOM. | Opsi A mengeliminasi *flash of unstyled content* (FOUC). |
| **Scalability (Themes)** | File CSS bertambah seiring jumlah brand dan mode (jika tidak di-split dengan baik). | Fleksibel tanpa limitasi; konfigurasi di-load secara on-demand via JSON API. | Gunakan Opsi A dengan *code-splitting* modular CSS per brand chunk via CDN. |
| **Infra & Tooling Cost**| **Tinggi**. Membutuhkan pipeline AST, Style Dictionary transform, dan verifikasi CI. | **Rendah**. Developer memetakan variabel secara ad-hoc di level state. | Opsi A memerlukan *investment cost* tim Foundation di awal, namun menurunkan *maintenance cost* jangka panjang secara drastis. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Circular Token References
- **Gejala**: Token build crash dengan error `Maximum call stack size exceeded` saat memanggil Style Dictionary.
- **Penyebab**: Definisi token siklik, misal: `color.surface.primary` mereferensikan `color.background.base`, sementara `color.background.base` mereferensikan balik `color.surface.primary`.
- **Troubleshooting**: Terapkan algoritma pendeteksi siklus berbasis DFS (Depth-First Search) pada file JSON sebelum parsing Style Dictionary dimulai:
```typescript
function detectCycle(graph: Record<string, string[]>, node: string, visited = new Set<string>(), recStack = new Set<string>()): boolean {
  visited.add(node);
  recStack.add(node);
  for (const neighbor of graph[node] || []) {
    if (!visited.has(neighbor) && detectCycle(graph, neighbor, visited, recStack)) return true;
    if (recStack.has(neighbor)) return true;
  }
  recStack.delete(node);
  return false;
}
```

#### 2. CSS Specificity Drift pada Multi-Theme Overrides
- **Gejala**: Ketika berganti tema, style lama masih menempel atau style komponen tidak berubah kecuali developer menambahkan `!important`.
- **Penyebab**: Variabel CSS didefinisikan tanpa skema *cascade layer*, sehingga spesifisitas selector class lokal komponen mengabaikan inheritance CSS variable root.
- **Troubleshooting**: Isolasi token dalam `@layer tokens, components;` dan assign nilai komponen hanya dengan membaca custom properties, bukan meng-override hardcoded styles.

#### 3. Variant Mismatch Antara Designer dan Developer
- **Gejala**: Designer membuat varian `type="destructive"` di Figma, tetapi developer mendefinisikannya sebagai `variant="danger"` di TypeScript.
- **Troubleshooting**: Terapkan AST Parity check di pre-commit hook atau GitHub Actions PR gate (lihat skrip `ComponentParityEngine` di Seksi 7).

---

### 11. Best Practices (Production Checklist)

- [ ] **W3C DTCG Standard Compliance**: Pastikan seluruh raw tokens menggunakan sintaks `$value`, `$type`, dan `$description`.
- [ ] **Immutable Token Core**: Jangan pernah mengizinkan pengubahan token `Global` secara sepihak tanpa *major version bump* (SemVer).
- [ ] **CSS Cascade Layering**: Bungkus seluruh token terkompilasi ke dalam `@layer design-system.tokens`.
- [ ] **Strict Typing Generation**: Hasilkan berkas `.d.ts` dan konstanta runtime bertipe `as const` untuk mencegah salah ketik token nama di level kode.
- [ ] **Zero Hardcoded CSS Values**: Lakukan linting via `stylelint` dengan plugin `stylelint-declaration-strict-value` untuk memblokir penulisan warna hex, margin absolut px, atau font family mentah.
- [ ] **Contrast Automation Gate**: Integrasikan pemeriksaan APCA/WCAG 2.1 AAA pada pipeline build Style Dictionary.
- [ ] **Hermetic Testing**: Visual Regression Tests menggunakan Storybook Test Runner dan Playwright harus berjalan dalam Docker container untuk memastikan kesamaan platform font-rendering.

---

### 12. Hands-on Practice

Buatlah workspace praktikum mandiri dengan struktur direktori berikut di direktori `hands-on/m02/`:

```
hands-on/m02/
├── package.json
├── tsconfig.json
├── tokens/
│   ├── primitives/
│   │   └── colors.json
│   └── semantics/
│       └── components.json
├── src/
│   └── components/
│       └── Badge.tsx
└── scripts/
    ├── build-tokens.ts
    └── verify-parity.ts
```

#### Langkah-langkah Praktikum:

##### 1. Setup Dependency
Jalankan inisialisasi di dalam `hands-on/m02/`:
```bash
npm init -y
npm install --save-dev style-dictionary@^4.0.0 ts-morph @types/node typescript ts-node class-variance-authority
```

Konfigurasi `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "moduleResolution": "node",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "jsx": "react-jsx"
  }
}
```

##### 2. Definisi Tokens
File: `tokens/primitives/colors.json`
```json
{
  "color": {
    "emerald": {
      "500": { "$value": "#10B981", "$type": "color" }
    },
    "rose": {
      "500": { "$value": "#F43F5E", "$type": "color" }
    }
  }
}
```

File: `tokens/semantics/components.json`
```json
{
  "badge": {
    "success": {
      "background": { "$value": "{color.emerald.500}", "$type": "color" }
    },
    "critical": {
      "background": { "$value": "{color.rose.500}", "$type": "color" }
    }
  }
}
```

##### 3. Kompilasi Token
Implementasikan skrip `build-tokens.ts` (mengacu pada arsitektur di Seksi 7.B.1) dan jalankan:
```bash
npx ts-node scripts/build-tokens.ts
```
*Pastikan file `dist/css/alpha/tokens.css` dan `dist/ts/alpha/tokens.ts` ter-generate secara sempurna.*

##### 4. Implementasikan Komponen Badge & Parity Verification
- Tulis `src/components/Badge.tsx` dengan varian `status: 'success' | 'critical'`.
- Buat skrip `scripts/verify-parity.ts` untuk memverifikasi keselarasan varian terhadap skema metadata tiruan dari Figma.
- Eksekusi verifikasi:
```bash
npx ts-node scripts/verify-parity.ts
```

---

### 13. Exercise

#### Level Easy
Ubah konfigurasi Style Dictionary untuk menambahkan custom transform bernama `size/percentToRatio` yang mengubah token dimensi dengan unit persen (misal: `"100%"`) menjadi rasio desimal string (misal: `"1.0"`).

#### Level Medium
Buat skrip validasi *Token Linter* independen yang membaca semua file JSON di folder `tokens/`. Aturan validasi:
1. Setiap token wajib memiliki field `$description`.
2. Format nama token wajib menggunakan konvensi `camelCase` untuk setiap leaf node.
3. Lempar exit code 1 jika ditemukan pelanggaran.

#### Level Hard
Kembangkan modul verifikasi AST menggunakan `ts-morph` yang mampu mengekstrak seluruh properti CSS yang diakses dalam komponen React (misal membaca ekspresi `var(--ds-*)`), kemudian melakukan kueri silang ke file output `tokens.ts`. Jika ada token CSS variable yang tidak terdaftar di `tokens.ts`, ciptakan *compiler error* yang mendetailkan file dan baris pelanggarannya.

---

### 14. Challenge

#### Skenario Kasus: Real-Time Dynamic Multi-Tenant Theme Switcher
Sebuah platform SaaS White-Label B2B mewajibkan sistem UI untuk dapat mengganti tema brand secara *runtime* tanpa melakukan fetch file CSS baru dari server dan tanpa memicu re-render siklus React DOM (Zero Virtual-DOM Re-render).

#### Syarat Implementasi:
1. Bangun pipeline token yang memetakan 2 brand berbeda ke format flattened nested tree custom properties CSS.
2. Rancang Web Worker atau performant micro-engine untuk memanipulasi CSSStyleSheet via Constructable Stylesheets API (`CSSStyleSheet.replaceSync`).
3. Buat demo React di mana perubahan warna brand di-trigger dari payload JSON baru, dan seluruh sub-tree komponen beradaptasi di bawah 5 milidetik dengan *memory footprint* seminimal mungkin.
4. Sertakan guardrail anti-memory leak dan proteksi terhadap serangan CSS Injection melalui token sanitization.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Apa tujuan utama dari adopsi spesifikasi W3C DTCG pada repositori design token?**
   - A. Mempercepat rendering CSS di browser.
   - B. Menyediakan skema standar interoperabilitas token yang dapat dikonsumsi oleh berbagai tools desain dan compiler kode secara seragam.
   - C. Menghilangkan kebutuhan untuk styling via CSS.
   - D. Menjamin CSS tersimpan di dalam memori database.

2. **Pada arsitektur 3-tier design token, token semantik (Tier 2) berfungsi untuk:**
   - A. Menentukan nilai absolut hex warna.
   - B. Membatasi token hanya dapat digunakan pada satu tombol saja.
   - C. Mengabstraksikan global tokens ke dalam konteks fungsionalitas dan maksud penggunaan UI.
   - D. Menggantikan peran TypeScript compiler.

3. **Peran utama Style Dictionary dalam Design Systems pipeline adalah:**
   - A. Mendesain aset vektor.
   - B. Menjadi build-system/compiler transformasi token dari format JSON deklaratif ke platform artifacts (CSS, Swift, Kotlin).
   - C. Menggantikan tugas Figma plugin.
   - D. Melakukan screenshot otomatis pada browser.

4. **Karakter penanda token reference (alias) pada spesifikasi W3C DTCG standar adalah:**
   - A. `$token.name$`
   - B. `var(--token-name)`
   - C. `{color.background.primary}`
   - D. `@ref(color.background.primary)`

5. **Mengapa penulisan token menggunakan CSS Cascade Layers (`@layer`) sangat direkomendasikan pada level enterprise?**
   - A. Agar variabel terbaca lebih cepat oleh mesin pencari Google.
   - B. Untuk mengatur hirarki prioritas spesifisitas secara eksplisit dan mencegah konflik override style antar library atau tema.
   - C. Karena CSS standard biasa sudah deprecated di browser modern.
   - D. Untuk mengenkripsi file CSS dari pembajakan kode.

#### Bagian 2: Intermediate (5 Soal)
6. **Di antara skenario berikut, manakah yang mengindikasikan adanya ketergantungan siklik (circular dependency) pada token tree?**
   - A. `token.a` mereferensikan `token.b`, dan `token.b` bernilai `#FFFFFF`.
   - B. `token.a` mereferensikan `token.b`, dan `token.b` mereferensikan `token.a`.
   - C. `token.a` dan `token.b` sama-sama mereferensikan `token.c`.
   - D. `token.a` mereferensikan nilai primitif integer 0.

7. **Bagaimana AST (Abstract Syntax Tree) engine seperti `ts-morph` mendeteksi parity drift antara varian Figma dan kode?**
   - A. Dengan me-render komponen ke DOM virtual lalu membaca teksnya.
   - B. Dengan membedah struktur gramatikal kode TypeScript menjadi pohon sintaksis dan membaca tipe literal pada node deklarasi Props.
   - C. Dengan melakukan pixel matching screenshot komponen.
   - D. Dengan membaca log console saat komponen di-mount.

8. **Mengapa runtime CSS-in-JS (seperti Styled Components tradisional) mulai ditinggalkan pada arsitektur design system enterprise berskala tinggi?**
   - A. Tidak mendukung varian warna.
   - B. Menyebabkan kalkulasi runtime overhead yang mengeksekusi serialization CSS via JavaScript pada setiap render cycle, memperburuk TTI (Time to Interactive).
   - C. Tidak dapat dikombinasikan dengan React.
   - D. Tidak kompatibel dengan browser Safari.

9. **Apa peran dari library `class-variance-authority` (CVA) dalam arsitektur design-to-code parity?**
   - A. Mengompresi ukuran file CSS agar di bawah 10KB.
   - B. Menyediakan deklarasi varian komponen tipe-aman yang memetakan props TSX secara deterministik ke kelas utility styling.
   - C. Menggantikan tugas Webpack atau Vite.
   - D. Menghubungkan langsung database ke UI.

10. **Ketika Style Dictionary mengeksekusi pipeline, apa urutan fase pemrosesan token internal yang benar?**
    - A. Format -> Transform -> Resolve References -> Parse File.
    - B. Parse File -> Resolve References -> Transform -> Format.
    - C. Transform -> Parse File -> Format -> Build.
    - D. Format -> Parse File -> Transform -> Deploy.

#### Bagian 3: Skenario Kasus Produksi (3 Soal)

11. **Skenario Kasus 1**:
    Tim Core Design System merilis versi token baru di mana token semantik `color.surface.action.primary` diubah dari yang semula me-refer `color.blue.500` menjadi `color.indigo.600`. Namun, pada aplikasi dashboard produksi, tombol-tombol utama masih tampak berwarna `blue.500`, meskipun package token di `package.json` sudah di-update ke versi terbaru. Tim menggunakan bundler Webpack dan micro-frontend architecture.
    *Apa kemungkinan akar masalah teknis (root cause) dan bagaimana solusinya?*

12. **Skenario Kasus 2**:
    Sebuah aplikasi e-commerce enterprise memiliki 3 sub-brand. Saat transisi tema dilakukan dengan mengubah atribut `<html data-brand="brandB">`, terjadi layout shift dan performa drop secara drastis (frame drop dari 60fps ke 18fps) selama 300ms. Profiling Chrome DevTools menunjukkan terjadi proses *Recalculate Style* masif pada puluhan ribu elemen DOM.
    *Bagaimana modifikasi arsitektur CSS token untuk mengatasi performance bottle-neck tersebut?*

13. **Skenario Kasus 3**:
    Designer menambahkan varian baru pada komponen Input di Figma bernama `state = "warning"`. Pipeline token berjalan sukses, namun tim QA mendapati bahwa di aplikasi Web, input dengan state warning tidak menampilkan styling border kuning melainkan fallback default border abu-abu. Skrip AST Parity Check tidak mendeteksi error saat pull request dibuka.
    *Di mana kelemahan sistem verifikasi parity tersebut dan bagaimana arsitektur proteksi ganda harus diimplementasikan?*

---

#### Kunci Jawaban & Pembahasan Quiz

##### Bagian 1 & 2:
1. **B** - W3C DTCG bertujuan menstandardisasi representasi data token agar agnostic terhadap vendor software (Figma, Style Dictionary, IDE).
2. **C** - Semantic tokens memberikan konteks intensi desain (misal: "background interaktif") terhadap nilai primitif mentah.
3. **B** - Style Dictionary adalah transform engine CLI/Node.js yang mengonversi JSON token menjadi target spesifik platform.
4. **C** - Notasi kurung kurawal `{path.to.token}` adalah format baku resolusi alias pada standar W3C DTCG.
5. **B** - CSS Layers (`@layer`) memecahkan masalah specificity wars dengan menjamin urutan prioritas styling tanpa dependensi selektor yang kompleks.
6. **B** - Dependensi siklik terjadi jika node A bergantung pada node B dan sebaliknya secara langsung maupun tak langsung.
7. **B** - AST parser menganalisis struktur kode menjadi pohon sintaks objek untuk menginspeksi type literal props tanpa harus menjalankan aplikasi.
8. **B** - Runtime CSS-in-JS membebani CPU device karena terus menginjeksi tag `<style>` dan menghitung hashing class name saat runtime.
9. **B** - CVA menyediakan pendekatan deklaratif tipe-aman untuk memetakan skema varian desain ke kombinasi class styling.
10. **B** - Engine harus membaca file terlebih dahulu, menyelesaikan referensi ketergantungan (DAG), menjalankan fungsi transformators nilai, lalu memformatnya via template engine formatter.

##### Bagian 3 (Skenario Kasus Produksi):
11. **Analisis Masalah Kasus 1**:
    *Root Cause*:
    1. Kegagalan *Cache Invalidation*: Host Micro-frontend (MFE) mungkin meng-embed file CSS token secara global dengan HTTP caching berdurasi panjang, sehingga update bundle CSS dari remote MFE tidak terefleksi.
    2. *Split-lock Package*: Terdapat MFE child yang me-resolve package token internal yang terduplikasi di `node_modules` lokalnya karena *semantic version mismatch* (misal child MFE lock di v1.1.0 sedangkan Host MFE mengimpor v1.2.0).
    *Solusi*:
    Konfigurasikan arsitektur token melalui Module Federation Shared Modules dengan aturan `singleton: true, strictVersion: true`, dan pastikan file stylesheet didistribusikan menggunakan content-hashing pada nama file (misal: `tokens.[contenthash].css`).

12. **Analisis Masalah Kasus 2**:
    *Root Cause*:
    Perubahan atribut pada elemen root `<html>` memaksa browser melakukan *global style invalidation* ke seluruh pohon DOM jika CSS custom property diwariskan (`inherit`) tanpa segmentasi. Jika selector token didefinisikan secara global dengan wildcard atau jika terdapat selector turunan yang kompleks, recalculation cost melonjak tinggi.
    *Solusi*:
    Terapkan teknik CSS *containment* (`contain: style`) pada sub-tree aplikasi atau pisahkan scoping token berdasarkan container utama (misal wrapper sub-aplikasi) alih-alih meletakkannya di root document node. Manfaatkan CSS Variables yang dideklarasikan secara modular di dalam *CSS Cascade Layers*, serta hindari styling turunan yang bergantung pada dynamic descendant selector (misal hindari: `[data-brand="B"] *`).

13. **Analisis Masalah Kasus 3**:
    *Root Cause*:
    Kelemahan Parity Engine: Skrip AST hanya memverifikasi keberadaan tipe pada deklarasi interface TypeScript (`InputProps`), namun tidak memverifikasi apakah nilai varian tersebut benar-benar di-handle pada implementasi logika styling (misal: *implementation branch* di file CVA atau style mapping object terlupakan dan masuk ke `defaultVariants`).
    *Solusi Arsitektur Proteksi Ganda*:
    1. Modifikasi AST checker untuk memvalidasi tidak hanya tipe interface Props, tetapi juga menginspeksi AST dari deklarasi konfigurasi styling (misal menginspeksi node `buttonVariants = cva(...)` untuk memastikan key `warning` ada dan memiliki string class yang valid).
    2. Integrasikan *Automated Contract Component Test* (Storybook CSF v3 + `@storybook/test` via Playwright): Secara otomatis generate story untuk setiap varian yang ada di metadata Figma dan jalankan snapshot visual regression test untuk memvalidasi bahwa style benar-benar ter-render pada computed CSS properties elemen.

---

### 16. Summary

Implementasi *Enterprise Design Systems & Design-to-Code Parity* adalah disiplin rekayasa sistem yang memadukan automasi desain, kompilasi token berbasis DAG, dan verifikasi antarmuka statis berbasis AST. 

Dengan memusatkan data pada arsitektur token 3-tingkat berbasis standar **W3C DTCG**, mengeliminasi overhead runtime JavaScript melalui **CSS Cascade Layers**, serta menerapkan **AST Parity Verification Gateway** di pipeline CI/CD, organisasi dapat menghapus kesenjangan (*drift*) antara rancangan UI di Figma dan implementasi aktual di production. Hasil akhirnya adalah integritas visual antarmuka yang presisi, performa rendering optimal (60fps), skalabilitas *multi-brand* lintas platform yang deterministik, dan siklus rilis yang terotomatisasi secara aman.