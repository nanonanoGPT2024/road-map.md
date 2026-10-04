# Bab 05 Module 01: Visual Systems, Typography & Color Science

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** Product Design
* **Kategori:** 03-Frontend-and-Mobile
* **Bab:** 05 — Design Systems & UI Architecture
* **Modul:** 01 — Visual Systems, Typography & Color Science
* **Tingkat Kesulitan:** Advanced / Staff-Level Architecture
* **Prasyarat:** Pemahaman mendalam tentang CSS Modern (Custom Properties, CSS Houdini, Media Queries), JavaScript/TypeScript (ES2022+), Web Standards (W3C Color Level 4/5, OpenType specs), serta fundamental rendering pipeline peramban (Blink/Gecko/WebKit).

---

## SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Merekayasa token visual deterministik berbasis matematika (*Modular Scales*, *Fluid Interpolation via Clamp*) yang tahan terhadap fragmentasi *viewport*.
2. Mengimplementasikan kalkulasi ruang warna perseptual modern (**Oklab**, **Oklch**) untuk memastikan konsistensi *perceptual uniformity*, interpolasi gradien linear tanpa *gray dead zones*, dan pemenuhan standar kontras **APCA (Advanced Perceptual Contrast Algorithm)** melebihi batas kalkulasi usang WCAG 2.1.
3. Membangun sistem tipografi fluid multivariat dengan *OpenType variable font axes* (Weight, Width, Optical Size, Slant), mengeliminasi *layout shift* (CLS 0) selama proses *font loading* melalui kalkulasi *Font Metric Overrides*.
4. Mengabstraksi palet warna semantik multi-tema (*Light*, *Dark*, *High-Contrast*) yang terisolasi dari *primitive values*, memungkinkan mutasi tema berbasis CSS variables tanpa re-rendering pohon DOM JavaScript.
5. Mengintegrasikan *telemetri rendering visual* untuk memantau performa *First Contentful Paint* (FCP), *Cumulative Layout Shift* (CLS), dan *dropped frame budget* (16.67ms/frame) akibat rekalkulasi gaya warna dan tipografi.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma
Desain visual dalam rekayasa frontend tingkat lanjut bukanlah sekadar keputusan estetika arbitrary atau kumpulan nilai statis yang disalin dari Figma ke dalam file CSS. Desain visual adalah **sistem komputasi fisik dan perseptual**.

```
[ Mental Model Usang ]
Hex/sRGB -> Pixel Static -> WCAG 2.1 Static Ratio (4.5:1) -> Breakpoint Media Query Jitter
       │
       ▼
[ Mental Model Modern (Staff Engineer) ]
Oklch/P3 Gamut -> Fluid Calculus (clamp/vi) -> APCA Contextual Contrast -> Continuous Vector Scale
```

* **Color as Perception, Not Data Storage:** sRGB dan nilai Hexadecimal (`#FFFFFF`) dirancang berdasarkan karakteristik tabung sinar katoda (CRT) tahun 1996, bukan cara mata manusia (*human visual system/HVS*) memproses cahaya. Ruang warna perseptual modern (**Oklch**) memisahkan *Lightness* ($L$), *Chroma* ($C$), dan *Hue* ($h$), memastikan bahwa perubahan *hue* pada tingkat *lightness* yang konstan tidak mengubah *perceived brightness*.
* **Typography as a Vector Field:** Teks bukan blok statis berbasis titik piksel (`px`). Tipografi web modern adalah fungsi dinamis $f(\text{viewport}) \to (\text{size}, \text{line-height}, \text{optical-weight})$ yang beradaptasi secara mulus terhadap resolusi fisik, jarak pandang (*viewing distance*), dan karakteristik optik layar.
* **Separation of Semantic Intent and Primitive Values:** Token visual tidak boleh memetakan warna langsung ke komponen (misal: `button-background: #0055FF`). Token harus dibangun dalam arsitektur 3 lapis: *Global/Primitive* $\to$ *Semantic/Alias* $\to$ *Component-Scoped*.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur token visual di bawah ini mengilustrasikan alur pemrosesan dari kalkulasi matematika matematis hingga pengikatan (*binding*) runtime pada CSS Engine peramban.

