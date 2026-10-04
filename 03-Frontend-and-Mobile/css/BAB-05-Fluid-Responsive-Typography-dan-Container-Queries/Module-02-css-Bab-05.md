# BAB 05: Fluid Responsive Typography & Container Queries
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Memformulasikan** kalkulasi matematika untuk *fluid typography* dan *fluid spacing* menggunakan `clamp()`, `calc()`, dan unit relasional berbasis CSS Custom Properties tanpa merusak aksesibilitas WCAG 1.4.4 (Resize Text 200%).
- **Merancang Arsitektur Layout Berbasis Kontainer** (*Container Queries*) menggunakan properti `container-type`, `container-name`, dan container query units (`cqw`, `cqh`, `cqi`, `cqb`) untuk membangun komponen yang sepenuhnya agnostik terhadap *viewport*.
- **Membedah Mekanisme Internal Browser Layout Engine** dalam memproses *containment*, khususnya pencegahan *infinite layout loops* dan bagaimana *LayoutNG/Gecko* mengisolasi kalkulasi reflow.
- **Mengintegrasikan Container Queries dan Fluid Tokens** ke dalam *Design System Enterprise* berskala besar (Micro-frontends, multi-tenant UI) dengan performa rendering optimal.
- **Mengidentifikasi, Mendiagnosis, dan Memitigasi** *trade-offs* performa, isu *layout shift* (CLS), dan degradasi aksesibilitas pada *modern dynamic layout*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta harus menguasai:
- **CSS Box Model & Formatting Contexts**: Pemahaman mendalam mengenai Block, Inline, Flexbox, dan CSS Grid Layout.
- **CSS Values & Units Level 4**: Pemahaman mendalam terkait unit relatif (`rem`, `em`, `vw`, `vh`, `vi`, `vb`, `%`).
- **CSS Custom Properties (Variables)**: Manajemen token dinamis, inheritance tree, dan fallback values.
- **Prinsip Browser Rendering Engine**: Tahapan parsing DOM/CSSOM, Recalculate Style, Layout (Reflow), Paint, dan Composite.
- **Dasar Aljabar Linear**: Interpolasi linear (*linear interpolation / lerp*) untuk kalkulasi rentang skala dinamis.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Internal Mechanics of Fluid Typography (`clamp()` AST & Interpolasi Linear)

Pendekatan responsif konvensional mengandalkan rentetan CSS Media Queries breakpoints (`@media (min-width: 768px) { font-size: 1.5rem; }`), yang menghasilkan perubahan ukuran teks secara diskrit (*stepped*). Hal ini menimbulkan masalah estetika pada batas viewport (*breakpoint snapping*) dan beban maintenance stylesheet yang membengkak.

*Fluid Typography* memecahkan masalah ini dengan mentransformasikan ukuran teks menjadi fungsi kontinu terhadap dimensi layout (baik *viewport* maupun *container*).

Secara matematis, formula interpolasi linear yang digunakan adalah:

$$y = y_1 + \left( \frac{y_2 - y_1}{x_2 - x_1} \right) \cdot (x - x_1)$$

Di mana:
- $y$: Ukuran font kalkulasi (*target size*)
- $x$: Lebar viewport/kontainer saat ini
- $x_1$: Ambang batas minimum viewport/kontainer ($V_{\min}$)
- $x_2$: Ambang batas maksimum viewport/kontainer ($V_{\max}$)
- $y_1$: Ukuran font minimum ($S_{\min}$)
- $y_2$: Ukuran font maksimum ($S_{\max}$)

Dalam implementasi CSS modern, fungsi ini distrukturkan menggunakan `clamp(MIN, VAL, MAX)`. Di balik layar, engine CSS (Blink, Gecko, WebKit) menyusun *Abstract Syntax Tree* (AST) untuk ekspresi matematika tersebut.

```
                  [ clamp() ]
                 /     |     \
          [Min Font] [calc()] [Max Font]
                     /      \
             [Base Font]    [Rate of Change]
                                /      \
                       [Slope (vw/cqi)] [Offset Intercept]
```

**Formula Operasional CSS:**
$$\text{Slope} = \frac{S_{\max} - S_{\min}}{V_{\max} - V_{\min}}$$
$$\text{Intercept} = S_{\min} - (\text{Slope} \times V_{\min})$$

$$\text{font-size} = \text{clamp}(S_{\min}, \text{Intercept} + (\text{Slope} \times 100\text{vi}), S_{\max})$$

*Catatan Kritis Aksesibilitas (WCAG 1.4.4)*:
Jika ekspresi dalam `clamp()` murni hanya menggunakan unit viewport (`vw` atau `vi`), browser akan gagal mengaplikasikan pembesaran saat pengguna melakukan zooming via browser (Ctrl/Cmd + Plus). Agar compliant, bagian intersep *harus* dinyatakan dalam unit `rem` atau diekspresikan bersamaan dengan unit basis teks pengguna, sehingga perkalian skala teks oleh sistem/browser tetap mempengaruhi hasil resolusi kalkulasi.

#### B. Internal Mechanics of Container Queries (`@container`)

Secara historis, CSS Media Queries Level 3 mengevaluasi kondisi visual berdasarkan *global window frame* (viewport). Akibatnya, komponen modular yang diletakkan pada sidebar sempit dan area konten utama yang luas menerima sinyal media query yang sama persis, membatasi portabilitas komponen.

Container Queries Level 3 mengubah paradigma ini dengan memindahkan evaluasi layout dari viewport ke *ancestor element* yang telah didefinisikan sebagai *containment context*.

##### Browser Rendering Engine: Containment & Cycle Prevention

