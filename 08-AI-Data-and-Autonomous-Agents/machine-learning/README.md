# Machine Learning Engineering: Production-Grade Curriculum

Kurikulum komprehensif Machine Learning ini dirancang untuk menjembatani kesenjangan antara riset matematis/teoretis dan rekayasa perangkat lunak skala produksi (*production engineering*). Standar materi mengacu pada ekosistem industri modern: mulai dari fondasi aljabar linear hingga *distributed serving*, *feature store*, dan *MLOps pipeline*.

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
Machine Learning dalam ranah enterprise bukan sekadar memanggil metode `.fit()` dan `.predict()` dari pustaka *black-box* di dalam Jupyter Notebook. Machine Learning adalah rekayasa sistem probabilistik yang membutuhkan:
1. **Mathematical Grounding:** Pemahaman mendalam mengenai optimasi konveks, aljabar linear numerik, kalkulus multivariat, dan teori probabilitas untuk mendiagnosis kegagalan model (*underfitting*, *overfitting*, degradasi gradien).
2. **Deterministic Software Rigor:** Kode Machine Learning harus mengadopsi prinsip *Clean Code*, *type safety*, unit testing matematis, *data validation*, dan modularitas pipeline.
3. **Production-First Mindset:** Model yang tidak dapat di-deploy dengan latensi terprediksi, tanpa observabilitas terhadap *data drift* dan *concept drift*, adalah model yang tidak bernilai secara operasional.

### Standar Teknis & Toolchain
- **Runtime:** Python 3.11+, CUDA 12.x
- **Core Math & Tabular:** NumPy, SciPy, Pandas, Polars, Scikit-Learn
- **Gradient Boosting:** XGBoost, LightGBM, CatBoost
- **Deep Learning Frameworks:** PyTorch, TorchScript, ONNX
- **MLOps & Storage:** MLflow, DVC, Feast (Feature Store), Triton Inference Server, Prometheus, Grafana

---

## 2. Learning Roadmap

