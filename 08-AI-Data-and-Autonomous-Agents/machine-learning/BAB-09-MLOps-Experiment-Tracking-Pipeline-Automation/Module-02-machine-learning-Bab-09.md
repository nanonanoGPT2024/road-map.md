# BAB 09: MLOps, Experiment Tracking & Pipeline Automation
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengoperasikan arsitektur end-to-end MLOps tingkat enterprise yang mencakup orkestrasi pipeline, *lineage tracking*, *feature store*, registrasi model otomatis, dan gerbang validasi (*quality gates*).
- Mengimplementasikan *Continuous Training* (CT) loop yang memicu retraining otomatis berbasis degradasi performa model (*data/concept drift*) dan kedatangan data baru secara deterministik.
- Membangun pipeline orkestrasi data dan model terisolasi menggunakan abstraksi containerized pipelines (Prefect / Kubeflow Pipelines SDK) yang terintegrasi dengan MLflow Tracking Server dan Feature Store (Feast).
- Menerapkan *Model Governance* dan *Auditability* yang patuh terhadap standar regulasi data (GDPR, ISO/IEC 42001) melalui immutable artifacts, reproducible seedings, cryptographic hashing data, dan environment virtualization.

---

### 2. Prerequisite
Untuk menyerap materi secara optimal, peserta wajib menguasai:
- **Python Lanjutan**: Metaprogramming (decorator, context manager), asynchronous execution (`asyncio`), typing system (`Pydantic`, static typing).
- **Software Engineering & DevOps Core**: Docker multi-stage builds, Kubernetes primitive resources (Pods, Jobs, CRDs), Git commit workflow, CI/CD pipeline (GitHub Actions/GitLab CI).
- **Machine Learning Foundations**: Training lifecycle, evaluation metrics (ROC-AUC, PR-AUC, F1-macro, Brier score), cross-validation, hyperparameter tuning via Bayesian Optimization (Optuna).
- **Database & Storage**: Object storage (S3/GCS API/MinIO), relational metadata storage (PostgreSQL), in-memory caching/NoSQL (Redis).

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur MLOps produksi memisahkan concern sistem ke dalam empat lapisan decoupled:

```
+-----------------------------------------------------------------------------------+
|                            MLOps Production Architecture                          |
+-----------------------------------------------------------------------------------+
|  1. INGESTION & FEATURE TIER                                                      |
|     Raw Data Streams/Batches -> Spark / DuckDB -> Feast Feature Store             |
|     [Online: Redis (Low-Latency)] <======> [Offline: Parquet/Snowflake (Point-in-Time)]
+-----------------------------------------------------------------------------------+
|  2. ORCHESTRATION & TRAINING ENGINE                                               |
|     Workflow DAGs (Prefect / Kubeflow / Argo Workflows)                           |
|     Data Validation (Great Expectations) -> Preprocess -> Tune (Optuna) -> Train  |
+-----------------------------------------------------------------------------------+
|  3. METADATA, ARTIFACT & GOVERNANCE STORE                                         |
|     MLflow Tracking Server <---> PostgreSQL (Runs, Params, Metrics, Lineage)      |
|                            <---> S3/MinIO (Model Binaries, Scalers, Plots)        |
|     MLflow Model Registry (Draft -> Staging -> Production -> Archived)           |
+-----------------------------------------------------------------------------------+
|  4. SERVING, DRIFT DETECTION & FEEDBACK LOOP                                      |
|     Inference Engine (Triton / TorchServe / FastAPI) -> Output                    |
|     Evidently AI / Whylogs -> Monitors KS-Test / PSI -> Trigger CT Pipeline       |
+-----------------------------------------------------------------------------------+
```

#### A. The Immutable Artifact & Lineage Graph
Di lingkungan enterprise, model tidak pernah berupa file `.pkl` yang berdiri sendiri. Model adalah satu kesatuan *tuple* yang terdiri dari:
$$\mathcal{M} = \langle \mathcal{W}, \mathcal{D}_{hash}, \mathcal{C}_{env}, \mathcal{P}_{hyper}, \mathcal{M}_{eval} \rangle$$
Di mana:
- $\mathcal{W}$: Bobot model ter-serialisasi (ONNX, SafeTensors, TorchScript).
- $\mathcal{D}_{hash}$: Cryptographic hash (SHA-256) snapshot dataset pelatihan atau snapshot view dari Feature Store.
- $\mathcal{C}_{env}$: Deklarasi environment komputasi (Docker digest hash, pinned conda/pip lockfile).
- $\mathcal{P}_{hyper}$: State konfigurasi runtime dan hyperparameter.
- $\mathcal{M}_{eval}$: Metrik evaluasi out-of-fold dan test-set holdout.

