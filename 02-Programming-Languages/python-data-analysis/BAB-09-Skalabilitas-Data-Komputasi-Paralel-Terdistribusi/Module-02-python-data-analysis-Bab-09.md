# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 09: Skalabilitas Data & Komputasi Paralel / Terdistribusi**  
**Track: Python Data Analysis (Enterprise Grade)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan memiliki kompetensi tingkat lanjut untuk:
1. **Menganalisis dan Memilih Engine Komputasi Terdistribusi**: Mengidentifikasi trade-off teknis antara Dask (Task Graph & Dataframe terdistribusi), Ray (Dynamic Task & Actor Model dengan Plasma Shared Memory), dan Polars Streaming Engine untuk beban kerja out-of-core berukuran multi-terabyte.
2. **Merancang Topologi & Alokasi Memori Produksi**: Mengonfigurasi arsitektur worker, partisi data, chunk sizing, dan parameter memory spilling (NVMe swap) guna mengeliminasi risiko *Out-Of-Memory (OOM)* pada lingkungan cluster Kubernetes.
3. **Mengoptimalkan Pipeline Data Skala Besar**: Menghilangkan *serialization bottleneck*, meminimalkan *data shuffling overhead*, dan menerapkan teknik *zero-copy memory access* berbasis Apache Arrow IPC.
4. **Menerapkan Observabilitas & Fault Tolerance**: Membangun mekanisme pemantauan task state, retry strategy, backpressure handling, dan diagnostic profiling pada cluster terdistribusi.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
* Arsitektur internal CPython: GIL (Global Interpreter Lock), `multiprocessing`, `threading`, dan buffer protocol.
* Konsep dasar Arrow Memory Format: ChunkedArray, RecordBatch, zero-copy slicing.
* Jaringan dasar & Linux OS internals: TCP socket buffering, file descriptors, virtual memory, memory swapping (page cache, dirty pages), cgroups v2.
* Kontainerisasi & Orkesstrasi: Docker multi-stage build, Kubernetes primitives (StatefulSets, Headless Services, Resource Limits & Requests).

---

## 3. Concept & Internal Architecture (Mendalam)

Komputasi data terdistribusi pada Python modern berfokus pada dua tantangan utama: **CPython GIL** dan **Overhead Serialisasi Data Antar-Proses**. Modul ini membedah arsitektur internal dua ekosistem terdepan: **Dask Distributed** dan **Ray Core**, serta integrasinya dengan **Apache Arrow**.

```
+-------------------------------------------------------------------------------+
|                           DASK vs RAY ARCHITECTURE                            |
+-------------------------------------------------------------------------------+
|                                                                               |
| [Dask Distributed: Centralized Dynamic Graph]                                 |
|                                                                               |
|     +-------------------------+                                               |
|     |  Dask Client (Driver)   |                                               |
|     +------------+------------+                                               |
|                  | (Graph Submission: High-Level Task Graph)                  |
|                  v                                                            |
|     +-------------------------+                                               |
|     | Distributed Scheduler   | <=== Event Loop (Tornado), In-Memory State    |
|     +------------+------------+      Tracks task states: waiting, ready, etc. |
|                  |                                                            |
|         +--------+--------+                                                   |
|         | Comm (Tornado)  |                                                   |
|         v                 v                                                   |
|  +--------------+  +--------------+                                           |
|  | Dask Worker  |  | Dask Worker  |                                           |
|  | [ThreadPool] |  | [ThreadPool] | ===> Spills to NVMe if RAM > Limit (85%) |
|  | In-Process   |  | In-Process   |                                           |
|  | Local Memory |  | Local Memory |                                           |
|  +--------------+  +--------------+                                           |
|                                                                               |
+-------------------------------------------------------------------------------+
|                                                                               |
| [Ray Core: Decentralized Bottom-Up Scheduling & Shared Plasma Store]          |
|                                                                               |
|     +-------------------------------------------------------------+           |
|     | Global Control Store (GCS) - Metadata, Actor Registration    |           |
|     +-------------------------------------------------------------+           |
|                     ^                                                         |
|                     | Heartbeats / Lineage                                    |
|     +---------------+---------------+                                         |
|     | Node A                        | Node B                                  |
|     |  +-------------------------+  |  +-------------------------+            |
|     |  | Raylet (Local Scheduler)|  |  | Raylet (Local Scheduler)|            |
|     |  +------------+------------+  |  +------------+------------+            |
|     |               |               |               |                         |
|     |   +-----------+-----------+   |   +-----------+-----------+             |
|     |   | Worker    | Worker    |   |   | Worker    | Worker    |             |
|     |   | Process 1 | Process 2 |   |   | Process 1 | Process 2 |             |
|     |   +-----+-----+-----+-----+   |   +-----+-----+-----+-----+             |
|     |         |           |         |         |           |                   |
|     |   +-----v-----------v-----+   |   +-----v-----------v-----+             |
|     |   |  Plasma Object Store  |<=====>|  Plasma Object Store  |             |
|     |   |  (Shared Mem / POSIX) |  P2P  |  (Shared Mem / POSIX) |             |
|     |   +-----------------------+  RDMA |+----------------------+             |
|     |               Zero-Copy Read via Apache Arrow                           |
|     +-------------------------------------------------------------+           |
+-------------------------------------------------------------------------------+
```

