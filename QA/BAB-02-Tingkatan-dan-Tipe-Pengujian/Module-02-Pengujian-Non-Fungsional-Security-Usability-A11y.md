---
[⬅️ Module 01: Functional Testing Levels](./Module-01-Pengujian-Fungsional-Unit-Integrasi-Sistem-Regression.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 02 ➡️](./BAB-02-Quiz-dan-Challenge.md)
---

# Module 02: Pengujian Non-Fungsional: Performance, Security (OWASP), Usability, & Aksesibilitas (WCAG 2.1)

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengidentifikasi dan membedakan cakupan **Non-Functional Testing (NFT)** dibandingkan pengujian fungsional (*"How well does the system work?" vs "What does the system do?"*).
- Memahami pilar-pilar utama NFT: **Performance Testing**, **Security Testing**, **Usability Testing**, **Accessibility (A11y) Testing**, dan **Compatibility Testing**.
- Memahami pola kerentanan keamanan web populer dari sudut pandang QA (**OWASP Top 10**): *SQL Injection, Cross-Site Scripting (XSS), Broken Object Level Authorization (BOLA),* dan *Sensitive Data Exposure*.
- Menguasai standar internasional aksesibilitas web **WCAG 2.1** dengan 4 pilar **POUR** (*Perceivable, Operable, Understandable, Robust*) pada level kepatuhan **Level AA**.
- Melakukan audit aksesibilitas antarmuka menggunakan teknik inspeksi DOM: rasio kontras warna (*Color Contrast Ratio* min. 4.5:1), atribut `aria-*`, navigasi keyboard (*Focus Trap & Tab Order*), serta teks alternatif gambar (`alt`).

---

## 2. Prerequisite
- Memahami konsep dasar tingkat pengujian (Unit, Integration, System) dari Module 01.
- Pengetahuan dasar tentang elemen HTML (`<button>`, `<input>`, `<img>`, `<a>`) dan protokol HTTP.

---

## 3. Concept
Pengujian fungsional memastikan bahwa ketika pengguna menekan tombol *"Kirim Uang"*, uang sebesar Rp 50.000 benar-benar berpindah ke rekening penerima. Namun, pengujian fungsional tidak dapat menjawab pertanyaan krusial berikut:
- *Apakah sistem tetap bisa mengirim uang jika ada 100.000 pengguna menekan tombol bersamaan?* (**Performance / Concurrency**)
- *Apakah penyerang bisa memanipulasi parameter HTTP agar uang terkirim dari rekening orang lain?* (**Security / Authorization**)
- *Apakah pengguna tunanetra yang menggunakan screen reader dapat mengetahui fungsi tombol tersebut?* (**Accessibility / WCAG**)
- *Apakah tombol tersebut responsif dan nyaman digunakan pada layar ponsel 4 inci dengan satu tangan?* (**Usability & Responsiveness**)

Inilah domain dari **Non-Functional Testing (NFT)**. NFT menguji atribut kualitas, ketahanan, kepatuhan hukum, dan pengalaman pengguna dari sistem perangkat lunak.

---

## 4. Why?
Mengapa QA modern wajib menguasai pengujian non-fungsional?
1. **Dampak Hukum & Kepatuhan (Legal Compliance)**: Di banyak negara maju, aplikasi yang tidak memenuhi standar aksesibilitas WCAG dapat dituntut di pengadilan perdata (*ADA Lawsuit*), yang berakibat denda jutaan dolar dan rusaknya reputasi brand.
2. **Keamanan Data & Pelanggaran Privasi (Data Breach)**: Rata-rata kerugian akibat pembobolan data menurut laporan IBM mencapai $4,45 juta per insiden. QA adalah garis pertahanan pertama sebelum kode rilis ke publik.
3. **Konversi Bisnis & Retensi Pengguna**: Studi Google menunjukkan bahwa keterlambatan loading halaman sebesar 1 detik menurunkan angka konversi e-commerce hingga 20%.

---

## 5. What? Pilar Utama Non-Functional Testing

### A. Taksonomi Pengujian Non-Fungsional

