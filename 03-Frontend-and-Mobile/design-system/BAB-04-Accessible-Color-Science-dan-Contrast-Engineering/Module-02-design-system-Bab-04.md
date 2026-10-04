# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Accessible Color Science dan Contrast Engineering**

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal/Staff Frontend Engineer dan Design System Architect diharapkan mampu:
*   Menganalisis keterbatasan matematis WCAG 2.x Relative Luminance ($L_1/L_2$) dan mengimplementasikan algoritma **APCA (Accessible Perceptual Contrast Algorithm / WCAG 3 Candidate)** untuk persepsi kontras fotopik, mesopik, dan efek polaritas visual.
*   Merancang arsitektur generator palet warna berbasis ruang warna **OKLCH (Oklab Cylindrical)** dan **CAM16**, menggantikan model non-uniform seperti sRGB dan HSL untuk menjamin uniformitas persepsi (*perceptual uniformity*).
*   Mengembangkan *gamut mapping engine* deterministik (menggunakan teknik *binary search chroma reduction*) untuk menangani degradasi anggun (*graceful fallback*) dari Wide Gamut (Display P3) ke sRGB tanpa distorsi *hue* (*hue-shift*).
*   Membangun runtime token sistem warna adaptif enterprise yang mengeksekusi kalkulasi kontras dinamis, mendukung Windows High Contrast Mode (`forced-colors`), serta mengintegrasikan *automated contrast regression test* ke dalam CI/CD pipeline.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib menguasai:
1.  **Linear Algebra & Color Space Basics**: Pemahaman mengenai matriks transformasi ruang warna, CIE 1931 XYZ, sRGB Gamma Correction/EOTF (*Electro-Optical Transfer Function*), dan representasi koordinat silindris.
2.  **Advanced TypeScript & AST Manipulation**: Penguasaan TypeScript generic constraints, dynamic typing, serta manipulasi CSS AST melalui PostCSS atau Style Dictionary.
3.  **Modern CSS Specifications**: Implementasi native CSS Color Module Level 4 & 5 (`color(display-p3 x y z)`, `oklch()`, `color-mix()`, dan `@media (prefers-contrast)`).

---

### 3. Concept & Internal Architecture

#### Keterbatasan Fundamental WCAG 2.x Contrast Ratio

Formula kontras WCAG 2.1 dirumuskan sebagai:

$$CR = \frac{L_1 + 0.05}{L_2 + 0.05}$$

Di mana $L_1$ adalah *relative luminance* warna yang lebih terang dan $L_2$ adalah warna yang lebih gelap, dihitung via:

$$Y = 0.2126 R_{lin} + 0.7152 G_{lin} + 0.0722 B_{lin}$$

Kelemahan kritis dari formulasi ini meliputi:
1.  **Simetri Ilusif (Polarity Ignorance)**: WCAG 2.x memberikan rasio yang identik baik untuk teks hitam di atas latar putih maupun teks putih di atas latar hitam ($21:1$). Di mata manusia, fenomena *halation* / *irradiance* pada mode gelap menyebabkan teks putih dengan rasio tinggi di atas latar hitam pekat tampak berpendar dan kabur, memicu kelelahan mata (*asthenopia*).
2.  **Perceptual Non-Uniformity**: Rasio $4.5:1$ pada spektrum warna kuning menghasilkan keterbacaan yang sangat berbeda secara empiris dibandingkan $4.5:1$ pada spektrum biru tua.
3.  **Spatial Frequency Neglect**: WCAG 2.x mengabaikan ketebalan (*weight*), ukuran font (*size*), dan jarak pandang (*visual angle*).

#### Anatomi Algoritma APCA (SAPC / WCAG 3 candidate)

APCA memodelkan pemrosesan visual manusia (*human visual system* / HVS) mulai dari adaptasi fotoreseptor retina hingga kompresi non-linear pada korteks visual:

```
[ sRGB / Display P3 ]
         │
         ▼
[ Linearized RGB (EOTF Removal) ]
         │
         ▼
[ Y_estimated (Spectral Sensitivity: R, G, B Cones Weighting) ]
         │
         ▼
[ Photopic Adaptation / Clamping (Local Background Adaptation) ]
         │
         ▼
[ Non-linear Power Law Compression (Stevens' Power Law) ]
         │
         ▼
[ Polarized Differential Output: Lc (Lightness Contrast: -108 to +106) ]
```

APCA menghasilkan nilai bertanda $L^c$ (*Lightness Contrast*):
*   **Nilai Positif ($+L^c$)**: Teks gelap di atas latar terang (*dark mode context disabled / positive polarity*).
*   **Nilai Negatif ($-L^c$)**: Teks terang di atas latar gelap (*negative polarity*).

APCA menetapkan ambang batas minimum berbasis *spatial frequency*:
*   $L^c \ge 60$: Batas minimum mutlak teks konten (setara 16px Regular).
*   $L^c \ge 75$: Batas teks bacaan panjang (*body text*).
*   $L^c \ge 90$: Teks tipis atau ukuran kecil (14px thin/light).

#### Perceptual Uniformity: Dari HSL ke OKLCH

HSL meregangkan ruang warna sRGB ke dalam silinder tanpa mempertimbangkan sensitivitas mata terhadap luminansi. Pada HSL, `hsl(60, 100%, 50%)` (kuning murni) dan `hsl(240, 100%, 50%)` (biru murni) memiliki Lightness nominal yang sama ($50\%$), namun luminansi relatif aktualnya ($Y$) sangat kontras: Kuning bernilai $\sim0.93$, sedangkan Biru bernilai $\sim0.07$.

OKLCH memecahkan anomali ini melalui pemetaan silindris dari Oklab (diciptakan oleh Björn Ottosson, 2020):
*   **$L$ (Perceived Lightness)**: $0.0$ (hitam absolut) hingga $1.0$ (putih absolut). Direkayasa agar seragam secara persepsi di seluruh panjang gelombang.
*   **$C$ (Chroma)**: Kejenuhan warna visual dari $0.0$ (akromatik/abu-abu netral) hingga $\approx 0.4$ (tepi luar batas Display P3/Rec.2020).
*   **$H$ (Hue Angle)**: Sudut spektrum warna dalam derajat ($0^\circ - 360^\circ$).

