# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 09: Enterprise Performance Optimization, Accessibility, dan Tooling/Testing**

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Principal Engineeer dan Senior Frontend Architect diharapkan mampu:
- Menganalisis siklus hidup *rendering pipeline* browser (Blink/Gecko) secara mendalam, dari resolusi CSSOM, *Rule Matching Tree*, *Style Invalidation*, hingga tahapan *Compositing* pada GPU.
- Mendiagnosis dan mengeliminasi *bottleneck* performa rendering seperti *Layout Thrashing*, *Excessive Style Recalculation*, serta lonjakan konsumsi VRAM akibat layerisasi (*Compositor Layer Explosion*).
- Merancang dan mengeksekusi strategi mitigasi Core Web Vitals (INP, LCP, CLS) berbasis CSS murni dan *hybrid tooling* melalui *sub-tree containment* (`content-visibility`), *critical CSS injection*, dan metrik koreksi font (*font metric overrides*).
- Mengonstruksi arsitektur Design Token enterprise yang mematuhi standar WCAG 2.2 Level AAA, mencakup *contrast ratio*, *motion sensitivity* (`prefers-reduced-motion`), dan *forced colors mode* (`forced-colors: active`).
- Mengembangkan *end-to-end automated testing harness* untuk CSS yang mengintegrasikan validasi AST (Stylelint), *accessibility assertion* (axe-core), dan *Visual Regression Testing* (Playwright + Pixelmatch) dalam pipeline CI/CD berkinerja tinggi.

---

### 2. Prerequisites & Assumptions
Sebelum mendalami modul ini, Anda diasumsikan telah menguasai:
- **Spesifikasi CSS Modern**: CSS Custom Properties Level 1, CSS Containment Module Level 3, CSS Grid/Flexbox Layout, dan CSS Selectors Level 4.
- **Runtime Browser & DOM**: Pemahaman arsitektur multi-proses Chromium (Browser Process, Renderer Process, GPU Process), V8 Event Loop, serta RequestAnimationFrame (rAF).
- **Tooling & Build System**: Pengalaman mengonfigurasi PostCSS, LightningCSS, Vite/Webpack, dan eksekusi skrip Node.js untuk manipulasi build pipelines.
- **Dasar Testing**: Pengalaman menulis unit testing dan end-to-end automation menggunakan JavaScript/TypeScript.

---

### 3. Conceptual Architecture & Internal Mechanics

#### 3.1. Browser Rendering Engine Pipeline (Chromium Blink Deep-Dive)
Browser tidak langsung menerapkan CSS ke DOM. Proses ini melewati serangkaian tahapan diskrit:

```
[HTML] -> DOM Tree \
                     --> [Style Resolution / Recalc] -> Layout Object Tree -> Paint Invalidation -> Compositor Tiling -> GPU Raster -> Screen
[CSS]  -> CSSOM     /      (Rule Hash Map Matching)      (Fragment Tree)      (Display Lists)     (cc::LayerTree)    (Skia/Ganesh)
```

1. **CSSOM Construction & Rule Indexing**:
   Blink mengurai lembar gaya (*style sheets*) menjadi representasi internal `StyleSheetContents`. Aturan (*rules*) diindeks ke dalam hash maps berdasarkan *rightmost selector* (Key Selector), dikelompokkan berdasarkan ID, Class, Tag, dan Universal selector. Ketika elemen DOM dievaluasi, browser tidak melakukan traversal linear, melainkan mengambil kandidat aturan dari hash map yang cocok dengan `Key Selector`.

2. **Style Resolution & Invalidation**:
   Ketika mutasi DOM atau kelas terjadi, browser menandai elemen sebagai *dirty* melalui mekanisme `ScheduleStyleInvalidation`. Blink menggunakan Bloom Filters untuk mempercepat pengecekan selektor leluhur (*ancestor selectors*). Jika terjadi modifikasi pada CSS custom properties (`var(--custom-prop)`), mutasi tersebut secara rekursif membatalkan (*invalidates*) seluruh sub-tree yang mereferensikan variabel tersebut, memicu *Recalculate Style* berskala besar.

3. **Layout & Box Tree (LayoutNG / Fragment Tree)**:
   Style resolution menghasilkan `LayoutObject` tree. Engine kemudian menghitung geometri: koordinat $(x, y)$, *width*, *height*, *margin*, *padding*, dan *borders*. Hasil akhirnya disimpan dalam struktur *immutable* yang disebut `NGPhysicalFragment`. Pembacaan properti geometri (seperti `element.offsetWidth` atau `getComputedStyle()`) secara intermiten sebelum siklus layout selesai akan memaksa browser menjalankan *Synchronous Forced Layout* (*Layout Thrashing*).

4. **Paint & Compositing (Blink Paint Artifact / CompositeAfterPaint)**:
   - **Paint**: Menghasilkan daftar instruksi visual (*Display Items* atau *Paint Operations*, misal: "gambar persegi", "cetak teks"), bukan piksel aktual.
   - **Layerization**: Engine membagi halaman menjadi layer-layer independen (`cc::Layer`). Elemen dengan transformasi 3D, tag `<video>`, `<canvas>`, atau elemen dengan properti CSS `will-change: transform` dipromosikan ke layer compositing khusus.
   - **Tiling & Rasterization**: Compositor membagi layer menjadi ubin (*tiles*) berukuran 256x256 atau 512x512 piksel. Pekerja rasterisasi (*Raster Workers*) menerjemahkan display lists menjadi representasi bitmap via library grafis (Skia/Ganesh atau Graphite) dengan akselerasi perangkat keras GPU.
   - **Draw Quad Generation**: Compositor menghasilkan *quads* yang dikirimkan ke GPU Process (Display Compositor / Viz) untuk diproyeksikan langsung ke layar melalui API grafis level rendah (DirectX, Vulkan, atau Metal).

