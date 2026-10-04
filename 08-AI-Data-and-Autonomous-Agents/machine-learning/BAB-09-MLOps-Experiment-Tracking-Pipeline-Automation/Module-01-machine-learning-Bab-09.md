# Bab 09: MLOps Experiment Tracking & Pipeline Automation

## Module 01: Production Experiment Tracking, Metadata Architecture, and Pipeline Automation Foundations

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang Arsitektur Dual-Store Tracking**: Mengonseptualisasikan dan mengimplementasikan sistem pelacakan eksperimen decoupled dengan PostgreSQL untuk ACID metadata transactions dan MinIO/S3 untuk immutable artifact storage.
- **Mengembangkan Client-Side Telemetry Buffering**: Membangun abstraction layer berbasis Python dengan asinkronus, batching, dan retry mechanism (tenacity) guna mencegah *network-induced training stall* saat logging metrik berkecepatan tinggi.
- **Menegakkan Deterministic Data & Model Lineage**: Mengimplementasikan cryptographic hashing (SHA-256) terhadap data input, environment specification, dan hyperparameter untuk membangun Directed Acyclic Graph (DAG) reproduktibilitas penuh.
- **Membangun Automated Model Packaging Pipeline**: Mengotomatisasi validasi artefak, inferensi skema input/output (Model Signatures), dan registrasi model stateful ke Model Registry dengan transisi status berbasis validasi metrik.
- **Mendeteksi dan Memitigasi Partial Failure States**: Menerapkan pola idempotency dan two-phase artifact commit untuk mencegah *split-brain states* antara metadata store dan artifact store pada *distributed training failures*.

---

### 2. Concept Overview

Dalam rekayasa sistem Machine Learning modern, transisi dari *exploratory data science* ke *production-grade MLOps* menuntut pergeseran mental model: **Machine Learning model bukanlah artefak statis, melainkan produk komputasi deterministik dari kombinasi Code, Data, Configuration, dan Compute Environment.**

```
+-------------------------------------------------------------------------+
|                    THE DETERMINISTIC REPRODUCIBILITY EQUATION           |
|                                                                         |
|  [ Code SHA ]  +  [ Data Hash ]  +  [ Hyperparams ]  +  [ Env Spec ]    |
|       │                 │                  │                 │          |
|       └────────┬────────┴──────────┬───────┴─────────────────┘          |
|                ▼                   ▼                                    |
|         ┌─────────────────────────────────────┐                         |
|         │      Deterministic ML Pipeline      │                         |
|         └──────────────────┬──────────────────┘                         |
|                            ▼                                            |
|         [ Immutable Artifact + Signature Hash ]                         |
+-------------------------------------------------------------------------+
```

Sistem pelacakan eksperimen (*Experiment Tracking System*) bukan sekadar logging library; sistem ini berfungsi sebagai **Transactional State Engine** terdistribusi yang mencatat lintasan komputasi model training. Entitas fundamental dalam arsitektur metadata ML meliputi:

1. **Experiment Namespace**: Logical container yang merepresentasikan batasan problem domain bisnis (misalnya: `fraud-detection-lgbm`).
2. **Run (Execution Unit)**: Eksekusi atomik tunggal dari pipeline pelatihan yang menghasilkan kombinasi metrik skalar (*time-series* loss/accuracy), parameter statis, metadata run, dan artefak biner.
3. **Parameters (Immutable Input)**: Konfigurasi invarian per run (learning rate, batch size, tree depth).
4. **Metrics (Dynamic Telemetry)**: Rangkaian data time-series diskrit $(step, timestamp, value)$ yang merefleksikan performa dan konvergensi model sepanjang siklus komputasi.
5. **Artifacts (Immutable Blobs)**: Representasi serialisasi dari model biner (`.onnx`, `.safetensors`, `.pkl`), visualisasi plots, schema definition, dan dataset slice references.
6. **Model Registry**: State machine tata kelola yang mempromosikan model dari status `None` $\rightarrow$ `Staging` $\rightarrow$ `Production` $\rightarrow$ `Archived` melalui gerbang pengujian performa terautomasi.

---

### 3. Why It Matters

Kegagalan menerapkan standardisasi pelacakan metadata dan otomatisasi pipeline menghasilkan disrupsi struktural pada skala enterprise:

- **The "Works on My GPU" Syndrome**: Ketidakmampuan mereplikasi akurasi model di lingkungan serving akibat tidak tercatatnya hash komit dependensi library (CUDNN/PyTorch mismatch) atau unpinned data slice versions.
- **Silent Metric Drift & Compliance Failure**: Regulasi ketat (seperti GDPR Article 22, HIPAA, Basel III) mewajibkan audit trail yang membuktikan secara persis data apa yang digunakan untuk melatih model tertentu. Tanpa cryptographic data-to-model lineage, model enterprise rentan terhadap sanksi kepatuhan dan recall operasional.
- **Storage Entropy & Zombie Runs**: Crash pada worker node di training cluster sering meninggalkan metadata berstatus `RUNNING` selamanya (*zombie state*) dan artefak parsial yang mengonsumsi ribuan gigabyte storage tanpa korelasi run yang valid.
- **Network-Blocked Training Loops**: Logging metrik sinkronus langsung ke HTTP tracking server pada setiap iterasi training batch dapat membebani GPU compute cycle dengan *I/O-wait*, menurunkan GPU utilization dari 98% menjadi <35%.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur produksi decoupling komputasi training, metadata logging, dan artifact persistence ke dalam model **Dual-Store Tracking Engine**:

```
+─────────────────────────────────────────────────────────────────────────────────────────+
|                                TRAINING INFRASTRUCTURE                                  |
|                                                                                         |
|  +-----------------------------------------------------------------------------------+  |
|  | Distributed Worker Nodes (K8s Pod / Slurm)                                        |  |
|  |                                                                                   |  |
|  |  +---------------------+        +--------------------+      +------------------+  |  |
|  |  | PyTorch / LightGBM  |        | Async Telemetry    |      | Checkpoint &     |  |  |
|  |  | Training Loop       |───────>| Buffer (Queue)     |      | Serializer       |  |  |
|  |  +---------------------+        +─────────┬──────────+      +────────┬─────────+  |  |
|  +───────────────────────────────────────────┼──────────────────────────┼────────────+  |
+──────────────────────────────────────────────┼──────────────────────────┼───────────────+
                                               │ (Batched HTTP REST/gRPC) │ (S3 Multipart)
                                               ▼                          │
+─────────────────────────────────────────────────────────────+           │
|                  MLOPS TRACKING PLANE                       |           │
|                                                             |           │
|  +───────────────────────────────────────────────────────+  |           │
|  | MLflow Tracking Server / Gateway (Stateless Pods)     |  |           │
|  |                                                       |  |           │
|  |  [ Auth & RBAC ] ──> [ Metric Ingestion ] ──> [ Auth ]|  |           │
|  +──────────────────────────────┬────────────────────────+  |           │
|                                 │ (SQL Transactions)        |           │
+─────────────────────────────────┼───────────────────────────┼───────────┼───────────────+
                                  │                           │           │
+─────────────────────────────────┼───────────────────────────┼───────────┼───────────────+
|                  PERSISTENCE INFRASTRUCTURE                 ▼           ▼               |
|                                                     +────────────────────────────────+  |
|  +─────────────────────────────────+                | High-Performance Object Store  |  |
|  | Metadata Store (RDBMS)          |                | (Ceph / MinIO / AWS S3)        |  |
|  |                                 |                |                                |  |
|  |  - Schema: PostgreSQL           |                |  s3://mlops-artifacts/         |  |
|  |  - Entities: Runs, Params,      |                |    ├── exp-42/run-a1/          |  |
|  |    Scalar Metric Snapshots,     |                |    │   ├── model.onnx          |  |
|  |    Tags, Model Registry States  |                |    │   ├── MLmodel (metadata)  |  |
|  |  - Constraints: ACID Compliant  |                |    │   └── conda.yaml          |  |
|  +─────────────────────────────────+                +────────────────────────────────+  |
+─────────────────────────────────────────────────────────────────────────────────────────+
```

