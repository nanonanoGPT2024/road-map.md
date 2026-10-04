# Bab 01: Fondasi MLOps & Rekayasa Sistem ML Produksi
## Module 01: Arsitektur Inti MLOps & Manajemen Technical Debt pada Sistem Berbasis ML

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Mendiagnosis** *Hidden Technical Debt* pada sistem berbasis *Machine Learning* berdasarkan taksonomi Sculley et al. menggunakan pemetaan batas subsistem (*system boundary mapping*).
- **Merancang** arsitektur *Machine Learning Operations* (MLOps) level L0 hingga L2 (sesuai spesifikasi Google Cloud MLOps maturity model) yang memisahkan *Data Plane*, *Control Plane*, dan *Metadata Plane*.
- **Mengimplementasikan** mekanisme deterministik untuk pelacakan silsilah data (*data lineage*), *artifact tracking*, dan reproduksibilitas model menggunakan kombinasi *cryptographic hashing* dan *immutable registry metadata schema*.
- **Mengevaluasi** risiko operasional akibat degradasi model (*data drift* dan *concept drift*) serta merumuskan SLA/SLO teknis untuk latensi inferensi, throughput evaluasi, dan integritas data.

---

### 2. Introduction & Concept

Secara historis, rekayasa perangkat lunak tradisional (*traditional software engineering*) berfokus pada dua dimensi utama: **Kode** dan **Logika Bisnis**. Jika kode ditulis secara deterministik dan lolos pengujian regresi, perilakunya dapat diprediksi di lingkungan produksi. 

Sistem *Machine Learning* (ML) memperkenalkan dimensi ketiga yang sangat dinamis: **Data**. Perilaku sistem ML di produksi tidak hanya ditentukan oleh kode yang dikompilasi, melainkan oleh fungsi parameter teroptimasi $f(x; \theta)$ yang diturunkan dari distribusi data pelatihan $P_{train}(X, Y)$. Akibatnya, sistem ML bersifat non-deterministik dan terikat erat pada perubahan kondisi dunia nyata (*real-world entropy*).

```
Traditional Software Engineering:
[ Code / Logic ] + [ Input Data ] = [ Computation Result ]

Machine Learning Systems:
[ Code / Algorithms ] + [ Training Data ] = [ Model Artifact (Parameters θ) ]
[ Model Artifact ]    + [ Production Data ] = [ Probabilistic Inference ]
```

**MLOps (Machine Learning Operations)** adalah disiplin rekayasa sistem yang menggabungkan prinsip *DevOps*, *Data Engineering*, dan *Machine Learning Engineering* untuk menstandarisasi siklus hidup sistem ML dari fase eksplorasi hingga penskalaan produksi secara andal, terukur, dan aman. 

MLOps **bukan** sekadar instalasi antarmuka eksperimen (seperti MLflow atau Weights & Biases), dan **bukan** otomasi penulisan skrip Jupyter Notebook via cron job. MLOps adalah rekayasa infrastruktur yang menjamin:
1. **Reproduksibilitas Penuh**: Kemampuan merekonstruksi artefak model yang identik hingga tingkat bit dari kombinasi snapshot data, kode sumber, dependensi lingkungan, dan seed stokastik.
2. **Observabilitas Berkelanjutan**: Telemetri data dan performa model (distribusi fitur, matriks konfusi, degradasi kalibrasi) secara *real-time*.
3. **Kontrak Data Terpadu**: Penegakan skema ketat (*strict schema enforcement*) pada setiap batas pertukaran data (*data boundary*) antar sistem.

---

### 3. Why It Matters

Kegagalan memperlakukan sistem ML sebagai sistem rekayasa perangkat lunak skala enterprise menyebabkan akumulasi **Hidden Technical Debt** yang eksponensial. Paper fundamental Google (*Sculley et al., 2015*) membuktikan bahwa kode ML murni hanya mencakup sekitar 5% dari total basis kode sistem ML produksi. Sisanya (95%) adalah infrastruktur pendukung: pengumpulan data, verifikasi fitur, alokasi sumber daya, pemantauan, dan manajemen metadata.

```
+-----------------------------------------------------------------------------------+
|               THE HIDDEN TECHNICAL DEBT OF MACHINE LEARNING SYSTEMS               |
|                                                                                   |
|  +--------------------+  +----------------------+  +---------------------------+  |
|  | Configuration      |  | Data Collection      |  | Feature Extraction        |  |
|  +--------------------+  +----------------------+  +---------------------------+  |
|  +--------------------+  +----------------------+  +---------------------------+  |
|  | Data Verification  |  |      [ ML CODE ]     |  | Metadata Management       |  |
|  +--------------------+  |        (~5-10%)      |  +---------------------------+  |
|  +--------------------+  +----------------------+  +---------------------------+  |
|  | Machine Resource   |  +----------------------+  | Monitoring & Alerting     |  |
|  | Management         |  | Serving Infrastructure| | Systems                   |  |
|  +--------------------+  +----------------------+  +---------------------------+  |
+-----------------------------------------------------------------------------------+
```

#### Dampak Kegagalan Tanpa MLOps:
1. **Silent Failures & Revenue Bleed**: Model tidak mengalami *crash* seperti layanan *backend* tradisional saat menghadapi masukan abnormal. Model tetap mengembalikan kode HTTP 200 OK dengan payload JSON valid, namun menghasilkan prediksi yang sepenuhnya salah akibat pergeseran distribusi kovariat (*covariate shift*).
2. **Entanglement (CACE Principle: Changing Anything Changes Everything)**: Dalam arsitektur fitur ML, modifikasi normalisasi pada Fitur $A$ secara tidak langsung merusak representasi konseptual dari Fitur $B$ sampai $Z$ yang terhubung melalui pembobotan gradien multi-layer, membatalkan seluruh proses validasi sebelumnya.
3. **Pipeline Jungles & Data Smells**: Pembersihan data ad-hoc menggunakan skrip shell atau notebook terisolasi menyebabkan skenario *training-serving skew*, di mana transformasi fitur waktu inferensi (*real-time inference*) berbeda secara numerik dari transformasi waktu pelatihan (*batch training*).

---

### 4. What: Core Principles & Theoretical Foundations

Arsitektur MLOps produksi bertumpu pada lima fondasi teoritis dan teknis:

#### 4.1. Contract-Driven Data Engineering
Data yang masuk ke pipeline ML harus diperlakukan sebagai antarmuka biner (*Application Binary Interface*). Kontrak data mendefinisikan tipe data statis, batas rentang nilai ($[x_{min}, x_{max}]$), ekspektasi distribusi (misal: divergensi Kullback-Leibler relatif terhadap data acuan), dan batas rasio nilai null ($NullRatio \le \epsilon$).

#### 4.2. Invarian Reproduksibilitas Deterministik
Sebuah model $\mathcal{M}$ pada versi $v$ didefinisikan secara formal sebagai fungsi determistik dari kuadrupel:
$$\mathcal{M}_v = \mathcal{F}(\mathcal{D}_{snapshot}, \mathcal{C}_{git}, \mathcal{E}_{env}, \mathcal{S}_{seed})$$

