# BAB 03: Quiz, Challenge, & Knowledge Check
**Fondasi CSS3: Box Model, Specificity & Rendering Pipeline**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Diferensiasi Matematis `content-box` vs `border-box`**  
   Diberikan sebuah elemen `<div>` dengan deklarasi:
   ```css
   width: 320px;
   padding: 16px 24px;
   border: 4px solid #000;
   margin: 12px;
   ```
   Hitung secara presisi total lebar fisik (*computed horizontal footprint*) yang diokupasi elemen tersebut di dalam layout tree ketika menggunakan `box-sizing: content-box` versus `box-sizing: border-box`. Jelaskan mengapa industri modern mengadopsi `box-sizing: border-box` sebagai standar *universal reset*.

2. **Mekanisme dan Syarat Terjadinya *Margin Collapsing***  
   Jelaskan secara mendalam fenomena *margin collapsing* pada CSS. Sebutkan tiga kondisi spesifik di mana *margin collapsing* **pasti** terjadi antar elemen blok struktural, dan tiga kondisi arsitektural di mana *margin collapsing* secara otomatis digagalkan (*prevented*).

3. **Dekonstruksi Vektor Bobot Spesifisitas (*Specificity Hierarchy*)**  
   Uraikan matriks kalkulasi spesifisitas CSS berbasis sistem 4-komponen `(Inline, ID, Class/Attribute/Pseudo-class, Element/Pseudo-element)`. Urutkan selektor berikut dari spesifisitas terendah ke tertinggi dan tentukan nilai bobotnya:
   - Selektor A: `nav ul.menu li:first-child a:hover`
   - Selektor B: `#main-header nav.primary a`
   - Selektor C: `div[data-role="dialog"] button.btn.btn-primary`
   - Selektor D: `:where(.card) h2`

4. **Arsitektur Critical Rendering Path (CRP) Browser**  
   Petakan alur transisi dari kode sumber CSS mentah hingga menjadi piksel raster pada layar monitor:
   $$\text{HTML/CSS} \longrightarrow \text{DOM/CSSOM} \longrightarrow \text{Render Tree} \longrightarrow \text{Layout} \longrightarrow \text{Paint} \longrightarrow \text{Composite}$$
   Jelaskan secara spesifik apa yang dieksekusi oleh mesin browser (*browser engine*) pada fase **Layout (Reflow)** dibandingkan dengan fase **Paint (Repaint)**.

5. **Karakteristik Format Konteks Blok vs Inline (*Formatting Contexts*)**  
   Jelaskan perbedaan mendasar antara elemen berstatus `display: block`, `display: inline`, dan `display: inline-block` dalam merespons properti dimensi vertikal (`height`, `margin-top`, `margin-bottom`, `padding-top`, `padding-bottom`). Mengapa elemen `inline` murni tidak dapat mengubah *line-box height* melalui `margin-top`?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Patologi *Stacking Context* dan Jebakan `z-index`**  
   Seorang *engineer* menetapkan `z-index: 99999` pada komponen `.modal-tooltip`, namun elemen tersebut tetap tertutup oleh elemen `.sidebar` yang hanya memiliki `z-index: 2`. Setelah diinspeksi, elemen induk langsung dari modal tersebut memiliki deklarasi `opacity: 0.98; transform: translateZ(0);`. Analisis akar masalah teknis berdasarkan spesifikasi *Stacking Context* CSS dan jelaskan solusi arsitekturalnya tanpa menghapus efek animasi pada induk.

2. **Anatomi *Layout Thrashing* (Forced Synchronous Layout)**  
   Perhatikan potongan kode JavaScript berikut:
   ```javascript
   const elements = document.querySelectorAll('.card');
   for (let i = 0; i < elements.length; i++) {
     const width = elements[i].offsetWidth; // Read
     elements[i].style.width = (width + 10) + 'px'; // Write
   }
   ```
   Jelaskan mengapa kode di atas memicu *Layout Thrashing*. Apa dampak langsungnya terhadap *frame rate* (FPS) dan *pipeline* rendering browser? Tunjukkan rekonstruksi kode yang optimal untuk mencegah degradasi performa tersebut.

3. **Subpixel Rendering & Pixel-Snapping Anomalies**  
   Pada layar densitas tinggi (Retina/HiDPI dengan `devicePixelRatio: 2` atau `3`), perataan tata letak menggunakan persentase atau unit `em`/`rem` sering menghasilkan celah visual tipis (*1px hairline gap*) antar border atau background. Jelaskan fenomena internal browser yang melandasi *subpixel rendering* dan *pixel snapping*, serta bagaimana cara memitigasinya pada desain presisi tinggi.