### 3.1 Dask Distributed Architecture

1. **High-Level Graph Optimization**: Dask membangun Directed Acyclic Graph (DAG) menggunakan representasi fungsional murni. Graph dioptimasi sebelum dieksekusi (culling unneeded branches, fusing trivial operations seperti `map` beruntun menjadi satu fungsi task untuk mengurangi penjadwalan).
2. **Dynamic Centralized Scheduler**:
   * Scheduler memantau dependensi data, ketersediaan worker, dan footprint memori.
   * State machine scheduler melacak status setiap key: `waiting`, `ready`, `queued`, `running`, `memory`, `released`, `erred`.
   * Penjadwalan data-locality aware: Scheduler mengarahkan task baru ke worker yang telah menampung data input di memori lokal guna menekan bandwidth jaringan.
3. **Memory Management & Spilling**:
   * Worker memonitor memory usage secara periodik melalui modul `psutil`.
   * Tiga ambang batas kritis:
     * `target` (default: ~60%): Worker mulai memindahkan partisi data yang tidak aktif ke disk lokal (NVMe SSD).
     * `spill` (default: ~70%): Worker memaksa serialisasi data ke storage secara agresif.
     * `pause` (default: ~80%): Worker berhenti menerima task baru dari Scheduler sampai garbage collection melepaskan memory.
     * `terminate` (default: ~95%): OS atau container runtime (cgroups) membunuh worker via `SIGKILL` (Exit Code 137).

### 3.2 Ray Architecture

1. **Bottom-Up Decentralized Scheduling**:
   * Alih-alih satu scheduler terpusat memproses jutaan tasks, Ray menggunakan **Raylet** lokal pada setiap instance/node.
   * Task dievaluasi pertama kali oleh Local Scheduler di Raylet. Jika kapasitas lokal habis atau dependensi data berada di remote node, Raylet melakukan *work-stealing* atau *node forwarding* ke Raylet lain melalui konsultasi dengan Global Control Store (GCS).
2. **Plasma Object Store**:
   * Shared-memory object store yang dialokasikan di Virtual Memory (RAM) berbasis POSIX shared memory primitives (`/dev/shm`).
   * Menggunakan Apache Arrow memory layout. Ketika Node Worker A menulis dataframe, Worker B, C, dan D pada node yang sama dapat membaca dataframe tersebut secara bersamaan via pointer memory tanpa proses de-serialisasi (Zero-Copy Read).
   * Menghindari limitasi Single GIL per-proses: beberapa worker dapat mengakses objek yang sama secara read-only tanpa duplikasi bytes di RAM.

---

## 4. Why & What

| Dimensi | Dask Distributed | Ray Core | Polars Streaming (Out-of-Core) |
| :--- | :--- | :--- | :--- |
| **Abstraksi Utama** | `dask.dataframe`, `dask.array`, Task Graphs | Ray Tasks (stateless), Ray Actors (stateful) | Streaming DataFrames, Chunked Batches |
| **Karakteristik Workload** | Tabular ETL, Data Science workflows, integrasi native scikit-learn / pandas | Machine Learning skala besar, Distributed Training, Actor-based Stateful Services, Dynamic Graphs | Manipulasi tabular lokal single-node dengan batas RAM terlampaui |
| **Penyimpanan Objek** | In-process memory worker + Spill to local disk | Plasma Object Store (Zero-Copy Shared Memory per-node) | Single Process Threaded Memory Pool (Rust Native) |
| **Skalabilitas Batas Node** | Ratusan node (terkendala performa centralized scheduler di ribuan task/sec) | Ribuan node (desentralisasi via GCS dan Raylets) | Single Node (Scale-Up vertical, CPU thread saturation) |
| **Overhead Scheduling** | ~200-500 microsecond per task | ~10-20 microsecond per task | Sub-microsecond (Rust execution engine, vectorized) |

### Mengapa Perlu Arsitektur Ini?
Ketika memproses dataset berukuran 100 GB hingga puluhan Terabyte:
1. **Pandas Tradisional** gagal karena memuat seluruh data ke memory footprint, mensyaratkan overhead RAM 5x hingga 10x dari ukuran file di disk.
2. **Multiprocessing Bawaan** gagal karena memerlukan serialisasi `pickle` penuh bolak-balik via OS pipes, menghasilkan latency tinggi dan memory footprint berlipat ganda.
3. **Apache Spark** sering kali memunculkan biaya operasional tinggi dan runtime JVM yang terpisah dari ekosistem Native C/Python data science (PyTorch, SciPy, Numba). Dask dan Ray berjalan murni di layer C/C++/Python, meminimalkan translation layer.

---

## 5. How (Workflow Detail)

Alur kerja implementasi arsitektur komputasi terdistribusi tingkat enterprise:

```
[Ingestion: Raw Object Storage S3/GCS]
                  |
                  v
[Partition Sizing Strategy (Optimal: 100MB - 250MB per chunk uncompressed)]
                  |
                  v
[Graph Construction & Predicate Pushdown / Column Pruning]
                  |
                  v
[Distributed Execution Cluster (K8s: KubeRay / Dask Gateway)]
                  |
    +-------------+-------------+
    |                           |
[Worker Node 1]           [Worker Node 2]
    |                           |
    v                           v
[Local Compute -> Apache Arrow IPC -> Zero-Copy Shuffle via Plasma/UCX]
                  |
                  v
[Monitoring & Health Check (Prometheus Exporter + OpenTelemetry)]
                  |
                  v
[Persistence: Target Parquet / Iceberg Table with Snappy/ZSTD Compression]
```

1. **Partitioning**: Hindari partisi terlalu kecil (*task scheduler thrashing*) atau terlalu besar (*OOM Worker Spilling*). Batas ideal partisi di memori adalah 100 MB hingga 250 MB.
2. **Scheduling Optimization**: Kirim predicate filtering sedini mungkin ke format storage Parquet (`filters=[('status', '==', 'SETTLED')]`) untuk mengurangi I/O network.
3. **Execution**: Eksekusi task graph dengan batasan resource strict.
4. **Shuffling & Spilling**: Gunakan unified communication protocol (UCX) atau NVMe Direct Storage jika beban komputasi melibatkan `merge`, `groupby`, atau `join` skala besar.

---

## 6. Analogy & Diagram ASCII

### Analogi Operasional: Dask vs. Ray vs. Multiprocessing

* **Python Multiprocessing (Pemberian Tugas via Fotokopi)**: Setiap pekerja duduk di ruangan terisolasi. Jika satu pekerja membutuhkan dokumen 100 halaman dari pekerja lain, dokumen harus difotokopi seluruhnya (`pickle`), dikirimkan lewat kurir lambat (`IPC Pipe`), lalu dibaca ulang (`unpickle`). Ruangan cepat penuh oleh tumpukan kertas.
* **Dask Distributed (Mandor Proyek Terpusat)**: Satu mandor sentral memegang buku cetak biru master. Mandor mengatur instruksi presisi: "Tukang A potong pipa 1, lalu hasilnya serahkan ke Tukang B." Bila meja kerja Tukang A penuh, ia menaruh sebagian material di gudang bawah tanah (NVMe Spilling).
* **Ray Core (Papan Informasi Terbuka / Balai Kerja Shared Memory)**: Balai kerja memiliki meja kaca raksasa tembus pandang (Plasma Store). Ketika Desainer A meletakkan rancangan di atas meja kaca, ratusan tukang lain dapat langsung melihat dan menggunakannya tanpa fotokopi ulang (Zero-Copy Memory). Manajer lokal di setiap divisi (Raylet) mendistribusikan pekerjaan tanpa perlu menelepon kantor pusat untuk setiap baut yang dipasang.

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Dynamic Parallelism dengan Dask Task Graph vs Ray Tasks

Berikut adalah perbandingan deklarasi low-level dynamic tasks untuk komputasi terdistribusi:

```python
# ============================================================================
# DASK LOW-LEVEL TASK GRAPH (dask.delayed)
# ============================================================================
import dask
from dask import delayed
import time

@delayed
def fetch_partition(partition_id: int) -> list[int]:
    # Simulasi I/O
    return [i * partition_id for i in range(1000)]

@delayed
def aggregate_partition(data: list[int]) -> int:
    return sum(data)

@delayed
def consolidate_results(scalars: list[int]) -> int:
    return sum(scalars)

# Graph Declaration (Lazy Evaluation)
partitions = [fetch_partition(pid) for pid in range(1, 5)]
aggregates = [aggregate_partition(p) for p in partitions]
dask_total_graph = consolidate_results(aggregates)

# Materialisasi Graph ke Komputasi
dask_final_result = dask_total_graph.compute()
print(f"[Dask Result]: {dask_final_result}")


# ============================================================================
# RAY DISTRIBUTED TASKS (Core Primitives)
# ============================================================================
import ray

# Inisialisasi local ray instance
if not ray.is_initialized():
    ray.init(ignore_reinit_error=True, num_cpus=4)

@ray.remote
def fetch_partition_ray(partition_id: int) -> list[int]:
    return [i * partition_id for i in range(1000)]

@ray.remote
def aggregate_partition_ray(data: list[int]) -> int:
    return sum(data)

@ray.remote
def consolidate_results_ray(scalars: list[int]) -> int:
    return sum(scalars)

# Futures Execution (Eager Scheduling with Object References)
ray_futures = [fetch_partition_ray.remote(pid) for pid in range(1, 5)]
ray_agg_futures = [aggregate_partition_ray.remote(ref) for ref in ray_futures]
ray_total_future = consolidate_results_ray.remote(ray_agg_futures)

# Resolving Object References from Plasma Store
ray_final_result = ray.get(ray_total_future)
print(f"[Ray Result]: {ray_final_result}")

ray.shutdown()
```

---

### 7.2 Practical Example: Enterprise Distributed Batch Aggregator dengan Custom Memory Management & Dask Distributed

Kode berikut mengimplementasikan agregator data transaksional skala besar yang berjalan di Dask Distributed Cluster, dilengkapi konfigurasi worker memory limits, adaptive batching, error retry, dan eksportasi ke Parquet berpartisi.

