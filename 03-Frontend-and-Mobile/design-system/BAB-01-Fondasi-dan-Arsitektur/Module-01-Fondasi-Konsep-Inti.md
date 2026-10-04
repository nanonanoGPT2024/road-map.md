# Bab 01 Module 01: Fondasi Arsitektur Design System & Anatomi Design Token

---

## 1. Metadata & Overview

| Atribut | Keterangan |
| :--- | :--- |
| **Domain** | Design System Engineering & Frontend Architecture |
| **Fokus Modul** | Arsitektur Design Token, Single Source of Truth (SSOT), Multi-Tier Token Contract |
| **Level Teknis** | Advanced / Staff-track |
| **Target Runtime** | Node.js (>=18.x LTS), Web Browser (ESNext, Modern CSS Engine) |
| **Tooling Inti** | Style Dictionary v4, TypeScript 5.x, PostCSS/Modern CSS Custom Properties |

---

## 2. Learning Objectives

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Menganalisis** kegagalan sinkronisasi UI/UX akibat kopling hardcoded value dan memetakan model relasi primitive, semantic, serta component tokens.
2. **Merancang** skema token berspesifikasi W3C Design Tokens Community Group (DTCG) berformat JSON/JSON5 yang mendukung resolusi referensi hierarkis.
3. **Mengonfigurasi dan Mengotomasi** pipeline translasi token lintas platform (*multi-target build system*) menggunakan Style Dictionary engine untuk Web (CSS/JS) dan Mobile (iOS Swift/Android Compose).
4. **Mengimplementasikan** kontrak tiping TypeScript tingkat lanjut (*Template Literal Types*, *Key Remapping*) guna menjamin *compile-time type safety* saat token dikonsumsi komponen.
5. **Mengevaluasi** dampak performa runtime CSS Custom Properties terhadap reflow/repaint engine dan mengaudit arsitektur token dari risiko *specificity collision*.

---

## 3. Conceptual Deep-Dive

### Why: Masalah Fragmentasi Antarmuka Skala Masif
Ketika platform digital berkembang melampaui satu aplikasi—mencakup Web SPA, Web SSR, Micro-frontends, Native iOS, dan Android—sinkronisasi visual menjadi tantangan distributed systems. Tanpa kontrak formal, tim UI engineering jatuh ke dalam jebakan:
- **Drift Value**: Definisi warna "Primary" terdistribusi manual ke `#0D6EFD`, `#0B5ED7`, dan `rgba(13, 110, 253, 1)` di repositori berbeda.
- **Biaya Redesign O(N*M)**: Mengubah baseline corner-radius atau palette brand menuntut perubahan di $N$ platform pada $M$ komponen.
- **Decoupled Semantics**: Developer tidak tahu apakah `#FA5252` digunakan sebagai warna destructive/error atau sekadar aksen dekoratif.

### What: Anatomi Design Tokens sebagai Architecture Primitive
Design Token adalah abstraksi formal dari keputusan desain (*design decisions*) yang dienkapsulasi menjadi data terstruktur (biasanya key-value berformat JSON/DTCG). Token bukan sekadar variabel CSS; token adalah protokol data deterministik.

Arsitektur token modern menganut pemisahan tier tiga lapis (*Three-Tier Token Architecture*):
1. **Global/Primitive Tokens**: Nilai mentah (*raw values*) yang independen dari konteks. Contoh: `blue.500: #1D4ED8`, `spacing.4: 16px`.
2. **Semantic/System Tokens**: Menyematkan intensi konteks dan fungsionalitas. Token ini mereferensikan primitive token. Contoh: `color.background.interactive.hover: {blue.500}`, `feedback.error: {red.600}`.
3. **Component Tokens**: Lingkup lokal (*scoped*) pada komponen UI tertentu untuk mencegah efek samping global. Contoh: `button.primary.hover.background: {color.background.interactive.hover}`.

```
+-------------------------------------------------------------+
| Primitive Tier: blue.600 = #2563EB                         |
+------------------------------+------------------------------+
                               | (referenced by)
+------------------------------v------------------------------+
| Semantic Tier: color.action.primary.default = {blue.600}    |
+------------------------------+------------------------------+
                               | (referenced by)
+------------------------------v------------------------------+
| Component Tier: btn.primary.bg = {color.action.primary.default}
+-------------------------------------------------------------+
```

