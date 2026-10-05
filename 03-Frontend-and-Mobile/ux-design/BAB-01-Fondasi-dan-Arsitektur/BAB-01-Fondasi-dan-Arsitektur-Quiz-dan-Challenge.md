# BAB-01-Fondasi-dan-Arsitektur: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi mandiri, verifikasi pemahaman konseptual, dan penerapan praktis dari prinsip **Fondasi UX & Arsitektur Informasi (IA)** dalam rekayasa produk digital modern skala produksi.

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1: Definisi & Boundary UX vs UI
Dalam siklus rekayasa perangkat lunak, manakah pernyataan berikut yang paling tepat membedakan peran *User Experience (UX)* dan *User Interface (UI)*?
- **A.** UX hanya berfokus pada estetika visual, warna, dan tipografi; sedangkan UI berfokus pada performa query database.
- **B.** UX berfokus pada pemahaman masalah pengguna, alur navigasi, model mental, dan kegunaan sistem; sedangkan UI berfokus pada implementasi representasi visual interaktif, tata letak, hierarki tipografi, dan konsistensi elemen desain.
- **C.** UX dibuat setelah koding frontend selesai, sedangkan UI dibuat sebelum arsitektur sistem dirancang.
- **D.** UX dan UI adalah entitas yang identik dan tidak membutuhkan pemisahan metodologi dalam software development lifecycle (SDLC).

> **Kunci Jawaban:** **B**  
> **Pembahasan:** UX mencakup seluruh spektrum pengalaman pengguna secara holistik (identifikasi friksi, *journey map*, arsitektur informasi, heuristik usability), sedangkan UI merupakan lapisan visual konkret (*visual presentation layer*) yang memfasilitasi interaksi pengguna dengan fungsionalitas sistem.

---

### Soal 2: Hukum Hick (Hick's Law)
Hukum Hick menyatakan bahwa waktu yang dibutuhkan seseorang untuk mengambil keputusan berbanding lurus dengan logaritma dari jumlah pilihan yang tersedia ($T = b \cdot \log_2(n + 1)$). Penerapan arsitektural yang paling efektif dari hukum ini pada navigasi produk kompleks adalah:
- **A.** Menampilkan semua opsi menu level 1 hingga level 4 sekaligus di *sidebar navigation* tanpa grouping.
- **B.** Menerapkan *progressive disclosure*, kategorisasi hierarkis berbasis taksonomi yang logis, dan menyederhanakan *decision points* kritis.
- **C.** Mengganti semua input navigasi dengan modal dialog berlapis (*stacked modals*).
- **D.** Menghapus sistem pencarian dan memaksa pengguna mengklik setiap link.

> **Kunci Jawaban:** **B**  
> **Pembahasan:** *Progressive disclosure* dan pengelompokan opsi hierarkis membatasi jumlah pilihan simultan yang harus diproses pengguna dalam satu waktu, meminimalkan *decision fatigue* dan mempercepat *time-to-action*.

---

### Soal 3: Komponen Inti Information Architecture (IA)
Menurut Lou Rosenfeld dan Peter Morville, empat sistem utama yang membentuk Information Architecture (IA) adalah:
- **A.** HTML, CSS, JavaScript, dan WebAssembly.
- **B.** Routing System, Controller System, Model System, dan View System.
- **C.** Organization Systems, Labeling Systems, Navigation Systems, dan Search Systems.
- **D.** Wireframe System, Prototype System, Mockup System, dan Styleguide System.

> **Kunci Jawaban:** **C**  
> **Pembahasan:** Keempat sistem ini mendefinisikan bagaimana informasi distrukturkan dan dikelompokkan (*organization*), bagaimana istilah direpresentasikan kepada pengguna (*labeling*), bagaimana pengguna berpindah antar-konten (*navigation*), serta bagaimana pengguna menemukan konten spesifik (*search*).

---

