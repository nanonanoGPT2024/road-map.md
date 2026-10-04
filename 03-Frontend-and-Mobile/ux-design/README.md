# Kurikulum Engineering UX Design (ux-design)

Selamat datang di repositori kurikulum resmi **UX Design** berbasis standar arsitektur kurikulum teknis tingkat lanjut. Kurikulum ini memosisikan User Experience (UX) bukan sekadar seni visual atau perancangan antarmuka permukaan (*surface-level UI*), melainkan sebagai disiplin ilmu rekayasa perilaku (*behavioral engineering*), psikologi kognitif terapan, pemodelan sistem informasi, dan validasi empiris berbasis data kuantitatif serta kualitatif.

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
UX Design pada tingkat rekayasa enterprise memperlakukan interaksi manusia dan komputer (*Human-Computer Interaction*) sebagai sistem deterministik yang dapat diobservasi, diukur, dan dioptimasi. Desain yang buruk bukan masalah selera subjektif; itu adalah kegagalan sistemik dalam memetakan model mental pengguna ke dalam model arsitektur sistem perangkat lunak, yang berujung pada tingginya beban kognitif (*cognitive load*), kesalahan operasional (*error rate*), dan inefisiensi bisnis.

### Paradigma Rekayasa UX
1. **Evidence-Based Design**: Setiap keputusan rancangan harus didukung oleh data riset empiris (kualitatif) atau telemetri perilaku (kuantitatif). Hipotesis harus diuji melalui eksperimen terkontrol, bukan asumsi komite internal.
2. **Cognitive Ergonomics**: Antarmuka dirancang untuk meminimalkan friksi perseptual (*perceptual friction*) dan beban kognitif intrinsik pengguna melalui penerapan hukum-hukum psikologi persepsi (Gestalt, Fitts, Hick-Hyman, Miller).
3. **Systemic Coherence**: Desain dipandang sebagai arsitektur informasi multidimensi, mencakup ontologi, taksonomi, dan koreografi alur kerja lintas platform yang terintegrasi secara modular melalui *Design Systems*.
4. **Accessibility as a Hard Constraint**: Aksesibilitas (WCAG 2.2) diperlakukan setara dengan spesifikasi non-fungsional perangkat lunak tingkat kritis (*mission-critical non-functional requirements*), bukan fitur tambahan opsional.

---

## 2. Learning Roadmap

