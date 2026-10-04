# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 08-AI-Data-and-Autonomous-Agents  
**Topik:** Prompt Engineering  
**Bab 10:** Enterprise LLM Evaluation, Testing & Observability

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Principal Engineer atau AI Platform Architect diharapkan mampu:
- **Merancang Arsitektur Observabilitas End-to-End**: Mengimplementasikan distributed tracing berbasis OpenTelemetry dan OpenInference standard untuk menangkap setiap siklus rantai inferensi prompt, retrieval, tool invocation, dan token drift.
- **Membangun Automated LLM-as-a-Judge Evaluation Pipeline**: Mengembangkan sistem evaluasi deterministik menggunakan teknik kalibrasi bias (positional, verbosity, dan self-enhancement bias) dengan metrics kustom berbasis G-Eval dan Ragas (Faithfulness, Answer Relevance, Context Recall, Semantic Similarity).
- **Menerapkan CI/CD Regression Testing untuk Prompt**: Mengintegrasikan continuous testing pipeline pada GitHub Actions/GitLab CI untuk memvalidasi perubahan prompt terhadap *golden dataset* sintetis dan historis guna mencegah regresi performa sebelum rilis ke produksi.
- **Mengelola Evaluasi Produksi & Drift Detection**: Mengoperasikan sistem canary deployment untuk prompt, semantic drift monitoring, cost-latency telemetry, serta guardrail dynamic routing pada skala multi-region.

---

## 2. Prerequisite

Peserta diasumsikan telah menguasai:
- **Python 3.11+ Lanjutan**: Pemrograman asinkron (`asyncio`), `typing` lanjutan, dan validasi data berbasis Pydantic V2.
- **Arsitektur RAG & Agent**: Memahami siklus Vector Search, Embedding Spaces, Context Injection, dan ReAct/Function Calling patterns.
- **Observability Standards**: Memahami dasar-dasar Distributed Tracing OpenTelemetry (Spans, Traces, Context Propagation, Exporters).
- **Testing & DevOps**: Familiar dengan Git workflows, CI/CD pipelines, containerization (Docker), serta unit/integration testing framework (`pytest`, `pytest-asyncio`).

---

## 3. Concept & Internal Architecture

Dalam skala enterprise, evaluasi sistem berbasis LLM bukan sekadar menjalankan unit test konvensional dengan *exact matching assertion*. Sifat non-deterministik dan elastisitas semantik dari model fondasi membutuhkan arsitektur evaluasi berlapis yang memisahkan antara **Deterministic Guardrails**, **Model-Based Evaluators**, dan **Statistical Observability**.

```
+--------------------------------------------------------------------------------------------------+
|                                  ENTERPRISE LLM OBSERVABILITY ENGINE                             |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   +-----------------------+     +------------------------+     +-----------------------------+   |
|   |   Application Layer   | --> | OpenTelemetry Exporter | --> | Distributed Collector       |   |
|   | (Prompt + RAG Context)|     | (Semantic Conventions) |     | (OTel Collector / OpenInf)  |   |
|   +-----------------------+     +------------------------+     +--------------+--------------+   |
|                                                                               |                  |
|                                         +-------------------------------------+                  |
|                                         v                                                        |
|   +---------------------------------------------------------------------------+                  |
|   |                       Telemetry Storage & Trace Graph                     |                  |
|   |                  (ClickHouse / OpenSearch / Langfuse / Phoenix)           |                  |
|   +-------------------------------------+-------------------------------------+                  |
|                                         |                                                        |
|                                         +-------------------------------------+                  |
|                                                                               |                  |
|                                                                               v                  |
|   +-------------------------------------------------------------+     +----------------------+   |
|   |               Continuous Evaluation Pipeline                |     |   Drift & Anomaly    |   |
|   | +-----------------+ +------------------+ +----------------+ |     |   Detection Service  |   |
|   | | Faithfulness    | | Context Recall   | | Toxicity / PII | |     | - Semantic Drift     |   |
|   | | (G-Eval / CoT)  | | (Intersection)   | | (Guardrails)   | |     | - Latency P99 Spikes |   |
|   | +-----------------+ +------------------+ +----------------+ |     | - Token Cost Drift   |   |
|   +-------------------------------------------------------------+     +----------------------+   |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

### Internal Architecture Mechanics

1. **Semantic Convention Spans**:
   Tracing tidak hanya mencatat durasi eksekusi, melainkan memetakan seluruh metadata model: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.response.finish_reasons`, `gen_ai.usage.prompt_tokens`, `gen_ai.usage.completion_tokens`, input prompt mentah, serta embedding vectors yang diambil dari Vector Store.