```python
import os
import sys
import logging
import tempfile
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from typing import Generator
from distributed import Client, LocalCluster, Variable
from distributed.diagnostics.plugin import WorkerPlugin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(processName)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DistributedEngine")

class EnterpriseWorkerEnvironmentPlugin(WorkerPlugin):
    """
    Worker Plugin untuk memastikan setiap worker threadpool memiliki 
    konfigurasi limitasi OS-level dan isolasi memory allocator.
    """
    def setup(self, worker):
        self.worker = worker
        logger.info(f"Worker {worker.address} terhubung. Konfigurasi jemalloc / allocator.")
        # Mengatur konfigurasi jemalloc background threads jika tersedia
        os.environ["MALLOC_CONF"] = "background_thread:true,dirty_decay_ms:30000,muzzy_decay_ms:30000"

    def teardown(self, worker):
        logger.info(f"Worker {worker.address} shutdown.")


def generate_synthetic_workload(
    base_dir: str, 
    num_files: int = 10, 
    rows_per_file: int = 100_000
) -> list[str]:
    """Menghasilkan dataset Parquet sintetis terfragmentasi untuk demonstrasi."""
    os.makedirs(base_dir, exist_ok=True)
    file_paths = []
    
    for idx in range(num_files):
        path = os.path.join(base_dir, f"transactions_part_{idx}.parquet")
        np.random.seed(idx)
        
        df = pd.DataFrame({
            "transaction_id": [f"tx_{idx}_{r}" for r in range(rows_per_file)],
            "account_id": np.random.randint(1000, 9999, size=rows_per_file),
            "amount": np.random.exponential(scale=150.0, size=rows_per_file).round(2),
            "currency": np.random.choice(["USD", "EUR", "IDR", "SGD"], size=rows_per_file),
            "timestamp": pd.date_range("2026-01-01", periods=rows_per_file, freq="s")
        })
        
        table = pa.Table.from_pandas(df)
        pq.write_table(table, path, compression="snappy")
        file_paths.append(path)
        
    return file_paths


def process_partition_out_of_core(file_path: str) -> pd.DataFrame:
    """
    Dipanggil oleh Dask Worker: Membaca file dengan Arrow engine, 
    menghindari footprint pandas yang besar, dan melakukan downcasting type.
    """
    import pyarrow.dataset as ds
    
    # Pruning & Projection via Arrow Dataset API (Zero-Copy)
    dataset = ds.dataset(file_path, format="parquet")
    
    # Hanya proyeksikan kolom agregasi yang relevan
    table = dataset.to_table(
        columns=["account_id", "amount", "currency"],
        filter=(ds.field("amount") > 10.0) # Filter level scan
    )
    
    df_chunk = table.to_pandas(split_blocks=True, self_destruct=True)
    
    # Agregasi lokal per partisi (Pre-aggregation guna menekan shuffle)
    aggregated = (
        df_chunk.groupby(["currency", "account_id"], as_index=False)
        .agg(
            total_amount=pd.NamedAgg(column="amount", aggfunc="sum"),
            transaction_count=pd.NamedAgg(column="amount", aggfunc="count")
        )
    )
    return aggregated


def run_pipeline():
    with tempfile.TemporaryDirectory() as tmp_dir:
        data_dir = os.path.join(tmp_dir, "input_data")
        output_dir = os.path.join(tmp_dir, "output_aggregated.parquet")
        
        logger.info("Menyiapkan dataset sintetis...")
        file_paths = generate_synthetic_workload(data_dir, num_files=8, rows_per_file=50_000)
        
        # Konfigurasi In-Memory Local Cluster dengan Batas Spilling Jelas
        logger.info("Menginisialisasi Dask LocalCluster dengan limitasi memori ketat...")
        cluster = LocalCluster(
            n_workers=2,
            threads_per_worker=2,
            memory_limit="1GB",         # Limit RAM per worker
            memory_target_fraction=0.6, # Mulai spill ke disk di 600MB
            memory_spill_fraction=0.7,  # Agresif spill di 700MB
            memory_pause_fraction=0.85, # Hentikan penerimaan task di 850MB
            local_directory=os.path.join(tmp_dir, "dask_spill_space")
        )
        
        client = Client(cluster)
        client.register_worker_plugin(EnterpriseWorkerEnvironmentPlugin())
        logger.info(f"Dashboard Scheduler aktif pada: {client.dashboard_link}")
        
        try:
            import dask.dataframe as dd
            
            # Memetakan file paths ke delayed executions
            logger.info("Membangun Dynamic Execution Graph...")
            delayed_partitions = [
                dask.delayed(process_partition_out_of_core)(f) 
                for f in file_paths
            ]
            
            # Membangkitkan Dask DataFrame dari objek delayed
            meta = pd.DataFrame({
                "currency": pd.Series(dtype="str"),
                "account_id": pd.Series(dtype="int64"),
                "total_amount": pd.Series(dtype="float64"),
                "transaction_count": pd.Series(dtype="int64")
            })
            
            ddf = dd.from_delayed(delayed_partitions, meta=meta)
            
            # Global Aggregation (Menimbulkan Shuffle terkontrol)
            final_ddf = (
                ddf.groupby(["currency", "account_id"])
                .agg({
                    "total_amount": "sum",
                    "transaction_count": "sum"
                })
                .reset_index()
            )
            
            # Export langsung ke partitioned parquet terdistribusi
            logger.info("Mengeksekusi task graph dan streaming hasil ke Parquet...")
            final_ddf.to_parquet(
                output_dir,
                engine="pyarrow",
                compression="zstd",
                write_index=False
            )
            
            # Validasi Hasil
            validation_table = pq.read_table(output_dir)
            logger.info(
                f"Pipeline Sukses. Baris teragregasi tersimpan: {validation_table.num_rows}"
            )
            
        finally:
            client.close()
            cluster.close()
            logger.info("Cluster berhasil dimatikan dengan aman.")


if __name__ == "__main__":
    run_pipeline()
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Fraud Detection Clickstream & Transaction Enrichment (E-Commerce Skala Asia Tenggara)

* **Volume Data**: 45 TB telemetry log harian (1.2 Miliar event transaksi dan web clickstream).
* **Kendala Arsitektur Lama**:
  * Menggunakan single-cluster Apache Spark yang memakan biaya komputasi AWS EMR sebesar $48,000/bulan.
  * Pipeline Python native (PyTorch feature store & isolation forest anomaly score) memerlukan serialisasi mahal bolak-balik antara JVM memory dan Python Worker via PySpark UDF (Socket Worker IPC). Hal ini menyebabkan CPU idle tinggi menunggu transfer data.
* **Solusi Arsitektur Baru**:
  1. Migrasi ke **Ray Core Cluster yang berjalan di KubeRay (Amazon EKS)** menggunakan armada Spot Instances (tipe c6i.4xlarge untuk compute, r6i.2xlarge untuk Plasma Store).
  2. Implementasi **Ray Datasets** dengan underlying **Apache Arrow buffers**. Clickstream data dibaca langsung dari S3 sebagai Arrow IPC Streams.
  3. Preprocessing, Sessionization, dan Join dilakukan langsung di **Plasma Shared Memory**. Feature array dikonsumsi secara Zero-Copy oleh Ray Actor yang menjalankan PyTorch Model Inference pada GPU yang sama tanpa data copies.
* **Hasil Pengujian Produksi**:
  * **Latency Reduksi**: Waktu pemrosesan batch harian terpangkas dari 6.5 jam menjadi 1 jam 45 menit.
  * **Infrastruktur Cost**: Tagihan AWS terpangkas 58% (menjadi ~$20,000/bulan) karena hilangnya JVM overhead dan adopsi Spot Instance yang toleran terhadap interupsi menggunakan Ray Fault-Tolerant Actor checkpointing.

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
       [Skalabilitas Sentral / Kompleksitas Rendah]
                          DASK
                         /    \
                        /      \
                       /        \
                      /   RAY    \
 [Efisiensi CPU Ekstrem]----------[Skalabilitas Desentral / Stateful Actor]
    POLARS STREAMING
```

