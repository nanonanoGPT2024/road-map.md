# Kurikulum Enterprise: Product Design & Design Systems Engineering
**Kategori:** 03-Frontend-and-Mobile  
**Bab 01:** Fondasi dan Arsitektur  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengoperasikan arsitektur token desain tersinkronisasi (*Design Token Pipeline*) berbasis W3C Design Token Community Group (DTCG) specification secara otomatis dari Figma ke multi-platform target (Web/CSS, iOS/Swift, Android/Kotlin).
- Mengimplementasikan pola arsitektur *Headless Component* yang decoupled dari visual presentation layer, menjamin aksesibilitas tingkat enterprise (WCAG 2.2 Level AA/AAA compliance).
- Mengintegrasikan *Contract-Driven UI Architecture* antara product designer dan frontend engineer menggunakan skema validasi berbasis AST (Abstract Syntax Tree) dan CI/CD automation.
- Mengelola state theming dinamis pada skala multi-brand dan runtime mode switching (Light/Dark/High Contrast) dengan zero-runtime overhead dan zero-CLS (*Cumulative Layout Shift*).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Foundational Token Design:** Pemahaman struktur token primitif, semantik, dan komponen (Modul 01).
- **TypeScript Lanjutan:** Utility types, template literal types, AST manipulasi dasar, dan mapped types.
- **Modern Build Tools & Engine:** Node.js/Bun execution, Rollup/Vite, Style Dictionary v4, Tailwind CSS engine internals, dan PostCSS.
- **Cross-platform UI Paradigms:** DOM layout tree & CSSOM (Web), UIKit/SwiftUI declarative paradigm (iOS), serta Jetpack Compose composable nodes (Android).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 The W3C DTCG Token Engine Architecture

Arsitektur token enterprise tidak lagi memperlakukan nilai desain (warna, spacing, tipografi) sebagai konstanta CSS statis. Token didefinisikan sebagai *Directed Acyclic Graph* (DAG), di mana node leaf merepresentasikan nilai skalar mentah (*Global/Primitive Tokens*), node intermediate merepresentasikan konteks bisnis (*Semantic/Alias Tokens*), dan node root merepresentasikan penerapan spesifik (*Component-scoped Tokens*).

```
[ Primitive Tokens ] (e.g., color.blue.500: #3B82F6)
        │
        ▼  Resolved via Alias Pointer ($value: "{color.blue.500}")
[ Semantic Tokens ] (e.g., surface.brand.primary: #3B82F6)
        │
        ▼  Context Injected (Brand: A, Mode: Dark)
[ Component Tokens ] (e.g., button.primary.bg.default: "{surface.brand.primary}")
        │
        ├── Compile-time Resolver (Style Dictionary Engine)
        │         ├── Formatter (AST Transpilation)
        │         └── Transform Group (Unit normalization: rem, pt, dp)
        ▼
[ Production Artifacts ]
   ├── Web: tokens.css / tokens.ts
   ├── iOS: DesignTokens.swift (UIColor / SwiftUI Color struct)
   └── Android: DesignTokens.kt (Compose Color / Dimension)
```

Proses resolusi dependensi token mengikuti algoritma Topological Sort:
1. **Extraction:** Menarik payload JSON dari Figma Variables API via Webhook atau REST API.
2. **Normalization:** Mengonversi struktur Figma ke W3C DTCG format (`$value`, `$type`, `$description`).
3. **Graph Flattening & Cycle Detection:** Memastikan tidak ada sirkular dependency (contoh: Token A merujuk Token B, dan Token B merujuk Token A).
4. **Transform Engine:**
   - Menghitung resolusi matematika dimensi (misal: scaling modular scale `1.25` dari basis `16px`).
   - Resolusi color-space: Konversi sRGB ke Display P3 dan format Oklch untuk konsistensi persepsi visual manusia (perceptual uniformity).
5. **Codegen:** Mengalirkan token yang telah diproses ke template generator AST untuk menghasilkan artefak type-safe.

### 3.2 Dynamic Theming & Sub-tree Scoping Engine

Pada arsitektur enterprise multi-brand (misal: satu codebase melayani Brand A, Brand B, dan sub-aplikasi internal), theming tidak boleh bergantung pada bundling terpisah atau rendering ulang aplikasi secara menyeluruh (*full app re-render*).