Mengizinkan elemen anak mengubah ukuran elemen induk berdasarkan dimensi elemen induk itu sendiri berisiko fatal: **Infinite Layout Loop** (Siklikal Reflow).
Contoh:
1. Kontainer memiliki lebar 400px.
2. Komponen anak mendeteksi lebar 400px, lalu mengaktifkan gaya `@container (max-width: 400px)` yang menyisipkan elemen baru berukuran 50px.
3. Penambahan elemen ini menyebabkan kontainer terdorong menjadi 450px.
4. Kondisi `@container (max-width: 400px)` menjadi *false*, elemen dihapus, kontainer kembali menjadi 400px.
5. Browser terjebak dalam *infinite render loop* dan crash.

Untuk mengeliminasi risiko ini, CSS Working Group menetapkan bahwa sebuah elemen harus secara eksplisit mendeklarasikan `containment` struktural sebelum dapat ditargetkan sebagai kontainer.

```css
.card-container {
  container-type: inline-size;
  container-name: cardContext;
}
```

Ketika `container-type: inline-size` diaplikasikan:
1. **Layout Isolation**: Browser Engine (seperti Blink LayoutNG) menginstansiasi *Layout Containment* dan *Inline-Size Containment* pada elemen tersebut.
2. **Dimension Independence**: Perhitungan ukuran inline (horizontal pada mode horizontal-tb) kontainer **dilarang keras** bergantung pada dimensi anak-anaknya (*intrinsic sizing* seperti `min-content` atau `max-content` pada arah inline dinonaktifkan atau diselesaikan sebelum evaluasi kueri). Kontainer harus mendapatkan ukuran inline secara ekstrinsik (misal melalui Flexbox stretch, CSS Grid track, atau explicit `width`).
3. **Targeted Subtree Reflow**: Saat lebar kontainer berubah, browser hanya memicu fase *Recalculate Style* dan *Layout* pada *subtree* yang diisolasi di bawah kontainer tersebut, bukan pada keseluruhan root document. Ini meningkatkan efisiensi komputasi *Layout Engine*.

---

### 4. Why & What

| Dimensi | Viewport-Driven Responsive Design (Legacy) | Container-Driven & Fluid Architecture (Modern) |
| :--- | :--- | :--- |
| **Kopling Komponen** | Sangat Tinggi (*Tightly Coupled* ke global viewport). | Komponen Agnostik (*Decoupled*). Mandiri di mana pun diletakkan. |
| **Modularitas UI** | Memerlukan utility override class (misal: `.card--sidebar`, `.card--main`). | *Single component definition*. Pola UI merespons ruang yang tersedia. |
| **Tipografi** | Terfragmentasi oleh puluhan breakpoint `px`/`em`. Lonjakan visual pada breakpoint. | Mulus (*continuous scaling*), terprediksi, berbasis matematika presisi via `clamp()`. |
| **Skalabilitas Micro-Frontend** | Sulit diisolasi; bentrok breakpoint antar-tim independen. | Sangat kompatibel; micro-frontend dapat mengelola query internal secara terisolasi. |
| **Efisiensi Stylesheet** | Ribuan baris CSS Media Queries boilerplate berulang. | Baris kode CSS ringkas, minim duplikasi deklarasi layout. |

---

### 5. How (Workflow Detail)

Langkah-langkah arsitektural untuk mengimplementasikan Fluid Responsive Typography dan Container Queries di tingkat produksi:

```
[Definisikan Fluid Token Matrix (Linear Equation)]
                        │
                        ▼
[Implementasikan Global Fluid Scale via CSS Variables]
                        │
                        ▼
[Deklarasikan Containment Context pada Atomic Layout Shell]
                        │
                        ▼
[Tulis Container Queries (@container) untuk Varian Komponen]
                        │
                        ▼
[Audit Aksesibilitas (WCAG 1.4.4 - Zoom 200%) & Performance Check]
```

#### Workflow Perhitungan Linear Interpolation Manual ke Variabel CSS:
1. Tentukan ukuran teks minimum ($S_{\min}$) pada viewport/kontainer batas bawah ($V_{\min}$).
2. Tentukan ukuran teks maksimum ($S_{\max}$) pada viewport/kontainer batas atas ($V_{\max}$).
3. Hitung $\text{Slope} = (S_{\max} - S_{\min}) / (V_{\max} - V_{\min})$.
4. Hitung $\text{Intercept} = S_{\min} - (\text{Slope} \times V_{\min})$.
5. Masukkan ke dalam fungsi `clamp(S_min, Intercept + Slope * CurrentAxis, S_max)`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Termos vs Wadah Kaca Modular

Pendekatan *Viewport Query* analog dengan mengatur volume cairan berdasarkan suhu cuaca di luar gedung; informasi global yang tidak relevan dengan kondisi fisik spesifik tempat cairan itu berada.

Sebaliknya, *Container Query* ibarat sifat air yang selalu mengisi dan menyesuaikan bentuk fisiknya secara otonom terhadap geometri wadah yang menampungnya—apakah ia dituangkan ke dalam mangkuk sup lebar atau ke dalam tabung reaksi sempit, respons bentuknya murni bergantung pada wadah penampungnya, bukan dimensi ruangan tempat wadah itu diletakkan.

#### Visualisasi Resolusi Konteks Layout

