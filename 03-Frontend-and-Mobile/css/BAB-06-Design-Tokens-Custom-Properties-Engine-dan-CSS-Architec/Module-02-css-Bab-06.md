# Bab 06: Design Tokens, Custom Properties Engine, dan CSS Architecture
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik enterprise diharapkan mampu:

1. **Merancang dan Mengimplementasikan Multi-Tier Design Token Engine**: Mengonstruksi arsitektur *Design Tokens* 3-tingkat (*Global/Primitive*, *Semantic/Alias*, dan *Component Tokens*) berbasis standar W3C Design Tokens Community Group (DTCG) yang terintegrasi penuh ke pipeline CI/CD.
2. **Mengeksploitasi CSS Houdini `@property` API**: Mengimplementasikan registrasi tipe data ketat (*strict typing*), definisi inheritance, dan *fallback behavior* pada level CSSOM untuk mengoptimalkan pipeline rendering browser dan mengeliminasi *layout thrashing*.
3. **Mengotomatisasi Token Distribution Pipeline**: Membangun workflow otomatisasi dari sumber *single-source-of-truth* (JSON/Figma Tokens) menggunakan Style Dictionary ke format CSS variables, SCSS, dan TypeScript typings.
4. **Menerapkan Contextual Theming dan Multi-Brand White-Labeling**: Membangun runtime CSS engine yang mendukung *nesting themes*, *dark/light mode switching*, dan *high-contrast accessibility modes* dengan kompleksitas kalkulasi $O(1)$ pada runtime browser.
5. **Mengaudit & Mengoptimalkan Kinerja Style Recalculation**: Menganalisis *performance cost* dari mutasi CSS Custom Properties terhadap tahapan *Recalculate Style*, *Layout*, dan *Paint* menggunakan Chrome DevTools Performance Profiler.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:

* **CSSOM & Cascading Specificity**: Memahami cara kerja cascading inheritance, specificity calculation, dan *CSS Value Processing Phases* (*Specified Value* $\to$ *Computed Value* $\to$ *Used Value* $\to$ *Actual Value*).
* **Modern CSS Foundations**: Penggunaan dasar `var()`, `calc()`, CSS Grid, Flexbox, dan Container Queries.
* **Build Tools & Module Bundlers**: Pemahaman tentang Node.js runtime, NPM scripts, PostCSS, dan Vite/Webpack.
* **Basic Browser Rendering Pipeline**: Pengetahuan mendalam mengenai tahapan *DOM/CSSOM Construction*, *Render Tree*, *Layout (Reflow)*, *Paint*, dan *Compositing*.

---

### 3. Concept & Internal Architecture

#### 3.1 Resolusi Custom Properties pada Browser Engine

CSS Custom Properties bukanlah variabel statis layaknya variabel pada SCSS yang di-*compile-time inline*. Di dalam engine peramban (seperti Blink pada Chromium atau Gecko pada Firefox), Custom Properties dievaluasi secara dinamis selama fase **Style Resolution** pada CSSOM:

```
[HTML Parser]       [CSS Parser]
      │                   │
      ▼                   ▼
    [DOM]              [CSSOM]
      │                   │
      └───► [Render Tree] ◄──┘
                 │
                 ▼
      [Style Recalculation] ──► Custom Property Resolution (Token Reference Lookup)
                 │
                 ▼
          [Layout/Reflow]
                 │
                 ▼
         [Paint & Composite]
```

1. **CSS Parsing Phase**: Browser membuat struktur data representasi properti. Ketika menemukan properti yang diawali `--`, browser memperlakukannya sebagai *untyped custom property* yang nilainya berupa *stream of tokens* (CSS token stream), kecuali jika didaftarkan via `@property`.
2. **Cascade & Inheritance Phase**: Properti diwariskan ke turunan elemen DOM mengikuti jalur *tree traversal*. Properti standar di-*resolve* ke computed value secara langsung. Namun, ekspresi `var(--name, fallback)` tetap dalam status *unresolved token sequence* hingga mencapai node DOM target.
3. **Resolution & Substitution Phase**: Browser menelusuri rantai *computed style* elemen induknya untuk mencocokkan nama properti. Jika ada rantai ketergantungan (misal `--a: var(--b); --b: var(--c)`), engine menggunakan algoritma resolusi siklus (*cycle-detection algorithm*). Jika terdeteksi siklus tertutup ($--a \to --b \to --a$), seluruh variabel yang terlibat langsung dianggap `guaranteed-invalid` dan nilainya jatuh ke `unset` atau *initial value*.

#### 3.2 CSS Houdini `@property`: Type System di Tingkat CSSOM

CSS standar memperlakukan nilai `--my-color: #ff0000;` sebagai token teks semata. Konsekuensinya:
* Engine tidak dapat menganimasikan transisi antar nilai warna secara halus (tidak ada interpolasi warna pada `transition: --my-color 0.3s ease`).
* Nilai tidak divalidasi; jika diisi `--my-color: 20px;`, browser tidak menghasilkan error sintaks saat parsing, melainkan gagal render secara dinamis di runtime (*invalid at computed-value time*).

