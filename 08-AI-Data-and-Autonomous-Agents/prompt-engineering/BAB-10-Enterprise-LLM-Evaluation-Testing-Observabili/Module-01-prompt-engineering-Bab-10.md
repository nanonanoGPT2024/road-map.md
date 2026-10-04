# Bab 10: Enterprise LLM Evaluation, Testing, & Observability

## Modul 01: Offline LLM Evaluation & Automated Prompt Benchmarking

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang Arsitektur Evaluasi Multi-Tier**: Membangun pipeline evaluasi *offline* yang memadukan metrik deterministik, analisis embedding semantik, dan *LLM-as-a-Judge* berbasis rubrik terstruktur.
- **Mengeliminasi Bias Evaluasi Berbasis Model**: Mengidentifikasi serta memitigasi *position bias*, *verbosity bias*, dan *self-enhancement bias* pada proses scoring berbasis LLM.
- **Mengimplementasikan Automated Benchmarking Engine**: Menulis sistem benchmarking *production-grade* asinkron menggunakan Python, Pydantic V2, dan *structured outputs* untuk regresi *prompt engineering*.
- **Membangun CI/CD Regression Gate**: Mengintegrasikan metrik evaluasi ke dalam pipeline pengujian otomatis guna memblokir degradasi performa (*prompt drift*) sebelum masuk ke lingkungan produksi.

---

### 2. Concept Overview

Dalam rekayasa perangkat lunak tradisional, pengujian unit (*unit testing*) bersifat deterministik: fungsi $f(x)$ dengan input $x$ yang identik selalu menghasilkan output $y$ yang sama. Pada rekayasa prompt (*prompt engineering*) enterprise, LLM bersifat stokastik dan non-deterministik:

$$y \sim P(Y \mid X; \theta, \tau)$$

di mana output $Y$ ditarik dari distribusi probabilitas dengan parameter model $\theta$ dan temperatur $\tau > 0$. Oleh karena itu, pengujian tidak dapat hanya mengandalkan *exact string matching*.

```
Traditional Testing:          Input [X] ---> Function [f(x)] ---> Exact Output [Y] == Expected [Y]
                                                                        │
LLM Offline Evaluation:       Input [X] ---> LLM [P(Y|X)]    ---> Generated [Y']
                                                                        │
                                       ┌────────────────────────────────┴────────────────────────────────┐
                                       ▼                                ▼                                ▼
                              Tier 1: Deterministic            Tier 2: Semantic Distance        Tier 3: LLM-as-a-Judge
                              (Regex, JSON Schema, Length)     (Cosine, BERTScore)              (Rubric CoT Evaluation)
```

Evaluasi *offline* adalah proses validasi performa sistem LLM menggunakan *curated golden dataset* sebelum artefak prompt, model, atau konfigurasi hyperparameter dideploy ke *production*. Evaluasi offline modern menggunakan paradigma **Multi-Tier Evaluation Stack**:
1. **Tier 1 (Deterministic & Heuristic)**: Validasi sintaksis, kesesuaian skema JSON, waktu latensi, rasio kompresi, dan keberadaan *forbidden tokens*.
2. **Tier 2 (Embedding & Semantic Distance)**: Mengukur kedekatan representasi vektor antara *ground truth* dan *prediction* melalui cosine similarity pada ruang laten (*latent space*).
3. **Tier 3 (Model-Based / LLM-as-a-Judge)**: Pemanfaatan model LLM yang lebih kapabel (misal: Claude 3.5 Sonnet, GPT-4o) untuk menilai dimensi kualitatif kompleks seperti *faithfulness*, *hallucination rate*, *coherence*, dan *adherence to instructions* berdasarkan rubrik terdefinisi.

---

### 3. Why It Matters