```
Viewport (Screen Width: 1440px)
┌────────────────────────────────────────────────────────────────────────┐
│  Desktop Shell Layout                                                  │
│  ┌─────────────────────────┐  ┌─────────────────────────────────────┐  │
│  │ Sidebar Column (320px)  │  │ Main Feed Area (800px)              │  │
│  │                         │  │                                     │  │
│  │ container-type:         │  │ container-type:                     │  │
│  │   inline-size           │  │   inline-size                       │  │
│  │                         │  │                                     │  │
│  │  ┌───────────────────┐  │  │  ┌───────────────────────────────┐  │  │
│  │  │ Product Card      │  │  │  │ Product Card                  │  │  │
│  │  │ (Renders Vertically│  │  │  │ (Renders Horizontally         │  │  │
│  │  │  Stacked Layout)  │  │  │  │  Side-by-Side Layout)         │  │  │
│  │  │                   │  │  │  │                               │  │  │
│  │  │ @container < 400px│  │  │  │ @container >= 600px           │  │  │
│  │  └───────────────────┘  │  │  └───────────────────────────────┘  │  │
│  └─────────────────────────┘  └─────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Mathematical Fluid Typography Engine

```css
:root {
  /* Konfigurasi Viewport Bounds */
  --fluid-min-width: 320; /* 320px */
  --fluid-max-width: 1200; /* 1200px */

  /* Konfigurasi Target Font Size (rem -> convert to absolute numeric representation for math) */
  --fluid-min-size: 16; /* 16px = 1rem */
  --fluid-max-size: 24; /* 24px = 1.5rem */

  /* Slope = (24 - 16) / (1200 - 320) = 8 / 880 = 0.0090909... */
  /* Dalam 100vw = 0.90909vw */
  /* Intercept = 16 - (0.0090909 * 320) = 16 - 2.90909 = 13.0909px -> ~0.818rem */

  --font-size-body-fluid: clamp(
    1rem,
    0.818rem + 0.909vw,
    1.5rem
  );
}

p.fluid-text {
  font-size: var(--font-size-body-fluid);
  line-height: 1.5;
}
```

#### B. Practical Example: Self-Contained Industrial Component

Penerapan komponen kartu (*Adaptive Data Tile*) yang mampu mengubah tipografi, spasi, dan orientasi grid internalnya secara independen terhadap ruang yang dialokasikan oleh parent layout.

```html
<div class="tile-wrapper">
  <article class="data-tile">
    <div class="data-tile__media">
      <img src="https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=600&q=80" alt="Grafik Metrik" />
    </div>
    <div class="data-tile__content">
      <span class="data-tile__tag">Operational Telemetry</span>
      <h3 class="data-tile__title">Real-Time Core Throughput</h3>
      <p class="data-tile__metric">842.6 <span class="data-tile__unit">GB/s</span></p>
      <p class="data-tile__description">
        Aggregated network egress across all active edge nodes within the last processing epoch.
      </p>
    </div>
  </article>
</div>
```

```css
/* 1. Inisialisasi Context Containment pada Wrapper */
.tile-wrapper {
  container-type: inline-size;
  container-name: data-tile-host;
  width: 100%;
  resize: horizontal; /* Utility interaktif untuk pengujian manual */
  overflow: hidden;
}

/* 2. Definisi Komponen Dasar */
.data-tile {
  box-sizing: border-box;
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  padding: clamp(0.75rem, 0.5rem + 1.5cqi, 2rem);
  background-color: #121316;
  color: #f1f3f5;
  border-radius: 8px;
  border: 1px solid #2a2c33;
}

.data-tile__media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 4px;
}

.data-tile__tag {
  display: inline-block;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #4dabf7;
  margin-bottom: 0.25rem;
}

/* Tipografi Adaptif Menggunakan Container Query Units (cqi) */
.data-tile__title {
  margin: 0;
  /* Font size berfluktuasi mulus terhadap inline size wadah */
  font-size: clamp(1rem, 0.85rem + 1.2cqi, 1.75rem);
  line-height: 1.25;
}

.data-tile__metric {
  margin: 0.5rem 0;
  font-weight: 700;
  font-size: clamp(1.5rem, 1.1rem + 2.5cqi, 3rem);
  color: #38d9a9;
}

.data-tile__unit {
  font-size: 0.4em;
  color: #adb5bd;
}

.data-tile__description {
  margin: 0;
  font-size: clamp(0.85rem, 0.75rem + 0.5cqi, 1rem);
  color: #a6a7ab;
  line-height: 1.4;
}

/* 3. Container Query Logic (Breakpoints Lokal Komponen) */
@container data-tile-host (min-width: 480px) {
  .data-tile {
    grid-template-columns: 180px 1fr;
    gap: 1.5rem;
  }
}

