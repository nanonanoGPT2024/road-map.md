# BAB 04: Quiz, Challenge, & Knowledge Check
**Sistem Tata Letak Modern: Flexbox & CSS Grid Multi-Dimensi**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Paradigma Dimensi & Alur Konten (1D vs 2D):** Jelaskan perbedaan mendasar antara filosofi *content-first layout* pada Flexbox (1-dimensi) dan *layout-first structure* pada CSS Grid (2-dimensi). Bagaimana browser engine memperlakukan kalkulasi ruang sisa (*available space distribution*) ketika menangani item yang membungkus (*wrapping*) pada `flex-wrap: wrap` dibandingkan dengan track implicit pada CSS Grid?
2. **Dekomposisi Shorthand `flex`:** Secara spesifikasi W3C, apa perbedaan kalkulasi matematis render engine browser saat sebuah flex item dideklarasikan dengan `flex: 1`, `flex: auto`, dan `flex: 0`? Uraikan nilai ekspansinya terhadap triplet `flex-grow`, `flex-shrink`, dan `flex-basis`, serta dampaknya terhadap *hypothetical main size*.
3. **Mekanisme Distribusi Unit Fraksional (`fr`):** Bagaimana CSS Grid menghitung alokasi unit `fr` ketika digabungkan dengan track berukuran absolut (misal: `px`), persentase (`%`), dan intrinsic sizing (`min-content` / `max-content`)? Tuliskan tahapan eliminasi ruang sisa (*free space resolution algorithm*) yang dilakukan engine.
4. **Eksplisit vs Implisit Grid:** Jelaskan siklus hidup penempatan item pada Grid. Kapan sebuah *implicit track* tercipta, dan bagaimana peran properti `grid-auto-flow` (khususnya nilai `dense`) dalam memanipulasi penataan *auto-placement cursor* ketika terjadi fragmentasi ruang kosong?
5. **Matriks Box Alignment:** Properti `justify-*` dan `align-*` beroperasi berdasarkan sumbu koordinat. Analisis mengapa `justify-content` pada CSS Grid mengatur penempatan track di dalam grid container, sedangkan pada Flexbox mengatur item di sepanjang *main axis*. Jelaskan pula bagaimana `margin: auto` berinteraksi dengan Box Alignment Module di kedua konteks tersebut.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **The Flex Item `min-width: auto` Trap:** Mengapa teks panjang tanpa spasi (atau blok kode) di dalam flex item sering kali merusak layout dan meluber (*overflow*) ke luar viewport meskipun flex container telah diberi `max-width: 100%` dan item memiliki `flex-shrink: 1`? Jelaskan mekanisme internal *automatic minimum size* pada flex items dan bagaimana solusinya secara spesifikasi CSS.
2. **Track Sizing Constraints (`minmax()` & Intrinsic Sizing):** Analisis mengapa deklarasi `grid-template-columns: repeat(auto-fit, minmax(300px, 1fr))` dapat menyebabkan *horizontal scrolling bug* pada perangkat mobile dengan lebar viewport `< 300px`. Bagaimana formulasi CSS yang benar untuk menjaga elastisitas container tanpa melanggar batas viewport?
3. **Stacking Context & Re-ordering Implications:** Apa konsekuensi arsitektural penggunaan `order` pada Flexbox/Grid terhadap pohon aksesibilitas (*accessibility tree* / *DOM order*) dan *keyboard tab navigation*? Kapan flex/grid item membentuk *Stacking Context* baru tanpa deklarasi `position: relative/absolute` secara eksplisit?
4. **Subgrid Deep Mechanics:** Dalam CSS Grid Level 2, bagaimana `subgrid` mengalirkan definisi track dari parent ke nested children? Apa trade-off performa rendering saat browser harus menyinkronkan ukuran track melintasi beberapa level kedalaman DOM (*nested context*), dan bagaimana penanganan `gap` inheritance-nya?
5. **Layout Thrashing & Rendering Pipeline:** Ditinjau dari Chromium Rendering Engine (Blink), mengapa mengubah ukuran container Flexbox yang memiliki banyak child dengan `flex-grow` dinamis membutuhkan kalkulasi *Recalculate Style* dan *Layout/Reflow* yang lebih intensif dibandingkan memutasi track CSS Grid berbasis fixed/fractional? 

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Bottleneck Performa pada Financial Trading Dashboard
Sebuah aplikasi web dashboard analitik keuangan menampilkan *data grid* dinamis berisi 500 komponen kartu metrik yang di-render secara bersamaan. Arsitek sebelumnya menggunakan `display: flex` bersarang (*deeply nested flex containers*, 6 level kedalaman) dengan konfigurasi `flex-grow: 1` dan `flex-basis: 0` pada setiap kolom agar kartu fleksibel. Saat WebSocket menerima update data pasar setiap 250ms, frame rate anjlok hingga 15 FPS akibat waktu *Layout Phase* di DevTools mencapai > 50ms.
* **Pertanyaan Diagnostik:**
  1. Mengapa struktur Flexbox bertingkat tersebut memicu algoritma penyelesaian ukuran (*flex layout multi-pass algorithm*) yang eksponensial?
  2. Rancang ulang arsitektur tata letak container utama menggunakan CSS Grid untuk mereduksi kalkulasi reflow menjadi *single-pass*, sembari mempertahankan aspek responsif komponen kartu.

