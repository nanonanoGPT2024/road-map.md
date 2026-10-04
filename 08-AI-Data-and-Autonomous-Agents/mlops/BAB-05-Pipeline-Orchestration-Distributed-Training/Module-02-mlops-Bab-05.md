# MLOps: Pipeline Orchestration & Distributed Training
**Bab 05:** BAB-05-Pipeline-Orchestration-Distributed-Training  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mendesain dan mengoperasikan arsitektur *distributed training* skala besar (multi-node, multi-GPU) menggunakan *PyTorch Fully Sharded Data Parallel* (FSDP) dan *Ray Train* di atas kluster Kubernetes.
- Mengonfigurasi *pipeline orchestration* deklaratif berkinerja tinggi menggunakan *Kubeflow Pipelines v2* (KFP) dan *Argo Workflows* dengan integrasi metadata tracking.
- Membangun mekanisme *fault tolerance*, *checkpointing engine*, dan pemulihan instan (*spot-instance elasticity*) menggunakan *TorchElastic* / *Ray Autoscaler*.
- Mengatasi *network bottlenecks* dan *GPU underutilization* melalui profiling metrik komunikasi kolektif NCCL (*Ring-AllReduce*, *Tree-AllReduce*, *GPUDirect RDMA*).
- Menghubungkan *artifact lineage*, *data versioning* (DVC/LakeFS), dan *model registry* ke dalam siklus hidup orkestrasi otomatis tanpa intervensi manual.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Distributed Computing & Containerization:** Pemahaman mendalam tentang Kubernetes (CRD, Operator pattern, CNI, Pod lifecycle, PV/PVC, Resource Limits/Requests).
- **Deep Learning Fundamentals:** Arsitektur transformer/CNN, backward pass, gradient accumulation, optimizer states (Adam/AdamW), mixed precision (FP16/BF16).
- **Jaringan & Akselerator Hardware:** Konsep PCIe bandwidth, NVLink, NVSwitch, InfiniBand/RoCE, serta abstraksi CUDA runtime.
- **Python Engineering:** Pemrograman asinkron (*asyncio*), multiprocessing, *context managers*, typing, dan library komputasi paralel (`torch.distributed`).

---

## 3. Concept & Internal Architecture

Ekosistem *Distributed Training* modern memisahkan lapisan abstraksi menjadi tiga domain utama: **Orchestration Layer**, **Distributed Runtime Layer**, dan **Communication Hardware Primitives**.

```
+-------------------------------------------------------------------------------+
|                             ORCHESTRATION LAYER                               |
|        (Kubeflow Pipelines Engine / Argo Workflows / Metadata Store)          |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                       DISTRIBUTED ENGINE & SCHEDULING                         |
|   (KubeRay Operator / Kubeflow Training Operator [PyTorchJob] / Volcano)       |
+-------------------------------------------------------------------------------+
         |                                                     |
         v                                                     v
+---------------------------------+   +-----------------------------------------+
|      WORKER NODE 0 (Master)     |   |          WORKER NODE 1..N               |
|  +---------------------------+  |   |  +-----------------------------------+  |
|  |     TorchElastic Agent    |  |   |  |        TorchElastic Agent         |  |
|  +---------------------------+  |   |  +-----------------------------------+  |
|    |           |           |    |   |    |           |           |            |
|    v           v           v    |   |    v           v           v            |
| +------+   +------+   +------+  |   | +------+   +------+   +------+          |
| |GPU 0 |   |GPU 1 |   |GPU 2 |  |   | |GPU 0 |   |GPU 1 |   |GPU 2 |          |
| +------+   +------+   +------+  |   | +------+   +------+   +------+          |
+---------------------------------+   +-----------------------------------------+
         ^                                                     ^
         |======== InfiniBand / RoCE (GPUDirect RDMA) =========|
         +=========== NCCL AllReduce / ReduceScatter ==========+
```

### 3.1 Distributed Training Topologies: FSDP vs 3D Parallelism

Ketika ukuran model melampaui memori VRAM GPU tunggal (OOM), paradigma paralelisme harus bergeser dari standar *Distributed Data Parallel* (DDP) menuju teknik partisi memori stateful:

1. **ZeRO (Zero Redundancy Optimizer) / PyTorch FSDP:**
   Memori model dibagi menjadi tiga komponen utama: Optimizer States ($4\times$ bobot model pada FP32), Gradients ($2\times$ bobot model), dan Parameters ($2\times$ bobot model).
   - **FSDP Full Shard (ZeRO-3):** Membagi Optimizer States, Gradients, dan Parameters ke seluruh rank komputasi. Parameter hanya di-*gather* sesaat sebelum forward/backward pass via `AllGather`, lalu dibebaskan kembali dari VRAM melalui `ReduceScatter`.
   - **FSDP Shard Grad Op (ZeRO-2):** Mempertahankan parameter lokal selama iterasi, tetapi membagi gradients dan optimizer states. Mengurangi overhead komunikasi jaringan dengan konsekuensi jejak memori VRAM lebih tinggi dibanding Full Shard.

2. **Tensor Parallelism (TP) vs Pipeline Parallelism (PP):**
   - **TP (Megatron-LM style):** Matriks bobot linear dibagi melintasi GPU (Column Parallelism pada layer pertama MLP, Row Parallelism pada layer kedua). Memerlukan bandwidth sangat tinggi (NVLink $\ge 600\text{ GB/s}$), umumnya dibatasi dalam satu node fisik tunggal.
   - **PP (Pipeline Parallelism):** Layer model dibagi secara sekuensial antar node. Aktivasi dikirim via micro-batching (1F1B schedule). Rentan terhadap *pipeline bubble* yang menurunkan efisiensi GPU compute.