| Parameter | Dask Distributed | Ray Core | Polars Streaming Engine |
| :--- | :--- | :--- | :--- |
| **Throughput Single-Node** | Moderat (Overhead koordinasi Python) | Tinggi (C++ Core + Plasma Zero-Copy) | Sangat Tinggi (Native Rust Vectorization & SIMD) |
| **Horizontal Scaling Limits** | Menurun di atas >500 Node (Scheduler CPU maxed out) | Sangat Tinggi (>2000 Node, GCS terdistribusi) | N/A (Hanya Single-Node Scale-Up) |
| **Stateful Processing** | Sulit (Didesain murni fungsional/immutable data DAG) | Native (Ray Actor Model dengan state persisten) | Tidak Didukung (Murni Query Plan Engine) |
| **Operasional & Infrastruktur** | Sangat Rendah (Dapat berjalan ad-hoc tanpa daemon) | Menengah-Tinggi (Perlu Redis/GCS, Raylet daemons) | Nol (Library binary, run as Python import) |
| **Cost Efficiency** | Optimal untuk data tabular 100GB - 2TB | Optimal untuk beban kerja ML/AI multi-node >2TB | Paling Efisien untuk data < Ukuran Disk Node Tunggal |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Memory Leaks Akibat Referensi Terbuka ke Future Objects
* **Symptom**: Penggunaan RAM pada scheduler/driver membengkak perlahan meskipun pekerjaan telah selesai.
* **Root Cause**: Menyimpan referensi objek `distributed.Future` atau `ray.ObjectRef` dalam global dictionary/list. Selama referensi masih hidup di Python memory driver, cluster dilarang menghapus data terkait dari Worker RAM / Plasma Store.
* **Solusi**: Pastikan scope object reference terisolasi atau panggil `del future_ref` secara eksplisit, atau gunakan iterator streaming (`ray.wait` / `as_completed`).

### Mistake 2: Bad Partitioning: "The 1-Million Tiny Tasks Catastrophe"
* **Symptom**: Scheduler Dask menggunakan CPU 100%, tetapi utilitas worker CPU < 5%. Jaringan dipenuhi jutaan paket TCP kecil.
* **Root Cause**: Mempartisi dataset 100 GB ke dalam 1.000.000 chunk masing-masing berukuran 100 KB. Overhead overhead Dask/Ray scheduler (~0.5 ms per task) melebihi durasi kalkulasi partisi itu sendiri.
* **Solusi**: Lakukan repartitioning agar ukuran uncompressed chunk berada di rentang **100 MB hingga 250 MB**.

