# BAB-07-Usability-Testing-Terukur-dan-Metrik-UX-Standar: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang untuk menguji, memvalidasi, dan memperdalam pemahaman teknis mengenai metodologi evaluasi pengalaman pengguna kuantitatif dan kualitatif, kalkulasi metrik standar industri (SUS, SEQ, UMUX-Lite, Task Completion Rate, Time-on-Task, Error Rate), hingga orkestrasi riset usability testing produksi skala enterprise.

---

## Bagian 1: Basic Questions (5 Pertanyaan)

### 1. Apa perbedaan mendasar antara Evaluasi Formatif (*Formative Usability Testing*) dan Evaluasi Sumatif (*Summative Usability Testing*) dalam siklus hidup produk digital?
**Jawaban & Pembahasan Teknis:**
- **Formatif (*Formative Testing*):** Dilakukan selama fase desain dan iterasi aktif (early discovery hingga protoyping tingkat rendah/tinggi). Tujuannya bersifat diagnostik kualitatif: menemukan titik friksi antarmuka (*usability flaws*), memahami model mental pengguna melalui *think-aloud protocol*, dan memperbaiki masalah arsitektur informasi sebelum kode diproduksi. Metrik numerik biasanya sekunder; ukuran sampel kecil (5–8 partisipan per segmen) sudah cukup untuk mendeteksi 80–85% isu usability utama.
- **Sumatif (*Summative Testing*):** Dilakukan pada akhir iterasi besar, fase rilis beta, atau pasca-peluncuran produk ke produksi. Tujuannya adalah validasi terukur (*benchmark*) berbasis metrik kuantitatif terstandar untuk membandingkan kinerja UX terhadap KPI bisnis, versi produk sebelumnya, atau kompetitor. Membutuhkan ukuran sampel statistik yang memadai (umumnya $n \ge 30\text{--}40$) agar margin error dan confidence interval ($95\%$ CI) valid secara statistik.

---

### 2. Bagaimana rumus dan metodologi normalisasi skor System Usability Scale (SUS) dari 10 pertanyaan skala Likert 5-poin?
**Jawaban & Pembahasan Teknis:**
SUS terdiri dari 10 butir pertanyaan ganjil (bermakna positif) dan genap (bermakna negatif) dengan skala Likert 1 (Sangat Tidak Setuju) hingga 5 (Sangat Setuju).
Metode kalkulasi skor terstandarisasi:
1. **Untuk butir bernomor ganjil (1, 3, 5, 7, 9):**
   $$\text{Skor Kontribusi} = \text{Respons Peserta} - 1$$
2. **Untuk butir bernomor genap (2, 4, 6, 8, 10):**
   $$\text{Skor Kontribusi} = 5 - \text{Respons Peserta}$$
3. **Kalkulasi Total:**
   $$\text{Skor SUS Akhir} = \left( \sum_{i=1}^{10} \text{Skor Kontribusi}_i \right) \times 2.5$$
Rentang skor akhir adalah 0 hingga 100. Perlu digarisbawahi bahwa skor SUS **bukan persentil murni**. Skor 68 merupakan rata-rata industri (*benchmark average* atau Grade C). Skor $>80.3$ merepresentasikan kualitas produk tingkat tinggi (*Grade A / Top 10%*).

---

### 3. Mengapa metrik Single Ease Question (SEQ) dinilai segera setelah satu tugas (*post-task*) selesai, bukan di akhir sesi pengujian (*post-test*)?
**Jawaban & Pembahasan Teknis:**
SEQ adalah kuesioner 1 butir skala Likert 7-poin (*"Overall, how easy or difficult was it to complete this task?"* dari 1 = Sangat Sulit hingga 7 = Sangat Mudah). SEQ wajib diberikan secara *immediate post-task* untuk menghindari fenomena kognitif:
- **Peak-End Rule & Recency Bias:** Peserta cenderung hanya mengingat insiden paling ekstrem (paling menyebalkan atau paling memuaskan) dan momen terakhir pengujian, sehingga mendistorsi ingatan terhadap kompleksitas tugas individual di awal sesi.
- **Halo Effect Post-Session:** Keberhasilan atau kegagalan tugas terakhir dapat mencemari evaluasi subjektif tugas-tugas sebelumnya jika diukur secara retroaktif di akhir sesi pengujian.

