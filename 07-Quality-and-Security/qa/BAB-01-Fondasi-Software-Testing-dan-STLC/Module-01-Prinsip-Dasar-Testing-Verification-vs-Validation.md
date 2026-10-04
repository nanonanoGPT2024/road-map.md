---
[📋 Silabus Induk](../README.md) | [Module 02: SDLC, STLC, & Bug Lifecycle ➡️](./Module-02-SDLC-STLC-dan-Bug-Defect-Lifecycle.md)
---

# Module 01: Prinsip Dasar Testing: Verification vs Validation, 7 Prinsip Testing (ISTQB), dan Kualitas Perangkat Lunak

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami esensi dan filosofi **Software Quality Assurance (QA)**, serta membedakan secara tegas antara konsep **Quality Assurance (QA)**, **Quality Control (QC)**, dan **Testing**.
- Menganalisis perbedaan krusial antara **Verification** (*"Apakah kita membangun produk dengan benar?"*) dan **Validation** (*"Apakah kita membangun produk yang benar?"*).
- Membedakan rantai terjadinya anomali perangkat lunak: **Error (Mistake)** $\to$ **Fault / Defect (Bug)** $\to$ **Failure** $\to$ **Incident**.
- Menguasai dan menerapkan **7 Prinsip Dasar Pengujian Perangkat Lunak (ISTQB Principles)** dalam merancang strategi uji dunia nyata.
- Memahami standar kualitas perangkat lunak internasional **ISO/IEC 25010** (Karakteristik Kualitas Produk).
- Menganalisis kurva **Cost of Quality (CoQ)** dan mengapa eskalasi perbaikan bug di tahap produksi bernilai 30 hingga 100 kali lipat lebih mahal dibandingkan pencegahan di fase awal (*Shift-Left Testing*).

---

## 2. Prerequisite
- Pemahaman umum tentang alur pembuatan aplikasi web/mobile.
- Pengalaman dasar menggunakan komputer dan antarmuka web.
- Rasa ingin tahu yang kritis terhadap penyebab kegagalan perangkat lunak (*analytical & skeptical mindset*).

---

## 3. Concept
Dalam rekayasa perangkat lunak modern, pengujian (*testing*) bukanlah sekadar aktivitas "mencari-cari kesalahan" di akhir proses pengembangan setelah programmer selesai menulis kode.

Pengujian adalah **disiplin rekayasa investigatif yang sistematis** untuk mengukur, menilai, dan memberikan visibilitas terhadap kualitas perangkat lunak secara berkelanjutan, sekaligus mengurangi risiko kegagalan sistem sebelum menyentuh pengguna akhir.

```
[ MANUSIA MEMBUAT KESALAHAN ]
             |
             v
       [ ERROR (Mistake) ] : Developer salah paham terhadap rumus diskon di dokumen PRD
             |
             v
       [ DEFECT / BUG ]    : Baris kode tertulis `total = price + discount` alih-alih `price - discount`
             |
             v
       [ FAILURE ]         : Saat aplikasi dijalankan, saldo dompet pengguna terpotong lebih besar!
             |
             v
       [ INCIDENT ]        : Pengguna komplain ke customer service, reputasi perusahaan anjlok
```

Pemahaman rantai ini sangat fundamental: **Error** dilakukan oleh manusia (pemikiran/tindakan keliru), yang bermanifestasi menjadi **Defect/Bug** di dalam kode sumber atau dokumen, yang jika dieksekusi saat runtime akan memicu **Failure** (kegagalan sistem melayani ekspektasi), dan akhirnya menimbulkan **Incident** di dunia nyata.

---

## 4. Why? (Mengapa Kita Memerlukan QA & Testing?)
1. **Pencegahan Kerugian Finansial & Nyawa**:
   - Sejarah mencatat kegagalan software yang fatal: peluncuran roket *Ariane 5 Flight 501* yang meledak 37 detik pasca-peluncuran akibat konversi integer 64-bit ke 16-bit (kerugian \$370 juta), atau bug mesin radiasi *Therac-25* yang merenggut nyawa pasien akibat *race condition*.
