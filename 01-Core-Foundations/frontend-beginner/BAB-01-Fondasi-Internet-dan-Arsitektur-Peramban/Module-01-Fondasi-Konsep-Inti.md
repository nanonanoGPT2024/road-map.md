# Bab 01: Fondasi Rekayasa Frontend Modern
## Modul 01: Arsitektur Ekosistem Web, Critical Rendering Path, dan Anatomi DOM

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis** siklus hidup navigasi browser dari resolusi DNS, *TCP Handshake*, *TLS Negotiation*, hingga transfer paket data HTTP/HTTPS.
- **Mengidentifikasi** tahapan *Critical Rendering Path* (CRP): resolusi HTML parsing, pembentukan *Document Object Model* (DOM), *CSS Object Model* (CSSOM), *Render Tree*, tahapan *Layout/Reflow*, dan *Painting*.
- **Mengevaluasi** dampak blocking script (`async` vs `defer`) terhadap thread pemrosesan utama (*Main Thread*) browser.
- **Mengimplementasikan** struktur semantik HTML5 standar industri yang ramah aksesibilitas (a11y) dan optimal untuk *Search Engine Optimization* (SEO).
- **Mendiagnosis** penurunan performa rendering yang diakibatkan oleh *layout thrashing* dan manipulasi DOM yang tidak efisien menggunakan Browser Developer Tools.

---

### 2. Concept Explanation
Frontend web development pada tingkat rekayasa perangkat lunak bukanlah sekadar merias tampilan antarmuka visual, melainkan mengendalikan alur instruksi pada lingkungan komputasi terdistribusi yang sangat heterogen: **Web Browser**.

Browser mengeksekusi dokumen berbasis teks (HTML) dan mengubahnya menjadi antarmuka grafis interaktif real-time melalui serangkaian lapisan abstraksi perangkat lunak:
1. **Network Layer**: Mengambil aset dari remote server melalui protokol transport dan aplikasi (TCP/IP, HTTP/1.1, HTTP/2, HTTP/3).
2. **Parsing Engine**: Membaca stream data biner/teks menjadi token, lalu mengonstruksinya menjadi struktur data pohon (*Tree Data Structure*) di dalam memori heap.
3. **Rendering/Layout Engine (Blink, Gecko, WebKit)**: Menghitung geometri, koordinat spasial piksel, pewarnaan, dan komposisi layer perangkat keras (GPU Compositing).
4. **JavaScript Engine (V8, SpiderMonkey, JavaScriptCore)**: Mengompilasi dan mengeksekusi logika komputasi dinamis yang memodifikasi model data in-memory secara asinkron.

Memahami model mental ini merupakan fondasi vital: **Browser adalah sebuah *runtime compiler* dan mesin rendering grafis real-time yang mengeksekusi kode Anda di bawah kendali hardware pengguna akhir**.

---

### 3. Why It Matters
Aplikasi web modern menghadapi ekspektasi performa ekstrem: *latency* interaksi di bawah 100ms dan *frame rate* stabil di 60 FPS (16.67ms per frame) atau 120 FPS. 

Ketika seorang engineer menulis satu baris elemen HTML atau script eksternal tanpa memahami cara kerja internal browser:
- Main Thread dapat terblokir (*thread starvation*), menyebabkan UI membeku (*jank/unresponsive*).
- Terjadi *Cumulative Layout Shift* (CLS) tinggi yang merusak *User Experience* dan menurunkan ranking Core Web Vitals pada algoritma Google.
- Konsumsi memori melonjak drastis pada perangkat mobile dengan spesifikasi rendah akibat retensi node DOM yang terisolasi (*detached DOM nodes*).

Rekayasa frontend yang andal menuntut penguasaan mutlak atas siklus hidup *rendering*, alokasi memori, serta alur data dari jaringan hingga piksel di layar monitor.

---

### 4. What It Is / What It Is Not

