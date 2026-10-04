# BAB 09: Quiz, Challenge, & Knowledge Check
**Rendering Sisi Server (SSR), Prerendering (SSG), & Hydration**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Komparasi Arsitektur Eksekusi (CSR vs. SSR vs. SSG):**  
   Jelaskan secara presisi perbedaan siklus hidup eksekusi kode Angular antara Client-Side Rendering (CSR), Server-Side Rendering (SSR), dan Static Site Generation (SSG). Tinjau bagaimana masing-masing pendekatan memengaruhi metrik *Core Web Vitals* kritis: Time to First Byte (TTFB), Largest Contentful Paint (LCP), dan Interaction to Next Paint (INP).

2. **Mekanisme Non-Destructive Hydration:**  
   Bagaimana arsitektur *non-destructive hydration* modern di Angular (v16+) memproses DOM hasil render server dibandingkan dengan pendekatan lama (*destructive re-rendering*)? Jelaskan peran penandaan node (*DOM annotations/contract*) internal yang disematkan server dalam mencegah *layout thrashing* dan kedipan visual (*flicker*).

3. **Peran Vital dan Siklus Hidup `TransferState`:**  
   Mengapa penggunaan `HttpClient` secara langsung tanpa `TransferState` atau `withFetch()` dalam lingkungan SSR menyebabkan *double-data fetching*? Uraikan bagaimana `TransferState` menserialisasikan state ke dalam tag `<script id="ng-state" type="application/json">` di server dan bagaimana client mendeserialisasikannya untuk meng-hydrate store lokal.

4. **Abstraksi Platform Runtime (`PLATFORM_ID` & `isPlatformServer`):**  
   Ekosistem Node.js tidak memiliki API global peramban (`window`, `document`, `localStorage`, `navigator`). Jelaskan bahaya mengeksekusi referensi ini secara langsung di komponen Angular yang mendukung SSR. Bagaimana dependensi injeksi menggunakan token `PLATFORM_ID` dan fungsi penjaga `isPlatformBrowser`/`isPlatformServer` memitigasi eksekusi kode spesifik platform tersebut?

5. **Deferrable Views (`@defer`) dalam Konteks Server & Hydration:**  
   Bagaimana compiler dan runtime Angular memperlakukan blok `@defer` saat dieksekusi di server? Secara default, apa yang di-render oleh server (konten `@defer` utama vs. blok `@placeholder`), dan bagaimana mekanisme *Incremental Hydration* (`@defer (hydrate on ...)`) mengoptimalkan ukuran bundle JavaScript awal yang dikirim ke client?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Anatomi dan Resolusi Hydration Mismatch:**  
   Sebuah aplikasi melempar peringatan runtime:  
   `NG0500: During hydration, Angular expected an element matching the selector '...' but found a different node.`  
   Uraikan 3 (tiga) *root cause* paling umum dari error ini (termasuk modul pihak ketiga yang memanipulasi DOM, manipulasi via direct DOM API, dan *timestamp/localization drift*). Kapan penggunaan direktif `ngSkipHydration` dapat dibenarkan secara teknis, dan apa konsekuensi strukturalnya terhadap sub-tree DOM di bawahnya?

2. **Penentuan Stabilitas Aplikasi (`ApplicationRef.isStable` & Zone.js):**  
   Engine SSR Angular (seperti `@angular/ssr` atau engine berbasis `@angular/platform-server`) menunggu `ApplicationRef.isStable` bernilai `true` sebelum memanggil serialisasi HTML. Bagaimana sebuah microtask atau macrotask tak berujung (misalnya `setInterval`, unclosed RxJS polling observables, atau microtasks yang terus-menerus terjadwal) dapat menggantung (*hang*) proses SSR Node.js hingga mengalami *request timeout*? Bagaimana strategi mitigasinya jika menggunakan `NgZone.runOutsideAngular` atau Zoneless Angular?

3. **Pencegahan Memory Leak dan Cross-Request State Pollution:**  
   Di lingkungan browser, runtime bersifat *single-tenant* (satu sesi per memori tab). Di server, sebuah proses Node.js melayani ribuan request konkuren secara *multi-tenant*. Jelaskan bahaya arsitektural dari mendaftarkan state berbasis user ke dalam *Root-level Singleton Service* (`@Injectable({ providedIn: 'root' })`) selama fase SSR. Bagaimana *leakage* data sensitif antar-request dapat terjadi dan bagaimana cara mendesain request-scoped data propagation yang aman?

4. **Propagasi Kredensial dan State HTTP (Cookie/Auth Forwarding):**  
   Saat browser meminta halaman `/dashboard` yang membutuhkan otentikasi via cookie `HttpOnly`, server SSR harus memanggil REST API downstream atas nama user tersebut. Namun, eksekusi `HttpClient` di server berjalan di dalam container Node.js, bukan peramban user. Bagaimana Anda mengarsiteksi `HttpInterceptorFn` di sisi server untuk mengekstrak header `Cookie` dari incoming Express/Node request dan meneruskannya ke request keluar downstream secara aman tanpa kebocoran thread-context?

