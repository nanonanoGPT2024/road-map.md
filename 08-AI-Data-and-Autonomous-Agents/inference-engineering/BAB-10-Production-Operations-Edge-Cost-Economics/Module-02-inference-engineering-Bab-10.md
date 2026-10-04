# BAB 10: Production Operations, Edge, & Cost Economics
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Merancang dan Mengimplementasikan Arsitektur Inferensi Skala Enterprise:** Membangun *data plane* dan *control plane* inferensi LLM yang tangguh (*fault-tolerant*), mendukung *high availability* (HA), *zero-downtime deployment*, dan *disaggregated prefill-decode serving*.
2. **Mengonfigurasi Autoscaling Berbasis Metrik LLM (SLA-Aware):** Mengintegrasikan KEDA (*Kubernetes Event-driven Autoscaling*) dengan metrik spesifik *inference engine* (TTFT, ITL, persentase utilisasi KV-cache, *queue depth*) alih-alih metrik konvensional seperti CPU/Memory utilization.
3. **Mengoptimalkan Routing dan Cache Affinity:** Mengembangkan *intelligent model router* yang memanfaatkan *Radix Tree prefix cache-hit tracking* untuk mengarahkan request ke worker GPU yang sudah memiliki residu KV-cache relevan.
4. **Mengeksekusi Cost Economics & Multi-Tenancy:** Menerapkan strategi *dynamic LoRA multiplexing*, *bin-packing* workload pada GPU heterogen (misalnya NVIDIA H100, L40S, A10G), serta integrasi *spot instance interruption handling*.
5. **Menerapkan Telemetri Observabilitas Komprehensif:** Menginstrumentasi OpenTelemetry (OTel) dan Prometheus untuk mengekstraksi metrik performa granular (*prefill latency*, *decode token throughput*, *KV cache fragmentation*) ke *production dashboard*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* **Inference Engine Internals:** Mekanisme kerja *PagedAttention*, *Continuous Batching*, pemisahan fase *Prefill* (compute-bound) dan *Decode* (memory-bandwidth bound) pada vLLM atau TensorRT-LLM.
* **Container Orchestration & Linux Kernel:** Arsitektur Kubernetes tingkat lanjut (CRD, Operator pattern, Ingress Controller), interaksi driver NVIDIA Container Toolkit, Linux cgroups v2, dan *shared memory* (`/dev/shm`) POSIX.
* **Networking & Protocols:** HTTP/2, HTTP/3, gRPC streaming, *Server-Sent Events* (SSE), serta arsitektur reverse proxy (Envoy, NGINX).
* **Distributed Systems Fundamentals:** Mekanisme konsistensi, *health checking*, mitigasi *thundering herd*, dan algoritma *consistent hashing*.

---

### 3. Concept & Internal Architecture (Mendalam)

Operasionalisasi inferensi skala produksi membutuhkan pergeseran paradigma dari *stateless web service* ke sistem *semi-stateful, accelerator-bound, hardware-aware distributed architecture*.

```
                                 [ Client Applications ]
                                            │
                                            ▼
                           [ Global Edge Ingress / Cloudflare ]
                                            │ (Anycast Routing / TLS Term.)
                                            ▼
                       [ Enterprise API Gateway / Envoy Ingress ]
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
          [ Semantic & Exact Cache ]                      [ Smart Model Router ]
          (Redis / Milvus Vector DB)                    (Radix Prefix Affinity)
                     │ (Cache Miss)                                │
                     └──────────────────────┬──────────────────────┘
                                            ▼
               [ Distributed Prefill-Decode Cluster Orchestration ]
       ┌────────────────────────────────────┴────────────────────────────────────┐
       ▼                                                                         ▼
[ Prefill Worker Pool ]                                                 [ Decode Worker Pool ]
(NVIDIA H100 / Compute-Bound)                                           (NVIDIA L40S / Bandwidth-Bound)
- Tensor Parallelism (TP=4)                                             - Pipeline/Tensor Parallelism
- Chunked Prefill Execution                                             - Continuous Batching / PagedAttention
- Context Caching Engine                                                - Speculative Decoding Engine
       │                                                                         ▲
       └────────────── Remote KV-Cache Transfer (RDMA / RoCE v2) ────────────────┘
                                            │
                                            ▼
                               [ Metrics & Observability ]
                           (Prometheus + KEDA + OpenTelemetry)
```