Pendekatan modern menggunakan **CSS Custom Property Scoping via Selector Tree Partitioning**:
- Level Root `:root` mendefinisikan fallback dan primitive layer.
- Attribut data `[data-theme="brand-a"][data-mode="dark"]` mendefinisikan alias layer.
- Dynamic Sub-tree Switching: Sebuah node kontainer dapat meng-override konteks tema untuk seluruh anak pohonnya (*child tree*) hanya dengan mengubah atribut DOM, tanpa mempengaruhi CSSOM tree global.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Hardcoded / Raw CSS) | Pendekatan Enterprise (Design Token Pipeline & Headless Architecture) |
| :--- | :--- | :--- |
| **Why (Tujuan)** | Cepat dibangun di awal, mengabaikan fragmentasi UI. | Skalabilitas multi-brand, nol drift antara desain dan implementasi, konsistensi multi-platform. |
| **What (Wujud)** | Kode CSS/SCSS acak, nilai heksadesimal tersebar di repo web dan native. | Single Source of Truth (SSOT) JSON DTCG repo -> Digenerasi otomatis ke Web, iOS, Android melalui pipeline CI/CD. |
| **Maintenance** | Re-theming memakan waktu berminggu-minggu dengan risiko regresi visual tinggi. | Perubahan warna/spacing global selesai dalam hitungan detik via Figma Variable sync. |
| **Aksesibilitas** | Pengecekan manual post-deployment, sering gagal audit rasio kontras. | Automated contrast calculation (APCA/WCAG) pada fase build token. |

---

## 5. How (Workflow Detail)

Alur kerja sinkronisasi token dan integrasi komponen pada arsitektur produksi:

```
[Designer] ──> Updates Variables in Figma
                   │
                   ▼ (Figma Action / Webhook)
[GitHub Actions] ──> Fetch Figma Variables (Figma REST API)
                   │
                   ▼ (Validation)
             Run DTCG Schema Validator & APCA Contrast Analyzer
                   │
                   ▼ (Transform: Style Dictionary v4)
             Resolve References ──> Apply Math Transforms ──> Output Formats
                   │
                   ├──> Generate packages/tokens/dist/css/variables.css
                   ├──> Generate packages/tokens/dist/ios/Tokens.swift
                   ├──> Generate packages/tokens/dist/android/Tokens.kt
                   └──> Generate packages/tokens/dist/ts/tokens.d.ts & tokens.js
                   │
                   ▼ (Publish)
             Publish to NPM Private Registry / Internal Git Submodules
                   │
                   ▼ (Consumers)
       ┌───────────┼───────────┐
       ▼           ▼           ▼
   Web App     iOS App    Android App
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem ini seperti jalur transmisi listrik modular (Power Grid):
- **Primitive Tokens** adalah sumber energi mentah (Batu bara, Hidro, Solar: 10.000V). Nilai ini berbahaya dan tidak stabil jika dicolok langsung ke perangkat pengguna.
- **Semantic Tokens** adalah gardu trafo distribusi yang menurunkan dan menamai voltase (Daya Domestik Standar: 220V, Daya Industri: 380V). Pengguna tahu kapan harus memakai daya 220V tanpa peduli sumber awalnya.
- **Component Tokens** adalah stopkontak spesifik di dinding (Stopkontak Kulkas, Stopkontak Server).
- **Headless Components** adalah sasis mesin cuci yang memiliki mekanisme motor, pompa, dan logika pengaman putaran, namun panel luarnya (casing, stiker warna) dapat diganti sesuai brand pabrikan.

```
[FigJam / Figma Canvas]
        │ (Raw Hex, Spacing)
        ▼
┌──────────────────────────────────────────────┐
│  STYLE DICTIONARY ENGINE (Trafo Distribusi)   │
│                                              │
│  Input: { "$value": "#0052CC", "$type": ...} │
│    ├── Transform: sRGB -> Oklch              │
│    ├── Format: Swift / CSS Var / Compose     │
│    └── Validate: Min Contrast Ratio 4.5:1    │
└──────────────────────────────────────────────┘
        │
        ├──────────────────────┬──────────────────────┐
        ▼                      ▼                      ▼
  [Web Platform]         [iOS Platform]         [Android Platform]
  --color-primary:       let colorPrimary =     val ColorPrimary =
     oklch(0.55 0.2 260)    Color(red:...)         Color(0xFF0052CC)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: W3C DTCG Token Definition
Definisi token dalam format standar (`tokens/primitives.json`):

```json
{
  "color": {
    "blue": {
      "500": {
        "$value": "#2563eb",
        "$type": "color",
        "$description": "Core identity primitive blue"
      }
    },
    "neutral": {
      "900": {
        "$value": "#0f172a",
        "$type": "color"
      }
    }
  }
}
```

Token semantik mereferensikan primitif (`tokens/semantics.json`):
```json
{
  "surface": {
    "action": {
      "primary": {
        "$value": "{color.blue.500}",
        "$type": "color",
        "$description": "Default background for prominent actions"
      }
    }
  }
}
```

---

### 7.2 Practical Example: Enterprise-Grade Style Dictionary Pipeline with Contrast Validation & Headless Component

#### Step 1: Config Style Dictionary (`build-tokens.ts`)
Menggunakan TypeScript dan Style Dictionary API terbaru untuk validasi rasio kontras saat build-time.

