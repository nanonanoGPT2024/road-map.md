# Aegis Enterprise Design System Engineering: Production-Grade Curriculum

Selamat datang di kurikulum **Design System Engineering**. Repositori ini berisi silabus komprehensif 10 bab yang dirancang untuk mentransformasi Frontend Engineer, UI/UX Engineer, dan Software Architect menjadi **Design System Specialist**.

Kurikulum ini mengadopsi standar industri terkini—mengintegrasikan fondasi matematika desain, arsitektur *design tokens*, *headless accessible primitives*, rekayasa *multi-brand/multi-platform engine*, otomatisasi CI/CD, hingga *governance* dan telemetri adopsi skala *enterprise*.

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
Design System bukan sekadar pustaka komponen (*component library*) atau *UI kit* di Figma; **Design System adalah produk infrastruktur perangkat lunak** yang melayani produk digital lain. Keberhasilannya diukur dari konsistensi UI, kecepatan rilis (*time-to-market*), penurunan regresi visual dan aksesibilitas, serta efisiensi kolaborasi lintas disiplin antara *Design*, *Engineering*, dan *Product*.

```
   ┌──────────────────────────────────────────────────────────────┐
   │                  Design Decisions (Figma)                    │
   └──────────────────────────────┬───────────────────────────────┘
                                  │ (Tokens Studio / Figma API)
                                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │         Design Tokens Pipeline (Style Dictionary)            │
   ├──────────────────────────────┬───────────────────────────────┤
   │ Transforms & Formats         │ OKLCH / APCA / Fluid Scales   │
   └──────────────┬───────────────┴───────────────┬───────────────┘
                  │                               │
                  ▼                               ▼
   ┌──────────────────────────────┐┌──────────────────────────────┐
   │   Web (CSS Variables / JS)   ││ Mobile (iOS Swift / Android) │
   └──────────────┬───────────────┘└──────────────────────────────┘
                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │      Headless Accessible Primitives (ARIA / State Machine)   │
   ├──────────────────────────────────────────────────────────────┤
   │      Enterprise Component Layer (React / Web Components)     │
   ├──────────────────────────────────────────────────────────────┤
   │      Documentation & Governance (Storybook / Changesets)     │
   └──────────────────────────────────────────────────────────────┘
```

### Mental Model & Core Paradigms
1. **Single Source of Truth (SSOT)**: Perubahan visual dan interaksi dikontrol melalui *Design Tokens* yang terikat pada kontrak semantik yang tidak bergantung pada platform (*platform-agnostic*).
2. **Separation of Concerns: Logic vs. Styling**: Memisahkan *behavior*, *state*, dan *accessibility* (Headless Primitives) dari lapisan presentasi visual (CSS Modules / Zero-runtime CSS-in-JS / Utility Tokens).
3. **Accessibility-First (A11y)**: Aksesibilitas (WCAG 2.2 AA/AAA) bukan fitur tambahan di akhir, melainkan prasyarat fundamental pada level primitif komponen.
4. **Strict Semantics & Resilient API**: API komponen dirancang menggunakan *strict TypeScript typing*, *composition over configuration*, dan *open-closed principle*.
5. **Infrastructure-Grade Quality**: Pengujian otomatis mencakup *Visual Regression Testing*, *Automated A11y Tree Audits*, *Unit Tests*, dan *Bundle Size Budgets*.

### Prasyarat Teknis
- Penguasaan mendalam atas Modern TypeScript (Generics, Conditional Types, Template Literal Types).
- Pemahaman solid mengenai arsitektur React (Hooks, Context, Composition, Polymorphic Components).
- Pemahaman dasar mengenai CSS modern (Custom Properties, Container Queries, Cascade Layers, Flexbox/Grid).
- Kemampuan mengoperasikan Node.js, monorepo tooling (PNPM / Turborepo), dan Git workflow.

---

## 2. Learning Roadmap

