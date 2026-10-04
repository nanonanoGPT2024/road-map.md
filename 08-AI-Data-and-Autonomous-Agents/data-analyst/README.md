# Modern Enterprise Data Analyst Curriculum
### *Architecting Data-Driven Decision Systems: From Raw Ingestion to Executive Strategy*

---

## 1. Course Overview & Mindset

Kurikulum **Modern Enterprise Data Analyst** dirancang untuk mentransformasi praktisi data dari sekadar *"report builder"* pasif menjadi *"strategic business driver"* yang mandiri. Di era modern, seorang Data Analyst kelas atas dituntut menguasai irisan tiga pilar fundamental: **Engineering Rigor** (SQL tingkat lanjut, *data modeling*, pipeline dbt, dan otomatisasi Python), **Statistical Literacy** (inferensi kausal, probabilistic modeling, dan rigorous A/B testing), serta **Commercial Acumen** (unit economics, dekomposisi metrik finansial, dan presentasi berbasis rekomendasi aksi).

```
                      +------------------------------------------+
                      |       THE STRATEGIC DATA ANALYST         |
                      +------------------------------------------+
                                           |
         +---------------------------------+---------------------------------+
         |                                 |                                 |
         v                                 v                                 v
+------------------+             +--------------------+            +-------------------+
| ENGINEERING      |             | STATISTICAL        |            | COMMERCIAL        |
| RIGOR            |             | LITERACY           |            | ACUMEN            |
|------------------|             |--------------------|            |-------------------|
| • SQL / CTEs     |             | • Causal Inference |            | • Unit Economics  |
| • dbt & CI/CD    | <=========> | • Hypothesis Test  | <========> | • Metric Trees    |
| • Data Modeling  |             | • Diff-in-Diff     |            | • Exec Storyteller|
| • Python/Polars  |             | • A/B Experiments  |            | • P&L Impact      |
+------------------+             +--------------------+            +-------------------+
```

### Pola Pikir (Mindset) Utama:
1. **Business Outcome First, Tools Second**: SQL, Python, dan BI hanyalah instrumen. Nilai seorang analis diukur dari seberapa besar dampak finansial atau efisiensi operasional yang dihasilkan oleh rekomendasinya.
2. **Deterministic Data Integrity**: Analisis yang brilian di atas data yang kotor adalah halusinasi. Analis wajib memvalidasi kualitas data, menangani anomali, dan memahami *lineage* hulu-ke-hilir sebelum menarik kesimpulan.
3. **Hypothesis-Driven Exploration**: Hindari *data dredging* (menggali data tanpa tujuan). Mulai dari hipotesis bisnis yang jelas (*MECE framework*), lalu uji kebenarannya menggunakan uji statistik yang valid.
4. **Reproducibility by Design**: Semua pipeline analisis harus terdokumentasi, menggunakan *version control* (Git), deterministik, dan dapat dijalankan ulang tanpa intervensi manual yang rentan *human error*.

---

## 2. Learning Roadmap

