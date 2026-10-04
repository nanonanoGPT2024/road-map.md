# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 01: Fondasi dan Arsitektur — MLOps Enterprise**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan memiliki kompetensi tingkat lanjut untuk:
1. **Merancang dan mengimplementasikan Feature Store terdistribusi** yang menjamin *point-in-time correctness* (mencegah *data leakage*) serta menyatukan definisi fitur antara *batch offline training* dan *real-time online inference*.
2. **Membangun orkestrasi pipeline pelatihan deterministik berbasis DAG** (menggunakan engine seperti Argo Workflows/Kubeflow) dengan isolasi artefak, pelacakan silsilah data (*metadata lineage*), dan eksekusi terdistribusi pada cluster Kubernetes.
3. **Mengonfigurasi infrastruktur komputasi model serving berskala masif** memanfaatkan Triton Inference Server atau TorchServe dengan teknik *dynamic batching*, optimasi engine komputasi (ONNX Runtime, TensorRT), dan partisi hardware (NVIDIA Multi-Instance GPU / MIG).
4. **Mengimplementasikan strategi deployment tingkat lanjut** (*Canary Rollout*, *Shadow Deployment*, dan *Multi-Armed Bandits*) yang diintegrasikan dengan Service Mesh (Istio) dan GitOps (ArgoCD).
5. **Membangun sistem *Continuous Training* (CT) berbasis *event-driven*** yang dipicu secara otomatis oleh deteksi penurunan performa (*performance decay*) serta penyimpangan data (*data & concept drift*).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
* Pemrograman Python tingkat lanjut (asynchronous programming, OOP, type hinting, metaclass).
* Konsep containerization dan orkestrasi: Docker internals, Kubernetes primitives (Pods, Deployments, CRDs, StatefulSets, Affinity/Tolerations, HPA).
* Dasar komputasi machine learning: PyTorch atau Scikit-Learn, optimasi gradient descent, metrik evaluasi model (AUC-ROC, LogLoss, F1-Score).
* Pemahaman dasar tentang sistem basis data terdistribusi: Perbedaan karakteristik OLTP (e.g., Redis, PostgreSQL) dan OLAP (e.g., BigQuery, ClickHouse, Parquet/S3).
* GitOps dan CI/CD pipeline fundamentals (Git branches, webhooks, runners).

---

## 3. Concept & Internal Architecture

Penerapan MLOps tingkat enterprise memisahkan sistem menjadi tiga lapisan fungsional (*Control Plane*, *Compute/Data Plane*, dan *Governance Plane*) untuk memitigasi *technical debt* bawaan sistem machine learning (Sculley et al.).

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ CONTROL PLANE                                                                 │
│ ┌──────────────────────┐  ┌───────────────────────┐  ┌──────────────────────┐ │
│ │ GitOps Repository    │  │ ML Metadata (MLMD)    │  │ Model Registry       │ │
│ │ (ArgoCD / Terraform) │  │ (Artifact Lineage)    │  │ (Version, Stage, OCI)│ │
│ └──────────┬───────────┘  └───────────▲───────────┘  └──────────▲───────────┘ │
└────────────┼──────────────────────────┼─────────────────────────┼─────────────┘
             │ Sync                     │ Metadata Logging        │ Model Push
┌────────────▼──────────────────────────┴─────────────────────────┴─────────────┐
│ DATA & COMPUTE PLANE                                                          │
│                                                                               │
│  [Raw Data Lakes] ──► [Feature Store (Feast/Hopsworks)]                       │
│                             │                  │                              │
│              (Offline Join) │                  │ (Low-latency Read)           │
│                             ▼                  ▼                              │
│         [Distributed Training (K8s)]     [Inference Mesh (Triton/Envoy)]      │
│         - PyTorch DDP / Ray Train        - Dynamic Batching                   │
│         - NVIDIA MIG Allocation          - Shadow / Canary Routing            │
│                             │                  │                              │
│                             ▼                  ▼                              │
│                     [Model Evaluation]   [Inference Logs & Predictions]       │
│                             │                  │                              │
└─────────────────────────────┼──────────────────┼──────────────────────────────┘
                              │                  │
┌─────────────────────────────▼──────────────────▼──────────────────────────────┐
│ GOVERNANCE & OBSERVABILITY PLANE                                              │
│ ┌──────────────────────────────────────┐  ┌─────────────────────────────────┐ │
│ │ Drift Engine (Evidently / Whylogs)   │  │ Prometheus / Grafana Dashboard  │ │
│ │ - KS-Test, PSI, Jensen-Shannon       │  │ - P99 Latency, GPU-Util, QPS    │ │
│ └──────────────────┬───────────────────┘  └─────────────────────────────────┘ │
│                    │ Drift Trigger Alert                                      │
│                    └────────────────► [Webhook Event: Retrain Trigger]        │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 3.1. Dual-Storage Feature Store & Point-in-Time Correctness
Tantangan terbesar sistem ML produksi adalah **Training-Serving Skew**—ketika data yang dikonsumsi saat pelatihan berbeda distribusinya dari data saat inferensi.

