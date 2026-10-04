# BAB 05: Quiz, Challenge, & Knowledge Check
**Media Responsif, Resource Hints, dan Optimasi Aset**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Resolusi Switching vs Art Direction:**
   Jelaskan perbedaan mendasar antara kebutuhan *Resolution Switching* (menggunakan `srcset` dan `sizes` pada elemen `<img>`) dan *Art Direction* (menggunakan elemen `<picture>` dan `<source media="...">`). Mengapa menyerahkan pemilihan resolusi gambar ke browser via `srcset`/`sizes` lebih optimal untuk performa rendering dibandingkan memaksakannya menggunakan CSS `background-image` atau query media imperatif?

2. **Peran Kritis Atribut `sizes` Terhadap Browser Preload Scanner:**
   Ketika browser melakukan parsing awal dokumen HTML, *speculative preload scanner* belum mengeksekusi CSS Object Model (CSSOM). Bagaimana atribut `sizes` menjembatani kesenjangan informasi ini sehingga browser dapat memilih kandidat gambar yang tepat dari `srcset` sebelum layout engine menghitung dimensi elemen sebenarnya?

3. **Taksonomi Resource Hints (`preload`, `prefetch`, `preconnect`, `dns-prefetch`):**
   Bedakan siklus hidup (*lifecycle*), alokasi prioritas antrean (*fetch priority queue*), dan konteks penggunaan yang tepat antara:
   - `rel="preload"`
   - `rel="prefetch"`
   - `rel="preconnect"`
   - `rel="dns-prefetch"`
   Jelaskan risiko performa jika engineer menggunakan `rel="preload"` secara berlebihan (*over-preloading*).

4. **Anatomi Cumulative Layout Shift (CLS) Terkait Media:**
   Secara spesifikasi rendering engine (Blink/WebKit), jelaskan bagaimana kombinasi atribut `width` dan `height` pada elemen `<img>` modern bekerja sama dengan properti CSS `aspect-ratio` untuk mengeliminasi CLS sebelum binary gambar selesai diunduh. Mengapa metode lama (menghilangkan atribut dimensi dan hanya mengandalkan CSS `width: 100%; height: auto;`) memicu *layout thrashing*?

5. **Dekoding Asinkron vs Native Lazy Loading:**
   Bandingkan mekanisme internal browser antara atribut `decoding="async"` dan `loading="lazy"`. Pada fase pipeline rendering mana masing-masing atribut bekerja (Network fetch phase, DOM layout, atau Compositing/Raster phase)? Mengapa menerapkan `loading="lazy"` pada gambar Largest Contentful Paint (LCP) merupakan anti-pattern fatal?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Resource Hints Priority Inversion & HTTP/2-HTTP/3 Streams:**
   Anda menambahkan `<link rel="preload" as="image" href="hero.avif" fetchpriority="high">` di dalam `<head>`. Namun, pada network waterfall, file CSS kritis (`critical.css`) terdorong ke bawah dan mengalami delay transfer data. Analisis bagaimana browser scheduler mengatur *stream dependency trees* pada HTTP/2 atau HTTP/3 multiplexing ketika dihadapkan pada tabrakan resource berprioritas tinggi, dan bagaimana Anda mengatasinya.

2. **Debugging Evaluasi Ukuran Viewport pada `sizes` Attribute:**
   Diberikan markup berikut:
   ```html
   <img srcset="small.webp 400w, medium.webp 800w, large.webp 1200w"
        sizes="(max-width: 768px) 100vw, 50vw"
        src="fallback.jpg" alt="Campaign Banner">
   ```
   Pengguna dengan layar 414px CSS width dan Device Pixel Ratio (DPR) 3.0 membuka halaman ini. Kandidat gambar mana yang akan diunduh oleh browser? Tunjukkan langkah kalkulasi matematis *effective pixel density* yang dilakukan browser rendering engine.

