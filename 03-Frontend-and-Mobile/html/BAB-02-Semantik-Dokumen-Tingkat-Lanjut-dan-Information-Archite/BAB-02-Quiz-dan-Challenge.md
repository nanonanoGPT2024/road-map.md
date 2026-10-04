# BAB 02: Quiz, Challenge, & Knowledge Check
**Semantik Dokumen Tingkat Lanjut & Information Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Taksonomi dan Isolasi Semantik: `<article>` vs `<section>`
Jelaskan perbedaan fundamental dalam semantik spesifikasi W3C/WHATWG antara elemen `<article>` dan `<section>`. Dalam skenario arsitektur informasi seperti apa sebuah `<article>` dapat disarangkan (*nested*) di dalam `<article>` lain, dan bagaimana *accessibility tree* (AOM) membedakan semantik induk versus anak pada struktur tersebut?

### Soal 1.2: Status De Facto HTML5 Document Outline Algorithm
Spesifikasi HTML5 awalnya memperkenalkan algoritma otomatisasi outline dokumen (di mana setiap *sectioning content* dapat memulai level heading dari `<h1>` dan dihitung secara hierarkis oleh *user agent*). Mengapa algoritma ini secara *de facto* dinyatakan gagal/ditinggalkan oleh para vendor browser (Blink, Gecko, WebKit) dan *assistive technologies*? Jelaskan dampaknya terhadap penentuan hierarki heading `<h1>`-`<h6>` pada sistem produksi saat ini.

### Soal 1.3: Implicit ARIA Semantics dan Batasan `<main>`
Setiap elemen semantik HTML5 memiliki pemetaan otomatis (*implicit landmark role*) pada Accessibility API sistem operasi. Terkait elemen `<main>`:
1. Apa *implicit role* dari elemen ini?
2. Mengapa spesifikasi melarang keberadaan lebih dari satu elemen `<main>` dalam dokumen aktif tanpa atribut `hidden`?
3. Apa konsekuensi struktural dan perilaku pembaca layar (*screen reader*) jika terjadi pelanggaran aturan ini?

### Soal 1.4: Page-Level vs Context-Level `<aside>`
Elemen `<aside>` merepresentasikan konten yang secara tangensial terkait dengan konten di sekitarnya. Analisis perbedaan semantik, struktural, dan penempatan arsitektural antara:
- Elemen `<aside>` yang ditempatkan sebagai anak langsung dari elemen `<body>` (*page-level landmark*).
- Elemen `<aside>` yang disarangkan di dalam elemen `<article>` (*context-level/article-level content*).
Bagaimana *assistive technology* membedakan jangkauan asosiasi (*scope of association*) dari kedua penempatan tersebut?

### Soal 1.5: Mesin Temporal: Elemen `<time>` dan Resolusi Parsing ISO 8601
Jelaskan tujuan arsitektur informasi dari elemen `<time>` beserta atribut `datetime`. Mengapa representasi visual seperti `"Kemarin"` atau `"Dua jam yang lalu"` tidak memadai untuk agen pengindeks (*web crawler*) dan teknologi asistif? Berikan contoh variasi nilai `datetime` yang valid untuk:
1. Titik waktu absolut dengan offset timezone.
2. Rentang durasi (*duration*).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Semantic Destruction dan AOM Tree Flattening
Perhatikan cuplikan markup berikut yang ditujukan untuk membuat layout daftar kartu modular:

```html
<ul class="card-grid">
  <div class="grid-row">
    <li class="card-item">Item 1</li>
    <li class="card-item">Item 2</li>
  </div>
</ul>
```

Analisis bagaimana parser HTML5 memproses DOM di atas dan apa dampak fatalnya terhadap pembentukan *accessibility tree* pada browser engine (Blink/Gecko). Jelaskan mekanisme internal mengapa penempatan `<div>` sebagai anak langsung dari `<ul>` merusak *parent-child relationship* (`list` -> `listitem`) pada Accessibility Object Model (AOM), serta bagaimana solusi arsitektural yang valid tanpa mengorbankan fleksibilitas styling CSS Grid/Flexbox.

