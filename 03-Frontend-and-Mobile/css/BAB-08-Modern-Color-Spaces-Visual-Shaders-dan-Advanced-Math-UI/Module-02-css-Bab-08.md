# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Kategori: 03-Frontend-and-Mobile
### Bab 08: Modern Color Spaces, Visual Shaders, dan Advanced Math UI
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik pada tingkat *Staff/Principal Engineer* diharapkan mampu:
- **Menganalisis & Mengisolasi Masalah Ruang Warna:** Mendiagnosis degradasi persepsi visual (*perceptual non-uniformity*), pergeseran hue (*hue-shift*), dan fenomena *gamut clipping* yang terjadi pada ruang warna sRGB konvensional.
- **Mengarsitekturi Token Desain Generasi Baru:** Merancang sistem token warna enterprise menggunakan ruang warna OKLCH dan Relative Color Syntax (RCS) berbasis CSS Color Module Level 4 & 5 dengan *automated perceptual contrast* (APCA).
- **Mengembangkan Shader Prosedural Berbasis Houdini:** Mengimplementasikan *off-main-thread procedural painting* menggunakan CSS Paint API (Paint Worklet) untuk merender visual shader berkinerja tinggi tanpa *overhead* DOM.
- **Mengkonstruksi Kalkulasi UI Non-Linear:** Memanfaatkan fungsi trigonometri CSS native (`sin()`, `cos()`, `atan2()`), fungsi kalkulasi lanjutan (`hypot()`, `round()`, `mod()`, `rem()`), serta *container queries* untuk membangun tata letak geometri kompleks dan tipografi adaptif tanpa ketergantungan pada JavaScript runtime loop.
- **Mengoptimalkan Pipeline Render Browser:** Memetakan alur eksekusi Chromium Blink/Skia/Graphite, meminimalkan *compositor layer explosion*, dan mempertahankan stabilitas frame-rate pada target 60/120 FPS.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib menguasai:
- **Arsitektur Rendering Engine:** Pemahaman mendalam mengenai alur *Style Recalculation*, *Layout (Reflow)*, *Paint*, dan *Composite (Compositor Thread & GPU)* pada Chromium/Gecko/WebKit.
- **Struktur Aljabar Linier & Trigonometri Komputasi:** Vektor, matriks rotasi 2D/3D, koordinat polar vs kartesian, kalkulasi radian dan derajat.
- **CSS Fundamental Tingkat Lanjut:** Custom Properties (`var()`), CSS Houdini baseline (`CSS.registerProperty`), Stacking Context, dan Hardware Layer Promotion (`will-change`, transform 3D).
- **Sistem Representasi Warna Digital:** Pengertian dasar CIE XYZ, sRGB, Display-P3, Adobe RGB, dan kurva gamma transfer function.

---

### 3. Concept & Internal Architecture

#### A. Evolusi Ruang Warna: Dari CIE 1931 ke OKLCH
Model sRGB (didefinisikan tahun 1996 oleh HP dan Microsoft) didesain untuk monitor CRT dengan keterbatasan ruang warna (*gamut*) yang sempit. Kelemahan fatal sRGB dan HSL terletak pada **ketidakseragaman perseptual (perceptual non-uniformity)**:
- Pada HSL, nilai saturasi 100% dan lightness 50% pada Hue $120^\circ$ (Hijau) menghasilkan luminansi perseptual yang jauh lebih tinggi daripada Hue $240^\circ$ (Biru). Mata manusia memiliki sensitivitas puncak pada spektrum hijau (panjang gelombang $\approx 555\text{ nm}$).
- Ruang warna CIELAB (1976) mencoba memperbaiki hal ini, namun mengalami distorsi rotasi hue pada wilayah biru menuju ungu (*Abney Effect*).
- **OKLab & OKLCH (diciptakan oleh Björn Ottosson, 2020):** Merupakan model warna koordinat silindris yang dibangun di atas transformasi non-linear dari ruang LMS (respon sel kerucut retina). OKLCH memisahkan:
  - $L$ (*Perceived Lightness*): Skala $0\%$ (hitam mutlak) hingga $100\%$ (putih mutlak) yang terkalibrasi linear terhadap respon fotoreseptor manusia.
  - $C$ (*Chroma*): Kemurnian/kejenuhan warna secara absolut (tidak dibatasi $0-100\%$, secara teoritis terbuka tergantung gamut target).
  - $H$ (*Hue*): Sudut rotasi $0^\circ - 360^\circ$ di mana representasi persepsi jarak sudutnya seragam di seluruh spektrum.

```
       CIE XYZ Matrix Transform        Cube Root (LMS)         Polar Transform
sRGB --------------> Linear LMS --------------> OKLab (L, a, b) --------------> OKLCH (L, C, H)
```

#### B. Gamut Mapping Engine pada Chromium (Blink / Skia / Graphite)
Ketika warna didefinisikan di luar batas fisik monitor (misal, Display-P3 pada monitor sRGB standard), browser mengeksekusi algoritma *Gamut Mapping*:
1. **Clipping:** Memotong nilai $R, G, B$ yang melebihi rentang $[0, 1]$. Pendekatan ini merusak saturasi dan menggeser *hue*.
2. **CSS Color 4 Chroma Reduction Algorithm:** Browser mempertahankan *Lightness* ($L$) dan *Hue* ($H$), lalu melakukan pencarian biner (*binary search*) untuk menurunkan nilai *Chroma* ($C$) hingga koordinat warna berada tepat di batas permukaan gamut target ($\Delta E_{\text{OK}} \le 0.00002$).