2. **Cost of Defect Escalation (Biaya Eskalasi Cacat)**:
   - Menemukan dan memperbaiki bug di fase analisis kebutuhan (requirement) hanya membutuhkan biaya \$1.
   - Jika bug tersebut lolos ke tahap coding, biayanya menjadi \$10.
   - Jika lolos ke tahap pengujian sistem, biayanya menjadi \$100.
   - Jika bug tersebut lolos hingga ke tangan jutaan pengguna di **Production**, biaya pemulihan, denda hukum, investigasi forensik, dan kehilangan pelanggan bisa mencapai **\$10.000 hingga \$100.000** per insiden!
3. **Membangun Kepercayaan Pengguna (Brand Reputation)**:
   - Aplikasi yang sering mengalami crash, tombol macet, atau salah kalkulasi akan ditinggalkan pengguna dalam hitungan detik.

---

## 5. What? (QA vs QC vs Testing & Verification vs Validation)

### A. Perbedaan QA, QC, dan Testing

| Dimensi | Quality Assurance (QA) | Quality Control (QC) | Software Testing |
| :--- | :--- | :--- | :--- |
| **Fokus Utama** | **Proses & Pencegahan** (*Process-oriented*) | **Produk & Pendeteksian** (*Product-oriented*) | **Eksekusi & Eksplorasi** (*Activity-oriented*) |
| **Tujuan** | Memperbaiki proses SDLC agar cacat tidak terjadi sejak awal. | Memeriksa apakah produk akhir memenuhi spesifikasi yang ditentukan. | Menjalankan sistem dengan input tertentu untuk menemukan defek nyata. |
| **Kapan Dilakukan?**| Sepanjang siklus SDLC (Proaktif). | Pada hasil akhir atau build rilis (Reaktif). | Selama fase testing dinamis & statis. |
| **Contoh Aksi** | Menyusun SOP review kode, audit standar penulisan requirement. | Inspeksi build release candidate, audit kepatuhan ISO. | Menjalankan test case login, automation regression test. |

### B. Verification vs Validation

```
+-----------------------------------------------------------------------------------+
| VERIFICATION (Apakah kita membangun produk DENGAN BENAR?)                         |
|  - Berorientasi pada spesifikasi teknis dan desain dokumen.                       |
|  - Bersifat STATIS (tanpa mengeksekusi kode program).                             |
|  - Meliputi: Code Review, Walkthrough dokumen PRD, Analisis Arsitektur.           |
+-----------------------------------------------------------------------------------+
                                        vs
+-----------------------------------------------------------------------------------+
| VALIDATION (Apakah kita membangun PRODUK YANG BENAR?)                             |
|  - Berorientasi pada kebutuhan pengguna nyata dan kepuasan bisnis.                |
|  - Bersifat DINAMIS (menjalankan aplikasi secara riil).                           |
|  - Meliputi: User Acceptance Testing (UAT), Pengujian Fungsional, Beta Testing.   |
+-----------------------------------------------------------------------------------+
```

---

## 6. How? (7 Prinsip Dasar Pengujian Perangkat Lunak - ISTQB)

### 1. Testing shows the presence of defects, not their absence (Testing Menunjukkan Adanya Cacat, Bukan Ketiadaannya)
- Pengujian membuktikan bahwa ada bug di dalam aplikasi. Namun, sebanyak apapun pengujian yang berhasil lolos (*pass*), **kita tidak pernah bisa menjamin bahwa aplikasi 100% bebas dari bug sama sekali**. Pengujian mengurangi risiko, bukan meniadakannya secara absolut.

### 2. Exhaustive testing is impossible (Pengujian Melelahkan Secara Total Adalah Mustahil)
- Menguji seluruh kemungkinan kombinasi input data, skenario klik, dan urutan waktu secara matematis mustahil dilakukan.
- *Contoh*: Sebuah form dengan 10 kolom teks bebas memiliki tak hingga kombinasi string.
- *Solusi QA*: Gunakan teknik prioritas berbasis risiko (*Risk-Based Testing*) dan teknik desain kasus uji (Equivalence Partitioning & Boundary Value Analysis).

