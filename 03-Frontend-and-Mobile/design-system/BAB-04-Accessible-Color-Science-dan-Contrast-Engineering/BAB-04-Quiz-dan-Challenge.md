# BAB 04: Quiz, Challenge, & Knowledge Check
**Accessible Color Science & Contrast Engineering**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Transformasi Gamma Companding ke Linear Radiance:**  
   Mengapa perhitungan *relative luminance* ($Y$) dalam standar CIE 1931/WCAG 2.1 mengharuskan nilai kanal sRGB 8-bit dide-kompresi terlebih dahulu melalui fungsi invers *gamma companding* ($sRGB \to sRGB_{linear}$), dan apa implikasi matematisnya terhadap rasio kontras jika kalkulasi dilakukan langsung pada ruang non-linear?

2. **Batasan Matematis WCAG 2.1 ($L_1/L_2$ Ratio) vs. Human Visual System (HVS):**  
   Formula WCAG 2.1 menggunakan formula rasio sederhana $\frac{L_1 + 0.05}{L_2 + 0.05}$. Jelaskan dua kelemahan fundamental formula ini ditinjau dari neurobiologi penglihatan manusia, khususnya terkait persepsi *spatial frequency* (ketebalan/ukuran teks) dan fenomena *irradiance/halation* pada polaritas teks terang di atas latar belakang gelap (*dark mode*).

3. **Perceptual Uniformity: sRGB/HSL vs. Oklab/Oklch:**  
   Saat membangun *tonal palette* sistematis untuk sebuah Design System, mengapa manipulasi parameter *Lightness* ($L$) pada HSL gagal menghasilkan kontras yang konsisten antar *hue*, sedangkan ruang warna Oklch mampu mempertahankan kontras perseptual yang seragam (*perceptually uniform*)?

4. **Kalkulasi Deterministik Alpha Compositing (Porter-Duff *Source Over*):**  
   Jika sebuah token teks memiliki nilai warna RGBA semi-transparan $C_{fg} = (R_{fg}, G_{fg}, B_{fg}, \alpha)$ yang dirender di atas latar belakang *solid* $C_{bg} = (R_{bg}, G_{bg}, B_{bg})$, jelaskan formula linear yang harus dieksekusi oleh mesin kalkulator kontras untuk mengonversi layer tersebut menjadi *effective opaque RGB* sebelum menghitung nilai luminansinya.

5. **Spatial Frequency & Fenomena *Simultaneous Contrast*:**  
   Bagaimana fenomena fisiologis *simultaneous contrast* (efek induksi lateral pada retina) dapat menyebabkan dua elemen teks dengan nilai heksadesimal dan *measured contrast ratio* yang identik terlihat memiliki keterbacaan (*legibility*) yang berbeda secara signifikan saat ditempatkan pada latar belakang yang berbeda nilai *chroma*-nya?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Gamut Mapping Strategy (P3 to sRGB):**  
   Saat sebuah Design System mendukung *wide-gamut displays* (Display P3) menggunakan CSS Color Module Level 4, bagaimana strategi *gamut mapping* (misalnya: *relative colorimetric clipping* vs. *Oklch Chroma reduction at constant Hue and Lightness*) memengaruhi kepatuhan aksesibilitas kontras saat aset dirender pada layar sRGB standar?

2. **APCA ($L^c$) Asymmetry & Polarity Mechanics:**  
   Dalam algoritma APCA (Advanced Perceptual Contrast Algorithm), nilai *Lightness Contrast* ($L^c$) bersifat bertanda (*signed*, positif/negatif). Jelaskan secara teknis mengapa kontras gelap-di-atas-terang (*positive polarity*) diproses menggunakan eksponen transfer function yang berbeda dibanding terang-di-atas-gelap (*negative polarity*), dan bagaimana hal ini mencegah *over-estimation* kontras pada teks putih di atas tombol hitam.

3. **Subpixel Antialiasing & Text Contrast Degradation:**  
   Pada level rasterisasi browser (Blink/Gecko), bagaimana *font smoothing* (misalnya `subpixel-antialiased` vs `antialiased`) menurunkan *effective contrast ratio* secara mikroskopis pada layar berdensitas rendah (*low-DPI 1x*), dan mengapa pengujian kontras statis berbasis DOM sering kali menghasilkan *false-positive pass* pada teks berukuran tipis (*light font weights*)?

