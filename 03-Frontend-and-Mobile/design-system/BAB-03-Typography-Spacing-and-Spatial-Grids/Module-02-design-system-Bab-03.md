# Kurikulum Enterprise Design System: 03-Frontend-and-Mobile
## BAB-03: Typography, Spacing, and Spatial Grids
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Engineeer / Design System Architect diharapkan mampu:
- Merancang dan mengimplementasikan **Fluid Modular Typography Engine** menggunakan fungsi matematika CSS (`clamp()`, `calc()`) yang terikat langsung ke token skala rasio dinamis tanpa memicu *Cumulative Layout Shift* (CLS).
- Mengeliminasi distorsi vertikal tipografi melalui teknik **Cap-Height / Baseline Grid Alignment** menggunakan metrik font internal (*ascent*, *descent*, *units-per-em*) via *CSS Font Metrics Overrides* (`@font-face` overrides) dan properti modern (`text-box-trim` / `text-box-edge`).
- Membangun **Multi-Tier Spatial Grid Engine** berbasis *CSS Subgrid* dan *CSS Container Queries* (`@container`) yang mendukung densitas dinamis (*compact*, *comfortable*, *spacious*) untuk platform SaaS multitenan enterprise.
- Mengotomatisasi pipeline kompilasi token tipografi dan spasial lintas-platform (Web, iOS, Android) menggunakan AST transformator dan *Style Dictionary* dengan mitigasi pembulatan sub-piksel (*sub-pixel rendering rounding errors*).
- Menjamin kepatuhan penuh terhadap kriteria aksesibilitas **WCAG 2.2 Level AAA** khusus kriteria *Resize Text* (1.4.4), *Text Spacing* (1.4.12), dan *Target Size (Minimum)* (2.5.8).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Foundational CSS Layouts**: Pemahaman mendalam tentang *Block Formatting Context* (BFC), *CSS Grid Level 2*, *Flexbox Layout Model*, dan *CSS Custom Properties Inheritance Cascade*.
- **Font Rendering Pipeline**: Pemahaman tentang Rasterisasi Tipografi (FreeType, CoreText, DirectWrite), *Font Execution Stack* (WOFF2, OpenType Tables seperti `OS/2`, `hhea`, `head`), dan siklus *Font Loading API*.
- **Token Architecture**: Pengetahuan komprehensif mengenai *W3C Design Token Community Group (DTCG) specification format*.
- **Tooling Environment**: Pengalaman tingkat lanjut dengan TypeScript, PostCSS/Tailwind internals, dan NodeJS file-system AST compilation tools.

---

### 3. Concept & Internal Architecture

Implementasi tipografi dan sistem spasial enterprise membutuhkan transisi dari pendekatan statis berbasis piksel menuju **arsitektur spasial matematika deterministik**.

```
+-------------------------------------------------------------------------------+
|                       DESIGN TOKEN SOURCE OF TRUTH (JSON)                     |
|        typography.tokens.json             |            spacing.tokens.json    |
+-------------------------------------------+-----------------------------------+
                     |                                       |
                     v                                       v
+-------------------------------------------------------------------------------+
|                        METRIC COMPILATION & AST ENGINE                        |
|  - Font Metrics Parser (capHeight, xHeight)  | - Sub-pixel Rounding Engine    |
|  - Fluid Clamping Generator (Min/Max/Slope)  | - Density Matrix Normalizer    |
+-------------------------------------------------------------------------------+
                     |                                       |
                     +-------------------+-------------------+
                                         |
                                         v
+-------------------------------------------------------------------------------+
|                        PRODUCTION RUNTIME LAYER (CSS)                         |
|  - Root CSS Variables (Fluid Scales, Metric Compensation Variables)           |
|  - Font Metric Overrides (@font-face: ascent-override, line-gap-override)     |
|  - Global Reset & Spatial Compositor (Subgrid + Container Queries)            |
+-------------------------------------------------------------------------------+
```

#### A. Fluid Typography Mathematical Mechanics
Tipografi adaptif tidak boleh bergantung pada *media query breakpoint cascading* yang diskrit dan memicu *layout thrashing*. Sebaliknya, sistem menggunakan fungsi linear *clamping* matematika:

$$\text{Ideal Value} = y_1 + \left( \frac{y_2 - y_1}{x_2 - x_1} \right) \times (100\text{vw} - x_1)$$

Di mana:
- $x_1$: *Viewport width* minimum (misal: `320px` atau `20rem`)
- $x_2$: *Viewport width* maksimum (misal: `1440px` atau `90rem`)
- $y_1$: Ukuran font minimum pada $x_1$
- $y_2$: Ukuran font maksimum pada $x_2$
- Slope ($S$): $\frac{y_2 - y_1}{x_2 - x_1}$
- Intersep $y$ ($I$): $y_1 - (S \times x_1)$

Dalam implementasi CSS:
```css
font-size: clamp(min_val, (I)rem + (S * 100)vw, max_val);
```

#### B. Font Metrics Normalization & Baseline Rhythm
Secara default, browser merender teks dengan kotak pembatas (*bounding box*) bawaan font yang mencakup *half-leading* ekstra yang ditentukan oleh tabel font `hhea` (Mac OS) dan `OS/2` (Windows). Ketidakkonsistenan ini merusak sistem grid 4px/8px vertikal.

Untuk menghapus *half-leading* tanpa JavaScript runtime, arsitektur enterprise menggunakan rasio metrik font terhitung:
1. **$A$ (Ascender Units)**, **$D$ (Descender Units)**, **$C$ (Cap-Height Units)**, **$U$ (Units Per Em)** diekstrak langsung dari file binary font OTF/WOFF2.
2. Hitung:
   $$\text{Ascent Override} = \left(\frac{A}{U}\right) \times 100\%$$
   $$\text{Cap-to-Top Offset} = \frac{(A - C)}{U}$$
   $$\text{Baseline-to-Bottom Offset} = \frac{|D|}{U}$$
