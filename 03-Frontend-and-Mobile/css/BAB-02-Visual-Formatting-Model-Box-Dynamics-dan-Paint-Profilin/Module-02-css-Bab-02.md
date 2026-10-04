# Kurikulum Rekayasa Perangkat Lunak Enterprise: Visual Formatting Model, Box Dynamics, & Paint Profiling

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengidentifikasi dan memanipulasi algoritma pembuatan *Box* dalam *Visual Formatting Model* (VFM) pada level spesifikasi W3C.
- Membedah dan mengendalikan siklus hidup *Formatting Contexts* (Block, Inline, Flex, Grid) serta perilakunya terhadap *Margin Collapsing* dan *Out-of-flow Positioning*.
- Mengisolasi dan mengontrol *Stacking Context Tree* untuk mencegah *z-index leakage* pada arsitektur UI skala besar.
- Mengimplementasikan konsep *Intrinsic* dan *Extrinsic Sizing* (`min-content`, `max-content`, `fit-content`) serta *CSS Logical Properties* dalam rancang bangun sistem desain responsif multi-arah.
- Melakukan profil perenderan mendalam (*Paint Profiling*) menggunakan browser DevTools untuk mendeteksi *forced reflow*, *layout thrashing*, dan *paint invalidation*.
- Menerapkan arsitektur compositing modern (`will-change`, `contain`, `content-visibility`) untuk memaksimalkan *hardware acceleration* tanpa memicu *VRAM bloat*.

---

## 2. Prerequisites
Sebelum mempelajari modul ini, Anda wajib menguasai:
- **DOM & CSSOM Tree Construction**: Siklus penguraian token HTML/CSS hingga pembentukan pohon objek render.
- **Rendering Pipeline Fundamental**: Urutan alur kerja browser: *Parse* $\rightarrow$ *Style* $\rightarrow$ *Layout* $\rightarrow$ *Paint* $\rightarrow$ *Composite*.
- **JavaScript Execution Cycle**: Pemahaman microtasks, macrotasks, dan mekanisme antrean `requestAnimationFrame`.
- **Dasar DevTools Performance Panel**: Kemampuan dasar membaca *timeline recording* pada Chromium-based browser.

---

## 3. Concept & Internal Architecture

### 3.1. Visual Formatting Model (VFM) & Box Tree Generation
Browser tidak langsung merender DOM Tree ke layar. Engine seperti Chromium (Blink) mentransformasikan **DOM Tree** + **CSSOM Tree** menjadi **LayoutObject Tree** (Box Tree).

```
[DOM Tree] + [CSSOM] 
       │
       ▼
 [RenderTree / LayoutObject Tree]
       │  (Menghitung geometri: X, Y, Width, Height)
       ▼
 [PaintLayer Tree]
       │  (Menentukan Stacking Context, Opacity, Clipping)
       ▼
 [GraphicsLayer / cc::Layer Tree]
       │  (Layering untuk Compositor Thread & GPU)
       ▼
 [Display Item List / Paint Artifacts]
       │  (Rasterisasi via Skia / Ganesh / Graphite)
       ▼
    [GPU VRAM / Screen]
```

Setiap elemen menghasilkan nol atau lebih *boxes* berdasarkan properti `display`:
- `display: none`: Elemen dan keturunannya tidak dimasukkan ke dalam Layout Tree (menghancurkan Box).
- `visibility: hidden`: Box tetap dihitung dalam Layout Tree (mengonsumsi ruang geometris), namun dilewati pada tahap *Paint*.
- `display: contents`: Elemen induk tidak menghasilkan Box geometris tersendiri; anak-anaknya dipromosikan seolah-olah menjadi anak langsung dari kontainer di atasnya.

### 3.2. Block Formatting Context (BFC) Internals
BFC adalah region terisolasi di mana elemen dirender secara vertikal mulai dari batas atas kontainer. Karakteristik utama BFC:
1. Margin vertikal antara dua box bertetangga hanya mengalami *collapse* jika keduanya berada dalam BFC yang sama tanpa sekat pembatas.
2. Batas terluar (border box) dari BFC tidak boleh tumpang tindih (*overlap*) dengan area `float`.
3. BFC mengkalkulasi ketinggian elemen `float` di dalamnya (mencegah fenomena *collapsed parent height*).

Kondisi pembuat BFC modern menurut spesifikasi *CSS Display Level 3*:
- `display: flow-root` (Metode standar tanpa efek samping).
- `overflow: hidden`, `auto`, atau `scroll` (bukan `visible`).
- Elemen dengan `position: absolute` atau `position: fixed`.
- Flex items (`display: flex` / `inline-flex`) dan Grid items (`display: grid` / `inline-grid`).
- `contain: layout`, `contain: paint`, atau `contain: strict`.

### 3.3. Stacking Context Tree Architecture
Rendering z-axis diatur oleh hierarki *Stacking Context*. Browser merender elemen ke layar dalam urutan bertingkat dari belakang ke depan (Back-to-Front Order):