Dengan **CSS Properties and Values API Level 1 (`@property`)**, browser menyediakan sistem tipe statis langsung pada CSS engine:

```css
@property --brand-accent {
  syntax: '<color>';
  inherits: true;
  initial-value: #0052cc;
}
```

* **`syntax`**: Menentukan jenis data representasi (`<color>`, `<length>`, `<percentage>`, `<integer>`, `<number>`, `<transform-function>`, dsb.). Engine browser akan menolak nilai yang tidak sesuai gramatikal dan langsung menggunakan `initial-value`.
* **`inherits`**: Boolean flag. Jika disetel ke `false`, engine **menghentikan traversal pewarisan DOM tree**, secara radikal mengurangi konsumsi memori dan mengeliminasi proses *style recalculation* pada subtree komponen anak yang tidak menggunakan variabel tersebut.
* **`initial-value`**: Nilai pasti yang dijadikan *fallback* jika nilai yang diberikan invalid pada computed-value time.

#### 3.3 Multi-Tier Token Architecture (DTCG Standard)

Sistem token enterprise yang skalabel tidak menghubungkan token visual langsung ke komponen. Kita membaginya menjadi tiga lapis isolasi abstraksi:

```
[Layer 1: Global / Primitive Tokens]
  - Raw immutable values
  - e.g., --color-blue-500: #0066FF; --space-4: 16px;
           │
           ▼
[Layer 2: Semantic / Alias Tokens]
  - Intent, context, and role-driven
  - e.g., --surface-primary: var(--color-blue-500);
  - Dynamic switching (Light/Dark theme hooks directly here)
           │
           ▼
[Layer 3: Component-Scoped Tokens]
  - Scoped explicitly to an isolated component
  - e.g., --btn-bg-default: var(--surface-primary);
  - Modifiable via contextual utility or component modifiers
```

---

### 4. Why & What

| Fitur / Parameter | SCSS / Preprocessor Variables | Vanilla CSS Custom Properties | Modern Typed Token Engine (`@property` + DTCG) |
| :--- | :--- | :--- | :--- |
| **Evaluasi Waktu** | Build-time (Statis) | Runtime (Dinamis pada CSSOM) | Runtime dengan Validasi Engine |
| **Type-Safety** | Lemah (Hanya saat compile) | Tidak ada (String Token) | **Ketat** (Divalidasi langsung oleh Browser Engine) |
| **DOM Tree Inheritance**| Tidak ada konsep DOM | Ya, selalu inherit (Beban CPU) | **Dapat Dikonfigurasi** (`inherits: false` menghemat CPU) |
| **Animasi & Transisi** | Mustahil tanpa manipulasi DOM | Tidak dapat diinterpolasi halus | **Full Interpolation** (Native Browser Transition) |
| **White-Labeling / Them.**| Butuh re-compile SCSS baru | Mutasi CSS class/style attribute | Dynamic Theme Injection dengan zero layout thrashing |
| **Performance Impact** | 0% Runtime Style Recalc | Sedang (Tergantung Subtree Tree) | Teroptimasi Tinggi (Bisa isolasi Tree via `inherits`) |

---

### 5. How (Workflow Detail)

Arsitektur token enterprise dieksekusi melalui *token pipeline lifecycle* berikut:

```
[Figma / UI Specs] 
       │ (JSON via Tokens Studio / Figma REST API)
       ▼
[tokens.json (W3C DTCG Format)]
       │
       ▼
[Build Engine (Style Dictionary 4.x)]
       ├── Transform Token Strings to Dimensions, HSL/OKLCH, Timings
       ├── Validate Token Types & Structure
       └── Format Generation:
             ├── css/variables.css (Raw CSS Custom Properties)
             ├── css/houdini.css   (@property registrations)
             ├── scss/_tokens.scss (Backward Compatibility)
             └── ts/tokens.d.ts    (Type safety untuk TS/React/Vue)
       │
       ▼
[CSS Architecture Integration (CUBE CSS Engine)]
       ├── Global / Primitive Loading
       ├── Semantic Mapping (Light / Dark Mode switching)
       └── Component Consumption (Scoped Block styles)
```

---

### 6. Analogy & Diagram ASCII

Bayangkan sistem distribusi daya listrik pada gedung pencakar langit multi-penyewa (multi-tenant):

```
+-------------------------------------------------------------+
|              POWER GENERATOR (Global Tokens)               |
|            --raw-voltage-110v, --raw-voltage-220v           |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|       CIRCUIT BREAKER & TRANSFORMER (Semantic Tokens)       |
|    "Tenant Power Socket" = Points to 220v or 110v dynamically|
|   --power-workstation-main: var(--raw-voltage-220v)        |
+-------------------------------------------------------------+
            |                                     |
            v                                     v
+------------------------+           +------------------------+
| APPLIANCE A: Server    |           | APPLIANCE B: Desk Lamp |
| (Component Tokens)     |           | (Component Tokens)     |
| --server-input:        |           | --lamp-input:          |
|   var(--power-main)    |           |   var(--power-main)    |
+------------------------+           +------------------------+
```

