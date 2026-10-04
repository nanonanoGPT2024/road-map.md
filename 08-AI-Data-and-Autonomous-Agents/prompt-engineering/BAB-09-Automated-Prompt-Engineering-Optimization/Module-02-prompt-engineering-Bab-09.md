# Kurikulum Enterprise: AI, Data, and Autonomous Agents
## Topik: Prompt Engineering
### BAB 09: Automated Prompt Engineering & Optimization (APE/APO)
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Algoritma Optimasi Prompt Diskrit**: Memahami formulasi matematis dan mekanisme internal dari *Discrete Prompt Search*, *Textual Gradients* (TextGrad), *Evolutionary Prompt Optimization* (EvoPrompt), serta *Bayesian Instruction Proposal* (DSPy MIPROv2).
2. **Merancang Sistem Continuous Prompt Optimization (CPO)**: Membangun pipeline optimasi otomatis berbasis metrik deterministik dan stokastik yang terintegrasi ke dalam CI/CD LLMOps.
3. **Mengimplementasikan Custom Optimization Loops**: Mengembangkan optimizer kustom menggunakan *teleprompters*, *surrogate loss functions*, dan teknik *LLM-as-a-Judge* terkalibrasi untuk meminimalkan *overfitting* pada *validation set*.
4. **Menjalankan Evaluasi & Observabilitas Skala Enterprise**: Menerapkan arsitektur *Shadow Deployment*, *Canary Testing*, serta deteksi regresi semantik menggunakan OpenTelemetry dan platform evaluasi (Langfuse/Arize Phoenix) untuk menjamin keandalan sistem produksi.

---