| Karakteristik | What It Is (Apa Sebenarnya) | What It Is Not (Bukan Hal Ini) |
|---|---|---|
| **HTML** | Bahasa deklaratif untuk memetakan struktur semantik, hierarki informasi, dan dokumen objek in-memory. | Bahasa pemrograman komputasional; bukan sekadar "syntax visual" untuk styling teks. |
| **DOM Tree** | Representasi node berbasis *object-oriented* dari dokumen HTML yang hidup di memori RAM dan dapat diakses via API. | Kode sumber teks HTML yang Anda tulis di text editor; bukan string statis. |
| **Browser Execution** | Lingkungan multi-process (Browser Process, Renderer Process, GPU Process, Network Process). | Satu proses monolitik tunggal yang hanya membaca file dari atas ke bawah. |
| **Web Standards** | Spesifikasi teknis formal yang diratifikasi oleh W3C dan WHATWG untuk interoperabilitas lintas platform. | Aturan subjektif yang dapat diabaikan atau fitur khusus salah satu browser saja. |

---

### 5. How It Works
Siklus dari input URL hingga visualisasi piksel pertama (*First Contentful Paint*) bekerja melalui pipa internal (*pipeline*) berikut:

1. **URL Resolution & Networking**:
   - Browser mengecek cache (DNS, HSTS, HTTP Cache).
   - Melakukan DNS Lookup (UDP) untuk menemukan IP target.
   - Melakukan TCP 3-Way Handshake (`SYN` $\rightarrow$ `SYN-ACK` $\rightarrow$ `ACK`).
   - Melakukan negosiasi TLS Handshake (enkripsi kunci publik/simetris).
   - Mengirimkan HTTP GET Request, menerima response byte stream (`Content-Type: text/html`).

2. **Bytes to Tokens (Tokenization)**:
   - Renderer process membaca raw bytes dari network buffer.
   - Mengonversi bytes menjadi karakter berdasarkan encoding (misal: UTF-8).
   - Lexer/Tokenizer mengubah karakter menjadi token standar (`StartTag: <html>`, `StartTag: <body>`, `EndTag: </body>`, dll).

3. **Tokens to Nodes & Tree Construction (DOM Tree)**:
   - Parser memproses token secara berurutan sesuai relasi parent-child.
   - Menginstansiasi node berbasis `Node` / `Element` interface ke dalam struktur data tree.

4. **Style Computation (CSSOM Construction)**:
   - Membaca file `.css` dan inline styles.
   - Menghitung nilai CSS cascade, inheritance, dan specificity menjadi *CSS Object Model*.

5. **Render Tree Generation**:
   - Mengombinasikan DOM dan CSSOM. Node dengan `display: none` diabaikan dari Render Tree (berbeda dengan `visibility: hidden` yang tetap masuk).

6. **Layout / Reflow**:
   - Menghitung geometri persis: ukuran (width/height) dan koordinat spasial (X/Y) setiap node visual relatif terhadap viewport.

7. **Paint & Compositing**:
   - Mengonversi data layout menjadi piksel visual (rasterization).
   - Memecah elemen ke dalam GPU layers, lalu mengirimkannya ke GPU untuk dikomposisikan (*composite layers*) ke layar.

---

### 6. ASCII Diagram: The Critical Rendering Path

