# BAB 02: Modular Pipeline & Experiment Tracking
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang Arsitektur Pipeline Modular Skala Enterprise**: Menerapkan abstraksi *step-based DAG* (Directed Acyclic Graph) yang memisahkan *compute engine*, *orchestration plane*, dan *metadata storage*.
- **Mengimplementasikan Deterministic Execution & Caching**: Membangun mekanisme *execution caching* berbasis *cryptographic content-hashing* untuk dataset, parameter, dan kode sumber guna mengeliminasi komputasi redundan.
- **Mengoperasikan High-Availability (HA) Experiment Tracking**: Mengonfigurasi arsitektur MLflow/Tracking Engine berbasis PostgreSQL multi-node dengan replikasi streaming dan S3-compatible Object Storage yang mendukung *asynchronous batch metric logging*.
- **Membangun Automated Model Lineage & Provenance Graph**: Merekam silsilah artefak (*data lineage*) dari raw data hash, intermediate transformed tensor, checkpoint model, hingga metadata registrasi secara otomatis menggunakan standar OpenLineage/MLflow Entities.
- **Mencegah Common Production Anti-Patterns**: Mengidentifikasi dan memitigasi *pipeline leakages*, state mutation lintas langkah pipeline, serta *connection pool exhaustion* pada backend store tracking engine.

---

### 2. Prerequisites
Sebelum mendalami modul ini, peserta wajib menguasai:
- **Pemrograman Python Tingkat Lanjut**: Concurrency (`asyncio`, `threading`), Metaprogramming (Decorators, Context Managers), Object-Oriented Design Pattern (Strategy, Factory, Inversion of Control), Type Annotations (`typing`, `pydantic`).
- **Containerization & Orchestration Dasar**: Dockerfile multi-stage builds, volume mounting, networking, pemahaman dasar Kubernetes primitive (Pods, Jobs, ConfigMaps, Secrets).
- **Relational Database & Object Storage**: PostgreSQL (Connection pooling, ACID properties, schema migrations) dan Amazon S3 / MinIO API (Signed URLs, multipart uploads, bucket policies).
- **Dasar Machine Learning Lifecycle**: Alur data preprocessing, feature engineering, model training, cross-validation, dan metric evaluation.

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur pipeline modular modern memisahkan sistem machine learning menjadi tiga bidang independen (*decoupled planes*): **Orchestration Plane**, **Execution/Compute Plane**, dan **Metadata/Tracking Plane**.

```
+-----------------------------------------------------------------------------------+
|                                ORCHESTRATION PLANE                                |
|  DAG Compiler / Scheduler (e.g., Kubeflow Pipelines, Airflow, Temporal, Kedro)   |
|  - Graph Topology Validation   - Task Dependency Resolution  - Parameter Injection |
+-----------------------------------------+-----------------------------------------+
                                          | Trigger Step execution
                                          v
+-----------------------------------------------------------------------------------+
|                               COMPUTE / EXECUTE PLANE                             |
|  Isolated Worker Nodes / Ephemeral Containers (Ray, K8s Jobs, Bare-metal Workers)  |
|                                                                                   |
|  +-------------------------+     Shared Object Store     +---------------------+  |
|  | Step 1: Ingest & Hash   | --[ Immutable Artifact ]--> | Step 2: Transform   |  |
|  +-------------------------+      (Parquet / S3)         +---------------------+  |
|               |                                                     |             |
|               | Artifact URI                                        | Artifact URI|
|               v                                                     v             |
+---------------+-----------------------------------------------------+-------------+
                | Read/Write Metadata & Run States                    |
                v                                                     v
+-----------------------------------------------------------------------------------+
|                           METADATA & TRACKING PLANE                               |
|  High-Availability Experiment Tracker (MLflow Tracking Server, OpenLineage)       |
|                                                                                   |
|    +----------------------------------+    +----------------------------------+   |
|    |      RDBMS (Backend Store)       |    |   Artifact Store (Blob Storage)  |   |
|    |  PostgreSQL HA (Patroni / PgB)   |    |    AWS S3 / Ceph / MinIO Cluster |   |
|    |  - Runs, Params, Metrics, Tags   |    |    - Raw Datasets, Weights (.pt) |   |
|    |  - Lineage Edge Definition       |    |    - ONNX, Encoders, Environments|   |
|    +----------------------------------+    +----------------------------------+   |
+-----------------------------------------------------------------------------------+
```

#### A. DAG Execution Engine & Parameter Hashing
Setiap *step* dalam pipeline modular dimodelkan sebagai fungsi murni (*pure mathematical function*):
$$f(\text{Artifact}_{\text{in}}, \theta) \to \text{Artifact}_{\text{out}}$$
Di mana $\theta$ merepresentasikan hyperparameter konfigurasi.

Untuk mendukung *deterministic caching*, internal engine menghitung hash eksekusi step ($H_{\text{step}}$):
$$H_{\text{step}} = \text{SHA256}(H_{\text{code}} \parallel H_{\text{inputs}} \parallel H_{\text{parameters}} \parallel H_{\text{environment}})$$
- $H_{\text{code}}$: Git commit hash tree dari direktori modul eksekusi.
- $H_{\text{inputs}}$: SHA-256 fingerprint dari seluruh input artifact manifests.
- $H_{\text{parameters}}$: Canonical JSON serialized string dari hyperparameter dictionary.
- $H_{\text{environment}}$: Container image digest (`sha256:...`) atau lockfile hash (`poetry.lock`/`requirements.txt`).

Jika $H_{\text{step}}$ sudah terdapat pada Metadata Cache Table dengan status `SUCCESS`, compute engine melewati eksekusi (*cache hit*) dan langsung menyalurkan output artifact URI dari registri historis ke langkah berikutnya.

#### B. Experiment Tracking Architecture Internal
Tracking Server bertindak sebagai perantara stateless antara compute worker dan persistent storage:
1. **Stateless API Gateway**: Menerima request HTTP REST / gRPC dari MLflow SDK worker. Menggunakan Gunicorn/Uvicorn worker process.
2. **Backend Store Interaction**: Menggunakan Object Relational Mapping (SQLAlchemy) ke PostgreSQL. Setiap *metric logging* (`log_metric`) menghasilkan baris pada tabel `metrics` yang berpotensi memicu *I/O bottleneck* jika tidak di-batch secara asynchronous oleh worker client.
3. **Artifact Proxy vs Direct Upload**:
   - *Legacy Direct Upload*: Worker membutuhkan kredensial IAM cloud langsung ke S3 bucket. Ini melanggar prinsip *least-privilege* pada multi-tenant infrastructure.
   - *Artifact Proxy Mode (Zero-Trust Enterprise)*: Worker mengirim artefak melalui Tracking Server streaming endpoint, atau Tracking Server menerbitkan *S3 Pre-signed URL* bertenggang waktu pendek (short-lived presigned PUT/GET URLs), mengisolasi kredensial infrastruktur di dalam server.