#### 3.2. Subtree Containment & Content Visibility
Properti `content-visibility: auto` mematikan proses rendering (Style, Layout, Paint) untuk elemen-elemen di luar *viewport* secara dinamis, mengemulasi *virtualization* tanpa manipulasi DOM di layer JavaScript.

```
+------------------------------------------+
| Viewport                                 |
| +--------------------------------------+ |
| | Section 1 (Rendered: Style/Layout/Paint| |
| +--------------------------------------+ |
+------------------------------------------+
  Section 2 (Skipped Subtree: Size only)    <-- content-visibility: auto
  contain-intrinsic-size: 1000px;              Layout Boundary Terjaga
+------------------------------------------+
```

Ketika `content-visibility: auto` aktif pada elemen yang *off-screen*:
- Browser menerapkan aturan: `contain: content` (ekuivalen dengan `contain: layout paint style`).
- Rendering engine melewati proses parsing fragment anak (*skip subtree layout & paint*).
- Untuk mencegah hilangnya total tinggi elemen yang mengakibatkan kolapsnya *scrollbar* (berujung pada Cumulative Layout Shift / CLS yang ekstrem), diwajibkan menyertakan `contain-intrinsic-size`, yang mengalokasikan ruang geometris *placeholder* hingga elemen mendekati margin observasi viewport.

#### 3.3. Font Metric Overrides & CLS Prevention
Penyebab utama Cumulative Layout Shift (CLS) saat *font swapping* (`font-display: swap`) adalah deviasi metrik glif antara *fallback font* bawaan sistem (seperti Arial atau Times New Roman) dan Web Font eksternal (seperti Inter atau Roboto). 

Browser menghitung dimensi teks menggunakan empat parameter utama:
- `ascent`: Jarak dari baseline ke titik tertinggi glif.
- `descent`: Jarak dari baseline ke titik terendah glif.
- `line-gap`: Spasi default antar baris teks.
- `size-adjust`: Skala rasio bounding box seluruh glif.

Dengan mendefinisikan `@font-face` *fallback* yang metriknya diselaraskan menggunakan CSS `@font-face` overrides (`ascent-override`, `descent-override`, `line-gap-override`), *layout footprint* teks fallback akan identik hingga ke tingkat sub-piksel dengan web font target, meniadakan CLS ketika aset web font selesai diunduh.

---

### 4. Why This Architecture Matters & Problem Statement

#### 4.1. The Performance Cliff: Layer Explosion & VRAM Depletion
Penggunaan `will-change: transform` atau `translateZ(0)` yang tidak terukur pada ribuan elemen list sering dianggap sebagai solusi akselerasi hardware. Kenyataannya, strategi ini dapat memicu *Compositor Layer Explosion*. 

Setiap layer compositing membutuhkan buffer tekstur di memori GPU. 
$$\text{GPU Memory per Layer} = \text{Width} \times \text{Height} \times 4 \text{ Bytes (RGBA8888)}$$
Pada layar retina (DPR 2 atau 3), layer berukuran $400 \times 100$ piksel menyerap:
$$400 \times 2 \times 100 \times 2 \times 4 = 640.000 \text{ bytes} \approx 625 \text{ KB VRAM}$$
Jika diterapkan ke 1.000 item daftar transaksi, VRAM browser akan terbebani sebesar $>600 \text{ MB}$. Hal ini memaksa GPU melakukan *texture trashing* atau memicu browser jatuh ke *fallback software rendering*, yang berakibat pada drop frame drastis ($<15 \text{ FPS}$) dan penurunan performa Interaction to Next Paint (INP).

#### 4.2. Accessibility: WCAG 2.2 AAA & APCA
Arsitektur warna enterprise lawas yang hanya mengandalkan rasio kontras WCAG 2.1 ($4.5:1$ untuk teks normal) sering kali gagal pada mode gelap (*Dark Mode*) atau skenario teks terang di atas latar belakang gelap karena persepsi spasial fotometrik manusia bersifat non-linear. WCAG 2.2 merekomendasikan kepatuhan terhadap APCA (*Accessible Perceptual Contrast Algorithm*) dan penanganan sistematis terhadap preferensi pengguna OS:
- `prefers-reduced-motion`: Mencegah disorientasi vestibular.
- `forced-colors`: Memastikan UI tetap berfungsi saat High Contrast Mode aktif di Windows.
- `prefers-color-scheme`: Mengisolasi palet warna secara konsisten melalui Semantic Tokens.

---

### 5. Step-by-Step Implementation Workflow

Diagram alur berikut mendemonstrasikan orkestrasi optimal dari proses build hingga eksekusi runtime browser:

```
[SCSS / CSS Modules]
        │
        ▼
[LightningCSS Engine] ──(Transform & Polyfill)
        │
        ▼
[Critical CSS Splitting] ──> Inline to <head> (HTML Payload)
        │
        ▼
[Non-Critical Bundles] ──> Preload & Async Load via media="print" onload="this.media='all'"
        │
        ▼
[Browser Parsing Phase]
   ├── 1. Inline Stylesheets Evaluated
   ├── 2. Font Metrics Overridden (Zero-CLS Fallbacks)
   ├── 3. Subtree Containment Initialized (content-visibility: auto)
   └── 4. Style Invalidation Paths Isolated (Container Queries & Strict Scope)
```

1. **Build Phase Token Compilation**:
   - Kompilasi Design Tokens dari format platform-agnostik (W3C Design Tokens Community Group format) ke CSS Custom Properties murni.
   - Pengecekan kontras otomatis di build time melalui script AST assertion.
2. **Bundle Splitting & Critical Extraction**:
   - Ekstrak CSS yang dibutuhkan untuk rendering First Contentful Paint (FCP) di atas *viewport* (Above the Fold).
   - Injeksi Critical CSS langsung ke blok `<style>` di dalam `<head>`.
   - Pisahkan non-critical CSS ke berkas chunk terkompresi Brotli/Gzip.