### Mistake 3: Serialization Failure ("Cannot pickle local object / thread.lock")
* **Symptom**: `TypeError: cannot pickle '_thread.lock' object` saat mengeksekusi `delayed` atau `.remote()`.
* **Root Cause**: Melewatkan koneksi database aktif, file-handler, atau state object CPython yang tidak serializable ke dalam task argument.
* **Solusi**: Jangan lewatkan koneksi client ke dalam task. Inisialisasi koneksi di dalam task execution atau gunakan **Ray Actor** / **Dask Worker Plugin** untuk mengelola koneksi stateful per worker life-cycle.

### Mistake 4: Shuffling Thrashing pada Cluster Saturated Memory
* **Symptom**: Worker mati mendadak dengan Exit Code 137 (`SIGKILL` oleh Linux OOM Killer) selama operasi `merge()` atau `set_index()`.
* **Root Cause**: Semua worker serentak menukar blok partisi (All-to-All shuffle) melewati TCP, memenuhi buffer memori sebelum disk spilling selesai dilakukan.
* **Solusi**: Aktifkan disk-based P2P shuffling di Dask:
  ```python
  import dask
  dask.config.set({"dataframe.shuffle.method": "p2p"})
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Data Locality & Chunk Size**: Verifikasi partisi dataset downstream berukuran minimal 100 MB dan maksimal 500 MB di dalam RAM.
- [ ] **Optimasi Arrow IPC**: Pastikan serialisasi data tabular antar-proses menggunakan format PyArrow, bukan Python native `pickle`.
- [ ] **Kubernetes Cgroups Awareness**: Set Dask/Ray memory limit ke **75% - 80%** dari limit Pod Kubernetes untuk memberikan ruang overhead bagi CPython runtime, glibc allocations, dan dynamic libraries.
- [ ] **Offload Garbage Collection**: Gunakan allocator modern seperti `jemalloc` atau `tcmalloc` untuk menghindari fragmentasi heap memory di Linux:
  ```bash
  export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so
  ```
- [ ] **Graceful Degraded NVMe Spilling**: Pastikan direktori spill menunjuk ke local scratch NVMe mounted disk (bukan network storage seperti NFS atau standard EBS volume yang memiliki IOPS limit).
- [ ] **Headless Service Deployment**: Pada environment Kubernetes, gunakan KubeRay Operator atau Dask Gateway untuk memastikan isolasi multi-tenant dan load balancing yang tepat.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### File Setup:
Buat virtual environment dan install dependency yang dibutuhkan:
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
python3 -m venv .venv
source .venv/bin/activate
pip install dask[complete]==2024.1.0 ray[default]==2.9.0 polars==0.20.5 pyarrow==15.0.0
```

### Langkah Praktikum:
1. **Langkah 1 (`task_graph_profiling.py`)**: Bangun eksekusi Dask delayed pipeline dengan profiling built-in. Tangkap memory footprint dan visualisasikan profil waktu eksekusi.
2. **Langkah 2 (`plasma_zero_copy.py`)**: Tulis data berukuran 1 GB ke Ray Plasma Object Store. Spawn 4 Ray Actor independen yang membaca data yang sama secara serentak. Ukur total alokasi RAM (verifikasi Zero-Copy).
3. **Langkah 3 (`out_of_core_pipeline.py`)**: Implementasikan streaming reader Polars yang melakukan sorting dan aggregation pada dataset yang ukurannya 3x lipat kapasitas RAM sistem lokal, verifikasi parameter disk spill.

---

## 13. Exercise

### Level Easy
Tuliskan script Python menggunakan `dask.delayed` yang memproses 10 buah file CSV sintetis secara paralel, mengekstrak nilai maksimum dari kolom tertentu, dan mengembalikan skalar nilai maksimum absolut. Pastikan graf hanya dievaluasi satu kali pada akhir eksekusi.

### Level Medium
Bangun sistem distributed token count menggunakan **Ray Tasks**:
- Input: List berisi 50 file teks dummy berukuran 20 MB per file.
- Requirement: Gunakan `ray.wait` untuk memproses chunk teks yang selesai lebih cepat (asynchronous completion processing) tanpa memblokir seluruh workflow jika salah satu task lambat.

### Level Hard
Rancang modul custom **Dask Shuffle Engine** yang menerima sebuah Dask DataFrame yang mengalami severe data skew (misal: 80% data bertumpu pada 1 partition key):
- Implementasikan teknik **Salting** (menambahkan random suffix integer pada join keys) secara programmatic pada Task Graph.
- Lakukan re-alignment partisi dan ukur penurunan memory peak pada worker yang menangani skewed partition tersebut.

---

## 14. Challenge

