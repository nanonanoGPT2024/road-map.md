# Kurikulum Rekayasa CSS Enterprise Modern

Selamat datang di kurikulum arsitektur CSS tingkat lanjut (*Advanced Enterprise CSS Architecture*). Program ini dirancang bukan sekadar untuk mengajarkan sintaks dasar penataan halaman web, melainkan untuk melatih pola pikir *browser engine rendering*, pemodelan tata letak deterministik, arsitektur token desain berlapis, serta optimasi performa skala enterprise tanpa kompromi.

---

## 1. Course Overview & Mindset

### Pergeseran Paradigma: CSS Sebagai Bahasa Pemrograman Deklaratif Mesin Rendering
CSS bukanlah alat rias antarmuka (*styling shortcut*), melainkan bahasa deklaratif berkinerja tinggi yang dieksekusi langsung oleh mesin rendering peramban (*Blink, Gecko, WebKit*). Menulis CSS untuk aplikasi enterprise menuntut pemahaman terhadap:
- **Biaya Pipeline Rendering**: Membedakan mutasi DOM yang memicu *Layout/Reflow*, *Repaint*, versus manipulasi non-blocking pada *Compositor Thread*.
- **Matematika Determinisme Cascade**: Menghilangkan dependensi terhadap `!important` dan *over-specificity* melalui kalkulasi spesifisitas formal, *Cascade Layers* (`@layer`), dan scoping eksplisit.
- **Isolasi Modul Komponen**: Menghapus kebocoran gaya (*global leak*) melalui struktur data Design Token multi-tier berbasis *CSS Custom Properties* dan *Container Queries*.
- **Aksesibilitas & Ketahanan Tampilan**: Memastikan antarmuka adaptif terhadap ragam *viewport*, perangkat input, kontras tinggi (*Windows Forced Colors Mode*), serta preferensi gerak (*prefers-reduced-motion*) pada tingkat standar WCAG 2.2 Level AAA.

---

## 2. Learning Roadmap

```text
ENGINEERING ROADMAP: ADVANCED ENTERPRISE CSS
│
├── BAB 01: CSS Engine Internals, Parsing, dan Cascade Mathematics
│   ├── 01. Browser Rendering Pipeline & CSSOM Construction
│   ├── 02. Specificity Calculation, Scoping, & Cascade Layers (@layer)
│   └── 03. Inheritance Mechanics, Explicit Defaults, & Keyword Semantics
│
├── BAB 02: Visual Formatting Model, Box Dynamics, & Paint Profiling
│   ├── 01. Margin Collapsing, BFC Formulation, & Overflow Clipping
│   ├── 02. Stacking Context, Paint Order, & Hardware Acceleration
│   └── 03. Sizing Constraints, Intrinsic Ratios, & Replaced Element Logic
│
├── BAB 03: Modern Flexbox Architecture & Flow Mechanics
│   ├── 01. Flex Container vs Item: Basis, Grow, & Shrink Distribution
│   ├── 02. Alignment Mechanics, Multi-Line Wrapping, & Dynamic Flow
│   └── 03. Flexbox Collision Patterns, Min-Size Traps, & Performance
│
├── BAB 04: Advanced CSS Grid Layouts & Subgrid Engineering
│   ├── 01. Two-Dimensional Track Sizing, fr Units, & Placement Algorithms
│   ├── 02. Named Grid Templates, Dense Packing, & Coordinate Mapping
│   └── 03. Subgrid Mechanics for Nested Cross-Component Alignment
│
├── BAB 05: Fluid Responsive Typography & Container Queries
│   ├── 01. Fluid Math with min(), max(), clamp(), & Dynamic Viewports (svh/dvh)
│   ├── 02. Container Queries: Size/Style Queries & Container Units (cqw/cqh)
│   └── 03. Component-Driven Responsive Patterns without Global Breakpoints
│
├── BAB 06: Design Tokens, Custom Properties Engine, & CSS Architecture
│   ├── 01. Dynamic Custom Properties Engine, Scope Trees, & Typed CSS
│   ├── 02. Multi-Tier Token Architectures: Primitive, Semantic, & Component
│   └── 03. Enterprise Scalability: Modern Zero-Runtime vs Utility vs Pure CSS
│
├── BAB 07: Compositor-Driven Animations, Motion Systems, & View Transitions
│   ├── 01. Kinetic Physics: Cubic-Bezier, Spring Math, & Keyframe Logic
│   ├── 02. View Transitions API: Cross-State Morphing & MPA/SPA Pipelines
│   └── 03. Native Scroll-Driven Animations (scroll() & view() Timelines)
│
├── BAB 08: Modern Color Spaces, Visual Shaders, & Advanced Math UI
│   ├── 01. Color Science: Gamut Mapping, Oklch, LCH, & Dynamic Color Mixing
│   ├── 02. Blend Modes, Advanced Backdrop Filters, & SVG Masking Pipelines
│   └── 03. CSS Trigonometry: Polar Coordinates, sin(), cos(), & Non-Linear UI
│
├── BAB 09: Enterprise Performance Optimization, Accessibility, & Tooling
│   ├── 01. Critical CSS Extraction, Invalidation Profiling, & Layout Thrashing
│   ├── 02. Strict WCAG 2.2 AA/AAA Audits, High-Contrast Modes, & Motion Safety
│   └── 03. Cross-Engine Normalization, CSS Nesting, PostCSS, & Modern Bundling
│
└── BAB 10: Capstone Project: Enterprise Design System & Mission-Critical Dashboard
    ├── 01. Architecture, Token Engine, & Base Layer Construction
    ├── 02. Complex Component Assembly, Subgrid Matrix, & State Mechanics
    └── 03. Performance Hardening, Motion Polish, & Multi-Platform Audit
```

