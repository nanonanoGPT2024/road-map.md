# Bab 04 Module 01: Advanced CSS Grid Layouts & Subgrid Engineering

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Topik Inti:** CSS Core & Modern Layout Engine
* **Modul:** Bab 04 Module 01 — Advanced CSS Grid Layouts & Subgrid Engineering
* **Level Teknis:** Advanced / Staff Engineer Level
* **Prasyarat:** Pemahaman solid CSS Display Model, Flexbox Box Alignment, Cascade, Specificity, dan dasar CSS Grid Level 1 (grid-template-columns, grid-template-rows, grid-column).

---

## SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta mampu:
1. Membedah algoritma internal browser dalam mengevaluasi ukuran track CSS Grid: kalkulasi `fr`, `minmax()`, dan sizing keyword (`min-content`, `max-content`, `fit-content()`).
2. Menganalisis lifecycle eksekusi Grid: Grid Sizing Algorithm, Auto-placement Matrix, Implicit vs Explicit tracks, serta dampaknya terhadap Layout Thrashing dan reflow.
3. Merancang arsitektur layout multidimensi yang tahan banting menggunakan `subgrid` untuk sinkronisasi layout lintas hierarki DOM tanpa merusak semantics tree.
4. Menerapkan Named Grid Lines dan Grid Areas tingkat lanjut untuk enterprise design system yang modular, decoupled, dan self-documenting.
5. Memecahkan edge cases pergeseran visual (Cumulative Layout Shift) dan misalignment flex-to-grid bridging di browser modern melalui isolasi rendering layout.

---

## SEKSI 03 — MINDSET & MENTAL MODEL
### Pergeseran Mental: One-Dimensional Flow vs Two-Dimensional Coordinate Matrix
Pengembang sering memperlakukan CSS Grid sebagai varian Flexbox yang kaku. Mental model yang benar:
* **Flexbox** bersifat *content-driven* (satu dimensi): Ukuran item mendikte ketersediaan ruang baris/kolom; perataan bersifat lokal terhadap flex line aktif.
* **Grid** bersifat *layout-driven* (dua dimensi): Kontainer mendikte matriks spasial global; item beradaptasi ke dalam sel koordinat `[x, y]`. Hubungan antar track bersifat struktural dan interdependent.

```
       Flexbox Mental Model                 Grid Mental Model
    +-------+ +-------------+ +---+      +-------+-------+-------+
    | Item  | | Long Item   | |Itm|  vs  | Track | Track | Track |
    +-------+ +-------------+ +---+      +-------+-------+-------+
    (Tiap elemen menghitung lebarnya      | Sumbu X dan Y terikat |
     secara independen per baris)        | dalam sistem koordinat|
```

### The Subgrid Paradigm
Sebelum CSS Subgrid (Grid Level 2), batas CSS layout terhenti di anak langsung (*direct children*). Setiap nested element membuat konteks formatting baru yang terisolasi (*nested formatting context*), memaksa pengembang melakukan:
1. Hardcoded height/width (menghancurkan fleksibilitas dinamis).
2. Perataan berbasis JavaScript (menghasilkan layout shifts dan jank).
3. Merusak nesting HTML demi mengekspos anak ke grid utama (merusak Web Accessibility/A11y dan semantik dokumen).

**Subgrid mentransendensikan batas tree DOM:** Ia mengizinkan child grid mengadopsi track sizing dan line labels dari parent grid, mengubah DOM tree hierarkis menjadi **unified geometric projection plane**.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Siklus Resolusi Track Size (W3C CSS Grid Sizing Algorithm)
Setiap frame yang memicu kalkulasi grid diproses melalui pipeline deterministik:

```
[DOM Mutasi / Resize / Font Load]
               │
               ▼
┌────────────────────────────────────────┐
│ Phase 1: Initialize Track Sizes        │
│ Set base size & growth limit per track │
└────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ Phase 2: Resolve Intrinsic Track Sizes │
│ Evaluasi: min-content, max-content,    │
│ fit-content(), auto                    │
└────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ Phase 3: Maximize Tracks               │
│ Alokasikan sisa ruang ke growth limits │
└────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ Phase 4: Expand Flexible Tracks        │
│ Hitung nilai 1fr terhadap sisa space:  │
│ FreeSpace / Sum(fr)                    │
└────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│ Phase 5: Align Content & Items         │
│ Resolusi justify-* & align-*           │
└────────────────────────────────────────┘
               │
               ▼
[Layout Phase Selesai -> Render Paint/Composite]
```

### 2. Arsitektur Komparasi Nested Grid vs Subgrid

```
+-------------------------------------------------------------------------+
| PARENT GRID CONTAINER (display: grid; grid-template-columns: 1fr 2fr 1fr)|
|                                                                         |
|  Track 01 (1fr)             Track 02 (2fr)            Track 03 (1fr)    |
|  [Line 1]                   [Line 2]                  [Line 3]   [Line 4]
|     │                          │                         │          │
|     │  +──────────────────────────────────────────────+  │          │
|     │  | DIRECT CHILD A (grid-column: 1 / 3)          |  │          │
|     │  |                                              |  │          │
|     │  | NESTED INDEPENDENT GRID:                     |  │          │
|     │  | display: grid; template: 1fr 1fr             |  │          │
|     │  | [Col 1]                [Col 2]               |  │          │
|     │  | (TIDAK ADA KONEKSI KE PARENT TRACK)          |  │          │
|     │  +──────────────────────────────────────────────+  │          │
|     │                          │                         │          │
|     │  +─────────────────────────────────────────────────────────+  │
|     │  | DIRECT CHILD B (grid-column: 1 / 4)                     |  │
|     │  | display: grid;                                          |  │
|     │  | grid-template-columns: subgrid;                         |  │
|     │  |                                                         |  │
|     │  | [Sub-Col 1]           [Sub-Col 2]            [Sub-Col 3]|  │
|     │  | (TERIKAT KE           (TERIKAT KE            (TERIKAT KE│  |
|     │  |  Line 1-2)             Line 2-3)              Line 3-4) │  |
|     │  +─────────────────────────────────────────────────────────+  │
+─────┴──────────────────────────┴─────────────────────────┴──────────┴───+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Anatomi Spesifikasi Grid
* **Explicit Grid:** Track yang didefinisikan secara eksplisit via `grid-template-rows` dan `grid-template-columns`.
* **Implicit Grid:** Track yang dibuat otomatis oleh browser ketika item ditempatkan di luar batas explicit grid, dikontrol via `grid-auto-rows` dan `grid-auto-columns`.
* **Grid Lines:** Garis horizontal dan vertikal bernomor (1-indexed dari awal, -1 indexed dari akhir) atau berlabel teks, memisahkan track.
* **Gutters (Gaps):** Ruang struktural antar track (`row-gap`, `column-gap`). Pada `subgrid`, gutter diwariskan dari parent kecuali didefinisikan ulang secara eksplisit.
* **Subgrid Context:** Menggantikan definisi track lokal dengan referensi langsung ke irisan track parent yang dilewati (*spanned*) oleh elemen tersebut.

### Algoritma Perhitungan `fr`
Unit `fr` (fractional) merepresentasikan proporsi ruang bebas (*free space*). Formula perhitungannya:
$$\text{FreeSpace} = \text{GridContainerWidth} - \sum(\text{FixedTracks}) - \sum(\text{Gaps})$$
$$\text{Value of } 1\text{fr} = \frac{\text{FreeSpace}}{\sum(\text{FlexFactors})}$$

Jika $\sum(\text{FlexFactors}) < 1$, ruang tidak akan terisi penuh; browser memperlakukan total flex factor sebagai persentase dari ruang bebas alih-alih membagi habis.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. `minmax()` dan Intrinsic Minimum Sizing
Kombinasi `minmax(min, max)` memandu browser menentukan ukuran minimum sebelum pembesaran terjadi. 
* Standar default track berukuran `1fr` ekuivalen dengan `minmax(auto, 1fr)`, **bukan** `minmax(0, 1fr)`.
* Karena `auto` mengevaluasi ukuran minimum intrinsik elemen (`min-width: auto`), teks panjang yang tidak wrap atau gambar berukuran besar dapat merusak layout (*grid blowout*).
* **Solusi Arsitektural:** Selalu gunakan `minmax(0, 1fr)` saat track ditargetkan untuk menampung komponen dinamis dengan truncation atau scrollable overflow.

### 2. Auto-Placement Matrix & Packing Algorithm
Properti `grid-auto-flow: dense` mengaktifkan algoritma pengemasan ruang (backfilling):
1. Browser mengurutkan item sesuai order DOM dan nilai CSS `order`.
2. Jika ada item berukuran besar (misal: span 2 kolom) yang tidak muat di sisa baris saat ini, browser melompat ke baris berikutnya.
3. Tanpa `dense`, slot kosong di baris sebelumnya ditinggalkan kosong permanen.
4. Dengan `dense`, item-item berikutnya yang lebih kecil (misal: span 1 kolom) akan ditarik ke belakang oleh browser untuk mengisi celah visual tersebut.
*Peringatan Accessibility (A11y):* `dense` dapat merusak sinkronisasi antara DOM order (aksesibilitas screen reader dan keyboard tab index) dan visual order. Gunakan hanya pada elemen non-interaktif atau visual dekoratif.

### 3. Subgrid Dynamic Sizing Coupling
Saat sebuah child dikonfigurasi dengan:
```css
.child {
  grid-column: 2 / span 3;
  display: grid;
  grid-template-columns: subgrid;
}
```
Child tersebut tidak mendefinisikan layout internal secara otonom. Parent grid sekarang menghitung ukuran kolom 2, 3, dan 4 dengan memperhitungkan isi di dalam subgrid child. 
Artinya: konten di dalam cicit (great-grandchild) dapat memperlebar kolom parent grid secara global. Ini adalah **bi-directional layout dependency**.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi dashboard multi-tier yang mendemonstrasikan named lines, layout responsif adaptif tanpa media query via `auto-fit`, dan `subgrid` untuk perataan kartu metrik.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Advanced CSS Grid Core Demo</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main class="dashboard-grid">
    <header class="dashboard-header">
      <h1>Metrik Performa Mesin Finansial</h1>
    </header>

    <section class="card-cluster">
      <article class="metric-card">
        <h2 class="card-title">Settlement Core</h2>
        <div class="card-body">
          Latency transaksi rata-rata tereduksi hingga batas optimal.
        </div>
        <footer class="card-footer">
          <button type="button">Detail Audit</button>
        </footer>
      </article>

      <article class="metric-card">
        <h2 class="card-title">Real-Time Risk Ledger Engine & Telemetry Monitoring Interface</h2>
        <div class="card-body">
          Penyimpanan data mutasi terenkripsi dengan toleransi fragmentasi nol.
        </div>
        <footer class="card-footer">
          <button type="button">Detail Audit</button>
        </footer>
      </article>

      <article class="metric-card">
        <h2 class="card-title">Data Ingestion Engine</h2>
        <div class="card-body">
          Pipeline konsumsi data skala terdistribusi.
        </div>
        <footer class="card-footer">
          <button type="button">Detail Audit</button>
        </footer>
      </article>
    </section>
  </main>
</body>
</html>
```