Feature Store mengatasi hal ini melalui dua *storage engine* dengan satu *interface* logis:
* **Offline Store (OLAP):** Menggunakan format Parquet, Apache Iceberg, Snowflake, atau DuckDB. Bertanggung jawab atas kueri agregasi historis bervolume tinggi.
* **Online Store (Low-Latency Key-Value):** Menggunakan Redis, AWS DynamoDB, atau Aerospike. Dioptimalkan untuk pembacaan sub-10ms berdasarkan *Entity ID*.

#### Mekanisme Matematis Point-in-Time Join (AS-OF Join)
Saat model dilatih pada rentang waktu historis $T$, data fitur tidak boleh mengambil nilai yang tercatat pada $t > T$ (*lookahead bias*). Jika label $L$ terjadi pada waktu $t_L$, nilai fitur $F$ yang valid adalah nilai paling mutakhir pada $t_F \le t_L$.

$$\text{Feature}(E, t_L) = \operatorname*{arg\,max}_{t_F \le t_L} \left( \text{Record}(E, t_F) \right)$$

Di mana $E$ adalah Entity ID, $t_L$ adalah *timestamp event*, dan $t_F$ adalah *timestamp update* fitur.

### 3.2. Dynamic Batching pada Triton Inference Server
Menjalankan inferensi model deep learning secara serial untuk setiap request menghasilkan utilisasi GPU yang sangat rendah (<10%) dan latensi tinggi akibat *PCIe transfer overhead*. 

Triton Inference Server mengimplementasikan algoritma **Dynamic Batching** di tingkat thread scheduler:
1. Request dari client masuk ke FIFO request queue.
2. Scheduler menahan request hingga:
   * Jumlah batch mencapai `max_batch_size`, ATAU
   * Durasi waktu tunggu mencapai `max_queue_delay_microseconds`.
3. Batch yang terkumpul dikirimkan sekaligus ke kernel GPU sebagai satu tensor berukuran $[B, C, H, W]$ atau $[B, S]$, memaksimalkan Tensor Core paralelisme.

---

## 4. Why & What

| Dimensi | Pendekatan MLOps Ad-Hoc / Konvensional | Pendekatan Enterprise MLOps (Module 02) |
| :--- | :--- | :--- |
| **Feature Engineering** | Notebook kustom, logic inferensi ditulis ulang di microservice backend (berisiko *skew*). | Unified Feature Definition; Single source of truth via Feature Store (Feast/Hopsworks). |
| **Model Reproducibility**| Bobot model `.pt` disimpan manual di bucket S3 tanpa metadata dependensi. | Immutable Model Artifact terdaftar di Model Registry dengan cryptographic hash dan OCI artifact packaging. |
| **Komputasi Pelatihan** | Single EC2/GPU instance statis; dependensi manual via SSH. | Distributed training (K8s pods dinamis) dengan autoscaling spot instances dan auto-checkpointing. |
| **Model Deployment** | Rolling restart langsung pada microservice API, downtime probabilistik. | Blue/Green, Canary berbasis Traffic Splitting (Istio), dan Shadow Deployment. |
| **Monitoring** | Hanya monitoring infrastruktur standar (CPU, RAM, HTTP status code 500). | Data Drift (PSI, Wasserstein Distance), Concept Drift, dan degradasi akurasi real-time. |

---

## 5. How (Workflow Detail)

Alur eksekusi *Continuous Training* dan *Zero-Downtime Deployment* skala enterprise:

```
[Data Stream / DWH] 
        │
        ▼ (Daily Ingestion)
[Feature Store Ingestion] ──► (Offline Parquet Sync & Online Redis Cache)
        │
        ▼ (Trigger: Data Drift Alert via EventBridge / Kafka)
[Orchestrator: Argo Workflows]
   ├── Step 1: Point-in-time extraction dari Offline Store
   ├── Step 2: Distributed PyTorch DDP via Kubeflow Training Operator
   ├── Step 3: Model Evaluator (Benchmarking vs Baseline Model di Production)
   │           ├── Syarat: F1-Score baru > F1-Score lama + 0.015
   │           └── Syarat: P99 Latency < 20ms pada Triton Bench
   └── Step 4: Push Model ke Registry (MLflow/Harbor) bertanda `candidate`
        │
        ▼ (GitOps Sync via ArgoCD)
[Deploy to Canary Environment]
   ├── 90% Traffic -> Current Production Model
   └── 10% Traffic -> Candidate Model
        │
        ▼ (Observability Window: 2 Jam)
   ├── Analisis Error Rate & KS-Test pada Prediksi
   └── IF Healthy -> Promosikan ke 100% Traffic (Canary Success)
       ELSE -> Rollback instan ke Model Sebelumnya via Envoy Routing
```

---

## 6. Analogy & Diagram ASCII