```text
E2E Enterprise Data Analyst Roadmap
│
├── [BAB 01] Business Problem Solving & Analytics Foundations
│   ├── Modul 01.1: Framework Dekomposisi Metrik & MECE Issue Trees
│   ├── Modul 01.2: Unit Economics, SaaS Metrics, & E-Commerce KPIs
│   └── Modul 01.3: Data Translation: Mengubah Ambiguitas Bisnis ke Spesifikasi Data
│
├── [BAB 02] Advanced Spreadsheet Engineering & Financial Modeling
│   ├── Modul 02.1: Dynamic Arrays, Matrix Manipulation, & Data Hygiene
│   ├── Modul 02.2: Financial & Operational Scenario Modeling (Monte Carlo, Solver)
│   └── Modul 02.3: Spreadsheet Automation: Scripting & Enterprise Reporting
│
├── [BAB 03] Relational Databases & Production-Grade SQL Engineering
│   ├── Modul 03.1: Complex Joins, Set Theory, & Query Execution Plans
│   ├── Modul 03.2: Window Functions & Analytics Frame Engineering
│   └── Modul 03.3: Recursive CTEs, Optimization, & Analytical Query Tuning
│
├── [BAB 04] Modern Data Warehousing & Dimensional Data Modeling
│   ├── Modul 04.1: Kimball Dimensional Modeling (Fact & Star/Snowflake Dimensions)
│   ├── Modul 04.2: Slowly Changing Dimensions (SCD Type 1, 2, 3, 4, 6)
│   └── Modul 04.3: Analytical Data Lakehouse Architecture (BigQuery/Snowflake)
│
├── [BAB 05] Python Data Engineering & Exploratory Data Analysis (EDA)
│   ├── Modul 05.1: High-Performance Vectorization: NumPy & Pandas vs Polars
│   ├── Modul 05.2: Data Wrangling, Imputation, & Structural Anomaly Detection
│   └── Modul 05.3: Programmatic EDA & Visual Distribution Diagnostics
│
├── [BAB 06] Applied Statistics & Experimentation (A/B Testing)
│   ├── Modul 06.1: Probabilitas, Distribusi Sampel, & Central Limit Theorem
│   ├── Modul 06.2: Parametric & Non-Parametric Hypothesis Testing
│   └── Modul 06.3: Enterprise A/B Testing: Sample Sizing, SRM, & Causal Inference
│
├── [BAB 07] Enterprise Business Intelligence & Semantic Layer Architecture
│   ├── Modul 07.1: Semantic Layer Modeling (Looker/Power BI/Tableau)
│   ├── Modul 07.2: Complex Calculations (DAX Context Transition / Tableau LOD)
│   └── Modul 07.3: Executive Dashboard UX & Visual Perception Principles
│
├── [BAB 08] Applied Machine Learning & Predictive Analytics for Analysts
│   ├── Modul 08.1: Unsupervised Learning: Customer Segmentation (RFM + K-Means)
│   ├── Modul 08.2: Supervised Learning: Churn & Conversion Prediction
│   └── Modul 08.3: Time Series Forecasting: Decompositions, ARIMA, & Prophet
│
├── [BAB 09] Analytics Engineering: dbt, Git, & Data Governance
│   ├── Modul 09.1: Git Workflow, Semantic Versioning, & PR Code Review
│   ├── Modul 09.2: Data Transformation using dbt Core (Models, Macros, Tests)
│   └── Modul 09.3: Data Governance, Lineage, Auditing, & Privacy Regulations
│
└── [BAB 10] Strategic Stakeholder Communication & Executive Storytelling
    ├── Modul 10.1: The Pyramid Principle & Minto Executive Framing
    ├── Modul 10.2: Crafting Decision-Oriented Analytical Memos (1-Pager)
    └── Modul 10.3: Presentation Delivery, Objection Handling, & Data Ethics
```

---

## 3. Navigasi Detail Bab 01 s/d Bab 10

---

### [BAB 01: Business Problem Solving & Analytics Foundations](./01-business-problem-solving/README.md)
*Membangun fondasi logika berpikir kritis untuk mendekonstruksi target performa bisnis menjadi variabel-variabel kuantitatif.*

* [Modul 01.1 - Framework Dekomposisi Metrik & MECE Issue Trees](./01-business-problem-solving/01-metric-decomposition-mece.md)
  * Mempelajari prinsip *Mutually Exclusive, Collectively Exhaustive* (MECE) untuk membedah masalah bisnis kompleks.
  * Konstruksi *Metric Driver Trees* untuk melacak akar penyebab perubahan target finansial.
  * Identifikasi *leading* vs. *lagging indicators* dalam ekosistem perusahaan berbasis data.

* [Modul 01.2 - Unit Economics, SaaS Metrics, & E-Commerce KPIs](./01-business-problem-solving/02-unit-economics-and-kpis.md)
  * Menghitung dan memvalidasi LTV (*Customer Lifetime Value*), CAC (*Customer Acquisition Cost*), Payback Period, dan Rasio LTV:CAC.
  * Pemodelan metrik *growth & churn*: Gross/Net Retention Rate (GRR/NRR), Monthly Recurring Revenue (MRR) Bridges, dan Cohort Attrition.
  * Analisis efisiensi platform e-commerce: AOV, GMV, Take Rate, Contribution Margin 1-3, dan Cart Abandonment Rate.

* [Modul 01.3 - Data Translation: Mengubah Ambiguitas Bisnis ke Spesifikasi Data](./01-business-problem-solving/03-business-to-data-translation.md)
  * Metodologi pengumpulan kebutuhan stakeholder bisnis tanpa bias kognitif.
  * Menyusun *Analytics Problem Definition Document* (APDD) yang mencakup batasan teknis, kriteria keberhasilan, dan asumsi.
  * Memitigasi risiko *scope creep* dan mendefinisikan *definition of done* untuk proyek analitik.