### 3. Early testing saves time and money / Shift-Left (Pengujian Dini Menghemat Waktu dan Biaya)
- Pengujian harus dimulai sedini mungkin dalam siklus hidup pengembangan (sejak review dokumen requirement). Menemukan ambiguitas kalimat di PRD jauh lebih murah daripada membongkar ulang kode di production.

### 4. Defect clustering / Pareto Principle 80/20 (Pengelompokan Cacat)
- Biasanya, **80% bug ditemukan pada 20% modul aplikasi** yang paling kompleks atau paling sering dimodifikasi. QA cerdas mengonsentrasikan tenaga pengujian pada modul-modul kritis ini.

### 5. Beware of the pesticide paradox (Waspada Paradoks Pestisida)
- Jika Anda menyemprotkan pestisida yang sama berulang-ulang pada tanaman, hama akan menjadi kebal. 
- Demikian pula, jika Anda menjalankan rangkaian test case yang sama persis tanpa pernah memperbaruinya, test case tersebut tidak akan lagi menemukan bug baru. Test case dan skrip otomasi harus diperbarui secara berkala (*Test Suite Review*).

### 6. Testing is context-dependent (Pengujian Bergantung pada Konteks)
- Strategi pengujian situs web e-commerce diskon kilat sangat berbeda dengan pengujian perangkat lunak sistem rem mobil otomatis (ABS) atau perangkat medis jantung. Konteks menentukan tingkat kedalaman, alat uji, dan toleransi risiko.

### 7. Absence-of-errors is a fallacy (Ketiadaan Error Adalah Ilusi)
- Menemukan dan memperbaiki 1.000 bug tidak ada artinya jika aplikasi yang dibangun sama sekali tidak berguna, tidak dibutuhkan oleh pasar, atau terlalu rumit untuk digunakan oleh manusia nyata.

---

## 7. Analogy
Bayangkan proses perakitan sebuah pesawat jet komersial:
- **Verification**: Insinyur memeriksa cetak biru (*blueprint*), menghitung daya tahan logam di atas kertas, dan memeriksa apakah baut dipasang dengan torsi yang tepat sesuai buku manual (*Statis - Memeriksa kesesuaian spesifikasi*).
- **Validation**: Pilot uji coba menyalakan mesin, lepas landas ke udara, dan menguji apakah pesawat dapat bermanuver dengan stabil di tengah badai cuaca nyata dan apakah kabin nyaman bagi penumpang (*Dinamis - Memeriksa kegunaan operasional riil*).
- Sebuah pesawat bisa saja lolos 100% verifikasi teknis baut, tetapi gagal validasi karena ternyata kabin terlalu sempit sehingga penumpang tidak bisa duduk!

---

## 8. Diagram Rantai Defek & Kurva Biaya Eskalasi

```
RANTAI ESKALASI ANOMALI:
[ Developer Lelah / Kurang Paham ]  ===> ( ERROR / Human Mistake )
                                                    |
                                                    v
[ Salah Ketik / Logika Percabangan ]===> ( DEFECT / Code Bug )
                                                    |
                                                    v (Dieksekusi Runtime)
[ Layar Putih / Kalkulasi Minus ]   ===> ( FAILURE / System Failure )
                                                    |
                                                    v
[ Kerugian Finansial / Komplain ]   ===> ( INCIDENT / Business Impact )

------------------------------------------------------------------------------------
KURVA BIAYA PERBAIKAN DEFECT (Cost of Defect Escalation Curve):
Biaya ($)
  ^
100x|                                                        [ PRODUCTION ]
    |                                                              *
 50x|                                                      *
    |                                              *
 20x|                                      [ SYSTEM TEST ]
    |                              *
 10x|                      [ INTEGRATION ]
    |              *
  1x| [ REQUIREMENT ]
    +--------------------------------------------------------------> Tahapan SDLC
```