```typescript
import StyleDictionary from 'style-dictionary';
import type { TransformedToken } from 'style-dictionary';

// Helper perceptual luminance calculation (Relative Luminance WCAG 2.1)
function getLuminance(hex: string): number {
  const rgb = hex.replace('#', '').match(/.{1,2}/g)?.map(x => parseInt(x, 16) / 255) || [0, 0, 0];
  const a = rgb.map(v => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)));
  return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
}

function calculateContrast(hex1: string, hex2: string): number {
  const lum1 = getLuminance(hex1);
  const lum2 = getLuminance(hex2);
  const brightest = Math.max(lum1, lum2);
  const darkest = Math.min(lum1, lum2);
  return (brightest + 0.05) / (darkest + 0.05);
}

// Custom Formatter with Built-in Contrast Assertion
StyleDictionary.registerFormat({
  name: 'css/validated-variables',
  format: async ({ dictionary }) => {
    // Assert: Check primary text against primary background
    const bgToken = dictionary.allTokens.find(t => t.name === 'surface-action-primary');
    const textToken = dictionary.allTokens.find(t => t.name === 'text-on-action-primary');

    if (bgToken && textToken) {
      const contrast = calculateContrast(bgToken.value, textToken.value);
      if (contrast < 4.5) {
        throw new Error(
          `[A11Y ERROR] Aksesibilitas gagal: Kontras antara ${bgToken.name} (${bgToken.value}) ` +
          `dan ${textToken.name} (${textToken.value}) adalah ${contrast.toFixed(2)}:1 (Minimal 4.5:1)`
        );
      }
    }

    const cssVars = dictionary.allTokens
      .map((token: TransformedToken) => `  --${token.name}: ${token.value};`)
      .join('\n');

    return `:root {\n${cssVars}\n}\n`;
  }
});

const sd = new StyleDictionary({
  source: ['tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'build/css/',
      files: [{
        destination: 'variables.css',
        format: 'css/validated-variables'
      }]
    },
    ios: {
      transformGroup: 'ios-swift',
      buildPath: 'build/ios/',
      files: [{
        destination: 'StyleTokens.swift',
        format: 'ios-swift/class.swift'
      }]
    }
  }
});

await sd.buildAllPlatforms();
console.log('Build token selesai dengan sukses.');
```

#### Step 2: Headless Component State Engine (React + ARIA State Machine)
Komponen Enterprise Button tanpa dependensi framework UI eksternal, decoupled sepenuhnya dari styling:

```tsx
import React, { forwardRef, useRef } from 'react';

export interface UseButtonProps {
  isDisabled?: boolean;
  onPress?: (e: React.MouseEvent | React.KeyboardEvent) => void;
  'aria-label'?: string;
  type?: 'button' | 'submit' | 'reset';
}

export function useButton(
  props: UseButtonProps,
  ref: React.RefObject<HTMLButtonElement | null>
) {
  const { isDisabled, onPress, type = 'button' } = props;

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (isDisabled) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onPress?.(event);
    }
  };

  const handleClick = (event: React.MouseEvent) => {
    if (isDisabled) {
      event.preventDefault();
      return;
    }
    onPress?.(event);
  };

  return {
    buttonProps: {
      type,
      tabIndex: isDisabled ? -1 : 0,
      'aria-disabled': isDisabled ? true : undefined,
      disabled: isDisabled,
      onClick: handleClick,
      onKeyDown: handleKeyDown,
      role: 'button',
      ref
    }
  };
}

// Consumer Presentation Component
export interface ButtonProps extends UseButtonProps {
  variant?: 'primary' | 'secondary' | 'danger';
  children: React.ReactNode;
  className?: string;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(({
  variant = 'primary',
  children,
  className = '',
  ...props
}, forwardedRef) => {
  const localRef = useRef<HTMLButtonElement | null>(null);
  const ref = (forwardedRef as React.RefObject<HTMLButtonElement>) || localRef;
  const { buttonProps } = useButton(props, ref);

  return (
    <button
      {...buttonProps}
      className={`btn-base btn--${variant} ${className}`}
    >
      <span className="btn__label">{children}</span>
    </button>
  );
});

Button.displayName = 'EnterpriseButton';
```

