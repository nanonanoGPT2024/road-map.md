## SEKSI 01 — IDENTITAS MODUL

*   **ID Modul**: `FED-01-CF-10-01`
*   **Kategori**: `01-Core-Foundations`
*   **Jalur Kurikulum**: `frontend-beginner`
*   **Bab**: 10 — Tooling Modern, Otomatisasi Rilis, dan Optimasi Performa
*   **Judul Modul**: Modern Build Tools, Deployment Pipeline & Audit Kinerja
*   **Tingkat Kesulitan**: Beginner to Intermediate Transition
*   **Estimasi Waktu Belajar**: 300 Menit (Teori: 90 Menit, Praktik Terpandu: 120 Menit, Evaluasi: 90 Menit)
*   **Prasyarat**:
    *   Penguasaan JavaScript Modern (ES6+ Modules: `import`/`export`, Promises, Async/Await).
    *   Pemahaman dasar arsitektur web: DOM, CSS Object Model, Request-Response HTTP lifecycle.
    *   Pengoperasian Terminal/CLI: Navigasi direktori, manipulasi file, eksekusi skrip Node.js.
    *   Dasar-dasar Version Control System: Git (`add`, `commit`, `push`, `branch`, GitHub repository management).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik memiliki kemampuan terukur untuk:

1.  **Menganalisis dan Membedakan Mekanisme Tooling (C4 - Analysis)**: Menjelaskan perbedaan fundamental antara unbundled development server berbasis Native ES Modules (Vite/esbuild) dan bundled production build (Rollup), serta menentukan tooling yang tepat berdasarkan kebutuhan proyek.
2.  **Mengonfigurasi Lingkungan Build Produksi (C3 - Application)**: Membangun konfigurasi Vite dari nol (`vite.config.js`), mengonfigurasi *path alias*, *asset hashing*, *environment variables*, dan pemisahan *chunks* (*code-splitting*).
3.  **Merancang dan Mengotomatisasi CI/CD Pipeline (C6 - Creation)**: Menyusun alur kerja GitHub Actions (`.github/workflows/*.yml`) yang secara otomatis memvalidasi integritas kode (*linting*, pengujian dasar) dan mengeksekusi *deployment* statis ke penyedia *edge hosting* (Cloudflare Pages atau Vercel).
4.  **Melakukan Audit dan Optimasi Performa Web (C5 - Evaluation)**: Mengukur metrik *Core Web Vitals* (LCP, INP, CLS) menggunakan Google Lighthouse dan Chrome DevTools, mengidentifikasi *bottleneck* aset kritis, serta mengimplementasikan mitigasi teknis untuk mencapai skor performa $\ge 90$.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
[Aplikasi Frontend Mentah (ES6+, SASS/PostCSS, Assets)]
                           │
                           ▼
          [Modern Build Engine (Vite)]
         ┌─────────────────┴─────────────────┐
         │ (Development Mode)                │ (Production Mode)
         ▼                                   ▼
 [Native ESM via HTTP]              [Rollup Compiler & Minifier]
 [Instant HMR via esbuild]          [Tree Shaking, Chunking, Hashing]
                                             │
                                             ▼
                                  [Distributable Output (dist/)]
                                             │
                                             ▼
                         [Continuous Integration / Delivery (CI/CD)]
                         [GitHub Actions: Lint -> Build -> Test]
                                             │
                                             ▼
                                 [Edge Static Hosting]
                         (Cloudflare Pages / Vercel / Netlify)
                                             │
                                             ▼
                                [Monitoring & Audit Kinerja]
                               ┌─────────────┴─────────────┐
                               ▼                           ▼
                     [Core Web Vitals]            [Lighthouse Audit]
                     - LCP (< 2.5s)               - Performance
                     - INP (< 200ms)              - Accessibility
                     - CLS (< 0.1)                - Best Practices / SEO
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pada era awal pengembangan web, arsitektur aplikasi frontend cukup mengandalkan file statis tunggal (`index.html`, `style.css`, `script.js`) yang diunggah langsung ke peladen web via FTP. Seiring transisi web menuju aplikasi berskala enterprise (*Single Page Applications*, modularitas komponen, dependensi pustaka pihak ketiga via npm), pendekatan konvensional menghadapi limitasi struktural:

1.  **Overhead Jaringan dan Latensi**: Memuat ratusan file JavaScript modular tanpa optimasi memicu ratusan *round-trip* permintaan HTTP/1.1 yang memblokir proses rendering browser (*waterfall problem*).
2.  **Ukuran Bundle yang Tidak Terkendali**: Tanpa proses eliminasi kode mati (*tree-shaking*) dan kompresi tingkat lanjut (*minification/uglification*), pengguna harus mengunduh megabyte kode yang tidak pernah dieksekusi.
3.  **Human Error dalam Rilis**: Deployment manual meningkatkan risiko inkonsistensi lingkungan (*"works on my machine"*), file yang terlewat, dan ketiadaan validasi regresi otomatis.
4.  **Dampak Finansial Performa Lambat**: Riset industri menunjukkan peningkatan waktu muat sebesar 100 milidetik dapat menurunkan tingkat konversi sebesar 7%. Google secara eksplisit menjadikan metrik *Core Web Vitals* sebagai variabel penentu peringkat pada algoritma Search Engine Optimization (SEO).

