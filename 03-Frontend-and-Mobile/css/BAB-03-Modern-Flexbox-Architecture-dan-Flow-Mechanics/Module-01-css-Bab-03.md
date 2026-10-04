# Modern Flexbox Architecture & Flow Mechanics

---

## SEKSI 01 — IDENTITAS MODUL

* **Track:** 03-Frontend-and-Mobile
* **Kategori:** CSS (Cascading Style Sheets)
* **Bab:** 03 — Layout Systems & Flow Control
* **Modul:** 01 — Modern Flexbox Architecture & Flow Mechanics
* **Prasyarat:** HTML5 Semantic Elements, CSS Box Model, CSS Stacking Contexts, BFC (Block Formatting Context)
* **Target Audience:** Frontend Engineers, UI/UX Technologists, Design Systems Engineers

---

## SEKSI 02 — LEARNING OBJECTIVES

1. Menguasai kalkulasi matematis di balik algoritma resolusi ruang Flexbox: *Hypothetical Size*, *Flex Basis Distribution*, *Flex Grow Scaling Ratio*, dan *Flex Shrink Factor Formulation*.
2. Membedakan secara presisi siklus hidup rendering layout engine browser saat memproses *Flex Formatting Context* (FFC) dibandingkan dengan *Block Formatting Context* (BFC).
3. Mengeliminasi bug degradasi visual klasik pada Flexbox modern, termasuk *Min-Content Overflow*, keruntuhan kontainer fleksibel (*Collapsing Sibling*), dan anomali margin *auto*.
4. Merancang arsitektur komponen UI enterprise berbasis Flexbox yang tangguh, modular, adaptif terhadap ambiguitas konten dinamis, serta memenuhi standar aksesibilitas WCAG 2.1 AA.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Flexbox bukan sekadar sintaks untuk menyejajarkan elemen secara horizontal atau vertikal; Flexbox adalah **algoritma distribusi ruang satu dimensi berbasis resolusi rasio vektor**.

```
    [Tradisional: BFC]               [Modern: Flexbox FFC]
  +--------------------+        +-----------------------------+
  | Layout Berbasis    |        | Layout Berbasis Distribusi  |
  | Dimensi Kaku       |   vs   | Ruang Berbobot (Weighted    |
  | (Width / Height)   |        | Space Distribution)         |
  +--------------------+        +-----------------------------+
```

* **Mental Model Tradisional (BFC):** Anda mendikte ukuran eksplisit suatu elemen (`width: 30%`), kemudian browser menempatkannya ke dalam flow. Jika konten melebihi batas, terjadi *overflow* struktural.
* **Mental Model Flexbox (FFC):** Kontainer induk memiliki *Available Free Space* (ruang kosong positif) atau *Negative Free Space* (ruang defisit). Elemen anak (*flex items*) bertindak sebagai partikel elastis yang mengajukan ukuran ideal (`flex-basis`), lalu melakukan negosiasi kolektif untuk menyerap ruang kosong (`flex-grow`) atau mengorbankan sebagian ukuran dirinya (`flex-shrink`) berdasarkan rasio bobot masing-masing.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah representasi visual diagram alur mekanika sumbu Flexbox (*Main Axis* vs *Cross Axis*) dan siklus kalkulasi layout engine (Blink/Gecko):