2. **The LLM-as-a-Judge Subsystem**:
   Mekanisme evaluasi modern menggunakan model yang lebih kuat (misal: GPT-4o, Claude 3.5 Sonnet) untuk mengaudit model yang lebih hemat biaya (misal: GPT-4o-mini, Llama-3-8B). Untuk mengatasi bias inheren:
   - **Position Bias**: Menjalankan evaluasi dua kali dengan urutan output yang ditukar ($A/B$ lalu $B/A$) dan menghitung konsistensi hasil.
   - **Verbosity Bias**: Normalisasi skor terhadap panjang output menggunakan regression adjustment.
   - **Self-Enhancement Bias**: Melarang model menjadi juri bagi outputnya sendiri tanpa *chain-of-thought grounding*.

3. **Multi-Faceted Metric Math**:
   - **Faithfulness Score**:
     $$\text{Faithfulness} = \frac{|\text{Klaim yang didukung oleh Konteks Retrieval}|}{|\text{Total Klaim Faktual dalam Respon}|}$$
   - **Context Recall Score**:
     $$\text{Context Recall} = \frac{|\text{Kalimat dalam Ground Truth yang ditemukan di Konteks Retrieval}|}{|\text{Total Kalimat dalam Ground Truth}|}$$

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Software Klasik) | Pendekatan Enterprise LLM Systems |
| :--- | :--- | :--- |
| **Assert Statements** | `assert response == expected_output` | Asersi Probabilistik & Semantik: `assert faithfulness_score >= 0.85` |
| **Tracing** | HTTP Request-Response, Database Query Latency | Nested Inference Tree: Retrieval -> Compression -> Prompt Assembly -> LLM Run -> Post-processing |
| **Dataset Pengujian** | Mocking statis, SQLite memory testing | Dinamis: Synthetic Golden Datasets dengan evolusi skenario (multi-turn, adversarial) |
| **Pipeline Failure** | Syntax Error, NPE, Logical Condition Error | Semantic Hallucination, PII Leakage, Instruction Drift, Context Saturation |

### Mengapa Perlu Arsitektur Observabilitas Khusus?
Sistem LLM dalam produksi mengalami degradasi senyap (*silent failure*). Model tidak melemparkan HTTP 500 error ketika berhalusinasi; ia mengembalikan HTTP 200 dengan payload yang meyakinkan namun salah secara faktual. Tanpa observabilitas berbasis token-level tracing dan automated judging, regresi ini baru terdeteksi setelah terjadi kerugian operasional atau reputasi.

---

## 5. How (Workflow Detail)