---

## 9. Simple Example: Anatomi Assertions pada Pengujian
Dalam dunia software testing, inti dari setiap kasus uji bermuara pada satu konsep matematis: **Membandingkan *Actual Result* dengan *Expected Result***.

```javascript
// Fungsi Bisnis yang Diuji (System Under Test / SUT)
function calculateCartDiscount(totalPrice, couponCode) {
  if (couponCode === "DISKON50") {
    return totalPrice * 0.5; // Diskon 50%
  }
  return 0;
}

// Kasus Uji 1: Kupon Valid
const actual1 = calculateCartDiscount(100000, "DISKON50");
const expected1 = 50000;

if (actual1 === expected1) {
  console.log("✅ TEST 1 PASS: Kalkulasi diskon 50% sesuai ekspektasi.");
} else {
  console.error(`❌ TEST 1 FAIL: Expected ${expected1}, received ${actual1}`);
}

// Kasus Uji 2: Kupon Kosong (Boundary/Negative Test)
const actual2 = calculateCartDiscount(100000, "");
const expected2 = 0;

if (actual2 === expected2) {
  console.log("✅ TEST 2 PASS: Kupon kosong menghasilkan diskon 0.");
} else {
  console.error(`❌ TEST 2 FAIL: Expected ${expected2}, received ${actual2}`);
}
```

---

## 10. Practical Example: Mengidentifikasi Celah Kualitas ISO/IEC 25010
Standar ISO/IEC 25010 membagi kualitas perangkat lunak menjadi 8 karakteristik inti yang wajib diperhatikan oleh seorang QA Engineer:

| Karakteristik ISO 25010 | Pertanyaan Kritis Pengujian | Contoh Bug yang Sering Lolos |
| :--- | :--- | :--- |
| **Functional Suitability** | Apakah sistem melakukan apa yang dibutuhkan? | Tombol "Transfer Saldo" tidak memindahkan uang. |
| **Performance Efficiency** | Seberapa cepat sistem merespons di bawah beban? | Server timeout jika ada 500 pengguna bersamaan. |
| **Compatibility** | Apakah sistem bekerja di berbagai OS/Browser? | Tampilan hancur saat dibuka di Safari iOS. |
| **Usability** | Seberapa mudah pengguna memahami antarmuka? | Tulisan font abu-abu tipis di atas latar putih (sulit dibaca). |
| **Reliability** | Apakah sistem tetap stabil saat terjadi error jaringan?| Aplikasi force close jika koneksi Wi-Fi putus sejenak. |
| **Security** | Apakah data sensitif pengguna terlindungi? | Password pengguna terlihat dalam URL query string. |
| **Maintainability** | Seberapa mudah sistem diperbaiki dan diuji kembali? | Mengubah satu warna tombol merusak seluruh layout halaman. |
| **Portability** | Seberapa mudah aplikasi dipindahkan ke platform lain? | Aplikasi hanya bisa berjalan di Windows 10, crash di Windows 11. |

---

## 11. Real-World Example: Insiden Defect Clustering pada Modul Checkout E-Commerce
Di sebuah marketplace nasional terkemuka, tim QA menganalisis riwayat 500 tiket bug yang dilaporkan selama 6 bulan terakhir:
- **Modul Katalog & Pencarian**: 35 bug (7%).
- **Modul Notifikasi & Email**: 25 bug (5%).
- **Modul Pengaturan Profil**: 15 bug (3%).
- **Modul Checkout, Pajak, Ongkir, & Diskon Multivendor**: **425 bug (85%)!**

**Tindakan Strategis QA**:
Alih-alih membagi waktu pengujian secara rata ke seluruh modul, tim QA mengalokasikan 80% waktu pengujian otomatis (*automation regression suite*) dan pengujian skenario ekstrem (*boundary testing*) khusus pada **Modul Checkout**, karena di sanalah defek berkumpul (*Defect Clustering*) dan di sanalah risiko kegagalan bisnis paling fatal berada.

