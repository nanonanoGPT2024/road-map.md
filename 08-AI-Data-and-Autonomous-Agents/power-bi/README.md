# Enterprise Power BI & Semantic Engineering: From Data Modeling to Fabric Architecture

Selamat datang di repositori kurikulum resmi **Power BI Engineer & Analytics Architect**. Kurikulum ini dirancang untuk menjembatani kesenjangan antara sekadar "membuat dashboard visual" dengan rekayasa sistem *Business Intelligence* (BI) tingkat enterprise yang terukur, aman, dan berkinerja tinggi.

---

## 1. Course Overview & Mindset

Dalam lanskap analitik modern, peran pengembang Power BI telah bergeser dari sekadar *report builder* menjadi **Semantic Data Engineer**. Paradigma ini menuntut penguasaan mendalam atas:

*   **Arsitektur Penyimpanan VertiPaq Engine:** Memahami bagaimana memori dikompresi (Dictionary Encoding, Run-Length Encoding, Bit-Packing) untuk merancang model data berkapasitas ratusan juta baris dengan latensi sub-detik.
*   **Dimensional Modeling yang Ketat:** Penerapan metodologi Kimball (Star Schema) murni untuk menghilangkan perangkap hubungan *many-to-many* dan propagasi filter yang tidak terkontrol.
*   **Formula Engine & Storage Engine Optimization:** Menulis DAX (*Data Analysis Expressions*) tingkat lanjut dengan kalkulasi asimetris, modifikasi konteks evaluasi, dan eliminasi *callback loops*.
*   **DevOps & ALM (Application Lifecycle Management):** Mengoperasionalkan artefak Power BI menggunakan format berbasis teks (PBIP, TMDL), integrasi Git, Tabular Editor, dan pipeline CI/CD otomatis.
*   **Tata Kelola & Keamanan Enterprise:** Penerapan *Dynamic Row-Level Security* (RLS), *Object-Level Security* (OLS), segregasi lisensi, serta orkestrasi integrasi dengan Microsoft Fabric dan Direct Lake.

### Mindset Transisi
```
[Report Designer]                [Enterprise BI Engineer]
Menarik & meletakkan chart   ->  Merancang arsitektur analitik end-to-end
Data denormalisasi lebar     ->  Star Schema presisi dengan kompresi VertiPaq
Kalkulasi calculated column  ->  DAX Measure berbasis konteks evaluasi
Manual deploy via Desktop    ->  CI/CD Pipeline via Git, PBIP, & Azure DevOps
Akses database DirectQuery   ->  Komposisi Hybrid Tables & Aggregations
```

---

## 2. Learning Roadmap