---

## 3. Navigasi Detail Kurikulum

### [BAB 01: CSS Engine Internals, Parsing, dan Cascade Mathematics](./01-engine-internals-and-cascade/README.md)
Pelajari bagaimana byte stream HTML/CSS diproses oleh parser browser hingga menjadi struktur data CSSOM dan Render Tree, serta mekanisme deterministik dari algoritma Cascade.
- [Modul 01: Browser Rendering Pipeline: Parsing, CSSOM, Style Recalculation, dan Render Tree](./01-engine-internals-and-cascade/01-rendering-pipeline-and-cssom.md)
- [Modul 02: Specificity Mathematics, Cascade Layers (`@layer`), dan Order of Precedence](./01-engine-internals-and-cascade/02-specificity-and-cascade-layers.md)
- [Modul 03: Property Inheritance, Initial Values, dan Keyword Semantics (`revert`, `unset`, `initial`)](./01-engine-internals-and-cascade/03-inheritance-and-keyword-semantics.md)

### [BAB 02: Visual Formatting Model, Box Dynamics, dan Paint Profiling](./02-box-model-and-stacking-context/README.md)
Bongkar anatomi kalkulasi dimensional elemen pada browser, batasan Block Formatting Context (BFC), serta hierarki 3D rendering layar.
- [Modul 01: Block Formatting Contexts (BFC), Margin Collapse Rules, dan Overflow Boundaries](./02-box-model-and-stacking-context/01-bfc-and-margin-collapsing.md)
- [Modul 02: Stacking Contexts, Paint Order Specification, dan Hardware Compositing Acceleration](./02-box-model-and-stacking-context/02-stacking-contexts-and-compositing.md)
- [Modul 03: Sizing Algorithms: Intrinsic vs Extrinsic Sizing, Aspect-Ratio, dan Replaced Elements](./02-box-model-and-stacking-context/03-intrinsic-extrinsic-sizing.md)