```
+---------------------------------------------------------------------------------------+
|                                PRIMITIVE TOKENS LAYER                                 |
|                                                                                       |
|   [ CIE XYZ D65 ] ---> [ Oklab Transform ] ---> [ Polar Form: Oklch Engine ]          |
|   L: 0.0 - 1.0          a: -0.4 - +0.4          Lightness (0-100%)                    |
|                         b: -0.4 - +0.4          Chroma    (0-0.37+)                   |
|                                                 Hue       (0-360deg)                  |
+-------------------------------------------+-------------------------------------------+
                                            |
                                            v
+---------------------------------------------------------------------------------------+
|                                SEMANTIC MAPPING LAYER                                 |
|                                                                                       |
|   Light Context (Base L=0.98)                  Dark Context (Base L=0.15)             |
|   APCA Contrast Target: Lc >= 75              APCA Contrast Target: Lc >= -75         |
|                                                                                       |
|   --sys-color-surface: oklch(0.98 0.01 240)   --sys-color-surface: oklch(0.15 0.02 240)
|   --sys-color-primary: oklch(0.55 0.22 260)   --sys-color-primary: oklch(0.75 0.18 260)
+-------------------------------------------+-------------------------------------------+
                                            |
                                            v
+---------------------------------------------------------------------------------------+
|                                TYPOGRAPHY ENGINE LAYER                                |
|                                                                                       |
|   Modular Scale: r = 1.25 (Major Third)       Fluid Calculus:                         |
|   Base Type: 1rem (16px)                      clamp(min, preferred, max)              |
|   Variable Font Engine: Optical Axis Adjust   Metric Overrides (ascent, descent, gap) |
+-------------------------------------------+-------------------------------------------+
                                            |
                                            v
+---------------------------------------------------------------------------------------+
|                               COMPONENT CONSUMPTION                                   |
|                                                                                       |
|   .c-card {                                                                           |
|     background-color: var(--sys-color-surface);                                       |
|     font-size: var(--sys-typescale-body-fluid);                                       |
|     color: var(--sys-color-on-surface);                                               |
|   }                                                                                   |
+---------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi Ruang Warna Oklch
Ruang warna Oklch didefinisikan oleh tiga komponen ortogonal:
* **$L$ (Perceptual Lightness):** Rentang `0%` (hitam absolut) hingga `100%` (putih absolut). Skala ini selaras linear dengan persepsi luminansi fotopik manusia.
* **$C$ (Chroma):** Tingkat kemurnian atau saturasi warna, dimulai dari `0` (monokrom/abu-abu) secara teoritis tanpa batas atas, namun dibatasi oleh cakupan gamut fisik perangkat (Display P3 mencapai sekitar `0.37` untuk warna-warna tertentu).
* **$h$ (Hue Angle):** Sudut pada lingkaran warna dari `0` hingga `360` derajat (`0` = Merah Muda/Magenta, `90` = Kuning, `180` = Cyan, `270` = Biru).

Perbedaan mendasar dari $HSL$ adalah bahwa pada $HSL$, warna kuning murni (`hsl(60, 100%, 50%)`) memiliki luminansi perseptual jauh lebih tinggi dibandingkan biru murni (`hsl(240, 100%, 50%)`), meskipun keduanya memiliki nilai *Lightness* yang sama yaitu `50%`. Pada Oklch, jika $L = 0.7$, seluruh warna pada semua rotasi *Hue* ($h$) memancarkan persepsi terangnya cahaya yang sama persis ke retina.

### 2. Anatomi Tipografi Fluid & Kalkulasi Slope-Intercept
Tipografi fluid mengandalkan fungsi CSS `clamp(MIN, VAL, MAX)`. Untuk menciptakan responsivitas linear murni antara batas *viewport* minimum ($V_{\min}$) dan maksimum ($V_{\max}$), kita menggunakan formulasi garis lurus $y = mx + b$:

$$\text{Slope } m = \frac{S_{\max} - S_{\min}}{V_{\max} - V_{\min}}$$

$$\text{Intercept } b = S_{\min} - (m \times V_{\min})$$

Di mana:
* $S_{\min}$ adalah ukuran font target minimum (misal: `16px`).
* $S_{\max}$ adalah ukuran font target maksimum (misal: `20px`).
* $V_{\min}$ adalah batas bawah lebar viewport (misal: `320px`).
* $V_{\max}$ adalah batas atas lebar viewport (misal: `1280px`).
* Nilai dinamis diimplementasikan sebagai: `clamp(S_min, b + (m * 100vw), S_max)`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Algoritma Kontras: WCAG 2.1 vs. APCA (SAPC)
Metode kalkulasi kontras WCAG 2.1 mengandalkan rumus rasio luminansi relatif:

$$\text{Ratio} = \frac{L_1 + 0.05}{L_2 + 0.05}$$

Kelemahan matematis WCAG 2.1 meliputi:
1. **Ketidakpekaan Polaritas:** Mengabaikan fenomena bahwa teks putih di atas latar hitam (*dark mode*) memiliki difraksi dan keterbacaan yang berbeda drastis pada fovea manusia dibanding teks hitam di atas putih.
2. **Kegagalan Ruang Warna Spasial:** Mengasumsikan batas kontras konstan `4.5:1` terlepas dari ketebalan (*font weight*) dan frekuensi spasial (*font size*).

**APCA (Advanced Perceptual Contrast Algorithm)** memperbaiki defisiensi ini melalui pemodelan non-linear adaptasi cahaya:
* APCA menghasilkan nilai **Lc (Lightness Contrast)** bertanda ($+$ atau $-$) yang mengindikasikan polaritas (teks gelap di atas terang atau sebaliknya).
* Menghitung nilai luminansi menggunakan eksponen non-linear ($\gamma \approx 0.56$ dan $\gamma \approx 0.65$) untuk meniru respons non-linear sel fotoreseptor kerucut (cone photoreceptors).
* Memetakan ambang batas minimum Lc langsung terhadap matriks ukuran font dan *weight* (misal: font tipis membutuhkan Lc lebih tinggi daripada font tebal).

```
Tingkat Kontras APCA (Lc Matrix Minimum):
+---------------------+-------------+-------------+-------------+
| Font Size / Weight  | Weight 300  | Weight 400  | Weight 700  |
+---------------------+-------------+-------------+-------------+
| 12px / 9pt          | Prohibited  | Lc >= 90    | Lc >= 75    |
| 16px / 12pt         | Lc >= 90    | Lc >= 75    | Lc >= 60    |
| 24px / 18pt         | Lc >= 75    | Lc >= 60    | Lc >= 45    |
| 36px / 27pt         | Lc >= 60    | Lc >= 45    | Lc >= 30    |
+---------------------+-------------+-------------+-------------+
```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi modul TypeScript murni yang menghitung ruang warna Oklch, mentranslasikannya ke Display P3 dan sRGB, serta menghasilkan variabel CSS fluid typography deterministik.

```typescript
// visual-engine.ts

