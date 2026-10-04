# BAB 06: Quiz, Challenge, & Knowledge Check
**Aksesibilitas Web Mendalam (A11y) & Integrasi WAI-ARIA**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Mekanisme First Rule of ARIA & Mutasi Accessibility Tree
Aturan pertama WAI-ARIA menyatakan: *"If you can use a native HTML element or attribute with the semantics and behavior you require already built-in, instead of re-purposing an element and adding an ARIA role, state or property to make it accessible, then do so."* 

Jelaskan secara mendalam bagaimana browser engine (misalnya Blink atau WebKit) memproses elemen `<button>` bawaan dibandingkan dengan `<div role="button" tabindex="0">` di dalam *Accessibility Tree* (AOM)! Mengapa penambahan ARIA tidak otomatis menyertakan kapabilitas *keyboard event handling*, fokus manajemen native, dan aktivasi via tombol `Enter`/`Space`?

### Soal 1.2: Dekonstruksi Algoritma Accessible Name Computation (AccName)
Sebutkan dan urutkan langkah-langkah resolusi prioritas yang dieksekusi oleh mesin browser dalam *Accessible Name and Description Computation (AccName) 1.2* untuk menentukan accessible name dari sebuah elemen interaktif! Apa yang terjadi jika sebuah elemen memiliki atribut `aria-labelledby`, `aria-label`, teks konten langsung (*subtree*), dan atribut `title` secara bersamaan?

### Soal 1.3: Kalkulasi Kontras Relatif & Perbedaan WCAG 2.1 vs 2.2
Berdasarkan spesifikasi WCAG 2.1/2.2 Level AA dan AAA:
1. Bagaimana formula matematis rasio kontras luminansi relatif ($L1 + 0.05) / (L2 + 0.05)$ diterapkan pada teks normal vs teks besar (*large text*)?
2. Jelaskan kriteria keberhasilan untuk kontras elemen antarmuka non-teks (*Non-text Contrast* - SC 1.4.11) seperti indikator fokus (*focus ring*), *checkbox boundary*, dan status grafis! Mengapa teknik *subpixel antialiasing* pada font rendering di browser dapat menggagalkan kepatuhan rasio kontras pada pengujian tingkat piksel?

### Soal 1.4: Semantik Landmark dan Hierarki Region
Bagaimana elemen landmark HTML5 (`<header>`, `<nav>`, `<main>`, `<aside>`, `<footer>`, `<form>`, `<section>`) diterjemahkan ke dalam platform Accessibility API (UIA, NSAccessibility, ATK)? Dalam kondisi arsitektur spesifik seperti apa elemen `<section>` kehilangan status landmark-nya, dan bagaimana cara memulihkan status landmark tersebut secara tepat menurut standar W3C?

### Soal 1.5: Disosiasi Focus Order vs DOM Order
Jelaskan dampak arsitektural dari manipulasi tata letak visual menggunakan CSS (`order` pada Flexbox, `grid-template-areas`, atau `position: absolute`) terhadap *Sequential Focus Navigation Order* (DOM order)! Mengapa ketidakselarasan antara alur visual dan alur fokus keyboard melanggar kriteria WCAG 2.4.3 (*Focus Order*), dan bagaimana peran atribut `tabindex` (nilai `0`, `-1`, dan bilangan positif) dalam memperparah atau memitigasi masalah ini?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Siklus Hidup Event & Mutasi ARIA Live Regions
Analisis perbedaan implementasi browser engine saat mengeksekusi mutasi DOM pada elemen berkonfigurasi `aria-live="polite"` versus `aria-live="assertive"`. 
1. Kapan tepatnya browser mengirimkan *accessibility event* ke *Assistive Technology* (AT) daemon?
2. Mengapa memasukkan kontainer `aria-live` secara dinamis bersamaan dengan teks barunya ke dalam DOM sering kali menghasilkan kegagalan *announcement* (*silent failure*) pada pembaca layar NVDA atau VoiceOver, dan bagaimana struktur DOM yang benar untuk mencegah *edge case* tersebut?

### Soal 2.2: Isolasi Interaksi Menggunakan Atribut `inert` vs `aria-modal="true"`
Bandingkan mekanisme internal penanganan modal dialog antara penggunaan atribut standar HTML `inert` pada node *sibling* dengan atribut ARIA legacy `aria-modal="true"`:
* Bagaimana masing-masing pendekatan memengaruhi traversal *virtual cursor* pada pembaca layar dan navigasi fokus keyboard tab?
* Mengapa `aria-modal="true"` tanpa isolasi fokus manual berbasis JavaScript masih memungkinkan kebocoran interaksi keyboard pada sebagian browser dan screen reader?