Jika terjadi pergeseran dari US Standard (110V) ke EU Standard (220V), Anda tidak mengganti setiap kabel di dalam server atau lampu (*component level*). Anda cukup memutar sakelar di *Circuit Breaker* (*Semantic level*). Lampu dan server secara otomatis menerima voltase baru tanpa harus dibongkar ulang.

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Typed Custom Property dengan Transisi Mulus

Jika Anda mencoba menganimasikan `background: linear-gradient()` menggunakan CSS variabel biasa, browser akan langsung melakukan *jump* (tidak ada transisi). Dengan `@property`, kita bisa menganimasikan nilai `<color>` atau `<percentage>`.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<style>
  /* 1. Registrasi Typed Property */
  @property --gradient-stop {
    syntax: '<percentage>';
    inherits: false;
    initial-value: 0%;
  }

  @property --glow-color {
    syntax: '<color>';
    inherits: false;
    initial-value: #00e5ff;
  }

  .interactive-card {
    width: 320px;
    height: 180px;
    border-radius: 12px;
    background: radial-gradient(
      circle at var(--gradient-stop) 50%,
      var(--glow-color),
      #0d1117 70%
    );
    transition: --gradient-stop 0.6s cubic-bezier(0.16, 1, 0.3, 1),
                --glow-color 0.4s ease;
  }

  .interactive-card:hover {
    --gradient-stop: 60%;
    --glow-color: #ff0055;
  }
</style>
</head>
<body>
  <div class="interactive-card"></div>
</body>
</html>
```

#### 7.2 Practical Example: Enterprise Token Engine Architecture

##### A. Token Definitions (`tokens.json` - W3C DTCG Format)
```json
{
  "global": {
    "color": {
      "neutral": {
        "0":   { "$value": "#ffffff", "$type": "color" },
        "900": { "$value": "#0f172a", "$type": "color" }
      },
      "brand": {
        "primary": { "$value": "#2563eb", "$type": "color" },
        "primary-hover": { "$value": "#1d4ed8", "$type": "color" }
      }
    },
    "spacing": {
      "1": { "$value": "0.25rem", "$type": "dimension" },
      "2": { "$value": "0.5rem",  "$type": "dimension" },
      "4": { "$value": "1rem",    "$type": "dimension" }
    }
  },
  "semantic": {
    "color": {
      "surface": {
        "default": { "$value": "{global.color.neutral.0}", "$type": "color" },
        "inverted": { "$value": "{global.color.neutral.900}", "$type": "color" }
      },
      "action": {
        "primary": { "$value": "{global.color.brand.primary}", "$type": "color" },
        "primary-hover": { "$value": "{global.color.brand.primary-hover}", "$type": "color" }
      }
    }
  }
}
```

##### B. Build Script Engine (`build-tokens.js` menggunakan Style Dictionary)
```javascript
import StyleDictionary from 'style-dictionary';

const sd = new StyleDictionary({
  source: ['tokens.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'dist/css/',
      files: [
        {
          destination: 'tokens.css',
          format: 'css/variables',
          options: {
            outputReferences: true, // Mempertahankan relasi var() alih-alih hardcoded inline
          }
        },
        {
          destination: 'tokens-typed.css',
          format: 'css/houdini-properties'
        }
      ]
    }
  }
});

// Format Custom untuk Houdini @property Declarations
sd.registerFormat({
  name: 'css/houdini-properties',
  format: ({ dictionary }) => {
    return dictionary.allTokens
      .filter(token => token.$type === 'color' || token.$type === 'dimension')
      .map(token => {
        const syntaxType = token.$type === 'color' ? '<color>' : '<length>';
        return `@property --${token.name} {
  syntax: '${syntaxType}';
  inherits: false;
  initial-value: ${token.value};
};`;
      })
      .join('\n\n');
  }
});

await sd.buildAllPlatforms();
```

##### C. Production CSS Architecture Output (`theme-engine.css`)
```css
/* ==========================================================================
   1. GLOBAL TOKENS (Primitive Layer)
   ========================================================================== */
:root {
  --color-neutral-0: #ffffff;
  --color-neutral-900: #0f172a;
  --color-brand-primary: #2563eb;
  --color-brand-primary-hover: #1d4ed8;
  --spacing-1: 0.25rem;
  --spacing-2: 0.5rem;
  --spacing-4: 1rem;
}

/* ==========================================================================
   2. SEMANTIC TOKENS (Contextual Mapping Layer)
   ========================================================================== */
:root,
[data-theme='light'] {
  --surface-base: var(--color-neutral-0);
  --surface-contrast: var(--color-neutral-900);
  --interactive-accent: var(--color-brand-primary);
  --interactive-accent-hover: var(--color-brand-primary-hover);
}

