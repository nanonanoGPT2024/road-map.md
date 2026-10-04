# Bab 08: Go-To-Market Strategy & Product-Led Growth
## Module 01: AI-First PLG Architecture, Telemetry, and Product-Qualified Account (PQA) Engine

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Product Manager (PM) teknis diharapkan mampu:
- **Menganalisis & Mengurangi Time-to-First-Agentic-Action (TTFAA):** Menurunkan latensi onboarding pengguna dari pendaftaran hingga eksekusi tugas otonom pertama yang berhasil (success outcome) di bawah 180 detik.
- **Merancang Unit Economics Engine untuk PLG AI:** Mengkalkulasi *Cost of Goods Sold* (COGS) berbasis inferensi (tokens, compute, vector queries) terhadap *Customer Acquisition Cost* (CAC) untuk mempertahankan *Gross Margin* minimum 65% pada *free-tier/reverse trial*.
- **Mengembangkan Algoritma Product-Qualified Account (PQA):** Membangun model skoring heuristik dan probabilistik untuk mendeteksi kesiapan ekspansi *enterprise* berdasarkan telemetri penggunaan agent, variasi integrasi alat (*tools*), dan kolaborasi *multi-tenant*.
- **Menerapkan Guardrail Arsitektur Quota & Rate-Limiting:** Mengimplementasikan kontrol kuota berbasis token dan eksekusi dinamis guna mencegah *runaway loop costs* dari agent liar tanpa merusak *user experience*.
- **Mengevaluasi Model Monetisasi AI:** Mengoperasikan transisi strategis antara *seat-based*, *consumption-based (token/compute)*, dan *outcome-based pricing*.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Product-Led Growth (PLG) tradisional (misal: Slack, Zoom, Figma) berakar pada prinsip: **Marginal Cost of Free Users $\approx \$0$**. Pengguna tambahan dapat mencoba produk secara gratis tanpa beban infrastruktur signifikan bagi perusahaan.

Pada produk **AI & Autonomous Agents**, paradigma ini runtuh:
$$\text{Marginal Cost of Free Agent Execution} = \text{LLM Inference} + \text{Vector Storage} + \text{Tool Execution Compute} + \text{Egress Network} > \$0$$

```
TRADITIONAL PLG vs. AI-FIRST AGENT PLG

[Traditional SaaS PLG]
User Signup ──> Free Access ──> Habitual Usage ──> Marginal Cost = $0 ──> Upgrade Prompt

[AI-First Agent PLG]
User Signup ──> Agent Task ──> Recursive LLM Loops ──> High Token/GPU Cost ($$$)
                     │
                     ▼
          Risk: Runaway Inference Cost before "Aha!" Moment
```

Oleh karena itu, PM AI harus beralih ke mental model **Constrained Autonomous PLG**:
1. **Value Before Exhaustion:** Pengguna harus mencapai *Agentic Aha! Moment*—yaitu saat agent berhasil menyelesaikan tugas multi-langkah (bukan sekadar merespons teks *chat*)—sebelum kuota gratis habis.
2. **Reverse Trial dengan Circuit Breaker:** Memberikan kemampuan model tertinggi (misal: GPT-4o, Claude 3.5 Sonnet) dengan batasan kuota komputasi ketat, lalu menurunkan (*fallback*) ke *lightweight distilled models* (misal: Llama-3-8B) saat batas penggunaan tercapai, alih-alih memutus akses secara biner.
3. **Data Flywheel Retention:** Retensi tidak dibangun di atas data historis statis, melainkan pada *Shared Agent Memory* (vektor profil, evaluasi eksekusi, integrasi alat perusahaan). Semakin sering agent dieksekusi, semakin kontekstual performanya (*compounding switching cost*).

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Di pasar Enterprise AI modern, kegagalan terbesar adopsi produk otonom disebabkan oleh dua ekstrem:
1. **GTM Sales-Led Usang:** Enterprise menolak menandatangani kontrak 6-digit untuk "AI Agents" yang belum teruji keandalannya (*vaporware fatigue*). Mereka menuntut *proof-of-value* langsung di lingkungan kerja mereka.
2. **PLG Naif:** Startup AI yang membuka akses tanpa batas mengalami kebangkrutan karena *inference cost blowout* akibat pengguna anonim mengeksploitasi agent untuk tugas komputasi berat (*token farming* atau *scraping* tak terkendali).

