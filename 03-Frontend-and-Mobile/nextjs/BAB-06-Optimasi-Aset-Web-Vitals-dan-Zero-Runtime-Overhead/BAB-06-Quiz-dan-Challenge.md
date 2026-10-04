# BAB 06: Quiz, Challenge, & Knowledge Check
**Optimasi Aset, Web Vitals, & Zero-Runtime Overhead**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi dan Mekanisme Viewport Sizing pada `next/image`**  
   Jelaskan secara mendalam bagaimana atribut `sizes` pada komponen `next/image` berinteraksi dengan browser layout engine sebelum file gambar selesai diunduh. Mengapa kelalaian dalam mendefinisikan `sizes` pada gambar responsif dengan `fill` dapat memicu pengunduhan aset beresolusi *desktop* pada perangkat *mobile*, dan bagaimana hal tersebut secara langsung merusak metrik *Largest Contentful Paint* (LCP)?

2. **Zero Layout Shift via Font Metric Overrides**  
   Bagaimana modul `next/font` (baik `next/font/google` maupun `next/font/local`) secara matematis mengeliminasi *Cumulative Layout Shift* (CLS)? Jelaskan peran injeksi CSS properties `@font-face` sintetis seperti `size-adjust`, `ascent-override`, `descent-override`, dan `line-gap-override` dalam menyamakan dimensi metrik font cadangan (*fallback font*) dengan *custom web font* sebelum proses *font swap* selesai.

3. **Lifecycle Script Execution Strategy**  
   Bandingkan siklus hidup (*lifecycle*) eksekusi dari empat strategi pemuatan komponen `next/script`: `beforeInteractive`, `afterInteractive`, `lazyOnload`, dan `worker`. Kapan browser mengeksekusi masing-masing skrip relatif terhadap parsing DOM, *hydration process*, dan *load event* window? Sebutkan use-case kritis di level produksi untuk masing-masing strategi.

4. **Paradigma Runtime CSS-in-JS vs. Zero-Runtime / Build-Time Styling**  
   Mengapa library *runtime CSS-in-JS* tradisional (seperti Styled-Components atau Emotion) menjadi antipattern di arsitektur Next.js App Router (React Server Components)? Jelaskan mekanisme *cost of runtime* (parsing JavaScript, dynamic style injection ke DOM tree, hydration mismatch) dan bandingkan dengan pendekatan *zero-runtime* (Tailwind CSS, CSS Modules, Vanilla Extract, atau StyleX) dari perspektif ukuran *main-thread blocking time*.

5. **Dekomposisi Metrik Interaction to Next Paint (INP)**  
   Metrik INP resmi menggantikan First Input Delay (FID) sebagai Core Web Vital. Uraikan 3 fase penyusun durasi INP: *Input Delay*, *Processing Duration*, dan *Presentation Delay*. Bagaimana arsitektur *client-side hydration* yang monolitik pada Next.js dapat secara drastis mendegradasi metrik *Processing Duration* dan *Presentation Delay* saat user berinteraksi dengan elemen UI interaktif?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Analisis Regresi Waterfall LCP: `loading="lazy"` vs `priority`**  
   Sebuah *Hero Image* dideklarasikan menggunakan `next/image`. Saat diaudit melalui Chrome DevTools Performance panel, tercatat LCP berada di angka 4.8 detik dengan rincian *Resource Load Delay* mencapai 72% dari total durasi LCP. Telusuri rantai eksekusi browser engine: apa yang terjadi jika engineer secara tidak sengaja membiarkan *Hero Image* memiliki flag default `loading="lazy"` alih-alih `priority`, dan bagaimana browser *Preload Scanner* memperlakukan kedua kondisi tersebut?

2. **DDoS Vector & Cache Eviction pada Image Optimization API**  
   Endpoint bawaan Next.js `/_next/image` melakukan *on-the-fly image optimization* menggunakan library libvips/sharp di sisi server. Jelaskan skenario di mana konfigurasi default `images.deviceSizes` dan `images.imageSizes` di `next.config.js` yang tidak dibatasi dapat dieksploitasi untuk menyebabkan *CPU saturation* dan *Memory Denial-of-Service* (OOM Crash). Bagaimana mekanisme *caching layer* bawaan Next.js bekerja untuk memvalidasi *request parameters* (`w`, `q`, `url`)?

