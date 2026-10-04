# BAB 02: Quiz, Challenge, & Knowledge Check
**Semantik HTML5, Aksesibilitas (a11y) & Struktur Data DOM**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Node vs. Element dalam DOM Tree
Jelaskan perbedaan struktural dan representasi memori antara antarmuka `Node` dan `Element` pada Document Object Model (DOM). Mengapa `NodeList` yang dihasilkan oleh `childNodes` bersifat *live* pada kasus tertentu sedangkan `querySelectorAll` menghasilkan *static* `NodeList`? Jelaskan dampaknya terhadap performa traversing.

### Soal 1.2: Accessible Name and Description Computation
Dalam algoritma Accessible Name and Description Computation (W3C), bagaimana browser mengkalkulasi nama terakses (*accessible name*) untuk sebuah elemen interaktif? Urutkan prioritas resolusi antara teks konten natif, atribut `alt`, atribut `title`, `aria-label`, dan `aria-labelledby`. Berikan kasus di mana penggunaan `aria-label` justru merusak navigasi pengguna *speech-input*.

### Soal 1.3: HTML5 Content Model & Semantic Outlining
Jelaskan perbedaan fungsional antara elemen `<article>`, `<section>`, dan `<div>` ditinjau dari *Accessibility Tree* (bukan tampilan visual). Mengapa HTML5 Document Outline Algorithm (yang semula dirancang untuk mengizinkan multiple `<h1>` per dokumen yang di-scope oleh section) dianggap gagal dan ditinggalkan oleh implementasi browser serta pembaca layar (*screen reader*) modern?

### Soal 1.4: First Rule of ARIA Use & Implisit Semantics
Jelaskan implikasi teknis dari aturan fundamental W3C: *"If you can use a native HTML element or attribute with the semantics and behavior you require already built-in, then do so."* Apa saja fungsionalitas *state machine*, integrasi *accessibility API* sistem operasi, dan *keyboard event handling* implisit yang hilang ketika developer mengganti `<button>` dengan `<div role="button" tabindex="0">`?

### Soal 1.5: Atribut Boolean HTML vs. Atribut String ARIA
Bandingkan penanganan evaluasi logika antara atribut boolean natif (contoh: `disabled`, `required`, `hidden`) dengan atribut status ARIA (contoh: `aria-disabled="false"`, `aria-hidden="true"`). Mengapa keberadaan atribut `aria-disabled="false"` pada DOM node sering kali menimbulkan bug logika jika diproses menggunakan pengecekan boolean JavaScript konvensional atau *attribute selectors* CSS?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: DOM Tree Construction & HTML Parser Tokenization
Bagaimana parsing engine browser (seperti Blink atau WebKit) menangani sintaks *self-closing* non-standar pada elemen non-void, misalnya penulisan `<div class="card" />`? Jelaskan bagaimana mekanisme *tree construction dispatch* menginterpretasikan tag tersebut dan mengapa hal ini dapat memicu *DOM corruption* serta kesalahan nesting (*foster parenting*) pada elemen-elemen di bawahnya.

### Soal 2.2: Focus Order, Tabindex Traps, dan DOM Order Disconnection
Jelaskan bahaya arsitektural penggunaan nilai integer positif pada atribut `tabindex` (misal: `tabindex="3"`). Bagaimana ketidaksesuaian antara urutan visual (*CSS flexbox/grid order*) dan urutan dokumen (*source order*) merusak navigasi keyboard? Bagaimana Anda mendeteksi dan menyelesaikan disparitas ini menggunakan DevTools tanpa memodifikasi tata letak visual?

### Soal 2.3: Mekanisme ARIA Live Regions & Screen Reader Announcement Queue
Jelaskan perbedaan siklus eksekusi internal antara `aria-live="polite"` dan `aria-live="assertive"`. Mengapa penulisan konten dinamis yang langsung dimasukkan bersamaan dengan deklarasi elemen kontainer (misalnya menginjeksi elemen `<div aria-live="polite">Notifikasi</div>` sekaligus ke dalam DOM) sering kali gagal dibacakan oleh *screen reader*? Bagaimana arsitektur injeksi DOM yang benar untuk menangani keterbatasan ini?

### Soal 2.4: Cross-Root ARIA References & Shadow DOM Encapsulation
Atribut relasional ARIA seperti `aria-labelledby` dan `aria-describedby` menggunakan referensi `IDREF`. Jelaskan mengapa integrasi komponen Web Components berbasis Shadow DOM sering memutus fungsionalitas aksesibilitas saat elemen input berada di dalam *light DOM* sedangkan elemen label berada di dalam *shadow root* (atau sebaliknya). Solusi standar modern apa yang disediakan oleh platform web untuk mengatasi batasan ini?