3. **Font Layout Anchoring**:
   - Definisikan Fallback Local Font dengan `@font-face` overriding metrik.
   - Muat Web Font via tag `<link rel="preload" as="font" type="font/woff2" crossorigin>`.
4. **Runtime Rendering Boundary Isolation**:
   - Isolasi komponen berat (seperti DataTable, infinite scroll grid) menggunakan `content-visibility: auto` dan `contain: paint layout`.
   - Alokasikan estimasi ukuran dimensional via `contain-intrinsic-size`.
5. **Continuous Verification**:
   - Linting CSS AST via Stylelint.
   - Axe-core validation untuk pohon DOM yang dirender.
   - Visual Regression snapshot dengan threshold deviasi piksel $\le 0.02\%$.

---

### 6. System Architecture & Component Interactions

```
+------------------------------------------------------------------------------------+
| CI/CD Pipeline & Build Orchestration                                               |
|                                                                                    |
|  +------------------------+      +-----------------------+                         |
|  | Design Token (JSON)    | ---> | Token Processor Engine|                         |
|  +------------------------+      +-----------+-----------+                         |
|                                              |                                     |
|                                              v                                     |
|  +-------------------------------------------+----------------------------------+  |
|  | CSS Artifacts Generation (LightningCSS / PostCSS)                            |  |
|  | - WCAG 2.2 AAA Dynamic Color System (APCA Checked)                           |  |
|  | - Font Metrics Adjusted (ascent/descent/size-adjust)                         |  |
|  | - Containment Rules Injected                                                 |  |
|  +-------------------------------------------+----------------------------------+  |
|                                              |                                     |
|               +------------------------------+------------------------------+      |
|               |                                                             |      |
|               v                                                             v      |
|  +-------------------------+                               +--------------------+  |
|  | Critical Path Extractor |                               | Bundle Packager    |  |
|  +------------+------------+                               +----------+---------+  |
+---------------|-------------------------------------------------------|------------+
                |                                                       |
                v                                                       v
+------------------------------------------------------------------------------------+
| Client Browser Runtime Environment                                                 |
|                                                                                    |
|  +---------------------------------------+   +----------------------------------+  |
|  | <head> Inlined Critical CSS           |   | Deferred Stylesheet Payload      |  |
|  | - Font Metrik Baseline                |   | - Off-screen Component Rules     |  |
|  | - Structural Shell Tokens             |   | - Complex Micro-interactions     |  |
|  +-------------------+-------------------+   +----------------+-----------------+  |
|                      |                                        |                    |
|                      +-------------------+--------------------+                    |
|                                          |                                         |
|                                          v                                         |
|  +------------------------------------------------------------------------------+  |
|  | Blink Engine Runtime Processing                                              |  |
|  |  [Rule Hash Matching Engine]                                                 |  |
|  |              │                                                               |  |
|  |              ▼                                                               |  |
|  |  [Computed Style Tree] <--- (Scoped Variable Boundary via container-type)   |  |
|  |              │                                                               |  |
|  |              ▼                                                               |  |
|  |  [Fragment Tree / Layout]                                                    |  |
|  |         ├── Visible Viewport  ---> LayoutNG Full Processing                  |  |
|  |         └── Off-screen Subtree --> Bypassed via content-visibility: auto    |  |
|  |                                    (contain-intrinsic-size boundary)         |  |
|  |              │                                                               |  |
|  |              ▼                                                               |  |
|  |  [Compositor Layer Promotion]                                                |  |
|  |         ├── will-change guarded dynamically via Pointer Events               |  |
|  |         └── Low VRAM Memory Allocation via Tiled Backing                     |  |
|  +------------------------------------------------------------------------------+  |
+------------------------------------------------------------------------------------+
```

---

### 7. Code Implementation: Minimalist Baseline vs. Production-Grade Engine

#### 7.1. Implementasi Naif / Anti-Pattern (Problematic)
Berikut contoh kode yang sering dijumpai pada sistem yang mengalami degradasi performa dan pelanggaran aksesibilitas:

```html
<!-- BAD: Font blocking, Layout Thrashing, Memory Leaks, Inaccessible Tokens -->
<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Menghambat Critical Path: Eksternal Google Fonts blocking render -->
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap" rel="stylesheet">
  <style>
    /* Global Universal Selector - Memory inefficient style invalidation */
    * {
      box-sizing: border-box;
      transition: all 0.3s ease; /* Pemicu Layout Thrashing pada semua properti */
    }

    /* VRAM Eruption: Mempromosikan setiap elemen ke GPU Layer secara permanen */
    .card-item {
      will-change: transform, opacity;
      transform: translateZ(0);
      /* Kontras warna buruk: #767676 di atas #FFFFFF (rasio 4.54:1 - batas tipis, gagal AAA) */
      color: #767676;
      background: #FFFFFF;
    }

    /* Mengabaikan reduced motion dan high contrast */
    .animated-spinner {
      animation: spin 1s infinite linear;
    }
    @keyframes spin {
      100% { transform: rotate(360deg); }
    }
  </style>
</head>
<body>
  <div class="card-item">
    <div class="animated-spinner"></div>
    Bad Performance Architecture
  </div>
</body>
</html>
```

#### 7.2. Implementasi Produksi (Production-Grade Architecture)
Solusi enterprise berikut menerapkan arsitektur token WCAG 2.2 AAA, pencegahan CLS berbasis penyesuaian metrik font, optimasi rendering sub-tree, serta isolasi compositing layer.

