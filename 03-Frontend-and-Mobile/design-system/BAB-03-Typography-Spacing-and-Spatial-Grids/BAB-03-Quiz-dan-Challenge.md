# BAB 03: Quiz, Challenge, & Knowledge Check
**Typography, Spacing, and Spatial Grids**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Matematika Modular Scale vs Linear Scale pada Tipografi
Jelaskan perbedaan mendasar antara pendekatan *Modular Type Scale* (misal: *Major Second* 1.125, *Major Third* 1.250, *Golden Ratio* 1.618) dan *Linear Scale* (misal: penambahan berbasis interval statis $+2\text{px}$ atau $+4\text{px}$) dalam pembentukan token tipografi. Mengapa sistem modular lebih direkomendasikan untuk mempertahankan hierarki visual kognitif pada antarmuka yang kompleks, dan apa dampak negatif penggunaan rasio modular yang terlalu agresif ($>1.333$) pada perangkat berlayar sempit (*mobile viewport*)?

### Soal 1.2: Perilaku Pewarisan (Inheritance) Unitless `line-height`
Mengapa arsitektur token tipografi standar enterprise mewajibkan nilai `line-height` dinyatakan dalam bentuk *unitless* (misalnya `line-height: 1.5`) alih-alih unit mutlak (`px`) atau unit relatif (`rem`, `%`, `em`)? Uraikan secara mekanis bagaimana browser menghitung *computed value* dari `line-height` ketika diwariskan dari elemen *ancestor* ke elemen *child* dengan ukuran `font-size` yang berbeda untuk masing-masing unit tersebut.

### Soal 1.3: Soft Grid System vs Hard Grid System
Bandingkan arsitektur *8pt Soft Grid System* dengan *8pt Hard Grid System*. Bagaimana kedua model tersebut memperlakukan penataan batas luar komponen (*bounding box*), jarak antar elemen (*margin/gap*), dan penempatan elemen di dalam kontainer (*padding*)? Analisis beban kognitif developer (*developer cognitive load*) dan fleksibilitas integrasi lintas platform (Web, iOS UIKit/SwiftUI, Android Jetpack Compose) pada kedua pendekatan tersebut.

### Soal 1.4: Mekanisme Fluid Typography Menggunakan `clamp()` dan Implikasi Aksesibilitas
Sebuah token tipografi fluid didefinisikan menggunakan fungsi CSS:
```css
font-size: clamp(1rem, 0.75rem + 1.25vw, 2.5rem);
```
Bedah formula matematika di balik fungsi tersebut (korelasi antara batas bawah, *slope/rate of change*, batas atas, dan *viewport width*). Selanjutnya, jelaskan risiko pelanggaran WCAG 2.1 *Success Criterion 1.4.4 (Resize Text)* jika kalkulasi *slope* tidak menyertakan basis unit berbasis pengguna (`rem`/`em`) dan sepenuhnya bergantung pada unit *viewport* (`vw`/`vh`).

### Soal 1.5: Anatomi Font Metrics dan Ilusi Asimetri Padding
Secara kasat mata, sebuah elemen `<button>` yang diberi deklarasi `padding-top: 12px; padding-bottom: 12px;` dengan sebuah *label text* di dalamnya sering kali terlihat memiliki ruang kosong vertikal yang tidak simetris (teks tampak melorot ke bawah atau terangkat ke atas). Jelaskan fenomena ini ditinjau dari metrik fisik font: *Ascender*, *Descender*, *Cap-Height*, *Baseline*, dan *Line Gap (Leading)* yang tertanam dalam metadata berkas font (tabel OS/2 dan hhea).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Implementasi Cap-Height Trimming dan CSS `text-box-trim`
CSS Working Group memperkenalkan properti standar `text-box-trim` dan `text-box-edge` (sebelumnya dikenal sebagai *leading-trim*). Jelaskan masalah spesifik pada *layout rendering engine* yang diselesaikan oleh spesifikasi ini. Jika sistem desain Anda harus berjalan pada browser produksi hari ini yang belum mendukung spesifikasi ini secara penuh, bagaimana Anda membangun *fallback mechanism* menggunakan *negative margin* atau *pseudo-element* berbasis perhitungan dinamis `cap-height` rasio font untuk mengeliminasi *half-leading*?

### Soal 2.2: Mitigasi Cumulative Layout Shift (CLS) Melalui Font Metric Overrides
Ketika memuat web font kustom secara asinkron (*FOUT - Flash of Unstyled Text*), pergantian dari *fallback system font* ke *custom font* kerap memicu pergeseran tata letak (*layout shift*) drastis yang merusak skor *Core Web Vitals* (CLS). Uraikan bagaimana Anda mengonfigurasi properti `@font-face` tingkat lanjut:
*   `ascent-override`
*   `descent-override`
*   `line-gap-override`
*   `size-adjust`

