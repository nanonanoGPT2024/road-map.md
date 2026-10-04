# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 10: Financial Acumen, Vendor Management, and Crisis Resilience in AI, Data, and Autonomous Agent Systems**
**Kategori: 08-AI-Data-and-Autonomous-Agents**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, seorang Engineering Manager (EM) dan Lead Architect mampu:
1. **Merancang dan Mengimplementasikan FinOps AI Architecture**: Membangun sistem *cost-observability* real-time berbasis token, throughput inference, dan komputasi GPU/vLLM yang terintegrasi dengan pipeline CI/CD dan runtime gateway.
2. **Mengeksekusi Dynamic Multi-Vendor Arbitration & Routing**: Membangun mekanisme fallback otomatis dan routing cerdas berbasis SLA, latensi, kualitas (eval benchmark), dan margin biaya antar penyedia LLM (OpenAI, Anthropic, Bedrock, self-hosted open-weight).
3. **Membangun Runtime Circuit Breakers & Kill-Switches**: Mencegah insiden *runaway cost* akibat recursive loops pada autonomous multi-agent systems melalui sliding-window budget limiting dan dynamic token budgeting.
4. **Mengevaluasi dan Menegosiasikan Kontrak Vendor Skala Enterprise**: Menganalisis Reserved Instance vs. Savings Plans vs. Provisioned Throughput (PTUs), menghitung Total Cost of Ownership (TCO), serta menegakkan service credit berbasis pelanggaran SLI/SLO.
5. **Mengelola Krisis Finansial dan Downtime Vendor**: Memimpin incident response krisis saat penyedia AI upstream mengalami *hard outage* atau degradasi performa akut tanpa mengorbankan Service Level Agreement ke pelanggan akhir.

---

## 2. Prerequisite

*   **Pemahaman Mendalam**: Arsitektur Autonomous Agents (ReAct, LangGraph, AutoGen) dan siklus eksekusi tool-calling.
*   **Fondasi Infrastruktur**: Docker, Kubernetes, distributed caching (Redis), serta prinsip reverse proxy/API Gateway (Envoy/FastAPI).
*   **Observabilitas**: Prometheus metrics, OpenTelemetry (tracing spans untuk LLM), Grafana dashboarding.
*   **Finansial & Operasional**: Memahami konsep OpEx vs. CapEx, Blended Cost per Token, P99 Latency, GPU Memory Bandwidth (VRAM allocation), dan amortisasi hardware.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 FinOps untuk Generative AI & Autonomous Agents

Dalam ekosistem *traditional software*, biaya komputasi berbanding lurus secara linier terhadap *request per second* (RPS) dengan margin deterministik. Pada ekosistem **Autonomous Agents**, kompleksitas komputasi bersifat *non-deterministik*. Sebuah agent yang bertugas melakukan rekonsiliasi data keuangan dapat mengeksekusi 1 call atau 45 iterative reasoning steps (Chain-of-Thought) tergantung pada entropi input.

```
Cost_Total = ∑ (Tokens_Prompt × Price_Prompt) + ∑ (Tokens_Completion × Price_Completion) + Overhead_VectorDB + Overhead_ToolExecution
```

Ketika model reasoning seperti OpenAI `o1`/`o3` atau Anthropic Claude 3.5 Sonnet dengan extended thinking diintegrasikan, rasio completion-to-prompt melonjak tajam. Tanpa arsitektur kontrol yang ketat, satu agent yang terjebak dalam *infinite reasoning loop* akibat edge case parser tool dapat menghabiskan ribuan dolar dalam hitungan jam.

### 3.2 Dynamic Cost-Aware Semantic Arbitration Engine

Arsitektur produksi modern membutuhkan abstraction layer antara Agent Logic dan Upstream Model Provider. Abstraction layer ini disebut **Model Routing Gateway**.

```
[Agent Execution Engine] 
           │
           ▼
[FinOps Model Gateway] 
   ├── 1. Budget Authorization Check (Tenant Quota Ledger)
   ├── 2. Semantic Cache Probe (Exact/Vector similarity hit)
   ├── 3. Dynamic Model Matrix Arbiter (Quality Score, Cost, Latency)
   │         ├── Primary Tier: Proprietary Frontier (e.g., Claude 3.5 Sonnet)
   │         ├── Secondary Tier: Frontier Alternative (e.g., GPT-4o)
   │         └── Tertiary Tier: Self-Hosted / Distilled (e.g., Llama 3.3 70B on vLLM)
   ├── 4. Token Circuit Breaker (Window-based Hard Stop)
   └── 5. Telemetry & Cost Allocator (OpenTelemetry + Prometheus)
```