```text
+-----------------------------------------------------------------------+
|                           NETWORK LAYER                               |
|  [Raw Bytes: 3C 68 74 6D 6C 3E] -> Character Stream (UTF-8 Parsing)   |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|                      PARSER / TOKENIZER                               |
|  Tokens: <StartTag: html> -> <StartTag: body> -> <EndTag: html>       |
+-----------------------------------------------------------------------+
        |                                                   |
        v                                                   v
+------------------+                               +------------------+
|     DOM TREE     |                               |   CSSOM TREE     |
|   (Object Node)  |                               | (Computed Style) |
|      [html]      |                               |     [body]       |
|      /    \      |                               |  font-size: 16px |
|   [head]  [body] |                               +------------------+
|             |    |                                        |
|            [h1]  |                                        |
+------------------+                                        |
        \                                                   /
         \_________________       _________________________/
                           \     /
                            v   v
                 +-----------------------+
                 |      RENDER TREE      |
                 | (Visible Nodes Only)  |
                 |     [h1: "Hello"]     |
                 +-----------------------+
                            |
                            v
                 +-----------------------+
                 |     LAYOUT ENGINE     |
                 | (Calculates Box Model |
                 |   X, Y, Width, H)     |
                 +-----------------------+
                            |
                            v
                 +-----------------------+
                 |     PAINT ENGINE      |
                 |  (Rasterization: Text,|
                 |   Colors, Shadows)    |
                 +-----------------------+
                            |
                            v
                 +-----------------------+
                 |    COMPOSITOR (GPU)   |
                 |  (Layers draw to screen)
                 +-----------------------+
```

---

### 7. Simple Code Example
Struktur minimal dokumen HTML5 yang valid secara semantik dan mekanika browser:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <!-- Metadata esensial untuk parser & rendering engine -->
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Minimal Fast Document</title>
  
  <style>
    /* Critical CSS: Minimal, mengeblok render sejenak demi mencegah FOIT/FOUC */
    body {
      font-family: system-ui, -apple-system, sans-serif;
      margin: 0;
      padding: 1.5rem;
    }
  </style>
</head>
<body>
  <header>
    <h1>Dokumen Performa Tinggi</h1>
  </header>

  <main>
    <p>Halaman ini meminimalkan CSSOM blocking dan menghindari parser-blocking JavaScript.</p>
  </main>

  <!-- Non-critical script dieksekusi secara asinkron tanpa memblokir DOM parsing -->
  <script src="app.js" defer></script>
</body>
</html>
```

---

### 8. Production/Practical Code Example
Implementasi arsitektur dokumen HTML5 tingkat produksi dengan optimasi *Critical Rendering Path*, resource hints, dan struktur semantik aksesibel.

```html
<!DOCTYPE html>
<html lang="id" dir="ltr">
<head>
  <meta charset="UTF-8">
  <!-- Wajib untuk responsivitas layout engine -->
  <meta name="viewport" content="width=device-width, initial-scale=1.0, shrink-to-fit=no">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  
  <!-- SEO & Social Graph Meta Tags -->
  <title>Enterprise Portal Engine | Performa Ekstrem</title>
  <meta name="description" content="Portal arsitektur enterprise modern dengan pemuatan sub-detik.">
  <link rel="canonical" href="https://example.com/portal">

  <!-- Resource Hints: Optimasi jaringan seawal mungkin -->
  <!-- Resolusi DNS sebelum network request terjadi -->
  <link rel="dns-prefetch" href="//analytics.provider.com">
  <!-- Preconnect untuk origin kritis: DNS + TCP + TLS handshake sekaligus -->
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

  <!-- Critical Inline Styles: Mencegah Flash of Unstyled Content (FOUC) -->
  <style>
    :root {
      --color-primary: #0284c7;
      --color-text: #0f172a;
      --color-bg: #ffffff;
    }
    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
    }
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: var(--color-text);
      background-color: var(--color-bg);
      line-height: 1.5;
    }
    .skeleton-placeholder {
      min-height: 200px;
      background: #e2e8f0;
      border-radius: 8px;
    }
  </style>

  <!-- Non-critical external stylesheet di-preload atau dipanggil via mekanisme non-blocking -->
  <link rel="preload" href="/css/main.chunk.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
  <noscript><link rel="stylesheet" href="/css/main.chunk.css"></noscript>

  <!-- Script Blocking Strategy: Menggunakan defer untuk mempertahankan eksekusi berurutan pasca-DOM parsing -->
  <script src="/js/core-runtime.js" defer></script>
  <script src="/js/analytics-tracker.js" async></script>
