# Bab 10: Containerization & Orchestration untuk Data Platform

---

## 1. Learning Objectives

Setelah menyelesaikan bab ini, Anda diharapkan mampu:
- **Menganalisis & Mengisolasi Workload Data Platform:** Membangun *OCI-compliant container images* multi-stage yang aman, minimalis, dan teroptimasi untuk dependensi C-extension berat (PyArrow, NumPy, Polars, DuckDB) dengan ukuran *image* tereduksi hingga >70%.
- **Merancang Kubernetes Data Topology:** Mengonfigurasi primitif Kubernetes tingkat lanjut (`Jobs`, `CronJobs`, `StatefulSets`, `InitContainers`, `Sidecars`) khusus pemrosesan data analitik dan *vector ingestion pipelines*.
- **Mengelola Resource Allocation & Scheduling:** Mengimplementasikan konfigurasi `requests`, `limits`, `LimitRanges`, `ResourceQuotas`, serta algoritma *Quality of Service* (QoS) guna mencegah *Node OOMKilled Cascades* pada cluster komputasi terdistribusi.
- **Mengontrol Lifecycle & Signal Handling:** Mengembangkan *worker runtime* berbasis Python yang mematuhi konvensi POSIX signal (`SIGTERM`, `SIGINT`) untuk melakukan *state checkpointing* dan *graceful drain* sebelum Pod di-*evict* oleh Kubernetes control plane.
- **Membangun Event-Driven Autoscaling:** Mengintegrasikan KEDA (*Kubernetes Event-driven Autoscaling*) untuk melakukan *horizontal scaling* pada data processing pods berdasarkan metrik *lag* broker data (Apache Kafka / AWS SQS).

---

## 2. Concept Overview

Containerization pada ekosistem data engineering bukan sekadar membungkus skrip ke dalam Docker image. Ini adalah teknik isolasi komputasi deterministik yang menjamin reproduksibilitas pemrosesan data terlepas dari heterogenitas infrastruktur fisik host.

```
+-----------------------------------------------------------------------+
|                             USER SPACE                                |
|  +---------------------------+       +-----------------------------+  |
|  | Container 1 (PySpark/DuckDB)|     | Container 2 (Kafka Consumer)|  |
|  | - Virtual Filesystem (/app)|      | - Virtual Filesystem (/app) |  |
|  | - Private PID Space (PID 1)|      | - Private PID Space (PID 1) |  |
|  +---------------------------+       +-----------------------------+  |
|               |                                     |                 |
|  +-----------------------------------------------------------------+  |
|  |           Container Runtime Engine (containerd / CRI-O)         |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
|                            KERNEL SPACE                               |
|  +-----------------------------------------------------------------+  |
|  | Linux Namespaces (Mount, PID, Network, IPC, UTS, User, Cgroup)  |  |
|  +-----------------------------------------------------------------+  |
|  | Control Groups v2 (Memory Limit, CPU Bandwidth, I/O Throttling)  |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

### Mental Model & Teori Inti

1. **Linux Kernel Primitives sebagai Fondasi:**
   - **Namespaces:** Membatasi *apa yang dapat dilihat* oleh container. Data container beroperasi dalam `mnt` (mount storage terisolasi), `pid` (penomoran proses dimulai dari 1), `net` (routing table dan virtual interfaces mandiri), dan `ipc` (inter-process communication terbatas).
   - **Cgroups (Control Groups v2):** Membatasi *berapa banyak yang dapat digunakan*. Menetapkan pagu ketat atas CPU *shares/quota*, ambang batas RAM, serta throughput I/O blok penyimpanan. Jika PySpark driver mengonsumsi memory melampaui cgroup boundary, Kernel OOM-Killer langsung mengintervensi dengan sinyal `SIGKILL` (Exit Code 137).

2. **Orkestrasi Deklaratif vs. Imperatif:**
   Sistem data lawas mengandalkan eksekusi skrip imperatif via SSH atau cron server host. Kubernetes mengubah paradigma ini menjadi *reconciliation loop* deklaratif:
   $$\text{Current State} \xrightarrow{\quad \text{Reconcile Controller} \quad} \text{Desired State}$$
   Engine data platform memproyeksikan state pipeline ke dalam Custom Resource Definitions (CRD) atau Kubernetes native primitives (`Job`, `Pod`). Control plane secara kontinu memantau metrik kluster dan merealokasi pod jika terjadi kegagalan hardware (*self-healing*).

3. **Stateless vs. Stateful Compute:**
   Komputasi analitik modern memisahkan lapisan storage dari compute (*Decoupled Storage-Compute Architecture*). Pod data pipeline bersifat *ephemeral*: disk lokal hanya digunakan untuk *spill-to-disk buffer* (DuckDB memory swap, temporary parquet buffering), sedangkan persistensi final dialirkan ke Object Storage (S3, GCS, MinIO) atau Distributed File Systems via POSIX/CSI drivers.

---

## 3. Why It Matters

Dalam implementasi skala *enterprise*, kegagalan containerization dan orkestrasi berujung pada konsekuensi sistemik:

- **Dependency Hell & Non-Deterministic Runs:** Perbedaan minor pada shared library dynamic link C (`glibc` vs `musl`, versi `libgeos` atau CUDA runtime) pada level host OS menyebabkan anomali transformasi data yang sukar di-debug.
- **Resource Starvation & Silent OOM Kills:** Tanpa limitasi cgroup yang terkalibrasi, satu query DuckDB/Pandas yang mengeksekusi *unpartitioned cross-join* dapat melahap seluruh RAM server fisik, memicu Kernel OOM killer untuk mematikan proses database kritis lain yang berjalan berdampingan di host yang sama.
- **Biaya Infrastruktur yang Tak Terkendali (Cloud Waste):** Menjalankan *dedicated virtual machines* (VM) untuk pipeline batch yang hanya aktif 20 menit per hari membuang hingga 85% biaya sewa komputasi. Orkestrasi container berbasis Kubernetes memungkinkan *density packing* tinggi dan *autoscaling* hingga titik nol (*scale-to-zero*).
- **Graceful Draining Failure:** Kegagalan menangani lifecycle pod saat Kubernetes melakukan cluster auto-scaler scale-down menyebabkan pod dipaksa mati (`SIGKILL`). Akibatnya, partisi data terpotong di tengah komputasi (*corrupted delta commits*), menciptakan status *data inconsistency* yang fatal pada Data Lake.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut memvisualisasikan platform data terorkestrasi: dari ingress data via broker, penjadwalan pod elastis berbasis KEDA, isolasi network/storage, hingga downstream object store.

```
                                  KUBERNETES DATA PLATFORM CLUSTER