### 3.2 Dynamic Scheduling & Elastic Fault Tolerance

Pada kluster komputasi awan, risiko preemption pada *spot instances* mengharuskan sistem bersifat elastis:
- **TorchElastic Architecture:** Sebuah daemon `torchrun` bertindak sebagai controller lokal. Ia berkomunikasi dengan rendezvous backend terdistribusi (berbasis etcd atau C10d store di node master). Jika satu node mati, status cluster berubah; `TorchElastic` menahan eksekusi rank lain, menginisialisasi ulang rendezvous, merekonfigurasi `WORLD_SIZE` dan `RANK`, lalu memuat *checkpoint* stateful terakhir secara otomatis tanpa me-restart seluruh pipeline job Kubernetes.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Monolithic Script / Single Node) | Pendekatan Enterprise (Orchestrated Distributed MLOps) |
| :--- | :--- | :--- |
| **Batas Skalabilitas** | Terbatas pada batas VRAM GPU node fisik tunggal ($\le 8\times \text{H100 } 80\text{GB}$). | Horizontal scaling tanpa batas teoritis via Multi-node FSDP & DeepSpeed 3D parallelism. |
| **Resiliensi Kegagalan** | Node gagal $\rightarrow$ proses crash total $\rightarrow$ data loss jika checkpointing manual gagal. | Self-healing cluster via KubeRay/KubeFlow Operator + Elastic Rendezvous + Automatic Stateful Checkpointing. |
| **Efisiensi Biaya** | Bergantung pada Reserved/On-Demand Cloud Instances yang mahal. | Optimasi Spot/Preemptible Instances dengan overhead failover $< 90$ detik. |
| **Reproducibility** | Script Python ad-hoc, dependensi bare-metal kotor, artefak tersebar di lokal disk. | Containerized immutable step, parameter & artifact tracking via MLflow/Kubeflow Metadata. |
| **Resource Contention** | Manual port forwarding, tabrakan CUDA device id antar developer. | Resource quotas deklaratif, fair-share GPU queuing via Volcano scheduler / Kubernetes Kueue. |

---

## 5. How (Workflow Detail)

Alur kerja end-to-end distributed training skala enterprise terdiri dari fase terstruktur:

```
[ Git Push / Trigger ] 
       │
       ▼
[ Pipeline Compilation ] ──> KFP Compiler memvalidasi DAG, input parameters, & output artifacts.
       │
       ▼
[ Pipeline Orchestrator ] ──> Argo Controller mengeksekusi Driver Pod.
       │
       ├─ Step 1: Data Preparation & Sharding Verification (LakeFS / S3 / S3-CSI)
       │
       ├─ Step 2: Provisioning Distributed Cluster via Custom Resource (KubeRay / PyTorchJob)
       │          │
       │          ├── Volcano / Kueue: Menjadwalkan Ganging Pod (Gang Scheduling)
       │          ├── TorchElastic Rendezvous initialization (TCP/etcd)
       │          └── Distributed Training Loop (Forward -> Backward -> AllReduce -> Checkpoint)
       │
       ├─ Step 3: Distributed Evaluation & Bias Auditing
       │
       └─ Step 4: Model Registration & Lineage Linking (MLflow / KFP Metadata)
```

1. **Gang Scheduling:** Menjamin seluruh $N$ worker pod dialokasikan secara atomik. Jika kluster hanya memiliki resource untuk $N-1$ worker, scheduler tidak akan mengalokasikan resource secara parsial guna mencegah *deadlock*.
2. **Dynamic Checkpointing:** Menyimpan tensor state ke distributed storage (Ceph, Lustre, S3) secara asynchronous non-blocking menggunakan worker thread terpisah.
3. **Artifact Lineage Emission:** Tiap step pipeline mengekspor SHA256 digest dari dataset, hash komit Git, hyperparameter, dan model binary ke metadata backend.

---

## 6. Analogy & Diagram ASCII

### Analogi Orkestrasi FSDP: Pabrik Perakitan Buku Raksasa

Bayangkan menulis ensiklopedia 10.000 halaman (Model Parameter Besar) oleh 4 juru tulis (GPU):
- **DDP Tradisional:** Setiap juru tulis harus memegang salinan lengkap 10.000 halaman di mejanya (VRAM habis). Mereka hanya membagi tumpukan draf bab pembaca (Data Sharding).
- **FSDP (ZeRO-3):** Buku disobek menjadi 4 bagian. Juru Tulis A memegang halaman 1-2500, Juru Tulis B memegang 2501-5000, dst.
  1. Ketika Juru Tulis A butuh membaca halaman 3000 untuk menulis catatannya, ia berteriak ke B (*AllGather*), meminjam halaman itu, menghitung gradiennya, lalu segera mengembalikan halaman tersebut ke B (*Memory Release*).
  2. Ketika tiba saatnya memperbarui draf, semua juru tulis menghitung revisi (*ReduceScatter*), dan hanya mengupdate lembaran milik masing-masing (*Optimizer Step*). Meja tulis tetap bersih dan muat bekerja.