#### Alur Interaksi Data (Sequence Flow)
1. **Inisialisasi**: Training client mengirim payload handshake ke Tracking Server; server mengalokasikan `run_id` baru di PostgreSQL dengan status `SCHEDULED` lalu `RUNNING`.
2. **Pencatatan Telemetri**: Worker mengirimkan metrik loss/evaluasi secara lokal ke ring-buffer memori internal. Thread background mengosongkan antrean (flush) setiap $N$ detik atau $M$ metrik ke Tracking Server via endpoint batched REST.
3. **Persistensi Artefak**: Model diekspor ke disk lokal, kemudian langsung diunggah dari worker node ke S3/MinIO menggunakan presigned URL yang diterbitkan oleh Tracking Server (menghindari bottleneck data transfer pada Tracking Server layer).
4. **Finalisasi**: Client mengirim sinyal `FINISHED` beserta referensi checksum SHA-256 artefak. PostgreSQL mengunci status run dan memperbarui metadata model registry secara transaksional.

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Dual-Store Ingestion Pattern
Sistem tracking memisahkan *High-Velocity Low-Volume Data* (metrik, parameter, run tags) dari *Low-Velocity High-Volume Data* (bobot model, dataset snapshots).
- **PostgreSQL**: Menggunakan tabel terindeks B-tree pada `(run_uuid, key, step)` untuk menjamin query latensi rendah pada visualisasi UI dashboard.
- **S3 Object Storage**: Mengandalkan immutable BLOB storage yang mendukung multipart streaming uploads, server-side encryption (SSE-KMS), dan lifecycle policy transition (misalnya memindahkan intermediate checkpoint ke Coldline/Glacier setelah 30 hari).

#### B. Asynchronous Telemetry Buffering
Logging langsung (sinkron) pada tiap iterasi mini-batch mengintroduksi overhead latensi jaringan ($\sim 10-50\text{ ms}$ per call). Jika satu epoch memiliki 5.000 batch, training loop mengalami penambahan waktu hingga 250 detik per epoch murni akibat I/O wait.
Solusi standar industri adalah **Ring-Buffer Producer-Consumer Pattern**:
- Training worker (Producer) memasukkan metrik ke thread-safe non-blocking bounded queue.
- Worker background (Consumer) mengumpulkan (*coalescing*) metrik hingga mencapai ukuran batch tertentu (misal: 500 item) atau interval waktu (misal: 2 detik), kemudian mengeksekusi operasi bulk insert ke database via Tracking API.

#### C. Lineage Derivation & Immutability Matrix
Guna menjamin reproducibilitas saintifik, hash komposit dihitung sebelum model dipromosikan ke Model Registry:

$$\mathcal{H}_{\text{lineage}} = \text{HMAC-SHA256}\Big(K_{\text{salt}}, \; \mathcal{H}(\text{Data}_{\text{train}}) \parallel \mathcal{H}(\text{Code}_{\text{commit}}) \parallel \mathcal{H}(\text{Params}) \parallel \mathcal{H}(\text{Env})\Big)$$

Jika $\mathcal{H}_{\text{lineage}}^{(A)} == \mathcal{H}_{\text{lineage}}^{(B)}$, maka komputasi model dijamin deterministik (dengan asumsi seed deterministik dan eksekusi instruksi GPU yang identik).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi modul experiment tracking client berbasis Python production-grade. Modul ini menerapkan thread-safe async batching, dynamic retry dengan backoff eksponensial, model serialization, dan integrasi MLflow API secara robust.