---

### 4. Why & What

| Dimensi | Legacy Workflow (Monolithic Scripts / Jupyter) | Enterprise Modular Pipeline Architecture |
| :--- | :--- | :--- |
| **State Coupling** | Status komputasi tersimpan di memori lokal RAM / Global Variables. | Status terisolasi secara matematis; state transfer terjadi via persistent, immutable object storage URI. |
| **Reproducibility** | Tidak deterministik ("Works on my machine" syndrome). Versi package & data tidak terlacak serentak. | Full Lineage: Git SHA + Data SHA256 + Environment Digest + Run Params terkunci di Metadata Backend. |
| **Failure Recovery** | Jika script gagal di epoch ke-90 atau tahapan evaluasi, seluruh proses harus diulang dari raw data ingest. | *Fault-tolerant Step Checkpointing*: Sistem melanjutkan eksekusi dari DAG node terakhir yang gagal (*smart resume*). |
| **Traceability** | Sulit membuktikan model $M_1$ dilatih dari subset data transaksi yang mana (kepatuhan audit GDPR/PCI-DSS gagal). | Graph Lineage terverifikasi: Audit trail memetakan model production langsung ke commit data mentah dan hash kode. |
| **Compute Efficiency** | Script dijalankan berulang kali untuk eksperimen kecil, membakar resource GPU/CPU secara identik. | *Content-addressed caching*: Hanya mengeksekusi node yang mengalami mutasi parameter, kode, atau data. |

---

### 5. How (Workflow Detail)

Alur kerja pipeline modular enterprise dari inisiasi hingga registrasi model mengikuti siklus hidup berikut:

```
[Developer/CI Runner]
        │
        ▼
1. Validate Graph Topology & Static Types (Mypy, Pydantic)
        │
        ▼
2. Resolve Step Caches (Query Metadata Store via $H_{\text{step}}$)
   ├─── Hit  ──> Skip Execution -> Forward historical Artifact URI ──────┐
   └─── Miss ──> Spawn Isolated Execution Worker Container              │
                        │                                                │
                        ▼                                                │
                 3. Worker Ingests Input Artifacts                       │
                    (Streamed from S3 Object Store)                      │
                        │                                                │
                        ▼                                                │
                 4. Execute Functional Logic (Train/Transform)           │
                        │                                                │
                        ▼                                                │
                 5. Asynchronous Tracking Ingestion                      │
                    (Batch log metrics/params via HTTP Proxy to PG)      │
                        │                                                │
                        ▼                                                │
                 6. Persist Output Artifacts & Generate Manifest         │
                    (Upload to S3 with cryptographic checksum)           │
                        │                                                │
                        ▼                                                │
                 7. Update Step Cache State in Metadata Store            │
                        │                                                │
                        ├────────────────────────────────────────────────┘
                        ▼
                 8. DAG Evaluator Transitions to Successor Nodes
                        │
                        ▼
                 9. Auto-Registration Gate
                    (Promote to Model Registry if Quality Metrics Met)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Pabrik Manufaktur Farmasi Modern
Bayangkan meracik obat presisi:
- **Jupyter Notebook Monolitik** seperti apoteker mencampur bahan kimia dalam satu ember besar tanpa takaran tertulis, mencicipinya sesekali, dan jika tumpah di langkah terakhir, seluruh bahan terbuang dan racikan harus diulang dari nol tanpa tahu mengapa rasanya berbeda dari racikan kemarin.
- **Enterprise Modular Pipeline** adalah fasilitas farmasi modern bersertifikasi cGMP (*Current Good Manufacturing Practice*):
  - Setiap bahan baku masuk memiliki barcode kontainer tersegel unik (**Immutable Input Artifact Hash**).
  - Setiap ruang proses (Sterilisasi, Ekstraksi, Pengeringan) beroperasi mandiri secara steril (**Isolated Container Step**).
  - Jika formula ekstraksi tidak berubah dari batch kemarin, fasilitas menggunakan stok hasil ekstraksi kemarin yang sudah tersimpan di ruang pendingin (**Step Caching**).
  - Sensor di setiap tangki mencatat suhu dan tekanan setiap milidetik ke black-box terpusat (**Asynchronous Metric Logging ke MLflow**).
  - Setiap botol obat jadi memiliki QR code yang dapat melacak kembali hingga ke nomor batch daun herbal yang dipetik petani 6 bulan lalu (**Lineage Tracking**).

#### Arsitektur Sistem Modular Pipeline & Experiment Tracking

```
                           DEVELOPER & CI/CD INTERFACE
               +---------------------------------------------------+
               | Kedro / KFP Pipeline Definition (YAML / Python)   |
               +---------------------------------------------------+
                                         |
                                         v
                         GRAPH SCHEDULER ENGINE (Local/K8s)
    +-------------------------------------------------------------------------+
    | Resolve Graph: [Data Ingest] -> [Feature Eng] -> [Train] -> [Evaluate]   |
    +-------------------------------------------------------------------------+
         |                        |                     |              |
         v (Task 1)               v (Task 2)            v (Task 3)     v (Task 4)
  +--------------+         +--------------+      +--------------+ +--------------+
  | IngestWorker |         | FE Worker    |      | Train Worker | | Eval Worker  |
  | (caching hit)|         | (ephemeral)  |      | (GPU node)   | | (CPU node)   |
  +--------------+         +--------------+      +--------------+ +--------------+
         |                        |                     |              |
         | Read cached out        | Stream in Data      | Stream data  | Stream weights
         |                        | Push Parquet        | Push .pt     | Push report
         v                        v                     v              v
+─────────────────────────────────────────────────────────────────────────────+
|                        S3-COMPATIBLE OBJECT STORAGE                         |
|  s3://mlops-artifacts/runs/<run_id>/features/dataset.parquet                |
|  s3://mlops-artifacts/runs/<run_id>/models/model.onnx                       |
+─────────────────────────────────────────────────────────────────────────────+
         ^                        ^                     ^              ^
         │                        │                     │              │
         │ Batch REST/gRPC        │ Batch REST/gRPC     │ Batch REST   │ Metadata sync
         v                        v                     v              v
+─────────────────────────────────────────────────────────────────────────────+
|                   HIGH-AVAILABILITY TRACKING SERVER (MLflow)                |
|                  (Stateless Workers behind NGINX Load Balancer)             |
+─────────────────────────────────────────────────────────────────────────────+
                                         │
                                         ▼ Connection Pool (PgBouncer)