export interface OklchColor {
  l: number; // 0.0 to 1.0 (Lightness)
  c: number; // 0.0 to ~0.4 (Chroma)
  h: number; // 0.0 to 360.0 (Hue angle)
  a?: number; // 0.0 to 1.0 (Alpha)
}

export interface FluidTypeConfig {
  minSizePx: number;
  maxSizePx: number;
  minViewportPx: number;
  maxViewportPx: number;
}

/**
 * Menghasilkan string CSS clamp untuk tipografi fluid yang presisi
 */
export function generateFluidClamp(config: FluidTypeConfig): string {
  const { minSizePx, maxSizePx, minViewportPx, maxViewportPx } = config;

  if (minViewportPx >= maxViewportPx || minSizePx >= maxSizePx) {
    throw new Error("Batas maksimum harus lebih besar dari batas minimum.");
  }

  // Hitung slope (gradien)
  const slope = (maxSizePx - minSizePx) / (maxViewportPx - minViewportPx);
  // Hitung perpotongan sumbu-Y (intercept) dalam satuan piksel
  const intersectionPx = minSizePx - slope * minViewportPx;

  // Konversi ke rem (asumsi base root = 16px)
  const slopeVw = (slope * 100).toFixed(4);
  const interceptRem = (intersectionPx / 16).toFixed(4);
  const minRem = (minSizePx / 16).toFixed(4);
  const maxRem = (maxSizePx / 16).toFixed(4);

  return `clamp(${minRem}rem, ${interceptRem}rem + ${slopeVw}vw, ${maxRem}rem)`;
}

/**
 * Format representasi CSS Color Level 4 untuk Oklch
 */