### Soal 2.2: Redundant Semantics dan Prinsip Pertama ARIA
Banyak pengembang menulis markup defensif seperti `<nav role="navigation">` atau `<header role="banner">`. 
1. Bedah "First Rule of ARIA use" dari W3C dan evaluasi apakah praktik ini merupakan *anti-pattern* atau teknik *fallback* yang valid untuk peramban modern.
2. Jelaskan skenario langka di mana penambahan explicit role pada native HTML5 element justru merusak komputasi state internal browser (misal: `<button role="button">` vs penanganan interaksi pointer dan keyboard bawaan).

### Soal 2.3: Heading Level Skipping dan Rotor Traversal Degradation
Jika sebuah halaman web melompat dari `<h1>` langsung ke `<h4>` demi mencapai skala visual tertentu tanpa penyesuaian CSS class, jelaskan proses internal navigasi pengguna tuna netra yang menggunakan fitur *Heading Rotor/Elements List* pada NVDA/JAWS/VoiceOver. Mengapa anomali struktural ini diklasifikasikan sebagai kegagalan WCAG 2.2 (Success Criterion 1.3.1 Info and Relationships), dan bagaimana cara memisahkan hierarki semantik (*semantic depth*) dari hierarki tipografi (*visual scale*)?

### Soal 2.4: Focus Management dan Landmark Announcement pada Dynamic Routing SPA
Pada aplikasi Single Page Application (SPA), pergantian rute berbasis JavaScript sering kali hanya memperbarui subtree di dalam `<main id="content">` tanpa memicu *full page reload*.
1. Mengapa peramban tidak otomatis mengumumkan perpindahan konteks halaman kepada pengguna alat bantu?
2. Bagaimana cara merekayasa arsitektur semantik dokumen (melibatkan manipulasi atribut `tabindex="-1"`, elemen `<title>`, dan *accessible routing announcements*) agar Information Architecture tetap terjaga saat terjadi navigasi asinkron?

### Soal 2.5: Microdata Maintenance Overhead vs JSON-LD
Dalam merancang Information Architecture untuk optimasi mesin pencari (SEO) dan interoperabilitas data:
1. Bandingkan pendekatan penyisipan semantik mesin menggunakan *Microdata* (atribut `itemscope`, `itemtype`, `itemprop` yang tersebar di elemen HTML) dengan *JSON-LD* (`<script type="application/ld+json">`).
2. Dari sudut pandang rekayasa perangkat lunak skala enterprise (misal: pemeliharaan design system, reusabilitas komponen UI, dan pemisahan *presentation layer* vs *data layer*), mengapa Microdata sering memicu kerapuhan (*brittleness*) saat terjadi refactoring layout?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Krisis Indexing & WCAG Audit pada Portal Berita Global
Sebuah portal berita global dengan 40 juta *monthly active users* baru saja melakukan migrasi dari CMS monolitik ke arsitektur decoupled berbasis Next.js/React. Dua minggu pasca migrasi, laporan pasca-rilis menunjukkan:
1. Terjadi penurunan drastis pada peringkat SEO organik untuk fitur Google News & Rich Snippets.
2. Hasil audit independen menyatakan kegagalan WCAG 2.1 AA massal pada struktur navigasi dan pembacaan artikel.

Setelah dilakukan inspeksi DOM, ditemukan bahwa seluruh artikel dibungkus dengan markup berikut:

```html
<div class="article-wrapper">
  <div class="article-header">
    <div class="title-text">Judul Berita Utama</div>
    <div class="author-info">Ditulis oleh: Redaksi - 2024-03-30</div>
  </div>
  <div class="article-body">
    <div class="paragraph-node">Konten berita paragraf pertama...</div>
    <div class="related-sidebar">
      <div class="title-text">Berita Terkait</div>
      <!-- List berita terkait -->
    </div>
  </div>
</div>
```

*Tugas Diagnostik:*
1. Identifikasi minimal 5 kegagalan arsitektur semantik fatal pada struktur markup di atas.
2. Rekonstruksi markup di atas menjadi dokumen HTML5 berstandar enterprise yang memaksimalkan semantic tagging (`<article>`, `<header>`, `<h1>`, `<address>`, `<time>`, `<aside>`, `<p>`, dll).
3. Jelaskan bagaimana perbaikan tersebut secara spesifik memperbaiki parsing *bot crawler* (Schema.org/Googlebot) dan parsing *accessibility tree*.

---

### Skenario B: Accessibility Crash pada Infinite-Scroll Data Monitoring Dashboard
Sebuah aplikasi Enterprise APM (Application Performance Monitoring) menampilkan log transaksi real-time dengan mekanisme *infinite scroll*. Tim frontend membungkus setiap batch log baru ke dalam elemen `<section>` tanpa heading, dan di dalamnya terdapat ribuan baris log yang menggunakan tag `<article>` dengan berbagai child interactive elements.

