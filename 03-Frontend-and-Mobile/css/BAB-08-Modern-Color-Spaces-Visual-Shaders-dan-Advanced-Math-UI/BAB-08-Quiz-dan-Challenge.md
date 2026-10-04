# BAB 08: Quiz, Challenge, & Knowledge Check
**Modern Color Spaces, Visual Shaders, dan Advanced Math UI**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Perceptual Uniformity dan Keterbatasan Ruang Warna Tradisional
Jelaskan kelemahan matematis mendasar dari ruang warna sRGB dan HSL dalam konteks *perceptual uniformity*. Mengapa nilai *lightness* $50\%$ pada warna kuning HSL (`hsl(60 100% 50%)`) secara fisiologis tampak jauh lebih terang bagi mata manusia (*Helmholtz-Kohlrausch effect*) dibandingkan nilai *lightness* $50\%$ pada warna biru HSL (`hsl(240 100% 50%)`), dan bagaimana arsitektur CIE LCH serta Oklch mengeliminasi anomali ini?

### Soal 1.2: Gamut Mapping, Wide Gamut (Display P3), dan Clipping
Uraikan perbedaan mendasar antara *gamut clipping* dan *gamut mapping* ketika sebuah *color value* yang didefinisikan dalam `color(display-p3 ...)` atau `oklch(...)` dirender pada panel layar perangkat keras yang hanya mendukung rentang warna sRGB. Bagaimana CSS Color Module Level 4 menstandarkan algoritma reduksi kroma agar hue dan lightness tidak mengalami pergeseran destruktif (*hue shifting*)?

### Soal 1.3: Mekanisme Komputasi Fungsi Trigonometri CSS
Bagaimana browser engine mengompilasi dan mengevaluasi fungsi trigonometri CSS (`sin()`, `cos()`, `tan()`, `asin()`, `acos()`, `atan()`, `atan2()`) di dalam CSS Object Model (CSSOM)? Jelaskan secara matematis bagaimana kombinasi `sin()` dan `cos()` bersama unit polaritas sudut (`deg`, `rad`, `turn`) dapat memposisikan elemen anak pada lintasan sirkular relatif terhadap pusat elemen induk tanpa memanipulasi koordinat Kartesius melalui JavaScript.

### Soal 1.4: Semantik Evaluasi `mod()`, `rem()`, dan `hypot()`
Jelaskan perbedaan mendasar antara fungsi matematika CSS `mod()` dan `rem()` saat berhadapan dengan operan bernilai negatif (*negative dividend/divisor*). Selanjutnya, berikan analisis matematis mengapa fungsi `hypot()` jauh lebih efisien dan tahan terhadap *overflow/underflow* numerik dibandingkan formulasi manual menggunakan kombinasi `calc(sqrt(var(--x) * var(--x) + var(--y) * var(--y)))`.

### Soal 1.5: Siklus Render Visual Shader: `filter` vs `backdrop-filter`
Analisis *pipeline* *rasterization* dan *compositing* browser ketika mengeksekusi properti `filter` versus `backdrop-filter`. Mengapa pengaplikasian `backdrop-filter: blur(...)` memerlukan *intermediate offscreen buffer* (penyalinan permukaan render di belakang elemen / *read-back pixel trap*), dan bagaimana perilaku ini memengaruhi konsumsi bandwidth memori GPU secara radikal dibandingkan filter konvensional?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik Stacking Context dan Bleeding pada `mix-blend-mode`
Sebuah layout visual mengalami *visual bug* di mana elemen teks dengan properti `mix-blend-mode: difference` memengaruhi elemen latar belakang global di luar kontainer pembungkusnya, merusak kontras elemen lain di seluruh *viewport*.
* Identifikasi akar masalah internal pada *compositing engine* browser.
* Bagaimana implementasi properti `isolation: isolate` secara mekanis memotong propagasi blending group, dan apa dampaknya terhadap pembentukan *stacking context* baru?

