# BAB-09-Enterprise-Design-Systems-dan-Design-to-Code-Parity: Quiz, Challenge, & Knowledge Check

Uji pemahaman konseptual, arsitektural, dan implementasi praktis terkait Enterprise Design Systems, multi-tier design tokens, pipeline Style Dictionary, governance, serta otomatisasi Design-to-Code Parity pada skala enterprise.

---

## Bagian 1: Basic Questions (5 Soal)

### 1. Apa perbedaan mendasar antara Global Tokens (Core/Primitive), Semantic Tokens (System/Alias), dan Component Tokens?
**A.** Global tokens mendefinisikan konteks penggunaan (misal: `color-button-primary`), sedangkan Semantic tokens mendefinisikan nilai heksadesimal mentah.  
**B.** Global tokens menyimpan raw values agnostik konteks (misal: `#0D6EFD`, `16px`), Semantic tokens mengikat raw values ke makna/tujuan fungsional (misal: `color-bg-interactive-default`), dan Component tokens mengisolasi styling komponen spesifik (misal: `button-primary-bg`).  
**C.** Component tokens adalah token global yang diekspor khusus untuk Web, sedangkan Global tokens hanya untuk Figma.  
**D.** Semantic tokens hanya digunakan untuk mode gelap (dark mode), sedangkan Global tokens untuk mode terang (light mode).

> **Kunci Jawaban: B**  
> **Penjelasan:** Multi-tier token architecture membagi token ke dalam 3 tier hierarki:  
> 1. *Global/Primitive Tokens*: Nilai mentah independen tanpa asumsi konteks (misal: `blue-500: #0D6EFD`).  
> 2. *Semantic/Alias Tokens*: Mengabstraksi intensi desain dan konteks semantik (misal: `action-primary-default: {blue-500}`), memungkinkan theming dinamis (light/dark mode, high contrast).  
> 3. *Component Tokens*: Merinci kontrak spesifik elemen visual komponen (misal: `button-filled-bg: {action-primary-default}`), mengisolasi perubahan internal komponen tanpa merusak komponen lain.

---

### 2. Mengapa format W3C Design Tokens Community Group (DTCG) menjadi standar de facto spesifikasi token modern?
**A.** Karena DTCG mewajibkan penulisan token dalam format XML biner agar tidak dapat diubah oleh desainer.  
**B.** Karena DTCG menyediakan skema standar JSON terstruktur (`$value`, `$type`, `$description`, `$extensions`) yang memungkinkan interoperabilitas antar Figma plugins, Style Dictionary, and tooling multi-platform tanpa vendor lock-in.  
**C.** Karena DTCG secara otomatis mengompilasi file Figma ke dalam kode Swift dan Kotlin tanpa build runner.  
**D.** Karena DTCG menghapus kebutuhan file CSS Variables di browser modern.

> **Kunci Jawaban: B**  
> **Penjelasan:** Spesifikasi DTCG menetapkan sintaks universal berbasis JSON dengan properti standar seperti `$value` dan `$type`. Hal ini mengakhiri fragmentasi format proprietary antar tools (misal format kustom Figma Tokens vs Tokens Studio vs proprietary JSON) dan memudahkan transformer engine (misalnya Style Dictionary) memetakan token ke Web (CSS/SCSS), iOS (Swift), and Android (Compose/XML).

---

### 3. Dalam pipeline Style Dictionary, apa peran dari "Transform" dan "Format"?
**A.** Transform mengunduh file dari Figma API, sedangkan Format mengunggahnya ke npm registry.  
**B.** Transform memodifikasi nilai satuan/nama token (misal: mengubah `px` ke `rem`, format kebab-case), sedangkan Format menentukan struktur output file akhir (misal: CSS custom properties, JSON, ES Module, atau Swift struct).  
**C.** Transform mengompresi gambar SVG, sedangkan Format melakukan linting file JavaScript.  
**D.** Transform hanya berjalan di browser, sedangkan Format dieksekusi di Figma plugin.

> **Kunci Jawaban: B**  
> **Penjelasan:** Pada Style Dictionary:  
> - *Transforms* adalah fungsi murni yang memproses unit token secara individual (misal: konversi color space hex ke rgba, resolusi math expression, transformasi naming convention ke camelCase/kebab-case).  
> - *Formats* menentukan template dokumen file keluaran yang mengagregasikan seluruh token yang telah di-transform (misal: file `:root { --token: val; }` untuk CSS, atau enum untuk Swift).

