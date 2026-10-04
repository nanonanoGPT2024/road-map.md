# SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Topik:** css
* **Bab:** 05
* **Module:** 01
* **Judul/Topik:** Fluid Responsive Typography & Container Queries
* **Level Kompleksitas:** Advanced / Staff Engineer Core
* **Prasyarat:** CSS Grid Level 2, Flexbox, CSS Custom Properties (Variables), Relative Units (`rem`, `em`, `ch`), Viewport Units (`vw`, `vh`, `vi`, `vb`), CSS Box Model.

---

# SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. **Merancang Mathematical Font Scaling System:** Mengimplementasikan tipografi fluid bebas *media query steps* menggunakan fungsi matematis CSS (`clamp()`, `calc()`, `min()`, `max()`) yang terikat pada skala modular linier dan kurva rasio viewport.
2. **Membedah Mekanisme Browser Formatting Engine:** Memahami bagaimana Layout Engine (Blink/Gecko/WebKit) mengkalkulasi *used values* tipografi, menghindari siklus layout thrashing, dan mempertahankan aksesibilitas WCAG 2.2 SC 1.4.4 (*Resize Text*).
3. **Menguasai Spesifikasi CSS Container Queries (Size & Style):** Mengatur konteks penahanan layout (`container-type`, `container-name`) dan memanfaatkan unit berbasis kontainer (`cqw`, `cqh`, `cqi`, `cqb`, `cqmin`, `cqmax`) untuk decoupling komponen UI dari viewport global.
4. **Menerapkan Advanced Micro-Layouts:** Memadukan fluid sizing dengan *container queries* untuk membangun pola arsitektur *Intrinsically Responsive Components* tanpa ketergantungan pada JavaScript ResizeObserver.
5. **Mitigasi Edge Cases Produksi:** Menghindari *infinite containment loops*, layout instability (CLS), dan degradasi performa render pipeline saat puluhan sub-kontainer bersarang (*nested containers*) dirender secara dinamis.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Macro-Responsive ke Micro-Responsive
Selama lebih dari satu dekade, desain web terperangkap dalam mentalitas berbasis viewport (*Macro-Responsive Design*). Media queries (`@media (min-width: 768px)`) mengasumsikan bahwa dimensi jendela browser mencerminkan ruang yang tersedia bagi setiap komponen individual di dalam pohon DOM. Pendekatan ini rusak ketika sistem antarmuka modern berevolusi menjadi arsitektur berbasis komponen (*design systems*, micro-frontends).

Sebuah komponen kartu informasi (`Card`) yang sama dapat ditempatkan pada:
- Kolom penuh pada layar mobile ($375\text{px}$).
- Sidebar kanan pada layar desktop ($300\text{px}$).
- Grid 3-kolom pada layar desktop ($400\text{px}$).

Jika komponen mengandalkan `@media`, kartu di dalam sidebar desktop akan mengasumsikan layar desktop lebar dan meledak secara visual, merusak ritme vertikal. *Container Queries* membalikkan relasi ketergantungan ini (*Micro-Responsive Design*): **Komponen merespons ruang yang dialokasikan oleh parent-nya, bukan ukuran jendela peramban pengguna.**

```
[ Mental Model Tradisional ]
Viewport -> Memaksakan layout ke Parent -> Memaksakan layout ke Komponen (Kaku/Coupled)

[ Mental Model Modern (Intrinsic & Containment) ]
Viewport -> Menyediakan kanvas -> Parent mengalokasikan ruang
Komponen membaca ruang alokasi (Container) -> Menentukan fluiditas tipografi & layout sendiri (Decoupled)
```

### Mental Model Tipografi: Stepped Breakpoints vs. Fluid Interpolation
Tipografi konvensional menggunakan *stepped breakpoint*: teks melompat dari $16\text{px}$ ke $18\text{px}$ pada $768\text{px}$, lalu melompat ke $24\text{px}$ pada $1024\text{px}$. Lompatan ini menghasilkan visual jerk dan mengharuskan pemeliharaan breakpoint CSS yang berlebihan. 