```
Aegis Design System Curriculum
│
├── [Bab 01] Foundations & Architecture of Modern Design Systems
│   ├── Modul 01: Taksonomi, Governance, dan Model Organisasi Design System
│   └── Modul 02: Audit Antarmuka, Tech Stack Evaluation, dan Tooling
│
├── [Bab 02] Design Tokens Architecture & Engineering
│   ├── Modul 01: Arsitektur Token: Global, Semantic, dan Component Scoped
│   ├── Modul 02: Style Dictionary Engine: Multi-Brand & Multi-Platform Pipeline
│   └── Modul 03: Integrasi Figma Tokens Studio & Automated Extraction API
│
├── [Bab 03] Typography, Spacing, and Spatial Grids
│   ├── Modul 01: Fluid Typography & Modular Scales Berbasis CSS Clamp
│   └── Modul 02: Spacing Scales, Dynamic Layout Grids, dan Elevation Systems
│
├── [Bab 04] Accessible Color Science & Contrast Engineering
│   ├── Modul 01: OKLCH Color Space & APCA (Advanced Perceptual Contrast Algorithm)
│   └── Modul 02: Dynamic Theming Engine: Light, Dark, dan High-Contrast Modes
│
├── [Bab 05] Component Primitives & Headless UI Architecture
│   ├── Modul 01: State Machines & Focus Trap pada Dialog/Modal Primitives
│   └── Modul 02: Floating UI, Popover, Tooltip, dan Compound Component Patterns
│
├── [Bab 06] Enterprise Component Implementation (React & Web Components)
│   ├── Modul 01: Polymorphic Components & Strict Typing Patterns
│   ├── Modul 02: Web Components (Lit) untuk Cross-Framework Interoperability
│   └── Modul 03: Styling Architecture: Zero-Runtime vs Pure Modern CSS
│
├── [Bab 07] Testing Strategies & Quality Engineering
│   ├── Modul 01: Visual Regression Testing dengan Playwright & Storybook
│   └── Modul 02: Automated Accessibility Audits (Axe-Core & Assistive Tree Testing)
│
├── [Bab 08] Documentation Engineering & Developer Experience (DX)
│   ├── Modul 01: Storybook 8 Deep Dive: CSF 3, MDX, dan Interaction Tests
│   └── Modul 02: Automated API Documentation Extraction & Interactive Sandboxes
│
├── [Bab 09] Packaging, Monorepo Infrastructure, & Versioning
│   ├── Modul 01: Monorepo Architecture dengan PNPM Workspaces & Turborepo
│   └── Modul 02: Semantic Versioning, Changesets Pipeline, dan AST Codemods
│
└── [Bab 10] Governance, Telemetry, and Scaling Across Organizations
    ├── Modul 01: Component Adoption Telemetry & AST-Based Static Analysis
    └── Modul 02: Contribution Framework, RFC Lifecycle, dan Multi-Tier Systems
```

---

## 3. Navigasi Detail Modul Silabus

### [Bab 01: Foundations & Architecture of Modern Design Systems](./bab-01-foundations-and-architecture/README.md)
Fondasi strategis, arsitektur tim, struktur tata kelola (*governance*), dan metodologi audit sistem UI legacy.
- [Modul 01: Taksonomi, Governance, dan Model Organisasi Design System](./bab-01-foundations-and-architecture/modul-01-taksonomi-governance.md)
  - Klasifikasi: Style Guide vs. Pattern Library vs. Design System.
  - Model Tata Kelola: *Centralized*, *Federated*, dan *Hybrid (Cyclical)*.
  - Mengukur Business Impact & ROI: Dev velocity, code deduplication, maintenance cost.
- [Modul 02: Audit Antarmuka, Tech Stack Evaluation, dan Tooling](./bab-01-foundations-and-architecture/modul-02-audit-dan-tooling.md)
  - Visual & Code Inventory: Memetakan inkonsistensi warna, tipografi, dan varian komponen.
  - Matrix Evaluasi Framework: Single-stack (React) vs Multi-stack (Lit/Web Components).
  - Setup Environment: Node.js runtime, Git flow, Linter, dan Prettier ruleset.

