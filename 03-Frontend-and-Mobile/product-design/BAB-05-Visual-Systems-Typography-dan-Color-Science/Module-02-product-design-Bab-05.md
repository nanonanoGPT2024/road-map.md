# BAB 05: Visual Systems, Typography, dan Color Science
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Mengonstruksi Sistem Warna Berbasis *Perceptually Uniform Color Space* (OKLab/OKLCH)** untuk aplikasi multi-platform, memitigasi anomali *chroma shift* dan *perceived lightness distortion* yang melekat pada model sRGB/HSL.
2. **Mengimplementasikan Algoritma Kontras Modern (APCA - *Advanced Perceptual Contrast Algorithm*)** dalam *pipeline design token* untuk memenuhi spesifikasi WCAG 3.0 (Silver/Gold level), menggantikan keterbatasan matematis WCAG 2.1.
3. **Membangun *Fluid Typography Engine* Berbasis Deterministik** menggunakan CSS *mathematical functions* (`clamp()`, `calc()`) yang terikat pada skala modular parametrik tanpa memicu *layout thrashing* atau degradasi performa rendering.
4. **Merancang dan Mengoptimasi Pipeline Tipografi Variabel (*Variable Fonts*)** melalui manipulasi *font variation axes* (`wght`, `wdth`, `opsz`, `slnt`), subpixel rasterization optimization, serta eliminasi *Cumulative Layout Shift* (CLS) mendekati `0.000` via *Font Metric Overrides* (`ascent-override`, `descent-override`, `size-adjust`).
5. **Menyusun Arsitektur *Design Token Engine*** level enterprise yang mampu mentranspilasi spesifikasi W3C Design Tokens Format Module (DTCG) menjadi artefak produksi multi-target (Web CSS Variables, iOS Swift Tokens, Android Jetpack Compose Singletons) dengan validasi CI/CD otomatis.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:

* **Dasar Vektor dan Matriks**: Operasi matriks 3x3 untuk transformasi koordinat ruang warna (*color space matrices conversion*).
* **CSS Modern Lanjutan**: Spesifikasi CSS Color Module Level 4 & 5, CSS Values and Units Module Level 4 (`clamp()`, `min()`, `max()`, *container query units* `cqw`/`cqh`).
* **Sistem Desain & Rekayasa Token**: Pemahaman tentang JSON Schema, AST (*Abstract Syntax Tree*), dan *build tools* berbasis Node.js/TypeScript.
* **Performa Rendering Web (Critical Rendering Path)**: Siklus hidup parsing HTML/CSS, *Layout*, *Paint*, *Composite*, dan pemahaman tentang *DirectWrite*, *CoreText*, serta rasterisasi tipografi *FreeType*.

---

### 3. Concept & Internal Architecture

#### 3.1. Color Science: Mengapa sRGB dan HSL Rusak Secara Matematis?

Model warna tradisional sRGB didasarkan pada karakteristik fisik fosfor tabung CRT tahun 1996, bukan pada sistem visual manusia (*Human Visual System* - HVS). HSL (*Hue, Saturation, Lightness*) dibangun sebagai transformasi silindris non-linear dari sRGB:

$$\text{Lightness (HSL)} = \frac{\max(R, G, B) + \min(R, G, B)}{2}$$

Formula ini mengabaikan bobot sensitivitas spektral sel fotoreseptor kerucut (*cone cells*) retina manusia. Berdasarkan fungsi efisiensi luminositas fotopik CIE ($\bar{y}(\lambda)$), mata manusia jauh lebih sensitif terhadap panjang gelombang hijau ($555\text{ nm}$) daripada biru ($445\text{ nm}$) atau merah ($650\text{ nm}$). Akibatnya:

* Warna Kuning Murni (`#FFFF00` $\rightarrow$ HSL: $60^\circ, 100\%, 50\%$) memiliki *perceived luminance* aktual $\approx 0.927$
* Warna Biru Murni (`#0000FF` $\rightarrow$ HSL: $240^\circ, 100\%, 50\%$) memiliki *perceived luminance* aktual $\approx 0.072$

Keduanya memiliki parameter $L = 50\%$ di HSL, namun menempatkan teks hitam di atas latar belakang biru menghasilkan kegagalan kontras ekstrem, sedangkan di atas kuning menghasilkan keterbacaan tinggi.

```
Perbandingan Luminansi Nyata (Perceived Lightness) pada HSL L=50%:
Hue:  0° (Red)    | ██████████░░░░░░░░░░ | Y ≈ 0.2126
Hue: 60° (Yellow) | ████████████████████ | Y ≈ 0.9278  <-- Ilusi L=50%
Hue: 120° (Green) | ███████████████░░░░░ | Y ≈ 0.7152
Hue: 240° (Blue)  | ███░░░░░░░░░░░░░░░░░ | Y ≈ 0.0722  <-- Ilusi L=50%
```

#### 3.2. Solusi Modern: OKLab dan OKLCH

Diciptakan oleh Björn Ottosson (2020), **OKLab** adalah ruang warna seragam perseptual (*perceptually uniform color space*). Jarak Euclidean ($\Delta E_{OK}$) antara dua titik warna dalam ruang OKLab berbanding lurus dengan perbedaan warna yang dipersepsikan oleh mata manusia:

$$\Delta E_{OK} = \sqrt{(L_1 - L_2)^2 + (a_1 - a_2)^2 + (b_1 - b_2)^2}$$

Transformasi dari ruang warna linier $sRGB$ ke $OKLab$ melewati dua tahap matriks:
1. Transformasi linier $RGB$ ke respons kerucut terstimulasi ($LMS$ space):

$$\begin{bmatrix} L \\ M \\ S \end{bmatrix} = \begin{bmatrix} 0.4122214708 & 0.5363325363 & 0.0514459929 \\ 0.2119034982 & 0.6806995451 & 0.1073969566 \\ 0.0883024619 & 0.2817188376 & 0.6299787005 \end{bmatrix} \begin{bmatrix} R_{lin} \\ G_{lin} \\ B_{lin} \end{bmatrix}$$

2. Pemampatan non-linear menggunakan akar pangkat tiga (menyerupai respons fotoreseptor retina):

$$l' = L^{1/3}, \quad m' = M^{1/3}, \quad s' = S^{1/3}$$

3. Transformasi ke koordinat Lab:

$$\begin{bmatrix} L \\ a \\ b \end{bmatrix} = \begin{bmatrix} 0.2104542553 & 0.7936177850 & -0.0040720468 \\ 1.9779984951 & -2.4285922050 & 0.4505937099 \\ 0.0259040371 & 0.7827717662 & -0.8086757660 \end{bmatrix} \begin{bmatrix} l' \\ m' \\ s' \end{bmatrix}$$

**OKLCH** adalah representasi silindris dari OKLab:
* **L (Lightness)**: $0.0 \dots 1.0$ (atau $0\% \dots 100\%$) persepsi terang-gelap yang sepenuhnya seragam.
* **C (Chroma)**: $0.0 \dots \approx 0.4$ tingkat kemurnian/kejenuhan warna (terbuka secara matematis melampaui sRGB hingga Display-P3 dan Rec.2020).
* **H (Hue)**: $0^\circ \dots 360^\circ$ sudut rona spektral.