### Analogi Pabrik Manufaktur Farmasi
Bayangkan sistem MLOps enterprise sebagai pabrik obat skala global:
1. **Feature Store:** Gudang bahan baku kimia murni berstandar ISO. Bahan harus memiliki cap tanggal kadaluwarsa dan waktu ekstraksi (*point-in-time*). Tidak boleh menggunakan bahan yang belum disintesis pada tanggal produksi obat tertentu.
2. **Training Pipeline (Argo/Kubeflow):** Jalur perakitan steril otomatis. Formulasi obat dicampur dengan robotik tanpa campur tangan manual. Setiap batch memiliki nomor seri unik (*Model Lineage*).
3. **Model Registry:** Badan Pengawas Obat (BPOM/FDA). Setiap formula yang lolos harus mendapatkan sertifikasi dan segel digital sebelum didistribusikan.
4. **Triton Dynamic Batching:** Kereta logistik yang mengangkut obat dari pabrik ke apotek. Daripada mengirim 1 kotak per kurir motor (inefisien), kurir menunggu maksimal 5 menit untuk mengisi mobil boks hingga penuh sebelum berangkat bersama.
5. **Canary Deployment:** Uji klinis fase akhir terbatas pada 5% populasi pasien sebelum obat didistribusikan secara nasional.

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Definisi Feature Store dengan Feast (Python)
Kode berikut mendefinisikan entitas pengguna dan *feature view* yang mengisolasi transformasi data untuk konsistensi online-offline.

```python
# feature_definitions.py
from datetime import timedelta
from feast import (
    Entity,
    FeatureView,
    Field,
    FileSource,
    PushSource,
)
from feast.types import Float32, Int64

# 1. Definisikan Entitas Utama
user_entity = Entity(
    name="user_id",
    join_keys=["user_id"],
    description="Identitas unik akun pengguna"
)

# 2. Definisikan Sumber Data Historis (Offline Store)
user_stats_source = FileSource(
    name="user_stats_parquet_source",
    path="/data/features/user_transaction_stats.parquet",
    timestamp_field="event_timestamp",
    created_timestamp_column="created_timestamp",
)

# 3. Definisikan Feature View
user_stats_view = FeatureView(
    name="user_transaction_feature_view",
    entities=[user_entity],
    ttl=timedelta(days=30),  # Mencegah penggunaan fitur yang terlalu usang
    schema=[
        Field(name="avg_transaction_amount_30d", dtype=Float32),
        Field(name="failed_login_attempts_24h", dtype=Int64),
        Field(name="velocity_score", dtype=Float32),
    ],
    online=True,  # Sinkronisasikan secara otomatis ke Redis Online Store
    source=user_stats_source,
)
```

---

### 7.2. Practical Example: Implementasi Inference Server Production-Grade

Berikut adalah script *high-performance inference* menggunakan klien Triton berbasis `asyncio` dan pooling koneksi gRPC, lengkap dengan penanganan fallback otomatis dan dynamic batch validation.

