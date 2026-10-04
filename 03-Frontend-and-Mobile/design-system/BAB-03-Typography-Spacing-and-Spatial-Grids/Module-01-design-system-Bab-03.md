# SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** 03-Frontend-and-Mobile
* **Topik Utama:** Design System
* **Modul:** Bab 03 Module 01
* **Judul Modul:** Typography, Spacing, and Spatial Grids
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat Pengetahuan:** CSS/CSSOM Internal, Fluid Mathematics (CSS `clamp()`), Type Rendering Engines (HarfBuzz, FreeType, CoreText), Token Transformation Pipeline (Style Dictionary), Layout Engines (Flexbox, CSS Grid Engine).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Merancang Mathematical Modular Scales:** Mengembangkan sistem tipografi berbasis rasio matematis dinamis menggunakan `clamp()` dan kalkulasi viewport-aware tanpa ketergantungan pada runtime JavaScript.
2. **Menguasai Baseline Grid Alignment:** Menyelesaikan masalah desinkronisasi metrik font vertikal menggunakan CSS `font-size-adjust`, `cap-height-based alignment`, dan CSS Box Model rhythm compensation.
3. **Membangun Spatial Token Engine:** Mengimplementasikan sistem 4pt/8pt soft & hard grid spatial engine yang deterministik, scalable, serta kompatibel lintas platform (Web, iOS, Android).
4. **Mengisolasi dan Memitigasi Web Font Performance Bottleneck:** Menganalisis dan meniadakan Cumulative Layout Shift (CLS), Flash of Unstyled Text (FOUT), dan Flash of Invisible Text (FOIT) via metrik override `@font-face` (`ascent-override`, `descent-override`, `line-gap-override`).
5. **Menjamin Aksesibilitas Spasial dan Tipografi Tingkat Enterprise:** Memenuhi WCAG 2.2 Success Criteria 1.4.4 (Resize Text), 1.4.10 (Reflow), dan 1.4.12 (Text Spacing) melalui tokenisasi berbasis unit relatif (`rem`, `ch`, `em`).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Tipografi dan tata ruang (spacing/grid) bukanlah dekorasi visual semata, melainkan **arsitektur koordinat dan ritme matematis** dari antarmuka pengguna. Di tingkat enterprise, teks dan ruang kosong adalah modul struktural:

```
[ Layout Viewport ] -> [ Spatial Grid Sub-system ] -> [ Modular Typographic Scale ] -> [ Glyphs/Rasterizer ]
```

### Mental Model 1: Ruang Negatif Adalah Elemen Kelas Satu (First-Class Citizen)
Elemen antarmuka tidak "mendorong" elemen lain secara acak. Spasi adalah token terukur yang mengikat hierarki kognitif. Setiap jarak vertikal dan horizontal harus merupakan hasil perkalian skalar dari basis grid atomik ($base = 4\text{px}$ atau $8\text{px}$).

### Mental Model 2: Tipografi Adalah Kotak Matematis, Bukan Sekadar Glif
Browser tidak merender huruf langsung pada kanvas; browser menghitung *Em-square*, *Font Metrics* (Ascender, Descender, Cap-Height, X-Height), dan menerapkan *Half-Leading* untuk membentuk baris teks. Mengabaikan metrik ini menyebabkan desinkronisasi vertikal dengan sistem spacing.

### Mental Model 3: Fluiditas Terkendali vs. Breakpoint Fragmentation
Pendekatan lama memecah font dan margin secara diskrit pada breakpoint kaku (misalnya `@media (min-width: 768px)`). Mental model modern menerapkan **kalkulasi linear terikat rentang** via CSS `clamp()`, memetakan transisi visual yang kontinu di antara batas bawah ($V_{\min}$) dan batas atas ($V_{\max}$) resolusi layar.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah arsitektur aliran token dari deklarasi desain atomik hingga perenderan pada level GPU/Rasterizer browser:

```
+--------------------------------------------------------------------------------------------------+
| DESIGN SYSTEM SOURCE (Tokens JSON / W3C Design Token Community Group Format)                      |
|  - spatial.base = 0.25rem (4px)                                                                   |
|  - type.scale.ratio = 1.25 (Major Third)                                                          |
|  - font.metrics = { ascent: 1900, descent: -500, unitsPerEm: 2048, capHeight: 1456 }              |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| TOKEN COMPILER & TRANSFORMATION PIPELINE (Style Dictionary Engine)                                |
|  - Resolver: Hitung interpolasi fluid clamp(min, slope + y-intercept, max)                       |
|  - Metric Normalizer: Hitung ascent-override, descent-override, line-gap-override                 |
|  - Target Output: CSS Custom Properties, SCSS Maps, TypeScript Types, Android XML, iOS Swift      |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| BROWSER COMPUTATION ENGINE (CSSOM & Render Tree)                                                  |
|  1. Root Calculation: HTML font-size = 100% (Inherited from OS/User Agent Base: 16px)             |
|  2. Relative Resolution: Unit rem dikonversi ke Computed Pixels                                  |
|  3. Spatial Box Alignment: Flex/Grid Layout Engine menyelaraskan Margin/Gap ke Hard 4pt/8pt Grid  |
|  4. Inline Formatting Context (IFC): Text Strut, Half-Leading, dan Baseline Rhythm disinkronkan   |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
+--------------------------------------------------------------------------------------------------+
| GPU TEXT RASTERIZATION & PAINT (DirectWrite / CoreText / FreeType)                                |
|  - Subpixel Positioning & Anti-Aliasing diterapkan                                               |
|  - CLS = 0 (Fallback Font Metrics identik dengan Web Font via CSS Metric Overrides)              |
+--------------------------------------------------------------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi Metrik Tipografi Internal (The Em Square)

Setiap font digital dirancang di dalam ruang kotak koordinat vektor bernama **Em-Square** (umumnya 1000 unit untuk PostScript/OTF, atau 2048 unit untuk TrueType/TTF).

```
   +--------------------------------------------------------+ <--- Line Box Top
   |                       Half-Leading                     |
   +========================================================+ <--- Ascent Boundary (Font Metric)
   |                                                        |
   |   * * *       * * *             (Cap Height: ~70% Em)  | <--- Cap-Height Level
   |   *     *   *     *                                    |
   |   * * *       * * *             (X-Height: ~50% Em)    | <--- X-Height Level
   |   *     *         *                                    |
 --+---*-----*---*-----*------------------------------------+ <--- BASELINE (y = 0)
   |                   *             (Descent Metric)       |
   +========================================================+ <--- Descent Boundary (Font Metric)
   |                       Half-Leading                     |
   +--------------------------------------------------------+ <--- Line Box Bottom
