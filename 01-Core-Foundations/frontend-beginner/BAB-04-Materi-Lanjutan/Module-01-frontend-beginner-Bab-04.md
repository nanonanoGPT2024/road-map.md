## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: FEB-01-04
* **Jalur Kurikulum**: Frontend Development Track
* **Kategori**: 01-Core-Foundations
* **Nama Modul**: Sistem Tata Letak Modern: Flexbox & CSS Grid Multi-Dimensi
* **Tingkat Kesulitan**: Beginner to Intermediate
* **Prasyarat**:
  * FEB-01-01: Arsitektur Dokumen Semantik & Struktur HTML5
  * FEB-01-02: Anatomi CSS & CSS Object Model (CSSOM)
  * FEB-01-03: CSS Box Model & Normal Flow Mechanics
* **Estimasi Waktu Belajar**: 8 Jam Belajar Terstruktur (4 Jam Teori & Analisis, 4 Jam Praktikum Hands-on)
* **Target Peran**: Frontend Software Engineer, UI/UX Implementation Specialist, Web Layout Architect

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta ajar diharapkan memiliki kemampuan komprehensif untuk:

1. **Menganalisis Perbedaan Paradigma (C4)**: Membedakan secara fundamental kalkulasi layout berbasis satu dimensi (Flexbox) dan dua dimensi (CSS Grid) untuk menentukan primitif tata letak yang tepat sesuai kebutuhan UI.
2. **Menguasai Distribusi Ruang Flexbox (C3, C4)**: Menghitung secara matematis alokasi ruang kosong (*positive/negative free space*) menggunakan formula `flex-grow`, `flex-shrink`, dan `flex-basis`.
3. **Mengonfigurasi Grid Tracks & Areas (C3)**: Merancang struktur layout dua dimensi menggunakan kombinasi satuan fraksional (`fr`), fungsi matematika intrinsik (`minmax()`, `fit-content()`), serta template penamaan area (`grid-template-areas`).
4. **Menerapkan Pola Responsif Tanpa Media Query (C3, C5)**: Mengimplementasikan fluid grid system menggunakan teknik auto-placement `repeat(auto-fit / auto-fill, minmax(...))` untuk menghasilkan antarmuka yang adaptif secara intrinsik.
5. **Memecahkan Masalah Defensive Layout (C4, C5)**: Mengidentifikasi dan memperbaiki anomali perenderan seperti *flex child minimum sizing overflow* menggunakan properti `min-width: 0` serta tumpang tindih elemen (*z-index contexts*) pada grid cells.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
Sistem Tata Letak Modern (Modern Layout Mechanics)
 ├── 1D Context: Flexible Box Module (Flexbox)
 │    ├── Flex Container
 │    │    ├── Axis Definition (flex-direction: row | column)
 │    │    ├── Multi-line Wrapping (flex-wrap: nowrap | wrap | wrap-reverse)
 │    │    ├── Main-Axis Distribution (justify-content)
 │    │    └── Cross-Axis Alignment (align-items, align-content)
 │    └── Flex Items
 │         ├── Sizing Flexibility (flex: <grow> <shrink> <basis>)
 │         ├── Self Alignment (align-self)
 │         └── Visual Reordering (order)
 │
 ├── 2D Context: CSS Grid Layout
 │    ├── Grid Container
 │    │    ├── Track Definitions (grid-template-columns, grid-template-rows)
 │    │    ├── Fractional Unit Allocation (1fr, auto, minmax())
 │    │    ├── Explicit vs Implicit Grid (grid-auto-rows, grid-auto-flow)
 │    │    └── Structural Gaps (gap, row-gap, column-gap)
 │    └── Grid Items
 │         ├── Coordinate Placement (grid-column: start / end, grid-row)
 │         ├── Named Grid Areas (grid-template-areas, grid-area)
 │         └── Self-Alignment Matrix (justify-self, align-self, place-self)
 │
 └── Hybrid Architectural Integration
      ├── Content-Driven (Flexbox) vs Layout-Driven (Grid)
      ├── Subgrid Mechanics (grid-template-*: subgrid)
      └── Intrinsic Sizing & Defensive Techniques (min-width: 0, auto-fit vs auto-fill)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sebelum standardisasi Flexbox (2012) dan CSS Grid (2017), rekayasa tata letak web bergantung pada manipulasi mekanisme yang awalnya tidak dirancang untuk UI aplikasi modern:
* Penggunaan `<table>` struktural yang merusak pohon aksesibilitas (*accessibility tree*) dan performa *parsing*.
* Pemanfaatan properti `float` yang menuntut teknik *hacky* seperti *clearfix hacks* (`clear: both`), yang sering memicu *margin collapsing* anomali dan hilangnya konteks tinggi kontainer.
* Manipulasi `display: inline-block` yang secara inheren menyisipkan spasi putih fisik (*whitespace characters*) dari sintaks HTML ke dalam rendering visual.