```
       [Urutan Layer Stacking Context (Belakang ke Depan)]
─────────────────────────────────────────────────────────────────
 1. Background & Border dari elemen akar stacking context
 2. Child Stacking Contexts dengan z-index bernilai negatif
 3. In-Flow, non-inline-level, non-positioned descendant boxes
 4. Non-positioned float boxes
 5. In-Flow, inline-level descendant boxes
 6. Child Stacking Contexts dengan z-index: 0 / 'auto'
 7. Child Stacking Contexts dengan z-index positif (1, 2, ...)
─────────────────────────────────────────────────────────────────
```

Kondisi pembentukan Stacking Context:
- Root element (`<html>`).
- Elemen dengan `position: absolute` atau `relative` dengan `z-index` selain `auto`.
- Elemen dengan `position: fixed` atau `sticky`.
- Elemen dengan `opacity` kurang dari `1`.
- Elemen dengan properti transformasional: `transform`, `filter`, `perspective`, `clip-path`, `mask` bukan `none`.
- Elemen dengan `isolation: isolate`.
- Elemen dengan `mix-blend-mode` selain `normal`.

### 3.4. Pipeline Engine: Layout vs Paint vs Compositing
- **Layout / Reflow**: Browser menghitung ulang posisi dan geometri elemen. Terjadi saat properti seperti `width`, `height`, `margin`, `top`, `font-size`, atau `display` berubah. Layout pada satu node dapat memicu *reflow* cascade ke seluruh sub-tree.
- **Paint / Repaint**: Pengisian piksel elemen (background, text color, shadows, border visual). Paint mahal secara komputasi CPU karena melibatkan rasterizer (*Skia* pada Blink).
- **Composite**: Penyatuan layer-layer bitmap yang telah digambar oleh GPU. Mengubah properti `transform` dan `opacity` **hanya** memicu compositing, berjalan langsung di *Compositor Thread* tanpa memblokir *Main Thread*.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan VFM & Paint-Engine Aware |
| :--- | :--- | :--- |
| **Penyelesaian Margin Bug** | Menambahkan `margin-top` sembarangan atau `padding` hack | Memicu BFC baru (`display: flow-root`) secara eksplisit |
| **Z-Index Management** | Nilai acak: `z-index: 999999` (*Z-Index Wars*) | Hierarki terkontrol dengan `isolation: isolate` |
| **Animasi & Interaksi** | Animasi via properti geometris (`top`, `left`, `margin`) | Animasi GPU-only via `transform: translate3d()` & `opacity` |
| **Performa Scroll** | Render ribuan node; sering terjadi *forced reflow* | Isolasi rendering: `contain: content`, `content-visibility: auto` |
| **I18n / Bi-directional UI** | Menggunakan `left`, `right`, `margin-left` manual | Penggunaan penuh *CSS Logical Properties* (`margin-inline-*`) |

---

## 5. How (Workflow Detail)

Berikut adalah alur diagnostik dan optimasi rendering browser:

```
[Mulai Evaluasi Performa UI]
               │
               ▼
[Rekam Profiling via Chrome DevTools (Performance Tab)]
               │
               ▼
     Apakah ada Long Task (> 50ms)?
        ├─── YES ───► Periksa Flame Chart: "Recalculate Style" / "Layout"?
        │                 ├── YES ──► Deteksi Forced Synchronous Layout (Baca DOM lalu Tulis DOM)
        │                 │            Solusi: Pisahkan Read/Write batch via requestAnimationFrame
        │                 └── NO  ──► Lanjut ke investigasi Paint
        └─── NO
               │
               ▼
[Aktifkan "Paint Flashing" & "Layer Borders" di Rendering Tab]
               │
               ▼
   Apakah seluruh viewport berkedip hijau saat scroll/animasi?
        ├─── YES ──► Paint Invalidation menyeluruh terdeteksi.
        │            Solusi: Bungkus komponen dalam layer terpisah (`will-change: transform` 
        │            atau isolasi konteks layout dengan `contain: paint layout`)
        └─── NO
               │
               ▼
   Apakah konsumsi Layer/VRAM membengkak?
        ├─── YES ──► Compositor Layer Explosion terdeteksi.
        │            Solusi: Audit selector `will-change`, hapus pemanggilan prematur
        └─── NO  ──► UI Render Pipeline berada dalam kondisi Optimal.
```

---

## 6. Analogy & Diagram ASCII

Bayangkan perenderan visual browser seperti **Studio Animasi Film Tradisional Multi-Layer**:

1. **Layout**: Arsitek menggambar sketsa teknis blueprint denah posisi karakter dan ukuran kertas.
2. **Paint**: Pelukis mewarnai karakter di atas lembaran plastik transparan (*cel*).
3. **Compositor**: Sutradara menumpuk lembaran-lembaran *cel* transparan tersebut di depan lensa kamera dan menggesernya secara independen.

```
+-------------------------------------------------------------+
| Browser Window (Viewport)                                    |
|                                                             |
|   +-- Root Stacking Context ----------------------------+   |
|   | Background: #f8fafc                                 |   |
|   |                                                     |   |
|   |  +-- Layer A (isolation: isolate) ---------------+  |   |
|   |  | z-index: 10                                    |  |   |
|   |  |  +-- Sub-layer: Modal Overlay (z-index: 999) -+|  |   |
|   |  |  | [ Terisolasi di dalam Layer A ]            ||  |   |
|   |  |  +--------------------------------------------+|  |   |
|   |  +------------------------------------------------+  |   |
|   |                                                     |   |
|   |  +-- Layer B (z-index: 20) -----------------------+  |   |
|   |  | Tooltip Widget (Muncul di atas Layer A karena  |  |   |
|   |  | Layer B memiliki z-index root lebih tinggi)    |  |   |
|   |  +------------------------------------------------+  |   |
|   +-----------------------------------------------------+   |
+-------------------------------------------------------------+
```

