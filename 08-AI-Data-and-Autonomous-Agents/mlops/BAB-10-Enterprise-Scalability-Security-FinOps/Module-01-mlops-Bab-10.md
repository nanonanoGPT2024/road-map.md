# Bab 10: Enterprise Scalability, Security, & FinOps
## Module 01: Multi-Tenant Scalability, Zero-Trust ML Security, dan FinOps Governance

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang Arsitektur Serving Multi-Tenant Skala Enterprise**: Menerapkan pola *Horizontal Pod Autoscaler* (HPA) dan *Kubernetes Event-driven Autoscaling* (KEDA) berbasis metrik beban inferensi non-linier (panjang antrean inferensi, konkurensi GPU, dan waktu tunggu KV-cache).
- **Mengonfigurasi Partisi Akselerator Hardware**: Mengimplementasikan strategi alokasi GPU tingkat lanjut menggunakan *Multi-Instance GPU* (MIG), *Time-Slicing*, dan *Multi-Process Service* (MPS) guna memaksimalkan saturasi komputasi *hardware*.
- **Mengintegrasikan Prinsip Zero-Trust pada Siklus Hidup ML**: Mengamankan saluran komunikasi antar-layanan melalui *mutual TLS* (mTLS) berbasis SPIFFE/SPIRE, enkripsi data *envelope* dengan KMS, dan verifikasi integritas model kriptografis menggunakan Sigstore/Cosign.
- **Membangun Model FinOps Presisi Tinggi untuk AI/ML**: Menghitung dan mengalokasikan *Unit Economics of Inference* (biaya per 1.000 token / transaksi inferensi) secara riil menggunakan agregasi metrik Prometheus dan atribusi biaya tingkat *tenant*.
- **Mengimplementasikan Failover dan Graceful Degradation Engine**: Mengembangkan *Inference Gateway* yang mampu menangani kondisi *GPU Out-of-Memory* (OOM), kegagalan instans *Spot/Preemptible*, serta menerapkan *fallback routing* ke model terkuantisasi secara transparan.

---

### 2. Concept Overview

Skalabilitas, keamanan, dan efisiensi biaya pada level enterprise bukanlah fitur yang dapat ditempelkan di akhir siklus pengembangan (*afterthought*), melainkan fondasi struktural sistem inferensi dan pelatihan ML produksi.

```
+-----------------------------------------------------------------------------------+
|                        ENTERPRISE MLOps CONTROL PLANE                             |
+-----------------------------------------------------------------------------------+
|  [Security / Zero-Trust]         [Scalability Engine]         [FinOps Engine]     |
|  - SPIFFE/SPIRE Identity         - KEDA Custom Metrics        - Node Sizing Engine|
|  - KMS Envelope Encryption       - Dynamic Batching           - GPU Idle Reaper   |
|  - Cosign Artifact Signing       - MIG / MPS Partitioning     - Unit Cost Tracker |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                        DATA PLANE / INFERENCE RUNTIME                             |
|  [API Gateway] ──(mTLS)──> [Triton / vLLM Pods] ──(Direct Engine)──> [vGPU/MIG]   |
+-----------------------------------------------------------------------------------+
```

#### Mental Model: The MLOps Trilemma
Di lingkungan produksi skala besar, arsitektur MLOps harus menyeimbangkan tiga pilar yang saling bertolak belakang:
1. **Performance/Scale**: Latensi minimum ($P_{99} < 50\text{ms}$), *throughput* tinggi ($>10.000\text{ RPS}$), dan ketersediaan tinggi ($99.99\%$).
2. **Security & Governance**: Isolasi data antar-penyewa (*multi-tenancy*), verifikasi integritas bobot model (*cryptographic provenance*), dan jejak audit yang sesuai dengan regulasi (SOC2, HIPAA, GDPR).
3. **FinOps & Cost-Efficiency**: Utilisasi GPU mendekati $\sim 85\%$, eliminasi *idle cost*, pemanfaatan instans *spot*, dan visibilitas biaya per unit bisnis.