```plaintext
UX Design Engineering Roadmap
│
├── [BAB 01] Fondasi Human-Computer Interaction (HCI) & Cognitive Psychology
│   ├── [Modul 01] Model Mental, Pemetaan Konseptual, dan Beban Kognitif
│   ├── [Modul 02] Hukum Fitts, Hick-Hyman, Miller, dan Prinsip Gestalt Terapan
│   └── [Modul 03] Neurobiologi Perhatian, Persepsi Visual, dan Ergonomi Digital
│
├── [BAB 02] User Research Rekayasa: Kuantitatif & Kualitatif
│   ├── [Modul 01] Metodologi Riset Generatif: Contextual Inquiry & Deep Interviewing
│   ├── [Modul 02] Riset Evaluatif: Survei Skala Besar, Sampling Statistik, dan Bias Reduksi
│   └── [Modul 03] Analisis Tematik Terstruktur dan Coding Kualitatif Rigor
│
├── [BAB 03] Pemodelan Perilaku, Sintesis Riset & Service Blueprinting
│   ├── [Modul 01] Behavioral Archetypes vs. Proto-Personas Berbasis Klaster Data
│   ├── [Modul 02] Customer Journey Mapping: State, Emosi, dan Friction Points
│   └── [Modul 03] Enterprise Service Blueprinting: Frontstage, Backstage, & Support Systems
│
├── [BAB 04] Arsitektur Informasi & Navigasi Struktural Enterprise
│   ├── [Modul 01] Ontologi, Taksonomi, dan Choreography Sistem Informasi
│   ├── [Modul 02] Card Sorting Terbuka/Tertutup & Validasi Algoritmik Tree Testing
│   └── [Modul 03] Desain Pola Navigasi: Faceted Search, Flat Hierarchy, & Deep Linking
│
├── [BAB 05] Interaction Design (IxD) & Mekanika Perilaku
│   ├── [Modul 01] Pemodelan State Machine: Siklus Hidup Input, Feedback, dan Transisi
│   ├── [Modul 02] Affordance, Signifiers, Constraints, dan Pemetaan Alami
│   └── [Modul 03] Error Prevention, Mitigation Systems, dan Resilient Recovery Loops
│
├── [BAB 06] Wireframing, Lo-Fi Prototyping & Validasi Cepat
│   ├── [Modul 01] Content-First Wireframing: Informasi Struktural Tanpa Gangguan Visual
│   ├── [Modul 02] Kalibrasi Kesetiaan Prototipe: Kapan Menggunakan Paper, Low, atau High-Fi
│   └── [Modul 03] Heuristic Evaluation Terstruktur (Nielsen-Norman, Shneiderman, Bastien-Scapin)
│
├── [BAB 07] Usability Testing Terukur & Metrik UX Standar
│   ├── [Modul 01] Perancangan Lab Usability: Skrip Tugas, Moderator Bias, dan Think-Aloud
│   ├── [Modul 02] Metrik Standar: SUS, SUPR-Q, UMUX-Lite, Task Success, dan Time-on-Task
│   └── [Modul 03] Analisis Varians Data Usability & Formulasi Rekomendasi RICE Terbobot
│
├── [BAB 08] Aksesibilitas Digital (a11y) & Desain Inklusif Lanjutan
│   ├── [Modul 01] Implementasi Mandatori WCAG 2.2 Level AA & AAA
│   ├── [Modul 02] Navigasi Keyboard Penuh, Screen Reader Tree, dan Semantic Mapping
│   └── [Modul 03] Desain untuk Keberagaman Neurodivergen dan Aksesibilitas Kognitif
│
├── [BAB 09] Enterprise Design Systems & Design-to-Code Parity
│   ├── [Modul 01] Arsitektur Design Tokens: Global, Semantic, dan Component Scopes
│   ├── [Modul 02] Komponen UI Terstandarisasi, Dokumentasi Interaksi, dan Edge-Case States
│   └── [Modul 03] Tata Kelola Design System, Versioning, dan Orkestrasi Hand-off Engineer
│
└── [BAB 10] Growth UX, Product Analytics & Post-Launch Optimization
    ├── [Modul 01] Telemetri Perilaku Pengguna: Event Tracking, Funnels, dan Heatmaps
    ├── [Modul 02] Perumusan Hipotesis Eksperimentasi UX & Metodologi A/B Multivariate Testing
    └── [Modul 03] Optimasi Konversi Beretika (Anti-Dark Patterns) & Retensi Berkelanjutan
```

---

## 3. Silabus Modul Detail

### [BAB 01: Fondasi Human-Computer Interaction (HCI) & Cognitive Psychology](./01-fondasi-hci-dan-psikologi-kognitif)
Fokus pada pemahaman fundamental bagaimana otak manusia memproses sinyal digital, mengelola memori jangka pendek, dan membentuk ekspektasi interaksi.
* [Modul 01: Model Mental, Pemetaan Konseptual, dan Beban Kognitif](./01-fondasi-hci-dan-psikologi-kognitif/01-model-mental-dan-beban-kognitif.md) — Mengukur beban kognitif intrinsik, germane, dan extraneous dalam penggunaan perangkat lunak.
* [Modul 02: Hukum Fitts, Hick-Hyman, Miller, dan Prinsip Gestalt Terapan](./01-fondasi-hci-dan-psikologi-kognitif/02-hukum-ergonomi-dan-gestalt.md) — Kalkulasi matematis target akuisisi, waktu reaksi pengambilan keputusan, dan pengelompokan visual.
* [Modul 03: Neurobiologi Perhatian, Persepsi Visual, dan Ergonomi Digital](./01-fondasi-hci-dan-psikologi-kognitif/03-persepsi-visual-dan-ergonomi.md) — Mekanisme foveal vs peripheral vision, scanning patterns (F-shape, Z-shape), dan kelelahan visual.

