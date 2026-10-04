# Kurikulum Enterprise MLOps Engineering

> Kurikulum komprehensif 10 Bab berstandar industri untuk membangun, mengotomatisasi, mengamankan, dan mengoperasikan platform Machine Learning skala produksi secara andal dan *reproducible*.

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
Machine Learning dalam ranah akademis dan *proof-of-concept* (PoC) berfokus pada metrik model statis seperti akurasi, F1-score, dan ROC-AUC pada dataset yang terisolasi. Sebaliknya, **Enterprise MLOps (Machine Learning Operations)** berakar pada realitas sistem produksi: kode model ML hanya mencakup sekitar 5% dari total ekosistem perangkat lunak produksi (merujuk pada *Hidden Technical Debt in Machine Learning Systems*, Google). Sisanya adalah infrastruktur orkestrasi, rekayasa data, *data validation*, *model governance*, *continuous delivery*, serta mitigasi *data drift* dan *concept drift*.

Kurikulum ini mengadopsi standar kompetensi dari platform resmi **roadmap.sh/mlops** dengan penekanan pada:
1. **Reproducibility First**: Tidak ada model yang layak dikirim ke *production* tanpa jejak audit (*lineage*) deterministik atas kode, data, konfigurasi, dan *environment runtime*.
2. **Shift-Left Testing for ML**: Pengujian tidak hanya berlaku untuk *unit test software*, tetapi meluas ke validasi skema data, pengujian integritas fitur, *bias/fairness testing*, dan evaluasi degradasi model sebelum masuk ke *registry*.
3. **Continuous Training & Zero-Downtime Serving**: Memisahkan siklus hidup *pipeline training* dari *pipeline serving*, menerapkan pola *shadow*, *canary*, atau *blue-green deployment*, dan mengotomatisasi *feedback loop* dengan *quality gates* yang ketat.
4. **Resiliency & FinOps**: Mengelola utilisasi akselerator (GPU/TPU), arsitektur *inference auto-scaling*, serta proteksi biaya komputasi *cloud* tanpa mengorbankan Service Level Objectives (SLO).

---

## 2. Learning Roadmap