```text
+-------------------------------------------------------------------------+
|                  NON-FUNCTIONAL TESTING (NFT) TAXONOMY                  |
+-------------------------------------------------------------------------+
| 1. PERFORMANCE TESTING                                                  |
|    - Load Testing: Menguji perilaku sistem pada beban normal/puncak.    |
|    - Stress Testing: Menguji batas hancur sistem (breaking point).      |
|    - Spike Testing: Menguji lonjakan traffic tiba-tiba dalam hitungan detik.|
|    - Soak/Endurance: Menguji stabilitas jangka panjang (memory leaks).  |
+-------------------------------------------------------------------------+
| 2. SECURITY TESTING (Dasar QA)                                          |
|    - Autentikasi & Sesi: Token timeout, brute force lock.               |
|    - Otorisasi: Verifikasi akses role (Admin vs Regular User).          |
|    - Input Sanitization: SQL Injection, Reflected/Stored XSS.           |
+-------------------------------------------------------------------------+
| 3. ACCESSIBILITY TESTING (WCAG 2.1 Level AA)                            |
|    - POUR: Perceivable, Operable, Understandable, Robust.               |
|    - Screen Reader compatibility, Keyboard navigation, Contrast ratio.  |
+-------------------------------------------------------------------------+
| 4. COMPATIBILITY & USABILITY TESTING                                    |
|    - Cross-Browser: Chrome, Safari, Firefox, Edge.                      |
|    - Cross-Device: iOS, Android, Desktop resolusi variatif.             |
|    - Usability: Heuristic Evaluation (Jakob Nielsen 10 Usability Heuristics)|
+-------------------------------------------------------------------------+
```

---

## 6. How? Standar Aksesibilitas WCAG 2.1 (Prinsip POUR)

World Wide Web Consortium (W3C) menetapkan pedoman **Web Content Accessibility Guidelines (WCAG)** yang terbagi dalam 3 tingkatan: Level A (Dasar), **Level AA (Standar Industri & Hukum)**, dan Level AAA (Paling Ketat).

### 4 Prinsip POUR:
1. **Perceivable (Dapat Dipersepsikan)**:
   - Informasi dan elemen antarmuka harus dapat ditangkap oleh indera pengguna (penglihatan, pendengaran).
   - *Syarat*: Semua gambar bermakna wajib memiliki atribut `alt="..."`. Gambar dekoratif murni menggunakan `alt=""` atau `aria-hidden="true"`.
   - *Rasio Kontras*: Teks normal minimal memiliki rasio kontras warna **4.5:1** terhadap latar belakang (*background*). Teks besar ($\ge 18\text{pt}$ atau $\ge 14\text{pt bold}$) minimal memiliki rasio **3:1**.
2. **Operable (Dapat Dioperasikan)**:
   - Antarmuka tidak boleh menuntut interaksi yang tidak dapat dilakukan oleh penyandang disabilitas motorik.
   - *Syarat*: Semua fitur interaktif (tombol, link, modal, dropdown) harus dapat diakses dan diaktifkan murni menggunakan tombol **Keyboard** (`Tab`, `Shift+Tab`, `Enter`, `Space`, `Escape`).
   - *Focus Indicator*: Elemen yang sedang aktif wajib menampilkan garis fokus visual yang jelas (tidak boleh mematikan `outline: none` tanpa styling pengganti).
3. **Understandable (Dapat Dipahami)**:
   - Informasi dan navigasi harus jelas dan tidak membingungkan.
   - *Syarat*: Form input harus memiliki label eksplisit (`<label for="...">`), bukan hanya `placeholder` yang menghilang saat diketik. Pesan error harus menjelaskan cara memperbaikinya.
4. **Robust (Kuat & Kompatibel)**:
   - Konten harus dapat diinterpretasikan secara andal oleh berbagai *User Agent*, termasuk teknologi asistif (*Screen Reader* seperti NVDA, JAWS, VoiceOver).
   - *Syarat*: Menggunakan elemen HTML semantik (`<button>`, `<nav>`, `<main>`, `<header>`) alih-alih membuat tombol dari tag `<div>` atau `<span>` yang tidak memiliki keyboard listener dan role bawaan.

---

## 7. Analogy
Bayangkan sebuah restoran bintang lima:
- **Pengujian Fungsional**: Memastikan hidangan steak yang dipesan benar-benar sampai di meja pelanggan, matang medium-rare, dan disajikan dengan saus yang tepat.
- **Performance Testing**: Memastikan dapur restoran tetap bisa melayani 500 tamu sekaligus pada malam tahun baru tanpa antrean 2 jam.
- **Security Testing**: Memastikan pintu belakang dapur terkunci rapat dari orang luar yang berniat meracuni bahan makanan atau mencuri uang kasir.
- **Accessibility Testing**: Memastikan restoran memiliki jalur landai (*ramp*) untuk kursi roda, buku menu dengan huruf Braille, dan pencahayaan yang cukup bagi pelanggan lanjut usia.

