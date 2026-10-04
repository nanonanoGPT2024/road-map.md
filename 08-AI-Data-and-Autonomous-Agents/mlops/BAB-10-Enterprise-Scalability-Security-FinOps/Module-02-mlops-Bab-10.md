# Bab 10: Enterprise Scalability, Security, & FinOps
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang Arsitektur Skalabilitas Inferensi Terdistribusi:** Mengonfigurasi Kubernetes Event-driven Autoscaling (KEDA) berbasis metrik latensi p99, throughput per-GPU, dan kedalaman antrean permintaan (*request queue depth*) pada Triton Inference Server atau vLLM.
- **Mengimplementasikan ML Supply Chain Security:** Menerapkan proses penandatanganan kriptografis (*model signing*) dan verifikasi integritas artefak model menggunakan Sigstore Cosign, mengelola Software Bill of Materials (SBOM) untuk pipeline ML, dan mengamankan komunikasi antar-layanan melalui Zero Trust Service Mesh (mTLS).
- **Membangun Sistem FinOps Terotomatisasi:** Membangun telemetri *cost attribution* berbasis tenant menggunakan Kubecost dan Prometheus untuk model inference, serta mengeksekusi arsitektur *spot instance orchestration* dengan *graceful draining* dan checkpointing deterministik.
- **Mengeksekusi Kebijakan Tata Kelola Data & Model Enterprise:** Mengisolasi data sensitif melalui enkripsi *at-rest* dan *in-transit* (KMS/Vault), mengaudit *data/model lineage*, dan menerapkan *role-based access control* (RBAC) granular hingga level layer atau bobot model tertentu.

---

### 2. Prerequisites

Sebelum memulai modul ini, Anda wajib memiliki pemahaman mendalam tentang:
- **Kubernetes Tingkat Lanjut:** Custom Resource Definitions (CRDs), Horizontal Pod Autoscaler (HPA), Topology Spread Constraints, dan Device Plugins (NVIDIA GPU Operator).
- **Inference Runtimes:** Triton Inference Server, vLLM, atau TorchServe (arsitektur engine, dynamic batching, paged attention).
- **Container Security & PKI:** Docker multi-stage builds, rootless containers, X.509 certificates, Open Policy Agent (OPA) / Gatekeeper.
- **Observability:** Prometheus Operator, Grafana PromQL, OpenTelemetry tracing.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi MLOps skala enterprise berada pada irisan antara efisiensi komputasi akselerator (GPU/TPU), pertahanan keamanan berlapis (*defense-in-depth*), dan kepatuhan finansial (*unit economics*).

```
+-----------------------------------------------------------------------------------+
|                           ENTERPRISE MLOPS RUNTIME                                |
+-----------------------------------------------------------------------------------+
|  [ INGRESS LAYER ]                                                                |
|  API Gateway (Envoy / Istio) ---> mTLS Strict Auth & SPIFFE/SPIRE Identity         |
|         |                                                                         |
|         v                                                                         |
|  [ SECURE SUPPLY CHAIN VERIFICATION ]                                             |
|  Kyverno / Gatekeeper Hook ---> Verifikasi Cosign Model Signature & Attestation    |
|         |                                                                         |
|         v                                                                         |
|  [ AUTOSCALING CONTROLLER (KEDA) ]                                                |
|  Prometheus Metrics Engine <--- Queue Depth (vLLM/Triton)                         |
|         | ScaledObject HPA                                                        |
|         v                                                                         |
|  [ GPU COMPUTE POOL (EKS/GKE) ]                                                   |
|  +-----------------------------------+  +--------------------------------------+  |
|  | Node Pool 1: On-Demand (Baseline) |  | Node Pool 2: Spot Instances (Spikes) |  |
|  | - Pod: Triton/vLLM Instance A     |  | - Pod: Triton/vLLM Instance C        |  |
|  | - DaemonSet: DCGM-Exporter        |  | - AWS Node Termination Handler       |  |
|  +-----------------------------------+  +--------------------------------------+  |
|         |                                                                         |
|         v                                                                         |
|  [ FINOPS & ATTRIBUTION ]                                                         |
|  OpenCost / Kubecost Pod Engine ---> Menghitung GPU-Hour per Tenant/Namespace      |
|  Prometheus ---> Export Metrik Biaya ke Enterprise Data Warehouse (BigQuery/S3)   |
+-----------------------------------------------------------------------------------+
```

#### A. GPU Scheduling & Topology-Aware Placement
Pada node multi-GPU (misal, 8x NVIDIA H100 SXM5), latensi *inter-GPU communication* sangat bergantung pada topologi NVLink. Jika pod terdistribusi pada GPU yang melintasi socket NUMA berbeda tanpa NVLink switch traversal yang optimal, latensi *all-reduce* pada pipeline/tensor parallelism meningkat drastis. Runtime inferensi harus dikonfigurasi menggunakan `topology-aware scheduling` melalui Kubernetes SRIOV atau Volcano Scheduler untuk menjamin bahwa model yang membutuhkan Tensor Parallelism ($TP > 1$) di-deploy pada GPU dengan interkoneksi langsung NVSwitch.

