---
[⬅️ Module 02: SDLC, STLC, & Bug Lifecycle](./Module-02-SDLC-STLC-dan-Bug-Defect-Lifecycle.md) | [📋 Silabus Induk](../README.md) | [BAB 02: Tingkatan & Tipe Pengujian ➡️](../BAB-02-Tingkatan-dan-Tipe-Pengujian/Module-01-Pengujian-Fungsional-Unit-Integrasi-Sistem-Regression.md)
---

# BAB 01: Quiz, Evaluasi, & Practical Challenge

## 1. Chapter Summary & Evaluasi Pemahaman
Pada BAB 01, Anda telah mempelajari fondasi terpenting dalam profesi Quality Assurance:
1. **Filosofi Testing**: Pengujian bukan untuk membuktikan software bebas bug, melainkan untuk membuktikan keberadaan bug (*Testing shows presence of defects, not their absence*).
2. **Verification vs Validation**: Membedakan antara pengujian cetak biru/dokumen/kode secara statis (*"Are we building the product right?"*) dan pembuktian kecocokan kebutuhan pengguna di runtime (*"Are we building the right product?"*).
3. **7 Prinsip ISTQB**: Dari kemustahilan exhaustive testing, fenomena pestisida, defect clustering 80/20, hingga fallacy of absence of errors.
4. **STLC & Bug Lifecycle**: Alur terstruktur dari Requirement Analysis hingga Test Closure, serta State Machine pengelolaan cacat dari New, Assigned, Fixed, Retest, Verified, hingga Closed.

---

## 2. Interactive Quiz

### Bagian A: Basic Questions (Konseptual Fundamental)
1. **Pertanyaan 1**: Apa perbedaan paling mendasar antara *Quality Assurance (QA)* dan *Quality Control (QC)*?
2. **Pertanyaan 2**: Mengapa *Exhaustive Testing* (menguji seluruh kemungkinan kombinasi input) dikatakan mustahil dalam sistem dunia nyata? Berikan contoh matematis sederhana.
3. **Pertanyaan 3**: Apa yang dimaksud dengan *Pesticide Paradox* dalam pengujian software, dan bagaimana cara tim QA mengatasinya?
4. **Pertanyaan 4**: Jelaskan rantai kausalitas berikut: Apa perbedaan antara **Error (Mistake)**, **Defect (Fault/Bug)**, dan **Failure**?
5. **Pertanyaan 5**: Siapakah satu-satunya pihak/peran dalam tim engineering yang memiliki otoritas untuk memindahkan status bug menjadi `Closed`? Mengapa developer tidak boleh menutupnya sendiri?

### Bagian B: Intermediate Questions (Analisis & Metrik)
6. **Pertanyaan 6**: Jelaskan konsep *Shift-Left Testing* dan jelaskan dampaknya terhadap kurva *Cost of Quality (CoQ)* berdasarkan data industri.
7. **Pertanyaan 7**: Suatu tim QA menemukan 180 bug selama fase testing internal sebelum rilis. Setelah perangkat lunak rilis ke produksi selama 1 bulan, pengguna melaporkan 20 bug baru. Hitunglah nilai **Defect Removal Efficiency (DRE)** dari tim QA tersebut. Apakah angka tersebut memenuhi standar industri ($\ge 90\%$)?
8. **Pertanyaan 8**: Jelaskan perbedaan antara **Severity** dan **Priority**. Berikan satu contoh konkret bug yang memiliki **High Severity namun Low Priority**, dan satu contoh bug yang memiliki **Low Severity namun High Priority**.
9. **Pertanyaan 9**: Apa yang harus dilakukan seorang QA jika seorang developer menolak bug dengan alasan *"Works on my machine / Not Reproducible"*? Jelaskan 3 langkah investigasi teknis yang wajib dilakukan.
10. **Pertanyaan 10**: Apa perbedaan tujuan antara pengujian **Re-testing** dan **Regression Testing** setelah developer melakukan merge commit perbaikan bug?

### Bagian C: Scenario-Based Questions (Problem Solving Dunia Nyata)
11. **Skenario 1**: Anda adalah QA Lead di startup fintech yang akan merilis fitur QRIS Payment dalam 3 hari. Product Manager bersikeras ingin langsung merilis fitur karena mengejar target kuartal, meskipun terdapat 2 bug berstatus *Severity: S2 (Major)* yang belum selesai diperbaiki oleh developer. Sebagai penanggung jawab kualitas, apa langkah strategis dan profesional yang Anda ambil?
12. **Skenario 2**: Sistem aplikasi mobile perbankan sering mengalami freeze ketika pengguna berpindah dari koneksi Wi-Fi ke koneksi seluler 4G yang tidak stabil. Developer kesulitan mereproduksi karena di kantor koneksi internet selalu stabil dan kencang. Rancanglah format tiket bug report yang presisi agar developer dapat langsung mereproduksi masalah tersebut tanpa debat.
13. **Skenario 3**: Sebuah e-commerce merayakan ulang tahun dengan promo diskon besar. Semua unit test dan automation script pass 100%. Namun saat jam 00:00, ratusan pengguna protes karena kupon diskon mereka terpotong dua kali dan saldo dompet digital menjadi negatif. Berdasarkan 7 Prinsip Testing ISTQB, prinsip manakah yang dilanggar atau terlupakan oleh tim engineering?