---

## 12. Trade-offs: Pengujian Manual vs Otomasi

| Kriteria | Pengujian Manual (Manual Exploratory) | Pengujian Otomatis (Test Automation) |
| :--- | :--- | :--- |
| **Biaya Awal Setup** | **Rendah (Langsung bisa mulai)** | Tinggi (Butuh coding, framework, CI/CD) |
| **Biaya Eksekusi Berulang** | Sangat Mahal (Membutuhkan jam kerja manusia) | **Sangat Murah (Bisa jalan ribuan kali di CI/CD)** |
| **Kecepatan Uji Regresi** | Lambat (Berhari-hari untuk seluruh sistem) | **Sangat Cepat (Hitungan menit)** |
| **Kemampuan Eksplorasi & UX**| **Sangat Tinggi (Intuisi & persepsi manusia)** | Nol (Hanya mengecek perintah yang diprogram) |
| **Uji Beban (10.000 User)** | **Mustahil dilakukan oleh manusia** | **Sangat Mudah (k6, JMeter, Locust)** |

---

## 13. When To Use Manual Testing
- **Exploratory Testing**: Menjelajahi fitur baru yang belum memiliki skenario baku untuk menemukan perilaku tak terduga.
- **Usability & UX Testing**: Menilai estetika, kenyamanan alur navigasi, dan kemudahan bagi manusia.
- **Pengujian Satu Kali (Ad-hoc Testing)**: Fitur prototipe cepat yang hanya akan dipakai untuk demo satu kali dan kemungkinan besar dibuang.

---

## 14. When NOT To Use Manual Testing
- **Regression Testing Harian**: Mengulang 500 test case yang sama setiap kali ada developer yang melakukan commit kode baru (Gunakan Otomasi!).
- **Performance & Load Testing**: Menguji ketahanan server terhadap lonjakan 50.000 request per detik.
- **Validasi Data Skala Besar**: Memeriksa konsistensi 100.000 baris rekaman transaksi database.

---

## 15. Common Mistakes
1. **Menganggap Testing adalah Fase Terakhir**:
   - Menunggu sampai sprint berakhir di hari Jumat sore untuk mulai mengetes. Jika ditemukan bug arsitektur fatal, rilis tertunda dan tim panik (*Waterfall Trap*).
2. **Mentalitas "Tidak Ada Bug Berarti Aplikasi Sempurna"**:
   - Mempercayai bahwa 0 bug di Jira membuktikan sistem 100% sempurna. Bisa jadi test case yang dirancang terlalu dangkal atau tidak menyentuh skenario ekstrem!
3. **Mengabaikan Dampak Paradoks Pestisida**:
   - Merasa aman hanya karena suite otomasi lama selalu berwarna hijau (*all passed*), tanpa pernah menambahkan test case untuk skenario fitur baru atau variasi input baru.

---

## 16. Best Practices

### Must Have
- Mulai pengujian sedini mungkin (*Shift-Left Testing*): review dokumen kebutuhan bisnis (PRD/User Stories) sebelum developer menulis baris kode pertama.
- Bedakan dokumen ekspektasi (*Expected Result*) dari hasil pengamatan riil (*Actual Result*) pada setiap laporan pengujian.
- Prioritaskan pengujian berdasarkan analisis risiko (*Risk-Based Testing*).

### Recommended
- Gabungkan pengujian fungsional dengan audit karakteristik ISO 25010 (periksa performa dasar, keamanan input, dan aksesibilitas).
- Lakukan review berkala terhadap test suite untuk membuang test case usang dan menambahkan skenario baru pencegah paradoks pestisida.

### Advanced
- Bangun budaya *Whole Team Quality*: QA bukan lagi "polisi penjaga gerbang" (*gatekeeper*), melainkan konsultan kualitas (*Quality Coach*) yang membantu developer menulis unit test yang kokoh dan merancang arsitektur yang mudah diuji (*Testability*).