---

### [Bab 02: Design Tokens Architecture & Engineering](./bab-02-design-tokens-architecture/README.md)
Rekayasa *design tokens* sebagai SSOT platform-agnostik dengan transformasi multi-target.
- [Modul 01: Arsitektur Token: Global, Semantic, dan Component Scoped](./bab-02-design-tokens-architecture/modul-01-arsitektur-token.md)
  - Hierarki 3-Tier: Core (Global) -> Semantic (Systemic) -> Component (Scoped).
  - Format spesifikasi W3C Design Tokens Community Group (DTCG).
  - Naming conventions: BEM-adjacent token naming strategies.
- [Modul 02: Style Dictionary Engine: Multi-Brand & Multi-Platform Pipeline](./bab-02-design-tokens-architecture/modul-02-style-dictionary-engine.md)
  - Setup Style Dictionary v4: Transforms, Formats, dan Actions kustom.
  - Kompilasi target: CSS Custom Properties, SCSS, JSON, iOS Swift, dan Android Compose/XML.
  - Multi-brand pipeline: Theming overrides menggunakan dynamic dictionary merges.
- [Modul 03: Integrasi Figma Tokens Studio & Automated Extraction API](./bab-02-design-tokens-architecture/modul-03-figma-api-sync.md)
  - Sync Figma Tokens Studio via GitHub Actions Webhook.
  - Figma REST API: Mengonversi Variable Collections menjadi file token format JSON.
  - Validasi skema token menggunakan Zod dan JSON Schema.

---

### [Bab 03: Typography, Spacing, and Spatial Grids](./bab-03-typography-spacing-grid/README.md)
Prinsip matematika visual untuk hierarki spasial dan tipografi yang responsif.
- [Modul 01: Fluid Typography & Modular Scales Berbasis CSS Clamp](./bab-03-typography-spacing-grid/modul-01-fluid-typography.md)
  - Teori Modular Scale: Rasio Golden, Major Third, dan Perfect Fourth.
  - Rumus matematis `clamp(min, preferred, max)` untuk tipografi fluid tanpa breakpoint berlebih.
  - Penanganan Web Font: FOUT/FOIT optimization, font-display, dan variable fonts.
- [Modul 02: Spacing Scales, Dynamic Layout Grids, dan Elevation Systems](./bab-03-typography-spacing-grid/modul-02-spacing-grid-elevation.md)
  - 4pt / 8pt Base Grid Logic: Standarisasi paddings, margins, dan line-height.
  - Micro/Macro layout: Sistem container responsif dengan CSS Subgrid dan Container Queries.
  - Elevation & Stacking Context: Manajemen z-index terstruktur dan ambient/direct shadow system.

---

### [Bab 04: Accessible Color Science & Contrast Engineering](./bab-04-accessible-color-science/README.md)
Implementasi ruang warna perseptual modern, kalkulasi kontras, dan dark mode yang dinamis.
- [Modul 01: OKLCH Color Space & APCA (Advanced Perceptual Contrast Algorithm)](./bab-04-accessible-color-science/modul-01-oklch-apca.md)
  - Mengapa sRGB & HSL gagal: Masalah persepsi uniformitas luminansi manusia.
  - Generasi palet warna presisi menggunakan ruang warna `oklch()`.
  - Transisi dari WCAG 2.1 Contrast Ratio ke APCA (WCAG 3.0 draft standard).
- [Modul 02: Dynamic Theming Engine: Light, Dark, dan High-Contrast Modes](./bab-04-accessible-color-science/modul-02-dynamic-theming-engine.md)
  - Semantic Color Mapping: Background, Surface, Border, Foreground, dan State colors.
  - Dark mode inversi: Surface elevation berbasis lightness mapping bukan pure black `#000000`.
  - Aksesibilitas OS: `prefers-color-scheme` dan `prefers-contrast` media queries.

