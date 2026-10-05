# BAB-02-User-Research-Rekayasa-Kuantitatif-dan-Kualitatif: Quiz, Challenge, & Knowledge Check

Dokumen evaluasi mandiri ini dirancang untuk menguji penguasaan metodologi user research tingkat lanjut, validasi data analitik kuantitatif, analisis tematik kualitatif, serta penerapan triangulasi data pada sistem frontend berskala enterprise.

---

## Bagian 1: Basic Questions (5 Soal Teoretis & Konseptual)

### Pertanyaan 1: Perbedaan Metrik Kualitatif vs Kuantitatif
**Soal:** Jelaskan perbedaan mendasar antara *generative research* (kualitatif) dan *evaluative research* (kuantitatif) dalam siklus hidup produk digital, serta sebutkan masing-masing 2 metrik representatif!

<details>
<summary>Jawaban & Pembahasan</summary>

* **Generative Research (Kualitatif):**
  * **Tujuan:** Mengidentifikasi masalah pengguna yang belum terartikulasi, kebutuhan laten, motivasi, serta model mental pengguna sebelum fitur dikembangkan (*exploratory phase*).
  * **Metrik/Artefak:** Mental Model Affinity Map, Kategori Masalah Emosional (Pain Points), Friction Count, Empathy Map.
* **Evaluative Research (Kuantitatif):**
  * **Tujuan:** Mengukur efektivitas, efisiensi, dan kepuasan terhadap solusi desain yang sudah diimplementasikan atau diprototipekan secara empiris.
  * **Metrik/Artefak:** System Usability Scale (SUS), Time on Task (ToT), Task Success Rate (TSR), Single Ease Question (SEQ), Core Web Vitals (INP/LCP) impact.
</details>

---

### Pertanyaan 2: Formula & Benchmark System Usability Scale (SUS)
**Soal:** Bagaimana formula matematis normalisasi skor System Usability Scale (SUS) 10 pertanyaan Likert 1–5, dan berapa benchmark skor standar industri untuk predikat "Good" (*acceptable*)?

<details>
<summary>Jawaban & Pembahasan</summary>

* **Formula Normalisasi:**
  * Pertanyaan ganjil (positif, item $1, 3, 5, 7, 9$): Skor kontribusi = $\text{Nilai Respons} - 1$.
  * Pertanyaan genap (negatif, item $2, 4, 6, 8, 10$): Skor kontribusi = $5 - \text{Nilai Respons}$.
  * Skor total SUS:
    $$\text{Skor SUS} = \left(\sum \text{Skor Kontribusi Ganjil} + \sum \text{Skor Kontribusi Genap}\right) \times 2.5$$
  * Skala akhir bernilai 0 hingga 100.
* **Benchmark Industri (Sauro & Lewis):**
  * Rata-rata global SUS adalah **68**.
  * Skor $\ge 68$ masuk kategori *Average / Acceptable*.
  * Skor $\ge 80.3$ diklasifikasikan sebagai *Good / Excellent* (Grade A).
</details>

---

### Pertanyaan 3: Prinsip Triangulasi Data (Mixed-Methods)
**Soal:** Mengapa data telemetri kuantitatif (seperti drop-off funnel di Google Analytics/Mixpanel) tidak boleh digunakan sendirian untuk merekayasa ulang alur checkout pengguna tanpa validasi kualitatif?

<details>
<summary>Jawaban & Pembahasan</summary>

Data telemetri kuantitatif hanya menjawab pertanyaan **"Apa yang terjadi"** (*What*) dan **"Di mana pengguna keluar"** (*Where*), namun mengalami kebutaan (*blind spot*) terhadap **"Mengapa masalah tersebut terjadi"** (*Why*). 

Misalnya, lonjakan drop-off pada form pembayaran bisa diakibatkan oleh:
1. Validasi regex form kartu kredit yang terlalu ketat (isu teknis).
2. Ketidakpercayaan terhadap gateway pembayaran baru (isu psikologis/trust).
3. Biaya admin tersembunyi yang baru muncul di langkah akhir (isu transparansi harga).

Mengubah alur checkout tanpa usability testing atau contextual inquiry kualitatif berisiko tinggi memecahkan symptom yang salah (*false problem framing*).
</details>