### Soal 4: Cognitive Load Theory (Beban Kognitif)
Beban kognitif yang timbul akibat desain antarmuka yang buruk, instruksi navigasi yang membingungkan, atau hierarki visual yang kontrasnya tidak memadai disebut sebagai:
- **A.** *Intrinsic Cognitive Load*
- **B.** *Germane Cognitive Load*
- **C.** *Extraneous Cognitive Load*
- **D.** *Algorithmic Cognitive Load*

> **Kunci Jawaban:** **C**  
> **Pembahasan:** *Extraneous cognitive load* adalah beban mental yang disebabkan oleh cara informasi disajikan (elemen desain yang berantakan, inkonsistensi layout). Tujuannya adalah meminimalkan *extraneous load* agar kapasitas kerja mental pengguna terfokus pada tugas utama (*intrinsic*) dan pemahaman pola sistem (*germane*).

---

### Soal 5: Nielsen's Heuristic - Visibility of System Status
Contoh implementasi teknis yang benar dari prinsip heuristik *"Visibility of System Status"* saat pengguna mengunggah berkas batch berukuran 500MB adalah:
- **A.** Mengunci layar tanpa indikator visual sampai respons HTTP 200 OK diterima dari server.
- **B.** Menampilkan status loading spinner generik tanpa informasi persentase atau estimasi waktu.
- **C.** Menampilkan progress bar deterministik dengan metrik persentase upload, estimasi kecepatan transfer, indikasi status per berkas, dan feedback visual saat proses selesai.
- **D.** Mengarahkan pengguna langsung ke homepage tanpa memberi konfirmasi apakah upload sedang berjalan di background.

> **Kunci Jawaban:** **C**  
> **Pembahasan:** Sistem harus selalu memberikan informasi yang jelas, tepat waktu, dan relevan mengenai apa yang sedang terjadi di latar belakang (*feedback loop*) melalui indikator progres yang bermakna.

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 6: Analisis Mental Model vs Implementation Model
Jelaskan mengapa ketidaksesuaian (*mismatch*) antara *mental model* pengguna dan *implementation model* developer kerap menjadi penyebab utama kegagalan adopsi sistem enterprise (misal: sistem ERP atau CRM), serta bagaimana arsitek UX menjembatani kesenjangan ini!

> **Kunci Jawaban & Pembahasan:**  
> - *Implementation Model* mencerminkan bagaimana sistem bekerja secara teknis di balik layar (relasi tabel database, normalisasi data, mekanisme lock transaction, state machine API).
> - *Mental Model* adalah representasi kognitif pengguna mengenai bagaimana proses bisnis semestinya berjalan berdasarkan pengalaman hidup nyata dan alur kerja manual mereka.
> - Ketika UI memaparkan abstraksi teknis mentah (misal: error code foreign key violation, validasi database langsung di form tanpa kontekstualisasi, atau pembagian menu berdasarkan skema mikroservis alih-alih alur kerja fungsional), pengguna mengalami disorientasi kognitif.
> - **Solusi Arsitek UX:** Membuat *Conceptual Model* yang mencocokkan *mental model* pengguna melalui riset pengguna (*task analysis*, *card sorting*), menyembunyikan kompleksitas teknis internal (*encapsulation of mechanics*), serta merekayasa interaksi berbasis tugas (*task-oriented workflow*) alih-alih berbasis struktur database (*data-oriented interface*).

---

### Soal 7: Arsitektur Taksonomi: Flat vs Deep Hierarchy
Bandingkan trade-off struktural antara arsitektur navigasi *broad & shallow* (lebar tapi dangkal) dengan *narrow & deep* (sempit tapi dalam) pada katalog data e-commerce/B2B marketplace dengan lebih dari 100.000 SKU.