@container data-tile-host (min-width: 720px) {
  .data-tile {
    grid-template-columns: 240px 1fr;
    gap: 2rem;
  }

  .data-tile__content {
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Dashboard Analitik Keuangan Multi-Tenant (SaaS)
Sebuah platform analitik finansial enterprise mendistribusikan pustaka komponen widget UI ke beberapa divisi internal menggunakan arsitektur **Micro-Frontend (MFE)**.
- Setiap tenant atau divisi bebas menyusun tata letak *workspace* (misalnya: Mode 3-Kolom, Mode Split-Screen, atau Mode Full-Canvas).
- Masalah: Komponen *Market Depth & Transaction Feed Widget* dirancang menggunakan CSS Media Queries (`@media (min-width: 768px)`).
- Dampak: Ketika pengguna menaruh widget pada layout 3-kolom di layar 4K, `@media` membaca lebar layar 4K (3840px), sehingga widget memaksa rendering tampilan desktop ultra-wide (horizontal-tabbed table), padahal lebar kolom aktual widget di layar hanya **320px**. Hasilnya: konten tabel terpotong, UI hancur, dan terjadi lonjakan *horizontal scroll bug*.

#### Solusi Arsitektural Berbasis Container Queries:
1. **Pemisahan Peran Layout Host dan Leaf Component**:
   Host MFE menyediakan area docking dengan `container-type: inline-size`. Komponen diisolasi sepenuhnya tanpa asumsi viewport.
2. **Dynamic Typography Matrix Token**:
   Menghapus pemanggilan unit `vw` global di seluruh atom komponen, dialihkan ke `cqi` (Container Query Inline Unit).

```css
/* File: /tokens/fluid-scale.css */
:root {
  --cq-step--1: clamp(0.75rem, 0.7rem + 0.25cqi, 0.875rem);
  --cq-step-0:  clamp(0.875rem, 0.8rem + 0.35cqi, 1rem);
  --cq-step-1:  clamp(1.125rem, 1rem + 0.6cqi, 1.35rem);
  --cq-step-2:  clamp(1.5rem, 1.3rem + 1cqi, 1.875rem);
}

/* File: /components/financial-grid/widget.css */
.mfe-dock-slot {
  container-type: inline-size;
  container-name: financial-slot;
  width: 100%;
  height: 100%;
}

.financial-widget {
  font-family: var(--font-mono, monospace);
  font-size: var(--cq-step-0);
}

.financial-widget__header {
  font-size: var(--cq-step-1);
}

.financial-widget__order-row {
  display: grid;
  grid-template-columns: 1fr auto;
}

/* Modulasi Berdasarkan Slot Kontainer */
@container financial-slot (max-width: 350px) {
  .financial-widget__header {
    display: none; /* Sembunyikan header grafik kompleks pada ruang ultra-sempit */
  }
  
  .financial-widget__extra-metadata {
    display: none;
  }
}

@container financial-slot (min-width: 351px) and (max-width: 599px) {
  .financial-widget__order-row {
    grid-template-columns: 1fr 1fr;
  }
}

@container financial-slot (min-width: 600px) {
  .financial-widget__order-row {
    grid-template-columns: 1.5fr 1fr 1fr 1fr;
  }
  
  .financial-widget__extra-metadata {
    display: block;
  }
}
```

Hasil Pengujian:
- Nol dependensi terhadap resolusi monitor host.
- Efisiensi deployment meningkat: tim Micro-Frontend tidak perlu memelihara class varian (`widget--compact`, `widget--wide`).
- Komponen dapat ditarik (*drag-and-drop*) secara bebas melintasi layout grid dengan respons visual seketika.

---

### 9. Trade-offs

| Aspek | Fluid & Container-Driven Layout | Konvensional Fixed Breakpoint (Media Queries) |
| :--- | :--- | :--- |
| **Performance Overhead** | Sedikit beban saat *initial paint* karena registrasi containment context. Namun, *subsequent reflow* **jauh lebih cepat** karena terisolasi ke subtree kontainer. | Reflow bersifat global. Perubahan ukuran viewport mengevaluasi dan merender ulang seluruh layout tree dokumen. |
| **Render Latency** | Penggunaan berlebih container queries bertingkat (*deeply nested* $> 5$ level) dapat memicu latensi resolusi gaya pada DOM yang sangat dalam. | Rendah untuk seleksi CSS, namun berpotensi memicu *Long Frame Tasks* saat reflow global terjadi. |
| **Scalability & Code Health**| Sangat tinggi untuk skalabilitas skala enterprise. Komponen benar-benar modular, mendukung arsitektur Design System dan Micro-Frontend. | Rendah. Membutuhkan konfigurasi global breakpoint yang rentan pecah ketika struktur layout induk berubah. |
| **Debugging Complexity** | DevTools debugging lebih rumit: inspeksi harus menelusuri konteks induk terdekat yang menjadi *containment root*. | Sangat mudah: perubahan dapat disimulasikan murni dengan mengubah ukuran lebar window browser. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Layout Containment Loop (Penyebab Siklus Tak Hingga)
*Kode Salah:*
```css
.card {
  container-type: inline-size;
  /* Kesalahan: Mengatur lebar kontainer berdasarkan lebar anaknya yang dikontrol kueri */
  width: max-content; 
}

@container (min-width: 300px) {
  .card__content {
    width: 400px; /* Kontainer melebar -> memicu kueri -> loop */
  }
}
```
*Dampak:* Browser akan mengabaikan intrinsic sizing atau menghasilkan output layout yang *glitchy* (flashing).
*Solusi:* Pastikan kontainer selalu memiliki dimensi inline yang dievaluasi dari konteks ekstrinsik (misal: `width: 100%`, flex shrink/grow, grid area).

#### Kesalahan 2: Kehancuran Aksesibilitas Pembesaran Teks (WCAG 1.4.4)
*Kode Salah:*
```css
/* HANYA menggunakan viewport units */
h1 {
  font-size: clamp(1.5rem, 5vw, 3.5rem);
}
```
*Dampak:* Pada layar resolusi rendah, jika pengguna menyetel Browser Zoom ke 200%, formula `5vw` tetap dihitung murni terhadap ukuran jendela fisik monitor. Huruf tidak membesar dengan benar, melanggar kriteria WCAG Success Criterion 1.4.4 Resize Text.
*Solusi:* Masukkan komponen `rem` ke dalam kalkulator slope/intersep:
```css
h1 {
  font-size: clamp(1.5rem, 0.75rem + 3vw, 3.5rem);
}
```

#### Kesalahan 3: Tidak Ditemukannya Konteks Kontainer (*Nameless Container Misdirection*)
*Kasus:*
```css
.profile-card {
  container-type: inline-size;
}

.nested-item {
  container-type: inline-size;
}

@container (min-width: 400px) {
  /* Bermaksud mengecek ukuran .profile-card, tetapi browser 
     mengevaluasi .nested-item sebagai kontainer terdekat! */
  .profile-badge { display: block; }
}
```
*Solusi:* Selalu gunakan `container-name` saat terdapat potensi nesting untuk menghindari *accidental resolution*:
```css
.profile-card {
  container: profileContext / inline-size;
}

@container profileContext (min-width: 400px) {
  .profile-badge { display: block; }
}
```

---

### 11. Best Practices (Production Checklist)

1. **Gunakan `inline-size`, Hindari `size` Kecuali Sangat Perlu**:
   - `container-type: size` memerlukan ukuran tinggi dan lebar yang terdefinisi ekstrinsik. Menggunakannya sembarangan akan menyebabkan tinggi kontainer menciut menjadi `0px`.
2. **Definisikan Fallback Strategis**:
   - Manfaatkan `@supports (container-type: inline-size)` untuk menyediakan grid layout fallback sederhana bagi runtime lawas.
3. **Standarisasi Formula Fluid Menggunakan Token Terpusat**:
   - Jangan menulis magic numbers `clamp()` secara ad-hoc di tiap file komponen. Gunakan CSS Variables generator atau token engine (Style Dictionary).
4. **Batas Aksesibilitas Skala Tipografi**:
   - Pastikan batas atas ($S_{\max}$) tidak mengakibatkan teks overflow di kontainer kecil ketika mode font sistem diperbesar oleh OS.
5. **Hindari Query Nesting yang Terlalu Dalam ($> 3$ lapis)**:
   - Batasi container query hanya pada tingkat *molecule* atau *organism*. Hindari mendefinisikan *atom* (misal button kecil) sebagai container query tersendiri jika tidak esensial.

---

### 12. Hands-on Practice

Buatlah proyek mandiri pada direktori `hands-on/m02/` dengan struktur:
```
hands-on/m02/
├── index.html
└── styles.css
```

#### File: `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Laboratorium Fluid Typography & Container Queries</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>

  <header class="app-header">
    <h1 class="app-header__title">Telemetry Dashboard Shell</h1>
    <p class="app-header__subtitle">Menguji dynamic containment dan fluid scaling</p>
  </header>

  <main class="dashboard-grid">
    <!-- Kolom 1: Sempit -->
    <section class="panel-wrapper panel--narrow">
      <h2 class="panel-legend">Narrow Viewport Slot (Sidebar)</h2>
      <div class="card-host">
        <article class="sensor-card">
          <div class="sensor-card__status-indicator"></div>
          <div class="sensor-card__body">
            <span class="sensor-card__label">Inlet Pressure</span>
            <div class="sensor-card__reading">1,420 <abbr title="Pound per Square Inch">PSI</abbr></div>
            <p class="sensor-card__notes">Automated bypass valve running nominal on thread Alpha.</p>
          </div>
        </article>
      </div>
    </section>

    <!-- Kolom 2: Luas -->
    <section class="panel-wrapper panel--wide">
      <h2 class="panel-legend">Wide Viewport Slot (Main View)</h2>
      <div class="card-host">
        <article class="sensor-card">
          <div class="sensor-card__status-indicator sensor-card__status-indicator--nominal"></div>
          <div class="sensor-card__body">
            <span class="sensor-card__label">Reactor Core Stability</span>
            <div class="sensor-card__reading">99.98 <abbr title="Percentage Ratio">%</abbr></div>
            <p class="sensor-card__notes">Active quantum magnetic damping operational. Heat exchange dissipation nominal.</p>
          </div>
        </article>
      </div>
    </section>
  </main>

</body>
</html>
```

#### File: `hands-on/m02/styles.css`
```css
/* ==========================================================================
   RESET & FOUNDATIONAL TOKENS
   ========================================================================== */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  --bg-color: #0b0c10;
  --panel-bg: #1f2833;
  --text-main: #c5c6c7;
  --text-bright: #ffffff;
  --accent-cyan: #66fcf1;
  --accent-teal: #45a29e;
  --status-warning: #ffbe0b;
  --status-ok: #06d6a0;

  /* Global Typography Scale Menggunakan Viewport Intercept (Accessible) */
  --fluid-h1: clamp(1.75rem, 1.2rem + 2.5vw, 3rem);
}

body {
  background-color: var(--bg-color);
  color: var(--text-main);
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  padding: 2rem;
  line-height: 1.5;
}

.app-header {
  margin-bottom: 2rem;
  border-bottom: 1px solid var(--accent-teal);
  padding-bottom: 1rem;
}

.app-header__title {
  font-size: var(--fluid-h1);
  color: var(--accent-cyan);
  font-weight: 800;
  letter-spacing: -0.02em;
}

.app-header__subtitle {
  font-size: clamp(0.9rem, 0.8rem + 0.5vw, 1.2rem);
  color: var(--text-main);
}

/* ==========================================================================
   LAYOUT GRID
   ========================================================================== */
.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 2rem;
}

