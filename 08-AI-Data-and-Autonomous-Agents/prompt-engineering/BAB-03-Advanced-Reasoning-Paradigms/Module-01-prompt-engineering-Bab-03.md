# Bab 03: Advanced Reasoning Paradigms — Module 01

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis & Mengklasifikasikan Pola Inferensi LLM**: Mengidentifikasi batasan arsitektur *autoregressive next-token prediction* dan membedakan kebutuhan antara inferensi linear (Zero-Shot/Few-Shot CoT) dengan penalaran non-linear (*Tree-of-Thoughts*, *Graph-of-Thoughts*).
- **Merancang Arsitektur Search-Based Reasoning**: Membangun state machine penalaran berbasis pohon (*Tree-of-Thoughts*) dan graf (*Graph-of-Thoughts*) menggunakan algoritma pencarian deterministik (BFS, DFS, A\*) yang diorkestrasi melalui prompt template terstruktur.
- **Mengimplementasikan Self-Consistency Sampling & Ensembling**: Menyusun pipeline agregasi stokastik dengan *temperature scheduling* dan *majority voting/Borda count* untuk menekan tingkat halusinasi pada domain penalaran deterministik.
- **Mengoptimalkan Token Budget & Latency Trade-offs**: Mengaudit rasio efisiensi komputasi ($Cost/Accuracy$) dengan menerapkan teknik *dynamic beam pruning*, *early exit*, dan *state caching*.
- **Membangun Production-Ready Reasoning Engine**: Menulis kode Python level produksi yang *thread-safe*, *type-hinted*, memiliki *structured error recovery*, serta validasi runtime berbasis Pydantic.

---

## 2. Concept Overview

Model bahasa besar (LLM) pada hakikatnya adalah aproksimator fungsi probabilitas sekuensial:

$$P(w_{t} \mid w_{1}, w_{2}, \dots, w_{t-1})$$

Ketika dihadapkan pada tugas penalaran multitahap (perencanaan strategis, matematika simbolik, optimasi combinatorial), generasi autoregresif linear rentan mengalami **Cognitive Drift** dan akumulasi kesalahan (*cascading failure*). Begitu token suboptimal masuk ke dalam *context window*, model mengondisikan komputasi berikutnya pada premis yang salah tersebut.

```
Linear CoT (Greedy/Single Path):
[Input Problem] ──> [Step 1] ──> [Step 2 (Faulty)] ──> [Step 3 (Compounded Error)] ──> [Wrong Output]

Tree-of-Thoughts (ToT - Exploration & Backtracking):
                  ┌──> [Step 1A] ──> [Step 2A (Score: 0.2)] ──> [PRUNED]
[Input Problem] ──┼──> [Step 1B] ──> [Step 2B (Score: 0.9)] ──> [Step 3B (Target)] ──> [Valid Output]
                  └──> [Step 1C] ──> [Step 2C (Score: 0.4)] ──> [PRUNED]
```

Untuk mentransformasi model autoregresif dari sekadar generator teks menjadi unit pemecah masalah algoritmik, paradigma penalaran harus dialihkan dari **Sequential Generation** ke **State-Space Search**:

1. **Chain-of-Thought (CoT)**: Mengubah pemetaan $X \to Y$ langsung menjadi $X \to z_1 \to z_2 \dots \to Y$, di mana $z_i$ adalah token penalaran laten perantara.
2. **Self-Consistency (CoT-SC)**: Melakukan marginalisasi terhadap jalur penalaran perantara dengan *sampling* $N$ jalur acak dan mengambil modus statistik dari hasil akhir: $\arg\max_y \sum_{i=1}^N \mathbb{I}(f(z^{(i)}) = y)$.
3. **Tree-of-Thoughts (ToT)**: Memformalkan proses penalaran sebagai penelusuran graf asiklik terarah (DAG) pohon, di mana tiap simpul adalah *thought chunk* (satuan pemikiran), dan transisi antar simpul dipandu oleh generator kandidat pikiran (*thought generation*) serta fungsi evaluasi nilai (*state evaluation/heuristic value*).
4. **Graph-of-Thoughts (GoT)**: Memperluas ToT dengan mengizinkan *arbitrary directed graph operations*, termasuk penyatuan pikiran (*thought aggregation/merging*), pembaruan rekursif (*looping back*), dan dekomposisi masalah menjadi sub-graf independen.