3. **Diagnostik Font Desynchronization: FOIT vs. FOUT**  
   Anda mengonfigurasi `next/font` dengan `display: 'swap'`. Namun, pengguna pada jaringan 3G melaporkan terjadinya teks "meloncat" secara vertikal sejauh 8px sesaat setelah web font selesai di-render, meskipun properti `adjustFontFallback` aktif. Lakukan *root cause analysis* terhadap skenario ini: faktor apa pada *variable font axes* (misalnya `wght`, `wdth`, `opsz`) atau deklarasi `@font-face` lokal kustom yang dapat menggagalkan kalkulasi otomatis *bounding box metrics* Next.js?

4. **Web Worker Offloading via Partytown (`strategy="worker"`)**  
   Saat memindahkan Google Tag Manager atau analitik pihak ketiga ke Web Worker menggunakan `next/script` dengan `strategy="worker"`, jelaskan mekanisme sinkronisasi data yang terjadi antara Web Worker thread dan Main Thread. Mengapa metode pemanggilan `document.cookie` atau `window.dataLayer.push()` dari worker thread dapat memicu *synchronous postMessage bottleneck* atau masalah *CORS sandbox* jika tidak di-proxy secara benar?

5. **Modularize Imports, Package Exports, dan Tree-Shaking Degradation**  
   Perhatikan kode berikut:
   ```typescript
   import { ArrowRight, Check, Search } from 'lucide-react';
   import { debounce } from 'lodash';
   ```
   Meskipun kedua pustaka mendukung ES Modules, hasil build `@next/bundle-analyzer` menunjukkan ratusan ikon lain ikut terbawa ke dalam bundle halaman tersebut. Jelaskan mengapa static AST analysis dari Webpack/Turbopack gagal melakukan tree-shaking secara optimal pada struktur paket barrel file tersebut, dan bagaimana opsi `modularizeImports` atau `optimizePackageImports` di `next.config.js` merekonstruksi AST import path secara internal untuk mengatasi masalah ini.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden OOM dan Degradasi LCP pada Skala Flash-Sale
*Sebuah platform e-commerce multi-kategori skala nasional meluncurkan halaman promo Midnight Flash Sale menggunakan Next.js App Router. Dalam 5 menit pertama, traffic melonjak hingga 450.000 Request Per Minute (RPM). Server farm (Node.js runtime di Kubernetes cluster) mengalami CPU Throttling 100% dan pod restart berulang kali akibat Out-Of-Memory (OOM) Killed. Metrik LCP global anjlok dari 1.8 detik ke 9.4 detik.*

*Investigasi awal menunjukkan bahwa halaman promo memuat grid katalog berisi 60 produk, di mana seluruh gambar menggunakan `next/image` dengan sumber URL dinamis dari AWS S3. Format gambar asli dari S3 berukuran rata-rata 4000x3000 piksel (resolusi kamera mentah tanpa pre-processing).*

**Pertanyaan Diagnostik:**
1. Bedah bagaimana pipeline `/_next/image` bawaan mengeksekusi request dalam skenario volume masif ini. Mengapa server node kehabisan memori secara eksponensial meskipun aset gambar di-serve dari bucket external S3?
2. Rancang solusi arsitektural komprehensif yang mencakup:
   - Modifikasi `next.config.js` (pengaturan cache TTL, loader kustom, domains vs remotePatterns).
   - Penentuan *Offloading strategy*: Kapan harus memutus pipeline `/_next/image` server-side dan beralih ke Dedicated Image CDN (misal Cloudinary, Imgix, atau Cloudflare Images Worker).
   - Optimasi layout atribut komponen (penggunaan `sizes`, decoding, format WebP/AVIF).

---

### Skenario B: Layout Instability Masif Akibat Late Hydration & Dynamic Web-Font Injection
*Sebuah portal berita online global mengalami penalti ranking SEO Google Core Web Vitals secara tiba-tiba karena metrik CLS melonjak menjadi 0.42 pada perangkat seluler. Analisis visual recording via PageSpeed Insights menunjukkan bahwa layout halaman berita terdorong ke bawah dalam dua tahap yang berbeda:*
1. *Tahap 1 (Detik ke 1.2): Header dan paragraf utama bergeser ke bawah sebesar 34px saat font lokal kustom diunduh dan menggantikan sistem fallback.*
2. *Tahap 2 (Detik ke 2.8): Blok artikel bergeser lagi sebesar 120px ke bawah ketika script injection pihak ketiga (AdSense script banner yang dipasang menggunakan inline dynamic script tag di dalam `useEffect`) merender slot iklan di atas judul berita tanpa alokasi dimensi container.*