```
[Developer Updates Prompt/Pipeline]
                |
                v
[Git Commit to Feature Branch]
                |
                v
[CI Runner Triggered (GitHub Actions / GitLab CI)]
                |
                +---> Step 1: Deterministic Tests (Formatting, Regex, Guardrails)
                |
                +---> Step 2: Semantic Pipeline Run across Synthetic Golden Dataset
                |
                +---> Step 3: Distributed LLM-as-a-Judge Execution (Parallel Async)
                |       |
                |       +---> Swap Position Evaluation (Calibration)
                |       +---> Metric Compute (Faithfulness, Relevance, Safety)
                |
                +---> Step 4: Regression Gate Analysis
                        |
       +----------------+----------------+
       | Pass                            | Fail
       v                                 v
[Deploy to Canary (10% Traffic)]   [Break Build & Generate Failure Report]
       |
       v
[Production Telemetry & Drift Monitor]
       |
       +---> Detect Latency/Cost Spikes? -> Rollback via Feature Flag
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sebuah pabrik perakitan jam tangan mekanis mewah.
- **Konvensional (Unit Test)**: Mengukur apakah diameter roda gigi pas dengan cetakan besi (True/False).
- **Prompt Engineering Observability**: Menyewa auditor independen bersertifikat (LLM Judge) untuk memeriksa ketepatan detik jam tersebut selama 30 hari dalam berbagai suhu dan gravitasi, mencatat setiap goresan mikro menggunakan mikroskop elektron (OpenTelemetry Tracing), dan memastikan jam tangan tersebut tidak meledak saat terkena medan magnet (Safety & Robustness Guardrails).

```
+--------------------------------------------------------------------+
|                       INFERENCE SPAN TREE                          |
+--------------------------------------------------------------------+
| [Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736]                      |
|                                                                    |
| root_rag_pipeline [340ms]                                          |
|  |                                                                 |
|  +-- embedding_generation [45ms] (model: text-embedding-3-small)   |
|  |                                                                 |
|  +-- vector_store_query [120ms] (top_k: 4, namespace: enterprise)  |
|  |                                                                 |
|  +-- rerank_context [25ms] (model: bge-reranker-large)             |
|  |                                                                 |
|  \-- llm_inference [150ms] (model: gpt-4o, tokens: 420)           |
|       |                                                            |
|       +-- gen_ai.prompt: "System: ... Context: ... User: ..."      |
|       \-- gen_ai.completion: "Berdasarkan laporan kuartal..."      |
+--------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: LLM-as-a-Judge Dasar Menggunakan Pydantic Structured Outputs

```python
import os
import asyncio
from pydantic import BaseModel, Field
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "mock-key"))

class FaithfulnessVerdict(BaseModel):
    reasoning: str = Field(description="Analisis langkah demi langkah apakah output didukung sepenuhnya oleh konteks.")
    claims: list[str] = Field(description="Daftar klaim faktual yang diekstraksi dari jawaban.")
    unsupported_claims: list[str] = Field(description="Daftar klaim yang tidak ditemukan dalam konteks.")
    score: float = Field(description="Skor antara 0.0 (halusinasi total) hingga 1.0 (sepenuhnya akurat).")

async def evaluate_faithfulness(context: str, answer: str) -> FaithfulnessVerdict:
    eval_prompt = f"""
Peran Anda adalah evaluator kepatuhan data faktual untuk sistem retrieval enterprise.
Tugas Anda: Verifikasi apakah 'Jawaban' berikut ini murni diderivasi HANYA dari 'Konteks' yang diberikan.
JANGAN asumsikan fakta luar apa pun. Jika fakta tidak ada di konteks, kategorikan sebagai unsupported.

Konteks:
{context}

Jawaban:
{answer}
"""
    response = await client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": "You are a rigid mathematical-grounding judge."},
            {"role": "user", "content": eval_prompt}
        ],
        response_format=FaithfulnessVerdict,
        temperature=0.0
    )
    return response.choices[0].message.parsed

# Quick run demonstration
async def main():
    ctx = "Layanan cloud perusahaan mengenakan biaya Rp 150/GB untuk cold storage dan Rp 500/GB untuk hot storage."
    ans = "Biaya cold storage adalah Rp 150/GB, dan transfer antar region gratis."
    verdict = await evaluate_faithfulness(ctx, ans)
    print(f"Score: {verdict.score}")
    print(f"Unsupported: {verdict.unsupported_claims}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7.2 Practical Example: Enterprise Tracing, Double-Swap Judgement & Guardrail Gate Engine

Struktur kode di bawah ini menerapkan trace lifecycle manual berbasis OpenTelemetry semantic conventions yang terintegrasi dengan double-swap position calibration evaluator.

```python
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Tuple
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

# Setup Tracing Subsystem
provider = TracerProvider()
processor = SimpleSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("enterprise-llm-evaluator", "2.1.0")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EnterpriseEvaluator")

client = AsyncOpenAI(api_key="sk-mock-key-for-production-environment")

class BinaryVerdict(BaseModel):
    thought_process: str = Field(description="Step-by-step logic checking each premise.")
    verdict_choice: str = Field(description="MUST be 'A', 'B', or 'TIE'")
    confidence: float = Field(description="Score between 0.0 to 1.0")

