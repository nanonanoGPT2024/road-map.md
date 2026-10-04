# Bab 06 Module 01: Styling Systems, Design Tokens & CSS Architecture

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Frontend & Mobile Development
*   **Kategori:** 03-Frontend-and-Mobile
*   **Kode Modul:** FE-ARCH-0601
*   **Judul:** Styling Systems, Design Tokens & CSS Architecture
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** Pemahaman mendalam tentang CSS Specificity, Cascade, Box Model, TypeScript modern, Build Tools (Vite/Rollup), AST (Abstract Syntax Tree), dan arsitektur komponen React/Web Components.
*   **Estimasi Waktu Belajar:** 14 Jam (Teori, Bedah Kode, dan Praktik Mandiri)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Merancang Multi-Tier Design Tokens Architecture:** Mengabstraksikan visual primitives menjadi arsitektur token tiga lapis (Global/Primitive, Semantic/System, Component-level) yang mendukung multi-brand, multi-theme, dan density scaling.
2.  **Mengimplementasikan Token Transformation Pipeline:** Membangun automated engine menggunakan Style Dictionary untuk mengekspor token dari JSON/W3C Community Group Format ke berbagai platform target (CSS Custom Properties, TypeScript types, iOS Swift, Android XML/Compose).
3.  **Menguasai Paradigma CSS Modern:** Menganalisis trade-off, mekanisme runtime, dan dampak performa antara CSS-in-JS (Runtime), Utility-First CSS, CSS Modules, dan Zero-Runtime CSS (Compile-time Style Extraction).
4.  **Mengontrol Cascade Melalui Modern Primitives:** Mengimplementasikan `@layer` (Cascade Layers) untuk eliminasi specificity wars, container queries (`@container`) untuk komponen responsif intrinsik, dan CSS `@scope` untuk isolasi visual.
5.  **Mendeteksi & Mengoptimasi Critical Rendering Path:** Menganalisis relasi antara CSS parsing, CSSOM reconstruction, style recalculation, serta dampak arsitektur styling terhadap Core Web Vitals (INP, CLS, LCP).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam skala enterprise, CSS bukan sekadar penata letak atau pemberi warna elemen DOM. CSS adalah **State Machine Visual Deklaratif yang Didistribusikan Secara Global**. Kesalahan terbesar para engineer adalah memperlakukan CSS sebagai bahasa pemrograman tanpa tipe yang terisolasi di level berkas lokal.

```
       PENDEKATAN MONOLITIK / NAIVE                PENDEKATAN SISTEMIK / ENTERPRISE
┌────────────────────────────────────────┐   ┌────────────────────────────────────────┐
│ Elemen UI ditulis manual:              │   │ Design Token Engine (Single Truth):    │
│ .card { background: #1E293B; }         │   │ $surface-card-primary                  │
│                                        │   │                  │                     │
│ Masalah:                               │   │       Transform Pipeline (CI/CD)       │
│ 1. Zero dynamic runtime control        │   │    ┌─────────────┼──────────────┐      │
│ 2. Specificity war (!important hack)   │   │    ▼             ▼              ▼      │
│ 3. Perubahan warna = Find & Replace    │   │ CSS Vars     TS Types      iOS/Android │
│ 4. Dead code menumpuk di bundle        │   │    │             │                     │
│ 5. Runtime CSS-in-JS = CPU spikes      │   │ Zero-Runtime Build Engine (Vanilla/Vite)│
│                                        │   │                  │                     │
│ Hasil: Regresi UI konstan, FOUC, INP   │   │ Kontrak Tipe Kuat, @layer terisolasi,   │
│ melonjak saat DOM kompleks.            │   │ Style Recalculation < 16ms.            │
└────────────────────────────────────────┘   └────────────────────────────────────────┘
```