---

## 8. Diagram

```text
========================================================================================
                          WCAG 2.1 POUR ACCESSIBILITY PILLARS
========================================================================================

                 [ ACCESSIBILITY (WCAG 2.1 AA) ]
                                |
        +---------------+-------+-------+---------------+
        |               |               |               |
        v               v               v               v
  [PERCEIVABLE]    [ OPERABLE ]   [UNDERSTANDABLE]   [ ROBUST ]
  - Alt text       - Keyboard      - Explicit labels - Semantic HTML
  - Color ratio      accessible    - Error hints     - ARIA roles
    (min 4.5:1)    - Visible focus - Form guidance   - Screen reader
  - Captions       - No trap lock                      ready

========================================================================================
                      CROSS-SITE SCRIPTING (XSS) QA VALIDATION FLOW
========================================================================================

 [ QA Input Malicious Payload ]
  Input: <script>alert('XSS')</script>
              |
              v
     [ Application Backend ]
              |
     +--------+--------+
     |                 |
(Vulnerable)       (Secured)
     |                 |
     v                 v
 Output mentah     Output disanitasi & di-encode:
 disimpan ke DB    &lt;script&gt;alert('XSS')&lt;/script&gt;
     |                 |
     v                 v
 Browser korban    Browser merender sebagai teks biasa.
 mengeksekusi JS   Skrip TIDAK dieksekusi!
  [DEFECT S1]       [TEST PASS]
```

---

## 9. Simple Example: Audit HTML Semantik vs Non-Semantik

```html
<!-- BURUK: Aksesibilitas 0% (Screen reader tidak mengenali sebagai tombol, keyboard tab macet) -->
<div class="my-btn" onclick="submitOrder()">
  <span>Beli Sekarang</span>
</div>

<!-- BAIK: Menggunakan HTML Semantik dengan keyboard support dan screen reader recognition bawaan -->
<button type="button" class="btn btn-primary" onclick="submitOrder()">
  Beli Sekarang
</button>

<!-- BAIK: Gambar dengan deskripsi alternatif informatif -->
<img src="sneakers-white.png" alt="Sepatu Sneakers Pria Warna Putih Ukuran 42" />

<!-- BURUK: Gambar tanpa alt text atau teks tidak bermakna -->
<img src="sneakers-white.png" alt="IMG_001.JPG" />
```

---

## 10. Practical Example: Checklist Audit Keamanan & Aksesibilitas untuk QA

### Checklist Aksesibilitas (WCAG 2.1 AA):
1. **Keyboard-Only Test**:
   - Cabut mouse atau matikan touchpad. Navigasi seluruh halaman hanya menggunakan `Tab`, `Shift+Tab`, panah, dan `Enter`.
   - Apakah semua menu, modal dialog, dan tombol bisa diakses?
   - Apakah saat modal popup muncul, fokus keyboard terkurung di dalam modal (*Focus Trap*) dan tidak melompat ke latar belakang?
2. **Color Contrast Audit**:
   - Gunakan Color Contrast Analyzer. Pastikan teks `#767676` di atas background putih `#FFFFFF` diperbaiki (karena rasio hanya 4.48:1, belum memenuhi 4.5:1).
3. **Screen Reader Voice Verification**:
   - Nyalakan Windows Narrator atau Mac VoiceOver. Tutup mata Anda dan dengarkan apakah formulir pendaftaran membacakan nama label input dengan benar.

### Checklist Keamanan Dasar untuk QA Web:
1. **Input Injection Testing**:
   - Masukkan payload string SQL sederhana `' OR '1'='1` pada field pencarian atau login. Pastikan sistem tidak menampilkan pesan error database mentah (*stack trace leakage*).
   - Masukkan payload XSS `<img src=x onerror=alert(1)>` pada field komentar profil. Pastikan tidak muncul alert box di browser.
2. **Broken Object Level Authorization (BOLA)**:
   - Login dengan User A (ID: `1001`), buka profil: `GET /api/users/1001`.
   - Ganti ID pada URL request menjadi `GET /api/users/1002` (milik User B).
   - Pastikan server mengembalikan **HTTP 403 Forbidden**, bukan data pribadi User B!

