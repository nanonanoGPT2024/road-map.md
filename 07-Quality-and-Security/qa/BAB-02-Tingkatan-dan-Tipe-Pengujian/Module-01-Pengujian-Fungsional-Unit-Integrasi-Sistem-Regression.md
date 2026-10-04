---
[⬅️ BAB 01: Quiz & Challenge](../BAB-01-Fondasi-Software-Testing-dan-STLC/BAB-01-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Non-Functional Testing ➡️](./Module-02-Pengujian-Non-Fungsional-Security-Usability-A11y.md)
---

# Module 01: Pengujian Fungsional: Unit, Integrasi, Sistem, UAT, & Piramida Pengujian (Testing Pyramid)

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengidentifikasi dan membedakan 4 tingkatan pengujian fungsional standar: **Unit Testing**, **Integration Testing**, **System Testing**, dan **User Acceptance Testing (UAT)**.
- Menganalisis strategi pengujian integrasi: **Top-Down Integration** (menggunakan Stubs), **Bottom-Up Integration** (menggunakan Drivers), dan bahaya pendekatan **Big-Bang Integration**.
- Membandingkan model arsitektur pengujian: **Testing Pyramid (Mike Cohn)**, **Testing Trophy (Kent C. Dodds)**, dan anti-pattern berbahaya **Testing Ice Cream Cone / Inverted Pyramid**.
- Membedakan secara presisi antara **Smoke Testing** (Build Verification), **Sanity Testing** (Quick Check setelah bug fix), **Regression Testing**, dan **Re-testing**.
- Menyusun strategi pemilihan test suite regresi menggunakan teknik *Risk-Based Regression* dan *Impact Analysis*.

---

## 2. Prerequisite
- Memahami konsep dasar verification vs validation dari BAB 01.
- Pemahaman dasar tentang struktur kode aplikasi (fungsi, komponen, API service, database).

---

## 3. Concept
Dalam rekayasa kualitas perangkat lunak, sebuah aplikasi tidak diuji sekaligus sebagai satu bongkahan raksasa yang utuh. Pendekatan modular membagi pengujian ke dalam **Tingkatan Pengujian (Levels of Testing)** yang selaras dengan hierarki arsitektur perangkat lunak:
1. Menguji fungsi atau unit kode terkecil secara terisolasi (**Unit Testing**).
2. Menguji antarmuka dan komunikasi antar-modul atau antar-layanan (**Integration Testing**).
3. Menguji seluruh sistem terintegrasi dari ujung ke ujung (*end-to-end*) sesuai kebutuhan bisnis (**System Testing**).
4. Menyerahkan sistem kepada pengguna akhir atau pemangku kepentingan untuk memvalidasi kesiapan operasional (**Acceptance Testing / UAT**).

Distribusi volume pengujian di antara tingkatan ini diatur oleh **Piramida Pengujian (Testing Pyramid)** demi mencapai efisiensi biaya eksekusi dan kecepatan umpan balik (*fast feedback loop*).

---

## 4. Why?
Mengapa kita membutuhkan tingkatan pengujian dan piramida pengujian?
1. **Kecepatan Umpan Balik (Feedback Loop)**: Unit test dapat mengeksekusi ribuan skenario dalam hitungan detik. Jika Anda hanya mengandalkan pengujian manual atau E2E UI testing, satu siklus pengujian bisa memakan waktu berjam-jam atau berhari-hari.
2. **Presisi Lokasi Akar Masalah (Root Cause Pinpointing)**: Ketika unit test gagal, developer langsung mengetahui baris kode dan fungsi mana yang rusak. Ketika tes E2E UI gagal, penyebabnya bisa puluhan kemungkinan: bug UI, API down, database timeout, jaringan lambat, atau salah konfigurasi environment.
3. **Biaya Pemeliharaan (Maintenance Cost)**: Tes antarmuka (UI) sangat rentan terhadap perubahan kecil pada selector HTML/CSS (*flaky tests*), sedangkan unit test dan contract test jauh lebih stabil dan tahan lama.

---

## 5. What?

### A. 4 Tingkatan Pengujian (Levels of Testing)