### Soal 2.2: Memory Leak dan Fill-Rate Saturation pada SVG Filter Primitives
Diberikan deklarasi filter CSS yang mereferensikan elemen SVG:
```css
.distort {
  filter: url(#displacement-filter);
}
```
```xml
<svg>
  <filter id="displacement-filter">
    <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="4" result="noise" />
    <feDisplacementMap in="SourceGraphic" in2="noise" scale="30" xChannelSelector="R" yChannelSelector="G" />
  </filter>
</svg>
```
Ketika elemen dengan kelas `.distort` dianimasikan posisinya menggunakan CSS `@keyframes` pada layar HiDPI (Retina), terjadi *jank* ekstrem dan crash GPU pada perangkat mobile. Lakukan bedah performa: mengapa komputasi per-piksel pada `feDisplacementMap` dan `feTurbulence` menyebabkan saturasi *pixel fill-rate*, dan mitigasi struktural apa yang harus diterapkan?

### Soal 2.3: Anomali Interpolasi Hue Polar pada `color-mix()`
Evaluasi ekspresi CSS berikut:
```css
/* Kasus A */
background: color-mix(in srgb, red 50%, blue);

/* Kasus B */
background: color-mix(in oklch shorter hue, red 50%, blue);

/* Kasus C */
background: color-mix(in oklch longer hue, red 50%, blue);
```
Jelaskan mengapa Kasus A menghasilkan warna abu-abu kusam berlumpur (*gray dead zone*), sedangkan Kasus B menghasilkan transisi ungu cerah, dan Kasus C menghasilkan rona hijau-kuning yang sama sekali tidak ada pada warna input. Apa yang terjadi pada komputasi lintasan lingkaran hue ($360^\circ$) pada masing-masing kasus?

### Soal 2.4: Edge Case Sub-Pixel Rounding pada `round()` dan `clamp()`
Dalam sebuah sistem tipografi modular, seorang engineer menulis:
```css
font-size: clamp(1rem, round(to-zero, 5vw, 0.25rem), 3rem);
```
Pada beberapa versi browser WebKit dan Gecko, teks mengalami flickering/getaran mikroskopik saat viewport di-resize secara perlahan.
* Jelaskan mengapa evaluasi *sub-pixel antialiasing* dan pemotongan nilai desimal oleh `round(to-zero, ...)` berinteraksi secara buruk dengan engine rasterizer teks.
* Strategi rounding apa (`nearest`, `up`, `down`, `to-zero`) yang secara matematis stabil untuk kalkulasi *fluid layout* tanpa memicu layout re-computation rekursif?

### Soal 2.5: GPU Overdraw dan Layer Explosion pada Mask Compositing
Analisis implementasi *multi-layered mask* berikut:
```css
.card {
  mask-image: radial-gradient(circle at 50% 50%, black 60%, transparent 100%), 
              linear-gradient(to bottom, black 0%, transparent 100%);
  mask-composite: intersect;
  backdrop-filter: blur(15px);
  will-change: transform;
}
```
Uraikan langkah demi langkah bagaimana GPU memproses properti di atas. Mengapa penggabungan `mask-composite` non-standar dengan `backdrop-filter` dan `will-change: transform` memicu alokasi VRAM yang sangat masif pada DOM berukuran besar, dan apa implikasi kegagalan *hardware acceleration* (*unpromoted software fallback*) pada skenario ini?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Frame-Rate Collapse pada Multi-Layer Glassmorphic Trading Dashboard
**Kondisi Produksi:**
Sebuah platform analitik finansial enterprise menampilkan *real-time streaming grid* dengan 150 panel data (*widgets*). Desainer UI menerapkan estetika *glassmorphism* modern dengan CSS berikut pada setiap panel:
```css
.panel {
  background: color-mix(in oklch, white 15%, transparent);
  backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid color-mix(in oklch, white 25%, transparent);
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.panel:hover {
  transform: translateY(-4px) scale(1.01);
}
```
**Insiden:**
Ketika pengguna melakukan *fast scrolling* atau saat chart di-update via WebSockets pada 60fps, GPU Safari dan Chrome pada workstation Apple Silicon (M-series) dan Windows High-Refresh Rate mengalami *frame drop* fatal dari 120 FPS ke 8–14 FPS. CPU Core Usage tetap rendah, tetapi WindowServer/DWM (Desktop Window Manager) memakan 100% thread GPU, mengakibatkan *thermal throttling*.