@media (min-width: 900px) {
  .dashboard-grid {
    grid-template-columns: 320px 1fr; /* Memisahkan host menjadi sempit dan luas */
  }
}

.panel-wrapper {
  background-color: #12141d;
  border: 1px dashed #3a3f58;
  padding: 1rem;
  border-radius: 8px;
}

.panel-legend {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--accent-teal);
  margin-bottom: 1rem;
}

/* ==========================================================================
   CONTAINMENT CONTEXT
   ========================================================================== */
.card-host {
  container-type: inline-size;
  container-name: sensorHost;
  width: 100%;
}

/* ==========================================================================
   LEAF COMPONENT (Sensor Card)
   Komponen ini sepenuhnya agnostik dan hanya peduli pada ukuran sensorHost
   ========================================================================== */
.sensor-card {
  background-color: var(--panel-bg);
  border-radius: 6px;
  border-left: 4px solid var(--status-warning);
  padding: clamp(0.75rem, 0.5rem + 2cqi, 1.5rem);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  transition: all 0.2s ease-in-out;
}

.sensor-card__status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background-color: var(--status-warning);
}

.sensor-card__status-indicator--nominal {
  background-color: var(--status-ok);
}

.sensor-card__label {
  font-size: clamp(0.75rem, 0.7rem + 0.3cqi, 0.9rem);
  text-transform: uppercase;
  color: #8f9aa8;
  letter-spacing: 0.05em;
}

