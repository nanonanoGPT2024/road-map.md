# BAB-08-Aksesibilitas-Digital-dan-Desain-Inklusif-Lanjutan: Quiz, Challenge, & Knowledge Check

Dokumen evaluasi ini dirancang untuk menguji penguasaan konseptual, arsitektural, dan implementasi praktis terkait **Aksesibilitas Digital (a11y)** tingkat lanjut dan **Desain Inklusif** sesuai standar global **WCAG 2.1 / 2.2 (Web Content Accessibility Guidelines)**, WAI-ARIA 1.2, serta integrasi teknologi asistif (*assistive technologies*) pada aplikasi web dan mobile modern.

---

## Bagian 1: Basic Questions (5 Soal Pilihan Ganda & Konsep Fundamental)

### Soal 1: Prinsip Rasio Kontras dan Hierarchy Warna (WCAG SC 1.4.3 & 1.4.11)
Dalam audit kepatuhan WCAG 2.1 Level AA pada sebuah dashboard analitik SaaS, Anda menemukan teks deskriptif dengan ukuran font 14px reguler (*normal text*) yang dipasang di atas latar belakang `#FFFFFF`. Manakah pernyataan berikut yang paling tepat mengenai persyaratan rasio kontras minimum yang harus dipenuhi?

- **A.** Rasio kontras minimum adalah 3:1 untuk teks normal dan 4.5:1 untuk komponen antarmuka grafis.
- **B.** Rasio kontras minimum adalah 4.5:1 untuk teks berukuran normal, sedangkan untuk *large text* (minimal 18pt reguler atau 14pt tebal/bold) ambang batasnya adalah 3:1.
- **C.** Semua teks tanpa terkecuali harus mencapai rasio kontras 7:1 di Level AA.
- **D.** Rasio kontras 3:1 cukup untuk semua teks asalkan memiliki bobot *font-weight* di atas 400.

> **Kunci Jawaban: B**  
> **Pembahasan Teknis:** Berdasarkan WCAG 2.1 Success Criterion 1.4.3 (Contrast Minimum - Level AA), teks biasa (*normal text*) wajib memiliki rasio kontras luminansi minimal **4.5:1** terhadap latar belakangnya. Untuk *large text* (didefinisikan sebagai minimal 18pt/24px atau 14pt/18.66px bold/tebal), rasio kontras minimum yang diwajibkan adalah **3:1**. Level AAA mensyaratkan 7:1 untuk teks normal dan 4.5:1 untuk teks besar (SC 1.4.6). Sedangkan SC 1.4.11 mengatur kontras non-teks (komponen UI dan grafis esensial) minimal 3:1.

---

### Soal 2: Filosofi Semantic HTML vs Penggunaan WAI-ARIA
Seorang frontend engineer menambahkan atribut `role="button"` dan event handler `onClick` pada elemen `<div>` custom:
```html
<div role="button" onClick="submitPayment()">Bayar Sekarang</div>
```
Evaluator a11y menandai komponen ini sebagai pelanggaran berat aksesibilitas. Mengapa pendekatan ini bermasalah dibandingkan menggunakan elemen `<button>` native, sesuai aturan *First Rule of ARIA use*?

- **A.** Elemen `<div>` tidak mendukung atribut `role` dalam spesifikasi HTML5 modern.
- **B.** Elemen native `<button>` secara otomatis menyediakan navigabilitas keyboard (`Tab` focusable), dukungan aktivasi tombol (`Enter` dan `Spacebar`), serta eksposur *Role, Name, State* native pada *Accessibility Tree* tanpa scripting tambahan.
- **C.** Penggunaan atribut `role="button"` akan secara otomatis memblokir browser dari merender styling CSS flexbox.
- **D.** WAI-ARIA tidak boleh digunakan sama sekali pada komponen transaksi e-commerce.