---

### [BAB 02: Advanced Spreadsheet Engineering & Financial Modeling](./02-advanced-spreadsheet-engineering/README.md)
*Pemanfaatan spreadsheet tingkat lanjut sebagai engine komputasi analisis cepat, prototyping model, dan simulasi skenario deterministik.*

* [Modul 02.1 - Dynamic Arrays, Matrix Manipulation, & Data Hygiene](./02-advanced-spreadsheet-engineering/01-dynamic-arrays-hygiene.md)
  * Penguasaan fungsi array dinamis: `LAMBDA`, `LET`, `FILTER`, `UNIQUE`, `SCAN`, dan `REDUCE`.
  * Normalisasi data tidak terstruktur: penanganan duplikasi tersembunyi, teks parsing via RegEx di Sheets/Excel, dan standarisasi zona waktu.
  * Desain spreadsheet modular dengan pemisahan tegas antara layer *Input*, *Calculation*, dan *Presentation*.

* [Modul 02.2 - Financial & Operational Scenario Modeling](./02-advanced-spreadsheet-engineering/02-scenario-modeling.md)
  * Konstruksi tabel sensitivitas multi-variabel (*Data Tables*) untuk stress-testing margin operasional.
  * Penerapan *Goal Seek* dan optimasi linear/non-linear menggunakan solver engine.
  * Implementasi simulasi Monte Carlo berbasis formula native spreadsheet untuk mengestimasi rentang volatilitas pendapatan.

* [Modul 02.3 - Spreadsheet Automation: Scripting & Enterprise Reporting](./02-advanced-spreadsheet-engineering/03-scripting-and-automation.md)
  * Otomasi pipeline spreadsheet via Google Apps Script (JavaScript) dan Excel Office Scripts (TypeScript).
  * Ekstraksi data real-time via API eksternal langsung ke lembar kerja secara terjadwal.
  * Mekanisme kontrol akses data: formula locking, data protection, dan jejak audit audit log formula.

---

### [BAB 03: Relational Databases & Production-Grade SQL Engineering](./03-sql-engineering/README.md)
*Penguasaan bahasa SQL analitik tingkat lanjut untuk querying jutaan baris data secara efisien dan deterministik.*

* [Modul 03.1 - Complex Joins, Set Theory, & Query Execution Plans](./03-sql-engineering/01-complex-joins-execution-plans.md)
  * Deep dive Join Mechanics: Hash Join, Merge Join, Nested Loops, Non-Equi Joins, dan Cartesian handling.
  * Pembacaan `EXPLAIN ANALYZE` execution plans: menganalisis Cost, Sequential Scans, Index Lookups, dan Memory Spills.
  * Mengatasi jebakan umum SQL: Trap Fan-out pada one-to-many joins, Chasm Traps, dan penanganan nilai `NULL` berbasis three-valued logic.

* [Modul 03.2 - Window Functions & Analytics Frame Engineering](./03-sql-engineering/02-window-functions-frames.md)
  * Penggunaan partisi analitik: `ROW_NUMBER()`, `RANK()`, `DENSE_RANK()`, `NTILE()`, dan `PERCENT_RANK()`.
  * Spesifikasi explicit frame clauses: `ROWS/RANGE/GROUPS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`.
  * Perhitungan running totals, moving average berbobot, time-series gap detection, dan lead/lag delta tracking.

* [Modul 03.3 - Recursive CTEs, Optimization, & Analytical Query Tuning](./03-sql-engineering/03-recursive-ctes-and-tuning.md)
  * Implementasi Recursive Common Table Expressions (CTE) untuk mengurai struktur hierarki organisasi dan data graf interaksi user.
  * Transformasi data: Dynamic Pivoting/Unpivoting via `CASE WHEN`, `CROSS JOIN LATERAL`, dan `ARRAY_AGG`.
  * Optimasi query skala besar: Partition Pruning, Sharding strategies, dan Materialized Views indexing.

---

### [BAB 04: Modern Data Warehousing & Dimensional Data Modeling](./04-data-warehousing-modeling/README.md)
*Arsitektur penyimpanan analitik enterprise, metodologi Kimball, dan optimasi struktur schema analitik modern.*