#### B. ML Supply Chain Security (Model Provenance & Integrity)
Berbeda dengan software supply chain tradisional, artefak model ML berukuran gigabyte hingga terabyte dalam format biner (misal: SafeTensors, GGUF, ONNX). Format lama seperti Python `pickle` rentan terhadap *arbitrary code execution*. 
Pilar keamanan pipeline ML enterprise:
1. **Safe Serialization:** Larangan mutlak terhadap format `pickle` (`.pt`, `.pkl`); wajib menggunakan format zero-copy deserialization seperti `SafeTensors`.
2. **Cryptographic Signing (Sigstore Cosign):** Hash SHA-256 dari bobot model ditandatangani menggunakan OIDC ephemeral key (*keyless signing*) dan dicatat dalam append-only transparency log (Rekor).
3. **Dynamic Admission Control:** Cluster menolak Pod inferensi jika *attestation signature* model di S3/OCI registry tidak cocok dengan public key otoritas deployment.

#### C. FinOps: Cost Attribution Engine & Spot Interruption Lifecycle
Biaya GPU menyumbang 70-85% dari total TCO (Total Cost of Ownership) platform ML. 
- **Graceful Draining:** Node Termination Handler (NTH) menangkap sinyal terminasi instance Spot (2 menit sebelum terminasi pada AWS, 30 detik pada GCP). Model server harus menolak request baru, menyelesaikan inferensi *in-flight*, dan me-route trafik ke node On-Demand melalui penyesuaian readiness probe.
- **Attribution Equation:** Biaya inferensi dihitung per-token atau per-request menggunakan rumus:
  $$\text{Cost}_{\text{tenant}} = \sum_{i=1}^{M} \left( \frac{\text{Execution Time}_{i}}{\text{Total GPU Allocation Time}} \times \text{Cost}_{\text{GPU/Hour}} \right) + \text{Cost}_{\text{idle-share}}$$

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional / Pemula | Pendekatan Enterprise Terstandarisasi |
| :--- | :--- | :--- |
| **Model Scaling** | Berbasis CPU/Memory Utilization HPA standar. | Autoscaling berbasis queue depth (KEDA) dan GPU Tensor Core duty cycle (NVIDIA DCGM). |
| **Model Storage & Delivery** | Model diunduh via script `initContainer` menggunakan `curl`/`wget` dari bucket publik. | Model diperlakukan sebagai OCI Artifacts, ditandatangani via Cosign, dimuat via memory-mapped distributed cache (JuiceFS / Lustre). |
| **Keamanan Inferensi** | HTTP polos internal cluster; tidak ada verifikasi integritas file bobot. | Zero Trust (Istio mTLS dengan SPIFFE ID), format SafeTensors tervalidasi via Open Policy Agent Gatekeeper. |
| **FinOps & Biaya** | Tagging manual di tingkat cloud provider; tagihan dibagi rata ke seluruh departemen. | *Chargeback* dan *Showback* real-time berbasis namespace/tenant menggunakan Kubecost dan metrik kustom vLLM/Prometheus. |

---

### 5. How (Workflow Detail)

Alur kerja operasional end-to-end terdiri dari 3 fase:

```
[ Phase 1: Build & Sign Artifact ]
Data Science Team ---> Training Pipeline ---> Model Export (SafeTensors)
       |
       v
Cosign CLI (CI/CD) ---> Sign SHA-256 digest via OIDC Identity Provider (Vault/GitHub Actions)
       |
       v
Push to Enterprise OCI Registry (Harbor / AWS ECR)

[ Phase 2: Secure Deployment ]
GitOps (ArgoCD) ---> Trigger Deployment Manifest
       |
       v
Kubernetes Admission Webhook (Kyverno) ---> Validasi Signature model terhadap Rekor Log
       |
       +---> [Valid]   ---> Mount Storage via CSI Driver & Spin up Pods
       +---> [Invalid] ---> Drop Deployment & Alert Security SOC

[ Phase 3: Autoscaling & FinOps Observation ]
Production Traffic ---> Envoy Gateway
       |
       v
Triton / vLLM Instance Processing
       |
       +---> Prometheus Metric: `vllm:num_requests_waiting`
       |          |
       |          v
       |     KEDA ScaledObject: Menambah Pod jika queue > threshold
       |
       +---> Kubecost Daemon: Membaca NVIDIA DCGM GPU Utilization
                  |
                  v
             Atribusi FinOps per Customer ID / Request Header
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Logistik Bandara Internasional
- **GPU Cluster** diibaratkan landasan pacu pesawat (*runway*). Runway sangat mahal untuk dibangun dan dirawat.
- **KEDA (Queue-based Scaling)** adalah *Air Traffic Controller* (ATC). ATC tidak menambah runway berdasarkan seberapa lelah petugas di lapangan (CPU/Memory), melainkan berdasarkan **berapa banyak pesawat yang sedang berputar di udara menunggu giliran mendarat** (*queue depth*).
- **Cosign & Gatekeeper** adalah petugas Bea Cukai dan Keamanan. Mereka tidak mengizinkan kargo masuk ke pesawat kecuali memiliki segel diplomatik yang belum rusak, diverifikasi secara digital, dan tercatat dalam manifes internasional (*transparency log*).
- **FinOps** adalah sistem tiket presisi. Setiap maskapai membayar sewa runway tepat sejumlah detik ban pesawat mereka menyentuh aspal, bukan dibagi rata ke seluruh maskapai yang terdaftar di bandara.

---

### 7. Simple Example & Practical Example

#### A. Triton Inference Server: Dynamic Batching & Model Configuration
Contoh file `config.pbtxt` untuk optimasi throughput inferensi dengan Dynamic Batching pada TensorRT engine:

```protobuf
name: "ensemble_fraud_detection"
platform: "tensorrt_plan"
max_batch_size: 128