+─────────────────────────────────────────────────────────────────────────────+
|                     PRIMARY-STANDBY POSTGRESQL CLUSTER                      |
|  - Experiments, Runs, Metrics, Lineage Graph Tables (ACID Verified)         |
+─────────────────────────────────────────────────────────────────────────────+
```

---

### 7. Simple Example & Practical Example

#### A. Konsep Inti Pipeline Step & Experiment Tracking (Python Murni)
Contoh berikut mengilustrasikan mekanisme hashing deterministik dan pencatatan eksperimen tanpa framework eksternal yang kompleks.

```python
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict

@dataclass(frozen=True)
class PipelineStepMetadata:
    step_name: str
    code_hash: str
    input_hash: str
    params: Dict[str, Any]

    def compute_step_hash(self) -> str:
        serialized_params = json.dumps(self.params, sort_keys=True)
        payload = f"{self.step_name}:{self.code_hash}:{self.input_hash}:{serialized_params}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

# Simulasi Verifikasi Caching
step_1 = PipelineStepMetadata(
    step_name="feature_transformation",
    code_hash="c3ab41f9",
    input_hash="9f83a21e",
    params={"scaling": "minmax", "impute_strategy": "median"}
)

step_2_identical = PipelineStepMetadata(
    step_name="feature_transformation",
    code_hash="c3ab41f9",
    input_hash="9f83a21e",
    params={"impute_strategy": "median", "scaling": "minmax"}  # urutan berbeda
)

assert step_1.compute_step_hash() == step_2_identical.compute_step_hash()
print(f"[CACHE KEY] Deterministic Hash Generated: {step_1.compute_step_hash()}")
```

#### B. Implementasi Pipeline Modular Skala Industri (Production-Ready)
Berikut implementasi pipeline modular tingkat produksi yang mengintegrasikan Pydantic untuk validasi kontrak data, MLflow Tracking Client dengan *robust error handling*, koneksi context manager, dan artefak deterministik.

```python
"""
Modular Production Pipeline Engine dengan MLflow Tracking Terintegrasi.
Mendukung: Type validation, Artifact Versioning, dan Lineage Enforcement.
"""
from __future__ import annotations

import os
import sys
import logging
import hashlib
import tempfile
from pathlib import Path
from typing import Tuple, Dict, Any
from dataclasses import dataclass

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, PositiveInt
from sklearn.datasets import make_classification
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, f1_score
import mlflow
from mlflow.tracking import MlflowClient

# Setup Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("MLOpsPipelineEngine")

# --- 1. CONFIGURATION CONTRACTS & VALIDATION ---
class DataIngestionConfig(BaseModel):
    n_samples: PositiveInt = Field(default=10000, description="Jumlah data sintetis")
    n_features: PositiveInt = Field(default=20, description="Total fitur input")
    random_state: int = Field(default=42)

class TrainingConfig(BaseModel):
    n_estimators: PositiveInt = Field(default=100)
    learning_rate: float = Field(default=0.1, gt=0.0, le=1.0)
    max_depth: PositiveInt = Field(default=5)
    random_state: int = Field(default=42)

class PipelineRunConfig(BaseModel):
    experiment_name: str
    tracking_uri: str
    ingestion: DataIngestionConfig
    training: TrainingConfig

# --- 2. PIPELINE STEP ABSTRACTIONS ---
class DataIngestionStep:
    """Mengeksekusi ekstraksi dan validasi data mentah dengan hashing integrity."""
    
    @staticmethod
    def run(config: DataIngestionConfig) -> Tuple[pd.DataFrame, str]:
        logger.info("Mengeksekusi Data Ingestion...")
        X, y = make_classification(
            n_samples=config.n_samples,
            n_features=config.n_features,
            n_informative=int(config.n_features * 0.7),
            random_state=config.random_state
        )
        feature_cols = [f"feat_{i}" for i in range(config.n_features)]
        df = pd.DataFrame(X, columns=feature_cols)
        df["target"] = y
        
        # Hitung deterministik hash dari dataset
        data_bytes = pd.util.hash_pandas_object(df, index=True).values
        data_hash = hashlib.sha256(data_bytes).hexdigest()
        logger.info("Dataset berhasil di-generate. SHA256 Hash: %s", data_hash)
        return df, data_hash

class FeaturePreprocessingStep:
    """Transformasi fitur dengan segregasi dataset train/test yang ketat."""
    
    @staticmethod
    def run(df: pd.DataFrame, split_ratio: float = 0.8) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
        logger.info("Mengeksekusi Feature Preprocessing & Split...")
        split_idx = int(len(df) * split_ratio)
        train_df = df.iloc[:split_idx].copy()
        test_df = df.iloc[split_idx:].copy()
        
        metadata = {
            "train_rows": len(train_df),
            "test_rows": len(test_df),
            "split_ratio": split_ratio
        }
        return train_df, test_df, metadata

class ModelTrainingStep:
    """Pelatihan estimator dengan logging metrik mendalam ke backend metadata."""
    
    @staticmethod
    def run(
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        config: TrainingConfig
    ) -> Tuple[GradientBoostingClassifier, Dict[str, float]]:
        logger.info("Memulai Model Training...")
        X_train = train_df.drop(columns=["target"])
        y_train = train_df["target"]
        X_test = test_df.drop(columns=["target"])
        y_test = test_df["target"]
        
        model = GradientBoostingClassifier(
            n_estimators=config.n_estimators,
            learning_rate=config.learning_rate,
            max_depth=config.max_depth,
            random_state=config.random_state
        )
        
        model.fit(X_train, y_train)
        
        # Validasi Prediksi
        preds_proba = model.predict_proba(X_test)[:, 1]
        preds_binary = model.predict(X_test)
        
        metrics = {
            "roc_auc": float(roc_auc_score(y_test, preds_proba)),
            "f1_score": float(f1_score(y_test, preds_binary))
        }
        logger.info("Training selesai. ROC-AUC: %.4f | F1-Score: %.4f", metrics["roc_auc"], metrics["f1_score"])
        return model, metrics

