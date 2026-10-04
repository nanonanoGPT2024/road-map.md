# Enterprise Curriculum: AI Data Scientist (`ai-data-scientist`)

> Standar Kurikulum Global Rekayasa Kecerdasan Buatan dan Sains Data Tingkat Enterprise berbasis peta jalan resmi `roadmap.sh: ai-data-scientist`.

---

## 1. Course Overview & Mindset

### Transisi Paradigma: Dari Script Notebook ke Production AI Systems
Banyak praktisi sains data terjebak pada paradigma *notebook-centric*—menjalankan eksperimen *ad-hoc* di Jupyter Notebook, mengoptimalkan metrik akurasi terisolasi pada dataset statis (Kaggle-style), lalu menyerahkan kode kotor kepada tim *engineering* untuk ditulis ulang.

Dalam lanskap komputasi modern, peran **AI Data Scientist** menuntut evolusi struktural:
1. **Mathematical Rigor**: Memahami kalkulus multivariat, aljabar linier numerik, optimasi non-konveks, dan inferensi probabilistik secara mekanistik, bukan sekadar memanggil API `model.fit()`.
2. **Software & Data Engineering Excellence**: Menulis kode Python performa tinggi (asinkron, berorientasi objek, *type-hinted*, teruji unit), memahami partisi data terdistribusi (*distributed compute primitives*), serta merancang arsitektur data *low-latency*.
3. **Dual Competency (Classical ML + Modern Generative AI)**: Menguasai algoritma deterministik, *tree-based ensembles*, pemodelan kausal, representasi mendalam (*deep representation learning*), serta arsitektur berbasis Transformer (LLM, Vision-Language Models, Agentic Workflows).
4. **Production Lifecycle Responsibility (MLOps & LLMOps)**: Bertanggung jawab atas siklus hidup model sejak data mentah, rekayasa fitur (*feature store*), pelatihan terdistribusi, kuantisasi, penyajian (*serving*), hingga *continuous monitoring* (mendeteksi *data drift*, *concept drift*, dan degradasi latensi).

```
   TRADITIONAL DATA SCIENTIST                  PRODUCTION AI DATA SCIENTIST
┌───────────────────────────────┐           ┌─────────────────────────────────────────┐
│ • Ad-hoc Jupyter Notebooks    │           │ • Modular, Tested, Type-safe Codebases │
│ • Static CSV Datasets         │  ───────► │ • Streaming & Distributed Ingestion     │
│ • Optimizing only for F1/MSE  │           │ • Optimizing for Latency, Cost, & Value │
│ • "Throw over the wall to ops"│           │ • End-to-end MLOps/LLMOps Ownership     │
└───────────────────────────────┘           └─────────────────────────────────────────┘
```

### Core Enterprise Technology Stack
* **Language & Runtime:** Python 3.11+, C++/Rust bindings (dasar eksekusi modul), CUDA / Triton.
* **Data Processing & Analytics:** Polars, DuckDB, Apache Spark / PySpark, Delta Lake.
* **Mathematical & Statistical Core:** NumPy, SciPy, Statsmodels, JAX.
* **Classical Machine Learning:** Scikit-Learn, LightGBM, XGBoost, CatBoost, Optuna.
* **Deep Learning Frameworks:** PyTorch 2.x, PyTorch Lightning, Hugging Face (Transformers, PEFT, TRL, Accelerate).
* **Vector Databases & GenAI Stack:** Qdrant / Milvus, LlamaIndex, LangGraph, vLLM, DeepSpeed.
* **Operational Infrastructure (MLOps):** MLflow, Feast (Feature Store), Triton Inference Server, Docker, Kubernetes, Prometheus, Evidently AI.

---

## 2. Learning Roadmap