3. Kompensasi vertikal diaplikasikan via CSS custom properties untuk memangkas *space-above-cap* dan *space-below-baseline*.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Naive) | Pendekatan Enterprise Architecture |
| :--- | :--- | :--- |
| **Penskalaan Tipografi** | Nilai statis per breakpoint (`px` / `rem` kaku via `@media`). | Skala modular matematis berbasis fungsi `clamp()` kontinu. |
| **Vertical Alignment** | Margin/padding perkiraan berbasis visual "eye-balling". | *Optical cap-height alignment* berbasis metrik font ekstraksi binari. |
| **Sistem Spasial** | Grid global statis 12-kolom terikat *viewport width*. | *Fluid micro-grids* memanfaatkan *Container Queries* dan *CSS Subgrid*. |
| **Kompensasi Font Swap** | FOIT/FOUT tanpa mitigasi layout shift. | `@font-face` overrides (`size-adjust`, `ascent-override`) menghasilkan 0 CLS. |
| **Manajemen Densitas** | Duplikasi class utilitas (e.g., `p-2`, `p-4`, `table-dense`). | *Contextual Spatial Density Switching* via inheritance token CSS variabel. |

---

### 5. How (Workflow Detail)

Alur produksi end-to-end dari token hingga render rasterisasi:

```
[Design Tool (Figma)]
         |
         v (Export Tokens via REST API)
[Raw JSON Design Tokens]
         |
         +---> [Font Metric Extractor (Node + opentype.js)]
         |              |
         |              v (Extract: capHeight, ascent, descent, unitsPerEm)
         |     [Computed Metric Definitions]
         |              |
         v              v
[Token Compiler Engine (Style Dictionary)]
         |
         +---> CSS Output: Variable Scales, Cap-Trims, Fluid Clamps
         +---> TypeScript Output: Const maps, layout engine contracts
         +---> JSON Output: Android Compose & iOS Swift definitions
         |
         v
[Production Component Library]
         |
         +---> Core Primitives: Box, Text, Stack, Cluster, Grid, Container
```

1. **Ekstraksi**: Script CI/CD memindai font binaries yang digunakan dan membaca tabel OpenType untuk menentukan konstanta pemotongan (*trim offsets*).
2. **Kompilasi**: Engine menghitung fungsi polinomial untuk ukuran tipografi minimum dan maksimum menggunakan rasio modular (e.g., Major Third: 1.25, Perfect Fourth: 1.333).
3. **Penyuntikan Runtime**: Nilai disuntikkan ke `:root` sebagai CSS custom properties, siap dikonsumsi langsung atau diabstraksikan via framework layout primitives.

---

### 6. Analogy & Diagram ASCII

Bayangkan tipografi konvensional seperti lukisan yang diletakkan di dalam bingkai kaca dengan ketebalan spons transparan yang acak di sisi atas dan bawahnya. Saat Anda mencoba meratakan bingkai tersebut ke rak buku (spatial grid), spons tersebut membuat lukisan tampak miring atau tidak sejajar, meskipun bingkai fisiknya menyentuh garis rak.

Arsitektur produksi bertindak seperti pemotong pisau presisi (*laser trimmer*) yang membuang spons transparan tersebut, sehingga batas visual huruf (puncak huruf kapital dan garis dasar bawah) menyentuh rak secara presisi matematika.

```
Konvensional (Font Bounding Box dengan White-space bawaan):
+---------------------------------------+  <- CSS Bounding Box Top
|         [Half-Leading Space]          |
|   +-------------------------------+   |
|   |  ####  #####  #####  #   #    |   |  <- Cap Height Level (Puncak Huruf)
|   |  #     #   #  #   #  #   #    |   |
|   |  ####  #####  #####  #####    |   |
|   |     #  #      #   #  #   #    |   |
|   |  ####  #      #   #  #   #    |   |  <- Baseline Level (Dasar Huruf)
|   +-------------------------------+   |
|         [Descent / Leading Space]     |
+---------------------------------------+  <- CSS Bounding Box Bottom
    * Spasi bawaan menyebabkan margin/padding tidak akurat pada grid! *

Enterprise Metric-Trimmed Engine:
=========================================  <- Spatial Grid Line
+---------------------------------------+  <- Cap Height sejajar sempurna
|  ####  #####  #####  #   #            |
|  #     #   #  #   #  #   #            |
|  ####  #####  #####  #####            |
|     #  #      #   #  #   #            |
|  ####  #      #   #  #   #            |
+---------------------------------------+  <- Baseline sejajar sempurna
=========================================  <- Spatial Grid Line
```

---

### 7. Simple Example & Practical Example

#### A. Advanced Math Generator (TypeScript Compilation Utility)
Generator untuk kalkulasi *fluid typography* dan *font overrides* yang dieksekusi pada saat proses *build*.