Di mana:
- $\mathcal{D}_{snapshot}$: Snapshot data ter-versi yang diidentifikasi oleh hash kriptografis (misal: SHA-256 Merkle root).
- $\mathcal{C}_{git}$: Commit hash unik repositori kode yang menjalankan pipeline pelatihan.
- $\mathcal{E}_{env}$: Digest *immutable container image* (misal: Docker image hash) yang mengunci dependensi C/CUDA dan runtime bahasa pemrograman.
- $\mathcal{S}_{seed}$: Seed generator pseudo-random numerik global.

Jika salah satu dari keempat elemen ini hilang atau diubah, reproduksibilitas model runtuh, menjadikan audit sistem mustahil dilakukan secara saintifik.

#### 4.3. Pemisahan Komputasi (Separation of Concerns across Planes)
- **Data Plane**: Jalur throughput tinggi yang memproses transfer data masukan, ekstraksi fitur, komputasi inferensi, dan logging streaming. Mengutamakan latensi rendah dan throughput I/O tinggi.
- **Control Plane**: Mengatur orkestrasi alur kerja (*DAG execution*), penjadwalan pelatihan ulang (*retraining triggers*), alokasi klaster komputasi dinamis, dan strategi deployment model (*canary*, *shadow*, *blue/green*).
- **Metadata Plane**: Basis data relasional atau graf terdistribusi yang menyimpan hubungan antar artefak, metrik eksperimen, silsilah data, skema validasi, dan log audit tata kelola secara *immutable*.

---

### 5. How It Works: Architectural Deep-Dive

Arsitektur MLOps modern terdiri dari beberapa subsistem terisolasi yang berkomunikasi melalui API kontrak ketat:

```
[Raw Data Sources]
       │
       ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│ DATA SUBSYSTEM (Data Ingestion & Feature Store)                                │
│ - Validation against Data Contract (Schema & Statistical Assertions)           │
│ - Feature Pipeline (Batch/Streaming) -> Offline Store (Parquet) & Online (Redis)│
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       │
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│ EXPERIMENTATION & TRAINING SUBSYSTEM                                           │
│ - Orchestrated by Pipeline Engine (Kubeflow / Argo Workflows)                  │
│ - Compute: Ephemeral GPU/CPU Pods                                              │
│ - Tracking: Hyperparameters, Metrics, Signatures to Metadata Store             │
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       │ Artifact Registration
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│ ARTIFACT & METADATA REGISTRY                                                   │
│ - Storage: S3/GCS Object Storage (Model Binaries, Tokenizers, Evaluators)       │
│ - Database: Metadata Ledger (Lineage Graph, Parent Hashes, Signatures)         │
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       │ Deployment Promotion Gate
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│ SERVING & INFERENCE SUBSYSTEM                                                  │
│ - Model Serving Cluster (Triton / TorchServe / vLLM)                           │
│ - Dynamic Shadow / Canary Router                                               │
│ - Low-Latency Feature Enrichment from Online Feature Store                     │
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       │
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│ OBSERVABILITY & DRIFT SUBSYSTEM                                                │
│ - Inference Telemetry Engine (Prediction Logs, Latency, Ingress Payloads)      │
│ - Statistical Drift Evaluator (PSI, KS-Test, Jensen-Shannon)                   │
│ - Feedback Loop: Retraining Alert Trigger to Control Plane                     │
└────────────────────────────────────────────────────────────────────────────────┘
```

#### Alur Eksekusi End-to-End:
1. **Ingesti Data & Pengecekan Kontrak**: Data mentah masuk ke pipeline via *event bus* atau *batch extraction*. Validator memeriksa integritas struktural dan statistik. Data yang melanggar kontrak dialirkan ke *Dead Letter Queue* (DLQ).
2. **Ekstraksi Fitur & Point-in-Time Correctness**: Fitur disimpan dalam *Feature Store*. *Offline store* (misal: Delta Lake/Iceberg) menjamin join data historis bebas kebocoran masa depan (*lookahead bias* / *data leakage*), sedangkan *online store* (misal: Redis) melayani fitur dengan latensi sub-milidetik.
3. **Orkestrasi Pelatihan**: Sistem kontrol memicu pod komputasi terisolasi. Pipeline menjalankan pelatihan deterministik, mengevaluasi model terhadap *holdout test set*, memverifikasi performa terhadap ambang batas batas bawah (*fairness* dan *accuracy baseline*), dan mengunggah artefak ke registry.
4. **Validasi Model Gate (Deployment Gating)**: Sebelum model dipromosikan ke tahap penyajian (*serving*), model harus melalui validasi otomatis: *stress-testing* throughput, analisis ketergantungan paket, dan *signature verification*.
5. **Penyajian & Telemetri**: Model disajikan dalam infrastruktur inferensi dengan *routing* pintar (*canary deployment*). Setiap prediksi, bersama fitur input dan skor probabilitas, dicatat secara asinkron ke antrian Kafka untuk dianalisis oleh monitor drift.

---

### 6. Architectural Diagram

Diagram ASCII berikut mengilustrasikan interaksi detail tingkat sistem antara komponen infrastruktur:

```
+------------------------------------------------------------------------------------------------------------------------------------+
|                                                  ENTERPRISE MLOps ARCHITECTURE                                                     |
+------------------------------------------------------------------------------------------------------------------------------------+

     DEVELOPMENT PLANE                           CONTINUOUS INTEGRATION / CONTINUOUS DELIVERY (CI/CD) PLANE
+-------------------------+             +-------------------------------------------------------------------------------+
|  Data Scientist / MLE   |             |                                                                               |
|  - Git Feature Branch   |             |  1. Linting & Static Code Analysis (Ruff, Mypy)                               |
|  - Local Notebooks/IDEs |────Push────>|  2. Unit Tests & Contract Integration Tests                                    |
|  - Micro-experiments    |             |  3. Build Immutable Execution Container (Docker Digest SHA)                   |
+-------------------------+             |  4. Trigger Continuous Training (CT) Pipeline Workflow                        |
                                        +---------------------------------------┬---------------------------------------+
                                                                                │
                                                                                ▼
 DATA & ARTIFACT REPOSITORY PLANE                                ORCHESTRATION & COMPUTATION ENGINE (DATA PLANE)
+------------------------------------+                  +---------------------------------------------------------------+
|  Data Lakehouse (Iceberg/S3)       |                  |  Workflow Engine (Argo Workflows / Kubeflow Pipelines)        |
|  - Immutable Versioned Partitions  |<──Pull Data──────|  ┌───────────────────┐    ┌─────────────────┐                 |
|  Feature Store (Feast/Hopsworks)   |                  |  | Extract & Validate|───>| Train & Tune    |                 |
|  - Point-in-time Engine            |──Fitur Matrix───>|  └───────────────────┘    └────────┬────────┘                 |
+------------------------------------+                  |                                    │                          |
|  Artifact Store (S3 Bucket)        |                  |                                    ▼                          |
|  - model.bin, tokenizer.json       |<──Store Model────|                           ┌─────────────────┐                 |
|  Metadata DB (PostgreSQL)          |                  |                           | Evaluate & Bias |                 |
|  - Schema, Params, Commit Hashes   |<──Store Lineage──|                           └────────┬────────┘                 |
+------------------------------------+                  +────────────────────────────────────┼──────────────────────────+
                                                                                             │ Pass Quality Gate
                                                                                             ▼
                                                        PRODUCTION SERVING & GOVERNANCE PLANE
                                                        +---------------------------------------------------------------+
                                                        |  Serving Pod (Triton / FastServe on K8s)                      |
                                                        |  ┌───────────────────┐    ┌─────────────────────────────────┐ |
+──────────────────+                                    |  | Ingress Proxy     |───>| Model Runtime Container         | |
| Client / API     |──────HTTPS Inference Call─────────>|  | (Envoy / Istio)   |    | (Loaded Model Artifact vX.Y)    | |
| Consumer         |<─────Predict JSON Response─────────|  └─────────┬─────────┘    └────────────────┬────────────────┘ |
+──────────────────+                                    +────────────┼───────────────────────────────┼──────────────────+
                                                                     │                               │
                                                        OBSERVABILITY│& TELEMETRY ENGINE            │
                                                        +────────────▼───────────────────────────────▼──────────────────+
                                                        | Kafka Streaming Topic (Inference Logs: Inputs + Predictions)  |
                                                        |                            │                                  |
                                                        |                            ▼                                  |
                                                        | Drift Detection Worker (Evidently / Alibi-Detect Daemon)      |
                                                        | - Kolmogorov-Smirnov Test (P-Value < 0.01)                     |
                                                        | - Population Stability Index (PSI > 0.25)                     |
                                                        |                            │ Drift Detected                   |
                                                        |                            ▼                                  |
                                                        | Alert Manager ──> Trigger Automated Retrain Pipeline Webhook  |
                                                        +---------------------------------------------------------------+
```

