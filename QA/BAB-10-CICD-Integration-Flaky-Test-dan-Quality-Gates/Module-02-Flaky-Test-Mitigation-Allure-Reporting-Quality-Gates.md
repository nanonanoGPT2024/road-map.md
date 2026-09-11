---
[⬅️ Module 01: CI/CD Pipeline & Sharding](./Module-01-CI-CD-Testing-Pipeline-GitHub-Actions-Parallel-Sharding.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 10 ➡️](./BAB-10-Quiz-dan-Challenge.md)
---

# Module 02: Manajemen Flaky Tests, Pelaporan Kaya (Allure Report), & Gerbang Kualitas Rilis (Quality Gates)

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengidentifikasi anatomi dan bahaya **Flaky Tests** (tes yang kadang lulus dan kadang gagal tanpa ada perubahan kode sumber) terhadap integritas tim engineering.
- Mendiagnosis 4 akar penyebab utama flakiness: **Race Conditions / Asynchronous Timing**, **Test State Pollution / Leaks**, **Ketidakstabilan Jaringan & Third-Party APIs**, serta **Order-Dependent Tests**.
- Menerapkan strategi mitigasi terstandar: **Retry Mechanism** cerdas, pola **Test Quarantine / Isolation Pattern** (mengarantina tes yang tidak stabil dari *blocking pipeline*), serta perhitungan metrik **Flaky Rate**.
- Mengintegrasikan pelaporan pengujian modern tingkat eksekutif (**Allure Report** & **Playwright HTML Report**) lengkap dengan metadata visual (kategori cacat, riwayat tren stabilitas, lampiran video/trace).
- Menegakkan **Quality Gates & Deployment Policies (Go/No-Go Decision Framework)** yang objektif sebelum kode diizinkan rilis ke produksi: *Zero P0/P1 Defects, 100% Smoke Pass, p95 Latency SLA, Minimum Code Coverage, dan Zero Flaky Blockers*.

---

## 2. Prerequisite
- Memahami konsep pipeline CI/CD dan Test Sharding dari Module 01.
- Pemahaman siklus hidup bug (STLC) dan metrik defek dari BAB 01.

---

## 3. Concept
Musuh terbesar dari otomasi pengujian bukanlah bug pada perangkat lunak, melainkan **Flaky Tests**. Ketika sebuah test suite sering gagal secara acak, tim developer akan kehilangan kepercayaan pada pengujian otomasi (*The Boy Who Cried Wolf Syndrome*). Developer akan mengabaikan tanda merah di pipeline CI/CD, menganggapnya sebagai *"hanya tes yang biasa error sendiri"*, lalu menekan tombol merge secara paksa. Akibatnya, bug produksi yang sebenarnya berbahaya lolos tanpa terdeteksi.

Untuk memulihkan kepercayaan pada pipeline pengujian, organisasi rekayasa perangkat lunak kelas dunia menerapkan **Manajemen Flaky Test** yang ketat melalui pola **Test Quarantine**, pelaporan transparan menggunakan **Allure Report**, serta penegakan **Quality Gates** terprogram yang secara objektif menentukan apakah sebuah build layak mendapatkan sertifikat rilis (*Production Readiness*).

---

## 4. Why?
Mengapa Flaky Test Management dan Quality Gates sangat menentukan keberhasilan organisasi?
1. **Mengembalikan Kepercayaan Tim (Trust in CI)**: Jika status build hijau berarti sistem 100% sehat dan status merah berarti ada bug nyata yang wajib diperbaiki, tim developer akan menghormati hasil pengujian.
2. **Menghilangkan Keputusan Subjektif (*No More Gut-Feeling Releases*)**: Tidak ada lagi perdebatan *"Apakah kita siap rilis hari ini?"* berdasarkan perasaan atau asumsi. Keputusan rilis didikte secara matematis oleh kriteria gerbang kualitas (*Hard Quality Gates*).
3. **Visibilitas Tingkat Eksekutif**: Allure Report menyajikan dashboard grafis yang dapat dipahami oleh VP of Engineering, Product Director, hingga tim audit eksternal.

---

## 5. What?