### [BAB 03: Modern Flexbox Architecture dan Flow Mechanics](./03-flexbox-architecture/README.md)
Kuasai perilaku komputasi flex layout satu dimensi, algoritma distribusi ruang fleksibel, dan resolusi layout collission.
- [Modul 01: Flex Basis vs Width, Algoritma Distribusi `flex-grow` dan `flex-shrink`](./03-flexbox-architecture/01-flex-distribution-algorithms.md)
- [Modul 02: Axis Alignment, Cross-Axis Wrapping, dan Safe Space Management (`space-between` vs `gap`)](./03-flexbox-architecture/02-alignment-and-wrapping-mechanics.md)
- [Modul 03: Flexbox Anti-Patterns: Minimum Size Constriction (`min-width: 0`), Overflow Traps, dan Performa](./03-flexbox-architecture/03-anti-patterns-and-gotchas.md)

### [BAB 04: Advanced CSS Grid Layouts dan Subgrid Engineering](./04-grid-and-subgrid/README.md)
Bangun arsitektur tata letak dua dimensi yang presisi menggunakan modern grid placement algorithms hingga level nested subgrid.
- [Modul 01: Grid Track Sizing, Flexible Units (`fr`), Minmax Constraints, dan Auto-Placement Algorithm](./04-grid-and-subgrid/01-grid-track-sizing-and-placement.md)
- [Modul 02: Named Template Areas, Explicit Coordinate Matrix, dan Dense Packing Pattern](./04-grid-and-subgrid/02-named-areas-and-dense-packing.md)
- [Modul 03: CSS Subgrid (`subgrid`): Integrasi Sumbu Track Menembus Batasan Hirarki Komponen](./04-grid-and-subgrid/03-subgrid-deep-dive.md)

### [BAB 05: Fluid Responsive Typography dan Container Queries](./05-fluid-responsive-and-container-queries/README.md)
Tinggalkan ketergantungan kaku pada *viewport media queries* global dan terapkan pendekatan responsif modular berbasis ukuran kontainer.
- [Modul 01: Mathematical Fluid Typography & Spacing via `clamp()`, `min()`, `max()`, serta Dynamic Units (`dvh`, `lvh`, `svh`)](./05-fluid-responsive-and-container-queries/01-mathematical-fluid-units.md)
- [Modul 02: Container Queries: `@container` Sizing, Container Units (`cqw`, `cqh`), dan Style Query Primitives](./05-fluid-responsive-and-container-queries/02-container-queries-engine.md)
- [Modul 03: Adaptive Micro-Layouts: Arsitektur Komponen yang Swasembada Konteks Tata Letak](./05-fluid-responsive-and-container-queries/03-micro-layouts-patterns.md)

### [BAB 06: Design Tokens, Custom Properties Engine, dan CSS Architecture](./06-tokens-and-css-architecture/README.md)
Rancang fondasi sistem desain enterprise menggunakan variabel CSS dinamis berskala besar, tipifikasi runtime, dan metodologi arsitektur modern.
- [Modul 01: CSS Custom Properties Engine: Scope Cascading, Fallback Chains, dan Manipulasi CSSOM Runtime](./06-tokens-and-css-architecture/01-custom-properties-engine.md)
- [Modul 02: Multi-Tier Token Hierarchy: Primitive/Global, Semantic/Alias, dan Component Tokens](./06-tokens-and-css-architecture/02-multi-tier-token-architecture.md)
- [Modul 03: CSS Paradigms at Scale: BEM, OOCSS, CSS Modules, Utility Primitives, dan Modern Native Inclusions](./06-tokens-and-css-architecture/03-enterprise-css-methodologies.md)

