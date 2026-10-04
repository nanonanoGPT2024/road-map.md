# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 03-Frontend-and-Mobile | **Topik:** HTML | **Bab:** 01 - Fondasi dan Arsitektur

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis dan Membedah Algoritma Parsing HTML5**: Memahami *Tokenization*, *Tree Construction*, hingga *Speculative Parsing* (Preload Scanner) pada level browser engine (Blink/WebKit/Gecko).
2. **Mengorkestrasi Critical Rendering Path (CRP)**: Menghilangkan *parser-blocking* dan *render-blocking resources* menggunakan strategi pemuatan skrip modern (`async`, `defer`, ES Modules, dan `fetchpriority`).
3. **Mengonstruksi Arsitektur Dokumen Skala Enterprise**: Menerapkan pola *Streaming HTML* berbasis *Chunked Transfer Encoding* dan *Islands Architecture* (partial hydration boundaries).
4. **Menerapkan Zero-Trust Security Perimeter pada Lapisan Dokumen**: Mengonfigurasi Content Security Policy (CSP Level 3), Subresource Integrity (SRI), serta isolasi origin tingkat lanjut (`COOP`, `COEP`, `CORP`).
5. **Mengeliminasi Degradasi Core Web Vitals**: Merancang struktur dokumen HTML yang secara deterministik mencegah *Cumulative Layout Shift* (CLS) dan meminimalkan *Largest Contentful Paint* (LCP).

---

## 2. Prerequisite

Sebelum mendalami modul ini, Anda wajib menguasai:
* Fundamental protokol HTTP/1.1, HTTP/2, dan HTTP/3 (multiplexing, head-of-line blocking, header compression HPACK/QPACK).
* Arsitektur runtime browser dasar (Main Thread, Worker Threads, Network Process, Compositor, GPU Process).
* Struktur dasar Document Object Model (DOM) dan Cascading Style Sheets Object Model (CSSOM).
* Dasar-dasar asynchronous execution JavaScript (Event Loop, Microtasks, Macrotasks).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Parsing Pipeline: Dari Byte Mentah ke DOM Tree

Browser tidak langsung mengeksekusi markup HTML. Proses transformasi dari stream biner menjadi representasi memori *in-memory tree structure* mengikuti spesifikasi formal HTML5 (WHATWG) melalui lima fase sekuensial:

```
[Network: Raw Bytes]
         │
         ▼ (Character Encoding: UTF-8)
[Characters Stream]
         │
         ▼ (Lexical Analysis: State Machine)
[Tokens (<tag>, </tag>, text, attr)]
         │
         ▼ (Tree Construction: Insertion Modes)
[DOM Nodes Tree]
         │
         ▼ (CSSOM + DOM Integration)
[Render Tree] ──► [Layout / Reflow] ──► [Paint] ──► [Composite]
```

1. **Byte Stream Decoding**: Data biner dari soket TCP/QUIC dikonversi ke deretan karakter berdasarkan *character encoding* yang dideklarasikan (`Content-Type: text/html; charset=UTF-8` pada HTTP response header atau tag `<meta charset="utf-8">`). Jika header absen, browser terpaksa menjalankan *character encoding sniffing* yang memakan latensi ekstra.
2. **Tokenization (State Machine)**: Parser mengimplementasikan *finite-state machine*. Karakter dikonsumsi satu per satu untuk menghasilkan token: `DOCTYPE`, `StartTag`, `EndTag`, `Comment`, `Character`, atau `EndOfFile`.
3. **Tree Construction (Insertion Modes)**: Algoritma *tree construction* bersifat reentrant dan bergantung pada konteks (*Insertion Mode*, misalnya: `initial`, `before html`, `before head`, `in head`, `in body`). Algoritma ini memiliki aturan koreksi kesalahan otomatis (*error tolerance*), seperti otomatis menyisipkan tag `<tbody>` di dalam `<table>` atau menutup tag `<p>` yang tidak berpasangan ketika bertemu tag block-level lain.
4. **Speculative Parsing (Preload Scanner)**: Karena *main parser* dapat terblokir oleh eksekusi skrip sinkron (`<script src="...">`), browser modern menjalankan thread terpisah bernama **Preload Scanner**. Thread ini memindai *stream* HTML secara spekulatif jauh di depan *main parser* untuk mengidentifikasi URL sub-sumber daya eksternal (CSS, JS, Web Fonts, Images) dan langsung menjadwalkan request jaringan berprioritas tinggi.

### 3.2. Script Execution Dynamics & Parser Blocking

Perilaku elemen `<script>` memengaruhi *Critical Rendering Path* secara signifikan:

| Atribut / Tipe | Eksekusi Jaringan (Fetch) | Waktu Eksekusi Skrip | Memblokir Parsing HTML? | Urutan Eksekusi (*Order*) |
| :--- | :--- | :--- | :--- | :--- |
| `<script src="...">` | Paralel (Main thread/Scanner) | Seketika saat unduhan selesai | **Ya** (Pause parsing) | Terurut sesuai kemunculan |
| `<script defer src="...">` | Paralel di latar belakang | Setelah HTML selesai diparsing, tepat sebelum `DOMContentLoaded` | **Tidak** | Terurut sesuai kemunculan di dokumen |
| `<script async src="...">` | Paralel di latar belakang | Seketika saat unduhan selesai (dapat menyela parsing) | **Ya**, hanya saat eksekusi | Tidak berurutan (*race condition*) |
| `<script type="module">` | Paralel (perilaku setara `defer`) | Setelah parsing selesai, sebelum `DOMContentLoaded` | **Tidak** | Terurut (hierarki dependency graph) |
| `<script type="module" async>`| Paralel di latar belakang | Seketika saat modul & dependensi selesai diunduh | **Ya**, saat eksekusi modul | Tidak berurutan |

### 3.3. Document Streaming dan Hydration Architectures

Pada arsitektur modern (misalnya SSR dengan React 18+, SvelteKit, atau Astro), server web tidak perlu menunggu seluruh halaman selesai dirender sebelum mengirim byte pertama.

Dengan menggunakan HTTP/1.1 `Transfer-Encoding: chunked` atau *data frames* HTTP/2/3, server mengirimkan *Initial Shell* (HTML `<head>`, CSS kritis, dan skeleton) secara instan. Browser dapat langsung membangun DOM parsed awal dan memulai *pre-fetching*, sementara server melakukan *streaming* komponen asinkron ke dalam stream dokumen yang sama.

---

## 4. Why & What

### Mengapa HTML Arsitektural Penting?
HTML bukan sekadar bahasa penandaan dekoratif (*presentational markup*). Dalam rekayasa sistem front-end modern:
* **HTML adalah Resource Orchestrator**: Dokumen HTML menentukan prioritas alokasi bandwidth, antrean soket jaringan, dan urutan eksekusi CPU pada perangkat klien.
* **HTML adalah Security Perimeter Pertama**: Header HTTP bersama tag `<meta>` adalah batas isolasi memori proses browser (*Site Isolation*) dan pertahanan terhadap XSS, Clickjacking, dan XS-Leaks.
* **HTML Menentukan Efisiensi LCP & INP**: Keputusan penempatan tag, deklarasi ukuran atribut `width`/`height`, dan penggunaan `fetchpriority` secara langsung mengontrol skor Web Vitals.

### Apa yang Membedakan Implementasi Enterprise?
Pada level enterprise, HTML dirancang secara deterministik:
1. Tidak ada dependensi yang tidak memiliki deklarasi integritas hash (SRI).
2. Sumber daya kritis di-*preload* dengan ukuran aset dan tipografi yang tepat guna mencegah *Flash of Unstyled Text* (FOUT) atau *Flash of Invisible Text* (FOIT).
3. Struktur semantik yang ketat untuk kompatibilitas penuh dengan *Assistive Technologies* (Screen Readers, braille displays) melalui pemetaan Accessible Rich Internet Applications (ARIA) otomatis tanpa markup berlebih.

---

## 5. How (Workflow Detail)

Alur kerja browser memproses dokumen HTML kelas produksi dari jaringan ke frame pertama:

```
[Inisiasi Request GET /]
         │
         ▼
[Server Respon: HTTP 200 OK + Early Hints (103)]
         │
         ├───► Preconnect & Preload link diproses oleh Browser Network Stack
         │
         ▼
[First Chunk HTML Diterima] ───► Tokenizer Aktif
         │                             │
         ├── Speculative Scanner       ├── Main Thread Parser
         │   menemukan:                │   menemukan:
         │   - Critical CSS            │   - DOCTYPE
         │   - Critical Font           │   - Meta viewport (tentukan layout baseline)
         │   - Deferred Scripts        │   - Inline critical CSS (kalkulasi CSSOM awal)
         │   (Unduhan dijadwalkan)     │
         │                             ▼
         │                    [CSSOM Siap & DOM Node Terbentuk]
         │                             │
         ▼                             ▼
[Next Chunks (Body Content)] ──► Streaming DOM Update ──► First Contentful Paint (FCP)
         │
         ▼
[Streaming Shell Selesai] ──► Deferred Scripts Mengeksekusi ──► DOMContentLoaded
         │
         ▼
[Images/Fonts Selesai Dimuat] ──► window.onload ──► Largest Contentful Paint (LCP) Stabil
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Konduktor Orkestra dan Rencana Logistik
Bayangkan dokumen HTML sebagai **Buku Rencana Logistik Pabrik Perakitan Cepat**.
* Jika rencana tersebut menuliskan instruksi: *"Tunggu kurir tiba membawa buku manual sebelum membangun dinding pabrik"* (Skrip sinkron tanpa atribut di dalam `<head>`), maka seluruh pekerja konstruksi berhenti bekerja (*Parser Blocking*).
* Namun, jika rencana tersebut menuliskan: *"Mulai pasang fondasi, kurir buku manual silakan jalan paralel, buku akan kita baca saat fondasi sudah berdiri"* (`defer`), perakitan berjalan tanpa jeda sedetik pun.
* **Preload Scanner** ibarat asisten logistik yang langsung melihat lembar belakang buku panduan pada detik pertama, memesan semua suku cadang kritis ke vendor via telepon, sementara mandor utama masih membaca instruksi bab pertama.

### Diagram: Eksekusi Timeline Parser vs Script Loading

```
Legend: 
[====] HTML Parsing
[....] Resource Downloading (Network)
[XXXX] Script Execution (Blocking Main Thread)