#### C. Arsitektur Evaluasi CSS Math (Trigonometri & Rounding)
Fungsi `sin()`, `cos()`, `tan()`, `asin()`, `acos()`, `atan2()`, `hypot()`, `round()`, `mod()`, dan `rem()` diproses langsung pada fase **Computed Value Time** di thread utama:
- Parser CSS memetakan ekspresi menjadi *Abstract Syntax Tree* (AST) matematika.
- Token sudut dinormalisasi ke radian: $\text{rad} = \text{deg} \times \left(\frac{\pi}{180}\right)$.
- Nilai dihitung menggunakan implementasi IEEE 754 floating-point hardware C++ browser. Jika kalkulasi berada di dalam `transform`, nilai hasil kalkulasi ditransfer ke matriks 4x4 untuk diproses langsung oleh GPU Compositor (`cc` di Chromium), tanpa memicu fase Layout berulang pada animasi berbasis CSS Custom Properties terdaftar.

#### D. Arsitektur CSS Houdini Paint API
CSS Paint Worklet mengeksekusi kode rendering kustom di thread terpisah (*Worklet Thread*), sejajar dengan alur Compositor:

```
[Main Thread]   JS Engine / DOM Mutation ---> Style Calculation ---> Layout
                                                                        |
[Worklet Thread]                                      CSS Paint API <----+ (Off-screen Canvas Context)
                                                                        |
[Compositor / GPU]                                    Rasterization <----+ (Direct Skia Draw Calls)
```

- Paint Worklet tidak memiliki akses ke DOM, *window*, atau fungsionalitas I/O jaringan.
- Kode yang dieksekusi di dalam worklet menghasilkan bitmap langsung ke backing store Skia/Graphite, mengeliminasi biaya retensi node DOM grafis (seperti ratusan elemen `<div>` atau elemen SVG kompleks).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Hex/RGB/HSL + JS Math + SVG) | Pendekatan Modern Enterprise (OKLCH + CSS Math + Paint API) |
| :--- | :--- | :--- |
| **Keseragaman Kontras Visual** | Gagal. HSL lightness tidak setara dengan persepsi kontras (misal: `hsl(240, 100%, 50%)` vs `hsl(60, 100%, 50%)`). | Konsisten secara deterministik di seluruh spektrum hue; Lightness linear menyederhanakan pemenuhan standar APCA/WCAG. |
| **Dukungan Wide-Gamut (P3)** | Terbatas pada sRGB (kehilangan $\approx 25\%$ volume spektrum warna pada layar modern Apple/OLED). | Mendukung Display-P3 dan Rec.2020 secara native dengan *fallback* Gamut Mapping otomatis. |
| **Overhead Runtime UI Dinamis** | Membutuhkan eksekusi JS (`requestAnimationFrame`) untuk menghitung posisi radial/rotasi, membebani Main Thread. | Komputasi CSS Trig terjadi di browser style engine; interpolasi transform dieksekusi di GPU Compositor Thread (Zero JS runtime). |
| **Rendering Kompleksitas Visual** | Ribuan node SVG/DOM memicu lonjakan konsumsi memori dan degradasi kalkulasi Reflow. | Houdini Paint Worklet merender langsung via bitmap canvas Skia/GPU tanpa overhead alokasi memori DOM tree. |

---

### 5. How (Workflow Detail)

Alur arsitektur implementasi pada sistem enterprise:

```
+-----------------------------------------------------------------------------------+
| 1. Design Token Pipeline (Figma Tokens / Style Dictionary)                        |
|    - Definisi warna basis dalam OKLCH (Target: Wide Gamut DCI-P3)                 |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| 2. CSS Architecture Layer (Design Tokens Engine)                                  |
|    - Implementasi Base Palette OKLCH                                              |
|    - Turunan Variasi UI via Relative Color Syntax (RCS)                           |
|    - Fallback Graceful Degradation via @supports (color: oklch(0 0 0))           |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| 3. Layout & Geometry Engine (CSS Math Level 4)                                    |
|    - Ekstraksi koordinat polar ke kartesian via sin() & cos()                     |
|    - Quantization & Snap-to-Grid via round() dan mod()                            |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| 4. Visual Rendering Subsystem                                                     |
|    - Standard Effects: Hardware-accelerated composite filter & backdrop-filter    |
|    - Complex Procedural Shaders: CSS Paint Worklet registration                   |
+-----------------------------------------------------------------------------------+
```

---

### 6. Analogy & Diagram ASCII

#### A. Perbandingan Ruang Warna (Gamut Volume)
Bayangkan ruang warna sebagai volume geometris 3D. sRGB adalah sebuah kotak kecil di dalam ruangan besar bernama Display-P3, sedangkan OKLCH adalah sistem koordinat yang mampu memetakan seluruh volume bentuk organik tersebut berdasarkan penglihatan manusia.

```
+-------------------------------------------------------------+
| OKLCH Space (Theoretical Limitless Gamut Coordinates)       |
|                                                             |
|         +-----------------------------------------+         |
|         | Display-P3 (Wide Color Gamut)           |         |
|         |                                         |         |
|         |        +-----------------------+        |         |
|         |        | sRGB (Standard Gamut) |        |         |
|         |        | [Hex / rgb() / hsl()] |        |         |
|         |        +-----------------------+        |         |
|         |                                         |         |
|         +-----------------------------------------+         |
|                                                             |
+-------------------------------------------------------------+
```