```typescript
// scripts/generators/spatial-math.ts
export interface FluidTokenConfig {
  minScreen: number; // in px
  maxScreen: number; // in px
  minSize: number;   // in px
  maxSize: number;   // in px
  rootFontSize?: number; // default 16
}

export function generateFluidClamp(config: FluidTokenConfig): string {
  const { minScreen, maxScreen, minSize, maxSize, rootFontSize = 16 } = config;
  
  const minScreenRem = minScreen / rootFontSize;
  const maxScreenRem = maxScreen / rootFontSize;
  const minSizeRem = minSize / rootFontSize;
  const maxSizeRem = maxSize / rootFontSize;

  const slope = (maxSizeRem - minSizeRem) / (maxScreenRem - minScreenRem);
  const intersection = -minScreenRem * slope + minSizeRem;

  const slopeVw = Number((slope * 100).toFixed(4));
  const intersectionRem = Number(intersection.toFixed(4));
  const minSizeFormatted = Number(minSizeRem.toFixed(4));
  const maxSizeFormatted = Number(maxSizeRem.toFixed(4));

  return `clamp(${minSizeFormatted}rem, ${intersectionRem}rem + ${slopeVw}vw, ${maxSizeFormatted}rem)`;
}

export interface FontMetrics {
  unitsPerEm: number;
  ascent: number;
  descent: number;
  capHeight: number;
}

export function calculateFontOverrides(metrics: FontMetrics) {
  const { unitsPerEm, ascent, descent } = metrics;
  const ascentOverride = (ascent / unitsPerEm) * 100;
  const descentOverride = (Math.abs(descent) / unitsPerEm) * 100;
  const lineGapOverride = 0;

  return {
    ascentOverride: `${ascentOverride.toFixed(2)}%`,
    descentOverride: `${descentOverride.toFixed(2)}%`,
    lineGapOverride: `${lineGapOverride}%`,
  };
}
```

#### B. Production CSS Architecture: Tokens & Engine
Sistem CSS lengkap dengan deklarasi *font-face metric compensation*, variabel fluid, dan engine *leading-trim*.

```css
/* styles/tokens.css */
:root {
  /* Baseline Grid Units */
  --grid-unit: 0.25rem; /* 4px base */
  
  /* Fluid Spacing Scale (Scale Factor: Perfect Fourth) */
  --space-1: calc(var(--grid-unit) * 1);  /* 4px */
  --space-2: calc(var(--grid-unit) * 2);  /* 8px */
  --space-3: calc(var(--grid-unit) * 3);  /* 12px */
  --space-4: calc(var(--grid-unit) * 4);  /* 16px */
  --space-6: calc(var(--grid-unit) * 6);  /* 24px */
  --space-8: calc(var(--grid-unit) * 8);  /* 32px */
  --space-12: calc(var(--grid-unit) * 12);/* 48px */
  --space-16: calc(var(--grid-unit) * 16);/* 64px */

  /* Density Modifiers */
  --density-ratio: 1;
  --space-dense-1: calc(var(--space-1) * var(--density-ratio));
  --space-dense-2: calc(var(--space-2) * var(--density-ratio));
  --space-dense-4: calc(var(--space-4) * var(--density-ratio));

  /* Fluid Typography Declarations: Calculated 320px -> 1440px */
  --font-size-sm: clamp(0.75rem, 0.7143rem + 0.1786vw, 0.875rem);
  --font-size-base: clamp(1rem, 0.9643rem + 0.1786vw, 1.125rem);
  --font-size-lg: clamp(1.25rem, 1.1786rem + 0.3571vw, 1.5rem);
  --font-size-xl: clamp(1.5625rem, 1.4196rem + 0.7143vw, 2.0625rem);
  --font-size-2xl: clamp(1.9531rem, 1.6853rem + 1.3393vw, 2.8906rem);

  /* Inter Font Metrics Constants */
  --font-inter-upm: 2048;
  --font-inter-ascent: 1984;
  --font-inter-descent: -494;
  --font-inter-cap: 1490;

  /* Metric Offsets */
  --inter-cap-offset: calc((var(--font-inter-ascent) - var(--font-inter-cap)) / var(--font-inter-upm));
  --inter-desc-offset: calc(abs(var(--font-inter-descent)) / var(--font-inter-upm));
}

/* Densitas Mode: Compact / Spacious Control */
[data-density="compact"] {
  --density-ratio: 0.75;
}

[data-density="spacious"] {
  --density-ratio: 1.5;
}

/* Zero-CLS Fallback Font Matching */
@font-face {
  font-family: 'Inter-Fallback';
  src: local('Arial');
  ascent-override: 96.88%;
  descent-override: 24.12%;
  line-gap-override: 0.00%;
  size-adjust: 100.2%;
}

@font-face {
  font-family: 'Enterprise-Inter';
  font-style: normal;
  font-weight: 100 900;
  font-display: swap;
  src: url('/fonts/inter-variable.woff2') format('woff2-variations');
}
```

#### C. React Production Component: Typography Primitive with Text-Trim Engine
Primitive komponen tipografi dengan fallback *optical-trimming* untuk browser yang belum mendukung spesifikasi CSS `text-box-trim`.

```tsx
// components/primitives/Text.tsx
import React, { ElementType, CSSProperties } from 'react';

type TextVariant = 'sm' | 'base' | 'lg' | 'xl' | '2xl';

interface TextProps {
  as?: ElementType;
  variant?: TextVariant;
  children: React.ReactNode;
  trim?: boolean;
  className?: string;
  style?: CSSProperties;
}

export const Text: React.FC<TextProps> = ({
  as: Component = 'p',
  variant = 'base',
  children,
  trim = true,
  className = '',
  style,
}) => {
  const computedStyle: CSSProperties = {
    fontFamily: "'Enterprise-Inter', 'Inter-Fallback', sans-serif",
    fontSize: `var(--font-size-${variant})`,
    lineHeight: 1.5,
    margin: 0,
    ...style,
  };

  if (!trim) {
    return <Component style={computedStyle} className={className}>{children}</Component>;
  }

  return (
    <Component
      style={{
        ...computedStyle,
        /* Properti masa depan native CSS */
        // @ts-expect-error - Future CSS property
        textBoxTrim: 'both',
        textBoxEdge: 'cap alphabetic',
        /* Fallback Pseudo Optical Leading Trim via variables */
        position: 'relative',
      }}
      className={`metric-trimmed-text ${className}`}
    >
      <span
        style={{
          display: 'block',
          marginTop: 'calc(var(--inter-cap-offset) * -0.5em)',
          marginBottom: 'calc(var(--inter-desc-offset) * -0.5em)',
        }}
      >
        {children}
      </span>
    </Component>
  );
};
```

