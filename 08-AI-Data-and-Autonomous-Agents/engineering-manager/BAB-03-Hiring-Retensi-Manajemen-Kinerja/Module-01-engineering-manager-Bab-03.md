# Bab 03: Hiring, Retensi, & Manajemen Kinerja
## Module 01: Strategi Hiring, Asesmen Teknis, & Kalibrasi Talenta Autonomous Systems & AI Data Engine

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Engineering Manager (EM) diharapkan mampu:
- **Merancang Kompetensi Matriks (L5–L7)**: Mengidentifikasi pemisah fundamental antara Software Engineer deterministik konvensional, Traditional Data/ML Engineer, dan *Autonomous Agent / Foundation Model Engineer* secara terukur.
- **Mengembangkan Pipeline Asesmen Teknis Anti-Fragile**: Mengonstruksi alur wawancara teknis end-to-end yang menguji intuisi sistem stokastik, debugging latensi/biaya model, mitigasi kegagalan loop otonom, dan rekayasa guardrail tanpa terjebak bias asesmen algoritma klasik.
- **Mengimplementasikan Strategi Anti-Cheating & Pro-Augmentation**: Menerapkan framework wawancara berbasis pairing yang mengevaluasi kemampuan kandidat dalam mengorkestrasi coding assistant (misalnya Cursor, Copilot) sambil tetap memverifikasi penguasaan arsitektur mendalam.
- **Memimpin Kalibrasi Bar-Raiser Berbasis Data**: Mengoperasikan sistem agregasi scorecard berbasis rubrik terstruktur dan mendeteksi anomali penilaian antar-pewawancara menggunakan metrik deviasi terstandardisasi.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Perekrutan talenta pada domain *AI, Data Platforms, and Autonomous Agents* menuntut pergeseran mental model dari verifikasi deterministik ke evaluasi adaptif-stokastik:

```
[Traditional SWE Paradigm]                  [Autonomous Agent / AI Paradigm]
Input + Algoritma = Output Pasti            Prompt/Context + LLM + Tools = Output Probabilistik
Asesmen: Big-O, State Machines, Unit Tests   Asesmen: Convergence, Guardrails, Evals, Drift, Tool Calling
```

Talenta engineering di ranah ini tidak cukup hanya menguasai integrasi API inferensi (`client.chat.completions.create()`). Terdapat empat pilar kompetensi inti:
1. **Sistem Stokastik vs. Deterministik**: Memahami sifat probabilitas LLM, variabilitas output, degradasi reasoning pada context window panjang, serta teknik sampling ($T$, Top-P, Top-K).
2. **Agentic Loops & Failure Modes**: Pengetahuan mendalam mengenai ReAct pattern, recursive tool calls, infinite loop state handling, error recovery, dan perancangan sub-agent orchestration.
3. **Sistem Evaluasi (Evals-driven Development)**: Kemampuan membangun *evaluation harness* otomatis (misal: LLM-as-a-Judge terkalibrasi, metrik ROUGE/BLEU, cosine similarity embedding, semantic exact match).
4. **Data Infrastructure & Inference Economics**: Intuisi terkait GPU serving (vLLM, TGI), cache KV memory footprint, token efficiency, serta arsitektur storage vektor vs. graph database.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Di ranah enterprise, kegagalan dalam strategi hiring talenta AI membawa risiko finansial dan operasional yang jauh lebih tinggi dibanding software deterministik:
- **Biaya Token & Latency Explosion**: Kandidat yang tidak memahami mekanisme *context pruning* dan *caching* dapat merilis sistem otonom yang membengkakkan tagihan API provider hingga puluhan ribu USD per hari serta memicu latensi timeout pada downstream microservice.
- **The "Demo Trap" (Paper Tiger)**: Banyak kandidat mampu membangun demo agent dalam waktu 15 menit menggunakan framework *high-level* (LangChain, CrewAI), tetapi gagal total ketika harus menangani *cascading hallucinations*, sinkronisasi state terdistribusi, atau mengimplementasikan retry pattern idempotensi saat model memproduksi format JSON yang invalid.
- **Flawed Evaluation Strategies**: Mempekerjakan talenta murni akademik tanpa pemahaman production SWE sering kali berujung pada arsitektur spaghetti yang tidak dapat di-scale, minim observability, serta nihil unit testing/CI/CD pipelines.

---

### 4. Arsitektur & Diagram Komponen