#### B. Transformasi Koordinat Polar ke Kartesian pada CSS
Untuk memposisikan elemen pada lintasan melingkar dengan radius $R$ dan sudut $\theta$:

$$\Delta X = R \cdot \cos(\theta)$$
$$\Delta Y = R \cdot \sin(\theta)$$

```
               Y-Axis (0px, -R) [Angle: 0deg / 360deg]
                       |
                       |
        (-X, -Y)       |       (+X, -Y)
                \      |      /
                 \     |     /
                  \    |    /
                   \   |   /  Radius (R)
                    \  |  /
                     \ | /
-----------------------+----------------------- X-Axis
                     / | \
                    /  |  \
                   /   |   \
                  /    |    \
                 /     |     \
        (-X, +Y)       |       (+X, +Y)
                       |
               Y-Axis (0px, +R) [Angle: 180deg]
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Relative Color Syntax & Trigonometri Native
Mengubah palet dasar secara dinamis dan mendistribusikan elemen melingkar murni dengan CSS.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <style>
    :root {
      --brand-color: oklch(0.65 0.24 260); /* Electric Blue */
      /* Derivasi warna otomatis dengan Relative Color Syntax */
      --brand-surface: oklch(from var(--brand-color) calc(l + 0.3) calc(c * 0.3) h);
      --brand-border:  oklch(from var(--brand-color) calc(l - 0.2) c h);
    }

    .orbital-container {
      position: relative;
      width: 300px;
      height: 300px;
      border: 1px dashed var(--brand-border);
      border-radius: 50%;
      margin: 50px auto;
      background: var(--brand-surface);
    }

    .satellite {
      --radius: 120px;
      --angle: 45deg; /* Sudut orbit */
      position: absolute;
      top: 50%;
      left: 50%;
      width: 40px;
      height: 40px;
      background: var(--brand-color);
      border-radius: 50%;
      
      /* Transformasi Koordinat Polar ke Kartesian via CSS Math */
      translate: calc(cos(var(--angle)) * var(--radius) - 50%)
                 calc(sin(var(--angle)) * var(--radius) - 50%);
    }
  </style>
</head>
<body>
  <div class="orbital-container">
    <div class="satellite"></div>
  </div>
</body>
</html>
```

#### B. Practical Example: Production-Ready Architectural Token Engine + Houdini Paint Shader
Implementasi sistem token adaptif gamut-aware yang mengintegrasikan CSS Paint Worklet untuk *noise visual shader*.

**Struktur File:**
```
assets/
 ├── shaders/
 │    └── procedural-grid.js
 └── css/
      └── design-system.css
```

**File: `assets/shaders/procedural-grid.js`**
```javascript
// CSS Houdini Paint Worklet: Procedural Grid Shader
class ProceduralGridPainter {
  static get inputProperties() {
    return [
      '--grid-cell-size',
      '--grid-line-color',
      '--grid-line-width',
      '--grid-subdivision'
    ];
  }

  paint(ctx, geom, properties) {
    const cellSize = parseFloat(properties.get('--grid-cell-size').toString()) || 40;
    const color = properties.get('--grid-line-color').toString().trim() || '#ffffff';
    const lineWidth = parseFloat(properties.get('--grid-line-width').toString()) || 1;
    const subdivision = parseInt(properties.get('--grid-subdivision').toString()) || 4;

    const width = geom.width;
    const height = geom.height;

    ctx.lineWidth = lineWidth;
    ctx.strokeStyle = color;

    // Gambar Grid Utama
    ctx.beginPath();
    for (let x = 0; x <= width; x += cellSize) {
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
    }
    for (let y = 0; y <= height; y += cellSize) {
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
    }
    ctx.stroke();

    // Gambar Subdivisi Halus
    const subCellSize = cellSize / subdivision;
    ctx.lineWidth = lineWidth * 0.4;
    ctx.beginPath();
    for (let x = 0; x <= width; x += subCellSize) {
      if (x % cellSize !== 0) {
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
      }
    }
    for (let y = 0; y <= height; y += subCellSize) {
      if (y % cellSize !== 0) {
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
      }
    }
    ctx.stroke();
  }
}

registerPaint('procedural-grid', ProceduralGridPainter);
```