```
Machine Learning Curriculum
├── 01. Foundations of Mathematical ML & Computing Architecture
│   ├── 01-linear-algebra-tensors
│   ├── 02-probabilistic-inference
│   └── 03-vectorized-computing
├── 02. Feature Engineering & Data Preprocessing Pipelines
│   ├── 01-eda-anomaly-detection
│   ├── 02-deterministic-transformations
│   └── 03-feature-stores-leakage
├── 03. Classical Supervised Learning: Regression & Classification
│   ├── 01-glm-convex-optimization
│   ├── 02-svm-kernels
│   └── 03-knn-naive-bayes
├── 04. Tree-Based Methods & Ensemble Architectures
│   ├── 01-decision-trees-pruning
│   ├── 02-random-forests
│   └── 03-gradient-boosting
├── 05. Unsupervised Learning & Dimensionality Reduction
│   ├── 01-clustering-algorithms
│   ├── 02-pca-svd
│   └── 03-tsne-umap
├── 06. Deep Learning Foundations & Optimization Dynamics
│   ├── 01-mlp-backprop-autograd
│   ├── 02-optimizers-learning-schedules
│   └── 03-regularization-normalization
├── 07. Specialized Deep Architectures: CV & NLP
│   ├── 01-cnn-architectures
│   ├── 02-sequence-models-attention
│   └── 03-transformers-tokenizers
├── 08. Model Evaluation, Validation & Interpretability
│   ├── 01-cross-validation-metrics
│   ├── 02-shap-lime-explainability
│   └── 03-fairness-bias-auditing
├── 09. MLOps: Experiment Tracking & Pipeline Automation
│   ├── 01-experiment-tracking
│   ├── 02-dvc-pipeline-automation
│   └── 03-orchestration-dag
└── 10. Production Deployment, Serving & Monitoring
    ├── 01-onnx-triton-serving
    ├── 02-realtime-vs-batch
    └── 03-drift-monitoring-alerting
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Foundations of Mathematical ML & Computing Architecture](./bab-01-foundations/README.md)
*Membangun fondasi komputasi numerik, analisis matriks, dan pemodelan statistik.*
- [Modul 01: Aljabar Linear, Operasi Tensor, dan Dekomposisi Matriks](./bab-01-foundations/01-linear-algebra-tensors.md)
  - Fokus: Ruang vektor, eigendecomposition, SVD, proyeksi ortogonal, dan operasi tensor berdimensi tinggi.
- [Modul 02: Teori Probabilitas, Bayesian Inference, dan Information Theory](./bab-01-foundations/02-probabilistic-inference.md)
  - Fokus: Distribusi probabilitas multivariat, Maximum Likelihood Estimation (MLE), Maximum A Posteriori (MAP), Entropy, dan KL-Divergence.
- [Modul 03: Vectorized Computing, Broadcasting, dan Akselerasi SIMD](./bab-01-foundations/03-vectorized-computing.md)
  - Fokus: Arsitektur memori NumPy/C-contiguous, memory layout striding, parallelization via CPU vectorization.

### [Bab 02: Feature Engineering & Data Preprocessing Pipelines](./bab-02-feature-engineering/README.md)
*Standardisasi transformasi data deterministik bebas kebocoran (leakage-free).*
- [Modul 01: Statistical EDA, Outlier Handling, dan Anomaly Detection](./bab-02-feature-engineering/01-eda-anomaly-detection.md)
  - Fokus: Robust statistics, Mahalanobis distance, Isolation Forest, dan penanganan missing data bertipe MCAR/MAR/MNAR.
- [Modul 02: Continuous & Categorical Feature Transformations](./bab-02-feature-engineering/02-deterministic-transformations.md)
  - Fokus: Quantile transformations, Box-Cox, Target Encoding dengan internal cross-fold regularizer, dan Scikit-Learn custom estimators.
- [Modul 03: Feature Store Architecture (Feast) & Data Leakage Prevention](./bab-02-feature-engineering/03-feature-stores-leakage.md)
  - Fokus: Point-in-time joins, offline vs. online storage synchronization, dan mitigasi target/train-test temporal leakage.

### [Bab 03: Classical Supervised Learning: Regression & Classification](./bab-03-supervised-learning/README.md)
*Penerapan algoritma fundamental berbasis optimasi parameter matematis eksplisit.*
- [Modul 01: Generalized Linear Models (GLM) & Convex Optimization](./bab-03-supervised-learning/01-glm-convex-optimization.md)
  - Fokus: Derivasi OLS, Ridge (L2), Lasso (L1), Logistic Regression, Gradient Descent vs. Quasi-Newton (L-BFGS).
- [Modul 02: Support Vector Machines (SVM) & Kernel Methods](./bab-03-supervised-learning/02-svm-kernels.md)
  - Fokus: Karush-Kuhn-Tucker (KKT) conditions, dual formulation, RBF/Polynomial kernels, dan batas margin maksimal.
- [Modul 03: Non-Parametric Models: k-Nearest Neighbors & Naive Bayes](./bab-03-supervised-learning/03-knn-naive-bayes.md)
  - Fokus: KD-Tree/Ball-Tree indexing complexities, Curse of Dimensionality, Gaussian/Multinomial Naive Bayes assumptions.

### [Bab 04: Tree-Based Methods & Ensemble Architectures](./bab-04-ensemble-trees/README.md)
*Dominasi pemodelan data tabular melalui partisi non-linear dan ensemble learning.*
- [Modul 01: Decision Trees, Splitting Criteria, dan Cost-Complexity Pruning](./bab-04-ensemble-trees/01-decision-trees-pruning.md)
  - Fokus: CART algorithm, Information Gain vs. Gini Impurity, Minimal Cost-Complexity Pruning ($\alpha$-pruning).
- [Modul 02: Bagging & Random Forests: Variance Reduction Techniques](./bab-04-ensemble-trees/02-random-forests.md)
  - Fokus: Bootstrap aggregation, out-of-bag (OOB) error estimation, korelasi antar pohon, dan feature importance bias.
- [Modul 03: Gradient Boosting Mechanisms: XGBoost, LightGBM, CatBoost](./bab-04-ensemble-trees/03-gradient-boosting.md)
  - Fokus: Algoritma ekspansi Taylor orde-2, Histogram-based binning, Gradient-based One-Side Sampling (GOSS), dan symmetric trees.

### [Bab 05: Unsupervised Learning & Dimensionality Reduction](./bab-05-unsupervised-learning/README.md)
*Eksplorasi manifold data tersembunyi, reduksi dimensi spasial, dan klasterisasi.*
- [Modul 01: Partitioning & Density-Based Clustering (k-Means, DBSCAN, HDBSCAN)](./bab-05-unsupervised-learning/01-clustering-algorithms.md)
  - Fokus: k-Means++ initialization, Voronoi cells, core distance, noise points handling, dan density tree cluster extraction.
- [Modul 02: Linear Dimensionality Reduction: PCA, SVD, & Kernel PCA](./bab-05-unsupervised-learning/02-pca-svd.md)
  - Fokus: Maximizing variance projection, analisis spektral matriks kovarian, rekonstruksi loss, dan non-linear kernel projection.
- [Modul 03: Non-Linear Manifold Learning: t-SNE & UMAP](./bab-05-unsupervised-learning/03-tsne-umap.md)
  - Fokus: Teori topologi aljabar, fuzzy simplicial sets, pemeliharaan struktur global vs. lokal, serta kompleksitas komputasi.

### [Bab 06: Deep Learning Foundations & Optimization Dynamics](./bab-06-deep-learning-core/README.md)
*Transisi ke representasi non-linear berlapis dan dynamic computational graphs.*
- [Modul 01: Multi-Layer Perceptrons & Autograd Engine from Scratch](./bab-06-deep-learning-core/01-mlp-backprop-autograd.md)
  - Fokus: Directed acyclic graphs untuk turunan parsial, backpropagation vector-Jacobian products, custom autograd implementations.
- [Modul 02: Optimization Landscapes: SGD, Momentum, AdamW, dan LR Schedules](./bab-06-deep-learning-core/02-optimizers-learning-schedules.md)
  - Fokus: Ill-conditioned surfaces, decoupled weight decay (AdamW), warm-up routines, dan Cosine Annealing.
- [Modul 03: Deep Regularization: Dropout, Batch/Layer Normalization, Residuals](./bab-06-deep-learning-core/03-regularization-normalization.md)
  - Fokus: Internal covariate shift myth, gradient propagation via skip-connections, dan representational capacity stability.

### [Bab 07: Specialized Deep Architectures: CV & NLP](./bab-07-cv-and-nlp/README.md)
*Spesialisasi representasi fitur spasial (Vision) dan kontekstual sekuensial (Language).*
- [Modul 01: Convolutional Architectures & Vision Backbones](./bab-07-cv-and-nlp/01-cnn-architectures.md)
  - Fokus: Receptive fields, spatial downsampling/striding, residual networks (ResNet), dan ConvNeXt.
- [Modul 02: Sequence Processing: Recurrent Units & Additive/Scaled Attention](./bab-07-cv-and-nlp/02-sequence-models-attention.md)
  - Fokus: Vanishing gradient pada vanilla RNN, gating mechanism pada LSTM/GRU, dan formulasi Bahdanau vs. Luong attention.
- [Modul 03: Transformer Architecture from Scratch & Subword Tokenizers](./bab-07-cv-and-nlp/03-transformers-tokenizers.md)
  - Fokus: Multi-Head Self-Attention, positional encodings, Byte-Pair Encoding (BPE), dan implementasi encoder-decoder layers.

### [Bab 08: Model Evaluation, Validation & Interpretability](./bab-08-evaluation-explainability/README.md)
*Verifikasi performa model secara objektif, pencegahan bias, dan audit keputusan model.*
- [Modul 01: Advanced Validation Strategies & Business-Metric Alignment](./bab-08-evaluation-explainability/01-cross-validation-metrics.md)
  - Fokus: Stratified Group Time-Series Split, Cost-Benefit matrix alignment, Expected Calibration Error (ECE), Brier Score.
- [Modul 02: Model Explainability: SHAP, LIME, dan Counterfactuals](./bab-08-evaluation-explainability/02-shap-lime-explainability.md)
  - Fokus: Shapley values teoretis, KernelSHAP vs. TreeSHAP, local surrogate models, dan batas validitas interpretasi post-hoc.
- [Modul 03: Fairness, Demographic Parity, & Model Robustness Audits](./bab-08-evaluation-explainability/03-fairness-bias-auditing.md)
  - Fokus: Disparate Impact ratio, Equalized Odds, adversarial perturbation tests, dan evaluasi ketahanan model terhadap input noise.

### [Bab 09: MLOps: Experiment Tracking & Pipeline Automation](./bab-09-mlops-pipelines/README.md)
*Membangun infrastruktur otomasi machine learning yang reproducible dan auditable.*
- [Modul 01: Experiment Tracking & Model Registry dengan MLflow](./bab-09-mlops-pipelines/01-experiment-tracking.md)
  - Fokus: Param/metric auto-logging, model artifact signature enforcement, stage transitions (Staging -> Production).
- [Modul 02: Data & Pipeline Versioning Menggunakan DVC](./bab-09-mlops-pipelines/02-dvc-pipeline-automation.md)
  - Fokus: Content-addressable storage untuk datasets, reproducible pipeline stages (`dvc.yaml`), dan integrasi Git hooks.
- [Modul 03: DAG-Based Workflow Orchestration (Kubeflow / Prefect)](./bab-09-mlops-pipelines/03-orchestration-dag.md)
  - Fokus: Dynamic tasks, retry semantics, containerized step isolation, dan scheduling retrain otomatis berbasis ambang metrik.

### [Bab 10: Production Deployment, Serving & Monitoring](./bab-10-deployment-serving/README.md)
*Eksekusi deployment skala tinggi dengan latensi rendah dan observabilitas berkelanjutan.*
- [Modul 01: High-Performance Serving: ONNX Runtime & Triton Server](./bab-10-deployment-serving/01-onnx-triton-serving.md)
  - Fokus: Graph optimizations, quantization (INT8/FP16), dynamic batching, concurrent model execution di Triton.
- [Modul 02: Serving Architectures: Real-Time REST/gRPC vs. Asynchronous Streaming](./bab-10-deployment-serving/02-realtime-vs-batch.md)
  - Fokus: Desain microservices berbasis FastAPI/gRPC, zero-copy deserialization, dan Apache Kafka worker pattern.
- [Modul 03: Observabilitas Produksi: Data Drift, Concept Drift, & Alerting](./bab-10-deployment-serving/03-drift-monitoring-alerting.md)
  - Fokus: Kolmogorov-Smirnov test, Population Stability Index (PSI), Wasserstein Distance, Prometheus exporter, Grafana dashboards.

---

## 4. Enterprise Capstone Project

### Real-Time Financial Fraud & AML Detection Platform
Peserta diwajibkan membangun platform end-to-end terdistribusi untuk mendeteksi transaksi fraud finansial secara real-time dan anti-money laundering (AML).

```
[ Ingest Stream (Kafka) ] 
       │
       ▼