</head>
<body>
  <!-- Navigasi Aksesibel: Landasan Screen Reader (WCAG Standard) -->
  <header role="banner">
    <nav role="navigation" aria-label="Navigasi Utama">
      <ul>
        <li><a href="#main-content">Lewati ke Konten Utama</a></li>
        <li><a href="/dashboard">Dashboard</a></li>
      </ul>
    </nav>
  </header>

  <main id="main-content" role="main">
    <article>
      <header>
        <h2>Metrik Eksekusi Browser Engine</h2>
        <time datetime="2026-03-30">30 Maret 2026</time>
      </header>
      
      <section aria-labelledby="section-stats">
        <h3 id="section-stats">Real-Time Core Web Vitals</h3>
        <div class="skeleton-placeholder" id="cwv-container">
          <!-- Injeksi Dynamic Template Data Client-Side -->
          <p>Memuat metrik...</p>
        </div>
      </section>
    </article>
  </main>

  <footer role="contentinfo">
    <p>&copy; 2026 Enterprise Systems. All rights reserved.</p>
  </footer>
</body>
</html>
```

---

### 9. Trade-offs & Alternatives

| Pendekatan | Keuntungan | Kerugian / Trade-off | Skenario Penggunaan yang Tepat |
|---|---|---|---|
| **`<script>` Standar (In-Head)** | Menjamin dependensi JS berjalan sebelum DOM diproses. | **Parser-blocking fatal**: Browser menghentikan konstruksi DOM secara total sampai file diunduh & dieksekusi. | Hampir **tidak boleh** digunakan di web modern kecuali polyfill engine yang sangat mendasar. |
| **`<script defer>`** | Non-blocking download; eksekusi ditunda sampai DOM selesai di-parse; urutan deklarasi file tetap terjaga. | Eksekusi script tertunda hingga parsing selesai; tidak cocok untuk metrik tracking yang harus firing instan. | Script aplikasi utama, library UI, dependensi yang berurutan. |
| **`<script async>`** | Non-blocking download; langsung dieksekusi detik itu juga begitu file selesai didownload. | Urutan eksekusi **tidak terjamin** (file kecil bisa menyalip file besar); dapat memotong parsing DOM saat eksekusi. | Script independen terisolasi: Analytics (Google Analytics), Ads, tracking piksel. |
| **CSS Inlining (`<style>`)** | Mengeliminasi round-trip HTTP request untuk CSS kritis, mempercepat *First Contentful Paint*. | Tidak dapat di-cache oleh browser secara terpisah dari dokumen HTML; memperbesar ukuran payload awal HTML. | CSS layout global atau *above-the-fold critical styling* saja. |

---

### 10. Best Practices & Guidelines
- **Gunakan Doctype HTML5 Baku (`<!DOCTYPE html>`)**: Memastikan browser berjalan pada *Standards Mode*, bukan *Quirks Mode* (yang meniru bug-bug browser kuno era 1990-an).
- **Struktur Semantik Prioritas**: Selalu gunakan `<main>`, `<nav>`, `<article>`, `<section>`, `<aside>`, `<header>`, dan `<footer>` alih-alih memanfaatkan `<div>` untuk segala kebutuhan (*div-soup antipattern*).
- **Tentukan Charset Sedini Mungkin**: Masukkan `<meta charset="UTF-8">` tepat di baris pertama dalam `<head>` sebelum karakter non-ASCII apa pun muncul untuk mencegah re-parsing encoding.
- **Deklarasikan Dimensi Gambar**: Selalu cantumkan atribut `width` dan `height` eksplisit pada tag `<img>` untuk memberi tahu layout engine rasio aspek (*aspect-ratio*), menghindari *Cumulative Layout Shift* (CLS).
- **Hindari Inline Event Handlers**: Jangan gunakan `onclick="..."` dalam atribut HTML. Pisahkan murni struktur (HTML), gaya (CSS), dan perilaku komputasi (JavaScript via `addEventListener`).

---

### 11. Common Pitfalls & Anti-Patterns

#### Anti-Pattern: Blocking the Parser dengan External Scripts
*Root Cause*: Parser mendapati tag `<script src="...">` tanpa atribut `defer` atau `async`. Parsing dihentikan (*stall*), render terblokir.

##### Buruk (Bad Practice):
```html
<head>
  <title>Situs Lambat</title>
  <!-- Parser terhenti di sini selama ratusan milidetik untuk download dan eksekusi -->
  <script src="heavy-bundle.js"></script>
  <link rel="stylesheet" href="style.css">
