# BAB 02: Quiz, Challenge, & Knowledge Check
**Visual Formatting Model, Box Dynamics, dan Paint Profiling**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Mekanisme Margin Collapsing dan Algoritma Resolusinya**
   Jelaskan secara deterministik bagaimana browser menyelesaikan *margin collapsing* ketika terjadi pertemuan antara:
   * Dua margin positif.
   * Satu margin positif dan satu margin negatif.
   * Dua margin negatif yang bersarang (*nested margins*).
   Sebutkan minimal 4 kondisi spesifik dalam spesifikasi CSS di mana *margin collapsing* **dibatalkan secara otomatis**.

2. **Extrinsic vs Intrinsic Sizing dalam Kaitannya dengan Box-Sizing**
   Jelaskan perbedaan fundamental bagaimana browser engine (misalnya Blink atau Gecko) menghitung dimensi akhir dari sebuah elemen ketika menggunakan `box-sizing: content-box` versus `box-sizing: border-box`. Bagaimana kedua model ini memengaruhi kalkulasi *intrinsic sizing keywords* (`min-content`, `max-content`, dan `fit-content`)?

3. **Anatomi dan Trigger Pembentukan Stacking Context**
   *Stacking Context* bukan sekadar urutan `z-index`. Jelaskan apa yang terjadi pada pohon render (*Render Tree*) saat sebuah *Stacking Context* baru terbentuk. Sebutkan minimal 5 properti CSS modern (di luar kombinasi `position: absolute/relative` + `z-index` integer) yang memicu pembentukan *Stacking Context* independen!

4. **Siklus Hidup Rendering Browser: Layout vs Paint vs Composite**
   Uraikan tahapan eksekusi pada pipeline rendering browser modern (Blink/V8):
   $$\text{DOM + CSSOM} \longrightarrow \text{Layout (Reflow)} \longrightarrow \text{Paint} \longrightarrow \text{Raster} \longrightarrow \text{Composite}$$
   Jelaskan mengapa mutasi properti seperti `left`/`top` memaksa browser mengeksekusi pipeline dari tahap Layout, sedangkan mutasi `transform: translate()` dapat langsung meloncat ke tahap Composite. Apa implikasi strukturalnya terhadap thread utama (*Main Thread*)?

5. **Perbedaan Formatting Context: BFC, IFC, dan FFC**
   Bandingkan karakteristik teknis antara *Block Formatting Context* (BFC), *Inline Formatting Context* (IFC), dan *Flex Formatting Context* (FFC). Bagaimana batas (*boundary*) dari sebuah BFC mencegah kebocoran elemen *float* dan margin eksternal?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Layer Squashing dan GPU Memory Explosion**
   Pada arsitektur Compositor browser, apa yang dimaksud dengan *Layer Squashing* dan *Implicit Compositing*? Jelaskan skenario patologis di mana promosi sebuah elemen menjadi *Composited Layer* via `will-change: transform` justru memicu pembengkakan alokasi memori VRAM GPU secara masif (*compositor memory explosion*) dan melumpuhkan perangkat *low-end*.

2. **Isolasi Stacking Context Menggunakan `isolation: isolate`**
   Sebelum hadirnya CSS `isolation: isolate`, para engineer sering menggunakan *hack* seperti `transform: translateZ(0)` atau `position: relative; z-index: 0` untuk membuat *stacking context boundary*. Mengapa *hack* berbasis `transform` berisiko merusak rendering teks atau komponen posisi `fixed` di dalamnya, dan bagaimana `isolation: isolate` menyelesaikan problem ini secara spesifik pada level spesifikasi CSS Compositing and Blending?

3. **Problem "Mysterious Gap" pada Inline-Block dan Anatomi IFC**
   Sebuah elemen `<div>` membungkus sebuah tag `<img>` atau elemen `<div style="display: inline-block">`. Secara visual, terdapat celah kosong sebesar ~3px hingga 5px di bagian bawah elemen tersebut meskipun `margin: 0` dan `padding: 0`. Jelaskan akar masalah internal browser ini ditinjau dari konsep *strut*, *baseline metric*, *x-height*, dan *line-box* pada Inline Formatting Context (IFC), serta tuliskan 3 cara mutlak untuk mengeliminasinya.

4. **Subpixel Antialiasing dan Transform Blurriness**
   Ketika elemen dipindahkan menggunakan `transform: translate(x, y)`, sering kali teks atau aset SVG di dalamnya tampak buram (*blurry/anti-aliased smearing*). Jelaskan penyebab mekanis masalah ini dalam kaitannya dengan *Device Pixel Ratio* (DPR), snapping ke grid piksel fisik, dan strategi compositing rasterization browser!