Pergeseran mental model yang esensial:
*   **Dari "Syle Sheet" ke "Design API":** CSS adalah kontrak publik (API). Perubahan nilai variabel token harus diperlakukan seperti perubahan API kontrak backend: versioned, strictly typed, dan backward-compatible.
*   **Cascade Beralih dari Musuh Menjadi Alat:** Alih-alih merusak inheritance dengan selektor hiper-spesifik (`div#app .wrapper > div.main-card .title`), gunakan `@layer` untuk mengatur prioritas evaluasi style sheet secara deterministik.
*   **Compile-time Over Runtime:** Ekstraksi style sheet statis pada fase kompilasi selalu mengungguli injeksi `<style>` tag dinamis di fase runtime browser jika diukur dari metrik alokasi memori dan garbage collection.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur aliran data menyeluruh dari Design Token hingga perenderan pada browser:

```
[Design Source (Figma Tokens / JSON W3C Spec)]
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 TOKEN TRANSFORMATION PIPELINE               │
│                   (Style Dictionary Engine)                 │
│                                                             │
│   Layer 1: Global Primitives (core.json)                    │
│   Layer 2: Semantic Intent (semantic-light.json, dark.json) │
│   Layer 3: Component Token Mapping                          │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
    [Format: CSS Variables]       [Format: TypeScript AST]
                │                             │
                ▼                             ▼
┌───────────────────────────────┐ ┌───────────────────────────┐
│  CSS Custom Properties File   │ │ Strict Typings & Theme    │
│  :root { --color-bg: ... }    │ │ type ColorTokens = '...'  │
└───────────────┬───────────────┘ └───────────┬───────────────┘
                │                             │
                └──────────────┬──────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               ZERO-RUNTIME / COMPILE-TIME ENGINE            │
│               (Vanilla Extract / CSS Modules)               │
│                                                             │
│  * Type-checking nama variabel vs nilai token               │
│  * Hashing selektor deterministik                           │
│  * Pengelompokan ke dalam @layer cascade                    │
└──────────────────────────────┬──────────────────────────────┘
                               │
               [Vite / Webpack / Rollup Plugin]
                               │
          ┌────────────────────┴────────────────────┐
          ▼                                         ▼
┌───────────────────────────┐             ┌───────────────────┐
│     Critical CSS Chunk    │             │ Defer CSS Chunks  │
│     (Injected into HTML)  │             │ (Loaded on demand)│
└─────────┬─────────────────┘             └─────────┬─────────┘
          │                                         │
          └────────────────────┬────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                       BROWSER PIPELINE                      │
│                                                             │
│ 1. Parse HTML ───► DOM Tree                                 │
│ 2. Parse CSS  ───► CSSOM Tree (Constructed Stylesheet)      │
│ 3. Match Specificity via @layer resolution                 │
│ 4. Compute Dynamic Values (resolve var(--...))              │
│ 5. Tree Synthesis ───► Render Tree                          │
│ 6. Layout (Reflow) ──► Paint ──► Composite                  │
└─────────────────────────────────────────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi Tiga Lapisan Token (Three-Tier Token Architecture)
Tokenisasi yang baik memisahkan definisi absolut dari maksud penggunaan (*intent*):

```
+--------------------------------------------------------------------------+
| 1. GLOBAL / PRIMITIVE TOKENS (Nilai mentah platform-agnostic)             |
|    blue-500 = "#3B82F6";  space-4 = "16px";  font-sans = "Inter, sans"   |
+--------------------------------------------------------------------------+
                                     │
                                     ▼ Diberi arti/konteks fungsional
+--------------------------------------------------------------------------+
| 2. SEMANTIC / SYSTEM TOKENS (Makna fungsional terikat tema/state)         |
|    color-bg-primary     = "{blue-500}"                                    |
|    color-bg-interactive = "{blue-500}"                                    |
|    color-text-danger    = "{red-600}"                                     |
+--------------------------------------------------------------------------+
                                     │
                                     ▼ Dikonsumsi spesifik oleh UI