```

* **Baseline:** Garis imajiner tempat glif utama duduk tanpa ekor bawah (descender).
* **Cap-Height:** Ketinggian huruf kapital (misal: 'H', 'T').
* **X-Height:** Ketinggian huruf kecil tanpa ascender (misal: 'x', 'a', 'e').
* **Ascender:** Bagian glif yang menjulang di atas x-height (misal: 'd', 'h', 'k').
* **Descender:** Bagian glif yang menggantung di bawah baseline (misal: 'p', 'y', 'g').
* **Half-Leading:** Ruang ekstra yang didistribusikan secara simetris di atas ascent dan di bawah descent oleh browser saat `line-height` > `font-size`:
  $$\text{Half-Leading} = \frac{\text{line-height} - (\text{Ascent} + |\text{Descent}|)}{2}$$

### 2. Anatomi Spatial Grid (Hard Grid vs. Soft Grid)

* **Hard Grid:** Komponen antarmuka memiliki tinggi dan lebar yang secara kaku bernilai mutlak kelipatan $8\text{px}$ (misal: $40\text{px}, 48\text{px}, 56\text{px}$). Semua elemen dipaksa duduk tepat pada garis batas grid vertikal. Kelemahan: Rentan rusak ketika perenderan teks menghasilkan line-wrap dinamis.
* **Soft Grid:** Menggunakan kelipatan $4\text{px}/8\text{px}$ murni pada token **margin, padding, dan gap**, sedangkan dimensi wadah (height) dibiarkan *fluid/auto* mengikuti konten. Ini merupakan standar de-facto aplikasi web enterprise.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Formulasi Matematis Tipografi Dinamis (Fluid Typography via Linear Spline)

Alih-alih menerapkan puluhan media query, kita menggunakan interpolasi linear untuk memetakan ukuran font secara presisi di antara dua titik ekstrem viewport.

Diberikan dua titik koordinat:
* $(V_{\min}, F_{\min})$: Nilai font minimum pada viewport terkecil.
* $(V_{\max}, F_{\max})$: Nilai font maksimum pada viewport terbesar.

Persamaan garis lurus $y = mx + c$, di mana:
$$\text{Slope } (m) = \frac{F_{\max} - F_{\min}}{V_{\max} - V_{\min}}$$
$$\text{Y-Intercept } (c) = F_{\min} - (m \times V_{\min})$$

Implementasi dalam sintaks CSS `clamp()`:
$$\text{font-size} = \text{clamp}(F_{\min},\; (m \times 100)\text{vw} + c,\; F_{\max})$$

*Catatan Implementasi Enterprise:* Nilai $c$ harus dikonversi ke unit `rem` untuk menjaga aksesibilitas ketika pengguna mengubah pengaturan default font browser (biasanya $16\text{px}$).

### 2. Harmonika Modular Typographic Scale

Hierarki visual dibentuk menggunakan deret ukur eksponensial:
$$S_n = S_0 \times r^n$$
Di mana:
* $S_0$ = Ukuran basis (Base Font Size, umumnya $1\text{rem}$ / $16\text{px}$).
* $r$ = Rasio skala (misal: Minor Third = $1.200$, Major Third = $1.250$, Perfect Fourth = $1.333$, Golden Ratio = $1.618$).
* $n$ = Langkah hierarki (integer: $-2, -1, 0, 1, 2, 3, \dots$).

### 3. Font Metric Overrides: Meniadakan CLS Akibat Web Font

Ketika font web kustom dimuat lambat, browser merender font cadangan sistem (*fallback font*, misal: Arial atau Times New Roman). Perbedaan rasio ascent/descent antara web font dan fallback menyebabkan pergeseran tata letak layout yang memicu skor CLS buruk.

CSS `@font-face` metric overrides memanipulasi fallback font agar menempati ruang kotak identik dengan font web tujuan:
$$\text{ascent-override} = \frac{\text{Ascender}}{\text{UnitsPerEm}} \times 100\%$$
$$\text{descent-override} = \frac{|\text{Descender}|}{\text{UnitsPerEm}} \times 100\%$$
$$\text{line-gap-override} = \frac{\text{LineGap}}{\text{UnitsPerEm}} \times 100\%$$

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah generator modular scale dan fluid token yang ditulis dalam TypeScript murni, tanpa dependensi eksternal, yang menghitung token spasial dan tipografi siap pakai untuk CSS output.

```typescript
// fluid-scale-generator.ts

export interface ViewportRange {
  minWidthPx: number;
  maxWidthPx: number;
}

export interface TypeScaleConfig {
  baseMinRem: number;
  baseMaxRem: number;
  ratioMin: number;
  ratioMax: number;
  viewport: ViewportRange;
}

export interface FluidTokenResult {
  step: number;
  minPx: number;
  maxPx: number;
  clampValue: string;
}

export function generateFluidModularScale(
  step: number,
  config: TypeScaleConfig
): FluidTokenResult {
  const { baseMinRem, baseMaxRem, ratioMin, ratioMax, viewport } = config;

  // 1 rem = 16px standard baseline
  const rootFontSize = 16;

  // Hitung ukuran target pada viewport min dan max
  const minSizeRem = baseMinRem * Math.pow(ratioMin, step);
  const maxSizeRem = baseMaxRem * Math.pow(ratioMax, step);

  const minSizePx = minSizeRem * rootFontSize;
  const maxSizePx = maxSizeRem * rootFontSize;

  // Hitung kemiringan (slope) dan perpotongan sumbu Y (y-intercept)
  const slope = (maxSizePx - minSizePx) / (viewport.maxWidthPx - viewport.minWidthPx);
  const yInterceptPx = minSizePx - slope * viewport.minWidthPx;
  const yInterceptRem = yInterceptPx / rootFontSize;

  const slopeVw = slope * 100;

  // Format clamp() string secara deterministik
  const minPart = `${Number(minSizeRem.toFixed(4))}rem`;
  const maxPart = `${Number(maxSizeRem.toFixed(4))}rem`;
  const preferredPart = `${Number(yInterceptRem.toFixed(4))}rem + ${Number(slopeVw.toFixed(4))}vw`;

  const clampValue = `clamp(${minPart}, ${preferredPart}, ${maxPart})`;

  return {
    step,
    minPx: Number(minSizePx.toFixed(2)),
    maxPx: Number(maxSizePx.toFixed(2)),
    clampValue,
  };
}