export function formatOklch(color: OklchColor): string {
  const { l, c, h, a } = color;
  const clampedL = Math.min(Math.max(l, 0), 1);
  const clampedC = Math.max(c, 0);
  const normalizedH = ((h % 360) + 360) % 360;

  if (a !== undefined && a < 1) {
    const clampedA = Math.min(Math.max(a, 0), 1);
    return `oklch(${clampedL.toFixed(4)} ${clampedC.toFixed(4)} ${normalizedH.toFixed(2)} / ${clampedA.toFixed(2)})`;
  }

  return `oklch(${clampedL.toFixed(4)} ${clampedC.toFixed(4)} ${normalizedH.toFixed(2)})`;
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Evaluasi Modul `visual-engine.ts`
1. **Baris 3–8 (`interface OklchColor`):** Mendefinisikan tipe data untuk koordinat warna Oklch. Membatasi $l$ dari $0.0$ hingga $1.0$ sesuai spesifikasi W3C Color Module Level 4, serta $h$ sebagai sudut derajat geometris.
2. **Baris 24–28 (`generateFluidClamp` math setup):** Mengimplementasikan interpolasi linear:
   $$\text{slope} = \frac{\Delta y}{\Delta x} = \frac{\text{maxSizePx} - \text{minSizePx}}{\text{maxViewportPx} - \text{minViewportPx}}$$
   Variabel `intersectionPx` adalah nilai $b$ dalam persamaan linier $y = mx + b$.
3. **Baris 31–36 (Konversi Satuan):** `slope * 100` mengonversi nilai desimal menjadi satuan viewport width (`vw`). Nilai `interceptRem` dihitung relatif terhadap standar `1rem = 16px`. Hasil keluaran menggabungkan unit statis (`rem`) dan dinamis (`vw`) untuk mencegah pemblokiran pembesaran teks (*text zoom accessibility override*) oleh pengguna di browser.
4. **Baris 42–54 (`formatOklch`):** Menjamin bahwa nilai numerik tetap berada dalam batas ruang aman matematis (*clamping* dan normalisasi modulo derajat `360`).

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks: Fintech Global Trading Platform ("AuraTrade")
AuraTrade menghadapi dua tantangan berat pada visual engine sistem aplikasinya:
1. **Chroma Clipping & False Information:** Pada monitor profesional gamut lebar (Apple Display P3), warna merah kerugian (*bearish*) dan hijau keuntungan (*bullish*) terdistorsi secara persepsi jika dikonversi secara naif via sRGB. Di mode malam, warna latar belakang berbenturan dengan nilai teks indikator, menyebabkan ketidakjelasan visual yang kritis bagi trader derivatif.
2. **Cumulative Layout Shift (CLS):** Penggunaan web font eksternal kustom (*custom geometric sans*) menimbulkan *Flash of Unstyled Text* (FOUT) dan lonjakan CLS sebesar `0.28` (jauh di atas batas Google Web Vitals `0.1`), karena perbedaan dimensi metrik antara fallback font sistem (`Arial/Helvetica`) dengan font kustom saat diunduh.

### Solusi Desain Sistem:
* Membangun tokenisasi warna semantik adaptif menggunakan ruang warna `oklch()` dengan kalkulasi target **APCA Lc $\ge 75$** untuk teks data tabel.
* Mengimplementasikan `@font-face` dengan atribut `size-adjust`, `ascent-override`, dan `descent-override` untuk menyamakan metrik fallback font sistem secara presisi, mereduksi CLS menjadi `0.00`.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah kode CSS terpadu dan arsitektur token yang mengintegrasikan metrik font kustom, fluid typography, serta palet semantik berbasis warna perseptual tingkat lanjut.

### File: `tokens.css`
```css
/* ==========================================================================
   METRIC OVERRIDES (Eliminasi CLS Font Loading)
   Fallback disesuaikan secara metrik terhadap font target 'Inter'
   ========================================================================== */
@font-face {
  font-family: 'Inter-Fallback';
  src: local('Arial');
  ascent-override: 90.20%;
  descent-override: 22.48%;
  line-gap-override: 0.00%;
  size-adjust: 107.40%;
}

@font-face {
  font-family: 'Inter';
  font-style: oblique 0deg 10deg;
  font-weight: 100 900;
  font-display: swap;
  src: url('/fonts/Inter-Variable.woff2') format('woff2-variations');
}

/* ==========================================================================
   PRIMITIVE & DYNAMIC COLOR ENGINE (Oklch)
   ========================================================================== */
:root {
  /* Primitive Hues */
  --primitive-hue-brand: 264.0;
  --primitive-hue-success: 145.0;
  --primitive-hue-danger: 25.0;

  /* Primitive Neutral Luminance Levels */
  --primitive-l-white: 1.0;
  --primitive-l-black: 0.0;

  /* Fluid Typography Scale (16px @ 360px -> 20px @ 1440px) */
  --fluid-text-base: clamp(1rem, 0.9167rem + 0.3704vw, 1.25rem);
  
  /* Fluid Heading Scale (24px @ 360px -> 48px @ 1440px) */
  --fluid-text-heading: clamp(1.5rem, 1.0rem + 2.2222vw, 3rem);

  /* Typography Fallbacks Composition */
  --font-stack-sans: 'Inter', 'Inter-Fallback', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

/* ==========================================================================
   SEMANTIC THEME TOKENS: LIGHT (Default Context)
   ========================================================================== */
:root, [data-theme="light"] {
  color-scheme: light;

  /* Canvas and Surfaces */
  --color-surface-canvas: oklch(0.99 0.002 var(--primitive-hue-brand));
  --color-surface-subtle: oklch(0.95 0.01 var(--primitive-hue-brand));
  --color-surface-panel:  oklch(1.00 0.00 var(--primitive-hue-brand));

  /* Foregrounds & Typography (Evaluated against Surface Lc > 75) */
  --color-text-primary:   oklch(0.18 0.03 var(--primitive-hue-brand));
  --color-text-secondary: oklch(0.42 0.04 var(--primitive-hue-brand));
  
  /* Brand Indicators */
  --color-action-primary: oklch(0.52 0.24 var(--primitive-hue-brand));
  --color-action-on-primary: oklch(0.99 0.00 var(--primitive-hue-brand));

  /* Trading States */
  --color-trade-bullish: oklch(0.55 0.18 var(--primitive-hue-success));
  --color-trade-bearish: oklch(0.52 0.22 var(--primitive-hue-danger));
}

/* ==========================================================================
   SEMANTIC THEME TOKENS: DARK (Auto / Inversion Context)
   ========================================================================== */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;

    --color-surface-canvas: oklch(0.12 0.015 var(--primitive-hue-brand));
    --color-surface-subtle: oklch(0.16 0.02 var(--primitive-hue-brand));
    --color-surface-panel:  oklch(0.20 0.025 var(--primitive-hue-brand));

    --color-text-primary:   oklch(0.94 0.01 var(--primitive-hue-brand));
    --color-text-secondary: oklch(0.70 0.02 var(--primitive-hue-brand));

    --color-action-primary: oklch(0.68 0.20 var(--primitive-hue-brand));
    --color-action-on-primary: oklch(0.10 0.02 var(--primitive-hue-brand));

    /* Adjusted for Dark Mode Halation Mitigation */
    --color-trade-bullish: oklch(0.72 0.16 var(--primitive-hue-success));
    --color-trade-bearish: oklch(0.68 0.19 var(--primitive-hue-danger));
  }
}

[data-theme="dark"] {
  color-scheme: dark;

  --color-surface-canvas: oklch(0.12 0.015 var(--primitive-hue-brand));
  --color-surface-subtle: oklch(0.16 0.02 var(--primitive-hue-brand));
  --color-surface-panel:  oklch(0.20 0.025 var(--primitive-hue-brand));

  --color-text-primary:   oklch(0.94 0.01 var(--primitive-hue-brand));
  --color-text-secondary: oklch(0.70 0.02 var(--primitive-hue-brand));

  --color-action-primary: oklch(0.68 0.20 var(--primitive-hue-brand));
  --color-action-on-primary: oklch(0.10 0.02 var(--primitive-hue-brand));

  --color-trade-bullish: oklch(0.72 0.16 var(--primitive-hue-success));
  --color-trade-bearish: oklch(0.68 0.19 var(--primitive-hue-danger));
}

/* ==========================================================================
   PRODUCTION COMPONENT: FINANCIAL DATA DISPLAY
   ========================================================================== */
.order-book-card {
  font-family: var(--font-stack-sans);
  background-color: var(--color-surface-panel);
  border: 1px solid var(--color-surface-subtle);
  border-radius: 8px;
  padding: 1.5rem;
  max-inline-size: 480px;
}

.order-book-header {
  font-size: var(--fluid-text-heading);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-text-primary);
  margin-block-end: 1rem;
}

.order-row {
  display: flex;
  justify-content: space-between;
  font-size: var(--fluid-text-base);
  padding-block: 0.5rem;
  border-block-end: 1px solid var(--color-surface-subtle);
}

.order-row--bullish .order-price {
  color: var(--color-trade-bullish);
  font-feature-settings: "tnum" 1, "cv05" 1; /* Tabular numbers & alternate styles */
}

.order-row--bearish .order-price {
  color: var(--color-trade-bearish);
  font-feature-settings: "tnum" 1, "cv05" 1;
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek Arsitektur | sRGB / Hexadecimal | HSL (Hue, Saturation, Lightness) | Oklch (W3C Color 4) |
| :--- | :--- | :--- | :--- |
| **Keseragaman Perseptual** | **Rendah**: `#FFFF00` (kuning) jauh lebih silau dibanding `#0000FF` (biru). | **Sangat Buruk**: $L=50\%$ biru sangat gelap bagi retina, sementara $L=50\%$ kuning sangat terang. | **Tinggi (Near Absolute)**: $L=0.7$ memiliki luminansi perseptual identik lintas semua $Hue$. |
| **Aksesibilitas Gamut Layar** | Terkunci pada gamut 8-bit sRGB usang (~35% persepsi mata manusia). | Terkunci pada gamut sRGB via silinder RGB transformasi. | **Gamut-Agnostik**: Mampu memetakan secara presisi gamut modern P3 hingga Rec.2020. |
| **Interpolasi Gradien** | Mengalami *gray dead zones* di area transisi saturasi. | Mengalami artefak rotasi hue non-linear saat blending warna berlawanan. | **Linear Bersih**: Transisi mulus tanpa degradasi kroma di titik tengah. |
| **Kompatibilitas Mesin Peramban** | 100% universal (Legacy IE support). | 100% universal (CSS3). | Chrome 111+, Safari 15.4+, Firefox 113+ (~92%+ global support di 2024). |
| **Overhead Parsing Komputasi** | Nol (pembacaan nilai integer direct byte). | Sangat rendah (kalkulasi floating point sederhana). | Rendah hingga Sedang (transformasi matriks matriks ruang linear CIE XYZ internal). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Gamut Clipping & Hardware Fallback
* **Gejala:** Menentukan nilai Chroma ekstrem seperti `oklch(0.6 0.35 150)`. Pada layar sRGB standar, browser terpaksa memotong (*gamut clipping*) warna ke nilai sRGB terdekat yang dapat dicapai. Hal ini dapat menyebabkan dua token warna yang berbeda menghasilkan representasi visual yang persis sama di layar kelas menengah ke bawah.
* **Mitigasi:** Gunakan media query `@supports` atau *color gamut queries* (`@media (color-gamut: p3)`) untuk menurunkan Chroma secara elegan:
```css
:root {
  --badge-color: oklch(0.6 0.18 150); /* Rentang aman sRGB */
}
@media (color-gamut: p3) {
  :root {
    --badge-color: oklch(0.6 0.32 150); /* P3 Expanded Gamut */
  }
}
```

### 2. The Optical Sizing Paradox pada Variable Fonts
* **Gejala:** Font variabel dengan sumbu *optical sizing* (`opsz`) yang berjalan otomatis dapat mengubah proporsi x-height huruf pada resolusi dinamis. Hal ini berpotensi memicu wrapping kata tak terduga (*line-wrapping flicker*) persis di batas piksel tertentu.
* **Mitigasi:** Standarkan deklarasi `font-optical-sizing: auto;` dan pastikan kontainer memiliki ruang *inline-size padding* toleransi minimal `2px` untuk mengakomodasi rasterisasi sub-piksel.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan Hex/sRGB untuk Manipulasi State Interaktif
* **Salah:**
```css
/* Menghasilkan state hover yang kotor/tidak konsisten pada warna yang berbeda */
.btn-primary { background: #6200ee; }
.btn-primary:hover { filter: brightness(1.2); } /* Merusak akurasi saturasi */
```
* **Benar:**
```css
/* Mengatur lightness secara terprediksi di ruang warna Oklch */
:root {
  --btn-l: 0.45;
  --btn-c: 0.22;
  --btn-h: 275;
  --btn-bg: oklch(var(--btn-l) var(--btn-c) var(--btn-h));
}
.btn-primary {
  background-color: var(--btn-bg);
}
.btn-primary:hover {
  /* Naikkan Lightness secara konsisten tanpa merusak saturation vector */
  background-color: oklch(calc(var(--btn-l) + 0.08) var(--btn-c) var(--btn-h));
}
```

### 2. Formula Fluid Clamp Berbasis Satuan `px` Statis Murni
* **Salah:**
```css
/* Gagal ketika pengguna mengatur preferensi Zoom Font di OS/Browser accessibility */
font-size: clamp(16px, 2vw, 24px);
```
* **Benar:**
```css
/* Selalu hitung dan kaitkan min/max/intercept ke basis rem */
font-size: clamp(1rem, 0.8rem + 1vw, 1.5rem);
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Aturan Skala Modular Matematis (Typographic Modular Scale):** Pilih tepat satu rasio per produk (misal: *Minor Third* `1.200` untuk densitas tinggi enterprise B2B; *Major Third* `1.250` untuk SaaS dashboard; *Perfect Fourth* `1.333` untuk editorial konten). Jangan mencampur rasio tanpa justifikasi arsitektural.
2. **OpenType Features Explicit Declaration:** Jangan mengandalkan browser defaults untuk rendering angka tabel keuangan. Selalu deklarasikan secara eksplisit: `font-variant-numeric: tabular-nums lining-nums;` untuk tabel data.
3. **Pemberian Nama Token Bertingkat Tiga (Three-Tier Naming):**
   * *Primitive:* `--color-blue-500: oklch(0.55 0.22 260);`
   * *Semantic:* `--color-interactive-default: var(--color-blue-500);`
   * *Component:* `--button-primary-bg: var(--color-interactive-default);`

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

* **Woff2 Subsetting:** Hindari mendistribusikan berkas `.woff2` font utuh yang berukuran $>500\text{ KB}$ jika hanya memuat set karakter Latin. Gunakan alat seperti `pyftsubset` untuk membuang glyph yang tidak terpakai, menghasilkan ukuran berkas tipis di bawah $30\text{ KB}$.
* **Layer Minimization on Theme Swapping:** Jangan lakukan transisi tema (`theme swap`) dengan mereplace seluruh *stylesheet* link tag secara runtime (memicu pemblokiran parser CSSOM dan flash rendering kosong). Tukar tema murni melalui modifikasi atribut root (`documentElement.setAttribute('data-theme', 'dark')`) yang memicu kalkulasi ulang variabel CSS secara efisien tanpa pembongkaran pohon DOM.

---

## SEKSI 16 — KEAMANAN & HARDENING

* **CSS Injection via Custom Properties:** Saat mengekspos modifikasi tema visual kepada pengguna akhir (misal: *custom workspace colors*), jangan pernah merefleksikan masukan teks mentah langsung ke dalam blok inline `<style>`. Nilai warna kustom harus divalidasi secara ketat oleh regex sanitasi server/client sebelum diinjeksikan:
```typescript
const OKLCH_REGEX = /^oklch\((0(\.\d+)?|1(\.0+)?)\s+(0(\.\d+)?|0\.[0-3]\d*)\s+([0-9]|[1-8][0-9]|9[0-9]|[12][0-9]{2}|3[0-5][0-9]|360)(\.\d+)?(\s*\/\s*(0(\.\d+)?|1(\.0+)?))?\)$/;

export function sanitizeCustomColor(input: string): string {
  const sanitized = input.trim();
  if (!OKLCH_REGEX.test(sanitized)) {
    throw new SecurityError("Invalid color token format. Injection aborted.");
  }
  return sanitized;
}
```
* **Content Security Policy (CSP):** Hindari penggunaan `'unsafe-inline'` untuk style. Gunakan nonce-based style injection atau terapkan mutasi token hanya via CSS Object Model API (`document.documentElement.style.setProperty(...)`).

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

S