Jika $L = 0.7$, maka warna apa pun—baik biru, kuning, hijau, maupun merah—memiliki tingkat keterangan seragam di mata manusia. Karakteristik ini memungkinkan otomatisasi pembuatan palet token semantik yang mathematically accessible.

---

### 4. Why & What

| Dimensi | Legacy System (sRGB + WCAG 2.1) | Enterprise Architecture (OKLCH + APCA) |
| :--- | :--- | :--- |
| **Model Warna Dasar** | sRGB / HSL (Non-linear, Non-uniform) | OKLCH / CIE CAM16 (Perceptually Uniform) |
| **Metrik Evaluasi Kontras** | WCAG 2.x Contrast Ratio ($1:1 - 21:1$) | APCA Lightness Contrast ($L^c\ -108$ hingga $+106$) |
| **Dukungan Polaritas** | Simetris (Mengabaikan efek *halation*) | Asimetris (Sensitivitas adaptasi gelap vs terang) |
| **Korelasi Tipografi** | Arbitrer ($4.5:1$ reguler, $3:1$ large text) | Terhubung matriks dinamis: Font Size $\times$ Font Weight |
| **Gamut Support** | Terbatas pada sRGB ($\approx 35\%$ visual spectrum) | Wide Gamut: Native Display P3 ($\approx 50\%$ visual) + Rec.2020 |
| **Dynamic Theming** | Rawan gagal kontras saat user mengubah aksen | Kontras terjamin deterministik secara matematis |

---

### 5. How (Workflow Detail)

Arsitektur orkestrasi warna enterprise memproses token melalui lintasan deterministik:

1.  **Seed Ingestion**: Mengambil warna dasar merek (*Brand Primary Seed*) dalam format Hex / CIE XYZ.
2.  **OKLCH Projection**: Mengonversi seed ke ruang OKLCH untuk mengekstrak $H$ (Hue) dan $C$ (Chroma).
3.  **Tonal Palette Quantization**: Membuat *lightness step* terkalibrasi ($L = 0.05, 0.10, \dots, 0.95, 0.98$).
4.  **Gamut Boundary Detection**: Menguji apakah kombinasi $(L, C, H)$ berada di dalam ruang target (Display P3 atau sRGB). Jika di luar batas, terapkan algoritma **Chroma Clipping via Binary Search** dengan mempertahankan nilai $L$ dan $H$ agar tidak terjadi pergeseran warna visual (*hue-shift*).
5.  **Semantic Mapping & APCA Matrix Verification**: Memetakan pasangan warna permukaan (*surface*) dan konten (*on-surface*). Algoritma APCA mengevaluasi apakah token memenuhi ambang batas $L^c$ sesuai target tipografi.
6.  **CSS Token Serialization**: Mengekspor token ke format CSS Custom Properties yang mendukung `@supports (color: color(display-p3 1 1 1))` dengan fallback sRGB.

---

### 6. Analogy & Diagram ASCII

Bayangkan HSL sebagai bukit gunung es berbentuk kerucut yang dipaksa dimasukkan ke dalam kaleng silinder. Bagian puncak (kuning) tertekan dan bagian dasar (biru) terdistorsi, sehingga ketika Anda memotong secara horizontal pada ketinggian 50%, Anda memotong es tebal di satu sisi dan udara kosong di sisi lain.

OKLCH memetakan gunung es tersebut secara presisi di ruang terbuka berdasarkan massa visual aslinya:

```
[Ruang Warna HSL]                   [Ruang Warna OKLCH]
Bentuk: Silinder Artifisial          Bentuk: Asimetris Alami Tubuh Warna
      ┌───────────┐                         .---.  <- Kuning (Chroma Max di L tinggi)
      │  Kuning   │                        /     \
  L50%├─── ─── ───┤                    ┌──/───────\──┐ L70% (Kuning & Biru
      │   Biru    │                    │ /         \ │       memiliki luminansi visual
      └───────────┘                    │/     .----.\|       yang sama persis)
Non-uniform: Kuning sangat terang,     │     / Biru \│ L30% (Chroma Max di L rendah)
Biru sangat gelap pada level L sama.   └────/────────\┘
                                           '---------'
```

#### Pipeline Resolusi Token Runtime

```
[Design Input: OKLCH Seed]
           │
           ▼
┌──────────────────────────────────────────────┐
│        Gamut Space Check Engine              │
│ Is (L, C, H) inside Target Gamut Canvas?     │
└──────────────┬───────────────────────────────┘
               │
       ┌───────┴───────┐
      YES              NO
       │               ▼
       │      ┌─────────────────────────┐
       │      │ Binary Search Gamut Map │
       │      │ Reduce Chroma (Hold L,H)│
       │      └────────┬────────────────┘
       │               │
       ├───────────────┘
       ▼
┌──────────────────────────────────────────────┐
│        APCA Contrast Verification Unit       │
│ Calculates Lc against target surfaces        │
│ Threshold: |Lc| >= target (e.g., 75 for body)│
└──────────────┬───────────────────────────────┘
               │
               ▼
[CSS AST Compiler: Variable Injection Engine]
   ├── Output fallback: sRGB oklch/hex
   └── Output @supports: color(display-p3 ...)
```

---

### 7. Implementation: Simple vs Production

#### Simple Example: Perhitungan WCAG 2.1 vs APCA Sederhana (TypeScript)

Berikut adalah demonstrasi mendasar perbedaan kalkulasi kontras WCAG 2.x dengan aproksimasi APCA:

```typescript
// simple-contrast.ts

export function parseHexToLinearRGB(hex: string): [number, number, number] {
  const bigint = parseInt(hex.replace('#', ''), 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;

  return [r, g, b].map((val) => {
    const s = val / 255;
    return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  }) as [number, number, number];
}

// 1. Standar WCAG 2.1
export function calculateWCAG2(fgHex: string, bgHex: string): number {
  const [r1, g1, b1] = parseHexToLinearRGB(fgHex);
  const [r2, g2, b2] = parseHexToLinearRGB(bgHex);

  const l1 = 0.2126 * r1 + 0.7152 * g1 + 0.0722 * b1;
  const l2 = 0.2126 * r2 + 0.7152 * g2 + 0.0722 * b2;

  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);

  return (lighter + 0.05) / (darker + 0.05);
}

// 2. Aproksimasi Fundamental APCA (SAPC v0.98G simplified constants)
export function calculateSimpleAPCA(txtHex: string, bgHex: string): number {
  const [rTxt, gTxt, bTxt] = parseHexToLinearRGB(txtHex);
  const [rBg, gBg, bBg] = parseHexToLinearRGB(bgHex);

  // Spectral Sensitivity coefficients (retinal cone weights)
  const yTxt = 0.2126729 * rTxt + 0.7151522 * gTxt + 0.0721750 * bTxt;
  const yBg = 0.2126729 * rBg + 0.7151522 * gBg + 0.0721750 * bBg;

  // Clamping threshold for sub-threshold darks
  const yTxtClamped = yTxt > 0.001 ? yTxt : 0.001;
  const yBgClamped = yBg > 0.001 ? yBg : 0.001;

  // Non-linear power-law perceptual compression
  const textComp = Math.pow(yTxtClamped, 0.57); // Soft power curve text
  const bgComp = Math.pow(yBgClamped, 0.56);   // Soft power curve background

  // Polarity determination
  const diff = textComp - bgComp;
  
  // Output Lc (Lightness Contrast) scaled to human-readable index
  return diff * 100;
}

// Eksekusi Anomali Kasus: Biru Tua vs Hitam
const blackBg = '#000000';
const darkBlueTxt = '#1a365d';

console.log('WCAG 2.1 Ratio:', calculateWCAG2(darkBlueTxt, blackBg).toFixed(2)); 
// Output: ~1.44:1 (Fail mutlak di WCAG)
console.log('APCA Lightness Contrast (Lc):', calculateSimpleAPCA(darkBlueTxt, blackBg).toFixed(2));
// Memberikan nilai presisi polaritas negatif terkompresi
```

---

#### Practical Enterprise Example: Dynamic Color Architecture Engine

Berikut implementasi engine modular berskala produksi: konversi OKLCH, Gamut Mapping via Binary Search ke Display P3/sRGB, APCA Engine level produksi, serta dynamic CSS token injection.

```typescript
// color-engine.ts

export interface OKLCH {
  l: number; // 0.0 to 1.0 (Lightness)
  c: number; // 0.0 to ~0.4 (Chroma)
  h: number; // 0.0 to 360.0 (Hue in degrees)
}

export interface RGB {
  r: number; // 0.0 to 1.0 (Linear sRGB)
  g: number;
  b: number;
}

// --- Ruang Warna OKLab/OKLCH Transform Matrices ---
export class OKLCHEngine {
  static oklchToOklab(c: OKLCH): [number, number, number] {
    const hRad = (c.h * Math.PI) / 180;
    const a = c.c * Math.cos(hRad);
    const b = c.c * Math.sin(hRad);
    return [c.l, a, b];
  }

  static oklabToLinearSRGB(L: number, a: number, b: number): RGB {
    const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
    const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
    const s_ = L - 0.0894841775 * a - 1.2914855480 * b;

    const l = l_ * l_ * l_;
    const m = m_ * m_ * m_;
    const s = s_ * s_ * s_;

    return {
      r: +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
      g: -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
      b: -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    };
  }

  static linearToGammaSRGB(linear: number): number {
    return linear <= 0.0031308
      ? linear * 12.92
      : 1.055 * Math.pow(linear, 1.0 / 2.4) - 0.055;
  }

  static isInSRGBGamut(rgb: RGB): boolean {
    const epsilon = 1e-4;
    return (
      rgb.r >= -epsilon && rgb.r <= 1.0 + epsilon &&
      rgb.g >= -epsilon && rgb.g <= 1.0 + epsilon &&
      rgb.b >= -epsilon && rgb.b <= 1.0 + epsilon
    );
  }

  /**
   * Mengurangi Chroma secara biner jika warna di luar gamut sRGB,
   * mempertahankan Lightness (L) dan Hue (H) konstan untuk mencegah hue-shifting.
   */
  static fitIntoSRGB(target: OKLCH): OKLCH {
    const [origL, origA, origB] = this.oklchToOklab(target);
    const testRGB = this.oklabToLinearSRGB(origL, origA, origB);

    if (this.isInSRGBGamut(testRGB)) {
      return target;
    }

    let minChroma = 0.0;
    let maxChroma = target.c;
    let currentTarget = { ...target };

    // Binary search gamut mapping: 10 iterasi memberikan akurasi ~0.0003
    for (let i = 0; i < 10; i++) {
      const midChroma = (minChroma + maxChroma) / 2;
      currentTarget.c = midChroma;
      const [l, a, b] = this.oklchToOklab(currentTarget);
      const res = this.oklabToLinearSRGB(l, a, b);

      if (this.isInSRGBGamut(res)) {
        minChroma = midChroma;
      } else {
        maxChroma = midChroma;
      }
    }

    currentTarget.c = minChroma;
    return currentTarget;
  }
}

// --- APCA 0.98G Full Contrast Math Model ---
export class APCAEngine {
  private static readonly R_COEFF = 0.2126729;
  private static readonly G_COEFF = 0.7151522;
  private static readonly B_COEFF = 0.0721750;

  private static readonly NORMOFFSET = 0.1;
  private static readonly REVOFFSET = 0.05;

  static calcLuminance(rgb: RGB): number {
    return (
      this.R_COEFF * Math.max(0, rgb.r) +
      this.G_COEFF * Math.max(0, rgb.g) +
      this.B_COEFF * Math.max(0, rgb.b)
    );
  }

  static calculateContrast(textRgb: RGB, bgRgb: RGB): number {
    const yTxt = this.calcLuminance(textRgb);
    const yBg = this.calcLuminance(bgRgb);

    // Clamping output per APCA standard
    const clampedTxt = yTxt > 0.001 ? yTxt : 0.001;
    const clampedBg = yBg > 0.001 ? yBg : 0.001;

    let contrast = 0.0;

    // Positive Polarity (Dark Text on Light Background)
    if (clampedBg > clampedTxt) {
      const sBg = Math.pow(clampedBg, 0.56);
      const sTxt = Math.pow(clampedTxt, 0.57);
      contrast = (sBg - sTxt) * 100 - this.NORMOFFSET;
      return contrast < 0 ? 0 : contrast;
    }

    // Negative Polarity (Light Text on Dark Background)
    const sBg = Math.pow(clampedBg, 0.65);
    const sTxt = Math.pow(clampedTxt, 0.62);
    contrast = (sBg - sTxt) * 100 + this.REVOFFSET;
    return contrast > 0 ? 0 : contrast;
  }
}

// --- Dynamic Token Generator Runtime ---
export interface SemanticPaletteDefinition {
  seedHue: number;
  chroma: number;
}

export class AccessibleDesignTokenEngine {
  static generateTonalScale(seed: SemanticPaletteDefinition) {
    const lightnessSteps = [
      { step: 50,  L: 0.98 },
      { step: 100, L: 0.93 },
      { step: 200, L: 0.85 },
      { step: 300, L: 0.75 },
      { step: 400, L: 0.65 },
      { step: 500, L: 0.55 },
      { step: 600, L: 0.45 },
      { step: 700, L: 0.35 },
      { step: 800, L: 0.25 },
      { step: 900, L: 0.15 },
      { step: 950, L: 0.08 },
    ];

    return lightnessSteps.map(({ step, L }) => {
      const rawOklch: OKLCH = { l: L, c: seed.chroma, h: seed.seedHue };
      const fittedOklch = OKLCHEngine.fitIntoSRGB(rawOklch);
      const [oLabL, a, b] = OKLCHEngine.oklchToOklab(fittedOklch);
      const linearRgb = OKLCHEngine.oklabToLinearSRGB(oLabL, a, b);

      const r = Math.min(255, Math.max(0, Math.round(OKLCHEngine.linearToGammaSRGB(linearRgb.r) * 255)));
      const g = Math.min(255, Math.max(0, Math.round(OKLCHEngine.linearToGammaSRGB(linearRgb.g) * 255)));
      const blue = Math.min(255, Math.max(0, Math.round(OKLCHEngine.linearToGammaSRGB(linearRgb.b) * 255)));

      return {
        step,
        oklchString: `oklch(${fittedOklch.l.toFixed(3)} ${fittedOklch.c.toFixed(3)} ${fittedOklch.h.toFixed(1)})`,
        p3String: `color(display-p3 ${(r / 255).toFixed(3)} ${(g / 255).toFixed(3)} ${(blue / 255).toFixed(3)})`,
        hexString: `#${((1 << 24) + (r << 16) + (g << 8) + blue).toString(16).slice(1)}`,
        linearRgb,
      };
    });
  }

  static buildAccessiblePair(
    bgStep: number,
    textStepCandidate: number,
    scale: ReturnType<typeof AccessibleDesignTokenEngine.generateTonalScale>,
    minLcRequired: number = 75
  ) {
    const bg = scale.find((s) => s.step === bgStep)!;
    const txt = scale.find((s) => s.step === textStepCandidate)!;

    const lc = APCAEngine.calculateContrast(txt.linearRgb, bg.linearRgb);

    if (Math.abs(lc) < minLcRequired) {
      throw new Error(
        `Contrast Violation: Pair Bg-${bgStep} and Text-${textStepCandidate} produces Lc = ${lc.toFixed(
          1
        )}, which is below required |${minLcRequired}|`
      );
    }

    return {
      background: bg.oklchString,
      fallbackBackground: bg.hexString,
      text: txt.oklchString,
      fallbackText: txt.hexString,
      evaluatedLc: lc,
    };
  }
}