**Pertanyaan Diagnostik:**
1. Bedah secara mendalam mengapa perkalian geometris dari 150 node dengan `backdrop-filter: blur()` memicu *GPU fill-rate exhaustion* dan *buffer read-back stall*.
2. Rancang arsitektur refactoring berbasis CSS murni (mengubah compositing strategy, isolasi layer, dan teknik pseudo-element virtualization) untuk menjaga estetika frosted glass yang identik tanpa memicu re-filtering global pada setiap frame tick.

---

### Skenario B: Degradasi Tonal Identitas Brand Global pada Dynamic Gamut Mapping
**Kondisi Produksi:**
Sebuah brand fashion luxury global meluncurkan *redesign* sistem desain digital menggunakan *wide-gamut color tokens* berbasis `oklch()` untuk mereproduksi warna jingga neon fisik ikonik mereka yang berada di luar spektrum warna sRGB:
```css
:root {
  --brand-primary: oklch(0.68 0.26 45.2); /* Ultra-saturated Neon Orange di P3/Rec.2020 */
  --brand-surface: oklch(0.98 0.02 45.2);
  --brand-contrast-text: oklch(0.20 0.05 45.2);
}
```
**Insiden:**
Saat diuji pada perangkat mobile modern (iPhone Pro, Samsung Ultra OLED), warna terlihat memukau dan lulus uji kontras WCAG AAA. Namun, saat diakses oleh jutaan pelanggan di monitor korporat sRGB standar (Dell/HP standard enterprise gamut) dan perangkat Android low-tier:
* Warna jingga neon mengalami *hue clipping* liar menjadi cokelat lumpur kekuningan.
* Rasio kontras teks runtuh dari 7:1 menjadi 2.8:1, menghasilkan kegagalan fatal pada audit aksesibilitas ADA/WCAG dan kebingungan brand visual (*brand inconsistency*).

**Pertanyaan Diagnostik:**
1. Mengapa algoritma *native gamut clipping* browser lama secara destruktif mengubah *hue angle* saat nilai kroma Oklch dipangkas secara paksa ke batasan kubus sRGB?
2. Susun arsitektur Color Token Fallback bertingkat yang defensif (*progressive enhancement*) menggunakan `@supports`, media query `@media (color-gamut: p3)`, dan formula `color-mix()` untuk menjamin integritas persepsi visual dan kepatuhan WCAG di seluruh variasi gamut perangkat keras display.

---

### Skenario C: Circular Dynamic HUD Layout & Trigonometric Performance Trade-off
**Kondisi Produksi:**
Anda bertindak sebagai Principal UI Architect untuk web application simulasi penerbangan (Aviation SaaS). Tim engineering sebelumnya menggunakan JavaScript library (ribuan requestAnimationFrame calls) untuk menghitung posisi koordinat Kartesius ($x = r \cdot \cos(\theta)$, $y = r \cdot \sin(\theta)$) dari 64 radar blip interaktif yang tersusun melingkar pada instrumen analog cockpit.

Tim berniat me-refactor seluruh sistem posisi radar ke CSS Trigonometry murni:
```css
.blip {
  --radius: 200px;
  --angle: 45deg;
  /* Formula CSS Trigonometri baru */
  transform: translate(
    calc(var(--radius) * cos(var(--angle))),
    calc(var(--radius) * sin(var(--angle)))
  );
}
```
**Trade-off & Dilema:**
Sebagian browser lawas pada enterprise intranet klien belum mendukung CSS Trigonometric Functions Level 4, tetapi tim backend mewajibkan *zero-JS dependency* pada UI layout rendering demi kestabilan main-thread saat pengolahan data telemetri berkecepatan tinggi.

**Pertanyaan Diagnostik:**
1. Bagaimana Anda menyusun arsitektur fallback matematis murni menggunakan properti transformasi CSS standar (kombinasi `rotate()`, `translate()`, dan inverse `rotate()`) yang menghasilkan representasi spasial identik dengan formula `cos`/`sin` di atas tanpa JavaScript?
2. Analisis perbandingan *computational cost* pada browser rendering pipeline (Recalculate Style, Layout, Composite) antara teknik trigonometri modern `translate(calc(... cos ...))` versus manipulasi rotasi matriks `transform: rotate(...) translate(...) rotate(...)`. Pendekatan mana yang lebih efisien meminimalkan alokasi transform matrix internal pada GPU?

