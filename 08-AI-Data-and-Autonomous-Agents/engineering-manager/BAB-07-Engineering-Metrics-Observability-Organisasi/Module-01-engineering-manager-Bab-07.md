# Bab 07: Engineering Metrics & Observability Organisasi
**Module 01: Telemetri, Evaluasi Kinerja, dan Tata Kelola Operasional AI & Autonomous Agents**

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Engineering Manager dan Tech Lead diharapkan mampu:

*   **Mendefinisikan dan Mengoperasikan AI-Specific SLI/SLO/SLA**: Merumuskan indikator level layanan kuantitatif yang mencakup latensi inferensi (*Time-to-First-Token* dan *Tokens-Per-Second*), *Tool Call Success Rate*, *Agentic Step-to-Goal Convergence*, dan *Budget/Cost-Per-Task*.
*   **Merancang Arsitektur Observability Terpadu**: Mengintegrasikan tiga pilar telemetri klasik (Metrics, Logs, Traces) dengan dua pilar modern AI (Evaluations & Cost Attribution) menggunakan standar OpenTelemetry Semantic Conventions for Generative AI.
*   **Mendeteksi dan Memitigasi Regresi Kinerja Non-Deterministik**: Menganalisis *data drift*, *concept drift*, *hallucination velocity*, dan degradasi akurasi reasoning pada agen otonom sebelum berdampak pada *Service-Level Objectives* (SLO).
*   **Mengimplementasikan Framework FinOps untuk AI Platforms**: Membangun mekanisme atribusi biaya inferensi per tim, per domain, dan per eksekusi agen dengan batas kuota dinamis (*circuit breaker* finansial).
*   **Mengembangkan Automated Trace & Evaluation Harness**: Mengimplementasikan pipeline pemantauan runtime yang mengevaluasi eksekusi multi-step agent secara asynchronous tanpa mendegradasi latensi end-to-end pengguna.

---

### 2. Concept Overview

Dalam sistem mikroservis tradisional, observabilitas difokuskan pada ketersediaan sistem deterministik: kode $A$ menerima input $X$ dan menghasilkan output $Y$ dengan kode status HTTP 200 dalam batas waktu $Z$ milidetik. Kegagalan bersifat biner (sukses vs *exception*).

Pada domain **AI, Data, dan Autonomous Agents**, paradigma ini bergeser fundamental:
Sistem bersifat **probabilistik dan non-deterministik**. Agen otonom dapat merespons dengan HTTP 200, menyelesaikan eksekusi dalam batas waktu yang ditentukan, namun menghasilkan keluaran yang keliru (*logical hallucination*), terjebak dalam *infinite reasoning loop*, atau menghabiskan anggaran komputasi ratusan dolar dalam hitungan detik melalui pemanggilan *tools* eksternal yang redundan.

```
+--------------------------------------------------------------------------------+
|                        PARADIGMA OBSERVABILITAS                                 |
+--------------------------------------------------------------------------------+
|  TRADISIONAL (Deterministic)           |  AI & AGENTIC (Probabilistic)         |
|  - Latency (p50, p95, p99)             |  - Time-To-First-Token (TTFT)         |
|  - Error Rate (HTTP 4xx, 5xx)          |  - Inter-Token Latency (ITL)          |
|  - Traffic (RPS)                       |  - Step Convergence Rate per Task     |
|  - Saturation (CPU, RAM, Disk, Net)    |  - Tool Call Precision/Recall         |
|  - Input-Output Logging                |  - Context-Window Saturation          |
|  - Tracing Sinkron (RPC/HTTP Spans)    |  - Semantic Drift & Toxicity Score    |
|                                        |  - Token Velocity & FinOps Burn Rate  |
+--------------------------------------------------------------------------------+
```

Observabilitas organisasi untuk Autonomous Agents memerlukan **5 Pilar Telemetri AI**:
1. **Metrics**: Kuantifikasi performa komputasi dan pemanfaatan sumber daya (TTFT, TPS, GPU VRAM, Queue Depth).
2. **Traces**: Rekonstruksi graf eksekusi Directed Acyclic Graph (DAG) dari tahapan *Reasoning Engine* (misal: ReAct framework), mencakup *Prompt Formulation*, *LLM Generation*, *Tool Invocation*, dan *State Reflection*.
3. **Logs**: Rekaman kontekstual immutable yang memetakan masukan raw prompt, payload konteks, token mask, dan output intermediate step.
4. **Evaluations (Evals-as-Telemetry)**: Scoring metrik kualitas otomatis secara runtime atau near-line (Faithfulness, Context Relevance, Hallucination Index).
5. **Cost Attribution**: Pemetaan real-time penggunaan token (input, output, cache-read, cache-creation) ke *cost center* bisnis dan *user identifier*.