### Skenario B: Truncation & Flex-Shrink Integrity Collapse pada Design System
Pada komponen Global Navigation Bar di sebuah platform enterprise berskala global, terdapat container `flex` horizontal yang menampung: [Logo Perusahaan], [Search Bar (fleksibel)], dan [User Profile Dropdown (berisi Avatar & Nama Lengkap)]. Ketika aplikasi dijalankan dalam bahasa Jerman (*i18n* dengan teks panjang), avatar mengecil secara abnormal (*squished/distorted*) dan Search Bar menimpa tombol navigasi, sementara nama user terpotong tanpa indikator elipsis (`...`).
* **Pertanyaan Diagnostik:**
  1. Identifikasi kegagalan kalkulasi *flex-shrink factor* dan *intrinsic content sizing* yang menyebabkan distorsi avatar dan pecahnya Search Bar.
  2. Tuliskan blok aturan CSS presisi (mencakup proteksi rasio aspek, flex items sizing limits, dan mekanisme text overflow) untuk memastikan Navbar tersebut *bulletproof* terhadap variasi panjang teks i18n.

### Skenario C: Trade-off Arsitektur E-Commerce Product Card (Flex vs Grid vs Subgrid)
Tim Design System diminta merancang kartu produk e-commerce (*Product Card*) yang memiliki: Gambar Produk, Judul Produk (panjang dinamis: 1-3 baris), Tag Promosi, Rating Bintang, dan Tombol "Tambah ke Keranjang" di posisi paling bawah. Masalah timbul: ketika beberapa kartu dijajarkan dalam satu baris, perbedaan panjang judul menyebabkan tombol "Tambah ke Keranjang" berada pada ketinggian vertikal yang tidak seragam, merusak estetika antarmuka.
* **Pertanyaan Diagnostik:**
  1. Bandingkan 3 pendekatan teknis untuk menyelesaikan masalah ini: (a) Flexbox dengan `margin-top: auto` pada tombol, (b) CSS Grid di dalam setiap kartu, dan (c) CSS Grid Level 2 (`subgrid`).
  2. Lakukan evaluasi trade-off arsitektural dari ketiga pendekatan tersebut berdasarkan kriteria: pemeliharaan kode (*maintainability*), fleksibilitas konten dinamis, dan kompatibilitas peramban (*browser support*). Solusi mana yang harus menjadi standar produksi?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Multi-Role Observability Dashboard Layout
Membangun layout dashboard observabilitas sistem (*mission-critical telemetry UI*) yang sepenuhnya adaptif dan responsif tanpa menggunakan *hardcoded media queries* untuk breakpoints kartu metrik, mengombinasikan CSS Grid dan Flexbox secara ortogonal.

#### Problem Statement
Anda ditugaskan mengimplementasikan layout untuk satu halaman telemetri sistem yang harus berjalan sempurna pada resolusi 320px (Mobile) hingga 3840px (Ultra-wide 4K Monitor). Dashboard harus memiliki sidebar navigasi yang dapat diciutkan (*collapsible*), area utama dengan header kontrol, grid metrik analitik yang otomatis menyesuaikan jumlah kolom berdasarkan ketersediaan ruang, serta panel log konsol dengan kemampuan *split-view*.

#### Requirements
1. **Shell Container (CSS Grid 2D):**
   - Gunakan CSS Grid untuk kerangka utama halaman: Sidebar, Header, Main Content, dan Footer/Status Bar.
   - Sidebar memiliki lebar minimum `240px` dan maksimum `300px` saat terbuka, namun dapat diciutkan (*collapsed*) menjadi `64px` menggunakan modulasi utility class state tanpa merusak struktur grid.
   - Header harus *sticky* di bagian atas viewport konten utama.

