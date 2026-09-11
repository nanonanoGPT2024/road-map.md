---
[⬅️ Module 01: Prinsip Dasar Testing](./Module-01-Prinsip-Dasar-Testing-Verification-vs-Validation.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 01 ➡️](./BAB-01-Quiz-dan-Challenge.md)
---

# Module 02: SDLC, STLC, & Bug / Defect Lifecycle Management

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami hubungan simbiotik antara **Software Development Life Cycle (SDLC)** dan **Software Testing Life Cycle (STLC)** dalam berbagai metodologi rekayasa (Waterfall, V-Model, Scrum/Agile, Kanban).
- Membedakan setiap fase kritis dalam STLC: *Requirement Analysis, Test Planning, Test Case Design & Development, Test Environment Setup, Test Execution,* dan *Test Cycle Closure*.
- Memahami anatomi dan komponen standar industri dari **Test Plan Document** (IEEE 829 standard) dan **Test Strategy**.
- Menguasai State Machine dari **Bug / Defect Life Cycle** (dari status `New`, `Assigned`, `Open`, `Fixed`, `Retest`, `Verified`, `Closed`, hingga penanganan `Rejected`, `Deferred`, dan `Duplicate`).
- Menulis **Bug Report** berstandar profesional yang komprehensif, reproduktif, dan actionable (Severity vs Priority, Steps to Reproduce, Expected vs Actual Behavior, Environment & Artifact logs).
- Menerapkan metrik kualitas dasar: *Defect Density, Defect Leakage, Defect Removal Efficiency (DRE),* dan *Test Execution Velocity*.

---

## 2. Prerequisite
- Memahami konsep dasar testing, perbedaan verification vs validation, serta 7 prinsip testing dari Module 01.
- Pemahaman umum tentang alur kerja tim rekayasa software modern (Developer, Product Manager, QA, DevOps).

---

## 3. Concept
Dalam ekosistem rekayasa perangkat lunak modern, pengujian bukan sekadar fase acak di mana seorang QA mengklik antarmuka aplikasi secara bebas (*ad-hoc testing*). Pengujian adalah proses terstruktur, terukur, dan berulang yang memiliki siklus hidup sendiri yang disebut **Software Testing Life Cycle (STLC)**. 

STLC berjalan paralel dan terintegrasi dengan **Software Development Life Cycle (SDLC)**. Setiap kali ditemukan deviasi antara perilaku sistem aktual dan spesifikasi kebutuhan, sebuah anomali dicatat sebagai **Defect / Bug**. Pengelolaan cacat ini dikendalikan oleh **Bug Life Cycle State Machine**, yang memastikan tidak ada satupun cacat yang terlewat, diabaikan, atau ditutup tanpa pembuktian verifikasi (*re-testing* & *regression testing*).

---

## 4. Why?
Mengapa STLC dan Defect Life Cycle yang formal sangat dibutuhkan?
1. **Mencegah *"Ping-Pong Communication"***: Tanpa status defect yang jelas, developer dan QA saling melempar tuduhan mengenai apakah suatu isu sudah selesai diperbaiki atau belum.
2. **Keterlacakan (Traceability)**: Menghubungkan setiap kebutuhan bisnis (*User Story*) dengan Test Case dan Bug Report terkait melalui *Requirements Traceability Matrix (RTM)*.
3. **Penyelarasan Ekspektasi & Jadwal**: Tanpa Test Plan yang jelas, tim manajemen proyek tidak akan tahu kapan fase testing selesai (*Exit Criteria*) dan apakah sistem sudah layak rilis (*Production Readiness*).
4. **Efisiensi Debugging Developer**: Laporan bug yang ditulis dengan format standar memangkas waktu investigasi developer hingga 70%, karena menyertakan langkah reproduksi yang presisi, screenshot, network log, dan environment ID.

---

## 5. What?

