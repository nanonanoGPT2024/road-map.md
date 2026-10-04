# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum**: `03-Frontend-and-Mobile`
*   **Modul**: `CSS`
*   **Bab**: `08` (Next-Gen Layouts, Graphics Engine, & Performance Architecture)
*   **Modul Unit**: `01`
*   **Topik**: *Modern Color Spaces, Visual Shaders, & Advanced Math UI*
*   **Tingkat Kesulitan**: Advanced / Staff Engineer Level
*   **Prasyarat**: Pemahaman mendalam CSS Custom Properties, Compositor Layers, SVG Filters, Trigonometri Web Dasar, dan Model Rendering Browser (Blink/Gecko/WebKit).

---

# SEKSI 02 — LEARNING OBJECTIVES

1.  **Menguasai Ruang Warna Gamut Luas (Wide-Gamut Color Spaces)**: Menganalisis perbedaan teknis antara `sRGB`, `Display P3`, `CIELAB`, `LCH`, `OKLAB`, dan `OKLCH`, serta mampu merekayasa palet dinamis yang *perceptually uniform* untuk display modern.
2.  **Mengimplementasikan Kalkulasi Visual Berbasis Advanced CSS Math**: Memanfaatkan fungsi matematika CSS Level 4 (`sin()`, `cos()`, `atan2()`, `pow()`, `sqrt()`, `hypot()`, `mod()`, `rem()`) untuk merancang antarmuka non-linear, tata letak sirkular terdistribusi, dan animasi fisika tanpa ketergantungan JavaScript runtime.
3.  **Merekayasa Shader Visual Tingkat Rendah Menggunakan CSS & SVG**: Membangun efek visual analog shader (distorsi mesh, procedural noise generation, chromatic aberration, lighting simulation) menggunakan penggabungan primitif `<feTurbulence>`, `<feDisplacementMap>`, dan filter pipeline CSS modern.
4.  **Mencegah Masalah Interpolasi Warna ("Gray Dead Zones")**: Mengontrol interpolasi gradien dan transisi menggunakan fungsi interpolasi warna eksplisit (`color-mix()`, `in oklch`, `in oklab`) guna memastikan kecerahan dan saturasi linear di seluruh spektrum visual.
5.  **Membangun Sistem Desain Enterprise Skalabel & Aksesibel**: Mengintegrasikan algoritma WCAG 2.2 dan APCA (Accessible Perceptual Contrast Algorithm) langsung ke dalam CSS tokens melalui komputasi warna OKLCH dan relative color syntax (`from <color>`).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Dari "Monitor CRT 8-bit" ke "Perceptually Uniform Photonic Engine"
Secara historis, model warna web didasarkan pada batasan hardware tabung sinar katoda (CRT) tahun 1996: ruang warna sRGB dengan representasi koordinat kubus non-linear berbasis integer 8-bit per kanal (`rgb(255, 255, 255)` atau `#FFFFFF`). Model ini cacat secara persepsi:
*   Hijau murni (`#00FF00`) memiliki luminansi perseptual yang jauh lebih tinggi daripada Biru murni (`#0000FF`), namun dalam ruang sRGB keduanya diperlakukan memiliki magnitudo koordinat yang setara (nilai 255).
*   Rotasi *hue* pada `hsl()` menghasilkan distorsi kecerahan visual drastis. Warna kuning pada $H=60^\circ$ menyilaukan mata, sedangkan warna biru pada $H=240^\circ$ terlihat sangat gelap, merusak konsistensi UI tematik.

```
Model Tradisional (sRGB / HSL):
Sumbu Matematis != Persepsi Biologis Manusia
[H: 60° (Kuning)] Luminansi Efektif: ~93%  --> Menyilaukan
[H: 240° (Biru)]   Luminansi Efektif: ~7%   --> Gelap Gulita
(Hasil: UI inkonsisten, kontras teks hancur saat tema diubah dinamis)

Model Modern (OKLCH):
Sumbu Matematis == Persepsi Biologis Manusia (CIE Standard Observer Model)
L = Lightness (Perceptual Luminescence terisolasi penuh dari Chroma dan Hue)
C = Chroma (Saturasi murni)
H = Hue (Sudut warna murni tanpa efek samping ke luminansi)
```