```text
+-------------------------------------------------------------------------+
| Level 4: ACCEPTANCE TESTING (UAT / Alpha / Beta)                       |
| Fokus: Kesiapan operasional bisnis & kepuasan pengguna akhir.          |
+-------------------------------------------------------------------------+
| Level 3: SYSTEM TESTING (End-to-End Testing)                           |
| Fokus: Memverifikasi sistem lengkap (Frontend + Backend + DB + 3rd Party)|
+-------------------------------------------------------------------------+
| Level 2: INTEGRATION TESTING                                           |
| Fokus: Protokol komunikasi & kontrak data antar modul/komponen/API.    |
+-------------------------------------------------------------------------+
| Level 1: UNIT TESTING                                                  |
| Fokus: Logika murni fungsi, method, atau class terisolasi.             |
+-------------------------------------------------------------------------+
```

1. **Unit Testing**:
   - Diuji oleh: Software Engineer / Developer.
   - Karakteristik: Menggunakan test double (*mocks, stubs, spies*) untuk memutus ketergantungan eksternal (database, network, file system).
   - Sasaran: Algoritma perhitungan, validasi regex, percabangan *if-else*, state manipulation murni.
2. **Integration Testing**:
   - Diuji oleh: Developer & QA Engineer.
   - Karakteristik: Menghubungkan 2 atau lebih modul nyata.
   - Jenis strategi:
     - **Big Bang**: Semua modul digabung sekaligus lalu diuji bersamaan (*Sangat berbahaya karena sulit melacak modul mana yang salah*).
     - **Top-Down**: Pengujian dimulai dari modul tingkat atas (UI/Controller) ke bawah, modul tingkat bawah disimulasikan menggunakan **Stubs**.
     - **Bottom-Up**: Pengujian dimulai dari modul tingkat bawah (Data Access Layer) ke atas, dipanggil oleh modul penguji buatan yang disebut **Drivers**.
3. **System Testing (E2E)**:
   - Diuji oleh: QA Engineer / SDET.
   - Karakteristik: Lingkungan uji mendekati produksi (*Staging/Pre-production*). Menguji alur bisnis lengkap (misal: registrasi -> verifikasi email -> belanja -> pembayaran -> pengiriman resi).
4. **User Acceptance Testing (UAT)**:
   - Diuji oleh: Product Owner, Klien Bisnis, atau Pengguna Nyata.
   - **Alpha Testing**: Dilakukan oleh stakeholder internal di lingkungan pengembang.
   - **Beta Testing**: Dirilis secara terbatas ke sekelompok pengguna riil di luar organisasi.

---

### B. Perbedaan Kritis: Smoke vs Sanity vs Regression vs Retesting

Tabel ini merangkum terminologi yang paling sering membingungkan dan ditanyakan dalam interview teknis QA:

| Aspek | Smoke Testing | Sanity Testing | Re-testing | Regression Testing |
|---|---|---|---|---|
| **Kapan Dijalankan?** | Setiap kali ada **Build Baru** dari CI/CD. | Setelah ada **Bug Fix** atau perubahan kecil. | Khusus setelah developer menyatakan bug tertentu sudah di-fix. | Setelah ada perubahan kode baru untuk memastikan fitur lama tidak rusak. |
| **Tujuan Utama** | Memverifikasi apakah build cukup stabil untuk diuji lebih lanjut (*Build Verification*). | Memverifikasi apakah perbaikan bug bekerja secara rasional (*Rationality Check*). | Memverifikasi apakah bug spesifik yang dilaporkan benar-benar hilang. | Memastikan tidak ada efek samping / dampak regresi pada modul lain. |
| **Cakupan Pengujian** | Sangat dangkal, namun mencakup alur paling kritis secara lebar (*Shallow & Wide*). | Fokus mendalam pada modul yang baru diperbaiki (*Narrow & Deep*). | Hanya pada skenario / test case spesifik yang sebelumnya gagal. | Menjalankan subset atau seluruh test suite terdahulu (*Comprehensive*). |
| **Otomasi** | Sangat disarankan otomatis di CI pipeline (waktu jalan < 5 menit). | Biasanya manual atau scripted test ringan. | Biasanya manual saat retest tiket. | Wajib diotomasi (Regression Suite). |