---

## 3. Why It Matters: Real-World & Enterprise Impact

Pada domain produksi enterprise, kesalahan penalaran LLM bukan sekadar masalah estetika; ini berdampak finansial dan operasional langsung:
- **Analisis Kepatuhan Regulasi & Finansial**: Validasi struktur utang lintas yurisdiksi memerlukan dekomposisi ratusan klausul kontrak. Kegagalan mengevaluasi cabang implikasi hukum memicu sanksi kepatuhan (*regulatory non-compliance*).
- **Automated Root Cause Analysis (RCA)**: Saat sistem telemetri terdistribusi mengalami *outage*, agen harus melakukan isolasi dependensi secara non-linear (memeriksa metrik DB, logs jaringan, dan *recent deployments* secara paralel), bukan sekadar menebak linearitas gejala.
- **Optimasi Rantai Pasok Kombinatorik**: Alokasi kargo multi-titik membutuhkan evaluasi cabang alternatif rute dengan konstrain kapasitas nyata. CoT standar gagal pada ruang pencarian berukuran faktorial ($O(n!)$).

Dengan mengimplementasikan **Advanced Reasoning Paradigms**, enterprise beralih dari model *single-shot guessing* (yang membutuhkan akurasi prompt manual ekstrem) menuju *systemic search guarantees* yang dapat diaudit, diukur performa per simpulnya, dan dipangkas secara deterministik sebelum mengonsumsi token API yang mahal.

---

## 4. Architecture & Component Diagram

Berikut adalah arsitektur sistem penalaran non-linear modular yang memadukan generator, evaluator, dan penelusur state (*search orchestrator*):

