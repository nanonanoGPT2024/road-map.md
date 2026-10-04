# SEKSI 01 — IDENTITAS MODUL

* **Domain Kurikulum:** `03-Frontend-and-Mobile`
* **Sub-Domain:** Core Web Platform, Accessibility, & Web Performance
* **Track:** `html`
* **Bab:** 02
* **Modul:** 01
* **Judul:** Semantik Dokumen Tingkat Lanjut & Information Architecture
* **Level:** Advanced (Staff / Principal Engineer Perspective)
* **Prasyarat Pengetahuan:** HTML5 Fundamentals, DOM Tree Construction Basics, CSS Box Model, Dasar WCAG 2.1/2.2 AA.

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta mampu:

1. **Membedah & Mengimplementasikan Accessibility Object Model (AOM):** Memahami determinisme pemetaan tag semantik HTML5 langsung ke Accessibility Tree (`a11y tree`) tanpa ketergantungan berlebih pada ARIA atribut redundan.
2. **Merancang Document Information Architecture (IA):** Menyusun hierarki heading (`<h1>`–`<h6>`) dan landmark regions (`<main>`, `<nav>`, `<aside>`, `<header>`, `<footer>`, `<section>`, `<article>`) yang valid untuk rendering mesin perayap (SEO) dan Assistive Technologies (AT).
3. **Menganalisis Perilaku Komputasi Algoritma Heading Outline:** Menguraikan kegagalan implementasi W3C HTML5 Document Outline Algorithm pada browser modern dan menetapkan strategi mitigasi manual hierarki heading statis.
4. **Mencegah Anti-Pola Semantik & Performa Render:** Mengidentifikasi regresi performa browser yang diakibatkan oleh *DOM bloat* (`<div>` soup) serta memitigasi dampak *Reflow/Layout shift* yang bersumber dari struktur kontainer semantik yang cacat.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa web modern skala enterprise, HTML bukan sekadar bahasa penanda tata letak visual; **HTML adalah antarmuka data struktural primer yang dikonsumsi oleh tiga entitas non-visual:**
1. Mesin parser browser (Blink, Gecko, WebKit) untuk konstruksi DOM dan A11y Tree.
2. Mesin perayap (Crawler / Indexer Bot: Googlebot, Bingbot, YandexBot) untuk ekstraksi relasi informasi dan indexing.
3. Assistive Technology (Screen Reader: NVDA, JAWS, VoiceOver) untuk navigasi non-visual via keyboard dan kontrol audio.

```
       [Dokumen HTML Mentah]
                 │
                 ▼
       ┌───────────────────┐
       │   HTML Parser     │
       └─────────┬─────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
   ┌─────────┐      ┌───────────┐
   │ DOM     │      │   CSSOM   │
   │ Tree    │      │   Tree    │
   └────┬────┘      └─────┬─────┘
        │                 │
        ├─────────────────┘
        ▼
   ┌─────────┐
   │ Render  │  ──> [Raster / Pixel Display] (Manusia Visual)
   │ Tree    │
   └────┬────┘
        │
        ▼
   ┌─────────┐
   │ A11y    │  ──> [Screen Reader / Assistive Tech] (Aksesibilitas)
   │ Tree    │
   └─────────┘
```

Perubahan paradigma krusial:
* **Visual-First Thinking (Keliru):** Menggunakan `<div>` dan `<span>` lalu merekayasa bentuknya dengan CSS Flexbox/Grid dan menambal navigasinya menggunakan JavaScript event listeners.
* **Semantic-First Thinking (Staff Engineer):** Menyusun kerangka dokumen menggunakan penanda semantik terkaya secara intrinsik. *Style* hanyalah proyeksi visual; struktur adalah fondasi absolut. Jika stylesheet dinonaktifkan (`CSS unstyled`), dokumen harus tetap terbaca logis, navigasi heading harus utuh, dan hubungan semantik antar komponen data tetap transparan.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Hubungan antara penandaan semantik HTML5, pemrosesan browser engine, pembentukan Accessibility Tree, serta jalur rendering ke Screen Reader digambarkan sebagai berikut:

```
+--------------------------------------------------------------------------------------------------+
| WEB BROWSER CORE ENGINE (Blink / Gecko / WebKit)                                                 |
|                                                                                                  |
|  Raw Token Stream:                                                                               |
|  <header> -> <nav> -> <main> -> <article> -> <h2> -> <aside> -> <footer>                         |
|                                                                                                  |
|                                   PARSER LAYER                                                   |
|                                         │                                                        |
|                                         ▼                                                        |
|  +--------------------------------------------------------------------------------------------+  |
|  | DOM Tree Nodes                                                                             |  |
|  |                                                                                            |  |
|  |             HTMLDocument                                                                   |  |
|  |                   │                                                                        |  |
|  |                 <html>                                                                     |  |
|  |                   │                                                                        |  |
|  |                 <body>                                                                     |  |
|  |       ┌───────────┴───────────┬──────────────────────┐                                     |  |
|  |    <header>                <main>                 <footer>                                 |  |
|  |       │                       │                      │                                     |  |
|  |     <nav>           ┌─────────┴─────────┐         <small>                                  |  |
|  |                   <article>          <aside>                                               |  |
|  |                     │                   │                                                  |  |
|  |                    <h2>                <p>                                                 |  |
|  +--------------------------------------------------------------------------------------------+  |
|                                         │                                                        |
|                    TRANSLATION TO COMPUTED ACCESSIBILITY TREE                                    |
|                                         ▼                                                        |
|  +--------------------------------------------------------------------------------------------+  |
|  | Accessibility Tree (Platform APIs: MSAA / IAccessible2 / UIA / ATK)                        |  |
|  |                                                                                            |  |
|  | [RootWebArea]                                                                              |  |
|  |   │                                                                                        |  |
|  |   ├── [banner] (Implicitly from <header> directly under <body>)                            |  |
|  |   │     └── [navigation] (Implicitly from <nav>)                                           |  |
|  |   │                                                                                        |  |
|  |   ├── [main] (Implicitly from <main>)                                                      |  |
|  |   │     │                                                                                  |  |
|  |   │     ├── [article] (Implicitly from <article>)                                          |  |
|  |   │     │     └── [heading, Level: 2, Name: "Judul Konten"]                                |  |
|  |   │     │                                                                                  |  |
|  |   │     └── [complementary] (Implicitly from <aside> scoped to <main>)                     |  |
|  |   │           └── [paragraph]                                                              |  |
|  |   │                                                                                        |  |
|  |   └── [contentinfo] (Implicitly from <footer> directly under <body>)                       |  |
|  +--------------------------------------------------------------------------------------------+  |
|                                         │                                                        |
+-----------------------------------------┼--------------------------------------------------------+
                                          │ Exposed through OS Accessibility Bridge
                                          ▼
                +---------------------------------------------------+
                | ASSISTIVE TECHNOLOGIES (NVDA / JAWS / VoiceOver)  |
                |                                                   |
                | Rotor Navigation:                                 |
                | - Jump directly to Landmarks (D, R shortcuts)     |
                | - Jump directly to Headings (H, 1-6 shortcuts)   |
                | - Read Structural Roles without synthetic ARIA    |
                +---------------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Landasan Pemetaan Implicit ARIA Semantics
Setiap elemen semantik HTML5 dipetakan secara intrinsik ke spesifikasi *HTML Accessibility API Mappings (HTML-AAM)*. Browser tidak memerlukan penambahan manual `role=""` jika elemen native telah digunakan.

| Elemen HTML5 | Implicit Role | Konteks Validitas Pemetaan |
| :--- | :--- | :--- |
| `<header>` | `banner` | Berlaku HANYA jika berada langsung dalam konteks `<body>` dan bukan di dalam `<article>`, `<aside>`, `<main>`, `<nav>`, atau `<section>`. |
| `<footer>` | `contentinfo` | Berlaku HANYA jika berada langsung dalam konteks `<body>`. |
| `<main>` | `main` | Konteks eksekusi konten utama dokumen. Maksimal 1 instans tersembunyi (non-`hidden`) dalam satu dokumen. |
| `<nav>` | `navigation` | Landmark untuk blok tautan navigasi mayor dokumen. |
| `<aside>` | `complementary` | Konten pendukung; jika disarangkan dalam `<article>`, perannya berubah menjadi pelengkap spesifik artikel tersebut. |
| `<section>` | `region` | Memiliki implicit role `region` **HANYA JIKA** memiliki accessible name (`aria-labelledby` atau `aria-label`). Tanpa nama aksesibel, perannya menjadi *generic* (sama seperti `<div>`). |
| `<article>` | `article` | Konten independen, tersendiri (*self-contained*), dan dapat didistribusikan ulang (syndicated). |

### 2. Anatomi Heading Levels & Accessible Name Computation
Saat browser memproses tag heading:
1. Engine membaca tag `<h1>` hingga `<h6>`.
2. Engine mengidentifikasi *Accessible Name Computation* (mengambil konten teks langsung, atribut `aria-label`, atau `aria-labelledby`).
3. Engine menetapkan properti `level` (integer 1-6).

Jika developer menggunakan `<div class="h1">`, engine memetakan node tersebut sebagai `generic container` tanpa properti `role="heading"` dan tanpa properti `level`. Pembaca layar tidak dapat mendaftar teks tersebut ke dalam daftar navigasi cepat (*Headings List*).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Mitos & Realitas "HTML5 Outline Algorithm"
Pada draf awal HTML5, W3C memperkenalkan konsep *Document Outline Algorithm*. Teori resminya menyatakan bahwa setiap kali elemen sectioning (`<section>`, `<article>`, `<nav>`, `<aside>`) digunakan, hierarki heading di dalamnya di-reset ke level 1:

```html
<!-- TEORI W3C DRAF AWAL: JANGAN DIAPLIKASIKAN -->
<h1>Judul Portal</h1>
<section>
  <h1>Judul Section (Diharapkan otomatis dianggap H2 oleh browser)</h1>
  <article>
    <h1>Judul Artikel (Diharapkan otomatis dianggap H3 oleh browser)</h1>
  </article>