```
+=============================================================================+
| FLEX CONTAINER                                                              |
|                                                                             |
|                           [ MAIN AXIS VECTOR ] --->                         |
|  main-start                                                      main-end   |
|  +--------+=====================================================+--------+  |
|  |        |                                                     |        |  |
|  |        |  [ITEM 1]              [ITEM 2]          [ITEM 3]   |        |  |
|c |        |  +--------------+      +----------+      +-------+  |        |c |
|r |        |  | flex-basis   |      |          |      |       |  |        |r |
|o |        |  | flex-grow    |      |          |      |       |  |        |o |
|s |        |  | flex-shrink  |      |          |      |       |  |        |s |
|s |        |  +--------------+      +----------+      +-------+  |        |s |
|- |        |                                                     |        |- |
|s |        |<-------------------- Free Space ------------------->|        |e |
|t |        |                                                     |        |n |
|a |        |                                                     |        |d |
|r |        +=====================================================+        |  |
|t |                        CROSS AXIS VECTOR                             |  |
|  |                                |                                     |  |
|  |                                v                                     |  |
|  +----------------------------------------------------------------------+  |
+=============================================================================+

ALUR RESOLUSI ALGORITMA FLEKSIBEL (BROWSER ENGINE):

  [ 1. Inisialisasi ]
         │
         ▼
  [ 2. Tentukan Available Space = Container Size - Padding - Border ]
         │
         ▼
  [ 3. Tentukan Base Outer Size tiap item via `flex-basis` ]
         │
         ▼
  [ 4. Hitung Sum of Flex Base Sizes ]
         │
         ├─────────────────────────────────────────┐
         ▼                                         ▼
   [ Total Base < Available ]                [ Total Base > Available ]
         │ (Terdapat Positif Free Space)           │ (Terdapat Negatif Free Space)
         ▼                                         ▼
   Distribusikan sisa ruang                 Kurangi ukuran via:
   berdasarkan Rasio `flex-grow`            Rasio (`flex-shrink` * `flex-basis`)
         │                                         │
         └────────────────────┬────────────────────┘
                              ▼
        [ 5. Evaluasi Properti Batas: `min-width` / `max-width` ]
                              │
                              ▼
        [ 6. Alignment & Positioning: `justify-content`, `align-items` ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi Properti Flex Container

* **`display: flex | inline-flex`**: Membangkitkan Flex Formatting Context (FFC). Mengubah seluruh *direct children* menjadi *flex items*, menonaktifkan perilaku blok normal seperti *margin collapsing*, `float`, `clear`, dan `vertical-align`.
* **`flex-direction`**: Mengikat sumbu koordinat. Nilai `row` / `row-reverse` memetakan Main Axis ke sumbu inline (horizontal secara default); `column` / `column-reverse` memetakan Main Axis ke sumbu block (vertikal).
* **`flex-wrap`**: Mengontrol pembentukan *flex lines* baru saat total ukuran dasar item melampaui dimensi kontainer.
* **`justify-content`**: Mengatur distribusi sisa ruang kosong di sepanjang Main Axis.
* **`align-items`**: Mengatur penyejajaran default semua item di sepanjang Cross Axis dalam garisnya (*flex line*).
* **`align-content`**: Mengatur distribusi ruang kosong antargaris (*multi-line flex container*) di sepanjang Cross Axis.

### 2. Anatomi Properti Flex Items

* **`flex-basis`**: Menetapkan ukuran awal hipotetis (*hypothetical size*) komponen sebelum penyerapan atau pemotongan ruang dilakukan. Mengesampingkan `width`/`height` jika keduanya dideklarasikan bersamaan.
* **`flex-grow`**: Faktor pembobotan penyerapan *positive free space*.
* **`flex-shrink`**: Faktor pembobotan pemotongan dimensi saat terjadi defisit ruang (*negative free space*).
* **`align-self`**: Mengesampingkan aturan `align-items` dari kontainer untuk item individual.
* **`order`**: Nilai integer untuk mengubah urutan visual rendering tanpa memodifikasi Document Object Model (DOM).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Matematis Algoritma Resolusi Flexbox

#### A. Penyerapan Ruang Positif (Positive Free Space Distribution)

Ketika total *flex-basis* dari semua item lebih kecil daripada ukuran Main Axis kontainer, tercipta *Positive Free Space* ($S_{pos}$).

$$S_{pos} = W_{container} - \sum (W_{basis\_i})$$

Jika terdapat sisa ruang ($S_{pos} > 0$), browser menghitung pertambahan lebar ($\Delta W_i$) untuk setiap item $i$ menggunakan formula:

$$\Delta W_i = S_{pos} \times \left( \frac{\text{flex-grow}_i}{\sum \text{flex-grow}} \right)$$

Ukuran akhir item $i$:

$$W_{final\_i} = W_{basis\_i} + \Delta W_i$$

#### B. Pemotongan Ruang Negatif (Negative Free Space Shrinkage)

Ketika total *flex-basis* melampaui ukuran Main Axis kontainer, terjadi *Negative Free Space* ($S_{neg}$). Berbeda dengan `flex-grow`, pemotongan ruang tidak semata-mata membagi rasio `flex-shrink`, melainkan **diberi bobot terhadap ukuran awal (`flex-basis`) elemen tersebut**. Hal ini mencegah item kecil menyusut hingga menjadi nol sebelum item besar terpotong seimbang.

Langkah 1: Menghitung *Scaled Shrink Factor* total ($SSF_{total}$):

$$SSF_{total} = \sum (\text{flex-basis}_i \times \text{flex-shrink}_i)$$

Langkah 2: Menghitung rasio pengurangan untuk item individual:

$$R_i = \frac{\text{flex-basis}_i \times \text{flex-shrink}_i}{SSF_{total}}$$

Langkah 3: Menghitung pengurangan aktual dan dimensi akhir:

$$\Delta W_i = |S_{neg}| \times R_i$$

$$W_{final\_i} = W_{basis\_i} - \Delta W_i$$

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental distribusi ruang non-proporsional dengan demonstrasi kalkulasi presisi:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Flexbox Mechanics Testbed</title>
  <style>
    :root {
      --bg-container: #0f172a;
      --color-item-1: #38bdf8;
      --color-item-2: #818cf8;
      --color-item-3: #c084fc;
      --text-color: #ffffff;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background-color: #020617;
      color: var(--text-color);
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      padding: 2rem;
    }

    /* Container: Lebar pasti 800px */
    .flex-container {
      display: flex;
      flex-direction: row;
      width: 800px;
      padding: 16px;
      background-color: var(--bg-container);
      border: 2px solid #334155;
      border-radius: 8px;
      gap: 16px; /* 2 gap * 16px = 32px terpakai */
    }

    .flex-item {
      padding: 16px;
      border-radius: 4px;
      font-weight: 600;
      text-align: center;
      min-width: 0; /* Menolak implisit auto min-width */
    }

    /* Item 1: Basis 200px, grow 1 */
    .item-alpha {
      background-color: var(--color-item-1);
      color: #0f172a;
      flex-grow: 1;
      flex-shrink: 1;
      flex-basis: 200px;
    }

    /* Item 2: Basis 150px, grow 2 */
    .item-beta {
      background-color: var(--color-item-2);
      color: #0f172a;
      flex-grow: 2;
      flex-shrink: 1;
      flex-basis: 150px;
    }

    /* Item 3: Basis 100px, grow 0 (kaku) */
    .item-gamma {
      background-color: var(--color-item-3);
      color: #0f172a;
      flex-grow: 0;
      flex-shrink: 0;
      flex-basis: 100px;
    }
  </style>
</head>
<body>
  <div class="flex-container">
    <div class="flex-item item-alpha">Item Alpha</div>
    <div class="flex-item item-beta">Item Beta</div>
    <div class="flex-item item-gamma">Item Gamma</div>
  </div>
</body>
</html>
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 38–46 (`.flex-container`)**:
  * `display: flex`: Membuka konteks formatting baru (FFC).
  * `width: 800px`: Menetapkan Main Axis space. Tersedia $800\text{px} - (16\text{px} \times 2 \text{ padding}) = 768\text{px}$.
  * `gap: 16px`: Terdapat 3 item, menghasilkan 2 sela sebesar $32\text{px}$. Total ruang efektif untuk item adalah $768\text{px} - 32\text{px} = 736\text{px}$.
* **Baris 47–53 (`.flex-item`)**:
  * `min-width: 0`: Mengatasi aturan CSS Flexbox level 1 default di mana flex item memiliki `min-width: auto`. Hal ini krusial agar item tidak mengalami overflow tak terkendali saat direduksi.
* **Baris 55–61 (`.item-alpha`)**:
  * `flex-basis: 200px`, `flex-grow: 1`.
* **Baris 63–69 (`.item-beta`)**:
  * `flex-basis: 150px`, `flex-grow: 2`.
* **Baris 71–77 (`.item-gamma`)**:
  * `flex-basis: 100px`, `flex-grow: 0`, `flex-shrink: 0`. Ukuran bersifat absolut stabil di 100px.

### Perhitungan Matematis Lapangan
1. **Total Basis Item**: $200\text{px} + 150\text{px} + 100\text{px} = 450\text{px}$.
2. **Positive Free Space ($S_{pos}$)**: $736\text{px} - 450\text{px} = 286\text{px}$.
3. **Total Grow Factor**: $1 (\text{Alpha}) + 2 (\text{Beta}) + 0 (\text{Gamma}) = 3$.
4. **Alokasi Delta Alpha**: $286\text{px} \times (1 / 3) = 95.33\text{px}$.
   * Lebar Final Alpha: $200\text{px} + 95.33\text{px} = \mathbf{295.33\text{px}}$.
5. **Alokasi Delta Beta**: $286\text{px} \times (2 / 3) = 190.67\text{px}$.
   * Lebar Final Beta: $150\text{px} + 190.67\text{px} = \mathbf{340.67\text{px}}$.
6. **Alokasi Delta Gamma**: $0\text{px}$.
   * Lebar Final Gamma: $\mathbf{100.00\text{px}}$.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Enterprise Production Scenario)

### Konteks Bisnis & Masalah
Sebuah platform analitik finansial enterprise (*FinTech Platform*) mengalami insiden kegagalan rendering UI pada komponen papan navigasi data (*Data Toolbar*). 

**Gejala:**
1. Ketika string nama workspace atau metrik sangat panjang, toolbar mengalami *blowout*, memunculkan horizontal scrollbar browser yang merusak viewport responsif.
2. Tombol aksi penting (*Export CSV*, *Filter Trigger*) terdorong keluar dari layar.
3. Struktur komponen sebelumnya menggunakan persentase statis dan deklarasi `float`/`display: inline-block` warisan yang rapuh.

**Kebutuhan:**
Membangun toolbar modular berbasis Flexbox yang adaptif. Toolbar harus memiliki:
* Area *Workspace Title* yang mengecil secara elegan (*truncation* via ellipsis) jika ruang sempit.
* Area *Global Search* yang bersifat elastis dengan batas pertumbuhan minimum dan maksimum.
* Area *Action Cluster* yang memiliki ukuran solid (*rigid dimension*) dan tidak boleh terpotong dalam kondisi ruang apa pun.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Analytics Toolbar</title>
  <style>
    :root {
      --ui-bg: #090d16;
      --ui-surface: #131b2e;
      --ui-border: #1e293b;
      --ui-text-main: #f8fafc;
      --ui-text-muted: #94a3b8;
      --ui-accent: #2563eb;
      --ui-accent-hover: #1d4ed8;
      --font-stack: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: var(--font-stack);
      background-color: var(--ui-bg);
      color: var(--ui-text-main);
      padding: 2rem;
    }

    /* Enterprise Toolbar Container */
    .c-toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1.5rem;
      background-color: var(--ui-surface);
      border: 1px solid var(--ui-border);
      padding: 0.75rem 1.25rem;
      border-radius: 8px;
      width: 100%;
      max-width: 1200px;
      margin: 0 auto;
    }

    /* Segment 1: Identity/Workspace (Shrinkable, Truncatable) */
    .c-toolbar__identity {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      /* Flex mechanics: fleksibel menyusut, tidak membesar */
      flex-grow: 0;
      flex-shrink: 1;
      flex-basis: 280px;
      min-width: 120px; /* Batas kritis penyusutan */
    }

    .c-toolbar__badge {
      width: 32px;
      height: 32px;
      border-radius: 6px;
      background: linear-gradient(135deg, #3b82f6, #1d4ed8);
      flex-shrink: 0; /* Icon avatar dilarang keras menyusut */
    }

    .c-toolbar__title-group {
      min-width: 0; /* ENABLER TRUNCATION: Override min-width auto */
      overflow: hidden;
    }

    .c-toolbar__title {
      font-size: 0.875rem;
      font-weight: 600;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .c-toolbar__subtitle {
      font-size: 0.75rem;
      color: var(--ui-text-muted);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    /* Segment 2: Search Input (Highly Elastic, Dynamic Growth) */
    .c-toolbar__search-cluster {
      flex-grow: 1;
      flex-shrink: 1;
      flex-basis: 300px;
      max-width: 480px;
      min-width: 160px;
    }

    .c-toolbar__input {
      width: 100%;
      background-color: #0b1120;
      border: 1px solid var(--ui-border);
      color: var(--ui-text-main);
      padding: 0.5rem 0.75rem;
      border-radius: 6px;
      font-size: 0.875rem;
      outline: none;
      transition: border-color 0.15s ease-in-out;
    }

    .c-toolbar__input:focus {
      border-color: var(--ui-accent);
    }

    /* Segment 3: Actions (Strictly Rigid, Zero Shrink, Zero Grow) */
    .c-toolbar__actions {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-grow: 0;
      flex-shrink: 0; /* Anti-collapse guarantee */
      flex-basis: auto;
    }

    .c-btn {
      appearance: none;
      border: 0;
      padding: 0.5rem 0.875rem;
      font-size: 0.875rem;
      font-weight: 500;
      border-radius: 6px;
      cursor: pointer;
      white-space: nowrap;
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
    }

    .c-btn--secondary {
      background-color: #1e293b;
      color: var(--ui-text-main);
    }

    .c-btn--primary {
      background-color: var(--ui-accent);
      color: #ffffff;
    }
  </style>
</head>
<body>

  <nav class="c-toolbar" aria-label="Financial Analytics Engine Controls">
    <div class="c-toolbar__identity">
      <div class="c-toolbar__badge" aria-hidden="true"></div>
      <div class="c-toolbar__title-group">
        <h1 class="c-toolbar__title">Sovereign Debt Real-time Multi-Index Aggregator</h1>
        <p class="c-toolbar__subtitle">Production Node: SG-109</p>
      </div>
    </div>

    <div class="c-toolbar__search-cluster">
      <input type="search" class="c-toolbar__input" placeholder="Query transactions, bonds, or ISIN..." aria-label="Search Engine">
    </div>

    <div class="c-toolbar__actions">
      <button type="button" class="c-btn c-btn--secondary">Filters</button>
      <button type="button" class="c-btn c-btn--primary">Export CSV</button>
    </div>
  </nav>

</body>
</html>
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek Arsitektural | Flexbox (FFC) | CSS Grid (GFC) | Absolute/Fixed Positioning |
| :--- | :--- | :--- | :--- |
| **Dimensi Kerja** | **Satu Dimensi (1D):** Menangani baris atau kolom secara independen. | **Dua Dimensi (2D):** Menangani baris dan kolom secara sinkron dalam matriks. | **Non-Dimensi:** Melepas elemen sepenuhnya dari alur dokumen normal. |
| **Penetapan Dimensi** | **Content-First:** Dimensi item dihitung berdasarkan ukuran konten intrinsik. | **Layout-First:** Konten dipaksa tunduk pada *grid-track* yang ditentukan container. | **Manual Diktat:** Dimensi diikat manual oleh koordinat `top`/`left`/`right`/`bottom`. |
| **Interaksi Ruang** | Mengalir elastis via rasio bobot `grow` dan `shrink`. | Mengisi track berbasis fraksi (`fr`), `minmax()`, atau piksel kaku. | Statis; tidak ada kalkulasi *free space negotiation*. |
| **Kasus Penggunaan Ideal** | Toolbar, button group, navbar item, media object, list linier. | Dashboard kompleks, kartu katalog multi-arah, kerangka halaman inti. | Modal dialog, tooltip kontekstual, floating action buttons (FAB). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Implied Minimum Size Problem (`min-width: auto`)
* **Masalah:** Berdasarkan spesifikasi CSS Flexible Box Layout Level 1, nilai bawaan untuk `min-width` pada flex item bukanlah `0`, melainkan `auto`. Akibatnya, browser menghitung ukuran terkecil item berdasarkan ukuran konten intrinsiknya (*content-based min-size*). Teks panjang atau gambar besar akan menolak menyusut melebihi ukuran kontennya, memicu *layout overflow*.
* **Mitigasi:** Terapkan `min-width: 0` (atau `min-height: 0` pada konteks `flex-direction: column`) pada flex item yang memuat konten elastis.

### 2. Collapsing Margin Desync
* **Masalah:** Flex container **tidak mengeksekusi margin-collapsing** antar-child items maupun antara parent dan child item. Jika Anda bermigrasi dari layout *flow block* klasik, margin vertikal yang sebelumnya saling menyatu (*collapsed*) akan tiba-tiba menjumlahkan nilai spasialnya.
* **Mitigasi:** Hapus margin vertikal dari flex item dan standarisasikan jarak menggunakan properti modern `gap`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Mengabaikan Penulisan Properti Singkat (`shorthand`)
* *Anti-Pattern:*
  ```css
  .item {
    flex-grow: 1; /* flex-shrink dan flex-basis menjadi implisit/tidak terduga */
  }
  ```
* *Koreksi:* Gunakan selalu shorthand tiga nilai:
  ```css
  .item {
    flex: 1 1 0%; /* Explisit: grow=1, shrink=1, basis=0% */
  }
  ```
  *Alasan:* `flex: 1` mengubah default `flex-basis` menjadi `0%`, sedangkan deklarasi parsial `flex-grow: 1` membiarkan `flex-basis` berada pada nilai defaultnya yaitu `auto`. Ini menghasilkan perilaku matematis yang jauh berbeda.

### Kesalahan Fatal 2: Menghitung Lebar Anak Menggunakan Persentase Kaku
* *Anti-Pattern:*
  ```css
  .flex-container { display: flex; }
  .flex-item { width: 33.33%; margin: 10px; } /* Rentan overflow jika ada border/gap */
  ```
* *Koreksi:*
  ```css
  .flex-container { display: flex; gap: 20px; }
  .flex-item { flex: 1 1 0%; }
  ```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan `gap` daripada Margin Spasial:** Deklarasikan kontrol ruang pada kontainer (`gap`, `row-gap`, `column-gap`). Ini mencegah perlunya teknik lama seperti selektor `:last-child { margin-right: 0; }`.
2. **Definisikan Rigid Item dengan `flex-shrink: 0`:** Setiap elemen fungsional statis (misalnya: *badge, icon wrapper, avatar*) wajib memiliki `flex-shrink: 0` agar dimensinya tidak terdegradasi saat kontainer menerima tekanan spasial ekstrem.
3. **Pemisahan Logis via Auto Margin:** Untuk memisahkan item ke ujung kontainer (misalnya tombol aksi di navigasi), hindari penggunaan kontainer perantara tak perlu. Gunakan `margin-left: auto` pada item target. Margin auto di dalam FFC akan menyerap seluruh sisa ruang kosong pada sumbu terkait.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Layout Thrashing & Subtree Invalidation
Flexbox mengkalkulasi posisi melalui algoritma multi-pass jika menggunakan nilai dimensi yang ambigu (`flex-basis: auto`).
* **Optimasi:** Menetapkan `flex-basis: 0%` atau `flex-basis: 0px` (biasanya melalui `flex: 1`) mempercepat engine browser karena browser dapat melewati fase perhitungan ukuran intrinsik elemen (*intrinsic sizing pass*) dan langsung membagi ruang kosong.
* **CSS Containment:** Pada flex items yang membungkus konten dinamis berulang berskala besar, terapkan deklarasi:
  ```css
  .massive-flex-item {
    contain: layout style;
  }
  ```
  Ini mengisolasi *layout pass* di dalam item tersebut, memastikan mutasi DOM internal tidak memicu rekalkulasi layout di seluruh flex container induk.

---

## SEKSI 16 — KEAMANAN & HARDENING

### Penipuan Visual vs Pembaca Layar (Visual vs Screen-Reader Disconnect)
* **Vulnerabilitas Aksesibilitas:** Properti `order` dan pengubahan arah alur via `flex-direction: row-reverse` atau `column-reverse` memanipulasi posisi visual elemen tanpa mengubah urutan DOM node.
* **Dampak:** Pengguna keyboard (*tabbing navigation*) dan pengguna *screen reader* akan melompat secara disorientatif melintasi antarmuka, menciptakan jebakan fokus (*focus trapping*) semu atau pelanggaran kepatuhan **WCAG 2.1 Success Criterion 1.3.2 (Meaningful Sequence)**.
* **Solusi Hardening:**
  * Jangan gunakan `order` untuk mengubah urutan hierarki semantik.
  * Jika alur membaca dokumen berubah, ubah urutan DOM secara native di berkas template (HTML/JSX/Vue). Gunakan `order` hanya untuk penyesuaian visual minor yang agnostik terhadap hierarki baca.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### DevTools Flexbox Inspector
Pada Chromium (Chrome/Edge DevTools) dan Gecko (Firefox Developer Tools):
1. Buka panel *Elements*, temukan badge bertuliskan `flex` di samping kontainer. Klik badge tersebut untuk mengaktifkan overlay garis kisi.
2. Analisis panel **Layout** -> sub-panel **Flexbox**. Perhatikan dimensi:
   * *Base Size*: Nilai `flex-basis` awal yang terbaca oleh engine.
   * *Growth / Shrink*: Besar alokasi piksel mutlak yang ditambahkan atau dikurangkan oleh engine.
   * *Overlapping Margins*: Deteksi sisa *Available Space*.

```
+-------------------------------------------------------------+
| DevTools Flex Overlay:                                      |
| [Flex Container] ---------------------------- (800 x 60px)  |
|   |--> [Item 1] Basis: 200px | Final: 295.33px (+95.33px)   |
|   |--> [Item 2] Basis: 150px | Final: 340.67px (+190.67px)  |
|   |--> [Item 3] Basis: 100px | Final: 100.00px (0.00px)     |
+-------------------------------------------------------------+
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
RUMUS MATEMATIS CEPAT:
1. Positif Space = ContainerWidth - Sum(ItemBasis) - Sum(Gaps)
   Pertambahan   = Positif Space * (ItemGrow / TotalGrow)