+--------------------------------------------------------------------------+
| 3. COMPONENT TOKENS (Scope lokal pada bounded context komponen)           |
|    btn-primary-bg-default = "{color-bg-interactive}"                     |
|    btn-primary-bg-hover   = "{blue-600}"                                 |
+--------------------------------------------------------------------------+
```

### 2. Mekanisme Resolusi Cascade Layers (`@layer`)
Standar CSS modern mengatur spesifisitas berdasarkan urutan deklarasi layer, bukan kalkulasi manual bobot selektor (`[id, class, element]`):

$$\text{Prioritas Layer: } \text{Unlayered CSS} > \text{Layer Terakhir} > \dots > \text{Layer Pertama}$$

Jika aturan CSS dideklarasikan dalam `@layer`:
```css
@layer reset, base, components, utilities;
```
Meskipun selektor pada `@layer reset` memiliki bobot spesifisitas tinggi (misal: `#app div.container input[type="text"]`), selektor kelas sederhana pada `@layer utilities` (misal: `.u-hidden`) akan **selalu menang mutlak**, mengeliminasi kebutuhan penggunaan flag `!important`.

*Pengecualian Aturan:* Jika `!important` digunakan di dalam layer, urutannya berbalik secara simetris: layer pertama yang dideklarasikan akan mengalahkan layer berikutnya untuk menjaga integritas reset/debugging.

### 3. CSSOM Injection vs Constructed Stylesheets
*   **Runtime CSS-in-JS Tradisional (e.g., Styled Components v5, Emotion):**
    Membuat tag `<style>` baru atau memanipulasi `styleSheet.insertRule()` di main thread saat komponen di-mount.
    *Konsekuensi:* Memicu Style Recalculation massal, konsumsi memori tinggi akibat duplikasi string CSS di JavaScript heap, dan Thread contention saat rendering ratusan node secara bersamaan.
*   **Modern CSS Architecture (Zero-Runtime & Constructed Stylesheets):**
    Menggunakan `new CSSStyleSheet()` dan `document.adoptedStyleSheets = [sheet]`. Browser mem-parse CSS tepat satu kali pada background thread; multiple custom elements/komponen dapat berbagi satu instance memori stylesheet yang sama secara referensial.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### CSS Specificity Algorithm (W3C Selectors Level 4)
Algoritma evaluasi spesifisitas CSS merepresentasikan bobot selektor sebagai sebuah tuple 3-dimensi: `(A, B, C)`.
*   **A (IDs):** Jumlah selektor ID (misal: `#main`).
*   **B (Classes, Attributes, Pseudo-classes):** Jumlah selektor class (misal: `.btn`), attribute selector (misal: `[type="text"]`), dan pseudo-class (misal: `:hover`, `:nth-child()`). *Catatan:* Pseudo-class `:not()`, `:is()`, dan `:has()` tidak menambah bobot sendiri; bobot dihitung dari argumen terberat di dalamnya.
*   **C (Types, Pseudo-elements):** Jumlah selektor tag HTML (misal: `div`, `span`) dan pseudo-element (misal: `::before`, `::after`).

Nilai inline style attributes (misal: `style="..."`) menempati level prioritas di atas selektor biasa sebelum spesifisitas diperhitungkan, sedangkan aturan `!important` memotong siklus evaluasi normal cascade.

### Runtime vs Zero-Runtime CSS Matrix