### 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut sebelum mempelajari modul ini:
* **Pemrograman Python Tingkat Lanjut**: Asynchronous programming (`asyncio`), `typing` modern, metaprogramming, dan Pydantic v2.
* **Dasar DSPy Framework**: Memahami primitives `dspy.Signature`, `dspy.Module`, `dspy.Predict`, dan `dspy.ChainOfThought`.
* **Statistik & Evaluasi ML**: Konsep F1-score, Bootstrapping, Bayesian Optimization (Tree-structured Parzen Estimators/TPE), Confusion Matrix, dan Inter-Annotator Agreement (Cohen's Kappa).
* **LLM Foundations**: Mekanisme inferensi autoregresif, *temperature/top-p sampling*, tokenisasi (BPE), dan kalkulasi biaya inferensi token input/output.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Formulasi Matematis Optimasi Prompt
Optimasi prompt pada dasarnya merupakan masalah optimasi kombinatorial diskrit pada ruang teks natural $\mathcal{V}^*$:

$$\theta^* = \arg\max_{\theta \in \mathcal{V}^*} \mathbb{E}_{(x, y) \sim \mathcal{D}} [\mathcal{M}(f(x; \theta), y)]$$

Di mana:
* $\mathcal{V}^*$ adalah ruang kombinatorial dari seluruh kemungkinan rangkaian token teks (discrete string search space).
* $\theta$ merepresentasikan sistem instruksi, prefix, atau kumpulan *few-shot exemplars*.
* $x$ dan $y$ adalah pasangan input dan ground-truth label/output dari distribusi data $\mathcal{D}$.
* $f(x; \theta)$ adalah output autoregresif LLM ketika diberikan input $x$ dengan parameter konteks $\theta$.
* $\mathcal{M}$ adalah fungsi evaluasi objektif (*reward/loss metric*), baik bersifat deterministik (akurasi regex, kemiripan AST, passing unit-test) maupun stokastik (LLM-as-a-Judge semantic rubric).

Karena ruang pencarian token bersifat non-diferensiabel secara langsung terhadap loss teks output melalui gradien floating-point standar ($\nabla_\theta$ tidak dapat dihitung langsung karena operasi diskrit sampling), Automated Prompt Engineering (APE) mengadopsi tiga paradigma utama:

```
+-----------------------------------------------------------------------------------+
|                        PARADIGMA OPTIMASI PROMPT DISKRIT                         |
+-----------------------------------------------------------------------------------+
| 1. Monte Carlo / Genetic Search (APE / EvoPrompt)                                 |
|    - Menggunakan LLM sebagai mutator dan crossover operator                       |
|    - Seleksi berbasis fitness score pada subset dataset                           |
|                                                                                   |
| 2. Textual Gradient Backpropagation (TextGrad)                                    |
|    - Loss dievaluasi secara tekstual: L_text = CriticLLM(Prediction, GroundTruth) |
|    - Gradien tekstual dipropagasi balik: \nabla_text = LLM_Backward(L_text)       |
|    - Update prompt dilakukan via optimizer tekstual: \theta_{t+1} = LLM_Step(...) |
|                                                                                   |
| 3. Multi-stage Bayesian Optimization (DSPy MIPROv2)                               |
|    - Dekopling Instruction Search dan Demonstration Search                        |
|    - Generasi proposal instruksi via meta-prompts dari data dan kegagalan inferensi|
|    - Bayesian Optimization (TPE) mengevaluasi kombinasi (instruksi + few-shots)   |
+-----------------------------------------------------------------------------------+
```

#### 3.2 Dekonstruksi Arsitektur MIPROv2 (Multi-prompt Instruction Proposal Optimizer)
MIPROv2 memecahkan inefisiensi pencarian naive dengan membagi optimasi menjadi dua fase:

1. **Fase Proposal (Off-line/Pre-trial)**:
   * **Proposal Instruksi**: Menggunakan model "Proposer" untuk menganalisis modul pipeline, data eksekusi, serta log kegagalan (*error traces*) guna menghasilkan kandidat instruksi $\mathcal{I} = \{I_1, I_2, \dots, I_K\}$.
   * **Proposal Demonstrasi**: Menjalankan *bootstrap tracing* untuk mengumpulkan traces eksekusi yang sukses ($x \to \text{step}_1 \to \dots \to y$) dan mengelompokkannya menjadi set *few-shot candidates* $\mathcal{D}_{\text{shots}} = \{D_1, D_2, \dots, D_M\}$.

2. **Fase Bayesian Optimization (Surrogate-driven Search)**:
   * Menggunakan Tree-structured Parzen Estimator (TPE) untuk memodelkan $P(\text{score} \mid \text{config})$, di mana $\text{config} = (I_j, D_k)$.
   * Mengevaluasi kandidat instruksi dan subset demonstrasi pada mini-batch validasi, kemudian memperbarui fungsi akuisisi (Expected Improvement) untuk memilih konfigurasi berikutnya yang paling menjanjikan.

```
+------------------------------------------------------------------------------------+
|                         INTERNAL WORKFLOW: DSPY MIPROv2                            |
+------------------------------------------------------------------------------------+
| [Training Data] ---> [Bootstrap Module Trace] ---> [Successful Traces (D_shots)]   |
|         |                                                         |                |
|         v                                                         v                |
| [Proposer LLM] <--- (Feed Failure Traces & Signatures) ---> [Candidate Pool]       |
|         |                                                         |                |
|         v                                                         v                |
|  [Instructions: {I_1..I_K}]                              [Few-Shots: {D_1..D_M}]   |
|         \                                                         /                |
|          +--------------------------+----------------------------+                 |
|                                     |                                              |
|                                     v                                              |
|                   +----------------------------------+                             |
|                   |  Tree-structured Parzen (TPE)    | <---+                       |
|                   |  Bayesian Trial Selector         |     |                       |
|                   +----------------------------------+     | Iterative Updates     |
|                                     |                      |                       |
|                        Sample Config: (I_j, D_k)           |                       |
|                                     v                      |                       |
|                   +----------------------------------+     |                       |
|                   |  Mini-Batch Validation Evaluator | ----+                       |
|                   +----------------------------------+                             |
|                                     |                                              |
|                       Convergence / Epoch Max Reached                              |
|                                     v                                              |
|                      [Compiled Optimized DSPy Module]                              |
+------------------------------------------------------------------------------------+
```

---

### 4. Why & What

| Dimensi | Manual Prompt Engineering (Trial & Error) | Automated Prompt Optimization (MIPROv2 / TextGrad) |
| :--- | :--- | :--- |
| **Metodologi** | Intuisi pengembang, eksperimen lokal ad-hoc. | Optimasi matematis berbasis metrik objektif dan dataset. |
| **Sensitivitas Model** | Prompt rusak saat migrasi model (e.g., GPT-4o ke Claude 3.5 Sonnet). | Kompilasi ulang otomatis terhadap model target tanpa intervensi manusia. |
| **Few-shot Selection** | Hardcoded, berisiko bias seleksi manual. | Penemuan otomatis demonstrasi optimal dari eksekusi valid. |
| **Resilience to Edge-cases**| Terbatas pada kasus yang dipikirkan manusia. | Memetakan dan mengoptimasi skenario kegagalan dari ribuan log. |
| **Auditability & Drift** | Sulit diukur; perubahan prompt tidak memiliki versi matematis. | Terbuka untuk versioning git-like, pelacakan metrik, dan canary release. |

**Mengapa ini krusial di Enterprise?**
Di tingkat enterprise, prompt bukan sekadar teks melainkan *software artifact*. Mengubah satu kata dalam prompt sistem pada pipeline transaksi finansial atau analisis rekam medis dapat menurunkan akurasi klasifikasi sebesar 10-15%. Otomatisasi mengubah prompt engineering menjadi proses rekayasa perangkat lunak standar (kredensial, tes unit, optimasi, deployment terukur).

---

### 5. How (Workflow Detail)

Arsitektur produksi Continuous Prompt Optimization (CPO) membutuhkan pipeline yang berulang:

```
+--------------------------------------------------------------------------------------+
|                      ENTERPRISE PIPELINE: CONTINUOUS OPTIMIZATION                    |
+--------------------------------------------------------------------------------------+
|                                                                                      |
|  +-------------------+      +-------------------+      +--------------------------+  |
|  | 1. Data Ingestion | ---> | 2. Metric Guard   | ---> | 3. Offline Optimization  |  |
|  | - Production Logs |      | - Deterministic   |      | - MIPROv2 / TextGrad     |  |
|  | - Ground Truth    |      | - LLM-as-a-Judge  |      | - Bayesian Search Loop   |  |
|  +-------------------+      +-------------------+      +--------------------------+  |
|                                                                      |               |
|  +-------------------+      +-------------------+                    v               |
|  | 6. Rollback Engine| <--- | 5. Online Testing | <--- +--------------------------+  |
|  | - Fallback to v1  |      | - Canary / Shadow |      | 4. Artifact Validation   |  |
|  | - PagerDuty Alert |      | - Phoenix / Traces|      | - Test Set Assertions    |  |
|  +-------------------+      +-------------------+      +--------------------------+  |
|                                                                                      |
+--------------------------------------------------------------------------------------+
```

1. **Data Ingestion & Curation**: Mengumpulkan pasangan input-output dari sistem live. Data diverifikasi oleh auditor manusia atau aturan validasi deterministik untuk membentuk training set ($\mathcal{D}_{\text{train}}$) dan test set ($\mathcal{D}_{\text{test}}$).
2. **Metric Definition & Calibration**: Membangun hierarki fungsi evaluasi. Evaluator deterministik (regex, parser, validasi Pydantic) dieksekusi terlebih dahulu. Jika valid, LLM-as-a-Judge dieksekusi dengan kriteria penilaian eksplisit (*rubrics*).
3. **Automated Search Optimization**: Menjalankan *optimizer job* di lingkungan staging menggunakan *dataset splitting* terisolasi guna menghindari data leakage.
4. **Artifact Freezing & Testing**: Menyimpan artefak prompt hasil kompilasi ke dalam model registry (JSON/YAML ter-enkripsi) disertai hash commit git, metrik performa, dan batas toleransi kegagalan.
5. **Shadow Deployment & Canary Testing**: Menjalankan model prompt baru di belakang modul reverse proxy. Persentase kecil dari traffic produksi ($1\% \to 5\% \to 25\% \to 100\%$) diarahkan ke prompt baru secara asinkron untuk memvalidasi performa di dunia nyata.
6. **Automated Rollback & Observability**: Jika metrik inferensi produksi mengalami anomali (peningkatan latensi > 20% atau penurunan *reward score* > 2%), traffic dialihkan seketika ke prompt rilis sebelumnya.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Compiler Optimizing vs. Manual Assembly Coding
* **Manual Prompting** ibarat menulis kode *Assembly* secara manual. Anda mengutak-atik setiap instruksi mikro, bergantung pada memori dan intuisi perakit. Begitu prosesor (LLM) berganti arsitektur dari x86 ke ARM, seluruh optimasi manual menjadi tidak optimal atau rusak total.
* **Automated Prompt Optimization (seperti DSPy)** bertindak sebagai *Optimizing Compiler* (seperti GCC `-O3` atau LLVM). Anda mendefinisikan *High-Level Intent* (Signature: Input $\to$ Output) dan *Test Suite* (Fungsi Metrik). Compiler menganalisis kode sumber, mencoba unrolling loop, menjadwalkan instruksi, dan menghasilkan artefak instruksi biner terbaik (prompt teks optimal + selected few-shots) khusus untuk silikon target (misal: Claude 3.5 Sonnet, GPT-4o, atau Llama 3 70B).

```
Manual Approach (Fragile):
[Developer] --- "Tolong perbaiki kata ini..." ---> [Prompt v1.2] ---> [LLM A (Success)]
                                                                  \-> [LLM B (Failure!)]

Compiler Approach (DSPy / Automated):
[Signature & Intent] + [Dataset D] + [Metric M]
              |
              v
     +------------------+
     | Prompt Optimizer | <--- Auto-tune hyperparams, instructions, & exemplars
     +------------------+
              |
      +-------+-------+
      v               v
 [Prompt for LLM A]  [Prompt for LLM B]
 (Acc: 94.2%)        (Acc: 91.8%)
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Conceptual Discrete Prompt Mutation Engine
Contoh ini mendemonstrasikan fondasi optimasi prompt: search loop berbasis genetic mutation dengan scoring deterministik.

```python
"""
Conceptual Discrete Mutation Optimizer.
Mendemonstrasikan algoritma optimasi prompt diskrit tingkat dasar berbasis mutasi LLM.
"""

from typing import List, Dict, Callable
import random

class SimplePromptOptimizer:
    def __init__(
        self,
        base_prompt: str,
        eval_fn: Callable[[str, Dict[str, str]], bool],
        dataset: List[Dict[str, str]],
    ):
        self.current_prompt = base_prompt
        self.eval_fn = eval_fn
        self.dataset = dataset

    def _simulate_llm_mutation(self, prompt: str) -> str:
        """Simulasi operator mutasi parafrase instruksi."""
        mutations = [
            f"{prompt} Be extremely concise and return strictly the answer.",
            f"Carefully analyze step-by-step before answering. {prompt}",
            f"{prompt} Ensure zero preamble. Format must strictly follow requirements.",
            f"Act as a world-class domain expert. {prompt}",
        ]
        return random.choice(mutations)

    def _evaluate(self, prompt: str) -> float:
        """Kalkulasi fitness score pada dataset."""
        successes = sum(1 for item in self.dataset if self.eval_fn(prompt, item))
        return successes / len(self.dataset)

    def optimize(self, iterations: int = 5) -> str:
        best_score = self._evaluate(self.current_prompt)
        best_prompt = self.current_prompt

        for i in range(iterations):
            candidate = self._simulate_llm_mutation(best_prompt)
            score = self._evaluate(candidate)
            if score > best_score:
                best_score = score
                best_prompt = candidate
                print(f"[Iter {i+1}] Prompt diperbarui! Skor Baru: {best_score:.2f}")

        return best_prompt
```

---

#### 7.2 Practical Example: Enterprise Multi-Stage Optimization Pipeline using DSPy

Berikut adalah implementasi end-to-end berstandar industri menggunakan **DSPy MIPROv2**, lengkap dengan:
1. Validasi skema ketat melalui **Pydantic v2**.
2. Evaluator komposit (Deterministic Schema + LLM-as-a-Judge Semantic Rubric).
3. Penggunaan `dspy.MIPROv2` dengan budget evaluasi dan batching yang terkelola.
4. Serialisasi artefak prompt siap produksi.

```python
import os
import re
import json
from typing import Dict, Any, Optional
import dspy
from pydantic import BaseModel, Field, ValidationError

# =====================================================================
# 1. SETUP ENVIRONMENT & MODEL CONFIGURATION
# =====================================================================

# Inisialisasi model: Teacher/Proposer (lebih cerdas) dan Student/Task Model
proposer_lm = dspy.LM(model="openai/gpt-4o", max_tokens=1000, temperature=0.7)
task_lm = dspy.LM(model="openai/gpt-4o-mini", max_tokens=600, temperature=0.0)

# Konfigurasi runtime default DSPy
dspy.configure(lm=task_lm)

# =====================================================================
# 2. DEFINISI SKEMA OUTPUT & TIPE DATA
# =====================================================================

class FraudAnalysisPayload(BaseModel):
    """Pydantic model untuk validasi payload ekstraksi fraud."""
    is_fraudulent: bool = Field(description="Apakah transaksi diindikasikan fraud.")
    risk_score: float = Field(ge=0.0, le=1.0, description="Tingkat risiko antara 0.0 sampai 1.0.")
    fraud_indicators: list[str] = Field(description="Daftar anomali atau indikator kecurigaan.")
    recommended_action: str = Field(description="Tindakan sistem: APPROVE, MANUAL_REVIEW, REJECT.")

# =====================================================================
# 3. DSPY SIGNATURE & MODULE
# =====================================================================

class FinancialFraudSignature(dspy.Signature):
    """Analisis log audit transaksi perbankan untuk mendeteksi kecurangan finansial."""
    transaction_metadata: str = dspy.InputField(desc="Metadata JSON dari payload transaksi.")
    account_history: str = dspy.InputField(desc="Histori transaksi 30 hari terakhir nasabah.")
    analysis_output: str = dspy.OutputField(desc="JSON string yang mematuhi skema FraudAnalysisPayload.")

class FinancialFraudPipeline(dspy.Module):
    """Pipeline analisis fraud dengan inferensi Chain of Thought."""
    def __init__(self):
        super().__init__()
        self.analyzer = dspy.ChainOfThought(FinancialFraudSignature)

    def forward(self, transaction_metadata: str, account_history: str) -> dspy.Prediction:
        return self.analyzer(
            transaction_metadata=transaction_metadata,
            account_history=account_history
        )

# =====================================================================
# 4. COMPOSITE EVALUATION METRIC (DETERMINISTIC + LLM-AS-A-JUDGE)
# =====================================================================

class MetricJudgeSignature(dspy.Signature):
    """Evaluasi kualitas dan ketajaman analisis fraud terhadap ground truth audit."""
    prediction_raw: str = dspy.InputField()
    ground_truth: str = dspy.InputField()
    verdict_score: float = dspy.OutputField(desc="Nilai float 0.0 - 1.0 berdasarkan akurasi penalaran.")

def enterprise_evaluation_metric(
    example: dspy.Example,
    pred: dspy.Prediction,
    trace: Optional[Any] = None
) -> float:
    """
    Fungsi metrik komposit:
    - 40% Bobot: Parsing integritas format Pydantic (Deterministik)
    - 60% Bobot: Validasi nilai keputusan & Penalaran Semantik (Judge)
    """
    score = 0.0

    # 1. Deterministic Evaluation: Validasi Regex & Validitas Skema Pydantic
    raw_output = pred.analysis_output.strip()
    json_match = re.search(r"\{.*\}", raw_output, re.DOTALL)
    
    if not json_match:
        return 0.0  # Penalti total jika output tidak mengandung format JSON yang valid

    json_str = json_match.group(0)
    try:
        parsed_data = FraudAnalysisPayload.model_validate_json(json_str)
        score += 0.4  # Mendapatkan poin parsing deterministik
    except ValidationError:
        return 0.1  # JSON parseable namun gagal validasi skema nilai

    # 2. Ground-truth Deterministic Matching
    target_data = json.loads(example.ground_truth)
    if parsed_data.is_fraudulent == target_data["is_fraudulent"]:
        score += 0.3
    if parsed_data.recommended_action == target_data["recommended_action"]:
        score += 0.1

    # 3. LLM-as-a-Judge Evaluation: Validasi rasionalitas fraud indicators
    # Hanya dijalankan jika format valid untuk efisiensi komputasi
    if score >= 0.7:
        try:
            with dspy.context(lm=proposer_lm):
                judge = dspy.Predict(MetricJudgeSignature)
                judge_result = judge(
                    prediction_raw=json_str,
                    ground_truth=example.ground_truth
                )
                judge_score = float(judge_result.verdict_score)
                judge_score = max(0.0, min(1.0, judge_score))
                score += (0.2 * judge_score)
        except Exception:
            # Fallback jika model judge mengalami timeout atau unhandled failure
            score += 0.0

    return round(score, 4)

# =====================================================================
# 5. DATASET CURATION & BOOTSTRAPPING
# =====================================================================

raw_training_data = [
    {
        "transaction_metadata": json.dumps({"amount": 150000000, "location": "Lagos, NG", "device": "Linux-Unrecognized"}),
        "account_history": json.dumps({"avg_daily_spend": 200000, "home_base": "Jakarta, ID", "velocity_1h": 8}),
        "ground_truth": json.dumps({
            "is_fraudulent": True,
            "risk_score": 0.95,
            "fraud_indicators": ["Geographical IP Anomaly", "Extreme Transaction Spike", "Rapid Velocity"],
            "recommended_action": "REJECT"
        })
    },
    {
        "transaction_metadata": json.dumps({"amount": 55000, "location": "Jakarta, ID", "device": "iPhone 15 (Known)"}),
        "account_history": json.dumps({"avg_daily_spend": 150000, "home_base": "Jakarta, ID", "velocity_1h": 1}),
        "ground_truth": json.dumps({
            "is_fraudulent": False,
            "risk_score": 0.02,
            "fraud_indicators": [],
            "recommended_action": "APPROVE"
        })
    }
]

# Konversi data mentah menjadi representasi dspy.Example
trainset = [
    dspy.Example(
        transaction_metadata=d["transaction_metadata"],
        account_history=d["account_history"],
        ground_truth=d["ground_truth"]
    ).with_inputs("transaction_metadata", "account_history")
    for d in raw_training_data
]

# =====================================================================
# 6. MIPROv2 OPTIMIZATION EXECUTION
# =====================================================================

def run_prompt_compilation() -> FinancialFraudPipeline:
    print("[+] Menginisialisasi MIPROv2 Optimizer...")
    
    # Inisialisasi MIPROv2 Teleprompter
    teleprompter = dspy.MIPROv2(
        metric=enterprise_evaluation_metric,
        prompt_model=proposer_lm,
        task_model=task_lm,
        num_candidates=3,        # Jumlah instruksi yang di-propose
        init_temperature=0.7,
        verbose=True
    )

    uncompiled_module = FinancialFraudPipeline()

    print("[+] Memulai proses Discrete Bayesian Prompt Search...")
    optimized_module = teleprompter.compile(
        uncompiled_module,
        trainset=trainset,
        max_bootstrapped_demos=2,
        max_labeled_demos=2,
        eval_kwargs={"num_threads": 2}
    )

    print("[+] Kompilasi selesai. Menyimpan modul teroptimasi...")
    optimized_module.save("artifacts/compiled_fraud_pipeline.json")
    return optimized_module

if __name__ == "__main__":
    os.makedirs("artifacts", exist_ok=True)
    compiled_model = run_prompt_compilation()
    
    # Verifikasi eksekusi inferensi pasca-optimasi
    sample_eval = compiled_model(
        transaction_metadata=json.dumps({"amount": 2500000, "location": "Singapore", "device": "Chrome-OS"}),
        account_history=json.dumps({"avg_daily_spend": 300000, "home_base": "Jakarta, ID", "velocity_1h": 2})
    )
    print("\n[+] Hasil Inferensi Teroptimasi:")
    print(sample_eval.analysis_output)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Global FinTech Payment Dispute Routing
* **Klien**: Lembaga Penagihan Pembayaran Lintas Batas (Memproses 800.000 dispute transaksi per hari).
* **Masalah**: Tim kepatuhan (*compliance*) mengandalkan instruksi prompt statis manual setebal 4 halaman yang dijalankan pada model GPT-4. Prompt ini menghasilkan:
  1. Tingkat akurasi pemilahan (*triage accuracy*) stagnan pada angka **76.4%** F1-score.
  2. Latensi rata-rata mencapai **4.8 detik** per kasus akibat konteks instruksi yang terlalu panjang (bloated).
  3. Total tagihan inferensi LLM mencapai **$142.000 / bulan**.

#### Solusi Arsitektural:
1. **Dekomposisi Pipeline**: Prompt monolitik dipecah menjadi 3 sub-modul DSPy: `Classifier`, `PolicyEvidenceExtractor`, dan `DisputeActionRecommender`.
2. **Offline APE Loop**: Menggunakan DSPy MIPROv2 dengan GPT-4o sebagai Proposer dan Llama-3.3-70B-Instruct (Self-hosted pada AWS vLLM) sebagai Student/Task model.
3. **Optimasi Berbasis Metrik**:
   * Menyiapkan 2.000 dataset dispute historis yang telah dianotasi oleh *Chief Legal Counsel*.
   * Memasukkan penalti metrik untuk setiap token di atas kuota ($LatencyPenalty$).
4. **Shadow Validation Pipeline**: Menjalankan evaluasi bayangan (*shadow evaluation*) terhadap 10% traffic live selama 7 hari berturut-turut.

```
+------------------------------------------------------------------------------------+
|                ENTERPRISE CONTINUOUS PROMPT COMPILATION ARCHITECTURE               |
+------------------------------------------------------------------------------------+
|                                                                                    |
| [Incoming Traffic]                                                                 |
|         |                                                                          |
|         v                                                                          |
|  [Ingress Proxy / Router]                                                          |
|         |                                                                          |
|         +---------------------------+ (90% Live Traffic)                           |
|         |                           v                                              |
|         |                 [Production Model]                                       |
|         |                 - Static Baseline Prompt                                 |
|         |                 - GPT-4 API                                              |
|         |                           |                                              |
|         | (10% Shadow Mirror)       v                                              |
|         |                 [Client Response] (Fast path)                            |
|         v                                                                          |
|  [Kafka Audit Queue]                                                               |
|         |                                                                          |
|         +---> [Shadow Executor: Candidate Model (MIPROv2 Prompt)]                  |
|                     |                                                              |
|                     v                                                              |
|         [Comparative Telemetry Store] (Phoenix / ClickHouse)                       |
|                     |                                                              |
|                     +---> F1-Score: 94.1% vs 76.4%                                 |
|                     +---> P99 Latency: 1.1s vs 4.8s                                |
|                     +---> Automated Canary Promotion Engine                        |
+------------------------------------------------------------------------------------+
```

#### Hasil Metrik:
* **F1-Score**: Meningkat dari **76.4%** menjadi **94.1%**.
* **P99 Latency**: Terpangkas dari **4.8 detik** menjadi **1.1 detik**.
* **Biaya Operasional**: Turun sebesar **68%** (dari $142.000 menjadi $45.440/bulan) karena modul yang teroptimasi mampu berjalan pada *smaller/cheaper open-weight models* dengan instruksi minimal yang terbukti efektif.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter | Manual Engineering | Zero-Shot Optimization (APE) | Bayesian Optimization (MIPROv2) | Textual Backpropagation (TextGrad) |
| :--- | :--- | :--- | :--- | :--- |
| **Search Space** | Sangat Rendah | Sedang (Generasi Parafrase) | Sangat Tinggi (Instruksi + Few-Shot) | Luas (Optimasi Multi-Node Bergradien) |
| **Optimization Latency** | Jam - Hari (Manual) | 5 - 15 Menit | 45 Menit - 4 Jam | 1 - 3 Jam |
| **Cost to Optimize** | Biaya Tenaga Kerja | $1 - $5 (Token LLM) | $20 - $80 (Eksplorasi Bayesian) | $40 - $120 (Backward passes per iterasi) |
| **Runtime Inference Latency** | Lambat (Instruksi verbose) | Cepat - Sedang | Sangat Teroptimasi & Ringkas | Tergantung konvergensi teks |
| **Overfitting Risk** | Sangat Subjektif | Rendah | Tinggi jika Trainset < 100 sampel | Sangat Tinggi jika learning rate longgar |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Data Leakage pada Demonstrations Search
* **Kesalahan**: Menggunakan training set yang sama untuk *bootstrap demonstration* dan untuk metrik evaluasi akhir (*evaluation loop*). LLM akan menghafal token spesifik dari kasus validasi (*memorization*).
* **Solusi**: Terapkan *Strict 3-Way Split*: `Train` (hanya untuk bootstrap exemplars), `Validation` (untuk scoring acquisition function Bayesian search), dan `Test` (unseen validation murni untuk verifikasi akhir sebelum deployment).

#### 2. Reward Hacking / Shortcut Learning oleh Optimizer
* **Kesalahan**: Evaluator hanya memeriksa format kembalian (e.g., `return 1.0 if "risk" in output else 0.0`). Optimizer akan belajar menghasilkan instruksi yang menyuruh model menulis kata `"risk"` tanpa mempedulikan analisis kasus sebenarnya.
* **Solusi**: Rancang metrik evaluasi hierarkis berlapis. Gabungkan *deterministic parsing asserts* dengan *adversarial edge cases* dan validasi semantik multi-aspek.

#### 3. Proposer Model Collapse
* **Kesalahan**: Proposer LLM menghasilkan kandidat instruksi yang identik atau berputar-putar dalam repetisi semantik akibat nilai parameter *temperature* yang diset terlalu rendah (misal: 0.0).
* **Solusi**: Atur temperature proposer antara $0.7 - 0.9$ dan aktifkan penalti diversitas (Diversity Penalty) atau embedding-based semantic distance thresholding antar kandidat yang diusulkan.

```python
# Troubleshooting snippet: Mencegah proposal instruksi yang duplikat secara semantik
import numpy as np

def filter_divergent_prompts(
    candidates: list[str],
    similarity_fn: callable,
    max_similarity: float = 0.85
) -> list[str]:
    """Menyaring kandidat instruksi yang identik secara embedding cosine distance."""
    unique_candidates = []
    for cand in candidates:
        if not unique_candidates:
            unique_candidates.append(cand)
            continue
        similarities = [similarity_fn(cand, existing) for existing in unique_candidates]
        if max(similarities) < max_similarity:
            unique_candidates.append(cand)
    return unique_candidates
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Data Stratification**: Memastikan trainset optimasi mencakup distribusi edge-cases minimal 20% dari total variasi sampel produksi.
- [ ] **Deterministic Parsing Guard**: Output schema validasi (e.g., Pydantic) divalidasi sebelum LLM-as-a-Judge dieksekusi guna menghemat kuota biaya token inferensi.
- [ ] **Model Invariance Testing**: Jika pipeline dioptimasi menggunakan Student Model $M_1$, jangan mendistribusikan prompt ke model $M_2$ tanpa melakukan re-kompilasi ulang.
- [ ] **Cost-Bounded Optimization**: Batasi kompilasi menggunakan parameter `max_bootstrapped_demos` dan `num_candidates` yang memiliki batas atas komputasi finansial maksimum (hard stop).
- [ ] **Semantic Drift Alerting**: Pasang telemetry untuk membandingkan output embedding drift antara artefak prompt vCurrent dan vNew secara online.
- [ ] **Automated Fallback Registry**: Sistem runtime harus memuat prompt default (*hardcoded fallbacks*) jika artefak hasil optimasi yang dimuat dari remote store korup atau gagal deserialisasi.

---

### 12. Hands-on Practice

Buat dan simpan file-file praktikum berikut ke dalam direktori: `hands-on/m02/`.

#### Langkah 1: Struktur Direktori
```bash
mkdir -p hands-on/m02/artifacts
cd hands-on/m02/
```

#### Langkah 2: Buat File Konfigurasi Dependency
Simpan sebagai `requirements.txt`:
```text
dspy-ai>=2.5.0
pydantic>=2.7.0
scikit-learn>=1.4.0
python-dotenv>=1.0.0
```

#### Langkah 3: Implementasi Optimizer Script
Simpan kode berikut sebagai `hands-on/m02/cpo_pipeline.py`:

```python
"""
hands-on/m02/cpo_pipeline.py
Pipeline Continuous Prompt Optimization Terotomasi Mandiri.
"""

import os
import json
import dspy
from pydantic import BaseModel, Field

# 1. Definisikan Signature
class CustomerIntentSignature(dspy.Signature):
    """Klasifikasi pesan keluhan pelanggan menjadi aksi mitigasi dan urgensi."""
    customer_message: str = dspy.InputField(desc="Pesan mentah nasabah.")
    classification_result: str = dspy.OutputField(desc="JSON dengan keys: category, priority, escalate.")

# 2. Definisikan Module
class IntentModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.prog = dspy.Predict(CustomerIntentSignature)

    def forward(self, customer_message: str):
        return self.prog(customer_message=customer_message)

# 3. Metrik Evaluasi Sederhana & Cepat
def intent_metric(gold: dspy.Example, pred: dspy.Prediction, trace=None) -> float:
    try:
        data = json.loads(pred.classification_result)
        gold_data = json.loads(gold.classification_result)
        
        matches = 0
        if data.get("category") == gold_data.get("category"):
            matches += 0.5
        if data.get("priority") == gold_data.get("priority"):
            matches += 0.5
        return matches
    except Exception:
        return 0.0

def main():
    # Setup LM Dummy / Test Local jika API key tidak tersedia
    lm = dspy.LM("openai/gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY", "mock-key"))
    dspy.configure(lm=lm)

    # 4. Dataset Mock
    trainset = [
        dspy.Example(
            customer_message="Uang saya terpotong dua kali di ATM BRI tadi pagi!",
            classification_result=json.dumps({"category": "ATM_FAILURE", "priority": "CRITICAL", "escalate": True})
        ).with_inputs("customer_message"),
        dspy.Example(
            customer_message="Bagaimana cara mengubah alamat email di profil saya?",
            classification_result=json.dumps({"category": "ACCOUNT_SETTINGS", "priority": "LOW", "escalate": False})
        ).with_inputs("customer_message")
    ]

    print("[*] Inisialisasi BootstrapFewShot Teleprompter...")
    teleprompter = dspy.BootstrapFewShot(metric=intent_metric, max_labeled_demos=1, max_bootstrapped_demos=1)
    
    print("[*] Mengompilasi Prompt IntentModule...")
    try:
        compiled_system = teleprompter.compile(IntentModule(), trainset=trainset)
        compiled_system.save("artifacts/compiled_intent_model.json")
        print("[+] Sukses mengompilasi dan menyimpan artefak ke: artifacts/compiled_intent_model.json")
    except Exception as e:
        print(f"[-] Terjadi error pada proses eksekusi simulasi: {e}")