### Mental Model CSS Math: "Declarative GPU Pipelines"
Alih-alih memandang kalkulasi posisi elemen sebagai kalkulasi tata letak imperatif pada JavaScript main-thread event-loop, pandanglah CSS Math (`sin`, `cos`, `atan2`, `hypot`) sebagai instruksi transform simpul langsung yang dievaluasi selama fase styling/layout engine browser. Variabel-variabel tersebut dapat ditautkan ke *ScrollTimeline*, *ViewTimeline*, atau *CSS Custom Properties* yang diubah via input mikro untuk menghasilkan pergerakan parametrik berkecepatan 120 FPS tanpa menyebabkan layout thrashing.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah diagram alur arsitektur pemrosesan warna, evaluasi matematika, dan kompilasi rendering filter pipeline di dalam browser engine modern (Blink/Skia/Chromium):

```
+---------------------------------------------------------------------------------------+
|                                    SOURCE CSS INPUT                                   |
|   color: oklch(from var(--primary) calc(l * 0.8) c calc(h + 180));                    |
|   transform: translate(calc(cos(var(--angle)) * 50px), calc(sin(var(--angle)) * 50px))|
|   filter: url(#noise-displacement);                                                   |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                                 PARSING & TOKENIZATION                                |
| - Resolver: CSSColorModuleLevel4 / CSSColorModuleLevel5                               |
| - Evaluator: CSSMathExpressionNode (AST Builder: sin, cos, atan2, hypot)              |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                          RESOLVED VALUE & GAMUT MAPPING                               |
| - Resolving 'OKLCH' -> Linear Rec.2020 / Linear Display P3 / Linear sRGB              |
| - Gamut Clipping vs. Gamut Mapping (CSS Color 4 algorithm: Ch seek & deltaE2000)      |
| - Math Node: Nilai Sudut di-resolve ke Scalar Float Pixels                            |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                         RENDER TREE & SKIA/GRAPHITE COMMANDS                          |
|  Paint Artifacts / SkColor4f (Float32x4 per channel, unclipped HDR capable)           |
+---------------------------------------------------------------------------------------+
                       |                                           |
      (Standard Raster Operations)                        (Visual Shader Pipeline)
                       |                                           |
                       v                                           v
+--------------------------------------+   +--------------------------------------------+
|      RASTER ENGINE (Skia Core)       |   |       GPU ACCELERATED PIXEL SHADER         |
| Menggambar primitif teks, batas, dan |   | - SVG Filter Node: feTurbulence (Perlin)   |
| background langsung ke pixel buffer  |   | - feDisplacementMap (Pixel Coordinate Shift|
+--------------------------------------+   | - Offscreen Buffer Alloc & Composite Blends|
                       \                   +--------------------------------------------+
                        \                                 /
                         \                               /
                          v                             v
+---------------------------------------------------------------------------------------+
|                               COMPOSITOR THREAD (Direct3D/Metal/Vulkan)               |
| Layer Compositing, Swap Chain SwapBuffers(), Wide Gamut Output ke Display P3 Monitor |
+---------------------------------------------------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi OKLCH dan Relative Color Syntax (RCS)
Fungsi `oklch()` menggunakan tiga sumbu silindris dari ruang warna OKLAB yang dirancang oleh Björn Ottosson (2020):
$$\text{oklch}(L \quad C \quad H \quad [/ \quad A])$$
*   **$L$ (Perceptual Lightness)**: `0%` sampai `100%` (atau `0.0` sampai `1.0`). Mengontrol luminansi perseptual murni. $L=0.7$ memiliki kecerahan perseptual yang identik, terlepas dari apakah warnanya merah, biru muda, atau kuning.
*   **$C$ (Chroma)**: Nilai desimal dari `0` hingga teoritis tak terbatas (dalam praktik `0` hingga sekitar `0.4` untuk gamut perangkat keras saat ini). Menunjukkan kemurnian/kejenuhan warna.
*   **$H$ (Hue)**: `0deg` hingga `360deg` (atau skalar satuan siklus/turn). Mengontrol nada warna secara bertahap tanpa memodifikasi luminansi ($0^\circ$ Merah muda, $90^\circ$ Kuning, $140^\circ$ Hijau, $240^\circ$ Biru).
*   **$A$ (Alpha)**: Transparansi dari `0%` ke `100%` atau `0.0` ke `1.0`.

**Relative Color Syntax (RCS)** membedah warna dasar ke dalam kanal-kanalnya menggunakan kata kunci `from`:
```css
/* Sintaks: oklch(from <origin-color> <channel-l> <channel-c> <channel-h> [ / <alpha> ]) */
background-color: oklch(from var(--brand-color) calc(l - 0.15) c h);
```
Secara internal, parser memproyeksikan `--brand-color` ke ruang warna target (OKLCH), mengisolasi variabel lokal `l`, `c`, `h`, dan `alpha`, lalu mengevaluasi ekspresi `calc()` untuk membentuk vektor warna baru sebelum rasterisasi.

### 2. Anatomi Engine CSS Advanced Math
Fungsi trigonometri CSS mematuhi standar *CSS Values and Units Module Level 4*. Mekanisme internalnya:
*   `sin(angle)` & `cos(angle)`: Mengembalikan angka float murni tanpa satuan (skalar) $[-1.0, 1.0]$.
*   `atan2(y, x)`: Menghitung sudut busur tangen dua parameter, mengembalikan jenis sudut `<angle>` (`rad` atau `deg`) antara $-\pi$ dan $\pi$. Berguna untuk rotasi otomatis elemen mengikuti vektor koordinat kursor.
*   `hypot(x, y, ...)`: Menghitung panjang vektor Euclidean: $\sqrt{x^2 + y^2 + \dots}$.
*   `mod(A, B)` & `rem(A, B)`: Mengembalikan sisa pembagian modulus (berbeda pada penanganan tanda negatif, `mod` mengikuti tanda $B$, `rem` mengikuti tanda $A$).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Transformasi Matriks Color Space: Gamut Mapping & Chromaticity
Ruang warna standar web lama sRGB dibatasi oleh segitiga gamut sempit di dalam CIE 1931 Chromaticity Diagram. Display modern (Apple Retina, panel OLED, monitor HDR) mencakup gamut **Display P3**, yang memiliki volume warna sekitar 50% lebih besar daripada sRGB, terutama pada area hijau saturasi tinggi dan merah pekat.

Ketika CSS mendefinisikan warna di luar gamut native monitor client (misal: client hanya memiliki layar standar sRGB, tetapi kode CSS meminta `oklch(0.65 0.32 140)` yang merupakan hijau Display P3 murni), browser menjalankan algoritma **Gamut Mapping**:

```
[Target Warna (Out-of-Gamut)]
              |
              v