[data-theme='dark'] {
  --surface-base: var(--color-neutral-900);
  --surface-contrast: var(--color-neutral-0);
  --interactive-accent: #3b82f6; /* Shifted contrast for dark mode */
  --interactive-accent-hover: #60a5fa;
}

/* High Contrast Accessibility Override */
@media (prefers-contrast: more) {
  :root {
    --interactive-accent: #0000ee;
    --surface-contrast: #000000;
  }
  [data-theme='dark'] {
    --interactive-accent: #ffff00;
    --surface-contrast: #ffffff;
  }
}

/* ==========================================================================
   3. COMPONENT TOKEN LAYER (CUBE CSS: Block Pattern)
   ========================================================================== */
.btn-core {
  /* Komponen mendeklarasikan dependensi lokalnya dengan fallback ke Semantik */
  --_btn-bg: var(--btn-custom-bg, var(--interactive-accent));
  --_btn-hover: var(--btn-custom-hover, var(--interactive-accent-hover));
  --_btn-padding: var(--spacing-2) var(--spacing-4);
  
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: var(--_btn-padding);
  background-color: var(--_btn-bg);
  color: var(--surface-base);
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s ease-in-out;
}

.btn-core:hover {
  background-color: var(--_btn-hover);
}

/* Exception Rule: Variant Injection tanpa merusak hierarki cascading */
.btn-core[data-variant='secondary'] {
  --_btn-bg: transparent;
  --_btn-hover: rgba(148, 163, 184, 0.1);
  color: var(--surface-contrast);
  border-color: var(--surface-contrast);
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Kasus
**Perusahaan**: Bank Digital "OmniFinance" (SaaS Core-Banking).  
**Permasalahan**: OmniFinance menyediakan platform *white-label* untuk 12 institusi perbankan regional mitra. Masing-masing mitra membutuhkan identitas visual unik (palet warna, kelengkungan border/radius, ritme tipografi). Tim arsitektur sebelumnya menggunakan SCSS dengan kompilasi per-brand yang menghasilkan 12 artefak stylesheet berbeda, berukuran masing-masing 450 KB, dan mengharuskan build ulang serta deploy ulang seluruh micro-frontend setiap kali mitra mengubah warna kampanye musiman.

#### Solusi Arsitektural
1. **Penyatuan Single-Engine CSS**: Mengganti 12 artefak SCSS dengan **satu inti runtime stylesheet (Unified CSS Runtime)** berbobot 85 KB (Gzipped).
2. **Dynamic Tenant Manifest Injection**: Profil mitra di-*serialize* menjadi JSON mini yang diinjeksi via server-side rendering (SSR) atau CDN Edge Worker langsung ke dalam tag `<head>` sebagai CSS custom properties:
   ```html
   <style id="tenant-manifest">
     :root {
       --brand-primary: #8a2be2;
       --brand-radius-base: 16px;
       --brand-font-family: 'Inter', sans-serif;
     }
   </style>
   ```
3. **Isolasi Nested Theming**: Komponen yang berada di dalam kontainer mitra (misal: widget ATM locator atau panel *embedded financing*) dapat di-override seketika menggunakan atribut scope:
   ```css
   [data-tenant-override='partner-express'] {
     --brand-primary: #00d084;
   }
   ```

#### Hasil Metrik Produksi
* **Build Time**: Turun dari 14 menit (kompilasi 12 bundle terpisah) menjadi **1 menit 12 detik** (single bundle).
* **Network Payload / Bandwidth**: Menghilangkan 5,4 MB storage duplikasi pada Edge CDN.
* **First Contentful Paint (FCP)**: Rata-rata meningkat 34% (turun dari 2.1 detik menjadi 1.38 detik) karena browser dapat melakukan caching pada CSS inti dan hanya memperbarui data deklaratif tenant di tag HTML head.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

#### Keuntungan (Pros)
* **Zero Runtime Scripting Overhead**: Mengubah tema tidak memerlukan looping JavaScript pada DOM node; browser mengevaluasi ulang gaya melalui native C++ engine.
* **Runtime Dynamic Coupling**: Pengubahan variabel di `:root` seketika termanifestasi di seluruh shadow root Web Components dan elemen DOM konvensional.
* **Dead Code Elimination**: Mengeliminasi ribuan utility classes spesifik warna (misal: `.text-blue-500`, `.text-blue-600`) dengan abstraksi semantik `--text-primary`.

#### Batasan & Risiko (Cons)
* **Style Recalculation Cost**: Mengubah variabel pada root node (`document.documentElement.style.setProperty('--global-bg', val)`) memaksa browser melakukan *style recalculation* pada **100% elemen di render tree**. Jika dilakukan di dalam event loop animasi tanpa batching, akan terjadi *frame dropping* parah (jank).
* **Inheritance Memory Overhead**: Custom properties secara default bersifat *inherited*. Pohon cascading yang terlampau dalam dengan ribuan variabel tak terpakai meningkatkan footprint memori CSSOM.
* **Fallbacks Fail-Silently**: Jika terjadi saltik pada nama variabel (`var(--brand-primry)`), browser tidak menampilkan warning di console. Elemen akan secara diam-diam mengevaluasi ke initial value (*guaranteed invalid value*).

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: "Invalid at Computed-Value Time" Mengakibatkan Unset, Bukan Fallback Standard

*Penyebab Error*:
Developer mengira jika Custom Property bernilai salah, CSS akan mundur ke deklarasi CSS sebelumnya.
```css
/* SALAH */
.box {
  background-color: red; /* Diharapkan jadi fallback jika --bg tidak valid */
  background-color: var(--bg);
}
```
Jika `--bg: 123px;` (tipe salah untuk background-color), browser **tidak** menggunakan `red`. Pada fase *Computed-Value Time*, deklarasi `background-color: var(--bg)` telah menimpa `background-color: red`. Karena `123px` invalid untuk background-color, browser mereset properti ke nilai `transparent` (initial value).

*Solusi*:
Gunakan fallback di dalam pemanggilan fungsi `var()` atau daftarkan dengan `@property`:
```css
/* BENAR */
.box {
  background-color: var(--bg, red);
}
```
Atau daftarkan syntax validation:
```css
@property --bg {
  syntax: '<color>';
  inherits: false;
  initial-value: red;
}
```

#### Kasus 2: Dependency Cycle Resolution Trap

*Penyebab Error*:
```css
:root {
  --base-size: var(--scaled-size);
  --scaled-size: calc(var(--base-size) * 1.25); /* Terjadi Cycle Loop */
}

.panel {
  padding: var(--base-size); /* BROWSER MENDETEKSI SIKLUS: Nilai menjadi guaranteed-invalid */
}
```
Browser melarang kalkulasi sirkular. Kedua variabel tersebut langsung di-invalidasi.

*Solusi*:
Pisahkan token mutlak dari token derivasi:
```css
:root {
  --primitive-size: 16px;
  --scaled-size: calc(var(--primitive-size) * 1.25);
  --base-size: var(--primitive-size);
}
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Terapkan Namespace Ketat**: Selalu gunakan prefix tier untuk mencegah tabrakan nama (`--g-` untuk Global, `--s-` untuk Semantic, `--c-` untuk Component; atau prefix organisasi `--omni-sys-*`).
- [ ] **Gunakan Private Component Variables Pattern**: Pola `--_local-var: var(--public-token, fallback)` mencegah manipulasi style komponen secara brutal dari luar, namun tetap mengekspos API pengubahan yang disengaja.
- [ ] **Gunakan `inherits: false` pada `@property`**: Daftarkan token non-pewaris (seperti margin, padding, border-radius) dengan `inherits: false` untuk mencegah kalkulasi recalculate style merambat ke leaf nodes DOM.
- [ ] **Audit via Stylelint**: Terapkan plugin `stylelint-declaration-strict-value` untuk melarang hardcoded hex colors, force penggunaan CSS variable semantik.
- [ ] **Hindari Inline Variable Injection pada Parent Node Berukuran Besar**: Jika mengupdate custom property via JS di tengah interaksi mouse/scroll, injeksikan ke elemen lokal spesifik, jangan pernah ke `:root` atau `<body>`.
- [ ] **Color Space Modern**: Standarisasi token warna baru pada color space `oklch()` atau `display-p3` untuk mendapatkan dynamic gamut yang seragam antara layar SDR dan HDR.

---

### 12. Hands-on Practice

Simpan seluruh file berikut ke dalam direktori: `hands-on/m02/`

#### Langkah 1: Siapkan Struktur Proyek
```bash
mkdir -p hands-on/m02/dist hands-on/m02/src
cd hands-on/m02
npm init -y
npm install --save-dev style-dictionary
```

#### Langkah 2: Buat Source Tokens
File: `hands-on/m02/src/tokens.json`
```json
{
  "sys": {
    "color": {
      "primary": {
        "$value": "#6366f1",
        "$type": "color"
      },
      "surface": {
        "$value": "#ffffff",
        "$type": "color"
      },
      "text": {
        "$value": "#0f172a",
        "$type": "color"
      }
    },
    "shape": {
      "radius": {
        "$value": "8px",
        "$type": "dimension"
      }
    }
  }
}
```

#### Langkah 3: Konfigurasi Compiler Tokens
File: `hands-on/m02/build.mjs`
```javascript
import StyleDictionary from 'style-dictionary';

const sd = new StyleDictionary({
  source: ['src/tokens.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'dist/',
      files: [
        {
          destination: 'design-tokens.css',
          format: 'css/variables',
          options: {
            outputReferences: true
          }
        }
      ]
    }
  }
});