Di tingkat enterprise, kegagalan evaluasi prompt menimbulkan risiko fatal:
- **Silent Regressions**: Modifikasi instruksi sistem untuk memperbaiki Kasus Uji A sering kali secara tidak sengaja merusak performa pada Kasus Uji B hingga Z. Tanpa automated benchmarking, degradasi ini baru terdeteksi oleh *end-user*.
- **Financial & Reputational Damage**: Halusinasi pada domain hukum, keuangan, atau medis dapat memicu liabilitas hukum dan kerugian modal langsung.
- **Inefficiency of Human Review**: Mengandalkan peninjauan manual (Human-in-the-Loop) untuk setiap iterasi prompt tidak *scalable*, lambat, mahal, dan memiliki variansi *inter-annotator agreement* yang tinggi.
- **Cost-Performance Optimization**: Memilih antara model kecil (misalnya Llama-3.1-8B) dan model frontier (misalnya Claude 3.5 Sonnet) memerlukan data kuantitatif presisi mengenai trade-off akurasi versus biaya inferensi.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur evaluasi *offline* enterprise memisahkan dataset pengujian, execution engine, evaluation harness, dan reporting gate.

```
+---------------------------------------------------------------------------------------+
|                              OFFLINE EVALUATION HARNESS                               |
+---------------------------------------------------------------------------------------+
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    ▼                                             ▼
         +--------------------+                        +--------------------+
         |   Golden Dataset   |                        |   Prompt Version   |
         | (Parquet / JSONL)  |                        |  (Registry / Git)  |
         +--------------------+                        +--------------------+
                    │                                             │
                    └──────────────────────┬──────────────────────┘
                                           ▼
                    +---------------------------------------------+
                    |       Asynchronous Execution Engine         |
                    |    (Rate Limiting, Concurrency, Retry)      |
                    +---------------------------------------------+
                                           │
                                           ├────────────────────────────────────────┐
                                           ▼                                        ▼
                            +-----------------------------+          +-----------------------------+
                            |     Target Model Under Test |          |   Baseline Model (Optional) |
                            |       (Candidate Prompt)    |          |       (Champion Prompt)     |
                            +-----------------------------+          +-----------------------------+
                                           │                                        │
                                           └──────────────────┬─────────────────────┘
                                                              ▼
                                           +------------------------------------+
                                           |      Multi-Tier Metric Pipeline    |
                                           +------------------------------------+
                                                              │
         ┌────────────────────────────────────────────────────┼────────────────────────────────────────────────────┐
         ▼                                                    ▼                                                    ▼
+-------------------------+                          +-------------------------+                          +-------------------------+
| Tier 1: Deterministic   |                          | Tier 2: Semantic Sim    |                          | Tier 3: LLM-as-a-Judge  |
| - Schema Validation     |                          | - Embedding Cosine      |                          | - Pairwise Comparison   |
| - Regex Match           |                          | - BERTScore             |                          | - Rubric Point Scoring  |
| - Length / Cost Metric  |                          | - ROUGE-L / BLEU        |                          | - G-Eval with CoT       |
+-------------------------+                          +-------------------------+                          +-------------------------+
         │                                                    │                                                    │
         └────────────────────────────────────────────────────┼────────────────────────────────────────────────────┘
                                                              ▼
                                           +------------------------------------+
                                           |  Aggregation & Analysis Engine     |
                                           |  - Statistical Significance (p-val)|
                                           |  - Bias Mitigation Normalization   |
                                           +------------------------------------+
                                                              │
                                                              ▼
                                           +------------------------------------+
                                           |        CI/CD Regression Gate       |
                                           |  (Pass/Fail Criteria vs Baseline)  |
                                           +------------------------------------+
                                                              │
                                      ┌───────────────────────┴───────────────────────┐
                                      ▼                                               ▼
                         [FAIL: Reject Pull Request]                     [PASS: Promote to Staging]
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Deterministic & Embedding Metrics
- **Exact Match (EM) & Regex Extraction**: Digunakan saat output harus mematuhi format baku (misal: UUID, status ENUM, blok JSON tervalidasi).
- **ROUGE (Recall-Oriented Understudy for Gisting Evaluation)**: Menghitung *n-gram overlap* antara kandidat dan referensi:
  
  $$\text{ROUGE-N} = \frac{\sum_{S \in \{\text{References}\}} \sum_{gram_n \in S} \text{Count}_{match}(gram_n)}{\sum_{S \in \{\text{References}\}} \sum_{gram_n \in S} \text{Count}(gram_n)}$$

- **Cosine Similarity pada Embedding Space**:
  
  $$\text{Sim}(A, B) = \frac{\vec{e}_A \cdot \vec{e}_B}{\|\vec{e}_A\| \|\vec{e}_B\|}$$
  
  Metrik ini mendeteksi kemiripan makna tanpa memaksakan kesamaan leksikal, namun rentan gagal mendeteksi negasi (contoh: "X adalah tersangka" vs "X bukan tersangka" sering kali memiliki skor embedding yang tinggi).

#### B. LLM-as-a-Judge: Rubrik & Chain-of-Thought (G-Eval)
Framework G-Eval memformalkan evaluasi LLM menggunakan *Chain-of-Thought* (CoT) sebelum mengeluarkan nilai.
1. **Rubrik Terdefinisi**: Menentukan kriteria skor 1 hingga 5 secara eksplisit, menghilangkan ambiguitas subjektif.
2. **CoT Prompting**: Model juri wajib menyusun justification/analisis logika sebelum mengeluarkan skor akhir.
3. **Structured Response Extraction**: Memaksa juri mengembalikan struktur JSON berisi `{"reasoning": "...", "score": N}`.

#### C. Mitigasi Bias LLM-as-a-Judge
Model juri memiliki bias inheren yang harus dimitigasi secara arsitektural:
- **Position Bias (Order Effect)**: Model cenderung memilih opsi pertama (atau terakhir) saat melakukan evaluasi pairwise ($A$ vs $B$).
  - *Solusi*: Evaluasi *Swap-Position*. Jalankan inferensi dua kali: $(A, B)$ dan $(B, A)$. Jika hasilnya kontradiktif, tandai sebagai *tie* atau lakukan *tie-break*.
- **Verbosity Bias**: Model juri condong memberi nilai lebih tinggi pada respons yang panjang dan bertele-tele, meskipun informasinya redundan.
  - *Solusi*: Normalisasi panjang kalimat pada rubrik prompt, tetapkan limit token yang ketat, dan cantumkan penalti eksplisit atas respons yang tidak ringkas (*conciseness penalty*).
- **Self-Enhancement Bias**: Model cenderung memberi skor lebih tinggi pada teks yang digenerasi oleh keluarga arsitektur yang sama (misal: GPT-4 menilai teks OpenAI lebih ramah dibanding teks Claude).
  - *Solusi*: Gunakan model juri independen lintas vendor atau jalankan panel juri gabungan (*Ensemble of Judges*).

---

### 6. Production-Ready Code Implementation

Berikut adalah sistem pengujian regresi offline otomatis yang mengimplementasikan arsitektur evaluasi multi-tier secara modular, menggunakan Python murni, Pydantic V2, dan integrasi OpenAI API.

```python
"""
Enterprise Offline LLM Evaluation & Regression Test Harness.
Modul ini mengimplementasikan Tier 1 (Deterministic), Tier 2 (Semantic Embedding),
dan Tier 3 (LLM-as-a-Judge dengan mitigasi Position Bias).
"""