```python
"""
production_tracker.py
Arsitektur Enterprise Tracking Client & Pipeline Automation Wrapper.
Mendukung: Asynchronous buffered metric logging, model validation, dan lineage tracking.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
import queue
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple, Union

import mlflow
from mlflow.entities import Metric, Param, RunStatus
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient
from pydantic import BaseModel, Field, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# --------------------------------------------------------------------------- #
# Structured Logging Setup
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("MLOpsTracker")


# --------------------------------------------------------------------------- #
# Domain Entities & Validation Models
# --------------------------------------------------------------------------- #
class MetricPayload(BaseModel):
    key: str = Field(..., min_length=1, max_length=250)
    value: float
    step: int = Field(..., ge=0)
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))


class RunManifest(BaseModel):
    experiment_name: str
    run_name: str
    git_commit_hash: str = Field(..., pattern=r"^[0-9a-f]{40}$|^unknown$")
    dataset_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    hyperparameters: Dict[str, Any]
    tags: Dict[str, str] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Model Serializer Interface & Concrete Implementation
# --------------------------------------------------------------------------- #
class SerializableModel(Protocol):
    def save_pretrained(self, save_directory: str) -> None:
        ...


class SklearnLightGBMWrapper:
    """Contoh container model generik yang kompatibel dengan protokol."""
    def __init__(self, model_instance: Any):
        self.model = model_instance

    def save_pretrained(self, save_directory: str) -> None:
        import joblib
        output_path = Path(save_directory) / "model.joblib"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, output_path)
        logger.info(f"Model tersimpan secara lokal pada: {output_path}")


# --------------------------------------------------------------------------- #
# Enterprise Tracking Engine
# --------------------------------------------------------------------------- #
class ProductionExperimentTracker:
    """
    Tracking Client dengan thread-safe asynchronous queueing, batching,
    serta safe two-phase termination handling.
    """

    def __init__(
        self,
        tracking_uri: str,
        manifest: RunManifest,
        buffer_capacity: int = 10000,
        flush_interval_sec: float = 2.0,
        batch_size: int = 100,
    ) -> None:
        self.tracking_uri = tracking_uri
        self.manifest = manifest
        self.buffer_capacity = buffer_capacity
        self.flush_interval_sec = flush_interval_sec
        self.batch_size = batch_size

        # Inisialisasi API Core MLflow
        mlflow.set_tracking_uri(self.tracking_uri)
        self.client = MlflowClient(tracking_uri=self.tracking_uri)
        
        self.experiment_id: str = self._resolve_experiment()
        self.active_run_id: Optional[str] = None
        self._is_active: bool = False

        # Inisialisasi Ring/Queue Buffer
        self._metric_queue: queue.Queue[MetricPayload] = queue.Queue(maxsize=self.buffer_capacity)
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    def _resolve_experiment(self) -> str:
        """Menemukan ID eksperimen atau membuatnya jika belum terdaftar."""
        try:
            exp = self.client.get_experiment_by_name(self.manifest.experiment_name)
            if exp:
                return exp.experiment_id
            return self.client.create_experiment(name=self.manifest.experiment_name)
        except MlflowException as exc:
            logger.error(f"Gagal resolusi experiment {self.manifest.experiment_name}: {str(exc)}")
            raise

    def start_run(self) -> str:
        """Membuat run metadata record dan meluncurkan background telemetry thread."""
        run = self.client.create_run(
            experiment_id=self.experiment_id,
            run_name=self.manifest.run_name,
            tags={
                **self.manifest.tags,
                "git.commit": self.manifest.git_commit_hash,
                "data.sha256": self.manifest.dataset_sha256,
                "tracker.version": "1.0.0",
            },
        )
        self.active_run_id = run.info.run_id
        self._is_active = True

        # Ingest Hyperparameters secara atomic batch
        params = [
            Param(key=k, value=str(v))
            for k, v in self.manifest.hyperparameters.items()
        ]
        self._log_params_with_retry(params)

        # Start Async Worker Thread
        self._shutdown_event.clear()
        self._worker_thread = threading.Thread(
            target=self._telemetry_worker,
            name="TelemetryWorkerThread",
            daemon=True,
        )
        self._worker_thread.start()

        # Daftarkan graceful exit hook
        atexit.register(self.end_run, status="FAILED")
        logger.info(f"MLOps Run berhasil diinisiasi. Run ID: {self.active_run_id}")
        return self.active_run_id

    def log_metric(self, key: str, value: float, step: int) -> None:
        """Mengirimkan metrik skalar ke buffer in-memory thread-safe."""
        if not self._is_active:
            raise RuntimeError("Tracker tidak aktif. Panggil start_run() terlebih dahulu.")

        try:
            payload = MetricPayload(key=key, value=value, step=step)
            self._metric_queue.put_nowait(payload)
        except queue.Full:
            logger.warning(
                f"Metric buffer kapasitas penuh ({self.buffer_capacity}). "
                f"Metrik {key} pada step {step} dibuang (Drop tail)!"
            )
        except ValidationError as val_err:
            logger.error(f"Validasi payload metrik gagal: {val_err}")

    def _telemetry_worker(self) -> None:
        """Background consumer worker: menguras queue dan batch insert ke MLflow Server."""
        logger.info("Telemetry background thread aktif.")
        buffer: List[MetricPayload] = []
        last_flush = time.time()

        while not self._shutdown_event.is_set() or not self._metric_queue.empty():
            try:
                # Mengambil metrik dengan batasan timeout agar thread tidak hang
                item = self._metric_queue.get(timeout=0.2)
                buffer.append(item)
                self._metric_queue.task_done()
            except queue.Empty:
                pass

            now = time.time()
            reached_batch_size = len(buffer) >= self.batch_size
            reached_time_limit = (now - last_flush) >= self.flush_interval_sec

            if buffer and (reached_batch_size or reached_time_limit or self._shutdown_event.is_set()):
                self._flush_metrics_to_server(buffer)
                buffer = []
                last_flush = now

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(MlflowException),
        reraise=False,
    )
    def _flush_metrics_to_server(self, metric_payloads: List[MetricPayload]) -> None:
        """Mengirimkan batch metrics ke MLflow Tracking Server dengan ketahanan retry."""
        if not self.active_run_id:
            return

        mlflow_metrics = [
            Metric(
                key=item.key,
                value=item.value,
                timestamp=item.timestamp,
                step=item.step,
            )
            for item in metric_payloads
        ]

        try:
            self.client.log_batch(
                run_id=self.active_run_id,
                metrics=mlflow_metrics,
                params=[],
                tags=[],
            )
        except Exception as exc:
            logger.error(f"Gagal mengirim batch {len(metric_payloads)} metrik: {str(exc)}")
            raise

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=5),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(MlflowException),
    )
    def _log_params_with_retry(self, params: List[Param]) -> None:
        if self.active_run_id and params:
            self.client.log_batch(run_id=self.active_run_id, params=params)

    def log_and_register_model(
        self,
        model: SerializableModel,
        artifact_subpath: str,
        registered_model_name: Optional[str] = None,
    ) -> None:
        """Menyimpan artefak, menghitung SHA-256 checksum, dan mendaftarkan ke Model Registry."""
        if not self.active_run_id:
            raise RuntimeError("Eksekusi Run tidak aktif.")

        staging_dir = Path("./tmp_staging") / self.active_run_id
        staging_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 1. Serialisasi lokal
            model.save_pretrained(str(staging_dir))

            # 2. Hitung Checksum Integritas
            checksum_map = {}
            for path in staging_dir.rglob("*"):
                if path.is_file():
                    sha = self._compute_file_sha256(path)
                    checksum_map[path.name] = sha

            checksum_file = staging_dir / "integrity_manifest.json"
            with open(checksum_file, "w") as f:
                json.dump(checksum_map, f, indent=2)

            # 3. Log Artifacts via Client
            self.client.log_artifacts(
                run_id=self.active_run_id,
                local_dir=str(staging_dir),
                artifact_path=artifact_subpath,
            )
            logger.info("Artefak model dan checksum berhasil diunggah ke Object Store.")

            # 4. Registrasi ke Model Registry jika diinstruksikan
            if registered_model_name:
                source_uri = f"runs:/{self.active_run_id}/{artifact_subpath}"
                reg_model = self.client.create_model_version(
                    name=registered_model_name,
                    source=source_uri,
                    run_id=self.active_run_id,
                    description=f"Model registered automatically from commit {self.manifest.git_commit_hash}",
                )
                logger.info(
                    f"Model terdaftar: '{reg_model.name}' Version: '{reg_model.version}' State: {reg_model.status}"
                )

        finally:
            # Cleanup workspace lokal (mencegah disk bloating pada worker)
            if staging_dir.exists():
                import shutil
                shutil.rmtree(staging_dir, ignore_errors=True)

    @staticmethod
    def _compute_file_sha256(file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def end_run(self, status: str = "FINISHED") -> None:
        """Menghentikan worker thread, menguras metric queue, dan menutup lifecycle Run."""
        if not self._is_active or not self.active_run_id:
            return

        logger.info(f"Mengakhiri run: {self.active_run_id} dengan status: {status}")
        self._is_active = False

        # 1. Hentikan worker thread
        self._shutdown_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10.0)

        # 2. Resolve Status Enum
        status_map = {
            "FINISHED": RunStatus.FINISHED,
            "FAILED": RunStatus.FAILED,
            "KILLED": RunStatus.KILLED,
        }
        final_status = status_map.get(status, RunStatus.FAILED)

        # 3. Terminate run di MLflow Server
        try:
            self.client.set_terminated(run_id=self.active_run_id, status=final_status)
            logger.info("Status run berhasil dikonsolidasikan ke Metadata Store.")
        except Exception as exc:
            logger.error(f"Gagal memperbarui status terminasi run: {str(exc)}")
        finally:
            self.active_run_id = None
            # Hapus referensi atexit untuk mencegah duplicate calls
            try:
                atexit.unregister(self.end_run)
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# Execution Verification Pipeline
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    # Inisialisasi Mock Server URL / Local Tracking Directory
    LOCAL_TRACKING_PATH = Path("./mlruns_local").resolve()
    TRACKING_URI = f"file://{LOCAL_TRACKING_PATH}"

    # Setup Lineage Metadata Manifest
    dummy_data = b"Simulated normalized feature vectors across 1M rows"
    dataset_hash = hashlib.sha256(dummy_data).hexdigest()

    manifest = RunManifest(
        experiment_name="fraud-detection-lightgbm",
        run_name=f"run-benchmark-node-{int(time.time())}",
        git_commit_hash="c5f88e1a3d90f23bcf441e892e850b55b2067ad1",
        dataset_sha256=dataset_hash,
        hyperparameters={
            "learning_rate": 0.03,
            "num_leaves": 63,
            "max_depth": 7,
            "objective": "binary",
            "device_type": "cuda",
        },
        tags={"env": "staging", "infra": "k8s-dgx-a100"},
    )

    tracker = ProductionExperimentTracker(
        tracking_uri=TRACKING_URI,
        manifest=manifest,
        batch_size=50,
        flush_interval_sec=1.0,
    )

    try:
        run_id = tracker.start_run()

        # Simulasi training loop berkecepatan tinggi
        logger.info("Memulai simulasi batch execution loop...")
        for epoch in range(1, 101):
            simulated_loss = 1.0 / (epoch + 1) + 0.05
            simulated_auc = 0.5 + (0.45 * (1 - 1 / (epoch + 1)))

            tracker.log_metric(key="train_loss", value=simulated_loss, step=epoch)
            tracker.log_metric(key="eval_auc", value=simulated_auc, step=epoch)
            time.sleep(0.01)  # Simulasi compute load 10ms

        logger.info("Training selesai. Mempersiapkan serialisasi model...")

        # Mock Model Instance
        class FakeClassifier:
            def predict(self, X): return [1]

        model_wrapper = SklearnLightGBMWrapper(FakeClassifier())

        # Registrasi model
        tracker.log_and_register_model(
            model=model_wrapper,
            artifact_subpath="classifier_model",
            registered_model_name=None,  # Set string jika menggunakan DB tracking server riil
        )

        tracker.end_run(status="FINISHED")
        logger.info("Pipeline tracking dieksekusi dengan sukses tanpa packet loss.")

    except Exception as err:
        logger.critical(f"Pipeline gagal dieksekusi: {err}", exc_info=True)
        tracker.end_run(status="FAILED")
```

