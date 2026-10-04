## SEKSI 01 — IDENTITAS MODUL

* **Track:** Frontend Development Beginner
* **Kategori:** 01-Core-Foundations
* **Bab:** 03 — Fondasi CSS3: Box Model, Specificity & Rendering Pipeline
* **Modul:** 01 — Box Model, Specificity & Critical Rendering Path
* **Prasyarat:** HTML5 Semantic Structure, Document Tree & DOM Basics
* **Estimasi Waktu:** 120 Menit (Teori: 45 Menit, Praktik: 75 Menit)
* **Level Kesulitan:** Beginner to Intermediate

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Mengkalkulasi Dimensi Box Model:** Membedakan secara matematis perilaku `content-box` versus `border-box`, serta mengidentifikasi fenomena *margin collapsing* pada flow dokumen normal.
2. **Menghitung dan Menyelesaikan Konflik CSS Specificity:** Menghitung bobot spesifisitas selector menggunakan matriks `(Inline, ID, Class/Attribute/Pseudo-class, Element/Pseudo-element)` dan menerapkan cascade resolution tanpa bergantung pada anti-pattern `!important`.
3. **Memetakan Browser Critical Rendering Path (CRP):** Menjelaskan siklus hidup rendering peramban (*DOM + CSSOM $\to$ Render Tree $\to$ Layout/Reflow $\to$ Paint $\to$ Composite*) serta membedakan properti CSS yang memicu *reflow*, *repaint*, atau *composite-only*.
4. **Membangun Komponen UI Berperforma Tinggi:** Mengimplementasikan styling komponen antarmuka yang tahan regresi visual, modular, dan teroptimasi secara performa runtime browser.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
                               FONDASI CSS3
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
    BOX MODEL                   SPECIFICITY               RENDERING PATH
  (Geometri Elemen)           (Resolusi Konflik)         (Pipeline Eksekusi)
         │                           │                           │
  ├── Content Area            ├── Specificity Weight      ├── DOM Tree Construction
  ├── Padding Box             │   (a, b, c, d)            ├── CSSOM Tree Construction
  ├── Border Box              ├── Cascade Origin          ├── Render Tree Construction
  ├── Margin Box              │   (Author, User, UA)      ├── Layout / Reflow
  │   └── Margin Collapsing   ├── Source Order            ├── Paint (Rasterization)
  └── box-sizing Switch       └── The `!important` Trap  └── Composite (GPU Layers)
      ├── content-box
      └── border-box
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Banyak pengembang web pemula memandang CSS sebagai bahasa penataan visual sederhana berbasis *trial-and-error*. Pola pikir ini mengarah pada tiga masalah fatal dalam skala produksi:

1. **Layout Fragility:** Menambahkan padding atau border sebesar `1px` merusak susunan grid atau mematahkan baris navigasi karena ketidaktahuan kalkulasi default `box-sizing: content-box`.
2. **Specificity Wars:** Ketika sebuah style tidak terpasang, solusi pintas adalah menambahkan selector berantai panjang atau menyematkan flag `!important`. Dalam tim lintas fungsi, ini menciptakan utang teknis (*technical debt*) di mana developer harus terus menimpa style sebelumnya dengan selector yang makin rumit.
3. **UI Jank & Micro-stuttering:** Mengubah properti visual seperti `top`, `left`, `width`, atau `margin` pada animasi memicu kalkulasi ulang geometri (*Layout/Reflow*) pada 60 frame per detik (fps). Browser kehabisan waktu budget frame (16.67ms), mengakibatkan animasi patah-patah (*jank*) dan konsumsi baterai perangkat membengkak.

Menguasai Box Model, Specificity, dan Rendering Pipeline mengubah CSS dari aksi tebak-tebakan menjadi disiplin rekayasa perangkat lunak yang presisi dan berperforma tinggi.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. The CSS Box Model
Setiap elemen di dalam dokumen HTML dibungkus oleh sebuah kotak persegi (*rectangular box*) yang terdiri dari empat lapisan konsentris:
* **Content:** Area inti tempat teks, gambar, atau elemen anak dirender.
* **Padding:** Area transparan yang memisahkan konten dari border; berada di dalam background elemen.
* **Border:** Garis pembatas yang membungkus padding dan konten.
* **Margin:** Ruang kosong terluar yang memisahkan elemen ini dari elemen sekitarnya di layout. Margin dapat mengalami *collapsing* secara vertikal.

### 2. Specificity & The Cascade
Cascade adalah algoritma yang menentukan nilai deklarasi mana yang diterapkan pada elemen saat terjadi benturan properti CSS. Salah satu faktor penentu terpenting adalah **Specificity** (Tingkat Kekhususan).