##### Berkas: `tokens/accessibility-palette.css`
```css
/* ==========================================================================
   ENTERPRISE DESIGN SYSTEM: ACCESSIBILITY & CONTRAST TOKENS
   Standard: WCAG 2.2 Level AAA Compliance & Perceptual Lightness Tuning
   ========================================================================== */

:root {
  /* Absolute color space primitives (Oklch for perceptual uniformity) */
  --sys-color-canvas-light: oklch(0.99 0.002 240);
  --sys-color-canvas-dark: oklch(0.14 0.005 240);
  
  --sys-color-ink-light: oklch(0.18 0.01 240);  /* > 12:1 Contrast Ratio */
  --sys-color-ink-dark: oklch(0.96 0.005 240);  /* > 12:1 Contrast Ratio */

  --sys-color-focus-light: oklch(0.45 0.28 264);
  --sys-color-focus-dark: oklch(0.75 0.18 264);

  /* Semantic Application Bindings (Default: Light Mode) */
  --color-surface-base: var(--sys-color-canvas-light);
  --color-surface-elevated: oklch(1 0 0);
  --color-text-primary: var(--sys-color-ink-light);
  --color-outline-focus: var(--sys-color-focus-light);

  /* Elevation primitives decoupled from heavy paints */
  --elevation-ring: 0 0 0 1px oklch(0 0 0 / 0.08);
  --elevation-shadow: 0 4px 12px -2px oklch(0 0 0 / 0.06);

  /* Motion parameters: Core Physics Engine Tokens */
  --motion-duration-fast: 150ms;
  --motion-duration-medium: 250ms;
  --motion-ease-standard: cubic-bezier(0.2, 0, 0, 1);
  --motion-ease-out: cubic-bezier(0, 0, 0.2, 1);
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-surface-base: var(--sys-color-canvas-dark);
    --color-surface-elevated: oklch(0.20 0.005 240);
    --color-text-primary: var(--sys-color-ink-dark);
    --color-outline-focus: var(--sys-color-focus-dark);
    --elevation-ring: 0 0 0 1px oklch(1 1 1 / 0.12);
    --elevation-shadow: 0 4px 16px -2px oklch(0 0 0 / 0.4);
  }
}

/* Fallback & Enforcement for OS High Contrast Mode (Windows / Assistive Tech) */
@media (forced-colors: active) {
  :root {
    --color-surface-base: Canvas;
    --color-surface-elevated: Canvas;
    --color-text-primary: CanvasText;
    --color-outline-focus: Highlight;
    --elevation-ring: 0 0 0 2px CanvasText;
    --elevation-shadow: none;
  }
}
```

##### Berkas: `typography/font-metrics.css`
```css
/* ==========================================================================
   ZERO-CLS WEB FONT METRIC OVERRIDES
   Font target: Inter Display (WOFF2)
   Fallback target: Arial & Helvetica (System-dependent)
   Calculations aligned to 0 Cumulative Layout Shift
   ========================================================================== */

/* 1. System Fallback with Adjusted Dimensions */
@font-face {
  font-family: 'Fallback-Inter';
  src: local('Arial'), local('Helvetica');
  /* Rasion kalkulasi: Mengubah tinggi font fallback agar matching dengan Inter */
  ascent-override: 89.71%;
  descent-override: 22.43%;
  line-gap-override: 0.00%;
  size-adjust: 107.68%;
}

/* 2. Web Font Definitive Declaration */
@font-face {
  font-family: 'Inter-Enterprise';
  src: url('/fonts/inter-latin-variable.woff2') format('woff2-variations');
  font-weight: 100 900;
  font-display: optional; /* Menghilangkan FOIT & mengeliminasi Layout Invalidation */
  font-style: normal;
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC;
}

body {
  font-family: 'Inter-Enterprise', 'Fallback-Inter', sans-serif;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
```

