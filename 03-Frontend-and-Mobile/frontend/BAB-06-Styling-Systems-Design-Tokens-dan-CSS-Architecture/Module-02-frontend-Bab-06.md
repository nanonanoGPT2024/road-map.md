# BAB 06: Styling Systems, Design Tokens, & CSS Architecture
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang Arsitektur Design Tokens Skala Enterprise**: Mengimplementasikan spesifikasi W3C Design Tokens Community Group (DTCG) menggunakan *multi-tier token architecture* (Global/Primitive, Semantic/Alias, dan Component Tokens) yang mendukung multi-brand, multi-platform, dan *dark/high-contrast mode*.
- **Menganalisis dan Mengoptimalkan Pipeline Render Engine Browser**: Menghilangkan *layout thrashing*, meminimalkan *Style Recalculation cost* ($O(N \times M)$ selector matching), serta mengisolasi layout dan paint boundary memanfaatkan CSS Containment (`contain`, `content-visibility`) dan sub-pixel rendering mechanics.
- **Menguasai Cascade Layers (`@layer`) & Container Queries (`@container`)**: Membangun orkestrasi spesifisitas deterministik tanpa *hack* `!important` serta merancang UI adaptif berbasis dimensi *viewport parent* (Intrinsic Design).
- **Mengevaluasi & Mengimplementasikan Zero-Runtime CSS Engine**: Membangun *styling pipeline* berbasis AST transformer (seperti Vanilla Extract atau StyleX) untuk menghilangkan *runtime overhead* CSS-in-JS warisan (Emotion/Styled-Components) pada aplikasi Next.js/RSC (*React Server Components*).
- **Menyusun Strategi Isolasi CSS untuk Arsitektur Micro-Frontend**: Mencegah *style bleed* lintas tim independen menggunakan Shadow DOM, CSS Scoping, CSS Modules bermutasi hash, dan *layered namespaces*.

---

### 2. Prerequisites
Sebelum mendalami modul ini, Anda wajib menguasai:
- **DOM & CSSOM Tree Construction**: Siklus *Critical Rendering Path* (DOM + CSSOM $\to$ Render Tree $\to$ Layout/Reflow $\to$ Paint $\to$ Composite).
- **AST (Abstract Syntax Tree) Transformations**: Pemahaman dasar PostCSS/Babel/SWC parser untuk pemrosesan file CSS/JS.
- **TypeScript Tingkat Lanjut**: Penggunaan *Template Literal Types*, *Mapped Types*, dan *Const Assertions* untuk *type-safe design tokens*.
- **Bundler Tooling**: Konfigurasi loader dan plugin pada Vite, Webpack, atau Rspack.

---

### 3. Concept & Internal Architecture

#### A. W3C Design Tokens Community Group (DTCG) & Multi-Tier Token Hierarchy
Sistem token enterprise memisahkan dependensi antara representasi visual mentah dan semantik aplikasi. Struktur data disusun dalam tiga tier hierarki:

```
[ Tier 1: Global / Primitive Tokens ]
  - Nilai absolut: Hex, Rem, Number (e.g., color.blue.500: #0070F3)
                   │
                   ▼
[ Tier 2: Semantic / System Tokens ]
  - Menentukan intent & konteks (e.g., color.interactive.primary: {color.blue.500})
  - Mendukung contextual switching: Light, Dark, High-Contrast, Brand A, Brand B
                   │
                   ▼
[ Tier 3: Component-Scoped Tokens ]
  - Variabel terisolasi per komponen (e.g., button.primary.bg: {color.interactive.primary})
```

Format standar W3C DTCG menggunakan properti `$value` dan `$type`:

```json
{
  "color": {
    "brand": {
      "primary": {
        "$value": "#0052cc",
        "$type": "color",
        "$description": "Core brand identity color"
      }
    }
  }
}
```

Pipeline transformasi (menggunakan tools seperti Style Dictionary v4) mem-parsing AST token JSON tersebut, memvalidasi dependensi sirkular via *Directed Acyclic Graph* (DAG), melakukan *token aliasing resolution*, lalu mengekspor output platform-spesifik: CSS Custom Properties, SCSS Maps, TypeScript types, iOS Swift Structs, dan Android XML/Jetpack Compose classes.

#### B. Internal Browser Engine: CSSOM, Layout Tree, dan Selector Matching
Untuk menulis CSS berkinerja tinggi, kita harus memahami algoritma evaluasi engine browser (misal: Blink/Chromium):
1. **Right-to-Left (RTL) Selector Evaluation**:
   Ketika browser membaca `.card .actions button.primary`, parsing dimulai dari kanan:
   - Evaluasi semua elemen `button.primary` di halaman (*Key Selector*).
   - Telusuri ancestor untuk mencari `.actions`.
   - Telusuri ancestor lebih tinggi untuk mencari `.card`.
   *Imbas performa*: Key selector yang terlalu umum (misal: `div *` atau `.container span`) memaksa browser melakukan traversal DOM tree yang masif.
2. **Invalidation Invariants & Recalculate Style**:
   Setiap mutasi DOM atau class memicu penandaan node sebagai *dirty*. Browser harus menghitung ulang Computed Style. Kompleksitas penentuan style adalah $O(N \times M)$ di mana $N$ adalah jumlah elemen yang terdampak dirty bit dan $M$ adalah jumlah rule CSS yang relevan.
