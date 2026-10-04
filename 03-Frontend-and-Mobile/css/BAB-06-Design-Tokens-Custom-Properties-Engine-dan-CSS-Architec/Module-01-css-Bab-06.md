# Kurikulum: CSS Skala Enterprise (03-Frontend-and-Mobile)
## Bab 06: Arsitektur Skala Besar, Desain Sistem, & Metodologi
### Modul 01: Design Tokens, Custom Properties Engine, & CSS Architecture

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran:** 03-Frontend-and-Mobile
* **Mata Pelajaran:** Arsitektur CSS Lanjutan & Fondasi Sistem Desain
* **Modul:** Bab 06 Module 01 — *Design Tokens, Custom Properties Engine, & CSS Architecture*
* **Tingkat Kesulitan:** Advanced / Staff Engineer
* **Prasyarat Pengetahuan:**
  * Penguasaan CSS Cascading, Specificity, dan Inheritansi Level 4.
  * Pemahaman mendalam tentang siklus hidup parsing CSS dan rendering pipeline (Recalculate Style, Layout, Paint, Composite).
  * Pengalaman operasional dengan sintaks dasar CSS Custom Properties (`var(--*)`) dan preprocessor (Sass/PostCSS).
  * Dasar automasi kompilasi modul JavaScript/Node.js (ekosistem npm, token transformers).
* **Alokasi Waktu Teori & Praktik:** 6 Jam Belajar Mandiri + 8 Jam Implementasi Laboratorium Produksi.

---

## SEKSI 02 — LEARNING OBJECTIVES

1. **Mengevaluasi & Merekayasa Graph Design Token Tiered:** Mengabstraksikan bahasa desain visual multi-platform ke dalam sistem 3-tier (*Global/Primitive*, *Semantic/Alias*, dan *Component-scoped*) menggunakan spesifikasi W3C Design Tokens Community Group (DTCG).
2. **Membangun Runtime Theme Engine Native:** Mengimplementasikan mesin switching tema (Light, Dark, High-Contrast) bebas *flash of unstyled content* (FOUC) dengan CSS Custom Properties murni tanpa runtime JavaScript overhead untuk manipulasi stylesheet.
3. **Menguasai Runtime Houdini Typed OM API:** Mengisolasi dan mendaftarkan CSS Custom Properties via `@property` dan CSS Typed Object Model (Typed OM) untuk kontrol inheritansi, validasi tipe ketat, *initial-value fallback*, serta transisi/animasi properti kustom yang mulus.
4. **Menerapkan Metodologi Arsitektur CSS Termutakhir:** Mengintegrasikan `@layer` (CSS Cascade Layers) bersama metodologi BEM/CUBE CSS untuk menyelesaikan konflik spesifisitas secara definitif dalam skala monorepo/micro-frontend.
5. **Mengoptimalkan Kinerja Engine Rendering:** Mengurangi *Style Recalculation Blast Radius* hingga < 16ms (60-120fps budget) dengan menavigasi batas-batas pewarisan (*inheritance boundary*) dan mitigasi layout thrashing pada token dinamis.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam skala enterprise, CSS bukan sekadar lembar gaya presentasional; **CSS adalah runtime dependency injection graph berbasis hierarki pohon DOM**. 

### 1. Pergeseran Paradigma: Preprocessor Variable vs. CSS Custom Property

```
[Statik / Preprocessor (Sass/Less)]
Code Time: $primary: #0055FF; ===(Compile)===> CSS Output: color: #0055FF;
* Nilai mati (inlined pada build-time).
* Tidak sadar konteks DOM tree.
* Tidak mendukung re-theming tanpa kompilasi ulang seluruh stylesheet.

[Dinamis / Native Custom Properties]
Runtime: --color-primary: #0055FF;
* Nilai hidup (resolved pada runtime oleh style engine browser).
* Sadar konteks cascading dan scope DOM.
* Merespons instan terhadap mutasi atribut DOM, media queries, dan kontainer kontras.
```

### 2. Mental Model: The Directed Acyclic Graph (DAG) of Tokens