```
AI Data Scientist Curriculum
│
├── 01. Advanced Mathematical Foundations & Optimization
│   ├── Linear Algebra & Matrix Decompositions
│   ├── Multivariate Calculus & Vector Gradients
│   └── Numerical Optimization & Probabilistic Inference
│
├── 02. Modern Data Engineering & Distributed Analytics
│   ├── High-Performance Dataframes (Polars/DuckDB)
│   ├── Distributed Computing with PySpark & Ray
│   └── Modern Streaming Ingestion & Lakehouse Architecture
│
├── 03. Exploratory Data Analysis & Feature Engineering
│   ├── Advanced Exploratory Data Analysis (EDA) & Diagnostics
│   ├── Production Feature Engineering & Scaling
│   └── Feature Store Architecture & Real-Time Transformation
│
├── 04. Classical & Modern Machine Learning Systems
│   ├── Supervised Learning & Generalized Additive Models
│   ├── Tree-Based Ensembles & Gradient Boosting Rigor
│   └── Unsupervised Learning, Clustering & Dimensionality Reduction
│
├── 05. Deep Learning Architectures & Representation Learning
│   ├── Deep Neural Network Foundations & Backpropagation
│   ├── Convolutional & Recurrent Computation Engines
│   └── Transformer Mechanics & Self-Attention Implementation
│
├── 06. Natural Language Processing & Large Language Models
│   ├── Tokenization, Embeddings, & Semantic Search
│   ├── Fine-Tuning Paradigms (Full, PEFT, LoRA, QLoRA)
│   └── Enterprise Retrieval-Augmented Generation (RAG) Systems
│
├── 07. Computer Vision & Multimodal Intelligence
│   ├── Modern Vision Transformers (ViT) & Object Detection
│   ├── Contrastive Multimodal Learning (CLIP, BLIP)
│   └── Vision-Language Models (VLM) for Structured Extraction
│
├── 08. Model Evaluation, Explainability (XAI) & Alignment
│   ├── Validation Strategies & Statistical Hypothesis Testing
│   ├── Explainable AI (SHAP, LIME, Integrated Gradients)
│   └── Guardrails, Red Teaming, & Algorithmic Fairness
│
├── 09. MLOps, LLMOps, & Production Model Serving
│   ├── Model Packaging, Quantization, & Compilation (ONNX/TensorRT)
│   ├── High-Throughput Inference Engines (vLLM, Triton)
│   └── CI/CD Pipelines, Experiment Tracking, & Drift Monitoring
│
├── 10. Advanced AI Paradigms: Autonomous Agents & RL
│   ├── Reinforcement Learning from Human Feedback (RLHF/DPO)
│   ├── Autonomous Agent Architecture & Tool Use
│   └── Graph Neural Networks (GNN) for Connected Intelligence
│
└── Capstone Project: Enterprise Real-Time Multimodal Intelligence Engine
```

---

## 3. Navigasi Detail Bab (01 s/d 10)

### Bab 01: Advanced Mathematical Foundations & Optimization
*Fondasi matematika analitis dan komputasi numerik yang mendasari algoritma inferensi cerdas.*
* **Target Kompetensi:** Menguasai faktorisasi matriks tingkat lanjut, turunan matriks multivariat (*Jacobian/Hessian*), serta implementasi algoritma optimasi dari nol menggunakan tensor murni.
* **Modul:**
  * [`./01-mathematical-foundations/01-linear-algebra-matrix-decompositions.md`](./01-mathematical-foundations/01-linear-algebra-matrix-decompositions.md): Eigendecomposition, Singular Value Decomposition (SVD), Principal Components, Matrix Inversion & Pseudo-inverse via SVD.
  * [`./01-mathematical-foundations/02-multivariate-calculus-vector-gradients.md`](./01-mathematical-foundations/02-multivariate-calculus-vector-gradients.md): Vector-Jacobian Products (VJP), Jacobian-Vector Products (JVP), Hessian Matrices, Automatic Differentiation (Autograd internals).
  * [`./01-mathematical-foundations/03-numerical-optimization-probabilistic-inference.md`](./01-mathematical-foundations/03-numerical-optimization-probabilistic-inference.md): Convex Optimization, Gradient Descent Variants (AdamW, RMSprop), Maximum Likelihood Estimation (MLE), Maximum A Posteriori (MAP), Bayesian Formulations.