```
Power BI Engineering Curriculum
│
├── [Bab 01] Fondasi Arsitektur Power BI & Data Ingestion
│   ├── Storage Modes (Import, DirectQuery, Dual, Composite)
│   ├── Power Query M Scripting & Data Transformation
│   └── Query Folding & Pipeline Acceleration
│
├── [Bab 02] Dimensional Data Modeling & Relational Semantics
│   ├── Kimball Star Schema & Normalisasi vs Denormalisasi
│   ├── Relationship Cardinality & Cross-Filtering Behavior
│   └── SCD (Slowly Changing Dimensions) & Role-Playing Dims
│
├── [Bab 03] DAX Core: Evaluation Contexts & Engine Internals
│   ├── Filter Context, Row Context, & Context Transition
│   ├── CALCULATE Internals & Filter Modifiers
│   └── Evaluation Order & Context Overrides
│
├── [Bab 04] Advanced DAX Patterns & Analytical Engineering
│   ├── Standard & Non-Standard Time Intelligence
│   ├── Virtual Tables, Iterators, & Extended Summaries
│   └── Semi-Additive Measures, Ranking, & Cohort Dynamics
│
├── [Bab 05] Information Design, UX Semantics & Visual Hierarchy
│   ├── Gestalt Principles & IBCS Reporting Standards
│   ├── Interactive Engineering (Bookmarks, Drillthrough, SVGs)
│   └── Accessibility (WCAG 2.1) & Mobile Optimization
│
├── [Bab 06] Power BI Service Architecture, Workspaces & Gateways
│   ├── Tenant Architecture, Workspaces, & App Orchestration
│   ├── Enterprise Data Gateways (Standard & VNet Cluster)
│   └── Refresh Strategies, Hybrid Partitioning, & Monitoring
│
├── [Bab 07] Enterprise Governance, Data Security & Compliance
│   ├── Static & Dynamic Row-Level Security (RLS) via UPN
│   ├── Object-Level Security (OLS) & Sensitive Metadata
│   └── Purview Integration, Data Lineage, & Tenant Auditing
│
├── [Bab 08] VertiPaq Optimization Engine & Performance Tuning
│   ├── VertiPaq Internals (Dictionary, RLE, Bit-Packing)
│   ├── Profiling via DAX Studio & Performance Analyzer
│   └── Aggregation Tables & Composite Model Optimization
│
├── [Bab 09] BI DevOps, ALM & Automated Deployment Pipelines
│   ├── PBIP Format, TMDL, & Git Version Control
│   ├── Deployment Pipelines (Dev-Test-Prod) & API Triggers
│   └── Tabular Editor Automation via BPA & DevOps Tasks
│
└── [Bab 10] Modern Fabric Integration & Embedded Analytics
    ├── Microsoft Fabric, OneLake & Direct Lake Mode
    ├── Advanced Analytics via PySpark & Python/R Run-times
    └── Power BI Embedded (App-Owns-Data vs User-Owns-Data)
```

---

## 3. Modul Silabus Terperinci

### [Bab 01: Fondasi Arsitektur Power BI & Data Ingestion Fundamentals](./bab-01-arsitektur-dan-ingestion/README.md)
Fondasi komputasi Power BI, memahami batas fisik pemrosesan data, serta teknik ekstraksi data dengan performa tinggi.
* [01-01: Ekosistem Arsitektur Power BI & Storage Modes](./bab-01-arsitektur-dan-ingestion/01-01-storage-modes.md)
  * VertiPaq memory architecture, perbandingan mendalam Import vs DirectQuery vs Dual Storage, serta arsitektur Composite Models.
* [01-02: Data Transformation Pipeline & Advanced Power Query (M)](./bab-01-arsitektur-dan-ingestion/01-02-power-query-m-scripting.md)
  * Sintaksis fungsional bahasa M, pembuatan *custom functions*, manipulasi list/record/table, dan *error handling* pada level mashup.
* [01-03: Optimasi Query Folding & ETL Mashup Performance](./bab-01-arsitektur-dan-ingestion/01-03-query-folding-dan-mashup.md)
  * Menjamin delegasi komputasi ke *source database*, penanganan indikator *step folding*, mitigasi *broken folding steps*, dan konfigurasi *parallel loading*.

### [Bab 02: Dimensional Data Modeling & Relational Semantics](./bab-02-dimensional-modeling/README.md)
Rancang bangun arsitektur data analitik tabular yang deterministik, efisien terhadap memori, dan bebas ambiguitas logika.
* [02-01: Star Schema vs Snowflake & Kimball Dimensional Design](./bab-02-dimensional-modeling/02-01-kimball-star-schema.md)
  * Perancangan Fact Table (Transactional, Periodic Snapshot, Accumulating Snapshot) versus Dimension Tables, degradasi relasi snowflake menjadi star schema murni.
* [02-02: Relationship Cardinality, Directionality & Ambiguity](./bab-02-dimensional-modeling/02-02-relationship-cardinality-filter-flow.md)
  * Relasi 1-to-Many vs Many-to-Many via bridge tables, dampak bahaya Bi-Directional Cross-Filtering, relasi aktif vs non-aktif (`USERELATIONSHIP`).