---

### 4. Apa yang dimaksud dengan "Design-to-Code Parity"?
**A.** Keadaan di mana tim desainer memiliki jumlah anggota yang sama persis dengan tim software engineer.  
**B.** Derajat keselarasan fungsional, visual, tokenomik, and state machine antara komponen yang didesain di Figma dengan komponen yang diimplementasikan di kode produksi.  
**C.** Proses konversi otomatis screenshot Figma menjadi kode HTML menggunakan Optical Character Recognition (OCR).  
**D.** Keharusan developer menggunakan Figma desktop client untuk menulis kode React.

> **Kunci Jawaban: B**  
> **Penjelasan:** Design-to-Code Parity mengukur konsistensi antara source of truth di sisi desain (Figma variants, design tokens, layout auto-layout rules, accessibility metadata) dan implementasi di kode produksi (props interface, token consumption, DOM layout, state handling, ARIA attributes). Zero drift adalah target parity sistem enterprise.

---

### 5. Apa fungsi utama dari Semantic Versioning (SemVer) dalam pengelolaan package Design System?
**A.** Menentukan harga lisensi komponen design system setiap kuartal.  
**B.** Mengatur hierarki otorisasi akses file Figma untuk junior vs lead designer.  
**C.** Mengomunikasikan dampak perubahan kontrak visual dan API komponen (`MAJOR.MINOR.PATCH`) sehingga tim konsumen dapat mengantisipasi breaking changes tanpa merusak layout aplikasi downstream.  
**D.** Membatasi jumlah komponen yang boleh dibuat maksimal 99 komponen.

> **Kunci Jawaban: C**  
> **Penjelasan:** SemVer (`MAJOR.MINOR.PATCH`) memberi jaminan stabilitas:  
> - *MAJOR*: Perubahan API breaking (misal: refactor nama prop, token renaming/penghapusan token publik, perombakan layout yang mengubah bounding box).  
> - *MINOR*: Penambahan komponen baru, variant baru, atau token baru yang backward-compatible.  
> - *PATCH*: Perbaikan bug styling mikro atau pembaruan dokumentasi tanpa perubahan kontrak.

---

## Bagian 2: Intermediate Questions (5 Soal)

### 6. Bagaimana arsitektur Style Dictionary menangani Token References (Aliasing) seperti `{color.base.blue.500}` dalam proses build?
**A.** Style Dictionary menghapus seluruh alias dan menggantinya dengan string kosong jika tidak ditemukan di file CSS.  
**B.** Style Dictionary melakukan deep resolution traversal pada Abstract Syntax Tree (AST) token sebelum tahap transform/format, mengganti referensi penunjuk dengan value konkret atau meneruskannya sebagai referensi CSS variable tergantung konfigurasi `outputReferences: true`.  
**C.** Style Dictionary mengeksekusi parser Babel runtime di production browser untuk me-resolve dependensi secara asinkron.  
**D.** Referensi hanya bisa di-resolve jika semua token disimpan dalam satu file JSON tunggal tanpa modularisasi direktori.

> **Kunci Jawaban: B**  
> **Penjelasan:** Engine Style Dictionary secara rekursif menelusuri dependensi referensi kurung kurawal `{...}`. Jika opsi `outputReferences: true` diaktifkan pada format CSS, engine mempertahankan hubungan semantik dengan menghasilkan `var(--semantic-token, var(--global-token))` daripada hardcoded value, mempertahankan kapabilitas dynamic runtime theming di browser.

---

### 7. Sebuah tim enterprise menerapkan multi-brand theming (Brand A, Brand B, Brand C) dengan dark mode untuk setiap brand. Bagaimana struktur tier token yang paling scalable untuk arsitektur ini?
**A.** Membuat salinan independen seluruh komponen React untuk masing-masing brand dan tema.  
**B.** Menyatukan Core Primitives yang komprehensif, lalu memisahkan Brand Semantic Overrides per brand (`tokens/brand-a/semantic.json`, `tokens/brand-b/semantic.json`), di mana masing-masing memiliki set `mode-light` dan `mode-dark` yang memetakan ke Core Primitives yang sama, sementara Component Tokens tetap agnostik terhadap brand.  
**C.** Menggunakan inline CSS styles yang membaca database konfigurasi tema melalui REST API setiap kali halaman dimuat.  
**D.** Menghapus level semantic token dan langsung memetakan Component Tokens ke hex code spesifik per brand di dalam source code JavaScript.