Mempelajari build tools, CI/CD, dan audit kinerja adalah jembatan yang mengubah seorang *coder* amatir menjadi perekayasa perangkat lunak (*software engineer*) web yang profesional dan berorientasi produksi.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Build Tools Generasi Baru (Next-Gen Build Tools)
Build tool adalah perangkat lunak yang mengotomatisasi transformasi kode sumber yang ditulis oleh pengembang (berisi sintaks modern, TypeScript, JSX, modul terpisah) menjadi aset web statis (HTML, CSS, JS) yang sangat teroptimasi dan kompatibel dengan browser target.
*   **Vite**: Alat tooling frontend modern yang memisahkan fase *development* (menggunakan *Native ES Modules* di browser dan *pre-bundling* dependensi berbasis Go via **esbuild**) dari fase *production* (menggunakan bundler berbasis Rollup).

### 2. Deployment Pipeline (CI/CD)
*   **Continuous Integration (CI)**: Praktik otomatisasi di mana setiap perubahan kode dalam repositori diuji secara berkala dengan menjalankan *linter*, pengecekan tipe (*type-check*), dan *unit test* sebelum digabungkan ke cabang utama.
*   **Continuous Delivery / Deployment (CD)**: Kelanjutan dari CI, di mana artifak kode yang telah lulus seluruh tahapan pengujian secara otomatis dikompilasi dan didistribusikan ke server staging atau produksi tanpa intervensi manual.

### 3. Core Web Vitals (CWV)
Inisiatif standarisasi Google untuk mengukur sinyal kualitas performa halaman web berdasarkan persepsi manusia secara riil (*real-user metrics*):
*   **Largest Contentful Paint (LCP)**: Mengukur kecepatan pemuatan. Waktu yang dibutuhkan browser untuk menampilkan elemen konten visual terbesar pada *viewport* (Target standar: $\le 2.5$ detik).
*   **Interaction to Next Paint (INP)**: Mengukur responsivitas runtime. Waktu latensi dari seluruh interaksi pengguna (klik, ketuk, penekanan tombol) hingga frame berikutnya di-render ke layar (Target standar: $\le 200$ milidetik). Menggantikan First Input Delay (FID).
*   **Cumulative Layout Shift (CLS)**: Mengukur stabilitas visual. Akumulasi pergeseran posisi layout yang tidak terduga dari elemen-elemen DOM yang terlihat selama halaman dimuat (Target standar: $\le 0.1$).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### A. Arsitektur Internal Vite: Dev vs. Production

```
DEVELOPMENT ARCHITECTURE:
[Browser] <--- Native ESM Request: /src/main.js <--- [Vite Dev Server]
[Browser] <--- Dynamic Import: /src/components/Header.js <-- (No Full Bundling)
* Dependencies diproses sekali di awal via esbuild (10-100x lebih cepat dari bundler JS).

PRODUCTION ARCHITECTURE:
[Source Code] ---> [Tree-Shaking] ---> [Code Splitting] ---> [Rollup Engine] ---> [dist/]
                                                                                  ├── index.html
                                                                                  ├── assets/main.a8b1c.js
                                                                                  └── assets/style.f3e2d.css
```

1.  **Fase Dev (On-Demand Compilation)**:
    Browser modern secara *native* mendukung `<script type="module">`. Vite tidak membundel ulang seluruh kode setiap kali ada perubahan file. Vite hanya bertindak sebagai peladen web statis yang menangani permintaan HTTP untuk file modul yang secara presisi diminta oleh browser. Ketika sebuah file diubah, Vite menggunakan *Hot Module Replacement* (HMR) berbasis WebSocket untuk mengganti modul terkait tanpa memuat ulang seluruh status aplikasi (*state*).
2.  **Fase Production (Deep Static Analysis)**:
    Untuk produksi, mengirim ratusan permintaan ESM melalui jaringan publik (Internet) menimbulkan latensi akibat round-trip TCP/TLS. Vite mengeksekusi Rollup untuk menghasilkan bundel teroptimasi:
    *   *Tree-shaking*: Analisis sintaks abstrak (AST) untuk mendeteksi dan menghapus fungsi yang diekspor tetapi tidak pernah diimpor.
    *   *Asset Inlining*: Mengonversi aset berukuran kecil (< 4KB) menjadi representasi string Data URL base64 guna menghemat pemanggilan jaringan.
    *   *Content Hashing*: Menyematkan hash kriptografis pada nama file output (misal: `app.7b9c1d.js`) untuk memaksimalkan efisiensi *HTTP Long-Term Caching*.