Gateway melakukan determinasi routing menggunakan dynamic scoring matrix:

$$\text{Score} = w_q \cdot \text{NormalizedQuality} - w_c \cdot \text{NormalizedCost} - w_l \cdot \text{P99Latency} - w_e \cdot \text{ErrorRate}$$

Di mana bobot ($w_q, w_c, w_l, w_e$) dapat diatur secara dinamis melalui kontrol FinOps policy engine tergantung tier pelanggan (Enterprise vs. Free Tier).

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional | Enterprise FinOps & Multi-Vendor Engine |
| :--- | :--- | :--- |
| **Integrasi Vendor** | Direct SDK call (e.g., `openai.ChatCompletion`) tersebar di codebase. | Unified API Gateway via Model Proxy terpusat dengan abstraction schema. |
| **Mitigasi Biaya** | Post-facto billing alerts via AWS Budgets / Cloud Dashboard bulanan. | In-flight execution hard-caps, sliding-window token circuit breaker per-request & tenant. |
| **Resiliensi Vendor** | Hardcoded model fallback manual saat terjadi downtime total. | Real-time automated arbitration berbasis health-check probing dan synthetic testing. |
| **Vendor Lock-in** | Menggunakan vendor-specific prompt tooling dan proprietary memory stores. | Canonical tool definitions, prompt sanitization layers, and model-agnostic schema wrappers. |
| **SLA Enforcement** | Pasif menerima pengumuman vendor status page. | Active synthetic SLI probes untuk audit klaim kompensasi Downtime Service Credit. |

---

## 5. How (Workflow Detail)

1.  **Ingress & Tenant Context Validation**: Request masuk membawa header metadata (Tenant ID, Project ID, Max Budget Tolerance).
2.  **Ledger Inspection**: Gateway memvalidasi Redis cache apakah tenant telah melampaui *daily cost threshold*. Jika ya, alihkan request ke model tier rendah atau tolak dengan `429 Insufficient Financial Quota`.
3.  **Semantic Cache Lookup**: Lakukan hash lookup dan embedding similarity search pada Vector Cache. Jika terdapat response semantik yang identik ($\text{similarity} \ge 0.96$) dengan TTL valid, return langsung ($0 inference cost).
4.  **Route Arbitration**:
    *   Periksa status matrix kesehatan vendor (Error Rate < 2% & P99 Latency < SLA limit).
    *   Pilih model optimum sesuai konfigurasi cost-performance routing.
5.  **Execution & Streaming Telemetry**:
    *   Eksekusi call secara asynchronous dengan timeout budget yang ketat.
    *   Catat token prompt, token completion, serta reasoning tokens via response headers.
6.  **Circuit Breaker Evaluation**:
    *   Update running cost counter pada Redis sliding window (1-menit dan 1-jam).
    *   Jika threshold terlewati di tengah eksekusi agent loop, potong eksekusi dan paksa model mengeluarkan sintesis kesimpulan parsial.
7.  **Egress Telemetry Push**: Kirim metrics log ke Prometheus dan trace spans ke OpenTelemetry collector.

---

## 6. Analogy & Diagram ASCII

Bayangkan Model Gateway sebagai **Lantai Bursa Saham (Smart Order Router)**:

```
+-----------------------------------------------------------------------+
|                       SMART AI ORDER ROUTER                           |
+-----------------------------------------------------------------------+
       |                                                    |
       v                                                    v
[Incoming Agent Order]                              [Financial Controls]
"Run Code Review Agent"                             "Max Budget: $0.15"
       |                                                    |
       +-------------------------+--------------------------+
                                 |
                                 v
                +----------------------------------+
                |    Semantic Cache Check (Redis)  |
                +----------------------------------+
                     | Hit ($0.00)           | Miss
                     v                       v
              [Return Cache]     +-----------------------+
                                 |  Health & Cost Matrix |
                                 +-----------------------+
                                    /         |         \
                                   /          |          \
                 [Healthy: Low Cost]   [Degraded]    [Operational]
                         |                    |             |
                         v                    v             v
                  +-------------+      +-------------+ +-------------+
                  | Llama 3 70B |      | Claude 3.5  | |   GPT-4o    |
                  | (Self-Host) |      | (SaaS API)  | | (SaaS API)  |
                  +-------------+      +-------------+ +-------------+
                         |                    |             |
                         +--------------------+-------------+
                                              |
                                              v
                              +--------------------------------+
                              | Runaway Cost Circuit Breaker   |
                              | [OK: $0.038 / Limit: $0.150]   |
                              +--------------------------------+
                                              |
                                              v
                                      [Response to Agent]
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Baseline Static Model Cost Calculator

```python
from typing import Dict

RATES_PER_1K_TOKENS: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "claude-3-5-sonnet": {"input": 0.0030, "output": 0.015},
    "llama-3-3-70b-vllm": {"input": 0.0007, "output": 0.0009},
}

def calculate_inference_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    if model not in RATES_PER_1K_TOKENS:
        raise ValueError(f"Model {model} pricing not registered.")
    
    rates = RATES_PER_1K_TOKENS[model]
    input_cost = (input_tokens / 1000.0) * rates["input"]
    output_cost = (output_tokens / 1000.0) * rates["output"]
    return round(input_cost + output_cost, 6)

print(f"GPT-4o Cost: ${calculate_inference_cost('gpt-4o', 12000, 3500)}")
```

### 7.2 Practical Example: Enterprise Multi-Vendor Gateway with Circuit Breaker

Contoh implementasi production-ready API Proxy menggunakan **FastAPI**, **Redis** untuk sliding-window tracking, circuit breaker, dan fallback failover otomatis.

```python
# Save as: gateway_engine.py
import time
import os
import redis
import httpx
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Request, Depends
from typing import List, Optional, Dict, Any

app = FastAPI(title="Enterprise AI FinOps & Circuit Breaker Gateway")

# Setup Redis connection pool
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Configuration Constants
MODEL_PRICING = {
    "anthropic/claude-3-5-sonnet": {"input": 0.000003, "output": 0.000015},
    "openai/gpt-4o": {"input": 0.0000025, "output": 0.000010},
    "vllm/llama-3-3-70b": {"input": 0.0000007, "output": 0.0000009}
}

FALLBACK_ORDER = [
    "anthropic/claude-3-5-sonnet",
    "openai/gpt-4o",
    "vllm/llama-3-3-70b"
]

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatPayload(BaseModel):
    tenant_id: str
    session_id: str
    max_budget_usd: float = Field(default=0.20, description="Max spend allocated for this session window")
    messages: List[ChatMessage]

class CostCircuitBreaker:
    """Sliding Window Cost Breaker backed by Redis."""
    def __init__(self, client: redis.Redis, window_seconds: int = 3600):
        self.client = client
        self.window = window_seconds

    def check_and_increment(self, tenant_id: str, estimated_cost: float, max_budget: float) -> bool:
        now = time.time()
        key = f"finops:budget:{tenant_id}"
        pipe = self.client.pipeline()

        # Remove elements older than window
        pipe.zremrangebyscore(key, 0, now - self.window)
        # Sum valid costs within window
        pipe.zrange(key, 0, -1, withscores=False)
        results = pipe.execute()

        current_spent = sum([float(val.split(":")[1]) for val in results[1]]) if results[1] else 0.0

        if (current_spent + estimated_cost) > max_budget:
            return False  # Circuit tripped

        # Record this intent tentatively
        unique_entry = f"{now}:{estimated_cost}"
        pipe.zadd(key, {unique_entry: now})
        pipe.expire(key, self.window)
        pipe.execute()
        return True

    def reconcile_actual(self, tenant_id: str, actual_cost: float):
        now = time.time()
        key = f"finops:realized:{tenant_id}"
        self.client.hincrbyfloat(key, "total_spend_usd", actual_cost)

circuit_breaker = CostCircuitBreaker(redis_client)