Mental model tipografi *fluid* memandang ukuran font ($y$) sebagai fungsi linier dari dimensi ruang ($x$):
$$y = mx + c$$
di mana font berinterpolasi secara kontinu di antara batas bawah ($y_{\min}$) dan batas atas ($y_{\max}$), terisolasi di dalam domain kontainer atau viewport tertentu, lalu dikunci menggunakan operator pemotongan batas (`clamp()`).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Evaluasi Container Query & Typography Interpolation

```
+-----------------------------------------------------------------------------+
| Browser Parser & DOM Tree Construction                                     |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| CSSOM: Menemukan 'container-type: inline-size'                             |
| Engine menginisialisasi Size Containment pada Node Induk                    |
| (Mencegah siklus: Anak tidak boleh mengubah lebar/inline-size Induk)        |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| Layout Phase: Induk dialokasikan Computed Inline-Size (misal: 640px)        |
| Unit 'cqi' diaktifkan: 1cqi = 640px / 100 = 6.4px                           |
+-----------------------------------------------------------------------------+
                                      |
                                      +---------------------------------------+
                                      |                                       |
                                      v                                       v
        +-------------------------------------------+       +-----------------------------------+
        | Evaluasi @container Rules                 |       | Evaluasi Fluid Typography         |
        | @container (min-width: 500px) -> TRUE     |       | clamp(1rem, 0.5rem + 2cqi, 2rem)  |
        | Terapkan overrides (misal: grid multi-kolom)|     | Hitung: 0.5rem(8px) + 2*6.4px     |
        +-------------------------------------------+       |        = 20.8px                   |
                                      |                     | Bandingkan dengan Min & Max       |
                                      |                     | Return used value: 20.8px         |
                                      |                     +-----------------------------------+
                                      \                                       /
                                       \-------------------------------------/
                                                          |
                                                          v
                                    +-------------------------------------------+
                                    | Text Layout & Glyph Shaping (HarfBuzz)    |
                                    | Penempatan karakter sesuai used font-size |
                                    +-------------------------------------------+
                                                          |
                                                          v
                                    +-------------------------------------------+
                                    | Paint & Compositing Pipeline              |
                                    +-------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi Primitif `clamp()`
Fungsi `clamp(MIN, VAL, MAX)` secara semantik ekuivalen dengan ekspresi:
$$\max(\text{MIN}, \min(\text{VAL}, \text{MAX}))$$
Kunci mekanismenya terletak pada parameter:
- **`MIN` (Batas Bawah):** Nilai absolut minimum yang diizinkan (biasanya menggunakan satuan `rem` untuk menghormati preferensi font OS/browser pengguna).
- **`VAL` (Ideal/Dynamic Rate):** Nilai skalar yang mengandung unit relatif dimensi kontainer atau viewport (`cqi`, `cqw`, `vi`, `vw`), dikombinasikan dengan basis statis (`rem`) menggunakan `calc()`.
- **`MAX` (Batas Atas):** Nilai absolut maksimum yang diizinkan sebelum skala font berhenti membesar.

### 2. Formulasi Matematika Interpolasi Tipografi Linier
Untuk menghasilkan skala font yang bertransisi secara mulus tepat dari ukuran $F_{\min}$ pada kontainer $C_{\min}$ ke ukuran $F_{\max}$ pada kontainer $C_{\max}$, kita menurunkan persamaan garis lurus:

$$\text{Slope } (m) = \frac{F_{\max} - F_{\min}}{C_{\max} - C_{\min}}$$

$$\text{Y-Intercept } (b) = F_{\min} - (m \times C_{\min})$$

$$\text{Ideal Value} = b + (m \times 100)\text{cqi}$$

Sehingga implementasi akhir dalam CSS:
```css
font-size: clamp(F_min, b + (m * 100) * 1cqi, F_max);
```

### 3. Mekanisme Containment Browser Engine
Ketika properti `container-type: inline-size` dideklarasikan:
- **Layout Containment:** Elemen mematikan pengaruh rendering geometri internalnya terhadap leluhur (ancestor). Anak-anak elemen tidak dapat memengaruhi dimensi lebar elemen itu sendiri.
- **Size Containment (Inline-Axis):** Dimensi *inline* elemen harus dapat dihitung sebelum layout anak-anaknya dihitung. Mesin browser mengabaikan konten anak saat menghitung ukuran inline dari kontainer guna menghindari dependensi siklis (*circular dependency*).

Jika sebuah elemen memiliki anak yang menggunakan `@container` yang memodifikasi ukuran elemen anak sehingga mengubah ukuran kontainer induknya, hal tersebut akan memicu *infinite layout loop*. Maka dari itu, browser secara ketat memutus loop ini pada fase spesifikasi: **Size containment mencegah konten mempengaruhi ukuran kontainer pada aksis yang ditentukan**.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Perbedaan Semantik Satuan Ukuran Kontainer
CSS Container Queries Level 3 memperkenalkan sistem unit baru yang dihitung berdasarkan ukuran *query container*:

| Unit | Definisi Relatif | Aksis Operasional |
| :--- | :--- | :--- |
| `cqw` | $1\%$ dari lebar (*width*) query container | Sumbu horizontal fisik |
| `cqh` | $1\%$ dari tinggi (*height*) query container | Sumbu vertikal fisik |
| `cqi` | $1\%$ dari ukuran inline (*inline-size*) query container | Sumbu logis (arah baca teks: horizontal pada LTR/RTL) |
| `cqb` | $1\%$ dari ukuran blok (*block-size*) query container | Sumbu logis (arah tumpukan paragraf) |
| `cqmin`| Nilai terkecil antara `cqi` dan `cqb` | Ekivalen adaptif |
| `cqmax`| Nilai terbesar antara `cqi` dan `cqb` | Ekivalen adaptif |

> **Rekomendasi Arsitektural:** Selalu gunakan `cqi` (bukan `cqw`) untuk teks dan elemen layout horizontal untuk mendukung internasionalisasi (*writing-mode: vertical-rl* atau *horizontal-tb*) secara mulus.

### Anatomi `container-type`
1. `container-type: normal` (Default): Elemen bukan query container untuk *size queries*, namun tetap dapat menjadi query container untuk *style queries* (variabel CSS).
2. `container-type: inline-size`: Menerapkan containment pada sumbu inline. Elemen induk dapat di-query berdasarkan lebarnya (pada mode horizontal), sementara tingginya tetap bebas bertambah secara intrinsik mengikuti ketinggian konten anak.
3. `container-type: size`: Menerapkan containment pada kedua sumbu (inline dan block). **Perhatian:** Elemen kontainer harus memiliki dimensi tinggi eksplisit (`height`, `block-size`), jika tidak, tingginya akan kolaps menjadi $0$, karena anak-anaknya dilarang memberikan kontribusi dimensi tinggi kepada induknya.

### Style Queries vs Size Queries
Size query mengevaluasi geometri dimensi:
```css
@container (min-width: 400px) { ... }
```
Style query mengevaluasi *computed value* dari properti CSS induk (saat ini didukung terutama untuk CSS custom properties):
```css
@container style(--theme: dark) { ... }
@container style(--variant: highlighted) { ... }
```
Ini membuka kapabilitas *context-aware styles* murni berbasis CSS tanpa manipulasi kelas DOM oleh JavaScript.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi sistem token skala modular tipografi fluid linier murni yang dikombinasikan dengan deklarasi kontainer.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Fluid Typography & Container Queries Core</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <!-- Container Boundary Induk -->
  <main class="dashboard-shell">
    <section class="card-wrapper">
      <article class="adaptive-card">
        <span class="card-badge">Staff Feature</span>
        <h2 class="card-title">Optimalisasi Layout Engine Tingkat Rendah</h2>
        <p class="card-body">
          Container Queries memisahkan logika tata letak modular dari viewport browser global,
          menghadirkan modularitas komponen UI sejati pada skala enterprise.
        </p>
      </article>
    </section>
  </main>
</body>
</html>
```

