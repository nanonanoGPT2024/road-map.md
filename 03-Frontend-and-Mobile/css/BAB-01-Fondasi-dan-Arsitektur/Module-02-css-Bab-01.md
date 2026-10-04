# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (CSS)

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Internal Browser Engine**: Menguraikan siklus hidup parsing CSS, konstruksi CSSOM, integrasi Render Tree, hingga proses layout/reflow, paint, dan compositing pada Blink/Gecko.
2. **Mengimplementasikan Arsitektur Modern Cascade Layers (`@layer`)**: Menghilangkan dependensi terhadap specificity hacks (`!important`, over-qualified selectors) melalui orkestrasi prioritas deklarasi eksplisit pada level enterprise.
3. **Membangun Runtime Token System Berbasis CSS Custom Properties**: Merancang arsitektur dynamic theming berkinerja tinggi tanpa menimbulkan runtime CSS-in-JS overhead atau layout thrashing.
4. **Mengoptimalkan Rendering Critical Path**: Mengaplikasikan CSS Containment (`contain`, `content-visibility`) dan subgrid untuk mereduksi paint invalidation dan reflow cost pada dokumen berskala masif (data grid/infinite list).
5. **Memecahkan Masalah Isolasi Style pada Arsitektur Micro-Frontends**: Mengamankan CSS boundaries menggunakan kombinasi `@layer`, CSS Scoping/Shadow DOM, dan PostCSS automated prefixing.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta harus menguasai:
* Fondasi spesifisitas CSS kalkulasi `(Inline, ID, Class/Attribute/Pseudo-class, Element/Pseudo-element)`.
* Pemahaman dasar siklus hidup DOM tree dan HTTP/2 / HTTP/3 asset delivery.
* Familiaritas dengan sintaks modern CSS (Flexbox, CSS Grid level 1, Custom Properties dasar).
* Pengalaman menggunakan build tools modern (Vite, Webpack, PostCSS) dan preprocessor (Sass/SCSS).

---

## 3. Concept & Internal Architecture

### 3.1. Parsing Pipeline: Dari Raw Bytes ke Composite Layers
Ketika browser menerima respons stream byte CSS dari jaringan:

```
[Raw Bytes] 
    │ (Character Encoding: UTF-8)
    ▼
[Characters] 
    │ (CSS Syntax Module Level 3 Tokenization)
    ▼
[Tokens] (Ident, At-Keyword, Hash, String, Delim, Number, Dimension)
    │ (Parser: Construction of Rules & Declarations)
    ▼
[CSSOM (CSS Object Model)] 
    │
    ├─────────────────────────────┐
    ▼                             ▼
[DOM Tree]                [Recalculate Style] 
                                  │ (ComputedStyle Map / Match Selectors against DOM)
                                  ▼
                          [Render/Layout Tree] 
                                  │ (Box Model Calculation: Geometry, X/Y, Width/Height)
                                  ▼
                             [Layout (Reflow)]
                                  │ (Generate Display Lists)
                                  ▼
                             [Paint (Raster)]
                                  │ (Tile Generation via Skia/Ganesh/Graphite)
                                  ▼
                            [Compositing] 
                                  │ (GPU Layer Manipulation via cc/Direct3D/Metal)
                                  ▼
                            [Pixels on Screen]
```

1. **CSSOM Construction & Memory Overhead**: Berbeda dari HTML parsing yang toleran terhadap parsing parsial bertahap (*speculative parsing*), CSSOM bersifat **render-blocking secara total**. Browser engine tidak dapat merender subtree DOM sampai seluruh CSS yang berlaku pada viewport selesai diparse. CSSOM memetakan relasi hierarki aturan, media queries, dan cascade.
2. **Style Recalculation (Rule Matching)**: Engine membaca selector dari **kanan ke kiri (right-to-left)**. Contoh: `.card .title span` mengharuskan engine mengecek seluruh elemen `<span>` (key selector), lalu menelusuri rantai parent untuk mencocokkan `.title` dan `.card`. Ini memicu implikasi performa selector complexity.
3. **Render Tree Generation**: Memfilter node DOM yang memiliki `display: none` (node ini dieliminasi total dari Render Tree). Node dengan `visibility: hidden` tetap dimasukkan ke Layout Tree karena masih mengonsumsi dimensi geometris.
4. **Layout (Reflow)**: Menghitung koordinat Cartesian absolut dan ukuran geometris setiap *LayoutObject/RenderBox*. Operasi ini bersifat rekursif dan mahal secara komputasi ($O(N)$ di mana $N$ adalah jumlah node terpengaruh).
5. **Paint**: Mengonversi LayoutObject menjadi instruksi visual (*DrawRect*, *DrawText*, *DrawImage*).
6. **Compositing**: Mengelompokkan layer-layer visual independen ke dalam GPU VRAM textures. Perubahan pada properti tertentu (`transform`, `opacity`, `filter`, `backdrop-filter`) diisolasi pada proses compositing tanpa memicu Reflow atau Paint.

### 3.2. Dynamic Cascade Engine & Algoritma `@layer`
Urutan prioritas kalkulasi CSS Cascade modern (CSS Cascading and Inheritance Level 5) dihitung berdasarkan hirarki berperingkat berikut:

```
+-------------------------------------------------------------+
| Prioritas Tertinggi (Highest Precedence)                     |
+-------------------------------------------------------------+
| 1. Transition declarations                                  |
| 2. !important User Agent                                    |
| 3. !important User                                          |
| 4. !important Author (@layer terluar / tanpa layer)         |
| 5. !important Author (@layer terurut: layer pertama > akhir)|
| 6. Animation declarations                                   |
| 7. Normal Author (Tanpa layer / Unlayered Styles)           |
| 8. Normal Author (@layer terurut: layer akhir > pertama)    |
| 9. Normal User                                              |
| 10. Normal User Agent                                       |
+-------------------------------------------------------------+
| Prioritas Terendah (Lowest Precedence)                      |
+-------------------------------------------------------------+
```

> **Hukum Pembalikan `!important` pada `@layer`:**
> Untuk deklarasi normal, layer yang dideklarasikan paling akhir (`@layer utilities`) akan mengalahkan layer yang dideklarasikan di awal (`@layer base`). Namun, jika deklarasi menggunakan keyword `!important`, hierarkinya **terbalik total**: `!important` pada `@layer base` akan mengalahkan `!important` pada `@layer utilities`, dan deklarasi unlayered `!important` memiliki prioritas di bawah unlayered normal jika dilihat dari perspektif isolasi, namun unlayered `!important` mengalahkan layered `!important`.

### 3.3. CSS Containment Internals
Spesifikasi CSS Containment (Level 1, 2, & 3) menginstruksikan browser engine untuk mengisolasi subtree DOM tertentu dari sisa dokumen:
* `contain: layout`: Mengisolasi box tree rendering. Perubahan dimensi internal tidak akan memicu reflow di luar boundary elemen ini. Elemen menjadi containing block untuk `position: fixed` dan `position: absolute`.
* `contain: paint`: Elemen tidak akan menggambar apa pun di luar bounds geometrisnya (ekivalen internal dengan implicit clipping). Jika elemen berada di luar viewport, browser dapat sepenuhnya men-skip fase raster/paint.
* `contain: size`: Dimensi elemen dihitung tanpa memeriksa dimensi child elements-nya. Mengurangi kompleksitas kalkulasi sizing intrinsik.
* `content-visibility: auto`: Implementasi otomatis *lazy-rendering*. Engine menahan kalkulasi layout dan painting subtree selama elemen berada di luar *render viewport margins*. Mengurangi TBT (Total Blocking Time) dan INP (Interaction to Next Paint) secara drastis pada halaman masif.

---

## 4. Why & What

### Why (Masalah pada Skala Enterprise)
* **Specificity Wars**: Penggunaan arsitektur monolitik CSS atau utility classes yang tercampur sering kali memaksa developer menulis `!important` atau cascading selector panjang (misal: `div.app #main-content .panel-wrapper .btn.btn-primary`). Hal ini merusak *maintainability* dan *reusability*.
* **Runtime Styling Overhead**: Library CSS-in-JS runtime (misal: styled-components, Emotion) mengeksekusi serialisasi string CSS dan menyuntikkan `<style>` tag via JavaScript thread pada setiap render cycle. Ini membebani CPU, meningkatkan First Input Delay (FID) dan Interaction to Next Paint (INP).
* **Layout Thrashing**: Eksekusi JavaScript yang membaca geometri DOM (`offsetHeight`, `getBoundingClientRect`) diikuti manipulasi style (`element.style.width = ...`) dalam loop memicu *synchronous forced layout*, menghancurkan target framerate 60/120 fps.

### What (Solusi Arsitektur Modern)
* **Native Cascade Layers (`@layer`)**: Memisahkan concerns CSS secara deklaratif tanpa memanipulasi specificities.
* **Tokenized Custom Properties (`--token`)**: State theming di-resolve secara native pada fase layout style recalculation browser tanpa perantara JS runtime.
* **Zero-Runtime Architecture**: Kompilasi style pada fase build (PostCSS/LightningCSS) dikombinasikan dengan kemampuan native browser modern.

---

## 5. How (Workflow Detail)

Alur kerja arsitektur CSS enterprise terbagi menjadi tiga tahapan:

```
[Design Tokens (Figma/Style-Dictionary)]
                    │
                    ▼  (Export: JSON)
[Token Compilation Stage]
    ├─ LightningCSS / PostCSS
    ├─ Resolusi @layer dependencies
    └─ Pengecekan Dead Code & Minifikasi AST
                    │
                    ▼  (Output: Optimized Layered CSS)
[Runtime Injection Stage]
    ├─ Critical Path: <link rel="stylesheet"> (Preload via Early Hints)
    ├─ Dynamic Themes: Modifikasi Custom Property pada root/container scope
    └─ Hardware Acceleration: Assign `will-change` secara atomik via runtime
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem lalu lintas jalan raya:
* **Unlayered CSS dengan Specificity Hacks** adalah jalanan tanpa marka di mana kendaraan berukuran besar (ID Selector) dan truk dengan sirine darurat (`!important`) berebut hak jalan. Ketika terjadi kemacetan (reflow), seluruh jaringan kota terhenti.
* **Cascade Layers (`@layer`) & CSS Containment** adalah jalan tol bertingkat (*multi-tier expressway*) yang dipisahkan secara fisik. Kendaraan di jalur logistik lokal (Layer: Component) tidak dapat mengganggu jalur ekspres (Layer: Utilities). Jika terjadi perbaikan jalan di jalur paling bawah (`contain: layout paint`), arus di jalur lain tetap berjalan pada kecepatan maksimal tanpa interupsi.

### Visualisasi Hubungan Layer dan Spesifisitas
```
========================================================================
CASCADE LAYER PRECEDENCE (NORMAL DECLARATIONS)
========================================================================
[Layer: reset]      --> Specificity (0, 9, 9) kalah terhadap
[Layer: base]       --> Specificity (0, 0, 1)
[Layer: components] --> Specificity (0, 0, 1)
[Layer: utilities]  --> Specificity (0, 0, 1) MENANG ATAS SEMUA LAYER SEBELUMNYA!
[Unlayered Styles]  --> Specificity (0, 0, 1) MENANG ATAS SEMUA LAYERED STYLES!
========================================================================
CASCADE LAYER PRECEDENCE (!IMPORTANT DECLARATIONS - INVERTED LOGIC)
========================================================================
[Unlayered !important]  --> Prioritas terendah dibanding layered !important
[Layer: utilities !imp] --> Kalah terhadap base
[Layer: components !imp]--> Kalah terhadap base
[Layer: base !important]--> MENANG (Memiliki otoritas proteksi tertinggi)
========================================================================
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Demonstrasi `@layer` Precedence

```css
/* Mendefinisikan urutan layer secara eksplisit */
@layer reset, base, components, utilities;

@layer utilities {
  /* Specificity rendah: (0, 0, 1) */
  .hidden {
    display: none;
  }
}

@layer components {
  /* Specificity sangat tinggi: (0, 2, 1) */
  #main-nav .menu-item.active {
    display: flex;
    background-color: var(--color-surface-active);
  }
}

/* 
HASIL EVALUASI BROWSER:
Jika elemen: <div id="main-nav"><div class="menu-item active hidden"></div></div>
Aturan '.hidden' pada @layer utilities AKAN MENANG dan elemen tetap 'display: none', 
meskipun specificity ID pada layer components jauh lebih tinggi.
*/
```

### 7.2. Practical Example: Enterprise Multi-Tier Layered Architecture

#### Directory Structure
```
tokens/
├── primitives.css
└── semantics.css
base/
├── reset.css
└── typography.css
components/
├── datagrid.css
└── modal.css
utilities/
└── layout.css
main.css
```