### A. 4 Akar Masalah Flaky Tests & Solusi Rekayasa

```text
========================================================================================
                          ROOT CAUSES OF TEST FLAKINESS
========================================================================================

 1. ASYNC TIMING & RACE CONDITIONS
    - Penyebab: UI mengklik elemen yang animasinya belum selesai atau API belum merespons.
    - Solusi  : Ganti assertion biasa dengan Web-First Assertions (Auto-retrying).

 2. TEST STATE POLLUTION / LEAKAGE
    - Penyebab: Test A mengubah database atau local storage yang dipakai Test B.
    - Solusi  : Terapkan Isolated Test Data Factories & Fresh Browser Context per test.

 3. THIRD-PARTY NETWORK INSTABILITY
    - Penyebab: Mengandalkan sandbox API eksternal (Payment/SMS) yang sering timeout.
    - Solusi  : Terapkan Network Mocking / Service Virtualization (page.route).

 4. ORDER DEPENDENCY
    - Penyebab: Test B hanya bisa lulus jika Test A dijalankan persis sebelumnya.
    - Solusi  : Jalankan test suite dengan urutan acak (--shuffle) di CI untuk membongkar dependensi.
```

---

### B. Pola Karantina Pengujian (The Test Quarantine Pattern)

Alih-alih membiarkan flaky test memblokir seluruh rilis tim:
1. **Deteksi**: Sistem mendeteksi test yang gagal lalu lulus saat di-retry (*Retry Passed*).
2. **Karantina**: Test tersebut otomatis diberi tag `@quarantine` dan dikeluarkan dari gerbang *Blocking PR Pipeline*.
3. **Tiket Defek**: Sistem membuat tiket Jira otomatis untuk tim pemilik test (*Fix Flakiness SLA: 3 Hari*).
4. **Rehabilitasi**: Test dijalankan di *Quarantine Pipeline* khusus (misal 50 kali berulang-ulang); jika lulus 50/50, test dikembalikan ke pipeline utama.

```text
========================================================================================
                          TEST QUARANTINE WORKFLOW
========================================================================================

  [ Test Suite di CI Pipeline ]
               |
               v (Terdeteksi Flaky / Gagal Acak)
  +--------------------------+
  | Karantina (@quarantine)  | <--- Dikeluarkan dari Blocking Gate
  +--------------------------+
               |
               v (Buka Tiket Bug Teknis untuk SDET)
  [ Perbaiki Masalah Timing / Mocking ]
               |
               v (Uji Stabilitas: Jalankan 50x Nonstop)
  [ 50/50 Lulus Berturut-turut? ]
         |                     |
       (YA)                 (TIDAK)
         v                     v
  [ Kembali ke PR Gate ]  [ Tetap Dikarantina ]
```

---

### C. Kriteria Gerbang Kualitas Rilis (The Go/No-Go Framework)

| Kategori Gerbang | Parameter Metrik | Ambang Batas Wajib (Threshold) | Aksi Jika Gagal |
|---|---|---|---|
| **Defect Blocker** | Severity: S1 (Critical) & S2 (Major) | **0 Bug Aktif** | **BLOKIR RILIS (NO-GO)** |
| **Smoke Suite** | Automated Smoke Tests di Staging | **100% Lulus (Zero Tolerance)** | **BLOKIR RILIS (NO-GO)** |
| **Regression Suite**| P0 & P1 Critical Business Journeys | $\ge 99\%$ Lulus | Perlu persetujuan QA Lead |
| **Performance SLA**| p95 Latency pada jam sibuk | $\le 300 \text{ ms}$ | Kembalikan ke Backend Team |
| **Aksesibilitas** | Pelanggaran axe-core (Critical A11y) | **0 Pelanggaran** | Perlu perbaikan tim Frontend |
| **Code Coverage** | Branch Coverage pada Core Services | $\ge 80\%$ | Peringatan / Blokir PR |

---

## 6. How? Konfigurasi Automatic Retry & Quarantine di Playwright