3. **Paint & Layout Containment**:
   CSS `contain: layout paint size style;` secara eksplisit memberi tahu engine layout browser:
   - Perubahan geometri di dalam kontainer tidak akan memicu reflow pada ancestor.
   - Elemen di dalam kontainer tidak akan menggambar di luar batas (*paint clipping boundary*).

#### C. Deterministic Cascade: Cascade Layers (`@layer`)
Cascade Resolution Algorithm standar CSS mengevaluasi aturan berdasarkan urutan:
$$\text{Importance} \to \text{Origin (User Agent/User/Author)} \to \text{Cascade Layers} \to \text{Specificity} \to \text{Order of Appearance}$$

Sebelum `@layer`, arsitektur CSS mengandalkan metodologi BEM atau konvensi penamaan agar tidak kalah oleh spesifisitas pihak ketiga. Dengan `@layer`, urutan deklarasi layer menentukan prioritas:

```css
@layer reset, base, components, utilities;

@layer utilities {
  .hidden { display: none; } /* Layer tertinggi, selalu menang atas components */
}

@layer components {
  /* Spesifisitas ID (#btn) di components TETAP kalah dari class (.hidden) di utilities */
  #submit-btn { display: inline-flex; }
}
```

---

### 4. Why & What

| Dimensi | Legacy Styling (Runtime CSS-in-JS / Unlayered SCSS) | Modern Enterprise Styling (Tokens + Zero-Runtime + Modern CSS) |
| :--- | :--- | :--- |
| **Runtime Overhead** | Dynamic `<style>` injection, JSON hashing di JavaScript thread, memory leaks akibat unmemoized dynamic props. | Zero runtime footprint. CSS diekstraksi ke file `.css` statis saat waktu kompilasi (*ahead-of-time*). |
| **Specificity Wars** | Bergantung pada BEM konvensional, selektor chained (`.card.active > div:first-child`), atau `!important`. | Spesifisitas terprediksi melalui `@layer`. Reset/vendors tidak pernah menimpa utility atau core logic. |
| **Theming Mechanics** | React Context provider menyebabkan re-render seluruh children tree saat tema berubah. | CSS Custom Properties di-swap via `data-theme` attribute pada root. Zero React re-renders. |
| **Responsive Model** | Media queries berbasis layar (Global Viewport) yang merusak konsep modularitas micro-frontend. | Container Queries (`@container`) memvalidasi layout berdasarkan ukuran host wrapper komponen itu sendiri. |
| **Type Safety** | Tipe string primitif tak tervalidasi (`padding: "16px"` tanpa kontrak baku). | Full TypeScript autocompletion dan compile-time contract enforcement untuk semua tokens. |

---

### 5. How: Workflow Detail

Diagram arsitektur alur kerja produksi:

```
[Design Tool: Figma Variables]
            │
            ▼ (Sync via GitHub Action / Webhook)
[Raw Tokens Repository: JSON DTCG Spec]
            │
            ▼
[Engine Transform: Style Dictionary v4 + Custom AST Parser]
     ├──────────────────────────┬──────────────────────────┐
     ▼                          ▼                          ▼
(CSS Custom Properties)     (TypeScript AST)       (Platform Targets)
 (tokens.vars.css)           (tokens.d.ts)       (Android / iOS / JSON)
     │                          │
     └───────────┬──────────────┘
                 ▼
[Compile-Time Styling Engine (Vanilla Extract / StyleX)]
                 │
                 ▼ (Bundler: Vite / Rspack)
   ┌─────────────┴─────────────┐
   ▼                           ▼
[Chunked Static CSS Files]   [Tree-shaken Component JS]
 (Optimized via LightningCSS)  (Zero Style Runtime)
```

1. **Token Ingestion**: Designer mengubah variabel di Figma; plugin mengekspor format JSON terstandarisasi DTCG ke repositori token.
2. **Deterministic Token Transformation**: Style Dictionary mengomputasi referensi relasional (resolusi alias `{color.brand.primary}` $\to$ `#0052cc`).
3. **Multi-Target Code Generation**:
   - Menghasilkan token bertipe kuat (`.d.ts`) untuk komponen UI.
   - Menghasilkan CSS custom properties yang dikelompokkan ke `@layer base.tokens`.
4. **Compile-Time Extraction**: Komponen mengimpor kontrak token melalui *Zero-Runtime CSS engine*. Saat kompilasi, seluruh kalkulasi CSS diekstrak menjadi stylesheet statis monolitik yang dioptimasi oleh *LightningCSS* (deduplikasi class, kalkulasi `calc()` konstan, dan vendor prefixing otomatis).
5. **Runtime Delivery**: Aplikasi client menerima CSS statis murni yang di-cache di CDN Edge. Perubahan tema dijalankan seketika via DOM dataset mutation tanpa runtime overhead.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem Tenaga Listrik Multi-Brand
Arsitektur token dapat dianalogikan dengan **Pembangkit Listrik dan Gardu Distribusi**:
- **Primitive Tokens (Pembangkit Listrik)**: Tegangan mentah 500kV (warna mentah, font-size mentah). Tidak aman dicolok langsung ke peralatan rumah.
- **Semantic Tokens (Gardu Distribusi / Trafo)**: Menurunkan daya menjadi 220V untuk perumahan atau 380V untuk industri (`surface.background.default`, `text.color.primary`). Menentukan peruntukan.
- **Component Tokens (Sirkuit Stop Kontak Khusus)**: Soket khusus oven microwave atau AC (`button.primary.bg`). Jika AC butuh daya cadangan (Dark Mode), gardu distribusi mengubah jalurnya tanpa mengganti seluruh kabel rumah.