Pengguna dengan *assistive technology* (VoiceOver di macOS) melaporkan bahwa peramban mengalami *freeze/unresponsive* total setelah 10 menit membuka halaman, sementara pengguna non-screen-reader hanya mengalami penurunan performa minor.

*Tugas Diagnostik:*
1. Mengapa akumulasi ribuan landmark semantik (`<section>`, `<article>`) secara tidak terbatas membebani *Accessibility Tree* dan menyebabkan *memory leak* / komputasi berlebihan pada engine pembaca layar, meskipun native DOM engine masih mampu merendernya?
2. Bagaimana mendesain ulang Information Architecture (IA) komponen live-log ini menggunakan semantik tabel/daftar yang tepat (`<table>`, `virtualized list`, `aria-live="polite"`, dan `role="log"`) untuk menyeimbangkan kebutuhan visual vs kapasitas pembacaan *assistive technology*?

---

### Skenario C: Multi-brand Design System: Semantic Rigidity vs Polymorphic Components
Anda menjabat sebagai Principal Frontend Architect yang memimpin standarisasi Design System untuk 8 anak perusahaan enterprise. Tim pengembang menginginkan komponen kartu (*Card Component*) yang "polimorfik" (dapat diubah tag HTML-nya melalui prop, misal: `<Card as="div">`, `<Card as="article">`, atau `<Card as="section">`). 

Namun, implementasi lapangan menunjukkan para pengembang junior sering membungkus seluruh layout kompleks dengan `<Card as="article">`, sehingga dalam satu halaman e-commerce terdapat 80+ elemen `<article>` yang merepresentasikan elemen non-standalone (mulai dari badge promo, banner navigasi, hingga form newsletter).

*Tugas Diagnostik:*
1. Evaluasi risiko arsitektur dari *over-semantics* (penggunaan elemen semantik tinggi secara serampangan) terhadap integritas Information Architecture portal e-commerce tersebut.
2. Tetapkan *Technical Standard Guideline* dan aturan *compile-time/linting* (misal: AST checking, Custom ESLint Rules, TypeScript definitions) untuk membatasi atau membimbing developer dalam memilih elemen semantik yang benar berdasarkan tipe data yang di-passing ke dalam Design System Component.

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Arsitektur Informasi "Enterprise Developer Documentation Hub"

#### Konteks & Problem Statement
Sebuah platform cloud enterprise membutuhkan layout template untuk sistem dokumentasi teknis publik mereka. Template ini harus melayani tiga jenis konsumen:
1. **Developer manusia** yang menuntut navigasi cepat via keyboard dan visual yang bersih.
2. **Pengguna Assistive Technology** (tuna netra/low-vision) yang bersandar 100% pada struktur dokumen yang rigid dan penandaan landmark yang sempurna tanpa *dead ends*.
3. **Automated Scraping & Search Engine Crawlers** yang mengekstrak metadata API, hierarki artikel, dan status verifikasi konten secara presisi.

#### Requirements
1. **Root & Shell Architecture**:
   - Memiliki *Skip-link Navigation* murni berbasis semantic anchor yang melewati header global dan navigasi samping, langsung mendarat pada target konten utama.
   - Menggunakan elemen `<header>`, `<nav>`, `<main>`, `<aside>`, dan `<footer>` yang ditempatkan secara hierarkis tanpa redundansi ARIA roles.
2. **Navigasi Multi-layer**:
   - Primary Navigation (Navigasi global antar produk cloud).
   - Secondary Documentation Tree Navigation (Hierarki folder dan bab dokumen teknis).
   - In-page Table of Contents (Navigasi internal dokumen ke level sub-heading).
   - Setiap navigasi harus diisolasi menggunakan `<nav>` dengan pembeda kontekstual via atribut `aria-labelledby` atau `aria-label` yang terhubung ke heading tersembunyi/terlihat.