* [Modul 04.1 - Kimball Dimensional Modeling](./04-data-warehousing-modeling/01-kimball-dimensional-modeling.md)
  * Desain Star Schema vs Snowflake Schema: Trade-off redundancy, I/O performance, dan usability untuk reporting.
  * Klasifikasi Fact Tables: Transactional Facts, Periodic Snapshot Facts, dan Accumulating Snapshot Facts.
  * Pembangunan Conformed Dimensions, Role-Playing Dimensions, dan penanganan Factless Fact Tables.

* [Modul 04.2 - Slowly Changing Dimensions (SCD Type 1, 2, 3, 4, 6)](./04-data-warehousing-modeling/02-slowly-changing-dimensions.md)
  * Karakteristik dan implementasi implementatif dari SCD Type 1 (Overwrite) dan SCD Type 2 (Historical Tracking via `valid_from`, `valid_to`, `is_current`).
  * Desain SCD Type 4 (Historical Archive Tables) dan Hybrid Type 6 (1+2+3).
  * Penanganan *late-arriving data* dan *early-arriving facts* pada pipeline pemrosesan analitik.

* [Modul 04.3 - Analytical Data Lakehouse Architecture (BigQuery/Snowflake)](./04-data-warehousing-modeling/03-lakehouse-architecture.md)
  * Arsitektur Data Warehouse Cloud Modern: Pemisahan Compute vs Storage pada BigQuery, Snowflake, dan Databricks.
  * Clustering Keys, Micro-partitioning, dan teknik mitigasi biaya komputasi query (Slot allocations, Credit management).
  * Penerapan Zero-Copy Cloning, Time Travel, dan Data Sharing lintas platform aman.

---

### [BAB 05: Python Data Engineering & Exploratory Data Analysis (EDA)](./05-python-and-eda/README.md)
*Manipulasi data skala besar dengan ekosistem Python modern, optimasi komputasi memori, dan teknik eksplorasi data mendalam.*

* [Modul 05.1 - High-Performance Vectorization: NumPy & Pandas vs Polars](./05-python-and-eda/01-vectorization-pandas-polars.md)
  * Menghilangkan penggunaan looping Python manual: Vectorized operations, broadcasting arrays, dan optimasi memory footprint (`downcasting dtypes`).
  * Paradigma modern dengan Polars: Lazy Evaluation Engine, Apache Arrow format, dan pemrosesan multi-threaded.
  * Profiling kode performansi komputasi data: Memory profiler dan runtime benchmark execution.

* [Modul 05.2 - Data Wrangling, Imputation, & Structural Anomaly Detection](./05-python-and-eda/02-wrangling-anomaly-detection.md)
  * Penanganan Missing Values deterministik: Missing Completely at Random (MCAR), MAR, dan MNAR dengan teknik imputasi statistik/algoritmik.
  * Deteksi Outlier: Z-score, Tukey’s IQR fences, isolation forests, dan deteksi nilai batas logis bisnis.
  * String matching fuzzy dan resolusi entitas inkonsisten menggunakan Levenshtein distance dan regular expression.

* [Modul 05.3 - Programmatic EDA & Visual Distribution Diagnostics](./05-python-and-eda/03-programmatic-eda.md)
  * Eksplorasi multivariat: Correlation matrices (Pearson, Spearman, Kendall Tau), p-value significance checking, dan Pairplot diagnostics.
  * Analisis Skewness, Kurtosis, dan transformasi data (Log Transform, Box-Cox, Yeo-Johnson).
  * Otomasi laporan EDA dengan custom Python scripts dan framework diagnostic viz (Seaborn, Plotly).

---

### [BAB 06: Applied Statistics & Experimentation (A/B Testing)](./06-statistics-and-ab-testing/README.md)
*Penerapan metode statistik inferensial formal dan desain eksperimen untuk memvalidasi kausalitas perubahan produk atau strategi bisnis.*

* [Modul 06.1 - Probabilitas, Distribusi Sampel, & Central Limit Theorem](./06-statistics-and-ab-testing/01-probability-and-distributions.md)
  * Fondasi Probabilitas Diskrit dan Kontinu: Normal, Binomial, Poisson, dan Exponential Distributions.
  * Teori Limit Terpusat (*Central Limit Theorem*) dan aplikasinya pada penarikan kesimpulan data non-normal.
  * Confidence Intervals vs Prediction Intervals: Formula, interpretasi praktis, dan bias miskonsepsi interval keyakinan.