### Soal 2.3: `aria-activedescendant` vs Roving Tabindex pada Komponen Gabungan
Pada komponen interaktif kompleks (misalnya: *WAI-ARIA 1.2 Combobox* atau *DataGrid*), arsitek frontend harus memilih antara pola *Roving Tabindex* atau `aria-activedescendant`.
* Jelaskan perbedaan fundamental kedua mekanisme tersebut dalam hal konsumsi memori, manipulasi atribut DOM, dan pergerakan *hardware focus* vs *virtual focus*!
* Skenario performa ekstrem mana yang membuat `aria-activedescendant` jauh lebih unggul dibandingkan *Roving Tabindex*?

### Soal 2.4: Visibilitas Konten: Analisis Dampak Hiding Techniques terhadap AOM
Berikan matriks dampak teknis terhadap rendering visual, ketersediaan di DOM Tree, keterbacaan di Accessibility Tree, dan fokusibilitas keyboard untuk kelima teknik penyembunyian konten berikut:
1. `display: none`
2. `visibility: hidden`
3. `hidden="until-found"`
4. `aria-hidden="true"`
5. Utility class `.sr-only` (menggunakan CSS clipping: `clip: rect(...)` / `clip-path`)

Jelaskan sebuah skenario kerentanan keamanan atau kebocoran data (*information disclosure*) yang dapat terjadi akibat penyalahgunaan teknik `.sr-only` atau `aria-hidden="true"`.

### Soal 2.5: Debugging State Inconsistency pada Dynamic Accessible Name
Perhatikan potongan kode markup berikut:
```html
<button id="cart-btn" aria-labelledby="cart-heading cart-count">
  <span id="cart-heading" aria-label="Keranjang Belanja">Toko</span>
  <span id="cart-count">3</span> item
</button>
```
1. Menurut algoritma AccName 1.2, apakah accessible name akhir yang dihitung oleh browser untuk tombol `#cart-btn`?
2. Tunjukkan titik kegagalan semantik pada snippet di atas dan lakukan refaktorisasi markup agar terbaca dengan presisi sebagai *"Keranjang Belanja: 3 item"* oleh Assistive Technology!

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Audit Kepatuhan Regulasi & Form Validation Engine pada Checkout Enterprise
Sebuah platform e-commerce enterprise dengan jutaan transaksi harian menghadapi ancaman denda kepatuhan hukum terkait disabilitas (misal: EAA / ADA Title III) karena alur checkout multi-step mereka dinilai tidak dapat diakses. 

**Kondisi Sistem:**
* Validasi formulir dilakukan secara asinkronus (API-driven). Ketika pengguna menekan tombol *Submit*, validasi microservice mengembalikan array error field.
* Komponen form saat ini me-render pesan kesalahan berupa teks merah di bawah masing-masing input: `<span class="err-msg">Nomor kartu kredit tidak valid</span>`.
* Fokus pengguna tetap berada di tombol *Submit* atau dilempar secara acak ke puncak form. Pengguna pembaca layar (screen reader) melaporkan bahwa mereka tidak menerima feedback apa pun saat tombol ditekan dan formulir gagal submit.

**Tugas Diagnostik & Arsitektural:**
1. Desain arsitektur markup dan manajemen ARIA (`aria-invalid`, `aria-describedby`, `aria-errormessage`) untuk mengaitkan error message secara deterministik ke masing-masing *form control*!
2. Rancang strategi fokus keyboard yang paling ergonomis dan patuh WCAG 2.2 (SC 3.3.1 Error Identification & SC 3.3.3 Error Suggestion) saat terjadi kegagalan validasi multi-field! Elemen mana yang harus menerima fokus pertama kali, dan bagaimana struktur pesan ringkasannya (*Error Summary*)?

### Skenario B: Race Condition pada SPA Route Transitions & Focus Announcer
Pada aplikasi Single Page Application (SPA) berbasis framework modern, navigasi antar-rute tidak memicu *full page reload*. Tim QA menemukan dua *critical bug*:
1. Ketika berpindah halaman dari `/catalog` ke `/product/123`, VoiceOver pada Safari (iOS/macOS) tetap membacakan sisa konten dari halaman katalog sebelum berpindah, atau langsung diam tanpa mengumumkan judul halaman baru.
2. Fokus keyboard tersangkut di elemen link yang baru saja diklik (yang kini sudah hilang dari DOM), sehingga browser mereset fokus keyboard kembali ke elemen `<body>`. Hal ini memaksa pengguna keyboard untuk menekan Tab puluhan kali untuk mencapai konten utama.

