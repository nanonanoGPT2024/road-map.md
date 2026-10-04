# BAB 10: Quiz, Challenge, & Knowledge Check
**Capstone Project: Enterprise-Grade Design System & High-Performance Dashboard**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Arsitektur Tokenisasi Berlapis (Multi-Tier Token Architecture)**  
   Jelaskan perbedaan struktural, tujuan tata kelola, dan batasan penggunaan antara *Global/Primitive Tokens* (misal: `--color-blue-500: #1d4ed8`), *Semantic/Alias Tokens* (misal: `--color-surface-interactive-default: var(--color-blue-500)`), dan *Component-Scoped Tokens* (misal: `--btn-bg: var(--color-surface-interactive-default)`). Mengapa mengekspos token primitif langsung ke dalam kode komponen enterprise dianggap sebagai pelanggaran tata kelola arsitektur (*architectural governance antipattern*)?

2. **Primitive Rendering Lifecycle & CSS Containment**  
   Bagaimana deklarasi `contain: strict;` dan `content-visibility: auto;` mempengaruhi siklus hidup rendering browser (*Style Recalculation*, *Layout*, *Paint*, dan *Composite*)? Jelaskan secara matematis dan prosedural mengapa properti `contain-intrinsic-size` wajib disertakan saat mengimplementasikan `content-visibility: auto` untuk mencegah anomali *layout shift* (CLS).

3. **Orkestrasi Spesifisitas Menggunakan CSS Cascade Layers (`@layer`)**  
   Di dalam ekosistem monorepo skala besar dengan dependensi pihak ketiga, bagaimana mekanisme resolving spesifisitas pada `@layer` membalikkan aturan *classic CSS specificity* (ID, class, attribute)? Jelaskan apa yang terjadi ketika gaya dideklarasikan di luar layer (*unlayered styles*) dibandingkan dengan gaya di dalam layer, dan bagaimana urutan evaluasi layer dieksekusi ketika digunakan bersama aturan `!important`.

4. **Transisi Ekosistem: Media Queries vs. Container Queries (Size & Style)**  
   Analisis kelemahan mendasar dari *Viewport-based Media Queries* dalam konteks *micro-frontend* dan arsitektur komponen modular. Bagaimana `@container (min-width: ...)` dan *container style queries* menyelesaikan batasan konteks rendering tersebut tanpa merusak modularitas independen dari komponen UI dashboard?

5. **Critical CSS Path dan Cost of CSSOM Generation**  
   Secara spesifik pada arsitektur streaming SSR (Server-Side Rendering), bagaimana browser memproses *Critical Path Rendering* dari pengiriman byte HTML pertama hingga *First Contentful Paint* (FCP)? Jelaskan dampak blocking dari *unminified, deeply nested selectors* terhadap waktu pembentukan CSSOM (*CSS Object Model*) dan eksekusi parsing thread utama.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Root Cause Analysis: Forced Synchronous Layout & Layout Thrashing**  
   Perhatikan cuplikan logika rendering dashboard berikut:
   ```javascript
   elements.forEach((el) => {
     const height = el.getBoundingClientRect().height;
     el.style.setProperty('--computed-height', `${height + 10}px`);
     el.style.transform = `translateY(${height}px)`;
   });
   ```
   Bedah bagaimana interaksi di atas memicu *layout thrashing* di tingkat internal rendering engine browser (Blink/Gecko). Tuliskan ulang alur kerja mutasi DOM dan pembacaan metrik geometri tersebut agar bersih dari *pipeline stalls* dan terisolasi dalam fase *Composite/Paint*.

2. **Resolusi Memory Footprint & Dynamic Token Inheritance**  
   Sebuah dashboard enterprise menampilkan hierarki DOM dengan kedalaman 35 level dan 20.000 elemen aktif. Setiap elemen mendeklarasikan custom property secara lokal: `* { --local-dynamic-val: ... }`. Bagaimana *CSS Custom Property inheritance graph* diproses di memori browser? Mengapa pendefinisian variabel CSS secara global di `:root` memiliki profil konsumsi memori dan komputasi *style invalidation* yang lebih efisien daripada scoping deklarasi di universal selector `*`?