input [
  {
    name: "input_features"
    data_type: TYPE_FP32
    dims: [ 64 ]
  }
]
output [
  {
    name: "probabilities"
    data_type: TYPE_FP32
    dims: [ 2 ]
  }
]

# Optimal dynamic batching config
dynamic_batching {
  max_queue_delay_microseconds: 5000 # Maksimal tunggu 5ms untuk agregasi batch
  preferred_batch_size: [ 16, 32, 64, 128 ]
}

# Instance allocation across GPUs
instance_group [
  {
    count: 2
    kind: KIND_GPU
    gpus: [ 0 ]
  }
]
```

#### B. KEDA ScaledObject: Autoscaling Berbasis Queue Depth vLLM
Manifest KEDA berikut mengatur autoscaling pod vLLM berbasis metrik Prometheus `vllm:num_requests_waiting`:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: vllm-llama3-autoscaler
  namespace: ml-inference
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vllm-llama3-70b
  minReplicaCount: 2
  maxReplicaCount: 10
  cooldownPeriod: 300
  pollingInterval: 15
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleDown:
          stabilizationWindowSeconds: 600 # Hindari flapping
          policies:
          - type: Percent
            value: 20
            periodSeconds: 60
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus-k8s.monitoring.svc.cluster.local:9090
      metricName: vllm_num_requests_waiting
      threshold: '5' # Scale up jika ada rata-rata > 5 request mengantre
      query: sum(vllm:num_requests_waiting{namespace="ml-inference"})
```

#### C. Production Python Script: Supply Chain Integrity & Cost Metric Scraper
Script Python production-grade untuk memverifikasi model signature via Cosign binary execution wrapper dan mengekspor metrik cost-per-inference ke Prometheus:

```python
#!/usr/bin/env python3
import json
import logging
import subprocess
import time
from typing import Dict, Any
from prometheus_client import start_http_server, Counter, Gauge

# Configure enterprise-grade logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s", "level":"%(levelname)s", "module":"%(name)s", "message":"%(message)s"}'
)
logger = logging.getLogger("mlops-runtime-guard")

# Prometheus Metrics
MODEL_VERIFICATION_STATUS = Gauge(
    'mlops_model_signature_verified',
    'Status verifikasi tanda tangan kriptografis model (1=Valid, 0=Invalid)',
    ['model_name', 'model_version']
)
INFERENCE_COST_ESTIMATE = Counter(
    'mlops_inference_estimated_cost_usd',
    'Estimasi biaya komputasi inferensi berdasarkan GPU utilization',
    ['tenant_id', 'model_name']
)

# Cost constant: AWS p4d.24xlarge (8x A100) ~ $32.77/hour -> ~$0.001138 per GPU-second
HOURLY_RATE_PER_GPU = 4.09625
COST_PER_GPU_SECOND = HOURLY_RATE_PER_GPU / 3600.0

class SecurityVerificationError(Exception):
    """Raised ketika model gagal diverifikasi."""
    pass

class ModelSecurityValidator:
    @staticmethod
    def verify_cosign_signature(image_ref: str, public_key_path: str) -> bool:
        """
        Memverifikasi tanda tangan image OCI model menggunakan Cosign.
        """
        command = [
            "cosign", "verify",
            "--key", public_key_path,
            image_ref
        ]
        logger.info(f"Memulai verifikasi integritas untuk artefak: {image_ref}")
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("Verifikasi model berhasil. Audit payload: %s", result.stdout.strip())
            return True
        except subprocess.CalledProcessError as err:
            logger.error("Verifikasi Cosign GAGAL: %s", err.stderr.strip())
            return False

class FinOpsTelemetryTracker:
    def __init__(self, tenant_id: str, model_name: str):
        self.tenant_id = tenant_id
        self.model_name = model_name
        self.start_time = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time
        cost = duration * COST_PER_GPU_SECOND
        INFERENCE_COST_ESTIMATE.labels(
            tenant_id=self.tenant_id,
            model_name=self.model_name
        ).inc(cost)
        logger.info(
            "Telemetry FinOps direkam",
            extra={
                "tenant": self.tenant_id,
                "latency_sec": duration,
                "cost_usd": cost
            }
        )

# Pipeline Execution Simulation
if __name__ == "__main__":
    MODEL_REF = "registry.enterprise.internal/ml-models/fraud-detection:v2.1.0"
    PUB_KEY = "/etc/pki/cosign/cosign.pub"

    # Start metrics server
    start_http_server(8080)
    logger.info("Prometheus telemetry endpoint live pada port :8080")

    # Step 1: Security Validation Gate
    is_valid = ModelSecurityValidator.verify_cosign_signature(MODEL_REF, PUB_KEY)
    if not is_valid:
        MODEL_VERIFICATION_STATUS.labels(model_name="fraud-detection", model_version="v2.1.0").set(0)
        raise SecurityVerificationError("Integritas model diragukan. Pipeline deployment dibatalkan.")
    
    MODEL_VERIFICATION_STATUS.labels(model_name="fraud-detection", model_version="v2.1.0").set(1)

    # Step 2: Simulated Inference Execution with FinOps Metering
    while True:
        with FinOpsTelemetryTracker(tenant_id="banking-fraud-division", model_name="fraud-detection"):
            # Simulasi waktu eksekusi inferensi
            time.sleep(0.045)  # 45ms inferensi batch
        time.sleep(1)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Global FinTech Payment Network
- **Skala:** 45.000 transaksi pembayaran per detik (TPS) pada jam sibuk global.
- **SLA:** Latensi inferensi model p99 < 15ms. Zero downtime deployment.
- **Audit Mandat:** Kepatuhan regulasi perbankan PCI-DSS v4.0 dan SOC2 Type II.

#### Permasalahan:
1. **GPU Under-utilization vs Cost:** Tim platform mengalokasikan pool node GPU On-Demand (A100) statis untuk mengantisipasi spike, menyebabkan $420.000/bulan terbuang sia-sia saat off-peak hours (GPU allocation ~18%).
2. **Security Vulnerability:** Data scientist mengimpor bobot model HuggingFace `.bin` (pickle based) secara langsung ke cluster produksi.
3. **No Multi-Tenancy Attribution:** Beban komputasi AI digunakan oleh unit bisnis Retail, Wealth Management, dan Commercial Payments, namun seluruh biaya GPU dibebankan pada tim IT Infrastructure.

#### Solusi Arsitektur:
1. **Spot Instance Hybrid Node Pool:**
   - 30% kapasitas dasar ditangani oleh On-Demand node pool.
   - 70% beban dinamis ditangani oleh Spot Instance pool.
   - Diterapkan `aws-node-termination-handler` dengan integrasi EventBridge untuk menangkap sinyal terminasi 120 detik, lalu mengirim `SIGTERM` terkoordinasi ke pod Triton.
2. **KEDA Driven by Triton Metric:**
   - HPA CPU standar digantikan KEDA dengan metrik `nv_inference_queue_duration_us`. Jika antrean melebihi 2.000 microsecond, trigger auto-scale horizontal secara instan.
3. **Cosign Zero-Trust Admission Webhook:**
   - Kyverno cluster policy memblokir semua pod yang mencoba memuat image model tanpa tag cryptographically signed dari enterprise HSM (*Hardware Security Module*). Format model dikonversi paksa ke TensorRT engine yang disimpan dalam blob SafeTensors.
4. **Per-Tenant Chargeback Engine:**
   - Menyisipkan metadata `X-Tenant-ID` ke Envoy routing header. Metrik internal Triton dikorelasikan via OpenTelemetry Span dan diproses oleh Kubecost untuk menghitung *cost per transaction*.

#### Hasil Terukur:
- **Biaya Infrastruktur GPU:** Turun sebesar **58%** (penghematan $243.600/bulan).
- **Keamanan:** 100% supply chain model lolos audit SOC2 Type II tanpa temuan kritis.
- **Stabilitas:** Availability inferensi bertahan di 99,995% meskipun terjadi 38 peristiwa terminasi spot instance per minggu.

---

### 9. Trade-offs

| Pendekatan / Pilihan | Keuntungan | Kerugian & Batasan | Mitigasi Engineering |
| :--- | :--- | :--- | :--- |
| **Spot Instance vs On-Demand untuk Akselerator AI** | Menghemat biaya komputasi GPU hingga 60-70%. | Risiko *interruption* sewaktu-waktu; ketersediaan GPU spot di cloud provider sering langka (*stockouts*). | Implementasikan *Hybrid Fallback Architecture*: jika spot gagal dialokasikan dalam 30 detik, fallback otomatis ke On-Demand melalui prioritas Karpenter / Cluster Autoscaler. |
| **Dynamic Batching (Triton/vLLM)** | Menghasilkan throughput total yang eksponensial lebih tinggi; utilitas Tensor Core optimal. | Menambah latensi p99 untuk request individu yang masuk pertama di antrean batching window. | Set batas ketat `max_queue_delay_microseconds` (contoh: 2ms - 5ms) agar penambahan throughput tidak mengorbankan SLA p99 latency. |
| **Model Weight Encryption at Rest & In Flight** | Melindungi intellectual property dan mencegah *data tampering* model internal. | Menambah overhead latensi startup pod saat deserialisasi dan verifikasi kunci kriptografis. | Terapkan caching in-memory node-level (ramdisk/tmpfs) yang diamankan oleh eBPF access boundary. |
| **Queue-depth Scaling vs GPU Duty-Cycle Scaling** | Queue-depth mendeteksi bottleneck *sebelum* GPU overload (leading indicator). | Metrik antrean bisa sangat fluktuatif (*noisy*) sehingga rentan memicu *pod thrashing*. | Terapkan HPA scale-down stabilization window yang panjang (5-10 menit) dan *step-wise scaling algorithm*. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum #1: Autoscaling Berbasis Metrik CPU/RAM pada Inferensi GPU
- **Gejala:** Request timeout masif terjadi saat lonjakan trafik, namun HPA tidak menambah pod.
- **Penyebab:** Eksekusi komputasi terjadi di GPU VRAM. CPU host pod sering kali idle (<15%) hanya bertindak sebagai I/O multiplexer. HPA standar berbasis CPU tidak mendeteksi beban komputasi.
- **Solusi:** Hentikan penggunaan resource metric CPU/Memory. Gunakan KEDA dengan metrik `nv_inference_request_summary_count` atau request queue duration dari NVIDIA DCGM / Triton metrics exporter.

#### Kesalahan Umum #2: Deadlock GPU Memory Saat Scale-Up Pod Baru
- **Gejala:** Pod baru masuk status `CrashLoopBackOff` dengan error: `CUDA out of memory (OOM-Killed)`.
- **Penyebab:** Konfigurasi `resources.limits.nvidia.com/gpu` tidak memperhitungkan memory overhead dari framework driver, unified memory, atau context KV cache allocation yang greedy (misal: vLLM default mengalokasikan 90% GPU RAM via `gpu_memory_utilization`).
- **Solusi:** Set parameter `--gpu-memory-utilization` ke angka realistis (misal: 0.80 atau 0.85) untuk memberikan ruang bagi dynamic memory expansion dan buffer sistem.

#### Kesalahan Umum #3: Silent Failure pada Spot Instance Termination
- **Gejala:** Client menerima error HTTP 502/504 Bad Gateway secara berkala.
- **Penyebab:** Pod terbunuh paksa (*SIGKILL*) oleh Kubernetes karena node spot langsung di-shutdown oleh cloud provider sebelum inference server sempat menyelesaikan request.
- **Solusi:** Pasang konfigurasi `preStop` hook pada pod manifest untuk mengubah status health probe server menjadi *unhealthy*, tunggu selama 10-15 detik untuk membiarkan in-flight request tuntas, baru jalankan shutdown logic:
```yaml
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "curl -X POST http://localhost:8000/v2/models/model_name/unload; sleep 15"]
```

---

### 11. Best Practices (Production Checklist)

#### Security & Compliance:
- [ ] Bobot model hanya disimpan dalam format `SafeTensors` atau binary engine terkompilasi (TensorRT, ONNX). Tidak ada deserializer Python pickle yang berjalan di runtime.
- [ ] Semua image model dan container di-*sign* menggunakan Sigstore Cosign dan diverifikasi secara wajib melalui Kyverno/Gatekeeper admission controller.
- [ ] Network policy default adalah `deny-all`; komunikasi antar model pipeline wajib dienkripsi dengan mTLS (Istio Strict Mode).

#### Scalability & Reliability:
- [ ] Menggunakan KEDA untuk autoscaling berbasis kedalaman antrean eksternal atau metrik runtime inferensi (bukan metrik node OS).
- [ ] Menetapkan `podAntiAffinity` agar pod replika tidak terkonsentrasi pada physical host GPU atau Availability Zone yang sama.
- [ ] Menyediakan `TopologySpreadConstraints` untuk mendistribusikan beban secara seimbang melintasi zone komputasi.

#### FinOps:
- [ ] Labeling wajib pada setiap manifest Kubernetes: `cost-center`, `tenant-id`, `model-family`, `environment`.
- [ ] Mengonfigurasi arsitektur node pool gabungan: On-Demand untuk reservasi minimum (baseline), Spot Instances untuk elastisitas lonjakan beban (burst).
- [ ] Kubecost / OpenCost terintegrasi penuh untuk mengirim laporan agregasi biaya GPU per-token atau per-request ke dashboard FinOps enterprise setiap 24 jam.

---

### 12. Hands-on Practice

Dalam sesi praktikum ini, Anda akan menyusun artefak keamanan model, mengonfigurasi admission enforcement, dan menyusun rule autoscaling KEDA.

#### Struktur Direktori:
```
hands-on/m02/
├── manifests/
│   ├── deployment.yaml
│   ├── keda-autoscaler.yaml
│   └── kyverno-policy.yaml
├── scripts/
│   ├── sign_model.sh
│   └── verify_and_test.sh
└── certs/
    └── cosign.pub
