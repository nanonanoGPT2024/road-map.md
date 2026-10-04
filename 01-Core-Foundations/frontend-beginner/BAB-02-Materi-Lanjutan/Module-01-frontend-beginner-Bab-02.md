## SEKSI 01 — IDENTITAS MODUL

* **Modul ID:** `FED-CORE-01-02`
* **Slug:** `semantik-html5-dan-aksesibilitas`
* **Kategori:** `01-Core-Foundations`
* **Track:** `frontend-beginner`
* **Tingkat Kesulitan:** Beginner to Early-Intermediate
* **Prasyarat:** `FED-CORE-01-01` (Sintaks Dasar HTML, Anatomi Dokumen, dan Lingkungan Kerja Web)
* **Estimasi Waktu Belajar:** 4–5 Jam (Teori, Analisis Accessibility Tree, dan Latihan Hands-on)
* **Teknologi & Alat Bantu:** HTML5, Modern Web Browser (Chromium/Firefox DevTools), Screen Reader (NVDA / VoiceOver), W3C Nu HTML Checker, Axe DevTools Extension

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Membedakan** elemen struktural semantik (`<main>`, `<nav>`, `<article>`, `<section>`, `<aside>`, `<header>`, `<footer>`) dari elemen generik non-semantik (`<div>`, `<span>`) berdasarkan fungsi data dan arsitektur dokumen.
2. **Mengonstruksi** hierarki heading (`<h1>` hingga `<h6>`) yang konsisten tanpa merusak struktur outline dokumen untuk navigasi teknologi asistif.
3. **Menjelaskan Mekanisme** transformasi HTML DOM menjadi *Accessibility Tree* (AOM) oleh *browser engine*.
4. **Menerapkan Prinsip Aksesibilitas Web (WCAG 2.2 Level AA)** pada elemen formulir, teks alternatif gambar (`alt`), dan tautan navigasi.
5. **Mengimplementasikan Atribut ARIA (Accessible Rich Internet Applications)** secara selektif sesuai aturan *First Rule of ARIA* tanpa redundansi semantik native.
6. **Mengevaluasi dan Mengaudit** halaman web terhadap isu aksesibilitas mendasar menggunakan DevTools dan screen reader bawaan sistem operasi.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
                                [Dokumen HTML]
                                       |
                   +-------------------+-------------------+
                   |                                       |
          [Semantik Struktural]                   [Aksesibilitas (a11y)]
                   |                                       |
     +-------------+-------------+           +-------------+-------------+
     |                           |           |                           |
[Landmark Roles]          [Konten Teks]   [WCAG Principles]    [Accessibility Tree]
 - <header>                - Hierarki Hn   - Perceivable        - Role, Name, Value
 - <nav>                   - <p>, <blockquote> - Operable       - State & Properties
 - <main>                  - <ul>, <ol>, <dl> - Understandable           |
 - <article>                               - Robust                      |
 - <aside>                                       |             [Screen Readers]
 - <footer>                               [ARIA Specs]         (NVDA, VoiceOver)
                                           - Roles
                                           - States (aria-expanded)
                                           - Properties (aria-label)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Ketika peramban membaca berkas HTML, tugasnya bukan sekadar merender piksel ke layar. Peramban juga membangun representasi paralel yang disebut **Accessibility Tree**. Representasi ini menjadi satu-satunya antarmuka yang dibaca oleh teknologi asistif seperti pembaca layar (*screen reader*), perangkat braille, dan sistem kontrol suara.

```
       +--------------+
       | Dokumen HTML |
       +-------+------+
               |
        Browser Engine
         Parses HTML
               |
       +-------+-------+
       |               |
       v               v
   +-------+   +---------------+
   |  DOM  |   | Accessibility |
   |  Tree |   |     Tree      |
   +---+---+   +-------+-------+
       |               |
       v               v
    Visual         Assistive
    Render        Technology
   (Monitor)    (Screen Reader)
```