---

## 4. Chapter Challenge

### Tantangan Praktis: Engineered Reactive Glassmorphic Radar HUD with Wide-Gamut Palette & Pure CSS Trigonometry

#### Deskripsi Skenario
Rancang dan bangun komponen antarmuka analitik avionik / radar sci-fi interaktif berdensitas tinggi (*heads-up display* / HUD) yang memanfaatkan seluruh keunggulan sistem kalkulasi warna modern, shader visual grafis, dan matematika trigonometri murni. Sistem ini harus beroperasi secara *fluid*, responsif, memiliki performa visual 60/120 FPS tanpa jank, dan bebas dari ketergantungan JavaScript untuk manipulasi layout spasialnya.

#### Requirements
1. **Mathematical Spatial Layout (Pure CSS Trigonometry):**
   * Buat sebuah sirkular radar disk yang merender minimal 12 target/blip avionik.
   * Posisi masing-masing target harus dikalkulasikan murni via CSS menggunakan `--angle` (0 hingga 360 derajat) dan `--distance` (persentase atau radius absolut) menggunakan fungsi `sin()` dan `cos()`.
   * Implementasikan scanning-sweep line kontinu yang berotasi $360^\circ$ menggunakan CSS `@keyframes`.
   * Ketika scanning-sweep line melintasi target blip, target harus menampilkan animasi visual *re-ping* (memanfaatkan kalkulasi CSS Math atau koordinasi variabel CSS murni).

2. **Perceptually Uniform Wide-Gamut Architecture:**
   * Bangun token sistem warna berbasis `oklch()` yang mencakup: Base Background, Scanning Sweep, Warning Target, Neutral Target, dan Target Reticle.
   * Gunakan `color-mix()` untuk menghasilkan variasi saturasi dinamis, state hover, dan *alpha channel transparency* tanpa pernah beralih ke representasi Hex atau RGB konvensional.
   * Sediakan fallback gamut bertingkat melalui `@supports (color: oklch(0 0 0))` dan `@media (color-gamut: p3)` sehingga perangkat P3 menampilkan warna ultra-vibrant, sedangkan panel sRGB menampilkan warna yang ter-gamut-map secara presisi dengan kontras teks terjaga.

3. **High-Performance Visual Shaders & Compositing:**
   * Aplikasikan lapisan *glassmorphic frosted surface* pada panel radar menggunakan `backdrop-filter: blur(...)` dan *monochromatic noise shader* berbasis SVG filter (`<feTurbulence>`).
   * Amankan seluruh pipeline blending menggunakan `isolation: isolate` untuk mencegah *compositing bleed*.
   * Pastikan tidak terjadi *layout thrashing* atau GPU memory overload: semua animasi harus dibatasi secara ketat pada properti transform dan opacity yang diakselerasi hardware.

4. **Advanced Math Sizing & Stepping:**
   * Dimensi radar, font HUD, dan padding harus diskalakan secara fluid menggunakan formula terpadu yang memadukan `clamp()`, `min()`, `hypot()`, dan fungsi stepping `round()` ke grid kelipatan unit tertentu (misal: membulatkan nilai sizing ke unit kelipatan 4px atau 8px terdekat secara dinamis).

#### Constraints
* **Zero JavaScript for Layout/Animation:** Dilarang menggunakan JavaScript untuk kalkulasi posisi trigonometri, perputaran radar sweep, atau interpolasi warna. JS hanya diperbolehkan (opsional) untuk menyuntikkan data kustom properti (`--angle`, `--distance`) pada simulasi initial mount.
* **GPU Memory Safe:** DOM node maksimum tidak boleh melebihi 50 elemen; dilarang menggunakan duplikasi nested backdrop-filter yang dapat memicu crash compositor GPU.
* **Strict Modern Standards:** Dilarang keras menggunakan model warna usang (`rgb()`, `hsl()`, atau hex 6-digit) pada stylesheet utama. Semua wajib dideklarasikan dalam `oklch()` atau `color(display-p3 ...)`.