#### Diagram Internal Browser Style Resolution
```
                    HTML Parsing          CSS Parsing
                         │                     │
                         ▼                     ▼
                      [ DOM ]              [ CSSOM ]
                         │                     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                    [ Selector Matching Engine ]
                    (Evaluasi Right-to-Left RTL)
                    (Resolusi @layer Specifity)
                                    │
                                    ▼
                          [ Render Tree ]
                       (Computed Styles Ready)
                                    │
             ┌──────────────────────┴──────────────────────┐
             │ CSS Containment Activated?                  │
             │ [ contain: layout paint ]                   │
             ▼                                             ▼
    (Full Page Reflow)                           (Subtree Isolated Reflow)
  Recalculate 10.000 Nodes                         Recalculate 5 Nodes
             │                                             │
             └──────────────────────┬──────────────────────┘
                                    │
                                    ▼
                        [ Layout (Reflow) Engine ]
                         (Geometri: x, y, w, h)
                                    │
                                    ▼
                         [ Paint & Rasterize ]
                        (Draw Calls, Skia/Ganesh)
                                    │
                                    ▼
                          [ Compositor GPU ]
                        (Transform & Opacity)
```

---

### 7. Implementation: Simple vs Practical

#### A. Simple Example (Konsep Dasar DTCG & Modern CSS Native)
File konfigurasi token manual dan implementasi modern CSS:

```css
/* tokens.css */
@layer base {
  :root {
    --color-primitive-blue-500: #0284c7;
    --color-primitive-slate-900: #0f172a;
    
    /* Semantic mapping */
    --color-surface-base: #ffffff;
    --color-text-primary: var(--color-primitive-slate-900);
    --color-interactive-brand: var(--color-primitive-blue-500);
  }

  [data-theme="dark"] {
    --color-surface-base: var(--color-primitive-slate-900);
    --color-text-primary: #f8fafc;
    --color-interactive-brand: #38bdf8;
  }
}

@layer layout {
  .card-container {
    container-type: inline-size;
    container-name: cardWrapper;
  }
}

@layer components {
  .product-card {
    background-color: var(--color-surface-base);
    color: var(--color-text-primary);
    contain: layout paint;
    display: flex;
    flex-direction: column;
    padding: 1rem;
  }

  /* Intrinsic Responsive Design tanpa Media Query Viewport */
  @container cardWrapper (min-width: 450px) {
    .product-card {
      flex-direction: row;
      gap: 1.5rem;
    }
  }
}
```

#### B. Practical Example (Production-Ready: Style Dictionary + Vanilla Extract)

##### 1. W3C DTCG Token Definitions (`tokens/design-tokens.json`)
```json
{
  "sys": {
    "color": {
      "brand": {
        "primary": {
          "$value": "#0d6efd",
          "$type": "color"
        }
      },
      "surface": {
        "canvas": {
          "$value": "#ffffff",
          "$type": "color"
        }
      }
    },
    "space": {
      "sm": { "$value": "8px", "$type": "dimension" },
      "md": { "$value": "16px", "$type": "dimension" },
      "lg": { "$value": "24px", "$type": "dimension" }
    }
  }
}
```

##### 2. Custom Token Pipeline Parser (`scripts/build-tokens.ts`)
```typescript
import StyleDictionary from 'style-dictionary';
import type { Config } from 'style-dictionary/types';

const config: Config = {
  source: ['tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'src/styles/generated/',
      files: [
        {
          destination: 'tokens.vars.css',
          format: 'css/variables',
          options: {
            outputReferences: true,
            selector: ':root'
          }
        }
      ]
    },
    typescript: {
      transforms: ['name/camel'],
      buildPath: 'src/styles/generated/',
      files: [
        {
          destination: 'tokens.ts',
          format: 'javascript/es6'
        }
      ]
    }
  }
};

const sd = new StyleDictionary(config);
await sd.buildAllPlatforms();
console.log('✅ Tokens deterministically transformed for Web & TS');
```

##### 3. Zero-Runtime Component System (`src/components/Card.css.ts`)
Menggunakan **Vanilla Extract** yang menghasilkan CSS murni pada *build-time*:

```typescript
import { createGlobalTheme, style, createContainer } from '@vanilla-extract/css';

// Deklarasi Container
export const cardContainer = createContainer();

// Kontrak Theme Variabel
export const vars = createGlobalTheme(':root', {
  color: {
    brandPrimary: 'var(--sys-color-brand-primary)',
    surfaceCanvas: 'var(--sys-color-surface-canvas)',
  },
  space: {
    sm: 'var(--sys-space-sm)',
    md: 'var(--sys-space-md)',
    lg: 'var(--sys-space-lg)',
  }
});

export const containerStyle = style({
  containerName: cardContainer,
  containerType: 'inline-size',
  width: '100%',
});

export const cardStyle = style({
  backgroundColor: vars.color.surfaceCanvas,
  padding: vars.space.md,
  borderRadius: '8px',
  display: 'flex',
  flexDirection: 'column',
  contain: 'layout paint',
  transition: 'transform 150ms cubic-bezier(0, 0, 0.2, 1)',
  willChange: 'transform',

  '@container': {
    [`${cardContainer} (min-width: 400px)`]: {
      flexDirection: 'row',
      alignItems: 'center',
      padding: vars.space.lg,
    }
  },

  ':hover': {
    transform: 'translateY(-2px)'
  }
});
```

