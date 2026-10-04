# Bab 05: Pipeline Orchestration & Distributed Training
## Modul 01: Machine Learning Pipeline Orchestration Engines & Resilient DAG Execution

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Menganalisis & Memilih Engine Orchestration**: Membedakan kapabilitas mendasar antara orchestrator data umum (*general-purpose data orchestrators* seperti Apache Airflow) dengan *ML-native orchestrators* (seperti Kubeflow Pipelines berbasis Argo Workflows dan Dagster) berdasarkan parameter abstraksi *artifact*, isolasi *compute*, dan *state management*.
2. **Merancang Deterministic DAG**: Mengonstruksi alur kerja *Directed Acyclic Graph* (DAG) yang *hermetic*, *idempotent*, dan *reproducible* menggunakan kontrak *artifact passing* terdesentralisasi via Object Storage.
3. **Mengimplementasikan Content-Addressed Caching**: Membangun mekanisme caching cerdas berbasis *cryptographic hash* dari *input parameter*, *runtime code*, dan *upstream data lineage* untuk meniadakan redundansi komputasi bernilai tinggi.
4. **Menerapkan Pola Fault-Tolerant & Spot-Aware Execution**: Mengonfigurasi strategi penanganan interupsi pod, *graceful termination* (SIGTERM trapping), dan *checkpoint resumption* pada *ephemeral/spot compute nodes* di lingkungan Kubernetes.
5. **Mengintegrasikan Metadata & Lineage Tracking**: Memprogram ekstraksi metadata eksekusi otomatis ke dalam *Machine Learning Metadata (MLMD)* store guna memenuhi auditabilitas *end-to-end* sesuai standar regulasi enterprise (misalnya EU AI Act).

---

### 2. Concept Overview

Dalam Machine Learning Engineering enterprise, *pipeline* bukan sekadar skrip Python berurutan (*sequential scripts*). Sebuah *ML Pipeline* adalah **State Machine Terdistribusi** yang direpresentasikan sebagai **Directed Acyclic Graph (DAG)**, di mana setiap simpul (*node*) adalah unit komputasi terisolasi (kontainer) dan setiap sisi (*edge*) merepresentasikan ketergantungan eksekusi serta transfer *immutable artifacts*.

```
                      [ Raw Data Source ]
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Data Validation    │ ◄─── (Schema / Drift Check)
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Feature Engineering │ ◄─── [Content-Addressed Cache]
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Distributed Train   │ ◄─── (Spot Instance Node Pool)
                    └──────────┬──────────┘
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
     ┌────────────────────┐        ┌────────────────────┐
     │ Offline Evaluation │        │ Bias & Fairness    │
     └──────────┬─────────┘        └──────────┬─────────┘
                └──────────────┬──────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Model Registration  │ ◄─── (Conditional Gate)
                    └─────────────────────┘
```

#### Mental Model: The Separation of Control Plane and Data Plane

Arsitektur orkestrasi ML modern memisahkan dua domain utama:

1. **Control Plane (The Brain / Orchestrator)**:
   * Mengurai topologi DAG.
   * Mengevaluasi dependensi simpul (*dependency resolution*).
   * Menjadwalkan pod ke cluster orchestrator (seperti Kubernetes).
   * Mengelola siklus hidup eksekusi (*Pending*, *Running*, *Succeeded*, *Failed*).
   * **Tidak pernah** memproses data pelatihan secara langsung di dalam proses engine.

2. **Data Plane (The Muscle / Execution Engines)**:
   * Wadah komputasi terisolasi (*ephemeral containers*).
   * Mengunduh *input artifacts* dari object storage yang ditunjuk.
   * Menjalankan transformasi beban kerja tinggi (CPU/GPU intensive).
   * Mengunggah *output artifacts* dan memancarkan (*emit*) metadata ke MLMD Store sebelum terminasi.

#### Perbedaan Mendasar: Data Pipelines vs. ML Pipelines

| Dimensi | Data Pipeline Tradisional (ETL/ELT) | Machine Learning Pipeline |
| :--- | :--- | :--- |
| **Fokus Utama** | Transformasi volume data (baris/kolom) | Eksperimen, kode, data, model weight, dan metrik |
| **Output Utama** | Database Table / File Data Lake | Serialized Model, Metrics, Evidentiary Artifacts |
| **Compute Profile** | Homogen (Memory/IO intensive) | Heterogen (CPU tinggi -> Multi-GPU -> CPU rendah) |
| **Determinisme** | Relatif tinggi (Query SQL / Spark deterministic) | Non-deterministik secara inheren (stochastic optimization) |
| **State Caching** | Partisi berbasis waktu (*idempotent partition*) | Partisi berbasis hash konten, hyperparameter, dan bobot |
| **Lifecycle** | Terus menerus / Terjadwal kaku (*cron*) | Berbasis pemicu (*event-driven*), manual, *continuous training* (CT) |