Flexbox dan CSS Grid diciptakan oleh W3C untuk mengubah manipulasi dokumen berbasis teks menjadi **rekayasa antarmuka deterministik**. 

Menguasai kedua modul ini penting karena:
1. **Prediktabilitas Algoritmik**: Layout engine browser mengalokasikan piksel dengan aturan pasti, meminimalkan *layout shift* (CLS) dan *paint overhead*.
2. **Efisiensi Kode & Maintainability**: Menghilangkan ribuan baris CSS berbasis *negative-margin wrappers*, framework CSS monolitik yang berat, dan perhitungan kalkulasi JavaScript yang boros memori (*DOM-measurement thrashing*).
3. **Desain Intrinsik Multi-Device**: Perangkat modern hadir dalam rentang viewport variabel dari jam tangan pintar hingga monitor ultrawide. Pendekatan layout modern memungkinkan komponen merespons ketersediaan ruang fisik komponen itu sendiri, bukan hanya ukuran layar browser.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. CSS Flexible Box Module (Flexbox)
Flexbox adalah sistem tata letak **satu dimensi (one-dimensional)**. Artinya, Flexbox mengelola tata letak elemen hanya pada satu sumbu dalam satu waktu: baik secara horizontal (*row*) atau vertikal (*column*). Flexbox berorientasi pada konten (*content-driven*), di mana ukuran elemen anak menentukan bagaimana ruang dalam kontainer dibagi secara dinamis.

### 2. CSS Grid Layout
CSS Grid adalah sistem tata letak **dua dimensi (two-dimensional)**. Grid dirancang untuk membagi kontainer menjadi baris (*rows*) dan kolom (*columns*) secara simultan. Grid berorientasi pada tata letak (*layout-driven*), di mana struktur didefinisikan terlebih dahulu pada kontainer, dan elemen anak ditempatkan ke dalam sel atau area yang ditentukan oleh koordinat garis-garis grid.

### 3. Matriks Perbandingan Karakteristik Teknis

| Parameter | CSS Flexible Box (Flexbox) | CSS Grid Layout |
| :--- | :--- | :--- |
| **Dimensi** | 1D (Baris *atau* Kolom) | 2D (Baris *dan* Kolom secara bersamaan) |
| **Pendekatan Desain** | Konten menentukan layout (*Content-out*) | Layout menentukan posisi konten (*Layout-in*) |
| **Sumbu Acuan** | Main Axis & Cross Axis | Inline Axis & Block Axis |
| **Perataan Multi-Elemen** | Terbatas pada baris aktif (tidak sinkron lintas baris) | Terkunci pada garis jalur (*tracks*) baris dan kolom yang kaku |
| **Penggunaan Ideal** | Komponen navigasi, form inputs, grouping tombol, kartu UI | Makro-layout halaman, galeri foto dinamis, dashboard modular |

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Algoritma Perhitungan Flexbox
Ketika kontainer dideklarasikan sebagai `display: flex`, browser membentuk konteks pemformatan fleksibel (*flex formatting context*). Distribusi ukuran elemen dihitung melalui tiga properti utama: `flex-basis`, `flex-grow`, dan `flex-shrink`.

1. **Penentuan Hypothetical Size**:
   Browser memeriksa `flex-basis`. Jika bernilai `auto`, browser membaca ukuran intrinsik konten atau properti `width`/`height`. Ukuran ini disebut *hypothetical item size*.
2. **Kalkulasi Remaining Free Space ($W_{free}$)**:
   $$W_{free} = W_{container} - \sum (W_{hypothetical\_item} + \text{margins} + \text{borders} + \text{paddings})$$
3. **Distribusi Positif ($W_{free} > 0$)**:
   Jika kontainer memiliki ruang sisa, browser membaca properti `flex-grow`. Porsi pertambahan setiap item ($G_{item}$) dihitung proporsional terhadap total bobot `flex-grow`:
   $$Porsi_{item} = \frac{flex\_grow_{item}}{\sum flex\_grow} \times W_{free}$$
   $$\text{Ukuran Akhir} = W_{basis} + Porsi_{item}$$
4. **Distribusi Negatif / Penyusutan ($W_{free} < 0$)**:
   Jika total ukuran item melebihi kontainer, browser memotong ukuran elemen berdasarkan proporsi `flex-shrink` dikalikan ukuran basis aslinya:
   $$Porsi\_Penyusutan_{item} = \frac{flex\_shrink_{item} \times W_{basis}}{\sum (flex\_shrink \times W_{basis})} \times |W_{free}|$$
   $$\text{Ukuran Akhir} = W_{basis} - Porsi\_Penyusutan_{item}$$