```python
# production_inference_client.py
from dataclasses import dataclass
import numpy as np
import tritonclient.grpc.aio as grpcclient
from tritonclient.utils import InferenceServerException
import structlog
import asyncio
from typing import List, Dict, Any, Optional

logger = structlog.get_logger(__name__)

@dataclass(frozen=True)
class InferenceConfig:
    server_url: str = "localhost:8001"
    model_name: str = "fraud_detection_ensemble"
    model_version: str = "1"
    timeout_seconds: float = 0.5

class TritonProductionClient:
    def __init__(self, config: InferenceConfig):
        self.config = config
        self._client: Optional[grpcclient.InferenceServerClient] = None

    async def initialize(self) -> None:
        """Inisialisasi channel gRPC non-blocking dengan HTTP/2 keep-alive."""
        try:
            self._client = grpcclient.InferenceServerClient(
                url=self.config.server_url,
                channel_args=[
                    ("grpc.keepalive_time_ms", 10000),
                    ("grpc.keepalive_timeout_ms", 5000),
                    ("grpc.http2.max_pings_without_data", 0),
                    ("grpc.keepalive_permit_without_calls", 1),
                ]
            )
            # Pastikan server dan model siap melayani traffic
            is_ready = await self._client.is_model_ready(
                model_name=self.config.model_name,
                model_version=self.config.model_version
            )
            if not is_ready:
                raise RuntimeError(f"Model {self.config.model_name} belum dalam status READY pada Triton.")
            logger.info("triton_client_initialized", model=self.config.model_name)
        except Exception as exc:
            logger.error("triton_initialization_failed", error=str(exc))
            raise

    async def predict_fraud(self, user_features: List[Dict[str, Any]]) -> np.ndarray:
        """
        Menjalankan inferensi asynchronous berkinerja tinggi.
        Payload input: List of dicts berisi fitur numerik.
        """
        if not self._client:
            raise RuntimeError("Client belum diinisialisasi. Panggil initialize() terlebih dahulu.")

        batch_size = len(user_features)
        
        # Ekstraksi matriks fitur dari raw dictionaries (Vectorized conversion)
        # Bentuk data akhir: (Batch_Size, 3) -> Sesuai input signature Triton
        input_matrix = np.array([
            [
                item["avg_transaction_amount_30d"],
                item["failed_login_attempts_24h"],
                item["velocity_score"]
            ]
            for item in user_features
        ], dtype=np.float32)

        # Siapkan protokol input tensor gRPC
        infer_input = grpcclient.InferInput(
            name="INPUT_FEATURES",
            shape=[batch_size, 3],
            datatype="FP32"
        )
        infer_input.set_data_from_numpy(input_matrix)

        # Siapkan output tensor capture
        infer_output = grpcclient.InferRequestedOutput(name="PROBABILITY")

        try:
            # Eksekusi pemanggilan gRPC asynchronous
            response = await asyncio.wait_for(
                self._client.infer(
                    model_name=self.config.model_name,
                    model_version=self.config.model_version,
                    inputs=[infer_input],
                    outputs=[infer_output],
                ),
                timeout=self.config.timeout_seconds
            )
            
            # Ekstraksi array probabilitas output
            prediction_probs = response.as_numpy("PROBABILITY")
            return prediction_probs

        except asyncio.TimeoutError:
            logger.error("triton_inference_timeout", timeout=self.config.timeout_seconds)
            # Fallback policy: Kembalikan baseline rule-based prediction atau nilai default konservatif
            return np.full((batch_size, 1), fill_value=0.5, dtype=np.float32)
        except InferenceServerException as ise:
            logger.error("triton_server_error", grpc_code=ise.status(), message=ise.message())
            raise
        except Exception as exc:
            logger.error("unexpected_inference_error", error=str(exc))
            raise

    async def close(self) -> None:
        if self._client:
            await self._client.close()

# Simulasi Eksekusi
async def main():
    cfg = InferenceConfig()
    client = TritonProductionClient(config=cfg)
    
    # Mocking inisialisasi lokal
    try:
        await client.initialize()
        mock_input = [
            {"avg_transaction_amount_30d": 1250.50, "failed_login_attempts_24h": 0, "velocity_score": 0.12},
            {"avg_transaction_amount_30d": 99999.0, "failed_login_attempts_24h": 5, "velocity_score": 0.98},
        ]
        probabilities = await client.predict_fraud(mock_input)
        print(f"Hasil Inferensi Probabilitas Fraud: {probabilities}")
    except Exception as e:
        print(f"Server Triton simulasi sedang offline: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Fraud Detection pada Core Banking Platform
* **Latar Belakang:** Bank Digital Tier-1 memproses 45.000 transaksi pembayaran per detik ($QPS$) pada jam sibuk. Model lama mengalami degradasi performa karena pola penipuan (*fraud patterns*) bermutasi setiap beberapa hari.
* **Bottleneck Teknis Awal:**
  * Fitur pengguna diekstrak langsung via kueri runtime ke database transaksional PostgreSQL OLTP, menyebabkan latensi kueri membengkak hingga >250ms dan memicu database *connection pool exhaustion*.
  * Pelatihan ulang model dilakukan secara manual setiap akhir bulan oleh tim data science.
* **Arsitektur Solusi Enterprise:**
  1. **Dual-Store Feast Deployment:**
     * Menggunakan Apache Kafka untuk *CDC (Change Data Capture)* langsung dari database rekening ke Feast Online Store (Redis Cluster berkapasitas 256GB).
     * Latensi *feature fetch* terpangkas dari 250ms menjadi **3.2ms (p99)**.
  2. **Triton Inference Cluster pada EKS:**
     * Cluster Kubernetes menggunakan instance `g5.2xlarge` (NVIDIA A10G). Mengaktifkan dynamic batching dengan parameter:
       ```protobuf
       dynamic_batching {
         max_queue_delay_microseconds: 2000
         preferred_batch_size: [ 8, 16, 32, 64 ]
       }
       ```
     * Throughput inferensi meningkat **8.4x lipat** dibandingkan arsitektur lama berbasis Flask API.
  3. **Continuous Retraining Trigger:**
     * Drift monitor mengevaluasi skor **Population Stability Index (PSI)** setiap window 1 jam. Jika $PSI > 0.25$ pada fitur *velocity_score*, Kafka event memicu pipeline Argo Workflows untuk menjalankan proses fine-tuning model menggunakan data 48 jam terakhir.
* **Hasil Bisnis & Metrik:**
  * False Positive Rate turun 38%, menyelamatkan potensi transaksi sah senilai USD 1.2M per kuartal.
  * P99 End-to-End SLA inferensi tercapai di angka **14.8ms**, berada di bawah batas ketat regulasi kartu kredit (50ms).

---

## 9. Trade-offs

Penerapan arsitektur tingkat lanjut memerlukan kompromi rekayasa yang harus diperhitungkan:

| Parameter | Dynamic Batching Triton | Non-Batched Direct Inference | Analisis Keputusan |
| :--- | :--- | :--- | :--- |
| **P99 Latency (Individual)** | Sedikit lebih tinggi (akibat `max_queue_delay`) | Paling optimal untuk individual query (tidak ada antrean) | Jika SLA p99 < 5ms sangat ketat, matikan dynamic batching. Jika p99 toleran hingga 20-30ms, aktifkan untuk menghemat GPU. |
| **Max Throughput (QPS)** | Sangat Tinggi ($> 10.000\text{ QPS/node}$) | Rendah ($< 800\text{ QPS/node}$) | Dynamic batching mutlak dibutuhkan pada sistem volume tinggi. |
| **GPU Compute Efficiency** | 80% - 95% GPU Core Utilization | 8% - 15% GPU Core Utilization | Dynamic batching secara dramatis menurunkan *Cost per 1M Predictions*. |

| Parameter | Centralized Online Feature Store | Local In-Memory Feature Cache | Analisis Keputusan |
| :--- | :--- | :--- | :--- |
| **Data Consistency** | Global consistency, zero skew antar node | Potensi perbedaan data antar instance replica | Feature Store menjamin integritas prediksi di seluruh pod autoscaling. |
| **Network Overhead** | Tambahan 1 extra network hop gRPC/Redis (1-3ms) | Zero network hop (Local microsecond access) | Gunakan Feature Store terpusat kecuali untuk komputasi edge ultra-low-latency. |
| **Infrastruktur & Maintenance**| Memerlukan redis cluster/distributed DB yang kompleks | Sederhana, tanpa dependensi eksternal | Pertimbangkan biaya operasional Ops/DevOps tim. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Data Leakage Melalui Agregasi Temporal yang Salah
* **Kesalahan:** Menghitung fitur agregasi (misalnya `avg_transaction_amount_30d`) menggunakan fungsi agregasi SQL biasa `AVG(amount) OVER(PARTITION BY user_id)` tanpa membatasi *window frame* secara eksplisit sebelum *event timestamp* transaksi.
* **Dampak:** Model memiliki skor akurasi 99.8% pada data validasi, namun akurasinya jatuh menjadi 55% di lingkungan produksi.
* **Solusi Teknis:** Wajib menggunakan pola *AS-OF Join* pada Feature Store atau SQL window framing eksplisit:
  ```sql
  AVG(amount) OVER (
      PARTITION BY user_id 
      ORDER BY transaction_timestamp 
      RANGE BETWEEN INTERVAL '30 DAYS' PRECEDING AND INTERVAL '1 SECOND' PRECEDING
  )
  ```

### 2. OOM (Out Of Memory) Akibat Dynamic Batching yang Terlalu Agresif
* **Gejala:** Triton server melempar status error `CUDA out of memory` saat lonjakan traffic (*spike*) tiba-tiba.
* **Troubleshooting:**
  1. Periksa parameter konfigurasi Triton `max_batch_size`.
  2. Hitung alokasi VRAM statis: $\text{VRAM}_{\text{req}} = \text{Model Weight} + (B_{\text{max}} \times \text{Activation Size})$.
  3. Aktifkan memory pooling pada Triton dengan parameter flags: `--cuda-memory-pool-byte-size=0:1073741824` (1GB pinned memory pool limit).

### 3. GPU Starvation Selama Distributed Training
* **Gejala:** Utilisasi GPU fluktuatif tajam antara 0% dan 100% (gergaji).
* **Akar Masalah:** Thread CPU data loader lambat mendekode gambar/tokenisasi teks dari storage sehingga GPU harus menunggu I/O (*I/O bound bottleneck*).
* **Solusi Teknis:**
  * Naikkan nilai `num_workers` pada PyTorch DataLoader.
  * Aktifkan `pin_memory=True`.
  * Konversi dataset terdistribusi ke format binary mentah terindeks (misalnya WebDataset / TFRecords / Arrow IPC) yang diletakkan pada local NVMe scratch disk.

---

## 11. Best Practices (Production Checklist)

### Feature Engineering & Data Pipeline
- [ ] Semua definisi fitur tercatat dalam Git repositori deklaratif (*Feature Repository as Code*).
- [ ] Fitur memiliki batas waktu kadaluwarsa (*TTL / Time-To-Live*) yang dikonfigurasi eksplisit.
- [ ] Pengecekan skema data (*great expectations* atau *pandera*) berjalan sebelum data dimasukkan ke Feature Store.

### Model Architecture & Training
- [ ] Bobot model dan runtime dependencies diekspor ke format serialisasi standar (*ONNX* atau *TorchScript*).
- [ ] Setiap proses training menyimpan matriks dependensi: Git commit SHA, dataset snapshot hash, parameter seed, dan model metrics ke Metadata Store.
- [ ] Gradient accumulation atau Checkpointing aktif saat melatih model skala besar untuk mencegah *crash* mendadak.

### Inference & Serving
- [ ] Service Level Objective (SLO) inferensi memiliki batas P99 latency dan fail-safe fallback mechanism.
- [ ] Health probe Kubernetes terkonfigurasi dengan tepat (`livenessProbe` dan `readinessProbe` memvalidasi ketersediaan model weight Triton).
- [ ] Instance GPU dipartisi menggunakan teknologi NVIDIA MIG (Multi-Instance GPU) jika menjalankan beberapa model kecil dalam satu GPU fisik besar (misal: NVIDIA A100 dipartisi menjadi $7 \times 1\text{g}.10\text{gb}$).

### Observability & Drift
- [ ] Matriks komputasi infrastruktur (GPU Memory, GPU Utilization, Tensor Core Load) dialirkan ke Prometheus melalui NVIDIA DCGM Exporter.
- [ ] Pipeline monitoring menghitung nilai *Population Stability Index (PSI)* dan *Wasserstein Distance* secara berkala terhadap distribusi fitur input.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun pipeline MLOps lokal menggunakan Docker Compose yang mencakup: Redis (Online Feature Store), Triton Inference Server, dan Python Ingestion Script.

### Struktur Direktori:
```text
hands-on/m02/
├── docker-compose.yml
├── model_repository/
│   └── simple_linear/
│       ├── config.pbtxt
│       └── 1/
│           └── model.onnx
└── scripts/
    ├── generate_model.py
    └── test_inference.py