.sensor-card__reading {
  /* Tipografi Fluid Berbasis cqi */
  font-size: clamp(1.5rem, 1.1rem + 2.5cqi, 2.75rem);
  font-weight: 700;
  color: var(--text-bright);
}

.sensor-card__reading abbr {
  font-size: 0.45em;
  color: var(--accent-cyan);
  margin-left: 0.25rem;
}

.sensor-card__notes {
  font-size: clamp(0.8rem, 0.75rem + 0.2cqi, 0.95rem);
  color: var(--text-main);
  line-height: 1.4;
}

/* ==========================================================================
   CONTAINER QUERIES
   ========================================================================== */
/* Layout saat container berukuran moderat/lebar */
@container sensorHost (min-width: 450px) {
  .sensor-card {
    display: grid;
    grid-template-columns: auto 1fr;
    grid-template-rows: auto auto;
    column-gap: 1.5rem;
    align-items: center;
    border-left-width: 8px;
  }

  .sensor-card__status-indicator {
    grid-row: span 2;
    width: 20px;
    height: 20px;
  }

  .sensor-card__body {
    grid-column: 2;
  }
}

/* Layout saat container sangat lebar */
@container sensorHost (min-width: 680px) {
  .sensor-card {
    grid-template-columns: auto 1.5fr 2fr;
    padding: 2rem;
  }

  .sensor-card__body {
    display: contents; /* Menghilangkan parent visual agar anak langsung berinteraksi dengan grid kartu */
  }

  .sensor-card__notes {
    border-left: 1px solid #3a3f58;
    padding-left: 1.5rem;
  }
}
```

---

### 13. Exercise

#### Level: Easy
1. Ubah deklarasi `clamp()` pada `.sensor-card__reading` agar memiliki batas bawah minimal `1.25rem` dan batas maksimal `2.25rem`. Pastikan interpolasinya tetap menggunakan unit `cqi`.
2. Tambahkan CSS fallback untuk browser lawas yang tidak mendukung `container-type` menggunakan directive `@supports not (container-type: inline-size)`.

#### Level: Medium
1. Bangun komponen `.pricing-matrix-tier` yang menggunakan `@container`.
2. Saat kontainer memiliki inline size di bawah `300px`, tampilkan daftar fitur kartu sebagai unordered list bertumpuk (*vertical list*).
3. Saat kontainer berada di antara `301px` dan `550px`, atur fitur ke dalam *2-column grid*.
4. Pada lebar kontainer $> 550px$, geser tombol Call to Action (CTA) ke sisi kanan bersebelahan secara horizontal dengan label harga, menggunakan *Fluid Spacing* (`padding: clamp(...)`).

#### Level: Hard
1. Buat sistem tipografi modular 5-tingkat (`--step--2` hingga `--step-2`) murni menggunakan ekspresi matematika CSS variables (`calc()` + `clamp()`).
2. Formula wajib menghitung skala modular dengan rasio *Major Third* (1.25) pada kontainer $1200px$, dan rasio *Minor Second* (1.067) pada kontainer $320px$.
3. Terapkan sistem variabel ini pada layout bersarang (*nested containers*), di mana parent container adalah `dashboard-panel`, dan child container adalah `widget-card`. Tunjukkan bahwa skala ukuran font di dalam anak sepenuhnya terisolasi dan tidak terpengaruh oleh manipulasi ukuran parent panel secara langsung.

---

### 14. Challenge

**Studi Kasus:** Anda adalah Lead Architect pada perusahaan FinTech Enterprise. Sistem Anda menyajikan komponen kompleks bernama *Stock-Order-Depth-Book*. 

**Ketentuan Desain & Batasan Arsitektural:**
1. Widget ini harus dapat disematkan ke dalam 3 container layout berbeda:
   - Panel modal *Flyout Drawer* ($280px \le \text{width} \le 380px$)
   - Grid Analytics Dashboard ($400px \le \text{width} \le 750px$)
   - Monitor Pro-Trader TV ($800px \le \text{width} \le 1600px$)
2. **Kondisi Khusus WCAG AAA**: Komponen harus mempertahankan skalabilitas visual tanpa memotong angka (*zero-clipping*) saat sistem disetel ke zoom 200%.
3. Dilarang menggunakan *CSS Framework* pihak ketiga (Tailwind/Bootstrap) dan dilarang menggunakan script JavaScript resize observer. Murni CSS Native.
4. **Tantangan Ekstrem**: Implementasikan kombinasi **Container Queries Style Queries** (`@container style(--theme = dark)`) atau fallback variable untuk mengubah skema palet kontras widget secara otonom saat variabel custom properti induknya berubah, di samping perubahan fisik geometri `inline-size`.

Dokumentasikan solusi Anda dalam file kode terpisah yang menyertakan analisis AST dan pemetaan containment tree.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Apa perbedaan mendasar antara `container-type: inline-size` dan `container-type: size`?**
   - A. `inline-size` hanya memonitor perubahan tinggi (*height*), sedangkan `size` memonitor lebar.
   - B. `inline-size` menerapkan containment pada sumbu horizontal (pada mode teks standar), sedangkan `size` menerapkan containment pada sumbu horizontal dan vertikal sekaligus.
   - C. `inline-size` mengizinkan konten anak menentukan lebar kontainer induk.
   - D. `inline-size` tidak mendukung unit kueri seperti `cqw`.
   *Jawaban:* B. `inline-size` mengevaluasi dimensi inline (lebar pada orientasi horizontal) tanpa memaksa isolasi dimensi blok.

2. **Mengapa unit `1cqw` bernilai setara dengan apa?**
   - A. 1% dari lebar browser window.
   - B. 1% dari tinggi kontainer terdekat.
   - C. 1% dari total inline size kontainer penampung terdekat yang memiliki context containment.
   - D. 10px flat rate.
   *Jawaban:* C. `cqw` merepresentasikan 1% dari lebar (width) dari query container context terdekat.

3. **Pada fungsi `clamp(MIN, VAL, MAX)`, kondisi apa yang menyebabkan browser memilih nilai `VAL`?**
   - A. Ketika nilai `VAL` lebih kecil daripada `MIN`.
   - B. Ketika nilai `VAL` berada di antara rentang nilai `MIN` dan `MAX`.
   - C. Ketika `MAX` tidak terdefinisi.
   - D. Hanya saat mode desktop aktif.
   *Jawaban:* B. `VAL` akan dieksekusi jika nilainya berada di dalam batas toleransi minimum dan maksimum.

4. **Apa dampak negatif jika kita mendeklarasikan Fluid Typography hanya menggunakan `font-size: clamp(1rem, 4vw, 2rem)` tanpa rem intersep?**
   - A. Halaman web menolak rendering di browser WebKit.
   - B. Membatalkan prinsip responsive design.
   - C. Melanggar aksesibilitas (WCAG) karena pembesaran teks via pengaturan browser (zoom) tidak merespons secara semestinya pada viewport tertentu.
   - D. Menyebabkan *infinite layout loop*.
   *Jawaban:* C. Tanpa percampuran unit berbasis preferensi pengguna (`rem`), kalkulasi viewport secara murni mengabaikan zoom level pengguna.

5. **Di mana kita harus mendeklarasikan `container-name` dan `container-type`?**
   - A. Pada elemen root `:root`.
   - B. Pada elemen induk (*ancestor/wrapper*) yang bertindak sebagai pembungkus komponen yang ditargetkan.
   - C. Tepat pada elemen leaf yang ingin diubah warnanya.
   - D. Di dalam blok media query `@media screen`.
   *Jawaban:* B. Containment context harus selalu dideklarasikan pada elemen induk dari target kueri.

#### Intermediate (5 Soal)
6. **Mengapa aturan CSS melarang kontainer bertipe `container-type: inline-size` memiliki dimensi inline yang ditentukan oleh `width: max-content`?**
   - A. Karena `max-content` memakan terlalu banyak alokasi memory GPU.
   - B. Karena hal tersebut menciptakan kontradiksi dependensi sirkular (*circular layout dependency*): ukuran kontainer memerlukan ukuran konten, namun layout konten menunggu kalkulasi kueri ukuran kontainer.
   - C. Karena properti `max-content` sudah usang (*deprecated*).
   - D. Karena akan menghasilkan error parsing CSSOM pada tahap lexical analysis.
   *Jawaban:* B. Dependensi sirkular adalah alasan fundamental mengapa browser membatasi kalkulasi intrinsik pada containment context.

7. **Perhatikan kode berikut:**
   ```css
   .wrapper-a { container: alpha / inline-size; }
   .wrapper-b { container: beta / inline-size; }
   @container (min-width: 500px) {
     .text { color: red; }
   }
   ```
   **Jika elemen `.text` berada di dalam `.wrapper-b`, dan `.wrapper-b` berada di dalam `.wrapper-a`, kontainer mana yang akan dievaluasi oleh query anonim di atas?**
   - A. `.wrapper-a`
   - B. `.wrapper-b`
   - C. Keduanya secara simultan.
   - D. Viewport global.
   *Jawaban:* B. Query tanpa nama (*unnamed container query*) secara otomatis mengikat dirinya ke *ancestor container* terdekat yang valid.

8. **Apa fungsi dari container query unit `cqi`?**
   - A. Mewakili 1% dari tinggi kontainer.
   - B. Mewakili 1% dari dimensi inline kontainer terdekat.
   - C. Mengukur resolusi layar per inch kontainer.
   - D. Mengambil nilai rata-rata dari width dan height kontainer.
   *Jawaban:* B. `cqi` adalah singkatan dari *Container Query Inline-size*, unit dinamis 1% sumbu inline.

9. **Bagaimana browser engine LayoutNG (Blink) mengoptimalkan performa halaman saat terjadi perubahan ukuran pada elemen bertanda `container-type: inline-size`?**
   - A. Mengirim operasi rendering ke Dedicated Web Worker.
   - B. Mengisolasi sub-tree layout: fase reflow dihentikan agar tidak merambat ke atas (*ancestor chain*), hanya memproses mutasi internal subtree kontainer.
   - C. Mengubah elemen tersebut secara otomatis menjadi bitmap canvas.
   - D. Melakukan hard-reload pada stylesheet document.
   *Jawaban:* B. Manfaat struktural dari layout containment adalah lokalisasi *Layout Tree Reflow*.

10. **Dalam kalkulasi interpolasi linear font: $y = y_1 + \left(\frac{y_2 - y_1}{x_2 - x_1}\right) \cdot (x - x_1)$, apa representasi dari $(x - x_1)$ pada runtime browser?**
    - A. Resolusi GPU pengguna.
    - B. Pergerakan delta antara ukuran aktual viewport/kontainer saat ini terhadap ambang batas bawah ($V_{\min}$).
    - C. Rasio pembagian pixel density device (DPI).
    - D. Nilai statis 1rem.
    *Jawaban:* B. Komponen ini merepresentasikan seberapa jauh layar telah membesar melampaui batas minimum yang ditentukan.

#### Production Scenarios (3 Skenario)

11. **Skenario 1:**
    Sebuah aplikasi web e-commerce mengalami lonjakan metrik **Cumulative Layout Shift (CLS)** yang signifikan setelah mengimplementasikan Fluid Typography berbasis `font-size: clamp(...)` pada judul produk di dalam list kartu. Setelah dianalisis menggunakan DevTools Performance Trace, font kustom berbasis *WebFont* lambat diunduh dan sistem fallback font standar memiliki metrik *x-height* yang sangat jauh berbeda dari web font utama.
    **Apa mitigasi teknis arsitektur CSS yang paling tepat untuk masalah ini tanpa membuang arsitektur fluid?**
    - A. Matikan fungsi `clamp()` dan gunakan fixed pixel.
    - B. Terapkan properti `@font-face { font-display: optional; }` dan sinkronisasikan metrik font fallback menggunakan CSS Font Metrics Overrides (`size-adjust`, `ascent-override`, `descent-override`) sehingga fallback font mengambil dimensi ruang yang identik dengan fluid target font saat fase *layout loading*.
    - C. Ubah `inline-size` kontainer menjadi fixed pixel via inline script.
    - D. Bungkus seluruh kartu dalam iframe terisolasi.
    *Evaluasi & Solusi:* Jawaban B adalah pendekatan production-grade terbaik. CLS terjadi akibat mismatch dimensional antar font saat kalkulasi fluid typography berjalan. Menyamakan font metrics via `size-adjust` secara tepat mengeliminasi pergeseran layout.

12. **Skenario 2:**
    Sebuah tim Micro-Frontend (MFE) mengintegrasikan widget mereka ke dalam dashboard platform utama. Saat diuji pada browser versi modern, kartu widget tidak me-render varian layout horizontal, meskipun ruang horizontal dashboard yang tersedia adalah 900px. Tim memeriksa kode CSS:
    ```css
    .widget-container { container-type: inline-size; }
    @container (min-width: 600px) {
      .widget-inner { display: flex; flex-direction: row; }
    }
    ```
    DOM host aplikasi induk membungkus widget tersebut dengan:
    ```html
    <div style="display: flex;">
      <div class="widget-container">...</div>
    </div>
    ```
    **Mengapa query container di atas tidak pernah terpenuhi (tetap pada varian mobile/vertikal)?**
    - A. Flexbox tidak mendukung elemen anak dengan container queries.
    - B. Elemen `.widget-container` berada di dalam flex parent tanpa deklarasi `flex-grow: 1` atau lebar eksplisit, sehingga ukuran default inline-size-nya runtuh menjadi minimum konten atau 0, yang tidak pernah melampaui ambang batas 600px.
    - C. `@container` tidak membaca flex context.
    - D. `container-type` harus diubah menjadi `block-size`.
    *Evaluasi & Solusi:* Jawaban B. Karena `container-type: inline-size` melarang browser mengalkulasi intrinsic sizing secara bebas pada kontainer tanpa arahan flex layout yang jelas, `.widget-container` tidak merenggang secara otomatis jika flex parent tidak menginstruksikannya (misal via `flex: 1` atau `width: 100%`).

13. **Skenario 3:**
    Dalam audit kepatuhan aksesibilitas perbankan, ditemukan bahwa sistem fluid typography berbasis formula:
    ```css
    font-size: clamp(1rem, 2.5cqi, 1.75rem);
    ```
    Gagal memenuhi kriteria *Success Criterion 1.4.4 Resize Text* ketika diuji di browser tanpa zooming layar penuh (hanya mode *Text-Only Zoom* aktif di Firefox).
    **Bagaimana arsitek CSS harus merevisi formula token ini agar compliant secara mutlak?**
    - A. Mengganti unit `cqi` menjadi `cqw`.
    - B. Mengombinasikan formula intersep dinamis dengan unit teks dasar: `clamp(1rem, 0.75rem + 1.5cqi, 1.75rem)`, sehingga porsi `0.75rem` tetap menjadi jangkar yang merespons penggandaan font browser pengguna saat mode Text Zoom diaktifkan.
    - C. Menghapus `clamp()` dan mengandalkan media queries berbasis `em`.
    - D. Menambahkan JavaScript untuk mendengarkan perubahan teks dan menyuntikkan inline styles.
    *Evaluasi & Solusi:* Jawaban B. Mode *Text-Only Zoom* murni memanipulasi nilai resolusi `1rem` tanpa mengubah resolusi viewport ataupun container dimensions. Jika nilai `cqi` berdiri sendiri dalam formula tengah, teks tidak akan membesar secara proporsional. Menyertakan unit `rem` dalam ekspresi penjumlahan adalah mandatory pattern aksesibilitas.

---

### 16. Summary

1. **Fluid Responsive Typography** memodernisasi cara penanganan teks di web dari sistem diskrit (*breakpoint jumping*) menjadi fungsi kontinu terprediksi. Penggunaan `clamp(MIN, Intercept + Slope, MAX)` wajib menyertakan unit `rem` sebagai intersep penahan aksesibilitas (*WCAG 1.4.4 compliance*).
2. **Container Queries (`@container`)** mentransformasikan arsitektur komponen web dari yang sebelumnya terikat global (*Viewport-dependent*) menjadi modular, otonom, dan agnostik layout (*Context-dependent*).
3. **Mekanisme Layout Containment** diterapkan oleh browser pada elemen dengan `container-type: inline-size` untuk mengisolasi proses reflow layout tree dan mencegah *infinite layout loops*. Hal ini mewajibkan kontainer mendapatkan dimensi inline-nya secara ekstrinsik.
4. Pada skala enterprise, gabungan antara **Container Queries** dan **Fluid Mathematical Tokens** merupakan fondasi arsitektur frontend modern yang menjamin skalabilitas, kecepatan eksekusi render, portabilitas Micro-Frontend, dan portabilitas Design System di berbagai form-factor layar.