// --- Execution Validation ---
const scale = AccessibleDesignTokenEngine.generateTonalScale({ seedHue: 250, chroma: 0.18 });
const semanticPair = AccessibleDesignTokenEngine.buildAccessiblePair(50, 900, scale, 75);

console.log('Deterministic Compliant Semantic Tokens:', semanticPair);
```

---

### 8. Real World Case Study: Financial Trading Terminal

#### Kasus Arsitektur
Sebuah enterprise fintech membangun dashboard terminal transaksi multiaset (mata uang, opsi, obligasi) dengan jutaan transaksi per detik. Sistem UI harus mendukung variasi dynamic lighting: mulai dari lantai bursa yang sangat terang hingga ruangan analisis kuantitatif yang gelap pekat.

#### Masalah Sistem Legacy
1.  **Kegagalan WCAG 2.1 pada Indikator Keuntungan/Kerugian**: Indikator tren warna hijau (`#00FF00`) dan merah (`#FF0000`) pada latar belakang gelap lolos uji WCAG 2.1 (rasio $> 5:1$). Namun secara visual, warna hijau berpendar secara agresif (*halation*), sedangkan teks merah tua menjadi tidak terbaca oleh pengguna dengan *deuteranopia* dan *protanopia*.
2.  **Gamut Inconsistency**: Pada monitor wide-gamut Display P3 (seperti Apple Retina Display), saturasi warna hijau memotong batas persepsi hingga menyamarkan detail angka desimal di belakang koma.

#### Solusi Berbasis Arsitektur Kontras Baru
1.  **Standarisasi OKLCH**: Palet *gain* dan *loss* dikunci pada nilai Lightness visual identik:
    *   `Gain`: `oklch(0.72 0.16 142)`
    *   `Loss`: `oklch(0.72 0.16 29)`
    Kedua warna memiliki persepsi keterangan visual yang setara ($L = 0.72$), mengeliminasi bias psikologis di mana pengguna merasa angka *gain* secara visual lebih "dekat" atau lebih penting daripada *loss*.
2.  **Dynamic APCA Enforcer**: Token teks runtime divalidasi dengan batas APCA $|L^c| \ge 75$ untuk seluruh tick data tabular, memastikan angka desimal tetap terbaca tanpa latensi komputasi berlebih.
3.  **Forced Colors Support**: Menyediakan fallback otomatis ke semantic system colors saat terminal mendeteksi mode *High Contrast* aktif pada sistem operasi Windows.

---

### 9. Trade-offs

```
                  Client-side Dynamic Runtime
                             ▲
                            / \
                           /   \
  [Fleksibilitas Tinggi]  /     \  [High Runtime Overhead]
  [Dynamic Accent Color] /       \ [Layout Shifts/FOUC Risk]
                        /         \
                       /           \
                      /             \
  Zero Runtime Static ─────────────── Hybrid Build & Compile-time
  Tokens (Pure CSS)                   Tokens (Akselerasi Edge/SSR)
  [Kecepatan Maksimal]                [Toleransi Dinamis Terbatas]
  [Zero Memory Footprint]             [Build Matrix Meledak]
```