```typescript
// playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  // Retry 2 kali hanya di CI, 0 kali di komputer lokal
  retries: process.env.CI ? 2 : 0,

  // Pisahkan reporter ke format Allure & HTML
  reporter: [
    ["list"],
    ["html", { open: "never" }],
    ["allure-playwright", { outputFolder: "allure-results" }]
  ],

  use: {
    // Rekam trace hanya saat terjadi percobaan ulang (Retry)
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure"
  }
});
```

---

## 7. Analogy
Bayangkan proses lepas landas pesawat terbang komersial:
- **Flaky Test**: Lampu sensor indikator pintu darurat di kokpit kadang berkedip kuning, lalu mati sendiri tanpa alasan. Jika pilot terbiasa menganggap *"Ah, sensor itu memang suka error sendiri"* (Mengabaikan flaky test), suatu hari pesawat akan terbang dengan pintu yang benar-benar tidak terkunci.
- **Test Quarantine**: Teknisi melepas sensor yang rusak tersebut, membawanya ke laboratorium kalibrasi untuk diperbaiki, dan memasang sensor cadangan terverifikasi sebelum pesawat diizinkan terbang.
- **Quality Gates (Go/No-Go)**: Pilot dan kopilot membaca buku checklist pra-penerbangan (*Pre-flight Checklist*). Jika salah satu butir keselamatan mutlak tidak terpenuhi (*No-Go Item*), pesawat **DILARANG LEPAS LANDAS**.

---

## 8. Diagram

```text
========================================================================================
                          ALLURE REPORT DASHBOARD VIEW
========================================================================================

  +----------------------------------------------------------------------------------+
  |  ALLURE EXECUTIVE OVERVIEW: RELEASE v3.8.0-RC1                                   |
  +----------------------------------------------------------------------------------+
  |  PASSED: 485 (97.0%)   |   FAILED: 2 (0.4%)   |   BROKEN: 1   |   SKIPPED: 12    |
  +----------------------------------------------------------------------------------+
  |  [DEFECT CATEGORIES]                                                             |
  |  * Product Defects: 2 (Assertion Failure: Expected 'Rp 50.000', got 'Rp 0')      |
  |  * Test Defects   : 1 (Network Timeout: 3rd party SMS gateway down)              |
  |                                                                                  |
  |  [BEHAVIOR / EPICS]                                                              |
  |  - Auth & Profile  : 100% Passed                                                 |
  |  - Checkout & Pay  : 95% Passed (2 Critical Bugs) <--- QUALITY GATE BLOCKED!     |
  +----------------------------------------------------------------------------------+
```

---

## 9. Simple Example: Implementasi Quality Gate Evaluator Sederhana

```javascript
class QualityGate {
  static evaluate({ openBugs, smokePassed, p95Latency, codeCoverage }) {
    const failures = [];

    // Gate 1: Zero S1 Bugs
    const criticalBugs = openBugs.filter(b => b.severity === "S1");
    if (criticalBugs.length > 0) {
      failures.push(`GATE FAILED: Ditemukan ${criticalBugs.length} bug berstatus S1 Critical!`);
    }

    // Gate 2: Smoke test 100%
    if (!smokePassed) {
      failures.push("GATE FAILED: Smoke test suite mengalami kegagalan!");
    }

    // Gate 3: Latency SLA <= 300ms
    if (p95Latency > 300) {
      failures.push(`GATE FAILED: Latensi p95 (${p95Latency}ms) melebihi batas toleransi 300ms!`);
    }

    // Gate 4: Coverage >= 80%
    if (codeCoverage < 80) {
      failures.push(`GATE FAILED: Code coverage (${codeCoverage}%) di bawah standar 80%!`);
    }

    return {
      isReadyForRelease: failures.length === 0,
      failures
    };
  }
}
```

---

## 10. Practical Example: Menghitung Flaky Test Rate

Metrik untuk mengukur kesehatan test suite perusahaan:

$$\text{Flaky Rate} = \left( \frac{\text{Jumlah Test yang Lolos Setelah Retry (Passed on Retry)}}{\text{Total Test yang Dijalankan}} \right) \times 100\%$$