### Soal 2.5: Inertness Subtree & State Synchronization
Bagaimana atribut HTML global `inert` memanipulasi pemrosesan event, fokus navigasi, dan penghitungan *accessibility tree* pada suatu *subtree* DOM? Bandingkan performa dan kompleksitas implementasi `inert` dengan metode manual lama yang menggunakan kombinasi `tabindex="-1"`, `aria-hidden="true"`, dan `pointer-events: none` pada seluruh node turunan secara rekursif.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Audit Kegagalan A11y pada Modul Checkout Skala Besar
Sebuah platform perbankan multinasional menerima ancaman litigasi akibat pelanggaran WCAG 2.1 Level AA pada halaman checkout. Investigasi awal menemukan:
1. Tombol checkout diimplementasikan sebagai `<a href="javascript:void(0)" class="btn">Bayar</a>`.
2. Saat saldo tidak mencukupi, sistem menampilkan teks kesalahan berwarna merah `#FF0000` di samping label tanpa teks penjelas eksplisit maupun asosiasi programmatic.
3. Modal dialog konfirmasi PIN diinjeksikan secara asinkron; saat modal terbuka, pengguna keyboard masih dapat menekan tombol `Tab` dan memindahkan fokus ke elemen-elemen di halaman latar belakang (*background leakage*).

**Tugas Diagnostik:**
*   Identifikasi kriteria sukses WCAG (SC) spesifik yang dilanggar oleh ketiga temuan di atas.
*   Rancang rekayasa balik (*remediation plan*) struktural pada level kode HTML dan interaksi DOM untuk memperbaiki setiap masalah secara deterministik.

### Skenario B: DOM Bloat & Dynamic Feed Memory Leak
Aplikasi *real-time sports monitoring* merender pembaruan skor live ke dalam sebuah `<ul>` setiap 500 milidetik melalui WebSocket. Setiap baris item diinstansiasi dengan format:
```html
<li class="match-item" role="status" aria-live="polite">
  <span class="team">Tim A</span> vs <span class="team">Tim B</span>
  <span class="score">1 - 0</span>
</li>
```
Setelah berjalan selama 15 menit, browser klien mengalami *high memory footprint*, respons thread utama melambat secara drastis, dan perangkat lunak pembaca layar (*screen reader*) pengguna mengalami *buffer freeze* atau macet total (*crash*).

**Tugas Diagnostik:**
*   Jelaskan akar penyebab (*root cause*) kegagalan sistem ini dari perspektif sinkronisasi Accessibility Tree dan siklus hidup node DOM.
*   Bagaimana Anda mendesain ulang arsitektur DOM untuk dynamic feed ini agar tetap *real-time*, hemat memori, dan tidak membebani buffer speech synthesizer pembaca layar?

### Skenario C: Custom Headless Dropdown vs. Native Form Semantics
Sebuah tim frontend memutuskan untuk tidak menggunakan elemen `<select>` natif dan membangun komponen multiselect custom menggunakan elemen `<div>` dan `<span>` dengan argumen "desain UI kustom yang tidak didukung browser". Pada tahap pengujian integrasi form submit otomatis dan autofill password manager, data dari custom dropdown tersebut hilang (*empty payload*) dan pengujian navigasi keyboard menunjukkan kegagalan total: tombol *Up/Down Arrow*, *Home*, *End*, serta pengetikan pencarian langsung (*type-ahead search*) tidak berfungsi.

**Tugas Diagnostik:**
*   Evaluasi trade-off arsitektural: Kapan custom dropdown benar-benar dibutuhkan, dan bagaimana cara mempertahankan integrasi standar `<form>` jika elemen non-form digunakan?
*   Spesifikasikan *state machine*, event listeners (`keydown`), dan atribut WAI-ARIA Design Pattern (`role="listbox"`, `role="option"`, `aria-activedescendant`) minimal yang wajib dibangun dari nol untuk membuat komponen tersebut mencapai paritas fungsional dengan elemen kontrol formulir natif.

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Primitif Accessible Modal Dialog (Zero-Dependency)

#### Problem Statement
Modal dialog adalah salah satu komponen UI paling sering disalahpahami dalam frontend development. Mayoritas implementasi gagal mengisolasi fokus keyboard, gagal menangani restorasi fokus saat ditutup, tidak memberikan semantik yang tepat ke teknologi asistif, dan memicu *scroll-bleed* pada dokumen utama. Anda diminta untuk mengimplementasikan komponen **Accessible Modal Dialog Primitif** murni menggunakan Web APIs natif tanpa library pihak ketiga.

