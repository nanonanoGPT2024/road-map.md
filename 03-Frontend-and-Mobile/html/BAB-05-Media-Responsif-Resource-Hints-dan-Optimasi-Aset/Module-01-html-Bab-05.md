# BAB 05 MODULE 01: MEDIA RESPONSIF, RESOURCE HINTS, DAN OPTIMASI ASET

---

## SEKSI 01 — IDENTITAS MODUL

* **Domain:** `03-Frontend-and-Mobile`
* **Mata Pelajaran:** HTML Core Standards & Web Performance Engineering
* **Bab:** 05 — Advanced Asset Delivery & Responsive Layout Systems
* **Modul:** 01 — Media Responsif, Resource Hints, dan Optimasi Aset
* **Tingkat Kesulitan:** Advanced / Staff Engineer Track
* **Prasyarat Pengetahuan:**
  * Pemahaman mendalam tentang Critical Rendering Path (CRP).
  * Mekanisme kerja browser HTTP Networking stack (HTTP/2, HTTP/3 QUIC, TCP/IP handshake, TLS 1.3 negotiation).
  * Dasar-dasar DOM Tree construction dan CSSOM Tree processing.
  * Pengetahuan format pengkodean citra/video modern (WebP, AVIF, H.264, VP9, AV1).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Mengimplementasikan Responsive Media Architecture:** Menguasai decoupling resolusi dan pemilihan format berbasis kapabilitas klien menggunakan elemen `<picture>`, atribut `srcset`, dan deskriptor `sizes` tanpa memicu layout shift atau overfetching aset.
2. **Mengatur Prioritas Jaringan Menggunakan Resource Hints:** Mengonfigurasi `dns-prefetch`, `preconnect`, `prefetch`, `preload`, dan `modulepreload` secara presisi untuk memanipulasi browser preloader pipeline dan mengurangi Network Round Trip Time (RTT).
3. **Mengoptimalkan Metrik Core Web Vitals:** Menghilangkan Cumulative Layout Shift (CLS) yang disebabkan oleh pergeseran media dan menurunkan Largest Contentful Paint (LCP) hingga di bawah ambang batas 2.5 detik untuk 75th percentile audiens pada koneksi target (4G/LTE).
4. **Menerapkan Modern Asset Encoding dan Content Negotiation:** Memanfaatkan format generasi masa depan (AVIF, WebP, SVG tersanitasi) melalui *graceful degradation* deklaratif di lapisan parser HTML.
5. **Mengamankan Pengiriman Aset:** Menerapkan Subresource Integrity (SRI) dan Content Security Policy (CSP) khusus media untuk mencegah eksploitasi MIME-confusion, CDN supply-chain compromise, dan pixel-injection attacks.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### The Parser vs. Network Race Model
Untuk memahami media responsif dan resource hints, Anda harus membongkar ilusi bahwa browser mengeksekusi dokumen secara sekuensial dari atas ke bawah secara pasif. Browser modern mempekerjakan setidaknya dua parser: **Main HTML Tokenizer/Tree Builder** dan **Speculative Pre-parser (Preload Scanner)**.

```
Incoming Byte Stream -> [Preload Scanner] -------------> Background Network Fetch (High Priority)
                             |
                             v
                        [HTML Tokenizer] -> [DOM Tree] -> [Style Layout] -> Render Tree -> GPU Paint
```

* **Mental Model 1: Preload Scanner Buta terhadap CSS.**
  Preload Scanner memindai byte stream yang masuk untuk menemukan tag `<img>`, `<link>`, atau `<script>` jauh sebelum CSS selesai diunduh dan di-parse. Akibatnya, scanner tidak mengetahui dimensi elemen di layar (`width: 50vw`) atau apakah suatu elemen disembunyikan via `display: none`. Jika Anda mengandalkan CSS untuk media selection, Preload Scanner akan mengunduh media default terlebih dahulu, menyebabkan *double-download*. Oleh karena itu, logika resolusi *wajib* dideklarasikan di HTML via atribut `sizes` dan `srcset`.
