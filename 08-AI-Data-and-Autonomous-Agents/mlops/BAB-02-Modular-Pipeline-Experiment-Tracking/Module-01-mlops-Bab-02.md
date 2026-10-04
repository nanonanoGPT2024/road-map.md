# Bab 02: Modular Pipeline & Experiment Tracking (Module 01)

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang (Design)** arsitektur pipeline machine learning yang modular, *loosely-coupled*, dan mengadopsi prinsip *Separation of Concerns* (SoC) serta *Single Responsibility Principle* (SRP).
- **Mengimplementasikan (Implement)** *Experiment Tracking* dan *Metadata Management* secara terpusat menggunakan MLflow API dengan arsitektur backend penyimpanan terdistribusi (SQL DB + Object Storage).
- **Membangun (Construct)** abstraksi kontrak data (*data contracts*) antar-tahap pipeline guna menjamin determinisme, *idempotency*, dan kemudahan *unit testing*.
- **Menganalisis (Analyze)** *lineage* artefak, parameter, metrik, dan dependensi lingkungan untuk memfasilitasi *end-to-end auditability* dan reproduktifitas model ML pada skala *enterprise*.
- **Menangani (Handle)** *failure modes* kritis seperti *schema drift*, kegagalan parsial pada pipeline eksekusi (*partial failure recovery*), dan degradasi konektivitas ke *tracking server*.

---

## 2. Concept Overview

Dalam rekayasa sistem Machine Learning modern (MLOps), transisi dari fase eksplorasi (*Jupyter Notebooks*) ke fase produksi menuntut pergeseran paradigma dari eksekusi *monolithic-imperative* menuju *modular-declarative execution*.

```
[ Monolithic Anti-Pattern ]
Raw Data ---> [ 2000-line script: clean + train + eval ] ---> model.pkl (?)
              (Unversioned, Non-reproducible, High State Coupling)

[ Modular DAG Architecture ]
Raw Data ---> [ Step 1: Ingest ]   ===> Validated Data
                     |
                     v
              [ Step 2: Transform] ===> Engineered Features (Versioned)
                     |
                     v
              [ Step 3: Train ]    ===> Model Checkpoint (Trained on Git SHA + Data Hash)
                     |
                     v
              [ Step 4: Evaluate]  ===> Metrics Evaluation & Gate Registry
```

