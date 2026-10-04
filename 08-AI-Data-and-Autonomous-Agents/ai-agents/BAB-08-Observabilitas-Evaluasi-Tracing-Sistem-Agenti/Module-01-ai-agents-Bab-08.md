# Bab 08: Observabilitas, Evaluasi, & Tracing Sistem Agentik

## Module 01: Observabilitas, Distributed Tracing, & Evaluasi Trajektori Sistem Otonom

---

### 1. Learning Objectives (Spesifik & Terukur)
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Mendesain dan Mengimplementasikan Arsitektur Tracing Terdistribusi:** Mengonstruksi trace context propagation end-to-end yang memetakan siklus hidup *agent execution graph* multi-step, mencakup *reasoning loop*, pemanggilan *tool*, dan *dynamic reflection* sesuai konvensi OpenTelemetry GenAI Semantic Conventions.
- **Membangun Telemetry Engine Real-Time:** Mengembangkan telemetry handler modular berlatensi rendah untuk menangkap metrik eksekusi (latensi inferensi, konsumsi token, *tool calling error rate*, dan *state transitions*) secara *asynchronous* tanpa memblokir *runtime agent*.
- **Merancang Automated Evaluation Engine Multi-Tier:** Mengimplementasikan pipeline evaluasi hibrida yang menggabungkan validasi deterministik (AST-based schema assertion, graph edit distance) dan metrik probabilistik berbasis *model-graded evaluation* (*faithfulness*, *tool invocation precision*, *trajectory efficiency*).
- **Mendiagnosis dan Memitigasi Non-Deterministic Failure Modes:** Menganalisis *cascading failures*, *infinite reflection loops*, dan *context drift* menggunakan visualisasi trace graf serta automated regression testing harness.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Mengamati arsitektur software tradisional (microservices) bertumpu pada premis deterministik: *Request* $A$ memicu *Path* $B$ melalui dependency graph yang telah ditentukan secara statis. Kegagalan umumnya berupa unhandled exception, timeout, atau status code non-200.

Sistem Agentik menghancurkan paradigma ini. Sebuah agent otonom adalah sistem stokastik berbasis Directed Acyclic Graph (DAG) dinamis yang jalurnya dikonstruksi secara runtime oleh LLM (*stochastic planner*). Sebuah request dapat mengeksekusi $N$ iterasi reasoning loop, menghasilkan percabangan eksekusi yang berbeda untuk prompt yang identik. Kegagalan fatal sering kali menghasilkan status HTTP 200 OK dengan payload jawaban yang koheren secara sintaktis, namun salah secara faktual (*hallucinated tool arguments*, *infinite self-correction*, atau *silent trajectory deviation*).

```
Traditional Tracing (Static Path):
Client ──► Gateway [Span A] ──► Auth Service [Span B] ──► Database [Span C]

Agentic Tracing (Dynamic Stochastic DAG):
Client ──► Agent Orchestrator [Root Span]
               ├── Loop 01: Plan & Reason [Span 1]
               │     └── LLM Inference (Model: Claude 3.5 Sonnet, 1.2k tokens)
               ├── Loop 01: Tool Execution [Span 2] (args: {"query": "SELECT..."})
               │     └── Database Engine (Status: SQL Syntax Error)
               ├── Loop 02: Reflection & Re-planning [Span 3]
               │     └── LLM Inference (Context updated with SQL Error)
               └── Loop 02: Tool Execution [Span 4] (args: {"query": "SELECT..."})
                     └── Final Synthesis [Span 5]
```

Oleh karena itu, sistem observabilitas agentik memerlukan tiga pilar terpadu:
1. **Structural Tracing (Lineage & Context):** Melacak silsilah hierarki *thought $\rightarrow$ action $\rightarrow$ observation $\rightarrow$ reflection* beserta snapshot state memory dan context window pada setiap langkah.
2. **Resource & Cost Instrumentation:** Monitoring konsumsi token (input, output, cache-read, cache-write) dan latensi per komponen untuk mencegah ledakan biaya eksponensial.
3. **Trajectory & Behavioral Evaluation:** Menilai apakah urutan aksi (*trajectory*) yang diambil oleh agent optimal, aman, dan tepat sasaran dibandingkan dengan *ground-truth execution plan*.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Di lingkungan produksi enterprise, agen otonom menghadapi tantangan operasional kritis:

- **Silent Reasoning Failures:** Agent mengambil tool yang salah, menerima output error, mencoba recovery secara keliru, dan mengembalikan jawaban fabrikasi ke pengguna tanpa memicu HTTP 5xx. Tanpa tracing granular, tim platform engineer tidak memiliki visibilitas atas titik degradasi.
- **Cost Runaway:** Loop refleksi tanpa batas (*infinite loops*) atau tool output bervolume masif yang di-inject kembali ke prompt context dapat membakar ribuan dolar dalam hitungan jam jika tidak ada pemutusan sirkuit (*circuit breaker*) berbasis observabilitas token real-time.
- **Auditability & Regulatory Compliance:** Regulasi seperti EU AI Act mewajibkan sistem AI berisiko tinggi memiliki logging komprehensif atas keputusan otomatis, parameter eksekusi, data pihak ketiga yang diakses, dan intervensi keamanan (*guardrails*).
- **Evaluation Drift:** Perubahan minor pada system prompt, model checkpoint (misalnya update minor provider LLM), atau skema API tool dapat menurunkan akurasi sistem secara senyap. Pipeline evaluasi otomatis diperlukan dalam CI/CD untuk memblokir regresi sebelum mencapai tahap rilis.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur observabilitas dan evaluasi modern dirancang *decoupled* dari runtime eksekusi utama, meminimalkan latensi overhead melalui pemrosesan *asynchronous queue* dan *out-of-band evaluation*.

```
+---------------------------------------------------------------------------------------+
|                                    AGENT CORE ENGINE                                  |
|                                                                                       |
|   +-----------------------+     State/Context      +------------------------------+   |
|   |   Agent Controller    | <--------------------> | Execution Context / Memory   |   |
|   +-----------------------+                        +------------------------------+   |
|               |                                                   |                   |
|               | Interceptors / Hooks (Pre/Post Invoke)            | Context Carrier   |
|               v                                                   v                   |
|   +-------------------------------------------------------------------------------+   |
|   |                     Telemetry Middleware & Context Propagation                 |   |
|   +-------------------------------------------------------------------------------+   |
+--------------------------------------|------------------------------------------------+
                                       |
                     Async Events / Spans (OTel Compatible)
                                       v
+---------------------------------------------------------------------------------------+
|                              OBSERVABILITY INGESTION PIPELINE                         |
|                                                                                       |
|   +--------------------+     Ring Buffer /     +----------------------------------+   |
|   |  OTel Collector /  | --------------------> | Background Exporter (Batching)   |   |
|   |  Agent Ingest API  |                       +----------------------------------+   |
|   +--------------------+                                         |                    |
+------------------------------------------------------------------|--------------------+
                                                                   |
                                    +------------------------------+
                                    |
                                    v
+---------------------------------------------------------------------------------------+
|                          STORAGE, EVALUATION, & ANALYTICS                             |
|                                                                                       |
|   +---------------------------------------+   +-----------------------------------+   |
|   | OLAP Trace Store (ClickHouse/Elastic) |   | Automated Trajectory Evaluator    |   |
|   |  - Trace Graph & DAG Reconstruction   |   |  - Schema & Tool Invocation Match |   |
|   |  - Token & Latency Metrics Aggregation|   |  - Hallucination / Faithfulness   |   |
|   +---------------------------------------+   |  - LLM-as-a-Judge Worker (Async)  |   |
|                                               +-----------------------------------+   |
|                                                                 |                     |
|   +-------------------------------------------------------------v-----------------+   |
|   | CI/CD Gating & Alerting Engine (SLO breaches, Trajectory drift alerts)        |   |
|   +-------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. OpenTelemetry GenAI Semantic Conventions & Context Propagation
Tracing agentik modern mengadopsi standar semantic conventions OpenTelemetry (OTel). Setiap siklus eksekusi memelihara `TraceContext` yang disuntikkan ke dalam panggilan *asynchronous task*.
1. **Trace:** Merepresentasikan seluruh siklus hidup penyelesaian tugas dari input pengguna hingga output final.
2. **Root Span:** Mengidentifikasi eksekusi agen secara keseluruhan (`invoke_agent`).
3. **Internal Spans:**
   - `gen_ai.reasoning`: Mengenkapsulasi komputasi perencana, *prompt template rendering*, dan output token inferensi. Atribut: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.prompt_tokens`, `gen_ai.usage.completion_tokens`.
   - `gen_ai.tool`: Mengenkapsulasi eksekusi fungsi/tool. Atribut: `gen_ai.tool.name`, `gen_ai.tool.arguments`, `gen_ai.tool.status`.
   - `gen_ai.evaluation`: Menandai evaluasi inline atau runtime guardrail checks.