1. Synchronous Script (<script src="bundle.js">):
Main Thread: [== Parsing ==]                    [== Parsing ==]
Network:                    [.... Download ....]
Execution:                                      [XXXX Exec XXXX]

2. Defer Script (<script defer src="bundle.js">):
Main Thread: [================ Parsing ================]
Network:     [.... Download ....]                      │
Execution:                                             [XXXX Exec XXXX] (Setelah Parse)

3. Async Script (<script async src="analytics.js">):
Main Thread: [===== Parsing =====]               [===== Parsing =====]
Network:     [.... Download ....]│
Execution:                       [XXXX Exec XXXX]

4. Module Script (<script type="module" src="app.js">):
Main Thread: [================ Parsing ================]
Network:     [.... Download + Graph Parse ....]        │
Execution:                                             [XXXX Exec XXXX]
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Baseline Dokumen Modern

File dokumen dasar dengan sintaks minimal yang mematuhi standar modern:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Minimal Resilient Skeleton</title>
</head>
<body>
  <h1>Sistem Produksi Aktif</h1>
</body>
</html>
```

### 7.2. Practical Example: Production-Grade Resilient Enterprise Shell

Berikut adalah cetak biru dokumen HTML enterprise-grade yang mengimplementasikan Content Security Policy (CSP) berbasis Nonce, Subresource Integrity (SRI), Optimasi Resource Hints, Font Preloading, Anti-CLS Image wrappers, dan Responsive Image Art Direction:

```html
<!DOCTYPE html>
<html lang="id" dir="ltr" class="no-js">
<head>
  <!-- 1. Karakter Encoding & Viewport: Wajib berada di 1024 byte pertama -->
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  
  <title>Enterprise Core Architecture - Platform Portal</title>
  
  <!-- 2. Security Headers via Meta (Fallback jika reverse proxy tidak menginjeksi header) -->
  <meta http-equiv="X-Content-Type-Options" content="nosniff">
  <!-- Content Security Policy Level 3 dengan Dynamic Nonce Injection Placeholder -->
  <meta http-equiv="Content-Security-Policy" content="
    default-src 'self';
    script-src 'self' 'nonce-rAnd0mN0nce123' 'strict-dynamic';
    style-src 'self' 'nonce-rAnd0mN0nce123' https://fonts.googleapis.com;
    font-src 'self' https://fonts.gstatic.com data:;
    img-src 'self' https://images.enterprise.internal data: blob:;
    connect-src 'self' https://api.enterprise.internal https://telemetry.enterprise.internal;
    object-src 'none';
    base-uri 'self';
    form-action 'self';
    frame-ancestors 'none';
  ">

  <!-- 3. Resource Hints & Performance Directives -->
  <!-- Early DNS Resolution & TLS Handshake untuk API & Font Engine -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="dns-prefetch" href="https://telemetry.enterprise.internal">

  <!-- Preload Critical Typography (Menghilangkan FOIT/FOUT) -->
  <link rel="preload" 
        href="/assets/fonts/inter-latin-variable.woff2" 
        as="font" 
        type="font/woff2" 
        crossorigin="anonymous">

  <!-- Preload LCP Hero Image (Optimasi LCP Matrix) -->
  <link rel="preload" 
        as="image" 
        href="/assets/images/hero-dashboard-wide.webp" 
        type="image/webp" 
        fetchpriority="high"
        media="(min-width: 1024px)">

  <!-- 4. Critical Inlined CSS (Kalkulasi CSSOM Instan tanpa Blocking Network Roundtrip) -->
  <style nonce="rAnd0mN0nce123">
    :root {
      --bg-primary: #0a0c10;
      --text-primary: #f0f6fc;
      --accent: #238636;
      --surface: #161b22;
      --font-stack: 'Inter', system-ui, -apple-system, sans-serif;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html { font-family: var(--font-stack); background-color: var(--bg-primary); color: var(--text-primary); }
    body { min-height: 100vh; display: flex; flex-direction: column; text-rendering: optimizeLegibility; }
    .hero-container { position: relative; width: 100%; aspect-ratio: 16 / 9; max-height: 600px; overflow: hidden; background: var(--surface); }
    .hero-container img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }
  </style>

  <!-- 5. Asynchronous Non-blocking Stylesheet -->
  <link rel="preload" href="/assets/css/app.min.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
  <noscript><link rel="stylesheet" href="/assets/css/app.min.css"></noscript>

  <!-- 6. Production Script Loading Strategy -->
  <!-- Modern ES Module bundle -->
  <script type="module" src="/assets/js/runtime.esm.js" nonce="rAnd0mN0nce123"></script>
  
  <!-- Critical Telemetry Loader (Asynchronous, Isolated) -->
  <script async src="/assets/js/telemetry.min.js" 
          integrity="sha384-oqVuAfXRKap7fdgcCY5uykM6+R9GqQ8K/uxy9rx7HNQlGYl1kPzQho1wx4JwY8wC" 
          crossorigin="anonymous" 
          nonce="rAnd0mN0nce123"></script>

  <!-- Modern Dynamic Polyfill / Detection -->
  <script nonce="rAnd0mN0nce123">
    document.documentElement.classList.remove('no-js');
    document.documentElement.classList.add('js');
  </script>
