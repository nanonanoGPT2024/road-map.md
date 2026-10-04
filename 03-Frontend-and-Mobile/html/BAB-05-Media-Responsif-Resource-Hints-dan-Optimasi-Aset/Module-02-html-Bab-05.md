# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Kategori: 03-Frontend-and-Mobile
### Topik: HTML
#### BAB-05: Media Responsif, Resource Hints, dan Optimasi Aset
##### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonfigurasi strategi resource hints tingkat lanjut (`dns-prefetch`, `preconnect`, `preload`, `prefetch`, `modulepreload`, serta Speculation Rules API) untuk memotong RTT (*Round Trip Time*) pada *Critical Rendering Path* (CRP).
- Merancang dan mengimplementasikan arsitektur gambar responsif multi-format modern (`AVIF`, `WebP`, fallback `JPEG`/`PNG`) menggunakan elemen `<picture>`, atribut `srcset`, dan `sizes` matematis yang memitigasi *Cumulative Layout Shift* (CLS) ke angka `< 0.05`.
- Mengintegrasikan mekanisme adaptif berbasis konektivitas dan preferensi pengguna via HTTP *Client Hints* (`Sec-CH-Width`, `Sec-CH-DPR`, `Save-Data`) dan media queries CSS.
- Mendiagnosis degradasi performa aset web, menganalisis *waterfall chart*, dan memvalidasi Core Web Vitals (khususnya LCP dan CLS) pada skala jutaan *request* per hari.
- Merancang arsitektur pipeline pemrosesan aset *edge-to-client* dengan sinkronisasi header HTTP caching (`immutable`, `stale-while-revalidate`) dan integrasi Content Delivery Network (CDN).

---

### 2. Prerequisites

Peserta wajib menguasai fondasi berikut sebelum memulai modul ini:
- Pemahaman mendalam tentang siklus hidup peramban web: parsing HTML tokens, konstruksi DOM, CSSOM, Render Tree, Layout/Reflow, dan Paint/Composite.
- Protokol Jaringan: Dasar-dasar TCP Handshake, TLS Negotiation, HTTP/1.1 pipelining limitations, HTTP/2 multiplexing, dan HTTP/3 QUIC stream transport.
- Format Kompresi Data: Perbedaan algoritma *lossy* vs *lossless*, DCT (*Discrete Cosine Transform*), struktur WebP berbasis VP8/VP8L, dan format AVIF berbasis AV1 intra-frame coding.
- Penguasaan dasar metrik Core Web Vitals (LCP, INP, CLS) serta penggunaan instrumen profiling Chrome DevTools (Network tab, Performance tab, Coverage tab, dan Lighthouse).

---

### 3. Concept & Internal Architecture

#### 3.1 Browser Speculative Parser & Resource Priority Matrix
Saat peramban melakukan *streaming* chunk HTML dari jaringan, *HTML Parser* utama membaca byte stream secara sekuensial. Jika parser menemukan tag eksternal (seperti `<script src="...">` tanpa `defer`/`async` atau stylesheet sinkron), proses parsing DOM utama akan terblokir (*parser-blocking*).

Untuk mengatasi inefisiensi ini, peramban modern menerapkan sub-engine paralel: **Speculative Parser** (atau *Preload Scanner*).
*Preload Scanner* berjalan di thread terpisah mendahului HTML parser utama untuk mencari URL aset esensial (`<link rel="stylesheet">`, `<script>`, `<img>`, font). Aset-aset ini diinjeksikan langsung ke dalam **Resource Fetch Scheduler** peramban.

Setiap aset diberikan prioritas internal (*Fetch Priority*) oleh mesin Blink/Chromium:

| Resource Type | Kondisi Penemuan | Default Priority Chromium |
|---|---|---|
| Main HTML Document | Navigasi awal | **VeryHigh** |
| CSS Stylesheet | Ditemukan di dalam `<head>` | **VeryHigh** |
| CSS Stylesheet | Menggunakan media query non-matching | **Lowest** |
| Font File | Dinyatakan via `@font-face` atau `<link rel="preload">` | **VeryHigh** |
| Script (Sync) | Ditemukan di dalam `<head>` sebelum stylesheet | **High** |
| Script (Sync) | Ditemukan setelah CSS di `<head>` | **Medium** (terhambat CSSOM) |
| Script (async/defer) | Di mana saja | **Low** |
| Images (Viewport) | Gambar pertama tanpa `loading="lazy"` | **High** |
| Images (General) | Di dalam markup standar, default | **Low** |
| Images (`loading="lazy"`) | Di bawah fold (belum mendekati ambang intersection) | **Lowest** |

Atribut `fetchpriority="high"` atau `fetchpriority="low"` memodifikasi penempatan request pada queue internal scheduler ini, memintas urutan antrean alami tanpa mengubah sifat eksekusi sinkron/asinkron dari skrip atau aset terkait.

#### 3.2 Resource Hints Engine: Lifecycle & Socket Pool Allocation
Resource hints menginstruksikan modul jaringan (*network stack*) peramban sebelum dokumen HTML atau kode JavaScript mereferensikan aset secara eksplisit:

```
[ DNS Lookup ] -> [ Initial TCP Handshake (SYN-ACK) ] -> [ TLS Negotiation (Client/Server Hello) ] -> [ HTTP Request/Response ]
     ^                           ^                                      ^
dns-prefetch               preconnect                               preconnect (complete)
```

1. **`dns-prefetch`**: Menginstruksikan OS DNS resolver untuk memetakan domain ke alamat IP. Hanya mengonsumsi sedikit bandwidth dan memori (menyimpan record A/AAAA pada cache DNS internal peramban selama TTL berlaku).
2. **`preconnect`**: Mengeksekusi DNS lookup + TCP 3-way handshake + TLS negotiation (1 RTT untuk HTTP/1.1 dan HTTP/2; 0-RTT/1-RTT untuk HTTP/3 QUIC). Menjaga socket tetap terbuka dalam *Socket Pool* peramban selama 10 detik default sebelum ditutup jika tidak ada transmisi data. Mengonsumsi memori dan slot koneksi TLS server, sehingga penggunaannya harus dibatasi secara ketat (< 3-4 domain per halaman).
3. **`preload`**: Mengunduh aset secara deterministik dan menyimpannya di memory cache peramban (*Preload Cache*) dengan prioritas yang ditentukan. Jika aset yang di-preload tidak dikonsumsi oleh dokumen dalam kurun waktu 3-5 detik, Chromium akan mengeluarkan warning di konsol: *"The resource was preloaded using link preload but not used within a few seconds from the window's load event."*
4. **`modulepreload`**: Khusus ES Modules (`<script type="module">`). Mengunduh file JavaScript, melakukan parsing token, dan menempatkan modul pada *Module Map* (V8 compilation phase) secara rekursif jika dependensi tree terpetakan.
5. **`prefetch`**: Mengunduh aset yang kemungkinan besar dibutuhkan pada navigasi berikutnya (*next page view*). Disimpan di *Disk Cache* atau *HTTP Cache* pada level prioritas `Lowest`. Diabaikan jika pengguna berada pada mode Data Saver atau jaringan seluler berkecepatan rendah.
6. **Speculation Rules API**: Spesifikasi W3C modern untuk melakukan prerendering sub-resource atau full page prerender secara aman dan terkontrol via JSON script block.