> **Kunci Jawaban: B**  
> **Penjelasan:** Skalabilitas multi-brand multi-theme dicapai dengan memisahkan *Tier Semantic* berdasarkan brand dan mode, sementara *Component Tokens* dan *Core Primitives* bersifat netral. Komponen hanya mengonsumsi Component/Semantic tokens. Ketika brand berganti, hanya token layer semantic yang ditukar via CSS class (`data-brand="a" data-theme="dark"`), tanpa ada modifikasi pada logika kode komponen.

---

### 8. Apa peran Visual Regression Testing (misalnya Playwright + Storybook Test Runner / Chromatic) dalam CI/CD pipeline Design System?
**A.** Memvalidasi apakah kode lolos unit test Jest untuk kalkulasi matematika token.  
**B.** Mengambil pixel screenshot dari setiap variant komponen Storybook pada berbagai viewport, lalu membandingkannya dengan baseline image via pixel-diffing algorithm untuk mendeteksi visual regressions atau layout shift yang tidak disengaja sebelum pull request di-merge.  
**C.** Mengukur kecepatan rendering canvas Figma di browser desainer.  
**D.** Mengonversi file PNG menjadi vector asset secara otomatis di CDN.

> **Kunci Jawaban: B**  
> **Penjelasan:** Visual regression testing di CI/CD memblokir merge PR jika terjadi visual drift yang tidak disengaja. Alat seperti Storybook Test Runner, Playwright, atau Chromatic merender setiap stories komponen, memotret DOM snapshot/canvas, dan melakukan threshold comparison (misal anti-aliasing delta, layout bounding box shift). Jika terdapat perubahan visual yang disengaja, reviewer harus menyetujui baseline baru.

---

### 9. Bagaimana Figma REST API dan Webhooks dimanfaatkan dalam otomatisasi pipeline Design-to-Code?
**A.** Menghapus file repository GitHub setiap kali desainer menutup aplikasi Figma.  
**B.** Figma Webhook mendeteksi event publikasi library (`LIBRARY_PUBLISHED`), memicu GitHub Actions runner untuk menarik file variables via Figma REST API (`/v1/files/:file_key/variables/local`), mengekstrak token DTCG JSON, menjalankan Style Dictionary, dan membuat automated Pull Request ke repositori design system.  
**C.** Figma REST API digunakan oleh browser client end-user untuk mengambil warna tombol secara real-time saat aplikasi dibuka.  
**D.** Mengirimkan pesan chat langsung ke seluruh pengguna aplikasi saat desainer mengubah warna button.

> **Kunci Jawaban: B**  
> **Penjelasan:** Event-driven design ops mengeliminasi proses ekspor token manual. Ketika desainer menekan "Publish Library" di Figma:  
> 1. Webhook memicu workflow CI/CD.  
> 2. Script extractor mengeksekusi Figma Variables API endpoint.  
> 3. Data dinormalisasi ke format W3C DTCG.  
> 4. Engine compiler memproduksi assets (CSS, SCSS, TS, Swift, Compose).  
> 5. Automated bot membuat PR lengkap dengan changelog token visual.

---

### 10. Mengapa komponen Design System sebaiknya menerapkan prinsip "Controlled Accessibility by Default" daripada menyerahkan atribut ARIA sepenuhnya kepada tim konsumen?
**A.** Karena browser menolak merender elemen HTML jika developer menulis atribut `aria-*` secara manual.  
**B.** Untuk menjamin kepatuhan standar WCAG 2.1/2.2 AA/AAA secara konsisten di seluruh produk, mengelola internal keyboard interaction patterns (misal Focus Trapping pada Modal, Arrow navigation pada Dropdown) dan state bindings (`aria-expanded`, `aria-controls`) di dalam komponen itu sendiri sehingga meminimalkan human error dari tim developer hilir.  
**C.** Agar komponen tidak dapat diakses oleh screen reader tanpa izin khusus dari tim security.  
**D.** Karena atribut ARIA memperlambat proses kompilasi bundler webpack.

> **Kunci Jawaban: B**  
> **Penjelasan:** Di level enterprise, delegasi manual accessibility ke ratusan feature developer downstream rentan menghasilkan bug kepatuhan (legal & compliance liability). Komponen primitive design system harus meng-encapsulate keyboard navigation specs (WAI-ARIA Authoring Practices), focus management, dynamic ARIA live announcement, dan color contrast ratio default di dalam core implementation.

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Kasus)