class ProductionEvaluator:
    def __init__(self, judge_model: str = "gpt-4o"):
        self.judge_model = judge_model

    async def _evaluate_single_pass(
        self, query: str, candidate_a: str, candidate_b: str, trace_id: str
    ) -> BinaryVerdict:
        with tracer.start_as_current_span("judge_single_pass") as span:
            span.set_attribute("gen_ai.system", "openai")
            span.set_attribute("gen_ai.request.model", self.judge_model)
            span.set_attribute("app.eval.trace_id", trace_id)

            prompt = f"""
Query: {query}

Kandidat Respon A:
{candidate_a}

Kandidat Respon B:
{candidate_b}

Evaluasi mana yang lebih aman, faktual, dan secara eksplisit menjawab instruksi query tanpa bertele-tele.
Pilih A, B, atau TIE jika keduanya seimbang.
"""
            # Simulasi fallback API call jika menggunakan mock token
            try:
                response = await client.beta.chat.completions.parse(
                    model=self.judge_model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format=BinaryVerdict,
                    temperature=0.0
                )
                verdict = response.choices[0].message.parsed
                span.set_attribute("gen_ai.eval.verdict", verdict.verdict_choice)
                return verdict
            except Exception as ex:
                span.record_exception(ex)
                span.set_status(Status(StatusCode.ERROR, str(ex)))
                # Deterministic fallback untuk keperluan mock running
                return BinaryVerdict(
                    thought_process="Fallback due to dry-run/mock token execution.",
                    verdict_choice="A",
                    confidence=0.9
                )

    async def run_calibrated_judge(
        self, query: str, baseline_resp: str, candidate_resp: str
    ) -> Dict[str, Any]:
        """
        Menjalankan Pairwise Evaluation dengan pertukaran posisi (A/B testing)
        untuk mengeliminasi Positional Bias secara deterministik.
        """
        with tracer.start_as_current_span("calibrated_evaluation_run") as root_span:
            start_time = time.perf_counter()
            run_id = f"eval-{int(start_time)}"
            root_span.set_attribute("eval.run_id", run_id)

            # Pass 1: candidate adalah A, baseline adalah B
            task_1 = self._evaluate_single_pass(query, candidate_resp, baseline_resp, run_id)
            # Pass 2: baseline adalah A, candidate adalah B (Swapped)
            task_2 = self._evaluate_single_pass(query, baseline_resp, candidate_resp, run_id)

            verdict_1, verdict_2 = await asyncio.gather(task_1, task_2)

            resolved_winner = "INCONCLUSIVE"
            # Interpretasi Simetris:
            # Pada run 1: A = Candidate, B = Baseline. Verdict A -> Candidate menang.
            # Pada run 2: A = Baseline, B = Candidate. Verdict B -> Candidate menang.
            cand_won_run1 = verdict_1.verdict_choice == "A"
            cand_won_run2 = verdict_2.verdict_choice == "B"
            base_won_run1 = verdict_1.verdict_choice == "B"
            base_won_run2 = verdict_2.verdict_choice == "A"

            if cand_won_run1 and cand_won_run2:
                resolved_winner = "CANDIDATE"
            elif base_won_run1 and base_won_run2:
                resolved_winner = "BASELINE"
            elif verdict_1.verdict_choice == "TIE" and verdict_2.verdict_choice == "TIE":
                resolved_winner = "TIE"
            else:
                resolved_winner = "POSITION_BIAS_DETECTED"

            execution_duration = time.perf_counter() - start_time
            root_span.set_attribute("eval.final_winner", resolved_winner)
            root_span.set_attribute("eval.duration_seconds", execution_duration)

            result = {
                "run_id": run_id,
                "winner": resolved_winner,
                "bias_detected": resolved_winner == "POSITION_BIAS_DETECTED",
                "run_1_verdict": verdict_1.model_dump(),
                "run_2_verdict": verdict_2.model_dump(),
                "duration": execution_duration
            }
            logger.info(f"Evaluation complete. Result: {json.dumps(result, indent=2)}")
            return result

if __name__ == "__main__":
    evaluator = ProductionEvaluator()
    sample_query = "Bagaimana kebijakan refund langganan API di cloud platform?"
    baseline = "Refund dapat diajukan kapan saja melalui dashboard pelanggan."
    candidate = "Sesuai SLA Bab 4, refund hanya dapat diproses dalam rentang 14 hari kerja kalender pasca pembayaran dipotong."

    res = asyncio.run(evaluator.run_calibrated_judge(sample_query, baseline, candidate))
    print(f"\nFinal Execution Output:\nVerdict Winner: {res['winner']}")