#### File: `main.css`
```css
/* 1. LAYER REGISTRATION ORDER */
@layer reset, framework, primitives, semantics, components, utilities;

/* 2. ROOT TOKENS & SYSTEM CONTRACT */
@layer primitives {
  :root {
    --space-unit: 4px;
    --space-1: calc(var(--space-unit) * 1); /* 4px */
    --space-2: calc(var(--space-unit) * 2); /* 8px */
    --space-4: calc(var(--space-unit) * 4); /* 16px */
    
    --palette-blue-500: #0ea5e9;
    --palette-blue-600: #0284c7;
    --palette-gray-100: #f1f5f9;
    --palette-gray-900: #0f172a;
    
    --elevation-1: 0 1px 3px rgba(0, 0, 0, 0.1);
    --elevation-2: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  }
}

@layer semantics {
  :root {
    --color-bg-canvas: var(--palette-gray-100);
    --color-text-main: var(--palette-gray-900);
    --color-interactive-primary: var(--palette-blue-500);
    --color-interactive-hover: var(--palette-blue-600);
  }

  [data-theme="dark"] {
    --color-bg-canvas: var(--palette-gray-900);
    --color-text-main: var(--palette-gray-100);
    --color-interactive-primary: var(--palette-blue-600);
    --color-interactive-hover: var(--palette-blue-500);
  }
}

@layer reset {
  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  
  body {
    background-color: var(--color-bg-canvas);
    color: var(--color-text-main);
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    text-rendering: optimizeLegibility;
    -webkit-font-smoothing: antialiased;
  }
}

@layer components {
  /* High-Performance Isolated DataGrid */
  .enterprise-grid-container {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--space-4);
    contain: layout inline-size;
  }

  .grid-card {
    background: canvas;
    border-radius: calc(var(--space-unit) * 2);
    box-shadow: var(--elevation-1);
    padding: var(--space-4);
    
    /* Paint and layout containment */
    contain: layout paint;
    content-visibility: auto;
    contain-intrinsic-size: 0 320px; /* Mencegah layout shift pada dynamic lazy rendering */
    transition: transform 180ms cubic-bezier(0.16, 1, 0.3, 1), box-shadow 180ms ease;
  }

  .grid-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--elevation-2);
    will-change: transform; /* Hint GPU compositing hanya ketika state relevan */
  }

  /* Subgrid implementation for strict alignment */
  .grid-card-inner {
    display: grid;
    grid-template-rows: subgrid;
    grid-row: span 3;
  }
}

@layer utilities {
  .u-visually-hidden {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    padding: 0 !important;
    margin: -1px !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
    white-space: nowrap !important;
    border: 0 !important;
  }
  
  .u-gpu-accelerate {
    transform: translateZ(0);
    backface-visibility: hidden;
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Migrasi Portal Finansial Multi-Brand (FinTech Super-App)
* **Konteks**: Aplikasi dashboard perbankan enterprise melayani 12 anak perusahaan dengan sistem white-labeling, memproses 10.000+ baris data transaksi real-time per tabel.
* **Problem**: 
  1. Penggunaan CSS-in-JS (Emotion) menyebabkan thread blocking JavaScript rata-rata 420ms saat initial mount dan runtime style re-computation setiap kali token stream websocket masuk.
  2. Terjadi specificity collision antara core framework CSS dengan theme override milik tenant. Developer sering menggunakan `!important` berantai hingga level selector 5 tingkat.
  3. Total Blocking Time (TBT) mencapai 850ms, Core Web Vitals INP (Interaction to Next Paint) berada di angka 340ms (kategori *Poor*).

### Solusi Arsitektural:
1. **Penerapan Native Dynamic Variables Tree**: Menghilangkan runtime Emotion. CSS diekstrak pada saat build (`LightningCSS`). State theme diatur via atribut root `[data-tenant="wealth-management"]` yang me-map 400+ custom properties.
2. **Standardisasi 5-Tier `@layer` Architecture**:
   `reset` $\rightarrow$ `vendor` $\rightarrow$ `design-system` $\rightarrow$ `tenant-theme` $\rightarrow$ `overrides`.
   Tenant hanya diizinkan menginjeksi style ke dalam `@layer tenant-theme`. Tidak ada kemungkinan tenant merusak fungsionalitas layer core design-system.
3. **Penerapan CSS Containment pada Data Table**:
   Elemen virtualized row menggunakan:
   ```css
   .table-row {
     content-visibility: auto;
     contain-intrinsic-size: auto 48px;
     contain: layout paint style;
   }
   ```

### Hasil Metrik Produksi:
* Reduksi ukuran bundle JavaScript (penghapusan runtime CSS-in-JS parser): **-78 KB (Gzip)**.
* Script Execution Time saat mounting dashboard: Turun dari **420ms menjadi 18ms**.
* INP Score: Berkurang dari **340ms menjadi 42ms** (*Good status*).
* Zero CSS specificity collision bug tercatat dalam 3 kuartal pasca rilis.

---

## 9. Trade-offs

| Pendekatan / Fitur | Keuntungan (Pros) | Konsekuensi Negatif (Cons / Trade-offs) | Mitigasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Cascade Layers (`@layer`)** | Kontrol cascade mutlak, eliminasi specificity war, isolasi arsitektur rapi. | Aturan `!important` membalikkan hierarki layer; membutuhkan browser modern (Chromium 99+, Firefox 97+, Safari 15.4+). | Gunakan PostCSS `@csstools/postcss-cascade-layers` untuk fallback environment legacy jika target browser kuno. |
| **CSS Custom Properties Engine** | Dynamic runtime theming, zero runtime JS overhead, scoping modular per DOM node. | Mengonsumsi memory footprint CSSOM tambahan jika dideklarasikan jutaan node secara instan; inheritance parsing overhead. | Deklarasikan token global pada level `:root`, batasi scoping property overrides hanya pada scope container. |
| **`content-visibility: auto`** | Reduksi besar pada layout & paint time; initial load rendering instan. | Masalah pada scrollbar jumping; find-in-page browser (Ctrl+F) native engine dapat delay pada subtree kompleks. | Wajib menyertakan `contain-intrinsic-size: auto <estimated-dimension>` agar scrollbar stabil. |
| **Hardware Acceleration (`will-change`)** | Render bypass: delegasi animasi langsung ke GPU thread tanpa reflow/paint. | Konsumsi VRAM membengkak signifikan; potensi memicu blurry text rendering akibat subpixel anti-aliasing dinonaktifkan. | Terapkan `will-change` hanya saat pseudo-state aktif (`:hover`, `:focus-within`) dan hapus saat idle. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Common Mistakes
1. **The Inverted Important Trap**: Developer berasumsi `@layer overrides { .btn { background: red !important; } }` akan mengalahkan `@layer base { .btn { background: blue !important; } }`. 
   * *Realita*: Aturan `@layer base` yang menang karena kalkulasi pembalikan prioritas `!important` spesifikasi CSS Level 5.
2. **Scrollbar Thrashing with `content-visibility`**: Menggunakan `content-visibility: auto` tanpa `contain-intrinsic-size`. Browser menganggap tinggi elemen bernilai `0px` sebelum masuk viewport, menyebabkan scrollbar berguncang liar (*jumping behavior*) saat di-scroll.
3. **Universal Custom Property Injection**: Menyematkan ribuan deklarasi CSS variable pada pemilih global `* { --my-var: 10px; }`. Ini memaksa browser engine mengkalkulasi ulang style sheet memory allocation untuk seluruh node tree.

### 10.2. Troubleshooting Checklist & Debugging
* **Masalah**: Deklarasi utility class tidak berfungsi menimpa aturan component.
  * *Diagnosis*: Cek apakah komponen dideklarasikan tanpa `@layer` (unlayered). Unlayered normal styles **selalu** mengalahkan layered styles terlepas dari specificity selector.
  * *Solusi*: Bungkus komponen ke dalam `@layer components`.
* **Masalah**: DevTools Performance Panel menampilkan event *Forced Reflow* berulang.
  * *Diagnosis*: Deteksi pemanggilan property geometri (misal: `clientWidth`) di dalam looping animasi DOM manipulation.
  * *Solusi*: Batch DOM read/write operasi, atau alihkan manipulasi sepenuhnya ke CSS variables yang dikonsumsi oleh `transform`.
* **Masalah**: Teks tampak buram setelah penambahan `transform: translate3d(0, 0, 0)`.
  * *Diagnosis*: Komposisi texture pada GPU tidak aligned dengan integer pixel grid monitor (subpixel rendering disengaged).
  * *Solusi*: Terapkan `round()` math function pada CSS calc atau pastikan nilai koordinat translasi merupakan nilai integer.

---

## 11. Best Practices (Production Checklist)

### Layout & Architecture
- [ ] Layer registration eksplisit di baris pertama entry-point CSS: `@layer reset, vendor, base, components, utilities;`.
- [ ] Tidak ada unlayered CSS di lingkungan produksi selain isolated emergency hotfix.
- [ ] Selector specificity dijaga maksimal 2 tingkat (misal: `.c-card__title`, bukan `div.content .c-card > h2.c-card__title`).
- [ ] Penggunaan CSS Subgrid untuk grid multidimensi bertingkat demi mempertahankan visual alignment.

### Performance & Engine Optimization
- [ ] Daftar panjang/kartu dinamis dioptimasi dengan `content-visibility: auto; contain-intrinsic-size: auto <dimension>;`.
- [ ] Properti animasi terbatas hanya pada `transform` dan `opacity`. Hindari menganimasikan `width`, `height`, `margin`, `top`, `left`.
- [ ] Hindari penulisan `will-change` secara statis pada selector umum. Terapkan secara dinamis saat interaksi dimulai.
- [ ] Gunakan `font-display: optional` atau `font-display: swap` bersamaan dengan `size-adjust` untuk mengeliminasi Cumulative Layout Shift (CLS).

### Maintainability
- [ ] Seluruh CSS Custom Properties di-namespace secara hierarkis: `--{category}-{domain}-{property}-{state}` (misal: `--color-action-primary-hover`).
- [ ] Dead code elimination diintegrasikan pada build pipeline menggunakan PurgeCSS atau AST-based pruning pada CSS modules.

---

## 12. Hands-on Practice

Berikut adalah panduan langkah demi langkah implementasi arsitektur styling enterprise. Simpan seluruh artefak ke direktori `hands-on/m02/`.

### Struktur File Direktori
```
hands-on/m02/
├── index.html
├── src/
│   ├── layers.css
│   ├── tokens.css
│   ├── components.css
│   └── main.css
└── package.json
```

### Langkah 1: Inisialisasi Environment
Buat file `hands-on/m02/package.json`:
```json
{
  "name": "enterprise-css-architecture",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build"
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "lightningcss": "^1.22.1"
  }
}
```

### Langkah 2: Definisikan Layer Architecture (`src/layers.css`)
```css
/* Registrasi urutan prioritas cascade layer */
@layer reset, base, system, components, utilities;
```

### Langkah 3: Definisikan Multi-tier Token System (`src/tokens.css`)
```css
@layer system {
  :root {
    --core-radius: 8px;
    --core-duration: 200ms;
    --core-timing: cubic-bezier(0.4, 0, 0.2, 1);
    
    --brand-h: 215;
    --brand-s: 90%;
    --brand-l: 50%;
    
    --theme-primary: hsl(var(--brand-h) var(--brand-s) var(--brand-l));
    --theme-surface: hsl(var(--brand-h) 10% 98%);
    --theme-text: hsl(var(--brand-h) 25% 10%);
  }

  [data-theme="dark"] {
    --theme-surface: hsl(var(--brand-h) 20% 12%);
    --theme-text: hsl(var(--brand-h) 10% 95%);
  }
}
```

### Langkah 4: Konstruksi Komponen Berkinerja Tinggi (`src/components.css`)
```css
@layer components {
  .feed-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1.5rem;
    padding: 1.5rem;
    max-width: 1200px;
    margin-inline: auto;
  }

  .virtual-card {
    background-color: var(--theme-surface);
    color: var(--theme-text);
    border-radius: var(--core-radius);
    padding: 1.25rem;
    border: 1px solid oklch(from var(--theme-text) l c h / 0.1);
    
    /* Engine Containment Optimization */
    contain: layout paint;
    content-visibility: auto;
    contain-intrinsic-size: auto 250px;
  }

  .virtual-card__title {
    font-size: 1.25rem;
    margin-bottom: 0.5rem;
    color: var(--theme-primary);
  }
}
```

### Langkah 5: Bundle Entry-Point (`src/main.css`)
```css
@import "./layers.css";
@import "./tokens.css";
@import "./components.css";