### [BAB 07: Compositor-Driven Animations, Motion Systems, dan View Transitions](./07-animations-and-view-transitions/README.md)
Bangun sistem gerak antarmuka tingkat lanjut dengan frame rate konstan 60/120 FPS tanpa menyebabkan beban kalkulasi rendering CPU.
- [Modul 01: Kinetic Timing Functions, Bézier Curves, Orchestrated Animations, dan State-Driven Transitions](./07-animations-and-view-transitions/01-kinetics-and-bezier-orchestration.md)
- [Modul 02: View Transitions API: Transisi Keadaan Antarmuka yang Mulus untuk SPA dan MPA Tanpa JavaScript Berlebih](./07-animations-and-view-transitions/02-view-transitions-api.md)
- [Modul 03: Scroll-Driven Animations: Implementasi `@scroll-timeline`, `animation-timeline: view()` dan `scroll()`](./07-animations-and-view-transitions/03-scroll-driven-animations.md)

### [BAB 08: Modern Color Spaces, Visual Shaders, dan Advanced Math UI](./08-color-spaces-and-visual-shaders/README.md)
Eksplorasi representasi warna masa depan ber-gamut lebar, kalkulasi visual optik, dan manipulasi antarmuka non-linear dengan matematika trigonometri CSS.
- [Modul 01: Wide-Gamut Color Science: `oklch()`, `color-mix()`, P3 Display Gamuts, dan Dynamic Contrast Gamut Math](./08-color-spaces-and-visual-shaders/01-modern-color-science.md)
- [Modul 02: Compositing Effects: Advanced Blend Modes, Glassmorphism Backdrop-Filters, dan Vector Masking Systems](./08-color-spaces-and-visual-shaders/02-blend-modes-and-masking.md)
- [Modul 03: CSS Mathematical Functions: Kalkulasi Trigonometri (`sin()`, `cos()`, `atan2()`) untuk Complex Radial Layouts](./08-color-spaces-and-visual-shaders/03-trigonometric-css-layouts.md)

### [BAB 09: Enterprise Performance Optimization, Accessibility, dan Tooling](./09-performance-accessibility-and-tooling/README.md)
Uji dan matangkan stylesheet untuk mencapai efisiensi eksekusi jaringan optimal, kepatuhan legal standar disabilitas internasional, dan integrasi rantai build modern.
- [Modul 01: Rendering Performance: Layout Thrashing Elimination, `content-visibility`, dan Invalidation Triggers](./09-performance-accessibility-and-tooling/01-rendering-performance-profiling.md)
- [Modul 02: Deep Accessibility: Kontras WCAG 2.2 AAA, High-Contrast Adaptation (`forced-colors`), dan Reduced Motion Profiles](./09-performance-accessibility-and-tooling/02-strict-accessibility-compliance.md)
- [Modul 03: Engineering Toolchains: Native CSS Nesting, PostCSS Pipeline, Modern Minification, dan Linting Architecture](./09-performance-accessibility-and-tooling/03-tooling-and-cross-browser.md)

### [BAB 10: Capstone Project: Enterprise-Grade Design System & High-Performance Dashboard](./10-capstone-enterprise-design-system/README.md)
Puncak kurikulum di mana semua teori, matematika cascade, token arsitektur, dan performa diintegrasikan ke dalam implementasi dashboard berskala industri.
- [Modul 01: Capstone Specification & System Architecture: Core Token Framework and Baseline Setup](./10-capstone-enterprise-design-system/01-capstone-specs-and-tokens.md)
- [Modul 02: Core Library Components & Subgrid Financial Data-Matrix Implementation](./10-capstone-enterprise-design-system/02-components-and-subgrid-matrix.md)
- [Modul 03: Motion Integration, View Transitions, Multi-Theme Engine, dan Audit Final](./10-capstone-enterprise-design-system/03-motion-theming-and-audit.md)

---

## 4. Spesifikasi Capstone Project Enterprise

Proyek akhir ini mengharuskan Anda membangun sistem desain lengkap beserta aplikasi dasbor telemetri keuangan/infrastruktur misi kritis (*Mission-Critical Infrastructure & Financial Dashboard*) yang sepenuhnya ditulis dalam **Pure Modern CSS**.