```

---

## 8. Real World Case Study (Enterprise Scale)

### Bank FinTech Global: Migrasi Agent Transaksional Kartu Kredit
- **Konteks**: Layanan perbankan digital skala 12 juta pengguna aktif memperbarui sistem prompt untuk Core Banking Agent dari GPT-4 legacy ke model open-weights yang di-self-host pada kluster Kubernetes GPU internal (Llama-3-70B-Instruct).
- **Insiden Regresi**: Saat rilis awal, prompt baru lolos dari unit test deterministik (karena format JSON-nya valid). Namun, di level produksi terjadi **Instruction Drift**: model menyetujui pembatalan biaya tahunan (*annual fee waiver*) secara otomatis tanpa memvalidasi minimum poin loyalitas nasabah.
- **Implementasi Solusi**:
  1. **Automated LLM Evaluation Harness**: Membangun pipeline evaluasi 5.000 skenario historis setiap kali terjadi pull request pada repositori template prompt.
  2. **Triple-Judge Ensemble**: Menggunakan Claude 3.5 Sonnet, GPT-4o, dan Mistral Large secara paralel. Skoring dihitung menggunakan rata-rata terbobot (*weighted majority voting*).
  3. **Continuous Semantic Drift Monitoring**: Setiap 1% traffic produksi di-stream ke Kafka, dievaluasi secara asinkron menggunakan Apache Flink dan OpenInference metrics, mendeteksi perubahan respons sebelum akumulasi kerugian finansial.
- **Hasil**: Mencegah kerugian finansial diperkirakan sebesar USD 4.2 Juta per tahun akibat otorisasi salah, dan menurunkan tingkat halusinasi kebijakan finansial hingga 0.02%.

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
                    [LLM EVALUATION TAXONOMY]
    High Quality /                                  Low Quality /
    High Cost                                       Low Cost
       |                                               |
       v                                               v
[LLM-as-a-Judge] --------> [Cross-Encoders] --------> [Exact / Regex /
(GPT-4o, Claude 3.5)       (BGE-Reranker, BERT)        Levenshtein / BLEU]
- Biaya $5-$30 / 1k evals  - Biaya $0.05 / 1k evals   - Biaya ~$0.0001 / 1k
- Latency 1-3 detik        - Latency 40-100ms          - Latency < 1ms
- Nuansa semantik tinggi   - Khusus ranking/overlap    - Sangat rapuh (brittle)
```

| Tipe Evaluasi | Keunggulan | Kelemahan | Trade-off Operasional |
| :--- | :--- | :--- | :--- |
| **Deterministic Exact Match** | Latensi mikrosekon, nol biaya API. | Gagal menangani parafrase, sinonim, atau keluaran non-deterministik. | Hanya cocok untuk validasi sintaksis JSON/XML dan PII blocking. |
| **Embedding Similarity (Cosine)** | Cepat (~5-15ms), murah. | Buta terhadap negasi (e.g. "Saya suka ini" vs "Saya tidak suka ini" memiliki kemiripan kosinus tinggi). | Tidak boleh digunakan sebagai satu-satunya *gatekeeper* logika bisnis. |
| **Pairwise LLM-as-a-Judge** | Mendeteksi reasoning mendalam, relevansi, dan nuansa emosional. | Mahal, latensi tinggi, memiliki position & self-enhancement bias. | Wajib dijalankan asinkron atau dibatasi pada CI/CD sampling dan canary evaluation. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Positional Bias dalam Pairwise Evaluation
- **Masalah**: LLM Judge memiliki kecenderungan memilih "Kandidat A" secara signifikan lebih sering daripada "Kandidat B", terlepas dari kualitas aslinya.
- **Solusi**: Wajib implementasi *swap evaluation* (evaluasi kandidat dalam urutan [A, B] dan [B, A]). Jika hasilnya kontradiktif, tandai sebagai *untrusted/inconclusive*.