```

#### Langkah 1: Generate Keypair & Sign Artifact Model
Jalankan script untuk membuat kunci kriptografi dan menandatangani container image model inferensi:

```bash
# Simpan di hands-on/m02/scripts/sign_model.sh
#!/usr/bin/env bash
set -euo pipefail

mkdir -p ../certs
cd ../certs

# 1. Generate keypair lokal (gunakan KMS jika di cloud enterprise)
cosign generate-key-pair

echo "Keypair berhasil dibuat. Public key tersimpan di hands-on/m02/certs/cosign.pub"

# 2. Simulasi penandatanganan image model (ganti dengan image repo aktual)
MODEL_IMAGE="my-registry.local/ml-models/fraud-detector:v1.0"
echo "Menandatangani target model image: ${MODEL_IMAGE}"
# cosign sign --key cosign.key ${MODEL_IMAGE}
```

#### Langkah 2: Buat Kyverno Policy untuk Verifikasi Signature Wajib
Buat manifest kebijakan admission controller:

```yaml
# Simpan di hands-on/m02/manifests/kyverno-policy.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-ml-model-signature
spec:
  validationFailureAction: Enforce
  background: false
  rules:
    - name: verify-signature-rule
      match:
        any:
        - resources:
            namespaces:
              - ml-inference
            kinds:
              - Pod
      verifyImages:
      - imageReferences:
        - "my-registry.local/ml-models/*"
        key: |-
          -----BEGIN PUBLIC KEY-----
          MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE... (paste isi cosign.pub di sini)
          -----END PUBLIC KEY-----