#### 3.3 Anatomi Algoritma Responsive Image Selection Engine
Ketika peramban mengevaluasi:
```html
<picture>
  <source type="image/avif" srcset="img-400.avif 400w, img-800.avif 800w" sizes="(max-width: 600px) 100vw, 50vw">
  <source type="image/webp" srcset="img-400.webp 400w, img-800.webp 800w" sizes="(max-width: 600px) 100vw, 50vw">
  <img src="img-fallback.jpg" alt="..." width="800" height="600" loading="lazy" decoding="async">
</picture>
```

Mesin peramban mengeksekusi algoritma berikut:
1. **MIME Type Negotiation**: Memeriksa tag `<source>` pertama. Jika decoder AVIF terpasang dan aktif di engine, peramban memilih source tersebut dan mengabaikan source berikutnya.
2. **Viewport & Density Calculus**:
   - Menghitung lebar viewport aktual (misal: `390px` pada iPhone 14 Pro).
   - Mengevaluasi media condition pada atribut `sizes`: `(max-width: 600px)` bernilai `true`, sehingga ukuran slot tampilan slot dihitung sebagai `100vw` = `390px`.
   - Mengambil Device Pixel Ratio (DPR) perangkat: `window.devicePixelRatio` = `3`.
   - Menghitung kebutuhan piksel fisik aktual: $W_{target} = 390 \times 3 = 1170 \text{ px}$.
3. **Candidate Matching**: Peramban membandingkan $W_{target}$ (1170) terhadap daftar kandidat `srcset` (`400w`, `800w`). Peramban memilih kandidat yang meminimalkan rasio sampling error/kebutuhan resolusi (dalam hal ini kandidat terbesar yang tersedia: `800w`, atau mengunduh resolusi yang paling mendekati preferensi bandwidth jaringan saat ini).
4. **Layout Reservation (Mitigasi CLS)**: Peramban membaca rasio aspek intrinsik dari atribut `width="800"` dan `height="600"` pada tag fallback `<img>`. CSS engine secara otomatis menghitung `aspect-ratio: 800 / 600 = 1.333`. Meskipun gambar aktual belum diunduh (terisolasi oleh `loading="lazy"`), kotak tata letak (*layout box*) telah dialokasikan secara instan pada fase Layout. Pergeseran tata letak (CLS) bernilai $0.00$.

---

### 4. Why & What

| Mekanisme Tradisional | Masalah & Hambatan Skalabilitas | Pendekatan Modern Enterprise | Solusi Teknis & Keuntungan |
|---|---|---|---|
| Monolithic `<img>` Tag (`<img src="hero.jpg">`) | Mengunduh file resolusi desktop (2MB+) di perangkat seluler; bandwidth terbuang, FCP/LCP membengkak. | Multi-tier `<picture>` + `srcset` + `sizes` | Mengirim byte optimal sesuai DPR dan viewport, pemotongan ukuran transfer hingga 70-85%. |
| Pemuatan font via `@import` di CSS | Rantai dependensi berantai (*waterfall chain*): HTML -> CSS -> @import -> WOFF2 (3-4 RTT delays). Terjadi FOIT/FOUT. | `<link rel="preload" as="font" type="font/woff2" crossorigin>` | Bypass unduhan CSSOM; font mulai diunduh paralel bersamaan dengan parser membaca `<head>`. |
| Semua aset di-load sinkron di awal | Menghabiskan thread pool jaringan TCP peramban (batas 6 koneksi simultan per host di HTTP/1.1), LCP tertahan. | Resource Prioritization Matrix (`fetchpriority`, `loading="lazy"`, Speculation Rules) | Alokasi bandwidth penuh untuk aset critical (LCP), penundaan aset di luar viewport. |
| Negosiasi format manual via JavaScript | Eksekusi JS memblokir main thread, memicu FOUC (*Flash of Unstyled Content*) atau CLS saat DOM diinjeksi. | Deklaratif HTML `<picture>` + Client Hints via HTTP Header | Keputusan rendering diselesaikan langsung oleh parser C++ internal peramban sebelum eksekusi JS. |

---

### 5. How (Workflow Detail)

Berikut adalah diagram alur keputusan transmisi aset dari Client Browser menuju Server/CDN:

```
                  +--------------------------------+
                  |  Client Parser Engine Membaca  |
                  |          HTML Stream           |
                  +---------------+----------------+
                                  |
                                  v
                  +--------------------------------+
                  |  Preload Scanner Mendeteksi    |
                  |     <link rel="preload">       |
                  +---------------+----------------+
                                  |
               +------------------+------------------+
               |                                     |
               v                                     v
     [ Resource: Font ]                     [ Resource: LCP Image ]
               |                                     |
    Harus ada atribut                      Gunakan 'fetchpriority="high"'
    crossorigin="anonymous"                 Hindari loading="lazy"
               |                                     |
               +------------------+------------------+
                                  |
                                  v
                  +--------------------------------+
                  | Evaluasi Algoritma <picture>   |
                  | - Validasi tipe MIME           |
                  | - Kalkulasi Media Query sizes  |
                  | - Pemilihan kandidat srcset    |
                  +---------------+----------------+
                                  |
                                  v
                  +--------------------------------+
                  | Kirim HTTP Request ke Edge CDN |
                  | Header: Accept, Sec-CH-Width   |
                  +---------------+----------------+
                                  |
       +--------------------------+--------------------------+
       | Cache HIT di Edge CDN                               | Cache MISS
       v                                                     v
+-------------------------------+             +-------------------------------+
| Kembalikan Binary Terkompresi |             | Serverless Image Optimizer    |
| (AVIF/WebP) + Cache-Control   |             | On-The-Fly Resizing & Convert |
+-------------------------------+             +---------------+---------------+
                                                              |
                                                              v
                                              +-------------------------------+
                                              | Simpan di Object Storage +    |
                                              | Cache Edge CDN                |
                                              +-------------------------------+
```

---

### 6. Analogy & Diagram ASCII