---

## 6. How? Piramida Pengujian vs Anti-Pattern

### 1. The Ideal Testing Pyramid (Mike Cohn)
Model piramida merekomendasikan:
- **70% Unit Tests**: Dasar piramida yang sangat lebar. Cepat, murah, stabil.
- **20% Integration / Service Tests**: Lapisan tengah. Menguji API contracts, query database, antarmuka service.
- **10% E2E UI Tests**: Puncak piramida yang kecil. Menguji hanya alur bisnis pengguna yang paling kritis (*happy paths*).

### 2. The Testing Trophy (Kent C. Dodds)
Populer di ekosistem web modern (Frontend/Node.js):
- **Static Analysis (TypeScript, ESLint)**: Menangkap typo dan syntax error sebelum kode dijalankan.
- **Unit Tests**: Menguji logika bisnis murni.
- **Integration Tests (Porsi Terbesar)**: Menguji interaksi komponen UI dengan hook/state atau API endpoint dengan database nyata. Memberikan *Return on Investment (ROI)* tertinggi.
- **End-to-End Tests**: Memverifikasi alur kritis sistem secara utuh.

### 3. The Ice Cream Cone Anti-Pattern (Inverted Pyramid)
Sebuah pola kegagalan fatal yang umum terjadi di organisasi dengan kematangan QA rendah:
- **0–10% Unit Tests**: Developer malas menulis unit test, koding buru-buru.
- **20% Integration Tests**: Sedikit pengujian API.
- **70–80% Manual & E2E UI Tests**: QA dipaksa mengklik ratusan halaman manual setiap sprint.
- **Akibat**: Rilis menjadi sangat lambat, regresi sering lolos ke produksi, tes otomasi UI terus-menerus gagal palsu (*flaky*), dan biaya QA membengkak.

---

## 7. Analogy
Bayangkan proses perakitan mobil balap Formula 1:
- **Unit Testing**: Menguji busi, piston, dan injector bahan bakar secara terpisah di laboratorium uji mesin. Memastikan setiap komponen kecil tahan panas dan memercikkan api tepat waktu.
- **Integration Testing**: Memasang piston ke dalam blok silinder dan menghubungkannya dengan transmisi girboks. Memastikan girboks menerima putaran mesin tanpa macet.
- **System Testing**: Memasang seluruh bodi mobil, ban, kemudi, dan sistem aerodinamika. Mobil dinyalakan dan dikemudikan di sirkuit privat oleh insinyur penguji.
- **UAT**: Pembalap F1 utama (seperti Max Verstappen) mencoba mobil tersebut di lintasan balap dan memberikan persetujuan akhir apakah pedal rem dan ergonomi kokpit sudah sesuai preferensinya sebelum balapan resmi dimulai.

---

## 8. Diagram

```text
========================================================================================
                          MODEL DISTRIBUSI PENGUJIAN
========================================================================================

    [ IDEAL: TESTING PYRAMID ]                    [ ANTI-PATTERN: ICE CREAM CONE ]
    
              / \                                        +---------------+
             /   \                                       |   Manual &    |  <-- Lambat, Mahal,
            / UI  \    <-- Sedikit (10%)                 |    E2E UI     |      Flaky, Sering
           /-------\                                     \  Testing (70%) /     Bottleneck
          / Integr- \                                     \-------------/
         /   ation   \  <-- Sedang (20%)                   \ Integration /
        /-------------\                                     \   (20%)   /
       /     Unit      \                                     \---------/
      /  Testing (70%)  \ <-- Terbanyak, Cepat, Murah         \ Unit /   <-- Developer Tidak
     +-------------------+                                     \-----/       Menulis Test

========================================================================================
                      STRATEGI INTEGRATION TESTING: STUB VS DRIVER
========================================================================================

      TOP-DOWN INTEGRATION                              BOTTOM-UP INTEGRATION
      
      [ Order Controller ] (Aktif)                      [ Test Driver ] (Penguji Buatan)
              |                                                |
      +-------+-------+                                        v
      |               |                               [ Payment Service ] (Aktif)
      v               v                                        |
 [ Payment ]     [ Inventory ]                                 v
   (STUB)          (STUB)                             [ Database Repository ] (Aktif)
      
 * Stub: Objek tiruan untuk                         * Driver: Modul tiruan untuk
   mensimulasikan modul bawahan.                       memanggil modul bawahan yang sedang diuji.
```