```css
/* style.css */
:root {
  --base-spacing: 1.5rem;
  --color-bg: #0f172a;
  --color-surface: #1e293b;
  --color-text: #f8fafc;
  --color-accent: #38bdf8;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background-color: var(--color-bg);
  color: var(--color-text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  padding: var(--base-spacing);
}

/* Explicit Named Grid Lines pada Kontainer Utama */
.dashboard-grid {
  display: grid;
  grid-template-columns: 
    [full-start] minmax(1rem, 1fr) 
    [content-start] minmax(auto, 1200px) 
    [content-end] minmax(1rem, 1fr) 
    [full-end];
  grid-template-rows: auto 1fr;
  row-gap: 2rem;
}

.dashboard-header {
  grid-column: content-start / content-end;
}

/* Card Cluster: Auto-fit Grid dengan Track Rows berbasis Konten */
.card-cluster {
  grid-column: content-start / content-end;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--base-spacing);
}

/* 
  Subgrid Implementation:
  Setiap metric-card span 3 baris internal milik card-cluster? 
  TIDAK: card-cluster mengalirkan item secara horizontal, 
  maka baris individual ditangani per-cluster menggunakan Subgrid per Baris!
*/
.metric-card {
  display: grid;
  grid-row: span 3;
  grid-template-rows: subgrid;
  background-color: var(--color-surface);
  border-radius: 8px;
  padding: 1.25rem;
  border: 1px solid #334155;
}

/* 
  Koreksi Arsitektur untuk Subgrid Multi-Baris:
  card-cluster harus mengaktifkan grid baris implisit/eksplisit 
  agar subgrid child memiliki referensi track.
*/
.card-cluster {
  grid-auto-rows: auto;
  /* Mengatur item agar menduduki 3 baris grid cluster secara sinkron */
  grid-template-rows: auto 1fr auto;
}

.card-title {
  font-size: 1.2rem;
  color: var(--color-accent);
}

.card-body {
  font-size: 0.95rem;
  line-height: 1.5;
  color: #cbd5e1;
}

.card-footer button {
  background: transparent;
  color: var(--color-accent);
  border: 1px solid var(--color-accent);
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  width: 100%;
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Menganalisis baris-baris kritis pada implementasi CSS di atas:

* **Baris 24–29 (`.dashboard-grid`):**
  ```css
  grid-template-columns: 
    [full-start] minmax(1rem, 1fr) 
    [content-start] minmax(auto, 1200px) 
    [content-end] minmax(1rem, 1fr) 
    [full-end];
  ```
  Mendefinisikan sistem layout *viewport-centering* modern tanpa pembungkus wrapper ekstra. Named lines `[content-start]` dan `[content-end]` membatasi konten maksimal 1200px, sementara track tepi berfungsi sebagai dynamic gutters dengan ukuran minimal `1rem`.

* **Baris 38–40 (`.card-cluster`):**
  ```css
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  ```
  `auto-fit` memberitahu browser untuk membuat kolom sebanyak mungkin yang muat dalam container. Jika track kosong, dimensinya diciutkan menjadi 0px, dan sisa track meregang (`1fr`). Minimum `280px` menjamin bahwa pada viewport di bawah nilai ini, track akan membungkus ke baris baru secara intrinsic tanpa memerlukan `@media (max-width: ...)`.

* **Baris 48–50 (`.metric-card`):**
  ```css
  grid-row: span 3;
  grid-template-rows: subgrid;
  ```
  Ini adalah kunci Subgrid: Elemen `.metric-card` diinstruksikan mengambil 3 baris dari parent (`card-cluster`). Alih-alih membuat kalkulasi baris baru, `grid-template-rows: subgrid` mendelegasikan ukuran ketiga baris tersebut (Header, Body, Footer) langsung ke konteks parent. Hasilnya: Semua Header kartu memiliki tinggi sama (mengikuti judul terpanjang), semua Body meregang sinkron, dan semua Footer terparkir rata di baris paling bawah.

---

## SEKSI 09 — STUDI KASUS NYATA
### Enterprise Analytics Dashboard Layout Engine
**Skenario:** Platform Perbankan Enterprise memerlukan antarmuka dashboard analitik dengan spesifikasi berikut:
1. Multi-tier complex dashboard: Sticky Sidebar, Collapsible Contextual Rail, Dynamic Main Workspace.
2. Data Visualization Matrix: Komponen Card Widget modular di mana judul, visualisasi grafik, ringkasan analitik, dan panel aksi harus sejajar sempurna secara horizontal lintas seluruh kolom, meskipun volume payload teks dinamis via WebSocket.
3. Nol layout shifting saat konten teks berukuran besar masuk secara real-time.
4. Mendukung degradasi anggun (*graceful fallback*) untuk mesin render browser yang belum mengaktifkan subgrid secara penuh.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Arsitektur produksi ini memisahkan Layout Shell, Dynamic Grid Tracks, dan Subgrid Alignment System.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Analytics Dashboard Engine</title>
  <link rel="stylesheet" href="enterprise-dashboard.css">
</head>
<body>
  <div class="shell-layout">
    <aside class="shell-sidebar">
      <nav>Sidebar Navigation</nav>
    </aside>
    
    <header class="shell-topbar">
      <span>Dashboard Executive Overview</span>
    </header>

    <main class="shell-workspace">
      <div class="widget-matrix">
        
        <!-- Widget Item 1 -->
        <article class="data-widget">
          <header class="widget-header">
            <h3>Net Inflow Rate</h3>
            <span class="badge status-ok">Live</span>
          </header>
          <div class="widget-visual">
            <div class="mock-chart">[Chart: 124.5 ops/sec]</div>
          </div>
          <div class="widget-content">
            <p>Data settlement stabil tanpa antrian antarmuka tertahan.</p>
          </div>
          <footer class="widget-actions">
            <button class="btn primary">Audit Stream</button>
          </footer>
        </article>

        <!-- Widget Item 2 (Long Payload Text) -->
        <article class="data-widget">
          <header class="widget-header">
            <h3>Aggregate Liquidity Risk Profiling System with Real-Time Distributed Ledger Audit</h3>
            <span class="badge status-warn">Review</span>
          </header>
          <div class="widget-visual">
            <div class="mock-chart">[Chart: Volatility Spike 18.2%]</div>
          </div>
          <div class="widget-content">
            <p>Peringatan volatilitas terdeteksi di node regional AP-Southeast-1. Memerlukan penyesuaian alokasi cadangan modal segera sesuai parameter mitigasi risiko perbankan.</p>
          </div>
          <footer class="widget-actions">
            <button class="btn secondary">Karantina Node</button>
            <button class="btn primary">Tinjau Ledger</button>
          </footer>
        </article>

        <!-- Widget Item 3 -->
        <article class="data-widget">
          <header class="widget-header">
            <h3>Latency Engine</h3>
            <span class="badge status-ok">Live</span>
          </header>
          <div class="widget-visual">
            <div class="mock-chart">[Chart: p99 at 4.2ms]</div>
          </div>
          <div class="widget-content">
            <p>Kinerja cluster optimal.</p>
          </div>
          <footer class="widget-actions">
            <button class="btn primary">Audit Stream</button>
          </footer>
        </article>

      </div>
    </main>
  </div>
</body>
</html>
```