##### Berkas: `components/enterprise-virtual-list.css`
```css
/* ==========================================================================
   HIGH-PERFORMANCE DATA-SURFACE COMPONENT ARCHITECTURE
   Techniques: Subtree Containment, Compositor Isolation, Motion Gating
   ========================================================================== */

.data-grid-viewport {
  width: 100%;
  min-height: 100vh;
  contain: layout size; /* Membatasi invalidasi layout hanya pada kontainer ini */
  background-color: var(--color-surface-base);
  color: var(--color-text-primary);
}

.data-row-card {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 1.25rem;
  margin-block-end: 1rem;
  background-color: var(--color-surface-elevated);
  box-shadow: var(--elevation-shadow);
  border-radius: 0.5rem;
  border: 1px solid transparent;

  /* PERFORMANCE CORE: Subtree bypass for off-screen nodes */
  content-visibility: auto;
  contain-intrinsic-size: auto 98px; /* Estimasi tinggi akurat untuk mencegah CLS saat scroll */

  /* Mencegah propagasi recalculate style */
  contain: layout paint style;
  
  /* Transisi terbatas: DILARANG transisi 'all'. Hanya komposit transform dan opacity */
  transition: 
    box-shadow var(--motion-duration-fast) var(--motion-ease-standard),
    border-color var(--motion-duration-fast) var(--motion-ease-standard);
}

/* Compositing Strategy: Promosikan layer HANYA saat ada indikasi interaksi */
.data-row-card:hover {
  border-color: var(--color-outline-focus);
}

@media (hover: hover) and (pointer: fine) {
  .data-row-card {
    /* Mencegah will-change permanen. Diaktifkan via class state saat user scrolling/hovering */
    will-change: auto;
  }
  
  .data-row-card:active {
    /* Akselerasi instan tanpa overhead alokasi layer jangka panjang */
    transform: scale(0.998);
  }
}

/* ==========================================================================
   A11Y ACCESSIBILITY FOCUS MANAGEMENT & MOTION MITIGATION
   ========================================================================== */

.data-row-card:focus-visible {
  outline: 3px solid var(--color-outline-focus);
  outline-offset: 2px;
  /* Visual highlight tetap terlihat meski High Contrast Mode OS aktif */
  forced-color-adjust: none; 
}

/* Disable/Flatten animations globally for users with vestibular disorders */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

---

### 8. Real-World Enterprise Scenario & Scalability Analysis

#### Skenario Kasus: Sistem FinTech Global Enterprise (Core Banking Dashboard)
- **Kondisi Beban**: Antarmuka dashboard real-time yang menerima 200 data updates/detik via WebSockets untuk ribuan entri order book bursa saham.
- **Masalah Produksi**: 
  - Penurunan FPS drastis hingga 12-18 FPS pada monitor 144Hz.
  - Skor *Cumulative Layout Shift* (CLS) sebesar 0.42 saat pertama kali dimuat.
  - Interaction to Next Paint (INP) membengkak menjadi 480ms pada perangkat kelas menengah (*mid-tier hardware*).
  - DevTools Timeline memperlihatkan pemanggilan `Recalculate Style` sebesar 68ms per frame dan alokasi GPU memory mencapai 1.4 GB.

```
+-------------------------------------------------------------------------------+
| Pipeline Analisis & Mitigasi Bottleneck Dashboard                             |
+-------------------------------------------------------------------------------+
| WebSocket Tick (200 ops/s)                                                    |
|        │                                                                      |
|        ▼                                                                      |
| [Mutasi DOM Kelas Global] ──> Style Recalculate Mencakup 45.000 Elemen DOM    |
|                                                                               |
| SOLUSI ARSITEKTUR:                                                            |
| 1. Pasang `contain: strict` pada komponen data cell individual.               |
| 2. Pisahkan stream render ke `content-visibility: auto`.                     |
| 3. Matikan alokasi layer statis (`will-change` dihapus dari 3.000 elemen).    |
| 4. Sisipkan Font Metric Overrides untuk mengunci layout.                      |
+-------------------------------------------------------------------------------+
```

#### Hasil Metrik Komparatif
| Metrik Produksi | Baseline (Legacy Architecture) | Pasca-Optimasi Arsitektur | Target SLA Perusahaan |
| :--- | :--- | :--- | :--- |
| **LCP (Largest Contentful Paint)** | 3.84 s | **1.12 s** | $\le 2.0 \text{ s}$ |
| **CLS (Cumulative Layout Shift)** | 0.420 | **0.001** | $\le 0.05$ |
| **INP (Interaction to Next Paint)**| 480 ms | **38 ms** | $\le 100 \text{ ms}$ |
| **Style Recalculation Time** | 68 ms / frame | **2.1 ms / frame** | $\le 5 \text{ ms}$ |
| **GPU VRAM Allocation** | 1,420 MB | **86 MB** | $\le 150 \text{ MB}$ |
| **Frame Rate Rendering** | 15 - 22 FPS | **Stable 60 / 120 FPS** | $\ge 60 \text{ FPS}$ |

---

### 9. Engineering Trade-offs & Operational Impact Matrix

| Keputusan Arsitektur | Keuntungan (*Pros*) | Kerugian & Batasan (*Cons*) | Skenario Penggunaan yang Direkomendasikan |
| :--- | :--- | :--- | :--- |
| **`content-visibility: auto`** | Mengurangi beban style recalc dan layout hingga 80-90% pada halaman panjang; FCP & INP meningkat signifikan. | Fitur pencarian peramban *Find-in-Page* (Ctrl+F) memerlukan engine modern (Chromium >90); tinggi scrollbar bisa bergetar jika `contain-intrinsic-size` tidak akurat. | Infinite feeds, data grid, dokumentasi teknis berukuran masif (>500 baris DOM). |
| **`font-display: optional`** | Mengeliminasi CLS secara total; tidak ada lonjakan memori akibat penataan ulang glif teks (*relayout*). | Pengguna dengan koneksi seluler lambat (High Latency) akan sepenuhnya melihat font lokal fallback pada sesi kunjungan pertama (*session-1*). | Web aplikasi transaksional/enterprise, SaaS B2B, portal perbankan dengan retensi pengguna rutin. |
| **`will-change` Dinamis** | Menjaga memori VRAM GPU serendah mungkin; rendering tetap mulus tanpa konsumsi memori berlebih. | Membutuhkan dependensi pada JavaScript event harness (misal via `pointerenter`/`pointerleave`) untuk menambahkan/menghapus kelas. | Komponen list yang kompleks, UI interaktif, aplikasi desktop berbasis Electron. |
| **Desain Token WCAG AAA (Oklch)** | Keterbacaan visual matematis teruji; tidak terdistorsi pada spektrum kecerahan monitor yang berbeda. | Palet warna cenderung lebih ketat dan kontras ekstrem; desainer grafis mungkin merasa terbatas secara estetika. | Aplikasi finansial kritis, dashboard analitik medis, sistem penerbangan, dan pemerintahan. |

---

### 10. Failure Modes, Edge Cases, Anti-Patterns & Troubleshooting

#### 10.1. Layout Thrashing (Forced Synchronous Layout)
- **Indikasi**: Chrome DevTools menampilkan bar merah bergerigi dengan peringatan: *"Forced reflow is a likely bottleneck"*.
- **Penyebab**: Menulis mutasi CSS (misal `element.classList.add()`) kemudian secara langsung membaca geometri DOM (`element.offsetHeight`, `getBoundingClientRect()`) dalam perulangan yang sama.
- **Solusi Troubleshooting**: Terapkan arsitektur *Read-First-Then-Write*, atau serahkan mutasi ke `requestAnimationFrame()`:
  ```javascript
  // ANTI-PATTERN: Forced Synchronous Layout Loop
  items.forEach(el => {
    el.style.width = '100px'; // Write
    const h = el.clientHeight; // READ: Memaksa LayoutNG mengkalkulasi ulang secara sinkron
  });

  // PRODUCTION PATTERN: Batching Read/Write
  const heights = items.map(el => el.clientHeight); // BATCH READ
  requestAnimationFrame(() => {
    items.forEach((el, i) => {
      el.style.width = '100px'; // BATCH WRITE di boundary frame berikutnya
    });
  });
  ```

#### 10.2. Scrollbar Jittering Akibat Desinkronisasi `contain-intrinsic-size`
- **Indikasi**: Scrollbar melompat liar (*jumping/stuttering*) saat user menggulir ke arah bawah dengan kecepatan konstan.
- **Penyebab**: Nilai placeholder dimensi yang diberikan ke `contain-intrinsic-size` sangat jauh berbeda dengan tinggi render aktual dari elemen.
- **Solusi**: Manfaatkan sintaksis modern `contain-intrinsic-size: auto [estimated_height]`. Fitur `auto` memerintahkan engine peramban untuk mengingat ukuran elemen terakhir setelah elemen tersebut sempat dirender sekali, mencegah layout shift sekunder:
  ```css
  /* CORRECTION */
  .feed-post {
    content-visibility: auto;
    contain-intrinsic-size: auto 350px; /* Nilai fallback 350px, digantikan auto-cache setelah render */
  }
  ```

#### 10.3. "Ghost" Focus Rings pada Forced Colors Mode
- **Indikasi**: Tombol kustom atau elemen interaktif kehilangan outline penanda fokus saat diakses pengguna dengan High Contrast Mode Windows aktif.
- **Penyebab**: Penggunaan selektor `outline: none` tanpa menyediakan *replacement outline* berbasis `CanvasText` atau `forced-color-adjust`.
- **Solusi**: Jangan pernah mengatur `outline: none` tanpa secara eksplisit mendefinisikan pseudokelas `:focus-visible` menggunakan properti warna sistemik.
  ```css
  /* CORRECTION */
  .accessible-button:focus-visible {
    outline: 2px solid Transparent; /* Invisible in standard, automatically rendered in High Contrast Mode */
    box-shadow: 0 0 0 2px var(--color-outline-focus);
  }
  ```

---

### 11. Production Readiness Checklist & Audit Trail

Gunakan checklist arsitektur berikut sebelum mempromosikan artefak CSS ke lingkungan *Production*:

- [ ] **CSS Invalidation Boundaries**:
  - [ ] Apakah komponen data tabel besar telah dibatasi oleh `contain: layout style paint`?
  - [ ] Apakah tidak ada selektor universal berantai universal (`* > * > *`) yang merusak performa *Bloom Filter* engine?
- [ ] **Core Web Vitals Enforcement**:
  - [ ] Font lokal fallback memiliki `@font-face` dengan `ascent-override`, `descent-override`, dan `size-adjust` untuk CLS target $\le 0.05$.
  - [ ] Web fonts menggunakan deklarasi `font-display: optional` atau `font-display: swap` yang diimbangi metrik overrides.
  - [ ] Konten di bawah layar (*Below-the-fold*) menggunakan `content-visibility: auto` dan `contain-intrinsic-size`.
- [ ] **Compositing & VRAM Budget**:
  - [ ] Tidak ada aturan `will-change: transform` atau `translateZ(0)` yang dipasang secara statis pada elemen multi-instance.
  - [ ] Tidak ada animasi berbasis layout properties (`margin`, `top`, `left`, `width`, `height`); seluruh animasi visual hanya memanipulasi `transform` dan `opacity`.
- [ ] **A11y (WCAG 2.2 AAA)**:
  - [ ] Semua rasio kontras teks reguler memenuhi minimal rasio $7:1$ (atau APCA $L^c \ge 75$).
  - [ ] Media query `@media (prefers-reduced-motion: reduce)` diterapkan secara global untuk menetralkan transisi.
  - [ ] Sistem mendukung Windows High Contrast Mode melalui `@media (forced-colors: active)`.
- [ ] **Tooling & Build Quality**:
  - [ ] Critical CSS diekstrak dan ukuran *inlined string* di HTML $\le 14 \text{ KB}$ (agar muat dalam TCP Initial Congestion Window / IW10).
  - [ ] Stylelint terkonfigurasi pada CI/CD untuk memblokir properti yang memicu Layout Thrashing.
  - [ ] Visual regression test diset dengan toleransi threshold $\le 0.02\%$.

---

### 12. Hands-on Practice (Laboratorium Terpandu)

Simpan seluruh implementasi praktikum di dalam direktori `hands-on/m02/`.

#### Struktur Berkas Laboratorium
```
hands-on/m02/
├── package.json
├── playwright.config.ts
├── .stylelintrc.json
├── src/
│   ├── index.html
│   ├── styles/
│   │   ├── system.css
│   │   ├── metrics.css
│   │   └── components.css
│   └── scripts/
│       └── app.js
└── tests/
    ├── a11y.spec.ts
    └── visual-regression.spec.ts