#### 6.1 Analogi Operasional
Bayangkan Anda adalah seorang koki di restoran berbintang Michelin:
- **Tanpa Resource Hints**: Anda menunggu pelanggan duduk, memesan steak, baru kemudian Anda menyuruh staf pergi ke pasar membeli daging (DNS), memotongnya (TCP/TLS), dan memasaknya. Waktu tunggu pelanggan sangat lama (High Latency).
- **`preconnect`**: Anda sudah menelepon peternak daging langganan, memesan tempat di jalur cepat, dan memastikan staf Anda sudah siap di kasir toko sebelum pesanan tiba.
- **`preload`**: Daging steak wagyu terbaik sudah dikeluarkan dari lemari es dan diletakkan di meja persiapan Anda karena 99% kemungkinan menu tersebut pasti dipesan oleh tamu VIP yang sudah reservasi.
- **`prefetch`**: Saat tamu sedang memakan hidangan utama, staf Anda mulai menyiapkan bahan untuk hidangan penutup yang kemungkinan besar akan dipesan berikutnya.
- **Responsive Images**: Anda menyajikan porsi kecil untuk anak-anak (Mobile DPR 1) dan porsi lengkap untuk atlet (Desktop DPR 3), bukan memberikan porsi katering pesta 10 kg kepada setiap orang yang datang sendirian.

#### 6.2 Diagram Waterfall Performa CRP
```
WAKTU (ms) -> 0ms      100ms     200ms     300ms     400ms     500ms     600ms
---------------------------------------------------------------------------------
TANPA OPTIMASI:
HTML Request   |======|
HTML Parse            |======|
main.css                     |======|
Hero Image (Wait CSS)               |==========================| (LCP: ~600ms)
WOFF2 Font (Wait CSSOM)                    |===================| (FOIT)

DENGAN OPTIMASI:
HTML Request   |======|
Preconnect CDN |===|
Preload Font   |=============|
Preload Hero   |===================| (fetchpriority="high")      (LCP: ~280ms)
HTML Parse            |======|
main.css                     |======|
Hero Render                              |* LCP COMPLETE (280ms)
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Deklarasi Preload dan Fallback Terstruktur
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Simple Resource Hints & Responsive Media</title>

  <!-- Preconnect ke origin font pihak ketiga -->
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

  <!-- Preload Critical CSS font (wajib crossorigin meskipun satu origin) -->
  <link rel="preload" href="/fonts/inter-latin-var.woff2" as="font" type="font/woff2" crossorigin>
</head>
<body>
  <!-- Responsive Image dengan explicit dimension untuk mengunci layout -->
  <picture>
    <source srcset="/img/coffee-small.webp 480w, /img/coffee-large.webp 800w" 
            sizes="(max-width: 600px) 480px, 800px" 
            type="image/webp">
    <img src="/img/coffee-large.jpg" 
         alt="Secangkir kopi panas di atas meja kayu" 
         width="800" 
         height="533" 
         loading="lazy" 
         decoding="async">
  </picture>
</body>
</html>
```

#### 7.2 Practical Enterprise Example: Komponen Hero Section E-Commerce
Struktur HTML kelas produksi yang dioptimalkan untuk skor LCP 100%, CLS 0, dan integrasi Speculation Rules API.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Enterprise Asset Optimization</title>

  <!-- 1. Resource Hints: Koneksi ke Static Asset CDN & Image Optimizer Edge -->
  <link rel="preconnect" href="https://assets.tokoweb.com">
  <link rel="dns-prefetch" href="https://analytics.tokoweb.com">

  <!-- 2. Preload Font Primer (Wajib CORS compliant) -->
  <link rel="preload" 
        href="https://assets.tokoweb.com/fonts/inter-display.woff2" 
        as="font" 
        type="font/woff2" 
        crossorigin="anonymous">

  <!-- 3. Preload Critical LCP Hero Image (Media-Query Conditional Preload) -->
  <link rel="preload" 
        as="image" 
        href="https://assets.tokoweb.com/hero/hero-mobile.avif" 
        type="image/avif" 
        media="(max-width: 767px)" 
        fetchpriority="high">
  
  <link rel="preload" 
        as="image" 
        imagesrcset="https://assets.tokoweb.com/hero/hero-desktop-1x.avif 1x, https://assets.tokoweb.com/hero/hero-desktop-2x.avif 2x" 
        type="image/avif" 
        media="(min-width: 768px)" 
        fetchpriority="high">

  <!-- 4. Critical Inline Stylesheet untuk Layout Stability -->
  <style>
    :root {
      --content-max-width: 1200px;
    }
    .hero-container {
      position: relative;
      width: 100%;
      max-width: var(--content-max-width);
      margin: 0 auto;
      background-color: #f3f4f6; /* Placeholder warna sebelum gambar render */
    }
    .hero-picture, .hero-img {
      display: block;
      width: 100%;
      height: auto;
    }
    /* Mengunci rasio aspek untuk mencegah CLS di desktop dan mobile */
    .hero-img {
      aspect-ratio: 16 / 9;
      object-fit: cover;
    }
  </style>

  <!-- 5. Modern Speculation Rules API (Next-Gen Prefetch/Prerender) -->
  <script type="speculationrules">
  {
    "prefetch": [
      {
        "source": "list",
        "urls": ["/checkout/cart", "/products/popular"],
        "requires": ["anonymous-client-ip-when-cross-origin"]
      }
    ],
    "prerender": [
      {
        "source": "list",
        "urls": ["/promotions/flash-sale"],
        "eagerness": "moderate"
      }
    ]
  }
  </script>
</head>
<body>
  <header>
    <nav>
      <a href="/promotions/flash-sale">Flash Sale Menanti!</a>
    </nav>
  </header>

  <main>
    <section class="hero-container">
      <!-- 
        LCP Image Node:
        - DILARANG loading="lazy" (akan mendegradasi LCP secara masif)
        - Diberikan fetchpriority="high"
        - decoding="sync" direkomendasikan untuk elemen LCP utama agar diprioritaskan oleh UI Thread
      -->
      <picture class="hero-picture">
        <!-- Sumber Resolusi & Format AVIF (High Compression Efficiency) -->
        <source media="(max-width: 767px)" 
                type="image/avif" 
                srcset="https://assets.tokoweb.com/hero/hero-mobile.avif 1x, 
                        https://assets.tokoweb.com/hero/hero-mobile-2x.avif 2x">

        <source media="(min-width: 768px)" 
                type="image/avif" 
                srcset="https://assets.tokoweb.com/hero/hero-desktop-1x.avif 1x, 
                        https://assets.tokoweb.com/hero/hero-desktop-2x.avif 2x">

        <!-- Fallback WebP untuk peramban non-AVIF -->
        <source media="(max-width: 767px)" 
                type="image/webp" 
                srcset="https://assets.tokoweb.com/hero/hero-mobile.webp 1x, 
                        https://assets.tokoweb.com/hero/hero-mobile-2x.webp 2x">

        <source media="(min-width: 768px)" 
                type="image/webp" 
                srcset="https://assets.tokoweb.com/hero/hero-desktop-1x.webp 1x, 
                        https://assets.tokoweb.com/hero/hero-desktop-2x.webp 2x">

        <!-- Standard Universal Fallback -->
        <img class="hero-img" 
             src="https://assets.tokoweb.com/hero/hero-desktop-1x.jpg" 
             alt="Promo Pesta Diskon Akhir Tahun Enterprise Commerce" 
             width="1920" 
             height="1080" 
             fetchpriority="high" 
             decoding="sync">
      </picture>
    </section>

    <section class="catalog">
      <!-- 
        Non-LCP Image: 
        - Wajib menggunakan loading="lazy"
        - decoding="async" untuk menjaga UI Thread tetap smooth
      -->
      <picture>
        <source type="image/avif" 
                srcset="/img/item1-300.avif 300w, /img/item1-600.avif 600w" 
                sizes="(max-width: 600px) 100vw, 300px">
        <img src="/img/item1-300.jpg" 
             alt="Sepatu Lari Running Speed Pro" 
             width="300" 
             height="300" 
             loading="lazy" 
             decoding="async">
      </picture>
    </section>
  </main>