---

### Pertanyaan 4: Sample Size Rule of Thumb (Jakob Nielsen)
**Soal:** Berdasarkan riset Jakob Nielsen dan Tom Landauer, mengapa pengujian usability kualitatif terhadap 5 pengguna dianggap mampu menemukan ~85% masalah kegunaan produk?

<details>
<summary>Jawaban & Pembahasan</summary>

Hubungan antara jumlah partisipan ($n$) dan proporsi masalah kegunaan yang ditemukan ($N$) dimodelkan melalui formula probabilitas binomial:
$$N = 1 - (1 - L)^n$$
di mana $L$ adalah probabilitas ditemukannya suatu masalah kegunaan oleh satu pengguna (tipikalnya $L \approx 0.31$ untuk usability study umum).

* Dengan $n = 5$:
  $$N = 1 - (1 - 0.31)^5 = 1 - (0.69)^5 \approx 1 - 0.156 \approx 84.4\%$$
* Menambahkan responden melampaui 5 partisipan dalam satu siklus iterasi menghasilkan pengulangan temuan (*diminishing marginal returns*). Alokasi sumber daya lebih efektif dialihkan ke siklus *test-iterate-test* ulang daripada menguji 15 partisipan sekaligus dalam satu putaran.
</details>

---

### Pertanyaan 5: Thematic Analysis Coding Framework
**Soal:** Jelaskan 3 tingkatan pengkodean (*coding*) dalam analisis tematik transkrip wawancara kualitatif: *Open Coding*, *Axial Coding*, dan *Selective Coding*!

<details>
<summary>Jawaban & Pembahasan</summary>

1. **Open Coding:** Tahap dekonstruksi teks mentah menjadi fragmen-fragmen konsep diskrit. Peneliti memberi label kode deskriptif awal langsung pada kutipan verbatim pengguna tanpa prasangka relasional.
2. **Axial Coding:** Tahap sintesis di mana kode-kode hasil *open coding* dikelompokkan ke dalam kategori, subkategori, dan dimensi hubungan sebab-akibat (kondisi, aksi, konsekuensi).
3. **Selective Coding:** Tahap integrasi tingkat tinggi di mana satu atau dua kategori inti (*core categories*) dipilih untuk merumuskan teori terpadu atau *insight driver* utama dari studi penelitian.
</details>

---

## Bagian 2: Intermediate Questions (5 Soal Analisis & Metodologi)

### Pertanyaan 6: Statistical Significance & Sample Size A/B Testing
**Soal:** Sebuah tim frontend ingin menguji varian CTA baru dengan tingkat konversi baseline $p_1 = 5\%$. Mereka menginginkan Minimum Detectable Effect (MDE) absolut $+1\%$ (menjadi $6\%$) dengan $\alpha = 0.05$ (tingkat signifikansi 95%) dan Statistical Power $1 - \beta = 0.80$. Berapa estimasi ukuran sampel minimum per varian dan bagaimana mitigasi terhadap *peeking problem*?

<details>
<summary>Jawaban & Pembahasan</summary>

* **Perhitungan Sampel Minimum (Pendekatan Evan Miller / Two-Proportion Z-Test):**
  * Formula standar:
    $$n = \frac{(Z_{\alpha/2}\sqrt{2\bar{p}(1-\bar{p})} + Z_{\beta}\sqrt{p_1(1-p_1) + p_2(1-p_2)})^2}{(p_2 - p_1)^2}$$
    di mana $p_1 = 0.05$, $p_2 = 0.06$, $\bar{p} = 0.055$, $Z_{\alpha/2} = 1.96$, $Z_{\beta} = 0.84$.
  * Hasil perhitungan menghasilkan sekitar **$\approx 11.000$ pengguna unik per varian** (total $22.000$ sampel).
* **Mitigasi Peeking Problem (P-Hacking):**
  * Mengintip nilai $p$-value setiap hari dan menghentikan pengujian segera saat $p < 0.05$ melipatgandakan False Positive Rate secara dramatis (hingga $>30\%$).
  * **Solusi Teknis:**
    1. Menerapkan *Fixed-Horizon Testing*: Sampel dikumpulkan hingga kuota minimum tercapai sebelum analisis dilakukan.
    2. Menggunakan algoritma *Sequential Testing* (misalnya *mSPRT - Mixture Sequential Probability Ratio Test*) yang memperbarui interval kepercayaan secara dinamis tanpa meningkatkan Type I Error.