#### B. Point-in-Time Feature Correctness (Feature Store)
Masalah terbesar dalam pipeline ML produksi adalah *Data Leakage via Temporal Bleeding* (menggunakan data masa depan saat melatih model masa lalu). Feature Store mengatasi ini dengan arsitektur dual-storage (Online vs Offline) menggunakan mekanisme *Time-Travel Join (As-Of Join)*:
Setiap record feature memiliki atribut:
$$\text{FeatureRecord} = (entity\_id, feature\_value, timestamp)$$
Saat query dilakukan untuk observasi pada waktu $T_{obs}$, Feature Store melakukan join:
$$\max(timestamp) \le T_{obs}$$
sehingga nilai fitur yang diambil adalah representasi faktual pada milidetik kejadian perkara tanpa bocoran masa depan.

#### C. Continuous Training (CT) Trigger Mechanisms
Retraining tidak hanya dijalankan via Cron job. CT enterprise mengimplementasikan 3 pemicu:
1. **Event-driven**: Peningkatan volume data baru yang terakumulasi melampaui batas ambang ($N$ baris baru atau $X$ GB).
2. **Metric Degradation-driven**: Population Stability Index (PSI) $> 0.25$ atau degradasi Wasserstein Distance pada feature kritis yang divalidasi oleh background monitoring worker.
3. **Business Performance Feedback**: Terjadinya lonjakan tingkat false-positive pada downstream business KPIs (fraud rate, chargeback rate).

---

### 4. Why & What

| Dimensi | Pendekatan Ad-Hoc / Legacy ML | Pendekatan Enterprise MLOps (Module 02) |
| :--- | :--- | :--- |
| **Reproducibility** | *"Works on my laptop"*, notebook berantakan, dependensi tidak terkunci. | Deterministic DAG run, locked dependency hashes, artifact storage immutable (S3 versioning). |
| **Data Synchronization** | SQL query manual di-copy-paste ke script train; raw copy di laptop. | Centralized Feature Store (Feast), Point-in-time joins, reproducible dataset lineage. |
| **Model Verification** | Manual metric check, deploy langsung jika akurasi tinggi. | Automated Quality Gates: Model shadow comparison, data slice testing, regression tests. |
| **Pipeline Failure Handling**| Script crash di step 4 dari 5 mengharuskan run ulang dari awal. | Stateful orchestrator with DAG task caching, retry strategies, and isolated container execution. |
| **Governance & Audit** | Sulit membuktikan data apa yang digunakan untuk melatih model 6 bulan lalu. | Full provenance tracking: Git commit SHA $\leftrightarrow$ Pipeline Run $\leftrightarrow$ Dataset Snapshot $\leftrightarrow$ Artifact. |

---

### 5. How (Workflow Detail)

Alur kerja Continuous Training (CT) dan Deployment Gate:

```
[Incoming Data Stream]
         │
         ▼
[Feature Ingestion Engine] ───► [Feast Feature Store]
                                         │
 ┌───────────────────────────────────────┘
 ▼
[Prefect Orchestration Triggered]
 ├── Step 1: Great Expectations Suite (Check Nulls, Ranges, Types)
 │           └── [FAIL] ──► Alert Slack/PagerDuty & Halt
 ├── Step 2: Time-Travel Data Extraction (Feast Offline Store)
 ├── Step 3: Train & Hyperparameter Search (Optuna + Distributed Worker)
 ├── Step 4: Metric Logging & Artifact Packaging (MLflow Server)
 └── Step 5: Challenger vs. Champion Model Validation Gate
             ├── Test: Candidate Metrics > Current Production Metrics?
             ├── Test: Inference Latency < SLA Threshold (e.g. 15ms)?
             ├── Test: Data Bias & Slice Fairness Test?
             │
             ├── [PASS] ──► MLflow Registry: Tag as "Staging"
             │              Trigger CD Pipeline (Deploy to Shadow/Canary)
             │
             └── [FAIL] ──► Tag as "Rejected", Log Diagnostic Report
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pabrik Manufaktur Farmasi vs. Dapur Masak Rumahan
- **Legacy ML** ibarat seorang koki yang memasak berdasarkan insting: sejumput garam, sedikit air, mencicipi kuah sendiri. Jika supnya basi atau rasanya aneh, tidak ada yang tahu batch garam mana yang terkontaminasi atau berapa derajat tepatnya kompor dinyalakan.
- **Enterprise MLOps** adalah pabrik farmasi bersertifikasi cGMP (*Current Good Manufacturing Practice*):
  - **Feature Store**: Bahan baku kimia murni tersertifikasi dengan nomor batch dan tanggal kadaluarsa jelas.
  - **Orchestrator**: Jalur perakitan robotik otomatis yang berhenti instan jika sensor suhu menyimpang 0.1°C.
  - **MLflow Tracking**: Sensor otomatis mencatat setiap voltase, durasi, dan kelembapan ruangan per batch kapsul.
  - **Model Registry & Quality Gates**: Uji klinis ganda independen sebelum botol obat diizinkan keluar dari gerbang pabrik menuju apotek (Production).

#### Diagram Transisi Lifecycle State Mesin Produksi:

```
   ┌──────────────┐
   │ Pipeline Run │
   └──────┬───────┘
          │ (Auto-Logged by Orchestrator)
          ▼
   ┌──────────────┐
   │ MLflow Run   │◄─────── Logs: Parameters, Metrics, Conda Env, Git SHA
   └──────┬───────┘
          │
          ├──────────────────────────────────────────────┐
          │ (Model Candidate Generated)                  │
          ▼                                              ▼
   ┌──────────────┐                              ┌──────────────┐
   │ Quality Gate │                              │ Validation   │
   │ Benchmark    ├─[Fail: Inferior Metric]────► │ Rejected /   │
   └──────┬───────┘                              │ Archived Run │
          │                                      └──────────────┘
          │ [Pass: Better Metric & Latency]
          ▼
   ┌──────────────┐
   │ Model        │
   │ Registry     │
   └──────┬───────┘
          │
   ┌──────┴──────────────────────────┐
   ▼                                 ▼
┌──────────────────┐       ┌────────────────────┐
│ Stage: "Staging" │       │ Stage: "Production"│
│ (Shadow Serving) │       │ (Live Traffic)     │
└──────────────────┘       └────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Fundamental MLflow Logging & Tracking Decorator

Implementasi dasar pelacakan experiment secara modular menggunakan context manager dan logging native:

```python
import mlflow
import numpy as np
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import train_test_split


def run_simple_experiment():
    mlflow.set_tracking_uri("sqlite:///mlruns_demo.db")
    mlflow.set_experiment("simple-rf-baseline")

    # Generate Synthetic Dataset
    X, y = make_classification(
        n_samples=1000, n_features=20, n_informative=10, random_state=42
    )
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    n_estimators = 75
    max_depth = 5

    with mlflow.start_run(run_name="rf-baseline-run") as run:
        # Log Hyperparameters
        mlflow.log_params(
            {"n_estimators": n_estimators, "max_depth": max_depth}
        )

        clf = RandomForestClassifier(
            n_estimators=n_estimators, max_depth=max_depth, random_state=42
        )
        clf.fit(X_train, y_train)

        # Predictions
        preds_proba = clf.predict_proba(X_test)[:, 1]

        # Calculate Metrics
        auc = roc_auc_score(y_test, preds_proba)
        loss = log_loss(y_test, preds_proba)

        # Log Metrics
        mlflow.log_metrics({"roc_auc": auc, "log_loss": loss})

        # Log Model Artifact
        mlflow.sklearn.log_model(
            sk_model=clf,
            artifact_path="model",
            registered_model_name="simple-rf-model",
        )

        print(
            f"Run ID: {run.info.run_id} completed. ROC-AUC: {auc:.4f}, Loss: {loss:.4f}"
        )


if __name__ == "__main__":
    run_simple_experiment()
```

#### B. Practical Example: Enterprise Production-Grade Pipeline (Prefect + MLflow + Quality Gates + Pydantic Config)

Pipeline terotomatisasi penuh yang merefleksikan standar enterprise: modular, divalidasi dengan type checking, mengeksekusi *champion vs challenger check*, serta mendaftarkan model secara dinamis ke Model Registry.

