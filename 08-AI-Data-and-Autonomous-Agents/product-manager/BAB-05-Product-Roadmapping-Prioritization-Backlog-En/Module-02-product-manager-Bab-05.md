# BAB 05: Product Roadmapping, Prioritization, & Backlog Engineering
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Technical Product Manager (AI/Data PM), AI Architect, dan Engineering Lead diharapkan mampu:
- **Merancang Arsitektur Backlog Berbasis Evaluasi (*Evaluation-Driven Backlog Engineering - EDBE*)**: Memetakan kapabilitas agen otonom dan sistem data non-deterministik ke dalam hierarki *Epics*, *Spikes*, dan *Eval Gates*.
- **Mengimplementasikan Kerangka Prioritisasi Probabilistik (*Probabilistic WSJF & RICE*)**: Menghitung *Cost of Delay* (CoD) dan estimasi nilai bisnis dengan memasukkan variabel ketidakpastian stokastik (*stochastic uncertainty*), risiko halusinasi, dan anggaran token/latensi.
- **Membangun Closed-Loop Telemetry to Backlog Engine**: Mengintegrasikan metrik observabilitas LLM/Agent (dari platform seperti Langfuse, Arize Phoenix, atau MLflow) secara otomatis ke dalam *ticketing system* (Linear/Jira) untuk *data-driven defect prioritization*.
- **Mengelola Kompromi Sistemik (*Systemic Trade-offs*)**: Menyeimbangkan *Context Window Precision*, *P99 Latency*, *Inference Cost (FLOPs/Token)*, dan *Safety Guardrails* dalam *production roadmap*.
- **Menetapkan *Definition of Ready* (DoR) dan *Definition of Done* (DoD) Spesifik AI**: Memastikan fitur agen AI tidak dianggap "selesai" hanya berdasarkan lulus uji deterministik fungsional, melainkan melewati ambang batas kuantitatif *Golden Dataset*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
1. **Dasar Manajemen Produk Perangkat Lunak**: Pemahaman mendalam mengenai Agile/Scrum, kanban, kalkulasi standard WSJF (*Weighted Shortest Job First*), dan metrik RICE.
2. **Prinsip Dasar Arsitektur AI/LLM**:
   - Konsep agen otonom (ReAct, Plan-and-Solve, Multi-Agent Swarms).
   - Metrik evaluasi model: Faithfulness, Answer Relevance, Context Recall, Semantic Drift, ROUGE, BLEU, dan G-Eval.
   - Paradigma RAG (*Retrieval-Augmented Generation*) dan *Vector Databases*.
3. **Rekayasa Perangkat Lunak & API**:
   - Pemahaman alur kerja Git, CI/CD pipelines, dan integrasi RESTful/GraphQL API.
   - Kemampuan dasar membaca dan mengeksekusi kode Python 3.10+ untuk otomasi backlog.

---

### 3. Concept & Internal Architecture (Mendalam)

Sistem perangkat lunak deterministik tradisional memiliki ruang status (*state space*) yang dapat diprediksi: untuk input $X$, output selalu $Y$. Sebaliknya, produk berbasis **Autonomous Agents & Large Language Models** beroperasi dalam ruang probabilitas tinggi: input $X$ dapat menghasilkan distribusi output $Y_1, Y_2, \dots, Y_n$ dengan deviasi reliabilitas dan variasi latensi. 

Oleh karena itu, arsitektur manajemen produk AI membutuhkan evolusi dari *Deterministic Feature Backlog* menuju **Stochastic Capability Backlog**.

```
+---------------------------------------------------------------------------------------+
|                 STOCHASTIC CAPABILITY BACKLOG ARCHITECTURE                            |
+---------------------------------------------------------------------------------------+
|                                                                                       |
|  [ BUSINESS VISION ]                                                                  |
|         │                                                                             |
|         ▼                                                                             |
|  [ AGENT MISSION EPIC ]  ──> Target: "Mengotomasi 85% Rekonsiliasi Faktur Pajak"      |
|         │                                                                             |
|         ├────────────────────────────────┬───────────────────────────────┐           |
|         ▼                                ▼                               ▼           |
|  [ DETERMINISTIC CAPABILITY ]   [ STOCHASTIC CAPABILITY ]      [ EVAL HARNESS SPIKE ] |
|  - OCR Parsing API              - ReAct Reasoning Tool         - Build Golden Dataset |
|  - DB Schema Validation         - LLM SQL Synthesizer          - Define Drift Metrics |
|  - ERP Webhook Integration      - Discrepancy Summarizer       - Set G-Eval Baselines |
|         │                                │                               │           |
|         └────────────────────────────────┼───────────────────────────────┘           |
|                                          ▼                                            |
|                  [ CI/CD EVALUATION GATEWAY (EVAL-GATE) ]                             |
|                  - Faithfulness >= 0.96                                              |
|                  - Tool Execution Accuracy >= 0.99                                   |
|                  - P95 Latency <= 2200ms                                             |
|                  - Token Budget <= $0.015 / request                                  |
|                                          │                                            |
|                     ┌────────────────────┴────────────────────┐                       |
|                     ▼                                         ▼                       |
|              [ PASS: MERGE ]                          [ FAIL: AUTO-TICKET ]           |
|         Release to Canary Stage                Create Defect Spike in Linear          |
|                                                (Auto-assigned with Trace ID)          |
+---------------------------------------------------------------------------------------+
```

#### Komponen Utama Arsitektur:

1. **Agent Mission Epic**: Lapisan abstraksi tertinggi yang berfokus pada hasil bisnis (*business outcome*), bukan implementasi model spesifik.
2. **Deterministic vs. Stochastic Backlog Partitioning**:
   - *Deterministic Backlog*: Komponen infrastruktur, skema basis data, integrasi middleware, dan auth/RBAC. Dikelola menggunakan Story Points standar.
   - *Stochastic Backlog*: Komponen logika agen, prompt engineering, RAG tuning, routing policy, dan tool selection. Dikelola menggunakan *Hypothesis-Driven Sprints*.