* [Modul 06.2 - Parametric & Non-Parametric Hypothesis Testing](./06-statistics-and-ab-testing/02-hypothesis-testing.md)
  * Menjalankan Two-Sample T-Test, Paired T-Test, Z-Test untuk proporsi, dan ANOVA (One-Way & Two-Way).
  * Uji Non-Parametrik: Mann-Whitney U, Wilcoxon Signed-Rank, dan Chi-Square Test of Independence untuk data berskew ekstrem.
  * Mengendalikan Type I Error ($\alpha$), Type II Error ($\beta$), Statistical Power ($1 - \beta$), dan koreksi multi-perbandingan (Bonferroni / FDR).

* [Modul 06.3 - Enterprise A/B Testing: Sample Sizing, SRM, & Causal Inference](./06-statistics-and-ab-testing/03-ab-testing-causal-inference.md)
  * Power Analysis: Menghitung Minimum Detectable Effect (MDE), ukuran sampel, dan estimasi durasi pengujian.
  * Diagnostik kegagalan eksperimen: Deteksi Sample Ratio Mismatch (SRM) dan Simpson’s Paradox.
  * Causal Inference non-eksperimental: Quasi-Experiments, Difference-in-Differences (DiD), Propensity Score Matching (PSM), dan Synthetic Control.

---

### [BAB 07: Enterprise Business Intelligence & Semantic Layer Architecture](./07-enterprise-bi-and-dashboards/README.md)
*Membangun antarmuka dashboard interaktif yang intuitif, scalable, dan memiliki tata kelola semantic logic terpusat.*

* [Modul 07.1 - Semantic Layer Modeling (Looker/Power BI/Tableau)](./07-enterprise-bi-and-dashboards/01-semantic-layer-modeling.md)
  * Definisi Semantic Layer: Memusatkan logika bisnis (`metrics definitions`) agar terisolasi dari reporting tool.
  * Arsitektur Data Model di BI: DirectQuery vs In-Memory Storage Engine (VertiPaq/Hyper Engine).
  * Konfigurasi Single Source of Truth: Menghindari duplikasi definisi revenue atau user active lintas departemen.

* [Modul 07.2 - Complex Calculations (DAX Context Transition / Tableau LOD)](./07-enterprise-bi-and-dashboards/02-advanced-bi-calculations.md)
  * Power BI DAX: Evaluasi Row Context vs Filter Context, context transition menggunakan `CALCULATE`, `KEEPFILTERS`, dan Time Intelligence.
  * Tableau LOD Expressions: Penguasaan `FIXED`, `INCLUDE`, dan `EXCLUDE` untuk komputasi agregasi multi-level.
  * Performance tuning visual BI: Mengurangi kardinalitas dimensi dan audit query BI traces via Performance Analyzer.

* [Modul 07.3 - Executive Dashboard UX & Visual Perception Principles](./07-enterprise-bi-and-dashboards/03-dashboard-ux-perception.md)
  * Gestalt Principles of Visual Perception dalam desain dashboard: Proximity, Similarity, Enclosure, dan Focal Points.
  * Hirarki visual laporan eksekutif: 5-Second Rule, Z-Pattern/F-Pattern layout design, dan tipografi data.
  * Desain interaksi UX: drill-down hierarkis, cross-filtering terarah, parameter controls, dan optimasi mobile layouts.

---

### [BAB 08: Applied Machine Learning & Predictive Analytics for Analysts](./08-applied-ml-and-prediction/README.md)
*Pemanfaatan model machine learning terapan untuk klasifikasi, segmentasi, dan peramalan tren bisnis masa depan.*

* [Modul 08.1 - Unsupervised Learning: Customer Segmentation (RFM + K-Means)](./08-applied-ml-and-prediction/01-segmentation-rfm-kmeans.md)
  * Konstruksi RFM Matrix (Recency, Frequency, Monetary) dari raw transaction logs.
  * Algoritma K-Means Clustering: Data scaling/normalization, Elbow Method, dan Silhouette Coefficient analysis.
  * Translasi cluster matematika ke persona operasional bisnis yang dapat ditindaklanjuti (Actionable Segments).