* **Mental Model 2: Resource Hints Adalah Pinjaman Utang Bandwidth.**
  Resource hints bukan "tombol turbo" yang dapat dipasang di setiap aset. Menggunakan `preload` secara serampangan mencuri *execution cycles* dan alokasi bandwidth dari aset kritis lainnya (seperti font rendering atau CSS blokir pertama). Perlakukan alokasi resource hint seperti transaksi anggaran zero-sum game pada TCP congestion window.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Penjadwalan Jaringan Browser (Resource Hints & Parser Lifecycle)

Diagram berikut mengilustrasikan bagaimana Chromium Network Stack memprioritaskan aset berdasarkan tipe resource hints dan parsing token:

```
[ HTTP/2 or HTTP/3 Stream Ingestion ]
                  │
                  ▼
   ┌──────────────────────────────┐
   │ Speculative Preload Scanner  │
   └──────────────┬───────────────┘
                  │
                  ├─────────────────────────────────────────┐
                  ▼                                         ▼
     ┌────────────────────────┐                ┌────────────────────────┐
     │ Found <link rel="..."> │                │ Found <picture>/<img>  │
     └────────────┬───────────┘                └────────────┬───────────┘
                  │                                         │
        ┌─────────┴───────────────┐                         ▼
        │ Evaluasi Tipe Hint:     │               ┌───────────────────┐
        │                         │               │ Evaluasi:         │
        ├─> dns-prefetch:         │               │ - Client DPR      │
        │   Resolve DNS only      │               │ - Viewport Width  │
        ├─> preconnect:           │               │ - sizes descriptor│
        │   DNS + TCP + TLS       │               │ - source media/type
        ├─> preload:              │               └─────────┬─────────┘
        │   High-Priority Ingestion                         │
        ├─> prefetch:             │                         │
        │   Idle Priority Queue   │                         │
        └─────────────────────────┘                         │
                  │                                         │
                  ▼                                         ▼
     ┌──────────────────────────────────────────────────────────────┐
     │               Resource Scheduler / NetLog                    │
     │  (Penyelarasan Priority Trees: HIGHEST -> HIGH -> LOW -> IDLE)
     └──────────────────────────────┬───────────────────────────────┘
                                    │
                                    ▼
     ┌──────────────────────────────────────────────────────────────┐
     │     Pemuatan Socket & Injeksi Aset ke Memory/Disk Cache       │
     └──────────────────────────────────────────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Dekonstruksi Sintaks Media Responsif
Sistem pemilihan media di browser bekerja menggunakan algoritma internal berikut:

```
                       ┌─────────────────────────┐
                       │ Elemen <picture> terbaca │
                       └────────────┬────────────┘
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
┌─────────────────────────┐                     ┌─────────────────────────┐
│     Evaluasi <source>   │                     │     Evaluasi fallback   │
│ - type="image/avif"?    │──(Tidak Didukung)──>│          <img>          │
│ - media="(min-width)"?  │                     │  - Pilih dari srcset    │
└───────────┬─────────────┘                     │    menggunakan sizes    │
            │ (Cocok)                           └─────────────────────────┘
            ▼