</head>
<body>
  <!-- Semantic Accessibility Landmark: Skip Link -->
  <a href="#main-content" class="visually-hidden">Lewati ke konten utama</a>

  <header role="banner" class="app-header">
    <nav role="navigation" aria-label="Navigasi Utama">
      <ul>
        <li><a href="/dashboard" aria-current="page">Dashboard</a></li>
        <li><a href="/analytics">Analytics</a></li>
        <li><a href="/settings">Sistem</a></li>
      </ul>
    </nav>
  </header>

  <main id="main-content" role="main">
    <section class="hero-container" aria-labelledby="hero-heading">
      <h1 id="hero-heading" class="visually-hidden">Performa Analitik Real-Time</h1>
      
      <!-- Anti-CLS Image Rendering dengan srcset, sizes, dan decoding async -->
      <picture>
        <source media="(min-width: 1024px)" srcset="/assets/images/hero-dashboard-wide.webp" type="image/webp">
        <source media="(min-width: 640px)" srcset="/assets/images/hero-dashboard-medium.webp" type="image/webp">
        <img src="/assets/images/hero-dashboard-small.jpg" 
             alt="Grafik Metrik Produksi Menunjukkan Tingkat Ketersediaan 99.99%" 
             width="1280" 
             height="720" 
             fetchpriority="high" 
             decoding="async" 
             loading="eager">
      </picture>
    </section>

    <!-- Island Architecture Hydration Target Marker -->
    <section id="interactive-grid-island" 
             data-hydration-strategy="visible" 
             data-component="SystemMetricsGrid" 
             aria-live="polite">
      <!-- Fallback SSR Skeleton (Server-Rendered Markup) -->
      <div class="skeleton-wrapper">
        <div class="skeleton-box" aria-hidden="true">Memuat metrik sistem terkini...</div>
      </div>
    </section>
  </main>

  <footer role="contentinfo">
    <p>&copy; 2026 Enterprise Global Corp. Seluruh Hak Cipta Dilindungi Undang-Undang.</p>
  </footer>
</body>
</html>
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Re-arsitektur Shell HTML Transaksi Toko E-Commerce Skala Global
* **Konteks**: Platform e-commerce dengan 80 juta *Monthly Active Users* (MAU) mengalami rasio *bounce rate* sebesar 34% pada koneksi mobile (3G/4G lambat).
* **Akar Masalah (Root-Cause Profiling via Chrome DevTools Tracing)**:
  1. File `index.html` dikirim sebagai berkas statis monolitik yang memanggil 12 skrip pihak ketiga sinkron di dalam tag `<head>` tanpa `async` atau `defer`.
  2. Browser parser mengalami *thread blocking* selama rata-rata 1.8 detik sebelum elemen `<body>` diparsing.
  3. Hero image banner produk memicu lonjakan CLS (skor: 0.42) karena tidak adanya reservasi dimensi CSS/atribut `width`-`height`.
  4. TTFB (Time to First Byte) cepat (80ms), namun First Contentful Paint (FCP) berada pada 3.9 detik, dan Largest Contentful Paint (LCP) pada 5.6 detik.

### Solusi Arsitektural:
1. **Transisi ke Edge-Rendered Streaming HTML**:
   * Memanfaatkan Cloudflare Workers / Node.js Stream untuk mengirim *HTML Shell Head* secara instan pada milidetik ke-15.
   * Konten keranjang belanja dan rekomendasi produk dialirkan (*streamed*) menggunakan tag `<template>` tersembunyi yang ditransklusikan ke layout utama menggunakan vanilla JavaScript micro-hydration.