#### Requirements
1. **Markup Semantik & A11y Attributes:**
   * Menggunakan elemen `<dialog>` HTML5 natif ATAU elemen container dengan `role="dialog"` (atau `role="alertdialog"`).
   * Elemen wajib memiliki penamaan terakses via `aria-labelledby` yang merujuk pada judul modal dan `aria-describedby` untuk deskripsi konten.
   * Properti `aria-modal="true"` harus diaktifkan secara dinamis saat modal terbuka.
2. **Focus Management & Keyboard Trapping:**
   * Saat modal terbuka, simpan referensi elemen yang sebelumnya memegang fokus (*trigger element*).
   * Pindahkan fokus secara otomatis ke elemen interaktif pertama di dalam modal, atau ke kontainer modal itu sendiri jika tidak ada elemen interaktif.
   * Terapkan *focus trap*: Menekan tombol `Tab` pada elemen interaktif terakhir di dalam modal harus memutar fokus kembali ke elemen interaktif pertama. Sebaliknya, menekan `Shift + Tab` pada elemen interaktif pertama harus memindahkan fokus ke elemen interaktif terakhir.
   * Menekan tombol `Escape` harus menutup modal.
3. **Background Isolation:**
   * Saat modal aktif, interaksi dengan elemen di luar modal harus dinonaktifkan total (gunakan API atribut `inert` pada node saudara/sibling di root dokumen).
   * Cegah scrolling pada elemen `<body>` latar belakang tanpa menyebabkan *layout shift* (hilangnya scrollbar width).
4. **Restorasi Fokus:**
   * Saat modal ditutup (baik via tombol close, tombol Escape, maupun klik pada area backdrop), fokus navigasi wajib dikembalikan secara presisi ke elemen *trigger* yang membukanya.

#### Constraints
* **Vanilla JavaScript Only:** Tidak diperbolehkan menggunakan framework (React/Vue/Angular) atau library utilitas (Focus-trap, jQuery, dll.).
* **Standard-Compliant:** Wajib lolos validator axe-core / Lighthouse Accessibility dengan skor 100/100.
* **Separation of Concerns:** Struktur kode harus memisahkan layer Presentasi (CSS), Struktur (HTML), dan Logika/State Machine (JS).

#### Expected Output
Sediakan file artefak tunggal atau terpisah yang mencakup:
1. `index.html`: Struktur semantik modal dan trigger button.
2. `styles.css`: Styling minimal untuk backdrop overlay, modal container, dan mitigasi layout shift.
3. `modal.js`: Class atau modul JavaScript mandiri yang mengelola siklus hidup modal (`open()`, `close()`, trapping logic, cleanup event listeners).

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk memvalidasi kesiapan teknis Anda sebelum melangkah ke topik berikutnya.

### Saya harus memahami:
- [ ] Perbedaan fundamental antara DOM Tree, CSSOM Tree, Render Tree, dan Accessibility Tree (AOM).
- [ ] Cara browser mengevaluasi Accessible Name Computation dan urutan presedensinya.
- [ ] Aturan emas WAI-ARIA (The 5 Rules of ARIA) dan dampak degradasi aksesibilitas akibat over-using ARIA.
- [ ] Mengapa navigasi keyboard (`focus`, `tabindex`, keyboard events) harus dirancang sinkron dengan representasi visual.
- [ ] Peran elemen landmark (`<main>`, `<nav>`, `<header>`, `<footer>`, `<aside>`) dalam navigasi screen reader.

### Saya tidak perlu menghafal:
- [ ] Seluruh tabel kode heksadesimal untuk entitas karakter HTML.
- [ ] Setiap properti interface Web IDL dari spesifikasi W3C DOM Core (cukup pahami cara membaca dokumentasi MDN).
- [ ] Seluruh atribut WAI-ARIA yang jarang digunakan; fokuslah pada pemahaman pola interaksi inti (*Widget Roles*, *Live Regions*, dan *Relationship Attributes*).

### Saya harus bisa melakukan:
- [ ] Menavigasi dan mengoperasikan web app secara menyeluruh hanya menggunakan keyboard (`Tab`, `Shift+Tab`, `Enter`, `Space`, `Arrow Keys`, `Escape`).
- [ ] Mengaudit struktur semantik dan skor a11y menggunakan Chrome DevTools (Accessibility Tree panel, Lighthouse, axe-core).
- [ ] Memperbaiki masalah *color contrast* dan missing programmatic labels pada elemen input/button.
- [ ] Mengimplementasikan *focus trap* dan *focus restoration* secara deterministik pada dynamic components (modal, drawer, dropdown).
- [ ] Menggunakan atribut `inert` untuk mengisolasi background node secara performan.