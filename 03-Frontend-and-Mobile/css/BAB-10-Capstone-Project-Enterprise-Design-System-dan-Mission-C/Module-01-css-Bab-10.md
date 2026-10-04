# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik:** css
*   **Bab:** 10 (Capstone Projects)
*   **Modul:** 01
*   **Judul:** Capstone Project: Enterprise Design System & Mission-Critical Dashboard
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** CSS Architecture (BEM, ITCSS, CUBE CSS), Modern Layouts (CSS Grid Level 2, Flexbox, Subgrid), CSS Custom Properties (Tokens, Dynamic Scoping), CSS Containment & Performance Optimization, Modern CSS Features (Cascade Layers `@layer`, Container Queries `@container`, Color Spaces `oklch`).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1.  **Merancang dan Mengimplementasikan Multi-Tier Design Tokens:** Mengembangkan pipeline token desain enterprise (Global, Semantic, Component) berbasis format standar JSON yang ditranspilasi ke CSS Custom Properties dengan dukungan multi-theming runtime (Light, Dark, High-Contrast) tanpa runtime JavaScript overhead.
2.  **Membangun Arsitektur CSS Skala Besar Menggunakan `@layer` dan ITCSS:** Mengontrol specificity cascade secara deterministik pada aplikasi mission-critical, mengeliminasi specificity war, dan menjamin isolasi style antara komponen inti dan konsumen dashboard.
3.  **Mengimplementasikan Fluid Responsive Layout Menggunakan CSS Subgrid dan Container Queries:** Merancang mission-critical dashboard layouts yang responsif terhadap dimensi kontainer independen tanpa coupling terhadap viewport global, serta mempertahankan alignment tabular kompleks antar-widget melalui `subgrid`.
4.  **Mengoptimalkan Rendering Pipeline Dashboard Real-Time:** Menerapkan strategi CSS containment (`contain`, `content-visibility`), compositing (`will-change`, GPU acceleration), dan isolasi reflow/repaint untuk mempertahankan render rate stabil pada 60/120 FPS di bawah beban injeksi ribuan data telemetry per detik.
5.  **Memenuhi Standar Aksesibilitas WCAG 2.2 Level AAA:** Mengintegrasikan CSS styling adaptif berbasis media queries (`prefers-contrast`, `prefers-reduced-motion`, `forced-colors`) dengan dynamic color calculations berbasis ruang warna modern `oklch`.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Mental Model: Utility-First / Ad-Hoc CSS ke Deterministic Architectural CSS Engine

Pada aplikasi skala kecil, CSS sering dipandang sebagai lapisan dekoratif visual yang ditulis secara ad-hoc atau mengandalkan utilitas generik. Pada level **Enterprise Mission-Critical Dashboard** (seperti sistem telemetri dirgantara, financial high-frequency trading terminal, atau command center infrastruktur cloud), CSS adalah **Execution Engine untuk User Interface** yang beroperasi langsung di atas thread rendering browser.

```
Pendekatan Ad-Hoc / Pemula:
Visual Design ---> Manual CSS Rules ---> High Specificity ---> Non-deterministic Override War

Mental Model Staff Engineer:
Design Tokens (Single Source of Truth)
      │
      ▼
Transpilation Pipeline (Style Dictionary)
      │
      ▼
Layered Cascade Engine (@layer) ──> Strict Specificity Budget
      │
      ▼
Isolated Compositor Nodes (containment, compositing, container queries)
      │
      ▼
Deterministic, 60fps Zero-Jank Rendering Under Telemetry Load
```

### Prinsip Utama Sistem Desain Mission-Critical:

1.  **Determinisme Cascade:** Tidak boleh ada selector yang bergantung pada urutan loading file (`<link>` sequence) atau specificity hack (`!important`, nesting tak terkontrol). Cascade diatur secara eksplisit menggunakan `@layer`.
2.  **Context-Aware Components (Container-Centric):** Komponen tidak boleh tahu di mana ia ditempatkan di layar. Komponen hanya merespons ukuran alokasi ruangnya sendiri via Container Queries (`@container`).
3.  **Reflow Containment Boundary:** Perubahan data pada widget berkecepatan tinggi (misalnya: ticker harga saham atau pembacaan sensor IoT) harus diisolasi secara mekanis di level browser engine agar tidak memicu recalculation tree visual di luar boundary widget tersebut.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur sistem dibangun di atas pipeline token terstruktur yang mengalir ke dalam struktur ITCSS (Inverted Triangle CSS) yang diikat oleh CSS Cascade Layers (`@layer`).