Alur hiring engineering terstruktur untuk domain AI & Autonomous Systems harus didesain untuk menyaring noise sejak awal, menguji trade-off production secara live, dan mengevaluasi kandidat melalui sistem penilaian yang terbebas dari bias subjektif:

```
+--------------------------------------------------------------------------------------------------+
|                                TALENT PIPELINE & CALIBRATION HARNESS                             |
+--------------------------------------------------------------------------------------------------+

  [ Inbound / Sourced ] 
           |
           v
  +-----------------------+     Fail
  |  1. Asynchronous      | -------------> [ Polite Rejection + Talent Pool DB ]
  |  Screening Portfolio  |
  +-----------------------+
           | Pass (Domain alignment)
           v
  +-----------------------+     Fail
  |  2. EM Exploratory    | -------------> [ Polite Rejection ]
  |  & Ambiguity Check    |
  +-----------------------+
           | Pass (Culture, System ownership, Comp alignment)
           v
  +----------------------------------------------------------------------+
  |                     3. Technical Onsite Loop                         |
  |                                                                      |
  |  +---------------------------+   +--------------------------------+  |
  |  | Round 3.1: Live Stochastic|   | Round 3.2: Autonomous Agent    |  |
  |  | Code Pairing & Guardrails |   | System Architecture Design     |  |
  |  | (Deterministic/Async/Eval)|   | (Tools, Memory, Failure State) |  |
  |  +---------------------------+   +--------------------------------+  |
  |                 |                                |                   |
  |  +---------------------------+   +--------------------------------+  |
  |  | Round 3.3: Production ML  |   | Round 3.4: Behavioral &        |  |
  |  | Inference & Data Platform |   | Cross-Functional Collaboration |  |
  |  | (vLLM, RAG, Latency/Cost) |   | (Product vs Tech Ambiguity)    |  |
  |  +---------------------------+   +--------------------------------+  |
  +----------------------------------------------------------------------+
           | Complete Scorecards
           v
  +----------------------------------------------------------------------+
  | 4. Calibration & Bar Raiser Engine                                   |
  | - Strict Rubric-based Scoring (1 - 4 Scale)                          |
  | - Variance & Bias Analysis (Inter-Interviewer Drift)                 |
  | - Bar-Raiser Veto Power (Non-Hiring Manager)                         |
  +----------------------------------------------------------------------+
           |
     +-----+-----+
     |           |
     v           v
  [ OFFER ]   [ REJECT ]
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Competency Rubric: L5 (Senior) vs L6 (Staff) Autonomous Agent Engineer

Penilaian objektif memerlukan rubrik bertingkat yang mendefinisikan ekspektasi perilaku teknis secara eksplisit:

| Dimensi Penilaian | L5 (Senior Autonomous Agent Engineer) | L6 (Staff / Principal Agent Engineer) |
| :--- | :--- | :--- |
| **Agent Loops & Routing** | Mengimplementasikan routing multi-agent deterministik, mendesain conditional fallback saat tools timeout, memvalidasi JSON schema secara strict. | Merancang dynamic self-healing loops, hierarchical planning topologies, serta arsitektur state persistence terdistribusi. |
| **Evals & Alignment** | Mampu membangun automated test set (Golden Datasets) dengan metrik komparasi statis, serta mengukur precision/recall tool selection. | Merancang platform evaluasi continuous synthetic data generation, kalibrasi LLM-as-a-judge dengan human correlation > 0.85, dan cost-performance Pareto frontiers. |
| **Context & Memory Ops** | Memahami RAG architecture: hybrid search (BM25 + Dense vector), reranking, metadata filtering, chunking strategies. | Merancang dynamic context optimization, short-term vs long-term multi-tier episodic memory systems, serta semantic KV-caching custom. |
| **Failure Mode Handling** | Mampu melakukan mitigasi infinite recursion, membatasi max budget token/step, menerapkan exponential backoff. | Mendesain circuit-breakers level platform, dynamic fallback to smaller distilled SLMs, mitigasi dynamic prompt injection adversarial attacks. |

#### B. The Live Agent Code Pairing Format (Anti-Cheating by Design)
Daripada memberikan tugas take-home tanpa pengawasan (yang rentan diselesaikan 100% oleh LLM tanpa pemahaman mendalam) atau LeetCode murni:
1. **Provide a Flawed Agent Base**: Berikan codebase starter yang berisi agen otonom sederhana dengan integrasi model yang memiliki *latent bugs* (misalnya: tidak ada penanganan schema failure saat tool execution, context window blow-up karena appending history mentah, dan tidak ada deteksi cyclic action).
2. **Explicitly Encourage LLM Usage**: Kandidat diizinkan menggunakan Copilot/Cursor. Evaluasi bagaimana mereka memformulasi instruksi debugging, apakah mereka mampu mendeteksi kode buruk yang disarankan oleh LLM, dan bagaimana mereka memverifikasi logika rekursif secara deterministik.
3. **Observation Points**: 
   - Apakah kandidat memeriksa edge cases API (rate limits, context truncation)?
   - Apakah kandidat menerapkan typing ketat dan structured schema parsing?
   - Bagaimana kandidat mengukur apakah "perbaikan" yang mereka buat benar-benar meningkatkan success rate?

---

### 6. Production-Ready Code Implementation

Berikut adalah sistem komputasi kalibrasi rubrik perekrutan (`TalentCalibrationEngine`) berbasis Python yang digunakan oleh Engineering Manager untuk:
1. Mengagregasi scorecard interview loop.
2. Memverifikasi kelengkapan penilaian pada pilar inti AI Engineering.
3. Mendeteksi bias interviewer (variance & outlier detection).
4. Menghitung status keputusan rekomendasi final dengan mekanisme veto *Bar Raiser*.

```python
"""
Module: talent_calibration_engine.py
Architecture: Clean Architecture / Scoring Domain Engine for AI Team Hiring.
Features: Type-hinted, Pydantic-validated, Outlier Detection, Bar-Raiser Enforcement.
"""