```plaintext
========================================================================================
                              MLOPS ENGINEERING ROADMAP
========================================================================================
[BAB 01: Fondasi MLOps, Data Versioning & Reproducibility]
   │  ├── Modul 01: Data Version Control (DVC) & S3-Compatible Remote Storage
   │  ├── Modul 02: Deterministic Environment Packaging (Docker & Poetry/Conda)
   │  └── Modul 03: Data & Artifact Lineage Management
   ▼
[BAB 02: Modular Pipeline & Experiment Tracking]
   │  ├── Modul 01: Framework Abstraksi Pipeline (Kedro & Hydra)
   │  ├── Modul 02: Experiment Tracking & Hyperparameter Logging (MLflow)
   │  └── Modul 03: Model Registry Architecture & Artifact Tagging
   ▼
[BAB 03: Feature Store Architecture & Real-Time Ingestion]
   │  ├── Modul 01: Offline vs. Online Feature Store Core Concepts (Feast)
   │  ├── Modul 02: Point-in-Time Correctness & Preventing Data Leakage
   │  └── Modul 03: Streaming Feature Ingestion (Kafka/Redis)
   ▼
[BAB 04: Data Validation, Continuous Testing, & Quality Gates]
   │  ├── Modul 01: Data Contract & Schema Validation (Great Expectations)
   │  ├── Modul 02: Pytest Suite for ML: Invariance, Directional & Leakage Tests
   │  └── Modul 03: Model Behavioral & Robustness Testing (Deepchecks)
   ▼
[BAB 05: Pipeline Orchestration & Distributed Training]
   │  ├── Modul 01: Workflow Orchestration (Kubeflow Pipelines / Apache Airflow)
   │  ├── Modul 02: Distributed Data & Model Parallelism (Ray Train & DDP)
   │  └── Modul 03: Managed Training Jobs & Spot Instance Fault-Tolerance
   ▼
[BAB 06: Model Optimization, Packaging, & Containerization]
   │  ├── Modul 01: Graph Optimization & Serialization (ONNX & TensorRT)
   │  ├── Modul 02: Model Quantization (INT8/FP16) & Pruning Strategies
   │  └── Modul 03: Multi-Stage Production Containers & Triton Inference Server
   ▼
[BAB 07: High-Throughput Model Serving & Deployment Patterns]
   │  ├── Modul 01: Low-Latency Inference Engines (FastAPI, BentoML, vLLM)
   │  ├── Modul 02: Advanced Rollouts (Canary, Blue/Green, Shadow Deployment)
   │  └── Modul 03: Cloud-Native Autoscaling & KServe on Kubernetes
   ▼
[BAB 08: CI/CD/CT Automation for Machine Learning]
   │  ├── Modul 01: GitHub Actions / GitLab CI Pipelines for Model Life-Cycle
   │  ├── Modul 02: GitOps Automation for ML Deployments via ArgoCD
   │  └── Modul 03: Continuous Training (CT) Triggers & Retraining Feedback Loops
   ▼
[BAB 09: Observability, Drift Detection, & Model Governance]
   │  ├── Modul 01: Metric Collection & Alerting (Prometheus & Grafana for ML)
   │  ├── Modul 02: Data Drift & Concept Drift Detection (Evidently AI & WhyLogs)
   │  └── Modul 03: Model Governance, Audit Logs, & Explainability (SHAP/Captum)
   ▼
[BAB 10: Enterprise Scalability, Security, & FinOps]
   │  ├── Modul 01: Model Security: Adversarial Defense, PII Scrubbing, & Model Signing
   │  ├── Modul 02: Cloud FinOps & GPU Slicing Optimization (MIG & Spot Orchestration)
   │  └── Modul 03: Multi-Tenant Architecture & End-to-End Production Compliance
========================================================================================
```

---

## 3. Navigasi Detail Bab 01 s/d Bab 10

### [BAB 01: Fondasi MLOps, Data Versioning & Reproducibility](./bab-01-fondasi-mlops-dan-versioning/README.md)
Membangun fondasi manajemen artefak data bervolume besar, memastikan determinisme *environment*, dan melacak perubahan data secara granular tanpa mengotori repositori Git.
* [Modul 01: Data Version Control (DVC) & S3-Compatible Remote Storage](./bab-01-fondasi-mlops-dan-versioning/modul-01-dvc-dan-s3.md) — Mengonfigurasi DVC dengan *backend storage* (AWS S3/MinIO), manajemen *pointer files* `.dvc`, dan *push/pull data pipelines*.
* [Modul 02: Deterministic Environment Packaging (Docker & Poetry/Conda)](./bab-01-fondasi-mlops-dan-versioning/modul-02-deterministic-packaging.md) — Menjamin paritas dependensi komputasi melalui *lockfiles*, isolasi CUDA *driver*, dan multi-platform Docker builds.
* [Modul 03: Data & Artifact Lineage Management](./bab-01-fondasi-mlops-dan-versioning/modul-03-lineage-management.md) — Memetakan silsilah ketergantungan antara raw data, pemrosesan fitur, model bobot, dan metadata audit trail.

### [BAB 02: Modular Pipeline & Experiment Tracking](./bab-02-modular-pipeline-dan-tracking/README.md)
Mengubah skrip eksplorasi Notebook yang berantakan menjadi arsitektur kode modular standar industri yang terintegrasi dengan pelacakan metrik real-time.
* [Modul 01: Framework Abstraksi Pipeline (Kedro & Hydra)](./bab-02-modular-pipeline-dan-tracking/modul-01-kedro-dan-hydra.md) — Menulis arsitektur *node* dan *pipeline* decoupled serta manajemen konfigurasi hierarkis berbasis YAML.
* [Modul 02: Experiment Tracking & Hyperparameter Logging (MLflow)](./bab-02-modular-pipeline-dan-tracking/modul-02-mlflow-tracking.md) — Instrumentasi kode pelatihan untuk mencatat metrik dinamis, kurva loss, *hyperparameter artifacts*, dan visualisasi performa.
* [Modul 03: Model Registry Architecture & Artifact Tagging](./bab-02-modular-pipeline-dan-tracking/modul-03-model-registry.md) — Manajemen *staging lifecycle* (`Staging`, `Production`, `Archived`), skema versi semantik model, dan metadata *signature*.