> **Kunci Jawaban: B**  
> **Pembahasan Teknis:** *First Rule of ARIA* dari W3C menyatakan: *"If you can use a native HTML element or attribute with the semantics and behavior you require already built in, then do so instead of re-purposing an element and adding an ARIA role, state or property to make it accessible."* Penggunaan `<div>` dengan `role="button"` menuntut pengembang mengimplementasikan `tabindex="0"`, event handler `keydown` untuk tombol `Enter` dan `Space`, manajemen pseudo-state `:focus-visible`, dan pengelolaan state disabled secara manual yang rentan bug.

---

### Soal 3: Manajemen Focus Order dan Manipulasi Tabindex
Perhatikan cuplikan markup berikut:
```html
<header>
  <a href="/logo" tabindex="2">Beranda</a>
  <input type="search" placeholder="Cari..." tabindex="1">
</header>
<main>
  <button tabindex="0">Aksi Utama</button>
  <div id="modal-target" tabindex="-1">Fokus Pemindahan Dinamis</div>
</main>
```
Berdasarkan spesifikasi DOM dan standar keyboard navigation WCAG SC 2.4.3 (Focus Order), manakah praktik yang dianggap *anti-pattern* dan harus dihindari?

- **A.** Menggunakan `tabindex="0"` pada elemen button yang sudah focusable secara native.
- **B.** Menggunakan nilai integer positif (`tabindex="1"`, `tabindex="2"`).
- **C.** Menggunakan `tabindex="-1"` untuk target fokus programatis JavaScript.
- **D.** Menempatkan elemen input di dalam container `<header>`.

> **Kunci Jawaban: B**  
> **Pembahasan Teknis:** Penggunaan nilai positif pada `tabindex` (`tabindex > 0`) merusak alur fokus alami DOM (*natural DOM order*). Browser akan memprioritaskan seluruh elemen dengan tabindex positif secara berurutan sebelum beralih ke elemen dengan urutan natural (`tabindex="0"` atau native focusable). Hal ini menyebabkan pengalaman navigasi keyboard yang membingungkan dan tidak terprediksi. Nilai yang diperbolehkan dalam arsitektur modern adalah `0` (memasukkan elemen non-interaktif ke dalam alur tab normal) dan `-1` (membuat elemen dapat difokuskan melalui `element.focus()` via script tanpa masuk ke urutan tombol Tab).

---

### Soal 4: Penerapan Alternative Text pada Gambar Informatif vs Dekoratif (WCAG SC 1.1.1)
Sebuah halaman artikel menampilkan ikon ilustrasi dekoratif di samping judul bab dan diagram alur transaksi perbankan yang krusial. Bagaimana penerapan atribut `alt` yang benar pada kedua elemen `<img>` tersebut?

- **A.** Keduanya wajib diberi atribut `alt` lengkap dan panjang agar pembaca layar mendapatkan semua informasi visual.
- **B.** Ikon dekoratif menggunakan `alt=""` (atau `aria-hidden="true"`), sedangkan diagram alur diberikan deskripsi singkat pada `alt` dan deskripsi komprehensif tertaut melalui `aria-describedby` atau teks kontekstual.
- **C.** Ikon dekoratif tidak perlu diberi atribut `alt` sama sekali (`<img>` tanpa atribut `alt`), sedangkan diagram alur cukup menggunakan nama file gambar.
- **D.** Atribut `alt` dihilangkan dan diganti sepenuhnya dengan atribut `title`.

> **Kunci Jawaban: B**  
> **Pembahasan Teknis:** Gambar dekoratif yang tidak menyampaikan informasi esensial wajib menyertakan atribut `alt=""` (*null alt text*) agar diabaikan oleh screen reader. Menghilangkan atribut `alt` sama sekali adalah kesalahan fatal karena screen reader akan membaca path file gambar (misal: `/assets/images/deco-01.png`). Untuk infografis atau diagram alur kompleks, `alt` ringkas berfungsi sebagai label identifikasi, dan rincian lengkapnya disediakan via struktur tabel/teks naratif yang direferensikan via `aria-describedby`.

---