#### B. Trajectory Evaluation Mechanics
Mengevaluasi agen tidak cukup dengan membandingkan teks jawaban akhir dengan string acuan (*exact string match*). Kita harus mengevaluasi *trajectory*—urutan transisi state dan pemanggilan tool:
- **Trajectory Edit Distance (TED):** Menghitung jarak struktural minimum (berbasis varian Levenshtein Distance pada DAG) antara urutan tool aktual ($T_{\text{actual}}$) dan urutan tool optimal ($T_{\text{gold}}$):
  
  $$\text{TED}(T_a, T_g) = \min_{\text{ops}} \sum \text{Cost}(\text{op})$$

- **Tool Call Argument Accuracy:** Verifikasi parameter berbasis AST (*Abstract Syntax Tree*) atau pencocokan skema JSON parsial untuk memastikan agen tidak melakukan inferensi nilai di luar rentang valid.
- **Context Pollution Rate:** Mengukur rasio token tidak relevan yang terakumulasi di memori kerja akibat eksekusi tool berulang yang tidak efektif.

#### C. Model-Graded Evaluation (LLM-as-a-Judge)
Untuk evaluasi kualitas semantik (*faithfulness*, *relevance*, *agent toxicity*), LLM independen digunakan sebagai evaluator dengan rubric terstruktur (*Chain-of-Thought Rubric Evaluation*). Untuk mengatasi bias umum LLM Judge (*positional bias*, *verbosity bias*, dan *self-enhancement bias*), pipeline menerapkan:
1. **Few-shot Calibration:** Memberikan referensi scoring yang dinormalisasi pada prompt juri.
2. **Structured Output Enforcement:** Memaksa juri mengeluarkan reasoning token terlebih dahulu sebelum memberikan skor diskrit/skalar via strict JSON schema.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi *production-ready* arsitektur tracing dan evaluasi sistem agentik berbasis Python murni (dengan `pydantic` dan `asyncio`). Implementasi ini mencakup:
1. Context propagation via contextvars.
2. OpenTelemetry-compliant structured tracing engine.
3. Automated multi-tier evaluator (Deterministic Tool Matcher & Model-Graded Evaluator).
4. Full type hinting, comprehensive error handling, dan modular design.