| Pendekatan | Latensi Eksekusi | Performa Memory | Fleksibilitas Tema | Kompleksitas CI/CD |
| :--- | :--- | :--- | :--- | :--- |
| **Pure Build-Time Static (PostCSS / Style-Dict)** | $0\text{ ms}$ (Native CSS parsing) | Minimal (Hanya CSS standard custom properties) | Sangat Kaku (Hanya varian tema yang didefinisikan saat build) | Sederhana (Linting berbasis file static) |
| **Client-Side Dynamic OKLCH/APCA Engine** | $15\text{ ms} - 45\text{ ms}$ saat inisialisasi thread utama | Overhead kalkulasi matriks warna pada DOM tree besar | Sangat Fleksibel (User bisa memilih semantic accent bebas) | Menengah (Perlu runtime assertion boundary) |
| **Hybrid Worker-Driven Gamut Resolution** | $< 2\text{ ms}$ (Offloaded ke Web Worker / Off-main thread) | Menengah (Caching tonal palettes di IndexedDB/Memory) | Tinggi (Mendukung tenant enterprise multi-brand secara live) | Tinggi (Pipeline enkapsulasi CSS Object Model) |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Gamut Clipping Clashing (Pergeseran Hue saat Clipping Sederhana)
*   **Kesalahan**: Memotong (*clamping*) nilai RGB yang meluap dari OKLCH dengan `Math.min(1.0, Math.max(0, val))`. Hal ini merusak rasio saluran RGB dan memicu pergeseran hue secara radikal (misal: warna ungu bergeser menjadi biru kusam).
*   **Mitigasi**: Gunakan *Chroma Reduction along constant Hue & Lightness*. Pertahankan nilai $L$ dan $H$, lalu kurangi nilai $C$ via binary search hingga koordinat linear RGB mendarat tepat di batas gamut target ($[0.0, 1.0]$).

#### 2. Polaritas Terbalik pada APCA Calculation
*   **Kesalahan**: Mengabaikan tanda minus pada kalkulasi APCA dan hanya menggunakan `Math.abs(lc)`.
*   **Dampak Negatif**: Teks terang di atas latar gelap bernilai negatif ($-L^c$). Kebutuhan kontras absolut untuk teks terang di latar gelap berbeda secara optik dari teks gelap di latar terang. 
*   **Mitigasi**: Selalu definisikan skala target berdasarkan polaritas:
    ```typescript
    const isDarkTheme = backgroundLuminance < 0.18;
    const requiredThreshold = isDarkTheme ? -75 : 60; // Nilai Lc
    ```

#### 3. Rusaknya Semantic Colors pada CSS `forced-colors: active`
*   **Kesalahan**: Menimpa token warna sistem saat Windows High Contrast Mode aktif menggunakan `!important`.
*   **Mitigasi**: Gunakan media query `@media (forced-colors: active)` dan map styling penting ke System Color keywords:
    ```css
    @media (forced-colors: active) {
      .trading-button-primary {
        background-color: ButtonFace;
        color: ButtonText;
        border: 2px solid Highlight;
      }
    }
    ```

---

### 11. Best Practices (Production Checklist)

*   [ ] **Gunakan OKLCH sebagai Source of Truth**: Definisikan seluruh master seed tokens dalam format `oklch(L C H)`. Hindari manipulasi HSL untuk palet enterprise.
*   [ ] **Sediakan Dual Architecture Support via CSS `@supports`**:
    ```css
    :root {
      --brand-primary: #1a56db; /* Fallback sRGB Legacy */
    }
    @supports (color: oklch(0.5 0.2 250)) {
      :root {
        --brand-primary: oklch(0.52 0.22 254.1); /* Native Wide Gamut Engine */
      }
    }
    ```
*   [ ] **Standar Ambang Batas Kontras APCA untuk Desain UI**:
    *   Teks Konten Inti / Input Form: Minimal $|L^c| \ge 75$.
    *   Headline Besar ($\ge 24\text{px}$ Bold / $\ge 32\text{px}$ Normal): Minimal $|L^c| \ge 60$.
    *   Placeholder / Disabled State / Ikon Non-Kritis: Minimal $|L^c| \ge 45$.
*   [ ] **Gunakan Spatial Frequency Matrix**: Kaitkan ukuran font dan tebal font secara dinamis dengan syarat $L^c$. Jangan tetapkan kontras seragam untuk seluruh skala tipografi.
*   [ ] **Subpixel Anti-Aliasing Compensation**: Pada sistem operasi macOS dan Windows dengan subpixel rendering, perhitungkan penurunan kontras teoritis sebesar $\approx 5\%\text{ - }8\%$ akibat *smoothing filter*. Berikan bantalan margin keselamatan (+5 $L^c$) pada token teks kritis.

---

### 12. Hands-on Practice

Buatlah tool generator palet warna mandiri di folder proyek `hands-on/m02/` dengan langkah-langkah berikut:

#### Step 1: Inisialisasi Project Directory
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install typescript @types/node ts-node --save-dev
npx tsc --init
```

#### Step 2: Konfigurasi `tsconfig.json`
Pastikan konfigurasi mendukung ESNext module resolution:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "lib": ["ES2022"],
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist"
  },
  "include": ["src/**/*"]
}
```

#### Step 3: Implementasi Script Generator
Buat file `src/generate-tokens.ts`. Salin seluruh implementasi kelas `OKLCHEngine`, `APCAEngine`, dan `AccessibleDesignTokenEngine` dari Seksi 7 (Practical Example). Tambahkan fungsionalitas penulisan file otomatis ke format CSS:

```typescript
// src/generate-tokens.ts
import * as fs from 'fs';
import * as path from 'path';
import { AccessibleDesignTokenEngine } from './color-engine'; // Exported logic

const primaryScale = AccessibleDesignTokenEngine.generateTonalScale({ seedHue: 220, chroma: 0.16 });
const neutralScale = AccessibleDesignTokenEngine.generateTonalScale({ seedHue: 220, chroma: 0.02 });

let cssOutput = `/**
 * Generated by Accessible Enterprise Color Science Engine
 * Standards: OKLCH, APCA, Display-P3 Fallback
 */