---

### 3. Why It Matters: Real-World Enterprise Impact

Implementasi pipeline ad-hoc menggunakan Jupyter Notebooks atau shell script linear menimbulkan tantangan signifikan di lingkungan enterprise:

1. **Bencana Biaya Komputasi (The Financial Bleed)**: Model pelatihan deep learning modern (LLM, computer vision) membutuhkan *compute cluster* berbiaya ribuan dolar per run. Apabila tahap evaluasi gagal pada pipeline tanpa *step-level checkpointing* dan *caching*, seluruh tahapan *feature extraction* dan *training* harus diulang dari awal.
2. **Ketiadaan Reprodusibilitas (The "Works on My Machine" Dilemma)**: Hilangnya relasi antara versi data, kode preprocessing, dependensi pustaka C++/CUDA, dan parameter pelatihan menyebabkan model yang dideploy ke *production* tidak dapat direkonstruksi identik ketika terjadi degradasi inferensi (*silent failure*).
3. **Auditabilitas dan Regulasi Kepatuhan**: Regulasi seperti *EU Artificial Intelligence Act* mewajibkan institusi keuangan dan kesehatan untuk membuktikan data apa yang digunakan untuk melatih model tertentu. Tanpa *artifact lineage* terorkestrasi, pembuktian ini secara teknis mustahil dilakukan.
4. **Kegagalan Infrastruktur Ephemeral**: Penggunaan *Spot/Preemptible Instances* dapat memangkas biaya infrastruktur hingga 70-90%. Namun, tanpa orchestrator yang mampu menangkap sinyal interupsi (*preemption signals*) dan merekam state eksekusi, penggunaan node spot akan memicu kegagalan pipeline berulang kali.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan interaksi menyeluruh antara Developer, GitOps Engine, Kubernetes Control Plane, Orchestrator Controller, Compute Infrastructure, dan Metadata/Artifact Storage.