</body>
</html>
```

---

### 8. Real World Case Study (Enterprise Scale)

#### 8.1 Konteks & Masalah
Sebuah platform media berita internasional (*News Outlet*) dengan rata-rata 45 juta *page views* harian mengalami penurunan traffic organik dari Google Search. Audit performa Core Web Vitals menunjukkan:
- **LCP (Largest Contentful Paint)**: Rata-rata 4.8 detik pada koneksi 4G seluler (Kategori: Buruk/Poor).
- **CLS (Cumulative Layout Shift)**: Rata-rata 0.28 (Kategori: Buruk/Poor).
- **Bandwidth Egress CDN**: Membengkak hingga 85 TB per bulan dengan biaya tagihan infrastruktur sangat tinggi.

#### 8.2 Analisis Masalah Mendalam
1. **LCP Bottleneck**: Hero image pada artikel berita dimuat via CSS `background-image: url(...)` di dalam bundle CSS eksternal. Browser harus:
   - Unduh dokumen HTML.
   - Parsing HTML -> temukan stylesheet eksternal.
   - Unduh file CSS -> parse CSSOM.
   - Menemukan deklarasi selector target -> baru memulai HTTP request untuk gambar LCP. Hal ini menciptakan dependensi 3 RTT yang tidak perlu.
2. **CLS Instability**: Gambar artikel tidak memiliki atribut `width` dan `height` eksplisit pada tag `<img>`. Saat gambar selesai diunduh, teks paragraf di bawahnya terdorong ke bawah secara masif.
3. **Ukuran File**: Semua gambar dikirim dalam format PNG/JPEG mentah (rata-rata 1.4 MB per hero image) tanpa memperhatikan DPR layar pengguna.

#### 8.3 Solusi Arsitektural
1. **HTML Markup Refactoring**: Mengganti `background-image` CSS dengan semantic element `<picture>` langsung di body HTML.
2. **Resource Prioritization**: Menginjeksikan `<link rel="preload" as="image" fetchpriority="high">` di dalam `<head>` yang dihasilkan secara otomatis oleh Server-Side Rendering (SSR) pipeline.
3. **Edge Image Transcoding**: Mengonfigurasi Cloudflare Workers / Fastly VCL untuk mengubah format secara instan menjadi AVIF untuk peramban Chromium/Safari modern, dan WebP untuk peramban lainnya, dengan fallback JPEG.
4. **Layout Reservation**: Menambahkan rasio dimensi intrinsik via atribut `width`, `height`, dan `aspect-ratio` inline style.

#### 8.4 Hasil Pasca-Implementasi (Berdasarkan Data RUM - Real User Monitoring)
- **LCP**: Menurun dari 4.8 detik menjadi **1.2 detik** (P95).
- **CLS**: Turun drastis dari 0.28 menjadi **0.002** (P95).
- **Ukuran Transfer Rata-Rata**: Turun dari 1.4 MB menjadi **110 KB** (AVIF level 65 quality).
- **Penghematan Bandwidth CDN**: Menurunkan transfer data bulanan sebesar 68%, menghemat belasan ribu dollar per kuartal.

---

### 9. Trade-offs

| Parameter Rekayasa | Pendekatan Agresif (Over-Optimized) | Pendekatan Konservatif | Keseimbangan Arsitektural Ideal |
|---|---|---|---|
| **Resource Hints (`preconnect`, `preload`)** | Memasang 15+ preload di `<head>` untuk semua skrip, CSS, font, dan gambar. | Tidak menggunakan preload sama sekali; mengandalkan default browser scanner. | Preload dibatasi untuk 1 Font Kritis, 1 LCP Image, dan maksimal 2 preconnect origin. |
| **Dampak CPU & Memori** | Menguras thread CPU, terjadi *bandwidth contention* (skrip fungsional tercekik oleh unduhan gambar). | Memori aman, namun browser thread menganggur menunggu antrean waterfall. | Prioritaskan LCP image dengan `fetchpriority="high"` dan gunakan `loading="lazy"` untuk 100% aset non-viewport. |
| **Kompresi AVIF vs WebP** | Encode semua aset ke AVIF level kompresi maksimal (slow encoding time). | Menggunakan JPEG standar atau WebP level rendah. | AVIF untuk target Web modern, WebP sebagai tier kedua. Caching agresif di Edge Server untuk mitigasi encoding cost CPU. |
| **Biaya Infrastruktur (CDN / Compute)** | Real-time dynamic image resizing tanpa cache layer (High Compute Cost). | Pre-generate ribuan variasi resolusi di build pipeline (Build time membengkak & Storage Cost). | *On-Demand Transformation with Long-lived Cache*: Generate saat request pertama, simpan permanen di Edge Storage Cache. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Kesalahan Fatal 1: Double-Download Akibat Mismatch Preload & Img Spec
**Kasus:** Menulis tag preload yang sedikit berbeda dengan tag eksekusi sebenarnya.
```html
<!-- KESALAHAN -->
<link rel="preload" as="image" href="/img/hero.jpg">
<!-- ... di body ... -->
<img src="/img/hero.jpg" srcset="/img/hero.jpg 1x, /img/hero-2x.jpg 2x" alt="Hero">
```
*Dampak:* Browser mengunduh `/img/hero.jpg` via preload scanner. Namun, ketika parser membaca tag `<img>` pada layar layar Retina (DPR 2), browser membatalkan referensi preload dan mengunduh `/img/hero-2x.jpg`. Hasil: **Gambar diunduh dua kali, bandwidth terbuang**.
*Solusi:* Samakan spesifikasi preload menggunakan atribut `imagesrcset` dan `imagesizes`:
```html
<link rel="preload" as="image" imagesrcset="/img/hero.jpg 1x, /img/hero-2x.jpg 2x" fetchpriority="high">
```

#### 10.2 Kesalahan Fatal 2: Menaruh `loading="lazy"` pada Elemen LCP
**Kasus:**
```html
<!-- KESALAHAN ANTI-PATTERN -->
<img src="/img/hero.jpg" width="1200" height="600" loading="lazy" fetchpriority="high" alt="LCP Image">
```
*Dampak:* Penambahan `loading="lazy"` menginstruksikan modul layout peramban untuk menunda request hingga posisi elemen terhadap intersection viewport terhitung secara tuntas (setelah styling & render tree pass selesai). Nilai LCP dapat melonjak 1-2 detik lebih lambat.
*Solusi:* **Haramkan** `loading="lazy"` untuk semua aset di atas *fold* (*above the fold*).

#### 10.3 Kesalahan Fatal 3: Missing Atribut `crossorigin` pada Preload Font
**Kasus:**
```html
<!-- KESALAHAN -->
<link rel="preload" href="/fonts/inter.woff2" as="font" type="font/woff2">
```
*Dampak:* Spesifikasi W3C mengharuskan unduhan Web Fonts diambil menggunakan mode **CORS Anonymous**, terlepas dari apakah font di-host pada origin yang sama atau domain berbeda. Tanpa atribut `crossorigin` atau `crossorigin="anonymous"`, peramban memperlakukan request preload sebagai no-cors, lalu mengabaikan cache tersebut saat parser CSS meminta font secara CORS. Hasil: **Font diunduh 2 kali**.

#### 10.4 Panduan Troubleshooting Waterfall Profiling
1. Buka Chrome DevTools -> tab **Network**.
2. Centang checkbox **Disable Cache** dan pilih throttling jaringan **Fast 4G**.
3. Klik kanan pada kolom header tabel Network, aktifkan kolom: **Priority**, **Protocol**, dan **Initiator**.
4. Urutkan berdasarkan kolom **Waterfall**.
5. Jika aset LCP Anda memiliki status baris prioritas bernilai `Low` pada durasi awal, pastikan tidak ada atribut `loading="lazy"` dan tambahkan `fetchpriority="high"`.
6. Jika font menunjukkan dua baris identik di Network tab, periksa keberadaan atribut `crossorigin` pada tag preload.

---

### 11. Best Practices (Production Checklist)

#### Pre-Deployment Architecture Audit Checklist
- [ ] **LCP Optimization**: Elemen visual LCP (gambar hero) tidak menggunakan atribut `loading="lazy"`.
- [ ] **Fetch Priority**: Elemen visual LCP memiliki atribut `fetchpriority="high"`.
- [ ] **Image Preloading**: Gambar LCP di-preload di dalam `<head>` menggunakan `<link rel="preload" as="image">` dengan `imagesrcset`/`imagesizes` yang identik.
- [ ] **CLS Prevention**: 100% tag `<img>` dan `<video>` memiliki atribut `width` dan `height` eksplisit atau didefinisikan via inline style `aspect-ratio`.
- [ ] **Font Optimization**: Maksimal 2 font kritis di-preload menggunakan atribut `as="font" type="font/woff2" crossorigin="anonymous"`.
- [ ] **Connection Warm-Up**: Tag `<link rel="preconnect">` digunakan maksimal untuk 2-3 domain third-party kritis (misal: CDN aset, payment gateway).
- [ ] **Modern Codecs**: Format gambar memanfaatkan `<picture>` dengan prioritas `AVIF` -> `WebP` -> `JPEG/PNG`.
- [ ] **Non-Critical Images**: Semua gambar di bawah viewport memiliki `loading="lazy"` dan `decoding="async"`.
- [ ] **Speculation Execution**: Speculation Rules API dikonfigurasi secara selektif untuk rute dengan probabilitas klik tinggi (`moderate` atau `conservative` eagerness).
- [ ] **Cache Header Alignment**: Response CDN menyertakan header `Cache-Control: public, max-age=31536000, immutable` untuk aset ter-hash (*fingerprinted*).

---

### 12. Hands-on Practice

Buat dan simpan struktur workspace berikut di direktori lokal Anda:
`hands-on/m02/`

```
hands-on/m02/
├── index.html
├── styles.css
└── generate-mock-assets.sh
```

#### Langkah 1: Script Pembuat Mock Aset
Buat file `hands-on/m02/generate-mock-assets.sh` untuk mensimulasikan aset resolusi berbeda. Jika Anda tidak memiliki CLI image encoder, buat file stub atau gunakan base64.
```bash
#!/bin/bash
# Eksekusi script ini untuk menyiapkan folder aset
mkdir -p assets
echo "Simulasi data binary font" > assets/font-mock.woff2
echo "Simulasi binary avif" > assets/hero-mobile.avif
echo "Simulasi binary avif desk" > assets/hero-desktop.avif
echo "Simulasi binary jpg fallback" > assets/hero-desktop.jpg
echo "Assets generated successfully."
```

Jalankan perintah:
```bash
chmod +x generate-mock-assets.sh && ./generate-mock-assets.sh
```

#### Langkah 2: Buat Stylesheet `hands-on/m02/styles.css`
```css
@font-face {
  font-family: 'EnterpriseFont';
  src: url('./assets/font-mock.woff2') format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'EnterpriseFont', sans-serif;
  line-height: 1.6;
  color: #1a1a1a;
  padding-bottom: 2000px; /* Force scrolling untuk pengujian lazy loading */
}