</details>

---

### Pertanyaan 7: Konstruksi Single Ease Question (SEQ) vs NASA-TLX
**Soal:** Kapan seorang UX Engineer harus memilih Single Ease Question (SEQ) dibandingkan National Aeronautics and Space Administration Task Load Index (NASA-TLX) saat mengukur beban kognitif pengguna pada alur form kompleks?

<details>
<summary>Jawaban & Pembahasan</summary>

* **Single Ease Question (SEQ):**
  * Instrumen 1 pertanyaan 7-skala Likert (*"Secara keseluruhan, seberapa mudah atau sulit tugas ini?"*).
  * **Kapan digunakan:** Evaluasi cepat post-task pada usability testing alur umum (e.g. pendaftaran akun, filter katalog) yang membutuhkan gangguan minimal terhadap ritme interaksi partisipan.
* **NASA-TLX (Task Load Index):**
  * Instrumen multidimensi yang membedah 6 subskala: Beban Mental (*Mental Demand*), Beban Fisik (*Physical Demand*), Kebutuhan Waktu (*Temporal Demand*), Performa (*Performance*), Usaha (*Effort*), dan Frustrasi (*Frustration*).
  * **Kapan digunakan:** Alur kerja kognitif tinggi spesialis (seperti form underwriting asuransi multi-step, cockpit dashboard finansial B2B, atau modul audit kepatuhan cloud) di mana desainer perlu mendeteksi apakah friksi berasal dari tekanan waktu, kompleksitas logika, atau frustrasi teknis.
</details>

---

### Pertanyaan 8: Heatmap vs Event Tracking Analytics Discrepancy
**Soal:** Sebuah alat heatmap (Hotjar/FullStory) menunjukkan 80% klik pengguna terkonsentrasi pada tombol "Download Invoice", namun analitik database backend hanya mencatat 25% pengunduhan sukses. Analisis potensi akar permasalahan frontend dan UX research tracking anomaly ini!

<details>
<summary>Jawaban & Pembahasan</summary>

Akar permasalahan dapat diidentifikasi dari dua dimensi:

1. **Rage Clicking / Dead Clicks (UX Defect):**
   * Pengguna mengklik tombol berkali-kali karena ketiadaan visual feedback (*loading state* / disabled status). Alat heatmap mencatat raw cursor click event, mendistorsi rasio intensitas interaksi.
2. **Asinkronitas Client-Side vs Server-Side:**
   * Tombol memicu JavaScript error (misalnya `Unhandled Promise Rejection` saat payload faktur diekstrak), atau popup blocker browser memblokir `window.open(invoiceBlobUrl)`.
3. **Tracking Instrumentation Gap:**
   * Heatmap melacak DOM `click` event pada level pointer, sedangkan analitik backend melacak `HTTP 200 OK` respons stream download. Jika pengguna menutup tab sebelum transmisi blob 2MB selesai di jaringan seluler lambat, klik tercatat tinggi tetapi konversi server nihil.
</details>

---

### Pertanyaan 9: Eliminasi Bias Konfirmasi dalam User Interview
**Soal:** Ubah 3 pertanyaan riset yang bias (*leading questions*) berikut menjadi format netral, berbasis perilaku riil (*behavioral-based*):
1. *"Apakah Anda menyukai tampilan dashboard baru yang lebih bersih ini?"*
2. *"Seberapa sering Anda merasa frustrasi dengan fitur pencarian yang lambat?"*
3. *"Apakah Anda bersedia membayar Rp50.000 jika kami menambahkan fitur ekspor PDF otomatis?"*

<details>
<summary>Jawaban & Pembahasan</summary>

1. **Revisi 1:**
   * *Bias:* Mengarahkan partisipan menyetujui bahwa tampilan lebih bersih (*acquiescence bias*).
   * *Netral:* *"Ceritakan impresi pertama Anda saat melihat layar ringkasan ini dan apa yang menarik perhatian Anda pertama kali?"*