### 1. Diagram Alir Token dan CSS Architecture

```
[Design Tokens (JSON / W3C Specs)]
   │
   ├── Tier 1: Global Tokens (Primitive values: Palette, Base Spacing)
   │     └── e.g., --sys-color-palette-blue-500: oklch(0.55 0.22 255);
   │
   ├── Tier 2: Semantic Tokens (Intent-based: Background, Text, Interactive)
   │     └── e.g., --sys-color-surface-critical: var(--sys-color-palette-red-600);
   │
   └── Tier 3: Component Tokens (Scoped bindings)
         └── e.g., --cmp-metric-card-bg: var(--sys-color-surface-critical);
   │
   ▼
[Build System: Style Dictionary / CLI]
   │
   ▼
[Generated CSS: design-tokens.css]
   │
   ▼
======================= CASCADE LAYERS PIPELINE (@layer) =======================
┌─────────────────────────────────────────────────────────────────────────────┐
│ @layer reset       : CSS Normalization, Box-sizing, Base Layout Reset      │
├─────────────────────────────────────────────────────────────────────────────┤
│ @layer tokens      : CSS Custom Properties Injection (:root, [data-theme])  │
├─────────────────────────────────────────────────────────────────────────────┤
│ @layer base        : Typography primitives, Document-level elements         │
├─────────────────────────────────────────────────────────────────────────────┤
│ @layer layout      : Dashboard Shell, Grid Systems, Subgrid alignments      │
├─────────────────────────────────────────────────────────────────────────────┤
│ @layer components  : Card, Telemetry Table, Metric Display, Alerts          │
├─────────────────────────────────────────────────────────────────────────────┤
│ @layer utilities   : Atomic overrides (Visually Hidden, Explicit Modifiers) │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2. Diagram Alir Layout Dashboard Mission-Critical

```
+-------------------------------------------------------------------------------+
| Dashboard Viewport Shell (Grid System)                                        |
| +-------------------------+-------------------------------------------------+ |
| | Sidebar Navigation      | Metric Grid Header (Subgrid Aligned)            | |
| |                         | [ KPI Card 1 ] [ KPI Card 2 ] [ KPI Card 3 ]    | |
| |                         +-------------------------------------------------+ |
| |                         | Telemetry Data Stream Viewport                  | |
| |                         | +---------------------------------------------+ | |
| |                         | | Container Query Context (@container)        | | |
| |                         | | +-----------------------------------------+ | | |
| |                         | | | Widget: Sensor Graph (contain: layout)  | | | |
| |                         | | +-----------------------------------------+ | | |
| |                         | | | Widget: High-Freq Feed (contain: strict)| | | |
| |                         | | +-----------------------------------------+ | | |
| |                         | +---------------------------------------------+ | | |
+---------------------------+-------------------------------------------------+---+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Cascade Layers Ordering Semantics

Ketika `@layer reset, tokens, base, layout, components, utilities;` dideklarasikan di awal stylesheet, browser menyusun urutan prioritas cascade secara absolut:

$$\text{reset} < \text{tokens} < \text{base} < \text{layout} < \text{components} < \text{utilities}$$

*   **Pembedahan Internal:** Selector kelas sederhana `.metric-panel` di dalam `@layer utilities` akan **selalu mengalahkan** selector dengan specificity lebih tinggi seperti `div.shell aside.sidebar .metric-panel` yang berada di dalam `@layer components`.
*   **Keuntungan:** Mengeliminasi "Specificity Arm-Race" yang sering merusak pemeliharaan CSS enterprise.

### 2. Layout Boundary Engine: `subgrid` dan `@container`

