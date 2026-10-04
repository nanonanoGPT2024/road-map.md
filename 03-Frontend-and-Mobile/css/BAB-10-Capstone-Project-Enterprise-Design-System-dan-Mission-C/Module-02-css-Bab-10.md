# BAB 10: Capstone Project – Enterprise Design System & Mission-Critical CSS Architecture
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang & Mengimplementasikan Arsitektur Multi-Brand Token Engine**: Mengonversi spesifikasi W3C Design Tokens (DTCG) menjadi distribusi multi-platform (CSS Variables, JSON, iOS/Android) dengan *Style Dictionary* terotomatisasi secara *zero-runtime overhead*.
2. **Menguasai Manajemen Cascade Skala Enterprise**: Menerapkan arsitektur `@layer` modular untuk mengeliminasi ketergantungan pada spesifisitas `!important` dan selector *chaining* berlebih pada lingkungan *Micro-Frontends* (MFE).
3. **Mengoptimalkan Jalur Kritis Rendering Browser (Critical Rendering Path)**: Mereduksi *Recalculate Style* dan *Layout Invalidation* menggunakan CSS Containment (`contain`, `content-visibility`) serta *Container Queries* dan CSS Subgrid.
4. **Membangun Sistem Isolasi Gaya Bebas Kebocoran (Zero-Leakage)**: Mengintegrasikan isolasi komponen tingkat lanjut tanpa degradasi performa Shadow DOM untuk ratusan modul terdistribusi.
5. **Menjamin Reliabilitas Sistem Visual**: Menerapkan otomatisasi CI/CD untuk CSS linting, deteksi *dead-code*, audit anggaran ukuran berkas (*bundle size budget*), dan pengujian regresi visual terdistribusi.

---

### 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut:
* Pemahaman fundamental CSS: Cascade, Inheritance, dan Specificity Math ($[a, b, c, d]$).
* Penguasaan CSS Custom Properties (`var()`, *variable scoping*, *fallback mechanics*).
* Pemahaman mendalam tentang siklus hidup rendering peramban (*DOM & CSSOM construction*, *Render Tree*, *Layout/Reflow*, *Paint*, *Composite*).
* Kemahiran dalam ekosistem Node.js/TypeScript, PostCSS, dan *bundler* modern (Vite/Webpack/Rollup).
* Pemahaman konsep dasar arsitektur Micro-Frontends dan *Web Components*.

---

### 3. Concept & Internal Architecture

Implementasi CSS tingkat *enterprise* memerlukan pendekatan rekayasa sistem yang memisahkan data desain, orkestrasi *cascade*, dan eksekusi rendering peramban.

```
+-----------------------------------------------------------------------------------+
|                        DESIGN TOKEN SOURCE (W3C DTCG SPEC)                        |
|                     tokens/globals/ -> tokens/brands/[A|B]/                       |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                   STYLE DICTIONARY ENGINE / AST COMPILER PIPELINE                 |
|       - Token Resolution (Deduplication, Aliasing, Math transforms)               |
|       - Platform Targets: Web (CSS/SCSS), Mobile (Swift/XML), Types (TS)          |
+-----------------------------------------+-----------------------------------------+
                                          |
                        +-----------------+-----------------+
                        |                                   |
                        v                                   v
+----------------------------------+     +----------------------------------+
|      PRIMITIVE VARIABLES         |     |       SEMANTIC TOKENS            |
|   :root { --color-blue-500:... } |     |   [data-theme="dark"] { ... }    |
+-----------------------+----------+     +------------------+---------------+
                        |                                   |
                        +-----------------+-----------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                           CASCADE LAYER ARCHITECTURE                              |
|   @layer reset, primitives, semantic, components, layout, overrides;              |
|                                                                                   |
|   +---------------------------------------------------------------------------+   |
|   | Micro-Frontend A (Host)          | Micro-Frontend B (Remote Plugin)       |   |
|   | Uses: @layer components.host;    | Uses: @layer components.remote;        |   |
|   +---------------------------------------------------------------------------+   |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                       BROWSER RENDERING ENGINE PIPELINE                           |
|  CSSOM Nodes -> Style Recalc -> Layout (Subgrid/CQ) -> Paint (contain) -> GPU Comp|
+-----------------------------------------------------------------------------------+
```

#### A. Multi-Tier Token Architecture
Desain sistem modular membagi token ke dalam tiga tingkatan hierarki untuk menghindari kopling langsung:
1. **Global/Primitive Tokens**: Nilai mentah (*hardcoded values*) yang mewakili palet desainer (misal: `--sys-palette-blue-500: #1a73e8;`).
2. **Contextual/Semantic Tokens**: Nilai yang merepresentasikan fungsi dan tujuan semantik dalam antarmuka, serta merujuk ke token primitif (misal: `--semantic-color-surface-action: var(--sys-palette-blue-500);`).
3. **Component-Scoped Tokens**: Variabel khusus untuk satu komponen tertentu yang dipetakan ke semantic token (misal: `--cmp-button-bg-primary: var(--semantic-color-surface-action);`).

#### B. Cascade Layering (`@layer`) pada Micro-Frontend
Dalam sistem multi-tim berskala besar, masalah klasik timbul saat Micro-Frontend A memiliki selector dengan bobot spesifisitas tinggi (`#app .main .btn`) yang menimpa gaya Micro-Frontend B. Aturan `@layer` mengabstraksi aturan resolusi: layer yang didefinisikan belakangan dalam urutan inisialisasi akan selalu menang mengalahkan layer sebelumnya, **tanpa memedulikan spesifisitas selektor di dalam layer tersebut**.