### A. Perbandingan SDLC vs STLC
- **SDLC (Software Development Life Cycle)**: Kerangka kerja holistik yang mendefinisikan tahapan pembuatan perangkat lunak dari inisiasi ide, pengumpulan kebutuhan, arsitektur, koding, pengujian, rilis, hingga pemeliharaan.
- **STLC (Software Testing Life Cycle)**: Rangkaian aktivitas spesifik yang dieksekusi secara sistematis untuk menjamin dan memverifikasi kualitas perangkat lunak yang sedang dikembangkan dalam SDLC.

### B. Tahapan dalam STLC
1. **Requirement Analysis**: QA menganalisis dokumen kebutuhan (BRD/PRD/User Story) untuk mengidentifikasi skenario yang dapat diuji (*testable requirements*) dan mendeteksi ambiguitas sedini mungkin.
2. **Test Planning**: QA Lead merumuskan dokumen Test Plan: ruang lingkup (*scope*), estimasi waktu, alokasi sumber daya, strategi pengujian, dan kriteria masuk/keluar (*Entry/Exit Criteria*).
3. **Test Design & Development**: QA merinci skenario menjadi Test Cases, Test Scripts, dan menyiapkan data uji (*Test Data*).
4. **Test Environment Setup**: Penyiapan server staging/testing, database mock, konfigurasi jaringan, dan kredensial uji.
5. **Test Execution**: QA mengeksekusi test cases, membandingkan *Expected Result* dengan *Actual Result*, dan mencatat bug jika ditemukan deviasi.
6. **Test Cycle Closure**: Analisis metrik pengujian, penyusunan *Test Summary Report*, evaluasi defect leakage, dan sesi retrospektif.

### C. Anatomi Defect Life Cycle (State Machine)
Sebuah defect bergerak melintasi serangkaian status:
- **New**: Bug baru pertama kali dicatat oleh QA.
- **Assigned**: Bug ditugaskan kepada Tech Lead atau Developer yang relevan.
- **Open**: Developer mulai menganalisis dan mereproduksi bug.
- **Rejected**: Developer menolak bug karena perilaku tersebut sesuai spesifikasi (bukan bug).
- **Deferred / Postponed**: Bug diakui nyata, namun prioritasnya rendah sehingga ditunda untuk sprint berikutnya.
- **Duplicate**: Bug serupa sudah dicatat dalam tiket lain.
- **Fixed**: Developer telah mengubah kode dan memverifikasi perbaikan di lokal.
- **Pending Retest**: Kode perbaikan telah di-deploy ke environment testing.
- **Retest**: QA menguji ulang skenario spesifik yang sebelumnya gagal.
- **Verified**: QA mengonfirmasi bug benar-benar hilang pada build terbaru.
- **Reopened**: Bug masih terjadi saat retest, atau menimbulkan regresi baru.
- **Closed**: Bug diverifikasi tuntas dan tidak lagi aktif.

---

## 6. How?

### Matriks Klasifikasi: Severity vs Priority
Salah satu keterampilan utama QA adalah membedakan antara tingkat keparahan teknis (**Severity**) dan urgensi bisnis (**Priority**).

| Kategori | Definisi | Ditentukan Oleh Siapa? | Contoh Kasus |
|---|---|---|---|
| **Severity (Tingkat Keparahan)** | Dampak teknis bug terhadap operasional sistem (Crash, Data Loss, Block). | QA Engineer / System Architect | Crash database saat batch update malam hari (Critical Severity). |
| **Priority (Tingkat Urgensi)** | Seberapa cepat bug harus diselesaikan berdasarkan dampak bisnis atau timeline rilis. | Product Manager / Product Owner bersama QA Lead | Logo perusahaan salah eja di halaman muka saat peluncuran kampanye nasional (High Priority, Low Severity). |

#### Kuadran Kombinasi Severity vs Priority:
1. **High Severity & High Priority**: Payment gateway melempar error 500 saat checkout; pengguna tidak bisa belanja. *Tindakan: Hotfix instan.*
2. **High Severity & Low Priority**: Fitur ekspor laporan tahunan 10 tahun lalu menyebabkan memory leak dan server crash, namun fitur ini hanya diakses 1 kali setahun oleh admin internal. *Tindakan: Perbaiki pada sprint terjadwal.*
3. **Low Severity & High Priority**: Salah ketik nama CEO atau brand perusahaan di landing page utama. Secara teknis tidak ada sistem rusak, tapi merusak reputasi publik. *Tindakan: Perbaiki segera sebelum kampanye rilis.*
4. **Low Severity & Low Priority**: Warna border tombol di halaman FAQ sedikit tidak sejajar sejauh 1 piksel pada browser Safari versi lawas. *Tindakan: Backlog prioritas rendah.*

