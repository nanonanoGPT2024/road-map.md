# Enterprise Product Design Curriculum (Syllabus)

Selamat datang di kurikulum teknis komprehensif **Product Design**. Silabus ini dirancang oleh Senior Technical Curriculum Architect untuk menjembatani jurang antara estetika visual, arsitektur informasi, psikologi kognitif, kelayakan teknis (*technical feasibility*), dan akselerasi bisnis (*business viability*).

Kurikulum ini mengadopsi standar kompetensi industri terkini yang selaras dengan roadmap resmi `roadmap.sh/product-design`, diekspansi secara mendalam ke dalam 10 Bab progresif dan terstruktur.

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
Product Design bukan sekadar merancang antarmuka pengguna (*User Interface*) yang indah. Product Design adalah rekayasa sistem solusi untuk memecahkan masalah manusia nyata secara berkelanjutan, terukur, dan menguntungkan bagi bisnis.

```
       [ Business Viability ]
                 ▲
                 │
                 ▼
[ Human Desirability ] ◄───► [ Technical Feasibility ]
```

Seorang Enterprise Product Designer dituntut menguasai tiga pilar utama:
1. **Human Desirability (Psikologi & UX):** Mengidentifikasi *latent needs*, pola kognitif, bias persepsi, dan memvalidasi hipotesis perilaku pengguna.
2. **Technical Feasibility (Rekayasa & Sistem):** Memahami arsitektur data, keterbatasan rendering web/native, *state management*, siklus rilis CI/CD, dan integrasi *Design Tokens*.
3. **Business Viability (Strategi & Metrik):** Menghubungkan *user flow* dengan *revenue stream*, konversi, retensi, LTV, CAC, serta indikator kesuksesan berbasis metrik (Google HEART, North Star Metric).

### Metodologi Pedagogis: Dual-Track Agile & Continuous Discovery
Kurikulum ini mengintegrasikan kerangka kerja **Double Diamond 2.0** yang dikombinasikan dengan **Dual-Track Agile (Discovery & Delivery)**:
* **Continuous Discovery:** Wawancara terstruktur mingguan, pemetaan Opportunity Solution Trees (OST), dan eksperimen cepat (*fail-fast*).
* **Robust Delivery:** *Component-driven design*, sistem token modular, arsitektur penanganan *edge-cases*, dan dokumentasi spesifikasi siap produksi untuk rekayasa perangkat lunak.

---

## 2. Learning Roadmap

Diagram alur pohon berikut menggambarkan lintasan instruksional dari level fondasi hingga level eksekutif/strategis:

```text
Product Design Curriculum (End-to-End)
│
├── [Bab 01] Fondasi Product Design & Product Thinking
│   ├── Modul 01: Evolusi Peran & Paradigma Product Thinking
│   └── Modul 02: Opportunity Solution Tree & Value Proposition Design
│
├── [Bab 02] User Research & Problem Discovery
│   ├── Modul 01: Metodologi Kualitatif & Kuantitatif Komparatif
│   ├── Modul 02: Jobs to Be Done (JTBD) & Outcome-Driven Innovation
│   └── Modul 03: Problem Framing & Eliminasi Bias Kognitif
│
├── [Bab 03] Arsitektur Informasi & Mental Models
│   ├── Modul 01: Ontologi, Taksonomi, & Core Modeling
│   ├── Modul 02: Object-Oriented UX (OOUX) Framework
│   └── Modul 03: Complex User Journey Mapping & Task Flow Engineering
│
├── [Bab 04] Wireframing, Low-Fi Testing & Desain Eksperimental
│   ├── Modul 01: Low-Fidelity Prototyping & Skeletalisasi Antarmuka
│   ├── Modul 02: Formative Usability Testing & Metrik Validasi Awal
│   └── Modul 03: Rapid Hypothesis Experimentation & Concierge MVP
│
├── [Bab 05] Visual Systems, Typography & Color Science
│   ├── Modul 01: Sistem Grid Responsif & Spasial Terkomputasi
│   ├── Modul 02: Tipografi Terstruktur & Skala Modular
│   └── Modul 03: Perceptual Color Spaces (OKLCH) & Aksesibilitas Kontras
│
├── [Bab 06] Design Systems Architecture & Token Engineering
│   ├── Modul 01: Atomic Design & Component Lifecycle Management
│   ├── Modul 02: Multi-Tier Design Tokens (Global, Alias, Component)
│   └── Modul 03: Sinkronisasi Token Otomatis (Figma -> Style Dictionary -> Code)
│
├── [Bab 07] Advanced Interaction Design, Micro-interactions & Motion
│   ├── Modul 01: State Machine & Pola Transisi Non-Linier
│   ├── Modul 02: Koreografi Gerak Berbasis Fisika (Spring Physics)
│   └── Modul 03: Standar Aksesibilitas WCAG 2.2 Tingkat AA/AAA
│
├── [Bab 08] High-Fidelity Dynamic Prototyping
│   ├── Modul 01: Pemodelan Logika Lanjutan Menggunakan Variabel & Array
│   └── Modul 02: Simulasi State Kompleks & Pemodelan Data Relasional
│
├── [Bab 09] Product Metrics, Analytics & Continuous Experimentation
│   ├── Modul 01: Telemetri UX, Product Instrumentation & Event Tracking
│   ├── Modul 02: Kerangka Kerja Google HEART & Metrik UX Terkuantifikasi
│   └── Modul 03: Desain Eksperimen A/B Testing & Analisis Signifikansi Statistik
│
└── [Bab 10] Product Strategy, DesignOps & Cross-Functional Delivery
    ├── Modul 01: DesignOps, Governance & Skalabilitas Operasional
    ├── Modul 02: Spesifikasi Pengembang, Edge-Case Auditing & Design QA
    └── Modul 03: Strategi Monetisasi, Ethical Design & Presentasi Eksekutif
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Fondasi Product Design & Product Thinking](./01-fondasi-product-design-dan-product-thinking/)
Membangun cara pandang analitis seorang Product Designer, membedah dikotomi antara rekayasa visual (*styling*) dan penciptaan nilai (*value creation*).
* [Modul 01: Evolusi Peran & Paradigma Product Thinking](./01-fondasi-product-design-dan-product-thinking/01-evolusi-peran-dan-paradigma-product-thinking.md)
  * *Topik:* UI vs UX vs Product Design; Triple Constraints (Viability, Feasibility, Desirability); Pergeseran dari output ke outcome.
* [Modul 02: Opportunity Solution Tree & Value Proposition Design](./01-fondasi-product-design-dan-product-thinking/02-opportunity-solution-tree-dan-value-proposition-design.md)
  * *Topik:* Dekonstruksi masalah menggunakan kerangka kerja Teresa Torres; Alignment Business Objectives & Customer Pain Points; Value Proposition Canvas (VPC).

---

### [Bab 02: User Research & Problem Discovery](./02-user-research-dan-problem-discovery/)
Melakukan riset terapan tingkat lanjut untuk mengekstrak akar masalah yang belum terartikulasi oleh pengguna.
* [Modul 01: Metodologi Kualitatif & Kuantitatif Komparatif](./02-user-research-dan-problem-discovery/01-metodologi-kualitatif-dan-kuantitatif-komparatif.md)
  * *Topik:* Triangulasi data; *Contextual Inquiry*; Desain survei tanpa bias; Analisis klastering data kualitatif menggunakan *Affinity Diagrams*.
* [Modul 02: Jobs to Be Done (JTBD) & Outcome-Driven Innovation](./02-user-research-dan-problem-discovery/02-jobs-to-be-done-dan-outcome-driven-innovation.md)
  * *Topik:* Jobs, Pains, Gains; *Forces of Progress Canvas*; Menulis *Job Statements* berbasis metrik keberhasilan fungsional dan emosional.
* [Modul 03: Problem Framing & Eliminasi Bias Kognitif](./02-user-research-dan-problem-discovery/03-problem-framing-dan-eliminasi-bias-kognitif.md)
  * *Topik:* Point-of-View (PoV) generation; Teknik "How Might We" (HMW); Identifikasi bias peneliti (Confirmation Bias, Framing Effect, Sunk Cost Fallacy).

---

### [Bab 03: Arsitektur Informasi & Mental Models](./03-arsitektur-informasi-dan-mental-models/)
Merancang cetak biru navigasi dan hubungan entitas data yang selaras dengan model mental pengguna.
* [Modul 01: Ontologi, Taksonomi, & Core Modeling](./03-arsitektur-informasi-dan-mental-models/01-ontologi-taksonomi-dan-core-modeling.md)
  * *Topik:* Klasifikasi informasi hierarkis, relasional, dan facet; Card Sorting (Open, Closed, Hybrid); Evaluasi Tree Testing.
* [Modul 02: Object-Oriented UX (OOUX) Framework](./03-arsitektur-informasi-dan-mental-models/02-object-oriented-ux-framework.md)
  * *Topik:* Metodologi ORCA (Objects, Relationships, Calls-to-action, Attributes); Menghubungkan entitas bisnis ke antarmuka aplikasi.
* [Modul 03: Complex User Journey Mapping & Task Flow Engineering](./03-arsitektur-informasi-dan-mental-models/03-complex-user-journey-mapping-dan-task-flow-engineering.md)
  * *Topik:* Diagram Service Blueprint; Arsitektur alur tugas non-linier; State transitions dan skenario degradasi koneksi offline.

---

### [Bab 04: Wireframing, Low-Fi Testing & Desain Eksperimental](./04-wireframing-low-fi-testing-dan-desain-eksperimental/)
Validasi ide dan struktur tata letak secara cepat sebelum berinvestasi dalam detail visual dan kode.
* [Modul 01: Low-Fidelity Prototyping & Skeletalisasi Antarmuka](./04-wireframing-low-fi-testing-dan-desain-eksperimental/01-low-fidelity-prototyping-dan-skeletalisasi-antarmuka.md)
  * *Topik:* Rasio kompresi visual (scaffolding); Alokasi hierarki tata letak tanpa dekorasi; Prototyping kertas vs paperless digital wireframe.
* [Modul 02: Formative Usability Testing & Metrik Validasi Awal](./04-wireframing-low-fi-testing-dan-desain-eksperimental/02-formative-usability-testing-dan-metrik-validasi-awal.md)
  * *Topik:* Protokol *Think-Aloud*; Menghitung System Usability Scale (SUS) awal; Mengukur Single Ease Question (SEQ) dan *Task Completion Rate*.
* [Modul 03: Rapid Hypothesis Experimentation & Concierge MVP](./04-wireframing-low-fi-testing-dan-desain-eksperimental/03-rapid-hypothesis-experimentation-dan-concierge-mvp.md)
  * *Topik:* Wizard of Oz prototyping; Smoke testing via landing pages; Perancangan matriks risiko vs ketidakpastian (*Risk-Assumption Mapping*).

---

### [Bab 05: Visual Systems, Typography & Color Science](./05-visual-systems-typography-dan-color-science/)
Membangun fondasi estetika matematis dan sistematis untuk produk skala enterprise.
* [Modul 01: Sistem Grid Responsif & Spasial Terkomputasi](./05-visual-systems-typography-dan-color-science/01-sistem-grid-responsif-dan-spasial-terkomputasi.md)
  * *Topik:* Grid 8pt / 4pt Spatial System; Fluid layouts menggunakan formula kalkulasi modular; Breakpoint responsif multi-device.
* [Modul 02: Tipografi Terstruktur & Skala Modular](./05-visual-systems-typography-dan-color-science/02-tipografi-terstruktur-dan-skala-modular.md)
  * *Topik:* Tipografi rasio matematis (Golden Ratio, Major Third); Vertical rhythm; Pemilihan font berdasarkan *legibility*, *x-height*, dan dukungan OpenType.
* [Modul 03: Perceptual Color Spaces (OKLCH) & Aksesibilitas Kontras](./05-visual-systems-typography-dan-color-science/03-perceptual-color-spaces-dan-aksesibilitas-kontras.md)
  * *Topik:* Model warna sRGB vs OKLCH; Generasi palet semantik adaptif (Dark/Light mode); Rasio kontras WCAG 2.2 APCA (*Accessible Perceptual Contrast Algorithm*).

---

### [Bab 06: Design Systems Architecture & Token Engineering](./06-design-systems-architecture-dan-token-engineering/)
Mendesain dan memelihara sistem komponen enterprise berskala masif dengan kontinuitas antarmuka dan kode produksi.
* [Modul 01: Atomic Design & Component Lifecycle Management](./06-design-systems-architecture-dan-token-engineering/01-atomic-design-dan-component-lifecycle-management.md)
  * *Topik:* Atomics, Molecules, Organisms; Strategi *Versioning* Komponen (SemVer); Deprecating, sunsetting, dan migrasi varian.
* [Modul 02: Multi-Tier Design Tokens (Global, Alias, Component)](./06-design-systems-architecture-dan-token-engineering/02-multi-tier-design-tokens.md)
  * *Topik:* Struktur JSON token (W3C Design Tokens Community Group specification); Abstraksi variabel primitive, contextual/semantic, dan component-level.
* [Modul 03: Sinkronisasi Token Otomatis (Figma -> Style Dictionary -> Code)](./06-design-systems-architecture-dan-token-engineering/03-sinkronisasi-token-otomatis.md)
  * *Topik:* Otomasi pipeline CI/CD tokens; Integrasi Figma REST API / Plugin; Kompilasi lintas platform via Amazon Style Dictionary (CSS, SCSS, Swift, Android XML/Compose).

---

### [Bab 07: Advanced Interaction Design, Micro-interactions & Motion](./07-advanced-interaction-design-micro-interactions-dan-motion/)
Merancang interaksi berdaya guna tinggi dengan mekanika mikro yang meningkatkan *clarity*, *feedback*, dan kedalaman kontekstual.
* [Modul 01: State Machine & Pola Transisi Non-Linier](./07-advanced-interaction-design-micro-interactions-dan-motion/01-state-machine-dan-pola-transisi-non-linier.md)
  * *Topik:* Finite State Machines (FSM) dalam konteks interaksi UI; State matrix (Default, Hover, Active, Focus, Disabled, Error, Loading, Skeleton).
* [Modul 02: Koreografi Gerak Berbasis Fisika (Spring Physics)](./07-advanced-interaction-design-micro-interactions-dan-motion/02-koreografi-gerak-berbasis-fisika.md)
  * *Topik:* Kurva Bezier kubik vs *Mass-Damping-Stiffness dynamics*; Waktu persepsi kognitif (100ms, 300ms, 1s); Choreographed stagger effects.
* [Modul 03: Standar Aksesibilitas WCAG 2.2 Tingkat AA/AAA](./07-advanced-interaction-design-micro-interactions-dan-motion/03-standar-aksesibilitas-wcag-22.md)
  * *Topik:* Navigasi papan ketik (*Focus Traps*, *Skip links*); Atribut ARIA (*roles*, *states*, *live regions*); Preferensi gerak sistem (*prefers-reduced-motion*).

---

### [Bab 08: High-Fidelity Dynamic Prototyping](./08-high-fidelity-dynamic-prototyping/)
Menciptakan prototipe interaktif fungsional tingkat lanjut yang mencerminkan kapabilitas sistem perangkat lunak nyata.
* [Modul 01: Pemodelan Logika Lanjutan Menggunakan Variabel & Array](./08-high-fidelity-dynamic-prototyping/01-pemodelan-logika-lanjutan-menggunakan-variabel-dan-array.md)
  * *Topik:* Logika kondisional Boolean; Operasi aritmatika data dalam prototipe; Penggunaan string & color variable expressions.
* [Modul 02: Simulasi State Kompleks & Pemodelan Data Relasional](./08-high-fidelity-dynamic-prototyping/02-simulasi-state-kompleks-dan-pemodelan-data-relasional.md)
  * *Topik:* Prototipe multi-halaman interaktif tersinkronisasi; Keranjang belanja dinamis, formulir validasi bertahap, dan manipulasi data interaktif lokal.

---

### [Bab 09: Product Metrics, Analytics & Continuous Experimentation](./09-product-metrics-analytics-dan-continuous-experimentation/)
Menghubungkan setiap elemen interaksi dengan data analitik dan instrumen pengujian ilmiah.
* [Modul 01: Telemetri UX, Product Instrumentation & Event Tracking](./09-product-metrics-analytics-dan-continuous-experimentation/01-telemetri-ux-product-instrumentation-dan-event-tracking.md)
  * *Topik:* Perancangan schema pelacakan event (Segment, Mixpanel); Heatmaps, Session Recording analysis (Hotjar/FullStory); Funnel Drop-off Diagnostic.
* [Modul 02: Kerangka Kerja Google HEART & Metrik UX Terkuantifikasi](./09-product-metrics-analytics-dan-continuous-experimentation/02-kerangka-kerja-google-heart-dan-metrik-ux-terkuantifikasi.md)
  * *Topik:* Happiness, Engagement, Adoption, Retention, Task Success; Perhitungan UMUX-Lite; Time-on-Task & Error-Rate monitoring.
* [Modul 03: Desain Eksperimen A/B Testing & Analisis Signifikansi Statistik](./09-product-metrics-analytics-dan-continuous-experimentation/03-desain-eksperimen-ab-testing-dan-analisis-signifikansi-statistik.md)
  * *Topik:* Perumusan hipotesis statistik null ($H_0$) dan alternatif ($H_1$); Penentuan *Sample Size* & *Statistical Power*; Mencegah bias *Sample Ratio Mismatch* (SRM).

---

### [Bab 10: Product Strategy, DesignOps & Cross-Functional Delivery](./10-product-strategy-designops-dan-cross-functional-delivery/)
Mengeksekusi desain dalam skala tim enterprise, tata kelola operasi, dan kolaborasi tanpa friksi bersama engineer dan manajer produk.
* [Modul 01: DesignOps, Governance & Skalabilitas Operasional](./10-product-strategy-designops-dan-cross-functional-delivery/01-designops-governance-dan-skalabilitas-operasional.md)
  * *Topik:* Alur kerja federasi vs terpusat; Standar penamaan berkas & repositori desain; Design critique framework & efisiensi operasional.
* [Modul 02: Spesifikasi Pengembang, Edge-Case Auditing & Design QA](./10-product-strategy-designops-dan-cross-functional-delivery/02-spesifikasi-pengembang-edge-case-auditing-dan-design-qa.md)
  * *Topik:* Dokumentasi anotasi fungsional menyeluruh; Penanganan *Zero-states*, *Extreme-character boundaries*, *API Failure latency states*; Protokol *Design QA checklist*.
* [Modul 03: Strategi Monetisasi, Ethical Design & Presentasi Eksekutif](./10-product-strategy-designops-dan-cross-functional-delivery/03-strategi-monetisasi-ethical-design-dan-presentasi-eksekutif.md)
  * *Topik:* Desain alur pembayaran/checkout dan *pricing pages*; Dark patterns auditing; Teknik persuasi berbasis data (*Executive Pitching*).

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title:
**"OmniLog: Enterprise B2B Autonomous Supply Chain & Logistics Orchestration Platform"**

### Gambaran Kasus (Business Context)
OmniLog adalah platform perangkat lunak SaaS B2B berskala global yang memfasilitasi orkestrasi armada logistik kargo terdesentralisasi, manajemen inventaris lintas gudang multimoda, dan penyelesaian anomali pengiriman real-time berbasis peringatan prediktif AI.

### Masalah Pengguna & Bisnis
1. **Beban Kognitif Berlebih (*Cognitive Overload*):** Dispatcher logistik memantau lebih dari 200 armada serentak dengan antarmuka yang lambat, mengakibatkan respons mitigasi insiden tertunda rata-rata 42 menit.
2. **Fragmentasi Data:** Informasi status pengiriman, dokumen bea cukai, dan peringatan telemetri armada terpisah dalam 4 sistem legacy yang berbeda tanpa model mental yang konsisten.
3. **Kebutuhan Aksesibilitas di Lapangan:** Pengemudi dan operator dermaga logistik menggunakan tablet industri di bawah pantulan sinar matahari langsung dengan keterbatasan jaringan.

---

### Spesifikasi & Kriteria Deliverable Proyek

Peserta wajib menyerahkan portofolio komprehensif yang mencakup seluruh artefak berikut:

```text
OmniLog Enterprise Deliverables
│
├── 01. Strategic Discovery & Problem Definition
│   ├── Opportunity Solution Tree (OST) lengkap
│   ├── JTBD Matrix & 5 Functional Job Maps
│   └── 3 Usability Benchmarking Reports kompetitor global
│
├── 02. Information Architecture & Systems Modeling
│   ├── Dokumen OOUX (ORCA Model: Object, Relationships, CTAs, Attributes)
│   ├── Entity-Relationship Map UI & System Navigation Model
│   └── Service Blueprint komprehensif (Customer actions, Frontstage, Backstage, Support)
│
├── 03. Design System & Token Distribution
│   ├── Repositori Multi-Tier Design Tokens (Format W3C JSON)
│   ├── Komponen Atomic interaktif di Figma (Autolayout, Properties, Variants)
│   ├── Konfigurasi Style Dictionary untuk kompilasi ke CSS Variables & JSON
│   └── Dokumentasi Aksesibilitas WCAG 2.2 AA (Color contrast, Aria specs, Focus indicators)
│
├── 04. High-Fidelity Prototype Berperforma Tinggi
│   ├── Prototipe Figma tingkat lanjut yang memanfaatkan Variable Logic, Array, & Conditional Logic
│   ├── Skenario Pengujian:
│   │   ├── Skenario A: Resolusi insiden suhu kargo anomali (Critical alert triage)
│   │   ├── Skenario B: Relokasi rute dinamis (Multi-stop rerouting with pricing changes)
│   │   └── Skenario C: Alur kerja offline dermaga logistik (Optimistic UI updates)
│
└── 05. Product Metrics, Handoff & Governance
    ├── Rencana Instrumentasi Event Telemetri (Event payload taxonomy)
    ├── Metrik Keberhasilan berbasis Google HEART Framework & UMUX-Lite target
    ├── Dokumen Spesifikasi Rekayasa (Edge cases, Error states, Micro-interactions)
    └── Lembar Rekonsiliasi Design QA (Design Audit Checklist)
```

### Standar Kelulusan Capstone
1. **Zero High-Severity Accessibility Violations:** Memenuhi standar kepatuhan kontras warna, pembaca layar (*screen reader*), dan fokus keyboard navigasi.
2. **Engineering Readiness Score:** Seluruh varian komponen, state boundary (loading, error, zero, long-string), dan token diekspor serta didokumentasikan tanpa ambigu.
3. **Business-UX Alignment:** Prototipe dan keputusan desain harus dapat dipertanggungjawabkan melalui penurunan metrik waktu penanganan insiden (*Time-to-Resolve Incident*) dan estimasi nilai ROI produk.