Jika Sub-layer Modal Overlay di dalam **Layer A** diberi `z-index: 999999`, ia **tidak akan pernah** bisa berada di atas **Layer B**, karena ruang lingkup tumpukannya telah dikurung di dalam konteks Layer A.

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Margin Collapsing & BFC Isolation

#### Kasus Margin Collapsing (Buggy)
```html
<div class="parent">
  <div class="child">Child Element</div>
</div>
```
```css
.parent {
  background-color: #cbd5e1;
  /* Masalah: Margin child 'bocor' keluar parent (margin collapsing) */
}
.child {
  margin-top: 40px;
  background-color: #3b82f6;
  color: #ffffff;
}
```

#### Solusi Robust Berbasis BFC
```css
.parent {
  background-color: #cbd5e1;
  /* Membuat BFC baru tanpa efek visual sampingan */
  display: flow-root; 
}
.child {
  margin-top: 40px;
  background-color: #3b82f6;
  color: #ffffff;
}
```

---

### 7.2. Practical Example: High-Frequency Ticker Component

Implementasi komponen feed data real-time dengan isolasi Stacking Context, pembatasan kalkulasi layout, dan akselerasi GPU.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>High Performance Ticker Grid</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="dashboard-viewport">
    <section class="ticker-panel">
      <header class="ticker-header">
        <h1 class="ticker-title">Order Book Stream</h1>
        <span class="ticker-badge">LIVE COMPOSITOR</span>
      </header>
      
      <!-- Virtualized Scroll Container -->
      <div class="scroll-container" id="scrollContainer">
        <ul class="ticker-list" id="tickerList">
          <!-- Dynamic high-frequency nodes -->
        </ul>
      </div>
    </section>
  </main>
  <script src="app.js"></script>
</body>
</html>
```

```css
/* styles.css */
:root {
  --color-bg-base: #090d16;
  --color-bg-surface: #131b2e;
  --color-border: #1e293b;
  --color-text-primary: #f8fafc;
  --color-text-secondary: #94a3b8;
  --color-gain: #10b981;
  --color-loss: #ef4444;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background-color: var(--color-bg-base);
  color: var(--color-text-primary);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  min-height: 100vh;
  display: grid;
  place-items: center;
}

.dashboard-viewport {
  inline-size: min(100% - 2rem, 640px);
  block-size: 520px;
}

/* Parent Panel: Isolation Boundary */
.ticker-panel {
  background-color: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  block-size: 100%;
  
  /* 
    Isolasi Stacking Context: Menjamin z-index anak tidak bocor 
    keluar window dashboard
  */
  isolation: isolate;
  
  /* 
    Isolasi Layout & Paint: Mutasi DOM di dalam panel 
    tidak memicu reflow pada elemen di luarnya 
  */
  contain: layout paint;
}

.ticker-header {
  padding: 1rem;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ticker-title {
  font-size: 1rem;
  font-weight: 600;
}

.ticker-badge {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  background-color: rgba(16, 185, 129, 0.1);
  color: var(--color-gain);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
}

.scroll-container {
  flex: 1;
  overflow-y: auto;
  position: relative;
  /* Mengoptimalkan scrolling via thread terpisah */
  overscroll-behavior-y: contain;
}

.ticker-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  padding: 0.5rem;
  gap: 0.25rem;
}

/* Item Node: Highly optimized for updates */
.ticker-item {
  display: grid;
  grid-template-columns: 80px 1fr 100px;
  align-items: center;
  padding: 0.5rem 0.75rem;
  background-color: rgba(255, 255, 255, 0.02);
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 0.875rem;
  
  /* Hindari Paint Flashing: Isolasi tiap item ke composited layer jika bergerak */
  contain: layout style;
  content-visibility: auto;
  contain-intrinsic-size: auto 36px;
}

.ticker-item .price {
  font-weight: 600;
}

.ticker-item .price.up { color: var(--color-gain); }
.ticker-item .price.down { color: var(--color-loss); }

.ticker-item .volume {
  text-align: right;
  color: var(--color-text-secondary);
}

/* Animasi Transform yang Ramah GPU */
.pulse-up {
  animation: gpuPulseGreen 400ms cubic-bezier(0, 0, 0.2, 1) forwards;
}