**Pertanyaan Diagnostik:**
1. Bagaimana Anda merestrukturisasi sistem tipografi aplikasi menggunakan `next/font/local` untuk menghasilkan *metric-matched fallback* yang meniadakan pergeseran 34px pada Tahap 1 secara mutlak?
2. Bagaimana Anda mengoreksi arsitektur penayangan iklan pada Tahap 2 menggunakan kombinasi `next/script` dan teknik *CSS aspect-ratio placeholder reservation* agar slot iklan tidak memicu Cumulative Layout Shift meskipun respons jaringan iklan terlambat atau gagal termuat?

---

### Skenario C: Krisis INP (Interaction to Next Paint) pada Monorepo Berbasis Legacy CSS-in-JS
*Sebuah aplikasi SaaS Enterprise yang menggunakan Next.js App Router mengintegrasikan Design System legacy berbasis Emotion (`@emotion/react` dan `@emotion/styled`) melalui adapter client component wrappers (`'use client'`). Setelah audit metrik lapangan (CrUX), nilai INP p75 di mobile mencapai 480ms (kategori Poor, threshold target: < 200ms).*

*Profiling traces menunjukkan bahwa ketika user mengklik tombol filter data tabel yang kompleks, thread browser mengalami Long Task selama 380ms. Dari waktu tersebut, 220ms dihabiskan oleh fungsi internal Emotion (`serializeStyles`, `insertStyles`, dan style tag injection via `document.head.appendChild`) yang dijalankan secara berulang pada ratusan elemen baris tabel yang di-render ulang secara bersamaan.*

**Pertanyaan Diagnostik:**
1. Jelaskan secara mendalam mengapa runtime injection stylesheet oleh library CSS-in-JS menghambat fase *Presentation Delay* pada metrik INP di level rendering pipeline browser (Recalculate Style, Layout, Paint, Composite).
2. Susun strategi refactoring arsitektur komponen tanpa harus merombak 100% kode basis secara instan:
   - Bagaimana membagi komponen antara Server Components dan Client Leaves untuk membatasi overhead Emotion?
   - Opsi styling pengganti apa (*zero-runtime*) yang dapat diintegrasikan secara hybrid dalam satu Next.js project untuk menekan execution time menjadi < 50ms per interaksi?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Media & Asset Pipeline Engine
Rancang dan implementasikan arsitektur halaman landing media interaktif performa tinggi dengan target absolut: **Lighthouse Performance Score 100/100, Core Web Vitals (LCP < 1.2s, CLS = 0, INP < 50ms) pada simulasi emulasi "Slow 4G & Mid-Tier Mobile (4x CPU Slowdown)".**

#### Problem Statement
Sebuah landing page kampanye peluncuran produk memiliki:
- 1 x Full-bleed Ultra-HD Responsive Hero Image (kandidat LCP).
- Tipografi kustom non-Google font (Inter Display & Editorial Serif) via file WOFF2 lokal.
- 1 x Heavy Third-Party Analytics tracker (Simulasi Google Tag Manager + Segment tracker) yang memblokir rendering.
- 1 x Grid Media 12-item dengan dynamic aspect ratios yang berisiko layout shift.
- Masalah bundle bloat akibat import icon set besar secara naif.

#### Requirements & Constraints
1. **App Router Only**: Implementasikan pada Next.js 14+/15 (App Router).
2. **Image Architecture**:
   - Hero Image harus menggunakan `next/image` dengan setup responsif murni (`sizes`), memanfaatkan format AVIF dengan WebP fallback, dan prioritas tinggi tanpa membebani preload bandwith secara berlebih.
   - Wajib menyertakan *Base64 Blur Placeholder* inline ultra-ringan yang di-generate saat build-time/server-side (bukan hardcoded random string).
   - Media Grid harus menerapkan progressive lazy-loading dengan intersection observer thresholding yang tepat.
3. **Typography Architecture**:
   - Gunakan `next/font/local`. Deklarasikan fallback fonts yang disetel presisi menggunakan `adjustFontFallback` atau penyesuaian metrik manual (`ascentOverride`, `descentOverride`) sehingga transisi font menghasilkan CLS persis `0.000`.
