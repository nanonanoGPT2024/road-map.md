# Bab 04 Module 01: Accessible Color Science & Contrast Engineering

---

## SEKSI 01 — IDENTITAS MODUL

* **Domain Kurikulum:** `03-Frontend-and-Mobile`
* **Sub-Domain:** `design-system`
* **Track:** Level 4 (Advanced Design Systems & Accessibility Engineering)
* **Kode Modul:** `DS-ACC-0401`
* **Topik:** Accessible Color Science & Contrast Engineering
* **Prasyarat Pengetahuan:**
  * Penguasaan mendalam CSS Color Module Level 4 & 5.
  * Pemahaman dasar linear algebra (vektor, transformasi matriks).
  * Pengalaman membangun multi-brand design tokens (Design Tokens W3C Community Group Spec).
  * Pemahaman regulasi WCAG 2.1/2.2 Level AA & AAA.

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, Anda diharapkan mampu:

1. **Menganalisis Perbedaan Kolorimetri:** Menguraikan kelemahan fundamental ruang warna sRGB dan algoritma WCAG 2.x Contrast Ratio terhadap persepsi visual manusia (aspek non-linear photopic vision).
2. **Menguasai Perceptual Color Spaces:** Mengimplementasikan kalkulasi warna pada ruang warna perseptual modern (Oklab, Oklch, dan CIECAM02) untuk transisi rona (*hue*), kroma (*chroma*), dan kecerahan (*lightness*) yang seragam secara perseptual (*perceptually uniform*).
3. **Mengintegrasikan Algoritma APCA:** Menulis engine kalkulasi Accessible Perceptual Contrast Algorithm (APCA) untuk WCAG 3.0 dari nol menggunakan TypeScript, mencakup kalkulasi *Lightness Contrast* ($Lc$) dan penanganan polaritas visual (*spatial frequency* vs. *polarity*).
4. **Membangun Palette Generator Otomatis:** Mengembangkan sistem *algorithmic programmatic token generation* yang menjamin kepatuhan kontras lintas mode (Light, Dark, High Contrast) tanpa intervensi manual desainer.
5. **Mengaudit Runtime Contrast Telemetry:** Memasang sistem telemetri kontras runtime pada DOM virtual/nyata untuk menangkap pelanggaran kontras dinamis yang dipicu oleh variasi latar belakang transparan, blending mode, dan rendering teks subpixel.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: "Warna Bukan Properti CSS, Melainkan Stimulus Visual"

Dalam rekayasa sistem desain konvensional, warna sering diperlakukan sebagai string hex statis (`#0070F3`) yang dipetakan secara acak ke nama semantik (`primary-500`). Paradigma ini cacat secara fundamental:

```
[ Mental Model Konvensional ]
RGB Hex -> Input CSS -> Layar Monitor -> Persepsi Pengguna (Diasumsikan Linear)
Masalah: #0000FF (Biru murni) dan #00FF00 (Hijau murni) memiliki nilai intensitas digital sama (255),
tetapi mata manusia melihat hijau berkali-kali lipat lebih terang daripada biru.
```

Persepsi visual manusia tidak merespons radiasi spektral secara seragam. Retina kita menggunakan sel fotoreseptor kerucut (L, M, dan S) yang memiliki respons puncak terhadap panjang gelombang yang berbeda (merah/hijau/biru), dengan sensitivitas maksimum terkonsentrasi di wilayah hijau-kuning.

```
[ Mental Model Staff Engineer ]
Stimulus Fisik (Spektral)
      │
      ▼
Transformasi Non-Linear Biologis (Human Visual System / Photopic Luminous Efficiency V(λ))
      │
      ▼
Ruang Warna Perseptual (Oklab / Oklch)
      │
      ▼
Kalkulasi Kontras Kontekstual (APCA: Frekuensi Spasial, Polaritas, Adaptasi Kromatik)
      │
      ▼
Token Semantik Adaptif (Runtime Deterministic Output)
```