```

### Langkah 1: Buat Direktori dan File Konfigurasi Model Triton
Jalankan di terminal Anda:
```bash
mkdir -p hands-on/m02/model_repository/simple_linear/1
mkdir -p hands-on/m02/scripts
cd hands-on/m02
```

Tulis file `model_repository/simple_linear/config.pbtxt`:
```protobuf
name: "simple_linear"
platform: "onnxruntime_onnx"
max_batch_size: 64

input [
  {
    name: "INPUT_FEATURES"
    data_type: TYPE_FP32
    dims: [ 3 ]
  }
]

output [
  {
    name: "OUTPUT_SCORE"
    data_type: TYPE_FP32
    dims: [ 1 ]
  }
]

dynamic_batching {
  max_queue_delay_microseconds: 5000
  preferred_batch_size: [ 8, 16, 32, 64 ]
}
```

### Langkah 2: Buat Model Dummy ONNX
Tulis dan jalankan script Python ini di root environment Anda untuk meng-generate file ONNX:
`scripts/generate_model.py`
```python
import torch
import torch.nn as nn

class LinearInferenceModel(nn.Module):
    def __init__(self):
        super(LinearInferenceModel, self).__init__()
        self.fc = nn.Linear(3, 1)
        # Inisialisasi bobot statis
        self.fc.weight.data = torch.tensor([[0.5, -0.2, 1.2]], dtype=torch.float32)
        self.fc.bias.data = torch.tensor([0.1], dtype=torch.float32)

    def forward(self, x):
        return self.fc(x)