---

### 7. Edge Cases & Failure Modes

#### 1. Split-Brain State (Two-Phase Commit Failure)
- **Kondisi**: Database mencatat run berstatus `FINISHED`, namun koneksi worker terputus saat proses multipart upload biner model ke S3 sedang berlangsung pada tahap 99%.
- **Dampak**: Model Registry menunjuk ke artefak S3 yang korup atau parsial; downstream pipeline deployment akan mengalami `FileNotFoundException` atau unpickling error saat start-up.
- **Mitigasi**: Terapkan **Atomic Manifest Checksum**. Unggah file `integrity_manifest.json` yang memuat hash SHA-256 dari seluruh bundle model sebagai berkas artefak *terakhir*. Server-side automation memvalidasi kesesuaian manifest sebelum memicu transisi status model menjadi `READY`.

#### 2. Metric Ingestion Flooding (Worker Memory Exhaustion)
- **Kondisi**: Tracking server mengalami latensi ekstrem (I/O saturation di PostgreSQL). Antrean memori worker `_metric_queue` terus terisi hingga melebihi batas RAM node, memicu `Out-Of-Memory (OOM) Killer` pada compute container.
- **Dampak**: Proses training terhenti paksa di tengah jalan; hilangnya *unflushed state*.
- **Mitigasi**: Gunakan **Bounded Queue** dengan kebijakan *Drop-Tail* atau *Drop-Oldest* terukur disertai logger warning, atau terapkan backpressure yang menghentikan sejenak training loop jika antrean telah mencapai threshold kapasitas $\ge 90\%$.