#### 3.3. WCAG 2.1 vs APCA (Advanced Perceptual Contrast Algorithm)

WCAG 2.1 Contrast Ratio memiliki kelemahan fatal:

$$\text{Ratio} = \frac{L_1 + 0.05}{L_2 + 0.05}$$

Formula ini simetris (tidak membedakan teks terang di atas gelap vs teks gelap di atas terang) dan mengabaikan frekuensi spasial (ukuran dan ketebalan font).

**APCA (WCAG 3.0)** menghitung *Lightness Contrast* ($L_c$) berbasis fungsi adaptasi non-linear fisiologis:
1. Menghitung *estimated screen luminance* ($Y_s$) dengan kurva transfer daya yang dikoreksi.
2. Memperhitungkan efek *photopic/scotopic vision drift* dan *glare factor*.
3. Menghitung kontras bertanda (*signed contrast*):
   * Nilai positif: Teks gelap di atas latar belakang terang (kondisi *positive polarity*).
   * Nilai negatif: Teks terang di atas latar belakang gelap (kondisi *negative polarity*).
4. Ambang batas $L_c$ dipetakan secara dinamis ke matriks ukuran font ($px$) dan bobot font ($font-weight$).

```
                      WCAG 2.1 vs APCA Matrix
┌──────────────────────┬────────────────────────┬─────────────────────────┐
│ Fitur                │ WCAG 2.1               │ APCA (WCAG 3.0 draft)   │
├──────────────────────┼────────────────────────┼─────────────────────────┤
│ Model Persepsi       │ Matematis Kasar        │ Berbasis Neurosains HVS │
│ Polaritas Warna      │ Diabaikan (Simetris)   │ Asimetris (Positif/Neg) │
│ Spasial & Berat Font │ Diskrit (Normal/Large) │ Kontinu (Bobot vs Px)   │
│ Rentang Nilai        │ 1:1 hingga 21:1        │ Lc -108 hingga +106     │
│ Dark Mode Accuracy   │ Sangat Rendah          │ Sangat Presisi          │
└──────────────────────┴────────────────────────┴─────────────────────────┘
```

#### 3.4. Tipografi: OpenType Engine, Rasterisasi, dan Layout Metrics

Rendering tipografi pada sistem operasi modern melibatkan:
1. **HarfBuzz / DirectWrite**: Mengurai tabel OpenType (`cmap`, `GSUB`, `GPOS`) untuk penataan glif (*glyph shaping*), ligatur, dan pergeseran kerning.
2. **Rasterizer (FreeType / CoreText)**: Mengubah kurva Bézier kuadratik (TrueType) atau kubik (CFF/PostScript) menjadi representasi *subpixel bitmap* menggunakan teknik *anti-aliasing* (misalnya ClearType atau subpixel positioning).
3. **Cumulative Layout Shift (CLS)**: Terjadi ketika web font ($F_{web}$) dimuat menggantikan fallback system font ($F_{sys}$). Jika metrik font ($\text{Ascender}$, $\text{Descender}$, $\text{Cap-Height}$, $\text{Advance Width}$) berbeda, browser memicu proses *Reflow* dan *Repaint* seluruh pohon DOM di bawah elemen teks tersebut.

Formula kompensasi menggunakan CSS Font Metrics Override:

$$\text{size-adjust} = \frac{\text{AdvanceWidth}(F_{web})}{\text{AdvanceWidth}(F_{sys})}$$

$$\text{ascent-override} = \frac{\text{Ascender}(F_{web})}{\text{UPM}(F_{web})} \times 100\%$$

$$\text{descent-override} = \frac{\text{Descender}(F_{web})}{\text{UPM}(F_{web})} \times 100\%$$

---

### 4. Why & What

| Pendekatan Tradisional | Pendekatan Enterprise Visual System | Dampak Produksi |
| :--- | :--- | :--- |
| **Palet Hex/HSL Statis**: Didefinisikan per *hex-code* manual via tools grafis tanpa normalisasi persepsi. | **Sistem Parametrik OKLCH**: Warna diturunkan dari kurva matematis konstan untuk Chroma & Lightness. | Konsistensi kontras otomatis di seluruh spektrum rona. Tema baru (multi-brand) dibuat secara deterministik tanpa audit manual satu per satu. |
| **Rasio Kontras WCAG 2.1 (4.5:1 / 3:1)**: Aturan biner kaku. | **APCA Dynamic Lookup Matrix**: Kontras dihitung berdasarkan kombinasi ukuran teks, ketebalan, dan arah polaritas. | Mengeliminasi false positive (kontras valid tapi tidak terbaca) dan false negative (desain bagus dicap gagal aksesibilitas padahal sangat terbaca). |
| **Breakpoint Font-Sizes Manual**: Mendefinisikan `font-size` berbeda di `@media (min-width: 768px)`, dsb. | **Continuous Fluid Typography**: Perhitungan fluid berbasis kurva interpolasi linier/non-linier `clamp()`. | Mengeliminasi lonjakan visual (*layout jitter*) antar-breakpoint, mengurangi ukuran stylesheet CSS secara signifikan. |
| **Static Web Fonts Multi-file**: Mengunduh 8 file font terpisah (Regular, Italic, Bold, BoldItalic, dll). | **Variable Fonts Tunggal + Metrik Fallback**: 1 file WOFF2 variabel yang mencakup multi-axis + sinkronisasi fallback. | Mengurangi HTTP overhead hingga 70%, menghilangkan FOUT/FOIT, dan menghasilkan CLS = `0.000`. |

---

### 5. How (Workflow Detail)

Arsitektur siklus produksi visual system skala enterprise:

```
[Design Tokens Input (W3C JSON)]
               │
               ▼
┌────────────────────────────────────────────────────────┐
│ 1. Token Transformer & AST Parser                     │
│    - Validasi Schema JSON                              │
│    - Resolusi Referensi/Alias ({color.brand.primary})  │
└────────────────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────┐
│ 2. Color Science Engine (Node.js Build Time)           │
│    - Konversi ke OKLCH                                 │
│    - Evaluasi APCA Matrix (Teks vs Background)         │
│    - Gamut Mapping Fallback (Display-P3 -> sRGB)       │
└────────────────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────┐
│ 3. Style Dictionary Build Engine                       │
│    - Format Web: CSS Custom Properties Modern          │
│    - Format iOS: Swift UIColor/Color Structs           │
│    - Format Android: Kotlin Compose Color/Typography   │
└────────────────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────┐
│ 4. CI/CD Automated Accessibility & Performance Gate   │
│    - APCA contrast validation check (Bail on fail)     │
│    - Headless Browser CLS Test (Puppeteer/Lighthouse)  │
└────────────────────────────────────────────────────────┘
```

---

### 6. Analogy & Diagram ASCII

#### 6.1. Diagram Gamut Ruang Warna (OKLCH Melampaui sRGB & Display-P3)