```
+---------------------------------------------------------------------------------------------------+
|                                PRODUCTION REASONING ENGINE                                        |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
                                       ┌─────────────────────┐
                                       │ Problem Formulation │
                                       └──────────┬──────────┘
                                                  │
                ┌─────────────────────────────────┴─────────────────────────────────┐
                ▼                                                                   ▼
+────────────────────────────────+                                +────────────────────────────────+
|   THOUGHT GENERATOR (PROMPT)   |                                |   STATE EVALUATOR (PROMPT)     |
| - Sample k Candidate Actions   |                                | - Classify: Sure/Likely/No     |
| - Strategy: Propose / Sample   |                                | - Scalar Scoring: [0.0 - 1.0]  |
+────────────────┬───────────────+                                +────────────────┬───────────────+
                 │                                                                 │
                 └───────────────────────────────┬─────────────────────────────────┘
                                                 │
                                                 ▼
                              +──────────────────────────────────────+
                              |         SEARCH CONTROLLER            |
                              | - Tree/Graph Representation (Memory) |
                              | - Policy: BFS / DFS / Beam Search    |
                              | - Dynamic Pruning (Threshold θ)      |
                              | - Budget Guard (Max Depth & Tokens)  |
                              +──────────────────┬───────────────────+
                                                 │
                                                 ▼
                               +────────────────────────────────----+
                               |     VERIFIER & AGGREGATOR ENGINE   |
                               | - Majority Voting / Borda Count    |
                               | - Cycle Detection & Deduplication  |
                               +─────────────────┬──────────────────+
                                                 │
                                                 ▼
                                     ┌───────────────────────┐
                                     │ Final Verified Output │
                                     └───────────────────────┘
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Formalisasi Tree-of-Thoughts (ToT)
ToT memandang pemecahan masalah sebagai traversal pada state space $\mathcal{S}$.
Sebuah state $s = [x, z_{1\dots i}]$ merepresentasikan sekuens input $x$ dan $i$ langkah pemikiran yang telah dieksplorasi.

Proses ToT terbagi atas 4 elemen fundamental:
1. **Thought Decomposition**: Mengubah masalah menjadi unit pemikiran diskret. Contoh: alih-alih meminta seluruh kode program, satu langkah dibatasi hanya mendesain *interface signature*, langkah berikutnya mendesain algoritma internal, dst.
2. **Thought Generator $G(p_\theta, s, k)$**: Menghasilkan $k$ kandidat pemikiran berikutnya untuk state $s$:
   - *Sample*: Menghasilkan $k$ pemikiran secara independen via I.I.D. decoding (berguna jika ruang pemikiran luas/kreatif).
   - *Propose*: Menghasilkan $k$ kandidat sekaligus dalam satu konteks prompt terstruktur (efisien token untuk ruang konstrain terbatas).
3. **State Evaluator $V(p_\theta, \mathcal{S})$**: Memberikan nilai heuristik pada state $s$:
   - *Value Scoring*: Memberikan nilai skalar $v \in [0, 1]$ secara langsung.
   - *Classification / Voting*: Melakukan kategorisasi diskret (`Sure`, `Likely`, `Impossible`) terhadap kelayakan state mencapai solusi akhir.
4. **Search Algorithm**:
   - **Breadth-First Search (BFS)**: Mempertahankan $b$ state terbaik di setiap level kedalaman (Beam Search). Cocok jika kedalaman pohon terbatas ($D \le 4$).
   - **Depth-First Search (DFS)**: Mengeksplorasi cabang hingga mentok, mengevaluasi status final, dan melakukan *backtracking* jika skor jatuh di bawah ambang batas $\tau$. Cocok untuk pencarian solusi tunggal optimal pada ruang masalah dalam.

### 5.2 Self-Consistency Sampling & Voting Entropy
Self-Consistency bergantung pada hipotesis bahwa jalur penalaran yang benar cenderung konvergen pada ruang jawaban yang sama, sedangkan jalur halusinasi tersebar secara acak dalam ruang probabilitas token.

Untuk mengkuantifikasi ketidakpastian (*confidence score*), kita menghitung **Marginal Entropy** dari distribusi jawaban akhir:

$$H(Y \mid X) = - \sum_{y \in \mathcal{Y}} P(y \mid X) \log P(y \mid X)$$

Jika $H(Y \mid X) \approx 0$, sistem memiliki derajat kepastian tinggi terhadap jawaban terpilih. Jika $H(Y \mid X) > \tau_{\text{entropy}}$, sistem secara otomatis mengeksekusi mekanisme fallback (misalnya: meningkatkan jumlah sampling $N$, memperlebar pencarian, atau eskalasi ke *human-in-the-loop*).

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem penalaran modular berbasis **Tree-of-Thoughts (ToT)** dengan algoritma **Beam Search**, dilengkapi validasi skema Pydantic, isolasi evaluasi asinkron, serta penanganan error deterministik.

```python
"""
Enterprise-Grade Tree-of-Thoughts (ToT) Engine.
Runtime: Python 3.11+
Dependencies: pydantic, openai / generic LLM client abstraction.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, ValidationError

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("ReasoningEngine")


# ============================================================================
# Domain Models & Schemas
# ============================================================================

class ThoughtCandidate(BaseModel):
    """Representasi satuan pemikiran diskret hasil generasi model."""
    thought_id: str = Field(description="Identifikasi unik untuk simpul pemikiran")
    content: str = Field(description="Isi teks langkah penalaran teknis")
    rationale: str = Field(description="Justifikasi logis mengapa pemikiran ini valid")


class ThoughtGenerationOutput(BaseModel):
    """Output parsing terstruktur dari prompt generator pikiran."""
    candidates: List[ThoughtCandidate] = Field(min_length=1)


class StateEvaluationOutput(BaseModel):
    """Output evaluasi heuristik untuk state penalaran."""
    score: float = Field(ge=0.0, le=1.0, description="Skor kelayakan state antara 0.0 hingga 1.0")
    classification: str = Field(description="'Sure', 'Likely', atau 'Impossible'")
    critique: str = Field(description="Analisis kritis kelemahan state saat ini")


@dataclass
class TreeNode:
    """Simpul dalam struktur data State-Space Search."""
    state_id: str
    parent: Optional[TreeNode]
    thought: str
    depth: int
    score: float = 0.0
    accumulated_path: List[str] = field(default_factory=list)
    children: List[TreeNode] = field(default_factory=list)

    def get_full_context(self) -> str:
        return " ->\n".join(self.accumulated_path)


# ============================================================================
# LLM Provider Abstraction
# ============================================================================

class BaseLLMClient(ABC):
    @abstractmethod
    async def generate_structured(
        self, system_prompt: str, user_prompt: str, response_schema: type[BaseModel]
    ) -> BaseModel:
        """Menghasilkan respon yang terjamin sesuai Pydantic Schema."""
        pass


class MockLLMClient(BaseLLMClient):
    """
    Mock LLM client untuk pengujian deterministic & CI/CD environment.
    Menstimulasikan perilaku probabilistik LLM produksi.
    """
    async def generate_structured(
        self, system_prompt: str, user_prompt: str, response_schema: type[BaseModel]
    ) -> BaseModel:
        await asyncio.sleep(0.05)  # Simulasi network latency
        
        if response_schema == ThoughtGenerationOutput:
            return ThoughtGenerationOutput(
                candidates=[
                    ThoughtCandidate(
                        thought_id="T1",
                        content="Dekomposisi sistem menjadi komponen Stateless Core dan Stateful Storage.",
                        rationale="Mengurangi kompleksitas konsistensi terdistribusi."
                    ),
                    ThoughtCandidate(
                        thought_id="T2",
                        content="Gunakan arsitektur Monolitik Terpusat dengan Thread Pool besar.",
                        rationale="Sederhana namun memiliki single-point-of-failure."
                    )
                ]
            )
        elif response_schema == StateEvaluationOutput:
            if "Monolitik" in user_prompt:
                return StateEvaluationOutput(
                    score=0.2,
                    classification="Impossible",
                    critique="Skalabilitas sistem tidak memadai untuk skala enterprise."
                )
            return StateEvaluationOutput(
                score=0.9,
                classification="Sure",
                critique="Sangat modular dan fault-tolerant."
            )
        raise ValueError(f"Skema tidak didukung: {response_schema}")


# ============================================================================
# Search Orchestrator: Tree-of-Thoughts with Beam Search
# ============================================================================

class TreeOfThoughtsSearchEngine:
    """
    Orkestrator pencarian penalaran non-linear berbasis Beam Search.
    Mengontrol batas kedalaman, token pruning, dan branching factor.
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        max_depth: int = 3,
        beam_width: int = 2,
        pruning_threshold: float = 0.5
    ):
        self.llm = llm_client
        self.max_depth = max_depth
        self.beam_width = beam_width
        self.pruning_threshold = pruning_threshold
        self._node_counter = 0

    def _next_node_id(self) -> str:
        self._node_counter += 1
        return f"node_{self._node_counter}"

    async def _generate_proposals(self, problem: str, current_path: List[str]) -> List[ThoughtCandidate]:
        path_str = "\n".join([f"Langkah {idx+1}: {step}" for idx, step in enumerate(current_path)])
        system_prompt = (
            "Anda adalah Perancang Penalaran Kritis Tingkat Tinggi. "
            "Tugas Anda adalah memecah masalah kompleks menjadi langkah penalaran diskret berikutnya. "
            "Kembalikan output строго dalam skema JSON terstruktur."
        )
        user_prompt = (
            f"Masalah Utama:\n{problem}\n\n"
            f"Jalur Penalaran Saat Ini:\n{path_str if path_str else '[Mulai dari Root]'}\n\n"
            "Tawarkan alternatif langkah logis berikutnya secara mendalam."
        )

        try:
            result = await self.llm.generate_structured(system_prompt, user_prompt, ThoughtGenerationOutput)
            return result.candidates  # type: ignore
        except Exception as e:
            logger.error(f"Gagal saat menghasilkan kandidat langkah: {str(e)}")
            return []

    async def _evaluate_state(self, problem: str, candidate_path: List[str]) -> float:
        path_str = " -> ".join(candidate_path)
        system_prompt = (
            "Anda adalah Sistem Verifikasi Evaluasi Status Logis. "
            "Analisis rantai penalaran dan berikan skor heuristik [0.0 - 1.0] "
            "yang mencerminkan probabilitas kebenaran menuju solusi akhir."
        )
        user_prompt = (
            f"Masalah Utama: {problem}\n"
            f"Evaluasi Evaluasi Rantai Penalaran Berikut:\n{path_str}"
        )

        try:
            result = await self.llm.generate_structured(system_prompt, user_prompt, StateEvaluationOutput)
            return result.score  # type: ignore
        except Exception as e:
            logger.warning(f"Evaluasi state gagal, fallback ke default minimal 0.0: {str(e)}")
            return 0.0

    async def execute_search(self, problem: str) -> Optional[TreeNode]:
        """
        Mengeksekusi penelusuran Beam Search terpandu pada pohon pemikiran.
        """
        logger.info(f"Memulai ToT Engine untuk masalah: '{problem[:50]}...'")
        
        # Root Node Initialization
        root = TreeNode(
            state_id=self._next_node_id(),
            parent=None,
            thought="ROOT",
            depth=0,
            score=1.0,
            accumulated_path=[]
        )
        current_beam: List[TreeNode] = [root]

        for depth in range(1, self.max_depth + 1):
            logger.info(f"--- Iterasi Pencarian Depth {depth}/{self.max_depth} (Aktif Beam: {len(current_beam)}) ---")
            candidates_for_next_beam: List[TreeNode] = []

            for parent_node in current_beam:
                # 1. Expand node: Generate thought steps
                proposals = await self._generate_proposals(problem, parent_node.accumulated_path)
                
                # 2. Score each candidate state secara paralel
                eval_tasks = []
                for p in proposals:
                    new_path = parent_node.accumulated_path + [p.content]
                    eval_tasks.append(self._evaluate_state(problem, new_path))
                
                scores = await asyncio.gather(*eval_tasks)

                # 3. Create child nodes & apply individual threshold pruning
                for proposal, score in zip(proposals, scores):
                    if score >= self.pruning_threshold:
                        child = TreeNode(
                            state_id=self._next_node_id(),
                            parent=parent_node,
                            thought=proposal.content,
                            depth=depth,
                            score=score,
                            accumulated_path=parent_node.accumulated_path + [proposal.content]
                        )
                        parent_node.children.append(child)
                        candidates_for_next_beam.append(child)
                    else:
                        logger.debug(f"Pruned thought di bawah threshold: '{proposal.content[:30]}' (Skor: {score})")

            # Check if all branches died out
            if not candidates_for_next_beam:
                logger.warning(f"Semua cabang dipangkas pada depth {depth}. Menghentikan ekspansi lebih lanjut.")
                break

            # 4. Beam Selection: Sort and retain Top-K
            candidates_for_next_beam.sort(key=lambda node: node.score, reverse=True)
            current_beam = candidates_for_next_beam[: self.beam_width]
            
            logger.info(f"Level {depth} selesai. Skor terbaik saat ini: {current_beam[0].score}")

        if not current_beam:
            return None

        # Return best terminal node
        best_node = max(current_beam, key=lambda n: n.score)
        logger.info(f"Pencarian selesai. Solusi terbaik ditemukan dengan skor akumulasi: {best_node.score}")
        return best_node


