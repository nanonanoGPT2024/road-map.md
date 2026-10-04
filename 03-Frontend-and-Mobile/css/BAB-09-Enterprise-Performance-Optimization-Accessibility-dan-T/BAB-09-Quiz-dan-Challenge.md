# BAB 09: Quiz, Challenge, & Knowledge Check
**Enterprise Performance Optimization, Accessibility, dan Tooling**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Critical Rendering Path (CRP) & CSSOM Blocking**
   Jelaskan secara mendalam mengapa file CSS eksternal secara *default* diklasifikasikan sebagai *render-blocking resource* oleh browser engine (Blink/Gecko/WebKit). Bagaimana browser mengoptimalkan jalur eksekusi jika atribut `media` disematkan pada tag `<link rel="stylesheet">` (misal: `media="print"` atau `media="(min-width: 1024px)"`), dan apa dampaknya terhadap pembentukan CSSOM serta proses *first paint*?

2. **Pipeline Rendering: Layout, Paint, dan Composite**
   Uraikan perbedaan siklus hidup rendering antara mutasi properti `left`/`top`, `margin`, `transform: translate()`, dan `opacity`. Mengapa modifikasi berbasis GPU layer via `transform` dan `opacity` mampu memotong fase *Layout (Reflow)* dan *Paint (Repaint)* langsung ke fase *Composite*? Jelaskan risiko alokasi memori VRAM jika optimasi ini diterapkan secara berlebihan (`over-promotion`).

3. **Korelasi Arsitektur CSS dengan Core Web Vitals (LCP, CLS, INP)**
   Identifikasi bagaimana penulisan dan strategi pemuatan CSS secara langsung dapat merusak skor:
   - **CLS (Cumulative Layout Shift):** Dampak dari font swapping tanpa metric overrides dan gambar tanpa `aspect-ratio`.
   - **LCP (Largest Contentful Paint):** Dampak dari critical CSS inlining yang berukuran masif vs pemuatan font via `@import`.
   - **INP (Interaction to Next Paint):** Dampak dari *recalculate style* yang kompleks pada deep DOM trees saat terjadi user interaction.

4. **Primitive Containment: `contain` dan `content-visibility`**
   Jelaskan cara kerja mekanik internal dari CSS `contain` (dengan nilai `layout`, `paint`, `size`, dan `strict`) dalam memutus dependensi pohon DOM (*sub-tree isolation*). Bagaimana properti modern `content-visibility: auto` memanfaatkan *containment* ini bersama *intersection observer internal browser* untuk mengabaikan rendering elemen di luar *viewport*, dan bagaimana peran `contain-intrinsic-size` dalam mencegah degradasi CLS?

5. **Prinsip Accessibility (A11y): Contrast Ratios & Motion Semantics**
   Sesuai pedoman WCAG 2.2 Level AA dan AAA, jelaskan formula rasio kontras minimum untuk teks normal dan teks berukuran besar (*large text*). Selanjutnya, jelaskan implementasi teknis penanganan *vestibular motion disorders* menggunakan *media feature* `@media (prefers-reduced-motion: reduce)`, serta berikan arsitektur tokenisasi CSS yang elegan untuk mematikan atau menyederhanakan animasi secara sistemik.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Forced Synchronous Layout (Layout Thrashing) Detection & Fix**
   Analisis potongan eksekusi JavaScript & CSS berikut:
   ```javascript
   elements.forEach(el => {
       const width = el.getBoundingClientRect().width; // Read
       el.style.width = (width + 10) + 'px';           // Write
   });
   ```
   Jelaskan mengapa kode di atas memicu *Layout Thrashing* pada browser engine. Bagaimana cara Anda mendiagnosis masalah ini melalui Chrome DevTools Performance Panel (khususnya *Recalculate Style* dan *Layout warnings*), dan bagaimana solusi refaktorisasi arsitektur CSS/JS menggunakan *FastDOM pattern* atau `requestAnimationFrame` batching?

2. **GPU Layer Promotion & Stacking Context Side-Effects**
   Penggunaan deklarasi `will-change: transform` atau `transform: translateZ(0)` memaksa browser membuat *GraphicsLayer* baru. Jelaskan:
   - Bagaimana penumpukan layer (*layer explosion*) dapat menyebabkan degradasi performa pada perangkat low-end (terkait VRAM bandwith dan bus transfer CPU ke GPU).
   - Efek samping pembentukan *Stacking Context* baru terhadap elemen turunan yang memiliki `position: fixed` atau `z-index`.