3. **Eval Harness Spikes**: Pra-syarat wajib sebelum stochastic story diimplementasikan. Menghasilkan *Golden Dataset* berlabel minimal 100–500 pasang input-output skenario dunia nyata untuk dijadikan *benchmarking harness*.
4. **CI/CD Eval Gate (Quality Gate)**: Gerbang otomatis berbasis metrik. Sebuah fitur agen tidak dapat berstatus *Done* jika evaluasi sintetis atau simulasi multi-turn gagal memenuhi batas ambang metrik yang telah disepakati oleh PM dan Tech Lead.

---

### 4. Why & What

#### Mengapa Metodologi Klasik Gagal untuk AI & Agen Otonom?
1. **Fluktuasi Akurasi Asimtotik**: Pada software tradisional, menambahkan kode umumnya menyelesaikan *bug* secara permanen. Pada agen LLM, memodifikasi prompt atau memperluas konteks untuk memperbaiki Edge Case A sering kali memicu regresi pada Kasus B, C, dan D (*Negative Transfer* atau *Prompt Fragility*).
2. **Biaya Non-Linier**: Penambahan fitur baru dapat melipatgandakan *token usage* dan waktu inferensi secara eksponensial jika agen terjebak dalam *infinite reasoning loop*.
3. **Erosi Reliabilitas Temporal (Data/Model Drift)**: Performa agen dapat menurun tanpa adanya perubahan kode aplikasi, semata-mata karena perubahan distribusi data input pengguna atau pembaruan minor dari penyedia *foundation model*.

#### Apa itu Evaluation-Driven Backlog Engineering (EDBE)?
EDBE adalah metodologi rekayasa backlog di mana setiap tiket fitur agen AI wajib memiliki:
- **Baseline Metric Target**: Ambang batas toleransi kuantitatif (misalnya: *Hallucination Rate* < 2%, *Tool Call Precision* > 98%).
- **Eval Dataset Reference**: Tautan langsung ke dataset pengetesan pada *artifact store*.
- **Cost & Latency Constraints**: Alokasi biaya maksimum per eksekusi sukses (misal: $\le \$0.03$) dan SLA responsivitas.

---

### 5. How (Workflow Detail)

Berikut adalah siklus hidup rekayasa prioritisasi dan pengelolaan backlog agen AI di tingkat produksi:

```
[ Step 1: Hypothesis & Constraint Definition ]
   - PM & Tech Lead mendefinisikan Agent Objective dan Performance Envelope (Budget, Latency, Accuracy).
   
[ Step 2: Golden Dataset Curation (Eval Spike) ]
   - Data Engineer & PM mengompilasi representasi data produksi dan skenario kegagalan kritis.

[ Step 3: Probabilistic WSJF Prioritization ]
   - Tim menghitung p-WSJF dengan menyertakan Uncertainty Penalty Factor.

[ Step 4: Iterative Engineering & Agent Tuning ]
   - Rekayasa Prompt, Implementasi RAG, Tuning Hyperparameter, Tool Registry Integration.

[ Step 5: Automated Eval Harness Execution in CI ]
   - Eksekusi model terhadap Golden Dataset via synthetic evaluator (misal: DeepEval / Ragas / G-Eval).

[ Step 6: Canary Deployment & Telemetry Ingestion ]
   - Rollout 5% traffic; Telemetry engine mendeteksi deviasi output, latency spike, atau negative feedback.

[ Step 7: Automated Feedback Loop to Backlog ]
   - Trace kegagalan otomatis ditransformasi menjadi Tiket Defect Berprioritas Tinggi di Linear/Jira.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Membangun software konvensional diibaratkan seperti **Membangun Jalan Tol Beton**:
Rencana konstruksi bersifat linier, material terukur pasti, dan setelah beton mengeras, jalan tersebut dipastikan dapat menahan beban kendaraan sesuai spesifikasi desain awal secara deterministik.

Membangun Agen Otonom diibaratkan seperti **Mengebor Sumur Minyak Lepas Pantai Berdasarkan Peta Seismik**:
Anda memiliki instrumen canggih dan data probabilitas, namun setiap pengeboran (*prompt/agent spike*) membawa ketidakpastian geologis (*stochastic response*). Anda tidak bisa hanya membuat jadwal kerja linier; Anda membutuhkan *contingency budget*, pengujian densitas kontinu di setiap meter pengeboran (*eval harness*), dan sistem pemutus darurat (*fallback/guardrails*) jika tekanan gas melebihi ambang batas aman.

#### Diagram Interaksi Sistem

```
+------------------+         +-----------------------+         +---------------------+
| Product Manager  |         | LLMOps / Telemetry    |         | CI/CD Pipeline      |
| & Engineering    |         | (Langfuse / OpenTel)  |         | (GitHub Actions)    |
+--------+---------+         +-----------+-----------+         +----------+----------+
         |                               |                                |
         | 1. Define Capability & Eval   |                                |
         |------------------------------>|                                |
         |                               |                                |
         | 2. Submit Feature Code (PR)   |                                |
         |--------------------------------------------------------------->|
         |                               |                                |
         |                               | 3. Run Golden Dataset Tests    |
         |                               |<-------------------------------|
         |                               |                                |
         |                               | 4. Return Accuracy & Cost Metr.|
         |                               |------------------------------->|
         |                               |                                |
         | 5. Gate Failed: Regresi Akurasi (< 95%)                        |
         |<---------------------------------------------------------------|
         |                               |                                |
         | 6. Telemetry Ingests Prod Outlier (Thumbs Down / Tool Fail)    |
         |                               |                                |
         | 7. Auto-generate Issue Ticket |                                |
         |<------------------------------|                                |
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Probabilistic WSJF Calculator (Python CLI)
Formula standar WSJF:
$$\text{WSJF} = \frac{\text{Cost of Delay (CoD)}}{\text{Job Size / Duration}}$$