##### 4. React Server Component Integration (`src/components/Card.tsx`)
```tsx
import React, { FC, ReactNode } from 'react';
import { containerStyle, cardStyle } from './Card.css';

interface CardProps {
  children: ReactNode;
}

export const Card: FC<CardProps> = ({ children }) => {
  return (
    <section className={containerStyle}>
      <div className={cardStyle}>
        {children}
      </div>
    </section>
  );
};
```

---

### 8. Real World Case Study: Multi-Brand FinTech SuperApp

#### Skenario Arsitektur
Sebuah institusi perbankan global memiliki satu *core platform codebase* yang harus menyediakan antarmuka untuk 3 anak usaha:
1. **Retail Banking**: Tema biru, border rounded tinggi, layout rapat (*compact*).
2. **Corporate Wealth**: Tema hitam/emas, tanpa border radius, layout lega (*spacious*).
3. **Neo-Bank (Gen-Z)**: Tema ungu cerah, font monospaced, dark-mode default.

#### Masalah Utama
Penggunaan runtime styled-components sebelumnya menghasilkan:
- File bundel JavaScript bengkak sebesar 850KB hanya untuk runtime CSS string interpolator.
- First Contentful Paint (FCP) mencapai **3.8 detik** pada perangkat entry-level Android.
- Masalah spesifisitas CSS pada sistem micro-frontend di mana widget Corporate Wealth menimpa style form Retail Banking saat navigasi SPA dilakukan tanpa refresh.

#### Solusi Implementasi
1. **Dynamic Token Swapping tanpa Runtime Re-renders**:
   Pemisahan semantic layer via atribut `data-brand` pada level root HTML tag:

```css
/* brand-themes.css */
@layer theme.primitive, theme.brand;

@layer theme.brand {
  :root[data-brand="retail"] {
    --sys-color-primary: #0047cc;
    --sys-radius-base: 12px;
    --sys-density-spacing: 8px;
  }

  :root[data-brand="corporate"] {
    --sys-color-primary: #d4af37;
    --sys-radius-base: 0px;
    --sys-density-spacing: 16px;
  }

  :root[data-brand="neobank"] {
    --sys-color-primary: #7928ca;
    --sys-radius-base: 24px;
    --sys-density-spacing: 12px;
  }
}
```

2. **Micro-Frontend Cascade Isolation**:
   Setiap Micro-App dimuat ke dalam `@layer` unik untuk menggaransi bahwa urutan inject tidak merusak cascading tree aplikasi host:

```css
@layer host, mfe-accounts, mfe-investments, mfe-transfers;

/* MFE Investments styles */
@layer mfe-investments {
  .btn-submit {
    /* Hanya bersaing dalam layer 'mfe-investments' */
    background: var(--sys-color-primary);
  }
}
```

#### Hasil Metrik Produksi
- **JavaScript Execution Time**: Berkurang dari 1.2 detik ke **0 ms** (menghapus runtime CSS-in-JS).
- **FCP (First Contentful Paint)**: Turun drastis dari 3.8s menjadi **0.9s** (skor Lighthouse 100/100 pada sub-metrik visual).
- **CSS Bundle Size**: 90KB gzipped diekstrak secara statis, dengan 95% *cache hit ratio* di seluruh domain multi-brand.

---

### 9. Trade-offs: Architectural Decision Matrix

| Kriteria | Native CSS Modules + Design Tokens | Zero-Runtime (StyleX / Vanilla Extract) | Utility Engine (Tailwind CSS v4) | Runtime CSS-in-JS (Emotion / Styled-Components) |
| :--- | :--- | :--- | :--- | :--- |
| **Runtime Overhead** | Zero (Murni file CSS statis) | Zero (Ekstraksi kompilasi via Babel/Vite) | Zero (Compiler JIT menghasilkan CSS murni) | **Tinggi** (JS engine hashing, CSSOM dynamic injection) |
| **Type-Safety Contract** | Rendah (Kecuali menggunakan `typed-css-modules`) | **Sangat Tinggi** (TypeScript-first API, autocomplete ketat) | Parsial (Via class completion ekstensi IDE) | Tinggi (Props-based typing) |
| **RSC Compatibility** | **Penuh** | **Penuh** | **Penuh** | **Buruk** (Memerlukan client boundary context) |
| **Build-Time Cost** | Sangat Cepat ($O(1)$ transfer langsung) | Sedang (Perlu transpilasi AST tambahan) | Cepat (Berbasis Rust/LightningCSS engine) | Sangat Cepat (Karena parsing ditunda ke runtime) |
| **Bundle Scalability** | Bertambah linier ($O(N)$) seiring bertambahnya komponen | Bertambah linier ($O(N)$), namun dapat dioptimalkan via Atomic extraction | **Asimtotik Datar ($O(1)$)**; mentok di plafon CSS utilitas statis | Bertambah di bundel JS ($O(N)$) |
| **Dynamic Theming** | Sangat Fleksibel (CSS Variable reassignment) | Sangat Fleksibel (CSS Variable mapping) | Fleksibel (Melalui theme CSS variables) | Ekstrem (Bisa menginjeksi kalkulasi fungsi JS sembarang) |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: Layout Thrashing Akibat Trigger Reflow di Loop Animasi
*Penyebab*: Membaca geometri DOM (`offsetHeight`, `clientWidth`) lalu menulis property layout (`style.width`, `style.top`) berulang kali, memaksa browser melakukan *Synchronous Layout Evaluation*.