---

## 11. Real World Example: Gugatan Hukum Kasus Domino's Pizza (Robles v. Domino's Pizza LLC)
Pada tahun 2019, seorang pria tunanetra bernama Guillermo Robles menggugat jaringan waralaba Domino's Pizza di Amerika Serikat:
- **Masalah**: Robles tidak dapat memesan pizza kustom secara online karena situs web dan aplikasi mobile Domino's tidak kompatibel dengan perangkat lunak pembaca layar (*screen reader*). Situs tidak memiliki teks alternatif gambar dan tombol tidak memiliki label ARIA.
- **Argumen Domino's**: Domino's berdalih bahwa undang-undang disabilitas (*Americans with Disabilities Act / ADA*) hanya berlaku untuk toko fisik, bukan aplikasi online.
- **Putusan Mahkamah Agung AS (Supreme Court)**: Menolak banding Domino's dan menyatakan bahwa situs web dan aplikasi komersial wajib memenuhi standar aksesibilitas digital bagi semua kalangan masyarakat.
- **Dampak bagi Industri QA**: Aksesibilitas resmi diakui sebagai persyaratan wajib (*hard requirement*), bukan lagi fitur opsional yang bisa ditunda.

---

## 12. Trade-offs

| Aspek Non-Fungsional | Keuntungan | Kompleksitas Pengujian | Biaya Implementasi |
|---|---|---|---|
| **Aksesibilitas (A11y)** | Inklusivitas pengguna, SEO lebih baik, bebas risiko hukum. | Sedang (Perlu audit keyboard + screen reader). | Rendah jika diterapkan sejak awal (*Shift-Left*). |
| **Performance Testing** | Mencegah downtime di traffic puncak, menjaga reputasi. | Tinggi (Memerlukan environment replika & tools k6/JMeter). | Sedang hingga Tinggi (Infrastruktur load generator). |
| **Security Testing** | Melindungi integritas data, mencegah kebocoran data. | Sangat Tinggi (Memerlukan pemahaman celah keamanan mendalam). | Tinggi (Penetration testing & audit sertifikasi). |

---

## 13. When To Use
- Terapkan **Aksesibilitas (WCAG 2.1 AA)** pada seluruh produk publik (layanan publik, perbankan, e-commerce, kesehatan, pendidikan).
- Terapkan **Security Testing BOLA & XSS** pada setiap penambahan endpoint REST API baru yang mengembalikan data pengguna.
- Terapkan **Performance / Stress Testing** sebelum peluncuran kampanye nasional (Promo Flash Sale, Registrasi CPNS, Tiket Konser).

## 14. When NOT To Use
- Jangan menghabiskan anggaran ribuan dolar untuk *Extreme Load Testing (100.000 VU)* pada dashboard admin internal perusahaan yang hanya digunakan oleh 5 orang staff HRD.
- Jangan memaksakan Level AAA WCAG (seperti rasio kontras 7:1) pada prototipe internal eksperimental yang belum divalidasi pasarnya.

---

## 15. Common Mistakes

```text
1. MISTAKE: Mematikan outline fokus keyboard pada CSS ("outline: none;").
   WHY IT HAPPENS: Desainer grafis merasa garis biru fokus merusak estetika visual tombol.
   WHY IT IS BAD: Pengguna yang mengandalkan keyboard tidak dapat melihat elemen mana yang sedang aktif.
   IMPACT: Melanggar WCAG 2.4.7 (Focus Visible), situs tidak dapat digunakan penyandang disabilitas motorik.
   CORRECT APPROACH: Ganti dengan custom focus state yang indah, misalnya "outline: 2px solid #2563EB; outline-offset: 2px;".

2. MISTAKE: Placeholder digunakan sebagai pengganti label form input.
   WHY IT HAPPENS: Ingin tampilan form terlihat minimalis dan ringkas.
   WHY IT IS BAD: Saat pengguna mulai mengetik, teks placeholder menghilang sehingga pengguna lupa input apa yang diminta.
   IMPACT: Menggagalkan uji aksesibilitas dan menyulitkan pengguna lanjut usia atau penderita cognitive impairment.
   CORRECT APPROACH: Gunakan tag <label for="..."> yang jelas dan permanen di atas kolom isian.
```

---

## 16. Best Practices