#### D. Production CSS Subgrid Container Implementation
Menjaga konsistensi ritme horizontal dan vertikal modular pada hierarki komponen bersarang (*nested components*).

```css
/* styles/spatial-grid.css */
.data-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 20rem), 1fr));
  grid-auto-rows: auto;
  gap: var(--space-dense-4);
}

.data-card {
  display: grid;
  /* Subgrid mewarisi track baris grid induk agar header dan footer kartu selaras */
  grid-row: span 3;
  grid-template-rows: subgrid;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: var(--space-dense-4);
  row-gap: var(--space-dense-2);
}

.data-card-header {
  grid-row: 1;
  align-self: start;
}

.data-card-body {
  grid-row: 2;
  align-self: start;
}

.data-card-actions {
  grid-row: 3;
  align-self: end;
  padding-top: var(--space-dense-2);
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Sebuah platform analitik finansial multitenan skala enterprise (*FinTech Platform*) mengalami degradasi visual dan performa:
1. **Layout Thrashing & Cumulative Layout Shift (CLS)** sebesar `0.38` saat runtime, dipicu oleh keterlambatan pengunduhan font web berukuran besar (2.4MB) yang merender font fallback OS (Times New Roman / Arial) dengan metrik vertikal yang berbeda drastis.
2. **Kerapatan Ruang Antarmuka**: Pelanggan institusional menuntut tabel data dengan kepadatan tinggi (*compact mode*), sementara pengguna ritel membutuhkan mode santai (*comfortable*). Perubahan densitas ini sebelumnya dikelola dengan menambahkan ratusan class overrides CSS kaku yang menaikkan ukuran bundle CSS hingga `450KB`.
3. **Penyimpangan Spasial Micro-alignment**: Teks label metrik keuangan tidak sejajar secara optik dengan grafik SVG dan ikon UI, menyebabkan tampilan tampak tidak seimbang (*ragged edge*).

#### Solusi Arsitektural
1. **Penerapan Dynamic Metric Fallback Matching**:
   Menggunakan *Font Metrics Parser* berbasis build pipeline untuk memetakan metrik font fallback lokal (`Arial` pada Windows, `Helvetica Neue` pada macOS, `Liberation Sans` pada Linux) agar identik secara vertikal dengan font primer korporat melalui properti CSS `@font-face` override (`ascent-override: 95.2%`, `descent-override: 23.8%`, `size-adjust: 102.1%`).
2. **Dynamic Contextual Tokens via CSS Custom Properties**:
   Mengganti arsitektur stylesheet ganda dengan penyuntikan token spasial modular level akar (`--grid-unit`) yang merespons atribut data konteks (`[data-density="compact"]`).
3. **Cap-height Text-box Scaffolding**:
   Membuat komponen tata letak dasar yang memangkas *half-leading* font sehingga baseline data teks sejajar secara matematis dengan garis grid kanvas grafik visual.

#### Hasil Metrik Produksi
- **CLS (Cumulative Layout Shift)**: Turun dari `0.38` menjadi `0.002` (peningkatan 99.4%, melewati batas *Good* Web Vitals).
- **CSS Bundle Size**: Berkurang dari `450KB` menjadi `48KB` (penurunan 89.3%) karena redundansi class modifier dieliminasi oleh CSS variable inheritance cascade.
- **Render Jank Frame-rate**: Stabil di 60fps konstan saat transisi pengalihan tema dan perubahan kerapatan data.

---

### 9. Trade-offs

| Pendekatan / Teknik | Keuntungan | Kerugian & Batasan | Mitigasi Arsitektural |
| :--- | :--- | :--- | :--- |
| **CSS Subgrid Spatial Layouts** | Menjamin penyelarasan cross-card tanpa batas wrapper; baris otomatis sejajar. | Browser lama (Safari <16, browser embedded WebView lama) tidak mendukung. | Sediakan fallback degradasi anggun menggunakan Flexbox display dengan explicit min-height. |
| **Fluid Scales (`clamp()`)** | Menghilangkan puluhan breakpoint kaku; responsif halus di semua viewport. | Menghitung nesting scale menjadi kompleks; sulit bagi desainer membaca nilai di inspektor. | Bangun PostCSS plugin atau helper inspector yang memetakan nilai clamp kembali ke alias token. |
| **Font Metric Overrides** | Mengeliminasi CLS sepenuhnya saat webfont terlambat dimuat. | Bergantung pada akurasi komputasi metrik; beda OS terkadang memicu pembulatan sub-piksel ganjil. | Kalibrasi metrik menggunakan tes regresi visual berbasis Playwright headless Chromium. |
| **Optical Margin Trimming (Negative Spacing)** | Menghapus whitespace bawaan; perataan visual 100% presisi. | Berisiko memotong glyph bahasa tertentu yang memiliki diakritik ekstrim (e.g., Vietnam, Arab). | Buat bypass pengecualian locale via properti `:lang()` yang menonaktifkan trim otomatis. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Menggunakan Unit Viewport Murni (`vw`) Tanpa Nilai Dasar
```css
/* SALAH: Membatalkan zoom aksesibilitas pengguna (WCAG 1.4.4 Violation) */
font-size: 2.5vw;