### 2. Algoritma Konstruksi CSS Grid
CSS Grid membagi kanvas render menjadi koordinat diskrit:
1. **Grid Tracks**: Ruang antara dua garis grid paralel yang berdekatan (membentuk baris atau kolom).
2. **The `fr` Unit (Fractional)**: Unit `1fr` mewakili satu fraksi dari ruang yang belum dialokasikan (*unallocated free space*) setelah semua elemen bernilai absolut (`px`, `rem`) atau intrinsik (`auto`, `min-content`) terpenuhi.
3. **Auto-Placement Algorithm**: Browser membaca `grid-auto-flow` (default: `row`). Item anak tanpa koordinat manual (`grid-column` / `grid-row`) akan dialokasikan secara sekuensial ke dalam sel kosong berikutnya. Jika mode `dense` diaktifkan (`grid-auto-flow: row dense`), browser memindai celah kosong di awal grid untuk menempatkan item kecil yang muncul kemudian di DOM.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Anatomi Sumbu Flexbox (Flexbox Axes)

```
flex-direction: row;
+========================= MAIN AXIS (Horizontal) ==========================>
| [Main-Start]                                                  [Main-End]  |
|                                                                           |
|   +-------------------+  (Gap)  +-------------------+                     |
|   | Flex Item 1       | <-----> | Flex Item 2       |                     |
|   |                   |         |                   |                     |
|   +-------------------+         |                   |                     |
|                                 |                   |                     |
|                                 +-------------------+                     |
| [Cross-Start]                                                             |
|                                                                           |
V CROSS AXIS (Vertical)                                                     |
|                                                                           |
| [Cross-End]                                                               |
+===========================================================================+
```

### 2. Anatomi Matriks CSS Grid

```
       Garis Kolom 1       Garis Kolom 2       Garis Kolom 3       Garis Kolom 4
             |                   |                   |                   |
             V                   V                   V                   V
Garis      +-------------------+-------+-------------------+-------+---+
Baris 1 -> | Grid Cell (1,1)   |  GAP  | Grid Cell (1,2)   |  GAP  |   |
           |                   |       |                   |       |   |
           +-------------------+-------+-------------------+-------+   | <-- Grid Track
Garis      | <===== GAP =====> |       | <===== GAP =====> |       |   |     (Baris 1)
           +-------------------+-------+-------------------+-------+---+
Baris 2 -> | Grid Area Gabungan (spanning 2 columns)       |  GAP  |   |
           | [grid-column: 1 / 3]                          |       |   |
           +-------------------+---------------------------+-------+   | <-- Grid Track
Garis      | <===== GAP =====> |                           |       |   |     (Baris 2)
           +-------------------+---------------------------+-------+---+
Baris 3 -> |                   |                           |       |   |
           +-------------------+---------------------------+-------+---+
           ^                   ^                           ^
           |--- Grid Track ----|                           |-- Track --|
               (Kolom 1)                                     (Kolom 3)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

### 1. Flexbox: Pemusatan Sempurna Sumbu Ganda (Centering Problem)

Solusi klasik untuk masalah historis sentralisasi elemen secara vertikal dan horizontal:

```html
<div class="flex-center-container">
  <div class="centered-box">Pusat Sempurna</div>
</div>
```

```css
.flex-center-container {
  display: flex;
  justify-content: center; /* Meratakan secara horizontal pada Main Axis */
  align-items: center;     /* Meratakan secara vertikal pada Cross Axis */
  height: 200px;
  background-color: #0f172a;
  border-radius: 8px;
}

.centered-box {
  padding: 1rem 2rem;
  background-color: #38bdf8;
  color: #0f172a;
  font-weight: bold;
  border-radius: 4px;
}
```

### 2. CSS Grid: Tata Letak 3 Kolom Responsif

Membagi kontainer menjadi 3 kolom yang identik tanpa perhitungan persentase manual:

```html
<div class="simple-grid">
  <article class="grid-item">Kolom 1</article>
  <article class="grid-item">Kolom 2</article>
  <article class="grid-item">Kolom 3</article>
</div>
```

```css
.simple-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr); /* 3 jalur dengan fraksi sama */
  gap: 1.5rem;                           /* Menangani jarak tanpa margin-collapse */
  background-color: #1e293b;
  padding: 1.5rem;
}