### Soal 5: Target Sentuh Minimum dan Pointer Gestures (WCAG 2.2 SC 2.5.8 & SC 2.5.5)
Pada aplikasi web mobile responsive, desainer menempatkan serangkaian ikon interaktif (Edit, Delete, Duplicate) yang berdekatan. Berapakah ukuran minimum target interaktif (*Target Size*) yang disyaratkan WCAG 2.2 Level AA (SC 2.5.8 Target Size - Minimum)?

- **A.** Minimal 12x12 CSS pixels tanpa jarak batas *offset*.
- **B.** Minimal 24x24 CSS pixels, atau jika lebih kecil, memiliki jarak (*spacing*) yang cukup sehingga lingkaran diameter 24px di tengah target tidak tumpang tindih dengan target lain.
- **C.** Minimal 48x48 CSS pixels wajib pada semua breakpoint desktop maupun mobile.
- **D.** Tidak ada batasan ukuran target untuk perangkat sentuh jika sudah ada zoom manual di browser.

> **Kunci Jawaban: B**  
> **Pembahasan Teknis:** Pada WCAG 2.2, Success Criterion 2.5.8 (Target Size - Minimum, Level AA) menetapkan target sentuh minimal sebesar **24x24 CSS pixels** atau memiliki *undersized target spacing* yang memastikan jarak lingkar target tidak bersinggungan. Sementara itu, SC 2.5.5 (Level AAA) merekomendasikan target ideal berukuran **44x44 CSS pixels** (sejalan dengan Human Interface Guidelines Apple dan Material Design Android yang merekomendasikan 48x48 dp).

---

## Bagian 2: Intermediate Questions (5 Soal Analisis Teknis & Arsitektur a11y)

### Soal 6: Mekanisme WAI-ARIA Live Regions pada Dynamic SPA Updates
Sebuah aplikasi Single Page Application (SPA) memuat feed transaksi secara asynchronous melalui WebSockets. Pengembang ingin memastikan pengguna screen reader diberi tahu setiap kali saldo rekening diperbarui tanpa menginterupsi pembacaan kalimat yang sedang berlangsung. Konfigurasi ARIA Live Region manakah yang tepat?

- **A.** `<div role="alert" aria-live="assertive">Saldo: Rp 5.000.000</div>`
- **B.** `<div aria-live="polite" aria-atomic="true">Saldo Baru: Rp 5.000.000</div>`
- **C.** `<div aria-live="off" aria-relevant="all">Saldo: Rp 5.000.000</div>`
- **D.** `<div role="status" aria-live="assertive" aria-busy="true">Saldo: Rp 5.000.000</div>`

> **Kunci Jawaban: B**  
> **Pembahasan Teknis:** Atribut `aria-live="polite"` menginstruksikan teknologi asistif untuk mengumumkan pembaruan konten setelah tugas atau pembacaan suara saat ini selesai (tidak memotong suara secara mendadak). Properti `aria-atomic="true"` menjamin bahwa seluruh isi region dibacakan secara utuh, bukan hanya karakter yang mengalami mutasi parsial. Nilai `"assertive"` hanya boleh digunakan untuk pesan kritis/darurat (seperti sesi kedaluwarsa atau error validasi penghalang transaksi) karena langsung memotong pembacaan screen reader seketika.

---

### Soal 7: Arsitektur Keyboard Trap & Modal Dialog Pattern (WAI-ARIA APG)
Saat mendesain komponen Modal Dialog Interaktif yang dapat diakses penuh, urutan eksekusi manakah yang wajib dipenuhi oleh siklus hidup (*lifecycle*) komponen saat dibuka dan ditutup?