Optimalisasi berlebihan pada performa tanpa FinOps memicu pembengkakan biaya infrastruktur hingga ratusan ribu dolar per bulan. Sebaliknya, pembatasan biaya yang agresif tanpa mekanisme *failover* yang tepat akan merusak *Service Level Agreement* (SLA) saat terjadi lonjakan beban (*traffic spike*).

---

### 3. Why It Matters

Di tingkat enterprise, kegagalan dalam mengelola ketiga pilar tersebut menimbulkan dampak katastropik:

- **Runaway Cloud Costs**: Berbeda dengan CPU yang dapat di-*oversubscribe* dengan aman, GPU yang dialokasikan namun tidak aktif (*idle*) tetap mengonsumsi biaya penuh ($3.00 - $4.50/jam per H100/A100). Tanpa *Scale-to-Zero* dan *dynamic bin-packing*, tagihan komputasi bulanan melonjak tanpa korelasi langsung terhadap nilai bisnis.
- **Model Poisoning & Supply Chain Attacks**: Bobot model (misalnya file `.bin`, `.pt`, atau `.safetensors`) dapat disusupi kode berbahaya via deserialisasi arbitrer (*pickle exploit*) atau dimanipulasi di artefak *registry* jika tidak memiliki penandatanganan kriptografis (*signature verification*).
- **SLA Breach & Cascading Failures**: Penggunaan metrik autoscaling tradisional (CPU/Memory usage) tidak efektif untuk inferensi ML. Model LLM atau Computer Vision dapat mencapai batas latensi komputasi sebelum batas CPU/RAM tercapai, mengakibatkan antrean permintaan menumpuk (*thundering herd*) dan memicu *OOM kills* masal.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut merepresentasikan alur inferensi end-to-end dengan implementasi Zero-Trust, KEDA autoscaling, partisi akselerator GPU, dan telemetri FinOps:

```
[ Ingress Client ]
        │ (HTTPS / TLS 1.3)
        ▼
+─────────────────────────────────────────────────────────────────────────────+
| Enterprise API Gateway (Envoy / Istio Service Mesh)                         |
|  - Rate Limiting (Token Bucket per Tenant ID)                               |
|  - SPIRE mTLS Workload Attestation Injector                                 |
|  - Open Policy Agent (OPA) PEP (Policy Enforcement Point)                   |
+─────────────────────────────────────────────────────────────────────────────+
        │ (Internal mTLS SPIFFE Identity: spiffe://cluster.local/ns/ml/sa/gateway)
        ▼
+─────────────────────────────────────────────────────────────────────────────+
| Dynamic Inference Router & Cost Allocator (FastAPI / Go Proxy)              |
|  - Prometheus Counter: Token / Request Count per Tenant                     |
|  - Fallback Orchestrator (Primary GPU -> Degraded Quantized Engine)         |
+─────────────────────────────────────────────────────────────────────────────+
        │                                         ▲
        │ Routing Decision                        │ Pull Metrics
        ▼                                         │
+─────────────────────────────────────────+  +────────────────────────────────+
| GPU Inference Pool (Primary Engine)     |  | Telemetry & Autoscaling Plane  |
|  - Node: Standard_ND96amsr_A100_v4      |  |  - Prometheus / OpenCost       |
|  - Slicing: NVIDIA MIG (1g.10gb slices) |  |  - KEDA Custom Controller      |
|  - Container: Triton / vLLM             |  |    (Queue Depth, GPU Duty Cycle|
|  - Artifacts: KMS Decrypted Safetensors |  |     KV-Cache Saturation %)     |
+─────────────────────────────────────────+  +────────────────────────────────+
        │                                         │
        │ Failover / High-Load Spikes             │ Triggers HPA Scale-Out
        ▼                                         ▼
+─────────────────────────────────────────+  +────────────────────────────────+
| Secondary Fallback Pool                 |  | Spot Node Auto-Provisioner     |
|  - Node: Spot CPU / L4 (Quantized INT8) |  | (Karpenter / Cluster Autoscaler|
+─────────────────────────────────────────+  +────────────────────────────────+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Autoscaling Lanjutan: KEDA vs HPA Tradisional
Autoscaling berbasis CPU/RAM tidak memadai untuk inferensi ML karena latensi dipengaruhi oleh *tensor operation queue* pada GPU. Solusi enterprise menggunakan metrik spesifik akselerator melalui Prometheus:

$$\text{Desired Replicas} = \left\lceil \text{Current Replicas} \times \left( \frac{\text{Current Metric Value}}{\text{Target Metric Value}} \right) \right\rceil$$

Untuk model LLM/Autoregressive, metrik yang digunakan adalah:
1. `vllm:num_requests_waiting`: Jumlah antrean *generation requests*. Jika $> 0$ selama lebih dari ambang batas toleransi latensi ($T_{\text{wait}} > 200\text{ms}$), instans tambahan harus dialokasikan.
2. `vllm:gpu_cache_usage_factor`: Rasio penggunaan memori KV-cache. Saturasi $> 85\%$ menandakan model akan mulai melakukan *preemption* pada permintaan baru.

#### B. GPU Virtualization: MIG vs MPS vs Time-Slicing
Membiarkan satu pod inferensi menguasai keseluruhan A100 (80GB) untuk model berukuran kecil/sedang menghasilkan inefisiensi biaya (*under-utilization*).

| Parameter | NVIDIA Multi-Instance GPU (MIG) | Multi-Process Service (MPS) | Time-Slicing |
| :--- | :--- | :--- | :--- |
| **Isolasi Memori** | Hardware-level (Mutlak, aman antar-*tenant*) | Software-level (Proteksi memori terbatas) | Tidak ada isolasi memori fisik |
| **Fault Isolation** | Error satu pod tidak mempengaruhi pod lain | Error satu pod dapat menyebabkan crash engine MPS | Tidak ada isolasi crash |
| **QoS Predictability**| Sangat tinggi (Jalur memori & *compute engine* independen)| Tinggi (Multiplexing dinamis) | Rendah (Konkurensi bergantung latensi OS) |
| **Kasus Penggunaan** | Multi-Tenancy Enterprise, Regulasi Ketat | Workload batch homogen, *single-tenant* | Development, testing non-produksi |

#### C. Zero-Trust Architecture: Model Provenance & SPIRE
Prinsip Zero-Trust *"never trust, always verify"* diwujudkan melalui:
1. **SPIFFE/SPIRE**: Menggantikan *API keys* atau *token Kubernetes static* dengan sertifikat X.509 berumur pendek (*short-lived*) yang diperbarui otomatis setiap jam, diikatkan pada identitas Pod (namespace, service account, node signature).
2. **Cosign/Sigstore**: Setiap bobot model ditandatangani saat lolos *Continuous Integration / Evaluation pipeline*. Pod inferensi memverifikasi *cryptographic signature* ini menggunakan *public key* yang terpasang sebelum memuat file ke dalam VRAM GPU:
   $$\text{Verify}(M_{\text{digest}}, \text{Signature}, PK_{\text{registry}}) \to \{\text{True}, \text{False}\}$$
3. **KMS Envelope Encryption**: Bobot model dienkripsi di Object Storage (S3/GCS) menggunakan *Data Encryption Key* (DEK). DEK ini dilindungi oleh *Key Encryption Key* (KEK) pada Hardware Security Module (HSM) Cloud. Pod hanya meminta dekripsi DEK saat *cold start*.

#### D. FinOps: Kalkulasi Unit Economics of Inference
Perhitungan biaya inferensi berbasis alokasi sumber daya nyata dihitung sebagai:

$$\text{Cost}_{\text{inference}} = \left( \frac{\text{Duration}_{\text{sec}}}{3600} \times \text{Cost}_{\text{node\_hr}} \times \frac{\text{Allocated GPU/MIG}}{\text{Total Node GPU}} \right) + \text{Cost}_{\text{network\_egress}}$$

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi **Enterprise Inference Routing, Policy Enforcement, & FinOps Telemetry Gateway** menggunakan Python (FastAPI), Pydantic V2, Prometheus client, dan mekanisme *circuit breaker/fallback*.

```python
"""
Enterprise MLOps Inference Gateway & FinOps Allocator
Author: Principal MLOps Architect
Scope: Production-grade multi-tenant routing, cryptographic attestation, 
       FinOps telemetry, and graceful fallback.
"""