@layer reset {
  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
  }
  body {
    background-color: var(--theme-surface);
    font-family: system-ui, sans-serif;
  }
}

@layer utilities {
  .u-force-visible {
    content-visibility: visible !important;
  }
}
```

### Langkah 6: Template Validasi HTML (`index.html`)
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Architecture Testbed</title>
  <link rel="stylesheet" href="./src/main.css">
</head>
<body>
  <button onclick="document.documentElement.dataset.theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'">
    Toggle Theme
  </button>
  <main class="feed-container" id="feed">
    <!-- Simulasikan 500 nodes via Script -->
  </main>
  <script>
    const feed = document.getElementById('feed');
    const fragment = document.createDocumentFragment();
    for(let i = 0; i < 500; i++) {
      const card = document.createElement('article');
      card.className = 'virtual-card';
      card.innerHTML = `<h2 class="virtual-card__title">Item ${i}</h2><p>Performance profile validation card content for Layout and Paint containment benchmarking.</p>`;
      fragment.appendChild(card);
    }
    feed.appendChild(fragment);
  </script>
</body>
</html>
```

---

## 13. Exercise

### Level Easy
1. Buat hierarki cascade layer `@layer base, components, overrides;`.
2. Tulis selektor `#header.nav` di dalam `@layer base` dan beri warna teks biru.
3. Tulis selektor `.nav` di dalam `@layer overrides` dan beri warna teks hijau.
4. **Target**: Buktikan bahwa teks berwarna hijau meskipun specificity selektor di `@layer base` lebih tinggi. Tuliskan analisis alasan teknisnya.