await sd.buildAllPlatforms();
console.log('Tokens successfully compiled to dist/design-tokens.css');
```

Jalankan:
```bash
node build.mjs
```

#### Langkah 4: Buat Demo Implementation
File: `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Token Engine Testbed</title>
  <link rel="stylesheet" href="dist/design-tokens.css">
  <style>
    /* Typed Property Registration */
    @property --card-elevation {
      syntax: '<length>';
      inherits: false;
      initial-value: 2px;
    }

    /* Contextual Light/Dark Mapping */
    :root {
      --ui-bg: var(--sys-color-surface);
      --ui-text: var(--sys-color-text);
      --ui-accent: var(--sys-color-primary);
    }

    [data-theme="dark"] {
      --ui-bg: #0b0f19;
      --ui-text: #f8fafc;
      --ui-accent: #818cf8;
    }

    body {
      background-color: var(--ui-bg);
      color: var(--ui-text);
      font-family: system-ui, sans-serif;
      display: grid;
      place-items: center;
      min-height: 100vh;
      margin: 0;
      transition: background-color 0.3s ease, color 0.3s ease;
    }

    /* Component Architecture */
    .pro-card {
      --_radius: var(--sys-shape-radius);
      
      background: var(--ui-bg);
      border: 1px solid rgba(125, 125, 125, 0.2);
      border-radius: var(--_radius);
      padding: 2rem;
      width: 300px;
      box-shadow: 0 var(--card-elevation) calc(var(--card-elevation) * 3) rgba(0,0,0,0.15);
      transition: --card-elevation 0.3s ease, transform 0.3s ease;
    }

    .pro-card:hover {
      --card-elevation: 12px;
      transform: translateY(-4px);
    }

    .theme-toggle-btn {
      margin-top: 1rem;
      padding: 0.5rem 1rem;
      background: var(--ui-accent);
      color: #fff;
      border: none;
      border-radius: var(--sys-shape-radius);
      cursor: pointer;
    }
  </style>