</head>
```

##### Benar (Good Practice):
```html
<head>
  <title>Situs Cepat</title>
  <!-- Non-blocking download, dieksekusi pasca DOM parsing selesai terstruktur -->
  <script src="heavy-bundle.js" defer></script>
  <link rel="stylesheet" href="style.css">
</head>
```

---

#### Anti-Pattern: Non-Semantic Div-Soup
*Root Cause*: Mengabaikan semantik bawaan browser, merusak fungsionalitas screen reader dan parsing mesin pencari.

##### Buruk (Bad Practice):
```html
<div class="header">
  <div class="nav-btn" onclick="goToMenu()">Menu</div>
</div>
<div class="content">
  <div class="big-text">Judul Artikel</div>
  <div class="text">Isi paragraf di sini...</div>
</div>
```

##### Benar (Good Practice):
```html
<header>
  <nav>
    <button type="button" aria-expanded="false" id="menu-toggle">Menu</button>
  </nav>
</header>
<main>
  <article>
    <h1>Judul Artikel</h1>
    <p>Isi paragraf di sini...</p>
  </article>
</main>
```

---

### 12. Edge Cases & Boundary Conditions
1. **Streaming HTML Parsing**: Browser tidak menunggu seluruh file HTML selesai diunduh untuk mulai parsing. Browser memproses data per-*chunk* yang tiba lewat TCP stream. Jika ada script blocking di tengah chunk, streaming terhenti.
2. **Quirks Mode vs No-Quirks Mode**: Jika deklarasi `<!DOCTYPE html>` dihilangkan atau ditaruh di bawah komentar/karakter lain, browser mengaktifkan *Quirks Mode*, mengubah algoritma box-model CSS (lebar border dihitung di dalam width/height secara keliru).
3. **Speculative Parsing / Preload Scanner**: Browser engine modern menjalankan thread parsing sekunder (*Preload Scanner*) saat thread parser utama terblokir oleh script. Scanner ini mencari URL aset (`link`, `script`, `img`) lebih awal untuk memulai download paralel.
4. **Mutasi DOM Bersarang Dalam (*Deeply Nested Elements*)**: Nesting HTML melebihi kedalaman 32 level memicu overhead memori pada struktur tree layout engine dan memperlambat traversal selektor CSS kompleks secara eksponensial.

---

### 13. Performance & Resource Considerations

```text
Performa DOM Tree Rendering:
- Waktu Parsing DOM: O(N) linear terhadap jumlah total nodes/tokens.
- CSS Specificity Matching: O(N * M) di mana N adalah jumlah elemen, M adalah selektor CSS kompleks.
- Layout Calculation: Worst-case O(N^2) jika memicu Forced Synchronous Layout / Layout Thrashing.
```

- **DOM Node Budget**: Batasi jumlah total elemen DOM dalam satu halaman di bawah **1.500 nodes**, kedalaman tree maksimal **32 nodes**, dan child nodes pada satu parent tidak melebihi **60 nodes**. Melanggar ini menyebabkan *garbage collection pause* tinggi di V8 engine.
- **Memory Footprint**: Setiap node DOM adalah objek C++ di dalam browser core (misal: Blink `Element` class instance) yang memakan memori RAM signifikan jika diakumulasikan.
- **Minifikasi & Kompresi**: HTML harus dikompresi di level server menggunakan algoritma **Brotli (br)** atau minimal **Gzip**, serta dilakukan penghapusan whitespace dan komentar (*HTML minification*) pada build step CI/CD.

---

### 14. Security Implications (OWASP & Threat Modeling)

```text
                     ATTACK VECTOR: Stored / Reflected XSS
                     
   Unsanitized User Input
             |
             v
   [ Browser Parser ] ====> Mengira input adalah tag valid:
                            "<img src=x onerror=alert(document.cookie)>"
                                     |
                                     v
                        [ Malicious Token Created ]
                                     |
                                     v
                     [ Arbitrary JavaScript Executed ]
                                     |
                                     v
                     [ Session Hijack / Data Theft ]
