---
[⬅️ Module 02: Non-Functional Testing](./Module-02-Pengujian-Non-Fungsional-Security-Usability-A11y.md) | [📋 Silabus Induk](../README.md) | [BAB 03: Teknik Perancangan Test Case ➡️](../BAB-03-Teknik-Perancangan-Test-Case-Black-Box-White-Box/Module-01-Black-Box-Equivalence-Partitioning-BVA-Decision-Table.md)
---

# BAB 02: Quiz, Evaluasi, & Practical Challenge

## 1. Chapter Summary & Evaluasi Pemahaman
Pada BAB 02, Anda telah mempelajari pengelompokan pengujian secara mendalam:
1. **4 Tingkatan Pengujian Fungsional**: Unit Testing (terisolasi, mocks/stubs), Integration Testing (antarmuka modul/API, Top-Down vs Bottom-Up), System Testing (E2E lengkap), dan UAT (Alpha/Beta operasional bisnis).
2. **Piramida Pengujian (Testing Pyramid)**: Membangun pondasi kokoh dengan porsi 70% Unit Test, 20% Integration Test, dan 10% E2E UI Test guna menghindari malapetaka *Testing Ice Cream Cone Anti-Pattern*.
3. **Smoke vs Sanity vs Regression vs Retesting**: Menguasai perbedaan taktis dalam alur CI/CD dan penanganan bug fix.
4. **Non-Functional Testing (NFT)**: Menguji ketahanan beban (*Load/Stress/Spike*), keamanan web dasar (*OWASP Top 10, BOLA, XSS, SQLi*), serta aksesibilitas inklusif (*WCAG 2.1 AA prinsip POUR*).

---

## 2. Interactive Quiz

### Bagian A: Basic Questions (Konseptual Fundamental)
1. **Pertanyaan 1**: Mengapa pendekatan *Big-Bang Integration Testing* sangat tidak disarankan dalam proyek rekayasa perangkat lunak modern?
2. **Pertanyaan 2**: Apa perbedaan mendasar antara **Stub** dan **Driver** dalam pengujian integrasi?
3. **Pertanyaan 3**: Apa yang dimaksud dengan anti-pattern *Testing Ice Cream Cone* dan apa dampak buruknya terhadap siklus rilis tim?
4. **Pertanyaan 4**: Mengapa kita membutuhkan **Smoke Testing** sebelum tim QA menjalankan pengujian regresi yang panjang?
5. **Pertanyaan 5**: Sebutkan 4 prinsip utama aksesibilitas web menurut standar **WCAG (POUR)** dan jelaskan arti masing-masing secara singkat!

### Bagian B: Intermediate Questions (Analisis & Desain Uji)
6. **Pertanyaan 6**: Jelaskan perbedaan antara pengujian **Load Testing**, **Stress Testing**, dan **Spike Testing**. Berikan contoh skenario nyata untuk masing-masing tipe.
7. **Pertanyaan 7**: Berapakah rasio kontras warna minimum yang disyaratkan oleh WCAG 2.1 Level AA untuk teks berukuran normal (di bawah 18pt)? Mengapa teks abu-abu terang di atas background putih dilarang keras?
8. **Pertanyaan 8**: Developer mengajukan perubahan kode berupa penggantian elemen `<button>` menjadi `<div class="btn" onclick="submit()">` demi kemudahan kustomisasi CSS. Jelaskan 2 alasan mengapa QA wajib menolak perubahan ini dari sudut pandang aksesibilitas!
9. **Pertanyaan 9**: Apa itu kerentanan **Broken Object Level Authorization (BOLA / IDOR)** pada pengujian API RESTful, dan bagaimana langkah QA untuk memverifikasinya?
10. **Pertanyaan 10**: Apa perbedaan tujuan antara **Sanity Testing** dan **Regression Testing** setelah tim developer merilis patch hotfix?

