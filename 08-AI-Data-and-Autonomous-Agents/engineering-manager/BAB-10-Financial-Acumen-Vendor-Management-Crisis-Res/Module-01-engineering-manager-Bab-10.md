# Bab 10: Financial Acumen, Vendor Management, & Crisis Response
## Module 01: FinOps for AI Infrastructure, Unit Economics, & Token Budgeting Governance

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Engineering Manager (EM) dan Technical Lead diharapkan mampu:

*   **Menghitung dan Menganalisis Unit Economics AI:** Menentukan *Blended Cost per Task* (BCpT) dan *Cost of Goods Sold* (COGS) berbasis token, komputasi vektor, dan latensi inferensi untuk menjaga target *Gross Margin* produk AI minimal di angka 65–75%.
*   **Merancang dan Mengimplementasikan Token Governance Engine:** Membangun arsitektur *hierarchical budget enforcement* (Organization $\rightarrow$ Team $\rightarrow$ Agent $\rightarrow$ Run) dengan latensi evaluasi kuota $<5\text{ ms}$ pada *inference gateway*.
*   **Mengonfigurasi Autonomous Circuit Breaker:** Mengembangkan mekanisme deteksi anomali biaya dan pemutus sirkuit (*circuit breaker*) real-time yang mampu mendeteksi serta mematikan *infinite tool-use loops* dalam waktu $<3$ detik tanpa mengorbankan status transaksi yang sah.
*   **Mengevaluasi dan Menegosiasikan Kontrak Vendor AI:** Menyusun kerangka perbandingan TCO (*Total Cost of Ownership*) antara *Provisioned Throughput Units* (PTU/Reserved GPU), *Serverless Pay-As-You-Go* (PAYG), dan *Self-Hosted Open Weights* (vLLM/TGI pada kluster k8s terkelola), lengkap dengan mitigasi SLA/vendor lock-in.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Mengelola infrastruktur AI untuk sistem agen otonom (*autonomous agents*) berbeda secara fundamental dari mengelola sistem microservices tradisional. Pada layanan web konvensional, biaya marginal per permintaan (*marginal cost per request*) mendekati nol ($\approx \$0.00001$). Pada sistem berbasis Large Language Model (LLM) dan agen multi-langkah (*multi-step autonomous agents*), satu pemicu eksternal dapat mengeksekusi puluhan pemanggilan model, pencarian basis data vektor (*vector search*), dan evaluasi perkakas (*tool calling*), yang dapat mendorong biaya marginal melonjak hingga $\$0.10$–$\$2.00$ per tugas.

```
+-----------------------------------------------------------------------+
|                    AI FinOps Framework Lifecycle                     |
+-----------------------------------------------------------------------+
|  1. INFORM             |  2. OPTIMIZE           |  3. OPERATE         |
|  - Real-time Token Tagger- Smart Semantic Cache - Budget Gatekeeper   |
|  - Cost Attribution     - Model Distillation/    - Cost Circuit-Breaker|
|    (Org/Team/Feature)     Cascade Routing       - Automated Fallback  |
|  - Unit Margin Auditing - Dynamic Context Window- Quota Kill-Switches |
+------------------------+------------------------+---------------------+
```

#### Mental Model: The AI Unit Economics Pyramid
Untuk mengendalikan belanja komputasi tanpa mematikan inovasi fungsional, EM harus memegang tiga lapisan metrik biaya:

1.  **L1: Direct Token & Compute Cost (Raw COGS):** Biaya eksplisit vendor per 1 juta token masukan/keluaran ($P_{\text{in}}, P_{\text{out}}$) serta biaya *hardware-hour* GPU ($C_{\text{GPU}}$).
2.  **L2: Task-Level Blended Cost ($C_{\text{task}}$):** Total biaya seluruh siklus agen, mencakup *reasoning tokens*, *tool-calling retry penalties*, *context summarization*, dan *vector indexing retrieval overhead*.
3.  **L3: Business Value Unit ($V_{\text{unit}}$):** Rasio efisiensi biaya terhadap unit metrik bisnis, misalnya *Cost per Successfully Resolved Support Ticket* atau *Cost per Approved Code Pull Request*.