---

### 7. Minimal Implementation

Implementasi minimal ini mendemonstrasikan fondasi terpenting dari MLOps yang sering diabaikan: **pipeline deterministik, hashing silsilah data (*data lineage hashing*), validasi kontrak skema, dan serialisasi metadata secara atomik**. Script ini menggunakan library standar Python murni tanpa dependensi eksternal untuk memperlihatkan mekanika internalnya.

Simpan file ini sebagai `minimal_mlops_pipeline.py`:

```python
"""
Minimal Deterministic MLOps Execution Engine.
Mendemonstrasikan data lineage, tracking metadata, dan validasi kontrak tanpa framework eksternal.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class PipelineMetadata:
    pipeline_run_id: str
    timestamp_utc: str
    data_sha256: str
    code_signature: str
    hyperparameters: Dict[str, float]
    metrics: Dict[str, float]
    model_artifact_path: str


class DataValidationError(Exception):
    """Diangkat jika data mentah melanggar batasan kontrak skema."""
    pass


class MinimalMLOpsEngine:
    EXPECTED_SCHEMA = {"feature_1": float, "feature_2": float, "target": int}

    def __init__(self, run_id: str, data_path: str, output_dir: str):
        self.run_id = run_id
        self.data_path = data_path
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def compute_sha256(self, filepath: str) -> str:
        """Menghitung cryptographic digest dari dataset secara streaming."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def validate_and_extract(self) -> Tuple[List[List[float]], List[int]]:
        """Memverifikasi skema data dan tipe nilai secara deterministik."""
        features: List[List[float]] = []
        targets: List[int] = []

        with open(self.data_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None or set(reader.fieldnames) != set(self.EXPECTED_SCHEMA.keys()):
                raise DataValidationError(f"Inkonsistensi skema. Didapat: {reader.fieldnames}")

            for row_idx, row in enumerate(reader):
                try:
                    f1 = float(row["feature_1"])
                    f2 = float(row["feature_2"])
                    t = int(row["target"])
                    if t not in (0, 1):
                        raise ValueError(f"Target di luar batasan biner pada baris {row_idx}: {t}")
                    features.append([f1, f2])
                    targets.append(t)
                except ValueError as err:
                    raise DataValidationError(f"Parsing error pada baris {row_idx}: {err}") from err

        if not features:
            raise DataValidationError("Dataset kosong.")
        return features, targets

    def fit_binary_classifier(
        self, X: List[List[float]], y: List[int], lr: float, epochs: int
    ) -> Tuple[List[float], float, float]:
        """Pelatihan Logistic Regression sederhana via Stochastic Gradient Descent deterministik."""
        import math

        weights = [0.0, 0.0]
        bias = 0.0
        n_samples = len(X)

        for _ in range(epochs):
            for i in range(n_samples):
                # Linear combination
                z = weights[0] * X[i][0] + weights[1] * X[i][1] + bias
                # Numerically stable Sigmoid
                pred = 1.0 / (1.0 + math.exp(-z)) if z >= 0 else math.exp(z) / (1.0 + math.exp(z))
                error = pred - y[i]

                # Update gradients
                weights[0] -= lr * error * X[i][0]
                weights[1] -= lr * error * X[i][1]
                bias -= lr * error

        # Evaluasi akurasi
        correct = 0
        for i in range(n_samples):
            z = weights[0] * X[i][0] + weights[1] * X[i][1] + bias
            pred_class = 1 if z >= 0.0 else 0
            if pred_class == y[i]:
                correct += 1

        accuracy = correct / n_samples
        return weights, bias, accuracy

    def execute(self, lr: float = 0.1, epochs: int = 100) -> None:
        data_hash = self.compute_sha256(self.data_path)
        X, y = self.validate_and_extract()

        weights, bias, acc = self.fit_binary_classifier(X, y, lr, epochs)

        # Simpan artefak model
        model_payload = {"weights": weights, "bias": bias, "schema": list(self.EXPECTED_SCHEMA.keys())}
        model_filename = f"model_{self.run_id}.json"
        model_filepath = os.path.join(self.output_dir, model_filename)

        with open(model_filepath, "w", encoding="utf-8") as f:
            json.dump(model_payload, f, indent=2)

        # Simpan metadata run
        metadata = PipelineMetadata(
            pipeline_run_id=self.run_id,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            data_sha256=data_hash,
            code_signature="minimal-v1.0.0",
            hyperparameters={"learning_rate": lr, "epochs": float(epochs)},
            metrics={"train_accuracy": acc},
            model_artifact_path=model_filepath,
        )

        metadata_filepath = os.path.join(self.output_dir, f"metadata_{self.run_id}.json")
        with open(metadata_filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(metadata), f, indent=2)

        sys.stdout.write(f"Pipeline Selesai. Model disimpan di: {model_filepath}\n")
        sys.stdout.write(f"Metadata Hash: {data_hash} | Akurasi: {acc:.4f}\n")


if __name__ == "__main__":
    # Buat dataset contoh secara deterministik
    dummy_data = "feature_1,feature_2,target\n1.2,0.5,1\n-0.4,1.8,0\n0.9,0.2,1\n-1.2,-0.8,0\n"
    data_file = "synthetic_data.csv"
    with open(data_file, "w", encoding="utf-8") as file:
        file.write(dummy_data)

    engine = MinimalMLOpsEngine(run_id="run-local-001", data_path=data_file, output_dir="./mlops_runs")
    engine.execute(lr=0.05, epochs=50)

    # Bersihkan file CSV sementara
    if os.path.exists(data_file):
        os.remove(data_file)
```