---

### 4. Apa perbedaan metodologis antara Task Completion Rate (TCR) biner dan TCR bertingkat (*partial completion*)?
**Jawaban & Pembahasan Teknis:**
- **TCR Biner ($0$ atau $1$):** Pengguna dinilai sukses ($1$) hanya jika memenuhi seluruh kriteria objektif keberhasilan tugas (*stopping condition*) tanpa intervensi fasilitator dan tanpa kesalahan fatal. Gagal ($0$) jika pengguna menyerah, menemui jalan buntu (*loop error*), atau keluar dari jalur kritis alur. Formula agregat:
  $$\text{TCR} = \frac{\text{Jumlah Task Sukses}}{\text{Total Task Percobaan}} \times 100\%$$
- **TCR Bertingkat (*Partial Credit / Graded Success*):** Diberikan bobot proporsional (misalnya: $1.0$ sukses mandiri, $0.5$ sukses dengan bantuan dokumentasi/hint non-fatal, $0$ gagal total). Digunakan pada analisis alur onboarding atau checkout multi-langkah kompleks di mana bisnis ingin memetakan *step-by-step conversion resilience* sebelum drop-off total.

---

### 5. Kapan sebaiknya tim UX menggunakan Single-Moderated Usability Testing dibandingkan Unmoderated Remote Usability Testing?
**Jawaban & Pembahasan Teknis:**
- **Moderated Testing:** Tepat digunakan saat menguji konsep tahap awal, alur transaksi tingkat tinggi yang membutuhkan validasi protokol keamanan/kepatuhan hukum, atau domain B2B khusus yang rumit. Fasilitator dapat mendalami respons mendadak pengguna melalui probing teknis (*"Mengapa Anda memilih tombol tersebut?"*), mencegah pengguna mengalami frustrasi fatal (*dead-end lockout*), serta mengamati bahasa tubuh mikro.
- **Unmoderated Remote Testing:** Tepat digunakan untuk validasi kuantitatif sumatif, benchmarking TCR dan Time-on-Task berskala besar ($n > 50\text{--}100$), verifikasi antarmuka yang sudah stabil (*high-fidelity prototype* atau live production), dan saat menguji pengguna dengan dispersi zona waktu global tanpa beban alokasi waktu fasilitator.

---

## Bagian 2: Intermediate Questions (5 Pertanyaan)

### 1. Bagaimana membedakan antara UMUX-Lite dan SUS, dan bagaimana persamaan regresi mentransformasi skor UMUX-Lite ke skala estimasi SUS?
**Jawaban & Pembahasan Teknis:**
Usability Metric for User Experience Lite (UMUX-Lite) adalah kuesioner ringkas 2 butir berbasis ISO 9241-11 yang mengukur *Perceived Ease of Use* dan *Perceived Usefulness* menggunakan skala Likert 7-poin:
1. *"Fitur-fitur sistem ini memenuhi kebutuhan saya."* (Kebergunaan)
2. *"Sistem ini mudah digunakan."* (Kemudahan Penggunaan)

Untuk mengonversi skor rata-rata UMUX-Lite ($U_L$ pada skala 0–100) menjadi estimasi ekuivalen skor SUS ($S_{est}$), Lewis dkk. menetapkan formula regresi linier empiris:
$$S_{est} = 0.65 \times U_L + 22.9$$
Alternatif koreksi satu langkah sederhana yang sering digunakan praktisi industri adalah:
$$\text{Adjusted Score} = \left( \frac{\text{Skor Item 1} + \text{Skor Item 2} - 2}{12} \right) \times 100$$
Formula ini mengurangi beban kognitif partisipan secara drastis dalam survei intercept web/aplikasi tanpa kehilangan korelasi signifikan ($r > 0.80$) terhadap skala SUS standar.

---