# --- 3. PIPELINE ORCHESTRATOR ENGINE ---
class ProductionPipelineRunner:
    """Mengontrol urutan DAG, tracking lifecycle, dan penanganan artefak."""
    
    def __init__(self, config: PipelineRunConfig):
        self.cfg = config
        mlflow.set_tracking_uri(self.cfg.tracking_uri)
        mlflow.set_experiment(self.cfg.experiment_name)
        self.client = MlflowClient()

    def execute(self) -> str:
        with mlflow.start_run(run_name="enterprise-modular-execution") as active_run:
            run_id = active_run.info.run_id
            logger.info("Pipeline Run diinisiasi. Run ID: %s", run_id)
            
            # Catat Parameter Pipeline Lengkap
            mlflow.log_params({
                "ingestion_samples": self.cfg.ingestion.n_samples,
                "ingestion_features": self.cfg.ingestion.n_features,
                "training_n_estimators": self.cfg.training.n_estimators,
                "training_lr": self.cfg.training.learning_rate,
                "training_max_depth": self.cfg.training.max_depth
            })

            # Eksekusi Langkah 1: Ingestion
            df, data_hash = DataIngestionStep.run(self.cfg.ingestion)
            mlflow.set_tag("data.sha256", data_hash)

            # Eksekusi Langkah 2: Preprocessing
            train_df, test_df, prep_meta = FeaturePreprocessingStep.run(df)
            for k, v in prep_meta.items():
                mlflow.log_param(f"prep.{k}", v)

            # Eksekusi Langkah 3: Training & Evaluasi
            model, eval_metrics = ModelTrainingStep.run(train_df, test_df, self.cfg.training)
            for m_name, m_val in eval_metrics.items():
                mlflow.log_metric(m_name, m_val)

            # Eksekusi Langkah 4: Serialisasi & Log Artefak
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                
                # Simpan Dataset Manifest
                dataset_path = tmp_path / "dataset_summary.json"
                with open(dataset_path, "w") as f:
                    import json
                    json.dump({"hash": data_hash, "shape": list(df.shape)}, f)
                mlflow.log_artifact(str(dataset_path), artifact_path="dataset_lineage")
                
                # Simpan Model via Native Flavor
                mlflow.sklearn.log_model(
                    sk_model=model,
                    artifact_path="model",
                    registered_model_name="Production-GradientBoosting-Engine"
                )
                logger.info("Artefak model dan dataset manifest berhasil diunggah.")

            logger.info("Pipeline Run %s selesai dengan status SUCCESS.", run_id)
            return run_id

if __name__ == "__main__":
    # Inisialisasi Mock Config untuk testing eksekusi lokal
    pipeline_configuration = PipelineRunConfig(
        experiment_name="Fraud-Detection-Core",
        tracking_uri="file:///tmp/mlruns",  # Pada environment produksi: "http://mlflow-proxy.internal:5000"
        ingestion=DataIngestionConfig(n_samples=5000, n_features=15),
        training=TrainingConfig(n_estimators=50, learning_rate=0.05, max_depth=4)
    )

    runner = ProductionPipelineRunner(config=pipeline_configuration)
    completed_run_id = runner.execute()
    print(f"\n[EXECUTION COMPLETED] Verified Run Output ID: {completed_run_id}")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Dynamic Fraud Risk Engine di Lembaga Keuangan Multinasional Tier-1
* **Volume Beban Kerja**: 120 Model Regional (Asia Pasifik, EMEA, LATAM), dilatih ulang setiap 6 jam berdasarkan *sliding window* 30 miliar data stream transaksi per hari. Total eksekusi pipeline mencapai ~480 runs/hari dengan >1.500 parameter combinations.
* **Tantangan Infrastruktur**:
  - Tim data science lokal sering kali menimpa (*overwrite*) artefak model global.
  - Tracking server MLflow monolitik berbasis single instance SQLite runtuh saat diserang 200 concurrent write operations dari Kubernetes pods (Error: `database is locked`).
  - Ketidakmampuan melacak model versi X dilatih menggunakan slice data transaksi perbankan yang mana, memicu temuan audit dari Financial Regulatory Authority.
* **Arsitektur Solusi**:
  1. **Decoupled Orchestration**: Memigrasikan komputasi ke distributed ephemeral worker pods via Kubeflow Pipelines (KFP) pada AWS EKS.
  2. **High-Availability MLflow Cluster**:
     - 4 node stateless MLflow API Server di balik AWS Network Load Balancer (NLB).
     - Backend DB: Amazon Aurora PostgreSQL Serverless v2 Multi-AZ dengan PgBouncer untuk connection pooling (max connection 5.000).
     - Storage Backend: Amazon S3 dengan IAM Roles for Service Accounts (IRSA) dan *Short-lived Pre-signed URLs* via MLflow Proxy.
  3. **Strict Lineage Standard**: Setiap pipeline step membangkitkan OpenLineage manifest yang mengaitkan SHA-256 data slice Iceberg table, git commit hash, Docker digest, dan run ID.
* **Hasil Bisnis & Teknis**:
  - Waktu retraining berkurang 68% berkat caching langkah *Feature Extraction* yang mendeteksi data masukan yang tidak berubah.
  - Zero-data loss dan downtime 0% pada Tracking Server selama lonjakan beban transaksi akhir tahun.
  - Lulus audit regulasi perbankan dengan kemampuan mereproduksi output inferensi masa lalu hingga tingkat byte secara deterministik.

---

### 9. Trade-offs

Mengadopsi pola arsitektur modular dan tracking terpusat melibatkan trade-off teknis yang signifikan:

```
        Arsitektur Monolitik                             Arsitektur Terdistribusi Modular
   [Fast Prototyping, Low Overhead]                  [High Resilience, Deterministic, Cost]
                 │                                                    │
                 ▼                                                    ▼
   +----------------------------+                     +-------------------------------+
   | (+) Zero latency overhead  |                     | (+) Deterministic & Scalable  |
   | (+) Setup instan           |                     | (+) Enterprise Lineage        |
   | (-) Zero auditability      |                     | (-) Latency serialization     |
   | (-) Crash menghapus state  |                     | (-) Biaya & Kompleksitas Infra|
   +----------------------------+                     +-------------------------------+
```