Lihat variabel CSS sebagai node dalam sebuah *Directed Acyclic Graph* (DAG).
* **Primitive Layer (Root):** Nilai atomik mutlak (`#0B0F19`, `16px`, `Inter`). Node ini tidak boleh dikonsumsi langsung oleh komponen antarmuka pengguna.
* **Semantic Layer (Resolver):** Menghubungkan primitif ke dalam intensi bisnis (`--bg-surface-default: var(--primitive-color-neutral-100)`). Layer ini bermutasi secara kondisional berdasarkan *mode* atau *tema*.
* **Component Layer (Consumer & API Hook):** Mengekspos antarmuka publik komponen (`--btn-bg: var(--bg-surface-default)`). Komponen hanya membaca token komponennya sendiri, membebaskan komponen dari dependensi langsung ke tema global.

```
       [Primitive Token Engine]   <-- Statik, tidak sadar tema (Penyedia Nilai Dasar)
                  │
                  ▼
       [Semantic Token Engine]    <-- Dinamis, responsif terhadap Tema / Media Context
                  │
                  ▼
      [Component Property Engine] <-- Scope lokal, terisolasi secara struktural
                  │
                  ▼
     [Computed Value pada Elemen] <-- Layout & Paint Rendering
```

Jika komponen Anda membaca `--primitive-color-blue-500` secara langsung, Anda menciptakan coupling monolitik yang merusak kemampuan multi-theming modular.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah representasi end-to-end arsitektur sistem token desain dari fase desainer (Figma) hingga konsumsi pada browser runtime menggunakan Cascade Layers (`@layer`) dan pendaftaran `@property`.