### 2. Mengapa metrik Time-on-Task (ToT) harus dianalisis menggunakan Geometric Mean atau Median, bukan Arithmetic Mean biasa?
**Jawaban & Pembahasan Teknis:**
Data durasi penyelesaian tugas (*Time-on-Task*) hampir selalu memiliki distribusi menceng ke kanan (*positively skewed / log-normal distribution*). Sebagian besar pengguna menyelesaikan tugas dalam rentang waktu teratur (misalnya 40–90 detik), namun beberapa pengguna mengalami distraksi, kebingungan, atau *extreme hesitation* yang memakan waktu 300–600 detik.
- **Arithmetic Mean (Rata-rata Aritmetika):** Sangat rentan terhadap outlier ekstrem tersebut, sehingga memberikan estimasi durasi tipikal yang bias dan terlalu tinggi.
- **Median atau Geometric Mean:** Merefleksikan nilai tendensi sentral yang sebenarnya. Geometric Mean dihitung dengan mentransformasikan data durasi ke skala logaritma natural, menghitung rata-rata aritmetika pada domain log, lalu melakukan eksponensiasi kembali (*anti-log*):
  $$\text{GeoMean} = \exp\left(\frac{1}{n} \sum_{i=1}^n \ln(t_i)\right)$$
Pendekatan ini menjamin estimasi ToT objektif untuk perbandingan versi antarmuka.

---

### 3. Bagaimana cara menghitung dan menginterpretasikan Adjusted Wald Binomial Confidence Interval untuk Task Completion Rate pada sampel kecil ($n = 15$)?
**Jawaban & Pembahasan Teknis:**
Pada sampel usability testing kecil ($n < 30$), rumus Wald tradisional ($p \pm z \sqrt{p(1-p)/n}$) menghasilkan interval yang terlalu sempit dan tidak akurat ketika rasio sukses mendekati 0 atau 1. 
Metode **Adjusted Wald (Agresti-Coull / "Add-Two-Successes-and-Two-Failures")** digunakan dengan menambahkan 4 pseudo-observasi (2 sukses, 2 gagal):
1. $\tilde{n} = n + 4 = 15 + 4 = 19$
2. $\tilde{x} = x + 2$ (di mana $x$ adalah jumlah tugas sukses)
3. Proporsi yang disesuaikan: $\tilde{p} = \frac{\tilde{x}}{\tilde{n}}$
4. Margin of Error ($95\%$ Confidence Interval, $z = 1.96$):
   $$\text{Margin of Error} (W) = 1.96 \times \sqrt{\frac{\tilde{p}(1 - \tilde{p})}{\tilde{n}}}$$
   $$\text{Confidence Interval} = \tilde{p} \pm W$$
Interpretasi: Jika $x = 12$, maka $\tilde{x} = 14, \tilde{n} = 19 \Rightarrow \tilde{p} = 0.737$ (73.7%). Margin error $\approx \pm 0.198$. Tim dapat menyimpulkan dengan keyakinan $95\%$ bahwa TCR populasi pengguna aktual berada di antara $53.9\%$ hingga $93.5\%$, membuktikan bahwa klaim "80% sukses pasti tercapai" belum terbukti kuat tanpa memperbesar sampel.

---

### 4. Dalam pengujian formatif, bagaimana mengidentifikasi dan memitigasi dampak dari "Hawthorne Effect" dan "Social Desirability Bias"?
**Jawaban & Pembahasan Teknis:**
- **Hawthorne Effect:** Peserta mengubah perilakunya menjadi lebih teliti, lambat, atau patuh terhadap instruksi karena menyadari bahwa gerak-gerik mereka direkam dan diamati oleh fasilitator.
- **Social Desirability Bias:** Peserta enggan mengkritik desain secara jujur karena takut menyinggung perancang atau ingin terlihat kompeten dan pintar di hadapan penguji.
- **Mitigasi Teknis:**
  1. *Standardized Pre-Test Scripting:* Fasilitator menyatakan penafian eksplisit: *"Kami menguji sistem, bukan menguji kemampuan Anda. Kegagalan sistem adalah kegagalan desain kami, bukan kesalahan Anda. Komentar kritis dan negatif adalah masukan paling berharga."*
  2. *Neutral Observer Stance:* Menerapkan *retrospective probing* alih-alih intervensi langsung, dan mematikan video fasilitator pada sesi remote unmoderated.
  3. *Anonymized Post-Task Ratings:* Memberikan formulir kuesioner digital mandiri tanpa fasilitator melihat langsung layar saat nilai Likert diinput.