/* BENAR: Menggunakan clamp yang selalu menyertakan unit berbasis 'rem' */
font-size: clamp(1.25rem, 0.95rem + 1.5vw, 2.25rem);
```
*Dampak*: Saat pengguna tunanetra memperbesar teks menggunakan *browser zoom* (200%), unit murni `vw` tidak akan membesar karena ukuran *viewport* browser tidak berubah. Mengintegrasikan unit `rem` memastikan teks membesar saat *root base rem* dinaikkan.

#### Kesalahan 2: Mengabaikan Fractional Sub-pixel Rounding pada Grid Spacing
Pada layar resolusi rendah atau penskalaan DPI ganjil (seperti 125% atau 150% pada Windows OS), kalkulasi modular seperti `1.333rem` dapat menghasilkan nilai piksel pecahan (misal: `21.328px`). Beberapa mesin perenderan membulatkan ke bawah (*floor*), beberapa membulatkan ke atas (*ceil*), memicu keretakan 1px pada perbatasan grid.

```css
/* SALAH: Kalkulasi rentan pembulatan sub-piksel */
margin-bottom: calc(var(--space-base) * 1.333);

/* BENAR: Memaksa pembulatan ke kelipatan grid unit bulat */
margin-bottom: calc(round(nearest, var(--space-base) * 1.333, var(--grid-unit)));
```

#### Kesalahan 3: Tidak Menyetel Ulang Line-Gap Pada Font Override
Saat mengonfigurasi `@font-face` override untuk mencegah CLS, banyak teknisi menyetel `ascent-override` dan `descent-override` namun melupakan `line-gap-override`. Akibatnya, browser menambahkan jarak *line gap* default dari font sistem lokal yang menghasilkan pergeseran vertikal kumulatif minor.
*Solusi*: Wajib mendeklarasikan `line-gap-override: 0%;` secara eksplisit pada layer fallback jika font web utama memiliki properti `lineGap = 0`.

---

### 11. Best Practices (Production Checklist)

#### Font Loading & Typography Architecture
- [ ] Semua font web disajikan secara lokal dalam format `.woff2` terkompresi dengan kompresi Brotli level 11.
- [ ] Font primer menyertakan `@font-face` cadangan (*fallback*) dengan metrik (`size-adjust`, `ascent-override`, `descent-override`) yang sudah diselaraskan dengan font sistem operasi.
- [ ] Semua ekspresi `clamp()` untuk tipografi wajib memiliki basis relatif `rem` pada nilai minimum dan idealnya untuk mematuhi WCAG 1.4.4.
- [ ] Skala modular dibatasi maksimal 7 tingkatan fungsional di lingkungan produksi (e.g., `sm`, `base`, `lg`, `xl`, `2xl`, `3xl`, `4xl`).
- [ ] Atribut OpenType seperti `font-feature-settings: 'cv02', 'cv03', 'cv04', 'tnum'` dikonfigurasi aktif untuk rendering tabular angka finansial.

#### Spacing & Layout Rhythm
- [ ] Seluruh nilai *spacing* (margin, padding, gap) wajib merupakan kelipatan dari `--grid-unit` fundamental (`4px`).
- [ ] Spasial antarmuka diatur menggunakan CSS Flexbox/Grid; hindari penempatan vertikal manual via `top` / `bottom` relatif.
- [ ] Gunakan CSS Subgrid pada *card-matrix layouts* bertingkat guna menjamin keselarasan visual lintas elemen bersaudara.
- [ ] Terapkan CSS `@container` queries untuk komponen desain sistem mandiri daripada bergantung pada `@media` queries global.
- [ ] Validasi nilai *touch target size* interaktif minimum adalah `24px` (WCAG 2.2 AA) atau `44px` (WCAG AAA) menggunakan token `--space` yang sesuai.

---

### 12. Hands-on Practice

Buat dan susun direktori pengujian implementasi berikut di:
`hands-on/m02/`

#### Struktur Proyek:
```
hands-on/m02/
├── package.json
├── index.html
├── scripts/
│   └── compile-tokens.js
├── src/
│   ├── tokens/
│   │   ├── spatial.json
│   │   └── typography.json
│   └── styles/
│       ├── tokens.css
│       └── layout.css
└── vite.config.js
```

#### Langkah 1: Inisialisasi Project & Dependensi
```bash
mkdir -p hands-on/m02/scripts hands-on/m02/src/tokens hands-on/m02/src/styles
cd hands-on/m02
npm init -y
npm install -D vite opentype.js
```

#### Langkah 2: Definisikan Token Desain Spasial & Tipografi
Tulis berkas token sumber:
`hands-on/m02/src/tokens/typography.json`:
```json
{
  "typography": {
    "scale": {
      "sm": { "min": 12, "max": 14 },
      "base": { "min": 16, "max": 18 },
      "lg": { "min": 20, "max": 24 },
      "xl": { "min": 25, "max": 32 }
    },
    "viewport": {
      "min": 320,
      "max": 1280
    }
  }
}
```

`hands-on/m02/src/tokens/spatial.json`:
```json
{
  "spatial": {
    "gridUnit": 4,
    "scale": [1, 2, 3, 4, 6, 8, 12, 16]
  }
}
```

#### Langkah 3: Buat Script Engine Kompilasi Token
`hands-on/m02/scripts/compile-tokens.js`:
```javascript
const fs = require('fs');
const path = require('path');

const typoTokens = JSON.parse(fs.readFileSync(path.join(__dirname, '../src/tokens/typography.json'), 'utf-8'));
const spatialTokens = JSON.parse(fs.readFileSync(path.join(__dirname, '../src/tokens/spatial.json'), 'utf-8'));

let cssOutput = ':root {\n  /* Generated Spatial Scale */\n';
cssOutput += `  --grid-unit: ${spatialTokens.spatial.gridUnit}px;\n`;

spatialTokens.spatial.scale.forEach(step => {
  cssOutput += `  --space-${step}: calc(var(--grid-unit) * ${step});\n`;
});