### How: Transform Engine Pipeline
Proses kompilasi token mengikuti paradigma compiler klasik:
1. **Source Parser**: Membaca kumpulan file JSON/DTCG, membentuk Abstract Token Graph.
2. **Resolver**: Menyelesaikan referensi silang (alias lookup: `{color.brand.primary} -> {palette.blue.600} -> #2563eb`) dan mendeteksi dependensi siklik.
3. **Transformer**: Memanipulasi unit dan representasi nilai (misal: merotasi satuan dari `px` ke `rem`, mentransformasi HEX ke `rgba()` atau format `UIColor` Swift).
4. **Formatter**: Serialisasi token menjadi artefak platform tujuan: CSS Custom Properties, SCSS map, TypeScript constants, Swift struct, atau Android Compose object.

---

## 4. ASCII Architecture Diagram

Berikut adalah alur *Token Lifecycle Pipeline* dari design source hingga runtime aplikasi:

```
+-------------------+
|   Figma Tokens    |
| (Tokens Studio /  |
|  Variables API)   |
+---------+---------+
          |
          | Git Sync / REST API Webhook
          v
+---------+-----------------------------------------------------------+
| SOURCE REPOSITORY (Single Source of Truth)                          |
| tokens/                                                             |
|   ├── base/primitive.json   (Hex, raw rem, primitive scales)        |
|   ├── semantic/light.json   (Token alias to base, light mode context)
|   └── semantic/dark.json    (Token alias to base, dark mode context) |
+---------+-----------------------------------------------------------+
          |
          | npm run build:tokens (Style Dictionary Engine)
          v
+---------+-----------------------------------------------------------+
| COMPILER CORE (Parsing -> Dependency Resolution -> Transformation)  |
|   ├── Cyclic Reference Check (Tarjan's/DFS Algorithm)               |
|   ├── Value Mutation: pxToRem, colorFormatToHsl                     |
|   └── Namespace Prefixing & Sanitization                            |
+---------+-----------------------------------------------------------+
          |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
+---------+---------+ +-------+---------+ +-------+-------------------+
| WEB ARTIFACTS     | | MOBILE ARTIFACTS| | META / DOCUMENTATION      |
| dist/             | | dist/           | | dist/                     |
|  ├── tokens.css   | |  ├── Colors.kt  | |  ├── metadata.json        |
|  ├── tokens.d.ts  | |  └── Style.swift| |  └── search-index.json    |
|  └── tokens.esm.js| |                 | |                           |
+---------+---------+ +-----------------+ +-------+-------------------+
          |
          v
+---------+-----------------------------------------------------------+
| RUNTIME APPLICATION EXECUTION                                       |
| React / SSR Web App                                                 |
| <button style="background-color: var(--color-action-primary)">     |
+---------------------------------------------------------------------+
```

---

## 5. Minimal Working Example (Pure Node.js Token Resolver)

Script murni berikut menunjukkan algoritma inti resolving alias tanpa library pihak ketiga:

```javascript
/**
 * mini-token-resolver.mjs
 * Demonstrasi algoritma resolving referensi token berlapis (dereferencing)
 */

const rawTokens = {
  global: {
    color: {
      blue: {
        600: { value: "#2563eb", type: "color" }
      }
    },
    spacing: {
      base: { value: "4px", type: "spacing" }
    }
  },
  semantic: {
    action: {
      primary: {
        bg: { value: "{global.color.blue.600.value}", type: "color" }
      }
    },
    layout: {
      gutter: { value: "calc({global.spacing.base.value} * 4)", type: "spacing" }
    }
  }
};

function resolvePath(obj, path) {
  return path.split('.').reduce((acc, key) => {
    if (acc === undefined || acc === null) return undefined;
    return acc[key];
  }, obj);
}

function resolveTokenValue(value, dictionary, visited = new Set()) {
  if (typeof value !== 'string') return value;

  const REFERENCE_REGEX = /\{([^}]+)\}/g;
  
  return value.replace(REFERENCE_REGEX, (match, path) => {
    if (visited.has(path)) {
      throw new Error(`Circular reference detected: ${Array.from(visited).join(' -> ')} -> ${path}`);
    }
    
    visited.add(path);
    const resolved = resolvePath(dictionary, path);
    
    if (resolved === undefined) {
      throw new Error(`Unresolved token reference: ${path}`);
    }
    
    return resolveTokenValue(resolved, dictionary, new Set(visited));
  });
}

function compileTokens(source) {
  const result = {};

  function traverse(current, path = []) {
    for (const [key, item] of Object.entries(current)) {
      if (item && typeof item === 'object' && 'value' in item) {
        const resolvedValue = resolveTokenValue(item.value, source);
        const tokenName = `--${[...path, key].join('-')}`;
        result[tokenName] = resolvedValue;
      } else if (item && typeof item === 'object') {
        traverse(item, [...path, key]);
      }
    }
  }

  traverse(source);
  return result;
}

// Execution
try {
  const flatCssTokens = compileTokens(rawTokens);
  console.log("=== HASIL KOMPILASI CSS VARIABLES ===");
  console.log(JSON.stringify(flatCssTokens, null, 2));
} catch (error) {
  console.error("Compilation failed:", error.message);
}
```