---

### 3. Why It Matters

Kegagalan membangun sistem observabilitas komprehensif pada AI Engine dan Autonomous Agents mengakibatkan berbagai risiko enterprise tingkat tinggi:

*   **Financial Denial of Service (Runaway Loops)**: Agen otonom yang gagal mencapai kriteria konvergensi (misalnya akibat parsing JSON yang terus-menerus gagal) dapat memanggil model bahasa frontier berulang kali dalam loop tak berujung. Tanpa observabilitas berbasis *step-budget* dan *cost anomaly alerts*, satu query pengguna dapat menghabiskan ribuan dolar dalam beberapa menit.
*   **Silent Semantic Failures**: Model yang mengalami *model drift* atau *prompt injection* dapat mengembalikan format respons yang valid secara sintaksis, namun secara semantik melanggar kepatuhan regulasi (seperti kebocoran PII, bias finansial, atau saran medis yang berbahaya). Metrik operasional tradisional akan menandai transaksi ini sebagai 100% "healthy".
*   **Debugging Paralysis pada Distributed Tool Calling**: Agen otonom memecah masalah dengan memanggil API pihak ketiga, mengeksekusi kode Python di sandbox, atau melakukan pencarian di Vector Database. Ketika latensi melonjak dari 1 detik ke 45 detik, Engineering Manager tidak dapat mengidentifikasi akar masalah tanpa *distributed span context propagation* yang melintasi batas LLM, Vector DB, dan Agent Runtime.
*   **Ketidakmampuan Mengukur ROI Engineering**: Tanpa pengukuran *Token ROI* (efisiensi token yang dihabiskan dibandingkan dengan penyelesaian task), pimpinan engineering tidak dapat membuat keputusan terukur mengenai kapan harus melakukan fine-tuning model open-source yang lebih kecil versus menyewa model frontier proprietary API.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan arsitektur observabilitas end-to-end untuk Autonomous Agents di level enterprise, berbasis OpenTelemetry Collector, Prometheus, Vector Metrics, dan Eval Harness Engine.