.hero-wrapper {
  width: 100%;
  max-width: 1200px;
  margin: 2rem auto;
  padding: 0 1rem;
}

.hero-wrapper picture,
.hero-wrapper img {
  width: 100%;
  height: auto;
  display: block;
}

/* Mengunci aspect ratio 16:9 */
.hero-wrapper img {
  aspect-ratio: 16 / 9;
  background-color: #e5e7eb;
}

.below-fold {
  max-width: 1200px;
  margin: 1000px auto 0;
  padding: 0 1rem;
}

.below-fold img {
  width: 100%;
  max-width: 600px;
  aspect-ratio: 4 / 3;
  background-color: #cbd5e1;
}
```

#### Langkah 3: Implementasi Dokumen Utama `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hands-on Enterprise Performance Lab</title>

  <!-- Preload Critical Font dengan Crossorigin -->
  <link rel="preload" 
        href="./assets/font-mock.woff2" 
        as="font" 
        type="font/woff2" 
        crossorigin="anonymous">

  <!-- Conditional Preload untuk LCP Image -->
  <link rel="preload" 
        as="image" 
        href="./assets/hero-mobile.avif" 
        type="image/avif" 
        media="(max-width: 768px)" 
        fetchpriority="high">
        
  <link rel="preload" 
        as="image" 
        href="./assets/hero-desktop.avif" 
        type="image/avif" 
        media="(min-width: 769px)" 
        fetchpriority="high">

  <link rel="stylesheet" href="./styles.css">

  <!-- Speculation Rules API untuk prefetch navigasi katalog -->
  <script type="speculationrules">
  {
    "prefetch": [
      {
        "source": "list",
        "urls": ["katalog.html"]
      }
    ]
  }
  </script>