* [Modul 08.2 - Supervised Learning: Churn & Conversion Prediction](./08-applied-ml-and-prediction/02-churn-and-conversion-ml.md)
  * Pemodelan klasifikasi biner menggunakan Logistic Regression dan Gradient Boosting (XGBoost/LightGBM).
  * Evaluasi model komersial: Confusion Matrix, Precision, Recall, F1-Score, ROC-AUC, dan Cost-Benefit Matrix threshold tuning.
  * Interpretasi model: Analisis Feature Importance dan SHAP (SHapley Additive exPlanations) values untuk stakeholder bisnis.

* [Modul 08.3 - Time Series Forecasting: Decompositions, ARIMA, & Prophet](./08-applied-ml-and-prediction/03-time-series-forecasting.md)
  * Dekomposisi Time Series: Tren, Musiman (Seasonality), Siklis, dan Residual (Additive vs Multiplicative).
  * Stasioneritas: Uji Augmented Dickey-Fuller (ADF) dan teknik differencing data time series.
  * Modeling peramalan performa penjualan menggunakan ARIMA/SARIMAX dan Meta Prophet dengan penambahan external regressor/holidays.

---

### [BAB 09: Analytics Engineering: dbt, Git, & Data Governance](./09-analytics-engineering-governance/README.md)
*Menerapkan praktik terbaik software engineering pada workflow transformasi data untuk menjamin kualitas dan reliabilitas.*

* [Modul 09.1 - Git Workflow, Semantic Versioning, & PR Code Review](./09-analytics-engineering-governance/01-git-and-code-reviews.md)
  * Git branching strategies (Trunk-based development vs GitFlow) dalam repository analitik.
  * Standar penulisan Pull Request (PR): Clean commit history, automated checks, dan code review checklist analitik.
  * Manajemen dependensi dan isolasi environment virtual (*venv, conda, dockerized analytics*).

* [Modul 09.2 - Data Transformation using dbt Core (Models, Macros, Tests)](./09-analytics-engineering-governance/02-dbt-transformation-testing.md)
  * Struktur project dbt: Staging (`stg_`), Intermediate (`int_`), dan Marts (`fct_`, `dim_`) layers.
  * Modularity menggunakan Jinja templating, Macros, package management, dan Ref functions.
  * Data Reliability Testing: Uji native (`unique`, `not_null`, `relationships`, `accepted_values`) dan custom dbt expectations.

* [Modul 09.3 - Data Governance, Lineage, Auditing, & Privacy Regulations](./09-analytics-engineering-governance/03-governance-and-privacy.md)
  * Membangun Data Lineage end-to-end dan Data Cataloging menggunakan dbt docs dan open-source tools.
  * Implementasi Role-Based Access Control (RBAC), Data Masking, dan Audit Logging pada analytical store.
  * Kepatuhan regulasi perlindungan data privasi konsumen: GDPR, CCPA, dan UU Perlindungan Data Pribadi (UU PDP).

---

### [BAB 10: Strategic Stakeholder Communication & Executive Storytelling](./10-strategic-communication/README.md)
*Mengubah temuan data teknis menjadi narasi strategis yang memikat, meyakinkan, dan menghasilkan aksi nyata di tingkat manajemen C-Suite.*

* [Modul 10.1 - The Pyramid Principle & Minto Executive Framing](./10-strategic-communication/01-pyramid-principle.md)
  * Struktur Komunikasi Barbara Minto: SCQA (Situation, Complication, Question, Answer).
  * Prinsip *Bottom-Line Up Front* (BLUF): Menempatkan kesimpulan dan rekomendasi di pembuka komunikasi.
  * Mengeliminasi jargon teknis: Mengubah metrik model machine learning (e.g., Log-Loss) menjadi dampak finansial langsung (e.g., Estimasi Penghematan Margin).

* [Modul 10.2 - Crafting Decision-Oriented Analytical Memos (1-Pager)](./10-strategic-communication/02-executive-memos.md)
  * Format Amazon-style 1-Pager/6-Pager Memo: Background, Hypothesis, Empirical Findings, Trade-off Decisions, Next Steps.
  * Menampilkan visualisasi data kompresi tinggi: Bullet graphs, sparklines, dan waterfall charts untuk efisiensi ruang.
  * Menulis bagian *Risks and Mitigations*: Proaktif memetakan kelemahan metodologi analisis sebelum ditanya manajemen.