* [02-03: Handling Complex Dimensions (SCD, Role-Playing, Junk)](./bab-02-dimensional-modeling/02-03-scd-role-playing-junk-dimensions.md)
  * Implementasi Slowly Changing Dimensions (SCD Tipe 1 & 2), dimensi tanggal ganda (*Ship Date*, *Order Date*), dan agregasi status ke *Junk Dimension*.

### [Bab 03: DAX Core: Evaluation Contexts & Engine Internals](./bab-03-dax-core-evaluation-contexts/README.md)
Menguasai mekanika internal *Data Analysis Expressions*, membedah pergeseran konteks evaluasi dan eksekusi formula.
* [03-01: Tiga Pilar Evaluasi: Row Context, Filter Context, dan Context Transition](./bab-03-dax-core-evaluation-contexts/03-01-evaluasi-konteks.md)
  * Mekanisme Row Context implisit, Filter Context runtime, dan transisi konteks menggunakan fungsi skalar dalam iterasi.
* [03-02: Kalkulasi DAX: Calculated Columns, Measures, & Evaluation Tree](./bab-03-dax-core-evaluation-contexts/03-02-measures-vs-calculated-columns.md)
  * Analisis alokasi memori RAM vs kalkulasi CPU on-the-fly, urutan pemrosesan DAX engine, dan *anti-patterns* penggunaan kolom kalkulasi.
* [03-03: Bedah Tuntas CALCULATE & Modifikasi Konteks](./bab-03-dax-core-evaluation-contexts/03-03-calculate-internals.md)
  * Logika internal fungsi `CALCULATE`/`CALCULATETABLE`, penggunaan *filter modifiers* (`ALL`, `ALLEXCEPT`, `ALLSELECTED`, `KEEPFILTERS`, `REMOVEFILTERS`).

### [Bab 04: Advanced DAX Patterns & Analytical Engineering](./bab-04-advanced-dax-patterns/README.md)
Implementasi kalkulasi bisnis kompleks, manipulasi tabel virtual di memori, dan penyelesaian masalah skenario analitik tingkat lanjut.
* [04-01: Time Intelligence Patterns (Standard vs Custom Fiscal Calendars)](./bab-04-advanced-dax-patterns/04-01-time-intelligence-advanced.md)
  * YTD, QTD, MTD, Parallel Period, Same Period Last Year, penanganan kalender 4-4-5 / 4-5-4 ISO-8601 tanpa fungsi *time-intelligence built-in*.
* [04-02: Iterator Operations & Virtual Table Manipulation](./bab-04-advanced-dax-patterns/04-02-iterators-virtual-tables.md)
  * Penguasaan `SUMX`, `AVERAGEX`, `RANKX`, operasi tabel virtual dengan `SUMMARIZECOLUMNS`, `ADDCOLUMNS`, `GENERATE`, `NATURALLEFTOUTERJOIN`.
* [04-03: Semi-Additive Measures, Dynamic Segmentation, & Cohort Analysis](./bab-04-advanced-dax-patterns/04-03-semi-additive-segmentation-cohorts.md)
  * Kalkulasi saldo kas harian/stok gudang (*closing balance*), segmentasi dinamis via skala parameter, dan metrik retensi/churn pelanggan multi-periode.

### [Bab 05: Information Design, UX Semantics & Visual Hierarchy](./bab-05-visual-design-and-ux/README.md)
Mentransformasikan data mentah menjadi wawasan kognitif yang cepat diserap melalui rekayasa antarmuka laporan enterprise.
* [05-01: Information Design & IBCS (International Business Communication Standards)](./bab-05-visual-design-and-ux/05-01-ibcs-visual-standards.md)
  * Standarisasi semantik warna, konsistensi visual chart, variasi skenario (Actual vs Budget vs Forecast), dan eliminasi chart-junk.