### [BAB 02: User Research Rekayasa: Kuantitatif & Kualitatif](./02-user-research-rekayasa)
Mempelajari instrumen pengumpulan data pengguna yang objektif, bebas bias peneliti, serta mampu menghasilkan temuan yang dapat direplikasi.
* [Modul 01: Metodologi Riset Generatif: Contextual Inquiry & Deep Interviewing](./02-user-research-rekayasa/01-riset-generatif-dan-contextual-inquiry.md) — Protokol wawancara mendalam, observasi etnografis langsung, dan pembedahan bias kognitif.
* [Modul 02: Riset Evaluatif: Survei Skala Besar, Sampling Statistik, dan Bias Reduksi](./02-user-research-rekayasa/02-riset-evaluatif-dan-sampling-statistik.md) — Desain kuesioner psikometrik, kalkulasi ukuran sampel minimum, dan margin of error.
* [Modul 03: Analisis Tematik Terstruktur dan Coding Kualitatif Rigor](./02-user-research-rekayasa/03-analisis-tematik-dan-coding-kualitatif.md) — Reduksi transkrip riset menjadi kode terstandarisasi menggunakan metode grounded theory terapan.

### [BAB 03: Pemodelan Perilaku, Sintesis Riset & Service Blueprinting](./03-pemodelan-perilaku-dan-service-blueprinting)
Mentransformasikan data mentah riset menjadi artifak operasional yang menyelaraskan pengalaman pengguna dengan kapabilitas infrastruktur teknis.
* [Modul 01: Behavioral Archetypes vs. Proto-Personas Berbasis Klaster Data](./03-pemodelan-perilaku-dan-service-blueprinting/01-behavioral-archetypes-dan-clustering.md) — Membangun persona empiris menggunakan parameter perilaku operasional alih-alih demografi fiktif.
* [Modul 02: Customer Journey Mapping: State, Emosi, dan Friction Points](./03-pemodelan-perilaku-dan-service-blueprinting/02-customer-journey-mapping.md) — Memetakan timeline perjalanan end-to-end, drop-off points, dan momen friksi kognitif.
* [Modul 03: Enterprise Service Blueprinting: Frontstage, Backstage, & Support Systems](./03-pemodelan-perilaku-dan-service-blueprinting/03-enterprise-service-blueprinting.md) — Menghubungkan titik sentuh pengguna dengan API calls, proses logistik fisik, dan dependensi database.

### [BAB 04: Arsitektur Informasi & Navigasi Struktural Enterprise](./04-arsitektur-informasi-dan-navigasi)
Rekayasa pengorganisasian data sistem agar dapat ditemukan secara intuitif tanpa membebani memori kerja pengguna.
* [Modul 01: Ontologi, Taksonomi, dan Choreography Sistem Informasi](./04-arsitektur-informasi-dan-navigasi/01-ontologi-taksonomi-dan-choreography.md) — Mendefinisikan entitas, relasi, dan pelabelan data sistem berskala besar.
* [Modul 02: Card Sorting Terbuka/Tertutup & Validasi Algoritmik Tree Testing](./04-arsitektur-informasi-dan-navigasi/02-card-sorting-dan-tree-testing.md) — Menguji struktur hierarki secara terukur sebelum antarmuka visual dibangun.
* [Modul 03: Desain Pola Navigasi: Faceted Search, Flat Hierarchy, & Deep Linking](./04-arsitektur-informasi-dan-navigasi/03-pola-navigasi-enterprise.md) — Arsitektur penjelajahan untuk ekosistem data kompleks multi-entitas.