Jika $\frac{C_{\text{task}}}{V_{\text{unit}}} \ge \text{Target Gross Margin Threshold}$, maka fitur AI tersebut secara ekonomi tidak layak (*economically non-viable*) dan harus diturunkan (*downgraded*) ke model yang lebih hemat, atau dihentikan melalui mekanisme *kill-switch*.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Tanpa kontrol FinOps yang ketat di level gateway, organisasi rentan terhadap tiga risiko kritis:

*   **The Runaway Agent Catastrophe:** Sebuah *autonomous coding/research agent* terjebak dalam *cyclic dependency hallucination*. Dalam semalam, agen memanggil varian model reasoning penalaran tinggi secara rekursif hingga menghabiskan limit kredit vendor senilai $\$30,000$ hanya untuk satu tiket masalah (*issue ticket*).
*   **Gross Margin Evaporation:** Perusahaan SaaS meluncurkan fitur "Chat with Data" dengan skema harga langganan tetap ($49/pengguna/bulan). Tanpa batas kuota token semantik, 5% pengguna dengan volume data besar memicu inferensi berbiaya $\$300/pengguna/bulan$, menghancurkan margin kotor perusahaan dari 80% menjadi -40%.
*   **Vendor Lock-in & SLA Cascades:** Penyedia model tier-1 mengalami degradasi performa atau kenaikan tarif sepihak. Tanpa *abstracted routing layer* dan tata kelola kuota yang transparan antar-vendor, proses migrasi memerlukan *downtime* berminggu-minggu dan refactoring basis kode.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur di bawah ini menunjukkan bagaimana setiap permintaan inferensi diinspeksi, diperiksa anggarannya, dialihkan ke model yang paling efisien, dan diputus jalurnya secara otomatis jika terdeteksi lonjakan biaya abnormal.

```
+----------------------------------------------------------------------------------------------------+
|                                      Enterprise Client / Agent SDK                                 |
+----------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+----------------------------------------------------------------------------------------------------+
|                                    Inference Proxy & FinOps Gateway                                |
|                                                                                                    |
|  +------------------------+     +------------------------+     +--------------------------------+  |
|  | Request Interceptor    | --> | Dynamic Quota &        | --> | Semantic Routing Engine        |  |
|  | - Metadata Extraction  |     | Leaky-Bucket Limiter   |     | - Complexity Evaluator         |  |
|  | - Cost Allocation Tags |     | - Redis Hierarchical   |     | - Fallback/Downgrade Router    |  |
|  |   (Org/Project/Agent)  |     |   Counter Check        |     |   (Tier-1 / Tier-2 / Self-Host)|  |
|  +------------------------+     +------------------------+     +--------------------------------+  |
|                                             │                                  │                   |
|                                             │ (Breach Event)                   │ (Forward Request) |
|                                             ▼                                  ▼                   |
|  +-------------------------------------------------------+     +--------------------------------+  |
|  | FinOps Anomaly & Circuit Breaker Engine               |     | Unified Provider Adapter       |  |
|  | - Runaway Agent Detector (Loop/Cost Spike)            |     | - OpenAI / Anthropic / Bedrock |  |
|  | - Circuit Breaker State Machine (Closed/Open/Half)    |     | - Self-Hosted vLLM Cluster     |  |
|  +-------------------------------------------------------+     +--------------------------------+  |
+---------------------------------------------------------------------------------│------------------+
                                                                                  │
                       ┌──────────────────────────────────────────────────────────┴────────┐
                       ▼                                                                   ▼
+---------------------------------------------+                     +------------------------------------+
| Tier-1 Inference (e.g., Claude 3.5 Sonnet / |                     | Tier-2 Inference / Local Fallback  |
| OpenAI o1)                                  |                     | (e.g., Llama-3.3-70B via vLLM)     |
+---------------------------------------------+                     +------------------------------------+
                       │                                                                   │
                       └──────────────────────────┬────────────────────────────────────────┘
                                                  ▼
+----------------------------------------------------------------------------------------------------+
|                                  Post-Inference Accounting Engine                                  |
|  - Real Token Usage Extraction (Prompt + Completion + Reasoning Tokens)                            |
|  - Real-time Balance Ledger Reconciliation (Redis Lua Script)                                      |
|  - Prometheus Metrics Exporter & OpenTelemetry Trace Injection (cost_usd, tokens_total)             |
+----------------------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1. Formula Matematika AI Unit Economics

Total biaya per siklus eksekusi agen ($C_{\text{agent}}$) dihitung secara komprehensif menggunakan formula:

$$C_{\text{agent}} = \sum_{i=1}^{N} \left[ (T_{\text{in}, i} \cdot P_{\text{in}, m_i}) + (T_{\text{out}, i} \cdot P_{\text{out}, m_i}) \right] + \sum_{j=1}^{K} C_{\text{tool}, j} + \sum_{r=1}^{R} \left( \frac{D_{\text{dim}} \cdot V_{\text{read}} \cdot C_{\text{vector}}}{10^6} \right)$$

Dimana:
*   $N$: Jumlah langkah penalaran (*reasoning steps*) yang dieksekusi oleh agen.
*   $T_{\text{in}, i}, T_{\text{out}, i}$: Jumlah token input dan output pada langkah ke-$i$.
*   $P_{\text{in}, m_i}, P_{\text{out}, m_i}$: Biaya per token untuk model $m$ yang dipilih pada langkah ke-$i$.
*   $C_{\text{tool}, j}$: Biaya overhead eksekusi eksternal (misal: API pihak ketiga, *code execution sandbox environment*).
*   $D_{\text{dim}}$: Dimensi vektor pencarian RAG; $V_{\text{read}}$: Jumlah vektor yang dipindai; $C_{\text{vector}}$: Biaya pencarian basis data vektor per unit.

#### 5.2. Hierarchical Budget Allocation Algorithm
Sistem menerapkan pembatasan anggaran secara bertingkat:
1.  **Global Monthly Hard Cap:** Total anggaran komputasi organisasi.
2.  **Team/Project Allocation Pool:** Partisi dinamis dari batas global.
3.  **Agent Instance Burst Envelope:** Anggaran maksimal per sesi interaksi agen tunggal (mencegah *cost injection* atau *loop exploits*).

Pemeriksaan kuota menggunakan operasi atomik di Redis untuk menghindari *race conditions* saat ratusan agen paralel mengeksekusi inferensi secara bersamaan.

```
       [Global Organization Budget: $50,000/mo]
                          │
          ┌───────────────┴──────────────┐
          ▼                              ▼