* [05-02: Advanced Interactive UX: Bookmarks, Drillthrough, & Dynamic Canvas](./bab-05-visual-design-and-ux/05-02-advanced-ux-bookmarks-drillthrough.md)
  * Rekayasa antarmuka berlapis dengan bookmark groups, drillthrough multi-level kontekstual, cross-report drillthrough, dan dynamic tooltips.
* [05-03: Dynamic DAX-Driven Visuals, Custom SVGs, & Accessibility (WCAG)](./bab-05-visual-design-and-ux/05-03-dax-svg-wcag-accessibility.md)
  * Pembuatan visual KPI kustom menggunakan DAX SVG string, implementasi kontras, navigasi tabulasi keyboard, dan pembaca layar (*screen reader*).

### [Bab 06: Power BI Service Architecture, Workspaces & Gateways](./bab-06-service-architecture-and-gateways/README.md)
Deploy, orkestrasi pembaruan, dan manajemen siklus distribusi artefak pada cloud tenant Power BI Service.
* [06-01: Tenant Topology, Workspace Governance, & Shared Semantic Models](./bab-06-service-architecture-and-gateways/06-01-workspace-governance.md)
  * Perancangan Workspace architecture, segregasi model data analitik (Golden Semantic Model) dari downstream reports via Read/Build permissions.
* [06-02: Enterprise Data Gateways: Clustering, Load Balancing, & VNet](./bab-06-service-architecture-and-gateways/06-02-enterprise-gateways-architecture.md)
  * Arsitektur On-Premises Data Gateway High-Availability Clusters, VNet Data Gateway, delegasi autentikasi Kerberos/SSO, dan load distribution.
* [06-03: Incremental Refresh, Large Dataset Storage, & Scheduled Automation](./bab-06-service-architecture-and-gateways/06-03-incremental-refresh-hybrid.md)
  * Konfigurasi parameter `RangeStart`/`RangeEnd`, partisi otomatis VertiPaq, real-time query partition (Hybrid Tables), dan REST API refresh triggers.

### [Bab 07: Enterprise Governance, Data Security & Compliance](./bab-07-governance-security-compliance/README.md)
Menjaga kerahasiaan, keandalan akses data, dan keselarasan terhadap regulasi kepatuhan korporat global.
* [07-01: Dynamic Row-Level Security (RLS) via Hierarchy & Active Directory UPN](./bab-07-governance-security-compliance/07-01-dynamic-rls-upn.md)
  * Implementasi keamanan multi-organisasi/multi-level menggunakan `USERPRINCIPALNAME()`, *Path functions*, dan dynamic entitlement mapping tables.
* [07-02: Object-Level Security (OLS) & Granular Column/Table Masking](./bab-07-governance-security-compliance/07-02-object-level-security-ols.md)
  * Restriksi akses skema data sensitif (misal: Kompensasi Pegawai, Margin Keuangan) pada level metadata menggunakan Tabular Editor.
* [07-03: Purview Data Governance, Sensitivity Labels, & Audit Log Extraction](./bab-07-governance-security-compliance/07-03-purview-audit-logs.md)
  * Integrasi Microsoft Purview Data Map, enkripsi data via Information Protection (MIP) labels, dan ekstraksi Power BI Activity Log via REST API.

### [Bab 08: VertiPaq Optimization Engine & Performance Tuning](./bab-08-vertipaq-optimization-tuning/README.md)
Audit, identifikasi *bottleneck*, dan optimasi eksekusi formula DAX serta struktur internal memori engine VertiPaq.
* [08-01: VertiPaq Physical Storage Internals: Encoding & Compression](./bab-08-vertipaq-optimization-tuning/08-01-vertipaq-internals-compression.md)
  * Analisis struktur memori: Value Encoding, Hash (Dictionary) Encoding, Run-Length Encoding (RLE), dan reduksi konsumsi memori tabular.