</section>
```

#### Mengapa Pola Tersebut Gagal di Produksi?
1. **Tidak Pernah Diimplementasikan Oleh Browser Engine Manapun:** Baik Blink, WebKit, maupun Gecko tidak pernah mengimplementasikan parser yang mentransformasi komputasi level heading berdasarkan nesting sectioning container secara otomatis ke Accessibility Tree.
2. **Dampak Bencana bagi Aksesibilitas:** Jika Anda menulis kode di atas, Screen Reader akan mengidentifikasi tiga heading bertingkat `Level 1` (`<h1>`). Pengguna tuna netra akan kehilangan konteks kedalaman dokumen dan struktur relasi informasi.
3. **Depresiasi Spesifikasi:** Algoritma tersebut secara resmi telah ditarik dan didepresiasi dari standar aktif WHATWG.
4. **Mandat Modern:** Developer **wajib** mengelola level heading secara manual dan eksplisit dari `<h1>` hingga `<h6>` secara berurutan, tanpa bergantung pada nesting tag sectioning.

### Information Architecture: Dokumen Model Multi-Kolom
Arsitektur informasi tingkat lanjut menuntut pemisahan tegas antara:
* **Global Navigation:** Navigasi lintas situs (`<header>` -> `<nav aria-label="Navigasi Utama">`).
* **Contextual Navigation:** Navigasi spesifik halaman/dokumen (`<nav aria-label="Daftar Isi Artikel">`).
* **Content Hierarchy:** Tubuh data (`<main>`) yang dibagi secara berimbang menjadi komponen mandiri (`<article>`) dan komponen pendukung (`<aside>`).

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah contoh implementasi struktur semantik tingkat lanjut dokumen artikel teknis enterprise yang mematuhi standar HTML-AAM:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Analisis Arsitektur Sistem Skala Besar - Enterprise Portal</title>
</head>
<body>

  <!-- Landmark: banner -->
  <header>
    <a href="#main-content" class="skip-link">Loncat ke Konten Utama</a>
    <div class="brand-container">
      <img src="/logo.svg" alt="Enterprise Portal Logo" width="120" height="40">
    </div>
    <!-- Landmark: navigation (Global) -->
    <nav aria-label="Navigasi Utama">
      <ul>
        <li><a href="/">Beranda</a></li>
        <li><a href="/arsitektur" aria-current="page">Arsitektur</a></li>
        <li><a href="/telemetri">Telemetri</a></li>
      </ul>
    </nav>
  </header>

  <!-- Landmark: main -->
  <main id="main-content">
    
    <!-- Landmark: article (Konten Inti Mandiri) -->
    <article>
      <header>
        <h1>Implementasi Distributed Event Bus Menggunakan EventStoreDB</h1>
        <p class="metadata">
          Diterbitkan oleh <span class="author">Staff Infrastructure Team</span> pada 
          <time datetime="2025-05-15T09:00:00Z">15 Mei 2025</time>
        </p>
      </header>

      <!-- Landmark: navigation (In-page / TOC) -->
      <nav aria-label="Daftar Isi Artikel">
        <h2>Daftar Isi</h2>
        <ol>
          <li><a href="#latar-belakang">Latar Belakang Masalah</a></li>
          <li><a href="#implementasi-teknis">Implementasi Teknis</a></li>
        </ol>
      </nav>

      <!-- Sectioning dengan Accessible Name -->
      <section id="latar-belakang" aria-labelledby="heading-latar-belakang">
        <h2 id="heading-latar-belakang">Latar Belakang Masalah</h2>
        <p>
          Ketika monolit dipecah menjadi layanan independen, orkestrasi status membutuhkan mekanisme event audit yang tidak dapat dimutasi.
        </p>
      </section>

      <section id="implementasi-teknis" aria-labelledby="heading-implementasi">
        <h2 id="heading-implementasi">Implementasi Teknis</h2>
        <p>
          Penggunaan projection engine internal memfasilitasi rekonsiliasi data secara konsisten.
        </p>
        
        <!-- Sub-section level 3 -->
        <section id="optimasi-jaringan" aria-labelledby="heading-optimasi">
          <h3 id="heading-optimasi">Optimasi Jaringan TCP</h3>
          <p>
            Konfigurasi soket TCP `keep-alive` pada pipeline internal.
          </p>
        </section>
      </section>

      <footer>
        <p>Kategori: <a href="/kategori/infrastruktur">Infrastruktur</a></p>
      </footer>
    </article>

    <!-- Landmark: complementary (Relasional terhadap halaman) -->
    <aside aria-labelledby="heading-artikel-terkait">
      <h2 id="heading-artikel-terkait">Artikel Terkait</h2>
      <ul>
        <li><a href="/cqrs-pattern">Penerapan Pola CQRS pada Go Microservices</a></li>
      </ul>
    </aside>

  </main>

  <!-- Landmark: contentinfo -->
  <footer>
    <p>&copy; 2025 Enterprise Portal System. Seluruh hak cipta dilindungi.</p>
  </footer>

</body>
</html>
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 11:** `<a href="#main-content" class="skip-link">Loncat ke Konten Utama</a>`<br>
  *Mekanisme Bypass Block*. Esensial bagi pengguna screen reader dan keyboard-only navigation untuk melompati deretan link navigasi dan langsung menuju ke elemen interaktif utama pertama.
* **Baris 17:** `<nav aria-label="Navigasi Utama">`<br>
  Atribut `aria-label` membedakan instans `<nav>` ini dengan `<nav>` lain di baris 39. Tanpa label eksplisit, screen reader hanya mengumumkan "Navigation", memaksa pengguna menebak konteks tautan yang ada di dalamnya.
* **Baris 27:** `<main id="main-content">`<br>
  Menandai awal dari *primary payload* dokumen. Menggunakan `id="main-content"` sebagai sasaran langsung dari anchor *skip link*.
* **Baris 30:** `<article>`<br>
  Mendefinisikan unit konten yang kohesif. Tag `<article>` diperbolehkan memiliki tag `<header>` (baris 31) dan `<footer>` (baris 66) sendiri tanpa merusak pemetaan `role="banner"` atau `role="contentinfo"` di level dokumen.
* **Baris 34:** `<time datetime="2025-05-15T09:00:00Z">`<br>
  Menyediakan data waktu yang dapat dibaca manusia secara visual (`15 Mei 2025`), sekaligus mesin perayap dan parser AT memperoleh ISO-8601 string yang tidak ambigu.
* **Baris 48:** `<section id="latar-belakang" aria-labelledby="heading-latar-belakang">`<br>
  Elemen `<section>` diberikan `aria-labelledby` yang merujuk pada `id` dari `<h2>` di dalamnya. Hal ini secara otomatis menaikkan status elemen dari generik menjadi *landmark role* `region`.
* **Baris 60:** `<h3>Optimasi Jaringan TCP</h3>`<br>
  Penurunan hierarki dilakukan secara strictly inkremental (`h1` -> `h2` -> `h3`). Tidak ada *heading skipping* (misal melompat dari `h1` langsung ke `h3`).
* **Baris 72:** `<aside aria-labelledby="heading-artikel-terkait">`<br>
  Menyediakan peran `complementary`. Karena berada di dalam `<main>`, ini mengindikasikan bahwa data pendukung ini relevan terhadap flow dokumen utama.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Dashboard E-Commerce Multi-Vendor Enterprise
Sebuah platform e-commerce skala besar bermigrasi dari arsitektur *Single Page Application* murni berbasis ribuan `<div>` bertingkat (*div-soup*) ke *Modern Micro-Frontend SSR Architecture*. Audit awal menghasilkan temuan berikut:

1. **Accessibility Score Lighthouse:** 42/100.
2. **Keluhan Pengguna Non-Visual:** Pengguna tuna netra tidak dapat melompat langsung ke filter produk atau daftar transaksi; mereka harus membaca seluruh DOM dari atas ke bawah.
3. **SEO Degradation:** Mesin pencari mengindeks teks menu navigasi dan footer sebagai ringkasan deskripsi produk karena hilangnya batas semantik `<main>` dan `<article>`.
4. **Masalah DOM Nodes:** Total node DOM mencapai > 4.500 node akibat pembungkus non-semantik yang tidak terkendali.

### Solusi Rekayasa
Merekonstruksi Information Architecture dokumen web menggunakan spesifikasi HTML5 Semantics murni, membersihkan pembungkus kontainer yang tidak berguna, membedakan *multiple navigation instances* melalui tokenisasi label ARIA, dan menetapkan struktur outline heading manual yang deterministik.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah arsitektur template produksi untuk halaman detail produk enterprise yang menyatukan seluruh prinsip di atas:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>High-Performance Mechanical Keyboard - Enterprise Gear</title>
  <link rel="stylesheet" href="/styles/semantic-layout.css">
</head>
<body>

  <!-- ACCESSIBILITY SKIP UTILITY -->
  <a href="#primary-product-content" class="visually-hidden focusable">
    Langsung ke detail produk
  </a>

  <!-- TOP-LEVEL SITE BANNER -->
  <header class="site-header" role="banner">
    <div class="site-header__brand">
      <a href="/" aria-label="Enterprise Gear Beranda">
        <svg aria-hidden="true" width="40" height="40"><circle cx="20" cy="20" r="18"/></svg>
      </a>
    </div>

    <!-- GLOBAL SITE NAVIGATION -->
    <nav class="site-nav" aria-label="Navigasi Utama Situs">
      <ul role="list">
        <li><a href="/katalog">Katalog Perangkat</a></li>
        <li><a href="/deals">Promo Server</a></li>
        <li><a href="/dukungan">Pusat Bantuan</a></li>
      </ul>
    </nav>
  </header>

  <!-- BREADCRUMBS: TERISOLASI SECARA SEMANTIK -->
  <nav class="breadcrumb-nav" aria-label="Rekam Jejak Navigasi (Breadcrumb)">
    <ol role="list">
      <li><a href="/">Beranda</a></li>
      <li><a href="/katalog">Katalog</a></li>
      <li><a href="/katalog/periferal">Periferal</a></li>
      <li><span aria-current="location">Mechanical Keyboard MK-800</span></li>
    </ol>
  </nav>

  <!-- CORE INFORMATION ARCHITECTURE -->
  <main id="primary-product-content" class="content-boundary">
    
    <!-- PRIMARY CONTENT UNIT -->
    <article class="product-entity" aria-labelledby="product-name">
      
      <header class="product-entity__header">
        <h1 id="product-name">Enterprise Mechanical Keyboard MK-800</h1>
        <p class="product-entity__sku">SKU: <span class="monospaced">KB-MK800-PRO</span></p>
      </header>

      <!-- VISUAL/GALLERY SECTION -->
      <section class="product-gallery" aria-label="Galeri Gambar Produk">
        <figure class="media-container">
          <img src="/img/mk800-main.webp" 
               alt="Tampak atas keyboard mekanikal MK-800 dengan layout tenkeyless berwarna abu-abu gelap"
               width="800" 
               height="600" 
               fetchpriority="high">
          <figcaption>Tata letak TKL ringkas dengan switch hot-swappable.</figcaption>
        </figure>
      </section>

      <!-- TRANSACTION SECTION -->
      <section class="product-purchase" aria-labelledby="pricing-heading">
        <h2 id="pricing-heading" class="visually-hidden">Harga dan Pembelian</h2>
        <div class="price-display">
          <span class="price-currency">IDR</span>
          <data class="price-value" value="2450000">2.450.000</data>
        </div>
        
        <form action="/cart/add" method="POST" class="purchase-form">
          <input type="hidden" name="sku" value="KB-MK800-PRO">
          <button type="submit" class="cta-button">
            Tambahkan ke Keranjang
          </button>
        </form>
      </section>

      <!-- SPECIFICATION ACCORDION/TABULAR DATA -->
      <section class="product-specifications" aria-labelledby="specs-heading">
        <h2 id="specs-heading">Spesifikasi Teknis</h2>
        <dl class="tech-specs-list">
          <dt>Tipe Koneksi</dt>
          <dd>Tri-mode (USB-C Braided, 2.4GHz Wireless, Bluetooth 5.2)</dd>

          <dt>Daya Tahan Baterai</dt>
          <dd>Hingga 200 jam dalam kondisi lampu latar mati</dd>

          <dt>Kompatibilitas Sistem Operasi</dt>
          <dd>Linux Kernel 5.4+, Windows 11, macOS Sequoia</dd>
        </dl>
      </section>

    </article>

    <!-- COMPLEMENTARY/SIDEBAR CONTENT -->
    <aside class="product-complementary" aria-labelledby="related-products-heading">
      <h2 id="related-products-heading">Perangkat Pendukung</h2>
      
      <ul class="related-list" role="list">
        <li>
          <article class="product-card-micro" aria-labelledby="card-title-01">
            <h3 id="card-title-01">
              <a href="/produk/wrist-rest-wood">Ergonomic Wooden Wrist Rest</a>
            </h3>
            <p>Penyangga pergelangan tangan berbahan kayu walnut solid.</p>
          </article>
        </li>
        <li>
          <article class="product-card-micro" aria-labelledby="card-title-02">
            <h3 id="card-title-02">
              <a href="/produk/coiled-cable-usbc">Aviation Coiled Cable USB-C</a>
            </h3>
            <p>Kabel lilit fleksibel dengan konektor aviator GX16.</p>
          </article>
        </li>
      </ul>
    </aside>

  </main>

  <!-- BOTTOM METADATA & SYSTEM FOOTER -->
  <footer class="site-footer" role="contentinfo">
    <section class="footer-links" aria-label="Tautan Pendukung Perusahaan">
      <h2>Pusat Informasi</h2>
      <ul role="list">
        <li><a href="/kebijakan-privasi">Kebijakan Privasi</a></li>
        <li><a href="/syarat-ketentuan">Syarat & Ketentuan</a></li>
        <li><a href="/status">Status Sistem Service</a></li>
      </ul>
    </section>

    <div class="footer-legal">
      <p>&copy; <time datetime="2025">2025</time> PT Enterprise Gear Indonesia. Seluruh hak cipta terdaftar.</p>
    </div>
  </footer>

</body>
</html>
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter | Native HTML5 Semantic Elements | Synthetic `div` + Explicit ARIA Roles | Pure CSS Generic Nodes (`div` / `span`) |
| :--- | :--- | :--- | :--- |
| **Ukuran DOM Payload (HTML Over-The-Wire)** | **Sangat Ringan:** Menghindari atribut boilerplate tambahan pada tiap baris. | **Besar:** Menambahkan atribut `role`, `aria-*`, dan `tabindex` berulang kali. | **Minimalis:** Struktur ramping, namun tidak memiliki makna komputasi. |
| **Resiliensi Terhadap Kegagalan CSS/JS** | **Tinggi:** Dokumen terdegradasi secara mulus (*graceful degradation*), struktur tetap utuh saat CSS gagal termuat. | **Sedang:** Navigasi terbantu, namun *interactive behavior* via JS kerap macet bila bundle gagal dieksekusi. | **Nol:** Struktur kolaps menjadi dokumen datar tanpa hierarki yang jelas. |
| **Komputasi A11y Tree Browser** | **O(1) Direct Mapping:** Browser engine secara native mengeksekusi C++ mappings langsung ke OS A11y APIs. | **Tinggi:** Perlu evaluasi override runtime dari ARIA parser sebelum ditransfer ke AT. | **Minimal:** Namun menghasilkan pohon aksesibilitas kosong yang mengisolasi pengguna difabel. |
| **SEO Ranking Factor & Bot Parsing** | **Kinerja Terbaik:** Mesin pencari memprioritaskan heading level native dan tag landmark untuk snippet ekstraksi. | **Sedang:** Crawler modern mengenali ARIA, tetapi bobot native tags tetap menjadi *gold standard*. | **Buruk:** Crawler kesulitan memisahkan konten inti dengan navigasi/boilerplate. |
| **Biaya Pemeliharaan Kode (Code Maintenance)** | **Rendah:** Aturan struktur baku berbasis standar platform web global. | **Sangat Tinggi:** Rentan human-error akibat benturan role manual dan atribut usang. | **Rendah di awal, Bencana di skala besar:** Beban teknis menumpuk saat audit kepatuhan WCAG dilakukan. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Heading Level Gap (Melompati Level Hierarki)
* **Kegagalan:** Melompat dari `<h1>` langsung ke `<h3>` atau `<h4>` murni karena pertimbangan visual ukuran teks default browser.
* **Konsekuensi:** Screen reader memperingatkan pengguna bahwa ada bagian dokumen yang hilang (*missing parent context*).
* **Mitigasi:** Pisahkan ukuran visual dari tingkatan semantik:
  ```html
  <!-- Tepat: Tingkat semantik 2, namun di-styling agar menyerupai display ukuran kecil -->
  <h2 class="text-caption">Metadata Subtitle</h2>
  ```

### 2. "Generic Region" Problem pada `<section>`
* **Kegagalan:** Menggunakan puluhan tag `<section>` tanpa atribut `aria-labelledby` atau `aria-label`.
* **Konsekuensi:** Berdasarkan HTML-AAM, elemen `<section>` tanpa *accessible name* TIDAK diakui sebagai *landmark role* `region`. Browser akan menganggapnya ekuivalen dengan `<div>` biasa, membatalkan tujuan navigasi landmark.
* **Mitigasi:** Pasang selalu heading bernomor (`<h2>`-`<h6>`) di dalam `<section>` lalu tautkan via `aria-labelledby`.

### 3. Multiple `<main>` Conflict
* **Kegagalan:** Merender lebih dari satu elemen `<main>` tanpa atribut `hidden` dalam satu dokumen HTML.
* **Konsekuensi:** Melanggar spesifikasi W3C. Screen reader akan mengalami tabrakan konteks dalam penentuan landmark *Main Content*.
* **Mitigasi:** Pastikan arsitektur templating Anda hanya merender satu elemen `<main>` aktif. Jika menggunakan SPA pre-rendering/caching, beri atribut `hidden` pada instans `<main>` yang sedang tidak aktif di viewport.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Redundansi "First Rule of ARIA"
```html
<!-- KESALAHAN FATAL -->
<nav role="navigation">
<header role="banner">
<button role="button">Submit</button>