[Engineering: $35,000]          [Customer Support: $15,000]
          │                              │
     ┌────┴─────┐                   ┌────┴─────┐
     ▼          ▼                   ▼          ▼
[Code Agent] [QA Agent]       [Triage Bot] [Escalation Bot]
 Max $2/run   Max $0.50/run   Max $0.05/run  Max $0.20/run
```

#### 5.3. Financial Circuit Breaker State Machine
Sirkuit proteksi keuangan beroperasi dengan 3 kondisi:
*   **CLOSED (Normal):** Permintaan diteruskan ke model target utama.
*   **OPEN (Tripped):** Jika pengeluaran dalam rentang waktu $\Delta t$ melampaui ambang batas anomali, sirkuit terbuka. Permintaan inferensi otomatis dibatalkan (*HTTP 429 / Budget Exceeded*) atau dialihkan secara paksa ke model lokal berbiaya rendah (*silent degradation*).
*   **HALF-OPEN (Recovery):** Setelah masa pendinginan (*cooldown window*), sistem meloloskan sampel kecil ($X\%$ permintaan) untuk mengevaluasi apakah rasio konsumsi token sudah kembali ke batas normal.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi **AI FinOps Gateway Core** menggunakan Python 3.11+, FastAPI, dan Redis. Kode ini mencakup validasi anggaran atomik via skrip Lua, kalkulasi biaya presisi tinggi, dan *Cost Anomaly Circuit Breaker*.

```python
# finops_gateway.py
from __future__ import annotations

import asyncio
from decimal import Decimal
from enum import Enum
import json
import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request, Depends, status

# Konfigurasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AIFinOpsGateway")