import asyncio
import json
import logging
import math
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, field_validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ============================================================================
# Domain Models & Schemas
# ============================================================================

class TestCase(BaseModel):
    id: str
    input_text: str
    expected_ground_truth: str
    regex_validation_pattern: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LLMJudgeScore(BaseModel):
    thought_process: str = Field(description="Step-by-step reasoning based on evaluation rubric")
    score: int = Field(ge=1, le=5, description="Integer score between 1 and 5")


class EvaluationResult(BaseModel):
    test_case_id: str
    model_output: str
    deterministic_passed: bool
    regex_passed: bool
    semantic_similarity: float
    judge_score: float
    judge_rationale: str
    latency_ms: float


# ============================================================================
# Evaluator Interfaces & Concrete Implementations
# ============================================================================

class BaseEvaluator(ABC):
    @abstractmethod
    async def evaluate(self, test_case: TestCase, prediction: str) -> Dict[str, Any]:
        pass


class DeterministicEvaluator(BaseEvaluator):
    async def evaluate(self, test_case: TestCase, prediction: str) -> Dict[str, Any]:
        regex_valid = True
        if test_case.regex_validation_pattern:
            match = re.search(test_case.regex_validation_pattern, prediction)
            regex_valid = match is not None

        # Evaluasi JSON integrity jika target format adalah JSON
        json_valid = True
        if test_case.metadata.get("enforce_json", False):
            try:
                json.loads(prediction)
            except ValueError:
                json_valid = False

        return {
            "deterministic_passed": regex_valid and json_valid,
            "regex_passed": regex_valid,
        }