Dalam pengembangan AI Stokastik, kita memperkenalkan **Uncertainty Risk Multiplier ($U_r$)** dan **Compliance/Safety Penalty ($C_s$)**:
$$\text{p-CoD} = (\text{User Value} + \text{Time Criticality} + \text{Risk Reduction}) \times C_s$$
$$\text{p-Job Size} = \text{Estimated Duration} \times (1 + U_r)$$
$$\text{p-WSJF} = \frac{\text{p-CoD}}{\text{p-Job Size}}$$

```python
#!/usr/bin/env python3
"""
Simple CLI: Probabilistic WSJF Calculator for Stochastic AI Features
"""
from dataclasses import dataclass

@dataclass
class AIFeatureCandidate:
    name: str
    user_business_value: float  # 1 - 10
    time_criticality: float     # 1 - 10
    risk_reduction: float       # 1 - 10
    estimated_sprints: float    # Base sprint duration
    uncertainty_score: float    # 0.0 (fully deterministic) to 1.5 (high R&D risk)
    safety_criticality: float   # 1.0 (standard) to 2.0 (high compliance impact)

    @property
    def probabilistic_cod(self) -> float:
        base_cod = self.user_business_value + self.time_criticality + self.risk_reduction
        return base_cod * self.safety_criticality

    @property
    def adjusted_job_size(self) -> float:
        return self.estimated_sprints * (1.0 + self.uncertainty_score)

    @property
    def p_wsjf(self) -> float:
        return round(self.probabilistic_cod / self.adjusted_job_size, 2)

if __name__ == "__main__":
    backlog = [
        AIFeatureCandidate("Deterministic Rule-based Fallback", 7, 8, 9, 2.0, 0.1, 1.2),
        AIFeatureCandidate("Multi-Agent Autonomous Negotiator", 10, 6, 4, 4.0, 1.4, 1.8),
        AIFeatureCandidate("Semantic Context Caching (Cost Optimizer)", 8, 5, 8, 1.5, 0.3, 1.0)
    ]

    print(f"{'Feature Name':<42} | {'p-CoD':<8} | {'p-Size':<8} | {'p-WSJF':<8}")
    print("-" * 74)
    for feat in sorted(backlog, key=lambda x: x.p_wsjf, reverse=True):
        print(f"{feat.name:<42} | {feat.probabilistic_cod:<8.1f} | {feat.adjusted_job_size:<8.2f} | {feat.p_wsjf:<8.2f}")
```

#### B. Practical Example: Enterprise Telemetry-to-Backlog Integration Engine
Implementasi produksi FastAPI service yang mengonsumsi Webhook observabilitas (misalnya dari sistem Tracing AI seperti Langfuse/Arize) saat mendeteksi kegagalan run agen secara berulang, menghitung kalkulasi prioritas berdasarkan dampak finansial, dan membuat *defect ticket* langsung ke Linear/Jira API.