2. **Orkestrasi Skrip & Nonce-Based CSP**:
   * Memindahkan seluruh analitik dan log pihak ketiga menggunakan `<script async defer>`.
   * Skrip aplikasi inti diubah menjadi `<script type="module">`.
   * Menambahkan header keamanan `Cross-Origin-Opener-Policy: same-origin` dan `Cross-Origin-Embedder-Policy: require-corp` untuk isolasi memori penuh.
3. **Penerapan Atribut Dimensi & Prioritas**:
   * Seluruh gambar wajib menyertakan rasio aspek via CSS `aspect-ratio` atau atribut eksplisit `width="w"` dan `height="h"`.
   * Menambahkan `fetchpriority="high"` secara khusus pada gambar pertama viewport LCP.

### Dampak Metrik Produksi:
* **FCP**: Turun dari 3.9 detik menjadi **0.8 detik** (-79.4%).
* **LCP**: Turun dari 5.6 detik menjadi **1.3 detik** (-76.7%).
* **CLS**: Turun dari 0.42 menjadi **0.002** (Lolos batas toleransi Google Search Core Web Vitals).
* **Konversi Pembayaran (Checkout Rate)**: Meningkat **14.2%** dalam 30 hari pasca-rilis.

---

## 9. Trade-offs

Setiap keputusan perancangan HTML melibatkan konsekuensi trade-off teknik:

```
[Inlined CSS/Critical Assets] ◄──────────────► [External Assets with Caching]
   - Keuntungan: FCP Instan (0 RTT)               - Keuntungan: Sangat optimal via HTTP Cache
   - Biaya: HTML Payload Membengkak               - Biaya: Wajib 1-2 RTT di koneksi baru

[Preload Aggressif (<link rel=preload>)] ◄──► [Lazy Discovery Parser Default]
   - Keuntungan: Aset kritis unduh lebih cepat    - Keuntungan: Menghemat bandwidth seluler
   - Biaya: Risiko saturasi bandwidth             - Biaya: Penundaan eksekusi elemen LCP
```

### Matriks Trade-off

| Keputusan Arsitektural | Keuntungan Utama | Biaya / Risiko | Mitigasi yang Direkomendasikan |
| :--- | :--- | :--- | :--- |
| **Inlining Critical CSS di `<head>`** | FCP sangat cepat; 0 RTT untuk evaluasi CSSOM. | Dokumen HTML tidak dapat di-cache secara granular; byte payload membengkak jika berlebihan. | Batasi critical inlined CSS maksimal **14-20 KB** (batas ambang initial TCP slow-start window / CWND). |
| **Agresif `<link rel="preload">`** | Mengunduh sub-resource (misal: font, LCP image) mendahului parser reguler. | Bersaing memperebutkan bandwidth dengan aset kritis lain; jika salah target (`as` salah), terjadi *double fetching*. | Preload maksimal 2-3 aset paling kritis; gunakan Chrome Coverage Tool untuk validasi. |
| **Streaming HTML via SSR** | TTFB ke FCP berlangsung kontinu; user segera melihat kerangka halaman. | Server memegang koneksi HTTP terbuka lebih lama; kompleksitas arsitektur edge/proxy meningkat. | Terapkan *timeout fallback* dan integrasikan CDN edge caching untuk *dynamic streams*. |
| **Strict CSP Level 3 (`nonce-based`)**| Mengeliminasi 99% celah injeksi XSS tradisional. | Mengharuskan infrastruktur SSR menginjeksi kriptografis unik per-request; menghambat inline script statis. | Gunakan middleware edge proxy untuk injeksi token dinamis otomatis ke HTML template. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Kesalahan Preload Font tanpa `crossorigin`
* **Gejala**: Font diunduh **dua kali** oleh browser (terlihat ganda di DevTools Network Tab).
* **Penyebab**: Spesifikasi font web mengharuskan font diambil via anonymous CORS mode. Menuliskan `<link rel="preload" as="font" href="font.woff2">` tanpa atribut `crossorigin` membuat Preload Scanner mengunduh via kredensial umum, lalu ditolak oleh parser CSS yang menuntut mode CORS.
* **Perbaikan**:
  ```html
  <!-- SALAH -->
  <link rel="preload" href="/fonts/inter.woff2" as="font" type="font/woff2">

  <!-- BENAR -->
  <link rel="preload" href="/fonts/inter.woff2" as="font" type="font/woff2" crossorigin="anonymous">
  ```

