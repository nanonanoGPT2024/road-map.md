# Bab 07: Debugging, Hallucination Mitigation, & Telemetry (Module 01)

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
*   **Menganalisis & Mengklasifikasikan Anomali Agen (Analyze)**: Mengidentifikasi akar penyebab non-deterministik, kegagalan *grounding*, dan deviasi logika pada *autonomous agent loop* menggunakan metrik entropi token dan analisis variansi semantik.
*   **Mengimplementasikan Telemetri GenAI Standar Industri (Apply)**: Mengintegrasikan distributed tracing berbasis OpenTelemetry (OTel) dengan Semantic Conventions untuk Generative AI guna merekam interaksi model, latensi inferensi, konsumsi token, serta eksekusi *tool/function call*.
*   **Merancang Sistem Mitigasi Halusinasi Adaptif (Create)**: Membangun arsitektur *self-reflective guardrail* dan *real-time semantic cross-examination* yang memvalidasi *factual consistency* secara deterministik sebelum respons dikirimkan ke pengguna akhir.
*   **Mengoptimalkan Trade-off Latensi vs. Reliabilitas (Evaluate)**: Mengevaluasi dampak komputasional dan biaya finansial dari berbagai strategi evaluasi (*Self-Consistency*, *Critic Agents*, dan *Deterministic Schema Validation*) pada lingkungan produksi berskala tinggi.

---

## 2. Concept Overview

Dalam pengembangan sistem berbasis *Large Language Models* (LLMs) dan *Autonomous Agents*, paradoks utama terletak pada sifat inferensi probabilistik yang berjalan di atas infrastruktur perangkat lunak deterministik. Fenomena "vibe-coding"—di mana pengembang mengandalkan intuisi cepat dan prototipe fluid dari LLM—sering kali runtuh ketika berhadapan dengan kebutuhan enterprise akibat kegagalan melacak status internal agen dan ketiadaan verifikasi formal.

```
       [ Probabilistic Layer ]              [ Deterministic Infrastructure ]
  +--------------------------------+       +-------------------------------+
  |   LLM / Agent Logic            |  ==>  | Execution Engines             |
  |   - Token Probability Drift    |  <--  | - Transactional DBs           |
  |   - Hallucination / Drift      |       | - External REST/gRPC APIs     |
  +--------------------------------+       +-------------------------------+
                  │                                        ▲
                  ▼                                        │
  +------------------------------------------------------------------------+
  |              Telemetry, Guardrails & Evaluation Subsystem              |
  |  - Token Entropy Analysis        - Real-Time Semantic Interception     |
  |  - OpenTelemetry Spans/Traces    - Synthetic Critique Loop             |
  +------------------------------------------------------------------------+
```

### Mental Model: Siklus Evaluasi Deterministik
Agen otonom bukanlah sekadar *black box* pemanggil API, melainkan *state machine* terdistribusi yang didorong oleh *stochastic state transitions*. Untuk menstabilkannya:
1.  **Observabilitas adalah Prasyarat**: Kita tidak dapat memperbaiki apa yang tidak dapat kita rekonstruksi. Setiap inferensi harus memiliki jejak audit (*trace*) yang merekam *prompt template*, *system state*, *retrieved context*, dan *generation parameters*.
2.  **Halusinasi adalah Kegagalan Sistemik**: Halusinasi bukan sekadar "kebohongan model", melainkan deviasi representasi yang terjadi akibat *attention dispersion*, *loss of context grounding*, atau keterbatasan kompresi pengetahuan parametrik model.
3.  **Intersepsi Berlapis (*Defense-in-Depth*)**: Mitigasi halusinasi harus dilakukan secara berlapis: *Pre-generation* (Grounding & Retrieval validation), *In-generation* (Logit bias & Structured decoding), dan *Post-generation* (Deterministic schema enforcement & Critic verification).

---

## 3. Why It Matters

Di lingkungan enterprise, deployment sistem AI tanpa sistem telemetri dan mitigasi halusinasi menghadirkan risiko katastropik:

*   **Silent Data Corruption**: Berbeda dengan bug perangkat lunak tradisional yang memicu `NullPointerException` atau `panic`, halusinasi LLM sering kali berupa teks atau data JSON yang secara sintaksis valid namun secara semantik destruktif (misalnya, salah menghitung batas kredit atau menghasilkan parameter query SQL fiktif).
*   **Financial & Resource Leakage**: *Infinite autonomous agent loops* tanpa telemetri yang memadai dapat menghabiskan kuota token bernilai ribuan dolar hanya dalam beberapa menit akibat kegagalan parsing respons rekursif.
*   **Regulatory & Compliance Exposure (EU AI Act, HIPAA)**: Ketidakmampuan untuk menjelaskan mengapa sebuah agen mengambil keputusan finansial atau medis tertentu (ketiadaan *distributed audit trail*) melanggar prinsip kepatuhan mendasar mengenai ketertelusuran dan akuntabilitas sistem otonom.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan arsitektur *observability-driven agent loop* yang menggabungkan distributed tracing OTel, *real-time guardrails*, dan sistem evaluasi mandiri (*reflective critic*).

```
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
|                                    ENTERPRISE AGENT RUNTIME PIPELINE                                     |
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
                                                     │
                                             User / Client Prompt
                                                     │
                                                     ▼
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
| 1. TELEMETRY INGESTION & TRACE INITIALIZATION (OpenTelemetry Context Propagation)                      |
|    - Inject TraceID & SpanID                                                                            |
|    - Capture Attributes: user.id, session.id, agent.variant, prompt.raw                                 |
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
                                                     │
                                                     ▼
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
| 2. GROUNDED CONTEXT RETRIEVAL (RAG / Knowledge Augmentation)                                           |
|    - Context Embedding & Similarity Search                                                              |
|    - Span: 'retrieval_service.query' | Metrics: context_relevance_score, retrieved_chunks_count         |
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
                                                     │
                                                     ▼
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
| 3. INFERENCE INTERCEPTOR PROXY                                                                          |
|    - Assemble Prompt (Context + Dynamic State + Task)                                                   |
|    - Span: 'llm.generation' | Record: prompt_tokens, temperature, model_provider                       |
|    - Stream/Awaits LLM Response                                                                        |
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
                                                     │
                         Raw LLM Output + Generation Metadata
                                                     │
                                                     ▼
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
| 4. MITIGATION ENGINE & CRITIC VALIDATOR (Dual-Phase Verification)                                       |
|    ┌──────────────────────────────────────────────┐  ┌────────────────────────────────────────────────┐ |
|    │ Phase A: Deterministic Schema & Type Check   │  │ Phase B: Semantic Grounding & Hallucination    │ |
|    │ - Pydantic Validation / Regex Bounds         │  │ - NLI (Natural Language Inference) Entailment  │ |
|    │ - JSON Schema Structural Conformance         │  │ - Fact Verification against Retrieved Context  │ |
|    └──────────────────────────────────────────────┘  └────────────────────────────────────────────────┘ |
|                                                    │                                                    |
|                                [Is Output Valid & Grounded?]                                            |
|                                        /                \                                               |
|                                    (No)                 (Yes)                                           |
+───────────────────────────────────────┬───────────────────┬─────────────────────────────────────────────+
                                        │                   │
                                        │                   ▼
                                        │    +──────────────────────────────────────────────+
                                        │    | 5. TELEMETRY EXPORT & AUDIT SINK             |
                                        │    |    - Export to Jaeger/OTLP/Prometheus        |
                                        │    |    - Record Metric: hallucination_score = 0  |
                                        │    |    - Send Sanitized Response to Client       |
                                        │    +──────────────────────────────────────────────+
                                        │
                                        ▼
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
| 6. CORRECTIVE FEEDBACK & RETRY ORCHESTRATOR (Max Retries: N)                                            |
|    - Span Event: 'hallucination_detected' with Violation Report                                         |
|    - Synthesize Corrective Error Prompt (Append violations as hard constraints)                          |
|    - Fallback Execution Path if Max Retries Exceeded (Circuit Breaker / Safe Response)                 |
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### A. Anatomi Terjadinya Halusinasi pada Model Bahasa
Secara matematis, LLM menghasilkan token berikutnya $y_t$ berdasarkan distribusi probabilitas kondisional atas kosakata $\mathcal{V}$:

$$P(y_t \mid y_{<t}, \mathbf{x}) = \text{softmax}(W_u h_t)$$

Di mana $\mathbf{x}$ adalah konteks input, $y_{<t}$ adalah token-token yang telah dihasilkan sebelumnya, $h_t$ adalah *hidden state* pada *layer* akhir, dan $W_u$ adalah matriks un-embedding. Halusinasi umumnya berkorelasi dengan:
1.  **High Entropy Distribution**: Ketika distribusi probabilitas mendekati seragam (entropi tinggi), model kehilangan *confidence* dan rentan memilih token yang divergen dari realitas faktual.
2.  **Attention Drift**: Pada sekuens konteks yang panjang, pembobotan *cross-attention* terhadap token fakta dalam konteks Retrieval-Augmented Generation (RAG) dapat melemah akibat *inter-token competition* dari representasi internal model.
3.  **Exposure Bias**: Deviasi kecil pada awal generasi terakumulasi secara autoregresif, membawa status laten ke manifold bahasa yang sepenuhnya terputus dari fakta awal (*hallucinatory cascade*).

### B. Natural Language Inference (NLI) & Metrik Grounding
Untuk memvalidasi bahwa output model $H$ (*Hypothesis*) didukung oleh konteks $P$ (*Premise*), kita menerapkan relasi NLI terformalisasi:

$$\text{Verdict}(P, H) = \begin{cases} 
\text{Entailment} & \text{jika } P \implies H \\
\text{Contradiction} & \text{jika } P \implies \neg H \\
\text{Neutral} & \text{jika } P \not\implies H \land P \not\implies \neg H 
\end{cases}$$

Sebuah respon hanya dianggap **Grounded** dan bebas halusinasi faktual jika setiap proposisi atomik di dalam $H$ memiliki status **Entailment** murni terhadap $P$. Respon dengan status *Neutral* menandakan ekstrapolasi informasi yang tidak disediakan oleh konteks tepercaya (potensi halusinasi parametrik).

### C. Standarisasi OpenTelemetry untuk LLM & Agen
Observabilitas modern tidak bergantung pada print logging lokal. Standar industri menuntut penggunaan OpenTelemetry dengan *semantic conventions* khusus GenAI:
*   `gen_ai.system`: Nama provider (`openai`, `anthropic`, `self_hosted`).
*   `gen_ai.request.model`: Model yang diminta (misal: `gpt-4o`, `claude-3-5-sonnet`).
*   `gen_ai.response.model`: Model riil yang melayani request (mengidentifikasi *silent model routing*).
*   `gen_ai.usage.prompt_tokens`: Jumlah token prompt.
*   `gen_ai.usage.completion_tokens`: Jumlah token output.
*   `agent.state.action`: Tool atau operasi yang dipanggil oleh agen otonom.

---

## 6. Production-Ready Code Implementation

Implementasi berikut menggunakan Python 3.11+ dengan integrasi OpenTelemetry murni, parsing Pydantic v2 deterministik, dan mesin evaluasi *NLI / factual consistency critic* dengan mekanisme *self-healing retry*.

```python
"""
production_agent_observability.py
Enterprise-grade agent execution wrapper with distributed tracing and hallucination mitigation.
Dependencies: opentelemetry-api, opentelemetry-sdk, pydantic>=2.0, httpx
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel, Field, ValidationError

# --- SETUP TELEMETRY BASELINE ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("EnterpriseAgentTelemetry")

provider = TracerProvider()
processor = BatchSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("com.enterprise.agent.core", "1.0.0")


# --- DATA CONTRACTS & SCHEMAS ---
class FinancialAnalysisPayload(BaseModel):
    ticker: str = Field(..., pattern=r"^[A-Z]{1,5}$", description="Valid stock ticker symbol")
    projected_revenue_m: float = Field(..., gt=0.0, description="Projected revenue in Millions USD")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Model confidence calculation")
    assumptions: List[str] = Field(..., min_length=1, description="List of factual assumptions taken")


class ValidationResult(BaseModel):
    is_valid: bool
    grounding_score: float = Field(..., ge=0.0, le=1.0)
    violations: List[str] = Field(default_factory=list)


# --- TELEMETRY CONTEXT & INTERCEPTOR INTERFACES ---
@dataclass
class LLMInteractionMetadata:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    model_name: str


class MockLLMClient:
    """Simulates an LLM API client supporting semantic reflection and generation."""
    
    def __init__(self, simulate_hallucination: bool = False):
        self.simulate_hallucination = simulate_hallucination
        self._execution_count = 0

    async def generate_response(self, system_prompt: str, user_prompt: str) -> Tuple[str, LLMInteractionMetadata]:
        await asyncio.sleep(0.15)  # Simulate network I/O
        self._execution_count += 1
        
        # Inject deterministic hallucination on first run if enabled
        if self.simulate_hallucination and self._execution_count == 1:
            raw_content = json.dumps({
                "ticker": "INVALID_TICKER_XYZ",
                "projected_revenue_m": -50.2,  # Schema violation
                "confidence_score": 0.95,
                "assumptions": ["Context provides this", "Revenue will double naturally"]
            })
        else:
            raw_content = json.dumps({
                "ticker": "ACME",
                "projected_revenue_m": 125.5,
                "confidence_score": 0.88,
                "assumptions": ["Based on 10-Q filing report", "Operating cost reduced by 5%"]
            })
            
        metadata = LLMInteractionMetadata(
            prompt_tokens=len(system_prompt + user_prompt) // 4,
            completion_tokens=len(raw_content) // 4,
            total_tokens=(len(system_prompt + user_prompt) + len(raw_content)) // 4,
            latency_ms=150.0,
            model_name="mock-transformer-ultra-v1"
        )
        return raw_content, metadata

    async def verify_hallucination(self, context: str, response: str) -> Tuple[bool, float, List[str]]:
        """Acts as a secondary NLI Critic Judge checking factual entailment."""
        await asyncio.sleep(0.08)  # Simulate secondary model call
        violations: List[str] = []
        
        # Deterministic check logic for the mock
        if "INVALID_TICKER_XYZ" in response or "-50.2" in response:
            violations.append("Contains negative financial revenue unsupported by reference context.")
            violations.append("Entity 'INVALID_TICKER_XYZ' does not exist in ground-truth documentation.")
            return False, 0.12, violations
            
        return True, 0.96, violations


# --- PRODUCTION GUARD & ORCHESTRATION PIPELINE ---
class RobustAgentPipeline:
    def __init__(self, llm_client: MockLLMClient, max_retries: int = 2):
        self.llm = llm_client
        self.max_retries = max_retries

    async def run(self, user_query: str, ground_truth_context: str) -> FinancialAnalysisPayload:
        with tracer.start_as_current_span("agent_pipeline_execution") as root_span:
            root_span.set_attribute("gen_ai.workflow.name", "FinancialExtractionPipeline")
            root_span.set_attribute("agent.max_retries", self.max_retries)
            
            error_history: List[str] = []
            
            for attempt in range(1, self.max_retries + 2):
                with tracer.start_as_current_span(f"pipeline_attempt_{attempt}") as attempt_span:
                    attempt_span.set_attribute("agent.attempt_number", attempt)
                    
                    # 1. Synthesize Prompt with Error Feedback if Available
                    system_prompt = (
                        "You are an enterprise financial analysis extraction engine. "
                        "Strictly adhere to ground truth context. Generate valid JSON matching schema."
                    )
                    if error_history:
                        feedback = "PREVIOUS ERRORS:\n" + "\n".join(f"- {e}" for e in error_history)
                        system_prompt += f"\n\nCRITICAL FIXES REQUIRED:\n{feedback}"

                    # 2. Invoke LLM with Telemetry Tracking
                    raw_content, meta = await self._call_llm_with_telemetry(system_prompt, user_query)
                    
                    # 3. Layer 1: Syntactic & Schema Validation
                    is_valid_schema, payload, schema_err = self._validate_schema(raw_content)
                    if not is_valid_schema:
                        error_msg = f"Schema Validation Failure: {schema_err}"
                        logger.warning(f"Attempt {attempt}: {error_msg}")
                        error_history.append(error_msg)
                        attempt_span.add_event("schema_validation_failed", {"error.message": error_msg})
                        continue

                    # 4. Layer 2: Semantic Verification / Hallucination Detection
                    is_grounded, grounding_score, violations = await self._verify_grounding(
                        ground_truth_context, raw_content
                    )
                    
                    if not is_grounded:
                        error_msg = f"Hallucination Detected (Score: {grounding_score}): {'; '.join(violations)}"
                        logger.warning(f"Attempt {attempt}: {error_msg}")
                        error_history.append(error_msg)
                        attempt_span.add_event(
                            "hallucination_detected",
                            {
                                "grounding_score": grounding_score,
                                "violations": json.dumps(violations)
                            }
                        )
                        continue

                    # 5. Success Path
                    root_span.set_status(Status(StatusCode.OK))
                    root_span.set_attribute("agent.success_attempt", attempt)
                    logger.info("Pipeline execution successfully completed and grounded.")
                    assert payload is not None  # Guaranteed by schema validator
                    return payload

            # 6. Terminal Fallback / Circuit Break
            root_span.set_status(Status(StatusCode.ERROR, "Max retry budget exceeded. System diverged."))
            logger.error("Terminal failure: System could not remediate hallucination within budget.")
            raise RuntimeError(f"Agent pipeline failed after {self.max_retries + 1} attempts. Errors: {error_history}")

    async def _call_llm_with_telemetry(self, system: str, user: str) -> Tuple[str, LLMInteractionMetadata]:
        with tracer.start_as_current_span("llm_inference_call") as span:
            start_time = time.perf_counter()
            content, meta = await self.llm.generate_response(system, user)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            span.set_attribute("gen_ai.system", "openai_compatible")
            span.set_attribute("gen_ai.request.model", meta.model_name)
            span.set_attribute("gen_ai.usage.prompt_tokens", meta.prompt_tokens)
            span.set_attribute("gen_ai.usage.completion_tokens", meta.completion_tokens)
            span.set_attribute("gen_ai.usage.total_tokens", meta.total_tokens)
            span.set_attribute("llm.latency_ms", elapsed_ms)
            
            return content, meta

    def _validate_schema(self, raw_json: str) -> Tuple[bool, Optional[FinancialAnalysisPayload], Optional[str]]:
        with tracer.start_as_current_span("schema_validator") as span:
            try:
                data = json.loads(raw_json)
                payload = FinancialAnalysisPayload(**data)
                span.set_attribute("validation.schema_matched", True)
                return True, payload, None
            except (json.JSONDecodeError, ValidationError) as e:
                span.set_attribute("validation.schema_matched", False)
                span.record_exception(e)
                return False, None, str(e)

    async def _verify_grounding(self, context: str, response: str) -> Tuple[bool, float, List[str]]:
        with tracer.start_as_current_span("hallucination_critic_evaluator") as span:
            is_valid, score, violations = await self.llm.verify_hallucination(context, response)
            span.set_attribute("eval.grounding_score", score)
            span.set_attribute("eval.is_factual", is_valid)
            span.set_attribute("eval.violations_count", len(violations))
            return is_valid, score, violations


# --- DEMONSTRATION RUNNER ---
async def main() -> None:
    context_fixture = (
        "ACME Corp reported Q3 results. Target projection: Revenue of 125.5 Million USD for next quarter. "
        "Operating costs dropped 5% YoY due to automated processing line updates."
    )
    user_query_fixture = "Extract financial projection summary for ACME."

    print("=== SCENARIO 1: INJECTING SYNTHETIC HALLUCINATION WITH SELF-HEALING ===")
    faulty_client = MockLLMClient(simulate_hallucination=True)
    pipeline = RobustAgentPipeline(llm_client=faulty_client, max_retries=2)
    
    try:
        result = await pipeline.run(user_query=user_query_fixture, ground_truth_context=context_fixture)
        print(f"\nFinal Validated Result:\n{result.model_dump_json(indent=2)}")
    except Exception as exc:
        print(f"Pipeline crashed with error: {exc}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 7. Edge Cases & Failure Modes

Pada level infrastruktur enterprise, integrasi telemetri dan sistem mitigasi dapat memicu kegagalan tingkat sistem jika tidak diantisipasi:

| Skenario Edge Case | Modus Kegagalan (*Failure Mode*) | Dampak Sistem | Strategi Mitigasi / Deteksi |
| :--- | :--- | :--- | :--- |
| **Context Window Saturation during Retries** | Akumulasi *traceback error* dan konteks asli melebihi kapasitas konteks LLM saat perulangan *retry*. | Request *crash* total (`BadRequestError: Context length exceeded`). | Implementasikan *context compression* dan batasan ketat (*hard truncation*) pada pesan koreksi kesalahan. |
| **Echo-Chamber Critic (Sycophancy)** | Model *critic* memvalidasi output halusinasi karena menggunakan model family dan *weights* identik. | Halusinasi lolos ke *production* dengan status *false-positive entailment*. | Gunakan arsitektur *cross-model evaluation* (misal: LLM Critic independen dengan *different parameter weights* atau *regex/symbolic rules*). |
| **Cascading Latency Spike** | Generasi multi-hop yang gagal memicu beruntun *retry* dan *reflection evaluation*. | Latensi p99 meroket dari 800ms menjadi >15 detik, memicu *timeout* pada load balancer. | Terapkan *Deadlines / Context Budgets* global; alokasikan batas waktu absolut per pipeline execution. |
| **Telemetry Ingestion Bottleneck** | Export telemetri OTel yang sinkron (*blocking*) memperlambat runtime inferensi throughput tinggi. | *Agent worker starvation*, peningkatan latensi drastis pada I/O thread. | Gunakan `BatchSpanProcessor` non-blocking dengan buffer memori terbatas dan proses ekspor ke *OTel Collector* asinkron. |

---

## 8. Trade-offs & Alternatif Solusi

| Pendekatan | Kelebihan | Kelemahan | Kasus Penggunaan Ideal |
| :--- | :--- | :--- | :--- |
| **Logit Bias / Strict Decoding (Grammar-based)** | 0% kesalahan sintaksis; determinisme struktural terjamin; zero latency overhead tambahan. | Tidak dapat mendeteksi halusinasi semantik; model dapat menghasilkan nilai faktual salah yang sesuai tata bahasa. | Ekstraksi entitas sederhana, pemilihan ENUM, parsing tipe data primitif. |
| **Self-Reflection (On-Model Critic)** | Mudah diintegrasikan; tidak memerlukan dependensi komputasi eksternal baru. | Bias konfirmasi tinggi (*sycophantic validation*); menambah 1x latensi inferensi. | Low-risk operations; pipeline internal non-finansial; batch processing. |
| **Cross-Examination Dual-Model Engine** | Deteksi deviasi semantik tingkat tinggi; resisten terhadap bias internal satu model. | Biaya operasional token 2x lipat; overhead latensi signifikan ($2\times$ baseline). | Diagnosis medis otomatis, eksekusi transaksi perbankan, kepatuhan hukum. |
| **Vector-based NLI / Cross-Encoder Classifier** | Latensi rendah (~30-50ms); biaya inferensi lokal jauh lebih murah dibanding model frontier. | Terbatas pada perbandingan teks pendek; rentan gagal pada analisis penalaran deduktif multi-langkah. | Validasi RAG berskala jutaan request per hari secara real-time. |

---

## 9. Best Practices & Standard Industri

1.  **PII & Token Redaction di Boundary Telemetri**: Jangan pernah mencatat (*log*) seluruh teks prompt atau respons pengguna tanpa masking. Terapkan interceptor OTel yang secara deterministik menyaring Nomor Induk Kependudukan (NIK), token akses, kartu kredit, dan data medis sebelum di-dispatch ke trace backend.
2.  **Semantic Conventions Compliance**: Standarisasi penamaan atribut tracing sesuai *OpenTelemetry Specification for Generative AI*:
    *   Wajib mencantumkan atribut `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.prompt_tokens`.
    *   Setiap kegagalan grounding harus didokumentasikan sebagai Span Event dengan atribut `event.name = "gen_ai.content.hallucination"`.
3.  **Circuit Breaking & Retry Limits**: Batasi retry semantik maksimal 2 kali. Jika model frontier gagal menstabilkan output setelah 2 iterasi, eksekusi *fallback deterministic static response* atau alihkan kontrol ke operator manusia (*Human-in-the-Loop*).
4.  **Decoupled Evaluation Pipeline**: Pisahkan *evaluasi metrik offline* (seperti penghitungan *RAG Triad*: Faithfulness, Answer Relevance, Context Precision) dari *critical path* produksi melalui sistem antrean pesan asinkron (Kafka/RabbitMQ).

---

## 10. Hands-on Lab Exercise

### Deskripsi Lab
Membangun sistem pipeline inferensi agen untuk e-commerce yang memiliki instrumen telemetri OTel dan mekanisme deteksi halusinasi deterministik. Peserta akan mereproduksi kegagalan halusinasi akibat manipulasi prompt (*adversarial attack*), mengintersepsinya menggunakan unit validator, dan memverifikasi jejak audit telemetri di console.

### Langkah-Langkah

#### Langkah 1: Persiapan Lingkungan
Buat direktori baru dan instal dependensi yang diperlukan:
```bash
mkdir agent-debugging-lab && cd agent-debugging-lab
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install opentelemetry-api opentelemetry-sdk pydantic httpx
```

#### Langkah 2: Buat Skrip Eksperimen (`lab_debug_hallucination.py`)
Salin kode berikut yang mengimplementasikan unit deterministik pencegah halusinasi inventaris:

```python
import asyncio
from typing import Dict
from pydantic import BaseModel, Field, ValidationError
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

# Inisialisasi Tracing ke Console
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("lab.anti_hallucination", "0.1.0")

# Database Mock Deterministic
INVENTORY_DB = {
    "SKU-4021": {"name": "Mechanical Keyboard", "stock": 5, "price": 120.0},
    "SKU-9901": {"name": "USB-C Hub", "stock": 0, "price": 45.0}
}

class OrderExtraction(BaseModel):
    sku: str
    quantity: int = Field(..., gt=0)
    confirmed_price: float

def execute_deterministic_grounding(extracted_data: OrderExtraction) -> bool:
    """Memverifikasi order terhadap sumber kebenaran (Database Inventaris)."""
    with tracer.start_as_current_span("verify_inventory_grounding") as span:
        sku = extracted_data.sku
        span.set_attribute("inventory.target_sku", sku)
        
        if sku not in INVENTORY_DB:
            span.record_exception(ValueError(f"SKU {sku} is a pure hallucination."))
            return False
            
        real_data = INVENTORY_DB[sku]
        if real_data["stock"] < extracted_data.quantity:
            span.set_attribute("inventory.failure_reason", "insufficient_stock")
            return False
            
        if real_data["price"] != extracted_data.confirmed_price:
            span.set_attribute("inventory.failure_reason", "price_mismatch")
            return False
            
        return True

async def simulate_agent_inference(malicious: bool) -> OrderExtraction:
    """Simulasi respon LLM terhadap prompt transaksi."""
    with tracer.start_as_current_span("llm_agent_execution") as span:
        if malicious:
            # LLM Mengarang SKU fiktif dan harga tidak akurat
            raw_output = {"sku": "SKU-FAKED-999", "quantity": 1, "confirmed_price": 10.0}
        else:
            raw_output = {"sku": "SKU-4021", "quantity": 2, "confirmed_price": 120.0}
            
        span.set_attribute("llm.raw_output", str(raw_output))
        return OrderExtraction(**raw_output)

async def run_lab():
    print("--- 1. MENJALANKAN INFERENSI NORMAL ---")
    data_valid = await simulate_agent_inference(malicious=False)
    assert execute_deterministic_grounding(data_valid) == True
    print(">> Validasi Berhasil: Data sepenuhnya ter-grounding.")

    print("\n--- 2. MENJALANKAN INFERENSI RAWAN HALUSINASI ---")
    data_invalid = await simulate_agent_inference(malicious=True)
    is_grounded = execute_deterministic_grounding(data_invalid)
    print(f">> Validasi Selesai: Grounded = {is_grounded} (Halusinasi Terdeteksi & Diblokir)")

if __name__ == "__main__":
    asyncio.run(run_lab())
```

#### Langkah 3: Eksekusi dan Verifikasi Jejak Telemetri
Jalankan program:
```bash
python lab_debug_hallucination.py
```

### Hasil yang Diharapkan
1.  Console mencetak span OpenTelemetry JSON terstruktur yang merekam span `llm_agent_execution` dan `verify_inventory_grounding`.
2.  Pada eksekusi skenario 2, span `verify_inventory_grounding` menangkap status kegagalan dan merekam *exception* `ValueError: SKU SKU-FAKED-999 is a pure hallucination.` dengan atribut konteks yang relevan.
3.  Alur aplikasi tidak mengalami kegagalan crash, melainkan secara deterministik menolak payload sebelum masuk ke layer eksekusi database.