```
+---------------------------------------------------------------------------------------------------------+
|                                    FASE DEFINISI & BUILD SYSTEM                                         |
+---------------------------------------------------------------------------------------------------------+
|  Figma / Tokens Studio (JSON DTCG Format)                                                                |
|  └── Primitive: { "color": { "blue": { "500": { "$value": "#3B82F6", "$type": "color" } } } }           |
|  └── Semantic:  { "surface": { "action": { "$value": "{color.blue.500}", "$type": "color" } } }        |
+---------------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------------+
|  Token Transformer Pipeline (Style Dictionary / Custom AST Tooling)                                     |
|  ├── Validasi Skema & Tipe Data                                                                        |
|  ├── Resolusi Referensi Silang (Aliasing)                                                              |
|  └── Emit: CSS Variables, TypeScript Types, JSON Metadata                                                |
+---------------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+---------------------------------------------------------------------------------------------------------+
|                                  FASE RUNTIME BROWSER RENDERING                                         |
+---------------------------------------------------------------------------------------------------------+
|                                                                                                         |
|  1. REGISTRASI HOUDINI ENGINE (Typed OM via CSS @property)                                               |
|     +---------------------------------------------------------------------------------------------+     |
|     | @property --sys-surface-primary {                                                           |     |
|     |   syntax: '<color>'; inherits: true; initial-value: #ffffff;                                |     |
|     | }                                                                                           |     |
|     +---------------------------------------------------------------------------------------------+     |
|                                                  │                                                      |
|                                                  ▼                                                      |
|  2. HIERARKI KASKADE (@layer Orchestration)                                                             |
|     +---------------------------------------------------------------------------------------------+     |
|     | @layer tokens.primitive {                                                                   |     |
|     |   :root { --pr-blue-500: #3b82f6; --pr-slate-900: #0f172a; }                                |     |
|     | }                                                                                           |     |
|     | @layer tokens.semantic {                                                                    |     |
|     |   :root, [data-theme="light"] { --sys-surface-bg: var(--pr-blue-500); }                     |     |
|     |   [data-theme="dark"]         { --sys-surface-bg: var(--pr-slate-900); }                    |     |
|     | }                                                                                           |     |
|     | @layer components {                                                                         |     |
|     |   .c-card {                                                                                 |     |
|     |     --comp-card-bg: var(--sys-surface-bg);                                                  |     |
|     |     background-color: var(--comp-card-bg);                                                  |     |
|     |   }                                                                                         |     |
|     | }                                                                                           |     |
|     +---------------------------------------------------------------------------------------------+     |
|                                                  │                                                      |
|                                                  ▼                                                      |
|  3. STYLE ENGINE (Recalculate Style Phase)                                                              |
|     ├── Parse DOM & CSSOM                                                                               |
|     ├── Resolusi Directed Acyclic Graph (DAG) Token Kustom                                              |
|     └── Evaluasi Inheritance Boundary (Isolasi Style Blast Radius)                                      |
|                                                  │                                                      |
|                                                  ▼                                                      |
|  4. LAYOUT & PAINT PIPELINE                                                                             |
|     └── Render Frame ke Tampilan Display Layar                                                           |
+---------------------------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Evaluasi Tipe Data Melalui Houdini `@property`

Deklarasi standar CSS Custom Property (`--val: red`) diperlakukan oleh browser sebagai deretan token string bebas tak bertipe (CSS syntax type: `*`). Ini mematikan kemampuan interpolasi animasi dan memaksa browser melakukan inferensi ulang berbiaya tinggi. 

Dengan `@property`, browser mengalokasikan tipe data native ke dalam CSS Typed OM:

```
+----------------------------------------------------+
|  @property --sys-accent-color                      |
|  +----------------------------------------------+  |
|  | syntax: '<color>';                           |  |  --> Memaksa validasi token parser: Tolak non-color
|  | inherits: false;                             |  |  --> Isolasi pewarisan: Menghindari Re-style subtree
|  | initial-value: #2563eb;                      |  |  --> Jaminan fallback mutlak bila parsing gagal
|  +----------------------------------------------+  |
+----------------------------------------------------+
```

* **`syntax`**: Menentukan kontrak tipe data (e.g., `<color>`, `<length>`, `<percentage>`, `<integer>`). Apabila nilai yang di-inject tidak cocok dengan syntax, browser otomatis mengabaikannya dan memakai `initial-value`.
* **`inherits`**: Jika diset ke `false`, properti ini **tidak akan turun** ke child DOM nodes. Ini adalah optimasi performa paling krusial dalam engine CSS custom properties untuk menghentikan rekursi pewarisan *computed values*.
* **`initial-value`**: Nilai pasti yang dijamin ada sejak cycle kalkulasi frame pertama. Bersifat wajib (mandatory) jika `syntax` bukan merupakan wildcard (`*`).

### 2. Resolusi Kaskade dan Fallback Tree

Ketika browser menemukan referensi ekspresi `var()`, mekanisme evaluasinya mengikuti aturan:

$$\text{Resolved Value} = f(\text{Declared Value}, \text{Inherited Value}, \text{Fallback Sequence}, \text{Guaranteed Invalid})$$

```
          Apakah properti terdefinisi
            pada elemen atau ancestor?
                    │
            ┌───────┴───────┐
           YA              TIDAK
            │               │
     Apakah valid      Apakah ada
    secara sintaks?     fallback?
     ┌──────┴──────┐    ┌───┴───┐
    YA            TIDAK YA     TIDAK
     │              │   │        │
  Gunakan        Evaluasi fallback Gunakan
   Nilai            │          Initial
                ┌───┴───┐       Value
               Valid  Invalid     │
                 │      │         │
              Gunakan Gunakan ────┘
               Nilai  Initial
              Fallback Value