---

## 6. Production-Grade Implementation

Implementasi ini menggunakan arsitektur modular: Style Dictionary v4, integrasi TypeScript Engine, validasi format, dan *Type Generator*.

### Directory Tree

```
tokens-compiler/
├── package.json
├── tsconfig.json
├── tokens/
│   ├── primitive/
│   │   └── base.json
│   └── semantic/
│       └── theme-light.json
├── src/
│   ├── config.ts
│   ├── transformers/
│   │   └── pxToRem.ts
│   ├── formats/
│   │   └── tsDefinition.ts
│   └── index.ts
└── dist/ (Generated)
```

### File: `tokens/primitive/base.json`
```json
{
  "primitive": {
    "color": {
      "neutral": {
        "0": { "$value": "#ffffff", "$type": "color" },
        "900": { "$value": "#0f172a", "$type": "color" }
      },
      "brand": {
        "500": { "$value": "#3b82f6", "$type": "color" },
        "600": { "$value": "#2563eb", "$type": "color" }
      }
    },
    "dimension": {
      "scale": {
        "1": { "$value": 4, "$type": "dimension" },
        "2": { "$value": 8, "$type": "dimension" },
        "4": { "$value": 16, "$type": "dimension" }
      }
    }
  }
}
```

### File: `tokens/semantic/theme-light.json`
```json
{
  "semantic": {
    "surface": {
      "background": {
        "$value": "{primitive.color.neutral.0}",
        "$type": "color"
      }
    },
    "interactive": {
      "cta": {
        "default": {
          "$value": "{primitive.color.brand.500}",
          "$type": "color"
        },
        "hover": {
          "$value": "{primitive.color.brand.600}",
          "$type": "color"
        }
      }
    },
    "spacing": {
      "container": {
        "padding": {
          "$value": "{primitive.dimension.scale.4}",
          "$type": "dimension"
        }
      }
    }
  }
}
```

### File: `src/transformers/pxToRem.ts`
```typescript
import type { Transform } from 'style-dictionary/types';

const BASE_FONT_SIZE = 16;

export const pxToRemTransformer: Transform = {
  name: 'dimension/pxToRem',
  type: 'value',
  transitive: true,
  matcher: (token) => {
    return token.$type === 'dimension' || token.type === 'dimension';
  },
  transformer: (token) => {
    const val = parseFloat(token.$value ?? token.value);
    if (isNaN(val)) {
      throw new TypeError(`Invalid numeric value for token ${token.name}: ${token.$value}`);
    }
    if (val === 0) return '0';
    return `${val / BASE_FONT_SIZE}rem`;
  }
};
```

### File: `src/formats/tsDefinition.ts`
```typescript
import type { Format } from 'style-dictionary/types';

export const tsTypeDefinitionFormat: Format = {
  name: 'typescript/exact-types',
  formatter: ({ dictionary }) => {
    const tokens = dictionary.allTokens;
    const tokenNames = tokens.map((t) => `'--${t.name}'`).join(' |\n  ');

    return `// Auto-generated by Style Dictionary Engine. JANGAN DIEDIT MANUAL.
export type DesignTokenName =
  | ${tokenNames};

export interface TokenMetadata {
  name: DesignTokenName;
  value: string;
  originalValue: string;
  path: string[];
}

export const DesignTokenMap: Record<DesignTokenName, string> = {
${tokens.map((t) => `  '--${t.name}': 'var(--${t.name})'`).join(',\n')}
} as const;
`;
  }
};
```