```python
"""Enterprise Continuous Training Pipeline with Quality Assurance Gates

Architecture:
  - Configuration Management: Pydantic BaseSettings
  - Orchestrator: Prefect 2.x
  - Experiment Tracking & Registry: MLflow
  - Quality Validation: Out-of-fold metrics & Champion Comparison
"""

import sys
from typing import Any, Dict, Tuple
import mlflow
from mlflow.tracking import MlflowClient
import numpy as np
import pandas as pd
from prefect import flow, task
from pydantic import BaseModel, Field
from sklearn.datasets import fetch_california_housing
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

# ==========================================
# 1. Pipeline Configuration Schema
# ==========================================


class TrainingConfig(BaseModel):
    experiment_name: str = Field(
        default="housing-regression-enterprise", description="MLflow Exp Name"
    )
    model_name: str = Field(
        default="california_housing_gbr", description="Registry Model Name"
    )
    tracking_uri: str = Field(
        default="sqlite:///enterprise_mlflow.db",
        description="MLflow Tracking Backend",
    )
    test_size: float = Field(default=0.2, ge=0.05, le=0.5)
    random_state: int = Field(default=42)
    n_estimators: int = Field(default=150, ge=10)
    learning_rate: float = Field(default=0.08, gt=0.0)
    max_depth: int = Field(default=4, ge=1)
    rmse_threshold_gate: float = Field(
        default=0.60, description="Max acceptable RMSE"
    )


# ==========================================
# 2. Pipeline Tasks
# ==========================================


@task(name="extract-data", retries=2, retry_delay_seconds=5)
def extract_data() -> pd.DataFrame:
    """Ekstraksi dataset dan penambahan metadata audit."""
    dataset = fetch_california_housing(as_frame=True)
    df = dataset.frame
    # Menambahkan deterministic row hash untuk data lineage audit
    df["_lineage_hash"] = pd.util.hash_pandas_object(df, index=True).astype(
        str
    )
    return df


@task(name="validate-and-split-data")
def validate_and_split(
    df: pd.DataFrame, config: TrainingConfig
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Validasi integritas dataset awal dan splitting."""
    if df.isnull().values.any():
        raise ValueError(
            "CRITICAL: Dataset terdeteksi memiliki missing values (NaN/Null)."
        )

    target_col = "MedHouseVal"
    features = [c for c in df.columns if c not in [target_col, "_lineage_hash"]]

    X_train, X_test, y_train, y_test = train_test_split(
        df[features],
        df[target_col],
        test_size=config.test_size,
        random_state=config.random_state,
    )
    return X_train, X_test, y_train, y_test


@task(name="train-candidate-model")
def train_model(
    X_train: pd.DataFrame, y_train: pd.Series, config: TrainingConfig
) -> GradientBoostingRegressor:
    """Pelatihan model dengan parameterized hyperparameter."""
    model = GradientBoostingRegressor(
        n_estimators=config.n_estimators,
        learning_rate=config.learning_rate,
        max_depth=config.max_depth,
        random_state=config.random_state,
    )
    model.fit(X_train, y_train)
    return model


@task(name="evaluate-metrics")
def evaluate_model(
    model: GradientBoostingRegressor, X_test: pd.DataFrame, y_test: pd.Series
) -> Dict[str, float]:
    """Kalkulasi metrik performa model."""
    predictions = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, predictions))
    mae = mean_absolute_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)

    metrics = {"rmse": float(rmse), "mae": float(mae), "r2": float(r2)}
    return metrics


@task(name="quality-and-champion-gate")
def quality_gate(
    metrics: Dict[str, float],
    config: TrainingConfig,
    client: MlflowClient,
) -> bool:
    """Quality Assurance Gate:

    1. Memeriksa apakah metrik lolos kriteria batas absolut.
    2. Membandingkan metrik challenger vs champion yang sedang aktif di production.
    """
    candidate_rmse = metrics["rmse"]

    # Gate 1: Absolute threshold check
    if candidate_rmse > config.rmse_threshold_gate:
        print(
            f"Quality Gate Failed: RMSE {candidate_rmse:.4f} > Threshold {config.rmse_threshold_gate:.4f}"
        )
        return False

    # Gate 2: Champion comparison check
    try:
        latest_prod = client.get_latest_versions(
            config.model_name, stages=["Production"]
        )
        if not latest_prod:
            print("Tidak ada champion di Production. Model lolos secara default.")
            return True

        champion_run_id = latest_prod[0].run_id
        champion_metrics = client.get_run(champion_run_id).data.metrics
        champion_rmse = champion_metrics.get("rmse", float("inf"))

        print(
            f"Champion RMSE: {champion_rmse:.4f} | Candidate RMSE: {candidate_rmse:.4f}"
        )
        if candidate_rmse < champion_rmse:
            print(
                "Challenger mengungguli Champion! Lolos evaluasi promosi."
            )
            return True
        else:
            print(
                "Challenger inferior dibandingkan Champion. Promosi ditolak."
            )
            return False

    except Exception as exc:
        print(f"Info/Warning saat mengambil data champion: {exc}")
        return True  # Fallback for empty registries


# ==========================================
# 3. Main Workflow Orchestration Flow
# ==========================================


@flow(name="enterprise-ct-pipeline")
def continuous_training_workflow(
    config: TrainingConfig = TrainingConfig(),
) -> None:
    mlflow.set_tracking_uri(config.tracking_uri)
    mlflow.set_experiment(config.experiment_name)
    client = MlflowClient(tracking_uri=config.tracking_uri)

    # Step 1: Ingestion
    raw_df = extract_data()

    # Step 2: Validation & Split
    X_train, X_test, y_train, y_test = validate_and_split(raw_df, config)

    # Step 3 & 4: Experiment Logging & Training
    with mlflow.start_run(
        run_name="automated-training-run"
    ) as run:
        mlflow.log_params(config.model_dump())
        mlflow.set_tag("pipeline.orchestrator", "prefect")
        mlflow.set_tag("pipeline.version", "2.1.0")

        # Training
        model = train_model(X_train, y_train, config)

        # Evaluation
        metrics = evaluate_model(model, X_test, y_test)
        mlflow.log_metrics(metrics)

        # Logging Artifact with input signature
        signature = mlflow.models.infer_signature(X_train, model.predict(X_train))
        model_info = mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="gbr_model",
            signature=signature,
        )

        # Step 5: Quality Gate Decision
        passed = quality_gate(metrics, config, client)

        if passed:
            print("Mendaftarkan model ke Model Registry...")
            reg_model = mlflow.register_model(
                model_uri=model_info.model_uri, name=config.model_name
            )

            # Promosikan versi ke Production, arsipkan yang lama
            client.transition_model_version_stage(
                name=config.model_name,
                version=reg_model.version,
                stage="Production",
                archive_existing_versions=True,
            )
            print(
                f"Model Version {reg_model.version} berhasil dipromosikan ke PRODUCTION."
            )
        else:
            print("Model candidate ditolak masuk production stage.")


if __name__ == "__main__":
    continuous_training_workflow()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Continuous Training Multi-Tenant FinTech (Anti-Fraud)
- **Konteks Skala**: Transaksi 12.000 QPS; 250 juta transaksi harian; retensi fraud data 3 tahun.
- **Problem Statement**: Modus penipuan (fraud attack vectors) bermutasi setiap 3–5 hari (*adversarial concept drift*). Menggunakan batch retraining mingguan menyebabkan kerugian fraud melonjak sebesar $1.8M per bulan karena latency model adaptasi lambat.
- **Arsitektur Solusi**:
  1. **Dual Feature Pipeline**:
     - *Streaming*: Kafka -> Apache Flink menghitung rolling aggregate 5-menit (contoh: `count_tx_last_5m`, `sum_amount_last_5m`) -> Di-push ke Redis (online store Feast) via dual-write.
     - *Batch*: Apache Iceberg table di S3 yang di-query via Trino/Athena -> Offline store Feast.
  2. **Automated Event-Triggered CT**:
     - Worker Drift Monitor (menggunakan *Evidently AI* pada streaming sink) mengevaluasi metrik Kolmogorov-Smirnov (KS-test) tiap 1 jam.
     - Jika 3 fitur utama memiliki nilai p-value $< 0.01$ atau F1-score harian turun di bawah 0.88, event `DRIFT_DETECTED` dipublikasikan ke Kafka.
  3. **Pipeline Orkestrasi (Kubeflow Pipelines di atas EKS)**:
     - Membaca snapshot data 14 hari terakhir via Feast point-in-time join.
     - Training XGBoost memanfaatkan GPU node auto-scaling spot instances.
     - Melakukan evaluation gate komparatif terhadap model aktif.
  4. **Deployment Strategy**:
     - Lolos Quality Gate -> Mengupdate CRD Canary di Kubernetes via Argo Rollouts.
     - 10% traffic dialihkan ke model baru (*canary slice*), sisa 90% ke model champion.
     - Automated canary analysis mengobservasi false positive rate selama 2 jam sebelum promosi penuh 100%.
- **Dampak Bisnis**:
  - Mengurangi Mean Time To Mitigate (MTTM) fraud vector baru dari 7 hari menjadi 3,5 jam.
  - Menghilangkan *Data Leakage* sepenuhnya, menurunkan false positive penghentian kartu kredit nasabah sah sebesar 31%.

---

### 9. Trade-offs

| Parameter | Solusi A: Minimalist / DIY (Cron + Script + Single VM) | Solusi B: Full Enterprise (Feature Store + Orchestrator + Registry) | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Complexity & Ops Overhead** | **Sangat Rendah**: Cukup satu VPS, skrip shell, dan cron. | **Tinggi**: Membutuhkan Kubernetes cluster, PostgreSQL backend, S3/MinIO, Redis, dan network peering. | Solusi B memerlukan tim platform engineer terspesialisasi. Overkill untuk startup tahap awal dengan 1-2 model. |
| **Data Consistency & Leakage** | **Risiko Sangat Tinggi**: Perhitungan fitur offline sering berbeda logika dengan online serving (Training-Serving Skew). | **Tereliminasi**: Feature Store menjamin satu sumber definisi fitur (*single logic definition*) untuk batch & real-time. | Biaya arsitektur Solusi B impas jika potensi kerugian akibat bias model bernilai jutaan dolar. |
| **Training Pipeline Latency** | **Cepat**: Eksekusi lokal tanpa network transport antar step container. | **Ada Network Overhead**: Setiap step containerized passing artifact ke S3/blob store. | Solusi B lebih lambat per-step, namun memiliki task cache: jika step 3 gagal, step 1 & 2 tidak perlu dijalankan ulang. |
| **Infrastructure Cost** | **Rendah**: Resource server static. | **Dinamis & Fluktuatif**: Cluster Kubernetes auto-scaling, IOPS storage tinggi, Redis RAM cluster. | Solusi B menghemat biaya jangka panjang melalui spot instances transient nodes saat training, mati saat idle. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Training-Serving Skew Akibat Parsing Fitur Asinkron
- **Gejala**: Model menghasilkan skor akurasi 99% saat validasi offline, namun akurasi rontok menjadi 52% saat traffic real-time diproses.
- **Penyebab**: Script feature engineering di preprocessing training menggunakan method `pandas.DataFrame.apply()` dengan timezone UTC, sedangkan backend live API (FastAPI) menggunakan datetime lokal server tanpa normalisasi ISO-8601.
- **Mitigasi**: Serialisasikan pipeline transformasi sebagai artefak terpadu (misal Sklearn `Pipeline`, ColumnTransformer, atau Feast Transformation Service). Jangan memprogram ulang logika komputasi fitur di layer aplikasi serving!

#### Kesalahan 2: Unbound Artifact Growth pada MLflow Backend
- **Gejala**: Disk storage instance MLflow habis, database PostgreSQL metadata mengalami hang karena query `mlflow search_runs` timeout.
- **Penyebab**: Melakukan logging model berukuran gigabyte atau raw evaluation dataframe di setiap epoch training hyperparameter search loop (ratusan iterasi Optuna).
- **Mitigasi**:
  1. Hanya log model binary pada iterasi terbaik (*best run*), bukan setiap trial.
  2. Implementasikan retention lifecycle policy pada bucket S3 (misal: otomatis hapus artefak `mlruns/` yang berusia lebih dari 90 hari kecuali tagged `keep-forever` atau `Production`).

#### Kesalahan 3: Non-Deterministic Pipelines
- **Gejala**: Pipeline CT menghasilkan model dengan performa yang fluktuatif tanpa ada perubahan data.
- **Penyebab**: Hilangnya seeding randomness di multiple layer (numpy, random, framework CUDA determinism) dan shuffle data tanpa sorting index awal.
- **Mitigasi**: Terapkan fungsi enforcement determinisme di awal setiap task:
```python
import os
import random
import numpy as np