| Parameter Evaluasi | Runtime CSS-in-JS (e.g., Emotion) | Utility-First (e.g., Tailwind v3/v4) | Zero-Runtime Type-Safe (e.g., Vanilla Extract) |
| :--- | :--- | :--- | :--- |
| **Parsing Time** | Di Main Thread JS saat runtime | Saat fase Build via PostCSS/Rust compiler | Saat fase Build via Bundler (Vite/Rollup) |
| **JS Bundle Impact** | Tinggi (Parser + Serializer + Styles) | Nol (Hanya string class name di JS) | Nol (Hanya hashing identifier class name) |
| **Dynamic Theming** | Sangat Mudah (via React Context) | Terbatas (harus via CSS Vars runtime) | Native & Cepat (berbasis CSS Custom Props) |
| **Type Safety** | Parsial (sering kali stringly-typed) | Butuh tooling tambahan (Tailwind TS) | **Penuh** (Typescript-first, linting token) |
| **INP Latency** | Rentan regresi saat re-render masif | Mendekati 0ms overhead | 0ms runtime overhead |

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Implementasi arsitektur token modern minimal: dari raw JSON tokens, script translasi token otomatis berbasis Node.js murni, hingga integrasi file CSS dengan deklarasi Cascade Layers.

### 1. Definisi Token JSON
File: `tokens/design-tokens.json`
```json
{
  "primitive": {
    "color": {
      "neutral-100": { "$value": "#F1F5F9", "$type": "color" },
      "neutral-900": { "$value": "#0F172A", "$type": "color" },
      "brand-500": { "$value": "#3B82F6", "$type": "color" },
      "brand-600": { "$value": "#2563EB", "$type": "color" }
    },
    "space": {
      "sm": { "$value": "8px", "$type": "dimension" },
      "md": { "$value": "16px", "$type": "dimension" }
    }
  },
  "semantic": {
    "color": {
      "surface-base": { "$value": "{primitive.color.neutral-100}", "$type": "color" },
      "text-primary": { "$value": "{primitive.color.neutral-900}", "$type": "color" },
      "interactive-default": { "$value": "{primitive.color.brand-500}", "$type": "color" },
      "interactive-hover": { "$value": "{primitive.color.brand-600}", "$type": "color" }
    }
  }
}
```

### 2. Transform Pipeline Sederhana (TypeScript / Node.js)
File: `scripts/build-tokens.ts`
```typescript
import * as fs from 'fs';
import * as path from 'path';

interface TokenNode {
  $value: string;
  $type: string;
}

type TokenGroup = {
  [key: string]: TokenNode | TokenGroup;
};

function resolveReference(ref: string, root: TokenGroup): string {
  const cleanRef = ref.replace(/[{}]/g, '');
  const parts = cleanRef.split('.');
  let current: any = root;
  for (const part of parts) {
    if (!current[part]) {
      throw new Error(`Gagal menyelesaikan referensi token: ${ref}`);
    }
    current = current[part];
  }
  return current.$value;
}

function processTokens(rawJson: TokenGroup): { cssVariables: string[]; tsTypes: string[] } {
  const cssVariables: string[] = [];
  const tsTokens: string[] = [];

  function traverse(obj: TokenGroup, currentPrefix: string) {
    for (const [key, val] of Object.entries(obj)) {
      const nextKey = currentPrefix ? `${currentPrefix}-${key}` : key;
      if (typeof val === 'object' && val !== null && '$value' in val) {
        let value = val.$value;
        if (value.startsWith('{') && value.endsWith('}')) {
          value = resolveReference(value, rawJson);
        }
        cssVariables.push(`  --${nextKey}: ${value};`);
        tsTokens.push(`  '${nextKey}': 'var(--${nextKey})',`);
      } else if (typeof val === 'object' && val !== null) {
        traverse(val as TokenGroup, nextKey);
      }
    }
  }

  traverse(rawJson.semantic as TokenGroup, 'sem');
  return { cssVariables, tsTypes: tsTokens };
}

const rawTokens = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../tokens/design-tokens.json'), 'utf-8'));
const { cssVariables, tsTypes } = processTokens(rawTokens);

const cssOutput = `/* AUTO-GENERATED - JANGAN DIEDIT MANUAL */
@layer tokens {
  :root {
${cssVariables.join('\n')}
  }
}
`;

const tsOutput = `// AUTO-GENERATED - JANGAN DIEDIT MANUAL
export const Tokens = {
${tsTypes.join('\n')}
} as const;