### B. Mekanisme Eksekusi CI/CD Pipeline

Pipeline dijalankan di atas lingkungan virtual (*container/virtual machine*) terisolasi yang diinisiasi oleh pemicu (*event trigger*), misalnya: `git push origin main`.

1.  **Checkout Code**: Mengkloning repositori ke runner runner pipeline.
2.  **Setup Runtime**: Menyiapkan Node.js dengan caching direktori paket (`~/.npm` atau `node_modules`).
3.  **Deterministic Dependency Installation**: Menjalankan `npm ci` (bukan `npm install`) untuk memastikan struktur dependensi yang terpasang presisi identik dengan yang terkunci di `package-lock.json`.
4.  **Static Verification**: Mengeksekusi linter dan unit testing. Jika terjadi galat (*error*), pipeline berhenti seketika (*fail-fast*), memblokir rilis rusak ke lingkungan publik.
5.  **Build Execution**: Menjalankan `npm run build` yang menghasilkan folder distribusi statis (`dist`).
6.  **Edge Ingestion**: Mengunggah artifak `dist/` ke CDN/Edge Storage provider.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Perbandingan Arsitektur: Bundler Klasik vs Vite

```text
BUNDLER-BASED DEV SERVER (Webpack, Rollup Legacy):
Entry File ───┐
Module A ─────┼──> [Bundler Memory Process] ──> [Bundle Tunggal] ──> [Server Siap]
Module B ─────┘     (Proses lambat saat skrip    (Ukuran besar)        (Menunggu lama)
                     mencapai ribuan modul)

VITE DEV SERVER (Unbundled Native ESM):
[Server Start Instan] ───> [Browser Mengakses URL]
                                   │
                                   ├──> Request /src/main.js ────────> Compile & Serve
                                   └──> Request /src/utils/math.js ──> Compile & Serve
                                        (Hanya compile apa yang diminta saat itu juga)
```

### 2. Alur CI/CD Deployment Menuju Edge Network

```text
Developer Machine              GitHub Repository                 Vercel / Cloudflare Edge
┌────────────────┐             ┌─────────────────┐             ┌─────────────────────────┐
│ git push main  │ ──────────> │ Webhook Event   │             │                         │
└────────────────┘             └────────┬────────┘             │                         │
                                        │                      │                         │
                                        ▼                      │                         │
                               ┌─────────────────┐             │                         │
                               │ GitHub Runner   │             │                         │
                               │ 1. npm ci       │             │                         │
                               │ 2. npm test     │             │                         │
                               │ 3. npm run build│             │                         │
                               └────────┬────────┘             │                         │
                                        │                      │                         │
                                        ▼ Artifacts (dist/)    │                         │
                               ┌─────────────────┐             │                         │
                               │ Deployment Task │ ──────────> │ Ingest to Edge Nodes    │
                               └─────────────────┘             │ Tokyo | SG | Frankfurt  │
                                                               └────────────┬────────────┘
                                                                            │ HTTP/3
                                                                            ▼
                                                                  [End User Browser]
```

### 3. Timeline Pengukuran Core Web Vitals (LCP, INP, CLS)

```text
[Navigasi Mulai]
       │
       ├─ TTFB (Time to First Byte) ────> HTML Diterima
       │
       ├─ FCP (First Contentful Paint) ─> Teks/Gambar pertama muncul di layar
       │
       ├─ LCP (Largest Contentful Paint)> Elemen gambar hero/heading utama selesai render
       │  [AMBANG BATAS IDEAL: < 2.5s]
       │
═══════╪══════════════════════════════════════════════════════════════════════════════════
 Siklus Interaksi (Runtime):
       │
       ├─ User Mengklik Tombol ─┐
       │                        ├─> Input Delay ──> Event Handler ──> Next Paint (INP)
       │ <──────────────────────┘   [AMBANG BATAS IDEAL: < 200ms]
       │
 Pergeseran Layout:
       │
       ├─ Gambar tanpa atribut width/height dimuat mendadak
       │  Layout teks terdorong ke bawah secara tiba-tiba (CLS Bertambah)
       │  [AMBANG BATAS IDEAL: < 0.1]
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah konfigurasi dasar proyek berbasis Vite murni (*Vanilla JavaScript*) yang dikonfigurasi untuk produksi.

### 1. Struktur Direktori
```text
my-vite-project/
├── index.html
├── package.json
├── vite.config.js
└── src/
    ├── main.js
    └── style.css
```

### 2. `package.json`
```json
{
  "name": "vite-starter",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "devDependencies": {
    "vite": "^5.2.0"
  }
}
```

### 3. `vite.config.js`
```javascript
import { defineConfig } from 'vite';