======================================================================================================
                                              +------------------------------------------------------+
                                              |                   KEDA Operator                      |
                                              +------------------------------------------------------+
                                                                    |
                                                     Polls Lag      | Updates Scale Target
                                                                    v
+------------------------+                     +-----------------------------------------------------+
| External Event Source  |                     |           Deployment / Job Controller               |
| (Kafka / SQS Stream)   |====================>|  - Replicas: Dynamic (0 to N)                       |
+------------------------+                     +-----------------------------------------------------+
                                                                    |
                                     +------------------------------+------------------------------+
                                     | Dispatches                                                  |
                                     v                                                             v
                  +------------------------------------+                         +------------------------------------+
                  |  Data Pipeline Pod (Replica 01)    |                         |  Data Pipeline Pod (Replica 02)    |
                  |                                    |                         |                                    |
                  |  +------------------------------+  |                         |  +------------------------------+  |
                  |  | Init Container:              |  |                         |  | Init Container:              |  |
                  |  | - Schema Validation          |  |                         |  | - Schema Validation          |  |
                  |  | - Wait for Upstream DB       |  |                         |  | - Wait for Upstream DB       |  |
                  |  +------------------------------+  |                         +---------------------------------+  |
                  |                 |                  |                                           |                  |
                  |  +------------------------------+  |                         |  +------------------------------+  |
                  |  | Core App Container:          |  |                         |  | Core App Container:          |  |
                  |  | - Python Worker Engine       |  |                         |  | - Python Worker Engine       |  |
                  |  | - Parquet Batch Processor    |  |                         |  | - Parquet Batch Processor    |  |
                  |  | - POSIX Signal Handler       |  |                         |  | - POSIX Signal Handler       |  |
                  |  +------------------------------+  |                         +---------------------------------+  |
                  |     | Local Scratch                |                         |     | Local Scratch                |
                  |     v                              |                         |     v                              |
                  |  [ emptyDir Volume (RAM/NVMe) ]    |                         |  [ emptyDir Volume (RAM/NVMe) ]    |
                  +------------------------------------+                         +------------------------------------+
                                     |                                                             |
                                     +------------------------------+------------------------------+
                                                                    | Writes Output
                                                                    v
                                              +------------------------------------------------------+
                                              | S3 / MinIO / Ceph Lakehouse (Parquet / Iceberg Format)|
                                              +------------------------------------------------------+