```

- **Cross-Site Scripting (XSS)**: Memasukkan data user mentah langsung ke dalam dokumen HTML menggunakan mekanisme manipulasi seperti `.innerHTML` membuka celah eksekusi script arbitrer. Selalu gunakan `.textContent` atau sanitasi ketat dengan pustaka seperti `DOMPurify`.
- **Content Security Policy (CSP)**: Deklarasikan header CSP untuk membatasi sumber asal script yang boleh dieksekusi browser:
  ```http
  Content-Security-Policy: default-src 'self'; script-src 'self' https://trustedscripts.com; object-src 'none';
  ```
- **Rel Noopener / Noreferrer**: Saat merender link eksternal dengan target blank:
  ```html
  <a href="https://external-site.com" target="_blank" rel="noopener noreferrer">Aset Luar</a>
  ```
  Menghilangkan `rel="noopener"` memungkinkan situs luar mengakses pointer `window.opener` dan mengubah lokasi navigasi halaman asli Anda (*Reverse Tabnabbing*).

---

### 15. Testing Strategies
Pengujian pada level fondasi dokumen HTML mencakup:
1. **Validasi Sintaksis Standar**:
   - Gunakan `html-validate` atau W3C Nu HTML Checker pada pipa CI/CD untuk memastikan zero syntax errors, unclosed tags, atau pelanggaran atribut.
2. **Aksesibilitas Otomatis (a11y)**:
   - Gunakan engine `@axe-core/cli` atau `pa11y` untuk mendeteksi *contrast ratio*, *missing alt tags*, *aria-roles* yang rusak, atau struktur heading level yang tidak urut (misal: lompat dari `<h1>` ke `<h3>`).
3. **Audit Core Web Vitals**:
   - Eksekusi **Lighthouse CLI** secara terisolasi untuk mengukur FCP (*First Contentful Paint*), LCP (*Largest Contentful Paint*), dan CLS (*Cumulative Layout Shift*).

```bash
# Integrasi pipeline: Validasi integritas dokumen dan aksesibilitas
npx html-validate "src/**/*.html"
npx axe https://localhost:8080 --tags wcag2a,wcag2aa
npx lighthouse-ci collect --url=http://localhost:8080
```

---

### 16. Debugging & Observability
Untuk mengamati dan memverifikasi alur parsing dan rendering:

1. **Chrome DevTools -> Network Panel**:
   - Amati kolom *Waterfall*.
   - Perhatikan bar biru muda (*Resource Scheduling/Queued*), hijau (*Time to First Byte / TTFB*), dan biru tua (*Content Download*).
   - Pastikan script eksternal tidak menahan *DOMContentLoaded* (garis vertikal biru).

2. **Chrome DevTools -> Performance Panel**:
   - Lakukan profiling rekaman (Record).
   - Periksa sub-panel *Main*: Analisis event `Parse HTML`, `Recalculate Style`, `Layout`, `Pre-Paint`, dan `Paint`.
   - Identifikasi *Long Tasks* (blok merah dengan durasi > 50ms) yang menahan Main Thread selama rendering.

3. **Chrome DevTools -> Console Timing API**:
   Gunakan instrumentasi programmatic untuk mengukur waktu rendering:
   ```javascript
   performance.mark('custom_parse_start');
   // ... Operasi modifikasi DOM atau kalkulasi ...
   performance.mark('custom_parse_end');
   performance.measure('DOM_Operation', 'custom_parse_start', 'custom_parse_end');
   console.log(performance.getEntriesByName('DOM_Operation')[0].duration + 'ms');
   ```

---

### 17. Real-world Scenario / Case Study

#### Permasalahan:
Sebuah portal berita e-commerce mengalami bounce rate 45% di jaringan mobile. Hasil profiling menunjukkan metrik **LCP (Largest Contentful Paint) berada di angka 4.8 detik** dan terjadi visual freeze berkepanjangan pada awal render.

#### Investigasi Akar Masalah:
Melalui DevTools Network dan Performance tracing, ditemukan:
1. File bundel analitik sebesar 350KB diletakkan di `<head>` tanpa atribut `defer` atau `async`.
2. Parser browser berhenti total selama ~1.8 detik saat mendownload dan mengeksekusi script tersebut sebelum tag `<body>` berhasil di-parse.
3. Gambar hero utama dimuat via CSS `background-image` yang baru terpicu setelah CSSOM dan Render Tree selesai dibentuk.

#### Solusi Perbaikan:
1. Menambahkan atribut `defer` ke script core dan memindahkan script analytics ke `async` dengan prioritas rendah.
2. Mengubah CSS background image menjadi tag `<img>` semantik dengan atribut native priority:
   ```html
   <link rel="preload" as="image" href="/assets/hero-banner.webp" fetchpriority="high">
   ```
3. Meng-inline Critical CSS dasar (hanya rule navigasi dan banner) dan me-load sisanya secara asinkron.

#### Hasil:
LCP terpangkas dari **4.8 detik menjadi 1.1 detik**. Main Thread blocking time drop sebesar 82%, dan metrik konversi bertambah sebesar 18% dalam dua minggu pertama rilis.

---

### 18. Exercises & Step-by-Step Challenges

#### Deskripsi Tantangan:
Anda diberikan dokumen HTML yang memiliki berbagai pelanggaran arsitektur: blocking parser, anti-semantik, dan aksesibilitas rusak. Tugas Anda adalah merekonstruksinya menjadi dokumen standar enterprise dengan *zero rendering block*.

#### Starter Code (Bermasalah):
```html
<html>
<head>
  <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
  <script src="/tracker.js"></script>
  <div style="font-size: 24px; font-weight: bold;">Portal Berita</div>