# ============================================================================
# Execution Entry Point
# ============================================================================

async def main():
    engine = TreeOfThoughtsSearchEngine(
        llm_client=MockLLMClient(),
        max_depth=2,
        beam_width=2,
        pruning_threshold=0.4
    )

    problem_statement = (
        "Rancang arsitektur microservices untuk sistem pembayaran real-time yang memproses "
        "100.000 transaksi per detik dengan toleransi latensi <10ms dan nol inkonsistensi saldo."
    )

    result_node = await engine.execute_search(problem_statement)

    if result_node:
        print("\n=== SOLUSI PENALARAN TERVERIFIKASI TERBAIK ===")
        print(f"Node ID: {result_node.state_id}")
        print(f"Skor Evaluasi: {result_node.score}")
        print("Langkah Rekonstruksi:")
        for idx, step in enumerate(result_node.accumulated_path):
            print(f"  {idx + 1}. {step}")
    else:
        print("Tidak ada solusi yang memenuhi threshold verifikasi kelayakan.")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 7. Edge Cases & Failure Modes

Pada level infrastruktur, algoritma penalaran non-linear memiliki karakteristik kegagalan yang berbeda drastis dibandingkan linear prompt generation:

### 1. The Sybil-Agreement Trap (False Consensus)
- **Gejala**: Pada *Self-Consistency Voting*, model yang diinstruksikan melakukan sampling independen ($N=20$) memberikan jawaban identik yang ternyata secara matematis/faktual salah (*correlated hallucinations*).
- **Akar Masalah**: Bias bobot internal pretraining dominan terhadap token tertentu, atau *temperature* terlalu rendah ($T < 0.2$), sehingga tidak menghasilkan divergensi jalur representasi.
- **Mitigasi**: Gunakan **Stochastic Prompt Variation** (variasikan *system prompt persona* atau urutan klausul) dikombinasikan dengan suhu dinamis ($T \in [0.6, 0.9]$) dan uji *Semantic Entropy* alih-alih sekadar *Lexical String Exact-Match*.