Penggunaan elemen generik seperti `<div>` dan `<span>` untuk seluruh antarmuka ("Div-Soup") menghancurkan struktur ini:
* **Bagi Pengguna Disabilitas:** Pembaca layar tidak dapat membedakan antara menu navigasi, konten utama, atau catatan kaki. Dokumen diperlakukan sebagai satu blok teks panjang tanpa penanda arah (*landmarks*).
* **Bagi Mesin Pencari (SEO):** Algoritma perayap (*crawler*) mengandalkan semantik untuk menentukan konten mana yang bernilai tinggi (misalnya `<article>` vs `<aside>`).
* **Bagi Maintainability:** Kode yang semantik bersifat *self-documenting*. Pengembang lain dapat memahami maksud struktur tanpa harus memeriksa kelas CSS yang kompleks.
* **Dari Sisi Regulasi:** Standar aksesibilitas (seperti mandat ADA Title III, European Accessibility Act, dan UU Disabilitas No. 8 Tahun 2016 di Indonesia) menuntut pemenuhan WCAG 2.1/2.2 Level AA. Kegagalan mematuhinya membawa konsekuensi hukum dan etika.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Semantik HTML5
Semantik adalah studi tentang makna linguistik. Dalam HTML, **elemen semantik** adalah tag yang secara eksplisit mendeskripsikan arti dan perannya kepada peramban dan pengembang, terlepas dari bagaimana elemen tersebut ditampilkan secara visual.

* **Elemen Non-Semantik:** `<div>`, `<span>` — Tidak memberi informasi tentang kontennya.
* **Elemen Semantik Struktural:** `<header>`, `<nav>`, `<main>`, `<article>`, `<section>`, `<aside>`, `<footer>`.
* **Elemen Semantik Teks/Data:** `<h1>`-`<h6>`, `<time>`, `<figure>`, `<figcaption>`, `<code>`, `<mark>`.

### 2. Aksesibilitas Web (a11y)
Aksesibilitas web berarti merancang situs agar dapat dipahami, dinavigasi, dan diinteraksikan oleh semua orang, termasuk mereka yang memiliki disabilitas visual, auditori, motorik, atau kognitif. Fondasi a11y diatur oleh **WCAG (Web Content Accessibility Guidelines)** berbasis empat prinsip utama (**POUR**):
1. **Perceivable (Dapat Dipersepsi):** Informasi dan komponen antarmuka harus dapat disajikan kepada pengguna melalui indra mereka (misal: atribut `alt` untuk tunanetra).
2. **Operable (Dapat Dioperasikan):** Antarmuka tidak boleh memerlukan interaksi yang tidak dapat dilakukan pengguna (misal: navigasi penuh via keyboard).
3. **Understandable (Dapat Dipahami):** Konten dan operasi antarmuka harus jelas dan konsisten.
4. **Robust (Kukuh):** Konten harus dapat diinterpretasikan secara andal oleh berbagai agen pengguna, termasuk teknologi asistif.

### 3. ARIA (Accessible Rich Internet Applications)
WAI-ARIA adalah spesifikasi teknis dari W3C yang menambahkan atribut khusus (`role`, `aria-*`) ke elemen HTML untuk mengisi celah ketika semantik native HTML tidak mencukupi (misalnya pada komponen dinamis interaktif seperti tab panel, modal dialog, atau menu dropdown).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Mekanisme Internal Browser: Dari Markup ke Accessibility Tree

```
[HTML Source] 
    └── HTML Parser ──> [DOM Tree]
                             │
                             ├── Layout/Style Engine ──> [Render Tree] ──> Frame Buffer (Layar)
                             │
                             └── Computed A11y Node Mapping 
                                      │
                                      └──> [Accessibility Tree (AOM)]
                                                │
                                                └── OS Accessibility API (MSAA, IAccessible2, AXUIElement, ATK)
                                                         │
                                                         └── Screen Reader (NVDA, JAWS, VoiceOver)
```