Spesifisitas dihitung sebagai 4 komponen terpisah (sering direpresentasikan sebagai tuple atau matriks `(a, b, c, d)`):
* **a (Inline Styles):** Deklarasi langsung pada atribut HTML `style="..."`.
* **b (IDs):** Penggunaan ID selector, misal `#header`.
* **c (Classes, Attributes, Pseudo-classes):** Class selector (`.card`), attribute selector (`[type="text"]`), dan pseudo-class (`:hover`, `:first-child`).
* **d (Elements & Pseudo-elements):** Type/tag selector (`div`, `p`, `h1`) dan pseudo-element (`::before`, `::after`).

> **Catatan Algoritmik:** Universal selector (`*`), combinator (`+`, `>`, `~`, ` `), dan pseudo-class penyeimbang seperti `:where()` memiliki nilai spesifisitas `(0, 0, 0, 0)`. Pseudo-class `:is()` dan `:not()` mengambil nilai spesifisitas tertinggi dari argumen di dalamnya.

### 3. Critical Rendering Path (CRP)
Siklus peramban web dari menerima berkas HTML & CSS hingga memetakan pixel ke monitor:
1. **DOM (Document Object Model):** Konversi token HTML menjadi representasi struktur pohon node.
2. **CSSOM (CSS Object Model):** Konversi aturan CSS menjadi struktur pohon aturan styling terindeks.
3. **Render Tree:** Penggabungan DOM dan CSSOM. Node dengan `display: none` diabaikan sepenuhnya dari Render Tree (berbeda dengan `visibility: hidden` yang tetap masuk ke Render Tree).
4. **Layout (Reflow):** Browser menghitung geometri absolut: koordinat posisi $(X, Y)$ dan ukuran geometris (panjang $\times$ lebar) setiap node di viewport.
5. **Paint (Rasterization):** Pengisian pixel warna, text rendering, borders, background, dan drop-shadow ke dalam layer-layer gambar bitmap.
6. **Composite:** Penggabungan layer-layer independen ke layar monitor oleh GPU (Graphics Processing Unit).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Mekanisme Perhitungan Box Model

#### Standard Box Model (`box-sizing: content-box`)
Secara default, penetapan properti `width` dan `height` hanya berlaku pada Content Area.
$$\text{Total Width} = \text{width} + \text{padding-left} + \text{padding-right} + \text{border-left} + \text{border-right} + \text{margin-left} + \text{margin-right}$$

#### Alternative Box Model (`box-sizing: border-box`)
Penetapan properti `width` dan `height` mencakup Content, Padding, dan Border.
$$\text{Total Width} = \text{width} (\text{sudah mencakup content, padding, dan border}) + \text{margin-left} + \text{margin-right}$$
$$\text{Content Width} = \text{width} - (\text{padding-left} + \text{padding-right}) - (\text{border-left} + \text{border-right})$$

#### Margin Collapsing Rules
Margin vertikal (top dan bottom) antara dua block-level element yang bersebelahan dapat bergabung (*collapse*) menjadi satu margin tunggal. Nilai akhir margin yang digunakan adalah nilai terbesar dari kedua margin tersebut:
$$\text{Collapsed Margin} = \max(\text{Margin}_{\text{bottom elemen 1}}, \text{Margin}_{\text{top elemen 2}})$$
*Jika terdapat margin bernilai negatif:*
$$\text{Collapsed Margin} = \max(\text{Margin Positif}) - |\min(\text{Margin Negatif})|$$
*Margin collapsing TIDAK terjadi pada:* elemen dengan `display: flex`, `display: grid`, elemen berposisi absolut, atau elemen ber-float.

---

### Algoritma Resolusi Specificity

Ketika dua selector membidik elemen yang sama dan mengubah properti identik, browser mengevaluasi bobot matriks dari kiri ke kanan:

```text
Bandingkan Matriks A (a1, b1, c1, d1) vs Matriks B (a2, b2, c2, d2):
1. Jika a1 > a2, Selector A menang. Jika a2 > a1, Selector B menang. Jika a1 == a2:
2. Jika b1 > b2, Selector A menang. Jika b2 > b1, Selector B menang. Jika b1 == b2:
3. Jika c1 > c2, Selector A menang. Jika c2 > c1, Selector B menang. Jika c1 == c2:
4. Jika d1 > d2, Selector A menang. Jika d2 > d1, Selector B menang. Jika d1 == d2:
5. TIE-BREAKER: Selector yang dideklarasikan TERAKHIR dalam source code menang.
```

---

### Pipeline Eksekusi Peramban (Layout vs. Paint vs. Composite)

Tiga jenis modifikasi CSS memicu alur eksekusi internal yang berbeda:

1. **Reflow/Layout Path (Paling Berat):**
   * *Properti:* `width`, `height`, `margin`, `padding`, `display`, `border-width`, `font-size`, `top`, `left`.
   * *Alur:* `CSS Modification` $\to$ `Layout (Reflow)` $\to$ `Paint` $\to$ `Composite`.
   * *Dampak:* Memaksa browser menghitung ulang geometri elemen target beserta seluruh relasi tetangga/induknya.