5. **Paint Flashing dan Invalidation Rect Profiling**
   Saat melakukan audit performa menggunakan panel **Rendering -> Paint Flashing** di Chrome DevTools, sebuah area hijau besar berkedip terus-menerus setiap kali kursor digerakkan di atas komponen visual. Langkah-langkah diagnostik apa yang harus Anda lakukan di DevTools (Performance Panel & Layers Panel) untuk menemukan *culprit* properti CSS yang memicu invalidasi paint rect tersebut?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Dropped Frames pada Virtualized Financial Ledger
* **Konteks:** Sebuah aplikasi web *fintech trading* menampilkan buku pesanan (*Order Book*) real-time berkecepatan tinggi (30–60 pembaruan per detik via WebSocket) menggunakan teknik *virtualized list*. Setiap baris berisi data angka, grafik bar mikro, dan *status badge*.
* **Gejala:** Pengguna melaporkan *frame drops* parah (turun ke 15–20 FPS) dan CPU usage melonjak hingga 100% pada *Renderer Process*. Profiling via DevTools menunjukkan waktu *Paint* dan *Raster* sangat dominan (memakan waktu ~28ms per frame).
* **Temuan Awal:** Setiap baris memiliki CSS `box-shadow: 0 2px 4px rgba(0,0,0,0.1)`, `border-radius: 4px`, dan warna latar belakang dinamis yang dianimasikan menggunakan transisi `background-color 0.2s ease`.
* **Pertanyaan Diagnostik:**
  1. Identifikasi mekanisme rendering yang menjadi bottleneck utama dan jelaskan mengapa kombinasi `border-radius` + `box-shadow` + perubahan `background-color` secara periodik membunuh performa *Paint Pipeline*.
  2. Rancang strategi refaktorisasi arsitektur CSS untuk mengisolasi atau mengeliminasi proses *repaint* tersebut agar pipeline rendering kembali berjalan stabil di 60 FPS tanpa mengorbankan estetika visual antarmuka secara drastis!

### Skenario B: Z-Index Collision & Stacking Context Trapping pada Micro-Frontend
* **Konteks:** Tim Enterprise Core mengintegrasikan modul *Notification Toast* global (z-index diset ke `999999`) dan sebuah *Sticky Header* global. Salah satu tim produk mengunggah Micro-Frontend (MFE) baru yang memiliki komponen *Modal Dialog*.
* **Gejala:** Komponen modal dialog tim produk secara visual selalu tertutup oleh *Sticky Header* dan komponen dashboard lainnya, meskipun modal tersebut telah disetel memiliki `z-index: 2147483647` (nilai integer 32-bit maksimal).
* **Temuan Awal:** Di level DOM tree, elemen leluhur pembungkus MFE memiliki properti CSS berikut:
  ```css
  .mfe-container {
    opacity: 0.999;
    filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1));
    contain: layout;
  }
  ```
* **Pertanyaan Diagnostik:**
  1. Mengapa nilai `z-index` yang bernilai maksimal tetap gagal mengangkat modal ke atas Sticky Header? Bedah hierarki pohon Stacking Context yang terbentuk!
  2. Solusi arsitektural apa yang harus diimplementasikan? Berikan analisis pro dan kontra antara pendekatan *CSS architectural restructuring* (memperbaiki stacking contexts) vs penggunaan native DOM *Top-Layer API* (seperti `<dialog>` atau Popover API).

### Skenario C: Subpixel Layout Shift & Jitter pada Fluid Responsive Grid
* **Konteks:** Sebuah platform e-commerce multi-vendor menggunakan CSS Grid modular dengan unit pecahan (`1fr`) yang dipadukan dengan perhitungan fungsi `calc()` dan persentase untuk menyusun grid kartu produk.
* **Gejala:** Pada resolusi layar spesifik (terutama saat rasio scaling OS diatur ke 125% atau 150% pada layar HiDPI/Retina), layout kartu produk mengalami *jitter* (getaran visual 1-pixel) saat ukuran layar di-*resize* atau saat scroll. Beberapa kartu terdorong ke bawah secara acak dan border pembatas 1px tampak hilang-timbul secara bergantian.
* **Pertanyaan Diagnostik:**
  1. Analisis bagaimana floating-point rounding error terjadi di dalam layout engine browser saat mengonversi CSS pixels (`px`) menjadi physical device pixels pada layar non-integer scaling factor.
  2. Bagaimana Anda merancang sistem box constraints dan border rendering (misalnya: transisi ke `box-shadow: inset` atau `outline`, kalkulasi minmax, dan penggunaan `gap`) untuk memastikan layout deterministik tahan terhadap *subpixel truncation*?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance GPU-Accelerated Sliding HUD Card

#### Problem Statement
Sebuah tim pengembang aplikasi navigasi taktis berbasis web membutuhkan komponen **HUD (Heads-Up Display) Telemetry Card** yang dapat ditarik (*swipe/slide*) dari tepi bawah layar, disertai indikator detak (*Pulse Beacon*) status jaringan yang berdenyut terus-menerus. Implementasi sebelumnya dibuat secara naif menggunakan manipulasi `bottom`, `box-shadow` berulang pada `@keyframes`, dan elemen yang memicu *invalidation storms* di seluruh viewport, menghabiskan baterai dan menyebabkan animasi tersendat (*jank*).

