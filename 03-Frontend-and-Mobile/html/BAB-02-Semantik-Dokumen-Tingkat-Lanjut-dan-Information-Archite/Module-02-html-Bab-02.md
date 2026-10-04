# BAB 02: Semantik Dokumen Tingkat Lanjut dan Information Architecture (IA)
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Technical Architect / Principal Engineer diharapkan mampu:

1. **Menganalisis & Mengonstruksi** arsitektur semantik dokumen berbasis standar W3C/WHATWG yang secara paralel membangun struktur *Document Object Model* (DOM) dan *Accessibility Tree* (`AXTree`) yang valid, deterministik, dan bebas degradasi struktural.
2. **Mengevaluasi & Mengoreksi** kegagalan implementasi *Document Outline Algorithm* modern dengan menegakkan hierarki heading eksplisit ($H_1-H_6$) yang kompatibel secara lintas platform dengan mesin peramban (Blink, Gecko, WebKit) dan *Assistive Technologies* (JAWS, NVDA, VoiceOver).
3. **Merancang** topologi *Landmark Architecture* WAI-ARIA 1.2 pada platform berbasis *Single Page Applications* (SPA) dan *Micro-Frontends* guna memastikan navigasi linier/non-linier berjalan efisien bagi mesin crawler dan pembaca layar.
4. **Mengintegrasikan** metadata semantik mesin tingkat lanjut melalui sintaksis ganda (*JSON-LD* dan *Microdata*) yang beroperasi harmonis dengan DOM Hydration pada arsitektur SSR/SSG tanpa menimbulkan *hydration mismatch*.
5. **Mengukur & Mengoptimalkan** *DOM Node Budget*, kedalaman pohon (*DOM Depth*), dan rasio semantik terhadap *layout thrashing* untuk menjaga stabilitas *Core Web Vitals* (khususnya *Interaction to Next Paint* [INP] dan *Cumulative Layout Shift* [CLS]).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib memiliki pemahaman mendalam tentang:

* Siklus hidup rendering peramban (*Critical Rendering Path*): Tokenisasi HTML $\rightarrow$ *Node Creation* $\rightarrow$ DOM/CSSOM $\rightarrow$ Render Tree $\rightarrow$ Layout $\rightarrow$ Paint $\rightarrow$ Composite.
* Model parsing HTML5 living standard, penanganan *error-tolerant parsing*, dan transisi state pada *HTML Tokenizer*.
* Dasar-dasar spesifikasi WCAG 2.1/2.2 level A & AA, khususnya Success Criteria 1.3.1 (Info and Relationships) dan 2.4.1 (Bypass Blocks).
* Pemrograman JavaScript modern (ESNext) untuk manipulasi DOM dan interfacing dengan *Chrome DevTools Protocol* (CDP) atau *TreeWalker* API.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Mesin Browser: Parsing Semantik vs AXTree Synthesis
Ketika browser menerima stream byte HTML melalui jaringan, antarmuka jaringan meneruskan chunk data tersebut ke parser HTML. Parser menjalankan dua tahap utama: **Tokenisasi** dan **Konstruksi Pohon** (*Tree Construction*). 

```
Byte Stream (010010...) 
   │
   ▼ [Character Encoding Sniffing: UTF-8]
Characters ("<article>...")
   │
   ▼ [State Machine Tokenizer]
Tokens (StartTag: article, Character: ..., EndTag: article)
   │
   ▼ [Tree Builder & Speculative Parser]
DOM Tree  ──────────────────────┐
   │                            │ (Parallel Compute)
   ▼                            ▼
Render Tree ────────────► Accessibility Tree (AXTree)
(Visual: Layout & Paint)    (Semantic: UIA, AT-SPI, NSAccessibility)
```

1. **Tokenisasi**: State machine internal browser mengubah character stream menjadi token semantik (`StartTag`, `EndTag`, `Comment`, `Character`, `DOCTYPE`).
2. **Konstruksi DOM**: Node dialokasikan di dalam memori C++ peramban (contoh: objek `blink::Element` atau `blink::HTMLArticleElement`). Pada tahap ini, pembungkus V8 JavaScript (`v8::DOMWrapper`) juga dipetakan.
3. **Sintesis AXTree**: Bersamaan dengan pembangunan DOM dan kalkulasi gaya (computed styles), browser mengekstraksi representasi semantik menjadi **Accessibility Tree**. Mesin peramban mengekspos representasi ini ke antarmuka aksesibilitas tingkat sistem operasi:
   * **Windows**: UI Automation (UIA) / IAccessible2
   * **macOS / iOS**: NSAccessibility / UIAccessibility
   * **Linux**: AT-SPI2
   * **Android**: AccessibilityNodeInfo

Elemen semantik seperti `<main>`, `<nav>`, dan `<article>` secara otomatis memetakan properti `Role`, `Name`, `Value`, dan `State` ke antarmuka API OS tersebut tanpa overhead JavaScript runtime. Penggunaan `<div>` yang diberi gaya CSS agar menyerupai `<nav>` gagal mengaktifkan pemetaan ini pada level engine internal, sehingga rendering aksesibilitasnya runtuh (*accessibility degradation*).

#### B. The Broken Promise: Realitas Document Outline Algorithm
Spesifikasi HTML5 awal mendefinisikan *Document Outline Algorithm* teoretis: penggunaan elemen seksi (`<section>`, `<article>`, `<aside>`, `<nav>`) secara nested seharusnya secara otomatis mereset level hierarki heading. Sebagai contoh, sebuah `<h1>` di dalam `<section>` bersarang seharusnya dievaluasi setara dengan `<h2>` secara dinamis oleh User Agent.

**Realitas Industri & Vendor Mesin (Blink, WebKit, Gecko):**
Algoritma ini **tidak pernah diimplementasikan** oleh vendor peramban maupun vendor pembaca layar (NVDA, Freedom Scientific/JAWS, Apple VoiceOver) karena inefisiensi komputasi traversal dan risiko merusak backwards compatibility web purba.

*Implikasi Arsitektural:*
* Peramban tetap memperlakukan heading sesuai tag eksplisitnya ($H_1$ tetaplah $H_1$, terlepas dari seberapa dalam ia bersarang di dalam elemen `<article>`).
* Jika sistem frontend bergantung pada auto-downscaling heading melalui pembungkusan `<section>`, dokumen tersebut akan memiliki banyak $H_1$ yang setara secara hierarkis. Hal ini melanggar Success Criterion WCAG 1.3.1 dan merusak orientasi spasial pengguna screen reader serta menurunkan skoring kontekstual mesin perayap (crawler indexing).

#### C. Microdata vs. JSON-LD pada Tingkat Pengolahan Crawler
Arsitektur informasi modern harus melayani dua konsumen: manusia melalui visual/aural interface, dan agen otonom (*bot crawler*).

