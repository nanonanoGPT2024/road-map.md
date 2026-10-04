# Enterprise Business Intelligence Analyst: End-to-End Curriculum Roadmap

Selamat datang di kurikulum resmi **BI Analyst (Business Intelligence Analyst)**. Kurikulum ini dirancang untuk mentransformasi praktisi data konvensional menjadi *Strategic Decision Engineer* dan *Analytics Architect* bertaraf enterprise yang mampu merancang, membangun, mengoperasikan, dan mempertahankan infrastruktur analitik modern (*Modern Data Stack*) dari hulu (*data ingestion & modeling*) hingga hilir (*actionable executive storytelling*).

---

## 1. Course Overview & Mindset

### The Enterprise BI Paradigm
Peran Business Intelligence (BI) Analyst di era data modern telah berevolusi secara radikal. BI Analyst bukan sekadar *"chart monkey"* yang mengekspor data ke spreadsheet atau menyusun dashboard dekoratif. BI Analyst modern adalah arsitek terjemahan bisnis-ke-teknis (*business-to-technical translation layer*) yang bertanggung jawab atas integritas semantik metrik bisnis, arsitektur pemodelan dimensional, performa query tingkat tinggi, hingga tata kelola data enterprise.

```
       TRADITIONAL BI                          MODERN BI ANALYST
┌─────────────────────────┐               ┌─────────────────────────┐
│ - Passive Reporting     │               │ - Decision Engineering  │
│ - Ad-hoc Excel Dumps    │   ───────►    │ - dbt & Dimensional Mod │
│ - Fragmented Metrics    │               │ - Metric Store & Governance
│ - Siloed Dashboards     │               │ - Proactive RCA & Cohorts
└─────────────────────────┘               └─────────────────────────┘
```

### Core Mindset Pillars
1. **Single Source of Truth (SSOT):** Konsistensi logika bisnis adalah harga mati. Metrik seperti *Net Revenue*, *Churn Rate*, atau *Customer Lifetime Value (LTV)* harus didefinisikan satu kali pada semantic layer, bukan dihitung ulang secara manual pada level dashboard.
2. **Performance-First Design:** Efisiensi komputasi analitik (OLAP) adalah prioritas. Query analitik enterprise harus dioptimalkan untuk meminimalkan *data scanning*, memanfaatkan *partitioning*, *clustering*, dan menghindari *full table scans* pada dataset berukuran multi-gigabyte/terabyte.
3. **Action-Oriented Analytics:** Visualisasi data yang tidak menghasilkan keputusan bisnis adalah beban teknis (*technical debt*). Setiap dashboard, KPI card, atau visualisasi harus memiliki jalur aksi (*decision pathway*) yang jelas bagi para pemangku kepentingan (*stakeholders*).
4. **Data Governance & Observability:** Integritas pipeline data dipantau dengan pengujian terotomatisasi, *data lineage*, *data cataloging*, serta kepatuhan terhadap proteksi data sensitif (*PII masking, Row-Level Security*).

---

## 2. Learning Roadmap

Berikut adalah peta struktur kurikulum 10 Bab komprehensif:

```text
E-CURRICULUM: BI ANALYST
├── Bab 01: Fondasi BI Enterprise & Arsitektur Data Modern
│   ├── 01.1 Arsitektur Data Modern (OLTP vs OLAP, Modern Data Stack)
│   ├── 01.2 Paradigma Kimball vs Inmon & Lifecycle BI Enterprise
│   └── 01.3 Ekosistem Warehousing: Snowflake, BigQuery, & Databricks
│
├── Bab 02: Advanced SQL Analytics & Query Optimization
│   ├── 02.1 Window Functions, Common Table Expressions (CTEs), & Subqueries
│   ├── 02.2 Teknik Agregasi Kompleks: Rollup, Cube, Grouping Sets, & Pivot
│   └── 02.3 Profiling Query, EXPLAIN Plans, Indexing, & Optimasi Partisi
│
├── Bab 03: Data Modeling & Dimensional Warehousing
│   ├── 03.1 Star Schema vs Snowflake Schema: Fact & Dimension Tables
│   ├── 03.2 Implementasi Slowly Changing Dimensions (SCD Tipe 0 - 6)
│   └── 03.3 Factless Fact Tables, Role-Playing & Conformed Dimensions
│
├── Bab 04: Data Transformation & Analytics Engineering dengan dbt
│   ├── 04.1 Pengenalan dbt: Staging, Marts, & Modular SQL Development
│   ├── 04.2 Testing Otomatis, Dokumentasi, & Visualisasi Data Lineage
│   └── 04.3 Materialization Strategy: Views, Tables, Incremental, & Ephemeral
│
├── Bab 05: Enterprise Semantic Layer & Metric Standardization
│   ├── 05.1 Konsep Semantic Layer, Headless BI, & Metric Stores
│   ├── 05.2 Definisi Metrik Global: Revenue, Churn, Active Users
│   └── 05.3 Implementasi Semantic Layer pada Tools Terpilih (dbt Semantic Layer/LookML)
│
├── Bab 06: Visual Analytics, Information Architecture & Human Cognition
│   ├── 06.1 Teori Gestalt, Cognitive Load, & Pre-attentive Attributes
│   ├── 06.2 Chart Selection Matrix: Menentukan Visualisasi Berdasarkan Tipe Data
│   └── 06.3 UI/UX Dashboard: Wireframing, Skema Warna Aksesibel, & F-Layout
│
├── Bab 07: Enterprise BI Platforms Deployment & Administration
│   ├── 07.1 Power BI Mastery: Arsitektur DAX, Tabular Modeling, & VertiPaq Engine
│   ├── 07.2 Tableau Enterprise: Level of Detail (LOD) Expressions & Data Server
│   └── 07.3 Keamanan Data Enterprise: Row-Level Security (RLS) & Workspace Governance
│
├── Bab 08: Business Analytics, Financial Modeling & Root Cause Analysis
│   ├── 08.1 Analisis Retensi & Cohort Matrix Lanjutan
│   ├── 08.2 SaaS Unit Economics: CAC, LTV, Payback Period, Net Revenue Retention
│   └── 08.3 Diagnostik & Root Cause Analysis: Pareto, Driver Analysis, & Decomposition
│
├── Bab 09: Data Governance, Quality Assurance & Data Observability
│   ├── 09.1 Framework Data Quality: Freshness, Completeness, Schema Evolution
│   ├── 09.2 Data Cataloging, Enterprise Metadata, & Data Lineage Tracking
│   └── 09.3 Kepatuhan Regulasi & Keamanan: Masking Data PII, GDPR, & Audit Trail
│
└── Bab 10: Production BI Operations (DataOps) & Capstone Project
    ├── 10.1 Version Control (Git), CI/CD Deployment untuk Aset BI
    ├── 10.2 BI Monitoring, Query Cost Tracking, & Alerting Otomatis
    └── 10.3 Capstone Project: End-to-End Enterprise BI Platform Implementation
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Fondasi BI Enterprise & Arsitektur Data Modern](bab-01/README.md)
*Membangun pemahaman fundamental arsitektur sistem analitik skala enterprise, memahami evolusi dari on-premise ke cloud, dan membedakan kebutuhan operasional vs kebutuhan analitik.*
* [Modul 01.1: Arsitektur Data Modern (OLTP vs OLAP, Modern Data Stack)](bab-01/01-1-arsitektur-data-modern.md)
* [Modul 01.2: Paradigma Kimball vs Inmon & Lifecycle BI Enterprise](bab-01/01-2-kimball-vs-inmon-lifecycle.md)
* [Modul 01.3: Ekosistem Warehousing: Snowflake, BigQuery, & Databricks](bab-01/01-3-ekosistem-cloud-warehousing.md)

### [Bab 02: Advanced SQL Analytics & Query Optimization](bab-02/README.md)
*Menguasai sintaks SQL tingkat lanjut untuk manipulasi data analitik masif dan teknik optimasi query berbasis execution plan mesin database analitik modern.*
* [Modul 02.1: Window Functions, Common Table Expressions (CTEs), & Subqueries](bab-02/02-1-window-functions-cte.md)
* [Modul 02.2: Teknik Agregasi Kompleks: Rollup, Cube, Grouping Sets, & Pivot](bab-02/02-2-agregasi-kompleks-pivot.md)
* [Modul 02.3: Profiling Query, EXPLAIN Plans, Indexing, & Optimasi Partisi](bab-02/02-3-profiling-explain-optimasi.md)

### [Bab 03: Data Modeling & Dimensional Warehousing](bab-03/README.md)
*Mendesain skema database analitik yang efisien, terstruktur, dan scalable menggunakan metodologi pemodelan dimensional enterprise.*
* [Modul 03.1: Star Schema vs Snowflake Schema: Fact & Dimension Tables](bab-03/03-1-star-snowflake-fact-dimension.md)
* [Modul 03.2: Implementasi Slowly Changing Dimensions (SCD Tipe 0 - 6)](bab-03/03-2-implementasi-scd-tipe-0-6.md)
* [Modul 03.3: Factless Fact Tables, Role-Playing & Conformed Dimensions](bab-03/03-3-factless-role-playing-conformed.md)

### [Bab 04: Data Transformation & Analytics Engineering dengan dbt](bab-04/README.md)
*Mengadopsi praktik software engineering ke dalam alur kerja data transformation menggunakan data build tool (dbt).*
* [Modul 04.1: Pengenalan dbt: Staging, Marts, & Modular SQL Development](bab-04/04-1-dbt-staging-marts-modular.md)
* [Modul 04.2: Testing Otomatis, Dokumentasi, & Visualisasi Data Lineage](bab-04/04-2-dbt-testing-lineage-docs.md)
* [Modul 04.3: Materialization Strategy: Views, Tables, Incremental, & Ephemeral](bab-04/04-3-dbt-materialization-strategies.md)

### [Bab 05: Enterprise Semantic Layer & Metric Standardization](bab-05/README.md)
*Membangun abstraction layer terpusat guna menjamin konsistensi metrik analitik di seluruh departemen dan tools visualisasi bisnis.*
* [Modul 05.1: Konsep Semantic Layer, Headless BI, & Metric Stores](bab-05/05-1-konsep-semantic-layer-headless-bi.md)
* [Modul 05.2: Definisi Metrik Global: Revenue, Churn, Active Users](bab-05/05-2-definisi-metrik-global-standar.md)
* [Modul 05.3: Implementasi Semantic Layer pada Tools Terpilih](bab-05/05-3-implementasi-semantic-layer.md)

### [Bab 06: Visual Analytics, Information Architecture & Human Cognition](bab-06/README.md)
*Menerapkan prinsip persepsi visual manusia, cognitive psychology, dan desain UI/UX interaktif untuk membangun dashboard eksekutif berstandar tinggi.*
* [Modul 06.1: Teori Gestalt, Cognitive Load, & Pre-attentive Attributes](bab-06/06-1-gestalt-cognitive-load-preattentive.md)
* [Modul 06.2: Chart Selection Matrix: Menentukan Visualisasi Berdasarkan Tipe Data](bab-06/06-2-chart-selection-matrix.md)
* [Modul 06.3: UI/UX Dashboard: Wireframing, Skema Warna Aksesibel, & F-Layout](bab-06/06-3-ui-ux-dashboard-layout-design.md)

### [Bab 07: Enterprise BI Platforms Deployment & Administration](bab-07/README.md)
*Mendalami konfigurasi platform BI terkemuka, optimalisasi engine internal, serta implementasi otorisasi data berbasis peran pengguna.*
* [Modul 07.1: Power BI Mastery: Arsitektur DAX, Tabular Modeling, & VertiPaq Engine](bab-07/07-1-power-bi-dax-vertipaq.md)
* [Modul 07.2: Tableau Enterprise: Level of Detail (LOD) Expressions & Data Server](bab-07/07-2-tableau-lod-data-server.md)
* [Modul 07.3: Keamanan Data Enterprise: Row-Level Security (RLS) & Workspace Governance](bab-07/07-3-enterprise-rls-governance.md)

### [Bab 08: Business Analytics, Financial Modeling & Root Cause Analysis](bab-08/README.md)
*Menerapkan kerangka kerja analitik bisnis mutakhir untuk membedah kinerja finansial, retensi pengguna, dan investigasi performa metrik yang fluktuatif.*
* [Modul 08.1: Analisis Retensi & Cohort Matrix Lanjutan](bab-08/08-1-retensi-cohort-matrix-lanjutan.md)
* [Modul 08.2: SaaS Unit Economics: CAC, LTV, Payback Period, Net Revenue Retention](bab-08/08-2-saas-unit-economics-modeling.md)
* [Modul 08.3: Diagnostik & Root Cause Analysis: Pareto, Driver Analysis, & Decomposition](bab-08/08-3-diagnostik-root-cause-analysis.md)

### [Bab 09: Data Governance, Quality Assurance & Data Observability](bab-09/README.md)
*Memastikan keandalan, keakuratan, dan kepatuhan hukum dari seluruh pipeline data melalui kerangka tata kelola terotomatisasi.*
* [Modul 09.1: Framework Data Quality: Freshness, Completeness, Schema Evolution](bab-09/09-1-framework-data-quality-testing.md)
* [Modul 09.2: Data Cataloging, Enterprise Metadata, & Data Lineage Tracking](bab-09/09-2-data-catalog-metadata-lineage.md)
* [Modul 09.3: Kepatuhan Regulasi & Keamanan: Masking Data PII, GDPR, & Audit Trail](bab-09/09-3-regulasi-pii-masking-compliance.md)

### [Bab 10: Production BI Operations (DataOps) & Capstone Project](bab-10/README.md)
*Menerapkan metodologi DataOps, integrasi continuous integration/continuous deployment (CI/CD), pemantauan biaya komputasi, dan eksekusi proyek akhir.*
* [Modul 10.1: Version Control (Git), CI/CD Deployment untuk Aset BI](bab-10/10-1-version-control-git-cicd-bi.md)
* [Modul 10.2: BI Monitoring, Query Cost Tracking, & Alerting Otomatis](bab-10/10-2-bi-monitoring-cost-alerting.md)
* [Modul 10.3: Capstone Project: End-to-End Enterprise BI Platform Implementation](bab-10/10-3-enterprise-capstone-project.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Proyek
**Global SaaS B2B Enterprise Revenue & Customer Lifecycle Intelligence Platform**

### Skenario Bisnis
Anda ditunjuk sebagai Lead BI Analyst pada perusahaan B2B SaaS global bernama *CloudScale Analytics*. Perusahaan memiliki 10.000+ pelanggan enterprise di berbagai benua dengan volume transaksi bernilai ratusan juta dolar. 

Saat ini, manajemen menghadapi masalah:
* Inkonsistensi perhitungan metrik *Monthly Recurring Revenue (MRR)* dan *Churn* antara tim Finance dan tim Sales.
* Query analitik yang lambat dan boros biaya pada platform Cloud Data Warehouse (menghabiskan ribuan dollar per bulan).
* Kurangnya visibilitas terhadap segmentasi *Cohort Retention* pelanggan, memicu lonjakan churn yang tidak teridentifikasi.
* Pelanggaran kepatuhan terkait data PII (*Personally Identifiable Information*) yang terekspos ke analis internal tanpa otorisasi.

### Skala & Sumber Data
* **Ukuran Dataset:** ~15.000.000 baris data transaksional, log penggunaan aplikasi bulanan, dan event klik.
* **Sumber Data Terintegrasi:**
  1. `Stripe/Billing API Data` (JSON/Parquet): Transaksi pembayaran, upgrade/downgrade subscription, refund.
  2. `Salesforce/HubSpot CRM Data` (Relational schema): Deals pipeline, lead stage, customer enterprise tiers.
  3. `Product Usage Telemetry Data` (Event stream dump): Log aktivitas harian akun, konsumsi storage/fitur.

### Objektif & Deliverables Wajib
Setiap peserta wajib menyelesaikan seluruh siklus hidup proyek analitik dengan artefak berikut:

1. **Arsitektur Pemodelan Dimensional (Data Warehouse Schema):**
   * Desain skema *Star/Snowflake Schema* lengkap (Fact: Subscription Events, Invoice Transactions, Daily Usage; Dim: Account, Product Plan, Geography, Date/Calendar).
   * Implementasi penanganan historisitas data menggunakan **SCD Type 2** untuk tracking perubahan paket langganan pelanggan.

2. **Analytics Engineering Pipeline (dbt Project):**
   * Repository dbt lengkap dengan pemisahan layer: `staging` (`stg_`), `intermediate` (`int_`), dan `marts` (`fct_`, `dim_`).
   * Mengimplementasikan materialization strategy yang optimal (incremental processing pada fact tables volume tinggi).
   * Menuliskan minimal 15 generic/singular dbt tests (mengecek *uniqueness*, *non-null*, *referential integrity*, dan custom business logic tests).

3. **Semantic Layer & Standarisasi Metrik Enterprise:**
   * Definisi golden metrics: *MRR*, *ARR*, *Net Retention Rate (NRR)*, *Gross Retention Rate (GRR)*, *Customer Acquisition Cost (CAC)*, *Payback Period*, dan *LTV*.

4. **Security & Governance Implementation:**
   * Konfigurasi **Row-Level Security (RLS)**: Account Executive regional hanya dapat melihat data sesuai wilayah operasionalnya; C-level dapat melihat data agregat global.
   * Strategi masking data sensitif (Nama PIC, Email, IP Address, Nomor Kartu).

5. **Executive Production Dashboard (Power BI / Tableau / Looker):**
   * **Page 1: C-Suite Executive Overview** (KPI Cards: ARR, NRR, Net Churn, Top-level Variance to Target).
   * **Page 2: Revenue Retention & Cohort Analysis** (Retention heatmaps, Customer upgrade/downgrade flow analysis).
   * **Page 3: Operational Account Diagnostics** (Deep-dive table pelanggan dengan conditional formatting & root cause driver analysis).

6. **Technical Documentation & Executive Decision Memo:**
   * Dokumentasi teknis arsitektur (Data dictionary, lineage graph).
   * 2 halaman *Executive Decision Memo* dalam format Markdown/PDF yang merangkum temuan analitik strategis dan 3 rekomendasi taktis terukur untuk dewan direksi.

---

### Rubrik Penilaian Capstone

| Kategori | Kriteria Evaluasi | Bobot |
|---|---|---|
| **Data Modeling** | Normalisasi/denormalisasi tepat, primary & foreign key terdefinisi baik, implementasi SCD Type 2 valid, efisiensi granularity level. | 25% |
| **SQL & Transformation (dbt)** | Kualitas kode SQL modular, performa query teroptimasi, implementasi dbt models, validitas testing, kelengkapan materialization. | 25% |
| **Visual Analytics & UI/UX** | Penerapan teori Gestalt, hierarki visual yang jelas, navigasi intuitif, konsistensi metrik, bebas dari *clutter* dan visual bias. | 20% |
| **Security & Governance** | Desain Row-Level Security (RLS) berfungsi sesuai peran (role-based), PII masking terverifikasi, dokumentasi metadata lengkap. | 15% |
| **Business Impact & Storytelling** | Kedalaman temuan masalah, ketajaman *Executive Memo*, kalkulasi unit economics akurat, kelayakan rekomendasi bisnis. | 15% |
| **Total** | | **100%** |

---

*Lanjutkan ke modul pertama untuk memulai kurikulum:*  
👉 **[Bab 01: Fondasi BI Enterprise & Arsitektur Data Modern](bab-01/README.md)**