**File: `assets/css/design-system.css`**
```css
/* Registrasi Properti untuk Animasi & Keamanan Tipe GPU */
@property --grid-cell-size {
  syntax: '<length>';
  inherits: false;
  initial-value: 32px;
}

@property --radar-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

:root {
  /* OKLCH Base Palette */
  --sys-color-primary-h: 150; /* Base Green Matrix */
  --sys-color-primary-c: 0.18;
  --sys-color-primary-l: 0.72;

  --color-primary-base: oklch(var(--sys-color-primary-l) var(--sys-color-primary-c) var(--sys-color-primary-h));
  
  /* Derivasi Variasi Aksesibel Menggunakan Relative Color Syntax */
  --color-primary-hover: oklch(from var(--color-primary-base) calc(l - 0.1) c h);
  --color-primary-active: oklch(from var(--color-primary-base) calc(l - 0.2) calc(c * 1.2) h);
  --color-primary-subtle: oklch(from var(--color-primary-base) 0.95 calc(c * 0.15) h);
  --color-surface-backdrop: oklch(0.12 0.02 var(--sys-color-primary-h));

  /* Properti Shader */
  --grid-cell-size: 40px;
  --grid-line-color: oklch(from var(--color-primary-base) 0.4 0.08 h / 0.3);
  --grid-line-width: 1px;
  --grid-subdivision: 4;
}

/* Wide-Gamut Hardware Adaptation via Media Query */
@supports (color: color(display-p3 1 1 1)) {
  @media (color-gamut: p3) {
    :root {
      /* Peningkatan kroma untuk layar high-end (DCI-P3) tanpa distorsi sRGB */
      --sys-color-primary-c: 0.24;
    }
  }
}

.radar-dashboard-card {
  position: relative;
  width: 100%;
  max-width: 480px;
  height: 480px;
  background-color: var(--color-surface-backdrop);
  /* Memanggil Houdini Paint Worklet */
  background-image: paint(procedural-grid);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 8px 32px oklch(0 0 0 / 0.5);
}

.radar-sweep {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: conic-gradient(
    from var(--radar-angle),
    transparent 0deg,
    oklch(from var(--color-primary-base) l c h / 0.25) 300deg,
    var(--color-primary-base) 360deg
  );
  animation: sweep-rotation 4s linear infinite;
  pointer-events: none;
}

/* Titik Pemantauan Terhitung secara Trigonometri */
.radar-node {
  --node-distance: 140px;
  --node-azimuth: 135deg;
  
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--color-primary-base);
  box-shadow: 0 0 12px var(--color-primary-base);
  top: 50%;
  left: 50%;

  /* Koordinat Native: cos untuk X, sin untuk Y */
  translate: calc(cos(var(--node-azimuth)) * var(--node-distance) - 50%)
             calc(sin(var(--node-azimuth)) * var(--node-distance) - 50%);
}

@keyframes sweep-rotation {
  from { --radar-angle: 0deg; }
  to   { --radar-angle: 360deg; }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario:
Sebuah platform analitik finansial enterprise (*Ultra-High-Frequency Trading Terminal*) memuat 50 widget visualisasi radar dan diagram koordinat polar secara bersamaan di layar dashboard 4K Wide-Gamut (Apple Pro Display XDR & Dell UltraSharp PremierColor).

#### Masalah Produksi:
1. **CPU Chokepoint & Battery Drain:** Implementasi awal menggunakan rendering SVG yang dimutasi melalui JavaScript runtime (`d3.js` & `requestAnimationFrame`). Ketika memuat 50 chart dengan ribuan titik node data, Main-Thread JS mengalami *jank* (frame drop hingga 18 FPS) akibat rekalkulasi layout SVG dan GC (*Garbage Collection*) pressure.
2. **Color Clashing Antar Monitor:** Analis menggunakan kombinasi laptop monitor P3 dan monitor sekunder sRGB standar. Palet berbasis HSL menghasilkan warna peringatan kritis (merah) yang tampak buram (*muddy*) pada monitor sRGB, dan terlalu silau (*oversaturated blown-out*) pada monitor P3.

#### Arsitektur Solusi:
1. **Migrasi Ruang Warna:** Seluruh sistem warna dipindahkan ke token **OKLCH**, dipadukan dengan modul fallback `@supports (color: oklch(0 0 0))`. *Perceived lightness* dikunci secara statis pada $L = 0.62$ untuk memastikan seluruh varian hue memenuhi rasio kontras APCA $\ge 60\text{ Lc}$ di atas background gelap ($L = 0.10$).
2. **Offloading Komputasi Geometri:** Logika distribusi radial dipindahkan dari JavaScript ke CSS Trigonometry Native (`cos()`, `sin()`).
3. **Migrasi Render Pipeline ke Houdini Paint API:** Elemen grid konsentris dan grid kartesian pada latar belakang chart dirender menggunakan CSS Paint Worklet off-main-thread.

#### Hasil Metrik Kinerja (Benchmarking):

```
+-----------------------------------+--------------------+--------------------+
| Metrik Kinerja                     | Legacy SVG + JS    | OKLCH + Math +     |
|                                   | (Baseline)         | Paint Worklet      |
+-----------------------------------+--------------------+--------------------+
| Main-Thread Execution Time (CPU)  | 142 ms / tick      | 4.2 ms / tick      |
| Browser Layout / Reflows          | 48 ops / sec       | 0 ops / sec        |
| Render Frame Rate (50 Chart Node) | 18 - 24 FPS (Jank) | 60 FPS (Rock solid)|
| GPU Memory Allocation (Backing)   | 480 MB             | 74 MB              |
| WCAG / APCA Compliance Rate       | 68% (Inconsistent) | 100% Deterministic |
+-----------------------------------+--------------------+--------------------+
```

---

### 9. Trade-offs

| Pendekatan / Fitur | Trade-off Positif (Keuntungan) | Trade-off Negatif (Konsekuensi & Mitigasi) |
| :--- | :--- | :--- |
| **Ruang Warna OKLCH** | Kontras perseptual konsisten di seluruh spektrum; manipulasi warna matematis akurat; akses instan ke wide-gamut Display-P3. | **Legacy Browser Support:** Browser non-modern (Chrome < 111, Safari < 15.4) tidak dapat membaca format ini. **Mitigasi:** Build-time PostCSS fallback transpilation ke sRGB. |
| **CSS Native Trigonometry** | Komputasi dieksekusi native pada thread C++ browser; nol bundle size JavaScript runtime; GPU-composited jika diikat pada `translate`/`transform`. | **Subpixel Jitter:** Pembulatan subpixel floating point pada layar berdensitas rendah ($1\times$ DPR) dapat memicu distorsi pergeseran 1px. **Mitigasi:** Gabungkan dengan `round(to-zero, ...)` |
| **CSS Paint API (Houdini)** | Rendering procedural off-main-thread; tidak ada alokasi node DOM; konsumsi memori sangat efisien. | **Platform Support Fragmented:** Belum didukung secara default di Mozilla Firefox dan Safari (membutuhkan flag/polyfill). **Mitigasi:** Pengecekan via `CSS.paintWorklet.addModule` dan graceful fallback ke SVG background. |
| **Relative Color Syntax (RCS)** | Menghilangkan duplikasi ribuan utility class; otomatisasi skema *dark/light mode* secara algoritmik. | **Debugging Complexity:** Style inspector browser saat ini masih terbatas dalam menampilkan alur derivasi matematika warna secara real-time. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Out-of-Gamut Hard Clipping
*   **Kesalahan:** Menggunakan nilai kroma ($C$) ekstrim pada OKLCH (misal: `oklch(0.7 0.45 140)`) tanpa strategi *fallback*.
*   **Dampak:** Monitor sRGB standar memotong warna secara kasar (*hard clip*), menghasilkan distorsi *hue* (warna hijau bergeser menjadi kuning kusam).
*   **Solusi:** Batasi kroma ke rentang aman sRGB ($C \le 0.20$) untuk token global, atau sediakan media query `@media (color-gamut: p3)` khusus untuk meningkatkan kroma.

#### 2. Paint Worklet Concurrency & Context Poisoning
*   **Kesalahan:** Menyimpan status lokal (*stateful*) dalam variabel scope global di dalam file Worklet script.
*   **Dampak:** Paint Worklet dijalankan di multiple thread secara acak. State global menyebabkan *rendering flicker* antar frame.
*   **Solusi:** Class Worklet harus bersifat sepenuhnya *stateless* dan *idempotent*. Seluruh input harus dialirkan melalui CSS Input Properties.

#### 3. Compositor Layer Explosion via Arbitrary `will-change`
*   **Kesalahan:** Menaruh `will-change: transform` pada setiap elemen yang diposisikan menggunakan CSS Trigonometry.
*   **Dampak:** Konsumsi VRAM GPU melonjak drastis, memicu *out-of-memory crash* pada perangkat mobile entry-level.
*   **Solusi:** Terapkan `will-change` secara selektif hanya saat elemen sedang bertransisi atau beranimasi secara aktif.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan Perceptual Gamut Fallback:**
  ```css
  /* 1. Base Fallback (Hex sRGB) */
  --surface: #1a73e8;
  /* 2. Modern OKLCH Standard */
  --surface: oklch(0.55 0.2 250);
  ```
- [ ] **Registrasikan Setiap Custom Property untuk Math Transitions:** Daftarkan tipe menggunakan `@property` untuk memastikan browser dapat melakukan interpolasi nilai non-linear alih-alih fallback ke pergantian tipe instan (*discrete swap*).
- [ ] **Hindari Magic Numbers pada Nilai Radian/Derajat:** Selalu gunakan unit implisit CSS (`deg`, `rad`, `turn`) pada parameter fungsi matematika (contoh: `sin(45deg)`, bukan `sin(45)`).
- [ ] **Sanitasi Paint Worklet Imports:**
  ```javascript
  if ('paintWorklet' in CSS) {
    CSS.paintWorklet.addModule('/assets/shaders/procedural-grid.js');
  } else {
    document.documentElement.classList.add('no-houdini');
  }
  ```
- [ ] **Pertahankan Lightness Threshold untuk Kontras:** Pada tema gelap, pertahankan lightness teks $L \ge 0.85$ dan background $L \le 0.20$ untuk menjamin kepatuhan kontras APCA tanpa bergantung pada saturation.

---

### 12. Hands-on Practice

Buat dan implementasikan sistem dial speedometer visual berbasis koordinat polar dan shader procedur di folder: `hands-on/m02/`

#### Step 1: Inisialisasi Struktur Direktori
```bash
mkdir -p hands-on/m02/shaders
cd hands-on/m02
touch index.html tokens.css dial-component.css shaders/dial-ticks.js
```

#### Step 2: Implementasi Paint Worklet Tick Radians
Tulis kode berikut pada `hands-on/m02/shaders/dial-ticks.js`:
```javascript
class DialTicksPainter {
  static get inputProperties() {
    return ['--tick-count', '--tick-color', '--tick-active-index'];
  }