```python
"""
Enterprise Telemetry-to-Backlog Engine
File: telemetry_backlog_bridge.py
"""
import os
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, Field
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TelemetryBacklogBridge")

app = FastAPI(title="AI Backlog Dynamic Ingestion Engine", version="1.0.0")

LINEAR_API_URL = "https://api.linear.app/graphql"
LINEAR_API_KEY = os.getenv("LINEAR_API_KEY", "mock_key")
ALERT_WEBHOOK_SECRET = os.getenv("ALERT_WEBHOOK_SECRET", "super-secret-auth-token")

class TraceFailurePayload(BaseModel):
    trace_id: str = Field(..., description="Unique Trace ID from OpenTelemetry/Langfuse")
    agent_id: str = Field(..., description="Identifier of the executing agent")
    failure_type: str = Field(..., description="e.g., ToolExecutionError, HallucinationDrift, LatencyViolation")
    severity: str = Field(..., description="LOW, MEDIUM, CRITICAL")
    user_impact_score: float = Field(..., ge=0.0, le=10.0, description="Estimated blast radius or user tier")
    token_waste_cost: float = Field(..., ge=0.0, description="Direct LLM dollar cost wasted in this trace")
    prompt_snippet: Optional[str] = None
    system_error_log: str

def verify_token(x_webhook_secret: str = Header(...)):
    if x_webhook_secret != ALERT_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized webhook trigger.")

class BacklogManager:
    @staticmethod
    def calculate_priority_score(payload: TraceFailurePayload) -> int:
        """
        Determines ticketing priority (1=Urgent, 2=High, 3=Normal, 4=Low)
        based on Stochastic Defect Impact formula.
        """
        severity_weight = {"LOW": 1.0, "MEDIUM": 2.5, "CRITICAL": 5.0}.get(payload.severity, 1.0)
        risk_index = (payload.user_impact_score * 0.6) + (severity_weight * 0.4)
        
        if payload.token_waste_cost > 5.0 or risk_index >= 4.0:
            return 1  # Urgent
        elif risk_index >= 2.5:
            return 2  # High
        elif risk_index >= 1.5:
            return 3  # Normal
        return 4      # Low

    @classmethod
    async def create_linear_issue(cls, payload: TraceFailurePayload, priority: int) -> Dict[str, Any]:
        title = f"[AI Defect - {payload.agent_id}] {payload.failure_type} on Trace {payload.trace_id[:8]}"
        description = (
            f"### Automated Stochastic Defect Report\n\n"
            f"- **Trace ID:** `{payload.trace_id}`\n"
            f"- **Agent Subsystem:** `{payload.agent_id}`\n"
            f"- **Failure Taxonomy:** `{payload.failure_type}`\n"
            f"- **Financial Impact:** `${payload.token_waste_cost:.4f}` wasted\n"
            f"- **Observed Logs:**\n```\n{payload.system_error_log}\n```\n\n"
            f"**Definition of Done:** Resolve defect and add prompt/input to Golden Dataset."
        )

        query = """
        mutation CreateIssue($title: String!, $description: String!, $priority: Int!) {
            issueCreate(input: {
                title: $title,
                description: $description,
                priority: $priority
            }) {
                success
                issue {
                    id
                    identifier
                    url
                }
            }
        }
        """
        variables = {"title": title, "description": description, "priority": priority}

        if LINEAR_API_KEY == "mock_key":
            logger.warning("Mock Mode: Issue creation skipped. Simulating success.")
            return {"success": True, "issue": {"id": "mock-123", "identifier": "AI-404", "url": "https://linear.app/mock"}}

        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": LINEAR_API_KEY, "Content-Type": "application/json"}
            response = await client.post(LINEAR_API_URL, json={"query": query, "variables": variables}, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Failed to communicate with Linear: {response.text}")
                raise HTTPException(status_code=502, detail="Upstream Task Manager Error")
            
            result = response.json()
            if "errors" in result:
                logger.error(f"GraphQL Errors: {result['errors']}")
                raise HTTPException(status_code=500, detail="Backlog GraphQL mutation failed.")
            return result["data"]["issueCreate"]

@app.post("/v1/telemetry/failure-trigger", dependencies=[Depends(verify_token)])
async def ingest_telemetry_failure(payload: TraceFailurePayload):
    try:
        calculated_priority = BacklogManager.calculate_priority_score(payload)
        ticket_result = await BacklogManager.create_linear_issue(payload, calculated_priority)
        
        logger.info(
            f"Successfully logged failure from trace {payload.trace_id} "
            f"as ticket {ticket_result['issue']['identifier']} with Priority {calculated_priority}"
        )
        return {
            "status": "PROCESSED",
            "issue_id": ticket_result["issue"]["id"],
            "issue_url": ticket_result["issue"]["url"],
            "assigned_priority": calculated_priority
        }
    except Exception as exc:
        logger.exception(f"Fatal processing telemetry event: {str(exc)}")
        raise HTTPException(status_code=500, detail=f"Internal Engine Error: {str(exc)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Bank Sentral Swasta Tier-1 — Autonomous Wealth Advisory Assistant
- **Skala Operasional**: 2,5 juta pengguna aktif bulanan, melayani rata-rata 120.000 kueri portofolio investasi per hari.
- **Tantangan Awal**: 
  - PM tim AI memprioritaskan fitur berdasarkan *User Voice* tradisional, berfokus menambahkan 15 tools eksternal baru (cek harga saham real-time, berita makro, laporan fundamental).
  - Hasil: Kompleksitas *reasoning* membengkak. *Tool Execution Hallucination* melonjak hingga 8,4% di produksi.
  - Dampak Finansial: Salah satu agen merekomendasikan restrukturisasi portofolio obligasi berisiko tinggi akibat kegagalan konteks temporal, memicu investigasi kepatuhan (*regulatory audit*).
- **Intervensi Arsitektur Backlog (Roadmap Restructuring)**:
  1. **Penghentian Fitur Baru (Feature Freeze)**: PM membatalkan 10 tiket fitur integrasi tool.
  2. **Implementasi EDBE**:
     - Dibangun *Golden Dataset* berisi 1.200 skenario kepatuhan OJK/SEC.
     - Setiap PR wajib melewati *CI Eval Gate* dengan metrik ketat: *Hallucination Rate* $\le 0.1\%$, *Context Precision* $\ge 0.98$.
  3. **Routing Architecture Spike**:
     - Backlog direorganisasi untuk membangun *Deterministic Intent Classifier* di depan LLM.
     - Kueri sederhana dialihkan ke algoritma deterministik; agen otonom hanya dipanggil jika kompleksitas portofolio memerlukan *multi-step reasoning*.
- **Hasil Terukur (Setelah 2 Kuartal)**:
  - Penurunan angka insiden kepatuhan hingga **0 insiden** selama 6 bulan berturut-turut.
  - Biaya inferensi bulanan turun sebesar **42%** karena penurunan utilisasi token yang tidak perlu.
  - P95 latency anjlok dari 6.8 detik menjadi 1.4 detik.

---

### 9. Trade-offs: Architectural & Roadmapping Matrix

Setiap keputusan prioritisasi pada agen otonom memiliki konsekuensi langsung terhadap operasional produksi. PM harus menavigasi matriks kompromi berikut:

| Pilihan Arsitektur / Backlog Focus | Latency Impact | Token Cost Impact | Accuracy / Safety | Developer Velocity | Kapan Harus Memilih? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Multi-Agent Orchestration (e.g., CrewAI / AutoGen)** | **Tinggi (Buruk)**<br>P95 > 8-15s | **Sangat Tinggi**<br>Eksponensial | **Tinggi**<br>(Refleksi mandiri) | **Rendah**<br>Sulit di-debug | Analisis mendalam asinkron (misal: Riset pasar mingguan otomatis). |
| **Single Agent + Dense Tool Schema** | **Sedang**<br>P95 ~ 3-5s | **Tinggi**<br>Context bloat | **Rentan**<br>Tool misdirection | **Tinggi**<br>Setup cepat | Prototipe awal / PoC internal skala terbatas. |
| **Deterministic Routing + Specialized SLM** | **Rendah (Optimal)**<br>P95 < 800ms | **Sangat Rendah**<br>Hemat FLOPs | **Sangat Tinggi**<br>Domain terisolasi | **Sedang**<br>Perlu fine-tuning SLM | Aplikasi *real-time customer facing* skala jutaan request/hari. |
| **Heavy Guardrails (Llama-Guard / NeMo)** | **Sedang-Tinggi**<br>+300-600ms overhead | **Sedang**<br>Double-inference | **Ekstrem**<br>Zero-tolerance safety | **Sedang**<br>Maintenance ruleset | Industri terikat regulasi ketat (Fintech, Healthcare, Legal). |

---

### 10. Common Mistakes & Troubleshooting

#### Anti-Pattern 1: Mengukur Progress Berdasarkan Story Points Tradisional
- **Gejala**: Tim menyelesaikan 50 Story Points per sprint, namun kepuasan pengguna (*CSAT*) anjlok dan tingkat kegagalan tugas agen di produksi meningkat.
- **Akar Masalah**: Poin diberikan untuk *menulis prompt* atau *menyambungkan tool*, bukan pada *peningkatan reliabilitas task completion*.
- **Solusi Troubleshooting**: Ganti metrik keberhasilan sprint dari *Velocity (Points)* menjadi *Delta Eval Score* ($\Delta \text{Task Completion Rate}$ pada Golden Dataset).

#### Anti-Pattern 2: The Sunk-Cost Prompting Rabbit Hole
- **Gejala**: Engineer menghabiskan 3 sprint berturut-turut merekayasa prompt 4.000 token untuk mencegah satu edge case tertentu.
- **Akar Masalah**: Mencoba menyelesaikan masalah non-linier deterministik hanya dengan rekayasa prompt.
- **Solusi Troubleshooting**: Terapkan aturan batas waktu (*Timebox Rule*): Jika modifikasi prompt tidak mencapai akurasi target dalam 3 hari, alihkan tiket ke pembuatan *Deterministic Pre-/Post-Processor* atau lakukan *Fine-Tuning* pada dataset representatif.

#### Anti-Pattern 3: Evaluasi Lepas-Tangan (*Vibe-Based Prioritization*)
- **Gejala**: Prioritas backlog ditentukan oleh komplain ad-hoc dari pimpinan eksekutif ("LLM kemarin salah jawab saat demo").
- **Akar Masalah**: Tidak adanya infrastruktur evaluasi berbasis metrik kuantitatif.
- **Solusi Troubleshooting**: Tolak tiket bug agen yang tidak menyertakan `Trace ID` produksi atau tidak dapat direplikasi dalam *Golden Dataset Test Harness*.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini pada setiap ritual *Backlog Refinement* dan *Sprint Planning*:

#### Definition of Ready (DoR) untuk Stochastic User Stories:
- [ ] Business Metric & Guardrail SLA terdefinisi secara numerik (misal: "Minimal 94% resolusi sukses tanpa intervensi manusia").
- [ ] Tersedia minimal 50 data uji (*baseline assertions*) yang mencakup skenario sukses, skenario adversarial (*prompt injection*), dan skenario data tidak lengkap.
- [ ] Anggaran biaya komputasi per transaksi telah ditetapkan (misal: Biaya LLM $\le \$0.02/\text{interaksi}$).
- [ ] Skema fallback telah disetujui (Apa yang terjadi jika LLM timeout atau mengembalikan output invalid?).

#### Definition of Done (DoD) untuk Stochastic User Stories:
- [ ] Kode terintegrasi dan lolos pengetesan deterministik (Unit Tests, Linter).
- [ ] Lolos *CI/CD Automated Eval Gate* terhadap *Golden Dataset* tanpa degradasi performa pada fitur sebelumnya (*no backward regression*).
- [ ] Latensi P95 dan P99 berada di bawah ambang batas SLA sistem.
- [ ] Konfigurasi prompt, model version, temperature, dan parameter sampling tercatat secara persisten (*version-controlled* di Git/MLflow, bukan hardcoded).
- [ ] Tracing dan logging observabilitas terpasang lengkap dengan tagging `tenant_id`, `model_version`, dan `prompt_hash`.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum ini di direktori: `hands-on/m02/`

#### Langkah 1: Siapkan Lingkungan Virtual
```bash
mkdir -p hands-on/m02
cd hands-on/m02
python3 -m venv venv
source venv/bin/activate
pip install pydantic pytest tabulate
```

#### Langkah 2: Buat Skrip Eval-Gate Simulator (`eval_gate.py`)
Skrip ini bertindak sebagai gerbang otomatis penilai kesiapan backlog sebelum *merge*.

```python
# hands-on/m02/eval_gate.py
import json
import sys