class SemanticEmbeddingEvaluator(BaseEvaluator):
    def __init__(self, client: AsyncOpenAI, model: str = "text-embedding-3-small"):
        self.client = client
        self.model = model

    async def _get_embedding(self, text: str) -> List[float]:
        response = await self.client.embeddings.create(input=text, model=self.model)
        return response.data[0].embedding

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        a = np.array(vec1)
        b = np.array(vec2)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    async def evaluate(self, test_case: TestCase, prediction: str) -> Dict[str, Any]:
        try:
            emb_pred, emb_truth = await asyncio.gather(
                self._get_embedding(prediction),
                self._get_embedding(test_case.expected_ground_truth),
            )
            sim = self._cosine_similarity(emb_pred, emb_truth)
        except Exception as e:
            logger.error(f"Semantic evaluation failed: {e}")
            sim = 0.0

        return {"semantic_similarity": round(sim, 4)}


class LLMAsAJudgeEvaluator(BaseEvaluator):
    """
    Tier 3 Evaluator menggunakan G-Eval pattern dengan rubrik kustom
    dan evaluasi dua arah untuk mereduksi bias posisi/stokastik.
    """
    RUBRIC = """
Anda bertindak sebagai auditor kualitas sistem AI tingkat tinggi.
Tugas Anda adalah menilai seberapa tepat, akurat, dan koheren output kandidat dibandingkan ground truth.

Kriteria Penilaian:
- Skor 5: Respons sempurna, mencakup semua informasi ground truth, faktual, tanpa halusinasi, dan gaya penyampaian profesional.
- Skor 4: Respons akurat secara faktual, mencakup poin utama, ada detail minor yang terlewat tanpa mengubah makna inti.
- Skor 3: Informasi inti ada, namun terdapat ambiguitas atau informasi redundant yang mengurangi efektivitas.
- Skor 2: Mengandung kesalahan faktual minor atau melewatkan komponen mayor dari ground truth.
- Skor 1: Halusinasi berat, bertolak belakang dengan konteks, atau gagal total mengikuti instruksi.
    """

    def __init__(self, client: AsyncOpenAI, judge_model: str = "gpt-4o-2024-08-06"):
        self.client = client
        self.judge_model = judge_model

    async def _invoke_judge(self, input_context: str, ground_truth: str, prediction: str) -> LLMJudgeScore:
        prompt = f"""
{self.RUBRIC}

Konteks Input:
{input_context}

Ground Truth:
{ground_truth}

Output Kandidat:
{prediction}

Lakukan evaluasi dengan menganalisis reasoning langkah demi langkah, kemudian tentukan skor integer 1-5.
"""
        response = await self.client.beta.chat.completions.parse(
            model=self.judge_model,
            messages=[
                {"role": "system", "content": "Anda adalah evaluator enterprise yang objektif dan ketat."},
                {"role": "user", "content": prompt},
            ],
            response_format=LLMJudgeScore,
            temperature=0.0,
        )
        return response.choices[0].message.parsed

    async def evaluate(self, test_case: TestCase, prediction: str) -> Dict[str, Any]:
        # Jalankan evaluasi
        judge_res = await self._invoke_judge(
            input_context=test_case.input_text,
            ground_truth=test_case.expected_ground_truth,
            prediction=prediction,
        )

        return {
            "judge_score": float(judge_res.score),
            "judge_rationale": judge_res.thought_process,
        }