5. **Mekanisme Event Replaying (Buffer Dispatcher):**  
   Pengguna mengklik tombol interaktif saat halaman telah selesai di-render oleh server (LCP tercapai) namun bundle JavaScript hydration belum selesai di-download atau diparsing oleh browser. Jelaskan cara kerja internal fitur *Event Replay* Angular dalam menangkap (*capturing*), menyimpan ke dalam *buffer*, dan memutar ulang (*replaying*) *user actions* tersebut tepat setelah hydration selesai tanpa kehilangan konteks *event target*.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck CPU Saturation & Node.js Crash saat Flash Sale
Sebuah platform e-commerce enterprise dengan arsitektur Angular SSR mengalami insiden Sev-1 ketika traffic melonjak tajam:
* **Gejala:** Penggunaan CPU pada container Node.js instan menyentuh 100%. Rata-rata TTFB anjlok dari 120ms ke 12 detik, disusul oleh cascading crash (Error: `JavaScript heap out of memory`) dan HTTP 504 Gateway Timeout di level Load Balancer/Cloudflare.
* **Kondisi Teknis:** Halaman katalog produk bersifat dinamis. Setiap request SSR memicu kompilasi template dan 4 pemanggilan API downstream independen melalui `HttpClient`.
* **Pertanyaan Diagnostik:**
  1. Langkah audit profiling apa yang harus segera Anda jalankan untuk memverifikasi apakah bottleneck terjadi akibat serialisasi DOM Angular, over-fetching data, atau event-loop starvation?
  2. Solusi arsitektur apa (misal: Dynamic SSR Caching via Redis, Edge Prerendering, HTTP Header `stale-while-revalidate`, atau degradasi terkontrol ke CSR via Fallback) yang akan Anda terapkan segera untuk menstabilkan cluster server tanpa menghilangkan SEO capability?

### Skenario B: Hydration Mismatch & Session Bleeding Akibat Timezone & Auth Leak
Portal perbankan menerapkan SSR untuk halaman landing dashboard publik yang memiliki widget jam transaksi dan status ringkasan user:
* **Gejala:**  
  1. Muncul error hydration masif di console client yang menyebabkan layout berkedip hebat (*flickering*) pada komponen jam/waktu transaksi.
  2. Laporan audit keamanan mendeteksi insiden fatal: Pengguna B yang membuka halaman landing secara berkala melihat teks "Selamat datang kembali, [Nama Pengguna A]" pada header untuk beberapa detik sebelum client-side script mengambil alih.
* **Pertanyaan Diagnostik:**
  1. Apa akar penyebab teknis dari ketidakcocokan DOM antara server dan client pada elemen waktu, dan bagaimana standardisasi eksekusi `formatDate` / UTC handling seharusnya diimplementasikan?
  2. Jelaskan mekanisme teknis spesifik yang menyebabkan kebocoran nama Pengguna A ke Pengguna B di lingkungan SSR Node.js, dan bagaimana Anda merekonstruksi siklus hidup dependensi injeksi (*injection scope*) untuk mencegah *state bleeding* ini selamanya?

### Skenario C: Dilema Arsitektur: SSG Skala Besar (1.000.000 SKU) vs On-Demand SSR
Perusahaan ritel global memiliki 1.000.000 halaman produk aktif. Tim engineer sedang memperdebatkan strategi rendering:
* **Dilema:**  
  * Tim A mengusulkan Static Site Generation (SSG) murni saat build-time menggunakan `@angular/ssr` prerendering agar biaya hosting server minimal dan TTFB mendekati 0ms via CDN. Namun, build time di CI/CD diproyeksikan memakan waktu lebih dari 18 jam.
  * Tim B mengusulkan Full SSR on-demand dengan pertimbangan update harga barang terjadi setiap beberapa menit, namun biaya compute cluster Kubernetes Node.js sangat tinggi.
* **Pertanyaan Diagnostik:**
  1. Mengapa implementasi SSG murni untuk 1 juta SKU tidak rasional secara operasional pipeline modern?
  2. Rancang solusi arsitektur hibrida (kombinasi SSG untuk core path, SSR dengan Edge/CDN caching layer, ISR-like pattern, dan client-side fallback) yang mampu menjamin performa TTFB < 200ms secara global, update data inventaris tetap akurat, dan efisiensi resource compute!

---

## 4. Chapter Challenge

### Tantangan Praktis: Mengimplementasikan Robust Hybrid SSR Pipeline dengan Caching, Authenticated State, & Safe Hydration

#### Deskripsi Masalah
Anda ditugaskan merombak aplikasi enterprise media berita yang sering mengalami *double-fetching*, *flickering* saat hydration, dan kegagalan SSR saat user terotentikasi mengakses data profil. Aplikasi harus mendukung performa *Core Web Vitals* optimal dengan merender artikel berita di server menggunakan cache pintar, sementara widget komentar di-load menggunakan deferred incremental hydration.