### [BAB 05: Interaction Design (IxD) & Mekanika Perilaku](./05-interaction-design-dan-mekanika-perilaku)
Mempelajari interaksi mikroskopik antara tindakan pengguna dan respons balik sistem digital secara responsif dan tanpa ambiguitas.
* [Modul 01: Pemodelan State Machine: Siklus Hidup Input, Feedback, dan Transisi](./05-interaction-design-dan-mekanika-perilaku/01-state-machine-dan-siklus-input.md) — Memetakan status UI: *idle, hover, active, loading, success, error, disabled*.
* [Modul 02: Affordance, Signifiers, Constraints, dan Pemetaan Alami](./05-interaction-design-dan-mekanika-perilaku/02-affordance-dan-constraints.md) — Menghilangkan salah tafsir interaksi melalui tanda fisik dan digital yang presisi.
* [Modul 03: Error Prevention, Mitigation Systems, dan Resilient Recovery Loops](./05-interaction-design-dan-mekanika-perilaku/03-error-prevention-dan-resilient-recovery.md) — Poka-yoke dalam perangkat lunak: konfirmasi destruktif, auto-save, dan graceful degradation.

### [BAB 06: Wireframing, Lo-Fi Prototyping & Validasi Cepat](./06-wireframing-dan-lofi-prototyping)
Teknik merepresentasikan struktur konten dan fungsi tanpa distraksi gaya visual untuk mempercepat iterasi validasi dasar.
* [Modul 01: Content-First Wireframing: Informasi Struktural Tanpa Gangguan Visual](./06-wireframing-dan-lofi-prototyping/01-content-first-wireframing.md) — Menyusun layout berbasis hirarki teks nyata, bukan teks *Lorem Ipsum*.
* [Modul 02: Kalibrasi Kesetiaan Prototipe: Kapan Menggunakan Paper, Low, atau High-Fi](./06-wireframing-dan-lofi-prototyping/02-kalibrasi-kesetiaan-prototipe.md) — Menentukan trade-off rasio investasi waktu vs fidelitas umpan balik yang valid.
* [Modul 03: Heuristic Evaluation Terstruktur (Nielsen-Norman, Shneiderman, Bastien-Scapin)](./06-wireframing-dan-lofi-prototyping/03-heuristic-evaluation-terstruktur.md) — Audit kegunaan independen oleh ahli berbasis metodologi evaluasi heuristik formal.

### [BAB 07: Usability Testing Terukur & Metrik UX Standar](./07-usability-testing-dan-metrik-ux)
Eksekusi pengujian fungsionalitas antarmuka langsung ke pengguna akhir dengan instrumen pengukuran performa yang dapat diaudit.
* [Modul 01: Perancangan Lab Usability: Skrip Tugas, Moderator Bias, dan Think-Aloud](./07-usability-testing-dan-metrik-ux/01-fasilitasi-lab-usability-dan-skrip.md) — Membangun skenario pengujian tanpa mengarahkan (*unbiased task prompts*).
* [Modul 02: Metrik Standar: SUS, SUPR-Q, UMUX-Lite, Task Success, dan Time-on-Task](./07-usability-testing-dan-metrik-ux/02-metrik-kuantitatif-sus-suprq-umux.md) — Formula statistik untuk mengukur kegunaan secara numerik.
* [Modul 03: Analisis Varians Data Usability & Formulasi Rekomendasi RICE Terbobot](./07-usability-testing-dan-metrik-ux/03-analisis-data-dan-prioritas-rekomendasi.md) — Menerjemahkan temuan usability test menjadi tiket backlog produk dengan skor prioritas matematis.