```css
/* Inisialisasi Urutan Otoritas */
@layer reset, base, design-system, components, utilities, overrides;

/* Aturan Spesifisitas Terisolasi:
   Selector di 'utilities' selalu mengalahkan selector di 'components',
   bahkan jika selector di 'components' adalah ID dan 'utilities' adalah class! */
@layer components {
  #checkout-btn { background: red; } /* Specificity: 1, 0, 0 */
}

@layer utilities {
  .u-bg-blue { background: blue; }    /* Specificity: 0, 1, 0 */
}
/* Hasil Komputasi: background: blue; */
```

#### C. Render Tree Optimization: Containment & Subgrid
Arsitektur CSS performa tinggi memanfaatkan fitur native browser engine:
* **CSS Containment (`contain: layout paint style`)**: Mengisolasi subtree DOM dari pohon dokumen utama. Jika elemen di dalam kontainer mengalami perubahan dimensi, peramban membatasi operasi *Reflow/Layout* hanya pada subtree tersebut, mencegah siklus invalidasi global.
* **`content-visibility: auto`**: Menghindari peramban merender elemen yang berada di luar *viewport* (*off-screen*), menghemat siklus CPU/GPU secara signifikan pada halaman data padat (*heavy-data tables/feeds*).
* **CSS Subgrid (`grid-template-columns: subgrid`)**: Menyelaraskan item bersarang langsung ke sistem grid induk tanpa menduplikasi parameter ukuran kolom, mengeliminasi kebutuhan JS layout calculations.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Monolithic SCSS/CSS-in-JS) | Enterprise CSS Architecture Modern |
| :--- | :--- | :--- |
| **Cascade Management** | Mengandalkan konvensi BEM ketat atau hash nama class dinamis. Rentan tabrakan saat integrasi Micro-Frontend. | Strict Native `@layer` orchestration. Tidak ada ketergantungan konvensi manual; dijamin oleh spesifikasi peramban. |
| **Dynamic Theming** | Kompilasi ulang file SCSS atau re-render runtime React (`ThemeProvider` dengan context injector) yang memicu rerender massal. | Swap CSS Custom Properties via atribut data (`data-theme="dark"`) murni di CSSOM. Render cost = 0 JS cycles. |
| **Layout Performance** | Polifill Flexbox/JS-based height sync. Menghasilkan *Layout Thrashing* dan pemblokiran thread utama. | Native Container Queries (`@container`) + CSS Subgrid + Hardware-Accelerated Transforms. |
| **Dead-Code Elimination** | Mengandalkan PurgeCSS regex scanning yang rawan menghapus class dinamis (*false-positives*). | Semantic AST analysis terintegrasi dengan bundler, dikombinasikan dengan token-based usage validation. |

---

### 5. How (Workflow Detail)

Berikut alur kerja integrasi *end-to-end* dari desain ke sistem produksi:

```
[Design Tool / Figma Tokens Studio]
                 |
                 v (Git Sync / Webhook)
[Source Repository: tokens/*.json]
                 |
                 v (GitHub Actions Triggered)
[Transform Layer: Style Dictionary + Transpiler Engine]
     ├── Format: CSS Variables (`:root`, `[data-theme="..."]`)
     ├── Format: TypeScript Type Definitions (`tokens.d.ts`)
     └── Format: JSON Schema (Untuk verifikasi linting komponen)
                 |
                 v
[CSS Layer Composition (PostCSS Pipeline)]
     ├── Injeksi Normalize & Core Base Layer
     ├── Injeksi Semantic Tokens
     ├── Kompilasi CSS Modules dengan scoped `@layer components`
     └── Optimasi Minifikasi via CSSNano / LightningCSS
                 |
                 v
[Distribution / Artifact Registry]
     ├── NPM Scope: `@enterprise/design-tokens`
     ├── NPM Scope: `@enterprise/ui-core`
     └── CDN Edge Endpoint: `https://static.cdn.enterprise.com/ds/v2/tokens.min.css`