#### A. Disaggregated Prefill-Decode Architecture
Secara historis, fase *prefill* (memproses input prompt) dan fase *decode* (menghasilkan token berikutnya satu per satu) dijalankan pada GPU yang sama. Hal ini memicu dua bottleneck struktural:
1. **Interference / Bubbles:** Fase prefill yang rakus komputasi menghalangi (*blocks*) fase decode yang sedang berjalan, memicu spike tajam pada *Inter-Token Latency* (ITL).
2. **Resource Mismatch:** Prefill dibatasi oleh kapasitas TFLOPS komputasi (*compute-bound*), sementara decode dibatasi oleh *memory bandwidth* (VRAM HBM bandwidth).

Arsitektur produksi modern memisahkan kluster worker menjadi:
* **Prefill Nodes:** Ditenagai akselerator komputasi masif (misal: NVIDIA H100 SXM5) yang memproses ribuan prompt token dalam hitungan milidetik, lalu mengalirkan *intermediate KV-cache* melalui jaringan RDMA (*Remote Direct Memory Access*) berkecepatan tinggi (Infiniband / RoCE v2).
* **Decode Nodes:** Ditenagai GPU yang optimal dalam rasio bandwidth-ke-biaya (misal: L40S, A100 80GB PCIe) yang bertugas mengeksekusi *autoregressive generation* secara kontinu tanpa terdistraksi lonjakan beban prompt baru.

#### B. Radix Tree-Aware Smart Routing
Inference engine modern seperti vLLM mengimplementasikan *automatic prefix caching* menggunakan struktur data *Radix Tree*. Jika dua request berbagi system prompt atau context document yang sama (misal: skema RAG enterprise), engine tidak perlu mengomputasi ulang KV-cache untuk token-token tersebut.

Namun, dalam kluster multi-replica horizontal di balik standard Load Balancer (Round Robin atau Least Connections), request yang identik sering kali mendarat di pod yang berbeda. Akibatnya, efisiensi prefix caching anjlok hingga 0%. 

**Smart Model Router** mempertahankan replika *Radix Tree metadata* di memori aplikasinya sendiri. Router memetakan hash token dari prompt ke pod tertentu yang telah meng-cache prefix tersebut (*cache affinity routing*), menurunkan *Time to First Token* (TTFT) dari rata-rata 1200ms menjadi kurang dari 40ms untuk prompt berulang.

#### C. SLA-Aware Dynamic Autoscaling
Penerapan Horizontal Pod Autoscaler (HPA) konvensional dengan ambang batas CPU atau GPU Utilization (via NVML) dipastikan **gagal total** pada inferensi LLM:
* GPU Utilization hampir selalu terbaca 99-100% ketika model sedang memproses bahkan hanya satu request dalam mode *continuous batching*, sehingga memicu *over-provisioning* yang boros biaya.
* Sebaliknya, jika antrean request menumpuk di memori host sementara GPU sedang sibuk memproses *batch*, metrik memori GPU tidak bertambah karena alokasi VRAM sudah direservasi sejak awal oleh *PagedAttention memory pool*.

Autoscaling produksi enterprise **wajib digerakkan oleh KEDA** dengan metrik kustom:
$$\text{Scaling Metric} = \alpha \cdot \frac{\text{Queue Length}}{\text{Avg Token Rate}} + \beta \cdot \text{GPU Cache Usage Factor} + \gamma \cdot \text{P95 TTFT}$$

Jika $\text{GPU Cache Usage Factor} > 0.85$ atau $\text{Requests Waiting} > 5$, KEDA segera memicu instansiasi pod tambahan sebelum model mengalami degradasi performa atau *out-of-memory eviction*.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Naive) | Pendekatan Enterprise Production (Advanced) |
| :--- | :--- | :--- |
| **Load Balancing** | Round-Robin / Random L4-L7 Ingress. | Token-Hash & Prefix-Affinity Routing via Router L7 cerdas. |
| **Autoscaling** | HPA berbasis CPU / Memory / GPU Engine % metric. | Event-Driven Autoscaling (KEDA) berbasis KV-cache pressure & TTFT/ITL SLA. |
| **Pemisahan Workload** | Monolitik (Prefill & Decode bercampur di GPU lokal). | Disaggregated Architecture (Prefill Cluster terpisah dari Decode Cluster via RDMA). |
| **Edge Integration** | Seluruh komputasi dialirkan ke Central Cloud. | Hybrid: Edge Inference (SLM di on-prem/gateway) + Central Escalation untuk model besar. |
| **Multi-Tenancy** | 1 Model Dedicated = 1 Dedicated GPU Pool per Tenant. | Shared Base Foundation Model + Dynamic LoRA Adapter Swapping di VRAM. |
| **Cost Management** | Static Reserved Instances (100% on-demand). | Dynamic Spot-Fleet Orchestration, aggressive scale-to-zero, dan model bin-packing. |