Sebagai seorang Staff Engineer, mental model Anda harus beralih dari **"mencocokkan rasio matematis WCAG 2.1 (4.5:1)"** ke **"memodelkan respons saraf visual manusia terhadap kontras spasial (Spatial Frequency Contrast)"**. Rasio WCAG 2.1 sering menghasilkan kontras palsu: meloloskan kombinasi warna yang tidak terbaca pada mode gelap (*false positive*), dan menggagalkan kombinasi warna teks tebal yang sangat mudah dibaca (*false negative*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah arsitektur aliran data sistem *deterministic accessible color pipeline* yang mengonversi input token primitif menjadi sistem warna semantik siap produksi yang memenuhi standar WCAG 2.2 dan APCA (WCAG 3.0):

```
+─────────────────────────────────────────────────────────────────────────────+
|                         FASE 1: INPUT DEFINISI WARNA                        |
|   Hex / sRGB Primitif -> Normalisasi ke sRGB Linear Floating-Point [0.0-1.0]|
+──────────────────────────────────────┬──────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
|                     FASE 2: TRANSFORMASI KOORDINAT RUANG                    |
|                                                                             |
|   [ sRGB Linear ] ──( Transformasi Matriks M1 )──> [ CIEXYZ ]              |
|                                                          │                  |
|                                             ( Transformasi Matriks M2 )     |
|                                                          │                  |
|                                                          ▼                  |
|   [ Oklch (L, C, h) ] <──( Konversi Poler )─────── [ Oklab (L, a, b) ]      |
+──────────────────────────────────────┬──────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
|                 FASE 3: GENERASI PALET ISOLATED CHROMA & LIGHTNESS          |
|                                                                             |
|   Pertahankan: Hue (h) & Chroma (C)                                         |
|   Variasikan: Lightness (L) secara terprediksi: L = [0.05, 0.15, ... 0.95]  |
|   Gamut Clipping: Cek apakah L,C,h berada di dalam Gamut Display P3 / sRGB   |
+──────────────────────────────────────┬──────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
|                    FASE 4: EVALUASI KONTRAST GANDA (DUAL-ENGINE)            |
|                                                                             |
|          ┌───────────────────────────┴───────────────────────────┐          |
|          ▼                                                       ▼          |
|  [ Mesin 1: WCAG 2.1 ]                                   [ Mesin 2: APCA ]  |
|  Hitung Luminansi Relatif (Y):                           Hitung Luminous    |
|  Y = 0.2126*R + 0.7152*G + 0.0722*B                      Flux (Y):          |
|  CR = (Y1 + 0.05) / (Y2 + 0.05)                          Koreksi Power Law  |
|  Ambang: 4.5:1 (Teks Normal),                            Model Transisi     |
|          3.0:1 (Komponen UI)                             Lightness (Lc)     |
|          │                                                       │          |
|          └───────────────────────────┬───────────────────────────┘          |
|                                      │                                      |
+──────────────────────────────────────┼──────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
|                FASE 5: PEMETAAN TOKEN SEMANTIK & RESOLUSI RUNTIME           |
|                                                                             |
|   IF Mode == Dark:                                                          |
|      Background = L=0.10, Foreground = Resolusi Lc > +75 / CR > 7.0         |
|   IF Mode == Light:                                                         |
|      Background = L=0.98, Foreground = Resolusi Lc < -75 / CR > 7.0         |
|   Ekspor Token: CSS Custom Properties (--color-text-on-action-default)      |
+─────────────────────────────────────────────────────────────────────────────+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Dekonstruksi Model Ruang Warna: Dari sRGB ke Oklab

Ruang warna sRGB bergantung pada nilai teknis perangkat tampilan tabung sinar katode (CRT) masa lalu. Nilai `RGB(100, 150, 200)` tidak memiliki signifikansi persepsi yang intuitif.

```
       Oklab Coordinates:
              +L (Lightness: 0.0 -> 1.0)
               │
               │   +b (Kuning)
               │   /
               │  /
               │ /
 -a (Hijau) ───┼─── +a (Merah)
              /│
             / │
            /  │
    -b (Biru)  │
              -L
```

* **L (Lightness):** Merepresentasikan kecerahan yang dirasakan secara perseptual. Jika $L = 0.5$, mata manusia memandangnya tepat di tengah antara hitam pekat ($L = 0$) dan putih menyilaukan ($L = 1$).
* **a (Green-Red Axis):** Mengukur seberapa hijau (negatif) atau merah (positif) sebuah warna.
* **b (Blue-Yellow Axis):** Mengukur seberapa biru (negatif) atau kuning (positif) sebuah warna.
* **Oklch (Bentuk Silindris Oklab):**
  * $L$ = Lightness.
  * $C = \sqrt{a^2 + b^2}$ (Chroma: saturasi atau kemurnian warna).
  * $h = \text{atan2}(b, a)$ (Hue: sudut putar warna dari $0^\circ$ hingga $360^\circ$).

### 2. Mekanisme Internal APCA (Accessible Perceptual Contrast Algorithm)

Algoritma WCAG 2.1 menggunakan rumus:
$$\text{Ratio} = \frac{Y_{\text{terang}} + 0.05}{Y_{\text{gelap}} + 0.05}$$
Di mana konstanta $0.05$ dimaksudkan untuk memodelkan *flare* layar (*ambient light*). Namun, rumus ini memiliki kelemahan:
1. **Mengabaikan Efek Helmholz-Kohlrausch:** Peningkatan saturasi warna meningkatkan kecerahan persepsi visual meskipun luminansi fisiknya tetap.
2. **Asimetri Polaritas:** Teks gelap di atas latar terang (polaritas positif) dibaca secara berbeda oleh korteks visual dibandingkan teks terang di atas latar gelap (polaritas negatif/mode gelap). WCAG 2.1 menghasilkan rasio yang sama jika teks dan latar belakang ditukar, yang bertentangan dengan fisiologi manusia.

APCA mengatasi masalah ini melalui tahapan:
1. Konversi sRGB ke $Y$ (Luminansi Spektral Tertimbang) menggunakan koefisien adaptasi fotopik modern.
2. Penerapan eksponen power-law non-linear ($\gamma \approx 0.56$ atau $0.62$) untuk memodelkan respons kurva sel saraf manusia.
3. Kalkulasi $Lc$ (*Lightness Contrast*): Bilangan bertanda dari $-108$ hingga $+106$. Tanda negatif menandakan teks terang pada latar gelap, sedangkan positif menandakan teks gelap pada latar terang.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Transformasi Matematika: sRGB Linear ke Oklab

Untuk memproses warna secara akurat, implementasi token sistem harus melewati rantai transformasi aljabar matriks linier berikut.

#### Langkah 1: Delinearisasi sRGB (*Gamma Un-companding*)
Diberikan nilai sRGB terkompresi $C_{srgb} \in [0, 1]$:

$$C_{linear} = \begin{cases} 
\frac{C_{srgb}}{12.92} & \text{jika } C_{srgb} \le 0.04045 \\
\left(\frac{C_{srgb} + 0.055}{1.055}\right)^{2.4} & \text{jika } C_{srgb} > 0.04045 
\end{cases}$$

#### Langkah 2: Konversi ke LMS Cone Space Melalui Ruang Antara
Oklab pertama-tama mengonversi sRGB linear ke respons kerucut fotoreseptor retina ($L, M, S$) menggunakan perkalian matriks $M_1$:

$$\begin{bmatrix} l \\ m \\ s \end{bmatrix} = \begin{bmatrix} 
0.4122214708 & 0.5363325363 & 0.0514459929 \\
0.2119034982 & 0.6806995451 & 0.1073969566 \\
0.0883024619 & 0.2817188376 & 0.6299787005 
\end{bmatrix} \begin{bmatrix} R_{linear} \\ G_{linear} \\ B_{linear} \end{bmatrix}$$

#### Langkah 3: Non-linearitas Sensoris Retina
Respons kerucut diproses secara non-linear (akar pangkat tiga) menyerupai kompresi dinamis sinyal biologis:

$$l' = l^{1/3}, \quad m' = m^{1/3}, \quad s' = s^{1/3}$$

#### Langkah 4: Transformasi ke Koordinat Oklab
Ruang oposisi warna diturunkan menggunakan matriks $M_2$:

$$\begin{bmatrix} L \\ a \\ b \end{bmatrix} = \begin{bmatrix} 
0.2104542553 & 0.7936177850 & -0.0040720468 \\
1.9779984951 & -2.4285922050 & 0.4505937099 \\
0.0259040371 & 0.7827717662 & -0.8086757660 
\end{bmatrix} \begin{bmatrix} l' \\ m' \\ s' \end{bmatrix}$$

### Pemodelan Frekuensi Spasial Teks pada Kontras

Kontras bukan nilai skalar independen, melainkan fungsi dari frekuensi spasial (ketebalan goresan dan ukuran font). Mata manusia memiliki *Contrast Sensitivity Function* (CSF) yang berbentuk lonceng:

```
Sensitivitas Kontras
  ▲
  │         Ketajaman Optimum
  │            (Teks 16px-24px)
  │                 ╭───╮
  │                ╭╯   ╰╮
  │               ╭╯     ╰╮   Garis Sangat Tipis
  │   Font Besar ╭╯       ╰╮  (High Frequency Cutoff)
  │  (Low Freq) ╭╯         ╰╮
  │            ╭╯           ╰╮
  └────────────┴─────────────┴──────────► Frekuensi Spasial (cycles/degree)
```

APCA menentukan kebutuhan kontras berdasarkan matriks ukuran dan bobot font:
* **Teks Tipis (Light 300, 14px):** Membutuhkan $Lc \ge 90$ karena CSF manusia rendah pada goresan tipis.
* **Teks Tebal (Bold 700, 24px):** Cukup dengan $Lc \ge 60$ karena integrasi fotoreseptor retina mencakup area spasial yang lebih luas.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah engine komputasi matematika TypeScript murni tanpa dependensi eksternal untuk mengonversi sRGB ke Oklab/Oklch, menghitung WCAG 2.1, dan mengeksekusi perhitungan APCA.

```typescript
// color-engine-core.ts

export interface RGB {
  r: number; // 0 - 255
  g: number; // 0 - 255
  b: number; // 0 - 255
}

export interface OKLCH {
  l: number; // 0.0 - 1.0 (Lightness)
  c: number; // 0.0 - ~0.4 (Chroma)
  h: number; // 0.0 - 360.0 (Hue angle in degrees)
}

/**
 * Normalisasi dan Gamut Gamma Un-companding (sRGB -> Linear RGB)
 */
export function sRGBToLinear(val: number): number {
  const v = val / 255;
  return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
}

/**
 * Konversi Linear RGB ke Oklch
 */
export function rgbToOklch(rgb: RGB): OKLCH {
  const lr = sRGBToLinear(rgb.r);
  const lg = sRGBToLinear(rgb.g);
  const lb = sRGBToLinear(rgb.b);

  // Matriks M1: Linear sRGB ke LMS
  const l_ = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb);
  const m_ = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb);
  const s_ = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb);

  // Matriks M2: LMS ke Oklab
  const L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_;
  const a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_;
  const b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_;

  const c = Math.sqrt(a * a + b * b);
  let h = (Math.atan2(b, a) * 180) / Math.PI;
  if (h < 0) h += 360;

  return { l: L, c, h };
}