> **Kunci Jawaban & Pembahasan:**
> 1. **Broad & Shallow (Banyak opsi per level, kedalaman klik 2-3 level):**
>    - *Kelebihan:* Mengurangi kedalaman navigasi (*click depth*), meminimalkan risiko konten terisolasi (*dead-end pages*), dan mempercepat eksplorasi jika label kategori jelas.
>    - *Kekurangan:* Tingginya *visual noise* dan risiko pelanggaran Hukum Hick jika pengelompokan tidak memiliki struktur klaster yang tegas.
> 2. **Narrow & Deep (Sedikit opsi per level, kedalaman klik >5 level):**
>    - *Kelebihan:* Tampilan awal terlihat bersih dan minimalis (*low initial cognitive load*).
>    - *Kekurangan:* Risiko disorientasi spasial pengguna (*getting lost in hyperspace*), beban memori kerja tinggi (pengguna lupa jalur breadcrumb asal), dan meningkatnya bounce rate akibat gesekan navigasi (*navigational friction*).
> 3. **Rekomendasi Praktis Skala Produksi:** Pendekatan *poly-hierarchical* yang dipadukan dengan *faceted search/filtering engine*. Kategori utama dijaga pada kedalaman seimbang (maksimal 3-4 tingkat), sementara penjelajahan spesifik dialihkan ke facet metadata (atribut teknis, merek, varian).

---

### Soal 8: Trade-off Wireframe Fidelity dalam Iterasi Rekayasa
Kapan tim produk harus berhenti menggunakan *Low-Fidelity Wireframes* dan beralih ke *High-Fidelity Interactive Prototypes*? Analisis risiko jika transisi ke *high-fidelity* dilakukan terlalu dini pada fase discovery!

> **Kunci Jawaban & Pembahasan:**
> - **Waktu Transisi:** Transisi ke *high-fidelity* dilakukan ketika struktur informasi, alur navigasi inti (*user flows*), arsitektur fungsional, dan batasan teknis telah tervalidasi dan disepakati oleh stakeholder serta representasi pengguna.
> - **Risiko Transisi Terlalu Dini:**
>   1. *Sunk Cost Fallacy & Rigiditas:* Desainer dan developer enggan merombak alur yang salah karena sudah membuang banyak waktu memoles komponen UI, animasi, dan micro-interaction.
>   2. *Distraksi Feedback:* Stakeholder dan user tester cenderung mengomentari pilihan warna, ukuran font, dan visual artefak sekunder ketimbang memvalidasi apakah problem fungsional dan arsitektur logisnya sudah tepat.
>   3. *Pemborosan Resource Engineering:* Spesifikasi frontend rentan berubah drastis saat problem arsitektur dasar baru ditemukan belakangan.

---

### Soal 9: Information Foraging Theory & Scent of Information
Bagaimana prinsip *Information Foraging Theory* (khususnya konsep *information scent*) mempengaruhi desain navigasi, breadcrumbs, dan copywriting tombol aksi (*call-to-action*) pada platform analitik data?

> **Kunci Jawaban & Pembahasan:**
> - *Information Foraging Theory* menganalogikan pengguna web seperti predator yang berburu makanan: pengguna menilai probabilitas menemukan informasi berharga berdasarkan petunjuk visual dan tekstual (*information scent*) dengan energi kognitif sekecil mungkin.
> - **Implementasi Desain:**
>   - **Copywriting CTA:** Mengganti label ambigu (seperti *"Klik di Sini"* atau *"Submit"*) dengan kata kerja berbobot semantik tinggi (misal: *"Download Laporan Audit Q3 (PDF)"* atau *"Kalkulasi Margin Laba"*).
>   - **Breadcrumbs:** Memberikan jejak remah roti semantik yang memungkinkan pengguna mundur secara akurat tanpa kehilangan konteks analitik yang telah difilter.
>   - **Microcopy & Metadata Preview:** Menyediakan ringkasan singkat (*summary snippet*) atau indikator data di samping link navigasi agar pengguna dapat mengukur relevansi target sebelum melakukan navigasi.

---

### Soal 10: Fitts's Law pada Antarmuka Modern & Mobile Form Factor
Rumus Hukum Fitts adalah $MT = a + b \cdot \log_2\left(\frac{2D}{W}\right)$, di mana $D$ adalah jarak ke target (*distance*) dan $W$ adalah ukuran target (*width*). Analisis implikasi hukum ini terhadap penempatan *destructive actions* (misal: "Hapus Akun / Format Database") vs *primary conversion actions* pada antarmuka mobile!