```

#### Langkah 1: Inisialisasi Environment & Konfigurasi Linter
Buat berkas `hands-on/m02/package.json`:
```json
{
  "name": "enterprise-css-performance-lab",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "test:lint": "stylelint 'src/styles/**/*.css'",
    "test:e2e": "playwright test"
  },
  "devDependencies": {
    "@axe-core/playwright": "^4.8.2",
    "@playwright/test": "^1.40.1",
    "pixelmatch": "^5.3.0",
    "stylelint": "^16.1.0",
    "stylelint-config-standard": "^36.0.0"
  }
}
```

Buat konfigurasi Stylelint pembatas anti-pattern di `hands-on/m02/.stylelintrc.json`:
```json
{
  "extends": "stylelint-config-standard",
  "rules": {
    "property-disallowed-list": [
      "all",
      {
        "message": "Penggunaan property 'transition: all' dilarang karena merusak pipeline rendering."
      }
    ],
    "selector-max-universal": 1,
    "color-named": "never"
  }
}
```

#### Langkah 2: Bangun Core CSS Architecture
Buat berkas `hands-on/m02/src/styles/system.css`:
```css
:root {
  --color-bg-base: oklch(0.98 0 0);
  --color-text-high-contrast: oklch(0.12 0 0);
  --color-interactive-focus: oklch(0.35 0.25 264);
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-bg-base: oklch(0.1 0 0);
    --color-text-high-contrast: oklch(0.98 0 0);
    --color-interactive-focus: oklch(0.7 0.2 264);
  }
}