4. **Algoritma Auto-Tonal Generation & Chroma Clipping:**  
   Ketika mengenerasi 10 tingkat *shade* warna turunan secara otomatis dari satu *seed color* menggunakan interpolasi Oklch, nilai *Chroma* ($C$) maksimum yang dapat dicapai tanpa keluar dari batas sRGB (*out-of-gamut*) bervariasi drastis berdasarkan *Hue* ($H$) dan *Lightness* ($L$). Bagaimana Anda mendesain algoritma kompensasi agar *tone* kuning (*high-luminance peak*) tidak mengalami *hue shifting* saat diturunkan luminansinya untuk kebutuhan teks berukuran kecil?

5. **Interseksi Windows High Contrast Mode (WHCM) / `@media (forced-colors: active)`:**  
   Ketika pengguna mengaktifkan mode kontras tinggi di tingkat OS, browser mengganti nilai warna latar belakang dan teks dengan palet sistem (*system color keywords* seperti `Canvas`, `CanvasText`, `HighlightText`). Mengapa penggunaan CSS Custom Properties yang di-injeksi secara dinamis melalui JavaScript dapat merusak state aksesibilitas ini, dan bagaimana cara memitigasinya menggunakan CSS *system colors* murni?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Krisis False-Positives CI/CD Pipeline pada Multi-Brand Engine
Perusahaan SaaS Anda mengelola 12 sub-brand yang menggunakan satu *core design engine*. Arsitek sebelumnya mengimplementasikan automated test berbasis Puppeteer yang menjalankan audit Lighthouse/axe-core (berbasis formula WCAG 2.1) pada setiap *pull request*. 
* **Masalah:** Tim UI/UX mengajukan keluhan massal karena sistem CI memblokir merge: badge teks warna kuning tua di atas latar belakang putih (`#7A6400` di atas `#FFFFFF`) lolos dengan skor 4.52:1 (Valid WCAG AA), namun secara visual sangat sulit dibaca pengguna manusia. Sebaliknya, teks putih tebal (*bold 18px*) di atas tombol oranye terang ditolak oleh CI karena rasio hanya 4.2:1, padahal keterbacaannya terbukti sangat tinggi saat user testing.
* **Pertanyaan Diagnostik:**
  1. Analisis akar penyebab matematis mengapa WCAG 2.1 meloloskan `#7A6400` pada putih tetapi menolak teks putih di atas oranye tersebut.
  2. Rancang arsitektur evaluasi kontras hibrida untuk CI/CD yang menggabungkan verifikasi compliance hukum (WCAG 2.1 AA) dengan verifikasi perseptual modern (APCA) tanpa memicu *flaky build*.

### Skenario B: Dynamic Theming Runtime Melanggar Regulasi Section 508 / EN 301 549
Aplikasi perbankan *enterprise* mengizinkan klien korporat menyuntikkan warna *primary brand* mereka secara kustom melalui portal admin (disimpan sebagai hex string pada database). Warna ini secara otomatis menurunkan token sekunder: *hover state*, *active state*, *focus ring indicator*, dan *subtle card backgrounds*.
* **Masalah:** Klien enterprise memilih warna korporat `#00FFFF` (Pure Cyan) dan `#FFE500` (Electric Yellow). Akibatnya, teks tombol aksi utama yang secara default di-hardcode berwarna putih (`#FFFFFF`) menjadi tidak terbaca. Saat dilakukan audit kepatuhan oleh regulator, sistem dinilai melanggar hukum federal dan terancam penalti operasional.
* **Pertanyaan Diagnostik:**
  1. Mengapa algoritma sederhana berbasis *threshold* luminansi linear (misal: `if (luminance > 0.5) return black; else return white;`) kerap menghasilkan *flashing artifacts* dan *edge-case failure* pada *hue* transisi seperti Cyan dan Magenta?
  2. Rancang formula deterministik di runtime (JavaScript/WebAssembly) yang menerima sembarang *hex seed color* dari user, lalu secara matematis mengkalkulasi dan mengunci:
     - Warna teks di atasnya (menjamin minimal $L^c \ge 75$ atau WCAG $\ge 4.5:1$).
     - State turunan (*hover/focus*) yang tetap mempertahankan rasio kontras 3:1 terhadap elemen sekitarnya (WCAG 2.1 Non-Text Contrast 1.4.11).