```

1. **Token Ingestion**: Desainer mengekspor token dalam format standar W3C DTCG ke repositori token via PR otomatis.
2. **Deterministic Build Pipeline**: GitHub Actions menjalankan skrip kompilasi *Style Dictionary* yang memvalidasi integritas struktur, dependensi warna (kontras rasio WCAG AAA), dan menghasilkan target artefak.
3. **Layer Integration**: Komponen UI mengimpor token variabel, mendeklarasikan cakupan gayanya di dalam `@layer components.*`.
4. **Validation**: CI menguji *bundle size budget* (maksimal kenaikan 2% per PR) dan menjalankan pengujian regresi visual Playwright tanpa *headless flicker*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Distribusi Tenaga Listrik Kota
Arsitektur CSS ini analog dengan infrastruktur penyediaan listrik modern:
* **Primitive Tokens = Pembangkit Listrik (Power Plant)**: Menghasilkan daya mentah (Tegangan Ultra Tinggi 500kV). Ini adalah warna dasar, jarak mentah, yang berbahaya jika diakses langsung oleh konsumen akhir.
* **Semantic Tokens = Gardu Transformator Distribusi**: Menurunkan tegangan menjadi 220V yang aman dan spesifik untuk peruntukannya (Residensial, Industri, Komersial). Ini setara dengan memetakan warna mentah menjadi "Background Primary", "Text Subdued".
* **Component Tokens = Stopkontak Dinding & Peralatan**: Titik konsumsi spesifik yang tinggal menancapkan steker tanpa perlu memikirkan dari mana sumber listrik berasal.
* **Cascade Layers (`@layer`) = Pemutus Sirkuit (Circuit Breaker Priority)**: Menentukan sirkuit mana yang diutamakan ketika terjadi lonjakan beban listrik tanpa merusak seluruh jaringan kabel rumah.

```
[Pembangkit: Raw Tokens]  ---> [Gardu: Semantic Tokens]  ---> [Stopkontak: Components]
(--palette-red-900: #4a0002)    (--color-status-danger)       (--btn-danger-bg)
                                          |
                                          v
               +------------------------------------------------------+
               | PRIORITY BREAKER PANEL (@layer)                      |
               |                                                      |
               | [Level 1: Reset]      (Grounding)                    |
               | [Level 2: Semantic]   (Tegangan Teratur)             |
               | [Level 3: Components] (Peralatan Rumah Tangga)       |
               | [Level 4: Overrides]  (Genset Darurat Tertinggi)     |
               +------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Style Dictionary Transformation Script

Skrip Node.js untuk mengekstrak dan memformat token menjadi CSS Custom Properties yang terbungkus `@layer`.

```javascript
// build-tokens.mjs
import StyleDictionary from 'style-dictionary';

StyleDictionary.registerFormat({
  name: 'css/layered-variables',
  formatter: function({ dictionary, file }) {
    return `@layer design-system.tokens {\n  :root {\n` +
      dictionary.allProperties.map(prop => {
        return `    --${prop.name}: ${prop.value};`;
      }).join('\n') +
      `\n  }\n}\n`;
  }
});

const sd = StyleDictionary.extend({
  source: ['tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'dist/css/',
      files: [{
        destination: 'tokens.css',
        format: 'css/layered-variables'
      }]
    }
  }
});

sd.buildAllPlatforms();
```

#### B. Practical Example: Mission-Critical Enterprise Data Card

Komponen ini memanfaatkan `@layer`, Container Queries (`@container`), Subgrid, CSS Variables hierarki tiga tingkat, dan performa tinggi isolasi rendering.

```css
/* styles/components/finance-card.css */

/* 1. Mendaftarkan Layer Global */
@layer reset, design-system, components, overrides;

@layer components {
  /* 2. Container Query Parent Declaration */
  .finance-card-container {
    contain: layout inline-size style;
    container-type: inline-size;
    container-name: finance-card;
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: var(--sys-spacing-4, 1rem);
  }

  /* 3. Component Implementation */
  .finance-card {
    /* Component Scoped Tokens with Semantic Fallbacks */
    --card-bg: var(--semantic-surface-raised, #ffffff);
    --card-border: var(--semantic-border-subtle, #e2e8f0);
    --card-text-primary: var(--semantic-text-primary, #0f172a);
    --card-padding: var(--sys-spacing-6, 1.5rem);

    grid-column: span 12;
    display: grid;
    grid-template-columns: subgrid;
    grid-template-rows: auto auto auto;
    
    background-color: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: var(--sys-radius-lg, 0.5rem);
    padding: var(--card-padding);
    
    /* Paint Containment to isolate GPU rasterization */
    contain: paint;
    content-visibility: auto;
    contain-intrinsic-size: 0 180px;
    
    transition: transform 150ms cubic-bezier(0, 0, 0.2, 1),
                box-shadow 150ms cubic-bezier(0, 0, 0.2, 1);
  }

  .finance-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--sys-elevation-level2, 0 4px 6px -1px rgba(0,0,0,0.1));
  }

  .finance-card__header {
    grid-column: span 12;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .finance-card__metrics {
    grid-column: span 12;
    display: grid;
    grid-template-columns: subgrid;
    margin-block-start: var(--sys-spacing-4, 1rem);
  }

  .finance-card__metric-item {
    grid-column: span 6;
  }

  /* 4. Container Query Responsive Logic (No Viewport Dependency) */
  @container finance-card (min-width: 640px) {
    .finance-card {
      grid-column: span 6;
    }
    
    .finance-card__metric-item {
      grid-column: span 3;
    }
  }

  @container finance-card (min-width: 1024px) {
    .finance-card {
      grid-column: span 4;
      --card-padding: var(--sys-spacing-8, 2rem);
    }
  }
}
```

Implementasi Markup HTML:

```html
<section class="finance-card-container">
  <article class="finance-card">
    <header class="finance-card__header">
      <h3 style="color: var(--card-text-primary);">Liquidity Pool A</h3>
      <span class="status-badge" data-status="healthy">Healthy</span>
    </header>
    <div class="finance-card__metrics">
      <div class="finance-card__metric-item">
        <small>APY</small>
        <strong>8.45%</strong>
      </div>
      <div class="finance-card__metric-item">
        <small>TVL</small>
        <strong>$142.8M</strong>
      </div>
    </div>
  </article>
</section>
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Sebuah institusi perbankan global memiliki aplikasi Super-App yang menampung 4 unit bisnis utama: Retail Banking, Corporate Wealth, Crypto Exchanges, dan Insurance Services. Masing-masing modul dibangun oleh tim rekayasa perangkat lunak otonom menggunakan arsitektur Micro-Frontend (Webpack Module Federation).

#### Permasalahan Skala Produksi
1. **Style Leaking Massif**: Tim *Corporate Wealth* menggunakan pustaka UI eksternal yang memuat CSS global kotor yang menimpa tag `table` dan `.btn` pada modul *Retail Banking*.
2. **CSS Spec War**: Ratusan selector menggunakan `!important` berantai (contoh: `#app .content .container .card .btn.primary !important`) untuk merebut prioritas cascade. Timbal baliknya: ukuran berkas CSS melambung menjadi 4.8MB (uncompressed).
3. **Cumulative Layout Shift (CLS = 0.42)**: Pengalihan tema (Light ke Dark) menyebabkan pembaruan *layout* seluruh dokumen secara beruntun (*synchronous layout thrashing*) yang memblokir main-thread selama 600ms pada gawai low-end.

#### Arsitektur Solusi
1. **Penerapan Multi-Tenant Cascade Layers**:
   Host application menetapkan isolasi orkestrasi:
   ```css
   @layer enterprise-reset, 
          enterprise-tokens, 
          mfe-retail, 
          mfe-corporate, 
          mfe-crypto, 
          enterprise-overrides;
   ```
   Setiap remote module dikompilasi ke dalam sub-layer spesifik mereka masing-masing via PostCSS plugin:
   ```javascript
   // postcss.config.js remote MFE Corporate
   export default {
     plugins: [
       require('postcss-wrap-in-layer')({ layer: 'mfe-corporate' })
     ]
   };
   ```
2. **Dynamic Theming via Zero-Runtime CSS Engine**:
   Menghapus seluruh dependensi CSS-in-JS (seperti Emotion/Styled-Components) yang menginjeksi tag `<style>` secara runtime. Seluruh parameter warna diubah menjadi representasi CSS Custom Properties dengan kompresi gamut warna Display-P3 melalui CSS Color Module Level 4:
   ```css
   [data-brand="corporate"][data-theme="dark"] {
     --semantic-bg-canvas: oklch(0.18 0.02 240);
     --semantic-accent: oklch(0.65 0.18 145);
   }
   ```
3. **Penyekatan Render Tree via Layout Isolation**:
   Setiap micro-frontend root dibatasi menggunakan `contain: layout style;`.

#### Hasil Metrik Kinerja Produksi
* **First Meaningful Paint (FMP)**: Menurun dari 3.8 detik menjadi 1.1 detik pada jaringan 4G.
* **Cumulative Layout Shift (CLS)**: Berkurang drastis dari **0.42** menjadi **0.002** (Lolos audit Core Web Vitals).
* **Ukuran Berkas Bundle CSS**: Terpangkas sebesar **72%** (dari 4.8MB menjadi 1.34MB transfer gzipped gabungan untuk 4 domain aplikasi).
* **Insiden Regresi Visual Bulanan**: Turun dari rata-rata 18 insiden per rilis sprint menjadi 0 selama 3 kuartal berturut-turut.

---

### 9. Trade-offs

| Pendekatan Arsitektur | Keuntungan (Pros) | Biaya & Kompromi (Cons) | Kapan Harus Digunakan? |
| :--- | :--- | :--- | :--- |
| **Native `@layer` Architecture** | Menghilangkan perang spesifisitas secara definitif; menyederhanakan CSS selector; integrasi MFE tanpa friksi. | Aturan pembalikan prioritas pada `!important` di dalam `@layer` sangat tidak intuitif; memerlukan peramban modern (Safari 15.4+, Chrome 99+). | Sistem multi-tim berskala besar dengan multi-microfrontends. |
| **Subgrid Layout Engine** | Menjaga konsistensi vertikal/horizontal hierarki komponen bersarang tanpa JavaScript. | Kurang fleksibel jika komponen anak harus memecah konteks alignment secara dinamis; debugging grid bersarang lebih kompleks. | Dashboard analitik, complex responsive tables, multi-column listing. |
| **Container Queries (`@container`)** | Komponen sepenuhnya modular dan otonom; responsif terhadap parent kontainer, bukan viewport kaku. | Penambahan parameter `contain: size` atau `inline-size` dapat memicu *infinite loop resolution* jika tidak dirancang hati-hati. | Komponen Design System yang harus bisa ditanam di sidebar, modal, ataupun main canvas. |
| **Pure CSS Custom Properties (Zero-Runtime)** | Performa rendering instan; pemakaian memori thread utama minimal; kompatibel dengan seluruh framework UI. | Kurang memiliki kapabilitas *dead-code tree-shaking* token secara otomatis jika dibandingkan dengan Vanilla-Extract / PandaCSS. | Komponen antarmuka yang membutuhkan *runtime dynamic theming* dengan latensi 0ms. |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: Pembalikan Otoritas `!important` pada Cascade Layers
* **Gejala Masalah**: Developer menambahkan `!important` pada layer prioritas rendah (misal: `reset`), namun deklarasi tersebut secara tak terduga menimpa layer prioritas tinggi (misal: `components`).
* **Akar Masalah (Root Cause)**: Sesuai spesifikasi W3C CSS Cascading and Inheritance Level 5, urutan prioritas untuk deklarasi bertanda `!important` adalah **kebalikan persis** dari deklarasi normal. Layer pertama (paling bawah di hierarki) memiliki hak veto tertinggi saat diberi `!important`.
  ```
  Normal:   reset < base < components < overrides
  Important: overrides < components < base < reset  (Reset MENANG!)
  ```
* **Solusi**: Larang keras deklarasi `!important` di dalam `@layer` internal melalui linter rule `stylelint`:
  ```json
  {
    "rules": {
      "keyframe-declaration-no-important": true,
      "declaration-no-important": true
    }
  }
  ```

#### Kasus 2: Subgrid Runtuh (*Collapse*) Akibat Properti Display Tak Sesuai
* **Gejala Masalah**: Elemen anak yang ditandai `grid-template-columns: subgrid` tidak merender kolom grid induk dan konten bertumpuk tak beraturan.
* **Akar Masalah**: Elemen bersarang tersebut belum dideklarasikan sebagai CSS Grid (`display: grid` belum diset pada elemen tersebut), sehingga instruksi subgrid diabaikan oleh engine peramban.
* **Solusi**:
  ```css
  /* SALAH */
  .nested-child {
    grid-template-columns: subgrid;
  }

  /* BENAR */
  .nested-child {
    display: grid;
    grid-template-columns: subgrid;
  }
  ```

#### Kasus 3: Infinite Loops pada Container Queries
* **Gejala Masalah**: Browser crash atau halaman membeku (*freezing*) dengan pemanfaatan CPU 100% saat mengubah ukuran browser.
* **Akar Masalah**: Ukuran kontainer (`container-type: size`) bergantung pada ukuran elemen anak, tetapi elemen anak mengubah ukurannya berdasarkan ukuran kontainer tersebut melalui `@container`.
* **Solusi**: Gunakan `container-type: inline-size` jika hanya ingin menyesuaikan layout secara horizontal, dan berikan dimensi deterministik pada sumbu blok (*vertical axis*).

---

### 11. Best Practices (Production Checklist)

Gunakan daftar periksa teknis ini sebelum merilis Design System ke tahap produksi:

```markdown
### [Production CSS Architecture Checklist]

#### Architecture & Cascade Management
- [ ] Seluruh stylesheet dasar, framework pihak ketiga, dan modul komponen dibungkus dalam explicit `@layer`.
- [ ] Tidak ada aturan `!important` yang digunakan untuk mengontrol spesifisitas antar layer.
- [ ] Selector spesifisitas tidak melebihi 2 level class (`.component__element` maksimum, tanpa arbitrary ID selector).

#### Design Token Integrity
- [ ] Token mematuhi spesifikasi standar W3C DTCG Format.
- [ ] Tidak ada hardcoded hex-color atau arbitrary pixel values di file komponen CSS.
- [ ] Seluruh token warna memiliki fallback yang memenuhi rasio kontras WCAG 2.1 AA (4.5:1 untuk teks normal).

#### Browser Engine Performance
- [ ] Elemen perulangan masif (list items, cards, charts) mengaktifkan `content-visibility: auto`.
- [ ] Komponen kompleks menggunakan `contain: layout style` untuk menyekat invalidasi rendering.
- [ ] Animasi antarmuka secara eksklusif hanya mengubah properti `transform` dan `opacity` (menghindari layout triggers).
- [ ] `contain-intrinsic-size` diset secara presisi untuk mencegah scroll-jumping saat off-screen render.

#### Delivery & Bundling
- [ ] Ukuran berkas CSS Kritis (*Critical CSS*) per halaman tidak melebihi anggaran 40KB (gzipped).
- [ ] CSS Modules atau Scoped Layers diterapkan untuk memastikan tidak ada pencemaran global (*global style pollution*).
- [ ] Target browser mendukung fitur baseline modern dengan PostCSS preset-env Stage 2+.
```

---

### 12. Hands-on Practice

Mari bangun implementasi arsitektur token dan komponen layered berstandar produksi di dalam folder `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── package.json
├── tokens/
│   ├── globals.json
│   └── semantic.json
├── scripts/
│   └── build-tokens.js
├── src/
│   ├── base.css
│   ├── components/
│   │   └── enterprise-metric.css
│   └── index.html
```

#### Langkah 1: Inisialisasi Proyek & Dependensi
Simpan berkas `package.json`:
```json
{
  "name": "enterprise-css-architecture",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "build:tokens": "node scripts/build-tokens.js",
    "serve": "npx serve src"
  },
  "devDependencies": {
    "style-dictionary": "^3.8.0"
  }
}
```
Jalankan di terminal:
```bash
npm install
```

#### Langkah 2: Konfigurasi Design Tokens
Simpan di `tokens/globals.json`:
```json
{
  "sys": {
    "palette": {
      "neutral": {
        "0": { "value": "#ffffff" },
        "900": { "value": "#0f172a" }
      },
      "brand": {
        "primary": { "value": "#2563eb" },
        "accent": { "value": "#06b6d4" }
      }
    },
    "spacing": {
      "base": { "value": "4px" },
      "unit-4": { "value": "{sys.spacing.base} * 4" }
    }
  }
}
```

Simpan di `tokens/semantic.json`:
```json
{
  "semantic": {
    "color": {
      "background": {
        "canvas": { "value": "{sys.palette.neutral.0}" },
        "inverted": { "value": "{sys.palette.neutral.900}" }
      },
      "action": {
        "primary": { "value": "{sys.palette.brand.primary}" }
      }
    }
  }
}
```

#### Langkah 3: Skrip Engine Kompilasi Token
Simpan di `scripts/build-tokens.js`:
```javascript
import StyleDictionary from 'style-dictionary';

StyleDictionary.registerFormat({
  name: 'css/production-tokens',
  formatter: function ({ dictionary }) {
    const lines = dictionary.allProperties.map(prop => {
      // Ubah parsing nesting menjadi css var standard name
      const cleanName = prop.path.join('-');
      return `    --${cleanName}: ${prop.value};`;
    });
    return `@layer design-system.tokens {\n  :root {\n${lines.join('\n')}\n  }\n}\n`;
  }
});

const sd = StyleDictionary.extend({
  source: ['tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'src/generated/',
      files: [{
        destination: 'tokens.css',
        format: 'css/production-tokens'
      }]
    }
  }
});

sd.buildAllPlatforms();
console.log('✅ Enterprise Token Engine successfully generated dist artifacts.');
```

#### Langkah 4: Pembuatan Base Cascade Layer
Simpan di `src/base.css`:
```css
@import "./generated/tokens.css";

/* Mendefinisikan Hirarki Layer Resmi */
@layer reset, design-system.tokens, base, components, overrides;

@layer reset {
  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  
  body {
    font-family: system-ui, -apple-system, sans-serif;
    background-color: var(--semantic-color-background-canvas);
    color: var(--semantic-color-background-inverted);
    padding: 2rem;
  }
}
```

#### Langkah 5: Implementasi Komponen Enterprise Berkinerja Tinggi
Simpan di `src/components/enterprise-metric.css`:
```css
@layer components {
  .metric-grid-host {
    contain: layout inline-size;
    container-type: inline-size;
    container-name: metric-host;
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 1.5rem;
    margin-block-start: 2rem;
  }

  .metric-card {
    /* Scoped Variables */
    --metric-border-color: #e2e8f0;
    --metric-accent-color: var(--semantic-color-action-primary);

    grid-column: span 12;
    display: grid;
    grid-template-columns: subgrid;
    border: 1px solid var(--metric-border-color);
    border-radius: 8px;
    padding: 1.5rem;
    background: #fff;
    contain: paint;
  }

  .metric-card__title {
    grid-column: span 12;
    font-size: 0.875rem;
    text-transform: uppercase;
    color: #64748b;
  }

  .metric-card__body {
    grid-column: span 12;
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    margin-block-start: 0.5rem;
  }

  .metric-card__val {
    font-size: 2rem;
    font-weight: 700;
  }

  .metric-card__trend {
    color: var(--metric-accent-color);
    font-size: 0.875rem;
    font-weight: 600;
  }

  /* Responsive via Parent Container Dimension */
  @container metric-host (min-width: 480px) {
    .metric-card {
      grid-column: span 6;
    }
  }

  @container metric-host (min-width: 900px) {
    .metric-card {
      grid-column: span 4;
    }
  }
}
```

#### Langkah 6: Menggabungkan dan Menjalankan Test Bench
Simpan di `src/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Enterprise CSS Architecture Test Bench</title>
  <link rel="stylesheet" href="base.css">
  <link rel="stylesheet" href="components/enterprise-metric.css">
</head>
<body>
  <h1>Performance & Architecture Dashboard</h1>
  <p>Cascade Layers & Container Queries Enterprise Implementation.</p>

  <section class="metric-grid-host">
    <article class="metric-card">
      <h4 class="metric-card__title">Total Transaction Value</h4>
      <div class="metric-card__body">
        <span class="metric-card__val">$1,248,200</span>
        <span class="metric-card__trend">↑ 12.4%</span>
      </div>
    </article>

    <article class="metric-card">
      <h4 class="metric-card__title">Compute Latency</h4>
      <div class="metric-card__body">
        <span class="metric-card__val">14.2 ms</span>
        <span class="metric-card__trend">↓ 2.1%</span>
      </div>
    </article>

    <article class="metric-card">
      <h4 class="metric-card__title">System Availability</h4>
      <div class="metric-card__body">
        <span class="metric-card__val">99.995%</span>
        <span class="metric-card__trend">0.0%</span>
      </div>
    </article>
  </section>
</body>
</html>
```

Eksekusi build dan render:
```bash
npm run build:tokens
npm run serve
```
Buka browser pada port yang dialokasikan, periksa *Elements Inspector* -> *Styles* tab, amati bagaimana browser memetakan `@layer`, mengonsumsi variabel, dan menyesuaikan ukuran elemen berdasarkan *Container Queries* bukan *Viewport*.

---

### 13. Exercise

Lakukan pemecahan masalah teknis berikut secara mandiri:

#### Level Easy
Buat layer kustom bernama `@layer overrides.hotfix;` di bagian paling akhir deklarasi layer. Gunakan class biasa tanpa ID atau tanpa `!important` untuk menimpa warna teks `.metric-card__val` menjadi warna ungu (`rebeccapurple`). Buktikan bahwa layer baru selalu menang atas deklarasi `@layer components`.

#### Level Medium
Ubah skrip kompilasi `build-tokens.js` agar mendukung format token multi-tema (*light* dan *dark*). Hasilkan file CSS yang secara otomatis memetakan variabel tema gelap di dalam blok `[data-theme="dark"]` yang dibungkus oleh `@layer design-system.tokens`.

#### Level Hard
Refaktor layout `metric-card` untuk menggunakan CSS Subgrid murni pada 3 tingkat kedalaman:
1. `metric-grid-host` (Grid 12-kolom utama)
2. `metric-card` (Subgrid dari induk)
3. `metric-card__body` (Subgrid dari `metric-card`)
Pastikan teks desimal dan satuan ukuran di dalam `.metric-card__body` selalu sejajar secara vertikal lintas seluruh kartu dalam satu baris grid, tanpa menggunakan properti `min-width` atau script kalkulasi tinggi DOM.

---

### 14. Challenge

**Skenario Misi-Kritis**: Anda memimpin tim rekayasa CSS untuk aplikasi terminal perdagangan saham finansial tinggi (*high-frequency trading platform*). Data pada tabel transaksi diperbarui via WebSocket sebanyak 60 kali per detik (60 FPS) dengan 10.000 baris DOM node.

**Persyaratan Tantangan**:
1. Buat arsitektur CSS untuk tabel data tersebut di mana *Recalculate Style* dan *Paint Operations* dibatasi secara presisi di tingkat baris/sel tanpa memicu *Composite/Layout Invalidation* ke seluruh halaman.
2. Gunakan CSS Containment (`contain`), `content-visibility`, dan hardware accelerated properties.
3. Total latensi thread utama per pembaruan DOM tidak boleh melebihi **1.2ms** pada saat pengujian performa Chrome DevTools Performance Profiler.
4. Rancang fallback elegan (*graceful degradation*) jika user membuka antarmuka pada peramban legasi yang belum mendukung *containment API*.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Bagaimana urutan prioritas pemenang resolusi cascade antara dua layer berikut jika target elemen memiliki class yang sama?**
   `@layer framework { .btn { color: red; } }`
   `@layer custom { .btn { color: blue; } }`
   Dengan inisialisasi: `@layer framework, custom;`
   - A. Merah, karena dideklarasikan pertama kali.
   - B. Biru, karena layer `custom` berada di urutan setelah `framework`.
   - C. Tergantung jumlah selector anak.
   - D. Berimbang dan menyebabkan error CSSOM parser.

2. **Apa yang terjadi bila selektor tanpa layer dideklarasikan bersamaan dengan selektor di dalam `@layer`?**
   - A. Selektor di dalam `@layer` selalu menang.
   - B. Gaya unlayered (tanpa layer) selalu memiliki prioritas tertinggi di atas semua gaya yang berada di dalam layer normal.
   - C. Browser mengabaikan gaya unlayered.
   - D. Mengikuti aturan spesifisitas standar $Specificity(a,b,c)$.

3. **Properti `container-type: inline-size` pada CSS Container Queries memerintahkan peramban untuk memantau perubahan pada:**
   - A. Sumbu horizontal (lebar) kontainer saja.
   - B. Sumbu vertikal (tinggi) kontainer saja.
   - C. Sumbu horizontal dan vertikal secara simultan.
   - D. Ukuran total viewport jendela peramban.

4. **Karakteristik penting dari CSS Containment `contain: paint` adalah:**
   - A. Melarang elemen turunan untuk mengubah warna teks.
   - B. Menjamin bahwa anak dari elemen tersebut tidak akan pernah dicat di luar kotak pembatasnya (*bounding box*).
   - C. Memaksa peramban merender elemen di thread GPU sekunder.
   - D. Menghapus properti background pada elemen root.

5. **Token berjenis *Semantic Token* idealnya merujuk langsung kepada:**
   - A. Komponen HTML spesifik (misal: Button, Card).
   - B. Nilai pixel/hex mentah secara langsung.
   - C. Primitive/Global Token.
   - D. Aturan `@media` query.

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Perhatikan deklarasi berikut:**
   ```css
   @layer alpha {
     #nav a { color: red !important; }
   }
   @layer beta {
     .link { color: blue !important; }
   }
   ```
   Jika urutan layer adalah `@layer alpha, beta;`, warna apa yang akan dirender oleh link `#nav a.link`?
   - A. Biru, karena layer `beta` berada setelah layer `alpha`.
   - B. Merah, karena aturan `!important` membalikkan prioritas urutan layer normal.
   - C. Ungu (campuran keduanya).
   - D. Tergantung apakah peramban berbasis WebKit atau Blink.

7. **Mengapa penggunaan CSS Subgrid (`grid-template-columns: subgrid`) jauh lebih unggul dalam menjaga performa Core Web Vitals (khususnya CLS) dibandingkan perataan kolom via JavaScript MutationObserver?**
   - A. Subgrid berjalan di proses render terpisah dari CSSOM.
   - B. Subgrid dihitung secara serentak dalam fase Layout engine browser sebelum frame pertama dicat, mencegah koreksi layout susulan (*layout shifting*).
   - C. JavaScript MutationObserver sepenuhnya diblokir oleh ad-blocker.
   - D. Subgrid tidak memerlukan alokasi memori RAM.

8. **Apa fungsi utama dari deklarasi `contain-intrinsic-size` saat dipasangkan dengan `content-visibility: auto`?**
   - A. Menentukan memori buffer kartu grafis.
   - B. Menyediakan dimensi placeholder estimasi (lebar/tinggi) untuk elemen saat sedang tidak dirender di off-screen, mencegah scrollbar melompat (*scrollbar jitter*).
   - C. Mengatur batas rasio kontras warna secara otomatis.
   - D. Membatasi ukuran DOM node agar tidak melebihi 1500 elemen.

9. **Manakah dari strategi berikut yang paling efektif untuk meminimalisasi *Style Invalidation* global saat memanipulasi class menggunakan JavaScript?**
   - A. Menambahkan class pada elemen `<body>` secara berulang.
   - B. Menerapkan isolasi via CSS Containment (`contain: layout style`) pada kontainer pembungkus komponen tersebut.
   - C. Menggunakan selector universal `*` untuk me-reset state elemen.
   - D. Mengganti semua properti CSS dengan atribut `style` inline.

10. **Dalam arsitektur Micro-Frontend, bagaimana cara termutakhir untuk mencegah benturan nama class tanpa bergantung pada teknik CSS-in-JS hashing?**
    - A. Menyematkan seluruh CSS di dalam atribut `style` masing-masing tag HTML.
    - B. Mengenkapsulasi CSS masing-masing Micro-Frontend ke dalam sub-layer terisolasi (`@layer mfeA.components`, `@layer mfeB.components`).
    - C. Mewajibkan developer menggunakan ID selector unik 64-karakter.
    - D. Menghapus penggunaan file CSS eksternal.

#### Bagian 3: Skenario Kasus Produksi (3 Kasus)
11. **Skenario 1**: Tim Anda mengintegrasikan widget obrolan (*Chat Widget*) pihak ketiga ke dalam platform e-commerce enterprise. Stylesheet widget tersebut menggunakan selector agresif seperti `div { box-sizing: content-box; }` yang merusak layout keranjang belanja Anda. Bagaimana cara mengatasinya secara elegan tanpa memodifikasi kode sumber pihak ketiga dan tanpa menggunakan `!important` massal?
12. **Skenario 2**: Pada pengujian audit performa di perangkat Android kelas bawah, ditemukan bahwa saat pengguna melakukan scrolling cepat pada halaman katalog produk yang memiliki 5.000 item, FPS drop drastis dari 60 FPS ke 12 FPS (*Jank*). DevTools mencatat *Recalculate Style* dan *Paint* memakan waktu 45ms per frame. Langkah arsitektur CSS presisi apa yang harus diterapkan?
13. **Skenario 3**: Sebuah institusi finansial mengharuskan portal perbankan mereka mendukung 5 anak perusahaan dengan 5 palet warna berbeda, serta mode gelap (*Dark Mode*) untuk masing-masing perusahaan. Jelaskan skema struktur hierarki CSS Custom Properties yang dapat menangani total 10 variasi tema ini tanpa menduplikasi aturan deklarasi styling komponen inti!

---

#### Kunci Jawaban & Pembahasan Quiz

##### Bagian 1: Basic
1. **B**: Pada deklarasi normal, urutan pendaftaran layer menentukan prioritas: layer yang didaftarkan belakangan (`custom`) mengalahkan layer sebelumnya (`framework`).
2. **B**: Elemen unlayered selalu diposisikan pada prioritas tertinggi di atas semua layer yang dibuat, memastikan kompatibilitas mundur dengan CSS warisan (*legacy*).
3. **A**: `inline-size` secara spesifik menginstruksikan kalkulasi peramban untuk hanya merespons perubahan ukuran pada sumbu horizontal dalam mode penulisan teks default (*horizontal writing-mode*).
4. **B**: `contain: paint` memastikan bahwa tidak ada elemen visual (seperti child dengan absolute position atau box-shadow luas) yang dicat di luar batas *clipping rectangle* induknya.
5. **C**: *Semantic tokens* (contoh: `--color-bg-primary`) memetakan tujuan fungsi ke *Primitive tokens* (contoh: `--palette-blue-500`) sebelum dikonsumsi oleh token komponen.

##### Bagian 2: Intermediate
6. **B**: Aturan `!important` membalikkan hierarki cascade layer. Layer terbawah/paling awal didaftarkan (`alpha`) menjadi layer dengan otoritas tertinggi untuk deklarasi yang memiliki `!important`.
7. **B**: Eksekusi CSS Native Subgrid terikat langsung dalam tahapan C++ layout engine peramban, berjalan sebelum frame layout pertama disajikan, sehingga tidak ada jeda perhitungan (*zero layout shift*).
8. **B**: Ketika `content-visibility: auto` mematikan rendering elemen off-screen, ukurannya berubah menjadi 0x0 secara internal jika tidak diberi dimensi; `contain-intrinsic-size` memberikan dimensi bayangan yang presisi agar scrollbar halaman tetap stabil.
9. **B**: Penyekatan menggunakan `contain: layout style` memotong jalur penjalaran invalidasi rekalkulasi gaya, sehingga peramban hanya mengevaluasi subtree lokal elemen tersebut.
10. **B**: `@layer` memungkinkan isolasi hak prioritas dan pengelompokan gaya dari modul yang berbeda secara native di tingkat browser engine tanpa overhead hashing kompilasi string class.

##### Bagian 3: Skenario Kasus Produksi
11. **Solusi Skenario 1**:
    Bungkus seluruh stylesheet pihak ketiga tersebut ke dalam layer prioritas terendah saat mengimpornya:
    ```css
    @import url("third-party-widget.css") layer(vendor-legacy);
    ```
    Karena layer buatan tim internal (misal: `@layer base, components;`) didefinisikan setelah `vendor-legacy`, maka seluruh aturan selektor internal aplikasi Anda akan secara mutlak mengalahkan selektor liar milik pihak ketiga tanpa perlu menaikkan spesifisitas selektor maupun menggunakan `!important`.

12. **Solusi Skenario 2**:
    Terapkan teknik *Modern Virtual Scrolling Isolation* murni berbasis CSS:
    ```css
    .product-card {
      content-visibility: auto;
      contain-intrinsic-size: auto 320px; /* Estimasi tinggi kartu */
      contain: layout paint style;
    }
    ```
    Ini akan menghentikan rendering untuk sekitar 4.980 kartu yang berada di luar viewport, mereduksi konsumsi memori GPU dan memangkas waktu *Recalculate Style* dari 45ms menjadi < 2ms per frame, mengembalikan stabilitas scrolling ke 60 FPS.

13. **Solusi Skenario 3**:
    Terapkan pemisahan token 2 dimensi (Brand Layer & Theme Mode Layer):
    1. Komponen hanya membaca variabel semantik: `background: var(--surface-primary)`.
    2. Pisahkan token Brand Primitif ke dalam data atribut perusahaan:
       ```css
       [data-brand="subsidiary-a"] { --brand-hue: 210; }
       [data-brand="subsidiary-b"] { --brand-hue: 140; }
       ```
    3. Hubungkan pemetaan Semantik ke variabel Hue dinamis dengan dukungan Color Spaces (OKLCH):
       ```css
       :root, [data-theme="light"] {
         --surface-primary: oklch(0.95 0.05 var(--brand-hue));
       }
       [data-theme="dark"] {
         --surface-primary: oklch(0.20 0.05 var(--brand-hue));
       }
       ```
    Ini memungkinkan 10 variasi tema berjalan secara otomatis hanya dengan kombinasi atribut `<html data-brand="subsidiary-b" data-theme="dark">` tanpa penambahan satu baris pun kode komponen baru.

---

### 16. Summary

1. **Arsitektur Skala Besar Memerlukan Kontrak Deterministik**: Skalabilitas CSS pada tingkat enterprise tidak lagi bergantung pada kepatuhan penamaan class manual (BEM), melainkan pada sistem deterministik yang dikontrol oleh mesin build (Design Token Engine) dan native runtime engine (`@layer`).
2. **Kedaulatan Cascade Layers (`@layer`)**: Memisahkan spesifisitas selektor dari hak prioritas cascade. Urutan deklarasi layer menentukan segalanya, memberikan perlindungan mutlak terhadap benturan kode pada integrasi Micro-Frontends.
3. **Hardware-Aware Rendering**: Pemanfaatan fitur modern seperti CSS Subgrid, Container Queries, dan CSS Containment (`contain`, `content-visibility`) menggeser beban komputasi layout dari eksekusi JavaScript yang rawan layout thrashing kembali ke engine rendering native browser yang terakselerasi secara optimal.
4. **Zero-Runtime Overhead adalah Standar Baru**: Mengurangi penggunaan library CSS-in-JS dinamis demi mengeliminasi pemblokiran main-thread. Pengalihan tema secara instan dicapai melalui rekonfigurasi CSS Custom Properties yang dipetakan secara matematis dalam palet ruang warna modern (OKLCH).