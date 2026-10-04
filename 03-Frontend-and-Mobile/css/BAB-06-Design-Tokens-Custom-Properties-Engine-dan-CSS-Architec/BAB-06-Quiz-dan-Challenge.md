# BAB 06: Quiz, Challenge, & Knowledge Check
**Design Tokens, Custom Properties Engine, dan CSS Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Arsitektur Token Tiga Tingkat (Three-Tier Token Architecture)
Dalam sistem desain skala enterprise, token arsitektur umumnya dibagi menjadi tiga tier: *Core/Global Tokens* (Primitive), *Semantic/Alias Tokens*, dan *Component Tokens*. 
Jelaskan secara struktural mengapa komponen UI (misalnya tombol atau modal) dilarang keras mengonsumsi Core Tokens secara langsung (`background-color: var(--color-blue-500);`). Apa konsekuensi arsitektural terhadap kemampuan *theming*, *dark mode switching*, dan pemeliharaan jangka panjang (*scalability*) jika aturan isolasi layer ini dilanggar?

### Soal 1.2: Runtime Reactivity: CSS Custom Properties vs Preprocessor Variables
Bandingkan secara mendalam model eksekusi antara variabel preprocessor (seperti Sass `$primary-color`) dengan CSS Custom Properties (`--primary-color`). Analisis perbedaan keduanya ditinjau dari:
1. Tahapan siklus kompilasi vs siklus hidup runtime browser (*CSSOM & Cascade lifecycle*).
2. Kemampuan delegasi *inheritance* berbasis struktur pohon DOM.
3. Dampak memori dan pemrosesan saat melakukan perubahan nilai secara dinamis melalui JavaScript.

### Soal 1.3: Mekanisme Resolusi Fallback & Evaluasi Tautan `var()`
Perhatikan deklarasi berikut:
```css
.card {
  --surface-color: ; /* Nilai berupa spasi kosong (whitespace/empty token) */
  background-color: var(--surface-color, var(--default-surface, #ffffff));
}
```
Bagaimana CSS Parser dan CSSOM mengevaluasi nilai `background-color` pada elemen `.card` di atas? Jelaskan secara spesifik perbedaan antara properti kustom yang *undeclared* (tidak terdefinisi), bernilai *empty token/whitespace*, dan bernilai `initial`. Mengapa fallback kedua (`#ffffff`) dieksekusi atau tidak dieksekusi?

### Soal 1.4: Paradigma CSS Architecture Modern vs Cascade Layers (`@layer`)
Metodologi konvensional seperti BEM (*Block Element Modifier*), OOCSS, dan SMACSS dirancang terutama untuk mengatasi masalah *specificity wars* dan scoping pada era ketika CSS bersifat *flat global namespace*. 
Bagaimana kehadiran spesifikasi CSS Modern Cascade Layers (`@layer`) mengubah fundamental arsitektur penulisan CSS? Bagaimana posisi *design token system* seharusnya dipetakan ke dalam struktur hierarki layer untuk menjamin token tidak dapat ditimpa (*overwritten*) secara tidak sengaja oleh spesifisitas selektor komponen?

### Soal 1.5: CSS Houdini Properties & Values API (`@property`)
Jelaskan batasan fundamental dari *CSS Custom Properties* standar yang diselesaikan oleh `@property`. Uraikan fungsi dari tiga deskriptor utama (`syntax`, `inherits`, dan `initial-value`) serta implikasinya terhadap kemampuan mesin peramban (*browser engine*) dalam melakukan interpolasi animasi/transisi warna secara mulus (*smooth color transitions*).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Insiden "Invalid at Computed-Value Time" (IACVT)
Perhatikan cuplikan kode berikut:
```css
:root {
  --brand-padding: 16px;
}
.banner {
  color: var(--brand-padding); /* 16px adalah tipe data <length>, bukan <color> */
}
```
Ketika browser memproses elemen `.banner`, jelaskan apa yang terjadi secara internal menurut spesifikasi CSS Custom Properties Level 1. 
1. Mengapa parser CSS tidak membuang (*discard*) deklarasi tersebut pada tahap *parse time*?
2. Apa nilai akhir dari `color` elemen `.banner` pada saat *computed-value time*? 
3. Mengapa browser tidak mengembalikan nilai warna ke deklarasi CSS fallback sebelumnya yang dituliskan di atasnya dalam *cascade rule*?