*Solusi*:
```typescript
// ❌ BURUK: Membaca & menulis menyebabkan Layout Thrashing
elements.forEach(el => {
  const height = el.getBoundingClientRect().height; // READ (Force Layout)
  el.style.height = `${height + 10}px`;            // WRITE (Invalidate)
});

// ✅ BENAR: Gunakan Compositor properties & CSS Containment
// style.css
.animated-card {
  contain: layout paint;
  will-change: transform;
  transition: transform 200ms ease;
}

// script.ts
// Animasi digerakkan via GPU Transform tanpa memicu layout tree recalculation
requestAnimationFrame(() => {
  elements.forEach((el, idx) => {
    el.style.transform = `translateY(${idx * 10}px)`;
  });
});
```

#### Kasus 2: FOUC (Flash of Unstyled Content) saat Theme Swap
*Penyebab*: Theme CSS Variables diset via JavaScript di dalam event listener `useEffect` React, menyebabkan browser me-render frame pertama dengan tema default/fallback sebelum JavaScript selesai dieksekusi.

*Solusi*:
Injeksi *blocking inline script* sinkron tepat di atas tag `<body>` (atau di root HTML document):
```html
<head>
  <!-- CSS Statis Utama Dimuat Di Sini -->
  <link rel="stylesheet" href="/assets/tokens.vars.css" />
</head>
<body>
  <script>
    (function() {
      // Baca preferensi lokal sebelum render pertama dipicu oleh browser
      const savedTheme = localStorage.getItem('app-theme') || 
        (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      document.documentElement.setAttribute('data-theme', savedTheme);
    })();
  </script>
  <div id="root"></div>
</body>
```

#### Kasus 3: Penyalahgunaan `will-change` Menyebabkan VRAM Starvation
*Penyebab*: Menerapkan `will-change: transform, opacity;` pada ribuan elemen list atau universal selector `*`. Browser mengalokasikan *GPU Layer Bitmap Memory* terpisah untuk setiap elemen.

*Solusi*:
Terapkan `will-change` secara dinamis sesaat sebelum animasi berjalan dan hapus setelah selesai:
```typescript
const handleMouseEnter = (e: HTMLElement) => {
  e.style.willChange = 'transform';
};

const handleAnimationEnd = (e: HTMLElement) => {
  e.style.willChange = 'auto'; // Release GPU buffer backing store
};
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Token Naming Convention**: Terapkan format CTI (*Category-Type-Item*) konsisten: `sys.color.background.interactive.hover`.
- [ ] **Enforce `@layer` Hierarchy**: Definisikan layer hierarchy di baris paling pertama file root CSS:
  ```css
  @layer reset, base, design-system, components, overrides;
  ```
- [ ] **Hindari Dynamic String Interpolation pada CSS**: Jangan pernah membuat class generator berbasis JS runtime yang menghalangi ekstraksi statis bundler:
  ```typescript
  // ❌ BURUK: Bundler tidak bisa menganalisis class dinamis ini
  const getClassName = (color: string) => `btn-${color}`;
  ```
- [ ] **Gunakan Modern Units**: Ganti penggunaan `px` statis untuk responsive spacing ke `rem`, `ch`, dan dynamic viewport units (`svh`, `dvh`, `cqw`).
- [ ] **Aktifkan Containment pada List Items**: Gunakan `content-visibility: auto;` dan `contain-intrinsic-size` pada virtualization container untuk menghemat hingga 80% rendering work pada layout DOM berukuran besar.
- [ ] **Linting & AST Guard**: Integrasikan `stylelint` dengan plugin `stylelint-no-unsupported-browser-features` dan rule pelarangan properti `!important`.
- [ ] **Zero Unused Styles**: Lakukan tree-shaking CSS via PurgeCSS atau AST-level extractor di pipeline CI/CD.

---

### 12. Hands-on Practice

Buat dan operasikan project praktikum berikut di folder `hands-on/m02/`:

#### Langkah 1: Inisialisasi Environment
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
npm init -y
npm install -D style-dictionary typescript @types/node
```

#### Langkah 2: Buat W3C Tokens Source (`hands-on/m02/tokens.json`)
```json
{
  "semantic": {
    "color": {
      "surface": {
        "default": { "$value": "#ffffff", "$type": "color" },
        "muted": { "$value": "#f1f5f9", "$type": "color" }
      },
      "text": {
        "primary": { "$value": "#0f172a", "$type": "color" }
      }
    }
  },
  "brand": {
    "primary": {
      "main": { "$value": "#2563eb", "$type": "color" }
    }
  }
}
```

#### Langkah 3: Konfigurasi Pipeline Engine (`hands-on/m02/sd.config.js`)
```javascript
export default {
  source: ['tokens.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'build/',
      files: [
        {
          destination: 'variables.css',
          format: 'css/variables',
          options: {
            outputReferences: true
          }
        }
      ]
    },
    json_flat: {
      transformGroup: 'js',
      buildPath: 'build/',
      files: [
        {
          destination: 'tokens-flat.json',
          format: 'json/flat'
        }
      ]
    }
  }
};
```