Gambarkan alur kalkulasi matematis untuk menyamakan metrik fallback font `Arial` agar identik dengan custom font `Inter`.

### Soal 2.3: Isolasi Spacing Primitives vs Contextual/Component Tokens
Perhatikan dua pendekatan dalam pembuatan token spasi:
*   **Pendekatan A (Scale-Only):** Menggunakan token skala primitif seperti `space.100` ($4\text{px}$), `space.200` ($8\text{px}$), `space.300` ($12\text{px}$), dst., langsung pada komponen.
*   **Pendekatan B (Semantic Layout Inset/Stack):** Mengabstraksi spasi ke dalam pola semantik seperti `space.inset.card.default`, `space.stack.form.gap`, atau primitif tata letak struktural (`<Stack>`, `<Inline>`, `<Box>`).

Lakukan *code-level & architectural trade-off analysis* antara kedua pendekatan ini. Mengapa Pendekatan A sering berujung pada inkonsistensi visual jangka panjang (*design token decay*), dan bagaimana Pendekatan B memitigasinya tanpa memicu *token explosion*?

### Soal 2.4: Mengintegrasikan CSS Subgrid ke dalam Spacing Engine Sistem Desain
Ketika membuat grid kartu multi-kolom yang masing-masing memiliki *header*, *body*, dan *footer* dengan panjang konten dinamis, implementasi `display: flex` atau `display: grid` standar pada masing-masing kartu sering kali gagal menyelaraskan garis *baseline* dan pemisah tombol antarkartu. Jelaskan mekanisme kerja `grid-template-rows: subgrid` dalam menyelesaikan masalah ini. Bagaimana Anda merancang komponen sistem desain `<Grid>` dan `<Grid.Item>` agar mendukung fallback aman (*graceful degradation*) pada klien peramban lama?

### Soal 2.5: Script Shifting dan Kompatibilitas Font Non-Latin (i18n)
Sistem tipografi enterprise yang dirancang sempurna untuk alfabet Latin (Inggris) sering kali hancur (*text clipping*, *line overlaps*, *distorted vertical alignment*) ketika diaplikasikan pada lokalisasi bahasa non-Latin seperti Arabic (RTL, aksen vertikal bertingkat), Devanagari (memiliki *hanging baseline*), atau Thai (karakter memiliki tumpukan *tone marks*). Bagaimana Anda mengarsitekturi *Typography Token Engine* agar dapat mendeteksi atau beralih ke skema metrik spasi dan `line-height` dinamis berbasis `lang` atribut tanpa merusak struktur visual komponen?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Regresi Tata Letak Skala Besar pada Arsitektur Micro-Frontend
Sebuah platform perbankan digital berbasis micro-frontend (mengintegrasikan 12 aplikasi frontend independen di bawah satu shell container) mengalami lonjakan drastis pada metrik *Cumulative Layout Shift (CLS)* hingga mencapai angka $0.45$ (kategori *Poor*). Setelah audit investigasi:
* Masing-masing tim micro-frontend mengimpor font `Inter` melalui CDN pihak ketiga dengan strategi *font-display* yang berbeda-beda (`swap`, `optional`, `block`).
* Terjadi *race condition* rendering: beberapa micro-frontend menggunakan font lokal browser sementara yang lain menunggu respons jaringan, menghasilkan lompatan tinggi komponen sebesar $4\text{px}$ hingga $12\text{px}$ pada ribuan node DOM secara berulang setiap kali route berganti.
* Spasi pada tabel data finansial menggunakan kombinasi unit absolut (`px`) dan `rem` yang tidak sinkron karena shell container mendefinisikan `:root { font-size: 62.5%; }` sedangkan dua micro-frontend mengasumsikan default browser standard (`16px`).

**Pertanyaan Diagnostik:**
1. Rancang arsitektur terpusat (*zero-CLS font delivery pipeline*) untuk shell dan seluruh micro-frontend.
2. Bagaimana Anda menyelesaikan kontradiksi `:root font-size` manipulation tanpa harus menulis ulang ribuan baris kode pada micro-frontend legacy yang menggunakan asumsi berbeda?
3. Buat rancangan *enforcement policy* berbasis CSS stylelint atau runtime contract agar fragmentasi metrik tipografi ini tidak berulang di masa depan.