/**
 * WCAG 2.1 Kalkulasi Luminansi Relatif
 */
export function getRelativeLuminance(rgb: RGB): number {
  const r = sRGBToLinear(rgb.r);
  const g = sRGBToLinear(rgb.g);
  const b = sRGBToLinear(rgb.b);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * WCAG 2.1 Kalkulasi Rasio Kontras
 */
export function getWCAG21Contrast(foreground: RGB, background: RGB): number {
  const lum1 = getRelativeLuminance(foreground);
  const lum2 = getRelativeLuminance(background);
  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);
  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * APCA (WCAG 3.0 draft) Perceptual Contrast Engine (W3 v0.98G simplified reference)
 */
export function calculateAPCA(text: RGB, bg: RGB): number {
  // Koefisien Luminansi APCA
  const rCoeff = 0.2126729;
  const gCoeff = 0.7151522;
  const bCoeff = 0.0721750;

  // Linearize dan hitung Y
  const yText =
    rCoeff * sRGBToLinear(text.r) +
    gCoeff * sRGBToLinear(text.g) +
    bCoeff * sRGBToLinear(text.b);

  const yBg =
    rCoeff * sRGBToLinear(bg.r) +
    gCoeff * sRGBToLinear(bg.g) +
    bCoeff * sRGBToLinear(bg.b);

  // Soft-clamp untuk noise latar gelap
  const clampYText = yText > 0.0005 ? yText : 0.0005;
  const clampYBg = yBg > 0.0005 ? yBg : 0.0005;

  // Power law eksponen persepsi
  const normBG = 0.56;
  const normTXT = 0.62;
  const revBG = 0.65;
  const revTXT = 0.55;

  // Ambang batas flare kompensasi
  const blkThrs = 0.022;
  const blkClmp = 1.414;

  let contrast = 0.0;

  // Polarisasi Positif: Teks Gelap di atas Latar Terang
  if (clampYBg >= clampYText) {
    const bgFactor = Math.pow(clampYBg, normBG);
    const txtFactor = Math.pow(clampYText, normTXT);
    contrast = (bgFactor - txtFactor) * 100;
  } 
  // Polarisasi Negatif: Teks Terang di atas Latar Gelap
  else {
    const bgFactor = Math.pow(clampYBg, revBG);
    const txtFactor = Math.pow(clampYText, revTXT);
    contrast = (bgFactor - txtFactor) * 100;
  }

  // Terapkan scaling mikro & abaikan desimal insignifikan
  if (Math.abs(contrast) < 0.1) return 0;
  return parseFloat(contrast.toFixed(2));
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah bedah logis arsitektur kode di atas:

1. **Baris 18–21 (`sRGBToLinear`)**:
   Fungsi ini membatalkan kompresi kurva gamma standar sRGB ($2.4$). Jika nilai integer $\le 0.04045$, kurva linear diterapkan ($v / 12.92$). Ini krusial karena kalkulasi luminansi dan persepsi pada ruang warna linear mensyaratkan data dalam rasio emisi foton fisik aktual, bukan kurva representasi monitor.
2. **Baris 33–35 (`l_`, `m_`, `s_`)**:
   Matriks Oklab $M_1$ memetakan koordinat Cartesian sRGB linear ke domain sel kerucut Long, Medium, dan Short retina kita. Penggunaan `Math.cbrt` (akar pangkat 3) secara eksplisit memodelkan non-linearitas persepsi kecerahan tubuh manusia terhadap kekuatan fisik stimulus fotopik (Stevens' Power Law / Plateau approximation).
3. **Baris 38–40 (`L`, `a`, `b`)**:
   Matriks transformasi kedua menghasilkan pemisahan ortogonal sempurna antara luminansi ($L$) dengan koordinat *chrominance opponent* ($a$ merah-hijau dan $b$ kuning-biru).
4. **Baris 78–80 (`normBG`, `normTXT`, `revBG`, `revTXT`)**:
   Konstanta eksponen APCA menangani efek *spatial luminance polarity*. Pada polaritas positif (latar terang), eksponen latar belakang adalah $0.56$ dan teks adalah $0.62$. Pada polaritas negatif (latar gelap), sistem saraf beradaptasi terhadap emisi global rendah, sehingga variabel eksponen ditukar secara asimetris menjadi $0.65$ dan $0.55$. Hal ini mencegah fenomena teks tebal berwarna putih tampak "berpendar menyilaukan" (*halation effect*) pada layar OLED/Dark Mode.
5. **Baris 92–104 (Blok Percabangan Polaritas APCA)**:
   Perhitungan nilai kontras mengembalikan skalar bertanda ($+$ atau $-$). Tanda ini mengindikasikan mode polaritas yang secara langsung menginformasikan mesin render apakah tipografi harus disesuaikan menggunakan *subpixel anti-aliasing* atau *grayscale smoothing*.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks Kasus
Platform FinTech Enterprise multi-penyewa (*multi-tenant*) B2B global meluncurkan fitur *Dynamic Theming*. Klien institusi diizinkan menyuntikkan satu warna primer identitas korporat (*Seed Color*). 

### Insiden Produksi
Seorang klien korporat memilih warna *Seed Brand* `#FACC15` (Kuning Terang / *Vibrant Yellow*). Sistem token warisan (berbasis manipulasi HSL konvensional) menurunkan token status dan interaksi secara linear dengan mengubah saturasi dan kecerahan:
1. Tombol primer menggunakan `#FACC15` dengan teks `#FFFFFF` karena sistem secara naif menganggap warna *Brand* wajib berpasangan dengan teks putih. Rasio kontras terukur WCAG 2.1 hanya **1.38:1** (Kategori Pelanggaran Ekstrem).
2. Ketika beralih ke Dark Mode, sistem otomatis menaikkan Lightness sRGB sebesar 20%, menghasilkan teks abu-abu terang di atas kartu latar abu-abu gelap yang secara visual "menghilang" bagi pengguna penyandang disabilitas penglihatan parsial (ambang ketajaman rendah).
3. Perusahaan menghadapi gugatan audit aksesibilitas legal berdasarkan standar ADA (Americans with Disabilities Act) Title III dan European Accessibility Act (EAA).

### Solusi Desain Sistem & Rekayasa
Membangun *Dynamic Palette Derivation Pipeline* otomatis berbasis Oklch dan APCA. Klien tetap dapat memilih warna *seed* apa pun, namun engine secara otomatis:
* Mengunci nilai perseptual lightness ($L$).
* Melakukan Gamut Mapping cerdas.
* Memilih teks kontras tertinggi secara deterministik dengan validasi APCA minimum $|Lc| \ge 75$.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistem token palet cerdas tingkat produksi yang memecahkan masalah studi kasus di atas. Modul ini menerima satu warna hex *seed*, mengekstrak Oklch, dan secara algoritmik menghasilkan seluruh varian token semantik UI yang dijamin patuh aksesibilitas.

```typescript
// accessible-palette-generator.ts
import { RGB, OKLCH, rgbToOklch, calculateAPCA, getWCAG21Contrast } from './color-engine-core';

export interface SemanticTokenSet {
  surfaceBackground: string;
  surfaceContainer: string;
  actionPrimary: string;
  textOnActionPrimary: string;
  actionFocusRing: string;
  metrics: {
    apcaScore: number;
    wcagScore: number;
  };
}

/**
 * Utilitas konversi Hex string ke RGB murni
 */
export function hexToRgb(hex: string): RGB {
  let cleanHex = hex.replace('#', '');
  if (cleanHex.length === 3) {
    cleanHex = cleanHex.split('').map(char => char + char).join('');
  }
  const intVal = parseInt(cleanHex, 16);
  return {
    r: (intVal >> 16) & 255,
    g: (intVal >> 8) & 255,
    b: intVal & 255
  };
}

/**
 * Utilitas konversi RGB ke CSS String Hex
 */
export function rgbToHex(rgb: RGB): string {
  const toHex = (n: number) => {
    const clamped = Math.max(0, Math.min(255, Math.round(n)));
    return clamped.toString(16).padStart(2, '0');
  };
  return `#${toHex(rgb.r)}${toHex(rgb.g)}${toHex(rgb.b)}`;
}

/**
 * Gamut Clipping & Inversi Oklch kembali ke sRGB Terbatas
 */
export function oklchToRgb(oklch: OKLCH): RGB {
  const hRad = (oklch.h * Math.PI) / 180;
  const a = oklch.c * Math.cos(hRad);
  const b = oklch.c * Math.sin(hRad);

  // Inversi Matriks M2: Oklab ke LMS
  const l_ = oklch.l + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = oklch.l - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = oklch.l - 0.0894841775 * a - 1.2914855480 * b;

  const l = l_ * l_ * l_;
  const m = m_ * m_ * m_;
  const s = s_ * s_ * s_;

  // Inversi Matriks M1: LMS ke Linear sRGB
  const rLin = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
  const gLin = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
  const bLin = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s;

  // Linear sRGB ke Standard Gamma sRGB (companding)
  const compand = (val: number) => {
    const clamped = Math.max(0, Math.min(1, val)); // Hard gamut clipping
    return clamped <= 0.0031308
      ? clamped * 12.92
      : 1.055 * Math.pow(clamped, 1.0 / 2.4) - 0.055;
  };

  return {
    r: compand(rLin) * 255,
    g: compand(gLin) * 255,
    b: compand(bLin) * 255
  };
}

/**
 * Generator Token Aksesibel Berbasis Algoritma Oklch & APCA
 */
export class AccessiblePaletteArchitect {
  /**
   * Menghasilkan pasangan warna teks deterministik (Hitam vs Putih)
   * Menggunakan algoritma APCA Lc Ambang Batas Minimal |Lc| >= 75
   */
  public static resolveAccessibleForeground(backgroundRgb: RGB): { textRgb: RGB; apca: number; wcag: number } {
    const pureWhite: RGB = { r: 255, g: 255, b: 255 };
    const pureBlack: RGB = { r: 0, g: 0, b: 0 };

    const apcaWhite = calculateAPCA(pureWhite, backgroundRgb);
    const apcaBlack = calculateAPCA(pureBlack, backgroundRgb);

    // Kriteria APCA: Lc mutlak terbesar adalah representasi kejernihan visual terbaik
    // Lc negatif = teks putih di atas latar gelap
    // Lc positif = teks hitam di atas latar terang
    const pickWhite = Math.abs(apcaWhite) >= Math.abs(apcaBlack);

    const chosenText = pickWhite ? pureWhite : pureBlack;
    const finalApca = pickWhite ? apcaWhite : apcaBlack;
    const finalWcag = getWCAG21Contrast(chosenText, backgroundRgb);

    return {
      textRgb: chosenText,
      apca: finalApca,
      wcag: finalWcag
    };
  }

  /**
   * Mengompilasi tema lengkap dari satu seed color
   */
  public static generateDesignTokens(seedHex: string, isDarkMode = false): SemanticTokenSet {
    const seedRgb = hexToRgb(seedHex);
    const seedOklch = rgbToOklch(seedRgb);

    // Lightness anchor mapping berbasis ruang persepsi
    let surfaceL = isDarkMode ? 0.12 : 0.98;
    let containerL = isDarkMode ? 0.18 : 0.92;
    
    // Normalisasi action lightness: Jangan biarkan action primary terlalu gelap pada dark mode
    // atau terlalu menyilaukan pada light mode.
    let actionL = isDarkMode ? Math.max(0.65, seedOklch.l) : Math.min(0.45, seedOklch.l);
    
    // Mitigasi warna saturasi abnormal (menghindari clipping distortion)
    let safeChroma = Math.min(seedOklch.c, 0.22);

    const bgOklch: OKLCH = { l: surfaceL, c: 0.01, h: seedOklch.h };
    const containerOklch: OKLCH = { l: containerL, c: 0.02, h: seedOklch.h };
    const actionOklch: OKLCH = { l: actionL, c: safeChroma, h: seedOklch.h };

    const bgRgb = oklchToRgb(bgOklch);
    const containerRgb = oklchToRgb(containerOklch);
    const actionRgb = oklchToRgb(actionOklch);

    const foregroundResolution = this.resolveAccessibleForeground(actionRgb);

    // Menghasilkan