model = LinearInferenceModel()
model.eval()

dummy_input = torch.randn(1, 3, dtype=torch.float32)
torch.onnx.export(
    model,
    dummy_input,
    "model_repository/simple_linear/1/model.onnx",
    input_names=["INPUT_FEATURES"],
    output_names=["OUTPUT_SCORE"],
    dynamic_axes={
        "INPUT_FEATURES": {0: "batch_size"},
        "OUTPUT_SCORE": {0: "batch_size"}
    },
    opset_version=14
)
print("Model ONNX berhasil dibuat di model_repository/simple_linear/1/model.onnx")
```
Jalankan:
```bash
python scripts/generate_model.py
```

### Langkah 3: Definisikan Docker Compose
Buat file `docker-compose.yml`:
```yaml
version: '3.8'

services:
  triton-server:
    image: nvcr.io/nvidia/tritonserver:23.10-py3
    container_name: triton_local_server
    command: ["tritonserver", "--model-repository=/models", "--strict-model-config=true"]
    ports:
      - "8000:8000" # HTTP
      - "8001:8001" # gRPC
      - "8002:8002" # Metrics
    volumes:
      - ./model_repository:/models
    shm_size: '1gb'

  redis-store:
    image: redis:7.0-alpine
    container_name: redis_feature_store
    ports:
      - "6379:6379"
```

Jalankan container:
```bash
docker compose up -d
```
Pastikan status Triton berjalan sehat dengan memeriksa endpoint metrik:
```bash
curl -i http://localhost:8000/v2/health/ready
# Output harus mengembalikan HTTP 200 OK
```

### Langkah 4: Eksekusi Test Inferensi dengan Dynamic Batch Simulation
Tulis file `scripts/test_inference.py`:
```python
import tritonclient.grpc as grpcclient
import numpy as np

def run_test():
    client = grpcclient.InferenceServerClient(url="localhost:8001")
    
    # Buat batch data ukuran 4
    input_data = np.array([
        [1.0, 2.0, 3.0],
        [0.5, 1.5, -1.0],
        [2.0, 0.0, 1.0],
        [-1.0, -1.0, 0.0]
    ], dtype=np.float32)

    inputs = [grpcclient.InferInput("INPUT_FEATURES", input_data.shape, "FP32")]
    inputs[0].set_data_from_numpy(input_data)
    
    outputs = [grpcclient.InferRequestedOutput("OUTPUT_SCORE")]
    
    result = client.infer(
        model_name="simple_linear",
        inputs=inputs,
        outputs=outputs
    )
    
    predictions = result.as_numpy("OUTPUT_SCORE")
    print("\n--- INFERENCE SUCCEEDED ---")
    print(f"Bentuk Tensor Output : {predictions.shape}")
    print(f"Hasil Nilai Inferensi:\n{predictions}")

if __name__ == "__main__":
    run_test()
