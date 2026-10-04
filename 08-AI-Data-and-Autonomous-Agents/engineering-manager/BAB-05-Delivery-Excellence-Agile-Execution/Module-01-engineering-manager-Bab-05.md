# Bab 05: Delivery Excellence & Agile Execution
## Module 01: Agile Frameworks for Non-Deterministic AI & Agentic Systems Delivery

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Engineering Manager (EM) dan Technical Lead diharapkan mampu:

1. **Mendesain dan Mengoperasikan Siklus Dual-Track Agile** khusus sistem kecerdasan buatan (*Discovery vs. Delivery*) yang mengintegrasikan eksperimentasi stokastik Machine Learning (ML) dan Autonomous Agents ke dalam sprint delivery berkecepatan tinggi tanpa merusak komitmen sprint.
2. **Merumuskan *Eval-Driven Acceptance Criteria* (EDAC)** berbasis metrik kuantitatif (akurasi retrieval, semantic similarity, toleransi halusinasi, batas token p99, dan latensi p95) sebagai pengganti kriteria penerimaan deterministik tradisional.
3. **Membangun Automated Eval-Gate Pipeline** di level CI/CD yang bertindak sebagai pemutus sirkuit (*circuit breaker*) deployment jika terjadi degradasi model atau drift pada *Golden Dataset*.
4. **Menerapkan Model Estimasi Stokastik Monte Carlo** untuk memproyeksikan lead time dan kapasitas sprint tim AI/Data, memitigasi variansi tinggi akibat *research dead-ends* dan *agent looping bugs*.
5. **Mengelola Technical & Scientific Debt** pada *Agentic Workflows* menggunakan matriks dekomposisi utang arsitektur, utang data/evaluasi, dan utang dependensi model fundamental.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Software engineering konvensional bersifat **deterministik**: input $X$ dengan fungsi $F$ yang terverifikasi akan selalu menghasilkan output $Y$. Dalam paradigma ini, metodologi Agile standar (Scrum/Kanban) mengasumsikan bahwa ketidakpastian (*uncertainty*) terbesar terletak pada *kebutuhan bisnis* (*user requirements*), bukan pada *fisika komputasi* sistem itu sendiri.

Sebaliknya, rekayasa Data Platform, Foundation Models, dan Multi-Agent Systems bersifat **stokastik dan non-deterministik**. Masalah utama yang dihadapi bukan sekadar "bagaimana menulis kode", melainkan "apakah distribusi probabilitas output model memenuhi batas toleransi bisnis dalam batasan biaya dan latensi".

```
Paradigma Rekayasa Tradisional:
[Spesifikasi Jelas] -> [Implementasi Deterministik] -> [Unit/Integration Test: Binary PASS/FAIL]

Paradigma Agentic & AI Engineering:
[Hipotesis Bisnis] -> [Eksperimentasi Stokastik] -> [Evaluasi Statistik pada Distribusi Data]
                                                  ↳ Pass Rate: 92.4% (Threshold: 90%)
                                                  ↳ Hallucination Index: 1.2%
                                                  ↳ Token Variance: ±35%
```

#### Mental Model: The AI Delivery Trilemma

Sebagai Engineering Manager, Anda menyeimbangkan tiga variabel yang saling bertolak belakang:
1. **Model Capability & Quality** (Kecerdasan, akurasi, domain coverage).
2. **System Latency & Cost** (Token consumption, resource limits, response time).
3. **Delivery Predictability** (Ketepatan waktu rilis, kestabilan sprint commitments).

Pendekatan konvensional yang memaksakan *story points* deterministik pada eksplorasi agen otonom akan memicu dua kegagalan ekstrem: **Sprint Burnout** (karena tim terjebak dalam lubang riset tak berujung) atau **Premature Delivery** (merilis agen rapuh tanpa evaluasi komprehensif ke produksi).