| Dimensi Arsitektur | Pilihan A: Monolithic Script + Local File Tracking | Pilihan B: Ephemeral Distributed DAG + HA Central Tracking | Justifikasi Keputusan Enterprise |
| :--- | :--- | :--- | :--- |
| **Pipeline Latency** | **Sangat Rendah**: Zero network I/O; passing DataFrame terjadi via memory pointers. | **Lebih Tinggi**: Terdapat *serialization overhead* (Pickle/Parquet) dan transfer S3 antar-step (penambahan 1-5 menit). | Pilihan B diterima karena integritas sistem dan fault tolerance jauh lebih krusial dibandingkan latensi retraining offline. |
| **Operational Cost** | **Minimal**: Hanya membayar single VM besar yang menyala terus menerus. | **Efisien Dinamis namun Kompleks**: Biaya infrastruktur RDS PostgreSQL, S3 storage, K8s cluster management, dan NLB. | Pilihan B menghemat compute jangka panjang karena instance GPU hanya dialokasikan tepat saat training step berjalan (ephemeral). |
| **Lineage & Compliance** | **Tidak Ada**: Bergantung pada penamaan manual file `.pkl` oleh data engineer. | **Otomatis & Kriptografis**: Standard audit terjamin via DB schema dan S3 object versioning. | Mandatori untuk industri finansial, kesehatan, dan mission-critical applications. |
| **Maintenance Burden** | **Sangat Rendah Awalnya**, berkembang menjadi mimpi buruk teknis (*technical debt* eksponensial). | **Tinggi Sejak Hari Pertama**: Memerlukan keahlian Platform Engineer/MLOps Engineer berpengalaman. | Infrastruktur harus dibangun di awal untuk mencegah rewrite total sistem saat ukuran tim membengkak. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Data Leakage Lintas Step via Global State / File System Bersama
* **Gejala**: Evaluasi validasi lokal menghasilkan F1-Score 0.99, namun anjlok menjadi 0.54 saat dideploy ke staging.
* **Akar Masalah**: Transformasi fitur fit-transform (seperti `StandardScaler` atau target encoder) dieksekusi secara monolitik pada *seluruh dataset* sebelum step `train_test_split`, membocorkan distribusi data test ke training set.
* **Solusi**: Isolasi langkah `FeatureFitStep` hanya untuk membaca data partisi train. Simpan transformer yang telah di-fit sebagai artefak terpisah, kemudian muat transformer tersebut pada step inferensi validasi.

#### 2. Bottleneck: MLflow Backend DB Mengalami "Too Many Connections"
* **Gejala**: Worker training gagal serentak dengan error: `sqlalchemy.exc.OperationalError: FATAL: remaining connection slots are reserved for non-replication superuser connections`.
* **Akar Masalah**: Setiap distributed hyperparameter tuning worker (e.g., ratusan Ray workers atau Optuna trials) membuka direct connection pool ke PostgreSQL backend secara simultan.
* **Solusi**: Terapkan **PgBouncer** di depan PostgreSQL dengan mode *transaction pooling*, atau gunakan arsitektur MLflow Tracking Server yang membatasi direct connection hanya dari API service ke PostgreSQL, sementara compute worker berkomunikasi via stateless REST endpoint.

```
[Ray / Worker Pods] --(HTTP/REST)--> [MLflow Tracking Server] --(SQLAlchemy Pool: 20)--> [PgBouncer] ---> [PostgreSQL]
```

#### 3. Caching Invalid: Non-deterministic Step Execution
* **Gejala**: Pipeline selalu mengeksekusi ulang seluruh DAG meskipun kode, data, dan parameter tidak mengalami modifikasi sama sekali.
* **Akar Masalah**: Penggunaan non-deterministic input dalam step caching key, seperti timestamp saat run dimulai (`datetime.now()`), serialisasi dictionary tanpa *key sorting*, atau dependencies yang tidak dipin versinya.
* **Solusi**: Gunakan deterministic serializers (`json.dumps(obj, sort_keys=True)`), isolasi dependency menggunakan lockfile biner/digest, dan gunakan data hash sebagai base key kalkulasi cache.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum mempromosikan modular pipeline ke staging/production environment:

- [ ] **Contract-Driven Design**: Seluruh skema input dan output data frame/tensor pada tiap node divalidasi dengan runtime validation tools (Pydantic / Pandera).
- [ ] **Immutable Artifacts**: Seluruh artefak intermediate disimpan pada object storage dengan pola path immutability: `s3://<bucket>/<project>/<run_id>/<step_name>/<artifact_hash>/`.
- [ ] **No Direct Database Access**: Compute worker tidak boleh memiliki environment variable `DATABASE_URL` ke persistent store tracking. Hanya miliki `MLFLOW_TRACKING_URI` HTTP proxy.
- [ ] **Asynchronous Logging**: Metric interval logging (per epoch/step) dikonfigurasi menggunakan memory buffer atau batch logging untuk mengurangi latensi jaringan TCP socket overhead.
- [ ] **Deterministic Environment**: Base Docker image dipin menggunakan digest sha256 unik (`image@sha256:...`), bukan dynamic tags seperti `latest` atau `main`.
- [ ] **Graceful Exception Trapping**: Jika sebuah step gagal, context manager run tracking harus secara eksplisit menangkap exception, menandai run status sebagai `FAILED`, dan membuang temporary dangling files untuk menghindari S3 cost sprawl.
- [ ] **Sanitized Parameters**: Credential, API tokens, atau PII data disaring secara otomatis dari parameter logging dictionary sebelum dikirimkan ke tracking store.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sistem modular pipeline dan HA tracking backend secara komprehensif di workstation lokal Anda menggunakan Docker Compose, PostgreSQL, MinIO (S3-compatible), dan MLflow.

#### Struktur Direktori Hands-on
Simpan seluruh file berikut ke dalam path `hands-on/m02/`:
```text
hands-on/m02/
├── docker-compose.yml
├── requirements.txt
├── config.py
└── pipeline_runner.py
```

#### Langkah 1: Siapkan Konfigurasi Dependensi
Buat file `hands-on/m02/requirements.txt`:
```text
mlflow==2.11.3
psycopg2-binary==2.9.9
boto3==1.34.69
scikit-learn==1.4.1.post1
pandas==2.2.1
pydantic==2.6.4
```

#### Langkah 2: Buat Local Enterprise-like Infrastructure Stack
Buat file `hands-on/m02/docker-compose.yml` untuk memutar PostgreSQL, MinIO, dan MLflow Tracking Server yang terisolasi.

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: mlops-postgres
    environment:
      POSTGRES_USER: mlflow_user
      POSTGRES_PASSWORD: mlflow_secure_password
      POSTGRES_DB: mlflow_db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mlflow_user -d mlflow_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:RELEASE.2024-03-15T01-07-19Z
    container_name: mlops-minio
    environment:
      MINIO_ROOT_USER: minio_admin
      MINIO_ROOT_PASSWORD: minio_secure_password
    ports:
      - "9000:9000"
      - "9001:9001"
    command: server /data --console-address ":9001"
    volumes:
      - miniodata:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 5s
      retries: 5

  create-bucket:
    image: minio/mc:RELEASE.2024-03-14T00-09-36Z
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://minio:9000 minio_admin minio_secure_password;
      mc mb --ignore-existing local/mlops-bucket;
      exit 0;
      "

  mlflow-server:
    image: ghcr.io/mlflow/mlflow:v2.11.3
    container_name: mlops-mlflow-server
    depends_on:
      postgres:
        condition: service_healthy
      create-bucket:
        condition: service_completed_successfully
    environment:
      AWS_ACCESS_KEY_ID: minio_admin
      AWS_SECRET_ACCESS_KEY: minio_secure_password
      MLFLOW_S3_ENDPOINT_URL: http://minio:9000
    ports:
      - "5000:5000"
    command: >
      mlflow server
      --backend-store-uri postgresql://mlflow_user:mlflow_secure_password@postgres:5432/mlflow_db
      --default-artifact-root s3://mlops-bucket/artifacts
      --artifacts-destination s3://mlops-bucket/artifacts
      --host 0.0.0.0
      --port 5000
      --serve-artifacts