1. **Tokenisasi & Parsing:** Browser mengurai string HTML menjadi simpul-simpul DOM (*Document Object Model*).
2. **Penciptaan Node Aksesibilitas:** Untuk setiap simpul DOM yang relevan, browser menghitung peran (*role*), status (*state*), nama (*accessible name*), dan deskripsi (*accessible description*).
3. **Sinkronisasi OS API:** Browser mengekspos Accessibility Tree ke API aksesibilitas bawaan sistem operasi (misalnya UI Automation di Windows atau NSAccessibility di macOS).
4. **Konsumsi Asistif:** *Screen reader* mengkueri OS API tersebut, mengumumkan informasi struktural seperti *"navigation landmark"*, *"heading level 1"*, atau *"button"*, serta merespons navigasi keyboard pengguna (seperti tombol panah, Tab, atau tombol pintas landmark `D`).

### Komputasi Accessible Name (AccName Standard)
Ketika screen reader fokus pada sebuah elemen, ia menghitung namanya berdasarkan hierarki prioritas:
1. Atribut `aria-labelledby`
2. Atribut `aria-label`
3. Semantik konten native (misal teks di dalam `<button>Kirim</button>` atau atribut `alt` pada `<img alt="Foto profil">`)
4. Atribut `title` (fallback kualitas rendah)

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah peta perbandingan representasi dokumen antara DOM dan Accessibility Tree:

```text
DOKUMEN HTML SUMBER:
<header>
  <h1>Portal Edukasi</h1>
  <nav>
    <a href="/kursus">Daftar Kursus</a>
  </nav>
</header>
<main>
  <article>
    <h2>Pengantar HTML5</h2>
    <p>HTML5 menyediakan semantik modern.</p>
    <button>Baca Selengkapnya</button>
  </article>
</main>

=========================== REPRESENTASI DIVERGENSI ===========================

        DOM TREE                                     ACCESSIBILITY TREE
  (Struktur Dokumen Visual)                     (Struktur Semantik Teknologi Asistif)

       [Document]                                         [Document]
           │                                                  │
        [<html>]                                       [banner] (header)
           │                                            ├── [heading] "Portal Edukasi" (level 1)
        [<body>]                                        └── [navigation]
           │                                                 └── [link] "Daftar Kursus"
     +-----+-----+                                            
     │           │                                     [main]
  [<header>]   [<main>]                                 └── [article]
     │           │                                           ├── [heading] "Pengantar HTML5" (level 2)
  +--+--+        │                                           ├── [text] "HTML5 menyediakan semantik modern."
  │     │    [<article>]                                     └── [button] "Baca Selengkapnya"
[<h1>] [<nav>]   │
  │     │     +--+--+
[text] [<a>]  │  │  │
             [h2][p][button]
```

Jika markup di atas ditulis menggunakan `<div>` dan `<span>` tanpa ARIA, Accessibility Tree hanya akan berisi serangkaian simpul teks generik tanpa simpul landmark (`banner`, `navigation`, `main`, `article`), menghilangkan kemampuan navigasi struktural secara total.

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Perbandingan langsung antara implementasi non-semantik (buruk) dan semantik aksesibel (benar).

### ❌ Buruk: Div-Soup & Fake Button
```html
<!-- Anti-pattern: Tidak ada semantic role, tidak bisa diakses via keyboard -->
<div class="header">
  <div class="title">Toko Sepatu Digital</div>
  <div class="menu">
    <span class="menu-item" onclick="navigate('/home')">Home</span>
    <span class="menu-item" onclick="navigate('/catalog')">Katalog</span>
  </div>
</div>

<div class="content">
  <div class="card">
    <div class="card-title">Sneakers Pro</div>
    <div class="btn" onclick="addToCart(102)">Beli Sekarang</div>
  </div>
</div>
```
*Masalah:*
* Keyboard tidak bisa melakukan `Tab` ke `.menu-item` atau `.btn`.
* Screen reader hanya membaca teks mentah tanpa konteks tombol atau link.
* Menekan tombol `Enter` atau `Space` tidak akan memicu interaksi.