- **A.** Menyimpan referensi elemen yang memicu modal (*trigger element*) -> Membuka modal -> Memindahkan fokus ke elemen interaktif pertama di dalam modal -> Mengunci alur Tab di dalam batas modal (*focus trapping*) -> Menutup modal saat tombol `Escape` ditekan -> Mengembalikan fokus ke *trigger element*.
- **B.** Membuka modal -> Membiarkan urutan fokus Tab mengalir keluar ke elemen background di halaman utama -> Menutup modal hanya via klik backdrop overlay.
- **C.** Menambahkan atribut `autofocus` pada semua input modal tanpa menyediakan mekanisme penutupan via tombol keyboard `Escape`.
- **D.** Menggunakan `display: none` pada seluruh halaman latar belakang saat modal aktif dan menghapus history browser.

> **Kunci Jawaban: A**  
> **Pembahasan Teknis:** Berdasarkan WAI-ARIA Authoring Practices Guide (APG) untuk Dialog (Modal):
> 1. Fokus harus diarahkan ke dalam modal (baik elemen fokus pertama atau heading modal).
> 2. Latar belakang harus dibuat *inert* (`aria-hidden="true"` pada container background atau menggunakan atribut HTML5 modern `inert`).
> 3. Alur keyboard Tab dan Shift+Tab wajib terkunci di dalam modal (*focus trap*).
> 4. Tombol `Escape` harus menutup modal.
> 5. Saat modal tertutup, fokus browser wajib dikembalikan ke elemen pemicu (*trigger element*) agar pengguna keyboard tidak terlempar ke awal dokumen (`<body>`).

---

### Soal 8: Validasi Form Aksesibel dan Relasi Error State
Diberikan input registrasi email yang mengalami kegagalan validasi format. Struktur markup manakah yang secara semantik memberikan asosiasi paling lengkap bagi screen reader saat input menerima fokus?

- **A.**
  ```html
  <label for="email">Alamat Email</label>
  <input type="text" id="email" class="border-red-500">
  <span style="color: red;">Email tidak valid!</span>
  ```
- **B.**
  ```html
  <label for="email">Alamat Email</label>
  <input type="email" id="email" aria-invalid="true" aria-describedby="email-error email-hint">
  <p id="email-hint">Gunakan email korporat Anda.</p>
  <p id="email-error" role="alert">Format email salah. Contoh: user@company.com</p>
  ```
- **C.**
  ```html
  <p>Alamat Email</p>
  <input type="email" placeholder="Email salah!" aria-label="Error">
  ```
- **D.**
  ```html
  <label for="email">Alamat Email</label>
  <input type="email" id="email" title="Format email salah">
  ```

> **Kunci Jawaban: B**  
> **Pembahasan Teknis:** Opsi B memenuhi standar emas validasi formulir:
> 1. Menggunakan pasangan eksplisit `<label for="email">` dan `id="email"`.
> 2. `aria-invalid="true"` memberi tahu teknologi asistif bahwa data dalam field ini saat ini dalam kondisi gagal validasi.
> 3. `aria-describedby="email-error email-hint"` mengaitkan field input dengan teks panduan sekaligus pesan error secara terprogram, sehingga saat kursor fokus masuk, screen reader akan membacakan nama label, nilai input, status invalid, dan seluruh deskripsi pendukung secara otomatis.
> 4. Pesan error diberi `role="alert"` untuk pemberitahuan live saat error terpicu.

---

### Soal 9: Aksesibilitas Visualisasi Data Kompleks (SVG Charts)
Sebuah dashboard keuangan menyajikan grafik batang performa portofolio investasi tahunan menggunakan format inline `<svg>`. Bagaimana cara membuat grafik ini sepenuhnya dapat diakses oleh tunanetra dan pengguna keyboard?

- **A.** Cukup menambahkan atribut `alt="Grafik performa investasi"` pada tag `<svg>`.
- **B.** Memberi tag `<svg>` atribut `role="img"` dan `aria-labelledby="chart-title chart-desc"`, menyediakan tag `<title>` dan `<desc>` di dalam SVG, serta menyertakan tabel data HTML native tersembunyi/terlihat (`<table>`) sebagai representasi tabular alternatif.
- **C.** Mengonversi seluruh elemen SVG menjadi format canvas raster base64 agar browser tidak memproses elemen DOM terpisah.
- **D.** Memasang event `onmouseover` pada setiap elemen bar `<rect>` di dalam SVG tanpa dukungan event keyboard.