| Parameter | Microdata (Inline DOM Attributes) | JSON-LD (`<script type="application/ld+json">`) |
| :--- | :--- | :--- |
| **Parsing Overhead** | Terikat langsung pada parsing pohon DOM; memperbesar ukuran memori node HTML (`itemscope`, `itemtype`, `itemprop`). | Diurai oleh isolated V8/JSON parser di luar thread layout/paint; zero-cost terhadap CSSOM. |
| **Hydration Collision** | Rentan memicu React/Vue *hydration mismatch* jika atribut diubah secara asinkron di client. | Tidak disentuh engine virtual DOM reconciliation runtime jika diletakkan statis di head/body. |
| **Crawl Budget** | Crawler harus menyelesaikan konstruksi DOM parsial untuk membaca metadata. | Crawler dapat memotong pemrosesan (*early bailout*) dan mengekstrak entitas tanpa rendering CSS. |
| **Maintainability** | Buruk; bercampur dengan markah presentasional. | Sangat baik; payload dapat diserialisasi langsung dari layer data domain (DTO/GraphQL). |

*Rekomendasi Enterprise:* Gunakan **JSON-LD** sebagai mekanisme primer *Structured Data Layer* (Schema.org), dan batasi **Microdata** hanya untuk kasus *edge runtime* di mana fragment HTML didistribusikan via RSS/Atom feeds atau Web Components lintas domain tanpa skrip eksternal.

---

### 4. Why & What

#### Mengapa Arsitektur Semantik Krusial bagi Skala Enterprise?
1. **Efisiensi Anggaran Perayapan (*Crawl Budget Optimization*):** Search engine bot seperti Googlebot mengalokasikan alokasi waktu rendering terbatas (eksekusi WRS - *Web Rendering Service* berbasis headless Chromium). Dokumen yang memiliki hierarki semantik native memungkinkan bot mengekstrak konten terpenting pada *first pass* (HTTP response parsing mentah) tanpa harus mengantre untuk rendering JavaScript yang mahal.
2. **Eliminasi Hutang Aksesibilitas (*A11y Compliance Debt*):** Pelanggaran terhadap ADA (Americans with Disabilities Act) Title III dan European Accessibility Act (EAA) membawa risiko hukum dan denda finansial masif. Semantik native menjamin kepatuhan WCAG 2.1 AA secara deterministik sejak level markup, bukan melalui *patchwork* ARIA manual di JavaScript.
3. **Optimasi Memori Native V8/Blink:** Setiap elemen HTML generik (`<div>`) yang dimanipulasi dengan custom JS listeners dan ARIA attributes buatan membutuhkan alokasi memori heap lebih besar daripada elemen native yang fungsionalitas interaktif dan aksesibilitasnya telah tertanam secara terkompilasi di C++ layer browser.

#### Apa yang Dibangun?
Arsitektur Dokumen Perusahaan (*Enterprise Document Architecture*) yang terdiri dari:
* **Structural Skeleton**: Pemetaan topologi *Landmarks* yang bersih (`banner`, `navigation`, `main`, `complementary`, `contentinfo`).
* **Deterministic Heading Matrix**: Kontrak hierarki $H_1-H_6$ yang tidak boleh dilanggar oleh komponen independen.
* **Semantic Micro-Architecture**: Struktur atomik artikel, metadata waktu terstandarisasi ISO 8601, data tabular teranotasi, dan isolasi konten sampingan.

---

### 5. How (Workflow Detail)

Berikut adalah alur perancangan Information Architecture (IA) semantik untuk sistem berskala besar:

```
[Design System Wireframe]
           │
           ▼
[Step 1: Top-Level Landmark Mapping]
├── <header> (role="banner")
├── <nav>    (role="navigation" via aria-label)
├── <main>   (role="main")
├── <aside>  (role="complementary")
└── <footer> (role="contentinfo")
           │
           ▼
[Step 2: Heading Topology Matrix Validation]
├── Validasi single H1 per root application context
└── Penegakan Level $H_N \le H_{N-1} + 1$ (Pencegahan Heading Skipping)
           │
           ▼
[Step 3: Component Isolation & Sectioning Strategy]
├── Gunakan <article> untuk entitas yang dapat disindikasi mandiri
└── Gunakan <section> hanya bila memiliki heading penjelas terikat
           │
           ▼
[Step 4: Machine Metadata Injection]
└── Kompilasi DTO backend -> JSON-LD payload -> Sisipkan ke DOM
           │
           ▼
[Step 5: Automated Verification in CI/CD]
├── Tree-traversal script via axe-core / CDP
└── Validasi AXTree nodes via Headless Chromium
```

#### Workflow Langkah Demi Langkah:
1. **Landmark Decomposition**: Pisahkan canvas UI menjadi *structural zones*. Setiap zona harus dipetakan ke native landmark tag. Apabila terdapat lebih dari satu tag sejenis (misal: dua tag `<nav>`), sertakan `aria-label` unik (misal: `aria-label="Navigasi Utama"` dan `aria-label="Navigasi Footer"`).
2. **Heading Level Contract Assignment**: Buat abstraction layer pada framework frontend (misal: React Heading Provider context) untuk menghitung secara dinamis atau mengunci level heading berdasarkan kedalaman nesting, mencegah benturan hierarki antar tim micro-frontend.
3. **Sectioning Scoping**: Setiap pemanggilan `<section>` harus memiliki relasi kepemilikan eksplisit terhadap sebuah heading melalui atribut `aria-labelledby` atau child heading langsung. Jika sebuah kontainer tidak membutuhkan heading, gunakan `<div>`.
4. **Metadata Synthesizing**: Ekstrak graph data dari API backend dan cetak representasi Schema.org ke dalam tag `<script type="application/ld+json">` yang di-inject di level Server-Side Rendering (SSR).

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata:
Bayangkan sebuah **Gedung Perkantoran Modern Multi-Tenant**:
* **Landmarks**: Pintu gerbang utama (`<header>`), resepsionis/direktori lift (`<nav>`), lantai kerja operasional (`<main>`), ruang istirahat/koridor logistik (`<aside>`), dan basement utilitas terpusat (`<footer>`). Tanpa partisi ini, gedung tersebut hanyalah satu aula kosong masif berisi ribuan partisi tripleks tanpa penunjuk arah (`<div>` soup).
* **Headings ($H_1-H_6$)**: Papan nomor lantai dan nomor ruangan. Anda tidak bisa melompat dari penunjuk Lantai 1 langsung ke label Kamar 402 tanpa membingungkan pengunjung.
* **JSON-LD**: Sertifikat IMB, cetak biru arsitektur, dan izin operasional gedung yang diserahkan langsung ke dinas tata kota dalam format standar, tanpa memaksa petugas memeriksa setiap batu bata secara manual.

#### Diagram Interaksi DOM vs Accessibility Tree:

```
+-----------------------------------------------------------------------------------+
| RAW HTML STREAM                                                                   |
| <header><nav aria-label="Global">...</nav></header>                               |
| <main><article><h1>Judul</h1><p>Konten</p></article></main>                       |
+-----------------------------------------------------------------------------------+
                                         │
                   Browser Rendering Engine (Blink/Gecko)
                                         │
        ┌────────────────────────────────┴────────────────────────────────┐
        ▼                                                                 ▼
+───────────────────────────+                     +───────────────────────────────────+
|     DOCUMENT OBJECT       |                     |        ACCESSIBILITY TREE         |
|       MODEL (DOM)         |                     |             (AXTree)              |
+───────────────────────────+                     +───────────────────────────────────+
| Node: HTMLDocument        |                     | Role: RootWebArea                 |
|  └── Node: HTMLHeader     |                     |  ├── Role: Banner                 |
|       └── Node: HTMLNav   |                     |  │    └── Role: Navigation        |
|  └── Node: HTMLMain       |                     |  │         Name: "Global"         |
|       └── Node: HTMLArt.. |                     |  └── Role: Main                   |
|            ├── Node: H1   |                     |       └── Role: Article           |
|            └── Node: P    |                     |            ├── Role: Heading      |
+───────────────────────────+                     |            │    Level: 1          |
                                                  |            │    Name: "Judul"     |
                                                  |            └── Role: Paragraph    |
                                                  +───────────────────────────────────+
                                                                    │
                                                  Exposed to Assistive Tech APIs
                                                  (JAWS / NVDA / VoiceOver)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Anti-Pattern vs Pattern

##### Bad Implementation (Semantic Div-Soup):
```html
<!-- ANTI-PATTERN: Pelanggaran aksesibilitas, headless parser gagal memetakan landmarks -->
<div class="header">
  <div class="nav-links">
    <div class="link" onclick="location.href='/home'">Home</div>
    <div class="link" onclick="location.href='/products'">Products</div>
  </div>
</div>
<div class="main-content">
  <div class="title">Laporan Keuangan Q3</div>
  <div class="section-custom">
    <div class="subtitle">Pendapatan Bersih</div>
    <div class="text">Mencapai target 120% dari proyeksi.</div>
  </div>
</div>
```

##### Good Implementation (Clean Native Semantics):
```html
<!-- PRODUCTION GRADE: Terbaca sempurna oleh browser, AXTree, dan mesin pencari -->
<header>
  <nav aria-label="Navigasi Utama">
    <ul>
      <li><a href="/home">Home</a></li>
      <li><a href="/products">Products</a></li>
    </ul>
  </nav>
</header>
<main>
  <article>
    <h1>Laporan Keuangan Q3</h1>
    <section aria-labelledby="heading-pendapatan">
      <h2 id="heading-pendapatan">Pendapatan Bersih</h2>
      <p>Mencapai target 120% dari proyeksi.</p>
    </section>
  </article>