┌─────────────────────────┐
│ Pilih kandidat terbaik  │
│ dari source.srcset      │
└─────────────────────────┘
```

* **`srcset` (Width Descriptor vs. Pixel Density):**
  * `image-400.jpg 400w`: Menyatakan lebar intrinsik citra adalah 400 piksel fisik.
  * `image-2x.jpg 2x`: Menargetkan Device Pixel Ratio (DPR) 2.0 (retina display). **Hindari format ini untuk desain responsif modern** karena mengasumsikan lebar container citra selalu konstan.
* **`sizes` (Layout Negotiation):**
  * Sintaks: `sizes="(media-condition) source-size, default-source-size"`.
  * Browser menghitung: `source-size * DPR = Lebar Piksel Target`. Browser kemudian memilih kandidat terdekat pada `srcset` yang nilainya $\ge \text{Lebar Piksel Target}$.

### 2. Mekanisme Internal Resource Hints
* **`dns-prefetch`:** Memaksa resolver sistem operasi mengeksekusi Address Record Resolution (A / AAAA query) ke DNS server tanpa menginisiasi koneksi socket. Memangkas 20–120ms latensi DNS.
* **`preconnect`:** Melangkah lebih jauh dengan melakukan DNS resolution, TCP three-way handshake, dan TLS 1.3 cryptographic negotiation (SNI, ALPN, Key Exchange). Memangkas hingga 3 RTT sebelum permintaan aset riil dipicu.
* **`preload`:** Menginstruksikan browser bahwa suatu aset *wajib* diunduh pada fase kompilasi/parsing saat ini karena akan digunakan dalam waktu dekat oleh DOM/CSSOM. Browser menempatkan aset ini dalam internal cache dengan prioritas tinggi (*High/VeryHigh*).
* **`prefetch`:** Menginstruksikan browser bahwa suatu aset kemungkinan besar dibutuhkan oleh *navigasi berikutnya* (halaman selanjutnya). Browser mengunduh aset tersebut menggunakan idle network cycles (*Lowest priority*).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Formula Matematis Resolusi Gambar
Misalkan viewport pengguna memiliki ukuran $W_v = 1200\text{px}$ dengan Device Pixel Ratio $\text{DPR} = 2.0$.
Didefinisikan aturan media pada markup:
```html
sizes="(max-width: 768px) 100vw, 50vw"
```
1. Browser mengevaluasi media queries:
   * $W_v \le 768\text{px}$ bernilai FALSE.
   * Fallback rule dieksekusi: lebar target citra = $50\text{vw}$.
2. Browser menghitung CSS Pixels:
   $$\text{CSS Pixels} = 50\% \times 1200\text{px} = 600\text{px}$$
3. Browser menghitung Device Physical Pixels yang diperlukan:
   $$\text{Physical Pixels Needed} = 600\text{px} \times 2.0 = 1200\text{px}$$
4. Browser memindai `srcset`:
   ```html
   srcset="hero-600.webp 600w, hero-900.webp 900w, hero-1200.webp 1200w, hero-1800.webp 1800w"
   ```
5. Browser memilih citra `hero-1200.webp` secara deterministik.

### Browser Heuristics: Fetch Priority API
Penambahan atribut `fetchpriority` ("high" | "low" | "auto") memodifikasi bobot *dependency tree* pada layer transport HTTP/2 dan HTTP/3:

| Elemen HTML | Default Priority | Dengan `fetchpriority="high"` | Dengan `fetchpriority="low"` |
| :--- | :--- | :--- | :--- |
| `<img>` (In-viewport / Early DOM) | Medium / High | High / Very High | Low |
| `<img>` (Lanjutan DOM / lazy) | Low | High (Mengesampingkan lazy) | Lowest |
| `<link rel="preload">` | Sesuai atribut `as` | Meningkatkan bobot stream | Menurunkan bobot stream |
| `<script>` | High / Low (async) | Very High | Lowest |

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah perbandingan pola buruk vs pola arsitektural yang benar untuk deklarasi hero banner responsif modern.

### Pola Anti-Pattern (Naif)
```html
<!-- BURUK: Single resolution, pemborosan bandwidth mobile, memicu CLS -->
<img src="banner-huge.jpg" alt="Platform Launch" style="width: 100%;">
```

### Pola Optimal (Standard Production)
```html
<!-- BAIK: Format negotiation, responsive scaling, layout preservation -->
<picture>
  <!-- Format generasi masa depan: AVIF -->
  <source 
    type="image/avif"
    srcset="banner-320.avif 320w,
            banner-640.avif 640w,
            banner-1280.avif 1280w,
            banner-1920.avif 1920w"
    sizes="(max-width: 640px) 100vw, (max-width: 1200px) 75vw, 1200px"
  />
  
  <!-- Format transisi: WebP -->
  <source 
    type="image/webp"
    srcset="banner-320.webp 320w,
            banner-640.webp 640w,
            banner-1280.webp 1280w,
            banner-1920.webp 1920w"
    sizes="(max-width: 640px) 100vw, (max-width: 1200px) 75vw, 1200px"
  />

  <!-- Fallback: MozJPEG / Optimized JPEG dengan dimensi intrinsik terdefinisi -->
  <img 
    src="banner-640.jpg" 
    srcset="banner-320.jpg 320w,
            banner-640.jpg 640w,
            banner-1280.jpg 1280w,
            banner-1920.jpg 1920w"
    sizes="(max-width: 640px) 100vw, (max-width: 1200px) 75vw, 1200px"
    alt="Arsitektur Ekosistem Cloud Engine Enterprise"
    width="1920"
    height="1080"
    loading="eager"
    fetchpriority="high"
    decoding="async"
  />
