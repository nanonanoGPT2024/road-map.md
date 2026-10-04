# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Jaringan, Internet & Arsitektur Peramban**

Dokumen evaluasi ini dirancang untuk menguji penguasaan konseptual, pemahaman arsitektur internal, serta kapabilitas diagnostik Anda terhadap mekanisme peramban web (*browser engine*) dan infrastruktur jaringan dasar.

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Resolusi DNS dan Latensi Jaringan
Jelaskan secara komprehensif siklus hidup resolusi DNS dari saat pengguna mengetikkan URL hingga peramban menerima alamat IP target. Bedakan peran *Recursive Resolver*, *Root Server*, *TLD Name Server*, dan *Authoritative Name Server*. Mengapa nilai *Time-to-Live* (TTL) yang disetel terlalu rendah dapat memengaruhi metrik *Time to First Byte* (TTFB) aplikasi web Anda secara signifikan?

### Soal 1.2: Anatomi Transport Layer: TCP 3-Way Handshake vs TLS 1.3
Gambarkan alur pertukaran paket pada pembentukan koneksi aman menggunakan protokol TCP dan TLS 1.3. Berapa *Round Trip Time* (RTT) minimum yang dibutuhkan sebelum peramban dapat mengirimkan *payload* HTTP GET pertama? Jelaskan bagaimana mekanisme *0-RTT Resumption* pada TLS 1.3 bekerja serta risiko keamanan (*replay attack*) yang menyertainya.

### Soal 1.3: Evolusi Protokol: Masalah Head-of-Line (HoL) Blocking
Bandingkan mekanisme transmisi data antara HTTP/1.1 (dengan *pipelining*), HTTP/2 (*multiplexing*), dan HTTP/3 (*QUIC over UDP*). Pada lapisan (*layer*) model OSI mana *Head-of-Line Blocking* terjadi pada masing-masing protokol tersebut, dan bagaimana implementasi *independent streams* pada HTTP/3 menuntaskan limitasi bawaan TCP?

### Soal 1.4: Arsitektur Multi-Process Peramban Modern
Peramban modern (seperti Chromium) beralih dari arsitektur *monolithic single-process* ke *multi-process architecture*. Jelaskan tanggung jawab spesifik dari:
1. *Browser Process*
2. *Renderer Process*
3. *Network Process*
4. *GPU Process*

Mengapa fitur *Site Isolation* mengharuskan pemisahan *Renderer Process* berbasis origin (atau *eTLD+1*), dan apa implikasi arsitektur ini terhadap konsumsi memori RAM?

### Soal 1.5: Critical Rendering Path (CRP)
Uraikan langkah-langkah deterministik peramban dalam mengubah *bytes* HTML mentah menjadi piksel pada layar: *Tokenization*, *DOM Tree Construction*, *CSSOM Construction*, *Render Tree*, *Layout (Reflow)*, dan *Paint*. Mengapa file CSS eksternal secara default diklasifikasikan sebagai *render-blocking resource*, sedangkan skrip JavaScript eksternal diklasifikasikan sebagai *parser-blocking resource*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Parser Execution: `async` vs `defer` vs Dynamic Imports
Analisis cuplikan tag skrip berikut:
```html
<script src="a.js"></script>
<script async src="b.js"></script>
<script defer src="c.js"></script>
```
Jelaskan perbedaan mendasar ketiganya dalam hal:
- Penghentian eksekusi HTML Parser (*speculative parser behavior*).
- Garansi urutan eksekusi (*execution order*).
- Waktu pengeksekusian relatif terhadap *event* `DOMContentLoaded` dan `window.onload`.

### Soal 2.2: Mekanisme Validasi Caching: HTTP 304 vs Browser In-Memory Cache
Jelaskan alur komparasi ketika peramban menghadapi *header* `Cache-Control: no-cache` versus `Cache-Control: no-store`. Kapan peramban mengirimkan *header* `If-None-Match` (menggunakan ETag) dan `If-Modified-Since`? Jika respons dari server adalah `304 Not Modified`, apa yang sebenarnya terjadi pada alur transmisi jaringan dan pemanfaatan *disk cache* lokal?