<!-- PERBAIKAN -->
<nav>
<header>
<button>Submit</button>
```
*Aturan Emas ARIA Pertama (W3C):* Jangan gunakan ARIA jika sudah ada elemen HTML native yang menyediakan semantik tersebut secara default. Duplikasi role di atas membuang byte jaringan dan mengindikasikan ketidaktahuan arsitektur web modern.

---

### Kesalahan 2: Menyalahartikan `<article>` sebagai Komponen Tata Letak Layout
```html
<!-- KESALAHAN FATAL: Membungkus kontainer UI semata-mata demi styling -->
<article class="card-wrapper-layout">
  <div>Item 1</div>
</article>

<!-- PERBAIKAN: Gunakan generic <div> untuk murni tata letak CSS Flex/Grid -->
<div class="card-grid">
  <article>
    <h2>Item 1</h2>
    <p>Deskripsi mandiri yang bisa di-syndicate.</p>
  </article>
</div>
```
Tag `<article>` mensyaratkan konten di dalamnya berdiri sendiri (*self-contained*). Jika konten tersebut diambil dan disebarkan via RSS feed, konten tersebut harus tetap masuk akal secara independen.

---

### Kesalahan 3: Menghancurkan List Semantics dengan Penataan CSS
```html
<!-- MASALAH TERSEMBUNYI -->
<nav>
  <ul style="list-style: none;">
    <li><a href="/a">A</a></li>
    <li><a href="/b">B</a></li>
  </ul>