---

## 7. Analogy
Bayangkan proses pembangunan gedung apartemen bertingkat:
- **SDLC**: Seluruh proyek dari arsitek menggambar denah, tukang cor memasang tiang pancang, tukang pipa memasang sanitasi, hingga serah terima kunci ke penghuni.
- **STLC**: Tim inspeksi keselamatan bangunan. Mereka tidak ikut mengecor semen, tetapi mereka memeriksa blueprint sebelum cor dibuat (*Requirement Review*), menyiapkan sensor getaran (*Test Setup*), menguji tekanan air pada pipa (*Execution*), dan memberikan sertifikat layak huni (*Test Closure*).
- **Bug Life Cycle**: Ketika inspektur menemukan pipa bocor (*New*), kontraktor pipa dipanggil (*Assigned*), pipa diganti (*Fixed*), inspektur memompa air kembali (*Retest*), dan jika kering maka segel aman diberikan (*Closed*).

---

## 8. Diagram

```text
========================================================================================
                          SOFTWARE TESTING LIFE CYCLE (STLC)
========================================================================================

 [1. Requirement]    [2. Test Planning]    [3. Test Design]    [4. Env Setup]
  - BRD/PRD Review    - Scope & Strategy    - Test Cases        - Server Staging
  - Traceability      - Effort Estimation   - Test Data Prep    - DB Seeding
         |                    |                    |                   |
         +--------------------+--------------------+-------------------+
                                       |
                                       v
                             [5. Test Execution] <---------------+
                              - Run Test Cases                   |
                              - Log Defects                      |
                                       |                         | Retest (Build Baru)
                                       v                         |
                               [Defect Ditemukan]                |
                                       |                         |
                                       v                         |
                             [6. Bug Life Cycle] ----------------+
                                       |
                              (Semua Exit Criteria Terpenuhi)
                                       v
                            [7. Test Cycle Closure]
                              - Test Summary Report
                              - Defect Metrics Analysis
                              - Retrospective & Sign-off

========================================================================================
                          BUG / DEFECT LIFE CYCLE STATE MACHINE
========================================================================================

                 +--------------+
                 |     NEW      |  (QA melaporkan bug)
                 +-------+------+
                         |
                         v
                 +--------------+
                 |   ASSIGNED   |  (Tech Lead menugaskan ke Dev)
                 +-------+------+
                         |
           +-------------+-------------+
           |             |             |
           v             v             v
     +-----------+ +-----------+ +-----------+
     | REJECTED  | | DEFERRED  | | DUPLICATE |  (Status Terminasi Alternatif)
     +-----------+ +-----------+ +-----------+
           |
           v
     +-----------+
     |   OPEN    | (Developer menginvestigasi)
     +-----+-----+
           |
           v
     +-----------+
     |   FIXED   | (Developer submit PR perbaikan)
     +-----+-----+
           |
           v
     +---------------+
     |PENDING RETEST | (Build baru di-deploy ke staging)
     +-------+-------+
             |
             v
       +-----------+
       |  RETEST   | (QA menguji ulang skenario)
       +-----+-----+
             |
       +-----+-----------------+
       |                       |
(Masih Rusak)             (Lulus Uji)
       v                       v
 +------------+         +-------------+
 |  REOPENED  |         |  VERIFIED   |
 +-----+------+         +------+------+
       |                       |
       +---> (Kembali ke Open) v
                        +-------------+
                        |   CLOSED    |
                        +-------------+
```

---

## 9. Simple Example: Format Standar Tiket Bug Report

Berikut adalah template standar industri penulisan tiket defect (misalnya pada Jira, Linear, atau GitHub Issues):