> **Kunci Jawaban: B**  
> **Pembahasan Teknis:** Tag `<svg>` tidak memiliki atribut `alt`. Untuk menjadikannya aksesibel:
> 1. Berikan `role="img"` pada elemen SVG root.
> 2. Hubungkan SVG dengan elemen teks judul dan deskripsi kontekstual menggunakan `aria-labelledby`.
> 3. Solusi paling inklusif untuk grafik data kuantitatif kompleks adalah menyediakan *Accessible Data Table* (tabel HTML standar dengan `<thead>`, `<th scope="col">`, `<tbody>`) sebagai representasi setara, sehingga pengguna screen reader dapat menjelajahi data angka spesifik per baris dan kolom dengan navigasi tabel shortcut.

---

### Soal 10: Preferensi Sistem Pengguna: Sensitivitas Gerak dan Reduksi Kontras
Banyak pengguna dengan gangguan vestibular (*vestibular disorders*) mengalami pusing, disorientasi, atau mual akibat animasi paralaks dan transisi zoom yang agresif di web. Bagaimana implementasi CSS modern yang benar untuk menghormati preferensi pengguna terkait gerak?

- **A.**
  ```css
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
  ```
- **B.**
  ```css
  @media (max-width: 768px) {
    * { display: none; }
  }
  ```
- **C.**
  ```css
  @media (prefers-color-scheme: dark) {
    .motion-wrapper { opacity: 0; }
  }
  ```
- **D.** Menghapus seluruh animasi dan transisi CSS dari seluruh codebase aplikasi selamanya untuk semua pengguna.

> **Kunci Jawaban: A**  
> **Pembahasan Teknis:** Media query `@media (prefers-reduced-motion: reduce)` mendeteksi apakah pengguna telah mengaktifkan opsi "Reduce Motion" pada pengaturan sistem operasi mereka (macOS, Windows, iOS, Android). Aturan CSS pada opsi A adalah pola standar industri untuk meminimalkan atau menonaktifkan durasi transisi, animasi keyframes, dan smooth scrolling, sehingga mencegah timbulnya gejala gangguan vestibular (WCAG 2.1 SC 2.3.3 Animation from Interactions).

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Real-World Scenarios)

### Skenario 1: Kegagalan Transisi Rute pada Aplikasi Next.js / React SPA
* **Konteks:** Tim QA dan auditor aksesibilitas melaporkan bahwa aplikasi perbankan berbasis Next.js App Router memiliki cacat kritis: saat pengguna tunanetra mengklik tautan navigasi di sidebar (misal dari menu "Ringkasan Akun" ke "Mutasi Transaksi"), visual halaman berubah secara instan, namun pengguna screen reader (NVDA/VoiceOver) tetap diam (*silent*) dan fokus keyboard tertinggal di tombol tautan sidebar yang lama atau terlempar ke `<body>`.
* **Identifikasi Masalah:**
  1. Pada arsitektur SPA/CSR, pergantian rute tidak memicu reload halaman penuh (*full page reload*), sehingga siklus pembacaan halaman tradisional browser tidak terpicu.
  2. Judul dokumen (`<title>`) mungkin berubah, namun perubahan title saja sering kali tidak diumumkan secara proaktif oleh banyak screen reader jika fokus tidak dipindahkan.
  3. Fokus pengguna tidak dipindahkan ke konten utama halaman baru.