</head>
<body>

  <header>
    <h1>Laboratorium Optimasi Aset</h1>
  </header>

  <main>
    <section class="hero-wrapper">
      <h2>Hero Section (Target Metrik LCP)</h2>
      <picture>
        <source media="(max-width: 768px)" 
                srcset="./assets/hero-mobile.avif" 
                type="image/avif">
        <source media="(min-width: 769px)" 
                srcset="./assets/hero-desktop.avif" 
                type="image/avif">
        <img src="./assets/hero-desktop.jpg" 
             alt="Platform Dashboard UI Showcase" 
             width="1600" 
             height="900" 
             fetchpriority="high" 
             decoding="sync">
      </picture>
    </section>

    <section class="below-fold">
      <h2>Aset di Luar Layar (Target Pengujian Lazy Load)</h2>
      <img src="./assets/hero-desktop.jpg" 
           alt="Katalog preview terisolasi" 
           width="800" 
           height="600" 
           loading="lazy" 
           decoding="async">
    </section>
  </main>

</body>
</html>
```

#### Langkah 4: Pengujian di Browser
1. Jalankan web server statis: `npx serve hands-on/m02` atau `python3 -m http.server 8080 --directory hands-on/m02`.
2. Buka Chrome DevTools -> **Performance** tab -> Record reload halaman.
3. Amati:
   - Tidak ada Layout Shift (Score: 0).
   - Tag font diunduh lebih awal bersamaan dengan parsing style.
   - Resource LCP mulai dimuat instan pada parse tree level awal.

---

### 13. Exercises

#### 13.1 Level: Easy
Diberikan markup aset gambar berikut:
```html
<img src="/assets/banner.png">
```
Ubah markup di atas agar:
1. Memiliki rasio aspek bawaan `4:1` dengan lebar standar desktop `1200px` dan tinggi `300px` untuk memitigasi CLS.
2. Dimuat secara non-blocking karena posisinya berada di bagian footer.
3. Thread rendering engine tidak terhambat saat mendekompresi bitmap gambar.

#### 13.2 Level: Medium
Sebuah situs web menyajikan banner desktop (`desktop.webp`, lebar 1200px) dan banner mobile (`mobile.webp`, lebar 600px).
1. Buat kode HTML tag `<picture>` yang menyajikan `desktop.webp` untuk layar dengan orientasi horizontal (`orientation: landscape`) atau lebar viewport minimal `768px`.
2. Sajikan `mobile.webp` untuk kondisi selain itu.
3. Tambahkan tag fallback universal standar `<img>` dengan konfigurasi prioritas rendering normal.

#### 13.3 Level: Hard
Tuliskan satu blok kode HTML `<head>` kelas enterprise yang lengkap, yang menangani kasus berikut:
1. Melakukan handshake jaringan lebih awal ke backend CDN terdistribusi: `https://static.cdn-perusahaan.com`.
2. Mengunduh secara spekulatif (preload) aset font variabel lokal (`/fonts/inter.woff2`).
3. Mengunduh secara kondisional hero background image yang memiliki 3 kandidat responsif berdasarkan kerapatan layar (1x, 2x, 3x) untuk desktop (`min-width: 1024px`) dengan tipe data modern `AVIF`.
4. Menerapkan skrip W3C Speculation Rules untuk melakukan **prerender** menyeluruh pada halaman `/checkout/direct-pay` saat pengguna mengarahkan mouse (hover/moderate) ke tombol terkait.

---

### 14. Challenges

#### Skenario Kasus Nyata: Migrasi Global Marketplace Terdistribusi
Anda adalah Lead Web Performance Engineer di sebuah startup decacorn e-commerce. Perusahaan mendapati bahwa metrik LCP mereka berada di angka 4.2 detik di wilayah Asia Tenggara di mana lebih dari 75% pengguna menggunakan gawai low-to-mid range Android dengan peramban Chromium lawas/modern di atas jaringan 3G/4G tidak stabil.

Spesifikasi & Konstrain Masalah:
1. Halaman utama memiliki "Flash Deal Carousel" yang terletak tepat di atas fold (LCP candidate). Carousel ini memiliki 5 gambar resolusi tinggi.
2. Tim pemasaran bersikeras menyajikan gambar beresolusi tinggi (minimal kualitas 90%).
3. Platform menyajikan font kustom korporat sebesar 350 KB dalam 4 variasi bobot font (regular, medium, bold, black).
4. Web server CDN mendukung HTTP/2, namun konfigurasi DNS, caching headers, dan prioritas request di tingkat HTML belum pernah dioptimalkan sejak implementasi awal monolith.

Tugas Arsitektur:
Rancang blueprint arsitektur dokumen HTML dan konfigurasi aset menyeluruh tanpa menggunakan library pihak ketiga JavaScript framework. Dokumentasikan:
- Strategi orkestrasi elemen `<head>` (urutan penempatan hints, blocking scripts, dan styles).
- Solusi markup carousel LCP (bagaimana memprioritaskan slide pertama dan menunda 4 slide lainnya).
- Strategi Client Hints untuk mendeteksi kapasitas memori perangkat (`Device-Memory`) dan kecepatan jaringan (`Downlink` / `Save-Data`) untuk menyajikan resolusi gambar yang diturunkan secara mulus.
- Berikan analisis kalkulasi matematika: bagaimana estimasi total transfer byte berkurang dan estimasi perbaikan RTT CRP secara terukur.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan fungsional utama antara atribut `loading="lazy"` dan atribut `fetchpriority="low"` pada elemen gambar?**
   - A. `loading="lazy"` menunda request hingga aset mendekati viewport, sedangkan `fetchpriority="low"` menurunkan prioritas antrean jaringan tanpa menunda inisiasi request.
   - B. `loading="lazy"` hanya bekerja pada skrip JavaScript, sedangkan `fetchpriority="low"` khusus untuk gambar.
   - C. Keduanya identik, `fetchpriority` adalah versi penamaan baru untuk browser modern.
   - D. `loading="lazy"` mematikan kompresi gambar, sedangkan `fetchpriority="low"` mengaktifkan kompresi AVIF.

2. **Mengapa penambahan atribut `width` dan `height` pada elemen `<img>` dapat mencegah layout shift (CLS)?**
   - A. Memaksa gambar diunduh pada resolusi sesuai angka tersebut secara kaku.
   - B. Memungkinkan browser menghitung rasio aspek intrinsik (*aspect-ratio*) dan mengalokasikan ruang kosong di layout tree sebelum binary gambar selesai diunduh.
   - C. Mengubah parsing HTML parser dari sinkron menjadi paralel.
   - D. Menginstruksikan browser untuk mengabaikan CSS styling eksternal.

