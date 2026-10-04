# Bab 02 Module 01: Visual Formatting Model, Box Dynamics, & Paint Profiling

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran:** 03-Frontend-and-Mobile
* **Kurikulum:** CSS Core Internals & Performance Engineering
* **Bab:** 02 (Render Tree, Geometry, and Compositing)
* **Modul:** 01
* **Judul:** Visual Formatting Model, Box Dynamics, & Paint Profiling
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat:** DOM Tree Construction, CSSOM Computation, Dasar-dasar Pipeline Rendering Browser (Recalc Style, Layout, Paint, Composite).

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, Anda diharapkan mampu:

1. **Membongkar Mekanisme Visual Formatting Model (VFM):** Mengidentifikasi bagaimana browser mentransformasikan node CSSOM menjadi box geometries konkret di layar melalui perhitungan Block Formatting Context (BFC), Inline Formatting Context (IFC), dan Stacking Context.
2. **Menganalisis Box Dynamics Secara Matematis:** Menghitung sizing constraints (`box-sizing`, `min/max-content`, intrinsic vs. extrinsic sizing) dan margin collapse algorithm secara presisi di level engine rendering.
3. **Mengisolasi Paint Profiling:** Melakukan audit layout thrashing, paint invalidation, dan compositing triggers menggunakan Chrome DevTools Performance & Rendering Profiler.
4. **Menerapkan Arsitektur Bebas Reflow:** Merancang layout UI kompleks dengan jaminan $0\text{ layout shift}$ ($CLS = 0$) dan isolasi grafis berbasis hardware acceleration (`transform`, `opacity`, `will-change`, CSS Containment).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Dari "Styling Deklaratif" ke "Instruksi Pipeline Geometri & Rasterisasi"

Banyak pengembang memandang CSS sebagai lembar konfigurasi visual sederhana. Dalam skala produksi enterprise berkinerja tinggi, CSS harus dipahami sebagai **bahasa instruksi kompilasi antarmuka**. Setiap deklarasi properti memengaruhi struktur graf internal engine browser:

```
[CSS Rules] 
    │
    ▼
[Calculated Style Rules] 
    │
    ▼
[Box Generation & Geometry Calculations (CPU Bound)] 
    │
    ▼
[Rasterization & Layer Tree Generation (CPU/Skia Bound)] 
    │
    ▼
[Draw Calls Submission to GPU VRAM (GPU Bound)]
```

### Mental Model: Box Dynamics Bukanlah Piksel Statis

Kotak (Box) pada CSS bukanlah sekadar area piksel empat persegi panjang. Sebuah *Box* adalah node topologi fleksibel yang memiliki:
* **Dimensi Intrinsik vs. Ekstrinsik:** Kemampuan menentukan ukuran berdasarkan beban konten di dalamnya vs. paksaan batas dari kontainer induknya.
* **Formatting Context:** Ruang lingkup isolasi algoritma penataan layout (BFC, IFC, FFC, GFC).
* **Layering & Paint Tree:** Representasi 3 dimensi ($X$, $Y$, dan indeks $Z$) yang menentukan urutan penggambaran (paint order) piksel sebelum dikirimkan ke compositing thread.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram visual pipeline eksekusi Visual Formatting Model serta lifecycle Box Invalidation yang memicu Paint/Composite dalam rendering engine (seperti Blink / Chromium):