```markdown
Title: [Checkout][Voucher] Diskon 50% tidak memotong tagihan saat pembayaran VA BCA

Issue Details:
- Project: E-Commerce Web Platform
- Component: Checkout / Payment Gateway
- Environment: Staging (v2.4.1-rc3), Chrome 128 (macOS Sonoma 14.5)
- Severity: S1 - Critical (Transaksi nominal salah)
- Priority: P1 - Blocker (Menahan rilis promo tanggal kembar)
- Reporter: Sarah (QA Engineer)
- Assignee: Dimas (Backend Engineer)

Pre-conditions:
1. Akun pengguna terdaftar dan memiliki keranjang belanja senilai Rp 100.000.
2. Kode voucher "HEMAT50" aktif di database dengan diskon 50% (maks. potongan Rp 50.000).

Steps to Reproduce (STR):
1. Masuk ke halaman cart (URL: https://staging.shop.com/cart).
2. Klik tombol "Gunakan Promo" dan masukkan kode "HEMAT50".
3. Pastikan ringkasan belanja menampilkan diskon -Rp 50.000 dan total Rp 50.000.
4. Klik tombol "Lanjut ke Pembayaran".
5. Pilih metode pembayaran "BCA Virtual Account".
6. Klik tombol "Bayar Sekarang".

Expected Result:
Modal pembayaran BCA VA menampilkan tagihan senilai Rp 50.000 (sesuai nilai diskon).

Actual Result:
Modal pembayaran BCA VA menampilkan tagihan penuh sebesar Rp 100.000. Diskon hilang saat payload dikirim ke API payment gateway.

Evidence / Attachments:
- Screenshot: cart_discount_applied.png
- Network Har Log: checkout_post_request.har (Payload: subtotal=100000, voucherCode="", total=100000)
- Console Error: payment.js:142 "TypeError: Cannot read properties of undefined (reading 'finalPrice')"
```

---

## 10. Practical Example: Menghitung Metrik Kualitas (Defect Metrics)

Sebagai QA profesional, Anda tidak hanya melaporkan bug, tetapi juga mengukur efektivitas proses uji tim Anda menggunakan metrik matematika standar industri.

### 1. Defect Removal Efficiency (DRE)
Mengukur seberapa efektif tim QA menemukan bug sebelum perangkat lunak dirilis ke tangan pengguna:

$$\text{DRE} = \left( \frac{D_{\text{internal}}}{D_{\text{internal}} + D_{\text{external}}} \right) \times 100\%$$

- $D_{\text{internal}}$: Jumlah bug yang ditemukan selama fase testing (sebelum rilis).
- $D_{\text{external}}$: Jumlah bug yang lolos dan dilaporkan pengguna di fase produksi (*defect leakage*).
- **Target Industri**: DRE $\ge 90\%$.

### 2. Defect Density
Mengukur kepadatan bug relatif terhadap ukuran kode atau jumlah user story:

$$\text{Defect Density} = \frac{\text{Total Defect Ditemukan}}{\text{KLOC (Ribuan Baris Kode)} \text{ atau Total User Story}}$$

---

## 11. Real World Example: Bug Leakage pada E-Commerce Flash Sale
Sebuah marketplace menggelar event Flash Sale pukul 00.00 WIB.
- **Kondisi Testing (Staging)**: QA menguji alur pembelian barang diskon dengan 1 akun tester pada koneksi internet cepat. Test case PASS.
- **Kondisi Produksi (00.00 WIB)**: 50.000 pengguna mengakses sistem bersamaan. Terjadi fenomena *Race Condition* di mana stok barang yang hanya 10 buah terbeli sebanyak 42 kali (*overselling defect*).
- **Penyebab Leakage**: Tim QA hanya menjalankan pengujian fungsional (*functional testing*) dan melewatkan pengujian performa & konkurensi (*non-functional concurrency testing*) dalam STLC Test Plan.
- **Dampak Finansial**: Marketplace terpaksa membatalkan 32 pesanan secara sepihak dan memberikan voucher kompensasi senilai total Rp 150.000.000 untuk meredam kemarahan konsumen.