### Bab 02: Modern Data Engineering & Distributed Analytics
*Pengolahan data skala *terabyte* dengan latensi rendah tanpa degradasi memori.*
* **Target Kompetensi:** Menggantikan pipeline *in-memory* Pandas tradisional dengan mesin analitik berbasis Rust/Arrow (Polars/DuckDB) dan komputasi kluster terdistribusi (Spark/Ray).
* **Modul:**
  * [`./02-data-engineering-analytics/01-high-performance-arrow-engines.md`](./02-data-engineering-analytics/01-high-performance-arrow-engines.md): Apache Arrow Memory Layout, Lazy Execution Pipelines dengan Polars, Zero-Copy Ingestion menggunakan DuckDB.
  * [`./02-data-engineering-analytics/02-distributed-computing-spark-ray.md`](./02-data-engineering-analytics/02-distributed-computing-spark-ray.md): PySpark DataFrame Optimization (Catalyst Optimizer, Tungsten), Adaptive Query Execution, Ray Core & Ray Datasets untuk beban kerja AI paralel.
  * [`./02-data-engineering-analytics/03-streaming-lakehouse-foundations.md`](./02-data-engineering-analytics/03-streaming-lakehouse-foundations.md): Lakehouse Formats (Delta Lake / Parquet), CDC (Change Data Capture), Event Ingestion dengan Kafka/Redpanda, Event-Time Windowing.

### Bab 03: Exploratory Data Analysis & Production Feature Engineering
*Transformasi data mentah heterogen menjadi representasi fitur bernilai informasi tinggi yang tahan uji masa pakai.*
* **Target Kompetensi:** Merancang pipeline rekayasa fitur deterministik, mengisolasi kebocoran data (*data leakage*), dan mengintegrasikan repositori fitur sentral (*feature store*).
* **Modul:**
  * [`./03-eda-feature-engineering/01-statistical-diagnostics-data-profiling.md`](./03-eda-feature-engineering/01-statistical-diagnostics-data-profiling.md): Kolom-ke-kolom Dependency Mapping, Identifikasi Outlier Multivariat (Isolation Forests, Mahalanobis Distance), Analisis Imputasi Stokastik.
  * [`./03-eda-feature-engineering/02-production-transformations-scaling.md`](./03-eda-feature-engineering/02-production-transformations-scaling.md): Target Encoding Bebas Leakage (Out-of-Fold), K-Bins Discretization, Embeddings Fitur Kategorikal, Penskalaan Robus, Siklus Hidup Imputasi.
  * [`./03-eda-feature-engineering/03-feature-store-architecture-feast.md`](./03-eda-feature-engineering/03-feature-store-architecture-feast.md): Arsitektur Online/Offline Feature Store menggunakan Feast, Point-in-time Correctness (*Time-travel queries*), Sinkronisasi Fitur Real-Time Redis/Parquet.

### Bab 04: Classical & Modern Machine Learning Systems
*Rekayasa algoritma prediktif tabular performa tinggi dengan fokus pada reliabilitas matematis dan batas generalisasi.*
* **Target Kompetensi:** Membangun *pipeline* klasifikasi dan regresi modular kelas enterprise berbasis *gradient boosted decision trees* (GBDT) dan model linier teratur.
* **Modul:**
  * [`./04-machine-learning-systems/01-regularized-generalized-linear-models.md`](./04-machine-learning-systems/01-regularized-generalized-linear-models.md): Generalized Linear Models (GLM), Regularisasi L1/L2/ElasticNet, Kalibrasi Probabilitas (Platt Scaling, Isotonic Regression), ROC-PR Curves Trade-off.
  * [`./04-machine-learning-systems/02-gradient-boosting-ensemble-rigor.md`](./04-machine-learning-systems/02-gradient-boosting-ensemble-rigor.md): Mekanika Internal LightGBM vs. XGBoost vs. CatBoost, Histogram-based Splitting, Custom Loss Functions, Optimasi Hyperparameter Bayesian via Optuna.
  * [`./04-machine-learning-systems/03-unsupervised-clustering-dimensionality-reduction.md`](./04-machine-learning-systems/03-unsupervised-clustering-dimensionality-reduction.md): UMAP, t-SNE Internals, HDBSCAN Density-based Clustering, Mixture Models, Deteksi Anomali Tanpa Supervisi.

### Bab 05: Deep Learning Architectures & Representation Learning
*Konstruksi arsitektur jaringan saraf mendalam secara modular menggunakan PyTorch murni.*
* **Target Kompetensi:** Memahami *computational graph*, menulis *custom autograd functions*, merancang layer konvolusional dan blok *self-attention* dari level tensor terendah.
* **Modul:**
  * [`./05-deep-learning-representation/01-pytorch-foundations-tensor-mechanics.md`](./05-deep-learning-representation/01-pytorch-foundations-tensor-mechanics.md): Dynamic Computational Graphs, PyTorch nn.Module, Custom Autograd Functions, Mixed-Precision (AMP) Training, Memory Profiling (CUDA VRAM).
  * [`./05-deep-learning-representation/02-spatial-sequential-architectures.md`](./05-deep-learning-representation/02-spatial-sequential-architectures.md): ResNet Residual Blocks, ConvNeXt, Bidirectional LSTMs, Temporal Convolutional Networks (TCN) untuk Analisis Data Deret Waktu.
  * [`./05-deep-learning-representation/03-transformer-mechanics-from-scratch.md`](./05-deep-learning-representation/03-transformer-mechanics-from-scratch.md): Scaled Dot-Product Attention, Multi-Head Attention, Rotary Positional Embedding (RoPE), LayerNorm vs. RMSNorm, KV-Cache Optimization.