======================================================================================================
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 OCI Image Layering, Multi-Stage Builds, dan Security Hardening
Container image standard OCI (*Open Container Initiative*) terdiri dari lapisan-lapisan *read-only tarball* yang ditumpuk via *OverlayFS*. Setiap baris instruksi `RUN`, `COPY`, `ADD` memproduksi layer baru.

Pada data platform, kompilasi driver data (seperti `duckdb`, `pyarrow`, `grpcio`) membutuhkan compiler C++ (`gcc`, `g++`, `musl-dev`). Jika build toolchain ini dibiarkan tertinggal di runtime image:
1. Ukuran image membengkak hingga > 1.5 GB, memperlambat *Pod Image Pull Time* saat auto-scaling mendesak.
2. Memperluas *attack surface* eksploitasi security (misal: GCC binary dapat disalahgunakan penyerang yang berhasil injeksi command).

Solusi arsitektural adalah **Multi-Stage Builds**:
- **Stage 1 (Builder):** Berisi *compilers*, *header files*, dan utilitas package manager. Menghasilkan *pre-compiled wheels* atau virtual environment terisolasi.
- **Stage 2 (Runtime Runner):** Menggunakan base image *distroless* atau *slim OS*. Hanya menyalin artefak virtual environment yang telah selesai dikompilasi dari Stage 1. Menjalankan container dengan non-root user (UID 10001) guna memitigasi eskalasi privilege ke host kernel.

### 5.2 Kubernetes Pod Lifecycle, POSIX Signals, dan Graceful Eviction
Saat Kubernetes memutuskan untuk men-terminate Pod (misal: akibat autoscaler scale-down atau node draining untuk maintenance):
1. **Pre-Stop Hook Triggered:** Kubernetes mengeksekusi konfigurasi `preStop` hook jika didefinisikan.
2. **Endpoint Controller Removal:** Pod dihapus dari daftar endpoints Service; lalu lintas baru berhenti dialirkan.
3. **Signal SIGTERM Dispatched:** Kubelet mengirim sinyal `SIGTERM` (Signal 15) ke root process (PID 1) di dalam container.
4. **Grace Period Counter Berjalan:** Kubelet menunggu selama `terminationGracePeriodSeconds` (default: 30 detik).
5. **Worker Graceful Drain:** Aplikasi runtime WAJIB mengintersepsi `SIGTERM`, berhenti mengambil tugas (*batch*) baru dari antrean, menyelesaikan pemrosesan partisi yang sedang berjalan, menulis *commit checkpoint* ke persistent storage, lalu keluar (*exit code 0*).
6. **Signal SIGKILL Dispatched:** Jika runtime aplikasi mengabaikan `SIGTERM` dan grace period habis, Kubelet mengirim `SIGKILL` (Signal 9). Kernel langsung menghancurkan proses secara paksa. Buffer di memori hilang, menghasilkan data rusak/inkonsisten.

### 5.3 Resource Management: Request, Limit, dan Throttling
Kubelet dan Linux CFS (*Completely Fair Scheduler*) mengontrol alokasi resource via cgroups:

- **CPU:** Diukur dalam satuan unit `millicores` (1000m = 1 vCPU).
  - CPU adalah *compressible resource*. Jika pod melampaui `limits.cpu`, kernel TIDAK mematikan proses, melainkan menerapkan **CFS Throttling**. Akibatnya, latensi pipeline analitik Anda melonjak drastis secara misterius.
- **Memory:** Diukur dalam *bytes* (e.g., `512Mi`, `4Gi`).
  - Memory adalah *incompressible resource*. Jika alokasi memory container melampaui batas cgroup `limits.memory`, kernel langsung membunuh pod melalui **OOM-Killer**. 
  - **QoS Classes:**
    - **Guaranteed:** `requests == limits` untuk CPU dan Memory. Probabilitas di-evict paling rendah.
    - **Burstable:** `requests < limits`. Pod dapat menggunakan sisa resource node jika tersedia, namun rentan throttling/eviction.
    - **BestEffort:** Tidak ada `requests` maupun `limits`. Pod pertama yang dimusnahkan Kubelet saat host mengalami starvation.