def run_eval_gate(benchmark_file: str, min_faithfulness: float, max_latency_p95: float):
    with open(benchmark_file, "r") as f:
        data = json.load(f)

    total_runs = len(data["runs"])
    avg_faithfulness = sum(r["faithfulness"] for r in data["runs"]) / total_runs
    latencies = sorted([r["latency_ms"] for r in data["runs"]])
    p95_latency = latencies[int(total_runs * 0.95)]

    print(f"=== EVAL GATE EXECUTION RESULTS ===")
    print(f"Total Evaluated Samples : {total_runs}")
    print(f"Observed Faithfulness   : {avg_faithfulness:.4f} (Min Required: {min_faithfulness})")
    print(f"Observed P95 Latency    : {p95_latency:.2f}ms (Max Allowed: {max_latency_p95}ms)")

    failures = []
    if avg_faithfulness < min_faithfulness:
        failures.append(f"Faithfulness below threshold: {avg_faithfulness:.4f} < {min_faithfulness}")
    if p95_latency > max_latency_p95:
        failures.append(f"P95 Latency violated: {p95_latency}ms > {max_latency_p95}ms")

    if failures:
        print("\n[RESULT: REJECTED FROM SPRINT DOD]")
        for err in failures:
            print(f" - ERROR: {err}")
        sys.exit(1)
    else:
        print("\n[RESULT: APPROVED FOR SPRINT DOD]")
        sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python eval_gate.py <results.json>")
        sys.exit(1)
    run_eval_gate(sys.argv[1], min_faithfulness=0.92, max_latency_p95=2000.0)
