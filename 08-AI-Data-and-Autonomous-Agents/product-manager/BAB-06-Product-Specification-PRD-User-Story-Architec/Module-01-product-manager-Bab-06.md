# Bab 06: Product Specification, PRD & User Story Architecture

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Technical Product Manager (AI/Data/Agents) diharapkan mampu:
- **Merancang Probabilistic Product Requirements Document (p-PRD):** Menyusun spesifikasi produk untuk sistem non-deterministik dengan transisi dari deterministik *boolean acceptance criteria* ke *statistical threshold acceptance criteria*.
- **Mendefinisikan Arsitektur User Story & Task Decomposition untuk Agen Otonom:** Memetakan hierarki kapabilitas agen (*intent recognition, multi-step planning, tool use, reflection, guardrails*) ke dalam format user story yang dapat dieksekusi oleh tim engineering.
- **Mengembangkan Contract-First Evals Specification:** Menuliskan spesifikasi evaluasi kuantitatif (*Golden Datasets*, metrik RAG/Agentik seperti faithfulness, answer relevancy, precision/recall pemanggilan tool) sebagai bagian inti dari PRD sebelum baris kode pertama ditulis.
- **Mengelola SLA, Latensi, dan Degradation Fallbacks:** Menentukan kriteria fungsional dan non-fungsional saat model mengalami *drift*, *rate-limiting*, halusinasi, atau *infinite planning loops*.

---

## 2. Concept Overview

Dalam rekayasa perangkat lunak konvensional, PRD mengasumsikan sistem deterministik:
$$\forall x \in X, \quad f(x) = y \quad (\text{selalu identik})$$

Dalam rekayasa produk berbasis kecerdasan buatan dan agen otonom (*AI & Autonomous Agents*), sistem bersifat probabilistik dan stateful:
$$P(Y = y \mid X = x, \theta, S_t) \in [0, 1]$$
di mana $\theta$ adalah bobot model dan $S_t$ adalah riwayat memori/konteks pada waktu $t$.

```
+-------------------------------------------------------------------------------+
|                       TRADITIONAL vs AI AGENT PRD MENTAL MODEL               |
+-------------------------------------------------------------------------------+
| Fitur                  | Tradisional (Deterministik) | AI Agentic (Probabilistik)     |
+------------------------+-----------------------------+--------------------------------+
| Acceptance Criteria    | True / False                | Statistical Pass Rate >= 95%   |
| Scope Boundary         | Rigid CRUD interfaces       | Intent space, Action space     |
| Logic Failure          | Bug di code / edge-case DB  | Hallucination, loop, drift     |
| Edge-case definition   | Boundary Value Analysis     | Out-of-Distribution (OOD) data |
| Quality Control        | Unit / Integration Tests    | Evals Harness + LLM-as-a-Judge |
+------------------------+-----------------------------+--------------------------------+
```

### Mental Model: PRD sebagai Kontrak Runtime & Evaluasi
Bagi AI Product Manager, PRD bukan sekadar dokumen dokumentasi statis, melainkan **Machine-Readable Contract** yang langsung menjadi benchmark dalam CI/CD evaluation harness. Tiga pilar utama dalam p-PRD:
1. **Agent Action Space:** Batasan tool, API, parameter mutasi data, dan radius ledakan (*blast radius*) sistem.
2. **Acceptance Threshold Vector:** Vektor metrik kepatuhan (akurasi semantic, latensi p95, rasio halusinasi, biaya token maksimum per sesi).
3. **Graceful Degradation Tree:** Algoritma pengambilan keputusan produk saat confidence score model jatuh di bawah batas aman.

---

## 3. Why It Matters