3. **Compositing Layer Explosion & Hardware Acceleration Traps**  
   Penggunaan deklarasi `will-change: transform;` secara preventif pada 500 kartu metrik data dashboard dilaporkan menyebabkan konsumsi VRAM GPU melonjak tajam dan memicu lag parah (*jank*) pada perangkat mobile/low-end. Analisis mekanisme pembuatan *GraphicLayers* internal browser, kriteria pembuatan layer baru (*layer promotion*), dan kondisi di mana browser jatuh ke dalam kondisi *Layer Explosion*.

4. **Edge Cases: Subpixel Anti-Aliasing & Fractional Pixel Shifting**  
   Ketika merender sistem Grid kompleks dan komponen SVG-based Data Visualization di layar high-DPI (Retina/4K), sering ditemukan masalah garis tepi (*borders*) yang kabur (*blurry*) atau hilang sebagian pada breakpoint tertentu. Mengapa pembagian fraksional piksel dalam CSS Flexbox/Grid menyebabkan anomali ini pada subpixel rendering engine, dan bagaimana mitigasi absolutnya menggunakan `devicePixelRatio`, `transform: translateZ(0)`, atau koordinat berbasis media queries?

5. **Spesifisitas dan Layer Inversion Debugging**  
   Perhatikan kode CSS berikut:
   ```css
   @layer framework, custom;

   @layer framework {
     #super-priority-btn.primary {
       background-color: blue !important;
     }
   }

   @layer custom {
     .btn {
       background-color: red !important;
     }
   }

   button {
     background-color: green;
   }
   ```
   Warna akhir apa yang dirender oleh browser pada elemen `<button id="super-priority-btn" class="primary btn">`? Jelaskan secara analitis logika penentuan kaskade browser berdasarkan spesifikasi *CSS Cascading and Inheritance Level 5*, khususnya mengenai interaksi antara *layer ordering* dan deklarasi `!important`.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Rendering Bottleneck pada Real-Time Financial Telemetry Table
* **Konteks:** Sebuah aplikasi perdagangan derivatif finansial merender tabel berisi 5.000 baris secara real-time via WebSocket dengan frekuensi pembaruan 60 kali per detik (60 FPS/Hz). 
* **Masalah:** Setiap pembaruan harga (yang mengubah warna teks sel dari hijau ke merah via class mutation) menyebabkan penurunan frame rate dramatis hingga 15 FPS. CPU Profiler menunjukkan bahwa 85% waktu thread utama habis di fase `Recalculate Style` dan `Update Layer Tree`.
* **Pertanyaan Diagnostik:**
  1. Audit arsitektur CSS: Selektor seperti apa yang dapat menyebabkan invalidasi *style tree* merambat secara luas ke seluruh pohon DOM saat class bermutasi?
  2. Rancang arsitektur styling zero-reflow untuk sel tabel tersebut menggunakan isolasi rendering (`contain`, `contain-intrinsic-size`, `@layer`), serta jelaskan apakah transisi warna harus didelegasikan ke GPU compositor atau inline custom properties tanpa memicu global style invalidation!

### Skenario B: Token Collision & Bleed-Through pada Arsitektur Micro-Frontend
* **Konteks:** Perusahaan melakukan federasi modul (*Module Federation*) yang menggabungkan Dashboard Tim Transaksi (menggunakan Design System Core v2 dengan variabel token terenkapsulasi) dan Widget Tim Analytics (masih menggunakan Design System Core v1).
* **Masalah:** Terjadi *token collision* masif. Variabel `--color-primary: #0052cc` milik Analytics menimpa `--color-primary: #107569` milik Transaksi di seluruh level host. Sebagian styling dari stylesheet lama bocor (*bleed-through*) ke dalam komponen Web Components/Shadow DOM dan micro-frontend lain karena kebocoran spesifisitas global selector.
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda merancang skema *token namespacing* dan isolasi spesifisitas pada runtime CSS tanpa harus menulis ulang seluruh basis kode v1 secara instan?
  2. Jika enkapsulasi Shadow DOM tidak dimungkinkan karena keterbatasan library pihak ketiga, bagaimana konfigurasi `@layer`, `@scope` (*CSS Scope Specification*), atau PostCSS prefixing dapat diimplementasikan untuk memberikan demarkasi batas gaya (*styling boundary*) yang absolut di antara kedua micro-frontend tersebut?