---

### 5. How (Workflow Detail)

Alur kerja eksekusi inferensi enterprise:

```
[Client Request: Prompt + SessionID]
   │
   ├──> 1. Ingress Validation & Rate Limiting (Token Bucket per Tenant API Key)
   │
   ├──> 2. Exact Cache Lookup (SHA-256 Hash of Full Prompt) ────[Hit]───> Return Stream
   │                                                                      (Latency < 5ms)
   ├──> 3. Semantic Similarity Cache (Embedding Lookup Cosine > 0.98) ─[Hit]──> Return Stream
   │
   └──> [Cache Miss Pipeline]
           │
           ├──> 4. Tokenizer Profiling: Hitung Token Length & Identifikasi Prefix Hash
           │
           ├──> 5. Router Metadata Lookup: Cari Node Decode dengan residu KV-Cache tertinggi
           │
           ├──> 6. Admission Controller: Evaluasi KV-Cache Watermark target worker
           │       ├── Jika worker KV Cache > 90% ──> Alihkan ke Standby Worker / Queue
           │       └── Jika worker KV Cache <= 90% ─> Forward Request via gRPC Stream
           │
           ├──> 7. Prefill Phase Execution (Chunked Prefill)
           │
           ├──> 8. Decode Phase Execution (Continuous Batching + PagedAttention)
           │
           └──> 9. SSE Streaming Back to Client + Push Telemetry to Prometheus
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional Komersial
Bayangkan inferensi LLM konvensional seperti bandara kecil di mana pesawat carteran (prompt panjang) dan helikopter komuter (prompt pendek/chat) berbagi satu landasan pacu yang sama secara acak. Ketika sebuah pesawat kargo super berat mendarat (prefill 8k token), seluruh helikopter yang hendak mengangkut penumpang reguler (decode per token) terhenti di udara, kehabisan bahan bakar (*latency spike*).

Arsitektur produksi membaginya menjadi:
* **Landasan Pacu Khusus Super-Heavy (Prefill Nodes):** Dilengkapi infrastruktur kargo masif (H100 compute) yang mendaratkan pesawat besar secepat kilat.
* **Terminal Transfer Khusus (RDMA Fast Interconnect):** Memindahkan bagasi (KV-cache) langsung ke terminal gate tanpa melalui jalan raya biasa.
* **Gate Komuter Khusus (Decode Nodes):** Mengalirkan penumpang secara kontinyu tanpa terganggu operasi pendaratan kargo berat.
* **Menara Pengawas Cerdas (Smart Router):** Mengarahkan armada ke gate yang sudah memiliki kru servis yang sesuai (Prefix Cache), menghindari reposisi peralatan yang memakan waktu.

```
                           +-------------------------------------+
                           |      SMART ROUTER (L7 Proxy)        |
                           |  [Radix Prefix Table: NodeA: 80%]   |
                           +-------------------------------------+
                                      /               \
              (Routing Key: Hash #419)                 (Fallback / Dynamic)
                                    /                   \
                                   v                     v
         +----------------------------------+   +----------------------------------+
         |     NODE A (Decode Worker)       |   |     NODE B (Decode Worker)       |
         | +------------------------------+ |   | +------------------------------+ |
         | | KV Cache Pool (PagedAttention)| |   | | KV Cache Pool (PagedAttention)| |
         | | [Block 0] System Prompt (HIT)| |   | | [Block 0] Empty / Cold Cache | |
         | | [Block 1] Financial Docs(HIT)| |   | | [Block 1] Empty / Cold Cache | |
         | | [Block 2] Dynamic Token Gen  | |   | | [Block 2] Dynamic Token Gen  | |
         | +------------------------------+ |   | +------------------------------+ |
         | Status: 65% VRAM Allocated     | |   | Status: 20% VRAM Allocated     | |
         +----------------------------------+   +----------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Custom Prometheus Scraper & KV-Cache Watermark Guard
Skrip Python ini mensimulasikan komponen admission control lokal yang memonitor engine vLLM dan menolak request jika cache pressure berisiko menyebabkan memory thrashing/OOM.

```python
# simple_guard.py
import urllib.request
import json
import sys

def get_vllm_metrics(metrics_url: str = "http://localhost:8000/metrics") -> dict:
    req = urllib.request.Request(metrics_url)
    metrics = {}
    with urllib.request.urlopen(req) as resp:
        for line in resp.read().decode("utf-8").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split(" ")
            if len(parts) >= 2:
                metrics[parts[0]] = float(parts[1])
    return metrics

def is_worker_healthy_for_admission(threshold: float = 0.85) -> bool:
    try:
        metrics = get_vllm_metrics()
        # Ambil faktor penggunaan KV-Cache GPU
        gpu_cache_usage = metrics.get('vllm:gpu_cache_usage_factor', 0.0)
        requests_waiting = metrics.get('vllm:num_requests_waiting', 0.0)
        
        print(f"[METRIC] KV Cache Factor: {gpu_cache_usage:.2f} | Queue Depth: {int(requests_waiting)}")
        
        if gpu_cache_usage > threshold or requests_waiting > 10:
            return False
        return True
    except Exception as e:
        print(f"[ERROR] Failed to fetch metrics: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    admit = is_worker_healthy_for_admission(threshold=0.80)
    print(f"Decision: {'ADMIT_REQUEST' if admit else 'DROP_OR_REDIRECT_REQUEST'}")
```

#### B. Practical Example: Enterprise Smart Prefix-Affinity Router
Implementasi reverse proxy asinkronus menggunakan FastAPI, `httpx`, dan hashing prefix untuk mengarahkan trafik LLM secara deterministik ke worker yang memegang cache.

```python
# production_smart_router.py
import hashlib
import time
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn
from typing import List, Dict

app = FastAPI(title="Enterprise Inference Smart Router", version="1.0.0")

# Definisi Topology Pod Pekerja Inferensi
WORKER_POOL: List[Dict[str, str]] = [
    {"id": "worker-gpu-01", "url": "http://10.244.1.15:8000"},
    {"id": "worker-gpu-02", "url": "http://10.244.2.28:8000"},
    {"id": "worker-gpu-03", "url": "http://10.244.3.42:8000"},
]

client = httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=60.0))

def extract_prefix_fingerprint(prompt: str, token_window_chars: int = 256) -> str:
    """
    Mengekstrak hash prefix dari token pembuka (misal: System Prompt / RAG Document).
    Karakter awal merepresentasikan konteks statis yang di-cache di Radix Tree.
    """
    prefix_data = prompt[:token_window_chars].encode("utf-8")
    return hashlib.sha256(prefix_data).hexdigest()

def select_worker_affinity(prefix_hash: str, pool: List[Dict[str, str]]) -> Dict[str, str]:
    """
    Consistent Hash Ring sederhana untuk memetakan prefix hash ke worker tertentu.
    """
    hash_val = int(prefix_hash, 16)
    target_idx = hash_val % len(pool)
    return pool[target_idx]

async def check_worker_kv_health(worker_url: str) -> bool:
    """
    Healthcheck cepat ke endpoint metrics untuk memverifikasi kapasitas KV cache.
    """
    try:
        resp = await client.get(f"{worker_url}/metrics", timeout=0.8)
        if resp.status_code != 200:
            return False
        for line in resp.text.splitlines():
            if line.startswith("vllm:gpu_cache_usage_factor"):
                val = float(line.split(" ")[1])
                return val < 0.90  # Tolak jika utilisasi cache > 90%
        return True
    except Exception:
        return False

@app.post("/v1/chat/completions")
async def route_chat_completion(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON Payload")

    messages = payload.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="Empty messages payload")

    # Rekonstruksi string context untuk ekstraksi fingerprint prefix
    system_prompts = [m.get("content", "") for m in messages if m.get("role") in ["system", "user"]]
    context_str = " ".join(system_prompts)
    
    prefix_hash = extract_prefix_fingerprint(context_str)
    target_worker = select_worker_affinity(prefix_hash, WORKER_POOL)
    
    # Verifikasi Admission Control
    is_healthy = await check_worker_kv_health(target_worker["url"])
    if not is_healthy:
        # Fallback ke worker alternatif jika target utama sedang mengalami cache pressure
        fallback_candidates = [w for w in WORKER_POOL if w["id"] != target_worker["id"]]
        routed = False
        for alt_worker in fallback_candidates:
            if await check_worker_kv_health(alt_worker["url"]):
                target_worker = alt_worker
                routed = True
                break
        if not routed:
            raise HTTPException(status_code=503, detail="All inference workers are saturated (KV Cache Full)")

    # Forwarding Stream Request ke Target Engine
    headers = {key: value for key, value in request.headers.items() if key.lower() not in ["host", "content-length"]}
    
    req_upstream = client.build_request(
        method="POST",
        url=f"{target_worker['url']}/v1/chat/completions",
        json=payload,
        headers=headers
    )
    
    upstream_resp = await client.send(req_upstream, stream=True)
    
    if upstream_resp.status_code != 200:
        await upstream_resp.aclose()
        raise HTTPException(status_code=upstream_resp.status_code, detail="Upstream Engine Error")

    async def stream_generator():
        try:
            async for chunk in upstream_resp.aiter_raw():
                yield chunk
        finally:
            await upstream_resp.aclose()

    return StreamingResponse(
        stream_generator(),
        media_type=upstream_resp.headers.get("content-type", "text/event-stream"),
        headers={
            "X-Routed-Worker": target_worker["id"],
            "X-Prefix-Hash": prefix_hash[:8]
        }
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur GenAI Bank FinTech Tier-1 (50 Juta Query/Hari)
* **Konteks Masalah:** Bank digital global menjalankan aplikasi Customer Service & Analisis Portofolio RAG dengan LLM 70B parameter. Infrastruktur awal menggunakan 64 node NVIDIA H100 di AWS dengan biaya bulanan membengkak hingga $460.000. 
* **Gejala Kegagalan:** P99 TTFT mencapai 4.2 detik selama jam bursa buka. Upaya autoscaling HPA standar berbasis CPU/GPU usage justru menciptakan *thrashing*: pod baru memakan waktu 8 menit untuk cold-start (download model weights 140GB), lalu segera crash akibat OOM saat menerima lonjakan traffic serentak.
* **Arsitektur Solusi Terapan:**
  1. **Disaggregated Cluster:** Memisahkan 16 instance GPU Tensor-Parallel compute (H100) khusus prefill prompt dokumen perbankan, dan 32 instance GPU L40S berkepadatan tinggi untuk fase decode streaming token.
  2. **Prefix-Cache Affinity Router:** Semua dokumen SOP bank dan ringkasan portofolio pengguna di-hash. Router Envoy L7 cerdas memetakan nasabah berulang ke pod yang sama. Efisiensi Prefix-Cache melonjak dari 11% menjadi 78%.
  3. **KEDA Scaling via vLLM Metrics:** Autoscaling didorong oleh metrik `vllm:num_requests_waiting` dan `vllm:gpu_cache_usage_factor`. Pod ditambahkan ketika antrean > 3 selama 30 detik berkelanjutan.
  4. **Dynamic LoRA Multiplexing:** Alih-alih menjalankan 10 model berbeda untuk compliance, loans, fraud, dan retail, mereka menjalankan 1 single Llama-3-70B Base Model dengan 10 LoRA adapters yang di-swap on-the-fly di VRAM melalui fitur dynamic adapter loading.
* **Hasil:**
  * P99 TTFT turun drastis dari 4.200ms menjadi **340ms** (turun 91.9%).
  * Kebutuhan GPU terpangkas dari 64x H100 menjadi kombinasi 16x H100 + 24x L40S.
  * Tagihan cloud GPU bulanan terpangkas dari $460.000 menjadi **$165.000** (penghematan $295.000/bulan atau $3,54 Juta/tahun).

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Kerugian / Risiko |
| :--- | :--- | :--- |
| **Prefix-Cache Affinity Routing** | Pangkas TTFT secara eksponensial; hindari kalkulasi ulang KV-cache redundan. | Risiko hotspotting jika satu tenant/prompt sangat dominan; perlu fallback load balancing rumit. |
| **Disaggregated Prefill-Decode** | Mencegah lonjakan ITL; throughput kluster optimal; isolasi fault domain komputasi. | Membutuhkan topologi jaringan RDMA inter-node ultra-low latency; kompleksitas devops tinggi. |
| **Aggressive Autoscaling (Scale to Zero)** | Efisiensi biaya ekstrem saat malam hari atau traffic rendah. | *Cold-start latency* tinggi (2-8 menit untuk streaming bobot puluhan GB ke VRAM GPU). |
| **Spot Instance Usage** | Pangkas biaya komputasi GPU hingga 60-70% dibanding On-Demand. | Risiko terminasi instan dengan notice 2 menit; membutuhkan arsitektur state drainer yang tangguh. |
| **Dynamic LoRA Multiplexing** | Mengurangi VRAM footprint secara masif; mendukung multi-tasking ribuan tenant. | Latensi kecil saat swapping bobot LoRA baru ke CUDA core; keterbatasan ukuran rank adapter. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum:
1. **Menggunakan Standar L4 Round-Robin Ingress:** Menyebabkan request dengan prefix yang sama tersebar merata ke seluruh pod, melenyapkan kapabilitas hardware Radix-tree caching engine.
2. **Cold-Start Image & Weight Pulling Bottleneck:** Mengunduh model ribuan file dari HuggingFace Hub langsung saat Pod init. Pod membutuhkan waktu 15 menit untuk `Ready`, menggagalkan autoscaling KEDA.
3. **Mengabaikan Shared Memory POSIX (`/dev/shm`):** PyTorch distributed tensor parallelism (NCCL) membutuhkan alokasi IPC shared memory besar. Container Docker default membatasi `/dev/shm` ke 64MB, memicu error `NCCL WARN: Call to connect returned Connection refused` atau *SIGBUS crash*.
4. **Setting Concurrency Limit Tidak Realistis:** Mengonfigurasi `max_num_seqs` terlalu besar di vLLM melampaui kapasitas VRAM yang dialokasikan untuk KV-cache, menyebabkan *frequent KV-cache preemptions* (re-computation).

#### Panduan Troubleshooting Lapangan:

| Masalah | Investigasi Root Cause | Langkah Remediasi |
| :--- | :--- | :--- |
| `CUDA out of memory during decode phase` | Alokasi `--gpu-memory-utilization` terlalu tinggi (misal: 0.98), tidak menyisakan ruang untuk fragmentasi PyTorch. | Turunkan `--gpu-memory-utilization` ke 0.88-0.90; set `--max-num-batched-tokens` secara eksplisit. |
| Pod CrashLoopBackOff: `Bus error (core dumped)` | Alokasi `/dev/shm` default container (64Mi) habis oleh NCCL backend selama komunikasi Tensor Parallelism. | Tambahkan volume `emptyDir` dengan `medium: Memory` pada mount `/dev/shm` di Pod spec Kubernetes. |
| P95 Inter-Token Latency (ITL) berfluktuasi ekstrem | Chunked prefill non-aktif; request dengan prompt besar (8K+) memblokir token generation sequence lain. | Pasang argumen `--enable-chunked-prefill=true` dan batasi `--max-num-batched-tokens=2048` pada runtime engine. |
| KEDA tidak pernah trigger scale down | Prometheus query mengembalikan nilai `NaN` atau data metrik tertahan akibat idle scraping. | Pastikan operator KEDA menggunakan query `sum(vllm:num_requests_waiting) or vector(0)` untuk handle data null. |

---

### 11. Best Practices (Production Checklist)

#### Hardware & Driver Initialization:
- [ ] Non-aktifkan ECC memory dynamic page retirement check delay; kunci GPU Clocks ke performa konstan (`nvidia-smi -lgc <MAX_CLOCK>,<MAX_CLOCK>`).
- [ ] Mount `/dev/shm` menggunakan memori RAM host secara eksplisit di manifest Kubernetes.
- [ ] Model weights disimpan di NVMe local disk (scratch storage) atau di-mount via distributed shared caching filesystem (seperti JuiceFS / Alluxio) via VPC internal endpoint.

#### Engine Runtime Configuration:
- [ ] Aktifkan `--enable-prefix-caching` pada vLLM / TensorRT-LLM.
- [ ] Aktifkan `--enable-chunked-prefill` untuk meratakan throughput komputasi prefill dan decode.
- [ ] Konfigurasi parameter batching: `--max-model-len`, `--max-num-seqs`, dan `--max-num-batched-tokens` berdasarkan kalkulasi kapasitas total token context vs ukuran VRAM.

#### Networking & Resiliency:
- [ ] Terapkan health probe Kubernetes (`readinessProbe` dan `livenessProbe`) pada endpoint `/health` bawaan engine, bukan port TCP mentah.
- [ ] Implementasikan gRPC / HTTP2 streaming keep-alive timeouts yang memadai (>300 detik) untuk mencegah proxy ingress memutus koneksi inferensi yang panjang.
- [ ] Siapkan Pod Disruption Budgets (PDB) dengan `minAvailable: 1` per shard cluster.

---

### 12. Hands-on Practice

Buat dan simpan seluruh file implementasi berikut di direktori `hands-on/m02/`.

#### Langkah 1: Manifest KEDA ScaledObject SLA-Aware
Simpan file ini sebagai `hands-on/m02/keda-vllm-autoscaler.yaml`. Manifest ini mengontrol scaling pod worker berdasarkan kedalaman antrean permintaan vLLM.

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: vllm-sla-autoscaler
  namespace: inference-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vllm-llama3-worker
  minReplicaCount: 2
  maxReplicaCount: 10
  cooldownPeriod: 300
  pollingInterval: 10
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleDown:
          stabilizationWindowSeconds: 600
          policies:
          - type: Percent
            value: 20
            periodSeconds: 60
        scaleUp:
          stabilizationWindowSeconds: 0
          policies:
          - type: Percent
            value: 100
            periodSeconds: 15
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus-server.monitoring.svc.cluster.local:9090
      metricName: vllm_num_requests_waiting
      query: sum(vllm:num_requests_waiting{namespace="inference-prod"})
      threshold: '4'
  - type: prometheus
    metadata:
      serverAddress: http://prometheus-server.monitoring.svc.cluster.local:9090
      metricName: vllm_gpu_cache_usage_factor
      query: max(vllm:gpu_cache_usage_factor{namespace="inference-prod"})
      threshold: '0.85'
```

#### Langkah 2: Manifest Deployment Pod dengan Resource Allocation Lengkap
Simpan file ini sebagai `hands-on/m02/vllm-deployment.yaml`.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-llama3-worker
  namespace: inference-prod
  labels:
    app: vllm-worker
spec:
  replicas: 2
  selector:
    matchLabels:
      app: vllm-worker
  template:
    metadata:
      labels:
        app: vllm-worker
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: vllm-engine
        image: vllm/vllm-openai:v0.6.2
        args:
        - "--model"
        - "meta-llama/Meta-Llama-3-8B-Instruct"
        - "--tensor-parallel-size"
        - "1"
        - "--gpu-memory-utilization"
        - "0.90"
        - "--enable-prefix-caching"
        - "--enable-chunked-prefill"
        - "--max-model-len"
        - "8192"
        ports:
        - containerPort: 8000
          name: http
        resources:
          limits:
            nvidia.com/gpu: "1"
            memory: 32Gi
            cpu: "8"
          requests:
            nvidia.com/gpu: "1"
            memory: 16Gi
            cpu: "4"
        volumeMounts:
        - mountPath: /dev/shm
          name: dshm
        - mountPath: /root/.cache/huggingface
          name: model-storage
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 120
          periodSeconds: 15
      volumes:
      - name: dshm
        emptyDir:
          medium: Memory
          sizeLimit: 8Gi
      - name: model-storage
        persistentVolumeClaim:
          claimName: nfs-model-weights-pvc
```

#### Langkah 3: Eksekusi Verifikasi Lingkungan
Jalankan perintah berikut di shell untuk memverifikasi deployment:

```bash
# Buat namespace dan apply manifest
kubectl create namespace inference-prod --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f hands-on/m02/vllm-deployment.yaml
kubectl apply -f hands-on/m02/keda-vllm-autoscaler.yaml

# Pantau status readiness pod dan metrik vLLM
kubectl get pods -n inference-prod -w
```

---

### 13. Exercise

#### Level Easy:
Buat skrip bash/Python yang memvalidasi ketersediaan endpoint `/metrics` dari tiga instance worker vLLM yang berbeda dan memparsing nilai `vllm:num_requests_running` serta `vllm:gpu_cache_usage_factor` secara berkala setiap 2 detik.

#### Level Medium:
Perluas kode `production_smart_router.py` agar mengimplementasikan algoritma *Weighted Least-Connection with KV-Cache Bias*:
1. Jika prompt prefix cocok dengan cache worker tertentu, bobot worker tersebut mendapat prioritas 70%.
2. Jika ada worker lain yang antrean permintaannya 0 sementara worker target antreannya > 5, alihkan request secara otomatis ke worker kosong (dynamic eviction tradeoff).

#### Level Hard:
Rancang dan simulasikan *Disaggregated Prefill-Decode pipeline* sederhana di Python:
1. Engine A (Prefill simulator) menerima teks panjang, menghitung dimensi KV-Cache tensor, dan menyimpannya di Redis shared memory.
2. Engine A mengembalikan ID pointer KV-cache ke client.
3. Engine B (Decode simulator) menerima pointer ID tersebut, membaca tensor KV-cache langsung dari shared memory tanpa prefill ulang, dan melanjutkan autoregressive loop sebanyak 50 token.

---

### 14. Challenge

**Skenario Kasus:** Anda adalah Lead Inference Platform Engineer di Unicorn E-Commerce. Sistem Anda menghadapi Flash Sale dengan lonjakan traffic hingga 15.000 RPS ke chatbot rekomendasi produk. 
Model yang digunakan adalah model 70B parameter (4x H100 GPU per replica).

**Tantangan Arsitektur:**
1. Desain arsitektur *Zero-Downtime Hot Model Swapping* ketika bobot model di-update dari versi Checkpoint v1.2 ke v1.3 tanpa membuang KV-Cache request yang sedang berjalan dan tanpa menyebabkan *Out of Memory* pada cluster GPU.
2. Rumuskan strategi integrasi *Spot Instance Termination Notice (2-Minute Warning)* dari AWS/GCP:
   * Bagaimana router mengetahui bahwa node decode tertentu akan di-terminate dalam 120 detik?
   * Bagaimana mekanisme memindahkan state *PagedAttention memory blocks* dari node yang hendak mati ke node baru tanpa memutuskan koneksi Server-Sent Events (SSE) klien yang sedang membaca respons token?

*Kirimkan rancangan ini dalam bentuk arsitektur diagram sistem terperinci, alur state machine mitigasi interupsi, dan pseudo-code penanganan drain connection.*

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal):
1. Mengapa metrik CPU Utilization atau GPU Processing Utilization standar dari NVML tidak efektif digunakan sebagai pemicu Horizontal Autoscaling pada LLM serving?
2. Apa fungsi mendasar dari parameter `/dev/shm` (POSIX shared memory) dalam deployment model LLM multi-GPU (Tensor Parallel)?
3. Apa perbedaan esensial antara fase *Prefill* dan fase *Decode* dalam hal konsumsi resource hardware?
4. Apa yang dimaksud dengan *Prefix Caching* (misal: Radix Tree Cache) pada engine inferensi?
5. Mengapa format respons streaming LLM di web modern hampir secara universal menggunakan protokol *Server-Sent Events* (SSE) alih-alih polling HTTP biasa?

#### Intermediate (5 Soal):
1. Bagaimana fenomena *KV-Cache Thrashing* dapat terjadi, dan apa dampaknya secara langsung terhadap throughput engine dan latency (ITL)?
2. Jelaskan mekanisme kerja *Chunked Prefill* dan bagaimana fitur tersebut menstabilkan *Inter-Token Latency* (ITL) bagi request lain yang sedang berada dalam tahap decode!
3. Dalam skenario apa arsitektur *Disaggregated Prefill-Decode* menjadi jauh lebih hemat biaya dibanding menyatukan prefill dan decode pada GPU yang sama?
4. Mengapa load balancer L4 murni (seperti TCP IPVS load balancer) merusak performa *Prefix Cache Hit Ratio* pada kluster model serving?
5. Bagaimana cara kerja *Dynamic LoRA Multiplexing* pada level VRAM GPU ketika melayani multi-tenant dengan ratusan fine-tuned model yang berbeda?

#### Skenario Kasus Produksi (3 Soal):
1. **Skenario A:** Pada dashboard Grafana, Anda melihat metrik `P99 Time to First Token (TTFT)` melonjak dari 150ms ke 5000ms secara acak setiap jam, tetapi `Inter-Token Latency (ITL)` tetap konstan di angka 20ms/token. Apa kemungkinan akar masalah arsitekturalnya, dan metrik apa yang harus Anda investigasi untuk membuktikannya?
2. **Skenario B:** Cluster inferensi Anda menggunakan 100% GPU Spot Instances untuk menghemat biaya. Saat terjadi event pemutusan mendadak (preemption) pada 30% node worker decode, seluruh pod API gateway Anda mengalami crash cascading (*thundering herd*). Desain mekanisme pertahanan sistem untuk mencegah failure cascading tersebut!
3. **Skenario C:** Tenant enterprise A memasukkan prompt analisis laporan keuangan sepanjang 32.000 token setiap 10 detik sekali, menyebabkan pengguna lain mengalami peningkatan ITL secara drastis (*starvation*). Kebijakan admission control dan scheduling apa yang wajib diaktifkan pada layer engine untuk menegakkan fairness tanpa menolak request Tenant A?

---

### 16. Summary

Operasionalisasi inferensi kecerdasan artifisial skala enterprise bukan sekadar menjalankan container model di Kubernetes. Ini adalah disiplin rekayasa sistem yang menuntut sinkronisasi antara keterbatasan fisik hardware (VRAM memory bandwidth, compute TFLOPS, bandwidth bus NVLink/RDMA) dengan dinamika traffic jaringan L7. 

Kunci stabilitas dan efisiensi biaya inferensi modern bertumpu pada empat pilar:
1. **Pemisahan Karakteristik Workload:** Pemisahan prefill (compute-bound) dan decode (bandwidth-bound).
2. **State-Aware Load Balancing:** Memanfaatkan prefix context affinity agar engine tidak membuang clock cycle untuk menghitung ulang state KV yang pernah diproses.
3. **Autoscaling Berbasis Metrik Domain LLM:** Menggunakan metrik KV cache saturation dan queue depth via KEDA alih-alih utilitas CPU/GPU generik.
4. **Resiliency Guardrails:** Penerapan chunked prefill, pembatasan shared memory yang presisi, dan admission control proaktif untuk mencegah crash out-of-memory secara deterministik.