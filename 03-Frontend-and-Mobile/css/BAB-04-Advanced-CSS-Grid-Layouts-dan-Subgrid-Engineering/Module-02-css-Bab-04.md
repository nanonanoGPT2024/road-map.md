# Kurikulum Rekayasa Frontend Enterprise: CSS Modern
## Bab 04: Advanced CSS Grid Layouts dan Subgrid Engineering
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, software engineer diharapkan mampu:
*   Menganalisis dan mengontrol mekanisme internal **CSS Grid Track Sizing Algorithm** (Blink/Gecko) untuk mengeliminasi siklus *layout thrashing* dan *unwanted intrinsic blowouts*.
*   Menguasai **CSS Subgrid Level 2 specification** untuk menyelesaikan fragmentasi vertikal/horizontal pada arsitektur komponen bertingkat (*nested component hierarchies*).
*   Mengimplementasikan strategi auto-placement tingkat lanjut (`grid-auto-flow: dense`) dengan kalkulasi deterministik serta mitigasi disonansi antara *Visual Tree* dan *Accessibility Object Model (AOM)*.
*   Mengintegrasikan **CSS Container Queries (`@container`)** dengan CSS Grid untuk menciptakan mikro-arsitektur tata letak modular yang sepenuhnya independen dari ukuran *viewport global*.
*   Membangun data-grid dan layout enterprise skala masif yang memiliki performa rendering 60fps dengan menjaga kompleksitas komputasi layout pada engine browser tetap linear ($O(N)$).

---

### 2. Prerequisite

*   Pemahaman mendalam mengenai siklus hidup rendering peramban (*Style Recalculation*, *Layout/Reflow*, *Paint*, *Compositing*).
*   Penguasaan dasar CSS Grid Level 1: `display: grid`, `grid-template-columns`, `grid-template-rows`, serta fungsi dasar `minmax()`.
*   Pemahaman format CSS Box Model: *Content-box*, *Border-box*, dan perilaku *Intrinsic Sizing* (`min-content`, `max-content`, `fit-content`).
*   Pengalaman menggunakan modern CSS Tooling dan Browser DevTools Layout Inspector (Firefox/Chrome Grid Inspector).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Track Sizing Algorithm (Spesifikasi W3C CSS Grid Level 1 & 2)

Browser rendering engine (seperti Blink pada Chromium atau Gecko pada Firefox) mengeksekusi Track Sizing Algorithm melalui beberapa fase deterministik sebelum menentukan koordinat piksel absolut dari sebuah elemen:

```
+-----------------------------------------------------------------------+
|                CSS GRID TRACK SIZING ALGORITHM (PHASES)              |
+-----------------------------------------------------------------------+
| 1. INITIALIZE TRACK SIZES                                             |
|    - Tentukan base size & growth limit untuk setiap track (min/max).  |
+----------------------------------+------------------------------------+
                                   |
                                   v
+----------------------------------+------------------------------------+
| 2. RESOLVE INTRINSIC SIZES (min-content, max-content, auto)          |
|    - Ukur konten item grid tanpa batasan constraint (Phase A).        |
|    - Distribusikan ruang ke track yang mencakup 1 item (Phase B).     |
|    - Distribusikan ruang ke span tracks > 1 (Phase C).                |
+----------------------------------+------------------------------------+
                                   |
                                   v
+----------------------------------+------------------------------------+
| 3. MAXIMIZE TRACK SIZES                                               |
|    - Jika ruang kontainer tersisa > akumulasi base size, tambahkan   |
|      ukuran track hingga mencapai growth limit.                       |
+----------------------------------+------------------------------------+
                                   |
                                   v
+----------------------------------+------------------------------------+
| 4. EXPAND FLEX TRACKS (fr Units)                                      |
|    - Hitung sisa ruang: FreeSpace = AvailableSpace - Sum(NonFlexTracks)|
|    - Bagi FreeSpace secara proporsional sesuai rasio fr item.         |
|    - Catatan: 1fr ekuivalen dengan minmax(auto, 1fr), BUKAN 0fr.      |
+----------------------------------+------------------------------------+
                                   |
                                   v
+----------------------------------+------------------------------------+
| 5. STRETCH 'AUTO' TRACKS                                              |
|    - Ekspansi track bertipe 'auto' jika align-content/justify-content |
|      diatur ke nilai default ('stretch').                             |
+-----------------------------------------------------------------------+
```

Perilaku kritis yang sering memicu *bug layout enterprise* adalah:
$$\text{Track Size Default} = \text{minmax}(\text{auto}, 1\text{fr})$$
Secara spesifikasi, nilai `auto` sebagai batas minimum mengizinkan konten intrinsik (seperti string panjang tanpa pemutus kata, `<pre>`, atau gambar besar) untuk memperbesar ukuran minimum track (*intrinsic minimum size*). Hal ini menyebabkan ukuran track melar melebihi alokasi proporsional `1fr`, memicu *layout overflow*. Solusi arsitekturalnya adalah memaksa batas bawah nol:
$$\text{Defensive Track Size} = \text{minmax}(0, 1\text{fr})$$

#### 3.2. Arsitektur Subgrid (CSS Grid Level 2)

Sebelum Subgrid distandarisasi, setiap kali elemen kontainer mendefinisikan `display: grid`, kontainer tersebut membentuk *independent formatting context*. Seluruh elemen turunan (*direct children*) hidup di grid tersebut, namun cucu (*grandchildren*) berada di luar jangkauan komputasi trek induk.