### 2. State-Space Explosion & Runaway Token Spend
- **Gejala**: Algoritma Tree-of-Thoughts dengan branching factor $b=5$ dan kedalaman $D=4$ mengeksekusi hingga $\sum_{i=1}^4 5^i = 780$ panggilan LLM per request.
- **Mitigasi**: Terapkan **Strict Token Budgeting & Circuit Breaking**. Implementasikan *Early Exit Criterion*: jika simpul memiliki evaluasi $v \ge 0.95$ dan klasifikasi `Sure`, bypass sisa penelusuran anak cabang dan langsung lakukan ekspansi greedy.

### 3. Cognitive Deadlock & Degenerate Loops
- **Gejala**: Pada *Graph-of-Thoughts*, node baru terus melakukan agregasi dari node sebelumnya tanpa memberikan informasi reduksi entropi baru (berputar pada parafrase tanpa menghasilkan solusi).
- **Mitigasi**: Lacak riwayat state menggunakan hashing semantik (vektor embedding simpul). Jika jarak kosinus $\cos(\theta) > 0.92$ terhadap *ancestor node*, lakukan *hard pruning* dan injeksikan penalti entropi.

---

## 8. Trade-offs & Alternatif Solusi

Setiap paradigma penalaran memiliki kurva perbandingan latensi, biaya, dan ketahanan akurasi:

| Strategi Penalaran | Typical Latency Overhead | Token Consumption Factor | Deterministic Reliability | Kompleksitas Orchestration | Best Used When... |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Standard CoT** | $1\times$ (Baseline) | $1.2\times - 1.5\times$ | Rendah (Gampang tergelincir pada langkah panjang) | Rendah (Single API call) | Task umum, klarifikasi logika dasar, ringkasan kontekstual |
| **Self-Consistency (CoT-SC)** | $1\times$ (Parallel) / $N\times$ (Serial) | $N\times$ ($N \in [5, 40]$) | Tinggi pada domain jawaban diskret/matematis | Rendah-Sedang (Agregasi output via Voting) | Soal numerik, ekstraksi entitas rigid, klasifikasi multi-kelas rentan bias |
| **Tree-of-Thoughts (ToT)** | $D \times (\text{Gen} + \text{Eval})$ | $O(b^D)$ (Tanpa Pruning) / $O(b \cdot k \cdot D)$ (Beam Search) | Sangat Tinggi (Dapat memulihkan diri via backtracking) | Tinggi (Butuh state machine, search controller) | Perencanaan arsitektur sistem, sintesis kode kompleks, optimasi rute logistik |
| **Graph-of-Thoughts (GoT)** | Tinggi (Bervariasi sesuai topologi graf) | Sangat Tinggi ($10\times - 50\times$) | Maksimal (Mendukung rekursi, dekomposisi & sintesis silang) | Sangat Tinggi (DAG execution engine dengan cycle detection) | Penulisan dokumen analitis panjang, investigasi forensik kejahatan finansial |