volumes:
  pgdata:
  miniodata:
```

#### Langkah 3: Jalankan Infrastruktur Lokal
Jalankan command berikut pada terminal di path `hands-on/m02/`:
```bash
docker compose up -d
```
Verifikasi bahwa seluruh service dalam kondisi running:
```bash
docker compose ps
```
Akses UI MinIO pada `http://localhost:9001` (User: `minio_admin`, Pass: `minio_secure_password`).
Akses UI MLflow pada `http://localhost:5000`.

#### Langkah 4: Buat Entrypoint Pipeline Berstandar Enterprise
Buat file `hands-on/m02/pipeline_runner.py`:

```python
import os
import sys
import logging
from typing import Tuple
import pandas as pd
from sklearn.datasets import load_diabetes
from sklearn.model_selection import train_test_split
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
import mlflow

# Konfigurasi Environtment Variables agar Pipeline Worker dapat berkomunikasi dengan MLflow Artifact Proxy
os.environ["MLFLOW_TRACKING_URI"] = "http://localhost:5000"
os.environ["MLFLOW_S3_ENDPOINT_URL"] = "http://localhost:9000"
os.environ["AWS_ACCESS_KEY_ID"] = "minio_admin"
os.environ["AWS_SECRET_ACCESS_KEY"] = "minio_secure_password"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HandsOnModularPipeline")

def step_data_ingestion() -> pd.DataFrame:
    logger.info("Step 1: Ingesting dataset...")
    diabetes = load_diabetes(as_frame=True)
    df = diabetes.frame
    return df

def step_feature_split(df: pd.DataFrame, test_size: float = 0.2) -> Tuple[pd.DataFrame, pd.DataFrame]:
    logger.info("Step 2: Splitting dataset...")
    train_df, test_df = train_test_split(df, test_size=test_size, random_state=42)
    return train_df, test_df

def step_train_evaluate(train_df: pd.DataFrame, test_df: pd.DataFrame, alpha: float) -> None:
    logger.info("Step 3: Training model & tracking artifacts...")
    X_train = train_df.drop(columns=["target"])
    y_train = train_df["target"]
    X_test = test_df.drop(columns=["target"])
    y_test = test_df["target"]

    model = Ridge(alpha=alpha)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mse = mean_squared_error(y_test, preds)
    r2 = r2_score(y_test, preds)

    # Tracking metrics & parameters
    mlflow.log_param("model_type", "Ridge")
    mlflow.log_param("alpha", alpha)
    mlflow.log_metric("mse", mse)
    mlflow.log_metric("r2", r2)

    # Logging Model langsung ke S3 Bucket via MLflow Proxy Server
    mlflow.sklearn.log_model(
        sk_model=model,
        artifact_path="model",
        registered_model_name="Diabetes-Ridge-Engine"
    )
    logger.info(f"Step 3 Complete. Alpha: {alpha} | MSE: {mse:.2f} | R2: {r2:.4f}")

def main():
    experiment_name = "Diabetes-Modular-Pipeline"
    mlflow.set_experiment(experiment_name)

    logger.info("Memulai eksekusi pipeline modular...")
    with mlflow.start_run(run_name="manual-modular-run") as run:
        df = step_data_ingestion()
        train_df, test_df = step_feature_split(df, test_size=0.25)
        step_train_evaluate(train_df, test_df, alpha=0.5)
        logger.info(f"Pipeline sukses dieksekusi. Artifacts & Run tercatat di Run ID: {run.info.run_id}")

if __name__ == "__main__":
    main()
```

#### Langkah 5: Eksekusi Pipeline
Instal dependensi lokal dan jalankan script:
```bash
pip install -r requirements.txt
python pipeline_runner.py
```
Buka browser Anda di `http://localhost:5000`. Verifikasi bahwa run telah tercatat di bawah experiment `Diabetes-Modular-Pipeline`, periksa parameter, metrik MSE/R2, dan pastikan artefak model `.bin`/pickle terunggah secara transparan ke bucket `mlops-bucket` di MinIO UI (`http://localhost:9001`).

---

### 13. Exercises

#### Level Easy
Tuliskan sebuah Python function decorator `@track_execution_time` yang dapat disematkan di atas setiap modular step. Decorator ini harus secara otomatis menghitung durasi eksekusi langkah (dalam detik) dan mencatat metrik tersebut ke MLflow menggunakan `mlflow.log_metric(f"{step_name}_duration_sec", duration)`.
*Kriteria Sukses*: Function wrapper mempertahankan signature asli dan metrik durasi berhasil muncul di UI MLflow.

#### Level Medium
Ubah script `pipeline_runner.py` pada Hands-on Practice untuk mendukung verifikasi schema input dan output pada `step_feature_split` menggunakan **Pandera** atau **Pydantic**.
*Kriteria Sukses*: Jika dataframe yang di-ingest kehilangan kolom `target` atau memiliki tipe data non-numeric, pipeline harus langsung *raise validation error*, menandai MLflow run status sebagai `FAILED`, dan tidak melanjutkan proses ke `step_train_evaluate`.

#### Level Hard
Rancang dan implementasikan sebuah class `DeterministicStepCacheManager` yang menerima:
1. Kode fungsi step (`callable`).
2. Input parameter (`dict`).
3. Dataset masukan (`pd.DataFrame`).

Class tersebut harus:
- Mengkalkulasikan hash SHA-256 dari kombinasi bytecode fungsi, parameter yang diurutkan, dan hash dataframe.
- Mengecek folder lokal `.cache/` apakah output dari hash tersebut sudah ada.
- Jika ada, kembalikan serialisasi data dari cache tanpa menjalankan callable. Jika tidak ada, jalankan callable, simpan output ke `.cache/<hash>.parquet`, dan catat status cache hit/miss sebagai tag di MLflow run.
*Kriteria Sukses*: Pipeline yang dijalankan dua kali berturut-turut dengan data dan parameter yang sama tidak boleh mengeksekusi komputasi pada pemanggilan kedua.

---

### 14. Challenge

#### Skenario: Arsitektur Zero-Downtime Data Lineage Migration di Multi-Cluster K8s
Perusahaan Anda memutuskan untuk memigrasikan backend tracking MLflow yang sebelumnya menggunakan arsitektur direct-to-S3 monolitik ke **Secure Artifact Proxy Architecture** dengan kontrol multi-region across AWS (`us-east-1` dan `ap-southeast-1`). Terdapat 2.500 active distributed worker nodes yang menjalankan training jobs secara parallel.