### File: `src/index.ts`
```typescript
import StyleDictionary from 'style-dictionary';
import { pxToRemTransformer } from './transformers/pxToRem.js';
import { tsTypeDefinitionFormat } from './formats/tsDefinition.js';

async function buildTokens(): Promise<void> {
  const sd = new StyleDictionary({
    source: ['tokens/**/*.json'],
    hooks: {
      transforms: {
        'dimension/pxToRem': pxToRemTransformer
      },
      formats: {
        'typescript/exact-types': tsTypeDefinitionFormat
      }
    },
    platforms: {
      css: {
        transformGroup: 'css',
        transforms: ['attribute/cti', 'name/kebab', 'dimension/pxToRem'],
        buildPath: 'dist/css/',
        files: [
          {
            destination: 'variables.css',
            format: 'css/variables',
            options: {
              outputReferences: true,
              selector: ':root'
            }
          }
        ]
      },
      ts: {
        transformGroup: 'js',
        transforms: ['attribute/cti', 'name/kebab', 'dimension/pxToRem'],
        buildPath: 'dist/ts/',
        files: [
          {
            destination: 'tokens.d.ts',
            format: 'typescript/exact-types'
          }
        ]
      }
    }
  });

  try {
    console.log('🚀 Memulai kompilasi Design Tokens...');
    await sd.buildAllPlatforms();
    console.log('✅ Kompilasi sukses untuk semua platform.');
  } catch (error) {
    console.error('❌ Terjadi kesalahan fatal kompilasi token:', error);
    process.exit(1);
  }
}

void buildTokens();
```

### File: `package.json`
```json
{
  "name": "@company/design-tokens",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "tsc && node dist-compiler/index.js",
    "prebuild": "rm -rf dist dist-compiler"
  },
  "dependencies": {
    "style-dictionary": "^4.0.0"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "typescript": "^5.3.3"
  }
}
```

---

## 7. Edge Cases & Boundary Conditions

1. **Circular Aliasing Loops**:
   - Skema seperti Token A $\to$ Token B $\to$ Token A menyebabkan stack overflow. Resolver wajib memakai graph traversal (*Depth First Search*) dilengkapi cache status node (`UNVISITED`, `VISITING`, `VISITED`).
2. **Karakter Non-Alpha-Numerik pada Key**:
   - Penggunaan dot separator dalam value JSON: `interactive.cta.active/focus`. Tanpa sanitasi, output CSS Custom Property menjadi invalid (`--interactive-cta-active/focus`). Formatter harus menyaring karakter selain `[a-zA-Z0-9_-]` menjadi delimiter dash `-`.
3. **Konversi Dimensi Bernilai 0**:
   - Nilai `0` tidak boleh dikonversi ke unit arbitrer (misal `0rem` atau `0px`), karena validasi strict unitless `0` diperlukan untuk beberapa context CSS property seperti `line-height` atau `zoom`.
4. **Theme Nesting Contexts**:
   - Jika dokumen menerapkan dark theme via data attribute `[data-theme='dark']` yang di-nest di dalam light theme, variabel CSS harus mengisolasi scopenya tanpa terjadi leakage inheritance yang menimpa child elements.

---

## 8. Failure Modes & Anti-Patterns

### Anti-Pattern 1: Leaking Raw Primitives ke Application Tier
```typescript
// ❌ WRONG: Komponen UI langsung mengonsumsi raw primitive tokens
export const DangerButton = styled.button`
  background-color: var(--primitive-color-brand-600); // Pelanggaran: Makna semantik hilang!
`;

// ✅ CORRECT: Komponen UI mengonsumsi Semantic atau Component Tokens
export const DangerButton = styled.button`
  background-color: var(--semantic-feedback-danger-surface);
`;
```

### Anti-Pattern 2: Dynamic CSS Variable Injection di Runtime Loop
Menginjeksi ribuan CSS variables secara dinamis lewat React `style` object pada list data yang dirender:
```tsx
// ❌ DANGEROUS: Menyebabkan Layout Thrashing & CSSOM Overhead tinggi
return items.map(item => (
  <div style={{ '--item-bg': item.dynamicColor } as React.CSSProperties} />
));
```
*Solusi*: Definisikan variasi styling statis via class names atau gunakan isolated stylesheet injection.

---

## 9. Trade-offs & Engineering Decisions