```
       RANK 0                    RANK 1                    RANK 2                    RANK 3
+-------------------+     +-------------------+     +-------------------+     +-------------------+
| Param: [W0]       |     | Param: [W1]       |     | Param: [W2]       |     | Param: [W3]       |
| Grad:  [G0]       |     | Grad:  [G1]       |     | Grad:  [G2]       |     | Grad:  [G3]       |
| Opt:   [S0]       |     | Opt:   [S1]       |     | Opt:   [S2]       |     | Opt:   [S3]       |
+-------------------+     +-------------------+     +-------------------+     +-------------------+
          │                         │                         │                         │
          └─────────────────────────┴───────────┬─────────────┴─────────────────────────┘
                                                │
                                    FORWARD PASS: AllGather
                                    (Semua rank menerima W0..W3)
                                                │
                                                ▼
+-------------------------------------------------------------------------------------------------+
| GPU Memory Rank 0..3 Sementara: [W0, W1, W2, W3] -> Compute Activation Layer                    |
+-------------------------------------------------------------------------------------------------+
                                                │
                                    BACKWARD PASS: ReduceScatter
                                    (Gradien diakumulasi & dibagi)
                                                │
                                                ▼
+-------------------+     +-------------------+     +-------------------+     +-------------------+
| Grad Sum: [G0]    |     | Grad Sum: [G1]    |     | Grad Sum: [G2]    |     | Grad Sum: [G3]    |
| Update:   [W0]    |     | Update:   [W1]    |     | Update:   [W2]    |     | Update:   [W3]    |
+-------------------+     +-------------------+     +-------------------+     +-------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: PyTorch FSDP Standalone Script

Skrip distributed data sharding menggunakan `torchrun`:

```python
# simple_fsdp.py
import os
import torch
import torch.nn as nn
import torch.distributed as dist
from torch.distributed.fsdp import FullyShardedDataParallel as FSDP

class SimpleTransformerBlock(nn.Module):
    def __init__(self, d_model=1024):
        super().__init__()
        self.fc1 = nn.Linear(d_model, d_model * 4)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(d_model * 4, d_model)

    def forward(self, x):
        return self.fc2(self.relu(self.fc1(x)))

def setup_distributed():
    dist.init_process_group(backend="nccl")
    local_rank = int(os.environ["LOCAL_RANK"])
    torch.cuda.set_device(local_rank)
    return local_rank

def main():
    local_rank = setup_distributed()
    model = SimpleTransformerBlock().to(local_rank)
    
    # Wrap model menggunakan FSDP
    fsdp_model = FSDP(model)
    
    loss_fn = nn.MSELoss()
    optimizer = torch.optim.AdamW(fsdp_model.parameters(), lr=1e-4)

    dummy_input = torch.randn(32, 1024, device=local_rank)
    dummy_target = torch.randn(32, 1024, device=local_rank)

    optimizer.zero_grad()
    output = fsdp_model(dummy_input)
    loss = loss_fn(output, dummy_target)
    loss.backward()
    optimizer.step()

    if dist.get_rank() == 0:
        print(f"Step completed. Loss: {loss.item():.4f}")

    dist.destroy_process_group()

if __name__ == "__main__":
    main()
```
*Eksekusi via terminal:*
```bash
torchrun --nproc_per_node=2 simple_fsdp.py
```

### 7.2 Practical Example: Enterprise Distributed Training Pipeline (KFP v2 + Ray Train)

Implementasi pipeline produksi end-to-end yang menyusun distributed training pipeline deklaratif menggunakan DSL Kubeflow Pipelines v2 dan Ray Train untuk komputasi multi-GPU.

#### File: `distributed_training_pipeline.py`

```python
import kfp
from kfp import dsl
from kfp.dsl import component, Output, Model, Metrics, Artifact

@component(
    base_image="python:3.11-slim",
    packages_to_install=["requests==2.31.0"]
)
def validate_data_readiness(
    data_bucket_path: str,
    manifest_status: Output[Artifact]
):
    import json
    import os
    
    print(f"Memvalidasi partisi data pada: {data_bucket_path}")
    # Simulasi verifikasi metadata partisi data di storage object
    validation_meta = {
        "dataset_path": data_bucket_path,
        "shards_count": 16,
        "format": "parquet",
        "is_consistent": True
    }
    
    with open(manifest_status.path, "w") as f:
        json.dump(validation_meta, f)

