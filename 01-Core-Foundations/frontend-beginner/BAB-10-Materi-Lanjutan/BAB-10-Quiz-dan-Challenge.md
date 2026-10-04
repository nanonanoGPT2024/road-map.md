# BAB 10: Quiz, Challenge, & Knowledge Check
**Modern Build Tools, Deployment Pipeline & Audit Kinerja**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Native ESM vs Bundled Development Server:**
   Jelaskan perbedaan fundamental arsitektur *development server* modern berbasis Native ES Modules (seperti Vite/esbuild) dibandingkan *bundler-based dev server* tradisional (seperti Webpack Dev Server). Mengapa Vite mampu menjaga waktu *cold start* dan Hot Module Replacement (HMR) tetap berada pada kompleksitas $O(1)$ terlepas dari bertambahnya ukuran basis kode aplikasi?

2. **Mekanisme Statis Tree-Shaking:**
   Mengapa sintaksis ES Module (`import` dan `export`) bersifat deterministik dan wajib digunakan agar *bundler* dapat mengeksekusi *Dead Code Elimination* (Tree-Shaking) secara optimal, sedangkan spesifikasi CommonJS (`require()` dan `module.exports`) menyebabkan *bundler* gagal menganalisis struktur modul secara statis pada waktu kompilasi (*compile-time*)?

3. **Strategi Caching: Content Hashing vs HTTP Cache Headers:**
   Jelaskan korelasi teknis antara teknik penamaan aset *Content Hashing* (misalnya `app.8f3d1b.js`) dengan instruksi HTTP Header `Cache-Control: public, max-age=31536000, immutable`. Mengapa file entry-point `index.html` mutlak **dilarang** menggunakan header *immutable* dan justru wajib dikonfigurasi dengan `Cache-Control: no-cache`?

4. **Metrik Core Web Vitals (LCP, INP, CLS):**
   Uraikan secara presisi apa yang diukur oleh masing-masing metrik *Core Web Vitals* berikut, apa penyebab degradasi teknis utamanya di sisi arsitektur front-end, serta berapa batas ambang (*threshold*) Google untuk kategori "Good":
   - Largest Contentful Paint (LCP)
   - Interaction to Next Paint (INP)
   - Cumulative Layout Shift (CLS)

5. **Anatomi dan Keamanan Source Maps di Produksi:**
   Bagaimana cara kerja Source Map (file `.map`) dalam memetakan *minified/obfuscated code* di browser kembali ke baris kode asli (*original source code*)? Dari perspektif *software security* dan *intellectual property*, mengapa file Source Map sebaiknya tidak di-hosting secara publik di CDN produksi, dan bagaimana pola arsitektur yang benar untuk tetap menggunakannya pada sistem *error tracking* (seperti Sentry)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Side Effects Flagging & False-Positive Elimination:**
   Pada file `package.json`, properti `"sideEffects": false` sering digunakan untuk memaksimalkan *tree-shaking*. Jelaskan skenario fatal di mana penambahan konfigurasi `"sideEffects": false` secara sembarangan justru merusak fungsionalitas aplikasi produksi (khususnya terkait impor file CSS global atau eksekusi *polyfill/prototype augmentation*). Bagaimana cara mengatasi *false-positive* tersebut menggunakan pola array *glob pattern*?

2. **Dynamic Import Waterfall & Preloading Optimization:**
   Ketika melakukan *route-based code splitting* menggunakan `import()`, browser mengeksekusi *chunk* secara *lazy* saat rute diakses. Jika *chunk* tersebut juga membutuhkan pustaka pihak ketiga (*vendor chunk*), sering terjadi fenomena *network waterfall*. Bagaimana elemen `<link rel="modulepreload">` atau konfigurasi bundler mitigasi masalah latensi ini sebelum interaksi pengguna terjadi?

3. **Debugging ChunkLoadError pada Zero-Downtime Deployment:**
   Pengguna aplikasi web Single Page Application (SPA) yang sedang aktif membuka halaman tiba-tiba mengalami error `ChunkLoadError: Loading chunk 404 failed` saat berpindah halaman beberapa menit setelah proses *continuous deployment* (CD) selesai dijalankan di server. Jelaskan akar masalah mekanisme *in-place deployment* yang memicu insiden ini dan bagaimana solusinya secara infrastruktur penyimpanan (S3/GCS + CDN)?

4. **Transpilasi Sintaksis vs Runtime Polyfilling:**
   Jelaskan perbedaan tugas mendasar antara *syntax transpiler* (misalnya SWC atau esbuild yang mengubah sintaks ES2022 seperti *optional chaining* `?.` atau *nullish coalescing* `??` menjadi ES2015) dengan *runtime polyfill* (seperti `core-js` untuk `Promise.allSettled` atau `Array.prototype.flat`). Mengapa mentranspilasi kode saja tidak cukup untuk menjamin kompatibilitas pada browser versi lama?

