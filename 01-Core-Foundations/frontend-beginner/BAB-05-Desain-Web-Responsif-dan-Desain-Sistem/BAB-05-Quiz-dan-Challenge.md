# BAB 05: Quiz, Challenge, & Knowledge Check
**Desain Web Responsif, Arsitektur CSS & Desain Sistem**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Dual Viewport & Rendering Pipeline
Jelaskan secara mendalam perbedaan mekanis antara *Visual Viewport* dan *Layout Viewport* pada peramban seluler. Mengapa deklarasi meta tag `<meta name="viewport" content="width=device-width, initial-scale=1.0">` menjadi prasyarat mutlak dalam modern responsive rendering pipeline, dan apa anomali layout serta kalkulasi CSS pixels yang terjadi pada engine peramban jika tag ini diabaikan?

### Soal 1.2: Fluid Typography & Mathematical Clamping
Bandingkan pendekatan penskalaan tipografi berbasis *fixed media query breakpoints* dengan *fluid dynamic scaling* menggunakan fungsi matematis `clamp(min, val, max)`. Jelaskan bagaimana *formula linear interpolation* (lerp) diintegrasikan ke dalam nilai `val` (menggunakan kombinasi `rem` dan `vw`) agar menghasilkan penskalaan yang terprediksi tanpa merusak mekanisme *browser zoom accessiblity* (WCAG SC 1.4.4).

### Soal 1.3: Paradigma Container Queries vs. Media Queries
Analisis pergeseran paradigma dari *Macro-Responsive* (Media Queries `@media`) menuju *Micro-Responsive* (Container Queries `@container`). Mengapa ketergantungan murni terhadap *viewport dimensions* dianggap sebagai *architectural anti-pattern* dalam pengembangan sistem komponen modular? Jelaskan cara kerja `container-type: inline-size` dan implikasinya terhadap *layout containment*.

### Soal 1.4: Cascade Layers (`@layer`) & Resolusi Spesifisitas
Bagaimana spesifikasi CSS Cascading and Inheritance Level 5 melalui fitur `@layer` merevolusi algoritma kalkulasi *CSS Cascade*? Jika terdapat deklarasi selector dengan spesifisitas tinggi (`#id .class[attr]`) di dalam layer prioritas rendah dan selector dengan spesifisitas rendah (`p`) di dalam layer prioritas tinggi, jelaskan selector mana yang menang serta urutan prioritas evaluasi engine peramban dari `origin`, `layer`, hingga `specificity`.

### Soal 1.5: Design Tokens: Runtime Custom Properties vs. Build-Time Preprocessors
Bandingkan arsitektur *Design Tokens* yang diimplementasikan menggunakan CSS Custom Properties (`var(--token)`) versus variabel preprocessor (seperti Sass `$token`). Tinjau perbandingan ini dari aspek:
1. Resolusi kompilasi (*build-time static evaluation* vs *runtime DOM-tree inheritance*).
2. Kemampuan mutasi dinamis berbasis konteks DOM (*scoped theme overrides*).
3. Jejak memori (*memory footprint*) dan performa *style recalculation* pada peramban.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik Cumulative Layout Shift (CLS) pada Responsive Media
Perhatikan fragmen kode responsif berikut:
```html
<!-- Markup -->
<div class="media-container">
  <img src="hero-small.webp" srcset="hero-small.webp 480w, hero-large.webp 1200w" alt="Hero">
</div>

<!-- CSS -->
.media-container { width: 100%; max-width: 800px; }
.media-container img { width: 100%; height: auto; }
```
Analisis mengapa kode di atas memicu lonjakan skor *Cumulative Layout Shift* (CLS) saat jaringan lambat (Slow 3G). Bagaimana implementasi modern atribut intrinsik `width` dan `height` bersamaan dengan properti CSS `aspect-ratio` menyelesaikan masalah kalkulasi *box-sizing aspect ratio box* sebelum aset biner terunduh?

### Soal 2.2: Subgrid Alignment pada Dynamic Multi-Card Layouts
Ketika menyusun komponen kartu responsif dalam CSS Grid, konten teks yang bervariasi panjangnya sering kali membuat elemen footer kartu (seperti tombol aksi) tidak sejajar secara horizontal antar kolom. 
1. Mengapa teknik fleksibel tradisional (`display: flex; flex-direction: column; justify-content: space-between;`) gagal memberikan konsistensi visual pada baris internal lintas kartu yang independen?
2. Bagaimana `grid-template-rows: subgrid` memecahkan masalah ini pada level internal engine peramban, dan apa batasan propagasi konteks grid-nya?