*   **Subgrid:** Meneruskan trek lintasan `grid-template-columns` atau `grid-template-rows` dari elemen induk langsung ke elemen anak. Elemen anak tidak lagi mengkalkulasi grid-nya secara independen, melainkan berpartisipasi langsung dalam penentuan ukuran track parent. Ini krusial pada kartu metrik dashboard di mana label, grafik mini, dan value numerik harus sejajar horizontal lintas kolom yang berbeda.
*   **Container Queries (`container-type: inline-size`):** Memaksa browser menciptakan query context terisolasi pada dimensi horizontal. Browser memantau resize context elemen kontainer dan mengevaluasi `@container (min-width: ...)` tanpa perlu melakukan trigger global window resize handler.

### 3. DOM & Rendering Pipeline Optimization: CSS Containment

Browser render engine (Blink/Gecko/WebKit) mengeksekusi pipeline:

$$\text{Style Calculation} \longrightarrow \text{Layout (Reflow)} \longrightarrow \text{Paint (Repaint)} \longrightarrow \text{Composite}$$

*   `contain: strict;` (Kombinasi `size`, `layout`, `paint`, `style`):
    *   Memberi tahu layout engine bahwa dimensi elemen tidak bergantung pada anaknya, dan konten anak tidak bisa meluap (overflow) keluar dari boundary.
    *   Ketika data telemetri memperbarui konten teks di dalam widget ini, siklus **Layout** dibatasi hanya di dalam subtree kontainer tersebut. Browser **tidak menjalankan global document reflow**.
*   `content-visibility: auto;`:
    *   Elemen dashboard yang berada di luar viewport (misalnya log table di bawah fold) secara otomatis menghentikan proses rendering (layout & painting) anak-anaknya, menurunkan biaya rendering awal hingga $70\%$.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Ruang Warna Modern: Mengapa `oklch` Wajib untuk Mission-Critical Dashboard?

Ruang warna konvensional seperti sRGB (via `hex`, `rgb()`, `hsl()`) memiliki kelemahan fatal: **Non-uniformity of Perceived Lightness**. 

Dalam HSL, warna kuning murni (`hsl(60, 100%, 50%)`) dan warna biru murni (`hsl(240, 100%, 50%)`) memiliki nilai lightness parameter yang sama ($50\%$). Namun, retina manusia memproses warna kuning jauh lebih terang dibanding warna biru. Pada dashboard critical alert, inkonsistensi perseptual ini dapat menyebabkan kontras teks gagal terbaca di kondisi darurat.

Ruang warna **OKLCH** menyelesaikan masalah ini dengan formula perseptual:

$$\text{OKLCH} = f(L, C, H)$$

*   $L$ (Perceptual Lightness): $0.0$ (Hitam mutlak) hingga $1.0$ (Putih mutlak). Nilai $L=0.7$ menjamin luminansi persepsi yang identik secara visual di seluruh spektrum warna.
*   $C$ (Chroma): Kejenuhan warna dari $0$ (netral/grayscale) hingga batas gamut layar (P3, Rec.2020).
*   $H$ (Hue): Sudut spektrum warna dari $0^\circ$ hingga $360^\circ$.

Pada dashboard telemetry, kita dapat menurunkan semantic palette untuk alert state yang menjamin rasio kontras WCAG secara deterministik:

```css
/* Lightness dipertahankan pada 0.65 untuk seluruh alert tokens */
--sys-color-alert-success: oklch(0.65 0.22 142); /* Hijau */
--sys-color-alert-warning: oklch(0.65 0.22 85);  /* Kuning-Oranye */
--sys-color-alert-danger:  oklch(0.65 0.22 29);  /* Merah */
```

Karena nilai $L$ (Lightness) terkunci sama, teks kontras di atas latar belakang ini akan selalu memiliki rasio kontras visual yang terukur secara akurat.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental dari pondasi sistem desain dan layout core berbasis CSS modern murni tanpa ketergantungan pihak ketiga.

### Struktur File

```
├── tokens.css       # Token 3-Tier dengan oklch
├── architecture.css # Definisi @layer
├── layout.css       # Subgrid Dashboard Layout
└── components.css   # Container Queries & High-frequency Widget
```

#### File: `architecture.css`