### [BAB 03: Feature Store Architecture & Real-Time Ingestion](./bab-03-feature-store-architecture/README.md)
Mengeliminasi *feature inconsistency* dan duplikasi pemrosesan data antara tahap pelatihan *offline* dan inferensi *online*.
* [Modul 01: Offline vs. Online Feature Store Core Concepts (Feast)](./bab-03-feature-store-architecture/modul-01-feast-core.md) — Arsitektur dual-storage: sinkronisasi batch layer (Parquet/Snowflake) dan fast-access layer (Redis/DynamoDB).
* [Modul 02: Point-in-Time Correctness & Preventing Data Leakage](./bab-03-feature-store-architecture/modul-02-point-in-time-correctness.md) — Implementasi algoritma *AS-OF joins* untuk memastikan kalkulasi fitur historis terisolasi dari *future data*.
* [Modul 03: Streaming Feature Ingestion (Kafka/Redis)](./bab-03-feature-store-architecture/modul-03-streaming-feature-ingestion.md) — Transformasi fitur real-time dan mekanisme *push* streaming dengan latensi sub-detik menuju *online store*.

### [BAB 04: Data Validation, Continuous Testing, & Quality Gates](./bab-04-data-validation-dan-testing/README.md)
Menerapkan disiplin pengujian *shift-left* pada data dan perilaku model sebelum *code* atau *artifact* dipromosikan ke tahap komputasi lebih lanjut.
* [Modul 01: Data Contract & Schema Validation (Great Expectations)](./bab-04-data-validation-dan-testing/modul-01-great-expectations.md) — Deklarasi kontrak data terotomatisasi, profiling distribusi kolom, dan blokade *pipeline* saat anomali skema terdeteksi.
* [Modul 02: Pytest Suite for ML: Invariance, Directional & Leakage Tests](./bab-04-data-validation-dan-testing/modul-02-ml-pytest-suites.md) — Mengembangkan *behavioral test suite*: uji invariansi input, *minimum functionality tests*, dan proteksi *label leakage*.
* [Modul 03: Model Behavioral & Robustness Testing (Deepchecks)](./bab-04-data-validation-dan-testing/modul-03-deepchecks-robustness.md) — Audit integritas komprehensif atas performa lintas sub-populasi, data imbalance, dan deteksi *spurious correlations*.

### [BAB 05: Pipeline Orchestration & Distributed Training](./bab-05-orchestration-dan-distributed-training/README.md)
Mengorkestrasi beban kerja DAG (*Directed Acyclic Graph*) skala besar dan mendistribusikan komputasi pelatihan model pada kluster multi-node.
* [Modul 01: Workflow Orchestration (Kubeflow Pipelines / Apache Airflow)](./bab-05-orchestration-dan-distributed-training/modul-01-kubeflow-airflow.md) — Membangun, menjadwalkan, dan memantau DAG modular berbasis container pada infrastruktur Kubernetes.
* [Modul 02: Distributed Data & Model Parallelism (Ray Train & DDP)](./bab-05-orchestration-dan-distributed-training/modul-02-distributed-training-ray.md) — Strategi pelatihan terdistribusi menggunakan PyTorch Distributed Data Parallel (DDP) dan Ray Core/Train engine.
* [Modul 03: Managed Training Jobs & Spot Instance Fault-Tolerance](./bab-05-orchestration-dan-distributed-training/modul-03-spot-instance-tolerance.md) — Penanganan interupsi mesin *cloud spot*, implementasi *checkpointing* elastis, dan strategi *auto-recovery*.