class UpstreamClient:
    """Simulated resilient LLM client with multi-provider failover."""
    
    @staticmethod
    async def call_provider(provider_model: str, messages: List[ChatMessage]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Simulate real network call to downstream providers
            # In production, use actual OpenAI/Anthropic/vLLM endpoints
            if "fail" in messages[0].content:
                raise httpx.RequestError(f"Provider {provider_model} is returning 503 Outage.")
            
            # Simulated usage
            prompt_tokens = sum([len(m.content.split()) * 2 for m in messages])
            completion_tokens = 150
            
            return {
                "model_used": provider_model,
                "content": f"Synthesized response from [{provider_model}].",
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens
                }
            }

@app.post("/v1/chat/completions/resilient")
async def execute_resilient_agent_call(payload: ChatPayload):
    # 1. Pre-computation estimation: Assume high-water-mark 4000 tokens
    estimated_ceiling_cost = 0.05
    
    # 2. Financial Circuit Breaker Verification
    is_allowed = circuit_breaker.check_and_increment(
        tenant_id=payload.tenant_id,
        estimated_cost=estimated_ceiling_cost,
        max_budget=payload.max_budget_usd
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Financial Circuit Breaker Tripped: Hourly tenant limit of ${payload.max_budget_usd} exceeded."
        )

    # 3. Dynamic Fallback Execution Loop
    last_exception = None
    for model_target in FALLBACK_ORDER:
        try:
            raw_response = await UpstreamClient.call_provider(model_target, payload.messages)
            
            # 4. Calculate Exact Financial Consumption
            usage = raw_response["usage"]
            pricing = MODEL_PRICING[model_target]
            realized_cost = (usage["prompt_tokens"] * pricing["input"]) + \
                            (usage["completion_tokens"] * pricing["output"])

            circuit_breaker.reconcile_actual(payload.tenant_id, realized_cost)

            return {
                "status": "success",
                "resolved_model": model_target,
                "cost_usd": realized_cost,
                "data": raw_response["content"],
                "usage": usage
            }
        except httpx.RequestError as exc:
            last_exception = exc
            # Log circuit warning and trigger next in line
            continue

    raise HTTPException(
        status_code=502,
        detail=f"All upstream AI vendors exhausted. Upstream failure: {str(last_exception)}"
    )
```

---

## 8. Real World Case Study (Enterprise Scale)

### 8.1 Konteks: Insiden "Autonomous Loop Billing Explosion" pada FinTech Unicorn
Sebuah platform Autonomous KYC & Financial Fraud Detection di Asia Tenggara mempekerjakan *Autonomous Reconciliation Agents* yang memproses dokumen transaksi PDF secara mandiri. Agen tersebut menggunakan pola ReAct (Reasoning + Acting) yang dipandu oleh frontier model berbayar $15/1M tokens completion.

### 8.2 Insiden
Pada hari Jumat pukul 23:14, seorang pengguna korporat mengunggah berkas neraca saldo PDF corrupt dengan struktur tabel melingkar (*cyclical reference*). 
1. Parser JSON lokal gagal menghasilkan output valid.
2. Agent secara rekursif mengulang pemanggilan model untuk "memperbaiki format JSON" (*self-healing prompt loop*).
3. Karena tidak adanya arsitektur *step-bounding* dan sliding window cost ceiling, agen mengeksekusi 18.000 reasoning loop dalam 4 jam.
4. Total tagihan API langsung melonjak **$14.200 USD dalam satu malam** untuk satu tenant tunggal, sekaligus memicu throttling API rate limit yang menyebabkan downtime untuk ratusan pelanggan lain.

### 8.3 Solusi Skala Produksi yang Diterapkan
Engineering Manager memimpin reformasi arsitektural menyeluruh:
1. **Deterministic Execution Bounds**: Membatasi recursive depth agent maksimal 8 iterations. Jika batas tercapai, sistem melakukan eksekusi fallback *deterministic human-in-the-loop task*.
2. **Gateway-Level Real-time Ledger**: Mengimplementasikan sliding window budget ceiling di Redis (seperti pada modul 7.2) dengan hard limit $0.50 per eksekusi dokumen.
3. **Local Distilled Screening**: Mengarahkan proses OCR parsing awal ke model open-weight Llama 3 8B yang di-host mandiri pada AWS ECS g5.xlarge instances ($1.006/jam flat), memangkas dependency frontier models sebesar 78%.
4. **Hasil Finansial**: Biaya operasional bulanan turun dari $82.000 menjadi $19.400 dengan P95 latency membaik dari 4.2 detik menjadi 1.1 detik.

---

## 9. Trade-offs

```
                       [Frontier SaaS (Claude/OpenAI)]
                                     ▲
                                    / \
                                   /   \
               High Quality, Low CapEx /     \ Expensive at Scale, Zero Privacy Control
                                 /       \
                                /         \
  [Self-Hosted Multi-GPU vLLM] ◄───────────► [Hybrid Orchestration Gateway]
  Low OpEx at High Throughput                 Balanced TCO, High Code Complexity,
  High Fixed CapEx & Maintenance Burden       Operational Governance Overhead