```css
/* Mengunci prioritas cascade deterministik */
@layer reset, tokens, base, layout, components, utilities;

@layer reset {
  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  body {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.5;
  }
}
```

#### File: `tokens.css`

```css
@layer tokens {
  :root {
    /* Tier 1: Primitive Tokens */
    --primitive-color-slate-950: oklch(0.12 0.02 260);
    --primitive-color-slate-900: oklch(0.18 0.03 260);
    --primitive-color-slate-800: oklch(0.25 0.04 260);
    --primitive-color-slate-100: oklch(0.96 0.01 260);
    --primitive-color-emerald-500: oklch(0.69 0.17 155);
    --primitive-color-rose-500: oklch(0.63 0.24 25);
    
    --primitive-space-1: 0.25rem;
    --primitive-space-2: 0.5rem;
    --primitive-space-4: 1rem;
    --primitive-space-6: 1.5rem;

    /* Tier 2: Semantic Tokens (Default: Dark Theme for Ops Centers) */
    --semantic-surface-canvas: var(--primitive-color-slate-950);
    --semantic-surface-panel: var(--primitive-color-slate-900);
    --semantic-surface-panel-border: var(--primitive-color-slate-800);
    --semantic-text-primary: var(--primitive-color-slate-100);
    --semantic-status-nominal: var(--primitive-color-emerald-500);
    --semantic-status-critical: var(--primitive-color-rose-500);
  }

  /* Support High-Contrast Accessibility Mode */
  @media (prefers-contrast: more) {
    :root {
      --semantic-surface-panel-border: oklch(1 0 0);
      --semantic-surface-panel: oklch(0 0 0);
    }
  }
}
```

#### File: `layout.css`

```css
@layer layout {
  .dashboard-shell {
    display: grid;
    grid-template-columns: 240px 1fr;
    min-height: 100vh;
    background-color: var(--semantic-surface-canvas);
    color: var(--semantic-text-primary);
  }

  .dashboard-main {
    padding: var(--primitive-space-6);
    display: flex;
    flex-direction: column;
    gap: var(--primitive-space-6);
  }

  /* Subgrid KPI Alignment */
  .kpi-board {
    display: grid;
    grid-template-columns: repeat(3, minmax(200px, 1fr));
    gap: var(--primitive-space-4);
  }
}
```

#### File: `components.css`