2. **Metrics Section (Adaptive Grid without Media Queries):**
   - Buat grid metrik analitik yang menampilkan N-kartu statistik.
   - Kartu harus menggunakan teknik `repeat()`, `auto-fit`, dan `minmax()` dengan batas ukuran minimum per kartu `280px` dan batas maksimum `1fr`.
   - Gunakan CSS Subgrid pada Product/Metric Card internal agar judul metrik dan data numerik antar kartu pada baris yang sama sejajar secara sempurna terlepas dari variasi panjang label teks.

3. **Card Component Internal (Flexbox 1D):**
   - Di dalam setiap kartu metrik, gunakan Flexbox untuk mendistribusikan:
     - Header kartu (Ikon metrik + Judul + Kebab Menu button). Menu button tidak boleh tertekan (*cannot shrink*).
     - Body kartu (Nilai metrik raksasa + Status perubahan persentase).
     - Footer kartu (Timestamp update yang selalu terkunci di dasar kartu).

4. **Console Log Section (Flexbox Overflow & Truncation):**
   - Menampilkan daftar log terminal di bawah grid metrik.
   - Setiap baris log berisi: [Timestamp (fixed)] + [Badge Level (INFO/WARN/ERR)] + [Message (dapat sangat panjang)] + [Action Button].
   - Pesan log yang melampaui sisa lebar baris harus terpotong secara rapi dengan elipsis (`text-overflow: ellipsis; white-space: nowrap`), tanpa menekan timestamp, badge, ataupun action button.

#### Constraints
- **Zero Breakpoint Hardcoding:** Bagian Metrics Grid dilarang menggunakan `@media (min-width: ...)` untuk mengubah jumlah kolom. Penataan kolom murni diatur oleh kalkulasi engine CSS Grid.
- **No Overflow Leakage:** Tidak boleh ada *horizontal scrollbar* tak terduga yang muncul pada level document body (`overflow-x: hidden` pada `body` dilarang sebagai jalan pintas; container harus mengelola dimensinya secara presisi).
- **Semantics:** Gunakan tag HTML5 yang valid (`<aside>`, `<header>`, `<main>`, `<section>`, `<article>`).

#### Expected Output
1. File HTML semantik yang mencerminkan struktur layout secara hierarkis.
2. File CSS produksi yang modular, bebas bug overflow flexbox (`min-width: 0`), dan menerapkan Box Alignment Module secara deterministik.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Logika matematika distribusi ukuran Flexbox: relasi antara `flex-grow`, `flex-shrink`, `flex-basis`, dan *remaining space*.
- [ ] Mekanisme kalkulasi *track sizing* pada CSS Grid (`minmax()`, `fit-content()`, `fr`, dan keyword intrinsic `min-content`/`max-content`).
- [ ] Penyebab utama overflow pada Flexbox dan mitigasinya menggunakan `min-width: 0` / `min-height: 0`.
- [ ] Perbedaan fungsional antara `auto-fill` dan `auto-fit` pada deklarasi `repeat()` Grid.
- [ ] Cara kerja CSS Grid Level 2 `subgrid` dalam mengintegrasikan nested context ke dalam koordinat parent grid.
- [ ] Dampak Box Alignment Module (`justify-*`, `align-*`, `place-*`) terhadap sumbu kartesian spesifik (Main vs Cross vs Inline vs Block).
- [ ] Implikasi pengubahan tatanan visual menggunakan properti `order` terhadap aksesibilitas (Screen Readers & Tab Index).

### Saya tidak perlu menghafal:
- [ ] Seluruh variasi sintaks legacy flexbox (`display: box`, `display: -webkit-flex`, dsb.).
- [ ] Deretan nilai desimal presisi untuk konversi lebar kontainer responsif tertentu (serahkan pada unit fraksional dan `calc()`).
- [ ] Spesifikasi nama alias track grid yang terlalu kompleks untuk layout sepele; prioritaskan struktur yang mudah dibaca tim.

### Saya harus bisa melakukan:
- [ ] Mengonstruksi layout layout-first (Grid) dan content-first (Flexbox) secara terpisah maupun secara *hybrid/nested* tanpa memicu layout thrashing.
- [ ] Melakukan isolasi dan debugging layout overflow menggunakan browser developer tools (Flexbox/Grid Inspector overlays).
- [ ] Mengimplementasikan *fluid responsive layout* yang beradaptasi secara mulus tanpa ketergantungan ekstrem pada media queries.
- [ ] Menerapkan aturan perataan vertikal dan horizontal yang konsisten di berbagai komponen design system.
- [ ] Menangani text truncation dan dynamic string elasticity di dalam flex containers tanpa merusak rasio elemen interaktif lain.