```

| Dimensi | All-In Frontier SaaS (OpenAI/Anthropic) | Fully Self-Hosted Open-Weight (vLLM/TGI) | Hybrid Arbitrated Gateway |
| :--- | :--- | :--- | :--- |
| **Model Quality** | Sangat Tinggi (SOTA General Reasoning). | Tergantung fine-tuning; tertinggal pada general edge-cases. | Tinggi (Routing tugas kompleks ke SaaS, tugas rutin ke open-weight). |
| **Biaya Per Token** | Variabel (OpEx murni); Sangat mahal pada throughput tinggi. | Biaya komputasi tetap per jam/GPU; amortisasi sangat murah pada load tinggi. | Teroptimasi secara dinamis; menekan pemborosan hingga 60-70%. |
| **P99 Latency** | Fluktuatif (Bergantung shared queue vendor dan network hops). | Deterministic & Dapat diatur via batching parameter (`max-num-seqs`). | Stabil via automated fallback saat vendor degradasi. |
| **Vendor Risk** | Sangat Tinggi (API deprecation, privacy policy change, outages). | Zero external risk; 100% operational risk internal tim infrastructure. | Termitigasi secara penuh melalui multi-cloud/multi-vendor distribution. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Silent Degradation pada Fallback Multi-Vendor
*   **Kesalahan**: Saat Anthropic mengalami downtime, gateway secara buta mengalihkan prompt ke open-weight model 8B tanpa penyesuaian instruksi atau tool formatting.
*   **Dampak**: Model 8B mengalami halusinasi sintaks tools, memicu catastrophic error cascade pada execution pipeline downstream.
*   **Solusi**: Terapkan **Schema Normalization Layer**. Jangan gunakan prompt native yang sarat vendor-specific system directives tanpa transpiler layer.

### 10.2 Abstraksi Biaya Reasoning Token (Hidden Thinking Cost)
*   **Kesalahan**: Menghitung estimasi biaya hanya berdasarkan `max_tokens` output eksplisit tanpa memperhitungkan hidden CoT tokens pada reasoning models (`o1`, `o3-mini`, `Claude 3.7 thinking`).
*   **Dampak**: Tagihan melambung 5x-10x di atas kalkulasi budget awal.
*   **Solusi**: Inspect response metadata field `completion_tokens_details.reasoning_tokens` secara eksplisit dan masukkan ke dalam ledger tracking formula.

---

## 11. Best Practices (Production Checklist)

- [ ] **Contractual SLA Verification**: Pastikan SLA vendor mencakup *minimum uptime* $\ge 99.9\%$, dengan pasal *financial service credits* eksplisit yang didukung data telemetry internal perusahaan.
- [ ] **Dual-Region / Multi-Provider Redundancy**: Setidaknya miliki dua API provider enterprise independen (misal: Anthropic via AWS Bedrock + OpenAI Direct) untuk mitigasi DNS/Global Edge Network failure.
- [ ] **Semantic Caching Layer**: Gunakan Redis/Milvus untuk caching query berulang; evaluasi cache ratio setiap sprint (target $\ge 20\%$ cache hit pada workload enterprise).
- [ ] **Decoupled Prompt Schemas**: Isolasi prompt templates dari parameter provider spesifik menggunakan Pydantic abstraction schemas.
- [ ] **Automated FinOps Anomaly Alert**: Pasang alarm Prometheus Alertmanager ketika pembakaran biaya per menit melonjak $> 3\sigma$ dari historical rolling baseline 7-hari.
- [ ] **Step Bounds pada Recursive Agents**: Hardcode batas maksimal loop iterasi agent ($\le 10$ steps) langsung pada runtime framework.

---

## 12. Hands-on Practice

Buat dan simpan seluruh artefak praktikum ini di direktori: `hands-on/m02/`

### Langkah 1: Siapkan Environment
```bash
mkdir -p hands-on/m02
cd hands-on/m02
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn redis httpx pydantic pytest pytest-asyncio
```

### Langkah 2: Jalankan Redis Instance
```bash
docker run -d --name finops-redis -p 6379:6379 redis:7-alpine
```

### Langkah 3: Tuliskan Mock Provider & Proxy Gateway
Salin kode dari **Seksi 7.2** dan simpan sebagai `hands-on/m02/gateway_engine.py`.

### Langkah 4: Tuliskan Verification Test Harness
Buat file `hands-on/m02/test_gateway.py`:

```python
import pytest
import httpx