### [BAB 08: Aksesibilitas Digital (a11y) & Desain Inklusif Lanjutan](./08-aksesibilitas-digital-dan-inklusif)
Rekayasa produk perangkat lunak universal yang patuh hukum regulasi global dan dapat dioperasikan secara penuh oleh seluruh spektrum kapabilitas manusia.
* [Modul 01: Implementasi Mandatori WCAG 2.2 Level AA & AAA](./08-aksesibilitas-digital-dan-inklusif/01-implementasi-wcag-2-2.md) — Standar rasio kontras warna, target sentuh minimum (minimum touch target 24x24px / 44x44px), dan penanganan focus visual.
* [Modul 02: Navigasi Keyboard Penuh, Screen Reader Tree, dan Semantic Mapping](./08-aksesibilitas-digital-dan-inklusif/02-keyboard-navigation-dan-screen-readers.md) — Memetakan alur tabulasi, ARIA-labels, live regions, dan hierarki landmark dokumen.
* [Modul 03: Desain untuk Keberagaman Neurodivergen dan Aksesibilitas Kognitif](./08-aksesibilitas-digital-dan-inklusif/03-aksesibilitas-kognitif-dan-neurodivergen.md) — Mereduksi kelebihan beban sensorik, visual flashing, kompleksitas sintaks teks, dan disorientasi navigasi.

### [BAB 09: Enterprise Design Systems & Design-to-Code Parity](./09-enterprise-design-systems)
Membangun fondasi infrastruktur desain yang skalabel secara modular serta memiliki keselarasan penuh dengan basis kode rekayasa perangkat lunak.
* [Modul 01: Arsitektur Design Tokens: Global, Semantic, dan Component Scopes](./09-enterprise-design-systems/01-arsitektur-design-tokens.md) — Standarisasi variabel warna, tipografi, dan elevasi lintas platform (Web, iOS, Android).
* [Modul 02: Komponen UI Terstandarisasi, Dokumentasi Interaksi, dan Edge-Case States](./09-enterprise-design-systems/02-komponen-ui-dan-edge-cases.md) — Menulis spesifikasi interaksi fungsional komprehensif bagi software engineer.
* [Modul 03: Tata Kelola Design System, Versioning, dan Orkestrasi Hand-off Engineer](./09-enterprise-design-systems/03-governance-versioning-handoff.md) — Semantic versioning (SemVer) untuk aset desain, proses RFC, dan otomatisasi hand-off.

### [BAB 10: Growth UX, Product Analytics & Post-Launch Optimization](./10-growth-ux-dan-product-analytics)
Menganalisis performa produk di lingkungan produksi langsung untuk mengoptimalkan retensi, konversi, dan pengalaman jangka panjang.
* [Modul 01: Telemetri Perilaku Pengguna: Event Tracking, Funnels, dan Heatmaps](./10-growth-ux-dan-product-analytics/01-telemetri-perilaku-dan-funnels.md) — Implementasi tracking kualitatif dan kuantitatif (Mixpanel, Amplitude, Hotjar).
* [Modul 02: Perumusan Hipotesis Eksperimentasi UX & Metodologi A/B Multivariate Testing](./10-growth-ux-dan-product-analytics/02-eksperimentasi-ux-dan-ab-testing.md) — Merancang pengujian komparatif dengan signifikansi statistik (*p-value < 0.05*).
* [Modul 03: Optimasi Konversi Beretika (Anti-Dark Patterns) & Retensi Berkelanjutan](./10-growth-ux-dan-product-analytics/03-anti-dark-patterns-dan-retensi.md) — Rekayasa pengalaman bernilai jangka panjang tanpa manipulasi psikologis manipulatif.

---

## 4. Enterprise Capstone Project Specification

### Judul Proyek
**"MedFlow Nexus: Platform Logistik Farmasi B2B & Manajemen Rantai Dingin Terdistribusi Multi-Fasilitas"**

### Konteks Bisnis & Sistem
MedFlow Nexus adalah platform SaaS enterprise yang melayani rumah sakit, distributor farmasi berlisensi, dan laboratorium rujukan. Sistem ini mengatur pergerakan vaksin dan obat-obatan dengan kontrol suhu ketat (*cold-chain logistics*). Kesalahan input antarmuka, disorientasi arsitektur informasi, atau keterlambatan interpretasi anomali data dapat mengakibatkan kerusakan obat bernilai miliaran rupiah dan membahayakan keselamatan pasien.