```python
"""
agentic_observability.py
Enterprise-grade Distributed Tracing and Evaluation Engine for Agentic Systems.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Protocol, Tuple
from pydantic import BaseModel, Field, ValidationError

# Configure structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AgentObservability")


# ============================================================================
# 1. CORE DOMAIN SCHEMAS (OpenTelemetry Semantic Conventions Aligned)
# ============================================================================

class SpanKind(str, Enum):
    AGENT = "agent"
    REASONING = "reasoning"
    TOOL = "tool"
    EVALUATION = "evaluation"


class SpanStatus(str, Enum):
    OK = "OK"
    ERROR = "ERROR"


@dataclass
class UsageMetrics:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0

    def merge(self, other: UsageMetrics) -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.cached_tokens += other.cached_tokens


@dataclass
class AgentSpan:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    kind: SpanKind
    start_time: float
    end_time: Optional[float] = None
    status: SpanStatus = SpanStatus.OK
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    usage: UsageMetrics = field(default_factory=UsageMetrics)
    error_message: Optional[str] = None

    def finish(self, status: SpanStatus = SpanStatus.OK, error: Optional[str] = None) -> None:
        self.end_time = time.perf_counter()
        self.status = status
        self.error_message = error

    @property
    def latency_ms(self) -> float:
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000.0


# ============================================================================
# 2. CONTEXT PROPAGATION & TRACER
# ============================================================================

current_trace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_trace_id", default=None)
current_span_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_span_id", default=None)


class TraceExporter(Protocol):
    async def export(self, spans: List[AgentSpan]) -> None:
        ...


class InMemoryTraceExporter:
    """Thread-safe trace repository for analysis, storage, and evaluation."""
    def __init__(self) -> None:
        self.spans: List[AgentSpan] = []
        self._lock = asyncio.Lock()

    async def export(self, spans: List[AgentSpan]) -> None:
        async with self._lock:
            self.spans.extend(spans)
            for span in spans:
                logger.debug(
                    f"Exported Span: {span.name} [{span.kind.value}] - "
                    f"TraceID: {span.trace_id[:8]} - Latency: {span.latency_ms:.2f}ms"
                )

    async def get_trace(self, trace_id: str) -> List[AgentSpan]:
        async with self._lock:
            return [s for s in self.spans if s.trace_id == trace_id]


class AgentTracer:
    """Orchestrates distributed tracing lifecycle and context propagation."""
    def __init__(self, exporter: TraceExporter) -> None:
        self.exporter = exporter
        self._buffer: List[AgentSpan] = []
        self._lock = asyncio.Lock()

    def start_trace(self, root_name: str) -> Tuple[str, str]:
        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex
        current_trace_id.set(trace_id)
        current_span_id.set(span_id)
        return trace_id, span_id

    def span(self, name: str, kind: SpanKind, attributes: Optional[Dict[str, Any]] = None) -> TraceSpanContextManager:
        return TraceSpanContextManager(self, name, kind, attributes or {})

    async def record_span(self, span: AgentSpan) -> None:
        async with self._lock:
            self._buffer.append(span)
            if len(self._buffer) >= 10:  # Batch threshold
                to_export = list(self._buffer)
                self._buffer.clear()
                asyncio.create_task(self.exporter.export(to_export))

    async def flush(self) -> None:
        async with self._lock:
            if self._buffer:
                to_export = list(self._buffer)
                self._buffer.clear()
                await self.exporter.export(to_export)


class TraceSpanContextManager:
    """Context manager handling span hierarchy and scope management."""
    def __init__(
        self,
        tracer: AgentTracer,
        name: str,
        kind: SpanKind,
        attributes: Dict[str, Any],
    ) -> None:
        self.tracer = tracer
        self.name = name
        self.kind = kind
        self.attributes = attributes
        self.span: Optional[AgentSpan] = None
        self._prev_span_id: Optional[str] = None

    async def __aenter__(self) -> AgentSpan:
        trace_id = current_trace_id.get()
        if not trace_id:
            trace_id, _ = self.tracer.start_trace(self.name)

        parent_id = current_span_id.get()
        self._prev_span_id = parent_id

        new_span_id = uuid.uuid4().hex
        current_span_id.set(new_span_id)

        self.span = AgentSpan(
            trace_id=trace_id,
            span_id=new_span_id,
            parent_span_id=parent_id,
            name=self.name,
            kind=self.kind,
            start_time=time.perf_counter(),
            attributes=dict(self.attributes),
        )
        return self.span

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.span:
            if exc_val:
                self.span.finish(status=SpanStatus.ERROR, error=str(exc_val))
            else:
                self.span.finish(status=SpanStatus.OK)
            await self.tracer.record_span(self.span)

        current_span_id.set(self._prev_span_id)


# ============================================================================
# 3. EVALUATION ENGINE: DETERMINISTIC & MODEL-GRADED
# ============================================================================

class TrajectoryStep(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]


class TrajectoryEvaluationResult(BaseModel):
    is_valid: bool
    path_efficiency_score: float  # Scale 0.0 - 1.0 (Optimal: 1.0)
    matched_steps: int
    total_expected_steps: int
    deviations: List[str]


class JudgeVerdict(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized score between 0.0 and 1.0")
    reasoning: str
    hallucination_detected: bool


class AgentEvaluator:
    """Performs multi-tier evaluation over execution traces."""

    @staticmethod
    def evaluate_trajectory_deterministic(
        actual_spans: List[AgentSpan],
        expected_trajectory: List[TrajectoryStep]
    ) -> TrajectoryEvaluationResult:
        """
        Calculates deterministic alignment and tool execution compliance.
        """
        tool_spans = [s for s in actual_spans if s.kind == SpanKind.TOOL and s.status == SpanStatus.OK]
        deviations: List[str] = []
        matched = 0

        # Structural comparison
        for idx, expected in enumerate(expected_trajectory):
            if idx >= len(tool_spans):
                deviations.append(f"Missing expected step {idx}: '{expected.tool_name}'")
                continue

            actual = tool_spans[idx]
            actual_tool = actual.attributes.get("gen_ai.tool.name")
            actual_args = actual.attributes.get("gen_ai.tool.arguments", {})

            if actual_tool != expected.tool_name:
                deviations.append(
                    f"Step {idx} mismatch: expected tool '{expected.tool_name}', got '{actual_tool}'"
                )
            else:
                # Compare critical keys
                arg_mismatch = False
                for k, v in expected.arguments.items():
                    if actual_args.get(k) != v:
                        deviations.append(
                            f"Step {idx} tool '{actual_tool}' argument mismatch for key '{k}': "
                            f"expected '{v}', got '{actual_args.get(k)}'"
                        )
                        arg_mismatch = True
                if not arg_mismatch:
                    matched += 1

        # Check for extraneous calls (inefficiency / looping)
        if len(tool_spans) > len(expected_trajectory):
            redundant_count = len(tool_spans) - len(expected_trajectory)
            deviations.append(f"Trajectory contains {redundant_count} redundant tool invocation(s)")

        total_expected = len(expected_trajectory)
        if total_expected == 0:
            efficiency_score = 1.0 if len(tool_spans) == 0 else 0.0
        else:
            # Penalize missing steps and redundant calls
            efficiency_score = max(0.0, (matched - (len(tool_spans) - matched)) / float(total_expected))

        return TrajectoryEvaluationResult(
            is_valid=(len(deviations) == 0),
            path_efficiency_score=round(efficiency_score, 2),
            matched_steps=matched,
            total_expected_steps=total_expected,
            deviations=deviations
        )

    @staticmethod
    async def evaluate_faithfulness_llm_judge(
        context: str,
        query: str,
        response: str,
        judge_llm_client: Optional[Callable[[str], Coroutine[Any, Any, str]]] = None
    ) -> JudgeVerdict:
        """
        LLM-as-a-judge for faithfulness assessment.
        Accepts an injected async LLM mock/client callable.
        """
        prompt = f"""[SYSTEM: High-Precision Evaluation Engine]
Evaluate whether the Agent's Response is strictly faithful to and fully supported by the Provided Context.
Do not assume facts outside the Context.

Context:
{context}

User Query:
{query}

Agent Response:
{response}

Emit response in pure JSON format conforming precisely to:
{{
    "score": <float 0.0 to 1.0>,
    "reasoning": "<concise chain-of-thought>",
    "hallucination_detected": <true|false>
}}
"""
        try:
            if judge_llm_client is None:
                # Default deterministic fallback judge mock for testing without external keys
                await asyncio.sleep(0.05)  # Simulate network latency
                return JudgeVerdict(
                    score=0.95,
                    reasoning="All entities in the response correlate directly to the contextual source.",
                    hallucination_detected=False
                )

            raw_eval = await judge_llm_client(prompt)
            data = json.loads(raw_eval)
            return JudgeVerdict(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Judge evaluation failed to parse response: {e}")
            return JudgeVerdict(
                score=0.0,
                reasoning=f"Judge failed with formatting/validation exception: {str(e)}",
                hallucination_detected=True
            )


# ============================================================================
# 4. EXECUTABLE END-TO-END DEMO SYSTEM
# ============================================================================

class MockAgentSystem:
    """Simulates an autonomous agent with instrumented tools and LLM steps."""
    def __init__(self, tracer: AgentTracer) -> None:
        self.tracer = tracer

    async def _mock_llm_call(self, prompt: str) -> Tuple[str, UsageMetrics]:
        await asyncio.sleep(0.08)  # Simulate inference latency
        return (
            "Thought: I need to query customer status from the database.",
            UsageMetrics(prompt_tokens=150, completion_tokens=45, total_tokens=195)
        )

    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        async with self.tracer.span(
            name=f"ToolCall:{tool_name}",
            kind=SpanKind.TOOL,
            attributes={"gen_ai.tool.name": tool_name, "gen_ai.tool.arguments": args}
        ) as span:
            await asyncio.sleep(0.05)  # Simulate tool execution
            if tool_name == "sql_query":
                if "INVALID" in args.get("query", ""):
                    raise ValueError("SQLSyntaxError: relation does not exist")
                result = {"status": "success", "rows": [{"id": 101, "tier": "enterprise"}]}
                span.attributes["gen_ai.tool.result"] = result
                return result
            raise NotImplementedError(f"Tool {tool_name} not found")

    async def run(self, user_query: str) -> str:
        trace_id, _ = self.tracer.start_trace("AgentWorkflow")
        
        async with self.tracer.span(
            name="InvokeAgent",
            kind=SpanKind.AGENT,
            attributes={"user.query": user_query}
        ) as root_span:
            
            # Step 1: Reasoning
            async with self.tracer.span("ReasoningPhase", kind=SpanKind.REASONING) as reason_span:
                thought, usage = await self._mock_llm_call(user_query)
                reason_span.usage = usage
                reason_span.attributes["agent.thought"] = thought
                root_span.usage.merge(usage)

            # Step 2: Tool Execution
            tool_args = {"query": "SELECT tier FROM customers WHERE id = 101;"}
            tool_res = await self.execute_tool("sql_query", tool_args)

            # Step 3: Synthesis
            async with self.tracer.span("FinalSynthesis", kind=SpanKind.REASONING) as synth_span:
                await asyncio.sleep(0.04)
                synth_usage = UsageMetrics(prompt_tokens=210, completion_tokens=30, total_tokens=240)
                synth_span.usage = synth_usage
                root_span.usage.merge(synth_usage)
                final_answer = f"The customer tier is verified as {tool_res['rows'][0]['tier']}."
                root_span.attributes["agent.output"] = final_answer

            return final_answer


async def main() -> None:
    print("=" * 80)
    print("RUNNING AGENT OBSERVABILITY & EVALUATION PIPELINE")
    print("=" * 80)

    exporter = InMemoryTraceExporter()
    tracer = AgentTracer(exporter=exporter)
    agent = MockAgentSystem(tracer=tracer)

    # 1. Execute agent task
    query = "Check subscription tier for customer #101"
    print(f"\n[1] Invoking Agent with Query: '{query}'")
    answer = await agent.run(query)
    await tracer.flush()
    print(f"[+] Agent Execution Finished. Result:\n    '{answer}'")

    # 2. Extract Trace
    trace_id = current_trace_id.get()
    assert trace_id is not None
    spans = await exporter.get_trace(trace_id)
    print(f"\n[2] Captured {len(spans)} Spans for Trace ID: {trace_id}")
    for s in spans:
        print(f"    - Span: {s.name:<25} | Kind: {s.kind.value:<10} | Latency: {s.latency_ms:>6.2f}ms | Status: {s.status.value}")

    # 3. Trajectory Evaluation (Deterministic)
    print("\n[3] Evaluating Trajectory against Gold Standard Plan...")
    expected_plan = [
        TrajectoryStep(
            tool_name="sql_query",
            arguments={"query": "SELECT tier FROM customers WHERE id = 101;"}
        )
    ]
    trajectory_eval = AgentEvaluator.evaluate_trajectory_deterministic(spans, expected_plan)
    print(f"    -> Trajectory Valid: {trajectory_eval.is_valid}")
    print(f"    -> Path Efficiency Score: {trajectory_eval.path_efficiency_score * 100}%")
    print(f"    -> Deviations: {trajectory_eval.deviations if trajectory_eval.deviations else 'None'}")

    # 4. Semantic / Faithfulness Evaluation (LLM-as-a-judge)
    print("\n[4] Running LLM-as-a-Judge Faithfulness Verification...")
    context_data = "Customer #101 has enterprise tier access verified by Billing DB."
    judge_result = await AgentEvaluator.evaluate_faithfulness_llm_judge(
        context=context_data,
        query=query,
        response=answer
    )
    print(f"    -> Faithfulness Score: {judge_result.score}")
    print(f"    -> Hallucination Detected: {judge_result.hallucination_detected}")
    print(f"    -> Reasoning: {judge_result.reasoning}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes (Mitigasi & Recovery)

| Failure Mode | Mekanisme & Dampak | Deteksi Tracing | Pola Mitigasi Arsitektural |
| :--- | :--- | :--- | :--- |
| **Runaway Loop (Infinite Reflection)** | Agent mengalami parsing error berulang dari model output atau kegagalan tool, memicu loop koreksi tanpa henti yang menghabiskan kuota token. | Deteksi span reasoning berulang dengan parent yang sama tanpa progres state ($N > \text{threshold}$). | **Circuit Breaker Span:** Inject tracer middleware yang menghitung frekuensi loop dan melempar `MaxTrajectoryHopsExceededException` jika melebihi batas (misal: 5 hops). |
| **Silent Payload Truncation** | Tool mengembalikan payload data sangat besar (misal: dumping 10k rows JSON). Agent context terpotong secara instan, menghasilkan penalaran yang terdistorsi. | Span tool mencatat bytes size di atas p99 atau `truncated=True` attribute. | **Payload Interceptor:** Masking dan ringkasan otomatis (*summarization hook*) sebelum payload ditulis ke span trace dan context memory. |
| **Context Window Bleed / PII Leak** | Data sensitif pengguna (PII, credentials) diteruskan ke tool arguments dan tersimpan permanen di trace backend tanpa enkripsi. | Static Regex / Entropy analyzer pada attribute ingestion pipeline. | **Trace Redaction Sanitizer:** Terapkan pipeline transformasi trace pada exporter level untuk melakukan regex substitution (`[REDACTED]`) terhadap SSN, credit cards, dan API keys. |
| **Judge Flakiness (LLM Variance)** | Evaluator berbasis LLM memberikan skor yang tidak konsisten untuk eksekusi trace yang sama akibat nondeterminisme inferensi juri. | Perhitungan standard deviasi skor antar batch run melebihi batas toleransi (> 0.15). | **Self-Consistency Sampling:** Jalankan judge 3 kali dengan $T=0.3$, lalu ambil nilai median atau implementasikan few-shot anchor rubric berstandar JSON Schema. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan desain dalam infrastruktur observabilitas agen memiliki konsekuensi arsitektural:

```
+-----------------------------------------------------------------------------------------+
|                              TRACING ARCHITECTURE TRADEOFFS                             |
+-----------------------------------------------------------------------------------------+
| Synchronous In-line Tracing                     Async Ring-Buffer Exporter             |
| - Low memory footprint                          - Zero overhead on critical path        |
| - High latency penalty on inference (P99 spikes) - Risk of trace loss on sudden crash    |
+-----------------------------------------------------------------------------------------+
| Proprietary SaaS (LangSmith, Phoenix)           Open-Source OTel + ClickHouse           |
| - Zero maintenance, turnkey analytics UI        - Complete data residency compliance    |
| - Vendor lock-in, high volume cost ($$$)        - Requires pipeline maintenance         |
+-----------------------------------------------------------------------------------------+
| LLM-as-a-Judge Scoring                          Deterministic Rule-Based Assertions     |
| - High semantic understanding                   - Zero token cost, sub-millisecond      |
| - High cost, slow, non-deterministic            - Fragile against natural phrasing drift|
+-----------------------------------------------------------------------------------------+
```

#### Detail Perbandingan Evaluasi
1. **Model-Graded Evaluation (LLM-as-a-Judge)**
   - *Pros:* Mampu mengevaluasi penalaran bebas, pemahaman konteks tersirat, dan nuansa percakapan manusia.
   - *Cons:* Menambah latensi signifikan (bisa 1–3 detik per evaluasi), menambah beban biaya inferensi, rentan *self-bias*.
2. **Deterministic Syntactic Assertions (JSON-Schema, AST, Exact Tool Path)**
   - *Pros:* Eksekusi sub-milidetik, deterministik 100%, biaya komputasi nol, sangat cocok sebagai security & schema gate pada automated CI/CD build.
   - *Cons:* Kaku, sering menghasilkan *false positive* jika agent menemukan rute alternatif yang sebenarnya valid secara semantik.
3. **Rekomendasi Arsitektur:** Gunakan **Hybrid Evaluation Pipeline**. Terapkan validasi deterministik pada runtime jalur kritis (memeriksa skema output dan validitas parameter tool) dan kirim trace ke background worker pool untuk evaluasi mendalam berbasis *LLM Judge* secara asinkron atau terjadwal.

---

### 9. Best Practices & Standar Industri

1. **Context Carrier Propagation:** Selalu injeksikan `traceparent` (W3C standard header) ke metadata tool network calls (HTTP/gRPC) agar sistem downstream dapat menyambungkan span microservice internal ke dalam trace agentik utama.
2. **Dynamic Sampling Strategy:** Terapkan *tail-based sampling*. Simpan 100% trace yang berstatus `ERROR` atau memiliki latensi > p90, dan lakukan sampling (misalnya 5%) untuk trace sukses normal. Hal ini menghemat biaya storage trace hingga 80% tanpa kehilangan visibilitas bug.
3. **Immutability of Evaluation Baselines:** Kunci dataset evaluasi (*golden evaluation dataset*) menggunakan hash checksum dan semantic versioning (`v1.2.0.json`). Jangan pernah mengevaluasi performa model baru terhadap ground truth yang dinamis.
4. **Separation of Concerns:** Jangan biarkan telemetry code mengotori logika bisnis reasoning. Gunakan pola *middleware*, *decorators*, atau *lifecycle hooks* (`on_tool_start`, `on_tool_end`, `on_llm_start`) untuk mengisolasi pelacakan dari eksekusi logika agen.

---

### 10. Hands-on Lab Exercise: Membangun CI Regression Gating Menggunakan Agent Tracing

#### Skenario Lab
Anda adalah Platform AI Engineer di sebuah perusahaan fintech. Tim baru saja memperbarui prompt pada `FinancialAdvisorAgent`. Anda harus membuat automated test suite yang mengeksekusi agen tersebut, memverifikasi bahwa agen memanggil tool yang benar tanpa loop redundan, dan memblokir release jika efisiensi trajektori turun di bawah 80%.

#### Langkah 1: Persiapan Environment
Pastikan Anda memiliki Python 3.10+ terinstal. Buat environment virtual baru dan instal dependencies yang dibutuhkan:
```bash
python -m venv venv
source venv/bin/activate
pip install pydantic pytest
```

#### Langkah 2: Buat File Test Harness (`test_agent_regression.py`)
Simpan implementasi kode dari Bagian 6 ke dalam file bernama `agent_engine.py`. Kemudian buat test file berikut:

```python
"""
test_agent_regression.py
Automated CI regression suite using Tracing and Trajectory Evaluation.
"""