### Soal 2.3: CORS Preflight & Header Evaluation
Sebuah aplikasi web pada origin `https://dashboard.domain.com` mengeksekusi request berikut:
```javascript
fetch("https://api.domain.com/v1/users", {
  method: "DELETE",
  headers: {
    "Content-Type": "application/json",
    "X-Client-Version": "2.4.0"
  },
  credentials: "include"
});
```
1. Mengapa permintaan ini memicu *Preflight Request* (`OPTIONS`)?
2. Sebutkan minimal 3 header respons HTTP wajib dari server agar preflight berhasil.
3. Mengapa server tidak boleh mengembalikan `Access-Control-Allow-Origin: *` pada konfigurasi di atas?

### Soal 2.4: Compositor Thread & Hardware Acceleration
Jelaskan mengapa perubahan properti CSS `transform: translate3d(...)` dan `opacity` tidak memicu tahap *Layout* maupun *Paint*, melainkan langsung diproses pada tahap *Compositing*. Apa peran *Compositor Thread* independen terhadap responsivitas aplikasi saat *Main Thread* mengalami *blocking* akibat eksekusi JavaScript yang berat? Apa bahaya dari fenomena *layer explosion* jika kita menerapkan properti `will-change: transform` secara serampangan?

### Soal 2.5: Speculative Pre-parsing dan Resource Hints
Peramban modern memiliki modul *Preload Scanner* (*speculative parser*). Jelaskan perbedaan mendasar fungsi, prioritas alokasi jaringan, dan siklus hidup dari empat *resource hint* berikut:
1. `<link rel="dns-prefetch">`
2. `<link rel="preconnect">`
3. `<link rel="preload">`
4. `<link rel="prefetch">`

Apa bahaya performa jika Anda melakukan `<link rel="preload">` terhadap resource yang tidak langsung digunakan dalam kurun waktu 3 detik setelah halaman dimuat?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Investigasi Latensi & TTFB Degradation pada Event Flash Sale
**Konteks Insiden:**
Pada event promosi skala besar, metrik *Largest Contentful Paint* (LCP) melonjak dari 1.2 detik menjadi 6.8 detik di jaringan seluler 4G. Berdasarkan audit Network Waterfall di Chrome DevTools, ditemukan pola berikut:
- Resolusi DNS memakan waktu 450ms.
- Koneksi TCP + TLS Handshake memakan waktu 600ms (terjadi koneksi baru ke domain asset yang berbeda: `cdn.img-store.com`, `api.promo.com`, `fonts.external.com`).
- Aset gambar LCP (banner utama) baru mulai di-download pada detik ke-3.5 karena tertahan antrean aset CSS sebesar 400KB yang memuat font pihak ketiga secara sinkron (`@import url(...)`).

**Pertanyaan Diagnostik:**
1. Rancang arsitektur optimasi jaringan untuk mereduksi *connection setup overhead* ke domain-domain pihak ketiga tersebut tanpa memindahkan seluruh server ke origin tunggal.
2. Identifikasi anti-pattern pada pemuatan CSS dan jelaskan langkah konkret restrukturisasi aset (*critical CSS*, penghapusan `@import`, optimasi pemuatan font) untuk membebaskan *Main Thread* dan mempercepat *discovery* aset banner LCP.

---

### Skenario B: Race Condition Caching & Script Inconsistency Pasca-Deployment
**Konteks Masalah:**
Tim Anda merilis pembaruan kritis pada sistem autentikasi SPA (*Single Page Application*). Struktur file build frontend menggunakan pola hashing:
- `index.html`
- `main.a8b1c2.js`
- `auth-vendor.f5e4d3.js`

Dua jam pasca-deploy, ribuan pengguna melaporkan halaman menjadi *blank* (*white screen of death*) dengan pesan galat di konsol: `Uncaught TypeError: window.__AUTH_SESSION__ is not a function`. 
Hasil investigasi menunjukkan:
- Konfigurasi server Nginx menyajikan `index.html` dengan header `Cache-Control: public, max-age=86400`.
- Versi `index.html` lama yang tersimpan di *browser cache* pengguna masih memanggil `auth-vendor` versi lama (yang sudah dihapus dari server CDN karena kebijakan rotasi penyimpanan), tetapi meminta `main.js` versi baru via Service Worker / inline chunk loader.