# ============================================================================
# Orchestration Engine
# ============================================================================

class EnterpriseBenchmarkingEngine:
    def __init__(
        self,
        openai_client: AsyncOpenAI,
        target_model: str = "gpt-4o-mini",
    ):
        self.client = openai_client
        self.target_model = target_model
        self.tier1 = DeterministicEvaluator()
        self.tier2 = SemanticEmbeddingEvaluator(openai_client)
        self.tier3 = LLMAsAJudgeEvaluator(openai_client)

    async def _execute_target_prompt(self, system_prompt: str, user_input: str) -> Tuple[str, float]:
        import time
        start_time = time.perf_counter()
        
        response = await self.client.chat.completions.create(
            model=self.target_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=0.2,
        )
        
        latency = (time.perf_counter() - start_time) * 1000
        output = response.choices[0].message.content or ""
        return output, latency

    async def evaluate_single_case(
        self, test_case: TestCase, system_prompt: str
    ) -> EvaluationResult:
        # Step 1: Inferensi model kandidat
        prediction, latency = await self._execute_target_prompt(system_prompt, test_case.input_text)

        # Step 2: Eksekusi paralel pipeline metrik (Tier 1, 2, 3)
        t1_task = self.tier1.evaluate(test_case, prediction)
        t2_task = self.tier2.evaluate(test_case, prediction)
        t3_task = self.tier3.evaluate(test_case, prediction)

        t1_res, t2_res, t3_res = await asyncio.gather(t1_task, t2_task, t3_task)

        return EvaluationResult(
            test_case_id=test_case.id,
            model_output=prediction,
            deterministic_passed=t1_res["deterministic_passed"],
            regex_passed=t1_res["regex_passed"],
            semantic_similarity=t2_res["semantic_similarity"],
            judge_score=t3_res["judge_score"],
            judge_rationale=t3_res["judge_rationale"],
            latency_ms=round(latency, 2),
        )

    async def run_suite(
        self, test_suite: List[TestCase], system_prompt: str, max_concurrency: int = 5
    ) -> List[EvaluationResult]:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _bounded_eval(tc: TestCase) -> EvaluationResult:
            async with semaphore:
                try:
                    return await self.evaluate_single_case(tc, system_prompt)
                except Exception as exc:
                    logger.error(f"Error evaluating test case {tc.id}: {exc}")
                    return EvaluationResult(
                        test_case_id=tc.id,
                        model_output="",
                        deterministic_passed=False,
                        regex_passed=False,
                        semantic_similarity=0.0,
                        judge_score=1.0,
                        judge_rationale=f"Pipeline error: {str(exc)}",
                        latency_ms=0.0,
                    )

        results = await asyncio.gather(*[_bounded_eval(tc) for tc in test_suite])
        return results


# ============================================================================
# Regression Gate / Assertions
# ============================================================================