3. **Dokumen Teknis Utama (`<main>`)**:
   - Menggunakan satu `<article>` yang memuat:
     - Header dokumen dengan metadata komprehensif (`<h1>`, versi rilis dokumen menggunakan `<data>`, tanggal pembaruan menggunakan `<time>`, penulis/maintainer menggunakan `<address>`).
     - Minimal dua `<section>` dengan `<h2>` yang terhubung.
     - Blok kode/output teknis menggunakan `<figure>`, `<figcaption>`, `<pre>`, dan `<code>`.
     - Callout/Admonition (warning/tip) yang secara semantik tidak memutus alur baca artikel utama (evaluasi kapan menggunakan `role="note"` vs `<aside>`).
4. **Metadata & Machine-Readability**:
   - Menghubungkan titik waktu ISO 8601 presisi tinggi pada atribut `datetime`.
   - Menandai ketersediaan konten alternatif atau relasi relaksasi dokumen.

#### Constraints
- **Murni Semantic HTML5**: Dilarang keras menggunakan `<div>` dan `<span>` kecuali untuk elemen pembungkus estetika murni yang telah dibuktikan tidak memiliki ekuivalen semantik HTML5.
- **Strictly WCAG 2.2 Level AA**: Lolos pengujian struktur Heading Hierarchy (tidak ada skipping levels) dan validitas formasi landmark.
- **W3C Nu HTML Checker Valid**: Validasi markup 100% tanpa *warnings* struktural maupun *errors*.
- **Tanpa CSS/JS**: Tantangan ini berfokus murni pada struktur dokumen (*skeleton & information architecture*). Tidak ada style CSS atau script interaktivitas JS yang diikutsertakan.

#### Expected Output
File tunggal HTML5 (`documentation-template.html`) yang lengkap, terstruktur rapi, tervalidasi, disertai komentar teknis pendek (*architectural annotations*) di dalam markup yang menjelaskan keputusan teknis di balik pemilihan elemen tertentu.

---

## 5. Knowledge Check & Checklist

Tinjau pemahaman Anda sebelum melangkah ke bab berikutnya. Tandai poin-poin berikut untuk memverifikasi kesiapan arsitektur Anda:

### Saya harus memahami:
- [ ] Logika perbedaan antara struktur dokumen visual (*DOM Tree*) dan interpretasi alat bantu (*Accessibility Tree / AOM*).
- [ ] Batasan spesifikasi teknis mengenai kapan konten layak berdiri sendiri (*self-contained*) sebagai `<article>`.
- [ ] Dampak pengabaian *Document Outline Algorithm* terhadap keharusan menyusun `<h1>`-`<h6>` secara inkremental tanpa melompat.
- [ ] Implikasi semantik dan performa dari penggunaan ARIA Landmark Roles versus Native HTML5 Landmarks.
- [ ] Kategori dan peran elemen pendukung metadata: `<time>`, `<address>`, `<figure>`, `<figcaption>`, `<data>`, dan `<mark>`.
- [ ] Mengapa *Microdata* inline dapat menimbulkan beban pemeliharaan teknis dibanding arsitektur data terpisah seperti *JSON-LD*.

### Saya tidak perlu menghafal:
- [ ] Seluruh format ekspresi durasi ISO 8601 (cukup pahami format umum `PnYnMnDTnHnMnS` dan rujuk spesifikasi saat butuh kombinasi eksotis).
- [ ] Seluruh atribut usang (*obsolete attributes*) peninggalan HTML 4.01/XHTML yang telah di-deprecate (misal: `summary` pada tabel).
- [ ] Matriks pemetaan ARIA internal untuk setiap browser engine baris-per-baris (cukup pahami prinsip implicit semantic mapping menurut HTML AAM - Accessible Name and Description Computation).

### Saya harus bisa melakukan:
- [ ] Membedah dokumen web kompleks dan memetakannya ke dalam Information Architecture berbasis Landmark (`<main>`, `<nav>`, `<aside>`, `<header>`, `<footer>`).
- [ ] Melakukan audit dokumen menggunakan Accessibility Inspector di DevTools untuk memverifikasi apakah semantic nodes terpapar dengan role yang benar ke AOM.
- [ ] Mengidentifikasi dan memperbaiki pelanggaran hierarki semantik (*skipped headings*, *orphaned list items*, *misused landmarks*).
- [ ] Mengisolasi navigasi ganda pada satu halaman dengan label diferensiasi yang tepat agar tidak membingungkan pengguna *screen reader*.
- [ ] Menulis markup dokumen teknis dan artikel jurnal yang secara instan dapat diparsing secara optimal oleh mesin pencari (*rich metadata ready*) dan assistive technologies tanpa ketergantungan JavaScript.