---

### 8. Production-Grade Implementation

Implementasi industri berikut menggunakan arsitektur modular yang mematuhi standar desain perangkat lunak modern:
- **Pydantic V2** untuk penegakan kontrak validasi data yang ketat.
- Penanganan anomali data, *null handling*, dan *feature clamping*.
- Serialisasi artefak terkompresi dengan verifikasi checksum MD5/SHA-256.
- Pencatatan metadata audit lengkap dengan penanganan error terisolasi.

#### Struktur File:
```
mlops_production/
├── config.py
├── contracts.py
├── engine.py
└── run.py
```

#### File: `contracts.py`
```python
"""
Definisi Data Contract & Validasi Skema Model.
"""
from typing import Annotated, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


class RawFeatureRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_amount: Annotated[float, Field(ge=0.0, description="Nominal transaksi, non-negatif.")]
    account_age_days: Annotated[int, Field(ge=0, le=36500, description="Usia akun dalam hari.")]
    failed_login_attempts: Annotated[int, Field(ge=0, le=100, description="Jumlah kegagalan login.")]
    is_fraud: Annotated[int, Field(ge=0, le=1, description="Label target biner: 0 atau 1.")]

    @field_validator("transaction_amount")
    @classmethod
    def validate_finite(cls, v: float) -> float:
        import math
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Transaction amount harus merupakan nilai riil finit.")
        return v


class ModelMetadataSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    model_type: str
    dataset_checksum_sha256: str
    feature_names: List[str]
    metrics: Dict[str, float]
    parameters: Dict[str, Any]
    created_at_utc: str
    serialized_weights_sha256: str
```

#### File: `engine.py`
```python
"""
Core Engine: Pemrosesan Data Terisolasi, Pelatihan, dan Registrasi Artefak.
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Tuple
import numpy as np
from contracts import RawFeatureRecord, ModelMetadataSchema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MLOpsProductionEngine")


class ProductionTrainingPipeline:
    def __init__(self, run_id: str, artifact_store_dir: str):
        self.run_id = run_id
        self.artifact_dir = artifact_store_dir
        os.makedirs(self.artifact_dir, exist_ok=True)
        self.feature_names = ["transaction_amount", "account_age_days", "failed_login_attempts"]

    def compute_sha256(self, filepath: str) -> str:
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def load_and_validate(self, filepath: str) -> Tuple[np.ndarray, np.ndarray]:
        """Membaca data baris demi baris menggunakan kontrak Pydantic untuk mengeliminasi silent corruption."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Dataset path tidak ditemukan: {filepath}")

        valid_features: List[List[float]] = []
        valid_targets: List[int] = []

        rejected_rows = 0
        with open(filepath, "r", encoding="utf-8") as f:
            headers = f.readline().strip().split(",")
            for line_idx, line in enumerate(f, start=2):
                parts = line.strip().split(",")
                if len(parts) != len(headers):
                    rejected_rows += 1
                    continue

                try:
                    payload = dict(zip(headers, parts))
                    # Eksekusi Contract Check
                    validated = RawFeatureRecord(
                        transaction_amount=float(payload["transaction_amount"]),
                        account_age_days=int(payload["account_age_days"]),
                        failed_login_attempts=int(payload["failed_login_attempts"]),
                        is_fraud=int(payload["is_fraud"]),
                    )
                    valid_features.append([
                        validated.transaction_amount,
                        float(validated.account_age_days),
                        float(validated.failed_login_attempts),
                    ])
                    valid_targets.append(validated.is_fraud)
                except Exception as err:
                    rejected_rows += 1
                    logger.warning("Data contract violation pada baris %d: %s", line_idx, str(err))

        logger.info(
            "Validasi data tuntas. Records valid: %d | Records dibuang: %d",
            len(valid_features),
            rejected_rows,
        )

        if len(valid_features) == 0:
            raise ValueError("Zero valid rows survived contract validation. Pipeline aborted.")

        return np.array(valid_features, dtype=np.float64), np.array(valid_targets, dtype=np.int32)

    def train_stable_model(
        self, X: np.ndarray, y: np.ndarray, regularization: float = 1e-4, epochs: int = 1000, lr: float = 0.01
    ) -> Tuple[np.ndarray, float, float]:
        """Pelatihan Ridge-regularized Logistic Regression deterministik menggunakan NumPy murni."""
        np.random.seed(42)
        n_samples, n_features = X.shape

        # Standardisasi data (Zero mean, unit variance) untuk stabilitas numerik
        mean = np.mean(X, axis=0)
        std = np.std(X, axis=0)
        std[std == 0.0] = 1.0  # Mencegah division by zero
        X_norm = (X - mean) / std

        weights = np.zeros(n_features, dtype=np.float64)
        bias = 0.0

        for epoch in range(epochs):
            linear_output = np.dot(X_norm, weights) + bias
            # Numerically stable sigmoid: clip values untuk cegah under/overflow
            linear_output_clipped = np.clip(linear_output, -500, 500)
            predictions = 1.0 / (1.0 + np.exp(-linear_output_clipped))

            # Gradien
            errors = predictions - y
            grad_w = (np.dot(X_norm.T, errors) / n_samples) + (regularization * weights)
            grad_b = np.sum(errors) / n_samples

            # Updates
            weights -= lr * grad_w
            bias -= lr * grad_b

        # Hitung training loss (Binary Cross-Entropy)
        final_preds = 1.0 / (1.0 + np.exp(-np.clip(np.dot(X_norm, weights) + bias, -500, 500)))
        eps = 1e-15
        final_preds_clipped = np.clip(final_preds, eps, 1.0 - eps)
        loss = -np.mean(y * np.log(final_preds_clipped) + (1 - y) * np.log(1 - final_preds_clipped))

        preds_labels = (final_preds >= 0.5).astype(np.int32)
        accuracy = float(np.mean(preds_labels == y))

        logger.info("Pelatihan selesai. Loss: %.5f | Accuracy: %.4f", loss, accuracy)
        
        # Kemas bobot bersama metadata standarisasi agar runtime serving bersifat mandiri
        model_payload = {
            "weights": weights.tolist(),
            "bias": float(bias),
            "scaler_mean": mean.tolist(),
            "scaler_std": std.tolist(),
        }
        return model_payload, loss, accuracy

    def serialize_and_register(
        self, data_checksum: str, model_payload: dict, metrics: dict, params: dict
    ) -> str:
        """Serialisasi model dan metadata secara atomik dengan enkripsi hash."""
        # 1. Simpan Artefak Model
        model_filename = f"model_artifact_{self.run_id}.json"
        model_path = os.path.join(self.artifact_dir, model_filename)
        with open(model_path, "w", encoding="utf-8") as f:
            json.dump(model_payload, f, indent=2)

        model_checksum = self.compute_sha256(model_path)

        # 2. Simpan Skema Metadata
        metadata = ModelMetadataSchema(
            run_id=self.run_id,
            model_type="RidgeLogisticRegression_Numpy_V1",
            dataset_checksum_sha256=data_checksum,
            feature_names=self.feature_names,
            metrics=metrics,
            parameters=params,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            serialized_weights_sha256=model_checksum,
        )

        metadata_filename = f"metadata_{self.run_id}.json"
        metadata_path = os.path.join(self.artifact_dir, metadata_filename)
        with open(metadata_path, "w", encoding="utf-8") as f:
            f.write(metadata.model_dump_json(indent=2))

        logger.info("Artefak dan Metadata teregistrasi secara atomik di: %s", self.artifact_dir)
        return metadata_path
```