```

Jika variabel bernilai `initial` atau referensi siklik terjadi (misal: `--a: var(--b); --b: var(--a);`), browser menetapkan status **Invalid at Computed-Value Time (IACVT)**. Pada kondisi IACVT, browser mengabaikan fallback yang ada di dalam `var()` dan seketika mengeksekusi nilai pewarisan (*inherited value*) dari parent, atau jika tidak ada, nilai awal native dari properti target (seperti `transparent` untuk `background-color`).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Struktur Design Tokens Standar W3C DTCG

Format pertukaran data token modern dibakukan dalam JSON terstruktur. Komponen kunci adalah `$value`, `$type`, dan metadata `$description`.

```json
{
  "color": {
    "primitive": {
      "blue": {
        "600": {
          "$value": "#2563eb",
          "$type": "color"
        }
      }
    },
    "semantic": {
      "action": {
        "primary": {
          "default": {
            "$value": "{color.primitive.blue.600}",
            "$type": "color",
            "$description": "Warna aksi interaktif primer untuk tombol dan tautan aktif."
          }
        }
      }
    }
  }
}
```

### 2. Arsitektur 3-Tier Token System

1. **Tier 1: Global/Primitive Tokens**
   * Merepresentasikan inventaris mentah desain.
   * Bersifat absolut, tidak memiliki konteks penggunaan.
   * *Penamaan:* `[kategori]-[keluarga]-[skala]` (Contoh: `--pr-color-slate-900`, `--pr-spacing-4`).
2. **Tier 2: Semantic/System Tokens**
   * Menghubungkan primitif ke dalam fungsi, interaksi, atau tema.
   * Merupakan lapisan yang di-override ketika tema (Dark/Light/Brand B) berganti.
   * *Penamaan:* `[konteks]-[elemen]-[varian]-[state]` (Contoh: `--sys-color-surface-elevated`, `--sys-color-text-danger-hover`).
3. **Tier 3: Component Tokens**
   * Terisolasi secara lokal pada komponen spesifik.
   * Memberikan kebebasan developer meng-override aspek visual komponen tanpa efek samping ke komponen lain.
   * *Penamaan:* `[komponen]-[properti]-[varian]-[state]` (Contoh: `--cmp-btn-bg-primary-hover`).

### 3. Rekayasa Spesifisitas via CSS Cascade Layers (`@layer`)

Sebelum `@layer`, arsitektur CSS sangat rentan terhadap *specificity wars* yang diatasi secara keliru dengan nesting selektor atau `!important`. `@layer` mengubah urutan kaskade normal:

```
Urutan Prioritas Kaskade Standar (Terendah ke Tertinggi):
1. User-Agent stylesheets
2. Normal Author Styles (Berdasarkan urutan deklarasi @layer)
   ├── layer(primitives)
   ├── layer(tokens)
   ├── layer(reset)
   ├── layer(base)
   ├── layer(components)
   └── layer(utilities)
3. Unlayered Author Styles (Gaya author tanpa layer - SELALU MENANG atas layered styles normal)
4. Author !important Styles (Layered styles TERBALIK: layer deklarasi awal menang atas deklarasi akhir)
```

Dengan mengapit token di dalam `@layer tokens`, sistem menjamin bahwa aturan utilitas atau komponen yang berada di layer berikutnya selalu memiliki prioritas penimpaan tanpa memerlukan selektor bernilai spesifisitas tinggi.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi engine token CSS native yang mengawinkan `@property`, `@layer`, tema runtime, dan isolasi token komponen.

```css
/* ==========================================================================
   01. REGISTRASI ENGINE HOUDINI TYPED OM (TYPE SAFETY & ISOLASI PERFORMA)
   ========================================================================== */
@property --sys-color-surface-bg {
  syntax: '<color>';
  inherits: true;
  initial-value: #ffffff;
}

@property --sys-color-text-primary {
  syntax: '<color>';
  inherits: true;
  initial-value: #0f172a;
}

@property --cmp-button-border-width {
  syntax: '<length>';
  inherits: false;
  initial-value: 1px;
}

/* ==========================================================================
   02. STRUKTURISASI CASCADE LAYERS
   ========================================================================== */
@layer tokens.primitive, tokens.semantic, base, components, utilities;

/* ==========================================================================
   03. TIER 1: PRIMITIVE TOKENS (STATIK)
   ========================================================================== */
@layer tokens.primitive {
  :root {
    /* Base Palette */
    --pr-color-neutral-0: #ffffff;
    --pr-color-neutral-100: #f1f5f9;
    --pr-color-neutral-800: #1e293b;
    --pr-color-neutral-900: #0f172a;

    --pr-color-blue-500: #3b82f6;
    --pr-color-blue-600: #2563eb;
    --pr-color-blue-700: #1d4ed8;

    /* Spacing Units */
    --pr-space-1: 0.25rem; /* 4px */
    --pr-space-2: 0.5rem;  /* 8px */
    --pr-space-3: 0.75rem; /* 12px */
    --pr-space-4: 1rem;    /* 16px */
    
    /* Typography */
    --pr-font-family-sans: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
}

/* ==========================================================================
   04. TIER 2: SEMANTIC TOKENS (RUNTIME THEMING GRAPH)
   ========================================================================== */
@layer tokens.semantic {
  /* Default / Light Theme */
  :root {
    --sys-color-surface-bg: var(--pr-color-neutral-0);
    --sys-color-surface-alt: var(--pr-color-neutral-100);
    --sys-color-text-primary: var(--pr-color-neutral-900);
    
    --sys-color-interactive-default: var(--pr-color-blue-600);
    --sys-color-interactive-hover: var(--pr-color-blue-700);
    --sys-color-interactive-contrast: var(--pr-color-neutral-0);

    color-scheme: light;
  }

  /* Dark Theme Context */
  [data-theme="dark"] {
    --sys-color-surface-bg: var(--pr-color-neutral-900);
    --sys-color-surface-alt: var(--pr-color-neutral-800);
    --sys-color-text-primary: var(--pr-color-neutral-0);

    --sys-color-interactive-default: var(--pr-color-blue-500);
    --sys-color-interactive-hover: var(--pr-color-blue-600);
    --sys-color-interactive-contrast: var(--pr-color-neutral-0);

    color-scheme: dark;
  }

  /* Automatic OS-level fallback */
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --sys-color-surface-bg: var(--pr-color-neutral-900);
      --sys-color-surface-alt: var(--pr-color-neutral-800);
      --sys-color-text-primary: var(--pr-color-neutral-0);

      --sys-color-interactive-default: var(--pr-color-blue-500);
      --sys-color-interactive-hover: var(--pr-color-blue-600);
      --sys-color-interactive-contrast: var(--pr-color-neutral-0);

      color-scheme: dark;
    }
  }
}