---

## 12. Trade-offs

| Dimensi | STLC Formal & Ketat (Heavyweight) | STLC Agile / Pragmatis (Lightweight) |
|---|---|---|
| **Dokumentasi** | Lengkap: IEEE 829 Test Plan, Test Cases ratusan halaman, RTM. | Ringkas: Checklist, Exploratory Charters, Gherkin Scenarios. |
| **Siklus Rilis** | Lambat (2–6 minggu untuk cycle test). | Cepat (Harian atau mingguan per sprint). |
| **Biaya Overhead** | Tinggi (Banyak waktu habis membuat dokumen formal). | Rendah (Fokus pada otomasi dan eksekusi cepat). |
| **Kesesuaian Regulasi** | Wajib untuk industri berisiko tinggi (Medis, Aviasi, Core Banking). | Ideal untuk SaaS, Startup, Media Sosial, E-Commerce. |
| **Defect Leakage Risk** | Sangat rendah untuk isu terencana. | Membutuhkan otomasi regresi yang kuat agar tidak bocor. |

---

## 13. When To Use
- Gunakan siklus **STLC Formal** ketika mengembangkan perangkat lunak yang tunduk pada kepatuhan audit legal (ISO 9001, FDA, PCI-DSS, Bank Indonesia).
- Gunakan **Bug State Machine yang Ketat** ketika tim engineering berskala medium hingga enterprise (>15 insinyur) agar status pekerjaan transparan dan tidak ada tiket terabaikan.

## 14. When NOT To Use
- Jangan menerapkan birokrasi tiket 10-status untuk proyek hackathon atau eksperimen prototipe kilat 3 hari. Komunikasi langsung (*ad-hoc*) jauh lebih efisien.
- Jangan membuat dokumen Test Plan setebal 50 halaman jika tim menggunakan iterasi Agile 1 minggu; ganti dengan *Sprint Test Charter* ringkas.

---

## 15. Common Mistakes

```text
1. MISTAKE: Severity dan Priority disamaratakan atau tertukar.
   WHY IT HAPPENS: QA baru menganggap setiap error teknis otomatis darurat bisnis tertinggi.
   WHY IT IS BAD: Mengacaukan fokus tim developer yang sedang mengerjakan fitur krusial rilis.
   IMPACT: Tech debt meningkat, hubungan antar-divisi memanas.
   CORRECT APPROACH: Diskusikan Priority dengan Product Owner/Manager; QA menetapkan Severity berdasarkan dampak teknis.

2. MISTAKE: Steps to Reproduce tidak lengkap ("Web error saat saya bayar").
   WHY IT HAPPENS: QA terburu-buru dan tidak mencatat kondisi input atau credential akun.
   WHY IT IS BAD: Developer tidak bisa mereproduksi bug di lokal (*"Works on my machine"*), tiket ditutup sebagai Not Reproducible.
   IMPACT: Bug lolos ke produksi.
   CORRECT APPROACH: Selalu sertakan akun uji, environment, data input persis, dan payload HTTP request/response.
```

---

## 16. Best Practices

### Must Have
- **Steps to Reproduce (STR)** yang bernomor urut dan dapat diulang oleh siapapun tanpa asumsi tersembunyi.
- Pembagian status defect yang jelas dengan aturan siapa yang berhak memindahkan status (hanya QA yang boleh menutup tiket ke status `Closed`).
- Menetapkan **Entry Criteria** (misal: build berhasil di-deploy ke staging tanpa error migrasi DB) dan **Exit Criteria** (misal: 100% test case P0 PASS, 0 Critical Bug).

### Recommended
- Mengintegrasikan bug tracker (Jira/Linear) dengan repository Git (GitHub/GitLab) sehingga commit commit hash dan branch perbaikan tercatat otomatis di tiket bug.
- Melampirkan rekaman video (*screen recording*) atau file `.har` untuk bug antarmuka atau anomali jaringan yang sulit direproduksi.