---

### [Bab 05: Component Primitives & Headless UI Architecture](./bab-05-component-primitives-headless/README.md)
Rekayasa logika interaksi kompleks, state management, dan pemenuhan standar ARIA.
- [Modul 01: State Machines & Focus Trap pada Dialog/Modal Primitives](./bab-05-component-primitives-headless/modul-01-state-machine-modal.md)
  - State modeling menggunakan finite state machine (FSM) atau reducer murni.
  - Focus Management: Focus Trap, Return Focus, Initial Focus, dan Inert Layering.
  - WAI-ARIA Dialog (Modal) Design Pattern & Keyboard Navigation (`Escape`, `Tab`).
- [Modul 02: Floating UI, Popover, Tooltip, dan Compound Component Patterns](./bab-05-component-primitives-headless/modul-02-floating-ui-compound.md)
  - Positioning engine: Collision detection, virtual elements, dan flip logic via `@floating-ui/dom`.
  - Compound Components Pattern: Injeksi context implisit antar sub-komponen.
  - WAI-ARIA Tooltip vs Popover vs Disclosure: Semantik dan keyboard accessibility.

---

### [Bab 06: Enterprise Component Implementation (React & Web Components)](./bab-06-enterprise-component-implementation/README.md)
Pengembangan komponen produksi berkinerja tinggi, kompatibel lintas framework, dan type-safe.
- [Modul 01: Polymorphic Components & Strict Typing Patterns](./bab-06-enterprise-component-implementation/modul-01-polymorphic-components.md)
  - Implementasi prop `as` / `asChild` (Radix pattern) dengan TypeScript inferensi tingkat lanjut.
  - Menghindari typing hell: Merging custom props dengan HTML native attributes.
  - Handling ForwardRef dan ref typing yang robust pada polymorphic interface.
- [Modul 02: Web Components (Lit) untuk Cross-Framework Interoperability](./bab-06-enterprise-component-implementation/modul-02-web-components-lit.md)
  - Konsep Custom Elements, Shadow DOM, dan Slot projection.
  - Membungkus komponen Lit ke React wrapper (@lit/react) dan Angular/Vue bindings.
  - Styling di dalam Shadow DOM: CSS Custom Properties & `::part` pseudo-element.
- [Modul 03: Styling Architecture: Zero-Runtime vs Pure Modern CSS](./bab-06-enterprise-component-implementation/modul-03-styling-architecture.md)
  - Analisis mendalam: Pure CSS Modules + `@layer` vs Tailwind vs Zero-runtime (Vanilla Extract/Panda CSS).
  - Isolasi CSS Cascade: `@layer reset, tokens, components, overrides;`.
  - Optimasi bundle: Tree-shaking CSS dan eliminasi runtime styling overhead.

---

### [Bab 07: Testing Strategies & Quality Engineering](./bab-07-testing-and-quality/README.md)
Strategi otomasi pengujian untuk mencegah regresi visual, fungsional, dan aksesibilitas.
- [Modul 01: Visual Regression Testing dengan Playwright & Storybook](./bab-07-testing-and-quality/modul-01-visual-regression.md)
  - Arsitektur snapshot pixel-level: Storybook Test-Runner vs Playwright Visual Comparisons.
  - Menghilangkan *flaky tests*: Handling web fonts loading, animations, dan dynamic dates.
  - Pengujian multi-viewport, multi-theme, dan cross-browser rendering (Chromium, Firefox, WebKit).
- [Modul 02: Automated Accessibility Audits (Axe-Core & Assistive Tree Testing)](./bab-07-testing-and-quality/modul-02-accessibility-audits.md)
  - Integrasi `@axe-core/playwright` pada pipeline visual test.
  - Assertion terhadap Accessible Name Computation dan Roles di Accessibility Tree.
  - Keyboard-only navigation end-to-end integration tests.