.grid-item {
  background-color: #334155;
  color: #f8fafc;
  padding: 2rem;
  text-align: center;
  border-radius: 6px;
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Implementasi arsitektur nyata: **Dashboard E-Commerce Product Listing**. Kasus ini menggabungkan CSS Grid untuk makro-layout katalog produk multi-kolom yang adaptif dan Flexbox untuk mikro-komponen kartu (*card*) individual agar tombol tindakan selalu sejajar di dasar kartu terlepas dari variasi panjang teks deskripsi.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sistem Katalog Modern</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>

  <main class="catalog-shell">
    <header class="catalog-header">
      <h2>Katalog Produk Pilihan</h2>
      <span class="badge">Sistem Grid & Flex Terintegrasi</span>
    </header>

    <!-- GRID: Mengontrol Makro-Layout Dua Dimensi Secara Intrinsik -->
    <section class="product-grid">
      
      <!-- ITEM 1 -->
      <article class="product-card">
        <div class="product-image-placeholder">Asset 1</div>
        <!-- FLEX: Mengontrol Struktur Satu Dimensi Kartu -->
        <div class="product-content">
          <h3 class="product-title">Mechanical Keyboard Custom TKL</h3>
          <p class="product-description">
            Switch linear lubed dengan gasket mount dan konektivitas tri-mode wireless latensi rendah.
          </p>
          <div class="product-footer">
            <span class="product-price">Rp 1.499.000</span>
            <button class="buy-button">Beli</button>
          </div>
        </div>
      </article>

      <!-- ITEM 2: Deskripsi Sangat Pendek (Uji Fleksibilitas Tinggi) -->
      <article class="product-card">
        <div class="product-image-placeholder">Asset 2</div>
        <div class="product-content">
          <h3 class="product-title">Deskmat XL Minimalis</h3>
          <p class="product-description">Kain jacquard tahan air.</p>
          <div class="product-footer">
            <span class="product-price">Rp 250.000</span>
            <button class="buy-button">Beli</button>
          </div>
        </div>
      </article>

      <!-- ITEM 3: Deskripsi Sangat Panjang (Uji Flex-Grow Pusher) -->
      <article class="product-card">
        <div class="product-image-placeholder">Asset 3</div>
        <div class="product-content">
          <h3 class="product-title">Ergonomic Mouse Vertikal Nirkabel</h3>
          <p class="product-description">
            Sensor optik presisi 4000 DPI dengan sudut 57 derajat natural untuk mengurangi ketegangan otot pergelangan tangan pada jam kerja panjang. Baterai tahan 3 bulan.
          </p>
          <div class="product-footer">
            <span class="product-price">Rp 820.000</span>
            <button class="buy-button">Beli</button>
          </div>
        </div>
      </article>

    </section>
  </main>

</body>
</html>
```

```css
/* style.css */

/* Reset Dasar */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background-color: #090d16;
  color: #f1f5f9;
  padding: 2rem;
  line-height: 1.5;
}

.catalog-shell {
  max-width: 1200px;
  margin: 0 auto;
}

.catalog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  border-bottom: 1px solid #1e293b;
  padding-bottom: 1rem;
}

.badge {
  background-color: #1e293b;
  color: #38bdf8;
  font-size: 0.875rem;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  border: 1px solid #38bdf8;
}

/* =====================================================================
   MAKRO-LAYOUT: CSS GRID
   Penggunaan auto-fit & minmax menghasilkan layout responsif murni
   tanpa membutuhkan satu pun breakpoint @media query!
   ===================================================================== */
.product-grid {
  display: grid;
  /* Kolom minimal 280px, maksimal mengisi sisa ruang (1fr) */
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
  align-items: stretch; /* Memaksa semua kartu dalam satu baris sama tinggi */
}

/* =====================================================================
   MIKRO-LAYOUT: FLEXBOX PADA KARTU
   Menjamin tombol checkout selalu berada persis di bagian dasar kartu
   ===================================================================== */
.product-card {
  background-color: #111827;
  border: 1px solid #1f2937;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column; /* Mengubah Main Axis menjadi vertikal */
}

.product-image-placeholder {
  height: 180px;
  background-color: #1e293b;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  font-weight: bold;
}

.product-content {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  flex-grow: 1; /* Mengisi sisa ruang kosong vertikal di kartu */
}

.product-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: #f8fafc;
}

.product-description {
  font-size: 0.875rem;
  color: #94a3b8;
  margin-bottom: 1.25rem;
  
  /* flex-grow: 1 di sini bertindak sebagai 'pusher'. Elemen ini akan menyerap
     seluruh ruang kosong vertikal berlebih, mendorong .product-footer
     ke titik paling dasar kartu secara deterministik. */
  flex-grow: 1; 
}

.product-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 1rem;
  border-top: 1px solid #1f2937;
}

.product-price {
  font-size: 1.1rem;
  font-weight: 700;
  color: #10b981;
}

.buy-button {
  background-color: #2563eb;
  color: #ffffff;
  border: none;
  padding: 0.5rem 1.25rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  transition: background-color 0.2s ease;
}