3. **Manakah dari resource hints berikut yang hanya menyelesaikan translasi nama host menjadi alamat IP tanpa membuka koneksi TCP?**
   - A. `preconnect`
   - B. `preload`
   - C. `dns-prefetch`
   - D. `prerender`

4. **Kapan browser akan memicu peringatan (warning) di developer console terkait penggunaan `<link rel="preload">`?**
   - A. Jika file yang di-preload berukuran lebih dari 1 MB.
   - B. Jika aset yang di-preload tidak dikonsumsi atau digunakan oleh dokumen dalam kurun waktu beberapa detik setelah pemuatan.
   - C. Jika preload diarahkan ke domain pihak ketiga.
   - D. Jika aset yang di-preload memiliki format `.webp`.

5. **Format gambar modern manakah yang secara konsisten menawarkan efisiensi kompresi superior dibanding WebP dan JPEG untuk web?**
   - A. BMP
   - B. GIF
   - C. AVIF
   - D. TIFF

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Mengapa tag `<link rel="preload" as="font" ...>` WAJIB menyertakan atribut `crossorigin="anonymous"` meskipun font di-host pada subdomain dan origin yang sama?**
   - A. Karena jika tidak ada, server web akan merespons dengan HTTP Status 403 Forbidden.
   - B. Karena spesifikasi pemuatan font CSS Web Fonts mewajibkan pengambilan secara anonymous CORS; tanpa atribut tersebut di preload, browser akan mengunduh font dua kali via dua request terpisah.
   - C. Agar font dapat dibaca oleh script Service Worker di thread latar belakang.
   - D. Atribut tersebut tidak wajib untuk origin yang sama, itu adalah bug pada browser lawas.

7. **Perhatikan kode berikut:**
   ```html
   <img src="small.jpg" srcset="medium.jpg 1000w, large.jpg 2000w" sizes="50vw" alt="Example">
   ```
   **Jika viewport browser lebarnya 1000 CSS pixel dan DPR layar bernilai 2, file gambar manakah yang akan dipilih browser?**
   - A. `small.jpg`
   - B. `medium.jpg` (karena 50vw dari 1000px = 500px)
   - C. `large.jpg` (karena 50vw = 500px dikalikan DPR 2 membutuhkan resolusi fisik 1000px, dan browser mencocokkan ke kandidat `1000w` atau `2000w`)
   - D. Browser akan mengunduh ketiganya secara paralel.

8. **Apa konsekuensi dari memasang terlalu banyak tag `<link rel="preconnect">` (misal lebih dari 6 origin) di bagian `<head>` dokumen?**
   - A. Browser akan mengalami crash stack overflow seketika.
   - B. Terjadi kompetisi CPU & socket exhaustion; koneksi yang terbuka menahan alokasi memori sistem dan TLS session dapat ditutup sepihak oleh OS sebelum digunakan.
   - C. Dokumen HTML otomatis dialihkan ke HTTP/1.0 fallback mode.
   - D. CSP (*Content Security Policy*) akan memblokir semua request jaringan internal.

9. **Apa perbedaan fundamental antara `prefetch` standar dan Speculation Rules API?**
   - A. `prefetch` standar berjalan di Service Worker, Speculation Rules API berjalan di Edge Node.
   - B. Speculation Rules API ditulis via format JSON deklaratif, mendukung rule-based speculative matching, dan mampu melakukan prerender full page secara aman tanpa mengeksekusi side-effect berbahaya sebelum aktivasi.
   - C. `prefetch` standar mampu merender JavaScript, sedangkan Speculation Rules hanya bisa mengunduh CSS statis.
   - D. Speculation Rules API ditujukan khusus untuk browser berbasis Mozilla Gecko dan tidak didukung oleh Chromium engine.

10. **Pada elemen `<picture>`, urutan penulisan tag `<source>` sangat krusial karena:**
    - A. Browser modern akan membaca dari tag `<source>` paling bawah ke atas secara terbalik.
    - B. Browser mengabaikan atribut `type` dan hanya membaca atribut `media`.
    - C. Browser akan mengevaluasi kondisi secara berurutan (*first-match wins*); kecocokan format atau media query pertama yang didukung akan langsung dieksekusi, mengabaikan tag di bawahnya.
    - D. Preload scanner tidak mampu membaca elemen `<picture>` jika terdapat lebih dari satu tag `<source>`.

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario 1**: Tim Anda meluncurkan landing page baru. Hasil audit Lighthouse menunjukkan metrik LCP bernilai **5.6 detik**. Saat melihat waterfall chart, gambar hero LCP baru mulai di-download pada detik ke 3.8. Markup halaman Anda adalah:
    ```html
    <div class="hero-banner"></div>
    ```
    CSS:
    ```css
    .hero-banner { background-image: url('hero.avif'); background-size: cover; }
    ```
    **Langkah arsitektur tercepat dan paling efektif untuk memangkas waktu start request gambar tersebut ke milidetik pertama parsing dokumen adalah:**
    - A. Mengompres file `hero.avif` menggunakan tool kompresi ekstrem.
    - B. Menambahkan `<link rel="preload" as="image" href="hero.avif" fetchpriority="high">` di dalam `<head>` atau memindahkan gambar ke elemen semantik `<picture>` / `<img>` langsung di body.
    - C. Mengubah format `hero.avif` menjadi base64 Data URI di dalam CSS internal.
    - D. Menambahkan script JavaScript di akhir body untuk memanipulasi DOM hero banner.

12. **Skenario 2**: Situs berita Anda melaporkan nilai CLS tinggi (0.35) khusus pada perangkat iPhone modern dengan Retina Display (DPR 3), sedangkan pada perangkat laptop desktop skor CLS stabil di 0.01. Setelah inspeksi kode ditemukan:
    ```html
    <picture>
      <source media="(max-width: 768px)" srcset="banner-mobile.webp">
      <source media="(min-width: 769px)" srcset="banner-desktop.webp">
      <img src="banner-desktop.webp" alt="News" width="1200" height="400">
    </picture>
    ```
    Gambar `banner-mobile.webp` memiliki dimensi asli `600x600` (rasio 1:1), sedangkan fallback `<img>` memiliki atribut `width="1200" height="400"` (rasio 3:1).
    **Mengapa CLS terjadi pada mobile dan bagaimana memperbaikinya secara definitif?**
    - A. Terjadi layout shift karena browser mobile menghitung reservasi rasio layout berdasarkan atribut `width`/`height` tag fallback `<img>` (3:1), namun saat gambar mobile selesai dimuat, rasio berubah menjadi 1:1. Perbaikannya adalah mendefinisikan atribut `width` dan `height` eksplisit pada tag `<source>` mobile atau via media query CSS `aspect-ratio`.
    - B. Retina display iPhone tidak mendukung format WebP sehingga terjadi decoding crash. Perbaikannya adalah mengganti WebP ke PNG.
    - C. Tag `<source>` tidak boleh memiliki atribut `media`. Perbaikannya adalah menghapus atribut media query.
    - D. Nilai DPR 3 melebihi kapasitas buffer WebKit, solusinya adalah memaksa viewport viewport-fit=cover.