| Strategi | Keuntungan (+)| Kerugian (-) | Skenario Pemilihan Optimal |
| :--- | :--- | :--- | :--- |
| **CSS Custom Properties (Runtime Tokens)** | Dynamic theme switching instan (tanpa re-render DOM/JS bundle download). Dukungan nesting natural melalui CSS cascading tree. | Tidak ada dead-code elimination (semua variabel dimuat ke memori browser). Resolusi terjadi di runtime. | Web app modern berorientasi multi-theme (Light/Dark/High Contrast) tanpa reload. |
| **Hardcoded Build-Time Inlining (JS Object/Zero-CSS-runtime)** | Kompatibel dengan tree-shaking 100%. Kompilasi statis CSS string menghemat parsing runtime variable. | Mengubah tema butuh re-mount component tree atau download chunk terpisah. Tidak bisa dinamis per-subtree. | Embedded micro-widgets, micro-frontends dengan batasan isolasi memori ketat. |
| **Monorepo Co-location vs Dedicated Token Repo** | Perubahan token langsung diverifikasi secara Atomic PR bersamaan dengan komponen UI. | Siklus tagging versi terkunci pada siklus rilis library UI. Mobile apps lambat mengejar update. | Core platform engineering tunggal yang mengontrol frontend web dan mobile sekaligus. |

---

## 10. Performance & Optimization

### Metrik & Footprint Runtime
- **CSSOM Tree Size**: Setiap 1000 CSS Variables menambah rata-rata 1.2MB overhead parsing memori internal Blink/Gecko jika diekspos di level `:root`.
- **Bundle Footprint**: Distribusikan token yang telah dipecah:
  - `primitives.css` (hanya jika mutlak diperlukan oleh sub-design-system, biasanya **tidak di-expose** ke bundle client akhir).
  - `theme-light.css` (~4KB gzipped).
  - `theme-dark.css` (~4KB gzipped).

### Optimasi Engine Style Dictionary
Batasi kedalaman traversal token traversal cache. Saat mereferensikan token, hindari transitif build berulang dengan memoization:

```typescript
// Optimasi transform memory caching
const memoizedResolution = new Map<string, string>();

export function getResolvedValue(tokenPath: string, resolverFn: () => string): string {
  if (memoizedResolution.has(tokenPath)) {
    return memoizedResolution.get(tokenPath)!;
  }
  const resolved = resolverFn();
  memoizedResolution.set(tokenPath, resolved);
  return resolved;
}
```

---

## 11. Security & Compliance Implications

1. **CSS Injection Vectors via Token Values**:
   - Jika token menerima input mentah dari eksternal (misal: CMS untuk Whitelabeling Tenant):
   - Token value `16px; background-image: url('http://malicious.com/pwned.png')` bisa lolos jika transformer tidak melakukan sanitasi/escaping.
   - *Mitigasi*: Token schema parser harus menerapkan regex validation strict berbasis JSON Schema/Zod.
2. **CSP (Content Security Policy) Violations**:
   - Pola injeksi CSS Variables via runtime injection `document.documentElement.style.setProperty()` ditolak pada environment CSP ketat: `style-src 'self' 'nonce-xxx'`.
   - *Mitigasi*: Generate CSS file fisik saat build time dan deploy via `<link rel="stylesheet">` yang diberi hash atau nonce resmi.

---

## 12. Observability & Telemetry

Integrasi audit penggunaan token dalam codebase:

```typescript
// scripts/audit-token-usage.ts
import fs from 'node:fs';
import glob from 'glob';

interface TokenCoverageMetrics {
  totalCssProperties: number;
  tokensUsedCount: number;
  hardcodedValuesCount: number;
  coveragePercentage: number;
}

export function auditCodebaseTokens(srcDir: string): TokenCoverageMetrics {
  const files = glob.sync(`${srcDir}/**/*.{css,tsx,ts}`);
  let totalProperties = 0;
  let tokensCount = 0;
  let hardcodedCount = 0;

  const CSS_PROPERTY_REGEX = /:\s*([^;]+);/g;
  const TOKEN_USAGE_REGEX = /var\(--[a-zA-Z0-9-]+\)/;

  for (const file of files) {
    const content = fs.readFileSync(file, 'utf-8');
    let match;
    while ((match = CSS_PROPERTY_REGEX.exec(content)) !== null) {
      totalProperties++;
      if (TOKEN_USAGE_REGEX.test(match[1])) {
        tokensCount++;
      } else {
        hardcodedCount++;
      }
    }
  }

  const coverage = totalProperties === 0 ? 100 : (tokensCount / totalProperties) * 100;

  return {
    totalCssProperties: totalProperties,
    tokensUsedCount: tokensCount,
    hardcodedValuesCount: hardcodedCount,
    coveragePercentage: parseFloat(coverage.toFixed(2))
  };
}

console.log(auditCodebaseTokens('./src'));
```