</head>
<body>
  <div class="pro-card">
    <h2>Enterprise Card</h2>
    <p>Engine ini mengintegrasikan Dynamic Tokens dengan Typed Custom Properties.</p>
    <button class="theme-toggle-btn" id="toggleTheme">Toggle Dark Mode</button>
  </div>

  <script>
    const btn = document.getElementById('toggleTheme');
    btn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      document.documentElement.setAttribute('data-theme', current === 'dark' ? 'light' : 'dark');
    });
  </script>
</body>
</html>
```

---

### 13. Exercise

#### Level: Easy
1. Ubah file `tokens.json` untuk menyertakan token semantic baru: `sys.color.danger` bernilai `#ef4444`.
2. Lakukan build ulang script dan bind variabel tersebut ke tombol baru berkelas `.btn-danger` pada demo `index.html`.

#### Level: Medium
1. Tulis deklarasi `@property` untuk properti `--avatar-border-width`.
2. Validasi properti tersebut dengan tipe `<length>`, atur agar tidak terwariskan (`inherits: false`), dan tentukan nilai default sebesar `2px`.
3. Buat implementasi transisi CSS yang membesarkan border width secara mulus saat avatar di-hover, tanpa memicu *layout thrashing* pada elemen sibling.

#### Level: Hard
1. Buat mekanisme *Container-Driven Dynamic Tokens*: Ketika kontainer komponen berukuran di bawah 400px (via `@container`), ubah `--sys-shape-radius` menjadi `4px` dan compact spacing padding dari `16px` menjadi `8px`.
2. Pastikan komponen tombol child yang membaca `--_btn-padding` mengkalkulasi ulang posisinya secara dinamis tanpa penambahan modifier class JavaScript sama sekali.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Web Performance Architect di perusahaan e-commerce multinasional.  
**Tantangan**: Buatlah arsitektur CSS Theming Engine untuk halaman checkout yang memenuhi seluruh kondisi ketat berikut:
1. **Zero FOUC (Flash of Unstyled Content)** saat user berganti tema atau berpindah domain white-label.
2. Tidak ada operasi JavaScript apa pun yang menyentuh atribut style inline di dalam node elemen child (`element.style.setProperty` pada level child dilarang mutlak).
3. Mendukung **High-Contrast Dark Mode** (kombinasi `@media (prefers-contrast: more)` dan `[data-theme='dark']`) dengan validasi rasio kontras WCAG AAA (minimal 7:1) secara strictly-typed.
4. Nilai tokens harus terenkapsulasi sehingga developer lain tidak bisa menginjeksi sembarang nilai string ke dalam visual layout engine.

*Deliverable*: Tuliskan dokumen arsitektur teknis mini, spesifikasi skema `@property`, cascading overrides matrix, dan skrip *pre-render execution* berbasis vanilla JS inline ultra-ringan (< 20 baris) di bagian paling atas dokumen HTML `<head>`.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Mengapa SCSS variable tidak dapat digunakan untuk runtime dark/light theme switching secara dinamis?**
   * A. Karena SCSS tidak mendukung fungsi kalkulasi.
   * B. Karena variabel SCSS dihapus saat kompilasi dan nilainya di-inline menjadi nilai statis pada file CSS output.
   * C. Karena browser memblokir syntax SCSS di memory.
   * D. Karena spesifisitas selector SCSS lebih rendah daripada CSS standar.
   * *Jawaban*: **B**. Variabel preprocessor bersifat compile-time, bukan CSSOM dynamic reference.