5. **Root-Cause Analysis Layout Shift (CLS) Akibat Web Fonts:**
   Sebuah halaman e-commerce mencatat skor CLS buruk (0.35). Melalui Chrome DevTools Performance panel, teridentifikasi bahwa teks navigasi dan judul bergeser posisinya tepat saat *custom web font* selesai diunduh. Jelaskan perbedaan antara FOUT (*Flash of Unstyled Text*) dan FOIT (*Flash of Invisible Text*), serta bagaimana properti CSS `font-display: optional` digabungkan dengan `size-adjust` pada `@font-face` dapat mereduksi skor CLS tersebut menjadi 0.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Lonjakan LCP 7.2 Detik Pasca Integrasi Hero Video & Tag Manager
* **Konteks:** Sebuah portal media meluncurkan pembaruan desain halaman beranda. Tim pemasaran memasang Google Tag Manager (GTM) dengan 15 *tracking pixels*, serta tim desain mengganti gambar statis hero banner dengan animasi video MP4 resolusi tinggi yang disematkan langsung di dalam *viewport*. Audit pasca rilis menunjukkan skor Lighthouse Mobile anjlok dari 94 ke 38, dengan LCP melonjak menjadi 7.2 detik dan Total Blocking Time (TBT) mencapai 1.400 ms.
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda mengisolasi kontribusi beban antara GTM (JavaScript main-thread blocking) dan media hero terhadap metrik LCP menggunakan tab *Network* dan *Performance* di DevTools?
  2. Susun rencana perbaikan teknis (*remediation plan*) konkret mencakup strategi pemuatan video/gambar responsif (format modern, `fetchpriority`, placeholder), serta eksekusi GTM (*off-main-thread* via Web Worker menggunakan Partytown atau penundaan inisialisasi) agar LCP kembali berada di bawah ambang batas < 2.5 detik.

### Skenario B: Race Condition pada Caching Pipeline & Stale State CDN
* **Konteks:** Tim DevOps memperbarui pipeline CI/CD GitHub Actions untuk deploy SPA ke AWS S3 yang berada di balik Cloudflare CDN. Langkah deployment menjalankan script `aws s3 sync ./dist s3://my-bucket --delete`. Tak lama setelah rilis versi `v2.4.0`, ratusan tiket keluhan masuk: pengguna menerima tampilan antarmuka yang rusak, tombol-tombol tidak merespons, dan konsol browser mencetak *uncaught syntax error*. Analisis menunjukkan browser mengunduh `index.html` versi `v2.4.0`, namun meminta file `main.hash-v1.js` (milik versi lama) yang telah terhapus dari S3 karena parameter `--delete`.
* **Pertanyaan Diagnostik:**
  1. Identifikasi *race condition* dan kesalahan urutan eksekusi (*order of execution*) sinkronisasi aset serta invalidasi cache CDN pada pipeline deployment tersebut.
  2. Rancang ulang tahapan langkah (*pipeline steps*) yang atomik dan aman agar deployment bersifat *immutable* dan menjamin klien yang masih membuka tab versi lama tidak mengalami *broken experience*.

### Skenario C: Arsitektur Granular Splitting vs HTTP/2 Multiplexing Overhead
* **Konteks:** Sebuah tim engineering melakukan eksperimen ekstrem dengan memecah *bundle* aplikasi secara ultra-granular: setiap modul file dari `node_modules` dijadikan satu file chunk terpisah (menghasilkan lebih dari 450 request file JS kecil berukuran 1KB–10KB). Asumsi mereka adalah HTTP/2 Multiplexing akan mengunduh semua file secara paralel tanpa *overhead*. Namun saat diuji di jaringan 4G/LTE seluler dengan latensi tinggi (RTT 150ms), performa aplikasi justru mengalami degradasi parah dibandingkan arsitektur 3–5 *chunk* gabungan (*vendor chunking*).
* **Pertanyaan Diagnostik:**
  1. Secara mekanika protokol jaringan dan kompresi (Gzip/Brotli), mengapa strategi pemecahan chunk yang terlalu granular (*over-splitting*) justru merugikan efisiensi kompresi kamus (*dictionary compression*) dan memicu *CPU/stream multiplexing congestion* di browser mobile?
  2. Apa strategi kompromi arsitektural (*sweet spot*) yang direkomendasikan untuk konfigurasi *manual chunks* pada bundler (Vite/Rollup) guna menyeimbangkan efisiensi *long-term caching* dan performa *network transfer*?

---

## 4. Chapter Challenge

### Tantangan Praktis: Modernisasi Pipeline Build, Zero-Downtime Deployment, dan Optimasi Web Vitals

#### Problem Statement
Anda mewarisi repositori SPA legacy berbasis Vanilla JavaScript/TypeScript yang dibangun tanpa struktur bundling modern. Aplikasi memiliki waktu muat lambat (skor Lighthouse Performance: 42), seluruh kode dan dependensi dikompilasi menjadi satu file monolitik `bundle.js` sebesar 3.8 MB, dan proses deployment masih manual menggunakan script FTP yang menimpa file produksi secara langsung di server web.