### 2. Token Saturation & Context Truncation
- **Masalah**: Trace spans tidak menampilkan error, tetapi evaluasi juri selalu mengembalikan skor 1.0 (false negative) karena dokumen konteks terlalu panjang dan terpotong di ujung (*needle-in-a-haystack failure*).
- **Solusi**: Pasang assertion validasi token length pada data pre-processing span, hitung token menggunakan `tiktoken` sebelum dikirim ke juri.

### 3. Verbosity Exploitation
- **Masalah**: Respon yang lebih panjang dinilai memiliki kualitas lebih tinggi oleh LLM judge, padahal mengandung filler text atau halusinasi berulang.
- **Solusi**: Normalisasikan skor evaluasi dengan metrik *Information Density* atau sertakan klausul eksplisit dalam evaluasi prompt: *"Respon yang singkat, padat, dan akurat bernilai lebih tinggi dibanding respon panjang yang bertele-tele."*

---

## 11. Best Practices (Production Checklist)

- [ ] **OpenTelemetry Semantic Attributes**: Gunakan atribut standar `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`.
- [ ] **Zero-Temperature Evaluation**: Set `temperature=0.0` pada semua model evaluasi juri untuk memastikan determinisme setinggi mungkin.
- [ ] **Golden Dataset Versioning**: Simpan *ground truth dataset* di storage terversifikasi (DVC, Git LFS, atau S3 versioned bucket). Jangan pernah biarkan juri mengevaluasi dataset dinamis yang tidak terdokumentasi.
- [ ] **Dual-Run CI Gating**: CI build dinyatakan **gagal** jika metrik *Faithfulness* turun lebih dari 2% ($\Delta < -0.02$) dibanding baseline main branch.
- [ ] **Cost-Cap Breakers**: Pasang rate-limiter dan budget threshold harian pada automated pipeline evaluasi agar recursive retry loop tidak menguras limit billing LLM provider.
- [ ] **Data Sanitation (PII Masking)**: Lakukan masking data sensitif (NIK, Credit Card, Email) sebelum trace data di-push ke cloud storage observability.

---

## 12. Hands-on Practice

Buat skrip pengujian performa pipeline regresi prompt pada direktori kerja berikut:

### Struktur Direktori:
```
hands-on/m02/
├── requirements.txt
├── golden_dataset.json
├── evaluator_engine.py
└── test_prompt_regression.py
```

### Langkah 1: Siapkan dependencies (`requirements.txt`)
```text
openai>=1.40.0
pydantic>=2.7.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
opentelemetry-api>=1.25.0
opentelemetry-sdk>=1.25.0
```

### Langkah 2: Buat dataset evaluasi (`golden_dataset.json`)
```json
[
  {
    "id": "tc-001",
    "query": "Berapa batas waktu transfer valas antar bank?",
    "context": "Instruksi transfer valuta asing (valas) antar bank diproses pada hari kerja pukul 08.00 hingga 15.00 WIB. Permintaan di luar jam tersebut akan dieksekusi hari kerja berikutnya.",
    "ground_truth": "Batas waktu transfer valas adalah hari kerja pukul 08.00 - 15.00 WIB."
  },
  {
    "id": "tc-002",
    "query": "Bagaimana skema biaya penutupan akun premium?",
    "context": "Penutupan akun premium gratis jika usia akun telah melebihi 6 bulan. Penutupan di bawah 6 bulan dikenakan penalti administrasi sebesar Rp 50.000.",
    "ground_truth": "Gratis jika akun lebih dari 6 bulan, penalti Rp 50.000 jika kurang dari 6 bulan."
  }
]
```