### Advanced
- Menghitung metrik **Defect Leakage Rate** secara otomatis di akhir setiap sprint dan menampilkannya pada dashboard monitoring tim (Grafana / Datadog).
- Menerapkan **Root Cause Analysis (RCA)** 5-Whys pada setiap defect berstatus Critical/Blocker untuk mencegah kejadian berulang di level arsitektur.

### Avoid / Overengineering
- Mewajibkan 15 kolom isian wajib pada form pembuatan bug untuk isu minor typo styling CSS. Buat formulir adaptif sesuai tingkat keparahan.

---

## 17. Troubleshooting Defect Disputes: *"Works On My Machine"*
Salah satu konflik paling umum antara QA dan Developer:

```text
Developer: "Bug ini tidak valid. Di komputer lokal saya kodenya berjalan sempurna!"
QA: "Tapi di environment staging saya kodenya gagal terus!"
```

**Langkah Solusi Sistematis**:
1. **Verifikasi Versi Build / Commit Hash**: Pastikan staging menjalankan commit hash yang sama dengan branch developer (`git rev-parse HEAD`).
2. **Bandingkan Test Data & State**: Periksa apakah database lokal developer memiliki data kotor atau cache lokal yang tidak ada di staging.
3. **Periksa Variabel Lingkungan (ENV)**: Cek perbedaan config seperti flag API, sandbox payment gateway, atau API timeout.
4. **Reproduksi Bersama (Pair Debugging)**: QA dan Developer duduk bersama (atau screen share) untuk mereproduksi langkah persis menggunakan incognito browser dan Network DevTools terbuka.

---

## 18. Exercise
1. **Latihan Severity vs Priority**: Tentukan Severity (S1-Critical / S2-Major / S3-Minor) dan Priority (P1-Urgent / P2-High / P3-Medium) untuk 3 kasus berikut:
   - Kasus A: Halaman Kebijakan Privasi memiliki broken image logo sponsor. Besok ada audit tahunan kementerian.
   - Kasus B: Sistem crash jika pengguna memasukkan karakter emoji kuno Mesir pada field catatan transfer bank.
   - Kasus C: Tombol "Logout" tidak merespons pada browser Firefox versi mobile, sehingga session tetap terbuka jika perangkat dipinjamkan.
2. Buat sebuah tiket laporan bug lengkap (STR, Pre-conditions, Expected, Actual) berdasarkan bug Kasus C di atas.

---

## 19. Challenge
Rancang sebuah **STLC Test Strategy Document** ringkas untuk rilis fitur baru: *"Peminjaman Dana Instan (PayLater)"* pada aplikasi super-app fintech. Tentukan:
1. Scope In-Scope dan Out-of-Scope.
2. 3 Entry Criteria sebelum QA mulai menguji di staging.
3. 3 Exit Criteria mutlak sebelum fitur diizinkan rilis ke produksi.
4. Rencana kontinjensi jika ditemukan Defect P1 H-1 sebelum jadwal peluncuran.

---

## 20. Summary
- **STLC** memberikan metodologi pengujian yang disiplin dan terukur, memastikan aktivitas QA terencana sejak fase analisis kebutuhan awal.
- **Bug Life Cycle** adalah state machine yang menjamin setiap anomali tertangani secara tuntas dengan kriteria verifikasi objektif.
- Severity mengukur dampak teknis kerusakan, sedangkan Priority mengukur urgensi kebutuhan bisnis. Keduanya harus diselaraskan secara objektif.
- Kualitas laporan bug berbanding lurus dengan kecepatan developer menyelesaikan perbaikan.

---

## Hands-on Practice: Simulator State Machine Bug Life Cycle & Metrik QA
Jalankan script simulator yang mengimplementasikan state machine siklus defect, validasi transisi status, pelaporan bug terstruktur, dan kalkulator DRE otomatis:

```bash
node QA/BAB-01-Fondasi-Software-Testing-dan-STLC/hands-on/m02/stlc_bug_lifecycle_sim.js
```

---
[⬅️ Module 01: Prinsip Dasar Testing](./Module-01-Prinsip-Dasar-Testing-Verification-vs-Validation.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 01 ➡️](./BAB-01-Quiz-dan-Challenge.md)
---