---

## 13. Real-World War Stories

### Insiden: Out of Memory (OOM) pada CI Runner Akibat Cyclic Dependency Token
*Background*: Tim core design token memperkenalkan cross-theme referencing untuk mendukung mode high-contrast.
*Incident*: Token `color.contrast.border` mereferensikan `color.background.base`, yang pada dark theme mereferensikan `color.contrast.border`.
*Dampak*: Kompilasi `style-dictionary build` terjebak infinite loop tanpa tail-call optimization, menghabiskan 8GB RAM pada runner GitHub Actions, memblokir seluruh pipeline deployment production selama 3 jam.
*Post-Mortem & Fix*:
1. Diimplementasikan graph validation step via Zod + Topological Sort sebelum Style Dictionary dijalankan.
2. Build gagal secara deterministik dalam $\le 200\text{ms}$ jika siklus terdeteksi.

---

## 14. Verification & Testing Strategy

Pengujian token mencakup integrasi skema dan parsing.

### File: `tests/token-pipeline.spec.ts`
```typescript
import { describe, it, expect } from 'vitest';
import { pxToRemTransformer } from '../src/transformers/pxToRem.js';
import type { TransformedToken } from 'style-dictionary/types';

describe('Design Token Transformers: pxToRem', () => {
  it('berhasil mengonversi nilai skalar integer px ke rem', () => {
    const mockToken: TransformedToken = {
      name: 'spacing-medium',
      value: 16,
      $value: 16,
      $type: 'dimension',
      path: ['spacing', 'medium'],
      original: { $value: 16 }
    };

    const transformed = pxToRemTransformer.transformer(mockToken, {}, {});
    expect(transformed).toBe('1rem');
  });

  it('mengonversi angka 0 menjadi unitless 0', () => {
    const mockToken: TransformedToken = {
      name: 'spacing-none',
      value: 0,
      $value: 0,
      $type: 'dimension',
      path: ['spacing', 'none'],
      original: { $value: 0 }
    };

    const transformed = pxToRemTransformer.transformer(mockToken, {}, {});
    expect(transformed).toBe('0');
  });

  it('melempar TypeError jika nilai token tidak valid/NaN', () => {
    const mockToken: TransformedToken = {
      name: 'spacing-invalid',
      value: 'abc',
      $value: 'abc',
      $type: 'dimension',
      path: ['spacing', 'invalid'],
      original: { $value: 'abc' }
    };

    expect(() => pxToRemTransformer.transformer(mockToken, {}, {})).toThrow(TypeError);
  });
});
```

---

## 15. Step-by-Step Hands-On Exercise

### Skenario
Anda ditugaskan membuat token sistem untuk skala elevasi (*elevation/box-shadow*) yang menyelaraskan model lighting Web dan Mobile.

### Tugas
1. Buat file `tokens/primitive/elevation.json` dengan 3 tingkatan (flat, raised, overlay).
2. Tulis transformer kustom `src/transformers/shadowToCss.ts` untuk memetakan spesifikasi array object menjadi string standar CSS `box-shadow`.

### Solusi Parsial Hands-On:

#### File: `tokens/primitive/elevation.json`
```json
{
  "primitive": {
    "elevation": {
      "raised": {
        "$type": "shadow",
        "$value": {
          "offsetX": "0px",
          "offsetY": "4px",
          "blur": "6px",
          "spread": "-1px",
          "color": "rgba(0, 0, 0, 0.1)"
        }
      }
    }
  }
}
```

#### File: `src/transformers/shadowToCss.ts`
```typescript
import type { Transform } from 'style-dictionary/types';

export const shadowToCss: Transform = {
  name: 'shadow/css-shorthand',
  type: 'value',
  transitive: true,
  matcher: (token) => token.$type === 'shadow',
  transformer: (token) => {
    const { offsetX, offsetY, blur, spread, color } = token.$value;
    return `${offsetX} ${offsetY} ${blur} ${spread} ${color}`;
  }
};
```