</picture>
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Mengacu pada blok kode optimal di **SEKSI 07**:

1. `<picture>`: Kontainer wrappers logika kondisional. Parser memanfaatkan blok ini untuk mengevaluasi elemen anak secara deklaratif tanpa intervensi JavaScript.
2. `<source type="image/avif" ...>`:
   * Browser mengecek *image codec subsystem*. Jika decoding AVIF didukung, browser *menghentikan* parsing tag `<source>` berikutnya dan langsung memproses `srcset` pada baris ini.
3. `srcset="banner-320.avif 320w, ..."`: Menyediakan peta pemetaan URL terhadap lebar intrinsik piksel file (`w`). Parser memetakan file mana yang paling mendekati target kalkulasi render.
4. `sizes="(max-width: 640px) 100vw, (max-width: 1200px) 75vw, 1200px"`: Memberi tahu Preload Scanner sebelum CSS selesai diunduh:
   * Jika lebar viewport $\le 640\text{px}$, citra akan dirender sebesar $100\%$ lebar layar (`100vw`).
   * Jika lebar viewport $\le 1200\text{px}$, citra akan dirender sebesar $75\%$ lebar layar (`75vw`).
   * Untuk ukuran selainnya, lebar citra adalah statis $1200\text{px}$.
5. `<source type="image/webp" ...>`: Fallback lapis kedua jika peramban (misal: klien browser lama) tidak dapat mendekode AVIF, namun mendukung WebP.
6. `<img ...>`: Elemen inti. Merupakan fallback mutlak jika `<picture>` tidak didukung dan entitas riil yang akan menempati DOM node tree.
7. `width="1920" height="1080"`: **Menghilangkan Cumulative Layout Shift (CLS)**. Atribut ini memungkinkan browser menghitung *aspect-ratio* intrinsik ($16:9$) secara instan sebelum file citra selesai diunduh, mengalokasikan ruang kosong layout render terlebih dahulu.
8. `loading="eager"`: Mencegah browser menunda pemuatan gambar LCP. Untuk aset non-kritis di bawah lipatan (*below-the-fold*), nilai ini harus diganti menjadi `loading="lazy"`.
9. `fetchpriority="high"`: Memaksa HTTP stack menaikkan prioritas stream transfer data setara dengan CSS blokir, penting untuk elemen kandidat Largest Contentful Paint.
10. `decoding="async"`: Memindahkan decoding kompresi citra dari *Main UI Thread* ke *Compositor/Worker Thread*, mencegah UI *frame drop* (jank) saat citra beresolusi besar diekstrak ke memori GPU.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Redesain Landing Page Marketplace B2B Skala Global
* **Konteks:** Sebuah portal logistik dan perdagangan enterprise memiliki 20 juta Monthly Active Users. Halaman utama memiliki metrik Core Web Vitals yang buruk:
  * LCP: **4.8s** pada jaringan 4G.
  * CLS: **0.32** (Sangat buruk, threshold Google: $\le 0.1$).