### 2. Mengabaikan Nilai Atribut Dimensi pada Tag Gambar (CLS Trigger)
* **Gejala**: Halaman melompat ke bawah saat gambar selesai dimuat (*Layout Shift* tinggi).
* **Penyebab**: Browser tidak dapat menghitung alokasi ruang (*layout box placeholder*) sebelum berkas gambar terunduh.
* **Perbaikan**: Selalu sediakan atribut `width` dan `height` intrinsik atau deklarasikan properti CSS `aspect-ratio`:
  ```html
  <!-- SALAH: Tidak memiliki dimensi eksplisit -->
  <img src="banner.webp" alt="Promo">

  <!-- BENAR: Browser mengkalkulasi aspect-ratio 16:9 secara instan -->
  <img src="banner.webp" width="1600" height="900" alt="Promo" style="width: 100%; height: auto;">
  ```

### 3. Syntax Quirks Mode Trigger
* **Gejala**: Tampilan CSS rendering acak-acakan (*box-model* kalkulasi lebar rusak).
* **Penyebab**: Ada karakter, spasi, atau komentar sebelum tag `<!DOCTYPE html>`. Browser Chromium, Safari, dan Firefox akan jatuh ke *Quirks Mode* alih-alih *Standards Mode*.
* **Perbaikan**: Baris paling pertama, karakter byte index 0 wajib diisi deklarasi:
  ```html
  <!DOCTYPE html>
  ```

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebagai *Quality Gate* pada pipeline CI/CD sebelum merilis template HTML ke produksi:

### Keamanan (Security)
- [ ] Tag `<!DOCTYPE html>` berada pada posisi paling awal tanpa byte tersembunyi/BOM.
- [ ] Deklarasi `<meta charset="utf-8">` berada di dalam 1024 byte pertama `<head>`.
- [ ] Atribut CSP dideklarasikan via HTTP Header (disarankan) atau fallback `<meta http-equiv="...">`.
- [ ] Seluruh skrip pihak ketiga (CDN) wajib menyertakan atribut `integrity` (SRI) dan `crossorigin`.
- [ ] Seluruh tautan `<a target="_blank">` menyertakan `rel="noopener noreferrer"` secara eksplisit (mencegah eksploitasi `window.opener`).

### Performa & Resource Loading
- [ ] Tag `<meta name="viewport">` dideklarasikan dengan `width=device-width, initial-scale=1.0`.
- [ ] Seluruh skrip aplikasi menggunakan atribut `defer` atau `type="module"`. Tidak ada script blocking sinkron di `<head>`.
- [ ] Tidak lebih dari 3 entri `<link rel="preload">` aktif secara bersamaan pada *initial view*.
- [ ] Font lokal dimuat dengan format `.woff2` dan dideklarasikan dengan `font-display: swap` (atau `optional`).
- [ ] Elemen gambar LCP utama dideklarasikan dengan `fetchpriority="high"` dan `loading="eager"`.
- [ ] Elemen gambar di bawah *fold* (*below the fold*) menggunakan atribut native `loading="lazy"`.

### Semantik & Aksesibilitas
- [ ] Elemen `<html>` menyertakan atribut bahasa yang valid (misal: `lang="id"`).
- [ ] Terdapat satu dan hanya satu elemen `<main>` per halaman.
- [ ] Hierarki heading (`<h1>` sampai `<h6>`) terurut secara logis tanpa lompatan tingkat.
- [ ] Tautan lompatan navigasi (*Skip to main content*) tersedia di urutan pertama `<body>`.

---

## 12. Hands-on Practice

Buatlah folder praktikum di repositori lokal Anda:
`mkdir -p hands-on/m02/ && cd hands-on/m02/`

### File 1: `server.js` (Simulasi Node.js Streaming Server)
Simulasi web server HTTP/1.1 yang mengalirkan (*stream*) HTML secara bertahap untuk mendemonstrasikan perilaku *Speculative Preload Scanner* dan *Streaming SSR*.