from __future__ import annotations

import statistics
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class CompetencyDomain(str, Enum):
    STOCHASTIC_SYSTEMS = "stochastic_systems"
    AGENTIC_ARCHITECTURE = "agentic_architecture"
    EVALS_AND_ALIGNMENT = "evals_and_alignment"
    DATA_AND_INFRA_ECONOMICS = "data_and_infra_economics"
    SYSTEM_DESIGN_PRAGMATISM = "system_design_pragmatism"
    LEADERSHIP_AND_AMBIGUITY = "leadership_and_ambiguity"


class ScoreValue(int, Enum):
    STRONG_NO_HIRE = 1
    NO_HIRE = 2
    HIRE = 3
    STRONG_HIRE = 4


class InterviewRound(BaseModel):
    interviewer_id: str = Field(..., min_length=3)
    round_name: str = Field(..., min_length=3)
    is_bar_raiser: bool = False
    scores: Dict[CompetencyDomain, ScoreValue]
    notes: str = Field(..., min_length=20, description="Constructive qualitative evidence")

    @field_validator("scores")
    @classmethod
    def validate_scores_not_empty(cls, v: Dict[CompetencyDomain, ScoreValue]) -> Dict[CompetencyDomain, ScoreValue]:
        if not v:
            raise ValueError("Scorecard must contain evaluation for at least one domain.")
        return v


class CalibrationInput(BaseModel):
    candidate_id: str = Field(..., min_length=3)
    target_level: str = Field(..., pattern=r"^L[5-7]$")
    rounds: List[InterviewRound] = Field(..., min_length=3)

    @model_validator(mode="after")
    def validate_bar_raiser_presence(self) -> CalibrationInput:
        bar_raiser_count = sum(1 for r in self.rounds if r.is_bar_raiser)
        if bar_raiser_count != 1:
            raise ValueError(f"Loop must contain exactly 1 Bar Raiser scorecard. Found: {bar_raiser_count}")
        return self


class CalibrationResult(BaseModel):
    candidate_id: str
    target_level: str
    composite_score: float
    bar_raiser_approved: bool
    domain_averages: Dict[CompetencyDomain, float]
    interviewer_variance: float
    recommendation: str
    flags: List[str]