13. **Skenario 3**: Sebuah aplikasi perbankan online memuat file JavaScript otentikasi kritis menggunakan `<link rel="preload" as="script" href="/auth/core.js">`. Namun, di tab console muncul warning bahwa skrip tersebut tidak digunakan dan diunduh ulang saat halaman memproses `<script type="module" src="/auth/core.js">`.
    **Apa akar masalah teknis ini dan perbaikan apa yang harus diterapkan?**
    - A. Skrip modul ES6 tidak dapat di-preload. Hapus tag preload tersebut.
    - B. Modul ES6 menggunakan parser mode yang berbeda; preload skrip standar (`as="script"`) tidak kompatibel dengan Module Map Vanya engine. Gunakan `<link rel="modulepreload" href="/auth/core.js">`.
    - C. Server web mengirimkan mime-type text/plain untuk skrip. Ubah server configuration ke application/json.
    - D. Atribut `fetchpriority="low"` harus ditambahkan ke tag `<script type="module">`.

---

### Kunci Jawaban & Rasionalisasi Quiz

#### Bagian 1: Basic
1. **A** - `loading="lazy"` mengontrol siklus *kapan* request dimulai berdasarkan posisi geometri layout viewport, sedangkan `fetchpriority` mengontrol *prioritas alokasi bandwidth antrean* di modul jaringan peramban.
2. **B** - Atribut `width` dan `height` memberikan peramban informasi rasio aspek sehingga peramban dapat mereservasi ruang render secara otomatis via default user-agent CSS rules (`aspect-ratio: attr(width) / attr(height)`), mencegah teks/elemen meloncat saat gambar mendarat.
3. **C** - `dns-prefetch` murni menjalankan DNS resolution. `preconnect` melakukan DNS + TCP + TLS handshake.
4. **B** - Preload ditujukan eksklusif untuk aset rendering kritis saat ini. Mengabaikan aset yang di-preload dalam batas waktu render pertama menandakan inefisiensi arsitektur yang mengorbankan bandwidth.
5. **C** - AVIF yang berbasis kompresi intra-frame codec video AV1 secara konsisten menghasilkan rasio kompresi 20-50% lebih ringkas dibanding WebP dan JPEG pada tingkat SSIM (*Structural Similarity Index Measure*) visual yang setara.

#### Bagian 2: Intermediate
6. **B** - Mengacu pada spesifikasi W3C Fetch & CSS Fonts standard, Web Font diambil menggunakan CORS mode anonym. Preload tanpa atribut `crossorigin` diinisiasi dengan mode non-cors. Karena mode CORS tidak cocok (*mismatched cache key credentials*), browser membuang hasil preload dan melakukan fetch ulang.
7. **C** - Evaluasi: $1000\text{px} \times 0.5\ (50\text{vw}) = 500\text{px}$ visual size. Dikalikan DPR 2 = $1000\text{px}$ physical size. Kandidat terdekat yang memenuhi atau melampaui adalah `1000w` atau `2000w` (tergantung kurva densitas peramban), dalam pilihan jawaban, `large.jpg` atau `medium.jpg` dapat dipilih, namun `large.jpg` dengan rasio teraman mencukupi kebutuhan density tinggi tanpa pixelation. Browser memilih kandidat optimal di array `srcset`.
8. **B** - Setiap koneksi preconnect mengonsumsi slot memori, komputasi kriptografi TLS handshake, dan socket TCP terbuka. Membuka terlalu banyak preconnect memicu overhead jaringan yang memakan bandwidth thread utama.
9. **B** - Speculation Rules API adalah standar modern berbasis JSON yang mampu mendefinisikan ruleset dinamis dan mendukung *instant page navigation* melalui off-screen background prerendering yang sepenuhnya aman (*isolated context*).
10. **C** - Parsing elemen `<picture>` mengevaluasi tag `<source>` secara linier dari atas ke bawah. Kondisi pertama yang lolos validasi kapabilitas decoder MIME type dan/atau media query akan langsung digunakan (*first-match semantic*).

#### Bagian 3: Skenario Kasus Produksi
11. **B** - Gambar yang disematkan melalui CSS background bergantung pada selesainya parsing CSS eksternal (CSSOM blocking). Memindahkannya ke HTML secara deklaratif atau menyematkan `<link rel="preload" as="image" fetchpriority="high">` memungkinkan Preload Scanner peramban mendeteksi dan mengunduh gambar secara instan di awal dokumen HTML.
12. **A** - Pada browser modern, elemen `<source>` di dalam `<picture>` juga dapat memiliki atribut `width` dan `height` atau diatur via CSS layout query. Inkonsistensi rasio antara fallback desktop (3:1) dan gambar mobile aktual (1:1) merusak kalkulasi ruang reservasi awal, menghasilkan CLS masif saat resolusi gambar mobile diterapkan.
13. **B** - ES Modules (`type="module"`) dieksekusi dengan model dependensi grafik pohon. Peramban membutuhkan `<link rel="modulepreload">` untuk mengunduh, mengurai (*parse*), dan mengompilasi modul JavaScript secara langsung ke V8 module map, bukan `<link rel="preload" as="script">`.

---

### 16. Summary

1. **Critical Rendering Path Acceleration**: Optimasi aset modern di tingkat HTML bukan sekadar mengompres ukuran file, melainkan memodifikasi alur kerja internal *Browser Preload Scanner*, antrean *Resource Fetch Scheduler*, dan resolusi soket jaringan.
2. **Harmonisasi Resource Hints**: Gunakan `dns-prefetch` dan `preconnect` secara hemat (<= 3 origin eksternal). Gunakan `preload` dan `modulepreload` khusus untuk aset pemblokir render kritis yang ditemukan terlambat (*late-discovered critical assets*), seperti font web dan LCP Hero Image.
3. **Core Web Vitals Determinism**:
   - **LCP**: Amankan LCP dengan kombinasi elemen `<picture>`, atribut `fetchpriority="high"`, dan conditional `<link rel="preload" as="image">`. **Jangan pernah** menaruh `loading="lazy"` pada elemen LCP.
   - **CLS**: Amankan CLS hingga mendekati 0.00 dengan selalu menyatakan atribut dimensi intrinsik `width` dan `height` atau CSS `aspect-ratio` pada semua container media.
4. **Next-Generation Delivery**: Adopsi format generasi berikutnya (`AVIF` -> `WebP` -> Universal Fallback) yang dipadukan dengan Speculation Rules API untuk navigasi instan antar-halaman (*instant sub-second transitions*). Sinkronisasikan implementasi HTML frontend dengan header transmisi caching HTTP edge server untuk arsitektur web berskala global.