### Avoid
- Jangan pernah mengubah ekspektasi test case agar cocok dengan perilaku bug yang sedang terjadi di aplikasi hanya agar status tes menjadi "hijau".

---

## 17. Troubleshooting Guide

| Gejala Masalah | Kemungkinan Akar Masalah | Solusi |
| :--- | :--- | :--- |
| Banyak bug kritis bocor ke Production padahal seluruh test case QA di Jira berstatus "Pass". | Test case hanya menguji *Happy Path* (skenario normal) dan tidak menguji *Negative Scenarios* atau batas ekstrim (*Boundary*). | Tambahkan skenario negatif, input ilegal, dan pengujian beban jaringan pada test suite. |
| Developer menolak tiket bug dengan status "Not a Bug / Works on My Machine". | Laporan bug tidak memiliki langkah reproduksi yang deterministik (*Incomplete Steps to Reproduce*) atau data uji spesifik. | Lengkapi laporan bug dengan data input pasti, environment (OS/Browser version), log console, dan video rekaman. |
| Suite otomasi selalu "Pass" tetapi pengguna komplain fitur baru tidak berfungsi. | Suite otomasi mengalami Paradoks Pestisida: hanya menguji fitur versi 1.0 dan belum ada skrip untuk fitur versi 2.0. | Perbarui dan audit cakupan test script secara berkala seiring pertumbuhan fitur baru. |

---

## 18. Exercise
- **Easy**: Tuliskan 3 perbedaan utama antara proses *Verification* dan *Validation* beserta contoh konkret pada aplikasi perbankan.
- **Medium**: Analisis skenario berikut: *"Sebuah form pendaftaran mewajibkan usia antara 18 hingga 60 tahun"*. Sebutkan nilai-nilai input batas (*boundary values*) yang wajib diuji untuk memastikan validasi berfungsi benar!
- **Hard**: Rancang sebuah assertion engine sederhana di JavaScript yang mampu mengevaluasi kesamaan objek mendalam (*deep equality*), mencatat statistik total test, test passed, test failed, dan waktu eksekusi.

---

## 19. Challenge
Buat dokumen strategi pengujian (*Test Strategy Document*) satu halaman untuk fitur baru "Instant QRIS Payment" pada aplikasi dompet digital. Terapkan 7 prinsip ISTQB dalam mengidentifikasi modul clustering risiko tertinggi, strategi mitigasi biaya eskalasi defek, dan rancangan pengujian fungsional serta non-fungsional berdasarkan ISO 25010.

---

## 20. Summary
- **Software Testing** adalah proses analitis terencana untuk mengukur kualitas dan memitigasi risiko kegagalan sistem sebelum menyentuh pengguna.
- **Verification** menguji kesesuaian dengan spesifikasi cetak biru teknis (*statis*), sedangkan **Validation** menguji kesesuaian dengan kebutuhan nyata pengguna (*dinamis*).
- Memahami **7 Prinsip Dasar ISTQB** membentengi tim QA dari ekspektasi keliru (seperti mitos software 100% bebas bug) dan mengarahkan fokus ke modul yang paling berisiko tinggi.
- Menerapkan budaya **Shift-Left Testing** memotong biaya perbaikan cacat secara eksponensial dan membangun perangkat lunak berkualitas sejak hari pertama.

---

## Hands-on Practice: Simulator Assertion Engine & Regression Detector
Jalankan simulator engine pengujian mandiri yang mengimplementasikan assertion runner, evaluasi kesetaraan data, dan deteksi regresi logika bisnis:

```bash
node QA/BAB-01-Fondasi-Software-Testing-dan-STLC/hands-on/m01/testing_fundamentals_assertions_sim.js
```

---
[📋 Silabus Induk](../README.md) | [Module 02: SDLC, STLC, & Bug Lifecycle ➡️](./Module-02-SDLC-STLC-dan-Bug-Defect-Lifecycle.md)
---