```

#### Langkah 3: Konfigurasi Deployment dengan Node Draining Lifecycle
Buat deployment inferensi yang FinOps-ready:

```yaml
# Simpan di hands-on/m02/manifests/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: triton-fraud-model
  namespace: ml-inference
  labels:
    app: triton-fraud
    finops.cost-center: "fraud-prevention-unit"
    finops.tier: "critical"
spec:
  replicas: 2
  selector:
    matchLabels:
      app: triton-fraud
  template:
    metadata:
      labels:
        app: triton-fraud
        finops.cost-center: "fraud-prevention-unit"
    spec:
      terminationGracePeriodSeconds: 120
      affinity:
        nodeAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 80
            preference:
              matchExpressions:
              - key: topology.kubernetes.io/instance-type-category
                operator: In
                values: ["spot"]
      containers:
      - name: triton-server
        image: nvcr.io/nvidia/tritonserver:24.01-py3
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 15"]
        resources:
          limits:
            nvidia.com/gpu: "1"
            memory: "16Gi"
            cpu: "4"
          requests:
            nvidia.com/gpu: "1"
            memory: "8Gi"
            cpu: "2"
        ports:
        - containerPort: 8000
          name: http-inference
        - containerPort: 8002
          name: metrics
```

#### Langkah 4: Terapkan Kebijakan KEDA Autoscaling
Terapkan autoscaling berbasis queue latency:

```yaml
# Simpan di hands-on/m02/manifests/keda-autoscaler.yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: triton-queue-scaledobject
  namespace: ml-inference
spec:
  scaleTargetRef:
    name: triton-fraud-model
  minReplicaCount: 2
  maxReplicaCount: 8
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus-k8s.monitoring.svc:9090
      metricName: nv_inference_queue_duration_us
      threshold: '5000' # Trigger jika antrean rata-rata > 5ms
      query: avg(nv_inference_queue_duration_us{app="triton-fraud"})