### Masalah Nyata di Industri
Banyak inisiatif agen LLM di enterprise mengalami kegagalan pada transisi dari *Proof-of-Concept* (PoC) ke *Production*. Masalah utamanya berakar pada spesifikasi produk:
1. **Vague Acceptance Criteria:** Tim PM menulis kriteria seperti: *"Agen harus menjawab pertanyaan pelanggan dengan ramah dan akurat."* Engineer tidak memiliki baseline validasi, sehingga deployment menghasilkan halusinasi yang melanggar compliance hukum atau finansial.
2. **Blast Radius Failure:** Agen diberikan akses mengeksekusi mutasi SQL/API tanpa spesifikasi PRD yang membatasi tindakan ireversibel (*irreversible actions*), memicu insiden integritas data produksi.
3. **Runaway Cost & Latency:** Tanpa batasan token budget per interaksi dan ambang batas kedalaman rekursi agen (*loop limits*), satu query pengguna dapat memakan biaya belasan dolar dan memakan waktu menit dengan status timeout.

Enterprise menuntut determinisme tata kelola di atas sistem inferensi yang probabilistik. Technical PM adalah jembatan yang menetapkan arsitektur pembatas (*guardrails*) tersebut melalui spesifikasi yang presisi.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan siklus hidup spesifikasi produk berbasis agen otonom, mulai dari PRD, dekonstruksi User Story, hingga verifikasi otomatis pada CI/CD Eval Harness:

```
[ Technical PRD Specification ]
  ├── 1. Intent & Action Space Definition
  ├── 2. Statistical Acceptance Criteria (SAC)
  └── 3. Blast Radius & Fallback Policies
             │
             ▼
[ User Story Architecture ]
  ├── Story 1: Reasoning & Task Planning (DAG generation)
  ├── Story 2: Tool Grounding & Payload Schema
  └── Story 3: Guardrail & Reflection Loops
             │
             ▼
[ Continuous Delivery / Eval Pipeline ]
  ┌─────────────────────────────────────────────────────────────┐
  │                   EVALS HARNESS RUNTIME                     │
  │                                                             │
  │  +------------------+     Execute Trace     +-------------+ │
  │  |  Golden Dataset  | ────────────────────> | Model/Agent | │
  │  +------------------+                       +------+------+ │
  │                                                    │        │
  │                                           Emits Trace Log   │
  │                                                    ▼        │
  │  +------------------+    Validates Against  +-------------+ │
  │  | SAC Metrics      | <───────────────────  | LLM Judge & | │
  │  | (Faithfulness,   |      Assertions       | Deterministic|│
  │  |  Tool Recall)    |                       | Evaluator   | │
  │  +--------+---------+                       +-------------+ │
  │           │                                                 │
  └───────────┼─────────────────────────────────────────────────┘
              │
      Threshold Met?
     /              \
  [YES]             [NO]
   │                  │
   ▼                  ▼
[Deploy to Prod]   [Block Build & Trigger Regression Analysis]
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### A. Anatomi Probabilistic PRD (p-PRD)
Spesifikasi agen otonom harus memisahkan fungsionalitas menjadi 4 lapisan inti:

1. **Cognitive Boundary (Batasan Kognitif):**
   - Mendefinisikan *System Prompt Baseline*.
   - Menyatakan kapabilitas yang diizinkan (*in-scope intents*) dan yang ditolak langsung secara deterministik (*out-of-scope/adversarial intents*).
2. **Tool Execution Matrix (Matriks Eksekusi Alat):**
   - Setiap pemanggilan tool oleh agen harus didokumentasikan layaknya endpoint REST API: Nama tool, input schema (JSON schema), idempotensi, serta mitigasi *side-effect*.
   - Read-only actions vs. Mutation actions (misal: `search_kb` vs. `transfer_funds`).
3. **Statistical Acceptance Criteria (SAC):**
   - Menggantikan formula konvensional "*Given-When-Then*" dengan "*Given-When-Expect-Threshold*".
   - Contoh: *Faithfulness Score $\ge 0.90$*, *Tool Selection Precision $\ge 0.98$*, *Context Recall $\ge 0.85$* pada dataset evaluasi $N \ge 500$.
4. **Token Economics & Latency Budgets:**
   - Batas maksimum konteks input, budget pemanggilan token output, batas iterasi re-planning (maksimal $K$ putaran), dan latensi end-to-end p95 (misal: $< 4.5 \text{ detik}$).

### B. Hierarki User Story untuk Agen Otonom
Pecah fitur kompleks menjadi hierarki dependen:

```
[Epic] Sistem Rekonsiliasi Faktur Agenik
   │
   ├── [Story 1: Schema Extraction & Validation]
   │     As an Accountant, I want the agent to extract invoice metadata
   │     so that structured validation can occur.
   │     - Criteria: JSON Schema conformance = 100% (Deterministic validation).
   │
   ├── [Story 2: Discrepancy Reasoning & Tool Use]
   │     As an Accountant, I want the agent to query the ERP system
   │     to identify variance between PO and Invoice.
   │     - Criteria: Precision of ERP tool selection >= 0.95.
   │
   └── [Story 3: Safety Guardrails & Human Escalation]
         As a Risk Manager, I want the agent to halt execution and ask human
         confirmation if variance > $1,000.
         - Criteria: Deterministic execution intercept on blast-radius rule.