### Soal 2.2: Style Invalidation & Recalculation Performance Bottleneck
Sebuah aplikasi web *single-page* skala besar memiliki 15.000 elemen DOM aktif. Tim engineering mengimplementasikan tema gelap (*dark theme*) dengan mengubah nilai custom property pada level root:
```javascript
document.documentElement.style.setProperty('--bg-primary', '#121212');
```
Operasi ini memicu *frame drop* signifikan (Long Task > 120ms) pada perangkat kelas menengah ke bawah (*low-end mobile*). 
1. Mengapa mutasi variabel di `:root` menyebabkan *full DOM style invalidation*?
2. Bagaimana strategi arsitektural menggunakan teknik *scoped custom properties* atau CSS Containment (`contain: style`) untuk memitigasi *invalidation blast radius* tersebut?

### Soal 2.3: Pendeteksian dan Resolusi Siklus Dependensi (Cyclic Dependencies)
Perhatikan kasus ketergantungan melingkar berikut:
```css
.box {
  --base-size: calc(var(--offset-size) + 4px);
  --offset-size: calc(var(--base-size) * 2);
  width: var(--base-size);
}
```
Bagaimana algoritma resolusi CSS Custom Properties mendeteksi siklus dependensi ini? Ketika siklus terdeteksi, apa status nilai dari `--base-size` dan `--offset-size` menurut W3C specification (*guaranteed-invalid value*)? Apa nilai aktual properti `width` pada rendering engine?

### Soal 2.4: Token Shadowing dan Mekanisme Inheritance Across Shadow DOM
Dalam arsitektur *Micro-Frontend* yang memanfaatkan Web Components (Shadow DOM v1), seorang developer mendefinisikan custom property di root dokumen hosting dan mencoba membacanya di dalam Shadow Root yang menggunakan mode `encapsulated` (`mode: 'closed'` atau `'open'`).
1. Mengapa CSS Custom Properties dapat menembus batas Shadow DOM (*Shadow Boundary*), sementara selektor CSS standar terblokir?
2. Bagaimana Anda merancang kontrak API publik (*Component Styling API*) untuk sebuah Web Component agar konsumen dapat memodifikasi token internal tanpa mengekspos struktur DOM internal komponen tersebut?

### Soal 2.5: Implementasi State Machine via "CSS Space Toggle"
Dalam beberapa CSS library tingkat lanjut, ditemukan pola kode berikut:
```css
:root {
  --ON: ;
  --OFF: initial;
}
.btn {
  --is-danger: var(--OFF);
  background-color: var(--is-danger, green) var(--is-not-danger, red);
}
```
Jelaskan mekanisme internal *CSS Space Toggle* (disebut juga *CSS Boolean/Ternary Logic*). Bagaimana manipulasi substitusi token kosong (*whitespace token*) versus nilai `initial` dapat bertindak sebagai gerbang logika (*logic gate*) deklaratif murni dalam engine CSS tanpa bantuan JavaScript? Apa bahaya tersembunyi (*maintenance overhead* dan risiko spesifikasi) dari pola ini?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Bottleneck Style Recalculation pada Super-App
**Konteks:** Sebuah aplikasi dashboard finansial enterprise menampilkan tabel data grid virtual dengan 50 kolom dan 2.000 baris yang dirender secara bersamaan. Setiap sel memanfaatkan token dinamis berbasis CSS Variables untuk status keuntungan/kerugian (`--cell-color: var(--trend-color)`). Saat streaming data WebSocket masuk setiap 100ms, sistem memperbarui token CSS pada level container baris:
```javascript
rowElement.style.setProperty('--trend-color', isPositive ? 'var(--color-profit)' : 'var(--color-loss)');
```
Browser Profiler (Chrome DevTools Performance Panel) menunjukkan *Recalculate Style* memakan 70% dari budget frame (70ms per cycle), mengakibatkan UI freezing permanen.

**Tugas Diagnostik & Solusi:**
1. Bedah mengapa *recalculation* merambat secara agresif ke seluruh anak elemen sel tabel meskipun nilainya hanya berganti warna teks (*paint property*).
2. Bagaimana Anda mendesain ulang arsitektur token tersebut dengan memanfaatkan `@property` (Houdini) dan membatasi *inheritance propagation* (`inherits: false`) untuk menghilangkan bottleneck tersebut secara permanen? Jelaskan mekanisme teknis mengapa perbaikan ini bekerja.

---