### Skenario C: Token Abstraction Trade-off untuk Theme Swapping (Dark, Light, & Dim)
Anda sedang memimpin refactoring token warna sistemik pada platform web berskala 50 juta MAU. Platform harus mendukung mode *Light*, *Dark*, dan *Dim/OLED*. Token saat ini menggunakan paradigma skeuomorfik lama berbasis shade (`color-gray-100`, `color-gray-900`) yang diubah-ubah nilainya via CSS class.
* **Masalah:** Arsitektur saat ini menyebabkan *layering collision*: ketika sebuah modal dibuka di atas halaman web pada Dark Mode, permukaan modal dan permukaan latar belakang menggunakan warna yang sama, menghilangkan persepsi kedalaman (*elevation/depth*) dan menurunkan kontras batas visual (*structural boundaries*) di bawah standar WCAG 1.4.11.
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda merestrukturisasi token dari abstraksi berbasis *shade/skala numerik* menjadi arsitektur token semantik berbasis *role & surface pairing* (misal: `surface-base`, `surface-raised`, `on-surface-primary`) untuk mencegah tabrakan elevasi?
  2. Dalam dark mode, kontras tidak dapat dicapai hanya dengan menambah saturasi/kegelapan bayangan (*drop shadows*). Jelaskan mekanisme penerapan *surface overlay tinting* berbasis persepsi Oklch untuk mengomunikasikan elevasi hierarkis sekaligus menjaga pemisahan kontras struktural minimal 3:1.

---

## 4. Chapter Challenge

### Tantangan Praktis: Accessible Algorithmic Palette Engine & Contrast Evaluator
Bangun sebuah *micro-engine* modular berbasis TypeScript murni (zero-dependency) yang mengonversi satu warna *seed* dasar menjadi sebuah *accessible semantic color family*, memvalidasi batas kontrasnya secara hibrida (WCAG 2.1 & APCA), dan mengekspor hasilnya menjadi CSS Custom Properties compliant.

#### Problem
Sistem token manual rentan terhadap *human error*. Desainer sering memilih warna state UI (*hover*, *pressed*, *focus*, *border*) yang tidak memenuhi standar aksesibilitas digital, terutama ketika sistem harus mendukung tema dinamis (*multi-tenant theming*).

#### Functional Requirements
1. **Engine Konversi Ruang Warna (Core Math):**
   - Implementasikan konverter: `sRGB (Hex) -> Linear sRGB -> Oklab -> Oklch` dan fungsi sebaliknya (`Oklch -> Oklab -> Linear sRGB -> Gamut Clamped sRGB Hex`).
   - Terapkan mekanisme *gamut mapping* deterministik: Jika nilai *Chroma* hasil interpolasi berada di luar gamut sRGB standar ($R, G, \text{atau } B \notin [0, 1]$), reduksi nilai $C$ secara bertahap dengan *binary search* hingga warna pas berada di dalam batas gamut sRGB tanpa mengubah nilai $H$ (*Hue*) dan $L$ (*Lightness*).
2. **Generasi Tonal Palette Sistemik:**
   - Diberikan sebuah warna input heksadesimal (misal: `#2563EB`), sistem harus mengenerasi skala tonal 11 level (indeks: `50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950`) dengan nilai $L$ (Lightness Oklch) yang terdistribusi secara matematis presisi dan independen terhadap *seed color*.
3. **Contrast Evaluator Hibrida:**
   - Implementasikan fungsi evaluasi WCAG 2.1: `calculateWCAG2(fgHex, bgHex): number` (mengembalikan nilai rasio $1.0 - 21.0$).
   - Implementasikan fungsi evaluasi APCA: `calculateAPCA(fgHex, bgHex): number` (mengembalikan estimasi nilai $L^c$).
   - Buat fungsi penentu warna teks otomatis: `resolveAccessibleTextColor(backgroundHex: string): { textColor: string, wcagRatio: number, apcaLc: number }` yang selalu mengembalikan warna teks kontras optimal (antara `#FFFFFF` atau token teks gelap `#0F172A`).
4. **Validasi State Interaktif:**
   - Sistem harus secara otomatis mengkalkulasi token state: `default`, `hover`, `active`, dan `focus-ring` untuk elemen komponen tombol. Token `focus-ring` wajib memenuhi rasio kontras non-text minimal 3:1 terhadap warna tombol maupun latar belakang kanvas luar.