**Problem Statement yang Harus Anda Rancang Solusinya**:
1. **Zero-Downtime Database Schema Migration**: Bagaimana Anda melakukan migrasi skema tabel PostgreSQL MLflow (dari versi legacy 1.x ke versi 2.11+) yang memiliki total 40 juta baris metrik tanpa menghentikan proses *write* dari worker jobs yang sedang berlangsung?
2. **Deterministic Step Caching under Distributed Execution**: Rancang mekanisme distributed step caching ketika 100 worker container terisolasi berjalan di node Kubernetes berbeda tanpa *shared local disk*. Bagaimana para worker berbagi cache artifact secara aman tanpa menimbulkan *race condition* (dua worker memproses hash yang sama secara bersamaan)?
3. **Audit Trail & Provenance Constraint**: Rancang spesifikasi manifest JSON standar industri yang mengikat cryptographic hash dari data mentah, dependensi environment (`pip freeze`), script commit hash, dan model serializations yang kebal terhadap perubahan (*tamper-proof*), dan bagaimana data ini dapat divalidasi secara otomatis sebelum model dipromosikan ke tahap Registry `Staging` -> `Production`.

*Deliverable*: Dokumen desain arsitektur teknis lengkap (spesifikasi arsitektural, diagram aliran data ASCII, mitigasi risiko kegagalan concurency/deadlock, dan strategi *canary rollback*).

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic (Pilihan Ganda)
1. Apa fungsi utama pemisahan *Orchestration Plane* dan *Compute Plane* pada modular pipeline ML?
   - A. Menghapus kebutuhan menggunakan relational database.
   - B. Memastikan task orchestration dapat diskalakan secara independen dari beban kerja komputasi training.
   - C. Mempercepat eksekusi single-threaded Python script.
   - D. Menghilangkan kebutuhan serialisasi data antar-step.
   *Jawaban*: **B**. Decoupling memungkinkan orchestrator tetap ringan sementara worker compute dialokasikan secara dinamis sesuai kebutuhan resource (misal: GPU ephemeral instances).

2. Apa yang mendasari penentuan sebuah step pipeline dapat menggunakan *cached result* dari eksekusi sebelumnya?
   - A. Waktu eksekusi lokal yang sama.
   - B. Kesamaan nama run pada eksperimen.
   - C. Kecocokan cryptographic hash dari kode sumber, parameter, dan input data.
   - D. Jumlah baris data yang persis sama.
   *Jawaban*: **C**. Caching deterministik wajib memvalidasi invariansi kode, parameter konfigurasi, dan content fingerprint dari dataset masukan.

3. Apa resiko utama mencatat metrik training (seperti loss tiap batch iteration) secara synchronous per-step langsung ke PostgreSQL Tracking Server?
   - A. Merusak weight model di GPU.
   - B. Terjadinya connection pool exhaustion dan degradasi performa I/O database yang parah.
   - C. Dataset otomatis terhapus dari Object Storage.
   - D. Kehilangan data parameter global.
   *Jawaban*: **B**. Logging frekuensi tinggi secara langsung via sinkronus HTTP/DB write akan membuat database kehabisan koneksi dan memicu I/O lock pada tabel metrik.

4. Dalam konteks artifact storage, apa yang dimaksud dengan *Artifact Proxy Mode* pada MLflow?
   - A. Worker MLflow tidak diizinkan menyimpan model sama sekali.
   - B. Klien/Worker mengunggah artefak melalui Tracking Server atau presigned URL tanpa perlu memegang kredensial AWS/S3 langsung.
   - C. Server menyimpan seluruh model di dalam RAM memory.
   - D. Artefak dikonversi menjadi baris data di PostgreSQL.
   *Jawaban*: **B**. Ini menerapkan prinsip Zero-Trust IAM isolation di mana worker training tidak membutuhkan akses IAM storage credentials tingkat tinggi.

5. Format serialisasi data tabular apa yang paling direkomendasikan untuk passing state antar-step dalam modular pipeline berkinerja tinggi?
   - A. CSV
   - B. JSON
   - C. Apache Parquet
   - D. XML
   *Jawaban*: **C**. Parquet mengusung columnar storage yang terkompresi efisien, menjaga tipe data skema secara native, dan jauh lebih cepat dibaca/tulis dibanding text-based formats (CSV/JSON).

---

#### B. Intermediate (Pilihan Ganda & Analisis Pendek)
6. Manakah konfigurasi caching parameter yang benar-benar menjamin hasil hash yang sama di Python?
   - A. `hashlib.sha256(str(dict_params).encode())`
   - B. `hashlib.sha256(json.dumps(dict_params, sort_keys=True).encode())`
   - C. `hashlib.sha256(pickle.dumps(dict_params))`
   - D. `hashlib.md5(str(dict_params.values()).encode())`
   *Jawaban*: **B**. `json.dumps(..., sort_keys=True)` menjamin urutan serialization keys selalu konsisten, sedangkan `str(dict)` atau `pickle` bergantung pada variasi implementasi runtime dan urutan memory pointer.

7. Sebuah model dilatih pada pod K8s yang tiba-tiba terbunuh karena *OOMKilled* (Out Of Memory). Apa status MLflow Run jika tracking client tidak menggunakan proper lifecycle context manager?
   - A. Otomatis menjadi `FAILED`.
   - B. Menggantung selamanya pada status `RUNNING`.
   - C. Berubah menjadi `KILLED`.
   - D. Dihapus dari metadata store.
   *Jawaban*: **B**. Jika proses terbunuh seketika oleh kernel OS tanpa mengirimkan API status termination request ke tracking server, record di backend store akan tertahan pada status `RUNNING`.

8. Mengapa data leakage dapat terjadi jika imputation transformer (misal `SimpleImputer`) dieksekusi sebelum modul split dataset?
   - A. Parameter mean/median dari validation/test set ikut terhitung ke dalam baseline transformasi fitur train set.
   - B. Ukuran byte dataset berkurang drastis.
   - C. Nilai target label akan ter-impute secara acak.
   - D. Caching key pipeline menjadi tidak valid.
   *Jawaban*: **A**. Informasi statistik dari test set "bocor" (*information bleed*) ke data pelatihan, memberikan performa evaluasi yang palsu (*artificially high*).