---

## 9. Simple Example: Perbandingan Kode Unit Test vs Integration Test

### Target Logic: Transfer Dana Perbankan
```javascript
// Unit Test: Menguji validasi logika murni akun (tanpa memanggil DB nyata)
function testWithdrawalPureLogic() {
  const account = { balance: 100000 };
  const amountToWithdraw = 40000;
  
  // Logic
  if (amountToWithdraw > account.balance) throw new Error("INSUFFICIENT_FUNDS");
  account.balance -= amountToWithdraw;
  
  // Assertion
  if (account.balance !== 60000) throw new Error("Unit test failed: Balance mismatch!");
  console.log("✓ Unit Test: Pengurangan saldo kalkulasi matematis VALID.");
}

// Integration Test: Menguji koordinasi antara AccountService dan DB Transaction Session
async function testWithdrawalIntegration(dbConnectionPool) {
  const session = await dbConnectionPool.startSession();
  try {
    session.startTransaction();
    // Memverifikasi bahwa query SQL, lock baris database, dan log audit benar-benar tersimpan
    await dbConnectionPool.query("UPDATE accounts SET balance = balance - $1 WHERE id = $2", [40000, "ACC-01"], { session });
    await dbConnectionPool.query("INSERT INTO audit_logs (event, amount) VALUES ($1, $2)", ["WITHDRAWAL", 40000], { session });
    await session.commitTransaction();
    console.log("✓ Integration Test: Transaksi ACID akun + audit log database VALID.");
  } catch (err) {
    await session.abortTransaction();
    throw err;
  }
}
```

---

## 10. Practical Example: Menyusun Checklist Smoke Testing untuk E-Commerce

Sebelum tim QA memulai pengujian mendalam pada build baru, checklist Smoke Test ini dieksekusi (durasi maksimal 10 menit):

```markdown
# Smoke Test Checklist: Build v3.8.0-rc1

1. [ ] Server Health Check:
   - Request `GET /healthz` merespons HTTP 200 OK dengan status "UP".
2. [ ] Autentikasi Pengguna:
   - Login dengan akun penguji `tester@demo.com` berhasil dan mendapatkan token JWT.
   - Logout berhasil dan token di-revoke.
3. [ ] Katalog & Pencarian Produk:
   - Halaman katalog utama menampilkan produk unggulan tanpa error 500.
   - Pencarian dengan kata kunci "sepatu" menghasilkan minimal 1 produk.
4. [ ] Keranjang & Checkout (Alur Kritis Transaksi):
   - Menambahkan produk ke keranjang belanja berhasil.
   - Halaman checkout memuat nominal total secara akurat.
5. [ ] Payment Gateway Mock:
   - Memilih metode sandbox Virtual Account menghasilkan nomor VA 16 digit.

*Kriteria Keputusan:*
- Jika 5/5 checklist PASS -> **BUILD ACCEPTED** (QA memulai pengujian fungsional & regresi).
- Jika ada 1 saja checklist FAIL -> **BUILD REJECTED** (Build dikembalikan ke developer, QA berhenti menguji).
```

---

## 11. Real World Example: Kegagalan Rilis Maskapai Penerbangan akibat Ice Cream Cone
Sebuah maskapai penerbangan internasional melakukan migrasi sistem reservasi tiket:
- Tim QA tidak memiliki unit test dan hanya mengandalkan 400 skenario automated Selenium UI test.
- Setiap kali tim developer merilis perubahan styling tombol (*CSS fix*), 60% skenario Selenium gagal karena elemen locator berubah (*selector flakiness*).
- Karena terbiasa melihat test gagal palsu, tim mengabaikan 1 skenario gagal: *"Kalkulasi Kurs Mata Uang Asing"*.
- Di hari peluncuran, pengguna dapat membeli tiket penerbangan London – Tokyo (senilai £1.200) hanya dengan membayar 1.200 Yen (sekitar £6). Kerugian mencapai jutaan poundsterling dalam 4 jam sebelum sistem dimatikan darurat.