```
Jalankan:
```bash
pip install tritonclient[grpc] numpy
python scripts/test_inference.py
```

### Cleanup:
```bash
docker compose down -v
```

---

## 13. Exercise

### Level Easy
Tuliskan sebuah script Python murni untuk menghitung metrik **Population Stability Index (PSI)** guna membandingkan dua array distribusi probabilitas (baseline vs target). 
* Aturan: Bagi array data ke dalam 10 *quantile bins*. Abaikan pembagian dengan angka nol menggunakan epsilon $1e-4$.

### Level Medium
Implementasikan skema definisi Feature View pada Feast yang memuat fitur agregasi berbasis *On-Demand Transformation* (menghitung rasio `debt_to_income = monthly_debt / monthly_income`) secara runtime sebelum fitur dikembalikan ke API inferensi.

### Level Hard
Rancang deklarasi arsitektur **Argo Workflows DAG (YAML format)** yang mengorkestrasikan:
1. Tahap Ekstraksi Data dari S3.
2. Tahap Paralelisasi: Melatih model menggunakan 2 algoritma berbeda secara simultan (LightGBM vs XGBoost).
3. Tahap Conditional Branching: Membandingkan metrik evaluasi AUC; hanya model dengan skor AUC tertinggi yang diizinkan untuk diekspor ke Model Registry bucket.

---

## 14. Challenge

**Skenario Sistem Global E-Commerce:**
Perusahaan Anda memiliki sistem rekomendasi real-time yang melayani 200 juta pengguna di 3 benua (US, EU, APAC). Regulasi privasi (GDPR di EU) melarang data profiling pengguna mentah keluar dari zona wilayah EU. Di sisi lain, *core deep learning model* membutuhkan sinkronisasi bobot secara berkala agar tidak terjadi fragmentasi pengalaman aplikasi.

**Tugas Tantangan:**
1. Rancang arsitektur data & compute pipeline terdistribusi yang:
   * Menjaga kepatuhan data locality (GDPR).
   * Tetap dapat melakukan *cross-region model training* (misalnya mengadopsi pola Federated Learning atau Split Training).
2. Buat dokumen arsitektur teknis yang menjelaskan:
   * Desain sinkronisasi Feature Store antar-region (komponen apa yang di-*replicate*, apa yang di-*shard*).
   * Strategi canary routing lintas region menggunakan Envoy Service Mesh dan ArgoCD Application Sets.
   * Mekanisme penanganan failover jika satu region Triton Inference Cluster mengalami pemadaman total (*outage*).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic
1. Apa akar penyebab terjadinya *Training-Serving Skew* dalam siklus hidup machine learning?
2. Jelaskan fungsi mendasar dari konsep *Point-in-Time Correctness* pada Feature Store!
3. Mengapa inferensi GPU menggunakan framework serial (seperti native Python interpreter) sering kali menghasilkan utilisasi hardware yang rendah?
4. Apa peran dari *Model Registry* dalam pipeline MLOps dibandingkan dengan penyimpanan object storage biasa (seperti raw AWS S3)?
5. Pada kondisi apa strategi *Shadow Deployment* lebih disukai daripada *Canary Deployment*?

### 15.2. Pertanyaan Intermediate
6. Bagaimana cara kerja algoritma *Dynamic Batching* pada Triton Inference Server dalam menyeimbangkan antara efisiensi throughput dan batas toleransi latensi per request?
7. Mengapa metrik Kolmogorov-Smirnov Test (KS-Test) atau Population Stability Index (PSI) lebih relevan digunakan untuk memicu *Continuous Training* otomatis daripada metrik akurasi (misal F1-score) di sistem produksi real-time?
8. Bagaimana implementasi teknologi partisi NVIDIA MIG (Multi-Instance GPU) dapat menghemat total biaya komputasi inferensi di cluster Kubernetes?
9. Jelaskan bagaimana Service Mesh (misal Envoy / Istio) melakukan pembagian traffic (*traffic splitting*) berbasis HTTP headers pada Canary Rollout model ML!
10. Apa risiko teknis dari mengatur parameter *Time-To-Live (TTL)* fitur yang terlalu panjang pada Feature Store?

### 15.3. Skenario Kasus Produksi
11. **Skenario 1:** Model pendeteksi transaksi penipuan Anda tiba-tiba mengalami lonjakan tajam pada metrik inferensi P99 latency (dari 15ms menjadi 600ms) saat jam diskon flash sale, namun utilisasi komputasi GPU Triton tercatat hanya 35%. Komponen mana dalam arsitektur yang paling mungkin menjadi *bottleneck*, dan bagaimana Anda membuktikannya?
12. **Skenario 2:** Pipeline evaluasi offline model Anda menyatakan model baru memiliki AUC 0.94 (model lama 0.88). Namun saat model baru di-rollout ke 10% canary traffic, tingkat konversi bisnis pengguna anjlok drastis sebesar 25%. Langkah forensik apa yang harus Anda lakukan untuk melacak sumber anomali tersebut?
13. **Skenario 3:** Tim keamanan enterprise mewajibkan bahwa seluruh model artifact yang dideploy ke cluster Kubernetes produksi harus memiliki jaminan integritas kriptografis dan tidak dapat dimodifikasi (*immutable & signed*). Bagaimana Anda mengintegrasikan *Cosign/Sigstore* dan *Kyverno/OPA Gatekeeper* ke dalam GitOps MLOps pipeline Anda?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Jawaban Pertanyaan Basic
1. Perbedaan transformasi data antara tahap pelatihan (*offline*, biasanya dijalankan dalam batch script) dan tahap inferensi (*online*, ditulis ulang pada backend service), serta penggunaan data masa depan (*data leakage*) saat pelatihan.
2. Menjamin data fitur yang diekstrak untuk data pelatihan merefleksikan kondisi aktual tepat pada saat *event* masa lalu terjadi, mencegah model belajar dari informasi yang belum tersedia (*lookahead bias*).
3. Karena CPU overhead, overhead transfer memori host-to-device melalui bus PCIe, dan ketidakmampuan native single thread mengisi ribuan CUDA compute cores secara paralel tanpa batching tensor.
4. Model Registry menyediakan *governance*: cryptographic hash, semantic versioning, tracking artifact lineage (input data hash, hyperparameter), approval stage gates, dan integrasi penandatanganan image/artifact metadata.
5. Ketika risiko bisnis akibat kegagalan prediksi model baru sangat tinggi (misal: pemberian limit kredit berisiko tinggi atau sistem kemudi otonom), sehingga model baru harus diuji secara pasif terhadap traffic live 100% tanpa memberikan output aktual kepada pengguna akhir.

#### Jawaban Pertanyaan Intermediate
6. Triton menggunakan internal queue; scheduler menunggu hingga tensor input terkumpul sebesar `preferred_batch_size` atau hingga waktu tunggu mencapai batas `max_queue_delay_microseconds`. Begitu salah satu kondisi tercapai, request digabungkan menjadi single batched tensor dan dieksekusi oleh engine.
7. Dalam sistem live, *ground truth label* sering kali tertunda berhari-hari atau berminggu-minggu (contoh: label *fraud chargeback* baru muncul 30 hari kemudian). Metrik distribusi data (PSI/KS-Test) dapat dihitung seketika tanpa membutuhkan ketersediaan ground truth label.
8. MIG memungkinkan satu kartu fisik (misal NVIDIA A100) dipecah di tingkat hardware menjadi beberapa GPU instance mandiri yang terisolasi secara memori, cache, dan compute core. Ini mencegah model-model kecil saling memperebutkan resource atau memonopoli satu GPU penuh yang mahal.
9. Service mesh mencegat traffic pada level reverse proxy (Envoy). Envoy membaca routing rules virtual service; traffic dengan bobot tertentu (misal 90:10) atau dengan custom HTTP header (`X-Model-Version: Candidate`) diarahkan ke Kubernetes Service target yang sesuai tanpa modifikasi kode aplikasi.
10. Data fitur historis yang telah mengalami perubahan distribusi drastis tetap disajikan ke model, menyebabkan model mengambil keputusan berdasarkan representasi status entitas yang sudah usang (*stale feature degradation*).

#### Jawaban Skenario Kasus Produksi
11. **Analisis Masalah:** Bottleneck hampir dipastikan bukan pada kernel inferensi GPU, melainkan pada:
    * *Feature retrieval latency* dari Online Feature Store (jaringan atau redis engine saturation).
    * Antrean request Triton tersendat pada thread IO gRPC atau saturasi socket connection.
    * Parameter `max_queue_delay_microseconds` dikonfigurasi terlalu besar dengan request rate yang tidak merata.
    * **Pembuktian:** Periksa metrik internal Triton `nv_inference_request_duration_us` (pisahkan grafik antara `compute_input`, `compute_infer`, dan `compute_output`). Jika durasi `compute_infer` kecil (misal 5ms) tetapi total request duration 600ms, bottleneck terjadi pada antrean transfer queue atau upstream data fetching.
12. **Forensik Anomali:**
    * Periksa kemungkinan *Lookahead Bias*: Cek apakah dataset evaluasi offline tidak sengaja memuat kolom fitur yang nilainya baru terupdate setelah event konversi terjadi.
    * Skew Skema Fitur: Bandingkan *summary statistics* (mean, variance, null-count) dari input tensor yang diterima oleh pod Canary secara live dengan dataset training offline menggunakan Evidently/Whylogs.
    * Pastikan *serialization format*: Cek apakah ada perbedaan implementasi tokenisasi/scaling (misal StandardScaler tidak disimpan fit parameter-nya dan ter-recompute secara parsial pada input canary).
13. **Implementasi Security Gate:**
    * Di akhir pipeline CI/CD (misal GitHub Actions/Tekton), setelah model lulus uji regresi, bobot model ditandatangani menggunakan *Cosign* dengan private key enterprise atau *keyless OIDC identity*.
    * Tandatangan dan metadata digest disimpan di Open Container Initiative (OCI) registry bersama model artifact.
    * Di cluster Kubernetes, pasang *Kyverno* admission controller policy yang mencegat setiap pembuatan Pod Triton Inference. Kyverno memverifikasi tanda tangan kriptografis dari model artifact yang ditarik oleh Init Container. Jika *signature* tidak valid atau tidak cocok dengan public key otoritas internal, admission webhook menolak Deployment Pod tersebut masuk ke cluster.

---

## 16. Summary

Arsitektur MLOps enterprise melampaui otomatisasi script sederhana; ia menuntut integrasi yang ketat antara rekayasa sistem terdistribusi, tata kelola data, dan optimasi hardware akselerator.

Fondasi stabilitas sistem machine learning produksi bersandar pada tiga pilar utama:
1. **Integritas Fitur (Feature Stores):** Menghilangkan *Training-Serving Skew* dengan menjamin konsistensi definisi komputasi dan ketepatan temporal (*point-in-time correctness*).
2. **Efisiensi Komputasi Inferensi (Model Serving Engine):** Mengoptimalkan pemanfaatan akselerator GPU melalui *Dynamic Batching*, optimasi compiler (ONNX/TensorRT), dan partisi hardware (MIG).
3. **Resiliensi Operasional (Continuous Training & Deployment):** Menutup loop umpan balik operasional dengan mendeteksi *data drift* secara real-time dan mengeksekusi *Zero-Downtime Deployment* yang aman melalui Service Mesh dan GitOps.