Subgrid menghapus batasan ini. Ketika elemen anak dideklarasikan dengan:
```css
.child-component {
  display: grid;
  grid-template-rows: subgrid;
  grid-template-columns: subgrid;
}
```
Engine browser tidak membuat sizing context baru untuk sumbu (*axis*) yang dideklarasikan sebagai subgrid. Sebaliknya, engine mendelegasikan penghitungan ukuran baris atau kolom langsung ke *parent grid formatting context*.

```
PARENT GRID CONTEXT (Columns: [col-1] 200px [col-2] 1fr [col-3] 2fr)
|------------------|-----------------------|----------------------------------|
| Row 1: Header    | Header Body           | Header Meta                      |
|                  |                       |                                  |
| [CHILD COMPONENT: display: grid; grid-column: 1 / -1; grid-template-columns: subgrid]
|    | Sub-Item A  | Sub-Item B            | Sub-Item C                       |
|    | (Locked 200)| (Locked to 1fr)       | (Locked to 2fr)                  |
|------------------|-----------------------|----------------------------------|
```

Dengan arsitektur ini:
*   Ukuran sub-item di dalam komponen anak dapat secara langsung mempengaruhi ukuran track induk (kontribusi intrinsik dua arah).
*   Penamaan garis (*named grid lines*) pada kontainer induk diwarisi oleh kontainer subgrid, namun subgrid juga dapat memberikan penamaan lokal (*local aliases*) tanpa mengotori skema global.

#### 3.3. Auto-Placement Algorithm: Sparse vs. Dense Packing

Algoritma penempatan otomatis CSS Grid beroperasi menggunakan *cursor positioning*:
1.  **Sparse Placement (Default - `grid-auto-flow: row | column`)**:
    *   Mesin penempatan bergerak linear dari baris ke baris, kolom ke kolom.
    *   Jika sebuah item membutuhkan span $N$ yang tidak muat pada ruang tersisa di baris aktif, kursor melompat ke baris berikutnya. Ruang kosong yang ditinggalkan dibiarkan kosong (*dead space*).
2.  **Dense Packing (`grid-auto-flow: row dense | column dense`)**:
    *   Ketika kursor melompat karena sebuah item tidak muat, item berikutnya dalam urutan DOM yang memiliki span lebih kecil akan di-*backtracking* oleh engine untuk mengisi celah (*backfilled*) yang tertinggal.
    *   **Kompleksitas Komputasi**: Menghasilkan overhead kalkulasi layout lebih tinggi dari $O(N)$ mendekati $O(N^2)$ pada skenario terburuk jika jumlah sel dan item sangat besar, karena engine harus memindai ulang slot-slot kosong sebelumnya.

---

### 4. Why & What

| Fitur | Pendekatan Tradisional (Flexbox / Nested Divs) | Pendekatan Modern (CSS Grid + Subgrid) |
| :--- | :--- | :--- |
| **Sikronisasi Tinggi Lintas Kartu** | Membutuhkan JavaScript (`ResizeObserver` / Window Resize listener) untuk menyamakan tinggi header/footer pada sekumpulan kartu dinamis. | Native CSS Subgrid; seluruh baris kartu berbagi trek baris global. Tidak ada eksekusi JS, *zero layout thrashing*. |
| **Penskalaan Komponen Mikro** | Tergantung pada Viewport Media Queries (`@media`), memaksa komponen terikat pada resolusi layar, bukan ruang kontainernya. | Kombinasi CSS Grid + CSS Container Queries (`@container`), memungkinkan grid beradaptasi modular di manapun diletakkan. |
| **Handling Overflow Konten** | Sering terjadi *broken layout* karena child flexbox tidak mengecil melewati `min-width: auto`. Membutuhkan trik `min-width: 0`. | Definisi deterministik dengan `minmax(0, 1fr)` atau `fit-content(limit)`. Kontrol granular atas batas intrinsik. |
| **Kompensasi Whitespace** | Perlu algoritma JavaScript pihak ketiga (misal: Masonry.js, Packery) untuk mengeliminasi ruang kosong layout asimetris. | Native `grid-auto-flow: dense`. Engine layout browser menangani kalkulasi pengisian ruang secara deterministik. |

---

### 5. How (Workflow Detail)

Untuk menerapkan CSS Grid & Subgrid tingkat lanjut dalam pipeline arsitektur frontend skala enterprise:

```
[Design Specs / Token Parsing]
               │
               ▼
[Step 1: Definisikan Global Grid Skeletons]
   - Gunakan CSS Custom Properties untuk melacak grid-template-columns/rows.
   - Tetapkan defensive sizing: minmax(0, 1fr) untuk fleksibilitas tanpa overflow.
               │
               ▼
[Step 2: Deklarasikan Boundaries Komponen]
   - Komponen turunan mengonsumsi span grid parent (cth: grid-column: span 3).
   - Terapkan display: grid; grid-template-rows: subgrid; pada komponen nested.
               │
               ▼
[Step 3: Tetapkan Line Naming Conventions]
   - Definisikan semantik: [header-start], [content-start], [footer-start].
   - Subgrid menggunakan nama garis parent untuk alignment otomatis.
               │
               ▼
[Step 4: Integrasikan Container Queries (@container)]
   - Pasang container-type: inline-size pada pembungkus komponen.
   - Sesuaikan konfigurasi grid sub-komponen terhadap ukuran kontainernya.
               │
               ▼
[Step 5: Verifikasi AOM & Aksesibilitas]
   - Cek DevTools Accessibility Inspector jika menggunakan auto-flow: dense.
   - Pastikan tab navigation (keystroke focus) selaras dengan orientasi visual.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan sebuah lemari arsip perkantoran (Parent Grid). 
*   **Tanpa Subgrid (Nested Independent Grid):** Anda menaruh kotak-kotak kecil (komponen kartu) di dalam laci. Setiap kotak memiliki sekat pemisahnya sendiri yang dibuat manual. Ukuran sekat di kotak A tidak peduli seberapa panjang dokumen di kotak B. Hasilnya: label dokumen di kotak A dan kotak B tidak berada pada ketinggian horizontal yang sama.
*   **Dengan Subgrid:** Kotak-kotak kecil tersebut transparan dan tidak memiliki sekat mandiri; mereka langsung menggunakan tiang-tiang penyangga vertikal dan horizontal milik lemari arsip utama. Jika dokumen di kotak A bertambah tebal, sekat lemari utama membesar, dan seluruh kotak lain di baris yang sama otomatis menyesuaikan ketinggiannya secara serentak.

#### Diagram ASCII: Arsitektur Subgrid Multi-Komponen

```
Parent Grid: 3 Kolom x 3 Baris Implisit
=============================================================================
Line:   [col-1]                [col-2]                [col-3]         [col-end]
=============================================================================
Row 1:  | Card A Container     | Card B Container     | Card C Container     |
        | [Header: Pendek]     | [Header: Sangat      | [Header: Sedang]     |
        |                      |  Panjang & Wrap]     |                      |