---

## 9. Best Practices & Standard Industri

1. **Decouple Generator and Evaluator System Prompts**: Jangan gunakan konteks prompt yang sama untuk membuat langkah dan menilai kelayakannya. Gunakan prompt adversarial khusus ("*Anda adalah Auditor Keamanan yang bertugas mematahkan asumsi langkah berikut*") untuk tahap evaluasi guna mencegah *confirmation bias*.
2. **Deterministic Output Serialization**: Selalu paksakan runtime untuk mengembalikan format terstruktur (JSON Schema/Pydantic validation). Jangan pernah melakukan parsing teks bebas berbasis regex pada sistem pencarian non-linear produksi.
3. **Dynamic Temperature Allocation**:
   - Fase *Generation/Branching*: Setel $T = 0.7 - 0.85$ untuk memastikan eksplorasi alternatif langkah penalaran yang heterogen.
   - Fase *Evaluation/Scoring*: Setel $T = 0.0$ untuk memastikan nilai evaluasi dan klasifikasi heuristik bersifat stabil dan deterministik.
4. **State Snapshotting & Audit Trails**: Simpan seluruh graf penalaran (termasuk simpul yang dipangkas beserta alasan penolakannya) ke dalam storage persisten (seperti DynamoDB atau PostgreSQL JSONB). Ini adalah data latih vital untuk proses optimasi prompt atau *fine-tuning* model internal (*Distillation of Reasoning*).

---

## 10. Hands-on Lab Exercise: Membangun Verifikasi GoT Sub-Graph

### Skenario Lab
Anda ditugaskan membangun pipeline inferensi Graph-of-Thoughts sederhana untuk menyelesaikan masalah dekomposisi dan agregasi: Mengidentifikasi kerentanan keamanan pada 3 microservices independen, lalu menggabungkan (*merging*) hasil temuan menjadi laporan mitigasi terpadu yang bebas duplikasi dan memperhitungkan interaksi lintas layanan.

### Instruksi Bertahap

#### Langkah 1: Siapkan Environment
Instal paket yang dibutuhkan:
```bash
pip install pydantic openai asyncio
```

