---
[⬅️ Module 02: Flaky Tests & Quality Gates](./Module-02-Flaky-Test-Mitigation-Allure-Reporting-Quality-Gates.md) | [📋 Silabus Induk](../README.md) | [🏆 CAPSTONE PROJECT ➡️](../CAPSTONE-PROJECT-Enterprise-Omnichannel-Quality-Engineering.md)
---

# BAB 10: Quiz, Evaluasi, & Practical Challenge

## 1. Chapter Summary & Evaluasi Pemahaman
Pada BAB 10, Anda telah menguasai puncak kompetensi seorang Senior QA Engineer / SDET:
1. **Otomasi CI/CD Modern**: Mengintegrasikan seluruh siklus pengujian otomatis ke dalam alur kerja GitHub Actions / GitLab CI yang dipicu secara instan pada setiap event `pull_request` dan `push`.
2. **Parallel Test Sharding**: Memecah ratusan skenario pengujian ke dalam matriks mesin runner paralel di cloud (`--shard=X/Y`), memangkas durasi pipeline dari jam menjadi beberapa menit.
3. **Manajemen Flaky Test**: Mendiagnosis akar masalah kegagalan acak (Race condition, polling asinkron, polusi state) dan menerapkan pola *Test Quarantine* terstruktur.
4. **Pelaporan Eksekutif (Allure Report)**: Menyajikan dashboard metrik kualitas yang kaya dengan visualisasi kategori cacat dan lampiran rekaman video/trace.
5. **Gerbang Kualitas Rilis (Quality Gates / Go-No-Go Framework)**: Mengambil keputusan kelayakan rilis secara objektif dan matematis berdasarkan ambang batas defek, hasil smoke test, latensi performa p95, dan cakupan kode.

---

## 2. Interactive Quiz

### Bagian A: Basic Questions (Konseptual Fundamental)
1. **Pertanyaan 1**: Apa yang dimaksud dengan **Flaky Test** dan mengapa tes yang flaky sangat berbahaya bagi budaya rekayasa tim pengembang?
2. **Pertanyaan 2**: Bagaimana cara kerja teknik **Test Sharding** di Playwright dan GitHub Actions dalam mempercepat eksekusi pengujian?
3. **Pertanyaan 3**: Apa fungsi dari parameter **`fail-fast: false`** pada konfigurasi matrix strategy GitHub Actions?
4. **Pertanyaan 4**: Mengapa fitur **Auto-Retry** (mengulang tes otomatis saat gagal) tidak boleh dianggap sebagai solusi permanen untuk memperbaiki flaky tests?
5. **Pertanyaan 5**: Sebutkan minimal 3 artefak visual yang wajib disimpan dan diunggah saat pengujian web UI mengalami kegagalan di server CI/CD tanpa monitor (*Headless Cloud*)!

### Bagian B: Intermediate Questions (Analisis & Rekayasa Pipeline)
6. **Pertanyaan 6**: Jelaskan apa yang dimaksud dengan **Pola Karantina Pengujian (The Test Quarantine Pattern)** dan bagaimana alur kerja sebuah tes yang dikarantina hingga boleh kembali ke pipeline utama!
7. **Pertanyaan 7**: Sebuah test suite terdiri dari 400 test case. Saat dijalankan di CI: 380 test lulus di percobaan pertama, 16 test lulus di percobaan kedua (*retry*), dan 4 test gagal total. Hitunglah nilai **Flaky Rate** dari suite tersebut! Apakah angka ini memenuhi ambang batas industri ($\le 2\%$)?
8. **Pertanyaan 8**: Mengapa penggunaan *Caching Dependensi* (`npm cache`) dan *Browser Binary Cache* sangat disarankan pada file YAML GitHub Actions?
9. **Pertanyaan 9**: Apa perbedaan antara kategori **Product Defects** dan **Test Defects** pada laporan Allure Report?
10. **Pertanyaan 10**: Apa itu aturan **Branch Protection Rules** di GitHub dan bagaimana kaitannya dengan hasil eksekusi status check CI/CD?