* [08-02: Diagnostics Profiling: DAX Studio, VertiPaq Analyzer, & Performance Analyzer](./bab-08-vertipaq-optimization-tuning/08-02-profiling-dax-studio-analyzer.md)
  * Profiling waktu eksekusi (Visual Display, DAX Query, DirectQuery SLA), ekstraksi *Server Timings* (Formula Engine vs Storage Engine), dan xmSQL reading.
* [08-03: Query Tuning, Cardinality Reduction, & User-Defined Aggregations](./bab-08-vertipaq-optimization-tuning/08-03-aggregations-cardinality-tuning.md)
  * Teknik menurunkan kardinalitas kolom, pemisahan waktu dan tanggal, serta konfigurasi Aggregation Tables (Import over DirectQuery) untuk data terabyte.

### [Bab 09: BI DevOps, ALM & Automated Deployment Pipelines](./bab-09-bi-devops-alm/README.md)
Modernisasi rekayasa BI menuju standar software engineering: deklaratif, berbasis kode, dan dioperasionalkan via CI/CD.
* [09-01: Source Control via PBIP, TMDL, & Git Integration](./bab-09-bi-devops-alm/09-01-pbip-tmdl-git-integration.md)
  * Arsitektur file Power BI Project (PBIP), dekonstruksi model menjadi Tabular Model Definition Language (TMDL), dan strategi merge branching di Git.
* [09-02: ALM Deployment Pipelines & Parameter Rules Management](./bab-09-bi-devops-alm/09-02-alm-deployment-pipelines.md)
  * Automasi perpindahan artefak melalui tahap Development, Test, dan Production menggunakan Deployment Pipelines dan parameter swapping.
* [09-03: Scripting Automation: Tabular Editor 3, TOM API, & CI/CD Pipelines](./bab-09-bi-devops-alm/09-03-tabular-editor-ci-cd-automation.md)
  * Penerapan Best Practice Analyzer (BPA) secara otomatis, automasi modifikasi model dengan Tabular Object Model (TOM) C#, dan eksekusi via GitHub Actions / Azure DevOps.

### [Bab 10: Modern Fabric Integration & Embedded Analytics](./bab-10-fabric-and-embedded-analytics/README.md)
Mempersiapkan model data untuk ekosistem analitik terpadu generasi berikutnya dan integrasi ke dalam aplikasi pihak ketiga.
* [10-01: Microsoft Fabric Convergence & Direct Lake Architecture](./bab-10-fabric-and-embedded-analytics/10-01-fabric-direct-lake-mode.md)
  * Memahami pergeseran paradigma dari Import ke Direct Lake, pembacaan file Delta Parquet langsung dari OneLake tanpa konsumsi refresh time.
* [10-02: Advanced Analytics: Integrasi PySpark, Python/R, & AI Insights](./bab-10-fabric-and-embedded-analytics/10-02-advanced-analytics-pyspark-python.md)
  * Transformasi data terdistribusi menggunakan Fabric Spark Notebooks, skrip visualisasi Python/R native, dan model prediktif Azure OpenAI.
* [10-03: Power BI Embedded Architecture: App-Owns-Data vs User-Owns-Data](./bab-10-fabric-and-embedded-analytics/10-03-power-bi-embedded.md)
  * Integrasi analitik ke portal kustom via REST APIs, Power BI JavaScript SDK, Service Principal Authentication, dan konfigurasi skenario RLS custom-token.

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title:
**Global Omnichannel Supply Chain & Financial Intelligence Platform (GOSC-FIP)**

### 1. Deskripsi Skenario Bisnis
Sebuah korporasi retail multinasional beroperasi di 12 negara dengan ribuan SKU produk, 500+ outlet fisik, serta kanal e-commerce cross-border. Korporasi membutuhkan satu platform analitik terpadu (*Single Source of Truth*) yang menggabungkan transaksi harian penjualan, logistik inventaris, dan buku besar keuangan dengan SLA latensi data tinggi, kompresi maksimal, dan aturan pembatasan akses data regional yang ketat.