#### Requirements
1. **Zero Layout Shifts:** Modul kartu HUD dapat digeser naik-turun (state collapsed: tinggi tampak 60px; state expanded: tinggi 400px) tanpa boleh memicu Layout/Reflow sama sekali. Kalkulasi wajib diselesaikan 100% pada Compositor Thread.
2. **Infinite Pulse Beacon:** Buat indikator visual sinyal (lingkaran 12px) yang berdenyut membesar dan memudar tanpa memicu tahapan *Paint* setelah frame pertama diinisialisasi.
3. **Stacking Context Isolation:** Seluruh styling kartu HUD harus dienkapsulasi sehingga properti `z-index` internal di dalam kartu (misal: tooltip, sub-menu) tidak bocor keluar atau terdistorsi oleh kontainer di luar modul.
4. **DevTools Profiling Validation:** Hasil audit menggunakan Chrome DevTools harus menunjukkan:
   * **Rendering Tab:** Tidak ada warna hijau (*Paint Flashing*) yang terdeteksi saat kartu bergeser ataupun saat beacon berdenyut.
   * **Performance Tab:** Frame rate stabil pada 60/120 FPS tanpa ada blok tugas bertingkat ungu (*Layout*) atau hijau (*Paint*) selama animasi berlangsung.

#### Constraints
* **Dilarang keras** menggunakan properti: `top`, `bottom`, `left`, `right`, `width`, `height`, dan `margin` untuk menggerakkan atau menganimasikan ukuran visual kartu.
* **Dilarang keras** menganimasikan `box-shadow` untuk efek denyut (*pulse*).
* Wajib menggunakan modern CSS (misalnya: `transform`, `opacity`, `will-change`, `contain`, `isolation`).
* Implementasi harus murni CSS untuk bagian animasi (JavaScript hanya diperbolehkan untuk toggle state class / attribute).

#### Expected Output
1. Blok kode CSS yang telah dioptimasi penuh sesuai spesifikasi di atas beserta markup HTML semantik.
2. Penjelasan arsitektur teknis singkat (1-2 paragraf) yang membuktikan bagaimana pipeline rendering (Layout -> Paint -> Composite) ditangani oleh engine browser untuk kode tersebut.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Aturan matematis margin collapsing pada elemen selevel (*siblings*), elemen bersarang (*parent-child*), dan blok kosong (*empty blocks*).
- [ ] Algoritma penentuan ukuran kotak: perbedaan `content-box`, `border-box`, serta resolusi kata kunci sizing (`min-content`, `max-content`, `fit-content`).
- [ ] 7+ pemicu terbentuknya *Stacking Context* modern di luar manipulasi `z-index` tradisional.
- [ ] Arsitektur internal browser engine: peran Main Thread vs Compositor Thread vs Raster Worker Threads.
- [ ] Perbedaan properti CSS pemicu Layout (Reflow), Paint, dan Composite.
- [ ] Konsep pembentukan BFC (Block Formatting Context) dan kegunaannya dalam isolasi layout.
- [ ] Dampak negatif *Layer Promotion Overuse* (Memory thrashing, VRAM bloat, dan layer squashing).
- [ ] Prinsip kerja *subpixel rendering* dan dampaknya terhadap fractional DPR (1.25, 1.5, dsb).

### Saya tidak perlu menghafal:
- [ ] Seluruh daftar 20+ properti spesifik SVG yang membentuk Stacking Context secara mandiri (cukup pahami konsep dasarnya dan cek dokumentasi bila menangani SVG).
- [ ] String nama vendor-prefix internal engine browser lawas (`-webkit-`, `-moz-`, `-ms-`) yang sudah usang dalam konteks CSS modern.
- [ ] Angka piksel presisi dari baseline metrik font sistem tertentu (cukup pahami mekanisme alokasi IFC dan konsep strut).

### Saya harus bisa melakukan:
- [ ] Membaca dan menganalisis laporan **Chrome DevTools Performance Panel** untuk mendeteksi *Long Tasks* yang diakibatkan oleh Layout and Paint storms.
- [ ] Memanfaatkan tab **Rendering (Paint Flashing, Layout Shift Regions, Layer Borders)** untuk memvalidasi efisiensi animasi.
- [ ] Menggunakan tab **Layers** di Chrome DevTools untuk menginspeksi alokasi memori kompositor, alasan promosi layer (*Compositing Reasons*), dan squashing issues.
- [ ] Menulis arsitektur CSS animasi bebas jank (*Zero-Paint Animations*) menggunakan kombinasi `transform` dan `opacity`.
- [ ] Mengatasi masalah layout tersembunyi seperti celah bawah inline-block image dan margin collapse tanpa efek samping merusak layout global.
- [ ] Mengisolasi komponen micro-frontend dari kebocoran konteks rendering menggunakan properti `contain` dan `isolation`.