```
+-------------------------------------------------------------------------------+
|                           DOM + CSSOM RESOLUTION                              |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+-------------------------------------------------------------------------------+
|                            LAYOUT TREE GENERATION                             |
|  - Menyaring 'display: none'                                                  |
|  - Menggenerasi Anonymous Blocks/Inline Boxes                                 |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+-------------------------------------------------------------------------------+
|                         VISUAL FORMATTING MODEL (VFM)                         |
|  +---------------------------+             +-------------------------------+  |
|  | Block Formatting Context  |  <=======>  |   Inline Formatting Context   |  |
|  | - Vertical Box Stacking   |             |   - Horizontal Line Boxes     |  |
|  | - Margin Collapsing Rules |             |   - Baseline Alignment        |  |
|  +---------------------------+             +-------------------------------+  |
|                                     │                                         |
|                                     ▼                                         |
|  +-------------------------------------------------------------------------+  |
|  | Sizing Pass (min-content, max-content, auto margin calculation)         |  |
|  +-------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+-------------------------------------------------------------------------------+
|                         PAINT INVALIDATION & RECORDING                        |
|  - Penentuan Stacking Contexts (z-index, opacity, transform)                  |
|  - Perekaman Display Items (Draw commands: DrawRect, DrawText via Skia)       |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+-------------------------------------------------------------------------------+
|                             COMPOSITING ENGINE                                |
|  +-------------------------------------------------------------------------+  |
|  | Layerization: Pemisahan GraphicsLayers (will-change, transform3d)       |  |
|  +-------------------------------------------------------------------------+  |
|  | Tiling: Memecah layer besar menjadi grid 256x256 / 512x512 piksel       |  |
|  +-------------------------------------------------------------------------+  |
|  | Raster Thread: Konversi instruksi Skia ke Bitmap via GPU (cc/raster)    |  |
|  +-------------------------------------------------------------------------+  |
|                                     │                                         |
|                                     ▼                                         |
|                              GPU DRAW CALLS                                   |
|                        (Quad Rendering ke Layar)                              |
+-------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Anatomy of CSS Boxes
Setiap box pada Visual Formatting Model terdiri atas empat area konsentris:

$$\text{Total Box Boundary} = \text{Content} + \text{Padding} + \text{Border} + \text{Margin}$$

* **Content Box:** Memuat teks atau elemen pengganti (replaced elements seperti `<img>`, `<video>`).
* **Padding Box:** Buffer internal di sekitar konten. Background dari elemen dirender hingga batas terluar padding (secara default jika `background-clip: border-box`, namun menutupi padding).
* **Border Box:** Batas fisik elemen. Properti `box-sizing: border-box` mengunci total ukuran (`width`/`height`) ke perimeter ini.
* **Margin Box:** Buffer isolasi eksternal antar-box.

### 2. Algoritma Margin Collapsing
Margin collapsing adalah perilaku fundamental dalam BFC di mana margin vertikal (top dan bottom) dari dua box digabungkan menjadi satu margin tunggal. Nilai kalkulasi matematisnya adalah:

$$\text{Margin Akhir} = 
\begin{cases} 
\max(M_1, M_2) & \text{jika } M_1 \ge 0 \land M_2 \ge 0 \\
M_{\text{positif}} - |M_{\text{negatif}}| & \text{jika } M_1 \cdot M_2 < 0 \\
- \max(|M_1|, |M_2|) & \text{jika } M_1 < 0 \land M_2 < 0 
\end{cases}$$

Margin collapsing **hanya** terjadi pada:
* Sibling yang berdekatan vertikal dalam in-flow layout.
* Parent dan first/last child jika tidak ada border, padding, inline content, atau clearance yang memisahkan mereka.
* Empty blocks (margin top dan bottom milik elemen itu sendiri saling bertubrukan).

### 3. Formatting Contexts Demystified
* **Block Formatting Context (BFC):** Region terisolasi di mana elemen-elemen diletakkan secara vertikal satu demi satu, dimulai dari batas atas containing block. Elemen float tidak keluar dari batas BFC induk, dan margin antar-BFC yang independen tidak runtuh (do not collapse).
* **Inline Formatting Context (IFC):** Region horizontal di mana elemen diatur dalam "line boxes". Line box memiliki tinggi sebesar elemen inline tertinggi atau baseline alignment, dan membungkus (wraps) ke baris berikutnya jika ruang horizontal habis.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Trigger Pembentukan Block Formatting Context (BFC)
BFC baru terbentuk secara deterministik jika elemen memenuhi salah satu kriteria berikut:
1. Elemen root dokumen (`<html>`).
2. Nilai `float` selain `none`.
3. Nilai `position` berupa `absolute` atau `fixed`.
4. Nilai `display` berupa `inline-block`, `table-cell`, `table-caption`.
5. Nilai `display: flow-root` (metode standar, murni, dan bebas efek samping).
6. Elemen dengan `overflow` selain `visible` atau `clip`.
7. Nilai `contain` dengan nilai `layout`, `content`, atau `paint`.
8. Flex items (`display: flex` / `inline-flex` children) jika mereka bukan flex container itu sendiri.
9. Grid items (`display: grid` / `inline-grid` children).
10. Multicolumn container (`column-count` atau `column-width` bukan `auto`).

### Stacking Context: Aturan Deterministik Z-Index
Z-index **tidak** beroperasi secara absolut global. Ia bekerja di dalam lokalitas Stacking Context. Pembentukan Stacking Context terjadi bila elemen:
* Menjadi dokumen root (`<html>`).
* Memiliki `position: relative`/`absolute` dengan `z-index` bernilai bilangan bulat selain `auto`.
* Memiliki `position: fixed` atau `sticky`.
* Menggunakan `display: flex` atau `grid` dengan `z-index` selain `auto`.
* Memiliki nilai `opacity` kurang dari `1`.
* Menerapkan salah satu dari properti mutasi GPU/Shader: `transform`, `filter`, `perspective`, `clip-path`, `mask` selain `none`.
* Menggunakan `mix-blend-mode` selain `normal`.
* Memiliki deklarasi `isolation: isolate`.
* Memiliki deklarasi `will-change` yang mengarah ke salah satu properti di atas.

#### Hierarki Paint Order dalam Satu Stacking Context (Terbawah ke Teratas):
1. Background dan borders dari stacking context root element.
2. Descendants dengan posisi ber-z-index negatif (terurut dari minus terbesar hingga terendah).
3. In-flow, non-inline-level descendants (elemen blok normal).
4. Non-positioned floats.
5. In-flow, inline-level descendants (teks, inline boxes).
6. Descendants dengan `z-index: 0` atau `z-index: auto` yang memiliki posisi (`position: relative`, dll).
7. Descendants dengan posisi ber-z-index positif (terurut dari terkecil hingga terbesar).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode pengujian pembentukan BFC, pencegahan Margin Collapse, serta isolasi Stacking Context.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>VFM Deep Dive</title>
  <style>
    /* Reset Box Model Universal */
    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    .test-wrapper {
      padding: 40px;
      background: #f4f4f9;
      font-family: monospace;
    }

    /* Kasus 1: Margin Collapse Eksplisit */
    .collapse-container {
      background: #e2e8f0;
      margin-bottom: 30px;
    }
    .box-a {
      height: 60px;
      background: #f87171;
      margin-bottom: 40px; /* Margin ini akan collapse dengan box-b */
    }
    .box-b {
      height: 60px;
      background: #60a5fa;
      margin-top: 20px;    /* 40px vs 20px => Jarak aktual = 40px */
    }

    /* Kasus 2: Mencegah Margin Collapse dengan BFC Modern */
    .bfc-container {
      display: flow-root; /* Standar modern pemicu BFC */
      background: #cbd5e1;
      margin-top: 20px;
    }
    .bfc-container .box-a {
      margin-bottom: 20px;
    }
    .bfc-container .box-b {
      margin-top: 20px; /* Jarak tetap 20px antar anak, namun parent terisolasi */
    }

    /* Kasus 3: Stacking Context Isolation */
    .parent-layer {
      position: relative;
      isolation: isolate; /* Menciptakan Stacking Context Mandiri */
      background: #ffffff;
      padding: 20px;
      border: 1px solid #94a3b8;
    }
    .child-under {
      position: absolute;
      top: 10px;
      left: 10px;
      width: 100px;
      height: 100px;
      background: #fbbf24;
      z-index: 9999; /* Z-index tinggi ini terisolasi di dalam parent-layer */
    }
    .sibling-layer {
      position: relative;
      z-index: 10;
      width: 150px;
      height: 50px;
      background: #34d399;
      margin-top: 20px;
    }
  </style>
</head>
<body>
  <div class="test-wrapper">
    <h2>1. Margin Collapsing Pipeline</h2>
    <div class="collapse-container">
      <div class="box-a">Box A (MB: 40px)</div>
      <div class="box-b">Box B (MT: 20px)</div>
    </div>

    <h2>2. BFC Container (flow-root)</h2>
    <div class="bfc-container">
      <div class="box-a">Box A (MB: 20px)</div>
      <div class="box-b">Box B (MT: 20px)</div>
    </div>

    <h2>3. Stacking Context (isolation: isolate)</h2>
    <div class="parent-layer">
      Parent Context
      <div class="child-under">Child (z: 9999)</div>
    </div>
    <div class="sibling-layer">
      Sibling Layer (z: 10)
    </div>
  </div>
</body>
</html>
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 10–14:**
  ```css
  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  ```
  *Mekanisme:* Mengubah model dimensi default dari `content-box` (W3C standard historis) ke `border-box`. Lebar dan tinggi elemen kini mengunci batas terluar border. Ini meniadakan penambahan kalkulasi matematis `width + padding + border` yang sering menyebabkan overflow tak diinginkan.
* **Baris 27–36:**
  ```css
  .box-a { margin-bottom: 40px; }
  .box-b { margin-top: 20px; }
  ```
  *Mekanisme:* Engine browser mengevaluasi kedua elemen yang berada di dalam BFC yang sama. Berdasarkan algoritma $\max(40, 20)$, ruang antara `.box-a` dan `.box-b` di-resolve tepat menjadi $40\text{px}$, bukan $60\text{px}$. Margin $20\text{px}$ milik `.box-b` "runtuh" (collapsed) ke dalam margin milik `.box-a`.
* **Baris 39–43:**
  ```css
  .bfc-container {
    display: flow-root;
  }
  ```
  *Mekanisme:* Properti `display: flow-root` secara eksplisit menginstruksikan layout engine untuk membuat Block Formatting Context baru pada elemen tersebut tanpa efek samping visual (seperti `overflow: hidden` yang memotong bayangan/shadow, atau float clearfix hack).
* **Baris 54–60:**
  ```css
  .parent-layer {
    position: relative;
    isolation: isolate;
  }
  ```
  *Mekanisme:* `isolation: isolate` memaksa browser membangun Stacking Context baru. Node ini kini menjadi acuan referensi dasar bagi semua z-index turunannya.
* **Baris 61–68:**
  ```css
  .child-under {
    position: absolute;
    z-index: 9999;
  }
  ```
  *Mekanisme:* Nilai `z-index: 9999` tidak akan pernah mampu menembus atau menutupi `.sibling-layer` di luar `.parent-layer` jika `.sibling-layer` memiliki koordinat z-index lebih tinggi dalam tatanan konteks stacking di level root dokumen.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Financial Trading Dashboard Virtualized Feed
Pada aplikasi web terminal trading frekuensi tinggi, antarmuka memproses render ratusan order-book rows per detik. Masalah yang dihadapi:
1. **Critical Jank & Frame Drop:** Frame rate anjlok dari $60\text{ fps}$ menjadi $< 18\text{ fps}$ setiap kali data masuk via WebSocket.
2. **Root Cause Analysis via Chrome Profiler:**
   * Penggunaan `width: auto` bersamaan dengan `margin` dinamis pada item baris order menyebabkan invalidasi berantai (global reflow / layout cascade).
   * Elemen baris tabel menggunakan `z-index` tanpa manajemen Stacking Context yang tepat, memaksa browser mengkalkulasi ulang urutan paint (*Paint Invalidation*) pada seluruh root layer canvas setiap kali baris baru masuk.

### Solusi Teknis:
1. Menghilangkan ketergantungan kalkulasi otomatis dimensi induk dengan menerapkan **CSS Intrinsic Sizing** dan **BFC Boundary Isolation**.
2. Menerapkan `contain: strict` pada baris order untuk memutus keterkaitan Layout, Style, dan Paint antara elemen baris dan dokumen luar.
3. Mengisolasi mutasi harga/nilai transaksi ke GPU composited layers via `transform: translateZ(0)` atau `will-change: transform`.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi komponen list ticker berkinerja tinggi yang dirancang untuk mencegah Layout Thrashing dan meminimalisasi Paint Boundaries.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>High-Performance Order Stream</title>
  <style>
    :root {
      --row-height: 36px;
      --color-bid: #10b981;
      --color-ask: #ef4444;
      --bg-dark: #0f172a;
      --bg-surface: #1e293b;
    }

    body {
      background-color: var(--bg-dark);
      color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 0;
      padding: 24px;
    }

    .order-book-container {
      width: 100%;
      max-width: 450px;
      border: 1px solid #334155;
      border-radius: 6px;
      background: var(--bg-surface);
      /* Membatasi dampak layout & paint hanya di dalam kontainer ini */
      contain: layout paint;
    }

    .order-book-header {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      padding: 8px 16px;
      font-size: 12px;
      text-transform: uppercase;
      color: #94a3b8;
      border-bottom: 1px solid #334155;
    }

    .order-stream-viewport {
      height: 360px;
      overflow-y: auto;
      position: relative;
      /* Memastikan scroll layer terpisah dalam Compositor */
      will-change: transform;
    }

    /* Target Komponen Berkinerja Tinggi */
    .order-row {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      align-items: center;
      height: var(--row-height);
      padding: 0 16px;
      font-size: 13px;
      font-variant-numeric: tabular-nums;
      border-bottom: 1px solid #1e293b;

      /* ISOLASI EKSTREM:
         strict = contain: size layout paint style
         Browser mematikan propagasi mutasi dari/ke node ini */
      contain: strict;
      content-visibility: auto;
      contain-intrinsic-size: 0 var(--row-height);
    }

    .order-row[data-side="bid"] .price { color: var(--color-bid); }
    .order-row[data-side="ask"] .price { color: var(--color-ask); }

    .align-right { text-align: right; }

    /* Indikator Volume Bar yang dirender langsung di GPU */
    .volume-bar {
      position: absolute;
      top: 0;
      right: 0;
      bottom: 0;
      opacity: 0.15;
      pointer-events: none;
      transform-origin: right center;
      /* Animasi/mutasi hanya memengaruhi Composite thread */
      will-change: transform;
      background: currentColor;
    }
  </style>
</head>
<body>

  <div class="order-book-container">
    <div class="order-book-header">
      <span>Price (USD)</span>
      <span class="align-right">Size</span>
      <span class="align-right">Time</span>
    </div>
    <div class="order-stream-viewport" id="viewport">
      <!-- Diisi secara dinamis -->
    </div>
  </div>

  <script>
    // Generator Baris Performa Tinggi: Menghindari Layout Thrashing
    const viewport = document.getElementById('viewport');
    const TOTAL_ROWS = 10;

    function initRows() {
      const fragment = document.createDocumentFragment();
      for (let i = 0; i < TOTAL_ROWS; i++) {
        const row = document.createElement('div');
        row.className = 'order-row';
        row.id = `row-${i}`;
        row.setAttribute('data-side', i % 2 === 0 ? 'bid' : 'ask');
        
        row.innerHTML = `
          <span class="price">00,000.00</span>
          <span class="size align-right">0.0000</span>
          <span class="time align-right">00:00:00</span>
        `;
        fragment.appendChild(row);
      }
      viewport.appendChild(fragment);
    }

    // Mutasi Data: 0 Layout Reflow Phase
    function updateRowMetrics(index, price, size, time, side) {
      const row = document.getElementById(`row-${index}`);
      if (!row) return;

      // Update tekstual tidak memicu layout reflow global karena contain: strict
      row.children[0].textContent = price.toFixed(2);
      row.children[1].textContent = size.toFixed(4);
      row.children[2].textContent = time;
      
      if (row.getAttribute('data-side') !== side) {
        row.setAttribute('data-side', side);
      }
    }

    initRows();

    // Simulasi Stream WebSocket 60fps
    let tick = 0;
    function simulateWebSocketTick() {
      const targetIndex = tick % TOTAL_ROWS;
      const basePrice = 64000 + Math.random() * 200;
      const baseSize = Math.random() * 2;
      const now = new Date().toTimeString().split(' ')[0];
      const side = Math.random() > 0.5 ? 'bid' : 'ask';

      updateRowMetrics(targetIndex, basePrice, baseSize, now, side);

      tick++;
      requestAnimationFrame(simulateWebSocketTick);
    }

    requestAnimationFrame(simulateWebSocketTick);
  </script>
</body>
</html>
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Mekanisme Isolasi / Layout | Keuntungan (Pros) | Biaya / Kerugian (Cons) | Skenario Terbaik |
| :--- | :--- | :--- | :--- |
| **`contain: strict`** | Memutus seluruh dependensi layout & paint subtree. Menurunkan recalculate style time hingga $\approx 90\%$. | Elemen wajib memiliki ukuran eksplisit (`width` & `height`). Kegagalan alokasi memicu collapse to $0\times 0\text{px}$. | Virtual list, tabel data besar, reusable card widget independen. |
| **`isolation: isolate`** | Menghindari polusi indeks visual global secara terkontrol tanpa mengubah z-index lokal anak. | Menambah kedalaman pohon Stacking Context pada memory engine browser. | Desain sistem komponen hierarkis (modal, tooltip, dropdown). |
| **`display: flow-root`** | Membuat BFC murni tanpa memotong visual clipping (aman dari `box-shadow` terpotong). | Tidak memutus isolasi ukuran layout sekuat `contain: layout`. | Micro-layout wrapping, meredam fenomena margin-collapse lokal. |
| **`will-change: transform`** | Mengangkat node ke Layer GPU independen, rendering via Compositor thread ($60\text{–}120\text{ fps}$). | Alokasi VRAM GPU membengkak drastis (*Layer Explosion*). Berpotensi memicu text blurry. | Animasi transformasi, off-canvas sliding menu, real-time visualizer. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Zero-Pixel Collapse pada `contain: size`
Jika Anda menetapkan `contain: size` atau `contain: strict` pada kontainer yang mengandalkan dimensi konten intrinsik (`height: auto`), engine browser mengabaikan tinggi konten anaknya dan meresolusi tinggi induk menjadi $0\text{px}$.
* *Mitigasi:* Selalu sertakan deklarasi `contain-intrinsic-size: <width> <height>` sebagai nilai *fallback* geometri sebelum konten diproses atau terapkan tinggi fix eksplisit.

### 2. Efek Samping Sub-Pixel Rendering pada Stacking Context Baru
Ketika sebuah elemen diangkat menjadi Stacking Context melalui properti seperti `opacity: 0.99` atau `transform: translateZ(0)`, browser sering kali melepaskan teknik *Subpixel Antialiasing* pada teks dan beralih ke *Grayscale Antialiasing*. Teks terlihat mendadak lebih tipis atau buram (*blurry text*).
* *Mitigasi:* Hindari penggunaan pseudo-hacks `translateZ(0)` sembarangan hanya untuk mengangkat elemen; gunakan hanya ketika profiling membuktikan adanya paint bottleneck.

### 3. Margin Collapsing pada Elemen Kosong
Elemen `<div></div>` tanpa border, padding, maupun content height, yang memiliki `margin-top: 20px` dan `margin-bottom: 20px`, akan menghasilkan margin akhir sebesar $20\text{px}$ (bukan $40\text{px}$) akibat *self-collapsing*. Jika elemen ini berdampingan dengan elemen lain, ketiga margin tersebut berkolaps menjadi satu nilai $\max$.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Clearfix Menggunakan Hacks Klasik
* *Anti-Pattern:*
  ```css
  .container::after {
    content: "";
    display: table;
    clear: both;
  }
  ```
* *Koreksi:*
  ```css
  .container {
    display: flow-root; /* Membentuk BFC modern secara deterministik */
  }
  ```

### Kesalahan 2: Memaksa z-index Maksimal untuk Menyelesaikan Tumpang Tindih
* *Anti-Pattern:* Menulis `z-index: 9999999 !important;` ketika modal atau tooltip tertutup elemen lain.
* *Koreksi:* Periksa *ancestor chain*. Jika parent memiliki Stacking Context dengan nilai z-index lebih rendah dari sibling parent tersebut, modifikasi parent stacking level menggunakan `isolation: isolate` atau restrukturisasi posisi DOM tree.

### Kesalahan 3: Memanipulasi Geometri dalam Loop Animasi
* *Anti-Pattern:* Menganimasikan posisi via properti `top`, `left`, `margin`, atau `padding`. Tindakan ini memicu: `Recalculate Style -> Layout -> Paint -> Composite` setiap frame ($16.6\text{ms}$).
* *Koreksi:* Gunakan strictly `transform: translate3d(x, y, 0)`. Hal ini melewati fase *Layout* dan *Paint*, mendelegasikan pembaruan langsung ke GPU *Compositor Thread*.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Explicit Box-Sizing Enforcement:** Tetapkan `border-box` pada universal selector di layer paling dasar CSS architecture.
2. **Predictable Component Rooting:** Gunakan `display: flow-root` pada level atomik komponen agar margin internal tidak bocor keluar (*margin leakage*) ke layout global.
3. **Intentional GPU Promotion:** Hindari menerapkan `will-change` secara statis pada ratusan elemen di stylesheet. Terapkan secara dinamis melalui JavaScript sesaat sebelum animasi berjalan (`mouseenter`), dan hapus begitu animasi selesai (`transitionend`).
4. **Isolate Component Stacking:** Gunakan `isolation: isolate` pada level komponen web (`custom-element` atau React/Vue component wrapper) untuk mencegah z-index leak ke document context.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Layout Thrashing (Forced Synchronous Layout)
Layout Thrashing terjadi ketika JavaScript membaca metrik geometri layout lalu langsung menulis perubahan gaya visual ke DOM secara bergantian dalam loop sinkron:

```javascript
// BURUK: Menyebabkan layout dihitung ulang berulang kali dalam satu frame
elements.forEach(el => {
  const height = el.offsetHeight; // READ: Browser terpaksa mengeksekusi Layout seketika
  el.style.height = `${height + 10}px`; // WRITE: Mengotori layout (dirty flag)
});