2. **Repaint Path (Sedang):**
   * *Properti:* `color`, `background-color`, `box-shadow`, `border-style`, `outline`.
   * *Alur:* `CSS Modification` $\to$ `Paint` $\to$ `Composite` (Melewati fase Layout).
   * *Dampak:* Geometri tidak berubah, namun pixel pada layar harus diarsir ulang.
3. **Composite-Only Path (Paling Ringan / Performa 60-120 FPS):**
   * *Properti:* `transform`, `opacity`, `filter` (dengan batasan).
   * *Alur:* `CSS Modification` $\to$ `Composite` (Melewati Layout dan Paint).
   * *Dampak:* Layer langsung diproses oleh GPU tanpa membebani Main Thread CPU.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Anatomi Box Model: Content-Box vs. Border-Box

```text
STANDARD BOX MODEL (box-sizing: content-box)
width: 300px; padding: 20px; border: 10px; margin: 15px;

┌─────────────────────────────────────────────────────────────┐  ▲
│ MARGIN BOX (Lebar Akhir Visual: 390px)                      │  │
│  ┌───────────────────────────────────────────────────────┐  │  │
│  │ BORDER BOX (Lebar Elemen yang Tergambar: 360px)       │  │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │  │
│  │  │ PADDING BOX (Lebar Terdorong: 340px)            │  │  │  │
│  │  │  ┌───────────────────────────────────────────┐  │  │  │  │ 390px
│  │  │  │ CONTENT AREA                              │  │  │  │  │
│  │  │  │ 300px x 100px                             │  │  │  │  │
│  │  │  └───────────────────────────────────────────┘  │  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │  │
│  └───────────────────────────────────────────────────────┘  │  │
└─────────────────────────────────────────────────────────────┘  ▼
◄─────────────────────────── 390px ───────────────────────────►

ALTERNATIVE BOX MODEL (box-sizing: border-box)
width: 300px; padding: 20px; border: 10px; margin: 15px;

┌─────────────────────────────────────────────────────────────┐  ▲
│ MARGIN BOX (Lebar Akhir Visual: 330px)                      │  │
│  ┌───────────────────────────────────────────────────────┐  │  │
│  │ BORDER BOX (Lebar Elemen yang Tergambar: 300px) FIX   │  │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │  │
│  │  │ PADDING BOX (280px)                             │  │  │  │
│  │  │  ┌───────────────────────────────────────────┐  │  │  │  │ 330px
│  │  │  │ CONTENT AREA                              │  │  │  │  │
│  │  │  │ 240px x 40px (Otomatis menyusut!)         │  │  │  │  │
│  │  │  └───────────────────────────────────────────┘  │  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │  │
│  └───────────────────────────────────────────────────────┘  │  │
└─────────────────────────────────────────────────────────────┘  ▼
◄─────────────────────────── 330px ───────────────────────────►
```

### 2. Browser Critical Rendering Path & Lifecycle

```text
HTML Request ──► [ Tokenizer ] ──► [ Parse HTML ] ──► [ DOM Tree ]
                                                             │
CSS Request  ──► [ Tokenizer ] ──► [ Parse CSS  ] ──► [ CSSOM Tree ]
                                                             │
                                                             ▼
                                                    [ RENDER TREE ]
                                              (Kombinasi DOM + CSSOM)
                                              (Excludes display:none)
                                                             │
                                                             ▼
                                                    [ LAYOUT / REFLOW ]
                                                Kalkulasi posisi (X, Y)
                                                dan ukuran dimensi (W, H)
                                                             │
                                                             ▼
                                                    [ PAINT / RASTER ]
                                                Konversi vektor visual
                                                ke matriks bitmap pixel
                                                             │
                                                             ▼
                                                    [ GPU COMPOSITING ]
                                                Penyatuan multi-layer
                                                ke frame monitor
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Contoh berikut menunjukkan bahaya bawaan `content-box` saat membuat sistem 2 kolom serta resolusi spesifisitas.

### Kasus 1: Layout Breakdown Akibat Box-Model
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <style>
    /* RESET GLOBAL DENGAN INHERITANCE */
    html {
      box-sizing: border-box;
    }
    *, *::before, *::after {
      box-sizing: inherit;
      margin: 0;
      padding: 0;
    }

    .container {
      width: 400px;
      border: 2px solid black;
    }

    /* Kasus Content-Box: Layout Rusak (Width 50% + 50% + Padding > 100%) */
    .broken-box {
      box-sizing: content-box;
      width: 50%;
      padding: 20px;
      float: left;
      background: #ffcccc;
    }

    /* Kasus Border-Box: Presisi Matematis (Tetap Pas 50% per kolom) */
    .correct-box {
      box-sizing: border-box;
      width: 50%;
      padding: 20px;
      float: left;
      background: #ccffcc;
    }
  </style>
</head>
<body>
  <div class="container">
    <!-- Ini akan wrap/patah ke bawah karena total width = 200px + 40px padding = 240px x 2 = 480px (> 400px) -->
    <div class="broken-box">Kolom 1</div>
    <div class="broken-box">Kolom 2</div>
    <div style="clear: both;"></div>
  </div>

  <div class="container" style="margin-top: 20px;">
    <!-- Ini tetap berdampingan: total width per elemen tepat 200px (Content = 160px + Padding = 40px) -->
    <div class="correct-box">Kolom 1</div>
    <div class="correct-box">Kolom 2</div>
    <div style="clear: both;"></div>
  </div>
</body>
</html>
```