> **Kunci Jawaban & Pembahasan:**
> - **Primary Conversion Actions:** Harus memiliki nilai $D$ yang kecil terhadap posisi istirahat ibu jari (*thumb zone* di area bawah layar) dan $W$ yang memadai (minimal tap target 48x48 dp/px sesuai pedoman WCAG/Material Design/HIG) untuk meminimalkan *Movement Time (MT)* dan friksi.
> - **Destructive Actions:** Memanfaatkan manipulasi nilai $D$ dan $W$ secara sengaja untuk mencegah kesalahan aksidental (*human error prevention*). Aksi destruktif ditempatkan di area dengan $D$ lebih jauh dari jangkauan instan ibu jari (misal: di dalam submenu atau pojok atas), diberikan ukuran tombol $W$ yang proporsional namun terpisah dari tombol konfirmasi, serta ditambahkan *friction gate* (seperti modal konfirmasi dengan pengetikan manual atau gesture *slide-to-confirm*).

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Kasus)

### Skenario 1: Krisis Drop-off Checkout SaaS B2B Multi-Step
**Konteks Masalah:**  
Sebuah platform SaaS B2B analitik logistik mengalami penurunan konversi (*drop-off*) sebesar 68% pada langkah pembayaran dan onboarding. Alur onboarding saat ini adalah wizard satu halaman panjang (*accordion-based*) berisi 32 kolom input, mencakup data personal, data legalitas entitas korporat, konfigurasi DNS server, dan nomor kartu kredit perusahaan.

**Tugas Evaluasi & Solusi:**
1. Identifikasi 3 masalah arsitektur informasi dan beban kognitif pada alur tersebut.
2. Usulkan rekonstruksi arsitektural menggunakan teknik *chunking* dan *progressive disclosure*.

> **Analisis Solusi Produksi:**
> 1. **Identifikasi Masalah:**
>    - *Violated Chunking & High Working Memory Load:* Menggabungkan input administratif (legal/billing) dengan konfigurasi teknis (DNS) membebani pengguna yang seringkali memiliki peran berbeda (*buyer* vs *engineer*).
>    - *Premature Friction:* Meminta konfigurasi infrastruktur DNS sebelum pengguna merasakan nilai inti (*time-to-value*) dari software.
>    - *Ambiguity of Progress:* Penggunaan accordion panjang menimbulkan ketidakpastian panjangnya alur kerja (*lack of explicit step progress*).
> 2. **Rencana Rekonstruksi:**
>    - **Fase 1: Minimal Viable Onboarding (Chunk 1):** Kurangi langkah awal menjadi hanya 3 field (Nama, Email Korporat, Password) + Verifikasi OTP/SSO. Akun langsung aktif dalam mode evaluasi.
>    - **Fase 2: Progressive Role Delegation (Chunk 2):** Pisahkan entitas pembayaran dengan setup teknis. Sediakan fitur *"Kirim tautan konfigurasi DNS ke Lead DevOps"* melalui email/link undangan.
>    - **Fase 3: Multi-step Wizard dengan Deterministic Progress:** Buat alur 3 langkah berurutan dengan progress bar persentase jelas: 1) Profil Perusahaan, 2) Metode Pembayaran/Trial Setup, 3) Integrasi Aset Pertama.

---

### Skenario 2: Kompleksitas Navigasi Portal Layanan Publik (GovTech)
**Konteks Masalah:**  
Portal terpadu satu pintu pemerintah daerah memiliki 420 layanan perizinan yang disusun murni berdasarkan struktur nama dinas birokrasi (misal: "Dinas Penanaman Modal", "Dinas Lingkungan Hidup", "Bagian Tata Ruang"). Warga mengeluh kebingungan menemukan izin pembukaan rintisan usaha kuliner karena izin limbah, izin bangunan, dan izin sanitasi berada di bawah 3 dinas yang berbeda.