#### Langkah 4: Buat File Implementasi CSS Native (`hands-on/m02/index.html`)
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hands-On M02 Styling Architecture</title>
  <link rel="stylesheet" href="build/variables.css">
  <style>
    @layer reset, base, layout, components;

    @layer reset {
      * { box-sizing: border-box; margin: 0; padding: 0; }
    }

    @layer layout {
      .app-shell {
        padding: 2rem;
        background-color: var(--semantic-color-surface-muted);
        min-height: 100vh;
      }
      .responsive-host {
        container-type: inline-size;
        resize: horizontal;
        overflow: auto;
        border: 2px dashed #94a3b8;
        padding: 1rem;
        min-width: 250px;
        width: 600px;
      }
    }

    @layer components {
      .responsive-card {
        contain: layout paint;
        background-color: var(--semantic-color-surface-default);
        color: var(--semantic-color-text-primary);
        padding: 1.5rem;
        border-radius: 8px;
        display: grid;
        grid-template-columns: 1fr;
        gap: 1rem;
      }

      /* Responsive berdasarkan container-nya sendiri */
      @container (min-width: 400px) {
        .responsive-card {
          grid-template-columns: 120px 1fr;
        }
      }
    }
  </style>
</head>
<body>
  <div class="app-shell">
    <div class="responsive-host">
      <article class="responsive-card">
        <div style="background-color: var(--brand-primary-main); aspect-ratio: 1; border-radius: 4px;"></div>
        <div>
          <h3>Container-Query Driven Component</h3>
          <p>Tarik sudut kanan bawah container ini untuk memicu perubahan layout tanpa bergantung pada ukuran viewport layar browser.</p>
        </div>
      </article>
    </div>
  </div>
</body>
</html>
```

#### Langkah 5: Eksekusi Pipeline
Tambahkan `"type": "module"` ke `package.json`, lalu jalankan:
```bash
npx style-dictionary build --config sd.config.js
```
Buka file `index.html` di browser menggunakan static server (e.g., `npx serve .`) dan amati file CSS yang dihasilkan secara deterministik di folder `build/variables.css`.

---

### 13. Exercises

#### Level Easy
Tulis skrip SCSS atau Vanilla CSS menggunakan Cascade Layers (`@layer`) dengan hierarki: `framework`, `custom`, `utilities`. Buktikan bahwa selektor spesifisitas rendah pada `.utilities` (misal: single class `.d-none`) tetap mengabaikan dan menimpa selektor spesifisitas tinggi milik `.custom` (misal: `#main-banner.hero-section div`).

#### Level Medium
Konfigurasikan formatter custom pada Style Dictionary v4 yang mem-parsing file token JSON DTCG dan mengekstraknya menjadi tipe TypeScript immutable:
```typescript
export const Tokens = { ... } as const;
export type AppTokenKey = ...;
```
Di mana keys token memiliki format nested typing yang valid.

#### Level Hard
Rancang arsitektur styling zero-runtime untuk sistem micro-frontend yang berjalan pada Module Federation:
1. Shell Host dan Remote App berbagi token yang sama.
2. Remote App menginjeksi CSS tanpa menyebabkan collision nama class dengan Shell Host (menggunakan custom hashing algorithm berbasis commit hash/package scope).
3. Buat script pembersih stylesheet yang secara otomatis menghapus tag `<style>` atau `<link>` milik Remote App dari DOM ketika komponen micro-frontend tersebut di-*unmount*.

---

### 14. Challenge: White-Label CSS Architecture Migration
Sebuah platform SaaS Enterprise multi-tenant meminta Anda memimpin migrasi styling sistem mereka dari arsitektur runtime CSS-in-JS (*Styled-Components*) yang rapuh ke arsitektur modern berkinerja tinggi.

**Batasan Masalah**:
- Platform memiliki **12 tenant aktif** dengan konfigurasi warna, tipografi, dan elevation yang berbeda-beda.
- Platform memiliki basis kode lebih dari **300 komponen antarmuka**.
- Rendering menggunakan **Next.js App Router (RSC)**; tidak boleh ada tag `'use client'` yang ditambahkan semata-mata demi kebutuhan styling/theming provider.
- Core Web Vitals target: **CLS (Cumulative Layout Shift) harus 0**, dan **LCP (Largest Contentful Paint) < 1.2 detik** pada koneksi 4G lambat.

**Tugas Arsitektur Anda**:
1. Rancang blueprint struktur JSON Design Tokens multi-tier yang memisahkan base design tokens SaaS dengan layer custom tenant branding.
2. Tentukan bagaimana CSS injection dijalankan pada streaming RSC SSR agar tidak terjadi FOUC ataupun Layout Shift ketika tenant context diakses via dynamic route domain (`tenant-a.saas.com` vs `tenant-b.saas.com`).
3. Sajikan proposal strategi kompilasi CSS (pilih antara Tailwind v4, Vanilla Extract, atau StyleX) lengkap dengan argumen trade-off mendalam terkait kecepatan CI/CD build vs fleksibilitas tenant.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Mengapa browser mengevaluasi selector CSS dari kanan ke kiri (Right-to-Left)?**
   - A. Karena dokumen HTML diurai dari kanan ke kiri.
   - B. Untuk memfilter elemen non-kandidat (key selector) secepat mungkin dari DOM tree.
   - C. Agar aturan cascading layer dapat diabaikan.
   - D. Merupakan warisan arsitektur XHTML yang tidak relevan lagi.

2. **Apa fungsi utama dari spesifikasi W3C Design Tokens Community Group (DTCG)?**
   - A. Menggantikan bahasa CSS sepenuhnya di browser modern.
   - B. Membakukan skema interoperabilitas metadata desain agar token dapat diterjemahkan ke berbagai platform secara konsisten.
   - C. Menyediakan library runtime JavaScript gratis untuk tema dark-mode.
   - D. Menghubungkan database SQL secara langsung ke file konfigurasi styling.