```css
/* style.css */

/* -------------------------------------------------------------
 * 1. Root Tokens & Global Settings
 * ----------------------------------------------------------- */
:root {
  --font-sans: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --bg-surface: #0f172a;
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --accent: #38bdf8;
}

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: var(--font-sans);
  background-color: #020617;
  color: var(--text-primary);
  line-height: 1.5;
  padding: 2rem;
}

/* -------------------------------------------------------------
 * 2. Formulasi Fluid Typography Tokens (Basis: Kontainer)
 * Target: 
 * - Min Inline-Size: 320px (20rem)  -> Font Size: 18px (1.125rem)
 * - Max Inline-Size: 960px (60rem)  -> Font Size: 32px (2rem)
 * Slope (m) = (32 - 18) / (960 - 320) = 14 / 640 = 0.021875
 * Intersection (b) = 18 - (0.021875 * 320) = 18 - 7 = 11px = 0.6875rem
 * Slope in % = 0.021875 * 100 = 2.1875cqi
 * ----------------------------------------------------------- */
:root {
  --fluid-h2-min: 1.125rem;
  --fluid-h2-max: 2rem;
  --fluid-h2-ideal: 0.6875rem + 2.1875cqi;
}

/* -------------------------------------------------------------
 * 3. Container Context Definition
 * ----------------------------------------------------------- */
.card-wrapper {
  /* Membuka context container pada axis inline */
  container-type: inline-size;
  container-name: card-slot;
  
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  resize: horizontal; /* Memungkinkan interaksi resize manual untuk demonstrasi */
  overflow: hidden;
  border: 1px dashed #334155;
  padding: 1.5rem;
  border-radius: 12px;
}

/* -------------------------------------------------------------
 * 4. Component Rules Mengonsumsi Unit Kontainer & Interpolasi
 * ----------------------------------------------------------- */
.adaptive-card {
  background-color: var(--bg-surface);
  border-radius: 8px;
  padding: clamp(1rem, 0.5rem + 2cqi, 2.5rem);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.card-title {
  /* Menerapkan Tipografi Fluid murni terikat ke card-slot */
  font-size: clamp(var(--fluid-h2-min), var(--fluid-h2-ideal), var(--fluid-h2-max));
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.card-badge {
  align-self: flex-start;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--accent);
}

.card-body {
  color: var(--text-secondary);
  font-size: clamp(0.875rem, 0.75rem + 0.5cqi, 1.125rem);
}

/* -------------------------------------------------------------
 * 5. Explicit Container Queries (Structural Mutation)
 * ----------------------------------------------------------- */
@container card-slot (min-width: 600px) {
  .adaptive-card {
    display: grid;
    grid-template-columns: 1fr 2fr;
    grid-template-areas: 
      "badge title"
      ".     body";
    align-items: start;
    column-gap: 2rem;
  }

  .card-badge {
    grid-area: badge;
  }

  .card-title {
    grid-area: title;
  }

  .card-body {
    grid-area: body;
  }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Blok 2: Formulasi Matematika Token Tipografi
- `var(--fluid-h2-ideal): 0.6875rem + 2.1875cqi;`: Memformulasikan $y$-intercept ($0.6875\text{rem}$ atau $11\text{px}$) ditambah kemiringan kurva per unit kontainer ($2.1875\text{cqi}$). Unit `rem` dipertahankan pada konstanta intercept agar ketika user memperbesar ukuran font bawaan browser (misal $32\text{px}$ dari normalnya $16\text{px}$), titik pangkal tipografi tetap menghormati preferensi aksesibilitas tersebut.

### Analisis Blok 3: Inisialisasi Isolasi Ukuran
- `container-type: inline-size;`: Menginstruksikan Layout Engine untuk mengisolasi perhitungan dimensi inline elemen `.card-wrapper`. Mesin browser tidak akan menunggu `.adaptive-card` selesai dihitung untuk menentukan lebar `.card-wrapper`.
- `container-name: card-slot;`: Memberi nama unik untuk namespace query konteks ini. Hal ini krusial saat terdapat *nested containers* agar komponen di dalam tidak keliru membaca ukuran container terluar.

### Analisis Blok 4: Implementasi Fluid Clamp
- `font-size: clamp(var(--fluid-h2-min), var(--fluid-h2-ideal), var(--fluid-h2-max));`: Browser memproses fungsi pemotongan:
  - Jika kontainer berukuran $300\text{px}$, maka $11\text{px} + (0.021875 \times 300) = 17.56\text{px}$. Karena $17.56\text{px} < 18\text{px}$ (`--fluid-h2-min`), maka browser memilih $18\text{px}$ ($1.125\text{rem}$).
  - Jika kontainer berukuran $640\text{px}$, maka $11\text{px} + (0.021875 \times 640) = 25\text{px}$. Nilai ini berada di antara $18\text{px}$ dan $32\text{px}$, sehingga used value dieksekusi tepat pada $25\text{px}$.
  - Jika kontainer berukuran $1200\text{px}$, maka nilainya $37.25\text{px}$. Browser langsung memotongnya pada batas maksimum $32\text{px}$ ($2\text{rem}$).

### Analisis Blok 5: Micro-Responsive Layout Mutator
- `@container card-slot (min-width: 600px)`: Mengkueri dimensi kontainer bernama `card-slot`. Aturan ini **hanya** aktif jika kontainer induk mencapai lebar $\ge 600\text{px}$, sepenuhnya independen dari ukuran monitor ataupun orientasi perangkat viewport pengguna. Komponen bertransformasi secara instan dari single-column Flexbox menjadi asymmetric CSS Grid.

---

# SEKSI 09 — STUDI KASUS NYATA
### Masalah Produksi: Enterprise Analytics Multi-Tenant Dashboard
Sebuah platform analitik finansial SaaS memiliki arsitektur dashboard berbasis *drag-and-drop widget*. Pengguna dapat menata widget metrik transaksi ("Revenue Analytics") ke dalam berbagai slot tata letak:
1. **Full-Width Canvas Area** ($1200\text{px}$ lebar).
2. **Split Split-Screen Column** ($600\text{px}$ lebar).
3. **Collapsible Sidebar Inspector** ($280\text{px}$ lebar).

### Kegagalan Solusi Tradisional
Pengembang sebelumnya menggunakan media queries `@media (min-width: 768px)`. Ketika dashboard dibuka di layar iMac $27\text{ inci}$ (Viewport lebar $2560\text{px}$), widget analitik yang disematkan di dalam Collapsible Sidebar ($280\text{px}$) memicu breakpoint desktop. Akibatnya:
- Teks judul metrik meledak menjadi $36\text{px}$, memotong teks (*text truncation* parah).
- Grafik tabular dipaksa render horizontal $4\text{ kolom}$, menghasilkan overflow horizontal di dalam sidebar kecil tersebut.
- Menciptakan inkonsistensi layout masif dan tiket komplain visual dari pengguna korporat.

### Solusi Arsitektur
Membangun widget modular mandiri menggunakan gabungan **Container Size Queries** untuk layout mutasi internal, dan **Fluid Math Scale** berbasis `cqi` untuk memastikan tipografi headline, data metrics, dan subtext beradaptasi secara matematis terhadap lebar slot widget mana pun ia ditempatkan, tanpa satupun baris JavaScript ResizeObserver.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistem komponen Analytics Widget produksi tinggi menggunakan SCSS/Modern CSS nesting, arsitektur token tipografi cairan bertingkat, dan perlindungan layout overflow.

```html
<div class="dashboard-grid">
  <!-- Slot Sidebar Sempit -->
  <aside class="dashboard-region" style="width: 300px;">
    <div class="widget-mount" data-widget="revenue">
      <div class="kpi-widget">
        <header class="kpi-header">
          <span class="kpi-label">MRR Growth</span>
          <span class="kpi-tag kpi-tag--positive">+14.2%</span>
        </header>
        <div class="kpi-display">
          <span class="kpi-currency">$</span>
          <span class="kpi-value">124,592</span>
        </div>
        <footer class="kpi-meta">
          Berdasarkan 30 hari penagihan terakhir dibandingkan kuartal sebelumnya.
        </footer>
      </div>
    </div>
  </aside>

  <!-- Slot Canvas Lebar -->
  <main class="dashboard-region" style="flex: 1;">
    <div class="widget-mount" data-widget="revenue">
      <div class="kpi-widget">
        <header class="kpi-header">
          <span class="kpi-label">MRR Growth</span>
          <span class="kpi-tag kpi-tag--positive">+14.2%</span>
        </header>
        <div class="kpi-display">
          <span class="kpi-currency">$</span>
          <span class="kpi-value">124,592</span>
        </div>
        <footer class="kpi-meta">
          Berdasarkan 30 hari penagihan terakhir dibandingkan kuartal sebelumnya.
        </footer>
      </div>
    </div>
  </main>
