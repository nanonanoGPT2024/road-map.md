# BAB 04: Quiz, Challenge, & Knowledge Check
**Advanced CSS Grid Layouts dan Subgrid Engineering**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Track Sizing Algorithm & Sizing Constraints:**  
   Jelaskan secara matematis dan prosedural bagaimana browser layout engine (Blink/Gecko) menghitung distribusi ruang pada CSS Grid saat menggunakan unit `fr` yang dikombinasikan dengan fungsi `minmax()`. Mengapa penggunaan `1fr` secara default dapat memicu horizontal overflow pada konten teks panjang yang tidak terputus (*unbroken strings*), dan bagaimana intrinsic sizing minimum (`min-width: auto`) berperan di dalamnya?

2. **Perbedaan Fundamental Subgrid vs. Nested Grid:**  
   Bedah arsitektur layout engine saat memproses *nested grid* independen dibandingkan dengan *subgrid* (`grid-template-columns: subgrid` atau `grid-template-rows: subgrid`). Fokuskan analisis Anda pada bagaimana resolusi *track sizing*, propagasi *gap*, delegasi margin/padding, dan pembentukan grid formatting context (GFC) ditangani pada keduanya.

3. **Auto-Placement Algorithm (Sparse vs. Dense Packing):**  
   Bagaimana algoritma penempatan otomatis CSS Grid (Grid Auto-Placement Algorithm) mengevaluasi kursor penempatan (*placement cursor*) saat menempatkan elemen dengan properti `grid-auto-flow: row` versus `grid-auto-flow: row dense`? Jelaskan trade-off antara integritas urutan DOM (aksesibilitas dan keyboard navigation) dengan optimalisasi efisiensi pemanfaatan ruang visual.

4. **Line Naming Conventions & Implicit Lines:**  
   Jelaskan mekanisme resolusi nama garis (*named grid lines*) ketika dikonfigurasi melalui `grid-template-areas` dibandingkan dengan deklarasi eksplisit via bracket notation `[name-start]` dan `[name-end]`. Bagaimana browser secara implisit menghasilkan set garis `-start` dan `-end`, dan apa dampaknya jika developer mendeklarasikan nama garis yang sama berulang kali di berbagai trek?

5. **Intrinsic vs. Extrinsic Sizing Keywords:**  
   Bandingkan secara teknis penggunaan keyword `min-content`, `max-content`, dan `fit-content(argument)` dalam deklarasi trek grid. Berikan skenario layout di mana `fit-content(limit)` berhenti berperilaku seperti `max-content` dan bertransisi menjadi fixed clamp, serta analisis dampaknya terhadap *growth limit* pada trek yang bersangkutan.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **The Zero-Minimum Sizing Trap (`minmax(0, 1fr)` vs `1fr`):**  
   Sebuah komponen `Card` di dalam kontainer grid memiliki *child element* berupa tag `<pre><code>` yang memiliki `overflow-x: auto`. Namun, kontainer grid tetap melebar melebihi batas viewport dan memicu *horizontal scrollbar global*. Jelaskan secara mendalam mengapa mengganti `grid-template-columns: repeat(3, 1fr)` menjadi `grid-template-columns: repeat(3, minmax(0, 1fr))` menyelesaikan masalah tersebut ditinjau dari spesifikasi *Grid Sizing Algorithm Step 2: Resolve Intrinsic Track Sizes*.

2. **Subgrid Gap Inheritance vs. Local Gap Override:**  
   Diberikan parent grid dengan `gap: 24px`. Child item dideklarasikan sebagai subgrid:
   ```css
   .parent {
     display: grid;
     grid-template-columns: repeat(4, 1fr);
     gap: 24px;
   }
   .child-subgrid {
     grid-column: span 2;
     display: grid;
     grid-template-columns: subgrid;
     gap: 8px; /* Local override */
   }
   ```
   Bagaimana layout engine Gecko/Blink menangani perbedaan selisih 16px tersebut tanpa merusak keselarasan garis (*line alignment*) trek parent? Mengapa spesifikasi CSS Grid Level 2 mengizinkan *local gap override* pada subgrid, dan apa implikasi visualnya terhadap margin box child item di dalam trek tepi subgrid?