### Kasus 2: Kalkulasi Skor Spesifisitas
```css
/* Selector A: (0, 0, 1, 1) -> Menang dari B */
nav.menu ul li a { color: blue; } 
/* Specificity: 0 Inline, 0 ID, 1 Class (.menu), 3 Elements (nav, ul, li, a = 4 tags) -> (0, 0, 1, 4) */

/* Selector B: (0, 1, 0, 1) -> Menang Mutlak dari A karena memiliki 1 ID */
#main-nav a { color: red; } 
/* Specificity: 0 Inline, 1 ID (#main-nav), 0 Class, 1 Element (a) -> (0, 1, 0, 1) */

/* Selector C: (0, 1, 1, 0) -> Menang dari B */
#main-nav .active { color: green; } 
/* Specificity: 0 Inline, 1 ID (#main-nav), 1 Class (.active), 0 Elements -> (0, 1, 1, 0) */
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kita akan membangun sistem komponen *Alert Notification Banner* produksi. Komponen ini dirancang dengan:
1. Skema penamaan BEM untuk mengontrol flat-specificity `(0, 0, 1, 0)`.
2. Box model konsisten berbasis CSS Variables.
3. Animasi sliding & fading yang dioptimasi hanya pada layer *Compositor* (`transform` dan `opacity`), tanpa memicu *Reflow* atau *Repaint*.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Production Alert Component</title>
  <style>
    /* ==========================================================================
       1. GLOBAL RESET & BASE SETTINGS
       ========================================================================== */
    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      padding: 2rem;
      background-color: #f8fafc;
      color: #0f172a;
    }

    /* ==========================================================================
       2. ALERT COMPONENT (BEM Architecture: Specificity Flat (0, 0, 1, 0))
       ========================================================================== */
    .alert {
      /* Dynamic Sizing Token */
      --alert-padding: 1rem 1.25rem;
      --alert-radius: 0.5rem;
      --alert-border-width: 1px;
      
      /* Dynamic Theme Token (Default Neutral) */
      --alert-bg: #ffffff;
      --alert-border-color: #e2e8f0;
      --alert-text-color: #334155;
      --alert-accent: #64748b;

      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
      width: 100%;
      max-width: 32rem;
      padding: var(--alert-padding);
      border-radius: var(--alert-radius);
      border: var(--alert-border-width) solid var(--alert-border-color);
      background-color: var(--alert-bg);
      color: var(--alert-text-color);
      
      /* Composite-only shadow via GPU translation layering */
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);

      /* GPU Animation Optimization */
      will-change: transform, opacity;
      transition: transform 300ms cubic-bezier(0.16, 1, 0.3, 1), 
                  opacity 300ms cubic-bezier(0.16, 1, 0.3, 1);
    }

    /* Modifier: Success State -> Specificity: (0, 0, 2, 0) or kept flat via single class */
    .alert--success {
      --alert-bg: #f0fdf4;
      --alert-border-color: #bbf7d0;
      --alert-text-color: #14532d;
      --alert-accent: #22c55e;
    }

    /* Modifier: Danger State */
    .alert--danger {
      --alert-bg: #fef2f2;
      --alert-border-color: #fecaca;
      --alert-text-color: #7f1d1d;
      --alert-accent: #ef4444;
    }

    /* Sub-elements (BEM Elements) */
    .alert__icon {
      flex-shrink: 0;
      width: 1.25rem;
      height: 1.25rem;
      margin-top: 0.125rem;
      fill: var(--alert-accent);
    }

    .alert__content {
      flex-grow: 1;
    }

    .alert__title {
      font-size: 0.875rem;
      font-weight: 600;
      margin-bottom: 0.25rem;
    }

    .alert__description {
      font-size: 0.8125rem;
      line-height: 1.4;
      color: currentColor;
      opacity: 0.9;
    }

    .alert__close-btn {
      flex-shrink: 0;
      background: transparent;
      border: none;
      cursor: pointer;
      color: inherit;
      opacity: 0.6;
      padding: 0.25rem;
      margin: -0.25rem -0.25rem 0 0;
      transition: opacity 150ms ease;
    }

    .alert__close-btn:hover {
      opacity: 1;
    }

    /* State: Triggering High-Performance Composite-Only Exit */
    .alert.is-hidden {
      opacity: 0;
      transform: translateY(-8px) scale(0.98);
      pointer-events: none;
    }
  </style>
</head>
<body>

  <!-- Success Notification Instance -->
  <div class="alert alert--success" id="auth-alert" role="alert">
    <svg class="alert__icon" viewBox="0 0 20 20">
      <path d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"/>
    </svg>
    <div class="alert__content">
      <h4 class="alert__title">Autentikasi Berhasil</h4>
      <p class="alert__description">Sesi kerja aman telah dibentuk. Token JWT aktif didelegasikan.</p>
    </div>
    <button class="alert__close-btn" aria-label="Tutup notifikasi" onclick="dismissAlert('auth-alert')">
      ✕
    </button>
  </div>

  <script>
    function dismissAlert(elementId) {
      const alertNode = document.getElementById(elementId);
      if (alertNode) {
        // Memicu Composite-only transitions tanpa Reflow layout sekitarnya
        alertNode.classList.add('is-hidden');
        
        // Membersihkan DOM setelah GPU Layer selesai beranimasi
        alertNode.addEventListener('transitionend', () => {
          alertNode.remove();
        }, { once: true });
      }
    }
  </script>
</body>
</html>
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi | Opsi A | Opsi B | Analisis Komparasi Arsitektural |
| :--- | :--- | :--- | :--- |
| **Model Geometri** | `box-sizing: content-box` (W3C Default) | `box-sizing: border-box` (Modern Standard) | `content-box` memerlukan kalkulasi manual pengurangan padding/border dari total width saat bekerja dengan persentase. `border-box` membuat penskalaan layout responsif intuitif dan deterministik. |
| **Spesifisitas** | Deep Selector Cascading (`#nav .list > li.active a`) | Flat BEM / Utility Architecture (`.c-nav__link--active`) | Deep Selector menciptakan keterikatan kuat (*high coupling*) dengan DOM tree HTML. Flat selector menjaga spesifisitas tetap di level seragam `(0, 0, 1, 0)`, mempermudah override komponen tanpa `!important`. |
| **Animasi Performa** | Geometri Animasi (`top`, `height`, `margin`) | Transform & Opacity Layering (`transform: translate()`, `scale()`) | Mengubah dimensi (`height`) memicu **Reflow global** (seluruh layout di bawahnya dihitung ulang). Menggunakan `transform` mendelegasikan tugas ke GPU; elemen bergeser di layer independen tanpa menyentuh DOM layout tree. |
| **Manajemen Margin** | Spasi vertikal margin pada setiap komponen | Single-Direction Margin / Container Spacing (Flex/Grid Gap) | Margin collapsing sering menimbulkan "phantom spacing" jika ada nested element. Mengandalkan `gap` pada Flexbox/Grid sepenuhnya mengeliminasi margin collapsing dan menjaga isolasi modular komponen. |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Border-Box Inherited Reset Secara Global:**
   ```css
   html {
     box-sizing: border-box;
   }
   *, *::before, *::after {
     box-sizing: inherit;
   }
   ```
   *Mengapa:* Memastikan integrasi pihak ketiga (misalnya library widget pihak ketiga yang mengasumsikan `content-box`) tetap dapat meng-override box-sizing pada kontainer lokal mereka dengan mudah.