// CONTOH EKSEKUSI
const config: TypeScaleConfig = {
  baseMinRem: 1.0,      // 16px di layar mobile
  baseMaxRem: 1.125,    // 18px di layar desktop
  ratioMin: 1.2,        // Minor Third di mobile
  ratioMax: 1.25,       // Major Third di desktop
  viewport: {
    minWidthPx: 375,    // iPhone SE
    maxWidthPx: 1440,   // Desktop Standar
  },
};

// Hitung heading H1 (Step 4 pada tangga nada tipografi)
const h1Token = generateFluidModularScale(4, config);
console.log("H1 Fluid Token:", h1Token);
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi matematis dan rekayasa kode pada Seksi 07:

1. **Baris 24-25 (`minSizeRem = baseMinRem * Math.pow(ratioMin, step)`):** Menerapkan fungsi eksponensial deret modular geometris $S_0 \cdot r^n$. Kita memisahkan rasio mobile (`ratioMin = 1.2`) dan desktop (`ratioMax = 1.25`) karena rasio yang terlalu curam pada layar sempit memicu pemotongan kata secara agresif (*word-wrapping failure*).
2. **Baris 27-28 (`minSizePx = minSizeRem * rootFontSize`):** Normalisasi satuan ukuran ke pixel absolut sementara, untuk keperluan perhitungan linear spline terhadap resolusi viewport.
3. **Baris 31 (`slope = (maxSizePx - minSizePx) / ...`):** Menghitung laju perubahan ukuran font per pixel penambahan lebar viewport ($\Delta y / \Delta x$).
4. **Baris 32 (`yInterceptPx = minSizePx - slope * viewport.minWidthPx`):** Menghitung nilai dasar font saat viewport secara virtual berada pada nilai 0px ($c = y - mx$).
5. **Baris 33 (`yInterceptRem = yInterceptPx / rootFontSize`):** **Kritis untuk Aksesibilitas!** Mengubah nilai intercept ke `rem`. Jika kita membiarkan intercept menggunakan `px`, browser tidak akan memperbesar teks saat user tunanetra menaikkan "Text Zoom" default di browser mereka, melanggar WCAG 1.4.4.
6. **Baris 35 (`slopeVw = slope * 100`):** Mengalikan kemiringan dengan faktor 100 untuk menghasilkan unit `vw` (1vw = 1% dari viewport width).
7. **Baris 42 (`clamp(...)`):** Membungkus nilai dalam fungsi proteksi native CSS `clamp(min, preferred, max)`. Fungsi ini membatasi pertumbuhan teks agar tidak terus mengecil di bawah `375px` atau terus membesar tanpa batas di monitor ultra-wide (`>1440px`).

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Financial Enterprise Dashboard & Reading Platform
* **Skala:** 40 juta Monthly Active Users, diakses mulai dari feature phone Android low-end (viewport $320\text{px}$) hingga layar monitor trading ultrawide ($3440\text{px}$).
* **Masalah:**
  1. Terjadi regresi layout berat dengan skor **Cumulative Layout Shift (CLS) = 0.42** saat font kustom web dimuat (target Core Web Vitals $\le 0.10$).
  2. Baseline vertikal antarkolom data tabel desinkronisasi sebesar $2\text{px}-5\text{px}$, menyebabkan mata pengguna cepat lelah saat membaca baris keuangan.
  3. Desainer mendefinisikan 37 breakpoint kustom yang mengakibatkan CSS bundle membengkak hingga $450\text{KB}$ murni untuk styling responsif layout dan font.
* **Solusi Arsitektural:**
  1. Menghapus 37 media query manual dan menggantinya dengan **Single Continuous Fluid Typographic Engine**.
  2. Implementasi **Metric Overrides** pada fallback font untuk mereduksi CLS dari $0.42$ ke **$0.00$**.
  3. Membangun **4pt Spatial Hard Grid System** untuk layout container, dipadukan dengan **Cap-Height Offset Trimming** menggunakan CSS modern pseudo-element rhythm controller.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistem produksi tingkat lanjut: CSS Design Tokens, Font Metric Stabilization, dan komponen Spatial Grid Container.

### 1. `tokens.css`: Token Spasial 4pt/8pt & Tipografi Fluid Terkalibrasi