```
        L (Lightness: 0 -> 1.0)
         ▲
         │       . - ~ ~ ~ - .
         │   . '   Display P3  ' .
         │  /   . - ~ ~ ~ - .     \
         │ /  /    sRGB      \  C  \
         ││  │   [Monitors]   │  h  │
         │ \  \   1996 CRT   /   r  /
         │  \   ' - ~ ~ ~ - '   o  /
         │   ' .               m  '
         │       ' - ~ ~ ~ - . a
         └─────────────────────────► Chroma (Kejenuhan Fisik)
                      Hue (Sudut Rotasi 0° - 360°)
```

*Analogi*: Memilih warna dalam sRGB ibarat memahat patung di dalam kardus sempit; batas fisiknya sering memotong saturasi warna tertentu secara tidak alami. Menggunakan OKLCH ibarat memahat di ruang terbuka (ruang visual alami manusia), di mana kita bisa menentukan warna target secara merata dan baru memproyeksikannya ke kapasitas layar penerima (sRGB, P3, atau Ultra-HD Rec.2020) melalui *gamut mapping*.

#### 6.2. Interpolasi Tipografi Fluida (CSS Clamp)

```
Font Size (px)
     ▲
     │
f_max│                                 +------------------------ (Tetap di f_max)
     │                                /
     │                               /  Kemiringan (Slope):
     │                              /   calc(V * 100vw + R)
     │                             /
f_min│  --------------------------+ (Tetap di f_min)
     │
     └────────────────────────────┼───────────────────────────► Viewport Width
                                v_min                        v_max
```

---

### 7. Implementation: Simple vs. Production-Grade

#### 7.1. Contoh Sederhana (Naive Implementation) - Mengapa Ini Buruk

```css
/* anti-pattern: HSL tidak linier, kontras manual, font melompat di breakpoint */
:root {
  --primary-hue: 220;
  --color-primary: hsl(var(--primary-hue), 100%, 50%);
  --color-primary-light: hsl(var(--primary-hue), 100%, 80%); /* Silau dan kontras teks rusak */
  --font-base: 16px;
}

@media (min-width: 768px) {
  :root {
    --font-base: 18px; /* Layout jump memicu reflow besar */
  }
}

.button {
  background-color: var(--color-primary);
  color: #ffffff; /* Gagal kontras jika hue diubah ke kuning tanpa kalkulasi ulang */
}
```

#### 7.2. Implementasi Produksi (Enterprise-Grade Visual Engine)

Sistem token warna dan kalkulator APCA modular dengan Style Dictionary dan CSS modern.

##### File: `tokens/color-scale-generator.ts`
Implementasi engine turunan warna OKLCH dan verifikator APCA.

```typescript
import { oklch, formatCss, converter } from 'culori';

// Tipe representasi warna OKLCH
export interface OklchColor {
  mode: 'oklch';
  l: number; // 0 to 1
  c: number; // 0 to ~0.4
  h: number; // 0 to 360
}

/**
 * Konversi standar sRGB Linear Lightness untuk perhitungan APCA
 */
function sRgbToY(r: number, g: number, b: number): number {
  // Transfer function sRGB ke Luminansi CIE Y (APCA variant)
  const toLinear = (c: number) =>
    c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  
  const rLin = toLinear(r / 255);
  const gLin = toLinear(g / 255);
  const bLin = toLinear(b / 255);
  
  return 0.2126729 * rLin + 0.7151522 * gLin + 0.0721750 * bLin;
}

/**
 * Kalkulator Sederhana APCA (W3C Silver Draft Formula)
 * Menghasilkan Nilai Kontras Lc (-108 hingga +106)
 */
export function calculateAPCA(textRgb: [number, number, number], bgRgb: [number, number, number]): number {
  const yTxt = sRgbToY(textRgb[0], textRgb[1], textRgb[2]);
  const yBg = sRgbToY(bgRgb[0], bgRgb[1], bgRgb[2]);

  // Ambang batas penyesuaian persepsi kegelapan
  const blkThrs = 0.022;
  const blkClmp = 1.414;
  
  const yTxtClamped = yTxt > blkThrs ? yTxt : yTxt + Math.pow(blkThrs - yTxt, blkClmp);
  const yBgClamped = yBg > blkThrs ? yBg : yBg + Math.pow(blkThrs - yBg, blkClmp);

  if (Math.abs(yBgClamped - yTxtClamped) < 0.0005) {
    return 0.0;
  }

  let outputContrast = 0;
  const normBG = 0.56;
  const normTXT = 0.57;
  const revBG = 0.62;
  const revTXT = 0.65;

  if (yBgClamped > yTxtClamped) {
    // Polaritas Positif: Teks Gelap di atas Latar Terang
    const sapc = (Math.pow(yBgClamped, normBG) - Math.pow(yTxtClamped, normTXT)) * 1.14;
    outputContrast = sapc < 0.1 ? 0 : (sapc - 0.027) * 100;
  } else {
    // Polaritas Negatif: Teks Terang di atas Latar Gelap
    const sapc = (Math.pow(yBgClamped, revBG) - Math.pow(yTxtClamped, revTXT)) * 1.14;
    outputContrast = sapc > -0.1 ? 0 : (sapc + 0.027) * 100;
  }

  return Number(outputContrast.toFixed(2));
}

/**
 * Generator Skala Shade Palet Deterministik berbasis Perceptually Uniform L*
 */
export function generateSemanticScale(baseHue: number, baseChroma: number) {
  const steps = [
    { name: '50',  l: 0.97, cFactor: 0.15 },
    { name: '100', l: 0.93, cFactor: 0.30 },
    { name: '200', l: 0.86, cFactor: 0.55 },
    { name: '300', l: 0.76, cFactor: 0.75 },
    { name: '400', l: 0.66, cFactor: 0.90 },
    { name: '500', l: 0.56, cFactor: 1.00 }, // Base
    { name: '600', l: 0.46, cFactor: 0.95 },
    { name: '700', l: 0.37, cFactor: 0.85 },
    { name: '800', l: 0.28, cFactor: 0.70 },
    { name: '900', l: 0.19, cFactor: 0.50 },
    { name: '950', l: 0.13, cFactor: 0.35 },
  ];

  return steps.reduce((acc, step) => {
    const color: OklchColor = {
      mode: 'oklch',
      l: step.l,
      c: Math.min(baseChroma * step.cFactor, 0.37), // Cegah out-of-gamut liar
      h: baseHue,
    };
    acc[step.name] = formatCss(color);
    return acc;
  }, {} as Record<string, string>);
}
```

##### File: `tokens/typography-math.ts`
Kalkulator deterministik parameter fluid typography tanpa layout shift.

```typescript
export interface FluidScaleConfig {
  minFontSizePx: number;
  maxFontSizePx: number;
  minViewportPx: number;
  maxViewportPx: number;
}

export function generateFluidClamp(config: FluidScaleConfig): string {
  const { minFontSizePx, maxFontSizePx, minViewportPx, maxViewportPx } = config;

  // Hitung gradien kemiringan interpolasi
  const slope = (maxFontSizePx - minFontSizePx) / (maxViewportPx - minViewportPx);
  const yAxisIntersection = -minViewportPx * slope + minFontSizePx;

  // Konversi ke satuan CSS rem (mengasumsikan root 16px)
  const rootFontSize = 16;
  const slopeVw = (slope * 100).toFixed(4);
  const interceptRem = (yAxisIntersection / rootFontSize).toFixed(4);
  const minRem = (minFontSizePx / rootFontSize).toFixed(4);
  const maxRem = (maxFontSizePx / rootFontSize).toFixed(4);

  return `clamp(${minRem}rem, ${interceptRem}rem + ${slopeVw}vw, ${maxRem}rem)`;
}
```