2. **Kendalikan Spesifisitas Menggunakan Metodologi BEM atau CSS Modules:**
   Hindari menarget ID (`#id`) untuk styling. Pertahankan spesifisitas kelas pada tingkat tunggal `(0, 0, 1, 0)`:
   * **Buruk:** `#header .nav-item.active a` $\to$ `(0, 1, 2, 1)`
   * **Baik:** `.nav__link--active` $\to$ `(0, 0, 1, 0)`

3. **Gunakan `:where()` untuk Mengatur Style Default Tanpa Menambah Spesifisitas:**
   Pseudo-class `:where()` secara spesifik memiliki bobot `(0, 0, 0, 0)`.
   ```css
   /* Spesifisitas nol: mudah ditimpa oleh developer consumer tanpa konflik */
   :where(.card) {
     padding: 1.5rem;
     border-radius: 8px;
   }
   ```

4. **Animasi Hanya Properti Ramah GPU (Composite Properties):**
   Gunakan pasangan properti berikut untuk animasi:
   * Posisi: Gunakan `transform: translate(x, y)` sebagai pengganti `top`, `bottom`, `left`, `right`.
   * Skala/Ukuran: Gunakan `transform: scale()` sebagai pengganti `width` dan `height`.
   * Visibilitas: Gunakan `opacity` sebagai pengganti `visibility` atau `display`.

5. **Waspadai Margin Collapsing Melalui Formasi BFC (Block Formatting Context):**
   Cegah margin anak bocor keluar dari kontainer induk dengan membuat BFC, misalnya menggunakan `display: flow-root` pada kontainer induk.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. The `!important` Spiral of Death
* **Kode Keliru:**
  ```css
  .nav-item { color: red !important; }
  /* Beberapa sprint kemudian untuk menimpa... */
  #header .nav-item { color: blue !important; }
  ```