---

## 12. Trade-offs

| Tingkatan Pengujian | Biaya Pembuatan | Kecepatan Eksekusi | Keandalan (Flakiness) | Tingkat Kepercayaan Bisnis |
|---|---|---|---|---|
| **Unit Test** | Sangat Rendah | Sangat Cepat (< 1 ms per test) | Sangat Andal (0% Flakiness) | Rendah (Hanya menguji komponen terisolasi) |
| **Integration Test** | Sedang | Cepat (10–100 ms per test) | Tinggi (Jarang Flaky) | Tinggi (Menguji integrasi nyata modul/API) |
| **System E2E Test** | Tinggi | Lambat (2–30 detik per test) | Rentan Flaky (Browser/Network) | Sangat Tinggi (Menguji real user journey) |
| **Manual UAT** | Sangat Tinggi (SDM) | Sangat Lambat (Hari/Minggu) | Tergantung Human Error | Mutlak (Keputusan Go/No-Go Stakeholder) |

---

## 13. When To Use
- Gunakan **Unit Testing** pada seluruh *business logic*, algoritma perhitungan, fungsi pembantu (*utils*), dan parser data.
- Gunakan **Smoke Testing** otomatis sebagai *quality gate* wajib di setiap merge request atau deployment CI/CD.
- Gunakan **Sanity Testing** ketika developer mengirimkan patch darurat (*hotfix*) yang hanya menyentuh satu fungsi spesifik.
- Gunakan **Risk-Based Regression Testing** menjelang rilis mingguan dengan memprioritaskan skenario P0 (transaksi inti, autentikasi, pembayaran).

## 14. When NOT To Use
- Jangan membuat pengujian E2E UI untuk memverifikasi 50 kombinasi format validasi nomor HP atau email. Serahkan 50 skenario tersebut ke **Unit Testing**; uji hanya 1 skenario sukses dan 1 skenario gagal di level UI.
- Jangan menjalankan pengujian regresi penuh (*Full Regression Suite* 1.000 test case) untuk perbaikan 1 huruf typo di footer. Cukup jalankan Sanity Test.

---

## 15. Common Mistakes

```text
1. MISTAKE: Mengabaikan Unit Test dan hanya mengandalkan E2E Testing (Ice Cream Cone).
   WHY IT HAPPENS: Manajemen menganggap "yang dilihat user adalah UI, jadi uji UI saja".
   WHY IT IS BAD: Eksekusi memakan waktu berjam-jam, pipeline CI/CD sering macet, tim frustrasi akibat tes flaky.
   CORRECT APPROACH: Investasikan 70% waktu pada Unit & Integration test, batasi E2E UI hanya untuk happy path terpenting.

2. MISTAKE: Mengira Re-testing dan Regression Testing adalah hal yang sama.
   WHY IT HAPPENS: Kurangnya pemahaman konsep dasar STLC.
   WHY IT IS BAD: QA hanya menguji bug yang diperbaiki (Re-testing) dan lupa menguji modul sekitarnya (Regression), sehingga bug efek samping lolos ke produksi.
   CORRECT APPROACH: Lakukan Re-testing terlebih dahulu; jika lolos, lanjutkan dengan Regression Testing pada modul terdampak.
```

---

## 16. Best Practices

### Must Have
- **Automated Smoke Test** yang memblokir build rusak (*Broken Build*) dalam waktu maksimal 5 menit di CI/CD.
- *Test Pyramid mindset* di seluruh tim: developer wajib menyertakan unit test pada setiap Pull Request.

### Recommended
- Membuat **Impact Matrix**: Ketika developer mengubah modul X, matriks ini secara otomatis memberitahu QA daftar modul Y dan Z yang wajib diuji dalam Regression Suite.
- Menggunakan *Contract Testing* (misal: Pact) pada lapisan Integration Test antar-microservices untuk menggantikan kebutuhan E2E test yang berat.