</div>
```

```css
/* ==========================================================================
   ENTERPRISE CONTAINER SYSTEM TOKENS & TYPOGRAPHY ENGINE
   ========================================================================== */

:root {
  --color-slate-950: #020617;
  --color-slate-900: #0f172a;
  --color-slate-800: #1e293b;
  --color-slate-400: #94a3b8;
  --color-slate-100: #f1f5f9;
  --color-emerald-400: #34d399;
  --color-emerald-950: #064e3b;
}

.dashboard-grid {
  display: flex;
  gap: 1.5rem;
  background-color: var(--color-slate-950);
  min-height: 100vh;
  padding: 2rem;
  color: var(--color-slate-100);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.dashboard-region {
  background: var(--color-slate-900);
  border: 1px solid var(--color-slate-800);
  border-radius: 12px;
  padding: 1.5rem;
}

/* --------------------------------------------------------------------------
   WIDGET CONTAINER ISOLATION BOUNDARY
   -------------------------------------------------------------------------- */
.widget-mount {
  /* Menerapkan size containment pada inline-axis untuk decoupling */
  container-type: inline-size;
  container-name: widget-container;
  width: 100%;
}

/* --------------------------------------------------------------------------
   KPI WIDGET COMPONENT (Encapsulated)
   -------------------------------------------------------------------------- */
.kpi-widget {
  background-color: var(--color-slate-800);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  
  /* Padding elastis berbasis cqi: min 12px, max 32px */
  padding: clamp(0.75rem, 0.5rem + 1.5cqi, 2rem);
  gap: clamp(0.5rem, 0.25rem + 1cqi, 1.25rem);
  transition: border-color 0.2s ease;
}

.kpi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.kpi-label {
  font-weight: 600;
  color: var(--color-slate-400);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  /* Fluid label size: min 11px, max 14px */
  font-size: clamp(0.6875rem, 0.625rem + 0.35cqi, 0.875rem);
}

.kpi-tag {
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-weight: 700;
  font-size: clamp(0.6875rem, 0.625rem + 0.35cqi, 0.8125rem);
}

.kpi-tag--positive {
  background-color: var(--color-emerald-950);
  color: var(--color-emerald-400);
}

/* Angka Metrik: Perlu interpolasi drastis namun aman dari line breaking */
.kpi-display {
  display: flex;
  align-items: baseline;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.kpi-currency {
  color: var(--color-slate-400);
  font-weight: 400;
  /* Dihitung 50% dari ukuran font metrik */
  font-size: clamp(1rem, 0.5rem + 2cqi, 2rem);
  margin-right: 0.25rem;
}

.kpi-value {
  font-weight: 800;
  letter-spacing: -0.03em;
  /* Fluid scaling: 24px pada 250px container -> 64px pada 800px container */
  /* Slope: (64 - 24) / (800 - 250) = 40 / 550 = 0.0727 */
  /* Intercept: 24 - (0.0727 * 250) = 5.82px = 0.363rem */
  font-size: clamp(1.5rem, 0.363rem + 7.27cqi, 4rem);
}

.kpi-meta {
  color: var(--color-slate-400);
  font-size: clamp(0.75rem, 0.7rem + 0.25cqi, 0.875rem);
  line-height: 1.4;
}

/* --------------------------------------------------------------------------
   MACRO SHIFT VIA CONTAINER QUERIES (Structural Mutation)
   Ketika widget ditempatkan pada slot dengan ruang inline memadai
   -------------------------------------------------------------------------- */
@container widget-container (min-width: 480px) {
  .kpi-widget {
    display: grid;
    grid-template-columns: 1fr auto;
    grid-template-rows: auto auto;
    align-items: center;
  }

  .kpi-header {
    grid-column: 1 / 2;
    grid-row: 1 / 2;
    justify-content: flex-start;
    gap: 1rem;
  }

  .kpi-display {
    grid-column: 1 / 2;
    grid-row: 2 / 3;
  }

  .kpi-meta {
    grid-column: 2 / 3;
    grid-row: 1 / 3;
    max-width: 180px;
    text-align: right;
    border-left: 1px solid var(--color-slate-800);
    padding-left: 1.5rem;
  }
}

@container widget-container (min-width: 700px) {
  .kpi-meta {
    max-width: 260px;
    font-size: 0.9375rem;
  }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektur | Media Queries (`@media`) | Fluid Math Viewport (`clamp() + vw`) | Container Queries (`@container` & `cqi`) |
| :--- | :--- | :--- | :--- |
| **Konteks Referensi** | Dimensi Jendela/Monitor Browser Global | Jendela Browser Global | Elemen Induk Langsung/Tertentu (Ancestor terdekat) |
| **Modularitas Komponen** | **Rendah**: Komponen terikat erat (*tightly-coupled*) dengan layout halaman | **Rendah**: Sizing tidak memperhitungkan nesting komponen | **Tinggi**: Komponen terisolasi (*fully decoupled* & context-agnostic) |
| **Overhead Rendering** | Rendah: Evaluasi sekali pada breakpoint viewport resize | Nol layout phase overhead: Murni kalkulasi ekspresi CSSOM | Sedang: Browser harus membangun konteks *containment* per-node |
| **Aksesibilitas (Zoom)** | Mudah dikontrol melalui satuan `rem` statis | **Rentan**: Penggunaan `vw` murni merusak zoom 200% WCAG | **Aman**: Selama dikombinasikan dengan basis `rem` di dalam `clamp()` |
| **Kompleksitas CSS** | Sedang: Banyak redundansi rules antar breakpoint | Rendah: Rumus matematika deklaratif ringkas | Sedang-Tinggi: Perlu manajemen hierarki penamaan kontainer |
| **Dukungan Legacy** | Global (Sejak IE9+) | Global (Evergreen Browser) | Modern (Chrome 105+, Firefox 110+, Safari 16+) |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Loop Penahanan Tak Hingga (Infinite Layout Loops)
* **Skenario:** Menggunakan `container-type: size` pada kontainer yang tingginya bergantung pada tinggi konten anak, sementara teks anak menggunakan ukuran berbasis unit tinggi kontainer (`cqh` atau `cqb`).
* **Mekanisme Kegagalan:** 
  1. Konten teks menentukan tinggi kontainer.
  2. Kontainer mengevaluasi tinggi konten dan mengupdate tingginya.
  3. Kueri kontainer membaca tinggi baru dan memperbesar `font-size`.
  4. Ukuran teks membesar, mendorong tinggi kontainer lebih tinggi lagi.
  5. Browser mendeteksi siklus tanpa henti (*infinite cyclic layout reflow*).
* **Mitigasi:** Standar CSS mengatasi ini secara defensif dengan mereset dimensi ke 0 jika terjadi dependensi siklis. Namun aturan produksi terbaik: **Gunakan secara konsisten `container-type: inline-size`**, bukan `size`, kecuali jika elemen kontainer memiliki nilai tinggi statis (`height: 100vh` atau `height: 500px`).

### 2. Isu Aksesibilitas WCAG 2.2 Kriteria Keberhasilan 1.4.4 (*Resize Text*)
* **Skenario:** Menulis formula fluid murni dengan unit dinamis: `font-size: clamp(12px, 5cqi, 32px)`.
* **Mekanisme Kegagalan:** Saat pengguna tunanetra menekan `Ctrl/Cmd + Plus` untuk zoom browser hingga $200\%$, browser memperbesar skala basis `1rem`. Karena formula di atas hanya menggunakan `px` dan `cqi`, ukuran font sama sekali menolak membesar. Hal ini merupakan pelanggaran hukum aksesibilitas level