def enforce_reproducibility(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    # Jika menggunakan PyTorch:
    # torch.manual_seed(seed)
    # torch.cuda.manual_seed_all(seed)
    # torch.backends.cudnn.deterministic = True
```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum mengaktifkan CT pipeline secara otonom di cluster produksi:

- [ ] **Data Immutability**: Training data memiliki hash identitas unik atau commit snapshot time-travel.
- [ ] **Strict Typing**: Payload inferensi dan training divalidasi via Pydantic atau Pandera schema.
- [ ] **Model Signature**: Model yang disimpan di registry wajib memiliki `signature` (input & output tensor/dataframe contract) yang eksplisit.
- [ ] **Decoupled Compute**: Task pipeline berjalan pada isolated container (Kubernetes Job/Pod), bukan di runtime shared server.
- [ ] **Automated Rollback**: Deployment controller memiliki mekanisme instan untuk revert traffic ke model versi sebelumnya jika rate HTTP 5xx serving $> 0.05\%$.
- [ ] **Credential Isolation**: Tidak ada raw AWS/GCP key di dalam kode atau Docker image; gunakan IAM Roles / Workload Identity.
- [ ] **Telemetry Metric Alarms**: Alert aktif via PagerDuty/Slack untuk run failure, data schema violation, dan quality gate drop.

---

### 12. Hands-on Practice

Buat direktori kerja lokal dan simpan script pengujian berikut untuk mempraktikkan automated training, logging, dan artifact inspection.

#### Struktur Direktori:
```text
hands-on/m02/
├── config.py
├── pipeline.py
└── test_pipeline.py
```

#### Langkah 1: Persiapan Environment
```bash
mkdir -p hands-on/m02
cd hands-on/m02
python3 -m venv venv
source venv/bin/activate
pip install prefect mlflow scikit-learn pandas numpy pydantic
```

#### Langkah 2: Buat File `config.py`
```python
# hands-on/m02/config.py
from pydantic import BaseModel


class PipelineConfig(BaseModel):
    experiment_name: str = "hands-on-mlops-m02"
    model_name: str = "production-fraud-detector"
    db_uri: str = "sqlite:///hands_on_mlflow.db"
    train_split_ratio: float = 0.8
    seed: int = 1337
```

#### Langkah 3: Buat File `pipeline.py`
Tulis script lengkap dengan mengadopsi struktur dari [Seksi 7.B](#b-practical-example-enterprise-production-grade-pipeline-prefect--mlflow--quality-gates--pydantic-config), lalu eksekusi:

```bash
python pipeline.py
```

#### Langkah 4: Buka MLflow Dashboard
```bash
mlflow ui --backend-store-uri sqlite:///enterprise_mlflow.db --port 5000
```
Buka browser pada `http://localhost:5000` dan verifikasi bahwa:
1. Experiment terdaftar dengan metrik (`rmse`, `mae`, `r2`).
2. Artifact model tersimpan lengkap dengan file `MLmodel`, signature schema, dan pickle/conda environment.
3. Model terdaftar di tab **Models** dengan versi 1 berstatus **Production**.

---

### 13. Exercise

#### Level Easy
Ubah implementasi `Simple Example` di Seksi 7.A agar menyimpan matriks konfusi (*confusion matrix plot*) sebagai artefak gambar `.png` ke dalam MLflow Run menggunakan `mlflow.log_figure()`.

#### Level Medium
Tambahkan mekanisme *Data Validation Check* menggunakan Pydantic/Pandera di dalam task `validate-and-split-data` pada `Practical Example`. Pipeline harus langsung melempar error kustom `DataSchemaError` dan membatalkan pipeline run sebelum model training dimulai jika ada kolom yang bertipe data salah atau nilai float berada di luar batas realistis (misal: harga rumah negatif).

#### Level Hard
Kembangkan pipeline di Seksi 7.B untuk mengimplementasikan optimasi Hyperparameter terdistribusi menggunakan **Optuna** di dalam Prefect task.
- Jalankan 20 trials tuning untuk mencari parameter optimal `n_estimators`, `max_depth`, dan `learning_rate`.
- Setiap trial Optuna harus dicatat sebagai nested run di bawah run MLflow utama menggunakan `nested=True`.
- Model terbaik dari best trial yang dipilih otomatis dievaluasi terhadap champion model di MLflow Model Registry.

---

### 14. Challenge

**Skenario**: Anda adalah Principal MLOps Engineer di platform E-Commerce berskala global. 
Platform mendeteksi lonjakan anomali pembatalan pesanan merchant. Tim Data Science telah membuat script baseline, namun model deployment masih dijalankan secara manual setiap bulan.

**Tugas Tantangan Arsitektur**:
Rancang arsitektur sistem CT tertutup (*Closed-loop Continuous Training System*) tanpa intervensi manusia langsung:
1. Tulis blueprint detail integrasi antara **Feast Feature Store**, **Argo Workflows / Kubeflow**, dan **MLflow**.
2. Rancang algoritma failover otomatis jika model challenger yang dipromosikan ke Canary deployment menunjukkan lonjakan latency p99 $> 100\text{ms}$ atau error rate $> 0.1\%$, termasuk mekanisme *circuit breaker* untuk rollback traffic ke model champion dalam waktu kurang dari 30 detik.
3. Definisikan manifest konfigurasi pipeline deklaratif (YAML/Python SDK) yang mencakup state machine deployment gate tersebut secara komprehensif.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa fungsi utama `Model Signature` pada MLflow Tracking dan mengapa wajib didefinisikan di level enterprise?
2. Jelaskan perbedaan mendasar antara *MLflow Experiment Tracking* dan *MLflow Model Registry*!
3. Mengapa menyimpan model machine learning sebagai script serialized mentah (seperti file `.pkl` di Git repo) merupakan anti-pattern fatal dalam rekayasa perangkat lunak?
4. Apa yang dimaksud dengan *Data/Concept Drift* dan bagaimana kaitannya dengan kebutuhan Continuous Training?
5. Apa peran parameter `archive_existing_versions=True` saat transisi stage model pada MLflow Client?

#### Pertanyaan Intermediate
6. Bagaimana cara Feature Store mencegah fenomena *Temporal Data Leakage* (fitur masa depan merembes ke data pelatihan masa lalu)?
7. Di dalam arsitektur containerized pipeline (seperti Prefect/Kubeflow), mengapa passing dataframe berukuran 20 GB antar task via memory/return variable dilarang keras, dan apa pola alternatif standar industri untuk mengatasinya?
8. Bagaimana strategi Anda memitigasi *training-serving skew* pada pipeline deep learning yang memiliki operasi augmentasi citra acak?
9. Mengapa *Bayesian Optimization* (seperti yang digunakan Optuna) jauh lebih efisien dibandingkan *Grid Search* dalam pipeline continuous retraining otomatis?
10. Jelaskan risiko keamanan model deserialization (`pickle.load`) dan sebutkan format serialisasi alternatif yang lebih aman untuk model inferensi produksi!

#### Skenario Kasus Produksi
11. **Skenario 1**: Pipeline CT Anda secara otomatis melatih model baru setiap malam. Suatu hari, model baru lolos semua quality gate metrik offline (AUC meningkat dari 0.85 menjadi 0.96), namun saat diuji di stage canary, tingkat konversi bisnis turun 40%. Investigasi root cause apa yang pertama kali harus Anda lakukan pada data lineage dan split strategy?
12. **Skenario 2**: Sistem pendeteksi fraud Anda menggunakan MLflow Registry. Sebuah model challenger berhasil dipromosikan ke `Production`. Namun 5 menit kemudian, cluster serving downstream mengalami *Out-Of-Memory (OOM) CrashLoopBackOff*. Bagaimana Anda merancang automated pre-flight serving test di dalam pipeline CI/CD untuk mencegah model lolos ke registry jika memiliki memory footprint yang melanggar SLA?
13. **Skenario 3**: Perusahaan Anda diwajibkan oleh regulator perbankan untuk membuktikan data spesifik mana yang digunakan untuk melatih model credit-scoring versi tertentu yang dibuat 18 bulan lalu. Jelaskan implementasi sistem metadata storage yang menjamin compliance auditability ini!

---

### 16. Summary

- **Enterprise MLOps** mentransformasikan eksperimen machine learning dari pekerjaan artisanal berbasis notebook yang rentan error menjadi proses rekayasa perangkat lunak industri yang deterministik, terukur, dan reproducible.
- **Pilar Inti**: Terdiri dari Orchestration engine terisolasi (Prefect/Kubeflow), Feature Store yang menjamin point-in-time correctness (Feast), Experiment Tracking & Registry tersentralisasi (MLflow), serta Continuous Validation Gates.
- **Model sebagai Entitas Holistik**: Sebuah model produksi bukan sekadar file binary bobot matematis, melainkan kesatuan utuh antara representasi kode, hashing data, dependensi environment, signature kontrak data, dan sertifikat kelayakan metrik.
- **Otomasi Terkendali**: Penerapan Continuous Training (CT) wajib diimbangi dengan gerbang komparasi champion-vs-challenger dan deployment canary/shadow guna menjamin bahwa stabilitas sistem dan tujuan performa bisnis downstream tidak pernah terkompromi.