#### File: `run.py`
```python
"""
Eksekusi Pipeline Produksi dengan Penanganan Error dan Data Sintetis Skala Realistis.
"""
import os
import sys
import uuid
from engine import ProductionTrainingPipeline

def generate_production_mock_data(filepath: str, n_rows: int = 1000) -> None:
    import numpy as np
    np.random.seed(1337)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("transaction_amount,account_age_days,failed_login_attempts,is_fraud\n")
        for _ in range(n_rows):
            age = np.random.randint(1, 3000)
            failed_logins = np.random.poisson(lam=0.5)
            # Injeksi korelasi logis
            if failed_logins > 3:
                amount = float(np.random.uniform(500, 5000))
                fraud = 1 if np.random.rand() > 0.3 else 0
            else:
                amount = float(np.random.exponential(scale=50) + 1.0)
                fraud = 0
            
            f.write(f"{amount:.2f},{age},{failed_logins},{fraud}\n")
        # Injeksi baris anomali untuk menguji ketahanan schema validator
        f.write("-999.0,50,0,0\n")  # Amount negatif (melanggar ge=0.0)
        f.write("150.0,500,10,2\n")   # Target bernilai 2 (melanggar le=1)

if __name__ == "__main__":
    run_id = f"prod-run-{uuid.uuid4().hex[:8]}"
    data_file = "production_source.csv"
    artifacts_path = "./model_registry"

    try:
        generate_production_mock_data(data_file, n_rows=2000)
        pipeline = ProductionTrainingPipeline(run_id=run_id, artifact_store_dir=artifacts_path)

        # 1. Hashing Data Lineage
        data_checksum = pipeline.compute_sha256(data_file)
        
        # 2. Extract, Validate & Transform
        X, y = pipeline.load_and_validate(data_file)

        # 3. Model Training
        hyperparams = {"regularization": 0.001, "epochs": 500, "lr": 0.05}
        weights_dict, loss, acc = pipeline.train_stable_model(
            X, y, 
            regularization=hyperparams["regularization"],
            epochs=hyperparams["epochs"],
            lr=hyperparams["lr"]
        )

        # 4. Atomic Registration
        pipeline.serialize_and_register(
            data_checksum=data_checksum,
            model_payload=weights_dict,
            metrics={"train_loss": loss, "train_accuracy": acc},
            params=hyperparams
        )
        sys.stdout.write("PRODUKSI: Pipeline dieksekusi dengan sukses.\n")
    finally:
        if os.path.exists(data_file):
            os.remove(data_file)
```

---

### 9. Step-by-Step Implementation Guide

Ikuti instruksi bertahap berikut untuk menjalankan implementasi production-grade di lingkungan lokal:

1. **Persiapan Virtual Environment**:
   Pastikan Python 3.10 atau versi yang lebih baru telah terpasang.
   ```bash
   python -m venv venv
   source venv/bin/activate  # Di Linux/macOS
   # venv\Scripts\activate   # Di Windows PowerShell
   ```

2. **Instalasi Dependensi Minimum**:
   Instal hanya paket yang dibutuhkan untuk eksekusi script:
   ```bash
   pip install --upgrade pip
   pip install pydantic==2.6.4 numpy==1.26.4
   ```

3. **Inisialisasi Direktori Proyek**:
   Letakkan file `contracts.py`, `engine.py`, dan `run.py` pada satu direktori bernama `mlops_production`:
   ```bash
   mkdir mlops_production
   cd mlops_production
   # Buat file contracts.py, engine.py, dan run.py sesuai source code di Seksi 8
   ```

4. **Eksekusi Pipeline**:
   Jalankan file `run.py` melalui terminal:
   ```bash
   python run.py
   ```

5. **Verifikasi Output Registry**:
   Periksa direktori `./model_registry` yang terbuat secara otomatis. Harus terdapat dua file:
   - `model_artifact_prod-run-xxxxxxxx.json`
   - `metadata_prod-run-xxxxxxxx.json`

   Baca isi metadata untuk memverifikasi silsilah data:
   ```bash
   cat model_registry/metadata_*.json
   ```

---

### 10. Verification & Testing

Sistem MLOps mewajibkan pengujian pada tiga level: **Unit Testing Kontrak**, **Property-Based Testing Data**, dan **Validasi Deterministik Artefak**. 

Berikut suite pengujian menggunakan `pytest`:

```python
# test_mlops_pipeline.py
import pytest
import os
import json
import numpy as np
from pydantic import ValidationError
from contracts import RawFeatureRecord
from engine import ProductionTrainingPipeline

def test_contract_validation_rejects_negative_amounts():
    """Memastikan nilai nominal negatif diblokir pada layer kontrak."""
    with pytest.raises(ValidationError):
        RawFeatureRecord(
            transaction_amount=-15.0,
            account_age_days=10,
            failed_login_attempts=0,
            is_fraud=0
        )

def test_contract_validation_rejects_non_binary_targets():
    """Memastikan target non-biner tidak lolos validasi."""
    with pytest.raises(ValidationError):
        RawFeatureRecord(
            transaction_amount=100.0,
            account_age_days=10,
            failed_login_attempts=0,
            is_fraud=2  # Invalid: hanya 0 atau 1
        )

def test_pipeline_determinism(tmp_path):
    """Pengujian kritis: Menjalankan engine dengan seed dan data yang sama harus menghasilkan bobot yang identik (toleransi floating-point 1e-12)."""
    dir_a = tmp_path / "run_a"
    dir_b = tmp_path / "run_b"
    
    # Input data buatan
    X = np.array([[10.0, 100.0, 1.0], [500.0, 50.0, 4.0]], dtype=np.float64)
    y = np.array([0, 1], dtype=np.int32)
    
    pipe_a = ProductionTrainingPipeline("run-A", str(dir_a))
    pipe_b = ProductionTrainingPipeline("run-B", str(dir_b))
    
    weights_a, _, _ = pipe_a.train_stable_model(X, y, epochs=50, lr=0.01)
    weights_b, _, _ = pipe_b.train_stable_model(X, y, epochs=50, lr=0.01)
    
    # Assert bobot harus identik sampai batas presisi mesin
    np.testing.assert_allclose(weights_a["weights"], weights_b["weights"], rtol=1e-12)
    assert weights_a["bias"] == pytest.approx(weights_b["bias"], abs=1e-12)

def test_atomic_metadata_integrity(tmp_path):
    """Memastikan hash artefak yang tersimpan pada metadata cocok secara kriptografis dengan file artefak sebenarnya."""
    pipe = ProductionTrainingPipeline("run-audit", str(tmp_path))
    dummy_payload = {"weights": [0.1, -0.2], "bias": 0.5}
    
    meta_path = pipe.serialize_and_register(
        data_checksum="dummy-hash",
        model_payload=dummy_payload,
        metrics={"acc": 1.0},
        params={"lr": 0.01}
    )
    
    with open(meta_path, "r", encoding="utf-8") as f:
        meta_data = json.load(f)
        
    model_artifact_path = os.path.join(tmp_path, f"model_artifact_{meta_data['run_id']}.json")
    actual_hash = pipe.compute_sha256(model_artifact_path)
    
    assert meta_data["serialized_weights_sha256"] == actual_hash
```