3. **Performance Cost of Dynamic Track Definition Updates:**  
   Dalam sebuah Single Page Application (SPA), state filter mengubah `grid-template-areas` secara dinamis melalui inline style atau class mutation setiap kali terjadi interaksi pengguna. Analisis siklus render browser (Recalculate Style $\rightarrow$ Layout/Reflow $\rightarrow$ Paint $\rightarrow$ Composite). Mengapa mutasi pada `grid-template-areas` atau `grid-template-columns` berpotensi memicu *forced synchronous layout* (layout thrashing) dibandingkan memanipulasi posisi visual elemen melalui transformasi CSS (`transform`)?

4. **Aspect-Ratio & Dynamic Track Sizing Cycle:**  
   Ketika sebuah grid item memiliki properti `aspect-ratio: 16/9` dan ditempatkan pada trek baris yang berukuran `grid-template-rows: auto`, sementara trek kolom berukuran `minmax(min-content, 1fr)`, bagaimana browser menghindari *infinite cyclic dependency* (di mana lebar kolom menentukan tinggi baris, yang kemudian mengubah ketersediaan tinggi viewport dan memengaruhi lebar kolom kembali)? Parameter apa yang digunakan browser untuk memutus siklus evaluasi ini?

5. **Stacking Context & Auto-Placed Item Z-Ordering:**  
   Dua grid items menempati sel grid yang sama (overlapping tracks): Elemen A menggunakan posisi eksplisit `grid-area: 1 / 1 / 3 / 3`, sedangkan Elemen B ditempatkan secara otomatis menggunakan `grid-auto-flow: dense`. Keduanya tidak memiliki properti `z-index`. Item mana yang dirender di atas item lainnya, dan bagaimana modifikasi nilai `opacity`, `transform`, atau `mix-blend-mode` pada salah satu item mengubah urutan render tanpa mengubah struktur DOM tree?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Layout Thrashing & CLS pada High-Frequency Trading Terminal
Sebuah platform analitik finansial menampilkan *real-time order book* dan metrik transaksi menggunakan nested grid multidimensi. Terdapat 60 baris data per detik yang masuk melalui WebSocket. Setiap baris data memiliki sub-elemen (Bid, Ask, Spread, Volume) yang harus terisi dan sejajar sempurna di seluruh kolom terminal.
* **Gejala:** Profiling via Chrome DevTools Performance panel menunjukkan frame rate anjlok hingga 18 FPS. Trace mencatat event *Layout* memakan waktu ~45ms per frame dengan visual jank dan Cumulative Layout Shift (CLS) sebesar 0.35 saat baris baru dimasukkan ke dalam DOM.
* **Pertanyaan Diagnostik:**
  1. Identifikasi akar penyebab mengapa nested grid dengan dynamic text insertion memicu reflow masif di seluruh tree hierarki DOM.
  2. Bagaimana Anda merancang ulang arsitektur layout menggunakan kombinasi `CSS Subgrid`, `contain: layout size`, dan `content-visibility: auto` untuk mengisolasi boundary layout engine dan mempertahankan 60 FPS?

### Skenario B: Dynamic Content Expansion & Truncation Race Condition pada E-Commerce Cards
Sebuah katalog produk e-commerce berskala enterprise menggunakan CSS Grid 4-kolom untuk menampilkan kartu produk. Setiap kartu berisi gambar produk, label diskon, judul produk multi-baris (panjang bervariasi antara 1 hingga 4 baris), rating bintang, dan tombol CTA "Beli Sekarang".
* **Gejala:** Desainer menuntut agar seluruh judul produk memiliki tinggi baris yang terkoordinasi secara visual (baris CTA selalu sejajar di bagian bawah kartu pada setiap row grid horizontal), tetapi implementasi Flexbox lama menghasilkan tombol CTA melayang jika judul produk hanya 1 baris. Saat migrasi ke Subgrid dilakukan, gambar produk yang di-load secara asinkron (*lazy-loaded*) memicu lonjakan tinggi trek yang memotong teks judul saat font eksternal (*web fonts*) selesai diunduh.
* **Pertanyaan Diagnostik:**
  1. Rancang arsitektur CSS Grid Level 2 (Subgrid) hierarkis (Parent Grid $\rightarrow$ Card Component $\rightarrow$ Card Internal Subgrid) yang menjamin tombol CTA sejajar sempurna horizontal per baris tanpa menggunakan JavaScript `height-syncing`.
  2. Bagaimana Anda mengatasi *font-swap layout shifting* dan *image reflow* pada subgrid tersebut menggunakan `font-display: optional`, `size-adjust`, dan CSS aspect-ratio containment?