* [Modul 10.3 - Presentation Delivery, Objection Handling, & Data Ethics](./10-strategic-communication/03-presentation-objection-handling.md)
  * Teknik memimpin rapat tinjauan data eksekutif: Manajemen waktu, kontrol alur narasi, dan delegasi diskusi lanjutan.
  * Menghadapi resistensi stakeholder: Menjawab keraguan metodologi, validasi skeptisisme data, dan negosiasi kompromi analitik.
  * Etika Penyajian Data: Menghindari manipulasi sumbu visual grafik (truncated axes), cherry-picking p-values, dan misleading metrics.

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Proyek:
**"OmniMarket Global: End-to-End Enterprise Customer Retention & Unit Economics Intelligence Platform"**

```
+--------------------------------------------------------------------------------------------------+
|                                    CAPSTONE PIPELINE ARCHITECTURE                                |
+--------------------------------------------------------------------------------------------------+
                                                                                                    
 [Raw Operational Data]           [Analytical Lakehouse]                [BI & Predictive Engine]    
 +-------------------+            +---------------------+               +-------------------------+ 
 | PostgreSQL (OLTP) |            | Google BigQuery     |               | Semantic BI Dashboards  | 
 | - Orders & Items  |            |                     |               | (Power BI / Tableau)    | 
 | - Clickstream Log | ---(dbt)---> - Marts: fct_orders | ------------> | - Exec LTV & Unit Econ  | 
 | - CS Tickets      |            | - Marts: dim_users  |               | - Cohort Retention Wall | 
 +-------------------+            | - Agg: cohort_ret   |               +-------------------------+ 
                                  +---------------------+                            |              
                                             |                                       v              
                                             |                          +-------------------------+ 
                                             +------------------------> | Scikit-Learn Engine     | 
                                               (Python Polars Pipeline) | - Churn Risk Score      | 
                                                                        | - RFM Clustering        | 
                                                                        +-------------------------+ 
```

### 1. Business Scenario & Problem Statement
*OmniMarket Global* adalah perusahaan retail e-commerce omnichannel multinasional dengan $250M GMV tahunan. Dalam 3 kuartal terakhir, unit economics perusahaan memburuk drastis:
- **Net Retention Rate (NRR)** turun dari 115% menjadi 88%.
- **Customer Acquisition Cost (CAC)** melonjak sebesar 42% akibat inefisiensi alokasi channel marketing.
- C-Suite mencurigai adanya kanibalisasi margin operasional oleh diskon promo yang tidak terkendali dan tingginya churn rate pada kuartal kedua pasca transaksi pertama (Q2 post-first purchase).

Tim Anda ditugaskan membangun pipeline data warehouse, menganalisis dekomposisi metrik churn secara granular, merancang segmentasi prediktif, menyusun model atribusi efisiensi unit economics, dan mempresentasikannya ke C-Level Executive board.

---

### 2. Dataset Architecture & Scale
Proyek menggunakan dataset sintetis terdistribusi berskala *enterprise-grade* (~5 juta record transaksi):
- `raw_transactions` (OLTP Postgres dump): Log pembelian transaksi, status pembayaran, diskon voucher, fee logistik.
- `raw_web_events` (Clickstream events JSON): Session id, user interactions, add-to-cart, bounce events, platform channel.
- `raw_support_tickets` (Customer Service log): Resolution time, CSAT score, category escalation flags.
- `raw_marketing_spends` (Daily marketing aggregated spend per channel: Meta Ads, Google Search, TikTok, Organic, Affiliate).

---

### 3. Deliverables & Technical Requirements

#### Stage 1: Data Modeling & Transformation (dbt + SQL)
- [ ] Rancang arsitektur model data dimensional (Star Schema) di Google BigQuery / Snowflake.
- [ ] Implementasikan transformasi data menggunakan **dbt Core**:
  - `stg_`: Membersihkan tipe data, unnesting JSON clickstream data, handling timezones.
  - `int_`: Menggabungkan session duration, menghitung interval transaksi, menandai refund flag.
  - `dim_customers`: Dimensi pengguna dengan **SCD Type 2** untuk melacak perubahan tier loyalitas.
  - `fct_orders`: Fact table transaksi partisi per tanggal dengan clustering pada `customer_id`.
- [ ] Terapkan minimal 8 dbt generic & singular tests untuk menjamin zero duplication pada primary keys dan konsistensi relasional antar foreign keys.