### 2. Arsitektur Solusi & Komponen Teknis
```
[ERP / CRM / POS / WMS]
        │
        ▼ (Azure Data Factory / Databricks)
[OneLake / ADLS Gen2 Parquet Medallion Layer]
        │
        ▼
[Enterprise Semantic Model (PBIP/TMDL)]
  ├── Storage Mode: Composite / Direct Lake
  ├── Modeling: Kimball Star Schema (>10 Juta Baris Fact)
  ├── Logic Engine: Complex DAX Measures
  ├── Security Layer: Dynamic RLS (Org Hierarchy) + OLS
  └── Optimization: VertiPaq Analyzed, Aggregations Enabled
        │
        ▼
[Power BI App Workspace Orchestration]
  ├── Multi-Audience Deployment (Executive, Finance, Logistics)
  ├── CI/CD: Azure DevOps + Tabular Editor BPA Validation
  └── Interactivity: Drillthrough, Parameterized UX, IBCS Visuals
```

### 3. Persyaratan Deliverables Proyek
Setiap siswa wajib menghasilkan repositori proyek utuh dengan kriteria berikut:

1. **Model Data Relasional (Kimball Star Schema):**
   * Minimal 2 Fact Tables: `Fact_SalesTransactions` (granularitas per baris checkout) dan `Fact_InventorySnapshot` (granularitas harian gudang).
   * Minimal 5 Dimension Tables: `Dim_Product`, `Dim_Customer`, `Dim_Store`, `Dim_Date` (termasuk offset flags & kalender fiskal khusus), dan `Dim_Geography`.
   * Skema Star murni tanpa relasi *bi-directional* langsung antar dimensi.

2. **Kalkulasi DAX Lanjutan (Min. 10 Ukuran Kompleks):**
   * *Dynamic Currency Conversion* berdasarkan kurs fluktuatif harian.
   * *Stock-out Prediction & Days-of-Supply (Semi-Additive measure)*.
   * *Same-Store-Sales (SSS) Growth* (memfilter hanya toko yang sudah beroperasi >12 bulan).
   * *Cohort-based Customer Retention & Churn Rate* dinamis.

3. **Keamanan & Kepatuhan Enterprise:**
   * Dynamic RLS berbasis Azure Active Directory (simulasi UPN) di mana Regional Manager hanya dapat melihat data negara masing-masing secara otomatis berdasarkan bagan struktur hierarki.
   * OLS diterapkan pada kolom laba kotor (*Gross Margin*) dan harga modal (*Unit Cost*) untuk role non-Finance.

4. **Kinerja & Optimasi Terverifikasi:**
   * Laporan audit **DAX Studio / VertiPaq Analyzer**:
     * Kolom kardinalitas tinggi dieliminasi/dioptimasi.
     * Evaluasi waktu respon query visual di bawah 800ms untuk 95% interaksi dashboard.
     * Implementasi *User-Defined Aggregation Table* untuk data penjualan historis.

5. **DevOps & Source Code Automation:**
   * Seluruh model wajib disimpan dalam format `.pbip` dengan skrip `TMDL`.
   * Repositori menyertakan pipeline file `azure-pipelines.yml` atau GitHub Actions workflow yang menjalankan rule-check **Tabular Editor Best Practice Analyzer (BPA)** sebelum deployment ke Power BI Service stage.

---

## 5. Pedoman Pembelajaran

* Pelajari materi berurutan dari Bab 01 hingga Bab 10 untuk menjaga koherensi pemahaman arsitektur.
* Kerjakan seluruh latihan hands-on yang terdapat pada setiap berkas modul Markdown sebelum melangkah ke bab berikutnya.
* Validasi pemahaman DAX dengan selalu menguji modifikasi konteks dan Storage Engine query traces di DAX Studio.
* Selamat merekayasa platform analitik data berskala enterprise!