### Spesifikasi Teknis deliverables Capstone

#### 1. Discovery & Research Engineering Dossier
* **Sampel Riset**: Minimal 5 wawancara mendalam berbasis *Contextual Inquiry* dengan operator logistik, farmasis rumah sakit, dan kurir berlisensi.
* **Transkrip & Koding Tematik**: Matriks *grounded theory* yang mengidentifikasi minimal 15 titik friksi operasional kritis.
* **Behavioral Archetypes**: 3 arketipe perilaku fungsional berdasarkan tanggung jawab peran dan batasan kognitif lingkungan kerja (gudang bersuhu rendah, mobilitas tinggi, kebisingan).

#### 2. Service Blueprinting & Information Architecture
* **Enterprise Service Blueprint**: Diagram menyeluruh yang mencakup:
  * Tindakan Pelanggan/Operator (*Frontstage*)
  * Titik Sentuh Antarmuka (*Digital Touchpoints*)
  * Tindakan Staf Pendukung (*Backstage*)
  * Proses Otomatisasi Sistem/API/IoT Sensor Alerts (*Support Processes*)
* **Information Architecture**: Struktur hierarki menu hasil validasi *Tree Testing* dengan tingkat kesuksesan navigasi langsung (*direct success rate*) minimal **85%** pada 30 partisipan uji.

#### 3. Interaction Mechanics & Heuristic Compliance
* **State Machine Diagram**: Pemodelan minimal 3 alur interaksi kritis (misal: *Penerimaan Vaksin Sensitif Suhu*, *Dispute Batch Kedaluwarsa*, *Ekskalasi Anomali IoT*).
* **Failsafe System Design**: Penerapan mekanisme pencegahan kesalahan (*error prevention*) berstatus *poka-yoke* dengan konfirmasi kontekstual bertingkat (*two-stage verification*) untuk operasi destruktif atau pengalihan batch obat.

#### 4. Design System & Accessibility Hard-Gate (WCAG 2.2 Level AA Mandatori)
* **Tokens & Components**: Repositori Figma/Tokens Studio yang mencakup semantic color palette, typographic scale berskala modular, dan komponen form lengkap dengan 7 state interaksi dasar.
* **Audit Kepatuhan a11y**:
  * Seluruh komponen interaktif harus memiliki rasio kontras visual minimal **4.5:1** (teks normal) dan **3:1** (elemen UI grafis/border).
  * Target klik/sentuh minimum berukuran **44x44 CSS pixels**.
  * Dilengkapi dokumentasi spesifikasi *Accessibility Tree* (spesifikasi tag semantik HTML, alur tombol Tabulasi, dan nilai atribut ARIA).

#### 5. Usability Testing & Statistical Validation Report
* **Metode Pengujian**: Pengujian kegunaan berbasis laboratorium (atau jarak jauh tersinkronisasi) dengan minimal 8 pengguna representatif industri medis/logistik.
* **Standar Kelulusan Metrik Kuantitatif**:
  * **System Usability Scale (SUS)**: Skor rata-rata $\ge 80.0$ (Kategori *Grade A / Excellent*).
  * **Task Completion Rate (TCR)**: $\ge 90\%$ untuk skenario tugas utama tanpa intervensi fasilitator.
  * **Single Ease Question (SEQ)**: Rata-rata $\ge 5.8$ dari skala 7 untuk tiap modul tugas operasional kritis.
* **Dossier Pasca-Peluncuran**: Matriks rencana pelacakan event analitik (*telemetry spec sheet*) untuk diimplementasikan oleh tim software engineering.

---
*Kurikulum ini disusun secara terstruktur untuk menjamin kompetensi tingkat staf/principal UX Designer yang mampu memimpin arsitektur interaksi produk skala besar secara ilmiah, terukur, dan patuh standar industri global.*