### Mental Model: Pipeline sebagai Directed Acyclic Graph (DAG)
Modular pipeline memecah alur kerja ML menjadi serangkaian *node* independen (*Steps*/*Components*). Setiap *node*:
1. Memiliki input dan output bertipe ketat (*strictly typed contracts*).
2. Bersifat *idempotent*: Eksekusi dengan input yang identik selalu menghasilkan output yang identik (menghilangkan *side-effects*).
3. Terisolasi secara komputasi: State antar-node tidak dibagikan via *global memory*, melainkan dialirkan melalui *artifact store* atau *intermediate data objects*.

### Mental Model: Experiment Tracking sebagai State & Lineage Engine
*Experiment Tracking* bukan sekadar logging teks ke konsol atau *file* log flat. Ini adalah pencatatan struktural terhadap dimensi ruang eksperimen:
- **Code State**: Git commit SHA, branch, status *working tree dirty*.
- **Environment State**: Docker image digest, OS, dependensi (`poetry.lock` / `requirements.txt`).
- **Data State**: Hash data input, parameter ekstraksi, skema feature store.
- **Hyperparameters**: Konfigurasi floating-point, integer, atau kategorikal model.
- **Metrics Trajectory**: Metrik run-time (loss step-by-step, GPU memory, epoch latency) dan metrik evaluasi akhir (F1, AUC-ROC, latency p99).
- **Artifacts**: Model biner terkompresi, visualisasi confusion matrix, SHAP plots, dan data profiling summary.

---

## 3. Why It Matters

### Masalah Nyata di Enterprise ML:
1. **The "Hidden Technical Debt" Crisis**: Sculley et al. (Google, 2015) mengidentifikasi bahwa kode ML riil hanya merepresentasikan <5% dari keseluruhan ekosistem. Sisanya berupa *glue code*, konfigurasi, manajemen metadata, dan validasi data. Pipeline monolitik meningkatkan beban *technical debt* ini hingga titik di mana *deployment velocity* menurun drastis.
2. **Ketiadaan Reproduktifitas (The "Works on My Machine" Syndrome)**: Ketika model di produksi mengalami *performance drift*, *engineer* gagal mereplikasi bobot model awal karena ketidakjelasan versi data yang digunakan 6 bulan lalu, ketiadaan random seed yang di-track, atau perbedaan minor pada versi lib *compiler* C++ (`xgboost`/`torch`).
3. **Audit & Compliance (GDPR, EU AI Act, Basel III/IV)**: Institusi keuangan dan kesehatan diwajibkan secara hukum untuk menjelaskan mengapa sebuah model inferensi mengambil keputusan tertentu. Tanpa *artifact lineage* yang mengaitkan `Model Version -> Experiment Run -> Data Split Hash -> Training Source Code`, model dianggap *non-compliant* dan dilarang beroperasi.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut merepresentasikan interaksi sistem modular pipeline dengan *backend* *Experiment Tracking* dan *Artifact Storage*:

```
+-----------------------------------------------------------------------------------------+
|                                    EXECUTION RUNNER                                     |
|                                                                                         |
|  +--------------------+        +---------------------+        +----------------------+  |
|  |   IngestionStep    |        |  TransformationStep |        |     TrainingStep     |  |
|  |                    |        |                     |        |                      |  |
|  | - Read Raw Data    | =====> | - Scaling/Encoding  | =====> | - Model Fit          |  |
|  | - Schema Validation|        | - Train/Test Split  |        | - Early Stopping     |  |
|  +---------+----------+        +----------+----------+        +----------+-----------+  |
|            |                              |                              |              |
+------------|------------------------------|------------------------------|--------------+
             |                              |                              |
             | Data Artifacts               | Data Artifacts               | Model Weights
             v                              v                              v
+-----------------------------------------------------------------------------------------+
|                                ARTIFACT STORE (e.g., S3 / GCS / MinIO)                  |
|  s3://bucket/artifacts/run_id_xyz/raw_data.parquet                                      |
|  s3://bucket/artifacts/run_id_xyz/features.parquet                                      |
|  s3://bucket/artifacts/run_id_xyz/model/model.pkl                                       |
+-----------------------------------------------------------------------------------------+
             ^                              ^                              ^
             | (Log URI)                    | (Log URI)                    | (Log Metrics/Params)
+------------+------------------------------+------------------------------+--------------+
|                         CENTRALIZED TRACKING SERVER (MLflow Server)                     |
|                                                                                         |
|  REST APIs: /api/2.0/mlflow/runs/create, /api/2.0/mlflow/runs/log-parameter             |
|                                                                                         |
|  +-----------------------------------------------------------------------------------+  |
|  |                     BACKEND STORE (RDBMS: PostgreSQL / MySQL)                     |  |
|  |  - runs (run_id, experiment_id, status, start_time, git_commit, user)             |  |
|  |  - params (run_id, key, value)                                                    |  |
|  |  - metrics (run_id, key, value, timestamp, step)                                  |  |
|  |  - tags (run_id, key, value)                                                      |  |
|  |  - model_registry (model_name, version, run_id, stage, status)                    |  |
|  +-----------------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Deterministic Execution & Seed Management
Ketidakteraturan (non-determinism) bersumber dari:
- Library ML (NumPy, PyTorch, Scikit-Learn) yang menginisialisasi pseudo-random number generator (PRNG) secara independen.
- Operasi paralel non-deterministik pada prosesor multithread/GPU (e.g., CUDA non-deterministic atomic operations).
Pipeline modern mengisolasi seed di level bootstrap dan menyimpan seed sebagai parameter eksperimen yang immutable.

### 5.2 Decoupled Data Contracts
Setiap *step* pipeline mengonsumsi data yang divalidasi oleh skema (menggunakan tools seperti Pydantic atau Pandera) dan memproduksi artefak yang terikat dengan hash integritas (SHA-256). Pengalihan data antar-node tidak dilakukan via pass-by-reference objek in-memory jika dieksekusi lintas proses atau kontainer, melainkan via *pass-by-reference of persistent URI*.

### 5.3 MLflow Entity Model & Lineage Tracking
MLflow memetakan observabilitas ML menjadi lima entitas inti:
1. **Experiment**: Namespace logis tingkat tinggi yang merepresentasikan problem domain (misal: `fraud-detection-lightgbm`).
2. **Run**: Eksekusi spesifik dari kode pipeline dalam cakupan Experiment. Run dapat bersifat hierarkis (Parent Run merepresentasikan keseluruhan Pipeline, Child Runs merepresentasikan tiap Step).
3. **Parameters**: Pasangan Key-Value string yang bersifat *immutable* setelah didefinisikan (e.g., `learning_rate: "0.01"`).
4. **Metrics**: Observasi numerik skalar yang mendukung *multi-step recording* untuk visualisasi *time-series* atau evaluasi step per step.
5. **Artifacts**: File biner bervolume tinggi (*unstructured/structured data*, bobot model, diagram visual) yang dialirkan langsung ke blob store.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi modular ML pipeline yang menggunakan pattern *Template Method*, strictly typed contracts dengan Pydantic, dan MLflow tracking dengan *hierarchical runs* (Parent-Child).

### Struktur Direktori
```text
ml_pipeline/
├── config.py
├── contracts.py
├── steps/
│   ├── base.py
│   ├── data_ingestion.py
│   ├── feature_engineering.py
│   ├── model_training.py
│   └── model_evaluation.py
└── pipeline.py
```

### Implementasi Lengkap

```python
# config.py
from pydantic import BaseModel, Field


class PipelineConfig(BaseModel):
    experiment_name: str = Field(..., description="Nama eksperimen MLflow")
    tracking_uri: str = Field(default="http://localhost:5000", description="URI Tracking Server")
    random_state: int = Field(default=42, description="Seed global untuk determinisme")
    data_source_url: str = Field(..., description="Path atau URL dataset input")
    test_size: float = Field(default=0.2, ge=0.05, le=0.5, description="Rasio split test")
    n_estimators: int = Field(default=100, ge=10, description="Hyperparameter model: n_estimators")
    max_depth: int = Field(default=5, ge=1, le=50, description="Hyperparameter model: max_depth")
    target_metric_threshold: float = Field(default=0.80, description="Threshold minimum F1 Score")
```

```python
# contracts.py
from typing import Tuple, Any
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict


class StepArtifact(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class IngestionOutput(StepArtifact):
    data: pd.DataFrame
    raw_data_hash: str


class TransformationOutput(StepArtifact):
    X_train: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray
    y_test: np.ndarray
    feature_names: list[str]


class TrainingOutput(StepArtifact):
    model: Any
    model_params: dict[str, Any]


class EvaluationOutput(StepArtifact):
    metrics: dict[str, float]
    passed_gate: bool
```

```python
# steps/base.py
import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar
import mlflow
from contracts import StepArtifact

InputT = TypeVar("InputT", bound=StepArtifact)
OutputT = TypeVar("OutputT", bound=StepArtifact)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


class BaseStep(ABC, Generic[InputT, OutputT]):
    def __init__(self, step_name: str):
        self.step_name = step_name
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def execute(self, inputs: InputT) -> OutputT:
        """Logika internal komputasi step."""
        pass

    def run(self, inputs: InputT) -> OutputT:
        """Wrapper method untuk eksekusi terstandarisasi dengan MLflow nested run."""
        self.logger.info(f"Memulai eksekusi step: {self.step_name}")
        with mlflow.start_run(run_name=self.step_name, nested=True) as child_run:
            mlflow.set_tag("step_name", self.step_name)
            try:
                output = self.execute(inputs)
                mlflow.set_tag("status", "SUCCESS")
                self.logger.info(f"Step {self.step_name} selesai secara sukses.")
                return output
            except Exception as e:
                mlflow.set_tag("status", "FAILED")
                self.logger.exception(f"Eksekusi step {self.step_name} gagal: {str(e)}")
                raise e
```

```python
# steps/data_ingestion.py
import hashlib
from sklearn.datasets import load_breast_cancer
import pandas as pd
from contracts import StepArtifact, IngestionOutput
from steps.base import BaseStep
from config import PipelineConfig
import mlflow


class EmptyInput(StepArtifact):
    pass


class DataIngestionStep(BaseStep[EmptyInput, IngestionOutput]):
    def __init__(self, config: PipelineConfig):
        super().__init__("DataIngestion")
        self.config = config

    def execute(self, inputs: EmptyInput) -> IngestionOutput:
        # Simulasi ingest dari data source riil
        dataset = load_breast_cancer(as_frame=True)
        df: pd.DataFrame = dataset.frame

        # Kalkulasi hash data mentah untuk audit lineage
        data_bytes = pd.util.hash_pandas_object(df).values.tobytes()
        raw_data_hash = hashlib.sha256(data_bytes).hexdigest()

        # Log metadata ke MLflow
        mlflow.log_param("dataset_name", "breast_cancer_wisconsin")
        mlflow.log_param("raw_data_hash", raw_data_hash)
        mlflow.log_metric("row_count", float(df.shape[0]))
        mlflow.log_metric("column_count", float(df.shape[1]))

        return IngestionOutput(data=df, raw_data_hash=raw_data_hash)
```

```python
# steps/feature_engineering.py
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from contracts import IngestionOutput, TransformationOutput
from steps.base import BaseStep
from config import PipelineConfig
import mlflow


class FeatureEngineeringStep(BaseStep[IngestionOutput, TransformationOutput]):
    def __init__(self, config: PipelineConfig):
        super().__init__("FeatureEngineering")
        self.config = config

    def execute(self, inputs: IngestionOutput) -> TransformationOutput:
        df = inputs.data
        X = df.drop(columns=["target"])
        y = df["target"].values
        feature_names = list(X.columns)

        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=self.config.test_size,
            random_state=self.config.random_state,
            stratify=y,
        )

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        mlflow.log_param("test_size", self.config.test_size)
        mlflow.log_param("scaler_type", "StandardScaler")
        mlflow.log_metric("train_samples", float(X_train_scaled.shape[0]))
        mlflow.log_metric("test_samples", float(X_test_scaled.shape[0]))

        return TransformationOutput(
            X_train=X_train_scaled,
            X_test=X_test_scaled,
            y_train=y_train,
            y_test=y_test,
            feature_names=feature_names,
        )
```

```python
# steps/model_training.py
from sklearn.ensemble import RandomForestClassifier
from contracts import TransformationOutput, TrainingOutput
from steps.base import BaseStep
from config import PipelineConfig
import mlflow
import mlflow.sklearn


class ModelTrainingStep(BaseStep[TransformationOutput, TrainingOutput]):
    def __init__(self, config: PipelineConfig):
        super().__init__("ModelTraining")
        self.config = config

    def execute(self, inputs: TransformationOutput) -> TrainingOutput:
        params = {
            "n_estimators": self.config.n_estimators,
            "max_depth": self.config.max_depth,
            "random_state": self.config.random_state,
        }

        # Log hyperparameter ke MLflow Run level step
        mlflow.log_params(params)

        model = RandomForestClassifier(**params)
        model.fit(inputs.X_train, inputs.y_train)

        # Log artifact model ke Tracking Server
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model_artifact",
            input_example=inputs.X_train[:5],
        )

        return TrainingOutput(model=model, model_params=params)
```

```python
# steps/model_evaluation.py
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from contracts import TransformationOutput, TrainingOutput, EvaluationOutput, StepArtifact
from steps.base import BaseStep
from config import PipelineConfig
import mlflow


class EvaluationInput(StepArtifact):
    transform_out: TransformationOutput
    train_out: TrainingOutput


class ModelEvaluationStep(BaseStep[EvaluationInput, EvaluationOutput]):
    def __init__(self, config: PipelineConfig):
        super().__init__("ModelEvaluation")
        self.config = config

    def execute(self, inputs: EvaluationInput) -> EvaluationOutput:
        model = inputs.train_out.model
        X_test = inputs.transform_out.X_test
        y_test = inputs.transform_out.y_test

        y_pred = model.predict(X_test)
        y_pred_proba = model.predict_proba(X_test)[:, 1]

        acc = float(accuracy_score(y_test, y_pred))
        f1 = float(f1_score(y_test, y_pred))
        auc = float(roc_auc_score(y_test, y_pred_proba))

        metrics = {"accuracy": acc, "f1_score": f1, "roc_auc": auc}
        mlflow.log_metrics(metrics)

        # Gate Evaluation Strategy
        passed_gate = f1 >= self.config.target_metric_threshold
        mlflow.log_metric("passed_gate", 1.0 if passed_gate else 0.0)

        if not passed_gate:
            self.logger.warning(
                f"Model metric (F1: {f1:.4f}) berada di bawah ambang batas "
                f"({self.config.target_metric_threshold})!"
            )

        return EvaluationOutput(metrics=metrics, passed_gate=passed_gate)
```

```python
# pipeline.py
import mlflow
from config import PipelineConfig
from contracts import EmptyInput
from steps.data_ingestion import DataIngestionStep
from steps.feature_engineering import FeatureEngineeringStep
from steps.model_training import ModelTrainingStep
from steps.model_evaluation import ModelEvaluationStep, EvaluationInput


class MLTrainingPipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config
        mlflow.set_tracking_uri(self.config.tracking_uri)
        mlflow.set_experiment(self.config.experiment_name)

        # Instansiasi komponen pipeline
        self.ingestion = DataIngestionStep(config)
        self.transformation = FeatureEngineeringStep(config)
        self.training = ModelTrainingStep(config)
        self.evaluation = ModelEvaluationStep(config)

    def run(self) -> bool:
        # Parent Run merepresentasikan orchestrator pipeline run
        with mlflow.start_run(run_name="EndToEndPipelineRun") as parent_run:
            mlflow.set_tag("pipeline_version", "1.0.0")
            mlflow.log_param("global_seed", self.config.random_state)

            try:
                # 1. Ingestion
                ingestion_out = self.ingestion.run(EmptyInput())

                # 2. Transformation
                transform_out = self.transformation.run(ingestion_out)

                # 3. Training
                train_out = self.training.run(transform_out)

                # 4. Evaluation
                eval_input = EvaluationInput(transform_out=transform_out, train_out=train_out)
                eval_out = self.evaluation.run(eval_input)

                # Log final aggregation status
                mlflow.log_metric("pipeline_f1_score", eval_out.metrics["f1_score"])
                mlflow.set_tag("pipeline_status", "SUCCESS" if eval_out.passed_gate else "FAILED_GATE")

                if eval_out.passed_gate:
                    # Registrasi model hanya jika lolos uji batas metrik (Model Gating)
                    mlflow.register_model(
                        model_uri=f"runs:/{parent_run.info.run_id}/ModelTraining/model_artifact",
                        name="CancerClassificationProd",
                    )
                return eval_out.passed_gate

            except Exception as e:
                mlflow.set_tag("pipeline_status", "ERROR")
                mlflow.log_param("error_message", str(e))
                raise RuntimeError(f"Pipeline berhenti secara paksa: {str(e)}") from e


if __name__ == "__main__":
    # Inisialisasi pipeline dengan konfigurasi
    config = PipelineConfig(
        experiment_name="Wisconsin_Diagnostic_RF",
        tracking_uri="http://localhost:5000",
        random_state=42,
        data_source_url="internal://dataset/load_breast_cancer",
        test_size=0.25,
        n_estimators=150,
        max_depth=6,
        target_metric_threshold=0.85,
    )

    pipeline = MLTrainingPipeline(config=config)
    success = pipeline.run()
    print(f"Status pipeline: {'SUKSES (Lolos Gating)' if success else 'GAGAL (Evaluasi Rendah)'}")
```

---

## 7. Edge Cases & Failure Modes

Dalam eksekusi *production-grade*, pipeline harus tangguh terhadap anomali berikut:

| Failure Mode | Mekanisme Munculnya Masalah | Strategi Mitigasi Terapan |
| :--- | :--- | :--- |
| **Tracking Server Downtime** | Jaringan putus atau MLflow server 503 saat eksekusi berjalan di worker nodes. | Terapkan *exponential backoff retry* pada MLflow Client HTTP calls, atau gunakan *local SQLite/File fallback* dengan *asynchronous sync daemon*. |
| **Memory Blowup / OOM** | Objek data skala gigabyte dikirimkan antar-step menggunakan *in-memory passing*. | Tulis intermediate artifacts ke distributed storage (S3/MinIO) dalam format kolumnar (Apache Parquet), dan *pass reference path* (URI) antar-step alih-alih data frame mentah. |
| **Silent Schema Drift** | Perubahan tipe kolom implisit (misal: `float64` terbaca sebagai `string` karena terdapat *null value* tak lazim). | Validasi skema deterministik sebelum feature engineering dijalankan (e.g., Pydantic parsing / Pandera schema checks). Gagal secara eksplisit (*Fail Fast*). |
| **Stale Run State (Zombies)** | Container dieksekusi oleh Kubernetes Spot Instance yang mengalami *eviction*. Status run di DB tetap `RUNNING`. | Implementasikan *heartbeat daemon* atau pasang *timeout interceptor* yang mengecek status aktif Pod dan memperbarui status run ke `KILLED` jika heartbeat hilang. |

---

## 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektural | Custom Modular Pipeline + MLflow | Orchestrator Native (ZenML / Kedro) | Heavy Enterprise Orchestration (Kubeflow / Airflow) |
| :--- | :--- | :--- | :--- |
| **Overhead Operasional** | **Rendah**: Cukup server database SQL dan direktori storage/S3. | **Moderat**: Membutuhkan adopsi SDK framework dan layer abstraksi lokal. | **Sangat Tinggi**: Kebutuhan cluster Kubernetes dedicated, RBAC kompleks, dan resources besar. |
| **Portabilitas Kode** | **Tinggi**: Berupa plain Python class; mudah diintegrasikan ke CI/CD runner mana pun. | **Tinggi**: Abstraksi step independen dari engine eksekutor. | **Rendah**: Terikat dengan resource manifest Kubernetes, YAML definitions, atau Airflow operators. |
| **Kurva Belajar Tim** | **Minimal**: Engineer yang menguasai Python dasar & MLflow dapat langsung berkontribusi. | **Moderat**: Perlu memahami konsep pipeline, steps, artifact stores spesifik framework. | **Tinggi**: Membutuhkan keahlian Kubernetes, Container internals, & Distributed Systems. |
| **Debugging Complexity** | **Sangat Sederhana**: Standard local Python breakpoint debugging langsung di IDE. | **Sederhana**: Tersedia local executor mode yang relatif mudah ditelusuri. | **Kompleks**: Remote debugging via Pod logs, forward tunneling, dan cluster tracing. |

---

## 9. Best Practices & Standard Industri

1. **Prinsip Immutability Artefak**: Sekali sebuah model binary atau processed parquet dataset tersimpan di artifact store dengan Run ID terkait, objek tersebut **tidak boleh** ditimpa (*no overwrite policy*). Gunakan hash unik atau ID eksperimen berbasis UUIDv4.
2. **Standardisasi Namespace Logging**:
   - Parameter: Gunakan format snake_case dengan domain prefix (e.g., `model_max_depth`, `opt_learning_rate`, `prep_imputation_strategy`).
   - Metrik: Pisahkan metrik training dan evaluasi (e.g., `train/loss_step`, `val/f1_epoch`, `test/auc_roc`).
3. **Automated Model Gating**: Hindari registrasi manual langsung ke `Production`. Terapkan *Evaluation Step* otomatis yang memverifikasi:
   - Metrik berada di atas *baseline minimum*.
   - Tidak ada degradasi performa pada subset/slice data kritis (*fairness metrics*).
   - Ukuran kompresi model dan latensi inferensi batch/real-time tidak melampaui SLA.
4. **Environment Freezing**: Simpan hash commit Git (`git rev-parse HEAD`) dan `pip freeze` / `poetry.lock` file ke dalam MLflow artifacts di setiap eksekusi pipeline untuk menjamin auditabilitas replikasi lingkungan.

---

## 10. Hands-on Lab Exercise: Building Resilient ML Pipeline

### Skenario Bisnis:
Anda ditugaskan membangun pipeline inferensi klasifikasi risiko penipuan (Fraud Detection). Pipeline ini harus mengeksekusi data ingestion, preprocessing, training, dan memvalidasi skor metrik sebelum meregistrasikan model ke Model Registry.

### Langkah 1: Persiapan Environment
Siapkan virtual environment terisolasi dan instal dependensi yang diperlukan:
```bash
python -m venv venv_mlops
source venv_mlops/bin/activate  # Untuk Windows: venv_mlops\Scripts\activate
pip install mlflow scikit-learn pandas pydantic
```

### Langkah 2: Jalankan MLflow Tracking Server Lokal
Jalankan instance MLflow tracking server dengan SQLite backend dan direktori lokal untuk artefak:
```bash
mlflow server \
    --backend-store-uri sqlite:///mlflow.db \
    --default-artifact-root ./mlruns_artifacts \
    --host 127.0.0.1 \
    --port 5000
```
*Pastikan server tetap berjalan di terminal terpisah. Buka `http://localhost:5000` pada peramban Anda.*

### Langkah 3: Eksekusi Pipeline Kode
Jalankan file implementasi `pipeline.py` yang disediakan pada Bagian 6:
```bash
python pipeline.py
```

### Langkah 4: Analisis dan Verifikasi Eksperimen via UI
1. Buka antarmuka MLflow di `http://127.0.0.1:5000`.
2. Klik nama eksperimen: **`Wisconsin_Diagnostic_RF`**.
3. Amati struktur hierarki: Anda akan melihat satu *Parent Run* bertajuk `EndToEndPipelineRun` yang melingkupi 4 *Nested Child Runs* (`DataIngestion`, `FeatureEngineering`, `ModelTraining`, `ModelEvaluation`).
4. Buka run `ModelTraining`, periksa tab **Artifacts**. Verifikasi keberadaan artefak `model_artifact/` yang memuat `MLmodel`, `model.pkl`, dan `conda.yaml`.
5. Periksa tab **Models** di navigasi atas. Pastikan model dengan nama **`CancerClassificationProd`** terdaftar sebagai Version 1 jika metrik F1-score memenuhi threshold.

### Langkah 5: Uji Gating Failure (Chaos Testing)
Ubah nilai `target_metric_threshold` di file konfigurasi menjadi `0.999` (ambang batas yang tidak mungkin tercapai):
```python
# Modifikasi di blok __main__
config = PipelineConfig(
    ...
    target_metric_threshold=0.999,
)
```
Jalankan kembali:
```bash
python pipeline.py
```
**Ekspektasi Output**: Pipeline harus mencatat tag `pipeline_status = FAILED_GATE`, dan **tidak** mendaftarkan versi model baru ke registry, mencegah model sub-optimal masuk ke downstream deployment. Verifikasi perubahan ini pada MLflow UI.