3. **Perilaku apa yang terjadi jika aturan CSS di dalam `@layer reset` menggunakan penanda `!important` berhadapan dengan `@layer utilities` tanpa `!important`?**
   - A. `@layer utilities` tetap menang karena dideklarasikan terakhir.
   - B. Terjadi error kompilasi CSS syntax invalid.
   - C. `@layer reset` yang memiliki `!important` akan menang; bahkan urutan pembalikan prioritas `!important` layers menempatkannya di atas layer reguler.
   - D. Kedua aturan saling membatalkan (*cascade nullification*).

4. **Karakteristik fundamental dari Zero-Runtime CSS Engine adalah:**
   - A. Tidak menggunakan file CSS sama sekali di browser.
   - B. Memproses semua style menjadi inline CSS attributes via Virtual DOM.
   - C. Melakukan kompilasi style menjadi stylesheet statis saat build-time tanpa injeksi kode parsing JS di client runtime.
   - D. Memerlukan web worker untuk menghitung class names secara paralel.

5. **Apa kegunaan properti `contain: layout;` pada browser rendering engine?**
   - A. Mengunci ukuran kontainer agar tidak bisa membesar.
   - B. Memberi tahu browser bahwa perubahan layout di dalam elemen tersebut tidak akan mempengaruhi geometri elemen luar.
   - C. Mengubah elemen menjadi Flexbox layout secara otomatis.
   - D. Menghapus margin collapse antar elemen saudara.

#### Intermediate (5 Pertanyaan)
6. **Perhatikan skenario selektor berikut. Manakah yang memiliki performa evaluasi browser paling optimal?**
   - A. `div.container ul li a.active`
   - B. `[data-active="true"] *`
   - C. `.nav-link-active`
   - D. `body > div > nav > a.active`

7. **Mengapa Container Queries (`@container`) lebih superior dibandingkan Media Queries (`@media`) dalam konteks arsitektur Desain Komponen Modular?**
   - A. Karena Container Queries didukung oleh GPU rendering sedangkan Media Queries tidak.
   - B. Karena evaluasi responsive breakpoint didasarkan pada dimensi parent host elemen itu sendiri, memungkinkan portabilitas komponen di berbagai konteks layout.
   - C. Karena Container Queries tidak memerlukan styling CSS dan dapat dikontrol langsung via atribut HTML.
   - D. Karena Media Queries menyebabkan memory leak pada browser Chrome.

8. **Masalah mendasar yang timbul saat memaksakan runtime CSS-in-JS (seperti Emotion) di lingkungan React Server Components (RSC) adalah:**
   - A. RSC tidak mendukung tag HTML `<style>`.
   - B. Library runtime tersebut mengandalkan React Context dan lifecycles yang hanya valid pada Client Components.
   - C. Server Components tidak diizinkan memiliki dependensi NPM.
   - D. CSS-in-JS runtime otomatis mengunci rendering menjadi synchronous single-threaded.

9. **Apa efek samping yang terjadi bila CSS property `content-visibility: auto;` digunakan tanpa properti pendamping `contain-intrinsic-size`?**
   - A. Teks di dalam elemen tidak akan pernah dirender.
   - B. Scrollbar browser akan mengalami "lompatan" drastis (*scrollbar jumping* / CLS tinggi) saat elemen masuk/keluar dari viewport.
   - C. Layar browser akan mengalami screen tearing.
   - D. Elemen akan otomatis terpotong (*clipped*) secara horizontal.

10. **Dalam transformasi token hierarki DTCG, peran utama dari *Semantic/Alias Token* adalah:**
    - A. Menyimpan nilai warna mentah heksadesimal langsung dari palet Adobe Illustrator.
    - B. Mengisolasi maksud penggunaan (intent) dari nilai absolutnya, memfasilitasi penggantian tema global (seperti Dark Mode) secara sentral.
    - C. Mengurangi ukuran file JSON agar bisa di-load lebih cepat oleh HTTP/2.
    - D. Menjamin spesifisitas ID selector selalu berada di atas Class selector.

#### Production Scenarios (3 Studi Kasus)
11. **Skenario Kasus 1**:
    Tim Anda merilis pembaruan komponen tabel dengan 5.000 baris data interaktif. Setiap baris memiliki event listener `mouseenter` yang menambahkan class CSS `.row-hovered` yang mengubah `box-shadow` dan `top: -2px` (menggunakan `position: relative`). Pengguna melaporkan lag ekstrem (frame rate drop ke 12 fps) saat menggerakkan kursor cepat melintasi tabel.
    *Tindakan arsitektur manakah yang menyelesaikan akar masalah performa tersebut secara definitif?*
    - A. Bungkus penambahan class di dalam `setTimeout(..., 50ms)`.
    - B. Ganti modifikasi properti layout `top` dengan `transform: translateY(-2px)`, tambahkan `contain: layout paint` pada wrapper baris, dan pastikan hover digerakkan murni via CSS selector `:hover` tanpa JavaScript DOM mutation.
    - C. Gunakan `!important` pada deklarasi `box-shadow` agar browser memotong cascade checking.
    - D. Naikkan memori Node.js di server build machine.