---

## 6. Production-Ready Code Implementation

Berikut adalah sistem data processing batch worker terisolasi secara penuh. Terdiri atas:
1. **Multi-Stage Dockerfile** dengan optimasi caching, hardening non-root, dan minimalisasi layer.
2. **Production-Ready Python Worker Engine** yang menangani parsing data batch, POSIX signal lifecycle, dan commit status.
3. **Enterprise Kubernetes Job Manifest** dengan volume mounts temporer berbasis RAM, security context, resource boundary, dan affinity.

### 6.1 Dockerfile (Multi-Stage Production Build)

Simpan file ini dengan nama `Dockerfile`.

```dockerfile
# ==============================================================================
# Stage 1: Build & Dependencies Compiler
# ==============================================================================
FROM python:3.11-slim-bookworm AS builder

# Set build-time environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install compiler dependencies yang dibutuhkan oleh C-extensions (PyArrow/DuckDB)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Buat virtual environment terisolasi
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency definition
COPY requirements.txt .

# Compile & install python packages
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# ==============================================================================
# Stage 2: Final Runtime Distroless-like Minimal Image
# ==============================================================================
FROM python:3.11-slim-bookworm AS runner

# Buat user non-privileged non-root khusus data runtime
RUN groupadd --gid 10001 dataops && \
    useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash dataops

# Install runtime dynamic shared libraries saja (tanpa compiler)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Salin pre-compiled virtual environment dari Stage 1
COPY --from=builder --chown=dataops:dataops /opt/venv /opt/venv
COPY --chown=dataops:dataops . /app

# Set runtime environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TEMP_SCRATCH_DIR="/tmp/scratch"

# Siapkan direktori scratch untuk scratch space DuckDB/PyArrow
RUN mkdir -p ${TEMP_SCRATCH_DIR} && \
    chown -R dataops:dataops ${TEMP_SCRATCH_DIR}

# Lepas seluruh elevated root permissions
USER 10001:10001

# Run entrypoint script
ENTRYPOINT ["python", "/app/worker.py"]
```

### 6.2 Application Code: `worker.py` (Graceful Signal Handler Data Engine)

Simpan file ini dengan nama `worker.py`.