```css
/* enterprise-dashboard.css */
:root {
  --bg-app: #090d16;
  --bg-panel: #111827;
  --border-panel: #1f2937;
  --text-main: #f9fafb;
  --text-muted: #9ca3af;
  --color-primary: #2563eb;
  --color-success: #10b981;
  --color-warning: #f59e0b;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background-color: var(--bg-app);
  color: var(--text-main);
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  overflow-x: hidden;
}

/* Enterprise Shell Layout */
.shell-layout {
  display: grid;
  min-height: 100vh;
  grid-template-columns: 260px minmax(0, 1fr);
  grid-template-rows: 64px 1fr;
  grid-template-areas:
    "sidebar topbar"
    "sidebar workspace";
}

.shell-sidebar {
  grid-area: sidebar;
  background-color: var(--bg-panel);
  border-right: 1px solid var(--border-panel);
  padding: 1.5rem;
}

.shell-topbar {
  grid-area: topbar;
  background-color: var(--bg-panel);
  border-bottom: 1px solid var(--border-panel);
  display: flex;
  align-items: center;
  padding: 0 2rem;
  font-weight: 600;
}

.shell-workspace {
  grid-area: workspace;
  padding: 2rem;
  overflow-y: auto;
}

/* 
  Data Widget Matrix:
  Mengatur 4 baris per unit widget: 
  Row 1: Header | Row 2: Visual | Row 3: Content | Row 4: Actions
*/
.widget-matrix {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  /* Inisialisasi baris berulang: Title, Chart, Description, Actions */
  grid-auto-rows: auto auto 1fr auto;
}

/* Fallback untuk Browser non-subgrid: Flex-column layout */
.data-widget {
  background-color: var(--bg-panel);
  border: 1px solid var(--border-panel);
  border-radius: 8px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.data-widget .widget-content {
  flex-grow: 1;
}

/* Progressive Enhancement: Subgrid Engine */
@supports (grid-template-rows: subgrid) {
  .widget-matrix {
    /* 
      Setiap kali ada baris widget baru, ia mengalokasikan 4 track 
      dengan dynamic sizing intrinsik 
    */
    grid-auto-rows: min-content minmax(120px, auto) 1fr auto;
  }

  .data-widget {
    display: grid;
    /* Ambil 4 baris eksplisit dari parent */
    grid-row: span 4;
    grid-template-rows: subgrid;
    gap: 0; /* Jarak dikontrol oleh gap kontainer utama & internal padding */
    padding: 0;
  }

  .widget-header,
  .widget-visual,
  .widget-content,
  .widget-actions {
    padding: 1rem 1.25rem;
  }

  .widget-header {
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  .widget-actions {
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    align-self: end;
  }
}

/* Internal Visual Rules */
.widget-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.widget-header h3 {
  font-size: 1.1rem;
  font-weight: 600;
  line-height: 1.4;
}

.badge {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  text-transform: uppercase;
  font-weight: 700;
}

.status-ok { background: rgba(16, 185, 129, 0.2); color: var(--color-success); }
.status-warn { background: rgba(245, 158, 11, 0.2); color: var(--color-warning); }

.mock-chart {
  background-color: rgba(255, 255, 255, 0.02);
  border: 1px dashed var(--border-panel);
  height: 100%;
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-family: monospace;
}

.widget-content p {
  color: var(--text-muted);
  font-size: 0.9rem;
  line-height: 1.6;
}

.widget-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  border: none;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
}

.btn.primary { background: var(--color-primary); color: white; }
.btn.secondary { background: transparent; color: var(--text-muted); border: 1px solid var(--border-panel); }
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Karakteristik | Flexbox Layout | Standard Nested Grid | CSS Subgrid (Level 2) |
| :--- | :--- | :--- | :--- |
| **Dimensi Koordinasi** | 1D (Baris ATAU Kolom) | 2D Terisolasi (Hanya dalam lingkup elemen itu sendiri) | 2D Terpadu Lintas Hierarki DOM |
| **Penyelarasan Vertikal Antar Komponen Mandiri** | Sulit (Memerlukan manipulasi tinggi tetap/JavaScript) | Mustahil antar container yang berbeda | Otomatis melalui pewarisan baris (*row sharing*) |
| **Dukungan Peramban (Legacy)** | Universal (>99.5%) | Luas (>97%) | Modern Evergreen Browser (~91%) |
| **Kompleksitas Perhitungan Layout Mesin Peramban** | Rendah: $O(N)$ kalkulasi lokal per container | Menengah: $O(N \cdot M)$ independen | Tinggi: Graph dependency resolution dua arah |
| **Performa Reflow / Biaya Resize** | Sangat Rendah | Rendah-Sedang | Sedang-Tinggi jika kedalaman nesting ekstrem |
| **Semantik & Web Accessibility (A11y)** | Kadang memerlukan DIV wrapper wrapper artifisial | Memerlukan Flattening struktur DOM | Mempertahankan semantik murni HTML5 |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Grid Blowout Bug (`min-width: auto`)
* **Mekanisme Kegagalan:** Komponen grid berisi pre-formatted text (`<pre>`), canvas dengan ukuran tetap, string teks panjang tanpa spasi (URL/Hash sha256), atau elemen dengan `min-width: max-content`.
* **Root Cause:** Sesuai CSS Box Alignment Model, nilai default kolom grid adalah `minmax(auto, 1fr)`. Browser memprioritaskan konten intrinsik daripada mengecilkan kolom.
* **Mitigasi:**
  ```css
  /* Selalu override min-width/min-height pada track atau elemen anak */
  .grid-column-safe {
    grid-template-columns: minmax(0, 1fr);
  }
  .grid-item-child {
    min-width: 0;
    overflow-wrap: break-word;
  }
  ```

### 2. Collapsed Track Inheritance pada Subgrid
* **Mekanisme Kegagalan:** Subgrid meregang di atas rentang kolom yang memiliki nilai collapsed/empty karena aturan conditional responsive layout pada parent.
* **Root Cause:** Elemen subgrid menempati track yang dievaluasi menjadi lebar `0px` oleh parent grid, namun margin/padding internal subgrid tetap diterapkan sehingga menyebabkan luapan grafis (*graphical overflow glitch*).
* **Mitigasi:** Pastikan item subgrid memiliki definisi fallback eksplisit pada media queries saat rentang track parent berubah:
  ```css
  @media (max-width: 768px) {
    .data-widget {
      grid-row: auto; /* Putus subgrid contract pada viewport mobile */
      grid-template-rows: none;
      display: flex;
      flex-direction: column;
    }
  }
  ```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan `100%` alih-alih `1fr` pada Komposisi Gap
* *Kesalahan:*
  ```css
  grid-template-columns: 50% 50%;
  gap: 20px; /* Menghasilkan horizontal scrollbar / overflow container */
  ```
* *Koreksi:* Persentase dihitung terhadap lebar total container **sebelum** pengurangan gap. Gunakan unit `fr` yang secara implisit menghitung alokasi setelah pengurangan gap:
  ```css
  grid-template-columns: 1fr 1fr;
  gap: 20px; /* Lebar = (100% - 20px) / 2 per kolom */
  ```

### 2. Auto-placement Mengacak Urutan Navigasi Keyboard
* *Kesalahan:* Menggunakan `grid-auto-flow: dense` pada kumpulan form input dinamis atau kartu produk yang dapat diakses melalui tombol keyboard (`Tab`).
* *Koreksi:* Hindari `dense` jika urutan visual menyimpang drastis dari alur logis DOM tree. Jangan gunakan CSS untuk mengoreksi struktur data DOM yang salah urus.

### 3. Asumsi Bahwa Subgrid Mewarisi Sumbu Otomatis (X dan Y)
* *Kesalahan:*
  ```css
  .nested {
    display: grid;
    subgrid: true; /* BUKAN SINTAKSIS VALID */
  }
  ```
* *Koreksi:* Subgrid harus dideklarasikan secara eksplisit per sumbu:
  ```css
  .nested {
    display: grid;
    grid-template-columns: subgrid; /* Mengadopsi kolom saja */
    grid-template-rows: auto auto;   /* Baris independen */
  }
  ```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Desain Sistem Terbuka Menggunakan Named Areas yang Konsisten:**
   Gunakan pemetaan semantic grid area string yang memvisualisasikan template secara deklaratif.
   ```css
   .enterprise-layout {
     grid-template-areas:
       "header header"
       "nav    main"
       "footer footer";
   }
   ```
2. **Definisikan Garis Grid dengan Pasangan Semantic Names:**
   Gunakan konvensi penamaan akhiran `-start` dan `-end` untuk memicu penetapan implisit area secara otomatis:
   ```css
   grid-template-columns: [main-start] 1fr [main-end];
   /* Secara otomatis memvalidasi grid-column: main; */
   ```
3. **Decouple Breakpoints dari Layout Components:**
   Manfaatkan `minmax()` yang digabung dengan `repeat(auto-fit, ...)` untuk mengizinkan komponen mengatur dirinya sendiri sesuai lebar kontainer induknya (*container-responsive mindset*).

---

##