**Skenario**: Sistem Rekomendasi Real-Time E-Commerce memproses event streams clickstream berkapasitas 2 TB per jam.
**Tantangan**:
Rancang arsitektur pipeline terdistribusi end-to-end yang memadukan **Ray Core (Actors)** dan **Polars Lazy Streaming Engine**:
1. Actor pool harus memegang connection pool ke object storage dan bertindak sebagai buffer receiver event data.
2. Setiap kali volume buffer mencapai 1 GB pada sebuah node, serahkan buffer tersebut ke engine lokal Polars tanpa melalui serialize-deserialize network cost.
3. Lakukan kalkulasi User Session Decay Matrix (matrix factorization) out-of-core.
4. Output harus dituliskan kembali ke Storage dalam format Iceberg Partitioned Table.
5. Syarat mutlak: Sistem harus mampu mentoleransi failure di mana 1 worker node mengalami hard termination (`kill -9`) tanpa menyebabkan seluruh job streaming crash atau duplikasi data (Exactly-Once Semantics / Idempotency). Tuliskan arsitektur desain dokumen dan core engine harness implementation-nya.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Basic Questions

#### Q1: Mengapa model serialisasi native Python (`pickle`) tidak efisien untuk komputasi data terdistribusi skala besar?
* **Jawaban**: `pickle` memerlukan proses konversi rekursif dari object model CPython ke stream of bytes, yang menduplikasi memori, mengonsumsi siklus CPU yang signifikan, dan memerlukan rekonsiliasi pointer heap memori penuh saat deserialisasi. Format seperti Apache Arrow menghindari hal ini dengan menata data dalam contiguous columnar memory buffer yang dapat dibaca secara zero-copy.

#### Q2: Apa yang dimaksud dengan konsep Lazy Evaluation pada Dask?
* **Jawaban**: Operasi komputasi yang dipanggil (seperti `.map()`, `.filter()`) tidak langsung dieksekusi saat kode dijalankan. Dask hanya mencatat operasi tersebut sebagai nodes dan edges di dalam Directed Acyclic Graph (DAG). Komputasi fisik hanya dijalankan ketika method `.compute()` atau `.persist()` dipanggil secara eksplisit.

#### Q3: Apa fungsi dari Global Control Store (GCS) pada arsitektur Ray?
* **Jawaban**: GCS adalah distributed storage terpusat (sering kali ditenagai Redis atau state engine internal) yang menyimpan metadata arsitektural: actor registration, task lineage, node heartbeats, dan spesifikasi placement groups, memisahkan data plane dari control plane.

#### Q4: Apa perbedaan mendasar antara `.persist()` dan `.compute()` pada Dask DataFrame?
* **Jawaban**: `.compute()` mengevaluasi graf dan mengonversi seluruh hasil kembali ke driver node sebagai single Python/Pandas object di local memory. `.persist()` mengevaluasi graf tetapi tetap mempertahankan hasil partisi data terdistribusi di dalam memori cluster workers (menghasilkan Dask DataFrame baru).

#### Q5: Mengapa chunk size 1 MB dianggap sebagai anti-pattern pada Dask Distributed?
* **Jawaban**: Karena overhead manajemen scheduler (~0.5 ms per task scheduling overhead) menjadi lebih mahal daripada durasi komputasi data 1 MB itu sendiri. Fenomena ini menciptakan scheduler queue contention dan network overhead yang masif.

---

### 15.2 Intermediate Questions

#### Q6: Bagaimana Plasma Object Store di Ray memungkinkan mekanisme Zero-Copy Read antar proses worker lokal?
* **Jawaban**: Plasma dialokasikan pada Shared Memory POSIX (`/dev/shm`). Objek ditulis dalam skema Apache Arrow. Karena representasi binary di shared memory identik dengan representasi di RAM proses, worker lain pada host yang sama cukup melakukan memory map (`mmap`) ke memory addresses tersebut via pointer Arrow, tanpa menduplikasi bytes ke local heap masing-masing worker.

#### Q7: Apa yang terjadi secara internal ketika Dask Worker mencapai konfigurasi `memory_pause_fraction`?
* **Jawaban**: Worker mengirimkan sinyal ke centralized scheduler untuk sementara waktu mengubah statusnya menjadi un-assignable. Scheduler akan berhenti mendistribusikan task baru ke worker tersebut. Worker memfokuskan threadpool-nya untuk melakukan kompresi dan spilling data aktif ke local disk storage hingga penggunaan RAM turun di bawah threshold target.

#### Q8: Mengapa Polars Streaming Engine sering kali mengungguli Dask DataFrame pada single-node instances?
* **Jawaban**: Polars diimplementasikan dalam Rust, bebas dari overhead CPython GIL, mengeksekusi SIMD vectorization langsung pada register CPU, memanfaatkan Apache Arrow memory chunks secara native, dan memiliki query optimizer internal berbasis pushdown projection dan predicate parsing pada level physical plan Rust, tanpa dynamic interpreter cost.

#### Q9: Bagaimana Ray Actor menangani state concurrency, dan apakah thread-safe secara default?
* **Jawaban**: Secara default, Ray Actor adalah single-threaded event loop. Setiap invocations method `.remote()` pada actor dimasukkan ke dalam antrean (FIFO queue) dan dieksekusi secara sekuensial. Ini memastikan thread-safety secara deterministik tanpa locking primitif eksplisit, kecuali jika secara spesifik dikonfigurasi menggunakan async actor concurrency (`max_concurrency`).