### Skenario 1: The "Snowflake Component" Contamination Crisis
* **Konteks:** Perusahaan fintech dengan 14 sub-produk independen mengalami pembengkakan varian komponen. Developer di tim sub-produk KPR dan Kartu Kredit sering membuat variasi button dan input kustom ("Snowflake") di repositori lokal mereka karena Design System inti dianggap terlalu kaku dan proses pengajuan request memakan waktu 3 minggu. Akibatnya, audit brand mendapati 47 variasi visual button yang berbeda di seluruh domain web perusahaan.
* **Pertanyaan Analisis:** Bagaimana memecahkan krisis ini dari sisi Governance, Token Architecture, and Technical Extensibility tanpa memperlambat delivery tim produk?
* **Solusi Arsitektural:**
  1. *Sub-atomic Slots & Compound Composition*: Refactor Button & Input core menjadi arsitektur compound component dengan slot support (`leadingIcon`, `trailingIcon`, `customContent`), memisahkan behavior logic dari strict layout decorator.
  2. *Component Override Tokens*: Buka layer Component Token yang aman di-override (misal `--btn-padding-inline`, `--btn-border-radius`) melalui theme provider scoped, tanpa mengizinkan hardcoded CSS injection atau arbitrary class overrides.
  3. *Federated Contribution Model & Fast-Track RFC*: Bentuk Design System Council dengan perwakilan dari tim produk. Buat pipeline RFC (Request For Comments) digital dengan SLA 72 jam: jika variant baru valid secara UX and disetujui, masuk ke *Experimental/Lab package* (`@ds/lab-button`) agar bisa langsung dipakai sambil menunggu stabilisasi masuk ke core library.
  4. *Linting Enforcement*: Pasang custom ESLint rule (`@ds/no-raw-button-elements` dan `@ds/no-arbitrary-colors`) di CI/CD seluruh tim produk untuk memblokir penggunaan tag HTML dasar atau CSS hardcoded values pada path UI critical.

---

### Skenario 2: Token Pipeline Crash pada Dark Mode Multi-Brand
* **Konteks:** Sebuah platform e-commerce meluncurkan brand baru ("Brand Premium") dengan palet dark mode eksklusif. Saat pipeline Style Dictionary dijalankan, script kompilasi crash dengan error: `Circular dependency detected: {color.surface.primary} -> {color.surface.canvas} -> {color.surface.primary}`. Sementara itu, tim Android melaporkan bahwa token opacity bernilai desimal `0.16` diubah menjadi integer `0` pada file XML resources, merusak seluruh elevation and backdrop visual.
* **Pertanyaan Analisis:** Apa akar masalah arsitektur token di atas dan bagaimana solusi perbaikannya?
* **Solusi Arsitektural:**
  1. *Akar Masalah Circular Dependency*: Terjadi cross-referencing pada level semantic tokens antar token di tier yang sama tanpa anchor ke primitive base token.  
     *Perbaikan*: Terapkan DAG (Directed Acyclic Graph) validation pada pre-build token linter. Tegakkan aturan ketat: *Semantic Token HANYA boleh mereferensikan Primitive Token*, tidak boleh mereferensikan sesama Semantic Token secara horizontal.
  2. *Akar Masalah Android Opacity Crash*: XML Android `<color>` resource tidak mendukung floating-point opacity format CSS secara langsung; hex color di Android menggunakan format ARGB (8 digit) bukan RGBA atau format desimal terpisah.  
     *Perbaikan*: Buat custom transform Style Dictionary khusus target Android (`attribute/color-argb`) yang mengonversi format alpha desimal menjadi 2 digit hex prefix (misal `0.16 * 255 = 40.8` $\rightarrow$ hex `29`), lalu digabungkan menjadi `#29FFFFFF`, serta simpan token numerik non-color ke file `dimens.xml` atau Jetpack Compose color object.

---