* **Solusi Arsitektural & Kode Implementasi:**
  1. Buat komponen rute listener terpusat yang memanfaatkan *Live Region Announcer*.
  2. Pindahkan fokus secara programatis ke container `<main id="main-content" tabindex="-1">` pada setiap penyelesaian transisi rute.
  ```tsx
  // RouteFocusManager.tsx
  import React, { useEffect, useRef } from 'react';
  import { usePathname } from 'next/navigation';

  export const RouteFocusManager: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const pathname = usePathname();
    const mainRef = useRef<HTMLElement>(null);
    const [announcement, setAnnouncement] = React.useState('');

    useEffect(() => {
      // 1. Ambil judul halaman yang baru dirender
      const pageTitle = document.title || 'Halaman baru telah dimuat';
      setAnnouncement(`Navigasi ke ${pageTitle}`);

      // 2. Pindahkan fokus keyboard ke container main tanpa outline visual yang mengganggu mouse
      if (mainRef.current) {
        mainRef.current.focus({ preventScroll: false });
      }
    }, [pathname]);

    return (
      <>
        {/* Live region tak terlihat untuk mengumumkan rute baru */}
        <div 
          role="status" 
          aria-live="polite" 
          aria-atomic="true" 
          className="sr-only"
        >
          {announcement}
        </div>

        {/* Target fokus utama dengan tabindex -1 */}
        <main id="main-content" ref={mainRef} tabIndex={-1} className="focus:outline-none">
          {children}
        </main>
      </>
    );
  };
  ```

---

### Skenario 2: Custom Multi-Select Dropdown Combobox yang Tidak Aksesibel
* **Konteks:** Perusahaan fintech membuat filter kategori saham kustom menggunakan `<div>` dan `<span>` dengan animasi cantik. Namun dalam audit kepatuhan, komponen ini gagal total:
  - Pengguna screen reader hanya mendengar "Unlabeled group".
  - Pengguna keyboard tidak bisa membuka menu dropdown menggunakan tombol panah (`Arrow Down`/`Arrow Up`).
  - Saat opsi dipilih, tidak ada konfirmasi suara mengenai berapa opsi yang sedang terpilih.
* **Identifikasi Masalah:**
  - Ketiadaan *WAI-ARIA 1.2 Combobox Pattern*.
  - Tidak adanya atribut `aria-expanded`, `aria-haspopup="listbox"`, `role="listbox"`, dan `role="option"`.
  - Tidak mengimplementasikan *Active Descendant Virtual Focus* (`aria-activedescendant`).
* **Solusi Perbaikan:**
  Implementasikan markup dan event navigation keyboard sesuai spesifikasi WAI-ARIA APG Combobox:
  ```html
  <!-- Container Combobox -->
  <div class="combobox-wrapper">
    <label id="combo-label" for="combo-input">Kategori Sektor Industri</label>
    <div class="input-wrapper">
      <input 
        id="combo-input"
        type="text" 
        role="combobox"
        aria-autocomplete="list"
        aria-expanded="false"
        aria-haspopup="listbox"
        aria-controls="combo-listbox"
        aria-labelledby="combo-label"
        aria-activedescendant=""
      />
      <button 
        id="combo-toggle" 
        tabindex="-1" 
        aria-label="Tampilkan opsi sektor"
        aria-expanded="false">▼</button>
    </div>

    <!-- Dropdown Listbox -->
    <ul 
      id="combo-listbox" 
      role="listbox" 
      aria-labelledby="combo-label" 
      aria-multiselectable="true" 
      tabindex="-1"
      class="hidden"
    >
      <li id="opt-1" role="option" aria-selected="false">Teknologi Informasi</li>
      <li id="opt-2" role="option" aria-selected="true">Perbankan & Finansial</li>
      <li id="opt-3" role="option" aria-selected="false">Kesehatan & Farmasi</li>
    </ul>
  </div>
  ```
  *Event Logic yang wajib ditambahkan di script:*
  1. Tombol `ArrowDown` dan `ArrowUp` mengubah nilai `aria-activedescendant="opt-X"` pada input dan menggeser visual highlight tanpa memindahkan fokus fisik DOM.
  2. Tombol `Space` atau `Enter` mengubah `aria-selected="true/false"`.
  3. Tombol `Escape` menutup listbox dan mengembalikan state `aria-expanded="false"`.