Solusinya adalah mentransformasi delivery engine menjadi **Hypothesis-Driven Dual-Track Agile**:
- **Discovery Track (Ilmiah/Eksploratif):** Dikelola menggunakan batas waktu terisolasi (*Timeboxed Spikes*) untuk validasi hipotesis data, pemilihan model/prompt, dan mitigasi non-determinisme.
- **Delivery Track (Sistemik/Deterministik):** Mengemas artefak yang lolos ambang batas evaluasi menjadi layanan mikro, pipeline data, dan tool-calling interfaces yang aman, teruji, dan terpantau.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Di lingkungan enterprise tier-1, kegagalan delivery pada produk AI jarang terjadi karena kegagalan sintaksis kode. Masalah umumnya berakar pada kegagalan eksekusi manajemen teknik:

1. **Sprint Commitment Collapse:** Tim menjanjikan integrasi agen *Autonomous Customer Support* dalam dua sprint. Pada hari ke-8, ditemukan bahwa agen mengalami *infinite tool-calling loop* saat menerima input ambigu, memicu lonjakan biaya API sebesar \$14.000 dalam 6 jam dan membatalkan seluruh komitmen sprint.
2. **The "Silent Regression" Trap:** Pembaruan kecil pada *system prompt* untuk memperbaiki performa ekstraksi entitas secara tidak sengaja merusak kepatuhan format JSON pada output agen, menyebabkan sistem hilir (*downstream pipeline*) mengalami *unhandled JSONDecodeError* masif di produksi.
3. **Scientific Spikes Tanpa Batas:** Insinyur AI menghabiskan waktu berminggu-minggu mencoba mengoptimalkan model dengan *fine-tuning* tanpa kriteria sukses yang jelas (*exit criteria*), sementara bisnis membutuhkan solusi yang cukup baik (*good-enough baseline*) menggunakan RAG terarah.

Delivery excellence dalam domain ini menuntut EM untuk menggeser paradigma dari sekadar mengukur *Velocity* (Story Points per Sprint) menjadi mengukur **Hypothesis Velocity**, **Evaluation Pass Rate**, dan **Cost-Normalized Latency Boundaries**.

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah arsitektur operasional eksekusi delivery untuk tim AI/Agentic System tingkat enterprise, yang menghubungkan siklus sprint, gerbang evaluasi otomatis (*automated eval gates*), dan orkestrasi deployment.