### Advanced
- Menerapkan *Test Impact Analysis (TIA)*: Tool cerdas yang menganalisis commit Git dan hanya menjalankan unit/integration test yang kodenya terdampak langsung, menghemat 80% waktu testing di CI pipeline.

### Avoid / Overengineering
- Menguji third-party library bawaan (misalnya menguji apakah fungsi `Array.prototype.sort()` milik JavaScript bekerja dengan benar). Uji logika Anda, bukan library vendor.

---

## 17. Troubleshooting: Mengatasi Flaky Tests di Tingkat System/E2E
Jika pengujian E2E sering gagal palsu tanpa ada perubahan kode:
1. **Penyebab: Hardcoded Sleep / Wait**: Menggunakan `sleep(5000)` alih-alih *Explicit Conditional Wait* (menunggu elemen muncul di DOM).
2. **Penyebab: Test Data State Pollution**: Test case B bergantung pada data yang dibuat oleh test case A. Jalankan setiap test secara terisolasi dengan data fixture mandiri (*independent tests*).
3. **Penyebab: Fluktuasi Jaringan / 3rd Party API**: Mocking service eksternal yang tidak stabil saat menjalankan pengujian UI fungsional.

---

## 18. Exercise
1. Sebuah tim mengembangkan sistem perpustakaan digital:
   - Identifikasi dan klasifikasikan 4 skenario berikut ke dalam tingkatan yang tepat (Unit, Integration, System, atau UAT):
     - Skenario A: Memverifikasi bahwa denda dihitung Rp 2.000 per hari keterlambatan menggunakan fungsi `calculateFine(daysOverdue)`.
     - Skenario B: Memverifikasi bahwa antarmuka sistem terhubung dengan gateway notifikasi WhatsApp untuk mengirimkan pengingat jatuh tempo.
     - Skenario C: Petugas perpustakaan menguji proses sirkulasi peminjaman buku menggunakan scanner barcode fisik di meja layanan untuk memastikan kenyamanan kerja sehari-hari.
     - Skenario D: Menguji seluruh alur dari pencarian buku di katalog web, reservasi buku, pembayaran denda via QRIS, hingga status buku berubah menjadi dipinjam.

---

## 19. Challenge
Rancang sebuah **Regression Test Strategy** untuk aplikasi dompet digital (*E-Wallet*) yang baru saja mengubah penyedia payment gateway dari Provider X ke Provider Y.
1. Tentukan modul apa saja yang masuk ke dalam *High Risk Impact*.
2. Pilih 5 skenario P0 mutlak yang wajib masuk ke dalam Regression Suite.
3. Tentukan bagaimana Anda memverifikasi backward-compatibility terhadap riwayat transaksi masa lalu yang diproses oleh Provider X.

---

## 20. Summary
- Pengujian fungsional dibagi menjadi 4 level: Unit, Integration, System, dan UAT.
- Piramida Pengujian adalah pedoman distribusi: bangun pondasi kokoh dengan Unit Test cepat, perkuat dengan Integration Test, dan batasi E2E Test pada alur kritis bisnis.
- Smoke Testing memvalidasi stabilitas build secara cepat, Sanity Testing memvalidasi perbaikan secara terfokus, Re-testing memvalidasi bug spesifik, dan Regression Testing menjaga kestabilan sistem keseluruhan dari efek samping.

---

## Hands-on Practice: Simulator Piramida Pengujian & Smoke/Sanity Runner
Jalankan simulator pengujian modular yang mendemonstrasikan eksekusi Unit Test, Integration Test dengan Mock/Stub, System Test, serta Smoke Test gatekeeper:

```bash
node QA/BAB-02-Tingkatan-dan-Tipe-Pengujian/hands-on/m01/testing_pyramid_runner_sim.js
```

---
[⬅️ BAB 01: Quiz & Challenge](../BAB-01-Fondasi-Software-Testing-dan-STLC/BAB-01-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Non-Functional Testing ➡️](./Module-02-Pengujian-Non-Fungsional-Security-Usability-A11y.md)
---