2. **Revisi 2:**
   * *Bias:* Mengasumsikan pengguna frustrasi dan pencarian lambat (*framing effect*).
   * *Netral:* *"Ceritakan pengalaman terakhir kali Anda mencari data dokumen di platform ini. Apa langkah-langkah yang Anda ambil dan kendala apa yang Anda temui jika ada?"*
3. **Revisi 3:**
   * *Bias:* Menanyakan niat hipotetis di masa depan (*speculative bias* yang tidak berkorelasi dengan perilaku nyata).
   * *Netral:* *"Bagaimana cara Anda membagikan laporan keuangan saat ini ke pihak manajemen? Berapa alokasi biaya atau waktu manual yang Anda habiskan untuk proses tersebut minggu lalu?"*
</details>

---

### Pertanyaan 10: Skema Pengukuran INP (Interaction to Next Paint) dalam Framework UX
**Soal:** Mengapa Interaction to Next Paint (INP) diklasifikasikan sebagai metrik UX kuantitatif kritikal, dan bagaimana korelasi psikologis delay render frame terhadap persepsi *System Responsiveness* pengguna?

<details>
<summary>Jawaban & Pembahasan</summary>

* **Definisi Teknis INP:** INP mengukur latensi keseluruhan dari interaksi pengguna (klik, ketukan, atau input keyboard) hingga browser menyajikan frame grafis visual berikutnya di layar (*next paint*). Durasi ini mencakup:
  $$\text{INP} = \text{Input Delay} + \text{Processing Time (Event Handlers)} + \text{Presentation Delay}$$