class TalentCalibrationEngine:
    """
    Engine untuk mengkuantifikasi dan mengalibrasi hasil interview loop tim AI/Agent.
    Menjamin objektivitas melalui deteksi disparitas penilaian dan veto Bar Raiser.
    """

    def __init__(self, variance_threshold: float = 1.0) -> None:
        self.variance_threshold = variance_threshold

    def evaluate_candidate(self, payload: CalibrationInput) -> CalibrationResult:
        flags: List[str] = []
        domain_tallies: Dict[CompetencyDomain, List[int]] = {d: [] for d in CompetencyDomain}
        round_averages: List[float] = []
        bar_raiser_approved = False

        for r in payload.rounds:
            round_numeric_scores = [score.value for score in r.scores.values()]
            round_avg = statistics.mean(round_numeric_scores)
            round_averages.append(round_avg)

            if r.is_bar_raiser:
                # Bar Raiser passes candidate if average >= 3 (Hire) and no Strong No Hire
                if round_avg >= 3.0 and ScoreValue.STRONG_NO_HIRE not in r.scores.values():
                    bar_raiser_approved = True
                else:
                    flags.append("BAR_RAISER_VETO: Bar raiser provided rejection or low scoring.")

            for domain, score in r.scores.items():
                domain_tallies[domain].append(score.value)

        # 1. Check Domain Coverage
        missing_critical_domains = [
            domain.value
            for domain in [
                CompetencyDomain.STOCHASTIC_SYSTEMS,
                CompetencyDomain.AGENTIC_ARCHITECTURE,
                CompetencyDomain.EVALS_AND_ALIGNMENT,
            ]
            if len(domain_tallies[domain]) == 0
        ]
        if missing_critical_domains:
            flags.append(f"UNASSESSED_CRITICAL_DOMAINS: {missing_critical_domains}")

        # 2. Inter-rater Variance Analysis
        interviewer_variance = statistics.variance(round_averages) if len(round_averages) > 1 else 0.0
        if interviewer_variance > self.variance_threshold:
            flags.append(
                f"HIGH_SCORER_DISPARITY: Variance of {interviewer_variance:.2f} exceeds threshold of {self.variance_threshold}."
            )

        # 3. Domain Aggregation
        domain_averages: Dict[CompetencyDomain, float] = {}
        all_scores: List[int] = []
        for domain, scores in domain_tallies.items():
            if scores:
                domain_averages[domain] = round(statistics.mean(scores), 2)
                all_scores.extend(scores)

        composite_score = round(statistics.mean(all_scores), 2) if all_scores else 0.0

        # 4. Final Recommendation Logic
        recommendation = self._determine_recommendation(
            composite_score=composite_score,
            bar_raiser_approved=bar_raiser_approved,
            target_level=payload.target_level,
            flags=flags,
        )

        return CalibrationResult(
            candidate_id=payload.candidate_id,
            target_level=payload.target_level,
            composite_score=composite_score,
            bar_raiser_approved=bar_raiser_approved,
            domain_averages=domain_averages,
            interviewer_variance=round(interviewer_variance, 3),
            recommendation=recommendation,
            flags=flags,
        )

    def _determine_recommendation(
        self,
        composite_score: float,
        bar_raiser_approved: bool,
        target_level: str,
        flags: List[str],
    ) -> str:
        if not bar_raiser_approved:
            return "REJECT (Bar Raiser Veto)"

        if any("UNASSESSED_CRITICAL_DOMAINS" in f for f in flags):
            return "HOLD (Missing Core Domain Assessment)"

        # Higher bar for L6+
        threshold = 3.2 if target_level in ["L6", "L7"] else 2.8

        if composite_score >= threshold:
            if any("HIGH_SCORER_DISPARITY" in f for f in flags):
                return "CALIBRATION_DEBRIEF_REQUIRED (Polarized Feedback)"
            return "STRONG_OFFER" if composite_score >= 3.6 else "OFFER"
        else:
            return "REJECT (Below Bar Score Threshold)"


if __name__ == "__main__":
    # Test Payload Simulating Real Loop
    sample_loop = CalibrationInput(
        candidate_id="cand_agent_eng_091",
        target_level="L6",
        rounds=[
            InterviewRound(
                interviewer_id="int_swe_lead",
                round_name="Live Agent Coding & Debugging",
                is_bar_raiser=False,
                scores={
                    CompetencyDomain.STOCHASTIC_SYSTEMS: ScoreValue.HIRE,
                    CompetencyDomain.AGENTIC_ARCHITECTURE: ScoreValue.STRONG_HIRE,
                },
                notes="Excellent grasp of tool retry handling and fallback JSON schema repair logic.",
            ),
            InterviewRound(
                interviewer_id="int_mlops_staff",
                round_name="Autonomous System Architecture",
                is_bar_raiser=False,
                scores={
                    CompetencyDomain.DATA_AND_INFRA_ECONOMICS: ScoreValue.HIRE,
                    CompetencyDomain.SYSTEM_DESIGN_PRAGMATISM: ScoreValue.STRONG_HIRE,
                },
                notes="Deep intuition regarding token pricing curves, vLLM throughput, and KV cache sizing.",
            ),
            InterviewRound(
                interviewer_id="int_bar_raiser",
                round_name="Bar Raiser - Alignment & Evals",
                is_bar_raiser=True,
                scores={
                    CompetencyDomain.EVALS_AND_ALIGNMENT: ScoreValue.HIRE,
                    CompetencyDomain.LEADERSHIP_AND_AMBIGUITY: ScoreValue.HIRE,
                },
                notes="Understands LLM-as-a-judge limits and demonstrated bias identification in ground truth sets.",
            ),
        ],
    )

    engine = TalentCalibrationEngine(variance_threshold=0.8)
    result = engine.evaluate_candidate(sample_loop)
    print("=== CALIBRATION RESULT ===")
    print(result.model_dump_json(indent=2))