3. **Typography Performance: FOIT, FOUT, dan Font Metric Overrides**
   Bedakan mekanisme browser saat menangani `font-display: block`, `swap`, `fallback`, dan `optional`. Jika tim Anda diwajibkan menggunakan `font-display: swap` demi LCP, bagaimana Anda mengatasi lonjakan CLS saat font kustom dimuat? Uraikan penggunaan CSS Font Metric Overrides modern (`ascent-override`, `descent-override`, `line-gap-override`, dan `size-adjust`) untuk menciptakan *fallback font match* yang presisi terhadap sistem operasi native.

4. **AOM (Accessibility Object Model) vs CSS Visibility**
   Jelaskan secara presisi representasi struktur pohon aksesibilitas (*Accessibility Tree*) ketika berhadapan dengan teknik-teknik penyembunyian elemen berikut:
   - `display: none`
   - `visibility: hidden`
   - `opacity: 0`
   - Class screen-reader utility (seperti `.sr-only` yang memanfaatkan `clip-path: inset(50%)` atau `rect(0 0 0 0)`)
   - Pseudo-elements (`::before` / `::after`) dengan properti `content: "..."`
   Kapan sebuah pseudo-element dibacakan oleh pembaca layar (*screen reader*), dan bagaimana memastikan *generated content* tidak menghasilkan informasi redundan bagi pengguna disabilitas netra?

5. **Tooling & Post-Processing Architecture: AST Engine Comparison**
   Bandingkan arsitektur internal PostCSS (berbasis JavaScript AST engine) dengan compiler modern berbasis Rust seperti Lightning CSS. Mengapa transformasi CSS skala enterprise bermigrasi ke native tooling? Bagaimana compiler menangani resolusi *dependency graph*, *CSS nesting flattening*, otomatisasi vendor prefixing via *Browserslist*, dan potensi bahaya *Dead Code Elimination* (seperti PurgeCSS/UnCSS) terhadap konstruksi class dinamis pada frontend framework?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden INP Masif pada Mega-Menu E-Commerce Enterprise
Sebuah aplikasi e-commerce global mengalami penurunan drastis pada metrik INP (tercatat p75 berada pada angka **620ms**, status *Poor*) segera setelah merilis navigasi "Mega-Menu" baru dengan ribuan node kategori dan produk promosi. Navigasi ini menggunakan transisi hover/focus murni berbasis CSS:
```css
.nav-item:hover .mega-menu-panel,
.nav-item:focus-within .mega-menu-panel {
    display: flex;
    opacity: 1;
    transform: translateY(0);
}
```
Pohon DOM halaman utama mencapai total 4.200 nodes. Setiap kali pengguna menggerakkan kursor di atas navigasi, DevTools mendeteksi *Long Frame* (>120ms) yang didominasi oleh event `Recalculate Style` dan `Layout`.

* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi akar penyebab tingginya waktu *Style Recalculation* pada kasus di atas sehubungan dengan kompleksitas selektor dan kedalaman DOM tree.
  2. Rancang arsitektur refaktorisasi CSS menggunakan kombinasi `content-visibility`, properti transisi baru (`@starting-style` dan `transition-behavior: allow-discrete` jika browser mendukung, atau strategi *DOM offloading*), serta reduksi selector specificity untuk menekan metrik INP kembali ke batas aman (< 200ms).

### Skenario B: Race Condition dan Layout Shifting pada Sistem Infinite Feed
Sebuah platform media sosial menyajikan konten dalam bentuk *infinite scroll virtualized feed*. Setiap item feed berisi kombinasi teks, dynamic mentions, dan media kaya (gambar/video responsif). Di lingkungan produksi, pengguna perangkat mobile melaporkan perilaku "konten melompat liar" (CLS melonjak hingga **0.45**) ketika scrolling cepat dilakukan saat jaringan mengalami *packet loss* atau throttled 3G/4G. 

Setelah diinvestigasi, terjadi benturan siklus rendering: container media bergantung pada dynamic sizing JavaScript, font fallback lokal digantikan oleh custom web-font, dan gambar lazy-loaded tidak memiliki reservasi dimensi eksplisit di level CSS.

* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana mekanisme *browser layout pipeline* memproses siklus ukuran kontainer ketika gambar dimuat secara asinkron tanpa rasio intrinsik yang terkunci?
  2. Tuliskan implementasi arsitektur CSS defensif menggunakan `aspect-ratio`, CSS container queries, dan teknik *modern skeleton state* yang secara mutlak mengunci geometri layout sebelum aset eksternal (font & media) tiba di browser, tanpa ketergantungan pada kalkulasi JS runtime.

### Skenario C: Migrasi Arsitektur Monolith: Runtime CSS-in-JS ke Zero-Runtime Lightning CSS
Perusahaan Anda memiliki aplikasi web enterprise berskala besar (monorepo dengan >300 komponen) yang dibangun menggunakan dynamic runtime CSS-in-JS (Styled-Components). Hasil audit performa menunjukkan:
- Runtime overhead JS bundle bertambah 180KB (parsing + serialization).
- *Style injection* dinamis saat render memicu *blocking main-thread* berulang kali.
- Tidak ada kemampuan *streaming critical CSS* saat SSR (Server-Side Rendering).

Manajemen menyetujui migrasi penuh ke paradigma zero-runtime / build-time CSS menggunakan CSS Modules yang diproses oleh Lightning CSS, namun sistem tetap harus mendukung:
1. Multi-tenant white-label theming (mengubah ratusan palet warna, tipografi, dan border radius secara dinamis saat runtime berdasarkan context perusahaan penyewa).
2. Atomic design system tokens.
3. Strict bundle-budgeting (CSS total initial-load di bawah 50KB terkompresi).

* **Pertanyaan Diagnostik & Solusi:**
  1. Apa trade-off arsitektural dari penghapusan runtime CSS-in-JS dan bagaimana menangani multi-tenant dynamic theming murni menggunakan CSS Custom Properties (`var()`) di tingkat `:root` atau data-attribute tanpa memicu *flash of unstyled theme*?
  2. Rancang strategi pipeline *code-splitting*, *critical CSS extraction*, dan struktur token design system menggunakan CSS modern yang menjamin ukuran file bundle tetap berada di bawah ambang batas (budget).

---

## 4. Chapter Challenge

### Tantangan Praktis: Audit, Refactor, dan Hardening Performa serta Aksesibilitas Komponen Data Table Enterprise

#### Konteks & Problem Statement
Anda menerima warisan basis kode (*legacy code*) berupa komponen **Enterprise Data Table** yang memuat 200 baris data interaktif dengan fitur: sticky header, expandable row, multi-select action, dan sparkline chart visualizer. 

Komponen ini saat ini mengalami masalah kritis:
1. Skor Lighthouse Performance: **48/100**, Accessibility: **54/100**.
2. Terjadi lonjakan CLS sebesar **0.28** saat data dimuat dan font kustom selesai diunduh.
3. INP tercatat sebesar **410ms** ketika pengguna melakukan filter atau memilih semua baris data.
4. Pengguna navigasi keyboard (*keyboard-only*) terjebak di dalam tabel (*keyboard trap*), outline fokus dinonaktifkan secara global (`outline: none`), dan kontras teks status tag tidak memenuhi standar WCAG.
5. Selektor CSS sangat tidak optimal (bertingkat hingga 6-7 kedalaman: `.table-wrapper div.row-item > div.cell-data span.badge ...`).

#### Requirements
1. **Performance Hardening:**
   - Reduksi selektor CSS menjadi arsitektur flat dengan spesifisitas rendah (BEM atau scoped CSS modules standar enterprise).
   - Implementasikan CSS Containment (`contain` dan `content-visibility: auto`) pada baris tabel yang tidak terlihat di viewport layar.
   - Atasi CLS dengan implementasi CSS `aspect-ratio` / reservasi layout dan skeleton loading state murni berbasis CSS modern.
   - Isolasi layer rendering kolom *sticky* menggunakan kompositor GPU yang aman tanpa memicu *layer explosion*.

2. **Full Accessibility Hardening (WCAG 2.2 Level AA):**
   - Hapus semua praktik destruktif `outline: none` dan implementasikan sistem visual fokus adaptif menggunakan pseudo-class `:focus-visible` dengan kontras minimal 3:1 terhadap warna latar belakang.
   - Perbaiki rasio kontras teks status badges/tags menjadi minimal 4.5:1 (Normal Text) menggunakan CSS Color Module Level 4 (`color-mix()` atau ruang warna OKLCH).
   - Buat implementasi visual states yang mendukung penuh `@media (prefers-reduced-motion: reduce)` dan `@media (forced-colors: active)` (Windows High Contrast Mode).
   - Buat kelas utility `.visually-hidden` / `.sr-only` yang robust dan tidak merusak layout visual untuk mengakomodasi screen reader.