@keyframes gpuPulseGreen {
  0% {
    transform: translateZ(0) scale(1);
    background-color: rgba(16, 185, 129, 0.4);
  }
  100% {
    transform: translateZ(0) scale(1);
    background-color: rgba(255, 255, 255, 0.02);
  }
}
```

```javascript
// app.js
document.addEventListener("DOMContentLoaded", () => {
  const tickerList = document.getElementById("tickerList");
  const symbols = ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "DOT-USD"];
  const rowsCount = 20;

  // Initialize initial nodes
  for (let i = 0; i < rowsCount; i++) {
    const li = document.createElement("li");
    li.className = "ticker-item";
    li.id = `row-${i}`;
    li.innerHTML = `
      <span class="symbol">${symbols[i % symbols.length]}</span>
      <span class="price up">0.00</span>
      <span class="volume">0.0000</span>
    `;
    tickerList.appendChild(li);
  }

  // High frequency simulation loop
  function updateData() {
    // Hindari Layout Thrashing: Pisahkan fase READ dan WRITE
    
    // 1. DATA READ / CALCULATION
    const targetIdx = Math.floor(Math.random() * rowsCount);
    const newPrice = (Math.random() * 50000 + 1000).toFixed(2);
    const newVol = (Math.random() * 5).toFixed(4);
    const isUp = Math.random() > 0.5;

    // 2. DOM WRITE BATCH (Di-queue dalam frame perenderan berikutnya)
    requestAnimationFrame(() => {
      const row = document.getElementById(`row-${targetIdx}`);
      if (!row) return;

      const priceNode = row.querySelector(".price");
      const volNode = row.querySelector(".volume");

      priceNode.textContent = newPrice;
      priceNode.className = `price ${isUp ? "up" : "down"}`;
      volNode.textContent = newVol;

      // Trigger composite-only pulse animation
      row.classList.remove("pulse-up");
      // Memicu reflow kecil hanya jika diperlukan secara spesifik,
      // lebih baik gunakan toggle microtask
      void row.offsetWidth; // Terisolir oleh contain: layout style
      row.classList.add("pulse-up");
    });
  }

  setInterval(updateData, 60);
});
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Global Trading Platform Dashboard Frame Rate Drop
- **Konteks**: Platform enterprise FX trading memproses rata-rata 250 mutasi harga per detik melalui WebSocket.
- **Gejala**: CPU utilisasi client mencapai 90-100%, terjadi *frame drops* masif (turun dari 60 FPS ke 14-18 FPS), scroll tersendat (*jank*), dan kipas mesin klien menderu kencang.
- **Hasil Audit DevTools Performance**:
  1. *Flame graph* menunjukkan eksekusi **"Layout"** (35ms) dan **"Paint"** (22ms) berjalan berulang kali di setiap interval frame (Total frame budget 16.6ms terlampaui).
  2. *Rendering Paint Flashing* menampilkan seluruh layar berkedip hijau saat satu baris orderbook berubah nilainya.
  3. Modals dan tooltips tertutup oleh orderbook komponen karena *z-index wars* (penggunaan `z-index: 9999` vs `z-index: 100000`).

```
[KONDISI BURUK (Layout Thrashing)]
WS Message ──► JS Read offsetHeight ──► JS Set style.top ──► Layout Triggered ──► Paint All
                     ▲                                             │
                     └──────────────── (Loop 250x/sec) ────────────┘

[KONDISI OPTIMAL (Hardware-Accelerated Stream)]
WS Message ──► Batch State (Queue) ──► rAF Commit:
                                         - contain: strict (Cegah global reflow)
                                         - GPU transform / textContent only
                                         - isolation: isolate (Cegah Z-leak)
```

- **Langkah Remediasi**:
  1. **Stacking Context Isolation**: Menambahkan `isolation: isolate;` pada root setiap *Widget Container*. Semua nilai `z-index` dinormalisasi menggunakan skala lokal `1 - 10`.
  2. **Isolasi Mutasi DOM**: Menyematkan `contain: strict;` (kombinasi layout, style, paint, size) pada kontainer tabel trading. Hal ini mencegah reflow lokal merambat ke elemen navigasi utama dashboard.
  3. **Virtual Sizing**: Mengaktifkan `content-visibility: auto;` dan `contain-intrinsic-size` pada 500 baris order book yang berada di luar viewport, mengeliminasi komputasi Layout dan Paint untuk node yang tidak kasat mata.
- **Hasil**: Frame rate stabil di angka solid 60 FPS, durasi siklus Main Thread per frame anjlok dari 57ms menjadi 3.2ms, dan utilisasi CPU turun menjadi rata-rata 12%.

---

## 9. Trade-offs