### Bagian C: Scenario-Based Questions (Problem Solving Dunia Nyata)
11. **Skenario 1**: Sebuah platform e-commerce tiket konser mengalami keluhan massal: saat penjualan tiket dibuka jam 10.00, halaman web menampilkan error 504 Gateway Timeout selama 15 menit pertama. Namun saat jam 10.20 ketika kuota tiket sudah habis, server berjalan sangat normal dan cepat. Tipe pengujian non-fungsional manakah yang gagal dijalankan oleh tim QA sebelum peluncuran, dan bagaimana Anda merancang skenario ujinya?
12. **Skenario 2**: Pipeline CI/CD perusahaan Anda membutuhkan waktu 45 menit untuk menyelesaikan seluruh automated test suite di setiap Pull Request. Developer mulai mengeluh dan sering mem-bypass testing agar fitur cepat di-merge. Sebagai QA Engineer, strategi apa yang Anda terapkan berdasarkan prinsip *Testing Pyramid* dan *Test Impact Analysis*?
13. **Skenario 3**: Sebuah bank digital meluncurkan aplikasi mobile baru. Seorang pengguna tunanetra mencoba melakukan transfer uang menggunakan fitur TalkBack / VoiceOver. Namun saat tiba di halaman konfirmasi, pembaca layar hanya membacakan teks: *"Button, Button, Unlabeled Image"*. Identifikasi cacat teknis HTML/mobile view apa yang terjadi dan bagaimana solusinya?

---

## 3. Chapter Challenge: Audit Kualitas Non-Fungsional & Strategi Piramida

### Deskripsi Skenario
Sebuah aplikasi web edukasi nasional bernama **"BelajarPintar"** sedang bersiap menyambut tahun ajaran baru dengan estimasi 100.000 siswa ujian online serentak. Aplikasi memiliki modul ujian interaktif, kuis timer, dan pembayaran sertifikat digital.

### Tugas Anda (Deliverables):
1. **Piramida Pengujian & Rencana Alokasi Test**:
   - Susun tabel distribusi pengujian (Unit, Integration, E2E) untuk modul *Perhitungan Skor Ujian & Timer*.
   - Jelaskan skenario apa saja yang masuk ke Unit Test, apa yang masuk ke Integration Test, dan 1 alur kritis apa yang masuk ke E2E Test.
2. **Smoke Test Gatekeeper Plan**:
   - Tuliskan 5 butir skenario Smoke Test kritis berwaktu eksekusi $< 3$ menit yang menentukan apakah sebuah build layak diproses atau wajib di-*reject* seketika.
3. **Audit Aksesibilitas Antarmuka (A11y Review)**:
   - Diberikan cuplikan form pembayaran berikut:
     ```html
     <div style="background-color: #E2E8F0;">
       <p style="color: #CBD5E1;">Silakan masukkan PIN 6 digit:</p>
       <input type="password" placeholder="PIN" />
       <div class="confirm-btn" onclick="processPayment()">Konfirmasi</div>
     </div>
     ```
   - Temukan 3 pelanggaran WCAG 2.1 AA pada cuplikan tersebut.
   - Tuliskan kode HTML pengganti yang 100% patuh WCAG 2.1 Level AA (lengkap dengan semantik label, keyboard accessibility, dan perbaikan warna).

---

## 4. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] 4 tingkatan pengujian fungsional dan peran masing-masing dalam SDLC.
- [ ] Logika pembagian piramida pengujian dan bahaya model Ice Cream Cone.
- [ ] Perbedaan Smoke, Sanity, Re-testing, dan Regression Testing.
- [ ] 4 pilar WCAG 2.1 POUR dan rasio kontras warna standar AA (4.5:1).
- [ ] Pola pengujian keamanan dasar (XSS, BOLA/IDOR, SQLi) untuk QA.

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh algoritma konversi warna sRGB ke formula luminansi relatif (cukup menggunakan kalkulator atau script otomasi).
- [ ] Seluruh daftar kode error OWASP CWE (fokus pada dampaknya terhadap fungsionalitas dan data pengguna).

### Saya Harus Bisa Melakukan:
- [ ] Merancang unit test terisolasi dan integration test menggunakan stub/mock.
- [ ] Melakukan keyboard-only testing pada antarmuka web tanpa mouse.
- [ ] Menulis skenario pengujian otorisasi API untuk mendeteksi celah BOLA.

---
[⬅️ Module 02: Non-Functional Testing](./Module-02-Pengujian-Non-Fungsional-Security-Usability-A11y.md) | [📋 Silabus Induk](../README.md) | [BAB 03: Teknik Perancangan Test Case ➡️](../BAB-03-Teknik-Perancangan-Test-Case-Black-Box-White-Box/Module-01-Black-Box-Equivalence-Partitioning-BVA-Decision-Table.md)
---