  paint(ctx, geom, properties) {
    const tickCount = parseInt(properties.get('--tick-count').toString()) || 60;
    const tickColor = properties.get('--tick-color').toString().trim() || '#ffffff';
    const activeIndex = parseInt(properties.get('--tick-active-index').toString()) || 0;

    const cx = geom.width / 2;
    const cy = geom.height / 2;
    const radius = Math.min(cx, cy) - 10;
    const tickLength = 12;

    for (let i = 0; i < tickCount; i++) {
      // Hanya gambar arc 240 derajat (sudut mobil sport tradisional)
      const angle = (240 / tickCount * i + 150) * (Math.PI / 180);
      
      const x1 = cx + Math.cos(angle) * radius;
      const y1 = cy + Math.sin(angle) * radius;
      const x2 = cx + Math.cos(angle) * (radius - tickLength);
      const y2 = cy + Math.sin(angle) * (radius - tickLength);

      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.lineWidth = (i <= activeIndex) ? 3 : 1;
      ctx.strokeStyle = (i <= activeIndex) ? tickColor : 'rgba(255,255,255,0.2)';
      ctx.stroke();
    }
  }
}
registerPaint('dial-ticks', DialTicksPainter);
```

#### Step 3: Implementasi Design Tokens dan Komponen UI
Tulis kode berikut pada `hands-on/m02/tokens.css`:
```css
:root {
  --color-brand-oklch: oklch(0.68 0.28 35); /* Neon Racing Orange */
  --bg-core: oklch(0.1 0.01 35);
  --ui-accent: oklch(from var(--color-brand-oklch) l c h);
  --ui-muted: oklch(from var(--color-brand-oklch) 0.4 0.05 h);
}
```

Tulis kode berikut pada `hands-on/m02/dial-component.css`:
```css
@property --needle-val {
  syntax: '<number>';
  inherits: false;
  initial-value: 0;
}