### Bab 06: Natural Language Processing & Large Language Models (LLMs)
*Implementasi model bahasa tingkat lanjut: dari representasi semantik hingga orkestrasi Retrieval-Augmented Generation (RAG).*
* **Target Kompetensi:** Mampu melakukan penyesuaian bobot LLM secara efisien parameter (LoRA/QLoRA) dan membangun mesin pencarian semantik perusahaan dengan *reranking*.
* **Modul:**
  * [`./06-nlp-large-language-models/01-tokenization-embeddings-vector-spaces.md`](./06-nlp-large-language-models/01-tokenization-embeddings-vector-spaces.md): Byte-Pair Encoding (BPE), SentencePiece, Dense Embeddings, Hierarchical Indexing (HNSW, IVF-PQ) pada Qdrant/Milvus.
  * [`./06-nlp-large-language-models/02-peft-lora-qlora-finetuning.md`](./06-nlp-large-language-models/02-peft-lora-qlora-finetuning.md): Parameter-Efficient Fine-Tuning (PEFT), Low-Rank Adaptation (LoRA), Kuantisasi 4-bit NF4 (QLoRA), SFT Trainer dengan Unsloth/Hugging Face Accelerate.
  * [`./06-nlp-large-language-models/03-production-rag-systems.md`](./06-nlp-large-language-models/03-production-rag-systems.md): Hybrid Search (BM25 + Dense), Cross-Encoder Reranking, Contextual Compression, Evaluation Framework (Ragas / TruLens), Guarding Halusinasi.

### Bab 07: Computer Vision & Multimodal Intelligence
*Sistem pemrosesan citra digital, segmentasi, deteksi objek, dan integrasi lintas modalitas (teks-gambar).*
* **Target Kompetensi:** Menerapkan Vision Transformer (ViT) kontemporer dan Vision-Language Models (VLM) untuk ekstraksi informasi visual dokumen tak terstruktur.
* **Modul:**
  * [`./07-computer-vision-multimodal/01-vision-transformers-object-detection.md`](./07-computer-vision-multimodal/01-vision-transformers-object-detection.md): Patch Extraction & Linear Projection pada ViT, Real-Time Object Detection (YOLOv9/YOLOv10), Instance Segmentation dengan Mask R-CNN.
  * [`./07-computer-vision-multimodal/02-contrastive-multimodal-representations.md`](./07-computer-vision-multimodal/02-contrastive-multimodal-representations.md): Zero-Shot Classification menggunakan CLIP, Contrastive Loss Formulations, Joint Visual-Textual Embeddings.
  * [`./07-computer-vision-multimodal/03-vision-language-models-vlm.md`](./07-computer-vision-multimodal/03-vision-language-models-vlm.md): Arsitektur LLaVA/PaliGemma, Vision Encoder ke Language Decoder Projections, Document Visual Question Answering (DocVQA) untuk Dokumen Legal/Keuangan.

### Bab 08: AI System Evaluation, Explainability (XAI) & Fairness
*Metodologi audit performa, akuntabilitas keputusan sistem, interpretasi model kotak hitam, dan mitigasi bias sistemik.*
* **Target Kompetensi:** Merancang kerangka evaluasi empiris terbebas dari *leakage*, mengekstrak nilai atribusi fitur, serta melakukan audit keadilan (*fairness audit*).
* **Modul:**
  * [`./08-model-evaluation-xai-fairness/01-rigorous-validation-uncertainty.md`](./08-model-evaluation-xai-fairness/01-rigorous-validation-uncertainty.md): Purged Cross-Validation untuk Time-Series, Conformal Prediction untuk Kuantifikasi Ketidakpastian (*Prediction Sets*), Bootstrap Hypothesis Testing.
  * [`./08-model-evaluation-xai-fairness/02-explainable-ai-interpretability.md`](./08-model-evaluation-xai-fairness/02-explainable-ai-interpretability.md): Game-Theoretic Attributions (KernelSHAP, TreeSHAP), Integrated Gradients untuk Jaringan Saraf, LIME Local Approximations.
  * [`./08-model-evaluation-xai-fairness/03-algorithmic-fairness-red-teaming.md`](./08-model-evaluation-xai-fairness/03-algorithmic-fairness-red-teaming.md): Disparate Impact Ratio, Equalized Odds, Demographic Parity, Adversarial Perturbation Attacks, Red Teaming LLM Prompts.