* **Korelasi Psikologis (Nielsen/Card's Law of Response Time):**
  * **$<100\text{ ms}$:** Pengguna mempersepsikan respons sistem bersifat instan (*immediate causality*). Persepsi manipulasi langsung terjaga.
  * **$100\text{ ms} - 300\text{ ms}$:** Pengguna mulai menyadari jeda mekanis (*subtle drag*). INP di atas 200ms menurunkan kepuasan kegunaan dan meningkatkan keraguan interaksi.
  * **$>1000\text{ ms}$:** Fokus mental pengguna terputus (*attention degradation*), sering memicu klik berulang (*rage click*) yang memperparah kemacetan main-thread browser.
</details>

---

## Bagian 3: Real-World Production Case Scenarios (3 Studi Kasus)

### Kasus 1: Anomali Drop-off Form Registrasi Fintech Multistep
**Latar Belakang:**
Sebuah aplikasi web fintech B2B mencatat conversion rate form onboarding Know Your Business (KYB) turun dari $18.4\%$ menjadi $7.1\%$ setelah rilis refactoring arsitektur formulir dari monolith form menjadi dynamic multistep wizard dengan validasi asynchronous (API sandbox verifikasi NPWP dan rekening bank).

**Data Telemetri:**
* Mixpanel Funnel: Step 1 (Company Details) 92% selesai, Step 2 (Document Upload) 88% selesai, Step 3 (Beneficial Owner & Bank Validation) drop-off mencapai 78%.
* Sentry Error Monitoring: Tidak ada log fatal JavaScript runtime error.

**Tugas Analisis:**
1. Desain protokol riset cepat (48 jam) untuk menemukan akar penyebab masalah.
2. Analisis potensi bottleneck interaksi pada Step 3 dari perspektif kognitif dan teknis.
3. Rancang rencana mitigasi arsitektur frontend UX.

<details>
<summary>Solusi Teknis & Resolusi Riset</summary>

#### 1. Protokol Riset Cepat (48 Jam):
* **Sesi 1 (Jam 0-12): Session Replay Audit.** Sampling 30 rekaman sesi pengguna yang terhenti di Step 3 menggunakan FullStory/LogRocket. Identifikasi kursor hovering berulang, dead clicks, dan durasi dwell time pada input form tertentu.
* **Sesi 2 (Jam 13-30): Moderated Think-Aloud Usability Test.** Rekrut 5 representasi staf finance/legal perusahaan klien. Berikan skenario pengisian data dummy di staging environment. Rekam verbalisasi kendala mental mereka.
* **Sesi 3 (Jam 31-48): Network & Async Payload Profiling.** Observasi waterfall API verifikasi perbankan pada throttling jaringan 3G/Slow 4G.

#### 2. Akar Masalah yang Terungkap:
* **Bottleneck Teknis:** Validasi asynchronous rekening bank dipicu pada event `onBlur`. API verifikasi backend membutuhkan waktu respons $4.2\text{ detik}$. Selama jeda ini, tombol "Lanjut" dinonaktifkan tanpa indikator visual loader spesifik pada field terkait.
* **Bottleneck Kognitif:** Pengguna menganggap aplikasi mengalami hang/freeze saat mengklik tombol submit, lalu menekan tombol kembali (*browser back button*), yang menghapus state Redux form karena ketiadaan persistensi localStorage/sessionStorage.

#### 3. Rencana Mitigasi Arsitektur Frontend:
* Menerapkan *Optimistic Visual Feedback* dan inline skeleton spinner pada field yang sedang divalidasi async.
* Terapkan debouncing pada input validation dan jangan memblokir tombol utama jika validasi sekunder dapat di-defer ke review modal.
* Implementasikan form state persistence di browser cache (IndexedDB / encrypted sessionStorage) agar ketika pengguna melakukan refresh atau navigasi mundur, input dokumen tidak hilang.
</details>

---

### Kasus 2: Konflik Interpretasi Redesign Katalog E-Commerce B2B
**Latar Belakang:**
Tim Desain mengusulkan redesign radikal antarmuka katalog e-commerce B2B dari tampilan *Dense Data Table* (tabel tabular padat informasi dengan 15 kolom) menjadi *Modern Visual Cards* (grid kartu produk dengan gambar resolusi tinggi dan visual whitespace lebar).

**Hasil Uji Pengguna Awal:**
* Pengguna retail internal (manajemen) memuji tampilan kartu baru karena estetik dan modern.
* Tim Sales and Procurement Enterprise (daya beli 80% GMV) menyatakan penolakan keras dalam sesi survei kualitatif pertama dan mengancam beralih ke vendor kompetitor.

**Tugas Analisis:**
1. Bedah benturan *mental model* antara persona pengambil keputusan internal vs *power user* enterprise procurement.
2. Evaluasi metrik kuantitatif yang salah dipilih oleh tim produk dalam menilai keberhasilan redesign.
3. Rumuskan solusi UX arsitektur yang mengomodasi kedua kebutuhan.

<details>
<summary>Solusi Teknis & Resolusi Riset</summary>

#### 1. Analisis Benturan Model Mental:
* **Persona Kasual / Manajemen:** Mengonsumsi katalog untuk eksplorasi visual, apresiasi branding, dan browsing santai (*discovery mindset*).
* **Power User (Procurement Specialist):** Bekerja berdasarkan transaksi massal (*transactional efficiency mindset*). Mereka menghafal SKU, membandingkan ketersediaan stok antar-gudang secara lintas baris, dan membutuhkan komparasi harga volume grosir secara simultan tanpa paginasi panjang atau scroll vertikal ekstrem. Tampilan kartu menurunkan densitas informasi hingga 70%, memperlambat *Task Completion Time* mereka dari 45 detik menjadi 4 menit.

#### 2. Kesalahan Metrik Tim Produk:
* Tim mengandalkan metrik vanity estetika: Skor *Attractiveness* (UEQ) dan feedback impresi visual surface-level.
* Tim mengabaikan metrik inti efisiensi kerja: *Task Completion Time (TCT)*, *Information Density Ratio*, *Keyboard Navigation Feasibility*, dan *Error Rate in Batch Ordering*.

#### 3. Rekayasa Solusi UX:
* Bangun *View Toggle Architecture* yang persisten pada preferensi pengguna (`localStorage` / user profile preference):
  * **Compact Data Grid View:** Standar untuk procurement (fitur inline batch edit, freeze column SKU/Harga, bulk checkbox, navigasi full keyboard arrow).
  * **Visual Gallery View:** Untuk pengguna eksploratif dan katalog presentasi client.
* Tetapkan *Compact Grid* sebagai konfigurasi default untuk akun korporat berdasar *User Role RBAC*.
</details>

---

### Kasus 3: Bias Survivor pada Survei Churn Dashboard SaaS
**Latar Belakang:**
Sebuah platform SaaS manajemen proyek mencatat penurunan retensi pengguna 30 hari sebesar 40%. Tim Product Operations menyebarkan pop-up survei kepuasan NPS (Net Promoter Score) di dalam aplikasi (*in-app survey*) kepada seluruh pengguna aktif di hari ke-25, menghasilkan skor NPS fantastis sebesar +62 ("World Class").

**Masalah:**
Meskipun skor NPS sangat tinggi, tingkat pembatalan langganan di bulan berikutnya tetap membengkak (*churn rate climbing*). Tim eksekutif bingung atas diskrepansi antara metrik kepuasan dan realitas bisnis.

**Tugas Analisis:**
1. Identifikasi cacat metodologis sampling riset (*sampling bias/survivorship bias*) dalam studi kasus ini.
2. Rancang arsitektur telemetri deteksi *early-churn signals* di sisi client frontend.
3. Rancang kerangka riset *Exit / Churn Interview* yang valid secara saintifik.

<details>
<summary>Solusi Teknis & Resolusi Riset</summary>

#### 1. Cacat Metodologis Sampling:
* **Survivorship Bias (Bias Penyintas):** Survei pop-up yang diberikan di dalam dashboard pada hari ke-25 hanya ditangkap oleh pengguna yang masih aktif membuka platform. Pengguna yang kecewa, frustrasi, atau tidak menemukan value produk sudah berhenti login (*dormant/abandoned*) sejak hari ke-3 hingga hari ke-7.
* Sampel survei hanya merefleksikan pendapat kelompok penggemar fanatik (*survivors*), mengabaikan 100% populasi yang berisiko churn.

#### 2. Telemetri Deteksi Sinyal Dini Churn (Frontend Tracking):
* Pasang event tracking proaktif sebelum hari ke-14:
  * **Feature Breadth:** Jumlah modul inti yang disentuh dalam 7 hari pertama (e.g. `workspace_created`, `team_invited`, `task_board_configured`).
  * **Session Decay:** Pengurangan frekuensi login dari harian menjadi mingguan.
  * **Negative Interactions:** Deteksi rage clicks pada modul integrasi atau akses halaman dokumentasi API/bantuan yang berulang tanpa penyelesaian tugas.

#### 3. Kerangka Riset Churn Valid:
* **Automated Offboarding Capture:** Saat pengguna menekan "Cancel Subscription", tampilkan modal terstruktur 1-pertanyaan non-intrusif mengenai alasan faktual terminasi, dipasangkan dengan kompensasi wawancara 15 menit berinsentif (e.g., voucher gift card).
* **Out-of-Band Research Outreach:** Kirimkan undangan wawancara melalui email kepada pengguna yang tidak aktif selama 14 hari berturut-turut (*dormant users*), bukan mengandalkan pop-up in-app.
</details>

---

## Bagian 4: Practical Chapter Challenge

### Tantangan Laboratorium: Engineering User Research Engine & Analytics Validator
**Objective:** Mengembangkan modul validasi data usability testing kuantitatif berbasis TypeScript untuk menghitung metrik SUS, mendeteksi anomali skewness data respon, dan menyusun payload pelaporan riset terstandarisasi.

#### Spesifikasi Kebutuhan:
1. Buat class TypeScript `UsabilityMetricsCalculator` yang mengimplementasikan:
   * Perhitungan skor SUS valid dari array 10 respons (skala 1-5).
   * Validasi integritas respons (mendeteksi *straight-lining bias* di mana responden mengisi angka 5 atau 1 secara monoton pada seluruh pertanyaan).
   * Transformasi skor SUS ke Grade Skala Nilai (A, B, C, D, F) dan persentil konversi empiris Sauro-Lewis.
2. Sediakan mock unit test data yang mendemonstrasikan penghitungan skor valid dan pelemparan exception pada input cacat.

```typescript
// Implementasi Solusi Acuan
export interface SUSResponse {
  respondentId: string;
  answers: [number, number, number, number, number, number, number, number, number, number];
}

export type SUSGrade = 'A+' | 'A' | 'B' | 'C' | 'D' | 'F';

export interface SUSAnalysisResult {
  respondentId: string;
  rawScore: number;
  grade: SUSGrade;
  isAcceptable: boolean;
  straightLiningDetected: boolean;
}

export class UsabilityMetricsCalculator {
  public static calculateSUS(response: SUSResponse): SUSAnalysisResult {
    const { answers, respondentId } = response;

    if (answers.length !== 10) {
      throw new Error(`Incomplete SUS response: expected 10 items, received ${answers.length}`);
    }

    // Validasi range 1-5
    for (const val of answers) {
      if (!Number.isInteger(val) || val < 1 || val > 5) {
        throw new Error(`Invalid Likert value: ${val}. All responses must be integers between 1 and 5.`);
      }
    }

    // Deteksi Straight-Lining Bias (seluruh jawaban identik)
    const firstVal = answers[0];
    const isStraightLining = answers.every(v => v === firstVal);

    // Kalkulasi Kontribusi
    // Odd items (0, 2, 4, 6, 8): Item Score - 1
    // Even items (1, 3, 5, 7, 9): 5 - Item Score
    let sumOdd = 0;
    let sumEven = 0;

    for (let i = 0; i < 10; i++) {
      if (i % 2 === 0) {
        sumOdd += (answers[i] - 1);
      } else {
        sumEven += (5 - answers[i]);
      }
    }

    const rawScore = (sumOdd + sumEven) * 2.5;

    return {
      respondentId,
      rawScore,
      grade: this.resolveGrade(rawScore),
      isAcceptable: rawScore >= 68,
      straightLiningDetected: isStraightLining,
    };
  }

  private static resolveGrade(score: number): SUSGrade {
    if (score >= 84.1) return 'A+';
    if (score >= 80.3) return 'A';
    if (score >= 74.0) return 'B';
    if (score >= 68.0) return 'C';
    if (score >= 51.0) return 'D';
    return 'F';
  }
}

// Simulasi Demonstrasi Eksekusi
const sampleValidResponse: SUSResponse = {
  respondentId: 'USR-001',
  answers: [5, 1, 4, 2, 5, 1, 4, 2, 5, 1] // Pola pengalaman sangat positif
};

const sampleBiasedResponse: SUSResponse = {
  respondentId: 'USR-002',
  answers: [3, 3, 3, 3, 3, 3, 3, 3, 3, 3] // Straight-lining neutral
};

console.log('Result USR-001:', UsabilityMetricsCalculator.calculateSUS(sampleValidResponse));
console.log('Result USR-002:', UsabilityMetricsCalculator.calculateSUS(sampleBiasedResponse));
```

#### Kriteria Keberhasilan (Acceptance Criteria):
* [ ] Modul menolak secara tegas respon bernilai di luar batas [1..5].
* [ ] Skor SUS untuk jawaban maksimal positif `[5, 1, 5, 1, 5, 1, 5, 1, 5, 1]` tepat bernilai 100.
* [ ] Skor SUS untuk jawaban maksimal negatif `[1, 5, 1, 5, 1, 5, 1, 5, 1, 5]` tepat bernilai 0.
* [ ] Flag `straightLiningDetected` bernilai `true` saat variasi jawaban adalah 0.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan rubrik berikut untuk memverifikasi kesiapan kompetensi rekayasa user research Anda:

- [ ] **Fondasi Teoretis:** Saya dapat membedakan kapan menggunakan metode kuantitatif (analitik, SUS, A/B testing) vs kualitatif (in-depth interview, think-aloud usability testing) tanpa mencampuradukkan tujuan riset.
- [ ] **Kalkulasi Metrik UX:** Saya memahami secara matematis pembobotan ganjil-genap skor SUS dan mampu menerjemahkan skor mentah ke persentil Sauro-Lewis.
- [ ] **Formulasi Pertanyaan Netral:** Saya mampu menyusun panduan wawancara (*interview guide*) yang bebas dari leading questions, confirmation bias, dan framing effect.
- [ ] **Triangulasi Data Produksi:** Saya dapat mengkorelasikan log analitik client-side, visual telemetry heatmap, dan log error backend untuk mengisolasi titik friksi nyata pada alur navigasi aplikasi.
- [ ] **Mitigasi Sampling Bias:** Saya mampu mengidentifikasi cacat metodologi pengumpulan data (seperti survivorship bias dan peeking problem) serta merancang arsitektur telemetri yang valid.