##### File: `styles/theme.css`
Implementasi runtime CSS Variables hasil build token dengan integrasi fallback Gamut dan Zero-CLS Font Loading.

```css
/* 1. Definisi Fallback Font Metrics Override untuk Eliminasi Total CLS */
@font-face {
  font-family: 'Fallback-Inter';
  src: local('Arial');
  ascent-override: 90.44%;
  descent-override: 22.56%;
  line-gap-override: 0.00%;
  size-adjust: 107.41%;
}

@font-face {
  font-family: 'Enterprise-Inter';
  src: url('/fonts/Inter-Variable.woff2') format('woff2-variations');
  font-weight: 100 900;
  font-display: swap;
  font-style: normal;
}

:root {
  /* Skala Tipografi Fluida Deterministik */
  --font-fluid-sm: clamp(0.7813rem, 0.7704rem + 0.0543vw, 0.8125rem);
  --font-fluid-base: clamp(1.0000rem, 0.9565rem + 0.2174vw, 1.1250rem);
  --font-fluid-h3: clamp(1.2500rem, 1.1196rem + 0.6522vw, 1.6250rem);
  --font-fluid-h2: clamp(1.5625rem, 1.3016rem + 1.3043vw, 2.3125rem);
  --font-fluid-h1: clamp(1.9531rem, 1.5033rem + 2.2492vw, 3.2462rem);

  /* Variabel Stack Font Terproteksi dari CLS */
  --font-sans: 'Enterprise-Inter', 'Fallback-Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;

  /* Base OKLCH Palette (Toleran Gamut Monitor Modern) */
  --brand-h: 250;
  --brand-c: 0.18;

  --color-brand-50: oklch(0.97 calc(var(--brand-c) * 0.15) var(--brand-h));
  --color-brand-100: oklch(0.93 calc(var(--brand-c) * 0.30) var(--brand-h));
  --color-brand-500: oklch(0.56 var(--brand-c) var(--brand-h));
  --color-brand-800: oklch(0.28 calc(var(--brand-c) * 0.70) var(--brand-h));
  --color-brand-950: oklch(0.13 calc(var(--brand-c) * 0.35) var(--brand-h));

  /* Surface and Semantic Text Variables */
  --surface-primary: var(--color-brand-50);
  --text-primary: var(--color-brand-950);
}

/* Dukungan Dynamic Dark Mode tanpa Pergeseran Hue */
@media (prefers-color-scheme: dark) {
  :root {
    --surface-primary: var(--color-brand-950);
    --text-primary: var(--color-brand-50);
  }
}

/* Komponen Typography-First Enterprise */
.display-header {
  font-family: var(--font-sans);
  font-size: var(--font-fluid-h1);
  font-variation-settings: 'wght' 720, 'opsz' 32;
  letter-spacing: -0.022em;
  line-height: 1.15;
  color: var(--text-primary);
  margin-block-end: 1rem;
}

.body-text {
  font-family: var(--font-sans);
  font-size: var(--font-fluid-base);
  font-variation-settings: 'wght' 400, 'opsz' 14;
  line-height: 1.6;
  color: var(--text-primary);
}
```

---

### 8. Real World Case Study: Multi-Tenant Enterprise Dashboard Platform

#### Latar Belakang & Masalah
Sebuah platform SaaS Fintech melayani ribuan instansi institusi keuangan (*white-label tenants*). Setiap *tenant* diizinkan memasukkan *Hex Code* brand mereka sendiri untuk mewarnai tema dashboard. 

*Bencana Produksi*: Klien memilih warna latar oranye terang (`#FFA500`) atau biru tua (`#000080`), menyebabkan teks tombol aksi utama yang berstatus *hardcoded* (`#FFFFFF` atau `#000000`) melanggar kriteria kepatuhan aksesibilitas perbankan (regulasi ADA & EN 301 549). Selain itu, pergantian font custom tiap tenant menyebabkan lonjakan CLS hingga `0.34`, menjatuhkan skor Google Core Web Vitals seluruh portal.

#### Solusi Arsitektur
1. **Dinamisasi Token Warna Run-time via OKLCH + APCA**:
   Tenant hanya memasukkan 1 nilai warna mentah. Sistem mengekstrak parameter *Hue* ($H$) dan mengunci saluran *Lightness* ($L$) serta *Chroma* ($C$) ke kurva keselamatan (*safety curve*) yang terkalibrasi secara matematis.
2. Generator teks APCA dinamis mengevaluasi warna latar. Jika ambang batas $L_c < |75|$ (rekomendasi APCA untuk teks tombol interaktif), sistem secara otomatis membalik warna teks ke *Lightness target* ($L=0.98$ atau $L=0.12$) tanpa mengubah preferensi *Chroma/Hue* dari brand.
3. **Automasi Font Metric Adjustment**:
   Engine CDN memindai WOFF2 milik tenant menggunakan modul Node.js berbasis `fontkit`, mengekstrak metrik UPM, dan menyuntikkan deklarasi `@font-face` dengan `size-adjust` serta `ascent-override` ke dokumen HTML secara dinamis sebelum proses rendering dimulai.

#### Hasil Terukur Produksi
* **Accessibility Failures**: Turun dari $42.3\%$ kegagalan kontras tenant menjadi **$0\%$** pelanggaran terdeteksi.
* **Core Web Vitals CLS**: Turun drastis dari rerata $0.34$ menjadi **$0.002$**.
* **Kecepatan Penerbitan Tema**: Kustomisasi tema brand dari 3 hari kerja tim desain berkurang menjadi **0 detik** (*pure deterministic runtime transformation*).

---

### 9. Trade-offs & Engineering Decisions

```
                           DECISION MATRIX
┌───────────────────────┬──────────────────────────┬──────────────────────────┐
│ Pendekatan Rekayasa   │ Keuntungan (Pros)        │ Kerugian/Biaya (Cons)    │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ OKLCH Native CSS      │ Kontras perseptual nyata │ Browser sebelum 2023     │
│                       │ Perhitungan kurva mulus  │ membutuhkan transpiler   │
│                       │ Gamut mapping luas       │ Polyfill postcss-oklab   │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ APCA Standards        │ Sesuai persepsi mata     │ Belum menjadi rilis final│
│                       │ Mendukung polaritas gelap│ resmi WCAG (masih status │
│                       │ dan ukuran font dinamis  │ working draft WCAG 3.0)  │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ Variable Fonts        │ 1 request network        │ File size awal lebih     │
│                       │ Fleksibilitas axis mikro │ besar jika hanya butuh 1 │
│                       │ Desain responsif presisi │ weight tunggal (~150KB)  │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ Fluid CSS `clamp()`   │ Nol layout shift breakpoint│ Menghitung testing QA    │
│                       │ Menghilangkan media query│ lebih rumit di resolusi  │
│                       │ tipografi berulang       │ non-standar / zoom user  │
└───────────────────────┴──────────────────────────┴──────────────────────────┘
```