import pytest
import asyncio
from agent_engine import (
    InMemoryTraceExporter,
    AgentTracer,
    MockAgentSystem,
    AgentEvaluator,
    TrajectoryStep,
    current_trace_id
)

@pytest.mark.asyncio
async def test_agent_trajectory_conformance():
    # Arrange
    exporter = InMemoryTraceExporter()
    tracer = AgentTracer(exporter=exporter)
    agent = MockAgentSystem(tracer=tracer)
    query = "Check subscription tier for customer #101"

    # Define the expected strict trajectory
    expected_trajectory = [
        TrajectoryStep(
            tool_name="sql_query",
            arguments={"query": "SELECT tier FROM customers WHERE id = 101;"}
        )
    ]

    # Act
    response = await agent.run(query)
    await tracer.flush()

    trace_id = current_trace_id.get()
    assert trace_id is not None, "Trace ID must be propagated."

    spans = await exporter.get_trace(trace_id)
    assert len(spans) > 0, "Telemetry engine must capture execution spans."

    # Assert: Trajectory Evaluation
    eval_result = AgentEvaluator.evaluate_trajectory_deterministic(spans, expected_trajectory)

    print(f"\n[Test Result] Path Efficiency: {eval_result.path_efficiency_score * 100}%")
    if eval_result.deviations:
        print(f"[Test Result] Deviations: {eval_result.deviations}")

    # Gating Assertions
    assert eval_result.is_valid, f"Trajectory validation failed: {eval_result.deviations}"
    assert eval_result.path_efficiency_score >= 0.8, "Path efficiency fell below production threshold (80%)"
    assert "enterprise" in response.lower(), "Final answer must synthesize retrieved database tier"