:root {\n`;

// Generate Neutral Tokens
neutralScale.forEach((s) => {
  cssOutput += `  --color-neutral-${s.step}: ${s.hexString};\n`;
  cssOutput += `  --color-neutral-${s.step}-oklch: ${s.oklchString};\n`;
});

// Generate Primary Tokens
primaryScale.forEach((s) => {
  cssOutput += `  --color-primary-${s.step}: ${s.hexString};\n`;
  cssOutput += `  --color-primary-${s.step}-oklch: ${s.oklchString};\n`;
});

cssOutput += `}\n`;

const outputPath = path.join(__dirname, 'tokens.css');
fs.writeFileSync(outputPath, cssOutput, 'utf-8');
console.log(`Tokens successfully generated at: ${outputPath}`);
```

#### Step 4: Eksekusi dan Verifikasi
Jalankan kompilasi:
```bash
npx ts-node src/generate-tokens.ts
```
Periksa file `tokens.css` yang dihasilkan dan amati bagaimana nilai Chroma menurun otomatis saat mendekati level ekstrim ($L = 0.98$ dan $L = 0.08$) untuk mempertahankan kepatuhan terhadap sRGB boundary.

---

### 13. Exercise

#### Level Easy
Buat fungsi verifikasi matematis dalam TypeScript: Diberikan dua nilai string RGB (`rgb(r, g, b)`), kembalikan `boolean` apakah pasangan tersebut lolos ambang batas standar WCAG 2.1 AA untuk teks reguler ($\ge 4.5:1$).

#### Level Medium
Kembangkan algoritma *gamut mapping* yang tidak hanya menguji ruang warna sRGB, tetapi juga memvalidasi apakah koordinat OKLCH target berada di dalam ruang warna **Display P3**. Jika berada di luar Display P3, terapkan *binary search chroma reduction*. Jika berada di dalam Display P3 tetapi di luar sRGB, hasilkan dua varian token: varian native sRGB dan varian `@supports color(display-p3 ...)`.

#### Level Hard
Buat modul komputasi dinamis yang menerima input satu buah *Surface Background Color* arbitrer dari user (misal: warna background dashboard kustom). Engine harus secara otomatis mencari nilai $L$ (Lightness) terdekat pada skala OKLCH yang menghasilkan nilai APCA $|L^c| \ge 75$ untuk teks di atasnya, dengan syarat meminimalkan lonjakan perbedaan kontras berlebih ($|L^c| \le 90$) guna mencegah terjadinya *halation artifacts* pada dark mode.

---

### 14. Challenge

**Skenario**: Sistem Operasi dan Browser Enterprise Anda menuntut arsitektur *Zero-FOUC (Flash of Unstyled Content) Accessible Dynamic Theming Engine* yang berjalan di lingkungan Micro-Frontend dengan 12 sub-aplikasi yang terisolasi di dalam Shadow DOM.

**Persyaratan Arsitektur Tantangan**:
1.  **Dynamic Ambient Adaptation**: Sistem harus mengubah contrast profile secara otonom ketika ambient light sensor mendeteksi perubahan intensitas cahaya ruangan tanpa merusak CSS cache.
2.  **No Pre-calculated Palettes**: Dilarang menggunakan lookup table atau palet statis. Seluruh token turunan semantik harus dihitung melalui koordinat trigonometri warna dalam CSS Houdini Typed OM atau *lightweight linear algebraic transform* micro-library (kapasitas bundle $\le 2.5\text{ KB}$).
3.  **Strict Performance Target**: Waktu eksekusi resolusi token dari seed hingga injeksi variable harus diselesaikan dalam durasi $\le 8\text{ ms}$ (kurang dari frame budget 120 FPS / $8.33\text{ ms}$) pada perangkat low-tier CPU (Snapdragon 400 series setara).
4.  **APCA Validation Assertion**: Sistem wajib mengeksekusi *runtime invariant check*. Jika sebuah micro-frontend mencoba me-render pasangan warna dengan ambang batas $|L^c| < 60$, UI komponen tersebut harus fallback ke sistem high-contrast monochrome secara aman tanpa melempar fatal exception ke console browser.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level (5 Soal)

1.  Mengapa ruang warna sRGB dan HSL dianggap tidak memadai untuk sistem kalkulasi palet warna otomatis?
    *   A. Karena tidak mendukung transparansi kanal Alpha.
    *   B. Karena tidak memiliki keseragaman persepsi (*perceptual uniformity*); nilai Lightness pada HSL tidak berkorelasi linier dengan luminansi visual aktual.
    *   C. Karena format string-nya tidak kompatibel dengan CSS Variables.
    *   D. Karena CSS Color Module Level 4 telah menghapus dukungan untuk HSL.

2.  Apa yang dimaksud dengan fenomena *halation* (*irradiance*) dalam desain UI kontras tinggi?
    *   A. Menghilangnya warna latar belakang saat monitor mengalami overheat.
    *   B. Efek visual di mana teks putih murni di atas latar hitam pekat tampak berpendar dan kabur di mata manusia, memicu kelelahan visual.
    *   C. Pergeseran hue dari ungu ke biru ketika chroma dipotong secara linier.
    *   D. Penurunan frame rate akibat kalkulasi kontras pada UI thread.

3.  Dalam ruang warna OKLCH, apa representasi dari parameter $L$, $C$, dan $H$?
    *   A. Linear, Cyan, Hue.
    *   B. Lightness (Keterangan Persepsi), Chroma (Kejenuhan/Kemurnian), Hue (Sudut Nada Warna).
    *   C. Luminance, Contrast, Halation.
    *   D. Level, Color, Highlight.

4.  Berapakah rasio kontras maksimum absolut yang dapat dihasilkan oleh algoritma WCAG 2.1?
    *   A. $100:1$
    *   B. $10:1$
    *   C. $21:1$
    *   D. $+106\ L^c$