### Skenario C: Architecture Trade-off: Enterprise Design System Component Federation
Tim inti Core UI/UX Enterprise sedang membangun komponen data table yang dapat dikustomisasi oleh 12 tim domain produk yang berbeda via Micro-frontend (MFE). Komponen table ini harus mendukung:
1. Kolom dinamis yang dapat disembunyikan/ditampilkan (*toggleable columns*).
2. Pinned columns (kiri dan kanan).
3. Expandable child rows yang memiliki layout internal sendiri namun tetap menghormati batas kolom tabel utama.
* **Pertanyaan Diagnostik:**
  1. Evaluasi secara kritis trade-off arsitektural antara:
     * **Pendekatan A:** Monolithic CSS Grid di level tabel parent dengan seluruh cell didelegasikan flat ke DOM.
     * **Pendekatan B:** Multi-layer federated architecture menggunakan CSS Subgrid (Table $\rightarrow$ Row $\rightarrow$ Cell).
     * **Pendekatan C:** CSS Container Queries (`@container`) dikombinasikan dengan Flexbox independen pada tiap baris.
  2. Manakah pendekatan yang paling meminimalisir *coupling* antar-MFE, memiliki performa render terbaik pada 5000+ nodes, dan tetap mendukung aksesibilitas semantik tabel HTML (`<table>`, `<tr>`, `<td>`)? Sertakan pembenaran teknisnya.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise SaaS Multi-Tenant Analytics Matrix with Bi-Directional Subgrid Alignment and Dynamic Density Control

#### Problem Statement
Anda ditugaskan membangun dashboard matriks perbandingan performa multi-tenant untuk sistem analitik enterprise. Setiap baris merepresentasikan metrik bisnis (misalnya: *Revenue, Churn, CAC, LTV*), dan setiap kolom merepresentasikan unit bisnis regional. Dashboard memiliki persyaratan visual yang sangat ketat: seluruh kartu metrik lintas baris dan kolom harus sejajar secara dua arah (*bi-directional alignment*). Artinya, header internal kartu, grafik mini (sparkline), dan footer kartu harus memiliki ukuran vertikal yang seragam di sepanjang baris horizontal, sementara lebar kolom harus merespons ukuran konten regional terlebar secara otomatis.

#### Requirements
1. **Parent-Child Subgrid Architecture:**
   * Parent container mendefinisikan layout makro (sidebar dan content matrix).
   * Matriks utama harus menggunakan CSS Grid eksplisit untuk kolom dan baris.
   * Setiap *Metric Card* di dalam matriks harus memanfaatkan `grid-template-rows: subgrid` pada sumbu vertikal (terdiri dari 3 trek: Header, Body/Sparkline, Footer) sehingga seluruh Header pada baris yang sama memiliki tinggi identik, terlepas dari variasi panjang teks judul.
2. **Dynamic UI Density Switching:**
   * Sistem harus mendukung tiga mode densitas data via data attribute pada root: `data-density="compact"`, `data-density="normal"`, dan `data-density="spacious"`.
   * Perubahan densitas HANYA boleh mengubah variabel CSS resolusi trek dan padding tanpa memicu reflow rekursif di JavaScript (zero JS runtime untuk layout re-calculation).
3. **Robust Overflow & Containment:**
   * Tidak boleh ada layout breakout: string teks panjang harus di-*truncate* dengan elipsis di dalam subgrid tanpa merusak kalkulasi lebar trek kolom induk.
   * Gunakan `minmax(0, 1fr)` atau intrinsic constraints yang tepat untuk mencegah fenomena zero-minimum collapse.