# --- MODEL KATALOG & PRICING REGISTRY (USD per 1,000 Tokens) ---
PRICING_TABLE: Dict[str, Dict[str, Decimal]] = {
    "claude-3-5-sonnet": {
        "input": Decimal("0.003000"),
        "output": Decimal("0.015000")
    },
    "gpt-4o": {
        "input": Decimal("0.002500"),
        "output": Decimal("0.010000")
    },
    "llama-3-3-70b-local": {
        "input": Decimal("0.000200"),
        "output": Decimal("0.000200")
    }
}

class CircuitBreakerStatus(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class InferenceRequestPayload(BaseModel):
    organization_id: str = Field(..., description="ID Tenant/Organisasi")
    project_id: str = Field(..., description="ID Proyek internal")
    agent_id: str = Field(..., description="ID instance agen otonom")
    model: str = Field(..., description="Model yang diminta")
    prompt: str = Field(..., description="Prompt masukan")
    estimated_max_output_tokens: int = Field(default=1024, ge=1, le=8192)

class UsageAccountingPayload(BaseModel):
    organization_id: str
    project_id: str
    agent_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int

# --- REDIS LUA SCRIPT: RESERVASI ANGGARAN ATOMIK ---
# Mencegah race condition ketika ribuan request konkuren tiba bersamaan.
LUA_BUDGET_RESERVATION_SCRIPT = """
local budget_key = KEYS[1]
local estimated_cost = tonumber(ARGV[1])
local current_balance = tonumber(redis.call('get', budget_key) or '0')

if current_balance >= estimated_cost then
    redis.call('decrby', budget_key, ARGV[1])
    return 1
else
    return 0
end
"""

class FinOpsGovernanceEngine:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.reservation_script_sha: Optional[str] = None

    async def initialize(self) -> None:
        """Mendaftarkan script Lua ke Redis server saat startup."""
        self.reservation_script_sha = await self.redis.script_load(
            LUA_BUDGET_RESERVATION_SCRIPT
        )
        logger.info(f"Lua script loaded with SHA: {self.reservation_script_sha}")

    def calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
        """Menghitung biaya aktual berdasarkan token dan model."""
        rates = PRICING_TABLE.get(model, PRICING_TABLE["llama-3-3-70b-local"])
        input_cost = (Decimal(prompt_tokens) / Decimal(1000)) * rates["input"]
        output_cost = (Decimal(completion_tokens) / Decimal(1000)) * rates["output"]
        return (input_cost + output_cost).quantize(Decimal("0.000001"))

    async def check_circuit_breaker(self, organization_id: str) -> CircuitBreakerStatus:
        """Memeriksa status proteksi lonjakan pengeluaran."""
        cb_key = f"finops:circuit:{organization_id}"
        state = await self.redis.get(cb_key)
        if not state:
            return CircuitBreakerStatus.CLOSED
        return CircuitBreakerStatus(state.decode("utf-8"))

    async def trip_circuit_breaker(self, organization_id: str, cooldown_seconds: int = 60) -> None:
        """Memutus sirkuit ketika terjadi anomali lonjakan biaya."""
        cb_key = f"finops:circuit:{organization_id}"
        await self.redis.set(cb_key, CircuitBreakerStatus.OPEN.value, ex=cooldown_seconds)
        logger.error(f"CIRCUIT BREAKER DITRIPPED untuk Organisasi: {organization_id} selama {cooldown_seconds} detik!")

    async def pre_flight_budget_check(
        self,
        org_id: str,
        model: str,
        estimated_max_output_tokens: int,
        prompt_char_len: int
    ) -> bool:
        """
        Estimasi konservatif sebelum inferensi diteruskan ke vendor.
        Asumsi kasar: 1 token ~= 4 karakter.
        """
        estimated_input_tokens = prompt_char_len // 4
        estimated_cost = self.calculate_cost(model, estimated_input_tokens, estimated_max_output_tokens)
        
        # Konversi biaya ke unit mikro (cents * 10,000) untuk komputasi integer atomik
        cost_micro_units = int(estimated_cost * Decimal(1_000_000))
        budget_key = f"finops:balance:{org_id}"

        # Eksekusi Lua script secara atomik
        is_allowed = await self.redis.evalsha(
            self.reservation_script_sha,
            1,
            budget_key,
            cost_micro_units
        )
        return bool(is_allowed)

    async def reconcile_actual_usage(self, usage: UsageAccountingPayload) -> Decimal:
        """
        Rekonsiliasi post-inference: menghitung selisih estimasi dengan
        penggunaan nyata lalu memperbarui data agregat pengeluaran.
        """
        actual_cost = self.calculate_cost(
            usage.model,
            usage.prompt_tokens,
            usage.completion_tokens
        )
        actual_micro_units = int(actual_cost * Decimal(1_000_000))
        
        # Simpan audit trail pengeluaran
        ledger_key = f"finops:ledger:{usage.organization_id}:{usage.project_id}"
        await self.redis.incrby(ledger_key, actual_micro_units)

        # Update rolling counter untuk deteksi runaway loop (per menit)
        velocity_key = f"finops:velocity:{usage.organization_id}:{usage.agent_id}"
        current_velocity = await self.redis.incrby(velocity_key, actual_micro_units)
        await self.redis.expire(velocity_key, 60)

        # Ambang batas Runaway Loop: $5.00 dalam 60 detik per agen
        MAX_PER_MINUTE_MICRO = int(Decimal("5.00") * Decimal(1_000_000))
        if current_velocity > MAX_PER_MINUTE_MICRO:
            await self.trip_circuit_breaker(usage.organization_id, cooldown_seconds=120)

        logger.info(
            f"Ledger Reconciled: Agent={usage.agent_id}, Model={usage.model}, "
            f"Tokens={usage.prompt_tokens + usage.completion_tokens}, Cost=${actual_cost}"
        )
        return actual_cost


# --- API GATEWAY INITIALIZATION ---
app = FastAPI(title="AI FinOps Governance Gateway", version="1.0.0")
redis_pool: Optional[aioredis.Redis] = None
governance_engine: Optional[FinOpsGovernanceEngine] = None

@app.on_event("startup")
async def on_startup():
    global redis_pool, governance_engine
    redis_pool = aioredis.from_url("redis://localhost:6379", decode_responses=False)
    governance_engine = FinOpsGovernanceEngine(redis_pool)
    await governance_engine.initialize()

@app.on_event("shutdown")
async def on_shutdown():
    if redis_pool:
        await redis_pool.close()

def get_engine() -> FinOpsGovernanceEngine:
    if not governance_engine:
        raise RuntimeError("Governance Engine belum terinisialisasi.")
    return governance_engine


@app.post("/v1/inference/proxy", status_code=status.HTTP_200_OK)
async def proxy_inference(
    payload: InferenceRequestPayload,
    engine: FinOpsGovernanceEngine = Depends(get_engine)
) -> Dict[str, Any]:
    """
    Reverse proxy endpoint dengan verifikasi kuota dan circuit breaker.
    """
    # 1. Cek Kondisi Circuit Breaker
    cb_status = await engine.check_circuit_breaker(payload.organization_id)
    if cb_status == CircuitBreakerStatus.OPEN:
        logger.warning(f"Akses ditolak: Sirkuit FinOps terbuka untuk {payload.organization_id}")
        # Strategi Degradasi: fallback ke model hemat lokal otomatis
        payload.model = "llama-3-3-70b-local"
    
    # 2. Pre-flight Atomic Reservation
    has_budget = await engine.pre_flight_budget_check(
        org_id=payload.organization_id,
        model=payload.model,
        estimated_max_output_tokens=payload.estimated_max_output_tokens,
        prompt_char_len=len(payload.prompt)
    )
    if not has_budget:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="FinOps Policy Breach: Kuota anggaran tidak mencukupi untuk estimasi eksekusi ini."
        )

    # 3. Simulasi Eksekusi Inferensi ke Provider LLM
    # Dalam produksi, gunakan httpx/aiohttp client ke upstream (Anthropic/OpenAI)
    simulated_prompt_tokens = len(payload.prompt) // 4
    simulated_completion_tokens = 150  # Simulasi hasil generate

    # 4. Post-execution Actual Cost Reconciliation
    actual_cost = await engine.reconcile_actual_usage(
        UsageAccountingPayload(
            organization_id=payload.organization_id,
            project_id=payload.project_id,
            agent_id=payload.agent_id,
            model=payload.model,
            prompt_tokens=simulated_prompt_tokens,
            completion_tokens=simulated_completion_tokens
        )
    )

    return {
        "status": "success",
        "model_served": payload.model,
        "circuit_breaker_status": cb_status.value,
        "tokens_evaluated": {
            "prompt": simulated_prompt_tokens,
            "completion": simulated_completion_tokens,
            "total": simulated_prompt_tokens + simulated_completion_tokens
        },
        "cost_incurred_usd": str(actual_cost),
        "output": "Simulated generation response completed successfully."
    }