export type TokenKey = keyof typeof Tokens;
`;

fs.writeFileSync(path.resolve(__dirname, '../src/styles/tokens.css'), cssOutput);
fs.writeFileSync(path.resolve(__dirname, '../src/styles/tokens.ts'), tsOutput);
console.log('✅ Pipeline Design Tokens Berhasil Dieksekusi!');
```

### 3. Implementasi CSS dengan Cascade Layers
File: `src/styles/main.css`
```css
/* Inisialisasi urutan prioritas layer secara deterministik */
@layer tokens, reset, components, utilities;

@import './tokens.css';

@layer reset {
  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  
  body {
    background-color: var(--sem-color-surface-base);
    color: var(--sem-color-text-primary);
    font-family: system-ui, -apple-system, sans-serif;
  }
}

@layer components {
  .btn-core {
    background-color: var(--sem-color-interactive-default);
    color: #ffffff;
    padding: 8px 16px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.2s ease-in-out;
  }

  .btn-core:hover {
    background-color: var(--sem-color-interactive-hover);
  }
}

@layer utilities {
  .u-visibility-hidden {
    display: none !important;
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Membedah mekanisme kerja modul kode fundamental di atas:

1.  **Resolusi Indireksi Token (`resolveReference`):**
    ```typescript
    const cleanRef = ref.replace(/[{}]/g, '');
    const parts = cleanRef.split('.');
    ```
    Mekanisme parsing ini mengimplementasikan konsep *Directed Acyclic Graph (DAG)* resolusi token. Jika semantic token mereferensikan `{primitive.color.brand-500}`, transpiler secara rekursif melacak pohon JSON primitif untuk mengekstrak nilai konkret (`#3B82F6`), mencegah terjadinya dead-reference saat file CSS di-generate.
2.  **Immutability Typing (`as const`):**
    ```typescript
    export const Tokens = { ... } as const;
    export type TokenKey = keyof typeof Tokens;
    ```
    Ekspresi `as const` mengunci runtime object menjadi tipe data readonly literals pada compile-time. Tipe `TokenKey` mengekstraksi union literal string (misal: `'sem-color-surface-base' | 'sem-color-interactive-default'`), mengunci pemanggilan token di layer komponen React/TypeScript agar typo dapat terdeteksi langsung oleh LSP IDE.
3.  **Deklarasi Explicit Layer Cascade:**
    ```css
    @layer tokens, reset, components, utilities;
    ```
    Baris ini adalah pilar arsitektur. Urutan penulisan nama layer di awal menentukan hierarki evaluasi browser. Komponen (`components`) dijamin memiliki prioritas lebih tinggi dibanding aturan `reset`, namun class pada `utilities` memiliki prioritas tertinggi.
4.  **Enkapsulasi CSS Variable dalam `:root` di `@layer tokens`:**
    ```css
    @layer tokens {
      :root {
        --sem-color-surface-base: #F1F5F9;
      }
    }
    ```
    Variabel dikurung dalam layer `tokens`. Pendekatan ini memastikan bahwa apabila aplikasi menginjeksikan layer mikro-frontend baru, nilai variabel global ini tidak akan memicu tabrakan selektor (*collision*) yang tak terkontrol.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks Kasus Enterprise
**Perusahaan:** FinTech Global "ApexPay"
**Masalah:** 
ApexPay memiliki portal SaaS perbankan dengan arsitektur Micro-Frontend (MFE) yang terdiri dari 14 tim terpisah. 
1.  **Specificity Hell:** Tim Core UI merilis Button dengan class `.btn-primary`. Tim Pembayaran menimpanya dengan `#app-container .payment-box .btn-primary { background: green !important; }`. Saat desain berganti, regresi tampilan terjadi di 40% aplikasi.
2.  **Performance Degradation:** Tim Checkout menggunakan library CSS-in-JS runtime (Emotion). Setiap kali pengguna mengetik jumlah uang (re-render cepat per-keystroke), runtime CSS-in-JS mengevaluasi ulang style, menginjeksi tag `<style>` baru ke dalam `<head>`. Akibatnya, nilai **Interaction to Next Paint (INP)** anjlok hingga 380ms (kategori *Poor*), menyebabkan freeze visual.
3.  **Multi-Theming Failure:** Portal harus memiliki tema berbeda untuk Enterprise White-Label Partner, namun tim kesulitan karena warna di-*hardcode* di puluhan file SASS dan konfigurasi Tailwind yang saling tumpang tindih.