3. **Memory Leak dan Resource Waste pada Elemen `<video>`:**
   Sebuah halaman landing page menggunakan background video loop:
   ```html
   <video autoplay loop muted playsinline preload="auto">
     <source src="bg.webm" type="video/webm">
     <source src="bg.mp4" type="video/mp4">
   </video>
   ```
   Ketika diaudit pada perangkat low-end mobile, terjadi frame dropping berat dan penggunaan memori melonjak hingga browser crash (*OOM killer*). Analisis apa yang salah dengan konfigurasi markup di atas dalam hal manajemen buffer, decoding hardware, dan strategi responsif berbasis bandwidth/daya.

4. **Edge Case: Kegagalan Negosiasi Format Gambar `<picture>`:**
   Sebuah CDN diatur untuk melakukan konversi on-the-fly, tetapi markup ditulis sebagai berikut:
   ```html
   <picture>
     <source srcset="image.avif" type="image/avif">
     <source srcset="image.webp" type="image/webp">
     <img src="image.jpg" alt="Thumbnail" loading="lazy">
   </picture>
   ```
   Jika server CDN mengembalikan respons `404 Not Found` untuk `image.avif`, jelaskan apakah browser akan otomatis melakukan *fallback* ke `image.webp`, atau menghentikan rendering gambar sama sekali? Rujuk spesifikasi HTML parsing algorithm terkait pemilihan sumber `<source>`.

5. **Interaksi `fetchpriority` dengan Script dan Font Preloading:**
   Jelaskan apa yang terjadi di internal browser resource scheduler jika Anda mengonfigurasi:
   ```html
   <link rel="preload" href="/fonts/inter.woff2" as="font" type="font/woff2" crossorigin>
   <script src="/js/bundle.js" async fetchpriority="low"></script>
   <img src="/img/lcp.webp" fetchpriority="high">
   ```
   Bagaimana browser mengurutkan prioritas ketiga resource ini sejak fase *speculative parsing* hingga fase *DOM Ready*? Faktor internal apa yang membuat font tetap berisiko menyebabkan layout shift (FOIT/FOUT) meskipun telah di-preload?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Regresi Masif Core Web Vitals (LCP & CLS) Pasca Migrasi Format Modern
Sebuah platform e-commerce skala besar melakukan refactoring dari format JPEG ke WebP/AVIF untuk 2.000.000 gambar produk. Tim frontend mengimplementasikan komponen responsif baru. Dua hari pasca deploy, Google Search Console melaporkan regresi fatal:
- Skor **LCP (Largest Contentful Paint)** melonjak dari 1.8 detik menjadi 4.6 detik pada perangkat mobile 4G.
- Skor **CLS (Cumulative Layout Shift)** naik dari 0.02 menjadi 0.28.

Setelah dilakukan audit DevTools pada halaman detail produk, ditemukan potongan kode berikut:
```html
<div class="product-gallery">
  <picture>
    <source type="image/avif" srcset="product-mobile.avif 480w, product-desktop.avif 1024w">
    <source type="image/webp" srcset="product-mobile.webp 480w, product-desktop.webp 1024w">
    <img src="fallback.jpg" loading="lazy" decoding="async" class="hero-image">
  </picture>
</div>
```
CSS yang menyertainya:
```css
.hero-image {
  width: 100%;
  height: auto;
}
```

**Pertanyaan Diagnostik:**
1. Bedah secara menyeluruh tiga kesalahan arsitektural fatal pada markup dan CSS di atas yang secara langsung memicu pembengkakan LCP dan CLS.
2. Tuliskan kode perbaikan (*refactored markup* & CSS) yang memenuhi standar *Core Web Vitals green threshold* tanpa menghilangkan dukungan AVIF/WebP responsif.

---

### Skenario B: Bandwidth Bleeding & Race Condition pada Asset Third-Party CDN
Sebuah portal berita mendistribusikan gambar artikel dari domain CDN terpisah (`https://assets.news-cdn.com`). Di dalam tag `<head>`, tim performa memasang:
```html
<link rel="preconnect" href="https://assets.news-cdn.com">
<link rel="preload" as="image" href="https://assets.news-cdn.com/top-news.webp">
```
Namun di bagian `<body>`, tim editorial menggunakan markup berikut dari CMS:
```html
<img src="https://assets.news-cdn.com/top-news.webp" 
     srcset="https://assets.news-cdn.com/top-news.webp?w=600 600w, https://assets.news-cdn.com/top-news.webp?w=1200 1200w" 
     sizes="(max-width: 600px) 100vw, 1200px" 
     alt="Berita Utama">
```
Audit network menunjukkan bahwa file `top-news.webp` diunduh **dua kali** oleh browser pada desktop view:
1. Permintaan pertama (initiator: `<link rel="preload">`)
2. Permintaan kedua (initiator: elemen `<img>`)