@component(
    base_image="rayproject/ray-ml:2.35.0-py310",
    packages_to_install=["torch==2.3.1", "torchvision==0.18.1"],
)
def execute_distributed_ray_fsdp(
    manifest_status: dsl.Input[Artifact],
    epochs: int,
    batch_size_per_gpu: int,
    metrics_out: Output[Metrics],
    model_out: Output[Model]
):
    import json
    import os
    import ray
    import ray.train
    from ray.train import ScalingConfig, Checkpoint
    from ray.train.torch import TorchTrainer, TorchConfig
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.distributed.fsdp import FullyShardedDataParallel as FSDP
    from torch.distributed.fsdp.fully_sharded_data_parallel import (
        FullStateDictConfig,
        StateDictType,
    )

    with open(manifest_status.path, "r") as f:
        manifest = json.load(f)
    print(f"Menjalankan training berdasarkan manifest: {manifest}")

    # Definisi Komponen Training
    def train_func_per_worker(config):
        # Ray Train mengelola rank, local_rank, and world_size
        device = ray.train.torch.get_device()
        
        # Arsitektur Jaringan Sederhana
        model = nn.Sequential(
            nn.Linear(512, 1024),
            nn.ReLU(),
            nn.Linear(1024, 512)
        ).to(device)

        # Bungkus model dalam FSDP engine
        fsdp_model = FSDP(model)
        loss_fn = nn.MSELoss()
        optimizer = optim.AdamW(fsdp_model.parameters(), lr=1e-3)

        for epoch in range(config["epochs"]):
            # Simulasi load data sharded
            x = torch.randn(config["batch_size"], 512, device=device)
            y = torch.randn(config["batch_size"], 512, device=device)

            optimizer.zero_grad()
            output = fsdp_model(x)
            loss = loss_fn(output, y)
            loss.backward()
            optimizer.step()

            # Logging metrics
            ray.train.report(
                metrics={"loss": loss.item(), "epoch": epoch}
            )

        # Penyimpanan Model Hanya dari Rank 0 menggunakan Full State Dict
        save_policy = FullStateDictConfig(offload_to_cpu=True, rank0_only=True)
        with FSDP.state_dict_type(fsdp_model, StateDictType.FULL_STATE_DICT, save_policy):
            cpu_state = fsdp_model.state_dict()
            if ray.train.get_context().get_world_rank() == 0:
                os.makedirs("/tmp/model_ckpt", exist_ok=True)
                torch.save(cpu_state, "/tmp/model_ckpt/model.pt")
                ray.train.report(
                    metrics={"final_loss": loss.item()},
                    checkpoint=Checkpoint.from_directory("/tmp/model_ckpt")
                )

    # Inisialisasi cluster compute Ray (In-Cluster atau Eksternal)
    ray.init(ignore_reinit_error=True)

    trainer = TorchTrainer(
        train_loop_per_worker=train_func_per_worker,
        train_loop_config={
            "epochs": epochs,
            "batch_size": batch_size_per_gpu
        },
        torch_config=TorchConfig(backend="nccl"),
        scaling_config=ScalingConfig(
            num_workers=2,         # Setara 2 Node / 2 GPU
            use_gpu=False          # Ubah ke True jika runtime GPU tersedia
        )
    )

    results = trainer.fit()
    
    # Ambil Best Checkpoint dan Simpan ke KFP Output Model
    best_loss = results.metrics.get("loss", 0.0)
    metrics_out.log_metric("final_train_loss", float(best_loss))
    
    with open(model_out.path, "w") as f:
        f.write(f"Model trained successfully. Best loss: {best_loss}")

@dsl.pipeline(
    name="enterprise-distributed-training-pipeline",
    description="Production pipeline dengan validasi data partisi dan Ray FSDP cluster execution."
)
def distributed_pipeline(
    dataset_uri: str = "s3://mlops-lakehouse/data/v1",
    total_epochs: int = 5,
    batch_size: int = 64
):
    check_task = validate_data_readiness(data_bucket_path=dataset_uri)
    
    train_task = execute_distributed_ray_fsdp(
        manifest_status=check_task.outputs["manifest_status"],
        epochs=total_epochs,
        batch_size_per_gpu=batch_size
    )
    # Konfigurasi resource pod orchestrator
    train_task.set_cpu_limit("4").set_memory_limit("8Gi")

if __name__ == "__main__":
    kfp.compiler.Compiler().compile(
        pipeline_func=distributed_pipeline,
        package_path="distributed_pipeline.yaml"
    )
    print("KFP Pipeline berhasil dikompilasi ke distributed_pipeline.yaml")
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: LLM Finetuning Multi-Node Failure di Platform Fintech Global
- **Konteks:** Perusahaan fintech melatih model *Fraud Detection* berbasis Llama-3-70B menggunakan 16 node AWS `p4de.24xlarge` (128 GPU A100 80GB) dengan Kubernetes via Kubeflow Training Operator.
- **Masalah Produksi:**
  1. *Eksplosi Biaya:* Penggunaan Spot Instances memicu *Spot Interruption* rata-rata setiap 3,5 jam. Satu pod terhenti menyebabkan seluruh pelatihan mati (Status: `Degraded`), membuang komputasi bernilai ribuan dolar.
  2. *Straggler Effect:* Salah satu GPU pada node 09 mengalami penurunan interkoneksi PCIe bandwidth dari 32 GB/s menjadi 4 GB/s akibat hardware degradation, membuat seluruh 127 GPU lain idle menunggu synchronization phase (*NCCL AllReduce*).
- **Arsitektur Solusi:**
  1. **Migrasi ke Elastic Horovod/TorchElastic + S3 Express One Zone Checkpointing:** Mengubah `PyTorchJob` specification untuk menggunakan elastic mode:
     ```yaml
     apiVersion: "kubeflow.org/v1"
     kind: "PyTorchJob"
     metadata:
       name: "llama3-70b-elastic-finetune"
     spec:
       elasticPolicy:
         minReplicas: 8
         maxReplicas: 16
         rdzvBackend: etcd
         rdzvEndpoint: etcd-cluster.monitoring.svc.cluster.local:2379
     ```
  2. **Automated Straggler Mitigation:** Mengintegrasikan Prometheus metrics yang mengekspor `nvml_pcie_tx_throughput` dan `nccl_allreduce_latency`. Ketika divergensi latensi worker $> 3\sigma$, webhook Kubelet mengeksekusi *taint node* dan memicu pod reschedule tanpa menggagalkan run utama.
- **Hasil:** Waktu terbuang akibat failover berkurang dari 4 jam menjadi 80 detik. Penghematan biaya komputasi mencapai 62% dengan utilization rate GPU naik dari 48% ke 89%.

---

## 9. Trade-offs