5.  Nilai kontras APCA ($L^c$) dapat bernilai negatif. Apa indikasi dari nilai negatif tersebut?
    *   A. Formula kalkulasi kontras mengalami pembagian dengan nol (*error*).
    *   B. Kontras berada di bawah standar aksesibilitas minimum.
    *   C. Polaritas negatif: Teks terang berada di atas latar belakang gelap (*dark mode context*).
    *   D. Warna berada di luar cakupan gamut Display P3.

#### Intermediate Level (5 Soal)

6.  Apa kelemahan utama dari metode Gamut Clipping sederhana (*clamping* langsung ke rentang $[0, 255]$ pada sRGB)?
    *   A. Waktu komputasi yang terlalu lama ($\mathcal{O}(n^2)$).
    *   B. Terjadinya distorsi *hue-shift* yang drastis akibat perubahan proporsi vektor linear antar-kanal RGB.
    *   C. Nilai alpha transparansi menjadi hilang.
    *   D. Mengakibatkan memory leak pada rendering engine browser Chromium.

7.  Pada algoritma APCA, mengapa ambang batas kontras untuk teks tipis/kecil membutuhkan nilai $|L^c|$ yang lebih tinggi dibandingkan teks berukuran besar/tebal?
    *   A. Karena APCA memodelkan *Spatial Frequency Response* dari sistem visual manusia; mata membutuhkan kontras luminansi lebih tinggi untuk mengenali detail spasial frekuensi tinggi.
    *   B. Karena teks berukuran kecil mengonsumsi memori GPU lebih sedikit.
    *   C. Untuk memenuhi standar backward-compatibility dengan WCAG 1.0.
    *   D. Karena ukuran teks berbanding terbalik dengan kecerahan lampu latar monitor.

8.  Mengapa algoritma pencarian biner (*binary search*) dipilih dalam proses *gamut mapping* OKLCH ke sRGB?
    *   A. Mengurangi latensi komputasi dengan mempertahankan $L$ dan $H$ konstan seraya menemukan batas Chroma ($C$) maksimum yang valid secara deterministik.
    *   B. Karena ruang warna sRGB berbentuk kubus sempurna di dalam ruang koordinat silindris.
    *   C. Untuk mengonversi koordinat polar menjadi koordinat kartesian secara instan.
    *   D. Binary search merupakan satu-satunya metode yang didukung oleh spesifikasi CSS Houdini.

9.  Bagaimana arsitektur token modern menangani pengguna yang mengaktifkan *Windows High Contrast Mode*?
    *   A. Memaksa injeksi script JavaScript untuk mengganti semua elemen warna menjadi hitam putih.
    *   B. Mematikan seluruh CSS file eksternal dari server.
    *   C. Menggunakan media feature `@media (forced-colors: active)` dan memetakan komponen ke *system color keywords* standar CSS.
    *   D. Mengalihkan pengguna ke subdomain khusus aksesibilitas (misal: `accessible.domain.com`).

10. Jika kita mempertahankan nilai Lightness $L = 0.65$ konstan di seluruh spektrum Hue ($0^\circ - 360^\circ$) pada OKLCH, apa implikasinya terhadap luminansi visual manusia?
    *   A. Setiap warna akan tampak memiliki tingkat terang yang seragam di mata manusia, terlepas dari apakah warnanya biru, hijau, atau kuning.
    *   B. Warna kuning akan selalu tampak jauh lebih terang daripada warna biru seperti halnya pada HSL.
    *   C. Seluruh warna akan otomatis terkonversi menjadi skala abu-abu (*grayscale*).
    *   D. Nilai gamut akan otomatis terpotong ke rentang sRGB.

#### Case Study Analysis (3 Skenario Produksi)

11. **Skenario 1**: Sebuah tim audit menemukan bahwa tombol dengan background `#2563EB` (Primary Blue) dan label teks `#93C5FD` (Light Blue) memiliki rasio kontras WCAG 2.1 sebesar $4.6:1$ (dinyatakan Lolos AA). Namun, pengguna dengan *low-vision* melaporkan bahwa tombol tersebut sangat sulit dibaca di lapangan. Ketika dianalisis dengan APCA, nilai kontrasnya hanya menghasilkan $L^c \approx 38$. Langkah rekayasa apa yang paling tepat diambil?
    *   A. Mengabaikan laporan audit karena sistem telah lolos uji regulasi hukum WCAG 2.1 AA.
    *   B. Menaikkan ketebalan border tombol tanpa mengubah warna latar atau teks.
    *   C. Memperbarui pipeline token untuk menetapkan validasi APCA minimum $|L^c| \ge 60$ untuk tombol interaktif, yang secara otomatis akan menurunkan Lightness latar belakang atau menaikkan Lightness teks hingga mencapai threshold persepsi.
    *   D. Mengubah teks tombol menjadi uppercase secara global melalui CSS.

12. **Skenario 2**: Sistem rendering token dinamis Anda pada aplikasi mobile banking berbasis WebView mengalami *frame drop* (jank) parah saat pengguna menggeser slider tema (*theme tint slider*). Profiling devtools menunjukkan beban berlebih pada eksekusi fungsi JavaScript yang memproses konversi ruang warna untuk $1.200$ elemen DOM secara berulang di UI thread. Solusi arsitektur mana yang paling optimal?
    *   A. Menghapus fitur slider tema dinamis dari aplikasi.
    *   B. Mengubah perhitungan warna menjadi pemanggilan API synchronous ke backend Node.js.
    *   C. Memindahkan perhitungan palet token ke Web Worker atau menerapkan CSS Custom Properties runtime scoping pada level root (`:root`), sehingga JS hanya menghitung ulang 1 set master seed tokens ($< 10$ kalkulasi) dan menyerahkan resolusi pewarnaan turunan ke CSS native engine browser.
    *   D. Mengurangi resolusi layar WebView pengguna menjadi $720\text{p}$.