#### Expected Output
Dokumentasi kode terstruktur yang mencakup:
1. Blok SVG Filter embedded untuk visual refraction/noise shader.
2. Arsitektur CSS Tokens lengkap dengan progressive gamut fallback.
3. Struktur HTML semantik komponen HUD.
4. Stylesheet modular lengkap dengan implementasi layout trigonometri dan optimasi compositing GPU.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur CIE LCH dan Oklch serta alasan matematis mengapa Oklch superior dalam hal perceptual uniformity dibanding HSL dan CIELAB (mengatasi kurvatur hue biru-ke-ungu).
- [ ] Perbedaan fisis antara Gamut Layar Perangkat Keras (sRGB, Display P3, Rec.2020) dan Ruang Warna Koordinat CSS.
- [ ] Algoritma Gamut Mapping di CSS Color Level 4 (Kroma reduction vs Clipping) dan implikasinya terhadap kontras rasio WCAG.
- [ ] Cara kerja engine rendering browser terhadap fungsi trigonometri CSS (`sin()`, `cos()`, `tan()`, `asin()`, `acos()`, `atan()`, `atan2()`).
- [ ] Perbedaan semantik dan hasil operan negatif antara `mod()` dan `rem()`.
- [ ] Alasan komputasi `hypot()` lebih stabil secara floating-point numerik dibanding formulasi phytagoras manual di CSS.
- [ ] Mekanisme sub-pixel rounding pada fungsi `round()` (`nearest`, `up`, `down`, `to-zero`) dan dampaknya pada anti-aliasing rendering.
- [ ] Pipeline render grafis: Compositor Layer, Rasterization, Texture Memory, Stacking Context, dan Isolasi Blending Group (`isolation: isolate`).
- [ ] Biaya performa GPU dari `backdrop-filter` (copy surface texture / read-back) dibandingkan elemen `filter` standar.
- [ ] Cara kerja filter primitif SVG grafis (`feTurbulence`, `feDisplacementMap`, `feColorMatrix`) ketika diintegrasikan ke dalam ekosistem CSS.

### Saya tidak perlu menghafal:
- [ ] Matriks transformasi numerik eksak 3x3 untuk konversi koordinat linear CIE XYZ ke sRGB atau D65-adapted P3.
- [ ] Implementasi algoritma internal C++ browser engine untuk deret Taylor / aproksimasi floating-point fungsi sinus dan cosinus.
- [ ] Nilai eksak koefisien panjang gelombang respons fotoreseptor mata (*CIE standard observer curves*).
- [ ] Spesifikasi sintaks legacy dari filter vendor-prefix usang (`-webkit-filter`).

### Saya harus bisa melakukan:
- [ ] Mengonversi sistem desain legacy berbasis Hex/RGB/HSL ke arsitektur token modern Oklch dengan variasi dinamis via `color-mix()`.
- [ ] Membangun layout melingkar (*radial layout*), diagram polar, partikel orbit, dan *dynamic circular meters* murni menggunakan CSS `sin()` dan `cos()`.
- [ ] Melakukan debugging visual pada insiden *color bleeding* atau hilangnya elemen UI akibat salah konfigurasi `mix-blend-mode` dan *stacking context*.
- [ ] Mengisolasi komponen glassmorphism performa tinggi menggunakan batasan layer GPU dan arsitektur *pseudo-element decoupling*.
- [ ] Menulis arsitektur fallback *wide-gamut* defensif menggunakan gabungan `@supports`, media query `@media (color-gamut)`, dan sistem token adaptif.
- [ ] Memanfaatkan `clamp()`, `hypot()`, dan `round()` untuk membangun sistem tipografi dan grid fluid tanpa media query yang bebas dari layout oscillation (getaran sub-pixel).
- [ ] Melakukan profiling visual shader di Chrome DevTools (Rendering panel: *Layer borders*, *Frame Rendering Stats*, *GPU rasterization view*) untuk mendeteksi bottleneck *composite cost*.