### Soal 2.3: Anti-FOUC Architecture pada Dynamic Theming
Dalam sistem *design tokens* berbasis CSS Custom Properties, peralihan tema (Dark/Light mode) yang dipicu oleh JavaScript di level `document.documentElement` sering menyebabkan *Flash of Unstyled Content* (FOUC) atau *Flash of Incorrect Theme*. 
1. Rancang arsitektur eksekusi kritis (*critical rendering path*) untuk sinkronisasi preferensi lokal pengguna (`localStorage`) dan OS (`prefers-color-scheme`).
2. Tentukan posisi eksekusi script, payload CSS kritis, dan strategi pencegahan layout thrashing tanpa memblokir parsing HTML secara berlebihan.

### Soal 2.4: Trade-Off Arsitektur CSS: CSS Modules vs. Utility-First (Tailwind) vs. CSS-in-JS
Lakukan evaluasi arsitektural komparatif mendalam antara **CSS Modules**, **Utility-First CSS (Tailwind)**, dan **Zero-Runtime CSS-in-JS (seperti Vanilla Extract)** untuk aplikasi skala enterprise berbasis Micro-Frontend. Fokuskan analisis Anda pada:
1. Isolasi *scope* dan eliminasi *dead-code* (Tree-shaking).
2. Skalabilitas ukuran bundel CSS terhadap pertumbuhan jumlah komponen (*bundle growth linearity*).
3. Kompleksitas orkestrasi *design tokens contract* antar tim independen.

### Soal 2.5: Logical Properties dan Bidirectional Layout Engine (LTR/RTL)
Jelaskan secara mekanis bagaimana adopsi *CSS Logical Properties* (misal: `inline-size`, `margin-block-start`, `padding-inline-end`) menggantikan *Physical Properties* (misal: `width`, `margin-top`, `padding-right`) dalam merancang sistem desain yang agnostik terhadap arah penulisan (*writing modes*). Mengapa penggunaan *physical absolute positioning offsets* (`left`, `right`) dianggap sebagai *technical debt* dalam globalisasi aplikasi enterprise?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Produksi - Reflow Storm & CLS Ambruk pada E-Commerce Flash Sale
* **Konteks:** Pada saat event Flash Sale dengan trafik jutaan RPS, metrik Core Web Vitals pada halaman katalog produk anjlok secara drastis (CLS melonjak hingga 0.45, dan INP mencapai 600ms). Tim infrastruktur mendeteksi adanya *reflow storm* berulang pada browser klien.
* **Hasil Audit:** 
  1. Halaman menggunakan komponen kartu produk responsif berbasis Flexbox dengan *media queries breakpoint* setiap 150px.
  2. Gambar produk menggunakan `loading="lazy"` tanpa reservasi dimensi eksplisit.
  3. Badge diskon diinjeksikan secara asinkronus melalui API pihak ketiga via JavaScript manipulasi class `.has-discount` yang mengubah margin seluruh kartu tetangga.
* **Pertanyaan Diagnostik:**
  1. Identifikasi akar masalah utama pemicu beruntunnya *Layout Reflow* dan *Paint Invalidations* pada kasus tersebut!
  2. Rancang strategi perbaikan refactoring CSS arsitektural lengkap dengan kode deklaratif (melibatkan `aspect-ratio`, CSS Grid, dan strategi penanganan injeksi DOM dinamis) untuk menekan CLS kembali ke `< 0.05` tanpa membebani thread utama CPU klien!

### Skenario B: Konflik Cascading & Specificity Bleed pada Integrasi Micro-Frontend
* **Konteks:** Perusahaan fintech mengintegrasikan modul baru bernama "Checkout Engine" (dikembangkan menggunakan Tailwind CSS dengan CSS Reset modern) ke dalam aplikasi portal utama yang masih mengandalkan arsitektur global stylesheet warisan (*legacy CSS 10 tahun* berbasis bootstrap 3 yang termodifikasi secara liar menggunakan selektor `#main-app .container div`).
* **Insiden:** Terjadi *visual regression catastrophic*. Style dari aplikasi portal merusak elemen form pada modul Checkout, dan sebaliknya *Preflight reset* dari modul Checkout menghapus margin/padding default ribuan elemen di aplikasi utama.
* **Pertanyaan Diagnostik:**
  1. Analisis mengapa teknik isolasi konvensional seperti penambahan prefix selector (`.checkout-prefix`) sering kali gagal memitigasi kebocoran gaya (*style bleed*) dua arah pada sistem berskala ribuan aturan CSS!
  2. Rancang solusi arsitektural pertahanan berlapis menggunakan kombinasi modern native CSS primitives (seperti `@layer`, `@scope`, atau Shadow DOM) untuk mengisolasi kedua aplikasi tersebut secara hermetis tanpa harus menulis ulang total stylesheet warisan!