---

### Skenario 3: Infinite Scroll Feed vs Skip Link dan Footer Trap
* **Konteks:** Portal berita menerapkan *Infinite Scroll* pada halaman depan. Saat pengguna menekan tombol Tab secara berulang-ulang untuk mencapai bagian footer (yang memuat informasi hak cipta, kebijakan privasi, kontak darurat, dan disclaimer regulasi hukum), aplikasi secara otomatis mengambil 20 artikel baru setiap kali kursor mendekati bawah. Akibatnya, pengguna keyboard mengalami *infinite navigation trap* dan tidak pernah dapat menyentuh footer.
* **Analisis Akar Masalah:**
  - Melanggar WCAG 2.1 SC 2.1.2 (No Keyboard Trap) dan SC 2.4.1 (Bypass Blocks).
  - Mekanisme loading otomatis yang dipicu oleh posisi scroll/fokus keyboard menghancurkan navigabilitas struktur akhir halaman.
* **Solusi Rekayasa Aksesibilitas:**
  1. **Transisi ke Tombol "Muat Lebih Banyak" Eksplisit (*Load More Button*):** Ganti infinite auto-trigger dengan tombol interaktif eksplisit. Ini memberi pengguna keyboard kendali penuh apakah ingin memuat konten tambahan atau melompati feed menuju footer.
  2. **Implementasi Skip Links & Landmark Navigation:**
     ```html
     <!-- Di bagian paling atas halaman sebelum nav -->
     <a href="#footer-content" class="skip-link">
       Langsung ke informasi footer dan kontak
     </a>
     ```
     CSS untuk skip-link:
     ```css
     .skip-link {
       position: absolute;
       top: -999px;
       left: 10px;
       background: #000;
       color: #fff;
       padding: 8px 16px;
       z-index: 9999;
     }
     .skip-link:focus {
       top: 10px;
     }
     ```
  3. Jika infinite scroll tetap dipertahankan untuk pointer mouse: Matikan trigger otomatis saat terdeteksi navigasi keyboard (`:focus-visible` aktif di dalam feed item), dan sajikan tombol manual khusus saat pengguna keyboard mencapai akhir batch artikel.

---

## Bagian 4: Practical Chapter Challenge

### Judul Tantangan
**Refactoring Audit & Implementasi High-End Accessible Component: Interactive Alert Modal Dialog dengan Focus Trapping Mandiri**

### Deskripsi Tugas
Anda ditugaskan merombak komponen dialog konfirmasi penghapusan data krusial ("Hapus Rekening Tabungan") yang saat ini dibangun menggunakan tag `<div>` biasa dengan styling bootstrap lama. Komponen baru harus dibangun dari awal menggunakan Semantic HTML5, WAI-ARIA 1.2 Modal Pattern, CSS modern dengan dukungan *prefers-reduced-motion* dan *high-contrast mode*, serta JavaScript murni (*vanilla*) untuk mengontrol alur fokus secara presisi.

### Spesifikasi Kebutuhan Teknis (Acceptance Criteria)
1. **Atribut Semantik & Hubungan ARIA:**
   - Container dialog menggunakan `role="dialog"` atau `role="alertdialog"`.
   - Wajib memiliki atribut `aria-modal="true"`.
   - Judul modal dikaitkan menggunakan `aria-labelledby`.
   - Pesan konfirmasi/peringatan bahaya dikaitkan menggunakan `aria-describedby`.
2. **Manajemen Keyboard & Focus Trap:**
   - Saat modal dibuka via tombol pemicu (*trigger button*), simpan elemen pemicu ke dalam variabel `lastActiveElement`.
   - Fokus keyboard langsung diarahkan secara otomatis ke tombol tindakan paling aman (misal: tombol "Batal"), bukan ke tombol destruktif ("Ya, Hapus").
   - Menekan `Tab` pada elemen interaktif terakhir di modal harus memindahkan fokus kembali ke elemen interaktif pertama di dalam modal.
   - Menekan `Shift + Tab` pada elemen pertama harus melompat ke elemen terakhir di dalam modal (*circular focus trap*).
   - Menekan tombol `Escape` harus menutup modal dialog.
   - Saat modal tertutup, fokus browser wajib dikembalikan secara mulus ke `lastActiveElement`.