---

### [Bab 08: Documentation Engineering & Developer Experience (DX)](./bab-08-documentation-and-dx/README.md)
Membangun platform dokumentasi interaktif yang selalu tersinkronisasi dengan kode sumber.
- [Modul 01: Storybook 8 Deep Dive: CSF 3, MDX, dan Interaction Tests](./bab-08-documentation-and-dx/modul-01-storybook-deep-dive.md)
  - Component Story Format (CSF 3) best practices: Args, Parameters, dan Decorators.
  - Interaksi otomatis menggunakan `play` function dan `@storybook/test` (Vitest engine).
  - Desain MDX untuk Guideline & Usage Do's and Don'ts visual matrix.
- [Modul 02: Automated API Documentation Extraction & Interactive Sandboxes](./bab-08-documentation-and-dx/modul-02-api-docs-sandboxes.md)
  - Ekstraksi metadata TypeScript via `react-docgen-typescript` untuk auto-props table.
  - Integrasi Live Code Playground (Sandpack / React-Live) di dalam dokumentasi.
  - Automated Design Tokens Inspector: Dokumentasi token yang terupdate otomatis saat build.

---

### [Bab 09: Packaging, Monorepo Infrastructure, & Versioning](./bab-09-packaging-monorepo-versioning/README.md)
Infrastruktur pengemasan, distribusi package, dan manajemen dependensi enterprise.
- [Modul 01: Monorepo Architecture dengan PNPM Workspaces & Turborepo](./bab-09-packaging-monorepo-versioning/modul-01-monorepo-turborepo.md)
  - Struktur workspace: `apps/docs`, `packages/tokens`, `packages/primitives`, `packages/react`, `packages/css`.
  - Pipeline cache optimization pada Turborepo: Hashing input/output build.
  - Bundling multi-format (ESM & CJS) menggunakan `tsup` dengan full declaration maps (`.d.ts`).
- [Modul 02: Semantic Versioning, Changesets Pipeline, dan AST Codemods](./bab-09-packaging-monorepo-versioning/modul-02-changesets-codemods.md)
  - Version management otomatis menggunakan `@changesets/cli`.
  - Otomatisasi rilis npm dan GitHub Releases melalui GitHub Actions.
  - Pembuatan jscodeshift codemods untuk migrasi otomatis *breaking changes* pada konsumen.

---

### [Bab 10: Governance, Telemetry, and Scaling Across Organizations](./bab-10-governance-telemetry-scaling/README.md)
Metrik adopsi sistem, siklus hidup depresiasi komponen, dan strategi penskalaan organisasi.
- [Modul 01: Component Adoption Telemetry & AST-Based Static Analysis](./bab-10-governance-telemetry-scaling/modul-01-component-telemetry.md)
  - Membuat CLI scanner berbasis TypeScript Compiler API untuk memindai repo konsumen.
  - Menghitung rasio adopsi: Penggunaan komponen resmi vs elemen raw HTML (`<button>` vs `<AegisButton>`).
  - Dashboard metriks: Visualisasi data adopsi sistem dan status versi dependency konsumen.
- [Modul 02: Contribution Framework, RFC Lifecycle, dan Multi-Tier Systems](./bab-10-governance-telemetry-scaling/modul-02-rfc-contribution-scaling.md)
  - Proses RFC (Request for Comments) untuk penambahan atau modifikasi komponen.
  - Multi-tier system architecture: Core DS -> Domain DS -> Application Level.
  - SLA Support, deprecation lifecycle, dan semantic lifecycle statuses (Alpha, Beta, Stable, Deprecated).

---

## 4. Spesifikasi Capstone Project Enterprise

### Nama Proyek: **Aegis Enterprise Design System**
Siswa diwajibkan membangun dan merilis Design System *enterprise-ready* dengan arsitektur multi-brand, multi-platform, dan fully-automated pipeline dari token hingga distribusi package.