* **Koreksi Arsitektural:** Identifikasi selector yang memicu konflik menggunakan browser inspector dan sederhanakan spesifisitas parent daripada membubuhkan `!important`.
  ```css
  .nav__item { color: red; }
  .nav__item--active { color: blue; }
  ```

### 2. Layout Thrashing via Inappropriate Transition Properties
* **Kode Keliru (Memicu Reflow 60 FPS):**
  ```css
  .dropdown-menu {
    height: 0;
    transition: height 0.3s ease; /* MEMICU REFLOW BERKELANJUTAN */
    overflow: hidden;
  }
  .dropdown-menu.is-open {
    height: 300px;
  }
  ```
* **Koreksi Performa (Composite Transition):**
  ```css
  .dropdown-menu {
    transform: scaleY(0);
    transform-origin: top;
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    will-change: transform;
  }
  .dropdown-menu.is-open {
    transform: scaleY(1);
  }
  ```

### 3. Margin Collapsing Mengacaukan Jarak Parent-Child
* **Skenario Masalah:** Anda memberikan `margin-top: 20px` pada elemen `<p>` pertama di dalam `<div>`, namun alih-alih bergeser ke bawah di dalam `<div>`, `margin-top` tersebut justru menembus keluar dan menggeser seluruh `<div>` induk dari batas atas layar.
* **Solusi Teknis:** Tambahkan `display: flow-root` pada elemen induk untuk membentuk BFC baru:
  ```css
  .parent-container {
    display: flow-root; /* Mengisolasi margin collapsing internal */
    background: #e2e8f0;
  }
  .parent-container > p {
    margin-top: 20px; /* Sekarang terisolasi rapi di dalam container */
  }
  ```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1 (Beginner): Menghitung Specificity Matrix
Tentukan selector pemenang untuk styling warna teks tombol `<button id="submit-btn" class="btn btn-primary" type="submit">Kirim</button>` dari deklarasi berikut:

1. `button[type="submit"]`
2. `.btn.btn-primary`
3. `#submit-btn`
4. `button.btn`

#### Solusi Langkah demi Langkah:
1. Hitung Matriks `(Inline, ID, Class/Attr/Pseudo-class, Element)`:
   * Deklarasi 1: `button[type="submit"]` $\to$ 0 ID, 1 Attribute, 1 Element $\to$ **(0, 0, 1, 1)**
   * Deklarasi 2: `.btn.btn-primary` $\to$ 0 ID, 2 Classes, 0 Element $\to$ **(0, 0, 2, 0)**
   * Deklarasi 3: `#submit-btn` $\to$ 1 ID, 0 Class, 0 Element $\to$ **(0, 1, 0, 0)**
   * Deklarasi 4: `button.btn` $\to$ 0 ID, 1 Class, 1 Element $\to$ **(0, 0, 1, 1)**
2. Evaluasi: Bandingkan kolom ID. Deklarasi 3 memiliki `1` pada kolom ID, sedangkan deklarasi lain `0`.
3. **Pemenang:** Deklarasi 3 (`#submit-btn`).

---

### Latihan 2 (Intermediate): Kalkulator Matematika Box Model
Sebuah kontainer memiliki lebar absolut `500px`. Di dalamnya terdapat elemen kotak dengan definisi:
```css
.card {
  box-sizing: content-box;
  width: 100%;
  padding: 16px;
  border: 4px solid #000;
  margin: 12px;
}
```
* **Pertanyaan A:** Berapakah total lebar fisik (*horizontal footprint*) yang dihabiskan oleh `.card` di layout layar?
* **Pertanyaan B:** Mengapa konfigurasi ini menyebabkan horizontal horizontal overflow?
* **Pertanyaan C:** Tuliskan deklarasi perbaikan agar `.card` muat pas $100\%$ di dalam batas kontainer tanpa meluap keluar.

#### Solusi:
* **Solusi A:**
  $$\text{Content Width} = 100\% \times 500\text{px} = 500\text{px}$$
  $$\text{Horizontal Footprint} = 500 + \text{Padding}(16 \times 2) + \text{Border}(4 \times 2) + \text{Margin}(12 \times 2)$$
  $$\text{Horizontal Footprint} = 500 + 32 + 8 + 24 = \mathbf{564\text{px}}$$
* **Solusi B:** Karena `box-sizing: content-box` menambahkan padding dan border di luar `width: 500px`, total lebar elemen tergambar mencapai $540\text{px}$, meluap $40\text{px}$ melebihi kontainer induk.
* **Solusi C:**
  ```css
  .card {
    box-sizing: border-box; /* Memaksa padding dan border masuk ke dalam kalkulasi 100% */
    width: 100%;
    padding: 16px;
    border: 4px solid #000;
    margin: 0; /* Hapus atau kelola margin agar tidak meluap */
  }
  ```

---

### Latihan 3 (Advanced): Profile & Fix Layout Thrashing Animation
Diberikan animasi drawer menu yang lambat dan patah-patah berikut:

```css
/* KODE AWAL YANG BERMASALAH */
.sidebar {
  position: fixed;
  top: 0;
  left: -300px;
  width: 300px;
  height: 100vh;
  transition: left 0.4s ease-out; /* Memicu Reflow setiap frame! */
}
.sidebar.active {
  left: 0;
}
```

* **Instruksi:** Refactor kode di atas agar bekerja murni pada tahap *Compositing*, stabil pada 60/120 FPS, dan terisolasi pada layer GPU independen.

#### Solusi Refactoring:
```css
/* KODE SETELAH OPTIMASI (COMPOSITE-ONLY) */
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  width: 300px;
  height: 100vh;
  /* Gunakan hardware-accelerated transform 3D/2D */
  transform: translateX(-100%);
  /* Transisikan properti transform, bukan left/geometri */
  transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  /* Berikan instruksi layer komposit awal kepada browser engine */
  will-change: transform;
}

.sidebar.active {
  transform: translateX(0);
}
```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa yang terjadi pada Content Area sebuah elemen dengan deklarasi `width: 200px; padding: 20px; border: 5px solid red; box-sizing: border-box;`?**
   * A. Content area tetap berukuran lebar 200px.
   * B. Content area mengecil secara otomatis menjadi lebar 150px.
   * C. Content area membesar menjadi 250px.
   * D. Peramban menghasilkan error sintaks CSS.
   * *Jawaban:* **B**. Pada `border-box`, Content Area dihitung dari: $\text{Width}(200) - \text{Padding}(40) - \text{Border}(10) = 150\text{px}$.

2. **Dua elemen blok yang bertetangga vertikal memiliki `margin-bottom: 30px` dan `margin-top: 20px`. Berapakah jarak aktual antar kedua elemen tersebut di layar?**
   * A. 50px
   * B. 10px
   * C. 30px
   * D. 600px
   * *Jawaban:* **C**. Terjadi *Margin Collapsing*. Aturan normal margin collapsing vertikal mengambil nilai terbesar antara kedua margin yang bersebelahan: $\max(30, 20) = 30\text{px}$.

3. **Selector manakah yang memiliki bobot spesifisitas tertinggi?**
   * A. `div#app .list-item.active`
   * B. `body div#app ul.list li a:hover`
   * C. `header .nav .item[data-state="open"]`
   * D. `html body #main-wrapper`
   * *Jawaban:* **A**. 
     * A = 1 ID, 2 Classes, 1 Tag $\to$ `(0, 1, 2, 1)`
     * B = 1 ID, 2 Classes/Pseudo, 4 Tags $\to$ `(0, 1, 2, 4)` -> *Koreksi:* Hitung ulang:
       * Matriks A: `#app` (1 ID), `.list-item`, `.active` (2 Classes), `div` (1 Element) $\to$ `(0, 1, 2, 1)`.
       * Matriks B: `#app` (1 ID), `.list` (1 Class), `:hover` (1 Pseudo-class), `body`, `div`, `ul`, `li`, `a` (5 Elements) $\to$ `(0, 1, 2, 5)`.
       * **Evaluasi Ulang:** Kolom ID (1 vs 1), Kolom Class (2 vs 2), Kolom Element (1 vs 5). Maka **B** lebih tinggi daripada A pada kolom elemen!
       * *Jawaban yang benar:* **B** dengan skor `(0, 1, 2, 5)`.

4. **Tahap peramban mana yang dilewati saat sebuah elemen hanya mengubah properti `transform: scale(1.1)`?**
   * A. Composite dan Paint
   * B. Layout dan Paint
   * C. Layout dan Composite
   * D. Tidak ada yang dilewati
   * *Jawaban:* **B**. Transform dieksekusi langsung pada layer compositor GPU, melewati tahap Layout (Reflow) dan Paint (Rasterization).