</head>
<body>
  <div id="wrapper">
    <div class="menu-list">
      <div onclick="location.href='/home'">Home</div>
      <div onclick="location.href='/tech'">Tech</div>
    </div>
    
    <div class="main-story">
      <div class="title">Serverless Architecture 2026</div>
      <img src="banner.jpg">
      <div class="body">Komputasi awan kini beralih...</div>
    </div>
  </div>
</body>
</html>
```

#### Batasan & Aturan (Constraints):
- Gunakan standar valid HTML5 (`<!DOCTYPE html>`, proper tags).
- Script `jquery` hanya boleh dijalankan jika DOM sudah siap; `tracker.js` tidak boleh menghambat render tree.
- Konversi seluruh struktur `div-soup` ke elemen semantik standar W3C.
- Berikan atribut rasio aspek gambar untuk mencegah CLS.
- Lengkapi metadata minimum untuk responsivitas viewport dan encoding UTF-8.

#### Solusi Jawaban Terverifikasi:
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Portal Berita - Rekayasa Frontend</title>

  <!-- jQuery dieksekusi teratur setelah DOM Tree selesai, tracker dieksekusi asinkron murni -->
  <script src="https://code.jquery.com/jquery-3.7.1.min.js" defer></script>
  <script src="/tracker.js" async></script>
</head>
<body>
  <header>
    <h1>Portal Berita</h1>
    <nav aria-label="Navigasi Header">
      <ul>
        <li><a href="/home">Home</a></li>
        <li><a href="/tech">Tech</a></li>
      </ul>
    </nav>
  </header>

  <main id="content">
    <article>
      <header>
        <h2>Serverless Architecture 2026</h2>
      </header>
      <figure>
        <img 
          src="banner.jpg" 
          alt="Diagram arsitektur sistem berbasis serverless" 
          width="800" 
          height="450" 
          loading="eager" 
          fetchpriority="high">
        <figcaption>Infrastruktur modern berbasis event-driven.</figcaption>
      </figure>
      <p>Komputasi awan kini beralih...</p>
    </article>
  </main>
</body>
</html>
```