Jalankan pengujian dengan perintah:
```bash
pip install pytest
pytest test_mlops_pipeline.py -v
```

---

### 11. Trade-offs & Engineering Decisions

Dalam merancang arsitektur sistem MLOps, insinyur dituntut mengambil keputusan arsitektural di bawah batasan *trade-off*:

```
Feature Transformation Trade-off Matrix:

       Batch (Offline) Transform                 Real-time (Online) Transform
  +-----------------------------------+     +-----------------------------------+
  | [+] Throughput sangat tinggi      |     | [+] Akses informasi instan        |
  | [+] Mampu agregasi jangka panjang |     | [+] Zero staleness                |
  | [-] Data stale (jeda sinkronisasi)|     | [-] Latensi serving meningkat     |
  | [-] Biaya komputasi terjadwal     |     | [-] Risiko Training-Serving skew  |
  +-----------------------------------+     +-----------------------------------+
```

#### Analisis Trade-offs Mendalam:

1. **Pre-computed Features vs. Dynamic On-the-fly Transformation**
   - *Pre-computed (Materialized di Online Store/Redis)*:
     - **Kelebihan**: Latensi pembacaan inferensi rendah ($< 2 \text{ ms}$). Beban komputasi inferensi ringan.
     - **Kekurangan**: Terikat oleh interval pembaruan (*staleness*). Jika pengguna baru saja melakukan transaksi sedetik lalu, fitur `count_transactions_last_1h` belum terbarui.
     - **Threshold Keputusan**: Pilih pre-computed jika komputasi fitur membutuhkan window agregasi kompleks ($> 10.000$ baris) dan model mentolerir latensi pembaruan fitur (misal: update per 5-15 menit).

2. **Immediate Retraining vs. Periodic Retraining Batch**
   - *Streaming/Immediate Online Learning*:
     - **Kelebihan**: Model langsung beradaptasi terhadap perubahan pola transaksi detik itu juga.
     - **Kekurangan**: Kerentanan catastrophic forgetting, drift akibat noise sesaat (*adversarial feedback loop*), dan verifikasi kepatuhan model menjadi sangat kompleks.
     - **Threshold Keputusan**: Standar enterprise mewajibkan periodic batch retraining (harian/mingguan) yang dipicu oleh drift threshold, bukan modifikasi bobot instan di production serving, kecuali untuk domain tertentu seperti recommendation engine feed.

3. **Strict Validation Gate vs. Fallback Imputation**
   - *Strict Contract Drop (Membuang baris anomali)*:
     - **Kelebihan**: Menjamin bobot gradien tidak terkontaminasi nilai outlier ekstrem.
     - **Kekurangan**: Potensi hilangnya sampel berharga saat terjadi pergeseran domain yang sah.
     - **Threshold Keputusan**: Tolak/Drop data jika data corruption terjadi pada field target biner atau fitur identitas kunci. Lakukan median-imputation hanya pada data continuous numerik sekunder dengan batasan mask flag ($IsImputed = 1$).

---

### 12. Common Failure Modes & Anti-Patterns

Berikut adalah analisis post-mortem dari kegagalan arsitektur MLOps yang umum terjadi di lingkungan produksi:

| Anti-Pattern | Root Cause Mekanikal | Gejala Produksi | Arsitektur Solusi (Fix) |
| :--- | :--- | :--- | :--- |
| **Notebook-as-Service** | Kode eksperimen di Jupyter Notebook diekspor langsung ke container microservice via wrapper Flask. | *Deadlock* pada multi-threading, dependensi liar yang tidak terdokumentasi, leak memori akibat variabel global tertahan. | Ekstraksi logika notebook ke modul Python terpisah (`src/`), audit dependensi menggunakan `poetry.lock`, pengujian unit modular minimum 80% coverage. |
| **Training-Serving Skew** | Fitur normalisasi dihitung menggunakan `pandas` saat training, namun ditulis ulang menggunakan `JavaScript/Go` di API gateway saat runtime. | Deviasi numerik presisi pecahan (misal: epsilon pembagi berbeda), akurasi model anjlok drastis di produksi tanpa error sistem. | Gunakan artefak transformasi tunggal yang diserialisasi (misal: ONNX pipeline atau shared C++ dynamic library) yang dipakai bersama oleh layer training dan serving. |
| **Silent Covariate Drift** | Distribusi input $P(X)$ berubah drastis akibat pembaruan OS pada aplikasi client, namun label target $Y$ tertunda kedatangannya berbulan-bulan. | Metrik sistem (CPU, latency, status 200 OK) terlihat normal, namun prediksi bisnis salah total (kerugian finansial senyap). | Implementasikan streaming computation untuk mengukur *Population Stability Index (PSI)* atau uji divergensi *Wasserstein* pada request payload terhadap baseline training. |
| **Pipeline Jungle** | Rangkaian skrip bash dan cron job mengaitkan transfer file CSV mentah dari server ke server tanpa tracking status atomik. | File yang ditransfer terpotong (*truncated read*), pipeline training berjalan pada data parsial, model kehilangan performa. | Ganti cron job ad-hoc dengan Directed Acyclic Graph (DAG) orchestrator yang bersifat deklaratif dan transactional (misal: Argo Workflows, Airflow, Temporal). |

---

### 13. Performance, Scalability & Resource Optimization

Mengoperasikan sistem MLOps pada throughput tinggi membutuhkan kontrol mendalam pada alokasi sumber daya komputasi dan transfer data.

#### Karakteristik Bottleneck Utama:
- **Pelatihan Terdistribusi**: Bottleneck biasanya bergeser dari kapasitas komputasi GPU (FLOPs) ke latensi bandwidth interkoneksi (*Network I/O*) saat sinkronisasi parameter gradien via *AllReduce*.
- **High-Throughput Serving**: Bottleneck berpusat pada deserialisasi payload JSON dan transfer array NumPy ke CUDA memory (*host-to-device memory copy latency*).

#### Strategi Optimalisasi:

1. **Pemanfaatan Memory-Mapped File Formats**:
   Hindari membaca dataset pelatihan format CSV atau JSON baris demi baris di memori. Gunakan format biner terindeks kolom seperti **Apache Parquet** atau **Apache Arrow**.
   
   $$\text{I/O Latency Gain} \approx \frac{\text{Size}_{CSV} \times \text{ParsingCost}_{CPU}}{\text{Size}_{Parquet} \times \text{ZeroCopyCost}_{Arrow}}$$
   
   Arrow memungkinkan akses *zero-copy deserialization*, memotong utilisasi CPU hingga 70% dan menghilangkan beban garbage collection memory overhead.