```

#### Langkah 3: Buat Mock Data Benchmark (`benchmark_sample.json`)
```json
{
  "runs": [
    {"run_id": "1", "faithfulness": 0.95, "latency_ms": 1200},
    {"run_id": "2", "faithfulness": 0.96, "latency_ms": 1400},
    {"run_id": "3", "faithfulness": 0.91, "latency_ms": 1100},
    {"run_id": "4", "faithfulness": 0.89, "latency_ms": 1950},
    {"run_id": "5", "faithfulness": 0.98, "latency_ms": 2500}
  ]
}
```

#### Langkah 4: Uji Eksekusi dan Verifikasi Kegagalan Gate
```bash
python eval_gate.py benchmark_sample.json
# Amati output: Skrip akan melempar exit code 1 karena rata-rata faithfulness atau latency P95 gagal melewati batas toleransi.
```

---

### 13. Exercise

#### Level 1 - Easy
Tuliskan 3 kriteria *Acceptance Criteria* (AC) bergaya BDD (*Given-When-Then*) untuk agen pembuat kueri SQL otomatis, dengan ketentuan wajib mencakup batasan keamanan (*read-only execution*) dan latensi.

#### Level 2 - Medium
Gunakan skrip `Simple CLI: Probabilistic WSJF Calculator` pada Seksi 7. Ubah perhitungannya agar memasukkan faktor **Token Unit Economics Variance**: Jika rasio estimasi biaya token terhadap estimasi pendapatan transaksi lebih dari 30%, kurangi prioritas p-WSJF secara dinamis sebesar 50%.

#### Level 3 - Hard
Rancang skema JSON Architecture untuk dokumen *Product Requirement Document* (PRD) agen otonom. Skema harus secara formal memvalidasi:
1. Matriks batas kesalahan (*error threshold limits*).
2. Mekanisme circuit breaker (kondisi kapan agen harus berhenti dan memanggil staf manusia).
3. Matriks fallback deterministik berjenjang (LLM $\to$ Semantic Cache $\to$ Static Rule-Engine).

---

### 14. Challenge

**Studi Kasus Ekstrem: Autonomous Diagnostic Triage Agent (Healthcare Platform)**

- **Konteks**: Anda memimpin tim produk AI untuk aplikasi triase medis darurat berkecepatan tinggi. Dokter jaga mengandalkan agen untuk merangkum riwayat rekam medis (EMR) dan memberikan skor keparahan pasien dalam waktu < 3 detik.
- **Kondisi Krisis**:
  - Model inferensi utama (Cloud-hosted LLM) mengalami *outage* intermiten dan lonjakan latensi P99 hingga 14 detik.
  - Terdapat laporan bahwa pada data pasien lanjut usia dengan multimorbiditas, agen melewatkan indikator kontraindikasi obat (*False Negative*) sebesar 3,2%.
  - Biaya API vendor LLM melonjak melampaui anggaran tahunan sebesar 180% pada kuartal berjalan.
- **Tugas Arsitektural**:
  Buat **Rencana Mitigasi Backlog Darurat (*Emergency Sprint Architecture*)** untuk 2 sprint ke depan:
  1. Tentukan urutan prioritas antara: Keamanan Klinis, Kepatuhan Regulasi, Reduksi Latensi, dan Efisiensi Biaya Token. Gunakan kerangka kuantitatif.
  2. Rancang arsitektur transisi: Bagaimana Anda membagi tanggung jawab komputasi antara SLM lokal (pada jaringan internal rumah sakit) dan Foundation Model eksternal?
  3. Definisikan metrik *Circuit Breaker* absolut yang secara otomatis menonaktifkan agen dan mengalihkan 100% alur ke triage konvensional tanpa menyebabkan kekacauan antrean rumah sakit.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Pemahaman Konseptual Dasar
1. Mengapa estimasi *Story Points* standar industri (deret Fibonacci) sering kali tidak akurat jika diterapkan secara langsung pada *prompt engineering* atau pengembangan kapabilitas agen otonom?
   - A. Karena insinyur AI bekerja lebih lambat dibanding web developer konvensional.
   - B. Karena ruang pencarian non-deterministik dan sifat regresi stokastik membuat kompleksitas debugging tidak berbanding lurus dengan baris kode.
   - C. Karena Scrum master tidak memahami matematika dasar dari Large Language Models.
   - D. Karena komputasi GPU selalu memiliki durasi waktu pengerjaan yang berubah-ubah di cloud.

2. Apa yang dimaksud dengan *Golden Dataset* dalam siklus rekayasa backlog AI?
   - A. Kumpulan data penjualan bernilai paling tinggi di dalam data warehouse perusahaan.
   - B. Dataset berisi token API berbayar tinggi untuk mengakses GPT-4 atau Claude 3.5 Sonnet.
   - C. Himpunan data uji berlabel yang dikurasi secara ketat dan diverifikasi kebenarannya untuk mengevaluasi metrik akurasi agen secara obyektif di CI/CD.
   - D. Hasil scraping data publik yang telah dibersihkan dari seluruh duplikasi baris.

3. Dalam adaptasi *Probabilistic WSJF*, faktor penyesuaian apa yang wajib ditambahkan pada penyebut (*Job Size / Duration*)?
   - A. GPU Core Frequency Multiplier.
   - B. Stochastic Uncertainty Score.
   - C. Total Parameter Size of the Foundation Model.
   - D. Daily API Rate Limits.

4. Manakah di bawah ini yang merupakan contoh kriteria *Definition of Done* (DoD) spesifik AI yang valid?
   - A. "Prompt telah dibaca dan disetujui oleh Senior PM."
   - B. "Tingkat halusinasi agen berada di bawah 1% berdasarkan evaluasi otomatis pada 500 kasus uji Golden Dataset."
   - C. "Model berhasil dijalankan di komputer lokal developer tanpa pesan error."
   - D. "Kode Python ditulis menggunakan paradigma pemrograman berorientasi objek."

5. Apa risiko utama arsitektur agen jika PM memprioritaskan penambahan terlalu banyak *Tools* ke dalam satu LLM Agent secara bersamaan?
   - A. Basis data SQL akan kehabisan ruang penyimpanan index.
   - B. Terjadinya degradasi penalaran (*reasoning degradation*), latensi membengkak, dan tingginya probabilitas pemilihan tool yang salah (*Tool Misdirection*).
   - C. Compiler Python tidak mampu mengeksekusi fungsi secara asinkron.
   - D. Tidak ada risiko teknis, LLM modern dapat menangani ribuan tools tanpa batasan kapasitas.

#### Bagian B: Analisis Menengah
6. Sebuah tim produk mengamati metrik: Akurasi agen meningkat dari 91% ke 97% setelah menggunakan teknik *Chain-of-Thought (CoT)* multi-step, namun latensi P95 melonjak dari 1,8 detik menjadi 9,2 detik. Sebagai PM sistem perbankan real-time, tindakan prioritisasi backlog apa yang paling rasional?
   - A. Menolak rilis CoT ke produksi dan membuat Spike untuk mengeksplorasi *Speculative Decoding*, *Model Distillation*, atau *Deterministic Semantic Routing*.
   - B. Langsung merilis ke produksi karena akurasi adalah satu-satunya metrik absolut yang diperhatikan nasabah.
   - C. Mengurangi kapasitas server basis data untuk mengimbangi lonjakan latensi jaringan.
   - D. Menghapus seluruh guardrails validasi keamanan perbankan untuk menghemat 200ms latensi.

7. Mengapa pengujian unit (*Unit Testing*) berbasis mock konvensional tidak cukup untuk menyatakan sebuah *Stochastic Agent Epic* telah selesai?
   - A. Karena pengujian unit tradisional memakan terlalu banyak ruang memori CPU.
   - B. Karena pengujian unit hanya memvalidasi determinisme alur logika pemanggilan fungsi, bukan kualitas, kepatuhan semantik, atau potensi bias dari respons probabilistik LLM.
   - C. Karena model bahasa tidak dapat dipanggil melalui antarmuka bahasa pemrograman modern.
   - D. Karena unit test tidak mendukung format pertukaran data JSON.

8. Dalam penghitungan *Cost of Delay* (CoD) fitur agen AI, apa dampak mengabaikan *Safety Guardrail Spike* pada sistem yang berinteraksi langsung dengan publik?
   - A. Penurunan performa kartu grafis server sebesar 15%.
   - B. Potensi kerugian finansial masif, tuntutan hukum, dan kerusakan reputasi merek akibat serangan *Adversarial Prompt Injection* atau pelanggaran privasi data.
   - C. Kegagalan fungsi integrasi web-hook ke aplikasi Jira.
   - D. Penurunan rasio token compression pada context window.

9. Apa perbedaan esensial antara *Spike: Exploratory Prompting* dan *Spike: Golden Dataset Generation*?
   - A. Exploratory Prompting bertujuan mencari tahu kapabilitas teoritis model, sedangkan Golden Dataset Generation bertujuan membangun tolok ukur pengujian kuantitatif yang objektif.
   - B. Exploratory Prompting dikerjakan oleh Data Analyst, sedangkan Golden Dataset dibuat oleh Tim Sales.
   - C. Tidak ada perbedaan nyata; keduanya hanya istilah administratif dalam Scrum.
   - D. Exploratory Prompting berfokus pada efisiensi biaya GPU, sedangkan Golden Dataset berfokus pada antarmuka UI.

10. Sistem observabilitas mencatat bahwa 15% respons agen ditolak oleh pengguna dengan menekan tombol *thumbs down*. Apa langkah teknis pertama yang harus diambil PM dalam siklus backlog?
    - A. Meminta tim marketing mengirimkan survei kepuasan pelanggan melalui email.
    - B. Mengisolasi trace log dari 15% kegagalan tersebut, mengelompokkannya berdasarkan taksonomi kegagalan (halusinasi, nada bicara, latensi, tool error), dan memasukkannya ke Golden Dataset sebagai pengetesan regresi baru.
    - C. Mengganti seluruh arsitektur backend dari Python ke Rust.
    - D. Menghapus tombol *thumbs down* dari antarmuka aplikasi.

#### Bagian C: Skenario Kasus Produksi
11. **Skenario Kasus 1**: Tim Anda sedang mengembangkan *Code Refactoring Autonomous Agent*. Data produksi menunjukkan bahwa pada repositori besar (> 50.000 baris kode), agen mengalami kegagalan *out-of-memory* pada context window atau memotong sintaks kode penting (*hallucinated omission*). 
    *Pertanyaan*: Tentukan item arsitektur backlog mana yang harus diprioritaskan pada sprint berikutnya untuk memecahkan masalah ini secara struktural dengan biaya terendah:
    - A. Beralih ke model komersial termahal dengan context window 2 Juta token tanpa mengubah arsitektur.
    - B. Membangun fitur *AST (Abstract Syntax Tree) Chunking Parser Spike* yang memecah dependensi kode secara deterministik sebelum diserahkan ke agen dengan konteks terisolasi.
    - C. Menginstruksikan pengguna untuk tidak menggunakan agen pada repositori berukuran besar.
    - D. Menambahkan lebih banyak memori RAM pada server hosting container aplikasi.

12. **Skenario Kasus 2**: Anda adalah PM sistem e-Commerce AI Agent. Menjelang festival belanja akhir tahun (*Black Friday / 11.11*), estimasi lonjakan lalu lintas adalah 10x lipat. Vendor Foundation Model mengonfirmasi adanya *Hard Concurrency Rate Limit* sebesar 100 RPS pada organisasi Anda. 
    *Pertanyaan*: Solusi backlog teknis mana yang wajib Anda prioritaskan untuk mencegah kegagalan sistem total pada hari pelaksanaan?
    - A. Menerapkan antrean pesan (Message Queue) dengan Semantic Caching deterministik (Redis + Embeddings) dan fallback bertingkat ke Static FAQ / Classic Search.
    - B. Meminta engineer untuk melakukan bypass rate-limit menggunakan skrip multithreading paralel tak terbatas.
    - C. Menonaktifkan sistem otentikasi login pengguna agar beban server berkurang.
    - D. Membeli 50 akun developer publik dari penyedia foundation model secara acak.

13. **Skenario Kasus 3**: Tim data science menyarankan migrasi dari LLM closed-source berbasis API ke *Self-Hosted Open-Source SLM (e.g., Llama-3-8B)* yang telah di-fine-tune untuk memangkas biaya operasional jangka panjang. Namun, fine-tuning membutuhkan waktu 6 sprint dan akurasi baseline pada general knowledge 12% lebih rendah dari model API saat ini.
    *Pertanyaan*: Bagaimana formula keputusan roadmapping yang paling tepat secara arsitektural?
    - A. Menolak ide Data Science secara permanen karena model API tertutup selalu lebih unggul.
    - B. Melakukan migrasi langsung 100% pada sprint berikutnya dan membiarkan pengguna beradaptasi dengan penurunan akurasi demi penghematan biaya perusahaan.
    - C. Membuat *Dual-Track Spike*: Pertahankan model API untuk kueri kompleks (*Zero-Shot Reasoning*), sambil secara bertahap menerapkan *Shadow Deployment* (membandingkan inferensi SLM lokal vs API secara paralel di background) dan memvalidasinya terhadap Golden Dataset hingga akurasi mencapai paritas yang diizinkan sebelum pengalihan lalu lintas produksi.
    - D. Mengganti target produk dari Autonomous Agent menjadi aplikasi CRUD statis biasa.

---

### Kunci Jawaban & Pembahasan Quiz

#### Bagian A: Dasar
1. **Jawaban: B**. Pengembangan sistem AI non-deterministik dipenuhi oleh ambiguitas stokastik. Perbaikan satu edge case pada prompt/model dapat memicu regresi performa tak terduga pada domain lain, sehingga korelasi linier jam kerja developer dengan *story points* klasik runtuh.
2. **Jawaban: C**. *Golden Dataset* adalah kumpulan data uji acuan kebenaran (*ground truth*) komprehensif yang digunakan untuk mengevaluasi kualitas output probabilitas sistem AI secara repeatable dan terukur.
3. **Jawaban: B**. Ketidakpastian stokastik (*Stochastic Uncertainty Score*) merefleksikan risiko R&D eksploratif pada fitur AI, sehingga estimasi durasi riil pekerjaan harus ditingkatkan proporsional terhadap ketidakpastian tersebut.
4. **Jawaban: B**. DoD untuk fitur stokastik wajib berpatokan pada ambang batas metrik performa kuantitatif objektif, bukan sekadar opini atau kesuksesan kompilasi kode deterministik.
5. **Jawaban: B**. Mengisi konteks model dengan terlalu banyak skema definisi tool meningkatkan kebingungan agen (*attention distraction*), melipatgandakan latensi pemrosesan input token, dan memperbesar probabilitas halusinasi eksekusi tool.

#### Bagian B: Menengah
6. **Jawaban: A**. Lonjakan latensi ke 9,2 detik tidak dapat diterima pada platform perbankan interaktif *real-time*. Tim harus mencari jalur arsitektur alternatif yang mempertahankan akurasi tanpa mengorbankan SLA performa secara ekstrem.
7. **Jawaban: B**. Unit test konvensional memvalidasi kabel infrastruktur (apakah objek terinisialisasi, apakah fungsi terpanggil), namun sama sekali buta terhadap apakah teks atau keputusan yang dihasilkan oleh LLM relevan, halusinasi, atau melanggar kebijakan sistem.
8. **Jawaban: B**. Pada sistem publik, ketiadaan guardrails berisiko tinggi memicu kebocoran data rahasia (*PII leak*), injeksi prompt yang mengambil alih kontrol agen, atau saran berbahaya yang berujung pada konsekuensi legalitas dan kebangkrutan reputasi.
9. **Jawaban: A**. *Exploratory Prompting* adalah aktivitas kualitatif untuk memahami batasan kapabilitas model, sedangkan *Golden Dataset Generation* adalah pembangunan infrastruktur metrik kuantitatif terstandarisasi untuk validasi berkelanjutan.
10. **Jawaban: B**. Pendekatan EDBE menuntut agar umpan balik negatif di produksi langsung ditransformasi menjadi artefak pengujian (*eval cases*), sehingga akar penyebab kegagalan dapat direplikasi dan diukur perbaikannya di masa depan.

#### Bagian C: Kasus Produksi
11. **Jawaban: B**. Pendekatan struktural rekayasa perangkat lunak (AST Chunking) memecah kompleksitas masalah sebelum mencapai model probabilistik. Ini jauh lebih murah, terukur, dan deterministik dibanding hanya mengandalkan kapasitas memori raw token context model yang mahal dan lambat.
12. **Jawaban: A**. Strategi ketahanan sistem (*resilience engineering*) pada beban puncak membutuhkan lapisan pelindung: membatasi request langsung ke model via cache semantik berlatensi ultra-rendah dan mendowngrade fitur secara teratur (*graceful degradation*) jika kuota vendor habis.
13. **Jawaban: C**. Pendekatan *Shadow Deployment* adalah standar de-facto enterprise AI untuk memverifikasi performa alternatif model baru di bawah kondisi data produksi nyata tanpa mempertaruhkan pengalaman pengguna aktif (*zero blast radius*).

---

### 16. Summary

1. **Paradigma Pergeseran Backlog**: Transisi dari software konvensional ke agen otonom menuntut transformasi dari *Deterministic Feature Lists* menuju **Evaluation-Driven Backlog Engineering (EDBE)**.
2. **Prioritisasi Probabilistik (p-WSJF)**: Penilaian kelayakan implementasi fitur AI harus memperhitungkan faktor risiko ketidakpastian stokastik (*Uncertainty Multiplier*), biaya komputasi token jangka panjang, dan dampak regulasi kepatuhan (*Safety Criticality*).
3. **Gerbang Otomasi Mutu (Eval Gates)**: Definisi *Done* (DoD) pada produk AI tidak ditentukan oleh sukses kompilasi kode, melainkan oleh kelulusan kuantitatif performa model terhadap *Golden Dataset* di dalam CI/CD pipeline.
4. **Closed-Loop Telemetry**: Sistem produksi modern wajib menjembatani platform observabilitas inferensi secara otomatis ke backlog ticketing engineering. Outlier dan kegagalan inferensi produksi harus langsung dikonversi menjadi data uji regresi baru untuk memperkuat ketahanan model secara berkelanjutan.