#### Step 3: CSS Consumer Implementation (CSS Semantic Tokens)
```css
/* button.css */
.btn-base {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-inset-sm) var(--space-inset-md);
  border-radius: var(--radius-interactive-md);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-body-md);
  font-weight: var(--font-weight-medium);
  transition: background-color 150ms cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 150ms cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
  border: 1px solid transparent;
}

.btn-base:focus-visible {
  box-shadow: 0 0 0 3px var(--surface-canvas-bg), 
              0 0 0 6px var(--border-focus-ring);
}

.btn--primary {
  background-color: var(--surface-action-primary);
  color: var(--text-on-action-primary);
}

.btn--primary:hover:not([disabled]) {
  background-color: var(--surface-action-primary-hover);
}

.btn--primary[disabled] {
  background-color: var(--surface-action-disabled);
  color: var(--text-on-disabled);
  cursor: not-allowed;
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Arsitektur Multi-Brand FinTech Global (SuperApp)
Sebuah konglomerat teknologi keuangan menaungi 3 produk:
1. **NeoBank Consumer** (Karakter: Playful, Border Radius Besar, Light Theme Dominan).
2. **Institutional Trading Terminal** (Karakter: High Information Density, Radius 0px, Dark Theme Permanen, Monospace Numbers).
3. **SME Payment Gateway** (Karakter: Corporate Blue, Standar Neutral).

#### Tantangan Teknis:
- Satu tim Design System (Core DS) harus melayani 140 frontend engineers di 18 squad feature.
- Token drift mencapai 40% di mana engineer sering melakukan *override inline* karena skema warna token tidak mencukupi kebutuhan sub-brand.
- Perubahan warna brand institusional membutuhkan waktu rilis 3 minggu karena pengetesan manual visual regression di 400+ view native dan web.

#### Solusi Arsitektural:
1. **Layered Token Repository:**
   Memisahkan token menjadi 3 paket independen:
   - `@enterprise/tokens-core`: Menyimpan nilai primitif dan fungsi kalkulasi matematika.
   - `@enterprise/tokens-brand-[consumer|trading|sme]`: Menimpa semantic token dengan merujuk pada core.
   - `@enterprise/tokens-runtime`: Engine CSS-in-JS/PostCSS injection untuk runtime switching.
2. **Automated Figma CI Engine:**
   GitHub Actions mendeteksi perilisan Figma Library versi baru via Figma Webhook. Engine memvalidasi kontras warna teks terhadap surface target (WCAG AAA untuk Institutional Terminal, AA untuk Consumer). Jika lolos, NPM package baru dirilis secara otomatis (`semantic-release`), dan PR pembaruan dependency dibuat ke repositori consumer via Renovate Bot.
3. **AST Linting & Enforcement:**
   Menerapkan custom ESLint plugin (`eslint-plugin-design-tokens-enforce`) yang memblokir penulisan hardcoded CSS hex codes (`#FFFFFF`, `rgb(...)`) atau inline Tailwind values yang tidak terdaftar di semantic tokens (`bg-[#123456]`).

#### Hasil:
- Zero visual drift antara Figma dan Production.
- Waktu deployment perubahan tema global turun dari 3 minggu menjadi 12 menit (durasi pipeline CI/CD).
- Bundle size berkurang 18% pada aplikasi web karena deduplikasi nilai warna statis menjadi shared atomic CSS tokens.

---

## 9. Trade-offs (Analisis Komparasi Arsitektur)

| Skenario Desain Token | Kelebihan | Biaya & Trade-off Teknis |
| :--- | :--- | :--- |
| **CSS Variables (Runtime Switch)** | - Nol re-render React/DOM tree.<br>- Dynamic switching instan via DOM attribute.<br>- Overhead parsing JavaScript rendah. | - Tidak kompatibel langsung dengan platform Canvas/WebGL.<br>- Rawan *Flash of Unstyled Theme (FOUT)* jika token dimuat asinkron. |
| **Compile-time CSS Extraction (Vanilla Extract/Tailwind JIT)** | - Zero-runtime performance impact.<br>- Dead-code elimination optimal.<br>- Validasi tipe statis komprehensif. | - Kompilasi build time lebih lambat.<br>- Sulit mendukung runtime customization oleh user (misal: custom brand theme oleh end-user enterprise). |
| **Component-Level Design Tokens (Micro-tokenization)** | - Presisi kontrol visual komponen 100%.<br>- Sangat aman dimodifikasi secara lokal tanpa efek samping global. | - Ledakan volume token (*token explosion*). File CSS bisa mencapai beberapa megabyte jika tidak dipadatkan.<br>- Beban kognitif tinggi bagi developer baru. |
| **Headless + Tailwind Token Mapping** | - Integrasi cepat dengan codebase existing.<br>- Aksesibilitas bawaan tinggi via library state. | - Membutuhkan abstraction layer tambahan.<br>- Debugging specificity conflict di CSS cascading layer kadang rumit jika konfigurasi plugin bermasalah. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Mengabstraksi Token Terlalu Dini atau Terlalu Dangkal
* **Kesalahan:** Menamai token semantik berdasarkan implementasi visual pertama kali, contoh: `color-sidebar-blue: #0000FF`. Saat sidebar diubah menjadi hitam, token bernama `blue` bernilai `#000000`.
* **Solusi Enterprise:** Gunakan penamaan fungsional berbasis peran: `surface-navigation-background`. Penamaan tidak boleh mendefinisikan warna fisik literal.

### 10.2 Circular Dependency pada Dynamic Theming
* **Gejala:** Resolver Style Dictionary crash dengan pesan `RangeError: Maximum call stack size exceeded` atau CSS runtime menampilkan `var(--color-a)` yang mereferensikan `var(--color-b)` dan sebaliknya.
* **Troubleshooting Step:**
  1. Pasang detektor sirkular berbasis DAG pada pipeline JSON parsing.
  2. Implementasikan algoritma Tarjan atau DFS cycle detection sebelum passing payload ke engine kompilasi:
  ```typescript
  function detectCycle(graph: Map<string, string[]>): boolean {
    const visited = new Set<string>();
    const recStack = new Set<string>();
    for (const node of graph.keys()) {
      if (checkCycleUtil(node, visited, recStack, graph)) return true;
    }
    return false;
  }
  ```