### Skenario B: Fragmentasi Render Lintas Platform (Web, iOS UIKit, Android Compose)
Sebuah design token engine mengekspor token tombol berikut:
```json
{
  "button": {
    "padding-vertical": "12px",
    "padding-horizontal": "24px",
    "font-size": "16px",
    "line-height": "24px",
    "font-family": "Roboto"
  }
}
```
Ketika token ini diimplementasikan:
* **Web (Chrome):** Tombol ter-render dengan tinggi total $48\text{px}$ sempurna secara matematis ($24\text{px}$ text line box + $12\text{px}$ top + $12\text{px}$ bottom padding).
* **iOS (UIKit via UIButton/UILabel):** Teks tampak melompat $1.5\text{px}$ lebih dekat ke garis tepi atas, meninggalkan ruang bawah yang terlalu lapang.
* **Android (Jetpack Compose Text):** Tombol ter-render dengan tinggi total $51\text{px}$ karena perilaku internal `includeFontPadding` pada platform Android yang menambahkan ruang ekstra di atas *ascender* dan di bawah *descender*.

**Pertanyaan Diagnostik:**
1. Bedah akar penyebab struktural (*engine-level rendering*) dari perbedaan kalkulasi geometris antara Web Box Model, Apple CoreText, dan Android Skia/Paint Metrics.
2. Solusi arsitektural apa yang harus diterapkan pada *token transformation pipeline* (misal: Style Dictionary) atau pada level *primitive UI component wrapper* di masing-masing native platform untuk memaksa hasil render identik hingga tingkat sub-pixel?

### Skenario C: Trade-off Arsitektur: Dynamic Fluid System vs Discrete Breakpoint Tokens
Sebuah platform SaaS enterprise multi-tenant berskala global sedang mempertimbangkan perombakan sistem responsif pada sistem desainnya. 
* Tim Arsitektur A mengusulkan **Dynamic Fluid Engine**: Menggunakan kalkulasi `clamp()`, `min()`, `max()`, dan Container Query Units (`cqi`, `cqw`) untuk ukuran tipografi dan spasi grid. Komponen beradaptasi secara mulus (*continuously fluid*) tanpa perlu media queries.
* Tim Arsitektur B mengusulkan **Discrete Breakpoint Matrix**: Menggunakan token statis berbasis *fixed breakpoints* konvensional ($4\text{pt}/8\text{pt}$ interval kaku di `sm`, `md`, `lg`, `xl`).

**Pertanyaan Diagnostik:**
1. Analisis perbandingan kedua arsitektur tersebut berdasarkan kriteria:
   * Performa kalkulasi *style recomputation* dan GPU rasterization pada browser kelas bawah.
   * Tingkat kesulitan pengujian regresi visual otomatis (*visual regression testing* dengan Cypress/Playwright).
   * Kompleksitas operasional desainer UI saat menyelaraskan layout di tools desain (Figma) dengan hasil aktual di kode produksi.
2. Berikan rekomendasi arsitektur hibrida (jika memungkinkan) yang memaksimalkan keuntungan dari fluid layouts namun tetap mempertahankan determinisme struktural sistem discrete design tokens.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Typography & Spatial Grid Engine

#### Problem Statement
Sebagian besar sistem desain gagal menjaga integritas ritme vertikal (*vertical rhythm*) karena mengabaikan *font metric half-leading* dan ketidaksesuaian spasi kontainer akibat *sub-pixel rounding*. Anda ditugaskan untuk merancang dan mengimplementasikan **Core Layout & Typography Engine** mandiri (zero-dependency) menggunakan modern CSS/TypeScript yang menjamin *pixel-perfect baseline alignment*, bebas CLS, dan responsif terhadap kontainer.

#### Technical Requirements
1. **Typography Metric Alignment (Cap-Height Baseline Engine):**
   * Buat CSS class / styled primitive generator yang mengeliminasi ruang kosong bawaan font (*half-leading*) pada font kustom target (pilih salah satu: *Inter*, *Roboto*, atau *Geist*).
   * Teks harus bisa diposisikan pada *baseline grid* $4\text{px}$ secara deterministik.
   * Sediakan implementasi modern menggunakan `text-box-trim` / `text-box-edge`, dilengkapi dengan fallback otomatis berbasis *pseudo-element* / negative-offset untuk browser yang belum mendukung.
2. **Deterministic Fallback Font Matching:**
   * Tulis deklarasi `@font-face` untuk font fallback sistem (`Arial` atau `Times New Roman`) yang menggunakan `ascent-override`, `descent-override`, `line-gap-override`, dan `size-adjust` yang dihitung secara presisi untuk meminimalkan perbedaan metrik fisik dengan font kustom target hingga selisih $<1\%$.
3. **Fluid Layout & Spacing Primitives:**
   * Bangun token set spasi berbasis *modular 8pt spatial grid* yang mendukung responsivitas *fluid* pada rentang kontainer tertentu menggunakan formula CSS `clamp()`.
   * Implementasikan komponen tata letak dasar berbasis modern web:
     * `<Stack>`: Mengatur jarak vertikal antar-elemen anak menggunakan `row-gap` murni (tanpa margin collapse bugs).
     * `<Inline>`: Mengatur susunan horizontal dengan penanganan wrapping otomatis.
     * `<Grid>`: Menggunakan CSS Grid dengan dukungan `subgrid` untuk penyelarasan anak tingkat dua (*nested children*).