---

## 16. Troubleshooting Guide

| Gejala (Symptom) | Kemungkinan Akar Masalah (Root Cause) | Tindakan Resolusi (Resolution) |
| :--- | :--- | :--- |
| Perubahan value token di Figma tidak muncul di runtime web. | Build pipeline webhook tidak trigger atau dist folder tidak di-link pada registry npm. | 1. Verifikasi payload commit Figma tokens studio.<br>2. Periksa cache pipeline build CI (`node_modules/.cache`).<br>3. Jalankan `npm run build` lokal dan inspect file `dist/css/variables.css`. |
| Nilai CSS Custom Property muncul sebagai `[object Object]`. | Transformer tidak memformat composite tokens (shadow/typography) menjadi string CSS murni. | Tambahkan kustom transformer yang menangani object schema (seperti `shadow/css-shorthand`). |
| Type-checking TS error: `Property '--action-btn-bg' does not exist`. | Type definitions stale, file `dist/ts/tokens.d.ts` belum di-regenerate pasca skema JSON diubah. | Jalankan script `npm run prebuild && npm run build` untuk meregenerasi interface typescript. |

---

## 17. Production Readiness Checklist

- [ ] Seluruh primitive tokens tidak memiliki referensi silang ke semantic tokens (Acyclic Dependency Model).
- [ ] Tersedia fallback value untuk token browser legacy bila diperlukan.
- [ ] Pipeline validasi skema JSON (JSON Schema Draft-07 / DTCG spec) terintegrasi di tahap Pull Request.
- [ ] Tipe TypeScript diekspor dengan format exact literals (`as const`).
- [ ] CSS generated output bebas dari redundant duplicates (deduplicated selector blocks).
- [ ] Ukuran bundle artifacts CSS terkompresi di bawah ambang batas toleransi (< 15KB brotli).
- [ ] CSS variables aman dari CSS injection via sanitasi format transformer.

---

## 18. Self-Study & Extension Challenges

1. **Static Analysis Linter**: Buat plugin ESLint kustom (`no-hardcoded-colors`) yang mendeteksi penggunaan raw HEX/RGB codes di dalam file styling (CSS-in-JS, Tailwind arbitraries, atau SCSS) dan mewajibkan substitusi ke token CSS variables.
2. **DTCG Spec Compliance**: Implementasikan parser lengkap yang mendukung `$extensions` metadata sesuai draf spesifikasi resmi terbaru dari *W3C Design Tokens Community Group*.
3. **Android Jetpack Compose Exporter**: Perluas platform konfigurasi Style Dictionary untuk men-generate Kotlin sealed class atau `@Composable` object theme tokens secara otomatis.

---

## 19. Key Takeaways & Executive Summary

- **Design System adalah Kompiler**: Desain token bertindak sebagai Intermediate Representation (IR), memungkinkan desain dikompilasi secara deterministik ke target target ekosistem web, iOS, dan Android.
- **Hierarki 3-Tier Wajib**: Primitive $\to$ Semantic $\to$ Component. Mengabaikan lapisan semantic akan merusak skalabilitas theming dan menghasilkan refactoring bernilai mahal di kemudian hari.
- **Strict Typing Mengeliminasi Drift**: Distribusi token harus disertai type declaration TypeScript terkomputasi (`exact literals`) untuk mencegah typo dan *out-of-sync usage* langsung pada tingkat IDE engineer.

---

## 20. Suggested Next Topics & Prerequisite Mapping

```
+------------------------------------------------------------+
| SELESAI: Bab 01 Module 01: Arsitektur Token & Engine Dasar |
+-----------------------------+------------------------------+
                              |
                              v
+------------------------------------------------------------+
| LANJUT: Bab 01 Module 02: Multi-Brand & Dynamic Theming    |
| Architecture (Context Isolation, SCSS vs Modern CSS Scope) |
+-----------------------------+------------------------------+
                              |
                              v
+------------------------------------------------------------+
| TARGET: Bab 02: Polymorphic UI Primitive Components        |
| (Radix Primitives, Base Aria Contracts, Dynamic Styling)   |
+------------------------------------------------------------+
```

* Prasyarat Lanjutan: Pemahaman mendalam terkait CSS Specificity, CSS Cascade Layers (`@layer`), dan AST Manipulation menggunakan PostCSS.