- **Target Kualitas Kelas Dunia**: $\text{Flaky Rate} \le 1\%$.
- Jika $\text{Flaky Rate} > 5\%$, tim wajib menghentikan penambahan fitur baru selama 1 sprint dan mendedikasikan waktu khusus untuk stabilisasi test (*Test Stabilization Sprint*).

---

## 11. Real World Example: Bencana Pembatalan Rilis Akibat Flaky Test di Perusahaan Ride-Hailing
Sebuah platform ride-hailing besar di Asia Tenggara memiliki 3.000 test case otomasi:
- Flaky rate mencapai 12%. Setiap kali developer push kode baru, pipeline hampir selalu gagal merah.
- Karena terbiasa dengan kegagalan palsu, tim manajemen memutuskan: *"Matikan saja pemeriksaan otomatis di CI, lakukan merge langsung!"*.
- Dua hari kemudian, fitur baru merusak fungsi penentuan tarif dasar pengemudi. Penumpang dapat memesan perjalanan dari Jakarta ke Bandung (jarak 150 km) hanya dengan tarif Rp 10.000.
- Platform merugi miliaran rupiah dalam waktu 6 jam sebelum server dimatikan darurat.

---

## 12. Trade-offs

| Strategi Penanganan | Keuntungan | Kelemahan |
|---|---|---|
| **Auto-Retry Tanpa Karantina** | Cepat menutupi kegagalan sesaat di CI. | Menyamarkan bug balapan (*race condition bug*) asli di kode aplikasi. |
| **Pola Karantina (Quarantine)** | Pipeline CI tetap cepat dan stabil, status merah selalu berarti bug nyata. | Memerlukan disiplin manajemen tiket untuk memperbaiki tes yang dikarantina. |
| **Menghapus Test yang Flaky** | Instan membersihkan pipeline. | Menghilangkan jaring pengaman pengujian untuk fitur tersebut (*Test Coverage Loss*). |

---

## 13. When To Use
- Terapkan **Pola Karantina** segera setelah sebuah test case terdeteksi gagal lebih dari 2 kali berturut-turut tanpa ada perubahan kode.
- Terapkan **Quality Gates** terprogram sebagai syarat mutlak sebelum pemicu deployment otomatis ke lingkungan produksi.
- Gunakan **Allure Report** pada rapat retrospektif rilis untuk menyajikan transparansi kualitas kepada manajemen.

## 14. When NOT To Use
- Jangan menggunakan fitur Auto-Retry tanpa batas (misal `retries: 10`); ini adalah anti-pattern yang menyembunyikan arsitektur kode yang buruk dan melipatgandakan waktu eksekusi CI. Maksimal `retries: 2`.
- Jangan mengkarantina test case fungsional kritis (P0) tanpa persetujuan tertulis dari QA Lead dan Product Owner.

---

## 15. Common Mistakes

```text
1. MISTAKE: Menganggap Auto-Retry sebagai solusi permanen untuk Flaky Tests.
   WHY IT HAPPENS: Menambahkan 'retries: 3' membuat build CI kembali hijau.
   WHY IT IS BAD: Memperpanjang waktu eksekusi pipeline hingga 3x lipat dan membiarkan bug race condition laten tetap hidup di sistem.
   CORRECT APPROACH: Gunakan retry hanya sebagai peredam guncangan sementara; akar masalah timing wajib diperbaiki di sprint berikutnya.

2. MISTAKE: Quality Gate yang tidak dapat dipenuhi (Unrealistic Quality Gate).
   WHY IT HAPPENS: Manajemen menetapkan target 100% Statement Coverage pada legacy code berusia 10 tahun.
   WHY IT IS BAD: Developer terpaksa menulis unit test palsu tanpa assertion hanya demi mengejar angka metrik.
   CORRECT APPROACH: Tetapkan gerbang yang realistis dan naikkan ambang batas secara bertahap (misal 60% -> 70% -> 80%).
```

---

## 16. Best Practices

### Must Have
- Quality Gate terprogram yang memblokir merge PR jika ada tes yang gagal.
- Menyimpan bukti rekaman visual (*Trace Viewer*) pada setiap tes yang mengalami kegagalan atau retry di CI.