4. **Third-Party Script Isolation**:
   - Offload analytic scripts keluar dari Main Thread secara penuh menggunakan `strategy="worker"` via Partytown atau integrasi sandboxed custom execution.
5. **Styling & Bundle Footprint**:
   - Zero-runtime overhead. Gunakan Tailwind CSS atau CSS Modules. Dilarang keras menggunakan runtime CSS injection.
   - Konfigurasikan `next.config.js` untuk mengaktifkan `optimizePackageImports`, AVIF support, dan pengetatan domain resource.
   - Total ukuran JavaScript awal (*First Load JS Shared*) untuk halaman ini tidak boleh melebihi **75 KB**.

#### Expected Output
1. File `next.config.mjs`: Konfigurasi komprehensif (`images`, `experimental.optimizePackageImports`, asset header caching).
2. File `app/layout.tsx`: Konfigurasi tipografi `next/font/local` dengan injection CSS variables yang terisolasi dan script loading pipeline.
3. File `app/page.tsx`: Implementasi komponen UI lengkap (Hero LCP candidate dengan `blurDataURL` dinamis, Responsive Media Grid, Interactive Component yang menguji INP).
4. Penjelasan analitis ringkas (maksimal 300 kata) mengenai *Waterfall Execution Diagram* yang membuktikan bagaimana arsitektur Anda menjamin tidak ada *Main Thread Congestion* pada saat initial paint.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal dan komparasi performa antara format gambar modern (AVIF vs WebP vs MozJPEG) serta rasio kompresi vs waktu komputasi decoding CPU.
- [ ] Cara browser layout engine memproses *CSS Box Model* saat transisi *Font Swapping* dan peran kalkulasi matematis `font-display: swap` yang diimbangi *fallback metric overrides*.
- [ ] Seluruh tahapan pipeline metrik Core Web Vitals: LCP (Time to First Byte, Resource Load Delay, Resource Load Duration, Element Render Delay), CLS (Impact Fraction x Distance Fraction), dan INP (Input Delay, Processing Time, Presentation Delay).
- [ ] Perbedaan eksekusi skrip browser antara `async`, `defer`, dan Next.js strategies (`beforeInteractive`, `afterInteractive`, `lazyOnload`, `worker`).
- [ ] Keterbatasan struktural arsitektur *Dynamic CSS-in-JS* pada ekosistem React Server Components (RSC) dan dampaknya terhadap *Garbage Collection* serta *Style Recalculation*.
- [ ] Mekanisme kerja Turbopack / Webpack Tree-Shaking, peran file `package.json` (`sideEffects: false`), dan mitigasi *re-export bloat* pada barrel files.

### Saya tidak perlu menghafal:
- [ ] Nilai persentase metrik biner eksak dari setiap font di dunia untuk `ascent-override` dan `descent-override` (hal ini dihitung otomatis oleh `next/font` engine pada saat build time).
- [ ] Format biner spesifikasi internal algoritma kompresi Brotli atau Gzip.
- [ ] Seluruh tabel konfigurasi mentah penyesuaian parameter `libvips` C++ image processing library.

### Saya harus bisa melakukan:
- [ ] Membaca, menganalisis, dan mendiagnosis file trace rekaman *Chrome DevTools Performance Panel* untuk menemukan Long Tasks (>50ms) dan rendering bottlenecks.
- [ ] Mengonfigurasi `next/image` secara optimal menggunakan kombinasi properti `sizes`, `priority`, `placeholder="blur"`, dan `blurDataURL` untuk memastikan LCP < 1.5 detik.
- [ ] Menghilangkan CLS font secara total dengan mengonfigurasi `next/font/google` atau `next/font/local` dengan mapping CSS variables.
- [ ] Mengisolasi beban kerja third-party scripts (tag manager, tracking pixels, customer chats) ke Web Worker thread menggunakan `next/script` dan Partytown.
- [ ] Mengaudit ukuran bundle aplikasi menggunakan `@next/bundle-analyzer` dan mengeksekusi optimasi dependensi melalui `optimizePackageImports` di `next.config.js`.
- [ ] Menulis arsitektur antarmuka modern yang strictly *zero-runtime styling overhead* untuk menjamin sub-50ms Interaction to Next Paint (INP).