| Aspek / Desain | Pilihan A: PyTorch FSDP (ZeRO-3) | Pilihan B: DeepSpeed 3D Parallelism (TP + PP + DP) |
| :--- | :--- | :--- |
| **Throughput & FLOPs Efficiency** | Sedang - Tinggi. Efisien hingga model ~70B parameter pada multi-node standar. | Sangat Tinggi. Eksekusi model $>100\text{B}+$ mencapai batas hardware compute utilization. |
| **Kompleksitas Implementasi** | Rendah - Moderat. Native di PyTorch, sedikit perubahan pada model layer definition. | Sangat Kompleks. Membutuhkan partisi manual layer model, penyesuaian attention heads dengan TP size. |
| **Overhead Komunikasi Jaringan** | **Tinggi.** Terus menerus memicu komunikasi `AllGather` dan `ReduceScatter` pada setiap layer. | **Rendah pada batas Node.** Tensor Parallel dibatasi via NVLink antar GPU lokal, PP latensi rendah antar node. |
| **Kebutuhan Minimum Hardware** | Membutuhkan minimal RoCE v2 atau InfiniBand ($\ge 100\text{ Gbps}$) untuk skalabilitas linear. | Dapat berjalan pada kluster interkoneksi heterogen (e.g., NVLink intra-node, 25GbE inter-node). |
| **Memory Footprint per GPU** | Minimal. Seluruh parameter/gradient/optimizer terbagi rata (*fully sharded*). | Tergantung tuning TP/PP/DP size, rentan memory imbalance jika layer tidak homogen. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Silent CUDA OOM saat Save Checkpoint pada FSDP
- **Gejala:** Training berjalan normal sepanjang epoch, namun tepat saat checkpointing di akhir step, seluruh proses terbunuh oleh Linux Out-Of-Memory Killer (`Killed: 9` atau `CUDA out of memory`).
- **Akar Masalah:** Developer memanggil `model.state_dict()` langsung tanpa menspesifikasikan konfigurasi sharding. FSDP mencoba menarik seluruh model parameter ke rank 0 VRAM secara instan.
- **Solusi:** Terapkan CPU Offloading context manager secara eksplisit:
  ```python
  from torch.distributed.fsdp import FullyShardedDataParallel as FSDP
  from torch.distributed.fsdp import FullStateDictConfig, StateDictType

  save_cfg = FullStateDictConfig(offload_to_cpu=True, rank0_only=True)
  with FSDP.state_dict_type(fsdp_model, StateDictType.FULL_STATE_DICT, save_cfg):
      state_dict = fsdp_model.state_dict()
      if dist.get_rank() == 0:
          torch.save(state_dict, "checkpoint.pt")
  ```

### 10.2 NCCL Watchdog Timeout (Error: `Watchdog caught collective operation timeout`)
- **Gejala:** Model tiba-tiba hang tanpa progress bar, diikuti error traceback NCCL timeout setelah 10 atau 30 menit.
- **Investigasi:**
  1. Set environment variable: `export NCCL_DEBUG=INFO` dan `export NCCL_DEBUG_SUBSYS=ALL,COLL`.
  2. Cek apakah ada distribusi data tidak seimbang (*data imbalance*): salah satu worker menerima lebih banyak batch daripada yang lain, memicu worker lain menunggu di sync barrier tanpa batas waktu.
- **Pencegahan:** Selalu gunakan `DistributedSampler` dengan konfigurasi flag `drop_last=True` pada DataLoader:
  ```python
  sampler = torch.utils.data.distributed.DistributedSampler(
      dataset,
      num_replicas=dist.get_world_size(),
      rank=dist.get_rank(),
      shuffle=True,
      drop_last=True # Mencegah hang pada sisa modulo batch size
  )
  ```

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum mengeksekusi pipeline distributed training skala multi-node:

- [ ] **Interconnect Verification:** Bandwidth fabric tervalidasi menggunakan `nccl-tests` (`all_reduce_perf`). Throughput bus mendekati batas native hardware (misal: $\ge 350\text{ GB/s}$ pada NVLink).
- [ ] **Network Shared Memory:** Pods Kubernetes dikonfigurasi dengan volume `emptyDir` mount bertipe `Memory` di `/dev/shm` guna menghindari IPC crashing:
  ```yaml
  volumes:
  - name: dshm
    emptyDir:
      medium: Memory
      sizeLimit: 32Gi
  ```
- [ ] **Deterministic Data Sharding:** Memastikan *seed* generator dan *DistributedSampler* sinkron melintasi rank, menghindari duplikasi kalkulasi data.
- [ ] **Mixed Precision Optimization:** Mengaktifkan PyTorch AMP (Automatic Mixed Precision) dengan format data `bfloat16` (bukan `float16`) untuk arsitektur modern demi stabilitas range gradient tanpa loss scaler.
- [ ] **Asynchronous Non-blocking IO:** Eksekusi snapshotting / checkpointing didelegasikan ke thread background (`asyncio` / concurrent futures) agar compute core GPU tidak mengalami siklus jeda (*zero stall*).
- [ ] **Gang Scheduling Enforcement:** CRD operator (Volcano / Kueue) dikonfigurasi untuk mencegah deadlock penjadwalan resource parsial.

---

## 12. Hands-on Practice

Dalam sesi praktikum ini, Anda akan membangun skrip training multi-proses lokal dan membungkusnya ke dalam sistem automated orchestrator menggunakan containerized pipeline.

### Direktori Kerja
Simpan seluruh artefak praktikum pada direktori: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
```

### Langkah 1: Buat Engine Distributed Training
Tulis file `src/train_engine.py`:

```python
import os
import argparse
import torch
import torch.nn as nn
import torch.distributed as dist
from torch.utils.data import DataLoader, Dataset
from torch.utils.data.distributed import DistributedSampler

class SyntheticDataset(Dataset):
    def __len__(self):
        return 1000
    def __getitem__(self, idx):
        return torch.randn(128), torch.randn(1)