body {
  margin: 0;
  background-color: var(--color-bg-base);
  color: var(--color-text-high-contrast);
  font-family: 'Fallback-Font', system-ui, sans-serif;
}
```

Buat berkas `hands-on/m02/src/styles/components.css`:
```css
.feed-container {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 2rem;
  max-width: 800px;
  margin: 0 auto;
}

.enterprise-node {
  padding: 1.5rem;
  background-color: color-mix(in oklch, var(--color-bg-base) 80%, white);
  border: 1px solid oklch(0 0 0 / 0.15);
  border-radius: 4px;
  
  /* Critical Performance Declarations */
  content-visibility: auto;
  contain-intrinsic-size: auto 120px;
  contain: layout paint;
}

.interactive-control {
  padding: 0.75rem 1.5rem;
  background-color: transparent;
  color: var(--color-text-high-contrast);
  border: 2px solid var(--color-text-high-contrast);
  cursor: pointer;
}

.interactive-control:focus-visible {
  outline: 3px solid var(--color-interactive-focus);
  outline-offset: 4px;
}
```

#### Langkah 3: Setup Automated E2E Visual Regression & A11y Tests
Buat berkas `hands-on/m02/tests/a11y.spec.ts`:
```typescript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Enterprise CSS Verification', () => {
  test('Audit WCAG 2.2 AAA Contrast and Invalidation Standards', async ({ page }) => {
    await page.goto('http://localhost:3000');
    
    // Inject and execute axe-core
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('Visual Regression Snapshot Validation', async ({ page }) => {
    await page.goto('http://localhost:3000');
    
    // Validate that components adhere down to pixel baseline
    await expect(page).toHaveScreenshot('dashboard-visual-baseline.png', {
      maxDiffPixelRatio: 0.02,
      animations: 'disabled'
    });
  });
});
```

---

### 13. Tiered Practical Challenges

#### Easy Challenge: "Eliminate the Shift"
- **Tantangan**: Diberikan sebuah implementasi Typography yang memicu Layout Shift sebesar CLS: 0.18 ketika mengunduh font kustom 'Space Grotesk'.
- **Objektif**: Buat file CSS `@font-face` fallback menggunakan metrik overrides (`ascent-override`, `descent-override`, `size-adjust`) dengan font lokal `Arial` sehingga total CLS bernilai tepat $0.00$.

#### Medium Challenge: "High-Density Data Grid Containment"
- **Tantangan**: Diberikan DOM yang terdiri dari 5.000 baris order book finansial yang menerima event mutasi warna latar belakang tiap detik.
- **Objektif**: Konfigurasikan CSS containment (`contain`, Container Queries, dan `content-visibility`) sehingga browser melewati tahapan kalkulasi *paint* dan *layout* untuk data di luar viewport, mereduksi waktu eksekusi *Style Recalculation* di Chrome Performance Profiler hingga di bawah $4 \text{ ms}$.

#### Hard Challenge: "Zero-VRAM Compositing & A11y Theme Engine"
- **Tantangan**: Rancang sistem tema CSS enterprise yang mendukung mode Dynamic Dark/Light, High-Contrast OS fallback, dan Motion gating secara murni tanpa pustaka JavaScript pihak ketiga.
- **Objektif**:
  1. Buat color system berbasis `oklch()` dengan rasio kontras teruji $\ge 7:1$.
  2. Implementasikan hover & focus animations yang mempromosikan compositing layer *hanya* pada saat pointer terdeteksi (`@media (hover: hover)`), dan hapus promosinya segera setelah animasi idle.
  3. Buktikan pada Chrome DevTools Layers panel bahwa alokasi memori VRAM GPU tetap stabil pada baseline $< 50 \text{ MB}$ saat halaman digulir cepat.

---

### 14. Complex Production Capstone Scenario

Anda ditunjuk sebagai Principal CSS Architect untuk platform SaaS Logistik Global yang menangani pelacakan kontainer kapal secara real-time.

```
+-----------------------------------------------------------------------------+
| REQUIREMENTS SPECIFICATION: ENTERPRISE TELEMETRY CONSOLE                    |
+-----------------------------------------------------------------------------+
| 1. Skala DOM           : 25.000 concurrent nodes per viewport state.        |
| 2. Target Kinerja Web  : INP <= 50ms, LCP <= 1.2s, CLS == 0.000.            |
| 3. Aksesibilitas       : Sertifikasi WCAG 2.2 Level AAA (Strict Compliance).|
| 4. Hardware Range      : Diharuskan berjalan stabil pada ruggedized tablet   |
|                          dengan keterbatasan GPU VRAM (<= 1 GB shared).     |
| 5. Tooling Automation  : Full regression test gating pada GitHub Actions.   |
+-----------------------------------------------------------------------------+
```

**Tugas Arsitektural Anda:**
1. Rancang blueprint CSS Modules / Structure komprehensif yang mengisolasi render sub-tree secara total.
2. Tentukan kalkulasi formula numerik presisi untuk `contain-intrinsic-size` pada variasi kartu kargo yang bersifat responsif dinamis (kartu berubah tinggi antara desktop dan mobile).
3. Bangun rule-chain selektor yang sepenuhnya bebas dari regresi *Layout Thrashing*.
4. Rancang skema pengetesan otomatis menggunakan kombinasi Stylelint AST validation rules dan engine screenshot rendering untuk diintegrasikan pada Docker execution container.

---

### 15. Comprehensive Knowledge Evaluation

#### Section A: Basic Principles (5 Pertanyaan)
1. Apa peran *Key Selector* (selektor paling kanan) dalam algoritma pencocokan CSS Rule Hash Map pada Blink?
2. Mengapa properti `transform` dan `opacity` merupakan satu-satunya properti yang dapat dianimasikan tanpa memicu tahapan Layout atau Paint?
3. Sebutkan perbedaan fungsional antara `font-display: swap` dan `font-display: optional` ditinjau dari metrik CLS.
4. Apa fungsi atribut `contain-intrinsic-size` ketika dipasangkan dengan `content-visibility: auto`?
5. Mengapa penggunaan selektor universal `* { transition: all 0.2s; }` diklasifikasikan sebagai anti-pattern kritis pada aplikasi enterprise?

#### Section B: Intermediate Engineering (5 Pertanyaan)
6. Jelaskan secara mekanistik bagaimana *Synchronous Forced Layout* (*Layout Thrashing*) terjadi di level thread engine renderer ketika instruksi DOM Read dieksekusi tepat setelah DOM Write!
7. Bagaimana spesifikasi CSS Containment (`contain: layout paint style`) mencegah perambatan invalidasi layout (*layout invalidation bubble*) ke root DOM?
8. Bagaimana browser menangani rendering ketika media query `@media (forced-colors: active)` terpicu oleh sistem operasi pengguna?
9. Jelaskan risiko pemakaian `will-change: transform` yang dipasang secara permanen pada 2.000 baris tabel terhadap alokasi memori VRAM GPU!
10. Mengapa ruang warna `oklch()` lebih dipilih daripada `rgb()` atau `hsl()` dalam perancangan palette warna design token yang memenuhi standar kontras WCAG 2.2?

#### Section C: Advanced Production Case Scenarios (3 Skenario)

11. **Skenario Kasus 1**:
    Tim Anda meluncurkan rilis baru yang menyertakan font interaktif kustom. Setelah rilis, metrik Core Web Vitals menunjukkan degradasi CLS dari $0.01$ melonjak menjadi $0.28$ pada perangkat mobile, meskipun Anda telah menerapkan `font-display: swap`. Analisis di mana letak kegagalan mekanismenya dan bagaimana Anda memperbaikinya menggunakan metrik font overrides?

12. **Skenario Kasus 2**:
    Sebuah aplikasi *crypto-exchange* mengalami penurunan frame rate secara berkala dari 60 FPS ke 14 FPS setiap kali order book diperbarui via WebSocket. Profiling DevTools menunjukkan bahwa tahapan `Recalculate Style` memakan waktu 45ms per batch update. Tidak ada elemen DOM yang ditambah atau dihapus. Tunjukkan 2 kemungkinan akar permasalahan struktural pada CSS Anda dan rancang solusi perbaikannya!

13. **Skenario Kasus 3**:
    Pada sebuah aplikasi dashboard analitik medis, tim QA menemukan bahwa saat pengguna Windows mengaktifkan High Contrast Mode, seluruh status indikator critical error (yang awalnya berwarna merah pekat) berubah warnanya menjadi identik dengan teks default, menghilangkan penanda visual status error. Rancang arsitektur CSS yang mematuhi standar aksesibilitas OS tanpa merusak palet Forced-Colors!

---

### 16. Summary & Architectural Cheat-Sheet

```
                 ENTERPRISE CSS PERFORMANCE MATRIX