```javascript
// hands-on/m02/server.js
const http = require('http');

const server = http.createServer((req, res) => {
  if (req.url === '/') {
    res.writeHead(200, {
      'Content-Type': 'text/html; charset=UTF-8',
      'Transfer-Encoding': 'chunked',
      'X-Content-Type-Options': 'nosniff'
    });

    // CHUNK 1: Mengirimkan Dokumen Head Kritis
    res.write(`<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Streaming HTML Lab</title>
  <style>
    body { font-family: sans-serif; background: #121212; color: #fff; padding: 2rem; }
    .card { background: #1e1e1e; border-radius: 8px; padding: 1.5rem; margin-top: 1rem; border: 1px solid #333; }
    .loader { color: #888; font-style: italic; }
  </style>
  <!-- Skrip async untuk demonstrasi paralelisme -->
  <script async src="/slow-script.js"></script>
</head>
<body>
  <h1>Laboratorium Streaming HTML Kinerja Tinggi</h1>
  <p>Status: Bagian Head & Shell Pertama Terkirim Cepat...</p>
`);

    // CHUNK 2: Simulasi Server Memproses Database Berat (Jeda 2 Detik)
    setTimeout(() => {
      res.write(`
  <main>
    <div class="card">
      <h2>Data Transaksi Penjualan (Hasil Query Berat)</h2>
      <p>Data metrik berhasil di-render dari server via edge chunking stream.</p>
    </div>
  </main>
`);

      // CHUNK 3: Menyelesaikan Dokumen HTML
      setTimeout(() => {
        res.write(`
  <footer>
    <p><small>&copy; 2026 Production Runtime Test Bed</small></p>
  </footer>
</body>
</html>`);
        res.end();
      }, 1000);

    }, 2000);

  } else if (req.url === '/slow-script.js') {
    // Simulasi delay eksekusi skrip jaringan
    setTimeout(() => {
      res.writeHead(200, { 'Content-Type': 'application/javascript' });
      res.end(`console.log('Slow script successfully loaded and executed at:', performance.now());`);
    }, 1500);
  } else {
    res.writeHead(404);
    res.end();
  }
});

server.listen(3000, () => {
  console.log('Server berjalan di http://localhost:3000');
});
```

### File 2: Uji Performa Parsing
1. Jalankan server:
   ```bash
   node server.js
   ```
2. Buka peramban Google Chrome, buka **Developer Tools (F12)** -> Tab **Performance**.
3. Pastikan throttling CPU diatur ke **4x slowdown** dan Network diatur ke **Fast 3G**.
4. Lakukan perekaman (*record*) saat mengakses `http://localhost:3000`.
5. Amati pada grafik waterfall: Elemen `<h1>` muncul sebelum Server Chunk 2 tiba. Skrip `/slow-script.js` diunduh secara paralel tanpa menahan visual awal.

---

## 13. Exercise

### Level Easy
Ubah dokumen HTML warisan di bawah ini agar memenuhi standar modern:
* Ubah skrip sinkron agar tidak memblokir parsing.
* Tambahkan atribut yang mengamankan navigasi keluar.
* Atur meta viewport agar responsif di platform mobile.

```html
<!-- DOKUMEN AWAL (DILARANG MENGGUNAKAN INI DI PRODUKSI) -->
<html>
<head>
  <title>Legacy Page</title>
  <script src="https://cdn.example.com/app.js"></script>
</head>
<body>
  <a href="https://partner.com" target="_blank">Akses Eksternal</a>
</body>
</html>
```

### Level Medium
Diberikan situasi di mana LCP halaman e-commerce adalah gambar hero dinamis berukuran besar. 
Rancang tag `<picture>` yang:
1. Menyediakan format alternatif Modern WebP dan AVIF beserta fallback JPEG standar.
2. Menyediakan resolusi adaptif untuk layar Desktop (1920px), Tablet (768px), dan Handphone (375px).
3. Memastikan parser mengalokasikan prioritas unduhan tertinggi.
4. Mencegah pergeseran tata letak (CLS) tanpa menggunakan framework CSS eksternal.

### Level Hard
Buat dokumen HTML yang mengimplementasikan arsitektur CSP Level 3 tanpa atribut unsafe:
1. Terapkan CSP meta tag yang hanya mengizinkan eksekusi inline script yang memiliki atribut `nonce="XYZ123"`.
2. Gunakan directive `'strict-dynamic'` untuk mengevaluasi script dependensi lanjutan.
3. Definisikan fallback skrip modular menggunakan pola kombinasi:
   * `<script type="module">` untuk browser modern.
   * `<script nomodule defer>` untuk legacy browser.
4. Tunjukkan secara tepat bagaimana script legacy diisolasi agar tidak dieksekusi dobel pada peramban modern.

---

## 14. Challenge

### Studi Kasus: Re-engineering Zero-CLS Dynamic Dashboard Shell
**Deskripsi Skenario**:
Anda adalah Principal Web Architect pada platform trading saham institusional. 
Halaman antarmuka beranda memuat data widget interaktif yang berukuran dinamis. 
Ketika sistem streaming web socket mulai memompa data grafik, browser klien mengalami freeze berulang dan nilai layout shift (CLS) meroket hingga 0.85, menyebabkan insiden pengguna salah klik tombol *Sell* alih-alih *Buy*.

**Spesifikasi Teknis Tantangan**:
1. Buat dokumen HTML monolitik murni (`index.html`) tanpa dependensi build-tool yang mengeliminasi masalah di atas.
2. Buat mekanisme penataan kerangka (*CSS Grid intrinsic scaffolding*) yang mengunci rasio aspek area kerja komponen grafik saham sebelum runtime JavaScript diinisialisasi.
3. Rancang struktur semantik tabel order book trading dengan tag native HTML (`table`, `caption`, `thead`, `tbody`, `tr`, `th scope="col"`) yang memenuhi level *WAI-ARIA Accessibility Authoring Practices*.
4. Konfigurasikan skrip isolasi runtime menggunakan *Web Worker* di dalam tag `<script type="text/worker" id="worker">` yang diekstrak menjadi Object URL Blob dari dalam dokumen HTML itu sendiri tanpa pemanggilan file eksternal tambahan.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic
1. Apa fungsi utama thread *Preload Scanner* pada browser modern saat main thread terhenti oleh eksekusi skrip sinkron?
2. Mengapa tag `<meta charset="utf-8">` wajib ditempatkan di dalam 1024 byte pertama dari berkas HTML?
3. Sebutkan perbedaan perilaku eksekusi antara skrip dengan atribut `defer` dan skrip bertipe `type="module"`.
4. Mengapa atribut `crossorigin="anonymous"` wajib disertakan pada elemen `<link rel="preload" as="font">` meskipun font berada pada origin yang sama?
5. Apa konsekuensi teknis jika dokumen HTML tidak mendeklarasikan tag `<!DOCTYPE html>` pada baris pertamanya?

### Bagian B: Intermediate
6. Jelaskan bagaimana mekanisme *Speculative Tree Construction* menangani kesalahan struktur HTML seperti elemen block `<div>` yang disematkan secara tidak sah di dalam elemen inline `<span>`!
7. Dalam kondisi jaringan buruk, mengapa penggunaan `<link rel="preload">` yang berlebihan (over-preloading) justru dapat merusak skor Largest Contentful Paint (LCP)?
8. Bagaimanakah cara kerja atribut `fetchpriority="high"` mempengaruhi antrean resource scheduler pada browser berbasis Blink?
9. Apa perbedaan mendasar antara directive CSP `script-src 'nonce-...'` dibanding `script-src 'hash-...'` dalam siklus pembaruan dokumen streaming SSR dinamis?
10. Mengapa atribut `decoding="async"` pada tag `<img>` dapat membebaskan *Main Thread* browser dari potensi frame dropping saat pengguna melakukan scroll cepat?

### Bagian C: Skenario Kasus Produksi
11. **Skenario 1**: Sebuah tim engineering mendapati bahwa berkas CSS pihak ketiga mereka mengalami kegagalan parsing intermiten di jaringan publik. Setelah diinspeksi, sebuah ISP lokal menyuntikkan (inject) skrip iklan ke dalam berkas CSS tersebut. Konfigurasi HTML apa yang harus dipasang untuk secara otomatis membatalkan pemuatan berkas yang telah termodifikasi tersebut?
12. **Skenario 2**: Analisis DevTools Performance menunjukkan LCP platform media berita Anda tertunda selama 2.1 detik karena aset gambar utama berada di akhir markup dokumen. Anda dilarang memindahkan posisi tag `<img>` tersebut karena hierarki komponen template engine. Solusi tingkat dokumen apa yang dapat Anda terapkan pada blok `<head>` untuk mengatasi masalah keterlambatan penemuan (*discovery latency*) ini?
13. **Skenario 3**: Platform perbankan Anda diwajibkan mengisolasi seluruh memori tab browser dari potensi serangan Spectre atau XS-Leaks lintas dokumen. Header/meta dokumen isolasi origin apa yang wajib dideklarasikan secara serentak agar fitur memori canggih seperti `SharedArrayBuffer` dapat diaktifkan kembali secara aman?

---

## 16. Summary

1. **HTML sebagai Execution Engine**: Dokumen HTML bukan sekadar data representasional pasif; ia bertindak sebagai manifes penjadwalan jaringan (*network scheduling manifesto*) yang mengendalikan alokasi thread CPU, antrean socket koneksi, dan layout boundary browser.
2. **Kompilasi Streaming & Parsing**: Browser memproses token HTML secara bertahap saat byte tiba di soket jaringan. Memahami pemisahan antara thread *Main Parser* dan *Preload Scanner* adalah kunci mutlak dalam merekayasa halaman dengan nilai Web Vitals prima (FCP & LCP rendah).
3. **Orkestrasi Asinkron Deterministi**: Penggunaan skrip sinkron di `<head>` merupakan antipattern terburuk dalam arsitektur web modern. Penggunaan `defer`, `type="module"`, dan `fetchpriority` memungkinkan pemuatan aset secara non-blocking dan terprediksi.
4. **Resiliensi & Zero Trust Security**: Integrasi ketat antara Content Security Policy berbasis cryptographic nonce, Subresource Integrity (SRI), dan atribut relasional pengaman merupakan garis pertahanan terdepan dalam melindungi ekosistem aplikasi front-end skala industri dari vektor serangan siber modern.