@pytest.mark.asyncio
async def test_agent_faulty_tool_recovery():
    # Arrange
    exporter = InMemoryTraceExporter()
    tracer = AgentTracer(exporter=exporter)
    agent = MockAgentSystem(tracer=tracer)

    # Act & Assert Tool Failure Injection
    with pytest.raises(ValueError, match="SQLSyntaxError"):
        await agent.execute_tool("sql_query", {"query": "SELECT * FROM INVALID_TABLE;"})

    await tracer.flush()
    trace_id = current_trace_id.get()
    spans = await exporter.get_trace(trace_id)

    # Assert error tracking inside spans
    error_spans = [s for s in spans if s.status.value == "ERROR"]
    assert len(error_spans) == 1, "The tracer must record failing tool execution as ERROR span status."
    assert "SQLSyntaxError" in error_spans[0].error_message
```

#### Langkah 3: Eksekusi Test Suite
Jalankan pengujian menggunakan `pytest` dengan flag verbose dan capture disable:
```bash
pytest -s -v test_agent_regression.py
```

#### Langkah 4: Verifikasi Hasil Evaluasi
Jika pipeline Anda berjalan sesuai standar, test runner akan memvalidasi silsilah span, memastikan efisiensi trajektori bernilai 1.0 (100%), dan memverifikasi penanganan error status code. Pengujian ini dapat diintegrasikan secara langsung ke dalam workflow GitHub Actions atau GitLab CI sebagai quality gate sistem agen sebelum deployment.