import asyncio
import logging
import os
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from fastapi import FastAPI, Request, Response, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import httpx

# --- KONFIGURASI LOGGING TERSTRUKTUR ---
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","message":"%(message)s"}'
)
logger = logging.getLogger("enterprise-gateway")

# --- PROMETHEUS FINOPS & SYSTEM TELEMETRY ---
INFERENCE_REQUEST_COUNT = Counter(
    "mlops_inference_requests_total",
    "Total model inference requests processed",
    ["tenant_id", "model_id", "status", "execution_engine"]
)
INFERENCE_LATENCY_SECONDS = Histogram(
    "mlops_inference_duration_seconds",
    "Latency of inference execution end-to-end",
    ["tenant_id", "model_id", "execution_engine"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)
INFERENCE_TOKEN_FINOPS_COUNTER = Counter(
    "mlops_finops_consumed_tokens_total",
    "Cumulative token consumption for chargeback calculations",
    ["tenant_id", "model_id"]
)
ESTIMATED_INFERENCE_COST_USD = Counter(
    "mlops_finops_cost_usd_total",
    "Calculated monetary cost of consumed compute infrastructure",
    ["tenant_id", "model_id", "tier"]
)

# --- MODELS & SCHEMAS ---
class InferenceRequestPayload(BaseModel):
    model_id: str = Field(..., description="ID model yang terdaftar pada registry")
    prompt: str = Field(..., min_length=1, max_length=8192, description="Payload inferensi")
    max_tokens: int = Field(default=128, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

class InferenceResponsePayload(BaseModel):
    model_id: str
    generated_text: str
    tokens_consumed: int
    execution_engine: str
    latency_ms: float
    cost_usd: float

@dataclass(frozen=True)
class HardwareTierRates:
    # Biaya per detik per instans (Estimasi standar AWS/GCP 2024)
    A100_MIG_1G_PER_SEC: float = 0.00015   # ~$0.54/jam
    SPOT_CPU_FALLBACK_PER_SEC: float = 0.00002 # ~$0.072/jam

# --- REPOSITORI ENDPOINT MODEL (SERVICE DISCOVERY) ---
PRIMARY_GPU_CLUSTER_URL = os.getenv("PRIMARY_GPU_URL", "http://triton-mig.serving.svc.cluster.local:8000")
FALLBACK_CPU_CLUSTER_URL = os.getenv("FALLBACK_CPU_URL", "http://quantized-fallback.serving.svc.cluster.local:8000")

# --- KEAMANAN: ZERO-TRUST WORKLOAD AUTHENTICATION ---
auth_scheme = HTTPBearer()

class TenantContext:
    def __init__(self, tenant_id: str, tier: str):
        self.tenant_id = tenant_id
        self.tier = tier

async def verify_zero_trust_token(credentials: HTTPAuthorizationCredentials = Depends(auth_scheme)) -> TenantContext:
    """
    Simulasi verifikasi SPIFFE/OIDC JWT token pada Service Mesh Zero-Trust.
    Memastikan identitas tenant valid dan memiliki hak akses inferensi.
    """
    token = credentials.credentials
    # Di lingkungan nyata: verifikasi cryptographic signature menggunakan public keys dari SPIRE/Vault JWKS
    if not token or token == "invalid-untrusted-token":
        logger.error("Akses ditolak: Kegagalan otentikasi identitas mTLS/Bearer token.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Zero-Trust validation failed: Invalid workload token."
        )
    
    # Dummy claims extraction
    if "premium" in token:
        return TenantContext(tenant_id="enterprise-org-01", tier="premium")
    return TenantContext(tenant_id="general-org-02", tier="standard")

# --- INITIALIZE APP ---
app = FastAPI(
    title="MLOps Enterprise Gateway",
    description="High-Throughput Zero-Trust Inference Routing with Automated FinOps Telemetry",
    version="1.0.0"
)

# --- REUSABLE HTTP CLIENT ENGINE ---
http_client: Optional[httpx.AsyncClient] = None

@app.on_event("startup")
async def startup_event():
    global http_client
    # Koneksi HTTP Persistent Connection Pooling untuk throughput optimal
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=2.0, read=15.0, write=5.0, pool=30.0),
        limits=httpx.Limits(max_keepalive_connections=100, max_connections=500)
    )