2. Negatif Space = Sum(ItemBasis) + Sum(Gaps) - ContainerWidth
   Pengurangan   = Negatif Space * (ItemBasis * ItemShrink) / TotalScaledShrinkFactor

DEKLARASI STANDAR FLEX SHORTHAND:
- flex: 0 1 auto;  --> Default browser. Tidak membesar, menyusut jika perlu, basis dari width/height/konten.
- flex: 1 1 0%;    --> Dianjurkan untuk fluid grid. Proporsional penuh, mengabaikan ukuran konten bawaan.
- flex: 0 0 250px; --> Rigid item. Anti membesar, anti menyusut, ukuran absolut terkunci di 250px.
- flex: auto;      --> flex: 1 1 auto; Fleksibel dengan memprioritaskan ukuran intrinsik konten.

SOLUSI BUG OVERFLOW INSTAN:
- Tambahkan `min-width: 0;` pada flex item yang memuat teks dengan text-overflow: ellipsis.
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Diberikan kontainer dengan lebar $600\text{px}$, tanpa padding, border, atau gap. Di dalamnya terdapat dua flex item:
* Item A: `flex: 1 1 200px`
* Item B: `flex: 3 1 200px`
Berapa lebar akhir item B?
* A) $300\text{px}$
* B) $350\text{px}$
* C) $400\text{px}$
* D) $450\text{px}$

### Soal 2
Mengapa teks panjang di dalam flex item menolak terpotong dengan `text-overflow: ellipsis` dan justru merusak lebar layout, meskipun properti overflow telah dikonfigurasi?
* A) Karena Flexbox menonaktifkan properti `overflow: hidden`.
* B) Karena flex item memiliki nilai default `min-width: auto` yang menghitung lebar intrinsik konten.
* C) Karena Flexbox memerlukan deklarasi `display: inline-block` pada container teks.
* D) Karena `white-space: nowrap` tidak didukung di dalam Flex Formatting Context.

### Soal 3
Bagaimana engine browser memproses kalkulasi penusutan (`flex-shrink`) saat ruang bernilai negatif, dibandingkan dengan ekspansi (`flex-grow`) saat ruang positif?
* A) Sama persis; hanya membagi negatif ruang berdasarkan rasio `flex