#### Langkah 2: Implementasikan Logika Graph Aggregator
Buat file `got_aggregation_lab.py`:
```python
import asyncio
from typing import List
from pydantic import BaseModel, Field

# 1. Definisikan Kontrak Data
class VulnerabilityItem(BaseModel):
    service_name: str
    cve_id_or_type: str
    severity: str
    description: str

class ServiceAnalysisResult(BaseModel):
    vulnerabilities: List[VulnerabilityItem]

class ConsolidatedRiskAssessment(BaseModel):
    critical_attack_vector: str = Field(description="Bagaimana kerentanan lintas layanan dapat dirangkai oleh penyerang")
    deduplicated_risks: List[str]
    immediate_mitigations: List[str]

# 2. Definisikan Node Operasi Graf
async def analyze_service_node(service_name: str, config_data: str) -> ServiceAnalysisResult:
    """Simulasi Node Dekomposisi Independen (Sub-graf paralel)."""
    await asyncio.sleep(0.1) # Network mock
    logger_out = f"Menganalisis {service_name}..."
    print(logger_out)
    
    # Mocking output LLM berbasis masukan
    if "Auth" in service_name:
        return ServiceAnalysisResult(vulnerabilities=[
            VulnerabilityItem(service_name=service_name, cve_id_or_type="JWT-None-Alg", severity="CRITICAL", description="Token parsing mengizinkan signature 'none'"),
            VulnerabilityItem(service_name=service_name, cve_id_or_type="Leak-Mem", severity="LOW", description="Trace log mengekspos token hash")
        ])
    else:
        return ServiceAnalysisResult(vulnerabilities=[
            VulnerabilityItem(service_name=service_name, cve_id_or_type="SSRF-Proxy", severity="HIGH", description="Gateway mengizinkan forwarding internal loopback tanpa otentikasi")
        ])

async def aggregate_thoughts_node(results: List[ServiceAnalysisResult]) -> ConsolidatedRiskAssessment:
    """Node Agregasi/Merge: Menggabungkan beberapa simpul pikiran menjadi satu wawasan sintesis."""
    await asyncio.sleep(0.1)
    print("Mengeksekusi Thought Merging / Graph Aggregation...")
    
    # Di level produksi: Panggil LLM dengan payload gabungan dari seluruh simpul sebelumnya
    return ConsolidatedRiskAssessment(
        critical_attack_vector="Penyerang mengeksploitasi SSRF pada Gateway untuk memalsukan request internal ke Auth Service menggunakan forged token dengan 'none' algorithm.",
        deduplicated_risks=[
            "Eksposur SSRF tidak terotentikasi",
            "Bypass otentikasi JWT menyeluruh"
        ],
        immediate_mitigations=[
            "Blokir loopback access pada Gateway reverse proxy",
            "Perbarui dependensi decoder JWT dan tolak secara eksplisit skema algoritma 'none'"
        ]
    )

# 3. Eksekusi Orchestration Graph
async def run_pipeline():
    services = [
        ("AuthService", "config: allow_unverified=True"),
        ("APIGateway", "config: forward_headers=['X-Forwarded-For']")
    ]
    
    # Tahap 1: Eksekusi Cabang Sub-graf Paralel
    print("[GoT Phase 1] Menjalankan Evaluasi Simpul Sub-Masalah...")
    tasks = [analyze_service_node(name, conf) for name, conf in services]
    sub_results = await asyncio.gather(*tasks)
    
    # Tahap 2: Transformasi Graf (Aggregation / Merge Transformation)
    print("\n[GoT Phase 2] Menggabungkan Jalur Penalaran Menjadi Simpul Konsolidasi...")
    final_assessment = await aggregate_thoughts_node(sub_results)
    
    print("\n=== HASIL AKHIR PENALARAN SINTESIS GRAF ===")
    print(f"Attack Vector: {final_assessment.critical_attack_vector}")
    print("Mitigasi Utama:")
    for m in final_assessment.immediate_mitigations:
        print(f" - {m}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
```

### Kriteria Keberhasilan Verifikasi
1. Script berjalan secara asinkron tanpa *blocking event loop*.
2. Seluruh simpul analisis independen dieksekusi secara konkuren sebelum fase konsolidasi dimulai.
3. Node agregator mampu mendeteksi korelasi eksploitasi silang (*lateral movement*) antara `AuthService` dan `APIGateway` yang mustahil disimpulkan jika evaluasi dilakukan secara sekuensial linear tanpa state merging.