#### Stage 2: Exploratory & Statistical Deep-Dive (Python)
- [ ] Eksekusi Vectorized EDA menggunakan **Polars/Pandas** untuk mengidentifikasi korelasi antara kompensasi CS ticket discount dengan repurchase rate.
- [ ] Desain dan evaluasi uji hipotesis formal:
  - Apakah pemberian diskon retensi secara kausal meningkatkan LTV 6-bulan, atau hanya mempercepat pembelian yang memang sudah direncanakan pengguna? (Gunakan *Difference-in-Differences* terhadap kelompok hold-out).
  - Validasi Sample Ratio Mismatch (SRM) terhadap A/B testing campaign diskon terakhir.

#### Stage 3: Predictive Customer Analytics (Machine Learning)
- [ ] **RFM + K-Means Segmentation Engine**: Klasterisasi basis pelanggan ke dalam segmen strategis (e.g., *Champions, At-Risk High Spenders, Discount Chasers, Hibernating*).
- [ ] **Churn Propensity Scoring Pipeline**: Buat model klasifikasi probabilistik (XGBoost/RandomForest) untuk memprediksi probabilitas pelanggan churn dalam 60 hari ke depan.
- [ ] Hitung metrik performa model: ROC-AUC minimal $\ge 0.78$ dan terapkan bobot *Expected Value Framework* guna menentukan batas cut-off probabilitas yang meminimalkan kerugian finansial.

#### Stage 4: Production BI Dashboard (Tableau / Power BI / Looker Studio)
- [ ] Bangun **Executive Control Tower Dashboard** yang mencakup:
  - Visualisasi interaktif Cohort Retention Triangle (Month 0 to Month 12 retention rates).
  - Dekomposisi Waterfall Unit Economics: GMV $\rightarrow$ Diskon $\rightarrow$ COGS $\rightarrow$ Shipping Costs $\rightarrow$ Contribution Margin 1 & 2.
  - Interactive What-If Parameter: Simulasi perbaikan NRR terhadap runway kas perusahaan.

#### Stage 5: Executive Communication Package
- [ ] Susun **1-Pager Strategic Memo** bergaya Minto Pyramid yang merinci akar penyebab drop performa bisnis dan 3 rekomendasi taktis berbobot ROI tinggi.
- [ ] Rancang slide deck ringkas (maksimal 7 slide) yang siap dipresentasikan di hadapan Chief Executive Officer (CEO) dan Chief Financial Officer (CFO).

---

### 4. Evaluation Rubric & Acceptance Criteria

| Kriteria Penilaian | Bobot | Standard Enterprise Excellence (Level 4/4) |
| :--- | :---: | :--- |
| **SQL & Data Modeling** | 25% | Star Schema sempurna; SCD Type 2 terkonfigurasi benar; query dbt modular, fully documented, teruji secara deterministik, tanpa Cartesian risk. |
| **Statistical Rigor** | 20% | Pemilihan metodologi inferensi/uji hipotesis tepat; pemahaman mendalam tentang confounders; zero misinterpretasi p-value; SRM tervalidasi. |
| **Predictive Modeling** | 15% | Data leakage dicegah total; evaluasi model diikat ke metrik nilai moneter nyata (Expected Value Matrix), bukan sekadar akurasi mentah. |
| **Dashboard Architecture** | 20% | Visualisasi mematuhi prinsip persepsi kognitif Gestalt; DAX / LOD formula teroptimasi tanpa lagging interaktif; semantic data layer solid. |
| **Executive Communication**| 20% | Narasi berbasis rekomendasi komersial konkret; zero jargon teknis pada ringkasan eksekutif; estimasi dampak profit/loss terjustifikasi data. |

---

## 5. Cara Menggunakan Repositori Ini

1. **Clone & Environment Setup**:
   ```bash
   git clone https://github.com/modern-data-academy/data-analyst-curriculum.git
   cd data-analyst-curriculum
   python -m venv venv
   source venv/bin/activate  # atau `venv\Scripts\activate` di Windows
   pip install -r requirements.txt
   ```
2. **Navigasi Sekuensial**: Masuki folder direktori bab secara urut dari `01-business-problem-solving/` hingga `10-strategic-communication/`. Setiap modul berisi dokumen konsep teknis, workbook studi kasus, kueri SQL, dan notebook Python yang dapat dieksekusi secara mandiri.
3. **Penyelesaian Capstone Project**: Kerjakan spesifikasi capstone setelah menyelesaikan seluruh materi pada Bab 01 sampai Bab 09, dan gunakan panduan Bab 10 untuk memfinalisasi artifak memo eksekutif Anda.