┌──────────────────────┬───────────────────────┬────────────────────────────┐
│ CSS Property         │ Rendering Phase Hit   │ Operational Impact         │
├──────────────────────┼───────────────────────┼────────────────────────────┤
│ width, height, top   │ Layout -> Paint ->    │ TERBURUK: Layout Thrashing │
│ margin, padding      │ Compositing           │ Pemicu Frame Drops & INP   │
├──────────────────────┼───────────────────────┼────────────────────────────┤
│ color, background,   │ Paint -> Compositing  │ SEDANG: Paint Invalidation │
│ box-shadow           │                       │ Beban CPU Raster Workers   │
├──────────────────────┼───────────────────────┼────────────────────────────┤
│ transform, opacity   │ Compositing ONLY      │ TERBAIK: Direct GPU Pass   │
│                      │                       │ Zero Reflow, Zero Repaint  │
└──────────────────────┴───────────────────────┴────────────────────────────┘
```

#### Aturan Baku Produksi (The Golden Rules)
1. **Isolasi Sub-tree Sejak Awal**:
   Bungkus modul, container, atau list views independen dengan `contain: layout paint style` atau manfaatkan `content-visibility: auto` untuk data di luar layer pandang.
2. **Kendalikan Compositor Budget**:
   Promosikan layer grafis GPU secara elastis dan transien. Jangan biarkan `will-change` aktif secara permanen pada elemen yang tidak sedang bergerak aktif.
3. **Patuhi Dimensi Font Metrik**:
   Nol-kan Cumulative Layout Shift (CLS) saat menggunakan Custom Font dengan memanfaatkan `ascent-override`, `descent-override`, dan `size-adjust` pada local fallback fonts.
4. **Validasi Kontras Persepsi**:
   Gunakan model warna `oklch()` untuk Token Aksesibilitas. Uji coba seluruh varian tema terhadap WCAG 2.2 AAA ($7:1$) dan selalu sertakan aturan protektif untuk `@media (forced-colors: active)`.
5. **Gating Mutasi Lewat CI/CD**:
   Gagalkan build pipeline jika Stylelint menemukan properti terlarang seperti `transition: all` atau jika Axe-core menemukan cacat aksesibilitas pada level automated visual testing.