2. **Karakter prefix apa yang wajib digunakan untuk mendefinisikan CSS Custom Property native?**
   * A. `$`
   * B. `@`
   * C. `--`
   * D. `__`
   * *Jawaban*: **C**. Sintaks native CSS Custom Properties wajib diawali dengan double-dash (`--`).

3. **Apa kegunaan argumen kedua pada pemanggilan `var(--main-color, #000)`?**
   * A. Menentukan warna saat hover.
   * B. Memberikan fallback value jika `--main-color` belum didefinisikan atau invalid pada saat parsing.
   * C. Mengubah warna latar browser.
   * D. Memaksa browser mengabaikan inheritance.
   * *Jawaban*: **B**. Argumen kedua bertindak sebagai nilai fallback.

4. **Kapan Custom Property dievaluasi oleh engine browser?**
   * A. Hanya saat file CSS didownload oleh network process.
   * B. Selama fase parsing HTML sebelum DOM tree selesai dibangun.
   * C. Selama fase resolusi CSSOM pada tahapan Computed Value.
   * D. Tepat sebelum server mengirim response header.
   * *Jawaban*: **C**. Engine mengevaluasinya pada fase Style Resolution / Computed-Value step.

5. **Apa ekstensi standar penulisan W3C Design Tokens Community Group?**
   * A. `.yaml`
   * B. `.tokens.json` / `.json`
   * C. `.xml`
   * D. `.theme.ts`
   * *Jawaban*: **B**. Standar W3C DTCG menggunakan format data JSON berbasis spesifikasi schema properti `$value` dan `$type`.

#### Bagian 2: Intermediate (5 Soal)
6. **Apa konsekuensi fatal dari mengubah CSS Custom Property di tingkat `:root` via JavaScript pada halaman berukuran 20.000 elemen DOM?**
   * A. Memory leak pada JavaScript garbage collector.
   * B. Browser akan memicu *Full Style Recalculation* pada seluruh pohon DOM yang berpotensi menghasilkan frame dropping parah.
   * C. Jaringan internet klien mengalami latency spike.
   * D. CSSOM langsung crash dan halaman menjadi unstyled.
   * *Jawaban*: **B**. Mengubah properti inherited di `:root` memaksa browser mengecek ulang validitas computed value pada seluruh node di DOM tree.

7. **Apa peran konfigurasi `inherits: false` pada deklarasi CSS `@property`?**
   * A. Mencegah properti dibaca oleh CSS inspect devtools.
   * B. Menghentikan penelusuran inheritance ke anak-anak elemen DOM, mengisolasi style recalculation pada node bersangkutan.
   * C. Mematikan animasi dan transisi CSS.
   * D. Menghapus properti dari CSSOM setelah dimuat.
   * *Jawaban*: **B**. Mengisolasi pewarisan dan mengoptimalkan komputasi style engine browser.

8. **Jika deklarasi `--color-accent: 12px;` digunakan pada `background-color: var(--color-accent, blue);`, apa warna yang akan di-render oleh browser?**
   * A. `blue`
   * B. `transparent` (initial value untuk background-color)
   * C. `black`
   * D. Error crash rendering
   * *Jawaban*: **B**. Pada saat parsing, `--color-accent` ada (sehingga fallback `blue` diabaikan). Pada *computed-value time*, `12px` tidak valid untuk properti warna, sehingga nilainya jatuh ke *initial value* properti tersebut, yakni `transparent`.

9. **Dalam arsitektur CUBE CSS, di mana letak deklarasi private component scoped variables (`--_local-var`) yang paling tepat?**
   * A. Global Utility Stylesheet.
   * B. Langsung di elemen target via atribut `style=""`.
   * C. Di dalam Block selector komponen tersebut sebagai mapping lokal dari Semantic Tokens.
   * D. Di dalam tag `<meta>` dokumen.
   * *Jawaban*: **C**. Pola privat scoped token CUBE CSS diletakkan di dalam Blok komponen bersangkutan.

10. **Bagaimana Style Dictionary menyelesaikan resolusi token `{global.color.brand.primary}` di file konfigurasi?**
    * A. Melakukan AJAX fetching ke server internal.
    * B. Melakukan dereferensi JSON pointer / object-path traversal selama fase transformasi build time.
    * C. Menggunakan regular expression saat runtime di browser.
    * D. Meminta compiler Node.js menjalankan eval().
    * *Jawaban*: **B**. Style Dictionary menelusuri struktur objek dictionary menggunakan referensi sintaks kurung kurawal `{}` dan menggantinya dengan nilai konkret.