2. **Model Serving Concurrency & Dynamic Batching**:
   Model inference engine murni single-thread akan mengunci proses. Gunakan multi-worker inference server (seperti Triton Inference Server) yang mendukung **Dynamic Server Batching**.

```
Single Request Arrivals:
t0: Request A (batch size 1) ──┐
t1: Request B (batch size 1) ──┼──> Dynamic Batcher (Window 5ms) ──> Single GPU Kernel Launch
t2: Request C (batch size 1) ──┘                                      (Batch Size 3 - High Saturation)
```

Dengan mengumpulkan request yang tiba dalam rentang waktu singkat (misal: $5\text{ ms}$), GPU Core dieksekusi pada saturasi tensor optimal, meningkatkan throughput total hingga $400-800\%$ tanpa melanggar SLO latensi tail (p99).

---

### 14. Security, Compliance & Governance

Sistem ML bukan sekadar aplikasi web; model ML bertindak sebagai *black-box logic store* yang rentan terhadap vektor serangan baru:

#### 14.1. Vektor Kerentanan Spesifik ML
- **Model Inversion & Membership Inference Attacks**: Penyerang mengirimkan kueri berulang pada endpoint API inferensi untuk mengekstrak data sensitif (PII) yang dihafal (*overfitted*) oleh model selama fase pelatihan.
- **Data Poisoning**: Injeksi terencana sejumlah data jahat (*malicious rows*) ke dalam data training publik untuk membuka pintu belakang (*backdoor*) klasifikasi tersembunyi.
- **Deserialization Exploits**: File bobot model tradisional seperti `pickle` dalam Python dapat mengeksekusi *arbitrary system shell commands* saat dijalankan via `pickle.load()`.

#### 14.2. Arsitektur Pertahanan & Kepatuhan
1. **Model Serialization Hardening**:
   - **Larang penggunaan `.pkl` atau `.pickle` di seluruh lingkungan produksi.**
   - Gunakan format serialisasi yang secara inheren aman dan terisolasi dari kode eksekusi, seperti **Safetensors** (Rust-backed memory map format) atau **ONNX**.
2. **Kriptografi & Audit Silsilah (Lineage Cryptographic Ledger)**:
   - Setiap model yang dipromosikan ke klaster produksi wajib diverifikasi integritasnya menggunakan public-key infrastructure (PKI) code-signing (misal: Cosign/Sigstore).
   - Terapkan metadata hash SHA-256 yang mengikat artefak ke dataset ID yang telah divalidasi.
3. **Data Governance & PII Redaction**:
   - Data pipeline wajib menerapkan hashing anonymization (misal: SHA-256 dengan per-app cryptographic salt) pada seluruh atribut PII (nama, email, nomor identitas) sebelum data mendarat di *Data Lakehouse* pelatihan.

---

### 15. Operational Playbook

Ketika terjadi anomali produksi, Operator MLOps harus mengikuti prosedur penanganan insiden standar berikut:

#### Metrik Kritis Alerting (SLI/SLO):
- **SLO Latensi**: 99% request diselesaikan dalam $< 50\text{ ms}$ (p99).
- **SLO Availability**: $99.95\%$ kueri menghasilkan kode status HTTP 200.
- **SLI Model Data Drift**: *Population Stability Index* (PSI) pada jendela geser 1 jam $\le 0.20$.
- **SLI Output Deviation**: Deviasi proporsi klasifikasi target terhadap rata-rata mingguan $\le 10\%$.

#### Incident Triage Matrix:

```
[ALERT: PSI Model Drift > 0.25 (Critical)]
                   │
                   ▼
       Cek Health Data Ingress Proxy
                   │
    ┌──────────────┴──────────────┐
    ▼ (Format Data Rusak)         ▼ (Format Data Normal)
[Payload Corrupted]       [Pergeseran Perilaku Dunia Nyata]
    │                             │
    ├─ Isolasi Ingress traffic    ├─ Beralih ke Safe Heuristic/Shadow Model
    ├─ Aktifkan Rule DLQ          ├─ Validasi Label Baru (Ground Truth Delay)
    └─ Investigasi upstream ETL   └─ Trigger Manual CT Pipeline dengan Retraining Gate
```

#### Runbook: Rollback Model Cepat (Emergency Procedure)
Jika model baru yang di-deploy menunjukkan lonjakan error inferensi atau performa bisnis drop seketika:

1. **Alihkan Lalu Lintas ke Versi Sebelumnya via Ingress Routing**:
   Jangan melakukan deploy ulang container. Ubah konfigurasi routing proxy (misal: Istio VirtualService):
   ```bash
   # Contoh penyesuaian weight routing darurat ke model v1 (fallback)
   kubectl patch virtualservice inference-service-router -n ml-serving --type merge -p \
     '{"spec":{"http":[{"route":[{"destination":{"host":"model-v1-service"},"weight":100},{"destination":{"host":"model-v2-service"},"weight":0}]}]}}'
   ```
2. **Karantina Versi Model yang Bermasalah**:
   Ubah status model di Metadata Registry dari `Production` menjadi `Quarantined`.
3. **Dump Inference Payload Log**:
   Tarik $1.000$ sampel request terakhir dari Kafka inference streaming topic untuk isolasi masalah di staging/debugging cluster.

---

### 16. Best Practices

Gunakan daftar checklist teknis ini untuk memastikan kepatuhan standar MLOps industri:

#### Arsitektur & Pipeline
- [ ] Pisahkan dependensi kode data ingestion dari kode pelatihan model.
- [ ] Simpan seluruh artefak (bobot, visualisasi evaluasi, tokenizer) di Object Storage yang memiliki status *immutable* / *write-once-read-many* (WORM).
- [ ] Tidak ada akses internet terbuka (*outbound public internet*) dari worker node komputasi pelatihan model di klaster produksi.

#### Mutu Kode & Validasi
- [ ] Hilangkan variabel acak yang tidak terkontrol: Pasang global seed (`torch.manual_seed`, `np.random.seed`) secara eksplisit di awal eksekusi.
- [ ] Terapkan kontrak validasi skema statis pada seluruh interface data masukan menggunakan tools seperti Pydantic atau Great Expectations.
- [ ] Pastikan seluruh transformasi inferensi dibundel ke dalam objek artefak model atau dipanggil dari shared library yang sama untuk mencegah *training-serving skew*.

#### Operasional & Monitoring
- [ ] Aktifkan pencatatan request-response log asinkron ke message broker tanpa membebani latensi endpoint inferensi utama.
- [ ] Tentukan ambang batas minimum metrik baseline (*quality gate*) yang harus dipenuhi secara otomatis sebelum model dipromosikan ke tahap staging.
- [ ] Siapkan *circuit-breaker* atau *fallback rule-based logic* jika layanan model inferensi mengalami degradasi performa atau timeout.

---

### 17. Concrete Tooling Ecosystem

Lanskap MLOps modern terdiri dari tool modular yang saling melengkapi di berbagai layer sistem:

```
+---------------------------------------------------------------------------------------+
| LAYER                   | OPEN-SOURCE STANDARDS           | CLOUD NATIVE / MANAGED    |
+-------------------------+---------------------------------+---------------------------+
| Pipeline Orchestration  | Argo Workflows, Kubeflow,       | AWS Step Functions,       |
|                         | Flyte, Airflow                  | GCP Vertex Pipelines      |
+-------------------------+---------------------------------+---------------------------+
| Metadata & Artifacts    | MLflow Tracking, DVC,           | Weights & Biases,         |
|                         | ClearML                         | Neptune.ai                |
+-------------------------+---------------------------------+---------------------------+
| Feature Store           | Feast, Hopsworks                | AWS SageMaker FeatureStore|
|                         |                                 | Databricks Feature Store  |
+-------------------------+---------------------------------+---------------------------+
| Model Serving Engine    | Triton Inference Server,        | AWS SageMaker Endpoints,  |
|                         | TorchServe, vLLM, Seldon Core   | Google Cloud Vertex Endp. |
+-------------------------+---------------------------------+---------------------------+
| Observability & Drift   | Evidently AI, Alibi Detect,     | Arize AI, Fiddler,        |
|                         | Prometheus + Grafana            | Datadog ML Metrics        |
+-------------------------+---------------------------------+---------------------------+
```

---

### 18. Real-World Case Study

#### FinSecure Bank: Resolusi Kasus Kegagalan Training-Serving Skew pada Deteksi Fraud

- **Latar Belakang**: 
  FinSecure Bank mengoperasikan model klasifikasi gradient-boosted tree untuk mendeteksi transaksi kartu kredit mencurigakan bernilai total $80 juta USD per hari.
  
- **Insiden**: 
  Setelah rilis model versi baru (v2.4), akurasi deteksi fraud menurun drastis sebesar 35% di produksi, mengakibatkan kerugian finansial senilai $420.000 USD dalam 48 jam pertama. Padahal saat proses validasi offline, model v2.4 mencatat skor PR-AUC impresif sebesar 0.94.

- **Investigasi Akar Masalah (Root Cause Analysis)**:
  Tim Data Science menggunakan library Python `pandas` untuk menghitung rasio agregasi transaksi:
  ```python
  # Kode pada Batch Training (Offline)
  df['amt_to_avg_ratio'] = df['amount'] / (df.groupby('user_id')['amount'].transform('mean') + 1e-5)
  ```
  Namun, pada layer API Serving (C++ microservice), tim backend mengimplementasikan transformasi fitur secara independen menggunakan rolling window Redis tanpa memperhitungkan transaksi saat ini (`amount` saat ini tidak dimasukkan ke dalam komponen denominator rata-rata). Hal ini menghasilkan diskrepansi numerik skala kecil yang memicu prediksi bernilai false negative pada model pohon keputusan (*tree-split thresholds* meleset secara seragam).

- **Arsitektur Solusi & Remediasi**:
  1. Menghapus reimplementasi fitur manual pada microservice serving.
  2. Mengadopsi arsitektur **Feature Store (Feast)** untuk menyatukan definisi komputasi fitur offline dan online ke dalam single definition file (Python DSL).
  3. Membangun pengujian otomatis CI/CD menggunakan *shadow deployment*: Semua model baru wajib menerima 100% lalu lintas transaksi produksi riil secara pasif (tanpa mengembalikan respons ke user) selama 24 jam untuk membandingkan output prediksi v2.4 terhadap baseline v2.3.

- **Hasil Metrik**:
  - Training-serving feature skew turun menjadi $0.000\%$.
  - Deteksi anomali fraud berhasil dinaikkan 41% relatif terhadap model warisan.
  - Deployment cycle dipercepat dari 3 minggu menjadi 2 hari kerja dengan tingkat keandalan yang terjamin.

---

### 19. Exercises & Hands-on Projects

Kerjakan tiga tugas berjenjang ini untuk menguji dan memperdalam pemahaman praktis Anda:

#### Proyek A (Tingkat Pemula): Verifikasi Integritas Dataset Berbasis Hash
- **Tugas**: Buat script Python standalone yang memindai direktori berisikan file Parquet/CSV. Script harus menghasilkan satu string hash SHA-256 tunggal (Merkle root style) yang merepresentasikan status absolut dari seluruh kumpulan file tersebut. Jika salah satu baris di salah satu file diubah, hash akhir harus berubah.
- **Batasan**: Eksekusi harus bersifat memory-efficient (tidak memuat seluruh file berukuran gigabyte ke memori secara langsung).

#### Proyek B (Tingkat Menengah): Pipeline Kontrak Validasi Otomatis
- **Tugas**: Kembangkan sistem validasi schema ingestor menggunakan library Python pilihan Anda (Pydantic atau Cerberus). Pipeline harus membaca dataset streaming event JSON palsu, memvalidasi tipe dan boundary numerik, kemudian mendistribusikan data secara terpisah: data valid dikompilasi ke file Parquet target, sedangkan data yang melanggar kontrak dialirkan ke dead-letter file JSON bersama pesan error spesifiknya.

#### Proyek C (Tingkat Lanjut): Mock Shadow Deployment Pipeline Engine
- **Tugas**: Bangun layanan REST API (menggunakan FastAPI atau standard library) yang mengimplementasikan arsitektur *Shadow Deployment Router*.
- **Spesifikasi**:
  1. Endpoint `/predict` menerima request payload.
  2. Router memanggil **Model Primer (v1)** dan mengembalikan responsnya ke pemanggil dengan latensi $< 20\text{ ms}$.
  3. Router memanggil **Model Bayangan (v2)** secara asinkron (*non-blocking* via thread-pool atau async task) dengan payload yang identik.
  4. Selisih numerik antara prediksi Model v1 dan Model v2 dicatat ke log telemetri lokal untuk keperluan analisis drift.

---

### 20. Conclusion & Strategic Next Steps

Pada modul ini, kita telah membongkar mitos bahwa sistem Machine Learning hanya berfokus pada pelatihan model semata. Kita telah mengeksplorasi secara mendalam konsep **Hidden Technical Debt**, mendesain pemisahan subsistem antara **Data Plane**, **Control Plane**, dan **Metadata Plane**, serta mengimplementasikan pipeline deterministik yang tahan terhadap kerusakan data struktural melalui penegakan **Data Contract**.

Arsitektur MLOps yang kokoh adalah prasyarat mutlak sebelum organisasi dapat melangkah lebih jauh ke ranah otomatisasi tingkat tinggi. Tanpa pelacakan metadata yang ketat dan jaminan reproduksibilitas, otomasi pelatihan ulang model hanya akan mempercepat penyebaran bug ke seluruh ekosistem komputasi Anda.

Di **Modul 02: Tracking Eksperimen, Versioning Data, & Reproduksibilitas Skala Penuh**, kita akan membedah internal teknis dari sistem pelacakan eksperimen terdistribusi, memanipulasi *Directed Acyclic Graph* (DAG) untuk kontrol silsilah data, serta mengimplementasikan versioning data skala terabyte menggunakan engine *Data Version Control* (DVC) dan backend *Object Storage*.