#### 3. Concurrent Pipeline Promotion Race Condition
- **Kondisi**: Dua pipeline evaluasi paralel memvalidasi dua Run berbeda dan secara simultan mencoba mempromosikan versinya ke stage `Production`.
- **Dampak**: Terjadi non-deterministic overwrite pada alias `Production`.
- **Mitigasi**: Gunakan **Optimistic Locking** atau **PostgreSQL Advisory Locks** pada tabel Model Registry saat mutasi status:
```sql
SELECT pg_advisory_xact_lock(hashtext('model_name_lock_key'));
-- Eksekusi evaluasi performa model dan mutasi stage di sini
```

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi | In-House / Open-Source (MLflow + MinIO + Postgres) | SaaS Terkelola (Weights & Biases / Neptune.ai) | Data Orchestrator Integrated (Dagster / Kubeflow Metadata) |
| :--- | :--- | :--- | :--- |
| **Data Governance** | **Maksimal**. Seluruh artefak tersimpan di VPC privat. Memenuhi batas kepatuhan industri finansial/kesehatan. | **Terbatas/Variatif**. Metadata transit dan tersimpan di cloud milik pihak ketiga (kecuali opsi Private Cloud/Enterprise). | **Maksimal**. Log dan lineage langsung berasosiasi dengan container pod lifecycle di cloud VPC internal. |
| **Operational Overhead**| **Tinggi**. Tim infra wajib mengelola High Availability (HA) Postgres, auto-scaling Tracking API Pods, dan object store lifecycle. | **Rendah (Zero Maintenance)**. Instan, scalable tanpa konfigurasi database infra, out-of-the-box alerting. | **Tinggi**. Menuntut pemahaman mendalam atas Kubernetes Custom Resource Definitions (CRDs) dan volume mounts. |
| **Latency & Throughput**| **Dapat Dioptimasi**. Dapat menempatkan Postgres instance di private subnets yang sama dengan compute cluster ($<1\text{ ms}$ latency). | Terbatas pada WAN latency, rentan terhadap network jitter publik saat push metrik. | Cepat untuk metadata pipeline, namun seringkali kaku untuk time-series metrics per mini-batch. |
| **Total Cost of Ownership**| **Komputasi & Storage Dasar**. Biaya serverless/VM statis + S3 capacity. | **Berbasis Lisensi/Seat**. Menjadi sangat mahal saat ukuran tim data dan volume metrics run bertumbuh masif. | Melekat dengan total konsumsi cluster compute Kubernetes yang dialokasikan. |