#### Requirements
1. **Konfigurasi Modern Build Tool (Vite):**
   - Inisialisasi Vite dengan TypeScript secara *strict*.
   - Implementasikan *Dynamic Import* untuk halaman yang tidak tampil di *initial landing view*.
   - Konfigurasi `rollupOptions` untuk memisahkan *vendor dependencies* berukuran besar ke dalam chunk terpisah menggunakan pola `manualChunks`.
   - Konfigurasi kompresi build-time menggunakan plugin `vite-plugin-compression` (menghasilkan file `.gz` dan `.br`).

2. **Automasi CI/CD Pipeline (GitHub Actions):**
   - Buat file *workflow* `.github/workflows/deploy.yml` yang terpicu saat ada *push* ke branch `main`.
   - Pipeline wajib memvalidasi linting (`eslint`), *type-checking* (`tsc --noEmit`), dan mengeksekusi build produksi.
   - Implementasikan proses upload artifak yang atomik: aset ter-hash diunggah terlebih dahulu dengan header cache abadi, disusul file `index.html` dengan proteksi cache.

3. **Infrastruktur & Web Server Rules (Nginx Config):**
   - Buat file `nginx.conf` produksi yang mengatur:
     - Header `Cache-Control: public, max-age=31536000, immutable` untuk path `/assets/*`.
     - Header `Cache-Control: no-cache, no-store, must-revalidate` untuk file `index.html`.
     - Enable Brotli/Gzip fallback di sisi web server.
     - Fallback routing SPA (`try_files $uri $uri/ /index.html;`).

4. **Audit & Optimasi Kinerja:**
   - Reduksi LCP dari baseline buruk menjadi < 2.0 detik.
   - Hilangkan Layout Shift (CLS = 0) dengan mengonfigurasi dimensi atribut statis serta optimasi pemuatan font.

#### Constraints
- File Source Map **tidak boleh** disajikan di direktori publik server web produksi.
- Ukuran *initial bundle* (JavaScript yang dieksekusi sebelum rute pertama render) tidak boleh melebihi 150 KB (Gzipped).
- Tidak boleh ada *runtime breaking change* pada fungsionalitas aplikasi yang sudah berjalan.

#### Expected Output
1. File konfigurasi `vite.config.ts` lengkap dengan optimasi chunking dan compression.
2. File pipeline `.github/workflows/deploy.yml` yang teruji dan menerapkan urutan upload deployment atomik.
3. Snippet konfigurasi `nginx.conf` yang mengimplementasikan aturan *caching headers* ketat dan SPA routing.
4. Laporan audit ringkas berupa tabel Markdown perbandingan metrik sebelum (*Before*) dan sesudah (*After*) optimasi: Ukuran Bundle, LCP, INP, CLS, dan skor Lighthouse.

---

## 5. Knowledge Check & Checklist

Verifikasi kesiapan pemahaman Anda sebelum melangkah ke modul arsitektur tingkat lanjut:

### Saya harus memahami:
- [ ] Perbedaan siklus hidup kompilasi antara Vite (esbuild/Rollup) dan Webpack saat menangani modul.
- [ ] Bagaimana algoritma *graph analysis* pada *bundler* mengidentifikasi modul yang tidak digunakan (*unreachable export*) untuk proses *Tree-Shaking*.
- [ ] Peran strategis *Content Hashing* dalam mencegah masalah *stale cache* pada CDN dan browser klien.
- [ ] Dampak eksekusi JavaScript pada *Main Thread* terhadap metrik Total Blocking Time (TBT) dan Interaction to Next Paint (INP).
- [ ] Logika penanganan aset SPA pada server statis (mengapa rute sub-path seperti `/dashboard/settings` memerlukan aturan *fallback* ke `index.html`).

### Saya tidak perlu menghafal:
- [ ] Seluruh nama properti konfigurasi API tingkat rendah pada Webpack/Rollup (cukup pahami konsep *entry*, *output*, *loader/plugin*, dan *chunking*).
- [ ] Format biner internal dari *Brotli compression algorithm* atau spesifikasi Base64 encoding pada Source Map VLQ.
- [ ] Seluruh baris sintaks syntax-tree (AST) yang dihasilkan oleh parser parser Babel/SWC.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan mengurai modul berukuran besar (*bloated dependencies*) menggunakan alat visualisasi seperti `rollup-plugin-visualizer` atau `webpack-bundle-analyzer`.
- [ ] Menulis konfigurasi CI/CD modern yang memisahkan tahapan *Lint*, *Type-Check*, *Build Artifact*, dan *Atomic Deployment*.
- [ ] Menggunakan Chrome DevTools (Tab *Coverage*, *Performance*, dan *Network*) untuk mengidentifikasi *render-blocking resources*, *Long Tasks*, dan pemicu *Layout Shift*.
- [ ] Mengonfigurasi web server (Nginx/Cloudflare/Vercel) untuk menerapkan HTTP Caching Headers yang tepat antara file entri statis dan file aset ter-hash.