```

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi **PRD Acceptance Criteria Evaluator Engine** berbasis Python. Modul ini bertindak sebagai jembatan langsung antara PRD yang ditulis oleh PM (didefinisikan dalam kode sebagai *Contract Specification*) dengan hasil observasi runtime agen (*execution traces*).

```python
"""
Module: prd_eval_engine.py
Description: Production-ready testing framework to evaluate Agent Traces against
             Product Requirements Document (PRD) Statistical Acceptance Criteria.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
import statistics
import json


# ============================================================================
# 1. PRD SPECIFICATION SCHEMAS (Technical Contract Definition)
# ============================================================================

class ToolCallSpec(BaseModel):
    tool_name: str
    required_arguments: List[str]
    is_mutation: bool = False


class StatisticalAcceptanceCriteria(BaseModel):
    min_faithfulness_score: float = Field(ge=0.0, le=1.0)
    min_tool_selection_accuracy: float = Field(ge=0.0, le=1.0)
    max_hallucination_rate: float = Field(ge=0.0, le=1.0)
    max_p95_latency_ms: float = Field(gt=0.0)
    max_cost_per_session_usd: float = Field(gt=0.0)
    max_agent_loop_iterations: int = Field(gt=0)


class AgentPRDSpec(BaseModel):
    prd_id: str
    feature_name: str
    version: str
    allowed_tools: List[ToolCallSpec]
    criteria: StatisticalAcceptanceCriteria


# ============================================================================
# 2. RUNTIME TRACE LOG SCHEMAS (Telemetry from Agent Execution)
# ============================================================================

class AgentStepTrace(BaseModel):
    step_number: int
    tool_invoked: Optional[str] = None
    tool_input_keys: List[str] = Field(default_factory=list)
    latency_ms: float
    cost_usd: float


class AgentSessionTrace(BaseModel):
    session_id: str
    input_prompt: str
    final_output: str
    steps: List[AgentStepTrace]
    faithfulness_score: float = Field(ge=0.0, le=1.0)  # Computed via Evaluator Model
    is_hallucinated: bool
    ground_truth_tool: Optional[str] = None


# ============================================================================
# 3. VERIFICATION ENGINE
# ============================================================================

class EvalSummary(BaseModel):
    passed: bool
    total_sessions: int
    avg_faithfulness: float
    tool_accuracy: float
    hallucination_rate: float
    p95_latency_ms: float
    avg_cost_usd: float
    max_iterations_detected: int
    violation_reasons: List[str]


class PRDEvaluationEngine:
    def __init__(self, spec: AgentPRDSpec):
        self.spec = spec

    def evaluate_test_suite(self, traces: List[AgentSessionTrace]) -> EvalSummary:
        """
        Validates a collection of execution traces against PRD Statistical Criteria.
        """
        if not traces:
            raise ValueError("Trace dataset cannot be empty for PRD evaluation.")

        violations: List[str] = []
        total_sessions = len(traces)

        # 1. Latency Metrics (p95)
        all_session_latencies = [
            sum(step.latency_ms for step in t.steps) for t in traces
        ]
        all_session_latencies.sort()
        p95_index = int(0.95 * total_sessions) - 1
        p95_latency = all_session_latencies[max(0, p95_index)]

        if p95_latency > self.spec.criteria.max_p95_latency_ms:
            violations.append(
                f"SLA Latency Violated: p95 is {p95_latency:.2f}ms "
                f"(Threshold: {self.spec.criteria.max_p95_latency_ms:.2f}ms)"
            )

        # 2. Faithfulness Metric
        faithfulness_scores = [t.faithfulness_score for t in traces]
        avg_faithfulness = statistics.mean(faithfulness_scores)
        if avg_faithfulness < self.spec.criteria.min_faithfulness_score:
            violations.append(
                f"Faithfulness Metric Failed: Avg is {avg_faithfulness:.4f} "
                f"(Threshold: {self.spec.criteria.min_faithfulness_score:.4f})"
            )

        # 3. Hallucination Metric
        hallucination_count = sum(1 for t in traces if t.is_hallucinated)
        hallucination_rate = hallucination_count / total_sessions
        if hallucination_rate > self.spec.criteria.max_hallucination_rate:
            violations.append(
                f"Hallucination Rate Exceeded: {hallucination_rate:.4f} "
                f"(Threshold: {self.spec.criteria.max_hallucination_rate:.4f})"
            )

        # 4. Tool Selection Accuracy & Schema Adherence
        correct_tools = 0
        total_tool_required_sessions = 0
        max_loop_seen = 0

        for trace in traces:
            max_loop_seen = max(max_loop_seen, len(trace.steps))
            if trace.ground_truth_tool:
                total_tool_required_sessions += 1
                # Cek apakah pemanggilan tool pertama sesuai ground truth
                invoked_tools = [s.tool_invoked for s in trace.steps if s.tool_invoked]
                if invoked_tools and invoked_tools[0] == trace.ground_truth_tool:
                    correct_tools += 1

        tool_accuracy = (
            (correct_tools / total_tool_required_sessions)
            if total_tool_required_sessions > 0
            else 1.0
        )
        if tool_accuracy < self.spec.criteria.min_tool_selection_accuracy:
            violations.append(
                f"Tool Selection Accuracy Failed: {tool_accuracy:.4f} "
                f"(Threshold: {self.spec.criteria.min_tool_selection_accuracy:.4f})"
            )

        # 5. Agent Iteration Depth (Loop Limits)
        if max_loop_seen > self.spec.criteria.max_agent_loop_iterations:
            violations.append(
                f"Agent Loop Boundary Breached: Max steps observed {max_loop_seen} "
                f"(Threshold: {self.spec.criteria.max_agent_loop_iterations})"
            )

        # 6. Cost Computation
        all_costs = [sum(step.cost_usd for step in t.steps) for t in traces]
        avg_cost = statistics.mean(all_costs)
        if avg_cost > self.spec.criteria.max_cost_per_session_usd:
            violations.append(
                f"Token Economics Breached: Avg session cost ${avg_cost:.4f} "
                f"(Threshold: ${self.spec.criteria.max_cost_per_session_usd:.4f})"
            )

        return EvalSummary(
            passed=len(violations) == 0,
            total_sessions=total_sessions,
            avg_faithfulness=avg_faithfulness,
            tool_accuracy=tool_accuracy,
            hallucination_rate=hallucination_rate,
            p95_latency_ms=p95_latency,
            avg_cost_usd=avg_cost,
            max_iterations_detected=max_loop_seen,
            violation_reasons=violations,
        )


# ============================================================================
# 4. RUNTIME VERIFICATION EXECUTION (Simulation)
# ============================================================================

if __name__ == "__main__":
    # Inisialisasi PRD Contract untuk Financial Agent
    invoice_agent_prd = AgentPRDSpec(
        prd_id="PRD-AGENT-FIN-001",
        feature_name="Autonomous Invoice Reconciliation",
        version="1.2.0",
        allowed_tools=[
            ToolCallSpec(
                tool_name="get_invoice_data",
                required_arguments=["invoice_id"],
                is_mutation=False,
            ),
            ToolCallSpec(
                tool_name="reconcile_discrepancy",
                required_arguments=["invoice_id", "po_id", "variance"],
                is_mutation=True,
            ),
        ],
        criteria=StatisticalAcceptanceCriteria(
            min_faithfulness_score=0.92,
            min_tool_selection_accuracy=0.95,
            max_hallucination_rate=0.02,
            max_p95_latency_ms=3000.0,
            max_cost_per_session_usd=0.05,
            max_agent_loop_iterations=4,
        ),
    )

    # Mock Data: Simulasi 5 Sesi Trace dari hasil staging run
    simulated_traces = [
        AgentSessionTrace(
            session_id="sess_001",
            input_prompt="Reconcile Invoice INV-9901 against PO-8821",
            final_output="Reconciliation complete. Variance: $0.00.",
            steps=[
                AgentStepTrace(
                    step_number=1,
                    tool_invoked="get_invoice_data",
                    tool_input_keys=["invoice_id"],
                    latency_ms=450.0,
                    cost_usd=0.005,
                ),
                AgentStepTrace(
                    step_number=2,
                    tool_invoked="reconcile_discrepancy",
                    tool_input_keys=["invoice_id", "po_id", "variance"],
                    latency_ms=800.0,
                    cost_usd=0.010,
                ),
            ],
            faithfulness_score=0.98,
            is_hallucinated=False,
            ground_truth_tool="get_invoice_data",
        ),
        AgentSessionTrace(
            session_id="sess_002",
            input_prompt="Check invoice details for INV-1022",
            final_output="Invoice total is $450 USD.",
            steps=[
                AgentStepTrace(
                    step_number=1,
                    tool_invoked="get_invoice_data",
                    tool_input_keys=["invoice_id"],
                    latency_ms=510.0,
                    cost_usd=0.004,
                )
            ],
            faithfulness_score=0.95,
            is_hallucinated=False,
            ground_truth_tool="get_invoice_data",
        ),
        AgentSessionTrace(
            session_id="sess_003",
            input_prompt="Reconcile faulty invoice INV-0000",
            final_output="Unknown failure.",
            steps=[
                AgentStepTrace(step_number=1, tool_invoked="unknown_tool", latency_ms=3200.0, cost_usd=0.08)
            ],
            faithfulness_score=0.70,
            is_hallucinated=True,
            ground_truth_tool="get_invoice_data",
        ),
    ]

    evaluator = PRDEvaluationEngine(spec=invoice_agent_prd)
    result = evaluator.evaluate_test_suite(simulated_traces)

    print(json.dumps(result.model_dump(), indent=2))
```

---

## 7. Edge Cases & Failure Modes

Spesifikasi PRD teknis wajib memiliki panduan mitigasi struktural untuk lima failure mode berikut:

1. **Infinite Re-planning Loops:**
   - *Failure:* Model mengulang rencana (*plan step*) secara siklis saat response tool tidak memberikan kejelasan (misal: query database return 0 rows).
   - *Mitigation Spec:* Tetapkan `hard_stop_recursion_limit = 4`. Jika batas terlampaui, agen wajib menghentikan eksekusi dan memicu hand-off ke manusia dengan status payload `ESCALATION_REASON: RECURSION_LIMIT_EXCEEDED`.
2. **Context Window Overflow & Truncation Amnesia:**
   - *Failure:* Agen mengumpulkan trace data berlebih dari alat eksternal sehingga konteks memotong instruksi sistem instruksional awal (*System Prompt*).
   - *Mitigation Spec:* Tentukan mekanisme pemotongan konteks (*context pruning*) atau kompresi semantik sebelum pemanggilan LLM pada loop berikutnya; tetapkan `max_context_token_threshold = 8192`.
3. **Cascading Hallucinations in Multi-Step Tools:**
   - *Failure:* Output halusinasi pada Step 1 dipakai sebagai input parameter mutasi pada Step 2.
   - *Mitigation Spec:* Sisipkan deterministik *JSON Schema validation layer* di antara pemanggilan tool. Jika schema tidak sesuai, eksekusi dihentikan secara deterministik sebelum mutasi database dijalankan.
4. **Tool Call Argument Injection:**
   - *Failure:* Teks dari input eksternal berisi perintah terselubung (*indirect prompt injection*) yang mengubah argumen tool agen.
   - *Mitigation Spec:* Strict whitelist types validation. Penggunaan format strongly-typed models (misal: Pydantic) dengan regex pattern khusus untuk ID atau parameter operasional.
5. **Cold-Start Latency Spikes (Tool Warmup):**
   - *Failure:* Panggilan pertama model ke vector store atau function runtime memicu latensi di atas batas SLA (> 10s).
   - *Mitigation Spec:* Spesifikasikan *Streaming Progress Updates* pada UI. PRD harus mendefinisikan *time-to-first-token* (TTFT) SLA dan *heartbeat message interval* (tiap 1.5 detik jika latensi belum tuntas).

---

## 8. Trade-offs & Alternatif Solusi

Setiap keputusan arsitektur dalam PRD agen memiliki konsekuensi mendasar:

### Open-Ended Agentic Planning vs. Deterministic State Machines
```
Open-Ended Planning (e.g., AutoGPT)           State Machine + LLM Nodes (e.g., LangGraph)
◄────────────────────────────────────────────────────────────────────────────────────────►
High Flexibility / Low Predictability         High Predictability / Constrained Scope
Low Reliability (Enterprise Risk)             High Reliability (Production-Grade)
```

- **Open-Ended Planning (ReAct Murni):**
  - *Trade-off:* Mampu menangani intent yang tidak terstruktur dan beradaptasi secara fleksibel.
  - *Kelemahan:* Sangat rentan terhadap non-deterministik regressions, sulit diuji secara komprehensif, latensi dan biaya sulit diprediksi.
- **Constrained Directed Acyclic Graph (DAG) / LangGraph:**
  - *Trade-off:* Fleksibilitas pergerakan agen dibatasi oleh edge transitions yang didefinisikan secara deterministik.
  - *Kelemahan:* Butuh upaya rekayasa awal yang lebih besar. Namun, pendekatan ini merupakan standar industri enterprise karena blast radius dapat dikunci.

### Statistical Tolerance vs. Business Criticality
- Mengatur *Acceptance Criteria Faithfulness* pada `0.99` versus `0.90`:
  - `0.99` membutuhkan dataset golden sample masif ($N > 2000$), arsitektur multi-agent self-critique yang mahal, serta menaikkan latensi p95 secara signifikan.
  - `0.90` cukup memakai single model inference dengan prompt terpantau, menghemat cost 80%, tetapi memerlukan mitigasi UX berupa disclaimer dan konfirmasi manual.

---

## 9. Best Practices & Standard Industri

1. **RFC / Spec Format: The "Three-Tier Acceptance Criteria":**
   Terapkan standarisasi penulisan Acceptance Criteria dalam PRD:
   - **Tier 1 (Deterministic Rules):** Menggunakan status pass/fail mutlak (misal: "Agen tidak boleh menampilkan data PII di output").
   - **Tier 2 (Statistical Evals):** Didasarkan pada baseline agregat (misal: "Akurasi perutean intent minimal 96% pada 1.000 test case").
   - **Tier 3 (Degradation Behavior):** Jalur penyelamatan saat Tier 1 atau 2 terancam gagal (misal: "Tampilkan fallback static response jika latency melebihi 4000ms").
2. **Golden Datasets Versioning:**
   - Perlakukan Golden Dataset evaluasi setara dengan kode produksi.
   - PRD wajib mencantumkan tautan ke dataset version control (misal: HuggingFace Datasets, DVC, atau Lakehouse commit hash). PRD tidak valid tanpa benchmark dataset.
3. **Model Cards & System Boundary Integration:**
   - Sertakan batasan operasional model ke dalam PRD (*known failure modes, language capability limits, bias disclosures*).
4. **CI/CD Eval Gating:**
   - Buat aturan baku tim engineering: *Pull Request* sistem agen tidak boleh dimerge ke *main branch* jika skrip verifikasi PRD (seperti `prd_eval_engine.py`) menghasilkan exit code 1.

---

## 10. Hands-on Lab Exercise

### Skenario
Anda adalah Lead Technical PM untuk modul agen perbankan: **"Card Dispute Automated Resolver"**. Tugas Anda adalah merancang PRD Contract terprogram dan mengujinya menggunakan test suite data log agen.

### Task 1: Definisikan PRD Metadata & Kriteria (30 Menit)
Tuliskan dokumen PRD teknis dengan struktur JSON Schema berikut dan simpan ke file `dispute_agent_prd.json`:

```json
{
  "prd_id": "PRD-FINTECH-DISPUTE-001",
  "feature_name": "Autonomous Debit Card Dispute Resolution",
  "system_actor": "DisputeAgent-v1",
  "action_space": [
    {
      "name": "lookup_transaction",
      "type": "read",
      "parameters": ["card_id", "transaction_id"]
    },
    {
      "name": "provisional_credit",
      "type": "mutation",
      "parameters": ["account_id", "amount_cents"],
      "blast_radius_limit": 50000
    }
  ],
  "statistical_acceptance_criteria": {
    "min_faithfulness": 0.95,
    "max_hallucination_rate": 0.01,
    "min_tool_precision": 0.98,
    "max_latency_p95_ms": 2500,
    "max_cost_session_usd": 0.03
  }
}
```

### Task 2: Verifikasi Log Trace Staging (45 Menit)
1. Buat skrip testing baru bernama `lab_test_runner.py`.
2. Gunakan arsitektur dari Bagian 6 (`PRDEvaluationEngine`) untuk membaca `dispute_agent_prd.json`.
3. Buat mock 20 variasi trace transaksi dispute (termasuk kasus di mana agen mencoba mencairkan provisi kredit di atas batasan `blast_radius_limit`).
4. Jalankan assertion test:
   ```bash
   python lab_test_runner.py
   ```
5. **Expected Output Goal:**
   Sistem harus mampu mendeteksi pelanggaran kontrak ketika ada sesi yang mencoba melakukan call ke tool `provisional_credit` melebihi limit tanpa human confirmation, dan menggagalkan pipeline deployment dengan error log yang eksplisit.

---

## 11. Post-Lab Assessment Checklist

- [ ] Apakah Acceptance Criteria dalam PRD Anda terbebas dari kata-kata ambigu seperti *"akurat"*, *"cepat"*, atau *"natural"* dan digantikan oleh metrik kuantitatif?
- [ ] Apakah setiap mutasi status bisnis (*mutation tool*) dilindungi batasan eksplisit (*blast radius cap*) pada PRD?
- [ ] Apakah skenario *degradation fallback* telah terdefinisi saat latency LLM melonjak?
- [ ] Apakah PRD terhubung langsung dengan automated evaluation harness di level CI/CD?