| Pendekatan / Properti | Keuntungan (Pros) | Biaya / Kerugian (Cons) | Dampak Skalabilitas |
| :--- | :--- | :--- | :--- |
| **`contain: strict` / `content-visibility: auto`** | Mengeliminasi reflow global; komputasi paint di luar viewport dipangkas hingga 90%. | Memerlukan estimasi `contain-intrinsic-size` eksplisit; jika keliru, scrollbar akan meloncat (*jumpy scroll*). | Sangat Tinggi: Memungkinkan rendering puluhan ribu node DOM tanpa virtualisasi kompleks. |
| **Layer Promotion Berlebih (`will-change: transform`)** | Operasi animasi dipindahkan sepenuhnya ke Compositor Thread (GPU-accelerated, zero-paint). | **Compositor Layer Explosion**: Menguras GPU VRAM secara agresif; crash browser pada perangkat low-end memory. | Rendah jika diterapkan membabi buta; Harus dikelola dinamis (tambahkan saat aktif, hapus saat selesai). |
| **`isolation: isolate`** | Menghilangkan *Z-Index wars*; membuat hierarki komponen modular dan independen secara tampilan. | Harus diperhitungkan matang jika komponen anak membutuhkan visual yang sengaja meluap (*overflow bleed*). | Sangat Tinggi: Mencegah regresi CSS visual antar-tim mikro-frontend. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Common Mistakes
1. **The Ghost Parent (Margin Collapsing Misunderstanding)**: Menambahkan `margin-top` pada anak pertama lalu heran mengapa background parent tidak membesar dan margin justru menempel pada elemen di atas parent.
2. **Transform Breaking Position Fixed**: Menggunakan `transform`, `filter`, atau `perspective` pada kontainer induk dari elemen yang memiliki `position: fixed`. Hal ini secara spesifikasi merestrukturisasi *Containing Block* dari fixed element: elemen tidak lagi berpatokan pada Viewport, melainkan berpatokan pada kontainer induk bertransformasi tersebut.
3. **Z-Index Escalation**: Terus menaikkan angka `z-index: 2147483647` tanpa menyadari bahwa elemen berada dalam Stacking Context induk yang memiliki z-index lebih rendah dari elemen pembanding.
4. **Layout Thrashing via Inlined Geometry Queries**: Membaca geometri DOM (`node.offsetHeight`, `getBoundingClientRect()`) tepat setelah menulis style DOM (`node.style.width = ...`), memaksa engine Chromium melakukan sinkronisasi *style & layout* instan di Main Thread.

### 10.2. Troubleshooting Guide

#### Isu: `position: fixed` anak berperilaku seperti `position: absolute`
- **Penyebab**: Terdapat ancestor yang memiliki properti pembentuk containing block baru (misal: `transform`, `will-change: transform`, `contain: paint`).
- **Diagnosis**: Jalankan di Console DevTools:
  ```javascript
  let el = document.querySelector(".fixed-child").parentElement;
  while (el) {
    const style = getComputedStyle(el);
    if (style.transform !== 'none' || style.contain.includes('paint')) {
      console.warn("Found offending ancestor:", el);
    }
    el = el.parentElement;
  }
  ```
- **Solusi**: Pindahkan fixed child langsung ke document body atau hilangkan efek transform/containment pada elemen ancestor terkait.

#### Isu: Sub-pixel Antialiasing Hilang (Teks terlihat buram/pecah)
- **Penyebab**: Promosi elemen ke Composited Layer menyebabkan hilangnya *Subpixel Font Antialiasing* (kembali ke *Grayscale Antialiasing* pada engine rasterisasi lama saat rendering GPU).
- **Solusi**: Pastikan layer memiliki background buram (`background-color` non-transparan) sebelum memicu hardware acceleration, atau gunakan:
  ```css
  .element {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **BFC Management**: Gunakan `display: flow-root` setiap kali memerlukan pembersihan float internal atau isolasi margin collapsing. Hindari hack usang `overflow: hidden` atau clearfix pseudo-element.
- [ ] **Defensive Stacking Context**: Gunakan `isolation: isolate` pada level komponen (Design System Components) agar styling z-index internal tidak mencemari atau tercemar oleh konteks global.
- [ ] **CSS Containment Usage**: Terapkan `contain: layout style` pada modul mandiri, dan `contain: paint` pada komponen yang membatasi render visual ke dalam batas *bounding box*.
- [ ] **Intrinsic Layout Sizing**: Manfaatkan `min-content`, `max-content`, dan `fit-content` untuk dynamic layout sebelum memaksakan perhitungan via JavaScript.
- [ ] **Zero-Layout Animations**: Animasikan **hanya** properti `transform` dan `opacity`. Jangan pernah menganimasikan properti ukuran (`width`, `height`), posisi geometris (`top`, `left`), atau padding/margin.
- [ ] **Prudent Hardware Acceleration**: Gunakan `will-change` secara reaktif dan temporer melalui JS jika animasi akan dimulai, dan hapus properti ini setelah animasi selesai untuk melepaskan VRAM GPU.

---

## 12. Hands-on Practice

Buatlah direktori praktikum dengan struktur:
```
hands-on/m02/
├── index.html
├── styles.css
└── perf-benchmark.js
```

### Langkah 1: Siapkan `index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>VFM & Paint Lab</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="control-panel">
    <button id="btnThrash">Run Layout Thrashing (Bad)</button>
    <button id="btnBatch">Run Optimized Batch (Good)</button>
    <div id="metric">Idle</div>
  </div>

  <div class="layout-boundary" id="stage">
    <!-- 500 Cards generated by JS -->
  </div>

  <script src="perf-benchmark.js"></script>
</body>
</html>
```

### Langkah 2: Definisikan Layout & Containment di `styles.css`
```css
:root {
  box-sizing: border-box;
}
*, *::before, *::after {
  box-sizing: inherit;
}

body {
  font-family: system-ui, sans-serif;
  margin: 0;
  padding: 1.5rem;
  background: #0f172a;
  color: #f1f5f9;
}

.control-panel {
  position: sticky;
  top: 0;
  background: #1e293b;
  padding: 1rem;
  border-radius: 8px;
  display: flex;
  gap: 1rem;
  align-items: center;
  z-index: 100;
  isolation: isolate;
  border: 1px solid #334155;
}

button {
  padding: 0.5rem 1rem;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}
button:hover { background: #1d4ed8; }

#metric {
  font-family: monospace;
  font-weight: bold;
}