### Level Medium
1. Rancang container layout 3-kolom berbasis CSS Grid di mana setiap kartu memiliki:
   * Header
   * Dynamic variable-height Body content
   * Footer yang terikat rapi di dasar (*bottom-aligned*)
2. Gunakan **CSS Subgrid** (`grid-template-rows: subgrid`) agar seluruh Header dan Footer antar kartu di baris yang sama sejajar secara presisi terlepas dari panjang teks body.
3. Batasi containment elemen kartu menggunakan `contain: layout paint;`.

### Level Hard
1. Implementasikan isolasi tema untuk micro-frontend: Rancang struktur CSS di mana dua micro-frontend (`#mfe-analytics` dan `#mfe-billing`) berjalan berdampingan pada satu halaman.
2. `#mfe-analytics` wajib menggunakan token tema berbasis warna biru (`brand-primary: blue`), sedangkan `#mfe-billing` wajib menggunakan token tema berbasis warna ungu (`brand-primary: purple`).
3. Keduanya harus mengimpor class name komponen yang identik (`.ui-button`), namun warna tombol terisolasi secara native menggunakan konteks `@layer` dan scope scoped Custom Properties tanpa membocorkan style ke luar container aplikasi masing-masing dan tanpa menggunakan iframe.

---

## 14. Challenge

**Skenario Kasus Kompleks (Sistem Desain Multi-Platform)**:
Anda adalah Principal Architect pada perusahaan ride-hailing berskala global. Perusahaan Anda mengakuisisi sistem pihak ketiga yang menggunakan framework UI lama dengan selektor penuh deklarasi spesifisitas tinggi berulang (misal: `body.app-root div#content .widget-box button.btn-submit { ... }`) serta banyak menggunakan `!important`.

**Spesifikasi Tantangan**:
1. Rancang arsitektur integrasi di mana aplikasi induk Anda dapat memuat komponen legacy ini tanpa mengubah source code internal file CSS legacy tersebut (dianggap immutable package).
2. Tentukan hierarki `@layer` khusus, skema scoping, atau mekanisme PostCSS/CSS engine wrapper untuk menjinakkan kode legacy tersebut sehingga utility classes modern milik aplikasi induk (`@layer modern-utilities { .u-hide { display: none; } }`) tetap mengalahkan kode legacy secara deterministik.
3. Selesaikan skenario edge-case: Ketika kode legacy memiliki deklarasi `!important` internal, temukan arsitektur cascade layer untuk menetralkannya agar tidak merusak tema global design system aplikasi induk. Tulis dokumen arsitektur dan potongan CSS implementasi yang memvalidasi konsep ini.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic
1. Mengapa engine browser mengevaluasi selector CSS dari kanan ke kiri (*right-to-left*)?
   * A. Mengikuti orientasi bacaan mesin kompilasi AST C++.
   * B. Untuk memfilter elemen kandidat (key selector) terlebih dahulu sebelum menelusuri rantai parent yang mahal.
   * C. Menjamin precedence `!important` dieksekusi lebih awal.
   * D. Karena DOM tree diproses dari daun (*leaf nodes*) ke root node secara streaming.
2. Jika ada dua deklarasi normal: Aturan A di `@layer reset` dengan selektor `#header` dan Aturan B di `@layer components` dengan selektor `header`, mana yang menang?
   * A. Aturan A karena ID selector memiliki specificity `(1,0,0)`.
   * B. Aturan B karena layer `components` diposisikan setelah layer `reset`.
   * C. Aturan A karena dideklarasikan pertama kali.
   * D. Imbang, browser mengambil urutan deklarasi baris code paling akhir.
3. Manakah properti di bawah ini yang perubahannya HANYA memicu tahapan **Compositing** (tanpa Layout maupun Paint)?
   * A. `margin-top`
   * B. `background-color`
   * C. `transform`
   * D. `top`