**Tugas Evaluasi & Solusi:**
1. Analisis jenis kegagalan *labeling* dan *organization system* yang terjadi.
2. Rancang restrukturisasi Arsitektur Informasi menggunakan metode *User-Centric Task-Based Classification* dan *Open/Closed Card Sorting*.

> **Analisis Solusi Produksi:**
> 1. **Kegagalan Sistem:**
>    - *Internal Organization Bias:* Organisasi konten disusun berdasarkan struktur departemen internal (*silo birokrasi*), bukan berdasarkan tujuan hidup warga (*citizen mental model*).
>    - *Opaque Labeling:* Istilah hukum administrasi dinas yang kaku dan asing bagi masyarakat awam menciptakan *broken information scent*.
> 2. **Metodologi Restrukturisasi:**
>    - **Card Sorting Study:** Jalankan sesi *Hybrid Card Sorting* bersama perwakilan pelaku usaha mikro/UMKM dan warga umum untuk mengelompokkan 420 izin ke dalam klaster intuitif.
>    - **Task-Oriented Taxonomy:** Ganti hierarki berbasis dinas dengan klaster tematik berbasis peristiwa kehidupan (*Life Events / Business Life Cycles*):
>      - *Memulai Usaha Kuliner & Restoran* -> otomatis merangkum perizinan tempat, sanitasi, limbah, dan izin edar dalam satu bundle panduan interaktif.
>    - **Dual Navigation Track:** Sediakan navigasi utama berbasis *"Kebutuhan Saya"* (warga awam) dan sediakan filter lanjutan berbasis *"Dinas Pengampu"* hanya sebagai filter sekunder untuk pengguna auditor/birokrat.

---

### Skenario 3: Penurunan Metrik Usability pada Redesain Dashboard Fintech
**Konteks Masalah:**  
Sebuah aplikasi wealth management merilis tampilan baru yang sangat minimalis (tren *flat-neomorphism*). Namun, data post-launch menunjukkan *customer support ticket* melonjak 300% dengan keluhan utama: *"Di mana tombol transfer dan jual reksa dana?"* dan *"Saldo investasi saya tidak kelihatan apakah sedang untung atau rugi."*

**Tugas Evaluasi & Solusi:**
1. Tinjau kegagalan ini berdasarkan *Affordance & Signifiers* (Don Norman) dan *Visual Hierarchy*.
2. Rumuskan mitigasi desain cepat (*triage patch*) untuk mengembalikan kegunaan sistem tanpa membatalkan seluruh repositori desain.

> **Analisis Solusi Produksi:**
> 1. **Akar Masalah UX:**
>    - *Missing Signifiers:* Desain flat ekstrem menghilangkan batas tombol (*button boundaries*), drop-shadow elevasi, atau warna pembeda, sehingga elemen yang dapat diklik (*clickable affordance*) tampak seperti teks statis biasa.
>    - *Broken Visual Hierarchy & Information Scent:* Indikator performa portofolio (+/- persentase dan warna semantik merah/hijau yang kontras) diubah menjadi warna abu-abu monokromatik demi estetika, menghilangkan status visual kritis dalam satu pandangan (*glanceability failure*).
> 2. **Mitigasi Triage Patch:**
>    - **Restorasi Signifier Aksi:** Kembalikan kontras kontur dan elevasi pada aksi utama (*Primary Action: Beli / Jual / Tarik Saldo*) menggunakan warna aksen dominan berstandar rasio kontras WCAG AA (minimal 4.5:1).
>    - **Semantik Status Real-time:** Terapkan kembali kode visual universal untuk metrik finansial (indikator hijau/merah dengan penambahan ikon panah naik/turun untuk aksesibilitas pengguna buta warna).
>    - **Floating Quick-Action Hub:** Sediakan panel aksi cepat persisten di area bawah layar yang selalu terlihat saat pengguna membuka tab ringkasan portofolio.

---

## Bagian 4: Practical Chapter Challenge

### Judul Tantangan:
**"Arsitektur Informasi & Low-Fidelity Blueprinting untuk Healthcare Telemedicine Triage Engine"**