.dial-wrapper {
  position: relative;
  width: 320px;
  height: 320px;
  background-color: var(--bg-core);
  background-image: paint(dial-ticks);
  border-radius: 50%;
  margin: 50px auto;
  --tick-count: 50;
  --tick-color: var(--ui-accent);
  --tick-active-index: calc(var(--needle-val) / 2);
}

.needle {
  /* Interpolasi sudut: 0 -> 150deg, 100 -> 390deg */
  --needle-angle: calc(150deg + (var(--needle-val) * 2.4deg));
  position: absolute;
  top: 50%;
  left: 50%;
  width: 120px;
  height: 4px;
  background: var(--ui-accent);
  transform-origin: 0% 50%;
  transform: rotate(var(--needle-angle));
  box-shadow: 0 0 8px var(--ui-accent);
  transition: --needle-val 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.center-pivot {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: white;
  translate: -50% -50%;
}
```

#### Step 4: Perakitan di `index.html`
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="tokens.css">
  <link rel="stylesheet" href="dial-component.css">
</head>
<body style="background: #000; color: #fff; font-family: sans-serif; text-align: center;">
  <h2>Telemetry Dial Core (Houdini + CSS Math Engine)</h2>
  <div class="dial-wrapper" id="speedo" style="--needle-val: 45;">
    <div class="needle"></div>
    <div class="center-pivot"></div>
  </div>
  <input type="range" min="0" max="100" value="45" id="rangeInput">

  <script>
    if ('paintWorklet' in CSS) {
      CSS.paintWorklet.addModule('./shaders/dial-ticks.js');
    }
    const dial = document.getElementById('speedo');
    document.getElementById('rangeInput').addEventListener('input', (e) => {
      dial.style.setProperty('--needle-val', e.target.value);
    });
  </script>
</body>
</html>
```

---

### 13. Exercise

#### Level: Easy
Gunakan CSS Relative Color Syntax untuk membuat palet *State* interaktif dari 1 variabel acuan:
- Input: `var(--base-color: oklch(0.5 0.15 200))`
- Buat `--state-hover` (Lightness bertambah $15\%$, Chroma konstan).
- Buat `--state-pressed` (Lightness berkurang $10\%$, Chroma bertambah $20\%$).
- Buat `--state-focus-ring` (Lightness konstan, Kroma berkurang $50\%$, Alpha $0.4$).

#### Level: Medium
Bangun sistem tata letak jam analog (12 penanda angka) menggunakan **satu container** dan 12 elemen `span` anak tanpa menggunakan `transform: rotate(...) translate(...)`.
- Seluruh penempatan posisi elemen **wajib** menggunakan kombinasi CSS `sin()`, `cos()`, dan fungsi `translate: calc(...) calc(...)`.

#### Level: Hard
Kembangkan CSS Paint Worklet yang menerima `--noise-frequency` dan `--gradient-stops` untuk menghasilkan efek visual *Perlin Noise Vignette* prosedural langsung di background canvas tanpa image assets eksternal. Sediakan graceful degradation SVG Data URI ketika Paint API tidak didukung oleh browser klien.

---

### 14. Challenge

**Skenario Sistem:**
Anda adalah Staff Architect di sebuah perusahaan pemetaan navigasi maritim global. Anda diminta mendesain *HUD Radar Overlay* real-time berbasis web yang beroperasi di anjungan kapal.
- **Kondisi Ekstrem:** Display kapal bervariasi dari panel monokrom industri hingga layar OLED Display-P3 berkecerahan 2000 nits.
- **Batasan Skalabilitas:** Terdapat hingga 500 kapal target yang koordinat sudut azimuth dan jarak radarnya diperbarui setiap 200ms via WebSockets.
- **Tantangan Arsitektur:**
  1. Rancang arsitektur komponen CSS murni di mana updating koordinat target polar **tidak pernah** memicu Layout/Reflow di thread utama browser.
  2. Implementasikan sistem palet darurat adaptif menggunakan OKLCH: Jika HUD mendeteksi sensor cahaya sekitar rendah (*night vision mode*), seluruh UI otomatis mengubah $L$ dan $C$ ke spektrum merah ($H \approx 25^\circ$) dengan kalkulasi kontras otomatis agar tidak menyilaukan nahkoda tanpa mengubah struktur token hierarkis aplikasi.
  3. Pastikan memori thread browser stabil tanpa alokasi garbage collection layer baru saat render looping berlangsung.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Mengapa ruang warna sRGB dinilai inferior dibanding OKLCH dalam perancangan token warna modern?**
   - A. sRGB tidak didukung oleh browser Chromium.
   - B. sRGB memiliki distorsi perseptual di mana nilai Lightness tidak merepresentasikan persepsi kecerahan mata manusia secara seragam.
   - C. sRGB mengonsumsi lebih banyak VRAM GPU dibandingkan OKLCH.
   - D. sRGB tidak dapat dikonversi ke format CMYK.

2. **Parameter $C$ dalam koordinat warna `oklch(L C H)` merepresentasikan:**
   - A. Cyan spectrum saturation.
   - B. Chroma (kemurnian/intensitas saturasi warna secara absolut).
   - C. Color-contrast index.
   - D. Channel compression ratio.

3. **Apa hasil dari evaluasi fungsi CSS `cos(0deg)`?**
   - A. `0`
   - B. `-1`
   - C. `1`
   - D. `undefined`

4. **Sintaks Relative Color Syntax (RCS) yang benar untuk menghasilkan warna dengan transparansi 50% dari variabel `--brand` adalah:**
   - A. `color-mix(in oklch, var(--brand), transparent 50%)`
   - B. `oklch(from var(--brand) l c h / 0.5)`
   - C. `oklch(var(--brand), alpha(0.5))`
   - D. `var(--brand, opacity=0.5)`

5. **Di thread browser manakah fungsi dari CSS Houdini Paint Worklet dieksekusi secara native?**
   - A. Main DOM Thread.
   - B. V8 Garbage Collector Thread.
   - C. Worklet / Background Thread terpisah yang terisolasi dari DOM.
   - D. Database IndexedDB Thread.

#### Bagian 2: Intermediate (5 Soal)
6. **Apa yang terjadi secara internal di rendering engine Chromium saat sebuah warna OKLCH berada di luar gamut fisik layar yang digunakan pengguna?**
   - A. Browser melempar fatal error CSS syntax.
   - B. Browser melakukan clipping koordinat RGB secara acak.
   - C. CSS Gamut Mapping Algorithm menurunkan Chroma secara biner dengan mempertahankan Lightness dan Hue hingga warna muat dalam gamut monitor.
   - D. Nilai warna otomatis di-fallback ke `#000000`.

7. **Mengapa penggunaan CSS Trigonometry untuk kalkulasi layout polar lebih optimal dibanding manipulasi koordinat melalui `element.style.left` via JavaScript?**
   - A. CSS Math otomatis mengabaikan CSS Box Model.
   - B. Kalkulasi trigonometri dieksekusi di fase computed style dan transformasinya dapat di-offload langsung ke GPU Compositor tanpa memicu reflow layout.
   - C. JavaScript tidak memiliki implementasi native fungsi `sin` dan `cos`.
   - D. V8 Engine membatasi floating point precision JavaScript hingga 8-bit.

8. **Fungsi CSS Math `round(to-zero, 15.7px, 5px)` akan menghasilkan nilai:**
   - A. `16px`
   - B. `20px`
   - C. `15px`
   - D. `15.5px`

9. **Manakah dari batasan berikut yang merupakan restriksi keamanan & arsitektural dari CSS Paint API?**
   - A. Tidak dapat membaca input CSS Custom Properties.
   - B. Tidak dapat mengakses DOM, variabel global `window`, atau memuat network asset via `fetch()`.
   - C. Tidak mendukung canvas context 2D primitives.
   - D. Hanya dapat beroperasi pada elemen bertipe `<canvas>`.

10. **Apa kegunaan utama mendefinisikan `@property` secara eksplisit dibanding Custom Property biasa (`--my-var`) saat bekerja dengan visual shader?**
    - A. Mempercepat download file CSS.
    - B. Memberi tahu browser tipe data syntax property sehingga nilainya dapat diinterpolasi (dianimasikan) secara halus oleh engine rendering.
    - C. Mencegah user mengedit nilai melalui inspect element.
    - D. Mengubah property menjadi komponen Shadow DOM.

#### Bagian 3: Analisis Skenario Kasus Produksi (3 Soal)
11. **Skenario Kasus 1:**
    Sebuah aplikasi web e-commerce menerapkan tema dinamis berbasis warna toko penjual menggunakan OKLCH: `oklch(from var(--seller-base) 0.8 c h)`. Ditemukan bahwa jika toko memilih warna kuning murni, teks putih di atasnya sama sekali tidak terbaca, melanggar WCAG 2.1 AA. Solusi arsitektur CSS murni apa yang paling deterministik untuk memecahkan masalah ini?
    - A. Beralih kembali ke model warna HEX.
    - B. Menggunakan fungsi `round()` untuk membulatkan kontras.
    - C. Menggunakan Lightness Threshold Switching via kalkulasi linear matematika atau menerapkan conditional color generation dengan memanfaatkan `color-mix()` terhadap target luminansi APCA standar.
    - D. Memaksa monitor pengguna masuk ke mode invert color.

12. **Skenario Kasus 2:**
    Sebuah tim front-end mengeluhkan terjadinya *micro-stuttering/jank* saat memutar jarum kompas UI yang menggunakan `translate: calc(cos(var(--a)) * 100px) calc(sin(var(--a)) * 100px)`. Pemeriksaan profiler menunjukkan tingginya waktu Style Recalculation. Apa penyebab utama dan tindakan mitigasi teknisnya?
    - A. Browser mengevaluasi ulang rumus pada Main Thread setiap frame karena `--a` diubah lewat JS tanpa registrasi `@property`. Daftarkan `--a` dengan syntax `<angle>`.
    - B. Fungsi `sin()` dan `cos()` tidak boleh digunakan bersamaan di properti `translate`.
    - C. GPU tidak mendukung perhitungan sudut negatif; ubah seluruh unit ke `turn`.
    - D. Terjadi *memory leak* pada CSS file cache; hapus Service Worker.

13. **Skenario Kasus 3:**
    Aplikasi Anda melayani pengguna perangkat high-end (MacBook Liquid Retina P3) dan low-end (budget smartphone Android sRGB). Tim desain menuntut saturasi warna yang menyala (*vibrant*) untuk kampanye promo, namun tidak boleh menghasilkan artefak *banding* atau distorsi warna pada perangkat mobile. Bagaimana strategi CSS Color Level 4 yang harus dipasang?
    - A. Menyajikan dua stylesheet terpisah yang dideteksi melalui User-Agent sniffing.
    - B. Mengatur warna dasar dalam rentang sRGB yang aman, lalu menggunakan media query `@media (color-gamut: p3)` untuk menimpa token tersebut dengan nilai kroma Display-P3 yang lebih tinggi.
    - C. Menghapus konfigurasi gamut dan mengandalkan auto-saturation browser Android.
    - D. Merender seluruh UI promo sebagai WebGL context.

---

### Kunci Jawaban & Rubrik Evaluasi

#### Bagian 1: Basic
1. **B** - sRGB memiliki masalah fundamental ketidakseragaman perseptual (perceived lightness berbeda drastis pada hue berbeda walau nominal value-nya sama).
2. **B** - $C$ merepresentasikan Chroma (tingkat kemurnian/kejenuhan warna absolut dalam ruang silindris OKLab).
3. **C** - Nilai cosinus dari $0^\circ$ secara matematis adalah $1$.
4. **B** - Format Relative Color Syntax CSS Color 5 mendefinisikan perubahan saluran melalui format `oklch(from var(...) l c h / alpha)`.
5. **C** - Paint Worklet dieksekusi di background thread independen tanpa membebani Main DOM Thread browser.

#### Bagian 2: Intermediate
6. **C** - Browser modern menggunakan Gamut Mapping Algorithm spesifikasi CSS Color 4 yang melakukan reduksi Chroma bertahap hingga warna berada di batas spektrum target tanpa merusak Lightness dan Hue.
7. **B** - Integrasi CSS Math native memotong latensi sinkronisasi JS-to-C++ bridge dan eksekusi transformasi dilakukan di Compositor Thread.
8. **C** - `to-zero` membulatkan angka ke kelipatan terdekat menuju angka nol (15.7px dibulatkan ke kelipatan 5px terdekat ke arah nol adalah 15px).
9. **B** - Paint Worklet dirancang *sandboxed* untuk keamanan dan performa: dilarang mengakses DOM, objek `window`, maupun I/O asynchronous.
10. **B** - Browser membutuhkan registrasi metadata tipe data property via `@property` agar engine layout/paint mengetahui cara menginterpolasi kalkulasi antar dua state.

#### Bagian 3: Analisis Kasus Produksi
11. **C** - Masalah kontras diselesaikan dengan mengatur lightness adaptif terhadap latar belakang secara matematis atau dengan mekanisme *color contrast derivation*, mengunci rasio APCA.
12. **A** - Custom Properties yang tidak terdaftar lewat `@property` diperlakukan sebagai string token murni, mematikan kemampuan browser melakukan optimasi fast-path interpolation pada rendering engine.
13. **B** - Media query `@media (color-gamut: p3)` adalah standar industri enterprise untuk mendistribusikan wide-gamut tokens secara adaptif tanpa merusak representasi visual pada panel layar standar sRGB.

---

### 16. Summary

1. **Modern Color Space (OKLCH):** Memisahkan dimensi warna secara independen ke dalam *Lightness*, *Chroma*, dan *Hue*. OKLCH menghilangkan anomali pergeseran hue pada manipulasi warna dan menjamin konsistensi aksesibilitas kontras visual (APCA/WCAG) di seluruh spektrum visual.
2. **Relative Color Syntax (RCS):** Memungkinkan derivasi skema warna dinamis langsung pada level stylesheet tanpa bantuan script runtime JavaScript, meminimalkan kompleksitas arsitektur token enterprise.
3. **CSS Trigonometry & Advanced Math UI:** Fungsi `sin()`, `cos()`, `atan2()`, `round()`, dan `mod()` memindahkan beban kalkulasi tata letak geometri non-linear dan animasi polar langsung ke thread native rendering engine (C++/GPU Compositor), mengeliminasi *frame-jank* akibat eksekusi skrip di Main Thread.
4. **CSS Houdini Paint API:** Solusi arsitektur grafis mutakhir untuk menghasilkan efek visual prosedural (*visual shaders*) dengan konsumsi memori sangat rendah, bekerja di luar thread utama tanpa menghasilkan overhead node grafis pada struktur DOM tree.