4. Apa fungsi dari properti `contain-intrinsic-size` ketika dipasangkan dengan `content-visibility: auto`?
   * A. Menentukan batas maksimal ukuran elemen saat dirender pada GPU.
   * B. Menyediakan placeholder dimensi estimasi geometris agar scrollbar tidak melompat ketika elemen di-skip oleh renderer.
   * C. Mengompresi memory footprint CSSOM dari child elements.
   * D. Menginstruksikan browser untuk mengabaikan kalkulasi CSS Flexbox.
5. Apa efek dari aturan style unlayered (aturan normal yang tidak dibungkus di dalam blok `@layer`) terhadap style yang berada di dalam `@layer`?
   * A. Unlayered style normal selalu mengalahkan layered style normal terlepas dari spesifisitas.
   * B. Unlayered style selalu kalah dari layered style.
   * C. Unlayered style dianggap memiliki layer bernama `default`.
   * D. Unlayered style memicu error kompilasi jika digabungkan dengan `@layer`.

### 15.2. Pertanyaan Intermediate
6. Bagaimana prioritas cascade berubah jika keyword `!important` ditambahkan pada aturan di dalam `@layer base` versus `@layer utilities`?
   * A. `@layer utilities !important` tetap menang atas `@layer base !important`.
   * B. Hierarki terbalik: `@layer base !important` mengalahkan `@layer utilities !important`.
   * C. Kedua aturan saling membatalkan dan browser menggunakan nilai default user-agent.
   * D. Browser mengabaikan keyword `!important` di dalam block `@layer`.
7. Perhatikan kode berikut:
   ```css
   .container { contain: paint; }
   .child { position: fixed; top: 10px; left: 10px; }
   ```
   Bagaimana perilaku rendering elemen `.child`?
   * A. `.child` diposisikan relatif terhadap browser viewport.
   * B. `.child` diposisikan relatif terhadap `.container` karena `contain: paint` menciptakan containing block baru untuk fixed positioning.
   * C. `.child` tidak terlihat sama sekali (tersembunyi secara permanen).
   * D. Engine membatalkan deklarasi `position: fixed` dan mengubahnya menjadi `static`.
8. Apa dampak arsitektural dari dynamic mutation ratusan CSS Custom Properties langsung pada selector `:root` melalui JavaScript per frame (misal pada event `mousemove`)?
   * A. Reflow total pada seluruh node aplikasi karena dependency recalculation cascade global.
   * B. Tidak ada dampak sama sekali karena variable CSS diisolasi di GPU memory.
   * C. Garbage collection stall akibat serialisasi string CSSOM berulang.
   * D. Hanya element yang mengonsumsi variable tersebut yang terhapus dari DOM.
9. Mengapa penggunaan CSS Subgrid lebih efisien dibandingkan membuat nested Flexbox berulang untuk meluruskan elemen antar kartu independen?
   * A. Subgrid mengurangi jumlah DOM node yang dibutuhkan dan menyatukan kalkulasi track layout dalam single-pass pipeline pada parent grid context.
   * B. Subgrid memindahkan rendering kartu langsung ke phase raster Skia.
   * C. Subgrid otomatis mengaktifkan `contain: size` pada semua child nodes.
   * D. Subgrid tidak memerlukan fase Recalculate Style.
10. Dalam diagram spesifikasi cascade modern, di manakah posisi prioritas deklarasi animasi CSS (`@keyframes`) normal?
    * A. Di bawah normal author declarations.
    * B. Di atas semua normal author declarations, tetapi di bawah deklarasi `!important` author.
    * C. Di atas `!important` author declarations.
    * D. Paling rendah sebelum user-agent styles.

### 15.3. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah tim e-commerce melaporkan bahwa metrik *Interaction to Next Paint* (INP) mereka melonjak buruk menjadi 480ms ketika pengguna menekan tombol filter produk yang merender 2.000 list card produk secara instan. Hasil DevTools Performance mencatat event *Recalculate Style* dan *Layout* memakan waktu 380ms. Tindakan arsitektural CSS mana yang memberikan perbaikan paling signifikan dengan refactoring minimal?
    * A. Menambahkan `transform: translateZ(0)` ke seluruh 2.000 card.
    * B. Mengimplementasikan `content-visibility: auto; contain-intrinsic-size: 0 120px;` pada class item list card.
    * C. Mengubah seluruh layout grid menjadi model kalkulasi manual berbasis `calc()` dan float.
    * D. Membungkus seluruh class produk ke dalam `@layer framework`.
12. **Skenario 2**: Anda mengintegrasikan library design system pihak ketiga yang menempelkan style:
    ```css
    @layer vendor {
      .input-text { border: 1px solid red !important; }
    }
    ```
    Bagaimana cara tim Anda menimpa deklarasi warna border tersebut menggunakan stylesheet aplikasi Anda sendiri (`@layer app`) tanpa menghapus file vendor?
    * A. Membuat aturan di `@layer app { .input-text { border: 1px solid blue !important; } }`.
    * B. Membuat aturan unlayered: `.input-text { border: 1px solid blue !important; }`.
    * C. Mendefinisikan layer urutan baru di mana vendor ditaruh setelah app: `@layer app, vendor;`, lalu memberikan aturan normal di app.
    * D. Mendaftarkan layer baru sebelum vendor: `@layer base-override, vendor;` dan mendeklarasikan `.input-text { border: 1px solid blue !important; }` di dalam `@layer base-override`.