def run(args):
    # Inisialisasi env via torchrun
    dist.init_process_group(backend="gloo" if not torch.cuda.is_available() else "nccl")
    rank = dist.get_rank()
    world_size = dist.get_world_size()
    
    device = torch.device(f"cuda:{args.local_rank}" if torch.cuda.is_available() else "cpu")
    if torch.cuda.is_available():
        torch.cuda.set_device(device)

    dataset = SyntheticDataset()
    sampler = DistributedSampler(dataset, num_replicas=world_size, rank=rank, shuffle=True, drop_last=True)
    loader = DataLoader(dataset, batch_size=args.batch_size, sampler=sampler)

    model = nn.Sequential(
        nn.Linear(128, 64),
        nn.ReLU(),
        nn.Linear(64, 1)
    ).to(device)

    if torch.cuda.is_available():
        model = nn.parallel.DistributedDataParallel(model, device_ids=[args.local_rank])
    else:
        model = nn.parallel.DistributedDataParallel(model)

    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    criterion = nn.MSELoss()

    for epoch in range(args.epochs):
        sampler.set_epoch(epoch)
        total_loss = 0.0
        for step, (inputs, targets) in enumerate(loader):
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        if rank == 0:
            print(f"[Epoch {epoch}] Loss rata-rata: {total_loss / len(loader):.4f}")

    if rank == 0:
        os.makedirs(args.output_dir, exist_ok=True)
        torch.save(model.module.state_dict(), os.path.join(args.output_dir, "checkpoint.pt"))
        print(f"Model tersimpan di {args.output_dir}/checkpoint.pt")

    dist.destroy_process_group()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-rank", type=int, default=int(os.environ.get("LOCAL_RANK", 0)))
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--output-dir", type=str, default="./outputs")
    args = parser.parse_args()
    run(args)
```

### Langkah 2: Buat Pipeline Orchestrator Driver
Tulis file `orchestrator.py`:

```python
import subprocess
import sys
import os

def trigger_pipeline():
    print("=== [PHASE 1] Memvalidasi Environment & Compute Targets ===")
    world_size = 2
    print(f"Targeting local simulated ranks: {world_size}")

    print("\n=== [PHASE 2] Eksekusi Distributed Runner via TorchElastic ===")
    cmd = [
        sys.executable,
        "-m", "torch.distributed.run",
        f"--nproc_per_node={world_size}",
        "src/train_engine.py",
        "--epochs", "2",
        "--batch-size", "32",
        "--output-dir", "hands-on/m02/artifacts"
    ]
    
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print("Pipeline execution: GAGAL")
        sys.exit(result.returncode)
    
    print("\n=== [PHASE 3] Evaluasi Pipeline Output & Verification ===")
    model_path = "hands-on/m02/artifacts/checkpoint.pt"
    if os.path.exists(model_path):
        size = os.path.getsize(model_path)
        print(f"Pipeline BERHASIL! Binary Model Valid: {model_path} ({size} bytes)")
    else:
        print("Pipeline GAGAL: Binary artifact tidak ditemukan.")
        sys.exit(1)

if __name__ == "__main__":
    trigger_pipeline()