### Recommended
- Membuat dashboard pemantau tren Flaky Tests mingguan menggunakan Allure Report atau Datadog CI Visibility.
- Mengalokasikan kapasitas 10–15% waktu engineering di setiap sprint khusus untuk merawat dan menstabilkan skrip pengujian (*Test Tech Debt Paydown*).

### Advanced
- Menerapkan *Predictive Test Selection (Machine Learning)*: Memprediksi dan hanya menjalankan subset test yang memiliki probabilitas tertinggi gagal berdasarkan diff kode yang diubah di PR.

### Avoid / Overengineering
- Mengirimkan notifikasi tag darurat ke seluruh channel Slack perusahaan untuk kegagalan tes minor non-blocking.

---

## 17. Troubleshooting: Mendiagnosa Race Condition pada Pengujian UI
Jika test case lulus di komputer lokal yang cepat, tetapi sering gagal di server runner GitHub Actions yang lambat:
1. **Penyebab**: *Race Condition*. Mesin virtual cloud memiliki CPU lebih lambat, sehingga eksekusi kode backend atau animasi frontend membutuhkan waktu 100 ms lebih lama daripada di laptop developer.
2. **Solusi**:
   - Cari baris kode yang menggunakan timeout pendek manual.
   - Ganti selector dengan locator yang menunggu state eksplisit:
     `await expect(page.getByRole('button')).toBeEnabled();`

---

## 18. Exercise
1. Sebuah tim memiliki 500 test case otomasi:
   - 460 test lulus pada percobaan pertama.
   - 35 test gagal pada percobaan pertama, namun lulus pada percobaan kedua (*Passed on Retry*).
   - 5 test gagal permanen.
   Hitunglah nilai **Flaky Rate** dari test suite tersebut! Apakah angka tersebut memenuhi target kualitas kelas dunia ($\le 1\%$)?
2. Sebutkan 4 kriteria mutlak yang wajib masuk ke dalam checklist **Quality Gates** sebelum sebuah aplikasi perbankan diizinkan rilis ke produksi.

---

## 19. Challenge
Rancang sebuah **Sistem Gerbang Kualitas & Manajemen Karantina (Quality Gates Engine)**:
1. Rancang arsitektur klasifikasi status pengujian: `PASSED`, `FAILED`, `FLAKY` (Lolos setelah retry), dan `QUARANTINED`.
2. Tuliskan aturan evaluasi Go/No-Go Decision yang mengevaluasi input metrik (Severity defek, status smoke suite, latensi p95, dan jumlah tes yang dikarantina).
3. Buat skema notifikasi otomatis ke Slack yang memberitahukan tim pengembang jika build rilis dibatalkan (*Release Rejected*) lengkap dengan daftar kegagalan gate spesifik.

---

## 20. Summary
- Flaky Tests merusak kepercayaan tim terhadap otomasi dan membuka jalan bagi bug kritis untuk lolos ke produksi.
- Pola Karantina (Quarantine Pattern) mengisolasi tes tidak stabil dari pipeline utama tanpa mengorbankan kecepatan rilis.
- Pelaporan terstruktur (Allure Report) memberikan visibilitas objektif mengenai tren stabilitas kualitas perangkat lunak kepada seluruh pemangku kepentingan.
- Quality Gates menegakkan disiplin rekayasa objektif (*Go/No-Go Decision*) yang memastikan hanya build dengan standar kualitas tertinggi yang boleh menyentuh pengguna akhir.

---

## Hands-on Practice: Simulator Deteksi Flaky Tests & Evaluator Quality Gates
Jalankan script simulator yang mendeteksi perilaku flaky test, menerapkan kebijakan karantina otomatis, dan mengevaluasi gerbang kualitas rilis (Go/No-Go Release Decision):

```bash
node QA/BAB-10-CICD-Integration-Flaky-Test-dan-Quality-Gates/hands-on/m02/flaky_test_quarantine_gate_sim.js
```

---
[⬅️ Module 01: CI/CD Pipeline & Sharding](./Module-01-CI-CD-Testing-Pipeline-GitHub-Actions-Parallel-Sharding.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 10 ➡️](./BAB-10-Quiz-dan-Challenge.md)
---