--------|----------------------|----------------------|----------------------| <-- Row 1 tersinkronisasi
Row 2:  | [Body Konten:        | [Body Konten:        | [Body Konten:        |
        |  Deskripsi Panjang]  |  Deskripsi Pendek]   |  Deskripsi Standar]  |
--------|----------------------|----------------------|----------------------| <-- Row 2 tersinkronisasi
Row 3:  | [Footer: Button]     | [Footer: Button]     | [Footer: Button]     |
============================================================================= <-- Row 3 tersinkronisasi
        * Seluruh Card adalah subgrid rows, mengunci header & footer pada garis horizontal absolut *
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Kartu Terenkapsulasi dengan Sinkronisasi Header & Footer

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <style>
    .card-deck {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 1.5rem;
      padding: 2rem;
      background-color: #f8fafc;
    }

    .card {
      display: grid;
      /* Memetakan 3 baris milik parent ke dalam kartu */
      grid-row: span 3;
      /* Subgrid baris: mengadopsi sizing parent untuk 3 baris */
      grid-template-rows: subgrid;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 1rem;
    }

    .card-header {
      font-weight: bold;
      border-bottom: 1px solid #f1f5f9;
      padding-bottom: 0.5rem;
    }

    .card-body {
      color: #475569;
      padding: 0.5rem 0;
    }

    .card-footer {
      margin-top: auto;
      background-color: #f8fafc;
      padding: 0.5rem;
      text-align: right;
    }
  </style>
</head>
<body>
  <div class="card-deck">
    <div class="card">
      <div class="card-header">Layanan Standar</div>
      <div class="card-body">Deskripsi singkat.</div>
      <div class="card-footer"><button>Pilih</button></div>
    </div>
    <div class="card">
      <div class="card-header">Layanan Enterprise Tingkat Lanjut dengan Skalabilitas Tinggi</div>
      <div class="card-body">Deskripsi panjang yang memiliki konten multi-paragraf untuk menguji dynamic height balancing pada engine browser.</div>
      <div class="card-footer"><button>Pilih</button></div>
    </div>
    <div class="card">
      <div class="card-header">Layanan Profesional</div>
      <div class="card-body">Deskripsi menengah tanpa konfigurasi rumit.</div>
      <div class="card-footer"><button>Pilih</button></div>
    </div>
  </div>