### Bab 09: MLOps, LLMOps, & Production Model Serving
*Infrastruktur operasionalisasi model dari eksperimen riset menuju kluster produksi terdistribusi.*
* **Target Kompetensi:** Mengkompilasi artefak model ke dalam mesin komputasi teroptimasi (TensorRT/ONNX), mengoperasikan mesin inferensi konkurensi tinggi, dan memantau pergeseran data secara *real-time*.
* **Modul:**
  * [`./09-mlops-llmops-serving/01-compilation-quantization-packaging.md`](./09-mlops-llmops-serving/01-compilation-quantization-packaging.md): Open Neural Network Exchange (ONNX) Runtime, TensorRT Acceleration, Post-Training Quantization (INT8, FP8), Weight-Only Quantization (AWQ/GPTQ).
  * [`./09-mlops-llmops-serving/02-high-throughput-model-serving.md`](./09-mlops-llmops-serving/02-high-throughput-model-serving.md): Triton Inference Server Multi-Model Pipelines, Dynamic Batching, vLLM Engine Deployment (PagedAttention, Continuous Batching), Desain API gRPC & FastAPI.
  * [`./09-mlops-llmops-serving/03-observability-drift-monitoring-cicd.md`](./09-mlops-llmops-serving/03-observability-drift-monitoring-cicd.md): Pipeline CI/CD Model berbasis GitHub Actions & CML, Continuous Monitoring dengan Evidently AI & Prometheus (Data Drift, Concept Drift), Automated Retraining Triggers.

### Bab 10: Advanced AI Paradigms: Autonomous Agents & RL
*Batas kemampuan AI modern: optimalisasi kebijakan adaptif (*Reinforcement Learning*), agen otonom multifungsi, dan jaringan graf.*
* **Target Kompetensi:** Memahami *reinforcement learning from feedback* (RLHF/DPO), mendesain agen otonom dengan penalaran ReAct berbasis graf, serta mengimplementasikan Graph Neural Networks (GNN).
* **Modul:**
  * [`./10-advanced-ai-paradigms/01-rlhf-direct-preference-optimization.md`](./10-advanced-ai-paradigms/01-rlhf-direct-preference-optimization.md): Reward Modeling, Proximal Policy Optimization (PPO), Direct Preference Optimization (DPO), KTO (Kahneman-Tversky Optimization).
  * [`./10-advanced-ai-paradigms/02-autonomous-multi-agent-systems.md`](./10-advanced-ai-paradigms/02-autonomous-multi-agent-systems.md): Arsitektur Perencanaan ReAct & Reflexion, Tool Calling & Structured Outputs, Multi-Agent Collaboration via LangGraph.
  * [`./10-advanced-ai-paradigms/03-graph-neural-networks-connected-data.md`](./10-advanced-ai-paradigms/03-graph-neural-networks-connected-data.md): Message Passing Networks, Graph Convolutional Networks (GCN), Graph Attention Networks (GAT) menggunakan PyTorch Geometric untuk Deteksi Sindikat Penipuan.

---

## 4. Enterprise Capstone Project Specification

### Judul Proyek
**"OmniRisk Sentinel: Enterprise Multimodal Fraud & Semantic Anomaly Intelligence Platform"**