### Skenario C: Architectural Trade-Off: Zero-Runtime CSS-in-JS vs. Atomic Utility CSS
* **Konteks:** Divisi Enterprise Engineering sedang merancang arsitektur dashboard analitik multi-tenant global yang melayani 100 juta *pageviews* per bulan. Arsitektur harus mendukung: *zero-CLS*, multi-brand theming (kemampuan rebranding dinamis per organisasi/tenant), ukuran bundel sekecil mungkin, dan kecepatan *Time to Interactive* (TTI) maksimum.
* **Masalah:** Tim inti terbagi menjadi dua kubu: Kubu A merekomendasikan Zero-Runtime CSS-in-JS (seperti Vanilla Extract / StyleX), sedangkan Kubu B merekomendasikan Pure Atomic Utility-First CSS (seperti Tailwind CSS dengan custom theme engine).
* **Pertanyaan Diagnostik:**
  1. Bandingkan kedua pendekatan tersebut secara komprehensif berdasarkan:
     * *Network transfer payload* saat aplikasi diskalakan ke 1.000+ komponen dashboard.
     * Mekanisme dynamic theme switching (overhead CSSOM vs switching custom properties).
     * DX (*Developer Experience*) dan integrasi TypeScript static type-checking pada token desain.
  2. Buat matriks keputusan keputusan arsitektur (ADR - *Architectural Decision Record*) yang secara tegas menetapkan pilihan mana yang paling optimal untuk skenario multi-tenant di atas, disertai justifikasi teknis tingkat mesin rendering.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Real-Time Telemetry Dashboard & Multi-Brand Token Engine

#### Problem Statement
Sistem analitik internal perusahaan tidak mampu memproses stream data telemetri ribuan server secara simultan tanpa *dropped frames* dan memory leak. Anda ditugaskan untuk membangun dashboard performa tinggi dari nol (*ground up*) yang memiliki kapabilitas multi-tenant dinamis, rendering data grid tervirtualisasi, dan responsivitas absolut menggunakan CSS modern murni.

#### Requirements
1. **Arsitektur Token Multi-Tier & Multi-Brand:**
   * Bangun token architecture (Primitive, Semantic, Component) murni menggunakan CSS Custom Properties.
   * Sediakan implementasi minimal dua tema (*Light Theme* dan *High-Contrast Dark Theme*) yang dapat dialihkan via atribut `data-theme` pada `:root` tanpa memicu *flash of unstyled content* (FOUC).
2. **Real-time Telemetry Data Grid:**
   * Rancang visualisasi grid dashboard menggunakan CSS Grid & Flexbox tingkat lanjut yang menampilkan metrik telemetri (CPU, Memory, Network I/O).
   * Elemen indikator metrik yang diperbarui via JavaScript interval (mensimulasikan WebSocket 60 updates/sec) hanya boleh memicu tahapan **Composite Only** (gunakan manipulasi GPU-friendly: `transform`, `opacity`, dan CSS Custom Property yang dimediasi Houdini `@property` bila diperlukan).
3. **Responsive Modular Containment:**
   * Terapkan Container Queries (`@container`) pada kartu metrik dashboard. Kartu harus mengubah layout internalnya secara otonom dari mode compact (vertikal) ke mode detail (multi-kolom) berdasarkan lebar kontainer induknya, bukan lebar *viewport* browser.
   * Terapkan `content-visibility: auto` dan `contain-intrinsic-size` pada list data telemetri panjang untuk memastikan browser melewati layouting node yang berada di luar layar (*off-screen*).
4. **Strict Isolation via CSS Cascade Layers:**
   * Bungkus seluruh aturan CSS dalam `@layer` dengan urutan prioritas yang ketat:
     `@layer reset, base, tokens, components, utilities;`
   * Pastikan tidak ada satupun *unlayered styles* yang berpotensi membocorkan spesifisitas.