### Brief Proyek:
Anda ditunjuk sebagai Lead UX Architect untuk merancang platform triase telemedicine gawat darurat dan konsultasi rawat jalan klinik swasta. Pengguna sistem bervariasi dari pasien lanjut usia dengan literasi digital rendah, pasien dalam kondisi panik, hingga operator perawat triase klinis.

### Spesifikasi Kebutuhan Deliverable:
Anda diwajibkan menyusun spesifikasi blueprint arsitektural teks (Markdown-based) yang mencakup:

1. **User Flow & Decision Tree Matrix:**
   - Gambarkan diagram alur logika keputusan dari pasien membuka aplikasi -> memasukkan gejala -> penentuan tingkat kegawatan (Merah: IGD/Ambulans, Kuning: Telekonsultasi Darurat <15 menit, Hijau: Booking Janji Temu Terjadwal).
   - Definisikan *fallback flow* ketika koneksi internet pasien terputus di tengah proses input data medis.

2. **Skema Taksonomi & Sitemapping:**
   - Rancang taksonomi informasi hierarkis 3 level untuk portal layanan kesehatan ini (*Global Navigation, Sub-category, Terminal Pages*).
   - Tentukan *labeling system* yang ramah orang awam (bebas jargon kedokteran rumit).

3. **Low-Fidelity ASCII / Text-Wireframe Layout:**
   - Buat representasi layout text-wireframe untuk layar utama triase medis mobile viewport (360x640 logical width).
   - Cantumkan penempatan komponen kritis: identifikasi darurat, input keluhan utama, tombol darurat satu ketukan (*SOS One-tap*), dan indikator akreditasi keamanan data rekam medis.

4. **Kriteria Keberhasilan (Acceptance Criteria):**
   - Waktu penyelesaian triase oleh pengguna mandiri $\le 90$ detik.
   - Zero-ambiguity pada pemanggilan ambulans (tombol SOS memiliki perlindungan dari ketidaksengajaan namun dapat dieksekusi dalam 2 gestur cepat).
   - Mematuhi prinsip beban kognitif minimal (maksimal 3 pertanyaan medis per layar).

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan rubrik berikut untuk mengevaluasi kesiapan Anda sebelum melangkah ke bab selanjutnya. Tandai kotak jika Anda telah menguasai kompetensi bersangkutan secara mendalam:

- [ ] **Fondasi & Prinsip:** Saya mampu mengartikulasikan perbedaan mendasar antara UX, UI, dan Product Design dengan argumentasi berbasis data dan arsitektur produk.
- [ ] **Hukum Psikologi UX:** Saya dapat menerapkan Hukum Fitts, Hukum Hick, Hukum Miller, dan Hukum Jakob secara presisi dalam penyusunan tata letak komponen antarmuka.
- [ ] **Arsitektur Informasi (IA):** Saya menguasai 4 pilar arsitektur informasi (Organization, Labeling, Navigation, Search) dan mampu mendesain taksonomi untuk sistem berbasis data skala besar.
- [ ] **Beban Kognitif:** Saya memahami pemisahan antara *intrinsic*, *extraneous*, dan *germane cognitive load* serta mampu mengeliminasi elemen desain yang menciptakan *extraneous load*.
- [ ] **Model Mental & Signifier:** Saya dapat mengidentifikasi kesenjangan antara representasi kode backend (*implementation model*) dengan ekspektasi kognitif pengguna (*mental model*) serta menyematkan *signifiers* yang kuat.
- [ ] **Mitigasi Kasus Nyata:** Saya mampu mendiagnosis anomali performa produk digital (drop-off, bounce rate tinggi, lonjakan tiket komplain) dan merumuskan intervensi desain berbasis bukti empiris.
- [ ] **Penyusunan User Flow & Wireframing:** Saya mampu memetakan alur keputusan multi-cabang yang memitigasi *edge-cases* teknis (error network, data timeout) sebelum tahap visualisasi grafis dimulai.