3. **Tooling & Build Pipeline Configuration:**
   - Konfigurasikan PostCSS atau Lightning CSS pipeline untuk melakukan otomatisasi prefixing, minifikasi, dan linting spesifisitas via Stylelint rules.
   - Definisikan batasan *budget* CSS pada build pipeline (contoh: bundle size limit warning jika total CSS melampaui batas tertentu).

#### Constraints
- Dilarang menggunakan library komponen eksternal (harus Vanilla CSS / CSS Modules).
- Tidak boleh memutus struktur semantik HTML tabel native (`<table>`, `<thead>`, `<tbody>`, `<tr>`, `<th>`, `<td>`).
- Dilarang keras menggunakan `!important` untuk menimpa spesifisitas aturan warisan.
- CSS harus valid dan kompatibel dengan browser modern (Baseline evergreen browsers).

#### Expected Output
1. File refaktorisasi CSS/SCSS yang bersih, terdokumentasi, dan terstruktur modular.
2. Penjelasan arsitektur tertulis yang menguraikan:
   - Analisis *before vs after* dari jalur rendering.
   - Matriks verifikasi rasio kontras warna (OKLCH calculations).
   - Skema proteksi CLS dan reduksi INP yang diimplementasikan.

---

## 5. Knowledge Check & Checklist

Tinjau penguasaan materi Anda sebelum melangkah ke bab berikutnya. Tandai checklist berikut secara objektif:

### Saya harus memahami:
- [ ] Mekanisme parsing browser dari tokenisasi HTML/CSS hingga pembentukan Render Tree.
- [ ] Batas pemisah operasi antara Main Thread (Layout, Recalculate Style, Paint) dan Compositor Thread (Compositing, GPU Tiling).
- [ ] Dampak arsitektur CSS terhadap tiga metrik vital Google: LCP, CLS, dan INP.
- [ ] Cara kerja internal CSS Containment (`layout`, `paint`, `size`, `style`) dan `content-visibility`.
- [ ] Standar WCAG 2.2 Level AA/AAA terkait color contrast, text scaling, target sizes, dan motion sensitivity.
- [ ] Siklus hidup visual web font (FOIT/FOUT) dan penanganannya menggunakan Font Metric Overrides.
- [ ] Mekanisme pemetaan DOM + CSSOM ke dalam Accessibility Tree (AOM) dan perbedaannya dengan Render Tree.
- [ ] Perbedaan pipeline AST parser tradisional (PostCSS) vs native compiled toolchain (Lightning CSS).

### Saya tidak perlu menghafal:
- [ ] Nilai presisi dari rasio metrik font kustom font-by-font (gunakan tools otomatisasi seperti *Fontaine* atau *Capsize*).
- [ ] Vendor prefixes historis browser usang (percayakan sepenuhnya pada Browserslist/Autoprefixer/Lightning CSS).
- [ ] Notasi matematis RGB desimal untuk rumus WCAG Luminance (gunakan Color Picker DevTools atau fungsi OKLCH/color-contrast tools).
- [ ] Seluruh parameter string konfigurasi compiler Rust/JS (cukup pahami fungsi opsi intinya).

### Saya harus bisa melakukan:
- [ ] Membaca flame-graph dan timeline di Chrome DevTools Performance Panel untuk melacak *Layout Thrashing* dan *Long Tasks* yang dipicu oleh CSS.
- [ ] Menggunakan DevTools Rendering tab (*Paint Flashing*, *Layout Shift Regions*, *Layer Borders*) untuk mendeteksi repaint dan over-compositing.
- [ ] Mengimplementasikan *Zero-CLS typography strategy* menggunakan `@font-face` dengan `size-adjust` dan metric overrides.
- [ ] Mendesain sistem tema multi-tenant menggunakan CSS Custom Properties tanpa JavaScript overhead saat runtime.
- [ ] Menulis CSS yang lolos audit automated accessibility checker (Axe Core / Lighthouse Accessibility) dengan skor 100/100.
- [ ] Mengonfigurasi linting sistemik (Stylelint) untuk memblokir penulisan selektor yang menghasilkan komputasi mahal (*expensive selector matching*).