cssOutput += '\n  /* Generated Fluid Typography Scales */\n';
const { min: minVw, max: maxVw } = typoTokens.typography.viewport;

for (const [key, val] of Object.entries(typoTokens.typography.scale)) {
  const minRem = val.min / 16;
  const maxRem = val.max / 16;
  const minVwRem = minVw / 16;
  const maxVwRem = maxVw / 16;

  const slope = (maxRem - minRem) / (maxVwRem - minVwRem);
  const intersection = -minVwRem * slope + minRem;

  const clampString = `clamp(${minRem.toFixed(4)}rem, ${intersection.toFixed(4)}rem + ${(slope * 100).toFixed(4)}vw, ${maxRem.toFixed(4)}rem)`;
  cssOutput += `  --font-size-${key}: ${clampString};\n`;
}

cssOutput += '}\n';

fs.writeFileSync(path.join(__dirname, '../src/styles/tokens.css'), cssOutput);
console.log('✅ Tokens compiled successfully to src/styles/tokens.css');
```

Jalankan script kompilasi:
```bash
node scripts/compile-tokens.js
```

#### Langkah 4: Bangun Layout Menggunakan Subgrid & Container Queries
`hands-on/m02/src/styles/layout.css`:
```css
@import './tokens.css';

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: #f8fafc;
  color: #0f172a;
  padding: var(--space-6);
}

.dashboard-container {
  container-type: inline-size;
  container-name: dashboard;
  max-width: 1200px;
  margin: 0 auto;
}

.card-collection {
  display: grid;
  grid-template-columns: repeat(1, 1fr);
  gap: var(--space-4);
}

/* Container Query: Menyesuaikan kolom berdasarkan ukuran kontainer, bukan viewport */
@container dashboard (min-width: 650px) {
  .card-collection {
    grid-template-columns: repeat(3, 1fr);
  }
}

.data-card {
  display: grid;
  grid-row: span 3;
  grid-template-rows: subgrid;
  background: white;
  border: 1px solid #cbd5e1;
  border-radius: var(--space-2);
  padding: var(--space-4);
  row-gap: var(--space-3);
}

.data-card h3 {
  font-size: var(--font-size-lg);
  line-height: 1.2;
}

.data-card p {
  font-size: var(--font-size-base);
  color: #475569;
  line-height: 1.5;
}

.data-card .action-box {
  padding-top: var(--space-2);
}