*Analisis Latensi vs CPU Runtime*: Menghitung kontras dan skala warna via JavaScript di *browser client* dapat memicu *Long Tasks* jika diaplikasikan pada pohon DOM yang besar. Rekomendasi enterprise: Jalankan perhitungan matematis warna pada **waktu build (Style Dictionary pipeline)** atau dalam **Web Worker / Server-side Rendering edge function**. Browser hanya boleh menerima nilai CSS Custom Properties yang telah tervolatisasi.

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Umum 1: Gamut Clipping Banding
*Gejala*: Warna gradien di monitor monitor biasa terlihat memiliki garis patah-patah (*banding*) atau warna menjadi kusam (*clipping*) ketika menggunakan nilai Chroma tinggi di ruang OKLCH.
*Akar Masalah*: Memilih Chroma di atas `0.32` pada hue tertentu (misal cyan/hijau) melampaui kemampuan rendering sRGB. Browser melakukan clipping secara hard-edge.
*Solusi*: Terapkan PostCSS Gamut Mapping atau gunakan CSS `@supports`:
```css
.card-highlight {
  /* Fallback aman untuk monitor sRGB standar */
  background-color: rgb(0, 162, 232);
}

@supports (color: oklch(0 0 0)) {
  .card-highlight {
    /* Display-P3 wide gamut jika didukung hardware */
    background-color: oklch(0.68 0.22 230);
  }
}
```

#### 10.2. Kesalahan Umum 2: Kerusakan Teks Aksesibel akibat "Text-Zoom" pada `clamp()`
*Gejala*: Ketika pengguna melakukan zoom-in browser hingga $200\%$, ukuran teks tidak bertambah secara proporsional, melanggar WCAG Success Criterion 1.4.4 (Resize Text).
*Akar Masalah*: Formula `clamp()` menggunakan satuan *absolute viewport* murni tanpa mengombinasikannya dengan unit `rem`.
*Solusi*: Pastikan sisi intercept selalu berbasis unit `rem` dan hindari slope yang didominasi `vw` secara sepihak:
```css
/* SALAH: Tidak merespons text zoom */
font-size: clamp(16px, 2vw, 24px);

/* BENAR: Mengakomodasi preferensi zoom default pengguna */
font-size: clamp(1rem, 0.75rem + 1vw, 1.5rem);
```

#### 10.3. Kesalahan Umum 3: Font Metrics Override Desync
*Gejala*: Penggunaan `ascent-override` bukannya menghilangkan layout shift, tetapi malah membuat teks terpotong (*text clipping*) pada inline element.
*Akar Masalah*: Menghitung rasio override menggunakan unit pixel rendered, bukan unit pembagi matriks internal font ($\text{Units Per Em} / \text{UPM}$).
*Solusi*: Baca metadata OpenType font header secara langsung dari file binary font (.ttf/.woff2) menggunakan tools font-inspector CLI sebelum memasukkan nilai ke stylesheet.

---

### 11. Best Practices (Production Checklist)

- [ ] **Color Uniformity**: Seluruh palet semantik sistem desain didefinisikan menggunakan model OKLCH dengan parameter *Lightness* bertahap linier.
- [ ] **APCA Compliance**: Seluruh kombinasi warna interaktif (Button, Input Field, Card Clicks) lolos verifikasi ambang batas $L_c \ge 60$ untuk teks tebal/besar dan $L_c \ge 75$ untuk *body text* reguler.
- [ ] **Gamut Fallback Chain**: Sediakan *CSS color gamut media queries* (`@media (color-gamut: p3)`) untuk token yang memanfaatkan warna-warna di luar cakupan standar sRGB.
- [ ] **No Media-Query Font Size**: Seluruh skala modular tipografi menggunakan interpolasi deterministik CSS `clamp()`. Tidak ada `@media` query diskrit yang hanya bertugas mengubah `font-size`.
- [ ] **Zero Cumulative Layout Shift**: Deklarasikan fallback font dengan metrik kompensasi (`size-adjust`, `ascent-override`, `descent-override`) untuk mengunci CLS $\le 0.01$.
- [ ] **Variable Font Subsetting**: File WOFF2 variabel telah di-*subset* hanya untuk set karakter Unicode yang dibutuhkan (misal: Basic Latin + Latin Extended) menggunakan tools seperti `glyphhanger` atau `pyftsubset`.
- [ ] **Cross-Platform Token Contract**: File token JSON berstandar DTCG divalidasi dengan JSON Schema di level CI sebelum kompilasi ke artefak platform-specific (CSS, Swift, Kotlin).

---

### 12. Hands-on Practice

Struktur direktori praktikum yang akan kita bangun:

```
hands-on/m02/
├── package.json
├── tsconfig.json
├── tokens/
│   ├── base.tokens.json
│   └── build-tokens.ts
├── src/
│   ├── index.html
│   └── styles/
│       ├── typography.css
│       └── generated-tokens.css
└── tests/
    └── visual-systems.test.ts
```

#### Langkah 1: Inisialisasi Project

Jalankan perintah berikut di terminal Anda:

```bash
mkdir -p hands-on/m02/tokens hands-on/m02/src/styles hands-on/m02/tests
cd hands-on/m02
npm init -y
npm install typescript @types/node culori ts-node vitest --save-dev
```

Konfigurasi `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "CommonJS",
    "moduleResolution": "node",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist"
  },
  "include": ["tokens/**/*", "tests/**/*"]
}
```

#### Langkah 2: Definisikan Kontrak Token W3C (`tokens/base.tokens.json`)

```json
{
  "color": {
    "brand": {
      "primary": {
        "$type": "color",
        "$value": {
          "model": "oklch",
          "l": 0.58,
          "c": 0.21,
          "h": 260
        }
      }
    }
  },
  "typography": {
    "display": {
      "min": { "$value": 32 },
      "max": { "$value": 56 }
    },
    "body": {
      "min": { "$value": 16 },
      "max": { "$value": 18 }
    },
    "viewport": {
      "min": { "$value": 360 },
      "max": { "$value": 1280 }
    }
  }
}
```

#### Langkah 3: Script Engine Build Transpiler (`tokens/build-tokens.ts`)