**Tugas Diagnostik & Arsitektural:**
1. Bedah *root cause* dari *race condition* antara manipulasi `document.title`, penghapusan komponen rute lama dari DOM, dan keterlambatan pembacaan live region pada level Platform Accessibility API!
2. Buat rancangan arsitektur modul `RouteAnnouncer` dan *Focus Management Strategy* vanilla/framework-agnostic yang mencakup:
   * Pengalihan fokus ke target yang valid (`<h1>` halaman baru atau *skip-to-content target*).
   * Penanganan transisi accessible name melalui live region terisolasi yang bebas dari *glitch* pemotongan suara (*speech truncation*).

### Skenario C: Trade-off Arsitektur Komponen Kompleks: Multi-Select TreeView dengan Virtual Scrolling
Design System enterprise Anda membutuhkan komponen hierarkis *Directory File TreeView* yang harus menangani 50.000 nodes. Untuk menjaga performa runtime 60fps, tim mengintegrasikan algoritma *DOM virtualization* (hanya me-render 30 node yang berada di dalam viewport).

**Tantangan Sistem:**
* Struktur virtual DOM meratakan struktur pohon menjadi flat nodes:
  ```html
  <div class="virtual-scroll-container">
    <div class="tree-node" style="transform: translateY(120px); padding-left: 32px;">File A.txt</div>
  </div>
  ```
* Virtualisasi menghancurkan relasi parent-child asli di DOM dan menyebabkan screen reader kehilangan konteks hierarki, jumlah level kedalaman (*nesting level*), dan total item dalam grup.
* Fokus keyboard sering kali hilang saat pengguna melakukan scroll cepat menggunakan tombol *Down Arrow*, karena node yang dituju belum selesai di-mount ke DOM oleh virtualizer.

**Tugas Diagnostik & Arsitektural:**
1. Tentukan set atribut WAI-ARIA (`role="tree"`, `role="treeitem"`, `role="group"`, `aria-level`, `aria-setsize`, `aria-posinset`, `aria-expanded`) yang harus dihitung dan diinjeksi secara matematis ke dalam flat virtual node agar screen reader menerima representasi pohon yang utuh!
2. Bagaimana Anda merancang interaksi keyboard (panah atas/bawah/kiri/kanan/Home/End) agar tetap sinkron dengan *render-buffer* virtual scrolling tanpa menyebabkan *focus dropping* ke `<body>` saat node target berada di luar viewport?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Komponen "Headless-Grade Accessible Modal Dialog"

#### Problem Statement
Sebagian besar implementasi modal dialog custom di web enterprise mengalami cacat aksesibilitas: keyboard focus dapat bocor ke elemen latar belakang (*background bleed*), interaksi pembaca layar tetap membaca konten di luar modal, tombol penutup tidak memiliki accessible name yang tepat, dan fokus tidak dikembalikan ke elemen pemicu (*trigger element*) saat modal ditutup. Anda ditugaskan untuk membangun primitif komponen **Modal Dialog** menggunakan JavaScript native dan Semantic HTML/ARIA yang sepenuhnya memenuhi standar **WAI-ARIA 1.2 Authoring Practices Guide (APG)** dan patuh **WCAG 2.2 Level AA**.

#### Requirements
1. **Semantic Structure & Roles:**
   * Elemen modal harus menggunakan role semantik yang tepat (`dialog` atau native `<dialog>`) dengan konfigurasi `aria-modal="true"`.
   * Accessible name modal harus ditautkan secara dinamis ke elemen heading modal via `aria-labelledby`.
   * Accessible description harus ditautkan ke teks pembuka atau deskripsi isi modal via `aria-describedby`.
2. **Strict Focus Trap & Keyboard Navigation:**
   * Saat modal terbuka, fokus harus secara otomatis dipindahkan ke elemen pertama yang dapat difokuskan di dalam modal (atau ke kontainer modal itu sendiri jika tidak ada elemen interaktif).
   * Menekan tombol `Tab` pada elemen interaktif terakhir di dalam modal harus memutar fokus kembali ke elemen interaktif pertama (*wrap around*).
   * Menekan kombinasi tombol `Shift + Tab` pada elemen interaktif pertama harus memutar fokus ke elemen terakhir di dalam modal.
   * Tidak boleh ada celah bagi pengguna keyboard untuk memfokuskan elemen apa pun di luar modal selama modal terbuka. Manfaatkan atribut `inert` pada kontainer sibling luar (misalnya `#app-root`).