13. **Skenario 3**: Sebuah aplikasi web enterprise mengalami masalah *layout thrashing* parah saat memproses chart responsif dinamis. Ditemukan kode legacy:
    ```javascript
    cards.forEach(card => {
      const height = card.getBoundingClientRect().height;
      card.style.setProperty('--card-computed-h', `${height * 1.5}px`);
    });
    ```
    Solusi restrukturisasi apa yang wajib diambil?
    * A. Pisahkan fase baca (`getBoundingClientRect`) seluruh card ke loop pertama, lalu lakukan modifikasi variabel pada loop kedua (Read-then-Write separation), atau gunakan CSS Container Queries / Layout Sizing intrinsik untuk mengeliminasi JS measurement seutuhnya.
    * B. Tambahkan `!important` ke dalam pemanggilan `style.setProperty`.
    * C. Bungkus seluruh kode JavaScript di dalam event listener `window.onscroll`.
    * D. Ganti Custom Property menjadi atribut inline HTML `data-height`.

---

### Kunci Jawaban & Pembahasan Evaluasi

#### Basic
1. **B**: Engine mencocokkan *key selector* (ujung kanan) terlebih dahulu untuk mengeliminasi 90%+ elemen yang tidak relevan, membatasi penelusuran hierarki ancestor.
2. **B**: Pada aturan normal, layer yang dideklarasikan belakangan (`components`) selalu menang atas layer sebelumnya (`reset`), terlepas dari perbedaan spesifisitas selektor.
3. **C**: `transform` dimanipulasi murni pada GPU Compositor thread tanpa memerlukan kalkulasi ulang box geometry (Layout) atau penggambaran ulang piksel visual (Paint).
4. **B**: Mencegah tinggi container anjlok menjadi 0 piksel saat subtree di luar viewport diabaikan oleh engine, menjaga stabilitas scrollbar dan mengeliminasi CLS.
5. **A**: Berdasarkan spesifikasi CSS Cascading Level 5, unlayered normal styles memiliki ranking precedence lebih tinggi dibanding layered normal styles.

#### Intermediate
6. **B**: Terjadi pembalikan prioritas cascade layers khusus untuk deklarasi berkata kunci `!important`. Tujuannya memberi kemampuan pada layer dasar/infrastruktur memproteksi sistem dari modifikasi layer di atasnya.
7. **B**: Properti `contain: paint` menciptakan stacking context baru dan containing block absolut untuk semua elemen descendant, termasuk yang memiliki `position: fixed`.
8. **A**: Mengubah variabel pada root scope memaksa browser melakukan traversal ke seluruh DOM tree aktif untuk mengalkulasi ulang node-node yang mewarisi variabel tersebut.
9. **A**: Subgrid menyematkan struktur layout child ke dalam track grid parent tunggal, mengurangi overhead komputasi fragmentasi layout bertingkat.
10. **B**: CSS Animations berada di atas seluruh deklarasi author normal (termasuk unlayered), namun berada tepat di bawah author `!important`.

#### Skenario Produksi
11. **B**: `content-visibility: auto` memangkas rendering cost secara masif karena engine langsung mengabaikan style calculation, layout, dan paint untuk kartu-kartu yang berada di luar viewport layar.
12. **D**: Karena aturan vendor menggunakan `!important`, layer yang dideklarasikan **sebelum** vendor (`base-override`) memiliki kekuasaan cascade `!important` lebih tinggi daripada layer vendor itu sendiri. Unlayered `!important` (opsi B) justru kalah terhadap layered `!important`.
13. **A**: Masalah forced synchronous layout terjadi akibat interleaved read-write geometri. Memisahkan fase baca dan tulis atau menyerahkan resizing ke CSS Container Queries menghilangkan layout thrashing secara mendasar.

---

## 16. Summary

1. **Rendering Pipeline Determinism**: Memahami siklus CSSOM $\rightarrow$ Layout $\rightarrow$ Paint $\rightarrow$ Composite adalah fondasi mutlak untuk menulis CSS berkinerja tinggi. Hindari manipulasi properti yang memicu reflow luas pada frame loop.
2. **Cascade Layers (`@layer`)**: Membawa determinisme mutlak ke dalam arsitektur CSS modern, membebaskan sistem dari perang spesifisitas. Ingat selalu hukum pembalikan urutan prioritas untuk deklarasi bernilai `!important`.
3. **CSS Containment**: Fitur seperti `contain` dan `content-visibility` mengubah paradigma rendering dokumen web berskala besar, memfasilitasi lazy evaluation setingkat native rendering engine.
4. **Zero-Runtime Dynamic Scalability**: Melalui CSS Custom Properties yang terdistribusi terstruktur dan kompilasi waktu build modern, aplikasi web enterprise dapat menyajikan dynamic theming kompleks tanpa mengorbankan metrik performa Core Web Vitals (INP, CLS, TBT).