BASE_URL = "http://localhost:8000"

@pytest.mark.asyncio
async def test_resilient_routing_success():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        payload = {
            "tenant_id": "enterprise-corp-01",
            "session_id": "sess-alpha-123",
            "max_budget_usd": 0.50,
            "messages": [{"role": "user", "content": "Analyze quarterly income report."}]
        }
        response = await client.post("/v1/chat/completions/resilient", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "resolved_model" in data
        assert data["cost_usd"] > 0

@pytest.mark.asyncio
async def test_circuit_breaker_tripped():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        payload = {
            "tenant_id": "frugal-startup-llc",
            "session_id": "sess-beta-456",
            "max_budget_usd": 0.04,  # Lower than single transaction safety margin ($0.05)
            "messages": [{"role": "user", "content": "Run deep audit."}]
        }
        response = await client.post("/v1/chat/completions/resilient", json=payload)
        assert response.status_code == 429
        assert "Financial Circuit Breaker Tripped" in response.json()["detail"]
```

### Langkah 5: Eksekusi dan Validasi
```bash
# Terminal 1: Jalankan service gateway
uvicorn gateway_engine:app --port 8000 --reload

# Terminal 2: Jalankan verification harness
pytest -v test_gateway.py
```

---

## 13. Exercise

### Level Easy
Modifikasi file `gateway_engine.py` agar mencatat metrics Prometheus counter berikut setiap kali request berhasil dieksekusi:
*   `finops_tokens_total{tenant_id, model, type="prompt|completion"}`
*   `finops_cost_usd_total{tenant_id, model}`

### Level Medium
Tambahkan mekanisme **Dynamic Semantic Caching** pada `gateway_engine.py`:
Sebelum memanggil model provider, buat SHA-256 hash dari serialisasi pesan `payload.messages`. Jika hash ada di Redis key `finops:cache:<hash>`, kembalikan response tersimpan dengan field `"cost_usd": 0.0` dan header HTTP `"X-Cache-Lookup": "HIT"`.

### Level Hard
Implementasikan **Dynamic Latency-Aware Fallback**:
Buat background task di FastAPI yang melakukan ping synthetic health check setiap 10 detik ke semua upstream model provider. Jika provider utama mencatat P99 latency $> 3500\text{ms}$ dalam 5 probe terakhir atau error rate $> 5\%$, pindahkan provider tersebut ke status `DEGRADED` dan alihkan traffic prioritas secara mulus ke secondary tier tanpa menunggu request real user mengalami timeout.

---

## 14. Challenge

**Skenario**: Perusahaan Anda adalah penyedia layanan Enterprise Autonomous Legal Discovery. Sistem memproses 20 juta token per hari. Dua jam sebelum penutupan audit akhir tahun, provider AI utama Anda (Tier 1) mengalami **Hard Global Outage** (HTTP 500 & Drop Connections). Pada saat yang bersamaan, provider Tier 2 Anda memberlakukan *strict rate limiting* (HTTP 429) karena lonjakan migrasi traffic global.

**Misi Arsitektural**:
Rancang dokumen arsitektur dan mitigasi teknis (tanpa menggunakan implementasi vendor proprietary tertutup):
1. Bagaimana arsitektur failover Anda mendistribusikan traffic secara cerdas ke cluster self-hosted vLLM cadangan yang menggunakan GPU Spot Instances di AWS/GCP tanpa mengalami Out-of-Memory (OOM) atau crash?
2. Bagaimana mekanisme *graceful degradation* agent Anda dalam memotong prompt chain agar dokumen legal tetap terproses dengan margin akurasi minimal 92% dan latency acceptable?
3. Rancang formula evaluasi ganti rugi (SLA credit claim) yang dapat diserahkan ke tim Legal untuk menuntut restitusi finansial ke provider Tier 1 atas kegagalan pemenuhan 99.9% availability contract.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara model perhitungan FinOps software tradisional dengan arsitektur LLM/Autonomous Agents?**
   * *Jawaban*: Software tradisional memiliki biaya komputasi deterministik per request, sedangkan agent berbasis LLM bersifat non-deterministik di mana token reasoning, tool calls, dan perulangan loop dinamis menentukan total konsumsi biaya.
2. **Apa yang dimaksud dengan "Reasoning Tokens" dan mengapa berpotensi merusak perencanaan anggaran FinOps?**
   * *Jawaban*: Reasoning tokens adalah token internal yang dihasilkan model saat fase "thinking" sebelum menghasilkan jawaban final. Token ini tidak selalu terlihat langsung di teks akhir namun tetap ditagih oleh penyedia LLM, sehingga estimasi biaya berbasis output visible akan meleset jauh.
3. **Mengapa rely pada billing dashboard bawaan cloud/vendor AI bulanan dianggap sebagai anti-pattern dalam produksi agent?**
   * *Jawaban*: Karena feedback loop-nya pasif dan memiliki latensi agregasi (data tertunda 2-24 jam). Saat tagihan membengkak terlihat di dashboard, insiden runaway cost sudah terlanjur terjadi dan dana telah hangus.
4. **Sebutkan metrik utama yang digunakan untuk menghitung Total Cost of Ownership (TCO) cluster GPU self-hosted (vLLM)!**
   * *Jawaban*: Biaya reservasi/sewa instance hardware GPU, utilitas VRAM, engineering maintenance overhead, data egress, storage weights/checkpoints, dan biaya listrik/pendingin jika on-premise.
5. **Apa fungsi utama dari Token Sliding-Window Circuit Breaker?**
   * *Jawaban*: Membatasi akumulasi biaya atau konsumsi token dalam jendela waktu tertentu (misal: 1 jam) dan memutus request seketika saat kuota terlampaui untuk mencegah kerugian finansial akibat infinite loop.

### Bagian 2: Intermediate (5 Pertanyaan)
1. **Bagaimana cara mendeteksi infinite execution loop pada autonomous agent sebelum circuit breaker gateway memotong koneksi?**
   * *Jawaban*: Menggunakan bounded-loop counters di framework agent, deteksi kesamaan semantik berulang pada chain history ($cosine\_similarity(step_{n}, step_{n-1}) > 0.98$), dan token ceiling thresholds per-session.
2. **Apa risiko teknis terbesar saat gateway melakukan fallback otomatis dari frontier model (e.g., Claude 3.5) ke open-weight model kecil (e.g., Llama 8B)?**
   * *Jawaban*: Kegagalan schema parsing tool/JSON, degradasi akurasi instruksi, halusinasi argumen fungsi, dan kegagalan menuruti *negative constraints* dalam system prompt.
3. **Bagaimana arsitektur Semantic Cache dapat menghemat biaya tanpa menyebabkan keusangan (*stale*) data analitik?**
   * *Jawaban*: Mengkombinasikan vector embedding similarity search dengan parameter TTL adaptif, cache invalidation tags berbasis entitas database, dan bypass flag untuk query yang membutuhkan *real-time retrieval*.
4. **Jelaskan perbedaan antara Provisioned Throughput Units (PTU) vs. Pay-As-You-Go dari sudut pandang Engineering Manager!**
   * *Jawaban*: PTU adalah model CapEx/Fixed-OpEx yang menjamin kapasitas komputasi dedicated dengan latensi konsisten tanpa rate-limiting, cocok untuk baseline traffic stabil. Pay-As-You-Go adalah pure OpEx variabel yang fleksibel untuk traffic berfluktuasi namun rentan terhadap *noisy neighbor* dan *throttling*.
5. **Bagaimana cara memverifikasi pemenuhan SLI/SLO ketersediaan vendor AI pihak ketiga secara objektif?**
   * *Jawaban*: Melakukan continuous synthetic probing independen dari multiple regions di luar jaringan vendor, mencatat P99 latency, HTTP status codes, dan validation errors secara internal, bukan hanya mengandalkan status page vendor.

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

#### Skenario 1: Vendor Outage & Cascading Failures
Sistem customer-support agent Anda bergantung pada Vendor X. Vendor X mengalami peningkatan error 500 hingga 30% dan P99 latency melonjak dari 800ms ke 12.000ms. Seluruh thread HTTP pool pada gateway backend Anda mengalami starvation dan API gateway utama perusahaan mulai tumbang (*cascading failure*).
*   **Pertanyaan**: *Langkah arsitektural darurat dan preventif apa yang harus diambil untuk mengisolasi gateway dalam hitungan detik?*
*   **Jawaban**: Aktifkan pattern *Bulkheading* dan *Circuit Breaker* (misal via Envoy atau code wrapper) dengan *strict timeout* diturunkan ke 2000ms. Buka circuit untuk Vendor X dan segera alihkan 100% traffic ke secondary vendor atau cluster vLLM internal. Kembalikan respons *graceful degradation* kepada pengguna jika kapasitas secondary terbatas.

#### Skenario 2: Token Runaway Incident
Sebuah agen data science internal dibiarkan berjalan semalaman untuk mengekstrak insight dari ribuan file CSV. Script agen mengalami error parser sehingga sistem terus mengirimkan traceback error 50.000 token berulang-ulang ke frontier model setiap 3 detik. Biaya membengkak $6.000 dalam 5 jam.
*   **Pertanyaan**: *Kontrol FinOps programmatic apa yang gagal bekerja dalam skenario ini dan bagaimana konfigurasi yang benar?*
*   **Jawaban**: Kegagalan ada pada ketiadaan **Per-Process Token Budgeting** dan **Input Sanitization Limiter**. Kontrol yang wajib dipasang: (1) Hardcap limit token input maksimum (misal: max 8k token per step), (2) Sliding window per-job budget limit ($5 per data processing batch), dan (3) Dead-man switch yang mematikan worker jika 3 error berulang berturut-turut terjadi.

#### Skenario 3: Penalti Pelanggaran SLA Vendor
Vendor AI Tier 1 Anda menjanjikan SLA uptime 99.9% per bulan. Pada bulan berjalan, terjadi degradasi performa selama total 4 jam di mana 40% request mengalami timeout. Vendor menolak klaim Service Credit Anda dengan alasan "Status Page menunjukkan sistem Operasional dan tidak terjadi full-outage".
*   **Pertanyaan**: *Sebagai Engineering Manager, instrumen teknis apa yang harus Anda ajukan untuk memenangkan sengketa klaim kontrak finansial tersebut?*
*   **Jawaban**: Serahkan data audit trail internal berupa telemetry log OpenTelemetry dan export Prometheus metrics yang mencakup: timestamped synthetic probe requests, client-side HTTP 5xx/timeout logs, distributed trace IDs, dan perbandingan baseline P99 latency. Buktikan bahwa degradasi tersebut secara efektif melanggar klausul *error rate threshold* yang tertera pada Service Level Agreement hukum kontrak enterprise Anda.

---

## 16. Summary

Mengelola autonomous agents dan sistem AI pada skala enterprise membutuhkan pergeseran paradigma dari rekayasa perangkat lunak tradisional menuju **Financial & Operational Resilience Engineering**. 

1. **FinOps Runtime Control**: Monitoring pasif bulanan adalah resep bencana; proteksi biaya wajib ditanamkan langsung pada arsitektur runtime melalui token budgeting, semantic caching, dan real-time sliding-window circuit breakers.
2. **Multi-Vendor Resiliency**: Hindari single-point-of-failure dengan membangun abstraction layer yang mampu melakukan routing dinamis dan failover otomatis antara proprietary frontier models dan self-hosted open-weight instances.
3. **Engineering Contract Governance**: Hubungan dengan vendor AI harus dikelola dengan pembuktian telemetri objektif. Jangan biarkan profitabilitas unit bisnis tergerus oleh *runaway agent loops* atau klaim performa sepihak dari upstream providers. Ketahanan sistem tercapai saat infrastruktur siap menghadapi kegagalan vendor kapan saja tanpa mengorbankan kontinuitas bisnis.