@app.on_event("shutdown")
async def shutdown_event():
    if http_client:
        await http_client.aclose()

# --- GATEWAY ENGINE CONTROLLER ---
class InferenceOrchestrator:
    @staticmethod
    async def route_inference(payload: InferenceRequestPayload, tenant: TenantContext) -> Dict[str, Any]:
        assert http_client is not None, "HTTP Client belum diinisialisasi."
        start_time = time.perf_counter()
        execution_engine = "A100_MIG_PRIMARY"
        
        # 1. Mencoba mengeksekusi inferensi pada Primary GPU Cluster
        try:
            # Contoh payload mock downstream
            downstream_req = {
                "inputs": [{"name": "prompt", "shape": [1], "datatype": "BYTES", "data": [payload.prompt]}],
                "parameters": {"max_tokens": payload.max_tokens, "temperature": payload.temperature}
            }
            
            # Simulasi pemanggilan downstream Triton/vLLM
            response = await http_client.post(
                f"{PRIMARY_GPU_CLUSTER_URL}/v1/models/{payload.model_id}/generate",
                json=downstream_req,
                headers={"X-Spiffe-Tenant": tenant.tenant_id}
            )
            response.raise_for_status()
            inference_data = response.json()
            raw_text = inference_data.get("text", "Processed via Primary Engine")
            tokens_generated = inference_data.get("tokens_count", payload.max_tokens)
            
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            # 2. Pola Failure Handling: Circuit breaking / Graceful degradation ke fallback instance
            logger.warning(
                f"Kegagalan klaster GPU utama ({exc}). Mengaktifkan fallback engine untuk model: {payload.model_id}"
            )
            execution_engine = "CPU_SPOT_FALLBACK"
            
            try:
                fallback_res = await http_client.post(
                    f"{FALLBACK_CPU_CLUSTER_URL}/v1/models/{payload.model_id}-quantized/generate",
                    json={"prompt": payload.prompt, "max_tokens": payload.max_tokens},
                    headers={"X-Fallback-Mode": "true"}
                )
                fallback_res.raise_for_status()
                inference_data = fallback_res.json()
                raw_text = inference_data.get("text", "Fallback degraded response")
                tokens_generated = inference_data.get("tokens_count", int(payload.max_tokens * 0.75))
            except Exception as critical_exc:
                logger.critical(f"Total cluster failure: Seluruh engine inferensi gagal. Error: {critical_exc}")
                INFERENCE_REQUEST_COUNT.labels(
                    tenant_id=tenant.tenant_id, model_id=payload.model_id, status="failed", execution_engine="NONE"
                ).inc()
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Inference cluster compute is currently unavailable."
                )

        duration = time.perf_counter() - start_time
        
        # 3. FinOps Cost Engine: Kalkulasi Biaya Komputasi
        rate_per_sec = (
            HardwareTierRates.A100_MIG_1G_PER_SEC 
            if execution_engine == "A100_MIG_PRIMARY" 
            else HardwareTierRates.SPOT_CPU_FALLBACK_PER_SEC
        )
        calculated_cost = duration * rate_per_sec

        # 4. Instrumentasi Metrik untuk Observabilitas dan Audit FinOps
        INFERENCE_REQUEST_COUNT.labels(
            tenant_id=tenant.tenant_id, model_id=payload.model_id, status="success", execution_engine=execution_engine
        ).inc()
        INFERENCE_LATENCY_SECONDS.labels(
            tenant_id=tenant.tenant_id, model_id=payload.model_id, execution_engine=execution_engine
        ).observe(duration)
        INFERENCE_TOKEN_FINOPS_COUNTER.labels(
            tenant_id=tenant.tenant_id, model_id=payload.model_id
        ).inc(tokens_generated)
        ESTIMATED_INFERENCE_COST_USD.labels(
            tenant_id=tenant.tenant_id, model_id=payload.model_id, tier=tenant.tier
        ).inc(calculated_cost)

        return {
            "model_id": payload.model_id,
            "generated_text": raw_text,
            "tokens_consumed": tokens_generated,
            "execution_engine": execution_engine,
            "latency_ms": round(duration * 1000, 2),
            "cost_usd": round(calculated_cost, 7)
        }