</body>
</html>
```

#### 7.2. Practical Example: Enterprise Data Comparison Table dengan Sticky Identifiers & Subgrid

Pola industri untuk komparasi metrik produk/keuangan dengan *nested layout alignment* dan *overflow protection*:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Matrix Subgrid Architecture</title>
  <style>
    :root {
      --color-border: #e2e8f0;
      --color-surface: #ffffff;
      --color-surface-subtle: #f8fafc;
      --color-text-main: #0f172a;
      --color-primary: #0284c7;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: var(--color-text-main);
      padding: 2rem;
      background-color: #f1f5f9;
    }

    .comparison-container {
      container-type: inline-size;
      container-name: matrix-wrapper;
      max-width: 1200px;
      margin: 0 auto;
    }

    /* Definisi Main Grid Canvas */
    .matrix-grid {
      display: grid;
      /* Kolom: Kolom Metrik (250px) + 3 Kolom Produk */
      grid-template-columns: 250px repeat(3, minmax(200px, 1fr));
      /* Baris: Header Produk, Baris Fitur 1, Fitur 2, Fitur 3, Action Footer */
      grid-template-rows: 
        [row-header-start] auto [row-header-end]
        [row-feat1-start] auto [row-feat1-end]
        [row-feat2-start] auto [row-feat2-end]
        [row-feat3-start] auto [row-feat3-end]
        [row-action-start] auto [row-action-end];
      gap: 0;
      background-color: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: 8px;
      overflow-x: auto;
    }

    /* Kolom Metrik (Label Sisi Kiri) */
    .metric-column {
      display: grid;
      grid-column: 1;
      grid-row: 1 / -1;
      grid-template-rows: subgrid;
      background-color: var(--color-surface-subtle);
      border-right: 2px solid var(--color-border);
    }

    /* Kolom Produk yang Mengonsumsi Subgrid Vertikal */
    .product-column {
      display: grid;
      grid-row: 1 / -1;
      grid-template-rows: subgrid;
      border-right: 1px solid var(--color-border);
      transition: background-color 0.2s ease;
    }

    .product-column:hover {
      background-color: #f0fdf4;
    }

    .cell {
      padding: 1.25rem;
      display: flex;
      align-items: center;
      border-bottom: 1px solid var(--color-border);
    }

    .cell.header {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
      background-color: var(--color-surface);
      font-weight: 700;
    }

    .cell.footer {
      border-bottom: none;
      justify-content: center;
    }

    .btn-action {
      width: 100%;
      padding: 0.75rem;
      background: var(--color-primary);
      color: white;
      border: none;
      border-radius: 4px;
      font-weight: 600;
      cursor: pointer;
    }

    /* Container Query Engine: Transformasi saat viewport/kontainer menyempit */
    @container matrix-wrapper (max-width: 768px) {
      .matrix-grid {
        grid-template-columns: 140px repeat(3, minmax(160px, 1fr));
      }
      .cell {
        padding: 0.75rem;
        font-size: 0.875rem;
      }
    }
  </style>
</head>
<body>

<div class="comparison-container">
  <div class="matrix-grid">
    <!-- Sisi Label / Metrik -->
    <div class="metric-column">
      <div class="cell header">Fitur & Arsitektur</div>
      <div class="cell">SLA Availability</div>
      <div class="cell">Dedicated Engine Instances & Custom Worker Nodes</div>
      <div class="cell">Audit Logs Retention</div>
      <div class="cell footer">Eksekusi</div>
    </div>

    <!-- Kolom Produk 1 -->
    <div class="product-column">
      <div class="cell header">
        <span>Tier Starter</span>
        <small style="color: #64748b;">$29/bln</small>
      </div>
      <div class="cell">99.5%</div>
      <div class="cell">Shared Tenancy</div>
      <div class="cell">30 Hari</div>
      <div class="cell footer"><button class="btn-action">Deploy</button></div>
    </div>

    <!-- Kolom Produk 2 (Tinggi Konten Tidak Seragam) -->
    <div class="product-column">
      <div class="cell header">
        <span>Tier Pro Enterprise</span>
        <small style="color: #64748b;">$299/bln</small>
      </div>
      <div class="cell">99.99% Guaranteed by Financial SLA Contract</div>
      <div class="cell">Hingga 16 Isolated Nodes dengan Custom Hardware Acceleration</div>
      <div class="cell">365 Hari (Compliant SOC2/HIPAA)</div>
      <div class="cell footer"><button class="btn-action">Deploy</button></div>
    </div>

    <!-- Kolom Produk 3 -->
    <div class="product-column">
      <div class="cell header">
        <span>Tier Unlimited</span>
        <small style="color: #64748b;">Custom Quote</small>
      </div>
      <div class="cell">99.999%</div>
      <div class="cell">Bare Metal Dedicated Clusters</div>
      <div class="cell">Tak Terbatas</div>
      <div class="cell footer"><button class="btn-action">Kontak</button></div>
    </div>
  </div>
</div>

</body>
</html>
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Aplikasi Web: **FinTech Real-Time High-Frequency Trading Risk Management Dashboard**.
Skala Pengguna: 5.000+ analis risiko institusional aktif secara bersamaan memantau portofolio instrumen derivatif.

#### Problem Statement
Dashboard menyajikan 50 widget risiko berbeda secara simultan dalam sebuah canvas dinamis. Masing-masing kartu widget memuat:
1.  Header interaktif dengan ticker realtime dan alert indicator.
2.  Visualisasi data (SVG/Canvas candlestick).
3.  Panel breakdown metrik risiko (*VaR, Expected Shortfall, Greeks*).
4.  Action bar untuk mitigasi posisi (*hedge execution*).

Ketika data pasar masuk via WebSocket dengan frekuensi ~50 update/detik, konten metrik berubah secara dinamis (angka bertambah digitnya, alert badges bertambah baris).

Pendekatan lama menggunakan **CSS Grid biasa dengan nested flexboxes** dan **JavaScript calculation** untuk menyamakan baseline visual memicu problem masif:
*   Layout Engine browser mengeksekusi *Recursive Reflow* terus-menerus.
*   Frame rate anjlok hingga <24fps (Jank parah) saat volatilitas pasar tinggi.
*   Total CPU utilization browser menyentuh 90%.

```
[WebSocket Stream: 50 msg/sec]
              │
              ▼
[DOM Update: Text Content Modified]
              │
              ▼ (Pendekatan Lama: JS DOM Reads/Writes)
[JS Height Balancer] ──> [DOM Mutation: Set inline style height]
                                    │
                                    ▼
                         [BROWSER FORCED REFLOW]  <── (Bottleneck: Layout Thrashing)
```

#### Solusi Rekayasa
1.  **Eliminasi Total Skrip Pengukur Layout:** Menghapus seluruh listener `ResizeObserver` dan library JS layout height-matching.
2.  **Arsitektur CSS Subgrid Bertingkat (Parent ke Cucu):**
    *   Tingkat 1 (Workspace): Grid 12 kolom dinamis.
    *   Tingkat 2 (Widget Container): Subgrid kolom & baris, mengambil bentang `grid-row: span 4`.
    *   Tingkat 3 (Sub-sections): Mengonsumsi baris subgrid tersebut secara deterministik.
3.  **Boundary Containment:**
    Menerapkan `contain: layout style;` pada wrapper widget individual yang tidak terikat row-sync guna memotong propagasi rekalkulasi reflow ke seluruh dokumen root.

```css
/* Core Production Snippet */
.trading-workspace {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  grid-auto-rows: min-content minmax(180px, auto) min-content 48px;
  gap: 1rem;
}