---

## 3. Chapter Challenge: Perancangan Test Strategy & Defect Triage Board

### Deskripsi Skenario
Sebuah platform *HealthTech* bernama **"DocCepat"** sedang membangun modul baru: **"Pemesanan Resep Obat Narkotika & Psikotropika Secara Terbatas"**.
Fitur ini memiliki regulasi kepatuhan hukum ketat dari Kementerian Kesehatan:
- Pasien wajib mengunggah foto KTP dan Surat Diagnosis Dokter Spesialis.
- Dokter yang meresepkan wajib memiliki Nomor SIP (Surat Izin Praktik) yang aktif dan terverifikasi di database Kemenkes.
- Pembayaran hanya bisa dilakukan menggunakan Virtual Account atau Kartu Debit berotentikasi 3D-Secure (OTP).
- Pengiriman obat hanya boleh menggunakan kurir medis bersertifikat dengan kode verifikasi serah terima fisik (PIN 6 digit).

### Tugas Anda (Deliverables):
1. **Requirement Analysis & Ambiguity Detection**:
   Tuliskan minimal 4 potensi celah kebutuhan (*ambiguity/unclear requirements*) yang harus Anda tanyakan kembali ke Product Manager dan Security Architect sebelum koding dimulai.
2. **Test Plan Outline (Scope & Criteria)**:
   - Tentukan apa saja yang masuk ke dalam *In-Scope* dan *Out-of-Scope* pengujian QA.
   - Tetapkan **3 Entry Criteria** (syarat awal sebelum QA mulai menguji di staging).
   - Tetapkan **3 Exit Criteria** mutlak sebelum fitur diizinkan rilis ke produksi (*Go-Live*).
3. **Defect Triage Simulation**:
   Diberikan 3 temuan bug berikut, tentukan Severity (S1-S4), Priority (P1-P4), dan berikan justifikasinya:
   - *Bug A*: Pasien dapat mengunggah file gambar resep berukuran 100 MB yang menyebabkan memori worker server naik menjadi 98%.
   - *Bug B*: Nomor SIP dokter yang berakhiran angka ganjil gagal terverifikasi ke API sandbox Kemenkes karena timeout 10 detik.
   - *Bug C*: Teks disclaimer hukum pada halaman persetujuan pengguna memiliki salah ketik: *"Kementrian"* bukan *"Kementerian"*.

---

## 4. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Esensi bahwa testing bertujuan mendeteksi risiko cacat, bukan membuktikan ketiadaan bug secara mutlak.
- [ ] Perbedaan fundamental antara Verification (statis, cetak biru) dan Validation (dinamis, runtime, bisnis).
- [ ] 7 Prinsip Pengujian Perangkat Lunak ISTQB dan contoh manifestasinya di lapangan.
- [ ] Tahapan STLC dari Requirement Analysis hingga Test Cycle Closure.
- [ ] Transisi status Defect Life Cycle dan peran otoritas masing-masing anggota tim engineering.
- [ ] Cara menghitung metrik DRE dan Defect Density.

### Saya Tidak Perlu Menghafal:
- [ ] Format kode template IEEE 829 kata per kata (yang terpenting memahami komponen logisnya).
- [ ] Seluruh nomor pasal standar ISO/IEC 25010 (cukup memahami 8 karakteristik utamanya).

### Saya Harus Bisa Melakukan:
- [ ] Merancang assertion engine mandiri untuk memverifikasi logika bisnis data.
- [ ] Menulis laporan bug profesional yang terstruktur (STR, Environment, Expected vs Actual).
- [ ] Melakukan investigasi saat menghadapi isu *"Works on my machine"*.

---
[⬅️ Module 02: SDLC, STLC, & Bug Lifecycle](./Module-02-SDLC-STLC-dan-Bug-Defect-Lifecycle.md) | [📋 Silabus Induk](../README.md) | [BAB 02: Tingkatan & Tipe Pengujian ➡️](../BAB-02-Tingkatan-dan-Tipe-Pengujian/Module-01-Pengujian-Fungsional-Unit-Integrasi-Sistem-Regression.md)
---