```css
/* tokens.css */
:root {
  /* ========================================================================
     SPATIAL SCALE (4pt Base Grid)
     Semua dimensi padding, margin, gap wajib menggunakan skalar ini.
     ======================================================================== */
  --space-0: 0;
  --space-1: 0.25rem;  /* 4px */
  --space-2: 0.5rem;   /* 8px */
  --space-3: 0.75rem;  /* 12px */
  --space-4: 1rem;      /* 16px */
  --space-5: 1.25rem;  /* 20px */
  --space-6: 1.5rem;   /* 24px */
  --space-8: 2rem;     /* 32px */
  --space-10: 2.5rem;  /* 40px */
  --space-12: 3rem;    /* 48px */
  --space-16: 4rem;    /* 64px */
  --space-20: 5rem;    /* 80px */

  /* ========================================================================
     FLUID TYPOGRAPHIC SCALE (Calculated from 375px to 1440px)
     Formulasi clamp() bebas breakpoint
     ======================================================================== */
  /* Body Base (Step 0): 16px -> 18px */
  --font-size-step-0: clamp(1rem, 0.956rem + 0.1878vw, 1.125rem);
  
  /* Step -1 (Caption/Small): 13.33px -> 14.4px */
  --font-size-step--1: clamp(0.8331rem, 0.808rem + 0.107vw, 0.9rem);
  
  /* Step 1 (Subheading): 19.2px -> 22.5px */
  --font-size-step-1: clamp(1.2rem, 1.123rem + 0.3286vw, 1.4063rem);

  /* Step 2 (Heading H3): 23.04px -> 28.13px */
  --font-size-step-2: clamp(1.44rem, 1.3201rem + 0.5117vw, 1.7578rem);

  /* Step 3 (Heading H2): 27.65px -> 35.16px */
  --font-size-step-3: clamp(1.728rem, 1.5518rem + 0.7519vw, 2.1973rem);

  /* Step 4 (Heading H1): 33.18px -> 43.95px */
  --font-size-step-4: clamp(2.0736rem, 1.8211rem + 1.0775vw, 2.7466rem);

  /* Deterministic Line Heights */
  --line-height-flat: 1;
  --line-height-tight: 1.2;
  --line-height-snug: 1.375;
  --line-height-normal: 1.5;
  --line-height-relaxed: 1.625;
}
```

### 2. `font-face.css`: Zero-CLS Fallback Matching System

```css
/* font-face.css */
/* 
Font Utama: Inter Display 
Metrik Asli: UnitsPerEm=2048, Ascent=1984, Descent=-494, LineGap=0
*/
@font-face {
  font-family: 'Inter Custom';
  src: url('/fonts/Inter-VariableFont.woff2') format('woff2-variations');
  font-weight: 100 900;
  font-display: swap;
  font-style: normal;
}

/* 
Fallback Font: Arial (Di-override agar cocok secara dimensi fisik 1:1)
Mengeliminasi Layout Shifts (CLS = 0)
*/
@font-face {
  font-family: 'Inter-Fallback';
  src: local('Arial');
  ascent-override: 96.875%;    /* 1984 / 2048 */
  descent-override: 24.121%;   /* 494 / 2048 */
  line-gap-override: 0%;       /* 0 / 2048 */
  size-adjust: 102.5%;         /* Menyelaraskan rata-rata width bounding box */
}

:root {
  --font-family-sans: 'Inter Custom', 'Inter-Fallback', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
```

### 3. `SpatialLayout.tsx`: Komponen Grid Production-Ready