### Skenario 3: Phantom Visual Drift Akibat Sub-Pixel Font Antialiasing
* **Konteks:** Tim QA visual melaporkan bahwa pada update minor library `@ds/core` (hanya pembaruan typography token dari `Inter` ke font korporat baru), visual regression testing di GitHub Actions menghasilkan 100% diff failure di seluruh 320 stories Storybook. Namun, saat diinspeksi secara manual oleh desainer di layar Retina display, tampilan visual tampak identik. Tim engineer terancam bypass seluruh visual test karena alarm palsu (*alert fatigue*).
* **Pertanyaan Analisis:** Mengapa hal ini terjadi di CI runner, dan bagaimana mengonfigurasi testing pipeline yang robust tanpa menurunkan standar parity?
* **Solusi Arsitektural:**
  1. *Akar Masalah*: Headless browser (Chromium) pada Linux runner di Docker CI merender font antialiasing (FreeType library) secara berbeda dengan macOS/Windows desktop desainer. Ketiadaan GPU hardware acceleration di headless Linux menyebabkan sub-pixel text boundary bergeser 0.5px - 1px, memicu pixel-by-pixel mismatch pada algoritma diffing gambar standar.
  2. *Perbaikan Containerization*: Standardisasi snapshot generation: developer tidak boleh membuat baseline snapshot dari mesin laptop lokal. Baseline snapshot hanya boleh digenerate di dalam Docker container yang identik dengan image CI runner (`mcr.microsoft.com/playwright`).
  3. *Tuning Pixel Diff Threshold & Anti-Aliasing Filter*: Konfigurasi algoritma diff (misal Pixelmatch):
     - Atur parameter `threshold: 0.1` (toleransi sensitivitas luminance).
     - Aktifkan `includeAA: false` untuk mengabaikan deviasi pada sub-pixel font anti-aliasing edges.
     - Tambahkan rule `maxDiffPixelRatio: 0.005` (toleransi perbedaan di bawah 0.5% dari total surface area komponen) untuk layout berbasis teks panjang.

---

## Bagian 4: Practical Chapter Challenge

### Tantangan: Bangun End-to-End Multi-Tier Token Pipeline & Production Button Component

#### Spesifikasi Tugas:
Anda ditugaskan merancang pipeline Design Token sederhana namun berstandar enterprise yang mengekstrak token DTCG JSON, mengompilasinya via script transformer, dan mengonsumsinya pada komponen web UI yang mendukung themer (Light & Dark Mode) dengan status parity visual 100%.

#### Langkah 1: Struktur File Token (Format W3C DTCG)
Buat representasi token dalam arsitektur 3-tier:

```json
// tokens/primitives.json
{
  "color": {
    "blue": {
      "50":  { "$value": "#eff6ff", "$type": "color" },
      "500": { "$value": "#3b82f6", "$type": "color" },
      "600": { "$value": "#2563eb", "$type": "color" },
      "700": { "$value": "#1d4ed8", "$type": "color" }
    },
    "neutral": {
      "0":   { "$value": "#ffffff", "$type": "color" },
      "900": { "$value": "#0f172a", "$type": "color" },
      "950": { "$value": "#020617", "$type": "color" }
    }
  },
  "spacing": {
    "2": { "$value": "8px", "$type": "dimension" },
    "4": { "$value": "16px", "$type": "dimension" }
  },
  "radius": {
    "md": { "$value": "6px", "$type": "dimension" }
  }
}
```

```json
// tokens/semantics.json
{
  "semantic": {
    "color": {
      "surface": {
        "canvas": {
          "default": {
            "$value": "{color.neutral.0}",
            "$type": "color",
            "$description": "Background canvas utama mode light"
          }
        }
      },
      "action": {
        "primary": {
          "default": { "$value": "{color.blue.600}", "$type": "color" },
          "hover":   { "$value": "{color.blue.700}", "$type": "color" },
          "focus":   { "$value": "{color.blue.500}", "$type": "color" }
        }
      },
      "text": {
        "on-action": { "$value": "{color.neutral.0}", "$type": "color" }
      }
    }
  }
}
```

#### Langkah 2: Build Engine Transformer (Style Dictionary Logic)
Konfigurasi compiler untuk menghasilkan variabel CSS terstandarisasi dengan fallback dynamic alias:

```javascript
// build-tokens.js (Ekivalen konfigurasi Style Dictionary v4)
export const config = {
  source: ['tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'dist/css/',
      options: {
        outputReferences: true
      },
      files: [
        {
          destination: 'tokens.css',
          format: 'css/variables',
          options: {
            selector: ':root'
          }
        },
        {
          destination: 'tokens-dark.css',
          format: 'css/variables',
          filter: (token) => token.filePath.includes('tokens-dark'),
          options: {
            selector: '[data-theme="dark"]'
          }
        }
      ]
    }
  }
};
```