.layout-boundary {
  margin-top: 2rem;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem;
  
  /* Isolasi Layout Container */
  contain: layout;
}

.card {
  background: #1e293b;
  padding: 1rem;
  border-radius: 6px;
  border: 1px solid #334155;
  
  /* Paint & Render Optimization */
  contain: layout paint;
  content-visibility: auto;
  contain-intrinsic-size: auto 80px;
}

.card-title {
  font-size: 0.875rem;
  margin-bottom: 0.5rem;
}

.card-bar {
  block-size: 8px;
  inline-size: 20%;
  background: #38bdf8;
  border-radius: 4px;
  transition: transform 0.2s ease-out;
  transform-origin: left;
}
```

### Langkah 3: Implementasi Skrip Uji di `perf-benchmark.js`
```javascript
const stage = document.getElementById("stage");
const metric = document.getElementById("metric");
const COUNT = 1000;

// Setup initial cards
for (let i = 0; i < COUNT; i++) {
  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `
    <div class="card-title">Worker #${i}</div>
    <div class="card-bar"></div>
  `;
  stage.appendChild(card);
}

const bars = document.querySelectorAll(".card-bar");

// BAD: Layout Thrashing (Read then Write in loop)
document.getElementById("btnThrash").addEventListener("click", () => {
  metric.textContent = "Calculating Thrashing...";
  const start = performance.now();

  bars.forEach((bar) => {
    // FORCE REFLOW: Read DOM geometry
    const parentWidth = bar.parentElement.offsetWidth;
    // WRITE DOM: Ubah layout geometry
    bar.style.width = `${(Math.sin(parentWidth) * 50 + 50)}%`;
  });

  const duration = (performance.now() - start).toFixed(2);
  metric.textContent = `Thrashing Duration: ${duration}ms (Notice UI Lag)`;
});