```tsx
import React, { CSSProperties } from 'react';

type GridColumns = 1 | 2 | 3 | 4 | 6 | 12;
type SpatialGap = 'space-1' | 'space-2' | 'space-3' | 'space-4' | 'space-6' | 'space-8';

interface SpatialContainerProps {
  children: React.ReactNode;
  columns?: GridColumns;
  gap?: SpatialGap;
  padding?: SpatialGap;
  className?: string;
}

export const SpatialContainer: React.FC<SpatialContainerProps> = ({
  children,
  columns = 12,
  gap = 'space-4',
  padding = 'space-6',
  className = '',
}) => {
  const containerStyle: CSSProperties = {
    display: 'grid',
    /* Auto-fit responsive tanpa CSS media query kaku */
    gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
    columnGap: `var(--${gap})`,
    rowGap: `var(--${gap})`,
    padding: `var(--${padding})`,
    width: '100%',
    maxWidth: '1440px',
    marginLeft: 'auto',
    marginRight: 'auto',
    boxSizing: 'border-box',
  };

  return (
    <div style={containerStyle} className={`spatial-grid-root ${className}`}>
      {children}
    </div>
  );
};

interface TypographyProps {
  as?: 'h1' | 'h2' | 'h3' | 'p' | 'span';
  variant: 'step-4' | 'step-3' | 'step-2' | 'step-1' | 'step-0' | 'step--1';
  lineHeight?: 'tight' | 'snug' | 'normal' | 'relaxed';
  trimLeading?: boolean;
  children: React.ReactNode;
}

export const Typography: React.FC<TypographyProps> = ({
  as: Component = 'p',
  variant,
  lineHeight = 'normal',
  trimLeading = false,
  children,
}) => {
  // Cap-Height Leading Trimming via modern CSS property
  // Mengeliminasi white-space berlebih dari font half-leading
  const typographyStyle: CSSProperties = {
    fontFamily: 'var(--font-family-sans)',
    fontSize: `var(--font-size-${variant})`,
    lineHeight: `var(--line-height-${lineHeight})`,
    margin: 0,
    textWrap: variant === 'step-4' || variant === 'step-3' ? 'balance' : 'pretty',
    // Fallback/standardized leading trimming
    ...(trimLeading && {
      marginBlockStart: 'calc((1em - 1lh) / 2)',
      marginBlockEnd: 'calc((1em - 1lh) / 2)',
    }),
  };

  return <Component style={typographyStyle}>{children}</Component>;
};
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektural | 8pt Spatial Grid Murni | 4pt/8pt Hybrid Soft Grid | Fluid Continuous (`clamp`) | Diskrit Breakpoints (`@media`) |
| :--- | :--- | :--- | :--- | :--- |
| **Kebutuhan Layout Complex** | Sangat Kaku; sering gagal pada tabel data rapat | Fleksibel; mendukung densitas tinggi & layout mikro | Sangat Halus (*No visual stutter*) | Terfragmentasi (*Layout jump* pada breakpoint) |
| **Ukuran CSS Bundle** | Rendah (Token statis) | Rendah (Token statis) | **Minimal (0 media query tambahan)** | Sangat Tinggi (Duplikasi kelas `@media`) |
| **Beban Kalkulasi Browser** | Sangat Ringan | Sangat Ringan | Sangat Ringan (Native GPU rendering engine) | Ringan (Evaluasi runtime breakpoint) |
| **Cognitive Load Devs** | Rendah | Sedang (Perlu disiplin pemilihan 4pt vs 8pt) | Sedang (Membutuhkan generator script) | Rendah di awal, Tinggi dalam jangka panjang |
| **Toleransi Multi-Platform** | Sempurna (iOS/Android/Web) | Sempurna (Kompatibel dengan iOS point & Android dp)| Butuh interpretasi native di platform seluler | Sangat terikat pada ekosistem web |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Zoom Invalidation Bug (Pelanggaran WCAG 1.4.4)
* **Kegagalan:** Jika kemiringan (slope) `clamp()` dihitung hanya menggunakan `vw` tanpa `rem` (contoh: `font-size: clamp(16px, 4vw, 32px);`), mekanisme Browser Zoom (Ctrl+/Cmd+) **tidak akan memperbesar teks**, karena ukuran berbasis murni pada dimensi viewport, bukan skala preferensi pengguna.
* **Mitigasi:** Y-intercept wajib selalu menyertakan basis `rem` yang merujuk pada `font-size` bawaan HTML: `clamp(1rem, 0.5rem + 2vw, 2rem)`.

### 2. High-Density Text Clipping pada Android Line-Spacing
* **Kegagalan:** Penerapan `line-height` kurang dari $1.2$ pada komponen multi-bahasa (seperti glif bahasa Arab, Devanagari, atau aksara Thailand) memicu pemotongan ekstrem (*clipping*) pada bagian atas ascender atau bawah descender.
* **Mitigasi:** Pasang mekanisme lokalisasi token tipografi. Ubah token `line-height` menjadi dinamis ketika atribut `lang` dokumen berubah ke aksara non-Latin:
  ```css
  :root:lang(ar), :root:lang(th) {
    --line-height-normal: 1.8;
  }
  ```

### 3. Subpixel Rounding Fracture
* **Kegagalan:** Pembagian fractional pixel pada engine WebKit/Blink (misal: 3 kolom `calc(100% / 3) = 33.3333%`) dikombinasikan dengan subpixel padding ganjil ($5\text{px}$) dapat menghasilkan nilai kumulatif $100.001\%$, memicu salah satu kolom terdorong ke baris baru (*column drop*).
* **Mitigasi:** Gunakan CSS Grid native dengan fr unit (`repeat(3, 1fr)`) dan pastikan seluruh gap serta padding berakar pada kelipatan angka bulat 4pt/8pt.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Mengubah `font-size` pada Root `<html>` Menjadi Pixel Statis
* **Anti-Pattern:**
  ```css
  html {
    font-size: 62.5%; /* Hack 10px usang */
    /* ATAU */
    font-size: 16px;  /* MERUSAK PREFERENSI USER BROWSER */
  }
  ```
* **Solusi:** Jangan pernah menimpa `font-size` absolut pada tag `<html>`. Biarkan `html { font-size: 100%; }` agar browser dapat menghormati pengaturan aksesibilitas sistem operasi pengguna secara native.

### 2. Menggunakan Spacing Token untuk Mengatur Ketinggian Teks
* **Anti-Pattern:** Memberikan margin bernilai negatif secara sembarangan untuk menutupi white-space bawaan font metrics (`margin-top: -6px;`). Ini menghasilkan *brittle CSS* yang runtuh saat web font gagal dimuat dan beralih ke fallback font.
* **Solusi:** Terapkan CSS modern `text-box-trim` / `text-box-edge` (atau Leading Trim pseudo-element) untuk memotong ruang kosong internal glif secara matematis.

### 3. Mengabaikan Nilai `text-wrap` pada Headings
* **Anti-Pattern:** Membiarkan judul artikel panjang mengalami *orphan text* (satu kata tertinggal sendirian di baris bawah).
* **Solusi:** Definisikan secara global:
  ```css
  h1, h2, h3, h4, h5, h6 {
    text-wrap: balance;
  }
  p {
    text-wrap: pretty;
  }
  ```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Aturan Kelipatan 8/4 (The 8pt Rule):** Gunakan 8pt ($0.5\text{rem}$) sebagai ukuran atomik standar untuk margin dan padding struktural layout. Gunakan 4pt ($0.25\text{rem}$) secara eksklusif untuk spasi mikro (misal: jarak antara icon dan label teks, internal padding button kecil).
2. **Penggunaan Unit CSS Berdasarkan Konteks:**
   * Tipografi: Wajib menggunakan `rem` (skala global) atau `clamp()` (berbasis `rem` + `vw`).
   * Spacing (Margin/Padding/Gap): Wajib menggunakan `rem` agar ikut berskala secara proporsional saat browser text-zoom diaktifkan.
   * Media Query Breakpoints: Gunakan `em` untuk menghindari bug rendering penanganan scrollbar di beberapa varian browser berbasis WebKit.
   * Border-width: Gunakan `px` mutlak (karena garis pembatas $1\text{px}$ tidak boleh melar secara fluid).
3. **Leading Proportions Inversely Scale with Size:** Semakin besar ukuran teks (display/heading), semakin kecil proporsi `line-height` yang dibutuhkan:
   * Body Text (16px) $\rightarrow$ `line-height: 1.5` hingga `1.65`
   * Headings (32px) $\rightarrow$ `line-height: 1.2` hingga `1.3`
   * Display Display Fonts (64px+) $\rightarrow$ `line-height: 1.0` hingga `1.1`

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. WOFF2 Subset Pruning
Jangan memuat file font WOFF2 lengkap yang berisi 20,000+ karakter internasional jika aplikasi hanya menargetkan audiens tertentu. Potong subset karakter menjadi **Latin Glyph Ranges** via tool seperti `pyftsubset`:
```bash
pyftsubset Inter-Variable.ttf \
  --unicodes="U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F" \
  --flavor=woff2 \
  --output-file=Inter-Subset.woff2
```
*Hasil:* Pengurangan ukuran aset font dari **$850\text{KB}$ menjadi $\sim 35\text{KB}$** (reduksi transfer data $\gt 90\%$).

### 2. Eliminasi