### Skenario C: Multi-Tenant Whitelabel Design System Scaling Trade-Off
* **Konteks:** Sebuah platform SaaS B2B melayani 500+ klien *whitelabel enterprise*. Setiap klien membutuhkan kustomisasi identitas visual: tipografi unik, radius sudut dinamis, elevation/shadows, hingga 3 variasi tema (Dark, Light, High-Contrast) yang dapat berganti secara instan saat *runtime* melalui Dashboard Admin.
* **Dilema Arsitektur:** Tim inti terbelah antara dua opsi arsitektur:
  * *Opsi 1:* Mengompilasi 500 file CSS statis terpisah (satu untuk setiap tenant) menggunakan Sass/PostCSS saat proses CI/CD.
  * *Opsi 2:* Menggunakan satu stylesheet universal tunggal yang didorong oleh *Semantic Design Tokens* berbasis CSS Custom Properties, dengan token yang disuntikkan secara dinamis melalui inline style atribut pada tag `<html>` atau file JSON konfigurasi runtime.
* **Pertanyaan Diagnostik:**
  1. Bedah trade-off performa, kompleksitas CI/CD pipeline, caching strategy (CDN edge latency), dan konsumsi memori peramban dari kedua opsi tersebut!
  2. Sebagai Principal Architect, berikan rekomendasi arsitektur final Anda (apakah memilih opsi 1, 2, atau arsitektur hibrida) lengkap dengan spesifikasi hierarki layer token (*Global Tokens*, *Semantic Tokens*, *Component Tokens*)!

---

## 4. Chapter Challenge

### Tantangan Praktis: Membangun "Enterprise Fluid & Theme-Aware Design Token Engine with Modern Responsive Card System"

#### 1. Deskripsi Masalah
Banyak sistem komponen modern gagal mempertahankan portabilitas saat diletakkan pada berbagai konteks layout (misal: ditaruh di dalam sidebar yang sempit vs ditaruh di dalam main grid yang luas). Selain itu, kerap terjadi regresi visual saat tema warna berubah atau saat ukuran layar berada pada titik ekstrim. Anda ditugaskan membangun sistem komponen kartu artikel (*Editorial Responsive Card*) yang mengadopsi prinsip desain sistem modern kelas enterprise, sepenuhnya fluid, dan bebas dependensi framework JavaScript.

#### 2. Requirements & Deliverables
Anda wajib menyusun sebuah implementasi statis (HTML dan CSS murni) yang mencakup:
1. **Design Token Architecture Layering:**
   * Deklarasikan token menggunakan CSS Custom Properties di dalam layer khusus `@layer tokens, reset, base, components, utilities;`.
   * Skema token harus mencakup 3 level:
     * *Global Primitive Tokens* (skala warna mentah, rasio font dasar).
     * *Semantic Tokens* (warna background permukaan, warna teks interaktif, status border).
     * *Component Tokens* (properti khusus kartu yang mereferensikan semantic tokens).
2. **Fluid Typography & Spacing System:**
   * Tidak diperbolehkan menggunakan media queries fixed pixels (`px`) untuk mendefinisikan ukuran font dan padding kontainer.
   * Gunakan fungsi matematis `clamp()` yang terintegrasi secara proporsional.
3. **Container-Driven Component Layout:**
   * Buat pembungkus kartu dengan deklarasi container context (`container-type: inline-size;`).
   * Rancang kartu agar secara otomatis bertransformasi:
     * Menjadi layout vertikal tunggal (*stacked layout*) ketika container width `< 400px`.
     * Menjadi layout horizontal (*side-by-side media & body*) ketika container width `>= 400px` dan `< 700px`.
     * Menjadi layout multi-kolom kompleks dengan *featured typography* ketika container width `>= 700px`.
     * **Aturan:** Transformasi ini tidak boleh menggunakan `@media (max-width / min-width)`, wajib `@container`!