```typescript
import * as fs from 'fs';
import * as path from 'path';
import { formatCss } from 'culori';

const rawTokens = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'base.tokens.json'), 'utf-8')
);

function generateClampCss(minSize: number, maxSize: number, minVw: number, maxVw: number): string {
  const slope = (maxSize - minSize) / (maxVw - minVw);
  const intercept = -minVw * slope + minSize;
  const slopeVw = (slope * 100).toFixed(4);
  const interceptRem = (intercept / 16).toFixed(4);
  const minRem = (minSize / 16).toFixed(4);
  const maxRem = (maxSize / 16).toFixed(4);

  return `clamp(${minRem}rem, ${interceptRem}rem + ${slopeVw}vw, ${maxRem}rem)`;
}

function run() {
  const brand = rawTokens.color.brand.primary.$value;
  const typo = rawTokens.typography;

  const shades = [
    { name: '100', l: 0.94, c: brand.c * 0.25 },
    { name: '300', l: 0.78, c: brand.c * 0.65 },
    { name: '500', l: brand.l, c: brand.c },
    { name: '700', l: 0.42, c: brand.c * 0.90 },
    { name: '900', l: 0.20, c: brand.c * 0.50 },
  ];

  let cssContent = `/* AUTO-GENERATED - JANGAN DIEDIT MANUAL */\n:root {\n`;

  // Output CSS Color Variables
  shades.forEach((s) => {
    const oklchCss = formatCss({
      mode: 'oklch',
      l: s.l,
      c: s.c,
      h: brand.h,
    });
    cssContent += `  --color-brand-${s.name}: ${oklchCss};\n`;
  });

  // Output Typography Variables
  const displayFluid = generateClampCss(
    typo.display.min.$value,
    typo.display.max.$value,
    typo.viewport.min.$value,
    typo.viewport.max.$value
  );
  const bodyFluid = generateClampCss(
    typo.body.min.$value,
    typo.body.max.$value,
    typo.viewport.min.$value,
    typo.viewport.max.$value
  );

  cssContent += `  --font-fluid-display: ${displayFluid};\n`;
  cssContent += `  --font-fluid-body: ${bodyFluid};\n`;
  cssContent += `}\n`;

  const outputPath = path.join(__dirname, '../src/styles/generated-tokens.css');
  fs.writeFileSync(outputPath, cssContent);
  console.log('✅ Tokens generated successfully at:', outputPath);
}

run();
```

#### Langkah 4: Tulis Unit Test Aksesibilitas APCA & Engine (`tests/visual-systems.test.ts`)

```typescript
import { describe, it, expect } from 'vitest';
import { generateFluidClamp } from '../tokens/color-scale-generator';

describe('Visual Systems Architecture Engine', () => {
  it('harus menghitung fluid clamp matematika dengan presisi absolut', () => {
    const clampResult = generateFluidClamp({
      minFontSizePx: 16,
      maxFontSizePx: 24,
      minViewportPx: 400,
      maxViewportPx: 1200,
    });

    // Perhitungan manual:
    // slope = (24 - 16) / (1200 - 400) = 8 / 800 = 0.01
    // y-intercept = -400 * 0.01 + 16 = -4 + 16 = 12px -> 0.75rem
    // slopeVw = 0.01 * 100 = 1vw
    expect(clampResult).toBe('clamp(1.0000rem, 0.7500rem + 1.0000vw, 1.5000rem)');
  });
});
```

#### Langkah 5: Eksekusi Pipeline

Tambahkan skrip di `package.json`:
```json
"scripts": {
  "build:tokens": "ts-node tokens/build-tokens.ts",
  "test": "vitest run"
}
```

Jalankan:
```bash
npm run build:tokens
npm run test
```

---

### 13. Exercises

#### Level Easy
Ubah berkas `tokens/base.tokens.json` untuk menambahkan token warna semantik `danger` berbasis rona merah OKLCH ($H = 25^\circ$). Jalankan script build token untuk memastikan CSS Variables baru `--color-danger-100` hingga `--color-danger-900` berhasil digenerasi ke berkas tujuan.
*Kriteria Penerimaan*:
* File `src/styles/generated-tokens.css` berisi 5 tingkatan warna bahaya.
* Tidak ada error transpiler TypeScript saat dieksekusi.

#### Level Medium
Buat modul fungsi TypeScript `gamutMapper(color: OklchColor): OklchColor` yang memeriksa apakah warna berada di dalam sRGB gamut boundary. Jika nilai berada di luar jangkauan representasi monitor sRGB, lakukan pemotongan Chroma ($C$) secara bertahap dengan langkah decrement $\Delta C = -0.01$ sampai warna valid kembali di ruang warna RGB tanpa merubah *Lightness* ($L$) atau *Hue* ($H$).
*Kriteria Penerimaan*:
* Fungsi memvalidasi warna menggunakan algoritma konversi `culori`.
* Nilai $L$ dan $H$ tidak bergeser lebih dari $\pm 0.001$.

#### Level Hard
Rancang pipeline komparasi kontras otomatis di Vitest yang memvalidasi seluruh kombinasi warna yang didefinisikan dalam token produksi. Pipeline harus menghentikan (*throw error*) proses build jika terdapat komponen interaktif dengan pasangan warna teks dan warna latar yang memiliki skor APCA di bawah $|L_c| = 60$.
*Kriteria Penerimaan*:
* Menghasilkan pelaporan tabular di terminal dengan kolom: `Foreground`, `Background`, `APCA Lc Score`, dan `Status (Pass/Fail)`.
* Otomatis memicu status `exit code 1` jika terjadi pelanggaran kontras.

---

### 14. Challenges

**Arsitektur Dynamic Multi-Brand Theming Berkinerja Tinggi Tanpa FOUC/CLS**

Anda adalah Principal Architect pada aplikasi enterprise dashboard berbasis Web Components yang melayani 50 brand anak perusahaan dengan tema visual berbeda-beda. 

*Target Desain Sistem*:
1. Rancang arsitektur sistem di mana konfigurasi token brand dimuat secara asinkron dari remote CDN tanpa memicu *Flash of Unstyled Content* (FOUC).
2. Terapkan fallback metriks sistem font sehingga transisi saat web-font terunduh menghasilkan Cumulative Layout Shift tepat $0.0000$.
3. Sistem wajib mendukung pertukaran *on-the-fly* tema gelap/terang yang secara otomatis menyesuaikan parameter *apochromatic contrast* (APCA) secara real-time di level DOM tanpa me-render ulang (*re-rendering*) elemen JavaScript.
4. Buat dokumen arsitektur teknis ringkas (1-2 halaman) yang mencakup rancangan mitigasi trade-off pemrosesan *CSS paint engine*, diagram aliran data token dari CMS hingga rendering akhir di layar client, dan skrip *automated sanity check*.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level (Pilihan Ganda)

1. Mengapa nilai Lightness 50% pada model HSL tidak menjamin tingkat keterbacaan yang sama antara warna Kuning dan Biru?
   - A. Karena HSL menggunakan representasi heksadesimal terkompresi.
   - B. Karena formula HSL tidak memperhitungkan kurva sensitivitas fotopik mata manusia terhadap panjang gelombang cahaya yang berbeda.
   - C. Karena monitor komputer membatasi gamut warna kuning secara artifisial.
   - D. Karena sudut rona (Hue) pada HSL tidak didasarkan pada lingkaran 360 derajat.
   *Kunci Jawaban*: **B**. HSL memperlakukan semua saluran warna fisik secara murni matematis, mengabaikan bahwa fotoreseptor retina manusia jauh lebih peka terhadap warna hijau/kuning daripada biru.

2. Parameter apa yang direpresentasikan oleh huruf 'C' dalam ruang warna OKLCH?
   - A. Colorimetry
   - B. Contrast Ratio
   - C. Chroma
   - D. Cyan Balance
   *Kunci Jawaban*: **C**. Chroma mengindikasikan tingkat kejenuhan atau kemurnian relatif warna, dihitung dari titik pusat akromatik menuju tepi luar ruang warna.