.btn {
  background: #0284c7;
  color: white;
  border: none;
  padding: var(--space-2) var(--space-4);
  border-radius: var(--space-1);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
```

#### Langkah 5: Buat File Pengujian HTML
`hands-on/m02/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Spatial Grid Demo</title>
  <link rel="stylesheet" href="./src/styles/layout.css">
</head>
<body>
  <div class="dashboard-container">
    <div style="margin-bottom: var(--space-6);">
      <h1 style="font-size: var(--font-size-xl);">Platform Spatial Architecture</h1>
      <p style="font-size: var(--font-size-base);">Pengujian Subgrid dengan penyelarasan baris independen.</p>
    </div>

    <div class="card-collection">
      <!-- Card 1 -->
      <div class="data-card">
        <h3>Laporan Ringkas</h3>
        <p>Teks ringkas di body card untuk menguji kesejajaran subgrid vertikal.</p>
        <div class="action-box">
          <button class="btn">Detail</button>
        </div>
      </div>

      <!-- Card 2 -->
      <div class="data-card">
        <h3>Laporan Terperinci dengan Judul yang Sangat Panjang Melebihi Dua Baris</h3>
        <p>Kartu ini memiliki deskripsi yang lebih panjang untuk membuktikan bahwa subgrid akan memaksa action box tetap sejajar sempurna di bagian bawah secara otomatis tanpa intervensi JavaScript.</p>
        <div class="action-box">
          <button class="btn">Detail</button>
        </div>
      </div>

      <!-- Card 3 -->
      <div class="data-card">
        <h3>Status Sistem</h3>
        <p>Semua node beroperasi normal.</p>
        <div class="action-box">
          <button class="btn">Detail</button>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
```

Jalankan server pengembangan:
```bash
npx vite
```
Buka browser, ubah ukuran jendela browser secara elastis untuk mengamati penskalaan tipografi kontinu via `clamp()` dan adaptasi kolom kartu via container queries, serta evaluasi kesejajaran tombol action card via CSS subgrid.

---

### 13. Exercise

#### Level Easy
Ubah berkas `hands-on/m02/scripts/compile-tokens.js` untuk menambahkan dukungan skala spasial negatif (misal: `--space-neg-1: -4px;`, `--space-neg-2: -8px;`) yang biasa digunakan untuk *negative margin overlapping UI* tanpa melanggar grid base 4px.

#### Level Medium
Implementasikan token kerapatan (*density tokens*) pada `hands-on/m02/src/styles/tokens.css` sedemikian rupa sehingga ketika elemen container memiliki atribut `data-density="compact"`, variabel `--grid-unit` otomatis berkurang dari `4px` menjadi `3px`, memicu restrukturisasi seluruh turunan spasial secara proporsional.

#### Level Hard
Tulis modul Node.js yang membaca file font binary `.ttf` atau `.woff` (menggunakan pustaka `opentype.js`), lalu secara otomatis mengekstrak metrik tabel `OS/2` dan `hhea`, menghitung nilai optimal untuk `ascent-override`, `descent-override`, dan `size-adjust` terhadap font referensi `Arial`, kemudian mencetaknya sebagai file CSS `@font-face` deklarasi fallback otomatis.

---

### 14. Challenge

**Skenario**: Sistem desain Anda diimplementasikan pada aplikasi perbankan global multi-skrip yang mendukung teks Latin, Arab (RTL, *Right-to-Left* dengan kebutuhan vertical ascender/descender tinggi), dan Devanagari (membutuhkan hanging-baseline alignment).

**Tuntutan**:
1. Rancang arsitektur token CSS di mana nilai line-height dan font-size beradaptasi otomatis terhadap atribut `:lang()` dokumen tanpa perlu menduplikasi deklarasi layout structural.
2. Selesaikan masalah "diacritic clipping": Ketika teks Arab menggunakan font kustom, tanda baca harakat terpotong oleh komponen pembungkus dengan `overflow: hidden` jika menerapkan pengetatan margin vertikal (*cap-trim*).
3. Buat demo terisolasi yang mendemonstrasikan bahwa *Arabic text* mempertahankan keterbacaan penuh tanpa pemotongan glyph, sementara *English text* tetap terkunci presisi pada 4px baseline grid.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Mengapa penggunaan unit `px` secara statis pada properti `font-size` dapat melanggar pedoman aksesibilitas WCAG 1.4.4?
2. Bagaimana mekanisme matematika kerja fungsi CSS `clamp(MIN, VAL, MAX)` saat resolusi viewport berubah secara dinamis?
3. Sebutkan perbedaan struktural mendasar antara CSS Grid konvensional dengan CSS Subgrid (`grid-template-rows: subgrid`) pada komponen bersarang.
4. Apa fungsi dari properti `@font-face` descriptor `size-adjust` dalam pencegahan *Cumulative Layout Shift* (CLS)?
5. Mengapa grid sistem antarmuka modern umumnya memilih angka dasar 8px atau 4px dibandingkan angka ganjil seperti 5px atau 7px?

#### Pertanyaan Intermediate
6. Dalam perumusan kalkulasi *Fluid Typography*, mengapa intersep $y$ ($I$) dan slope ($S$) tidak disarankan dihitung secara manual di dalam runtime CSS via fungsi `calc()` yang rumit, melainkan lebih baik dikompilasi saat proses *build time*?
7. Bagaimana spesifikasi CSS `text-box-trim` (sebelumnya `leading-trim`) menyelesaikan masalah perataan spasial vertikal jika dibandingkan dengan pemberian margin negatif manual?
8. Apa kelemahan utama mengandalkan `@media (min-width: ...)` dibandingkan `@container (min-width: ...)` saat mendesain layout komponen modular pada arsitektur sistem desain berbasis micro-frontend?
9. Bagaimana pembulatan sub-piksel (*sub-pixel rendering*) oleh antarmuka grafis sistem operasi dapat merusak keselarasan visual pada grid 8px, dan bagaimana mitigasinya di CSS modern?
10. Kapan penggunaan teknik `font-display: swap` justru dapat memperburuk skor performa Core Web Vitals jika tidak disertai dengan *metric overrides*?

#### Skenario Kasus Produksi
11. **Skenario 1**: Sebuah tim produk melaporkan bahwa setelah menerapkan komponen typography baru dengan *negative margin baseline compensation*, tombol aksi tertentu pada perangkat iOS Safari tidak dapat ditekan (*unclickable*). Jelaskan akar masalah arsitektural rendering engine ini dan solusinya.
12. **Skenario 2**: Sistem desain enterprise Anda diterapkan pada aplikasi portal trading yang menampilkan tabel berisi 10.000 sel angka finansial real-time. Terjadi penurunan performa (*layout thrashing*) yang masif saat data mengalir via websocket. Analisis bagaimana arsitektur tipografi dan CSS custom properties Anda dapat dioptimalkan untuk meminimalkan tahapan *Recalculate Style* pada browser pipeline.
13. **Skenario 3**: Sebuah brand enterprise mengakuisisi produk SaaS lain yang memiliki skala tipografi berbasis rasio *Golden Ratio* (1.618), sedangkan produk utama menggunakan rasio *Major Third* (1.25). Rancang strategi migrasi berbasis token tanpa merusak tampilan visual komponen yang ada (*zero regression*).

---

### Kunci Jawaban Quiz

#### Pertanyaan Basic
1. Nilai `px` statis mengunci ukuran teks secara absolut di beberapa browser lama dan aplikasi pembaca layar, sehingga membatasi kemampuan sistem operasi atau preferensi browser pengguna tunanetra untuk memperbesar ukuran font minimal hingga 200% tanpa merusak tata letak.
2. Fungsi `clamp()` menetapkan nilai tengah (*ideal/VAL*) yang fleksibel (misal menggunakan kombinasi unit viewport `vw` dan `rem`), namun membatasi eksekusinya agar tidak pernah lebih kecil dari nilai batas bawah (*MIN*) dan tidak pernah lebih besar dari nilai batas atas (*MAX*).
3. Grid standar mendefinisikan layout hanya untuk anak langsung (*direct children*). Anak tingkat kedua (*grandchildren*) kehilangan konteks struktur grid induk. Sebaliknya, CSS Subgrid memungkinkan elemen bersarang mengadopsi dan mengunci langsung baris atau kolom yang telah didefinisikan oleh leluhurnya (*ancestor*).
4. `size-adjust` secara visual memperbesar atau memperkecil skala glyph dari font cadangan (*fallback font*) secara proporsional sehingga rata-rata dimensi horizontal dan vertikal karakter fallback identik dengan font web utama, mengeliminasi lompatan ukuran teks saat font utama selesai dimuat.
5. Angka 4 dan 8 merupakan bilangan genap yang dapat dibagi dua berulang kali tanpa menghasilkan pecahan desimal (`8 -> 4 -> 2 -> 1`), selaras dengan sebagian besar kerapatan piksel layar fisik perangkat keras modern (penskalaan faktor 1x, 2x, 3x Retina, 1.5x, 1.25x).

#### Pertanyaan Intermediate
6. Menghitung formula linier di dalam runtime CSS via `calc()` murni di klien meningkatkan beban kerja parsing CSS dan komputasi style recalculation pada thread utama (*main thread*), serta membuat stylesheet sulit didebug. Melakukan pra-kompilasi saat build menghasilkan nilai deterministik siap pakai yang performan.
7. `text-box-trim` memangkas ruang kosong (*half-leading*) langsung pada tingkat rasterizer mesin perenderan teks tanpa mengubah *bounding box* layout fisik elemen via margin. Ini mempertahankan batas aliran normal dokumen (*normal document flow*) tanpa risiko tumpang tindih elemen (*overlapping*) tak terduga.
8. `@media` terikat secara kaku ke ukuran jendela browser global (*viewport*). Komponen sistem desain modular yang diletakkan di sidebar sempit akan merender layout yang sama dengan komponen yang diletakkan di area konten utama jika viewport-nya sama, merusak responsivitas lokal. `@container` merespons ruang aktual yang tersedia bagi komponen tersebut.
9. Penskalaan layar (seperti display scaling 125%) menyebabkan 1px CSS dirender sebagai 1.25px fisik. Jika sistem tata letak menghasilkan dimensi pecahan, engine rasterizer melakukan pembulatan yang bervariasi antar-browser (beberapa pembulatan ke bawah, beberapa ke atas), menghasilkan celah 1px. Mitigasi: Gunakan properti `round()` CSS untuk mengunci perhitungan ke bilangan bulat atau kelipatan unit dasar.
10. `font-display: swap` secara paksa menampilkan font fallback terlebih dahulu sebelum menukar (*swap*) ke font utama ketika file font terunduh. Jika ukuran huruf dan metrik vertikal antara kedua font berbeda, proses penukaran tersebut memicu lonjakan layout masif (CLS tinggi).

#### Skenario Kasus Produksi
11. **Akar Masalah**: Margin negatif yang diterapkan untuk mengimbangi *half-leading* menyebabkan kotak pembatas (*bounding box*) teks tumpang tindih secara vertikal di atas elemen interaktif tetangga. WebKit (Safari) memperlakukan area pseudo/overflow teks ini sebagai lapisan transparan yang menangkap pointer event (*hit testing blocker*).  
    **Solusi**: Tambahkan deklarasi `pointer-events: none;` pada kontainer teks yang dipangkas, dan aktifkan kembali `pointer-events: auto;` secara eksplisit hanya jika terdapat tautan/interaksi di dalam teks, atau transisikan pemotongan ruang menggunakan CSS Flexbox inline offset (`transform: translateY(...)`) yang aman terhadap hit-testing.
12. **Akar Masalah & Solusi Arsitektural**:  
    - Font proporsional menyebabkan lebar angka bervariasi (angka "1" lebih sempit daripada "8"), memicu *layout reflow* pada tabel saat angka berfluktuasi cepat. Wajib menyuntikkan `font-variant-numeric: tabular-nums;` (OpenType `tnum`) agar semua angka memiliki lebar horizontal seragam.  
    - Hindari penggunaan CSS Variables yang sering berubah di level root sel tabel. Alih-alih merombak token runtime per sel, isolasi modifikasi nilai pada elemen data statis, dan manfaatkan CSS `contain: strict;` atau `contain: content;` pada level baris atau sel tabel (`<tr>` / `<td>`) agar rendering engine mengisolasi layout reflow hanya di dalam sel tersebut tanpa memicu restrukturisasi DOM satu dokumen.
13. **Strategi Arsitektural**:  
    - Buat *Abstract Spacing & Typography Layer* berbasis *token aliasing*.  
    - Hindari penggunaan nama skala absolut berbasis nilai (misal jangan gunakan `--font-16px` atau `--space-1-618`).  
    - Gunakan penamaan semantik tingkatan fungsional: `--font-scale-step-1`, `--font-scale-step-2`, dst.  
    - Di produk eksisting (lama), alias skala dipetakan ke formula Modular Ratio 1.25. Di produk yang baru diakuisisi, token semantik yang sama dipetakan ke formula 1.618 melalui file tema terisolasi (`[data-theme="acquired-brand"]`).  
    - Lakukan penyesuaian *base grid* secara bertahap dengan memetakan unit dasar spasial kedua produk ke *greatest common divisor* (GCD), yaitu basis 4px atau 2px micro-unit.

---

### 16. Summary

1. **Fluid Typography Modern**: Menggabungkan modular scaling matematis dengan fungsi CSS `clamp()` yang menyertakan basis `rem` menghasilkan penskalaan adaptif tanpa breakpoint kaku, bebas CLS, dan patuh WCAG 1.4.4.
2. **Eliminasi Spacing Vertikal Palsu**: Half-leading bawaan font OpenType merusak konsistensi ritme vertikal. Arsitektur mutakhir enterprise mengompensasi inkonsistensi ini via ekstraksi binary metrik font untuk disuntikkan ke CSS `@font-face` overrides (`ascent-override`, `size-adjust`) dan modern layout trimming.
3. **Penyelarasan Spasial Modular**: Mengandalkan kombinasi **CSS Subgrid** untuk sinkronisasi layout vertikal/horizontal multi-hierarki komponen, serta **Container Queries (`@container`)** untuk mewujudkan elemen UI modular independen yang beradaptasi terhadap kontainer penampungnya, bukan terhadap viewport global.
4. **Tokenisasi Kompilatif**: Seluruh nilai matematika spasial dan tipografi tidak didefinisikan secara manual/statik, melainkan diabstraksikan dalam format standar JSON dan dikompilasi via automated build pipeline (Node.js / Style Dictionary) untuk menjaga presisi sub-piksel dan integritas multi-platform.