</nav>
```
Pada mesin browser WebKit (Safari), menetapkan CSS `list-style: none` pada elemen `<ul>` atau `<ol>` akan **menghapus semantik list** dari Accessibility Tree (VoiceOver tidak akan mengumumkan *"List, 2 items"*).
* **Solusi Perbaikan:** Jika elemen tersebut memang sebuah daftar penting, tambahkan `role="list"` secara eksplisit pada tag `<ul>` sebagai mitigasi khusus Safari WebKit bug:
  ```html
  <ul role="list" class="unstyled-list">
  ```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Aturan 1 Dokumen = 1 `<h1>` Primer:** Meskipun draf HTML5 usang pernah membolehkan multi-`<h1>`, industri modern (Google Search Central, WCAG working group) merekomendasikan secara mutlak bahwa setiap dokumen web hanya memiliki **satu** `<h1>` yang mendeskripsikan tujuan utama halaman tersebut.
2. **Kemandirian Tag `<time>`:** Pasang format ISO-8601 standar pada atribut `datetime` (`YYYY-MM-DD` atau `YYYY-MM-DDTHH:MM:SSZ`) agar terbaca oleh parser kalender dan search crawler.
3. **Pemisahan Peran Landmark `<header>` dan `<footer>`:**
   * `<header>` langsung di bawah `<body>` = Landmark `banner`.
   * `<header>` di dalam `<article>` atau `<section>` = Non-landmark, penanda kepala konten lokal.
   * `<footer>` langsung di bawah `<body>` = Landmark `contentinfo`.
   * `<footer>` di dalam `<article>` atau `<section>` = Non-landmark, penanda kaki konten lokal.
4. **Accessible Skip-Links:** Sediakan link navigasi tersembunyi sebagai elemen DOM pertama dalam `<body>` yang menjadi fokus pertama via tab keyboard, mengarah langsung ke `id` dari `<main>`.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Flattening the DOM (Reduksi Kedalaman Tree)
Penggantian tag pembungkus tak berguna dengan elemen semantik berdampak langsung terhadap konsumsi memori browser:
* **DOM Memory Footprint:** Setiap elemen `<div>` instans memakan alokasi heap C++ (Node, Element, CSSComputedStyleDeclaration, LayoutObject). Mengurangi 1.000 div-soup wrapper menghemat ~1.2MB alokasi memori runtime pada V8/Blink.
* **Layout Thrashing & Recalculate Styles:** Menipiskan kedalaman tree (`tree depth`) dari 32 level menjadi 12 level mempercepat komputasi CSS Selector Matching hingga 40% pada perangkat mobile *low-end*.

### 2. Streaming Parser Delivery
HTML diparsing secara streaming (*chunk-by-chunk*). Menempatkan semantik struktural secara tepat memungkinkan browser mengalokasikan thread *Pre-