```

---

### 7. Edge Cases & Failure Modes

Dalam hiring spesialis AI dan Autonomous Systems, kegagalan umum terjadi pada bias evaluasi dan celah teknis:

1. **The "Paper Author / Kaggle Grandmaster" Trap**:
   - *Failure Mode*: Kandidat memiliki portofolio publikasi prestisius atau ranking kompetisi tinggi, namun tidak memahami software engineering modern (Clean Code, Asynchronous I/O, Testing, CI/CD, Containerization).
   - *Mitigation*: Selalu terapkan *hard-filter* pada live coding engineering dasar sebelum masuk ke sesi modeling.

2. **The LLM Hallucination Apologist**:
   - *Failure Mode*: Kandidat menganggap kegagalan inferensi atau halusinasi sebagai *unavoidable feature* ("Modelnya memang begitu dari OpenAI"), tanpa strategi mitigasi proaktif.
   - *Mitigation*: Berikan skenario error konkret: *"Bagaimana Anda merancang sistem transfer dana perbankan berbasis LLM agent tanpa risiko double withdrawal atau salah nominal akibat halusinasi?"* Tolak kandidat yang tidak menawarkan arsitektur deterministik guardrail (State Machines, Database Locks, Human-in-the-loop triggers).

3. **Interviewer Polarization (Vibe-Coding Bias)**:
   - *Failure Mode*: Pewawancara deterministik tradisional memberikan nilai 1 (Strong No Hire) karena kandidat tidak menghafal algoritma red-black tree, sedangkan pewawancara AI product memberikan nilai 4 (Strong Hire) karena kandidat fasih berdiskusi tentang prompt chaining.
   - *Mitigation*: Gunakan deteksi varians inter-rater pada engine kalibrasi. Wajibkan debrief rapat sinkron jika $\sigma^2 > 0.8$ untuk menyelaraskan pemahaman rubrik.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter | Approach A: Take-Home AI Project | Approach B: Live Debugging & Pairing (Direkomendasikan) | Approach C: LeetCode + ML Theory Q&A |
| :--- | :--- | :--- | :--- |
| **Sinyal Kualitas Kode** | Rendah (Terganggu penggunaan LLM asisten tanpa pengawasan). | **Sangat Tinggi** (Melihat live reasoning, prompt editing, debugging). | Tinggi untuk sintaks dasar, Rendah untuk arsitektur sistem. |
| **Evaluasi Sistem Stokastik**| Parsial (Sering kali hanya memverifikasi skenario ideal / *happy path*). | **Tinggi** (Pewawancara dapat menyuntikkan failure mode tak terduga secara real-time). | Nihil (Hanya menguji algoritma deterministik). |
| **Beban Kandidat (Candidate Drop-off)** | Sangat Tinggi (Kandidat senior sering kali menolak tugas > 4 jam). | **Rendah** (Terjadwal pasti, maksimal 60–90 menit per sesi). | Rendah hingga Sedang. |
| **Waktu Pewawancara** | Sedang (Perlu mereview pull request). | Tinggi (Wajib sinkron live). | Rendah (Bisa diotomasi platform online). |

---

### 9. Best Practices & Standar Industri

1. **Mekanisme Bar-Raiser Independen**: Tunjuk satu orang Bar-Raiser di luar tim yang merekrut. Bar-Raiser memegang hak veto mutlak terhadap keputusan akhir untuk mencegah kompromi standar akibat kepanikan manajer yang kekurangan kapasitas tim (*desperation hiring*).
2. **Standardized Anchor Questions**: Gunakan bank soal arsitektur sistem agen otonom yang sama selama minimal 6 bulan untuk mengumpulkan data pembanding performa antar kandidat.
3. **Structured Scorecard SLA**: Wajibkan submission scorecard dalam waktu maksimal 2 jam setelah wawancara selesai. Melarang pewawancara saling membaca feedback sebelum seluruh scorecard terkumpul (*preventing anchoring bias*).
4. **Transparent Comp-Band Calibration**: Kaitkan level L5–L7 langsung dengan metrik kemandirian arsitektur. L5 mengeksekusi arsitektur agent yang telah ditentukan, L6 merancang platform agent terdistribusi dan framework evaluasi tim, L7 menentukan strategi adopsi model enterprise vs distilled open-source.

---

### 10. Hands-on Lab Exercise

#### Skenario Kasus
Tim Anda sedang membangun *Enterprise Support Autonomous Agent* yang bertugas membaca dokumen SLA, mengueri database billing via SQL, dan memicu refund melalui REST API internal. Anda perlu merancang paket asesmen wawancara teknis 60 menit untuk kandidat **Senior Autonomous Agent Engineer (L5/L6)**.

#### Instruksi Langkah-demi-Langkah

##### Step 1: Merumuskan Soal Debugging Live Pairing
Siapkan mock repository Python yang memiliki arsitektur sub-agent sederhana yang mengalami *infinite recursive loop* saat tool SQL mengembalikan `Empty Result Set`.

*File: `broken_agent_snippet.py`*
```python
# Berikan kode ini kepada kandidat saat live interview
import json