```

---

### 7. Edge Cases & Failure Modes

*   **Streaming Inference Abort (Client Disconnect):** 
    *   *Problem:* Klien memutus koneksi HTTP saat streaming baru berjalan 10% (misal 50 token dari 2000 token output). Provider tetap menagih token yang sempat tergenerasi di memori GPU.
    *   *Mitigasi:* Tangani event `request.is_disconnected()` pada FastAPI/ASGI handler. Gunakan *SSE chunk counters* untuk mencatat token aktual sebelum soket ditutup dan segera rekonisiliasikan saldo, alih-alih mengasumsikan batas maksimal alokasi.
*   **Split-Brain Redis Budget Registry:**
    *   *Problem:* Partisi jaringan pada Redis Sentinel/Cluster menyebabkan dua node master mengizinkan mutasi anggaran secara terpisah, memungkinkan overspending hingga 200%.
    *   *Mitigasi:* Gunakan Redis Redlock atau konsolidasi master terpusat dengan persistensi `AOF` (*Append Only File*) `fsync everysec`. Konfigurasikan fallback *Fail-Closed* untuk inferensi tier-1 jika koneksi ke state store Redis terputus.
*   **Reasoning Token Shadow Costs (e.g., OpenAI o1/o3, DeepSeek R1):**
    *   *Problem:* Token *internal chain-of-thought* disembunyikan dari teks final tetapi tetap ditagihkan sebagai token keluaran (*completion tokens*). Hal ini menyebabkan deviasi estimasi awal (*pre-flight estimation*) menjadi 5–10× lebih rendah dibanding tagihan faktual.
    *   *Mitigasi:* Terapkan pengali keamanan (*safety multiplier*) dinamis sebesar $4.0\times$ untuk model-model reasoning pada tahap pre-flight check.

---

### 8. Trade-offs & Alternatif Solusi

| Strategi Pendekatan | Kelebihan | Kekurangan | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **Serverless Pay-As-You-Go (PAYG)** | Nol *idle cost*, skalabilitas instan tanpa manajemen hardware. | Biaya marginal tinggi pada volume tinggi ($>100\text{M tokens/hari}$), rentan *rate-limit* (HTTP 429). | Fase eksplorasi fitur, POC, dan beban kerja dengan lalu lintas fluktuatif/tidak terduga. |
| **Provisioned Throughput Units (PTU / Reserved)** | Latensi terjamin (konsisten), throughput terisolasi, diskon biaya pada utilisasi stabil $>80\%$. | Komitmen kontrak finansial jangka panjang (1–12 bulan), penalti biaya ekstrem jika kapasitas *idle*. | Core production enterprise dengan volume konsisten dan stabil sepanjang waktu. |
| **Self-Hosted Open-Weights (vLLM on k8s GPU)** | Privasi data absolut, bebas biaya margin vendor API, kustomisasi penuh arsitektur inferensi. | Beban operasional MLOps tinggi, overhead biaya cold-start GPU kluster, *hardware supply chain constraint*. | Entitas perbankan/medis dengan compliance ketat dan tim platform matang. |
| **Pre-Flight Estimation vs. Post-Hoc Auditing** | Pre-flight menjamin *zero over-budget risk*; Post-hoc meminimalkan *latency overhead* pada *hot-path*. | Pre-flight menambah latensi internal $\approx 3-5\text{ ms}$; Post-hoc berisiko *spending overrun* sebelum sempat dihentikan. | Gunakan Pre-Flight untuk autonomous agent berisiko tinggi; gunakan Post-Hoc untuk *low-latency consumer chat*. |

---

### 9. Best Practices & Standard Industri

1.  **Mandatory Fine-Grained Cost Tagging:** Setiap permintaan inferensi LLM harus membawa atribut OpenTelemetry span berikut:
    *   `ai.organization.id`
    *   `ai.project.id`
    *   `ai.agent.run_id`
    *   `ai.model.provider`
    *   `ai.tokens.prompt`
    *   `ai.tokens.completion`
2.  **Tiered Model Degradation Cascades:** Terapkan hirarki model otomatis:
    *   *Tier-1:* Complex Reasoning / Architecture (e.g., Claude 3.5 Sonnet / GPT-4o)
    *   *Tier-2:* Routine Transformations / Extraction (e.g., Llama-3.3-70B / Mistral-Small)
    *   *Tier-3:* Deterministic Code / Regex / Local Embedding
3.  **Vendor Negotiation Levers:**
    *   Selalu negosiasikan struktur kontrak berbasis komitmen bertingkat (*Tiered Commitment Discount*) dengan opsi *Burstable Ceiling*.
    *   Pastikan Service Level Agreement (SLA) vendor mencakup klausul *Latency P99 guarantees* dan penalti kompensasi (*service credits*) jika error rate HTTP 5xx atau 429 melampaui $0.05\%$ per bulan.

---

### 10. Hands-on Lab Exercise

#### Skenario: Menghentikan Runaway Agent dengan FinOps Circuit Breaker
Sebagai Engineering Manager, Anda menemukan bug pada sistem agen baru yang masuk ke kondisi rekursif tak terbatas. Anda harus menguji ketahanan FinOps Gateway untuk memutus loop tersebut sebelum menghabiskan saldo organisasi.

#### Langkah 1: Siapkan Lingkungan & Redis
Jalankan instance Redis lokal dan pastikan Python dependencies terinstal:

```bash
docker run -d --name finops-redis -p 6379:6379 redis:7-alpine
pip install fastapi uvicorn redis pydantic
```

#### Langkah 2: Suntikkan Modal Awal Organisasi
Inisialisasi saldo organisasi `org-acme-corp` sebesar $\$10.00$ (disimpan dalam micro-units: $\$10.00 \times 1,000,000 = 10,000,000$ unit):

```bash
docker exec -it finops-redis redis-cli SET "finops:balance:org-acme-corp" 10000000
```

#### Langkah 3: Jalankan Gateway
Simpan implementasi Python di bagian 6 sebagai `finops_gateway.py` dan jalankan servernya:

```bash
uvicorn finops_gateway:app --host 0.0.0.0 --port 8000 --reload
```

#### Langkah 4: Simulasikan Serangan Runaway Loop (Eksploitasi)
Jalankan skrip bash untuk mengirim lonjakan *rapid requests* secara simultan guna memicu threshold sirkuit:

```bash
#!/usr/bin/env bash
echo "Memulai simulasi Runaway Loop..."
for i in {1..35}
do
   curl -s -X POST http://localhost:8000/v1/inference/proxy \
        -H "Content-Type: application/json" \
        -d '{
              "organization_id": "org-acme-corp",
              "project_id": "auto-crawler",
              "agent_id": "agent-rogue-007",
              "model": "claude-3-5-sonnet",
              "prompt": "Analyze this recursively and generate an extensive breakdown of internal memories...",
              "estimated_max_output_tokens": 1024
            }' | grep -o '"circuit_breaker_status":"[^"]*"' || echo "Failed"
   sleep 0.1
done
```

#### Langkah 5: Evaluasi Hasil & Verifikasi Circuit Breaker
1.  Periksa log terminal server: Anda akan melihat pesan peringatan `CIRCUIT BREAKER DITRIPPED`.
2.  Amati respon cURL: Gateway secara instan mengubah status dari `CLOSED` menjadi `OPEN`, dan mengalihkan pemanggilan downstream ke fallback model lokal (`llama-3-3-70b-local`), sehingga menghentikan pengurasan modal organisasi.
3.  Audit saldo tersisa di Redis:
    ```bash
    docker exec -it finops-redis redis-cli GET "finops:balance:org-acme-corp"
    ```
    Konfirmasikan bahwa saldo tidak pernah menyentuh nilai minus ($<0$).