**Pertanyaan Diagnostik:**
1. Bedah kegagalan arsitektur *caching strategy* pada kasus di atas. Tentukan header HTTP `Cache-Control` yang wajib diterapkan untuk file HTML entry-point (`index.html`) versus file static assets bertanda hash (`.js`, `.css`).
2. Rancang skema *deployment rollback mitigation* dan jelaskan bagaimana peramban memvalidasi file `index.html` secara instan menggunakan ETag tanpa membuang bandwidth transfer jika tidak ada pembaruan kode.

---

### Skenario C: Trade-off Arsitektur: Iframe vs Web Components / ES Modules
**Konteks Arsitektur:**
Perusahaan perbankan ingin membangun portal enterprise yang mengintegrasikan tiga aplikasi internal berbeda (Core Banking, Fraud Detection, dan Customer Support) ke dalam satu dashboard terpadu. Tim arsitektur berdebat antara dua opsi:
- **Opsi 1 (Process Isolation):** Mengintegrasikan sub-aplikasi menggunakan `<iframe>` multi-origin.
- **Opsi 2 (Unified DOM):** Mengintegrasikan sub-aplikasi menggunakan arsitektur Micro-Frontend berbasis ES Modules / Module Federation dan Web Components (Shadow DOM).

**Pertanyaan Diagnostik:**
1. Dari sudut pandang **Arsitektur Peramban** (*Main Thread allocation*, *Renderer Process*, *Memory footprint*, dan *Cross-Site Scripting attack surface*), bedah trade-off fundamental antara Opsi 1 dan Opsi 2.
2. Jika Opsi 1 dipilih karena regulasi keamanan data finansial yang ketat, bagaimana strategi mitigasi performa untuk mengatasi latensi inisialisasi *window context* baru, dan bagaimana arsitektur komunikasi antar-frame yang aman diimplementasikan tanpa membuka celah CSRF/XSS?

---

## 4. Chapter Challenge

### Tantangan Praktis: Deep Network & Rendering Audit Blueprint
Anda berperan sebagai Lead Architect yang diminta mengaudit file HAR (*HTTP Archive*) dan rekaman *Chrome DevTools Performance Trace* dari landing page e-commerce yang mengalami degradasi performa berat.

#### Deskripsi Masalah:
Aplikasi memiliki *Core Web Vitals* yang buruk:
- **TTFB:** 1.8s
- **First Contentful Paint (FCP):** 4.2s
- **Cumulative Layout Shift (CLS):** 0.38
- **Interaction to Next Paint (INP):** 520ms

#### Requirements & Constraints:
Anda diwajibkan menyusun dokumen teknis perbaikan (maksimal berbentuk laporan audit arsitektur) yang mencakup:
1. **Network Layer Optimization Plan:**
   - Rekomendasi restrukturisasi koneksi jaringan (skema *Keep-Alive*, integrasi HTTP/2 atau HTTP/3, optimalisasi TLS termination).
   - Matriks penataan *caching policy* terinci untuk 4 kategori file: Entry HTML, Vendor Bundles (immutable), Application Bundles, dan Dynamic User Payload API. Tuliskan representasi persis dari response header `Cache-Control`, `Vary`, dan mekanisme revalidasi untuk tiap kategori.
2. **Critical Rendering Path Overhaul:**
   - Audit script loading: Transformasikan 5 pemanggilan skrip sinkron (analitik, core bundle, widget chat, font loader, theme switcher) menggunakan kombinasi `async`, `defer`, inline critical script, atau dynamic execution agar parser HTML tidak terblokir.
   - Analisis mitigasi CLS: Identifikasi akar masalah pergeseran tata letak (asynchronous image loading tanpa rasio dimensi, injeksi dynamic ad banner, web font FOIT/FOUT) dan berikan aturan teknis CSS (*aspect-ratio*, `font-display: swap`, content-visibility) untuk menguncinya ke angka `< 0.05`.