export default defineConfig({
  // Menentukan sub-path jika aplikasi di-host pada direktori publik non-root (opsional)
  base: './',
  build: {
    // Menargetkan browser modern yang mendukung native ES2020
    target: 'es2020',
    // Lokasi direktori output kompilasi
    outDir: 'dist',
    // Mengaktifkan visualisasi pelaporan ukuran chunk
    reportCompressedSize: true,
    // Batas ambang peringatan ukuran chunk dalam satuan kBs
    chunkSizeWarningLimit: 500,
  }
});
```

### 4. `index.html`
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vite Minimal Architecture</title>
  <link rel="stylesheet" href="./src/style.css">
</head>
<body>
  <div id="app">
    <h1>Memulai dengan Vite</h1>
    <button id="counter-btn">Klik: 0</button>
  </div>
  
  <!-- Titik masuk eksekusi Native ES Module -->
  <script type="module" src="./src/main.js"></script>
</body>
</html>
```

### 5. `src/main.js`
```javascript
let count = 0;
const button = document.getElementById('counter-btn');

button.addEventListener('click', () => {
  count += 1;
  button.textContent = `Klik: ${count}`;
});
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus Produksi Nyata: Sebuah aplikasi dashboard frontend yang memiliki:
1. Konfigurasi build tingkat lanjut dengan *manual chunking* (Rollup).
2. Pipeline GitHub Actions otomatis untuk deployment ke GitHub Pages.
3. Skrip instrumentasi telemetri performa untuk menangkap metrik Core Web Vitals secara real-time.

### 1. `vite.config.js` (Optimasi Lanjutan)

```javascript
import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  // Resolusi path alias agar impor file terstruktur rapi
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false, // Nonaktifkan di produksi demi keamanan dan ukuran aset
    minify: 'terser', // Menggunakan terser untuk optimasi kompresi mendalam
    terserOptions: {
      compress: {
        drop_console: true, // Menghapus console.log di produksi
        drop_debugger: true,
      },
    },
    rollupOptions: {
      output: {
        // Deterministic manual chunking: memisahkan vendor pihak ketiga
        manualChunks(id) {
          if (id.includes('node_modules')) {
            // Seluruh dependensi node_modules dikelompokkan ke dalam vendor chunk
            return 'vendor';
          }
        },
        // Pola penamaan aset untuk caching statis permanen
        entryFileNames: 'assets/js/[name]-[hash].js',
        chunkFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: ({ name }) => {
          if (/\.(gif|jpe?g|png|svg|webp|avif)$/.test(name ?? '')) {
            return 'assets/images/[name]-[hash][extname]';
          }
          if (/\.css$/.test(name ?? '')) {
            return 'assets/css/[name]-[hash][extname]';
          }
          return 'assets/[name]-[hash][extname]';
        },
      },
    },
  },
});
```

### 2. Otomatisasi CI/CD: `.github/workflows/deploy.yml`

```yaml
name: Production Deployment Pipeline

on:
  push:
    branches:
      - main

# Batasi izin runner sesuai prinsip least privilege
permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: 'pages'
  cancel-in-progress: true

jobs:
  build-and-validate:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Setup Node.js Runtime
        uses: actions/setup-node@v4
        with:
          node-version: 20.x
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Build Distributable Artifacts
        run: npm run build
        env:
          NODE_ENV: production

      - name: Upload Pages Artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: './dist'

  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build-and-validate
    steps:
      - name: Deploy to GitHub Pages Edge
        id: deployment
        uses: actions/deploy-pages@v4
```

### 3. Monitoring Core Web Vitals: `src/metrics.js`

Gunakan pustaka resmi `web-vitals` untuk mencatat performa langsung dari peramban pengguna.

```javascript
import { onCLS, onINP, onLCP } from 'web-vitals';

/**
 * Mengirimkan payload analitik performa ke peladen telemetri
 * @param {Object} metric - Objek metrik Web Vitals
 */
function sendToAnalytics(metric) {
  const body = JSON.stringify({
    name: metric.name,
    value: metric.value,
    rating: metric.rating, // 'good' | 'needs-improvement' | 'poor'
    delta: metric.delta,
    id: metric.id,
    navigationType: metric.navigationType,
    url: window.location.href,
    timestamp: Date.now()
  });

  // Gunakan navigator.sendBeacon jika didukung untuk mencegah pembatalan request saat navigasi ditutup
  if (navigator.sendBeacon) {
    navigator.sendBeacon('/api/analytics/vitals', body);
  } else {
    fetch('/api/analytics/vitals', {
      body,
      method: 'POST',
      keepalive: true,
      headers: {
        'Content-Type': 'application/json'
      }
    }).catch(err => console.error('Gagal mengirim metrik:', err));
  }
}