4. **Fallback & Graceful Degradation Strategy:**
   * Implementasikan CSS Feature Queries (`@supports (grid-template-rows: subgrid)`) untuk menyediakan fallback berbasis flexbox/grid konvensional yang dapat diterima untuk browser legacy yang belum mendukung subgrid.

#### Constraints
* **Pure CSS Layout Engine:** Dilarang menggunakan JavaScript untuk mengukur dimensi elemen (`getBoundingClientRect`, `offsetHeight`, dsb.) atau menyelaraskan tinggi elemen.
* **Strict DOM Semantics:** Gunakan markup semantik (`<section>`, `<article>`, `<header>`, `<footer>`, `<figure>`).
* **Zero External Layout Libraries:** Tidak boleh menggunakan framework CSS (Tailwind, Bootstrap, dll.). Tuliskan Pure Vanilla CSS modern (CSS Nesting diperbolehkan sesuai standar W3C).

#### Expected Output
* Kode HTML semantik lengkap yang merepresentasikan struktur matriks minimal 2 regional column dan 2 rows matriks (total 4 cards, masing-masing memiliki header bervariasi panjangnya).
* Kode CSS production-ready terstruktur yang mencakup:
  1. CSS Custom Properties untuk sistem densitas dan konfigurasi trek.
  2. Implementasi Parent Grid dan Bi-directional Subgrid alignment.
  3. Konfigurasi truncation text aman di dalam grid item.
  4. Blok `@supports` fallback handling.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme matematis resolusi Grid Track Sizing Algorithm (Base Size, Growth Limit, Unconstrained vs Constrained space).
- [ ] Perbedaan fundamental arsitektur layout engine antara CSS Subgrid (sharing track context) vs Nested Grid independen.
- [ ] Pengaruh intrinsic sizing default (`min-width: auto`) terhadap layout overflow dan solusinya menggunakan `minmax(0, ...)`.
- [ ] Perilaku transmisi dan override properti `gap` pada implementasi subgrid satu sumbu (aksial) maupun dua sumbu (bi-aksial).
- [ ] Urutan penempatan algoritma penempatan otomatis CSS Grid (Grid Placement Algorithm) dengan flag `dense` serta dampaknya terhadap traversal fokus keyboard (AOM vs DOM).
- [ ] Karakteristik performa dan isolasi layout boundary menggunakan properti `contain` pada antarmuka CSS Grid yang padat data.

### Saya tidak perlu menghafal:
- [ ] Sintaks mikro shorthand kompleks `grid` 1 baris yang menggabungkan template-rows, template-columns, template-areas, auto-flow, auto-rows, dan auto-columns secara bersamaan (lebih baik gunakan longhand demi maintainability enterprise).
- [ ] Algoritma spesifik per-browser untuk pembulatan subpixel (*subpixel antialiasing/rounding calculation*) pada trek pecahan `fr`.
- [ ] Daftar lengkap vendor prefix masa lalu untuk CSS Grid engine versi IE10/IE11 (`-ms-grid-*`).

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan mengeliminasi bug horizontal scrolling tak diinginkan yang dipicu oleh interaksi teks panjang dengan trek `1fr`.
- [ ] Mengonfigurasi subgrid satu sumbu (`grid-template-rows: subgrid` atau `grid-template-columns: subgrid`) untuk menyelaraskan elemen internal komponen anak melintasi beberapa sel induk secara horizontal maupun vertikal.
- [ ] Menggunakan DevTools Grid Inspector (Chrome/Firefox/Safari) untuk memeriksa garis grid eksplisit, implisit, area name, serta subgrid inheritance paths.
- [ ] Menuliskan strategi progressive enhancement menggunakan `@supports` untuk memastikan aplikasi tetap fungsional di lingkungan browser yang tidak mendukung CSS Subgrid.
- [ ] Merancang antarmuka dashboard kompleks yang responsif dengan kombinasi fungsi `minmax()`, `repeat(auto-fit, ...)`, dan `clamp()` tanpa ketergantungan media query berlebih.