---

### 5. Bagaimana korelasi dan perbedaan fungsional antara Net Promoter Score (NPS), Customer Satisfaction (CSAT), dan System Usability Scale (SUS) dalam evaluasi produk digital?
**Jawaban & Pembahasan Teknis:**
- **CSAT (Customer Satisfaction):** Mengukur kepuasan sesaat (*transactional/short-term satisfaction*) terhadap interaksi spesifik (misalnya: penutupan tiket customer support atau penyelesaian pembayaran).
- **SUS (System Usability Scale):** Mengukur persepsi kebergunaan dan efisiensi sistem (*pragmatic/functional usability*) secara menyeluruh pada produk perangkat lunak. Skor SUS adalah metrik diagnostik murni untuk antarmuka.
- **NPS (Net Promoter Score):** Mengukur loyalitas jangka panjang dan nilai reputasi merek (*brand loyalty & advocacy*) melalui pertanyaan rekomendasi: *"Seberapa besar kemungkinan Anda merekomendasikan produk ini kepada rekan Anda?"*
- **Korelasi Produksi:** Produk dengan skor SUS di bawah 68 hampir tidak pernah mencapai NPS positif. Peningkatan reliabilitas dan usability sistem (SUS $>80$) berkorelasi linear terhadap peningkatan retensi dan probabilitas promotor pada NPS, namun NPS juga dipengaruhi oleh harga produk, brand image, dan performa customer service di luar UI/UX itu sendiri.

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 1: Krisis Drop-Off Alur Checkout Fintech Pembayaran Multi-Kanal
**Konteks Masalah:**
Aplikasi dompet digital enterprise mengalami penurunan *checkout completion rate* dari $88\%$ menjadi $62\%$ pasca peluncuran pembaruan antarmuka *Smart Split-Bill & Multi-Source Funding*. Manajemen menuntut investigasi terukur dalam tempo 7 hari kerja untuk mengembalikan metrik transaksi tanpa menebak-nebak akar penyebab.

**Tugas & Solusi Teknis:**
1. **Penyusunan Usability Test Plan Berorientasi Metrik:**
   - Rekrut 12 partisipan yang dibagi menjadi dua kelompok screener: 6 pengguna reguler aktif dan 6 pengguna baru dengan latar belakang non-tech-savvy.
   - Skenario pengujian terarah (*Task-based Script*): Peserta diminta menyelesaikan pembayaran split-bill Rp 350.000 dengan kombinasi saldo wallet dan kartu debit virtual.
2. **Koleksi Metrik Usability Inti:**
   - *Task Completion Rate (TCR)* biner per langkah alur.
   - *Time-on-Task (ToT)* diukur dari penekanan tombol "Bayar Sekarang" hingga layar sukses.
   - *Post-Task SEQ* untuk mengisolasi titik friksi kognitif.
   - *Error Frequency & Classification:* Memetakan slips (salah ketik PIN/pilihan) vs mistakes (salah memahami terminologi "Multi-Source Funding").
3. **Temuan & Tindakan Berdasarkan Data:**
   - Hasil menunjukkan TCR rontok pada tahap pemilihan kartu sekunder karena indikator dropdown tertutup keyboard virtual Android (UI overlay bug) dan skor SEQ tahap tersebut berada pada angka rata-rata $2.1 / 7$.
   - Dilakukan hotfix layout keyboard padding dan penyederhanaan microcopy terminologi. Re-testing unmoderated sumatif ($n = 40$) membuktikan pemulihan TCR ke angka $89.4\%$ dengan rata-rata SEQ $6.3 / 7$.

---

### Skenario 2: Migrasi Sistem ERP Rumah Sakit (Medical Record EHR) Berisiko Tinggi
**Konteks Masalah:**
Sebuah rumah sakit swasta mengimplementasikan sistem Electronic Health Record (EHR) berbasis web untuk perawat dan dokter jaga. Pada uji coba awal, terjadi komplain massal: waktu administrasi resep obat meningkat 3 kali lipat dan tingkat kesalahan input dosis meningkat secara berbahaya (*critical medical slips*).