#### Constraints
- **Murni TypeScript Native:** Dilarang menggunakan pustaka warna pihak ketiga (seperti `chroma-js`, `colord`, atau `culori`). Semua matriks perkalian dan kurva transfer fungsi matematika harus ditulis secara eksplisit dari kalkulasi dasar (*first principles*).
- **Gamut Safety:** Tidak boleh ada *overflow* atau komponen NaN pada kalkulasi heksadesimal akhir.
- **Strict Typing:** Seluruh tipe warna harus memiliki kontrak kuat (`type Oklch = { l: number; c: number; h: number }`, dsb.).

#### Expected Output
1. File modul TypeScript yang berisi:
   - Modul `ColorMath` (Parsing, Konversi, Gamut Mapping).
   - Modul `ContrastEngine` (WCAG 2.1 & APCA implementation).
   - Modul `ThemeGenerator` (Penerimaan warna input, penghasil skala tonal, dan penentu token semantik).
2. Ekspor struktur data JavaScript/JSON akhir yang memetakan token ke format CSS Variables:
```css
:root {
  --color-brand-50: #f0f6fe;
  /* ... hingga 950 ... */
  --color-brand-500: #2563eb;
  --button-primary-bg: var(--color-brand-500);
  --button-primary-fg: #ffffff; /* Kalkulasi deterministik */
  --button-primary-hover: #1d4ed8;
  --button-primary-focus-ring: #000000; /* Terbukti kontras 3:1 vs canvas & bg */
  /* Diagnostic metrics metadata */
  --_debug-wcag-ratio: 4.86;
  --_debug-apca-lc: -74.2;
}
```

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis sebelum melangkah ke implementasi level produksi.

### Saya harus memahami:
- [ ] Formula matematis *gamma companding* dan *linearization* sRGB beserta letak presisi eksponen ($2.4$ vs $2.2$).
- [ ] Definisi CIE *relative luminance* ($Y$) dan bobot fisiologis fotoreseptor mata manusia terhadap warna Hijau ($0.7152$), Merah ($0.2126$), dan Biru ($0.0722$).
- [ ] Limitasi arsitektural WCAG 2.1 dalam memproses polaritas *light-on-dark* (*dark mode*) dan bagaimana APCA memperbaikinya menggunakan fungsi kompresi daya (*power-law transfer functions*).
- [ ] Mengapa ruang warna Oklab/Oklch secara superior memisahkan dimensi *Lightness*, *Chroma*, dan *Hue* dibanding HSL/HSV untuk manipulasi warna berbasis kode.
- [ ] Persyaratan non-text contrast (WCAG 2.1 SC 1.4.11) sebesar 3:1 untuk batasan visual *input fields*, *focus indicators*, dan ikon grafis.
- [ ] Dampak *High Contrast Mode* OS terhadap arsitektur Design Tokens berbasis CSS Custom Properties.

### Saya tidak perlu menghafal:
- [ ] Matriks koefisien konversi eksplisit 3x3 untuk transformasi $RGB_{linear} \to XYZ$ atau $XYZ \to LMS$ (cukup pahami alur pipeline transformasinya dan simpan koefisien sebagai konstanta matematis).
- [ ] Nilai eksak koefisien numerik polinomial APCA (misal bobot eksponen $0.56, 0.62$, dsb.) di luar memori kerja harian; yang fundamental adalah memahami logika polaritas dan kurva kompresi spasialnya.
- [ ] Tabel lookup spesifikasi *font-size* vs *weight* vs APCA $L^c$ matrix secara mendetail; gunakan referensi tabel APCA lookup saat mendesain ambang batas sistem.

### Saya harus bisa melakukan:
- [ ] Menulis kalkulator kontras WCAG 2.1 bebas bug dari nol menggunakan TypeScript murni tanpa *third-party runtime dependencies*.
- [ ] Menghitung warna hasil *alpha compositing* (transparansi) terhadap latar belakang statis untuk mengevaluasi apakah token *glassmorphism* atau *overlay* memenuhi syarat aksesibilitas.
- [ ] Mengonfigurasi automated end-to-end audit (CI/CD) yang memvalidasi *design token output* terhadap standar WCAG 2.1 AA level secara deterministik.
- [ ] Merancang arsitektur CSS Token Semantik bertingkat tiga (*Global/Primitive -> Semantic/Alias -> Component*) yang dapat berganti tema (*Dark, Light, High-Contrast*) tanpa memutus relasi kontras minimum antar-elemen.
- [ ] Mengimplementasikan fallback CSS yang elegan untuk Windows High Contrast Mode menggunakan `@media (forced-colors: active)` dan kata kunci warna sistem.