* **Akar Masalah:**
  1. Hero section menggunakan satu file PNG transparan berukuran 3.8 MB yang dimuat menggunakan tag `<img src="hero.png">` tanpa atribut `width` dan `height`.
  2. Gambar produk ditarik dari CDN pihak ketiga (`https://assets.cdn-supplier.com`) tanpa inisialisasi koneksi awal (mengakibatkan TLS Handshake stalling sebesar 280ms).
  3. Video promosi MP4 disematkan menggunakan `<video autoplay loop>` tanpa poster, mengonsumsi seluruh TCP stream data awal yang bersaing dengan bundle JavaScript aplikasi.
* **Solusi Arsitektur:**
  1. Mengimplementasikan `<link rel="preconnect">` ke domain CDN dengan atribut `crossorigin`.
  2. Mengonversi media ke format AVIF/WebP responsif dengan kalkulasi atribut `sizes` presisi dan penerapan aspek rasio berbasis atribut HTML dimensi.
  3. Mengarahkan resource loading untuk video menggunakan kombinasi poster frame responsif dan penundaan preloading stream video.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah dokumen implementasi modular yang memecahkan masalah pada Studi Kasus Seksi 09:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Infrastruktur Logistik Global | Enterprise Engine</title>

  <!-- 1. Resource Hints: Koneksi Awal CDN Pihak Ketiga -->
  <link rel="dns-prefetch" href="https://assets.cdn-supplier.com">
  <link rel="preconnect" href="https://assets.cdn-supplier.com" crossorigin>

  <!-- 2. Preload Hero Image LCP Secara Deklaratif Menggunakan Source Set -->
  <link 
    rel="preload" 
    as="image" 
    type="image/avif" 
    href="https://assets.cdn-supplier.com/hero-1280.avif"
    imagesrcset="https://assets.cdn-supplier.com/hero-640.avif 640w,
                 https://assets.cdn-supplier.com/hero-1280.avif 1280w,
                 https://assets.cdn-supplier.com/hero-1920.avif 1920w"
    imagesizes="(max-width: 768px) 100vw, 1200px"
    fetchpriority="high"
  >

  <style>
    /* Mengamankan kestabilan CLS dan implementasi Fluid CSS */
    .hero-container {
      width: 100%;
      max-width: 1200px;
      margin: 0 auto;
    }
    .responsive-media {
      width: 100%;
      height: auto;
      display: block;
      /* Mencegah reflow layout */
      aspect-ratio: 16 / 9;
    }
  </style>
</head>
<body>

  <header>
    <h1>Pusat Distribusi Global</h1>
  </header>

  <main>
    <section class="hero-container">
      <!-- Media Responsif Resolusi Tinggi (LCP Candidate) -->
      <picture>
        <source 
          type="image/avif"
          srcset="https://assets.cdn-supplier.com/hero-640.avif 640w,
                  https://assets.cdn-supplier.com/hero-1280.avif 1280w,
                  https://assets.cdn-supplier.com/hero-1920.avif 1920w"
          sizes="(max-width: 768px) 100vw, 1200px"
        />
        <source 
          type="image/webp"
          srcset="https://assets.cdn-supplier.com/hero-640.webp 640w,
                  https://assets.cdn-supplier.com/hero-1280.webp 1280w,
                  https://assets.cdn-supplier.com/hero-1920.webp 1920w"
          sizes="(max-width: 768px) 100vw, 1200px"
        />
        <img 
          src="https://assets.cdn-supplier.com/hero-1280.jpg" 
          srcset="https://assets.cdn-supplier.com/hero-640.jpg 640w,
                  https://assets.cdn-supplier.com/hero-1280.jpg 1280w,
                  https://assets.cdn-supplier.com/hero-1920.jpg 1920w"
          sizes="(max-width: 768px) 100vw, 1200px"
          alt="Visualisasi Jaringan Pengiriman Lintas Benua" 
          width="1920" 
          height="1080" 
          class="responsive-media"
          loading="eager" 
          fetchpriority="high" 
          decoding="async"
        />
      </picture>
    </section>

    <!-- Media Non-Kritis / Below-the-fold (Lazy Loaded Video dan Poster) -->
    <section class="hero-container" style="margin-top: 4rem;">
      <video 
        class="responsive-media" 
        width="1920" 
        height="1080" 
        controls 
        preload="none" 
        poster="https://assets.cdn-supplier.com/video-poster-1280.webp"
      >
        <source src="https://assets.cdn-supplier.com/promo-logistics.mp4" type="video/mp4; codecs='avc1.4D401F, mp4a.40.2'">
        <track kind="captions" src="/captions/promo-id.vtt" srclang="id" label="Bahasa Indonesia" default>
        Browser Anda tidak mendukung reproduksi video HTML5 native.
      </video>
    </section>
  </main>