.buy-button:hover {
  background-color: #1d4ed8;
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Memilih antara CSS Grid dan Flexbox bukan perihal "mana teknologi yang lebih baru", melainkan evaluasi matematis terhadap batasan sistem rendering browser:

| Skenario Desain | Rekomendasi Mesin | Alasan Teknis & Trade-off |
| :--- | :--- | :--- |
| **Penyelarasan Komponen 2 Arah** | CSS Grid | Flexbox tidak mampu menyelaraskan elemen anak dari baris ke-2 dengan elemen anak di baris ke-1 jika jumlah elemen tidak seimbang. Grid mengunci relasi ini pada level *track registry*. |
| **Distribusi Berdasarkan Ukuran Konten** | Flexbox | Flexbox menghitung ukuran berbasis konten intrinsik teks/gambar (`content-driven`). Grid memaksa konten mengikuti batas sel (*rigidity*), yang bisa menyebabkan *overflow* jika tidak disiapkan dengan `minmax`. |
| **Performa Render (Reflow/Layout Phase)** | Flexbox (Umumnya Sedikit Lebih Cepat) | Pohon Grid membutuhkan dua lintasan kalkulasi matematis (baris dan kolom saling berkorelasi) sebelum browser dapat mengeksekusi proses *painting*. Flexbox hanya menghitung satu dimensi linier. Perbedaan ini menjadi signifikan pada daftar DOM ribuan baris. |
| **Desain Adaptif Tanpa Media Query** | CSS Grid | Pola `repeat(auto-fit, minmax(N, 1fr))` tidak dapat direplikasi pada Flexbox murni dengan kestabilan visual yang setara tanpa injeksi JavaScript. |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Properti `gap` Eksklusif**: Hindari penggunaan `margin` pada item anak untuk membuat jarak antar grid/flex items. Properti `gap`, `row-gap`, dan `column-gap` menangani kalkulasi pemisahan tanpa menimbulkan efek samping margin berlebih pada batas kontainer terluar.
2. **Defensive Min-Sizing pada Flex Items**: Secara spesifikasi, elemen flex memiliki default `min-width: auto;` dan `min-height: auto;`. Hal ini mencegah item menyusut lebih kecil dari ukuran teks kontennya, memicu *overflow horizontal* pada layar kecil. Selalu terapkan:
   ```css
   .flex-child {
     min-width: 0; /* Menimpa batasan minimum intrinsik */
   }
   ```
3. **Pahami Perbedaan `auto-fill` vs `auto-fit`**:
   * `auto-fill`: Membuat *track* kosong sebanyak mungkin yang muat di dalam kontainer, meskipun track tersebut tidak memiliki konten DOM.
   * `auto-fit`: Menghapus track kosong yang tidak terpakai dan merentangkan (*stretch*) track yang memiliki konten untuk memenuhi seluruh ruang kontainer yang tersedia.
4. **Prioritaskan Penamaan Area untuk UI Kompleks**: Untuk makro-layout halaman, gunakan `grid-template-areas`. Ini membuat kode CSS dapat dibaca layaknya representasi visual ASCII:
   ```css
   .app-layout {
     display: grid;
     grid-template-areas:
       "header header"
       "sidebar main"
       "footer footer";
   }
   ```

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Menghancurkan Aspek Rasio Gambar di Flex Container
* **Kesalahan**: Menyematkan elemen `<img>` langsung sebagai anak Flexbox tanpa pembungkus atau properti alignment yang benar, menyebabkan gambar gepeng/terdistorsi secara vertikal karena nilai default `align-items: stretch`.
* **Solusi**: Terapkan `align-self: flex-start` atau bungkus elemen gambar di dalam kontainer `<div>` netral dengan rasio pasti (`aspect-ratio`).

### 2. Menggunakan `100%` alih-alih `1fr` pada Grid Columns
* **Kesalahan**:
  ```css
  /* SALAH: Memaksa overflow horizontal */
  grid-template-columns: repeat(3, 33.33%);
  gap: 20px; /* 33.33% * 3 + gap > 100% lebar kontainer! */
  ```
* **Solusi**:
  ```css
  /* BENAR: Algoritma Grid memperhitungkan gap sebelum membagi 1fr */
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  ```

### 3. Kebingungan antara `justify-items` dan `justify-content`
* **Miskonsepsi**: Menggunakan `justify-items` pada Flexbox (di mana properti ini tidak didukung pada sumbu utama flexbox) atau tertukar fungsi antara meratakan sel grid vs meratakan seluruh matriks grid.
* **Kaidah Tetap**:
  * Properti berakhiran `-content` (`justify-content`, `align-content`): Mengatur distribusi **seluruh struktur track/items** terhadap kontainernya.
  * Properti berakhiran `-items` (`justify-items`, `align-items`): Mengatur penempatan **konten di dalam sel atau cross-axis** masing-masing item.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1 (Tingkat Dasar): Navbar Responsif dengan Flexbox
* **Tugas**: Bangun sebuah bar navigasi horizontal.
* **Spesifikasi**:
  1. Logo aplikasi berada di sisi kiri paling ujung.
  2. Daftar menu (`Home`, `Features`, `Pricing`) berada di tengah.
  3. Tombol `Login` dan `Sign Up` berada di sisi kanan paling ujung.
  4. Semua item harus sejajar vertikal persis di tengah tinggi navbar (tinggi navbar: `64px`).
* **Petunjuk**: Gunakan `display: flex` pada navigasi utama, lalu manfaatkan teknik `margin-left: auto` atau pisahkan struktur dokumen menjadi 3 sub-grup flex.

### Latihan 2 (Tingkat Menengah): Galeri Gambar Fluid Menggunakan Grid
* **Tugas**: Buat galeri visual gambar adaptif tanpa menulis satupun baris `@media` query.
* **Spesifikasi**:
  1. Kolom tidak boleh memiliki lebar lebih sempit dari `200px`.
  2. Gambar harus mengisi sisa ruang secara proporsional jika layar membesar.
  3. Jarak horizontal dan vertikal antar gambar adalah seragam sebesar `16px`.
  4. Elemen gambar harus mempertahankan rasio `1:1` (kotak) dan tidak terdistorsi (`object-fit: cover`).

### Latihan 3 (Tingkat Mahir): Dashboard Modular dengan Grid-Template-Areas
* **Tugas**: Rekayasa antarmuka *Admin Control Center* menggunakan `grid-template-areas`.
* **Spesifikasi**:
  1. Definisikan area berikut: `header`, `sidebar`, `analytics-panel`, `activity-log`, `footer`.
  2. Pada viewport desktop: `sidebar` berada di kiri (lebar `260px` fix), `header` melintang di atas area konten, `analytics-panel` menempati porsi `2fr`, `activity-log` menempati `1fr`, dan `footer` di dasar layar.
  3. Implementasikan aturan defensive layout: Pastikan jika isi `activity-log` memuat teks panjang tanpa spasi (misalnya token enkripsi log yang panjang), layout tidak pecah (*no horizontal window-level overflow*).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

### Pertanyaan Evaluasi

1. **Apa yang mendasari keputusan spesifikasi W3C untuk tidak menyertakan properti `justify-items` pada kontainer Flexbox satu dimensi?**
   * A. Kesalahan arsitektur browser engine lama yang belum diperbaiki.
   * B. Karena perataan item individu pada sumbu utama (*main axis*) ditangani oleh `justify-content` dan teknik auto-margins (`margin: auto`).
   * C. Karena Flexbox hanya mendukung perataan vertikal.
   * D. Karena item flexbox tidak memiliki dimensi horizontal intrinsik.

2. **Diberikan kontainer flex sebesar 500px dengan properti `gap: 0`. Kontainer berisi dua elemen anak: Item A (`flex-basis: 300px`, `flex-grow: 1`) dan Item B (`flex-basis: 100px`, `flex-grow: 3`). Berapakah lebar akhir Item B yang dirender browser?**
   * A. 175px
   * B. 200px
   * C. 125px
   * D. 100px

3. **Manakah dari baris CSS berikut yang secara deterministik membuat tata letak grid dengan kolom yang mengisi kontainer, namun jika sisa ruang tidak cukup untuk menampung minimal 250px per kolom, kolom berikutnya otomatis dipindahkan ke baris baru?**
   * A. `grid-template-columns: repeat(3, minmax(250px, 1fr));`
   * B. `grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));`
   * C. `grid-template-columns: repeat(auto-fill, 250px);`
   * D. `grid-template-columns: 250px 1fr 1fr;`

4. **Mengapa properti `min-width: 0;` sering kali wajib ditambahkan pada elemen anak dari kontainer Flexbox atau CSS Grid?**
   * A. Untuk mengaktifkan akselerasi perangkat keras (*GPU compositing layer*).
   * B. Untuk menghapus padding bawaan browser.
   * C. Untuk menimpa aturan bawaan spesifikasi `min-width: auto` yang mencegah flex/grid item menyusut lebih kecil dari ukuran konten teksnya.
   * D. Agar animasi transisi properti lebar berjalan mulus (*smooth*).

5. **Apa efek visual dari deklarasi `grid-auto-flow: dense;` terhadap susunan elemen di dalam CSS Grid?**
   * A. Memadatkan resolusi gambar di dalam elemen anak secara otomatis.
   * B. Mengubah rendering grid menjadi Flexbox jika memori browser menipis.
   * C. Menginstruksikan browser untuk memindai dan mengisi lubang-lubang kosong di dalam grid dengan elemen DOM yang muncul belakangan jika ukurannya muat.
   * D. Mengunci lebar baris agar sama dengan tinggi kolom.

---

### Kunci Jawaban & Analisis Solusi

* **1. Jawaban B**: Pada Flexbox, sumbu utama (*main axis*) menangani alokasi ruang kosong agregat melalui `justify-content`. Fleksibilitas individual per-item pada sumbu utama dicapai secara elegan menggunakan `margin-left: auto` atau `margin-right: auto`, sehingga penambahan `justify-items` bersifat redundan secara matematika layout.
* **2. Jawaban A**:
  * Lebar Total Basis: $300\text{px} + 100\text{px} = 400\text{px}$.
  * Ruang Kosong Tersisa ($W_{free}$): $500\text{px} - 400\text{px} = 100\text{px}$.
  * Total Bobot `flex-grow`: $1 (\text{Item A}) + 3 (\text{Item B}) = 4$.
  * Alokasi Tambahan Item B: $\frac{3}{4} \times 100\text{px} = 75\text{px}$.
  * Lebar Akhir Item B: $100\text{px} (\text{basis}) + 75\text{px} (\text{alokasi}) = 175\text{px}$.
* **3. Jawaban B**: Fungsi `repeat(auto-fit, minmax(250px, 1fr))` mengevaluasi ukuran viewport secara dinamis. `auto-fit` akan merentangkan track yang terisi, sementara `minmax(250px, 1fr)` mengunci ukuran minimum ke 250px dan membungkus elemen ke baris baru saat ambang batas terlampaui.
* **4. Jawaban C**: Spesifikasi CSS mendefinisikan nilai default `min-width` pada flex/grid items sebagai `auto`. Secara algoritme, ini berarti *"jangan biarkan elemen ini lebih kecil dari konten terpanjangnya"*. Jika terdapat string URL panjang atau `pre-formatted text`, elemen akan meluap (*overflow*). Memberikan nilai `min-width: 0` membebaskan browser untuk menyusutkan elemen di bawah ukuran teks.
* **5. Jawaban C**: Algoritma auto-placement default melangkah maju secara linear tanpa kembali ke baris sebelumnya. Mode `dense` mengubah traversal algoritme dengan mengisi ruang kosong (*holes*) yang ditinggalkan oleh elemen berukuran besar dengan elemen kecil berikutnya, mengoptimalkan kepadatan visual.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **W3C Specifications**:
  * [CSS Flexible Box Layout Module Level 1](https://www.w3.org/TR/css-flexbox-1/)
  * [CSS Grid Layout Module Level 2 (Termasuk Subgrid)](https://www.w3.org/TR/css-grid-2/)
* **Dokumentasi Resmi & Panduan MDN**:
  * [MDN Web Docs: Basic Concepts of Flexbox](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_flexible_box_layout/Basic_concepts_of_flexbox)
  * [MDN Web Docs: Relationship of Grid Layout to Other Layout Methods](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_grid_layout/Relationship_of_grid_layout)
* **Karya Referensi & Literatur Standar**:
  * *"Every Layout"* oleh Heydon Pickering & Andy Bell (Katalog pola layout modular intrinsik).
  * *"CSS Grid Layout"* oleh Rachel Andrew (Panduan arsitektural spesifikasi W3C Grid).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Flexbox (1D) vs Grid (2D)**: Flexbox dirancang untuk mengalirkan elemen dalam satu garis linier (*content-outward*). CSS Grid dirancang untuk membangun sistem koordinat terstruktur yang menempatkan elemen pada baris dan kolom yang terikat bersamaan (*layout-inward*).
2. **Kalkulasi Ruang Flexbox**: `flex-grow` mendistribusikan sisa ruang positif secara proporsional terhadap bobotnya, sedangkan `flex-shrink` menyusutkan elemen secara proporsional berdasarkan kombinasi bobot dan ukuran basisnya saat kontainer mengalami ruang negatif.
3. **Kekuatan Matriks CSS Grid**: Fraksi `1fr` membagi sisa ruang bersih setelah alokasi fixed dan gap terpenuhi. Kombinasi `repeat(auto-fit, minmax(...))` menghasilkan layout multi-kolom yang sepenuhnya adaptif tanpa ketergantungan media query.
4. **Sinergi Terintegrasi**: Aplikasi web enterprise tidak memilih salah satu teknologi secara eksklusif. Praktik terbaik industri menggunakan **CSS Grid untuk tata letak makro** (kerangka aplikasi dan daftar kartu) dan **Flexbox untuk tata letak mikro** (isi komponen, header, baris input form, dan tombol).
5. **Defensive Layout**: Cegah masalah overflow struktural pada flex/grid items dengan selalu memvalidasi properti batas minimum (`min-width: 0;`), menyetel `box-sizing: border-box;`, serta mengganti properti `margin` usang dengan `gap`.

---

## SEKSI 17 — GLOSARIUM

* **Main Axis**: Sumbu utama pada kontainer Flexbox yang ditentukan oleh `flex-direction`. Jalur default-nya membentang horizontal dari kiri ke kanan (`row`).
* **Cross Axis**: Sumbu sekunder yang posisinya tegak lurus (perpendikular) 90 derajat terhadap Main Axis.
* **Positive Free Space**: Kelebihan ruang kosong pada kontainer setelah seluruh ukuran intrinsik/basis elemen anak selesai dihitung.
* **Negative Free Space**: Jumlah defisit piksel ketika ukuran akumulatif elemen anak melebihi dimensi fisik kontainer pembungkusnya.
* **Grid Track**: Kolom atau baris individual yang dibatasi oleh dua garis grid (*grid lines*) paralel yang berdekatan.
* **Grid Cell**: Unit unit struktural terkecil pada CSS Grid, dihasilkan dari perpotongan satu baris track dan satu kolom track (ekuivalen dengan 1 sel pada lembar kerja spreadsheet).
* **Grid Area**: Bidang persegi panjang logis yang terdiri dari satu atau beberapa grid cell yang berdekatan, diapit oleh empat garis grid.
* **Fraction Unit (`fr`)**: Unit ukuran fleksibel yang mewakili fraksi ruang yang tersisa di dalam kontainer CSS Grid setelah elemen-elemen berukuran statis dialokasikan.
* **Subgrid**: Fitur pada CSS Grid Level 2 di mana grid item yang bertindak sebagai kontainer anak dapat mengadopsi dan mengunci langsung definisi track (baris/kolom) milik induk utamanya.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Model Mental untuk Disampaikan ke Siswa
Saat mengajarkan konsep dasar, jangan langsung membombardir siswa dengan sintaks properti. Gunakan analogi fisik:
* **Flexbox adalah Kalung Manik-manik**: Manik-manik berjejer satu per satu sepanjang seutas benang (Main Axis). Anda dapat memilih untuk merapatkan semuanya ke kiri, menyebarkannya dengan jarak yang rata, atau membiarkan manik-manik melar jika karetnya ditarik. Namun, manik-manik pada baris kedua tidak tahu apa-apa tentang posisi manik-manik pada baris pertama.
* **CSS Grid adalah Lemari Rak Buku (Matrix)**: Rak telah dibagi menjadi sekat-sekat kayu horizontal dan vertikal yang permanen. Buku atau kotak barang diletakkan ke dalam kompartemen yang sudah ada. Bentuk dan ukuran kotak barang harus tunduk pada dimensi sekat rak tersebut.

### Titik Kesulitan Utama Siswa (Stumbling Blocks)
1. **Perbedaan `auto-fit` vs `auto-fill`**:
   * *Cara Mengatasi*: Buat demo interaktif dengan kontainer lebar berukuran 1200px dan hanya masukkan 2 kartu berukuran `minmax(200px, 1fr)`. Tunjukkan bahwa `auto-fill` akan mempertahankan ruang kosong untuk 4 kolom hantu di sebelah kanan, sedangkan `auto-fit` akan memaksa 2 kartu tersebut membesar selebar 600px masing-masing.
2. **Kalkulasi `flex: 1` vs `flex: auto`**:
   * *Cara Mengatasi*: Tunjukkan bahwa `flex: 1` ekuivalen dengan `flex: 1 1 0%` (mengabaikan ukuran konten awal dan membagi ruang murni secara matematis rata), sedangkan `flex: auto` ekuivalen dengan `flex: 1 1 auto` (memperhitungkan panjang teks awal sebelum membagi sisa ruang).

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal Rilis | Penulis / Maintainer | Catatan Perubahan Mutasi |
| :--- | :--- | :--- | :--- |
| **v1.0.0** | 2024-01-15 | Layout Systems Taskforce | Inisialisasi materi perdana: Rilis arsitektur Flexbox & Grid Core. |
| **v1.1.0** | 2024-06-20 | Frontend Curriculum Team | Menambahkan bab Defensive CSS (`min-width: 0`), kalkulasi Free Space, dan pembaruan browser support subgrid. |
| **v1.2.0** | 2024-10-30 | Lead Curriculum Architect | Refaktorisasi format ke standar modular terintegrasi 20 seksi GEMINI.md. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: [FEB-01-03: CSS Box Model & Normal Flow Mechanics](../FEB-01-03/README.md)
* **Modul Saat Ini**: **FEB-01-04: Sistem Tata Letak Modern: Flexbox & CSS Grid Multi-Dimensi**
* **Modul Berikutnya**: [FEB-01-05: Strategi Desain Responsif & Container Queries](../FEB-01-05/README.md)