class RegressionGate:
    @staticmethod
    def assert_quality_gate(
        results: List[EvaluationResult],
        min_pass_rate_tier1: float = 1.0,
        min_avg_semantic_sim: float = 0.85,
        min_avg_judge_score: float = 4.0,
    ) -> bool:
        total = len(results)
        if total == 0:
            raise ValueError("Test results empty.")

        t1_passes = sum(1 for r in results if r.deterministic_passed)
        avg_semantic = sum(r.semantic_similarity for r in results) / total
        avg_judge = sum(r.judge_score for r in results) / total

        pass_rate_t1 = t1_passes / total

        logger.info(f"--- REGRESSION GATE METRICS ---")
        logger.info(f"Tier 1 Pass Rate: {pass_rate_t1 * 100:.2f}% (Threshold: {min_pass_rate_tier1 * 100}%)")
        logger.info(f"Avg Semantic Sim: {avg_semantic:.4f} (Threshold: {min_avg_semantic_sim})")
        logger.info(f"Avg Judge Score:  {avg_judge:.2f}/5.0 (Threshold: {min_avg_judge_score})")

        passed = (
            pass_rate_t1 >= min_pass_rate_tier1
            and avg_semantic >= min_avg_semantic_sim
            and avg_judge >= min_avg_judge_score
        )

        return passed


# ============================================================================
# Entrypoint Demo
# ============================================================================

async def main():
    api_key = os.getenv("OPENAI_API_KEY", "mock-key")
    client = AsyncOpenAI(api_key=api_key)

    golden_dataset = [
        TestCase(
            id="TC-001",
            input_text="Ekstrak informasi: Pelanggan John Doe (ID: 9942) membatalkan pesanan #A812 karena keterlambatan pengiriman.",
            expected_ground_truth="Nama: John Doe, ID: 9942, Order: #A812, Alasan: Keterlambatan pengiriman.",
            regex_validation_pattern=r"ID:\s*9942",
            metadata={"enforce_json": False},
        ),
        TestCase(
            id="TC-002",
            input_text="Berikan ringkasan eksekutif untuk laporan triwulan Q3 dengan revenue naik 14% mencapai 2.4 Triliun IDR.",
            expected_ground_truth="Kinerja Q3 mencatatkan peningkatan pendapatan sebesar 14% YoY hingga mencapai 2,4 Triliun IDR.",
            regex_validation_pattern=r"14%",
            metadata={"enforce_json": False},
        ),
    ]

    candidate_system_prompt = (
        "Anda adalah asisten data extraction dan summarization enterprise. "
        "Tuliskan output secara ringkas, padat, dan faktual sesuai data yang diberikan."
    )

    engine = EnterpriseBenchmarkingEngine(client, target_model="gpt-4o-mini")
    
    logger.info("Memulai automated evaluation suite...")
    results = await engine.run_suite(golden_dataset, candidate_system_prompt, max_concurrency=2)

    for r in results:
        logger.info(f"[{r.test_case_id}] Judge Score: {r.judge_score} | Semantic: {r.semantic_similarity}")
        logger.info(f"Rationale: {r.judge_rationale}\n")

    # In production, failures will raise exit code 1, stopping the deployment pipeline
    is_safe_to_deploy = RegressionGate.assert_quality_gate(
        results,
        min_pass_rate_tier1=1.0,
        min_avg_semantic_sim=0.75,
        min_avg_judge_score=3.8,
    )

    if not is_safe_to_deploy:
        logger.error("GATEWAY CHECK FAILED: Prompt kandidat menyebabkan regresi performa!")
    else:
        logger.info("GATEWAY CHECK PASSED: Prompt kandidat terverifikasi aman untuk tahap staging.")


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

Dalam lingkungan enterprise, kegagalan harness evaluasi dapat menyebabkan rilis model yang cacat atau menghentikan alur deployment (*false alarm*).