4. **Karakteristik Isolasi Spesifisitas: `:is()` vs `:where()` vs Cascade Layers (`@layer`)**  
   Bandingkan kalkulasi spesifisitas selektor antara `:is(.card, #modal)` dengan `:where(.card, #modal)`. Selanjutnya, jelaskan bagaimana fitur modern *Cascade Layers* (`@layer`) mengubah aturan resolusi konflik gaya tanpa harus menaikkan spesifisitas selektor atau menyalahgunakan `!important`.

5. **Akselerasi Perangkat Keras (*Compositor-Only Mutations*)**  
   Mengapa transisi animasi yang menggunakan `transform: translateY()` dan `opacity` dapat dieksekusi pada 60/120 FPS tanpa membebani *main thread*, sedangkan animasi berbasis `top`, `margin-top`, atau `height` rentan terhadap *jank* (stuttering)? Jelaskan peran GPU, *Compositor Layer*, dan risiko degradasi memori (*layer explosion*) akibat penggunaan `will-change: transform` yang tidak terkontrol.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Performa Scrolling Terdegradasi Parah pada Enterprise Data Table
*Konteks*: Aplikasi SaaS FinTech menampilkan tabel transaksi berisi 200 baris dengan kalkulasi dinamis. Setiap sel memiliki border, badge status, dan hover tooltip. Pengguna melaporkan bahwa saat melakukan *scrolling* cepat, CPU klien melonjak 100% dan *frame rate* anjlok ke 15 FPS (*extreme jank*). Tim menemukan bahwa selector CSS berikut terpasang secara global:
```css
table.data-table tr:hover * {
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
  outline: 1px solid blue;
}
```
*Pertanyaan Diagnostik*:
1. Analisis mengapa selektor dan properti tersebut memicu beban kalkulasi rendering yang sangat masif di setiap interaksi hover/scroll.
2. Identifikasi tahapan *rendering pipeline* (Layout, Paint, atau Composite) yang dipaksa berjalan terus-menerus.
3. Rancang strategi refaktorisasi CSS untuk mengisolasi mutasi grafis agar tabel mencapai performa stabil 60 FPS saat interaksi.

### Skenario B: Konflik Gaya (*Cascade War*) pada Transisi Migrasi Micro-Frontend
*Konteks*: Perusahaan sedang memigrasikan aplikasi monolitik lama ke arsitektur Micro-Frontend. Tim Anda memuat komponen React baru ke dalam shell aplikasi lama (*legacy*). Aplikasi *legacy* memiliki stylesheet global tanpa metodologi penamaan:
```css
/* Legacy Global CSS */
#app .content div.panel-container > button {
  background-color: #333 !important;
  padding: 8px 12px;
}
```
Komponen baru Anda menggunakan arsitektur modular (`.btn-primary`), namun tampilannya rusak karena *override* dari CSS lama. Seorang engineer junior mengusulkan untuk menulis:
```css
#app .content div.panel-container > button.btn-primary {
  background-color: #0066ff !important;
}
```
*Pertanyaan Diagnostik*:
1. Mengapa pendekatan junior engineer tersebut menciptakan *anti-pattern* (*specificity inflation arms race*) yang berbahaya bagi siklus rilis jangka panjang?
2. Bagaimana cara menyelesaikan konflik cascade ini secara sistematis menggunakan isolasi CSS modern (misalnya `@layer`, BFC, CSS Modules, atau Shadow DOM)?
3. Jelaskan evaluasi *trade-off* dari masing-masing solusi isolasi tersebut jika ditinjau dari kemudahan integrasi dan kompatibilitas sistem lama.

### Skenario C: Arsitektur Layout Design System yang Rapuh (*Rigid Sizing*)
*Konteks*: Design System perusahaan mendefinisikan komponen form input menggunakan ukuran eksplisit absolut:
```css
.input-control {
  width: 360px;
  height: 48px;
  padding: 12px 16px;
  box-sizing: content-box;
}
```
Ketika komponen ini digunakan di dalam *dashboard modal*, *sidebar*, dan tampilan *mobile webview*, form meluap (*overflow*) keluar dari container induknya, teks terpotong (*text clipping*), dan layout berantakan saat font sistem diperbesar oleh preferensi aksesibilitas pengguna (*dynamic type*).
*Pertanyaan Diagnostik*:
1. Audit cacat arsitektur pada spesifikasi kelas `.input-control` di atas yang melanggar prinsip *fluid/defensive design*.
2. Rekonstruksi spesifikasi CSS komponen input tersebut agar responsif terhadap container induknya, adaptif terhadap skala tipografi aksesibilitas, dan anti-overflow.
3. Jelaskan pilihan unit pengukur (`rem`, `ch`, `%`, `min()`, `clamp()`) yang Anda gunakan pada kode rekonstruksi beserta alasan teknisnya.

---

## 4. Chapter Challenge

**Tantangan Praktis: Rekonstruksi High-Performance & Isolated Modal Component**