```

### Langkah 3: Eksekusi dan Verifikasi
Jalankan praktikum di environment lokal Anda:

```bash
python orchestrator.py
```

---

## 13. Exercise

### Level Easy
Modifikasi script `src/train_engine.py` agar membaca metric log dan menyimpan ringkasan JSON berisi `epoch`, `duration_seconds`, dan `final_loss` pada direktori `hands-on/m02/artifacts/summary.json` hanya melalui Rank 0.

### Level Medium
Ubah arsitektur paralelisme pada `src/train_engine.py` dari `DistributedDataParallel` (DDP) standar menjadi `FullyShardedDataParallel` (FSDP). Konfigurasikan auto-wrapping policy menggunakan linear transformer block sederhana dan pastikan state dict diekspor menggunakan mode `StateDictType.FULL_STATE_DICT` dengan offloading ke CPU.

### Level Hard
Rancang sebuah custom Argo Workflows template (`workflow.yaml`) yang mengimplementasikan fault recovery cycle:
1. Tahap 1: Validasi keberadaan dataset pada bucket MinIO.
2. Tahap 2: Menjalankan Distributed Job pod (Master & Worker).
3. Tahap 3: Jika Tahap 2 exit code $\neq 0$ (mengalami kegagalan), picu fallback task yang melakukan pembersihan resource pod kotor, mengirim alerting webhook ke Slack, dan men-submit job baru dengan konfigurasi batch size yang diturunkan 50%.

---

## 14. Challenge

**Skenario Kasus Kompleks:**  
Sebuah kluster multi-tenant AI menjalankan model deep learning multimodal berukuran 30 Miliar parameter melintasi 8 node (masing-masing 8x GPU H100 80GB, total 64 GPU). Infrastruktur sering mengalami *dynamic preemption* karena berjalan di atas AWS Spot Capacity Blocks.

**Objektif Tantangan:**
1. Desain spesifikasi arsitektur deklaratif (gabungan Kubernetes Operator, Argo/KFP, dan PyTorch FSDP) yang mampu menangani penghentian (*interruption*) node komputasi tanpa membatalkan tahapan orchestrator DAG.
2. Buat sistem checkpointing terdistribusi asinkron yang mampu mem-flush parameter sharded ke Amazon S3 via interface berkecepatan tinggi tanpa menghentikan komputasi GPU lebih dari 3% dari total wall-clock time per iterasi.
3. Definisikan algoritma rendezvous failure recovery dinamis yang dapat mendeteksi kegagalan worker dalam waktu $\le 10$ detik, merestrukturisasi topologies NCCL ring baru dari $N$ menjadi $N-1$ worker node secara elastis, dan menginstruksikan rank tersisa untuk memuat checkpoint terakhir tanpa mengulang pipeline dari step awal.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Apa fungsi utama dari primitif komunikasi kolektif `AllReduce` pada Distributed Data Parallel?
   - A. Mengirimkan subset data dari master node ke seluruh worker pod.
   - B. Menjumlahkan gradien dari seluruh worker GPU dan mendistribusikan hasil akhirnya kembali ke seluruh GPU.
   - C. Membagi parameter model ke CPU RAM.
   - D. Menyimpan checkpoint secara paralel ke sistem storage.
2. Komponen memori mana yang di-shard pada penerapan FSDP ZeRO Stage 1?
   - A. Parameter model saja.
   - B. Gradients saja.
   - C. Optimizer States.
   - D. Seluruh layer aktivasi forward pass.
3. Apa peran utama dari agent `TorchElastic` (`torchrun`)?
   - A. Menulis metadata pipeline ke dalam SQLite registry.
   - B. Mengatur dynamic rendezvous, monitoring failure pod, dan re-assign rank secara otomatis jika terjadi perubahan cluster size.
   - C. Mengonversi model PyTorch menjadi format runtime ONNX.
   - D. Menjadwalkan pod Kubernetes menggunakan Gang Scheduler Volcano.
4. Parameter apa yang harus diset pada PyTorch `DistributedSampler` untuk mencegah freeze/deadlock saat ukuran dataset tidak habis dibagi total worker GPU?
   - A. `shuffle=False`
   - B. `pin_memory=False`
   - C. `drop_last=True`
   - D. `num_replicas=0`
5. Pada sistem Kubernetes, pola architectural apa yang digunakan oleh Kubeflow Training Operator untuk mengontrol lifecycle distributed training pods?
   - A. Service Mesh Pattern.
   - B. Controller / Operator Pattern berbasis Custom Resource Definition (CRD).
   - C. Sidecar Proxy Pattern murni.
   - D. Monolithic DaemonSet.

### Bagian 2: Intermediate (Pilihan Ganda)
6. Manakah konfigurasi FSDP yang paling optimal jika bandwidth interkoneksi jaringan antar-node sangat terbatas (misalnya hanya 10Gbps Ethernet biasa)?
   - A. FSDP Full Shard (ZeRO-3) dengan aggressive prefetching.
   - B. Standar DDP atau FSDP Shard Grad Op (ZeRO-2) dengan Gradient Accumulation tinggi.
   - C. Tensor Parallelism melintasi node via TCP socket.
   - D. Pipeline Parallelism tanpa micro-batching.
7. Mengapa `/dev/shm` (Shared Memory) pada container Docker/Kubernetes harus diperbesar ketika melatih model terdistribusi menggunakan PyTorch DataLoader?
   - A. Karena NCCL backend menyimpan file bobot floating point langsung di shared memory.
   - B. DataLoader worker memanfaatkan POSIX shared memory antar proses untuk mentransfer batch tensor; jika default 64MB terlampaui, worker akan crash seketika (SIGBUS).
   - C. Untuk menampung container image layer yang ditarik dari registry.
   - D. Agar kernel Linux dapat melakukan page caching ke NVRAM accelerator.
8. Apa kelemahan utama dari topologi Pipeline Parallelism (PP) dibandingkan Data Parallelism murni?
   - A. Membutuhkan interkoneksi NVLink berkecepatan tinggi antar seluruh node kluster.
   - B. Memunculkan *pipeline bubble* (GPU idle time) saat menunggu aktivasi forward dan gradien backward melintasi boundary stage.
   - C. Menghabiskan VRAM GPU lebih banyak untuk menyimpan Optimizer State di seluruh node.
   - D. Tidak mendukung model berbasis transformer.
9. Pada Kubeflow Pipelines v2, bagaimana data berukuran gigabyte ditransfer secara efisien antar dua task komponen yang berbeda?
   - A. Data dilewatkan langsung secara in-memory melalui environment variable task pod berikutnya.
   - B. Data disimpan ke remote artifact repository (seperti S3/MinIO), dan yang diteruskan antar container task hanyalah metadata URI/path.
   - C. Data disimpan pada pod disk lokal lalu dipindahkan via SCP otomatis.
   - D. Melalui database KFP central metastore secara serial.
10. Kapan Anda harus memilih model parallelisme berbasis Tensor Parallel (TP) daripada FSDP?
    - A. Ketika Anda melatih model di ratusan worker node berlatensi tinggi.
    - B. Ketika single layer matrix multiplication dari model tidak lagi muat di VRAM satu GPU dan latensi komunikasi intra-node sangat rendah (tersedia NVLink).
    - C. Saat jumlah data batch training jauh lebih besar dari parameter model.
    - D. Ketika GPU yang digunakan tidak mendukung operasi floating point BF16.

### Bagian 3: Skenario Kasus Produksi
11. **Skenario 1:** Tim Anda menjadwalkan job pelatihan FSDP 4-node pada kluster Kubernetes. Job berstatus `Pending` selamanya meskipun secara agregat kluster memiliki kapasitas core dan GPU yang cukup di berbagai node yang tersebar. Masalah arsitektur apa yang terjadi pada scheduler, dan bagaimana solusinya?
12. **Skenario 2:** Sebuah pipeline pelatihan deep learning mengalami crash sporadis dengan pesan error `CUDA error: an illegal memory access was encountered` hanya pada worker rank 3 saat backward pass. Namun skrip yang sama berjalan sukses jika dieksekusi di single GPU. Apa langkah isolasi sistemis yang harus diambil?
13. **Skenario 3:** Dalam deployment model berskala ratusan node, throughput pelatihan (TFLOPS per GPU) menurun secara drastis seiring penambahan jumlah worker node (skalabilitas sub-linear parah). Hasil profiling menunjukkan overhead waktu terbesar berada pada fase `ncclKernel_AllReduce`. Strategi arsitektur jaringan dan software apa yang wajib diaplikasikan?

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **B** — `AllReduce` menjumlahkan nilai (gradien) dari seluruh worker dan mendistribusikan total penjumlahan ke seluruh node partisipan.
2. **C** — ZeRO Stage 1 membagi Optimizer State; ZeRO Stage 2 membagi Gradients + Optimizer States; ZeRO Stage 3 membagi seluruh Parameter, Gradients, dan Optimizer States.
3. **B** — TorchElastic memantau worker lifecycle, merekonfigurasi rendezvous topology secara dinamis saat terjadi node drop/join.
4. **C** — `drop_last=True` mencegah ketimpangan jumlah batch di rank terakhir yang dapat membekukan operasi collective sync barrier.
5. **B** — Menggunakan Operator/Controller pattern yang merekonsiliasi Custom Resource Definition (misal: `PyTorchJob`).

#### Bagian 2: Intermediate
6. **B** — FSDP ZeRO-3 membebani interkoneksi dengan lalu lintas AllGather/ReduceScatter kontinu. Jika bandwidth jaringan rendah, DDP atau ZeRO-2 yang dikombinasikan dengan gradient accumulation meminimalkan overhead frekuensi transfer.
7. **B** — PyTorch DataLoader memanfaatkan shm IPC. Limit default Docker (64MB) memicu `Bus error / SIGBUS` saat batch berukuran besar dilewatkan antar worker thread.
8. **B** — Pipeline Parallelism menghasilkan bubble idle time di mana akselerator hulu/hilir menunggu dependency data batch berikutnya.
9. **B** — Data passing pada KFP/Argo bersifat out-of-band berbasis Object Storage abstraction; hanya lightweight reference pointer (URI artifact) yang dikirim antar pod.
10. **B** — Tensor Parallel memecah parameter layer matriks individual; ini membutuhkan bandwidth komunikasi ekstrem (NVLink intra-node) dan ditujukan untuk layer yang melampaui VRAM GPU tunggal.

#### Bagian 3: Solusi Skenario Kasus Produksi
11. **Analisis Solusi 1:** Terjadi kondisi *Resource Fragmentation* akibat ketiadaan Gang Scheduling. Scheduler bawaan Kubernetes mencoba menjadwalkan pod secara individual bukan secara atomik kelompok (`Gang`). Pod master/worker pertama mungkin mengunci kuota node tertentu sementara worker sisanya tidak menemukan node utuh yang muat. **Solusi:** Terapkan scheduler khusus komputasi batch paralel seperti **Volcano Scheduler** atau **Kubernetes Kueue** dengan konfigurasi `PodGroup` minimal target `minMember: 4`.
12. **Analisis Solusi 2:** Error *illegal memory access* pada multi-GPU training biasanya berakar dari: (a) Desinkronisasi indexing tensor dinamis antar rank yang memicu out-of-bound pointer CUDA kernel, atau (b) Masalah hardware VRAM degradation pada unit fisik GPU rank 3 tersebut. **Langkah Isolasi:** Aktifkan environment variable `export CUDA_LAUNCH_BLOCKING=1` dan `export TORCH_USE_CUDA_DSA=1` (Device-side Assertions) untuk melacak index baris kode penyebab crash. Jalankan program diagnosa hardware (`dcgmproftester` atau `memtestG80`) pada mesin node GPU rank 3 untuk memverifikasi ada tidaknya bit flip/hardware fault.
13. **Analisis Solusi 3:** Komunikasi inter-node menjadi *bottleneck*. **Langkah Perbaikan:** 
    - *Hardware/Network:* Pastikan jaringan antar node mendukung InfiniBand atau RoCE v2 dengan driver GPUDirect RDMA aktif, melewati bottleneck memory copy kernel CPU.
    - *Software/Algoritma:* Naikkan `batch_size` efektif menggunakan Gradient Accumulation untuk menaikkan rasio komputasi terhadap komunikasi (*Compute-to-Communication Ratio*). Ganti topologi murni FSDP ZeRO-3 menjadi Hybrid Sharding (intra-node FSDP via NVLink, inter-node DDP via network).

---

## 16. Summary

- **Distributed Orchestration** memadukan abstraksi deklaratif (Kubeflow Pipelines/Argo) dengan engine eksekusi komputasi paralel runtime (PyTorch FSDP, DeepSpeed, Ray Train).
- **PyTorch FSDP (ZeRO-3)** mengeliminasi redundansi memori di kluster dengan melakukan partisi merata atas *Parameters*, *Gradients*, dan *Optimizer States*, memungkinkan training model masif dengan interkoneksi jaringan berkecepatan tinggi.
- **Resiliensi Tingkat Enterprise** dibangun di atas lapisan dynamic orchestrator: Gang Scheduling (Volcano/Kueue) untuk alokasi resource atomik, TorchElastic rendezvous untuk autoscaling failover, dan S3-compatible asynchronous engine untuk snapshotting checkpoint stateful.
- Desain arsitektur distributed MLOps yang sukses selalu menyeimbangkan rasio komputasi terhadap komunikasi, menghindari network straggler, dan memastikan seluruh artefak tervolume serta tercatat lineage-nya secara konsisten dan reproducible.