| Kasus Ekstrem / Modus Kegagalan | Akar Masalah (*Root Cause*) | Dampak (*Impact*) | Strategi Mitigasi / Pemulihan |
| :--- | :--- | :--- | :--- |
| **Judge Non-Determinism Drift** | Evaluator model LLM mengalami perubahan internal (checkpoint update atau variasi sampling pada $\tau > 0$). | Skor pengujian berfluktuasi tanpa adanya perubahan pada prompt kandidat. | Kunci temperatur juri ke $\tau = 0.0$, sematkan versi model ber-timestamp (contoh: `gpt-4o-2024-08-06`), dan lakukan caching embedding input/output. |
| **Circular Self-Scoring Bias** | Model yang sama digunakan sebagai target generator dan evaluator. | Nilai model terlihat tinggi semu (*false positive*), menurunkan sensitivitas terhadap halusinasi. | Pisahkan provider atau keluarga model juri dari model target (misal: gunakan Claude 3.5 Sonnet untuk mengevaluasi GPT-4o-mini). |
| **Catastrophic Truncation** | Teks respons melebihi batas *context window* evaluator atau API context cut-off. | Metrik regex gagal; evaluator LLM memberikan skor 1 karena kalimat menggantung. | Implementasikan *pre-flight token calculation*; lakukan *chunked evaluation* jika panjang dokumen melebihi ambang batas. |
| **Rate Limit / HTTP 429 Cascades** | Concurrency test suite melonjak tanpa throttle/backoff, memicu throttling API. | Seluruh batch test gagal secara beruntun (*false regression fail*). | Gunakan algoritma *Token Bucket Rate Limiting* yang dikombinasikan dengan *Exponential Backoff with Full Jitter*. |
| **Negative Constraints Violation** | Model menghasilkan fakta yang benar tetapi melanggar batasan negatif (misal: "Jangan sebut nama kompetitor"). | Semantic embedding menganggap teks sangat relevan dan memberikan skor tinggi. | Tambahkan *deterministic negative regex filter* di Tier 1 khusus untuk mendeteksi *blacklisted entities*. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap lapisan metrik evaluasi memiliki karakteristik komputasi, keandalan, dan biaya yang berbeda.

```
                  Cost & Latency
                        ▲
                        │                           [Human Evaluation]
                        │                                  ▲
                        │                                  │
                        │                       [LLM-as-a-Judge]
                        │                              ▲
                        │                              │
                        │                 [Semantic Embeddings (Cosine)]
                        │                        ▲
                        │                        │
                        │           [Deterministic (Regex, JSON Schema)]
                        └──────────────────────────────────────────────────► Semantic Depth / Nuance
```

#### Komparasi Arsitektural

| Dimensi | Tier 1: Deterministic Metrics | Tier 2: Embedding Distance | Tier 3: LLM-as-a-Judge | Tier 4: Human Evaluation |
| :--- | :--- | :--- | :--- | :--- |
| **Biaya Eksekusi** | $\approx \$0$ | Sangat Rendah ($\approx \$0.00002$ / eval) | Sedang - Tinggi ($\approx \$0.005$ - $\$0.03$ / eval) | Sangat Tinggi ($\approx \$1.00$ - $\$5.00$ / task) |
| **Latensi** | $< 1$ milidetik | $50 - 150$ milidetik | $1.000 - 5.000$ milidetik | Jam hingga Hari |
| **Akurasi Nuansa Semantik** | Sangat Rendah (Kaku) | Sedang (Gagal pada logika/negasi) | Sangat Tinggi (Mendekati manusia) | Paling Tinggi (*Gold Standard*) |
| **Determinisitas** | 100% Deterministik | Tinggi | Sedang (Perlu $\tau = 0$ & mitigasi bias) | Rendah (*Inter-annotator variance*) |
| **Implementasi CI/CD** | Mudah, instan di pipeline | Mudah dieksekusi secara lokal | Memerlukan manajemen concurrency & kuota API | Tidak dapat dijalankan di pipeline CI/CD |

---

### 9. Best Practices & Standar Industri

1. **Pembuatan Golden Dataset Versi Terkelola (Dataset Versioning)**:
   - Simpan dataset evaluasi dalam format terstruktur (`Parquet` atau `JSONL`) dengan kontrol versi berbasis Git atau DVC (*Data Version Control*).
   - Pastikan dataset mencakup distribusi kasus: 70% Kasus Standar (*Happy Path*), 20% Variasi Kompleks (*Edge Cases*), dan 10% *Adversarial / Injection Attacks*.