```css
@layer components {
  /* KPI Component using Subgrid & Container Context */
  .kpi-card {
    /* Tier 3: Component Token Mapping */
    --kpi-border: var(--semantic-surface-panel-border);
    --kpi-bg: var(--semantic-surface-panel);

    /* Mengaktifkan Container Query Context */
    container-type: inline-size;
    container-name: kpi-card-context;

    background-color: var(--kpi-bg);
    border: 1px solid var(--kpi-border);
    border-radius: 8px;
    padding: var(--primitive-space-4);
    
    /* Strict Containment untuk Mengisolasi Perubahan Nilai Realtime */
    contain: layout paint;
  }

  .kpi-title {
    font-size: 0.875rem;
    opacity: 0.8;
  }

  .kpi-value {
    font-size: 1.75rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }

  /* Container Query: Beradaptasi secara lokal */
  @container kpi-card-context (max-width: 250px) {
    .kpi-value {
      font-size: 1.25rem;
    }
  }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Menelusuri keputusan teknik di balik kode di Seksi 07:

1.  `@layer reset, tokens, base, layout, components, utilities;`
    *   Mendefinisikan spesifikasi layer secara global di baris pertama. Ini mencegah browser dari dynamic ordering issues yang sering terjadi pada micro-frontend architecture saat komponen di-load secara asynchronous.
2.  `--primitive-color-slate-950: oklch(0.12 0.02 260);`
    *   Penggunaan ruang warna OKLCH memastikan representasi gamut warna yang luas dan luminansi yang stabil.
3.  `font-variant-numeric: tabular-nums;`
    *   **Krusial untuk Mission-Critical Dashboard:** Menginstruksikan font rendering engine untuk menggunakan monospaced glyphs untuk angka. Mencegah getaran layout (layout jitter/dancing numbers) ketika data telemetri berubah cepat dari angka tipis (seperti "1") ke angka lebar (seperti "8").
4.  `container-type: inline-size; container-name: kpi-card-context;`
    *   Mendefinisikan batas evaluasi Container Query pada dimensi horizontal. Browser mengisolasi reflow kalkulasi layout anak hanya terhadap lebar kontainer ini, mengeliminasi query global window resize.
5.  `contain: layout paint;`
    *   Menginstruksikan browser bahwa elemen anak tidak akan pernah merusak layout box di luar batas `.kpi-card` dan tidak ada rendering painting yang tumpah (clip default). Mengurangi cycle time Style Recalculation hingga tingkat mikrodetik.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: "AeroPulse Global Fleet Telemetry & Ops Command"

Anda ditugaskan sebagai Staff Frontend Engineer pada sistem telemetry satelit dan penerbangan komersial global. Dashboard ini menerima update metrik lebih dari 5.000 titik instrumen via WebSocket pada frekuensi **30Hz (30 update per detik)**.

#### Masalah Sistem Sebelumnya:
1.  **Drop Frame Kronis:** Browser sering mengalami freezing dan frame drop turun ke 12-15 FPS. Profiling Chrome DevTools menunjukkan $45\%$ dari CPU time dihabiskan pada fase **Layout** (Reflow) dan **Recalculate Style**.
2.  **Specificity Spaghetti:** Tim developer menggunakan UI component library pihak ketiga yang di-override menggunakan class `.card > div:nth-child(2) > span.highlight !important`. Setiap ada rilis baru, override patah.
3.  **Data Jittering:** Ticker telemetry membuat visual bergetar secara horizontal karena proporsionalitas lebar digit angka font variabel.
4.  **Kegagalan Regulasi Aksesibilitas FAA/Aviation:** Pada kondisi ruangan kokpit dengan cahaya silau tinggi, skema warna dashboard gagal memenuhi kontras minimum, berisiko tinggi terhadap salah baca data kritis altimeter dan status anomali mesin.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi lengkap untuk Mission-Critical Telemetry Dashboard Core, siap produksi, dengan zero runtime style overhead.

### HTML Structure (`index.html`)

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AeroPulse Mission-Critical Telemetry</title>
  <link rel="stylesheet" href="production-system.css">
</head>
<body>
  <div class="shell">
    <aside class="shell__sidebar">
      <div class="shell__brand">AEROPULSE // OPS</div>
      <nav class="nav-tree">
        <button class="nav-tree__item nav-tree__item--active">Fleet Telemetry</button>
        <button class="nav-tree__item">Propulsion Diagnostics</button>
        <button class="nav-tree__item">Orbital Matrix</button>
      </nav>
    </aside>

    <main class="shell__content">
      <!-- High-Density Telemetry Stream Header -->
      <section class="telemetry-grid">
        <!-- Subgrid Consumer Card 1 -->
        <article class="metric-widget metric-widget--status-nominal">
          <header class="metric-widget__header">
            <span class="metric-widget__label">SYS-01 // Core Altitude</span>
            <span class="metric-widget__indicator" aria-label="Status: Nominal"></span>
          </header>
          <div class="metric-widget__body">
            <span class="metric-widget__value">41,290.42</span>
            <span class="metric-widget__unit">FT</span>
          </div>
          <footer class="metric-widget__footer">
            <span class="metric-widget__delta metric-widget__delta--positive">+0.04% / SEC</span>
          </footer>
        </article>

        <!-- Subgrid Consumer Card 2 -->
        <article class="metric-widget metric-widget--status-critical">
          <header class="metric-widget__header">
            <span class="metric-widget__label">SYS-02 // Turbine Thermal Core</span>
            <span class="metric-widget__indicator" aria-label="Status: Critical"></span>
          </header>
          <div class="metric-widget__body">
            <span class="metric-widget__value">1,248.91</span>
            <span class="metric-widget__unit">°C</span>
          </div>
          <footer class="metric-widget__footer">
            <span class="metric-widget__delta metric-widget__delta--negative">+14.2% CRITICAL</span>
          </footer>
        </article>

        <!-- Subgrid Consumer Card 3 -->
        <article class="metric-widget metric-widget--status-nominal">
          <header class="metric-widget__header">
            <span class="metric-widget__label">SYS-03 // Comm Bus Signal</span>
            <span class="metric-widget__indicator" aria-label="Status: Nominal"></span>
          </header>
          <div class="metric-widget__body">
            <span class="metric-widget__value">-42.10</span>
            <span class="metric-widget__unit">dBm</span>
          </div>
          <footer class="metric-widget__footer">
            <span class="metric-widget__delta metric-widget__delta--positive">STABLE (99.9%)</span>
          </footer>
        </article>
      </section>

      <!-- Mission Data Stream Logs (Performance Isolated) -->
      <section class="stream-viewport">
        <div class="stream-panel">
          <div class="stream-panel__header">High-Frequency Telemetry Packet Intercept</div>
          <div class="stream-panel__data-feed" id="perf-telemetry-feed">
            <!-- Representasi baris terisolasi rendering -->
            <div class="feed-row"><span class="timestamp">12:00:01.042</span><span class="id">PKT-4091</span><span class="status">OK</span><span class="payload">PAYLOAD_ACK_SYNCED</span></div>
            <div class="feed-row"><span class="timestamp">12:00:01.074</span><span class="id">PKT-4092</span><span class="status status--warn">DEGRADE</span><span class="payload">PACKET_RETRY_ACK</span></div>
            <div class="feed-row"><span class="timestamp">12:00:01.106</span><span class="id">PKT-4093</span><span class="status">OK</span><span class="payload">PAYLOAD_ACK_SYNCED</span></div>
          </div>
        </div>
      </section>
    </main>
  </div>
</body>
</html>
```