#### Bagian 3: Skenario Kasus Produksi (3 Soal)
11. **Skenario 1**: Sebuah platform e-learning enterprise melaporkan masalah UI di mana ketika user membuka drawer menu, terjadi lag sebesar 120ms (Jank). Profiling Chrome DevTools menunjukkan event *Recalculate Style* memakan waktu 95ms. Anda menemukan ada animasi CSS bertipe:
    ```css
    .drawer {
      --drawer-x: 0px;
      transform: translateX(var(--drawer-x));
      transition: --drawer-x 0.3s;
    }
    ```
    *Apa root cause dari masalah tersebut dan bagaimana cara mematikan lag secara drastis?*
    * *Analisis & Solusi*: Root cause adalah pemicuan layout/paint recalculation berulang akibat manipulasi variabel custom property yang tidak didefinisikan syntax-nya atau animasi yang tidak di-offload ke Compositor. Solusi terbaik adalah **menghindari transisi pada variabel custom property untuk koordinat transform**. Transisikan properti `transform` secara native (`transition: transform 0.3s cubic-bezier(...)`) atau jika wajib menggunakan typed variable, daftarkan `@property --drawer-x` dengan `inherits: false`, tipe `<length>`, dan pastikan hanya node layer `.drawer` yang memiliki `will-change: transform`.

12. **Skenario 2**: Aplikasi micro-frontend Anda memuat CSS dari 3 tim berbeda. Tim A mendefinisikan `--color-primary: #00f;` di `:root`. Tim B mendefinisikan `--color-primary: #f00;` juga di `:root`. Terjadi insiden di mana tombol Tim A berubah warna menjadi merah karena urutan pemuatan stylesheet asinkron.
    *Bagaimana modifikasi arsitektur token yang wajib Anda lakukan untuk mencegah tabrakan global namespace tersebut?*
    * *Analisis & Solusi*:
      1. Terapkan **Token Namespacing Strict Policy**: Ganti variabel global tanpa nama domain menjadi sistem domain: `--mfe-a-sys-color-primary` dan `--mfe-b-sys-color-primary`.
      2. Terapkan **CSS Cascade Layers (`@layer`)** untuk mendistribusikan prioritas:
         ```css
         @layer team-a, team-b;
         ```
      3. Gunakan pola token komponen lokal terenkapsulasi: komponen internal tim membaca private property `--_btn-color: var(--mfe-a-brand-primary, #00f)`.

13. **Skenario 3**: Bank ingin meluncurkan fitur Dark Mode instan. Developer menggunakan solusi cepat:
    ```css
    html.dark {
      filter: invert(1) hue-rotate(180deg);
    }
    ```
    Solusi ini menyebabkan gambar user, banner marketing, dan video streaming rusak warnanya, serta performa rendering hancur pada perangkat mobile low-end.
    *Rancang blueprint arsitektur perbaikan yang elegan menggunakan sistem token 3-tier!*
    * *Analisis & Solusi*:
      1. **Hapus Filter Inversi Global**: Inversi CSS pada level root memaksa GPU melakukan post-processing framebuffer terus-menerus pada seluruh composited layers.
      2. **Bangun Semantic Abstraction Layer**:
         * Tentukan Primitive: `--color-neutral-100: #fff;`, `--color-neutral-900: #121212;`
         * Tentukan Semantic: Pada `html`, petakan `--bg-app: var(--color-neutral-100);` dan `--text-app: var(--color-neutral-900);`.
         * Pada `html.dark` (atau `[data-theme="dark"]`), balik penunjukan pointer semantic: `--bg-app: var(--color-neutral-900);` dan `--text-app: var(--color-neutral-100);`.
      3. Komponen media (`img`, `video`) tidak terpengaruh karena hanya membaca CSS property reguler dan tidak mengonsumsi token surface latar belakang. Operasi rendering tetap berada pada GPU pipeline native tanpa filter.

---

### 16. Summary

1. **Abstraksi Tiga Tingkat (3-Tier Token Architecture)**: Pemisahan tegas antara *Global (Primitive)*, *Semantic (Alias)*, dan *Component Tokens* adalah fondasi utama arsitektur antarmuka modern untuk mencapai interoperabilitas, white-labeling, dan pemeliharaan jangka panjang.
2. **Dynamic Computation Lifecycle**: Tidak seperti variabel preprocessor, CSS Custom Properties hidup di dalam CSSOM dan dievaluasi di runtime peramban pada tahap *Computed-Value*. Kesalahan gramatika sintaks tidak memicu CSS compile error, melainkan mengevaluasi ke *invalid at computed-value time*.
3. **CSS Houdini `@property`**: Merupakan lompatan paradigma dari *loosely-typed text stream* menjadi *strongly-typed engine attributes*. Penggunaan atribut `syntax`, `inherits: false`, dan `initial-value` memberikan performa style recalculation optimal serta memungkinkan native interpolation untuk animasi tingkat lanjut.
4. **Toolchain Integration**: Arsitektur Design Tokens enterprise wajib mengadopsi standar single-source-of-truth berbasis format W3C DTCG yang dikompilasi secara otomatis melalui Style Dictionary untuk menjamin konsistensi lintas ekosistem (Web, iOS, Android, Figma).