### [BAB 06: Model Optimization, Packaging, & Containerization](./bab-06-model-optimization-dan-packaging/README.md)
Mengonversi model mentah dari framework riset ke format inferensi performa tinggi dengan konsumsi memori dan latensi minimal.
* [Modul 01: Graph Optimization & Serialization (ONNX & TensorRT)](./bab-06-model-optimization-dan-packaging/modul-01-onnx-tensorrt.md) — Fusi layer, *graph pruning*, kompilasi kernel GPU, dan standardisasi runtime multi-framework.
* [Modul 02: Model Quantization (INT8/FP16) & Pruning Strategies](./bab-06-model-optimization-dan-packaging/modul-02-quantization-pruning.md) — Post-Training Quantization (PTQ), Quantization-Aware Training (QAT), dan verifikasi deviasi akurasi model.
* [Modul 03: Multi-Stage Production Containers & Triton Inference Server](./bab-06-model-optimization-dan-packaging/modul-03-triton-containerization.md) — Merancang Docker image ramping dengan Triton Inference Server untuk mendukung *dynamic batching* dan *concurrent model execution*.

### [BAB 07: High-Throughput Model Serving & Deployment Patterns](./bab-07-model-serving-dan-deployment/README.md)
Menyajikan model sebagai layanan jaringan mikro (*microservices*) dengan SLA ketat, *throughput* tinggi, dan strategi rilis nir-henti.
* [Modul 01: Low-Latency Inference Engines (FastAPI, BentoML, vLLM)](./bab-07-model-serving-dan-deployment/modul-01-inference-engines.md) — Pola *serving synchronous/asynchronous*, optimasi *worker process*, dan *streaming responses* untuk model generatif/diskriminatif.
* [Modul 02: Advanced Rollouts (Canary, Blue/Green, Shadow Deployment)](./bab-07-model-serving-dan-deployment/modul-02-advanced-rollouts.md) — Rekayasa perutean lalu lintas jaringan (*traffic split*) untuk memvalidasi model baru terhadap data produksi tanpa risiko *downtime*.
* [Modul 03: Cloud-Native Autoscaling & KServe on Kubernetes](./bab-07-model-serving-dan-deployment/modul-03-kserve-autoscaling.md) — Konfigurasi serverless inferensi dengan KServe, Knative, dan HPA (*Horizontal Pod Autoscaler*) berbasis latensi atau GPU duty-cycle.

### [BAB 08: CI/CD/CT Automation for Machine Learning](./bab-08-cicd-dan-ct-automation/README.md)
Menggabungkan DevOps konvensional dengan *Continuous Training* untuk merealisasikan siklus rilis dan retraining model yang terautomasi penuh.
* [Modul 01: GitHub Actions / GitLab CI Pipelines for Model Life-Cycle](./bab-08-cicd-dan-ct-automation/modul-01-ci-pipelines.md) — Pipeline validasi kode, linting, eksekusi unit test data, pembuatan artefak kontainer, dan pemicu komputasi eksternal.
* [Modul 02: GitOps Automation for ML Deployments via ArgoCD](./bab-08-cicd-dan-ct-automation/modul-02-gitops-argocd.md) — Deklaratif infrastruktur kluster ML, sinkronisasi state aplikasi inferensi, dan kapabilitas *automated rollback*.
* [Modul 03: Continuous Training (CT) Triggers & Retraining Feedback Loops](./bab-08-cicd-dan-ct-automation/modul-03-continuous-training-ct.md) — Mekanisme pemicu *retraining* berbasis *schedule*, *threshold drift*, atau *volume ingress* data baru dengan batasan proteksi performa (*regression gates*).