**Tugas & Solusi Teknis:**
1. **Desain Protokol Pengujian Khusus Regulasi Keselamatan:**
   - Gunakan *Concurrent Think-Aloud (CTA)* yang dimoderasi langsung di lingkungan simulasi bangsal rumah sakit (high-fidelity testbed) dengan melibatkan 8 perawat intensif dan 6 dokter spesialis.
2. **Matriks Evaluasi Kritis Usability:**
   - *Critical Slip Rate:* Frekuensi salah pilih satuan dosis (mg vs mcg) atau salah identifikasi nama obat yang mirip (*Look-Alike, Sound-Alike / LASA*).
   - *Lostness Metric ($L$):*
     $$L = \sqrt{\left(\frac{N}{S} - 1\right)^2 + \left(\frac{R}{N} - 1\right)^2}$$
     Di mana $N$ = jumlah halaman unik yang dikunjungi, $S$ = total halaman yang dikunjungi, dan $R$ = jumlah halaman minimum optimal. Nilai $L > 0.4$ menunjukkan disorientasi arsitektur navigasi navigasional.
3. **Penyusunan Rekomendasi Solutif:**
   - Skor Lostness rata-rata dokter mencapai $0.58$, membuktikan dokter tersesat dalam modal multi-tab.
   - Tim merekonstruksi UI modal resep menjadi panel samping persisten (*drawer panel*) dengan validasi visual kontras tinggi untuk satuan dosis berbahaya dan penambahan auto-complete berbasis fuzzy search terverifikasi. Pada pengujian validasi ulang, slip rate turun menjadi $0\%$ dan ToT berkurang sebesar $54\%$.

---

### Skenario 3: Redesain Dashboard Analitik SaaS B2B Enterprise untuk Menembus Benchmark SUS
**Konteks Masalah:**
Platform analitik rantai pasok B2B memiliki skor SUS rendah yaitu $52.5$ (Grade F / Poor Usability), memicu churn pelanggan korporat saat masa perpanjangan kontrak tahunan. Tim engineering berpendapat fitur sistem sudah lengkap, sementara tim sales menyatakan antarmuka terlalu membingungkan bagi manajer logistik.

**Tugas & Solusi Teknis:**
1. **Metode Audit & Benchmark Komparatif:**
   - Lakukan studi benchmarking kompetitif sumatif terhadap versi eksisting vs 2 prototipe desain baru (Desain Modular Widget vs Desain Alur Pipeline Linear) melibatkan 30 manajer logistik terverifikasi melalui screener profesional.
2. **Kombinasi Pengukuran Kuantitatif Terpadu:**
   - Pengukuran SUS 10-butir lengkap pada akhir sesi.
   - Pengukuran UMUX-Lite sebagai checkpoint cepat di sela-sela skenario tugas filtrasi inventaris global.
   - Heatmap fiksasi visual (*eye-tracking simulation / click-path tracking*) untuk mendeteksi *dwell time* pada elemen grafik.
3. **Hasil & Eksekusi Arsitektural:**
   - Desain Modular Widget menghasilkan skor SUS $82.4$ (Grade A) dibandingkan desain linear ($68.2$).
   - Analisis korelasi menunjukkan bahwa eliminasi navigasi hierarki bertingkat (*deep-nested side navigation*) menjadi pendorong utama kenaikan persepsi efisiensi sistem. Manajemen mengesahkan pembaruan antarmuka ke produksi berdasarkan bukti data kuantitatif yang tak terbantahkan.

---

## Bagian 4: Practical Chapter Challenge (1 Tantangan Komprehensif)

### Tantangan: Perancangan Usability Test Protocol & Dashboard Analisis Metrik E-Commerce Multi-Vendor

#### Deskripsi Misi
Anda ditunjuk sebagai Lead UX Researcher untuk merancang dan mengeksekusi dokumen **Usability Test Plan & Evaluasi Kuantitatif Terpadu** pada fitur checkout dan pelacakan pesanan aplikasi e-commerce enterprise multi-vendor.

