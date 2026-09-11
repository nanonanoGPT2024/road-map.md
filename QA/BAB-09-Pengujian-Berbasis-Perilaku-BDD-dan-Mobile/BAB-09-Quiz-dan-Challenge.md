---
[⬅️ Module 02: Mobile Testing & AxeCore](./Module-02-Mobile-Testing-Appium-dan-Aksesibilitas-AxeCore.md) | [📋 Silabus Induk](../README.md) | [BAB 10: CI/CD & Flaky Test Management ➡️](../BAB-10-CICD-Integration-Flaky-Test-dan-Quality-Gates/Module-01-CI-CD-Testing-Pipeline-GitHub-Actions-Parallel-Sharding.md)
---

# BAB 09: Quiz, Evaluasi, & Practical Challenge

## 1. Chapter Summary & Evaluasi Pemahaman
Pada BAB 09, Anda telah memperluas kapabilitas pengujian ke domain perilaku bisnis, perangkat bergerak, dan inklusi aksesibilitas:
1. **Behavior-Driven Development (BDD)**: Membangun jembatan kolaborasi antara Product Owner, Developer, dan QA (*The Three Amigos*) menggunakan bahasa domain terpadu (*Ubiquitous Language*).
2. **Sintaks Gherkin**: Menguasai kata kunci `Feature`, `Background`, `Scenario`, `Given-When-Then`, serta matriks `Scenario Outline` dan `Examples`.
3. **Declarative vs Imperative BDD**: Menghindari perangkap penulisan detail klik antarmuka yang rapuh dan mempertahankan fokus murni pada nilai bisnis.
4. **Living Documentation**: Menghasilkan dokumentasi sistem hidup yang memvalidasi dirinya sendiri di setiap proses build CI/CD.
5. **Otomasi Mobile Lintas Platform (Appium)**: Mengendalikan perangkat Android (UiAutomator2) dan iOS (XCUITest) menggunakan protokol standar W3C WebDriver dan strategi locator `accessibility-id`.
6. **Gestur Sentuhan & Audit Aksesibilitas (axe-core)**: Mengotomasi gestur sentuh (Swipe, Scroll, Pinch) dan memindai kepatuhan WCAG 2.1 AA (rasio kontras, target sentuh 48dp, pembaca layar).

---

## 2. Interactive Quiz

### Bagian A: Basic Questions (Konseptual Fundamental)
1. **Pertanyaan 1**: Siapa saja tiga peran yang tergabung dalam konsep **"The Three Amigos"** dalam metodologi BDD dan apa peran masing-masing pihak?
2. **Pertanyaan 2**: Apa perbedaan mendasar antara gaya penulisan Gherkin **Declarative** dan **Imperative**? Berikan satu contoh singkat yang membedakan keduanya!
3. **Pertanyaan 3**: Apa yang dimaksud dengan **Living Documentation** dalam konteks BDD?
4. **Pertanyaan 4**: Mengapa **Accessibility ID (`content-desc` pada Android dan `accessibilityIdentifier` pada iOS)** menjadi strategi locator paling direkomendasikan dalam otomasi Appium?
5. **Pertanyaan 5**: Berapakah ukuran area sentuh minimal (*Touch Target Size*) untuk tombol interaktif pada perangkat mobile menurut standar aksesibilitas WCAG 2.5.5?

### Bagian B: Intermediate Questions (Analisis & Teknik Lanjutan)
6. **Pertanyaan 7**: Kapan seorang QA harus menggunakan fitur **`Scenario Outline`** dan tabel **`Examples`** dalam file Gherkin?
7. **Pertanyaan 7**: Jelaskan bagaimana W3C Actions API mengeksekusi gestur **Vertical Scroll / Swipe Up** pada layar ponsel dari sudut pandang koordinat layar (*pointerMove*, *pointerDown*, *pointerUp*)!
8. **Pertanyaan 8**: Apa perbedaan arsitektur pengujian antara aplikasi mobile **Native** (Java/Kotlin/Swift) dan aplikasi **Hybrid Webview** saat diotomasi dengan Appium?
9. **Pertanyaan 9**: Bagaimana engine **`axe-core`** membantu tim QA mendeteksi pelanggaran aksesibilitas secara otomatis dan mengapa audit manual tetap dibutuhkan?
10. **Pertanyaan 10**: Apa fungsi dari tag Gherkin seperti `@smoke` dan `@regression` dalam mengatur strategi eksekusi pengujian di pipeline CI/CD?