</main>
```

#### B. Practical Enterprise Example: Enterprise Product Detail Page (PDP)

Berikut adalah implementasi dokumen HTML standar produksi untuk modul e-commerce enterprise. Memadukan isolasi konten, breadcrumb navigation, Microdata, dan JSON-LD schema secara sinkron.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Asus ROG Zephyrus G14 (2024) - Enterprise Hardware Portal</title>
  <meta name="description" content="Spesifikasi teknis, ketersediaan inventaris, dan pengadaan unit laptop Asus ROG Zephyrus G14.">
  
  <!-- Canonical Document Verification -->
  <link rel="canonical" href="https://hardware.enterprise.com/laptops/asus-rog-g14-2024">

  <!-- Machine Readable Entity Layer: JSON-LD Graph Injection -->
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "BreadcrumbList",
        "itemListElement": [
          {
            "@type": "ListItem",
            "position": 1,
            "name": "Hardware",
            "item": "https://hardware.enterprise.com/"
          },
          {
            "@type": "ListItem",
            "position": 2,
            "name": "Laptops",
            "item": "https://hardware.enterprise.com/laptops"
          },
          {
            "@type": "ListItem",
            "position": 3,
            "name": "Asus ROG G14 2024"
          }
        ]
      },
      {
        "@type": "Product",
        "@id": "https://hardware.enterprise.com/laptops/asus-rog-g14-2024#product",
        "name": "Asus ROG Zephyrus G14 (2024)",
        "sku": "ROG-G14-2024-001",
        "description": "AMD Ryzen 9 8945HS, 32GB LPDDR5X, RTX 4070, 14-inch OLED 120Hz.",
        "brand": {
          "@type": "Brand",
          "name": "ASUS"
        },
        "offers": {
          "@type": "Offer",
          "url": "https://hardware.enterprise.com/laptops/asus-rog-g14-2024",
          "priceCurrency": "IDR",
          "price": "34999000",
          "availability": "https://schema.org/InStock",
          "priceValidUntil": "2026-12-31"
        }
      }
    ]
  }
  </script>
</head>
<body>
  <!-- Top-Level Skip Navigation for Power Users & Screen Readers -->
  <a href="#main-content" class="sr-only-focusable">Lewati ke Konten Utama</a>

  <!-- Global Platform Header -->
  <header role="banner">
    <div class="corporate-brand">
      <a href="/" aria-label="Portal Pengadaan Perusahaan - Beranda">
        <svg aria-hidden="true" width="40" height="40"><circle cx="20" cy="20" r="18"/></svg>
        <span>CorpSupply</span>
      </a>
    </div>

    <!-- Secondary Navigational Landmark -->
    <nav aria-label="Akses Cepat Akun">
      <ul>
        <li><a href="/procurement/orders">Pesanan Saya</a></li>
        <li><a href="/support">Dukungan Teknis</a></li>
      </ul>
    </nav>
  </header>

  <!-- Breadcrumb Navigation Architecture -->
  <nav aria-label="Jejak Navigasi (Breadcrumbs)">
    <ol>
      <li><a href="/">Beranda</a></li>
      <li><a href="/laptops">Laptop Enterprise</a></li>
      <li><span aria-current="page">Asus ROG G14 (2024)</span></li>
    </ol>
  </nav>

  <!-- Main Structural Landmark -->
  <main id="main-content" tabindex="-1">
    <article aria-labelledby="product-title">
      <header class="product-core-header">
        <h1 id="product-title">Asus ROG Zephyrus G14 (2024)</h1>
        <p class="sku-reference">SKU: <span data-spec="sku">ROG-G14-2024-001</span></p>
      </header>

      <!-- Primary Specification Breakdown -->
      <section aria-labelledby="specs-heading">
        <h2 id="specs-heading">Spesifikasi Komputasi</h2>
        <dl>
          <dt>Prosesor</dt>
          <dd>AMD Ryzen 9 8945HS (8 Cores, 16 Threads, up to 5.2 GHz)</dd>
          <dt>Kapasitas Memori</dt>
          <dd>32GB LPDDR5X 6400MHz</dd>
          <dt>Akselerator Grafis</dt>
          <dd>NVIDIA GeForce RTX 4070 (8GB GDDR6)</dd>
          <dt>Panel Visual</dt>
          <dd>14" 3K (2880 x 1800) OLED, Rasio 16:10, Refresh Rate 120Hz</dd>
        </dl>
      </section>

      <!-- Pricing and Procurement Logic -->
      <section aria-labelledby="procurement-heading">
        <h2 id="procurement-heading">Pengadaan Unit dan Lisensi</h2>
        <p>Harga Basis: <strong>IDR 34.999.000</strong> (Termasuk Pajak Pertambahan Nilai)</p>
        
        <form action="/api/v1/cart/checkout" method="POST">
          <input type="hidden" name="sku" value="ROG-G14-2024-001">
          <label for="quantity-selector">Kuantitas Pemesanan Batch:</label>
          <input type="number" id="quantity-selector" name="quantity" min="1" max="50" value="1">
          <button type="submit">Ajukan Surat Pesanan (PO)</button>
        </form>
      </section>
    </article>

    <!-- Contextually Related Aside Landmark -->
    <aside aria-labelledby="related-accessories-heading">
      <h2 id="related-accessories-heading">Aksesoris Kompatibel Resmi</h2>
      <ul>
        <li>
          <article>
            <h3><a href="/accessories/rog-100w-charger">Adaptor Daya USB-C 100W GaN</a></h3>
            <p>Pengisian daya ultra-ringkas untuk mobilitas kerja teknis.</p>
          </article>
        </li>
      </ul>
    </aside>
  </main>

  <!-- Platform Contentinfo Landmark -->
  <footer role="contentinfo">
    <section aria-labelledby="compliance-heading">
      <h2 id="compliance-heading" class="sr-only">Kepatuhan Hukum dan Hak Cipta</h2>
      <p>&copy; 2026 PT Perangkat Korporasi Indonesia. Seluruh hak cipta dilindungi undang-undang.</p>
      <nav aria-label="Kebijakan Legalitas">
        <ul>
          <li><a href="/legal/sla">Service Level Agreement (SLA)</a></li>
          <li><a href="/legal/privacy">Kebijakan Privasi Data Karyawan</a></li>
        </ul>
      </nav>
    </section>
  </footer>
</body>
</html>
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Sebuah platform publikasi finansial skala global (*Tier-1 Global Media*, memproses >120 juta *pageviews* bulanan) mengalami anomali serius:
1. **Penyusutan Organik Googlebot**: Efisiensi anggaran perayapan merosot sebesar 35%. WRS (Web Rendering Service) sering kali mengabaikan artikel berita baru karena keterbatasan kuota render CPU.
2. **Litigasi Aksesibilitas**: Menerima surat peringatan legal terkait ketidakpatuhan terhadap standar WCAG 2.1 AA (khususnya pembaca layar tersesat di dalam struktur portal yang terdiri dari 400+ `<div>` bersarang tanpa landmark boundaries).
3. **Hydration Mismatch Berulang**: Render microdata yang ditanam via React SSR sering kali mengalami desinkronisasi atribut dengan client state, memicu re-render layout menyeluruh (*Layout Thrashing*).

#### Intervensi Arsitektur
Tim Arsitektur Inti melakukan refactoring sistem besar-besaran:
1. **Eliminasi Total Div-Soup Wrapper**: Mengganti 12 layer `<div>` pembungkus kontainer aplikasi menjadi semantic bounds standar: `<header>`, `<nav>`, `<main>`, `<article>`, `<aside>`, `<footer>`.
2. **Strict Heading Orchestration System**: Mengintegrasikan linting compile-time menggunakan custom AST (Abstract Syntax Tree) validator pada build pipeline Vite/Webpack. Bila seorang engineer merender `<h3>` tanpa diawali `<h2>` di dalam komponen terkait, build process akan dihentikan secara otomatis (*fail-fast*).
3. **Pemisahan Total Microdata ke JSON-LD**: Seluruh deklarasi Schema.org dipindahkan dari inline attributes HTML ke serialisasi JSON-LD yang dirender sekali di edge network (Cloudflare Workers) pada fase streaming SSR response.

#### Metrik Keberhasilan (Hasil Pasca-Migrasi 90 Hari)
* **WRS Rendering Queue:** Turun dari latensi rata-rata 18 jam menjadi <4 menit untuk pengindeksan artikel breaking news.
* **Organic Search Traffic:** Naik 28.4% karena Googlebot mampu mengurai seluruh metadata Schema.org langsung pada tahap tokenisasi stream pertama.
* **WCAG Compliance Score:** Meningkat dari 58% menjadi 100% pada audit otomatis axe-core, meloloskan perusahaan dari risiko gugatan perdata.
* **DOM Node Count:** Mengurangi rata-rata jumlah DOM nodes per halaman dari 3.850 node menjadi 1.120 node, menghasilkan peningkatan performa *Interaction to Next Paint* (INP) sebesar 42ms.

---

### 9. Trade-offs

Setiap keputusan arsitektur semantik melibatkan kompromi teknis yang harus dievaluasi secara rasional:

| Strategi Arsitektur | Keuntungan | Kerugian & Konsekuensi Teknis | Skenario Pemilihan |
| :--- | :--- | :--- | :--- |
| **Native HTML Semantics Murni** | Menggunakan resource CPU native browser, zero bundle size, map langsung ke platform accessibility API secara deterministik. | Kurang fleksibel jika framework memerlukan nesting node arbitrer untuk styling CSS grid/flexbox kompleks. | Fondasi sistem web enterprise standar produksi; portal informasi, checkout, dan konten. |
| **Generik Divs + ARIA Attributes (`role="main"`, dll.)** | Memberikan kebebasan mutlak kepada styling system UI (CSS-in-JS, Tailwind) tanpa terikat default styling browser. | Memperbesar ukuran HTML; rawan kesalahan desinkronisasi manual; tidak terbaca oleh bot pencari non-JS sederhana. | Prototyping cepat atau legacy micro-frontends yang membungkus komponen pihak ketiga tak tersentuh. |
| **Shadow DOM Encapsulation (Web Components)** | Isolasi gaya dan markup internal komponen secara independen; mencegah style pollution. | Batas Shadow DOM memotong traversal heading linear; beberapa Assistive Technologies mengalami bug saat melintasi batas Shadow Tree. | Design system atomik terdistribusi lintas framework (React, Angular, Vue). |
| **JSON-LD vs Microdata** | Mengurangi beban parsing DOM; isolasi mutlak antara representasi data dan representasi visual. | Duplikasi data teks di HTML; potensi payload response awal membengkak jika data payload terlalu detail. | Wajib untuk SEO modern, integrasi schema produk, e-commerce, dan platform berita. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Multiple Elements `<main>` Terbuka Secara Bersamaan
* **Gejala:** Screen reader membacakan keberadaan lebih dari satu landmark "Main", membingungkan hierarki konten.
* **Penyebab:** Pada aplikasi SPA, rute baru dimuat tanpa membersihkan atau menyembunyikan tag `<main>` dari layout container pembungkus.
* **Solusi Teknis:** Hanya boleh ada **satu** elemen `<main>` yang terlihat (*visible*) dalam satu dokumen. Jika ada lebih dari satu, tag lainnya wajib memiliki atribut boolean `hidden`:
  ```html
  <main id="dashboard-view">...</main>
  <main id="settings-view" hidden>...</main>
  ```

#### 2. Heading Skipping (Level Hopping)
* **Gejala:** Pengguna screen reader melompat dari level `<h1>` langsung ke `<h4>` dan mengasumsikan ada bagian konten substansial yang hilang atau terlewat.
* **Penyebab:** Rekayasa visual berbasis kelas CSS dipaksakan ke tag heading (misal: developer menggunakan `<h4>` hanya karena ingin ukuran font yang kecil).
* **Solusi Teknis:** Pisahkan semantik hierarki dari gaya visual. Gunakan tag heading yang konsisten secara matematis, atur styling visual via utility classes:
  ```html
  <!-- SALAH -->
  <h1>Dasbor Keuangan</h1>
  <h4>Ringkasan Saldo</h4>

  <!-- BENAR -->
  <h1>Dasbor Keuangan</h1>
  <h2 class="text-sm font-normal">Ringkasan Saldo</h2>
  ```

#### 3. Redundansi Peran Eksplisit (*Redundant ARIA Landmarks*)
* **Gejala:** Konsol peringatan audit aksesibilitas memicu notice/warning terkait redundansi.
* **Penyebab:** Menambahkan `role="navigation"` ke tag `<nav>` atau `role="banner"` ke tag top-level `<header>`.
* **Solusi Teknis:** Jangan menduplikasi native semantics kecuali untuk menutupi bug spesifik browser warisan (Internet Explorer yang sudah obsolete). Gunakan native tags tanpa atribut role manual yang mubazir.

#### 4. Sectioning Tag Tanpa Judul (*Headless Sections*)
* **Gejala:** Validator HTML W3C mengeluarkan peringatan: *"A section not introduced by a heading."*
* **Penyebab:** Menjadikan `<section>` sebagai wrapper murni pengganti `<div>` untuk keperluan styling CSS flex/grid.
* **Solusi Teknis:** Jika sebuah blok layout tidak membutuhkan label/heading tersurat maupun tersirat, gunakan `<div>`. Tag `<section>` secara arsitektural wajib memiliki direct-heading yang mendeskripsikan blok tersebut.

#### 5. Skrip Otomatisasi Troubleshooting (Node.js + Axe-Core CI Script)
Implementasikan script ini pada pipeline CI/CD untuk menggagalkan *pull request* yang merusak hierarki semantik dokumen:

```javascript
// scripts/verify-semantics.mjs
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import assert from 'node:assert';

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  // Arahkan ke endpoint pengujian staging
  await page.goto('http://localhost:3000/products/sample-pdp');

  try {
    const results = await new AxeBuilder({ page })
      .withRules([
        'landmark-one-main',
        'page-has-heading-one',
        'heading-order',
        'landmark-unique'
      ])
      .analyze();

    if (results.violations.length > 0) {
      console.error('❌ Pelanggaran Semantik Dokumen Terdeteksi:');
      results.violations.forEach(violation => {
        console.error(`- ID: ${violation.id} [${violation.impact}]`);
        console.error(`  Deskripsi: ${violation.description}`);
        console.error(`  Node Target:`, violation.nodes.map(n => n.target));
      });
      process.exit(1);
    }

    console.log('✅ Verifikasi Semantik & Information Architecture Lolos Standar Enterprise.');
  } catch (error) {
    console.error('Kesalahan eksekusi pipeline validasi:', error);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
```

---

### 11. Best Practices (Production Checklist)

#### Architecture Phase
- [ ] Diagram Information Architecture telah dipetakan ke 5 Landmark Primer: `banner`, `navigation`, `main`, `complementary`, `contentinfo`.
- [ ] Single Source of Truth untuk Hierarki Heading: Hanya ada tepat satu `<h1>` utama per halaman logika.
- [ ] Skema penamaan multisitus diatur melalui `aria-label` jika terdapat lebih dari satu elemen `<nav>` (misal: Navigasi Global vs Navigasi Sub-Halaman).

#### Implementation Phase
- [ ] Isolasi konten independen yang dapat disindikasi (*syndicated*) menggunakan elemen `<article>`.
- [ ] Konten pelengkap yang memiliki dependensi tidak langsung terhadap topik utama dibungkus di dalam `<aside>`.
- [ ] Representasi data tabular keuangan/analitik wajib memiliki `<caption>`, `<thead scope="col">`, dan `<th scope="row">`.
- [ ] Data penanggalan yang dapat dibaca manusia wajib didampingi tag `<time datetime="YYYY-MM-DDThh:mm:ssTZD">`.
- [ ] Semua image kontekstual memiliki teks alternatif (`alt`) yang akurat; image murni presentasional memiliki atribut eksplisit `alt=""` atau ditandai `aria-hidden="true"`.

#### Machine-Readable Metadata (SEO & Linked Data)
- [ ] Seluruh skema terstruktur dikompilasi menggunakan validasi tipe Schema.org dalam format JSON-LD.
- [ ] Dokumen memuat tag canonical relasional yang mengarah ke URL tunggal yang divalidasi.
- [ ] Kontrak Open Graph (`og:`) dan Twitter Card sinkron dengan payload JSON-LD.

#### CI/CD & Deployment Phase
- [ ] Audit otomatis via `@axe-core` atau Google Lighthouse terpasang pada continuous delivery pipeline.
- [ ] Ambang batas maksimal DOM Depth tidak melebihi 32 level nesting.
- [ ] Ambang batas total DOM Nodes tidak melampaui 1.400 node per halaman view.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sebuah modul dokumen terisolasi yang mengimplementasikan arsitektur semantik dokumen tingkat lanjut dan memvalidasinya secara programatis.

#### Struktur Direktori:
```
hands-on/
└── m02/
    ├── package.json
    ├── index.html
    └── scripts/
        └── audit-dom.mjs
```

#### Langkah 1: Inisialisasi Repositori Praktikum
Buka terminal dan jalankan konfigurasi workspace:
```bash
mkdir -p hands-on/m02/scripts
cd hands-on/m02
npm init -y
npm install playwright @axe-core/playwright
```

Perbarui file `hands-on/m02/package.json` untuk mengaktifkan ES Modules:
```json
{
  "name": "hands-on-m02-semantics",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "audit": "node scripts/audit-dom.mjs"
  },
  "dependencies": {
    "@axe-core/playwright": "^4.10.1",
    "playwright": "^1.49.0"
  }
}
```

#### Langkah 2: Konstruksi Dokumen Semantik
Tulis dokumen semantik berikut ke dalam file `hands-on/m02/index.html`. Dokumen ini mensimulasikan portal analitik server perusahaan.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Observabilitas Infrastruktur - Node Telemetry Sektor A</title>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "TechArticle",
    "headline": "Observabilitas Infrastruktur - Node Telemetry Sektor A",
    "datePublished": "2026-03-31T08:00:00+07:00",
    "author": {
      "@type": "Organization",
      "name": "Cloud Infrastructure Operations"
    }
  }
  </script>
</head>
<body>
  <header role="banner">
    <nav aria-label="Portal Sistem">
      <ul>
        <li><a href="/telemetry">Telemetri</a></li>
        <li><a href="/alerts">Peringatan Sistem</a></li>
      </ul>
    </nav>
  </header>

  <main id="content">
    <article>
      <header>
        <h1>Laporan Telemetri Node Sektor A</h1>
        <p>Diperbarui pada: <time datetime="2026-03-31T07:55:00Z">31 Maret 2026, 07:55 UTC</time></p>
      </header>

      <section aria-labelledby="sec-metrics">
        <h2 id="sec-metrics">Metrik Komputasi Utama</h2>
        <table>
          <caption>Pemanfaatan Sumber Daya Node per Node Cluster</caption>
          <thead>
            <tr>
              <th scope="col">Node ID</th>
              <th scope="col">Utilisasi CPU</th>
              <th scope="col">Pemanfaatan Memori</th>
              <th scope="col">Status Operasional</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">node-compute-01a</th>
              <td>23.4%</td>
              <td>14.2 GB / 64 GB</td>
              <td>Stabil</td>
            </tr>
            <tr>
              <th scope="row">node-compute-02a</th>
              <td>89.1%</td>
              <td>58.7 GB / 64 GB</td>
              <td>Peringatan Beban Tinggi</td>
            </tr>
          </tbody>
        </table>
      </section>
    </article>

    <aside aria-labelledby="sec-incident-notes">
      <h2 id="sec-incident-notes">Catatan Insiden Terkait</h2>
      <p>Node-02a dijadwalkan untuk proses migrasi beban kerja ke zona ketersediaan cadangan.</p>
    </aside>
  </main>

  <footer role="contentinfo">
    <p><small>&copy; 2026 Operasional Infrastruktur Cloud Internasional.</small></p>
  </footer>
</body>
</html>
```