// GOOD: Composited & Batched Execution
document.getElementById("btnBatch").addEventListener("click", () => {
  metric.textContent = "Calculating Batched...";
  const start = performance.now();

  // 1. PURE READ: Dilakukan satu kali untuk seluruh batch
  const sampleWidth = bars[0].parentElement.offsetWidth;
  const targetScales = [];

  for (let i = 0; i < COUNT; i++) {
    targetScales.push((Math.sin(sampleWidth + i) * 0.5 + 0.5) * 4);
  }

  // 2. COMPOSITED WRITE: Tidak ada Layout/Reflow, hanya transform
  requestAnimationFrame(() => {
    bars.forEach((bar, idx) => {
      bar.style.transform = `scaleX(${targetScales[idx]})`;
    });

    const duration = (performance.now() - start).toFixed(2);
    metric.textContent = `Optimized Batch Duration: ${duration}ms (Silk Smooth)`;
  });
});
```

---

## 13. Exercises

### 13.1. Level: Easy
Buat komponen avatar bertingkat (*overlapping avatar list*) di mana setiap avatar menumpuk di atas avatar sebelumnya, namun saat hover avatar yang bersangkutan harus melompat ke tumpukan paling depan tanpa merusak urutan avatar lainnya.
- **Kriteria Keberhasilan**: Menggunakan manipulasi BFC dan Stacking Context lokal (`position: relative; z-index: x;`) tanpa menggunakan JavaScript sama sekali.

### 13.2. Level: Medium
Diberikan sebuah komponen layout dashboard yang memiliki *Sidebar*, *Fixed Header*, dan *Scrollable Content*. Terdapat bug di mana tooltip pada elemen baris pertama tabel di *Scrollable Content* terpotong oleh batas *Header*.
- **Kriteria Keberhasilan**: Selesaikan bug pemotongan tooltip ini murni via restrukturisasi *Stacking Context Tree* dan CSS containment tanpa memindahkan posisi node tooltip di DOM tree.

### 13.3. Level: Hard
Bangun implementasi kustom *Accordion Tree* multi-level (kedalaman hingga 5 tingkat). Setiap level harus memiliki margin collapse yang terisolasi sempurna tanpa menggunakan `overflow: hidden`, dan animasi buka-tutup wajib berjalan 60 FPS menggunakan GPU Composite Transform (`scaleY` / `translateY`), bukan menganimasikan `max-height` atau `height`.
- **Kriteria Keberhasilan**: Buka DevTools Rendering Tab, buktikan bahwa selama proses transisi ekspansi accordion berlangsung, **Paint Flashing** tidak menunjukkan kotak hijau sama sekali pada Main Window.

---

## 14. Challenges

### Real-time High-Density Financial Order Matrix
Rancang arsitektur visual untuk rendering matriks heatmap harga saham berukuran 100 baris $\times$ 10 kolom (1000 sel dinamis):
- **Spesifikasi**:
  1. WebSocket memancarkan hingga 1500 pembaruan sel/detik secara acak.
  2. Terdapat fitur "Sticky Header" dan "Sticky Column" (dua sumbu beku sekaligus).
  3. Setiap pembaruan sel harus menampilkan animasi efek pendaran (*flash fade-out*) warna merah/hijau.
- **Batasan**:
  1. Main Thread long-task selama streaming data tidak boleh melebihi batas 16ms (Frame Budget).
  2. Memory footprint GPU Compositor Layers tidak boleh melebihi **80MB** di DevTools Memory Profiler.
  3. Nilai scroll horizontal dan vertikal harus tetap native tanpa jitter/stutter pada layar dengan refresh rate 120Hz.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. Apa cara paling tepat dan bebas efek samping untuk membuat Block Formatting Context (BFC) baru menurut spesifikasi CSS modern?
   - A. `overflow: hidden`
   - B. `display: flow-root`
   - C. `float: left`
   - D. `display: block`

2. Mengapa margin vertikal antara dua elemen sibling mengalami collapsing?
   - A. Karena keduanya berada dalam Formatting Context yang berbeda.
   - B. Karena keduanya adalah in-flow block-level boxes dalam BFC yang sama.
   - C. Karena elemen induk memiliki `box-sizing: border-box`.
   - D. Karena kedua elemen memiliki `position: relative`.

3. Properti mana yang **HANYA** memicu tahap Compositing tanpa memicu Layout dan Paint jika diubah via transisi/animasi?
   - A. `top`
   - B. `background-color`
   - C. `transform`
   - D. `margin-left`

4. Apa dampak penerapan `isolation: isolate` pada sebuah elemen HTML?
   - A. Mencegah seluruh JavaScript mengakses DOM elemen tersebut.
   - B. Menghentikan pewarisan properti typography ke child nodes.
   - C. Membentuk Stacking Context baru tanpa memerlukan properti `position` atau `z-index`.
   - D. Mengubah elemen secara paksa menjadi BFC independen.

5. Sizing keyword mana yang mewakili ukuran minimum yang dibutuhkan sebuah kontainer tanpa menyebabkan teks mengalami line-break yang tidak diinginkan?
   - A. `min-content`
   - B. `max-content`
   - C. `fit-content`
   - D. `auto`

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis Pendek)

6. Sebuah elemen memiliki CSS: `position: fixed; top: 0; left: 0;`. Mengapa posisinya tiba-tiba relatif terhadap kontainer induknya (bukan viewport)?
   - A. Kontainer induk memiliki `display: flex`.
   - B. Kontainer induk memiliki properti `transform` selain `none`.
   - C. Viewport browser sedang mengalami zoom in.
   - D. Kontainer induk memiliki `z-index: -1`.

7. Apa konsekuensi teknis jika kita menambahkan properti `* { will-change: transform; }` ke seluruh elemen halaman aplikasi enterprise?
   - A. Aplikasi menjadi sangat cepat karena seluruh komputasi dipindahkan ke GPU.
   - B. Terjadi **Compositor Layer Explosion** yang menghabiskan memori VRAM GPU dan dapat menyebabkan crash.
   - C. Seluruh layout akan otomatis berubah menjadi Flexbox.
   - D. Layout thrashing akan dicegah secara otomatis oleh engine browser.

8. Perhatikan potongan kode berikut:
   ```javascript
   div.style.left = div.offsetLeft + 10 + "px";
   ```
   Mengapa baris kode di atas memicu masalah performa jika dieksekusi dalam loop berulang kali?
   - A. Karena `left` tidak didukung oleh browser modern.
   - B. Karena pembacaan `offsetLeft` memaksa browser melakukan **Forced Synchronous Layout** setelah mutasi style.
   - C. Karena string concatenation lambat di V8 engine.
   - D. Karena properti `style.left` mengubah pohon Stacking Context secara destruktif.

9. Apa fungsi spesifik dari deklarasi `content-visibility: auto` pada komponen scroll list yang panjang?
   - A. Mengompres ukuran file gambar secara otomatis saat scroll.
   - B. Menghilangkan scrollbar vertikal browser saat idle.
   - C. Melewati kalkulasi Layout dan Paint untuk elemen yang saat ini berada di luar batas viewport.
   - D. Mengubah rendering teks dari format SVG ke format Canvas.

10. Jika Child A memiliki `z-index: 99999` di dalam Parent A (`z-index: 1; isolation: isolate`), dan Child B memiliki `z-index: 1` di dalam Parent B (`z-index: 2; isolation: isolate`). Manakah elemen yang akan tampil di tumpukan paling atas?
    - A. Child A
    - B. Child B
    - C. Keduanya akan bertumpuk sejajar (flickering)
    - D. Tergantung urutan DOM Child A dan Child B

---

### Bagian 3: Skenario Kasus Produksi

11. **Skenario 1**: Tim Anda mengembangkan ekstensi browser widget (*overlay chat*) yang diinjeksi ke ribuan website klien pihak ketiga. Widget sering kali tampil di belakang navbar website klien atau tertimpa elemen lain meskipun Anda telah mengatur `z-index: 2147483647;`. Analisis akar masalah visual formatting model dari kasus ini dan rancang solusi arsitektur CSS agar widget selalu berada di layer terdepan tanpa merusak layout host.
12. **Skenario 2**: Dalam sebuah halaman e-commerce dashboard, tabel histori transaksi memiliki 2.000 baris. Saat pengguna mengetik di input filter teks, terjadi delay ketik (*input latency*) sebesar 300ms. Profiler DevTools menunjukkan long task didominasi oleh "Recalculate Style" dan "Layout" dari seluruh baris tabel. Bagaimana Anda menyusun ulang containment CSS dan strategi rendering tabel untuk menekan angka latency di bawah 16ms?
13. **Skenario 3**: Sebuah komponen infinite canvas menampilkan artefak visual berupa garis-garis rambut halus (*sub-pixel seam rendering*) dan teks buram saat pengguna melakukan operasi panning/zooming. Telusuri bagaimana mekanisme sub-pixel rounding dan komposisi layer GPU bekerja di balik layar yang memicu isu ini, dan jelaskan langkah mitigasinya.

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Kunci Bagian 1
1. **B** — `display: flow-root` dirancang khusus dalam CSS3 untuk membentuk BFC tanpa efek samping seperti pemotongan visual (*clipping*) pada `overflow: hidden`.
2. **B** — Margin collapsing hanya terjadi pada elemen in-flow block-level yang berada dalam BFC yang sama.
3. **C** — `transform` (dan `opacity`) diproses langsung di *Compositor Thread* via GPU, memintas fase Layout dan Paint.
4. **C** — `isolation: isolate` secara eksplisit membentuk Stacking Context lokal baru tanpa perlu modifikasi nilai `position` atau pemberian `z-index`.
5. **B** — `max-content` merepresentasikan ukuran intrinsik terlebar di mana konten dibentangkan tanpa melakukan wrapping/line-break opsional.

#### Kunci Bagian 2
6. **B** — Properti transformasi non-trivial seperti `transform` meredefinisi containing block bagi elemen keturunannya yang berposisi `fixed` maupun `absolute`.
7. **B** — Layer promotion massal menghasilkan layer bitmap individual untuk tiap node di VRAM, memicu konsumsi GPU berlebih dan berisiko crash.
8. **B** — Akses properti geometris (`offsetLeft`) sesaat setelah mutasi gaya memicu *Forced Reflow* karena engine browser harus segera menghitung koordinat akurat terbaru di Main Thread.
9. **C** — `content-visibility: auto` secara cerdas mengabaikan rendering node di luar viewport hingga node tersebut mendekati area layar.
10. **B** — Child B berada di atas Child A karena konteks induk Parent B (`z-index: 2`) memiliki prioritas tumpukan lebih tinggi dibandingkan Parent A (`z-index: 1`).

#### Panduan Jawaban Bagian 3 (Kasus Produksi)
11. **Solusi Skenario 1**: Akar masalahnya adalah widget diinjeksi ke dalam node DOM yang berada di bawah Stacking Context ancestor yang memiliki nilai `z-index` rendah atau terkena clipping. Solusi arsitektur: Gunakan **Shadow DOM** yang di-mount langsung sebagai anak langsung dari root `document.body`, dan terapkan strategi penataan *Top Layer API* (seperti elemen `<dialog>` native atau *Popover API*) yang secara arsitektural merender elemen di atas *Canvas Root Stacking Context*, sepenuhnya kebal terhadap `isolation` atau `z-index` lokal milik website host.
12. **Solusi Skenario 2**: Terapkan `contain: strict;` pada wrapper tabel untuk memutus rantai kalkulasi reflow ke elemen filter input. Tambahkan `content-visibility: auto;` beserta `contain-intrinsic-size: auto 45px;` pada tiap baris data (`<tr>` / `.table-row`). Dengan arsitektur ini, input filter hanya akan memicu kalkulasi ulang style pada 15-20 baris yang terlihat di layar, memotong komputasi layout dari 2.000 node menjadi hanya sebagian kecil, memangkas *input latency* hingga di bawah ambang batas 16ms.
13. **Solusi Skenario 3**: Isu disebabkan oleh transformasi matriks pecahan (*floating point coordinates*) yang tidak sejajar dengan grid piksel fisik layar (*sub-pixel misalignment*), diperparah oleh raster scaling pada layer GPU yang menonaktifkan sub-pixel anti-aliasing. Mitigasi: Terapkan fungsi pembulatan piksel integer (`Math.round()` atau penyesuaian matriks via `devicePixelRatio`) pada nilai translate canvas, gunakan CSS `transform: translate3d(Xpx, Ypx, 0)` dengan nilai koordinat integer, dan berikan `backface-visibility: hidden;` serta pastikan latar belakang kontainer bersifat *opaque* (padat/tidak transparan) untuk mempertahankan rendering teks yang tajam.

---

## 16. Summary
Memahami **Visual Formatting Model**, **Box Dynamics**, dan **Paint Engine** adalah pembeda fundamental antara perekayasa web enterprise dengan pengembang web kasual:
- **Hierarki Geometri**: DOM Tree dikonversi ke Box Tree; pembentukan context (BFC, IFC, FFC) menentukan kalkulasi flow dan boundary margin elemen secara deterministik.
- **Hierarki Kedalaman**: Z-Index tidak bersifat absolut; pemahaman mendalam tentang *Stacking Context Tree* dan penggunaan `isolation: isolate` merupakan kunci mengeliminasi konflik visual pada aplikasi berskala besar.
- **Pipeline Performance**: Animasi modern harus berorientasi pada **Compositor-Only Properties** (`transform`, `opacity`). Isolasi mutasi layout menggunakan CSS Containment (`contain`, `content-visibility`) wajib diintegrasikan pada arsitektur komponen dengan throughput data tinggi untuk menjamin performa rendering yang mulus di 60/120 FPS.