### ✅ Benar: Semantic & Accessible
```html
<!-- Solusi: Semantik asli browser, keyboard-accessible by default -->
<header>
  <h1>Toko Sepatu Digital</h1>
  <nav aria-label="Navigasi Utama">
    <ul>
      <li><a href="/home">Home</a></li>
      <li><a href="/catalog">Katalog</a></li>
    </ul>
  </nav>
</header>

<main>
  <article>
    <h2>Sneakers Pro</h2>
    <button type="button" onclick="addToCart(102)">Beli Sekarang</button>
  </article>
</main>
```
*Keunggulan:*
* Tag `<nav aria-label="Navigasi Utama">` secara otomatis memiliki role `navigation`.
* Tag `<button>` secara inheren mendukung fokus keyboard, aktivasi via tombol `Space` dan `Enter`, serta melaporkan role `button` ke screen reader.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah komponen halaman artikel berita lengkap yang mematuhi standar arsitektur semantik HTML5, navigasi keyboard terstruktur, penanganan gambar, dan formulir aksesibel.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Analisis Web Semantik - TechJournal</title>
  <style>
    /* Styling esensial untuk visual focus indicator */
    :focus-visible {
      outline: 3px solid #005fcc;
      outline-offset: 2px;
    }
    .visually-hidden {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
    .skip-link {
      position: absolute;
      top: -40px;
      left: 0;
      background: #000;
      color: #fff;
      padding: 8px;
      z-index: 100;
      transition: top 0.2s;
    }
    .skip-link:focus {
      top: 0;
    }
  </style>
</head>
<body>

  <!-- Mekanisme Skip to Main Content untuk aksesibilitas keyboard -->
  <a href="#main-content" class="skip-link">Loncat ke konten utama</a>

  <header>
    <p>TechJournal Online</p>
    <nav aria-label="Navigasi Utama">
      <ul>
        <li><a href="/" aria-current="page">Beranda</a></li>
        <li><a href="/arsip">Arsip Berita</a></li>
        <li><a href="/kontak">Kontak Redaksi</a></li>
      </ul>
    </nav>
  </header>

  <main id="main-content">
    <article>
      <header>
        <h1>Mengapa HTML Semantik Adalah Tulang Punggung Web Modern</h1>
        <p>Ditulis oleh <span class="author">Ahmad Fauzi</span> pada <time datetime="2024-10-24">24 Oktober 2024</time></p>
      </header>

      <section>
        <h2>Pengenalan Semantik</h2>
        <p>
          HTML semantik menyediakan makna intrinsik pada struktur web. Dokumen web bukan
          hanya susunan visual di monitor, melainkan dokumen berbasis data hierarkis.
        </p>

        <!-- Figure dengan Caption Deskriptif -->
        <figure>
          <img 
            src="flow-parser.png" 
            alt="Bagan alur parsing berkas HTML menjadi DOM Tree dan Accessibility Tree secara simultan"
            width="600" 
            height="300"
          >
          <figcaption>Gbr 1: Alur kerja browser engine dalam memproses dokumen HTML.</figcaption>
        </figure>
      </section>

      <section>
        <h2>Umpan Balik Pembaca</h2>
        <!-- Form yang fully accessible dengan label eksplisit -->
        <form action="/submit-comment" method="POST">
          <div>
            <label for="reader-name">Nama Lengkap (Wajib):</label>
            <input type="text" id="reader-name" name="name" required aria-required="true">
          </div>

          <div>
            <label for="reader-comment">Komentar:</label>
            <textarea id="reader-comment" name="comment" rows="4" aria-describedby="comment-hint"></textarea>
            <small id="comment-hint">Maksimal 500 karakter. Harap berkomentar dengan sopan.</small>
          </div>

          <button type="submit">Kirim Komentar</button>
        </form>
      </section>
    </article>

    <!-- Sidebar Konten Terkait -->
    <aside aria-label="Informasi Terkait">
      <h3>Artikel Terkait</h3>
      <ul>
        <li><a href="/a11y-basics">Panduan Dasar Aksesibilitas WCAG 2.2</a></li>
        <li><a href="/aria-roles">Memahami Kapan Harus Menggunakan ARIA</a></li>
      </ul>
    </aside>
  </main>

  <footer>
    <p>&copy; 2024 TechJournal Network. Seluruh hak cipta dilindungi undang-undang.</p>
  </footer>

</body>
</html>
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Pendekatan | Semantic HTML Native | Custom Elements + Heavy ARIA |
| :--- | :--- | :--- |
| **Ukuran & Kompleksitas Kode** | Rendah; menggunakan elemen standar tanpa boilerplate script. | Sangat Tinggi; butuh JavaScript ekstensif untuk keyboard events, focus management, dan sinkronisasi atribut state ARIA. |
| **Kinerja Runtime** | Maksimal; dioptimalkan pada layer native C++ oleh browser engine. | Berpotensi lambat; ada overhead komputasi JS DOM mutation listener. |
| **Aksesibilitas Default** | Bawaan (Free accessibility features: focus, activation, role, keyboard handling). | Fragil; jika satu status ARIA (`aria-expanded`) lupa di-update via JavaScript, status a11y akan desinkronisasi. |
| **Fleksibilitas Desain Visual** | Kadang memiliki styling default agresif (seperti `<select>` atau `<input type="date">`) yang sulit di-*reset*. | Visual sepenuhnya bebas dikustomisasi sejak awal. |
| **Dukungan Asistif Antar-Platform**| Sangat stabil dan seragam di semua browser dan screen reader. | Berisiko inkonsisten; interpretasi ARIA kompleks berbeda antar kombinasi OS/Screen Reader (NVDA vs VoiceOver). |

---

## SEKSI 11 — BEST PRACTICES

1. **Hukum Pertama ARIA (First Rule of ARIA):** Jika elemen HTML native sudah memiliki semantik atau perilaku yang Anda butuhkan, **gunakan elemen tersebut**. Jangan gunakan `<div>` lalu menambahkan `role` dan keyboard listener secara manual.
   * *Contoh:* Gunakan `<button>`, bukan `<div role="button" tabindex="0">`.
2. **Pertahankan Hierarki Heading Matematis:** Jangan pernah melompati level heading demi kepentingan gaya font visual (misalnya dari `<h1>` langsung meloncat ke `<h3>`). Gunakan CSS class untuk memodifikasi ukuran visual, biarkan struktur dokumen tetap logis:
   ```html
   <!-- Benar -->
   <h1>Judul Halaman</h1>
   <h2>Bagian Pertama</h2>
   <h3>Sub-bagian A</h3>
   <h2>Bagian Kedua</h2>
   ```
3. **Eksplisitkan Label Form:** Setiap elemen input kontrol wajib terhubung dengan elemen `<label>` via pasangan atribut `for` dan `id`.
4. **Perjelas Maksud Tautan (Hyperlink Meaning):** Hindari teks tautan ambigu seperti "klik di sini" atau "baca lebih lanjut". Tautan harus dapat dipahami secara independen jika diisolasi dari paragraf.
   * ❌ `<a href="/doc">Klik di sini</a> untuk unduh PDF.`
   * ✅ `<a href="/doc">Unduh laporan tahunan (PDF, 2MB)</a>.`
5. **Alt Text Berdasarkan Fungsi Kontekstual:**
   * Gambar informatif: Isi `alt` dengan ringkasan pesan gambar.
   * Gambar murni dekoratif (ikon pemanis layout): Gunakan string kosong (`alt=""`) atau `aria-hidden="true"` agar screen reader melewatinya.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Duplikasi Semantik Native dengan ARIA (Redundant ARIA)
Menambahkan atribut `role` yang fungsinya sama persis dengan elemen native hanya membebani memori parsing.
```html
<!-- SALAH -->
<nav role="navigation">...</nav>
<button role="button">Simpan</button>

<!-- BENAR -->
<nav>...</nav>
<button>Simpan</button>
```

### 2. Mengabaikan Navigasi Keyboard pada Elemen Klik Tiruan
Membuat interaksi pada `<div>` tanpa mengikat event `keydown` / `keyup` dan tanpa atribut `tabindex`.
```javascript
/* SALAH: Pengguna keyboard (disabilitas motorik/visual) TIDAK BISA mengakses elemen ini */
<div class="fake-btn" onclick="sendData()">Kirim</div>

/* BENAR: Menggunakan elemen yang natively focusable dan actionable */
<button type="button" onclick="sendData()">Kirim</button>
```

### 3. Salah Penggunaan Alt Text pada Gambar
* Menuliskan kata "Gambar dari..." atau "Foto..." di dalam atribut `alt`. Screen reader secara default telah mengumumkan kata "graphic" atau "image" sebelum membaca deskripsi alt.
* Menggunakan nama berkas sebagai alt: `alt="IMG_09234.JPG"`.

### 4. Tombol Ikonik Tanpa Accessible Name
Membuat tombol yang hanya berisi icon SVG/Font-icon tanpa teks tersembunyi atau label pendukung.
```html
<!-- SALAH: Screen reader membaca tombol ini sebagai "button, blank" -->
<button><i class="fa fa-trash"></i></button>

<!-- BENAR: Menggunakan aria-label atau teks visually hidden -->
<button aria-label="Hapus Dokumen">
  <svg aria-hidden="true">...</svg>
</button>
```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Starter (Refactoring Landmark & Teks Alternatif)
Refaktor dokumen HTML mentah berikut menjadi markup yang valid, semantik, dan lulus audit dasar Accessibility Tree.

**Tugas Markup Sumber:**
```html
<div class="top-bar">
  <div class="logo">Klinik Sehat</div>
  <div class="nav-links">
    <a href="/dokter">Cari Dokter</a>
    <a href="/jadwal">Jadwal Periksa</a>
  </div>
</div>
<div class="main-body">
  <div class="hero">
    <img src="banner.jpg">
    <div class="hero-desc">Pusat Layanan Medis Terpercaya</div>
  </div>
</div>
<div class="footer">
  <div>Hak Cipta 2024</div>
</div>
```

---

### Latihan 2: Intermediate (Formulir Pendaftaran Aksesibel)
Bangun sebuah formulir interaktif semantik untuk pendaftaran janji temu pasien:
* Memiliki field: Nama Pasien (teks), Email (email), Tanggal Reservasi (date), dan Keluhan Singkat (textarea).
* Setiap kontrol form wajib memiliki `<label>` yang terikat secara programatik.
* Berikan pesan instruksi tambahan pada textarea menggunakan atribut `aria-describedby`.
* Berikan penanda field wajib menggunakan `required` dan `aria-required="true"`.
* Tombol submit wajib menggunakan elemen `<button>` yang valid.

---

### Latihan 3: Advanced (Card Komponen Interaktif & Accessible Modals)
Buat struktur semantic HTML untuk sebuah kartu profil produk e-commerce (*Product Card*):
* Menggunakan tag `<article>`.
* Gambar produk dengan deskripsi alternatif yang akurat.
* Judul produk dengan level heading yang tepat.
* Teks harga dengan semantik teks penekanan atau data waktu/diskon yang tepat (`<del>`, `<ins>`, `<data>` atau `<time>`).
* Grup tombol aksi ("Tambah ke Wishlist", "Beli Sekarang") yang menyertakan label aksesibel untuk *screen reader*, di mana tombol wishlist hanya menampilkan ikon hati visual namun tetap terbaca *"Tambahkan [Nama Produk] ke Wishlist"* oleh teknologi asistif.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawab pertanyaan-pertanyaan berikut untuk menguji pemahaman konsep Anda:

1. **Apa perbedaan teknis mendasar antara elemen `<section>` dan `<article>`?**
   * *A.* `<section>` untuk dokumen panjang, `<article>` untuk dokumen pendek.
   * *B.* `<article>` merepresentasikan konten yang mandiri dan dapat didistribusikan ulang (reusable/syndicatable) secara independen, sedangkan `<section>` merepresentasikan pengelompokan tematik generik dari dokumen yang biasanya memiliki heading sendiri.
   * *C.* `<section>` memiliki nilai visual CSS berupa margin, sedangkan `<article>` tidak.
   * *D.* `<section>` otomatis dibaca oleh screen reader, sedangkan `<article>` diabaikan.

2. **Perhatikan markup berikut: `<button aria-label="Tutup Panel">X</button>`. Teks apa yang akan diumumkan oleh pembaca layar (screen reader)?**
   * *A.* "X"
   * *B.* "Tutup Panel X"
   * *C.* "Tutup Panel, button"
   * *D.* "X Tutup Panel"

3. **Manakah aturan WCAG 2.2 terkait hierarki Heading yang paling benar?**
   * *A.* Setiap halaman wajib memiliki maksimal satu elemen `<h1>`, dan level heading berikutnya harus terstruktur logis tanpa melompati tingkat (misal dari `<h2>` langsung ke `<h4>`).
   * *B.* Heading hanya boleh digunakan jika teks diubah ukurannya menjadi bold.
   * *C.* Heading `<h6>` memiliki prioritas semantik lebih tinggi dibanding `<h3>`.
   * *D.* Diperbolehkan melompati heading jika tampilan visual CSS menghendakinya.

4. **Kapan Anda harus menggunakan atribut `alt=""` (string kosong) pada elemen `<img>`?**
   * *A.* Saat Anda lupa deskripsi dari gambar tersebut.
   * *B.* Saat gambar tersebut bersifat murni dekoratif dan tidak menambahkan konteks informasi baru ke halaman.
   * *C.* Saat format gambar adalah PNG, bukan JPEG.
   * *D.* Atribut `alt` tidak boleh dikosongkan dalam kondisi apa pun.

5. **Apa yang dimaksud dengan "The First Rule of ARIA"?**
   * *A.* Selalu tambahkan ARIA ke setiap elemen HTML.
   * *B.* Jangan menggunakan ARIA jika Anda dapat menggunakan elemen HTML native yang sudah memiliki semantik dan fungsionalitas bawaan yang dibutuhkan.
   * *C.* ARIA hanya berlaku untuk peramban desktop.
   * *D.* Setiap elemen `<div>` harus memiliki atribut `role`.

### Kunci Jawaban & Evaluasi:
* **1: B** — Elemen `<article>` dirancang untuk konten independen (blog post, widget, komentar), sedangkan `<section>` adalah pemisah tematik dokumen.
* **2: C** — Sesuai algoritma Accessible Name Computation, atribut `aria-label` menimpa teks internal node ("X"), kemudian screen reader mengumumkan role-nya ("button").
* **3: A** — Struktur heading membangun outline logis; melompati hierarki akan membingungkan pengguna teknologi asistif saat bernavigasi antar heading.
* **4: B** — Atribut `alt=""` menginstruksikan screen reader untuk melewati elemen gambar dekoratif secara diam-diam tanpa mengumumkan nama file yang mengganggu.
* **5: B** — W3C mengamanatkan prioritas elemen HTML native sebelum beralih ke ARIA sintetis.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **W3C HTML5 Specification:** [W3C Semantic Elements Specification](https://www.w3.org/TR/html52/semantics.html)
* **MDN Web Docs:** [HTML: A good basis for accessibility](https://developer.mozilla.org/en-US/docs/Learn/Accessibility/HTML)
* **Web Content Accessibility Guidelines (WCAG) 2.2:** [W3C Recommendation](https://www.w3.org/TR/WCAG22/)
* **WAI-ARIA Authoring Practices Guide (APG):** [APG Patterns and Practices](https://www.w3.org/WAI/ARIA/apg/)
* **WebAIM (Web Accessibility in Mind):** [WebAIM Resources and Articles](https://webaim.org/)
* **A11y Project Checklist:** [The A11Y Project Checklist](https://www.a11yproject.com/checklist/)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. HTML Semantik bukan perihal preferensi sintaks semata, melainkan penyusunan struktur data dokumen yang menentukan interpretasi mesin pencari dan teknologi asistif melalui **Accessibility Tree**.
2. Elemen Landmark (`<header>`, `<nav>`, `<main>`, `<article>`, `<section>`, `<aside>`, `<footer>`) menyediakan titik loncat (*jump points*) navigasi bagi pengguna disabilitas visual.
3. Hierarki Heading (`<h1>` - `<h6>`) adalah peta navigasi mental dokumen; jangan melompat level hanya demi styling visual.
4. Aksesibilitas (a11y) berlandaskan 4 prinsip utama WCAG: **Perceivable, Operable, Understandable, Robust (POUR)**.
5. Gunakan elemen native terlebih dahulu (**First Rule of ARIA**). Gunakan ARIA hanya ketika HTML native tidak menyediakan kapabilitas semantik atau state yang dibutuhkan.
6. Kontrol interaktif native seperti `<button>` dan `<a>` memberikan dukungan navigasi keyboard (Focus, Tab index, Enter, Space) tanpa perlu baris JavaScript tambahan.

---

## SEKSI 17 — GLOSARIUM

* **Accessibility Tree (AOM):** Struktur paralel yang dibuat browser engine dari DOM Tree yang berisi informasi semantik (Role, Name, State, Value) untuk dikonsumsi API Aksesibilitas OS.
* **Accessible Name:** String teks yang digunakan oleh teknologi asistif untuk mengidentifikasi suatu elemen interaktif kepada pengguna.
* **Landmark:** Wilayah halaman web yang dipetakan secara semantik oleh browser (seperti role `main`, `navigation`, `banner`) untuk memungkinkan navigasi pintas.
* **Screen Reader:** Perangkat lunak pembaca layar (seperti NVDA, JAWS, VoiceOver) yang menerjemahkan antarmuka visual grafis menjadi suara atau output braille.
* **WCAG (Web Content Accessibility Guidelines):** Standar teknis global untuk aksesibilitas web yang dikelola oleh konsorsium W3C.
* **Skip Link:** Tautan tersembunyi di bagian paling atas dokumen yang memungkinkan pengguna keyboard melompati navigasi berulang langsung menuju ke area konten utama.
* **Div-Soup:** Istilah peyoratif untuk menyebut halaman web yang terstruktur secara eksklusif menggunakan tumpukan tag non-semantik `<div>`.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Pedagogis Utama:
* Saat mengajarkan modul ini, **jangan gunakan simulator kebutaan visual berbasis filter blur saja**. Tunjukkan cara kerja screen reader nyata (misal: aktifkan VoiceOver di Mac atau NVDA di Windows, lalu matikan monitor). Biarkan siswa merasakan disorientasi ketika menavigasi situs "Div-Soup" vs situs semantik.
* Tekankan bahwa CSS mengubah **presentasi**, bukan **makna**. Jika kita memperbesar tag `<p>` dengan font size 32px dan font weight bold, teks tersebut tetaplah sebuah paragraf bagi browser engine, bukan sebuah heading.
* Sorot pentingnya tombol `<button>` vs link `<a>`: *"Jika aksi mengubah URL halaman, gunakan tautan (`<a>`). Jika aksi mengeksekusi logika di halaman tanpa navigasi dokumen, gunakan tombol (`<button>`)"*.

### Jebakan Pemula yang Perlu Diwaspadai:
* Siswa sering memasukkan elemen `<header>` dan `<footer>` di dalam tag `<main>`, atau membuat multi-level `<main>` (yang dilarang oleh spesifikasi dokumen W3C; hanya boleh ada satu `<main>` yang terlihat per dokumen).
* Siswa sering mengacaukan teks alternatif gambar dekoratif dengan menghapus atribut `alt` sama sekali. Tekankan bedanya: tidak ada `alt` membuat screen reader mengeja URL gambar, sedangkan `alt=""` membuat screen reader melewatinya secara anggun.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi:** 1.0.0
* **Tanggal Rilis:** 2024-10-24
* **Perubahan Utama:**
  * Inisialisasi rilis kurikulum modul Semantik HTML5 dan Aksesibilitas.
  * Penambahan bab alur konversi DOM ke Accessibility Tree.
  * Pemutakhiran standar referensi menuju WCAG 2.2.
* **Author/Reviewer:** Frontend Curriculum Architecture Core Team

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `FED-CORE-01-01` — Sintaks Dasar HTML, Anatomi Dokumen, dan Lingkungan Kerja Web
* **Modul Saat Ini:** `FED-CORE-01-02` — Semantik HTML5 dan Aksesibilitas
* **Modul Berikutnya:** `FED-CORE-01-03` — Formulir Mendalam, Validasi Native, dan Penanganan Media Responsif