.risk-widget {
  grid-column: span 4;
  grid-row: span 4;
  display: grid;
  grid-template-columns: subgrid;
  grid-template-rows: subgrid;
}

.risk-widget__header { grid-row: 1; grid-column: 1 / -1; }
.risk-widget__chart  { grid-row: 2; grid-column: 1 / -1; }
.risk-widget__table  { grid-row: 3; grid-column: 1 / -1; }
.risk-widget__action { grid-row: 4; grid-column: 1 / -1; }
```

#### Hasil Metrik Kinerja Produksi
*   **Recalculate Style & Layout Cost:** Turun dari ~18.4ms per frame menjadi ~1.2ms per frame.
*   **Frame Stability:** Konstan pada 60fps, bahkan saat lonjakan data WebSocket 100 msg/sec.
*   **Bundle Size Reduction:** Mengeliminasi 42KB library third-party layout syncing JS.

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan (*Pros*) | Kerugian / Risiko (*Cons*) | Mitigasi Arsitektural |
| :--- | :--- | :--- | :--- |
| **CSS Subgrid** | Integritas alignment vertikal/horizontal native tanpa JavaScript; performansi tinggi; kode CSS sangat deklaratif. | Tidak mendukung browser *legacy* (IE11, Chromium < 117); debugging inspeksi inspect element lebih kompleks. | Gunakan Progressive Enhancement melalui `@supports (grid-template-rows: subgrid)`. Terapkan flexbox fallback sederhana. |
| **`grid-auto-flow: dense`** | Memaksimalkan efisiensi visual real estate, tidak ada ruang kosong di dashboard berbasis data. | **Aksesibilitas Rusak:** Urutan fokus navigasi keyboard (`Tab`) melompat-lompat acak karena DOM order berbeda dari Visual order. | Hindari penggunaan `dense` pada formulir interaktif atau teks naratif. Gunakan hanya pada strictly non-navigable analytic cards. |
| **Container Queries + Grid** | Modularitas sejati level komponen; komponen dapat di-embed pada sidebar, modal, atau main-content tanpa class modifier. | Sedikit penambahan kalkulasi style resolution overhead jika jumlah kontainer `inline-size` mencapai ribuan sel. | Batasi penetapan `container-type: inline-size` pada wrapper level makro, jangan pasang pada ribuan atom item kecil. |
| **`minmax(0, 1fr)` vs `1fr`** | Mencegah overflow horizontal yang dipicu oleh elemen teks tak terpatahkan atau gambar lebar. | Konten yang sangat panjang dapat terpotong (*clipped*) atau tertekan jika tidak dipasangkan dengan strategi `text-overflow` atau scrolling. | Konfigurasikan `overflow: hidden; text-overflow: ellipsis;` secara wajib pada elemen teks level daun (*leaf nodes*). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: "Subgrid Not Working" Karena Kurangnya Alokasi Track pada Sumbu Terkait
*Penyebab:* Pengembang menyatakan `grid-template-rows: subgrid;` pada child, tetapi lupa mengalokasikan bentangan baris (`grid-row: span N`) pada child tersebut. Subgrid tidak tahu berapa baris parent yang harus dipinjam.
```css
/* SALAH: Engine browser default mengasumsikan span 1, baris berikutnya kolaps */
.nested-component {
  display: grid;
  grid-template-rows: subgrid;
}

/* BENAR: Nyatakan span eksplisit sesuai hierarki anak */
.nested-component {
  display: grid;
  grid-row: span 3; /* Menyatakan komponen ini menempati 3 baris parent */
  grid-template-rows: subgrid;
}
```

#### Kesalahan 2: Kerusakan Tata Letak Akibat Sizing `1fr` Default (Intrinsic Blowout)
*Penyebab:* Konten di dalam grid item memiliki string panjang tanpa spasi (misal hash ID transaksi: `0x71C...b97CA8`), membuat minimum track size default (`auto`) menolak mengecil.
```css
/* SALAH: Menyebabkan horizontal scrolling yang tidak diinginkan */
.container {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
}