---

### 9. Best Practices & Standard Industri

1. **Deterministic Data Fingerprinting**: Jangan pernah mengandalkan nama file dataset (misal: `data_clean.csv`). Gunakan *Data Content Hashing* (misalnya: SHA-256 dari partition parquet atau Delta Table version snapshot) yang dimasukkan sebagai parameter wajib run manifest.
2. **Zero Direct Network Stalling**: Training script **tidak boleh** memanggil network I/O sinkron di dalam batch execution loop. Gunakan telemetry ring-buffer atau flush periodik di boundary step epoch.
3. **Structured Model Signatures**: Pastikan model selalu dipaketkan bersama skema input/output yang strict menggunakan typing framework (misalnya Pydantic atau MLflow ModelSignature) guna mendeteksi *input shape mismatch* saat runtime serving sebelum menerima traffic.
4. **Decoupled Architecture with Presigned URLs**: Hindari menyalurkan streaming upload artefak biner model (yang berukuran puluhan gigabyte) melalui container Tracking Server. Rancang arsitektur di mana Tracking Server hanya menghasilkan S3 Presigned URL, dan compute worker node mengunggah file biner langsung ke Object Storage target.
5. **Auto-Tombstoning Orphaned Runs**: Implementasikan background worker reaper yang mengevaluasi run berstatus `RUNNING` dengan timestamp heartbeat yang tidak diperbarui dalam durasi $> 1$ jam, lalu mengubah statusnya secara otomatis menjadi `FAILED (ZOMBIE)`.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan menyiapkan arsitektur pelacakan eksperimen enterprise secara lokal menggunakan infrastruktur container terisolasi: MLflow Tracking Server, PostgreSQL backend, dan MinIO S3 storage. Selanjutnya, Anda akan memvalidasi lineage tracking serta memeriksa artefak dan metric trajectory yang dihasilkan.

```
                                  LAB TOPOLOGY
+─────────────────────────────────────────────────────────────────────────────+
| Local Host Network (Docker Compose Engine)                                 |
|                                                                             |
|  +--------------------+   Port 5432   +----------------------------------+  |
|  | PostgreSQL Service |<──────────────| MLflow Tracking Server           |  |
|  | (Metadata DB)      |               | Port: 5000                       |  |
|  +--------------------+               +────────────────┬─────────────────+  |
|                                                        │                    |
|  +--------------------+               Port 9000 (S3)   │                    |
|  | MinIO Object Store |<───────────────────────────────┤                    |
|  | Bucket: /mlflow    |                                │                    |
|  +--------------------+                                │                    |
|            ▲                                           │                    |
|            └───────────────────┐                       │                    |
|                         S3 I/O │                       │ REST Logs          |
|                                +───────────────────────┴─+                  |
|                                | Python Lab Worker Run   |                  |
|                                | (Executes Pipeline)     |                  |
|                                +─────────────────────────+                  |
+─────────────────────────────────────────────────────────────────────────────+
```