```python
"""
Data Pipeline Worker Engine.
Mengonsumsi batch data mentah, melakukan agregasi analitik via DuckDB,
dan mengelola lifecycle eksekusi dengan intercept POSIX signals (SIGTERM, SIGINT).
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Final, List, Optional

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

# Setup Logging Standard JSON / Production Friendly
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [PID:%(process)d] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger: Final[logging.Logger] = logging.getLogger("DataPipelineWorker")


@dataclass(frozen=True)
class WorkerConfig:
    scratch_dir: Path
    output_dir: Path
    batch_size: int = 50_000
    total_batches: int = 10

    @classmethod
    def from_env(cls) -> WorkerConfig:
        scratch = Path(os.getenv("TEMP_SCRATCH_DIR", "/tmp/scratch"))
        output = Path(os.getenv("OUTPUT_DIR", "/tmp/output"))
        batch_size = int(os.getenv("BATCH_SIZE", "50000"))
        total_batches = int(os.getenv("TOTAL_BATCHES", "10"))
        
        scratch.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        
        return cls(
            scratch_dir=scratch,
            output_dir=output,
            batch_size=batch_size,
            total_batches=total_batches,
        )


class GracefulKiller:
    """Mendeteksi sinyal terminasi OS (SIGINT, SIGTERM) dan memicu state shutdown."""

    def __init__(self) -> None:
        self.kill_now: bool = False
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum: int, frame: Optional[FrameType]) -> None:
        sig_name = signal.Signals(signum).name
        logger.warning(
            f"Sinyal {sig_name} ({signum}) diterima! Mengaktifkan mode graceful shutdown..."
        )
        self.kill_now = True


class BatchProcessor:
    """Engine pemrosesan data dengan proteksi persistensi state."""

    def __init__(self, config: WorkerConfig, killer: GracefulKiller) -> None:
        self.config = config
        self.killer = killer
        self.db_conn = duckdb.connect(
            database=str(self.config.scratch_dir / "worker_scratch.duckdb")
        )
        self._init_duckdb()

    def _init_duckdb(self) -> None:
        # Batasi konsumsi thread dan disk swap DuckDB di dalam cgroup boundaries
        self.db_conn.execute("SET threads TO 2;")
        self.db_conn.execute(f"SET temp_directory='{self.config.scratch_dir}';")
        self.db_conn.execute("SET max_memory='1.5GB';")

    def synthesize_mock_data(self, batch_idx: int) -> pa.Table:
        """Membuat payload Arrow sintetis guna simulasi load memory & processing."""
        records = self.config.batch_size
        logger.info(f"Generating data sintetis batch #{batch_idx} ({records} rows)...")
        
        user_ids = pa.array([f"USR_{i}_{batch_idx}" for i in range(records)], type=pa.string())
        values = pa.array([float(i * 1.5) for i in range(records)], type=pa.float64())
        timestamps = pa.array([int(time.time())] * records, type=pa.int64())

        return pa.Table.from_arrays(
            [user_ids, values, timestamps],
            names=["user_id", "metric_value", "timestamp"],
        )

    def process_and_flush(self, batch_idx: int, table: pa.Table) -> Path:
        """Memproses data via DuckDB dan menuliskan partitioned Parquet."""
        target_path = self.config.output_dir / f"processed_batch_{batch_idx}.parquet"
        
        # Eksekusi in-memory DuckDB query langsung atas Arrow Table
        self.db_conn.register("current_arrow_batch", table)
        query = """
            SELECT 
                user_id,
                metric_value,
                timestamp,
                metric_value * 2.5 AS adjusted_metric,
                CASE WHEN metric_value > 10000.0 THEN 'HIGH' ELSE 'LOW' END AS tier
            FROM current_arrow_batch
        """
        result_arrow = self.db_conn.execute(query).arrow()
        self.db_conn.unregister("current_arrow_batch")

        # Tulis partisi parquet dengan Snappy compression
        pq.write_table(
            result_arrow,
            where=target_path,
            compression="snappy",
            use_dictionary=True,
        )
        return target_path

    def run_pipeline(self) -> None:
        logger.info("Memulai iterasi batch processing loop.")
        processed_files: List[Path] = []

        for batch_idx in range(1, self.config.total_batches + 1):
            if self.killer.kill_now:
                logger.warning(
                    f"Pipeline diinterupsi sebelum memproses batch #{batch_idx}. Melakukan cleaning..."
                )
                self._safe_checkpoint(processed_files)
                sys.exit(0)

            t0 = time.perf_counter()
            arrow_table = self.synthesize_mock_data(batch_idx)
            written_file = self.process_and_flush(batch_idx, arrow_table)
            processed_files.append(written_file)
            elapsed = time.perf_counter() - t0

            logger.info(
                f"Batch #{batch_idx} sukses ditulis ke {written_file} dalam {elapsed:.2f} detik."
            )
            
            # Simulasi latensi I/O & cek sinyal di celah iterasi
            time.sleep(1.0)

        logger.info("Seluruh batch berhasil diproses secara penuh tanpa interupsi.")
        self._safe_checkpoint(processed_files)

    def _safe_checkpoint(self, files: List[Path]) -> None:
        """Commit metadata progress."""
        logger.info(f"Writing checkpoint metadata untuk {len(files)} file berhasil...")
        metadata_file = self.config.output_dir / "manifest.chk"
        with open(metadata_file, "a") as f:
            for p in files:
                f.write(f"{p.name}\n")
        self.db_conn.close()
        logger.info("Checkpoint status berhasil di-commit. Worker siap terminated.")


def main() -> None:
    logger.info("Starting up Data Processing Worker Micro-Engine...")
    config = WorkerConfig.from_env()
    killer = GracefulKiller()
    processor = BatchProcessor(config=config, killer=killer)

    try:
        processor.run_pipeline()
    except Exception as exc:
        logger.critical(f"FATAL Pipeline Crash: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

### 6.3 Dependensi Pip: `requirements.txt`

```text
duckdb==0.10.0
pyarrow==15.0.0
```

### 6.4 Kubernetes Manifest (`batch-job.yaml`)

Manifest orkestrasi lengkap dengan proteksi memory limits, affinity, dan `emptyDir` scratch space.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: data-lake-processor-job
  namespace: data-platform
  labels:
    app.kubernetes.io/name: parquet-aggregator
    app.kubernetes.io/part-of: lakehouse-etl
spec:
  # Pod retry maksimal 3 kali sebelum Job dideklarasikan Failed secara permanen
  backoffLimit: 3
  # Bersihkan pod otomatis 300 detik setelah selesai (mencegah akumulasi stale pod metadata di etcd)
  ttlSecondsAfterFinished: 300
  template:
    metadata:
      labels:
        app.kubernetes.io/name: parquet-aggregator
    spec:
      restartPolicy: OnFailure
      # Memberikan waktu 60 detik bagi worker untuk menangkap SIGTERM dan menulis checkpoint
      terminationGracePeriodSeconds: 60
      
      # Keamanan runtime pod level (Principle of Least Privilege)
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault

      # Init Container: Verifikasi ketersediaan dependency upstream sebelum core runner aktif
      initContainers:
        - name: check-prerequisites
          image: busybox:1.36.1
          command: ['sh', '-c', 'echo "Verifying mounts and upstream network..."; test -d /tmp/scratch']
          volumeMounts:
            - name: scratch-volume
              mountPath: /tmp/scratch
          resources:
            limits:
              cpu: "100m"
              memory: "64Mi"
            requests:
              cpu: "50m"
              memory: "32Mi"

      containers:
        - name: data-worker
          image: myregistry.internal.net/dataops/lake-worker:v1.2.0
          imagePullPolicy: IfNotPresent
          env:
            - name: BATCH_SIZE
              value: "100000"
            - name: TOTAL_BATCHES
              value: "5"
            - name: TEMP_SCRATCH_DIR
              value: "/tmp/scratch"
            - name: OUTPUT_DIR
              value: "/tmp/output/data"
          
          # Bound resource terdefinisi secara presisi (QoS: Burstable to near Guaranteed)
          resources:
            requests:
              cpu: "1000m"      # 1 core CPU dialokasikan
              memory: "2Gi"       # 2 Gigabyte RAM direservasi
              ephemeral-storage: "1Gi"
            limits:
              cpu: "2000m"      # Throttling limit 2 core
              memory: "3Gi"       # Ambang OOM-Killed (Hard Limit)
              ephemeral-storage: "5Gi"

          # Restriksi kapabilitas keamanan kernel container
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: false
            capabilities:
              drop:
                - ALL

          volumeMounts:
            - name: scratch-volume
              mountPath: /tmp/scratch
            - name: output-volume
              mountPath: /tmp/output/data

      volumes:
        # RAM/Fast NVMe Ephemeral storage untuk komputasi sementara DuckDB
        - name: scratch-volume
          emptyDir:
            medium: Memory
            sizeLimit: 1Gi
        # Persistensi data lokal host atau persistent volume claim
        - name: output-volume
          emptyDir: {}
```