13. **Skenario 3**: Dalam pipeline CI/CD Design System, serangkaian unit test contrast checking berbasis WCAG 2.1 mendadak gagal (*broken build*) setelah tim desain mengekspor palet warna baru dari Figma yang dirancang menggunakan ruang warna Display P3. Tim desain bersikeras warna tersebut terlihat sempurna di layar monitor modern mereka. Tindakan teknis apa yang harus diambil oleh Principal Frontend Architect?
    *   A. Memaksa tim desain untuk kembali menggunakan perangkat monitor standar sRGB era 1990-an.
    *   B. Mematikan testing aksesibilitas di CI pipeline agar rilis tidak terhambat.
    *   C. Memodifikasi test runner di CI untuk mengisolasi evaluasi warna Display P3 dengan Color Gamut Mapping assertions, dan menyediakan build target dual-output: menghasilkan token fallback sRGB via chroma-reduction deterministik serta token P3 via CSS `@supports`, seraya memvalidasi keduanya dengan matriks kontras APCA.
    *   D. Mengonversi seluruh kode warna CSS menjadi format HSL string.

---

### Kunci Jawaban & Rasionalisasi Quiz

1.  **B**: Ruang warna HSL tidak seragam secara persepsi (*perceptually uniform*). Sebagai contoh, Lightness nominal $50\%$ pada HSL kuning memiliki luminansi aktual visual yang jauh lebih tinggi dibandingkan Lightness nominal $50\%$ pada HSL biru.
2.  **B**: Fenomena *halation* terjadi akibat pembiasan cahaya di dalam lensa mata pada kontras ekstrim di latar gelap, menyebabkan karakter teks putih tampak mengembang dan berpendar (*glow effect*), yang mempercepat kelelahan mata.
3.  **B**: $L$ merepresentasikan Perceived Lightness ($0.0 - 1.0$), $C$ merepresentasikan Chroma ($0.0 - \sim0.4$), dan $H$ merepresentasikan sudut Hue dalam lingkaran $0^\circ - 360^\circ$.
4.  **C**: Batas maksimal rasio WCAG 2.x adalah $21:1$ (perbandingan antara Putih murni $L=1.0$ dengan Hitam murni $L=0.0$).
5.  **C**: APCA memodelkan asimetri polaritas penglihatan manusia. Tanda minus ($-L^c$) secara eksplisit menandakan teks terang di atas latar gelap (*negative polarity*), yang memiliki karakteristik ambang batas fisiologis berbeda dari teks gelap di atas latar terang ($+L^c$).
6.  **B**: Pemotongan saluran RGB yang meluap (*clamping*) secara terpisah akan mengubah rasio antar nilai $R$, $G$, dan $B$. Perubahan rasio ini merusak sumbu sudut $H$, yang menyebabkan pergeseran warna visual (*hue shift*), misal dari ungu violet menjadi biru kusam.
7.  **A**: Sistem visual manusia memiliki sensitivitas kontras yang bervariasi bergantung pada ukuran spasial target. Teks kecil dan tipis memiliki frekuensi spasial tinggi yang membutuhkan modulasi kontras luminansi fisik jauh lebih tinggi agar fotoreseptor retina dapat membedakannya dari latar belakang.
8.  **A**: Binary search chroma reduction memungkinkan kita mencari titik perpotongan batas terluar dari *gamut envelope* (sRGB atau P3) secara efisien tanpa mengubah parameter persepsi $L$ (keterangan) dan $H$ (nada warna), sehingga integritas tonal palet tetap terjaga.
9.  **C**: Sistem operasi enterprise modern menyediakan CSS media query `@media (forced-colors: active)`. Standar arsitektur mewajibkan integrasi dengan *CSS system colors* (seperti `Canvas`, `CanvasText`, `Highlight`) agar sistem operasi dapat memetakan tema aksesibilitas tinggi secara native.
10. **A**: Definisi matematis dari OKLab/OKLCH memastikan bahwa nilai Lightness $L$ bersifat univariat terhadap persepsi manusia; kontras luminansi yang dirasakan konstan di seluruh spektrum warna pada nilai $L$ yang identik.
11. **C**: Masalah ini adalah kelemahan klasik formulasi WCAG 2.x yang memberikan "False Pass" pada teks biru saturasi tinggi. Mengintegrasikan algoritma APCA ke dalam token pipeline menjamin penyesuaian otomatis Lightness secara matematis hingga memenuhi ambang batas persepsi yang dapat dibaca manusia ($|L^c| \ge 60$).
12. **C**: Menghitung ulang ribuan elemen secara langsung via JavaScript di main thread memicu *long task* dan memblokir UI render frame. Mengabstraksi perhitungan ke beberapa master seed variables di level CSS root mengalihkan proses interpolasi ke GPU/CSS rendering engine browser secara native.
13. **C**: Menolak Wide-Gamut menahan kemajuan grafis enterprise, namun mengabaikan fallback merusak aksesibilitas monitor non-P3. Solusi enterprise adalah membangun dual-pipeline di CI: Gamut Mapping deterministik dengan fallback sRGB dan optimasi native Display P3, dievaluasi secara independen via APCA.

---

### 16. Summary

1.  **Kegagalan WCAG 2.x**: Model kontras rasio matematis WCAG 2.x ($L_1/L_2$) memiliki kelemahan fundamental berupa ketiadaan pengenalan polaritas (mengabaikan efek *halation* pada dark mode) serta non-uniformitas persepsi pada spektrum warna murni (terutama biru dan kuning).
2.  **Keunggulan APCA**: Algoritma APCA (kandidat WCAG 3) menghitung kontras persepsi berbasis frekuensi spasial tipografi (*size & weight*), adaptasi luminansi latar, dan polaritas penglihatan manusia, menghasilkan metrik kontras $L^c$ yang berkorelasi linier dengan fungsi visual nyata.
3.  **OKLCH Sebagai Fondasi Tonal**: Berbeda dengan sRGB atau HSL, ruang warna OKLCH memisahkan Lightness perseptual secara independen dari Chroma dan Hue. Nilai $L$ konstan menjamin luminansi perseptual seragam di seluruh spektrum warna.
4.  **Deterministik Gamut Mapping**: Konversi dari Wide Gamut (Display P3) ke sRGB wajib menggunakan *Binary Search Chroma Reduction* pada sumbu $L$ dan $H$ yang dikunci untuk mencegah anomali *hue-shifting*.
5.  **Arsitektur Produksi Skalabel**: Sistem token enterprise modern mengisolasi kalkulasi warna berbasis seed pada tataran build-time atau scoped CSS Custom Properties di level root, mendukung native `@media (forced-colors: active)` untuk Windows High Contrast Mode, dan memvalidasi regresi kontras tipografi secara otomatis di CI/CD pipeline.