</body>
</html>
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Mekanisme / Format | Keunggulan | Kelemahan / Konsekuensi | Skenario Terbaik |
| :--- | :--- | :--- | :--- |
| **`<img>` dengan `srcset`** | Sangat efisien; integrasi native dengan algoritma scaling resolusi browser internal. | Hanya menangani resolusi aset yang sama; tidak cocok untuk *art direction* kompleks. | Foto umum, katalog produk, layout yang proporsinya statis. |
| **`<picture>` System** | Mendukung *art direction* (crop berbeda per media) dan *format negotiation* (AVIF/WebP/JPG). | Overhead markup HTML besar; kompleksitas konfigurasi build-pipeline CDN. | Hero banners multi-rasio, integrasi format terdepan yang belum 100% universal. |
| **`preload` Hint** | Memaksa aset diunduh sedini mungkin; memotong latency discovery LCP. | Menggunakan bandwidth pada fase rendering awal; jika salah target, memicu *bandwidth starvation*. | Font files lokal kritis (`.woff2`), hero image LCP eksplisit. |
| **`prefetch` Hint** | Mengoptimalkan transisi navigasi berikutnya secara dramatis (0ms TTFB cache). | Mengonsumsi kuota data klien untuk halaman yang belum pasti dikunjungi. | Navigasi multi-langkah (misal: tombol checkout pada funnel cart). |
| **Format AVIF** | Kompresi 20–50% lebih efisien dibanding WebP/JPEG tanpa kehilangan detail struktural. | Encoding CPU-bound sangat lambat pada build time; rendering sedikit lebih lambat pada peramban tua. | High-traffic e-commerce; platform media dengan kebutuhan throughput masif. |
| **Format SVG** | Resolusi independen (skalabilitas tanpa batas); ukuran file berbasis vektor sangat kecil. | Parsing CPU membengkak jika node path ribet; potensi kerentanan keamanan XSS jika tidak disanitasi. | Ikon, logo, ilustrasi antarmuka pengguna berbasis bentuk geometris. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Preload Duplication Trap
Jika Anda mendeklarasikan `<link rel="preload">` untuk gambar yang juga memiliki `srcset` di tag `<img>`, Anda **wajib** menyertakan `imagesrcset` dan `imagesizes` pada tag `<link>`.
* **Failure Mode:** Jika Anda hanya menulis `<link rel="preload" as="image" href="fallback.jpg">`, sementara browser memilih `fallback-400.webp` via `srcset`, browser akan **mengunduh kedua gambar tersebut**. Penggunaan kuota jaringan meningkat $2\times$ lipat.

### 2. The `crossorigin` Preconnect Mismatch
Ketika melakukan `preconnect` ke CDN penyedia resource yang membutuhkan CORS (seperti font atau `crossorigin` images):
* **Failure Mode:** Menulis `<link rel="preconnect" href="https://cdn.example.com">` tanpa atribut `crossorigin`. Browser menyimpan socket pool untuk koneksi non-CORS. Saat aset CORS dieksekusi, browser terpaksa membuka **koneksi TCP/TLS baru**, membuat hint awal sia-sia.
* **Mitigasi:** Selalu gunakan `<link rel="preconnect" href="https://cdn.example.com" crossorigin>` untuk domain yang mendistribusikan font atau CORS-enabled images.