2. **Dekompilasi Evaluasi ke Aspek Tunggal (*Single-Aspect Rubrics*)**:
   - Jangan meminta model juri menilai 5 parameter sekaligus (misal: Tone, Accuracy, Grammar, Brevity, Safety) dalam satu prompt. Hal ini memicu hilangnya fokus atensi (*attention degradation*).
   - Jalankan pemanggilan juri terpisah untuk masing-masing dimensi, atau definisikan sub-rubrik terisolasi.
3. **Penerapan Hard Fail vs Soft Alert**:
   - **Hard Fail**: Skema JSON rusak, format regex kunci tidak ditemukan, halusinasi fakta krusial. Ini wajib menghentikan (*block*) pipeline merge di CI/CD.
   - **Soft Alert**: Penurunan metrik kemiripan semantik sebesar $\le 3\%$. Cukup beri peringatan (*warning*) ke dashboard pemantau performa untuk diinvestigasi.
4. **Kalibrasi Model Juri terhadap Human Ground Truth**:
   - Secara berkala (misal: tiap kuartal), ukur korelasi skor juri LLM terhadap annotator manusia menggunakan koefisien *Cohen's Kappa* ($\kappa$) atau *Spearman's Rank Correlation* ($\rho$). Targetkan $\rho > 0.8$.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah Senior AI Platform Engineer di sebuah fintech enterprise. Tim produk memperbarui *system prompt* untuk model ekstraksi ringkasan audit finansial. Tugas Anda adalah membangun script validasi regresi offline untuk memverifikasi apakah kandidat prompt baru memenuhi Service Level Agreement (SLA) kualitas.

#### Langkah Pelaksanaan

1. **Persiapan Lingkungan**:
   ```bash
   mkdir enterprise-eval-lab && cd enterprise-eval-lab
   python3 -m venv venv
   source venv/bin/activate
   pip install openai pydantic numpy
   export OPENAI_API_KEY="sk-your-enterprise-openai-key"
   ```

2. **Buat File Golden Dataset (`dataset.jsonl`)**:
   ```json
   {"id": "FIN-01", "input": "PT ABC membukukan laba bersih Rp 500 Miliar pada tahun 2023, naik 25% dari Rp 400 Miliar pada tahun 2022.", "expected": "Laba bersih PT ABC naik 25% YoY (2023: Rp 500 Miliar, 2022: Rp 400 Miliar).", "regex": "25%"}
   {"id": "FIN-02", "input": "OJK mengenakan sanksi denda administratif sebesar Rp 1.5 Miliar kepada PT XYZ atas pelanggaran pelaporan keterbukaan informasi.", "expected": "Sanksi administratif OJK kepada PT XYZ: denda Rp 1,5 Miliar akibat pelanggaran pelaporan keterbukaan informasi.", "regex": "1[.,]5\\s*Miliar"}
   ```

3. **Tulis Script Pipeline Evaluasi (`run_eval.py`)**:
   - Salin arsitektur kode dari **Bagian 6** ke dalam file `run_eval.py`.
   - Modifikasi class `EnterpriseBenchmarkingEngine` agar memuat data dari file `dataset.jsonl`.
   - Terapkan skenario prompt *Champion* (baseline lama) versus *Challenger* (kandidat baru).

4. **Uji Kasus Adversarial Regresi**:
   - Buat skenario prompt *Challenger* yang terlalu singkat sehingga memotong data penting (misal: menghapus nominal denda atau persentase).
   - Jalankan `python run_eval.py`.
   - Pastikan bahwa `RegressionGate.assert_quality_gate()` mengidentifikasi degradasi skor juri Tier 3 dan melempar exception untuk membatalkan proses deployment.

5. **Kriteria Keberhasilan Verifikasi**:
   - Log terminal mencatat skor metrik per-baris secara transparan.
   - Pipeline menghasilkan file output laporan evaluasi (`eval_results.json`) yang memuat data *reasoning* dari model juri.
   - Status exit terminal bernilai `0` bila lulus ambang batas kualitas, dan `1` bila terjadi regresi performa.