### 10.3 Cumulative Layout Shift (CLS) Akibat Font Token Swapping
* **Gejala:** Saat berpindah tema (misal: Dark ke Light, atau Consumer ke Trading) yang menggunakan ukuran/weight font berbeda, layout bergeser drastis (CLS > 0.1).
* **Solusi Enterprise:** Normalisasi *font metric override* pada `@font-face` menggunakan properti CSS:
  ```css
  @font-face {
    font-family: 'Brand-Font-Fallback';
    src: local('Arial');
    ascent-override: 95%;
    descent-override: 20%;
    line-gap-override: 0%;
  }
  ```
  Pastikan nilai `line-height` pada token bersifat absolut (misal: `1.5` unitless atau `px` terukur) bukan mengandalkan inherent metrics dari file font.

---

## 11. Best Practices (Production Checklist)

- [ ] **DTCG Compliance:** Semua token JSON menggunakan format standar W3C (`$value`, `$type`, `$description`).
- [ ] **Contrast Automation:** CI pipeline secara otomatis menggagalkan build jika kontras teks terhadap background semantic-nya di bawah 4.5:1 (Normal Text) atau 3:1 (Large Text/UI Components).
- [ ] **Platform Target Support:** Pipeline menghasilkan output minimal untuk 3 platform: CSS variables (Web), Swift structs (iOS), dan Jetpack Compose objects (Android).
- [ ] **Immutable Primitives:** Primitives tokens tidak boleh diubah oleh context runtime (light/dark mode hanya menukar pointer pada alias/semantic token layer).
- [ ] **Zero Inline Visual Hacks:** CSS files di aplikasi client tidak boleh mengandung static hex `#`, `rgb`, atau arbitrary unit dimensions yang tidak terdaftar di token registry.
- [ ] **Component Boundary Isolation:** Gunakan CSS `@layer` (misal: `@layer tokens, base, components, utilities;`) untuk memastikan token tidak kalah prioritas cascading dari selector pihak ketiga.
- [ ] **AST Tree-Shaking:** Pastikan distribusi TypeScript token mengekspor const assertions (`as const`) agar auto-complete TypeScript instan tanpa membebani runtime bundle size.

---

## 12. Hands-on Practice

Buatlah sistem kompilasi token modular di direktori kerja: `hands-on/m02/`

### Struktur Direktori:
```text
hands-on/m02/
├── package.json
├── tsconfig.json
├── tokens/
│   ├── primitives/
│   │   ├── colors.json
│   │   └── spacing.json
│   └── semantics/
│       ├── light.json
│       └── dark.json
├── scripts/
│   └── build-tokens.ts
└── src/
    └── components/
        └── Button.tsx
```

### Langkah 1: Setup Workspace & Dependencies
Inisialisasi workspace Node.js dan pasang dependency:
```bash
mkdir -p hands-on/m02/tokens/primitives hands-on/m02/tokens/semantics hands-on/m02/scripts hands-on/m02/src/components
cd hands-on/m02
npm init -y
npm install -D typescript @types/node style-dictionary tsx
```

### Langkah 2: Buat Token JSON
`tokens/primitives/colors.json`:
```json
{
  "color": {
    "white": { "$value": "#ffffff", "$type": "color" },
    "black": { "$value": "#000000", "$type": "color" },
    "gray": {
      "100": { "$value": "#f1f5f9", "$type": "color" },
      "800": { "$value": "#1e293b", "$type": "color" },
      "900": { "$value": "#0f172a", "$type": "color" }
    },
    "emerald": {
      "500": { "$value": "#10b981", "$type": "color" },
      "600": { "$value": "#059669", "$type": "color" }
    }
  }
}
```

`tokens/semantics/light.json`:
```json
{
  "surface": {
    "canvas": { "$value": "{color.white}", "$type": "color" },
    "brand": {
      "default": { "$value": "{color.emerald.500}", "$type": "color" },
      "hover": { "$value": "{color.emerald.600}", "$type": "color" }
    }
  },
  "text": {
    "primary": { "$value": "{color.gray.900}", "$type": "color" },
    "on-brand": { "$value": "{color.white}", "$type": "color" }
  }
}
```

`tokens/semantics/dark.json`:
```json
{
  "surface": {
    "canvas": { "$value": "{color.gray.900}", "$type": "color" },
    "brand": {
      "default": { "$value": "{color.emerald.600}", "$type": "color" },
      "hover": { "$value": "{color.emerald.500}", "$type": "color" }
    }
  },
  "text": {
    "primary": { "$value": "{color.gray.100}", "$type": "color" },
    "on-brand": { "$value": "{color.white}", "$type": "color" }
  }
}
```

### Langkah 3: Eksekusi Pipeline
Tulis build engine pada `scripts/build-tokens.ts` (gunakan implementasi Style Dictionary yang memproses file semantic light dan dark secara terpisah dengan CSS scoping class), kemudian jalankan:
```bash
npx tsx scripts/build-tokens.ts
```

---

## 13. Exercise