Selain itu, ditemukan pula warning pada Chrome DevTools Console: *“Resource was preloaded using link preload but not used within a few seconds from the window's load event.”*

**Pertanyaan Diagnostik:**
1. Mengapa browser mengunduh resource tersebut dua kali dan memicu console warning padahal URL target tampak identik? Jelaskan peran cache key matching dan atribut `imagesrcset`/`imagesizes`.
2. Bagaimana cara mengonfigurasi resource hint preload yang valid untuk gambar yang bersifat dinamis/responsif?
3. Apakah `<link rel="preconnect">` tetap bekerja optimal jika server CDN aset menggunakan CORS? Konfigurasi atribut apa yang hilang?

---

### Skenario C: Trade-off Arsitektur Streaming Video vs Format Animasi (WebM/MP4 vs GIF)
Aplikasi SaaS Analytics menyajikan animasi tutorial pada dashboard onboarding. Animasi asli dalam bentuk `.gif` berukuran 18 MB. Tim engineering menggantinya dengan loop video WebM dan MP4 untuk memangkas ukuran menjadi 1.2 MB:
```html
<video autoplay loop muted playsinline width="800" height="450">
  <source src="tutorial.webm" type="video/webm">
  <source src="tutorial.mp4" type="video/mp4">
</video>
```
Meskipun ukuran transfer berkurang 93%, tim QA menemukan masalah baru:
- Pada mode "Battery Saver" di sistem operasi mobile atau laptop, video macet atau menampilkan kotak hitam (*black frame*).
- Pada koneksi lemot (3G), rendering UI dashboard terblokir (*freeze*) selama 300-600ms ketika video mulai diinisialisasi oleh GPU.
- Pengguna yang mengaktifkan preferensi OS *Reduced Motion* (`prefers-reduced-motion: reduce`) tetap dipaksa memutar animasi tersebut.

**Pertanyaan Diagnostik:**
1. Mengapa pemutaran `<video>` via hardware acceleration dapat memicu UI freeze pada low-end hardware, dan bagaimana mekanisme `preload="none"` atau `preload="metadata"` memitigasi hal ini?
2. Bagaimana Anda merancang fallback arsitektur (menggunakan kombinasi HTML `<picture>`, `<video>`, CSS media query, atau JavaScript non-intrusif) yang secara elegan menghormati settingan `prefers-reduced-motion: reduce` pengguna, namun tetap menyajikan video performan bagi pengguna normal?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Hero Component Engine

#### Problem Statement
Anda ditugaskan merancang arsitektur komponen **Hero Section** untuk situs berita global yang memiliki regulasi performa ekstrem:
- **LCP** harus di bawah 1.2 detik pada jaringan Fast 3G.
- **CLS** bernilai mutlak `0`.
- Dukungan gambar harus mencakup resolusi multi-layar, art-direction berbeda antara mobile (rasio 4:3, fokus potret) dan desktop (rasio 16:9, lanskap lebar), serta format modern (AVIF, WebP, fallback JPEG) yang dilayani dari origin terpisah (`https://cdn.globalnews.com`).

#### Requirements
1. **Konstruksi `<head>` (Resource Hints & Preloading):**
   - Lakukan spekulasi koneksi yang tepat ke domain CDN.
   - Preload gambar LCP kandidat terbaik secara responsif dari `<head>` sehingga browser speculative scanner dapat langsung mendownload varian mobile atau desktop yang sesuai dengan orientasi viewport sebelum CSS eksternal diproses.