/* BENAR: Batalkan batas intrinsik minimum dengan angka 0 */
.container {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
```

#### Kesalahan 3: Tab Ordering Disconnect dengan `grid-auto-flow: dense`
*Gejala:* Audit Aksesibilitas (WCAG 2.1 Criteria 1.3.2 Meaningful Sequence) gagal karena fokus tab keyboard melompat dari kartu 1, ke kartu 4, lalu mundur ke kartu 2.
*Troubleshooting:* Buka Chrome DevTools -> Run Command -> "Show Accessibility Tree". Bandingkan DOM Reading Order dengan urutan geometris visual. Jika terjadi ketidakselarasan drastis, hilangkan flag `dense` atau atur DOM sequence secara deterministik pada level server-side rendering.

---

### 11. Best Practices (Production Checklist)

*   [ ] **Gunakan Naming Convention Terstruktur pada Grid Lines:**
    Gunakan suffix `-start` dan `-end` (misal: `[sidebar-start] 250px [sidebar-end] [main-start] 1fr [main-end]`). Ini otomatis menciptakan area implisit (`grid-area: sidebar` / `grid-area: main`).
*   [ ] **Hindari Magic Numbers:**
    Jangan menggunakan nilai pixel hardcoded untuk mengatasi alignment celah sub-komponen. Serahkan penyelarasan pada pembagian subgrid.
*   [ ] **Defensive Viewport Constraints:**
    Pastikan kontainer grid level atas selalu memiliki `max-width: 100%` atau ditautkan dengan `overflow: hidden / auto` untuk mengisolasi kegagalan rendering anak.
*   [ ] **Progressive Enhancement Pattern:**
    ```css
    /* Pola Produksi Wajib Fallback */
    .feature-card {
      display: flex;
      flex-direction: column;
    }

    @supports (grid-template-rows: subgrid) {
      .feature-parent {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      }
      .feature-card {
        display: grid;
        grid-row: span 3;
        grid-template-rows: subgrid;
      }
    }
    ```
*   [ ] **Minimalisir Layering z-index:**
    Manfaatkan urutan deklarasi grid auto-placement untuk layering, hindari penggunaan `z-index: 9999` yang tidak terkendali di dalam grid cell formatting context.

---

### 12. Hands-on Practice

Buat dan simpan struktur file berikut pada direktori kerja Anda di `hands-on/m02/`.

#### File: `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Multi-Variant Card Engine</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>

  <header class="app-header">
    <h1>Analisis Portofolio Cloud</h1>
    <p>Konfigurasi Layout Menggunakan Native CSS Subgrid & Container Queries</p>
  </header>

  <main class="dashboard-viewport">
    <section class="portfolio-grid">
      
      <!-- Card Instance 1 -->
      <article class="portfolio-card">
        <div class="card-badge">PRODUCTION</div>
        <h2 class="card-title">Instance Cluster Alpha</h2>
        <div class="card-telemetry">
          <p>Status: <strong>Normal</strong></p>
          <p>Uptime: 99.98%</p>
        </div>
        <div class="card-actions">
          <button class="btn btn-secondary">Logs</button>
          <button class="btn btn-primary">Restart</button>
        </div>
      </article>

      <!-- Card Instance 2 (Extreme Content Length) -->
      <article class="portfolio-card">
        <div class="card-badge card-badge--warning">WARNING</div>
        <h2 class="card-title">Instance Cluster Beta dengan Beban Komputasi Lintas Region yang Sangat Berat</h2>
        <div class="card-telemetry">
          <p>Status: <strong>Memory Pressure Alert</strong></p>
          <p>Uptime: 94.12%</p>
          <p>Thread Count: 1,024 Active</p>
          <p>Memory Usage: 98.4% of 128GB Allocated RAM</p>
        </div>
        <div class="card-actions">
          <button class="btn btn-secondary">Logs</button>
          <button class="btn btn-primary">Restart</button>
        </div>
      </article>

      <!-- Card Instance 3 -->
      <article class="portfolio-card">
        <div class="card-badge">STAGING</div>
        <h2 class="card-title">Instance Cluster Gamma</h2>
        <div class="card-telemetry">
          <p>Status: <strong>Idle</strong></p>
        </div>
        <div class="card-actions">
          <button class="btn btn-secondary">Logs</button>
          <button class="btn btn-primary">Restart</button>
        </div>
      </article>

    </section>
  </main>

</body>
</html>
```

#### File: `hands-on/m02/styles.css`
```css
/* CSS Reset & System Tokens */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  --font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --bg-app: #090d16;
  --bg-card: #131b2e;
  --border-color: #232f48;
  --text-main: #f1f5f9;
  --text-muted: #94a3b8;
  --color-primary: #3b82f6;
  --color-primary-hover: #1d4ed8;
  --color-warning: #f59e0b;
}

body {
  font-family: var(--font-family);
  background-color: var(--bg-app);
  color: var(--text-main);
  padding: 2.5rem;
  line-height: 1.5;
}

.app-header {
  margin-bottom: 2rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 1rem;
}

.app-header h1 {
  font-size: 1.75rem;
  font-weight: 700;
}

.app-header p {
  color: var(--text-muted);
}

/* Master Container */
.dashboard-viewport {
  container-type: inline-size;
  container-name: dashboard;
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
}

/* 
  Parent Grid: Mendefinisikan baris global yang akan dikonsumsi oleh Subgrid
*/
.portfolio-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  /* 4 Track Baris: Badge, Title, Telemetry, Actions */
  grid-auto-rows: 
    [card-badge-start] auto [card-badge-end]
    [card-title-start] auto [card-title-end]
    [card-telemetry-start] auto [card-telemetry-end]
    [card-actions-start] auto [card-actions-end];
  gap: 1.5rem;
}

/* 
  Komponen Kartu Individual: Meminjam 4 Baris Induk via Subgrid
*/
.portfolio-card {
  display: grid;
  grid-row: span 4;
  grid-template-rows: subgrid;
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
}

/* Elemen-elemen Daun diikat ke jalurnya masing-masing */
.card-badge {
  grid-row: 1;
  display: inline-block;
  align-self: start;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.05em;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  background-color: rgba(59, 130, 246, 0.15);
  color: var(--color-primary);
  width: fit-content;
}

.card-badge--warning {
  background-color: rgba(245, 158, 11, 0.15);
  color: var(--color-warning);
}

.card-title {
  grid-row: 2;
  font-size: 1.15rem;
  font-weight: 600;
  margin: 0.75rem 0;
  color: var(--text-main);
  align-self: start;
}

.card-telemetry {
  grid-row: 3;
  color: var(--text-muted);
  font-size: 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.75rem 0;
  border-top: 1px dashed var(--border-color);
  margin-bottom: 1rem;
}

.card-telemetry strong {
  color: var(--text-main);
}

.card-actions {
  grid-row: 4;
  display: flex;
  gap: 0.75rem;
  align-self: end;
}

.btn {
  flex: 1;
  padding: 0.6rem 1rem;
  font-weight: 600;
  font-size: 0.875rem;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  transition: background-color 0.2s;
}