Enterprise membutuhkan produk AI yang menawarkan:
- **Zero-Friction Sandbox:** Kemampuan mengeksekusi integrasi nyata (GitHub, Jira, Salesforce) secara instan tanpa panggilan sales manual.
- **Deterministic Billing Transparency:** Prediktabilitas biaya sebelum beralih dari fase uji coba ke produksi.
- **Product-Qualified Account (PQA) Routing:** Mengidentifikasi secara otomatis ketika sebuah tim kecil di dalam perusahaan Fortune 500 mulai menghubungkan data sensitif dan mencapai limit produktivitas, menandakan waktu yang tepat bagi tim *Sales-Assist* untuk masuk dengan penawaran Enterprise Grade (SLA, VPC peering, SOC2, SSO).

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah arsitektur *event-driven* untuk sistem GTM Telemetry, Quota Management, dan PQA Engine pada platform Autonomous Agent:

```
+-----------------------------------------------------------------------------------+
|                                  CLIENT LAYER                                     |
|  [ Web UI / CLI / SDK / Slack Bot ]                                               |
+------------------------------------------+----------------------------------------+
                                           |
                                           | API Requests (Task Execution)
                                           v
+-----------------------------------------------------------------------------------+
|                        API GATEWAY & TELEMETRY INGESTION                          |
|  - Rate Limiter (Token Bucket)                                                    |
|  - Tenant / Organization Context Extraction                                       |
|  - OpenTelemetry Tracing Injection (trace_id, org_id, agent_id)                   |
+------------------------------------------+----------------------------------------+
                                           |
                   +-----------------------+-----------------------+
                   | Forward Task                                  | Async Telemetry
                   v                                               v
+--------------------------------------+       +------------------------------------+
|         AGENT RUNTIME ENGINE         |       |        REAL-TIME EVENT BUS         |
|  - Planner (ReAct / Plan-and-Solve)  |       |        (Apache Kafka / Redpanda)   |
|  - Tool Invoker (APIs, Code Exec)    |       +-----------------+------------------+
|  - LLM Gateway (Semantic Caching)    |                         |
+------------------+-------------------+                         | Stream Events
                   |                                             v
                   | Execution Metrics         +------------------------------------+
                   | (Tokens, Latency, Tool)   |      TELEMETRY STREAM PROCESSOR    |
                   +-------------------------->|      (Apache Flink / Faust)        |
                                               +-----------------+------------------+
                                                                 |
                                       +-------------------------+------------------+
                                       | Aggregated Metrics                         | Dynamic Rules
                                       v                                            v
+------------------------------------------------------+   +------------------------+
|             USAGE & QUOTA STATE STORE                |   |       PQA ENGINE       |
|             (Redis Cluster / DynamoDB)               |   |  - Task Success Rate   |
|  - Org Token Spend Ledger                            |   |  - Tool Diversity      |
|  - Runaway Loop Detector Circuit Breaker             |   |  - Seat Expansion      |
+------------------------------------------------------+   +-----------+------------+
                                                                       | PQA Alert
                                                                       v
                                                           +------------------------+
                                                           |   CRM & REV-OPS SYNC   |
                                                           | (HubSpot / Salesforce) |
                                                           +------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. The PQA Scoring Engine (Algoritma Kualifikasi Akun)
Berbeda dengan MQL (Marketing Qualified Lead) yang berbasis demografis, PQA diturunkan murni dari telemetri perilaku penggunaan AI Agent.

Indeks PQA dihitung menggunakan bobot komposit:
$$\text{PQA Score} = w_1 \cdot \mathcal{A}_{\text{completion}} + w_2 \cdot \mathcal{T}_{\text{diversity}} + w_3 \cdot \mathcal{S}_{\text{velocity}} + w_4 \cdot \mathcal{U}_{\text{utilization}}$$

Dimana:
- **$\mathcal{A}_{\text{completion}}$ (Task Completion Quality):** Rasio tugas otonom yang diselesaikan tanpa intervensi manual (Human-in-the-Loop abort). Menandakan *true value adoption*.
- **$\mathcal{T}_{\text{diversity}}$ (Tool Breadth Index):** Entropi atau jumlah konektor eksternal yang diotorisasi (misal: Postgres + Jira + GitHub). Mengindikasikan integrasi mendalam ke alur kerja enterprise.
- **$\mathcal{S}_{\text{velocity}}$ (Seat/Invitee Velocity):** Laju pertambahan pengguna internal baru dalam organisasi yang sama (domain email terverifikasi) dalam window 7 hari.
- **$\mathcal{U}_{\text{utilization}}$ (Quota Consumption Curve):** Derivatif konsumsi kuota $\frac{d(\text{Tokens})}{dt}$. Konsumsi eksponensial menandakan automasi skala tim, bukan eksplorasi kasual.

#### B. Dynamic Agentic Circuit Breakers (Anti-Cost Blowout)
Untuk melindungi unit economics saat masa trial:
1. **Recursion Depth Hard-Capping:** Membatasi loop penalaran ReAct maksimum (misal: 10 iterasi) untuk free users.
2. **Model Degradation Cascading:** Jika penggunaan organisasi melewati 80% kuota harian gratis, router inferensi secara otomatis mengarahkan *sub-agent non-kritis* (seperti text summarizer) ke model open-source berbiaya rendah, menjaga model frontier hanya untuk modul *planning*.
3. **Loop Detection Heuristic:** Menghentikan eksekusi jika agent memanggil tool yang sama dengan parameter identik $>3$ kali berturut-turut tanpa perubahan state.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi *PQA Scoring & Quota Enforcement Engine* menggunakan Python modern (Python 3.11+), Pydantic v2, dan pola arsitektur *Clean Pipeline*. Modul ini mengevaluasi telemetri agent secara real-time dan mengklasifikasikan akun untuk ekspansi sales.

```python
"""
Core GTM & Telemetry Engine for AI Autonomous Agents
Architecture: Domain-Driven Design / Event-Driven Telemetry Processor
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field, field_validator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GTMTelemetryEngine")


class TenantTier(str, enum.Enum):
    FREE_SANDBOX = "FREE_SANDBOX"
    REVERSE_TRIAL = "REVERSE_TRIAL"
    PRODUCT_QUALIFIED = "PRODUCT_QUALIFIED"
    ENTERPRISE = "ENTERPRISE"


class AgentExecutionEvent(BaseModel):
    """Payload telemetri yang dipancarkan oleh runtime agent setelah satu run selesai."""
    event_id: str
    organization_id: str
    user_id: str
    agent_id: str
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    tools_invoked: List[str] = Field(default_factory=list)
    iterations_count: int = Field(ge=1)
    is_success: bool
    human_interrupted: bool
    execution_time_ms: int = Field(ge=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("tools_invoked")
    @classmethod
    def normalize_tools(cls, v: List[str]) -> List[str]:
        return [tool.strip().lower() for tool in v]


@dataclass
class OrganizationState:
    """State agregasi telemetri organisasi yang disimpan dalam in-memory cache / Redis."""
    org_id: str
    tier: TenantTier = TenantTier.FREE_SANDBOX
    total_tokens_consumed: int = 0
    token_budget: int = 1_000_000  # Default sandbox budget
    unique_users: Set[str] = field(default_factory=set)
    connected_tools: Set[str] = field(default_factory=set)
    successful_runs: int = 0
    failed_runs: int = 0
    pqa_score: float = 0.0
    is_flagged_for_sales: bool = False


class QuotaExceededException(Exception):
    """Exception yang dilemparkan ketika batas inferensi terlampaui."""
    pass


class CircuitBreakerException(Exception):
    """Exception untuk mendeteksi anomali loop eksekusi."""
    pass


class PQAEngine:
    """Engine untuk kalkulasi Product Qualified Account dan penegakan guardrails biaya."""

    # Bobot Heuristik PQA
    WEIGHT_SUCCESS: float = 0.30
    WEIGHT_TOOL_BREADTH: float = 0.25
    WEIGHT_COLLABORATION: float = 0.25
    WEIGHT_CONSUMPTION: float = 0.20

    PQA_THRESHOLD: float = 0.72

    def __init__(self, quota_limit: int = 500_000) -> None:
        self._org_registry: Dict[str, OrganizationState] = {}
        self.default_quota = quota_limit

    def get_or_create_org(self, org_id: str) -> OrganizationState:
        if org_id not in self._org_registry:
            self._org_registry[org_id] = OrganizationState(
                org_id=org_id,
                token_budget=self.default_quota
            )
        return self._org_registry[org_id]

    def validate_pre_execution_guardrails(self, org_id: str, estimated_tokens: int) -> None:
        """Memvalidasi kuota sebelum model LLM dipanggil."""
        org = self.get_or_create_org(org_id)

        if org.tier == TenantTier.ENTERPRISE:
            return  # Enterprise memiliki batasan soft/post-billing

        if org.total_tokens_consumed + estimated_tokens > org.token_budget:
            logger.warning(f"Org {org_id} exceeded token allocation. Quota: {org.token_budget}")
            raise QuotaExceededException(
                f"Token budget exhausted for Organization: {org_id}. Upgrade to Enterprise."
            )

    def process_execution_telemetry(self, event: AgentExecutionEvent) -> OrganizationState:
        """Ingest telemetri, deteksi loop runaway, dan hitung ulang status PQA."""
        org = self.get_or_create_org(event.organization_id)

        # 1. Runaway Circuit Breaker Heuristic
        if event.iterations_count > 15 and not event.is_success:
            logger.error(f"Runaway loop anomaly detected on agent {event.agent_id} in Org {org.org_id}")
            raise CircuitBreakerException("Agent execution aborted: Recursive iteration ceiling breached.")

        # 2. Update In-Memory Metrics
        tokens_this_run = event.prompt_tokens + event.completion_tokens
        org.total_tokens_consumed += tokens_this_run
        org.unique_users.add(event.user_id)
        org.connected_tools.update(event.tools_invoked)

        if event.is_success and not event.human_interrupted:
            org.successful_runs += 1
        else:
            org.failed_runs += 1

        # 3. Calculate Normalized Sub-metrics
        total_runs = org.successful_runs + org.failed_runs
        success_ratio = (org.successful_runs / total_runs) if total_runs > 0 else 0.0

        # Normalisasi metrik (Min-Max bounded [0.0, 1.0])
        tool_breadth_score = min(len(org.connected_tools) / 5.0, 1.0)  # Saturation di 5 enterprise tools
        collab_score = min(len(org.unique_users) / 4.0, 1.0)          # Saturation di 4 active seats
        consumption_score = min(org.total_tokens_consumed / org.token_budget, 1.0)

        # 4. Compute Weighted PQA Score
        org.pqa_score = (
            (self.WEIGHT_SUCCESS * success_ratio) +
            (self.WEIGHT_TOOL_BREADTH * tool_breadth_score) +
            (self.WEIGHT_COLLABORATION * collab_score) +
            (self.WEIGHT_CONSUMPTION * consumption_score)
        )

        # 5. Evaluate Expansion Readiness
        if org.pqa_score >= self.PQA_THRESHOLD and not org.is_flagged_for_sales:
            org.is_flagged_for_sales = True
            org.tier = TenantTier.PRODUCT_QUALIFIED
            self._trigger_sales_assisted_handshake(org)

        logger.info(
            f"Telemetri Diperbarui: Org={org.org_id} | Score={org.pqa_score:.2f} | "
            f"Tokens={org.total_tokens_consumed}/{org.token_budget} | PQA_Flagged={org.is_flagged_for_sales}"
        )
        return org

    def _trigger_sales_assisted_handshake(self, org: OrganizationState) -> None:
        """Memancarkan webhook / event ke sistem CRM (HubSpot/Salesforce)."""
        logger.info(
            f">>> [WEBHOOK OUTBOUND] PQA TRIGGERED: Org '{org.org_id}' "
            f"mencapai PQA Score {org.pqa_score:.2f} dengan {len(org.unique_users)} seats terhubung."
        )


# ============================================================================
# Driver Execution Test
# ============================================================================
if __name__ == "__main__":
    engine = PQAEngine(quota_limit=100_000)
    mock_org = "org_enterprise_acme"

    # Simulasi Rangkaian Event Penggunaan Bertahap
    telemetry_samples = [
        # Penggunaan Awal (Single User, tugas sederhana)
        AgentExecutionEvent(
            event_id="evt_01",
            organization_id=mock_org,
            user_id="user_alice",
            agent_id="agent_code_reviewer",
            prompt_tokens=5000,
            completion_tokens=1500,
            tools_invoked=["github"],
            iterations_count=3,
            is_success=True,
            human_interrupted=False,
            execution_time_ms=2300,
        ),
        # Ekspansi Kolaborasi (Multi-seat, tool bertambah)
        AgentExecutionEvent(
            event_id="evt_02",
            organization_id=mock_org,
            user_id="user_bob",
            agent_id="agent_db_analyst",
            prompt_tokens=25000,
            completion_tokens=8000,
            tools_invoked=["github", "postgresql", "slack"],
            iterations_count=6,
            is_success=True,
            human_interrupted=False,
            execution_time_ms=5600,
        ),
        # Penggunaan Lanjutan (Konsumsi token tinggi, pengguna ketiga bergabung)
        AgentExecutionEvent(
            event_id="evt_03",
            organization_id=mock_org,
            user_id="user_charlie",
            agent_id="agent_infra_ops",
            prompt_tokens=40000,
            completion_tokens=12000,
            tools_invoked=["aws_cli", "datadog", "slack"],
            iterations_count=8,
            is_success=True,
            human_interrupted=False,
            execution_time_ms=9200,
        ),
    ]

    for telemetry in telemetry_samples:
        try:
            engine.validate_pre_execution_guardrails(
                telemetry.organization_id, 
                telemetry.prompt_tokens + telemetry.completion_tokens
            )
            state = engine.process_execution_telemetry(telemetry)
        except (QuotaExceededException, CircuitBreakerException) as e:
            logger.error(f"Guardrail triggered execution rejection: {e}")
```

---

### 7. Edge Cases & Failure Modes

| Edge Case / Failure Mode | Root Cause Teknis | Dampak Bisnis / GTM | Mitigasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Runaway Looping Agents** | LLM ReAct loop gagal mengurai output parser tool, memicu pengulangan tanpa batas. | Membakar token trial dalam hitungan menit; tagihan komputasi provider membengkak. | Implementasikan *Max Loop Ceiling* di API Gateway level dan deteksi duplikasi *action fingerprint*. |
| **PQA False Positive via Failure Spamming** | Pengguna menjalankan agent yang gagal berulang kali sehingga konsumsi token melonjak artifisial. | Sales menghubungi akun yang frustrasi, bukan akun yang siap beli (merusak reputasi sales). | Penalti kuadratik pada skor PQA: Bobot konsumsi token dikalikan dengan kuadrat *Task Completion Ratio*. |
| **Inference Cold-Start Churn** | Agent dengan multi-step reasoning membutuhkan waktu $>60$ detik pada eksekusi pertama. | Drop-off pada *activation funnel*; pengguna mengira sistem *hung*. | Tampilkan *Streaming Thought Execution Logs* via Server-Sent Events (SSE) agar waktu tunggu terisi visualisasi kognitif agent. |
| **Context Window Cache Poisoning** | Free user mengunggah berkas sampah besar untuk menguji limit RAG. | Latensi vector search naik, membebani shared-tenant vector database. | Terapkan batas ukuran file per tier, batasi *chunk parsing*, dan isolasi *free tier collections* di vector store. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan monetisasi dan onboarding pada agent otonom membawa konsekuensi operasional yang radikal:

```
                      GTM MONETIZATION SPECTRUM
                      
   Seat-Based (SaaS Lama)       Consumption (Tokens)        Outcome-Based (Masa Depan)
<─────────────────────────────┼─────────────────────────────┼─────────────────────────────>
• Prediktabilitas Enterprise  • Selaras dengan Cost Cloud   • Nilai bisnis absolut
• Membatasi viralitas agent   • Prediktabilitas rendah      • Sangat sulit diverifikasi
• Disinsentif otonomi penuh   • Margin terjamin             • Risiko sengketa tinggi
```

#### Komparasi Strategi Onboarding Model AI

| Dimensi | Freemium Tradisional | Time-Bound Reverse Trial | Credit-Based Sandbox (Direkomendasikan) |
| :--- | :--- | :--- | :--- |
| **Mekanisme** | Fitur terbatas, selamanya gratis. | Akses fitur Enterprise selama 14 hari, lalu diturunkan. | Diberikan saldo kredit komputasi (misal: \$20 token credit). |
| **Gross Margin Risk** | **Sangat Tinggi:** Biaya inferensi berulang tanpa batas waktu. | **Sedang:** Dibatasi oleh durasi waktu, namun rentan lonjakan dalam 14 hari. | **Terkontrol Penuh:** Kerugian maksimal per user terkunci secara deterministik sebesar alokasi kredit. |
| **Time-to-Value (TTV)** | Lambat; model yang digunakan biasanya lambat/lemah. | Cepat; user langsung mengakses performa agent tier tertinggi. | Sangat Cepat; fleksibilitas mencoba model frontier hingga kredit habis. |
| **Konversi Sales** | Rendah ($<2\%$). | Tinggi ($5\% - 8\%$). | Sangat Tinggi ($8\% - 14\%$) jika dipadukan dengan PQA Telemetry. |

---

### 9. Best Practices & Standard Industri

1. **Progressive Autonomous Disclosure:**
   Jangan langsung memberi agent kontrol penuh di awal onboarding. Terapkan level otonomi bertahap:
   - *Level 1 (Copilot):* Agent memberi rekomendasi rencana aksi; manusia menyetujui setiap klik/alat.
   - *Level 2 (Semi-Autonomous):* Agent mengeksekusi sub-task baca (*read-only*), meminta persetujuan untuk mutasi (*write/delete*).
   - *Level 3 (Fully Autonomous):* Eksekusi *end-to-end* tanpa interupsi, diaktifkan hanya setelah pengguna memvalidasi minimal 5 tugas di Level 2.
2. **Reverse Proxy Masking & Cost Governance:**
   Gunakan gateway seperti LiteLLM atau Cloudflare AI Gateway untuk abstraksi provider. Terapkan *budgeting* otomatis per *API Key/User ID* di level proksi, bukan di level aplikasi inti.
3. **Data-Privacy First Tiering:**
   Pada produk AI, fitur enterprise terkuat bukan sekadar *seat management*, melainkan **Zero Data Retention (ZDR)**. Terapkan strategi GTM di mana *data exclusion from LLM training* menjadi pemicu ekspansi dari Free ke Tier Berbayar.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda adalah Principal PM di startup AI yang membangun **"DevOps Incident Autonomous Agent"**. Produk Anda memiliki fitur di mana agent masuk ke sistem log (Datadog), mendeteksi *stack trace*, menulis *patch code*, dan membuat *Pull Request* otomatis. Anda ditugaskan merancang strategi PLG dan menguji PQA Scoring Engine secara lokal.

#### Langkah 1: Setup Lingkungan
Pastikan Python 3.10+ terpasang, lalu siapkan virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # atau venv\Scripts\activate pada Windows
pip install pydantic
```

#### Langkah 2: Buat Skrip Simulasi Telemetri
Simpan implementasi kode dari Bagian 6 ke dalam berkas bernama `pqa_telemetry_engine.py`.

#### Langkah 3: Eksekusi Kasus Uji Ekstrem (Edge Cases)
Tambahkan blok pengujian berikut di bagian akhir berkas untuk memvalidasi proteksi *cost blowout*:

```python
# Tambahkan ke pqa_telemetry_engine.py

def run_stress_tests():
    print("\n--- RUNNING STRESS TEST: CIRCUIT BREAKER DETECTION ---")
    test_engine = PQAEngine(quota_limit=50_000)
    abusive_org = "org_malicious_script"

    runaway_event = AgentExecutionEvent(
        event_id="evt_anomaly_01",
        organization_id=abusive_org,
        user_id="user_bot",
        agent_id="agent_recursive_crawler",
        prompt_tokens=1000,
        completion_tokens=200,
        tools_invoked=["web_scraper"],
        iterations_count=20, # Melewati batas 15 iterasi
        is_success=False,
        human_interrupted=False,
        execution_time_ms=45000
    )

    try:
        test_engine.process_execution_telemetry(runaway_event)
        print("TEST FAILED: Runaway loop lolos tanpa interupsi!")
    except CircuitBreakerException as e:
        print(f"TEST PASSED: Circuit Breaker Berhasil Menghentikan Agent: {e}")

    print("\n--- RUNNING STRESS TEST: EXHAUSTION GUARDRAIL ---")
    try:
        # Mencoba request token di atas sisa kuota (Budget: 50.000, Request: 60.000)
        test_engine.validate_pre_execution_guardrails(abusive_org, estimated_tokens=60000)
        print("TEST FAILED: Quota breach tidak terdeteksi!")
    except QuotaExceededException as e:
        print(f"TEST PASSED: Pre-execution validation memblokir inferensi: {e}")

if __name__ == "__main__":
    run_stress_tests()
```

#### Langkah 4: Verifikasi Output
Jalankan skrip:
```bash
python pqa_telemetry_engine.py
```
**Ekspektasi Hasil:**
1. Engine mencatat telemetri dan memicu log `[WEBHOOK OUTBOUND] PQA TRIGGERED` ketika akumulasi metrik mencapai ambang batas $\ge 0.72$.
2. Uji *stress test* memicu `TEST PASSED` untuk kedua skenario batas (*Circuit Breaker* pada iterasi liar dan *Quota Exceeded* sebelum eksekusi).

#### Langkah 5: Tugas Analisis PM (Deliverable Mandiri)
Tulis *Product Requirement Document (PRD)* mini sepanjang 1 halaman yang merumuskan:
- Ambang batas metrik PQA spesifik untuk vertikal produk Anda (Metrik apa yang membuktikan agent memberikan *real economic value*?).
- Skema *soft-gate* ketika kredit token sandbox pengguna tersisa 10% (Teks modal, trigger UX, dan insentif ekspansi ke paket Enterprise).