### Skenario B: Race Condition dan Token Collisions pada Integrasi Micro-Frontend
**Konteks:** Perusahaan Anda menggabungkan tiga aplikasi micro-frontend independen (Aplikasi Pembayaran, Aplikasi Katalog, dan Aplikasi Header Global) ke dalam satu *shell container* bersama. 
- Aplikasi Pembayaran memuat Design System v1 dengan definisi `:root { --color-primary: #0052cc; }`.
- Aplikasi Katalog memuat Design System v2 dengan definisi `:root { --color-primary: #ff5630; }`.
- Kedua aplikasi memuat stylesheet mereka secara dinamis (*asynchronous bundle injection*) tergantung navigasi rute pengguna.

Akibatnya, terjadi insiden di mana warna tombol bayar pada Aplikasi Pembayaran tiba-tiba berubah menjadi oranye (`#ff5630`) ketika pengguna membuka tab Katalog di background, merusak integritas brand dan lolos dari UI integration tests.

**Tugas Diagnostik & Solusi:**
1. Analisis mengapa `:root` selector menjadi *single point of failure* dalam arsitektur token micro-frontend.
2. Rancang arsitektur CSS Token Namespace dan Isolation System yang kebal terhadap urutan eksekusi script (*asynchronous load race conditions*). Solusi harus mencakup:
   - Penggunaan *Contextual Theme Scoping* berbasis atribut dataset.
   - Pemanfaatan `@layer` untuk mengunci urutan prioritas cascade.
   - Mekanisme proteksi terhadap kebocoran token (*token leaking*).

---

### Skenario C: Dilema Arsitektur Multi-Brand Whitelabel (Runtime vs Build-Time)
**Konteks:** Anda adalah Principal Architect yang diminta membangun platform e-commerce multi-tenant (Whitelabel) yang mendukung 30 brand berbeda. Setiap brand memiliki palet warna unik, variasi tipografi, border-radius, dan skema mode *Light/Dark*. 
Tim terbelah menjadi dua kubu:
- **Kubu A:** Mengusulkan *Zero-Runtime Approach* menggunakan preprocessor/CSS-in-JS build tools (Sass/Vanilla Extract) yang menghasilkan file CSS statis terpisah untuk setiap brand (`brand-a.css`, `brand-b.css`).
- **Kubu B:** Mengusulkan *Dynamic Engine Approach* berbasis Single Universal CSS Bundle dengan CSS Custom Properties Engine yang menginjeksi token secara dinamis di runtime via tag `<style>` atau file JSON token yang di-resolve via CSS variables.

**Tugas Evaluasi & Solusi:**
1. Sajikan analisis perbandingan *trade-off* mendalam yang mencakup metrik:
   - *Time to First Byte* (TTFB) & Critical CSS Size.
   - Rasio *Cache Hit Rate* pada CDN antar-tenant.
   - Kompleksitas CI/CD deployment pipeline.
   - Kemampuan *real-time runtime rebranding* (misal: visual theme builder untuk admin).
2. Rancang solusi arsitektur hibrida (*Hybrid Token Architecture*) yang mengambil keunggulan terbaik dari kedua pendekatan tersebut secara elegan.

---

## 4. Chapter Challenge

### Tantangan Praktis: Membangun Enterprise-Grade Dynamic Token Engine dengan Houdini & Cascade Layers

#### Problem Statement
Sebuah platform SaaS enterprise memerlukan sistem arsitektur CSS modern yang modular, tahan terhadap konflik spesifisitas, memiliki validasi tipe data yang ketat (*type safety*), mendukung *nested theme switching* (misal: kartu bertema gelap di dalam halaman bertema terang), dan mendukung mode *high-contrast* untuk aksesibilitas WCAG AAA tanpa menggunakan framework pihak ketiga atau runtime JavaScript berat.

#### Requirements
1. **Three-Tier Architecture Hierarchy:**
   - **Tier 1 (Primitive):** Palet raw color (HWB/OKLCH), scale spasi modular, dan radius.
   - **Tier 2 (Semantic):** Mapping context (`--surface-canvas`, `--text-primary`, `--interactive-accent`, dll.) yang merespons perubahan tema secara dinamis.
   - **Tier 3 (Component):** Token khusus komponen yang mengonsumsi semantic tokens dengan mekanisme *self-fallback*.
2. **Type Safety via `@property`:**
   - Definisikan minimal 3 custom property menggunakan `@property` dengan sintaks yang ketat (misalnya tipe `<color>`, `<length>`, atau `<percentage>`), deskriptor `inherits`, dan `initial-value` valid untuk memastikan transisi warna mulus tanpa cacat visual.