3. Apa keuntungan mendasar dari APCA dibandingkan rasio kontras WCAG 2.1?
   - A. APCA hanya menggunakan perhitungan heksadesimal murni.
   - B. APCA sepenuhnya mengabaikan ukuran font demi standardisasi.
   - C. APCA mempertimbangkan ukuran font, ketebalan (*weight*), dan polaritas latar belakang (terang-di-atas-gelap vs gelap-di-atas-terang).
   - D. APCA selalu menghasilkan rasio tetap 4.5:1 untuk semua warna.
   *Kunci Jawaban*: **C**. APCA berbasis persepsi neurosensori yang memperlakukan keterbacaan secara kontekstual terhadap ukuran elemen tipografi dan perbedaan arah kontras spasial.

4. Apa dampak penggunaan satuan `px` statis pada parameter kemiringan fungsi CSS `clamp()` terhadap aksesibilitas?
   - A. Menghilangkan keterbacaan pada browser Safari.
   - B. Mencegah mekanisme Text Zoom browser berfungsi sesuai spesifikasi WCAG 1.4.4.
   - C. Memicu memory leak pada Core Web Vitals rendering.
   - D. Menurunkan kecepatan unduh file stylesheet CSS.
   *Kunci Jawaban*: **B**. Penggunaan satuan absolut (non-rem) mematikan kalkulasi pembesaran teks berbasis pengaturan preferensi user font size di peramban.

5. Atribut font-face apa yang digunakan untuk mengompensasi perbedaan metrik vertikal antara web font dan fallback system font untuk mencegah layout shift?
   - A. `font-stretch` dan `font-variant`
   - B. `ascent-override`, `descent-override`, dan `size-adjust`
   - C. `font-smooth` dan `text-rendering`
   - D. `unicode-range` dan `font-display`
   *Kunci Jawaban*: **B**. Properti Font Metric Overrides memungkinkan developer menyelaraskan bounding box font cadangan lokal agar identik dengan web font eksternal sebelum font tersebut selesai dimuat.

---

#### Intermediate Level (Analisis & Rekayasa)

6. Sebuah monitor generasi baru mendukung cakupan warna Display-P3. Manakah deklarasi CSS Color Module Level 4 yang valid untuk mendefinisikan warna hijau cerah yang berada di luar jangkauan sRGB tanpa mengalami clipping manual?
   - A. `color: rgb(0 255 0 / wide-gamut);`
   - B. `color: oklch(0.85 0.28 140);`
   - C. `color: hsl(140deg, 100%, 50%, P3);`
   - D. `color: cie-lab(100 0 -50);`
   *Kunci Jawaban*: **B**. Sintaks `oklch(L C H)` secara native menjangkau cakupan ruang warna tak terbatas (unbounded) dan diinterpolasikan oleh monitor berteknologi wide gamut seperti Display-P3 atau Rec.2020.

7. Mengapa CSS Variable Theming berbasis custom properties dinilai lebih superior dibandingkan CSS-in-JS (seperti Styled Components runtime) dalam skala arsitektur enterprise?
   - A. CSS Variables tidak memerlukan deklarasi nama kelas unik.
   - B. CSS Variables dievaluasi secara natif oleh browser C++ rendering engine tanpa overhead eksekusi JavaScript runtime atau re-injection stylesheet ke dokumen `head`.
   - C. CSS Variables secara otomatis mengubah layout engine browser menjadi multi-threaded.
   - D. CSS Variables tidak bisa di-override di level element instance.
   *Kunci Jawaban*: **B**. CSS Custom Properties mengubah nilai di level style cascade engine tanpa kompilasi ulang string AST oleh engine V8 JavaScript, mencegah frame drops dan memori bloat saat tema diganti.

8. Perhatikan fungsi interpolasi tipografi berikut:
   `font-size: clamp(1rem, 0.5rem + 1.5vw, 2rem);`
   Pada ukuran lebar viewport berapakah font mencapai ukuran maksimumnya (2rem / 32px asumsi 1rem = 16px)?
   - A. 1000px
   - B. 1200px
   - C. 1600px
   - D. 2000px
   *Kunci Jawaban*: **C**.
   Target font-size = `2rem` = `32px`.
   Sisi intercept = `0.5rem` = `8px`.
   Formula: $32\text{px} = 8\text{px} + 1.5\text{vw}$
   $24\text{px} = 1.5\% \times \text{Viewport Width}$
   $\text{Viewport Width} = 24 / 0.015 = 1600\text{px}$.

9. Apa yang terjadi jika token warna mentah berformat Oklch langsung diparsing ke peramban tanpa penanganan Gamut Mapping saat dibuka pada layar sRGB lawas?
   - A. Halaman crash secara total dan memicu blank-screen DOM.
   - B. Browser melakukan clipping kasar pada saluran koordinat RGB yang meluap, memicu deviasi hue drastis (misal warna oranye bergeser menjadi cokelat keruh).
   - C. Browser membatalkan seluruh render cascading stylesheet.
   - D. Peramban otomatis mengonversi dokumen menjadi hitam-putih.
   *Kunci Jawaban*: **B**. Tanpa algoritma gamut mapping perseptual yang mempertahankan *lightness*, mekanisme *coordinate clipping* standar memangkas nilai RGB ke rentang `0-255`, merusak distorsi persepsi rona secara liar.

10. Mengapa variable font dengan sumbu optik (`opsz`) meningkatkan keterbacaan teks dibandingkan font statis tunggal?
    - A. `opsz` secara otomatis mengompres format biner file font menjadi 50% lebih kecil.
    - B. `opsz` menyesuaikan ketebalan garis halus (*hairlines*), proporsi kontras glif, dan spasi x-height secara presisi agar ramah dibaca pada ukuran fisik teks mikro tanpa kehilangan detail saat ditampilkan dalam ukuran besar.
    - C. `opsz` mengubah rasterizer OS dari antialiasing menjadi monokrom murni.
    - D. `opsz` mengizinkan developer menyisipkan gambar SVG langsung ke dalam glif tipografi.
    *Kunci Jawaban*: **B**. *Optical Sizing* (`opsz`) merupakan teknik tipografi klasik di mana desain anatomi glif disesuaikan untuk mengatasi efek visual distorsi yang muncul pada ukuran fisik rendering yang berbeda di layar display.

---

#### Production Scenario Cases