[DeltaE (ΔE) Check Terhadap Batas Monitor Destination]
              |
              v
[Algoritma Gamut Mapping CSS Color 4]:
  Looping binary-search:
    Koreksi nilai Chroma (C) ke arah bawah (mendekati C = 0)
    Sambil MEMPERTAHANKAN Lightness (L) dan Hue (H) konstan
    Hingga warna masuk ke dalam representasi monitor dengan ΔE minimal
              |
              v
[Clamped Perceptually Equivalent Color]
```
Metode ini jauh melampaui pendekatan lama (*Naive Clipping*), di mana pemotongan nilai $R, G, B$ secara kasar merusak *hue* dan mengubah warna (misal: warna ungu terpotong menjadi biru gelap kusam).

### 2. Eliminasi "Gray Dead Zones" pada Gradient Interpolation
Dalam CSS tradisional:
```css
/* Menggunakan ruang interpolasi sRGB secara default */
background: linear-gradient(to right, red, blue);
```
Titik tengah gradien dihitung secara linier pada kanal RGB non-linear:
$R_{mid} = 127, G_{mid} = 0, B_{mid} = 127$. Hasil visualnya adalah warna ungu kusam berlumpur yang kehilangan kecerahan perseptual (Luminansi turun drastis di tengah).

CSS Color 4 menyelesaikan ini dengan *Color Interpolation Methods*:
```css
/* Interpolasi terjadi di dalam perceptual OKLAB space */
background: linear-gradient(to right in oklab, red, blue);
```
Algoritma gradien berjalan melalui ruang warna di mana luminansi ditransisikan secara linear sejati, mempertahankan saturasi dan menghindari zona abu-abu mati.

### 3. Visual Shaders Melalui SVG & CSS Filter Graph Pipeline
CSS Filters konvensional (`blur`, `brightness`, `contrast`) beroperasi sebagai operasi piksel monolitik sederhana. Namun, dengan menggabungkan CSS filter dengan primitif SVG Filters off-screen, kita dapat menyusun graf komputasi *fragment shader* yang berjalan langsung pada grafis GPU.

Graf pemrosesan *Noise Displacement Shader*:
1.  **`<feTurbulence>`**: Menggenerasi tekstur fraktal noise berbasis algoritma Perlin noise ($f(x, y)$) langsung di GPU offscreen buffer. Output berupa raster RGBA.
2.  **`<feColorMatrix>`**: Memanipulasi kanal RGBA noise tekstur, meningkatkan kontras kanal Alpha dan memetakan nilai intensitas warna merah dan hijau sebagai vektor diferensial.
3.  **`<feDisplacementMap>`**: Menggunakan kanal warna tekstur masukan (misal: $R$ dan $G$) untuk mendistorsi koordinat $x$ dan $y$ dari layer elemen target DOM HTML:
$$P_{dest}(x, y) = P_{src}(x + \text{scale} \cdot (R(x, y) - 0.5), \; y + \text{scale} \cdot (G(x, y) - 0.5))$$
Prosesor grafis engine menggeser texel DOM asli berdasarkan variasi fraktal, menghasilkan efek refraksi kaca (glass refraction), riak air, atau distorsi termal realistis.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi sistem UI terpadu yang memadukan:
1. Relative Color Syntax untuk variasi warna adaptif.
2. Interpolasi gradien modern tanpa *dead-zone*.
3. CSS Math Trigonometri untuk memposisikan sub-elemen secara melingkar (*Radial Menu*).

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Fundamental Modern Color & Math</title>
  <style>
    :root {
      /* Base Token dalam OKLCH */
      --color-brand-base: oklch(0.65 0.24 260); /* Biru Cerah Wide-Gamut */
      --radius-menu: 120px;
    }

    body {
      display: grid;
      place-items: center;
      min-height: 100vh;
      margin: 0;
      background-color: oklch(0.15 0.02 260);
      font-family: system-ui, -apple-system, sans-serif;
    }

    /* Container dengan Gradien Perceptually Uniform */
    .color-showcase {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
      padding: 2rem;
      border-radius: 1rem;
      background: linear-gradient(
        135deg in oklch,
        oklch(from var(--color-brand-base) l c h),
        oklch(from var(--color-brand-base) calc(l * 0.4) calc(c * 0.8) calc(h + 90))
      );
      box-shadow: 0 20px 40px oklch(0 0 0 / 0.4);
    }

    /* Radial Trigonometric Layout System */
    .radial-container {
      position: relative;
      width: 300px;
      height: 300px;
      border: 1px dashed oklch(from var(--color-brand-base) 0.8 0.05 h / 0.3);
      border-radius: 50%;
      display: grid;
      place-items: center;
    }

    .center-anchor {
      width: 50px;
      height: 50px;
      border-radius: 50%;
      background: var(--color-brand-base);
      box-shadow: 0 0 20px oklch(from var(--color-brand-base) l c h / 0.8);
    }

    .orbital-node {
      --index: 0;
      --total: 6;
      --angle: calc((360deg / var(--total)) * var(--index));
      
      /* Pure CSS Trigonometry Positioning */
      --pos-x: calc(cos(var(--angle)) * var(--radius-menu));
      --pos-y: calc(sin(var(--angle)) * var(--radius-menu));

      position: absolute;
      width: 40px;
      height: 40px;
      border-radius: 50%;
      
      /* Varian warna otomatis menggunakan Relative Color Syntax */
      background: oklch(
        from var(--color-brand-base) 
        calc(l + 0.1) 
        calc(c * 1.2) 
        calc(h + (var(--index) * 40))
      );

      /* Transformasi node menggunakan vektor matematika */
      transform: translate(var(--pos-x), var(--pos-y));
      transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .orbital-node:nth-child(1) { --index: 0; }
    .orbital-node:nth-child(2) { --index: 1; }
    .orbital-node:nth-child(3) { --index: 2; }
    .orbital-node:nth-child(4) { --index: 3; }
    .orbital-node:nth-child(5) { --index: 4; }
    .orbital-node:nth-child(6) { --index: 5; }

    .radial-container:hover .orbital-node {
      /* Manipulasi dinamis berbasis scale math */
      --pos-x: calc(cos(var(--angle)) * calc(var(--radius-menu) * 1.15));
      --pos-y: calc(sin(var(--angle)) * calc(var(--radius-menu) * 1.15));
    }
  </style>
</head>
<body>

  <div class="color-showcase">
    <div class="radial-container">
      <div class="center-anchor"></div>
      <div class="orbital-node"></div>
      <div class="orbital-node"></div>
      <div class="orbital-node"></div>
      <div class="orbital-node"></div>
      <div class="orbital-node"></div>
      <div class="orbital-node"></div>
    </div>
  </div>

</body>
</html>
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 9**: `--color-brand-base: oklch(0.65 0.24 260);`
    Mendefinisikan warna utama menggunakan model OKLCH. Nilai lightness ($0.65$) memastikan persepsi kecerahan menengah-terang konstan. Nilai Chroma ($0.24$) menggunakan potensi gamut di luar sRGB (Display P3) secara presisi, menghasilkan warna biru elektrik yang jernih.
*   **Baris 24-28**:
    ```css
    background: linear-gradient(
      135deg in oklch,
      oklch(from var(--color-brand-base) l c h),
      oklch(from var(--color-brand-base) calc(l * 0.4) calc(c * 0.8) calc(h + 90))
    );
    ```
    Sintaks `in oklch` menginstruksikan modul rendering browser untuk melakukan interpolasi linear di dalam ruang vektor polar OKLCH, bukan memotong langsung melalui sRGB standar. Sub-argumen `calc(h + 90)` memutar *hue* sejauh 90 derajat secara perseptual murni tanpa mengorbankan luminositas dasar secara asimetris.
*   **Baris 46-49**:
    ```css
    --angle: calc((360deg / var(--total)) * var(--index));
    --pos-x: calc(cos(var(--angle)) * var(--radius-menu));
    --pos-y: calc(sin(var(--angle)) * var(--radius-menu));
    ```
    Engine CSS mengevaluasi rasio sudut untuk setiap elemen berdasarkan custom property `--index`. Nilai trigonometri `cos()` dan `sin()` mengembalikan skalar floating point antara $-1$ hingga $1$. Hasil perkalian skalar dengan panjang dimensi satuan (`120px`) menghasilkan vektor koordinat Kartesius yang valid secara matematis untuk penempatan posisi elemen.
*   **Baris 56-61**:
    ```css
    background: oklch(
      from var(--color-brand-base) 
      calc(l + 0.1) 
      calc(c * 1.2) 
      calc(h + (var(--index) * 40))
    );
    ```
    Penggunaan Relative Color Syntax (RCS). Browser mengekstrak komponen kanal `l`, `c`, `h` dari `--color-brand-base`. Varian warna dihasilkan secara modular: *Lightness* dinaikkan $0.1$, saturasi ditingkatkan $20\%$, dan corak warna (*hue*) bergeser terdistribusi sebesar 40 derajat untuk setiap langkah iterasi simpul.

---

# SEKSI 09 — STUDI KASUS NYATA

### Enterprise Scenario: Arsitektur UI Trading Terminal & Mission-Control HUD
**Latar Belakang**:
Sebuah platform analitik finansial enterprise multi-layar membutuhkan dashboard tingkat tinggi yang menampilkan ratusan indikator pasar real-time. 

**Tantangan Teknis**:
1.  **Akurasi Kontras & Kelelahan Visual**: Indikator kritis (Volatilitas, Arbitrase, Likuiditas) memerlukan pemetaan warna dinamis dari merah (*bearish*) ke hijau (*bullish*). Menggunakan model HSL atau sRGB tradisional menciptakan "Dead Lightness Spike" di area kuning, yang menyilaukan mata para trader di ruang gelap (*low-light environments*) dan melanggar rasio kontras compliance ADA/WCAG pada varian warna tertentu.
2.  **Overhead JavaScript Runtime**: Antarmuka dashboard lama menggunakan JavaScript (Three.js/Canvas 2D) untuk membuat radar chart melingkar dan efek distorsi kaca (*frosted optic refractive panel*). Saat ratusan data WebSocket masuk per detik, eksekusi JavaScript pada main thread terblokir, memicu frame drop parah (<30 FPS) dan degradasi latensi input.

**Solusi Arsitektural**:
*   Migrasi sistem token warna secara total ke **OKLCH Systemic Theme Tokens** yang menggunakan Relative Color Syntax untuk menjamin rasio kontras APCA (Accessible Perceptual Contrast Algorithm) yang seragam secara deterministik.
*   Pembuatan indikator radar HUD parametrik terdistribusi yang murni menggunakan **CSS Math Trigonometri (`sin`, `cos`, `hypot`)**.
*   Pengalihan beban visual rendering shader (glass distortion & aberration) dari JavaScript ke **Hardware-Accelerated CSS-SVG Filter Graph**.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah kode siap produksi untuk antarmuka "HUD Tactical Financial Radar" yang mengintegrasikan OKLCH dynamic scale, shader refraksi prosedural via SVG Filters terintegrasi CSS, dan CSS Math UI positioning.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Production Tactical Trading HUD</title>
  <style>
    :root {
      /* Enterprise Design Tokens - Perceptually Tuned Engine */
      --hud-surface-base: oklch(0.12 0.03 240);
      --hud-accent-base: oklch(0.75 0.18 150); /* Ultra Green Tactical */
      --hud-alert-base: oklch(0.65 0.25 25);   /* Absolute Hue Amber/Red */
      --hud-radius: 140px;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--hud-surface-base);
      color: oklch(0.95 0.01 240);
      font-family: 'JetBrains Mono', 'Segoe UI Mono', monospace;
      min-height: 100vh;
      display: flex;
      justify-content: center;
      align-items: center;
      overflow: hidden;
    }

    /* Container HUD dengan Visual Shader Glass Distortion */
    .hud-panel {
      position: relative;
      width: 480px;
      height: 480px;
      border-radius: 24px;
      padding: 24px;
      background: oklch(from var(--hud-surface-base) calc(l + 0.04) c h / 0.65);
      border: 1px solid oklch(from var(--hud-accent-base) 0.8 0.05 h / 0.2);
      box-shadow: 
        0 30px 60px oklch(0 0 0 / 0.6),
        inset 0 1px 0 oklch(1 0 0 / 0.1);
      
      /* Hubungkan CSS Filter ke Hardware-Accelerated SVG Shader */
      backdrop-filter: blur(12px) url(#hud-refraction);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }

    /* Radar Viewport */
    .radar-display {
      position: relative;
      width: calc(var(--hud-radius) * 2);
      height: calc(var(--hud-radius) * 2);
      border-radius: 50%;
      border: 1px solid oklch(from var(--hud-accent-base) l c h / 0.15);
      background: radial-gradient(
        circle,
        oklch(from var(--hud-accent-base) 0.3 0.05 h / 0.05) 0%,
        transparent 70%
      );
    }

    /* Radar Reticle Rings */
    .radar-display::before {
      content: '';
      position: absolute;
      inset: 25%;
      border-radius: 50%;
      border: 1px dashed oklch(from var(--hud-accent-base) l c h / 0.25);
    }

    /* Parametric Math Nodes (Rendering Posisi Target Finansial) */
    .market-node {
      --val-r: 0px;       /* Jarak radial (Hypot magnitude) */
      --val-deg: 0deg;    /* Sudut fase */
      
      /* Transformasi Kalkulasi Trigonometris CSS murni */
      --node-x: calc(cos(var(--val-deg)) * var(--val-r));
      --node-y: calc(sin(var(--val-deg)) * var(--val-r));

      position: absolute;
      top: 50%;
      left: 50%;
      width: 12px;
      height: 12px;
      margin-left: -6px;
      margin-top: -6px;
      border-radius: 50%;

      /* Mengubah warna secara dinamis berbanding lurus dengan jarak sudut */
      background: oklch(
        from var(--hud-accent-base) 
        l 
        c 
        calc(h + (var(--val-deg) * 0.5))
      );
      
      box-shadow: 0 0 12px oklch(
        from var(--hud-accent-base) 
        l 
        c 
        calc(h + (var(--val-deg) * 0.5)) / 0.8
      );

      transform: translate(var(--node-x), var(--node-y));
      will-change: transform;
      transition: transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
    }

    /* Injeksi posisi target secara individual */
    .node-alpha { --val-r: 110px; --val-deg: 45deg; }
    .node-beta  { --val-r: 65px;  --val-deg: 130deg; }
    .node-gamma { --val-r: 90px;  --val-deg: 260deg; }
    .node-delta { 
      --val-r: 125px; 
      --val-deg: 320deg;
      /* Override ke mode Alert dengan saturasi penuh */
      background: var(--hud-alert-base) !important;
      box-shadow: 0 0 16px var(--hud-alert-base) !important;
    }

    /* Radar Sweep Animation */
    .radar-sweep {
      position: absolute;
      inset: 0;
      border-radius: 50%;
      background: conic-gradient(
        from 0deg,
        oklch(from var(--hud-accent-base) l c h / 0.4) 0deg,
        transparent 60deg,
        transparent 360deg
      );
      animation: sweep-spin 4s linear infinite;
    }

    @keyframes sweep-spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }

    .readout-panel {
      margin-top: 1.5rem;
      font-size: 0.85rem;
      letter-spacing: 0.1em;
      color: oklch(from var(--hud-accent-base) 0.85 0.05 h);
      text-transform: uppercase;
    }
  </style>
</head>
<body>

  <!-- Hidden SVG Shader Graph Engine -->
  <svg width="0" height="0" style="position: absolute; pointer-events: none;">
    <defs>
      <!-- Pipeline Filter: Prosedural Noise + Displasemen Koordinat -->
      <filter id="hud-refraction" x="-20%" y="-20%" width="140%" height="140%">
        <!-- Tahap 1: Hasilkan gelombang noise fraktal GPU -->
        <feTurbulence 
          type="fractalNoise" 
          baseFrequency="0.04 0.04" 
          numOctaves="2" 
          result="noiseMap" />
        
        <!-- Tahap 2: Koreksi kontras vektor pergeseran -->
        <feColorMatrix 
          in="noiseMap" 
          type="matrix" 
          values="1 0 0 0 0  
                  0 1 0 0 0  
                  0 0 1 0 0  
                  0 0 0 1 0" 
          result="adjustedNoise" />

        <!-- Tahap 3: Geser piksel tampilan target berdasarkan intensitas tekstur -->
        <feDisplacementMap 
          in="SourceGraphic" 
          in2="adjustedNoise" 
          scale="8" 
          xChannelSelector="R" 
          yChannelSelector="G" />
      </filter>
    </defs>
  </svg>

  <div class="hud-panel">
    <div class="radar-display">
      <div class="radar-sweep"></div>
      <div class="market-node node-alpha"></div>
      <div class="market-node node-beta"></div>
      <div class="market-node node-gamma"></div>
      <div class="market-node node-delta"></div>
    </div>
    <div class="readout-panel">
      Tracking: 4 Targets Active [OKLCH Wide-Gamut]
    </div>
  </div>

</body>
</html>
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

### 1. Evaluasi Komparatif Ruang Warna Web

| Fitur / Karakteristik | sRGB (`rgb()`, HEX) | HSL (`hsl()`) | Display P3 (`color(display-p3)`) | OKLCH (`oklch()`) |
| :--- | :--- | :--- | :--- | :--- |
| **Gamut Volume Coverage** | Rendah (~35% ruang CIE) | Rendah (Identik dengan sRGB) | Tinggi (+50% dari sRGB) | Maksimal (Mencakup seluruh spektrum visible & wide-gamut) |
| **Perceptual Uniformity** | Buruk (Matematika linear tanpa bobot biologis) | Sangat Buruk (Distorsi kecerahan ekstrem per hue) | Buruk (Sama seperti sRGB, hanya batas koordinat diperlebar) | **Sempurna** (Disesuaikan dengan respons persepsi manusia) |
| **Pemisahan Dimensi (L, C