### Problem
Komponen modal bawaan tim Anda memiliki tiga masalah kritis di lingkungan produksi:
1. Menimpa elemen z-index aplikasi utama secara sporadis karena *stacking context* yang tidak terisolasi.
2. Memicu *Layout Thrashing* dan *Repaint* besar-besaran saat animasi *backdrop* dan *dialog appearance*.
3. Mengalami kebocoran cascade: gaya tombol dan tipografi di dalam modal terpengaruh oleh CSS global aplikasi host.

### Requirements
Buat implementasi komponen modal struktural menggunakan HTML & CSS murni dengan spesifikasi:
1. **Cascade Isolation**: Gunakan fitur `@layer` modern untuk mengisolasi modal ke dalam layer `components.dialog` tanpa memakai satu pun deklarasi `!important`.
2. **Deterministic Stacking Context**: Modal harus membungkus dirinya sendiri dalam *stacking context* independen menggunakan properti modern (misal `isolation: isolate`). Modal harus selalu berada di atas layer aplikasi utama secara terprediksi.
3. **Box-Model Defense**: Terapkan *defensive box model reset* pada seluruh anak elemen di dalam dialog modal. Ukuran modal harus adaptif: maksimal lebar 560px, tetapi memiliki margin pengaman 16px jika dibuka pada layar resolusi kecil (<560px).
4. **Compositor-Only Animations**:
   - Transisi kemunculan *backdrop* (fade-in) dan dialog (scale & slide-up) hanya boleh memicu tahap **Composite**.
   - Dilarang menganimasikan: `top`, `left`, `margin`, `width`, `height`.
   - Gunakan `transform` dan `opacity` dengan kurva bezier performan (`cubic-bezier(0.16, 1, 0.3, 1)`).
5. **No Layout Shift on Scroll Lock**: Buat struktur CSS yang mengantisipasi hilangnya scrollbar pada `<body>` saat modal terbuka (gunakan fallback `scrollbar-gutter: stable`).

### Constraints
- Dilarang menggunakan *framework* atau *library* CSS eksternal (murni native CSS modern).
- Dilarang menggunakan selektor berbasis ID (`#id`). Maksimal bobot spesifisitas per selektor adalah `(0, 2, 0)`.
- Nilai animasi harus tetap menghormati preferensi pengguna via media query `@media (prefers-reduced-motion: reduce)`.

### Expected Output
- File kode CSS terstruktur rapi yang terbagi atas: Reset/Layer Definition, Stacking/Overlay Architecture, Box Model Constraints, dan Hardware-Accelerated Keyframes/Transitions.
- Penjelasan singkat (1-2 paragraf) tentang alur verifikasi bahwa animasi modal tersebut berjalan murni di *Compositor Layer* menggunakan browser DevTools (Performance & Rendering Tab).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme kalkulasi fisik Box Model (`content-box` vs `border-box`) dan implikasinya terhadap dimensi rendering.
- [ ] Aturan pasti terbentuknya *Margin Collapsing* dan cara mengendalikannya melalui pembentukan *Block Formatting Context* (BFC).
- [ ] Algoritma penghitungan CSS Specificity `(Inline, ID, Class, Type)` dan bagaimana Cascade Resolution memprosesnya.
- [ ] Siklus hidup Critical Rendering Path: Parsing, DOM, CSSOM, Render Tree, Reflow/Layout, Repaint, dan Composite.
- [ ] Syarat terbentuknya *Stacking Context* baru (bukan hanya `z-index`, melainkan pemicu properti CSS3 seperti `transform`, `filter`, `opacity`, `isolation`).
- [ ] Perbedaan beban komputasi CPU vs GPU saat menganimasikan geometri layout vs properti komposit.

### Saya tidak perlu menghafal:
- [ ] Tabel lengkap setiap pemicu CSS trigger browser untuk seluruh properti (cukup pahami kategorinya: Layout, Paint, atau Composite melalui referensi *csstriggers.com*).
- [ ] Sintaks *vendor prefix* historis (`-webkit-`, `-moz-`, `-ms-`) yang sudah tidak relevan di browser modern.
- [ ] Nilai spesifisitas absolut desimal dari dokumen spesifikasi lama (cukup kuasai model matriks 4-kolom).

### Saya harus bisa melakukan:
- [ ] Menghitung manual nilai spesifisitas dari selektor kompleks dalam hitungan detik tanpa ragu.
- [ ] Mengidentifikasi dan memperbaiki *Layout Thrashing* (Forced Synchronous Layout) menggunakan Chrome DevTools Performance panel.
- [ ] Mengonfigurasi isolasi CSS menggunakan `@layer` untuk mencegah *specificity conflict* pada aplikasi skala besar.
- [ ] Mencegah kebocoran visual layout menggunakan defensive box model dan modern CSS units (`clamp()`, `min()`, `max()`).
- [ ] Menganalisis *Paint Flashing* dan *Layer Borders* pada browser untuk memverifikasi akselerasi perangkat keras (*GPU acceleration*).