#### Langkah 3: Implementasi Script Audit
Buat script validasi DOM otomatis di `hands-on/m02/scripts/audit-dom.mjs`:

```javascript
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  const absolutePath = path.resolve(__dirname, '../index.html');
  await page.goto(`file://${absolutePath}`);

  console.log('🔍 Memulai Audit Semantik DOM dan Konstruksi AXTree...');

  const results = await new AxeBuilder({ page })
    .withRules([
      'landmark-one-main',
      'page-has-heading-one',
      'heading-order',
      'table-duplicate-name',
      'scope-attr-valid'
    ])
    .analyze();

  if (results.violations.length > 0) {
    console.error('❌ Audit Gagal! Terdeteksi pelanggaran standar semantik:');
    console.log(JSON.stringify(results.violations, null, 2));
    await browser.close();
    process.exit(1);
  }

  console.log('✅ Audit Sukses: Tidak ditemukan cacat semantik pada dokumen.');
  await browser.close();
})();
```

#### Langkah 4: Eksekusi Audit
Jalankan tes validasi melalui konsol:
```bash
npm run audit
```
Pastikan output mencetak pesan keberhasilan audit tanpa pelanggaran aturan.

---

### 13. Exercise

Kerjakan tiga modul refactoring kode di bawah ini untuk menguji pemahaman operasional Anda:

#### Level Easy
**Target:** Identifikasi dan perbaiki kesalahan penggunaan tag presentasional dan heading skipping pada widget feed ringkas berikut:
```html
<!-- REFACTOR KODE INI -->
<div class="feed-card">
  <b>Pembaruan Firmware v2.1</b>
  <p>Perbaikan kernel stability telah didistribusikan.</p>
  <div class="date">Waktu rilis: 12 April 2026</div>