```
+---------------------------------------------------------------------------------------------------+
|                                      KUBERNETES CLUSTER                                           |
|                                                                                                   |
|  +-------------------------------------+             +-----------------------------------------+  |
|  |     ML Pipeline Control Plane       |             |           K8s Worker Node Pool          |  |
|  |                                     |             |                                         |  |
|  |  +-------------------------------+  |             |  +-----------------------------------+  |  |
|  |  |  Pipeline API & Webhook Engine |  |             |  | Step 1: Preprocessing Pod (CPU)   |  |  |
|  |  +---------------┬---------------+  |             |  | - Pulls Raw Data                  |  |  |
|  |                  │                  |             |  | - Emits Cleaned Dataset           |  |  |
|  |                  ▼                  |   Deploy    |  +-----------------┬-----------------+  |  |
|  |  +-------------------------------+  |   Pod       |                    │                    |  |
|  |  | Workflow Controller / Engine  |──┼────────────►|                    │ Triggers           |  |
|  |  | (e.g. Argo/KFP Controller)     |  |             |                    ▼                    |  |
|  |  +---------------┬---------------+  |             |  +-----------------------------------+  |  |
|  |                  │                  |   Deploy    |  | Step 2: Training Pod (GPU/Spot)   |  |  |
|  |                  ▼                  |   Pod       |  | - Loads Checkpoint                |  |  |
|  |  +-------------------------------+  |────────────►|  | - Handles SIGTERM Preemption      |  |  |
|  |  | Caching & Lineage Resolver    |  |             |  | - Emits Model Weight              |  |  |
|  |  +---------------┬---------------+  |             |  +-----------------┬-----------------+  |  |
|  |                  │                  |             |                    │                    |  |
|  +------------------┼──────────────────+             |                    ▼                    |  |
|                     │                                |  +-----------------------------------+  |  |
|                     │                                |  | Step 3: Evaluation Pod (CPU)      |  |  |
|                     │                                |  | - Assesses Metrics vs Baseline    |  |  |
|                     │                                |  | - Conditional Promotion           |  |  |
|                     │                                |  +-----------------┬-----------------+  |  |
|                     │                                +--------------------┼--------------------+  |
|                     │ Writes / Reads Metadata                             │ Writes Artifacts   |
+─────────────────────┼─────────────────────────────────────────────────────┼───────────────────+
                      │                                                     │
                      ▼                                                     ▼
    +───────────────────────────────────+                 +───────────────────────────────────+
    |   MLMD Store (PostgreSQL / RDBMS) |                 | Object Storage (MinIO / S3 / GCS) |
    |   - Execution Run IDs             |                 | - /artifacts/datasets/hash-a8f1.. |
    |   - Content Hashes (Cache Key)    |                 | - /artifacts/models/run-992a/     |
    |   - Step Lineage Graph (DAG Edges)|                 | - /artifacts/checkpoints/ep-04/   |
    +--------------------------------───+                 +--------------------------------───+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Topological Sorting & Kahn’s Algorithm pada Directed Acyclic Graph (DAG)

Orchestrator mengevaluasi eksekusi menggunakan representasi graf berarah tanpa siklus $G = (V, E)$, di mana $V$ merepresentasikan *task nodes* dan $E$ merepresentasikan relasi dependensi *directed edges*. Untuk menentukan urutan eksekusi yang valid, engine menerapkan **Kahn's Algorithm** untuk *Topological Sorting*:

1. Hitung *in-degree* (derajat masuk) untuk setiap node $v \in V$.
2. Inisialisasi antrean $Q$ berisi semua simpul dengan *in-degree* = 0.
3. Selama $Q$ tidak kosong:
   * Ambil simpul $u$ dari $Q$, masukkan ke urutan eksekusi (*execution schedule*).
   * Untuk setiap simpul tetangga $w$ di mana terdapat edge $(u, w) \in E$:
     * Kurangi *in-degree* $w$ dengan 1.
     * Jika *in-degree* $w$ bernilai 0, masukkan $w$ ke dalam $Q$.
4. Jika jumlah elemen pada urutan eksekusi tidak sama dengan $|V|$, maka terdeteksi siklus (*cycle detected*), dan DAG dinyatakan tidak valid.

#### B. Content-Addressed Caching Architecture

Efisiensi eksekusi pipeline bersandar pada formula deterministik caching. Engine menghitung *Cache Key* ($\mathcal{K}_{step}$) sebelum meluncurkan pod:

$$\mathcal{K}_{step} = \text{HMAC-SHA256}\Big(\text{CodeSignature} \parallel \text{ImageDigest} \parallel \text{Parameters} \parallel \sum_{i=1}^{n} \text{Hash}(\text{InputArtifact}_i)\Big)$$

* **CodeSignature**: Checksum dari fungsi eksekusi atau repositori skrip yang dimuat.
* **ImageDigest**: Hash unik kontainer Docker (`sha256:...`), menjamin layer dependensi sistem identik.
* **Parameters**: String terurut (*lexicographically sorted JSON*) dari hyperparameter input.
* **Hash(InputArtifact)**: Hash kriptografis dari data input upstream atau ETag/Content-MD5 dari objek di S3/MinIO.

Jika tuple $\langle \mathcal{K}_{step} \rangle$ ditemukan di *MLMD database* dengan status `COMPLETED`, sistem melewati (*skips*) alokasi komputasi Kubernetes, menyalin referensi output sebelumnya ke node downstream, dan menandai status sebagai `CACHED`.

#### C. Isolasi Artifact & File Handshake Protocol

Orchestrator yang baik meniadakan *shared file-system locks* (seperti NFS yang rentan terhadap *race condition* dan *bottleneck bandwidth*). Sebagai gantinya, digunakan paradigma **Decoupled Object Storage Handshake**:

```
[ Step A Pod ] ──(Upload)──► S3 Bucket (/pipeline/run-id/step-a/output.parquet)
                                       ▲
                                       │ (Download via signed URI / IAM)
[ Step B Pod ] ────────────────────────┘
```

1. **Step Pod Initialization**: *Init container* menginjeksi kredensial IAM role dan mengunduh metadata input via referensi URI.
2. **Main Container Execution**: Kode pengguna membaca data lokal yang sudah dimuat, mengeksekusi logika komputasi, dan menulis data ke direktori `/outputs/`.
3. **Wait/Sidecar Container Execution**: Setelah aplikasi utama selesai (exit code 0), kontainer *sidecar* menyalin output ke Object Storage, menghasilkan *checksum digest*, dan mendaftarkannya ke Control Plane.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi *Custom Lightweight Resilient ML Pipeline Execution Engine* dalam Python murni dengan integrasi Object Storage (MinIO/S3), hashing deterministik, Topological DAG evaluation, dan penanganan sinyal OS (SIGTERM/SIGINT) untuk spot interruption.

Arsitektur kode dirancang modular:
* `Artifact`: Abstraksi data input/output berbasis S3.
* `Task`: Node komputasi dengan konfigurasi retry, cache validation, dan isolation logic.
* `DAG`: Dependency resolver dan orchestrator runtime engine.

```python
"""
ML Pipeline Orchestration Engine (Production-Grade Prototype)
File: ml_orchestrator.py
"""

from __future__ import annotations
import os
import sys
import json
import time
import signal
import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Callable
from collections import deque
import urllib.parse

# Setup Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}'
)
logger = logging.getLogger("MLOrchestrator")


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    CACHED = "CACHED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