### 3. DPR Volatility pada Art Direction
Pada layar densitas tinggi (misal: iPhone DPR 3.0), browser dapat memilih gambar dari resolusi desktop untuk layout mobile jika Anda mendefinisikan lebar piksel mentah pada elemen `<picture>` tanpa batasan max-width pada `<source media="...">`. Browser mengutamakan ketajaman gambar ketimbang penghematan data.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan CSS `background-image` untuk Aset LCP
* **Salah:** Menetapkan hero image via `background-image: url('hero.jpg')` di CSS eksternal.
* **Mengapa:** Preload scanner tidak dapat mendeteksi aset ini hingga CSS diunduh dan diparsing. Waktu LCP tertunda secara signifikan.
* **Solusi:** Gunakan tag `<picture>` atau `<img>` di HTML dengan atribut `fetchpriority="high"`.

### 2. Menggunakan Nilai `sizes="100vw"` Tanpa Kondisi
* **Salah:** Memberikan `sizes="100vw"` pada gambar yang berada di dalam container terbatas (misal: `max-width: 1200px`).
* **Mengapa:** Pada layar beresolusi 4K (3840px), browser akan mengunduh gambar berukuran 4K meskipun container hanya merender gambar sebesar 1200px.
* **Solusi:** Berikan batas akhir pada deskriptor: `sizes="(max-width: 1200px) 100vw, 1200px"`.

### 3. Memasang `loading="lazy"` pada Hero Image LCP
* **Salah:** Menulis `<img src="hero.jpg" loading="lazy">` pada gambar pertama di viewport teratas.
* **Mengapa:** Peramban sengaja menunda aset dengan penanda lazy hingga tata letak layout terhitung lengkap. Ini merusak skor Largest Contentful Paint.
* **Solusi:** Gunakan `loading="eager"` dan `fetchpriority="high"` untuk aset LCP. Pasang `loading="lazy"` hanya untuk aset sekunder yang berada di luar initial viewport.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Rasio Aspek Konsisten Secara Deklaratif:**
   Selalu sematkan atribut `width` dan `height` absolut yang merefleksikan aspek rasio asli gambar, lalu biarkan CSS menangani responsivitasnya via `height: auto` atau `aspect-ratio`.
2. **Prioritas Urutan `<source>`:**
   Susun format file dari yang paling modern ke fallback terlama:
   * Urutan: AVIF $\rightarrow$ WebP $\rightarrow$ JPEG/PNG.
3. **Optimasi SVG:**
   SVG harus diminifikasi menggunakan alat seperti `svgo`, membersihkan metadata editor (seperti Illustrator/Inkscape), dan disajikan langsung atau via `<img>` yang terisolasi dari konteks DOM utama.
4. **Alokasi Resource Hint yang Terukur:**
   Batasi jumlah deklarasi `<link rel="preconnect">` maksimal 2–4 origin pihak ketiga yang benar-benar kritis. Terlalu banyak koneksi awal akan membuang CPU cycles perangkat mobile untuk alokasi thread TLS handshake.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Kalkulasi Efisiensi Payloads
Dengan mengimplementasikan arsitektur gambar responsif multi-format, kita dapat mengukur penghematan jaringan:

$$\text{Data Transfer Reduction (\%)} = \left( 1 - \frac{\text{Ukuran AVIF Terpilih}}{\text{Ukuran JPEG Orisinal}} \right) \times 100$$

Dalam skenario pengujian baseline:
* Hero Legacy: JPEG 1920px (980 KB) dikirim ke layar mobile (390px Viewport @3x DPR $\rightarrow$ butuh rendering width 1170px).
* Hero Responsif Modern: AVIF 1200px (64 KB).
* Efisiensi Bandwidth:
  $$\left( 1 - \frac{64}{980} \right) \times 100 = 93.47\% \text{ reduksi byte data.}$$