3. **Cascade Layering Strategy:**
   - Seluruh stylesheet wajib diorganisasikan ke dalam skema `@layer` yang presisi:
     `@layer reset, tokens.primitive, tokens.semantic, layout, components, overrides;`
4. **Contextual & Nested Theming Engine:**
   - Theme switching harus dapat diterapkan di level root (`data-theme="dark"`) maupun di level sub-tree lokal (`data-theme="dark"` diterapkan pada card di dalam root bertema terang) tanpa memecah kalkulasi variabel.
5. **A11y High-Contrast Mode:**
   - Sediakan integrasi media query `@media (prefers-contrast: more)` yang merekonfigurasi semantic tokens secara otomatis untuk memenuhi rasio kontras 7:1.

#### Constraints
- **Strictly No-JS for Theming:** Pergantian visual tema dan fallback harus berjalan 100% menggunakan deklarasi CSS murni (state switching diperbolehkan menggunakan atribut HTML `data-theme` statis untuk demonstrasi).
- **Zero Use of `!important`:** Pengaturan prioritas spesifisitas harus diatur murni melalui arsitektur `@layer` dan keteraturan cascade.
- **Modern Color Spaces:** Palet warna utama wajib didefinisikan menggunakan ruang warna modern: **OKLCH** (bukan hex atau RGB tradisional) untuk memastikan linearitas persepsi luminansi (*perceptual uniformity*).

#### Expected Output
Kirimkan satu bundle implementasi terstruktur yang mencakup:
1. Blok registrasi Houdini API (`@property`).
2. Definisi hierarki `@layer` dan struktur token tiga tingkat.
3. Blok CSS untuk Theming & A11y Adaptation.
4. Cuplikan implementasi satu komponen UI kompleks (misalnya: `.pricing-card`) yang mengekspos Component Tokens secara defensif.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi spesifikasi CSS Custom Properties Level 1 dan algoritma substitusi `var()`.
- [ ] Definisi dan implikasi status *Invalid at Computed-Value Time* (IACVT) versus *Parse-time Invalidity*.
- [ ] Mengapa mekanisme fallback `var(--x, fallback)` hanya terpicu jika properti bernilai *guaranteed-invalid* dan gagal jika bernilai salah tipe (*type mismatch*).
- [ ] Peran dan cara kerja registrasi CSS Houdini Properties and Values API (`@property`) dalam kontrol pewarisan (*inheritance control*) dan interpolasi animasi.
- [ ] Matriks prioritas pada CSS Cascade Layers (`@layer`) dan bagaimana *unlayered styles* selalu mengalahkan *layered styles*.
- [ ] Dampak modifikasi custom property di level root terhadap pipeline render peramban (*Style Invalidation -> Recalculate Styles -> Layout -> Paint*).
- [ ] Prinsip *Perceptually Uniform Color Spaces* (OKLCH) dalam perancangan palet design tokens modern.

### Saya tidak perlu menghafal:
- [ ] Seluruh tabel konversi nama warna bawaan browser (Named Colors seperti `rebeccapurple`, `papayawhip`).
- [ ] Sintaks mikro-deskriptor yang jarang digunakan pada grammar `@property` (misal deskriptor kombinasi kompleks `<transform-function> | <custom-ident>` yang cukup dilihat pada dokumentasi MDN saat dibutuhkan).
- [ ] Daftar lengkap kode hex lama untuk library warna legacy (cukup pahami model channel OKLCH: Lightness, Chroma, Hue).

### Saya harus bisa melakukan:
- [ ] Mengaudit dan memetakan struktur CSS monolitik ke dalam arsitektur Design Tokens Tiga Tingkat (Primitive, Semantic, Component).
- [ ] Melakukan debugging visual pada Chrome/Firefox DevTools untuk melacak asal-usul inheritance custom property yang tertimpa (*overridden token tree*).
- [ ] Mengisolasi bottleneck performa rendering yang disebabkan oleh perubahan nilai CSS Variables skala besar menggunakan Performance Profiler.
- [ ] Mengonfigurasi arsitektur styling Web Component atau Micro-Frontend yang aman dari kebocoran token (*token leaking*) menggunakan Shadow DOM Boundaries dan `@property { inherits: false }`.
- [ ] Membangun mesin tema (*theming engine*) multi-brand deklaratif yang mendukung *Dark Mode* dan *High-Contrast Accessibility* tanpa ketergantungan runtime JavaScript.