@dataclass(frozen=True)
class Artifact:
    """Representasi immutable artifact dalam object storage."""
    name: str
    uri: str
    checksum: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class StorageBackend:
    """Mock/Simulasi S3/MinIO Object Storage Driver."""
    def __init__(self, base_path: str = "/tmp/mlops_storage"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def _resolve_path(self, uri: str) -> str:
        parsed = urllib.parse.urlparse(uri)
        return os.path.join(self.base_path, parsed.netloc, parsed.path.lstrip("/"))

    def write_artifact(self, uri: str, data: str) -> Artifact:
        target_path = self._resolve_path(uri)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(data)
            
        hasher = hashlib.sha256()
        hasher.update(data.encode("utf-8"))
        checksum = hasher.hexdigest()
        
        logger.info(f"Artifact berhasil disimpan di {target_path} | Checksum: {checksum[:8]}...")
        return Artifact(name=os.path.basename(uri), uri=uri, checksum=checksum)

    def read_artifact(self, uri: str) -> str:
        target_path = self._resolve_path(uri)
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Artifact tidak ditemukan pada path: {target_path}")
        with open(target_path, "r", encoding="utf-8") as f:
            return f.read()


class MetadataStore:
    """Penyimpan State Pipeline dan Cache Registry (Representasi MLMD)."""
    def __init__(self):
        self._cache_db: Dict[str, Dict[str, Any]] = {}
        self._execution_history: Dict[str, Dict[str, Any]] = {}

    def get_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        return self._cache_db.get(cache_key)

    def set_cache(self, cache_key: str, outputs: Dict[str, Artifact]) -> None:
        self._cache_db[cache_key] = {
            "outputs": outputs,
            "cached_at": time.time()
        }

    def record_step(self, task_name: str, run_id: str, status: ExecutionStatus) -> None:
        key = f"{run_id}:{task_name}"
        self._execution_history[key] = {
            "status": status.value,
            "updated_at": time.time()
        }


class TaskInterruptedException(Exception):
    """Exception khusus saat node menerima sinyal terminasi paksa (Spot Preemption)."""
    pass


class Task:
    """Node eksekusi dalam pipeline."""
    def __init__(
        self,
        name: str,
        fn: Callable[..., Dict[str, str]],
        retries: int = 2,
        enable_cache: bool = True
    ):
        self.name = name
        self.fn = fn
        self.retries = retries
        self.enable_cache = enable_cache
        self.upstream: Set[Task] = set()
        self.downstream: Set[Task] = set()

    def set_upstream(self, other: Task) -> None:
        self.upstream.add(other)
        other.downstream.add(self)

    def __rshift__(self, other: Task) -> Task:
        """Syntax sugar: task1 >> task2."""
        other.set_upstream(self)
        return other

    def compute_cache_key(
        self,
        parameters: Dict[str, Any],
        input_artifacts: Dict[str, Artifact]
    ) -> str:
        hasher = hashlib.sha256()
        
        # 1. Masukkan bytecode string representasi
        hasher.update(self.fn.__name__.encode("utf-8"))
        
        # 2. Masukkan parameter serial terurut
        sorted_params = json.dumps(parameters, sort_keys=True)
        hasher.update(sorted_params.encode("utf-8"))
        
        # 3. Masukkan checksum artifact hulu (lineage binding)
        for art_name in sorted(input_artifacts.keys()):
            hasher.update(input_artifacts[art_name].checksum.encode("utf-8"))
            
        return hasher.hexdigest()


class PipelineContext:
    """Konteks runtime yang dibagikan antar eksekusi task."""
    def __init__(self, run_id: str, storage: StorageBackend, metadata: MetadataStore):
        self.run_id = run_id
        self.storage = storage
        self.metadata = metadata
        self.task_artifacts: Dict[str, Dict[str, Artifact]] = {}
        self.should_terminate = False

    def handle_signal(self, signum: int, frame: Any) -> None:
        logger.warning(f"Menerima OS Signal: {signum}. Melakukan persistensi state & graceful teardown...")
        self.should_terminate = True
        raise TaskInterruptedException("Eksekusi pod dibatalkan oleh orkestrator host/spot reclamation.")


class PipelineEngine:
    """The Controller: Mengelola Eksekusi DAG, Caching, Fault-Tolerance."""
    def __init__(self, name: str, storage: StorageBackend, metadata: MetadataStore):
        self.name = name
        self.tasks: Dict[str, Task] = {}
        self.storage = storage
        self.metadata = metadata

    def add_task(self, task: Task) -> None:
        if task.name in self.tasks:
            raise ValueError(f"Task ganda terdeteksi: {task.name}")
        self.tasks[task.name] = task

    def _validate_dag(self) -> List[Task]:
        """Validasi siklus DAG menggunakan Algoritma Kahn."""
        in_degree = {name: len(task.upstream) for name, task in self.tasks.items()}
        queue = deque([task for name, task in self.tasks.items() if in_degree[name] == 0])
        sorted_tasks: List[Task] = []

        while queue:
            node = queue.popleft()
            sorted_tasks.append(node)

            for neighbor in node.downstream:
                in_degree[neighbor.name] -= 1
                if in_degree[neighbor.name] == 0:
                    queue.append(neighbor)

        if len(sorted_tasks) != len(self.tasks):
            raise ValueError("Kritikal: Ditemukan dependensi siklik (Cycle Detected) dalam DAG!")

        return sorted_tasks

    def execute_pipeline(self, run_id: str, global_params: Dict[str, Any]) -> bool:
        logger.info(f"--- Memulai Eksekusi Run ID: {run_id} ---")
        execution_order = self._validate_dag()
        context = PipelineContext(run_id, self.storage, self.metadata)

        # Mendaftarkan OS Signal Trap (Spot Termination: SIGTERM, SIGINT)
        signal.signal(signal.SIGINT, context.handle_signal)
        signal.signal(signal.SIGTERM, context.handle_signal)

        for task in execution_order:
            logger.info(f"Mempersiapkan eksekusi Task: [{task.name}]")

            # 1. Mengumpulkan dependensi upstream artifacts
            input_artifacts: Dict[str, Artifact] = {}
            for up in task.upstream:
                input_artifacts.update(context.task_artifacts.get(up.name, {}))

            # 2. Evaluasi Deterministik Caching
            task_params = global_params.get(task.name, {})
            cache_key = task.compute_cache_key(task_params, input_artifacts)
            
            if task.enable_cache:
                cached_result = self.metadata.get_cache(cache_key)
                if cached_result:
                    logger.info(f"⚡ [CACHE HIT] Menghindari eksekusi Task: [{task.name}]. Cache Key: {cache_key[:12]}")
                    context.task_artifacts[task.name] = cached_result["outputs"]
                    self.metadata.record_step(task.name, run_id, ExecutionStatus.CACHED)
                    continue

            logger.info(f"🚀 [CACHE MISS] Mengeksekusi Task: [{task.name}]. Menjadwalkan komputasi...")
            self.metadata.record_step(task.name, run_id, ExecutionStatus.RUNNING)

            # 3. Eksekusi dengan Mekanisme Exponential Backoff Retry Loop
            success = False
            attempts = 0
            while attempts <= task.retries and not success:
                try:
                    attempts += 1
                    if context.should_terminate:
                        raise TaskInterruptedException("Cluster Spot preempted pod.")

                    # Eksekusi fungsi utama
                    raw_outputs = task.fn(context, input_artifacts, task_params)
                    
                    # Persistensi output ke Object Storage
                    task_persisted_artifacts: Dict[str, Artifact] = {}
                    for out_name, out_data in raw_outputs.items():
                        s3_uri = f"s3://ml-bucket/{run_id}/{task.name}/{out_name}.dat"
                        artifact_obj = self.storage.write_artifact(s3_uri, out_data)
                        task_persisted_artifacts[out_name] = artifact_obj

                    # Simpan ke memori konteks & metadata store
                    context.task_artifacts[task.name] = task_persisted_artifacts
                    self.metadata.set_cache(cache_key, task_persisted_artifacts)
                    self.metadata.record_step(task.name, run_id, ExecutionStatus.SUCCEEDED)
                    
                    success = True
                    logger.info(f"✅ Selesai: Task [{task.name}] berhasil diselesaikan.")

                except TaskInterruptedException as tie:
                    logger.error(f"⚠️ Sinyal Interupsi pada [{task.name}]: {str(tie)}")
                    self.metadata.record_step(task.name, run_id, ExecutionStatus.INTERRUPTED)
                    return False

                except Exception as ex:
                    logger.error(f"❌ Error pada Task [{task.name}] Percobaan ({attempts}/{task.retries + 1}): {str(ex)}")
                    if attempts <= task.retries:
                        sleep_seconds = 2 ** attempts
                        logger.info(f"Menunggu {sleep_seconds}s sebelum retry...")
                        time.sleep(sleep_seconds)
                    else:
                        self.metadata.record_step(task.name, run_id, ExecutionStatus.FAILED)
                        logger.critical(f"Pipeline gagal pada node: [{task.name}]. Terminasi DAG.")
                        return False

        logger.info(f"--- Pipeline Selesai Sukses: Run ID {run_id} ---")
        return True


# =====================================================================
# Definisi Worker Steps (Implementasi Domain ML Nyata)
# =====================================================================

def task_validate_data(ctx: PipelineContext, inputs: Dict[str, Artifact], params: Dict[str, Any]) -> Dict[str, str]:
    # Simulasi validasi schema
    logger.info("Mengeksekusi Data Ingestion dan Data Quality Barrier...")
    min_rows = params.get("min_rows", 100)
    data_content = f"raw_data_sample_content_validated_rows_{min_rows}"
    return {"validated_dataset": data_content}


def task_preprocess(ctx: PipelineContext, inputs: Dict[str, Artifact], params: Dict[str, Any]) -> Dict[str, str]:
    logger.info("Mengeksekusi Tokenization / Normalization...")
    raw_artifact = inputs["validated_dataset"]
    # Membaca data mentah dari S3 via URI
    raw_data = ctx.storage.read_artifact(raw_artifact.uri)
    processed_data = f"preprocessed({raw_data})_scale={params.get('scaling', 'standard')}"
    return {"preprocessed_dataset": processed_data}


def task_train_model(ctx: PipelineContext, inputs: Dict[str, Artifact], params: Dict[str, Any]) -> Dict[str, str]:
    logger.info("Memulai komputasi Deep Learning (Multi-GPU Emulated)...")
    dataset = ctx.storage.read_artifact(inputs["preprocessed_dataset"].uri)
    learning_rate = params.get("lr", 0.001)
    
    # Mocking Training Step
    model_weights = f"WEIGHTS_TENSOR_DERIVED_FROM({dataset})_AT_LR({learning_rate})"
    return {"model_weights": model_weights}


def task_evaluate_gate(ctx: PipelineContext, inputs: Dict[str, Artifact], params: Dict[str, Any]) -> Dict[str, str]:
    logger.info("Mengevaluasi F1-Score & Loss Function...")
    model_str = ctx.storage.read_artifact(inputs["model_weights"].uri)
    
    # Menghitung metrik deterministik
    accuracy = 0.945
    min_acc_threshold = params.get("accuracy_threshold", 0.90)
    
    if accuracy < min_acc_threshold:
        raise ValueError(f"Model Quality Gate Gagal: Akurasi {accuracy} < {min_acc_threshold}")
        
    return {"evaluation_report": f"Status=PASSED;Metric={accuracy};WeightsRef={model_str[:16]}"}


# =====================================================================
# Driver Execution & Verification Script
# =====================================================================

if __name__ == "__main__":
    # Inisialisasi Storage dan State Backend
    storage = StorageBackend(base_path="/tmp/mlops_pipeline_storage")
    metadata_db = MetadataStore()

    # Bangun Topologi Pipeline
    engine = PipelineEngine("EnterpriseMLPipeline", storage, metadata_db)

    t_validate = Task("validate_data", task_validate_data)
    t_preprocess = Task("preprocess", task_preprocess)
    t_train = Task("train_model", task_train_model, retries=1)
    t_eval = Task("evaluate_gate", task_evaluate_gate)

    # Injeksi Relasi Dependensi (Topologi DAG)
    t_validate >> t_preprocess >> t_train >> t_eval

    engine.add_task(t_validate)
    engine.add_task(t_preprocess)
    engine.add_task(t_train)
    engine.add_task(t_eval)

    # Inisiasi Hyperparameter Configuration
    config = {
        "validate_data": {"min_rows": 5000},
        "preprocess": {"scaling": "robust"},
        "train_model": {"lr": 0.0003},
        "evaluate_gate": {"accuracy_threshold": 0.92}
    }

    print("\n" + "="*80)
    print("RUN #1: EKSEKUSI SEGAR (COLD START - SELURUH TASK CACHE MISS)")
    print("="*80)
    success_run1 = engine.execute_pipeline("run-alpha-001", config)
    assert success_run1 is True

    print("\n" + "="*80)
    print("RUN #2: RUN IDENTIK (DETERMINISTIC CACHING - HARUS 100% CACHE HIT)")
    print("="*80)
    success_run2 = engine.execute_pipeline("run-alpha-002", config)
    assert success_run2 is True

    print("\n" + "="*80)
    print("RUN #3: PARTIAL INVALIDATION (MODIFIKASI HYPERPARAMETER LR DI TRAIN)")
    print("="*80)
    config_modified = dict(config)
    config_modified["train_model"] = {"lr": 0.0001}  # Merubah parameter training

    # Harapan: validate_data & preprocess CACHED, train_model & evaluate_gate EXECUTED
    success_run3 = engine.execute_pipeline("run-alpha-003", config_modified)
    assert success_run3 is True
```

---

### 7. Edge Cases & Failure Modes

#### 1. Spot Instance Node Eviction (Preemption)
* **Gejala**: K8s Worker Node menerima sinyal terminasi dari Cloud Provider AWS/GCP (peringatan 30–120 detik sebelum shutdown). Pod langsung dimatikan paksa dengan Exit Code 137 (`OOMKilled` atau `SIGKILL`).
* **Mitigasi**:
  * Pod mendengarkan sinyal `SIGTERM`.
  * Aplikasi training segera melakukan flush tensor state ke disk lokal (`/tmp/checkpoint.pt`) dan memanggil integrasi S3 multipart upload sinkron.
  * Gunakan mekanisme Kubernetes *Pod Disruption Budgets* (PDB) serta taint/toleration untuk membedakan node master orkestrator (On-Demand) dengan node worker training (Spot).

#### 2. Pipeline-Wide Cache Poisoning
* **Gejala**: Sebuah task preprocessing menghasilkan data rusak (misalnya parsing CSV yang salah mengisi nilai `NaN` secara masif), namun menghasilkan status `COMPLETED`. Hash yang sama tersimpan di Metadata Store. Run selanjutnya terus menerus menggunakan data rusak karena *false Cache Hit*.
* **Mitigasi**:
  * Sertakan skema validasi berbasis *Great Expectations* atau schema hash ke dalam formula `Cache Key`.
  * Sediakan flag runtime override eksplisit (`--force-cache-bust` atau `--no-cache`) pada level CLI orchestrator untuk menghapus entri indeks metadata.

#### 3. Pod Ephemeral Storage Saturation (Disk Pressure)
* **Gejala**: Task preprocessing mengunduh file mentah terkompresi 200GB ke direktori root kontainer, memicu *Kubernetes Node Disk Eviction* (`The node was low on resource: ephemeral-storage`).
* **Mitigasi**:
  * Definisikan limit dan request `ephemeral-storage` secara eksplisit pada spesifikasi Pod Kubernetes.
  * Alih-alih menyalin data secara lokal, gunakan *streaming I/O* langsung dari S3 bucket menggunakan chunk generator atau FUSE-based mounts (misalnya S3FS / Goofys) dengan memory buffering terisolasi.

#### 4. Silent Upstream Drift (The "Hidden Hash" Anomaly)
* **Gejala**: Kode task dan hyperparameter sama persis, tetapi data upstream di S3 diperbarui secara *in-place* dengan nama file yang sama (misal `s3://data/latest.csv`) tanpa pembaruan ETag/hash metadata.
* **Mitigasi**:
  * **Hukum Mutlak MLOps**: Dilarang menggunakan pointer *mutable* seperti nama file `latest` untuk input pipeline. Seluruh path input harus menerapkan *Content-Addressable Storage (CAS)* atau immutable paths (`/dataset/version=v1.2.0/data.parquet`).

---

### 8. Trade-offs & Alternatif Solusi

Setiap orchestrator mengambil kompromi desain arsitektural yang berbeda:

```
                  Kubernetes-Native (Argo / KFP)
                                ▲
                                │
                                │   ★ Kubeflow Pipelines (KFP)
                                │   ★ Argo Workflows
                                │
        Low-Code / Config       │       Code-First / Functional
   ◄────────────────────────────┼────────────────────────────►
        Airflow (Task-Centric)  │   ★ Dagster (Data-Aware)
                                │   ★ Prefect
                                │
                                ▼
                   Host/Worker-Centric (Celery)
```

| Engine | Paradigma Utama | Keunggulan Enterprise | Kelemahan Arsitektural | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- | :--- |
| **Kubeflow Pipelines (KFP)** | *Container-Centric* & *K8s Native* (Argo under the hood) | Isolasi step sempurna; setiap task memiliki container image, CPU, dan alokasi GPU mandiri; integrasi MLMD natively. | Kurva belajar Kubernetes tinggi; *overhead* latensi inisialisasi pod (cold start) signifikan untuk task kecil. | Produksi berskala besar dengan armada GPU heterogen di Kubernetes. |
| **Apache Airflow** | *Task-Centric* (Berbasis Celery/K8s Executor) | Ekosistem plugin raksasa; dukungan enterprise mature; kapabilitas penjadwalan waktu (cron) paling stabil. | *Artifact passing* lemah (sering disalahgunakan via XCom yang membebani database backend); minim abstraksi model lineage bawaan. | Enterprise dengan data warehouse/ETL legacy yang ingin menyisipkan ML tanpa migrasi infra. |
| **Dagster** | *Data-Asset Centric* (Software-Defined Assets) | Menjadikan *Data Asset* sebagai warga kelas satu; *local development experience* terbaik; lineage dan declarative data catalog terintegrasi. | Membutuhkan standarisasi kode tim secara ketat; adopsi ekosistem Kubernetes tidak se-native Argo/KFP. | Tim MLOps modern yang mengedepankan data quality, testing komprehensif, dan software engineering best practices. |
| **Prefect** | *Workflow-as-Code* (Dynamic DAGs via Python decorators) | Mengubah fungsi Python arbitrer menjadi DAG dinamis secara instan; *orchestration logic* terlepas dari *execution infrastructure*. | Metadata lineage ML tingkat lanjut harus dibangun mandiri; integrasi ekosistem ML terbuka lebih sedikit dibanding KFP. | Prototyping cepat, dynamic branch runtime di mana topologi DAG berubah tergantung data input. |

---

### 9. Best Practices & Standar Industri

1. **Prinsip Satu Kontainer, Satu Tanggung Jawab**: Jangan gunakan *single giant docker image* untuk seluruh pipeline. Gunakan *lightweight image* berbasis Alpine/Slim Python untuk Data Extraction dan Preprocessing, dan gunakan *NVIDIA CUDA-optimized image* hanya pada node Training.
2. **Strict Hermeticity (Reproduksibilitas Absolut)**:
   * Kunci versi dependensi library secara deterministik menggunakan file *lockfile* (`poetry.lock`, `Pipfile.lock`).
   * Jangan mengandalkan tag image `latest`. Selalu gunakan *immutable digest pinning* (misal: `image: nvcr.io/nvidia/pytorch:23.10-py3@sha256:d84...`).
3. **Decoupled Identity via Workload Identity (Zero Hardcoded Secrets)**: Dilarang menyuntikkan `AWS_ACCESS_KEY_ID` atau database password ke dalam parameter DAG. Konfigurasi Kubernetes Service Accounts (KSA) yang dipetakan ke IAM Roles (IRSA di AWS atau Workload Identity di GCP) agar pod mendapatkan token akses terotentikasi secara temporer dan otomatis.
4. **Declarative Infrastructure via GitOps**: Seluruh definisi pipeline harus tersimpan sebagai kode (Python DSL atau YAML manifest). Sinkronisasi dari commit Git ke cluster orkestrasi wajib ditangani oleh engine GitOps seperti ArgoCD.

---

### 10. Hands-on Lab Exercise: Membangun Resilient ML Pipeline

#### Skenario Lab
Anda bertugas membangun pipeline otomatisasi end-to-end yang mengambil dataset tabular, menjalankan penskalaan fitur, melatih Linear/Tree Estimator, mengevaluasi akurasi terhadap batas threshold produksi, dan mensimulasikan pemulihan kegagalan sistem.

#### Langkah 1: Persiapan Lingkungan
Buat direktori kerja baru dan pasang dependensi yang diperlukan:

```bash
mkdir -p mlops_pipeline_lab/src
cd mlops_pipeline_lab
python3 -m venv venv
source venv/bin/activate
pip install numpy scikit-learn
```

#### Langkah 2: Menuliskan Implementasi Pipeline
Simpan kode sumber yang telah disediakan pada bagian **6. Production-Ready Code Implementation** ke dalam file bernama `src/engine.py`.

#### Langkah 3: Eksekusi Pipeline Uji Coba Caching
Jalankan file `engine.py` untuk mengamati transisi status eksekusi dari Cold Start hingga Deterministic Cache Hit:

```bash
python3 src/engine.py
```

*Verifikasi Hasil:*
Periksa keluaran terminal. Pada **RUN #1**, pastikan keempat task (`validate_data`, `preprocess`, `train_model`, `evaluate_gate`) mencetak log `[CACHE MISS]`.
Pada **RUN #2**, pastikan keempat task langsung mencetak log `⚡ [CACHE HIT]` dengan waktu eksekusi yang terpangkas drastis (mendekati 0 milidetik).

#### Langkah 4: Simulasi Kegagalan (Failure Injection & Quality Gate Breached)
Buka file `src/engine.py`, modifikasi parameter pengujian pada pemanggilan akhir untuk memaksa task evaluasi gagal:

```python
    # Tambahkan di bagian bawah file src/engine.py
    print("\n" + "="*80)
    print("RUN #4: SIMULASI THRESHOLD GATE FAILURE")
    print("="*80)
    config_failing = dict(config)
    config_failing["evaluate_gate"] = {"accuracy_threshold": 0.999} # Nilai mustahil dicapai (99.9%)
    
    failure_run = engine.execute_pipeline("run-fail-004", config_failing)
    assert failure_run is False
    print("Verifikasi Berhasil: Pipeline berhenti secara aman saat Quality Gate gagal.")
```

Jalankan kembali script:

```bash
python3 src/engine.py
```

*Verifikasi Hasil Akhir:*
Pastikan proses terminal menampilkan log error `❌ Error pada Task [evaluate_gate] Percobaan (1/1)` dan Pipeline mengembalikan status `False` tanpa melanjutkan proses ke task hipotetis berikutnya (misal: *Model Deployment*). Periksa direktori `/tmp/mlops_pipeline_storage` untuk memvalidasi bahwa seluruh *intermediate artifacts* tersimpan dengan penamaan checksum yang benar.