### Level Easy
Ubah file `tokens/primitives/spacing.json` untuk menerapkan modular scale 8-point system (skala: `0`, `4px`, `8px`, `16px`, `24px`, `32px`, `48px`, `64px`) menggunakan format standar W3C DTCG. Buat transform script sederhana untuk mengubah semua nilai pixel (`px`) menjadi `rem` secara otomatis (asumsi `1rem = 16px`).

### Level Medium
Buat transformer custom untuk Style Dictionary yang mengekspor token ke format SCSS Map, dengan validasi format penamaan BEM (`Block-Element-Modifier`). Pastikan build script memunculkan warning jika ditemukan nesting token lebih dari 4 level depth.

### Level Hard
Implementasikan sebuah utility AST transformer menggunakan `@babel/parser` dan `magic-string` yang menganalisis file React Component (`.tsx`). Transformer ini harus mendeteksi secara statis jika ada inline style atau string literal Tailwind class yang melanggar aturan semantik sistem (misal penggunaan `className="bg-[#2563eb]"` atau `style={{ color: '#fff' }}`), dan secara otomatis mengubahnya menjadi token reference class yang setara (`className="bg-surface-brand-default"`).

---

## 14. Challenge

### Arsitektur Micro-Frontend Dynamic CSS Isolation & Font Metrics Standardization

#### Deskripsi Kasus:
Anda ditunjuk sebagai Principal Design System Engineer di sebuah unicorn ecommerce. Aplikasi web utama Anda menggunakan arsitektur Micro-Frontend (MFE) di mana 6 aplikasi berjalan pada satu viewport DOM:
- Header & Navigasi (MFE Tim Platform - React)
- Product Detail (MFE Tim Catalog - Next.js)
- Payment Gateway Widget (MFE Tim Checkout - Svelte)
- Recommendation Engine (MFE Tim ML - Vue 3)

Masing-masing MFE saat ini membawa library tema masing-masing. Masalah kritis muncul:
1. **CSS Collision:** Token CSS variable `--primary-color` dari Tim Checkout menimpa CSS variable Tim Catalog.
2. **Font Jitter/Layout Shift:** Tim Catalog menggunakan Web Font kustom, sedangkan Tim Checkout menggunakan System Native Font. Ketika komponen dirender berdampingan, baseline text tidak rata sebesar 3px, mengakibatkan tombol navigasi bergetar (*layout jitter*).
3. **Memory Leaks:** Pergantian tema terus menerus menginjeksi tag `<style>` baru ke dalam `<head>` tanpa pembersihan berkala.

#### Tugas Arsitektural Anda:
Rancang arsitektur integrasi design token terpadu yang memecahkan masalah di atas secara tuntas.
- Definisikan strategi CSS Isolation (apakah menggunakan Shadow DOM, CSS Layering, scoping attributes unik, atau sandboxed custom property namespaces).
- Rancang skema Shared Memory Token Synchronization yang aman tanpa mengorbankan decoupled release lifecycle tiap tim micro-frontend.
- Tulis spesifikasi implementasi engine fallback font metric untuk menyamakan baseline alignment lintas font keluarga secara deterministik.
- Sediakan proof-of-concept skema arsitektur dan dokumentasi integrasi API antarmuka (*Interface Specification*).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda / Konsep Fondasional)

1. Apa perbedaan arsitektural utama antara Primitive Token dan Semantic Token?
   - A. Primitive token disimpan dalam JSON, semantic token disimpan dalam CSS.
   - B. Primitive token merepresentasikan nilai skalar absolut tanpa konteks penggunaan, sedangkan semantic token merepresentasikan intent atau fungsi bisnis dari token tersebut.
   - C. Primitive token hanya dapat digunakan di platform Web, sedangkan semantic token hanya untuk Mobile.
   - D. Semantic token tidak dapat dikonversi ke CSS Variables.

2. Menurut spesifikasi W3C Design Token Community Group (DTCG), properti standar apa yang wajib digunakan untuk mendefinisikan nilai aktual dari sebuah token?
   - A. `value`
   - B. `val`
   - C. `$value`
   - D. `rawValue`

3. Mengapa unit `rem` lebih disukai dibandingkan `px` untuk ukuran font dan spacing pada aplikasi web enterprise?
   - A. `rem` membuat rendering GPU lebih cepat dibanding `px`.
   - B. `rem` menghormati preferensi ukuran font root browser yang diatur oleh pengguna untuk kebutuhan aksesibilitas visual.
   - C. `px` tidak dapat diparsing oleh mobile browser modern.
   - D. `rem` menghapus kebutuhan akan media queries secara keseluruhan.

4. Apa dampak penggunaan headless component pattern terhadap implementasi design system?
   - A. Mempercepat rendering DOM dengan cara menghilangkan layer virtual DOM.
   - B. Mengisolasi state machine, event handling, dan aksesibilitas keyboard dari lapisan tampilan visual (CSS).
   - C. Mengharuskan developer menulis styling menggunakan inline CSS styles.
   - D. Menghilangkan kebutuhan penulisan unit testing.