### CSS Production Architecture (`production-system.css`)

```css
/* ==========================================================================
   CASCADE LAYERS DEFINITION (Deterministic specificity orchestration)
   ========================================================================== */
@layer framework.reset,
       framework.tokens,
       framework.base,
       framework.layout,
       framework.components,
       framework.utilities;

/* ==========================================================================
   RESET & SYSTEM BASELINE
   ========================================================================== */
@layer framework.reset {
  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  html, body {
    height: 100%;
    overflow: hidden; /* App-like Dashboard Shell */
  }

  body {
    background-color: var(--sys-color-bg-base);
    color: var(--sys-color-text-primary);
    font-family: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace;
    font-size: 13px;
    line-height: 1.4;
    text-rendering: optimizeLegibility;
    -webkit-font-smoothing: antialiased;
  }

  button {
    font: inherit;
    color: inherit;
    background: none;
    border: none;
    cursor: pointer;
  }
}

/* ==========================================================================
   DESIGN TOKENS (Multi-Tier Architecture with OKLCH)
   ========================================================================== */
@layer framework.tokens {
  :root {
    /* Tier 1: Primitives (Direct color definitions in OKLCH) */
    --primitive-neutral-950: oklch(0.12 0.01 260);
    --primitive-neutral-900: oklch(0.16 0.02 260);
    --primitive-neutral-850: oklch(0.20 0.02 260);
    --primitive-neutral-800: oklch(0.26 0.02 260);
    --primitive-neutral-400: oklch(0.60 0.02 260);
    --primitive-neutral-100: oklch(0.95 0.01 260);

    --primitive-emerald-500: oklch(0.72 0.19 150);
    --primitive-amber-500:   oklch(0.75 0.18 75);
    --primitive-rose-500:    oklch(0.65 0.24 25);

    /* Spacing primitives */
    --primitive-space-xs: 4px;
    --primitive-space-sm: 8px;
    --primitive-space-md: 16px;
    --primitive-space-lg: 24px;

    /* Tier 2: Semantic Intent */
    --sys-color-bg-base:        var(--primitive-neutral-950);
    --sys-color-surface-panel:  var(--primitive-neutral-900);
    --sys-color-surface-inset:  oklch(0.10 0.01 260);
    --sys-color-border-subtle:  var(--primitive-neutral-850);
    --sys-color-border-strong:  var(--primitive-neutral-800);

    --sys-color-text-primary:   var(--primitive-neutral-100);
    --sys-color-text-secondary: var(--primitive-neutral-400);

    --sys-color-status-nominal:  var(--primitive-emerald-500);
    --sys-color-status-warning:  var(--primitive-amber-500);
    --sys-color-status-critical: var(--primitive-rose-500);

    /* Animation Tokens */
    --sys-motion-duration-instant: 50ms;
    --sys-motion-easing-standard:  cubic-bezier(0.2, 0, 0, 1);
  }

  /* Accessibility Overrides: High-Contrast Mode Engine */
  @media (prefers-contrast: more) {
    :root {
      --sys-color-bg-base: oklch(0 0 0);
      --sys-color-surface-panel: oklch(0 0 0);
      --sys-color-border-subtle: oklch(1 0 0);
      --sys-color-border-strong: oklch(1 0 0);
      --sys-color-text-primary: oklch(1 0 0);
      --sys-color-text-secondary: oklch(0.9 0 0);
      --sys-color-status-nominal: oklch(0.8 0.3 140);
      --sys-color-status-critical: oklch(0.7 0.35 25);
    }
  }

  /* Accessibility Overrides: Reduced Motion Engine */
  @media (prefers-reduced-motion: reduce) {
    :root {
      --sys-motion-duration-instant: 0ms;
    }
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
}

/* ==========================================================================
   LAYOUT ARCHITECTURE (Mission-Critical Grid Shell & Subgrid Alignment)
   ========================================================================== */
@layer framework.layout {
  .shell {
    display: grid;
    grid-template-columns: 260px 1fr;
    height: 100vh;
    width: 100vw;
  }

  .shell__sidebar {
    background-color: var(--sys-color-surface-panel);
    border-right: 1px solid var(--sys-color-border-subtle);
    display: flex;
    flex-direction: column;
    padding: var(--primitive-space-md);
  }

  .shell__brand {
    font-weight: 700;
    letter-spacing: 0.1em;
    color: var(--sys-color-status-nominal);
    margin-bottom: var(--primitive-space-lg);
    border-left: 3px solid currentColor;
    padding-left: var(--primitive-space-sm);
  }

  .shell__content {
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: var(--primitive-space-lg);
    gap: var(--primitive-space-lg);
    background-color: var(--sys-color-bg-base);
  }

  /* Telemetry Master Grid - Defining Shared Row Tracks for Subgrid Consumption */
  .telemetry-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    /* Parent mengalokasikan 3 explicit rows per entitas widget: 
       Row 1: Header, Row 2: Value/Body, Row 3: Delta/Footer */
    grid-template-rows: auto auto auto;
    gap: var(--primitive-space-md);
  }
}

/* ==========================================================================
   COMPONENTS ARCHITECTURE (Subgrid, Container Queries & Containment)
   ========================================================================== */
@layer framework.components {
  /* Navigation Tree Component */
  .nav-tree {
    display: flex;
    flex-direction: column;
    gap: var(--primitive-space-xs);
  }

  .nav-tree__item {
    text-align: left;
    padding: var(--primitive-space-sm);
    border-radius: 4px;
    color: var(--sys-color-text-secondary);
    transition: background-color var(--sys-motion-duration-instant) var(--sys-motion-easing-standard),
                color var(--sys-motion-duration-instant) var(--sys-motion-easing-standard);
  }

  .nav-tree__item:hover {
    background-color: var(--sys-color-surface-inset);
    color: var(--sys-color-text-primary);
  }

  .nav-tree__item--active {
    background-color: var(--sys-color-border-subtle);
    color: var(--sys-color-text-primary);
    font-weight: bold;
  }

  /* Metric Widget (Subgrid Child & Container Query Context) */
  .metric-widget {
    /* Mengisi 3 baris dari grid induk, mengaktifkan subgrid */
    grid-row: span 3;
    display: grid;
    grid-template-rows: subgrid;

    background-color: var(--sys-color-surface-panel);
    border: 1px solid var(--sys-color-border-subtle);
    border-radius: 6px;
    padding: var(--primitive-space-md);
    
    /* Strict Containment Boundary: 
       Mengunci layout dan paint recalculation di dalam komponen ini */
    contain: layout paint;
    
    /* Container Query Context */
    container-type: inline-size;
    container-name: metric-panel;
    
    position: relative;
  }

  