#### Kebutuhan & Deliverable Wajib:
1. **Dokumen Screener Partisipan:**
   - Definisikan kriteria inklusi dan eksklusi ketat untuk merekrut 10 partisipan moderated (5 segmen tech-savvy, 5 segmen pengguna awam/usia 50+).
   - Sertakan minimal 4 pertanyaan filter dengan logika eliminasi (*disqualifying options*).
2. **Task Scenario Terstruktur:**
   - Rancang 3 skenario tugas realistis dengan penentuan kriteria objektif keberhasilan (*Success Stopping Conditions*):
     - *Task A:* Mencari barang dengan 2 filter spesifik dan menambahkan ke keranjang belanja.
     - *Task B:* Melakukan checkout menggunakan voucher diskon dan metode pembayaran split.
     - *Task C:* Mengunduh bukti faktur pajak pesanan dari riwayat transaksi.
3. **Log Lembar Observasi Data (Observation Sheet Structure):**
   - Kolom tabel wajib memuat: ID Partisipan, Status Task (Pass/Fail biner), Time-on-Task (detik), SEQ Score (1–7), Kategori Kesalahan (*Slip / Mistake*), Skor SUS 10-butir, dan Catatan Kualitatif Verbatim.
4. **Formula & Template Spreadsheet Perhitungan:**
   - Sertakan kalkulasi formula matematis dalam format pseudocode / formula spreadsheet (Excel/Google Sheets) untuk menghitung:
     - Rata-rata TCR beserta Margin of Error Adjusted Wald ($95\%$ CI).
     - Geometric Mean untuk Time-on-Task.
     - Normalisasi Skor SUS final per partisipan dan rata-rata kelompok.

#### Rubrik Penilaian Keberhasilan:
| Komponen Evaluasi | Bobot | Kriteria Kelulusan Mutlak |
| :--- | :--- | :--- |
| **Screener & Skenario** | 30% | Bebas dari leading questions, stopping condition terdefinisi secara biner dan terukur tanpa bias subjektif fasilitator. |
| **Penerapan Metrik Standar** | 40% | Penggunaan SEQ pasca-tugas dan SUS pasca-sesi dihitung dengan formula normalisasi yang tepat tanpa manipulasi bobot. |
| **Validasi Statistik** | 30% | Penerapan Geometric Mean untuk ToT dan penanganan confidence interval sampel kecil menggunakan Adjusted Wald secara akurat. |

---

## Bagian 5: Checklist Pemahaman Konsep (Knowledge Check)

Gunakan checklist ini untuk memverifikasi kesiapan operasional Anda sebelum mengeksekusi usability testing di lingkungan produksi:

- [ ] **Distribusi Sampel:** Memahami batasan *rule-of-thumb* 5 partisipan Jakob Nielsen (hanya berlaku untuk formative/qualitative testing) dan kebutuhan $n \ge 30\text{--}40$ untuk sumatif/benchmark.
- [ ] **Kalkulasi SUS Bebas Error:** Menguasai konversi ganjil $(x - 1)$, genap $(5 - x)$, pengali total $2.5$, serta memahami bahwa skor SUS adalah persentil/peringkat kualitas, bukan nilai persentase benar-salah.
- [ ] **Pemberian SEQ Akurat:** Memastikan kuesioner SEQ diberikan tepat setelah tugas berakhir sebelum fasilitator beralih ke skenario berikutnya.
- [ ] **Penanganan Outlier Durasi:** Tidak lagi menggunakan rata-rata aritmetika biasa untuk Time-on-Task ketika terdapat sebaran data dengan skewness tinggi.
- [ ] **Klasifikasi Usability Error:** Mampu membedakan secara tegas antara *Slip* (kesalahan eksekusi motorik/perhatian pada alur yang dipahami) dan *Mistake* (kesalahan model mental akibat desain informasi yang menyesatkan).
- [ ] **Etika & Netralitas Penguji:** Menjalankan protokol fasilitasi tanpa membimbing (*leading*), tanpa mengoreksi pilihan pengguna saat pengujian berlangsung, dan menjamin netralitas data observasi.