.btn-primary {
  background-color: var(--color-primary);
  color: #ffffff;
}

.btn-primary:hover {
  background-color: var(--color-primary-hover);
}

.btn-secondary {
  background-color: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-main);
}

.btn-secondary:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

/* Responsivitas Berbasis Mikro-Kontainer */
@container dashboard (max-width: 900px) {
  .portfolio-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@container dashboard (max-width: 580px) {
  .portfolio-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .portfolio-card {
    grid-row: span 4;
    grid-template-rows: auto auto auto auto; /* Fallback to independent tracks */
  }
}
```

---

### 13. Exercise

#### Level: Easy
Ubah konfigurasi file pada `hands-on/m02/` sehingga track baris `card-title` memiliki batas ketinggian minimum sebesar `4rem` menggunakan fungsi `minmax()` pada parent grid, untuk mencegah inkonsistensi layout saat teks sangat pendek.

#### Level: Medium
Implementasikan skema horizontal alignment menggunakan `grid-template-columns: subgrid;`. Buat sebuah komponen formulir di mana label form berada di kolom 1 dan input field berada di kolom 2. Pastikan input field melebar secara proporsional dan seluruh label form sejajar sempurna terlepas dari panjang string teks label.

#### Level: Hard
Bangun timeline dependency tracker modular:
*   Parent grid memiliki kolom per-minggu: `repeat(12, minmax(60px, 1fr))`.
*   Buat komponen bar tugas (*task item*) yang menempati span acak (cth: `grid-column: 3 / span 4`).
*   Di dalam task item, deklarasikan `grid-template-columns: subgrid` sehingga milestone internal (titik-titik checklist di dalam task bar) mengunci posisinya langsung ke garis minggu global milik parent tanpa perhitungan persentase atau koordinat pixel manual.

---

### 14. Challenge

**Studi Kasus:** Bangun arsitektur tata letak untuk sistem **Data Visualization Pivot Matrix** dengan kriteria rekayasa tingkat lanjut:
1.  **Frozen Panes Dua Arah:** Baris header tabel terkunci secara vertikal (*sticky top*), dan kolom identifier metrik terkunci secara horizontal (*sticky left*).
2.  **Zero-JS Auto-Balancing:** Komparasi metrik terdiri dari modul accordion bersarang (*nested expanding drawers*). Ketika sebuah baris accordion di dalam salah satu sel diperluas (*expanded*), seluruh baris transversal di kolom-kolom saudara (*sibling columns*) harus langsung memperbesar ukurannya secara tersinkronisasi murni menggunakan kalkulasi layout engine native CSS.
3.  **Algoritma Dense Placement Deterministic:** Terapkan dense auto-placement pada grid metrik pendukung untuk mengemas ringkasan grafik mikro secara rapat tanpa membiarkan visual tab order menyimpang dari urutan logika baca.
4.  **Aturan Pembatasan:** Tidak boleh ada pemanggilan objek `window`, `document.querySelector`, `getBoundingClientRect`, atau `ResizeObserver` dari JavaScript. Seluruh komputasi spasial wajib diselesaikan oleh CSS Grid Level 2 dan Browser Compositor.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1.  Mengapa deklarasi `grid-template-columns: 1fr 1fr;` dapat memicu munculnya horizontal scrollbar yang tidak diinginkan pada browser?
    *Jawaban Singkat:* Karena `1fr` memiliki implicit minimum sizing sebesar `auto`. Jika ada konten internal yang tidak dapat dipatahkan (seperti string panjang atau gambar lebar), lebar track akan membesar melampaui `1fr` untuk menampung konten tersebut.
2.  Apa perbedaan mendasar antara nested grid konvensional dengan CSS Subgrid?
    *Jawaban Singkat:* Nested grid konvensional menginisialisasi context kalkulasi track baru yang independen dari induknya. Subgrid berbagi (*inherits*) pembagian track dan sizing algorithm langsung dari parent grid formatting context.
3.  Syntax apa yang harus dideklarasikan pada elemen anak agar mengadopsi baris dari kontainer grid induknya?
    *Jawaban Singkat:* `display: grid; grid-row: span N; grid-template-rows: subgrid;`.
4.  Apa efek penggunaan `grid-auto-flow: dense` terhadap elemen grid yang memiliki ukuran kecil?
    *Jawaban Singkat:* Browser akan memposisikan elemen kecil tersebut ke ruang/slot kosong yang ditinggalkan sebelumnya (*backfilling*), melompati urutan DOM aslinya jika perlu.
5.  Apakah Subgrid harus selalu diterapkan pada kedua sumbu (baris dan kolom) secara bersamaan?
    *Jawaban Singkat:* Tidak. Subgrid dapat dideklarasikan secara independen hanya pada sumbu baris (`grid-template-rows: subgrid`) atau hanya pada sumbu kolom (`grid-template-columns: subgrid`).

#### Intermediate Questions
6.  Bagaimana cara kerja penamaan grid line (*line naming*) induk saat diwariskan ke dalam subgrid?
    *Jawaban Singkat:* Garis yang dicakup oleh bentang subgrid mewarisi nama garis dari parent grid. Subgrid juga dapat menambahkan nama garis lokal baru tanpa menghapus identitas nama garis parent.
7.  Jelaskan skenario di mana browser engine terpaksa mengeksekusi komputasi track sizing dengan kompleksitas mendekati $O(N^2)$ pada CSS Grid!
    *Jawaban Singkat:* Terjadi saat menggunakan `grid-auto-flow: dense` dengan ribuan grid items dan kombinasi multidimensi auto-spans, yang memaksa engine mengulang traversal pencarian slot kosong yang tertinggal setiap kali item baru tidak muat.
8.  Mengapa penggunaan Container Queries (`@container`) lebih direkomendasikan daripada Media Queries (`@media`) saat merancang komponen grid modular?
    *Jawaban Singkat:* Media queries hanya membaca ukuran viewport layar global, membatasi portabilitas komponen. Container queries merespons dimensi elemen pembungkus langsung (*parent container*), memungkinkan komponen menyesuaikan layout grid-nya secara dinamis saat ditempatkan di sidebar, modal, ataupun area utama.
9.  Bagaimana cara melakukan mitigasi Progressive Enhancement untuk browser yang belum mengimplementasikan CSS Subgrid?
    *Jawaban Singkat:* Memanfaatkan *feature query* `@supports (grid-template-rows: subgrid) { ... }` untuk menyuntikkan logika subgrid, sementara di luar blok tersebut disiapkan tata letak berbasis Flexbox atau auto-rows standar.
10. Bagaimana mekanisme pemrosesan track sizing `fit-content(limit)` bekerja?
    *Jawaban Singkat:* Formula eksekusinya adalah: `min(max-content, max(min-content, limit))`. Artinya ukuran akan melar mengikuti konten hingga batas `limit`, dan tidak akan pernah lebih kecil dari `min-content`.

#### Production Scenarios

11. **Skenario Kasus Produksi A:**
    *Masalah:* Di sistem e-commerce berskala enterprise, tim QA melaporkan bahwa navigasi keyboard (Accessibility Tab Index) pada halaman katalog produk melompat secara acak setelah diterapkannya optimasi layout grid.
    *Investigasi:* File CSS menunjukkan penggunaan `grid-auto-flow: row dense;` dengan kartu-kartu promosi berukuran `grid-column: span 2` yang ditempatkan secara acak dari API.
    *Akar Masalah & Solusi:* Dense packing mengubah rendering visual tree menjauh dari DOM order. Pembaca layar (*screen reader*) dan navigasi tab fokus mengikuti DOM order asli, bukan urutan visual layout. Solusinya: Urutkan data secara deterministik dari backend/state management dan kembalikan aliran grid ke default (`grid-auto-flow: row`), atau atur penataan visual menggunakan span yang modular tanpa flag `dense`.

12. **Skenario Kasus Produksi B:**
    *Masalah:* Sebuah dashboard analitik performa mengalami layout failure; konten di dalam kartu subgrid meluap keluar dari batas kontainer saat dibuka di browser Chromium versi lama (v105) pada perangkat workstation lawas perusahaan.
    *Akar Masalah & Solusi:* Chromium baru mendukung subgrid penuh pada versi 117. Solusi arsitektur: Implementasikan baseline styling berupa `display: flex; flex-direction: column; justify-content: space-between;` pada kartu, lalu bungkus aturan subgrid di dalam `@supports (grid-template-rows: subgrid)`. Browser lawas akan menggunakan Flexbox fallback dengan aman.

13. **Skenario Kasus Produksi C:**
    *Masalah:* Aplikasi finansial memiliki tabel raksasa (500 baris x 20 kolom) yang diimplementasikan dengan `display: grid; grid-template-rows: subgrid;` di setiap barisnya. Pengguna mengeluhkan lag pengetikan (*input latency*) saat mengetik pada search filter bar.
    *Investigasi:* Profiling Performance DevTools menunjukkan bahwa setiap keystroke memicu *Style Recalculation* dan *Layout* sebesar ~150ms.
    *Akar Masalah & Solusi:* Subgrid menghubungkan seluruh sel ke satu context kalkulasi raksasa. Mutasi DOM kecil memicu rekalkulasi track bertingkat ke seluruh 10.000 sel. Solusinya: Implementasikan teknik virtualisasi tabel (DOM windowing via Virtual Scroll) sehingga hanya baris yang terlihat di layar (~20 baris) yang dirender ke DOM, serta tambahkan `content-visibility: auto;` pada baris-baris tabel untuk memotong render tree traversal yang tidak terlihat.

---

### 16. Summary

1.  **Track Sizing Algorithm Determinism:** Pemahaman tahapan pemrosesan engine browser dari evaluasi batas intrinsik (`min-content`, `max-content`) hingga resolusi unit fleksibel (`fr`) adalah fondasi dalam mencegah cacat layout seperti *intrinsic blowout*. Nilai defensif `minmax(0, 1fr)` harus selalu menjadi default saat mendistribusikan fraksi ruang.
2.  **Subgrid Resolves Vertical & Horizontal Fragmentation:** CSS Subgrid (Grid Level 2) mematahkan isolasi batasan konteks format (*formatting context isolation*). Subgrid memungkinkan komponen anak berpartisipasi langsung dalam track parent grid, mewujudkan sinkronisasi visual sempurna tanpa setetespun kode JavaScript pengukur ketinggian.
3.  **Modularitas Modern:** Integrasi antara CSS Grid, CSS Subgrid, dan CSS Container Queries menghadirkan paradigma arsitektur frontend baru: layout yang sepenuhnya terisolasi, modular, responsif terhadap lingkungannya sendiri, dan bebas ketergantungan terhadap dimensi layar perangkat global.
4.  **Engineering Vigilance:** Penggunaan fitur auto-placement mutakhir seperti `dense` harus diimbangi dengan mitigasi aksesibilitas yang ketat. Keseimbangan performa layout engine ($O(N)$ vs $O(N^2)$) harus dipertahankan melalui isolasi batasan render (*CSS Containment*) pada aplikasi enterprise skala besar.