if __name__ == "__main__":
    main()
```

#### Langkah 4: Eksekusi Praktikum
```bash
python cpo_pipeline.py
```

---

### 13. Exercise

#### Tingkat Easy
Modifikasi skrip `cpo_pipeline.py` untuk menambahkan field baru `sentiment` (skala 1-5) pada output schema JSON dan tambahkan perhitungan metrik Mean Absolute Error (MAE) sederhana ke dalam fungsi evaluasi.

#### Tingkat Medium
Bangun sistem evaluasi validasi 2-tahap:
1. Tahap 1: Evaluator memvalidasi string regex JSON tanpa memanggil LLM (Biaya $0).
2. Tahap 2: Jika Tahap 1 sukses, jalankan modul DSPy kedua yang bertindak sebagai "Auditor Model" untuk menilai kesopanan respon output. Rancang mekanisme short-circuit execution: jika Tahap 1 gagal, Tahap 2 tidak boleh dipanggil sama sekali.

#### Tingkat Hard
Implementasikan algoritma TextGrad-like loop kustom tanpa library TextGrad eksternal:
1. Bangun pipeline di mana Model A menghasilkan ringkasan teks.
2. Model B (Critic) menghasilkan "Textual Gradient" berupa paragraf instruksi revisi: *"Prompt Anda kurang menekankan aspek X, tambahkan penekanan pada Y"*.
3. Model C (Optimizer) mengambil instruksi Model A, teks evaluasi Model B, lalu merevisi prompt Model A untuk putaran berikutnya.
4. Jalankan iterasi ini sebanyak 3 generasi dan log riwayat mutasi prompt serta nilai fitness-nya.

---

### 14. Challenge

**Skenario**: Anda adalah Staff AI Infrastructure Architect di sebuah perusahaan asuransi berskala global. Sistem Anda harus memvalidasi klaim asuransi polis kecelakaan mobil secara otomatis.
* Dokumen input terdiri dari deskripsi insiden dalam teks bebas berisik (*noisy transcript*).
* Anda harus menghasilkan JSON ketat yang menentukan nilai persentase tanggungan liabilitas (0% - 100%) dan klausul legal pasal yang dilanggar.
* **Kendala Arsitektural**:
  1. Biaya evaluasi prompt tidak boleh melebihi total **$5.00** selama seluruh proses kompilasi berlangsung.
  2. Dilarang melakukan hardcoding instruction string sama sekali pada kode sumber. Semua instruksi harus berawal dari string kosong (`""`) dan dihasilkan secara deterministik melalui *Bayesian MIPROv2 search*.
  3. Prompt yang dihasilkan wajib lolos **100%** terhadap parser skema Pydantic dari 100 data uji *unseen test cases*, serta memiliki skor akurasi hukum minimal **85%** menurut penilaian evaluasi model *Claude-3.5-Sonnet-as-a-Judge*.

Rancang spesifikasi arsitektur sistem, strategi isolasi dataset, definisi metrik objektif anti-reward-hacking, dan parameter kompilasi DSPy yang menjamin kepatuhan terhadap seluruh batas komputasi dan biaya di atas.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Pertanyaan Konseptual Dasar (5 Soal)

1. **Apa perbedaan fundamental antara Discrete Prompt Search dengan optimasi gradien continuous (backpropagation biasa pada bobot model)?**
   * A. Discrete Prompt Search mengubah bobot internal matriks transformer secara perlahan.
   * B. Discrete Prompt Search beroperasi pada ruang token diskrit teks yang non-diferensiabel melalui teknik pencarian/heuristik tanpa memperbarui bobot model LLM.
   * C. Discrete Prompt Search membutuhkan akses langsung ke tensor layer aktivasi LLM.
   * D. Continuous backpropagation tidak membutuhkan fungsi loss atau reward objektif.
   * *Kunci: B. Prompt search tidak memodifikasi weight model melainkan mencari kombinasi string/token diskrit pada input.*

2. **Pada arsitektur DSPy, apa peran utama dari sebuah `Teleprompter` (sekarang disebut `Optimizer`)?**
   * A. Menyimpan log token ke database OpenTelemetry.
   * B. Mengatur inferensi autoregresif menjadi streaming SSE.
   * C. Mengambil program DSPy, metrik, dan dataset pelatihan untuk mengotomatisasi pencarian prompt dan seleksi few-shot demonstrasi yang optimal.
   * D. Menghubungkan client HTTP ke server vLLM secara paralel.
   * *Kunci: C. Optimizer/Teleprompter adalah compiler yang memetakan program DSPy dan metrik ke prompt/demonstrasi teroptimasi.*

3. **Mengapa TextGrad menggunakan konsep "Textual Gradient" alih-alih nilai tensor floating-point?**
   * A. Karena API komersial penyedia LLM (OpenAI/Anthropic) umumnya tidak mengekspos representasi gradien vektor bobot internal kepada publik.
   * B. Karena representasi float tidak kompatibel dengan arsitektur transformer modern.
   * C. Karena nilai numerik float rentan mengalami overflow pada sequence length yang panjang.
   * D. Karena instruksi bahasa alami lebih hemat memori GPU daripada vektor floating point.
   * *Kunci: A. TextGrad diciptakan untuk mengoptimasi sistem AI black-box di mana gradien tensor internal tidak dapat diakses secara langsung.*

4. **Apa yang dimaksud dengan fenomena "Overfitting pada Demonstrasi" dalam automated prompt tuning?**
   * A. Biaya komputasi optimizer meningkat melampaui alokasi memori context window.
   * B. Model LLM menolak mengeksekusi instruksi baru akibat token context window penuh.
   * C. Prompt menyerap pola token spesifik dari dataset pelatihan sehingga performa anjlok drastis saat diuji pada data produksi yang unseen.
   * D. Model Proposer menghasilkan prompt yang formatnya melanggar sintaks bahasa alami.
   * *Kunci: C. Overfitting terjadi ketika few-shots atau instruksi terlalu spesifik terhadap variasi data latih dan gagal digeneralisasi.*

5. **Apa fungsi utama dari Tree-structured Parzen Estimator (TPE) pada algoritma DSPy MIPROv2?**
   * A. Melakukan tokenisasi BPE pada instruksi sistem secara paralel.
   * B. Memodelkan probabilitas kondisional performa konfigurasi instruksi dan few-shots secara Bayesian untuk memandu pemilihan eksperimen berikutnya secara cerdas.
   * C. Mengklasifikasi apakah sebuah pesan input mengandung serangan prompt injection atau tidak.
   * D. Menghapus few-shot examples yang duplikat di dalam database vektor.
   * *Kunci: B. TPE bertindak sebagai algoritma Bayesian Optimization surrogate model untuk mengeksplorasi ruang pencarian secara efisien.*

---

#### Bagian B: Pertanyaan Lanjutan & Analisis Arsitektur (5 Soal)

6. **Dalam evaluasi metrik untuk optimasi prompt terotomasi, mengapa mengandalkan 100% pada evaluasi "LLM-as-a-Judge" berisiko tinggi terhadap proses konvergensi optimizer?**
   * A. Biaya inferensi token Judge model akan selalu berujung pada HTTP error 429.
   * B. LLM-as-a-Judge rentan terhadap *positional bias*, *verbosity bias*, dan *self-enhancement bias*, yang memicu terjadinya fenomena *reward hacking* oleh optimizer.
   * C. LLM-as-a-Judge tidak mampu menghasilkan nilai float antara 0.0 sampai 1.0.
   * D. DSPy melarang penggunaan LLM di dalam fungsi evaluasi metrik.
   * *Kunci: B. Judge models memiliki bias bawaan (menyukai teks panjang, format rapi tetapi halusinasi) yang dieksploitasi oleh optimizer secara keliru.*

7. **Perhatikan skenario berikut: Anda mengompilasi prompt menggunakan MIPROv2 dengan Proposer: GPT-4o dan Student: Llama-3-8B. Hasil prompt berjalan sangat presisi pada Llama-3-8B. Namun ketika diuji pada Mistral-7B, akurasinya jatuh di bawah baseline. Apa penyebab teknis utama fenomena ini?**
   * A. Mistral-7B tidak mendukung inferensi zero-shot berbasis JSON format.
   * B. Format tokenizer dan *inductive bias* pemahaman bahasa tiap LLM berbeda; instruksi dan few-shot yang teroptimasi secara spesifik mengeksploitasi karakteristik representasi model target (Llama-3-8B).
   * C. Optimizer secara otomatis mengubah weight tensor pada Llama-3-8B saja.
   * D. Dataset evaluasi tidak mendukung format tokenisasi Mistral.
   * *Kunci: B. Kompilasi prompt mengoptimasi interaksi terhadap model spesifik; generalisasi lintas arsitektur LLM tidak dijamin (Model Specificity).*

8. **Bagaimana cara mencegah evaluasi parsing Pydantic yang gagal (*JSONDecodeError*) merusak scoring gradien TextGrad atau evaluasi Bayesian?**
   * A. Mengabaikan output yang error dan mengisinya dengan output default ground truth.
   * B. Menerapkan skema penalti diskrit (*Hard Fallback Penalty*), misalnya memberikan skor absolut 0.0 jika format parsing gagal, sehingga optimizer menghindari cabang proposal tersebut.
   * C. Mengubah suhu model target menjadi 2.0 agar model mencoba format acak lain.
   * D. Mematikan skema validasi Pydantic selama siklus optimasi berlangsung.
   * *Kunci: B. Penalti keras (zero reward) pada kegagalan deterministik mutlak memandu optimizer untuk mengeliminasi prompt yang melanggar integritas struktural.*

9. **Mengapa teknik "Shadow Deployment" wajib diterapkan sebelum merilis prompt hasil kompilasi APE ke lingkungan transaksi finansial langsung?**
   * A. Untuk menguji daya tahan beban koneksi database Postgres terhadap beban konkurensi baru.
   * B. Karena performa prompt pada dataset validasi offline dapat mengalami *distribution drift* saat terekspos pada anomali traffic pengguna real-time.
   * C. Karena Shadow Deployment secara otomatis membersihkan cache memori GPU pada cluster inferensi.
   * D. Untuk menghindari pembatasan rate-limit kuota token dari penyedia gateway LLM.
   * *Kunci: B. Validasi offline tidak mencakup keseluruhan keacakan dunia nyata; Shadow deployment memvalidasi reliabilitas model tanpa mengekspos risiko bisnis kepada pengguna.*

10. **Kapan Anda sebaiknya memilih algoritma optimasi `BootstrapFewShot` dibandingkan `MIPROv2` dalam sebuah project enterprise?**
    * A. Ketika Anda memiliki dataset berlabel yang masif (lebih dari 50.000 sampel) dan budget komputasi tanpa batas.
    * B. Ketika Anda membutuhkan optimasi instan, memiliki keterbatasan budget token API yang ketat, dan instruksi dasar (system prompt) sudah ditulis dengan baik secara manual.
    * C. Ketika Anda ingin optimizer menulis ulang sistem instruksi dari nol tanpa campur tangan manusia.
    * D. Ketika Anda menggunakan model embedding alih-alih model bahasa autoregresif.
    * *Kunci: B. BootstrapFewShot hanya bertugas mencari exemplars demonstrasi yang sukses tanpa melakukan komputasi proposal instruksi yang mahal seperti MIPROv2.*

---

#### Bagian C: Pemecahan Masalah Skenario Kasus Produksi (3 Soal)

11. **Skenario Kasus 1: Reward Hacking pada Logistik Medis**
    * *Kasus*: Anda mengoptimasi pipeline ringkasan rekam medis pasien menggunakan metrik kemiripan token ROUGE-L terhadap ringkasan dokter spesialis. Setelah kompilasi, prompt baru menghasilkan skor ROUGE-L sebesar **98.2%**, namun dokter spesialis komplain bahwa hasil ringkasan justru mengabaikan kontraindikasi alergi obat pasien yang sangat fatal.
    * *Akar Masalah & Solusi Arsitektur*: Metrik ROUGE hanya menilai tumpang tindih n-gram secara leksikal, bukan kebenaran klinis (*clinical factual safety*). Optimizer melakukan hacking metrik dengan cara menyalin kalimat panjang yang tidak relevan secara leksikal.
    * *Solusi*: Ubah fungsi metrik evaluasi menjadi kombinasi berbobot: **$0.2 \times \text{ROUGE} + 0.8 \times \text{Deterministic Allergen Assertion}$** (mengecek apakah daftar alergen kritis pada data rekam medis tercantum lengkap di output tanpa halusinasi).

12. **Skenario Kasus 2: Degradasi Latensi Ekstrem Pasca-Optimasi**
    * *Kasus*: Tim ML Anda menggunakan MIPROv2 untuk mengoptimasi customer support triage agent. Akurasi meningkat dari 81% ke 93%. Namun, tim operasional melaporkan bahwa P99 Latency melonjak dari 800ms menjadi 5.2 detik, menyebabkan antrean HTTP request timeout di payment gateway.
    * *Akar Masalah & Solusi Arsitektur*: MIPROv2 memilih terlalu banyak *bootstrapped few-shot examples* (misal: 8 sampel multi-turn conversation) dan menambahkan instruksi penalaran bertahap (Chain-of-Thought) yang sangat panjang, membebani context window dan memperbanyak komputasi output tokens.
    * *Solusi*: Konfigurasi constraint optimizer dengan membatasi `max_bootstrapped_demos=2`, matikan Chain-of-Thought untuk klasifikasi langsung (`dspy.Predict`), dan masukkan penalti latensi/panjang token ke dalam loss function: $\text{Loss} = \text{Score} - \lambda \cdot \max(0, \text{Tokens} - \text{Threshold})$.

13. **Skenario Kasus 3: Kegagalan Deserialisasi Artefak Prompt di Multiple Cluster Node**
    * *Kasus*: Setelah prompt terkompilasi disimpan ke dalam storage S3 (`compiled_model.json`), 4 dari 20 instance worker Kubernetes mengalami crash loop (`KeyError: 'signature_instructions'`) saat runtime bootstrapping.
    * *Akar Masalah & Solusi Arsitektur*: Adanya versi library DSPy yang tidak seragam (mismatch) antar cluster container node (beberapa pod menjalankan versi library lama yang memiliki struktur serialisasi artefak berbeda) atau proses pembacaan file JSON terjadi sebelum file selesai ditulis utuh (race condition write-to-read).
    * *Solusi*: Terapkan validasi skema semantik Pydantic pada artefak prompt sebelum pipeline di-instansiasi. Simpan artefak dengan hashing SHA-256 dan kunci dependensi library (`dspy-ai==2.5.x`) di dalam manifest deployment Kubernetes secara deklaratif dan *immutable*.

---

### 16. Summary

1. **Automated Prompt Engineering (APE)** mengubah paradigma rekayasa prompt dari seni intuisi manual (*trial-and-error*) menjadi proses optimasi diskrit matematis yang terstruktur, deterministik, dan dapat diaudit secara ilmiah.
2. **DSPy MIPROv2** bekerja dengan memisahkan pencarian instruksi (*meta-prompt proposal*) dan demonstrasi (*bootstrapping few-shots*), kemudian mengorkestrasi pencarian ruang kombinasinya secara efisien menggunakan Bayesian Optimization berbasis Tree-structured Parzen Estimator (TPE).
3. **Fungsi Evaluasi (Metrics)** adalah komponen inti optimasi otomatis. Penggunaan evaluasi tunggal LLM-as-a-Judge berisiko memicu fenomena *reward hacking*; sistem enterprise wajib menerapkan **Composite Metrics** yang mengombinasikan validasi struktural deterministik (Pydantic/Regex) dengan evaluasi semantik terkalibrasi.
4. Di lingkungan produksi enterprise, prompt yang terkompilasi harus diperlakukan sebagai **Immutable Software Artifacts**. Pipeline wajib dilengkapi mekanisme **Shadow Deployment**, pemantauan drift latensi/akurasi secara berkelanjutan, serta arsitektur rollback otomatis untuk menjamin stabilitas sistem.