#### Langkah 3: Komponen Button Terisolasi (Production-Ready)
Tulis implementasi komponen yang mengonsumsi CSS variables dari token layer tanpa hardcoded values:

```html
<!-- button.css -->
:root {
  /* Component Level Mappings */
  --btn-bg-default: var(--semantic-color-action-primary-default, #2563eb);
  --btn-bg-hover: var(--semantic-color-action-primary-hover, #1d4ed8);
  --btn-text: var(--semantic-color-text-on-action, #ffffff);
  --btn-padding-y: var(--spacing-2, 8px);
  --btn-padding-x: var(--spacing-4, 16px);
  --btn-radius: var(--radius-md, 6px);
  --btn-focus-ring: var(--semantic-color-action-primary-focus, #3b82f6);
}

.ds-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: var(--btn-padding-y) var(--btn-padding-x);
  font-family: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.25rem;
  color: var(--btn-text);
  background-color: var(--btn-bg-default);
  border: 1px solid transparent;
  border-radius: var(--btn-radius);
  cursor: pointer;
  transition: background-color 150ms cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 150ms cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
}

.ds-button:hover:not(:disabled) {
  background-color: var(--btn-bg-hover);
}

.ds-button:focus-visible {
  box-shadow: 0 0 0 3px var(--btn-focus-ring);
}

.ds-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

```html
<!-- index.html (Demonstrasi Theming Parity) -->
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="button.css">
</head>
<body>
  <!-- Light Theme Container -->
  <div style="padding: 24px; background: #ffffff;">
    <button class="ds-button" type="button">Primary Action</button>
  </div>

  <!-- Dark Theme Container (Scoped Override) -->
  <div data-theme="dark" style="padding: 24px; background: #0f172a;">
    <button class="ds-button" type="button">Primary Action Dark</button>
  </div>
</body>
</html>
```

#### Rubrik Penilaian & Verifikasi:
1. **Separation of Concerns (30%)**: File token terbagi rapi antara primitive dan semantic, tanpa adanya circular references.
2. **Design-to-Code Parity (30%)**: Seluruh properti CSS Button (warna, spacing, radius, focus state) merujuk ke token variable, tanpa satu pun magic number (seperti `padding: 11px` atau hardcoded `#1d4ed8`).
3. **Accessibility Compliance (20%)**: State `:focus-visible` memiliki ring kontras minimum 3:1 terhadap background, dan state disabled menangani cursor serta interaksi.
4. **Resilience & Fallbacks (20%)**: CSS variable memiliki safe inline fallbacks sehingga komponen tetap fungsional jika file token eksternal mengalami kegagalan loading.

---

## Bagian 5: Checklist Pemahaman Bab 09

Tandai checklist ini untuk mengonfirmasi kesiapan Anda sebelum melangkah ke implementasi arsitektur frontend tingkat lanjut:

- [ ] **Konseptual Multi-Tier Token**: Saya dapat menjelaskan perbedaan mendasar dan batas tanggung jawab antara Global/Primitive Tokens, Semantic/Contextual Tokens, dan Component Tokens.
- [ ] **Spesifikasi DTCG W3C**: Saya memahami struktur JSON terstandarisasi dengan key `$value`, `$type`, `$description`, serta format referensi `{tier.category.name}`.
- [ ] **Compiler Pipeline**: Saya memahami lifecycle Style Dictionary (Source Parsing $\rightarrow$ Dependency Resolution $\rightarrow$ Transforms $\rightarrow$ Formats) untuk target Web, iOS, and Android.
- [ ] **Theming & Multi-Brand Strategy**: Saya tahu cara menyusun semantic token layering agar perubahan tema (Light/Dark) atau perpindahan brand dapat terjadi secara instan via runtime CSS variables tanpa duplikasi kode komponen.
- [ ] **Figma API & Event Automation**: Saya memahami arsitektur webhook and REST API Figma untuk membangun continuous integration pipeline yang mengotomatiskan update token dari canvas desain ke pull request kode.
- [ ] **Design-to-Code Parity Testing**: Saya memahami implementasi Visual Regression Testing (Storybook + Playwright/Chromatic) serta mitigasi perbedaan sub-pixel antialiasing antar OS/CI runner.
- [ ] **Enterprise Governance & Versioning**: Saya mampu merancang alur kontribusi federasi (RFC process) dan menerapkan Semantic Versioning untuk menjamin zero breaking changes tak terduga bagi tim produk hilir.