```
+------------------------------------------------------------------------------------+
|                                 APPLICATION LAYER                                  |
|                                                                                    |
|  +-------------------------------------------------------------------------------+ |
|  |                          Autonomous Agent Runtime                             | |
|  |  [User Task] -> [Reasoning Loop] <---> [Tools / Vector DB / Code Sandbox]     | |
|  |                        |                                                      | |
|  |     Instrumented via OpenTelemetry GenAI Semantic Conventions API             | |
|  +------------------------+------------------------------------------------------+ |
+---------------------------|--------------------------------------------------------+
                            | Spans, Token Counts, Tool Payloads, Step Counters
                            v
+------------------------------------------------------------------------------------+
|                             TELEMETRY INGESTION BUS                                |
|                                                                                    |
|  +-------------------------------------------------------------------------------+ |
|  |               OpenTelemetry Collector (Edge / Gateway Daemon)                 | |
|  |  Receivers: OTLP/gRPC                                                         | |
|  |  Processors:                                                                  | |
|  |    - PII Redaction & Masking Processor                                        | |
|  |    - Dynamic Attribute Enrichment (Tenant ID, Cost Center, Model Family)      | |
|  |    - Probabilistic & Tail-based Sampler (100% of errors/high cost, 5% happy)  | |
|  +--------+--------------------------+----------------------------+--------------+ |
+-----------|--------------------------|----------------------------|----------------+
            |                          |                            |
            v                          v                            v
+----------------------+   +------------------------+   +----------------------------+
| METRICS STORAGE      |   | TRACE & LOG STORAGE    |   | NEAR-LINE EVAL HARNESS     |
| (Prometheus/Victoria)|   | (Jaeger / ClickHouse)  |   | (Async Worker Pool)        |
|                      |   |                        |   |                            |
| - Counters:          |   | - Full Agent Trajectory|   | - Hallucination Scorer     |
|   Tokens, Loops      |   | - Step-by-step spans   |   | - Context Relevance Eval   |
| - Gauges:            |   | - Tool input/output    |   | - Toxicity / PII Auditing  |
|   Inflight Tasks     |   | - Raw Token Metadata   |   | - Output Faithfulness      |
| - Histograms:        |   |                        |   |              |             |
|   TTFT, ITL, Cost    |   |                        |   |              v             |
+----------+-----------+   +-----------+------------+   +--------------+-------------+
           |                           |                               |
           +--------------------+      |      +------------------------+
                                |      |      |
                                v      v      v
+------------------------------------------------------------------------------------+
|                         ORGANIZATIONAL DASHBOARD & ALERTING                        |
|                                                                                    |
|  +-------------------------+ +------------------------+ +------------------------+ |
|  |      Grafana Engine     | |     PagerDuty / Ops    | |     FinOps Engine      | |
|  | - Agent Convergence SLO | | - Runaway Loop Alerts  | | - Department Billing   | |
|  | - Token Velocity / Tier | | - Hallucination Spikes | | - Cost Quota Breaches  | |
|  | - P99 TTFT & ITL        | | - Tool Failure > 5%    | | - Model ROI Matrix     | |
|  +-------------------------+ +------------------------+ +------------------------+ |
+------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Token Tracking & Cost Calculation Framework
Model LLM mengenakan biaya asimetris: input/prompt tokens secara signifikan lebih murah daripada output/completion tokens, sementara *cached prompts* memberikan diskon lebih lanjut. Observabilitas organisasi harus memetakan ini secara deterministik:

$$\text{Cost}_{\text{Task}} = \sum_{s=1}^{S} \left( T_{\text{prompt}}^{(s)} \times P_{\text{prompt}} + T_{\text{completion}}^{(s)} \times P_{\text{completion}} - T_{\text{cache}}^{(s)} \times D_{\text{cache}} \right) + \sum_{k=1}^{K} C_{\text{tool}}^{(k)}$$

*Dimana:*
*   $S$ adalah total langkah (*steps/turns*) eksekusi agen.
*   $T_{\text{prompt}}, T_{\text{completion}}, T_{\text{cache}}$ adalah kuantitas token pada step $s$.
*   $P_{\text{prompt}}, P_{\text{completion}}$ adalah harga unit per token untuk model aktif.
*   $D_{\text{cache}}$ adalah potongan harga prompt caching.
*   $C_{\text{tool}}$ adalah biaya pemanggilan tools pihak ketiga (misal: Serper API, Twilio, WolframAlpha) pada step $k$.

#### B. Agentic Loop Telemetry: Convergence Rate & Step Efficiency
Salah satu ancaman terbesar pada agen otonom adalah *Stochastic Thrashing*: agen memanggil tools berulang kali tanpa membuat progres nyata ke arah resolusi tujuan (*Goal Trajectory*).
Metrik kritis yang harus diinstrumentasi:
*   **Step Convergence Rate**: Rasio task yang berhasil diselesaikan di bawah batas $N$ steps:
    $$R_{\text{convergence}} = \frac{\text{Tasks Completed Successfully with Steps } \le N_{\text{budget}}}{\text{Total Tasks Initiated}}$$
*   **Tool Execution Precision ($TEP$)**: Rasio eksekusi tool yang menghasilkan data valid terhadap seluruh percobaan eksekusi tool:
    $$TEP = \frac{\sum \text{Tool Calls with HTTP 200 \& Valid Schema}}{\text{Total Tool Call Attempts}}$$
*   **Context Window Saturation ($CWS$)**:
    $$CWS = \frac{\text{Current Context Tokens}}{\text{Maximum Context Window Capacity (Context Window Limit)}}$$
    Jika $CWS > 0.85$, latensi inferensi meningkat secara eksponensial (akibat operasi self-attention $O(N^2)$ atau varian chunked-attention), dan risiko *forgetfulness* (*Lost in the Middle*) meningkat tajam.

#### C. Asynchronous Evaluation (Evals-as-Telemetry)
Mengevaluasi kualitas output secara sinkron akan menambah overhead latensi yang tidak dapat ditoleransi (misalnya menjalankan model LLM-as-a-judge selama 2 detik di dalam request-path). Oleh karena itu, arsitektur observabilitas agentic menggunakan pemisahan jalur:
1. **Critical Path (Sinkron)**: Agen mengeksekusi task, merekam span OTel, memancarkan token counts, dan mengirimkan respons langsung ke pengguna.
2. **Analysis Path (Asinkron)**: Span yang telah diekspor dialirkan ke antrean pesan (misalnya Kafka atau Redis Streams), di mana worker pool menjalankan evaluasi deterministik (BLEU, ROUGE, regex safety) dan heuristik (LLM-as-a-judge untuk mengevaluasi *Hallucination Score* dan *Context Relevance*). Hasil evaluasi dimasukkan kembali ke Prometheus dan Vector Database sebagai anotasi trace.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi Python production-grade untuk sistem telemetri AI Agent. Kode ini mengintegrasikan tracing berbasis OpenTelemetry dengan semantic convention, menghitung biaya token secara dinamis, mengumpulkan metrik performa step-level, dan mengekspor data ke Prometheus secara *thread-safe*.

```python
"""
agent_observability.py
Enterprise Observability Module for AI & Autonomous Agents.
Compatible with OpenTelemetry and Prometheus Client libraries.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
from contextlib import contextmanager

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Span
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource

# -----------------------------------------------------------------------------
# LOGGING SETUP
# -----------------------------------------------------------------------------
logger = logging.getLogger("ai_observability")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s'))
logger.addHandler(handler)


# -----------------------------------------------------------------------------
# DATA STRUCTURES & CONFIGURATION
# -----------------------------------------------------------------------------
class ModelProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPEN_SOURCE = "open_source_vllm"


@dataclass(frozen=True)
class ModelCostMatrix:
    prompt_token_cost_per_million: float
    completion_token_cost_per_million: float
    cache_read_discount_percentage: float = 0.5


PRICING_TABLE: Dict[str, ModelCostMatrix] = {
    "gpt-4o": ModelCostMatrix(prompt_token_cost_per_million=5.00, completion_token_cost_per_million=15.00),
    "gpt-4o-mini": ModelCostMatrix(prompt_token_cost_per_million=0.15, completion_token_cost_per_million=0.60),
    "claude-3-5-sonnet": ModelCostMatrix(prompt_token_cost_per_million=3.00, completion_token_cost_per_million=15.00),
    "llama-3.1-70b-instruct": ModelCostMatrix(prompt_token_cost_per_million=0.80, completion_token_cost_per_million=0.80),
}


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class StepTelemetryContext:
    step_number: int
    step_name: str
    start_time: float = field(default_factory=time.perf_counter)
    usage: TokenUsage = field(default_factory=TokenUsage)
    attributes: Dict[str, Any] = field(default_factory=dict)


# -----------------------------------------------------------------------------
# METRICS REGISTRY (PROMETHEUS ENGINE)
# -----------------------------------------------------------------------------
class AgentMetricsRegistry:
    """Enterprise Registry encapsulating operational, qualitative, and FinOps metrics."""

    def __init__(self, registry: CollectorRegistry = CollectorRegistry()):
        self.registry = registry

        # Counters
        self.token_counter = Counter(
            name="agent_tokens_consumed_total",
            documentation="Total number of tokens consumed by models within agents.",
            labelnames=["agent_id", "team_id", "model_name", "token_type"],
            registry=self.registry,
        )
        self.incurred_cost_counter = Counter(
            name="agent_financial_cost_usd_total",
            documentation="Accumulated USD cost incurred from LLM token operations.",
            labelnames=["agent_id", "team_id", "model_name"],
            registry=self.registry,
        )
        self.tool_invocations_total = Counter(
            name="agent_tool_invocations_total",
            documentation="Total tool executions split by tool name and status.",
            labelnames=["agent_id", "tool_name", "status"],
            registry=self.registry,
        )
        self.agent_runs_total = Counter(
            name="agent_executions_total",
            documentation="Total completed agent tasks grouped by terminal status.",
            labelnames=["agent_id", "status"],
            registry=self.registry,
        )

        # Histograms
        self.time_to_first_token = Histogram(
            name="agent_llm_time_to_first_token_seconds",
            documentation="Duration between prompt dispatch and reception of initial token stream.",
            labelnames=["model_name"],
            buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.registry,
        )
        self.step_execution_latency = Histogram(
            name="agent_step_execution_latency_seconds",
            documentation="Execution latency per agentic reasoning step.",
            labelnames=["agent_id", "step_name"],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
            registry=self.registry,
        )

        # Gauges
        self.context_saturation_ratio = Gauge(
            name="agent_context_window_saturation_ratio",
            documentation="Ratio of current token buffer to maximum context window limit.",
            labelnames=["agent_id", "model_name"],
            registry=self.registry,
        )
        self.active_agents_gauge = Gauge(
            name="agent_active_instances",
            documentation="Current number of active agentic loops running concurrently.",
            labelnames=["agent_id"],
            registry=self.registry,
        )


# Initialize global registry
agent_metrics = AgentMetricsRegistry()


# -----------------------------------------------------------------------------
# OBSERVABILITY ENGINE & WRAPPER
# -----------------------------------------------------------------------------
class AgentObservabilityLifecycle:
    """Manages the lifecycle of an Agent Execution Task, aggregating Spans, Logs, and Metrics."""

    def __init__(
        self,
        agent_id: str,
        team_id: str,
        trace_provider: Optional[TracerProvider] = None,
    ):
        self.agent_id = agent_id
        self.team_id = team_id
        self.tracer = (
            trace_provider.get_tracer("agent_runtime")
            if trace_provider
            else trace.get_tracer("agent_runtime")
        )
        self.root_span: Optional[Span] = None
        self.steps: List[StepTelemetryContext] = []
        self._current_step: Optional[StepTelemetryContext] = None

    def start_agent_run(self, session_id: str, task_objective: str) -> None:
        """Initializes the root execution span for the agent."""
        agent_metrics.active_agents_gauge.labels(agent_id=self.agent_id).inc()
        self.root_span = self.tracer.start_span(
            name=f"AgentTaskExecution: {self.agent_id}",
            attributes={
                "gen_ai.system": "AutonomousAgentFramework",
                "agent.id": self.agent_id,
                "agent.team_id": self.team_id,
                "agent.session_id": session_id,
                "agent.objective": task_objective,
            },
        )
        logger.info(f"Task started for agent '{self.agent_id}' under session '{session_id}'.")

    @contextmanager
    def track_step(self, step_number: int, step_name: str):
        """Context manager to monitor individual agentic reasoning/action steps."""
        step_ctx = StepTelemetryContext(step_number=step_number, step_name=step_name)
        self._current_step = step_ctx
        step_span = self.tracer.start_span(
            name=f"AgentStep: {step_name}",
            attributes={
                "agent.step_number": step_number,
                "agent.step_name": step_name,
                "agent.id": self.agent_id,
            },
        )
        start_ts = time.perf_counter()

        try:
            yield step_ctx
            step_span.set_status(Status(StatusCode.OK))
        except Exception as exc:
            step_span.record_exception(exc)
            step_span.set_status(Status(StatusCode.ERROR, str(exc)))
            logger.error(f"Step {step_number} [{step_name}] failed: {exc}", exc_info=True)
            raise
        finally:
            latency = time.perf_counter() - start_ts
            agent_metrics.step_execution_latency.labels(
                agent_id=self.agent_id, step_name=step_name
            ).observe(latency)
            step_span.end()
            self.steps.append(step_ctx)
            self._current_step = None

    def record_llm_inference(
        self,
        model_name: str,
        usage: TokenUsage,
        context_limit: int,
        ttft_seconds: Optional[float] = None,
    ) -> float:
        """Records token metrics, calculates FinOps liability, and tracks latency."""
        # 1. Update Ingestion Counters
        agent_metrics.token_counter.labels(
            agent_id=self.agent_id, team_id=self.team_id, model_name=model_name, token_type="prompt"
        ).inc(usage.prompt_tokens)
        agent_metrics.token_counter.labels(
            agent_id=self.agent_id, team_id=self.team_id, model_name=model_name, token_type="completion"
        ).inc(usage.completion_tokens)

        # 2. Financial Attribution
        cost = self._calculate_cost(model_name, usage)
        agent_metrics.incurred_cost_counter.labels(
            agent_id=self.agent_id, team_id=self.team_id, model_name=model_name
        ).inc(cost)

        # 3. Saturation Gauge
        saturation = usage.total_tokens / float(context_limit) if context_limit > 0 else 0.0
        agent_metrics.context_saturation_ratio.labels(
            agent_id=self.agent_id, model_name=model_name
        ).set(saturation)

        # 4. TTFT Recording
        if ttft_seconds is not None:
            agent_metrics.time_to_first_token.labels(model_name=model_name).observe(ttft_seconds)

        # 5. Link usage to current active step if inside track_step context
        if self._current_step:
            self._current_step.usage.prompt_tokens += usage.prompt_tokens
            self._current_step.usage.completion_tokens += usage.completion_tokens
            self._current_step.usage.cached_tokens += usage.cached_tokens

        return cost

    def record_tool_call(self, tool_name: str, success: bool, payload_size_bytes: int) -> None:
        """Monitors downstream tool execution efficiency."""
        status_label = "success" if success else "failure"
        agent_metrics.tool_invocations_total.labels(
            agent_id=self.agent_id, tool_name=tool_name, status=status_label
        ).inc()

        if self.root_span:
            self.root_span.add_event(
                name="tool_call_completed",
                attributes={
                    "tool.name": tool_name,
                    "tool.success": success,
                    "tool.payload_size_bytes": payload_size_bytes,
                },
            )

    def finalize_agent_run(self, terminal_status: str) -> None:
        """Closes the trace root and resets active lifecycle allocations."""
        agent_metrics.agent_runs_total.labels(
            agent_id=self.agent_id, status=terminal_status
        ).inc()
        agent_metrics.active_agents_gauge.labels(agent_id=self.agent_id).dec()

        if self.root_span:
            if terminal_status == "SUCCESS":
                self.root_span.set_status(Status(StatusCode.OK))
            else:
                self.root_span.set_status(Status(StatusCode.ERROR, f"Task terminated with status: {terminal_status}"))
            self.root_span.end()
            self.root_span = None

        logger.info(f"Agent '{self.agent_id}' run finished. Status: {terminal_status}. Steps taken: {len(self.steps)}")

    @staticmethod
    def _calculate_cost(model_name: str, usage: TokenUsage) -> float:
        matrix = PRICING_TABLE.get(model_name)
        if not matrix:
            logger.warning(f"Cost matrix missing for model '{model_name}'. Defaulting to $0.00.")
            return 0.0

        billable_prompt = usage.prompt_tokens - (usage.cached_tokens * matrix.cache_read_discount_percentage)
        billable_prompt = max(0.0, billable_prompt)

        prompt_cost = (billable_prompt / 1_000_000.0) * matrix.prompt_token_cost_per_million
        completion_cost = (usage.completion_tokens / 1_000_000.0) * matrix.completion_token_cost_per_million
        return prompt_cost + completion_cost


# -----------------------------------------------------------------------------
# RUNTIME INTEGRATION VALIDATION (SMOKE TEST)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Setup test trace infrastructure
    provider = TracerProvider(
        resource=Resource.create({"service.name": "enterprise-agent-core"})
    )
    obs = AgentObservabilityLifecycle(agent_id="finance-reconciler-agent", team_id="ops-core", trace_provider=provider)

    obs.start_agent_run(session_id="sess-9941a", task_objective="Reconcile daily billing ledgers.")

    # Simulate Step 1: Query Knowledge Retrieval
    with obs.track_step(step_number=1, step_name="VectorSearch-Step"):
        # Simulated LLM interaction
        simulated_tokens = TokenUsage(prompt_tokens=1500, completion_tokens=120, cached_tokens=500)
        cost = obs.record_llm_inference(
            model_name="gpt-4o",
            usage=simulated_tokens,
            context_limit=128000,
            ttft_seconds=0.34,
        )
        obs.record_tool_call(tool_name="qdrant_vector_store", success=True, payload_size_bytes=4096)

    # Simulate Step 2: Code Execution / Calculation
    with obs.track_step(step_number=2, step_name="CodeExecution-Step"):
        simulated_tokens = TokenUsage(prompt_tokens=2200, completion_tokens=450, cached_tokens=0)
        cost += obs.record_llm_inference(
            model_name="gpt-4o",
            usage=simulated_tokens,
            context_limit=128000,
            ttft_seconds=0.48,
        )
        obs.record_tool_call(tool_name="python_docker_sandbox", success=True, payload_size_bytes=512)

    obs.finalize_agent_run(terminal_status="SUCCESS")
    print(f"Total calculated cost for execution run: ${cost:.6f}")
```

---

### 7. Edge Cases & Failure Modes

Mengelola observabilitas sistem AI dan Autonomous Agent membutuhkan strategi mitigasi untuk sejumlah kegagalan spesifik:

| Failure Mode | Mekanisme Terjadinya | Dampak Teknis & Finansial | Mitigasi Engineering |
| :--- | :--- | :--- | :--- |
| **Runaway Agent Loops** | Agen gagal menguraikan argumen pemanggilan tools secara rekursif, masuk ke loop eksekusi tak terhingga. | Lonjakan tagihan API (*financial exhaustion*), thread starvation, dan saturasi koneksi backend. | Terapkan batas eksekusi deterministik (*Hard Max Steps Count* $\le 10$), dan buat metrik OTel pengukur gradien delta token per step. |
| **Context Window Degradation (Lost in the Middle)** | Prompt context terus mengembang tanpa kompresi hingga mendekati kapasitas limit model. | Latensi eksponensial, reasoning failure, dan halusinasi akibat token relevan tergeser keluar atensi. | Konfigurasikan alert pada rasio saturasi context $> 80\%$. Terapkan auto-summarization pipeline saat batas tercapai. |
| **Telemetry Ingestion Bottleneck (OOM)** | Log trace mencatat *raw payload* embeddings atau citra/base64 dalam span attributes. | Collector OTel kehabisan memori (*OOMKilled*), lonjakan latensi transmisi span, *network egress penalty*. | Masking layer wajib: larang serialisasi array float (vektor) atau base64 payload ke dalam span attributes; gunakan hashing SHA-256. |
| **High-Cardinality Explosion** | Menambahkan `task_input_prompt` atau rentang teks dinamis sebagai label Prometheus metric. | Database time-series (TSDB) crash akibat jutaan time-series unik dibuat dalam hitungan jam. | Gunakan Prometheus strictly untuk metadata diskrit berkardinalitas rendah (team_id, model, status); simpan metadata leksikal di Jaeger/ClickHouse. |
| **Silent Model Deprecation** | Penyedia LLM memperbarui bobot model internal (*stealth fine-tuning*) di balik tag model statis. | Penurunan drastis pada *Tool Call Precision* tanpa adanya error HTTP dari penyedia model. | Jalankan *Continuous Golden Dataset Canary Test* secara terjadwal untuk memvalidasi output model terhadap ground-truth baseline. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan arsitektur dalam observabilitas sistem AI melibatkan kompromi teknis:

#### A. Sampling Strategy: 100% Trace Recording vs. Tail-Based Sampling
*   **100% Trace Recording**:
    *   *Kelebihan*: Auditability penuh. Setiap insiden keselamatan (*safety breach*), halusinasi, atau anomali dapat direkonstruksi secara absolut.
    *   *Kekurangan*: Biaya penyimpanan astronomis. Menyimpan jutaan token input/output setiap hari di database analitik membebani anggaran operasional.
    *   *Trade-off*: Gunakan **Tail-Based Sampling**. Rekam 100% trace yang menghasilkan status `ERROR`, latency $> \text{p95}$, atau biaya $> \$0.50$. Untuk eksekusi normal yang sukses, sampling secara deterministik hanya 1% hingga 5%.

#### B. LLM Evaluation Pipeline: In-line Evaluation vs. Asynchronous Evaluation
*   **In-line Evaluation (LLM-as-a-judge dalam request path)**:
    *   *Kelebihan*: Kemampuan untuk memblokir respons toksik atau halusinasi secara langsung sebelum mencapai user.
    *   *Kekurangan*: Menambah latensi 1.5 - 3 detik pada end-to-end response time; melipatgandakan konsumsi token per request.
*   **Asynchronous Evaluation (via Message Broker)**:
    *   *Kelebihan*: Zero-latency impact pada user path; evaluasi dapat dibatasi (*rate-limited*) dan menggunakan model evaluasi yang lebih besar.
    *   *Kekurangan*: Sifatnya reaktif. Pengguna sudah terpapar konten bermasalah sebelum sistem memicu alert keselamatan.
    *   *Rekomendasi*: Gunakan *Deterministic Regex/Heuristic In-line* untuk filter instan keamanan dasar, lalu gunakan *LLM-as-a-judge Asynchronous* untuk scoring observabilitas komprehensif.

---

### 9. Best Practices & Standar Industri

Sebagai Engineering Manager yang mengarahkan platform AI tingkat lanjut, standar operasional berikut harus diterapkan:

1.  **Standarisasi OpenInference / OpenTelemetry GenAI Semantic Conventions**:
    Gunakan atribut semantik standar OTel, bukan skema custom:
    *   `gen_ai.system`: Identifier vendor (e.g., `openai`, `anthropic`).
    *   `gen_ai.request.model`: Model yang diminta oleh aplikasi.
    *   `gen_ai.response.model`: Model fisik yang melayani inferensi.
    *   `gen_ai.usage.prompt_tokens` & `gen_ai.usage.completion_tokens`.
2.  **Definisi SLO Khusus Agentic System**:
    Buat Service Level Objectives yang merefleksikan karakter probabilistik:
    *   *Availability SLO*: 99.5% dari semua inisiasi task selesai tanpa internal platform error (eksklusif dari API provider failures).
    *   *Performance SLO*: P90 Time-To-First-Token $< 800\text{ms}$ untuk request streaming.
    *   *Convergence SLO*: P95 Agent Steps per Task $\le 6$ langkah.
    *   *Fidelity SLO*: $98\%$ query RAG memiliki skor Context Relevance $> 0.80$.
3.  **Dynamic FinOps Circuit Breakers**:
    *   Tetapkan *hard budget caps* per `team_id` dan per `agent_id`.
    *   Jika pemakaian mencapai 80% dari batas harian: Turunkan prioritas (*fallback*) dari model frontier ke model open-source yang lebih murah (misal: dari gpt-4o ke llama-3.1-70b-instruct).
    *   Jika pemakaian mencapai 100%: Tolak eksekusi task otonom non-kritis secara otomatis dengan status HTTP 429 (*Quota Exceeded*).
4.  **PII Sanitization At The Edge**:
    *   Lakukan redaksi data pribadi sensitif (KTP, nomor kartu kredit, identitas personal) pada layer OpenTelemetry Collector processor sebelum payload disimpan di storage terpusat untuk mematuhi regulasi privasi data.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan menginvestigasi sebuah Autonomous Agent yang dilaporkan mengalami lonjakan latensi drastis dan membengkakkan biaya tagihan LLM sebesar 400% dalam satu hari.

#### Target Lab
1. Menjalankan skrip instrumen lokal yang memicu agent run dengan *infinite tool-loop*.
2. Membaca metrik Prometheus dan Span OTel untuk mengidentifikasi akar masalah (*root-cause*).
3. Menerapkan *budget enforcement limiter* untuk menahan degradasi sistem.

#### Langkah 1: Persiapan Environment
Pastikan dependensi terpasang di runtime Python Anda:
```bash
pip install prometheus-client opentelemetry-api opentelemetry-sdk
```

#### Langkah 2: Buat Skrip Simulasi Kegagalan (`lab_agent_simulation.py`)
```python
import time
from agent_observability import AgentObservabilityLifecycle, TokenUsage

def faulty_agent_execution():
    obs = AgentObservabilityLifecycle(agent_id="data-extractor-v2", team_id="analytics")
    obs.start_agent_run(session_id="err-run-101", task_objective="Extract financial data from corrupted PDF")
    
    total_cost = 0.0
    max_steps_allowed = 15 # Simulasi looping berlebih
    
    for step in range(1, max_steps_allowed + 1):
        with obs.track_step(step_number=step, step_name=f"Parse-Step-{step}"):
            # Simulasi LLM terus menerus memanggil parser yang gagal membaca data
            usage = TokenUsage(prompt_tokens=4000, completion_tokens=300)
            cost = obs.record_llm_inference(model_name="gpt-4o", usage=usage, context_limit=128000)
            total_cost += cost
            
            # Simulasi tool selalu gagal mengekstrak schema yang benar
            tool_success = False
            obs.record_tool_call(tool_name="unstructured_pdf_parser", success=tool_success, payload_size_bytes=1024)
            
            print(f"Step {step} finished. Incurred cost so far: ${total_cost:.4f}")
            time.sleep(0.1) # Simulasi latensi
            
    obs.finalize_agent_run(terminal_status="FAILED_MAX_STEPS")

if __name__ == "__main__":
    faulty_agent_execution()
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan skrip:
```bash
python lab_agent_simulation.py
```
*Observasi*: Perhatikan bagaimana satu task mengeksekusi 15 langkah berturut-turut tanpa progres nyata, menghabiskan lebih dari 60,000 prompt tokens untuk data yang redundan.

#### Langkah 4: Terapkan Remediasi (Circuit Breaker Guard)
Buka kode agen Anda dan bungkus iterasi reasoning loop dengan pengecekan batas biaya dan batas kegagalan berulang (*consecutive failures limit*):

```python
# Terapkan pola pengaman ini ke dalam loop:
MAX_ALLOWABLE_COST_PER_TASK = 0.20  # USD 20 sen max per query
CONSECUTIVE_TOOL_FAILURES_THRESHOLD = 3

consecutive_failures = 0
accumulated_cost = 0.0

for step in range(1, max_steps_allowed + 1):
    if accumulated_cost >= MAX_ALLOWABLE_COST_PER_TASK:
        obs.finalize_agent_run(terminal_status="CIRCUIT_BREAKER_COST_EXCEEDED")
        raise RuntimeError("Agent terminated: Financial cost ceiling breached.")
        
    if consecutive_failures >= CONSECUTIVE_TOOL_FAILURES_THRESHOLD:
        obs.finalize_agent_run(terminal_status="CIRCUIT_BREAKER_TOOL_COLLAPSE")
        raise RuntimeError("Agent terminated: Downstream tool failed persistently.")
        
    # (Lanjutkan eksekusi terkontrol...)
```

#### Langkah 5: Validasi Hasil
Jalankan kembali simulasi. Sistem harus memutus eksekusi (*short-circuit*) tepat pada Step 3 atau saat limit biaya terlewati, menghentikan kebocoran anggaran komputasi dan memancarkan alarm metrik `agent_executions_total{status="CIRCUIT_BREAKER_TOOL_COLLAPSE"}` ke sistem telemetri.