class SimpleAgent:
    def __init__(self, tools: dict):
        self.tools = tools
        self.history = []

    def execute_step(self, user_query: str) -> str:
        self.history.append({"role": "user", "content": user_query})
        
        # Simulasi LLM Call tanpa guardrail limit
        while True:
            # Bug 1: Tidak ada context truncation -> Token overflow
            # Bug 2: Tidak ada tracking depth counter -> Infinite loop
            action_decision = self._mock_llm_decide(self.history)
            
            if action_decision["action"] == "finish":
                return action_decision["output"]
            
            tool_name = action_decision["action"]
            tool_args = action_decision["args"]
            
            # Bug 3: Eksekusi tool tanpa try-catch & parsing validation
            tool_output = self.tools[tool_name](**tool_args)
            self.history.append({"role": "tool", "content": json.dumps(tool_output)})

    def _mock_llm_decide(self, history):
        # Stub logic yang mereproduksi siklus kegagalan kandidat
        last_entry = history[-1]["content"]
        if "empty" in str(last_entry).lower():
            # LLM panik dan terus mencoba query yang sama
            return {"action": "sql_query", "args": {"query": "SELECT * FROM billing WHERE id=UNKNOWN"}}
        return {"action": "sql_query", "args": {"query": "SELECT * FROM billing"}}
```

##### Step 2: Mengisi Template Rubrik Observasi Pewawancara
Evaluasi kandidat menggunakan rubrik observasi berikut selama sesi berlangsung:

```markdown
### Interviewer Scorecard Matrix
Candidate Name: _______________________
Target Level: [ ] L5 Senior  [ ] L6 Staff

1. Deteksi Infinite Loop & State Recovery (Bobot: 30%)
   - [ ] Fail (Score 1): Tidak menyadari infinite loop; hanya memodifikasi query SQL string.
   - [ ] Meet (Score 3): Menambahkan max_steps / recursion_limit serta graceful exit fallback.
   - [ ] Exceed (Score 4): Mengimplementasikan circuit-breaker pattern, short-circuit validation, 
                          dan feedback loop injection ke LLM untuk memperbaiki instruksi.

2. Context Window Management & Memory Optimization (Bobot: 30%)
   - [ ] Fail (Score 1): Membiarkan list history membengkak tanpa mitigasi.
   - [ ] Meet (Score 3): Menerapkan sliding-window atau token count cutoff terhitung.
   - [ ] Exceed (Score 4): Mengimplementasikan semantic summarization pada intermediate tool responses
                          serta pruning data SQL berukuran besar.

3. Structured Output & Safety Guardrails (Bobot: 40%)
   - [ ] Fail (Score 1): Menganggap JSON parsing dari LLM selalu valid tanpa schema engine.
   - [ ] Meet (Score 3): Membungkus parsing menggunakan Pydantic dengan penanganan ValidationError.
   - [ ] Exceed (Score 4): Merancang deterministic schema validation layer dengan retry prompt
                          yang mengembalikan error traceback secara presisi ke LLM.
```

##### Step 3: Menjalankan Kalibrasi Pasca-Wawancara
Kumpulkan seluruh skor dari pewawancara, jalankan script `talent_calibration_engine.py`, pastikan tidak ada indikasi polarisasi ekstrem, dan buat ringkasan hiring memo formal untuk dibagikan saat engineering hiring debrief.