3. **Execution Thread Optimization:**
   - Berikan instruksi teknis untuk melepaskan beban pemrosesan DOM berskala besar dari *Main Thread* ke *Compositor Thread* atau *Web Worker*, guna menekan angka INP ke bawah 150ms.

#### Expected Output:
Dokumen arsitektur perbaikan terstruktur yang memuat diagram alur/skema *loading sequence*, tabel spesifikasi header caching, cuplikan perbaikan implementasi tag `<head>` HTML yang telah dioptimasi penuh, dan justifikasi teknis tingkat mesin (*browser engine level*) atas setiap keputusan yang diambil.

---

## 5. Knowledge Check & Checklist

Gunakan daftar periksa mandiri ini untuk mengukur kesiapan teknis Anda sebelum melangkah ke bab berikutnya.

### Saya harus memahami:
- [ ] Mekanisme resolusi hierarkis DNS (Cache lokal, Resolver, Root, TLD, Authoritative) dan dampaknya terhadap TTFB.
- [ ] Perbedaan struktural pertukaran paket TCP Handshake (SYN, SYN-ACK, ACK) dan TLS 1.2 vs TLS 1.3 Handshake.
- [ ] Batasan transmisi data pada HTTP/1.1 (*pipelining limitation*), HTTP/2 (*binary framing*, *multiplexing*, TCP HoL), dan HTTP/3 (*QUIC over UDP*, *independent streams*).
- [ ] Arsitektur multi-proses peramban: *Browser Process*, *Renderer Process*, *GPU Process*, dan *Network Process*, beserta fungsi keamanan *Site Isolation*.
- [ ] Rantai *Critical Rendering Path*: Parsir token HTML/CSS, resolusi selektor CSSOM, kalkulasi geometri pada *Layout*, rasterisasi pada *Paint*, dan penanganan lapisan oleh *Compositor Thread*.
- [ ] Konsep *Layer Promotion* pada GPU dan properti-properti CSS yang berjalan eksklusif pada *Compositor Thread* (`transform`, `opacity`).
- [ ] Matriks status HTTP Caching: `no-cache`, `no-store`, `must-revalidate`, `stale-while-revalidate`, serta alur komparasi ETag/If-None-Match.
- [ ] Mekanisme keamanan CORS, kriteria *Simple Request* vs *Preflight Request* (`OPTIONS`), serta relasi `Vary: Origin` dengan *shared proxy cache*.

### Saya tidak perlu menghafal:
- [ ] Nilai *hexadecimal* atau representasi *bit-level* paket biner frame HTTP/2 dan HTTP/3 QUIC.
- [ ] Seluruh nomor RFC spesifikasi jaringan (misal: RFC 7231, RFC 8446) di luar pemahaman fungsionalitasnya.
- [ ] Angka persis batas alokasi memori default yang dialokasikan OS untuk V8 Engine pada setiap platform perangkat.
- [ ] Seluruh deretan cipher suites TLS kriptografi manual secara tekstual.

### Saya harus bisa melakukan:
- [ ] Membaca dan menganalisis *Waterfall Chart* pada Chrome DevTools Network Tab untuk mendeteksi *Resource Blocking*, DNS resolution overhead, dan *Connection stalling*.
- [ ] Menemukan titik degradasi performa CRP (*Long Tasks*, *Layout Shifts*, *Forced Synchronous Layout*) menggunakan Chrome DevTools Performance Panel.
- [ ] Mendiagnosis dan memperbaiki kesalahan konfigurasi CORS langsung melalui manipulasi header respons HTTP server/reverse proxy.
- [ ] Menyusun strategi pemuatan skrip eksternal yang optimal menggunakan atribut `defer`, `async`, atau penempatan modular tanpa memicu *parser interruption*.
- [ ] Mengonfigurasi header `Cache-Control` yang presisi untuk arsitektur modern (membedakan penanganan *cache busting hash* vs berkas navigasi utama).