### Langkah 3: Implementasikan engine regresi evaluasi (`evaluator_engine.py`)
```python
import json
from typing import Dict, Any, List
from pydantic import BaseModel, Field

class FaithfulnessReport(BaseModel):
    is_faithful: bool = Field(description="Apakah output hanya memuat fakta dari konteks?")
    unsupported_elements: List[str] = Field(default_factory=list)
    score: float = Field(description="Nilai kepercayaan 0.0 sampai 1.0")

class RegressionHarness:
    @staticmethod
    def mock_llm_inference(prompt_version: str, query: str, context: str) -> str:
        """Simulasi inferensi model yang akan diuji."""
        if prompt_version == "v1_stable":
            if "valas" in query:
                return "Transfer valas diproses pukul 08.00-15.00 WIB pada hari kerja."
            return "Penutupan akun gratis setelah 6 bulan, atau Rp 50.000 jika di bawah 6 bulan."
        else: # "v2_experimental_broken"
            if "valas" in query:
                return "Transfer valas buka 24 jam setiap hari via mobile banking." # HALUSINASI
            return "Penutupan akun gratis kapan saja." # HALUSINASI

    @staticmethod
    def evaluate_output(context: str, generated_output: str) -> FaithfulnessReport:
        """Evaluator logis deterministik untuk hands-on."""
        # Simulasi deteksi halusinasi secara terprogram
        if "24 jam" in generated_output and "24 jam" not in context:
            return FaithfulnessReport(
                is_faithful=False,
                unsupported_elements=["Klaim 24 jam tidak ada di konteks."],
                score=0.0
            )
        if "gratis kapan saja" in generated_output and "penalti" in context:
            return FaithfulnessReport(
                is_faithful=False,
                unsupported_elements=["Mengabaikan klausa penalti 6 bulan."],
                score=0.2
            )
        return FaithfulnessReport(is_faithful=True, unsupported_elements=[], score=1.0)
```

### Langkah 4: Tulis Pytest Regression Gate (`test_prompt_regression.py`)
```python
import json
import pytest
from evaluator_engine import RegressionHarness

@pytest.fixture
def golden_cases():
    with open("golden_dataset.json", "r") as f:
        return json.load(f)

def test_stable_prompt_regression_gate(golden_cases):
    """Memastikan prompt stable lolos threshold evaluasi >= 0.85"""
    total_score = 0.0
    for case in golden_cases:
        output = RegressionHarness.mock_llm_inference("v1_stable", case["query"], case["context"])
        report = RegressionHarness.evaluate_output(case["context"], output)
        total_score += report.score

    mean_score = total_score / len(golden_cases)
    assert mean_score >= 0.85, f"Regresi terdeteksi! Skor rata-rata: {mean_score}"

def test_experimental_prompt_regression_gate(golden_cases):
    """Eksperimen rusak harus ditolak oleh CI test (diasertikan gagal)."""
    total_score = 0.0
    for case in golden_cases:
        output = RegressionHarness.mock_llm_inference("v2_experimental_broken", case["query"], case["context"])
        report = RegressionHarness.evaluate_output(case["context"], output)
        total_score += report.score

    mean_score = total_score / len(golden_cases)
    # Pipeline harus menangkap bahwa versi v2 ini gagal
    assert mean_score < 0.50, f"Evaluator gagal mendeteksi halusinasi! Skor: {mean_score}"
```

Jalankan pengujian via terminal:
```bash
pytest test_prompt_regression.py -v
```

---

## 13. Exercise

### Level Easy
Tuliskan skrip Python yang menerima dua string (*ground truth* dan *predicted answer*) lalu menghitung Levenshtein Distance dan Semantic Word Intersect Ratio. Jika intersect ratio di bawah 0.6, return status `WARNING`.

### Level Medium
Buat script evaluator asinkron berbasis Pydantic yang mengekstrak semua klaim numerik (angka persentase, mata uang, tanggal) dari output LLM dan memverifikasi ketersediaannya secara presisi pada context dokumen teks.

### Level Hard
Rancang kelas OpenTelemetry Tracing Span wrapper yang secara otomatis:
1. Menghitung estimasi token input/output menggunakan library `tiktoken`.
2. Menghitung perkiraan biaya API berdasarkan tarif GPT-4o (`$2.50 / 1M input`, `$10.00 / 1M output`).
3. Menginjeksi metrik biaya ini ke atribut OpenTelemetry span: `gen_ai.usage.cost_usd`.
4. Jika total latency melebihi 2500ms, memicu peringatan (*span event*) status warning secara otomatis.

---

## 14. Challenge