3. **Dismissal & Focus Restoration:**
   * Modal harus dapat ditutup dengan menekan tombol `Escape`.
   * Modal harus menyediakan tombol tutup visual eksplisit yang memiliki label aksesibel (misalnya: *“Tutup dialog konfirmasi”*).
   * Ketika modal ditutup (baik via tombol `Escape`, tombol *Close*, maupun klik overlay), fokus keyboard **wajib dikembalikan secara presisi** ke elemen pemicu (*trigger element*) yang membukanya.
4. **Scrolling & Accessibility Tree Sanitization:**
   * Gulir layar latar belakang (`body scroll`) harus dinonaktifkan tanpa menyebabkan layout shift (*scrollbar jitter*).
   * Konten di luar modal harus disembunyikan dari Accessibility Tree (baik melalui atribut `inert` atau polyfill `aria-hidden="true"` pada seluruh root sibling).

#### Constraints
* Tidak boleh menggunakan pustaka eksternal (murni HTML5, CSS modern, dan Vanilla ES6+).
* Komponen harus ditulis dalam bentuk class atau factory function yang *reusable* (`class AccessibleModal { ... }`).
* Harus menangani situasi di mana modal tidak memiliki elemen interaktif sama sekali di dalam kontennya.
* Tidak boleh terjadi *memory leak* dari keyboard event listener yang tertinggal saat modal dihancurkan (*destroy*).

#### Expected Output
1. File markup HTML lengkap yang merepresentasikan struktur dokumen (konten aplikasi utama, tombol pemicu, dan markup modal).
2. Kode CSS minimal untuk menangani visibilitas dan kalkulasi scroll-lock/overlay.
3. Kode JavaScript Vanilla kelas produksi dengan implementasi penanganan event (`keydown`, fokus trapping, penyimpanan referensi `activeElement`, dan pembersihan event listener).

---

## 5. Knowledge Check & Checklist

Verifikasi pemahaman teknis Anda terhadap materi bab ini dengan mengisi checklist berikut:

### Saya harus memahami:
- [ ] Perbedaan fundamental antara DOM Tree, CSSOM, dan Accessibility Object Model (AOM) pada browser engine.
- [ ] Aturan prioritas pemrosesan algoritma *Accessible Name and Description Computation (AccName 1.2)*.
- [ ] Formula kalkulasi luminansi relatif dan kriteria kepatuhan rasio kontras warna WCAG 2.1/2.2 untuk teks maupun antarmuka non-teks.
- [ ] Cara kerja pembaca layar (screen reader) dalam memanfaatkan Accessibility API sistem operasi (MSAA, IAccessible2, UIA, NSAccessibility, ATK).
- [ ] Kapan WAI-ARIA mutlak dibutuhkan dan kapan penambahan ARIA justru menjadi anti-pattern (*Bad ARIA*).
- [ ] Arsitektur dan siklus transmisi data pada `aria-live` regions (`polite` vs `assertive`).
- [ ] Perbedaan fungsional antara atribut isolasi native `inert` dan atribut semantik `aria-modal="true"`.

### Saya tidak perlu menghafal:
- [ ] Seluruh tabel kode heksadesimal nilai warna kontras secara manual (gunakan tooling kalkulator luminansi terstandarisasi).
- [ ] Ratusan mapping internal role ARIA spesifik platform OS (cukup pahami abstraksi W3C WAI-ARIA role).
- [ ] Seluruh shortcut keyboard pembaca layar (NVDA, JAWS, VoiceOver, Orca) di luar shortcut navigasi virtual cursor dasar dan rotor.

### Saya harus bisa melakukan:
- [ ] Melakukan audit aksesibilitas manual menggunakan keyboard secara eksklusif (tanpa mouse) untuk mendeteksi *keyboard traps* dan *focus loss*.
- [ ] Menggunakan Chrome/Edge DevTools Accessibility Pane untuk menginspeksi Accessibility Tree, computed properties, dan accessible name derivation.
- [ ] Mengoperasikan screen reader desktop (NVDA pada Windows atau VoiceOver pada macOS) untuk menguji alur pengguna kritis (*critical user flows*).
- [ ] Mengimplementasikan *Focus Trap* yang anti-bocor (*bulletproof*) menggunakan Vanilla JavaScript dan atribut `inert`.
- [ ] Menulis form dengan arsitektur validasi error dinamis yang terhubung penuh ke Assistive Technology via `aria-invalid`, `aria-describedby`, dan live regions.
- [ ] Menyeimbangkan dynamic SPA client-side routing dengan sistem fokus dan *accessible announcement* yang bebas dari race condition.