</div>
```
*Syarat Keberhasilan:* Konversi ke tag semantik mandiri, gunakan heading level yang tepat, dan ubah tanggal presentasional ke native `<time>` tag dengan atribut `datetime` standar ISO.

#### Level Medium
**Target:** Bangun arsitektur dokumen layout untuk sebuah *Multi-Tenant Dashboard*.
*Syarat Keberhasilan:*
* Harus memiliki 2 navigasi berbeda: "Navigasi Global Sistem" dan "Navigasi Ruang Kerja Tenant" yang dibedakan secara aksesibel.
* Terapkan `skip-link` fungsional di awal dokumen untuk pembaca layar.
* Tabel analitik performa wajib menggunakan konfigurasi header kolom (`scope="col"`) dan baris (`scope="row"`).

#### Level Hard
**Target:** Rancang arsitektur dokumen HTML untuk halaman *Financial Annual Report* multi-bab interaktif yang beroperasi sebagai Hybrid SPA.
*Syarat Keberhasilan:*
* Desain struktur semantic landmarks yang mendukung dynamic context switching tanpa pernah memunculkan lebih dari satu elemen `<main>` visible secara bersamaan.
* Buat struktur navigasi outline (Table of Contents) yang mencerminkan hierarki $H_1, H_2, H_3$ secara matematis sinkron dengan teks isi.
* Sertakan validasi inline JSON-LD Graph multidimensi yang memuat `@type: "Report"` dan `@type: "Organization"` secara terhubung menggunakan field `@id`.

---

### 14. Challenge

#### Skenario Kasus Kompleks: High-Frequency Trading Live Terminal Markup Architecture
Anda adalah Lead Web Architect pada perusahaan sekuritas Wall Street. Anda ditugaskan merancang spesifikasi fondasi dokumen HTML untuk antarmuka terminal eksekusi trading real-time berbasis web.

#### Kendala & Persyaratan Ekstrem:
1. **Zero Layout Thrashing Target:** Data buku pesanan (*Order Book*) diperbarui dengan frekuensi 60Hz (via WebSocket stream). Format markup tabular harus dirancang sedemikian rupa sehingga pembaruan isi sel harga (`<td>`) tidak memicu reflow kalkulasi layout pada tag landmark tetangga (`<aside>`, `<nav>`).
2. **WCAG 2.1 AAA Compliance:** Terminal wajib dapat dioperasikan 100% oleh trader tuna netra yang menggunakan Screen Reader NVDA/VoiceOver dengan *refresh rate high-speed TTS*. Anda harus menentukan bagaimana `aria-live` regions diintegrasikan secara semantik tanpa membuat pembaca layar macet (*buffer choke*) akibat luapan pembaruan harga 60Hz.
3. **Complex Landmark Federation:** Terdapat 6 panel floating (Komponen Micro-frontend independen: Chart Canvas, Order Book, Depth Chart, Order Entry Form, News Stream, Risk Alerts). Rancang kontrak Information Architecture HTML yang menjamin keenam panel ini tidak menciptakan kekacauan *Landmark Hierarchy* saat salah satu panel di-docking, di-minimize, atau di-undock ke *window* terpisah.

#### Tugas Arsitektural Anda:
Tuliskan cetak biru arsitektur dokumen HTML lengkap (kerangka dokumen, konfigurasi landmark, integrasi live region, dan hierarki heading level) yang siap diimplementasikan oleh tim rekayasa perangkat lunak frontend Anda!

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. **Bagaimana status implementasi *HTML5 Document Outline Algorithm* pada mesin browser modern saat ini (Blink, Gecko, WebKit)?**
   * A. Diimplementasikan penuh sejak versi HTML 5.2.
   * B. Berfungsi optimal hanya jika screen reader diaktifkan.
   * C. Tidak pernah diimplementasikan oleh vendor mesin browser maupun screen reader; hierarki heading harus dikelola secara manual eksplisit.
   * D. Digantikan secara otomatis oleh atribut `role="region"`.

2. **Tag HTML manakah yang paling tepat merepresentasikan unit konten yang dapat berdiri sendiri, dapat didistribusikan secara independen, dan dapat disindikasi ulang (misal via RSS)?**
   * A. `<section>`
   * B. `<article>`
   * C. `<aside>`
   * D. `<main>`

3. **Bila sebuah halaman web memiliki dua elemen `<nav>`, langkah apa yang wajib dilakukan untuk mematuhi Success Criterion WCAG 1.3.1?**
   * A. Mengubah salah satu tag `<nav>` menjadi `<div>`.
   * B. Memberikan atribut `aria-label` atau `aria-labelledby` yang berbeda pada masing-masing tag `<nav>`.
   * C. Menambahkan atribut `role="navigation"` hanya pada navigasi pertama.
   * D. Menjadikan navigasi kedua sebagai child dari elemen `<aside>`.

4. **Apa fungsi utama atribut `scope="row"` pada elemen `<th>` di dalam tabel HTML?**
   * A. Mengatur warna latar belakang baris secara otomatis melalui User Agent stylesheet.
   * B. Menggabungkan dua baris secara vertikal (*row spanning*).
   * C. Menegaskan relasi semantik bahwa sel header tersebut mendefinisikan label data untuk seluruh sel horizontal di baris yang sama pada AXTree.
   * D. Membatasi perambanan crawler pencari hanya pada baris tersebut.

5. **Manakah sintaks penulisan elemen penanggalan yang valid secara standar ISO 8601 dan dapat di-parse mesin dengan benar?**
   * A. `<time date="2026-03-31">31 Maret 2026</time>`
   * B. `<time datetime="2026-03-31T14:30:00+07:00">31 Maret 2026, 14:30 WIB</time>`
   * C. `<span type="date" value="2026-03-31">31 Maret 2026</span>`
   * D. `<date timestamp="1774942200">31 Maret 2026</date>`

---

#### Bagian 2: Intermediate (Pilihan Ganda)

6. **Kapan sebuah elemen `<aside>` TIDAK BOLEH digunakan menurut standar spesifikasi WHATWG?**
   * A. Ketika membungkus daftar tautan blogroll eksternal.
   * B. Ketika membungkus konten yang menjadi alur utama pemahaman teks (seperti paragraf inti sebuah esai teknis).
   * C. Ketika membungkus glosarium istilah di samping dokumen.
   * D. Ketika membungkus formulir pemesanan buletin (*newsletter subscription*).

7. **Mengapa menanam data terstruktur melalui format JSON-LD (`<script type="application/ld+json">`) lebih disukai dalam arsitektur modern dibanding Microdata inline?**
   * A. JSON-LD dapat langsung dieksekusi sebagai script JavaScript browser.
   * B. JSON-LD mengecualikan crawler membaca informasi hak cipta.
   * C. Memisahkan data domain dari struktur visual DOM, memitigasi isu hydration mismatch pada SSR, dan tidak memperbesar kompleksitas node pohon DOM.
   * D. Microdata sudah didepresiasi sepenuhnya oleh konsorsium W3C sejak tahun 2021.

8. **Perhatikan struktur berikut:**
   ```html
   <header>
     <h1>Platform Analisis</h1>
   </header>
   <main>
     <section>
       <h3>Metrik Realtime</h3>
       <p>...</p>
     </section>
   </main>
   ```
   **Apa cacat arsitektural utama pada dokumen di atas?**
   * A. Elemen `<section>` tidak boleh berada langsung di dalam `<main>`.
   * B. Terdapat *Heading Level Skipping*: hierarki melompat langsung dari `<h1>` ke `<h3>` tanpa adanya `<h2>` perantara, merusak navigasi AXTree.
   * C. Tag `<header>` tidak boleh memuat `<h1>`.
   * D. Dokumen kekurangan elemen `<footer>`.

9. **Bagaimana relasi yang tepat antara Accessibility Tree (`AXTree`) dan CSS property `display: none`?**
   * A. Elemen dengan `display: none` tetap muncul di AXTree agar screen reader bisa membacanya.
   * B. Node tersebut dihapus sepenuhnya dari render tree visual maupun AXTree.
   * C. Elemen diubah menjadi teks datar (*flat text*) pada AXTree.
   * D. Peramban secara otomatis menggantinya dengan atribut `aria-hidden="false"`.

10. **Apa dampak arsitektur *Deep DOM Nesting* (>32 level tag pembungkus) terhadap browser layout engine?**
    * A. Browser beralih secara otomatis ke quirks mode.
    * B. Meningkatkan konsumsi memori V8 wrapper, memperlambat proses kalkulasi rekursif *Style Invalidation*, dan memperparah latensi *Interaction to Next Paint* (INP).
    * C. Seluruh semantik tag HTML di dalam nesting dalam diabaikan oleh mesin peramban.
    * D. Parser browser membatalkan proses parsing dan memicu *Network Error*.

---

#### Bagian 3: Skenario Kasus Produksi (Analisis Arsitektur)

11. **Skenario Kasus 1: Micro-Frontend Semantics Clashing**
    Sebuah aplikasi web perbankan enterprise menggabungkan tiga aplikasi micro-frontend independen ke dalam satu halaman DOM bersama: Tim Akun (`AccountMFE`), Tim Kartu Kredit (`CardsMFE`), dan Tim Investasi (`InvestMFE`). Saat halaman digabungkan oleh host shell container, ditemukan ada tiga buah tag `<h1>` yang independen, dua tag `<main>`, dan tiga tag `<header role="banner">`. 
    *Pertanyaan:* Sebagai Enterprise Web Architect, tentukan desain arsitektur spesifikasi integrasi yang harus diterapkan oleh platform host untuk menyelesaikan benturan semantik ini tanpa memaksa penulisan ulang seluruh logika internal micro-frontend!

12. **Skenario Kasus 2: The E-Commerce Infinite Scroll Destruction**
    Sebuah toko retail online global mengubah halaman katalog produknya dari paginasi standar ke sistem *Infinite Scroll Virtualized List*. Setelah deployment, tim SEO melaporkan indeks artikel produk baru di dasar katalog merosot 80%, dan pengguna VoiceOver mengeluhkan fokus bacaan mereka terlempar ke awal halaman setiap kali batch 20 produk baru dimuat.
    *Pertanyaan:* Analisis akar masalah teknis dari perspektif DOM tokenization, AXTree re-calculation, dan rancang arsitektur dokumen solusinya!

13. **Skenario Kasus 3: SSR Hydration Mismatch pada Timestamp Semantik**
    Sebuah portal berita mendistribusikan artikel ke seluruh dunia. Di server node (berlokasi di zona UTC), SSR merender:
    `<time datetime="2026-03-31T00:00:00Z">31/03/2026 00:00</time>`.
    Saat payload tiba di browser pengguna di Jakarta (UTC+7), komponen client framework (React) melakukan re-render lokal berbasis objek `new Date()` lokal menjadi:
    `<time datetime="2026-03-31T07:00:00+07:00">31/03/2026 07:00</time>`.
    Hal ini menyebabkan insiden *Hydration Error*, memicu re-render layout keseluruhan (*CLS* meningkat tajam) dan merusak parsing Schema.org.
    *Pertanyaan:* Bagaimana rancangan arsitektur penanganan data semantik berbasis waktu yang deterministik untuk menyelesaikan kegagalan hidrasi ini?

---

### Kunci Jawaban & Pembahasan Evaluasi

#### Bagian 1: Basic
1. **C** - Vendor browser menolak Document Outline Algorithm karena komputasi rekursif yang mahal dan risiko inkonsistensi rendering; developer wajib mengatur level heading secara eksplisit ($H_1-H_6$).
2. **B** - Tag `<article>` dirancang spesifik untuk konten yang self-contained dan dapat didistribusikan/disindikasi ulang secara mandiri.
3. **B** - Berdasarkan WCAG 1.3.1, apabila terdapat lebih dari satu landmark berjenis sama, setiap elemen harus memiliki pembeda melalui label (`aria-label` atau `aria-labelledby`).
4. **C** - Atribut `scope="row"` mengasosiasikan sel header secara horizontal ke seluruh sel data pada baris yang sama di Accessibility Tree.
5. **B** - Elemen `<time>` wajib menggunakan atribut `datetime` dengan format string waktu ISO 8601 yang valid (termasuk penanda zona waktu).

#### Bagian 2: Intermediate
6. **B** - Konten utama dokumen tidak boleh dibungkus di dalam `<aside>`. `<aside>` ditujukan untuk informasi pelengkap atau tangensial.
7. **C** - JSON-LD memisahkan payload data domain dari rendering pohon visual DOM, mencegah isu rekonsiliasi state hydration, dan tidak membebani layout engine.
8. **B** - Terjadi heading skipping dari `<h1>` langsung ke `<h3>`. Hierarki heading harus bersifat linear dan tidak boleh melompati level perantara demi menjaga orientasi screen reader.
9. **B** - Properti CSS `display: none` secara spesifikasi menghapus node terkait dari visual layout dan pohon aksesibilitas (`AXTree`).
10. **B** - Pohon DOM yang terlalu dalam menuntut kalkulasi rekursif yang masif pada fase Style Invalidation dan Layout, menghabiskan memori heap browser dan menurunkan metrik INP secara signifikan.

#### Bagian 3: Skenario Kasus Produksi
11. **Solusi Arsitektur Skenario 1:**
    * Kontainer Host bertindak sebagai pemilik tunggal *Root Landmarks*: Hanya host yang diizinkan merender `<header role="banner">`, `<main id="app-root">`, dan `<footer role="contentinfo">`.
    * Host mengekspos API/Properties kepada micro-frontend: MFE tidak boleh merender tag `<main>` atau top-level `<header>`. MFE wajib dirender sebagai `<section aria-labelledby="mfe-heading-id">` di dalam host container.
    * Heading Level Contract: Host mengunci `<h1>` untuk judul konteks aplikasi (misal: "Portal Perbankan Terpadu"). Setiap MFE diisolasi untuk memulai judul areanya dari level `<h2>`. Sistem build MFE diintegrasikan dengan compiler plugin yang otomatis me-rewrite `<h1>` internal MFE menjadi `<h2>`.
12. **Solusi Arsitektur Skenario 2:**
    * **Akar Masalah SEO**: Virtualized list menghapus (*unmount*) DOM node yang berada di luar viewport visual untuk menghemat memori. Crawler Googlebot yang tidak mengeksekusi scroll interaktif kompleks tidak akan pernah memicu permintaan network fetch data produk berikutnya.
    * **Akar Masalah Aksesibilitas**: Unmounting dan re-mounting node secara agresif menghancurkan referensi fokus pembaca layar di AXTree, me-reset fokus pembaca ke root body.
    * **Solusi Arsitektur**: Terapkan arsitektur *Hybrid Semantic Progressive Pagination*:
      * Sediakan markup fallback tautan semantik navigasi standar (`<nav aria-label="Katalog Halaman"><a href="?page=2">Halaman Berikutnya</a></nav>`) di dalam markup SSR awal yang dibaca crawler.
      * Untuk screen reader, kelola virtual rendering dengan menambahkan kontainer status non-visual (`aria-live="polite" aria-atomic="true"`) yang membacakan: *"Menampilkan produk 21 hingga 40 dari 200"* tanpa me-reset fokus kursor aktif pengguna.
13. **Solusi Arsitektur Skenario 3:**
    * **Akar Masalah**: Ketidaksinkronan referensi waktu antara server execution context (UTC) dan client browser context (Local Timezone) yang dieksekusi secara naif di dalam siklus rendering awal komponen.
    * **Solusi Arsitektur**:
      * Kunci representasi atribut `datetime` dalam UTC absolut secara statis sejak di server: `<time datetime="2026-03-31T00:00:00Z">...</time>`.
      * Gunakan arsitektur *Two-Pass Rendering* atau *Client-Only Rehydration Directive* untuk teks visual yang dilihat manusia. Pada render pertama (SSR), cetak format waktu UTC universal.
      * Setelah event mount client selesai (`useEffect` / `onMounted`), konversi visual representation ke timezone lokal pengguna, atau gunakan Web Component standar seperti `<relative-time>` yang menangani lokalisasi visual di Shadow DOM tanpa merusak atribut semantik host DOM tree.
      * Ekstrak representasi waktu untuk Structured Data ke dalam JSON-LD statis terpisah di `<head>`, sehingga agen SEO membaca data absolut yang kebal terhadap perubahan client hydration.

---

### 16. Summary

1. **Accessibility Tree (`AXTree`) adalah Konsumen Utama Semantik Dokumen:** Browser memetakan elemen HTML native secara paralel ke dalam DOM dan AXTree. Mengabaikan semantik HTML demi *div-soup* merusak representasi aksesibilitas pada level antarmuka kernel sistem operasi.
2. **Document Outline Algorithm Tidak Ada di Dunia Nyata:** Vendor browser tidak pernah mengimplementasikan auto-heading level resolution. Arsitek software wajib menegakkan hierarki heading manual yang ketat ($H_1 \rightarrow H_2 \rightarrow H_3$) tanpa pernah melompati level (*no heading skipping*).
3. **Pemisahan Tegas antara Struktur dan Metadata:** Gunakan native landmarks (`<header>`, `<nav>`, `<main>`, `<article>`, `<aside>`, `<footer>`) untuk mengorkestrasi tata letak visual/aksesibilitas, dan isolasi data mesin ke format **JSON-LD Graph** guna memaksimalkan efisiensi anggaran perayapan (crawl budget) serta menghindari konflik hidrasi pada aplikasi modern berbasis SSR.