#### Constraints
* **Zero CSS Framework Dependencies:** Dilarang menggunakan Tailwind, Bootstrap, Sass, atau CSS-in-JS runtime engine. Gunakan *Vanilla Modern CSS*.
* **Zero Layout Thrashing:** DevTools Performance panel tidak boleh mencatat adanya *Forced Reflow* (garis merah pada frame timeline).
* **Lighthouse Performance Score:** Wajib mencapai skor performa minimal **98/100** dengan CLS (Cumulative Layout Shift) mutlak **0.00**.
* **Browser Compatibility:** Baseline CSS modern (Chrome 105+, Firefox 110+, Safari 16+).

#### Expected Output
1. File `tokens.css`: Deklarasi hierarki token berlapis beserta strategi `@layer tokens`.
2. File `layout.css`: Implementasi Grid, Subgrid, dan Container Queries responsif.
3. File `dashboard.css`: Implementasi komponen terisolasi (`contain`, Houdini `@property`, Composite styles).
4. File `index.html`: Simulasi mock UI dashboard dengan skrip pengujian beban update interval 60 FPS.
5. Laporan singkat ringkasan eksekusi DevTools: Bukti tidak terjadinya *Layout Thrashing* dan validasi *FPS Timeline* stabil di kisaran 60 FPS saat ribuan data diperbarui secara simultan.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup rendering browser secara mendalam (*Parse HTML* -> *DOM Tree* + *CSSOM* -> *Render Tree* -> *Layout* -> *Paint* -> *Composite*).
- [ ] Perilaku matematis dan prioritas CSS Cascade Layers (`@layer`) termasuk anomali pembalikan prioritas pada aturan `!important`.
- [ ] Cara kerja internal CSS Containment (`contain: layout paint size style`) dalam memangkas subtree style calculation.
- [ ] Mekanisme Browser Rendering Engine dalam mengalokasikan memori untuk *Compositing Layers* dan bahaya *Compositing Layer Explosion*.
- [ ] Perbedaan fundamental antara komputasi CSS Custom Properties saat runtime vs variabel pre-prosesor (Sass/Less) saat build-time.
- [ ] Keterbatasan struktural Viewport Media Queries dan keunggulan mekanis Container Queries (`@container`) dalam arsitektur komponen terisolasi.
- [ ] Algoritma resolving spesifisitas CSS dan implementasi ITCSS (*Inverted Triangle CSS*) untuk tata kelola enterprise monorepo.

### Saya tidak perlu menghafal:
- [ ] Nilai exact dari dynamic viewport units lama (misal: hack koordinat spesifik Safari iOS `100vh` bug, karena telah digantikan secara native oleh `dvh`, `svh`, `lvh`).
- [ ] Vendor prefixes non-standar (`-webkit-`, `-moz-`, `-ms-`) yang sudah terdepresiasi dari spec W3C (cukup delegasikan ke pipeline build Autoprefixer).
- [ ] Sintaks legacy CSS Grid/Flexbox era Internet Explorer 10/11 (`-ms-grid-columns`, dll).
- [ ] Hex code absolut dari palet warna desain token (cukup pahami abstraksi referensial hierarkinya).

### Saya harus bisa melakukan:
- [ ] Mengaudit, mendeteksi, dan menghilangkan *Forced Synchronous Layout* dan *Layout Thrashing* menggunakan Chrome DevTools Performance & Rendering Panel.
- [ ] Merancang arsitektur CSS multi-tier tokens enterprise yang mampu beradaptasi dengan kebutuhan multi-brand dan dynamic context-switching tanpa FOUC.
- [ ] Mengimplementasikan *zero-runtime animation/transitions* yang hanya berjalan di GPU thread (*compositor-only properties*: `transform`, `opacity`).
- [ ] Menyusun arsitektur CSS modular berbasis `@layer` dan `@container` yang tahan terhadap kebocoran spesifisitas pada integrasi micro-frontend.
- [ ] Mengoptimalkan performa halaman dengan *deep-DOM lists* hingga mencapai stabilitas rendering 60 FPS menggunakan kombinasi `content-visibility` dan `contain-intrinsic-size`.
- [ ] Menggunakan CSS Houdini API (`@property`) untuk mendefinisikan tipe data, inheritabilitas, dan nilai fallback pada CSS Custom Properties guna mendukung transisi/animasi variabel tingkat lanjut.