[ Feature Pipeline (Feast) ] ──> Point-in-Time Join ──> Feature Vector
       │
       ▼
[ Ensemble Model Cluster ]
  ├── 1. GBDT (LightGBM): Tabular Feature Specialist
  └── 2. Deep Sequence Model (Transformer): Behavioral Sequence Specialist
       │
       ▼
[ Triton Inference Server (ONNX Optimized) ] ──> Decision: [Approve / Deny / Review]
       │
       ▼
[ Prometheus + Grafana Observability ] ──> Drift & Latency Tracking
```

### Spesifikasi Teknis & Persyaratan Arsitektur
1. **Hybrid Inference Engine:**
   - Model 1: LightGBM untuk atribut transaksi terstruktur (frekuensi, delta nominal, lokasi).
   - Model 2: Transformer Encoder kecil (ONNX FP16) untuk mengekstraksi representasi sekuensial dari 50 riwayat transaksi terakhir nasabah.
   - Output kedua model digabungkan melalui *calibrated meta-classifier*.
2. **Feature Store Integration:**
   - Integrasi Feast: Redis untuk low-latency retrieval (<5ms) pada fitur *online*, dan Parquet/DuckDB untuk pelatihan *offline*.
3. **Serving SLA:**
   - P99 Latency $\le$ 35ms pada throughput minimum 2.500 request per detik (RPS).
   - Deployment containerized via Triton Inference Server dengan fitur *dynamic batching*.
4. **Reliability & Observability:**
   - Pelacakan metrik *Population Stability Index* (PSI) pada setiap jendela transaksi 1 jam.
   - Pemicu otomatis *retraining pipeline* melalui webhook Apache Airflow/Prefect ketika PSI melewati ambang batas $> 0.2$.
   - Sistem explainability real-time menggunakan TreeSHAP yang di-cache untuk memunculkan alasan penolakan transaksi pada dashboard admin internal.

### Kriteria Kelulusan Proyek
- Repositori kode bersih dengan *type hints*, test coverage $> 85\%$, dan file konfigurasi reproduktifitas penuh (`conda`/`poetry`, `Dockerfile`, `dvc.lock`).
- Laporan validasi teknis mencakup evaluasi *Precision-Recall AUC* (PR-AUC $\ge$ 0.88 pada skenario rasio data minoritas 1:1000) dan kalkulasi analisis biaya bisnis (*cost-matrix evaluation*).