### Must Have
- Atribut `alt` pada setiap elemen `<img>` yang bermakna informasi.
- Navigasi keyboard penuh (`Tab` & `Enter`) pada seluruh komponen interaktif tanpa ada jebakan fokus (*no keyboard trap*).
- Validasi otorisasi data (BOLA) pada endpoint API yang memiliki parameter ID.

### Recommended
- Mengintegrasikan linter aksesibilitas otomatis (seperti `axe-core` atau `eslint-plugin-jsx-a11y`) ke dalam pipeline CI/CD frontend.
- Menentukan batas ambang performa (*Performance Budgets*) pada Lighthouse (misal: First Contentful Paint < 1.5 detik).

### Advanced
- Melakukan *Chaos Engineering* & *Soak Testing* selama 24 jam nonstop untuk mendeteksi kebocoran memori (*memory leak*) pada aplikasi microservices di staging.

### Avoid / Overengineering
- Menulis ulang seluruh styling komponen bawaan HTML native hanya demi animasi mewah yang justru merusak keyboard accessibility.

---

## 17. Troubleshooting: Diagnosa Masalah Kontras Warna
Jika skor kontras warna gagal pada tombol:
1. Hitung rasio kontras menggunakan rumus Luminansi Relatif WCAG:
   $$\text{Ratio} = \frac{L_1 + 0.05}{L_2 + 0.05}$$
   di mana $L_1$ adalah luminansi warna yang lebih terang dan $L_2$ adalah warna yang lebih gelap.
2. Jika rasio $< 4.5:1$, gelapkan warna latar belakang atau terangkan warna teks hingga mencapai nilai $\ge 4.5:1$.

---

## 18. Exercise
1. Tinjau potongan kode formulir login berikut dan identifikasi minimal 3 pelanggaran standar aksesibilitas WCAG:
   ```html
   <div style="background-color: #FAFAFA; color: #CCCCCC;">
     <h2>Masuk ke Akun Anda</h2>
     <input type="text" placeholder="Masukkan Email Anda" />
     <input type="password" placeholder="Kata Sandi" />
     <span onclick="login()">Kirim</span>
   </div>
   ```
2. Jelaskan perbaikan kode di atas agar memenuhi standar WCAG 2.1 Level AA.

---

## 19. Challenge
Sebuah aplikasi perbankan digital memiliki fitur transfer dana antar-rekening.
Rancang sebuah dokumen skenario pengujian non-fungsional terintegrasi yang mencakup:
1. **2 Uji Keamanan**: 1 skenario pengujian otorisasi BOLA (IDOR) dan 1 skenario brute-force PIN transaksi.
2. **2 Uji Aksesibilitas**: Verifikasi pembacaan saldo oleh Screen Reader dan konfirmasi transfer via keyboard.
3. **1 Uji Performa Beban**: Kriteria sukses uji beban saat terjadi transfer massal di tanggal gajian (target: 2.000 TPS, latensi p95 < 800 ms, error rate < 0.01%).

---

## 20. Summary
- Non-Functional Testing (NFT) menguji ketahanan, performa, keamanan, dan inklusivitas antarmuka perangkat lunak.
- Standar WCAG 2.1 AA dengan prinsip POUR (Perceivable, Operable, Understandable, Robust) merupakan standar hukum dan etika global untuk inklusi digital.
- Keamanan dasar bagi QA berfokus pada pencegahan injeksi input, validasi otorisasi (BOLA), dan perlindungan data sensitif.
- Membangun kualitas non-fungsional sejak awal jauh lebih murah daripada menghadapi tuntutan hukum atau kerugian peretasan data di kemudian hari.

---

## Hands-on Practice: Simulator Auditor Aksesibilitas DOM & Kontras Warna (WCAG 2.1 AA)
Jalankan script simulator yang mem-parsing elemen antarmuka DOM, mengaudit teks alternatif gambar, mendeteksi ketiadaan label form, mengevaluasi tombol non-semantik, dan menghitung rasio kontras warna otomatis:

```bash
node QA/BAB-02-Tingkatan-dan-Tipe-Pengujian/hands-on/m02/a11y_wcag_dom_auditor_sim.js
```

---
[⬅️ Module 01: Functional Testing Levels](./Module-01-Pengujian-Fungsional-Unit-Integrasi-Sistem-Regression.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 02 ➡️](./BAB-02-Quiz-dan-Challenge.md)
---