### Arsitektur Repositori (Monorepo)
```
aegis-design-system/
├── .github/
│   └── workflows/
│       ├── tokens-sync.yml       # Figma tokens pipeline
│       ├── test-and-audit.yml    # Lint, A11y, Playwright visual tests
│       └── release.yml           # Changesets automated publish
├── packages/
│   ├── tokens/                   # Style Dictionary input/output (JSON, CSS, JS/TS)
│   ├── primitives/               # Headless accessible component logic
│   ├── react/                    # Aegis React Component Library
│   ├── web-components/           # Lit-based universal custom elements
│   └── codemods/                 # Migration scripts (jscodeshift)
├── apps/
│   ├── docs/                     # Storybook 8 & Docs portal
│   └── telemetry-dashboard/      # Static report generator for DS adoption
├── turbo.json
├── pnpm-workspace.yaml
└── package.json
```

### Kriteria Minimum Penerimaan (Acceptance Criteria)

1. **Tokens Pipeline (W3C Standard)**:
   - File JSON token global, semantik, dan komponen.
   - Script kompilasi Style Dictionary menghasilkan:
     - `css/tokens.css` (berisi CSS Variables dengan fallback).
     - `es/tokens.ts` (Typed tokens untuk runtime JS).
     - Variasi token untuk minimal 2 Brand (misal: *Aegis FinTech* dan *Aegis Healthcare*) serta 2 Mode (*Light* dan *Dark*).
   - Penggunaan ruang warna OKLCH dan pengecekan kontras APCA / WCAG 2.2 AA otomatis saat token di-generate.

2. **Core Components (Minimal 5 Komponen Produksi Komprehensif)**:
   - **Button**: Mendukung polymorphic `asChild`, multiple variants, states (loading, disabled, focused), icon injection.
   - **Input / FormField**: Floating label atau stacked, visual validation state (error, success), error message yang terikat secara semantik via `aria-describedby`.
   - **Modal / Dialog**: Implementasi headless focus trapping, portal rendering, backdrop blur, keyboard trap escape, dan restore focus saat tertutup.
   - **DataTable / DataGrid**: Virtualized rendering untuk performa, accessible row selection, sorting indicators yang terbaca screen-reader.
   - **Select / Dropdown (Custom)**: Menggunakan Popover + Listbox WAI-ARIA pattern, floating positioning dengan auto-flip logic.

3. **Accessibility & Quality Engineering (Strict Standards)**:
   - 100% kelulusan Axe-core linting tanpa violation `critical` atau `serious`.
   - Visual regression snapshot tests dengan Playwright untuk semua variasi tema & viewport.
   - Interaksi keyboard lengkap diuji via Storybook play functions.

4. **Distribution & Packaging**:
   - Monorepo terkelola via PNPM Workspaces dan dioptimasi oleh Turborepo cache.
   - Pengemasan dual-format (CJS + ESM) dengan source maps dan zero unused declarations.
   - Otomatisasi rilis menggunakan Changesets yang menaikkan versi sesuai SemVer dan menghasilkan `CHANGELOG.md` otomatis.

5. **Telemetry & Codemod**:
   - Memiliki minimal satu npx script: `npx @aegis-ds/scanner` untuk memindai codebase lokal dan melaporkan persentase adopsi komponen Aegis.
   - Memiliki script codemod untuk memigrasikan prop deprecated secara otomatis (misal: `variant="danger"` menjadi `variant="critical"`).

---

## Memulai Kurikulum
Untuk memulai, lanjutkan ke [Bab 01: Foundations & Architecture of Modern Design Systems](./bab-01-foundations-and-architecture/README.md) dan baca [Modul 01: Taksonomi, Governance, dan Model Organisasi](./bab-01-foundations-and-architecture/modul-01-taksonomi-governance.md).