12. **Skenario Kasus 2**:
    Pada aplikasi Micro-Frontend, tim Checkout menyematkan library CSS pihak ketiga yang memiliki selector sangat agresif: `button { padding: 20px !important; }`. Hal ini merusak tampilan button di seluruh shell aplikasi Host dan MFE milik tim lain. Anda tidak memiliki akses untuk mengubah file source code vendor tersebut.
    *Bagaimana cara menetralisir polusi style tersebut menggunakan fitur native Modern CSS?*
    - A. Membungkus impor CSS pihak ketiga ke dalam Cascade Layer terendah, misal `@layer vendor { @import "third-party.css"; }`.
    - B. Menulis script JavaScript yang menghapus semua tag `<button>` dan menggantinya dengan `<div>`.
    - C. Menimpa kembali semua tombol dengan `button { padding: 8px !important; }` di level file global host.
    - D. Mengubah seluruh aplikasi micro-frontend lain menggunakan inline style.

13. **Skenario Kasus 3**:
    Aplikasi web e-commerce mengalami regresi Cumulative Layout Shift (CLS) sebesar 0.45 saat pergantian tema dari 'Light' ke 'Dark'. Setelah diinspeksi, tema dark mengaktifkan font weight `font-weight: 700` sedangkan tema light menggunakan `font-weight: 400`, yang mengakibatkan perubahan lebar teks tombol navigasi dan membengkokkan wrapping layout container.
    *Bagaimana arsitek styling memperbaiki sistem token tipografi ini tanpa merusak estetika desain?*
    - A. Tambahkan `overflow: hidden` pada elemen `body`.
    - B. Gunakan properti CSS `font-variation-settings` pada Variable Font atau manfaatkan teknik layout guard teks semu (mengalokasikan ruang terlebar via hidden pseudo-element `::after` dengan font-weight 700), sehingga pergantian weight tidak mengubah *inline box metrics*.
    - C. Terapkan animasi transisi `all 0.5s ease` pada selector universal `*`.
    - D. Larang penggunaan mode gelap sama sekali pada aplikasi e-commerce.

---

### Kunci Jawaban Quiz

#### Basic
1. **B** — Evaluasi Right-to-Left memungkinkan browser menyaring mayoritas elemen DOM tree yang tidak cocok dengan Key Selector sejak langkah pertama.
2. **B** — DTCG mendefinisikan format JSON agnostik platform untuk interoperabilitas spesifikasi desain antar-tooling dan framework.
3. **C** — Mekanisme cascade layer membalikkan urutan layer ketika penanda `!important` digunakan; layer deklarasi terbawah yang memiliki `!important` justru akan mengalahkan layer di atasnya.
4. **C** — Zero-runtime mentranspilasi struktur style menjadi CSS murni waktu build, meniadakan injeksi dynamic style di JavaScript thread client.
5. **B** — Layout containment mengisolasi subtree DOM sehingga mutasi di dalamnya tidak memicu reflow ancestor.

#### Intermediate
6. **C** — Single class selector `.nav-link-active` dievaluasi seketika ($O(1)$ lookup via hash map engine browser) tanpa traversal DOM tree ancestors.
7. **B** — Container Queries mengizinkan komponen merespons ukuran ruang tempat komponen tersebut diletakkan secara mandiri, mendukung decoupling layout sejati.
8. **B** — Library runtime CSS-in-JS membutuhkan React Context API dan dynamic execution lifecycle yang tidak diizinkan pada Server Components.
9. **B** — Jika browser tidak mengetahui estimasi tinggi rendering subtree yang dilewati (skip rendering), ukuran total dokumen akan memendek drastis dan menyebabkan scrolling jumping.
10. **B** — Semantic tokens memetakan kebutuhan sistem ke primitive tokens, memungkinkan variasi tema (dark/light) cukup dialihkan di layer semantic tanpa merombak component logic.

#### Production Scenarios
11. **B** — Properti `top` memicu kalkulasi tahapan Layout & Paint secara synchronous pada seluruh tabel. Menggantinya dengan `transform` mengalihkan operasi ke Compositor thread (GPU) secara mulus.
12. **A** — Membungkus external bundle ke dalam layer terbawah menetralisir dampaknya secara deterministik sesuai spesifikasi CSS Cascade Layers specification.
13. **B** — Perubahan font-weight standar memodifikasi metrik glif font (width box). Penggunaan variable font text-stroke atau invisible pseudo-element width-guard mengunci metrik inline box dimensi tanpa layout shift.

---

### 16. Summary
Arsitektur styling enterprise modern telah bertransformasi dari sekadar teknik penamaan class konvensional menjadi sebuah disiplin rekayasa sistem yang terintegrasi penuh dengan siklus kompilasi bundler dan internal rendering engine browser:
1. **Design Tokens Sebagai Single Source of Truth**: W3C DTCG memfasilitasi kontrak desain-ke-kode multi-platform deterministik tanpa redundansi manual.
2. **Browser Engine Alignment**: Desain selektor efisien (RTL-aware), CSS Containment (`contain`, `content-visibility`), dan pergeseran animasi ke Compositor-only properties (`transform`, `opacity`) menjamin interaksi 60/120 fps stabil.
3. **Paradigma Zero-Runtime**: Pemisahan tegas antara kompilasi style (*build-time*) dan pergantian tema (*runtime* via CSS Custom Properties) mutlak diperlukan untuk kompatibilitas penuh dengan React Server Components dan penekanan TBT (Total Blocking Time).
4. **Cascade Orchestration**: Adopsi native Modern CSS seperti `@layer` dan `@container` memberikan determinisme spesifisitas absolut dan kemandirian komponen tingkat tinggi pada skala enterprise.