5. Apa fungsi utama dari algoritma Topological Sort pada build engine token desain?
   - A. Menghapus token yang tidak digunakan dalam kode client.
   - B. Mengompres ukuran file JSON token menjadi format biner.
   - C. Menyusun urutan kompilasi token berdasarkan pohon dependensi alias sehingga token referensi selalu dihitung setelah token sumbernya tersedia.
   - D. Mengubah format warna sRGB menjadi HEX string.

---

### Bagian 2: Intermediate (Analisis Arsitektur)

6. Pada arsitektur multi-brand theming menggunakan CSS custom properties, mengapa pendekatan pengubahan class selector pada elemen root (`<html class="brand-a">`) lebih efisien dibandingkan melakukan *mount/unmount* file `<link rel="stylesheet">` dinamis?
   - A. Mengubah atribut class tidak memicu Network Request baru dan mencegah *Flash of Unstyled Text/Content* (FOUT/FOUC).
   - B. Link stylesheet dinamis diblokir oleh Content Security Policy (CSP) standar level 3.
   - C. Class selector mencegah browser menjalankan layout recalibration.
   - D. CSS variables tidak bisa dimuat melalui file link stylesheet eksternal.

7. Perhatikan potongan token berikut:
   ```json
   {
     "color-a": { "$value": "{color-b}" },
     "color-b": { "$value": "{color-c}" },
     "color-c": { "$value": "{color-a}" }
   }
   ```
   Bagaimana build engine Style Dictionary menangani struktur ini secara default, dan apa mekanisme arsitektur yang benar untuk mencegahnya?
   - A. Mengabaikan token dan menjadikannya string kosong; gunakan regex validator.
   - B. Mengalami infinite recursion / stack overflow; gunakan algoritma siklus deteksi graf berarah (Directed Graph Cycle Detection) saat tahap inisialisasi graph node.
   - C. Meresolusi nilai menjadi default browser (black); gunakan CSS cascade layers.
   - D. Mengonversi ketiga token menjadi unitless integers; gunakan linter formatting.

8. Dalam audit kepatuhan WCAG 2.2 AA, berapa rasio kontras minimum yang harus dipenuhi antara teks berukuran reguler (di bawah 18pt / 24px) dengan warna latar belakangnya?
   - A. 3:1
   - B. 4.5:1
   - C. 7:1
   - D. 2:1

9. Manakah pernyataan yang BENAR mengenai perbedaan mekanisme handling token antarmuka antara Web CSS Variables dan Jetpack Compose pada Android?
   - A. Web CSS Variables diresolusi secara dinamis di level CSSOM engine runtime browser, sedangkan Jetpack Compose tokens diresolusi melalui immutable Kotlin data classes yang dialirkan via `CompositionLocalProvider`.
   - B. Jetpack Compose memetakan langsung token menjadi CSS property tree di Android rendering pipeline.
   - C. Web CSS Variables mengharuskan full DOM tree rebuild saat tema berubah.
   - D. Jetpack Compose tidak mendukung runtime dynamic switching.

10. Apa tujuan penambahan properti CSS `@layer tokens, base, components, utilities;` pada arsitektur CSS modern design system?
    - A. Mempercepat eksekusi HTTP/3 multiplexing.
    - B. Mengatur spesifisitas CSS (specificity) secara deterministik terlepas dari urutan loading file CSS dalam HTML.
    - C. Mengaktifkan CSS parsing langsung pada Web Worker.
    - D. Menghubungkan CSS engine langsung dengan GPU thread.

---

### Bagian 3: Production Case Scenarios

11. **Skenario 1:** Tim QA menemukan bahwa tombol `Button` utama pada aplikasi mobile Android dan Web memiliki warna yang tampak berbeda secara visual di layar, padahal kedua platform menggunakan token yang sama (`#2563EB`). Setelah dianalisis, Web menggunakan monitor bersertifikasi sRGB sementara perangkat uji Android menggunakan layar OLED dengan color profile DCI-P3 Native. Apa tindakan korektif arsitektural yang paling tepat pada layer build token?
    - A. Mengganti semua token warna menjadi format CMYK.
    - B. Memperbarui pipeline token untuk menghasilkan format warna berbasis Color Space agnostic menggunakan ruang warna Oklch (`color(display-p3 ...)`) dengan fallback sRGB terkalibrasi untuk platform web, dan implementasi ColorSpace mapping eksplisit pada native rendering mobile.
    - C. Mengurangi opacity tombol di mobile sebesar 10%.
    - D. Memaksa browser web dijalankan dalam rendering mode hardware canvas.

12. **Skenario 2:** Aplikasi web enterprise Anda mengalami lonjakan metrik Cumulative Layout Shift (CLS) sebesar 0.28 setiap kali pengguna berganti dari Light Theme ke Dark Theme. Investigasi menunjukkan font-weight tombol berubah dari `400` (Light) menjadi `600` (Dark) untuk mengimbangi ilusi optik latar belakang gelap. Bagaimana menyelesaikan masalah ini dari sudut pandang rekayasa design system tanpa menghilangkan penyesuaian optik weight tersebut?
    - A. Mematikan fitur Dark Theme.
    - B. Menerapkan font-face berbasis Variable Font (`font-variation-settings: 'wght' 600`) dipadukan dengan teknik isolasi text layer menggunakan invisible pseudo-element `::after` yang memuat teks dengan weight tertinggi untuk mem-preserve bounding-box layout tombol secara permanen.
    - C. Memberikan transisi CSS `transition: all 500ms ease;` pada seluruh elemen DOM.
    - D. Mengubah rendering mode aplikasi menjadi SSR (Server Side Rendering) penuh.