### Solusi Arsitektural Staff Engineer
1.  Mengintegrasikan Style Dictionary dengan arsitektur multi-brand token.
2.  Migrasi penuh dari Runtime CSS-in-JS ke Zero-Runtime Engine (Vanilla Extract) yang digabungkan dengan CSS Custom Properties native.
3.  Mengatur isolasi gaya antarmuka mikro-frontend via Modern CSS: `@layer` untuk specificity deterministic control dan `@container` queries untuk komponen form payment.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah arsitektur styling zero-runtime yang diterapkan untuk platform multi-brand ApexPay menggunakan vanilla-extract dan CSS variables native.

### 1. Engine Kontrak Tema (Zero-Runtime Contract)
File: `src/theme/contract.css.ts`
```typescript
import { createThemeContract } from '@vanilla-extract/css';

// Kontrak wajib yang harus dipenuhi oleh semua brand (Design API Contract)
export const vars = createThemeContract({
  color: {
    background: null,
    surface: null,
    text: null,
    brandPrimary: null,
    brandActive: null,
  },
  space: {
    xs: null,
    sm: null,
    md: null,
    lg: null,
  },
  typography: {
    fontFamily: null,
    fontSizeSm: null,
    fontSizeBase: null,
  }
});
```

### 2. Implementasi Tema Brand A (Retail Theme)
File: `src/theme/retail.css.ts`
```typescript
import { createTheme } from '@vanilla-extract/css';
import { vars } from './contract.css';

export const retailThemeClass = createTheme(vars, {
  color: {
    background: '#F8FAFC',
    surface: '#FFFFFF',
    text: '#0F172A',
    brandPrimary: '#0284C7',
    brandActive: '#0369A1',
  },
  space: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
  },
  typography: {
    fontFamily: 'Inter, system-ui, sans-serif',
    fontSizeSm: '12px',
    fontSizeBase: '14px',
  }
});
```

### 3. Implementasi Tema Brand B (Enterprise Dark Theme)
File: `src/theme/enterprise.css.ts`
```typescript
import { createTheme } from '@vanilla-extract/css';
import { vars } from './contract.css';

export const enterpriseThemeClass = createTheme(vars, {
  color: {
    background: '#0B0F17',
    surface: '#1E293B',
    text: '#F8FAFC',
    brandPrimary: '#10B981',
    brandActive: '#059669',
  },
  space: {
    xs: '6px',
    sm: '12px',
    md: '20px',
    lg: '32px',
  },
  typography: {
    fontFamily: '"JetBrains Mono", monospace',
    fontSizeSm: '13px',
    fontSizeBase: '15px',
  }
});
```