---

## 7. Edge Cases & Failure Modes

| Edge Case / Failure Mode | Deteksi & Gejala | Akar Masalah (Root Cause) | Solusi Arsitektural / Recovery |
| :--- | :--- | :--- | :--- |
| **Silent Node OOMKilled (Exit Code 137)** | Pod tiba-tiba menghilang atau berstatus `OOMKilled`. Tidak ada stack trace error di log aplikasi. | Alokasi `limits.memory` lebih rendah dari konsumsi memori aktual data batch (e.g., *skewed partition* menghasilkan 10x ukuran normal). | 1. Konfigurasi `limits.memory` berbasis kalkulasi $P_{99}$ burst.<br>2. Terapkan spilling-to-disk pada DuckDB/Spark.<br>3. Gunakan streaming read/write alih-alih me-load seluruh dataset ke memory sekaligus. |
| **CFS CPU Throttling** | Waktu eksekusi pipeline melonjak dari 5 menit menjadi 45 menit tanpa ada error log. | CPU CFS bandwidth quota terlalu ketat. Container mencapai batas `limits.cpu` per-interval 100ms. | 1. Naikkan `limits.cpu` atau hilangkan limit CPU (biarkan hanya `requests.cpu`) pada cluster data compute yang dedicated.<br>2. Gunakan multi-threading terukur sesuai jatah vCPU. |
| **Zombie Init Process (PID 1 Leak)** | Pod macet saat di-terminate; selalu menunggu hingga batas maksimal `terminationGracePeriodSeconds` lalu mati via `SIGKILL`. | Script dieksekusi melalui shell wrapper seperti `CMD ./run.sh` alih-alih bentuk exec `CMD ["python", "app.py"]`. Shell tidak meneruskan sinyal POSIX ke subproses Python. | Gunakan format `ENTRYPOINT ["executable", "param"]` langsung atau gunakan init runner seperti `tini` (`ENTRYPOINT ["/usr/bin/tini", "--", "python", "worker.py"]`). |
| **Node Disk Pressure & Eviction** | Pod di-evict dengan pesan: *The node had condition: [DiskPressure]*. | Driver analytic menulis temporary swap files/spill ke root layer filesystem container, menghabiskan disk host OS. | Mount direktori sementara ke `emptyDir` dengan batasan `sizeLimit`, atau pasang volume penyimpanan berbasis PersistentVolume/CSI NVMe terpisah. |
| **ImagePullBackOff / Throttling Registry** | Worker Job gagal berputar saat auto-scaling mendadak berskala ribuan node. | Docker Hub / Registry privat mengalami API rate-limiting atau koneksi bottleneck akibat image layer berukuran gigabyte di-download serentak. | 1. Kecilkan image menggunakan multi-stage build.<br>2. Gunakan image caching proxy lokal (*Harbor/Dragonfly*).<br>3. Gunakan image pre-pulling daemon sets. |