11. **Skenario Produksi 1**:
    Tim Core Web Vitals melaporkan bahwa skor LCP (Largest Contentful Paint) stabil di angka `1.2 detik`, tetapi skor CLS melonjak menjadi `0.28` tepat saat teks judul hero utama muncul di layar. Anda memeriksa stylesheet dan mendapati deklarasi:
    ```css
    h1 {
      font-family: 'Corporate-Sans', sans-serif;
      font-size: clamp(2rem, 1rem + 3vw, 4rem);
    }
    ```
    Font web membutuhkan waktu 800ms untuk diunduh dari remote server. Apa penyebab pasti layout shift ini dan bagaimana instruksi arsitektural spesifik untuk memperbaikinya tanpa menghapus font custom?
    *Jawaban Komprehensif*:
    *Akar Penyebab*: Teks awalnya dirender menggunakan fallback font bawaan OS (`sans-serif`) dengan metrik x-height, ascender, dan advance width default sistem. Ketika file `Corporate-Sans` selesai diunduh via jaringan, browser mengganti glif dengan metrik font baru yang berbeda ukurannya secara fisik, memaksa DOM menghitung ulang tinggi elemen (reflow) dan menggeser seluruh blok konten di bawah judul hero tersebut.
    *Solusi Arsitektur*:
    1. Ekstrak nilai metrik dari file binary font `Corporate-Sans` (Ascender, Descender, Units Per Em).
    2. Buat `@font-face` lokal cadangan dengan menerapkan `size-adjust`, `ascent-override`, dan `descent-override` sehingga ukuran rendering fisik font lokal sama persis dengan web-font sebelum file tiba.
    3. Terapkan `font-display: swap` bersamaan dengan deklarasi font stack terpadu:
    ```css
    @font-face {
      font-family: 'Corporate-Sans-Fallback';
      src: local('Arial');
      size-adjust: 104.2%;
      ascent-override: 92.5%;
      descent-override: 23.1%;
    }
    h1 {
      font-family: 'Corporate-Sans', 'Corporate-Sans-Fallback', sans-serif;
    }
    ```
    4. Tambahkan tag `<link rel="preload" href="/fonts/corporate-sans.woff2" as="font" type="font/woff2" crossorigin>` pada dokumen HTML header.

12. **Skenario Produksi 2**:
    Aplikasi web Anda mendukung dynamic theming melalui sistem design token. Pengguna enterprise memilih warna primer `--brand-base: oklch(0.65 0.24 130)` (Hijau Terang). Tombol aksi utama mengaplikasikan warna teks putih `#ffffff` di atas warna brand tersebut. Pengujian manual via WCAG 2.1 menyatakan warna ini *Lolos* (Rasio 4.6:1), namun pengguna lansia mengeluh teks tombol sangat sulit dibaca di monitor kantor mereka. Ketika diuji dengan APCA, berapa estimasi nilai kontras dan mengapa verifikasi WCAG 2.1 memberikan hasil palsu (*false positive*)?
    *Jawaban Komprehensif*:
    *Analisis Masalah*: WCAG 2.1 hanya menghitung rasio matematis relatif berbasis formula luminansi sRGB terstandardisasi lama tanpa mempertimbangkan polaritas persepsi spasial teks terang di atas latar belakang terang (*light-on-light irradiation effect*).
    Pada spektrum hijau/kuning, mata manusia menerima saturasi energi foton yang tinggi. Menaruh teks putih di atas latar hijau terang menghasilkan efek pembauran visual (*halation/blooming effect*) di mana cahaya dari latar mengaburkan garis batas tepi huruf teks putih.
    *Hasil APCA*: Formula APCA mendeteksi polaritas negatif ini secara asimetris dan akan menghasilkan skor $L_c$ di kisaran $-45$ hingga $-50$. Skor ini berada jauh di bawah batas minimum kelayakan teks tombol interaktif ($|L_c| \ge 60$ s.d $75$).
    *Rekomendasi Rekayasa*: Sistem design token engine wajib menerapkan APCA-based contrast picker. Jika skor $L_c < |60|$, warna teks tombol harus dialihkan secara otomatis ke warna gelap akromatik terkontrol (misalnya `oklch(0.15 0.02 130)`), menghasilkan nilai kontras positif $L_c > +80$ yang tajam dan nyaman bagi sistem penglihatan manusia.

13. **Skenario Produksi 3**:
    Perusahaan Anda memutuskan untuk memigrasikan 15 repositori aplikasi frontend monolitik dari CSS manual berbasis SCSS variabel ke Arsitektur Multi-Platform W3C Design Tokens. Tim QA Anda menemukan bahwa setelah transpilasi token selesai, ukuran bundel total CSS meningkat sebesar 45KB per halaman karena ribuan baris CSS Custom Properties yang tidak digunakan ikut ter-injeksi ke dalam berkas akhir. Bagaimana Anda mendesain ulang arsitektur build pipeline token agar distribusi token tetap aman, terisolasi, efisien, dan memiliki ukuran payload seminimal mungkin?
    *Jawaban Komprehensif*:
    *Strategi Arsitektur Pipeline*:
    1. **Pemisahan Tingkat Token (Token Tiering)**: Pisahkan kamus token menjadi 3 layer hierarki terisolasi:
       - *Global/Primitive Tokens* (Seluruh skala warna mentah, durasi animasi, skala angka murni).
       - *Semantic Tokens* (Abstraksi peran: `surface-primary`, `text-interactive`).
       - *Component Tokens* (Kebutuhan spesifik: `button-primary-bg`).
    2. **Eliminasi Primitif di Runtime Output**: Jangan transpilasikan *Global/Primitive Tokens* menjadi CSS Custom Properties publik di root runtime browser. Gunakan layer primitif hanya pada waktu kompilasi (*build-time only*) untuk mengompilasi nilai layer Semantik.
    3. **Static Analysis & Tree-Shaking CSS Variables**:
       Gunakan integrasi PurgeCSS / PostCSS AST traversal script di dalam bundler (misalnya Rollup/Vite/Webpack) yang memindai template HTML/JSX/Vue untuk mendeteksi variabel mana yang benar-benar dipanggil dengan sintaks `var(--token-name)`.
    4. Variabel CSS yang tidak memiliki referensi pemanggilan aktif pada komponen yang dibundel di-prune secara otomatis dari lembar stylesheet final.
    5. Distribusikan tema tenant dinamis melalui *Atomic Scoped Properties*, bukan dengan menyuntikkan seluruh definisi tema secara global di root selector `:root`.

---

### 16. Summary

Visual Systems skala enterprise modern telah berevolusi dari sekadar pemilihan kode visual estetis menjadi disiplin rekayasa perangkat lunak berbasis matematika murni dan ilmu persepsi manusia (*color and optical science*):

1. **OKLab/OKLCH** mengatasi cacat struktural sRGB/HSL dengan menyediakan koordinat perseptual seragam. Hal ini memungkinkan pembuatan variasi tema dan kalkulasi palet secara deterministik tanpa deviasi kecerahan nyata.
2. **APCA (Advanced Perceptual Contrast Algorithm)** menghadirkan standar aksesibilitas generasi baru yang berbasis neurosains fisiologis, memitigasi kesalahan verifikasi kontras WCAG 2.1 pada aplikasi modern, khususnya dalam ekosistem *Dark Mode*.
3. **Fluid Typography** melalui fungsi matematis CSS `clamp()` mengeliminasi ketergantungan rapuh pada media-query diskrit, menghadirkan skalabilitas antarmuka mulus di seluruh dimensi layar perangkat.
4. **Font Performance Optimization** via *Variable Font Axes* dan kalkulasi *Font Metric Overrides* (`size-adjust`, `ascent-override`, `descent-override`) berhasil mereduksi Cumulative Layout Shift (CLS) hingga bernilai nol mutlak, mempertahankan stabilitas visual antarmuka pengguna tanpa mengorbankan identitas tipografi brand enterprise.
5. **Token Pipeline Automation** bertindak sebagai *single source of truth* lintas platform yang menjamin konsistensi sistem, efisiensi bundel kode, serta validasi kepatuhan aksesibilitas secara otomatis dalam siklus CI/CD modern.