### 4. Definisi Layer dan Style Komponen Modern
File: `src/components/PaymentCard.css.ts`
```typescript
import { style, globalLayer } from '@vanilla-extract/css';
import { vars } from '../theme/contract.css';

// Deklarasi cascade layers
export const resetLayer = globalLayer('reset');
export const componentLayer = globalLayer('components');

export const container = style({
  '@layer': {
    [componentLayer]: {
      containerType: 'inline-size',
      containerName: 'paymentCardContainer',
      width: '100%',
      maxWidth: '600px',
      margin: '0 auto',
    }
  }
});

export const card = style({
  '@layer': {
    [componentLayer]: {
      backgroundColor: vars.color.surface,
      color: vars.color.text,
      padding: vars.space.md,
      borderRadius: '8px',
      border: `1px solid ${vars.color.brandPrimary}`,
      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
      display: 'flex',
      flexDirection: 'column',
      gap: vars.space.sm,
      fontFamily: vars.typography.fontFamily,
      transition: 'transform 0.15s ease',

      // Modern Container Queries
      '@container': {
        'paymentCardContainer (min-width: 450px)': {
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: vars.space.lg,
        }
      }
    }
  }
});

export const submitButton = style({
  '@layer': {
    [componentLayer]: {
      backgroundColor: vars.color.brandPrimary,
      color: '#FFFFFF',
      padding: `${vars.space.sm} ${vars.space.md}`,
      fontSize: vars.typography.fontSizeBase,
      fontWeight: 600,
      border: 'none',
      borderRadius: '6px',
      cursor: 'pointer',
      outline: 'none',
      ':hover': {
        backgroundColor: vars.color.brandActive,
      },
      ':focus-visible': {
        boxShadow: `0 0 0 3px ${vars.color.brandActive}`,
      }
    }
  }
});
```

### 5. Komponen React Fungsional Produksi
File: `src/components/PaymentCard.tsx`
```tsx
import React, { useState } from 'react';
import * as styles from './PaymentCard.css';

interface PaymentCardProps {
  amount: number;
  currency: string;
  onExecute: () => Promise<void>;
}

export const PaymentCard: React.FC<PaymentCardProps> = ({ amount, currency, onExecute }) => {
  const [isProcessing, setIsProcessing] = useState<boolean>(false);

  const handlePayment = async () => {
    try {
      setIsProcessing(true);
      await onExecute();
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className={styles.container}>
      <article className={styles.card} role="region" aria-label="Ringkasan Pembayaran">
        <div>
          <span style={{ fontSize: '0.85em', opacity: 0.8 }}>Total Tagihan</span>
          <h2 style={{ fontSize: '1.5em', margin: '4px 0' }}>
            {currency} {amount.toLocaleString()}
          </h2>
        </div>
        <button
          className={styles.submitButton}
          onClick={handlePayment}
          disabled={isProcessing}
          aria-busy={isProcessing}
        >
          {isProcessing ? 'Memproses...' : 'Bayar Sekarang'}
        </button>
      </article>
    </div>
  );
};
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

Memilih arsitektur styling memerlukan evaluasi trade-off teknik secara komprehensif:

```
                  SKALABILITAS TIM & KONTRAK DESAIN
                               ▲
                               │     * Vanilla Extract
                               │       (Compile-time, Zero-runtime, Strict Typing)
                               │
                               │     * CSS Modules
                               │       (Simple, Isolatip, Less Structured)
                               │
                               │     * Tailwind CSS
                               │       (High Velocity, No Context Switching, Utility Monolith)
                               │
                               │     * Styled Components / Emotion
                               │       (High Dynamic Flexibility, Memory Leak, INP Hazard)
                               │
                               └────────────────────────────────────────►
                                PERFORMA RUNTIME & EFISIENSI RENDER (LOW LATENCY)