```
                            OMNIRISK SENTINEL ARCHITECTURE
  
  [ Real-Time Transactions ]      [ Unstructured Docs (PDFs/Images) ]
              │                                      │
              ▼                                      ▼
     [ Redpanda / Kafka ]                  [ FastAPI File Ingest ]
              │                                      │
              ▼                                      ▼
    [ Polars Streaming ]                  [ VLM / OCR Feature Extractor ]
    (Real-time Aggregation)               (Visual Identity & Layout Embeds)
              │                                      │
              └──────────────┬───────────────────────┘
                             │
                             ▼
               [ Feast Online Feature Store ]
                             │
         ┌───────────────────┴───────────────────┐
         ▼                                       ▼
  [ LightGBM Ensemble ]                  [ Qdrant Vector Store ]
  (Tabular Risk Scoring)                 (Cross-Modal Semantic Search)
         │                                       │
         └───────────────────┬───────────────────┘
                             │
                             ▼
                [ LangGraph Agent Supervisor ]
                 - Cross-evaluates anomalies
                 - Synthesizes risk reports via LLM (vLLM)
                 - Generates SHAP explanation payloads
                             │
                             ▼
              [ Triton Inference Cluster / Dashboard ]
              - Prometheus Metrics & Evidently AI Drift Watch
```

### Problem Statement
Institusi finansial global menghadapi kerugian miliaran dolar akibat kejahatan terorganisir yang memadukan manipulasi data tabular (transaksi cepat bernilai kecil), pemalsuan identitas visual (KTP/Paspor teranomali), dan dokumen legalitas fiktif. Model *single-modality* tradisional gagal menangkap pola sindikat kejahatan yang terkoordinasi ini. Proyek ini menuntut perancangan sistem intelijen risiko terintegrasi yang mampu mendeteksi kecurangan secara multimodal dalam waktu sub-detik serta memproduksi laporan audit kepatuhan terotentikasi.

### Arsitektur & Spesifikasi Rekayasa
1. **Ingestion & Streaming Fabric:**
   * Pipeline *streaming* transaksi sintetis frekuensi tinggi menggunakan Kafka/Redpanda yang diproses oleh *consumer engine* berbasis Polars streaming.
   * *Dead-letter queue* terotomasi, skema kontrak menggunakan Protocol Buffers / Avro.
2. **Dual-Model Inference Engine:**
   * **Tabular Branch**: Klasifikasi anomali transaksi real-time menggunakan LightGBM yang dioptimalkan dengan kustom *focal-loss* untuk mengatasi *extreme class imbalance* (99.9% non-fraud vs. 0.1% fraud). Fitur ditarik langsung dari Feast Feature Store (Redis backend).
   * **Multimodal Branch**: Dokumen pendukung (PDF/PNG) diproses melalui Vision-Language Model (VLM) terkuantisasi (AWQ 4-bit) pada mesin vLLM untuk mengekstraksi representasi semantik dan memvalidasi keaslian dokumen visual.
3. **Graph Syndication Engine:**
   * PyTorch Geometric (GAT - Graph Attention Network) untuk mendeteksi *money mule rings* berdasarkan relasi rekening-perangkat-alamat.
4. **Agentic Explanation & Human-in-the-Loop:**
   * Orkestrasi agen menggunakan LangGraph: jika skor risiko gabungan berada dalam rentang *uncertainty* (Conformal Prediction interval), agen mengaktifkan *tool-use* untuk mengumpulkan bukti forensik, menghitung kontribusi atribusi SHAP, dan menghasilkan berkas ringkasan eksekutif (*LLM-generated explanation*).
5. **Production Reliability & SLOs:**
   * Latensi inferensi akhir: $\le 150\text{ ms}$ untuk evaluasi tabular (P99); $\le 1.2\text{ s}$ untuk evaluasi multimodal penuh.
   * Model disajikan via Triton Inference Server dengan *dynamic batching*.
   * Pemantauan pergeseran data (*Wasserstein distance* & *PSI*) menggunakan Evidently AI yang terintegrasi dengan alert Prometheus/Grafana.

### Deliverables & Standar Penilaian
* **Repositori Modular**: Kode produksi standar PEP 8, *type annotations* (`mypy` compliant), pengujian unit dan integrasi (`pytest`) dengan *code coverage* minimal 80%.
* **Artifacts & Pipelines**: Skrip pelatihan otomatis yang dapat direproduksi (*reproducible training pipelines*), konfigurasi Dockerfile *multi-stage build*, manifest Kubernetes, dan diagram arsitektur teknis lengkap.
* **Auditability**: Laporan evaluasi komprehensif mencakup ROC-AUC, PR-AUC, metrik *fairness* lintas demografi, *latency benchmarking under concurrency load*, dan interpretasi *sample-level* SHAP.