### Bagian C: Scenario-Based Questions (Problem Solving Dunia Nyata)
11. **Skenario 1**: Seorang Product Manager menulis skenario Gherkin: *"When user enters 'admin' in input#username and clicks button.btn-blue"*. Sebagai QA Lead yang menerapkan prinsip BDD murni, mengapa Anda wajib menolak skrip ini dan bagaimana format perbaikan deklaratifnya?
12. **Skenario 2**: Skrip Appium untuk alur pembelian tiket selalu gagal saat dijalankan pada ponsel Android Xiaomi dan Oppo, namun berjalan mulus di emulator Google Pixel. Setelah diinvestigasi, popup sistem "Izin Lokasi" memiliki tombol dengan teks yang berbeda antar-vendor ponsel. Bagaimana strategi Anda mengatasi fragmentasi dialog sistem ini di Appium?
13. **Skenario 3**: Sebuah aplikasi fintech mobile ingin meluncurkan fitur dompet digital baru. Hasil pemindaian axe-core menemukan bahwa tombol "Kirim Uang" berukuran $30 \times 30 \text{ dp}$ dan tidak memiliki atribut `content-description`. Jelaskan dampak bisnis dan hukum dari temuan ini jika aplikasi tetap dipaksakan rilis ke Google Play Store!

---

## 3. Chapter Challenge: Perancangan BDD Living Suite & Otomasi Mobile Fintech

### Deskripsi Skenario
Sebuah aplikasi mobile perbankan bernama **"NusantaraPay"** sedang mengembangkan fitur baru: **"Transfer Antar-Pengguna Menggunakan Kode QR (QRIS Mobile)"**:
- Pengguna membuka kamera pemindai QR di dalam aplikasi.
- Memindai kode QR merchant atau pengguna lain.
- Layar menampilkan nama penerima dan form nominal transfer.
- Pengguna memasukkan nominal dan PIN 6 digit.
- Pembayaran sukses dan struk transfer muncul di layar.

### Tugas Anda (Deliverables):
1. **Living Documentation Gherkin Feature File (`qris_transfer.feature`)**:
   - Tuliskan file feature deklaratif lengkap yang mencakup 1 Background, 1 Scenario Happy Path, dan 1 Scenario Outline untuk variasi validasi nominal transfer (Transfer Rp 10.000 sukses, Transfer Rp 500 tertolak di bawah minimum, dan Transfer Rp 25.000.000 tertolak di atas limit harian).
2. **Step Definitions Architecture**:
   - Tuliskan pemetaan Step Definitions dalam JavaScript/TypeScript menggunakan regular expression parameter matching.
3. **Appium Mobile Gestures & Camera Permission Plan**:
   - Tuliskan konfigurasi Desired Capabilities untuk Android UiAutomator2 yang secara otomatis memberikan izin kamera (`autoGrantPermissions`).
   - Rancang fungsi helper gestur sentuh *Swipe Down to Refresh* pada riwayat transaksi.
4. **Automated Accessibility Audit Specification (axe-core)**:
   - Rancang skenario pengujian yang memindai halaman struk transaksi dan memastikan tidak ada pelanggaran *Touch Target Size* atau *Missing Content Description* pada icon verifikasi centang hijau.

---

## 4. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Filosofi BDD dan peran The Three Amigos dalam menyelaraskan kebutuhan bisnis.
- [ ] Sintaks Gherkin (Feature, Background, Scenario, Scenario Outline, Examples).
- [ ] Perbedaan tegas antara gaya penulisan Declarative vs Imperative.
- [ ] Arsitektur client-server Appium (W3C WebDriver, UiAutomator2, XCUITest).
- [ ] Cara kerja W3C Touch Actions untuk gestur Swipe, Scroll, dan Tap.
- [ ] Evaluasi audit aksesibilitas otomatis menggunakan axe-core.

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh tabel kode heksadesimal warna untuk evaluasi kontras manual (gunakan axe-core).
- [ ] Seluruh nomor port default internal driver Android ADB.

### Saya Harus Bisa Melakukan:
- [ ] Menulis skenario BDD deklaratif yang mudah dipahami stakeholder non-teknis.
- [ ] Mengimplementasikan step definitions yang memetakan kalimat Gherkin ke Page Object Model.
- [ ] Menghitung koordinat dinamis gestur sentuh mobile berdasarkan resolusi layar perangkat.

---
[⬅️ Module 02: Mobile Testing & AxeCore](./Module-02-Mobile-Testing-Appium-dan-Aksesibilitas-AxeCore.md) | [📋 Silabus Induk](../README.md) | [BAB 10: CI/CD & Flaky Test Management ➡️](../BAB-10-CICD-Integration-Flaky-Test-dan-Quality-Gates/Module-01-CI-CD-Testing-Pipeline-GitHub-Actions-Parallel-Sharding.md)
---