13. **Skenario 3:** Sebuah pipeline CI/CD memakan waktu 45 menit hanya untuk memproses repositori design system multi-brand yang memiliki 12.000 token permutasi untuk 8 platform target. Langkah profiling menemukan proses translasi file JSON AST dan pembuatan file individual memicu I/O disk throttling di environment runner. Langkah optimasi arsitektural apa yang harus diimplementasikan?
    - A. Menghapus platform iOS dan Android dari pipeline build otomatis.
    - B. Menulis ulang token ke dalam file single CSS monolitik berukuran besar tanpa parsing AST.
    - C. Mengimplementasikan in-memory build cache (seperti Turborepo / Nx cache) berbasis hash input token JSON dan memparalelkan proses translasi platform via Node.js Worker Threads dengan output writing berbasis buffer stream ke disk.
    - D. Menjalankan pipeline hanya setiap 1 bulan sekali secara manual.

---

### Kunci Jawaban & Evaluasi

#### Bagian 1: Basic
1. **B** — Primitive token menyimpan data mentah, semantic token menyimpan konteks logika/intensi penggunaannya.
2. **C** — Standar DTCG mendefinisikan keyword `$value` (disertai prefix dollar) untuk nilai token.
3. **B** — `rem` berakar pada root font-size pengguna di browser, menjamin hak aksesibilitas jika user memperbesar default font size.
4. **B** — Headless component mengurus event handler, accessibility state (ARIA), dan logic tanpa mengikat styling visual.
5. **C** — Topological sort memastikan seluruh node reference graph diselesaikan dari daun ke akar tanpa referensi menggantung (*unresolved references*).

#### Bagian 2: Intermediate
6. **A** — Mengubah class attribute hanya memicu restyle/repaint pada browser render tree tanpa request HTTP tambahan atau parsing stylesheet dari nol.
7. **B** — Resolusi dependensi melingkar (*cyclic graph*) berujung pada memory overflow; wajib dicegah menggunakan Cycle Detection algorithm sebelum parsing dimulai.
8. **B** — WCAG 2.2 Level AA menetapkan ambang batas rasio minimal 4.5:1 untuk teks standar terhadap latar belakangnya.
9. **A** — CSS variables adalah entitas dynamic CSSOM runtime browser; Jetpack Compose token dioperasikan via type-safe immutable tree injection (`CompositionLocalProvider`).
10. **B** — `@layer` memungkinkan developer menyusun urutan prioritas cascade CSS secara eksplisit, menghapus adu spesifisitas selector (`!important` war).

#### Bagian 3: Production Scenarios
11. **B** — Perbedaan color profile hardware diselesaikan dengan mendefinisikan warna pada perceptual uniform space (Oklch/Display-P3) dan memprogram build pipeline untuk meng-output fallback gamut mapping spesifik platform.
12. **B** — Menggunakan variable font dikombinasikan dengan teknik dummy pseudo-element `::after` mempertahankan layout width elemen, sehingga pergantian font weight tidak mengubah dimensi geometris kontainer dan CLS tetap bernilai 0.
13. **C** — Bottleneck disk I/O dan CPU parsing diselesaikan melalui komputasi paralel worker threads, stream writing, dan dependency hashing caching (arsitektur monorepo modern).

---

## 16. Summary

Arsitektur Design System modern skala enterprise berada di titik temu antara rekayasa perangkat lunak (*software engineering*) dan desain produk (*visual UX*). Pondasi sistem ini bertumpu pada standardisasi token berbasis W3C DTCG yang diperlakukan sebagai kode sumber (Source of Truth) berintegritas tinggi.

Komponen-komponen kritis arsitektur produksi mencakup:
1. **Automated Token Transformation Pipeline:** Menerjemahkan single source JSON menjadi aset native platform (Web, Swift, Kotlin) dengan validasi statis (A11y/APCA contrast assertion).
2. **Headless Component Paradigm:** Memisahkan concerns antara state machine/accessibility (ARIA primitives) dan visual rendering tokens, menjamin reusability tanpa keterikatan visual vendor.
3. **Deterministic CSS Governance:** Pemanfaatan CSS Cascade Layers (`@layer`) dan scoped dynamic custom properties untuk memastikan pergantian tema (multi-brand/dark mode) berjalan dengan zero-CLS dan zero-runtime overhead.

Dengan mengadopsi pola-pola arsitektural ini, organisasi engineering skala besar dapat mengeliminasi *design drift*, menjaga kepatuhan aksesibilitas secara otomatis, dan mempercepat *time-to-market* pengembangan fitur lintas platform.