#### Langkah 1: Deklarasi Infrastruktur (`docker-compose.yml`)
Simpan konfigurasi berikut ke dalam direktori kerja Anda:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: mlops_postgres
    environment:
      POSTGRES_USER: mlops_user
      POSTGRES_PASSWORD: mlops_password
      POSTGRES_DB: mlflow_db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mlops_user -d mlflow_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:RELEASE.2023-09-07T02-12-07Z
    container_name: mlops_minio
    environment:
      MINIO_ROOT_USER: minio_admin
      MINIO_ROOT_PASSWORD: minio_password
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

  create_bucket:
    image: minio/mc:RELEASE.2023-09-07T00-24-44Z
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      /usr/bin/mc alias set local_minio http://minio:9000 minio_admin minio_password;
      /usr/bin/mc mb local_minio/mlflow-bucket || true;
      exit 0;
      "

  mlflow_server:
    image: ghcr.io/mlflow/mlflow:v2.8.1
    container_name: mlops_mlflow_server
    depends_on:
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy
      create_bucket:
        condition: service_completed_successfully
    ports:
      - "5000:5000"
    environment:
      AWS_ACCESS_KEY_ID: minio_admin
      AWS_SECRET_ACCESS_KEY: minio_password
      MLFLOW_S3_ENDPOINT_URL: http://minio:9000
      MLFLOW_S3_IGNORE_TLS: "true"
    command: >
      mlflow server
      --backend-store-uri postgresql://mlops_user:mlops_password@postgres:5432/mlflow_db
      --default-artifact-root s3://mlflow-bucket/
      --host 0.0.0.0
      --port 5000

volumes:
  pgdata:
  miniodata:
```

#### Langkah 2: Bootstrap Layanan
Jalankan stack infrastruktur melalui terminal:
```bash
docker compose up -d
```
Pastikan seluruh container berada dalam kondisi running dan healthy:
```bash
docker compose ps
```

#### Langkah 3: Eksekusi Pipeline Client
Set environment variables pada terminal kerja Anda agar client Python dapat berinteraksi dengan MinIO:
```bash
export MLFLOW_TRACKING_URI="http://localhost:5000"
export AWS_ACCESS_KEY_ID="minio_admin"
export AWS_SECRET_ACCESS_KEY="minio_password"
export MLFLOW_S3_ENDPOINT_URL="http://localhost:9000"
export MLFLOW_S3_IGNORE_TLS="true"
```

Jalankan script Python:
```bash
python production_tracker.py
```

#### Langkah 4: Validasi dan Inspeksi Diagnostik

1. **Validasi State Metadata (PostgreSQL)**:
Masuk ke instance database dan pastikan run terdaftar dengan state `FINISHED`:
```bash
docker exec -it mlops_postgres psql -U mlops_user -d mlflow_db -c \
  "SELECT run_uuid, name, status, start_time, end_time FROM runs;"
```

2. **Validasi Integritas Metric Telemetry (PostgreSQL)**:
Periksa sampel run metrik bertingkat yang di-ingest melalui batched background consumer:
```bash
docker exec -it mlops_postgres psql -U mlops_user -d mlflow_db -c \
  "SELECT key, value, step FROM metrics WHERE key='train_loss' ORDER BY step DESC LIMIT 5;"
```

3. **Validasi Immutable Artifact Storage (MinIO S3)**:
Pastikan artefak model biner dan manifest checksum terunggah di bucket target MinIO:
```bash
docker exec -it mlops_minio /usr/bin/mc ls --recursive /data/mlflow-bucket/
```

4. **Web UI Verification**:
Akses visualisasi dashboard MLflow melalui browser pada alamat:
```
http://localhost:5000
```
Verifikasi bahwa seluruh hyperparameter, metrics time-series (AUC & Loss curves), dan file artefak biner beserta `integrity_manifest.json` dapat ditelusuri secara interaktif.