---

## 8. Trade-offs & Alternatif Solusi

Setiap keputusan arsitektur orkestrasi memiliki konsekuensi trade-off:

```
                    KOMPLEKSITAS OPERASIONAL
                               ^
                               |                               [*] Kubernetes
                               |                              /
                               |                    [*] HashiCorp Nomad
                               |                   /
                               |         [*] AWS ECS
                               |        /
                               | [*] Docker Compose
                               +-------------------------------------------------> SKALABILITAS & FITUR
```

### 1. Docker Compose vs. Kubernetes
- **Docker Compose:**
  - *Kelebihan:* Setup instan, konfigurasi minimal, ideal untuk siklus *local development* dan CI pipeline sederhana.
  - *Kekurangan:* Tidak memiliki native distributed scheduling, tidak ada dynamic service autoscaling, tidak ada self-healing lintas server fisik (single host failure point).
  - *Rekomendasi:* Batasi penggunaannya hanya untuk pengujian unit lokal / development laptop.

### 2. Kubernetes vs. HashiCorp Nomad
- **HashiCorp Nomad:**
  - *Kelebihan:* Jauh lebih ringan daripada K8s, binary tunggal, integrasi deklaratif fleksibel (dapat mengorkestrasi binary mentah, Java JAR, dan container OCI sekaligus).
  - *Kekurangan:* Ekosistem tooling pihak ketiga (monitoring, CRD data, KEDA autoscaling) jauh lebih terbatas dibanding K8s.
  - *Rekomendasi:* Gunakan jika organisasi memiliki keterbatasan engineering resources untuk mengelola overhead K8s control-plane.

### 3. Kubernetes Native Job vs. Argo Workflows / Apache Airflow on K8s
- **Kubernetes Native Job:**
  - *Kelebihan:* Tidak memerlukan instalasi custom controller eksternal. Sangat baik untuk task single-execution terisolasi.
  - *Kekurangan:* Sulit memetakan dependensi kompleks (DAG - Directed Acyclic Graph) antar-job yang berantai.
  - *Rekomendasi:* Gunakan K8s Native Job sebagai execution unit akhir yang di-trigger oleh orchestrator level tinggi seperti Airflow (via `KubernetesPodOperator`) atau Dagster/Argo.

---

## 9. Best Practices & Standar Industri

1. **Prinsip Single Responsibility Process:** Satu container hanya mengeksekusi satu proses logis. Jangan memasang background cron daemon, SSH server, atau syslog collector dalam satu container bersama data worker.
2. **Deterministic Version Pinning:**
   - DILARANG menggunakan tag `:latest` pada production container image. Tag `:latest` menyebabkan deployment tidak bersifat deterministik.
   - Gunakan kombinasi Git Commit SHA atau Semantic Versioning (`:v1.2.4-sha.8fbc2a`).
3. **Immutability & Statelessness:**
   - Desain data container agar *stateless*. Jika container mati di tengah proses, state tidak boleh bergantung pada file lokal internal container. State pipeline wajib tersimpan di *metadata store* eksternal atau checkpointed files.