// Inisialisasi pengamatan metrik
export function registerPerformanceObserver() {
  // Largest Contentful Paint: Kecepatan memuat visual dominan
  onLCP(sendToAnalytics);
  
  // Interaction to Next Paint: Mengukur responsivitas interaksi tombol/form
  onINP(sendToAnalytics);
  
  // Cumulative Layout Shift: Stabilitas tata letak visual
  onCLS(sendToAnalytics);
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Dalam merancang siklus build dan deployment frontend, setiap keputusan arsitektur membawa kompromi sistem:

| Keputusan Arsitektural | Keuntungan (Pros) | Konsekuensi Negatif (Cons / Trade-offs) | Kapan Harus Digunakan |
| :--- | :--- | :--- | :--- |
| **Vite (Unbundled Dev) vs Webpack (Bundled Dev)** | Server startup instan ($<300$ms), HMR tidak terdegradasi seiring membesarnya ukuran codebase. | Perilaku lingkungan dev (ESM) berbeda secara teknis dari output bundle Rollup di produksi (*parity discrepancy*). | Standar de-facto proyek frontend modern (SPA, MPAs) skala baru hingga enterprise. |
| **Monolithic Bundle vs Aggressive Code Splitting** | Meminimalkan overhead HTTP handshake jika menggunakan HTTP/1.1; satu file selesai untuk semua rute. | Ukuran unduhan awal membengkak; browser mengeksekusi kode rute yang belum tentu dibuka pengguna (*high TBT & LCP*). | Aplikasi sangat kecil (< 50KB total JS code). |
| **Manual Vendor Splitting (`rollupOptions`)** | Meningkatkan rasio *cache hit*. Library seperti React/Lodash tidak diunduh ulang jika kode aplikasi berubah. | Menghasilkan dependensi sirkular jika dependensi internal vendor saling terkait; kompleksitas konfigurasi meningkat. | Aplikasi dengan dependensi pihak ketiga yang stabil dan berbobot besar. |
| **Static Edge Hosting (Vercel/Cloudflare Pages) vs Traditional NGINX/VM** | Zero-maintenance infrastructure, automasi SSL, mitigasi DDoS terdistribusi di ratusan edge locations global. | Kontrol server terbatas, tidak bisa melakukan operasi dinamis sisi server berat tanpa *serverless/edge functions*. | Aplikasi web berbasis Client-Side Rendering (CSR) atau Static-Site Generation (SSG). |

---

## SEKSI 11 — BEST PRACTICES

1.  **Penerapan Immutable HTTP Cache Headers**:
    Aset statis pada folder `dist/assets/` yang memiliki hash unik (misal: `index-Cz109x.js`) harus dilayani dengan header HTTP:
    `Cache-Control: public, max-age=31536000, immutable`
    File `index.html` **tidak boleh** di-cache secara permanen:
    `Cache-Control: public, max-age=0, must-revalidate`
2.  **Dimensi Eksplisit pada Konten Multimedia**:
    Cegah lonjakan skor CLS (*Cumulative Layout Shift*) dengan selalu menyertakan atribut `width` dan `height` atau CSS `aspect-ratio` pada tag `<img>` dan `<video>`:
    ```html
    <!-- Baik: Browser mencadangkan ruang rendering sebelum aset terunduh -->
    <img src="hero.webp" width="1200" height="600" alt="Hero Banner" fetchpriority="high">
    ```
3.  **Optimalisasi Largest Contentful Paint (LCP)**:
    Jika elemen LCP adalah gambar hero, gunakan resource hint `preload` dan atribut `fetchpriority="high"` untuk memerintahkan browser mengunduh aset tersebut sebelum CSS/JS sekunder tuntas dieksekusi:
    ```html
    <link rel="preload" as="image" href="/assets/hero.webp" fetchpriority="high">
    ```
4.  **Font Subsetting dan CSS `font-display`**:
    Hindari *Flash of Invisible Text* (FOIT) dengan menambahkan deklarasi `font-display: swap` pada setiap blok `@font-face`.
5.  **Gunakan `npm ci` di Lingkungan Server/CI**:
    Jangan pernah menggunakan `npm install` dalam alur kerja CI/CD. `npm ci` memastikan tidak adanya mutasi pada `package-lock.json` dan menghapus `node_modules` sebelum instalasi, menjamin *build reproducibility*.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Membocorkan Kunci Rahasia (*Secrets Leak*) via Variabel Lingkungan
*   **Kesalahan Fatal**: Menyimpan `API_SECRET_KEY` atau kata sandi basis data di dalam file `.env` dengan prefiks Vite (`VITE_`).
    ```ini
    # BAHAYA: Akan dibundel ke kode publik client-side
    VITE_STRIPE_SECRET_KEY=sk_live_abcdef123456
    ```
*   **Koreksi**: Hanya variabel yang aman dikonsumsi publik yang boleh menggunakan prefiks `VITE_` (misalnya: `VITE_FIREBASE_PUBLIC_API_KEY`). Kunci rahasia harus tetap berada di layer backend peladen/fungsi *serverless*.

### 2. Relative Path Breaks pada Routing Statis
*   **Masalah**: Konfigurasi `base` yang salah di `vite.config.js` menyebabkan aset gagal dimuat (terjadi error 404 pada CSS dan JS) saat di-deploy ke sub-path (seperti `https://username.github.io/repo-name/`).
*   **Koreksi**: Setel `base` sesuai nama repositori:
    ```javascript
    export default defineConfig({
      base: '/repo-name/',
    });
    ```

### 3. Mengabaikan Tree-Shaking Poisoning
*   **Masalah**: Melakukan impor library utilitas secara destruktif:
    ```javascript
    // Buruk: Menarik seluruh library lodash (puluhan kilobyte dieksekusi sia-sia)
    import _ from 'lodash';
    const active = _.filter(users, 'active');
    ```
*   **Koreksi**: Gunakan *named import* dari modul ES atau library yang modular:
    ```javascript
    // Baik: Hanya modul filter yang masuk ke bundel produksi
    import filter from 'lodash-es/filter';
    ```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Inisialisasi dan Konfigurasi Path Aliasing (Tingkat: Rendah)
*   **Tugas**:
    1. Buat proyek Vite baru menggunakan template Vanilla JS melalui terminal (`npm create vite@latest lab-vite -- --template vanilla`).
    2. Modifikasi `vite.config.js` untuk menambahkan path alias `@components` yang merujuk langsung ke folder `src/components/`.
    3. Pindahkan file modul komponen ke folder tersebut dan lakukan impor menggunakan path alias tersebut di `src/main.js`.
*   **Kriteria Keberhasilan**: Perintah `npm run build` sukses berjalan tanpa kegagalan resolusi path oleh Rollup.

### Latihan 2: Pembuatan Pipeline Deployment Otomatis (Tingkat: Menengah)
*   **Tugas**:
    1. Buat repositori baru di GitHub dan hubungkan dengan proyek lokal Anda.
    2. Susun alur kerja `.github/workflows/deploy.yml` yang mengeksekusi instalasi dependensi, validasi `npm run build`, dan distribusi otomatis ke GitHub Pages.
    3. Lakukan `git push` dan pantau jalannya tab *Actions* di GitHub hingga deployment berhasil.
*   **Kriteria Keberhasilan**: Situs web Anda dapat diakses secara global melalui tautan domain `https://<github-username>.github.io/<repo-name>/`.

### Latihan 3: Diagnosa dan Remediasi Metrik Core Web Vitals (Tingkat: Tinggi)
*   **Skenario**: Halaman web pengujian memuat sebuah gambar banner berukuran 8 Megabyte (`.png`) tanpa dimensi eksplisit dan memiliki tombol yang menjalankan kalkulasi algoritma blocking sinkronus yang menghambat UI thread.
*   **Tugas**:
    1. Jalankan audit Lighthouse di Chrome DevTools pada mode *Incognito* dan catat skor LCP, INP, serta CLS awal (diasumsikan berada pada zona merah/oranye).
    2. Lakukan perbaikan: Konversi gambar menjadi format `.webp`, terapkan kompresi, deklarasikan atribut `width` dan `height`, serta refaktor kalkulasi blocking menggunakan teknik *Web Workers* atau `setTimeout/requestIdleCallback`.
    3. Lakukan audit ulang menggunakan profil emulasi jaringan mobile (*Slow 4G*).
*   **Kriteria Keberhasilan**: Skor performa Lighthouse melonjak hingga $\ge 90$, dengan rincian: LCP $< 2.5$ detik, CLS $< 0.05$, dan tidak ada penalti pergeseran layout.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan berikut untuk memvalidasi pemahaman konseptual Anda:

#### 1. Mengapa Vite dapat memulai server pengembangan jauh lebih cepat dibandingkan bundler tradisional seperti Webpack?
*   A. Karena Vite mengonversi semua file menjadi format WebAssembly sebelum dijalankan.
*   B. Karena browser memproses modul kode secara *native* via ES Modules saat development, sehingga server tidak perlu melakukan *bundling* menyeluruh di awal.
*   C. Karena Vite tidak memeriksa integritas sintaks JavaScript sampai halaman web dimuat.
*   D. Karena Vite tidak mendukung penggunaan CSS dan dependensi npm.

#### 2. Apa fungsi utama dari penyematan hash konten (misal: `style.d83f1a.css`) pada nama file hasil kompilasi produksi?
*   A. Mencegah peretasan skrip melalui modifikasi kode berbahaya di sisi client.
*   B. Memaksa server web mengompresi file menggunakan algoritma Brotli secara default.
*   C. Memungkinkan penggunaan strategi HTTP cache permanen (*immutable*), karena perubahan isi file akan selalu menghasilkan nama file yang berbeda, mencegah masalah *stale cache*.
*   D. Mempercepat proses kompilasi Rollup saat build ulang dijalankan.

#### 3. Peristiwa manakah yang paling berpotensi merusak skor Cumulative Layout Shift (CLS) secara drastis?
*   A. Pengambilan data JSON menggunakan fungsi `fetch()` yang lambat pada latar belakang.
*   B. Gambar berukuran besar disisipkan ke dalam DOM secara dinamis tanpa reservasi dimensi `width` dan `height` atau wadah pembungkus dengan *aspect-ratio*.
*   C. Penggunaan skrip pihak ketiga yang berjalan di dalam Web Worker terisolasi.
*   D. Penulisan nama variabel JavaScript yang tidak memenuhi kaidah konvensi camelCase.

#### 4. Apa perbedaan instruksi `npm install` dengan `npm ci` dalam eksekusi CI/CD pipeline?
*   A. `npm install` lebih cepat karena tidak membaca file `package-lock.json`.
*   B. `npm ci` mengabaikan seluruh dependensi dev dan langsung menghasilkan file build produksi.
*   C. `npm ci` menghapus direktori `node_modules` dan menginstal dependensi secara ketat dan deterministik berdasarkan `package-lock.json`, serta memicu galat jika terjadi ketidakcocokan versi.
*   D. Keduanya identik, perbedaannya hanya terletak pada nama alias perintah di shell Linux.

#### 5. Metrik Core Web Vitals terbaru yang secara resmi menggantikan First Input Delay (FID) untuk mengukur responsivitas halaman secara holistik adalah...
*   A. Time to Interactive (TTI)
*   B. Total Blocking Time (TBT)
*   C. Interaction to Next Paint (INP)
*   D. First Contentful Paint (FCP)

---

### Kunci Jawaban & Rasional Teknis
1.  **Jawaban: B**. Vite memanfaatkan Native ESM pada peramban modern. Pemrosesan kode dilakukan secara on-demand, menghindari overhead kompilasi seluruh dependensi ke dalam satu bundel besar sebelum server dapat menyala.
2.  **Jawaban: C**. Dengan nama file berbasis *content hash*, peramban dapat menyimpan file di cache lokal tanpa batas waktu (`max-age=31536000`). Ketika ada rilis baru, hash berubah dan browser otomatis mengunduh file baru tanpa menampilkan versi usang (*stale*).
3.  **Jawaban: B**. Tanpa deklarasi dimensi eksplisit, browser tidak dapat menghitung ruang yang dibutuhkan elemen visual sebelum file gambar selesai diunduh. Akibatnya, elemen teks di bawahnya terdorong secara tiba-tiba ke bawah saat gambar selesai render, memicu skor CLS tinggi.
4.  **Jawaban: C**. `npm ci` (*Clean Install*) dirancang khusus untuk lingkungan otomatisasi dan integrasi kontinu guna memastikan konsistensi build tanpa mengubah `package-lock.json`.
5.  **Jawaban: C**. INP (*Interaction to Next Paint*) mengukur latensi end-to-end dari setiap interaksi selama siklus hidup halaman web, tidak hanya interaksi pertama seperti pada FID.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Dokumentasi Resmi Vite**: [vitejs.dev](https://vitejs.dev/) - Panduan arsitektur internal, plugin API, dan konfigurasi server.
*   **Web.dev Core Web Vitals Documentation**: [web.dev/vitals/](https://web.dev/vitals/) - Spesifikasi matematis dan teknis pengukuran LCP, INP, dan CLS oleh Google Chrome Team.
*   **GitHub Actions Official Documentation**: [docs.github.com/en/actions](https://docs.github.com/en/actions) - Sintaks alur kerja YAML, manajemen Secrets, dan konfigurasi runner virtual.
*   **Rollup Plugin & Bundler Anatomy**: [rollupjs.org](https://rollupjs.org/) - Mekanisme Tree-shaking dan optimasi manual chunking.
*   **Buku**: *High Performance Browser Networking* oleh Ilya Grigorik (O'Reilly Media) - Fundamental TCP, HTTP/2, HTTP/3, dan mekanisme transmisi aset web.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  **Vite merevolusi produktivitas developer** dengan membagi ekosistemnya: *native* ES Modules untuk kecepatan saat development via esbuild, dan *bundled/minified artifacts* untuk efisiensi produksi via Rollup.
2.  **Asset Processing untuk Produksi** membutuhkan minifikasi, tree-shaking untuk membuang unused code, content-hashing untuk HTTP caching jangka panjang, serta pemisahan chunk vendor untuk meminimalkan waktu unduh.
3.  **CI/CD Pipeline via GitHub Actions** menyediakan jaminan mutu otomatis. Melalui alur terstruktur (`lint` $\to$ `test` $\to$ `build` $\to$ `deploy`), potensi bug dan human error dapat diisolasi sebelum menjangkau pengguna akhir.
4.  **Edge Hosting Platforms** mendistribusikan aset statis secara global di simpul-simpul CDN terdekat dengan lokasi fisik pengguna, memangkas nilai *Round Trip Time* (RTT) dan *Time to First Byte* (TTFB).
5.  **Optimasi Core Web Vitals** bukan sekadar angka Lighthouse, melainkan ukuran objektif terhadap persepsi performa pengguna:
    *   **LCP ($\le 2.5$s)** dioptimasi via kompresi aset gambar modern dan resource hints (`preload`).
    *   **INP ($\le 200$ms)** dioptimasi dengan memecah *long tasks* pada main thread JavaScript.
    *   **CLS ($\le 0.1$)** dioptimasi dengan menyediakan dimensi visual eksplisit sebelum rendering aset terjadi.

---

## SEKSI 17 — GLOSARIUM

*   **Tree-Shaking**: Proses eliminasi dead-code (kode yang diekspor tetapi tidak pernah digunakan oleh modul manapun) dari bundel final melalui evaluasi analisis statis terhadap sintaks `import`/`export`.
*   **HMR (Hot Module Replacement)**: Kemampuan sistem tooling untuk menukar, menambah, atau menghapus modul secara langsung di browser tanpa memerlukan *full reload* (refresh) dari seluruh halaman web.
*   **Content Hash**: Rangkaian karakter unik berbasis algoritma kriptografi (misal: SHA-256) yang dihasilkan dari analisis isi file; jika isi file berubah satu karakter saja, hash akan berubah secara fundamental.
*   **Minification**: Proses pengetatan ukuran kode dengan menghapus spasi, baris baru, komentar, dan menyingkat nama variabel panjang tanpa mengubah logika fungsionalitas program sama sekali.
*   **Edge Computing / Edge CDN**: Jaringan infrastruktur peladen terdistribusi yang memproses permintaan HTTP di lokasi yang sedekat mungkin secara geografis dengan pengguna akhir.
*   **Time to First Byte (TTFB)**: Durasi waktu yang dibutuhkan browser mulai dari mengirim permintaan HTTP hingga menerima bita data pertama respons dari server web.
*   **Critical Rendering Path**: Rangkaian langkah yang dilalui browser (HTML $\to$ DOM, CSS $\to$ CSSOM, Render Tree, Layout, Paint) untuk mengubah kode menjadi piksel visual pada layar.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Hambatan Mahasiswa Paling Umum**:
    *   Mahasiswa pemula sering kali bingung membedakan variabel lingkungan sistem (`process.env`) dengan variabel lingkungan browser yang diinjeksi Vite (`import.meta.env`). Tekankan bahwa browser tidak memiliki akses native ke variabel internal sistem operasi host server.
    *   Sering terjadi kesalahan pada deployment GitHub Pages akibat jalur file aset (*path asset*) yang relatif tidak merujuk ke subdirektori repositori (`base` setting di `vite.config.js`).
*   **Strategi Pengajaran**:
    *   Awali sesi dengan demonstrasi langsung (*live demo*): buka repositori Webpack lama yang memiliki waktu start 15 detik, bandingkan langsung dengan Vite yang menyala dalam hitungan milidetik. Hal ini memberikan motivasi visual yang kuat.
    *   Pada sesi performa, gunakan Chrome DevTools dengan fitur *CPU Throttling 4x slowdown* dan *Network Throttling Fast/Slow 3G*. Pengembang sering kali lupa bahwa pengguna mereka tidak menggunakan MacBook berkecepatan tinggi dengan koneksi fiber optik gigabit.
*   **Manajemen Waktu**:
    *   Alokasikan waktu ekstra (minimal 30 menit) pada segmen konfigurasi YAML GitHub Actions, karena galat sintaksis indentasi YAML dan izin branch protection merupakan kendala yang paling sering menghabiskan waktu mahasiswa.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi**: `1.0.0` (Rilis Kurikulum Dasar)
    *   **Tanggal Efektif**: 2024-10-25
    *   **Catatan Pembaruan**:
        *   Inisialisasi draf modul standar arsitektur frontend pemula.
        *   Penggantian First Input Delay (FID) dengan Interaction to Next Paint (INP) sesuai panduan resmi Google Search Engine Console Maret 2024.
        *   Standarisasi contoh alur kerja menggunakan GitHub Actions v4 runtimes dan integrasi Vite 5.x build core.
    *   **Penyusun/Arsitek Kurikulum**: Senior Technical Curriculum Architect Team

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya**: `FED-01-CF-09-02` — *Asynchronous JavaScript, Fetch API, and State Synchronization Patterns*
*   **Modul Saat Ini**: `FED-01-CF-10-01` — *Modern Build Tools, Deployment Pipeline & Audit Kinerja*
*   **Modul Berikutnya**: `FED-01-CF-11-01` — *Capstone Project: Production-Ready Static Web Application Architecture*