/* ==========================================================================
   05. TIER 3: COMPONENT IMPLEMENTATION & CONTRACT
   ========================================================================== */
@layer components {
  /* Base Reset / Global Application */
  body {
    background-color: var(--sys-color-surface-bg);
    color: var(--sys-color-text-primary);
    font-family: var(--pr-font-family-sans);
    margin: 0;
    transition: background-color 200ms ease, color 200ms ease;
  }

  /* Button Component Implementation */
  .c-button {
    /* 1. Component Property Engine Interface (API Pribadi) */
    --_btn-bg: var(--cmp-button-bg, var(--sys-color-interactive-default));
    --_btn-text: var(--cmp-button-text, var(--sys-color-interactive-contrast));
    --_btn-px: var(--cmp-button-padding-x, var(--pr-space-4));
    --_btn-py: var(--cmp-button-padding-y, var(--pr-space-2));
    
    /* 2. Deklarasi Presentasional */
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: var(--_btn-py) var(--_btn-px);
    background-color: var(--_btn-bg);
    color: var(--_btn-text);
    border: var(--cmp-button-border-width) solid transparent;
    border-radius: 4px;
    font-weight: 600;
    cursor: pointer;
    text-decoration: none;
    transition: background-color 150ms cubic-bezier(0.4, 0, 0.2, 1);
  }

  .c-button:hover {
    --_btn-bg: var(--cmp-button-bg-hover, var(--sys-color-interactive-hover));
  }

  /* Variant: Secondary Button */
  .c-button--secondary {
    --cmp-button-bg: var(--sys-color-surface-alt);
    --cmp-button-text: var(--sys-color-text-primary);
    --cmp-button-bg-hover: var(--pr-color-neutral-100);
    --cmp-button-border-width: 1px;
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Registrasi `@property` (Baris 4–18)
* `syntax: '<color>';`: Browser memvalidasi bahwa setiap pengikatan pada `--sys-color-surface-bg` harus menghasilkan nilai representasi warna sah (misal: hex, rgb, oklch). Jika diisi string acak seperti `100px`, browser menggugurkannya.
* `inherits: false;` pada `--cmp-button-border-width`: **Kritis untuk performa**. Mencegah browser mengeksekusi *tree-walking* pewarisan nilai batas tombol ini ke seluruh elemen *children* (seperti icon SVG atau label teks) yang ada di dalam elemen `.c-button`.

### Deklarasi Urutan Layer `@layer` (Baris 23)
* `@layer tokens.primitive, tokens.semantic, base, components, utilities;`: Menetapkan *order of precedence* mutlak sejak awal. Layer paling kanan (`utilities`) memiliki prioritas kaskade tertinggi dibanding layer sebelumnya, independen dari spesifisitas selektor kelas CSS.

### Lapisan Semantik Multi-Theme (Baris 48–78)
* `:root` dan `[data-theme="dark"]`: Meresolusi variabel primitif menjadi instansiasi kontekstual. 
* `color-scheme: light/dark;`: Menginstruksikan modul rendering bawaan OS untuk menyinkronkan *form controls*, *scrollbar*, dan elemen antarmuka sistem lainnya dengan skema warna yang diaktifkan.
* Guard `:root:not([data-theme="light"])`: Memastikan kueri media `@media (prefers-color-scheme: dark)` tidak menimpa pengaturan eksplisit ketika user secara sadar memilih tema *Light* via UI switch.

### Private Component Variables `--_btn-*` (Baris 97–101)
* Penggunaan prefiks garis bawah ganda (`--_btn-bg`) merupakan implementasi pola desain **Private Component Variables**. Pola ini mengevaluasi variabel publik kustom (`--cmp-button-bg`) jika ada penyuntikan dari luar, dan jatuh kembali (*fallback*) ke semantic default global (`--sys-color-interactive-default`). Ini mencegah kontaminasi cakupan global.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Migrasi White-Label FinTech Platform

Sebuah platform perbankan multinasional ("Apex FinTech") melayani tiga merek perbankan digital berbeda (*Brand Core*, *Brand Wealth*, dan *Brand Neo*) dari basis kode monorepo yang sama. 

#### Tantangan Teknis:
1. **Flash of Unstyled Content (FOUC):** Pengguna mengalami kedipan tema selama 150-300ms saat server merender HTML dan JavaScript runtime menentukan tema aktif.
2. **Specificity Conflicts:** Penyesuaian tema (*theming overrides*) dilakukan dengan menambahkan class chaining berkekuatan spesifisitas tinggi (`body.brand-wealth .dashboard .c-card { ... }`), menyebabkan stylesheet membengkak hingga 4.2 MB dan merusak ekstensi CSS masa depan.
3. **Style Recalculation Bottleneck:** Saat pengguna mengubah tema secara manual, terjadi *frame drop* ekstrim (jank hingga 240ms) karena browser mengevaluasi ulang pewarisan ribuan token pada jutaan node DOM secara bersamaan.

#### Solusi Arsitektural:
* Menerapkan sistem **Tiered Design Tokens murni CSS** yang dibundel langsung ke blok `<head>` dokumen via inline CSS berukuran < 14KB (memastikan single round-trip HTTP).
* Memigrasikan arsitektur spesifisitas warisan ke **CSS Cascade Layers (`@layer`)**.
* Menggunakan **`inherits: false`** pada semua token privat komponen menggunakan API `@property` untuk mengisolasi *Recalculate Style blast radius*.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Struktur arsitektur produksi sistem tema FinTech terintegrasi:

```
src/tokens/
├── 01-primitives.css
├── 02-semantics.css
├── 03-brands/
│   ├── brand-core.css
│   ├── brand-wealth.css
│   └── brand-neo.css
└── index.css
```

### 1. `02-semantics.css` — Engine Semantik & Registrasi Houdini

```css
/* Pendaftaran Kontrak Strict Typed */
@property --theme-brand-accent {
  syntax: '<color>';
  inherits: true;
  initial-value: #004ac2;
}

@property --theme-elevation-shadow {
  syntax: '*';
  inherits: false;
  initial-value: none;
}

@layer tokens.semantic {
  :root {
    --fx-elevation-level-1: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
    --fx-elevation-level-2: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  }
}
```

### 2. `brand-wealth.css` — Konfigurasi Skema Sub-Brand

```css
@layer tokens.semantic {
  :root[data-brand="wealth"] {
    --theme-brand-accent: #d97706; /* Amber Gold */
    --sys-surface-bg: #030712;      /* Deep Luxury Charcoal */
    --sys-surface-card: #111827;
    --sys-text-primary: #f9fafb;
    --sys-text-secondary: #9ca3af;
    --sys-border-subtle: #1f2937;
    
    --theme-elevation-shadow: 0 10px 15px -3px rgba(217, 119, 6, 0.05);
  }
}
```

### 3. Komponen Produksi: Data Table Metrik Keuangan Terisolasi

```css
@layer components {
  .ft-metric-card {
    /* Private API tokens: Mengunci ketergantungan internal */
    --_card-bg: var(--metric-card-custom-bg, var(--sys-surface-card, #ffffff));
    --_card-border: var(--metric-card-custom-border, var(--sys-border-subtle, #e5e7eb));
    --_card-accent: var(--metric-card-custom-accent, var(--theme-brand-accent));

    position: relative;
    display: flex;
    flex-direction: column;
    padding: 1.5rem;
    background-color: var(--_card-bg);
    border: 1px solid var(--_card-border);
    border-radius: 8px;
    box-shadow: var(--theme-elevation-shadow);
    transition: border-color 200ms ease;
  }

  .ft-metric-card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 4px;
    height: 100%;
    background-color: var(--_card-accent);
    border-top-left-radius: 8px;
    border-bottom-left-radius: 8px;
  }

  .ft-metric-card__title {
    font-size: 0.875rem;
    color: var(--sys-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0 0 0.5rem 0;
  }

  .ft-metric-card__value {
    font-size: 1.875rem;
    font-weight: 700;
    color: var(--sys-text-primary);
    margin: 0;
  }
}
```

### 4. Zero-FOUC Inlined Controller (HTML Document Integration)

Untuk menjamin tidak ada kedipan tampilan (FOUC), script engine kecil disematkan pada awal tag `<head>` sebelum stylesheet CSS eksternal diproses:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Apex FinTech Platform</title>

  <!-- Anti-FOUC Zero Runtime Delay Script -->
  <script>
    (function() {
      try {
        const savedTheme = localStorage.getItem('apex_theme') || 'system';
        const savedBrand = localStorage.getItem('apex_brand') || 'wealth';
        const root = document.documentElement;
        
        root.setAttribute('data-brand', savedBrand);
        
        if (savedTheme === 'system') {
          const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
          root.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
        } else {
          root.setAttribute('data-theme', savedTheme);
        }
      } catch (e) {
        // Fallback default jika LocalStorage diblokir oleh security sandbox
        document.documentElement.setAttribute('data-theme', 'light');
        document.documentElement.setAttribute('data-brand', 'wealth');
      }
    })();
  </script>

  <link rel="stylesheet" href="/assets/css/engine.css">
</head>
<body>
  <main style="padding: 2rem;">
    <section class="ft-metric-card">
      <h3 class="ft-metric-card__title">Total Nilai Portofolio</h3>
      <p class="ft-metric-card__value">Rp 12.845.000.000</p>
    </section>
  </main>
</body>
</html>
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek Arsitektur | SCSS/Sass Variables | Vanilla CSS Custom Properties | Houdini `@property` Engine | CSS-in-JS (e.g., Emotion/Styled) |
| :--- | :--- | :--- | :--- | :--- |
| **Waktu Resolusi Nilai** | Waktu Kompilasi (Build Time) | Runtime DOM Tree Walk | Runtime DOM Typed OM Engine | Runtime JS Thread Execution |
| **Overhead Ukuran Bundle** | Sangat Rendah (String terduplikasi) | Rendah (Hanya deklarasi variabel) | Sangat Rendah (Deklarasi spesifikasi token) | Tinggi (Runtime JS parser & injector) |
| **Dukungan Dynamic Theming** | Buruk (Perlu unduh CSS file terpisah) | Sempurna (Cukup mutasi atribut root) | Sempurna (Mutasi atribut + validasi) | Baik, tetapi memicu re-render JS komponen |
| **Kinerja Interpolasi/Animasi** | Tidak Mendukung Animasi Dinamis | Tidak Bisa Diinterpolasi secara mulus | Mendukung Interpolasi Halus Native | Bergantung pada library animasi JS eksternal |
| **Type Safety & Fallback** | Tinggi di level build tooling | Lemah (Fallback manual dalam `var()`) | Sangat Tinggi (Strict native contract) | Tinggi via TypeScript interfaces |
| **Konsumsi Memori Browser** | Paling Efisien (Sifatnya statis) | Menengah (Penyimpanan graph referensi) | Terkelola Optimal (Tanpa inherit tak perlu) | Buruk (Duplikasi Style Sheet Instance di Memori) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Fallback Cycle Trap (Siklus Sirkular)

```css
/* JANGAN LAKUKAN INI */
:root {
  --color-a: var(--color-b, #111);
  --color-b: var(--color-a, #999);
}
```

* **Mekanisme Kegagalan:** Browser mendeteksi siklus dependensi tak berujung (*cyclic dependency*). Pada saat dependensi siklik terdeteksi, **seluruh variabel yang terlibat dianggap tidak valid pada saat evaluasi nilai (IACVT)**.
* **Mitigasi:** Variabel