5. **Berapa nilai spesifisitas yang ditambahkan oleh selector `:where(.header, .nav)`?**
   * A. `(0, 0, 1, 0)`
   * B. `(0, 0, 2, 0)`
   * C. `(0, 0, 0, 0)`
   * D. `(0, 1, 0, 0)`
   * *Jawaban:* **C**. Karakteristik spesifik dari pseudo-class `:where()` sesuai spesifikasi W3C adalah selalu bernilai spesifisitas nol mutlak `(0, 0, 0, 0)`.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **W3C CSS Box Model Module Level 4:**
  [https://www.w3.org/TR/css-box-4/](https://www.w3.org/TR/css-box-4/)
* **W3C CSS Cascading and Inheritance Level 5 (Specificity Specification):**
  [https://www.w3.org/TR/css-cascade-5/](https://www.w3.org/TR/css-cascade-5/)
* **MDN Web Docs — Introduction to the CSS box model:**
  [https://developer.mozilla.org/en-US/docs/Learn/CSS/Building_blocks/The_box_model](https://developer.mozilla.org/en-US/docs/Learn/CSS/Building_blocks/The_box_model)
* **Google Chrome Developers — Rendering Performance & Lifecycle:**
  [https://developer.chrome.com/docs/performance/rendering/](https://developer.chrome.com/docs/performance/rendering/)
* **CSS Triggers (Tabel Pemicu Reflow/Paint Tiap Properti Mesin Browser):**
  [https://csstriggers.com/](https://csstriggers.com/)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* **Box Model:** Seluruh elemen visual terdiri dari Content, Padding, Border, dan Margin. Aturan `box-sizing: border-box` wajib diimplementasikan sejak awal proyek untuk memastikan konsistensi kalkulasi matematis width/height pada layout responsif.
* **Margin Collapsing:** Penggabungan margin vertikal block-level yang berdampingan secara otomatis mengambil nilai margin terbesar. Ini dapat diisolasi menggunakan Block Formatting Context (`display: flow-root`).
* **Specificity Tuple `(a, b, c, d)`:** Inline styles mengalahkan ID; ID mengalahkan Class/Attribute/Pseudo-class; Class mengalahkan Elements. Hindari perang `!important` dengan mengadopsi struktur selektor yang datar (*flat specificity*) seperti metodologi BEM.
* **Critical Rendering Path (CRP):** Mengetahui jalur *DOM/CSSOM $\to$ Render Tree $\to$ Layout $\to$ Paint $\to$ Composite* memungkinkan developer membangun interaksi visual yang bebas *jank* (stutter) dengan menganimasikan properti GPU-friendly (`transform`, `opacity`) daripada memicu siklus berat *Layout/Reflow*.

---

## SEKSI 17 — GLOSARIUM

* **BFC (Block Formatting Context):** Wilayah rendering visual independen di mana kalkulasi penataan elemen block berada terisolasi dari lingkungan eksternal dokumen.
* **Composite:** Tahap rendering di mana peramban menggabungkan layer-layer terpisah menjadi satu tampilan utuh pada layar monitor menggunakan GPU.
* **Layout Thrashing:** Kondisi penurunan performa drastis ketika skrip JavaScript secara berulang membaca dan menulis properti geometris CSS, memaksa browser melakukan *reflow* beruntun dalam satu siklus frame animasi.
* **Margin Collapsing:** Perilaku CSS di mana margin atas dan bawah dari dua elemen disatukan menjadi margin tunggal dengan besaran nilai terbesar di antara keduanya.
* **Rasterization (Paint):** Proses mengubah data bentuk geometris dan informasi warna hasil Render Tree menjadi titik-titik pixel individual pada layar.
* **Reflow (Layout):** Proses kalkulasi browser untuk menentukan posisi fisik dan ukuran dari semua objek yang berada di dalam Render Tree.
* **Specificity:** Algoritma pembobotan numerik yang diterapkan oleh browser pada selector CSS untuk menentukan deklarasi aturan yang menang saat terjadi benturan styling.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Titik Miskonsepsi Siswa:**
  * Siswa sering mengira bahwa `padding` berada di luar `border`. Tekankan dengan analogi lukisan: Content adalah lukisan, Padding adalah passe-partout (ruang kosong pelindung di dalam bingkai), Border adalah bingkai kayu, dan Margin adalah jarak antar bingkai di dinding galeri.
  * Siswa sering mengira nilai spesifisitas adalah sistem desimal murni (misal: 10 tag selector akan mengalahkan 1 class). **Ini salah.** Skor spesifisitas tidak berpindah basis radix secara desimal; satu class `(0, 0, 1, 0)` tidak akan pernah bisa dikalahkan oleh 100 elemen selector berantai `(0, 0, 0, 100)`.
* **Demonstrasi Live Coding:**
  * Buka Chrome DevTools $\to$ panel **Performance**. Rekam interaksi saat menganimasikan elemen menggunakan `left` vs. `transform: translateX()`. Tunjukkan kepada kelas perbedaan dramatis pada grafik *Layout* (berwarna ungu) dan *Paint* (berwarna hijau).

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.1.0 (2025-02-15):**
  * Penambahan penjelasan pseudo-class spesifisitas modern: `:where()`, `:is()`, dan `:not()`.
  * Pembaruan visual diagram ASCII Box Model & Lifecycle Rendering Engine.
* **Versi 1.0.0 (2024-08-10):**
  * Rilis modul inisial: Standar Box Model, Resolusi Matriks Spesifisitas, dan Fondasi Pipeline CRP.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `01-Core-Foundations / Bab 02 Module 02 — Semantic HTML & Accessible Document Tree`
* **Modul Saat Ini:** `01-Core-Foundations / Bab 03 Module 01 — Fondasi CSS3: Box Model, Specificity & Rendering Pipeline`
* **Modul Berikutnya:** `01-Core-Foundations / Bab 03 Module 02 — Layout Modern: Flexbox Deep-Dive & Alignment Mechanics`