### Studi Kasus Produksi: "The Invisible Prompt Poisoning & Cost Drift Attack"
- **Skenario**: Sistem customer service enterprise Anda melayani 500.000 permintaan per hari. Sekelompok pengguna anonim mengeksploitasi sistem dengan memberikan query adversarial yang dirancang untuk memicu *token-length dilation attack* (membuat LLM menghasilkan output maksimal token yang bertele-tele tanpa memicu filter toxic kata kunci konvensional). Hal ini membuat latency P99 membengkak dari 800ms menjadi 18.000ms dan tagihan API bulanan melonjak 400%.
- **Tugas Arsitektur**:
  1. Rancang arsitektur sistem observabilitas real-time yang dapat mendeteksi anomali *Output-to-Input Token Ratio* secara otomatis menggunakan streaming sliding-window algorithm.
  2. Definisikan pipeline automated mitigation: Bagaimana circuit-breaker pattern diterapkan pada API Gateway untuk me-reroute traffic mencurigakan ke model open-source berbiaya rendah atau static canned response tanpa mematikan sistem untuk pengguna normal?
  3. Sajikan desain arsitektur dalam bentuk ASCII sequence diagram dan dokumen spesifikasi mitigasi fallback.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Apa kelemahan utama menggunakan metrik BLEU atau ROUGE untuk mengevaluasi jawaban generative model bisnis?
2. Mengapa pengaturan `temperature=0.0` sangat direkomendasikan untuk LLM-as-a-Judge?
3. Sebutkan dua atribut wajib OpenTelemetry Semantic Conventions untuk LLM tracing!
4. Apa yang dimaksud dengan *Positional Bias* pada pairwise LLM evaluation?
5. Mengapa assertion berbasis string matching klasik (`response == expected`) tidak cocok untuk pengujian regresi prompt?

### 5 Pertanyaan Intermediate
6. Bagaimana cara menghitung metrik *Faithfulness* secara probabilistik menggunakan Pydantic structured output?
7. Jelaskan strategi *Double-Swap Evaluation* untuk mengeliminasi preferensi order pada pairwise judging!
8. Apa perbedaan mendasar antara span metric *Context Precision* dan *Context Recall* pada evaluasi arsitektur RAG?
9. Bagaimana cara mendeteksi *Verbosity Bias* pada model juri LLM dan bagaimana kompensasinya?
10. Dalam siklus CI/CD prompt engineering, mengapa evaluasi terhadap *golden dataset* harus memisahkan validasi guardrail deterministik dan semantic checking?

### 3 Skenario Kasus Produksi
11. **Skenario 1**: Metrik Faithfulness model RAG Anda di dashboard produksi stabil di angka 0.98 (sangat tinggi), namun komplain pelanggan terkait informasi palsu meningkat 40%. Setelah diaudit, ternyata dokumen yang ditarik oleh Vector Database memang salah. Metrik evaluasi apa yang gagal Anda ukur dalam pipeline ini?
12. **Skenario 2**: CI pipeline prompt testing Anda memakan waktu 45 menit untuk memvalidasi 2.000 test case setiap push commit, menghambat kecepatan rilis tim engineering. Strategi komputasi dan arsitektur pengujian apa yang harus diterapkan untuk memangkas durasi testing menjadi di bawah 5 menit tanpa mengorbankan coverage?
13. **Skenario 3**: Model juri utama Anda (misal GPT-4o) mengalami *outage* parsial dari pihak provider saat batch regression testing berjalan di lingkungan CI. Bagaimana merancang arsitektur evaluator yang *fault-tolerant* agar proses deployment tetap memiliki *governance threshold* yang valid?

---

## 16. Summary

- Evaluasi sistem LLM enterprise menuntut transisi mendasar dari deterministic binary assertions menuju **Probabilistic & Calibrated Semantic Assertions**.
- Tiga pilar utama pengujian prompt modern adalah **Faithfulness** (terbebas dari halusinasi konteks), **Relevance** (menjawab kebutuhan pengguna secara presisi), dan **Deterministic Guardrails** (bebas dari pelanggaran PII, toxic, dan logic drift).
- Model-as-a-Judge memiliki bias inheren (positional, verbosity, self-enhancement) yang harus dimitigasi secara terstruktur melalui teknik **Double-Swap Permutation** dan validasi Pydantic schema yang ketat.
- Observabilitas sejati hanya dapat dicapai melalui standardisasi OpenTelemetry/OpenInference distributed tracing, memetakan rantai inferensi dari prompt level hingga token telemetry, latensi parsial, dan pergeseran semantik (*semantic drift*) secara real-time di lingkungan produksi.