2. **Konstruksi `<body>` (Responsive Media Markup):**
   - Gunakan elemen `<picture>` yang menyertakan art-direction:
     - Mobile: Viewport `< 768px`, rasio 4:3 (kandidat lebar 400px dan 800px).
     - Desktop: Viewport `>= 768px`, rasio 16:9 (kandidat lebar 1200px dan 1600px).
   - Pastikan ada fallback pipeline format bertingkat: AVIF -> WebP -> JPEG.
   - Set instruksi decoding dan rendering engine priority yang tepat.
3. **Pemberantasan Layout Shift Tanpa CSS Eksternal (Zero-CLS Native HTML):**
   - Manfaatkan atribut native HTML5 layout reservation (`width`, `height`, inline styling bila mutlak diperlukan) untuk memastikan browser mengalokasikan aspect ratio box yang tepat sebelum gambar selesai di-render.

#### Constraints
- Dilarang keras menggunakan JavaScript untuk memanipulasi pemilihan gambar atau inject link preload.
- Dilarang keras memicu *double download* aset pada breakpoint transisi.
- Wajib menyertakan *accessible text container* yang aman bagi screen reader tanpa merusak komposisi responsif.

#### Expected Output
1. Blok kode HTML murni yang valid secara spesifikasi W3C/WHATWG yang memuat konfigurasi `<head>` dan komponen `<picture>` pada `<body>`.
2. Penjelasan teknis singkat (3-4 paragraf) yang mendokumentasikan:
   - Alasan penetapan `imagesrcset` dan `imagesizes` pada tag `<link rel="preload">`.
   - Bagaimana penentuan nilai `width` dan `height` pada elemen `<img>` di dalam `<picture>` menangani dua aspek rasio berbeda (4:3 vs 16:9) tanpa menimbulkan CLS.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan matematis kalkulasi browser antara pixel density descriptor (`x`) dan width descriptor (`w`).
- [ ] Mekanisme Browser Preload Scanner dan batasannya dalam membaca CSS Object Model (CSSOM).
- [ ] Mengapa `loading="lazy"` bekerja menggunakan threshold Intersection Observer internal browser dan dampaknya pada LCP.
- [ ] Siklus koneksi TCP, TLS Handshake, dan bagaimana `rel="preconnect"` serta `rel="dns-prefetch"` menghemat Round Trip Time (RTT).
- [ ] Algoritma evaluasi sumber pada elemen `<picture>`: urutan evaluasi `<source>` dari atas ke bawah dan ketiadaan fallback dinamis jika request HTTP menghasilkan status error (4xx/5xx).
- [ ] Hubungan antara atribut `width`/`height` rasio intrinsik HTML dengan properti CSS `aspect-ratio` untuk penentuan placeholder rendering box.
- [ ] Perbedaan fungsionalitas decoding thread: `decoding="async"`, `decoding="sync"`, dan `decoding="auto"`.

### Saya tidak perlu menghafal:
- [ ] Tabel heksadesimal representasi header file binary gambar (Magic Numbers JPEG/AVIF/WebP).
- [ ] Matriks resolusi layar dari setiap merk dan tipe perangkat mobile di pasaran (cukup gunakan representasi breakpoint fluid).
- [ ] Spesifikasi matematis algoritma kompresi wavelet AV1 / VP9 di tingkat C++/assembly library libavif/libvpx.
- [ ] Syntax konfigurasi internal server web (Nginx/Apache/Caddy) untuk MIME types (cukup pahami deklarasi `type="image/..."` di level HTML).

### Saya harus bisa melakukan:
- [ ] Menulis markup responsive image (`srcset`, `sizes`, `<picture>`) tanpa bantuan framework atau compiler abstraction.
- [ ] Menghitung nilai string `sizes` secara akurat berdasarkan layout grid responsif desktop, tablet, dan mobile.
- [ ] Mengonfigurasi `<link rel="preload">` responsif menggunakan atribut `imagesrcset` dan `imagesizes`.
- [ ] Mendiagnosis penyebab double-download resource pada network waterfall DevTools.
- [ ] Mengukur dan mengeliminasi kontribusi media terhadap metrik Core Web Vitals (LCP, CLS) menggunakan Chrome DevTools / Lighthouse.
- [ ] Mengimplementasikan media fallback bertingkat (Modern Formats -> Legacy Formats) dengan validasi parsing standar browser engine.