# --- ROUTES ---
@app.post("/v1/predict", response_model=InferenceResponsePayload, status_code=status.HTTP_200_OK)
async def predict_endpoint(
    payload: InferenceRequestPayload,
    tenant: TenantContext = Depends(verify_zero_trust_token)
):
    """
    Endpoint inferensi terlindungi dengan Zero-Trust Context Injection
    dan pelacakan FinOps granular secara real-time.
    """
    result = await InferenceOrchestrator.route_inference(payload, tenant)
    return InferenceResponsePayload(**result)

@app.get("/metrics", response_class=Response)
def metrics_endpoint():
    """
    Scrape endpoint untuk Prometheus Server guna mengumpulkan metrik performa dan FinOps.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/healthz", status_code=status.HTTP_200_OK)
def health_check():
    return {"status": "healthy", "service": "enterprise-inference-gateway"}
```

---

### 7. Edge Cases & Failure Modes

Pada implementasi skala enterprise, kegagalan sistem inferensi sering kali tidak bersifat biner (nyala/mati), melainkan degradasi bertahap (*cascading failure*):

1. **GPU Out-Of-Memory (OOM) via Unbounded Context Window**:
   - *Mode Kegagalan*: User mengirimkan *prompt* dengan ukuran melampaui batas VRAM yang tersisa, memicu pemutusan proses container oleh kernel Linux (`cudaErrorMemoryAllocation`).
   - *Mitigasi*: Validasi panjang token di Gateway (*pre-flight validation*), isolasi VRAM dinamis dengan *PagedAttention* (seperti pada vLLM), dan membatasi ukuran alokasi per *batch* secara tegas.

2. **Thundering Herd Saat Scale-to-Zero Wake-Up**:
   - *Mode Kegagalan*: Trafik naik drastis dari 0 ke ribuan request saat Pod berada pada status 0 replika. Pod membutuhkan waktu 45-90 detik untuk memuat model 14B/70B dari storage ke VRAM. Request mengalami *timeout* massal ($504\text{ Gateway Timeout}$).
   - *Mitigasi*: Menetapkan `minReplicas: 1` pada deployment produksi, menggunakan *warm pool* instans, atau mengonfigurasi *lazy loading* menggunakan teknik memori virtual terdistribusi (misalnya Juicesync atau model caching via local NVMe daemon).

3. **Silent Drift vs Hardware Degradation**:
   - *Mode Kegagalan*: Penurunan frekuensi clock GPU (*thermal throttling*) atau kegagalan interkoneksi PCIe/NVLink menyebabkan latensi inferensi meningkat secara acak tanpa adanya error aplikasi yang jelas.
   - *Mitigasi*: Pemasangan *DCGM (Data Center GPU Manager) Exporter* untuk memonitor metrik *GPU temperature*, *throttling flags*, dan *XID errors*. Mengisolasi dan mengeluarkan node secara otomatis (*cordon & drain*) jika terdeteksi error hardware.

4. **KMS Quota Exhaustion**:
   - *Mode Kegagalan*: Ratusan pod autoscaling meminta dekripsi DEK ke AWS/GCP KMS secara simultan saat *traffic surge*, memicu rate-limit HTTP 429 pada cloud provider.
   - *Mitigasi*: Gunakan *local cache* terenkripsi untuk kunci dekripsi di tingkat Node (memanfaatkan Kubernetes Secrets yang di-*mount* via `tmpfs`) dengan waktu retensi yang terkontrol (*TTL*).

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Keputusan | Opsi Terpilih (KEDA + Triton/vLLM + MIG) | Alternatif Solusi (AWS SageMaker Endpoints) | Justifikasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Kontrol Akselerator** | Partisi granular via NVIDIA MIG (Slicing 1 GPU menjadi hingga 7 instance). | Model-to-instance mapping bawaan (1 Pod = 1 GPU penuh). | Penghematan biaya komputasi hingga 65% untuk beban kerja inferensi skala kecil/menengah (*hybrid models*). |
| **Vendor Lock-in** | Mandiri / Cloud-Agnostic (Dapat dijalankan di GCP, AWS, Azure, atau On-Premises bare-metal). | Terikat sepenuhnya pada ekosistem proprietary AWS (Boto3, SageMaker SDK). | Memberikan fleksibilitas negosiasi harga komputasi GPU dan kedaulatan data (*data sovereignty*). |
| **Kompleksitas Operasional** | **Tinggi**: Membutuhkan tim MLOps internal untuk konfigurasi Kubernetes, GPU Operators, dan Service Mesh. | **Rendah**: Manajemen infrastruktur ditangani penuh oleh cloud provider (*fully managed*). | Skala enterprise dengan utilisasi komputasi tinggi mendapatkan ROI positif dari pengurangan margin markup biaya cloud provider. |
| **Biaya Jangka Panjang** | Lebih efisien pada skala volume tinggi ($> 5\text{M}$ transaksi/hari). | Mahal pada volume tinggi karena overhead biaya manajemen platform per jam. | Model biaya mandiri berbasis FinOps memungkinkan alokasi biaya presisi per divisi bisnis. |

---

### 9. Best Practices & Standar Industri

1. **Atribusi FinOps Berbasis Labeling Ketat (Mandatory Tagging Policy)**:
   Setiap workload inferensi wajib menyertakan metadata label berikut pada spesifikasi Pod Kubernetes:
   ```yaml
   metadata:
     labels:
       finops.cost.center: "analytics-eng-402"
       finops.owner: "nlp-core-team"
       finops.environment: "production"
       finops.model.architecture: "llama-3-8b-instruct"
   ```
2. **Kuantisasi Adaptif untuk Fallback**:
   Sediakan versi terkuantisasi (AWQ/GPTQ 4-bit atau FP8) dari setiap model di instans CPU/GPU murah. Jika instans utama GPU penuh, alihkan trafik non-kritis ke versi terkuantisasi ini demi mempertahankan uptime tanpa melanggar batas alokasi biaya (*Graceful SLA degradation*).
3. **Pemberian Identitas Workload Menggunakan SPIRE**:
   Jangan pernah menggunakan *static API keys* di dalam pod inferensi. Manfaatkan sertifikat SPIFFE X.509 berumur pendek untuk komunikasi internal antar-layanan (*zero-trust microsegmentation*).
4. **Validasi Bobot Model Secara Kriptografis Sebelum Loading**:
   Gunakan admission controller (misalnya Kyverno atau OPA Gatekeeper) untuk memastikan hanya file model yang telah ditandatangani oleh *Cosign pipeline* resmi perusahaan yang diizinkan untuk dimuat ke dalam klaster inferensi.

---

### 10. Hands-on Lab Exercise: KEDA ScaledObject dengan Mock Custom Metrics & FinOps Tracking

#### Skenario Lab
Anda bertugas merancang autoscaling otomatis untuk model LLM/Embedding menggunakan KEDA. Klaster harus melakukan scale-up pod inferensi ketika rata-rata antrean permintaan (*waiting requests*) pada server inferensi $\ge 5$, dan melakukan *scale-to-zero* saat tidak ada aktivitas selama 5 menit.

#### Langkah 1: Terapkan KEDA ScaledObject Konfigurasi

Simpan manifes berikut sebagai `keda-inference-scaler.yaml`:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: enterprise-llm-scaler
  namespace: ml-serving
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vllm-inference-worker
  minReplicaCount: 0
  maxReplicaCount: 8
  cooldownPeriod: 300 # Menunggu 5 menit sebelum scale-to-zero (mencegah flapping)
  pollingInterval: 15  # Evaluasi metrik setiap 15 detik
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleUp:
          stabilizationWindowSeconds: 0
          policies:
            - type: Percent
              value: 100 # Izinkan penggandaan replika secara cepat saat lonjakan trafik
              periodSeconds: 15
        scaleDown:
          stabilizationWindowSeconds: 300
          policies:
            - type: Percent
              value: 25 # Scale-down bertahap untuk menjaga latensi
              periodSeconds: 60
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-k8s.monitoring.svc.cluster.local:9090
        metricName: vllm_num_requests_waiting
        query: sum(vllm:num_requests_waiting{namespace="ml-serving", model="meta-llama/Llama-3-8B"})
        threshold: '5' # Trigger scale-out jika antrean mencapai 5
```

#### Langkah 2: Menjalankan Stress Test dan Validasi FinOps

1. **Jalankan Deployment Mock Worker & Gateway**:
   ```bash
   kubectl apply -f keda-inference-scaler.yaml
   ```

2. **Simulasikan Lonjakan Trafik Inferensi**:
   Gunakan tool benchmarking seperti `hey` atau `wrk` untuk mengirimkan 50 request konkuren secara serentak ke API Gateway:
   ```bash
   hey -n 1000 -c 50 -m POST \
     -H "Authorization: Bearer valid-token-premium" \
     -H "Content-Type: application/json" \
     -d '{"model_id":"meta-llama/Llama-3-8B","prompt":"Simulasikan arsitektur multi-tenant MLOps.","max_tokens":256}' \
     http://<EXTERNAL_GATEWAY_IP>/v1/predict
   ```

3. **Verifikasi Status Autoscaling**:
   Amati respon KEDA dan HPA dalam memicu alokasi pod baru secara real-time:
   ```bash
   kubectl get hpa -n ml-serving -w
   kubectl get pods -n ml-serving -l app=vllm-inference-worker
   ```

4. **Audit Metrik FinOps pada Prometheus**:
   Akses antarmuka web Prometheus atau eksekusi query PromQL berikut untuk menghitung total akumulasi biaya komputasi per *tenant*:
   ```promql
   sum by (tenant_id) (mlops_finops_cost_usd_total)
   ```
   Pastikan tagihan tercatat secara akurat sesuai durasi eksekusi dan tier komputasi yang digunakan. Output ini membuktikan bahwa arsitektur berhasil mengintegrasikan skalabilitas dinamis, isolasi aman, dan akuntabilitas biaya operasional tingkat enterprise.