4. **Keamanan Eksekusi (Hardening Container):**
   - Jalankan container dengan `readOnlyRootFilesystem: true` dan mount `emptyDir` hanya pada folder yang mutlak memerlukan operasi penulisan disk (`/tmp`).
   - Hapus seluruh capability Linux (`drop: ["ALL"]`) dan jangan berikan akses root socket Docker (`/var/run/docker.sock`) ke data pod.
5. **Observability via Structured Logging:**
   - Format log data processing pod wajib dialirkan ke `stdout`/`stderr` dalam format **JSON** agar dapat di-parse otomatis oleh log collector (FluentBit, Vector, Promtail).

---

## 10. Hands-on Lab Exercise

### Skenario Lab
Anda diminta untuk membangun dan menguji pipeline batch processing terisolasi secara end-to-end:
1. Membangun *hardened* multi-stage Docker image dari source code di Bab 6.
2. Melakukan deployment Job ke kluster Kubernetes lokal (Minikube / KinD).
3. Menguji responsivitas graceful shutdown container terhadap sinyal `SIGTERM` secara riil.

### Langkah 1: Setup Local Cluster & Namespace

```bash
# 1. Jalankan cluster KinD (Kubernetes in Docker) jika belum aktif
kind create cluster --name dataops-lab

# 2. Buat namespace khusus data platform
kubectl create namespace data-platform
```

### Langkah 2: Build & Load Container Image

```bash
# 1. Buat direktori kerja dan salin Dockerfile, worker.py, requirements.txt dari Bab 6
mkdir -p /tmp/lake-job && cd /tmp/lake-job

# (Pastikan file Dockerfile, worker.py, dan requirements.txt tersedia di direktori ini)

# 2. Build multi-stage container image
docker build -t myregistry.internal.net/dataops/lake-worker:v1.2.0 .

# 3. Load image langsung ke dalam cluster KinD (tanpa perlu push ke external registry)
kind load docker-image myregistry.internal.net/dataops/lake-worker:v1.2.0 --name dataops-lab
```

### Langkah 3: Deploy Batch Job Manifest

```bash
# Deploy manifest Kubernetes Job
kubectl apply -f batch-job.yaml

# Pantau pembuatan pod dan eksekusi init-containers
kubectl get pods -n data-platform -w
```

### Langkah 4: Verifikasi Log dan Graceful Termination Test

Buka dua terminal terpisah:

**Terminal 1 (Monitoring Log):**
```bash
# Dapatkan nama Pod Job yang sedang berjalan
POD_NAME=$(kubectl get pods -n data-platform -l app.kubernetes.io/name=parquet-aggregator -o jsonpath="{.items[0].metadata.name}")

# Stream output log proses komputasi data
kubectl logs -n data-platform $POD_NAME -c data-worker -f
```

**Terminal 2 (Simulasi Kubernetes Pod Interruption / Eviction):**
```bash
# Saat Terminal 1 memperlihatkan "Generating data sintetis batch #2...",
# kirim sinyal DELETE (ini memicu urutan Kubelet SIGTERM graceful drain)
kubectl delete pod -n data-platform $POD_NAME
```

### Evaluasi Output Terminal 1:
Verifikasi bahwa worker **TIDAK crash seketika**, melainkan menangkap sinyal POSIX dan melakukan commit checkpoint:
```text
202X-XX-XX XX:XX:XX [INFO] [PID:1] Batch #2 sukses ditulis ke /tmp/output/data/processed_batch_2.parquet dalam 0.45 detik.
202X-XX-XX XX:XX:XX [WARNING] [PID:1] Sinyal SIGTERM (15) diterima! Mengaktifkan mode graceful shutdown...
202X-XX-XX XX:XX:XX [WARNING] [PID:1] Pipeline diinterupsi sebelum memproses batch #3. Melakukan cleaning...
202X-XX-XX XX:XX:XX [INFO] [PID:1] Writing checkpoint metadata untuk 2 file berhasil...
202X-XX-XX XX:XX:XX [INFO] [PID:1] Checkpoint status berhasil di-commit. Worker siap terminated.
```

Pod keluar secara bersih (*Clean Exit Code 0*), menjamin pipeline tidak menghasilkan corrupt state pada downstream data lakehouse. Hubungkan kembali node atau submit ulang Job; scheduler akan meneruskan eksekusi dari batch index selanjutnya.