#### Q10: Apa konsekuensi arsitektural dari operasi Shuffle All-to-All pada Dask DataFrame?
* **Jawaban**: Shuffle All-to-All memerlukan $N \times M$ koneksi jaringan (di mana $N$ dan $M$ adalah partisi awal dan akhir). Setiap worker harus membuka soket TCP secara bersamaan ke worker lain, memecah data lokal menjadi partisi-partisi kecil, dan mengirimkannya via network fabric. Hal ini rentan terhadap network saturation, TCP connection drop, dan lonjakan dirty pages pada OS memory.

---

### 15.3 Skenario Kasus Produksi

#### Skenario 1: Worker OOM Silent Kill pada High-Concurrency Cluster
* **Kasus**: Di cluster Kubernetes, Pod Dask Worker sering mati mendadak dengan Exit Code 137. Namun, log Dask scheduler tidak mencatat error traceback apa pun selain sinyal disconnect worker. Parameter Dask `memory_limit` diset ke 8 GB, dan memory request/limit di manifest Pod K8s diset ke 8 GB.
* **Analisis & Solusi**: Cgroup Kubernetes menghentikan Pod melalui host OOM killer karena penggunaan memori total Pod melebihi 8 GB. Dask Worker memory tracker (`psutil`) hanya melacak managed memory dan heap memory Python, tidak mengkalkulasi alokasi memory yang dilakukan library native C/C++ (seperti PyArrow JNI, OpenBLAS, atau un-freed buffers oleh glibc memory fragmentation).
  * **Solusi**: Terapkan safety headroom margin. Berikan resource limit K8s Pod sebesar 10 GB bila batas memori Dask adalah 8 GB (alokasikan ~20% buffer untuk unmanaged C-level memory allocations). Konfigurasikan env variable `MALLOC_ARENA_MAX=2` atau gunakan `jemalloc` untuk membatasi virtual memory allocator fragmentation.

#### Skenario 2: Serialization Failure pada Ray Task Execution
* **Kasus**: Tim Data Engineer mencoba menjalankan task Ray:
  ```python
  import ray
  import psycopg2

  conn = psycopg2.connect("postgresql://...")

  @ray.remote
  def write_to_db(data, connection):
      cursor = connection.cursor()
      cursor.execute(...)
  
  ray.get(write_to_db.remote(my_data, conn))
  ```
  Job gagal secara instan dengan exception `TypeError: cannot pickle 'psycopg2.extensions.connection' object`.
* **Analisis & Solusi**: Objek koneksi database memegang internal C-pointer ke dynamic TCP socket descriptors OS yang tidak mungkin diserialisasikan oleh `cloudpickle` untuk ditransfer antar proses atau node.
  * **Solusi**: Transformasikan architecture menjadi **Ray Actor** pattern atau inisialisasi koneksi di dalam task scope:
  ```python
  @ray.remote
  class DatabaseWriterActor:
      def __init__(self, dsn: str):
          self.conn = psycopg2.connect(dsn)
      
      def write(self, data):
          with self.conn.cursor() as cur:
              cur.execute(...)
  ```

#### Skenario 3: Skewed Shuffle Starvation
* **Kasus**: Pipeline join berskala 5 TB antara tabel `Users` dan tabel `Transactions` menggunakan Dask DataFrame mengalami kebuntuan di progres 92%. Satu worker mengalami pemakaian CPU 100% dan NVMe disk write jenuh, sementara seluruh worker lain berstatus IDLE (menunggu).
* **Analisis & Solusi**: Data transaksi mengalami **Data Skewing Ekstrem**. Partisi join key (misal: ID transaksi guest checkout `NULL` atau `account_id=0`) terkonsentrasi secara masif pada satu partisi hash. Akibatnya, satu worker menangani puluhan gigabyte data join seorang diri (Hash Join Partition Collapse).
* **Solusi**: 
  1. Lakukan filter out transaksi guest/null keys sebelum join, proses null keys via path union terpisah tanpa shuffle.
  2. Implementasikan teknik **Salting Join**: Tambahkan kolom integer acak $K \in [0, N]$ pada dataset kiri, dan gandakan data pencocokan di dataset kanan sebanyak $N$ kali, sehingga beban terdistribusi merata ke $N$ worker selama proses all-to-all shuffle.

---

## 16. Summary

1. **Pemilihan Engine Terdistribusi**: Pilihlah **Dask** untuk workload data tabular yang membutuhkan integrasi transparan dengan API Pandas dan Scikit-Learn. Pilihlah **Ray** untuk ekosistem AI/ML heterogen yang memerlukan Dynamic Graph, Actor Stateful Lifecycle, dan Plasma Shared Memory berskala masif. Pilihlah **Polars Streaming** untuk memaksimalkan utilitas satu node tanpa kompleksitas cluster jaringan.
2. **Kunci Efisiensi Memori**: Eliminasi overhead konversi serialisasi data dengan menstandarisasi pipeline pada **Apache Arrow IPC format**. Manfaatkan zero-copy data reads pada arsitektur node yang sama.
3. **Produksi Tanpa Crash**: Tentukan ukuran partisi terdistribusi di sweet-spot **100 MB - 250 MB**, isolasi alokasi native C/glibc memory dengan `jemalloc`, dan selalu sediakan minimal 20% headroom memory limit container terhadap memory limit worker engine guna menghindari termination oleh OS OOM Killer.