3. **Inert Background:**
   - Semua elemen di luar container dialog harus dinonaktifkan dari interaksi keyboard dan screen reader (menggunakan atribut `inert` atau `aria-hidden="true"` pada elemen sibling utama).
4. **Sensitivitas Gaya & Motion:**
   - Animasi fade-in dan scale-up modal harus dibatasi atau dinonaktifkan ketika sistem operasi mengaktifkan `@media (prefers-reduced-motion: reduce)`.
   - Tombol interaktif memiliki indikator fokus yang sangat jelas (`outline` minimal 2px solid dengan kontras tinggi terhadap latar modal).

### Format Pengumpulan & Rubrik Penilaian

| Kriteria Penilaian | Bobot | Deskripsi Bukti Keberhasilan |
| :--- | :---: | :--- |
| **WAI-ARIA & Semantics** | 25% | Penerapan `role="alertdialog"`, `aria-modal="true"`, `aria-labelledby`, dan `aria-describedby` tepat sasaran tanpa sintaks redundan. |
| **Focus Trapping Engine** | 35% | Siklus hidup fokus keyboard (simpan trigger, auto-focus batal, circular Tab/Shift+Tab, restore trigger) berjalan 100% tanpa error kursor bocor ke background. |
| **Keyboard Interaction** | 20% | Tombol `Escape` berfungsi, tombol `Enter`/`Space` mengaktifkan aksi, tidak ada keyboard trap permanen. |
| **Visual Styling & Inklusivitas** | 20% | Kontras teks minimum > 4.5:1, target sentuh tombol minimal 44x44px, styling `:focus-visible` kontras ganda, serta aturan `prefers-reduced-motion`. |

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan daftar periksa berikut untuk memvalidasi kesiapan Anda sebelum memimpin audit aksesibilitas di level produksi:

- [ ] **WCAG Principles (POUR):** Saya dapat menjelaskan dan mengidentifikasi implementasi teknis dari 4 pilar utama: *Perceivable*, *Operable*, *Understandable*, dan *Robust*.
- [ ] **Level Kepatuhan:** Saya memahami perbedaan batasan antara WCAG 2.1 / 2.2 Level A (kebutuhan dasar), Level AA (standar kepatuhan hukum internasional umum seperti ADA dan EN 301 549), dan Level AAA (tingkat khusus lanjutan).
- [ ] **Screen Reader Testing:** Saya terbiasa menjalankan pengujian fungsional secara mandiri menggunakan setidaknya satu screen reader utama (NVDA di Windows, VoiceOver di macOS/iOS, atau TalkBack di Android).
- [ ] **Keyboard-Only Traversal:** Saya mampu menavigasi seluruh alur checkout atau formulir pendaftaran aplikasi tanpa menggunakan mouse sama sekali, dengan status fokus yang selalu tampak jelas (*visible focus indicator*).
- [ ] **Color Independence:** Saya memastikan bahwa peringatan error, status sukses, dan kategori data pada diagram tidak bergantung hanya pada warna saja, melainkan selalu disertai label teks, ikon semantik, atau pola grafis pembeda.
- [ ] **Automated vs Manual Auditing:** Saya memahami bahwa alat audit otomatis (seperti Lighthouse, Axe-core, Pa11y) hanya mampu menangkap 30% - 40% dari total masalah aksesibilitas, dan sisanya membutuhkan pengujian logika interaksi manual.
- [ ] **Accessibility Tree Inspection:** Saya mampu membuka panel *Accessibility* di Chrome DevTools / Firefox Developer Tools untuk menginspeksi nilai *Computed Role*, *Name*, dan *State* dari setiap elemen antarmuka kustom.