```text
+-----------------------------------------------------------------------------------------------+
| TOPBAR: Realtime Status | OKLCH Palette Switcher | Contrast Toggle | View-Transition Engine   |
+-----------------------------------------------------------------------------------------------+
| NAV (Fluid) | MAIN DASHBOARD VIEWPORT (Subgrid Driven Matrix)                                 |
|             | +-----------------------------+ +---------------------------------------------+ |
| Prim. Token | | Financial Chart Panel       | | Multi-Tier Server Telemetry Grid            | |
| Sem. Token  | | (Scroll-Timeline / Shaders) | | (Container Queries: Resizes without Breakpt) | |
| Comp. Token | +-----------------------------+ +---------------------------------------------+ |
|             | +-----------------------------------------------------------------------------+ |
| Subgrid Nav | | Enterprise Data Table: Dynamic Sticky Header, Perfect Alignment via Subgrid | |
|             | +-----------------------------------------------------------------------------+ |
+-----------------------------------------------------------------------------------------------+
```

### Persyaratan Utama Arsitektur

1. **Arsitektur Token Berlapis (*Multi-Tier Custom Properties Engine*)**:
   - `Primitive Tokens`: Nilai mentah HSL/OKLCH, skala spasi geometrik, skala modular tipografi.
   - `Semantic Tokens`: Abstraksi tujuan (*surface-ground*, *text-contrast-high*, *interactive-focus*).
   - `Component Tokens`: Token scoped khusus untuk variasi komponen (*card-padding*, *data-grid-border*).
   - Dukungan tema instan (*Dark*, *Light*, *High Contrast*, dan *Cyberpunk Wide-Gamut P3*) murni menggunakan deklarasi token CSS tanpa manipulasi kelas komponen individual.

2. **Tata Letak Bebas Breakpoint Global (*Container-Query-Centric*)**:
   - Panel dashboard menyusun ulang layout-nya secara internal berbasis `@container (min-width: ...)` atau `@container (inline-size: ...)`.
   - Grid data analitik menggunakan CSS Subgrid (`subgrid`) untuk menjamin keselarasan (*vertical/horizontal alignment*) header kolom dengan sel data yang berada di kedalaman pohon DOM berbeda.

3. **Rendering & Compositing Zero-Jank**:
   - 0 layout recalculation loop selama scrolling.
   - Pemanfaatan `content-visibility: auto` dan `contain-intrinsic-size` pada viewport virtualized data table.
   - Seluruh animasi micro-interaction dieksekusi eksklusif pada GPU thread (`transform`, `opacity`, `clip-path`).

4. **Integrasi View Transitions & Scroll Animations**:
   - Navigasi antar-tab dashboard memanfaatkan browser-native `View Transitions API` dengan kustom pseudo-element styling (`::view-transition-old`, `::view-transition-new`).
   - Indikator progres data feed dan visualisasi telemetry terikat langsung dengan *Scroll-Driven Animations* (`animation-timeline: view()` / `scroll()`).

5. **Kepatuhan Aksesibilitas Ekstrem**:
   - Memenuhi kepatuhan WCAG 2.2 AAA untuk rasio kontras teks (minimal 7:1) di seluruh mode tema menggunakan ruang warna `oklch()`.
   - Adaptif terhadap media query: `@media (prefers-reduced-motion: reduce)`, `@media (forced-colors: active)`, dan `@media (prefers-color-scheme: dark)`.

### Kriteria Evaluasi Kelulusan
- **Performance Audit (Lighthouse)**: Nilai CSS Performance 100/100, tidak ada laporan *Render-blocking stylesheets*, CLS (Cumulative Layout Shift) = 0.
- **Cascade Cleanliness**: Bebas penggunaan `!important` (kecuali pada utility class override yang diisolasi di `@layer utility`). Penggunaan `@layer` secara ketat: `base`, `tokens`, `components`, `utilities`.
- **Zero Framework Dependency**: Bebas dari Tailwind, Bootstrap, Sass/SCSS, atau pustaka JavaScript runtime CSS-in-JS. Murni arsitektur modern web platform standards.