---

### 19. Self-Assessment / Quiz
Uji penguasaan konsep Anda terhadap sistem internal browser:

1. **Apa perbedaan mendasar antara DOM Tree dan Render Tree?**
   - *Jawaban*: DOM Tree merepresentasikan seluruh elemen dokumen secara utuh sesuai token HTML termasuk tag `<head>`, `<meta>`, `<script>`, dan node berlabel `display: none`. Sedangkan Render Tree hanya mencakup node visual yang benar-benar akan dikomposisikan ke layar (mengabaikan node tak terlihat seperti `<head>` atau node dengan styling `display: none`).

2. **Jika sebuah script memiliki atribut `defer`, kapan tepatnya browser akan mengeksekusi script tersebut?**
   - *Jawaban*: Script diunduh secara paralel di background selama proses parsing HTML berlangsung, dan dieksekusi tepat setelah parsing dokumen HTML selesai, sesaat sebelum browser menembakkan event `DOMContentLoaded`.

3. **Mengapa modifikasi ukuran elemen menggunakan JavaScript berulang-ulang di loop dapat memicu *Layout Thrashing*?**
   - *Jawaban*: Karena membaca properti geometris (seperti `offsetWidth`, `clientHeight`) memaksa browser untuk langsung melakukan kalkulasi Layout sinkron (*Forced Synchronous Layout*) sebelum loop berikutnya dapat menulis perubahan nilai baru, menghancurkan optimasi batch rendering browser engine.

4. **Kapan Anda memilih atribut `async` dibandingkan `defer`?**
   - *Jawaban*: `async` dipilih untuk file script independen pihak ketiga yang tidak memanipulasi DOM dan tidak bergantung pada script lain (contoh: tracking Google Analytics, log event). `defer` dipilih untuk script yang bergantung pada DOM siap atau script aplikasi yang membutuhkan jaminan urutan eksekusi dependency.

5. **Apa efek samping dari menghapus deklarasi `<!DOCTYPE html>` pada baris pertama file HTML?**
   - *Jawaban*: Browser engine akan mengaktifkan *Quirks Mode*, menonaktifkan standar layout W3C modern dan memberlakukan box model legacy masa lalu yang menyebabkan kalkulasi ukuran kontainer layout tidak konsisten antar browser modern.

---

### 20. References & Further Reading
- **W3C / WHATWG HTML Living Standard**: Spesifikasi resmi mekanisme parsing dan model objek DOM (https://html.spec.whatwg.org/multipage/)
- **MDN Web Docs**: *Populating the page: how browsers work* (Detail tahapan Critical Rendering Path)
- **Chromium Project Documentation**: *Life of a Pixel* (Arsitektur internal Blink Engine, Layout, Paint, dan GPU Compositor)
- **Web.dev by Google**: *Optimize Critical Rendering Path & Core Web Vitals (LCP, FID/INP, CLS)*