4. **Zero-CLS Responsive Media Implementation:**
   * Komponen media gambar harus memanfaatkan rasio aspek dinamis (`aspect-ratio: 16 / 9` untuk stacked, `1 / 1` untuk side-by-side) serta atribut intrinsik untuk memastikan skor CLS adalah mutlak **0**.
5. **Bidirectional & Accessible Color Scheme Support:**
   * Mendukung skema warna *Light* dan *Dark* otomatis via media query `@media (prefers-color-scheme: dark)` dengan token swapping murni.
   * Gunakan CSS Logical Properties di seluruh aspek perataan layout untuk memastikan kesiapan RTL (*Right-to-Left*).

#### 3. Constraints (Batasan Mutlak)
* **Dilarang** menggunakan JavaScript sama sekali untuk kalkulasi tata letak, pergantian ukuran, atau modifikasi token.
* **Dilarang** menggunakan library CSS eksternal (Bootstrap, Tailwind, dsb.) atau CSS Preprocessor (Sass, Less). Kode harus berupa CSS Native modern valid.
* **Dilarang** menggunakan selector `!important` untuk memecahkan konflik spesifisitas.
* Browser target adalah *Modern Evergreen Browsers* (Chrome, Firefox, Safari, Edge versi 2 tahun terakhir).

#### 4. Expected Output
Dokumen kode mandiri berformat HTML yang menyertakan style internal (atau file CSS terpisah) yang siap diuji pada viewport desktop, tablet, maupun seluler, serta demonstrasi kartu yang ditempatkan secara berdampingan di dalam kolom sempit (sidebar 300px) dan kolom lebar (main area 900px) untuk membuktikan adaptabilitas container query secara simultan tanpa distorsi visual.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme parsing browser terhadap *Layout Viewport* vs *Visual Viewport* serta implikasi scale factor.
- [ ] Algoritma resolusi CSS Cascade Level 5: Urutan evaluasi dari *Origin*, *Context*, *Layers*, *Specificity*, hingga *Order of Appearance*.
- [ ] Prinsip matematis di balik fluid calculations: Hubungan fungsional antara `clamp()`, `min()`, `max()`, `calc()`, dan satuan berbasis viewport (`vw`, `cqw`).
- [ ] Perbedaan fundamental antara macro-breakpoints (`@media`) dan micro-breakpoints (`@container`) dalam konteks isolasi rendering komponen.
- [ ] Konsep arsitektur hierarki design tokens: *Primitive/Global Tokens*, *Semantic/System Tokens*, dan *Component Tokens*.
- [ ] Mekanisme kalkulasi *Aspect Ratio Box* oleh browser engine untuk pencegahan Layout Invalidation dan degradasi performa CLS.
- [ ] Konsep *Physical Properties* vs *Logical Properties* dalam rendering engine berbasis *Writing Modes* (LTR, RTL, Vertical).

### Saya tidak perlu menghafal:
- [ ] Nilai eksak kalkulasi pixel desimal dari rumus interpolasi fluid `clamp()` (gunakan formula kalkulator / tooling compiler).
- [ ] Prefix historis vendor engine lawas (`-webkit-`, `-moz-`, `-ms-`) yang sudah tidak relevan pada evergreen browsers.
- [ ] Daftar lengkap ribuan kode hex warna standar (gunakan penamaan semantik berbasis HSL, OKLCH, atau RGB tokens).
- [ ] Seluruh nilai konversi tabel resolusi DPI media query usang (`device-pixel-ratio`).

### Saya harus bisa melakukan:
- [ ] Melakukan profiling dan debugging *Layout Shift* secara presisi menggunakan Chrome DevTools Performance & Rendering Panel.
- [ ] Mengonfigurasi arsitektur styling berskala enterprise menggunakan `@layer` untuk mengeliminasi ketergantungan pada selektor `!important`.
- [ ] Mengimplementasikan *Container Queries* dengan penanganan *containment context* yang tepat (`container-type` dan `container-name`).
- [ ] Merancang ekosistem *CSS Custom Properties* yang mendukung dynamic contextual overriding (misal: theming, nesting) tanpa *side-effects*.
- [ ] Menulis CSS berbasis *Logical Properties* secara konsisten untuk memastikan antarmuka adaptif terhadap lokalisasi multi-bahasa global (LTR & RTL).
- [ ] Mengaudit dan mengoptimalkan performa rendering CSS guna meminimalkan *Style Recalculation Time* dan mencegah *Layout Thrashing*.