### Manajemen Memori GPU
Citra yang diunduh harus didekompresi ke dalam memori VRAM GPU sebagai bitmap mentah:
$$\text{Konsumsi Memori} = \text{Lebar} \times \text{Tinggi} \times 4 \text{ bytes (RGBA)}$$
Citra statis 4000x3000px mengonsumsi $\approx 48\text{ MB}$ VRAM terlepas dari apakah ukuran file terkompresinya hanya 200 KB. Menyajikan ukuran yang disesuaikan secara proporsional melalui `srcset` mencegah *Out-Of-Memory (OOM) browser crash* pada perangkat low-end.

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Mitigasi Serangan Vektor SVG (Cross-Site Scripting)
SVG adalah dokumen XML yang dapat mengeksekusi JavaScript. Jika platform Anda menerima upload SVG dari pengguna:
* **Risiko:** Inline `<svg><script>alert(document.cookie)</script></svg>` dapat membajak session pengguna.
* **Hardening:**
  * Sajikan SVG selalu melalui tag `<img>`, bukan di-render inline via `dangerouslySetInnerHTML` atau sejenisnya. Gambar yang dipanggil via tag `<img>` menonaktifkan eksekusi script engine di sebagian besar browser standar.
  * Terapkan header Content Security Policy (CSP):
    ```http
    Content-Security-Policy: default-src 'self'; image-src 'self' https://assets.cdn-supplier.com data:; script-src 'self';
    ```

### 2. Subresource Integrity (SRI) pada Preloaded Assets
Ketika memuat aset dari CDN publik menggunakan resource hint:
```html
<link 
  rel="preload" 
  href="https://assets.cdn-supplier.com/lib/animation-core.js" 
  as="script" 
  integrity="sha384-oqVuAfXRKap7fdgcCY5uykM6+R9GqQ8K/uxy9rx7HNQlGYl1kPzQho1wx4JwY8wC" 
  crossorigin="anonymous"
>
```
Hal ini memastikan bahwa jika CDN mengalami intrusi dan file dimodifikasi, browser akan menolak mengeksekusi payload yang rusak tersebut.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### 1. Memeriksa Dynamic Network Decision Melalui DevTools
1. Buka **Chrome DevTools** $\rightarrow$ Tab **Network**.
2. Aktifkan kolom **Priority** (klik kanan header kolom $\rightarrow$ centang *Priority*).
3. Filter berdasarkan `Img`.
4. Amati kolom **Initiator**:
   * Jika nilainya *Preload Scanner* / *parser*, resource hint bekerja.
   * Jika nilainya CSS file atau script file, browser mengalami penundaan eksekusi fetch.

### 2. Monitoring Runtime dengan PerformanceObserver API
Gunakan skrip telemetri berikut untuk memantau waktu unduh dan mendeteksi aset yang memicu layout shift secara langsung dari browser pengguna:

```javascript
// Telemetri Kinerja Pengiriman Media
if ('PerformanceObserver' in window) {
  // 1. Audit Largest Contentful Paint (LCP)
  const lcpObserver = new PerformanceObserver((entryList) => {
    const entries = entryList.getEntries();
    const lastEntry = entries[entries.length - 1];
    
    console.group('[Telemetry] LCP Detection');
    console.log('LCP Element:', lastEntry.element);
    console.log('LCP Render Time:', `${lastEntry.renderTime || lastEntry.loadTime} ms`);
    console.log('LCP Resource URL:', lastEntry.url);
    console.groupEnd();
  });
  lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });

  // 2. Audit Cumulative Layout Shift (CLS) Akibat Media
  const clsObserver = new PerformanceObserver((entryList) => {
    for (const entry of entryList.getEntries()) {
      if (!entry.hadRecentInput) {
        entry.sources?.forEach((source) => {
          if (source.node && source.node.nodeName === 'IMG') {
            console.warn('[Telemetry] Layout Shift Detected pada Node:', source.node);
            console.warn('Pergeseran Nilai CLS:', entry.value);