### [BAB 09: Observability, Drift Detection, & Model Governance](./bab-09-observability-dan-governance/README.md)
Menjaga transparansi, keandalan, dan kepatuhan sistem ML pasca-implementasi produksi dengan telemetri tingkat lanjut.
* [Modul 01: Metric Collection & Alerting (Prometheus & Grafana for ML)](./bab-09-observability-dan-governance/modul-01-prometheus-grafana.md) — Monitoring *system metrics* (CPU, GPU, RAM, P99 latency) berdampingan dengan *business & statistical metrics* (klasifikasi rasio, inferensi per detik).
* [Modul 02: Data Drift & Concept Drift Detection (Evidently AI & WhyLogs)](./bab-09-observability-dan-governance/modul-02-drift-detection.md) — Menjalankan uji statistik (Kolmogorov-Smirnov, Wasserstein Distance, Population Stability Index) untuk mendeteksi deviasi fitur dan distribusi label.
* [Modul 03: Model Governance, Audit Logs, & Explainability (SHAP/Captum)](./bab-09-observability-dan-governance/modul-03-explainability-governance.md) — Logging inferensi kepatuhan GDPR/regulasi finansial, perhitungan nilai atribusi fitur (SHAP) secara asinkron, dan penelusuran *reproducibility audit*.

### [BAB 10: Enterprise Scalability, Security, & FinOps](./bab-10-scalability-security-dan-finops/README.md)
Mengoptimalkan aspek non-fungsional tingkat lanjut: keamanan artefak dari serangan musuh (*adversarial*), privasi data, dan efisiensi biaya infrastruktur AI.
* [Modul 01: Model Security: Adversarial Defense, PII Scrubbing, & Model Signing](./bab-10-scalability-security-dan-finops/modul-01-model-security.md) — Enkripsi model saat *rest* dan *transit*, mitigasi *data poisoning*, pembersihan PII otomatis, dan penandatanganan kriptografis artefak (*Sigstore/Cosign*).
* [Modul 02: Cloud FinOps & GPU Slicing Optimization (MIG & Spot Orchestration)](./bab-10-scalability-security-dan-finops/modul-02-finops-gpu-slicing.md) — Partisi GPU berbasis Multi-Instance GPU (MIG), *dynamic resource scheduling*, dan pemantauan biaya per-inferensi.
* [Modul 03: Multi-Tenant Architecture & End-to-End Production Compliance](./bab-10-scalability-security-dan-finops/modul-03-enterprise-compliance.md) — Isolasi ruang kerja (RBAC) pada *shared cluster*, kebijakan kuota *namespace*, dan sertifikasi kesiapan operasional (*Production Readiness Review*).

---

## 4. End-to-End Enterprise Capstone Project

### Judul Proyek
**"Real-Time Fraud Prevention & Credit Default Platform with Automated CI/CD/CT, Distributed Training, and Multi-Tier Drift Observability"**

### Arsitektur Sistem Produksi

```plaintext
                                      [Streaming Events]
                                              │ (Kafka)
                                              ▼
[Historical Data (S3)] ──► [Feast Feature Store] ◄── [Streaming Processor]
          │                     │             │
          ▼                     ▼             ▼
   [Data Validation]      [Offline Join]  [Online Store (Redis)]
(Great Expectations)            │             │
          │                     ▼             ▼
          └──────────────► [Ray Train / DDP]  │  ◄── [User Ingestion API]
                                │             │              │
                                ▼             │              ▼
                        [ONNX/TensorRT]       │      [FastAPI / Triton]
                                │             │     (Canary Deployment)
                                ▼             │              │
                      [MLflow Model Registry] │              │
                                │             │              ▼
                        [ArgoCD / GitOps] ────┴──────► [Inference Engine]
                                                             │
                                                             ▼
                                                    [Telemetry & Traces]
                                                (Prometheus/Grafana/Evidently)
                                                             │
                                                             ▼
                                                [Trigger Continuous Retrain]
```

### Spesifikasi Teknis & Kriteria Keberhasilan