#### Requirements Teknis
1. **TransferState Implementation:**
   * Bangun data-access service yang mengambil data artikel melalui `HttpClient`.
   * Implementasikan caching state menggunakan `TransferState` dan `makeStateKey` sehingga pemanggilan API downstream hanya terjadi SEKALI di sisi server. Di browser, client harus mengonsumsi snapshot data dari DOM script tag tanpa mengeksekusi request HTTP kedua.
2. **Safe Platform Consumption:**
   * Buat sebuah directive atau utility service yang mengakses `localStorage` (untuk preferensi tema: Dark/Light).
   * Pastikan eksekusi kode sepenuhnya aman dari crash runtime ketika dieksekusi di Node.js platform tanpa menggunakan pengecekan `typeof window !== 'undefined'` secara *hardcoded* (wajib menggunakan token Angular `PLATFORM_ID`).
3. **Incremental Hydration & Deferrable Views:**
   * Pada template artikel, bungkus komponen interaktif berat `app-comment-section` menggunakan blok `@defer`.
   * Konfigurasikan `@defer` agar di-render sebagai placeholder di SSR, dan hanya mengalami *hydration* ketika user melakukan scroll hingga komponen masuk ke viewport (`hydrate on viewport`).
4. **Node.js Memory Cache Middleware:**
   * Pada file `server.ts` (Express engine), implementasikan in-memory caching layer berbasis URL (dengan TTL 60 detik) untuk rute publik `/article/:id`.
   * Cache harus di-bypass jika incoming request memiliki header `Authorization` atau cookie sesi login aktif untuk mencegah *cross-user cache poisoning*.

#### Batasan Arsitektur (Constraints)
* Wajib menggunakan Angular v17/v18+ dengan pola Standalone Components.
* Dilarang menggunakan `ngSkipHydration` di tingkat root component (`app-root`); hydration mismatch harus diselesaikan secara presisi pada level elemen sumber masalah.
* Memory footprint server Node.js tidak boleh meningkat secara progresif (pastikan TTL dan ukuran cache dibatasi).

#### Output yang Diharapkan
1. Kode file komponen dan service terkait (`article.service.ts`, `article-detail.component.ts`, `article-detail.component.html`).
2. Kode konfigurasi `server.ts` yang menunjukkan integrasi caching dan routing SSR.
3. Penjelasan teknis singkat (1-2 paragraf) mengenai verifikasi pengujian hydration melalui developer tools (menunjukkan tidak adanya double-network call dan zero-flicker).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara CSR, SSR, SSG, dan trade-off masing-masing terhadap Core Web Vitals (LCP, TTFB, INP).
- [ ] Siklus hidup dan arsitektur *Non-Destructive Hydration* Angular (bagaimana engine mencocokkan DOM tree tanpa menghancurkan elemen).
- [ ] Mengapa `TransferState` diperlukan dan format serialisasi data dari platform server ke client DOM.
- [ ] Peran `ApplicationRef.isStable` dalam menentukan kapan serialisasi HTML siap dieksekusi di platform Node.js.
- [ ] Bahaya kebocoran memori (*memory leak*) dan *cross-request state pollution* pada Singleton Services di lingkungan server multi-tenant.
- [ ] Perilaku compiler terhadap blok `@defer` dan strategi *Incremental Hydration* (`@defer (hydrate on ...)`).
- [ ] Batasan runtime Node.js dan cara melakukan mocking/abstraksi dependensi spesifik browser menggunakan `PLATFORM_ID` dan Document token.

### Saya tidak perlu menghafal:
- [ ] Seluruh kode boilerplate internal dari `@angular/ssr` atau factory generator template engine Express.
- [ ] String kode error internal Angular secara spesifik (cukup pahami konteks pesan error seperti `NG0500` = hydration mismatch).
- [ ] Spesifikasi byte-level representasi biner protokol transfer data di engine V8.

### Saya harus bisa melakukan:
- [ ] Mengonversi aplikasi Angular berbasis CSR menjadi aplikasi hybrid SSR/SSG menggunakan Angular CLI modern.
- [ ] Melakukan troubleshooting dan memperbaiki akar masalah error hydration mismatch tanpa membabi-buta menggunakan `ngSkipHydration`.
- [ ] Mengimplementasikan `TransferState` pada pipeline HTTP untuk mengeliminasi fenomena *flickering* dan *double-data fetching*.
- [ ] Mengonfigurasi propagasi cookie dan header HTTP secara aman dari Express server context ke Angular HTTP pipeline.
- [ ] Mengoptimalkan waktu load awal halaman interaktif menggunakan kombinasi `@defer`, *Event Replay*, dan *Incremental Hydration*.
- [ ] Mengaudit performa SSR menggunakan Node.js Profiler dan Chrome DevTools Network/Performance tab.