4. **Token Contract Structure:**
   * Token harus diekspor dalam format JSON standar W3C Community Group Design Tokens (*DTCG Specification*).

#### Constraints & Edge Cases
* **Zero CSS Framework:** Tidak diperbolehkan menggunakan Tailwind, Bootstrap, atau UI library pihak ketiga. Seluruh logika tata letak dan matematika CSS harus ditulis manual secara modular.
* **WCAG 2.1 AA Compliance:** Font scaling harus dapat dizoom hingga $200\%$ melalui browser zoom settings tanpa terjadi teks bertumpuk (*text overlap*) atau terpotong (*clipping*).
* **Sub-pixel Preservation:** Nilai perhitungan spasi fluid tidak boleh menghasilkan nilai ganjil yang memicu jitter visual pada layar dengan Device Pixel Ratio (DPR) $1.25$ atau $1.5$.

#### Expected Output
* File token tipografi dan spasi berstandar DTCG (`tokens.json`).
* File konfigurasi CSS / SCSS / CSS-in-JS utility yang berisi generator *leading-trim compensation* dan *font-metric overrides*.
* Sebuah demonstrasi komponen kartu interaktif (*responsive card preview*) yang membuktikan:
  1. Header, body text, dan footer terpasang sempurna pada garis *baseline grid overlay* visual $4\text{px}/8\text{px}$.
  2. Bebas dari layout shift saat font dimuat secara lambat (*throttled 3G network simulation*).
  3. Kolom berdampingan dengan panjang teks berbeda tetap memiliki posisi tombol aksi yang sejajar secara horizontal menggunakan *subgrid*.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Formula kalkulasi matematika *Modular Scale* dan bagaimana *ratio* mempengaruhi rasio kontras visual informasi.
- [ ] Perilaku engine browser saat mewariskan unitless `line-height` vs unit `rem`/`px` pada pohon DOM bersarang (*nested DOM*).
- [ ] Anatomi internal font metrics (*ascender*, *descender*, *cap-height*, *x-height*, *UPM - Units Per Em*) dan korelasinya terhadap CSS box model.
- [ ] Perbedaan filosofis dan teknis antara arsitektur *Hard Grid* ($8\text{pt}$ strictly enforced) vs *Soft Grid* ($8\text{pt}$ components, $4\text{pt}$ internal/text).
- [ ] Cara kerja spesifikasi `text-box-trim` / `text-box-edge` W3C dan metode kompensasi metrik font manual via CSS.
- [ ] Mekanisme optimasi performa font web: FOIT, FOUT, `@font-face` overrides (`ascent-override`, `descent-override`, `size-adjust`) untuk eliminasi CLS.
- [ ] Aturan WCAG 2.1 AA terkait aksesibilitas teks (*Success Criterion 1.4.4 Resize Text* dan *1.4.12 Text Spacing*).
- [ ] Keterbatasan dan keunggulan CSS `subgrid` dalam menjaga keharmonisan ritme spasial komponen kompleks multi-tier.

### Saya tidak perlu menghafal:
- [ ] Nilai eksak biner dari tabel metrik OS/2 dan hhea pada berkas font biner (cukup gunakan tools ekstraktor seperti *FontDrop!* atau *Capsize*).
- [ ] Angka desimal presisi tinggi dari rasio modular klasik (misal: rasio *Octave* = 2, *Golden Ratio* = 1.6180339...; cukup ketahui peruntukan skalanya).
- [ ] Sintaks spesifik vendor prefix lawas untuk properti flexbox atau grid.
- [ ] Konstanta padding internal spesifik platform native legacy yang sudah usang di luar platform target aktif.

### Saya harus bisa melakukan:
- [ ] Menulis kalkulasi CSS `clamp()` yang aman dan valid secara aksesibilitas untuk ukuran font dan spasi fluida.
- [ ] Menghitung dan mengonfigurasi metrik fallback font secara tepat menggunakan `@font-face` metric overrides agar layout shift bernilai $\approx 0$.
- [ ] Membangun abstraction layer komponen layout struktural (`<Box>`, `<Stack>`, `<Inline>`, `<Grid>`) yang menegakkan penggunaan token spasi tanpa celah kebocoran nilai hardcoded.
- [ ] Melakukan debugging visual rhythm secara visual menggunakan canvas/SVG baseline grid overlay di browser DevTools.
- [ ] Menyusun arsitektur token tipografi dan spasi multi-tier (Global Primitive -> Semantic Contextual -> Component Level) sesuai standar DTCG.
- [ ] Mendiagnosis dan memperbaiki masalah *cross-platform vertical alignment* antara Web (CSS), iOS (SwiftUI/UIKit), dan Android (Jetpack Compose).