1. **Reproducibility & Code Standards**:
   * Seluruh kode harus terorganisasi menggunakan struktur modular yang ketat (tanpa `.ipynb` di tahap eksekusi produksi).
   * Data dan artefak terikat secara deterministik menggunakan DVC yang menunjuk ke MinIO/S3 bucket.
   * Dependensi diisolasi secara deterministik via Poetry dengan *pinned sha256 lockfiles*.

2. **Feature Management & Pipeline Data Contract**:
   * Feast Feature Store wajib memproses data *offline* (Parquet/Delta) dan menyinkronkan data *online* ke Redis secara konsisten.
   * Menerapkan pengujian *point-in-time correctness* pada pemrosesan batch; tidak boleh ada kebocoran informasi (*data leakage*) antara tanggal pengajuan transaksi historis dan label target.
   * Great Expectations harus memvalidasi data *ingress* secara otomatis di setiap tahap eksekusi pipeline. Pipeline **harus gagal (*fail-fast*)** jika skema atau batas variansi dilanggar.

3. **Distributed Training & Model Packaging**:
   * Model klasifikasi risiko harus dilatih menggunakan *Distributed Data Parallel* (Ray Train / PyTorch DDP).
   * Model wajib dikonversi dan dioptimasi menggunakan ONNX Runtime atau TensorRT dengan validasi deviasi performa maksimal $< 0.1\%$ terhadap model dasar.
   * Model di-package ke dalam kontainer multi-stage berbasis Triton Inference Server atau FastAPI yang dioptimalkan dengan footprint kontainer $< 800\text{ MB}$ (tidak termasuk bobot model).

4. **Automated CI/CD/CT & GitOps**:
   * Pemicuan otomatis melalui GitHub Actions / GitLab CI yang menjalankan *unit test*, *data checks*, *model regression tests*, serta kontainerisasi otomatis.
   * ArgoCD mengelola deployment aplikasi ke kluster Kubernetes lokal (Kind/Minikube) atau *cloud-managed* Kubernetes (EKS/GKE).
   * Menerapkan strategi rilis bertahap: **Canary Rollout (10% traffic split)** yang dianalisis secara dinamis sebelum migrasi 100%.

5. **Observability, Drift, & Automated Retraining (CT)**:
   * Ekspor metrik inferensi real-time ke Prometheus dan buat visualisasi terpadu pada Grafana Dashboard.
   * Pantau *Data Drift* dan *Prediction Drift* menggunakan Evidently AI atau WhyLogs.
   * Apabila Population Stability Index (PSI) $> 0.2$ atau nilai *p-value* uji Kolmogorov-Smirnov $< 0.05$ selama jendela waktu observasi 30 menit berturut-turut, sistem wajib secara terotomatisasi menerbitkan *alert* dan memicu *Continuous Retraining DAG* melalui webhook / event trigger ke Argo Workflows atau Airflow.

6. **Target Service Level Objectives (SLO)**:
   * **Inference Latency (P99)**: $\le 25\text{ ms}$ di bawah beban kerja konkuren 500 Request Per Second (RPS).
   * **Serving Availability**: $\ge 99.95\%$.
   * **Automated Rollback Latency**: Degradasi akurasi $> 5\%$ atau error rate HTTP $> 1\%$ harus memicu rollback otomatis dalam tempo $< 60\text{ detik}$.

---

## 5. Prasyarat & Lingkungan Pengembangan
* **Bahasa Pemrograman**: Python 3.10+ (Kecakapan tingkat menengah hingga lanjut dalam OOP, typing, asynchronous programming).
* **Containerization & Orchestration**: Docker, Docker Compose, Kubernetes fundamental (Pods, Deployments, Services, ConfigMaps).
* **Infrastruktur & Cloud**: Pemahaman dasar tentang object storage (S3/GCS), jaringan TCP/HTTP/gRPC, dan sistem operasi Linux (Bash scripting, resource monitoring).
* **Dasar Machine Learning**: Memahami siklus pengembangan model *supervised/unsupervised*, teknik preprocessing, metrik evaluasi, dan deep learning fundamentals (PyTorch/Scikit-Learn).