9. Apa fungsi utama komponen `PgBouncer` yang diletakkan di antara MLflow Tracking Server dan PostgreSQL database?
   - A. Melakukan caching artefak model `.pkl`.
   - B. Mengenkripsi storage disk tingkat blok.
   - C. Mengelola dan me-multiplex ribuan koneksi stateless dari worker ke sejumlah kecil koneksi persisten database PostgreSQL.
   - D. Menggantikan peran S3 bucket.
   *Jawaban*: **C**. PgBouncer mencegah connection spike dan memory overload pada relational database saat worker cluster berskala besar mengeksekusi tracking calls serentak.

10. Jika hash kode pipeline Anda berubah karena penambahan komentar (*comment*) baru pada source code, bagaimana dampaknya terhadap deterministic cache engine modern?
    - A. Cache tetap digunakan karena fungsionalitas logika bytecode tidak berubah.
    - B. Cache hangus (*cache miss*) jika engine hanya mengevaluasi Git Commit SHA atau hash teks file mentah.
    - C. Sistem otomatis error dan membatalkan pipeline.
    - D. Tracking server menolak commit tersebut.
    *Jawaban*: **B**. Jika kalkulasi hash berbasis *file content text hash* atau *Git Tree SHA*, perubahan karakter non-eksekusional seperti komentar akan mengubah hash dan memicu invalidasi cache. (Mitigasi tingkat lanjut mengevaluasi Python AST / Bytecode hash).

---

#### C. Skenario Kasus Produksi (Analisis Arsitektur)
11. **Skenario 1**: Tim Anda meluncurkan batch retraining terdistribusi dengan 500 node serentak. Setelah 10 menit berjalan, dashboard MLflow menjadi tidak responsif (HTTP 504 Gateway Timeout), dan seluruh pod pelatihan mulai gagal dengan error koneksi timeout. Setelah dicek, CPU PostgreSQL berada pada level 100%. 
    *Pertanyaan Kasus*: Apa akar masalah arsitekturalnya dan 2 langkah mitigasi konkret apa yang harus diterapkan pada tracking plane?
    *Jawaban Evaluasi*:
    - **Akar Masalah**: Serangan *thundering herd* dari 500 node yang melakukan direct synchronous `log_metric` tanpa koneksi pooling dan query batching, menyebabkan connection saturation dan lock-contention pada PostgreSQL.
    - **Mitigasi 1**: Pasang *Connection Pooler* (misalnya PgBouncer) dan perbesar kapasitas pooling pada SQLAlchemy backend.
    - **Mitigasi 2**: Ubah strategi tracking client pada SDK worker untuk melakukan buffering metric lokal dalam memory queue, dan mengirimkannya dalam format batch request berkala (misal tiap 60 detik atau via flush on exit) menggunakan API asynchronous batch.

12. **Skenario 2**: Sebuah bank mendapati bahwa audit membuktikan salah satu model credit scoring di production menghasilkan keputusan yang tidak konsisten dengan run artifact di staging. Tim MLOps menyadari ada data scientist yang mengganti file `model.onnx` di S3 secara manual menggunakan script independen.
    *Pertanyaan Kasus*: Pola keamanan dan arsitektural apa yang dilanggar, dan bagaimana merekayasa ulang alur persistensi artefak agar kebal terhadap manipulasi manual (*immutable & audit-proof*)?
    *Jawaban Evaluasi*:
    - **Pelanggaran**: Kurangnya pembatasan akses data (*lack of least-privilege principle*) dan tidak diterapkannya pola *Object Immutability*.
    - **Solusi Rekayasa**:
      1. Aktifkan **S3 Object Lock** (Write Once, Read Many / WORM) dan aktifkan *S3 Bucket Versioning*.
      2. Cabut hak akses tulis S3 direct dari seluruh akun pengguna personal/IAM Data Scientist.
      3. Izinkan upload hanya melalui *MLflow Artifact Proxy* yang menggunakan IAM Role terisolasi (Service Account), yang secara otomatis memvalidasi checksum SHA-256 dan mencatat identitas eksekutor pipeline ke dalam database audit log.

13. **Skenario 3**: Data Engineer mengeluhkan bahwa pipeline modular memerlukan waktu total 45 menit untuk run, padahal proses training model hanya memakan waktu 3 menit. Sisa waktu 42 menit dihabiskan untuk membaca dan menulis data Parquet perantara (intermediate datasets) bolak-balik antara S3 dan container lokal pada setiap step dari total 12 step pipeline.
    *Pertanyaan Kasus*: Bagaimana mengoptimalkan arsitektur data transfer antar-step ini tanpa mengorbankan isolasi failure recovery?
    *Jawaban Evaluasi*:
    - **Optimasi Arsitektural**:
      1. **Step Consolidation**: Gabungkan langkah-langkah mikro yang memiliki coupling ketat dan overhead compute rendah ke dalam satu execution boundary container (misal: Data Cleaning dan Data Type Casting disatukan).
      2. **In-Memory / Shared Memory Transfer**: Jika dijalankan pada satu host / Kubernetes node yang sama, gunakan *Shared Memory IPC* (misalnya Apache Arrow Plasma store atau shared volume RAM `/dev/shm`) untuk membaca/menulis state tanpa serialize/deserialize Parquet ke jaringan S3.
      3. **Lazy Artifact Offloading**: Hanya unggah snapshot state ke remote S3 jika step tersebut didefinisikan sebagai *critical checkpoint* atau terjadi kegagalan (*checkpoint-on-failure*), sementara antar-step reguler menggunakan fast ephemeral streaming cache.

---

### 16. Summary

Modul ini telah mengupas secara mendalam fondasi arsitektur modular pipeline dan experiment tracking skala enterprise:

1. **Decoupled Architecture**: Pemisahan tegas antara Orchestration Plane (KFP/Kedro), Compute Plane (Worker pods), dan Metadata Tracking Plane (MLflow/Postgres/S3) adalah prasyarat mutlak untuk membangun sistem ML yang skalabel, aman, dan mudah di-maintain.
2. **Determinisme & Lineage**: Reproducibility sejati hanya dapat dicapai jika sistem mampu mengunci silsilah data: $\text{Code Hash} + \text{Data SHA256} + \text{Param Hash} \to \text{Artifact Hash}$. Hilangnya salah satu komponen akan menghancurkan rantai audit kepatuhan (*provenance chain*).
3. **Optimasi Performa & Ketahanan Infrastruktur**: Penulisan metrik ke backend store wajib mempertimbangkan beban I/O. Pemanfaatan connection pooler (PgBouncer), mode proxy artefak, dan mekanisme *content-addressed execution caching* merupakan pembeda antara sistem eksperimen kasual dan platform produksi kelas dunia.

Pada modul berikutnya, kita akan melangkah lebih jauh ke dalam **Automated Pipeline Orchestration & Continuous Training (CT)**, mendalami bagaimana pipeline modular ini diintegrasikan ke dalam trigger events berbasis data drift dan automated CI/CD deployment gates.