```

| Dimensi | Tailwind CSS | Vanilla Extract | Emotion / Styled Components | CSS Modules |
| :--- | :--- | :--- | :--- | :--- |
| **Parsing Cost** | Minimal (Atomic CSS diparsing sekali) | Sangat Cepat (Output pure `.css` statis) | Lambat (JS parse styling + dynamic injection) | Sangat Cepat (CSS Statis native) |
| **Bundle Scalability** | Mencapai kurva datar (*plateaus*) | Linear seiring bertambahnya komponen | Linear dan menggandakan ukuran bundle JS | Linear seiring bertambahnya komponen |
| **Strict Design System Typing** | Rentan (*arbitrary values* `w-[321px]` sering bocor) | Mutlak (*Strict typing contract via TS*) | Menengah (bergantung pada arsitektur programmer) | Lemah (Tidak ada validasi tipe native token) |
| **Container Queries Integration** | Baik (via arbitrary / dynamic class) | Sangat Baik (Native declaration terstruktur) | Menengah | Sempurna (Native syntax CSS) |
| **Konteks Penggunaan Optimal** | Web app bervelositas tinggi, admin panel | Enterprise UI Core Library, Multi-brand SaaS | Dynamic internal tools mikro-skala | Aplikasi monolitik dengan arsitektur klasik |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. CSS Variable Scope Leakage pada Shadow DOM / Micro-frontends
*   **Kasus:** Mendefinisikan token CSS di `:root` pada Micro-Frontend A akan menimpa `:root` Micro-Frontend B jika berada dalam satu dokumen window.
*   **Mitigasi:** Kurung scope token pada container induk MFE, jangan di `:root`:
    ```css
    /* Hindari di MFE: */
    :root { --color-primary: #ff0000; }

    /* Gunakan Bounded Scope: */
    #mfe-checkout-root, .mfe-checkout-scope {
      --color-primary: #ff0000;
    }
    ```

### 2. Broken Container Queries Akibat Container Type Tanpa Dimensi Axis
*   **Kasus:** Menggunakan `container-type: inline-size` pada elemen yang ukuran lebarnya bergantung secara intrinsik pada kontennya (*shrink-to-fit* seperti elemen `display: inline-block` tanpa lebar pasti).
*   **Dampak:** Terjadi *Infinite Layout Loop* di mana browser mengevaluasi lebar elemen -> memicu container queries -> mengubah ukuran elemen -> layout dievaluasi ulang -> browser crash / freeze.
*   **Mitigasi:** Selalu deklarasikan lebar yang deterministik (`width: 100%`) atau pastikan container berada di dalam Block Formatting Context (BFC).

### 3. FOUC (Flash of Unstyled Content) saat Deferring CSS
*   **Kasus:** Memisahkan CSS terlalu agresif ke dalam asynchronous chunking dapat membuat dokumen HTML ter-render sebelum CSS Custom Properties selesai diparsing.
*   **Mitigasi:** Design Token CSS yang berisi variabel global (`tokens.css`) WAJIB di-*inline*-kan langsung di dalam blok `<head>` atau dijadikan Critical Path CSS blocking, sedangkan CSS komponen individual dapat di-defer.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan Nilai Arbitrary untuk Menghindari Design Tokens
*   ❌ **Salah:** Menggunakan styling instan langsung di file:
    ```tsx
    // Tailwind
    <div className="bg-[#123456] p-[13px]">...</div>
    ```
*   ✅ **Benar:** Memperluas definisi semantic token melalui konfigurasi terpusat:
    ```tsx
    <div className="bg-surface-elevated p-spacing-card">...</div>
    ```
    *Alasan:* Nilai arbitrary merusak kemampuan themer otomatis (misal: Dark Mode, High Contrast Mode) dan menyebabkan fragmentasi desain visual.

### 2. Menyalahgunakan Flag `!important` untuk Memenangkan Specificity
*   ❌ **Salah:**
    ```css
    .card-title {
      font-size: 1.5rem !important;
    }
    ```
*   ✅ **Benar:** Gunakan arsitektur `@layer` untuk memetakan prioritas selektor:
    ```css
    @layer components {
      .card-title {
        font-size: 1.5rem;
      }
    }
    ```
    *Alasan:* `!important` merusak perilaku natural Cascade engine dan membuat modifikasi style sheet di masa depan hampir mustahil dilakukan tanpa menambahkan rantai `!important` yang lebih panjang.

### 3. Mengkalkulasi CSS Variables Runtime Tanpa Fallback
*   ❌ **Salah:**
    ```css
    color: var(--brand-color);
    ```
*   ✅ **Benar:**
    ```css
    color: var(--brand-color, #0F172A);
    ```