// OPTIMAL: Batching Read/Write Phase
const heights = elements.map(el => el.offsetHeight); // Batch READ
elements.forEach((el, i) => {
  el.style.height = `${heights[i] + 10}px`; // Batch WRITE
});
```

### VRAM Budgeting & Layer Squashing
Membuat layer baru (`will-change: transform`) membutuhkan memori GPU (VRAM):

$$\text{Alokasi VRAM} \approx \text{Width} \times \text{Height} \times 4 \text{ bytes (RGBA)}$$

Untuk layar Retina $4\text{K}$, satu layer berukuran penuh memakan:

$$3840 \times 2160 \times 4 \text{ bytes} \approx 33.17\text{ MB VRAM}$$

Terlalu banyak layer grafis memicu fenomena **Layer Explosion**, yang menyebabkan alokasi memori berlebih dan memicu tab browser crash pada perangkat mobile dengan memori terbatas.

---

## SEKSI 16 — KEAMANAN & HARDENING

Meskipun Visual Formatting Model berfokus pada layout, kesalahan arsitektur VFM dapat membuka celah keamanan:

1. **Clickjacking via Box Overlay Abuse:** 
   Penyerang dapat menyusun iframe tak terlihat di atas tombol penting menggunakan `opacity: 0`, manipulasi `z-index`, dan `pointer-events: auto`.
   * *Mitigasi:*
     ```http
     Content-Security-Policy: frame-ancestors 'none';
     X-Frame-Options: DENY
     ```
2. **CSS Injection / Exfiltration melalui Font Metrics:**
   Penyerang mengeksfiltrasi nilai input karakter dengan melacak layout shift saat font kustom memicu fallback layout width.
   * *Mitigasi:* Terapkan sanitasi ketat pada input user, batasi CSS `@font-face` eksternal via Content Security Policy (`font-src 'self'`).

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### Diagnostic Langkah demi Langkah Menggunakan Chrome DevTools:

1. **Memeriksa Repaint Area:**
   * Buka DevTools (`F12`) $\rightarrow$ Tekan `Cmd+Shift+P` (Mac) atau `Ctrl+Shift+P` (Windows).
   * Ketik `Show Rendering`.
   * Centang **Paint Flashing**. Setiap area yang digambar ulang oleh CPU Skia akan berkedip hijau. Jika seluruh layar berkedip hijau saat perubahan minor, Anda mengalami masalah invalidasi BFC/Stacking Context global.
2. **Memeriksa Layer Tree & Compositing Reasons:**
   * Buka panel **Layers** di DevTools.
   * Identifikasi layer aktif: Analisis parameter *Composite Reasons* untuk mengetahui apakah elemen dipromosikan ke layer tersendiri akibat `will-change`, `transform 3D`, atau *Squashing Culprit*.
3. **Menganalisis Layout Invalidation via Performance Panel:**
   * Rekam trace selama $3\text{ detik}$.
   * Identifikasi tanda segitiga merah pada task bar bertuliskan **Forced Reflow**. Periksa *Call Tree* untuk mengidentifikasi baris JavaScript yang memicu akses properti geometri seperti `getBoundingClientRect()`, `offsetTop`, atau `getComputedStyle()`.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **`display: flow-root`:** Pemicu BFC modern tanpa efek samping. Menyerap margin collapse anak dan mengurung elemen float.
* **`box-sizing: border-box`:** Mengunci kalkulasi total lebar ke perimeter border (`content + padding + border`).
* **Margin Collapse Formula:** $\max(M_1, M_2)$ untuk margin positif; nilai negatif mengurangi nilai positif terbesar.
* **Stacking Context Triggers:** `opacity < 1`, `transform !== none`,