```

---

### 13. Exercise

#### Level Easy
Konfigurasikan script bash untuk mengekstrak metrik Prometheus `container_gpu_utilization` dari node pool tertentu dan cetak hasilnya dalam format JSON dengan mapping unit bisnis berdasarkan namespace Kubernetes.

#### Level Medium
Tuliskan OPA Gatekeeper Constraint Template yang memvalidasi bahwa setiap Pod yang meminta resource `nvidia.com/gpu` memiliki toleransi dan affinity untuk spot instance, serta mewajibkan keberadaan label `finops.chargeback.account`.

#### Level Hard
Rancang arsitektur Python async reverse-proxy yang bertindak sebagai model sidecar. Proxy ini harus:
1. Menerima request eksternal.
2. Memeriksa token budget tenant dari Redis (Rate Limiting + Cost Quota enforcement).
3. Meneruskan request ke runtime lokal hanya jika cost quota bulan ini belum terlampaui.
4. Mengembalikan HTTP 429 dengan header `X-FinOps-Budget-Exceeded: true` jika kuota terlampaui.

---

### 14. Challenge

**Skenario Sistem:**
Anda diangkat sebagai Principal MLOps Engineer di perusahaan Ride-Hailing terkemuka. Sistem routing armada mereka bergantung pada ensemble 4 model deep learning yang dijalankan bersamaan (Graph Neural Networks dan Deep Reinforcement Learning) dengan SLA response time p99 maksimal **35ms**.

**Kondisi Tantangan:**
1. **Budget Cap:** Total anggaran operasional GPU tidak boleh melebihi $50.000/bulan (saat ini membengkak di angka $130.000/bulan).
2. **Kondisi Trafik:** Rasio beban kerja siang dan malam bervariasi sangat ekstrem (Rasio 15:1 antara peak rush hour vs jam 03.00 pagi).
3. **Infrastruktur:** Cluster berjalan di atas multi-cloud (AWS EKS & GCP GKE) karena regulasi kedaulatan data regional.
4. **Serangan Adversarial:** Terdeteksi upaya injection attack pada model weights di environment staging yang memodifikasi parameter keselamatan armada.

**Tugas Arsitektur:**
Rancang arsitektur deployment terperinci yang mencakup:
- Strategi orkestrasi model ensemble (Model pipelining vs Triton BLS / Ensemble engine).
- Solusi zero-trust artifact supply chain yang memvalidasi integritas model secara terdistribusi di multi-cloud.
- Arsitektur elastisitas FinOps agresif yang mengombinasikan Spot instance, model quantization (FP8/INT4), dan queue-based autoscaling lintas cloud provider secara harmonis tanpa melanggar batasan p99 35ms.

Dokumentasikan solusi Anda lengkap dengan blueprint diagram topologi, strategi mitigasi kegagalan spot multi-region, formula perhitungan unit economics biaya per-routing, dan skema zero-trust verification.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa alasan utama format serialisasi `.pkl` (Python Pickle) dilarang digunakan dalam arsitektur MLOps enterprise?
   - A. Kecepatan deserialisasi lebih lambat dibanding JSON murni.
   - B. Tidak mendukung tipe data matriks float16/bfloat16.
   - C. Memungkinkan *arbitrary code execution* saat proses deserialisasi dilakukan.
   - D. File hasil serialisasi pickle tidak dapat dikompresi.
   *(Jawaban: C)*

2. Metrik manakah di bawah ini yang paling tidak reliabel untuk digunakan sebagai trigger autoscaling pod inferensi model deep learning?
   - A. Request Queue Duration.
   - B. Host Node CPU Utilization.
   - C. vLLM Waiting Requests Count.
   - D. NVIDIA DCGM Tensor Core Activity.
   *(Jawaban: B)*

3. Sigstore Cosign pada pipeline deployment model ML enterprise berfungsi untuk:
   - A. Mengompres bobot model dari FP32 ke FP8.
   - B. Melakukan profiling performa latensi GPU.
   - C. Menandatangani dan memverifikasi integritas kriptografis artefak model secara digital.
   - D. Mengubah format ONNX menjadi TensorRT plan binary.
   *(Jawaban: C)*

4. Dalam konteks FinOps Kubernetes, istilah "Showback" merujuk pada:
   - A. Pemotongan anggaran divisi secara otomatis dari rekening bank.
   - B. Pelaporan transparansi biaya konsumsi komputasi ke unit bisnis tanpa penagihan riil secara akuntansi.
   - C. Penjualan kembali sisa kapasitas GPU yang tidak terpakai ke spot market.
   - D. Penghapusan pod secara paksa ketika budget bulanan habis.
   *(Jawaban: B)*

5. Waktu tunggu yang diberikan oleh AWS Node Termination Handler sebelum sebuah Spot Instance benar-benar dimatikan adalah:
   - A. 30 detik.
   - B. 2 menit (120 detik).
   - C. 15 menit.
   - D. Seketika tanpa peringatan (*0 detik*).
   *(Jawaban: B)*

---

#### Bagian 2: Intermediate (Pilihan Ganda)
6. Dynamic Batching pada Triton Inference Server diatur oleh dua parameter kunci: `max_queue_delay_microseconds` dan `preferred_batch_size`. Apa dampak teknis jika `max_queue_delay_microseconds` diatur terlalu besar (misal: 1 detik)?
   - A. GPU VRAM akan langsung mengalami Out-Of-Memory (OOM).
   - B. Latensi individu untuk request yang datang lebih awal akan membengkak, merusak target SLA latensi p99.
   - C. Triton server akan crash akibat thread deadlock.
   - D. Throughput komputasi GPU akan turun drastis ke level zero.
   *(Jawaban: B)*

7. Mengapa penempatan workload Tensor Parallelism ($TP > 1$) di Kubernetes memerlukan interkoneksi berkecepatan tinggi seperti NVLink dibandingkan PCIe standar?
   - A. Karena data training harus ditulis ke SSD NVMe secara simultan.
   - B. Operasi sinkronisasi tensor (`all-reduce`/`all-gather`) melintasi PCIe bus akan menjadi bottleneck latency komunikasi yang sangat tinggi.
   - C. Driver NVIDIA CUDA memblokir pembagian bobot model di luar bus NVLink.
   - D. Kubernetes Device Plugin tidak mendukung alokasi multi-GPU pada jalur PCIe.
   *(Jawaban: B)*

8. Bagaimana Kyverno atau OPA Gatekeeper mengamankan deployment model dari ancaman modifikasi supply chain liar?
   - A. Dengan memindai kode Python menggunakan linter SonarQube di dalam container.
   - B. Melalui intercepting deployment request di admission controller untuk memvalidasi cryptographic signature image/artefak terhadap root authority sebelum pod diizinkan berjalan.
   - C. Memblokir akses jaringan outbound internet dari GPU node.
   - D. Melakukan enkripsi real-time pada seluruh traffic API HTTP Triton.
   *(Jawaban: B)*

9. Pada arsitektur FinOps enterprise, mengapa alokasi biaya GPU idle harus dialokasikan (*allocated idle cost*) kepada tenant, bukan sekadar diabaikan?
   - A. Agar cloud provider memberikan potongan diskon tambahan.
   - B. Karena kapasitas idle GPU yang direservasi oleh suatu namespace tetap berbayar penuh ke cloud provider dan mencegah unit lain menggunakannya.
   - C. Untuk memenuhi persyaratan format laporan metrik Prometheus.
   - D. Karena GPU idle mengonsumsi daya listrik yang sama besarnya dengan GPU full load.
   *(Jawaban: B)*

10. Apa fungsi mekanisme `preStop` hook pada pod deployment model deep learning yang berjalan di atas spot node pool?
    - A. Memulai proses fine-tuning model otomatis sesaat sebelum node mati.
    - B. Mengunggah log lokal pod ke S3 secara asinkron.
    - C. Memberi sinyal unregister ke service load balancer, menolak request baru, dan menuntaskan request yang sedang diproses sebelum node ditarik provider.
    - D. Menghapus image dari Docker cache lokal node untuk menghemat disk.
    *(Jawaban: C)*

---

#### Bagian 3: Skenario Kasus Produksi

11. **Skenario Kasus A:**
    Cluster inferensi LLM Anda yang berjalan di atas 16x pod vLLM (masing-masing 8x A100 GPU) mengalami penurunan throughput drastis saat terjadi lonjakan trafik pengguna secara tiba-tiba. Setelah diperiksa via Prometheus, metrik `vllm:num_requests_waiting` melonjak ke angka 450, namun `container_gpu_utilization` menunjukkan angka rata-rata hanya 40%. Di sisi lain, KEDA tidak melakukan scale-up karena trigger autoscaler menggunakan metrik GPU Utilization.
    **Analisis & Evaluasi:** 
    - Identifikasi akar masalah pada arsitektur autoscaling dan runtime engine.
    - Apa tindakan remediasi mendesak dan konfigurasi autoscaler permanen yang harus diterapkan?

12. **Skenario Kasus B:**
    Sebuah tim audit keamanan mendeteksi bahwa artefak model fraud detection di cluster produksi memuat layer arbitrer tambahan yang tidak tercatat pada commit Git pipeline CI/CD resmi. Terungkap bahwa seorang engineer mengeksekusi hotfix darurat dengan mengunduh bobot langsung dari S3 bucket staging menggunakan script internal Pod dan menimpa direktori model lokal via `kubectl exec`.
    **Analisis & Evaluasi:**
    - Sebutkan 3 celah arsitektur enterprise security yang dilanggar dalam kasus ini.
    - Rancang rancangan kontrol preventif terstruktur (kombinasi RBAC, Admission Webhooks, dan Container Runtime Security) untuk mencegah insiden ini terulang.

13. **Skenario Kasus C:**
    Manajemen keuangan (FinOps) mendapati lonjakan biaya compute GPU bulanan sebesar $80.000 pada satu cluster pengujian. Setelah dilacak, terdapat 10 deployment pengujian inference batch berukuran besar yang dideploy oleh engineer yang sedang cuti. Pod-pod tersebut meminta alokasi GPU eksklusif (`limits: nvidia.com/gpu: 4`), namun proses inferensi telah selesai 2 minggu lalu dan server hanya berada dalam status idle menunggu request HTTP yang tidak pernah datang.
    **Analisis & Evaluasi:**
    - Kebijakan platform otomatis apa yang harus diimplementasikan pada level Kubernetes cluster untuk mendeteksi dan mengeliminasi "Zombie Inference Pods"?
    - Bagaimana mekanisme arsitektur "Scale-to-Zero" dapat diterapkan pada kasus inference batch/testing semacam ini?

---

### 16. Summary

Mengelola platform MLOps skala Enterprise menuntut transformasi mendasar dari eksperimentasi ad-hoc menuju disiplin rekayasa sistem yang kokoh:
1. **Scalability:** Penjadwalan beban inferensi GPU modern tidak dapat disamakan dengan web service konvensional. Autoscaling wajib berbasis *queue metrics* (KEDA) dan mempertimbangkan topologi interkoneksi hardware (NVLink/NUMA).
2. **Security:** Keamanan AI bukan hanya urusan dependensi library, melainkan perlindungan penuh terhadap model supply chain. Penerapan SafeTensors, penandatanganan kriptografis via Sigstore Cosign, dan verifikasi mutlak di Kubernetes admission webhook merupakan fondasi integritas zero-trust.
3. **FinOps:** Tanpa unit economics yang transparan, operasional model AI skala besar akan runtuh di bawah beban biaya akselerator komputasi. Integrasi spot instances dengan lifecycle draining yang mulus, digabungkan dengan metering real-time berbasis tenant (Kubecost/Prometheus), adalah prasyarat keberlanjutan platform enterprise modern.