```
+---------------------------------------------------------------------------------------------------+
|                                  DUAL-TRACK AGILE ARCHITECTURE                                    |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [TRACK 1: DISCOVERY & EXPERIMENTATION]                                                           |
|  +------------------+      +-------------------+      +------------------+                        |
|  | Hypothesis & PRD | ---> | Timeboxed Spike   | ---> | Eval Suite Run   |                        |
|  | (Target Metric)  |      | (Max 3-5 Hari)    |      | (Offline Golden) |                        |
|  +------------------+      +-------------------+      +--------+---------+                        |
|                                                                |                                  |
|                                     [Gate: Threshold Met?] <---+                                  |
|                                        /              \                                           |
|                               (NO: Re-scope)       (YES: Promote to Delivery)                     |
|                                     v                  v                                          |
+-------------------------------------+------------------+------------------------------------------+
|                                                        |                                          |
|  [TRACK 2: PRODUCTION DELIVERY ENGINE]                 |                                          |
|  +-----------------------------------------------------+                                          |
|  |                                                                                                |
|  |  +-------------------+      +--------------------+      +-----------------------------------+  |
|  |  | Hardened Software | ---> | Pull Request Engine| ---> | CI/CD Pipeline Automations        |  |
|  |  | Engineering       |      | (Deterministic CI) |      | - Unit & Contract Tests           |  |
|  |  +-------------------+      +--------------------+      | - Semantic Drift Gate             |  |
|  |                                                         | - Token Cost Stress Test          |  |
|  |                                                         | - Adversarial Prompt Probe        |  |
|  |                                                         +-----------------+-----------------+  |
|  |                                                                           |                    |
+--+---------------------------------------------------------------------------+--------------------+
|                                                                              |                    |
|  [DEPLOYMENT RUNTIME & FEEDBACK LOOP]                                        v                    |
|  +---------------------------------------------------------------------------+-----------------+  |
|  | Production System (Canary Release 5% -> 25% -> 100%)                                        |  |
|  |                                                                                             |  |
|  |  +---------------------+      +---------------------+      +-----------------------------+  |  |
|  |  | Agent Execution Bus | ---> | Tracing & Observab. | ---> | Continuous Feedback Engine  |  |  |
|  |  | (Fallback Circuits) |      | (LangSmith / OTel)  |      | (Auto-curation Golden Data) |  |  |
|  |  +---------------------+      +---------------------+      +--------------+--------------+  |  |
|  |                                                                           |                 |  |
|  +---------------------------------------------------------------------------+-----------------+  |
+------------------------------------------------------------------------------|--------------------+
                                                                               |
                                    [Regenerate Golden Dataset for Next Sprint]<--+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Dual-Track Execution: Separation of Concerns
1. **Discovery Backlog:** Mengelola ketidakpastian model. Tiket di sini berbentuk *Spikes* dengan parameter ketat:
   - *Timebox Limit*: Maksimal 3 hari kerja.
   - *Hypothesis Statement*: "Menggunakan reranker `bge-reranker-large` akan menaikkan Hit Rate retrieval sebesar 15% pada skenario data polis asuransi."
   - *Kill Criteria*: Jika peningkatan < 5% atau latensi bertambah > 400ms, hentikan eksplorasi dan pertahankan baseline.
2. **Delivery Backlog:** Mengelola stabilitas sistem. Hanya tiket yang telah tervalidasi pada discovery track yang boleh dipecah menjadi user stories produksi: integrasi API, implementasi fallback, caching layer, rate limiter, instrumentation, dan alert policy.

#### B. Eval-Driven Acceptance Criteria (EDAC)
User story pada sistem LLM/Agent tidak valid jika hanya memuat kriteria fungsional deskriptif. Format enterprise EDAC mengikat performa statistik sistem:

$$\text{Story Eligibility} = \begin{cases} 
\text{APPROVED}, & \text{if } (\text{Accuracy}_{\text{eval}} \ge \alpha) \land (\text{Cost}_{\text{max}} \le \beta) \land (\text{Latency}_{p95} \le \gamma) \\ 
\text{BLOCKED}, & \text{otherwise} 
\end{cases}$$

Contoh Implementasi Kriteria Penerimaan:
- **Retrieval Precision@K**: Baseline $\ge 0.85$ pada 500 sampel *Golden Dataset*.
- **Faithfulness / Groundedness**: Skor $G \ge 0.90$ menggunakan validasi LLM-as-a-judge yang dikalibrasi secara deterministik.
- **Cost Envelope**: Maksimal \$0.012 per interaksi pada transaksi normal.
- **Latency SLAs**: $p95 < 2500$ ms, $p99 < 4500$ ms di bawah beban 50 concurrent requests.

#### C. Stochastic Delivery Forecasting (Monte Carlo Simulation)
Alih-alih mengandalkan estimasi single-point (misal: "Fitur Agen ini berbobot 8 Story Points"), tim AI mengestimasi menggunakan distribusi probabilitas tiga titik (*Three-point PERT estimation*):
- $O$ = Optimistic estimate (hari kerja)
- $M$ = Most likely estimate (hari kerja)
- $P$ = Pessimistic estimate (termasuk risiko model underfitting/hallucination debugging)

Nilai ini diintegrasikan ke dalam simulasi Monte Carlo (10.000 iterasi) untuk menghasilkan kurva probabilitas penyelesaian sprint yang realistis untuk para stakeholder bisnis (misal: "Ada probabilitas 85% bahwa modul agen selesai dalam 14 hari kalender").

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem orkestrasi tata kelola delivery AI:
1. **Eval Gate Runner**: Komponen CI/CD otomatis untuk memverifikasi model/prompt changes terhadap Golden Dataset.
2. **Monte Carlo Delivery Forecaster**: Generator proyeksi kepastian delivery sprint untuk EM.

```python
"""
AI & Autonomous Agents Delivery Governance Framework
Component: Automated Eval-Gate and Monte Carlo Delivery Forecaster
Architecture: Clean Architecture (Domain Models -> Services -> Gate Runners)
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("DeliveryGovernance")


# =====================================================================
# DOMAIN: EVALUATION GATES & THRESHOLDS (CI/CD PIPELINE INTEGRATION)
# =====================================================================

class MetricType(str, Enum):
    ACCURACY = "accuracy"
    FAITHFULNESS = "faithfulness"
    LATENCY_P95 = "latency_p95_ms"
    COST_PER_CALL = "cost_per_call_usd"
    HALLUCINATION_RATE = "hallucination_rate"


@dataclass(frozen=True)
class EvalThreshold:
    metric_type: MetricType
    min_value: Optional[float] = None
    max_value: Optional[float] = None

    def validate(self, observed_value: float) -> Tuple[bool, str]:
        if self.min_value is not None and observed_value < self.min_value:
            return False, f"FAILED: {self.metric_type.value} {observed_value:.4f} < MIN {self.min_value}"
        if self.max_value is not None and observed_value > self.max_value:
            return False, f"FAILED: {self.metric_type.value} {observed_value:.4f} > MAX {self.max_value}"
        return True, f"PASSED: {self.metric_type.value} {observed_value:.4f}"


@dataclass
class EvalSample:
    query: str
    ground_truth: str
    generated_output: str
    latency_ms: float
    cost_usd: float
    hallucination_detected: bool
    similarity_score: float


@dataclass
class EvalRunResult:
    total_samples: int
    metrics: Dict[MetricType, float]
    passed_gate: bool
    rejection_reasons: List[str]


class AutomatedEvalGateService:
    """
    Menjalankan verifikasi statistik terhadap artefak model/prompt
    sebelum diizinkan merge ke release branch.
    """

    def __init__(self, thresholds: List[EvalThreshold]) -> None:
        self.thresholds = thresholds

    def evaluate_test_suite(self, dataset: List[EvalSample]) -> EvalRunResult:
        if not dataset:
            raise ValueError("Dataset evaluasi kosong. Minimal diperlukan 1 sampel.")

        total_samples = len(dataset)
        avg_latency = sum(s.latency_ms for s in dataset) / total_samples
        avg_cost = sum(s.cost_usd for s in dataset) / total_samples
        avg_accuracy = sum(s.similarity_score for s in dataset) / total_samples
        
        # Hitung persentase halusinasi
        hallucination_count = sum(1 for s in dataset if s.hallucination_detected)
        hallucination_rate = hallucination_count / total_samples
        
        # Proxy faithfulness berbanding terbalik dengan halusinasi
        faithfulness_score = max(0.0, 1.0 - hallucination_rate)

        # Hitung Latensi p95
        sorted_latencies = sorted([s.latency_ms for s in dataset])
        p95_index = math.ceil(0.95 * total_samples) - 1
        p95_latency = sorted_latencies[min(p95_index, total_samples - 1)]

        calculated_metrics: Dict[MetricType, float] = {
            MetricType.ACCURACY: avg_accuracy,
            MetricType.FAITHFULNESS: faithfulness_score,
            MetricType.LATENCY_P95: p95_latency,
            MetricType.COST_PER_CALL: avg_cost,
            MetricType.HALLUCINATION_RATE: hallucination_rate,
        }

        rejection_reasons: List[str] = []
        overall_pass = True

        for threshold in self.thresholds:
            if threshold.metric_type in calculated_metrics:
                val = calculated_metrics[threshold.metric_type]
                passed, reason = threshold.validate(val)
                if not passed:
                    overall_pass = False
                    rejection_reasons.append(reason)
                else:
                    logger.debug(reason)

        return EvalRunResult(
            total_samples=total_samples,
            metrics=calculated_metrics,
            passed_gate=overall_pass,
            rejection_reasons=rejection_reasons,
        )


# =====================================================================
# DOMAIN: STOCHASTIC DELIVERY ESTIMATION (MONTE CARLO)
# =====================================================================

@dataclass
class AISprintTask:
    task_id: str
    name: str
    optimistic_days: float  # Best-case research/implementation
    nominal_days: float     # Most-likely scenario
    pessimistic_days: float # Edge case loops, model drift, bad evals


class MonteCarloDeliveryForecaster:
    """
    Mensimulasikan delivery burn-down untuk mengatasi non-determinisme riset AI.
    Menggunakan distribusi probabilitas Triangular / Beta-PERT.
    """

    def __init__(self, tasks: List[AISprintTask]) -> None:
        self.tasks = tasks

    def _sample_pert(self, opt: float, nom: float, pess: float) -> float:
        """
        Mengambil sampel dari distribusi Beta-PERT.
        Mean = (opt + 4 * nom + pess) / 6
        """
        mean = (opt + 4.0 * nom + pess) / 6.0
        # Standard deviation approximation
        std_dev = (pess - opt) / 6.0
        if std_dev <= 0:
            return nom
        
        # Transformasi ke parameter distribusi Beta via method of moments
        alpha = ((mean - opt) / (pess - opt)) * (((mean - opt) * (pess - mean) / (std_dev ** 2)) - 1)
        beta_param = alpha * (pess - mean) / (mean - opt)
        
        if alpha <= 0 or beta_param <= 0:
            # Fallback jika standard deviasi degeneratif
            return random.triangular(opt, nom, pess)
            
        sampled_beta = random.betavariate(alpha, beta_param)
        return opt + sampled_beta * (pess - opt)

    def run_simulation(self, iterations: int = 10000) -> Dict[str, float]:
        if not self.tasks:
            return {"p50": 0.0, "p85": 0.0, "p95": 0.0}

        simulated_durations: List[float] = []

        for _ in range(iterations):
            sprint_total_days = 0.0
            for task in self.tasks:
                task_duration = self._sample_pert(
                    task.optimistic_days,
                    task.nominal_days,
                    task.pessimistic_days,
                )
                sprint_total_days += task_duration
            simulated_durations.append(sprint_total_days)

        simulated_durations.sort()
        
        def get_percentile(p: float) -> float:
            idx = math.ceil(p * iterations) - 1
            return round(simulated_durations[min(idx, iterations - 1)], 2)

        return {
            "p50_days": get_percentile(0.50),
            "p85_days": get_percentile(0.85),
            "p95_days": get_percentile(0.95),
            "max_worst_case_days": round(simulated_durations[-1], 2),
        }


# =====================================================================
# PIPELINE EXECUTION HARNESS
# =====================================================================

def execute_governance_demonstration() -> None:
    logger.info("=== STEP 1: EVAL-GATE VALIDATION FOR AI AGENT MERGE ===")

    # Definisi Gates sesuai SLA Perusahaan
    gates: List[EvalThreshold] = [
        EvalThreshold(MetricType.ACCURACY, min_value=0.85),
        EvalThreshold(MetricType.FAITHFULNESS, min_value=0.90),
        EvalThreshold(MetricType.LATENCY_P95, max_value=2000.0), # max 2000 ms
        EvalThreshold(MetricType.COST_PER_CALL, max_value=0.03), # max $0.03
        EvalThreshold(MetricType.HALLUCINATION_RATE, max_value=0.05), # max 5%
    ]

    eval_engine = AutomatedEvalGateService(thresholds=gates)

    # Mock Evaluasi Run dari 100 sampel Golden Dataset
    synthetic_eval_run: List[EvalSample] = []
    random.seed(42)
    for i in range(100):
        synthetic_eval_run.append(
            EvalSample(
                query=f"Contoh Query Enterprise #{i}",
                ground_truth="Expected deterministic intent extraction",
                generated_output="Agent execution payload with tools",
                latency_ms=random.gauss(1200, 300),
                cost_usd=random.uniform(0.015, 0.028),
                hallucination_detected=(random.random() < 0.04), # 4% rate
                similarity_score=random.uniform(0.86, 0.98),
            )
        )

    result = eval_engine.evaluate_test_suite(synthetic_eval_run)
    logger.info(f"Gate Status: {'PASSED' if result.passed_gate else 'BLOCKED'}")
    for metric, value in result.metrics.items():
        logger.info(f" - Metric {metric.value}: {value:.4f}")

    if not result.passed_gate:
        logger.error(f"Blocking Pull Request due to failures: {result.rejection_reasons}")
    else:
        logger.info("Semua batas evaluasi terpenuhi. PR diizinkan lanjut ke staging.")

    print("\n" + "="*70 + "\n")

    logger.info("=== STEP 2: STOCHASTIC SPRINT ESTIMATION (MONTE CARLO) ===")
    
    # Task backlog untuk inisiatif Autonomous Agent Customer Support
    backlog: List[AISprintTask] = [
        AISprintTask("AI-101", "RAG Pipeline Semantic Hybrid Search", 2.0, 3.5, 8.0),
        AISprintTask("AI-102", "Agent Tool-calling Schema & Guardrails", 1.5, 3.0, 6.0),
        AISprintTask("AI-103", "Mitigasi Loop & State Management Fallback", 2.0, 4.0, 10.0),
        AISprintTask("AI-104", "Fine-tuning Small LM untuk Router", 3.0, 5.0, 12.0),
        AISprintTask("AI-105", "Tracing Observability Setup (OpenTelemetry)", 1.0, 2.0, 3.0),
    ]

    forecaster = MonteCarloDeliveryForecaster(tasks=backlog)
    sim_results = forecaster.run_simulation(iterations=10000)

    logger.info("Hasil Analisis Kapasitas Sprint Berbasis Simulasi Monte Carlo:")
    logger.info(f" - 50% Confidence Target (P50) : {sim_results['p50_days']} Days")
    logger.info(f" - 85% Enterprise Target (P85) : {sim_results['p85_days']} Days (Direkomendasikan untuk SLA Stakeholder)")
    logger.info(f" - 95% Risk Buffer Target (P95): {sim_results['p95_days']} Days")
    logger.info(f" - Worst-case Scenario Bounds : {sim_results['max_worst_case_days']} Days")


if __name__ == "__main__":
    execute_governance_demonstration()
```

---

### 7. Edge Cases & Failure Modes

Dalam eksekusi pengiriman sistem AI/Agent, Engineering Manager wajib mengidentifikasi dan menyiapkan protokol mitigasi untuk kegagalan berikut:

| Failure Mode | Mekanisme Penyebab | Dampak Operasional | Mitigasi Engineering Management |
| :--- | :--- | :--- | :--- |
| **Golden Dataset Contamination** | Data uji evaluasi tidak sengaja masuk ke dalam basis data embedding / konteks augmentasi RAG. | Skor evaluasi terlihat sempurna di CI/CD (*False Positive*), namun anjlok total di produksi. | Terapkan *Data Sanitization Hash Ring* dan pemisahan VPC fisik antara repositori *Test Harness* dengan data pipeline ingestor. |
| **Agentic Loop Exhaustion** | Model mengalami kebingungan keputusan saat menghadapi parsing kegagalan tool terus-menerus. | Lonjakan biaya token eksponensial; thread worker terkunci (*deadlock*). | Tetapkan *Max Step Limit* yang ketat (misal: max 5 iterasi) dan *Circuit Breaker Fallback* otomatis ke model deterministik/human-in-the-loop. |
| **Evaluation Flakiness (LLM-as-a-Judge)** | Model penilai (*evaluator model*) mengalami ketidakstabilan akibat variasi temperatur atau update upstream API. | Pipeline CI/CD acak gagal (*intermittent failure*), menurunkan kepercayaan tim pada automated gate. | Kunci parameter evaluasi: `temperature=0.0`, gunakan *Few-Shot Calibration Examples*, atau ganti sebagian eval dengan metrik berbasis *Deterministic Heuristics* (Regex, AST-parsing). |
| **Research Sunk-Cost Fallacy** | Tim menghabiskan 3 sprint mencoba membuat arsitektur agen khusus (*novel*) tanpa perbaikan metrik yang signifikan. | Hilangnya kepercayaan stakeholder bisnis; target kuartalan meleset. | Terapkan *Strict Timeboxed Spikes* (maksimal 1 sprint). Jika dalam 1 sprint skor F1 tidak naik $\ge 5\%$, paksa tim menggunakan implementasi baseline yang stabil. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan tata kelola delivery AI melibatkan kompromi fundamental antara kecepatan delivery, biaya komputasi, dan keandalan sistem:

#### 1. In-Sprint Full Evaluation vs. Asynchronous Shadow Evaluation
* **In-Sprint Full Evaluation (Gate CI/CD):**
  * *Kelebihan:* Menjamin nol degradasi masuk ke cabang utama (*main branch*).
  * *Kekurangan:* Durasi build lambat (bisa memakan waktu 30-60 menit) dan biaya token evaluasi tinggi pada setiap Pull Request.
* **Alternatif (Async Shadow Evaluation):**
  * Jalankan smoke test kecil (10-20 sampel) pada level PR. Jalankan evaluasi penuh (*deep suite* 1.000+ sampel) sebagai *Nightly Batch Run* atau *Shadow Traffic Replay*.
  * *Trade-off:* Kecepatan review meningkat drastis, tetapi tim berisiko harus melakukan *hotfix rollback* jika nightly job menemukan regresi performa.

#### 2. LLM-as-a-Judge vs. Deterministic & Embedding Heuristics
* **LLM-as-a-Judge (e.g., GPT-4o untuk evaluasi konten):**
  * *Kelebihan:* Menangkap nuansa semantik, gaya bahasa, konteks penalaran tinggi.
  * *Kekurangan:* Mahal, lambat, dan memiliki variansi stokastik inheren.
* **Alternatif (Rule-based + Exact Matches + Cross-Encoder Rerankers):**
  * Menggunakan validasi skema Pydantic, regex boundaries, dan skor Cosine similarity lokal via MiniLM.
  * *Trade-off:* Jauh lebih murah dan cepat (eksekusi milidetik), namun tidak mampu mengevaluasi *logical coherence* penalaran agen yang rumit.

#### 3. Story Point Velocity vs. Probabilistic Lead Time
* Menggunakan Story Points tradisional pada tim riset agen memberi ilusi kontrol yang semu.
* Mengadopsi simulasi Monte Carlo berbasis distribusi PERT (tiga titik estimasi) meningkatkan akurasi estimasi delivery sebesar 40-60% pada proyek non-deterministik, namun menuntut edukasi ekstra kepada jajaran Product Owner dan Business Executive.

---

### 9. Best Practices & Standar Industri

1. **Definisikan "Done" Khusus AI (Definition of Done - DoD):**
   - Kode lulus format linter deterministik & *Static Analysis* (Ruff, Mypy).
   - Seluruh integrasi *tool calling* terlindungi skema validasi tipe yang kaku.
   - Evaluasi regresi pada *Golden Dataset* berhasil (minimal 95% pass rate).
   - Penggunaan batas konsumsi token maksimum terdefinisi pada setiap request agent.
   - Tracing metrik OpenTelemetry / LangSmith terinstrumentasi untuk tiap interaksi model.

2. **Dekomposisi Utang Teknis AI (*AI Technical Debt Framework*):**
   - **Data Drift Debt:** Memastikan evaluasi tidak menggunakan data usang; wajib ada pipeline kurasi otomatis untuk memasukkan kegagalan produksi kembali ke *Golden Dataset*.
   - **Prompt Debt:** Mengurangi ketergantungan pada prompt berukuran masif (*mega-prompts*); pecah logika menjadi modular chain atau sistem multi-agen dengan tanggung jawab terfokus.
   - **Fallback Debt:** Selalu siapkan degradasi fungsional bertingkat: *Autonomous Agent* $\rightarrow$ *Single-shot LLM* $\rightarrow$ *Rules Engine* $\rightarrow$ *Graceful Error Message*.

3. **Operasionalisasi DORA Metrics untuk AI Engine:**
   - *Deployment Frequency:* Diakselerasi melalui pemisahan antara pembaruan prompt (via Feature Flag/CMS Model) dengan pembaruan platform inti.
   - *Change Failure Rate (CFR):* Dihitung bukan dari *HTTP 500 status code*, melainkan dari frekuensi interaksi yang memicu *Circuit Breaker* atau *Negative User Feedback* (thumbs-down rate $> 3\%$).

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Tim Anda sedang membangun *Customer Ingestion Autonomous Agent*. Pada sprint terakhir, terjadi komplain bahwa latensi sistem melonjak dan agen mulai memberikan respons yang tidak relevan (*out-of-domain answers*). Tugas Anda adalah menyiapkan automated evaluation harness, menetapkan parameter gerbang rilis yang ketat, dan memvalidasi kelayakan deploy.

#### Langkah 1: Persiapan Lingkungan
Buat direktori proyek dan instal dependensi yang diperlukan:
```bash
mkdir -p ai-delivery-lab && cd ai-delivery-lab
python3 -m venv .venv
source .venv/bin/activate
pip install pydantic pytest
```

#### Langkah 2: Definisikan Golden Dataset Evaluasi
Simpan berkas berikut sebagai `eval_dataset.json`:
```json
[
  {
    "query": "Bagaimana cara membatalkan polis asuransi saya?",
    "expected_intent": "POLICY_CANCELLATION",
    "mock_model_output": "Anda dapat membatalkan polis melalui tab Pengaturan Akun.",
    "latency_ms": 1100,
    "cost_usd": 0.012,
    "hallucination": false,
    "accuracy_score": 0.95
  },
  {
    "query": "Berapa modal awal untuk trading crypto di platform ini?",
    "expected_intent": "OUT_OF_DOMAIN_REJECTION",
    "mock_model_output": "Kami bukan platform crypto, kami adalah asuransi kesehatan.",
    "latency_ms": 850,
    "cost_usd": 0.008,
    "hallucination": false,
    "accuracy_score": 0.92
  },
  {
    "query": "Klaim rumah sakit saya ditolak nomor #99912.",
    "expected_intent": "CLAIM_INQUIRY",
    "mock_model_output": "Silakan hubungi agen properti terdekat untuk perbaikan atap.",
    "latency_ms": 4200,
    "cost_usd": 0.045,
    "hallucination": true,
    "accuracy_score": 0.32
  },
  {
    "query": "Ubah alamat email korespondensi saya.",
    "expected_intent": "UPDATE_PROFILE",
    "mock_model_output": "Email berhasil diperbarui ke database pengguna.",
    "latency_ms": 1250,
    "cost_usd": 0.011,
    "hallucination": false,
    "accuracy_score": 0.91
  }
]
```

#### Langkah 3: Tulis Skrip Evaluator Test Runner
Simpan berkas berikut sebagai `test_eval_pipeline.py`:
```python
import json
import pytest
from delivery_engine import AutomatedEvalGateService, EvalSample, EvalThreshold, MetricType

def load_samples():
    with open("eval_dataset.json", "r") as f:
        data = json.load(f)
    samples = []
    for item in data:
        samples.append(
            EvalSample(
                query=item["query"],
                ground_truth=item["expected_intent"],
                generated_output=item["mock_model_output"],
                latency_ms=item["latency_ms"],
                cost_usd=item["cost_usd"],
                hallucination_detected=item["hallucination"],
                similarity_score=item["accuracy_score"],
            )
        )
    return samples

def test_pipeline_eval_gates():
    dataset = load_samples()
    
    # Standar Enterprise SLAs
    gates = [
        EvalThreshold(MetricType.ACCURACY, min_value=0.85),
        EvalThreshold(MetricType.LATENCY_P95, max_value=2500.0),
        EvalThreshold(MetricType.HALLUCINATION_RATE, max_value=0.10), # Max 10%
    ]
    
    service = AutomatedEvalGateService(thresholds=gates)
    result = service.evaluate_test_suite(dataset)
    
    # Assertion harus gagal karena sample #3 memiliki latensi 4200ms dan halusinasi fatal
    assert result.passed_gate, f"CI Gate ditolak karena: {result.rejection_reasons}"
```

#### Langkah 4: Eksekusi dan Verifikasi Failure Circuit
Jalankan pengujian menggunakan Pytest:
```bash
pytest test_eval_pipeline.py -v
```

**Ekspektasi Output Lab:**
Pengujian akan memicu `FAILED` secara otomatis. Di konsol Anda akan terlihat:
```text
FAILED test_eval_pipeline.py::test_pipeline_eval_gates - AssertionError: 
CI Gate ditolak karena: [
  'FAILED: accuracy 0.7750 < MIN 0.85', 
  'FAILED: latency_p95_ms 4200.0000 > MAX 2500.0', 
  'FAILED: hallucination_rate 0.2500 > MAX 0.1'
]
```

#### Langkah 5: Refleksi Analisis Engineering Manager
Diskusikan bersama tim teknis Anda:
1. Mengapa sample #3 menghasilkan kegagalan fatal pada akurasi dan latensi sekaligus?
2. Bagaimana cara memisahkan penanganan intent *out-of-domain* ke dalam router layer terpisah yang murah (*deterministic regex* atau model embedding lokal) guna mencegah LLM mengeksekusi penalaran berbiaya tinggi?
3. Langkah perbaikan apa yang harus dimasukkan ke dalam *Discovery Spike* sprint berikutnya untuk mengisolasi penanganan status klaim yang ditolak?