### Bagian C: Scenario-Based Questions (Problem Solving Dunia Nyata)
11. **Skenario 1**: Sebuah test case checkout berhasil 100% saat dijalankan di laptop developer, namun gagal 50% saat dijalankan di runner GitHub Actions Ubuntu. Dari pemeriksaan log, tombol checkout diklik sebelum data ongkos kirim selesai dimuat oleh API. Perbaikan arsitektur apa yang wajib dilakukan pada locator atau assertion test tersebut?
12. **Skenario 2**: Jadwal rilis aplikasi mobile banking dijadwalkan pukul 17.00 WIB. Hasil evaluasi Quality Gates menunjukkan: 0 Bug S1/S2, Smoke Test 100% Lulus, namun Flaky Rate tercatat 18% dan p95 latensi transaksi mencapai 450 ms (SLA $\le 300 \text{ ms}$). Sebagai QA Lead, apakah Anda memberikan keputusan **GO** atau **NO-GO**? Berikan justifikasi profesional Anda!
13. **Skenario 3**: Pipeline CI/CD perusahaan membutuhkan waktu 90 menit dan mengonsumsi kuota build cloud yang sangat boros. Rancanglah arsitektur tahapan (*pipeline stages*) bertingkat yang menerapkan *Fail-Fast Smoke Gates* dan *Parallel Sharding* untuk memangkas waktu menjadi di bawah 15 menit!

---

## 3. Chapter Challenge: Perancangan Arsitektur Quality Engineering CI/CD Enterprise

### Deskripsi Skenario
Sebuah platform super-app logistik dan kurir instan bernama **"KirimExpress"** memiliki:
- 600 Automated Unit Tests
- 150 Automated API Contract Tests
- 300 Automated Playwright Web UI E2E Tests
- Tim engineering melakukan merge rata-rata 25 Pull Request setiap hari.

### Tugas Anda (Deliverables):
1. **GitHub Actions CI/CD Workflow (`.github/workflows/quality-gates.yml`)**:
   - Tuliskan file YAML terstruktur dengan 3 jobs bertingkat (`lint_unit` $\to$ `api_contract` $\to$ `e2e_sharded`).
   - Konfigurasikan matrix sharding 4 runner paralel pada job E2E (`--shard=${{ matrix.shard }}/4`).
   - Konfigurasikan pengunggahan artefak Playwright trace dan failure screenshot.
2. **Flaky Test Management Policy**:
   - Susun dokumen standar operasional tim (*SOP*) saat sebuah tes terdeteksi flaky: kriteria karantina, penugasan tiket bug perbaikan, dan kriteria rehabilitasi (misal: wajib lulus 30x berturut-turut di staging).
3. **Go/No-Go Release Decision Engine**:
   - Tuliskan fungsi validator programatik dalam JavaScript yang mengevaluasi apakah sebuah build berstatus `READY_FOR_PRODUCTION` atau `BLOCKED` berdasarkan input metrik rilis.

---

## 4. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Arsitektur pipeline CI/CD modern dan pemicu otomatis event Git.
- [ ] Konsep pembagian beban Test Sharding secara deterministik.
- [ ] Bahaya sistemik Flaky Tests dan 4 akar penyebab utamanya.
- [ ] Pola Karantina (Quarantine Pattern) untuk melindungi stabilitas pipeline.
- [ ] Kategori dan metrik pada dashboard Allure Report.
- [ ] Kriteria objektif pengambilan keputusan rilis (Quality Gates Go/No-Go).

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh sintaks ekspresi cron waktu dunia (gunakan generator cron online).
- [ ] Semua konfigurasi internal runner virtual machine GitHub.

### Saya Harus Bisa Melakukan:
- [ ] Menulis workflow YAML GitHub Actions lengkap dengan matrix sharding.
- [ ] Menganalisis rekaman Trace Viewer untuk menemukan akar masalah test failure di CI.
- [ ] Menegakkan gerbang kualitas yang memblokir rilis jika SLA performa atau bug blocker terlanggar.

---
[⬅️ Module 02: Flaky Tests & Quality Gates](./Module-02-Flaky-Test-Mitigation-Allure-Reporting-Quality-Gates.md) | [📋 Silabus Induk](../README.md) | [🏆 CAPSTONE PROJECT ➡️](../CAPSTONE-PROJECT-Enterprise-Omnichannel-Quality-Engineering.md)
---
